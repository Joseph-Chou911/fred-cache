#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nasdaq BB monitor (PRICE: QQQ; VOL: VXN) with BB(len,k) on log-close.

Outputs (under --out_dir):
- snippet_price.json
- snippet_vxn.json (if --vxn_enable)

Design goals:
- Audit-friendly: explicit meta/params/latest/simulation/action_output/trigger_reason
- Deterministic definitions:
  * forward_mdd <= 0 (clamped)
  * forward_max_runup >= 0 (clamped)
- Regime split for VXN:
  A) low-vol: z <= z_thresh_low
  B) high-vol: z >= z_thresh_high
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from urllib.request import Request, urlopen


# --------------------------
# Utilities
# --------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def download_text(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (nasdaq-bb-monitor)"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # try utf-8, fallback latin-1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def parse_csv_to_df(text: str) -> pd.DataFrame:
    # use python csv to be robust to odd quoting
    reader = csv.reader(text.splitlines())
    rows = list(reader)
    if not rows:
        raise ValueError("CSV is empty")
    header = rows[0]
    data = rows[1:]
    return pd.DataFrame(data, columns=header)


def infer_date_and_value_cols(df: pd.DataFrame, preferred_value_cols: List[str]) -> Tuple[str, str]:
    # Date candidates
    date_candidates = ["Date", "DATE", "date", "observation_date", "Observation Date", "Trade Date", "trade_date"]
    date_col = None
    for c in date_candidates:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        # heuristic: first col that parses as date for most rows
        for c in df.columns[:3]:
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().mean() > 0.8:
                date_col = c
                break
    if date_col is None:
        raise ValueError(f"Cannot infer date column from columns={list(df.columns)[:20]}")

    # Value candidates
    value_col = None
    for c in preferred_value_cols:
        if c in df.columns:
            value_col = c
            break
    if value_col is None:
        # heuristic: last numeric-like column
        best = None
        best_score = -1
        for c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            score = s.notna().mean()
            if score > best_score:
                best_score = score
                best = c
        if best is None or best_score < 0.6:
            raise ValueError(f"Cannot infer value column from columns={list(df.columns)[:20]}")
        value_col = best

    return date_col, value_col


def normalize_series_df(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    out = df[[date_col, value_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.date
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    out = out.dropna()
    out = out.sort_values(by=date_col).drop_duplicates(subset=[date_col], keep="last")
    out = out.rename(columns={date_col: "date", value_col: "close"})
    out = out.reset_index(drop=True)
    return out


def staleness_days(generated_at_utc: str, max_date_str: str) -> int:
    # computed by DATE only (not time), consistent with your report notes
    gen_date = datetime.fromisoformat(generated_at_utc.replace("Z", "+00:00")).date()
    max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
    return (gen_date - max_date).days


def staleness_flag(days: int, ok_days: int = 2) -> str:
    return "OK" if days <= ok_days else "HIGH"


def confidence_from(stale_flag: str, sample_size: int) -> str:
    if stale_flag != "OK":
        return "LOW"
    if sample_size < 30:
        return "LOW"
    if sample_size < 80:
        return "MED"
    return "HIGH"


# --------------------------
# Bollinger calculations
# --------------------------

@dataclass
class BBResult:
    df: pd.DataFrame  # date, close, mid, lower, upper, z, bandwidth_pct, bandwidth_delta_pct, pos, dist_lower_pct, dist_upper_pct, walk_lower_count, walk_upper_count


def compute_bollinger(
    series_df: pd.DataFrame,
    length: int,
    k: float,
    use_log: bool,
    ddof: int,
) -> BBResult:
    df = series_df.copy()
    close = df["close"].astype(float)

    if use_log:
        # guard against non-positive
        if (close <= 0).any():
            # drop non-positive rows (shouldn't happen for QQQ/VXN)
            df = df[close > 0].copy()
            close = df["close"].astype(float)
        x = np.log(close.to_numpy())
        x_s = pd.Series(x, index=df.index)
        mid = x_s.rolling(length).mean()
        sd = x_s.rolling(length).std(ddof=ddof)
        z = (x_s - mid) / sd

        # convert bands back to price space
        mid_p = np.exp(mid)
        upper_p = np.exp(mid + k * sd)
        lower_p = np.exp(mid - k * sd)
    else:
        x_s = close
        mid_p = x_s.rolling(length).mean()
        sd = x_s.rolling(length).std(ddof=ddof)
        z = (x_s - mid_p) / sd
        upper_p = mid_p + k * sd
        lower_p = mid_p - k * sd

    # bandwidth in fraction (not percent): (upper-lower)/mid
    bandwidth = (upper_p - lower_p) / mid_p

    # bandwidth delta pct: day-over-day percent change
    bandwidth_delta_pct = (bandwidth / bandwidth.shift(1) - 1.0) * 100.0

    # position in band [0..1] ideally
    pos = (close - lower_p) / (upper_p - lower_p)

    # distances in percent of close
    dist_lower_pct = (close - lower_p) / close * 100.0
    dist_upper_pct = (upper_p - close) / close * 100.0

    # walk counts (consecutive days)
    walk_lower = []
    walk_upper = []
    c_low = 0
    c_up = 0
    for i in range(len(df)):
        if pd.isna(lower_p.iloc[i]) or pd.isna(upper_p.iloc[i]):
            c_low = 0
            c_up = 0
        else:
            if close.iloc[i] <= lower_p.iloc[i]:
                c_low += 1
            else:
                c_low = 0
            if close.iloc[i] >= upper_p.iloc[i]:
                c_up += 1
            else:
                c_up = 0
        walk_lower.append(c_low)
        walk_upper.append(c_up)

    df["bb_mid"] = mid_p
    df["bb_lower"] = lower_p
    df["bb_upper"] = upper_p
    df["z"] = z
    df["bandwidth_pct"] = bandwidth  # fraction (0.0654 means 6.54%)
    df["bandwidth_delta_pct"] = bandwidth_delta_pct
    df["position_in_band"] = pos
    df["distance_to_lower_pct"] = dist_lower_pct
    df["distance_to_upper_pct"] = dist_upper_pct
    df["walk_lower_count"] = walk_lower
    df["walk_upper_count"] = walk_upper

    return BBResult(df=df)


# --------------------------
# Forward metrics (clamped definitions)
# --------------------------

def forward_mdd(close: pd.Series, start_idx: int, horizon: int) -> Optional[float]:
    """
    forward_mdd definition (audit):
    min(close[t+1..t+h]) / close[t] - 1, clamped to <= 0 (0 means no drawdown)
    """
    if start_idx >= len(close):
        return None
    entry = safe_float(close.iloc[start_idx])
    if entry is None or entry <= 0:
        return None
    end = min(len(close) - 1, start_idx + horizon)
    if end <= start_idx:
        return None

    fwd = pd.to_numeric(close.iloc[start_idx + 1 : end + 1], errors="coerce").dropna()
    if len(fwd) == 0:
        return None

    raw = float(fwd.min()) / entry - 1.0
    return min(0.0, raw)


def forward_max_runup(close: pd.Series, start_idx: int, horizon: int) -> Optional[float]:
    """
    forward_max_runup definition (audit):
    max(close[t+1..t+h]) / close[t] - 1, clamped to >= 0 (0 means no runup)
    """
    if start_idx >= len(close):
        return None
    entry = safe_float(close.iloc[start_idx])
    if entry is None or entry <= 0:
        return None
    end = min(len(close) - 1, start_idx + horizon)
    if end <= start_idx:
        return None

    fwd = pd.to_numeric(close.iloc[start_idx + 1 : end + 1], errors="coerce").dropna()
    if len(fwd) == 0:
        return None

    raw = float(fwd.max()) / entry - 1.0
    return max(0.0, raw)


def pick_samples_indices(z: pd.Series, thresh_fn, horizon: int, cooldown: int) -> List[int]:
    """
    Picks indices i where thresh_fn(z[i]) is True, ensuring enough future horizon,
    and applying cooldown bars to reduce overlap.
    """
    idxs: List[int] = []
    i = 0
    n = len(z)
    while i < n:
        zi = safe_float(z.iloc[i])
        if zi is not None and thresh_fn(zi) and (i + horizon) < n:
            idxs.append(i)
            i += cooldown  # skip ahead
        else:
            i += 1
    return idxs


def summarize_samples(values: List[float]) -> Dict[str, Any]:
    arr = np.array(values, dtype=float)
    if arr.size == 0:
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
        "sample_size": int(arr.size),
        "p10": float(np.quantile(arr, 0.10)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "mean": float(arr.mean()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


# --------------------------
# Data sources
# --------------------------

def fetch_stooq_daily(ticker: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
    text = download_text(url)
    df_raw = parse_csv_to_df(text)
    date_col, value_col = infer_date_and_value_cols(df_raw, preferred_value_cols=["Close", "CLOSE", "close"])
    df = normalize_series_df(df_raw, date_col, value_col)

    meta = {
        "attempt_errors": [],
        "source": "stooq",
        "url": url,
        "series_id": ticker,
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df["date"].iloc[0]),
        "max_date": str(df["date"].iloc[-1]),
    }
    return df, meta


def fetch_fred_series(series_id: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    text = download_text(url)
    df_raw = parse_csv_to_df(text)
    # FRED standard columns
    date_col, value_col = infer_date_and_value_cols(df_raw, preferred_value_cols=[series_id, "VALUE", "value"])
    df = normalize_series_df(df_raw, date_col, value_col)

    meta = {
        "attempt_errors": [],
        "source": "fred",
        "url": url,
        "series_id": series_id,
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df["date"].iloc[0]),
        "max_date": str(df["date"].iloc[-1]),
    }
    return df, meta


def fetch_cboe_vxn() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv"
    text = download_text(url)
    df_raw = parse_csv_to_df(text)

    # CBOE CSV columns can vary. Use robust inference:
    # likely date col: "DATE" or "Trade Date"
    # likely value col: "CLOSE" or "Close" or "VXN" or "Index Value"
    date_col, value_col = infer_date_and_value_cols(
        df_raw,
        preferred_value_cols=["CLOSE", "Close", "close", "VXN", "Index Value", "INDEX VALUE", "IndexValue"],
    )
    df = normalize_series_df(df_raw, date_col, value_col)

    meta = {
        "attempt_errors": [],
        "source": "cboe",
        "url": url,
        "series_id": "VXN",
        "date_col": date_col,
        "value_col": value_col,
        "rows": int(df.shape[0]),
        "min_date": str(df["date"].iloc[0]),
        "max_date": str(df["date"].iloc[-1]),
    }
    return df, meta


def fetch_vxn_with_fallback(order: str) -> Tuple[pd.DataFrame, Dict[str, Any], str, bool]:
    """
    order:
      - "cboe_first": try cboe -> fred
      - "fred_first": try fred -> cboe
    """
    errors: List[str] = []

    def try_cboe():
        try:
            df, meta = fetch_cboe_vxn()
            return df, meta, "cboe", False
        except Exception as e:
            errors.append(f"cboe_error={repr(e)}")
            raise

    def try_fred():
        try:
            df, meta = fetch_fred_series("VXNCLS")
            return df, meta, "fred", False
        except Exception as e:
            errors.append(f"fred_error={repr(e)}")
            raise

    if order == "cboe_first":
        try:
            df, meta, src, _ = try_cboe()
            meta["attempt_errors"] = []
            return df, meta, src, False
        except Exception:
            try:
                df, meta, src, _ = try_fred()
                meta["attempt_errors"] = errors[:]  # record prior errors
                return df, meta, src, True
            except Exception as e2:
                raise RuntimeError("Both CBOE and FRED failed: " + "; ".join(errors + [repr(e2)]))
    else:  # fred_first
        try:
            df, meta, src, _ = try_fred()
            meta["attempt_errors"] = []
            return df, meta, src, False
        except Exception:
            try:
                df, meta, src, _ = try_cboe()
                meta["attempt_errors"] = errors[:]
                return df, meta, src, True
            except Exception as e2:
                raise RuntimeError("Both FRED and CBOE failed: " + "; ".join(errors + [repr(e2)]))


# --------------------------
# Action rules
# --------------------------

def action_price(latest: Dict[str, Any], z_thresh: float) -> Tuple[str, str]:
    z = safe_float(latest.get("z"))
    pos = safe_float(latest.get("position_in_band"))
    if z is None or pos is None:
        return "INSUFFICIENT_DATA", "missing_z_or_pos"

    # priority: hard trigger first
    if z <= z_thresh:
        return "AT_LOWER_BAND (TRIGGER)", f"z<={z_thresh:g}"
    if z <= -1.5:
        return "NEAR_LOWER_BAND (MONITOR)", "z<=-1.5"
    if pos >= 0.9:
        return "NEAR_UPPER_BAND (WATCH)", f"position_in_band>=0.9 (pos={pos:.3f})"
    return "NORMAL_RANGE", "none"


def action_vxn(latest: Dict[str, Any], z_low: float, z_high: float) -> Tuple[str, str, str, bool]:
    z = safe_float(latest.get("z"))
    pos = safe_float(latest.get("position_in_band"))
    if z is None or pos is None:
        return "INSUFFICIENT_DATA", "missing_z_or_pos", "NONE", False

    if z <= z_low:
        return "LOW_VOL (INFO)", f"z<={z_low:g}", "A", False
    if z >= z_high:
        return "HIGH_VOL (ALERT)", f"z>={z_high:g}", "B", True
    if pos >= 0.8:
        return "NEAR_UPPER_BAND (WATCH)", f"position_in_band>=0.8 (pos={pos:.3f})", "NONE", False
    return "NORMAL_RANGE", "none", "NONE", False


# --------------------------
# Build snippet objects
# --------------------------

def build_latest_dict(bb: BBResult) -> Dict[str, Any]:
    df = bb.df
    df_valid = df[df["bb_mid"].notna() & df["z"].notna()].copy()
    if df_valid.empty:
        raise ValueError("Not enough data to compute BB (no valid rows).")

    row = df_valid.iloc[-1]
    latest = {
        "date": str(row["date"]),
        "close": float(row["close"]),
        "bb_mid": float(row["bb_mid"]),
        "bb_lower": float(row["bb_lower"]),
        "bb_upper": float(row["bb_upper"]),
        "z": float(row["z"]),
        "bandwidth_pct": float(row["bandwidth_pct"]),  # fraction
        "bandwidth_delta_pct": float(row["bandwidth_delta_pct"]),
        "distance_to_lower_pct": float(row["distance_to_lower_pct"]),
        "distance_to_upper_pct": float(row["distance_to_upper_pct"]),
        "position_in_band": float(row["position_in_band"]),
        "walk_lower_count": int(row["walk_lower_count"]),
        "walk_upper_count": int(row["walk_upper_count"]),
    }
    return latest


def run_price_pipeline(
    ticker: str,
    out_dir: str,
    bb_len: int,
    bb_k: float,
    use_log: bool,
    ddof: int,
    z_thresh: float,
    horizon_days: int,
    cooldown_bars: int,
    quiet: bool,
) -> Dict[str, Any]:
    generated_at = utc_now_iso()
    df, meta = fetch_stooq_daily(ticker)

    bb = compute_bollinger(df, length=bb_len, k=bb_k, use_log=use_log, ddof=ddof)
    latest = build_latest_dict(bb)

    # trigger for "hard" signal day (used for historical simulation)
    trigger_z_le_thresh = bool(safe_float(latest["z"]) is not None and latest["z"] <= z_thresh)

    # historical simulation: only on signal days z <= z_thresh
    z_series = bb.df["z"]
    close_series = bb.df["close"]

    idxs = pick_samples_indices(
        z_series,
        thresh_fn=lambda zz: zz <= z_thresh,
        horizon=horizon_days,
        cooldown=cooldown_bars,
    )
    vals: List[float] = []
    for i in idxs:
        v = forward_mdd(close_series, i, horizon_days)
        if v is not None:
            vals.append(v)

    sim = summarize_samples(vals)
    sim.update({
        "metric": "forward_mdd",
        "metric_interpretation": "<=0; closer to 0 is less pain; more negative is deeper drawdown",
        "z_thresh": float(z_thresh),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
    })

    # staleness + confidence
    s_days = staleness_days(generated_at, meta["max_date"])
    s_flag = staleness_flag(s_days)
    sim["confidence"] = confidence_from(s_flag, int(sim["sample_size"]))
    sim["confidence_rule"] = "stale!=OK => LOW else <30=LOW, 30-79=MED, >=80=HIGH"

    action_output, trigger_reason = action_price(latest, z_thresh=z_thresh)

    out = {
        "name": f"{ticker.upper()}_BB(len={bb_len},k={bb_k},log={use_log})",
        "generated_at_utc": generated_at,
        "meta": meta,
        "params": {
            "length": int(bb_len),
            "k": float(bb_k),
            "use_log": bool(use_log),
            "ddof": int(ddof),
        },
        "latest": {
            **latest,
            "trigger_z_le_-2": bool(trigger_z_le_thresh),
        },
        "historical_simulation": sim,
        "staleness_days": int(s_days),
        "staleness_flag": s_flag,
        "action_output": action_output,
        "trigger_reason": trigger_reason,
    }

    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, "snippet_price.json")
    write_json(out_path, out)
    if not quiet:
        print(f"Wrote {out_path}")
    return out


def run_vxn_pipeline(
    vxn_code: str,
    out_dir: str,
    bb_len: int,
    bb_k: float,
    use_log: bool,
    ddof: int,
    z_thresh_low: float,
    z_thresh_high: float,
    horizon_days: int,
    cooldown_bars: int,
    vxn_source: str,
    quiet: bool,
) -> Dict[str, Any]:
    generated_at = utc_now_iso()

    df, meta, selected_source, fallback_used = fetch_vxn_with_fallback(vxn_source)

    bb = compute_bollinger(df, length=bb_len, k=bb_k, use_log=use_log, ddof=ddof)
    latest = build_latest_dict(bb)

    trig_a = bool(safe_float(latest["z"]) is not None and latest["z"] <= z_thresh_low)
    trig_b = bool(safe_float(latest["z"]) is not None and latest["z"] >= z_thresh_high)

    # simulations
    z_series = bb.df["z"]
    close_series = bb.df["close"]

    idxs_a = pick_samples_indices(z_series, thresh_fn=lambda zz: zz <= z_thresh_low, horizon=horizon_days, cooldown=cooldown_bars)
    vals_a: List[float] = []
    for i in idxs_a:
        v = forward_max_runup(close_series, i, horizon_days)
        if v is not None:
            vals_a.append(v)
    sim_a = summarize_samples(vals_a)
    sim_a.update({
        "regime": "A_lowvol",
        "metric": "forward_max_runup",
        "metric_interpretation": ">=0; larger means bigger spike risk",
        "z_thresh": float(z_thresh_low),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
    })

    idxs_b = pick_samples_indices(z_series, thresh_fn=lambda zz: zz >= z_thresh_high, horizon=horizon_days, cooldown=cooldown_bars)
    vals_b: List[float] = []
    for i in idxs_b:
        v = forward_max_runup(close_series, i, horizon_days)
        if v is not None:
            vals_b.append(v)
    sim_b = summarize_samples(vals_b)
    sim_b.update({
        "regime": "B_highvol",
        "metric": "forward_max_runup",
        "metric_interpretation": ">=0; larger means further spike continuation risk",
        "z_thresh": float(z_thresh_high),
        "horizon_days": int(horizon_days),
        "cooldown_bars": int(cooldown_bars),
    })

    # staleness + confidence
    s_days = staleness_days(generated_at, meta["max_date"])
    s_flag = staleness_flag(s_days)
    sim_a["confidence"] = confidence_from(s_flag, int(sim_a["sample_size"]))
    sim_b["confidence"] = confidence_from(s_flag, int(sim_b["sample_size"]))
    overall_conf = max([sim_a["confidence"], sim_b["confidence"]], key=lambda c: {"LOW": 0, "MED": 1, "HIGH": 2}[c])

    action_output, trigger_reason, active_regime, tail_b_applicable = action_vxn(
        latest, z_low=z_thresh_low, z_high=z_thresh_high
    )

    out = {
        "name": f"{vxn_code}_BB(len={bb_len},k={bb_k},log={use_log})",
        "generated_at_utc": generated_at,
        "meta": meta,
        "params": {
            "length": int(bb_len),
            "k": float(bb_k),
            "use_log": bool(use_log),
            "ddof": int(ddof),
            "z_thresh_low": float(z_thresh_low),
            "z_thresh_high": float(z_thresh_high),
        },
        "source": meta.get("source"),
        "url": meta.get("url"),
        "selected_source": selected_source,
        "fallback_used": bool(fallback_used),
        "latest": {
            **latest,
            "trigger_z_le_-2 (A_lowvol)": bool(trig_a),
            "trigger_z_ge_2 (B_highvol)": bool(trig_b),
        },
        "historical_simulation": {
            "A": sim_a,
            "B": sim_b,
            "confidence_rule": "stale!=OK => LOW else <30=LOW, 30-79=MED, >=80=HIGH",
            "confidence_overall": overall_conf,
        },
        "staleness_days": int(s_days),
        "staleness_flag": s_flag,
        "action_output": action_output,
        "trigger_reason": trigger_reason,
        "active_regime": active_regime,
        "tail_B_applicable": bool(tail_b_applicable),
    }

    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, "snippet_vxn.json")
    write_json(out_path, out)
    if not quiet:
        print(f"Wrote {out_path}")
    return out


# --------------------------
# CLI
# --------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute BB(len,k) logclose for QQQ (price) and VXN (vol), emit snippets.")
    p.add_argument("--price_ticker", default="qqq.us", help="Stooq ticker for price series, e.g., qqq.us")
    p.add_argument("--out_dir", default="nasdaq_bb_cache", help="Output directory, e.g., nasdaq_bb_cache")
    p.add_argument("--bb_len", type=int, default=60, help="Bollinger length (window)")
    p.add_argument("--bb_k", type=float, default=2.0, help="Bollinger k (std multiplier)")
    p.add_argument("--use_log", action="store_true", default=True, help="Use log-close (default true).")
    p.add_argument("--no_log", action="store_true", help="Disable log-close and use raw close.")
    p.add_argument("--ddof", type=int, default=0, help="Std ddof (0 = population)")
    p.add_argument("--z_thresh", type=float, default=-2.0, help="Price signal threshold (z <= z_thresh)")
    p.add_argument("--z_thresh_low", type=float, default=-2.0, help="VXN low-vol threshold (z <= z_thresh_low)")
    p.add_argument("--z_thresh_high", type=float, default=2.0, help="VXN high-vol threshold (z >= z_thresh_high)")
    p.add_argument("--horizon_days", type=int, default=20, help="Forward horizon bars")
    p.add_argument("--cooldown_bars", type=int, default=20, help="Cooldown bars between samples")
    p.add_argument("--vxn_enable", action="store_true", help="Enable VXN processing")
    p.add_argument("--vxn_code", default="VXN", help="Label for VXN series (for naming)")
    p.add_argument("--vxn_source", choices=["cboe_first", "fred_first"], default="cboe_first",
                   help="VXN source order: cboe_first or fred_first")
    p.add_argument("--quiet", action="store_true", help="Less stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    use_log = True
    if args.no_log:
        use_log = False
    elif args.use_log:
        use_log = True

    # PRICE
    try:
        run_price_pipeline(
            ticker=args.price_ticker,
            out_dir=args.out_dir,
            bb_len=args.bb_len,
            bb_k=args.bb_k,
            use_log=use_log,
            ddof=args.ddof,
            z_thresh=args.z_thresh,
            horizon_days=args.horizon_days,
            cooldown_bars=args.cooldown_bars,
            quiet=args.quiet,
        )
    except Exception as e:
        print(f"[ERROR] price pipeline failed: {repr(e)}", file=sys.stderr)
        return 2

    # VXN optional
    if args.vxn_enable:
        try:
            run_vxn_pipeline(
                vxn_code=args.vxn_code,
                out_dir=args.out_dir,
                bb_len=args.bb_len,
                bb_k=args.bb_k,
                use_log=use_log,
                ddof=args.ddof,
                z_thresh_low=args.z_thresh_low,
                z_thresh_high=args.z_thresh_high,
                horizon_days=args.horizon_days,
                cooldown_bars=args.cooldown_bars,
                vxn_source=args.vxn_source,
                quiet=args.quiet,
            )
        except Exception as e:
            print(f"[ERROR] vxn pipeline failed: {repr(e)}", file=sys.stderr)
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())