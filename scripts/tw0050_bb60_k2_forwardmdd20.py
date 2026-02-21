#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tw0050_bb60_k2_forwardmdd20.py  (v12.adjclose_audit)

0050 BB(60,2) + forward_mdd(20D) compute script.

Outputs (in --cache_dir):
  - data.csv
  - stats_latest.json
  - history_lite.json

Data source:
  1) yfinance (preferred; long history; uses Adj Close if available)
  2) TWSE fallback (recent-only; raw/unadjusted prices)

v10.shortcircuit 核心：
  - 若進入「未還原價格模式」（unadjusted_price_mode=True），直接短路：
      * 不做 BB / forward_mdd / trend / vol / atr / regime 等會被 NA 覆寫的運算
      * 僅輸出 latest_price/date + 明確 DQ flags/notes + pledge=DISALLOW
  - TWSE fallback 時，預設與強制限制 months_back 為小值（避免 14 個月 I/O 黑洞）
  - 仍保留 yfinance + adjclose 正常路徑的完整計算（含 break-clean forward_mdd）

v11.condfwd_additive 新增（只加欄位，不改原有邏輯）：
  - stats_latest.json 新增欄位 forward_mdd_conditional：
      * 以 entry 時點 bb_z[t] 的 5 段 bucket（<=-2, (-2,-1.5], (-1.5,1.5), [1.5,2), >=2）
      * 分別統計 10D/20D forward_mdd 的 raw/clean/primary 分佈分位數與 min audit trail
  - short-circuit 模式下也輸出同 schema 的 NA 版本（不引入任何 dirty-data）

v12.adjclose_audit（只加審計證據，不改原有策略/短路規則）：
  - 新增 adjclose vs close 的一致性審計（meta.adjclose_audit）：
      * 計算 abs((adjclose-close)/close) 的 max/p99/非零比例
      * 若在 yfinance 路徑下 adjclose 幾乎完全等於 close，標記 DQ：
          ADJCLOSE_EQUALS_CLOSE_SUSPECT_UNADJUSTED
      * 若 yfinance 回傳缺少 Adj Close 欄位而由程式用 close 補出，標記 DQ：
          YFINANCE_ADJCLOSE_MISSING_SYNTHESIZED
  - 注意：此審計不會強制 short-circuit（避免改動既有決策）；僅提供可驗證證據。

安全策略：
  - unadjusted_price_mode = used_fallback OR (price_col_used != "adjclose")
  - 在 unadjusted_price_mode 下：
      * latest 的 BB 欄位全 None，state="NA_DUE_TO_UNADJUSTED_PRICE"
      * forward/trend/vol/atr/regime 全 NA（結構完整）
      * pledge 永遠 DISALLOW（DQ veto）
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
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


SCRIPT_FINGERPRINT = "tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit"
TZ_LOCAL = "Asia/Taipei"
TRADING_DAYS_PER_YEAR = 252

# adjclose audit thresholds (evidence-only; does NOT alter short-circuit rules)
ADJCLOSE_AUDIT_EPS_REL = 1e-8
ADJCLOSE_AUDIT_MIN_N = 252


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


def _clip01(x: float) -> float:
    if x is None or (not np.isfinite(x)):
        return float("nan")
    return float(np.clip(x, 0.0, 1.0))


def _ticker_to_twse_stock_no(ticker: str, default: str = "0050") -> str:
    """
    Convert possible yfinance ticker (e.g., '0050.TW', '0050') to TWSE stockNo ('0050').
    Conservative: only accept 4-digit numeric; else fallback to default.
    """
    t = (ticker or "").strip().upper()
    m = re.match(r"^(\d{4})", t)
    if m:
        return m.group(1)
    return default


def adjclose_audit_vs_close(
    df: pd.DataFrame,
    *,
    eps_rel: float = ADJCLOSE_AUDIT_EPS_REL,
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    Evidence-only audit: quantify how different Adj Close is from Close.

    Returns metrics on abs((adjclose-close)/close) where close != 0 and both finite.
    Intended to detect the suspicious case where adjclose == close everywhere (likely unadjusted),
    but it does NOT change strategy/short-circuit rules by itself.

    Output keys are stable and JSON-friendly.
    """
    out: Dict[str, Any] = {
        "available": False,
        "n": 0,
        "eps_rel": float(eps_rel),
        "max_abs_rel_diff": None,
        "p99_abs_rel_diff": None,
        "nonzero_count": 0,
        "nonzero_frac": None,
        "top_abs_rel_diff": [],  # list of {date, close, adjclose, abs_rel_diff}
    }

    if df is None or df.empty:
        return out
    if "close" not in df.columns or "adjclose" not in df.columns or "date" not in df.columns:
        return out

    try:
        close = pd.to_numeric(df["close"], errors="coerce").astype(float)
        adj = pd.to_numeric(df["adjclose"], errors="coerce").astype(float)
        dates = pd.to_datetime(df["date"], errors="coerce")
        mask = np.isfinite(close.to_numpy()) & np.isfinite(adj.to_numpy()) & np.isfinite(dates.to_numpy())
        mask = mask & (close.to_numpy() != 0.0)

        if not np.any(mask):
            return out

        c = close.to_numpy()[mask]
        a = adj.to_numpy()[mask]
        d = dates.to_numpy()[mask]

        abs_rel = np.abs((a - c) / c)
        abs_rel = abs_rel[np.isfinite(abs_rel)]
        if abs_rel.size == 0:
            return out

        out["available"] = True
        out["n"] = int(abs_rel.size)
        out["max_abs_rel_diff"] = _nan_to_none(float(np.max(abs_rel)))
        out["p99_abs_rel_diff"] = _nan_to_none(float(np.quantile(abs_rel, 0.99)))
        nz = int(np.sum(abs_rel > float(eps_rel)))
        out["nonzero_count"] = nz
        out["nonzero_frac"] = _nan_to_none(float(nz / abs_rel.size))

        # Top-K rows by abs_rel
        if top_k > 0:
            idx_sorted = np.argsort(abs_rel)[::-1]
            take = idx_sorted[: min(int(top_k), int(idx_sorted.size))]
            top = []
            # We need to map back: take indices correspond to filtered arrays; use those directly
            for j in take:
                try:
                    dt = pd.to_datetime(d[j]).strftime("%Y-%m-%d")
                except Exception:
                    dt = None
                top.append({
                    "date": dt,
                    "close": _nan_to_none(float(c[j])),
                    "adjclose": _nan_to_none(float(a[j])),
                    "abs_rel_diff": _nan_to_none(float(abs_rel[j])),
                })
            out["top_abs_rel_diff"] = top

        return out
    except Exception:
        return out


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

    Map to: date, open, high, low, close, adjclose(=close), volume

    NOTE: TWSE endpoint is raw/unadjusted (dividends/splits not adjusted).
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
    out["open"] = df[col_open].astype(str).str.replace(",", "", regex=False) if col_open else None
    out["high"] = df[col_high].astype(str).str.replace(",", "", regex=False) if col_high else None
    out["low"] = df[col_low].astype(str).str.replace(",", "", regex=False) if col_low else None
    out["volume"] = df[col_vol].astype(str).str.replace(",", "", regex=False) if col_vol else None

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


def _sleep_with_jitter(base_sec: float, jitter_sec: float) -> None:
    base = max(0.0, float(base_sec))
    jitter = max(0.0, float(jitter_sec))
    t = base + (random.random() * jitter if jitter > 0 else 0.0)
    if t > 0:
        time.sleep(t)


def _twse_fetch_month_with_retries(
    stock_no: str,
    year: int,
    month: int,
    dq_flags: List[str],
    dq_notes: List[str],
    *,
    timeout: int,
    max_retries: int,
    sleep_sec: float,
    sleep_jitter: float,
) -> pd.DataFrame:
    """
    Retry policy (fallback-only):
      - sleep (base + jitter) before each attempt
      - on exception: exponential backoff = sleep_sec * (2**attempt) + jitter
      - max_retries counts total attempts (>=1)
    """
    tries = max(1, int(max_retries))
    last_err = None

    for attempt in range(tries):
        try:
            if attempt > 0:
                backoff = float(sleep_sec) * (2 ** attempt)
                _sleep_with_jitter(backoff, sleep_jitter)
            else:
                _sleep_with_jitter(sleep_sec, sleep_jitter)

            df = _twse_fetch_month(stock_no, year, month, timeout=timeout)
            return df

        except Exception as e:
            last_err = e
            dq_flags.append("TWSE_FETCH_ERROR")
            dq_notes.append(f"TWSE fetch failed (attempt={attempt+1}/{tries}) for {year}-{month:02d}: {repr(e)}")

    dq_flags.append("TWSE_FETCH_FAILED_FINAL")
    dq_notes.append(f"TWSE month fetch exhausted retries for {year}-{month:02d}; last_error={repr(last_err)}")
    return pd.DataFrame()


def fetch_twse_recent(
    stock_no: str,
    months_back: int,
    dq_flags: List[str],
    dq_notes: List[str],
    *,
    twse_timeout: int,
    twse_max_retries: int,
    twse_sleep_sec: float,
    twse_sleep_jitter: float,
) -> pd.DataFrame:
    frames = []
    for (yy, mm) in _twse_months_back_list(months_back):
        dfm = _twse_fetch_month_with_retries(
            stock_no,
            yy,
            mm,
            dq_flags,
            dq_notes,
            timeout=twse_timeout,
            max_retries=twse_max_retries,
            sleep_sec=twse_sleep_sec,
            sleep_jitter=twse_sleep_jitter,
        )
        if dfm is not None and len(dfm) > 0:
            frames.append(dfm)

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

        # Evidence-only: detect if Adj Close was missing (we will synthesize = close)
        if "adjclose" not in df.columns:
            dq_flags.append("YFINANCE_ADJCLOSE_MISSING_SYNTHESIZED")
            dq_notes.append("yfinance did not provide 'Adj Close'; synthesized adjclose=close (may be unadjusted).")
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

    Index bounds:
      - last computable t satisfies t + fwd_days <= n-1  =>  t <= n - fwd_days - 1
      - therefore loop is range(0, n - fwd_days)  (stop is exclusive)
    """
    n = len(prices)
    out = np.full(n, np.nan, dtype=float)

    # minimal n to compute at least one entry (t=0) is fwd_days + 1
    if n < (fwd_days + 1):
        stats = ForwardMDDStats(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), -1, -1)
        return out, stats

    if valid_entry_mask is None:
        valid_entry_mask = np.ones(n, dtype=bool)

    for i in range(0, n - fwd_days):
        if not valid_entry_mask[i]:
            continue
        base = prices[i]
        if not np.isfinite(base) or base <= 0:
            continue
        future = prices[i + 1: i + fwd_days + 1]
        if future.size == 0:
            continue
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
        "rv_ann": None,       # decimal (e.g. 0.207 for 20.7%)
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
        "atr_pct": None,  # percent value (e.g. 1.66 means 1.66%)
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

    if tr.dropna().shape[0] < atr_days:
        return out

    atr = pd.Series(index=tr.index, dtype=float)
    tr_sma = tr.rolling(window=atr_days, min_periods=atr_days).mean()
    first_valid = tr_sma.first_valid_index()
    if first_valid is None:
        return out
    atr.loc[first_valid] = tr_sma.loc[first_valid]

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

    Note:
      - Cash dividends typically cause small drops (a few %) and will NOT trigger by default.
      - Splits / reverse splits / severe data breaks are what this targets.
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
        "bb_pos": latest.get("bb_pos"),             # clipped
        "bb_pos_raw": latest.get("bb_pos_raw"),     # unclipped
        "price_used": latest.get("price_used"),
        "run_ts_utc": meta.get("run_ts_utc"),
    })
    rows = sorted(rows, key=lambda r: r.get("day_key_local", ""))
    hist["rows"] = rows
    hist.setdefault("meta", {})["updated_at_utc"] = utc_now_iso_z()


# -------------------------
# NA packers (short-circuit path)
# -------------------------

def pack_fwd_na(label: str, fwd_days_used: int) -> Dict[str, Any]:
    return {
        "label": label,
        "definition": f"min(price[t+1..t+{fwd_days_used}]/price[t]-1), level-price based",
        "n": 0,
        "p50": None,
        "p25": None,
        "p10": None,
        "p05": None,
        "min": None,
        "min_entry_date": None,
        "min_entry_price": None,
        "min_future_date": None,
        "min_future_price": None,
    }


def pack_trend_na(ma_days: int, slope_days: int, slope_thr_pct: float) -> Dict[str, Any]:
    return {
        "trend_ma_days": int(ma_days),
        "trend_slope_days": int(slope_days),
        "trend_slope_thr_pct": float(slope_thr_pct),
        "trend_ma_last": None,
        "trend_slope_pct": None,
        "price_vs_trend_ma_pct": None,
        "state": "TREND_NA",
    }


def pack_vol_na(rv_days: int) -> Dict[str, Any]:
    return {
        "rv_days": int(rv_days),
        "rv_ann": None,
        "rv_ann_pctl": None,
        "rv_hist_n": 0,
        "rv_hist_q20": None,
        "rv_hist_q50": None,
        "rv_hist_q80": None,
    }


def pack_atr_na(atr_days: int) -> Dict[str, Any]:
    return {
        "atr_days": int(atr_days),
        "atr": None,
        "atr_pct": None,
        "tr_mode": "NA",
    }


def pack_regime_na(rv_pctl_max_100: float, min_samples: int, trend_required: str) -> Dict[str, Any]:
    return {
        "definition": "TREND_UP & RV20_percentile<=pctl_max & rv_hist_n>=min_samples => RISK_ON_ALLOWED",
        "params": {
            "rv_pctl_max": float(rv_pctl_max_100),
            "min_samples": int(min_samples),
            "trend_required": str(trend_required),
        },
        "inputs": {
            "trend_state": "TREND_NA",
            "rv_ann": None,
            "rv_ann_pctl": None,
            "rv_hist_n": 0,
            "bb_state": "NA",
        },
        "passes": {
            "trend_ok": False,
            "rv_hist_ok": False,
            "rv_ok": False,
        },
        "tag": "RISK_ON_UNKNOWN",
        "allowed": False,
        "reasons": ["unadjusted_price_mode_or_insufficient_history"],
    }


# -------------------------
# forward_mdd conditional (ADD-ONLY)
# -------------------------

def _bbz_bucket_masks_5(bbz: np.ndarray) -> List[Tuple[str, str, np.ndarray]]:
    """
    Mutually exclusive bb_z buckets aligned with classify_state thresholds.
    """
    z = bbz
    finite = np.isfinite(z)

    return [
        ("z_le_-2.0", "bb_z<=-2.0", finite & (z <= -2.0)),
        ("-2.0_to_-1.5", "-2.0<bb_z<=-1.5", finite & (z > -2.0) & (z <= -1.5)),
        ("-1.5_to_1.5", "-1.5<bb_z<1.5", finite & (z > -1.5) & (z < 1.5)),
        ("1.5_to_2.0", "1.5<=bb_z<2.0", finite & (z >= 1.5) & (z < 2.0)),
        ("z_ge_2.0", "bb_z>=2.0", finite & (z >= 2.0)),
    ]


def _pack_fwd_bucket_stats(
    *,
    fwd_arr: np.ndarray,
    prices_np: np.ndarray,
    df_dates: pd.Series,
    fwd_days_used: int,
    bucket_mask: np.ndarray,
    bucket_id: str,
    bucket_label: str,
) -> Dict[str, Any]:
    """
    Compute quantiles/min audit trail for forward_mdd values restricted to a bucket_mask on entry t.

    IMPORTANT: This is additive analytics only; it does NOT alter fwd_arr or any existing outputs.
    """
    idx = np.where(bucket_mask & np.isfinite(fwd_arr))[0]
    if idx.size == 0:
        return {
            "bucket_id": bucket_id,
            "bucket_label": bucket_label,
            "n": 0,
            "p50": None,
            "p25": None,
            "p10": None,
            "p05": None,
            "min": None,
            "min_entry_date": None,
            "min_entry_price": None,
            "min_future_date": None,
            "min_future_price": None,
        }

    v = fwd_arr[idx].astype(float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {
            "bucket_id": bucket_id,
            "bucket_label": bucket_label,
            "n": 0,
            "p50": None,
            "p25": None,
            "p10": None,
            "p05": None,
            "min": None,
            "min_entry_date": None,
            "min_entry_price": None,
            "min_future_date": None,
            "min_future_price": None,
        }

    mn = float(np.min(v))

    # map back to original entry index
    vals_on_idx = fwd_arr[idx].astype(float)
    entry_pos = int(np.nanargmin(vals_on_idx))
    entry_idx = int(idx[entry_pos])

    # audit trail for bucket-min entry
    min_entry_date = None
    min_future_date = None
    min_entry_price = None
    min_future_price = None

    try:
        if 0 <= entry_idx < len(prices_np):
            base = float(prices_np[entry_idx])
            future = prices_np[entry_idx + 1: entry_idx + fwd_days_used + 1]
            if np.isfinite(base) and base > 0 and future.size > 0:
                rel = future / base - 1.0
                if np.isfinite(rel).any():
                    off = int(np.nanargmin(rel))
                    future_idx = entry_idx + 1 + off

                    if 0 <= future_idx < len(prices_np):
                        min_entry_date = pd.to_datetime(df_dates.iloc[entry_idx]).strftime("%Y-%m-%d")
                        min_future_date = pd.to_datetime(df_dates.iloc[future_idx]).strftime("%Y-%m-%d")
                        min_entry_price = _nan_to_none(base)
                        min_future_price = _nan_to_none(float(prices_np[future_idx]))
    except Exception:
        pass

    return {
        "bucket_id": bucket_id,
        "bucket_label": bucket_label,
        "n": int(v.size),
        "p50": _nan_to_none(float(np.quantile(v, 0.50))),
        "p25": _nan_to_none(float(np.quantile(v, 0.25))),
        "p10": _nan_to_none(float(np.quantile(v, 0.10))),
        "p05": _nan_to_none(float(np.quantile(v, 0.05))),
        "min": _nan_to_none(mn),
        "min_entry_date": min_entry_date,
        "min_entry_price": min_entry_price,
        "min_future_date": min_future_date,
        "min_future_price": min_future_price,
    }


def build_forward_mdd_conditional_block(
    *,
    bbz_np: np.ndarray,
    prices_np: np.ndarray,
    df_dates: pd.Series,
    fwd_days_20: int,
    fwd_days_10: int,
    fwd_raw_20: np.ndarray,
    fwd_clean_20: np.ndarray,
    fwd_primary_20: np.ndarray,
    fwd_raw_10: np.ndarray,
    fwd_clean_10: np.ndarray,
    fwd_primary_10: np.ndarray,
    forward_mode_primary: str,
) -> Dict[str, Any]:
    buckets = _bbz_bucket_masks_5(bbz_np)

    def _pack_one(arr: np.ndarray, fwd_days_used: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for (bid, blabel, bmask) in buckets:
            out[bid] = _pack_fwd_bucket_stats(
                fwd_arr=arr,
                prices_np=prices_np,
                df_dates=df_dates,
                fwd_days_used=fwd_days_used,
                bucket_mask=bmask,
                bucket_id=bid,
                bucket_label=blabel,
            )
        return out

    return {
        "meta": {
            "scheme": "bb_z_5bucket_v1",
            "note": "condition evaluated at entry t using bb_z[t]; stats computed on already-produced forward_mdd arrays (respecting raw/clean masks).",
            "thresholds": {"near": 1.5, "extreme": 2.0},
            "forward_mode_primary": str(forward_mode_primary),
        },
        "20D": {
            "raw": _pack_one(fwd_raw_20, fwd_days_20),
            "clean": _pack_one(fwd_clean_20, fwd_days_20),
            "primary": _pack_one(fwd_primary_20, fwd_days_20),
        },
        "10D": {
            "raw": _pack_one(fwd_raw_10, fwd_days_10),
            "clean": _pack_one(fwd_clean_10, fwd_days_10),
            "primary": _pack_one(fwd_primary_10, fwd_days_10),
        },
    }


def pack_forward_mdd_conditional_na(*, forward_mode_primary: str) -> Dict[str, Any]:
    """
    NA packer for short-circuit (unadjusted price mode).
    Keeps schema stable without altering existing logic.
    """
    dummy_buckets = [
        ("z_le_-2.0", "bb_z<=-2.0"),
        ("-2.0_to_-1.5", "-2.0<bb_z<=-1.5"),
        ("-1.5_to_1.5", "-1.5<bb_z<1.5"),
        ("1.5_to_2.0", "1.5<=bb_z<2.0"),
        ("z_ge_2.0", "bb_z>=2.0"),
    ]

    def _empty_bucket_dict() -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for bid, blabel in dummy_buckets:
            out[bid] = {
                "bucket_id": bid,
                "bucket_label": blabel,
                "n": 0,
                "p50": None,
                "p25": None,
                "p10": None,
                "p05": None,
                "min": None,
                "min_entry_date": None,
                "min_entry_price": None,
                "min_future_date": None,
                "min_future_price": None,
            }
        return out

    return {
        "meta": {
            "scheme": "bb_z_5bucket_v1",
            "note": "NA due to unadjusted_price_mode short-circuit.",
            "thresholds": {"near": 1.5, "extreme": 2.0},
            "forward_mode_primary": str(forward_mode_primary),
        },
        "20D": {"raw": _empty_bucket_dict(), "clean": _empty_bucket_dict(), "primary": _empty_bucket_dict()},
        "10D": {"raw": _empty_bucket_dict(), "clean": _empty_bucket_dict(), "primary": _empty_bucket_dict()},
    }


# -------------------------
# Pledge guidance (compute-only; additive)
# -------------------------

def compute_pledge_guidance_block(
    *,
    latest_price: Optional[float],
    bb_state: str,
    bb_z: Optional[float],
    regime: Dict[str, Any],
    forward20_primary: Dict[str, Any],
    forward10_primary: Dict[str, Any],
    dq_flags: List[str],
    forward_mode: str,
) -> Dict[str, Any]:
    """
    Pledge guidance (compute-only; deterministic; non-predictive):
    - DOES NOT change any existing logic/fields.
    - Uses only already-computed fields: bb_state/bb_z/regime/forward_mdd + dq_flags.
    - Intended as a conservative veto/guardrail for "pledge to add" decisions.
    """
    ACCUM_Z = -1.5
    NO_CHASE_Z = 1.5

    # DQ veto flags: if present, refuse to advise pledge-add
    DQ_VETO = {
        "UNADJUSTED_PRICE_MODE",
        "DATA_SOURCE_TWSE_FALLBACK",
        "TWSE_UNADJUSTED_PRICE_WARNING",
        "FWD_MDD_CORP_ACTION_CONTAMINATION_RISK",
        "PRICE_COL_FALLBACK_UNADJUSTED",
        "YFINANCE_IMPORT_ERROR",
        "YFINANCE_ERROR",
        "TWSE_FETCH_FAILED_FINAL",
    }

    def _get_fwd_dd(d: Dict[str, Any], k: str) -> Optional[float]:
        v = safe_get(d, k, None)
        return _nan_to_none(v)

    def _level(label: str, dd: Optional[float]) -> Dict[str, Any]:
        if latest_price is None or (dd is None):
            return {"label": label, "drawdown": dd, "price_level": None}
        try:
            return {"label": label, "drawdown": float(dd), "price_level": float(latest_price) * (1.0 + float(dd))}
        except Exception:
            return {"label": label, "drawdown": dd, "price_level": None}

    veto_reasons: List[str] = []
    regime_allowed = bool(safe_get(regime, "allowed", False))

    # 1) Data quality veto
    hit_dq = sorted([f for f in dq_flags if f in DQ_VETO])
    if hit_dq:
        veto_reasons.append("data_quality_veto:" + ",".join(hit_dq))

    # 2) Regime gate veto
    if not regime_allowed:
        veto_reasons.append("regime_gate_closed")

    # 3) No-chase veto (upper band / high z)
    z = None
    try:
        z = float(bb_z) if bb_z is not None else None
    except Exception:
        z = None

    if bb_state in ("EXTREME_UPPER_BAND", "NEAR_UPPER_BAND"):
        veto_reasons.append(f"no_chase_state:{bb_state}")
    if (z is not None) and np.isfinite(z) and (z >= NO_CHASE_Z):
        veto_reasons.append(f"no_chase_z>= {NO_CHASE_Z:.2f}")

    pledge_policy = "DISALLOW"
    action_bucket = "HOLD_NO_PLEDGE"

    if veto_reasons:
        pledge_policy = "DISALLOW"
        action_bucket = "DATA_QUALITY_VETO" if any(r.startswith("data_quality_veto") for r in veto_reasons) else "VETO"
    else:
        if (z is not None) and np.isfinite(z) and (z <= ACCUM_Z):
            pledge_policy = "ALLOW"
            action_bucket = "ACCUMULATE_OK"
        else:
            pledge_policy = "DISALLOW"
            action_bucket = "HOLD_NO_PLEDGE"

    dd_10_p10 = _get_fwd_dd(forward10_primary, "p10")
    dd_10_p05 = _get_fwd_dd(forward10_primary, "p05")
    dd_20_p10 = _get_fwd_dd(forward20_primary, "p10")
    dd_20_p05 = _get_fwd_dd(forward20_primary, "p05")

    tranche_levels = [
        _level("10D_p10_uncond", dd_10_p10),
        _level("10D_p05_uncond", dd_10_p05),
        _level("20D_p10_uncond", dd_20_p10),
        _level("20D_p05_uncond", dd_20_p05),
    ]

    return {
        "version": "pledge_guidance_v1",
        "scope": "compute_only_no_margin_no_chip",
        "thresholds": {
            "accumulate_z_threshold": ACCUM_Z,
            "no_chase_z_threshold": NO_CHASE_Z,
            "require_regime_allowed": True,
        },
        "inputs": {
            "bb_state": bb_state,
            "bb_z": _nan_to_none(z),
            "regime_allowed": regime_allowed,
            "forward_mode_primary": str(forward_mode),
        },
        "decision": {
            "pledge_policy": pledge_policy,         # ALLOW / DISALLOW
            "action_bucket": action_bucket,
            "veto_reasons": veto_reasons,
        },
        "unconditional_tranche_levels": {
            "price_anchor": _nan_to_none(latest_price),
            "note": "levels derived from unconditional forward_mdd quantiles; not conditioned on current state",
            "levels": tranche_levels,
        },
    }


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

    # Sidecar short forward window (default 10D)
    ap.add_argument("--fwd_days_short", type=int, default=10)

    # Support both names to avoid yml mismatch
    ap.add_argument("--price_col", default="adjclose")
    ap.add_argument("--price_col_requested", default=None)

    # v10: TWSE fallback is short-circuit mode (unadjusted), so default should be small
    ap.add_argument("--twse_months_back", type=int, default=2)
    ap.add_argument("--twse_months_back_unadjusted_cap", type=int, default=2)

    # TWSE fallback throttling / retries
    ap.add_argument("--twse_timeout", type=int, default=20)
    ap.add_argument("--twse_max_retries", type=int, default=3)
    ap.add_argument("--twse_sleep_sec", type=float, default=1.0)
    ap.add_argument("--twse_sleep_jitter", type=float, default=0.5)

    # Outlier tagging for raw (20D)
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
    twse_months_eff = None

    if df is None or len(df) == 0:
        used_fallback = True
        dq_flags.append("DATA_SOURCE_TWSE_FALLBACK")
        stock_no = _ticker_to_twse_stock_no(ticker, default="0050")

        # v10 short-circuit: cap months_back in unadjusted mode to avoid I/O blackhole
        req_mb = max(1, int(args.twse_months_back))
        cap_mb = max(1, int(args.twse_months_back_unadjusted_cap))
        twse_months_eff = min(req_mb, cap_mb)

        dq_notes.append(
            f"Used TWSE fallback (raw/unadjusted). months_back requested={req_mb}, cap_unadjusted={cap_mb}, "
            f"effective={twse_months_eff}, stockNo={stock_no}."
        )

        df = fetch_twse_recent(
            stock_no=stock_no,
            months_back=twse_months_eff,
            dq_flags=dq_flags,
            dq_notes=dq_notes,
            twse_timeout=int(args.twse_timeout),
            twse_max_retries=int(args.twse_max_retries),
            twse_sleep_sec=float(args.twse_sleep_sec),
            twse_sleep_jitter=float(args.twse_sleep_jitter),
        )

    if df is None or len(df) == 0:
        print("ERROR: no data from yfinance and TWSE fallback.", file=sys.stderr)
        stats_path = os.path.join(args.cache_dir, "stats_latest.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(
                {"meta": {"run_ts_utc": utc_now_iso_z(), "module": "tw0050_bb", "ticker": ticker,
                          "script_fingerprint": SCRIPT_FINGERPRINT},
                 "dq": {"flags": dq_flags, "notes": dq_notes}},
                f, ensure_ascii=False, indent=2
            )
        return 1

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    last_idx = len(df) - 1
    last_date = df.loc[last_idx, "date"].strftime("%Y-%m-%d")

    # choose price series
    if price_col_req in df.columns and df[price_col_req].notna().any():
        price_used = df[price_col_req].astype(float).copy()
        price_col_used = price_col_req
    else:
        # fallback attempt
        if "adjclose" in df.columns and df["adjclose"].notna().any():
            price_used = df["adjclose"].astype(float).copy()
            price_col_used = "adjclose"
        else:
            price_used = df["close"].astype(float).copy()
            price_col_used = "close"
        dq_flags.append("PRICE_COL_FALLBACK")
        dq_notes.append(f"requested={price_col_req} not usable; used={price_col_used}.")

    # Evidence-only audit: adjclose vs close
    adj_audit = adjclose_audit_vs_close(df, eps_rel=ADJCLOSE_AUDIT_EPS_REL, top_k=3)
    if (not used_fallback) and bool(adj_audit.get("available")):
        n_a = int(adj_audit.get("n") or 0)
        max_abs_rel = adj_audit.get("max_abs_rel_diff", None)
        try:
            max_abs_rel_f = float(max_abs_rel) if max_abs_rel is not None else None
        except Exception:
            max_abs_rel_f = None

        # Flag suspicious condition: adjclose ~= close everywhere
        if (n_a >= ADJCLOSE_AUDIT_MIN_N) and (max_abs_rel_f is not None) and np.isfinite(max_abs_rel_f) and (max_abs_rel_f <= ADJCLOSE_AUDIT_EPS_REL):
            dq_flags.append("ADJCLOSE_EQUALS_CLOSE_SUSPECT_UNADJUSTED")
            dq_notes.append(
                f"Adj Close equals Close within eps_rel={ADJCLOSE_AUDIT_EPS_REL} across n={n_a}; "
                f"data may be effectively unadjusted despite 'adjclose' label. (evidence-only; no auto short-circuit)"
            )

    latest_price = float(price_used.iloc[last_idx]) if np.isfinite(price_used.iloc[last_idx]) else float("nan")

    # unadjusted mode decision (v10)
    unadjusted_price_mode = bool(used_fallback) or (str(price_col_used).lower() != "adjclose")
    if unadjusted_price_mode:
        dq_flags.append("UNADJUSTED_PRICE_MODE")
        if used_fallback:
            dq_flags.append("TWSE_UNADJUSTED_PRICE_WARNING")
            dq_flags.append("FWD_MDD_CORP_ACTION_CONTAMINATION_RISK")
            dq_notes.append("TWSE fallback uses raw (unadjusted) daily prices; all derived indicators are short-circuited to NA.")
        if str(price_col_used).lower() != "adjclose":
            dq_flags.append("PRICE_COL_FALLBACK_UNADJUSTED")
            dq_notes.append(f"price_col_used={price_col_used} (not adjclose); indicators short-circuited to NA to avoid dividend/corp-action contamination.")

    # --- common meta ---
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
        "reliability": "LOW" if unadjusted_price_mode else "HIGH",
        "reliability_reason": (
            ["unadjusted_price_mode"] if unadjusted_price_mode else ["yfinance_adjclose_ok"]
        ),
        "bb_window": int(args.bb_window),
        "bb_k": float(args.bb_k),
        "fwd_days": int(args.fwd_days),
        "fwd_days_short": int(args.fwd_days_short),
        "price_calc": str(price_col_used),
        "price_col_requested": price_col_req,
        "price_col_used": str(price_col_used),
        "last_date": last_date,
        "break_detection": {
            "break_ratio_hi": float(args.break_ratio_hi),
            "break_ratio_lo": float(args.break_ratio_lo),
            "break_count": None,  # filled in normal path
            "forward_mode_primary": str(args.forward_mode).lower(),
        },
        "twse_fallback_policy": {
            "months_back_requested": int(args.twse_months_back),
            "months_back_unadjusted_cap": int(args.twse_months_back_unadjusted_cap),
            "months_back_effective": int(twse_months_eff) if twse_months_eff is not None else None,
            "timeout_sec": int(args.twse_timeout),
            "max_retries": int(args.twse_max_retries),
            "sleep_sec": float(args.twse_sleep_sec),
            "sleep_jitter_sec": float(args.twse_sleep_jitter),
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
        "shortcircuit": {
            "enabled": True,
            "unadjusted_price_mode": bool(unadjusted_price_mode),
            "skipped_compute_when_unadjusted": True,
        },
        # ADD-ONLY: evidence about whether adjclose is meaningfully different from close
        "adjclose_audit": adj_audit,
        "adjclose_audit_policy": {
            "eps_rel": float(ADJCLOSE_AUDIT_EPS_REL),
            "min_n": int(ADJCLOSE_AUDIT_MIN_N),
            "note": "Evidence-only; does not alter short-circuit rules. Use DQ flags/notes to interpret."
        },
    }

    # -------------------------
    # v10 SHORT-CIRCUIT PATH
    # -------------------------
    if unadjusted_price_mode:
        # official latest block: BB-related fields must be None to prevent dirty-data leakage
        latest = {
            "date": last_date,
            "close": _nan_to_none(float(df.loc[last_idx, "close"])) if "close" in df.columns else None,
            "adjclose": _nan_to_none(float(df.loc[last_idx, "adjclose"])) if "adjclose" in df.columns else None,
            "price_used": _nan_to_none(latest_price),

            "bb_ma": None,
            "bb_sd": None,
            "bb_upper": None,
            "bb_lower": None,
            "bb_z": None,
            "bb_pos": None,
            "bb_pos_raw": None,
            "dist_to_lower_pct": None,
            "dist_to_upper_pct": None,
            "band_width_geo_pct": None,
            "band_width_std_pct": None,

            "state": "NA_DUE_TO_UNADJUSTED_PRICE",
        }

        fwd_days = int(args.fwd_days)
        fwd_days_short = int(args.fwd_days_short)
        forward_mode = str(args.forward_mode).lower()

        forward20_primary = pack_fwd_na(f"forward_mdd_{forward_mode}_20D", fwd_days)
        forward10_primary = pack_fwd_na(f"forward_mdd_{forward_mode}_10D", fwd_days_short)

        # keep audit extra keys but NA to preserve schema stability
        forward20_raw = pack_fwd_na("forward_mdd_raw_20D", fwd_days)
        forward20_clean = pack_fwd_na("forward_mdd_clean_20D", fwd_days)
        forward10_raw = pack_fwd_na("forward_mdd_raw_10D", fwd_days_short)
        forward10_clean = pack_fwd_na("forward_mdd_clean_10D", fwd_days_short)

        trend = pack_trend_na(int(args.trend_ma_days), int(args.trend_slope_days), float(args.trend_slope_thr_pct))
        vol_rv = pack_vol_na(int(args.rv_days))
        atr = pack_atr_na(int(args.atr_days))

        pctl_max_100 = float(args.regime_rv_pctl_max) * 100.0
        min_samples = int(args.regime_min_samples)
        regime = pack_regime_na(pctl_max_100, min_samples, trend_required="TREND_UP")

        # pledge: deterministic DISALLOW via DQ veto + regime gate closed
        pledge_block = compute_pledge_guidance_block(
            latest_price=_nan_to_none(latest_price),
            bb_state=latest["state"],
            bb_z=None,
            regime=regime,
            forward20_primary=forward20_primary,
            forward10_primary=forward10_primary,
            dq_flags=dq_flags,
            forward_mode=forward_mode,
        )

        # ADD-ONLY: conditional forward_mdd schema in NA form (short-circuit)
        fwd_conditional = pack_forward_mdd_conditional_na(forward_mode_primary=forward_mode)

        stats_out = {
            "meta": meta,
            "latest": latest,

            "forward_mdd": forward20_primary,
            "forward_mdd10": forward10_primary,

            "forward_mdd_raw": forward20_raw,
            "forward_mdd_clean": forward20_clean,

            "forward_mdd10_raw": forward10_raw,
            "forward_mdd10_clean": forward10_clean,

            # ADD-ONLY
            "forward_mdd_conditional": fwd_conditional,

            "trend": trend,
            "vol": vol_rv,
            "atr": atr,
            "regime": regime,

            "pledge": pledge_block,

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

        print(f"[OK][SHORTCIRCUIT] wrote: {stats_path}")
        print(f"[OK][SHORTCIRCUIT] wrote: {out_csv_path}")
        print(f"[OK][SHORTCIRCUIT] wrote: {hist_path}")
        return 0

    # -------------------------
    # NORMAL COMPUTE PATH (adjusted / yfinance adjclose)
    # -------------------------

    w = int(args.bb_window)
    k = float(args.bb_k)

    # BB
    ma, sd, upper, lower = compute_bb(price_used, window=w, k=k)

    latest_ma = float(ma.iloc[last_idx]) if np.isfinite(ma.iloc[last_idx]) else float("nan")
    latest_sd = float(sd.iloc[last_idx]) if np.isfinite(sd.iloc[last_idx]) else float("nan")
    latest_upper = float(upper.iloc[last_idx]) if np.isfinite(upper.iloc[last_idx]) else float("nan")
    latest_lower = float(lower.iloc[last_idx]) if np.isfinite(lower.iloc[last_idx]) else float("nan")

    bb_z = float((latest_price - latest_ma) / latest_sd) if np.isfinite(latest_sd) and latest_sd > 0 else float("nan")

    denom = (latest_upper - latest_lower)
    pos_raw = float((latest_price - latest_lower) / denom) if np.isfinite(denom) and denom != 0 else float("nan")
    pos = _clip01(pos_raw)

    dist_to_lower_pct = ((latest_price - latest_lower) / latest_price) * 100.0 if np.isfinite(latest_lower) and latest_price > 0 else float("nan")
    dist_to_upper_pct = ((latest_upper - latest_price) / latest_price) * 100.0 if np.isfinite(latest_upper) and latest_price > 0 else float("nan")

    band_width_geo_pct = ((latest_upper / latest_lower) - 1.0) * 100.0 if (np.isfinite(latest_upper) and np.isfinite(latest_lower) and latest_lower > 0) else float("nan")
    band_width_std_pct = ((latest_upper - latest_lower) / latest_ma) * 100.0 if (np.isfinite(latest_upper) and np.isfinite(latest_lower) and np.isfinite(latest_ma) and latest_ma != 0) else float("nan")

    state = classify_state(bb_z=bb_z, bb_pos=pos)

    prices_np = price_used.to_numpy(dtype=float)
    n_prices = int(len(prices_np))

    # forward_mdd(20D): raw + clean
    fwd_days = int(args.fwd_days)
    fwd_raw_arr, fwd_raw_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days)

    breaks = detect_price_breaks(prices_np, ratio_hi=float(args.break_ratio_hi), ratio_lo=float(args.break_ratio_lo))
    break_idxs = np.where(breaks)[0].tolist()
    meta["break_detection"]["break_count"] = int(len(break_idxs))

    clean_mask_20 = build_clean_entry_mask(n_prices, breaks, fwd_days=fwd_days)
    fwd_clean_arr, fwd_clean_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days, valid_entry_mask=clean_mask_20)

    # forward_mdd(10D): raw + clean
    fwd_days_short = int(args.fwd_days_short)
    fwd10_raw_arr, fwd10_raw_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days_short)
    clean_mask_10 = build_clean_entry_mask(n_prices, breaks, fwd_days=fwd_days_short)
    fwd10_clean_arr, fwd10_clean_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days_short, valid_entry_mask=clean_mask_10)

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

    # Raw outlier tagging (20D)
    thr = float(args.outlier_min_threshold)
    raw_outlier = (fwd_raw_stats.n > 0 and np.isfinite(fwd_raw_stats.min) and fwd_raw_stats.min < thr)
    if raw_outlier:
        dq_flags.append("FWD_MDD_OUTLIER_MIN_RAW_20D")
        dq_notes.append(f"forward_mdd_raw_20D min={fwd_raw_stats.min:.4f} < threshold({thr}); see raw min_audit_trail.")
        if str(args.forward_mode).lower() == "clean":
            dq_flags.append("RAW_OUTLIER_EXCLUDED_BY_CLEAN")
            dq_notes.append("Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.")

    forward_mode = str(args.forward_mode).lower()
    primary20_stats = fwd_clean_stats if forward_mode == "clean" else fwd_raw_stats
    primary10_stats = fwd10_clean_stats if forward_mode == "clean" else fwd10_raw_stats

    def min_audit_from(stats: ForwardMDDStats, fwd_days_used: int) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[float]]:
        if stats.n <= 0 or stats.min_entry_idx < 0 or stats.min_future_idx < 0:
            return None, None, None, None
        if stats.min_entry_idx >= len(df) or stats.min_future_idx >= len(df):
            return None, None, None, None
        if stats.min_future_idx <= stats.min_entry_idx or (stats.min_future_idx - stats.min_entry_idx) > fwd_days_used:
            return None, None, None, None
        med = df.loc[stats.min_entry_idx, "date"].strftime("%Y-%m-%d")
        mfd = df.loc[stats.min_future_idx, "date"].strftime("%Y-%m-%d")
        mep = float(prices_np[stats.min_entry_idx])
        mfp = float(prices_np[stats.min_future_idx])
        return med, mep, mfd, mfp

    def pack_fwd(stats: ForwardMDDStats, label: str, fwd_days_used: int) -> Dict[str, Any]:
        med, mep, mfd, mfp = min_audit_from(stats, fwd_days_used=fwd_days_used)
        return {
            "label": label,
            "definition": f"min(price[t+1..t+{fwd_days_used}]/price[t]-1), level-price based",
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

    forward20_primary = pack_fwd(primary20_stats, f"forward_mdd_{forward_mode}_20D", fwd_days_used=fwd_days)
    forward20_raw = pack_fwd(fwd_raw_stats, "forward_mdd_raw_20D", fwd_days_used=fwd_days)
    forward20_clean = pack_fwd(fwd_clean_stats, "forward_mdd_clean_20D", fwd_days_used=fwd_days)

    forward10_primary = pack_fwd(primary10_stats, f"forward_mdd_{forward_mode}_10D", fwd_days_used=fwd_days_short)
    forward10_raw = pack_fwd(fwd10_raw_stats, "forward_mdd_raw_10D", fwd_days_used=fwd_days_short)
    forward10_clean = pack_fwd(fwd10_clean_stats, "forward_mdd_clean_10D", fwd_days_used=fwd_days_short)

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

    if state == "EXTREME_UPPER_BAND":
        regime["reasons"].append("bb_extreme_upper_band_stretched")
    if state == "EXTREME_LOWER_BAND":
        regime["reasons"].append("bb_extreme_lower_band_stressed")

    latest = {
        "date": last_date,
        "close": _nan_to_none(float(df.loc[last_idx, "close"])) if "close" in df.columns else None,
        "adjclose": _nan_to_none(float(df.loc[last_idx, "adjclose"])) if "adjclose" in df.columns else None,
        "price_used": _nan_to_none(latest_price),

        "bb_ma": _nan_to_none(latest_ma),
        "bb_sd": _nan_to_none(latest_sd),
        "bb_upper": _nan_to_none(latest_upper),
        "bb_lower": _nan_to_none(latest_lower),
        "bb_z": _nan_to_none(bb_z),

        "bb_pos": _nan_to_none(pos),
        "bb_pos_raw": _nan_to_none(pos_raw),

        "dist_to_lower_pct": _nan_to_none(dist_to_lower_pct),
        "dist_to_upper_pct": _nan_to_none(dist_to_upper_pct),

        "band_width_geo_pct": _nan_to_none(band_width_geo_pct),
        "band_width_std_pct": _nan_to_none(band_width_std_pct),

        "state": state,
    }

    pledge_block = compute_pledge_guidance_block(
        latest_price=_nan_to_none(latest_price),
        bb_state=state,
        bb_z=_nan_to_none(bb_z),
        regime=regime,
        forward20_primary=forward20_primary,
        forward10_primary=forward10_primary,
        dq_flags=dq_flags,
        forward_mode=forward_mode,
    )

    # -------------------------
    # ADD-ONLY: forward_mdd_conditional (bb_z bucket conditioned distributions)
    # -------------------------
    # full-series bb_z for conditional analysis only (does NOT change any existing logic)
    sd_safe = sd.replace(0.0, np.nan)
    bbz_series = (price_used - ma) / sd_safe
    bbz_np = bbz_series.to_numpy(dtype=float)

    # primary arrays for conditional block follow the same forward_mode choice already used elsewhere
    fwd_primary_20_arr = fwd_clean_arr if forward_mode == "clean" else fwd_raw_arr
    fwd_primary_10_arr = fwd10_clean_arr if forward_mode == "clean" else fwd10_raw_arr

    fwd_conditional = build_forward_mdd_conditional_block(
        bbz_np=bbz_np,
        prices_np=prices_np,
        df_dates=df["date"],
        fwd_days_20=fwd_days,
        fwd_days_10=fwd_days_short,
        fwd_raw_20=fwd_raw_arr,
        fwd_clean_20=fwd_clean_arr,
        fwd_primary_20=fwd_primary_20_arr,
        fwd_raw_10=fwd10_raw_arr,
        fwd_clean_10=fwd10_clean_arr,
        fwd_primary_10=fwd_primary_10_arr,
        forward_mode_primary=forward_mode,
    )

    stats_out = {
        "meta": meta,
        "latest": latest,

        "forward_mdd": forward20_primary,
        "forward_mdd10": forward10_primary,

        "forward_mdd_raw": forward20_raw,
        "forward_mdd_clean": forward20_clean,

        "forward_mdd10_raw": forward10_raw,
        "forward_mdd10_clean": forward10_clean,

        # ADD-ONLY
        "forward_mdd_conditional": fwd_conditional,

        "trend": trend,
        "vol": vol_rv,
        "atr": atr,
        "regime": regime,

        "pledge": pledge_block,

        "dq": {"flags": dq_flags, "notes": dq_notes},
    }

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats_out, f, ensure_ascii=False, indent=2, sort_keys=True)

    out_df = df.copy()
    out_df["date"] = out_df["date"].dt.strftime("%Y-%m-%d")
    out_csv = _df_to_csv_min(out_df)
    out_csv_path = os.path.join(args.cache_dir, "data.csv")
    out_csv.to_csv(out_csv_path, index=False)

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