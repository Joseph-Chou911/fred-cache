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
C) roll25_split_ref: if unified JSON does not provide explicit split fields, derive deterministically from existing
   report fields (no guessing):
   - heated_market := cross_module.roll25_heated (legacy) if present
   - dq_issue := any of:
       * cross_module.roll25_confidence != OK
       * roll25_derived.confidence != OK
       * used_date_status != OK_LATEST
       * LookbackNActual < LookbackNTarget
       * signals.OhlcMissing == true
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


# ---- FX helpers (dq) ----

def _fx_momentum_unavailable(mom: Any) -> bool:
    """
    Deterministic DQ:
    - momentum is missing/not a dict => unavailable
    - OR momentum exists but ALL key fields are None => unavailable
    - OR momentum exists but none of the keys exist => unavailable
    """
    if not isinstance(mom, dict):
        return True
    keys = [
        "ret1_pct", "chg_5d_pct",
        "ret1_from", "ret1_to",
        "chg_5d_from", "chg_5d_to",
    ]
    any_present = False
    any_nonnull = False
    for k in keys:
        if k in mom:
            any_present = True
            if mom.get(k) is not None:
                any_nonnull = True
    return (not any_present) or (not any_nonnull)


# ---- roll25 split ref helpers (cross_module) ----

def _norm_bool(x: Any) -> Optional[bool]:
    return x if isinstance(x, bool) else None


def _roll25_split_values(
    *,
    roll25_core: Dict[str, Any],
    roll25_latest: Dict[str, Any],
    roll25_derived: Dict[str, Any],
    cross_module: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministic extraction / derivation of split booleans.
    Priority:
      1) explicit fields (if builder provides)
      2) deterministic derivation from existing report fields (no guessing)

    Returns:
      {"heated_market": <bool|None>, "dq_issue": <bool|None>, "dq_reasons": [..]}
    """
    dq_reasons: List[str] = []

    # 1) Try explicit (builder-provided) fields (if they exist)
    # e.g., roll25_core.heat_split / roll25_latest.roll25_heat_split / roll25_derived.*
    heated = _norm_bool(_safe_get(roll25_core, "heat_split", "heated_market"))
    dq = _norm_bool(_safe_get(roll25_core, "heat_split", "dq_issue"))

    if heated is None:
        heated = _norm_bool(_safe_get(roll25_latest, "roll25_heat_split", "roll25_heated_market"))
    if dq is None:
        dq = _norm_bool(_safe_get(roll25_latest, "roll25_heat_split", "roll25_data_quality_issue"))

    if heated is None:
        heated = _norm_bool(_safe_get(roll25_derived, "roll25_heated_market"))
    if dq is None:
        dq = _norm_bool(_safe_get(roll25_derived, "roll25_data_quality_issue"))

    # 2) If still missing, derive deterministically
    # heated_market := cross_module.roll25_heated (legacy)
    if heated is None:
        heated = _norm_bool(cross_module.get("roll25_heated"))
        if heated is not None:
            dq_reasons.append("heated_market_from_cross.roll25_heated")

    # dq_issue: any DQ degradation indicator
    if dq is None:
        # roll25_confidence gate
        rc = cross_module.get("roll25_confidence")
        if isinstance(rc, str) and rc.upper() != "OK":
            dq_reasons.append(f"cross.roll25_confidence={rc}")
        # roll25_derived confidence gate
        rdc = roll25_derived.get("confidence")
        if isinstance(rdc, str) and rdc.upper() != "OK":
            dq_reasons.append(f"roll25_derived.confidence={rdc}")
        # used_date_status gate
        uds = roll25_core.get("used_date_status")
        if isinstance(uds, str) and uds.upper() != "OK_LATEST":
            dq_reasons.append(f"roll25.used_date_status={uds}")
        # lookback short gate
        try:
            tgt = int(roll25_core.get("LookbackNTarget")) if roll25_core.get("LookbackNTarget") is not None else None
            act = int(roll25_core.get("LookbackNActual")) if roll25_core.get("LookbackNActual") is not None else None
        except Exception:
            tgt, act = None, None
        if isinstance(tgt, int) and isinstance(act, int) and act < tgt:
            dq_reasons.append(f"roll25.LookbackNActual<{tgt} (actual={act})")
        # ohlc missing gate
        sigs = roll25_core.get("signals")
        ohlc_missing = _infer_ohlc_missing(sigs, roll25_latest)
        if ohlc_missing is True:
            dq_reasons.append("signals.OhlcMissing=true")

        dq = True if dq_reasons else False

    return {"heated_market": heated, "dq_issue": dq, "dq_reasons": dq_reasons}


def _build_roll25_split_ref(vals: Dict[str, Any]) -> str:
    heated = vals.get("heated_market")
    dq = vals.get("dq_issue")

    heated_s = "NA" if heated is None else ("true" if heated else "false")
    dq_s = "NA" if dq is None else ("true" if dq else "false")

    return f"heated_market={heated_s}, dq_issue={dq_s} (see roll25_cache section)"


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

    source_policy = "SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)"

    spx_m = _find_row(m_rows, "SP500")
    vix_m = _find_row(m_rows, "VIX")

    spx_sig = spx_m.get("signal_level") if isinstance(spx_m, dict) else None
    spx_tag = spx_m.get("tag") if isinstance(spx_m, dict) else None
    spx_date = spx_m.get("data_date") if isinstance(spx_m, dict) else None

    trend_on = bool(
        isinstance(spx_sig, str)
        and spx_sig.upper() == "INFO"
        and isinstance(spx_tag, str)
        and ("LONG_EXTREME" in spx_tag.upper())
    )

    credit = _find_row(f_rows, "BAMLH0A0HYM2")
    dgs10 = _find_row(f_rows, "DGS10")

    credit_sig = credit.get("signal_level") if isinstance(credit, dict) else None
    dgs10_sig = dgs10.get("signal_level") if isinstance(dgs10, dict) else None

    credit_fragile = _truthy_signal(credit_sig, ["ALERT"])
    rate_stress = _truthy_signal(dgs10_sig, ["WATCH", "ALERT"])
    tw_margin_sig = tw_cross.get("margin_signal") if isinstance(tw_cross, dict) else None
    tw_margin = _truthy_signal(tw_margin_sig, ["WATCH", "ALERT"])
    cross_cons = tw_cross.get("consistency") if isinstance(tw_cross, dict) else None
    cross_divergence = bool(isinstance(cross_cons, str) and cross_cons.upper() == "DIVERGENCE")

    fragility_high = bool((credit_fragile or rate_stress) and (tw_margin or cross_divergence))

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
    if isinstance(sp