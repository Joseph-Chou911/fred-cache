#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render unified_dashboard/latest.json into report.md

Adds:
- (2) Positioning Matrix (report-only; deterministic; uses signals already present in unified JSON)
- roll25_derived (realized vol / max drawdown)
- fx_usdtwd section (BOT USD/TWD mid + deterministic signal)
- cross_module (kept)

This renderer does NOT recompute market/fred/margin/roll25/fx stats; it only formats fields already in unified JSON.
If a field is missing => prints NA.

2026-01-25 updates:
- Fix roll25 tag semantics: separate run-day tag vs used-date status.
- Display OhlcMissing even if signals lacks it, by inferring from ohlc_status when possible.
- Align field names with unified JSON: roll25.core.used_date_status, roll25.core.tag_legacy
- Prefer unified top-level run_day_tag for run-day context.
- Cross_module unit fix: display margin change unit (e.g., 億) deterministically.
- Render chg_last5 as JSON-like numeric list + unit once.

2026-01-25 follow-up:
- Positioning Matrix: SP500 and VIX use market_cache only (single source policy).
- Positioning Matrix prints source_policy and includes data_date for SP500/VIX (audit-friendly).

2026-01-26 updates (A+B):
A) roll25_cache: add a deterministic note clarifying run_day_tag vs UsedDate semantics (report-only).
B) FX: treat "momentum dict exists but all key fields are None" as momentum_unavailable (deterministic dq note).

2026-01-26 follow-up:
- roll25_split_ref is rendered deterministically (even if cross_module did not provide it),
  by referencing roll25 heat-split flags when present; otherwise NA.

2026-01-26 FX audit upgrade (renderer-only; no guessing):
- Add fx.momentum_reason (deterministic) to disambiguate why momentum is NA:
  * If momentum dict missing / all key fields None -> INSUFFICIENT_HISTORY_OR_MISSING
  * If some fields exist but both ret1_pct and chg_5d_pct are NA -> PARTIAL_HISTORY
  * If at least one of ret1_pct / chg_5d_pct is numeric -> AVAILABLE
- Optionally print history_points_used if unified JSON provides:
  modules.fx_usdtwd.derived.history_points_used (int) OR derived.mid_points (int)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return f"{x:.{nd}f}"
    return str(x)


def _fmt_int(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _detect_root_report_residue(in_path: str, out_path: str) -> Dict[str, Any]:
    """
    Detect whether repo-root has a report.md that is NOT the intended output.
    Heuristic:
      - If out_path basename is report.md and out_path is not exactly ./report.md,
        and ./report.md exists -> residue likely.
      - If out_path is ./report.md, then no residue warning (it's intended).
    """
    info: Dict[str, Any] = {
        "root_report_exists": False,
        "root_report_is_output": False,
        "warn_root_report_residue": False,
        "root_report_path": os.path.abspath("report.md"),
        "output_abs": os.path.abspath(out_path),
        "input_abs": os.path.abspath(in_path),
    }

    root_exists = os.path.isfile("report.md")
    info["root_report_exists"] = root_exists

    out_abs = info["output_abs"]
    root_abs = info["root_report_path"]
    info["root_report_is_output"] = (out_abs == root_abs)

    if root_exists and not info["root_report_is_output"]:
        info["warn_root_report_residue"] = True

    return info


def _infer_ohlc_missing(sigs: Any, r_latest: Any) -> Any:
    """
    Display-only helper:
    - If signals has OhlcMissing, use it.
    - Else try infer from r_latest.ohlc_status ("OK" vs "MISSING").
    - Else return None.
    """
    if isinstance(sigs, dict) and "OhlcMissing" in sigs:
        return sigs.get("OhlcMissing")
    if isinstance(r_latest, dict):
        st = r_latest.get("ohlc_status")
        if isinstance(st, str):
            if st.upper() == "MISSING":
                return True
            if st.upper() == "OK":
                return False
    return None


# ---- unit helpers (cross_module) ----

def _get_twmargin_chg_unit_label(uni: Any) -> str:
    """
    Read unit label for TWSE chg_yi from unified JSON:
      modules.taiwan_margin_financing.latest.series.TWSE.chg_yi_unit.label
    Returns "NA" if missing.
    """
    label = _safe_get(
        uni,
        "modules",
        "taiwan_margin_financing",
        "latest",
        "series",
        "TWSE",
        "chg_yi_unit",
        "label",
    )
    if isinstance(label, str) and label.strip():
        return label.strip()
    return "NA"


def _fmt_with_unit(x: Any, unit: str, nd: int = 3) -> str:
    if x is None:
        return "NA"
    try:
        v = float(x)
    except Exception:
        return "NA"
    if not unit or unit == "NA":
        return "NA"
    return f"{v:.{nd}f} {unit}"


def _fmt_num_list_json(xs: Any, nd: int = 1) -> Any:
    if not isinstance(xs, list):
        return None
    out: List[float] = []
    for it in xs:
        try:
            v = float(it)
        except Exception:
            return None
        out.append(round(v, nd))
    return json.dumps(out, ensure_ascii=False)


# ---- positioning matrix helpers (report-only) ----

def _find_row(rows: Any, series_name: str) -> Optional[Dict[str, Any]]:
    if not isinstance(rows, list):
        return None
    for it in rows:
        if isinstance(it, dict) and str(it.get("series", "")).upper() == series_name.upper():
            return it
    return None


def _truthy_signal(x: Any, allowed: List[str]) -> bool:
    if not isinstance(x, str):
        return False
    return x.upper() in [a.upper() for a in allowed]


# ---- FX helpers (dq; deterministic; no guessing) ----

_FX_KEYS = [
    "ret1_pct", "chg_5d_pct",
    "ret1_from", "ret1_to",
    "chg_5d_from", "chg_5d_to",
]


def _fx_momentum_unavailable(mom: Any) -> bool:
    """
    Deterministic DQ:
    - momentum missing/not dict => unavailable
    - OR momentum exists but all key fields are None/missing => unavailable
    - If any key field is present and not None => available
    """
    if not isinstance(mom, dict):
        return True
    saw_any_key = False
    for k in _FX_KEYS:
        if k in mom:
            saw_any_key = True
            if mom.get(k) is not None:
                return False
    return True  # keys absent or all None


def _is_number(x: Any) -> bool:
    if isinstance(x, bool) or x is None:
        return False
    if isinstance(x, (int, float)):
        return True
    try:
        float(x)
        return True
    except Exception:
        return False


def _fx_momentum_reason(mom: Any) -> str:
    """
    Renderer-only, deterministic, no guessing.

    Returns one of:
      - INSUFFICIENT_HISTORY_OR_MISSING
      - PARTIAL_HISTORY
      - AVAILABLE
    """
    # Missing / not dict => unavailable
    if not isinstance(mom, dict):
        return "INSUFFICIENT_HISTORY_OR_MISSING"

    # If all known keys missing or None => unavailable
    if _fx_momentum_unavailable(mom):
        return "INSUFFICIENT_HISTORY_OR_MISSING"

    # Some key exists and not None, but check whether computed pct fields are available
    ret1_ok = _is_number(mom.get("ret1_pct"))
    chg5_ok = _is_number(mom.get("chg_5d_pct"))

    if ret1_ok or chg5_ok:
        return "AVAILABLE"

    # Key fields exist (e.g., from/to) but pct fields not present/NA => partial history
    return "PARTIAL_HISTORY"


def _fx_history_points_hint(fx_der: Any) -> Optional[int]:
    """
    Optional renderer-side hint (no guessing):
    Return int only if upstream provides it.
      derived.history_points_used OR derived.mid_points
    """
    if not isinstance(fx_der, dict):
        return None
    v = fx_der.get("history_points_used")
    if isinstance(v, int):
        return v
    v2 = fx_der.get("mid_points")
    if isinstance(v2, int):
        return v2
    return None


# ---- roll25 split-ref helpers (deterministic; renderer-side) ----

def _pick_roll25_heat_flags(roll25: Any) -> Dict[str, Any]:
    """
    Try several likely paths (do not guess; only return if found).
    Returns: {"heated_market": <bool|None>, "dq_issue": <bool|None>}
    """
    candidates = [
        ("roll25_heat_split", "roll25_heated_market", "roll25_data_quality_issue"),
        ("heat_split", "heated_market", "dq_issue"),
        ("heat_split", "roll25_heated_market", "roll25_data_quality_issue"),
    ]

    # direct under modules.roll25_cache.*
    for base, k1, k2 in candidates:
        heated = _safe_get(roll25, base, k1)
        dq = _safe_get(roll25, base, k2)
        if heated is not None or dq is not None:
            return {"heated_market": heated, "dq_issue": dq}

    # under latest_report.*
    lr = _safe_get(roll25, "latest_report")
    if isinstance(lr, dict):
        for base, k1, k2 in candidates:
            heated = _safe_get(lr, base, k1)
            dq = _safe_get(lr, base, k2)
            if heated is not None or dq is not None:
                return {"heated_market": heated, "dq_issue": dq}

    # under derived/cross_module (if builder stored there)
    der = _safe_get(roll25, "derived")
    if isinstance(der, dict):
        heated = der.get("roll25_heated_market")
        dq = der.get("roll25_data_quality_issue")
        if heated is not None or dq is not None:
            return {"heated_market": heated, "dq_issue": dq}

    return {"heated_market": None, "dq_issue": None}


def _fmt_bool_or_na(x: Any) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    return "NA"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="in_path",
        default="unified_dashboard/latest.json",
        help="Input unified dashboard JSON path",
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        default="unified_dashboard/report.md",
        help="Output markdown report path",
    )
    args = ap.parse_args()

    uni = _load_json(args.in_path)
    rendered_at_utc = _now_utc_z()

    modules = uni.get("modules", {}) if isinstance(uni, dict) else {}
    market = modules.get("market_cache", {})
    fred = modules.get("fred_cache", {})
    roll25 = modules.get("roll25_cache", {})
    twm = modules.get("taiwan_margin_financing", {})
    fx = modules.get("fx_usdtwd", {})

    lines: List[str] = []
    lines.append("# Unified Risk Dashboard Report\n")

    # Module status
    lines.append("## Module Status")
    lines.append(f"- market_cache: {_safe_get(market,'status') or 'NA'}")
    lines.append(f"- fred_cache: {_safe_get(fred,'status') or 'NA'}")
    lines.append(f"- roll25_cache: {_safe_get(roll25,'status') or 'NA'}")
    lines.append(f"- taiwan_margin_financing: {_safe_get(twm,'status') or 'NA'}")
    lines.append(f"- fx_usdtwd: {_safe_get(fx,'status') or 'NA'}")
    lines.append(f"- unified_generated_at_utc: {uni.get('generated_at_utc','NA')}\n")

    # ----------------------------
    # (2) Positioning Matrix
    # ----------------------------
    m_dash = _safe_get(market, "dashboard_latest") or {}
    m_rows = _safe_get(m_dash, "rows") or []

    f_dash = _safe_get(fred, "dashboard_latest") or {}
    f_rows = _safe_get(f_dash, "rows") or []

    tw_cross = _safe_get(twm, "cross_module") or {}
    roll25_der = _safe_get(roll25, "derived") or {}
    fx_der = _safe_get(fx, "derived") or {}

    # Single-source policy (explicit, to avoid confusion)
    source_policy = "SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)"

    spx_m = _find_row(m_rows, "SP500")
    vix_m = _find_row(m_rows, "VIX")

    # trend_on: based on market_cache SP500 only
    spx_sig = spx_m.get("signal_level") if isinstance(spx_m, dict) else None
    spx_tag = spx_m.get("tag") if isinstance(spx_m, dict) else None
    spx_date = spx_m.get("data_date") if isinstance(spx_m, dict) else None

    trend_on = bool(
        isinstance(spx_sig, str)
        and spx_sig.upper() == "INFO"
        and isinstance(spx_tag, str)
        and ("LONG_EXTREME" in spx_tag.upper())
    )

    # fragility_high parts (deterministic, signal-only)
    credit = _find_row(f_rows, "BAMLH0A0HYM2")
    dgs10 = _find_row(f_rows, "DGS10")

    credit_sig = credit.get("signal_level") if isinstance(credit, dict) else None
    dgs10_sig = dgs10.get("signal_level") if isinstance(dgs10, dict) else None

    credit_fragile = _truthy_signal(credit_sig, ["ALERT"])  # strict
    rate_stress = _truthy_signal(dgs10_sig, ["WATCH", "ALERT"])

    tw_margin_sig = tw_cross.get("margin_signal") if isinstance(tw_cross, dict) else None
    tw_margin = _truthy_signal(tw_margin_sig, ["WATCH", "ALERT"])

    cross_cons = tw_cross.get("consistency") if isinstance(tw_cross, dict) else None
    cross_divergence = bool(isinstance(cross_cons, str) and cross_cons.upper() == "DIVERGENCE")

    fragility_high = bool((credit_fragile or rate_stress) and (tw_margin or cross_divergence))

    # vol_runaway: market_cache VIX only (single source)
    vix_sig = vix_m.get("signal_level") if isinstance(vix_m, dict) else None
    vix_dir = vix_m.get("dir") if isinstance(vix_m, dict) else None
    vix_ret1 = vix_m.get("ret1_pct60") if isinstance(vix_m, dict) else None
    vix_date = vix_m.get("data_date") if isinstance(vix_m, dict) else None

    vix_ret1_val: Optional[float] = None
    try:
        if vix_ret1 is not None:
            vix_ret1_val = float(vix_ret1)
    except Exception:
        vix_ret1_val = None

    vol_runaway = bool(
        isinstance(vix_sig, str)
        and (
            vix_sig.upper() == "ALERT"
            or (vix_sig.upper() == "WATCH" and (vix_ret1_val is not None and vix_ret1_val >= 5.0))
        )
    )

    matrix_cell = f"Trend={'ON' if trend_on else 'OFF'} / Fragility={'HIGH' if fragility_high else 'LOW'}"

    if vol_runaway:
        mode = "PAUSE_RISK_ON"
    else:
        if trend_on and fragility_high:
            mode = "DEFENSIVE_DCA"
        elif trend_on and not fragility_high:
            mode = "NORMAL_DCA"
        elif (not trend_on) and fragility_high:
            mode = "RISK_OFF"
        else:
            mode = "HOLD_CASH"

    roll25_conf = roll25_der.get("confidence") if isinstance(roll25_der, dict) else None
    fx_conf = fx_der.get("fx_confidence") if isinstance(fx_der, dict) else None

    lines.append("## (2) Positioning Matrix")
    lines.append("### Current Strategy Mode (deterministic; report-only)")
    lines.append("- strategy_version: strategy_mode_v1")
    lines.append(f"- source_policy: {source_policy}")
    lines.append(f"- trend_on: {_fmt(trend_on,0)}")
    lines.append(f"- fragility_high: {_fmt(fragility_high,0)}")
    lines.append(f"- vol_runaway: {_fmt(vol_runaway,0)}")
    lines.append(f"- matrix_cell: {matrix_cell}")
    lines.append(f"- mode: {mode}\n")

    lines.append("**reasons**")
    if isinstance(spx_m, dict):
        lines.append(
            f"- trend_basis: market_cache.SP500.signal={spx_sig if spx_sig is not None else 'NA'}, "
            f"tag={spx_tag if spx_tag is not None else 'NA'}, data_date={spx_date if spx_date is not None else 'NA'}"
        )
    else:
        lines.append("- trend_basis: market_cache.SP500: NA (missing row)")

    lines.append(
        "- fragility_parts: "
        f"credit_fragile(BAMLH0A0HYM2={credit_sig if credit_sig is not None else 'NA'})="
        f"{str(credit_fragile).lower()}, "
        f"rate_stress(DGS10={dgs10_sig if dgs10_sig is not None else 'NA'})="
        f"{str(rate_stress).lower()}, "
        f"tw_margin({tw_margin_sig if tw_margin_sig is not None else 'NA'})="
        f"{str(tw_margin).lower()}, "
        f"cross_divergence({cross_cons if cross_cons is not None else 'NA'})="
        f"{str(cross_divergence).lower()}"
    )

    if isinstance(vix_m, dict):
        lines.append(
            f"- vol_gate: market_cache.VIX only (signal={vix_sig if vix_sig is not None else 'NA'}, "
            f"dir={vix_dir if vix_dir is not None else 'NA'}, "
            f"ret1%60={_fmt(vix_ret1_val,6) if vix_ret1_val is not None else 'NA'}, "
            f"data_date={vix_date if vix_date is not None else 'NA'})"
        )
    else:
        lines.append("- vol_gate: market_cache.VIX only: NA (missing row)")

    lines.append("\n**dq_gates (no guessing; conservative defaults)**")
    lines.append(f"- roll25_derived_confidence={roll25_conf if roll25_conf is not None else 'NA'} (derived metrics not used for upgrade triggers)")
    lines.append(f"- fx_confidence={fx_conf if fx_conf is not None else 'NA'} (fx not used as primary trigger)\n")

    # ----------------------------
    # market_cache detailed
    # ----------------------------
    m_meta = _safe_get(m_dash, "meta") or {}
    lines.append("## market_cache (detailed)")
    lines.append(f"- as_of_ts: {m_meta.get('stats_as_of_ts','NA')}")
    lines.append(f"- run_ts_utc: {m_meta.get('run_ts_utc','NA')}")
    lines.append(f"- ruleset_id: {m_meta.get('ruleset_id','NA')}")
    lines.append(f"- script_fingerprint: {m_meta.get('script_fingerprint','NA')}")
    lines.append(f"- script_version: {m_meta.get('script_version','NA')}")
    lines.append(f"- series_count: {m_meta.get('series_count','NA')}\n")

    if isinstance(m_rows, list) and m_rows:
        hdr = [
            "series", "signal", "dir", "market_class", "value", "data_date", "age_h",
            "z60", "p60", "p252", "zΔ60", "pΔ60", "ret1%60", "reason", "tag", "prev",
            "delta", "streak_hist", "streak_wa", "source"
        ]
        rws: List[List[str]] = []
        for it in m_rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag", "NA")
            mclass = "NONE"
            if isinstance(tag, str):
                if "LONG_EXTREME" in tag:
                    mclass = "LONG"
                if "EXTREME_Z" in tag:
                    mclass = "LEVEL" if mclass == "NONE" else f"{mclass}+LEVEL"
                if "JUMP" in tag:
                    mclass = "JUMP" if mclass == "NONE" else f"{mclass}+JUMP"
            rws.append([
                str(it.get("series", "NA")),
                str(it.get("signal_level", "NA")),
                str(it.get("dir", "NA")),
                mclass,
                _fmt(it.get("value"), 6),
                str(it.get("data_date", "NA")),
                _fmt(it.get("age_hours"), 6),
                _fmt(it.get("z60"), 6),
                _fmt(it.get("p60"), 6),
                _fmt(it.get("p252"), 6),
                _fmt(it.get("z_delta60"), 6),
                _fmt(it.get("p_delta60"), 6),
                _fmt(it.get("