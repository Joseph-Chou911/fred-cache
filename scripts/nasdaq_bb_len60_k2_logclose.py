#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nasdaq_bb_len60_k2_logclose.py

Audit-first Nasdaq risk monitor using Bollinger Bands (BB).
- PRICE: QQQ from Stooq
- VOL:   VXN from Cboe (best-effort) with fallback to FRED

Enhancements:
- VOL action_output now also uses position_in_band >= 0.80 to trigger WATCH (Suggestion 1B),
  guarded by a minimum bandwidth_pct to avoid narrow-band false positives.

Notes:
- PRICE conditional stat: forward_mdd (<= 0 by construction)
- VOL conditional stats:
    (A) low-vol regime (z <= z_thresh_low):  forward_max_runup (>= 0)
    (B) high-vol regime (z >= z_thresh_high): forward_max_runup (>= 0)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


# ---------------------------
# Utilities
# ---------------------------

def _utc_now_iso() -> str:
    return pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _http_get(url: str, timeout: int = 30, max_retries: int = 3, backoff_s: float = 1.5) -> bytes:
    last_err = None
    headers = {"User-Agent": "risk-dashboard-bb-script/3.1"}
    for i in range(max_retries):
        try:
            r = requests.get(url, timeout=timeout, headers=headers)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            return r.content
        except Exception as e:
            last_err = e
            if i < max_retries - 1:
                time.sleep(backoff_s * (i + 1))
    raise RuntimeError(f"GET failed after {max_retries} retries: {url}\nLast error: {last_err}")


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    from io import BytesIO
    try:
        return pd.read_csv(BytesIO(content))
    except UnicodeDecodeError:
        return pd.read_csv(BytesIO(content), encoding="latin-1")


def _pick_date_col(df: pd.DataFrame) -> str:
    candidates = [c for c in df.columns if str(c).strip().lower() in ("date", "trade date", "timestamp", "observation_date", "date ")]
    if candidates:
        return candidates[0]
    for c in df.columns:
        if "date" in str(c).strip().lower():
            return c
    raise ValueError(f"Cannot find a date column in columns={list(df.columns)[:10]}...")


def _pick_value_col(df: pd.DataFrame) -> str:
    for name in ("close", "closing", "value", "close value", "vix close", "vxn close", "close "):
        for c in df.columns:
            if str(c).strip().lower() == name:
                return c

    close_like = [c for c in df.columns if "close" in str(c).strip().lower()]
    if close_like:
        close_like.sort(key=lambda x: len(str(x)))
        return close_like[0]

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if numeric_cols:
        return numeric_cols[-1]

    raise ValueError(f"Cannot find a close/value column in columns={list(df.columns)[:10]}...")


def _coerce_series_df(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)

    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    out = out.dropna(subset=[value_col])

    out = out[~out.index.duplicated(keep="last")]
    out = out.rename(columns={value_col: "close"})
    return out[["close"]]


def _safe_float(x, default=None):
    try:
        if x is None:
            return default
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return default
        return v
    except Exception:
        return default


# ---------------------------
# Data sources
# ---------------------------

def fetch_stooq_daily(ticker: str) -> Tuple[pd.DataFrame, Dict]:
    sym = urllib.parse.quote_plus(ticker.lower())
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    content = _http_get(url)
    raw = _read_csv_bytes(content)

    date_col = _pick_date_col(raw)
    value_col = _pick_value_col(raw)
    df = _coerce_series_df(raw, date_col=date_col, value_col=value_col)

    meta = {
        "source": "stooq",
        "url": url,
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df.index.min().date()),
        "max_date": str(df.index.max().date()),
    }
    return df, meta


def fetch_fred_daily(series_id: str) -> Tuple[pd.DataFrame, Dict]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    content = _http_get(url)
    raw = _read_csv_bytes(content)

    date_col = "DATE" if "DATE" in raw.columns else _pick_date_col(raw)
    if series_id in raw.columns:
        value_col = series_id
    else:
        value_col = _pick_value_col(raw)

    df = raw[[date_col, value_col]].copy()
    df = _coerce_series_df(df, date_col=date_col, value_col=value_col)

    meta = {
        "source": "fred",
        "url": url,
        "series_id": series_id,
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df.index.min().date()),
        "max_date": str(df.index.max().date()),
    }
    return df, meta


def fetch_cboe_daily_prices(index_code: str) -> Tuple[pd.DataFrame, Dict]:
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{index_code.upper()}_History.csv"
    content = _http_get(url)
    raw = _read_csv_bytes(content)

    date_col = _pick_date_col(raw)
    value_col = _pick_value_col(raw)
    df = _coerce_series_df(raw, date_col=date_col, value_col=value_col)

    meta = {
        "source": "cboe",
        "url": url,
        "index_code": index_code.upper(),
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df.index.min().date()),
        "max_date": str(df.index.max().date()),
    }
    return df, meta


# ---------------------------
# Bollinger calculations
# ---------------------------

@dataclasses.dataclass(frozen=True)
class BBParams:
    length: int = 60
    k: float = 2.0
    use_log: bool = True
    ddof: int = 0


def compute_bollinger(df: pd.DataFrame, params: BBParams) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("df must have a 'close' column")

    out = df.copy().sort_index()

    if params.use_log:
        if (out["close"] <= 0).any():
            raise ValueError("Found non-positive close while use_log=True")
        out["x"] = np.log(out["close"].astype(float))
    else:
        out["x"] = out["close"].astype(float)

    w = int(params.length)
    if w < 2:
        raise ValueError("length must be >= 2")

    out["ma"] = out["x"].rolling(window=w, min_periods=w).mean()
    out["sd"] = out["x"].rolling(window=w, min_periods=w).std(ddof=int(params.ddof))

    out["upper_x"] = out["ma"] + params.k * out["sd"]
    out["lower_x"] = out["ma"] - params.k * out["sd"]

    if params.use_log:
        out["mid_price"] = np.exp(out["ma"])
        out["upper_price"] = np.exp(out["upper_x"])
        out["lower_price"] = np.exp(out["lower_x"])
    else:
        out["mid_price"] = out["ma"]
        out["upper_price"] = out["upper_x"]
        out["lower_price"] = out["lower_x"]

    out["z"] = (out["x"] - out["ma"]) / out["sd"]
    out["bandwidth_pct"] = (out["upper_price"] - out["lower_price"]) / out["mid_price"]

    close = out["close"].to_numpy(dtype=float)
    lower = out["lower_price"].to_numpy(dtype=float)
    upper = out["upper_price"].to_numpy(dtype=float)

    walk_lower = np.zeros(len(out), dtype=int)
    walk_upper = np.zeros(len(out), dtype=int)

    for i in range(len(out)):
        if np.isfinite(lower[i]) and np.isfinite(close[i]) and close[i] <= lower[i]:
            walk_lower[i] = (walk_lower[i - 1] + 1) if i > 0 else 1
        else:
            walk_lower[i] = 0

        if np.isfinite(upper[i]) and np.isfinite(close[i]) and close[i] >= upper[i]:
            walk_upper[i] = (walk_upper[i - 1] + 1) if i > 0 else 1
        else:
            walk_upper[i] = 0

    out["walk_lower_count"] = walk_lower
    out["walk_upper_count"] = walk_upper

    return out


# ---------------------------
# Forward metrics
# ---------------------------

def forward_mdd(close_window: np.ndarray) -> float:
    if close_window.size < 1:
        return np.nan
    c0 = close_window[0]
    m = np.min(close_window)
    return float(m / c0 - 1.0)


def forward_max_runup(close_window: np.ndarray) -> float:
    if close_window.size < 1:
        return np.nan
    c0 = close_window[0]
    m = np.max(close_window)
    return float(m / c0 - 1.0)


def _pick_event_positions_le(z: np.ndarray, thresh: float, cooldown: int) -> List[int]:
    pos = []
    i = 0
    n = len(z)
    cd = max(1, int(cooldown))
    while i < n:
        if np.isfinite(z[i]) and z[i] <= thresh:
            pos.append(i)
            i += cd
        else:
            i += 1
    return pos


def _pick_event_positions_ge(z: np.ndarray, thresh: float, cooldown: int) -> List[int]:
    pos = []
    i = 0
    n = len(z)
    cd = max(1, int(cooldown))
    while i < n:
        if np.isfinite(z[i]) and z[i] >= thresh:
            pos.append(i)
            i += cd
        else:
            i += 1
    return pos


def _summarize(values: List[float], metric: str, interpretation: str, z_thresh: float, horizon: int, cooldown: int) -> Dict:
    if len(values) == 0:
        return {
            "metric": metric,
            "metric_interpretation": interpretation,
            "z_thresh": z_thresh,
            "horizon_days": horizon,
            "cooldown_bars": cooldown,
            "sample_size": 0,
            "p50": None,
            "p90": None,
            "mean": None,
            "min": None,
            "max": None,
        }
    arr = np.array(values, dtype=float)
    return {
        "metric": metric,
        "metric_interpretation": interpretation,
        "z_thresh": z_thresh,
        "horizon_days": horizon,
        "cooldown_bars": cooldown,
        "sample_size": int(arr.size),
        "p50": float(np.nanpercentile(arr, 50)),
        "p90": float(np.nanpercentile(arr, 90)),
        "mean": float(np.nanmean(arr)),
        "min": float(np.nanmin(arr)),
        "max": float(np.nanmax(arr)),
    }


def conditional_stats_price_mdd(df_bb: pd.DataFrame, z_thresh: float, horizon: int, cooldown: int) -> Dict:
    df = df_bb.dropna(subset=["z", "close"]).copy()
    close = df["close"].to_numpy(dtype=float)
    z = df["z"].to_numpy(dtype=float)

    trig_pos = _pick_event_positions_le(z=z, thresh=z_thresh, cooldown=cooldown)
    vals: List[float] = []
    for i in trig_pos:
        j = min(i + horizon, len(close) - 1)
        vals.append(forward_mdd(close[i: j + 1]))

    return _summarize(
        values=vals,
        metric="forward_mdd",
        interpretation="<=0; closer to 0 is less pain; more negative is deeper drawdown",
        z_thresh=z_thresh,
        horizon=horizon,
        cooldown=cooldown,
    )


def conditional_stats_runup_le(df_bb: pd.DataFrame, z_thresh: float, horizon: int, cooldown: int) -> Dict:
    df = df_bb.dropna(subset=["z", "close"]).copy()
    close = df["close"].to_numpy(dtype=float)
    z = df["z"].to_numpy(dtype=float)

    trig_pos = _pick_event_positions_le(z=z, thresh=z_thresh, cooldown=cooldown)
    vals: List[float] = []
    for i in trig_pos:
        j = min(i + horizon, len(close) - 1)
        vals.append(forward_max_runup(close[i: j + 1]))

    return _summarize(
        values=vals,
        metric="forward_max_runup",
        interpretation=">=0; larger means bigger spike risk",
        z_thresh=z_thresh,
        horizon=horizon,
        cooldown=cooldown,
    )


def conditional_stats_runup_ge(df_bb: pd.DataFrame, z_thresh: float, horizon: int, cooldown: int) -> Dict:
    df = df_bb.dropna(subset=["z", "close"]).copy()
    close = df["close"].to_numpy(dtype=float)
    z = df["z"].to_numpy(dtype=float)

    trig_pos = _pick_event_positions_ge(z=z, thresh=z_thresh, cooldown=cooldown)
    vals: List[float] = []
    for i in trig_pos:
        j = min(i + horizon, len(close) - 1)
        vals.append(forward_max_runup(close[i: j + 1]))

    return _summarize(
        values=vals,
        metric="forward_max_runup",
        interpretation=">=0; larger means further spike continuation risk",
        z_thresh=z_thresh,
        horizon=horizon,
        cooldown=cooldown,
    )


# ---------------------------
# Latest derived fields
# ---------------------------

def _latest_derived(latest: pd.Series) -> Dict:
    close = _safe_float(latest.get("close"))
    lower = _safe_float(latest.get("lower_price"))
    upper = _safe_float(latest.get("upper_price"))
    z = _safe_float(latest.get("z"))
    bw = _safe_float(latest.get("bandwidth_pct"))
    walk_l = int(_safe_float(latest.get("walk_lower_count"), 0) or 0)
    walk_u = int(_safe_float(latest.get("walk_upper_count"), 0) or 0)

    dist_lower = None
    dist_upper = None
    pos_in_band = None

    if close is not None and close > 0 and lower is not None:
        dist_lower = float((close - lower) / close * 100.0)
    if close is not None and close > 0 and upper is not None:
        dist_upper = float((upper - close) / close * 100.0)

    if lower is not None and upper is not None and close is not None and upper > lower:
        pos_in_band = float((close - lower) / (upper - lower))
        pos_in_band = float(np.clip(pos_in_band, 0.0, 1.0))

    return {
        "close": close,
        "bb_mid": _safe_float(latest.get("mid_price")),
        "bb_lower": lower,
        "bb_upper": upper,
        "z": z,
        "trigger_z_le_-2": (z is not None and z <= -2.0),
        "trigger_z_ge_2": (z is not None and z >= 2.0),
        "distance_to_lower_pct": dist_lower,
        "distance_to_upper_pct": dist_upper,
        "position_in_band": pos_in_band,
        "bandwidth_pct": bw,
        "walk_lower_count": walk_l,
        "walk_upper_count": walk_u,
    }


# ---------------------------
# Action label (guardrail)
# ---------------------------

def decide_action_price(latest: pd.Series, bw_delta_pct: Optional[float]) -> str:
    z = _safe_float(latest.get("z"))
    walk_lower = int(_safe_float(latest.get("walk_lower_count"), 0) or 0)

    if z is None:
        return "INSUFFICIENT_DATA"

    if walk_lower >= 3:
        return "LOCKOUT_WALKING_LOWER_BAND (DO_NOT_CATCH_FALLING_KNIFE)"

    if bw_delta_pct is not None and bw_delta_pct >= 10.0 and z <= -2.0:
        return "LOCKOUT_VOL_EXPANSION_AT_LOWER (WAIT)"

    if z <= -3.0:
        return "EXTREME_TAIL_RISK (WAIT)"
    if z <= -2.0:
        return "LOWER_BAND_TOUCH (MONITOR / SCALE_IN_ONLY)"
    if z <= -1.5:
        return "NEAR_LOWER_BAND (MONITOR)"
    return "NORMAL_RANGE"


def _position_in_band_from_row(latest: pd.Series) -> Optional[float]:
    close = _safe_float(latest.get("close"))
    lower = _safe_float(latest.get("lower_price"))
    upper = _safe_float(latest.get("upper_price"))
    if close is None or lower is None or upper is None:
        return None
    if upper <= lower:
        return None
    pos = (close - lower) / (upper - lower)
    return float(np.clip(pos, 0.0, 1.0))


def decide_action_vol(
    latest: pd.Series,
    bw_delta_pct: Optional[float],
    pos_watch_threshold: float = 0.80,         # Suggestion 1(B)
    min_bandwidth_pct: float = 0.05,           # guard: avoid ultra-narrow band false positives
) -> str:
    z = _safe_float(latest.get("z"))
    bw = _safe_float(latest.get("bandwidth_pct"))
    pos = _position_in_band_from_row(latest)

    walk_upper = int(_safe_float(latest.get("walk_upper_count"), 0) or 0)

    if z is None:
        return "INSUFFICIENT_DATA"

    if walk_upper >= 3:
        return "STRESS_LOCKOUT_WALKING_UPPER_BAND (RISK_HIGH)"

    if bw_delta_pct is not None and bw_delta_pct >= 10.0 and z >= 2.0:
        return "STRESS_VOL_EXPANSION (RISK_HIGH)"

    if z >= 3.0:
        return "EXTREME_VOL_SPIKE_ZONE (RISK_HIGH)"
    if z >= 2.0:
        return "UPPER_BAND_TOUCH (STRESS)"

    # --- Suggestion 1(B): position-based WATCH ---
    # If price sits high within band (>=0.80), trigger WATCH even if z < 1.5,
    # but only when band is not trivially narrow.
    if pos is not None and pos >= pos_watch_threshold and (bw is None or bw >= min_bandwidth_pct):
        return "NEAR_UPPER_BAND (WATCH)"

    if z >= 1.5:
        return "NEAR_UPPER_BAND (WATCH)"

    if z <= -3.0:
        return "EXTREME_LOW_VOL_ZONE (COMPLACENCY)"
    if z <= -2.0:
        return "LOWER_BAND_TOUCH (COMPLACENCY)"
    if z <= -1.5:
        return "NEAR_LOWER_BAND (COMPLACENCY_WATCH)"

    return "NORMAL_RANGE"


# ---------------------------
# Build snippet JSON
# ---------------------------

def build_snippet(
    name: str,
    df_bb: pd.DataFrame,
    params: BBParams,
    meta: Dict,
    series_kind: str,
    hist: Dict,
) -> Dict:
    df = df_bb.dropna(subset=["ma", "sd", "upper_price", "lower_price", "z"]).copy()
    if df.empty:
        return {
            "name": name,
            "status": "INSUFFICIENT_DATA",
            "meta": meta,
            "params": dataclasses.asdict(params),
            "generated_at_utc": _utc_now_iso(),
        }

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    bw_delta_pct = None
    if prev is not None:
        prev_bw = _safe_float(prev.get("bandwidth_pct"))
        cur_bw = _safe_float(latest.get("bandwidth_pct"))
        if prev_bw is not None and cur_bw is not None and prev_bw != 0:
            bw_delta_pct = float((cur_bw / prev_bw - 1.0) * 100.0)

    latest_pack = {
        "date": str(latest.name.date()),
        **_latest_derived(latest),
        "bandwidth_delta_pct": bw_delta_pct,
    }

    if series_kind == "price":
        action = decide_action_price(latest, bw_delta_pct)
    elif series_kind == "vol":
        action = decide_action_vol(latest, bw_delta_pct)
    else:
        action = "UNKNOWN_SERIES_KIND"

    return {
        "name": name,
        "generated_at_utc": _utc_now_iso(),
        "meta": meta,
        "params": dataclasses.asdict(params),
        "latest": latest_pack,
        "historical_simulation": hist,
        "action_output": action,
    }


# ---------------------------
# CLI / Main
# ---------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Nasdaq BB(60,2) monitor (logclose): QQQ + optional VXN (Cboe/FRED)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--price_ticker", default="qqq.us", help="Stooq ticker for price series (default: qqq.us)")

    p.add_argument("--vxn_enable", action="store_true")
    p.add_argument("--vxn_source", choices=["cboe_first", "fred_first"], default="fred_first")
    p.add_argument("--vxn_code", default="VXN", help="Cboe index code for CSV attempt (default: VXN)")
    p.add_argument("--vxn_fred_series", default="VXNCLS", help="FRED series id (default: VXNCLS)")

    p.add_argument("--bb_len", type=int, default=60)
    p.add_argument("--bb_k", type=float, default=2.0)
    p.add_argument("--use_log", action="store_true", default=True)
    p.add_argument("--no_log", action="store_true")
    p.add_argument("--ddof", type=int, choices=[0, 1], default=0)

    p.add_argument("--z_thresh", type=float, default=-2.0, help="PRICE trigger: z <= z_thresh")
    p.add_argument("--z_thresh_low", type=float, default=-2.0, help="VOL(A) trigger: z <= z_thresh_low")
    p.add_argument("--z_thresh_high", type=float, default=2.0, help="VOL(B) trigger: z >= z_thresh_high")

    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--cooldown", type=int, default=20)

    p.add_argument("--out_dir", default="nasdaq_bb_cache")
    p.add_argument("--quiet", action="store_true")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    use_log = bool(args.use_log) and (not bool(args.no_log))
    params = BBParams(length=args.bb_len, k=args.bb_k, use_log=use_log, ddof=args.ddof)

    _ensure_dir(args.out_dir)

    # PRICE: QQQ
    price_df, price_meta = fetch_stooq_daily(args.price_ticker)
    price_bb = compute_bollinger(price_df, params)

    price_hist = conditional_stats_price_mdd(
        price_bb,
        z_thresh=args.z_thresh,
        horizon=args.horizon,
        cooldown=args.cooldown,
    )

    price_snippet = build_snippet(
        name=f"QQQ_BB(len={params.length},k={params.k},log={params.use_log})",
        df_bb=price_bb,
        params=params,
        meta=price_meta,
        series_kind="price",
        hist=price_hist,
    )

    price_json_path = os.path.join(args.out_dir, "snippet_price_qqq.json")
    with open(price_json_path, "w", encoding="utf-8") as f:
        json.dump(price_snippet, f, ensure_ascii=False, indent=2)

    price_csv_path = os.path.join(args.out_dir, "tail_price_qqq.csv")
    price_bb.tail(200).to_csv(price_csv_path, index=True)

    if not args.quiet:
        print("=== PRICE SNIPPET (QQQ) ===")
        print(json.dumps(price_snippet, ensure_ascii=False, indent=2))

    # VOL: VXN (optional)
    if args.vxn_enable:
        vxn_df = None
        vxn_meta = None
        attempt_errors: List[str] = []

        order = ["cboe", "fred"] if args.vxn_source == "cboe_first" else ["fred", "cboe"]
        selected_source = None

        for src in order:
            try:
                if src == "cboe":
                    vxn_df, vxn_meta = fetch_cboe_daily_prices(args.vxn_code)
                else:
                    vxn_df, vxn_meta = fetch_fred_daily(args.vxn_fred_series)
                selected_source = src
                break
            except Exception as e:
                attempt_errors.append(f"{src}: {e}")

        if vxn_df is None or vxn_meta is None or selected_source is None:
            raise RuntimeError("Failed to fetch VXN from all sources:\n" + "\n".join(attempt_errors))

        vxn_meta2 = {
            "attempt_errors": attempt_errors,
            "selected_source": selected_source,
            "fallback_used": (selected_source != order[0]),
            **vxn_meta,
        }

        vxn_bb = compute_bollinger(vxn_df, params)

        vxn_hist_low = conditional_stats_runup_le(
            vxn_bb,
            z_thresh=args.z_thresh_low,
            horizon=args.horizon,
            cooldown=args.cooldown,
        )
        vxn_hist_high = conditional_stats_runup_ge(
            vxn_bb,
            z_thresh=args.z_thresh_high,
            horizon=args.horizon,
            cooldown=args.cooldown,
        )

        vxn_hist = {
            "A_lowvol": vxn_hist_low,
            "B_highvol": vxn_hist_high,
        }

        vxn_snippet = build_snippet(
            name=f"VXN_BB(len={params.length},k={params.k},log={params.use_log})",
            df_bb=vxn_bb,
            params=params,
            meta=vxn_meta2,
            series_kind="vol",
            hist=vxn_hist,
        )

        vxn_json_path = os.path.join(args.out_dir, "snippet_vxn.json")
        with open(vxn_json_path, "w", encoding="utf-8") as f:
            json.dump(vxn_snippet, f, ensure_ascii=False, indent=2)

        vxn_csv_path = os.path.join(args.out_dir, "tail_vxn.csv")
        vxn_bb.tail(200).to_csv(vxn_csv_path, index=True)

        if not args.quiet:
            print("\n=== VOL SNIPPET (VXN) ===")
            print(json.dumps(vxn_snippet, ensure_ascii=False, indent=2))

    if not args.quiet:
        print("\nWrote:")
        print(f"- {price_json_path}")
        print(f"- {price_csv_path}")
        if args.vxn_enable:
            print(f"- {os.path.join(args.out_dir, 'snippet_vxn.json')}")
            print(f"- {os.path.join(args.out_dir, 'tail_vxn.csv')}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)