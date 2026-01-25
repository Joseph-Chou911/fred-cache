#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render unified_dashboard/latest.json into report.md

Adds:
- roll25_derived (realized vol / max drawdown)
- fx_usdtwd section (BOT USD/TWD mid + deterministic signal)
- cross_module (kept)

This renderer does NOT recompute; it only formats fields already in unified JSON.
If a field is missing => prints NA.

Small audit-focused enhancements:
- Footer prints input_path/output_path for self-audit.
- Detects repo-root report.md residue and warns in footer (does NOT delete).

2026-01-25 update:
- Fix roll25 tag semantics: separate run-day tag vs used-date status.
  Prints:
    - run_day_tag (e.g., NON_TRADING_DAY when workflow runs on weekend)
    - used_date_status (e.g., OK_TODAY / OK_LATEST / DATA_NOT_UPDATED / ...)
    - tag (legacy) kept for backward compatibility
- Display OhlcMissing even if signals lacks it, by inferring from ohlc_status when possible.

2026-01-25 (follow-up fix):
- Align field names with unified JSON:
    roll25.core.used_date_status, roll25.core.tag_legacy
- Prefer unified top-level run_day_tag for run-day context.

2026-01-25 (cross_module unit fix):
- Display margin change unit (e.g., 億) in cross_module section.
- Format sum_last5 / latest_chg with unit (no guessing; missing => NA).

2026-01-25 (chg_last5 converge):
- Render chg_last5 as a JSON-like numeric list + unit once:
    chg_last5: [43.4, 39.9, -34.8, 18.1, 60.2] 億
  (If unit missing => NA; do not guess)

2026-01-25 (Positioning Matrix):
- Add "(2) Positioning Matrix" section in report.md only.
- Uses existing signals in unified JSON; no recomputation / no JSON mutation.
- Missing fields => NA + dq_gates (conservative).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List


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

    # If we're NOT writing to root/report.md but root/report.md exists -> likely residue
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
    """
    Format a scalar numeric with unit (audit-friendly).
    - If x is None or not numeric => "NA"
    - If unit missing => "NA" (do not guess)
    """
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
    """
    Return a JSON-like numeric list string: "[43.4, 39.9, -34.8]"
    - If xs is not list => None
    - Non-numeric items => None (audit: do not silently coerce)
    """
    if not isinstance(xs, list):
        return None
    out: List[float] = []
    for it in xs:
        try:
            v = float(it)
        except Exception:
            return None
        out.append(round(v, nd))
    # json.dumps => no Python repr, stable brackets/commas, no single quotes
    return json.dumps(out, ensure_ascii=False)


# ---- positioning / strategy helpers (report-only; deterministic; no recompute of inputs) ----

def _index_rows_by_series(rows: Any) -> Dict[str, Dict[str, Any]]:
    """
    Build lookup: series -> row(dict)
    If duplicates exist, last one wins (stable enough for dashboard_latest rows).
    """
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for it in rows:
        if not isinstance(it, dict):
            continue
        s = it.get("series")
        if isinstance(s, str) and s.strip():
            out[s.strip()] = it
    return out


def _sig(it: Any) -> str:
    if not isinstance(it, dict):
        return "NA"
    v = it.get("signal_level")
    return v if isinstance(v, str) and v else "NA"


def _tag(it: Any) -> str:
    if not isinstance(it, dict):
        return "NA"
    v = it.get("tag")
    return v if isinstance(v, str) and v else "NA"


def _bool(x: Any) -> Any:
    return x if isinstance(x, bool) else None


def _compute_strategy_mode(
    uni: Any,
    m_rows: Any,
    f_rows: Any,
    cross: Any,
    roll25_derived: Any,
    fx_derived: Any,
) -> Dict[str, Any]:
    """
    Deterministic, report-only strategy mode:
      - Trend axis: SP500 INFO + LONG_EXTREME => Trend=ON
      - Fragility axis: credit ALERT or rate WATCH or margin WATCH/ALERT or DIVERGENCE
      - Hedge overlay: only when vol_runaway is strongly supported

    Missing fields => do NOT guess; add dq_gates instead.
    """
    out: Dict[str, Any] = {
        "trend_on": None,
        "fragility_high": None,
        "vol_runaway": None,
        "mode": "NA",
        "matrix_cell": "NA",
        "reasons": [],
        "dq_gates": [],
        "version": "strategy_mode_v1",
    }

    m = _index_rows_by_series(m_rows)
    f = _index_rows_by_series(f_rows)

    # ---- Trend axis (SP500) ----
    spx = m.get("SP500") or f.get("SP500")
    spx_sig = _sig(spx)
    spx_tag = _tag(spx)

    trend_on = None
    if spx_sig != "NA" or spx_tag != "NA":
        # Require explicit LONG_EXTREME tag to avoid over-triggering trend-on.
        trend_on = (spx_sig == "INFO") and ("LONG_EXTREME" in spx_tag)
        out["reasons"].append(f"trend_basis: SP500.signal={spx_sig}, tag={spx_tag}")
    else:
        out["dq_gates"].append("trend_basis_missing: cannot read SP500 signal/tag")

    # ---- Fragility axis ----
    hy = f.get("BAMLH0A0HYM2")
    dgs10 = f.get("DGS10")

    hy_alert = (_sig(hy) == "ALERT")
    rate_watch = (_sig(dgs10) == "WATCH")

    margin_sig = "NA"
    divergence = False
    if isinstance(cross, dict):
        margin_sig = cross.get("margin_signal", "NA")
        divergence = (cross.get("consistency") == "DIVERGENCE")

    margin_hot = (margin_sig in ("WATCH", "ALERT"))

    frag_parts = [
        ("credit_fragile(BAMLH0A0HYM2=ALERT)", hy_alert),
        ("rate_stress(DGS10=WATCH)", rate_watch),
        (f"tw_margin({margin_sig})", margin_hot),
        ("cross_divergence(DIVERGENCE)", divergence),
    ]

    frag_known = [b for _, b in frag_parts if isinstance(b, bool)]
    if frag_known:
        fragility_high = any(frag_known)
        out["reasons"].append(
            "fragility_parts: " + ", ".join([f"{name}={str(val).lower()}" for name, val in frag_parts])
        )
    else:
        fragility_high = None
        out["dq_gates"].append("fragility_basis_missing: cannot read fragility signals")

    # ---- Vol runaway gate (strict) ----
    vix = m.get("VIX")
    vixcls = f.get("VIXCLS")

    vix_sig = _sig(vix)
    vixcls_sig = _sig(vixcls)

    vix_up = None
    vixcls_up = None
    if isinstance(vix, dict) and isinstance(vix.get("ret1_pct60"), (int, float)):
        vix_up = (float(vix.get("ret1_pct60")) > 0)
    if isinstance(vixcls, dict) and isinstance(vixcls.get("ret1_pct"), (int, float)):
        vixcls_up = (float(vixcls.get("ret1_pct")) > 0)

    any_vol_alert = (vix_sig == "ALERT") or (vixcls_sig == "ALERT")
    both_watch = (vix_sig in ("WATCH", "ALERT")) and (vixcls_sig in ("WATCH", "ALERT"))

    if any_vol_alert:
        vol_runaway = True
        out["reasons"].append(f"vol_gate: VIX={vix_sig}, VIXCLS={vixcls_sig} => vol_runaway=true (ALERT)")
    elif both_watch and (vix_up is True) and (vixcls_up is True):
        vol_runaway = True
        out["reasons"].append(
            f"vol_gate: both WATCH and up (VIX_up={str(vix_up).lower()}, VIXCLS_up={str(vixcls_up).lower()})"
        )
    elif both_watch:
        vol_runaway = False
        out["reasons"].append(
            f"vol_gate: mixed/unknown WATCH direction (VIX_up={str(vix_up).lower()}, VIXCLS_up={str(vixcls_up).lower()})"
        )
    else:
        vol_runaway = False
        out["reasons"].append(f"vol_gate: VIX={vix_sig}, VIXCLS={vixcls_sig} => not runaway")

    # ---- DQ gates (do not upgrade based on downgraded derived modules) ----
    if isinstance(roll25_derived, dict) and roll25_derived.get("confidence") == "DOWNGRADED":
        out["dq_gates"].append("roll25_derived_confidence=DOWNGRADED (derived metrics not used for upgrade triggers)")
    if isinstance(fx_derived, dict) and fx_derived.get("fx_confidence") == "DOWNGRADED":
        out["dq_gates"].append("fx_confidence=DOWNGRADED (fx not used as primary trigger)")

    out["trend_on"] = trend_on
    out["fragility_high"] = fragility_high
    out["vol_runaway"] = vol_runaway

    if trend_on is None or fragility_high is None:
        out["matrix_cell"] = "NA"
        out["mode"] = "NA"
        out["dq_gates"].append("mode_unresolved: missing trend/fragility axis")
        return out

    # Base cell -> mode
    if trend_on and (not fragility_high):
        cell = "Trend=ON / Fragility=LOW"
        mode = "NORMAL"
    elif trend_on and fragility_high:
        cell = "Trend=ON / Fragility=HIGH"
        mode = "DEFENSIVE_DCA"
    elif (not trend_on) and fragility_high:
        cell = "Trend=OFF / Fragility=HIGH"
        mode = "RISK_OFF"
    else:
        cell = "Trend=OFF / Fragility=LOW"
        mode = "NORMAL"

    # Hedge overlay only if vol runaway AND fragility high
    if vol_runaway and fragility_high:
        mode = "HEDGE_READY"
        out["reasons"].append("hedge_overlay: vol_runaway=true AND fragility_high=true")

    out["matrix_cell"] = cell
    out["mode"] = mode
    return out


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

    # Prepare commonly reused objects (for strategy + later rendering)
    m_dash = _safe_get(market, "dashboard_latest") or {}
    m_meta = _safe_get(m_dash, "meta") or {}
    m_rows = _safe_get(m_dash, "rows") or []

    f_dash = _safe_get(fred, "dashboard_latest") or {}
    f_meta = _safe_get(f_dash, "meta") or {}
    f_rows = _safe_get(f_dash, "rows") or []

    cross = _safe_get(twm, "cross_module") or {}
    r_der = _safe_get(roll25, "derived") or {}
    fx_der = _safe_get(fx, "derived") or {}

    # (2) Positioning Matrix / Strategy Mode (report-only; deterministic)
    sm = _compute_strategy_mode(uni, m_rows, f_rows, cross, r_der, fx_der)
    lines.append("## (2) Positioning Matrix")
    lines.append("### Current Strategy Mode (deterministic; report-only)")
    lines.append(f"- strategy_version: {sm.get('version','NA')}")
    lines.append(f"- trend_on: {_fmt(_bool(sm.get('trend_on')),0)}")
    lines.append(f"- fragility_high: {_fmt(_bool(sm.get('fragility_high')),0)}")
    lines.append(f"- vol_runaway: {_fmt(_bool(sm.get('vol_runaway')),0)}")
    lines.append(f"- matrix_cell: {sm.get('matrix_cell','NA')}")
    lines.append(f"- mode: {sm.get('mode','NA')}")
    lines.append("")
    if isinstance(sm.get("reasons"), list) and sm["reasons"]:
        lines.append("**reasons**")
        for r in sm["reasons"]:
            lines.append(f"- {r}")
        lines.append("")
    if isinstance(sm.get("dq_gates"), list) and sm["dq_gates"]:
        lines.append("**dq_gates (no guessing; conservative defaults)**")
        for g in sm["dq_gates"]:
            lines.append(f"- {g}")
        lines.append("")

    # market_cache detailed
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
                _fmt(it.get("ret1_pct60"), 6),
                str(it.get("reason", "NA")),
                str(tag),
                str(it.get("prev_signal", "NA")),
                str(it.get("delta_signal", "NA")),
                _fmt_int(it.get("streak_hist")),
                _fmt_int(it.get("streak_wa")),
                str(it.get("source_url", "NA")),
            ])
        lines.append(_md_table(hdr, rws))
        lines.append("")

    # fred_cache
    lines.append("## fred_cache (ALERT+WATCH+INFO)")
    lines.append(f"- as_of_ts: {f_meta.get('stats_as_of_ts','NA')}")
    lines.append(f"- run_ts_utc: {f_meta.get('run_ts_utc','NA')}")
    lines.append(f"- ruleset_id: {f_meta.get('ruleset_id','NA')}")
    lines.append(f"- script_fingerprint: {f_meta.get('script_fingerprint','NA')}")
    lines.append(f"- script_version: {f_meta.get('script_version','NA')}")
    summ = f_meta.get("summary", {})
    if isinstance(summ, dict):
        lines.append(f"- ALERT: {summ.get('ALERT','NA')}")
        lines.append(f"- WATCH: {summ.get('WATCH','NA')}")
        lines.append(f"- INFO: {summ.get('INFO','NA')}")
        lines.append(f"- NONE: {summ.get('NONE','NA')}")
        lines.append(f"- CHANGED: {summ.get('CHANGED','NA')}\n")
    else:
        lines.append("")

    if isinstance(f_rows, list) and f_rows:
        hdr = [
            "series", "signal", "fred_dir", "fred_class", "value", "data_date", "age_h",
            "z60", "p60", "p252", "zΔ60", "pΔ60", "ret1%", "reason", "tag", "prev", "delta", "source"
        ]
        rws_f: List[List[str]] = []
        for it in f_rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag", "NA")
            fclass = "NONE"
            if isinstance(tag, str):
                if "LONG_EXTREME" in tag:
                    fclass = "LONG"
                elif "EXTREME_Z" in tag:
                    fclass = "LEVEL"
                elif "JUMP" in tag:
                    fclass = "JUMP"
            rws_f.append([
                str(it.get("series", "NA")),
                str(it.get("signal_level", "NA")),
                str(it.get("fred_dir", "NA")),
                fclass,
                _fmt(it.get("value"), 6),
                str(it.get("data_date", "NA")),
                _fmt(it.get("age_hours"), 6),
                _fmt(it.get("z60"), 6),
                _fmt(it.get("p60"), 6),
                _fmt(it.get("p252"), 6),
                _fmt(it.get("z_delta_60"), 6),
                _fmt(it.get("p_delta_60"), 6),
                _fmt(it.get("ret1_pct"), 6),
                str(it.get("reason", "NA")),
                str(tag),
                str(it.get("prev_signal", "NA")),
                str(it.get("delta_signal", "NA")),
                str(it.get("source_url", "NA")),
            ])
        lines.append(_md_table(hdr, rws_f))
        lines.append("")

    # roll25_cache (core fields from latest report)
    r_latest = _safe_get(roll25, "latest_report") or {}
    r_core = _safe_get(roll25, "core") or {}

    # Backward-compat: if unified builder didn't provide "core", reconstruct from latest_report
    if not r_core and isinstance(r_latest, dict):
        nums = r_latest.get("numbers", {}) if isinstance(r_latest.get("numbers"), dict) else {}
        sigs = r_latest.get("signal", {}) if isinstance(r_latest.get("signal"), dict) else {}
        r_core = {
            "UsedDate": nums.get("UsedDate") or r_latest.get("used_date"),
            "tag_legacy": r_latest.get("tag"),
            "used_date_status": r_latest.get("used_date_status") or r_latest.get("tag_used_date_status"),
            "risk_level": r_latest.get("risk_level"),
            "turnover_twd": nums.get("TradeValue"),
            "turnover_unit": "TWD",
            "volume_multiplier": nums.get("VolumeMultiplier"),
            "vol_multiplier": nums.get("VolMultiplier"),
            "amplitude_pct": nums.get("AmplitudePct"),
            "pct_change": nums.get("PctChange"),
            "close": nums.get("Close"),
            "signals": sigs,
            "LookbackNTarget": 20,
            "LookbackNActual": r_latest.get("lookback_n_actual"),
            "ohlc_status": r_latest.get("ohlc_status"),
        }

    # New: separate tag semantics (prefer structured fields; fallback to legacy)
    run_day_tag = (
        uni.get("run_day_tag")
        or _safe_get(r_latest, "run_day_tag")
        or _safe_get(r_latest, "tag")
        or _safe_get(r_core, "run_day_tag")
        or _safe_get(r_core, "tag_legacy")
        or _safe_get(r_core, "tag")
    )

    used_date_status = (
        _safe_get(r_core, "used_date_status")
        or _safe_get(r_latest, "used_date_status")
        or _safe_get(r_latest, "tag_used_date_status")
    )

    legacy_tag = (
        _safe_get(r_core, "tag_legacy")
        or _safe_get(r_core, "tag")
        or "NA"
    )

    lines.append("## roll25_cache (TW turnover)")
    lines.append(f"- status: {_safe_get(roll25,'status') or 'NA'}")
    lines.append(f"- UsedDate: {_fmt(r_core.get('UsedDate'),0)}")
    lines.append(f"- run_day_tag: {run_day_tag if run_day_tag is not None else 'NA'}")
    lines.append(f"- used_date_status: {used_date_status if used_date_status is not None else 'NA'}")
    lines.append(f"- tag (legacy): {legacy_tag}")
    lines.append(f"- risk_level: {r_core.get('risk_level','NA')}")
    lines.append(f"- turnover_twd: {_fmt(r_core.get('turnover_twd'),0)}")
    lines.append(f"- turnover_unit: {r_core.get('turnover_unit','NA')}")
    lines.append(f"- volume_multiplier: {_fmt(r_core.get('volume_multiplier'),3)}")
    lines.append(f"- vol_multiplier: {_fmt(r_core.get('vol_multiplier'),3)}")
    lines.append(f"- amplitude_pct: {_fmt(r_core.get('amplitude_pct'),3)}")
    lines.append(f"- pct_change: {_fmt(r_core.get('pct_change'),3)}")
    lines.append(f"- close: {_fmt(r_core.get('close'),2)}")
    lines.append(f"- LookbackNTarget: {_fmt_int(r_core.get('LookbackNTarget'))}")
    lines.append(f"- LookbackNActual: {_fmt_int(r_core.get('LookbackNActual'))}")

    sigs = r_core.get("signals", {})
    ohlc_missing = _infer_ohlc_missing(sigs, r_latest)

    if isinstance(sigs, dict):
        for k in ["DownDay", "VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak"]:
            lines.append(f"- signals.{k}: {_fmt(sigs.get(k),0)}")
        lines.append(f"- signals.OhlcMissing: {_fmt(ohlc_missing,0)}")
    else:
        lines.append(f"- signals.OhlcMissing: {_fmt(ohlc_missing,0)}")
    lines.append("")

    # roll25 derived
    lines.append("### roll25_derived (realized vol / drawdown)")
    lines.append(f"- status: {r_der.get('status','NA')}")
    params = r_der.get("params", {}) if isinstance(r_der.get("params"), dict) else {}
    lines.append(f"- vol_n: {_fmt_int(params.get('vol_n'))}")
    lines.append(f"- realized_vol_N_annualized_pct: {_fmt(r_der.get('realized_vol_N_annualized_pct'),6)}")
    lines.append(f"- realized_vol_points_used: {_fmt_int(r_der.get('realized_vol_points_used'))}")
    lines.append(f"- dd_n: {_fmt_int(params.get('dd_n'))}")
    lines.append(f"- max_drawdown_N_pct: {_fmt(r_der.get('max_drawdown_N_pct'),6)}")
    lines.append(f"- max_drawdown_points_used: {_fmt_int(r_der.get('max_drawdown_points_used'))}")
    lines.append(f"- confidence: {r_der.get('confidence','NA')}")
    lines.append("")

    # FX
    lines.append("## FX (USD/TWD)")
    lines.append(f"- status: {_safe_get(fx,'status') or 'NA'}")
    lines.append(f"- data_date: {fx_der.get('data_date','NA')}")
    lines.append(f"- source_url: {fx_der.get('source_url','NA')}")
    usd = fx_der.get("usd_twd", {}) if isinstance(fx_der.get("usd_twd"), dict) else {}
    lines.append(f"- spot_buy: {_fmt(usd.get('spot_buy'),6)}")
    lines.append(f"- spot_sell: {_fmt(usd.get('spot_sell'),6)}")
    lines.append(f"- mid: {_fmt(usd.get('mid'),6)}")
    mom = fx_der.get("momentum", {}) if isinstance(fx_der.get("momentum"), dict) else {}
    lines.append(f"- ret1_pct: {_fmt(mom.get('ret1_pct'),6)} (from {mom.get('ret1_from','NA')} to {mom.get('ret1_to','NA')})")
    lines.append(f"- chg_5d_pct: {_fmt(mom.get('chg_5d_pct'),6)} (from {mom.get('chg_5d_from','NA')} to {mom.get('chg_5d_to','NA')})")
    lines.append(f"- dir: {fx_der.get('dir','NA')}")
    lines.append(f"- fx_signal: {fx_der.get('fx_signal','NA')}")
    lines.append(f"- fx_reason: {fx_der.get('fx_reason','NA')}")
    lines.append(f"- fx_confidence: {fx_der.get('fx_confidence','NA')}")
    lines.append("")

    # taiwan margin financing
    tw_latest = _safe_get(twm, "latest") or {}
    lines.append("## taiwan_margin_financing (TWSE/TPEX)")
    lines.append(f"- status: {_safe_get(twm,'status') or 'NA'}")
    lines.append(f"- schema_version: {tw_latest.get('schema_version','NA')}")
    lines.append(f"- generated_at_utc: {tw_latest.get('generated_at_utc','NA')}")
    lines.append("")

    # cross_module
    if isinstance(cross, dict) and cross:
        chg_unit = _get_twmargin_chg_unit_label(uni)

        lines.append("### cross_module (Margin × Roll25 consistency)")
        lines.append(f"- margin_signal: {cross.get('margin_signal','NA')}")
        lines.append(f"- margin_signal_source: {cross.get('margin_signal_source','NA')}")
        mr = cross.get("margin_rationale", {}) if isinstance(cross.get("margin_rationale"), dict) else {}
        lines.append(f"- margin_rule_version: {mr.get('rule_version','NA')}")

        lines.append(f"- chg_unit: {chg_unit} (from modules.taiwan_margin_financing.latest.series.TWSE.chg_yi_unit.label)")

        chg_last5 = mr.get("chg_last5", None)
        chg_last5_json = _fmt_num_list_json(chg_last5, nd=1)

        # Converged: numeric list + unit once (no unit => NA; do not guess)
        if chg_last5_json is not None and chg_unit != "NA":
            lines.append(f"- chg_last5: {chg_last5_json} {chg_unit}")
        else:
            lines.append("- chg_last5: NA")

        lines.append(f"- sum_last5: {_fmt_with_unit(mr.get('sum_last5'), chg_unit, nd=3)}")
        lines.append(f"- pos_days_last5: {_fmt_int(mr.get('pos_days_last5'))}")
        lines.append(f"- latest_chg: {_fmt_with_unit(mr.get('latest_chg'), chg_unit, nd=3)}")

        lines.append(f"- margin_confidence: {mr.get('confidence','NA')}")
        lines.append(f"- roll25_heated: {_fmt(cross.get('roll25_heated'),0)}")
        lines.append(f"- roll25_confidence: {cross.get('roll25_confidence','NA')}")
        lines.append(f"- consistency: {cross.get('consistency','NA')}")
        da = _safe_get(cross, "rationale", "date_alignment") or {}
        if isinstance(da, dict) and da:
            lines.append(
                f"- date_alignment: twmargin_date={da.get('twmargin_date','NA')}, "
                f"roll25_used_date={da.get('roll25_used_date','NA')}, "
                f"match={str(da.get('used_date_match','NA')).lower()}"
            )
        lines.append("")

    # audit footer
    residue = _detect_root_report_residue(args.in_path, args.out_path)
    lines.append(f"<!-- rendered_at_utc: {rendered_at_utc} -->")
    lines.append(f"<!-- input_path: {args.in_path} | input_abs: {residue['input_abs']} -->")
    lines.append(f"<!-- output_path: {args.out_path} | output_abs: {residue['output_abs']} -->")
    lines.append(
        f"<!-- root_report_exists: {str(residue['root_report_exists']).lower()} | "
        f"root_report_is_output: {str(residue['root_report_is_output']).lower()} -->"
    )
    if residue["warn_root_report_residue"]:
        lines.append("<!-- WARNING: repo root has report.md but output is not root/report.md; likely residue file. -->")
    lines.append("")

    text = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out_path) or ".", exist_ok=True)
    with open(args.out_path, "w", encoding="utf-8") as f:
        f.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())