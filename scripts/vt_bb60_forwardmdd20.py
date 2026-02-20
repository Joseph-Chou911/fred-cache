#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VT BB(60,2) + forward_mdd(20D) monitor (independent module)

Outputs (deterministic, audit-first):
- <cache_dir>/latest.json
- <cache_dir>/history.json
- <cache_dir>/report.md

Key design choices:
- BB computed on log(adj_close) by default.
- forward_mdd(20D) computed on linear price series (same as BB base series).
- FX (USD/TWD):
  (1) STRICT: only exact SAME-DATE match will populate main fields:
      fx_usdtwd.rate, derived_twd.price_twd, derived_twd.close_twd
  (2) REFERENCE (optional): if strict match missing, compute a *reference* TWD price
      using the most recent available FX date <= vt_date (from history and/or latest),
      and explicitly annotate lag_days and source.
      This reference does NOT replace strict fields.

This prevents "fake precision" while still giving you a usable reference number when FX lags.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date as dt_date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

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
    if isinstance(x, (int, float)):
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
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


def _ymd_to_date(s: str) -> Optional[dt_date]:
    if not s or not isinstance(s, str):
        return None
    t = s.strip()
    if len(t) == 10 and t[4] == "-" and t[7] == "-":
        try:
            y = int(t[0:4]); m = int(t[5:7]); d = int(t[8:10])
            return dt_date(y, m, d)
        except Exception:
            return None
    return None


# ----------------------------
# FX parsing (schema-flexible)
# ----------------------------
@dataclass
class FxSeries:
    by_date: Dict[str, float]        # YYYY-MM-DD -> rate(mid)
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
        for k in ["items", "history", "data", "rows", "records", "series"]:
            v = obj.get(k)
            if isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict)):
                return v  # type: ignore
        for _, v in obj.items():
            if isinstance(v, dict):
                for kk in ["items", "history", "data", "rows", "records"]:
                    vv = v.get(kk)
                    if isinstance(vv, list) and (len(vv) == 0 or isinstance(vv[0], dict)):
                        return vv  # type: ignore
    return None


def _pick_keys(records: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Heuristic to pick date and rate keys.

    Your fx_history schema example:
      items[].date, items[].mid, items[].spot_buy, items[].spot_sell
    """
    if not records:
        return None, None, "EMPTY_RECORDS"

    date_candidates = [
        "date", "data_date", "day", "ymd", "day_key", "UsedDate", "used_date", "d"
    ]
    rate_candidates = [
        # <<< critical fix: include mid/spot_*
        "mid", "spot_buy", "spot_sell",
        # legacy/other possibilities
        "usdtwd", "usd_twd", "USD_TWD", "USDTWD", "rate", "close", "value", "price"
    ]

    date_key = None
    for dk in date_candidates:
        if dk in records[0]:
            date_key = dk
            break
    if date_key is None:
        for k in records[0].keys():
            lk = k.lower()
            if "date" in lk or "ymd" in lk or lk == "day" or "useddate" in lk:
                date_key = k
                break

    rate_key = None
    for rk in rate_candidates:
        if rk in records[0]:
            rate_key = rk
            break
    if rate_key is None:
        for k in records[0].keys():
            lk = k.lower()
            if "mid" == lk or "spot_buy" == lk or "spot_sell" == lk:
                rate_key = k
                break
            if "usdtwd" in lk or "usd_twd" in lk:
                rate_key = k
                break

    status = "OK" if (date_key and rate_key) else "KEYS_NOT_FOUND"
    return date_key, rate_key, status


def load_fx_history(fx_history_path: str) -> FxSeries:
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
        if len(d) == 8 and d.isdigit():
            d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"

        v = _safe_float(v_raw)
        if v is None:
            continue

        # sanity range (very wide but blocks nonsense)
        if not (5.0 <= v <= 100.0):
            continue

        if len(d) == 10 and d[4] == "-" and d[7] == "-":
            out[d] = v

    return FxSeries(by_date=out, detected_date_key=date_key, detected_rate_key=rate_key, parse_status="OK")


def load_fx_latest_mid(fx_latest_path: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Return (data_date, mid, status)
    Expected schema (your latest.json):
      data_date: YYYY-MM-DD
      usd_twd.mid: float
    """
    obj = _read_json(fx_latest_path)
    if not isinstance(obj, dict):
        return None, None, "NO_LATEST"

    d = obj.get("data_date")
    usd = obj.get("usd_twd")
    mid = None
    if isinstance(usd, dict):
        mid = _safe_float(usd.get("mid"))

    d_str = str(d).strip() if d else None
    if d_str and len(d_str) == 8 and d_str.isdigit():
        d_str = f"{d_str[0:4]}-{d_str[4:6]}-{d_str[6:8]}"

    if (not d_str) or (mid is None):
        return d_str, mid, "LATEST_KEYS_MISSING"
    return d_str, mid, "OK"


# ----------------------------
# VT data fetch
# ----------------------------
def fetch_daily_ohlc(ticker: str, retries: int = 3) -> pd.DataFrame:
    last_err = None
    for _ in range(retries):
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
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
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
def compute_bb_log(price: pd.Series, window: int, k: float) -> pd.DataFrame:
    logp = np.log(price.astype(float))
    ma = logp.rolling(window=window, min_periods=window).mean()
    sd = logp.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    z = (logp - ma) / sd.replace(0.0, np.nan)

    denom = (upper - lower).replace(0.0, np.nan)
    pos = (logp - lower) / denom
    pos = pos.clip(lower=0.0, upper=1.0)

    return pd.DataFrame({"logp": logp, "ma": ma, "sd": sd, "upper": upper, "lower": lower, "z": z, "pos": pos})


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
    prev = _read_json(history_path)
    items: List[Dict[str, Any]] = []
    if isinstance(prev, dict) and isinstance(prev.get("items"), list):
        for it in prev["items"]:
            if isinstance(it, dict) and key in it:
                items.append(it)

    idx: Dict[str, Dict[str, Any]] = {str(it[key]): it for it in items if it.get(key) is not None}
    for r in rows:
        dk = str(r.get(key))
        idx[dk] = r

    all_items = list(idx.values())
    all_items.sort(key=lambda x: str(x.get(key)))

    if max_rows and len(all_items) > max_rows:
        all_items = all_items[-max_rows:]

    return {"schema_version": "vt_bb_cache.v1", "items": all_items}


# ----------------------------
# FX reference selection
# ----------------------------
def pick_fx_reference(
    vt_date_str: str,
    fx_hist: FxSeries,
    fx_latest_path: str,
) -> Dict[str, Any]:
    """
    Returns a dict:
      {
        "ref_rate": float|None,
        "ref_date": "YYYY-MM-DD"|None,
        "ref_source": "HISTORY"|"LATEST"|None,
        "lag_days": int|None,
        "status": "OK"|"NO_REF"|"TOO_STALE"|...
        "stale_threshold_days": int
      }
    Policy: choose the most recent FX date <= vt_date from:
      - history by_date
      - latest.json (data_date, mid) if <= vt_date
    """
    stale_threshold_days = 30  # audit guard; still returns info even if too stale but flags it
    vt_d = _ymd_to_date(vt_date_str)
    if vt_d is None:
        return {
            "ref_rate": None, "ref_date": None, "ref_source": None,
            "lag_days": None, "status": "VT_DATE_PARSE_FAIL",
            "stale_threshold_days": stale_threshold_days
        }

    # Candidate from history: max date <= vt_date
    hist_best_date = None
    hist_best_rate = None
    if fx_hist.parse_status == "OK" and fx_hist.by_date:
        # iterate keys; keep <= vt_date
        for d_str, rate in fx_hist.by_date.items():
            d = _ymd_to_date(d_str)
            if d is None:
                continue
            if d <= vt_d and (hist_best_date is None or d > hist_best_date):
                hist_best_date = d
                hist_best_rate = rate

    # Candidate from latest
    latest_date_str, latest_mid, latest_status = load_fx_latest_mid(fx_latest_path)
    latest_d = _ymd_to_date(latest_date_str) if latest_date_str else None
    latest_ok = (latest_status == "OK" and latest_d is not None and latest_mid is not None and latest_d <= vt_d)

    # Choose most recent
    ref_source = None
    ref_date = None
    ref_rate = None

    if hist_best_date is not None:
        ref_source = "HISTORY"
        ref_date = hist_best_date
        ref_rate = hist_best_rate

    if latest_ok:
        if ref_date is None or latest_d > ref_date:
            ref_source = "LATEST"
            ref_date = latest_d
            ref_rate = latest_mid

    if ref_date is None or ref_rate is None:
        return {
            "ref_rate": None, "ref_date": None, "ref_source": None,
            "lag_days": None, "status": "NO_REF",
            "stale_threshold_days": stale_threshold_days,
            "latest_status": latest_status,
            "history_status": fx_hist.parse_status,
        }

    lag_days = (vt_d - ref_date).days
    status = "OK"
    if lag_days > stale_threshold_days:
        status = "TOO_STALE"

    return {
        "ref_rate": float(ref_rate),
        "ref_date": ref_date.isoformat(),
        "ref_source": ref_source,
        "lag_days": int(lag_days),
        "status": status,
        "stale_threshold_days": stale_threshold_days,
        "latest_status": latest_status,
        "history_status": fx_hist.parse_status,
    }


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

    # prefer Adj Close, fallback to Close
    if "Adj Close" in df.columns and df["Adj Close"].notna().any():
        base = df["Adj Close"].astype(float).copy()
        price_mode = "adj_close"
    else:
        base = df["Close"].astype(float).copy()
        price_mode = "close_only"

    close = df["Close"].astype(float).copy()

    base = base.replace([np.inf, -np.inf], np.nan)
    base = base.where(base > 0)

    bb = compute_bb_log(base, window=args.window, k=args.k)

    last_idx = bb.dropna().index.max()
    if pd.isna(last_idx):
        raise SystemExit("FATAL: insufficient data to compute BB (need >= window valid points).")

    last_date = pd.Timestamp(last_idx).date().isoformat()
    last_row = bb.loc[last_idx]

    last_price = float(base.loc[last_idx])
    last_close = float(close.loc[last_idx]) if pd.notna(close.loc[last_idx]) else None

    z = float(last_row["z"])
    bucket = bucket_from_z(z)

    upper_lin = float(np.exp(last_row["upper"]))
    lower_lin = float(np.exp(last_row["lower"]))
    dist_to_lower = (last_price - lower_lin) / last_price if last_price else None
    dist_to_upper = (upper_lin - last_price) / last_price if last_price else None
    pos_in_band = float(last_row["pos"])

    prices = base.to_numpy(dtype=float)
    fwd_mdd = compute_forward_mdd(prices, forward_days=args.forward_days)

    buckets = bb["z"].apply(lambda v: bucket_from_z(float(v)) if pd.notna(v) else None)
    mask = (buckets == bucket) & np.isfinite(fwd_mdd)
    mdd_stats = summarize_mdd(fwd_mdd[mask.to_numpy()])

    # FX strict + reference
    fx_series = load_fx_history(args.fx_history)
    fx_rate_strict = fx_series.by_date.get(last_date) if fx_series.parse_status == "OK" else None
    fx_used_policy = "HISTORY_DATE_MATCH" if fx_rate_strict is not None else "NA"

    # strict derived
    price_twd = (last_price * fx_rate_strict) if fx_rate_strict is not None else None
    close_twd = (last_close * fx_rate_strict) if (fx_rate_strict is not None and last_close is not None) else None

    # reference derived (if strict missing)
    fx_ref = pick_fx_reference(last_date, fx_series, args.fx_latest)
    ref_rate = fx_ref.get("ref_rate")
    ref_date = fx_ref.get("ref_date")
    ref_lag_days = fx_ref.get("lag_days")
    ref_source = fx_ref.get("ref_source")
    ref_status = fx_ref.get("status")

    price_twd_ref = (last_price * ref_rate) if (fx_rate_strict is None and ref_rate is not None) else None
    close_twd_ref = (last_close * ref_rate) if (fx_rate_strict is None and ref_rate is not None and last_close is not None) else None

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
            # strict fields (do NOT fill with lagged)
            "rate": fx_rate_strict,
            "used_policy": fx_used_policy,
            "parse_status": fx_series.parse_status,
            "detected_date_key": fx_series.detected_date_key,
            "detected_rate_key": fx_series.detected_rate_key,
            # reference fields (only meaningful when strict is NA)
            "reference": {
                "rate": ref_rate if fx_rate_strict is None else None,
                "ref_date": ref_date if fx_rate_strict is None else None,
                "lag_days": ref_lag_days if fx_rate_strict is None else None,
                "ref_source": ref_source if fx_rate_strict is None else None,  # HISTORY or LATEST
                "status": ref_status if fx_rate_strict is None else None,
                "stale_threshold_days": fx_ref.get("stale_threshold_days"),
                "latest_status": fx_ref.get("latest_status"),
                "history_status": fx_ref.get("history_status"),
            },
        },
        "derived_twd": {
            # strict derived
            "price_twd": price_twd,
            "close_twd": close_twd,
            # reference derived (lagged FX) - only if strict missing
            "price_twd_ref": price_twd_ref,
            "close_twd_ref": close_twd_ref,
        },
        "notes": [
            "BB computed on log(price_usd) where price_usd is adj_close when available.",
            "forward_mdd20 computed on linear price_usd (same series as BB).",
            "FX strict: only same-date match populates fx_usdtwd.rate and derived_twd.price_twd.",
            "FX reference: if strict match missing, derived_twd.price_twd_ref may be computed using the most recent FX date <= data_date, with lag_days and source annotated.",
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
        # strict fx
        "fx_usdtwd": fx_rate_strict,
        "price_twd": price_twd,
        # reference fx (only if strict missing)
        "fx_ref_date": ref_date if fx_rate_strict is None else None,
        "fx_ref_rate": ref_rate if fx_rate_strict is None else None,
        "fx_ref_lag_days": ref_lag_days if fx_rate_strict is None else None,
        "fx_ref_source": ref_source if fx_rate_strict is None else None,
        "price_twd_ref": price_twd_ref,
    }

    history_obj = upsert_history(history_path, [hist_row], max_rows=args.max_history_rows)
    _write_json(history_path, history_obj)

    # report.md (human readable)
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

    report: List[str] = []
    report.append("# VT BB Monitor Report (VT + optional USD/TWD)")
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
    report.append("## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）")
    report.append(f"- fx_history_parse_status: `{fx_series.parse_status}`")
    report.append(f"- fx_strict_used_policy: `{fx_used_policy}`")
    report.append(f"- fx_rate_strict (for {last_date}): `{fmt_num(fx_rate_strict, 4)}`")
    report.append(f"- derived price_twd (strict): `{fmt_num(price_twd, 2)}`")
    report.append("")
    report.append("### Reference（僅供參考；使用落後 FX 且標註落後天數）")
    if fx_rate_strict is None and ref_rate is not None:
        report.append(f"- fx_ref_source: `{ref_source}`")
        report.append(f"- fx_ref_date: `{ref_date}`")
        report.append(f"- fx_ref_rate: `{fmt_num(ref_rate, 4)}`")
        report.append(f"- fx_ref_lag_days: `{ref_lag_days}`")
        report.append(f"- fx_ref_status: `{ref_status}` (stale_threshold_days={fx_ref.get('stale_threshold_days')})")
        report.append(f"- derived price_twd_ref: `{fmt_num(price_twd_ref, 2)}`")
    else:
        report.append("- fx_ref: `NA` (strict match exists, or no usable reference rate)")
    report.append("")
    report.append("## Notes")
    report.append("- forward_mdd20 理論上應永遠 <= 0；若你看到 >0，代表資料對齊或定義出錯。")
    report.append("- FX strict 欄位不會用落後匯率填補；落後匯率只會出現在 Reference 區塊。")
    report.append("")

    _write_text(report_path, "\n".join(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())