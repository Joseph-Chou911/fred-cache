#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TW0050 Bollinger Bands (window=60, k=2) + forward MDD (20 trading days)

Data source:
- Default: Yahoo Finance via yfinance (symbol: 0050.TW)
- Optional: user-provided CSV (Date + Close/Adj Close)

Outputs (in --cache_dir):
- stats_latest.json         : latest-day snapshot + forward_mdd distribution stats
- history_lite.json         : last N rows of daily metrics (lite)
- prices.csv                : fetched price table (audit/debug)

Key robustness fix:
- Force all vectors (price/sma/std/upper/lower/z/pos/dist/forward_mdd) into 1D Series.
  This prevents pandas ValueError: "Data must be 1-dimensional, got ndarray of shape (n, 1)".
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
        # Align to index; if mismatch, rebuild with provided index
        if len(s) != len(index):
            arr = np.asarray(s.to_numpy()).reshape(-1)
            s = pd.Series(arr, index=index, name=name)
        else:
            s = s.reindex(index)
    else:
        arr = np.asarray(x).reshape(-1)  # crucial: (n,1) -> (n,)
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


def percentile_safe(x: np.ndarray, q: float) -> Optional[float]:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.percentile(x, q))


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
    ap.add_argument("--z_threshold", type=float, default=-1.5, help="Condition for forward_mdd stats (default: -1.5)")
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

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    run_ts_utc = utc_now_iso()
    script_fp = sha256_file(Path(__file__))

    dq: Dict[str, Any] = {
        "fetch_ok": False,
        "insufficient_history": False,
        "stale_days_local": None,
        "notes": [],
    }

    # ----- Load prices -----
    if args.input_csv:
        data_source = "csv"
        prices_df = read_csv_prices(Path(args.input_csv), args.csv_price_col)
        price_basis = args.csv_price_col
    else:
        data_source = "yfinance"
        df = fetch_yahoo_prices(args.symbol, args.start, args.end)

        # Choose field
        if args.use_close:
            field = "Close"
        else:
            # Prefer Adj Close if available (and either flag set or default)
            field = "Adj Close" if "Adj Close" in df.columns else "Close"

        # If MultiIndex columns (rare but can happen), try best-effort flatten
        if isinstance(df.columns, pd.MultiIndex):
            # common pattern: ('Adj Close', '0050.TW') etc.
            # pick the first matching field level
            try:
                sub = df[field]
                # sub can still be DataFrame if multiple tickers/levels
                if isinstance(sub, pd.DataFrame):
                    sub = sub.iloc[:, 0]
                prices_df = pd.DataFrame({"price": pd.to_numeric(sub, errors="coerce")}, index=df.index)
            except Exception:
                # fallback: take first column as price
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

    # Persist raw prices for audit
    prices_out = prices_df.copy()
    prices_out = prices_out.reset_index()
    prices_out["Date"] = pd.to_datetime(prices_out["Date"]).dt.date.astype(str)
    prices_out.to_csv(cache_dir / "prices.csv", index=False)

    # ----- Force price into 1D Series (critical fix) -----
    price = _to_1d_series(prices_df.iloc[:, 0], prices_df.index, "price")
    # sanity check: must be 1D
    if price.to_numpy().ndim != 1:
        raise RuntimeError(f"price not 1D after coercion: shape={price.to_numpy().shape}")

    # ----- Compute indicators -----
    if args.use_logclose:
        base = np.log(price)
        bb_base_label = "log(price)"
    else:
        base = price.copy()
        bb_base_label = "price"

    win = int(args.window)
    horizon = int(args.horizon)

    if len(base) < win + horizon + 5:
        dq["insufficient_history"] = True
        dq["notes"].append(
            f"Insufficient length: need roughly window+horizon; len={len(base)}, window={win}, horizon={horizon}"
        )

    # Ensure base is 1D Series
    base = _to_1d_series(base, prices_df.index, "bb_base")

    sma = base.rolling(window=win, min_periods=win).mean()
    std = base.rolling(window=win, min_periods=win).std(ddof=0)  # ddof=0 to avoid small-sample inflation

    upper = sma + float(args.k) * std
    lower = sma - float(args.k) * std

    z = (base - sma) / std
    band_w = upper - lower
    pos = (base - lower) / band_w

    # dist in real price space (interpretability)
    if args.use_logclose:
        # upper/lower/sma in log space; convert bands back to price space for distance
        lower_px = np.exp(lower)
        upper_px = np.exp(upper)
        dist_to_lower = (price - lower_px) / price
        dist_to_upper = (upper_px - price) / price
    else:
        dist_to_lower = (price - lower) / price
        dist_to_upper = (upper - price) / price

    # forward mdd uses real price
    price_np = np.asarray(price.to_numpy()).astype(float).reshape(-1)
    fwd_mdd = calc_forward_mdd(price_np, horizon)

    # ----- Coerce all vectors to 1D Series aligned to index (critical fix) -----
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

    # ----- forward_mdd stats -----
    mdd_all = out_df["forward_mdd"].to_numpy()
    mask_cond = (
        np.isfinite(out_df["forward_mdd"].to_numpy())
        & np.isfinite(out_df["z"].to_numpy())
        & (out_df["z"].to_numpy() <= float(args.z_threshold))
    )
    mdd_cond = out_df.loc[mask_cond, "forward_mdd"].to_numpy()

    stats_all = {
        "n": int(np.isfinite(mdd_all).sum()),
        "p50": percentile_safe(mdd_all, 50),
        "p10": percentile_safe(mdd_all, 10),
        "min": None if mdd_all[np.isfinite(mdd_all)].size == 0 else float(np.min(mdd_all[np.isfinite(mdd_all)])),
        "conf": conf_from_n(int(np.isfinite(mdd_all).sum())),
    }
    stats_cond = {
        "z_threshold": float(args.z_threshold),
        "n": int(np.isfinite(mdd_cond).sum()),
        "p50": percentile_safe(mdd_cond, 50),
        "p10": percentile_safe(mdd_cond, 10),
        "min": None if mdd_cond[np.isfinite(mdd_cond)].size == 0 else float(np.min(mdd_cond[np.isfinite(mdd_cond)])),
        "conf": conf_from_n(int(np.isfinite(mdd_cond).sum())),
    }

    stats_latest = {
        "meta": {
            "run_ts_utc": run_ts_utc,
            "module": "tw0050_bb",
            "symbol": args.symbol,
            "data_source": data_source,
            "price_basis": price_basis,
            "bb_base": bb_base_label,
            "window": int(args.window),
            "k": float(args.k),
            "horizon": int(args.horizon),
            "z_threshold": float(args.z_threshold),
            "script_fingerprint": script_fp,
            "timezone_local": args.tz,
            "as_of_date": str(last_dt),
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
            "cond_on_z_le_threshold": stats_cond,
        },
        "repro": {
            "command": " ".join(
                [
                    "python",
                    str(Path(__file__)),
                    f"--symbol {args.symbol}",
                    f"--window {int(args.window)}",
                    f"--k {float(args.k)}",
                    f"--horizon {int(args.horizon)}",
                    f"--z_threshold {float(args.z_threshold)}",
                    f"--cache_dir {str(cache_dir)}",
                    "--use_close" if args.use_close else "--use_adj_close",
                    "--use_logclose" if args.use_logclose else "",
                ]
            ).strip()
        },
    }

    write_json(cache_dir / "stats_latest.json", stats_latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())