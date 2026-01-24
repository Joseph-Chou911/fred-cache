#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_unified_report_md.py

Render a human/audit friendly report.md from unified_dashboard_latest_v1 JSON.

Design goals:
- Deterministic output ordering (stable diffs)
- No external fetch (pure rendering)
- Clear separation of module sections
- Canonicalized Margin rationale printing (build.cross_module.margin_rationale)

Input schema (expected):
- schema_version: unified_dashboard_latest_v1
- generated_at_utc
- modules.market_cache.dashboard_latest.{meta,rows}
- modules.fred_cache.dashboard_latest.{meta,rows}
- modules.roll25_cache.{latest_report,core}
- modules.taiwan_margin_financing.{latest}
- modules.taiwan_margin_financing.cross_module.{margin_signal,...} (optional)

Usage:
  python scripts/render_unified_report_md.py \
    --input unified_dashboard_latest.json \
    --output report.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


NA = "NA"


# -----------------------------
# Helpers
# -----------------------------
def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def g(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        if k not in cur:
            return default
        cur = cur[k]
    return cur


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def fmt_bool(x: Any) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    return NA if x is None else str(x)


def fmt_num_default(x: Any) -> str:
    if x is None:
        return NA
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return fmt_bool(x)
    if not is_number(x):
        return str(x)
    # integer-like
    if abs(float(x) - round(float(x))) < 1e-12 and abs(float(x)) < 1e15:
        return str(int(round(float(x))))
    # default
    return f"{float(x):.6f}".rstrip("0").rstrip(".")


def fmt_num_fixed(x: Any, ndp: int) -> str:
    if x is None:
        return NA
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return fmt_bool(x)
    if not is_number(x):
        return str(x)
    # keep fixed decimals (audit readability)
    return f"{float(x):.{ndp}f}"


def md_kv(lines: List[str], k: str, v: Any) -> None:
    if isinstance(v, bool):
        s = fmt_bool(v)
    elif isinstance(v, list):
        s = json.dumps(v, ensure_ascii=False)
    elif is_number(v):
        s = fmt_num_default(v)
    elif v is None:
        s = NA
    else:
        s = str(v)
    lines.append(f"- {k}: {s}")


def md_h3(lines: List[str], title: str) -> None:
    lines.append("")
    lines.append(f"## {title}")


def md_h4(lines: List[str], title: str) -> None:
    lines.append("")
    lines.append(f"### {title}")


def md_table(lines: List[str], headers: List[str], rows: List[List[str]]) -> None:
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        # Ensure length match
        rr = r + [""] * (len(headers) - len(r))
        rr = rr[: len(headers)]
        lines.append("| " + " | ".join(rr) + " |")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# -----------------------------
# Domain mappings / deterministic derivations
# -----------------------------
# Heuristic direction for FRED series (risk-bias). Unmapped => NA.
# NOTE: You can extend this map; renderer does not infer beyond this table.
FRED_DIR_MAP: Dict[str, str] = {
    # equity / risk assets: higher => more risk-on / stretched (treat as HIGH risk bias)
    "SP500": "HIGH",
    "DJIA": "HIGH",
    "NASDAQCOM": "HIGH",
    # volatility / stress: higher => more risk-off / stress (treat as HIGH risk bias)
    "VIXCLS": "HIGH",
    "STLFSI4": "HIGH",
    # credit spread: higher spread => higher risk (HIGH risk bias)
    "BAMLH0A0HYM2": "HIGH",
    # yields / curve: higher may signal tighter conditions / stress depending regime
    # keep as HIGH for your current display (consistent with your report samples)
    "DGS10": "HIGH",
    "DGS2": "HIGH",
    "T10Y3M": "HIGH",
    "T10Y2Y": "HIGH",
    # dollar index (broad USD): higher can be tightening; keep NA unless you decide
    # "DTWEXBGS": "HIGH",
    # leverage: your report example uses LOW (keep)
    "NFCINONFINLEVERAGE": "LOW",
}


def derive_class_from_tag(tag: Any) -> str:
    """
    Deterministic class:
      - LONG if tag contains LONG_EXTREME
      - LEVEL if tag contains EXTREME_Z
      - JUMP if any tag contains 'JUMP'
    If multiple => join by '+', with order LONG, LEVEL, JUMP (stable).
    """
    if not isinstance(tag, str) or not tag:
        return "NONE"
    parts = [p.strip() for p in tag.split(",") if p.strip()]
    flags = []
    if any(p == "LONG_EXTREME" for p in parts):
        flags.append("LONG")
    if any(p == "EXTREME_Z" for p in parts):
        flags.append("LEVEL")
    if any("JUMP" in p for p in parts):
        flags.append("JUMP")
    if not flags:
        return "NONE"
    # stable
    order = {"LONG": 0, "LEVEL": 1, "JUMP": 2}
    flags = sorted(list(dict.fromkeys(flags)), key=lambda x: order.get(x, 99))
    return "+".join(flags)


def severity(sig: str) -> int:
    m = {"ALERT": 3, "WATCH": 2, "INFO": 1, "NONE": 0, NA: 0}
    return m.get(sig or NA, 0)


def resonance_level(market_sig: str, fred_sig: str) -> str:
    """
    Deterministic resonance label (minimal set, stable):
      - CONCORD_STRONG: both >= WATCH
      - STRUCTURAL_VS_SHOCK: market >= WATCH and fred == INFO
      - SHOCK_VS_STRUCTURAL: market == INFO and fred >= WATCH
      - CONCORD_WEAK: both INFO
      - DISCORD: otherwise
    """
    ms = severity(market_sig)
    fs = severity(fred_sig)
    if ms >= 2 and fs >= 2:
        return "CONCORD_STRONG"
    if ms >= 2 and fs == 1:
        return "STRUCTURAL_VS_SHOCK"
    if ms == 1 and fs >= 2:
        return "SHOCK_VS_STRUCTURAL"
    if ms == 1 and fs == 1:
        return "CONCORD_WEAK"
    return "DISCORD"


# -----------------------------
# Renderers
# -----------------------------
def render_market_section(lines: List[str], market: Dict[str, Any]) -> None:
    md_h3(lines, "market_cache (detailed)")

    meta = g(market, "dashboard_latest", "meta", default={})
    # Header bullets (match your report style)
    md_kv(lines, "as_of_ts", meta.get("stats_as_of_ts", NA))
    md_kv(lines, "run_ts_utc", meta.get("run_ts_utc", NA))
    md_kv(lines, "ruleset_id", meta.get("ruleset_id", NA))
    md_kv(lines, "script_fingerprint", meta.get("script_fingerprint", NA))
    md_kv(lines, "script_version", meta.get("script_version", NA))
    md_kv(lines, "series_count", meta.get("series_count", NA))

    rows = g(market, "dashboard_latest", "rows", default=[])
    out_rows: List[List[str]] = []
    headers = [
        "series", "signal", "dir", "market_class",
        "value", "data_date", "age_h",
        "z60", "p60", "p252",
        "zΔ60", "pΔ60", "ret1%60",
        "reason", "tag", "prev", "delta",
        "streak_hist", "streak_wa", "source",
    ]

    for r in rows if isinstance(rows, list) else []:
        series = r.get("series", NA)
        sig = r.get("signal_level", NA)
        d = r.get("dir", NA)
        tag = r.get("tag", NA)
        mclass = derive_class_from_tag(tag)
        out_rows.append([
            str(series),
            str(sig),
            str(d),
            str(mclass),
            fmt_num_default(r.get("value")),
            str(r.get("data_date", NA)),
            fmt_num_fixed(r.get("age_hours"), 6),
            fmt_num_fixed(r.get("z60"), 6),
            fmt_num_fixed(r.get("p60"), 6) if is_number(r.get("p60")) else fmt_num_default(r.get("p60")),
            fmt_num_fixed(r.get("p252"), 6) if is_number(r.get("p252")) else fmt_num_default(r.get("p252")),
            fmt_num_fixed(r.get("z_delta60"), 6),
            fmt_num_default(r.get("p_delta60")),
            fmt_num_fixed(r.get("ret1_pct60"), 6),
            str(r.get("reason", NA)),
            str(tag),
            str(r.get("prev_signal", NA)),
            str(r.get("delta_signal", NA)),
            fmt_num_default(r.get("streak_hist")),
            fmt_num_default(r.get("streak_wa")),
            str(r.get("source_url", NA)),
        ])

    md_table(lines, headers, out_rows)


def render_fred_section(lines: List[str], fred: Dict[str, Any]) -> None:
    md_h3(lines, "fred_cache (ALERT+WATCH+INFO)")

    meta = g(fred, "dashboard_latest", "meta", default={})
    summary = meta.get("summary", {}) if isinstance(meta.get("summary", {}), dict) else {}

    md_kv(lines, "as_of_ts", meta.get("stats_as_of_ts", NA))
    md_kv(lines, "run_ts_utc", meta.get("run_ts_utc", NA))
    md_kv(lines, "ruleset_id", meta.get("ruleset_id", NA))
    md_kv(lines, "script_fingerprint", meta.get("script_fingerprint", NA))
    md_kv(lines, "script_version", meta.get("script_version", NA))
    md_kv(lines, "ALERT", summary.get("ALERT", NA))
    md_kv(lines, "WATCH", summary.get("WATCH", NA))
    md_kv(lines, "INFO", summary.get("INFO", NA))
    md_kv(lines, "NONE", summary.get("NONE", NA))
    md_kv(lines, "CHANGED", summary.get("CHANGED", NA))

    rows = g(fred, "dashboard_latest", "rows", default=[])
    out_rows: List[List[str]] = []
    headers = [
        "series", "signal", "fred_dir", "fred_class",
        "value", "data_date", "age_h",
        "z60", "p60", "p252",
        "zΔ60", "pΔ60", "ret1%",
        "reason", "tag", "prev", "delta", "source",
    ]

    for r in rows if isinstance(rows, list) else []:
        series = r.get("series", NA)
        sig = r.get("signal_level", NA)
        fdir = FRED_DIR_MAP.get(str(series), NA)
        tag = r.get("tag", NA)
        fclass = derive_class_from_tag(tag)
        out_rows.append([
            str(series),
            str(sig),
            str(fdir),
            str(fclass),
            fmt_num_default(r.get("value")),
            str(r.get("data_date", NA)),
            fmt_num_fixed(r.get("age_hours"), 6),
            fmt_num_fixed(r.get("z60"), 6),
            fmt_num_fixed(r.get("p60"), 6) if is_number(r.get("p60")) else fmt_num_default(r.get("p60")),
            fmt_num_fixed(r.get("p252"), 6) if is_number(r.get("p252")) else fmt_num_default(r.get("p252")),
            fmt_num_fixed(r.get("z_delta_60"), 6),
            fmt_num_default(r.get("p_delta_60")),
            fmt_num_fixed(r.get("ret1_pct"), 6),
            str(r.get("reason", NA)),
            str(tag),
            str(r.get("prev_signal", NA)),
            str(r.get("delta_signal", NA)),
            str(r.get("source_url", NA)),
        ])

    md_table(lines, headers, out_rows)

    # Audit notes (match your report)
    md_h3(lines, "Audit Notes")
    lines.append("- fred_dir is DERIVED (heuristic) from a fixed mapping table in this script (FRED_DIR_MAP). Unmapped series => NA.")
    lines.append("- market_class/fred_class are DERIVED from tag only (deterministic): LONG if tag contains LONG_EXTREME; LEVEL if tag contains EXTREME_Z; JUMP if tag contains JUMP* (incl. JUMP_DELTA/JUMP_RET); otherwise NONE.")
    lines.append("- roll25_heated/roll25_confidence are COMPUTED in build step from roll25 JSON only; renderer does not recompute.")


def render_resonance_matrix(lines: List[str], market: Dict[str, Any], fred: Dict[str, Any]) -> None:
    md_h3(lines, "Resonance Matrix (strict + alias)")

    mrows = g(market, "dashboard_latest", "rows", default=[])
    frows = g(fred, "dashboard_latest", "rows", default=[])

    m_by_series: Dict[str, Dict[str, Any]] = {}
    f_by_series: Dict[str, Dict[str, Any]] = {}

    for r in mrows if isinstance(mrows, list) else []:
        s = str(r.get("series", NA))
        m_by_series[s] = r
    for r in frows if isinstance(frows, list) else []:
        s = str(r.get("series", NA))
        f_by_series[s] = r

    headers = [
        "resonance_level", "pair_type", "series",
        "market_series", "fred_series",
        "market_signal", "fred_signal",
        "market_class", "fred_class",
        "market_tag", "fred_tag",
        "market_dir", "fred_dir",
        "market_reason", "fred_reason",
        "market_date", "fred_date",
        "market_source", "fred_source",
    ]

    out: List[List[str]] = []

    # Alias pairs (stable order)
    alias_pairs: List[Tuple[str, str, str]] = [
        ("VIX↔VIXCLS", "VIX", "VIXCLS"),
    ]

    for label, ms, fs in alias_pairs:
        if ms in m_by_series and fs in f_by_series:
            mr = m_by_series[ms]
            fr = f_by_series[fs]
            msig = str(mr.get("signal_level", NA))
            fsig = str(fr.get("signal_level", NA))
            out.append([
                resonance_level(msig, fsig),
                "ALIAS",
                label,
                ms,
                fs,
                msig,
                fsig,
                derive_class_from_tag(mr.get("tag", "")),
                derive_class_from_tag(fr.get("tag", "")),
                str(mr.get("tag", NA)),
                str(fr.get("tag", NA)),
                str(mr.get("dir", NA)),
                FRED_DIR_MAP.get(fs, NA),
                str(mr.get("reason", NA)),
                str(fr.get("reason", NA)),
                str(mr.get("data_date", NA)),
                str(fr.get("data_date", NA)),
                str(mr.get("source_url", NA)),
                str(fr.get("source_url", NA)),
            ])

    # Strict pairs: same series in both
    common = sorted(set(m_by_series.keys()).intersection(set(f_by_series.keys())))
    for s in common:
        mr = m_by_series[s]
        fr = f_by_series[s]
        msig = str(mr.get("signal_level", NA))
        fsig = str(fr.get("signal_level", NA))
        out.append([
            resonance_level(msig, fsig),
            "STRICT",
            s,
            s,
            s,
            msig,
            fsig,
            derive_class_from_tag(mr.get("tag", "")),
            derive_class_from_tag(fr.get("tag", "")),
            str(mr.get("tag", NA)),
            str(fr.get("tag", NA)),
            str(mr.get("dir", NA)),
            FRED_DIR_MAP.get(s, NA),
            str(mr.get("reason", NA)),
            str(fr.get("reason", NA)),
            str(mr.get("data_date", NA)),
            str(fr.get("data_date", NA)),
            str(mr.get("source_url", NA)),
            str(fr.get("source_url", NA)),
        ])

    md_table(lines, headers, out)


def render_roll25(lines: List[str], roll25: Dict[str, Any], cross: Optional[Dict[str, Any]] = None) -> None:
    md_h3(lines, "roll25_cache (TW turnover)")

    core = roll25.get("core", {}) if isinstance(roll25.get("core", {}), dict) else {}
    latest = roll25.get("latest_report", {}) if isinstance(roll25.get("latest_report", {}), dict) else {}

    md_kv(lines, "status", roll25.get("status", NA))
    md_kv(lines, "UsedDate", core.get("UsedDate", latest.get("used_date", NA)))
    md_kv(lines, "tag", core.get("tag", latest.get("tag", NA)))
    md_kv(lines, "risk_level", core.get("risk_level", latest.get("risk_level", NA)))
    md_kv(lines, "turnover_twd", core.get("turnover_twd", NA))
    md_kv(lines, "turnover_unit", core.get("turnover_unit", NA))
    md_kv(lines, "volume_multiplier", core.get("volume_multiplier", NA))
    md_kv(lines, "vol_multiplier", core.get("vol_multiplier", NA))
    md_kv(lines, "amplitude_pct", core.get("amplitude_pct", NA))
    md_kv(lines, "pct_change", core.get("pct_change", NA))
    md_kv(lines, "close", core.get("close", NA))
    md_kv(lines, "LookbackNTarget", core.get("LookbackNTarget", NA))
    md_kv(lines, "LookbackNActual", core.get("LookbackNActual", NA))

    sigs = core.get("signals", {}) if isinstance(core.get("signals", {}), dict) else {}
    md_kv(lines, "signals.DownDay", sigs.get("DownDay", NA))
    md_kv(lines, "signals.VolumeAmplified", sigs.get("VolumeAmplified", NA))
    md_kv(lines, "signals.VolAmplified", sigs.get("VolAmplified", NA))
    md_kv(lines, "signals.NewLow_N", sigs.get("NewLow_N", NA))
    md_kv(lines, "signals.ConsecutiveBreak", sigs.get("ConsecutiveBreak", NA))
    md_kv(lines, "signals.OhlcMissing", sigs.get("OhlcMissing", NA))

    md_h4(lines, "roll25_heated / confidence (from build)")
    if cross is None:
        md_kv(lines, "roll25_heated", NA)
        md_kv(lines, "roll25_confidence", NA)
        md_kv(lines, "consistency(Margin×Roll25)", NA)
        md_kv(lines, "margin_signal", NA)
        md_kv(lines, "margin_signal_source", NA)
    else:
        md_kv(lines, "roll25_heated", cross.get("roll25_heated", NA))
        md_kv(lines, "roll25_confidence", cross.get("roll25_confidence", NA))
        md_kv(lines, "consistency(Margin×Roll25)", cross.get("consistency", NA))
        md_kv(lines, "margin_signal", cross.get("margin_signal", NA))
        md_kv(lines, "margin_signal_source", cross.get("margin_signal_source", NA))

        # --- UPDATED: Canonical margin_rationale printing (stable order + aliases) ---
        mr = cross.get("margin_rationale", None)
        if isinstance(mr, dict) and mr:
            md_h4(lines, "margin_rationale (from build; canonical order)")
            # Canonicalize field names for stable report diffs (no inference).
            method = mr.get("method", NA)
            basis = mr.get("basis", NA)
            rule_version = mr.get("rule_version", NA)
            rule_hit = mr.get("rule_hit", NA)

            chg_last5 = mr.get("chg_last5", [])
            if not isinstance(chg_last5, list):
                chg_last5 = []

            sum_last5 = mr.get("sum_last5", None)
            pos_days_last5 = mr.get("pos_days_last5", None)
            latest_chg = mr.get("latest_chg", None)

            md_kv(lines, "method", method)
            md_kv(lines, "basis", basis)
            md_kv(lines, "rule_version", rule_version)
            md_kv(lines, "rule_hit", rule_hit)

            md_kv(lines, "chg_last5", chg_last5 if chg_last5 else NA)
            md_kv(lines, "sum_last5", sum_last5)
            md_kv(lines, "pos_days_last5", pos_days_last5)
            md_kv(lines, "latest_chg", latest_chg)

            lines.append("")
            lines.append("##### margin_rationale (aliases for report continuity)")
            md_kv(lines, "sum_chg_yi_last5", sum_last5)
            md_kv(lines, "latest.chg_yi", latest_chg)
            md_kv(lines, "pos_days_last5", pos_days_last5)

            # Print extras (sorted) to avoid silent loss
            extra_keys = sorted([k for k in mr.keys() if k not in {
                "method", "basis", "rule_version", "rule_hit",
                "chg_last5", "sum_last5", "pos_days_last5", "latest_chg",
            }])
            if extra_keys:
                lines.append("")
                lines.append("##### margin_rationale (extra fields)")
                for k in extra_keys:
                    md_kv(lines, k, mr.get(k))
        # If mr missing => do nothing here; we still show margin_signal fields above.


def render_unified_judgment(lines: List[str], market: Dict[str, Any], fred: Dict[str, Any], cross: Optional[Dict[str, Any]]) -> None:
    md_h3(lines, "Unified Risk Judgment (Market + FRED + Roll25)")

    # market counts
    mrows = g(market, "dashboard_latest", "rows", default=[])
    frows = g(fred, "dashboard_latest", "rows", default=[])
    m_watch = sum(1 for r in mrows if isinstance(r, dict) and r.get("signal_level") == "WATCH")
    m_alert = sum(1 for r in mrows if isinstance(r, dict) and r.get("signal_level") == "ALERT")
    f_watch = sum(1 for r in frows if isinstance(r, dict) and r.get("signal_level") == "WATCH")
    f_alert = sum(1 for r in frows if isinstance(r, dict) and r.get("signal_level") == "ALERT")

    md_kv(lines, "market_WATCH", m_watch)
    md_kv(lines, "market_ALERT", m_alert)
    md_kv(lines, "fred_WATCH", f_watch)
    md_kv(lines, "fred_ALERT", f_alert)

    roll25_heated = cross.get("roll25_heated", NA) if isinstance(cross, dict) else NA
    roll25_conf = cross.get("roll25_confidence", NA) if isinstance(cross, dict) else NA
    md_kv(lines, "roll25_heated", roll25_heated)
    md_kv(lines, "roll25_confidence", roll25_conf)

    # Deterministic unified state rule (renderer-only; transparent)
    # NOTE: This is intentionally simple; your build step can override if you later embed a field.
    has_m = (m_watch + m_alert) > 0
    has_f = (f_watch + f_alert) > 0
    heated = (roll25_heated is True)

    if has_m and has_f:
        uni = "RESONANCE_MF"
    elif has_m and not has_f:
        uni = "RESONANCE_M"
    elif (not has_m) and has_f:
        uni = "RESONANCE_F"
    else:
        uni = "CALM"
    if heated:
        uni = uni + "+ROLL25"

    md_kv(lines, "UnifiedState", uni)
    lines.append("")
    lines.append("- Rule: UnifiedState is derived deterministically from (market has WATCH/ALERT?, fred has WATCH/ALERT?, roll25_heated). No forecast inference.")


def summarize_margin_last5(series: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute summary for TWSE/TPEX from latest.series.*.rows (first 5 entries as latest->older).
    Returns a dict with keys matching your report style.
    """
    rows = series.get("rows", []) if isinstance(series.get("rows", []), list) else []
    if not rows:
        return {
            "latest": {},
            "last5": {},
        }

    def safe_get(i: int) -> Optional[Dict[str, Any]]:
        if 0 <= i < len(rows) and isinstance(rows[i], dict):
            return rows[i]
        return None

    latest = safe_get(0) or {}
    last5 = [safe_get(i) for i in range(5)]
    last5 = [x for x in last5 if isinstance(x, dict)]

    chg = []
    for x in last5:
        v = x.get("chg_yi", None)
        if is_number(v):
            chg.append(float(v))
    sum5 = sum(chg) if chg else None
    avg5 = (sum5 / len(chg)) if chg else None
    pos_days = sum(1 for v in chg if v > 0) if chg else None
    neg_days = sum(1 for v in chg if v < 0) if chg else None
    max5 = max(chg) if chg else None
    min5 = min(chg) if chg else None

    return {
        "latest": {
            "date": latest.get("date", NA),
            "balance_yi": latest.get("balance_yi", NA),
            "chg_yi": latest.get("chg_yi", NA),
        },
        "last5": {
            "sum_chg_yi_last5": sum5,
            "avg_chg_yi_last5": avg5,
            "pos_days_last5": pos_days,
            "neg_days_last5": neg_days,
            "max_chg_last5": max5,
            "min_chg_last5": min5,
        },
    }


def render_taiwan_margin(lines: List[str], twm: Dict[str, Any]) -> None:
    md_h3(lines, "taiwan_margin_financing (TWSE/TPEX)")

    latest = twm.get("latest", {}) if isinstance(twm.get("latest", {}), dict) else {}
    series_all = g(latest, "series", default={})
    if not isinstance(series_all, dict) or not series_all:
        lines.append("- (no data)")
        return

    for k in ["TWSE", "TPEX"]:
        s = series_all.get(k, {}) if isinstance(series_all.get(k, {}), dict) else {}
        md_h4(lines, f"{k} (data_date={s.get('data_date', NA)})")
        md_kv(lines, "source_url", s.get("source_url", NA))

        summ = summarize_margin_last5(s)
        latest_row = summ["latest"]
        last5 = summ["last5"]

        md_kv(lines, "latest.date", latest_row.get("date", NA))
        md_kv(lines, "latest.balance_yi", latest_row.get("balance_yi", NA))
        md_kv(lines, "latest.chg_yi", latest_row.get("chg_yi", NA))

        md_kv(lines, "sum_chg_yi_last5", last5.get("sum_chg_yi_last5", NA))
        md_kv(lines, "avg_chg_yi_last5", last5.get("avg_chg_yi_last5", NA))
        md_kv(lines, "pos_days_last5", last5.get("pos_days_last5", NA))
        md_kv(lines, "neg_days_last5", last5.get("neg_days_last5", NA))
        md_kv(lines, "max_chg_last5", last5.get("max_chg_last5", NA))
        md_kv(lines, "min_chg_last5", last5.get("min_chg_yi_last5", last5.get("min_chg_last5", NA)))


def render_report(unified: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append("# Unified Risk Dashboard Report")
    lines.append("")
    lines.append("## Module Status")

    modules = unified.get("modules", {}) if isinstance(unified.get("modules", {}), dict) else {}
    for name in ["market_cache", "fred_cache", "roll25_cache", "taiwan_margin_financing"]:
        st = g(modules, name, "status", default=NA)
        lines.append(f"- {name}: {st}")

    gen = unified.get("generated_at_utc", NA)
    lines.append(f"- unified_generated_at_utc: {gen}")

    market = modules.get("market_cache", {}) if isinstance(modules.get("market_cache", {}), dict) else {}
    fred = modules.get("fred_cache", {}) if isinstance(modules.get("fred_cache", {}), dict) else {}
    roll25 = modules.get("roll25_cache", {}) if isinstance(modules.get("roll25_cache", {}), dict) else {}
    twm = modules.get("taiwan_margin_financing", {}) if isinstance(modules.get("taiwan_margin_financing", {}), dict) else {}
    cross = twm.get("cross_module", None) if isinstance(twm.get("cross_module", None), dict) else None

    render_market_section(lines, market)
    render_fred_section(lines, fred)
    render_resonance_matrix(lines, market, fred)
    render_roll25(lines, roll25, cross=cross)
    render_unified_judgment(lines, market, fred, cross=cross)
    render_taiwan_margin(lines, twm)

    # Footer (optional, stable)
    lines.append("")
    lines.append(f"<!-- rendered_at_utc: {now_utc_iso()} -->")
    return "\n".join(lines) + "\n"


# -----------------------------
# CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render report.md from unified_dashboard_latest_v1 JSON.")
    p.add_argument("--input", default="unified_dashboard_latest.json", help="Path to unified_dashboard_latest.json")
    p.add_argument("--output", default="report.md", help="Output report path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    data = _load_json(args.input)
    if not isinstance(data, dict):
        raise SystemExit("Input JSON is not an object.")
    out = render_report(data)
    _write_text(args.output, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())