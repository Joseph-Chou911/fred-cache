#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nasdaq_bb_len60_k2_logclose.py

Outputs (under out_dir/cache_dir):
- snippet_price_qqq.json
- snippet_vxn.json (optional; when --vxn_enable)

This version adds argparse aliases to match existing workflow calls, including:
--price_ticker, --out_dir, --vxn_enable, --vxn_code, --bb_len, --bb_k,
--z_thresh, --z_thresh_low, --z_thresh_high, --quiet

And keeps backward compatibility with:
--cache_dir, --length, --k, --qqq_url, --vxn_source, etc.

VXN snippet additions:
- active_regime: "A_lowvol" | "B_highvol" | "NONE"
- tail_B_applicable: bool (True only when active_regime == "B_highvol")
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests


# ----------------------------
# Utilities
# ----------------------------

def utc_now_iso() -> str:
    return pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except Exception:
        return None


def quantile_safe(s: pd.Series, q: float) -> Optional[float]:
    if s is None or len(s) == 0:
        return None
    try:
        return float(s.quantile(q))
    except Exception:
        return None


def stooq_daily_url(ticker: str) -> str:
    # e.g. qqq.us -> https://stooq.com/q/d/l/?s=qqq.us&i=d
    return f"https://stooq.com/q/d/l/?s={ticker}&i=d"


def cboe_daily_url(code: str) -> str:
    # e.g. VXN -> https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv
    c = code.strip().upper()
    return f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{c}_History.csv"


def default_fred_series_for_vxn_code(code: str) -> str:
    # for VXN, common fred series is VXNCLS
    c = code.strip().upper()
    if c == "VXN":
        return "VXNCLS"
    # fallback: user should pass explicit --vxn_fred_series if not VXN
    return f"{c}CLS"


# ----------------------------
# Fetchers
# ----------------------------

@dataclass
class FetchResult:
    ok: bool
    df: Optional[pd.DataFrame]
    meta: Dict[str, Any]
    errors: List[str]


def fetch_csv(url: str, timeout: int = 20, retries: int = 3, backoff_sec: float = 1.5) -> Tuple[Optional[str], List[str]]:
    errors: List[str] = []
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code != 200:
                errors.append(f"http_status={r.status_code}")
                time.sleep(backoff_sec * (i + 1))
                continue
            return r.text, errors
        except Exception as e:
            errors.append(f"exception={type(e).__name__}:{e}")
            time.sleep(backoff_sec * (i + 1))
    return None, errors


def parse_stooq_daily(csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    df.rename(columns={"Date": "date", "Close": "close"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    df["date"] = df["date"].dt.date.astype(str)
    return df[["date", "close"]].reset_index(drop=True)


def parse_fred(csv_text: str, series_id: str) -> pd.DataFrame:
    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    date_col = "observation_date"
    val_col = series_id
    df.rename(columns={date_col: "date", val_col: "close"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    df["date"] = df["date"].dt.date.astype(str)
    return df[["date", "close"]].reset_index(drop=True)


def parse_cboe_vxn(csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    col_map = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl == "date":
            col_map[c] = "date"
        if cl == "close":
            col_map[c] = "close"
    df.rename(columns=col_map, inplace=True)

    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError(f"Unexpected CBOE columns: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    df["date"] = df["date"].dt.date.astype(str)
    return df[["date", "close"]].reset_index(drop=True)


def fetch_qqq_stooq(url: str, timeout: int, retries: int) -> FetchResult:
    txt, errs = fetch_csv(url, timeout=timeout, retries=retries)
    meta = {"source": "stooq", "url": url, "date_col": "date", "value_col": "close"}
    if txt is None:
        return FetchResult(False, None, meta, errs)
    try:
        df = parse_stooq_daily(txt)
        meta.update({
            "rows": int(len(df)),
            "min_date": df["date"].iloc[0] if len(df) else None,
            "max_date": df["date"].iloc[-1] if len(df) else None,
        })
        return FetchResult(True, df, meta, errs)
    except Exception as e:
        errs.append(f"parse_error={type(e).__name__}:{e}")
        return FetchResult(False, None, meta, errs)


def fetch_vxn_cboe(url: str, timeout: int, retries: int) -> FetchResult:
    txt, errs = fetch_csv(url, timeout=timeout, retries=retries)
    meta = {"source": "cboe", "url": url, "date_col": "date", "value_col": "close"}
    if txt is None:
        return FetchResult(False, None, meta, errs)
    try:
        df = parse_cboe_vxn(txt)
        meta.update({
            "rows": int(len(df)),
            "min_date": df["date"].iloc[0] if len(df) else None,
            "max_date": df["date"].iloc[-1] if len(df) else None,
        })
        return FetchResult(True, df, meta, errs)
    except Exception as e:
        errs.append(f"parse_error={type(e).__name__}:{e}")
        return FetchResult(False, None, meta, errs)


def fetch_vxn_fred(series_id: str, url: str, timeout: int, retries: int) -> FetchResult:
    txt, errs = fetch_csv(url, timeout=timeout, retries=retries)
    meta = {
        "source": "fred",
        "url": url,
        "series_id": series_id,
        "date_col": "observation_date",
        "value_col": series_id,
    }
    if txt is None:
        return FetchResult(False, None, meta, errs)
    try:
        df = parse_fred(txt, series_id=series_id)
        meta.update({
            "rows": int(len(df)),
            "min_date": df["date"].iloc[0] if len(df) else None,
            "max_date": df["date"].iloc[-1] if len(df) else None,
        })
        return FetchResult(True, df, meta, errs)
    except Exception as e:
        errs.append(f"parse_error={type(e).__name__}:{e}")
        return FetchResult(False, None, meta, errs)


# ----------------------------
# Bollinger + Metrics
# ----------------------------

def compute_bb(df: pd.DataFrame, length: int, k: float, use_log: bool, ddof: int) -> pd.DataFrame:
    out = df.copy()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"]).reset_index(drop=True)

    if use_log:
        out["x"] = out["close"].apply(lambda v: math.log(v) if v > 0 else float("nan"))
    else:
        out["x"] = out["close"]

    out["mid_x"] = out["x"].rolling(length, min_periods=length).mean()
    out["std_x"] = out["x"].rolling(length, min_periods=length).std(ddof=ddof)
    out["lower_x"] = out["mid_x"] - k * out["std_x"]
    out["upper_x"] = out["mid_x"] + k * out["std_x"]

    if use_log:
        out["bb_mid"] = out["mid_x"].apply(lambda v: math.exp(v) if pd.notna(v) else float("nan"))
        out["bb_lower"] = out["lower_x"].apply(lambda v: math.exp(v) if pd.notna(v) else float("nan"))
        out["bb_upper"] = out["upper_x"].apply(lambda v: math.exp(v) if pd.notna(v) else float("nan"))
    else:
        out["bb_mid"] = out["mid_x"]
        out["bb_lower"] = out["lower_x"]
        out["bb_upper"] = out["upper_x"]

    out["z"] = (out["x"] - out["mid_x"]) / out["std_x"]

    out["bandwidth_pct"] = (out["bb_upper"] - out["bb_lower"]) / out["bb_mid"]
    out["bandwidth_delta_pct"] = (out["bandwidth_pct"] / out["bandwidth_pct"].shift(1) - 1.0) * 100.0

    out["distance_to_lower_pct"] = (out["close"] - out["bb_lower"]) / out["close"] * 100.0
    out["distance_to_upper_pct"] = (out["bb_upper"] - out["close"]) / out["close"] * 100.0

    denom = (out["bb_upper"] - out["bb_lower"])
    out["position_in_band"] = (out["close"] - out["bb_lower"]) / denom.replace(0, float("nan"))

    return out


def walk_count(series_x: pd.Series, band_x: pd.Series, direction: str) -> int:
    if len(series_x) == 0:
        return 0
    cnt = 0
    for x, b in zip(series_x[::-1], band_x[::-1]):
        if pd.isna(x) or pd.isna(b):
            break
        if direction == "lower":
            if x <= b:
                cnt += 1
            else:
                break
        else:
            if x >= b:
                cnt += 1
            else:
                break
    return cnt


def events_with_cooldown(mask: pd.Series, cooldown: int) -> List[int]:
    idxs: List[int] = []
    i = 0
    n = len(mask)
    while i < n:
        if bool(mask.iloc[i]):
            idxs.append(i)
            i += cooldown
        else:
            i += 1
    return idxs


def forward_mdd(close: pd.Series, start_idx: int, horizon: int) -> Optional[float]:
    if start_idx >= len(close):
        return None
    entry = safe_float(close.iloc[start_idx])
    if entry is None or entry <= 0:
        return None
    end = min(len(close) - 1, start_idx + horizon)
    if end <= start_idx:
        return None
    fwd = close.iloc[start_idx + 1 : end + 1]
    fwd = pd.to_numeric(fwd, errors="coerce").dropna()
    if len(fwd) == 0:
        return None
    m = float(fwd.min())
    return m / entry - 1.0


def forward_max_runup(close: pd.Series, start_idx: int, horizon: int) -> Optional[float]:
    if start_idx >= len(close):
        return None
    entry = safe_float(close.iloc[start_idx])
    if entry is None or entry <= 0:
        return None
    end = min(len(close) - 1, start_idx + horizon)
    if end <= start_idx:
        return None
    fwd = close.iloc[start_idx + 1 : end + 1]
    fwd = pd.to_numeric(fwd, errors="coerce").dropna()
    if len(fwd) == 0:
        return None
    m = float(fwd.max())
    return m / entry - 1.0


def summarize_series(vals: List[Optional[float]]) -> Dict[str, Any]:
    s = pd.Series([v for v in vals if v is not None], dtype="float64")
    if len(s) == 0:
        return {
            "sample_size": 0,
            "p10": None,
            "p50": None,
            "p90": None,
            "mean": None,
            "min": None,
            "max": None,
        }
    return {
        "sample_size": int(len(s)),
        "p10": quantile_safe(s, 0.10),
        "p50": quantile_safe(s, 0.50),
        "p90": quantile_safe(s, 0.90),
        "mean": float(s.mean()),
        "min": float(s.min()),
        "max": float(s.max()),
    }


# ----------------------------
# Snippet builders
# ----------------------------

def build_price_snippet(
    df: pd.DataFrame,
    meta: Dict[str, Any],
    length: int,
    k: float,
    use_log: bool,
    ddof: int,
    z_thresh: float,
    horizon_days: int,
    cooldown_bars: int,
) -> Dict[str, Any]:
    dfb = compute_bb(df, length=length, k=k, use_log=use_log, ddof=ddof)
    dfb = dfb.dropna(subset=["bb_mid", "bb_lower", "bb_upper", "z"]).reset_index(drop=True)
    if len(dfb) == 0:
        raise ValueError("Not enough data after BB computation.")

    last = dfb.iloc[-1]
    z = float(last["z"])
    trigger_z_le = bool(z <= z_thresh)

    # action_output + trigger_reason (align with your report examples)
    if z <= -2.0:
        action_output = "TOUCH_LOWER_BAND (TRIGGER)"
        trigger_reason = "z<=-2"
    elif z <= -1.5:
        action_output = "NEAR_LOWER_BAND (MONITOR)"
        trigger_reason = "z<=-1.5"
    else:
        action_output = "NORMAL_RANGE"
        trigger_reason = ""

    wl = walk_count(dfb["x"], dfb["lower_x"], direction="lower")

    mask = dfb["z"] <= z_thresh
    event_idxs = events_with_cooldown(mask, cooldown=cooldown_bars)
    mdds = [forward_mdd(dfb["close"], i, horizon=horizon_days) for i in event_idxs]

    hist = {
        "metric": "forward_mdd",
        "metric_interpretation": "<=0; closer to 0 is less pain; more negative is deeper drawdown",
        "z_thresh": float(z_thresh),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
        **summarize_series(mdds),
    }

    return {
        "name": f"QQQ_BB(len={length},k={k},log={use_log})",
        "generated_at_utc": utc_now_iso(),
        "meta": {"attempt_errors": meta.get("attempt_errors", []), **meta},
        "params": {"length": int(length), "k": float(k), "use_log": bool(use_log), "ddof": int(ddof)},
        "latest": {
            "date": str(last["date"]),
            "close": float(last["close"]),
            "bb_mid": float(last["bb_mid"]),
            "bb_lower": float(last["bb_lower"]),
            "bb_upper": float(last["bb_upper"]),
            "z": float(last["z"]),
            "trigger_z_le_-2": bool(trigger_z_le),
            "distance_to_lower_pct": float(last["distance_to_lower_pct"]),
            "distance_to_upper_pct": float(last["distance_to_upper_pct"]),
            "position_in_band": float(last["position_in_band"]),
            "bandwidth_pct": float(last["bandwidth_pct"]),
            "bandwidth_delta_pct": float(last["bandwidth_delta_pct"]),
            "walk_lower_count": int(wl),
        },
        "historical_simulation": hist,
        "action_output": action_output,
        "trigger_reason": trigger_reason,
    }


def build_vxn_snippet(
    df: pd.DataFrame,
    meta: Dict[str, Any],
    length: int,
    k: float,
    use_log: bool,
    ddof: int,
    z_low: float,
    z_high: float,
    horizon_days: int,
    cooldown_bars: int,
) -> Dict[str, Any]:
    dfb = compute_bb(df, length=length, k=k, use_log=use_log, ddof=ddof)
    dfb = dfb.dropna(subset=["bb_mid", "bb_lower", "bb_upper", "z"]).reset_index(drop=True)
    if len(dfb) == 0:
        raise ValueError("Not enough data after BB computation.")

    last = dfb.iloc[-1]
    z = float(last["z"])

    trigger_low = bool(z <= z_low)
    trigger_high = bool(z >= z_high)

    # Suggestion #2 fields
    if trigger_low:
        active_regime = "A_lowvol"
        tail_B_applicable = False
    elif trigger_high:
        active_regime = "B_highvol"
        tail_B_applicable = True
    else:
        active_regime = "NONE"
        tail_B_applicable = False

    pos = safe_float(last["position_in_band"])
    if pos is not None and pos >= 0.8:
        action_output = "NEAR_UPPER_BAND (WATCH)"
        trigger_reason = f"position_in_band>=0.8 (pos={pos:.3f})"
    elif pos is not None and pos <= 0.2:
        action_output = "NEAR_LOWER_BAND (MONITOR)"
        trigger_reason = f"position_in_band<=0.2 (pos={pos:.3f})"
    else:
        action_output = "NORMAL_RANGE"
        trigger_reason = ""

    wu = walk_count(dfb["x"], dfb["upper_x"], direction="upper")

    mask_a = dfb["z"] <= z_low
    idx_a = events_with_cooldown(mask_a, cooldown=cooldown_bars)
    runups_a = [forward_max_runup(dfb["close"], i, horizon=horizon_days) for i in idx_a]

    mask_b = dfb["z"] >= z_high
    idx_b = events_with_cooldown(mask_b, cooldown=cooldown_bars)
    runups_b = [forward_max_runup(dfb["close"], i, horizon=horizon_days) for i in idx_b]

    hist_a = {
        "metric": "forward_max_runup",
        "metric_interpretation": ">=0; larger means bigger spike risk",
        "z_thresh": float(z_low),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
        **summarize_series(runups_a),
    }
    hist_b = {
        "metric": "forward_max_runup",
        "metric_interpretation": ">=0; larger means further spike continuation risk",
        "z_thresh": float(z_high),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
        **summarize_series(runups_b),
    }

    return {
        "name": f"VXN_BB(len={length},k={k},log={use_log})",
        "generated_at_utc": utc_now_iso(),
        "meta": {"attempt_errors": meta.get("attempt_errors", []), **meta},
        "params": {"length": int(length), "k": float(k), "use_log": bool(use_log), "ddof": int(ddof)},
        "active_regime": active_regime,
        "tail_B_applicable": bool(tail_B_applicable),
        "latest": {
            "date": str(last["date"]),
            "close": float(last["close"]),
            "bb_mid": float(last["bb_mid"]),
            "bb_lower": float(last["bb_lower"]),
            "bb_upper": float(last["bb_upper"]),
            "z": float(last["z"]),
            "trigger_z_le_-2": bool(trigger_low),
            "trigger_z_ge_2": bool(trigger_high),
            "distance_to_lower_pct": float(last["distance_to_lower_pct"]),
            "distance_to_upper_pct": float(last["distance_to_upper_pct"]),
            "position_in_band": float(last["position_in_band"]),
            "bandwidth_pct": float(last["bandwidth_pct"]),
            "bandwidth_delta_pct": float(last["bandwidth_delta_pct"]),
            "walk_upper_count": int(wu),
        },
        "historical_simulation": {
            "A_lowvol": hist_a,
            "B_highvol": hist_b,
        },
        "action_output": action_output,
        "trigger_reason": trigger_reason,
    }


# ----------------------------
# Main
# ----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Compute BB for QQQ price + optional VXN vol, output snippets into cache dir.",
    )

    # Output directory (alias: --out_dir)
    p.add_argument("--cache_dir", "--out_dir", dest="cache_dir", default="nasdaq_bb_cache")

    # BB params (aliases: --bb_len, --bb_k)
    p.add_argument("--length", "--bb_len", dest="length", type=int, default=60)
    p.add_argument("--k", "--bb_k", dest="k", type=float, default=2.0)
    p.add_argument("--use_log", action="store_true", default=True)
    p.add_argument("--ddof", type=int, default=0)

    # simulation params
    p.add_argument("--horizon_days", type=int, default=20)
    p.add_argument("--cooldown_bars", type=int, default=20)

    # QQQ source:
    p.add_argument("--qqq_url", default="https://stooq.com/q/d/l/?s=qqq.us&i=d")
    p.add_argument("--price_ticker", dest="price_ticker", default=None,
                   help="If provided, overrides qqq_url to stooq daily url for this ticker (e.g. qqq.us).")

    # thresholds (aliases to match workflow)
    p.add_argument("--qqq_z_thresh", "--z_thresh", dest="qqq_z_thresh", type=float, default=-2.0)
    p.add_argument("--vxn_z_low", "--z_thresh_low", dest="vxn_z_low", type=float, default=-2.0)
    p.add_argument("--vxn_z_high", "--z_thresh_high", dest="vxn_z_high", type=float, default=2.0)

    # VXN enable + code (workflow style)
    p.add_argument("--vxn_enable", action="store_true", default=False,
                   help="Enable VXN fetch/compute. If not set, only QQQ snippet is produced.")
    p.add_argument("--vxn_code", dest="vxn_code", default="VXN",
                   help="Index code for CBOE history url pattern: {CODE}_History.csv (default VXN).")

    # VXN source preference (kept)
    p.add_argument("--vxn_source", choices=["cboe_first", "fred_first"], default="cboe_first")
    p.add_argument("--vxn_cboe_url", default=None,
                   help="If set, overrides default CBOE url derived from vxn_code.")
    p.add_argument("--vxn_fred_series", default=None,
                   help="If set, overrides default fred series (VXN -> VXNCLS).")
    p.add_argument("--vxn_fred_url", default=None,
                   help="If set, overrides default fred url.")

    # network
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--retries", type=int, default=3)

    # misc
    p.add_argument("--quiet", action="store_true", default=False)

    return p.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dir(args.cache_dir)

    # resolve QQQ url
    qqq_url = args.qqq_url
    if args.price_ticker:
        qqq_url = stooq_daily_url(args.price_ticker.strip())

    # ---- Fetch QQQ ----
    qqq_meta: Dict[str, Any] = {"attempt_errors": []}
    qqq_res = fetch_qqq_stooq(qqq_url, timeout=args.timeout, retries=args.retries)
    qqq_meta.update(qqq_res.meta)
    if not qqq_res.ok or qqq_res.df is None:
        qqq_meta["attempt_errors"].extend(qqq_res.errors)
        raise RuntimeError(f"QQQ fetch failed: {qqq_meta.get('attempt_errors')}")

    qqq_snip = build_price_snippet(
        qqq_res.df,
        meta=qqq_meta,
        length=args.length,
        k=args.k,
        use_log=args.use_log,
        ddof=args.ddof,
        z_thresh=args.qqq_z_thresh,
        horizon_days=args.horizon_days,
        cooldown_bars=args.cooldown_bars,
    )

    out_price = os.path.join(args.cache_dir, "snippet_price_qqq.json")
    with open(out_price, "w", encoding="utf-8") as f:
        json.dump(qqq_snip, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print(f"Wrote: {out_price}")

    # ---- Optional VXN ----
    if args.vxn_enable:
        vxn_code = args.vxn_code.strip().upper()

        cboe_url = args.vxn_cboe_url or cboe_daily_url(vxn_code)

        fred_series = args.vxn_fred_series or default_fred_series_for_vxn_code(vxn_code)
        fred_url = args.vxn_fred_url or f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_series}"

        vxn_attempt_errors: List[str] = []
        selected_source = None
        fallback_used = False
        vxn_df: Optional[pd.DataFrame] = None
        vxn_meta: Dict[str, Any] = {"attempt_errors": vxn_attempt_errors}

        def try_cboe():
            r = fetch_vxn_cboe(cboe_url, timeout=args.timeout, retries=args.retries)
            return r.ok, r.df, r.meta, r.errors

        def try_fred():
            r = fetch_vxn_fred(fred_series, fred_url, timeout=args.timeout, retries=args.retries)
            return r.ok, r.df, r.meta, r.errors

        order = ["cboe", "fred"] if args.vxn_source == "cboe_first" else ["fred", "cboe"]
        first = True
        for src in order:
            ok, df, meta, errs = (try_cboe() if src == "cboe" else try_fred())
            vxn_attempt_errors.extend(errs)
            if ok and df is not None:
                vxn_df = df
                vxn_meta.update(meta)
                selected_source = meta.get("source", src)
                if not first:
                    fallback_used = True
                break
            first = False

        if vxn_df is None:
            raise RuntimeError(f"VXN fetch failed: {vxn_attempt_errors}")

        vxn_meta["selected_source"] = selected_source
        vxn_meta["fallback_used"] = bool(fallback_used)

        vxn_snip = build_vxn_snippet(
            vxn_df,
            meta=vxn_meta,
            length=args.length,
            k=args.k,
            use_log=args.use_log,
            ddof=args.ddof,
            z_low=args.vxn_z_low,
            z_high=args.vxn_z_high,
            horizon_days=args.horizon_days,
            cooldown_bars=args.cooldown_bars,
        )

        out_vxn = os.path.join(args.cache_dir, "snippet_vxn.json")
        with open(out_vxn, "w", encoding="utf-8") as f:
            json.dump(vxn_snip, f, ensure_ascii=False, indent=2)

        if not args.quiet:
            print(f"Wrote: {out_vxn}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())