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
  (1) STRICT: only exact SAME-DATE match will populate main fields.
  (2) REFERENCE (optional): if strict missing, compute a *reference* TWD price
      using the most recent FX date <= vt_date (from history and/or latest),
      and explicitly annotate lag_days and source.

NEW (2026-02-20):
- Δ1D section (prev BB-computable trading day baseline)
- last 5 BB-valid trading days mini table
- streak metrics:
    * bucket streak
    * pos>=threshold streak (reading hint)
    * dist_to_upper<=threshold streak (reading hint)
- forward_mdd(20D) additional "slices" (reading-only; does NOT replace bucket-conditioned stats)
    * pos>=pos_hint_threshold
    * dist_to_upper<=dist_upper_hint_threshold
- forward_mdd(20D) "in-bucket intersection slices" (reading-only):
    * bucket ∩ pos>=threshold
    * bucket ∩ dist_to_upper<=threshold
- conf_decision + min_n_required for each forward_mdd summary

NEW (2026-02-20, band_width quantile observation; independent item):
- band_width quantile thresholds (p20/p50/p80) and current percentile
- forward_mdd(20D) slices by band_width quantiles (global; reading-only)
- forward_mdd(20D) slices by band_width quantiles within current bucket (reading-only)
- These are stored under latest.json: band_width_observation
  (does NOT affect bucket rules nor main forward_mdd stats)

PATCH (2026-02-20):
- Fix "pos vs dist_to_upper consistency check" to match *log-band geometry*.
  Previous linear approximation can falsely WARN.

PATCH (2026-02-20, review fixes):
- Safe mkdir for write_json/write_text when dirname == "".
- load_fx_latest_mid: avoid "or" short-circuit semantics; explicit None fallback.
- bucket_from_z: NaN/inf guard -> UNKNOWN.
- Use _dist_to_lower/_dist_to_upper helpers consistently in main.
- yfinance MultiIndex: assert single ticker before flatten.
- Consistency check: use abs+rel dual-threshold to avoid near-zero rel_err blowups.
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


def _ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    _ensure_parent_dir(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _write_text(path: str, text: str) -> None:
    _ensure_parent_dir(path)
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
            y = int(t[0:4])
            m = int(t[5:7])
            d = int(t[8:10])
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
    if not records:
        return None, None, "EMPTY_RECORDS"

    date_candidates = ["date", "data_date", "day", "ymd", "day_key", "UsedDate", "used_date", "d"]
    rate_candidates = ["mid", "spot_buy", "spot_sell", "usdtwd", "usd_twd", "USD_TWD", "USDTWD", "rate", "close", "value", "price"]

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
            if lk in {"mid", "spot_buy", "spot_sell"}:
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
        # Defensive plausibility range; USD/TWD should not be near 0
        if not (5.0 <= v <= 100.0):
            continue

        if len(d) == 10 and d[4] == "-" and d[7] == "-":
            out[d] = v

    return FxSeries(by_date=out, detected_date_key=date_key, detected_rate_key=rate_key, parse_status="OK")


def load_fx_latest_mid(fx_latest_path: str) -> Tuple[Optional[str], Optional[float], str]:
    obj = _read_json(fx_latest_path)
    if not isinstance(obj, dict):
        return None, None, "NO_LATEST"

    d = obj.get("data_date")
    usd = obj.get("usd_twd")
    mid: Optional[float] = None

    # Explicit None fallback; do NOT use "or" because 0.0 is falsy (even if implausible for FX).
    if isinstance(usd, dict):
        mid = _safe_float(usd.get("mid"))
        if mid is None:
            mid = _safe_float(usd.get("rate"))
        if mid is None:
            mid = _safe_float(usd.get("value"))
    else:
        mid = _safe_float(usd)

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

            # yfinance can return MultiIndex columns: (field, ticker)
            if isinstance(df.columns, pd.MultiIndex):
                # Expect single ticker in this script; refuse silently-bad flatten if not.
                if df.columns.get_level_values(1).nunique() != 1:
                    raise RuntimeError("unexpected multi-ticker MultiIndex columns from yfinance")
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
    # NaN/inf guard: do not silently map to MID_BAND
    if not math.isfinite(z):
        return "UNKNOWN"
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
    # Range is correct: last computable t is n-forward_days-1
    for t in range(0, n - forward_days):
        p0 = prices[t]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        future_min = np.min(prices[t + 1 : t + forward_days + 1])
        if not np.isfinite(future_min) or future_min <= 0:
            continue
        out[t] = (future_min / p0) - 1.0
    return out


def summarize_mdd(mdd: np.ndarray, min_n_required: int = 200) -> Dict[str, Any]:
    """
    Returns:
      n, p50, p10, min, conf, conf_decision, min_n_required

    conf:
      - statistical sample confidence tier based on n (HIGH/MED/LOW/NA)
    conf_decision:
      - OK if n >= min_n_required
      - LOW_FOR_DECISION if 0 < n < min_n_required
      - NA if n == 0
    """
    x = mdd[np.isfinite(mdd)]
    n = int(x.shape[0])
    if n == 0:
        return {
            "n": 0,
            "p50": None,
            "p10": None,
            "min": None,
            "conf": "NA",
            "conf_decision": "NA",
            "min_n_required": int(min_n_required),
        }

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

    conf_decision = "OK" if n >= min_n_required else "LOW_FOR_DECISION"

    return {
        "n": n,
        "p50": p50,
        "p10": p10,
        "min": mn,
        "conf": conf,
        "conf_decision": conf_decision,
        "min_n_required": int(min_n_required),
    }


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
def pick_fx_reference(vt_date_str: str, fx_hist: FxSeries, fx_latest_path: str) -> Dict[str, Any]:
    stale_threshold_days = 30
    vt_d = _ymd_to_date(vt_date_str)
    if vt_d is None:
        return {
            "ref_rate": None, "ref_date": None, "ref_source": None,
            "lag_days": None, "status": "VT_DATE_PARSE_FAIL",
            "stale_threshold_days": stale_threshold_days
        }

    hist_best_date = None
    hist_best_rate = None
    if fx_hist.parse_status == "OK" and fx_hist.by_date:
        for d_str, rate in fx_hist.by_date.items():
            d = _ymd_to_date(d_str)
            if d is None:
                continue
            if d <= vt_d and (hist_best_date is None or d > hist_best_date):
                hist_best_date = d
                hist_best_rate = rate

    latest_date_str, latest_mid, latest_status = load_fx_latest_mid(fx_latest_path)
    latest_d = _ymd_to_date(latest_date_str) if latest_date_str else None
    latest_ok = (latest_status == "OK" and latest_d is not None and latest_mid is not None and latest_d <= vt_d)

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
    status = "OK" if lag_days <= stale_threshold_days else "TOO_STALE"

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
# Small helpers (display + streak + series)
# ----------------------------
def _band_width_pct(lower_u: Optional[float], upper_u: Optional[float]) -> Optional[float]:
    if lower_u is None or upper_u is None:
        return None
    if not (np.isfinite(lower_u) and np.isfinite(upper_u)) or lower_u <= 0 or upper_u <= 0:
        return None
    return (upper_u / lower_u) - 1.0


def _dist_to_upper(p: Optional[float], upper_u: Optional[float]) -> Optional[float]:
    if p is None or upper_u is None:
        return None
    if not (np.isfinite(p) and np.isfinite(upper_u)) or p <= 0:
        return None
    return (upper_u - p) / p


def _dist_to_lower(p: Optional[float], lower_u: Optional[float]) -> Optional[float]:
    if p is None or lower_u is None:
        return None
    if not (np.isfinite(p) and np.isfinite(lower_u)) or p <= 0:
        return None
    return (p - lower_u) / p


def streak_from_tail(bool_series: pd.Series) -> int:
    """Count consecutive True from the end of series."""
    n = 0
    for v in reversed(bool_series.tolist()):
        if bool(v):
            n += 1
        else:
            break
    return n


def _percentile_of_score(sorted_vals: np.ndarray, x: float) -> Optional[float]:
    """
    Return percentile (0..100) of x within sorted_vals using right-inclusive rank.
    Deterministic and simple; does not assume normality.
    """
    if sorted_vals.size == 0 or not np.isfinite(x):
        return None
    k = int(np.searchsorted(sorted_vals, x, side="right"))
    return 100.0 * (k / sorted_vals.size)


def _compute_band_width_series(bb: pd.DataFrame) -> pd.Series:
    """band_width_pct series aligned to bb index: exp(upper)/exp(lower) - 1."""
    upper_u = np.exp(bb["upper"])
    lower_u = np.exp(bb["lower"])
    bw = (upper_u / lower_u) - 1.0
    bw = bw.replace([np.inf, -np.inf], np.nan)
    return bw


def _pos_dist_consistency_check_logband(
    pos: float,
    dist_to_upper: Optional[float],
    band_width_pct: Optional[float],
    rel_tolerance: float = 0.02,
    abs_tol: float = 1e-4,  # 0.01% absolute tolerance to avoid near-zero rel_err blowups
) -> Dict[str, Any]:
    """
    Consistency check for *log-band* BB.

    Given:
      pos = (logp - lower_log)/(upper_log - lower_log)
      ratio = upper/lower = exp(upper_log - lower_log) = 1 + band_width_pct

    Then implied dist_to_upper is:
      (upper - p)/p = ratio^(1-pos) - 1

    We evaluate both:
      - absolute error <= abs_tol  OR
      - relative error <= rel_tolerance
    """
    if dist_to_upper is None or band_width_pct is None:
        return {"status": "NA", "reason": "missing_fields", "rel_tolerance": float(rel_tolerance), "abs_tol": float(abs_tol), "model": "logband"}

    if not (np.isfinite(dist_to_upper) and np.isfinite(band_width_pct) and np.isfinite(pos)):
        return {"status": "NA", "reason": "non_finite", "rel_tolerance": float(rel_tolerance), "abs_tol": float(abs_tol), "model": "logband"}

    ratio = 1.0 + float(band_width_pct)
    if ratio <= 0:
        return {"status": "NA", "reason": "bad_ratio", "rel_tolerance": float(rel_tolerance), "abs_tol": float(abs_tol), "model": "logband"}

    implied = (ratio ** (1.0 - float(pos))) - 1.0

    abs_err = abs(float(dist_to_upper) - float(implied))
    denom = max(1e-12, abs(float(implied)), abs(float(dist_to_upper)))
    rel_err = abs_err / denom

    if abs_err <= abs_tol or rel_err <= rel_tolerance:
        return {
            "status": "OK",
            "reason": "within_abs_or_rel_tolerance",
            "abs_err": float(abs_err),
            "abs_tol": float(abs_tol),
            "rel_err": float(rel_err),
            "rel_tolerance": float(rel_tolerance),
            "expected_dist_to_upper": float(implied),
            "model": "logband",
        }

    return {
        "status": "WARN",
        "reason": "outside_abs_and_rel_tolerance",
        "abs_err": float(abs_err),
        "abs_tol": float(abs_tol),
        "rel_err": float(rel_err),
        "rel_tolerance": float(rel_tolerance),
        "expected_dist_to_upper": float(implied),
        "model": "logband",
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

    # reading thresholds (do NOT change bucket rules)
    ap.add_argument("--pos_hint_threshold", type=float, default=0.80)
    ap.add_argument("--dist_upper_hint_threshold", type=float, default=0.02)  # 2%

    # decision guard
    ap.add_argument("--min_n_required", type=int, default=200)

    # band_width observation quantiles
    ap.add_argument("--bw_low_q", type=float, default=20.0)   # p20
    ap.add_argument("--bw_high_q", type=float, default=80.0)  # p80

    # tolerance for consistency check
    ap.add_argument("--consistency_rel_tolerance", type=float, default=0.02)
    ap.add_argument("--consistency_abs_tol", type=float, default=1e-4)

    args = ap.parse_args()

    generated_at_utc = utc_now_iso()

    df = fetch_daily_ohlc(args.ticker)

    if "Adj Close" in df.columns and df["Adj Close"].notna().any():
        base = df["Adj Close"].astype(float).copy()
        price_mode = "adj_close"
    else:
        base = df["Close"].astype(float).copy()
        price_mode = "close_only"

    close = df["Close"].astype(float).copy()

    base = base.replace([np.inf, -np.inf], np.nan)
    # Note: NaN stays NaN; invalid <=0 becomes NaN (excluded by rolling min_periods)
    base = base.where(base > 0)

    bb = compute_bb_log(base, window=args.window, k=args.k)

    bb_valid = bb.dropna()
    last_idx = bb_valid.index.max()
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

    # Use helpers consistently
    dist_to_lower = _dist_to_lower(last_price, lower_lin)
    dist_to_upper = _dist_to_upper(last_price, upper_lin)

    pos_in_band = float(last_row["pos"])
    band_width_pct = _band_width_pct(lower_lin, upper_lin)

    # forward_mdd series (aligned to base index)
    prices = base.to_numpy(dtype=float)
    fwd_mdd = compute_forward_mdd(prices, forward_days=args.forward_days)

    # bucket-conditioned distribution (main stat)
    buckets_series = bb["z"].apply(lambda v: bucket_from_z(float(v)) if pd.notna(v) else None)
    mask_bucket = (buckets_series == bucket) & np.isfinite(fwd_mdd)
    mdd_stats_bucket = summarize_mdd(fwd_mdd[mask_bucket.to_numpy()], min_n_required=args.min_n_required)

    # slice-conditioned distributions (global; reading-only)
    pos_series = bb["pos"]
    upper_lin_series = np.exp(bb["upper"])
    dist_u_series = (upper_lin_series - base) / base

    mask_pos = (pos_series >= args.pos_hint_threshold) & np.isfinite(fwd_mdd)
    mdd_stats_pos = summarize_mdd(fwd_mdd[mask_pos.fillna(False).to_numpy()], min_n_required=args.min_n_required)

    mask_distu = (dist_u_series <= args.dist_upper_hint_threshold) & np.isfinite(fwd_mdd)
    mdd_stats_distu = summarize_mdd(fwd_mdd[mask_distu.fillna(False).to_numpy()], min_n_required=args.min_n_required)

    forward_mdd20_slices = {
        f"pos>={args.pos_hint_threshold:.2f}": {
            "condition": f"pos_in_band>={args.pos_hint_threshold:.2f}",
            **mdd_stats_pos,
        },
        f"dist_to_upper<={args.dist_upper_hint_threshold*100:.1f}%": {
            "condition": f"dist_to_upper<={args.dist_upper_hint_threshold:.4f}",
            **mdd_stats_distu,
        },
    }

    # in-bucket intersection slices (reading-only; avoid mixing regimes)
    mask_pos_in_bucket = (buckets_series == bucket) & (pos_series >= args.pos_hint_threshold) & np.isfinite(fwd_mdd)
    mdd_stats_pos_in_bucket = summarize_mdd(
        fwd_mdd[mask_pos_in_bucket.fillna(False).to_numpy()],
        min_n_required=args.min_n_required,
    )

    mask_distu_in_bucket = (buckets_series == bucket) & (dist_u_series <= args.dist_upper_hint_threshold) & np.isfinite(fwd_mdd)
    mdd_stats_distu_in_bucket = summarize_mdd(
        fwd_mdd[mask_distu_in_bucket.fillna(False).to_numpy()],
        min_n_required=args.min_n_required,
    )

    forward_mdd20_slices_in_bucket = {
        f"bucket={bucket} ∩ pos>={args.pos_hint_threshold:.2f}": {
            "condition": f"(bucket=={bucket}) AND (pos_in_band>={args.pos_hint_threshold:.2f})",
            **mdd_stats_pos_in_bucket,
        },
        f"bucket={bucket} ∩ dist_to_upper<={args.dist_upper_hint_threshold*100:.1f}%": {
            "condition": f"(bucket=={bucket}) AND (dist_to_upper<={args.dist_upper_hint_threshold:.4f})",
            **mdd_stats_distu_in_bucket,
        },
    }

    # streaks on BB-valid trading days
    bbv = bb_valid.copy()
    bbv_bucket = bbv["z"].apply(lambda vv: bucket_from_z(float(vv)) if pd.notna(vv) else None)

    bucket_streak = streak_from_tail((bbv_bucket == bucket).astype(bool))
    pos_streak = streak_from_tail((bbv["pos"] >= args.pos_hint_threshold).fillna(False).astype(bool))

    bbv_upper = np.exp(bbv["upper"])
    bbv_price = base.reindex(bbv.index)
    bbv_dist_u = (bbv_upper - bbv_price) / bbv_price
    distu_streak = streak_from_tail((bbv_dist_u <= args.dist_upper_hint_threshold).fillna(False).astype(bool))

    # consistency check (logband geometry; abs+rel thresholds)
    consistency_check = _pos_dist_consistency_check_logband(
        pos=pos_in_band,
        dist_to_upper=dist_to_upper,
        band_width_pct=band_width_pct,
        rel_tolerance=args.consistency_rel_tolerance,
        abs_tol=args.consistency_abs_tol,
    )

    # ----------------------------
    # band_width quantile observation (independent item)
    # ----------------------------
    bw_series = _compute_band_width_series(bb)
    bw_valid = bw_series.reindex(bb_valid.index)
    bw_vals = bw_valid.to_numpy(dtype=float)
    bw_vals = bw_vals[np.isfinite(bw_vals)]
    bw_vals_sorted = np.sort(bw_vals) if bw_vals.size > 0 else np.array([], dtype=float)

    bw_p20 = float(np.percentile(bw_vals_sorted, args.bw_low_q)) if bw_vals_sorted.size > 0 else None
    bw_p50 = float(np.percentile(bw_vals_sorted, 50.0)) if bw_vals_sorted.size > 0 else None
    bw_p80 = float(np.percentile(bw_vals_sorted, args.bw_high_q)) if bw_vals_sorted.size > 0 else None
    bw_pctl = _percentile_of_score(bw_vals_sorted, float(band_width_pct)) if (band_width_pct is not None and bw_vals_sorted.size > 0) else None

    if bw_p20 is None or bw_p80 is None:
        mask_bw_low = pd.Series(False, index=bb.index)
        mask_bw_high = pd.Series(False, index=bb.index)
    else:
        mask_bw_low = (bw_series <= float(bw_p20))
        mask_bw_high = (bw_series >= float(bw_p80))

    mdd_bw_low = summarize_mdd(
        fwd_mdd[(mask_bw_low.fillna(False).to_numpy()) & np.isfinite(fwd_mdd)],
        min_n_required=args.min_n_required,
    )
    mdd_bw_high = summarize_mdd(
        fwd_mdd[(mask_bw_high.fillna(False).to_numpy()) & np.isfinite(fwd_mdd)],
        min_n_required=args.min_n_required,
    )

    mask_bw_low_in_bucket = (buckets_series == bucket) & mask_bw_low & np.isfinite(fwd_mdd)
    mask_bw_high_in_bucket = (buckets_series == bucket) & mask_bw_high & np.isfinite(fwd_mdd)

    mdd_bw_low_in_bucket = summarize_mdd(
        fwd_mdd[mask_bw_low_in_bucket.fillna(False).to_numpy()],
        min_n_required=args.min_n_required,
    )
    mdd_bw_high_in_bucket = summarize_mdd(
        fwd_mdd[mask_bw_high_in_bucket.fillna(False).to_numpy()],
        min_n_required=args.min_n_required,
    )

    bwv = bw_valid.copy()
    bw_low_streak = 0
    bw_high_streak = 0
    if bw_p20 is not None:
        bw_low_streak = streak_from_tail((bwv <= float(bw_p20)).fillna(False).astype(bool))
    if bw_p80 is not None:
        bw_high_streak = streak_from_tail((bwv >= float(bw_p80)).fillna(False).astype(bool))

    band_width_observation = {
        "note": "Independent observation only. Does NOT affect bucket rules nor main forward_mdd stats.",
        "current": {
            "band_width_pct": band_width_pct,
            "percentile": bw_pctl,
        },
        "quantiles": {
            "q_low": float(args.bw_low_q),
            "q_high": float(args.bw_high_q),
            "p_low": bw_p20,
            "p50": bw_p50,
            "p_high": bw_p80,
            "n_bw_samples": int(bw_vals_sorted.size),
        },
        "streak": {
            "bw_le_p_low_streak": int(bw_low_streak),
            "bw_ge_p_high_streak": int(bw_high_streak),
        },
        "forward_mdd20_bw_slices": {
            f"bw<=p{int(args.bw_low_q)}": {
                "condition": f"band_width_pct <= p{int(args.bw_low_q)}",
                **mdd_bw_low,
            },
            f"bw>=p{int(args.bw_high_q)}": {
                "condition": f"band_width_pct >= p{int(args.bw_high_q)}",
                **mdd_bw_high,
            },
        },
        "forward_mdd20_bw_slices_in_bucket": {
            f"bucket={bucket} ∩ bw<=p{int(args.bw_low_q)}": {
                "condition": f"(bucket=={bucket}) AND (band_width_pct <= p{int(args.bw_low_q)})",
                **mdd_bw_low_in_bucket,
            },
            f"bucket={bucket} ∩ bw>=p{int(args.bw_high_q)}": {
                "condition": f"(bucket=={bucket}) AND (band_width_pct >= p{int(args.bw_high_q)})",
                **mdd_bw_high_in_bucket,
            },
        },
    }

    # ----------------------------
    # FX strict + reference
    # ----------------------------
    fx_series = load_fx_history(args.fx_history)
    fx_rate_strict = fx_series.by_date.get(last_date) if fx_series.parse_status == "OK" else None
    fx_used_policy = "HISTORY_DATE_MATCH" if fx_rate_strict is not None else "NA"

    price_twd = (last_price * fx_rate_strict) if fx_rate_strict is not None else None
    close_twd = (last_close * fx_rate_strict) if (fx_rate_strict is not None and last_close is not None) else None

    fx_ref = pick_fx_reference(last_date, fx_series, args.fx_latest)
    ref_rate = fx_ref.get("ref_rate")
    ref_date = fx_ref.get("ref_date")
    ref_lag_days = fx_ref.get("lag_days")
    ref_source = fx_ref.get("ref_source")
    ref_status = fx_ref.get("status")

    price_twd_ref = (last_price * ref_rate) if (fx_rate_strict is None and ref_rate is not None) else None
    close_twd_ref = (last_close * ref_rate) if (fx_rate_strict is None and ref_rate is not None and last_close is not None) else None

    # ----------------------------
    # Write latest.json / history.json / report.md
    # ----------------------------
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
        "min_n_required": int(args.min_n_required),
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
            "band_width_pct": band_width_pct,  # display-friendly; not used for signal
            "streak": {
                "bucket_streak": int(bucket_streak),
                "pos_ge_threshold_streak": int(pos_streak),
                "dist_u_le_threshold_streak": int(distu_streak),
                "pos_threshold": float(args.pos_hint_threshold),
                "dist_u_threshold": float(args.dist_upper_hint_threshold),
            },
        },
        "consistency_check": {
            "pos_vs_dist_to_upper": consistency_check,
        },
        "forward_mdd20": mdd_stats_bucket,
        "forward_mdd20_slices": forward_mdd20_slices,  # reading-only
        "forward_mdd20_slices_in_bucket": forward_mdd20_slices_in_bucket,  # reading-only
        "band_width_observation": band_width_observation,  # independent observation item
        "fx_usdtwd": {
            "rate": fx_rate_strict,
            "used_policy": fx_used_policy,
            "parse_status": fx_series.parse_status,
            "detected_date_key": fx_series.detected_date_key,
            "detected_rate_key": fx_series.detected_rate_key,
            "reference": {
                "rate": ref_rate if fx_rate_strict is None else None,
                "ref_date": ref_date if fx_rate_strict is None else None,
                "lag_days": ref_lag_days if fx_rate_strict is None else None,
                "ref_source": ref_source if fx_rate_strict is None else None,
                "status": ref_status if fx_rate_strict is None else None,
                "stale_threshold_days": fx_ref.get("stale_threshold_days"),
                "latest_status": fx_ref.get("latest_status"),
                "history_status": fx_ref.get("history_status"),
            },
        },
        "derived_twd": {
            "price_twd": price_twd,
            "close_twd": close_twd,
            "price_twd_ref": price_twd_ref,
            "close_twd_ref": close_twd_ref,
        },
        "notes": [
            "BB computed on log(price_usd) where price_usd is adj_close when available.",
            "forward_mdd20 computed on linear price_usd (same series as BB).",
            "forward_mdd20_slices and *_in_bucket are reading-only; do NOT replace bucket-conditioned stats.",
            "band_width_observation is independent reading-only; does NOT affect bucket rules nor main forward_mdd stats.",
            "Consistency check uses logband geometry with abs+rel thresholds; expected dist_to_upper = (1+band_width_pct)^(1-pos) - 1.",
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

        "band_width_pct": band_width_pct,
        "dist_to_upper": dist_to_upper,

        "p50_mdd20": mdd_stats_bucket.get("p50"),
        "p10_mdd20": mdd_stats_bucket.get("p10"),
        "min_mdd20": mdd_stats_bucket.get("min"),
        "n_mdd20": mdd_stats_bucket.get("n"),

        "p50_mdd20_pos_ge": mdd_stats_pos.get("p50"),
        "n_mdd20_pos_ge": mdd_stats_pos.get("n"),
        "p50_mdd20_dist_u_le": mdd_stats_distu.get("p50"),
        "n_mdd20_dist_u_le": mdd_stats_distu.get("n"),

        "p50_mdd20_pos_ge_in_bucket": mdd_stats_pos_in_bucket.get("p50"),
        "n_mdd20_pos_ge_in_bucket": mdd_stats_pos_in_bucket.get("n"),
        "p50_mdd20_dist_u_le_in_bucket": mdd_stats_distu_in_bucket.get("p50"),
        "n_mdd20_dist_u_le_in_bucket": mdd_stats_distu_in_bucket.get("n"),

        "p50_mdd20_bw_low": mdd_bw_low.get("p50"),
        "n_mdd20_bw_low": mdd_bw_low.get("n"),
        "p50_mdd20_bw_high": mdd_bw_high.get("p50"),
        "n_mdd20_bw_high": mdd_bw_high.get("n"),

        "p50_mdd20_bw_low_in_bucket": mdd_bw_low_in_bucket.get("p50"),
        "n_mdd20_bw_low_in_bucket": mdd_bw_low_in_bucket.get("n"),
        "p50_mdd20_bw_high_in_bucket": mdd_bw_high_in_bucket.get("p50"),
        "n_mdd20_bw_high_in_bucket": mdd_bw_high_in_bucket.get("n"),

        "fx_usdtwd": fx_rate_strict,
        "price_twd": price_twd,

        "fx_ref_date": ref_date if fx_rate_strict is None else None,
        "fx_ref_rate": ref_rate if fx_rate_strict is None else None,
        "fx_ref_lag_days": ref_lag_days if fx_rate_strict is None else None,
        "fx_ref_source": ref_source if fx_rate_strict is None else None,
        "price_twd_ref": price_twd_ref,
    }

    history_obj = upsert_history(history_path, [hist_row], max_rows=args.max_history_rows)
    _write_json(history_path, history_obj)

    # ----------------------------
    # report.md
    # ----------------------------
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

    def fmt_money(x: Any, nd: int = 2) -> str:
        v = _safe_float(x)
        if v is None:
            return "NA"
        return f"{v:.{nd}f}"

    def fmt_int(x: Any) -> str:
        if x is None:
            return "NA"
        try:
            return str(int(x))
        except Exception:
            return "NA"

    # Δ1D vs previous BB-valid day
    prev_date = None
    d_price_1d = None
    d_z_1d = None
    d_pos_1d = None
    d_bw_1d = None
    d_dist_u_1d = None

    if len(bb_valid.index) >= 2:
        prev_idx = bb_valid.index[-2]
        prev_date = pd.Timestamp(prev_idx).date().isoformat()

        prev_price = _safe_float(base.loc[prev_idx]) if prev_idx in base.index else None
        prev_z = _safe_float(bb.loc[prev_idx, "z"]) if prev_idx in bb.index else None
        prev_pos = _safe_float(bb.loc[prev_idx, "pos"]) if prev_idx in bb.index else None

        prev_upper = None
        prev_lower = None
        try:
            prev_upper = float(np.exp(bb.loc[prev_idx, "upper"]))
            prev_lower = float(np.exp(bb.loc[prev_idx, "lower"]))
        except Exception:
            prev_upper = None
            prev_lower = None

        prev_bw = _band_width_pct(prev_lower, prev_upper)
        prev_dist_u = _dist_to_upper(prev_price, prev_upper)

        if prev_price is not None and prev_price > 0:
            d_price_1d = (last_price / prev_price) - 1.0
        if prev_z is not None:
            d_z_1d = z - float(prev_z)
        if prev_pos is not None:
            d_pos_1d = pos_in_band - float(prev_pos)
        if prev_bw is not None and band_width_pct is not None:
            d_bw_1d = band_width_pct - float(prev_bw)
        if prev_dist_u is not None and dist_to_upper is not None:
            d_dist_u_1d = dist_to_upper - float(prev_dist_u)

    # last 5 BB-valid days table
    tail_n = 5
    tail_idx = list(bb_valid.index[-tail_n:]) if len(bb_valid.index) > 0 else []
    tail_rows: List[Dict[str, Any]] = []
    for ts in tail_idx:
        d = pd.Timestamp(ts).date().isoformat()
        p = _safe_float(base.loc[ts]) if ts in base.index else None
        zz = _safe_float(bb.loc[ts, "z"]) if ts in bb.index else None
        pp = _safe_float(bb.loc[ts, "pos"]) if ts in bb.index else None
        try:
            uu = float(np.exp(bb.loc[ts, "upper"]))
        except Exception:
            uu = None
        dist_u = _dist_to_upper(p, uu)
        bkt = bucket_from_z(float(zz)) if zz is not None else "NA"
        tail_rows.append({"date": d, "price_usd": p, "z": zz, "pos": pp, "bucket": bkt, "dist_to_upper": dist_u})

    # build report
    R: List[str] = []
    R.append("# VT BB Monitor Report (VT + optional USD/TWD)")
    R.append("")
    R.append(f"- report_generated_at_utc: `{generated_at_utc}`")
    R.append(f"- data_date: `{last_date}`")
    R.append(f"- price_mode: `{price_mode}`")
    R.append(f"- params: `BB({args.window},{args.k}) on log(price)`, `forward_mdd({args.forward_days}D)`")
    R.append("")

    R.append("## 15秒摘要")
    R.append(
        f"- **VT** ({last_date} price_usd={fmt_money(last_price, 4)}) → **{bucket}** "
        f"(z={fmt_num(z, 4)}, pos={fmt_num(pos_in_band, 4)}); "
        f"dist_to_lower={fmt_pct(dist_to_lower)}; dist_to_upper={fmt_pct(dist_to_upper)}; "
        f"{args.forward_days}D forward_mdd: p50={fmt_pct(mdd_stats_bucket.get('p50'))}, "
        f"p10={fmt_pct(mdd_stats_bucket.get('p10'))}, min={fmt_pct(mdd_stats_bucket.get('min'))} "
        f"(n={mdd_stats_bucket.get('n')}, conf={mdd_stats_bucket.get('conf')}, "
        f"conf_decision={mdd_stats_bucket.get('conf_decision')}, min_n_required={mdd_stats_bucket.get('min_n_required')})"
    )
    R.append("")

    R.append("## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）")
    if prev_date is None:
        R.append("- Δ1D: `NA`（資料不足：至少需要 2 個可計算 BB 的交易日）")
    else:
        R.append(f"- prev_bb_date: `{prev_date}`")
        R.append(f"- Δprice_1d: {fmt_pct(d_price_1d)}")
        R.append(f"- Δz_1d: {fmt_num(d_z_1d, 4)}")
        R.append(f"- Δpos_1d: {fmt_num(d_pos_1d, 4)}")
        R.append(f"- Δband_width_1d: {fmt_pct(d_bw_1d)}")
        R.append(f"- Δdist_to_upper_1d: {fmt_pct(d_dist_u_1d)}")
    R.append("")

    R.append("## 解讀重點（更詳盡）")
    R.append(f"- **Band 位置**：pos={fmt_num(pos_in_band, 4)}（≥{args.pos_hint_threshold:.2f} 視為「靠近上緣」閱讀提示；此提示不改 bucket 規則）")
    R.append(f"- **距離上下軌**：dist_to_upper={fmt_pct(dist_to_upper)}；dist_to_lower={fmt_pct(dist_to_lower)}")
    R.append(f"- **波動區間寬度（閱讀用）**：band_width≈{fmt_pct(band_width_pct)}（= upper/lower - 1；用於直覺理解，不作信號）")
    R.append(f"- **streak（連續天數）**：bucket_streak={bucket_streak}；pos≥{args.pos_hint_threshold:.2f} streak={pos_streak}；dist_to_upper≤{args.dist_upper_hint_threshold*100:.1f}% streak={distu_streak}")
    R.append(
        f"- **forward_mdd({args.forward_days}D)**（bucket={bucket}）："
        f"p50={fmt_pct(mdd_stats_bucket.get('p50'))}、p10={fmt_pct(mdd_stats_bucket.get('p10'))}、min={fmt_pct(mdd_stats_bucket.get('min'))}；"
        f"n={mdd_stats_bucket.get('n')}（conf={mdd_stats_bucket.get('conf')}；conf_decision={mdd_stats_bucket.get('conf_decision')}）"
    )
    R.append("")

    R.append("## pos vs dist_to_upper 一致性檢查（提示用；不改數值）")
    R.append(f"- status: `{consistency_check.get('status')}`")
    R.append(f"- reason: `{consistency_check.get('reason')}`")
    if "expected_dist_to_upper" in consistency_check:
        R.append(f"- expected_dist_to_upper(logband): `{fmt_pct(consistency_check.get('expected_dist_to_upper'))}`")
    if "abs_err" in consistency_check:
        R.append(f"- abs_err: `{fmt_num(consistency_check.get('abs_err'), 8)}`; abs_tol: `{fmt_num(consistency_check.get('abs_tol'), 8)}`")
    if "rel_err" in consistency_check:
        R.append(f"- rel_err: `{fmt_num(consistency_check.get('rel_err'), 6)}`; rel_tolerance: `{fmt_num(consistency_check.get('rel_tolerance'), 6)}`")
    R.append("")

    R.append(f"## forward_mdd({args.forward_days}D) 切片分布（閱讀用；不回填主欄位）")
    R.append("")
    R.append(
        f"- Slice A（pos≥{args.pos_hint_threshold:.2f}）："
        f"p50={fmt_pct(mdd_stats_pos.get('p50'))}、p10={fmt_pct(mdd_stats_pos.get('p10'))}、min={fmt_pct(mdd_stats_pos.get('min'))} "
        f"(n={mdd_stats_pos.get('n')}, conf={mdd_stats_pos.get('conf')}, conf_decision={mdd_stats_pos.get('conf_decision')}, min_n_required={mdd_stats_pos.get('min_n_required')})"
    )
    R.append(
        f"- Slice B（dist_to_upper≤{args.dist_upper_hint_threshold*100:.1f}%）："
        f"p50={fmt_pct(mdd_stats_distu.get('p50'))}、p10={fmt_pct(mdd_stats_distu.get('p10'))}、min={fmt_pct(mdd_stats_distu.get('min'))} "
        f"(n={mdd_stats_distu.get('n')}, conf={mdd_stats_distu.get('conf')}, conf_decision={mdd_stats_distu.get('conf_decision')}, min_n_required={mdd_stats_distu.get('min_n_required')})"
    )
    R.append("- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。")
    R.append("")

    R.append(f"## forward_mdd({args.forward_days}D) 交集切片（bucket 內；閱讀用；不回填主欄位）")
    R.append("")
    R.append(
        f"- Slice A_inBucket（bucket={bucket} ∩ pos≥{args.pos_hint_threshold:.2f}）："
        f"p50={fmt_pct(mdd_stats_pos_in_bucket.get('p50'))}、p10={fmt_pct(mdd_stats_pos_in_bucket.get('p10'))}、min={fmt_pct(mdd_stats_pos_in_bucket.get('min'))} "
        f"(n={mdd_stats_pos_in_bucket.get('n')}, conf={mdd_stats_pos_in_bucket.get('conf')}, conf_decision={mdd_stats_pos_in_bucket.get('conf_decision')}, min_n_required={mdd_stats_pos_in_bucket.get('min_n_required')})"
    )
    R.append(
        f"- Slice B_inBucket（bucket={bucket} ∩ dist_to_upper≤{args.dist_upper_hint_threshold*100:.1f}%）："
        f"p50={fmt_pct(mdd_stats_distu_in_bucket.get('p50'))}、p10={fmt_pct(mdd_stats_distu_in_bucket.get('p10'))}、min={fmt_pct(mdd_stats_distu_in_bucket.get('min'))} "
        f"(n={mdd_stats_distu_in_bucket.get('n')}, conf={mdd_stats_distu_in_bucket.get('conf')}, conf_decision={mdd_stats_distu_in_bucket.get('conf_decision')}, min_n_required={mdd_stats_distu_in_bucket.get('min_n_required')})"
    )
    R.append("- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。")
    R.append("")

    R.append("## band_width 分位數觀察（獨立項目；不改 bucket / 不回填主欄位）")
    R.append("")
    if bw_p20 is None or bw_p80 is None or bw_pctl is None:
        R.append("- 狀態：`NA`（band_width 分位數樣本不足或計算失敗）")
    else:
        R.append(f"- band_width_current: {fmt_pct(band_width_pct)}; percentile≈{fmt_num(bw_pctl, 2)}")
        R.append(
            f"- quantiles: p{int(args.bw_low_q)}={fmt_pct(bw_p20)}, p50={fmt_pct(bw_p50)}, p{int(args.bw_high_q)}={fmt_pct(bw_p80)} "
            f"(n_bw_samples={fmt_int(band_width_observation['quantiles']['n_bw_samples'])})"
        )
        R.append(
            f"- streak: bw≤p{int(args.bw_low_q)} streak={fmt_int(band_width_observation['streak']['bw_le_p_low_streak'])}; "
            f"bw≥p{int(args.bw_high_q)} streak={fmt_int(band_width_observation['streak']['bw_ge_p_high_streak'])}"
        )
        R.append("")
        R.append(f"### forward_mdd({args.forward_days}D) × band_width（全樣本切片；閱讀用）")
        R.append(
            f"- BW_LOW（bw≤p{int(args.bw_low_q)}）："
            f"p50={fmt_pct(mdd_bw_low.get('p50'))}、p10={fmt_pct(mdd_bw_low.get('p10'))}、min={fmt_pct(mdd_bw_low.get('min'))} "
            f"(n={mdd_bw_low.get('n')}, conf={mdd_bw_low.get('conf')}, conf_decision={mdd_bw_low.get('conf_decision')})"
        )
        R.append(
            f"- BW_HIGH（bw≥p{int(args.bw_high_q)}）："
            f"p50={fmt_pct(mdd_bw_high.get('p50'))}、p10={fmt_pct(mdd_bw_high.get('p10'))}、min={fmt_pct(mdd_bw_high.get('min'))} "
            f"(n={mdd_bw_high.get('n')}, conf={mdd_bw_high.get('conf')}, conf_decision={mdd_bw_high.get('conf_decision')})"
        )
        R.append("")
        R.append(f"### forward_mdd({args.forward_days}D) × band_width（bucket 內交集；閱讀用）")
        R.append(
            f"- BW_LOW_inBucket（bucket={bucket} ∩ bw≤p{int(args.bw_low_q)}）："
            f"p50={fmt_pct(mdd_bw_low_in_bucket.get('p50'))}、p10={fmt_pct(mdd_bw_low_in_bucket.get('p10'))}、min={fmt_pct(mdd_bw_low_in_bucket.get('min'))} "
            f"(n={mdd_bw_low_in_bucket.get('n')}, conf={mdd_bw_low_in_bucket.get('conf')}, conf_decision={mdd_bw_low_in_bucket.get('conf_decision')})"
        )
        R.append(
            f"- BW_HIGH_inBucket（bucket={bucket} ∩ bw≥p{int(args.bw_high_q)}）："
            f"p50={fmt_pct(mdd_bw_high_in_bucket.get('p50'))}、p10={fmt_pct(mdd_bw_high_in_bucket.get('p10'))}、min={fmt_pct(mdd_bw_high_in_bucket.get('min'))} "
            f"(n={mdd_bw_high_in_bucket.get('n')}, conf={mdd_bw_high_in_bucket.get('conf')}, conf_decision={mdd_bw_high_in_bucket.get('conf_decision')})"
        )
        R.append("- 說明：這是「獨立觀察項」，用來觀察 band 寬窄是否改變 forward_mdd 的尾部形狀；不作為信號。")
    R.append("")

    R.append("## 近 5 日（可計算 BB 的交易日；小表）")
    R.append("")
    if not tail_rows:
        R.append("- `NA`（無可計算 BB 的資料）")
        R.append("")
    else:
        R.append("| date | price_usd | z | pos | bucket | dist_to_upper |")
        R.append("|---|---:|---:|---:|---|---:|")
        for tr in tail_rows:
            R.append(
                f"| {tr['date']} | {fmt_money(tr['price_usd'], 4)} | {fmt_num(tr['z'], 4)} | {fmt_num(tr['pos'], 4)} | {tr['bucket']} | {fmt_pct(tr['dist_to_upper'])} |"
            )
        R.append("")

    R.append("## BB 詳細（可稽核欄位）")
    R.append("")
    R.append("| field | value | note |")
    R.append("|---|---:|---|")
    R.append(f"| price_usd | {fmt_money(last_price, 4)} | {price_mode} |")
    R.append(f"| close_usd | {fmt_money(last_close, 4) if last_close is not None else 'NA'} | raw close (for reference) |")
    R.append(f"| z | {fmt_num(z, 4)} | log(price) z-score vs BB mean/stdev |")
    R.append(f"| pos_in_band | {fmt_num(pos_in_band, 4)} | (logp-lower)/(upper-lower) clipped [0,1] |")
    R.append(f"| lower_usd | {fmt_money(lower_lin, 4)} | exp(lower_log) |")
    R.append(f"| upper_usd | {fmt_money(upper_lin, 4)} | exp(upper_log) |")
    R.append(f"| dist_to_lower | {fmt_pct(dist_to_lower)} | (price-lower)/price |")
    R.append(f"| dist_to_upper | {fmt_pct(dist_to_upper)} | (upper-price)/price |")
    R.append(f"| band_width | {fmt_pct(band_width_pct)} | (upper/lower - 1) reading-only |")
    R.append(f"| bucket | {bucket} | based on z thresholds |")
    R.append("")

    R.append(f"## forward_mdd({args.forward_days}D)（分布解讀）")
    R.append("")
    R.append("- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。")
    R.append("- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。")
    R.append(f"- 你目前看到的是 **bucket={bucket}** 條件下的歷史樣本分布（不是預測）。")
    R.append("")

    R.append("## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）")
    R.append(f"- fx_history_parse_status: `{fx_series.parse_status}`")
    R.append(f"- fx_strict_used_policy: `{fx_used_policy}`")
    R.append(f"- fx_rate_strict (for {last_date}): `{fmt_num(fx_rate_strict, 4)}`")
    R.append(f"- derived price_twd (strict): `{fmt_money(price_twd, 2)}`")
    R.append("")
    R.append("### Reference（僅供參考；使用落後 FX 且標註落後天數）")
    if fx_rate_strict is None and ref_rate is not None:
        R.append(f"- fx_ref_source: `{ref_source}`")
        R.append(f"- fx_ref_date: `{ref_date}`")
        R.append(f"- fx_ref_rate: `{fmt_num(ref_rate, 4)}`")
        R.append(f"- fx_ref_lag_days: `{ref_lag_days}`")
        R.append(f"- fx_ref_status: `{ref_status}` (stale_threshold_days={fx_ref.get('stale_threshold_days')})")
        R.append(f"- derived price_twd_ref: `{fmt_money(price_twd_ref, 2)}`")
        R.append("- 說明：Reference 不會回填 strict 欄位；它只是一個「在 FX 滯後下的閱讀參考價」。")
    else:
        R.append("- fx_ref: `NA` (strict match exists, or no usable reference rate)")
    R.append("")

    R.append("## Data Quality / Staleness 提示（不改數值，只提示狀態）")
    if fx_rate_strict is None and ref_lag_days is not None:
        R.append(f"- FX strict 缺值，已提供 Reference；lag_days={ref_lag_days}。")
    else:
        R.append("- FX strict 有值（同日對齊成立）或無可用參考。")
    R.append("- 若遇到長假/休市期間，FX strict 為 NA 屬於正常現象；Reference 會明確標註落後天數。")
    R.append("")

    R.append("## Notes")
    R.append("- bucket 以 z 門檻定義；pos/dist_to_upper 的閾值僅作閱讀提示，不改信號。")
    R.append("- Δ1D 的基準是「前一個可計算 BB 的交易日」，不是日曆上的昨天。")
    R.append("- forward_mdd 切片（含 in-bucket / band_width）為閱讀用；conf_decision 會在樣本數不足時標示 LOW_FOR_DECISION。")
    R.append("- pos vs dist_to_upper 一致性檢查採 logband 幾何一致性，並用 abs+rel 雙門檻避免 near-zero 相對誤差放大。")
    R.append("- FX strict 欄位不會用落後匯率填補；落後匯率只會出現在 Reference 區塊。")
    R.append("")

    _write_text(report_path, "\n".join(R))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())