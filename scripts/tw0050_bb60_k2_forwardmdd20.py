#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
0050 BB(60,2) + forward_mdd(20D) compute script.

Outputs (in --cache_dir):
  - data.csv
  - stats_latest.json
  - history_lite.json

Data source:
  1) yfinance (preferred; long history)
  2) TWSE fallback (recent-only; months_back default=6)

Key features:
  - Robust scalar parsing for ticker/price_col (prevents tuple->lower() crashes)
  - Computes TWO forward_mdd distributions:
      * forward_mdd_raw   : no filtering (may include split-like artifacts)
      * forward_mdd_clean : excludes windows contaminated by detected price breaks
    The primary field "forward_mdd" uses CLEAN by default (audit-grade usable).
  - Keeps Min Audit Trail for both raw and clean.
  - DQ flags disclose break detection and cleaning.
  - Adds Trend / Volatility filters:
      * trend: MA(trend_ma_days) + slope over slope_days (%)
      * vol  : RV(vol_window_days) annualized + ATR(atr_window_days) and ATR%
        - ATR needs High/Low; if unavailable, DQ flag will disclose.

"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz
import requests

try:
    import yfinance as yf
except Exception:
    yf = None


SCRIPT_FINGERPRINT = "tw0050_bb60_k2_forwardmdd20@2026-02-19.v5"
TZ_LOCAL = "Asia/Taipei"
TRADING_DAYS_PER_YEAR = 252


# -------------------------
# Helpers
# -------------------------

def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _to_scalar_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    if isinstance(x, (list, tuple)):
        if len(x) == 0:
            return default
        return str(x[0])
    return str(x)

def _quantile(a: np.ndarray, q: float) -> float:
    if a.size == 0:
        return float("nan")
    return float(np.quantile(a, q))

def _nan_to_none(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None

def _local_day_key_now() -> str:
    tz = pytz.timezone(TZ_LOCAL)
    return datetime.now(timezone.utc).astimezone(tz).strftime("%Y-%m-%d")

def _df_to_csv_min(df: pd.DataFrame) -> pd.DataFrame:
    # Keep as minimal as possible, but include OHLC if present for auditability.
    cols = []
    for c in ["date", "open", "high", "low", "close", "adjclose", "volume"]:
        if c in df.columns:
            cols.append(c)
    return df[cols].copy()


# -------------------------
# TWSE fallback (recent)
# -------------------------

def _twse_months_back_list(months_back: int) -> List[Tuple[int, int]]:
    tz = pytz.timezone(TZ_LOCAL)
    now = datetime.now(tz)
    y, m = now.year, now.month
    out = []
    for i in range(months_back):
        yy = y
        mm = m - i
        while mm <= 0:
            mm += 12
            yy -= 1
        out.append((yy, mm))
    out.reverse()
    return out

def _twse_fetch_month(stock_no: str, year: int, month: int, timeout: int = 20) -> pd.DataFrame:
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
    date_str = f"{year}{month:02d}01"
    params = {"date": date_str, "stockNo": stock_no, "response": "json"}
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    j = r.json()
    if j.get("stat") != "OK" or "data" not in j:
        return pd.DataFrame()

    data = j.get("data", [])
    fields = j.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=fields)

    def roc_to_date(s: str) -> Optional[str]:
        try:
            s = str(s).strip()
            roc_y, mm, dd = s.split("/")
            gy = int(roc_y) + 1911
            return f"{gy:04d}-{int(mm):02d}-{int(dd):02d}"
        except Exception:
            return None

    col_date = None
    col_open = None
    col_high = None
    col_low = None
    col_close = None
    col_vol = None

    for c in df.columns:
        if "日期" in c:
            col_date = c
        if "開盤" in c:
            col_open = c
        if "最高" in c:
            col_high = c
        if "最低" in c:
            col_low = c
        if "收盤" in c:
            col_close = c
        if "成交股數" in c:
            col_vol = c

    if not col_date or not col_close:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["date"] = df[col_date].map(roc_to_date)

    def _to_num_series(s: pd.Series) -> pd.Series:
        return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")

    if col_open:
        out["open"] = _to_num_series(df[col_open])
    if col_high:
        out["high"] = _to_num_series(df[col_high])
    if col_low:
        out["low"] = _to_num_series(df[col_low])

    out["close"] = _to_num_series(df[col_close])

    if col_vol:
        out["volume"] = _to_num_series(df[col_vol])
    else:
        out["volume"] = np.nan

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).sort_values("date")

    # TWSE fallback has no true adjclose => treat as close
    out["adjclose"] = out["close"]

    keep = ["date"]
    for c in ["open", "high", "low", "close", "adjclose", "volume"]:
        if c in out.columns:
            keep.append(c)
    return out[keep].reset_index(drop=True)

def fetch_twse_recent_0050(months_back: int, dq_flags: List[str], dq_notes: List[str]) -> pd.DataFrame:
    stock_no = "0050"
    frames = []
    for (yy, mm) in _twse_months_back_list(months_back):
        try:
            frames.append(_twse_fetch_month(stock_no, yy, mm))
        except Exception as e:
            dq_flags.append("TWSE_FETCH_ERROR")
            dq_notes.append(f"TWSE month fetch failed: {yy}-{mm:02d}: {repr(e)}")
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


# -------------------------
# yfinance fetch
# -------------------------

def fetch_yfinance(ticker: str, start: str, dq_flags: List[str], dq_notes: List[str]) -> pd.DataFrame:
    if yf is None:
        dq_flags.append("YFINANCE_IMPORT_ERROR")
        dq_notes.append("yfinance not importable in runtime; fallback will be used.")
        return pd.DataFrame()
    try:
        df = yf.download(
            tickers=ticker,
            start=start,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )
        if df is None or len(df) == 0:
            return pd.DataFrame()

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        df = df.reset_index()

        rename = {
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjclose",
            "Volume": "volume",
        }
        df.rename(columns=rename, inplace=True)

        if "date" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()

        # Ensure optional columns exist
        if "adjclose" not in df.columns:
            df["adjclose"] = df["close"]
        for c in ["open", "high", "low"]:
            if c not in df.columns:
                df[c] = pd.NA
        if "volume" not in df.columns:
            df["volume"] = pd.NA

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ["open", "high", "low", "close", "adjclose", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)

        return df[["date", "open", "high", "low", "close", "adjclose", "volume"]]
    except Exception as e:
        dq_flags.append("YFINANCE_ERROR")
        dq_notes.append(f"yfinance fetch failed: {e.__class__.__name__}: {e}")
        return pd.DataFrame()


# -------------------------
# Indicators
# -------------------------

def compute_bb(price: pd.Series, window: int, k: float) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    return ma, sd, upper, lower

def classify_state(bb_z: float, bb_pos: float) -> str:
    if bb_z is None or not np.isfinite(bb_z):
        return "NA"
    if bb_z >= 2.0 or bb_pos >= 1.0:
        return "EXTREME_UPPER_BAND"
    if bb_z <= -2.0 or bb_pos <= 0.0:
        return "EXTREME_LOWER_BAND"
    if bb_z >= 1.5 or bb_pos >= 0.8:
        return "NEAR_UPPER_BAND"
    if bb_z <= -1.5 or bb_pos <= 0.2:
        return "NEAR_LOWER_BAND"
    return "IN_BAND"

def compute_trend_filter(
    price_used: pd.Series,
    ma_days: int,
    slope_days: int,
    slope_thr_pct: float
) -> Dict[str, Any]:
    """
    Trend filter:
      - trend_ma = SMA(ma_days)
      - slope_pct = (trend_ma[t] / trend_ma[t-slope_days] - 1) * 100
      - price_vs_ma_pct = (price / trend_ma - 1) * 100
    """
    out: Dict[str, Any] = {
        "ma_days": int(ma_days),
        "slope_days": int(slope_days),
        "slope_thr_pct": float(slope_thr_pct),
        "ma_last": None,
        "ma_prev": None,
        "slope_pct": None,
        "price_vs_ma_pct": None,
        "state": "NA",
    }

    if price_used is None or len(price_used) < (ma_days + slope_days + 1):
        return out

    ma = price_used.rolling(window=ma_days, min_periods=ma_days).mean()

    last_idx = len(price_used) - 1
    ma_last = ma.iloc[last_idx]
    if not np.isfinite(ma_last) or ma_last <= 0:
        return out

    prev_idx = last_idx - slope_days
    ma_prev = ma.iloc[prev_idx] if prev_idx >= 0 else np.nan

    price_last = price_used.iloc[last_idx]
    if not np.isfinite(price_last) or price_last <= 0:
        return out

    out["ma_last"] = float(ma_last)
    if np.isfinite(ma_prev) and ma_prev > 0:
        out["ma_prev"] = float(ma_prev)
        slope_pct = (ma_last / ma_prev - 1.0) * 100.0
        out["slope_pct"] = float(slope_pct)

        if slope_pct >= slope_thr_pct:
            out["state"] = "TREND_UP"
        elif slope_pct <= -slope_thr_pct:
            out["state"] = "TREND_DOWN"
        else:
            out["state"] = "TREND_FLAT"

    out["price_vs_ma_pct"] = float((price_last / ma_last - 1.0) * 100.0)
    return out

def compute_realized_vol_ann(price_used: pd.Series, vol_window_days: int) -> Dict[str, Any]:
    """
    Realized volatility from log returns:
      rv_daily = std(logret, window=vol_window_days)
      rv_ann   = rv_daily * sqrt(252)
    """
    out: Dict[str, Any] = {
        "rv_days": int(vol_window_days),
        "rv_daily": None,
        "rv_ann": None,
    }
    if price_used is None or len(price_used) < (vol_window_days + 2):
        return out

    p = price_used.astype(float)
    logret = np.log(p / p.shift(1))
    rv = logret.rolling(window=vol_window_days, min_periods=vol_window_days).std(ddof=0)
    last = rv.iloc[-1]
    if np.isfinite(last) and last >= 0:
        out["rv_daily"] = float(last)
        out["rv_ann"] = float(last * np.sqrt(TRADING_DAYS_PER_YEAR))
    return out

def compute_atr(close: pd.Series, high: Optional[pd.Series], low: Optional[pd.Series], atr_window_days: int) -> Dict[str, Any]:
    """
    ATR (simple moving average of True Range). Requires high/low.
    ATR% is ATR / close * 100
    """
    out: Dict[str, Any] = {
        "atr_days": int(atr_window_days),
        "atr": None,
        "atr_pct": None,
    }

    if close is None or len(close) < (atr_window_days + 2):
        return out
    if high is None or low is None:
        return out

    c = close.astype(float)
    h = high.astype(float)
    l = low.astype(float)

    # If high/low are mostly missing, bail.
    if (h.notna().sum() < (atr_window_days + 2)) or (l.notna().sum() < (atr_window_days + 2)):
        return out

    prev_close = c.shift(1)
    tr1 = (h - l).abs()
    tr2 = (h - prev_close).abs()
    tr3 = (l - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=atr_window_days, min_periods=atr_window_days).mean()
    atr_last = atr.iloc[-1]
    close_last = c.iloc[-1]

    if np.isfinite(atr_last) and np.isfinite(close_last) and close_last > 0:
        out["atr"] = float(atr_last)
        out["atr_pct"] = float((atr_last / close_last) * 100.0)

    return out


@dataclass
class ForwardMDDStats:
    n: int
    p50: float
    p25: float
    p10: float
    p05: float
    min: float
    min_entry_idx: int
    min_future_idx: int


def compute_forward_mdd(
    prices: np.ndarray,
    fwd_days: int,
    valid_entry_mask: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, ForwardMDDStats]:
    """
    forward_mdd[t] = min(prices[t+1..t+fwd]/prices[t] - 1)

    valid_entry_mask:
      - optional boolean mask length n; if provided, only compute out[t] when mask[t] is True.
    """
    n = len(prices)
    out = np.full(n, np.nan, dtype=float)

    if n < (fwd_days + 2):
        stats = ForwardMDDStats(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), -1, -1)
        return out, stats

    if valid_entry_mask is None:
        valid_entry_mask = np.ones(n, dtype=bool)

    for i in range(0, n - fwd_days - 1):
        if not valid_entry_mask[i]:
            continue
        base = prices[i]
        if not np.isfinite(base) or base <= 0:
            continue
        future = prices[i + 1: i + fwd_days + 1]
        rel = future / base - 1.0
        out[i] = np.nanmin(rel)

    valid = out[np.isfinite(out)]
    if valid.size == 0:
        stats = ForwardMDDStats(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), -1, -1)
        return out, stats

    mn = float(np.min(valid))
    entry_idx = int(np.nanargmin(out))

    base = prices[entry_idx]
    future = prices[entry_idx + 1: entry_idx + fwd_days + 1]
    rel = future / base - 1.0
    future_offset = int(np.nanargmin(rel))
    future_idx = entry_idx + 1 + future_offset

    stats = ForwardMDDStats(
        n=int(valid.size),
        p50=_quantile(valid, 0.50),
        p25=_quantile(valid, 0.25),
        p10=_quantile(valid, 0.10),
        p05=_quantile(valid, 0.05),
        min=mn,
        min_entry_idx=entry_idx,
        min_future_idx=future_idx
    )
    return out, stats


# -------------------------
# Price break detection
# -------------------------

def detect_price_breaks(prices: np.ndarray, ratio_hi: float, ratio_lo: float) -> np.ndarray:
    n = len(prices)
    breaks = np.zeros(n, dtype=bool)
    for i in range(1, n):
        a = prices[i - 1]
        b = prices[i]
        if not np.isfinite(a) or not np.isfinite(b) or a <= 0 or b <= 0:
            continue
        r = b / a
        if r >= ratio_hi or r <= ratio_lo:
            breaks[i] = True
    return breaks

def build_clean_entry_mask(n: int, breaks: np.ndarray, fwd_days: int) -> np.ndarray:
    """
    If there's a break at index j (transition j-1->j), then any entry i whose window [i+1..i+fwd]
    includes j should be excluded:
      i < j <= i+fwd_days  =>  i in [j - fwd_days, j-1]
    """
    mask = np.ones(n, dtype=bool)
    break_idxs = np.where(breaks)[0]
    for j in break_idxs:
        lo = max(0, j - fwd_days)
        hi = min(n, j)
        mask[lo:hi] = False
    return mask


# -------------------------
# history_lite
# -------------------------

def load_history_lite(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"meta": {"created_at_utc": utc_now_iso_z()}, "rows": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history_lite(path: str, hist: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2, sort_keys=True)

def upsert_history_row(hist: Dict[str, Any], day_key: str, latest: Dict[str, Any], meta: Dict[str, Any]) -> None:
    rows = hist.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    rows = [r for r in rows if r.get("day_key_local") != day_key]
    rows.append({
        "day_key_local": day_key,
        "as_of_last_date": meta.get("last_date"),
        "state": latest.get("state"),
        "bb_z": latest.get("bb_z"),
        "bb_pos": latest.get("bb_pos"),
        "price_used": latest.get("price_used"),
        "run_ts_utc": meta.get("run_ts_utc"),
    })
    rows = sorted(rows, key=lambda r: r.get("day_key_local", ""))
    hist["rows"] = rows
    hist.setdefault("meta", {})["updated_at_utc"] = utc_now_iso_z()


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--cache_dir", required=True)

    ap.add_argument("--start", default="2003-01-01")
    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)
    ap.add_argument("--fwd_days", type=int, default=20)

    # Support both names to avoid yml mismatch
    ap.add_argument("--price_col", default="adjclose")
    ap.add_argument("--price_col_requested", default=None)

    ap.add_argument("--twse_months_back", type=int, default=6)

    # Outlier tagging for raw
    ap.add_argument("--outlier_min_threshold", type=float, default=-0.4)

    # Break detection thresholds (split-like)
    ap.add_argument("--break_ratio_hi", type=float, default=1.8)
    ap.add_argument("--break_ratio_lo", type=float, default=(1.0 / 1.8))

    # Cleaning mode for primary forward_mdd
    ap.add_argument("--forward_mode", choices=["raw", "clean"], default="clean")

    # Trend / Vol filters
    ap.add_argument("--trend_ma_days", type=int, default=200)      # allow 200 or 252
    ap.add_argument("--trend_slope_days", type=int, default=20)    # slope horizon
    ap.add_argument("--trend_slope_thr_pct", type=float, default=0.5)

    ap.add_argument("--vol_window_days", type=int, default=20)     # RV20
    ap.add_argument("--atr_window_days", type=int, default=14)     # ATR14 (common)

    args = ap.parse_args()

    dq_flags: List[str] = []
    dq_notes: List[str] = []

    ticker = _to_scalar_str(args.ticker).strip()
    if not ticker:
        print("ERROR: empty --ticker after normalization", file=sys.stderr)
        return 2

    price_col_req = args.price_col_requested if args.price_col_requested is not None else args.price_col
    price_col_req = _to_scalar_str(price_col_req, "adjclose").strip().lower()

    ensure_dir(args.cache_dir)

    df = fetch_yfinance(ticker=ticker, start=str(args.start), dq_flags=dq_flags, dq_notes=dq_notes)
    used_fallback = False

    if df is None or len(df) == 0:
        used_fallback = True
        dq_flags.append("DATA_SOURCE_TWSE_FALLBACK")
        dq_notes.append(f"Used TWSE fallback (recent-only, months_back={int(args.twse_months_back)}).")
        df = fetch_twse_recent_0050(months_back=int(args.twse_months_back), dq_flags=dq_flags, dq_notes=dq_notes)

    if df is None or len(df) == 0:
        print("ERROR: no data from yfinance and TWSE fallback.", file=sys.stderr)
        stats_path = os.path.join(args.cache_dir, "stats_latest.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(
                {"meta": {"run_ts_utc": utc_now_iso_z(), "module": "tw0050_bb", "ticker": ticker},
                 "dq": {"flags": dq_flags, "notes": dq_notes}},
                f, ensure_ascii=False, indent=2
            )
        return 1

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # choose price series
    if price_col_req in df.columns and df[price_col_req].notna().any():
        price_used = df[price_col_req].astype(float).copy()
        price_col_used = price_col_req
    else:
        price_used = df["adjclose"].astype(float).copy() if "adjclose" in df.columns else df["close"].astype(float).copy()
        price_col_used = "adjclose" if "adjclose" in df.columns else "close"
        dq_flags.append("PRICE_COL_FALLBACK")
        dq_notes.append(f"requested={price_col_req} not usable; used={price_col_used}.")

    # BB
    w = int(args.bb_window)
    k = float(args.bb_k)
    ma, sd, upper, lower = compute_bb(price_used, window=w, k=k)

    last_idx = len(df) - 1
    last_date = df.loc[last_idx, "date"].strftime("%Y-%m-%d")

    latest_price = float(price_used.iloc[last_idx])
    latest_ma = ma.iloc[last_idx]
    latest_sd = sd.iloc[last_idx]
    latest_upper = upper.iloc[last_idx]
    latest_lower = lower.iloc[last_idx]

    bb_z = float((latest_price - latest_ma) / latest_sd) if np.isfinite(latest_sd) and latest_sd > 0 else float("nan")
    bb_pos = float((latest_price - latest_lower) / (latest_upper - latest_lower)) if np.isfinite(latest_upper - latest_lower) and (latest_upper - latest_lower) != 0 else float("nan")

    dist_to_lower_pct = (latest_price / latest_lower - 1.0) * 100.0 if np.isfinite(latest_lower) and latest_lower > 0 else float("nan")
    dist_to_upper_pct = (latest_price / latest_upper - 1.0) * 100.0 if np.isfinite(latest_upper) and latest_upper > 0 else float("nan")

    state = classify_state(bb_z=bb_z, bb_pos=bb_pos)

    # forward_mdd raw
    prices_np = price_used.to_numpy(dtype=float)
    fwd_days = int(args.fwd_days)
    fwd_raw_arr, fwd_raw_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days)

    # detect breaks & clean
    breaks = detect_price_breaks(prices_np, ratio_hi=float(args.break_ratio_hi), ratio_lo=float(args.break_ratio_lo))
    break_idxs = np.where(breaks)[0].tolist()
    clean_mask = build_clean_entry_mask(len(prices_np), breaks, fwd_days=fwd_days)
    fwd_clean_arr, fwd_clean_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days, valid_entry_mask=clean_mask)

    if len(break_idxs) > 0:
        dq_flags.append("PRICE_SERIES_BREAK_DETECTED")
        show = []
        for j in break_idxs[:3]:
            d = df.loc[j, "date"].strftime("%Y-%m-%d")
            a = prices_np[j - 1]
            b = prices_np[j]
            r = (b / a) if (np.isfinite(a) and a > 0) else float("nan")
            show.append(f"{d}(r={r:.3f})")
        dq_notes.append(
            f"Detected {len(break_idxs)} break(s) by ratio thresholds; sample: {', '.join(show)}; "
            f"hi={float(args.break_ratio_hi)}, lo={float(args.break_ratio_lo):.6f}."
        )
        dq_flags.append("FWD_MDD_CLEAN_APPLIED")
        dq_notes.append("Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).")

    # tag outlier on RAW only
    thr = float(args.outlier_min_threshold)
    if fwd_raw_stats.n > 0 and np.isfinite(fwd_raw_stats.min) and fwd_raw_stats.min < thr:
        dq_flags.append("FWD_MDD_OUTLIER_MIN_RAW")
        dq_notes.append(f"forward_mdd_raw min={fwd_raw_stats.min:.4f} < threshold({thr}); see raw min_audit_trail.")

    # choose primary forward_mdd
    forward_mode = str(args.forward_mode).lower()
    primary_stats = fwd_clean_stats if forward_mode == "clean" else fwd_raw_stats

    def min_audit_from(stats: ForwardMDDStats) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[float]]:
        if stats.n <= 0 or stats.min_entry_idx < 0 or stats.min_future_idx < 0:
            return None, None, None, None
        med = df.loc[stats.min_entry_idx, "date"].strftime("%Y-%m-%d")
        mfd = df.loc[stats.min_future_idx, "date"].strftime("%Y-%m-%d")
        mep = float(prices_np[stats.min_entry_idx])
        mfp = float(prices_np[stats.min_future_idx])
        return med, mep, mfd, mfp

    # Trend / Volatility
    trend = compute_trend_filter(
        price_used=price_used,
        ma_days=int(args.trend_ma_days),
        slope_days=int(args.trend_slope_days),
        slope_thr_pct=float(args.trend_slope_thr_pct),
    )

    vol_rv = compute_realized_vol_ann(price_used=price_used, vol_window_days=int(args.vol_window_days))

    # ATR uses close/high/low (not adjclose)
    high = df["high"] if "high" in df.columns else None
    low = df["low"] if "low" in df.columns else None
    close = df["close"] if "close" in df.columns else None
    atr = compute_atr(close=close, high=high, low=low, atr_window_days=int(args.atr_window_days))

    if atr.get("atr") is None:
        dq_flags.append("ATR_UNAVAILABLE")
        dq_notes.append("ATR not computed (missing/insufficient high-low data).")

    # build outputs
    run_ts_utc = utc_now_iso_z()
    meta = {
        "run_ts_utc": run_ts_utc,
        "module": "tw0050_bb",
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "ticker": ticker,
        "start": str(args.start),
        "fetch_start_effective": str(args.start) if not used_fallback else df["date"].min().strftime("%Y-%m-%d"),
        "rows": int(len(df)),
        "tz": TZ_LOCAL,
        "data_source": "yfinance_yahoo_or_twse_fallback",
        "bb_window": w,
        "bb_k": k,
        "fwd_days": fwd_days,
        "price_calc": "adjclose" if price_col_used == "adjclose" else "close",
        "price_col_requested": price_col_req,
        "price_col_used": price_col_used,
        "last_date": last_date,
        "break_detection": {
            "break_ratio_hi": float(args.break_ratio_hi),
            "break_ratio_lo": float(args.break_ratio_lo),
            "break_count": int(len(break_idxs)),
            "forward_mode_primary": forward_mode,
        },
        "trend_params": {
            "trend_ma_days": int(args.trend_ma_days),
            "trend_slope_days": int(args.trend_slope_days),
            "trend_slope_thr_pct": float(args.trend_slope_thr_pct),
        },
        "vol_params": {
            "vol_window_days": int(args.vol_window_days),
            "atr_window_days": int(args.atr_window_days),
            "rv_annualization_days": TRADING_DAYS_PER_YEAR,
        },
    }

    latest = {
        "date": last_date,
        "close": _nan_to_none(float(df.loc[last_idx, "close"])) if "close" in df.columns else None,
        "adjclose": _nan_to_none(float(df.loc[last_idx, "adjclose"])) if "adjclose" in df.columns else None,
        "price_used": _nan_to_none(latest_price),
        "bb_ma": _nan_to_none(float(latest_ma)),
        "bb_sd": _nan_to_none(float(latest_sd)),
        "bb_upper": _nan_to_none(float(latest_upper)),
        "bb_lower": _nan_to_none(float(latest_lower)),
        "bb_z": _nan_to_none(float(bb_z)),
        "bb_pos": _nan_to_none(float(bb_pos)),
        "dist_to_lower_pct": _nan_to_none(float(dist_to_lower_pct)),
        "dist_to_upper_pct": _nan_to_none(float(dist_to_upper_pct)),
        "state": state,
    }

    def pack_fwd(stats: ForwardMDDStats, label: str) -> Dict[str, Any]:
        med, mep, mfd, mfp = min_audit_from(stats)
        return {
            "label": label,
            "definition": f"min(price[t+1..t+{fwd_days}]/price[t]-1), level-price based",
            "n": int(stats.n),
            "p50": _nan_to_none(stats.p50),
            "p25": _nan_to_none(stats.p25),
            "p10": _nan_to_none(stats.p10),
            "p05": _nan_to_none(stats.p05),
            "min": _nan_to_none(stats.min),
            "min_entry_date": med,
            "min_entry_price": _nan_to_none(mep),
            "min_future_date": mfd,
            "min_future_price": _nan_to_none(mfp),
        }

    forward_primary = pack_fwd(primary_stats, f"forward_mdd_{forward_mode}")
    forward_raw = pack_fwd(fwd_raw_stats, "forward_mdd_raw")
    forward_clean = pack_fwd(fwd_clean_stats, "forward_mdd_clean")

    stats_out = {
        "meta": meta,
        "latest": latest,
        "trend": trend,          # NEW
        "vol": {                 # NEW (merge rv + atr)
            **vol_rv,
            **atr,
        },
        "forward_mdd": forward_primary,
        "forward_mdd_raw": forward_raw,
        "forward_mdd_clean": forward_clean,
        "dq": {"flags": dq_flags, "notes": dq_notes},
    }

    # write stats_latest.json
    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats_out, f, ensure_ascii=False, indent=2, sort_keys=True)

    # write data.csv
    out_df = df.copy()
    out_df["date"] = out_df["date"].dt.strftime("%Y-%m-%d")
    out_csv = _df_to_csv_min(out_df)
    out_csv_path = os.path.join(args.cache_dir, "data.csv")
    out_csv.to_csv(out_csv_path, index=False)

    # write history_lite.json
    hist_path = os.path.join(args.cache_dir, "history_lite.json")
    hist = load_history_lite(hist_path)
    upsert_history_row(hist, day_key=_local_day_key_now(), latest=latest, meta=meta)
    save_history_lite(hist_path, hist)

    print(f"[OK] wrote: {stats_path}")
    print(f"[OK] wrote: {out_csv_path}")
    print(f"[OK] wrote: {hist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())