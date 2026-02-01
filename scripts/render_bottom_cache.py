#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottom_cache renderer:
- Global bottom/reversal workflow from market_cache (single-source)
- TW local gate from existing repo outputs (no fetch):
    * roll25_cache/latest_report.json
    * taiwan_margin_cache/latest.json

Outputs (ONE folder):
- dashboard_bottom_cache/latest.json
- dashboard_bottom_cache/history.json
- dashboard_bottom_cache/report.md

Principles:
- Deterministic rules only; no guessing.
- Missing fields => NA + excluded reasons.
- TW leverage heat: flow-only signal is always computed if enough rows.
  Optional "level gate" is applied when there are enough balance points; otherwise downgrade (does not NA-out the signal).

Patch v0.1.2:
- report.md Recent History table: normalize None -> "NA" (fix legacy history rows)
- Fix a critical formatting bug: DO NOT render legitimate signal "NONE" as "NA"
  (previous _fmt_na used s.lower()=="none" which incorrectly mapped "NONE" -> "NA")
- Normalize margin signal to canonical {"NONE","WATCH","ALERT"} or None
  so TRIG_TW_LEVERAGE_HEAT cannot show 0 when margin signal is actually NA/None.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo

TZ_TPE = ZoneInfo("Asia/Taipei")

# ---- config ----
MARKET_STATS_PATH = "market_cache/stats_latest.json"

# TW inputs (existing workflow outputs, no fetch)
TW_ROLL25_REPORT_PATH = "roll25_cache/latest_report.json"
TW_MARGIN_PATH = "taiwan_margin_cache/latest.json"

# unified output folder
OUT_DIR = "dashboard_bottom_cache"
OUT_LATEST = f"{OUT_DIR}/latest.json"
OUT_HISTORY = f"{OUT_DIR}/history.json"
OUT_MD = f"{OUT_DIR}/report.md"

# what we need from market_cache
NEEDED = ["VIX", "SP500", "HYG_IEF_RATIO", "OFR_FSI"]

# risk direction is a RULE (not guessed)
RISK_DIR = {
    "VIX": "HIGH",
    "OFR_FSI": "HIGH",
    "HYG_IEF_RATIO": "LOW",
    "SP500": "LOW",
}

# v0 thresholds (deterministic)
TH_VIX_PANIC = 20.0
TH_SPX_RET1_PANIC = -1.5     # unit = percent (%)
TH_HYG_VETO_Z = -2.0         # systemic credit stress veto (LOW direction)
TH_OFR_VETO_Z = 2.0          # systemic stress veto (HIGH direction)

HISTORY_SHOW_N = 10

# --- TW panic semantics (deterministic numeric thresholds) ---
TH_TW_CONSEC_BREAK_STRESS = 2       # ConsecutiveBreak >= 2 counts as stress
TH_TW_NEWLOW_STRESS_MIN = 1         # NewLow_N >= 1 counts as stress

# --- TW margin flow thresholds (億) ---
TW_MARGIN_WATCH_SUM5_YI = 100.0
TW_MARGIN_ALERT_SUM5_YI = 150.0
TW_MARGIN_POSDAYS5_MIN = 4
TW_MARGIN_FLOW_MIN_POINTS = 5       # require last5 fully available for strictness

# --- OPTIONAL: TW margin level gate (balance percentile) ---
TW_MARGIN_LEVEL_GATE_ENABLED = True
TW_MARGIN_LEVEL_MIN_POINTS = 60     # below this => downgrade to flow-only
TW_MARGIN_LEVEL_WINDOW = 252        # use up to last252 points if available
TW_MARGIN_LEVEL_P_MIN = 95.0        # high percentile => "level is extreme"


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tpe_now() -> str:
    return datetime.now(TZ_TPE).isoformat()


def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            return float(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None


def _as_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return int(x)
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return int(float(s))
    except Exception:
        return None


def _as_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    s = str(x).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def _as_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x)
    if s.strip() == "" or s.strip().upper() == "NA":
        return None
    return s


def _get(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _series_signal(z60: Optional[float], p252: Optional[float]) -> Optional[str]:
    if z60 is None and p252 is None:
        return None
    if z60 is not None and abs(z60) >= 2.5:
        return "ALERT"
    if z60 is not None and abs(z60) >= 2.0:
        return "WATCH"
    if p252 is not None and (p252 >= 95.0 or p252 <= 5.0):
        return "INFO"
    return "NONE"


def _day_key_tpe_from_iso(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_TPE)
        return dt.date().isoformat()
    except Exception:
        return "NA"


def _safe_float_str(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    fmt = f"{{:.{nd}f}}"
    return fmt.format(float(x))


def _iso_sort_key(iso: str) -> Tuple[int, str]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (int(dt.timestamp()), iso)
    except Exception:
        return (0, iso)


def _fmt_na(x: Any) -> str:
    """
    Normalize any null-ish value for report rendering.
    IMPORTANT: "NONE" is a legitimate signal value and must NOT be rendered as "NA".

    - None -> "NA"
    - empty string -> "NA"
    - "NA"/"N/A"/"NULL"/"NaN" (case-insensitive) -> "NA"
    - legacy null strings: "None" or "none" -> "NA"  (but "NONE" stays "NONE")
    Otherwise -> str(x)
    """
    if x is None:
        return "NA"

    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return "NA"

        up = s.upper()
        if up in ("NA", "N/A", "NULL", "NAN"):
            return "NA"

        # legacy null strings (do NOT collapse "NONE")
        if s in ("None", "none"):
            return "NA"

        return s

    return str(x)


def _canon_margin_signal(x: Any) -> Optional[str]:
    """
    Canonicalize margin signal:
    - returns one of {"NONE","WATCH","ALERT"} or None
    - treats "NA"/"None"/""/"null"/"nan" as None
    - normalizes case (e.g., "watch" -> "WATCH")
    """
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return None
        up = s.upper()
        if up in ("NA", "N/A", "NULL", "NAN"):
            return None
        if s in ("None", "none"):
            return None
        if up in ("NONE", "WATCH", "ALERT"):
            return up
        return None
    return None


# ---------------- TW helpers ----------------

def _load_tw_roll25(excluded: List[Dict[str, str]]) -> Tuple[Dict[str, Any], bool]:
    if not os.path.exists(TW_ROLL25_REPORT_PATH):
        excluded.append({"trigger": "TW:INPUT_ROLL25", "reason": "not_available:file_not_found"})
        return ({}, False)
    try:
        obj = _read_json(TW_ROLL25_REPORT_PATH)
        return (obj if isinstance(obj, dict) else {}, True)
    except Exception as e:
        excluded.append({"trigger": "TW:INPUT_ROLL25", "reason": f"read_or_parse_failed:{type(e).__name__}"})
        return ({}, False)


def _load_tw_margin(excluded: List[Dict[str, str]]) -> Tuple[Dict[str, Any], bool]:
    if not os.path.exists(TW_MARGIN_PATH):
        excluded.append({"trigger": "TW:INPUT_MARGIN", "reason": "not_available:file_not_found"})
        return ({}, False)
    try:
        obj = _read_json(TW_MARGIN_PATH)
        return (obj if isinstance(obj, dict) else {}, True)
    except Exception as e:
        excluded.append({"trigger": "TW:INPUT_MARGIN", "reason": f"read_or_parse_failed:{type(e).__name__}"})
        return ({}, False)


def _sort_rows_newest_first(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _k(r: Dict[str, Any]) -> str:
        return _as_str(r.get("date")) or ""
    # dates are YYYY-MM-DD; lexical sort works
    return sorted(rows, key=_k, reverse=True)


def _derive_margin_flow_signal(rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Flow-only leverage heat signal from TWSE rows (chg_yi):
    - WATCH if sum_last5 >= 100 and pos_days_last5 >= 4
    - ALERT if sum_last5 >= 150 and pos_days_last5 >= 4
    Returns (signal, dbg); signal=None => NA (insufficient data)
    """
    if not isinstance(rows, list) or len(rows) == 0:
        return (None, {"reason": "rows_empty_or_invalid"})

    rows2 = _sort_rows_newest_first([r for r in rows if isinstance(r, dict)])
    last5 = rows2[:5]
    chgs: List[float] = []
    for r in last5:
        v = _as_float(r.get("chg_yi"))
        if v is None:
            chgs.append(float("nan"))
        else:
            chgs.append(float(v))

    if len(chgs) < TW_MARGIN_FLOW_MIN_POINTS or any(str(x) == "nan" for x in chgs):
        return (
            None,
            {
                "reason": "insufficient_flow_points_or_nan",
                "need_points": TW_MARGIN_FLOW_MIN_POINTS,
                "have_points": len(chgs),
                "chg_last5_yi": chgs,
            },
        )

    sum5 = float(sum(chgs))
    pos_days = sum(1 for x in chgs if x > 0)

    sig = "NONE"
    if pos_days >= TW_MARGIN_POSDAYS5_MIN and sum5 >= TW_MARGIN_ALERT_SUM5_YI:
        sig = "ALERT"
    elif pos_days >= TW_MARGIN_POSDAYS5_MIN and sum5 >= TW_MARGIN_WATCH_SUM5_YI:
        sig = "WATCH"

    dbg = {
        "chg_last5_yi": chgs,
        "sum_last5_yi": sum5,
        "pos_days_last5": pos_days,
        "rule": f"WATCH(sum5>={TW_MARGIN_WATCH_SUM5_YI} & pos_days>={TW_MARGIN_POSDAYS5_MIN}); "
                f"ALERT(sum5>={TW_MARGIN_ALERT_SUM5_YI} & pos_days>={TW_MARGIN_POSDAYS5_MIN})",
    }
    return (sig, dbg)


def _compute_percentile(latest: float, xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    n = len(xs)
    c = sum(1 for x in xs if x <= latest)
    return (c / n) * 100.0


def _derive_margin_level_gate(rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Level gate using balance_yi percentile within last N points (up to 252).
    - PASS if p >= 95
    - FAIL if p < 95
    - NA if insufficient points (<60)
    """
    if not TW_MARGIN_LEVEL_GATE_ENABLED:
        return ("SKIPPED", {"reason": "level_gate_disabled"})

    rows2 = _sort_rows_newest_first([r for r in rows if isinstance(r, dict)])
    balances: List[float] = []
    for r in rows2[: max(1, min(TW_MARGIN_LEVEL_WINDOW, len(rows2)))]:
        v = _as_float(r.get("balance_yi"))
        if v is None:
            continue
        balances.append(float(v))

    if len(balances) < TW_MARGIN_LEVEL_MIN_POINTS:
        return (
            None,
            {
                "reason": "insufficient_level_points",
                "min_points": TW_MARGIN_LEVEL_MIN_POINTS,
                "have_points": len(balances),
            },
        )

    latest = balances[0]
    p = _compute_percentile(latest, balances)
    if p is None:
        return (None, {"reason": "percentile_compute_failed"})

    gate = "PASS" if p >= TW_MARGIN_LEVEL_P_MIN else "FAIL"
    dbg = {
        "window_used": min(TW_MARGIN_LEVEL_WINDOW, len(balances)),
        "p": p,
        "p_min": TW_MARGIN_LEVEL_P_MIN,
        "latest_balance_yi": latest,
    }
    return (gate, dbg)


def main() -> None:
    run_ts_utc = _utc_now()
    as_of_ts_tpe = _tpe_now()
    git_sha = os.environ.get("GITHUB_SHA", "NA")

    excluded: List[Dict[str, str]] = []

    # ---- read market_cache stats ----
    try:
        root = _read_json(MARKET_STATS_PATH)
        ok_market = True
    except Exception as e:
        root = {}
        ok_market = False
        excluded.append({"trigger": "ALL", "reason": f"read_or_parse_failed:{type(e).__name__}"})

    meta = {
        "generated_at_utc": _as_str(root.get("generated_at_utc")),
        "as_of_ts": _as_str(root.get("as_of_ts")),
        "script_version": _as_str(root.get("script_version")),
        "ret1_mode": _as_str(root.get("ret1_mode")),
        "percentile_method": _as_str(root.get("percentile_method")),
    }

    series_root = root.get("series") if isinstance(root.get("series"), dict) else {}

    # ---- extract series snapshots ----
    series_out: Dict[str, Any] = {}
    for sid in NEEDED:
        s = series_root.get(sid, {}) if isinstance(series_root, dict) else {}
        latest = s.get("latest") if isinstance(s.get("latest"), dict) else {}
        w60 = _get(s, ["windows", "w60"]) if isinstance(_get(s, ["windows", "w60"]), dict) else {}
        w252 = _get(s, ["windows", "w252"]) if isinstance(_get(s, ["windows", "w252"]), dict) else {}

        z60 = _as_float(w60.get("z"))
        p252 = _as_float(w252.get("p"))

        sig = _series_signal(z60, p252)

        series_out[sid] = {
            "series_id": sid,
            "risk_dir": RISK_DIR.get(sid, "NA"),
            "latest": {
                "data_date": _as_str(latest.get("data_date")),
                "value": _as_float(latest.get("value")),
                "as_of_ts": _as_str(latest.get("as_of_ts")) or meta["as_of_ts"],
                "source_url": _as_str(latest.get("source_url")) or "NA",
            },
            "w60": {
                "z": z60,
                "p": _as_float(w60.get("p")),
                "ret1_pct": _as_float(w60.get("ret1_pct")),
                "z_delta": _as_float(w60.get("z_delta")),
                "p_delta": _as_float(w60.get("p_delta")),
            },
            "w252": {
                "z": _as_float(w252.get("z")),
                "p": p252,
            },
            "series_signal": sig or "NA",
        }

    # ---- Global triggers ----
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]

    trig_panic: Optional[int] = None
    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and float(vix_val) >= TH_VIX_PANIC)
        cond_spx = (spx_ret1 is not None and float(spx_ret1) <= TH_SPX_RET1_PANIC)
        trig_panic = 1 if (cond_vix or cond_spx) else 0

    hyg_z = series_out["HYG_IEF_RATIO"]["w60"]["z"]
    hyg_sig = series_out["HYG_IEF_RATIO"]["series_signal"]
    ofr_z = series_out["OFR_FSI"]["w60"]["z"]
    ofr_sig = series_out["OFR_FSI"]["series_signal"]

    trig_veto: Optional[int] = None
    if hyg_z is None and ofr_z is None:
        excluded.append({"trigger": "TRIG_SYSTEMIC_VETO", "reason": "missing_fields:HYG_IEF_RATIO.w60.z & OFR_FSI.w60.z"})
    else:
        hyg_can = (hyg_z is not None and hyg_sig in ("WATCH", "ALERT"))
        ofr_can = (ofr_z is not None and ofr_sig in ("WATCH", "ALERT"))
        hyg_veto = 1 if (hyg_can and float(hyg_z) <= TH_HYG_VETO_Z) else 0
        ofr_veto = 1 if (ofr_can and float(ofr_z) >= TH_OFR_VETO_Z) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        # VIX cooling: any available metric < 0
        vix_cooling: Optional[int] = None
        for x in (vix_ret1, vix_zd, vix_pd):
            if x is not None:
                vix_cooling = 1 if float(x) < 0 else 0
                break

        spx_stab: Optional[int] = None
        if spx_ret1 is not None:
            spx_stab = 1 if float(spx_ret1) >= 0 else 0

        if vix_cooling is None or spx_stab is None:
            miss = []
            if vix_cooling is None:
                miss.append("VIX(w60.ret1_pct/z_delta/p_delta)")
            if spx_stab is None:
                miss.append("SP500(w60.ret1_pct)")
            excluded.append({"trigger": "TRIG_REVERSAL", "reason": "missing_fields:" + "&".join(miss)})
            trig_rev = None
        else:
            trig_rev = 1 if (vix_cooling == 1 and spx_stab == 1) else 0

    # bottom state
    if trig_panic == 0:
        bottom_state = "NONE"
    elif trig_panic == 1:
        if trig_veto == 1:
            bottom_state = "PANIC_BUT_SYSTEMIC"
        elif trig_veto == 0:
            bottom_state = "BOTTOM_CANDIDATE" if trig_rev == 1 else "BOTTOM_WATCH"
        else:
            bottom_state = "BOTTOM_WATCH"
    else:
        bottom_state = "NA"

    # context (non-trigger)
    spx_p252 = series_out["SP500"]["w252"]["p"]
    context_equity_extreme: Optional[int] = None
    if spx_p252 is not None:
        context_equity_extreme = 1 if float(spx_p252) >= 95.0 else 0

    # distances (<=0 means triggered)
    dist_vix_panic = (TH_VIX_PANIC - float(vix_val)) if vix_val is not None else None
    dist_spx_panic = (float(spx_ret1) - TH_SPX_RET1_PANIC) if spx_ret1 is not None else None
    dist_hyg_veto = (float(hyg_z) - TH_HYG_VETO_Z) if hyg_z is not None else None
    dist_ofr_veto = (TH_OFR_VETO_Z - float(ofr_z)) if ofr_z is not None else None

    # ---------------- TW Local Gate ----------------
    tw_roll25, ok_roll25 = _load_tw_roll25(excluded)
    tw_margin, ok_margin = _load_tw_margin(excluded)

    # roll25 key fields
    tw_used_date = _as_str(tw_roll25.get("used_date") or _get(tw_roll25, ["numbers", "UsedDate"]))
    tw_run_day_tag = _as_str(
        tw_roll25.get("run_day_tag")
        or _get(tw_roll25, ["signal", "RunDayTag"])
        or tw_roll25.get("tag")
    )
    tw_used_date_status = _as_str(tw_roll25.get("used_date_status") or _get(tw_roll25, ["signal", "UsedDateStatus"]))
    tw_lookback_actual = _as_int(_get(tw_roll25, ["numbers", "LookbackNActual"]) or tw_roll25.get("lookback_n_actual"))
    tw_lookback_target = _as_int(_get(tw_roll25, ["numbers", "LookbackNTarget"]) or tw_roll25.get("lookback_n_target"))

    tw_pct_change = _as_float(_get(tw_roll25, ["numbers", "PctChange"]))
    tw_amplitude_pct = _as_float(_get(tw_roll25, ["numbers", "AmplitudePct"]))
    tw_turnover_twd = _as_float(_get(tw_roll25, ["numbers", "TradeValue"]))
    tw_close = _as_float(_get(tw_roll25, ["numbers", "Close"]))

    sig_obj = _get(tw_roll25, ["signal"])
    if not isinstance(sig_obj, dict):
        sig_obj = {}

    # numeric-aware parsing
    sig_downday = _as_bool(sig_obj.get("DownDay"))
    sig_volamp = _as_bool(sig_obj.get("VolumeAmplified"))
    sig_volamp2 = _as_bool(sig_obj.get("VolAmplified"))
    sig_newlow_n = _as_int(sig_obj.get("NewLow_N"))
    sig_consec_n = _as_int(sig_obj.get("ConsecutiveBreak"))

    stress_newlow = None if sig_newlow_n is None else (sig_newlow_n >= TH_TW_NEWLOW_STRESS_MIN)
    stress_consec = None if sig_consec_n is None else (sig_consec_n >= TH_TW_CONSEC_BREAK_STRESS)

    # TW margin (TWSE)
    tw_margin_unit = "億"
    twse_rows: List[Dict[str, Any]] = []
    twse_data_date: Optional[str] = None

    if ok_margin:
        series = tw_margin.get("series")
        if isinstance(series, dict) and isinstance(series.get("TWSE"), dict):
            twse = series["TWSE"]
            twse_data_date = _as_str(twse.get("data_date"))
            rows = twse.get("rows")
            if isinstance(rows, list):
                twse_rows = [r for r in rows if isinstance(r, dict)]
            unit_label = _get(twse, ["chg_yi_unit", "label"])
            if isinstance(unit_label, str) and unit_label.strip():
                tw_margin_unit = unit_label.strip()

    # derive margin flow + optional level gate
    margin_flow_signal: Optional[str] = None
    margin_flow_dbg: Dict[str, Any] = {}
    margin_level_gate: Optional[str] = None
    margin_level_dbg: Dict[str, Any] = {}
    margin_confidence = "OK"

    if ok_margin and twse_rows:
        margin_flow_signal, margin_flow_dbg = _derive_margin_flow_signal(twse_rows)
        margin_flow_signal = _canon_margin_signal(margin_flow_signal)

        if margin_flow_signal is None:
            excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "margin_flow_signal_NA"})

        # level gate
        margin_level_gate, margin_level_dbg = _derive_margin_level_gate(twse_rows)
        if margin_level_gate is None and TW_MARGIN_LEVEL_GATE_ENABLED:
            # downgrade but do not block signal
            margin_confidence = "DOWNGRADED"
    else:
        if ok_margin:
            excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "missing_fields:series.TWSE.rows"})
        # if ok_margin is False, already excluded by TW:INPUT_MARGIN

    # final margin signal (canonical)
    # - if flow is NA => final NA
    # - if level gate FAIL => force NONE (level not extreme, block heat)
    # - otherwise keep flow signal
    tw_margin_signal: Optional[str] = None
    if margin_flow_signal is None:
        tw_margin_signal = None
    else:
        if TW_MARGIN_LEVEL_GATE_ENABLED and margin_level_gate == "FAIL":
            tw_margin_signal = "NONE"
        else:
            tw_margin_signal = margin_flow_signal

    tw_margin_signal = _canon_margin_signal(tw_margin_signal)

    # TRIG_TW_PANIC
    trig_tw_panic: Optional[int] = None
    if not ok_roll25:
        trig_tw_panic = None
        excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_input:roll25_cache/latest_report.json"})
    else:
        need = [sig_downday, sig_volamp, sig_volamp2, stress_newlow, stress_consec]
        if any(x is None for x in need):
            excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_fields:roll25.signal.*"})
            trig_tw_panic = None
        else:
            any_stress = bool(sig_volamp or sig_volamp2 or stress_newlow or stress_consec)
            trig_tw_panic = 1 if (sig_downday and any_stress) else 0

    # TRIG_TW_LEVERAGE_HEAT
    # IMPORTANT: if margin signal is NA/None => trigger must be NA (None), not 0
    trig_tw_heat: Optional[int] = None
    if tw_margin_signal is None:
        trig_tw_heat = None
    else:
        trig_tw_heat = 1 if (tw_margin_signal in ("WATCH", "ALERT")) else 0

    # TRIG_TW_REVERSAL: PANIC & NOT heat & pct_change>=0 & DownDay=false
    trig_tw_rev: Optional[int] = None
    if trig_tw_panic != 1:
        trig_tw_rev = 0 if trig_tw_panic in (0, None) else None
    else:
        if tw_pct_change is None or sig_downday is None:
            excluded.append({"trigger": "TRIG_TW_REVERSAL", "reason": "missing_fields:pct_change or DownDay"})
            trig_tw_rev = None
        else:
            if trig_tw_heat is None:
                trig_tw_rev = 0
            else:
                trig_tw_rev = 1 if (trig_tw_heat == 0 and float(tw_pct_change) >= 0 and sig_downday is False) else 0

    # TW state
    if trig_tw_panic is None:
        tw_state = "NA"
    elif trig_tw_panic == 0:
        tw_state = "NONE"
    else:
        if trig_tw_heat == 1:
            tw_state = "PANIC_BUT_LEVERAGE_HEAT"
        elif trig_tw_heat == 0:
            tw_state = "TW_BOTTOM_CANDIDATE" if trig_tw_rev == 1 else "TW_BOTTOM_WATCH"
        else:
            tw_state = "TW_BOTTOM_WATCH"

    # TW distances / gating
    pct_change_to_nonnegative_gap: Optional[float] = None
    if tw_pct_change is not None:
        pct_change_to_nonnegative_gap = max(0.0, 0.0 - float(tw_pct_change))

    lookback_missing_points: Optional[int] = None
    if tw_lookback_actual is not None and tw_lookback_target is not None:
        lookback_missing_points = max(0, int(tw_lookback_target) - int(tw_lookback_actual))

    # latest balance display
    twse_latest_balance_yi: Optional[float] = None
    twse_latest_chg_yi: Optional[float] = None
    if twse_rows:
        rows2 = _sort_rows_newest_first(twse_rows)
        twse_latest_balance_yi = _as_float(rows2[0].get("balance_yi"))
        twse_latest_chg_yi = _as_float(rows2[0].get("chg_yi"))

    # ---- build latest.json ----
    latest_out = {
        "schema_version": "bottom_cache_v1_1",
        "generated_at_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "inputs": {
            "market_cache_stats_path": MARKET_STATS_PATH,
            "market_cache_ok": ok_market,
            "market_cache_generated_at_utc": meta["generated_at_utc"] or "NA",
            "market_cache_as_of_ts": meta["as_of_ts"] or "NA",
            "market_cache_script_version": meta["script_version"] or "NA",
            "market_cache_ret1_mode": meta["ret1_mode"] or "NA",
            "market_cache_percentile_method": meta["percentile_method"] or "NA",
            "tw_roll25_report_path": TW_ROLL25_REPORT_PATH,
            "tw_margin_path": TW_MARGIN_PATH,
        },
        "bottom_state_global": bottom_state,
        "triggers_global": {
            "TRIG_PANIC": trig_panic,
            "TRIG_SYSTEMIC_VETO": trig_veto,
            "TRIG_REVERSAL": trig_rev,
        },
        "context_global": {
            "context_equity_extreme_sp500_p252_ge_95": context_equity_extreme,
            "sp500_p252": spx_p252 if spx_p252 is not None else None,
        },
        "distances_global": {
            "vix_panic_gap": dist_vix_panic,
            "sp500_ret1_panic_gap": dist_spx_panic,
            "hyg_veto_gap_z": dist_hyg_veto,
            "ofr_veto_gap_z": dist_ofr_veto,
        },
        "tw_local_gate": {
            "tw_state": tw_state,
            "UsedDate": tw_used_date or "NA",
            "run_day_tag": tw_run_day_tag or "NA",
            "used_date_status": tw_used_date_status or "NA",
            "lookback_n_actual": tw_lookback_actual,
            "lookback_n_target": tw_lookback_target,
            "pct_change": tw_pct_change,
            "amplitude_pct": tw_amplitude_pct,
            "turnover_twd": tw_turnover_twd,
            "close": tw_close,
            "signals": {
                "DownDay": sig_downday,
                "VolumeAmplified": sig_volamp,
                "VolAmplified": sig_volamp2,
                "NewLow_N": sig_newlow_n,
                "ConsecutiveBreak": sig_consec_n,
                "stress_newlow": stress_newlow,
                "stress_consecutive_break": stress_consec,
            },
            "margin": {
                "data_date": twse_data_date,
                "unit": tw_margin_unit,
                "flow_signal": margin_flow_signal,
                "flow_dbg": margin_flow_dbg,
                "level_gate": margin_level_gate,
                "level_dbg": margin_level_dbg,
                "final_signal": tw_margin_signal,
                "confidence": margin_confidence,
                "latest_balance_yi": twse_latest_balance_yi,
                "latest_chg_yi": twse_latest_chg_yi,
            },
            "triggers": {
                "TRIG_TW_PANIC": trig_tw_panic,
                "TRIG_TW_LEVERAGE_HEAT": trig_tw_heat,
                "TRIG_TW_REVERSAL": trig_tw_rev,
            },
            "distances": {
                "pct_change_to_nonnegative_gap": pct_change_to_nonnegative_gap,
                "lookback_missing_points": lookback_missing_points,
            },
        },
        "excluded_triggers": excluded,
        "series_global": series_out,
        "notes": [
            "Global: single source = market_cache/stats_latest.json",
            "TW: uses existing repo outputs only (no external fetch here)",
            "Signals are deterministic; missing fields => NA + excluded reasons",
            "ret1_pct unit is percent (%)",
            "TW pct_change_to_nonnegative_gap is a true 'gap' (>=0)",
            "TW margin heat uses flow signal; optional level gate blocks only when enough data; otherwise downgrade",
            "Patch v0.1.2: report formatting no longer maps legitimate 'NONE' -> 'NA'; margin signal is canonicalized.",
        ],
    }

    _write_json(OUT_LATEST, latest_out)

    # ---- history.json append (overwrite same TPE day bucket) ----
    hist: Dict[str, Any] = {"schema_version": "bottom_history_v1", "items": []}
    if os.path.exists(OUT_HISTORY):
        try:
            tmp = _read_json(OUT_HISTORY)
            if isinstance(tmp, dict) and isinstance(tmp.get("items"), list):
                hist = tmp
        except Exception:
            hist = {"schema_version": "bottom_history_v1", "items": []}

    item = {
        "run_ts_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "bottom_state_global": bottom_state,
        "triggers_global": latest_out["triggers_global"],
        "context_global": latest_out["context_global"],
        "distances_global": latest_out["distances_global"],
        "tw_state": tw_state,
        "tw_triggers": latest_out["tw_local_gate"]["triggers"],
    }

    dk = _day_key_tpe_from_iso(as_of_ts_tpe)
    old_items = hist.get("items", [])
    if not isinstance(old_items, list):
        old_items = []

    new_items = [it for it in old_items if _day_key_tpe_from_iso(_as_str(it.get("as_of_ts")) or "NA") != dk]
    new_items.append(item)
    hist["items"] = new_items
    _write_json(OUT_HISTORY, hist)

    # ---- analytics on history for report.md ----
    items_sorted: List[Dict[str, Any]] = [it for it in hist.get("items", []) if isinstance(it, dict)]
    items_sorted.sort(key=lambda x: _iso_sort_key(_as_str(x.get("as_of_ts")) or "NA"))
    recent = items_sorted[-HISTORY_SHOW_N:] if items_sorted else []

    # streaks
    streak_global = 0
    for it in reversed(items_sorted):
        if (it.get("bottom_state_global") or "NA") == bottom_state:
            streak_global += 1
        else:
            break

    streak_tw = 0
    for it in reversed(items_sorted):
        if (it.get("tw_state") or "NA") == tw_state:
            streak_tw += 1
        else:
            break

    # ---- report.md ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0.1)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state (Global): **{bottom_state}**  (streak={streak_global})\n")
    md.append(f"- market_cache_as_of_ts: `{meta['as_of_ts'] or 'NA'}`\n")
    md.append(f"- market_cache_generated_at_utc: `{meta['generated_at_utc'] or 'NA'}`\n\n")

    md.append("## Rationale (Decision Chain) - Global\n")
    md.append(f"- TRIG_PANIC = `{_fmt_na(trig_panic)}`  (VIX >= {TH_VIX_PANIC} OR SP500.ret1% <= {TH_SPX_RET1_PANIC})\n")
    md.append(f"- TRIG_SYSTEMIC_VETO = `{_fmt_na(trig_veto)}`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)\n")
    md.append(f"- TRIG_REVERSAL = `{_fmt_na(trig_rev)}`  (panic & NOT systemic & VIX cooling & SP500 stable)\n\n")

    md.append("## Distance to Triggers - Global\n")
    md.append(f"- VIX panic gap: `{_safe_float_str(dist_vix_panic, 4)}`\n")
    md.append(f"- SP500 ret1% gap: `{_safe_float_str(dist_spx_panic, 4)}`\n")
    md.append(f"- HYG veto gap(z): `{_safe_float_str(dist_hyg_veto, 4)}`\n")
    md.append(f"- OFR veto gap(z): `{_safe_float_str(dist_ofr_veto, 4)}`\n\n")

    md.append("## Context (Non-trigger) - Global\n")
    md.append(f"- SP500.p252: `{_fmt_na(spx_p252)}`; equity_extreme(p252>=95): `{_fmt_na(context_equity_extreme)}`\n\n")

    md.append("## TW Local Gate (roll25 + margin)\n")
    md.append(f"- tw_state: **{tw_state}**  (streak={streak_tw})\n")
    md.append(f"- UsedDate: `{tw_used_date or 'NA'}`; run_day_tag: `{tw_run_day_tag or 'NA'}`; used_date_status: `{tw_used_date_status or 'NA'}`\n")
    md.append(f"- Lookback: `{_fmt_na(tw_lookback_actual)}/{_fmt_na(tw_lookback_target)}`\n")
    md.append(f"- margin_final_signal(TWSE): `{_fmt_na(tw_margin_signal)}`; confidence: `{margin_confidence}`; unit: `{tw_margin_unit}`\n")
    md.append(f"- margin_balance(TWSE latest): `{_safe_float_str(twse_latest_balance_yi, 1)}` {tw_margin_unit}\n")
    md.append(f"- margin_chg(TWSE latest): `{_safe_float_str(twse_latest_chg_yi, 1)}` {tw_margin_unit}\n\n")

    md.append("### TW Triggers (0/1/NA)\n")
    md.append(f"- TRIG_TW_PANIC: `{_fmt_na(trig_tw_panic)}`\n")
    md.append(f"- TRIG_TW_LEVERAGE_HEAT: `{_fmt_na(trig_tw_heat)}`\n")
    md.append(f"- TRIG_TW_REVERSAL: `{_fmt_na(trig_tw_rev)}`\n\n")

    md.append("### TW Distances / Gating\n")
    md.append(f"- pct_change_to_nonnegative_gap: `{_safe_float_str(pct_change_to_nonnegative_gap, 3)}`\n")
    md.append(f"- lookback_missing_points: `{_fmt_na(lookback_missing_points)}`\n\n")

    md.append("### TW Snapshot (key fields)\n")
    md.append(f"- pct_change: `{_fmt_na(tw_pct_change)}`; amplitude_pct: `{_fmt_na(tw_amplitude_pct)}`; turnover_twd: `{_fmt_na(tw_turnover_twd)}`; close: `{_fmt_na(tw_close)}`\n")
    md.append(f"- signals: DownDay={_fmt_na(sig_downday)}, VolumeAmplified={_fmt_na(sig_volamp)}, VolAmplified={_fmt_na(sig_volamp2)}, NewLow_N={_fmt_na(sig_newlow_n)}, ConsecutiveBreak={_fmt_na(sig_consec_n)}\n")
    md.append(f"- stress_flags: newlow={_fmt_na(stress_newlow)}, consecutive_break>={TH_TW_CONSEC_BREAK_STRESS}={_fmt_na(stress_consec)}\n\n")

    if excluded:
        md.append("## Excluded / NA Reasons\n")
        for e in excluded:
            md.append(f"- {e.get('trigger','NA')}: {e.get('reason','NA')}\n")
        md.append("\n")

    md.append("## Recent History (last 10 buckets)\n")
    if not recent:
        md.append("- NA (history empty)\n")
    else:
        md.append("| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev |\n")
        md.append("|---|---|---|---:|---:|---:|---|---:|---:|---:|\n")
        for it in recent:
            asof = _as_str(it.get("as_of_ts")) or "NA"
            dk2 = _day_key_tpe_from_iso(asof)
            st = it.get("bottom_state_global") or "NA"

            tr = it.get("triggers_global") if isinstance(it.get("triggers_global"), dict) else {}
            p = _fmt_na(tr.get("TRIG_PANIC", None))
            v = _fmt_na(tr.get("TRIG_SYSTEMIC_VETO", None))
            r = _fmt_na(tr.get("TRIG_REVERSAL", None))

            tws = it.get("tw_state") or "NA"
            twtr = it.get("tw_triggers") if isinstance(it.get("tw_triggers"), dict) else {}
            twp = _fmt_na(twtr.get("TRIG_TW_PANIC", None))
            twh = _fmt_na(twtr.get("TRIG_TW_LEVERAGE_HEAT", None))
            twr = _fmt_na(twtr.get("TRIG_TW_REVERSAL", None))

            md.append(f"| {dk2} | {asof} | {st} | {p} | {v} | {r} | {tws} | {twp} | {twh} | {twr} |\n")
        md.append("\n")

    md.append("## Series Snapshot (Global)\n")
    md.append("| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) |\n")
    md.append("|---|---|---|---|---:|---:|---:|---:|\n")
    for sid in NEEDED:
        s = series_out[sid]
        md.append(
            f"| {sid} | {s['risk_dir']} | {s['series_signal']} | {s['latest']['data_date'] or 'NA'} | "
            f"{s['latest']['value'] if s['latest']['value'] is not None else 'NA'} | "
            f"{s['w60']['z'] if s['w60']['z'] is not None else 'NA'} | "
            f"{s['w252']['p'] if s['w252']['p'] is not None else 'NA'} | "
            f"{s['w60']['ret1_pct'] if s['w60']['ret1_pct'] is not None else 'NA'} |\n"
        )

    md.append("\n## Data Sources\n")
    md.append(f"- Global (single-source): `{MARKET_STATS_PATH}`\n")
    md.append("- TW Local Gate (existing workflow outputs, no fetch):\n")
    md.append(f"  - `{TW_ROLL25_REPORT_PATH}`\n")
    md.append(f"  - `{TW_MARGIN_PATH}`\n")
    md.append("- This dashboard does not fetch external URLs directly.\n")

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()