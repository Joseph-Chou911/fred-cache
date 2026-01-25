#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottom_cache renderer (market_cache single-source) -> dashboard_bottom_cache/*

Outputs (all in ONE folder):
- dashboard_bottom_cache/latest.json
- dashboard_bottom_cache/history.json
- dashboard_bottom_cache/report.md

Design intent (v0+):
- Event-driven "bottom / reversal workflow" signal, not a daily "market state" dashboard.
- Deterministic rules only; no guessing; missing fields => NA + excluded reasons.

Upstream sources:
- Global (US): ONLY market_cache/stats_latest.json
- TW Local Gate (optional): existing workflow outputs (no new fetch)
  * roll25_cache/latest.json
  * roll25_derived/latest.json
  * taiwan_margin_financing/latest.json
  * fx_usdtwd/latest.json
  * unified_dashboard/cross_module.json  (or wherever your cross_module lives)

Policy:
- Keep Global bottom_state as-is (market_cache-based).
- Add TW Local Gate as a parallel section (does NOT change Global triggers).
- If TW sources are missing => TW triggers become NA and logged in excluded_triggers.
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

# ✅ single unified output folder
OUT_DIR = "dashboard_bottom_cache"
OUT_LATEST = f"{OUT_DIR}/latest.json"
OUT_HISTORY = f"{OUT_DIR}/history.json"
OUT_MD = f"{OUT_DIR}/report.md"

# what we need from market_cache (Global)
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

# ---- TW Local Gate inputs (existing workflow outputs; no new fetch) ----
# You may adjust these paths to match your repo.
TW_ROLL25_LATEST_PATH = "roll25_cache/latest.json"
TW_ROLL25_DERIVED_PATH = "roll25_derived/latest.json"
TW_MARGIN_LATEST_PATH = "taiwan_margin_financing/latest.json"
TW_FX_LATEST_PATH = "fx_usdtwd/latest.json"

# Cross module output path (you showed a "cross_module (Margin × Roll25 consistency)" block).
# Put the real path here. If not found, TW will still run but without LEVERAGE_HEAT.
TW_CROSS_MODULE_PATH_CANDIDATES = [
    "unified_dashboard/cross_module.json",
    "unified_dashboard/latest.json",
    "unified_risk_dashboard/cross_module.json",
    "cross_module/latest.json",
]

# TW Local Gate thresholds (v0, deterministic)
# TRIG_TW_PANIC uses roll25 boolean signals primarily. Optional pct_change check is informational.
# TRIG_TW_LEVERAGE_HEAT uses cross_module: margin_signal in {WATCH,ALERT} AND consistency=DIVERGENCE
# TRIG_TW_REVERSAL uses pct_change >= 0 and DownDay=false, but ONLY evaluated when PANIC=1 and LEVERAGE_HEAT=0
# TRIG_TW_DRAWDOWN optional and gated by confidence not DOWNGRADED. Default disabled by threshold very large.
TH_TW_DRAWDOWN_PCT = -8.0  # e.g., -8% in N window. Only used if confidence OK. You can change.


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _try_read_json(path: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Return (obj, err_reason). No exception thrown.
    """
    try:
        obj = _read_json(path)
        return obj, None
    except FileNotFoundError:
        return None, "file_not_found"
    except json.JSONDecodeError:
        return None, "json_decode_error"
    except Exception as e:
        return None, f"read_failed:{type(e).__name__}"


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
            return 1 if x else 0
        if isinstance(x, int):
            return int(x)
        if isinstance(x, float):
            return int(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        if s.lower() in ("true", "yes"):
            return 1
        if s.lower() in ("false", "no"):
            return 0
        return int(float(s))
    except Exception:
        return None


def _as_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(int(x))
    s = str(x).strip().lower()
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0"):
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


def _parse_iso_sortkey(iso: str) -> Tuple[int, str]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (int(dt.timestamp()), iso)
    except Exception:
        return (0, iso)


def _find_cross_module_obj(excluded: List[Dict[str, str]]) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Try candidate paths. Return (obj, path_used, err_reason_if_any).
    """
    last_err: Optional[str] = None
    for p in TW_CROSS_MODULE_PATH_CANDIDATES:
        obj, err = _try_read_json(p)
        if obj is None:
            last_err = err
            continue
        # If unified latest contains nested "cross_module", extract it.
        if isinstance(obj, dict) and "cross_module" in obj and isinstance(obj["cross_module"], dict):
            return obj["cross_module"], p, None
        # Or it might itself be the cross module dict.
        if isinstance(obj, dict) and ("consistency" in obj or "margin_signal" in obj):
            return obj, p, None
        # not usable
        last_err = "format_unrecognized"
    if last_err is not None:
        excluded.append({"trigger": "TW:INPUT_CROSS_MODULE", "reason": f"not_available:{last_err}"})
    else:
        excluded.append({"trigger": "TW:INPUT_CROSS_MODULE", "reason": "not_available"})
    return None, None, last_err


def _tw_local_gate(
    excluded: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Build TW Local Gate outputs from existing workflow caches.
    Does NOT alter global bottom_state. This is parallel info.
    """
    out: Dict[str, Any] = {
        "inputs": {},
        "tw_triggers": {
            "TRIG_TW_PANIC": None,
            "TRIG_TW_LEVERAGE_HEAT": None,
            "TRIG_TW_REVERSAL": None,
            "TRIG_TW_DRAWDOWN": None,
        },
        "tw_state": "NA",
        "tw_context": {},
        "tw_distances": {},
        "notes": [
            "TW Local Gate v0: uses existing workflow outputs only (no new fetch).",
            "TW triggers are parallel and do NOT change Global bottom_state.",
            "If any required TW inputs missing => trigger becomes NA and logged in excluded_triggers.",
        ],
    }

    # ---- read roll25_cache/latest.json ----
    roll25, err = _try_read_json(TW_ROLL25_LATEST_PATH)
    out["inputs"]["roll25_cache_latest_path"] = TW_ROLL25_LATEST_PATH
    out["inputs"]["roll25_cache_ok"] = (roll25 is not None and isinstance(roll25, dict))
    if roll25 is None or not isinstance(roll25, dict):
        excluded.append({"trigger": "TW:INPUT_ROLL25", "reason": f"not_available:{err or 'unknown'}"})
        roll25 = {}

    # ---- read roll25_derived/latest.json (optional) ----
    roll25d, err2 = _try_read_json(TW_ROLL25_DERIVED_PATH)
    out["inputs"]["roll25_derived_latest_path"] = TW_ROLL25_DERIVED_PATH
    out["inputs"]["roll25_derived_ok"] = (roll25d is not None and isinstance(roll25d, dict))
    if roll25d is None or not isinstance(roll25d, dict):
        # optional; no excluded unless we try to use TRIG_TW_DRAWDOWN
        roll25d = {}
        out["inputs"]["roll25_derived_err"] = err2 or "unknown"

    # ---- read margin latest (optional for context only; main trigger uses cross_module) ----
    margin, err3 = _try_read_json(TW_MARGIN_LATEST_PATH)
    out["inputs"]["taiwan_margin_financing_latest_path"] = TW_MARGIN_LATEST_PATH
    out["inputs"]["taiwan_margin_financing_ok"] = (margin is not None and isinstance(margin, dict))
    if margin is None or not isinstance(margin, dict):
        margin = {}
        out["inputs"]["taiwan_margin_financing_err"] = err3 or "unknown"

    # ---- read fx latest (optional; mostly for future expansion) ----
    fx, err4 = _try_read_json(TW_FX_LATEST_PATH)
    out["inputs"]["fx_usdtwd_latest_path"] = TW_FX_LATEST_PATH
    out["inputs"]["fx_usdtwd_ok"] = (fx is not None and isinstance(fx, dict))
    if fx is None or not isinstance(fx, dict):
        fx = {}
        out["inputs"]["fx_usdtwd_err"] = err4 or "unknown"

    # ---- cross_module (preferred for leverage heat) ----
    cross, cross_path, _ = _find_cross_module_obj(excluded)
    out["inputs"]["cross_module_path_used"] = cross_path or "NA"
    out["inputs"]["cross_module_ok"] = (cross is not None and isinstance(cross, dict))
    if cross is None or not isinstance(cross, dict):
        cross = {}

    # ---- extract key fields from roll25 ----
    used_date = _as_str(roll25.get("UsedDate") or roll25.get("used_date") or roll25.get("data_date"))
    run_day_tag = _as_str(roll25.get("run_day_tag") or roll25.get("tag") or roll25.get("tag_legacy"))
    lookback_target = _as_int(roll25.get("LookbackNTarget") or roll25.get("lookback_target"))
    lookback_actual = _as_int(roll25.get("LookbackNActual") or roll25.get("lookback_actual"))
    risk_level = _as_str(roll25.get("risk_level"))

    pct_change = _as_float(roll25.get("pct_change"))
    close_val = _as_float(roll25.get("close"))
    turnover = _as_float(roll25.get("turnover_twd") or roll25.get("turnover"))
    amplitude_pct = _as_float(roll25.get("amplitude_pct"))

    # roll25 boolean signals (these are your best v0 panic primitives)
    sigs = roll25.get("signals") if isinstance(roll25.get("signals"), dict) else {}
    down_day = _as_bool(sigs.get("DownDay"))
    vol_amp = _as_bool(sigs.get("VolumeAmplified"))
    vola_amp = _as_bool(sigs.get("VolAmplified"))
    newlow = _as_bool(sigs.get("NewLow_N"))
    consec_break = _as_bool(sigs.get("ConsecutiveBreak"))
    ohlc_missing = _as_bool(sigs.get("OhlcMissing"))

    # confidence markers
    roll25_conf = _as_str(roll25.get("confidence") or roll25.get("roll25_confidence"))
    # if not explicitly present, infer DOWNGRADED when window not full
    if roll25_conf is None and lookback_target is not None and lookback_actual is not None:
        if lookback_actual < lookback_target:
            roll25_conf = "DOWNGRADED"

    out["tw_context"].update({
        "UsedDate": used_date or "NA",
        "run_day_tag": run_day_tag or "NA",
        "risk_level": risk_level or "NA",
        "LookbackNTarget": lookback_target,
        "LookbackNActual": lookback_actual,
        "roll25_confidence": roll25_conf or "NA",
        "pct_change": pct_change,
        "close": close_val,
        "turnover_twd": turnover,
        "amplitude_pct": amplitude_pct,
        "signals": {
            "DownDay": down_day,
            "VolumeAmplified": vol_amp,
            "VolAmplified": vola_amp,
            "NewLow_N": newlow,
            "ConsecutiveBreak": consec_break,
            "OhlcMissing": ohlc_missing,
        }
    })

    # ---- TRIG_TW_PANIC ----
    # Panic requires DownDay=True AND (any stress boolean true)
    trig_tw_panic: Optional[int] = None
    # If we cannot even tell DownDay or any boolean, NA.
    bools = [vol_amp, vola_amp, newlow, consec_break]
    any_known = (down_day is not None) or any(b is not None for b in bools)
    if not any_known:
        excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_fields:roll25.signals.*"})
        trig_tw_panic = None
    else:
        if down_day is False:
            trig_tw_panic = 0
        elif down_day is True:
            any_stress = False
            for b in bools:
                if b is True:
                    any_stress = True
                    break
            trig_tw_panic = 1 if any_stress else 0
        else:
            # down_day is NA; fallback: if any stress booleans are true => treat as panic=1 else NA
            any_true = any(b is True for b in bools)
            if any_true:
                trig_tw_panic = 1
            else:
                excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_fields:DownDay"})
                trig_tw_panic = None

    out["tw_triggers"]["TRIG_TW_PANIC"] = trig_tw_panic

    # ---- TRIG_TW_LEVERAGE_HEAT ----
    # Use cross_module: margin_signal in {WATCH,ALERT} AND consistency=DIVERGENCE
    trig_tw_heat: Optional[int] = None
    margin_sig = _as_str(cross.get("margin_signal"))
    consistency = _as_str(cross.get("consistency"))
    roll25_heated = _as_bool(cross.get("roll25_heated"))
    margin_conf = _as_str(cross.get("margin_confidence"))
    roll25_conf2 = _as_str(cross.get("roll25_confidence"))

    out["tw_context"].update({
        "cross_module": {
            "margin_signal": margin_sig or "NA",
            "consistency": consistency or "NA",
            "roll25_heated": roll25_heated,
            "margin_confidence": margin_conf or "NA",
            "roll25_confidence": roll25_conf2 or "NA",
        }
    })

    if margin_sig is None or consistency is None:
        excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "missing_fields:cross_module.margin_signal&consistency"})
        trig_tw_heat = None
    else:
        hot = (margin_sig in ("WATCH", "ALERT")) and (consistency == "DIVERGENCE")
        trig_tw_heat = 1 if hot else 0

    out["tw_triggers"]["TRIG_TW_LEVERAGE_HEAT"] = trig_tw_heat

    # ---- TRIG_TW_REVERSAL ----
    # Only meaningful when panic=1 and heat=0.
    trig_tw_rev: Optional[int] = None
    if trig_tw_panic != 1:
        trig_tw_rev = 0 if trig_tw_panic == 0 else None
    elif trig_tw_heat != 0:
        # heat=1 blocks reversal confirmation; if heat NA -> NA
        trig_tw_rev = 0 if trig_tw_heat == 1 else None
    else:
        # Evaluate: pct_change>=0 AND DownDay=false
        if pct_change is None or down_day is None:
            miss = []
            if pct_change is None:
                miss.append("roll25.pct_change")
            if down_day is None:
                miss.append("roll25.signals.DownDay")
            excluded.append({"trigger": "TRIG_TW_REVERSAL", "reason": "missing_fields:" + "&".join(miss)})
            trig_tw_rev = None
        else:
            trig_tw_rev = 1 if (pct_change >= 0.0 and down_day is False) else 0

    out["tw_triggers"]["TRIG_TW_REVERSAL"] = trig_tw_rev

    # ---- TRIG_TW_DRAWDOWN (optional, gated) ----
    trig_tw_dd: Optional[int] = None
    dd_conf = _as_str(roll25d.get("confidence"))
    max_dd = _as_float(roll25d.get("max_drawdown_N_pct"))
    dd_n = _as_int(roll25d.get("dd_n"))
    dd_pts = _as_int(roll25d.get("max_drawdown_points_used"))

    out["tw_context"]["roll25_derived"] = {
        "confidence": dd_conf or "NA",
        "dd_n": dd_n,
        "max_drawdown_N_pct": max_dd,
        "max_drawdown_points_used": dd_pts,
    }

    if not roll25d:
        trig_tw_dd = None
    else:
        # If downgraded, do not use.
        if (dd_conf or "").upper() == "DOWNGRADED":
            excluded.append({"trigger": "TRIG_TW_DRAWDOWN", "reason": "gated_by_confidence:DOWNGRADED"})
            trig_tw_dd = None
        else:
            if max_dd is None:
                excluded.append({"trigger": "TRIG_TW_DRAWDOWN", "reason": "missing_fields:roll25_derived.max_drawdown_N_pct"})
                trig_tw_dd = None
            else:
                trig_tw_dd = 1 if (max_dd <= TH_TW_DRAWDOWN_PCT) else 0

    out["tw_triggers"]["TRIG_TW_DRAWDOWN"] = trig_tw_dd

    # ---- TW State ----
    # TW_NONE: panic=0
    # TW_BOTTOM_WATCH: panic=1 & heat=1
    # TW_BOTTOM_CANDIDATE: panic=1 & heat=0 & rev=0
    # TW_BOTTOM_CONFIRM: panic=1 & heat=0 & rev=1
    tw_state = "NA"
    if trig_tw_panic == 0:
        tw_state = "TW_NONE"
    elif trig_tw_panic == 1:
        if trig_tw_heat == 1:
            tw_state = "TW_BOTTOM_WATCH"
        elif trig_tw_heat == 0:
            if trig_tw_rev == 1:
                tw_state = "TW_BOTTOM_CONFIRM"
            elif trig_tw_rev == 0:
                tw_state = "TW_BOTTOM_CANDIDATE"
            else:
                tw_state = "TW_BOTTOM_CANDIDATE"
        else:
            tw_state = "TW_BOTTOM_WATCH"  # conservative if heat NA
    else:
        tw_state = "NA"

    out["tw_state"] = tw_state

    # ---- TW distances (gap-to-trigger) ----
    # Not all triggers have numeric thresholds. We can still provide simple gaps:
    # - If pct_change exists, "rev_gap" = max(0, -pct_change) for requiring >=0 (<=0 means OK)
    if pct_change is not None:
        out["tw_distances"]["pct_change_to_nonnegative_gap"] = 0.0 if pct_change >= 0 else (-pct_change)
    else:
        out["tw_distances"]["pct_change_to_nonnegative_gap"] = None

    # drawdown gap (<=0 means drawdown trigger reached)
    if max_dd is not None:
        out["tw_distances"]["drawdown_gap_pct"] = float(max_dd) - TH_TW_DRAWDOWN_PCT
    else:
        out["tw_distances"]["drawdown_gap_pct"] = None

    # window completeness gap (<=0 means ok)
    if lookback_target is not None and lookback_actual is not None:
        out["tw_distances"]["lookback_missing_points"] = float(lookback_target - lookback_actual)
    else:
        out["tw_distances"]["lookback_missing_points"] = None

    return out


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

    # ---- triggers (Global) ----
    # TRIG_PANIC: VIX >= 20 OR SP500.ret1% <= -1.5
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]  # unit %

    trig_panic: Optional[int] = None
    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and vix_val >= TH_VIX_PANIC)
        cond_spx = (spx_ret1 is not None and spx_ret1 <= TH_SPX_RET1_PANIC)
        trig_panic = 1 if (cond_vix or cond_spx) else 0

    # TRIG_SYSTEMIC_VETO: systemic stress veto via HYG_IEF_RATIO / OFR_FSI
    hyg_z = series_out["HYG_IEF_RATIO"]["w60"]["z"]
    hyg_sig = series_out["HYG_IEF_RATIO"]["series_signal"]
    ofr_z = series_out["OFR_FSI"]["w60"]["z"]
    ofr_sig = series_out["OFR_FSI"]["series_signal"]

    trig_veto: Optional[int] = None
    hyg_can = (hyg_z is not None and hyg_sig in ("WATCH", "ALERT"))
    ofr_can = (ofr_z is not None and ofr_sig in ("WATCH", "ALERT"))

    if hyg_z is None and ofr_z is None:
        excluded.append({"trigger": "TRIG_SYSTEMIC_VETO", "reason": "missing_fields:HYG_IEF_RATIO.w60.z & OFR_FSI.w60.z"})
    else:
        hyg_veto = 1 if (hyg_can and hyg_z <= TH_HYG_VETO_Z) else 0
        ofr_veto = 1 if (ofr_can and ofr_z >= TH_OFR_VETO_Z) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    # TRIG_REVERSAL: panic & NOT systemic & VIX cooling & SP500 stable
    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        # VIX cooling: any first available metric < 0
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
            trig_rev = None
        else:
            trig_rev = 1 if (vix_cooling == 1 and spx_stab == 1) else 0

    # ---- bottom_state (Global) ----
    bottom_state = "NA"
    if trig_panic == 0:
        bottom_state = "NONE"
    elif trig_panic == 1:
        if trig_veto == 1:
            bottom_state = "PANIC_BUT_SYSTEMIC"
        elif trig_veto == 0:
            bottom_state = "BOTTOM_CANDIDATE" if trig_rev == 1 else "BOTTOM_WATCH"
        else:
            bottom_state = "BOTTOM_WATCH"  # veto NA -> conservative
    else:
        bottom_state = "NA"

    # ---- context flags (non-trigger, but useful) ----
    spx_p252 = series_out["SP500"]["w252"]["p"]
    context_equity_extreme: Optional[int] = None
    if spx_p252 is None:
        context_equity_extreme = None
    else:
        context_equity_extreme = 1 if float(spx_p252) >= 95.0 else 0

    # ---- distances to trigger thresholds (<=0 means triggered) ----
    dist_vix_panic: Optional[float] = None
    if vix_val is not None:
        dist_vix_panic = TH_VIX_PANIC - float(vix_val)

    dist_spx_panic: Optional[float] = None
    if spx_ret1 is not None:
        dist_spx_panic = float(spx_ret1) - TH_SPX_RET1_PANIC  # <=0 triggers

    dist_hyg_veto: Optional[float] = None
    if hyg_z is not None:
        dist_hyg_veto = float(hyg_z) - TH_HYG_VETO_Z          # <=0 veto active (more negative)

    dist_ofr_veto: Optional[float] = None
    if ofr_z is not None:
        dist_ofr_veto = TH_OFR_VETO_Z - float(ofr_z)          # <=0 veto active (>=2)

    # ---- TW Local Gate (parallel) ----
    tw_out = _tw_local_gate(excluded)

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
            "tw_local_gate": tw_out.get("inputs", {}),
        },
        "bottom_state": bottom_state,
        "triggers": {
            "TRIG_PANIC": trig_panic,
            "TRIG_SYSTEMIC_VETO": trig_veto,
            "TRIG_REVERSAL": trig_rev,
        },
        "context": {
            "context_equity_extreme_sp500_p252_ge_95": context_equity_extreme,
            "sp500_p252": spx_p252 if spx_p252 is not None else None,
            "tw_local_gate": tw_out.get("tw_context", {}),
        },
        "distances": {
            "vix_panic_gap": dist_vix_panic,
            "sp500_ret1_panic_gap": dist_spx_panic,
            "hyg_veto_gap_z": dist_hyg_veto,
            "ofr_veto_gap_z": dist_ofr_veto,
            "tw_local_gate": tw_out.get("tw_distances", {}),
        },
        "tw_local_gate": {
            "tw_state": tw_out.get("tw_state", "NA"),
            "tw_triggers": tw_out.get("tw_triggers", {}),
        },
        "excluded_triggers": excluded,
        "series": series_out,
        "notes": [
            "Global v0: single source = market_cache/stats_latest.json",
            "TW Local Gate v0: uses existing TW workflow outputs; parallel only",
            "signal derived from w60.z and w252.p using deterministic thresholds",
            "ret1_pct unit is percent (%)",
            "context fields do NOT change triggers; they are informational only",
        ] + (tw_out.get("notes", []) if isinstance(tw_out.get("notes"), list) else []),
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
        "bottom_state": bottom_state,
        "triggers": latest_out["triggers"],
        "context": latest_out["context"],
        "distances": latest_out["distances"],
        "tw_local_gate": latest_out.get("tw_local_gate", {}),
        "series_signals": {sid: series_out[sid]["series_signal"] for sid in NEEDED},
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
    items_sorted.sort(key=lambda x: _parse_iso_sortkey(_as_str(x.get("as_of_ts")) or "NA"))

    # last N
    recent = items_sorted[-HISTORY_SHOW_N:] if len(items_sorted) > 0 else []

    # streak of current bottom_state (by distinct TPE day buckets already ensured)
    streak = 0
    cur_state = bottom_state
    for it in reversed(items_sorted):
        if (it.get("bottom_state") or "NA") == cur_state:
            streak += 1
        else:
            break

    # transitions in recent window
    transitions: List[str] = []
    prev_state: Optional[str] = None
    for it in recent:
        st = it.get("bottom_state") or "NA"
        if prev_state is None:
            prev_state = st
            continue
        if st != prev_state:
            transitions.append(f"{prev_state} → {st} @ {_as_str(it.get('as_of_ts')) or 'NA'}")
        prev_state = st

    # top-2 nearest activation distances (smaller positive means closer; <=0 already triggered)
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

    # ---- TW analytics in history ----
    # streak of TW state
    tw_state_now = (latest_out.get("tw_local_gate") or {}).get("tw_state", "NA")
    tw_streak = 0
    for it in reversed(items_sorted):
        ts = (it.get("tw_local_gate") or {}).get("tw_state", "NA")
        if ts == tw_state_now:
            tw_streak += 1
        else:
            break

    # ---- dashboard markdown ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state (Global): **{bottom_state}**  (streak={streak})\n")
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

    # ---- TW Local Gate section ----
    tw_tr = tw_out.get("tw_triggers", {}) if isinstance(tw_out.get("tw_triggers"), dict) else {}
    md.append("## TW Local Gate (roll25 + margin + cross_module)\n")
    md.append(f"- tw_state: **{tw_out.get('tw_state','NA')}**  (streak={tw_streak})\n")
    tc = tw_out.get("tw_context", {}) if isinstance(tw_out.get("tw_context"), dict) else {}
    md.append(f"- UsedDate: `{tc.get('UsedDate','NA')}`; run_day_tag: `{tc.get('run_day_tag','NA')}`; risk_level: `{tc.get('risk_level','NA')}`\n")
    md.append(f"- Lookback: `{tc.get('LookbackNActual','NA')}/{tc.get('LookbackNTarget','NA')}`; roll25_confidence: `{tc.get('roll25_confidence','NA')}`\n")
    md.append("\n### TW Triggers (0/1/NA)\n")
    md.append(f"- TRIG_TW_PANIC: `{tw_tr.get('TRIG_TW_PANIC','NA')}`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))\n")
    md.append(f"- TRIG_TW_LEVERAGE_HEAT: `{tw_tr.get('TRIG_TW_LEVERAGE_HEAT','NA')}`  (margin_signal∈{{WATCH,ALERT}} & consistency=DIVERGENCE)\n")
    md.append(f"- TRIG_TW_REVERSAL: `{tw_tr.get('TRIG_TW_REVERSAL','NA')}`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)\n")
    md.append(f"- TRIG_TW_DRAWDOWN: `{tw_tr.get('TRIG_TW_DRAWDOWN','NA')}`  (gated by roll25_derived.confidence != DOWNGRADED)\n\n")

    td = tw_out.get("tw_distances", {}) if isinstance(tw_out.get("tw_distances"), dict) else {}
    md.append("### TW Distances / Gating\n")
    md.append(f"- pct_change_to_nonnegative_gap: `{_safe_float_str(_as_float(td.get('pct_change_to_nonnegative_gap')), 4) if td.get('pct_change_to_nonnegative_gap') is not None else 'NA'}`\n")
    md.append(f"- lookback_missing_points: `{_safe_float_str(_as_float(td.get('lookback_missing_points')), 0) if td.get('lookback_missing_points') is not None else 'NA'}`\n")
    md.append(f"- drawdown_gap_pct (<=0 means reached): `{_safe_float_str(_as_float(td.get('drawdown_gap_pct')), 4) if td.get('drawdown_gap_pct') is not None else 'NA'}`\n\n")

    md.append("### TW Snapshot (key fields)\n")
    sigs = tc.get("signals", {}) if isinstance(tc.get("signals"), dict) else {}
    md.append(f"- pct_change: `{tc.get('pct_change','NA')}`; amplitude_pct: `{tc.get('amplitude_pct','NA')}`; turnover_twd: `{tc.get('turnover_twd','NA')}`; close: `{tc.get('close','NA')}`\n")
    md.append(f"- signals: DownDay={sigs.get('DownDay','NA')}, VolumeAmplified={sigs.get('VolumeAmplified','NA')}, VolAmplified={sigs.get('VolAmplified','NA')}, NewLow_N={sigs.get('NewLow_N','NA')}, ConsecutiveBreak={sigs.get('ConsecutiveBreak','NA')}\n")
    cm = tc.get("cross_module", {}) if isinstance(tc.get("cross_module"), dict) else {}
    md.append(f"- cross_module: margin_signal={cm.get('margin_signal','NA')}, consistency={cm.get('consistency','NA')}, roll25_heated={cm.get('roll25_heated','NA')}, margin_confidence={cm.get('margin_confidence','NA')}, roll25_confidence={cm.get('roll25_confidence','NA')}\n")
    rd = tc.get("roll25_derived", {}) if isinstance(tc.get("roll25_derived"), dict) else {}
    md.append(f"- roll25_derived: confidence={rd.get('confidence','NA')}, max_drawdown_N_pct={rd.get('max_drawdown_N_pct','NA')}, points_used={rd.get('max_drawdown_points_used','NA')}\n\n")

    # ---- excluded reasons ----
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
    md.append("- TW Local Gate: 若 TW_BOTTOM_CONFIRM 才允許把「台股加碼」推進到執行層；否則僅做準備\n\n")

    md.append("## Recent History (last 10 buckets)\n")
    if not recent:
        md.append("- NA (history empty)\n\n")
    else:
        md.append("| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | note |\n")
        md.append("|---|---|---|---:|---:|---:|---|---:|---:|---:|---|\n")
        for it in recent:
            asof = _as_str(it.get("as_of_ts")) or "NA"
            dk2 = _day_key_tpe_from_iso(asof)
            st = it.get("bottom_state") or "NA"
            tr = it.get("triggers") if isinstance(it.get("triggers"), dict) else {}
            p = tr.get("TRIG_PANIC", "NA")
            v = tr.get("TRIG_SYSTEMIC_VETO", "NA")
            r = tr.get("TRIG_REVERSAL", "NA")

            twg = it.get("tw_local_gate") if isinstance(it.get("tw_local_gate"), dict) else {}
            tstate = twg.get("tw_state", "NA")
            ttr = twg.get("tw_triggers") if isinstance(twg.get("tw_triggers"), dict) else {}
            tp = ttr.get("TRIG_TW_PANIC", "NA")
            th = ttr.get("TRIG_TW_LEVERAGE_HEAT", "NA")
            trv = ttr.get("TRIG_TW_REVERSAL", "NA")

            note = ""
            if isinstance(it.get("context"), dict):
                ce = it["context"].get("context_equity_extreme_sp500_p252_ge_95", None)
                if ce == 1:
                    note = "equity_extreme"
            md.append(f"| {dk2} | {asof} | {st} | {p} | {v} | {r} | {tstate} | {tp} | {th} | {trv} | {note} |\n")
        md.append("\n")

    if transitions:
        md.append("## State Transitions (within recent window)\n")
        for t in transitions:
            md.append(f"- {t}\n")
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
    md.append(f"  - `{TW_ROLL25_LATEST_PATH}`\n")
    md.append(f"  - `{TW_ROLL25_DERIVED_PATH}` (optional)\n")
    md.append(f"  - `{TW_MARGIN_LATEST_PATH}` (optional)\n")
    md.append(f"  - `{TW_FX_LATEST_PATH}` (optional)\n")
    md.append(f"  - cross_module candidates: `{', '.join(TW_CROSS_MODULE_PATH_CANDIDATES)}`\n")

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()