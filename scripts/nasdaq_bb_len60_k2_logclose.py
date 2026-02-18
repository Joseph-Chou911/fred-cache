#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nasdaq_bb_len60_k2_logclose.py

Goal
-----
1) Fetch Nasdaq proxy price series (default: ^NDX) and compute Bollinger Bands (len=60, k=2)
   on log(close) by default (audit-friendly, stable across price scales).
2) Optionally fetch Cboe Nasdaq-100 Volatility Index (VXN) history (via Cboe endpoint if available,
   otherwise via FRED as a reliable fallback) and compute the same BB diagnostics.
3) Produce an "action snippet" JSON + a small CSV for quick inspection.
4) Compute conditional forward drawdown statistics after "touch lower band" triggers.

This is a risk-monitoring utility, NOT a prediction engine.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import time
import urllib.parse
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import requests


# ---------------------------
# Utilities
# ---------------------------

def _utc_now_iso() -> str:
    return pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _http_get(url: str, timeout: int = 30, max_retries: int = 3, backoff_s: float = 1.5) -> bytes:
    last_err = None
    headers = {"User-Agent": "risk-dashboard-bb-script/1.0"}
    for i in range(max_retries):
        try:
            r = requests.get(url, timeout=timeout, headers=headers)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            return r.content
        except Exception as e:
            last_err = e
            if i < max_retries - 1:
                time.sleep(backoff_s * (i + 1))
    raise RuntimeError(f"GET failed after {max_retries} retries: {url}\nLast error: {last_err}")


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    try:
        from io import BytesIO
        return pd.read_csv(BytesIO(content))
    except UnicodeDecodeError:
        from io import BytesIO
        return pd.read_csv(BytesIO(content), encoding="latin-1")


def _pick_date_col(df: pd.DataFrame) -> str:
    candidates = [c for c in df.columns if str(c).strip().lower() in ("date", "trade date", "timestamp")]
    if candidates:
        return candidates[0]
    for c in df.columns:
        if "date" in str(c).strip().lower():
            return c
    raise ValueError(f"Cannot find a date column in columns={list(df.columns)[:10]}...")


def _pick_close_col(df: pd.DataFrame) -> str:
    for name in ("close", "closing", "close value", "vix close", "vxn close", "close*"):
        for c in df.columns:
            if str(c).strip().lower() == name:
                return c

    close_like = [c for c in df.columns if "close" in str(c).strip().lower()]
    if close_like:
        close_like.sort(key=lambda x: len(str(x)))
        return close_like[0]

    if "Close" in df.columns:
        return "Close"

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if numeric_cols:
        return numeric_cols[-1]
    raise ValueError(f"Cannot find a close column in columns={list(df.columns)[:10]}...")


def _coerce_ohlc_df(df: pd.DataFrame, date_col: str, close_col: str) -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col])
    out = out.sort_values(date_col)
    out = out.set_index(date_col)

    out[close_col] = pd.to_numeric(out[close_col], errors="coerce")
    out = out.dropna(subset=[close_col])

    out = out[~out.index.duplicated(keep="last")]
    out = out.rename(columns={close_col: "close"})
    return out[["close"]]


# ---------------------------
# Data sources
# ---------------------------

def fetch_stooq_daily(ticker: str) -> Tuple[pd.DataFrame, Dict]:
    """
    Stooq daily CSV endpoint:
      https://stooq.com/q/d/l/?s=%5Endx&i=d
    """
    sym = urllib.parse.quote_plus(ticker.lower())
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    content = _http_get(url)
    raw = _read_csv_bytes(content)
    date_col = _pick_date_col(raw)
    close_col = _pick_close_col(raw)
    df = _coerce_ohlc_df(raw, date_col=date_col, close_col=close_col)

    meta = {
        "source": "stooq",
        "url": url,
        "date_col": date_col,
        "close_col": close_col,
        "rows": int(df.shape[0]),
        "min_date": str(df.index.min().date()),
        "max_date": str(df.index.max().date()),
    }
    return df, meta


def fetch_fred_daily(series_id: str) -> Tuple[pd.DataFrame, Dict]:
    """
    FRED CSV endpoint (no API key required for this download format):
      https://fred.stlouisfed.org/graph/fredgraph.csv?id=VXNCLS
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    content = _http_get(url)
    raw = _read_csv_bytes(content)

    date_col = "DATE" if "DATE" in raw.columns else _pick_date_col(raw)

    if series_id in raw.columns:
        value_col = series_id
    elif "VALUE" in raw.columns:
        value_col = "VALUE"
    else:
        value_col = _pick_close_col(raw)

    df = raw[[date_col, value_col]].copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[date_col, value_col]).sort_values(date_col).set_index(date_col)
    df = df.rename(columns={value_col: "close"})

    meta = {
        "source": "fred",
        "url": url,
        "series_id": series_id,
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df.index.min().date()),
        "max_date": str(df.index.max().date()),
    }
    return df, meta


def fetch_cboe_daily_prices(index_code: str) -> Tuple[pd.DataFrame, Dict]:
    """
    Cboe daily prices endpoint used by multiple indices (e.g., VIX_History.csv):
      https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv

    NOTE:
      - Some environments may receive 403/429; this function is best-effort.
      - If you get blocked, use FRED fallback which still cites Cboe as the source in series notes.
    """
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{index_code.upper()}_History.csv"
    content = _http_get(url)
    raw = _read_csv_bytes(content)
    date_col = _pick_date_col(raw)
    close_col = _pick_close_col(raw)
    df = _coerce_ohlc_df(raw, date_col=date_col, close_col=close_col)

    meta = {
        "source": "cboe",
        "url": url,
        "index_code": index_code.upper(),
        "date_col": date_col,
        "close_col": close_col,
        "rows": int(df.shape[0]),
        "min_date": str(df.index.min().date()),
        "max_date": str(df.index.max().date()),
    }
    return df, meta


# ---------------------------
# BB calculations
# ---------------------------

@dataclasses.dataclass(frozen=True)
class BBParams:
    length: int = 60
    k: float = 2.0
    use_log: bool = True
    ddof: int = 0  # 0=population std, 1=sample std


def compute_bollinger(df: pd.DataFrame, params: BBParams) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("df must have a 'close' column")

    out = df.copy().sort_index()

    if params.use_log:
        if (out["close"] <= 0).any():
            raise ValueError("Found non-positive close while use_log=True")
        out["x"] = np.log(out["close"].astype(float))
    else:
        out["x"] = out["close"].astype(float)

    w = int(params.length)
    if w < 2:
        raise ValueError("length must be >= 2")

    out["ma"] = out["x"].rolling(window=w, min_periods=w).mean()
    out["sd"] = out["x"].rolling(window=w, min_periods=w).std(ddof=int(params.ddof))

    out["upper_x"] = out["ma"] + params.k * out["sd"]
    out["lower_x"] = out["ma"] - params.k * out["sd"]

    if params.use_log:
        out["mid_price"] = np.exp(out["ma"])
        out["upper_price"] = np.exp(out["upper_x"])
        out["lower_price"] = np.exp(out["lower_x"])
    else:
        out["mid_price"] = out["ma"]
        out["upper_price"] = out["upper_x"]
        out["lower_price"] = out["lower_x"]

    out["z"] = (out["x"] - out["ma"]) / out["sd"]
    out["bandwidth_pct"] = (out["upper_price"] - out["lower_price"]) / out["mid_price"]

    walk = np.zeros(len(out), dtype=int)
    close = out["close"].to_numpy()
    lower = out["lower_price"].to_numpy()
    for i in range(len(out)):
        if np.isfinite(lower[i]) and close[i] <= lower[i]:
            walk[i] = (walk[i - 1] + 1) if i > 0 else 1
        else:
            walk[i] = 0
    out["walk_count"] = walk

    return out


def forward_max_drawdown(close: np.ndarray) -> float:
    if close.size < 2:
        return np.nan
    c0 = close[0]
    m = np.min(close[1:])
    return float(m / c0 - 1.0)


def conditional_pain_stats(df_bb: pd.DataFrame, z_thresh: float = -2.0, horizon: int = 20) -> Dict:
    df = df_bb.dropna(subset=["z", "close"]).copy()
    triggers = df[df["z"] <= z_thresh].copy()
    idx = df.index.to_list()
    close = df["close"].to_numpy()

    pos_map = {d: i for i, d in enumerate(idx)}
    dd_list = []
    for d in triggers.index:
        i = pos_map.get(d)
        if i is None:
            continue
        j = min(i + horizon, len(close) - 1)
        window = close[i : j + 1]
        if window.size >= 2:
            dd_list.append(forward_max_drawdown(window))

    if len(dd_list) == 0:
        return {
            "z_thresh": z_thresh,
            "horizon_days": horizon,
            "sample_size": 0,
            "p50_maxdd": None,
            "p90_maxdd": None,
            "mean_maxdd": None,
        }

    arr = np.array(dd_list, dtype=float)
    return {
        "z_thresh": z_thresh,
        "horizon_days": horizon,
        "sample_size": int(arr.size),
        "p50_maxdd": float(np.nanpercentile(arr, 50)),
        "p90_maxdd": float(np.nanpercentile(arr, 90)),
        "mean_maxdd": float(np.nanmean(arr)),
        "min_maxdd": float(np.nanmin(arr)),
        "max_maxdd": float(np.nanmax(arr)),
    }


def decide_action(latest: pd.Series, bw_delta_pct: Optional[float]) -> str:
    z = latest.get("z", np.nan)
    walk = latest.get("walk_count", 0)
    if not np.isfinite(z):
        return "INSUFFICIENT_DATA"

    if walk >= 3:
        return "LOCKOUT_WALKING_BAND (DO_NOT_CATCH_FALLING_KNIFE)"

    if bw_delta_pct is not None and bw_delta_pct >= 10.0 and z <= -2.0:
        return "LOCKOUT_VOL_EXPANSION (WAIT)"

    if z <= -3.0:
        return "EXTREME_TAIL_RISK (WAIT)"
    if z <= -2.0:
        return "LOWER_BAND_TOUCH (MONITOR / SCALE_IN_ONLY)"
    if z <= -1.5:
        return "NEAR_LOWER_BAND (MONITOR)"
    return "NORMAL_RANGE"


def build_snippet(name: str, df_bb: pd.DataFrame, pain: Dict, params: BBParams, meta: Dict) -> Dict:
    df = df_bb.dropna(subset=["ma", "sd", "upper_price", "lower_price", "z"]).copy()
    if df.empty:
        return {
            "name": name,
            "status": "INSUFFICIENT_DATA",
            "meta": meta,
            "params": dataclasses.asdict(params),
            "generated_at_utc": _utc_now_iso(),
        }

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    bw_delta_pct = None
    if prev is not None and np.isfinite(prev["bandwidth_pct"]) and prev["bandwidth_pct"] != 0:
        bw_delta_pct = float((latest["bandwidth_pct"] / prev["bandwidth_pct"] - 1.0) * 100.0)

    return {
        "name": name,
        "generated_at_utc": _utc_now_iso(),
        "meta": meta,
        "params": dataclasses.asdict(params),
        "latest": {
            "date": str(latest.name.date()),
            "close": float(latest["close"]),
            "bb_mid": float(latest["mid_price"]),
            "bb_lower": float(latest["lower_price"]),
            "bb_upper": float(latest["upper_price"]),
            "z": float(latest["z"]),
            "bandwidth_pct": float(latest["bandwidth_pct"]),
            "bandwidth_delta_pct": bw_delta_pct,
            "walk_count": int(latest["walk_count"]),
        },
        "historical_simulation": pain,
        "action_output": decide_action(latest, bw_delta_pct),
    }


# ---------------------------
# Main
# ---------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Nasdaq BB(60,2) monitor (logclose) + optional Cboe/FRED VXN fetch",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--price_source", choices=["stooq"], default="stooq", help="Price data source")
    p.add_argument("--price_ticker", default="^ndx", help="Ticker for price series (Nasdaq proxy)")

    p.add_argument("--vxn_enable", action="store_true", help="Also fetch VXN (Nasdaq-100 implied vol) series")
    p.add_argument("--vxn_source", choices=["cboe", "fred"], default="cboe", help="VXN data source preference")
    p.add_argument("--vxn_code", default="VXN", help="Cboe index code (for cboe daily_prices endpoint)")
    p.add_argument("--vxn_fred_series", default="VXNCLS", help="FRED series id for VXN close")

    p.add_argument("--bb_len", type=int, default=60, help="Bollinger length")
    p.add_argument("--bb_k", type=float, default=2.0, help="Bollinger k (std multiplier)")
    p.add_argument("--use_log", action="store_true", default=True, help="Compute bands in log space")
    p.add_argument("--no_log", action="store_true", help="Disable log space; compute bands on raw close")
    p.add_argument("--ddof", type=int, choices=[0, 1], default=0, help="Std ddof (0=population, 1=sample)")

    p.add_argument("--z_thresh", type=float, default=-2.0, help="Trigger threshold in z space")
    p.add_argument("--horizon", type=int, default=20, help="Forward horizon (trading days) for max drawdown")

    p.add_argument("--out_dir", default="out_bb", help="Output directory")
    p.add_argument("--quiet", action="store_true", help="Less console output")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    use_log = bool(args.use_log) and (not bool(args.no_log))
    params = BBParams(length=args.bb_len, k=args.bb_k, use_log=use_log, ddof=args.ddof)

    _ensure_dir(args.out_dir)

    price_df, price_meta = fetch_stooq_daily(args.price_ticker)
    price_bb = compute_bollinger(price_df, params)
    price_pain = conditional_pain_stats(price_bb, z_thresh=args.z_thresh, horizon=args.horizon)

    price_snippet = build_snippet(
        name=f"PRICE_{args.price_ticker.upper()}_BB(len={params.length},k={params.k},log={params.use_log})",
        df_bb=price_bb,
        pain=price_pain,
        params=params,
        meta=price_meta,
    )

    price_json_path = os.path.join(args.out_dir, f"snippet_price_{args.price_ticker.lower()}.json")
    with open(price_json_path, "w", encoding="utf-8") as f:
        json.dump(price_snippet, f, ensure_ascii=False, indent=2)

    price_csv_path = os.path.join(args.out_dir, f"tail_price_{args.price_ticker.lower()}.csv")
    price_bb.tail(200).to_csv(price_csv_path, index=True)

    if not args.quiet:
        print("=== PRICE SNIPPET ===")
        print(json.dumps(price_snippet, ensure_ascii=False, indent=2))

    if args.vxn_enable:
        vxn_df = None
        vxn_meta = None
        errors = []

        sources = ["cboe", "fred"] if args.vxn_source == "cboe" else ["fred", "cboe"]
        for src in sources:
            try:
                if src == "cboe":
                    vxn_df, vxn_meta = fetch_cboe_daily_prices(args.vxn_code)
                else:
                    vxn_df, vxn_meta = fetch_fred_daily(args.vxn_fred_series)
                break
            except Exception as e:
                errors.append(f"{src}: {e}")

        if vxn_df is None:
            raise RuntimeError("Failed to fetch VXN from all sources:\n" + "\n".join(errors))

        vxn_bb = compute_bollinger(vxn_df, params)
        vxn_pain = conditional_pain_stats(vxn_bb, z_thresh=args.z_thresh, horizon=args.horizon)
        vxn_snippet = build_snippet(
            name=f"VXN_BB(len={params.length},k={params.k},log={params.use_log})",
            df_bb=vxn_bb,
            pain=vxn_pain,
            params=params,
            meta={"attempt_errors": errors, **(vxn_meta or {})},
        )

        vxn_json_path = os.path.join(args.out_dir, "snippet_vxn.json")
        with open(vxn_json_path, "w", encoding="utf-8") as f:
            json.dump(vxn_snippet, f, ensure_ascii=False, indent=2)

        vxn_csv_path = os.path.join(args.out_dir, "tail_vxn.csv")
        vxn_bb.tail(200).to_csv(vxn_csv_path, index=True)

        if not args.quiet:
            print("\n=== VXN SNIPPET ===")
            print(json.dumps(vxn_snippet, ensure_ascii=False, indent=2))

    if not args.quiet:
        print("\nWrote:")
        print(f"- {price_json_path}")
        print(f"- {price_csv_path}")
        if args.vxn_enable:
            print(f"- {os.path.join(args.out_dir, 'snippet_vxn.json')}")
            print(f"- {os.path.join(args.out_dir, 'tail_vxn.csv')}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)