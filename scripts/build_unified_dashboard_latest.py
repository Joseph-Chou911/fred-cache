#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build unified dashboard JSON from module outputs.

Adds:
- roll25_derived: N-day realized volatility (annualized) + max drawdown
- fx_usdtwd: USD/TWD spot mid (BOT) + ret1/chg_5d + deterministic signal rule

NO external fetch here. Pure merge + deterministic calculations.

Inputs (default paths are aligned with your unified_dashboard_latest_v1 sample):
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
    # cache_roll25 in sample is newest first; keep that order
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

    # take most recent (n+1) closes, newest->oldest
    closes = closes_newest_first[: n + 1]
    # compute log returns for n intervals: r_t = ln(C_t / C_{t-1}) where t is newer
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
    Use series ordered newest->oldest; we evaluate on chronological order oldest->newest.
    Returns (max_drawdown_pct as negative number, points_used).
    """
    if n <= 1:
        return None, 0
    if len(closes_newest_first) < n:
        return None, 0

    # convert to oldest->newest
    series = list(reversed(closes_newest_first[:n]))
    peak = -1e100
    max_dd = 0.0  # negative or 0
    for c in series:
        if c > peak:
            peak = c
        if peak > 0:
            dd = (c / peak) - 1.0
            if dd < max_dd:
                max_dd = dd
    return max_dd * 100.0, len(series)


# ---------- FX derived metrics ----------

def _load_fx_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        obj = _load_json(path)
        items = obj.get("items") if isinstance(obj, dict) else None
        if isinstance(items, list):
            # ensure sorted ascending by date (fetcher already does)
            return [x for x in items if isinstance(x, dict) and isinstance(x.get("date"), str)]
    except Exception:
        return []
    return []


def _fx_ret1_and_chg5(history_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute ret1% and 5d change% from history (ascending by date).
    ret1%: last vs prev
    chg_5d%: last vs 5 trading days ago (index -6)
    """
    mids: List[float] = []
    dates: List[str] = []
    for it in history_items:
        mid = it.get("mid")
        if isinstance(mid, (int, float)):
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
        # Apply thresholds only on available metrics
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

        # Confidence downgrade if window not full (you already track LookbackNActual/Target)
        lookback_actual = _safe_get(roll_obj, "lookback_n_actual")
        lookback_target = _safe_get(roll_obj, "numbers", "LookbackNTarget")  # may be absent in report
        if lookback_target is None:
            lookback_target = _safe_get(roll_obj, "LookbackNTarget")
        confidence = "OK"
        if isinstance(lookback_actual, int) and isinstance(lookback_target, int) and lookback_actual < lookback_target:
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

        # Directional label (NOT a forecast): USD/TWD down => TWD stronger
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
            "Signal rules are deterministic; missing data => NA and confidence downgrade (no guessing).",
        ],
    }

    _dump_json(args.out, unified)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())