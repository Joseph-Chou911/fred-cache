#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nasdaq BB monitor: QQQ (price) + VXN (vol).

- Computes Bollinger Bands BB(len,k) on log-close by default.
- Emits JSON snippets for report generation.

Outputs (under --out_dir):
  snippet_price.json
  snippet_vxn.json (if --vxn_enable)

Data sources
- PRICE: Stooq CSV
- VXN:   CBOE CSV (primary) with optional FRED CSV fallback

Metric invariants (enforced by clamping)
- forward_mdd <= 0
- forward_max_runup >= 0

Note
- bandwidth_pct is stored as a ratio (e.g. 0.0654 == 6.54%).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_get_text(url: str, timeout: int = 20, retries: int = 3, backoff: float = 1.8) -> Tuple[str, List[str]]:
    """Return (text, errors). If all retries fail, raises RuntimeError."""
    errors: List[str] = []
    headers = {"User-Agent": "nasdaq-bb-monitor/1.0"}
    for i in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp.text, errors
        except Exception as e:  # noqa: BLE001
            errors.append(f"try#{i+1}: {type(e).__name__}: {e}")
            time.sleep(backoff ** i)
    raise RuntimeError(f"GET failed: {url} | errors=" + " | ".join(errors))


def _standardize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with columns: date (datetime64[ns]), close (float), sorted asc, no NaNs."""
    date_col = None
    for c in ["Date", "DATE", "date", "observation_date", "Observation Date"]:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        raise ValueError(f"Cannot find date column in columns={list(df.columns)}")

    close_col = None
    for c in ["Close", "CLOSE", "close", "VALUE", "value"]:
        if c in df.columns:
            close_col = c
            break
    if close_col is None:
        if len(df.columns) >= 2:
            close_col = df.columns[-1]
        else:
            raise ValueError(f"Cannot find close/value column in columns={list(df.columns)}")

    out = df[[date_col, close_col]].copy()
    out.columns = ["date", "close"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).sort_values("date")
    return out


def fetch_stooq_daily(ticker: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
    text, errs = _http_get_text(url)
    df = pd.read_csv(StringIO(text))
    sdf = _standardize_df(df)
    meta = {
        "source": "stooq",
        "url": url,
        "rows": int(len(sdf)),
        "min_date": str(sdf["date"].min().date()) if len(sdf) else None,
        "max_date": str(sdf["date"].max().date()) if len(sdf) else None,
        "attempt_errors": errs,
    }
    return sdf, meta


def fetch_cboe_index_history(code: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{code}_History.csv"
    text, errs = _http_get_text(url)
    df = pd.read_csv(StringIO(text))
    sdf = _standardize_df(df)
    meta = {
        "source": "cboe",
        "url": url,
        "rows": int(len(sdf)),
        "min_date": str(sdf["date"].min().date()) if len(sdf) else None,
        "max_date": str(sdf["date"].max().date()) if len(sdf) else None,
        "attempt_errors": errs,
    }
    return sdf, meta


def fetch_fred_series_csv(series_id: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    text, errs = _http_get_text(url)
    df = pd.read_csv(StringIO(text))
    sdf = _standardize_df(df)
    meta = {
        "source": "fred",
        "url": url,
        "rows": int(len(sdf)),
        "min_date": str(sdf["date"].min().date()) if len(sdf) else None,
        "max_date": str(sdf["date"].max().date()) if len(sdf) else None,
        "attempt_errors": errs,
    }
    return sdf, meta


def compute_bb_features(df: pd.DataFrame, bb_len: int, bb_k: float, use_log: bool = True, ddof: int = 0) -> pd.DataFrame:
    s = df.set_index("date")["close"].astype(float)
    x = np.log(s) if use_log else s.copy()

    ma = x.rolling(bb_len).mean()
    sd = x.rolling(bb_len).std(ddof=ddof)

    upper = ma + bb_k * sd
    lower = ma - bb_k * sd

    if use_log:
        bb_mid = np.exp(ma)
        bb_upper = np.exp(upper)
        bb_lower = np.exp(lower)
    else:
        bb_mid = ma
        bb_upper = upper
        bb_lower = lower

    z = (x - ma) / sd

    out = pd.DataFrame({"close": s, "bb_mid": bb_mid, "bb_lower": bb_lower, "bb_upper": bb_upper, "z": z})
    out["distance_to_lower_pct"] = (out["close"] - out["bb_lower"]) / out["close"] * 100.0
    out["distance_to_upper_pct"] = (out["bb_upper"] - out["close"]) / out["close"] * 100.0
    out["position_in_band"] = (out["close"] - out["bb_lower"]) / (out["bb_upper"] - out["bb_lower"])
    out["bandwidth_pct"] = (out["bb_upper"] - out["bb_lower"]) / out["bb_mid"]  # ratio (not percent)
    out["bandwidth_delta_pct"] = out["bandwidth_pct"].pct_change() * 100.0
    return out


def _last_walk_count(cond: pd.Series) -> int:
    c = 0
    for v in cond.fillna(False).to_numpy()[::-1]:
        if bool(v):
            c += 1
        else:
            break
    return int(c)


def _pick_trigger_indices(z: pd.Series, mode: str, thresh: float, cooldown_bars: int) -> List[int]:
    idx: List[int] = []
    last = -10**9
    arr = z.to_numpy()
    for i, v in enumerate(arr):
        if not np.isfinite(v):
            continue
        ok = (v <= thresh) if mode == "le" else (v >= thresh)
        if ok and (i - last) >= cooldown_bars:
            idx.append(i)
            last = i
    return idx


def _forward_mdd(close: pd.Series, i: int, horizon: int) -> Optional[float]:
    c0 = float(close.iloc[i])
    fut = close.iloc[i + 1 : i + 1 + horizon]
    if len(fut) < horizon:
        return None
    mdd_raw = float(fut.min() / c0 - 1.0)
    return min(0.0, mdd_raw)  # clamp to <=0


def _forward_max_runup(close: pd.Series, i: int, horizon: int) -> Optional[float]:
    c0 = float(close.iloc[i])
    fut = close.iloc[i + 1 : i + 1 + horizon]
    if len(fut) < horizon:
        return None
    ru_raw = float(fut.max() / c0 - 1.0)
    return max(0.0, ru_raw)  # clamp to >=0


def _summarize_samples(samples: List[float]) -> Dict[str, Any]:
    arr = np.asarray(samples, dtype=float)
    return {
        "sample_size": int(arr.size),
        "p10": float(np.quantile(arr, 0.10)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "mean": float(arr.mean()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def simulate_price_forward_mdd(bb: pd.DataFrame, z_thresh: float, horizon_days: int, cooldown_bars: int) -> Dict[str, Any]:
    close = bb["close"]
    z = bb["z"]
    trigger_idx = _pick_trigger_indices(z, "le", z_thresh, cooldown_bars)

    samples: List[float] = []
    for i in trigger_idx:
        v = _forward_mdd(close, i, horizon_days)
        if v is not None:
            samples.append(v)

    out: Dict[str, Any] = {
        "metric": "forward_mdd",
        "metric_interpretation": "<=0; closer to 0 is less pain; more negative is deeper drawdown",
        "z_thresh": float(z_thresh),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
    }
    out.update(_summarize_samples(samples) if samples else {"sample_size": 0})
    return out


def simulate_vol_forward_runup(bb: pd.DataFrame, mode: str, z_thresh: float, horizon_days: int, cooldown_bars: int) -> Dict[str, Any]:
    close = bb["close"]
    z = bb["z"]
    trig_mode = "le" if mode == "A" else "ge"
    trigger_idx = _pick_trigger_indices(z, trig_mode, z_thresh, cooldown_bars)

    samples: List[float] = []
    for i in trigger_idx:
        v = _forward_max_runup(close, i, horizon_days)
        if v is not None:
            samples.append(v)

    interp = ">=0; larger means bigger spike risk" if mode == "A" else ">=0; larger means further spike continuation risk"
    out: Dict[str, Any] = {
        "metric": "forward_max_runup",
        "metric_interpretation": interp,
        "z_thresh": float(z_thresh),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
    }
    out.update(_summarize_samples(samples) if samples else {"sample_size": 0})
    return out


def decide_price_action(latest: Dict[str, Any], z_near: float, z_touch: float) -> Tuple[str, str]:
    z = float(latest["z"])
    if z <= z_touch:
        return "LOWER_BAND_TOUCH (WATCH)", f"z<={z_touch:g}"
    if z <= z_near:
        return "NEAR_LOWER_BAND (MONITOR)", f"z<={z_near:g}"
    return "NORMAL_RANGE", "none"


def decide_vxn_action(latest: Dict[str, Any], z_low: float, z_high: float, pos_watch: float) -> Tuple[str, str]:
    z = float(latest["z"])
    pos = float(latest["position_in_band"])
    if z >= z_high:
        return "HIGH_VOL_TAIL (ALERT)", f"z>={z_high:g}"
    if z <= z_low:
        return "LOW_VOL_TAIL (INFO)", f"z<={z_low:g}"
    if pos >= pos_watch:
        return "NEAR_UPPER_BAND (WATCH)", f"position_in_band>={pos_watch:g} (pos={pos:.3f})"
    return "NORMAL_RANGE", "none"


def build_price_snippet(
    bb: pd.DataFrame,
    meta: Dict[str, Any],
    params: Dict[str, Any],
    z_thresh: float,
    z_near: float,
    horizon_days: int,
    cooldown_bars: int,
) -> Dict[str, Any]:
    bb2 = bb.dropna().copy()
    if bb2.empty:
        raise RuntimeError("Not enough data to compute BB (price).")

    last = bb2.iloc[-1]
    walk_lower = _last_walk_count(bb2["close"] <= bb2["bb_lower"])

    latest = {
        "date": str(bb2.index[-1].date()),
        "close": float(last["close"]),
        "bb_mid": float(last["bb_mid"]),
        "bb_lower": float(last["bb_lower"]),
        "bb_upper": float(last["bb_upper"]),
        "z": float(last["z"]),
        "trigger_z_le_-2": bool(float(last["z"]) <= float(z_thresh)),
        "distance_to_lower_pct": float(last["distance_to_lower_pct"]),
        "distance_to_upper_pct": float(last["distance_to_upper_pct"]),
        "position_in_band": float(last["position_in_band"]),
        "bandwidth_pct": float(last["bandwidth_pct"]),
        "bandwidth_delta_pct": float(last["bandwidth_delta_pct"]) if np.isfinite(last["bandwidth_delta_pct"]) else None,
        "walk_lower_count": int(walk_lower),
    }

    action_output, trigger_reason = decide_price_action(latest, z_near=z_near, z_touch=z_thresh)
    hist = simulate_price_forward_mdd(bb2, z_thresh=z_thresh, horizon_days=horizon_days, cooldown_bars=cooldown_bars)

    return {
        "generated_at_utc": utc_now_iso(),
        "meta": meta,
        "params": params,
        "latest": latest,
        "historical_simulation": hist,
        "action_output": action_output,
        "trigger_reason": trigger_reason,
    }


def build_vxn_snippet(
    bb: pd.DataFrame,
    meta: Dict[str, Any],
    params: Dict[str, Any],
    z_low: float,
    z_high: float,
    pos_watch: float,
    horizon_days: int,
    cooldown_bars: int,
    selected_source: str,
    fallback_used: bool,
) -> Dict[str, Any]:
    bb2 = bb.dropna().copy()
    if bb2.empty:
        raise RuntimeError("Not enough data to compute BB (VXN).")

    last = bb2.iloc[-1]
    walk_upper = _last_walk_count(bb2["close"] >= bb2["bb_upper"])

    latest = {
        "date": str(bb2.index[-1].date()),
        "close": float(last["close"]),
        "bb_mid": float(last["bb_mid"]),
        "bb_lower": float(last["bb_lower"]),
        "bb_upper": float(last["bb_upper"]),
        "z": float(last["z"]),
        "trigger_z_le_-2": bool(float(last["z"]) <= float(z_low)),
        "trigger_z_ge_2": bool(float(last["z"]) >= float(z_high)),
        "distance_to_lower_pct": float(last["distance_to_lower_pct"]),
        "distance_to_upper_pct": float(last["distance_to_upper_pct"]),
        "position_in_band": float(last["position_in_band"]),
        "bandwidth_pct": float(last["bandwidth_pct"]),
        "bandwidth_delta_pct": float(last["bandwidth_delta_pct"]) if np.isfinite(last["bandwidth_delta_pct"]) else None,
        "walk_upper_count": int(walk_upper),
    }

    action_output, trigger_reason = decide_vxn_action(latest, z_low=z_low, z_high=z_high, pos_watch=pos_watch)
    active_regime = "A" if latest["trigger_z_le_-2"] else ("B" if latest["trigger_z_ge_2"] else "NONE")
    tail_b_applicable = bool(active_regime == "B")

    hist_a = simulate_vol_forward_runup(bb2, mode="A", z_thresh=z_low, horizon_days=horizon_days, cooldown_bars=cooldown_bars)
    hist_b = simulate_vol_forward_runup(bb2, mode="B", z_thresh=z_high, horizon_days=horizon_days, cooldown_bars=cooldown_bars)

    return {
        "generated_at_utc": utc_now_iso(),
        "meta": meta,
        "params": params,
        "latest": latest,
        "historical_simulation": {"A": hist_a, "B": hist_b},
        "action_output": action_output,
        "trigger_reason": trigger_reason,
        "active_regime": active_regime,
        "tail_B_applicable": tail_b_applicable,
        "selected_source": selected_source,
        "fallback_used": bool(fallback_used),
    }


def fetch_vxn_with_fallback(vxn_code: str, fred_series: str, policy: str) -> Tuple[pd.DataFrame, Dict[str, Any], str, bool]:
    attempt_errors: List[str] = []

    def _try(fetch_fn, label: str):
        nonlocal attempt_errors
        try:
            df, meta = fetch_fn()
            if attempt_errors:
                meta = dict(meta)
                meta["attempt_errors"] = attempt_errors + meta.get("attempt_errors", [])
            return df, meta, label
        except Exception as e:  # noqa: BLE001
            attempt_errors.append(f"{label}: {type(e).__name__}: {e}")
            return None, None, None

    if policy == "cboe_first":
        r = _try(lambda: fetch_cboe_index_history(vxn_code), "cboe")
        if r[0] is not None:
            return r[0], r[1], r[2], False
        r2 = _try(lambda: fetch_fred_series_csv(fred_series), "fred")
        if r2[0] is not None:
            return r2[0], r2[1], r2[2], True
    else:
        r = _try(lambda: fetch_fred_series_csv(fred_series), "fred")
        if r[0] is not None:
            return r[0], r[1], r[2], False
        r2 = _try(lambda: fetch_cboe_index_history(vxn_code), "cboe")
        if r2[0] is not None:
            return r2[0], r2[1], r2[2], True

    raise RuntimeError("All VXN sources failed: " + " | ".join(attempt_errors))


def write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--price_source", default="stooq", choices=["stooq"])
    ap.add_argument("--price_ticker", default="qqq.us")

    ap.add_argument("--vxn_enable", action="store_true")
    ap.add_argument("--vxn_code", default="VXN")

    # Primary name
    ap.add_argument("--fred_series", default="VXNCLS")
    # Backward/alt name (your current CLI/YML): --vxn_fred_series VXNCLS
    ap.add_argument("--vxn_fred_series", default=None)

    # Primary name
    ap.add_argument("--vxn_source", default="cboe_first", choices=["cboe_first", "fred_first"])
    # Alias (some configs may use this)
    ap.add_argument("--vxn_source_policy", default=None)

    ap.add_argument("--bb_len", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)
    ap.add_argument("--ddof", type=int, default=0)
    ap.add_argument("--no_log", action="store_true")

    ap.add_argument("--z_thresh", type=float, default=-2.0)
    ap.add_argument("--z_near", type=float, default=-1.5)
    ap.add_argument("--z_thresh_low", type=float, default=-2.0)
    ap.add_argument("--z_thresh_high", type=float, default=2.0)
    ap.add_argument("--pos_watch", type=float, default=0.8)

    ap.add_argument("--horizon_days", type=int, default=20)
    ap.add_argument("--cooldown_bars", type=int, default=20)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    # Apply aliases (so your existing YML/CLI keeps working)
    if args.vxn_fred_series:
        args.fred_series = args.vxn_fred_series
    if args.vxn_source_policy:
        args.vxn_source = args.vxn_source_policy

    use_log = not args.no_log

    price_df, price_meta = fetch_stooq_daily(args.price_ticker)
    price_params = {
        "price_source": args.price_source,
        "price_ticker": args.price_ticker,
        "bb_len": args.bb_len,
        "bb_k": args.bb_k,
        "ddof": args.ddof,
        "use_log": use_log,
        "z_thresh": args.z_thresh,
        "z_near": args.z_near,
        "horizon_days": args.horizon_days,
        "cooldown_bars": args.cooldown_bars,
    }
    price_bb = compute_bb_features(price_df, args.bb_len, args.bb_k, use_log=use_log, ddof=args.ddof)
    price_snip = build_price_snippet(
        price_bb, price_meta, price_params, args.z_thresh, args.z_near, args.horizon_days, args.cooldown_bars
    )
    write_json(os.path.join(args.out_dir, "snippet_price.json"), price_snip)

    if args.vxn_enable:
        vxn_df, vxn_meta, selected_source, fallback_used = fetch_vxn_with_fallback(
            args.vxn_code, args.fred_series, args.vxn_source
        )
        vxn_params = {
            "vxn_code": args.vxn_code,
            "fred_series": args.fred_series,
            "vxn_source_policy": args.vxn_source,
            "bb_len": args.bb_len,
            "bb_k": args.bb_k,
            "ddof": args.ddof,
            "use_log": use_log,
            "z_thresh_low": args.z_thresh_low,
            "z_thresh_high": args.z_thresh_high,
            "pos_watch": args.pos_watch,
            "horizon_days": args.horizon_days,
            "cooldown_bars": args.cooldown_bars,
        }
        vxn_bb = compute_bb_features(vxn_df, args.bb_len, args.bb_k, use_log=use_log, ddof=args.ddof)
        vxn_snip = build_vxn_snippet(
            vxn_bb,
            vxn_meta,
            vxn_params,
            args.z_thresh_low,
            args.z_thresh_high,
            args.pos_watch,
            args.horizon_days,
            args.cooldown_bars,
            selected_source,
            fallback_used,
        )
        write_json(os.path.join(args.out_dir, "snippet_vxn.json"), vxn_snip)

    if not args.quiet:
        print(os.path.join(args.out_dir, "snippet_price.json"))
        if args.vxn_enable:
            print(os.path.join(args.out_dir, "snippet_vxn.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())