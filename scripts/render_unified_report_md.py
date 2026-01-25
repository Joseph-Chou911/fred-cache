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
    - OR momentum exists but all key fields are None => unavailable
    """
    if not isinstance(mom, dict):
        return True
    keys = [
        "ret1_pct", "chg_5d_pct",
        "ret1_from", "ret1_to",
        "chg_5d_from", "chg_5d_to",
    ]
    any_present = False
    for k in keys:
        if k in mom:
            any_present = True
            if mom.get(k) is not None:
                return False
    # If none of the keys exist, treat as unavailable; if keys exist but all None, unavailable
    return True if (not any_present or True) else True


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

    # Conservative runaway gate: ALERT, or WATCH with very large jump
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

    # mode mapping (deterministic; report-only)
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

    # dq gates (display-only; conservative)
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
                if "LONG_EXTREME" in tag:
                    mclass = "LONG"
                if "EXTREME_Z" in tag:
                    mclass = "LEVEL" if mclass == "NONE" else f"{mclass}+LEVEL"
                if "JUMP" in tag:
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
                if "LONG_EXTREME" in tag:
                    fclass = "LONG"
                elif "EXTREME_Z" in tag:
                    fclass = "LEVEL"
                elif "JUMP" in tag:
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

    # ----------------------------
    # roll25_cache (core fields from latest report)
    # ----------------------------
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

    # (A) deterministic note to avoid semantic confusion
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
    fx_der = _safe_get(fx, "derived") or {}
    lines.append("## FX (USD/TWD)")
    lines.append(f"- status: {_safe_get(fx,'status') or 'NA'}")
    lines.append(f"- data_date: {fx_der.get('data_date','NA')}")
    lines.append(f"- source_url: {fx_der.get('source_url','NA')}")
    usd = fx_der.get("usd_twd", {}) if isinstance(fx_der.get("usd_twd"), dict) else {}
    lines.append(f"- spot_buy: {_fmt(usd.get('spot_buy'),6)}")
    lines.append(f"- spot_sell: {_fmt(usd.get('spot_sell'),6)}")
    lines.append(f"- mid: {_fmt(usd.get('mid'),6)}")
    mom = fx_der.get("momentum", None)

    # (B) deterministic dq note (unavailable if missing or all key fields None)
    momentum_unavailable = _fx_momentum_unavailable(mom)
    if momentum_unavailable:
        lines.append("- momentum_unavailable: true (deterministic dq note)")

    mom_dict = mom if isinstance(mom, dict) else {}
    lines.append(f"- ret1_pct: {_fmt(mom_dict.get('ret1_pct'),6)} (from {mom_dict.get('ret1_from','NA')} to {mom_dict.get('ret1_to','NA')})")
    lines.append(f"- chg_5d_pct: {_fmt(mom_dict.get('chg_5d_pct'),6)} (from {mom_dict.get('chg_5d_from','NA')} to {mom_dict.get('chg_5d_to','NA')})")
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
    cross = _safe_get(twm, "cross_module") or {}
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
        lines.append(f"- roll25_heated (legacy): {_fmt(cross.get('roll25_heated'),0)}")
        lines.append(f"- roll25_confidence: {cross.get('roll25_confidence','NA')}")

        # Optional: split reference if present (kept minimal; no guessing)
        split_ref = cross.get("roll25_split_ref")
        if split_ref is not None:
            lines.append(f"- roll25_split_ref: {split_ref}")

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