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

Added features:
  - Trend filter: MA200 + slope20D (on MA200), threshold (default 0.50%)
  - Vol filter: RV20 annualized + ATR14 (Wilder ATR; fallback to close-only TR if OHLC missing)
  - Regime tag (simple): TREND_UP & RV20_percentile <= pctl_max & rv_hist_n >= min_samples
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


SCRIPT_FINGERPRINT = "tw0050_bb60_k2_forwardmdd20@2026-02-19.v6"
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
    cols = []
    for c in ["date", "close", "adjclose", "volume"]:
        if c in df.columns:
            cols.append(c)
    return df[cols].copy()


def percentile_rank_leq(values: np.ndarray, x: float) -> Optional[float]:
    """
    Percentile rank in [0,100], defined as P(value <= x).
    Deterministic and audit-friendly.
    """
    try:
        v = values[np.isfinite(values)]
        if v.size == 0 or (not np.isfinite(x)):
            return None
        return float((np.sum(v <= x) / v.size) * 100.0)
    except Exception:
        return None


def safe_get(d: Any, k: str, default=None):
    try:
        if isinstance(d, dict):
            return d.get(k, default)
        return default
    except Exception:
        return default


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
    """
    TWSE STOCK_DAY fields typically include:
      日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數
    We map to: date, open, high, low, close, adjclose(=close), volume
    """
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
    out["close"] = df[col_close].astype(str).str.replace(",", "", regex=False)
    if col_open:
        out["open"] = df[col_open].astype(str).str.replace(",", "", regex=False)
    else:
        out["open"] = None
    if col_high:
        out["high"] = df[col_high].astype(str).str.replace(",", "", regex=False)
    else:
        out["high"] = None
    if col_low:
        out["low"] = df[col_low].astype(str).str.replace(",", "", regex=False)
    else:
        out["low"] = None

    if col_vol:
        out["volume"] = df[col_vol].astype(str).str.replace(",", "", regex=False)
    else:
        out["volume"] = None

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out = out.dropna(subset=["date", "close"]).sort_values("date")

    # If OHLC missing, backfill with close
    for c in ["open", "high", "low"]:
        if c not in out.columns or out[c].isna().all():
            out[c] = out["close"]
        else:
            out[c] = out[c].fillna(out["close"])

    out["adjclose"] = out["close"]
    return out[["date", "open", "high", "low", "close", "adjclose", "volume"]].reset_index(drop=True)


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

        # normalize possible MultiIndex
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

        if "adjclose" not in df.columns:
            df["adjclose"] = df["close"]
        if "volume" not in df.columns:
            df["volume"] = pd.NA

        # If OHLC missing, backfill with close (still lets ATR fallback)
        for c in ["open", "high", "low"]:
            if c not in df.columns:
                df[c] = df["close"]

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ["open", "high", "low", "close", "adjclose", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)

        # backfill OHLC NaNs with close
        for c in ["open", "high", "low"]:
            df[c] = df[c].fillna(df["close"])

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
    if bb_z >= 2.0 or (bb_pos is not None and np.isfinite(bb_pos) and bb_pos >= 1.0):
        return "EXTREME_UPPER_BAND"
    if bb_z <= -2.0 or (bb_pos is not None and np.isfinite(bb_pos) and bb_pos <= 0.0):
        return "EXTREME_LOWER_BAND"
    if bb_z >= 1.5 or (bb_pos is not None and np.isfinite(bb_pos) and bb_pos >= 0.8):
        return "NEAR_UPPER_BAND"
    if bb_z <= -1.5 or (bb_pos is not None and np.isfinite(bb_pos) and bb_pos <= 0.2):
        return "NEAR_LOWER_BAND"
    return "IN_BAND"


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
      - This is how we "clean" windows contaminated by detected breaks, without altering price series.
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


def compute_trend_filter(price: pd.Series, ma_days: int, slope_days: int, slope_thr_pct: float) -> Dict[str, Any]:
    """
    Trend filter:
      - trend_ma = SMA(ma_days)
      - slope_pct = (trend_ma[t] / trend_ma[t-slope_days] - 1) * 100
      - price_vs_ma_pct = (price[t] / trend_ma[t] - 1) * 100
    Rule:
      - TREND_UP: price_vs_ma_pct > 0 AND slope_pct >= slope_thr_pct
      - TREND_DOWN: price_vs_ma_pct < 0 AND slope_pct <= -slope_thr_pct
      - otherwise: TREND_SIDE
    """
    out: Dict[str, Any] = {
        "trend_ma_days": int(ma_days),
        "trend_slope_days": int(slope_days),
        "trend_slope_thr_pct": float(slope_thr_pct),
        "trend_ma_last": None,
        "trend_slope_pct": None,
        "price_vs_trend_ma_pct": None,
        "state": "TREND_NA",
    }

    ma = price.rolling(window=ma_days, min_periods=ma_days).mean()
    if ma.isna().all():
        return out

    last = ma.iloc[-1]
    if not np.isfinite(last):
        return out

    out["trend_ma_last"] = _nan_to_none(float(last))

    px = float(price.iloc[-1]) if np.isfinite(price.iloc[-1]) else float("nan")
    if np.isfinite(px) and float(last) > 0:
        out["price_vs_trend_ma_pct"] = _nan_to_none((px / float(last) - 1.0) * 100.0)

    if len(ma) > slope_days and np.isfinite(ma.iloc[-slope_days - 1]) and float(ma.iloc[-slope_days - 1]) > 0:
        prev = float(ma.iloc[-slope_days - 1])
        slope_pct = (float(last) / prev - 1.0) * 100.0
        out["trend_slope_pct"] = _nan_to_none(slope_pct)

        p_vs = out["price_vs_trend_ma_pct"]
        if p_vs is None or out["trend_slope_pct"] is None:
            out["state"] = "TREND_NA"
        else:
            if (p_vs > 0) and (slope_pct >= slope_thr_pct):
                out["state"] = "TREND_UP"
            elif (p_vs < 0) and (slope_pct <= -slope_thr_pct):
                out["state"] = "TREND_DOWN"
            else:
                out["state"] = "TREND_SIDE"
    else:
        out["state"] = "TREND_NA"

    return out


def compute_rv20_ann(price: pd.Series, rv_days: int) -> Dict[str, Any]:
    """
    Realized Vol (RV) annualized from log returns:
      rv_daily = std(logret over rv_days)
      rv_ann = rv_daily * sqrt(252)
    """
    out: Dict[str, Any] = {
        "rv_days": int(rv_days),
        "rv_ann": None,  # decimal (e.g. 0.207 for 20.7%)
        "rv_ann_pctl": None,  # 0..100
        "rv_hist_n": 0,
        "rv_hist_q20": None,
        "rv_hist_q50": None,
        "rv_hist_q80": None,
    }

    p = price.astype(float)
    logret = np.log(p / p.shift(1))
    rv_daily = logret.rolling(window=rv_days, min_periods=rv_days).std(ddof=0)
    rv_ann = rv_daily * np.sqrt(TRADING_DAYS_PER_YEAR)

    rv_last = rv_ann.iloc[-1]
    if np.isfinite(rv_last):
        out["rv_ann"] = _nan_to_none(float(rv_last))

    rv_hist = rv_ann.dropna().to_numpy(dtype=float)
    out["rv_hist_n"] = int(rv_hist.size)
    if rv_hist.size > 0:
        out["rv_hist_q20"] = _nan_to_none(float(np.quantile(rv_hist, 0.20)))
        out["rv_hist_q50"] = _nan_to_none(float(np.quantile(rv_hist, 0.50)))
        out["rv_hist_q80"] = _nan_to_none(float(np.quantile(rv_hist, 0.80)))

    if out["rv_ann"] is not None and rv_hist.size > 0:
        out["rv_ann_pctl"] = percentile_rank_leq(rv_hist, float(out["rv_ann"]))

    return out


def compute_atr14(df_ohlc: pd.DataFrame, atr_days: int, price_for_pct: float) -> Dict[str, Any]:
    """
    Wilder's ATR:
      TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
      ATR_t = (ATR_{t-1}*(n-1) + TR_t)/n, seeded by SMA(TR, n) at first valid.

    Fallback:
      if high/low not available, use TR = abs(close - prev_close)
    """
    out: Dict[str, Any] = {
        "atr_days": int(atr_days),
        "atr": None,
        "atr_pct": None,  # percent (0..100) stored as percent value? we store as percentage number (e.g. 1.66)
        "tr_mode": "OHLC"  # or "CLOSE_ONLY"
    }

    if df_ohlc is None or df_ohlc.empty or "close" not in df_ohlc.columns:
        return out

    close = df_ohlc["close"].astype(float).copy()
    prev_close = close.shift(1)

    have_ohlc = all(c in df_ohlc.columns for c in ["high", "low"])
    if have_ohlc:
        high = df_ohlc["high"].astype(float).copy()
        low = df_ohlc["low"].astype(float).copy()

        tr1 = (high - low).abs()
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        out["tr_mode"] = "OHLC"
    else:
        tr = (close - prev_close).abs()
        out["tr_mode"] = "CLOSE_ONLY"

    tr = tr.replace([np.inf, -np.inf], np.nan)

    # Need at least atr_days + 1 points (because prev_close)
    if tr.dropna().shape[0] < atr_days:
        return out

    # Wilder ATR
    atr = pd.Series(index=tr.index, dtype=float)
    tr_sma = tr.rolling(window=atr_days, min_periods=atr_days).mean()
    # Seed at first point where SMA valid
    first_valid = tr_sma.first_valid_index()
    if first_valid is None:
        return out
    atr.loc[first_valid] = tr_sma.loc[first_valid]

    # Iterate forward
    idxs = list(tr.index)
    start_pos = idxs.index(first_valid)
    for i in range(start_pos + 1, len(idxs)):
        t = idxs[i]
        t_prev = idxs[i - 1]
        if not np.isfinite(atr.loc[t_prev]) or not np.isfinite(tr.loc[t]):
            atr.loc[t] = np.nan
            continue
        atr.loc[t] = (atr.loc[t_prev] * (atr_days - 1) + tr.loc[t]) / atr_days

    atr_last = atr.iloc[-1]
    if np.isfinite(atr_last):
        out["atr"] = _nan_to_none(float(atr_last))
        if np.isfinite(price_for_pct) and price_for_pct > 0:
            out["atr_pct"] = _nan_to_none((float(atr_last) / float(price_for_pct)) * 100.0)

    return out


# -------------------------
# Price break detection
# -------------------------

def detect_price_breaks(prices: np.ndarray, ratio_hi: float, ratio_lo: float) -> np.ndarray:
    """
    Detect split-like / data-break points using day-to-day ratio.

    breaks[t] = True means the transition from t-1 -> t is suspicious:
      prices[t] / prices[t-1] >= ratio_hi OR <= ratio_lo
    """
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
    includes j should be excluded.

    Exclude entries i where:
      i < j <= i+fwd_days  => i in [j - fwd_days, j-1]
    """
    mask = np.ones(n, dtype=bool)
    break_idxs = np.where(breaks)[0]
    for j in break_idxs:
        lo = max(0, j - fwd_days)
        hi = min(n, j)  # exclude up to j-1
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

    # Trend filter params
    ap.add_argument("--trend_ma_days", type=int, default=200)
    ap.add_argument("--trend_slope_days", type=int, default=20)
    ap.add_argument("--trend_slope_thr_pct", type=float, default=0.50)

    # Vol/ATR params
    ap.add_argument("--rv_days", type=int, default=20)
    ap.add_argument("--atr_days", type=int, default=14)

    # Regime (relative percentile)
    ap.add_argument("--regime_rv_pctl_max", type=float, default=0.60)   # 0~1
    ap.add_argument("--regime_min_samples", type=int, default=252)

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

    thr = float(args.outlier_min_threshold)
    raw_outlier = (fwd_raw_stats.n > 0 and np.isfinite(fwd_raw_stats.min) and fwd_raw_stats.min < thr)
    if raw_outlier:
        dq_flags.append("FWD_MDD_OUTLIER_MIN_RAW")
        dq_notes.append(f"forward_mdd_raw min={fwd_raw_stats.min:.4f} < threshold({thr}); see raw min_audit_trail.")
        # If we are using clean as primary, explicitly tag that raw outlier got excluded by clean.
        if str(args.forward_mode).lower() == "clean":
            dq_flags.append("RAW_OUTLIER_EXCLUDED")
            dq_notes.append("Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.")

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

    # Trend/Vol/ATR
    trend = compute_trend_filter(
        price=price_used,
        ma_days=int(args.trend_ma_days),
        slope_days=int(args.trend_slope_days),
        slope_thr_pct=float(args.trend_slope_thr_pct),
    )

    vol_rv = compute_rv20_ann(price=price_used, rv_days=int(args.rv_days))
    atr = compute_atr14(df_ohlc=df, atr_days=int(args.atr_days), price_for_pct=float(latest_price))

    # Regime tag (simple, percentile-based)
    rv_hist_n = int(safe_get(vol_rv, "rv_hist_n", 0) or 0)
    rv_pctl_val = safe_get(vol_rv, "rv_ann_pctl", None)
    trend_state = safe_get(trend, "state", "TREND_NA")

    pctl_max_100 = float(args.regime_rv_pctl_max) * 100.0
    min_samples = int(args.regime_min_samples)

    trend_ok = (trend_state == "TREND_UP")
    rv_hist_ok = (rv_hist_n >= min_samples)
    rv_ok = (rv_pctl_val is not None) and (float(rv_pctl_val) <= pctl_max_100)

    regime: Dict[str, Any] = {
        "definition": "TREND_UP & RV20_percentile<=pctl_max & rv_hist_n>=min_samples => RISK_ON_ALLOWED",
        "params": {
            "rv_pctl_max": pctl_max_100,      # stored as 0..100
            "min_samples": min_samples,
            "trend_required": "TREND_UP",
        },
        "inputs": {
            "trend_state": trend_state,
            "rv_ann": safe_get(vol_rv, "rv_ann"),
            "rv_ann_pctl": rv_pctl_val,
            "rv_hist_n": rv_hist_n,
            "bb_state": state,
        },
        "passes": {
            "trend_ok": bool(trend_ok),
            "rv_hist_ok": bool(rv_hist_ok),
            "rv_ok": bool(rv_ok),
        },
        "tag": "RISK_ON_UNKNOWN",
        "allowed": False,
        "reasons": [],
    }

    if (not rv_hist_ok) or (rv_pctl_val is None):
        regime["tag"] = "RISK_ON_UNKNOWN"
        regime["allowed"] = False
        regime["reasons"].append("insufficient_rv_history_or_missing_percentile")
        dq_flags.append("REGIME_INSUFFICIENT_HISTORY")
        dq_notes.append(f"regime requires rv_hist_n>={min_samples}; got {rv_hist_n}.")
    else:
        if trend_ok and rv_ok:
            regime["tag"] = "RISK_ON_ALLOWED"
            regime["allowed"] = True
        else:
            regime["tag"] = "RISK_OFF_OR_DEFENSIVE"
            regime["allowed"] = False

    # Context reasons (do not block allowed; just notes)
    if state == "EXTREME_UPPER_BAND":
        regime["reasons"].append("bb_extreme_upper_band_stretched")
    if state == "EXTREME_LOWER_BAND":
        regime["reasons"].append("bb_extreme_lower_band_stressed")

    if used_fallback:
        dq_flags.append("REGIME_DQ_SHORT_HISTORY_RISK")
        dq_notes.append("Using TWSE fallback recent-only data; rv percentile/regime should be down-weighted.")

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
            "rv_days": int(args.rv_days),
            "atr_days": int(args.atr_days),
        },
        "regime_params": {
            "rv_pctl_max": float(args.regime_rv_pctl_max),
            "min_samples": int(args.regime_min_samples),
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

        # Primary used by report (build script reads this)
        "forward_mdd": forward_primary,

        # Audit extras
        "forward_mdd_raw": forward_raw,
        "forward_mdd_clean": forward_clean,

        # Added blocks
        "trend": trend,
        "vol": vol_rv,
        "atr": atr,
        "regime": regime,

        "dq": {"flags": dq_flags, "notes": dq_notes},
    }

    # write stats_latest.json
    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats_out, f, ensure_ascii=False, indent=2, sort_keys=True)

    # write data.csv (keep minimal columns)
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