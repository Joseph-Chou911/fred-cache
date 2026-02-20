#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BB(60,2) + forward_mdd(20D) monitor (independent module)

Outputs (deterministic, audit-first):
- <cache_dir>/latest.json
- <cache_dir>/history.json
- <cache_dir>/report.md

Key design choices:
- BB computed on log(price) by default (price = adj_close if available, else close).
- forward_mdd(20D) computed on linear price series (same base series as BB).
- FX (USD/TWD):
  (1) STRICT: only exact SAME-DATE match will populate main fields.
      Strict match sources:
        - fx_history.json (preferred)
        - fx_latest.json (fallback) when it is same-date and parse OK
  (2) REFERENCE (optional): if strict missing, compute a *reference* TWD price
      using the most recent FX date <= data_date (from history and/or latest),
      and explicitly annotate lag_days and source.

PATCH set (2026-02-20, review pass):
- _safe_float: reject bool with explicit comment (bool is subclass of int).
- pick_fx_reference: rename vt_* variables to data_date_* (ticker-agnostic).
- buckets_series: unify UNKNOWN semantics (no None/UNKNOWN split).
- Add assert/guard that len(fwd_mdd) == len(bb) (audit alignment check).
- Remove redundant float(last_close) wrappers (last_close already Optional[float]).
- summarize_mdd: restore docstring clarifying conf vs conf_decision.
- report.md: keep a minimal slice summary section (human-readable parity with JSON).

PATCH set (2026-02-20, review pass #2):
- Mask ops: explicitly convert pandas Series masks to numpy arrays to avoid implicit alignment.
- Promote _safe_bucket() to module-level helper for reuse and readability.
- upsert_history: rename lambda var from x -> item for lint friendliness.
- report.md: add disclaimer to Forward MDD slices section.
- (Optional note) load_fx_latest_mid still may be called twice (strict fallback + reference); kept as-is.
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
    """Parse to finite float; reject bool explicitly."""
    if x is None:
        return None
    # bool is subclass of int; must check BEFORE isinstance(x, (int, float))
    if isinstance(x, bool):
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
# Indicators
# ----------------------------
def bucket_from_z(z: float) -> str:
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


def _safe_bucket(v: Any) -> str:
    """Safe bucketization for pandas apply; never returns None."""
    try:
        return bucket_from_z(float(v))
    except Exception:
        return "UNKNOWN"


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
    if not (5.0 <= mid <= 100.0):
        return d_str, None, "LATEST_RATE_OUT_OF_RANGE"
    return d_str, float(mid), "OK"


# ----------------------------
# Ticker data fetch
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
# BB + forward MDD
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


def summarize_mdd(mdd: np.ndarray, min_n_required: int = 200) -> Dict[str, Any]:
    """
    Summarize forward drawdown distribution.

    Returns:
      - conf: statistical confidence tier based on sample size n only:
          HIGH (n>=120), MED (n>=60), LOW (n>=20), else NA.
      - conf_decision: decision sufficiency gate:
          OK if n>=min_n_required;
          LOW_FOR_DECISION if 0<n<min_n_required;
          NA if n==0.
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
    all_items.sort(key=lambda item: str(item.get(key)))

    if max_rows and len(all_items) > max_rows:
        all_items = all_items[-max_rows:]

    return {"schema_version": "bb_cache.v1", "items": all_items}


# ----------------------------
# FX reference selection
# ----------------------------
def pick_fx_reference(data_date_str: str, fx_hist: FxSeries, fx_latest_path: str) -> Dict[str, Any]:
    """Pick the most recent FX date <= data_date, with explicit lag and staleness gate."""
    stale_threshold_days = 30
    data_d = _ymd_to_date(data_date_str)
    if data_d is None:
        return {
            "ref_rate": None, "ref_date": None, "ref_source": None,
            "lag_days": None, "status": "DATE_PARSE_FAIL",
            "stale_threshold_days": stale_threshold_days
        }

    hist_best_date = None
    hist_best_rate = None
    if fx_hist.parse_status == "OK" and fx_hist.by_date:
        for d_str, rate in fx_hist.by_date.items():
            d = _ymd_to_date(d_str)
            if d is None:
                continue
            if d <= data_d and (hist_best_date is None or d > hist_best_date):
                hist_best_date = d
                hist_best_rate = rate

    latest_date_str, latest_mid, latest_status = load_fx_latest_mid(fx_latest_path)
    latest_d = _ymd_to_date(latest_date_str) if latest_date_str else None
    latest_ok = (latest_status == "OK" and latest_d is not None and latest_mid is not None and latest_d <= data_d)

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

    lag_days = (data_d - ref_date).days
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
# Small helpers
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
    n = 0
    for v in reversed(bool_series.tolist()):
        if bool(v):
            n += 1
        else:
            break
    return n


def _pos_dist_consistency_check_logband(
    pos: float,
    dist_to_upper: Optional[float],
    band_width_pct: Optional[float],
    rel_tolerance: float = 0.02,
    abs_tol: float = 1e-4,
) -> Dict[str, Any]:
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
    ap.add_argument("--cache_dir", default="bb_cache")
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--forward_days", type=int, default=20)
    ap.add_argument("--fx_latest", default="fx_cache/latest.json")
    ap.add_argument("--fx_history", default="fx_cache/history.json")
    ap.add_argument("--max_history_rows", type=int, default=2500)

    ap.add_argument("--pos_hint_threshold", type=float, default=0.80)
    ap.add_argument("--dist_upper_hint_threshold", type=float, default=0.02)
    ap.add_argument("--min_n_required", type=int, default=200)

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
    base = base.where(base > 0)

    bb = compute_bb_log(base, window=args.window, k=args.k)
    bb_valid = bb.dropna()
    last_idx = bb_valid.index.max()
    if pd.isna(last_idx):
        raise SystemExit("FATAL: insufficient data to compute BB (need >= window valid points).")

    # Alignment guard (audit)
    prices = base.to_numpy(dtype=float)
    fwd_mdd = compute_forward_mdd(prices, forward_days=args.forward_days)
    if len(fwd_mdd) != len(bb):
        raise SystemExit(f"FATAL: fwd_mdd/bb length mismatch: len(fwd_mdd)={len(fwd_mdd)} vs len(bb)={len(bb)}")

    last_date = pd.Timestamp(last_idx).date().isoformat()
    last_row = bb.loc[last_idx]

    last_price = _safe_float(base.loc[last_idx])
    if last_price is None:
        raise SystemExit(f"FATAL: last_price is NA at {last_date}; base series corrupted or misaligned.")
    last_price = float(last_price)

    last_close = _safe_float(close.loc[last_idx]) if pd.notna(close.loc[last_idx]) else None

    z = _safe_float(last_row["z"])
    if z is None:
        raise SystemExit(f"FATAL: last z is non-finite at {last_date}; BB computation invalid.")
    z = float(z)

    bucket = bucket_from_z(z)
    if bucket == "UNKNOWN":
        raise SystemExit(f"FATAL: bucket=UNKNOWN because z is non-finite (z={z}); data may be corrupted.")

    upper_lin = float(np.exp(last_row["upper"]))
    lower_lin = float(np.exp(last_row["lower"]))

    dist_to_lower = _dist_to_lower(last_price, lower_lin)
    dist_to_upper = _dist_to_upper(last_price, upper_lin)

    pos_in_band = _safe_float(last_row["pos"])
    if pos_in_band is None:
        raise SystemExit(f"FATAL: pos_in_band is NA at {last_date}; BB computation invalid.")
    pos_in_band = float(pos_in_band)

    band_width_pct = _band_width_pct(lower_lin, upper_lin)

    # bucket series (UNKNOWN semantics unified; never None)
    buckets_series = bb["z"].apply(_safe_bucket)

    # ---- masks: explicit numpy (avoid implicit pandas alignment) ----
    mask_bucket_np = (buckets_series == bucket).to_numpy() & np.isfinite(fwd_mdd)
    mdd_stats_bucket = summarize_mdd(fwd_mdd[mask_bucket_np], min_n_required=args.min_n_required)

    pos_series = bb["pos"]
    upper_lin_series = np.exp(bb["upper"])
    dist_u_series = (upper_lin_series - base) / base

    mask_pos_np = (pos_series >= args.pos_hint_threshold).fillna(False).to_numpy() & np.isfinite(fwd_mdd)
    mdd_stats_pos = summarize_mdd(fwd_mdd[mask_pos_np], min_n_required=args.min_n_required)

    mask_distu_np = (dist_u_series <= args.dist_upper_hint_threshold).fillna(False).to_numpy() & np.isfinite(fwd_mdd)
    mdd_stats_distu = summarize_mdd(fwd_mdd[mask_distu_np], min_n_required=args.min_n_required)

    mask_pos_in_bucket_np = (
        (buckets_series == bucket).to_numpy()
        & (pos_series >= args.pos_hint_threshold).fillna(False).to_numpy()
        & np.isfinite(fwd_mdd)
    )
    mdd_stats_pos_in_bucket = summarize_mdd(fwd_mdd[mask_pos_in_bucket_np], min_n_required=args.min_n_required)

    mask_distu_in_bucket_np = (
        (buckets_series == bucket).to_numpy()
        & (dist_u_series <= args.dist_upper_hint_threshold).fillna(False).to_numpy()
        & np.isfinite(fwd_mdd)
    )
    mdd_stats_distu_in_bucket = summarize_mdd(fwd_mdd[mask_distu_in_bucket_np], min_n_required=args.min_n_required)

    # streaks
    bbv = bb_valid.copy()
    bbv_bucket = bbv["z"].apply(_safe_bucket)
    bucket_streak = streak_from_tail((bbv_bucket == bucket).astype(bool))
    pos_streak = streak_from_tail((bbv["pos"] >= args.pos_hint_threshold).fillna(False).astype(bool))

    bbv_upper = np.exp(bbv["upper"])
    bbv_price = base.reindex(bbv.index)
    bbv_dist_u = (bbv_upper - bbv_price) / bbv_price
    distu_streak = streak_from_tail((bbv_dist_u <= args.dist_upper_hint_threshold).fillna(False).astype(bool))

    consistency_check = _pos_dist_consistency_check_logband(
        pos=pos_in_band,
        dist_to_upper=dist_to_upper,
        band_width_pct=band_width_pct,
        rel_tolerance=args.consistency_rel_tolerance,
        abs_tol=args.consistency_abs_tol,
    )

    # ----------------------------
    # FX strict: history date match, else latest same-date match
    # ----------------------------
    fx_series = load_fx_history(args.fx_history)

    fx_rate_strict: Optional[float] = None
    fx_used_policy = "NA"

    if fx_series.parse_status == "OK":
        fx_rate_strict = fx_series.by_date.get(last_date)
        if fx_rate_strict is not None:
            fx_used_policy = "HISTORY_DATE_MATCH"

    if fx_rate_strict is None:
        latest_date_str, latest_mid, latest_status = load_fx_latest_mid(args.fx_latest)
        if latest_status == "OK" and latest_date_str == last_date and latest_mid is not None:
            fx_rate_strict = float(latest_mid)
            fx_used_policy = "LATEST_DATE_MATCH"

    price_twd = (last_price * fx_rate_strict) if fx_rate_strict is not None else None
    close_twd = (last_close * fx_rate_strict) if (fx_rate_strict is not None and last_close is not None) else None

    # FX reference (only if strict missing)
    fx_ref = pick_fx_reference(last_date, fx_series, args.fx_latest)
    ref_rate = fx_ref.get("ref_rate")
    ref_date = fx_ref.get("ref_date")
    ref_lag_days = fx_ref.get("lag_days")
    ref_source = fx_ref.get("ref_source")
    ref_status = fx_ref.get("status")

    price_twd_ref = (last_price * ref_rate) if (fx_rate_strict is None and ref_rate is not None) else None
    close_twd_ref = (last_close * ref_rate) if (fx_rate_strict is None and ref_rate is not None and last_close is not None) else None

    # ----------------------------
    # Write latest/history/report
    # ----------------------------
    cache_dir = args.cache_dir
    latest_path = os.path.join(cache_dir, "latest.json")
    history_path = os.path.join(cache_dir, "history.json")
    report_path = os.path.join(cache_dir, "report.md")

    latest = {
        "schema_version": "bb_cache.v1",
        "module": "bb_cache",
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
            "band_width_pct": band_width_pct,
            "streak": {
                "bucket_streak": int(bucket_streak),
                "pos_ge_threshold_streak": int(pos_streak),
                "dist_u_le_threshold_streak": int(distu_streak),
                "pos_threshold": float(args.pos_hint_threshold),
                "dist_u_threshold": float(args.dist_upper_hint_threshold),
            },
        },
        "consistency_check": {"pos_vs_dist_to_upper": consistency_check},
        "forward_mdd20": mdd_stats_bucket,
        "forward_mdd20_slices": {
            f"pos>={args.pos_hint_threshold:.2f}": {"condition": f"pos_in_band>={args.pos_hint_threshold:.2f}", **mdd_stats_pos},
            f"dist_to_upper<={args.dist_upper_hint_threshold*100:.1f}%": {"condition": f"dist_to_upper<={args.dist_upper_hint_threshold:.4f}", **mdd_stats_distu},
        },
        "forward_mdd20_slices_in_bucket": {
            f"bucket={bucket} ∩ pos>={args.pos_hint_threshold:.2f}": {
                "condition": f"(bucket=={bucket}) AND (pos_in_band>={args.pos_hint_threshold:.2f})",
                **mdd_stats_pos_in_bucket,
            },
            f"bucket={bucket} ∩ dist_to_upper<={args.dist_upper_hint_threshold*100:.1f}%": {
                "condition": f"(bucket=={bucket}) AND (dist_to_upper<={args.dist_upper_hint_threshold:.4f})",
                **mdd_stats_distu_in_bucket,
            },
        },
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
            "conf is statistical sample confidence tier (HIGH/MED/LOW/NA) based on n only.",
            "conf_decision is decision sufficiency: OK if n>=min_n_required; LOW_FOR_DECISION if 0<n<min_n_required; NA if n==0.",
            "FX strict uses exact same-date match: fx_history preferred; fx_latest same-date fallback allowed.",
            "FX reference is only used when strict is missing; reference never backfills strict fields.",
        ],
    }

    _write_json(latest_path, latest)

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

    # Δ1D vs previous BB-valid day
    prev_date = None
    d_price_1d = None
    d_z_1d = None
    d_pos_1d = None

    if len(bb_valid.index) >= 2:
        prev_idx = bb_valid.index[-2]
        prev_date = pd.Timestamp(prev_idx).date().isoformat()

        prev_price = _safe_float(base.loc[prev_idx]) if prev_idx in base.index else None
        prev_z = _safe_float(bb.loc[prev_idx, "z"]) if prev_idx in bb.index else None
        prev_pos = _safe_float(bb.loc[prev_idx, "pos"]) if prev_idx in bb.index else None

        if prev_price is not None and prev_price > 0 and last_price is not None:
            d_price_1d = (last_price / float(prev_price)) - 1.0
        if prev_z is not None:
            d_z_1d = z - float(prev_z)
        if prev_pos is not None:
            d_pos_1d = pos_in_band - float(prev_pos)

    # last 5 BB-valid days mini table
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
        bkt = _safe_bucket(zz) if zz is not None else "UNKNOWN"
        tail_rows.append({"date": d, "price_usd": p, "z": zz, "pos": pp, "bucket": bkt, "dist_to_upper": dist_u})

    def _slice_line(name: str, s: Dict[str, Any]) -> str:
        return (
            f"- {name}: p50={fmt_pct(s.get('p50'))}, p10={fmt_pct(s.get('p10'))}, "
            f"min={fmt_pct(s.get('min'))}, n={s.get('n')}, conf={s.get('conf')}, conf_decision={s.get('conf_decision')}"
        )

    R: List[str] = []
    R.append(f"# {args.ticker} BB Monitor Report ({args.ticker} + optional USD/TWD)")
    R.append("")
    R.append(f"- report_generated_at_utc: `{generated_at_utc}`")
    R.append(f"- data_date: `{last_date}`")
    R.append(f"- price_mode: `{price_mode}`")
    R.append(f"- params: `BB({args.window},{args.k}) on log(price)`, `forward_mdd({args.forward_days}D)`")
    R.append("")

    R.append("## 15秒摘要")
    R.append(
        f"- **{args.ticker}** ({last_date} price_usd={fmt_money(last_price, 4)}) → **{bucket}** "
        f"(z={fmt_num(z, 4)}, pos={fmt_num(pos_in_band, 4)}); dist_to_lower={fmt_pct(dist_to_lower)}; dist_to_upper={fmt_pct(dist_to_upper)}; "
        f"{args.forward_days}D forward_mdd: p50={fmt_pct(mdd_stats_bucket.get('p50'))}, p10={fmt_pct(mdd_stats_bucket.get('p10'))}, min={fmt_pct(mdd_stats_bucket.get('min'))} "
        f"(n={mdd_stats_bucket.get('n')}, conf={mdd_stats_bucket.get('conf')}, conf_decision={mdd_stats_bucket.get('conf_decision')}, min_n_required={mdd_stats_bucket.get('min_n_required')})"
    )
    R.append("")

    R.append("## Forward MDD slices（摘要）")
    R.append("（閱讀用；不替換 bucket-conditioned 主統計。conf_decision 低於 OK 時，樣本數不足以作決策依據。）")
    R.append(_slice_line(f"pos>={args.pos_hint_threshold:.2f}", mdd_stats_pos))
    R.append(_slice_line(f"dist_to_upper<={args.dist_upper_hint_threshold*100:.1f}%", mdd_stats_distu))
    R.append(_slice_line(f"bucket={bucket} ∩ pos>={args.pos_hint_threshold:.2f}", mdd_stats_pos_in_bucket))
    R.append(_slice_line(f"bucket={bucket} ∩ dist_to_upper<={args.dist_upper_hint_threshold*100:.1f}%", mdd_stats_distu_in_bucket))
    R.append("")

    R.append("## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）")
    if prev_date is None:
        R.append("- Δ1D: `NA`（資料不足：至少需要 2 個可計算 BB 的交易日）")
    else:
        R.append(f"- prev_bb_date: `{prev_date}`")
        R.append(f"- Δprice_1d: {fmt_pct(d_price_1d)}")
        R.append(f"- Δz_1d: {fmt_num(d_z_1d, 4)}")
        R.append(f"- Δpos_1d: {fmt_num(d_pos_1d, 4)}")
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

    R.append("## 近 5 日（可計算 BB 的交易日；小表）")
    R.append("")
    if not tail_rows:
        R.append("- `NA`（無可計算 BB 的資料）")
    else:
        R.append("| date | price_usd | z | pos | bucket | dist_to_upper |")
        R.append("|---|---:|---:|---:|---|---:|")
        for tr in tail_rows:
            R.append(
                f"| {tr['date']} | {fmt_money(tr['price_usd'], 4)} | {fmt_num(tr['z'], 4)} | {fmt_num(tr['pos'], 4)} | {tr['bucket']} | {fmt_pct(tr['dist_to_upper'])} |"
            )
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

    R.append("## Notes")
    R.append("- conf 是「樣本數分級的統計信心」；conf_decision 是「是否足夠用於決策」的門檻判定。")
    R.append("- conf_decision: OK 表示 n>=min_n_required；LOW_FOR_DECISION 表示樣本不足但可閱讀；NA 表示完全無樣本。")
    R.append("- FX strict 只接受同日對齊；來源優先 fx_history，其次 fx_latest 同日 fallback。")
    R.append("- FX reference 只在 strict 缺值時提供，且永不回填 strict 欄位。")
    R.append("")

    _write_text(report_path, "\n".join(R))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())