#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compute 0050 (ticker default: 0050.TW) Bollinger Bands (60, 2) and forward MDD (20D),
then write audit-friendly artifacts:

- <cache_dir>/data.csv                (merged OHLCV from Yahoo Finance)
- <cache_dir>/stats_latest.json       (latest BB + distribution of forward_mdd_20d)
- <cache_dir>/history_lite.json       (last N rows: date, price, z, band_pos, fwd_mdd)

Data source: yfinance (Yahoo Finance).
Default uses Adj Close for computations to account for distributions/splits over long horizons.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception as e:
    raise SystemExit(
        "ERROR: yfinance not installed. Please `pip install yfinance`.\n"
        f"Original error: {e}"
    )


# -----------------------------
# Helpers
# -----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float, np.floating)) and not (isinstance(x, float) and math.isnan(x)):
        return float(x)
    try:
        s = str(x).strip()
        if s in ("", "N/A", "NA", "nan", "None"):
            return None
        return float(s)
    except Exception:
        return None


def _safe_pct(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return float(x) * 100.0


def _quantile(values: np.ndarray, q: float) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.quantile(values, q))


def normalize_yf_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance may return:
      - normal columns: ["Open","High","Low","Close","Adj Close","Volume"]
      - or MultiIndex columns for some versions/tickers
    This function flattens and standardizes to:
      date index (DatetimeIndex), columns: open/high/low/close/adjclose/volume
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # flatten multiindex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join([str(x) for x in col if str(x) != ""]).strip() for col in df.columns]

    colmap = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "")
        if cl == "open":
            colmap[c] = "open"
        elif cl == "high":
            colmap[c] = "high"
        elif cl == "low":
            colmap[c] = "low"
        elif cl == "close":
            colmap[c] = "close"
        elif cl in ("adjclose", "adjclose*"):
            colmap[c] = "adjclose"
        elif cl == "volume":
            colmap[c] = "volume"

    out = df.rename(columns=colmap).copy()
    # Keep only known columns
    keep = [c for c in ["open", "high", "low", "close", "adjclose", "volume"] if c in out.columns]
    out = out[keep].copy()
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    return out


def load_existing_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if "date" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        return df
    except Exception:
        return pd.DataFrame()


def save_csv_with_date_index(df: pd.DataFrame, path: str) -> None:
    out = df.copy()
    out = out.sort_index()
    out.index.name = "date"
    out.reset_index().to_csv(path, index=False)


@dataclass
class DQ:
    flags: List[str]
    notes: List[str]

    def add(self, flag: str, note: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)
        self.notes.append(note)


# -----------------------------
# Core calculations
# -----------------------------

def compute_bb(
    price: pd.Series,
    window: int,
    k: float,
) -> pd.DataFrame:
    ma = price.rolling(window=window, min_periods=window).mean()
    # Use population std (ddof=0) for deterministic BB; if you prefer sample std, change ddof=1.
    sd = price.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd

    z = (price - ma) / sd
    band_pos = (price - lower) / (upper - lower)  # 0..1, may exceed if outside band

    out = pd.DataFrame(
        {
            "bb_ma": ma,
            "bb_sd": sd,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_z": z,
            "bb_pos": band_pos,
        }
    )
    return out


def compute_forward_mdd_from_entry(price: np.ndarray, fwd_days: int) -> np.ndarray:
    """
    forward_mdd[t] = min_{k=1..fwd_days} (price[t+k]/price[t] - 1)
    Interpreted as "worst drawdown from entry price within next fwd_days".
    """
    n = price.shape[0]
    out = np.full(n, np.nan, dtype=float)
    if n <= fwd_days:
        return out

    for t in range(0, n - fwd_days):
        p0 = price[t]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        window = price[t + 1 : t + fwd_days + 1]
        window = window[np.isfinite(window)]
        if window.size == 0:
            continue
        min_p = window.min()
        out[t] = (min_p / p0) - 1.0
    return out


def classify_bb_state(z: Optional[float]) -> str:
    """
    Simple, deterministic label only based on z (no "prediction").
    """
    if z is None or not np.isfinite(z):
        return "NA"
    if z <= -2.0:
        return "EXTREME_LOWER_BAND"
    if z <= -1.5:
        return "NEAR_LOWER_BAND"
    if z >= 2.0:
        return "EXTREME_UPPER_BAND"
    if z >= 1.5:
        return "NEAR_UPPER_BAND"
    return "MID_BAND"


def main() -> None:
    p = argparse.ArgumentParser(
        description="0050 BB(60,2) + forward_mdd(20D) calculator (standalone, audit-friendly)."
    )
    p.add_argument("--ticker", default="0050.TW", help="Yahoo Finance ticker. Default: 0050.TW")
    p.add_argument("--cache_dir", default="tw0050_bb_cache", help="Output directory.")
    p.add_argument("--start", default="2003-01-01", help="Start date (YYYY-MM-DD). Default: 2003-01-01")
    p.add_argument("--bb_window", type=int, default=60, help="BB window. Default: 60")
    p.add_argument("--bb_k", type=float, default=2.0, help="BB k. Default: 2.0")
    p.add_argument("--fwd_days", type=int, default=20, help="Forward window (trading days). Default: 20")
    p.add_argument(
        "--price_col",
        choices=["adjclose", "close"],
        default="adjclose",
        help="Which price column to use for calculations. Default: adjclose",
    )
    p.add_argument("--use_log_price", action="store_true", help="Compute BB on log(price).")
    p.add_argument("--history_keep", type=int, default=400, help="Keep last N rows in history_lite.json")
    p.add_argument("--tz", default="Asia/Taipei", help="Timezone label for report metadata. Default: Asia/Taipei")
    args = p.parse_args()

    ensure_dir(args.cache_dir)
    dq = DQ(flags=[], notes=[])

    run_ts_utc = utc_now_iso()
    data_csv_path = os.path.join(args.cache_dir, "data.csv")
    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    hist_path = os.path.join(args.cache_dir, "history_lite.json")

    # Load existing to allow incremental merge
    existing = load_existing_csv(data_csv_path)

    # Decide fetch range
    fetch_start = args.start
    if not existing.empty:
        last_dt = existing.index.max()
        # fetch from a bit earlier to handle revisions / timezone / last row overlap
        fetch_start = (last_dt - pd.Timedelta(days=14)).date().isoformat()

    # Fetch
    try:
        raw = yf.download(
            tickers=args.ticker,
            start=fetch_start,
            auto_adjust=False,
            progress=False,
            interval="1d",
            actions=False,
            group_by="column",
        )
    except Exception as e:
        raise SystemExit(f"ERROR: yfinance download failed: {e}")

    df_new = normalize_yf_df(raw)
    if df_new.empty:
        raise SystemExit("ERROR: Empty data from yfinance. (ticker wrong? network blocked? Yahoo transient?)")

    # Merge existing + new
    if not existing.empty:
        merged = pd.concat([existing, df_new], axis=0)
        merged = merged[~merged.index.duplicated(keep="last")]
        merged = merged.sort_index()
    else:
        merged = df_new

    # Basic DQ
    if "adjclose" not in merged.columns:
        dq.add("MISSING_ADJCLOSE", "Yahoo data did not provide Adj Close; falling back to Close when needed.")
        merged["adjclose"] = merged["close"]

    if merged.shape[0] < (args.bb_window + args.fwd_days + 10):
        dq.add(
            "INSUFFICIENT_HISTORY",
            f"Rows={merged.shape[0]} < bb_window({args.bb_window}) + fwd_days({args.fwd_days}) + buffer.",
        )

    # Persist merged data
    save_csv_with_date_index(merged, data_csv_path)

    # Select price series
    price_used_col = args.price_col
    price_series = merged[price_used_col].copy()

    # Check non-positive values for log
    if args.use_log_price:
        if (price_series <= 0).any():
            dq.add("NON_POSITIVE_PRICE", "Non-positive prices exist; log(price) invalid for those rows.")
        price_calc = np.log(price_series.replace(0, np.nan))
        price_calc_name = f"log({price_used_col})"
    else:
        price_calc = price_series.copy()
        price_calc_name = price_used_col

    # BB
    bb = compute_bb(price_calc, window=args.bb_window, k=args.bb_k)
    out = pd.concat([merged, bb], axis=1)

    # Distances (computed on original level price to be intuitive; still deterministic)
    upper = out["bb_upper"]
    lower = out["bb_lower"]

    # If log mode, convert upper/lower back to level space for distance display
    if args.use_log_price:
        upper_level = np.exp(upper)
        lower_level = np.exp(lower)
        price_level = price_series
    else:
        upper_level = upper
        lower_level = lower
        price_level = price_series

    dist_to_lower = (price_level - lower_level) / price_level
    dist_to_upper = (upper_level - price_level) / price_level

    out["dist_to_lower_pct"] = _safe_pct(dist_to_lower)
    out["dist_to_upper_pct"] = _safe_pct(dist_to_upper)

    # forward_mdd_20d on LEVEL price (entry drawdown)
    price_np = price_series.to_numpy(dtype=float)
    fwd_mdd = compute_forward_mdd_from_entry(price_np, fwd_days=args.fwd_days)
    out[f"forward_mdd_{args.fwd_days}d"] = fwd_mdd

    # Latest snapshot
    latest_idx = out.index.max()
    latest_row = out.loc[latest_idx]

    latest_z = _to_float(latest_row.get("bb_z"))
    latest_pos = _to_float(latest_row.get("bb_pos"))

    # Distribution stats of forward_mdd over history where it is defined
    fwd_vals = out[f"forward_mdd_{args.fwd_days}d"].dropna().to_numpy(dtype=float)
    fwd_n = int(fwd_vals.size)

    if fwd_n < 200:
        dq.add("LOW_SAMPLE_FORWARD_MDD", f"forward_mdd sample size is small (n={fwd_n}).")

    stats = {
        "meta": {
            "run_ts_utc": run_ts_utc,
            "module": "tw0050_bb",
            "ticker": args.ticker,
            "data_source": "yfinance_yahoo",
            "tz": args.tz,
            "start": args.start,
            "fetch_start_effective": fetch_start,
            "bb_window": args.bb_window,
            "bb_k": args.bb_k,
            "fwd_days": args.fwd_days,
            "price_col_requested": args.price_col,
            "price_col_used": price_used_col,
            "price_calc": price_calc_name,
            "rows": int(out.shape[0]),
            "last_date": latest_idx.date().isoformat(),
        },
        "dq": {
            "flags": dq.flags,
            "notes": dq.notes,
        },
        "latest": {
            "date": latest_idx.date().isoformat(),
            "close": _to_float(latest_row.get("close")),
            "adjclose": _to_float(latest_row.get("adjclose")),
            "price_used": _to_float(price_series.loc[latest_idx]) if latest_idx in price_series.index else None,
            "bb_ma": _to_float(latest_row.get("bb_ma")),
            "bb_sd": _to_float(latest_row.get("bb_sd")),
            "bb_upper": _to_float(latest_row.get("bb_upper")),
            "bb_lower": _to_float(latest_row.get("bb_lower")),
            "bb_z": latest_z,
            "bb_pos": latest_pos,
            "dist_to_lower_pct": _to_float(latest_row.get("dist_to_lower_pct")),
            "dist_to_upper_pct": _to_float(latest_row.get("dist_to_upper_pct")),
            "state": classify_bb_state(latest_z),
        },
        "forward_mdd": {
            "definition": f"min(price[t+1..t+{args.fwd_days}]/price[t]-1), level-price based",
            "n": fwd_n,
            "p50": _quantile(fwd_vals, 0.50),
            "p25": _quantile(fwd_vals, 0.25),
            "p10": _quantile(fwd_vals, 0.10),
            "p05": _quantile(fwd_vals, 0.05),
            "min": float(np.min(fwd_vals)) if fwd_n > 0 else None,
        },
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, sort_keys=True)

    # history_lite.json (keep last N rows, include forward_mdd for those dates)
    tail = out.tail(args.history_keep).copy()
    hist_items: List[Dict[str, Any]] = []
    for idx, r in tail.iterrows():
        hist_items.append(
            {
                "date": idx.date().isoformat(),
                "price": _to_float(price_series.loc[idx]) if idx in price_series.index else None,
                "bb_z": _to_float(r.get("bb_z")),
                "bb_pos": _to_float(r.get("bb_pos")),
                f"forward_mdd_{args.fwd_days}d": _to_float(r.get(f"forward_mdd_{args.fwd_days}d")),
            }
        )

    hist = {
        "meta": {
            "run_ts_utc": run_ts_utc,
            "ticker": args.ticker,
            "rows_kept": len(hist_items),
            "history_keep": args.history_keep,
        },
        "items": hist_items,
    }

    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"OK: wrote {data_csv_path}")
    print(f"OK: wrote {stats_path}")
    print(f"OK: wrote {hist_path}")


if __name__ == "__main__":
    main()