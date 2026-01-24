#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
scripts/build_unified_dashboard_latest.py

Goal (audit-first):
- Merge modules: market_cache / fred_cache / taiwan_margin_financing / roll25_cache
- Add deterministic cross-module consistency (Margin × Roll25) into:
  modules.taiwan_margin_financing.cross_module

Rules (deterministic, no guessing):
- roll25_heated:
    risk_level in {中, 高}
    OR any of signals {VolumeAmplified, VolAmplified, NewLow_N, ConsecutiveBreak} is True
  Special-case:
    tag == "NON_TRADING_DAY" => heated=False, add note
  Confidence downgrade:
    LookbackNActual < LookbackNTarget => confidence="DOWNGRADED" (note only)

- margin_signal:
    Prefer structured fields inside taiwan_margin_cache/latest.json:
      1) ["summary"]["signal"]
      2) ["signal"]
      3) ["status"]["signal"]
      4) ["result"]["signal"]
    If not found => "NA" and consistency="NA"

- consistency:
    if margin_signal in {"WATCH","ALERT"} and roll25_heated: "RESONANCE"
    if margin_signal in {"WATCH","ALERT"} and not roll25_heated: "DIVERGENCE"
    if margin_signal not in {"WATCH","ALERT"} and roll25_heated: "MARKET_SHOCK_ONLY"
    else: "QUIET"
  If margin_signal=="NA" or roll25 unavailable => "NA"

Note:
- This script does NOT parse markdown dashboards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

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
    # From file checks: present|missing
    # Also accepts: success|failure|cancelled|skipped (if you later want step outcomes)
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

def pick_margin_signal(twm: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (margin_signal, evidence_path)
    """
    candidates = [
        ("summary.signal", safe_get(twm, "summary", "signal")),
        ("signal", safe_get(twm, "signal")),
        ("status.signal", safe_get(twm, "status", "signal")),
        ("result.signal", safe_get(twm, "result", "signal")),
    ]
    for path, val in candidates:
        s = normalize_signal(val)
        if s != NA:
            return s, path
    return NA, "NA"

def pick_roll25_core(roll25: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a small, auditable subset (no guessing).
    We keep raw roll25 too, but this makes report/inspection easier.
    """
    used_date = (
        safe_get(roll25, "UsedDate")
        or safe_get(roll25, "used_date")
        or safe_get(roll25, "meta", "UsedDate")
        or safe_get(roll25, "meta", "used_date")
    )
    risk_level = safe_get(roll25, "risk_level") or safe_get(roll25, "riskLevel") or safe_get(roll25, "meta", "risk_level")
    tag = safe_get(roll25, "tag") or safe_get(roll25, "meta", "tag")
    signals = safe_get(roll25, "signals")
    if not isinstance(signals, dict):
        signals = {}

    # window info (names may vary; keep robust)
    n_target = (
        safe_get(roll25, "LookbackNTarget")
        or safe_get(roll25, "meta", "LookbackNTarget")
        or safe_get(roll25, "lookback", "target")
    )
    n_actual = (
        safe_get(roll25, "LookbackNActual")
        or safe_get(roll25, "meta", "LookbackNActual")
        or safe_get(roll25, "lookback", "actual")
    )

    return {
        "UsedDate": used_date if used_date is not None else NA,
        "risk_level": risk_level if risk_level is not None else NA,
        "tag": tag if tag is not None else NA,
        "signals": {
            "DownDay": signals.get("DownDay", NA),
            "VolumeAmplified": signals.get("VolumeAmplified", NA),
            "VolAmplified": signals.get("VolAmplified", NA),
            "NewLow_N": signals.get("NewLow_N", NA),
            "ConsecutiveBreak": signals.get("ConsecutiveBreak", NA),
            "OhlcMissing": signals.get("OhlcMissing", NA),
        },
        "LookbackNTarget": n_target if n_target is not None else NA,
        "LookbackNActual": n_actual if n_actual is not None else NA,
    }

def roll25_heated_and_confidence(roll25: Dict[str, Any]) -> Tuple[Optional[bool], str, Dict[str, Any]]:
    """
    Returns:
      heated: Optional[bool] (None if cannot determine)
      confidence: "OK"|"DOWNGRADED"|"NA"
      rationale: dict (auditable)
    """
    if not isinstance(roll25, dict) or not roll25:
        return None, NA, {"reason": "roll25_missing"}

    core = pick_roll25_core(roll25)
    tag = core.get("tag", NA)
    risk_level = core.get("risk_level", NA)
    sigs = core.get("signals", {}) if isinstance(core.get("signals"), dict) else {}

    # tag: NON_TRADING_DAY => forced not heated (deterministic)
    if isinstance(tag, str) and tag.strip().upper() == "NON_TRADING_DAY":
        confidence = "OK"
        # but still check window for confidence downgrade note
        confidence, window_note = window_confidence(core)
        rat = {
            "rule": "NON_TRADING_DAY => heated=False",
            "tag": tag,
            "risk_level": risk_level,
            "window_note": window_note,
            "signals_used": sigs,
        }
        return False, confidence, rat

    heated_flags = []
    # risk_level
    rl_heated = (isinstance(risk_level, str) and risk_level in ("中", "高"))
    heated_flags.append(("risk_level_in_{中,高}", rl_heated))

    # signals: treat only explicit True as True
    def is_true(v: Any) -> bool:
        b = as_bool(v)
        return b is True

    s_volume = is_true(sigs.get("VolumeAmplified"))
    s_vol = is_true(sigs.get("VolAmplified"))
    s_newlow = is_true(sigs.get("NewLow_N"))
    s_break = is_true(sigs.get("ConsecutiveBreak"))

    heated_flags.append(("VolumeAmplified", s_volume))
    heated_flags.append(("VolAmplified", s_vol))
    heated_flags.append(("NewLow_N", s_newlow))
    heated_flags.append(("ConsecutiveBreak", s_break))

    heated = any(flag for _, flag in heated_flags)

    confidence, window_note = window_confidence(core)
    rat = {
        "rule": "heated := risk_level∈{中,高} OR any(signal in {VolumeAmplified,VolAmplified,NewLow_N,ConsecutiveBreak})",
        "risk_level": risk_level,
        "tag": tag,
        "heated_flags": [{"name": n, "value": v} for n, v in heated_flags],
        "window_note": window_note,
        "signals_used": sigs,
    }
    return heated, confidence, rat

def window_confidence(core: Dict[str, Any]) -> Tuple[str, str]:
    """
    Confidence downgrade if LookbackNActual < LookbackNTarget (when both numeric).
    """
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
    # unknown
    return "OK", "window_info_unavailable"

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

    # derive cross-module consistency (Margin × Roll25)
    margin_signal, margin_signal_path = pick_margin_signal(twm) if twm else (NA, NA)
    r_heated, r_conf, r_rationale = roll25_heated_and_confidence(roll25) if roll25 else (None, NA, {"reason": "roll25_missing"})
    cons = consistency_decision(margin_signal, r_heated)

    # Additional audit note: date alignment (confirm-only)
    roll_core = pick_roll25_core(roll25) if roll25 else {}
    roll_used_date = roll_core.get("UsedDate", NA) if isinstance(roll_core, dict) else NA
    # Try to read margin latest date from twm (best-effort, no guessing)
    # Common possible paths: ["series"]["TWSE"]["data_date"], ["meta"]["data_date"], ["data_date"]
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
                    "margin_signal_source": margin_signal_path,
                    "roll25_heated": r_heated if r_heated is not None else NA,
                    "roll25_confidence": r_conf,
                    "consistency": cons,
                    "rationale": {
                        "consistency_rule": "See script header; deterministic Margin×Roll25",
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
            "margin_signal is read from taiwan_margin_cache/latest.json structured fields; if missing => NA and consistency => NA.",
            "No markdown parsing; no external data fetch in this step.",
        ],
    }

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()