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

2026-02-01 patch:
- TW margin "leverage heat" upgraded to Flow + Level (水位) gate:
    (1) FLOW gate: use max(sum_last5, sum_prev5) to reduce flip-flop
    (2) LEVEL gate: require balance_yi percentile (p<=latest) >= 95 (default) using last up-to-252 points
  If LEVEL not satisfied => margin_signal = NONE (not heated)
  If LEVEL cannot be computed due to insufficient balance points => margin_signal = NA (excluded)
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
TW_MARGIN_PATH = "taiwan_margin_cache/latest.json"  # ✅ corrected path

# ✅ single unified output folder
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

# v0 thresholds (keep deterministic)
TH_VIX_PANIC = 20.0
TH_SPX_RET1_PANIC = -1.5     # unit = percent (%)
TH_HYG_VETO_Z = -2.0         # systemic credit stress veto (LOW direction)
TH_OFR_VETO_Z = 2.0          # systemic stress veto (HIGH direction)
HISTORY_SHOW_N = 10          # for report only

# TW local gate rules (v0)
# panic when DownDay AND any stress flags
TW_PANIC_REQUIRES = ["DownDay"]
TW_PANIC_ANY_OF = ["VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak"]

# ---- TW margin heat (v1 = Flow + Level) ----
# FLOW:
#   WATCH if 5-day sum chg_yi >= 100 (億) AND pos_days_last5 >= 4
#   ALERT if 5-day sum chg_yi >= 150 (億) AND pos_days_last5 >= 4
#   Use effective_sum = max(sum_last5, sum_prev5) to reduce flip-flop.
TW_MARGIN_WATCH_SUM5_YI = 100.0
TW_MARGIN_ALERT_SUM5_YI = 150.0
TW_MARGIN_POSDAYS5_MIN = 4

# LEVEL (水位):
#   Require balance_yi percentile (P = count(x<=latest)/n*100) >= 95 to allow WATCH/ALERT.
#   Compute percentile using last up-to-252 balance points (newest->older).
#   If not enough points => NA (excluded), not guessed.
TW_MARGIN_LEVEL_P_MIN = 95.0
TW_MARGIN_LEVEL_WINDOW = 252
TW_MARGIN_LEVEL_MIN_POINTS = 60


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
        if isinstance(x, bool):
            # avoid bool -> 1.0/0.0 silently for fields that should be numeric
            return float(int(x))
        if isinstance(x, (int, float)):
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
    """
    Align with your system style:
    - Extreme z: WATCH/ALERT
    - Percentile extremes: INFO
    """
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
    """
    Convert iso to TPE date key (YYYY-MM-DD). If parse fails -> "NA"
    """
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_TPE)
        return dt.date().isoformat()
    except Exception:
        return "NA"


def _safe_float_str(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    fmt = f"{{:.{nd}f}}"
    return fmt.format(x)


def _iso_sort_key(iso: str) -> Tuple[int, str]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (int(dt.timestamp()), iso)
    except Exception:
        return (0, iso)


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


def _percentile_leq(xs: List[float], latest: float) -> Optional[float]:
    """
    Deterministic percentile:
    P = count(x<=latest)/n * 100
    """
    if not xs:
        return None
    n = len(xs)
    c = sum(1 for x in xs if x <= latest)
    return (c / n) * 100.0


def _derive_margin_signal_from_rows(rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Derive margin heat signal from TWSE rows (chg_yi + balance_yi), deterministic.

    FLOW gate:
      - compute sum_last5 on rows[:5]
      - compute sum_prev5 on rows[1:6]
      - effective_sum = max(sum_last5, sum_prev5)
      - pos_days_effective = max(pos_days_last5, pos_days_prev5)

    LEVEL gate (水位):
      - compute percentile of latest balance_yi against last up-to-252 balances (newest->older)
      - require p_balance >= TW_MARGIN_LEVEL_P_MIN to allow WATCH/ALERT
      - if not enough balance points => return (None, reason)  (NA)

    Final:
      - if level_ok is False => signal = "NONE"
      - if level_ok is True => apply WATCH/ALERT thresholds on effective_sum + pos_days_effective
    """
    if not isinstance(rows, list) or len(rows) == 0:
        return (None, {"reason": "rows_empty_or_invalid"})

    if len(rows) < 6:
        return (None, {"reason": "need_at_least_6_rows_for_prev_window", "rows_len": len(rows)})

    def _window_stats(win: List[Dict[str, Any]]) -> Tuple[List[float], float, int]:
        chgs: List[float] = []
        for r in win:
            v = _as_float(r.get("chg_yi"))
            if v is None:
                continue
            chgs.append(v)
        if not chgs:
            return ([], 0.0, 0)
        s = float(sum(chgs))
        posd = sum(1 for x in chgs if x > 0)
        return (chgs, s, posd)

    # FLOW: two windows (reduce flip-flop)
    w0 = rows[:5]
    w1 = rows[1:6]

    chg0, sum0, pos0 = _window_stats(w0)
    chg1, sum1, pos1 = _window_stats(w1)

    # keep the same minimum flow points constraint as your original spirit
    if len(chg0) < 3:
        return (None, {"reason": "insufficient_chg_yi_points_last5", "points": len(chg0)})
    if len(chg1) < 3:
        return (None, {"reason": "insufficient_chg_yi_points_prev5", "points": len(chg1)})

    sum_eff = max(sum0, sum1)
    pos_eff = max(pos0, pos1)

    # LEVEL: balance percentile
    balances_all: List[float] = []
    for r in rows:
        b = _as_float(r.get("balance_yi"))
        if b is None:
            continue
        balances_all.append(b)

    if len(balances_all) < TW_MARGIN_LEVEL_MIN_POINTS:
        return (None, {
            "reason": "insufficient_balance_points_for_level_gate",
            "points": len(balances_all),
            "min_points": TW_MARGIN_LEVEL_MIN_POINTS
        })

    latest_balance = balances_all[0]
    bal_win_n = min(TW_MARGIN_LEVEL_WINDOW, len(balances_all))
    bal_window = balances_all[:bal_win_n]
    bal_p = _percentile_leq(bal_window, latest_balance)

    if bal_p is None:
        return (None, {"reason": "balance_percentile_compute_failed"})

    level_ok = True if float(bal_p) >= float(TW_MARGIN_LEVEL_P_MIN) else False

    # Final
    sig = "NONE"
    if level_ok:
        if pos_eff >= TW_MARGIN_POSDAYS5_MIN and sum_eff >= TW_MARGIN_ALERT_SUM5_YI:
            sig = "ALERT"
        elif pos_eff >= TW_MARGIN_POSDAYS5_MIN and sum_eff >= TW_MARGIN_WATCH_SUM5_YI:
            sig = "WATCH"
        else:
            sig = "NONE"
    else:
        sig = "NONE"

    dbg = {
        "flow": {
            "chg_last5_yi": chg0,
            "sum_last5_yi": sum0,
            "pos_days_last5": pos0,
            "chg_prev5_yi": chg1,
            "sum_prev5_yi": sum1,
            "pos_days_prev5": pos1,
            "sum5_effective_yi": sum_eff,
            "pos5_effective": pos_eff,
            "rule_flow": (
                f"effective_sum=max(sum_last5,sum_prev5); "
                f"WATCH(sum>={TW_MARGIN_WATCH_SUM5_YI} & pos>={TW_MARGIN_POSDAYS5_MIN}); "
                f"ALERT(sum>={TW_MARGIN_ALERT_SUM5_YI} & pos>={TW_MARGIN_POSDAYS5_MIN})"
            ),
        },
        "level": {
            "latest_balance_yi": latest_balance,
            "balance_window_n": bal_win_n,
            "percentile_method": "P=count(x<=latest)/n*100",
            "balance_p": float(bal_p),
            "level_p_min": float(TW_MARGIN_LEVEL_P_MIN),
            "level_ok": level_ok,
            "rule_level": f"require balance_p >= {TW_MARGIN_LEVEL_P_MIN} (window<= {TW_MARGIN_LEVEL_WINDOW}, min_points={TW_MARGIN_LEVEL_MIN_POINTS})",
        },
        "final_rule": "heat = (level_ok) AND (flow triggers WATCH/ALERT); else NONE; insufficient level data => NA"
    }
    return (sig, dbg)


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
                "ret1_pct": _as_float(w60.get("ret1_pct")),   # unit = %
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
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]  # unit %

    trig_panic: Optional[int] = None
    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and vix_val >= TH_VIX_PANIC)
        cond_spx = (spx_ret1 is not None and spx_ret1 <= TH_SPX_RET1_PANIC)
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
        hyg_veto = 1 if (hyg_can and hyg_z is not None and hyg_z <= TH_HYG_VETO_Z) else 0
        ofr_veto = 1 if (ofr_can and ofr_z is not None and ofr_z >= TH_OFR_VETO_Z) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        vix_cooling: Optional[int] = None
        for x in (vix_ret1, vix_zd, vix_pd):
            if x is not None:
                vix_cooling = 1 if x < 0 else 0
                break

        spx_stab: Optional[int] = None
        if spx_ret1 is not None:
            spx_stab = 1 if spx_ret1 >= 0 else 0

        if vix_cooling is None or spx_stab is None:
            miss = []
            if vix_cooling is None:
                miss.append("VIX(w60.ret1_pct/z_delta/p_delta)")
            if spx_stab is None:
                miss.append("SP500(w60.ret1_pct)")
            excluded.append({"trigger": "TRIG_REVERSAL", "reason": "missing_fields:" + "&".join(miss)})
        else:
            trig_rev = 1 if (vix_cooling == 1 and spx_stab == 1) else 0

    bottom_state = "NA"
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

    # ---- context flags (non-trigger) ----
    spx_p252 = series_out["SP500"]["w252"]["p"]
    context_equity_extreme: Optional[int] = None
    if spx_p252 is None:
        context_equity_extreme = None
    else:
        context_equity_extreme = 1 if float(spx_p252) >= 95.0 else 0

    # ---- distances (<=0 means triggered) ----
    dist_vix_panic: Optional[float] = TH_VIX_PANIC - float(vix_val) if vix_val is not None else None
    dist_spx_panic: Optional[float] = float(spx_ret1) - TH_SPX_RET1_PANIC if spx_ret1 is not None else None
    dist_hyg_veto: Optional[float] = float(hyg_z) - TH_HYG_VETO_Z if hyg_z is not None else None
    dist_ofr_veto: Optional[float] = TH_OFR_VETO_Z - float(ofr_z) if ofr_z is not None else None

    # ---------------- TW Local Gate ----------------
    tw_roll25, ok_roll25 = _load_tw_roll25(excluded)
    tw_margin, ok_margin = _load_tw_margin(excluded)

    # roll25 fields from latest_report.json
    tw_used_date = _as_str(tw_roll25.get("used_date") or _get(tw_roll25, ["numbers", "UsedDate"]))
    # run_day_tag may be stored as "tag" or "run_day_tag"; keep deterministic fallback
    tw_tag = _as_str(tw_roll25.get("tag") or tw_roll25.get("run_day_tag"))
    tw_risk_level = _as_str(tw_roll25.get("risk_level"))
    tw_lookback_actual = _as_int(tw_roll25.get("lookback_n_actual") or _get(tw_roll25, ["numbers", "LookbackNActual"]) or _get(tw_roll25, ["signal", "LookbackNActual"]))
    tw_lookback_target = _as_int(tw_roll25.get("lookback_n_target") or _get(tw_roll25, ["numbers", "LookbackNTarget"]) or _get(tw_roll25, ["signal", "LookbackNTarget"]))

    tw_pct_change = _as_float(_get(tw_roll25, ["numbers", "PctChange"]))
    tw_amplitude_pct = _as_float(_get(tw_roll25, ["numbers", "AmplitudePct"]))
    tw_turnover_twd = _as_float(_get(tw_roll25, ["numbers", "TradeValue"]))
    tw_close = _as_float(_get(tw_roll25, ["numbers", "Close"]))

    sig_obj = _get(tw_roll25, ["signal"])
    if not isinstance(sig_obj, dict):
        sig_obj = {}

    sig_downday = _as_bool(sig_obj.get("DownDay"))
    sig_volamp = _as_bool(sig_obj.get("VolumeAmplified"))
    sig_volamp2 = _as_bool(sig_obj.get("VolAmplified"))
    sig_newlow = _as_bool(sig_obj.get("NewLow_N"))
    sig_consec = _as_bool(sig_obj.get("ConsecutiveBreak"))

    # TW margin derive (TWSE)
    tw_margin_signal: Optional[str] = None
    tw_margin_dbg: Dict[str, Any] = {}
    tw_margin_unit = "億"  # ✅ display unit for margin numbers

    twse_rows: List[Dict[str, Any]] = []
    if ok_margin:
        # accept schema:
        # - { "series": { "TWSE": { "rows": [...] , "chg_yi_unit": {...}}}}
        series = tw_margin.get("series")
        if isinstance(series, dict) and isinstance(series.get("TWSE"), dict):
            twse = series["TWSE"]
            rows = twse.get("rows")
            if isinstance(rows, list):
                twse_rows = [r for r in rows if isinstance(r, dict)]
            # unit label if exists
            unit_label = _get(twse, ["chg_yi_unit", "label"])
            if isinstance(unit_label, str) and unit_label.strip():
                tw_margin_unit = unit_label.strip()

    if ok_margin and twse_rows:
        tw_margin_signal, tw_margin_dbg = _derive_margin_signal_from_rows(twse_rows)
        if tw_margin_signal is None:
            # level gate NA or flow insufficient -> excluded
            excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "margin_signal_NA:insufficient_flow_or_level_data"})
    else:
        if ok_margin:
            excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "missing_fields:series.TWSE.rows[].chg_yi/balance_yi"})
        else:
            # already excluded by TW:INPUT_MARGIN
            pass

    # TRIG_TW_PANIC
    trig_tw_panic: Optional[int] = None
    if not ok_roll25:
        trig_tw_panic = None
        excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_input:roll25_cache/latest_report.json"})
    else:
        # require DownDay + any_of stress flags
        if sig_downday is None or any(x is None for x in [sig_volamp, sig_volamp2, sig_newlow, sig_consec]):
            excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_fields:roll25.signal.*"})
            trig_tw_panic = None
        else:
            any_stress = bool(sig_volamp or sig_volamp2 or sig_newlow or sig_consec)
            trig_tw_panic = 1 if (sig_downday and any_stress) else 0

    # TRIG_TW_LEVERAGE_HEAT
    trig_tw_heat: Optional[int] = None
    if tw_margin_signal is None:
        trig_tw_heat = None
        # excluded reason already appended above
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
            # if heat is NA, conservative: do not confirm reversal
            if trig_tw_heat is None:
                trig_tw_rev = 0
            else:
                trig_tw_rev = 1 if (trig_tw_heat == 0 and tw_pct_change >= 0 and sig_downday is False) else 0

    # TW state machine (simple v0)
    tw_state = "NA"
    if trig_tw_panic is None:
        tw_state = "NA"
    elif trig_tw_panic == 0:
        tw_state = "NONE"
    else:
        # panic == 1
        if trig_tw_heat == 1:
            tw_state = "PANIC_BUT_LEVERAGE_HEAT"
        elif trig_tw_heat == 0:
            tw_state = "TW_BOTTOM_CANDIDATE" if trig_tw_rev == 1 else "TW_BOTTOM_WATCH"
        else:
            tw_state = "TW_BOTTOM_WATCH"  # heat NA -> conservative

    # TW distances
    pct_change_gap_nonneg: Optional[float] = None
    if tw_pct_change is not None:
        pct_change_gap_nonneg = float(tw_pct_change)

    lookback_missing_points: Optional[int] = None
    if tw_lookback_actual is not None:
        if tw_lookback_target is None:
            lookback_missing_points = None
        else:
            lookback_missing_points = max(0, int(tw_lookback_target) - int(tw_lookback_actual))

    # ---- build latest.json ----
    latest_out = {
        "schema_version": "bottom_cache_v1",
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
            "run_day_tag": tw_tag or "NA",
            "risk_level": tw_risk_level or "NA",
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
                "NewLow_N": sig_newlow,
                "ConsecutiveBreak": sig_consec,
            },
            "margin": {
                "margin_signal_TWSE": tw_margin_signal,
                "unit": tw_margin_unit,
                "dbg": tw_margin_dbg,
                "policy": {
                    "flow_two_windows": True,
                    "level_gate_enabled": True,
                    "level_p_min": TW_MARGIN_LEVEL_P_MIN,
                    "level_window": TW_MARGIN_LEVEL_WINDOW,
                    "level_min_points": TW_MARGIN_LEVEL_MIN_POINTS,
                }
            },
            "triggers": {
                "TRIG_TW_PANIC": trig_tw_panic,
                "TRIG_TW_LEVERAGE_HEAT": trig_tw_heat,
                "TRIG_TW_REVERSAL": trig_tw_rev,
            },
            "distances": {
                "pct_change_to_nonnegative_gap": pct_change_gap_nonneg,
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
            "TW margin heat: Flow + Level (balance percentile gate) to reduce false heat & flip-flop",
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

    # nearest global distances
    dist_map = {
        "VIX panic gap (<=0 triggered)": dist_vix_panic,
        "SP500 ret1% gap (<=0 triggered)": dist_spx_panic,
        "HYG veto gap z (<=0 veto)": dist_hyg_veto,
        "OFR veto gap z (<=0 veto)": dist_ofr_veto,
    }

    def _dist_rank_val(x: Optional[float]) -> float:
        if x is None:
            return float("inf")
        return -1e9 if x <= 0 else x

    dist_sorted = sorted(dist_map.items(), key=lambda kv: _dist_rank_val(kv[1]))
    top2 = dist_sorted[:2]

    # margin balance display (latest TWSE balance) with unit "億"
    twse_latest_balance_yi: Optional[float] = None
    twse_latest_chg_yi: Optional[float] = None
    if twse_rows:
        twse_latest_balance_yi = _as_float(twse_rows[0].get("balance_yi"))
        twse_latest_chg_yi = _as_float(twse_rows[0].get("chg_yi"))

    # ---- report.md ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state (Global): **{bottom_state}**  (streak={streak_global})\n")
    md.append(f"- market_cache_as_of_ts: `{meta['as_of_ts'] or 'NA'}`\n")
    md.append(f"- market_cache_generated_at_utc: `{meta['generated_at_utc'] or 'NA'}`\n\n")

    md.append("## Rationale (Decision Chain) - Global\n")
    md.append(f"- TRIG_PANIC = `{trig_panic}`  (VIX >= {TH_VIX_PANIC} OR SP500.ret1% <= {TH_SPX_RET1_PANIC})\n")
    md.append(f"- TRIG_SYSTEMIC_VETO = `{trig_veto}`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)\n")
    md.append(f"- TRIG_REVERSAL = `{trig_rev}`  (panic & NOT systemic & VIX cooling & SP500 stable)\n")
    if trig_panic == 0:
        md.append("- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）\n")
    elif trig_panic == 1 and trig_veto == 1:
        md.append("- 已觸發恐慌，但出現系統性 veto → 不抄底（先等信用/壓力解除）\n")
    elif trig_panic == 1 and trig_veto == 0 and trig_rev == 0:
        md.append("- 恐慌成立且無系統性 veto，但尚未看到反轉確認 → BOTTOM_WATCH\n")
    elif trig_panic == 1 and trig_veto == 0 and trig_rev == 1:
        md.append("- 恐慌成立且無系統性 veto，且反轉確認成立 → BOTTOM_CANDIDATE\n")
    md.append("\n")

    md.append("## Distance to Triggers (How far from activation) - Global\n")
    if dist_vix_panic is not None and vix_val is not None:
        md.append(f"- VIX panic gap = {TH_VIX_PANIC} - {vix_val} = **{_safe_float_str(dist_vix_panic, 4)}**  (<=0 means triggered)\n")
    else:
        md.append("- VIX panic gap = NA (missing VIX.latest.value)\n")

    if dist_spx_panic is not None and spx_ret1 is not None:
        md.append(f"- SP500 ret1% gap = {spx_ret1} - ({TH_SPX_RET1_PANIC}) = **{_safe_float_str(dist_spx_panic, 4)}**  (<=0 means triggered)\n")
    else:
        md.append("- SP500 ret1% gap = NA (missing SP500.w60.ret1_pct)\n")

    if dist_hyg_veto is not None and hyg_z is not None:
        md.append(f"- HYG veto gap (z) = {hyg_z} - ({TH_HYG_VETO_Z}) = **{_safe_float_str(dist_hyg_veto, 4)}**  (<=0 means systemic veto)\n")
    else:
        md.append("- HYG veto gap (z) = NA (missing HYG_IEF_RATIO.w60.z)\n")

    if dist_ofr_veto is not None and ofr_z is not None:
        md.append(f"- OFR veto gap (z) = ({TH_OFR_VETO_Z}) - {ofr_z} = **{_safe_float_str(dist_ofr_veto, 4)}**  (<=0 means systemic veto)\n")
    else:
        md.append("- OFR veto gap (z) = NA (missing OFR_FSI.w60.z)\n")

    md.append("\n### Nearest Conditions (Top-2) - Global\n")
    for name, val in top2:
        md.append(f"- {name}: `{_safe_float_str(val, 4)}`\n")
    md.append("\n")

    md.append("## Context (Non-trigger) - Global\n")
    if context_equity_extreme is None:
        md.append("- SP500.p252: NA → cannot evaluate equity extreme context\n")
    else:
        md.append(f"- SP500.p252 = `{_safe_float_str(float(spx_p252), 4) if spx_p252 is not None else 'NA'}`; equity_extreme(p252>=95) = `{context_equity_extreme}`\n")
        if context_equity_extreme == 1:
            md.append("- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）\n")
    md.append("\n")

    md.append("## Triggers (0/1/NA) - Global\n")
    md.append(f"- TRIG_PANIC: `{trig_panic}`\n")
    md.append(f"- TRIG_SYSTEMIC_VETO: `{trig_veto}`\n")
    md.append(f"- TRIG_REVERSAL: `{trig_rev}`\n\n")

    # ---- TW section ----
    md.append("## TW Local Gate (roll25 + margin)\n")
    md.append(f"- tw_state: **{tw_state}**  (streak={streak_tw})\n")
    md.append(f"- UsedDate: `{tw_used_date or 'NA'}`; run_day_tag: `{tw_tag or 'NA'}`; risk_level: `{tw_risk_level or 'NA'}`\n")
    md.append(f"- Lookback: `{tw_lookback_actual}/{tw_lookback_target}`\n")
    md.append(f"- margin_signal(TWSE): `{tw_margin_signal}`; unit: `{tw_margin_unit}`\n")
    md.append(f"- margin_policy: flow_two_windows=True; level_gate=True; level_p_min={TW_MARGIN_LEVEL_P_MIN}\n")
    if twse_latest_balance_yi is not None:
        md.append(f"- margin_balance(TWSE latest): `{_safe_float_str(twse_latest_balance_yi, 1)}` {tw_margin_unit}\n")
    else:
        md.append(f"- margin_balance(TWSE latest): `NA` {tw_margin_unit}\n")
    if twse_latest_chg_yi is not None:
        md.append(f"- margin_chg(TWSE latest): `{_safe_float_str(twse_latest_chg_yi, 1)}` {tw_margin_unit}\n")
    else:
        md.append(f"- margin_chg(TWSE latest): `NA` {tw_margin_unit}\n")
    md.append("\n")

    md.append("### TW Triggers (0/1/NA)\n")
    md.append(f"- TRIG_TW_PANIC: `{trig_tw_panic}`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))\n")
    md.append(f"- TRIG_TW_LEVERAGE_HEAT: `{trig_tw_heat}`  (margin_signal∈{{WATCH,ALERT}}; requires Flow+Level)\n")
    md.append(f"- TRIG_TW_REVERSAL: `{trig_tw_rev}`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)\n\n")

    md.append("### TW Distances / Gating\n")
    md.append(f"- pct_change_to_nonnegative_gap: `{_safe_float_str(pct_change_gap_nonneg, 3) if pct_change_gap_nonneg is not None else 'NA'}`\n")
    md.append(f"- lookback_missing_points: `{lookback_missing_points if lookback_missing_points is not None else 'NA'}`\n\n")

    md.append("### TW Snapshot (key fields)\n")
    md.append(
        f"- pct_change: `{tw_pct_change}`; amplitude_pct: `{tw_amplitude_pct}`; "
        f"turnover_twd: `{tw_turnover_twd}`; close: `{tw_close}`\n"
    )
    md.append(
        f"- signals: DownDay={sig_downday}, VolumeAmplified={sig_volamp}, VolAmplified={sig_volamp2}, "
        f"NewLow_N={sig_newlow}, ConsecutiveBreak={sig_consec}\n\n"
    )

    if excluded:
        md.append("## Excluded / NA Reasons\n")
        for e in excluded:
            md.append(f"- {e.get('trigger','NA')}: {e.get('reason','NA')}\n")
        md.append("\n")

    md.append("## Action Map (v0)\n")
    md.append("- Global NONE: 維持既定 DCA/資產配置紀律；不把它當成抄底時點訊號\n")
    md.append("- Global BOTTOM_WATCH: 只做準備（現金/分批計畫/撤退條件），不進場\n")
    md.append("- Global BOTTOM_CANDIDATE: 允許分批（例如 2–3 段），但需設定撤退條件\n")
    md.append("- Global PANIC_BUT_SYSTEMIC: 不抄底，先等信用/壓力解除\n")
    md.append("- TW Local Gate: 若 TW_BOTTOM_CANDIDATE 才允許把「台股加碼」推進到執行層；否則僅做準備\n\n")

    md.append("## Recent History (last 10 buckets)\n")
    if not recent:
        md.append("- NA (history empty)\n\n")
    else:
        md.append("| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | note |\n")
        md.append("|---|---|---|---:|---:|---:|---|---:|---:|---:|---|\n")
        for it in recent:
            asof = _as_str(it.get("as_of_ts")) or "NA"
            dk2 = _day_key_tpe_from_iso(asof)
            st = it.get("bottom_state_global") or "NA"
            tr = it.get("triggers_global") if isinstance(it.get("triggers_global"), dict) else {}
            p = tr.get("TRIG_PANIC", "NA")
            v = tr.get("TRIG_SYSTEMIC_VETO", "NA")
            r = tr.get("TRIG_REVERSAL", "NA")
            tws = it.get("tw_state") or "NA"
            twtr = it.get("tw_triggers") if isinstance(it.get("tw_triggers"), dict) else {}
            twp = twtr.get("TRIG_TW_PANIC", "NA")
            twh = twtr.get("TRIG_TW_LEVERAGE_HEAT", "NA")
            twr = twtr.get("TRIG_TW_REVERSAL", "NA")
            note = ""
            ce = (it.get("context_global") or {}).get("context_equity_extreme_sp500_p252_ge_95", None)
            if ce == 1:
                note = "equity_extreme"
            md.append(f"| {dk2} | {asof} | {st} | {p} | {v} | {r} | {tws} | {twp} | {twh} | {twr} | {note} |\n")
        md.append("\n")

    md.append("## Series Snapshot (Global)\n")
    md.append("| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |\n")
    md.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|\n")
    for sid in NEEDED:
        s = series_out[sid]
        md.append(
            f"| {sid} | {s['risk_dir']} | {s['series_signal']} | {s['latest']['data_date'] or 'NA'} | "
            f"{s['latest']['value'] if s['latest']['value'] is not None else 'NA'} | "
            f"{s['w60']['z'] if s['w60']['z'] is not None else 'NA'} | "
            f"{s['w252']['p'] if s['w252']['p'] is not None else 'NA'} | "
            f"{s['w60']['ret1_pct'] if s['w60']['ret1_pct'] is not None else 'NA'} | "
            f"{s['w60']['z_delta'] if s['w60']['z_delta'] is not None else 'NA'} | "
            f"{s['w60']['p_delta'] if s['w60']['p_delta'] is not None else 'NA'} |\n"
        )

    md.append("\n## Data Sources\n")
    md.append(f"- Global (single-source): `{MARKET_STATS_PATH}`\n")
    md.append("- TW Local Gate (existing workflow outputs, no fetch):\n")
    md.append(f"  - `{TW_ROLL25_REPORT_PATH}`\n")
    md.append(f"  - `{TW_MARGIN_PATH}`  (unit: 億)\n")
    md.append("- This dashboard does not fetch external URLs directly.\n")

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()