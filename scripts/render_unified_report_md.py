#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render unified_dashboard/latest.json into report.md

Adds:
- (2) Positioning Matrix (report-only; deterministic; uses signals already present in unified JSON)
- roll25_derived (realized vol / max drawdown)
- fx_usdtwd section (BOT USD/TWD mid + deterministic signal)
- AUTO Module Status (core modules first, then any extra modules sorted)
- Optional module sections: inflation_realrate_cache / asset_proxy_cache (display-only; no guessing)
- taiwan_signals (pass-through; not used for mode)
  - Prefer --tw-signals only
  - If missing/unreadable/core fields missing -> NA + dq_note
  - NO silent fallback to unified.modules.taiwan_margin_financing.cross_module

This renderer does NOT recompute market/fred/margin/roll25/fx stats; it only formats fields already in unified JSON.
If a field is missing => prints NA.

2026-02-03 update:
- taiwan_signals: prefer --tw-signals; no fallback to unified cross_module; missing -> NA + dq_note
- roll25_cache: remove heat_split.* lines from report
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


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
    if not isinstance(mom, dict):
        return True
    keys = [
        "ret1_pct", "chg_5d_pct",
        "ret1_from", "ret1_to",
        "chg_5d_from", "chg_5d_to",
    ]
    for k in keys:
        if k in mom and mom.get(k) is not None:
            return False
    return True


# ---- generic module rendering (display-only) ----

def _render_generic_dashboard_section(lines: List[str], module_name: str, mod: Any) -> None:
    lines.append(f"## {module_name} (detailed)")
    lines.append(f"- status: {_safe_get(mod,'status') or 'NA'}")

    dash = _safe_get(mod, "dashboard_latest") or {}
    meta = _safe_get(dash, "meta") or {}
    rows = _safe_get(dash, "rows") or []

    if isinstance(meta, dict) and meta:
        lines.append(f"- as_of_ts: {meta.get('stats_as_of_ts','NA')}")
        lines.append(f"- run_ts_utc: {meta.get('run_ts_utc','NA')}")
        lines.append(f"- ruleset_id: {meta.get('ruleset_id','NA')}")
        lines.append(f"- script_fingerprint: {meta.get('script_fingerprint','NA')}")
        lines.append(f"- script_version: {meta.get('script_version','NA')}")
        lines.append(f"- series_count: {meta.get('series_count','NA')}")

    if isinstance(rows, list) and rows:
        hdr = [
            "series","signal","dir","class","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%60","reason","tag","prev",
            "delta","streak_hist","streak_wa","source"
        ]
        rws: List[List[str]] = []
        for it in rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag", "NA")
            cls = "NONE"
            if isinstance(tag, str):
                up = tag.upper()
                if "LONG_EXTREME" in up:
                    cls = "LONG"
                elif "EXTREME_Z" in up:
                    cls = "LEVEL"
                elif "JUMP" in up:
                    cls = "JUMP"
            rws.append([
                str(it.get("series","NA")),
                str(it.get("signal_level","NA")),
                str(it.get("dir","NA")),
                cls,
                _fmt(it.get("value"),6),
                str(it.get("data_date","NA")),
                _fmt(it.get("age_hours"),6),
                _fmt(it.get("z60"),6),
                _fmt(it.get("p60"),6),
                _fmt(it.get("p252"),6),
                _fmt(it.get("z_delta60"),6),
                _fmt(it.get("p_delta60"),6),
                _fmt(it.get("ret1_pct60"),6),
                str(it.get("reason","NA")),
                str(tag),
                str(it.get("prev_signal","NA")),
                str(it.get("delta_signal","NA")),
                _fmt_int(it.get("streak_hist")),
                _fmt_int(it.get("streak_wa")),
                str(it.get("source_url","NA")),
            ])
        lines.append("")
        lines.append(_md_table(hdr, rws))
        lines.append("")
    else:
        lines.append("- note: dashboard_latest.rows missing/empty; nothing to render (deterministic).")
        lines.append("")


def _render_module_status(lines: List[str], modules: Dict[str, Any], unified_generated_at_utc: str) -> None:
    core_order = [
        "market_cache",
        "fred_cache",
        "roll25_cache",
        "taiwan_margin_financing",
        "fx_usdtwd",
    ]

    lines.append("## Module Status")
    seen = set()

    for name in core_order:
        if name in modules:
            lines.append(f"- {name}: {_safe_get(modules.get(name), 'status') or 'NA'}")
            seen.add(name)
        else:
            lines.append(f"- {name}: NA")

    extras = sorted([k for k in modules.keys() if k not in seen])
    for name in extras:
        lines.append(f"- {name}: {_safe_get(modules.get(name), 'status') or 'NA'}")

    lines.append(f"- unified_generated_at_utc: {unified_generated_at_utc}\n")


# ---- taiwan_signals (pass-through) helpers ----

def _try_load_json_dict_with_note(path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Deterministic:
    - Returns ({}, dq_note) on any failure.
    - Returns (dict_obj, None) on success.
    """
    try:
        obj = _load_json(path)
    except FileNotFoundError:
        return {}, "TW_SIGNALS_FILE_NOT_FOUND"
    except Exception:
        return {}, "TW_SIGNALS_READ_OR_PARSE_FAILED"

    if not isinstance(obj, dict):
        return {}, "TW_SIGNALS_NOT_A_DICT"
    return obj, None


def _get_first_present(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d.get(k) is not None:
            return d.get(k)
    return None


def _extract_date_alignment(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    da = d.get("date_alignment")
    if isinstance(da, dict) and da:
        return da
    rat = d.get("rationale")
    if isinstance(rat, dict):
        da2 = rat.get("date_alignment")
        if isinstance(da2, dict) and da2:
            return da2
    return None


def _render_taiwan_signals_pass_through(
    lines: List[str],
    tw_signals_path: str,
) -> None:
    tw_sig, load_note = _try_load_json_dict_with_note(tw_signals_path)

    # Core fields (required for "usable" summary)
    margin_signal = _get_first_present(tw_sig, ["margin_signal", "signal"])
    consistency = _get_first_present(tw_sig, ["consistency", "resonance"])

    # Optional fields
    confidence = _get_first_present(tw_sig, ["confidence", "margin_confidence"])
    dq_reason = _get_first_present(tw_sig, ["dq_reason"])
    da = _extract_date_alignment(tw_sig)

    dq_note: Optional[str] = None

    if load_note is not None:
        dq_note = load_note
        # Force NA display for all fields when file unreadable
        margin_signal = None
        consistency = None
        confidence = None
        dq_reason = None
        da = None
    else:
        # No fallback; if core fields missing, show NA + dq_note
        missing_core: List[str] = []
        if margin_signal is None:
            missing_core.append("margin_signal")
        if consistency is None:
            missing_core.append("consistency")
        if missing_core:
            dq_note = "TW_SIGNALS_MISSING_CORE_FIELDS:" + ",".join(missing_core)

    lines.append("### taiwan_signals (pass-through; not used for mode)")
    lines.append(f"- source: --tw-signals ({tw_signals_path})")
    lines.append(f"- margin_signal: {margin_signal if margin_signal is not None else 'NA'}")
    lines.append(f"- consistency: {consistency if consistency is not None else 'NA'}")
    lines.append(f"- confidence: {confidence if confidence is not None else 'NA'}")
    lines.append(f"- dq_reason: {dq_reason if dq_reason is not None else 'NA'}")

    if isinstance(da, dict) and da:
        lines.append(
            f"- date_alignment: twmargin_date={da.get('twmargin_date','NA')}, "
            f"roll25_used_date={da.get('roll25_used_date','NA')}, "
            f"match={str(da.get('used_date_match','NA')).lower()}"
        )
    else:
        lines.append("- date_alignment: NA")

    if dq_note is not None:
        lines.append(f"- dq_note: {dq_note}")
    lines.append("")


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
    ap.add_argument(
        "--tw-signals",
        dest="tw_signals_path",
        default="taiwan_margin_cache/signals_latest.json",
        help="Taiwan margin signals_latest.json path (pass-through only; no fallback)",
    )

    args = ap.parse_args()

    uni = _load_json(args.in_path)
    rendered_at_utc = _now_utc_z()

    modules = uni.get("modules", {}) if isinstance(uni, dict) else {}
    if not isinstance(modules, dict):
        modules = {}

    market = modules.get("market_cache", {})
    fred = modules.get("fred_cache", {})
    roll25 = modules.get("roll25_cache", {})
    twm = modules.get("taiwan_margin_financing", {})
    fx = modules.get("fx_usdtwd", {})

    infl = modules.get("inflation_realrate_cache", {})
    apx = modules.get("asset_proxy_cache", {})

    lines: List[str] = []
    lines.append("# Unified Risk Dashboard Report\n")

    _render_module_status(lines, modules, str(uni.get("generated_at_utc", "NA")))

    # ----------------------------
    # (2) Positioning Matrix (global-only for fragility)
    # ----------------------------
    m_dash = _safe_get(market, "dashboard_latest") or {}
    m_rows = _safe_get(m_dash, "rows") or []

    f_dash = _safe_get(fred, "dashboard_latest") or {}
    f_rows = _safe_get(f_dash, "rows") or []

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

    # GLOBAL-ONLY fragility parts
    credit_fragile = _truthy_signal(credit_sig, ["ALERT"])
    rate_stress = _truthy_signal(dgs10_sig, ["WATCH", "ALERT"])
    fragility_high = bool(credit_fragile or rate_stress)

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
        "- fragility_parts (global-only): "
        f"credit_fragile(BAMLH0A0HYM2={credit_sig if credit_sig is not None else 'NA'})="
        f"{str(credit_fragile).lower()}, "
        f"rate_stress(DGS10={dgs10_sig if dgs10_sig is not None else 'NA'})="
        f"{str(rate_stress).lower()}"
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

    # taiwan signals pass-through (NO fallback)
    _render_taiwan_signals_pass_through(lines, args.tw_signals_path)

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
            "series","signal","dir","market_class","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%60","reason","tag","prev",
            "delta","streak_hist","streak_wa","source"
        ]
        rws: List[List[str]] = []
        for it in m_rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag","NA")
            mclass = "NONE"
            if isinstance(tag, str):
                up = tag.upper()
                if "LONG_EXTREME" in up:
                    mclass = "LONG"
                if "EXTREME_Z" in up:
                    mclass = "LEVEL" if mclass == "NONE" else f"{mclass}+LEVEL"
                if "JUMP" in up:
                    mclass = "JUMP" if mclass == "NONE" else f"{mclass}+JUMP"
            rws.append([
                str(it.get("series","NA")),
                str(it.get("signal_level","NA")),
                str(it.get("dir","NA")),
                mclass,
                _fmt(it.get("value"),6),
                str(it.get("data_date","NA")),
                _fmt(it.get("age_hours"),6),
                _fmt(it.get("z60"),6),
                _fmt(it.get("p60"),6),
                _fmt(it.get("p252"),6),
                _fmt(it.get("z_delta60"),6),
                _fmt(it.get("p_delta60"),6),
                _fmt(it.get("ret1_pct60"),6),
                str(it.get("reason","NA")),
                str(tag),
                str(it.get("prev_signal","NA")),
                str(it.get("delta_signal","NA")),
                _fmt_int(it.get("streak_hist")),
                _fmt_int(it.get("streak_wa")),
                str(it.get("source_url","NA")),
            ])
        lines.append(_md_table(hdr, rws))
        lines.append("")

    # ----------------------------
    # fred_cache
    # ----------------------------
    f_meta = _safe_get(f_dash, "meta") or {}
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
            "series","signal","fred_dir","fred_class","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%","reason","tag","prev","delta","source"
        ]
        rws_f: List[List[str]] = []
        for it in f_rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag","NA")
            fclass = "NONE"
            if isinstance(tag, str):
                up = tag.upper()
                if "LONG_EXTREME" in up:
                    fclass = "LONG"
                elif "EXTREME_Z" in up:
                    fclass = "LEVEL"
                elif "JUMP" in up:
                    fclass = "JUMP"
            rws_f.append([
                str(it.get("series","NA")),
                str(it.get("signal_level","NA")),
                str(it.get("fred_dir","NA")),
                fclass,
                _fmt(it.get("value"),6),
                str(it.get("data_date","NA")),
                _fmt(it.get("age_hours"),6),
                _fmt(it.get("z60"),6),
                _fmt(it.get("p60"),6),
                _fmt(it.get("p252"),6),
                _fmt(it.get("z_delta_60"),6),
                _fmt(it.get("p_delta_60"),6),
                _fmt(it.get("ret1_pct"),6),
                str(it.get("reason","NA")),
                str(tag),
                str(it.get("prev_signal","NA")),
                str(it.get("delta_signal","NA")),
                str(it.get("source_url","NA")),
            ])
        lines.append(_md_table(hdr, rws_f))
        lines.append("")

    # optional modules
    if "inflation_realrate_cache" in modules:
        _render_generic_dashboard_section(lines, "inflation_realrate_cache", infl)
    if "asset_proxy_cache" in modules:
        _render_generic_dashboard_section(lines, "asset_proxy_cache", apx)

    # ----------------------------
    # roll25_cache (core fields from latest report)
    # ----------------------------
    r_latest = _safe_get(roll25, "latest_report") or {}
    r_core = _safe_get(roll25, "core") or {}

    if not r_core and isinstance(r_latest, dict):
        nums = r_latest.get("numbers", {}) if isinstance(r_latest.get("numbers"), dict) else {}
        sigs0 = r_latest.get("signal", {}) if isinstance(r_latest.get("signal"), dict) else {}
        r_core = {
            "UsedDate": nums.get("UsedDate") or r_latest.get("used_date"),
            "run_day_tag": r_latest.get("run_day_tag"),
            "used_date_status": r_latest.get("used_date_status") or r_latest.get("tag_used_date_status"),
            "used_date_selection_tag": r_latest.get("tag"),
            "tag_legacy": r_latest.get("tag"),
            "risk_level": r_latest.get("risk_level"),
            "turnover_twd": nums.get("TradeValue"),
            "turnover_unit": "TWD",
            "volume_multiplier": nums.get("VolumeMultiplier"),
            "vol_multiplier": nums.get("VolMultiplier"),
            "amplitude_pct": nums.get("AmplitudePct"),
            "pct_change": nums.get("PctChange"),
            "close": nums.get("Close"),
            "signals": sigs0,
            "LookbackNTarget": nums.get("LookbackNTarget") or 20,
            "LookbackNActual": r_latest.get("lookback_n_actual") or nums.get("LookbackNActual"),
            "ohlc_status": r_latest.get("ohlc_status"),
            "freshness_ok": r_latest.get("freshness_ok"),
        }

    run_day_tag = (
        uni.get("run_day_tag")
        or _safe_get(r_core, "run_day_tag")
        or _safe_get(r_latest, "run_day_tag")
        or "NA"
    )

    used_date_status = (
        _safe_get(r_core, "used_date_status")
        or _safe_get(r_latest, "used_date_status")
        or _safe_get(r_latest, "tag_used_date_status")
        or "NA"
    )

    used_date_selection_tag = (
        _safe_get(r_core, "used_date_selection_tag")
        or _safe_get(r_latest, "used_date_selection_tag")
        or _safe_get(r_core, "tag_legacy")
        or _safe_get(r_latest, "tag")
        or "NA"
    )

    legacy_tag = (
        _safe_get(r_core, "tag_legacy")
        or _safe_get(r_latest, "tag")
        or "NA"
    )

    lines.append("## roll25_cache (TW turnover)")
    lines.append(f"- status: {_safe_get(roll25,'status') or 'NA'}")
    lines.append(f"- UsedDate: {_fmt(r_core.get('UsedDate'),0)}")
    lines.append(f"- run_day_tag: {run_day_tag}")
    lines.append(f"- used_date_status: {used_date_status}")
    lines.append(f"- used_date_selection_tag: {used_date_selection_tag}")
    lines.append(f"- tag (legacy): {legacy_tag}")
    lines.append("- note: run_day_tag is report-day context; UsedDate is the data date used for calculations (may lag on not-updated days)")

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
        for k in ["DownDay","VolumeAmplified","VolAmplified","NewLow_N","ConsecutiveBreak"]:
            lines.append(f"- signals.{k}: {_fmt(sigs.get(k),0)}")
        lines.append(f"- signals.OhlcMissing: {_fmt(ohlc_missing,0)}")
    else:
        lines.append(f"- signals.OhlcMissing: {_fmt(ohlc_missing,0)}")
    lines.append("")

    # roll25 derived
    r_der = _safe_get(roll25, "derived") or {}
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
    fx_der2 = _safe_get(fx, "derived") or {}
    lines.append("## FX (USD/TWD)")
    lines.append(f"- status: {_safe_get(fx,'status') or 'NA'}")
    lines.append(f"- data_date: {fx_der2.get('data_date','NA')}")
    lines.append(f"- source_url: {fx_der2.get('source_url','NA')}")
    usd = fx_der2.get("usd_twd", {}) if isinstance(fx_der2.get("usd_twd"), dict) else {}
    lines.append(f"- spot_buy: {_fmt(usd.get('spot_buy'),6)}")
    lines.append(f"- spot_sell: {_fmt(usd.get('spot_sell'),6)}")
    lines.append(f"- mid: {_fmt(usd.get('mid'),6)}")
    mom = fx_der2.get("momentum", None)

    momentum_unavailable = _fx_momentum_unavailable(mom)
    if momentum_unavailable:
        lines.append("- momentum_unavailable: true (deterministic dq note)")

    mom_dict = mom if isinstance(mom, dict) else {}
    lines.append(f"- ret1_pct: {_fmt(mom_dict.get('ret1_pct'),6)} (from {mom_dict.get('ret1_from','NA')} to {mom_dict.get('ret1_to','NA')})")
    lines.append(f"- chg_5d_pct: {_fmt(mom_dict.get('chg_5d_pct'),6)} (from {mom_dict.get('chg_5d_from','NA')} to {mom_dict.get('chg_5d_to','NA')})")
    lines.append(f"- dir: {fx_der2.get('dir','NA')}")
    lines.append(f"- fx_signal: {fx_der2.get('fx_signal','NA')}")
    lines.append(f"- fx_reason: {fx_der2.get('fx_reason','NA')}")
    lines.append(f"- fx_confidence: {fx_der2.get('fx_confidence','NA')}")
    lines.append("")

    # taiwan margin financing (module header only; detailed decisions are in dedicated dashboard)
    tw_latest = _safe_get(twm, "latest") or {}
    lines.append("## taiwan_margin_financing (TWSE/TPEX)")
    lines.append(f"- status: {_safe_get(twm,'status') or 'NA'}")
    lines.append(f"- schema_version: {tw_latest.get('schema_version','NA')}")
    lines.append(f"- generated_at_utc: {tw_latest.get('generated_at_utc','NA')}")
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