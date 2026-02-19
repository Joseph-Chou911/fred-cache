#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TW0050 Bollinger Bands (window=60, k=2) + forward MDD (20 trading days)
with auditable split handling + gap/jump audit.

Key outputs (in --cache_dir):
- stats_latest.json   : latest snapshot + DQ audit + forward_mdd distribution stats
- history_lite.json   : last N rows of daily metrics (lite)
- prices.csv          : audit table (close/adj_close/price_raw/price_adj/adj_factor)

Important behavioral change vs your earlier version:
- If you use Adj Close (default), split-heal is OFF by default, because Adj Close may already be adjusted.
  You can override with --split_heal_on_adjclose.
- You can force split events by --force_splits "YYYY-MM-DD:4,YYYY-MM-DD:2".
  For 0050 split per TWSE announcement, align to the first trading date after halt: 2025-06-18:4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # pragma: no cover


DEFAULT_TZ = "Asia/Taipei"


# ----------------------------
# Utils
# ----------------------------
def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def local_today(tz_name: str) -> date:
    if ZoneInfo is None:
        return datetime.now().date()
    return datetime.now(ZoneInfo(tz_name)).date()


def _to_1d_series(x, index, name: str) -> pd.Series:
    """
    Force x into a 1D pandas Series aligned to `index`.
    Accepts Series / 1-col DataFrame / ndarray (n,) or (n,1).
    """
    if isinstance(x, pd.DataFrame):
        if x.shape[1] != 1:
            raise ValueError(f"{name}: expected 1 column, got {x.shape}")
        x = x.iloc[:, 0]

    if isinstance(x, pd.Series):
        s = x.copy()
        if len(s) != len(index):
            arr = np.asarray(s.to_numpy()).reshape(-1)
            s = pd.Series(arr, index=index, name=name)
        else:
            s = s.reindex(index)
    else:
        arr = np.asarray(x).reshape(-1)
        s = pd.Series(arr, index=index, name=name)

    s = pd.to_numeric(s, errors="coerce")
    s.name = name
    return s


# ----------------------------
# Data loading
# ----------------------------
def read_csv_prices(csv_path: Path, price_col: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if "Date" not in df.columns:
        raise ValueError("CSV must contain 'Date' column (YYYY-MM-DD).")

    if price_col not in df.columns:
        candidates = ["Adj Close", "AdjClose", "Close", "close", "adj_close", "adjclose"]
        found = None
        for c in candidates:
            if c in df.columns:
                found = c
                break
        if not found:
            raise ValueError(
                f"CSV must contain price column '{price_col}' or one of {candidates}."
            )
        price_col = found

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    px = pd.to_numeric(df[price_col], errors="coerce")
    out = pd.DataFrame({"price": px.values}, index=pd.to_datetime(df["Date"]).values)
    out.index.name = "Date"
    out = out.dropna()
    return out


def fetch_yahoo_prices(symbol: str, start: str, end: Optional[str]) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed. Install with: pip install yfinance")

    df = yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"Empty price data from yfinance for symbol={symbol}.")
    df = df.copy()
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.dropna(axis=0, how="any")
    df.index.name = "Date"
    return df


def try_fetch_yf_splits(symbol: str) -> Optional[pd.Series]:
    """
    Best-effort: fetch Yahoo split series via yfinance Ticker.
    Returns a Series indexed by date with split ratio (e.g. 4.0 means 4:1 split).
    """
    if yf is None:
        return None
    try:
        t = yf.Ticker(symbol)
        s = t.splits
        if s is None:
            return None
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            return None
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s.dropna()
        return s
    except Exception:
        return None


# ----------------------------
# Split handling
# ----------------------------
def _is_close_ratio(r: float, target: float, tol: float) -> bool:
    if not np.isfinite(r) or r <= 0:
        return False
    return abs(r / target - 1.0) <= tol


def parse_force_splits(s: Optional[str]) -> List[Dict[str, Any]]:
    """
    Parse: "YYYY-MM-DD:4,YYYY-MM-DD:2"
    Meaning: at that date (or next trading date), apply split factor=4 (4:1).
    """
    out: List[Dict[str, Any]] = []
    if not s:
        return out

    parts = [p.strip() for p in str(s).split(",") if p.strip()]
    for p in parts:
        if ":" not in p:
            raise ValueError(f"--force_splits item must be like YYYY-MM-DD:4, got: {p}")
        d, f = p.split(":", 1)
        d = d.strip()
        f = float(f.strip())
        if f <= 0:
            raise ValueError(f"Split factor must be >0, got: {f} in {p}")
        dt = pd.to_datetime(d, errors="raise").date()
        out.append({"date": str(dt), "factor": float(f), "direction": "SPLIT"})
    out.sort(key=lambda x: x["date"])
    return out


def detect_split_events_by_ratio(
    price_raw: pd.Series,
    factors: List[float],
    tol: float,
    min_price: float = 0.01,
) -> List[Dict[str, Any]]:
    """
    Heuristic detection: scan ratios r[t] = price[t] / price[t-1]
    If r ~ 1/f => SPLIT(f:1) at t
    If r ~ f   => REVERSE_SPLIT(1:f) at t
    """
    s = pd.to_numeric(price_raw.copy(), errors="coerce").where(lambda x: x > min_price)
    idx = s.index
    vals = s.to_numpy(dtype=float)
    n = len(vals)
    if n < 3:
        return []

    events: List[Dict[str, Any]] = []
    for t in range(1, n):
        p0 = vals[t - 1]
        p1 = vals[t]
        if not (np.isfinite(p0) and np.isfinite(p1)) or p0 <= 0:
            continue
        r = p1 / p0

        for f in factors:
            if _is_close_ratio(r, 1.0 / f, tol):
                events.append(
                    {
                        "event_index": int(t),
                        "event_date": str(pd.to_datetime(idx[t]).date()),
                        "direction": "SPLIT",
                        "factor": float(f),
                        "raw_ratio": float(r),
                        "tolerance": float(tol),
                        "source": "ratio_detect",
                    }
                )
                break
            if _is_close_ratio(r, f, tol):
                events.append(
                    {
                        "event_index": int(t),
                        "event_date": str(pd.to_datetime(idx[t]).date()),
                        "direction": "REVERSE_SPLIT",
                        "factor": float(f),
                        "raw_ratio": float(r),
                        "tolerance": float(tol),
                        "source": "ratio_detect",
                    }
                )
                break

    # de-dup same date multiple hits
    uniq: Dict[str, Dict[str, Any]] = {}
    for e in events:
        k = f'{e["event_date"]}:{e["direction"]}:{e["factor"]}'
        if k not in uniq:
            uniq[k] = e
    out = list(uniq.values())
    out.sort(key=lambda x: x["event_date"])
    return out


def apply_split_events_to_earlier_history(
    price_raw: pd.Series,
    events: List[Dict[str, Any]],
) -> Tuple[pd.Series, List[Dict[str, Any]]]:
    """
    Make series continuous in the "post-event unit" by adjusting earlier history:

    - SPLIT factor f (f:1): price drops to ~1/f at event -> multiply earlier history by 1/f
    - REVERSE_SPLIT factor f (1:f): price jumps by f at event -> multiply earlier history by f

    We apply events in chronological order.
    """
    s = pd.to_numeric(price_raw.copy(), errors="coerce")
    idx = s.index
    adj = s.to_numpy(dtype=float).reshape(-1)
    n = len(adj)

    applied: List[Dict[str, Any]] = []
    if n < 3 or not events:
        return pd.Series(adj, index=idx, name="price_adj"), applied

    # Build a date->index map for exact hits; otherwise use first index >= date
    idx_dates = pd.to_datetime(idx).date

    def find_event_index(d: date) -> Optional[int]:
        # exact
        for i, di in enumerate(idx_dates):
            if di == d:
                return i
        # next trading day
        for i, di in enumerate(idx_dates):
            if di > d:
                return i
        return None

    for e in events:
        d = pd.to_datetime(e["event_date"], errors="coerce").date()
        t = e.get("event_index", None)
        if t is None:
            t = find_event_index(d)
        if t is None or t <= 0 or t >= n:
            applied.append(
                {
                    **e,
                    "applied": False,
                    "reason": "event date not in index and no later trading date",
                }
            )
            continue

        f = float(e["factor"])
        direction = str(e["direction"]).upper()
        if direction == "SPLIT":
            mult = 1.0 / f
        elif direction == "REVERSE_SPLIT":
            mult = f
        else:
            applied.append({**e, "applied": False, "reason": f"unknown direction={direction}"})
            continue

        # adjust earlier history
        adj[:t] = adj[:t] * mult

        applied.append(
            {
                **e,
                "applied": True,
                "apply_multiplier_to_earlier": float(mult),
                "applied_to_range": f"[0:{t})",
                "event_index_used": int(t),
                "event_date_used": str(pd.to_datetime(idx[t]).date()),
            }
        )

    return pd.Series(adj, index=idx, name="price_adj"), applied


# ----------------------------
# Forward MDD + BB
# ----------------------------
def calc_forward_mdd(prices_1d: np.ndarray, horizon: int) -> np.ndarray:
    """
    forward_mdd[t] = minimum drawdown within next `horizon` trading days:
        min(0, min_{i=1..horizon} (price[t+i]/price[t] - 1))
    """
    prices_1d = np.asarray(prices_1d).reshape(-1)
    n = len(prices_1d)
    out = np.full(n, np.nan, dtype=float)
    if horizon <= 0:
        return out

    for t in range(0, n - horizon):
        p0 = prices_1d[t]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        fut = prices_1d[t + 1 : t + 1 + horizon]
        if fut.size == 0 or not np.all(np.isfinite(fut)):
            continue
        m = np.min(fut / p0 - 1.0)
        out[t] = min(0.0, float(m))
    return out


def conf_from_n(n: int) -> str:
    if n >= 120:
        return "HIGH"
    if n >= 60:
        return "MED"
    if n >= 20:
        return "LOW"
    return "NA"


def compute_mdd_stats(arr: np.ndarray) -> Dict[str, Any]:
    arr = np.asarray(arr, dtype=float)
    fin = arr[np.isfinite(arr)]
    n = int(fin.size)
    if n == 0:
        return {"n": 0, "p50": None, "p10": None, "min": None, "conf": "NA"}
    return {
        "n": n,
        "p50": float(np.percentile(fin, 50)),
        "p10": float(np.percentile(fin, 10)),
        "min": float(np.min(fin)),
        "conf": conf_from_n(n),
    }


def bb_state_from_z(z: Optional[float]) -> Tuple[str, str]:
    if z is None or not np.isfinite(z):
        return ("NA", "z is NA")
    if z <= -2.0:
        return ("BELOW_LOWER_BAND", "z<=-2.0")
    if z <= -1.5:
        return ("NEAR_LOWER_BAND", "z<=-1.5")
    if z >= 2.0:
        return ("ABOVE_UPPER_BAND", "z>=2.0")
    if z >= 1.5:
        return ("NEAR_UPPER_BAND", "z>=1.5")
    return ("IN_BAND", "-1.5<z<1.5")


# ----------------------------
# DQ audit: gaps / jumps / factor changes
# ----------------------------
def audit_gaps_and_jumps(
    idx: pd.DatetimeIndex,
    price_raw: pd.Series,
    price_adj: pd.Series,
    *,
    gap_busdays_warn: int,
    ret_jump_raw: float,
    ret_jump_adj: float,
    raw_jump_thr: float,
    adj_stable_thr: float,
    adj_factor_change_tol: float,
) -> Dict[str, Any]:
    """
    Gap audit uses weekday heuristic only (Mon-Fri business days), NOT Taiwan market holidays.
    This is why you may see many "gaps" around lunar new year etc.
    """
    idx = pd.to_datetime(idx)
    n = int(len(idx))
    out: Dict[str, Any] = {
        "n": n,
        "gap_count": 0,
        "gap_suspects": [],
        "jump_count": 0,
        "jump_suspects": [],
        "factor_change_count": 0,
        "factor_change_suspects": [],
        "params": {
            "gap_busdays_warn": int(gap_busdays_warn),
            "ret_jump_raw": float(ret_jump_raw),
            "ret_jump_adj": float(ret_jump_adj),
            "raw_jump_thr": float(raw_jump_thr),
            "adj_stable_thr": float(adj_stable_thr),
            "factor_change_tol": float(adj_factor_change_tol),
        },
        "weekday_heuristic": True,
    }

    # gaps
    dates = pd.to_datetime(idx).date
    for i in range(1, n):
        d0 = dates[i - 1]
        d1 = dates[i]
        if d1 <= d0:
            continue
        # business days strictly between
        mid = pd.bdate_range(pd.Timestamp(d0) + pd.Timedelta(days=1),
                             pd.Timestamp(d1) - pd.Timedelta(days=1))
        missing = int(len(mid))
        if missing >= gap_busdays_warn:
            out["gap_suspects"].append({"from": str(d0), "to": str(d1), "missing_busdays": missing})

    out["gap_count"] = int(len(out["gap_suspects"]))

    # jumps
    pr = pd.to_numeric(price_raw, errors="coerce")
    pa = pd.to_numeric(price_adj, errors="coerce")
    ret_r = pr.pct_change()
    ret_a = pa.pct_change()

    for i in range(1, n):
        rr = ret_r.iloc[i]
        ra = ret_a.iloc[i]
        if not (np.isfinite(rr) and np.isfinite(ra)):
            continue

        # raw return jump
        if abs(rr) >= ret_jump_raw:
            out["jump_suspects"].append(
                {
                    "date": str(pd.to_datetime(idx[i]).date()),
                    "kind": "RET_JUMP_RAW",
                    "ret_raw": float(rr),
                    "ret_adj": float(ra),
                    "price_raw": None if not np.isfinite(pr.iloc[i]) else float(pr.iloc[i]),
                    "price_adj": None if not np.isfinite(pa.iloc[i]) else float(pa.iloc[i]),
                }
            )

        # adj return jump
        if abs(ra) >= ret_jump_adj:
            out["jump_suspects"].append(
                {
                    "date": str(pd.to_datetime(idx[i]).date()),
                    "kind": "RET_JUMP_ADJ",
                    "ret_raw": float(rr),
                    "ret_adj": float(ra),
                    "price_raw": None if not np.isfinite(pr.iloc[i]) else float(pr.iloc[i]),
                    "price_adj": None if not np.isfinite(pa.iloc[i]) else float(pa.iloc[i]),
                }
            )

        # raw jump but adj stable => likely split heal signature
        if abs(rr) >= raw_jump_thr and abs(ra) <= adj_stable_thr:
            out["jump_suspects"].append(
                {
                    "date": str(pd.to_datetime(idx[i]).date()),
                    "kind": "RAW_JUMP_ADJ_STABLE",
                    "ret_raw": float(rr),
                    "ret_adj": float(ra),
                    "price_raw": None if not np.isfinite(pr.iloc[i]) else float(pr.iloc[i]),
                    "price_adj": None if not np.isfinite(pa.iloc[i]) else float(pa.iloc[i]),
                }
            )

    out["jump_count"] = int(len(out["jump_suspects"]))

    # factor change suspects: adj_factor = price_adj / price_raw
    with np.errstate(divide="ignore", invalid="ignore"):
        adj_factor = (pa / pr).replace([np.inf, -np.inf], np.nan)

    af_chg = adj_factor.pct_change()
    for i in range(1, n):
        chg = af_chg.iloc[i]
        if not np.isfinite(chg):
            continue
        if abs(chg) >= adj_factor_change_tol:
            out["factor_change_suspects"].append(
                {
                    "date": str(pd.to_datetime(idx[i]).date()),
                    "adj_factor": None if not np.isfinite(adj_factor.iloc[i]) else float(adj_factor.iloc[i]),
                    "adj_factor_chg": float(chg),
                }
            )
    out["factor_change_count"] = int(len(out["factor_change_suspects"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="TW0050 BB(60,2) + forward_mdd(20D) generator (auditable split/gap)")
    ap.add_argument("--symbol", default="0050.TW", help="Yahoo Finance symbol (default: 0050.TW)")
    ap.add_argument("--start", default="2003-01-01", help="Start date YYYY-MM-DD (default: 2003-01-01)")
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: None)")
    ap.add_argument("--window", type=int, default=60, help="BB window length (default: 60)")
    ap.add_argument("--k", type=float, default=2.0, help="BB k (default: 2.0)")
    ap.add_argument("--horizon", type=int, default=20, help="Forward MDD horizon in trading days (default: 20)")
    ap.add_argument("--cache_dir", default="tw0050_bb_cache", help="Output cache dir")
    ap.add_argument("--history_limit", type=int, default=400, help="Rows to keep in history_lite.json (default: 400)")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"Local timezone for staleness calc (default: {DEFAULT_TZ})")

    # Data input options
    ap.add_argument("--input_csv", default=None, help="Optional CSV input instead of yfinance")
    ap.add_argument("--csv_price_col", default="Adj Close", help="CSV price column name (default: 'Adj Close')")

    # Price selection for yfinance
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--use_adj_close", action="store_true", help="Use Adj Close (default if neither flag is set)")
    g.add_argument("--use_close", action="store_true", help="Use Close")
    ap.add_argument("--use_logclose", action="store_true", help="Compute BB on log(price_adj)")

    # Split options
    ap.add_argument("--force_splits", default=None,
                    help='Force split events, e.g. "2025-06-18:4" or "2025-06-18:4,2014-01-02:4"')
    ap.add_argument("--prefer_yf_splits", action="store_true",
                    help="If no --force_splits, try yfinance Ticker().splits as split source (recommended with --use_close)")
    ap.add_argument("--disable_split_heal", action="store_true",
                    help="Disable split detection/healing entirely")
    ap.add_argument("--split_heal_on_adjclose", action="store_true",
                    help="Allow split-heal even when using Adj Close (default is OFF for Adj Close).")

    # Heuristic split detection (only used when not forced and not prefer_yf_splits)
    ap.add_argument("--split_factors", default="4",
                    help="Comma-separated split factors to detect (default: '4'). Example: '2,4,5,10'")
    ap.add_argument("--split_tol", type=float, default=0.06,
                    help="Relative tolerance for detecting split ratios (default: 0.06 => ±6%%).")

    # Conditional thresholds for forward MDD stats
    ap.add_argument("--z_threshold", type=float, default=-1.5,
                    help="Cheap-side threshold for conditional stats (default: -1.5)")
    ap.add_argument("--z_hot", type=float, default=1.5, help="Hot-side threshold (default: 1.5)")
    ap.add_argument("--z_hot2", type=float, default=2.0, help="Extreme hot-side threshold (default: 2.0)")

    # Gap/jump audit params (to match your stats_latest.json schema)
    ap.add_argument("--gap_busdays_warn", type=int, default=2, help="Warn if missing business days >= this (default: 2)")
    ap.add_argument("--ret_jump_raw", type=float, default=0.2, help="Raw return jump threshold (default: 0.2)")
    ap.add_argument("--ret_jump_adj", type=float, default=0.2, help="Adj return jump threshold (default: 0.2)")
    ap.add_argument("--raw_jump_thr", type=float, default=0.2, help="Raw jump threshold for RAW_JUMP_ADJ_STABLE (default: 0.2)")
    ap.add_argument("--adj_stable_thr", type=float, default=0.05, help="Adj stable threshold for RAW_JUMP_ADJ_STABLE (default: 0.05)")
    ap.add_argument("--adj_factor_change_tol", type=float, default=0.1, help="Adj factor change tol (default: 0.1)")

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    script_fp = sha256_file(Path(__file__))

    dq: Dict[str, Any] = {
        "fetch_ok": False,
        "insufficient_history": False,
        "stale_days_local": None,
        "split_heal_enabled": False,
        "split_events": [],
        "gap_audit": None,
        "gap_suspects": [],
        "jump_suspects": [],
        "factor_change_suspects": [],
        "notes": [],
    }

    # ----- Load prices -----
    data_source = "csv" if args.input_csv else "yfinance"

    yf_splits: Optional[pd.Series] = None
    if args.input_csv:
        prices_df = read_csv_prices(Path(args.input_csv), args.csv_price_col)
        prices_df.index.name = "Date"
        close_s = None
        adj_close_s = None
    else:
        df = fetch_yahoo_prices(args.symbol, args.start, args.end)
        close_s = df["Close"] if "Close" in df.columns else None
        adj_close_s = df["Adj Close"] if "Adj Close" in df.columns else None
        yf_splits = try_fetch_yf_splits(args.symbol)

        # keep a unified df for audit columns
        cols = {}
        if close_s is not None:
            cols["Close"] = pd.to_numeric(close_s, errors="coerce")
        if adj_close_s is not None:
            cols["Adj Close"] = pd.to_numeric(adj_close_s, errors="coerce")
        if not cols:
            # fallback: take first column
            cols["Close"] = pd.to_numeric(df.iloc[:, 0], errors="coerce")
        prices_df = pd.DataFrame(cols, index=df.index).dropna(how="all")
        prices_df.index.name = "Date"

    if prices_df.empty:
        raise RuntimeError("No usable price data loaded.")

    dq["fetch_ok"] = True

    # ----- Choose price_raw basis -----
    if args.use_close:
        chosen = "Close"
    else:
        # default to Adj Close if available; else Close
        chosen = "Adj Close" if ("Adj Close" in prices_df.columns) else "Close"

    if chosen not in prices_df.columns:
        chosen = prices_df.columns[0]

    price_raw = _to_1d_series(prices_df[chosen], prices_df.index, "price_raw").dropna()
    price_raw = price_raw.reindex(prices_df.index)  # keep alignment
    price_basis = chosen

    # ----- Decide split heal enablement -----
    forced_events = parse_force_splits(args.force_splits)

    split_heal_enabled = False
    split_event_source = "none"

    if args.disable_split_heal:
        split_heal_enabled = False
    else:
        if price_basis == "Adj Close" and (not args.split_heal_on_adjclose) and (not forced_events):
            # IMPORTANT safety: Adj Close may already be split adjusted.
            split_heal_enabled = False
            dq["notes"].append("Split heal OFF by default for Adj Close (to avoid double-adjust). Use --use_close or --split_heal_on_adjclose.")
        else:
            split_heal_enabled = True

    dq["split_heal_enabled"] = bool(split_heal_enabled)

    # ----- Build split events -----
    events: List[Dict[str, Any]] = []
    if forced_events:
        events = [
            {
                "event_date": e["date"],
                "direction": e["direction"],
                "factor": float(e["factor"]),
                "source": "forced",
            }
            for e in forced_events
        ]
        split_event_source = "forced"
    elif split_heal_enabled and args.prefer_yf_splits and (yf_splits is not None) and (not yf_splits.empty):
        # Use Yahoo-reported splits as primary source (best effort)
        tmp: List[Dict[str, Any]] = []
        for ts, ratio in yf_splits.items():
            if not np.isfinite(ratio) or ratio <= 0:
                continue
            d = pd.to_datetime(ts).date()
            # yfinance splits are usually split ratios (e.g. 4.0 means 4:1 split)
            tmp.append({"event_date": str(d), "direction": "SPLIT", "factor": float(ratio), "source": "yfinance_splits"})
        tmp.sort(key=lambda x: x["event_date"])
        events = tmp
        split_event_source = "yfinance_splits"
    elif split_heal_enabled:
        # Heuristic detection
        factors = []
        for tok in str(args.split_factors).split(","):
            tok = tok.strip()
            if tok:
                try:
                    factors.append(float(tok))
                except Exception:
                    pass
        if not factors:
            factors = [4.0]
        events = detect_split_events_by_ratio(price_raw, factors=factors, tol=float(args.split_tol))
        split_event_source = "ratio_detect"

    # ----- Apply split events -----
    if split_heal_enabled and events:
        price_adj, applied = apply_split_events_to_earlier_history(price_raw, events)
        dq["split_events"] = applied