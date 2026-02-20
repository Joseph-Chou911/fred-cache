#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VT BB(60,2) + forward_mdd(20D) monitor (independent module)

Outputs (deterministic, audit-first):
- <cache_dir>/latest.json
- <cache_dir>/history.json
- <cache_dir>/report.md

Key design choices:
- BB computed on log(adj_close) by default (stable vs splits/dividends adjustments).
- forward_mdd(20D) computed on adj_close series (linear domain).
- FX (USD/TWD) is OPTIONAL and audit-strict:
  * only uses FX rate if a SAME-DATE match is found in fx_history.json
  * otherwise FX fields are NA (no "nearest" or "latest" guessing)
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
import pytz

try:
    import yfinance as yf
except Exception as e:
    raise SystemExit(f"FATAL: yfinance import failed: {e}")


# ----------------------------
# Utilities (audit-friendly)
# ----------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "" or s.upper() in {"NA", "N/A", "NULL", "NONE"}:
            return None
        try:
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None
    return None


def _read_json(path: str) -> Optional[Any]:
    if not path:
        return None
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ----------------------------
# FX parsing (schema-flexible, strict date-match)
# ----------------------------
@dataclass
class FxSeries:
    by_date: Dict[str, float]        # YYYY-MM-DD -> rate
    detected_date_key: Optional[str]
    detected_rate_key: Optional[str]
    parse_status: str


def _extract_records(obj: Any) -> Optional[List[Dict[str, Any]]]:
    """Try to find list[dict] records from various common containers."""
    if obj is None:
        return None
    if isinstance(obj, list) and (len(obj) == 0 or isinstance(obj[0], dict)):
        return obj  # type: ignore
    if isinstance(obj, dict):
        # common containers
        for k in ["history", "data", "items", "rows", "records", "series"]:
            v = obj.get(k)
            if isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict)):
                return v  # type: ignore
        # sometimes nested one more layer
        for k, v in obj.items():
            if isinstance(v, dict):
                for kk in ["history", "data", "items", "rows", "records"]:
                    vv = v.get(kk)
                    if isinstance(vv, list) and (len(vv) == 0 or isinstance(vv[0], dict)):
                        return vv  # type: ignore
    return None


def _pick_keys(records: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Heuristic to pick date and rate keys.
    We prefer:
      date keys: date, day, ymd, day_key, UsedDate
      rate keys: usdtwd, usd_twd, rate, close, value
    """
    if not records:
        return None, None, "EMPTY_RECORDS"

    date_candidates = ["date", "day", "ymd", "day_key", "UsedDate", "used_date", "d"]
    rate_candidates = ["usdtwd", "usd_twd", "USD_TWD", "USDTWD", "rate", "close", "value", "price"]

    # find date key
    date_key = None
    for dk in date_candidates:
        if dk in records[0]:
            date_key = dk
            break
    if date_key is None:
        # scan keys for something date-like
        for k in records[0].keys():
            lk = k.lower()
            if "date" in lk or "ymd" in lk or "day" == lk or "useddate" in lk:
                date_key = k
                break

    # find rate key
    rate_key = None
    for rk in rate_candidates:
        if rk in records[0]:
            rate_key = rk
            break
    if rate_key is None:
        # scan for usdtwd-like key
        for k in records[0].keys():
            lk = k.lower()
            if "usdtwd" in lk or "usd_twd" in lk:
                rate_key = k
                break

    status = "OK" if (date_key and rate_key) else "KEYS_NOT_FOUND"
    return date_key, rate_key, status


def load_fx_history_strict(fx_history_path: str) -> FxSeries:
    """
    Load fx_history.json and build date->rate map.
    Strict: only exact YYYY-MM-DD match will be used later.
    """
    obj = _read_json(fx_history_path)
    records = _extract_records(obj)
    if records is None:
        return FxSeries(by_date={}, detected_date_key=None, detected_rate_key=None, parse_status="NO_RECORDS")

    date_key, rate_key, status = _pick_keys(records)
    if status != "OK":
        return FxSeries(by_date={}, detected_date_key=date_key, detected_rate_key=rate_key, parse_status=status)

    out: Dict[str, float] = {}
    for r in records:
        d_raw = r.get(date_key)  # type: ignore[arg-type]
        v_raw = r.get(rate_key)  # type: ignore[arg-type]
        if d_raw is None:
            continue

        d = str(d_raw).strip()
        # normalize: allow YYYYMMDD -> YYYY-MM-DD
        if len(d) == 8 and d.isdigit():
            d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"

        v = _safe_float(v_raw)
        if v is None:
            continue
        # sanity check: USD/TWD often in ~10-50
        if not (5.0 <= v <= 100.0):
            # ignore obviously wrong values
            continue
        if len(d) == 10 and d[4] == "-" and d[7] == "-":
            out[d] = v

    return FxSeries(by_date=out, detected_date_key=date_key, detected_rate_key=rate_key, parse_status="OK")


# ----------------------------
# VT data fetch
# ----------------------------
def fetch_daily_ohlc(ticker: str, retries: int = 3) -> pd.DataFrame:
    last_err = None
    for i in range(retries):
        try:
            df = yf.download(
                tickers=ticker,
                period="max",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if df is None or df.empty:
                raise RuntimeError("empty dataframe from yfinance")
            # normalize columns
            # yfinance may return multiindex columns; flatten if needed
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            # must have Close; Adj Close may be missing sometimes
            if "Close" not in df.columns:
                raise RuntimeError(f"missing Close column; columns={list(df.columns)}")
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            last_err = e
    raise RuntimeError(f"yfinance fetch failed after {retries} retries: {last_err}")


# ----------------------------
# Indicators
# ----------------------------
@dataclass
class BbResult:
    z: float
    ma: float
    sd: float
    upper: float
    lower: float
    pos: float
    dist_to_lower: float
    dist_to_upper: float


def compute_bb_log(price: pd.Series, window: int, k: float) -> pd.DataFrame:
    """
    price: linear domain (e.g., adj_close)
    returns dataframe with ma, sd, upper, lower, z, pos_in_band in LOG domain, but bands in LOG too.
    """
    logp = np.log(price.astype(float))
    ma = logp.rolling(window=window, min_periods=window).mean()
    sd = logp.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    z = (logp - ma) / sd.replace(0.0, np.nan)

    # position in band (log domain)
    denom = (upper - lower).replace(0.0, np.nan)
    pos = (logp - lower) / denom
    pos = pos.clip(lower=0.0, upper=1.0)

    out = pd.DataFrame(
        {
            "logp": logp,
            "ma": ma,
            "sd": sd,
            "upper": upper,
            "lower": lower,
            "z": z,
            "pos": pos,
        }
    )
    return out


def bucket_from_z(z: float) -> str:
    if z <= -2.0:
        return "BELOW_LOWER_BAND"
    if z <= -1.5:
        return "NEAR_LOWER_BAND"
    if z >= 2.0:
        return "ABOVE_UPPER_BAND"
    if z >= 1.5:
        return "NEAR_UPPER_BAND"
    return "MID_BAND"


def compute_forward_mdd(prices: np.ndarray, forward_days: int) -> np.ndarray:
    """
    forward_mdd[t] = (min(prices[t+1:t+forward_days]) / prices[t]) - 1
    undefined for tail where future window missing -> nan
    """
    n = len(prices)
    out = np.full(n, np.nan, dtype=float)
    for t in range(0, n - forward_days):
        p0 = prices[t]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        future_min = np.min(prices[t + 1 : t + forward_days + 1])
        if not np.isfinite(future_min) or future_min <= 0:
            continue
        out[t] = (future_min / p0) - 1.0
    return out


def summarize_mdd(mdd: np.ndarray) -> Dict[str, Any]:
    x = mdd[np.isfinite(mdd)]
    n = int(x.shape[0])
    if n == 0:
        return {"n": 0, "p50": None, "p10": None, "min": None, "conf": "NA"}
    p50 = float(np.percentile(x, 50))
    p10 = float(np.percentile(x, 10))
    mn = float(np.min(x))

    if n >= 120:
        conf = "HIGH"
    elif n >= 60:
        conf = "MED"
    elif n >= 20:
        conf = "LOW"
    else:
        conf = "NA"
    return {"n": n, "p50": p50, "p10": p10, "min": mn, "conf": conf}


# ----------------------------
# History maintenance
# ----------------------------
def upsert_history(history_path: str, rows: List[Dict[str, Any]], key: str = "date", max_rows: int = 2500) -> Dict[str, Any]:
    """
    history.json schema:
      { "schema_version": "...", "items": [ {...}, ... ] }
    De-dup by date, keep sorted ascending, keep last max_rows.
    """
    prev = _read_json(history_path)
    items: List[Dict[str, Any]] = []
    if isinstance(prev, dict) and isinstance(prev.get("items"), list):
        for it in prev["items"]:
            if isinstance(it, dict) and key in it:
                items.append(it)

    # index existing
    idx: Dict[str, Dict[str, Any]] = {str(it[key]): it for it in items if it.get(key) is not None}

    for r in rows:
        dk = str(r.get(key))
        idx[dk] = r

    # sort by date string
    all_items = list(idx.values())
    all_items.sort(key=lambda x: str(x.get(key)))
    if max_rows and len(all_items) > max_rows:
        all_items = all_items[-max_rows:]

    return {"schema_version": "vt_bb_cache.v1", "items": all_items}


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="VT")
    ap.add_argument("--cache_dir", default="vt_bb_cache")
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--forward_days", type=int, default=20)
    ap.add_argument("--fx_latest", default="fx_cache/latest.json")
    ap.add_argument("--fx_history", default="fx_cache/history.json")
    ap.add_argument("--max_history_rows", type=int, default=2500)
    args = ap.parse_args()

    generated_at_utc = utc_now_iso()

    df = fetch_daily_ohlc(args.ticker)
    # prefer Adj Close, fallback to Close if missing
    if "Adj Close" in df.columns and df["Adj Close"].notna().any():
        base = df["Adj Close"].astype(float).copy()
        price_mode = "adj_close"
    else:
        base = df["Close"].astype(float).copy()
        price_mode = "close_only"

    close = df["Close"].astype(float).copy()
    # remove non-positive
    base = base.replace([np.inf, -np.inf], np.nan)
    base = base.where(base > 0)

    bb = compute_bb_log(base, window=args.window, k=args.k)

    # last valid row
    last_idx = bb.dropna().index.max()
    if pd.isna(last_idx):
        raise SystemExit("FATAL: insufficient data to compute BB (need >= window valid points).")
    last_date = pd.Timestamp(last_idx).date().isoformat()

    last_row = bb.loc[last_idx]
    last_price = float(base.loc[last_idx])
    last_close = float(close.loc[last_idx]) if pd.notna(close.loc[last_idx]) else None

    z = float(last_row["z"])
    bucket = bucket_from_z(z)

    # dist in linear domain using bands in log domain -> exp back
    upper_lin = float(np.exp(last_row["upper"]))
    lower_lin = float(np.exp(last_row["lower"]))
    dist_to_lower = (last_price - lower_lin) / last_price if last_price else None
    dist_to_upper = (upper_lin - last_price) / last_price if last_price else None
    pos_in_band = float(last_row["pos"])

    # forward mdd on linear base series
    prices = base.to_numpy(dtype=float)
    fwd_mdd = compute_forward_mdd(prices, forward_days=args.forward_days)

    # bucketize historical days
    buckets = bb["z"].apply(lambda v: bucket_from_z(float(v)) if pd.notna(v) else None)
    mask = (buckets == bucket) & np.isfinite(fwd_mdd)
    mdd_stats = summarize_mdd(fwd_mdd[mask.to_numpy()])

    # FX strict date-match
    fx_series = load_fx_history_strict(args.fx_history)
    fx_rate = fx_series.by_date.get(last_date) if fx_series.parse_status == "OK" else None
    fx_used = "HISTORY_DATE_MATCH" if fx_rate is not None else "NA"

    price_twd = (last_price * fx_rate) if fx_rate is not None else None
    close_twd = (last_close * fx_rate) if (fx_rate is not None and last_close is not None) else None

    latest = {
        "schema_version": "vt_bb_cache.v1",
        "module": "vt_bb_cache",
        "ticker": args.ticker,
        "generated_at_utc": generated_at_utc,
        "price_mode": price_mode,
        "data_date": last_date,
        "window": args.window,
        "k": args.k,
        "forward_days": args.forward_days,
        "price_usd": last_price,
        "close_usd": last_close,
        "bb": {
            "z": z,
            "pos_in_band": pos_in_band,
            "upper_usd": upper_lin,
            "lower_usd": lower_lin,
            "dist_to_lower": dist_to_lower,
            "dist_to_upper": dist_to_upper,
            "bucket": bucket,
        },
        "forward_mdd20": mdd_stats,
        "fx_usdtwd": {
            "rate": fx_rate,
            "used_policy": fx_used,
            "parse_status": fx_series.parse_status,
            "detected_date_key": fx_series.detected_date_key,
            "detected_rate_key": fx_series.detected_rate_key,
        },
        "derived_twd": {
            "price_twd": price_twd,
            "close_twd": close_twd,
        },
        "notes": [
            "BB computed on log(price_usd) where price_usd is adj_close when available.",
            "forward_mdd20 computed on linear price_usd (same series as BB).",
            "FX is strict: only same-date match from fx_history.json is accepted; otherwise NA.",
        ],
    }

    cache_dir = args.cache_dir
    latest_path = os.path.join(cache_dir, "latest.json")
    history_path = os.path.join(cache_dir, "history.json")
    report_path = os.path.join(cache_dir, "report.md")

    _write_json(latest_path, latest)

    # history row (compact)
    hist_row = {
        "date": last_date,
        "price_usd": last_price,
        "close_usd": last_close,
        "z": z,
        "pos_in_band": pos_in_band,
        "bucket": bucket,
        "p50_mdd20": mdd_stats.get("p50"),
        "p10_mdd20": mdd_stats.get("p10"),
        "min_mdd20": mdd_stats.get("min"),
        "n_mdd20": mdd_stats.get("n"),
        "fx_usdtwd": fx_rate,
        "price_twd": price_twd,
    }

    history_obj = upsert_history(history_path, [hist_row], max_rows=args.max_history_rows)
    _write_json(history_path, history_obj)

    # report.md (human readable)
    # Keep it short and stable; no speculation.
    def fmt_pct(x: Any) -> str:
        v = _safe_float(x)
        if v is None:
            return "NA"
        return f"{v*100:.3f}%"

    def fmt_num(x: Any, nd: int = 4) -> str:
        v = _safe_float(x)
        if v is None:
            return "NA"
        return f"{v:.{nd}f}"

    report = []
    report.append(f"# VT BB Monitor Report (VT + optional USD/TWD)")
    report.append("")
    report.append(f"- report_generated_at_utc: `{generated_at_utc}`")
    report.append(f"- data_date: `{last_date}`")
    report.append(f"- price_mode: `{price_mode}`")
    report.append("")
    report.append("## 15秒摘要")
    report.append(
        f"- **VT** ({last_date} price_usd={fmt_num(last_price, 4)}) → **{bucket}** "
        f"(z={fmt_num(z, 4)}, pos={fmt_num(pos_in_band, 4)}); "
        f"dist_to_lower={fmt_pct(dist_to_lower)}; dist_to_upper={fmt_pct(dist_to_upper)}; "
        f"20D forward_mdd: p50={fmt_pct(mdd_stats.get('p50'))}, p10={fmt_pct(mdd_stats.get('p10'))}, "
        f"min={fmt_pct(mdd_stats.get('min'))} (n={mdd_stats.get('n')}, conf={mdd_stats.get('conf')})"
    )
    report.append("")
    report.append("## FX (USD/TWD)（可選，嚴格同日對齊）")
    report.append(f"- fx_history_parse_status: `{fx_series.parse_status}`")
    report.append(f"- fx_used_policy: `{fx_used}`")
    report.append(f"- fx_rate (for {last_date}): `{fmt_num(fx_rate, 4)}`")
    report.append(f"- derived price_twd: `{fmt_num(price_twd, 2)}`")
    report.append("")
    report.append("## Notes")
    report.append("- forward_mdd20 理論上應永遠 <= 0；若你看到 >0，代表資料對齊或定義出錯。")
    report.append("- 若 FX 無同日資料，TWD 相關欄位會是 NA（不做 nearest / latest 代入）。")
    report.append("")

    _write_text(report_path, "\n".join(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())