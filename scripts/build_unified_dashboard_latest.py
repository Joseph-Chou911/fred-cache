#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
scripts/build_unified_dashboard_latest.py

Goal (audit-first):
- Merge modules: market_cache / fred_cache / taiwan_margin_financing / roll25_cache
- Add deterministic cross-module consistency (Margin × Roll25) into:
  modules.taiwan_margin_financing.cross_module

Deterministic rules (no guessing, rules are explicit):

A) roll25_heated:
    - If tag == "NON_TRADING_DAY" => heated=False
    - Else heated := (risk_level in {"中","高"})
                  OR any of signals {VolumeAmplified, VolAmplified, NewLow_N, ConsecutiveBreak} is True
    - Confidence downgrade:
        LookbackNActual < LookbackNTarget => confidence="DOWNGRADED" (note only)

B) margin_signal (two-stage):
    1) Prefer structured fields inside taiwan_margin_cache/latest.json:
       ["summary"]["signal"], ["signal"], ["status"]["signal"], ["result"]["signal"],
       ["meta"]["summary"]["signal"], ["meta"]["signal"]
       If found => use it.
    2) If not found (as in your current JSON), derive deterministically from chg_yi with rule_v1:
       - Compute TWSE last5 chg_yi: sum_last5, pos_days_last5, latest_chg
       - Rule_v1:
           ALERT if (sum_last5 >= 200) OR (pos_days_last5 >= 4 AND sum_last5 >= 150)
           WATCH if (sum_last5 >= 100) OR (pos_days_last5 >= 4 AND latest_chg >= 40)
           else NONE
       - Evidence path recorded as "DERIVED.rule_v1(TWSE_chg_yi_last5)"

C) consistency (Margin × Roll25):
    if margin_signal in {"WATCH","ALERT"} and roll25_heated: "RESONANCE"
    if margin_signal in {"WATCH","ALERT"} and not roll25_heated: "DIVERGENCE"
    if margin_signal not in {"WATCH","ALERT"} and roll25_heated: "MARKET_SHOCK_ONLY"
    else: "QUIET"
  If margin_signal=="NA" or roll25 unavailable => "NA"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

NA = "NA"

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def try_read(path: str) -> Dict[str, Any]:
    p = Path(path)
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def outcome_to_status(outcome: str) -> str:
    if outcome in ("present", "success", "ok", "OK"):
        return "OK"
    if outcome in ("failure", "cancelled", "FAILED"):
        return "FAILED"
    return "MISSING"

def safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur

def as_bool(x: Any) -> Optional[bool]:
    if isinstance(x, bool):
        return x
    return None

def normalize_signal(x: Any) -> str:
    if not isinstance(x, str):
        return NA
    s = x.strip().upper()
    if s in ("ALERT", "WATCH", "INFO", "NONE"):
        return s
    return NA

# -----------------------
# Margin: pick or derive
# -----------------------
def pick_margin_signal_structured(twm: Dict[str, Any]) -> Tuple[str, str]:
    candidates = [
        ("summary.signal", safe_get(twm, "summary", "signal")),
        ("signal", safe_get(twm, "signal")),
        ("status.signal", safe_get(twm, "status", "signal")),
        ("result.signal", safe_get(twm, "result", "signal")),
        ("meta.summary.signal", safe_get(twm, "meta", "summary", "signal")),
        ("meta.signal", safe_get(twm, "meta", "signal")),
    ]
    for path, val in candidates:
        s = normalize_signal(val)
        if s != NA:
            return s, path
    return NA, "NA"

def _extract_chg_lastn(twm: Dict[str, Any], which: str, n: int = 5) -> List[float]:
    rows = safe_get(twm, "series", which, "rows")
    out: List[float] = []
    if isinstance(rows, list):
        for r in rows[:n]:
            try:
                v = r.get("chg_yi")
                if isinstance(v, (int, float)):
                    out.append(float(v))
                elif isinstance(v, str) and v.strip():
                    out.append(float(v.strip()))
            except Exception:
                pass
    return out

def derive_margin_signal_rule_v1(twm: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """
    Deterministic derivation from TWSE last5 chg_yi.
    Returns (signal, source, rationale)
    """
    chg = _extract_chg_lastn(twm, "TWSE", 5)
    if not chg:
        return NA, "NA", {"reason": "no_chg_yi_last5"}

    sum_last5 = float(sum(chg))
    pos_days = int(sum(1 for x in chg if x > 0))
    latest_chg = float(chg[0])

    # rule_v1 thresholds (explicit constants)
    if (sum_last5 >= 200.0) or (pos_days >= 4 and sum_last5 >= 150.0):
        sig = "ALERT"
        rule_hit = "ALERT if sum_last5>=200 OR (pos_days>=4 AND sum_last5>=150)"
    elif (sum_last5 >= 100.0) or (pos_days >= 4 and latest_chg >= 40.0):
        sig = "WATCH"
        rule_hit = "WATCH if sum_last5>=100 OR (pos_days>=4 AND latest_chg>=40)"
    else:
        sig = "NONE"
        rule_hit = "NONE otherwise"

    rationale = {
        "basis": "TWSE chg_yi last5",
        "chg_last5": chg,
        "sum_last5": sum_last5,
        "pos_days_last5": pos_days,
        "latest_chg": latest_chg,
        "rule_version": "rule_v1",
        "rule_hit": rule_hit,
    }
    return sig, "DERIVED.rule_v1(TWSE_chg_yi_last5)", rationale

def pick_or_derive_margin_signal(twm: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    s, path = pick_margin_signal_structured(twm)
    if s != NA:
        return s, path, {"method": "structured_field", "path": path}

    s2, src2, rat2 = derive_margin_signal_rule_v1(twm)
    if s2 != NA:
        return s2, src2, {"method": "derived_rule", **rat2}

    return NA, "NA", {"method": "unavailable"}

# -----------------------
# Roll25 core extraction
# -----------------------
def _extract_lookback_from_caveats(caveats: Any) -> Tuple[Any, Any]:
    """
    Parse LookbackNTarget / LookbackNActual from caveats string if present.
    Deterministic regex parse; if not found => NA.
    """
    if not isinstance(caveats, str):
        return NA, NA
    m_t = re.search(r"LookbackNTarget=(\d+)", caveats)
    m_a = re.search(r"LookbackNActual=(\d+)", caveats)
    t = int(m_t.group(1)) if m_t else NA
    a = int(m_a.group(1)) if m_a else NA
    return t, a

def pick_roll25_core(roll25: Dict[str, Any]) -> Dict[str, Any]:
    numbers = safe_get(roll25, "numbers")
    if not isinstance(numbers, dict):
        numbers = {}

    sigs = safe_get(roll25, "signal")
    if not isinstance(sigs, dict):
        sigs = safe_get(roll25, "signals")
    if not isinstance(sigs, dict):
        sigs = {}

    used_date = (
        numbers.get("UsedDate")
        or safe_get(roll25, "UsedDate")
        or safe_get(roll25, "used_date")
        or safe_get(roll25, "meta", "UsedDate")
        or safe_get(roll25, "meta", "used_date")
    )

    risk_level = safe_get(roll25, "risk_level") or safe_get(roll25, "riskLevel") or safe_get(roll25, "meta", "risk_level")
    tag = safe_get(roll25, "tag") or safe_get(roll25, "meta", "tag")

    # lookback (prefer explicit fields; else parse caveats)
    n_target = safe_get(roll25, "LookbackNTarget") or safe_get(roll25, "lookback_n_target") or safe_get(roll25, "meta", "LookbackNTarget")
    n_actual = safe_get(roll25, "LookbackNActual") or safe_get(roll25, "lookback_n_actual") or safe_get(roll25, "meta", "LookbackNActual")

    if n_target is None or n_actual is None:
        t2, a2 = _extract_lookback_from_caveats(safe_get(roll25, "caveats"))
        if n_target is None:
            n_target = t2
        if n_actual is None:
            n_actual = a2

    return {
        "UsedDate": used_date if used_date is not None else NA,
        "tag": tag if tag is not None else NA,
        "risk_level": risk_level if risk_level is not None else NA,

        # turnover & related (numbers)
        "turnover_twd": numbers.get("TradeValue", NA),
        "turnover_unit": "TWD",
        "volume_multiplier": numbers.get("VolumeMultiplier", NA),
        "vol_multiplier": numbers.get("VolMultiplier", NA),
        "amplitude_pct": numbers.get("AmplitudePct", NA),
        "pct_change": numbers.get("PctChange", NA),
        "close": numbers.get("Close", NA),

        # signals
        "signals": {
            "DownDay": sigs.get("DownDay", NA),
            "VolumeAmplified": sigs.get("VolumeAmplified", NA),
            "VolAmplified": sigs.get("VolAmplified", NA),
            "NewLow_N": sigs.get("NewLow_N", NA),
            "ConsecutiveBreak": sigs.get("ConsecutiveBreak", NA),
            "OhlcMissing": sigs.get("OhlcMissing", NA),
        },
        "LookbackNTarget": n_target if n_target is not None else NA,
        "LookbackNActual": n_actual if n_actual is not None else NA,
    }

def window_confidence(core: Dict[str, Any]) -> Tuple[str, str]:
    n_target = core.get("LookbackNTarget", NA)
    n_actual = core.get("LookbackNActual", NA)

    def to_int(x: Any) -> Optional[int]:
        try:
            if isinstance(x, bool):
                return None
            if isinstance(x, int):
                return x
            if isinstance(x, float):
                return int(x)
            if isinstance(x, str) and x.strip() and x.strip().upper() != NA:
                return int(float(x.strip()))
        except Exception:
            return None
        return None

    t = to_int(n_target)
    a = to_int(n_actual)
    if t is not None and a is not None:
        if a < t:
            return "DOWNGRADED", f"LookbackNActual={a}/{t} (window_not_full)"
        return "OK", f"LookbackNActual={a}/{t} (window_full)"
    return "OK", "window_info_unavailable"

def roll25_heated_and_confidence(roll25: Dict[str, Any]) -> Tuple[Optional[bool], str, Dict[str, Any]]:
    if not isinstance(roll25, dict) or not roll25:
        return None, NA, {"reason": "roll25_missing"}

    core = pick_roll25_core(roll25)
    tag = core.get("tag", NA)
    risk_level = core.get("risk_level", NA)
    sigs = core.get("signals", {}) if isinstance(core.get("signals"), dict) else {}

    # NON_TRADING_DAY => forced not heated
    if isinstance(tag, str) and tag.strip().upper() == "NON_TRADING_DAY":
        confidence, window_note = window_confidence(core)
        return False, confidence, {
            "rule": "NON_TRADING_DAY => heated=False",
            "tag": tag,
            "risk_level": risk_level,
            "window_note": window_note,
            "signals_used": sigs,
        }

    def is_true(v: Any) -> bool:
        b = as_bool(v)
        return b is True

    rl_heated = (isinstance(risk_level, str) and risk_level in ("中", "高"))
    s_volume = is_true(sigs.get("VolumeAmplified"))
    s_vol = is_true(sigs.get("VolAmplified"))
    s_newlow = is_true(sigs.get("NewLow_N"))
    s_break = is_true(sigs.get("ConsecutiveBreak"))

    heated_flags = [
        ("risk_level_in_{中,高}", rl_heated),
        ("VolumeAmplified", s_volume),
        ("VolAmplified", s_vol),
        ("NewLow_N", s_newlow),
        ("ConsecutiveBreak", s_break),
    ]
    heated = any(v for _, v in heated_flags)

    confidence, window_note = window_confidence(core)
    return heated, confidence, {
        "rule": "heated := risk_level∈{中,高} OR any(signal in {VolumeAmplified,VolAmplified,NewLow_N,ConsecutiveBreak})",
        "risk_level": risk_level,
        "tag": tag,
        "heated_flags": [{"name": n, "value": v} for n, v in heated_flags],
        "window_note": window_note,
        "signals_used": sigs,
    }

def consistency_decision(margin_signal: str, roll25_heated: Optional[bool]) -> str:
    if margin_signal == NA or roll25_heated is None:
        return NA
    if margin_signal in ("WATCH", "ALERT") and roll25_heated:
        return "RESONANCE"
    if margin_signal in ("WATCH", "ALERT") and (not roll25_heated):
        return "DIVERGENCE"
    if margin_signal not in ("WATCH", "ALERT") and roll25_heated:
        return "MARKET_SHOCK_ONLY"
    return "QUIET"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market_in", required=True)
    ap.add_argument("--fred_in", required=True)
    ap.add_argument("--twmargin_in", required=True)
    ap.add_argument("--roll25_in", required=False, default="roll25_cache/latest_report.json")
    ap.add_argument("--market_outcome", required=True)
    ap.add_argument("--fred_outcome", required=True)
    ap.add_argument("--twmargin_outcome", required=True)
    ap.add_argument("--roll25_outcome", required=False, default="missing")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    market_ok = outcome_to_status(args.market_outcome) == "OK"
    fred_ok = outcome_to_status(args.fred_outcome) == "OK"
    twm_ok = outcome_to_status(args.twmargin_outcome) == "OK"
    roll_ok = outcome_to_status(args.roll25_outcome) == "OK"

    market = try_read(args.market_in) if market_ok else {}
    fred = try_read(args.fred_in) if fred_ok else {}
    twm = try_read(args.twmargin_in) if twm_ok else {}
    roll25 = try_read(args.roll25_in) if roll_ok else {}

    # margin signal (pick or derive)
    margin_signal, margin_signal_src, margin_rationale = (NA, NA, {"method": "unavailable"})
    if twm:
        margin_signal, margin_signal_src, margin_rationale = pick_or_derive_margin_signal(twm)

    # roll25 heated
    r_heated, r_conf, r_rationale = roll25_heated_and_confidence(roll25) if roll25 else (None, NA, {"reason": "roll25_missing"})
    cons = consistency_decision(margin_signal, r_heated)

    roll_core = pick_roll25_core(roll25) if roll25 else {}
    roll_used_date = roll_core.get("UsedDate", NA) if isinstance(roll_core, dict) else NA

    twm_date = (
        safe_get(twm, "meta", "data_date")
        or safe_get(twm, "data_date")
        or safe_get(twm, "series", "TWSE", "data_date")
        or safe_get(twm, "twse", "data_date")
    )
    twm_date = twm_date if isinstance(twm_date, str) and twm_date.strip() else NA
    used_date_match = (twm_date != NA and roll_used_date != NA and twm_date == roll_used_date)

    unified = {
        "schema_version": "unified_dashboard_latest_v1",
        "generated_at_utc": now_utc(),
        "inputs": {
            "market_in": args.market_in,
            "fred_in": args.fred_in,
            "twmargin_in": args.twmargin_in,
            "roll25_in": args.roll25_in,
        },
        "modules": {
            "market_cache": {
                "status": outcome_to_status(args.market_outcome),
                "dashboard_latest": market if market else None,
            },
            "fred_cache": {
                "status": outcome_to_status(args.fred_outcome),
                "dashboard_latest": fred if fred else None,
            },
            "roll25_cache": {
                "status": outcome_to_status(args.roll25_outcome),
                "latest_report": roll25 if roll25 else None,
                "core": roll_core if roll_core else None,
            },
            "taiwan_margin_financing": {
                "status": outcome_to_status(args.twmargin_outcome),
                "latest": twm if twm else None,
                "cross_module": {
                    "margin_signal": margin_signal,
                    "margin_signal_source": margin_signal_src,
                    "margin_rationale": margin_rationale,
                    "roll25_heated": r_heated if r_heated is not None else NA,
                    "roll25_confidence": r_conf,
                    "consistency": cons,
                    "rationale": {
                        "consistency_rule": "Deterministic Margin×Roll25 (see script header).",
                        "roll25_rationale": r_rationale,
                        "date_alignment": {
                            "twmargin_date": twm_date,
                            "roll25_used_date": roll_used_date,
                            "used_date_match": used_date_match if (twm_date != NA and roll_used_date != NA) else NA,
                            "note": "confirm-only; does not change signal",
                        },
                    },
                },
            },
        },
        "audit_notes": [
            "roll25_heated is computed deterministically from roll25 JSON only (risk_level + explicit signal booleans); NON_TRADING_DAY forces heated=False.",
            "roll25_confidence is DOWNGRADED only when LookbackNActual < LookbackNTarget (info-note only).",
            "margin_signal: prefer structured field; if missing, derive by rule_v1 from TWSE chg_yi last5 (explicit thresholds, deterministic).",
            "No external data fetch in this step.",
        ],
    }

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()