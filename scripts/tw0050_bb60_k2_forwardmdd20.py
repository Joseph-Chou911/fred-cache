# scripts/tw0050_bb60_k2_forwardmdd20.py
# -*- coding: utf-8 -*-
"""
Compute 0050 BB(60,2) + forward_mdd(20D) stats and write to cache_dir/stats_latest.json.

Key features (audit-friendly):
- Uses yfinance as primary source; if empty, tries a TWSE fallback for recent data only.
- Computes BB( window, k ) on price_used (adjclose preferred; falls back to close).
- Computes forward_mdd distribution and records the min outlier entry/future details.
- Adds dq.flags + dq.notes when forward_mdd min is suspiciously extreme.

Designed for CI (GitHub Actions) and local runs.

Example:
  python scripts/tw0050_bb60_k2_forwardmdd20.py --cache_dir tw0050_bb_cache
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# yfinance is expected to be installed in your CI environment.
import yfinance as yf  # type: ignore

try:
    import requests  # optional; used for TWSE fallback
except Exception:
    requests = None  # type: ignore


DEFAULT_TZ = "Asia/Taipei"


@dataclass
class DQ:
    flags: List[str]
    notes: List[str]

    def add(self, flag: str, note: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)
        if note not in self.notes:
            self.notes.append(note)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _to_float(x) -> Optional[float]:
    """Convert common numeric-ish values to float; return None for invalid."""
    if x is None:
        return None
    if isinstance(x, (float, int, np.floating, np.integer)):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "" or s.upper() in {"N/A", "NA", "NULL", "NONE"}:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def normalize_yf_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize yfinance download output to columns: close, adjclose, volume.
    Index -> 'date' as datetime.date.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume"])

    out = df.copy()

    # yfinance uses 'Adj Close'
    cols = {c.lower().replace(" ", ""): c for c in out.columns}
    # Required: Close
    close_col = cols.get("close")
    adj_col = cols.get("adjclose") or cols.get("adjclose")  # just in case
    vol_col = cols.get("volume")

    # Build normalized frame
    norm = pd.DataFrame(index=out.index)
    if close_col is not None:
        norm["close"] = out[close_col]
    else:
        # If missing, attempt 'Close' exact
        if "Close" in out.columns:
            norm["close"] = out["Close"]
        else:
            norm["close"] = np.nan

    if "Adj Close" in out.columns:
        norm["adjclose"] = out["Adj Close"]
    elif adj_col is not None and adj_col in out.columns:
        norm["adjclose"] = out[adj_col]
    else:
        norm["adjclose"] = np.nan

    if vol_col is not None:
        norm["volume"] = out[vol_col]
    else:
        if "Volume" in out.columns:
            norm["volume"] = out["Volume"]
        else:
            norm["volume"] = np.nan

    # Index handling: convert to date
    norm = norm.reset_index()
    # yfinance index name can be "Date" or "Datetime"
    if "Date" in norm.columns:
        norm.rename(columns={"Date": "date"}, inplace=True)
    elif "Datetime" in norm.columns:
        norm.rename(columns={"Datetime": "date"}, inplace=True)
    elif "index" in norm.columns:
        norm.rename(columns={"index": "date"}, inplace=True)

    norm["date"] = pd.to_datetime(norm["date"]).dt.date
    norm = norm.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return norm[["date", "close", "adjclose", "volume"]]


def fetch_yfinance(
    ticker: str,
    start: str,
    end: Optional[str],
    dq: DQ,
) -> pd.DataFrame:
    """
    Fetch daily OHLCV from yfinance and return normalized df.
    """
    try:
        df = yf.download(
            tickers=ticker,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=True,
        )
        ndf = normalize_yf_df(df)
        if ndf.empty:
            dq.add("YFINANCE_EMPTY", f"Empty data from yfinance for ticker={ticker}.")
        return ndf
    except Exception as e:
        dq.add("YFINANCE_ERROR", f"yfinance fetch failed: {type(e).__name__}: {e}")
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume"])


def twse_fallback_recent(
    ticker_numeric: str,
    months_back: int,
    dq: DQ,
) -> pd.DataFrame:
    """
    Very lightweight TWSE fallback:
    - Pulls recent monthly data via TWSE JSON endpoint, concatenates.
    - Returns normalized frame with close + volume; adjclose set to close.

    Note: This fallback is intentionally 'recent-only' to avoid heavy looping.
    """
    if requests is None:
        dq.add("TWSE_FALLBACK_UNAVAILABLE", "requests not available; cannot use TWSE fallback.")
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume"])

    # TWSE endpoint for ETF/stock daily: STOCK_DAY (works for listed equities/ETFs)
    # Example:
    # https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20240201&stockNo=0050
    base = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

    def month_iter(end_dt: date, m_back: int) -> List[date]:
        ds = []
        y, m = end_dt.year, end_dt.month
        for i in range(m_back + 1):
            mm = m - i
            yy = y
            while mm <= 0:
                mm += 12
                yy -= 1
            ds.append(date(yy, mm, 1))
        return ds

    end_dt = date.today()
    months = month_iter(end_dt, months_back)

    rows: List[Tuple[date, float, float]] = []  # date, close, volume
    for d0 in months:
        ymd = f"{d0.year:04d}{d0.month:02d}{d0.day:02d}"
        params = {"response": "json", "date": ymd, "stockNo": ticker_numeric}
        try:
            r = requests.get(base, params=params, timeout=15)
            if r.status_code != 200:
                continue
            j = r.json()
            if j.get("stat") != "OK":
                continue
            data = j.get("data") or []
            # data columns: 日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數
            for it in data:
                if not it or len(it) < 7:
                    continue
                # date is ROC string like "115/02/11" or "2014/02/05" depending; commonly ROC for TWSE
                sdate = str(it[0]).strip()
                # parse ROC yy/mm/dd
                dtv = None
                try:
                    parts = sdate.split("/")
                    if len(parts) == 3:
                        yy = int(parts[0])
                        mm = int(parts[1])
                        dd = int(parts[2])
                        if yy < 1911:  # ROC year
                            yy = yy + 1911
                        dtv = date(yy, mm, dd)
                except Exception:
                    dtv = None
                if dtv is None:
                    continue

                close = _to_float(str(it[6]).replace(",", ""))
                vol = _to_float(str(it[1]).replace(",", ""))
                if close is None:
                    continue
                if vol is None:
                    vol = float("nan")
                rows.append((dtv, float(close), float(vol)))
        except Exception:
            continue

    if not rows:
        dq.add("TWSE_FALLBACK_EMPTY", "TWSE fallback returned no rows.")
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume"])

    df = pd.DataFrame(rows, columns=["date", "close", "volume"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df["adjclose"] = df["close"]
    dq.add("DATA_SOURCE_TWSE_FALLBACK", f"Used TWSE fallback (recent-only, months_back={months_back}).")
    return df[["date", "close", "adjclose", "volume"]]


def load_cache_prices(cache_dir: str) -> pd.DataFrame:
    p = os.path.join(cache_dir, "prices.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume", "source"])
    df = pd.read_csv(p)
    if df.empty:
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume", "source"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for c in ["close", "adjclose", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "source" not in df.columns:
        df["source"] = "cache"
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return df[["date", "close", "adjclose", "volume", "source"]]


def save_cache_prices(cache_dir: str, df: pd.DataFrame) -> None:
    p = os.path.join(cache_dir, "prices.csv")
    out = df.copy()
    out["date"] = out["date"].astype(str)
    out.to_csv(p, index=False)


def merge_prices(cache_df: pd.DataFrame, new_df: pd.DataFrame, source: str) -> pd.DataFrame:
    if new_df.empty and cache_df.empty:
        return pd.DataFrame(columns=["date", "close", "adjclose", "volume", "source"])

    ndf = new_df.copy()
    if not ndf.empty:
        ndf["source"] = source

    df = pd.concat([cache_df, ndf], ignore_index=True)
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    # Keep only needed cols
    for c in ["close", "adjclose", "volume"]:
        if c not in df.columns:
            df[c] = np.nan
    if "source" not in df.columns:
        df["source"] = "merged"
    return df[["date", "close", "adjclose", "volume", "source"]]


def compute_bb(price: pd.Series, window: int, k: float) -> pd.DataFrame:
    ma = price.rolling(window=window).mean()
    sd = price.rolling(window=window).std(ddof=1)
    upper = ma + k * sd
    lower = ma - k * sd
    z = (price - ma) / sd
    pos = (price - lower) / (upper - lower)
    return pd.DataFrame(
        {
            "bb_ma": ma,
            "bb_sd": sd,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_z": z,
            "bb_pos": pos,
        }
    )


def classify_state(bb_z: float) -> str:
    if bb_z >= 2.0:
        return "EXTREME_UPPER_BAND"
    if bb_z >= 1.5:
        return "NEAR_UPPER_BAND"
    if bb_z <= -2.0:
        return "EXTREME_LOWER_BAND"
    if bb_z <= -1.5:
        return "NEAR_LOWER_BAND"
    return "IN_BAND"


def compute_forward_mdd(price: pd.Series, fwd_days: int) -> Tuple[pd.Series, Dict[str, object]]:
    """
    forward_mdd[t] = min(price[t+1..t+fwd_days]/price[t]-1)
    Returns:
      - series of forward_mdd aligned with price index (NaN where insufficient future)
      - dict with min entry/future info (dates/prices) for the global minimum
    """
    idx = price.index
    p = price.to_numpy(dtype=float)
    n = len(p)
    out = np.full(shape=(n,), fill_value=np.nan, dtype=float)

    min_val = float("inf")
    min_i = None
    min_j = None

    for i in range(n):
        j1 = i + 1
        j2 = i + fwd_days
        if j2 >= n:
            break
        p0 = p[i]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        window = p[j1 : j2 + 1]
        if window.size == 0:
            continue
        wmin = np.nanmin(window)
        if not np.isfinite(wmin):
            continue
        v = (wmin / p0) - 1.0
        out[i] = v
        if v < min_val:
            min_val = v
            min_i = i
            # find the first occurrence of that min within the future window
            # (ties: earliest)
            rel = int(np.nanargmin(window))
            min_j = j1 + rel

    info: Dict[str, object] = {}
    if min_i is not None and min_j is not None and np.isfinite(min_val):
        info = {
            "min": float(min_val),
            "min_entry_date": str(idx[min_i]),
            "min_entry_price": float(p[min_i]),
            "min_future_date": str(idx[min_j]),
            "min_future_price": float(p[min_j]),
        }

    return pd.Series(out, index=idx, name="forward_mdd"), info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="0050.TW")
    ap.add_argument("--start", default="2003-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)
    ap.add_argument("--fwd_days", type=int, default=20)

    ap.add_argument("--price_col_requested", default="adjclose", choices=["adjclose", "close"])
    ap.add_argument("--twse_fallback_months_back", type=int, default=6)
    ap.add_argument("--fwd_mdd_outlier_threshold", type=float, default=-0.4)

    args = ap.parse_args()

    dq = DQ(flags=[], notes=[])
    ensure_dir(args.cache_dir)

    # Load cache
    cache_df = load_cache_prices(args.cache_dir)

    # Decide incremental fetch start: last_date - buffer
    buffer_days = max(10, args.bb_window + args.fwd_days + 5)
    inc_start = args.start
    if not cache_df.empty:
        last_cached = cache_df["date"].max()
        if isinstance(last_cached, date):
            inc_start = str(last_cached - timedelta(days=buffer_days))

    # Fetch yfinance incremental (or full if no cache)
    yf_df = fetch_yfinance(args.ticker, start=inc_start, end=args.end, dq=dq)

    merged = merge_prices(cache_df, yf_df, source="yfinance")
    data_source = "yfinance"
    if yf_df.empty:
        # Use TWSE fallback for recent prices; merge to keep history if any
        ticker_num = args.ticker.split(".")[0]
        tw_df = twse_fallback_recent(ticker_num, months_back=args.twse_fallback_months_back, dq=dq)
        merged = merge_prices(cache_df, tw_df, source="twse_fallback")
        data_source = "twse_fallback" if not tw_df.empty else "none"

    if merged.empty:
        raise SystemExit("ERROR: No price data available from yfinance nor fallback.")

    # Persist merged cache
    save_cache_prices(args.cache_dir, merged)

    # Choose price column
    price_col_used = args.price_col_requested
    if price_col_used == "adjclose":
        # if adjclose all NaN, fall back to close
        if merged["adjclose"].isna().all():
            price_col_used = "close"
            dq.add("ADJCLOSE_MISSING", "adjclose missing; using close instead.")
    if price_col_used == "close" and merged["close"].isna().all():
        raise SystemExit("ERROR: close is missing; cannot compute indicators.")

    # Work frame
    df = merged.copy()
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df["price_used"] = df[price_col_used].astype(float)

    # Remove rows with invalid price_used
    df = df[np.isfinite(df["price_used"]) & (df["price_used"] > 0)].copy()
    if len(df) < (args.bb_window + args.fwd_days + 10):
        dq.add(
            "INSUFFICIENT_ROWS",
            f"rows={len(df)} < bb_window+fwd_days+10 ({args.bb_window + args.fwd_days + 10}).",
        )

    # Compute BB
    bb = compute_bb(df["price_used"], window=args.bb_window, k=args.bb_k)
    df = pd.concat([df.reset_index(drop=True), bb.reset_index(drop=True)], axis=1)

    # Latest row that has BB fully defined (bb_ma not NaN)
    df_valid = df.dropna(subset=["bb_ma", "bb_sd", "bb_upper", "bb_lower", "bb_z", "bb_pos"])
    if df_valid.empty:
        raise SystemExit("ERROR: BB could not be computed (not enough non-NaN rows).")

    last_row = df_valid.iloc[-1]
    last_date = str(last_row["date"])

    # Distances (percent of price_used)
    price_used = float(last_row["price_used"])
    dist_to_lower_pct = (float(last_row["price_used"] - last_row["bb_lower"]) / price_used) * 100.0
    dist_to_upper_pct = (float(last_row["bb_upper"] - last_row["price_used"]) / price_used) * 100.0

    bb_z = float(last_row["bb_z"])
    state = classify_state(bb_z)

    # forward_mdd over the entire (valid) series (use full df with price_used)
    # Use index as date strings for audit clarity.
    s_price = pd.Series(df["price_used"].to_numpy(dtype=float), index=df["date"].astype(str).tolist(), name="price_used")
    fwd, min_info = compute_forward_mdd(s_price, fwd_days=args.fwd_days)
    fwd_clean = fwd.dropna()
    if fwd_clean.empty:
        dq.add("FWD_MDD_EMPTY", "forward_mdd series empty (insufficient future window).")

    # Distribution stats
    def q(x: np.ndarray, p: float) -> float:
        return float(np.quantile(x, p))

    fwd_arr = fwd_clean.to_numpy(dtype=float)
    fwd_stats: Dict[str, object] = {
        "definition": f"min(price[t+1..t+{args.fwd_days}]/price[t]-1), level-price based",
        "n": int(fwd_arr.size),
    }
    if fwd_arr.size > 0:
        fwd_stats.update(
            {
                "p50": q(fwd_arr, 0.50),
                "p25": q(fwd_arr, 0.25),
                "p10": q(fwd_arr, 0.10),
                "p05": q(fwd_arr, 0.05),
                "min": float(np.min(fwd_arr)),
            }
        )
        # Attach min entry/future details if computed
        if min_info:
            fwd_stats.update(min_info)

        # Outlier rule
        if float(fwd_stats["min"]) < float(args.fwd_mdd_outlier_threshold):
            dq.add(
                "FWD_MDD_OUTLIER_MIN",
                f"forward_mdd min={float(fwd_stats['min']):.4f} < threshold({args.fwd_mdd_outlier_threshold}); audit min_entry_date.",
            )

    # Latest snapshot object
    latest = {
        "date": last_date,
        "close": float(last_row["close"]) if np.isfinite(last_row["close"]) else float("nan"),
        "adjclose": float(last_row["adjclose"]) if np.isfinite(last_row["adjclose"]) else float("nan"),
        "price_used": price_used,
        "bb_ma": float(last_row["bb_ma"]),
        "bb_sd": float(last_row["bb_sd"]),
        "bb_upper": float(last_row["bb_upper"]),
        "bb_lower": float(last_row["bb_lower"]),
        "bb_z": bb_z,
        "bb_pos": float(last_row["bb_pos"]),
        "dist_to_lower_pct": float(dist_to_lower_pct),
        "dist_to_upper_pct": float(dist_to_upper_pct),
        "state": state,
    }

    # Meta
    meta = {
        "run_ts_utc": utc_now_iso(),
        "module": "tw0050_bb",
        "tz": DEFAULT_TZ,
        "ticker": args.ticker,
        "start": args.start,
        "fetch_start_effective": inc_start,
        "last_date": last_date,
        "rows": int(len(df)),
        "bb_window": int(args.bb_window),
        "bb_k": float(args.bb_k),
        "fwd_days": int(args.fwd_days),
        "price_calc": args.price_col_requested,
        "price_col_requested": args.price_col_requested,
        "price_col_used": price_col_used,
        "data_source": "yfinance_yahoo_or_twse_fallback",
        "data_source_detail": data_source,
    }

    out = {
        "dq": {"flags": dq.flags, "notes": dq.notes},
        "forward_mdd": fwd_stats,
        "latest": latest,
        "meta": meta,
    }

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())