#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compute 0050 (default ticker: 0050.TW) Bollinger Bands (60, 2) and forward MDD (20D),
then write audit-friendly artifacts:

- <cache_dir>/data.csv                (merged OHLCV)
- <cache_dir>/stats_latest.json       (latest BB + distribution of forward_mdd_20d)
- <cache_dir>/history_lite.json       (last N rows: date, price, z, band_pos, fwd_mdd)

Primary data source: yfinance (Yahoo Finance)
Resilience:
  - retry with backoff
  - fallback to Ticker().history(period="max")
  - fallback to TWSE STOCK_DAY endpoint when Yahoo returns empty (common on CI)

CI-safety fixes:
  - Force all DatetimeIndex to tz-naive to avoid tz-aware vs tz-naive comparison/merge errors.
  - _safe_pct supports scalar/Series/ndarray to avoid "float(Series)" TypeError.

Audit enhancement:
  - Locate forward_mdd min details:
      min_entry_date, min_entry_price, min_future_date, min_future_price
  - Add DQ flag if min looks abnormal (threshold configurable)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

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
        if s in ("", "N/A", "NA", "nan", "None", "--"):
            return None
        return float(s)
    except Exception:
        return None


def _safe_pct(x: Any) -> Any:
    """
    Accept scalar OR vector-like (pd.Series / np.ndarray) and multiply by 100.
    """
    if x is None:
        return None
    if isinstance(x, pd.Series):
        return x * 100.0
    if isinstance(x, np.ndarray):
        return x * 100.0
    try:
        return float(x) * 100.0
    except Exception:
        return None


def _quantile(values: np.ndarray, q: float) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.quantile(values, q))


def _ensure_tz_naive_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make index tz-naive (strip timezone) to avoid tz-aware vs tz-naive comparison errors.
    """
    if df is None or df.empty:
        return df
    idx = df.index
    try:
        if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
            df = df.copy()
            df.index = idx.tz_localize(None)
    except Exception:
        pass
    return df


def normalize_yf_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize to columns: open/high/low/close/adjclose/volume with tz-naive DatetimeIndex.
    """
    if df is None or df.empty:
        return pd.DataFrame()

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
    keep = [c for c in ["open", "high", "low", "close", "adjclose", "volume"] if c in out.columns]
    out = out[keep].copy()

    out.index = pd.to_datetime(out.index)
    out = _ensure_tz_naive_index(out)
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
        df = _ensure_tz_naive_index(df)
        return df
    except Exception:
        return pd.DataFrame()


def save_csv_with_date_index(df: pd.DataFrame, path: str) -> None:
    out = df.copy().sort_index()
    out = _ensure_tz_naive_index(out)
    out.index.name = "date"
    out.reset_index().to_csv(path, index=False)


def _sleep_backoff(attempt: int, base: float = 1.6) -> None:
    t = min(10.0, base ** attempt)
    time.sleep(t)


@dataclass
class DQ:
    flags: List[str]
    notes: List[str]

    def add(self, flag: str, note: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)
        self.notes.append(note)


# -----------------------------
# Data fetch (resilient)
# -----------------------------

def fetch_from_yfinance(ticker: str, start: str, tries: int = 4) -> pd.DataFrame:
    """
    Try multiple ways to fetch Yahoo data to reduce empty dataframe failures in CI.
    Returns tz-naive index.
    """
    last_err: Optional[Exception] = None
    start_dt = pd.to_datetime(start)

    # 1) yf.download(start=...)
    for i in range(tries):
        try:
            raw = yf.download(
                tickers=ticker,
                start=start,
                auto_adjust=False,
                progress=False,
                interval="1d",
                actions=False,
                group_by="column",
                threads=False,
            )
            df = normalize_yf_df(raw)
            if not df.empty:
                return df
        except Exception as e:
            last_err = e
        _sleep_backoff(i)

    # 2) yf.Ticker().history(period="max") then slice
    for i in range(tries):
        try:
            raw = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=False, actions=False)
            df = normalize_yf_df(raw)
            if not df.empty:
                df = df[df.index >= start_dt]
                if not df.empty:
                    return df
        except Exception as e:
            last_err = e
        _sleep_backoff(i)

    if last_err:
        print(f"[yfinance] last exception: {last_err}")
    return pd.DataFrame()


def _roc_date_to_dt(s: str) -> pd.Timestamp:
    # TWSE ROC date format: "112/02/01"
    y, m, d = s.split("/")
    return pd.Timestamp(year=int(y) + 1911, month=int(m), day=int(d))


def _to_num(s: str) -> Optional[float]:
    s = str(s).strip()
    if s in ("", "--", "N/A", "NA", "nan", "None"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def fetch_from_twse(stock_no: str, start: str, tries: int = 3) -> pd.DataFrame:
    """
    TWSE open data monthly endpoint:
      https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=YYYYMMDD&stockNo=0050

    Returns columns: open/high/low/close/adjclose/volume (adjclose=close).
    tz-naive index.
    """
    start_dt = pd.to_datetime(start).normalize()
    today = pd.Timestamp.today().normalize()

    cur = pd.Timestamp(year=start_dt.year, month=start_dt.month, day=1)
    end = pd.Timestamp(year=today.year, month=today.month, day=1)

    rows: List[Dict[str, Any]] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (GitHubActions; research data fetch)",
        "Accept": "application/json,text/plain,*/*",
    }

    while cur <= end:
        yyyymmdd = f"{cur.year}{cur.month:02d}01"
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={yyyymmdd}&stockNo={stock_no}"

        for i in range(tries):
            try:
                r = requests.get(url, headers=headers, timeout=20)
                if r.status_code != 200:
                    _sleep_backoff(i)
                    continue
                js = r.json()
                if js.get("stat") != "OK":
                    break  # not retryable

                data = js.get("data", [])
                # 0 日期, 1 成交股數, 2 成交金額, 3 開盤價, 4 最高價, 5 最低價, 6 收盤價, 7 漲跌價差, 8 成交筆數
                for it in data:
                    dt = _roc_date_to_dt(it[0])
                    if dt < start_dt:
                        continue
                    vol = _to_num(it[1])
                    o = _to_num(it[3])
                    h = _to_num(it[4])
                    l = _to_num(it[5])
                    c = _to_num(it[6])
                    if c is None:
                        continue
                    rows.append(
                        {
                            "date": dt,
                            "open": o,
                            "high": h,
                            "low": l,
                            "close": c,
                            "adjclose": c,  # TWSE no adjusted close
                            "volume": int(vol) if vol is not None else None,
                        }
                    )
                break
            except Exception:
                _sleep_backoff(i)

        time.sleep(0.25)
        cur = (cur + pd.offsets.MonthBegin(1)).normalize()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
    df = df.set_index("date")
    df.index = pd.to_datetime(df.index)
    df = _ensure_tz_naive_index(df)
    return df


# -----------------------------
# Core calculations
# -----------------------------

def compute_bb(price: pd.Series, window: int, k: float) -> pd.DataFrame:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    z = (price - ma) / sd
    band_pos = (price - lower) / (upper - lower)

    return pd.DataFrame(
        {
            "bb_ma": ma,
            "bb_sd": sd,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_z": z,
            "bb_pos": band_pos,
        }
    )


def compute_forward_mdd_from_entry(price: np.ndarray, fwd_days: int) -> np.ndarray:
    """
    forward_mdd[t] = min_{k=1..fwd_days} (price[t+k]/price[t] - 1)
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
        out[t] = (window.min() / p0) - 1.0
    return out


def classify_bb_state(z: Optional[float]) -> str:
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


def locate_forward_mdd_min_details(
    out: pd.DataFrame,
    price_series: pd.Series,
    fwd_key: str,
    fwd_days: int,
) -> Tuple[Optional[pd.Timestamp], Optional[float], Optional[pd.Timestamp], Optional[float]]:
    """
    Find the entry date that yields min forward_mdd and the min future price/date within the next fwd_days.
    Returns:
      (min_entry_date, min_entry_price, min_future_date, min_future_price)
    """
    if fwd_key not in out.columns:
        return None, None, None, None

    s = out[fwd_key].dropna()
    if s.empty:
        return None, None, None, None

    try:
        min_entry_date = s.idxmin()
    except Exception:
        return None, None, None, None

    min_entry_price = None
    try:
        if min_entry_date in price_series.index and pd.notna(price_series.loc[min_entry_date]):
            min_entry_price = float(price_series.loc[min_entry_date])
    except Exception:
        pass

    min_future_date = None
    min_future_price = None

    try:
        idx_pos = out.index.get_loc(min_entry_date)
        if isinstance(idx_pos, slice):
            # should not happen after de-dup, but handle defensively
            idx_pos = idx_pos.start
        if isinstance(idx_pos, (int, np.integer)):
            start_pos = int(idx_pos) + 1
            end_pos = min(len(out), start_pos + int(fwd_days))
            if start_pos < len(out) and start_pos < end_pos:
                future_idx = out.index[start_pos:end_pos]
                fut_prices = price_series.reindex(future_idx).dropna()
                if not fut_prices.empty:
                    min_future_date = fut_prices.idxmin()
                    min_future_price = float(fut_prices.loc[min_future_date])
    except Exception:
        pass

    return min_entry_date, min_entry_price, min_future_date, min_future_price


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
    p.add_argument(
        "--fwd_mdd_outlier_threshold",
        type=float,
        default=-0.40,
        help="If forward_mdd min < threshold, add DQ flag for audit. Default: -0.40",
    )
    args = p.parse_args()

    ensure_dir(args.cache_dir)
    dq = DQ(flags=[], notes=[])

    run_ts_utc = utc_now_iso()
    data_csv_path = os.path.join(args.cache_dir, "data.csv")
    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    hist_path = os.path.join(args.cache_dir, "history_lite.json")

    # Load existing for incremental merge
    existing = load_existing_csv(data_csv_path)

    # Decide fetch range
    fetch_start = args.start
    if not existing.empty:
        last_dt = existing.index.max()
        fetch_start = (last_dt - pd.Timedelta(days=14)).date().isoformat()

    # Fetch
    df_new = fetch_from_yfinance(args.ticker, fetch_start, tries=4)

    if df_new.empty:
        # Yahoo blocked/transient => TWSE fallback
        stock_no = args.ticker.split(".")[0]
        df_twse = fetch_from_twse(stock_no=stock_no, start=fetch_start, tries=3)
        if not df_twse.empty:
            dq.add("YFINANCE_EMPTY_FALLBACK_TWSE", "yfinance returned empty; used TWSE STOCK_DAY fallback.")
            dq.add("TWSE_NO_ADJCLOSE", "TWSE has no adjusted close; adjclose is set equal to close.")
            df_new = df_twse
        else:
            raise SystemExit(
                "ERROR: Empty data from yfinance, and TWSE fallback also returned empty. "
                "Likely network / endpoint blocking in CI."
            )

    df_new = _ensure_tz_naive_index(df_new)

    # Merge
    if not existing.empty:
        merged = pd.concat([existing, df_new], axis=0)
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        merged = df_new.sort_index()

    merged = _ensure_tz_naive_index(merged)

    # DQ checks
    if "adjclose" not in merged.columns:
        dq.add("MISSING_ADJCLOSE", "Data did not provide Adj Close; set adjclose=close.")
        merged["adjclose"] = merged["close"]

    if merged.shape[0] < (args.bb_window + args.fwd_days + 10):
        dq.add(
            "INSUFFICIENT_HISTORY",
            f"Rows={merged.shape[0]} < bb_window({args.bb_window}) + fwd_days({args.fwd_days}) + buffer.",
        )

    # Persist data
    save_csv_with_date_index(merged, data_csv_path)

    # Price series
    price_used_col = args.price_col
    price_series = merged[price_used_col].copy()

    # Calc price series for BB
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
    out = _ensure_tz_naive_index(out)

    # Distances (level price)
    upper = out["bb_upper"]
    lower = out["bb_lower"]

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

    # forward_mdd on level price
    price_np = price_series.to_numpy(dtype=float)
    fwd_mdd = compute_forward_mdd_from_entry(price_np, fwd_days=args.fwd_days)
    fwd_key = f"forward_mdd_{args.fwd_days}d"
    out[fwd_key] = fwd_mdd

    # Audit: locate min details (entry date & min future price/date)
    min_entry_date, min_entry_price, min_future_date, min_future_price = locate_forward_mdd_min_details(
        out=out, price_series=price_series, fwd_key=fwd_key, fwd_days=int(args.fwd_days)
    )

    # Latest
    latest_idx = out.index.max()
    latest_row = out.loc[latest_idx]
    latest_z = _to_float(latest_row.get("bb_z"))
    latest_pos = _to_float(latest_row.get("bb_pos"))

    # Distribution
    fwd_vals = out[fwd_key].dropna().to_numpy(dtype=float)
    fwd_n = int(fwd_vals.size)
    if fwd_n < 200:
        dq.add("LOW_SAMPLE_FORWARD_MDD", f"forward_mdd sample size is small (n={fwd_n}).")

    fwd_min = float(np.min(fwd_vals)) if fwd_n > 0 else None
    if (fwd_min is not None) and (fwd_min < float(args.fwd_mdd_outlier_threshold)):
        dq.add(
            "FWD_MDD_OUTLIER_MIN",
            f"forward_mdd min={fwd_min:.4f} < threshold({args.fwd_mdd_outlier_threshold}); audit min_entry_date.",
        )

    stats = {
        "meta": {
            "run_ts_utc": run_ts_utc,
            "module": "tw0050_bb",
            "ticker": args.ticker,
            "data_source": "yfinance_yahoo_or_twse_fallback",
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
        "dq": {"flags": dq.flags, "notes": dq.notes},
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
            "min": fwd_min,
            # audit details
            "min_entry_date": min_entry_date.date().isoformat() if min_entry_date is not None else None,
            "min_entry_price": min_entry_price,
            "min_future_date": min_future_date.date().isoformat() if min_future_date is not None else None,
            "min_future_price": min_future_price,
        },
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, sort_keys=True)

    # history_lite.json
    tail = out.tail(args.history_keep).copy()
    hist_items: List[Dict[str, Any]] = []
    for idx, r in tail.iterrows():
        hist_items.append(
            {
                "date": idx.date().isoformat(),
                "price": _to_float(price_series.loc[idx]) if idx in price_series.index else None,
                "bb_z": _to_float(r.get("bb_z")),
                "bb_pos": _to_float(r.get("bb_pos")),
                fwd_key: _to_float(r.get(fwd_key)),
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