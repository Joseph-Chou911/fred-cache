#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build unified dashboard JSON from module outputs.

Adds:
- roll25_derived: N-day realized volatility (annualized) + max drawdown
- fx_usdtwd: USD/TWD spot mid (BOT) + ret1/chg_5d + deterministic signal rule
- taiwan_margin_financing.cross_module:
  - margin_signal (derived from TWSE chg_yi last5 if not present)
  - roll25_heated (derived from roll25 report only)
  - roll25_confidence (DOWNGRADED when lookback not full or unknown)
  - consistency (CONVERGENCE/DIVERGENCE) + deterministic rationale

NO external fetch here. Pure merge + deterministic calculations.

Inputs:
- dashboard/dashboard_latest.json
- dashboard_fred_cache/dashboard_latest.json
- taiwan_margin_cache/latest.json
- roll25_cache/latest_report.json
- fx_cache/latest.json (+ fx_cache/history.json)

Output:
- unified_dashboard/latest.json (or any path you pass)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _dump_json(path: str, obj: Any) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ---------- Roll25 derived metrics ----------

def _extract_roll25_closes(roll25_latest_report: Dict[str, Any]) -> List[float]:
    # Prefer cache_roll25 (already ordered newest->oldest in your sample)
    arr = roll25_latest_report.get("cache_roll25")
    out: List[float] = []
    if isinstance(arr, list):
        for it in arr:
            if isinstance(it, dict):
                v = it.get("close")
                if isinstance(v, (int, float)):
                    out.append(float(v))
    # cache_roll25 is expected newest first; keep that order
    return out


def _realized_vol_annualized_pct(closes_newest_first: List[float], n: int) -> Tuple[Optional[float], int]:
    """
    Compute annualized realized volatility (pct) from last n returns.
    Uses log returns; annualization sqrt(252).
    Need at least n+1 closes.
    Returns (vol_pct, points_used).
    """
    if n <= 0:
        return None, 0
    if len(closes_newest_first) < n + 1:
        return None, 0

    closes = closes_newest_first[: n + 1]
    rets: List[float] = []
    for i in range(n):
        c_new = closes[i]
        c_old = closes[i + 1]
        if c_new <= 0 or c_old <= 0:
            return None, 0
        rets.append(math.log(c_new / c_old))

    if len(rets) < 2:
        return None, len(rets)

    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)  # sample var
    vol_daily = math.sqrt(max(var, 0.0))
    vol_ann = vol_daily * math.sqrt(252.0)
    return vol_ann * 100.0, len(rets)


def _max_drawdown_pct(closes_newest_first: List[float], n: int) -> Tuple[Optional[float], int]:
    """
    Max drawdown over last n closes (not returns).
    Input order newest->oldest; evaluate chronologically oldest->newest.
    Returns (max_drawdown_pct as negative number, points_used).
    """
    if n <= 1:
        return None, 0
    if len(closes_newest_first) < n:
        return None, 0

    series = list(reversed(closes_newest_first[:n]))
    peak = -1e100
    max_dd = 0.0
    for c in series:
        if c > peak:
            peak = c
        if peak > 0:
            dd = (c / peak) - 1.0
            if dd < max_dd:
                max_dd = dd
    return max_dd * 100.0, len(series)


def _extract_lookback_target_from_roll25_report(roll_obj: Dict[str, Any]) -> Optional[int]:
    """
    Deterministically extract LookbackNTarget.
    Priority:
    1) roll_obj.core.LookbackNTarget
    2) roll_obj.numbers.LookbackNTarget
    3) roll_obj.LookbackNTarget
    4) parse from caveats string: "LookbackNTarget=20"
    If not found => None
    """
    for path in [
        ("core", "LookbackNTarget"),
        ("numbers", "LookbackNTarget"),
        ("LookbackNTarget",),
    ]:
        v = _safe_get(roll_obj, *path) if len(path) > 1 else roll_obj.get(path[0])
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)

    cav = roll_obj.get("caveats")
    if isinstance(cav, str):
        m = re.search(r"LookbackNTarget=(\d+)", cav)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None


def _extract_useddate_from_roll25_report(roll_obj: Dict[str, Any]) -> Optional[str]:
    # Prefer numbers.UsedDate (as in your sample), else used_date
    v = _safe_get(roll_obj, "numbers", "UsedDate")
    if isinstance(v, str):
        return v
    v2 = roll_obj.get("used_date")
    if isinstance(v2, str):
        return v2
    return None


def _roll25_heated_rule_v1(roll_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic "heated" flag from roll25 JSON only.
    Rules:
    - If tag == "NON_TRADING_DAY" => heated=False
    - Else heated=True if ANY of these signals are true:
      DownDay, VolumeAmplified, VolAmplified, NewLow_N, ConsecutiveBreak, OhlcMissing
    - Else heated=False
    Confidence:
    - DOWNGRADED if LookbackNActual < LookbackNTarget OR target unknown.
    """
    tag = roll_obj.get("tag")
    risk_level = roll_obj.get("risk_level")
    nums = roll_obj.get("numbers") if isinstance(roll_obj.get("numbers"), dict) else {}
    sigs = roll_obj.get("signal") if isinstance(roll_obj.get("signal"), dict) else {}

    used_date = _extract_useddate_from_roll25_report(roll_obj)

    def _b(x: Any) -> bool:
        return bool(x) is True

    if isinstance(tag, str) and tag == "NON_TRADING_DAY":
        heated = False
        rule_note = "NON_TRADING_DAY => heated=False"
    else:
        keys = ["DownDay", "VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak", "OhlcMissing"]
        hits = {k: _b(sigs.get(k)) for k in keys}
        heated = any(hits.values())
        rule_note = "heated=True if any key signals true else False"

    lookback_actual = roll_obj.get("lookback_n_actual")
    if not isinstance(lookback_actual, int):
        # If absent, try fall back from numbers
        la2 = nums.get("LookbackNActual")
        if isinstance(la2, int):
            lookback_actual = la2

    lookback_target = _extract_lookback_target_from_roll25_report(roll_obj)

    confidence = "OK"
    if not isinstance(lookback_actual, int):
        confidence = "DOWNGRADED"
    elif lookback_target is None:
        confidence = "DOWNGRADED"
    elif lookback_actual < lookback_target:
        confidence = "DOWNGRADED"

    return {
        "roll25_heated": bool(heated),
        "roll25_confidence": confidence,
        "roll25_rationale": {
            "rule": rule_note,
            "tag": tag if isinstance(tag, str) else "NA",
            "risk_level": risk_level if isinstance(risk_level, str) else "NA",
            "window_note": (
                f"LookbackNActual={lookback_actual}/{lookback_target} (window_not_full)"
                if isinstance(lookback_actual, int) and isinstance(lookback_target, int) and lookback_actual < lookback_target
                else (
                    f"LookbackNActual={lookback_actual}/{lookback_target}"
                    if isinstance(lookback_actual, int)
                    else "LookbackNActual=NA"
                )
            ),
            "signals_used": {
                "DownDay": sigs.get("DownDay", False),
                "VolumeAmplified": sigs.get("VolumeAmplified", False),
                "VolAmplified": sigs.get("VolAmplified", False),
                "NewLow_N": sigs.get("NewLow_N", False),
                "ConsecutiveBreak": sigs.get("ConsecutiveBreak", False),
                "OhlcMissing": sigs.get("OhlcMissing", False),
            },
            "used_date": used_date or "NA",
        },
    }


# ---------- Margin signal (TWSE) ----------

def _extract_twm_series(twm_obj: Dict[str, Any], market: str) -> Optional[Dict[str, Any]]:
    """
    Your taiwan_margin_cache/latest.json sample:
    latest.series.TWSE / latest.series.TPEX
    """
    series = _safe_get(twm_obj, "series")
    if not isinstance(series, dict):
        return None
    node = series.get(market)
    return node if isinstance(node, dict) else None


def _derive_margin_signal_rule_v1_from_twm(twm_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic margin_signal rule (v1) based on TWSE chg_yi last5:
    - WATCH if sum_last5>=100 OR (pos_days>=4 AND latest_chg>=40)
    - INFO  if sum_last5>=60  OR (pos_days>=3 AND latest_chg>=30)
    - NONE  otherwise
    Confidence:
    - DOWNGRADED if <5 chg values available
    """
    twse = _extract_twm_series(twm_obj, "TWSE") or {}
    rows = twse.get("rows")
    chgs: List[float] = []
    if isinstance(rows, list):
        for it in rows[:10]:  # only need a few newest
            if isinstance(it, dict):
                v = it.get("chg_yi")
                if isinstance(v, (int, float)):
                    chgs.append(float(v))

    last5 = chgs[:5]
    points = len(last5)
    sum_last5 = sum(last5) if points > 0 else 0.0
    pos_days = sum(1 for x in last5 if x > 0)
    latest_chg = last5[0] if points >= 1 else None

    # thresholds (explicit, deterministic)
    signal = "NA"
    rule_hit = "NA"
    if points >= 1:
        hit_watch = (points >= 5 and sum_last5 >= 100.0) or (points >= 5 and pos_days >= 4 and latest_chg is not None and latest_chg >= 40.0)
        hit_info = (points >= 5 and sum_last5 >= 60.0) or (points >= 5 and pos_days >= 3 and latest_chg is not None and latest_chg >= 30.0)
        if hit_watch:
            signal = "WATCH"
            rule_hit = "WATCH if sum_last5>=100 OR (pos_days>=4 AND latest_chg>=40)"
        elif hit_info:
            signal = "INFO"
            rule_hit = "INFO if sum_last5>=60 OR (pos_days>=3 AND latest_chg>=30)"
        else:
            signal = "NONE"
            rule_hit = "below thresholds"

    confidence = "OK" if points >= 5 else "DOWNGRADED"

    # best-effort date
    data_date = twse.get("data_date") if isinstance(twse.get("data_date"), str) else None

    return {
        "margin_signal": signal,
        "margin_signal_source": "DERIVED.rule_v1(TWSE_chg_yi_last5)",
        "margin_rationale": {
            "method": "derived_rule",
            "basis": "TWSE chg_yi last5",
            "chg_last5": last5,
            "sum_last5": sum_last5,
            "pos_days_last5": pos_days,
            "latest_chg": latest_chg,
            "rule_version": "rule_v1",
            "rule_hit": rule_hit,
            "confidence": confidence,
            "twse_data_date": data_date or "NA",
        },
    }


def _get_margin_signal_prefer_structured(twm_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    If margin cache already has cross_module.margin_signal, prefer it (structured),
    else derive using rule_v1 from TWSE.
    """
    cm = twm_obj.get("cross_module")
    if isinstance(cm, dict) and isinstance(cm.get("margin_signal"), str):
        # still ensure rationale exists
        out = {
            "margin_signal": cm.get("margin_signal", "NA"),
            "margin_signal_source": cm.get("margin_signal_source", "STRUCTURED"),
            "margin_rationale": cm.get("margin_rationale", {"method": "structured_or_unknown"}),
        }
        return out
    return _derive_margin_signal_rule_v1_from_twm(twm_obj)


def _date_alignment(twm_obj: Dict[str, Any], roll_obj: Dict[str, Any]) -> Dict[str, Any]:
    twse = _extract_twm_series(twm_obj, "TWSE") or {}
    twm_date = twse.get("data_date") if isinstance(twse.get("data_date"), str) else None
    used_date = _extract_useddate_from_roll25_report(roll_obj)
    used_date_match = (twm_date is not None and used_date is not None and twm_date == used_date)
    return {
        "twmargin_date": twm_date or "NA",
        "roll25_used_date": used_date or "NA",
        "used_date_match": bool(used_date_match),
        "note": "confirm-only; does not change signal",
    }


def _consistency_rule_v1(margin_signal: str, roll25_heated: bool) -> Dict[str, Any]:
    """
    Deterministic consistency label between margin and roll25 heat.
    - DIVERGENCE if (margin in WATCH/ALERT and heated=False) OR (margin==NONE and heated=True)
    - CONVERGENCE otherwise
    """
    ms = margin_signal or "NA"
    heated = bool(roll25_heated)

    diverge = ((ms in ("WATCH", "ALERT")) and (not heated)) or ((ms == "NONE") and heated)
    return {
        "consistency": "DIVERGENCE" if diverge else "CONVERGENCE",
        "consistency_rule": "Deterministic Margin×Roll25 (rule_v1).",
    }


# ---------- FX derived metrics ----------

def _load_fx_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        obj = _load_json(path)
        items = obj.get("items") if isinstance(obj, dict) else None
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict) and isinstance(x.get("date"), str)]
    except Exception:
        return []
    return []


def _fx_ret1_and_chg5(history_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    mids: List[float] = []
    dates: List[str] = []
    for it in history_items:
        mid = it.get("mid")
        if isinstance(mid, (int, float)) and isinstance(it.get("date"), str):
            mids.append(float(mid))
            dates.append(it["date"])

    out: Dict[str, Any] = {
        "ret1_pct": None,
        "ret1_from": None,
        "ret1_to": None,
        "chg_5d_pct": None,
        "chg_5d_from": None,
        "chg_5d_to": None,
        "points": len(mids),
    }
    if len(mids) >= 2:
        prev = mids[-2]
        last = mids[-1]
        if prev != 0:
            out["ret1_pct"] = (last - prev) / abs(prev) * 100.0
            out["ret1_from"] = dates[-2]
            out["ret1_to"] = dates[-1]
    if len(mids) >= 6:
        base = mids[-6]
        last = mids[-1]
        if base != 0:
            out["chg_5d_pct"] = (last - base) / abs(base) * 100.0
            out["chg_5d_from"] = dates[-6]
            out["chg_5d_to"] = dates[-1]
    return out


def _fx_signal_rule_v1(ret1_pct: Optional[float], chg_5d_pct: Optional[float], points: int) -> Dict[str, Any]:
    """
    Deterministic FX pressure signal (v1).
    - WATCH if abs(chg_5d_pct) >= 1.5 OR abs(ret1_pct) >= 1.0
    - INFO  if abs(chg_5d_pct) >= 1.0 OR abs(ret1_pct) >= 0.7
    - NONE  otherwise
    Confidence:
    - DOWNGRADED if points < 6 (cannot compute chg_5d) OR ret1 unavailable
    """
    def _abs(x: Optional[float]) -> Optional[float]:
        return None if x is None else abs(float(x))

    a1 = _abs(ret1_pct)
    a5 = _abs(chg_5d_pct)

    signal = "NA"
    reason = "NA"
    if a1 is not None or a5 is not None:
        hit_watch = ((a5 is not None and a5 >= 1.5) or (a1 is not None and a1 >= 1.0))
        hit_info = ((a5 is not None and a5 >= 1.0) or (a1 is not None and a1 >= 0.7))
        if hit_watch:
            signal = "WATCH"
            reason = "abs(chg_5d%)>=1.5 OR abs(ret1%)>=1.0"
        elif hit_info:
            signal = "INFO"
            reason = "abs(chg_5d%)>=1.0 OR abs(ret1%)>=0.7"
        else:
            signal = "NONE"
            reason = "below thresholds"

    confidence = "OK"
    if points < 2 or a1 is None:
        confidence = "DOWNGRADED"
    elif points < 6 or a5 is None:
        confidence = "DOWNGRADED"

    return {
        "fx_signal": signal,
        "fx_reason": reason,
        "fx_rule_version": "rule_v1",
        "fx_confidence": confidence,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market-in", default="dashboard/dashboard_latest.json")
    ap.add_argument("--fred-in", default="dashboard_fred_cache/dashboard_latest.json")
    ap.add_argument("--twmargin-in", default="taiwan_margin_cache/latest.json")
    ap.add_argument("--roll25-in", default="roll25_cache/latest_report.json")
    ap.add_argument("--fx-in", default="fx_cache/latest.json")
    ap.add_argument("--fx-history", default="fx_cache/history.json")
    ap.add_argument("--out", default="unified_dashboard/latest.json")

    ap.add_argument("--roll25-vol-n", type=int, default=int(os.getenv("ROLL25_VOL_N", "10")))
    ap.add_argument("--roll25-dd-n", type=int, default=int(os.getenv("ROLL25_DD_N", "10")))
    args = ap.parse_args()

    generated_at_utc = _now_utc_z()

    def _load_or_fail(path: str) -> Tuple[str, Any]:
        try:
            return "OK", _load_json(path)
        except Exception as e:
            return f"ERROR: {e}", None

    market_status, market_obj = _load_or_fail(args.market_in)
    fred_status, fred_obj = _load_or_fail(args.fred_in)
    twm_status, twm_obj = _load_or_fail(args.twmargin_in)
    roll_status, roll_obj = _load_or_fail(args.roll25_in)
    fx_status, fx_obj = _load_or_fail(args.fx_in)

    # roll25 derived
    roll25_derived: Dict[str, Any] = {"status": "NA"}
    if roll_status == "OK" and isinstance(roll_obj, dict):
        closes_newest = _extract_roll25_closes(roll_obj)
        vol_pct, vol_pts = _realized_vol_annualized_pct(closes_newest, args.roll25_vol_n)
        dd_pct, dd_pts = _max_drawdown_pct(closes_newest, args.roll25_dd_n)

        lookback_actual = roll_obj.get("lookback_n_actual")
        lookback_target = _extract_lookback_target_from_roll25_report(roll_obj)

        confidence = "OK"
        if not isinstance(lookback_actual, int):
            confidence = "DOWNGRADED"
        elif lookback_target is None:
            confidence = "DOWNGRADED"
        elif lookback_actual < lookback_target:
            confidence = "DOWNGRADED"

        roll25_derived = {
            "status": "OK",
            "params": {"vol_n": args.roll25_vol_n, "dd_n": args.roll25_dd_n},
            "realized_vol_N_annualized_pct": vol_pct,
            "realized_vol_points_used": vol_pts,
            "max_drawdown_N_pct": dd_pct,
            "max_drawdown_points_used": dd_pts,
            "confidence": confidence,
            "notes": [
                "Realized vol uses log returns, sample std (ddof=1), annualized by sqrt(252).",
                "Max drawdown computed on chronological closes within N points.",
            ],
            "lookback": {
                "LookbackNActual": lookback_actual if isinstance(lookback_actual, int) else "NA",
                "LookbackNTarget": lookback_target if isinstance(lookback_target, int) else "NA",
            },
        }

    # fx derived
    fx_derived: Dict[str, Any] = {"status": "NA"}
    fx_hist_items = _load_fx_history(args.fx_history)
    if fx_status == "OK" and isinstance(fx_obj, dict):
        data_date = fx_obj.get("data_date")
        mid = _safe_get(fx_obj, "usd_twd", "mid")
        spot_buy = _safe_get(fx_obj, "usd_twd", "spot_buy")
        spot_sell = _safe_get(fx_obj, "usd_twd", "spot_sell")
        src_url = fx_obj.get("source_url")

        mom = _fx_ret1_and_chg5(fx_hist_items)
        sig = _fx_signal_rule_v1(mom.get("ret1_pct"), mom.get("chg_5d_pct"), mom.get("points", 0))

        dir_label = "NA"
        if isinstance(mom.get("ret1_pct"), (int, float)):
            dir_label = "TWD_STRONG" if mom["ret1_pct"] < 0 else "TWD_WEAK"

        fx_derived = {
            "status": "OK",
            "source": fx_obj.get("source"),
            "source_url": src_url,
            "data_date": data_date,
            "usd_twd": {"spot_buy": spot_buy, "spot_sell": spot_sell, "mid": mid},
            "momentum": mom,
            "dir": dir_label,
            **sig,
        }

    # cross_module (Margin×Roll25)
    cross_module: Dict[str, Any] = {}
    if twm_status == "OK" and isinstance(twm_obj, dict) and roll_status == "OK" and isinstance(roll_obj, dict):
        ms = _get_margin_signal_prefer_structured(twm_obj)
        r25 = _roll25_heated_rule_v1(roll_obj)
        align = _date_alignment(twm_obj, roll_obj)
        cons = _consistency_rule_v1(str(ms.get("margin_signal", "NA")), bool(r25.get("roll25_heated", False)))

        cross_module = {
            "margin_signal": ms.get("margin_signal", "NA"),
            "margin_signal_source": ms.get("margin_signal_source", "NA"),
            "margin_rationale": ms.get("margin_rationale", {"method": "NA"}),
            "roll25_heated": r25.get("roll25_heated", False),
            "roll25_confidence": r25.get("roll25_confidence", "NA"),
            "consistency": cons.get("consistency", "NA"),
            "rationale": {
                "consistency_rule": cons.get("consistency_rule", "NA"),
                "roll25_rationale": r25.get("roll25_rationale", {"rule": "NA"}),
                "date_alignment": align,
            },
        }

    unified = {
        "schema_version": "unified_dashboard_latest_v1",
        "generated_at_utc": generated_at_utc,
        "inputs": {
            "market_in": args.market_in,
            "fred_in": args.fred_in,
            "twmargin_in": args.twmargin_in,
            "roll25_in": args.roll25_in,
            "fx_in": args.fx_in,
            "fx_history": args.fx_history,
        },
        "modules": {
            "market_cache": {
                "status": "OK" if market_status == "OK" else market_status,
                "dashboard_latest": market_obj,
            },
            "fred_cache": {
                "status": "OK" if fred_status == "OK" else fred_status,
                "dashboard_latest": fred_obj,
            },
            "roll25_cache": {
                "status": "OK" if roll_status == "OK" else roll_status,
                "latest_report": roll_obj,
                "derived": roll25_derived,
            },
            "taiwan_margin_financing": {
                "status": "OK" if twm_status == "OK" else twm_status,
                "latest": twm_obj,
                "cross_module": cross_module if cross_module else None,
            },
            "fx_usdtwd": {
                "status": "OK" if fx_status == "OK" else fx_status,
                "latest": fx_obj,
                "derived": fx_derived,
            },
        },
        "audit_notes": [
            "Roll25 derived metrics are computed from roll25_cache/latest_report.json only (no external fetch).",
            "FX derived metrics are computed from fx_cache/history.json (local) + fx_cache/latest.json (local).",
            "Margin×Roll25 cross_module is computed deterministically from twmargin latest + roll25 latest only (no external fetch).",
            "Signal rules are deterministic; missing data => NA and confidence downgrade (no guessing).",
        ],
    }

    # avoid emitting null cross_module for cleanliness
    if unified["modules"]["taiwan_margin_financing"].get("cross_module") is None:
        unified["modules"]["taiwan_margin_financing"].pop("cross_module", None)

    _dump_json(args.out, unified)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())