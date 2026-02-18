#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TW0050 Bollinger Bands (window=60, k=2) + forward MDD (20 trading days)

Data source:
- Default: Yahoo Finance via yfinance (symbol: 0050.TW)
- Optional: user-provided CSV (Date + Close/Adj Close)

Outputs (in --cache_dir):
- stats_latest.json         : latest-day snapshot + forward_mdd distribution stats + dq audit
- history_lite.json         : last N rows of daily metrics (lite)
- prices.csv                : fetched price table (audit/debug), includes price_raw and price_adj

Key robustness:
1) Force all vectors into 1D Series to avoid pandas ValueError: "Data must be 1-dimensional..."
2) Split/reverse-split detection + optional healing:
   - detect jumps near factor=f or 1/f (configurable tolerance)
   - optionally heal earlier history to make series continuous
   - IMPORTANT: healing can be constrained by known split dates (whitelist gating)
3) Forward MDD conditional stats are direction-complete:
   - z <= -1.5 (cheap side)
   - z >= +1.5 (hot side)
   - z >= +2.0 (extreme hot side)
4) DQ gap/jump/factor audits (weekday heuristic only; market holidays not modeled):
   - missing business days gaps
   - raw/adj return jump suspects
   - raw vs adj factor change suspects
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

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
    return df


def calc_forward_mdd(prices_1d: np.ndarray, horizon: int) -> np.ndarray:
    """
    forward_mdd[t] = minimum drawdown within next `horizon` trading days:
        min(0, min_{i=1..horizon} (price[t+i]/price[t] - 1))
    prices_1d must be shape (n,) (1D).
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


def _is_close_ratio(r: float, target: float, tol: float) -> bool:
    if not np.isfinite(r) or r <= 0:
        return False
    return abs(r / target - 1.0) <= tol


def _parse_known_split_days(s: str) -> Set[pd.Timestamp]:
    out: Set[pd.Timestamp] = set()
    if not str(s).strip():
        return out
    for tok in str(s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.add(pd.Timestamp(tok).normalize())
    return out


def _allowed_by_known_dates(
    event_day: pd.Timestamp,
    known_days: Optional[Set[pd.Timestamp]],
    window_days: int,
) -> bool:
    if not known_days:
        return True
    d = event_day.normalize()
    for kd in known_days:
        if abs((d - kd).days) <= int(window_days):
            return True
    return False


def detect_and_heal_splits(
    price_raw: pd.Series,
    factors: List[float],
    tol: float,
    min_price: float = 0.01,
    known_split_days: Optional[Set[pd.Timestamp]] = None,
    split_date_window: int = 1,
) -> Tuple[pd.Series, List[Dict[str, Any]]]:
    """
    Detect split/reverse-split jumps by scanning ratios r[t]=price[t]/price[t-1].

    If r is close to 1/f or f for any f in factors, record an event.
    Healing (modifying earlier history) is applied ONLY if:
      - known_split_days is empty => allow all heals (legacy behavior)
      - otherwise event_date must be within +/- split_date_window days of any known_split_day

    Healing rule:
      - if r ~= 1/f  (price drops to 1/f), interpret as split (f:1): adjust earlier history DOWN by 1/f
      - if r ~= f    (price jumps by f), interpret as reverse-split (1:f): adjust earlier history UP by f
    Apply cumulatively in time order.

    Returns:
      price_adj, events
    """
    s = price_raw.copy()
    s = pd.to_numeric(s, errors="coerce")
    s = s.where(s > min_price)

    idx = s.index
    vals = s.to_numpy(dtype=float)
    n = len(vals)
    if n < 3:
        return s, []

    adj = vals.copy()
    events: List[Dict[str, Any]] = []

    for t in range(1, n):
        p_prev = adj[t - 1]
        p_now = adj[t]
        if not (np.isfinite(p_prev) and np.isfinite(p_now)) or p_prev <= 0:
            continue

        r = p_now / p_prev

        matched = None
        direction = None
        implied = None

        for f in factors:
            if _is_close_ratio(r, 1.0 / f, tol):
                matched = f
                direction = "SPLIT"
                implied = f
                break
            if _is_close_ratio(r, f, tol):
                matched = f
                direction = "REVERSE_SPLIT"
                implied = f
                break

        if matched is None:
            continue

        if direction == "SPLIT":
            factor_apply = 1.0 / float(implied)
        else:
            factor_apply = float(implied)

        event_day = pd.Timestamp(idx[t]).normalize()
        allow_heal = _allowed_by_known_dates(event_day, known_split_days, split_date_window)

        ev: Dict[str, Any] = {
            "event_index": t,
            "event_date": str(event_day.date()),
            "raw_ratio": float(r),
            "direction": direction,
            "implied_factor": float(implied),
            "tolerance": float(tol),
            "applied_to_range": f"[0:{t})",
            "apply_multiplier_to_earlier": float(factor_apply),
            "healed": bool(allow_heal),
        }

        if not allow_heal:
            ev["heal_skipped_reason"] = "not_in_known_split_window"
            events.append(ev)
            continue

        adj[:t] = adj[:t] * factor_apply
        events.append(ev)

    price_adj = pd.Series(adj.reshape(-1), index=idx, name="price_adj")
    return price_adj, events


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


def _business_days_missing(prev_day: pd.Timestamp, next_day: pd.Timestamp) -> int:
    """
    Count missing business days between prev_day and next_day excluding endpoints.
    Weekday heuristic only; does not model exchange holidays.
    """
    if next_day <= prev_day:
        return 0
    start = (prev_day + pd.Timedelta(days=1)).normalize()
    end = (next_day - pd.Timedelta(days=1)).normalize()
    if end < start:
        return 0
    rng = pd.bdate_range(start, end, inclusive="both")
    return int(len(rng))


def run_gap_jump_factor_audit(
    price_raw: pd.Series,
    price_adj: pd.Series,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build dq audit fields:
      - gap_suspects: missing business days between consecutive quotes
      - jump_suspects: return jumps on raw/adj
      - factor_change_suspects: raw vs adj factor change jumps
      - gap_audit summary (counts + params + weekday_heuristic)
    """
    gap_busdays_warn = int(params["gap_busdays_warn"])
    ret_jump_raw_thr = float(params["ret_jump_raw"])
    ret_jump_adj_thr = float(params["ret_jump_adj"])
    raw_jump_thr = float(params["raw_jump_thr"])
    adj_stable_thr = float(params["adj_stable_thr"])
    adj_factor_change_tol = float(params["adj_factor_change_tol"])

    idx = price_raw.index
    n = int(len(idx))

    # --- gaps ---
    gap_suspects: List[Dict[str, Any]] = []
    for i in range(1, n):
        d0 = pd.Timestamp(idx[i - 1]).normalize()
        d1 = pd.Timestamp(idx[i]).normalize()
        miss = _business_days_missing(d0, d1)
        if miss > gap_busdays_warn:
            gap_suspects.append(
                {"from": str(d0.date()), "to": str(d1.date()), "missing_busdays": int(miss)}
            )

    # --- returns & jumps ---
    pr = price_raw.to_numpy(dtype=float)
    pa = price_adj.to_numpy(dtype=float)

    # ret[t] is return from t-1 -> t; ret[0]=nan
    ret_raw = np.full(n, np.nan, dtype=float)
    ret_adj = np.full(n, np.nan, dtype=float)

    for i in range(1, n):
        if np.isfinite(pr[i - 1]) and np.isfinite(pr[i]) and pr[i - 1] > 0:
            ret_raw[i] = pr[i] / pr[i - 1] - 1.0
        if np.isfinite(pa[i - 1]) and np.isfinite(pa[i]) and pa[i - 1] > 0:
            ret_adj[i] = pa[i] / pa[i - 1] - 1.0

    jump_suspects: List[Dict[str, Any]] = []
    for i in range(1, n):
        day = str(pd.Timestamp(idx[i]).normalize().date())

        if np.isfinite(ret_raw[i]) and abs(ret_raw[i]) >= ret_jump_raw_thr:
            jump_suspects.append(
                {
                    "date": day,
                    "kind": "RET_JUMP_RAW",
                    "price_raw": None if not np.isfinite(pr[i]) else float(pr[i]),
                    "price_adj": None if not np.isfinite(pa[i]) else float(pa[i]),
                    "ret_raw": float(ret_raw[i]),
                    "ret_adj": None if not np.isfinite(ret_adj[i]) else float(ret_adj[i]),
                }
            )

        if np.isfinite(ret_adj[i]) and abs(ret_adj[i]) >= ret_jump_adj_thr:
            jump_suspects.append(
                {
                    "date": day,
                    "kind": "RET_JUMP_ADJ",
                    "price_raw": None if not np.isfinite(pr[i]) else float(pr[i]),
                    "price_adj": None if not np.isfinite(pa[i]) else float(pa[i]),
                    "ret_raw": None if not np.isfinite(ret_raw[i]) else float(ret_raw[i]),
                    "ret_adj": float(ret_adj[i]),
                }
            )

        # raw jump but adj stable => suspicious data/split handling discrepancy
        if (
            np.isfinite(ret_raw[i])
            and abs(ret_raw[i]) >= raw_jump_thr
            and np.isfinite(ret_adj[i])
            and abs(ret_adj[i]) <= adj_stable_thr
        ):
            jump_suspects.append(
                {
                    "date": day,
                    "kind": "RAW_JUMP_ADJ_STABLE",
                    "price_raw": None if not np.isfinite(pr[i]) else float(pr[i]),
                    "price_adj": None if not np.isfinite(pa[i]) else float(pa[i]),
                    "ret_raw": float(ret_raw[i]),
                    "ret_adj": float(ret_adj[i]),
                }
            )

    # --- factor changes (adj/raw) ---
    factor_change_suspects: List[Dict[str, Any]] = []
    # adj_factor[t] = adj/raw; factor_chg[t] = factor[t-1] - factor[t]  (matches your sample -0.75)
    adj_factor = np.full(n, np.nan, dtype=float)
    for i in range(n):
        if np.isfinite(pr[i]) and pr[i] > 0 and np.isfinite(pa[i]):
            adj_factor[i] = pa[i] / pr[i]

    for i in range(1, n):
        if np.isfinite(adj_factor[i - 1]) and np.isfinite(adj_factor[i]):
            chg = adj_factor[i - 1] - adj_factor[i]
            if abs(chg) >= adj_factor_change_tol:
                factor_change_suspects.append(
                    {
                        "date": str(pd.Timestamp(idx[i]).normalize().date()),
                        "adj_factor": float(adj_factor[i]),
                        "adj_factor_chg": float(chg),
                    }
                )

    gap_audit = {
        "n": int(n),
        "gap_count": int(len(gap_suspects)),
        "jump_count": int(len(jump_suspects)),
        "factor_change_count": int(len(factor_change_suspects)),
        "params": {
            "gap_busdays_warn": gap_busdays_warn,
            "ret_jump_raw": ret_jump_raw_thr,
            "ret_jump_adj": ret_jump_adj_thr,
            "raw_jump_thr": raw_jump_thr,
            "adj_stable_thr": adj_stable_thr,
            "adj_factor_change_tol": adj_factor_change_tol,
        },
        "weekday_heuristic": True,
    }

    return {
        "gap_audit": gap_audit,
        "gap_suspects": gap_suspects,
        "jump_suspects": jump_suspects,
        "factor_change_suspects": factor_change_suspects,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="TW0050 BB(60,2) + forward_mdd(20D) generator"
    )
    ap.add_argument("--symbol", default="0050.TW", help="Yahoo Finance symbol (default: 0050.TW)")
    ap.add_argument("--start", default="2003-01-01", help="Start date YYYY-MM-DD (default: 2003-01-01)")
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: None)")
    ap.add_argument("--window", type=int, default=60, help="BB window length (default: 60)")
    ap.add_argument("--k", type=float, default=2.0, help="BB k (default: 2.0)")
    ap.add_argument("--horizon", type=int, default=20, help="Forward MDD horizon in trading days (default: 20)")
    ap.add_argument("--z_threshold", type=float, default=-1.5, help="Cheap-side conditional stats threshold (default: -1.5)")
    ap.add_argument("--cache_dir", default="tw0050_bb_cache", help="Output cache dir")
    ap.add_argument("--history_limit", type=int, default=400, help="Rows to keep in history_lite.json (default: 400)")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"Local timezone for age calculation (default: {DEFAULT_TZ})")

    # Data input options
    ap.add_argument("--input_csv", default=None, help="Optional CSV input instead of yfinance")
    ap.add_argument("--csv_price_col", default="Adj Close", help="CSV price column name (default: 'Adj Close')")

    # Price selection for yfinance
    ap.add_argument("--use_adj_close", action="store_true", help="Use Adj Close (recommended)")
    ap.add_argument("--use_close", action="store_true", help="Use Close (overrides --use_adj_close)")
    ap.add_argument("--use_logclose", action="store_true", help="Compute BB on log(price)")

    # Split detection/healing
    ap.add_argument(
        "--split_factors",
        default="4",
        help="Comma-separated split factors to detect (default: '4'). Example: '2,4,5,10'",
    )
    ap.add_argument(
        "--split_tol",
        type=float,
        default=0.06,
        help="Relative tolerance for detecting split ratios (default: 0.06 => ±6%%).",
    )
    ap.add_argument(
        "--disable_split_heal",
        action="store_true",
        help="Disable split detection/healing (not recommended unless your data is already cleaned).",
    )

    # NEW: whitelist gating for split healing (prevents false-heal on data-provider artifacts)
    ap.add_argument(
        "--known_split_dates",
        default="",
        help="Comma-separated YYYY-MM-DD dates where split healing is allowed (e.g. '2025-06-18'). Empty => allow all (legacy behavior).",
    )
    ap.add_argument(
        "--split_date_window",
        type=int,
        default=1,
        help="Allow heal within +/- N calendar days around known_split_dates (default: 1).",
    )

    # Hot-side thresholds
    ap.add_argument("--z_hot", type=float, default=1.5, help="Hot-side threshold (default: 1.5)")
    ap.add_argument("--z_hot2", type=float, default=2.0, help="Extreme hot-side threshold (default: 2.0)")

    # DQ audit thresholds (match your repro/meta)
    ap.add_argument("--gap_busdays_warn", type=int, default=2, help="Warn if missing business days > this (default: 2)")
    ap.add_argument("--ret_jump_raw", type=float, default=0.2, help="Raw daily return jump threshold abs(ret)>=thr (default: 0.2)")
    ap.add_argument("--ret_jump_adj", type=float, default=0.2, help="Adj daily return jump threshold abs(ret)>=thr (default: 0.2)")
    ap.add_argument("--raw_jump_thr", type=float, default=0.2, help="Raw jump threshold for RAW_JUMP_ADJ_STABLE (default: 0.2)")
    ap.add_argument("--adj_stable_thr", type=float, default=0.05, help="Adj stable threshold for RAW_JUMP_ADJ_STABLE (default: 0.05)")
    ap.add_argument("--adj_factor_change_tol", type=float, default=0.1, help="Factor change tolerance for adj/raw (default: 0.1)")

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    script_fp = sha256_file(Path(__file__))

    dq: Dict[str, Any] = {
        "fetch_ok": False,
        "insufficient_history": False,
        "stale_days_local": None,
        "split_heal_enabled": (not args.disable_split_heal),
        "split_events": [],
        "notes": [],
    }

    known_split_days = _parse_known_split_days(args.known_split_dates)
    split_window = int(args.split_date_window)

    # ----- Load prices -----
    if args.input_csv:
        data_source = "csv"
        prices_df = read_csv_prices(Path(args.input_csv), args.csv_price_col)
        price_basis = args.csv_price_col
    else:
        data_source = "yfinance"
        df = fetch_yahoo_prices(args.symbol, args.start, args.end)

        if args.use_close:
            field = "Close"
        else:
            # default prefer Adj Close if present
            field = "Adj Close" if "Adj Close" in df.columns else "Close"

        # yfinance sometimes returns MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            try:
                sub = df[field]
                if isinstance(sub, pd.DataFrame):
                    sub = sub.iloc[:, 0]
                prices_df = pd.DataFrame({"price": pd.to_numeric(sub, errors="coerce")}, index=df.index)
            except Exception:
                sub = df.iloc[:, 0]
                prices_df = pd.DataFrame({"price": pd.to_numeric(sub, errors="coerce")}, index=df.index)
        else:
            if field not in df.columns:
                field = df.columns[0]
            sub = df[field]
            if isinstance(sub, pd.DataFrame):
                sub = sub.iloc[:, 0]
            prices_df = pd.DataFrame({"price": pd.to_numeric(sub, errors="coerce")}, index=df.index)

        prices_df.index.name = "Date"
        prices_df = prices_df.dropna()
        price_basis = field

    if prices_df.empty or prices_df.iloc[:, 0].dropna().empty:
        raise RuntimeError("No usable price data loaded.")

    dq["fetch_ok"] = True

    # ----- price_raw as 1D -----
    price_raw = _to_1d_series(prices_df.iloc[:, 0], prices_df.index, "price_raw")
    if price_raw.to_numpy().ndim != 1:
        raise RuntimeError(f"price_raw not 1D after coercion: shape={price_raw.to_numpy().shape}")

    # ----- Split detection & healing (with optional whitelist gating) -----
    if args.disable_split_heal:
        price_adj = price_raw.copy()
        dq["notes"].append("Split heal disabled by --disable_split_heal.")
    else:
        try:
            factors: List[float] = []
            for tok in str(args.split_factors).split(","):
                tok = tok.strip()
                if tok:
                    factors.append(float(tok))
            if not factors:
                factors = [4.0]
        except Exception:
            factors = [4.0]

        price_adj, events = detect_and_heal_splits(
            price_raw,
            factors=factors,
            tol=float(args.split_tol),
            known_split_days=known_split_days if known_split_days else None,
            split_date_window=split_window,
        )
        dq["split_events"] = events

        healed_cnt = sum(1 for e in events if e.get("healed") is True)
        detected_cnt = len(events)

        if known_split_days:
            dq["notes"].append(
                f"Split heal whitelist active: known_split_dates={sorted([str(d.date()) for d in known_split_days])} window=±{split_window}d"
            )

        if detected_cnt == 0:
            dq["notes"].append(
                f"Split heal enabled but no events detected (factors={factors}, tol={args.split_tol})"
            )
        else:
            dq["notes"].append(
                f"Split events detected={detected_cnt}, healed={healed_cnt} (factors={factors}, tol={args.split_tol})"
            )
            if healed_cnt == 0 and known_split_days:
                dq["notes"].append(
                    "NOTE: All detected split-like events were outside known_split_dates window; no healing applied."
                )

    # Persist raw/adj prices for audit
    prices_out = pd.DataFrame(
        {
            "Date": pd.to_datetime(prices_df.index).date.astype(str),
            "price_raw": price_raw.to_numpy(dtype=float),
            "price_adj": price_adj.to_numpy(dtype=float),
        }
    )
    prices_out.to_csv(cache_dir / "prices.csv", index=False)

    # ----- DQ audits: gaps/jumps/factors -----
    audit_params = {
        "gap_busdays_warn": int(args.gap_busdays_warn),
        "ret_jump_raw": float(args.ret_jump_raw),
        "ret_jump_adj": float(args.ret_jump_adj),
        "raw_jump_thr": float(args.raw_jump_thr),
        "adj_stable_thr": float(args.adj_stable_thr),
        "adj_factor_change_tol": float(args.adj_factor_change_tol),
    }
    audit = run_gap_jump_factor_audit(price_raw=price_raw, price_adj=price_adj, params=audit_params)

    # Merge audit into dq
    dq.update(audit)
    dq["notes"].append("Gap audit uses weekday heuristic only (market holidays not modeled).")

    ga = dq.get("gap_audit", {})
    if isinstance(ga, dict):
        if int(ga.get("gap_count", 0)) > 0:
            dq["notes"].append(f"GAP_WARNING: missing business days detected (count={ga.get('gap_count')})")
        if int(ga.get("jump_count", 0)) > 0:
            dq["notes"].append(f"JUMP_WARNING: return jumps detected (count={ga.get('jump_count')})")
        if int(ga.get("factor_change_count", 0)) > 0:
            dq["notes"].append(f"FACTOR_WARNING: raw/adj factor changes detected (count={ga.get('factor_change_count')})")

    # ----- Compute indicators on price_adj -----
    price = _to_1d_series(price_adj, prices_df.index, "price")

    if args.use_logclose:
        base = np.log(price)
        bb_base_label = "log(price_adj)"
    else:
        base = price.copy()
        bb_base_label = "price_adj"

    win = int(args.window)
    horizon = int(args.horizon)

    if len(base) < win + horizon + 5:
        dq["insufficient_history"] = True
        dq["notes"].append(
            f"Insufficient length: need roughly window+horizon; len={len(base)}, window={win}, horizon={horizon}"
        )

    base = _to_1d_series(base, prices_df.index, "bb_base")

    sma = base.rolling(window=win, min_periods=win).mean()
    std = base.rolling(window=win, min_periods=win).std(ddof=0)

    upper = sma + float(args.k) * std
    lower = sma - float(args.k) * std

    z = (base - sma) / std
    band_w = upper - lower
    pos = (base - lower) / band_w

    if args.use_logclose:
        lower_px = np.exp(lower)
        upper_px = np.exp(upper)
        dist_to_lower = (price - lower_px) / price
        dist_to_upper = (upper_px - price) / price
    else:
        dist_to_lower = (price - lower) / price
        dist_to_upper = (upper - price) / price

    price_np = np.asarray(price.to_numpy()).astype(float).reshape(-1)
    fwd_mdd = calc_forward_mdd(price_np, horizon)

    # Coerce all to 1D series
    sma = _to_1d_series(sma, prices_df.index, "sma")
    std = _to_1d_series(std, prices_df.index, "std")
    upper = _to_1d_series(upper, prices_df.index, "upper")
    lower = _to_1d_series(lower, prices_df.index, "lower")
    z = _to_1d_series(z, prices_df.index, "z")
    pos = _to_1d_series(pos, prices_df.index, "pos")
    dist_to_lower = _to_1d_series(dist_to_lower, prices_df.index, "dist_to_lower")
    dist_to_upper = _to_1d_series(dist_to_upper, prices_df.index, "dist_to_upper")
    fwd_mdd_s = _to_1d_series(fwd_mdd, prices_df.index, "forward_mdd")

    # ----- Age calculation (local) -----
    last_dt = pd.to_datetime(prices_df.index[-1]).date()
    today_local = local_today(args.tz)
    dq["stale_days_local"] = int((today_local - last_dt).days)

    # ----- Build lite history -----
    out_df = pd.DataFrame(
        {
            "price": price,
            "bb_base": base,
            "sma": sma,
            "std": std,
            "upper": upper,
            "lower": lower,
            "z": z,
            "pos": pos,
            "dist_to_lower": dist_to_lower,
            "dist_to_upper": dist_to_upper,
            "forward_mdd": fwd_mdd_s,
        },
        index=prices_df.index,
    )

    lite = out_df.tail(int(args.history_limit)).copy()
    lite = lite.reset_index().rename(columns={"Date": "date"})
    lite["date"] = pd.to_datetime(lite["date"]).dt.date.astype(str)

    history_lite = []
    for _, r in lite.iterrows():
        history_lite.append(
            {
                "date": r["date"],
                "price": None if not np.isfinite(r["price"]) else float(r["price"]),
                "sma": None if not np.isfinite(r["sma"]) else float(r["sma"]),
                "std": None if not np.isfinite(r["std"]) else float(r["std"]),
                "upper": None if not np.isfinite(r["upper"]) else float(r["upper"]),
                "lower": None if not np.isfinite(r["lower"]) else float(r["lower"]),
                "z": None if not np.isfinite(r["z"]) else float(r["z"]),
                "pos": None if not np.isfinite(r["pos"]) else float(r["pos"]),
                "dist_to_lower": None if not np.isfinite(r["dist_to_lower"]) else float(r["dist_to_lower"]),
                "dist_to_upper": None if not np.isfinite(r["dist_to_upper"]) else float(r["dist_to_upper"]),
                "forward_mdd": None if not np.isfinite(r["forward_mdd"]) else float(r["forward_mdd"]),
            }
        )
    write_json(cache_dir / "history_lite.json", history_lite)

    # ----- Latest snapshot -----
    last_row = out_df.iloc[-1]
    z_last = None if not np.isfinite(last_row["z"]) else float(last_row["z"])
    state, state_reason = bb_state_from_z(z_last)

    # ----- forward_mdd stats (direction-complete) -----
    mdd_all = out_df["forward_mdd"].to_numpy()
    z_arr = out_df["z"].to_numpy()

    stats_all = compute_mdd_stats(mdd_all)

    # Cheap-side
    z_cheap = float(args.z_threshold)
    mask_cheap = np.isfinite(mdd_all) & np.isfinite(z_arr) & (z_arr <= z_cheap)
    stats_cheap = compute_mdd_stats(out_df.loc[mask_cheap, "forward_mdd"].to_numpy())
    stats_cheap["condition"] = f"z <= {z_cheap}"
    stats_cheap["z_threshold"] = z_cheap

    # Hot-side
    z_hot = float(args.z_hot)
    mask_hot = np.isfinite(mdd_all) & np.isfinite(z_arr) & (z_arr >= z_hot)
    stats_hot = compute_mdd_stats(out_df.loc[mask_hot, "forward_mdd"].to_numpy())
    stats_hot["condition"] = f"z >= {z_hot}"
    stats_hot["z_threshold"] = z_hot

    # Extreme hot-side
    z_hot2 = float(args.z_hot2)
    mask_hot2 = np.isfinite(mdd_all) & np.isfinite(z_arr) & (z_arr >= z_hot2)
    stats_hot2 = compute_mdd_stats(out_df.loc[mask_hot2, "forward_mdd"].to_numpy())
    stats_hot2["condition"] = f"z >= {z_hot2}"
    stats_hot2["z_threshold"] = z_hot2

    # Repro command (include known_split gating only if set)
    repro_parts = [
        "python",
        str(Path(__file__)),
        f"--symbol {args.symbol}",
        f"--window {int(args.window)}",
        f"--k {float(args.k)}",
        f"--horizon {int(args.horizon)}",
        f"--cache_dir {str(Path(args.cache_dir))}",
        "--use_close" if args.use_close else "--use_adj_close",
        "--use_logclose" if args.use_logclose else "",
        f"--split_factors {args.split_factors}",
        f"--split_tol {float(args.split_tol)}",
        "--disable_split_heal" if args.disable_split_heal else "",
        (f"--known_split_dates {args.known_split_dates}" if str(args.known_split_dates).strip() else ""),
        (f"--split_date_window {int(args.split_date_window)}" if str(args.known_split_dates).strip() else ""),
        f"--z_threshold {float(args.z_threshold)}",
        f"--z_hot {float(args.z_hot)}",
        f"--z_hot2 {float(args.z_hot2)}",
        f"--gap_busdays_warn {int(args.gap_busdays_warn)}",
        f"--ret_jump_raw {float(args.ret_jump_raw)}",
        f"--ret_jump_adj {float(args.ret_jump_adj)}",
        f"--raw_jump_thr {float(args.raw_jump_thr)}",
        f"--adj_stable_thr {float(args.adj_stable_thr)}",
        f"--adj_factor_change_tol {float(args.adj_factor_change_tol)}",
    ]
    repro_cmd = " ".join([p for p in repro_parts if p]).strip()

    stats_latest = {
        "meta": {
            "run_ts_utc": utc_now_iso(),
            "module": "tw0050_bb",
            "symbol": args.symbol,
            "data_source": data_source,
            "price_basis": price_basis,
            "bb_base": bb_base_label,
            "window": int(args.window),
            "k": float(args.k),
            "horizon": int(args.horizon),
            "script_fingerprint": script_fp,
            "timezone_local": args.tz,
            "as_of_date": str(last_dt),
            "split_factors": str(args.split_factors),
            "split_tol": float(args.split_tol),
            "known_split_dates": str(args.known_split_dates),
            "split_date_window": int(args.split_date_window),
            "z_threshold_cheap": float(args.z_threshold),
            "z_threshold_hot": float(args.z_hot),
            "z_threshold_hot2": float(args.z_hot2),
            # dq thresholds
            "gap_busdays_warn": int(args.gap_busdays_warn),
            "ret_jump_raw": float(args.ret_jump_raw),
            "ret_jump_adj": float(args.ret_jump_adj),
            "raw_jump_thr": float(args.raw_jump_thr),
            "adj_stable_thr": float(args.adj_stable_thr),
            "adj_factor_change_tol": float(args.adj_factor_change_tol),
        },
        "dq": dq,
        "latest": {
            "date": str(last_dt),
            "price": None if not np.isfinite(last_row["price"]) else float(last_row["price"]),
            "sma": None if not np.isfinite(last_row["sma"]) else float(last_row["sma"]),
            "std": None if not np.isfinite(last_row["std"]) else float(last_row["std"]),
            "upper": None if not np.isfinite(last_row["upper"]) else float(last_row["upper"]),
            "lower": None if not np.isfinite(last_row["lower"]) else float(last_row["lower"]),
            "z": z_last,
            "pos": None if not np.isfinite(last_row["pos"]) else float(last_row["pos"]),
            "dist_to_lower_pct": None if not np.isfinite(last_row["dist_to_lower"]) else float(last_row["dist_to_lower"] * 100.0),
            "dist_to_upper_pct": None if not np.isfinite(last_row["dist_to_upper"]) else float(last_row["dist_to_upper"] * 100.0),
            "state": state,
            "state_reason": state_reason,
        },
        "forward_mdd": {
            "definition": "min(0, min_{i=1..H} (price[t+i]/price[t]-1)), H=horizon trading days",
            "all_days": stats_all,
            "conditional": {
                "cheap_side": stats_cheap,
                "hot_side": stats_hot,
                "hot_side_extreme": stats_hot2,
            },
        },
        "repro": {"command": repro_cmd},
    }

    write_json(Path(args.cache_dir) / "stats_latest.json", stats_latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())