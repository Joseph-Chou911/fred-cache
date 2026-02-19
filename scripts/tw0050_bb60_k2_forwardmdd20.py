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

Key fix vs your current failure:
  - force ticker / price_col to scalar string to avoid yfinance AttributeError:
      "'tuple' object has no attribute 'lower'"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz
import requests

try:
    import yfinance as yf
except Exception:
    yf = None  # allow fallback-only mode


SCRIPT_FINGERPRINT = "tw0050_bb60_k2_forwardmdd20@2026-02-19.v3"
TZ_LOCAL = "Asia/Taipei"


# -------------------------
# Helpers (audit-friendly)
# -------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _to_scalar_str(x: Any, default: str = "") -> str:
    """
    Convert x into a scalar string.
    - If x is list/tuple, take first element (common when argparse uses nargs=1/+).
    - If x is None, return default.
    """
    if x is None:
        return default
    if isinstance(x, (list, tuple)):
        if len(x) == 0:
            return default
        return str(x[0])
    return str(x)

def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and x.strip().upper() in ("N/A", "NA", ""):
            return None
        return float(x)
    except Exception:
        return None

def _quantile(a: np.ndarray, q: float) -> float:
    if a.size == 0:
        return float("nan")
    return float(np.quantile(a, q))

def _nan_to_none(x: float) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(x)

def _df_to_csv_min(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize to minimal columns for audit
    cols = []
    for c in ["date", "close", "adjclose", "volume"]:
        if c in df.columns:
            cols.append(c)
    return df[cols].copy()

def _local_day_key(ts: datetime) -> str:
    tz = pytz.timezone(TZ_LOCAL)
    return ts.astimezone(tz).strftime("%Y-%m-%d")


# -------------------------
# TWSE fallback (recent)
# -------------------------

def _twse_months_back_list(months_back: int) -> List[Tuple[int, int]]:
    """
    Generate (year, month) list from now back N months, inclusive.
    """
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
    TWSE STOCK_DAY endpoint.
    Note: returns daily data for one month.
    """
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
    date_str = f"{year}{month:02d}01"
    params = {
        "date": date_str,
        "stockNo": stock_no,
        "response": "json",
    }
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    j = r.json()
    if j.get("stat") != "OK" or "data" not in j:
        return pd.DataFrame()

    data = j["data"]
    fields = j.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=fields)

    # TWSE uses ROC date like "114/02/03"
    # We convert to Gregorian yyyy-mm-dd
    def roc_to_date(s: str) -> Optional[str]:
        try:
            s = str(s).strip()
            if "/" not in s:
                return None
            roc_y, mm, dd = s.split("/")
            gy = int(roc_y) + 1911
            return f"{gy:04d}-{int(mm):02d}-{int(dd):02d}"
        except Exception:
            return None

    # Try to locate date/close/volume columns by Chinese field names
    # Common fields: "日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"
    col_date = None
    col_close = None
    col_vol = None
    for c in df.columns:
        if "日期" in c:
            col_date = c
        if "收盤" in c:
            col_close = c
        if "成交股數" in c:
            col_vol = c

    if not col_date or not col_close:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["date"] = df[col_date].map(roc_to_date)
    out["close"] = df[col_close].astype(str).str.replace(",", "", regex=False)
    if col_vol:
        out["volume"] = df[col_vol].astype(str).str.replace(",", "", regex=False)
    else:
        out["volume"] = None

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).sort_values("date")

    # TWSE fallback has no adjclose; treat adjclose=close
    out["adjclose"] = out["close"]
    return out[["date", "close", "adjclose", "volume"]].reset_index(drop=True)

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
        # Robust: download is less quirky than some Ticker.history paths
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

        # If multiindex columns appear, flatten
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        df = df.reset_index()  # Date -> column
        # Standardize names
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

        for c in ["date", "close"]:
            if c not in df.columns:
                return pd.DataFrame()

        if "adjclose" not in df.columns:
            df["adjclose"] = df["close"]

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ["close", "adjclose", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
        return df[["date", "close", "adjclose", "volume"]]
    except Exception as e:
        dq_flags.append("YFINANCE_ERROR")
        dq_notes.append(f"yfinance fetch failed: {e.__class__.__name__}: {e}")
        return pd.DataFrame()


# -------------------------
# Indicators
# -------------------------

def compute_bb(price: pd.Series, window: int, k: float) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    ma = price.rolling(window=window, min_periods=window).mean()
    # ddof=0 for population std (more stable; audit-friendly)
    sd = price.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    return ma, sd, upper, lower


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


def compute_forward_mdd(prices: np.ndarray, fwd_days: int) -> Tuple[np.ndarray, ForwardMDDStats]:
    """
    forward_mdd[t] = min(prices[t+1..t+fwd]/prices[t] - 1)
    Only defined for t where t+fwd < len(prices).
    """
    n = len(prices)
    if n < (fwd_days + 2):
        arr = np.array([], dtype=float)
        stats = ForwardMDDStats(
            n=0, p50=float("nan"), p25=float("nan"), p10=float("nan"), p05=float("nan"),
            min=float("nan"), min_entry_idx=-1, min_future_idx=-1
        )
        return arr, stats

    out = np.full(n, np.nan, dtype=float)

    # brute force but small enough (~5000)
    for i in range(0, n - fwd_days - 1):
        base = prices[i]
        if not np.isfinite(base) or base <= 0:
            continue
        future = prices[i+1 : i+fwd_days+1]
        rel = future / base - 1.0
        out[i] = np.nanmin(rel)

    valid = out[np.isfinite(out)]
    if valid.size == 0:
        stats = ForwardMDDStats(
            n=0, p50=float("nan"), p25=float("nan"), p10=float("nan"), p05=float("nan"),
            min=float("nan"), min_entry_idx=-1, min_future_idx=-1
        )
        return out, stats

    mn = float(np.min(valid))
    # find entry idx in original out
    entry_idx = int(np.nanargmin(out))

    # find future idx producing that min
    base = prices[entry_idx]
    future = prices[entry_idx+1 : entry_idx+fwd_days+1]
    rel = future / base - 1.0
    future_offset = int(np.nanargmin(rel))  # 0..fwd_days-1
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


def classify_state(bb_z: float, bb_pos: float) -> str:
    # deterministic, simple
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


# -------------------------
# history_lite (minimal)
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
    # remove same day
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

    # support both names to avoid yml/script mismatch
    ap.add_argument("--price_col", default="adjclose")
    ap.add_argument("--price_col_requested", default=None)

    ap.add_argument("--twse_months_back", type=int, default=6)
    ap.add_argument("--outlier_min_threshold", type=float, default=-0.4)

    args = ap.parse_args()

    dq_flags: List[str] = []
    dq_notes: List[str] = []

    ticker = _to_scalar_str(args.ticker).strip()
    if not ticker:
        print("ERROR: empty --ticker after normalization", file=sys.stderr)
        return 2

    # normalize price_col
    price_col_req = args.price_col_requested if args.price_col_requested is not None else args.price_col
    price_col_req = _to_scalar_str(price_col_req, "adjclose").strip().lower()
    if price_col_req not in ("adjclose", "close"):
        # keep permissive: allow unknown but will fallback
        dq_flags.append("PRICE_COL_UNUSUAL")
        dq_notes.append(f"price_col_requested={price_col_req}; will fallback to available columns if missing.")

    ensure_dir(args.cache_dir)

    # 1) yfinance fetch
    df = fetch_yfinance(ticker=ticker, start=str(args.start), dq_flags=dq_flags, dq_notes=dq_notes)

    data_source = "yfinance_yahoo_or_twse_fallback"
    used_fallback = False

    # if yfinance empty, fallback to TWSE recent
    if df is None or len(df) == 0:
        used_fallback = True
        dq_flags.append("DATA_SOURCE_TWSE_FALLBACK")
        dq_notes.append(f"Used TWSE fallback (recent-only, months_back={args.twse_months_back}).")
        df = fetch_twse_recent_0050(months_back=int(args.twse_months_back), dq_flags=dq_flags, dq_notes=dq_notes)

    if df is None or len(df) == 0:
        print("ERROR: no data from yfinance and TWSE fallback.", file=sys.stderr)
        # still write minimal outputs for audit
        stats_path = os.path.join(args.cache_dir, "stats_latest.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(
                {"meta": {"run_ts_utc": utc_now_iso_z(), "module": "tw0050_bb", "ticker": ticker},
                 "dq": {"flags": dq_flags, "notes": dq_notes}},
                f, ensure_ascii=False, indent=2
            )
        return 1

    # normalize dataframe
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # choose price used
    if price_col_req in df.columns and df[price_col_req].notna().any():
        price_used = df[price_col_req].astype(float).copy()
        price_col_used = price_col_req
    else:
        price_used = df["adjclose"].astype(float).copy() if "adjclose" in df.columns else df["close"].astype(float).copy()
        price_col_used = "adjclose" if "adjclose" in df.columns else "close"
        if price_col_used != price_col_req:
            dq_flags.append("PRICE_COL_FALLBACK")
            dq_notes.append(f"requested={price_col_req} not usable; used={price_col_used}.")

    # BB
    w = int(args.bb_window)
    k = float(args.bb_k)
    ma, sd, upper, lower = compute_bb(price_used, window=w, k=k)

    last_idx = len(df) - 1
    last_date = df.loc[last_idx, "date"].strftime("%Y-%m-%d")

    # latest snapshot (require BB ready)
    latest_ma = ma.iloc[last_idx]
    latest_sd = sd.iloc[last_idx]
    latest_upper = upper.iloc[last_idx]
    latest_lower = lower.iloc[last_idx]
    latest_price = float(price_used.iloc[last_idx])

    bb_z = float((latest_price - latest_ma) / latest_sd) if np.isfinite(latest_sd) and latest_sd > 0 else float("nan")
    bb_pos = float((latest_price - latest_lower) / (latest_upper - latest_lower)) if np.isfinite(latest_upper - latest_lower) and (latest_upper - latest_lower) != 0 else float("nan")

    dist_to_lower_pct = (latest_price / latest_lower - 1.0) * 100.0 if np.isfinite(latest_lower) and latest_lower > 0 else float("nan")
    dist_to_upper_pct = (latest_price / latest_upper - 1.0) * 100.0 if np.isfinite(latest_upper) and latest_upper > 0 else float("nan")

    state = classify_state(bb_z=bb_z, bb_pos=bb_pos)

    # forward_mdd
    prices_np = price_used.to_numpy(dtype=float)
    fwd_days = int(args.fwd_days)
    fwd_arr, fwd_stats = compute_forward_mdd(prices_np, fwd_days=fwd_days)

    # min audit trail
    min_entry_date = None
    min_future_date = None
    min_entry_price = None
    min_future_price = None
    if fwd_stats.n > 0 and fwd_stats.min_entry_idx >= 0 and fwd_stats.min_future_idx >= 0:
        min_entry_date = df.loc[fwd_stats.min_entry_idx, "date"].strftime("%Y-%m-%d")
        min_future_date = df.loc[fwd_stats.min_future_idx, "date"].strftime("%Y-%m-%d")
        min_entry_price = float(prices_np[fwd_stats.min_entry_idx])
        min_future_price = float(prices_np[fwd_stats.min_future_idx])

        # outlier rule (audit only; does not alter distribution)
        thr = float(args.outlier_min_threshold)
        if np.isfinite(fwd_stats.min) and fwd_stats.min < thr:
            dq_flags.append("FWD_MDD_OUTLIER_MIN")
            dq_notes.append(f"forward_mdd min={fwd_stats.min:.4f} < threshold({thr}); audit min_entry_date.")

    # outputs
    run_ts_utc = utc_now_iso_z()
    tz = TZ_LOCAL

    meta = {
        "run_ts_utc": run_ts_utc,
        "module": "tw0050_bb",
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "ticker": ticker,
        "start": str(args.start),
        "fetch_start_effective": str(args.start) if not used_fallback else df["date"].min().strftime("%Y-%m-%d"),
        "rows": int(len(df)),
        "tz": tz,
        "data_source": data_source,
        "bb_window": w,
        "bb_k": k,
        "fwd_days": fwd_days,
        "price_calc": "adjclose" if price_col_used == "adjclose" else "close",
        "price_col_requested": price_col_req,
        "price_col_used": price_col_used,
        "last_date": last_date,
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

    fwd_out = {
        "definition": "min(price[t+1..t+20]/price[t]-1), level-price based",
        "n": int(fwd_stats.n),
        "p50": _nan_to_none(float(fwd_stats.p50)),
        "p25": _nan_to_none(float(fwd_stats.p25)),
        "p10": _nan_to_none(float(fwd_stats.p10)),
        "p05": _nan_to_none(float(fwd_stats.p05)),
        "min": _nan_to_none(float(fwd_stats.min)),
        "min_entry_date": min_entry_date,
        "min_entry_price": _nan_to_none(min_entry_price) if min_entry_price is not None else None,
        "min_future_date": min_future_date,
        "min_future_price": _nan_to_none(min_future_price) if min_future_price is not None else None,
    }

    stats = {
        "meta": meta,
        "latest": latest,
        "forward_mdd": fwd_out,
        "dq": {"flags": dq_flags, "notes": dq_notes},
    }

    # write stats_latest.json
    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, sort_keys=True)

    # write data.csv (minimal audit table)
    out_df = df.copy()
    out_df["date"] = out_df["date"].dt.strftime("%Y-%m-%d")
    out_csv = _df_to_csv_min(out_df)
    out_csv_path = os.path.join(args.cache_dir, "data.csv")
    out_csv.to_csv(out_csv_path, index=False)

    # write history_lite.json (minimal)
    hist_path = os.path.join(args.cache_dir, "history_lite.json")
    hist = load_history_lite(hist_path)
    day_key = _local_day_key(datetime.now(timezone.utc))
    upsert_history_row(hist, day_key=day_key, latest=latest, meta=meta)
    save_history_lite(hist_path, hist)

    print(f"[OK] wrote: {stats_path}")
    print(f"[OK] wrote: {out_csv_path}")
    print(f"[OK] wrote: {hist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())