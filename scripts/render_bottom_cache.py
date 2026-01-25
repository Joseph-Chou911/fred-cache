#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottom_cache renderer (global market_cache + TW local gate) -> dashboard_bottom_cache/*

Outputs (all in ONE folder):
- dashboard_bottom_cache/latest.json
- dashboard_bottom_cache/history.json
- dashboard_bottom_cache/report.md

Design intent:
- Global: Event-driven "bottom / reversal workflow" signal (NOT a daily market-state dashboard).
- TW: Use existing workflow outputs (no external fetch here) as a *local gate* for Taiwan bottoming.
- Deterministic rules only; no guessing; missing fields => NA + excluded reasons.

Upstream inputs:
- Global (single-source): market_cache/stats_latest.json
- TW local gate (existing outputs):
  - roll25_cache/latest_report.json (preferred)
  - taiwan_margin_financing/latest.json (preferred)
  - (optional) fx_usdtwd/latest.json (not required in v0)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo

TZ_TPE = ZoneInfo("Asia/Taipei")

# =========================
# Config
# =========================
MARKET_STATS_PATH = "market_cache/stats_latest.json"

# ✅ single unified output folder
OUT_DIR = "dashboard_bottom_cache"
OUT_LATEST = f"{OUT_DIR}/latest.json"
OUT_HISTORY = f"{OUT_DIR}/history.json"
OUT_MD = f"{OUT_DIR}/report.md"

# Global series we need from market_cache
NEEDED = ["VIX", "SP500", "HYG_IEF_RATIO", "OFR_FSI"]

# risk direction is a RULE (not guessed)
RISK_DIR = {
    "VIX": "HIGH",
    "OFR_FSI": "HIGH",
    "HYG_IEF_RATIO": "LOW",
    "SP500": "LOW",
}

# Global v0 thresholds (deterministic)
TH_VIX_PANIC = 20.0
TH_SPX_RET1_PANIC = -1.5     # unit = percent (%)
TH_HYG_VETO_Z = -2.0         # systemic credit stress veto (LOW direction)
TH_OFR_VETO_Z = 2.0          # systemic stress veto (HIGH direction)
HISTORY_SHOW_N = 10          # for report only

# TW inputs (existing workflow outputs)
ROLL25_REPORT_PATH = "roll25_cache/latest_report.json"
TW_MARGIN_PATH = "taiwan_margin_financing/latest.json"

# TW v0 gate thresholds (deterministic)
# Panic trigger via roll25 signals
# - TRIG_TW_PANIC = DownDay AND (VolumeAmplified OR VolAmplified OR NewLow_N OR ConsecutiveBreak)
# Leverage heat derived from margin rows (since no cross_module file exists)
# - Derive margin_signal from TWSE last5 chg_yi (unit: 億)
# - Heat if margin_signal in {WATCH, ALERT}
# Reversal trigger:
# - PANIC & NOT heat & pct_change>=0 & DownDay=false
# Drawdown gate:
# - disabled in this repo (no roll25_derived file); kept as NA with reason

# Margin signal derivation thresholds (unit: 億)
TH_MARGIN_INFO_SUM5 = 80.0
TH_MARGIN_WATCH_SUM5 = 120.0
TH_MARGIN_ALERT_SUM5 = 200.0
TH_MARGIN_WATCH_POS5_SUM5 = 100.0   # pos_days>=4 and sum>=100 -> WATCH
TH_MARGIN_ALERT_POS5_SUM5 = 150.0   # pos_days>=5 and sum>=150 -> ALERT


# =========================
# Utils
# =========================
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
            if x != x:
                return None
            return int(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        if s.lower() in ("true", "false"):
            return 1 if s.lower() == "true" else 0
        return int(float(s))
    except Exception:
        return None


def _as_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
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


def _exists_read_json(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not os.path.exists(path):
            return None, "file_not_found"
        obj = _read_json(path)
        if not isinstance(obj, dict):
            return None, "not_a_dict"
        return obj, None
    except Exception as e:
        return None, f"read_or_parse_failed:{type(e).__name__}"


# =========================
# TW: roll25 parsing
# =========================
def _extract_roll25_fields(roll: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse roll25_cache/latest_report.json

    Expected:
      - numbers: UsedDate, Close, PctChange, TradeValue, VolumeMultiplier, AmplitudePct, VolMultiplier
      - signal: DownDay, VolumeAmplified, VolAmplified, NewLow_N, ConsecutiveBreak, OhlcMissing
      - lookback_n_actual, LookbackNTarget (may be in caveats text, but latest_report.json provides lookback_n_actual)
    """
    notes: List[str] = []
    out: Dict[str, Any] = {}

    numbers = roll.get("numbers") if isinstance(roll.get("numbers"), dict) else {}
    signal = roll.get("signal") if isinstance(roll.get("signal"), dict) else {}

    out["UsedDate"] = _as_str(numbers.get("UsedDate"))
    out["run_day_tag"] = _as_str(roll.get("tag"))
    out["risk_level"] = _as_str(roll.get("risk_level"))
    out["turnover_twd"] = _as_float(numbers.get("TradeValue"))
    out["close"] = _as_float(numbers.get("Close"))
    out["pct_change"] = _as_float(numbers.get("PctChange"))
    out["amplitude_pct"] = _as_float(numbers.get("AmplitudePct"))
    out["volume_multiplier"] = _as_float(numbers.get("VolumeMultiplier"))
    out["vol_multiplier"] = _as_float(numbers.get("VolMultiplier"))

    # lookback
    out["lookback_n_actual"] = _as_int(roll.get("lookback_n_actual"))
    # Some historical versions used LookbackNTarget; keep best-effort
    out["lookback_n_target"] = _as_int(roll.get("LookbackNTarget")) or None

    # signals
    out["signals"] = {
        "DownDay": _as_bool(signal.get("DownDay")),
        "VolumeAmplified": _as_bool(signal.get("VolumeAmplified")),
        "VolAmplified": _as_bool(signal.get("VolAmplified")),
        "NewLow_N": _as_bool(signal.get("NewLow_N")),
        "ConsecutiveBreak": _as_bool(signal.get("ConsecutiveBreak")),
        "OhlcMissing": _as_bool(signal.get("OhlcMissing")),
    }

    # validation notes
    if out["UsedDate"] is None:
        notes.append("missing numbers.UsedDate")
    if out["pct_change"] is None:
        notes.append("missing numbers.PctChange")
    if out["signals"]["DownDay"] is None:
        notes.append("missing signal.DownDay")

    return out, notes


# =========================
# TW: margin signal derivation (unit: 億)
# =========================
def _derive_margin_signal_from_rows(rows: Any) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Derive a simple margin_signal from rows (list of {date, chg_yi, balance_yi}).
    Unit of chg_yi and balance_yi is 億 (based on your schema).

    Need last5 valid chg_yi numbers, else NA.

    Compute:
      last5 = first 5 rows chg_yi (assuming rows are latest->older)
      sum_last5
      pos_days_last5
      latest_chg = last5[0]

    Signal:
      ALERT if (sum_last5 >= 200) OR (pos_days_last5 >= 5 and sum_last5 >= 150)
      WATCH if (sum_last5 >= 120) OR (pos_days_last5 >= 4 and sum_last5 >= 100)
      INFO  if (sum_last5 >= 80)
      NONE otherwise
    """
    dbg: Dict[str, Any] = {
        "unit": "億",
        "chg_last5_yi": None,
        "sum_last5_yi": None,
        "pos_days_last5": None,
        "latest_chg_yi": None,
        "rule": "v0(sum_last5/pos_days)",
        "thresholds_yi": {
            "INFO_sum_last5": TH_MARGIN_INFO_SUM5,
            "WATCH_sum_last5": TH_MARGIN_WATCH_SUM5,
            "ALERT_sum_last5": TH_MARGIN_ALERT_SUM5,
            "WATCH_pos>=4_sum>=100": TH_MARGIN_WATCH_POS5_SUM5,
            "ALERT_pos>=5_sum>=150": TH_MARGIN_ALERT_POS5_SUM5,
        },
    }

    if not isinstance(rows, list) or len(rows) < 5:
        return None, dbg

    last5: List[float] = []
    for i in range(5):
        r = rows[i]
        if not isinstance(r, dict):
            return None, dbg
        chg = _as_float(r.get("chg_yi"))
        if chg is None:
            return None, dbg
        last5.append(float(chg))

    s5 = sum(last5)
    pos = sum(1 for x in last5 if x > 0)
    latest = last5[0]

    dbg["chg_last5_yi"] = last5
    dbg["sum_last5_yi"] = s5
    dbg["pos_days_last5"] = pos
    dbg["latest_chg_yi"] = latest

    if (s5 >= TH_MARGIN_ALERT_SUM5) or (pos >= 5 and s5 >= TH_MARGIN_ALERT_POS5_SUM5):
        return "ALERT", dbg
    if (s5 >= TH_MARGIN_WATCH_SUM5) or (pos >= 4 and s5 >= TH_MARGIN_WATCH_POS5_SUM5):
        return "WATCH", dbg
    if s5 >= TH_MARGIN_INFO_SUM5:
        return "INFO", dbg
    return "NONE", dbg


def _extract_margin_signal(margin: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Extract or derive margin signal from taiwan_margin_financing/latest.json.

    Your schema:
      margin["series"]["TWSE"]["rows"] (latest->older)
      margin["series"]["TPEX"]["rows"]

    There is no precomputed 'margin_signal', so we derive it deterministically from TWSE last5 chg_yi.
    """
    if not isinstance(margin, dict):
        return None, {"reason": "margin_not_dict"}

    series = margin.get("series")
    if not isinstance(series, dict):
        return None, {"reason": "missing_series"}

    twse = series.get("TWSE", {})
    rows = twse.get("rows") if isinstance(twse, dict) else None

    sig, dbg = _derive_margin_signal_from_rows(rows)
    if sig is None:
        dbg["reason"] = "missing_or_invalid_rows_or_chg_yi"
    dbg["data_date"] = _as_str(twse.get("data_date")) if isinstance(twse, dict) else None
    dbg["source_url"] = _as_str(twse.get("source_url")) if isinstance(twse, dict) else None
    return sig, dbg


# =========================
# TW Local Gate (roll25 + margin)
# =========================
def _tw_local_gate(excluded: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Return TW gate section:
      - inputs summary
      - triggers: TRIG_TW_PANIC / TRIG_TW_LEVERAGE_HEAT / TRIG_TW_REVERSAL / TRIG_TW_DRAWDOWN (NA)
      - state: NA/NONE/TW_BOTTOM_WATCH/TW_BOTTOM_CANDIDATE/PANIC_BUT_LEVERAGE_HEAT
      - snapshot values for reporting
    """
    out: Dict[str, Any] = {
        "tw_state": "NA",
        "triggers": {
            "TRIG_TW_PANIC": None,
            "TRIG_TW_LEVERAGE_HEAT": None,
            "TRIG_TW_REVERSAL": None,
            "TRIG_TW_DRAWDOWN": None,
        },
        "distances": {
            "pct_change_to_nonnegative_gap": None,
            "lookback_missing_points": None,
            "drawdown_gap_pct": None,
        },
        "inputs": {
            "roll25_path": ROLL25_REPORT_PATH,
            "roll25_ok": False,
            "margin_path": TW_MARGIN_PATH,
            "margin_ok": False,
        },
        "snapshot": {
            "UsedDate": None,
            "run_day_tag": None,
            "risk_level": None,
            "lookback_n_actual": None,
            "lookback_n_target": None,
            "roll25_confidence": "NA",  # not present in latest_report.json; keep as NA
            "pct_change": None,
            "amplitude_pct": None,
            "turnover_twd": None,
            "close": None,
            "signals": {},
            "margin": {},
        },
        "notes": [],
    }

    # --- load roll25 latest_report.json ---
    roll, rerr = _exists_read_json(ROLL25_REPORT_PATH)
    if roll is None:
        excluded.append({"trigger": "TW:INPUT_ROLL25", "reason": f"not_available:{rerr or 'unknown'}"})
    else:
        out["inputs"]["roll25_ok"] = True
        roll_fields, roll_notes = _extract_roll25_fields(roll)
        out["snapshot"]["UsedDate"] = roll_fields.get("UsedDate")
        out["snapshot"]["run_day_tag"] = roll_fields.get("run_day_tag")
        out["snapshot"]["risk_level"] = roll_fields.get("risk_level")
        out["snapshot"]["lookback_n_actual"] = roll_fields.get("lookback_n_actual")
        out["snapshot"]["lookback_n_target"] = roll_fields.get("lookback_n_target")
        out["snapshot"]["pct_change"] = roll_fields.get("pct_change")
        out["snapshot"]["amplitude_pct"] = roll_fields.get("amplitude_pct")
        out["snapshot"]["turnover_twd"] = roll_fields.get("turnover_twd")
        out["snapshot"]["close"] = roll_fields.get("close")
        out["snapshot"]["signals"] = roll_fields.get("signals", {})
        if roll_notes:
            out["notes"].append("roll25_notes:" + ",".join(roll_notes))

    # --- load margin latest.json ---
    margin, merr = _exists_read_json(TW_MARGIN_PATH)
    margin_signal: Optional[str] = None
    margin_dbg: Dict[str, Any] = {}

    if margin is None:
        excluded.append({"trigger": "TW:INPUT_MARGIN", "reason": f"not_available:{merr or 'unknown'}"})
    else:
        out["inputs"]["margin_ok"] = True
        margin_signal, margin_dbg = _extract_margin_signal(margin)
        if margin_signal is None:
            out["notes"].append("margin file exists but cannot derive margin_signal -> heat=NA")

    out["snapshot"]["margin"] = {
        "margin_signal": margin_signal or "NA",
        "unit": "億",
        "debug": margin_dbg,
    }

    # --- derive TW triggers ---
    sigs = out["snapshot"]["signals"] if isinstance(out["snapshot"]["signals"], dict) else {}

    down = _as_bool(sigs.get("DownDay"))
    volA = _as_bool(sigs.get("VolumeAmplified"))
    volB = _as_bool(sigs.get("VolAmplified"))
    newlow = _as_bool(sigs.get("NewLow_N"))
    conbreak = _as_bool(sigs.get("ConsecutiveBreak"))

    # TRIG_TW_PANIC
    if down is None or (volA is None and volB is None and newlow is None and conbreak is None):
        excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_fields:roll25.signal.DownDay and/or other signal fields"})
        out["triggers"]["TRIG_TW_PANIC"] = None
    else:
        cond_any = False
        for b in (volA, volB, newlow, conbreak):
            if b is True:
                cond_any = True
                break
        out["triggers"]["TRIG_TW_PANIC"] = 1 if (down is True and cond_any) else 0

    # TRIG_TW_LEVERAGE_HEAT (no cross_module -> derived from margin_signal)
    if margin_signal is None:
        excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "missing_fields:margin_signal (derived from taiwan_margin_financing.series.TWSE.rows)"})
        out["triggers"]["TRIG_TW_LEVERAGE_HEAT"] = None
    else:
        out["triggers"]["TRIG_TW_LEVERAGE_HEAT"] = 1 if margin_signal in ("WATCH", "ALERT") else 0

    # TRIG_TW_REVERSAL
    pct_change = out["snapshot"].get("pct_change")
    pct_change = float(pct_change) if isinstance(pct_change, (int, float)) else None

    tw_panic = out["triggers"]["TRIG_TW_PANIC"]
    tw_heat = out["triggers"]["TRIG_TW_LEVERAGE_HEAT"]

    if tw_panic != 1:
        out["triggers"]["TRIG_TW_REVERSAL"] = 0 if tw_panic in (0, None) else 0
    else:
        if tw_heat is None:
            excluded.append({"trigger": "TRIG_TW_REVERSAL", "reason": "gating_missing:TRIG_TW_LEVERAGE_HEAT"})
            out["triggers"]["TRIG_TW_REVERSAL"] = None
        elif tw_heat == 1:
            out["triggers"]["TRIG_TW_REVERSAL"] = 0
        else:
            # heat==0, need pct_change>=0 and DownDay==False
            if pct_change is None or down is None:
                excluded.append({"trigger": "TRIG_TW_REVERSAL", "reason": "missing_fields:roll25.numbers.PctChange and/or roll25.signal.DownDay"})
                out["triggers"]["TRIG_TW_REVERSAL"] = None
            else:
                out["triggers"]["TRIG_TW_REVERSAL"] = 1 if (pct_change >= 0 and down is False) else 0

    # TRIG_TW_DRAWDOWN (no roll25_derived file in this repo)
    excluded.append({"trigger": "TRIG_TW_DRAWDOWN", "reason": "not_supported:no roll25_derived input in repo"})
    out["triggers"]["TRIG_TW_DRAWDOWN"] = None

    # Distances / gating notes
    if pct_change is not None:
        out["distances"]["pct_change_to_nonnegative_gap"] = pct_change - 0.0  # <=0 means still negative
    else:
        out["distances"]["pct_change_to_nonnegative_gap"] = None

    # lookback missing points vs target=20 (fixed), but your report already has actual
    act = out["snapshot"].get("lookback_n_actual")
    if isinstance(act, int):
        out["distances"]["lookback_missing_points"] = max(0, 20 - act)
    else:
        out["distances"]["lookback_missing_points"] = None

    out["distances"]["drawdown_gap_pct"] = None

    # TW state machine (simple v0)
    # - If no roll25 -> NA
    if out["inputs"]["roll25_ok"] is not True:
        out["tw_state"] = "NA"
        return out

    # - If TW_PANIC==0 => NONE
    if out["triggers"]["TRIG_TW_PANIC"] == 0:
        out["tw_state"] = "NONE"
        return out

    # - If TW_PANIC==1 and heat==1 => PANIC_BUT_LEVERAGE_HEAT
    if out["triggers"]["TRIG_TW_PANIC"] == 1 and out["triggers"]["TRIG_TW_LEVERAGE_HEAT"] == 1:
        out["tw_state"] = "PANIC_BUT_LEVERAGE_HEAT"
        return out

    # - If TW_PANIC==1 and heat==0:
    if out["triggers"]["TRIG_TW_PANIC"] == 1 and out["triggers"]["TRIG_TW_LEVERAGE_HEAT"] == 0:
        if out["triggers"]["TRIG_TW_REVERSAL"] == 1:
            out["tw_state"] = "TW_BOTTOM_CANDIDATE"
        else:
            out["tw_state"] = "TW_BOTTOM_WATCH"
        return out

    out["tw_state"] = "NA"
    return out


# =========================
# Main
# =========================
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

    # ---- extract global series snapshots ----
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

    # ---- global triggers ----
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]  # unit %

    # TRIG_PANIC: VIX >= 20 OR SP500.ret1% <= -1.5
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

    # ---- global bottom_state ----
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

    # ---- global context flags ----
    spx_p252 = series_out["SP500"]["w252"]["p"]
    context_equity_extreme: Optional[int] = None
    if spx_p252 is None:
        context_equity_extreme = None
    else:
        context_equity_extreme = 1 if float(spx_p252) >= 95.0 else 0

    # ---- global distances (<=0 means triggered) ----
    dist_vix_panic: Optional[float] = None
    if vix_val is not None:
        dist_vix_panic = TH_VIX_PANIC - float(vix_val)

    dist_spx_panic: Optional[float] = None
    if spx_ret1 is not None:
        dist_spx_panic = float(spx_ret1) - TH_SPX_RET1_PANIC

    dist_hyg_veto: Optional[float] = None
    if hyg_z is not None:
        dist_hyg_veto = float(hyg_z) - TH_HYG_VETO_Z

    dist_ofr_veto: Optional[float] = None
    if ofr_z is not None:
        dist_ofr_veto = TH_OFR_VETO_Z - float(ofr_z)

    # ---- TW local gate ----
    tw = _tw_local_gate(excluded)

    # ---- build latest.json ----
    latest_out = {
        "schema_version": "bottom_cache_v2",
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
        },
        "global": {
            "bottom_state": bottom_state,
            "triggers": {
                "TRIG_PANIC": trig_panic,
                "TRIG_SYSTEMIC_VETO": trig_veto,
                "TRIG_REVERSAL": trig_rev,
            },
            "context": {
                "context_equity_extreme_sp500_p252_ge_95": context_equity_extreme,
                "sp500_p252": spx_p252 if spx_p252 is not None else None,
            },
            "distances": {
                "vix_panic_gap": dist_vix_panic,
                "sp500_ret1_panic_gap": dist_spx_panic,
                "hyg_veto_gap_z": dist_hyg_veto,
                "ofr_veto_gap_z": dist_ofr_veto,
            },
            "series": series_out,
        },
        "tw": tw,
        "excluded_triggers": excluded,
        "notes": [
            "Global: single-source = market_cache/stats_latest.json",
            "TW: uses existing workflow outputs (roll25_cache/latest_report.json, taiwan_margin_financing/latest.json)",
            "No external fetching in this renderer.",
            "ret1_pct unit is percent (%) in market_cache",
            "TW margin unit is 億 (chg_yi, balance_yi)"
        ],
    }

    _write_json(OUT_LATEST, latest_out)

    # ---- history.json append (overwrite same TPE day bucket) ----
    hist: Dict[str, Any] = {"schema_version": "bottom_history_v2", "items": []}
    if os.path.exists(OUT_HISTORY):
        try:
            tmp = _read_json(OUT_HISTORY)
            if isinstance(tmp, dict) and isinstance(tmp.get("items"), list):
                hist = tmp
        except Exception:
            hist = {"schema_version": "bottom_history_v2", "items": []}

    item = {
        "run_ts_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "global": {
            "bottom_state": bottom_state,
            "triggers": latest_out["global"]["triggers"],
            "context": latest_out["global"]["context"],
            "distances": latest_out["global"]["distances"],
        },
        "tw": {
            "tw_state": tw.get("tw_state", "NA"),
            "triggers": tw.get("triggers", {}),
        },
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

    def _parse_iso(iso: str) -> Tuple[int, str]:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return (int(dt.timestamp()), iso)
        except Exception:
            return (0, iso)

    items_sorted.sort(key=lambda x: _parse_iso(_as_str(x.get("as_of_ts")) or "NA"))

    recent = items_sorted[-HISTORY_SHOW_N:] if items_sorted else []

    # global streak
    streak_g = 0
    cur_state_g = bottom_state
    for it in reversed(items_sorted):
        g = it.get("global", {}) if isinstance(it.get("global"), dict) else {}
        st = g.get("bottom_state") or "NA"
        if st == cur_state_g:
            streak_g += 1
        else:
            break

    # TW streak
    streak_tw = 0
    cur_state_tw = tw.get("tw_state", "NA")
    for it in reversed(items_sorted):
        t = it.get("tw", {}) if isinstance(it.get("tw"), dict) else {}
        st = t.get("tw_state") or "NA"
        if st == cur_state_tw:
            streak_tw += 1
        else:
            break

    # top-2 nearest global distances
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

    # ---- report.md ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state (Global): **{bottom_state}**  (streak={streak_g})\n")
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
    md.append(f"- tw_state: **{tw.get('tw_state','NA')}**  (streak={streak_tw})\n")
    md.append(f"- UsedDate: `{tw.get('snapshot',{}).get('UsedDate')}`; run_day_tag: `{tw.get('snapshot',{}).get('run_day_tag')}`; risk_level: `{tw.get('snapshot',{}).get('risk_level')}`\n")
    md.append(f"- Lookback: `{tw.get('snapshot',{}).get('lookback_n_actual')}/{tw.get('snapshot',{}).get('lookback_n_target')}`; roll25_confidence: `{tw.get('snapshot',{}).get('roll25_confidence','NA')}`\n")
    md.append(f"- margin_signal(TWSE): `{tw.get('snapshot',{}).get('margin',{}).get('margin_signal','NA')}`; unit: `億`\n\n")

    md.append("### TW Triggers (0/1/NA)\n")
    tr_tw = tw.get("triggers", {}) if isinstance(tw.get("triggers"), dict) else {}
    md.append(f"- TRIG_TW_PANIC: `{tr_tw.get('TRIG_TW_PANIC')}`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))\n")
    md.append(f"- TRIG_TW_LEVERAGE_HEAT: `{tr_tw.get('TRIG_TW_LEVERAGE_HEAT')}`  (margin_signal∈{{WATCH,ALERT}})\n")
    md.append(f"- TRIG_TW_REVERSAL: `{tr_tw.get('TRIG_TW_REVERSAL')}`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)\n")
    md.append(f"- TRIG_TW_DRAWDOWN: `{tr_tw.get('TRIG_TW_DRAWDOWN')}`  (not supported in repo)\n\n")

    md.append("### TW Distances / Gating\n")
    dist_tw = tw.get("distances", {}) if isinstance(tw.get("distances"), dict) else {}
    md.append(f"- pct_change_to_nonnegative_gap: `{dist_tw.get('pct_change_to_nonnegative_gap')}`\n")
    md.append(f"- lookback_missing_points: `{dist_tw.get('lookback_missing_points')}`\n")
    md.append(f"- drawdown_gap_pct (<=0 means reached): `{dist_tw.get('drawdown_gap_pct')}`\n\n")

    md.append("### TW Snapshot (key fields)\n")
    snap = tw.get("snapshot", {}) if isinstance(tw.get("snapshot"), dict) else {}
    sigs = snap.get("signals", {}) if isinstance(snap.get("signals"), dict) else {}
    md.append(f"- pct_change: `{snap.get('pct_change')}`; amplitude_pct: `{snap.get('amplitude_pct')}`; turnover_twd: `{snap.get('turnover_twd')}`; close: `{snap.get('close')}`\n")
    md.append(
        "- signals: "
        f"DownDay={sigs.get('DownDay')}, "
        f"VolumeAmplified={sigs.get('VolumeAmplified')}, "
        f"VolAmplified={sigs.get('VolAmplified')}, "
        f"NewLow_N={sigs.get('NewLow_N')}, "
        f"ConsecutiveBreak={sigs.get('ConsecutiveBreak')}\n"
    )
    mdbg = snap.get("margin", {}).get("debug", {}) if isinstance(snap.get("margin", {}), dict) else {}
    if isinstance(mdbg, dict) and mdbg.get("sum_last5_yi") is not None:
        md.append(
            f"- margin_debug(TWSE, unit=億): "
            f"sum_last5={_safe_float_str(_as_float(mdbg.get('sum_last5_yi')), 1)}, "
            f"pos_days_last5={mdbg.get('pos_days_last5')}, "
            f"latest_chg={_safe_float_str(_as_float(mdbg.get('latest_chg_yi')), 1)}\n"
        )
    md.append("\n")

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
            g = it.get("global", {}) if isinstance(it.get("global"), dict) else {}
            t = it.get("tw", {}) if isinstance(it.get("tw"), dict) else {}
            st = g.get("bottom_state") or "NA"
            trg = g.get("triggers", {}) if isinstance(g.get("triggers"), dict) else {}
            p = trg.get("TRIG_PANIC", "NA")
            v = trg.get("TRIG_SYSTEMIC_VETO", "NA")
            r = trg.get("TRIG_REVERSAL", "NA")
            tw_state = t.get("tw_state", "NA")
            tw_tr = t.get("triggers", {}) if isinstance(t.get("triggers"), dict) else {}
            tp = tw_tr.get("TRIG_TW_PANIC", None)
            th = tw_tr.get("TRIG_TW_LEVERAGE_HEAT", None)
            trv = tw_tr.get("TRIG_TW_REVERSAL", None)

            note = ""
            ctx = g.get("context", {}) if isinstance(g.get("context"), dict) else {}
            if ctx.get("context_equity_extreme_sp500_p252_ge_95", None) == 1:
                note = "equity_extreme"
            md.append(f"| {dk2} | {asof} | {st} | {p} | {v} | {r} | {tw_state} | {tp} | {th} | {trv} | {note} |\n")
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
    md.append(f"  - `{ROLL25_REPORT_PATH}`\n")
    md.append(f"  - `{TW_MARGIN_PATH}`  (unit: 億)\n")
    md.append("- This dashboard does not fetch external URLs directly.\n")

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()