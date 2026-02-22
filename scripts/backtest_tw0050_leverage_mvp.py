#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backtest_tw0050_leverage_mvp.py

Audit-first MVP backtest for "base hold + conditional leverage leg" using BB z-score.

Stable semantics (explicit):
- Reads price series from: <cache_dir>/<price_csv> (default data.csv). NEVER overwrites it.
- base_shares = 1 / first_price  (normalized base equity starts at 1.0)
- leverage leg uses constant shares:
    lever_shares_target = base_shares * leverage_frac
  On entry:
    borrow_principal = lever_shares_target * entry_price
    lever_shares = lever_shares_target
    cash unchanged (0.0 at entry; later becomes negative due to interest accrual)
  Daily equity mark-to-market:
    equity = (base_shares + lever_shares) * price + cash - borrow_principal

Critical policy decisions (documented for audit):
- same-day reentry: NOT allowed. If we exit on day i, we do not re-enter on the same day.
- interest accrual: row-based accrual while in position; includes the first row after entry
  (may be interpreted as entry-day accrual depending on timing assumption).
- end-of-data handling: if a leveraged position is still open at the end, we FORCE-CLOSE at last row
  with exit_reason="end_of_data" and include it in trades.

Trade semantics note:
- lever_leg_pnl is GROSS P&L for the leverage leg (proceeds - principal), does NOT include interest.
  net_lever_pnl = lever_leg_pnl - interest_paid
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

SCRIPT_FINGERPRINT = "backtest_tw0050_leverage_mvp@2026-02-22.v11.auditnotes_mddle0_pricecolwarn_grosspnl_note"

TRADE_COLS = [
    "entry_date",
    "entry_price",
    "entry_z",
    "borrow_principal",
    "lever_shares",
    "interest_paid",
    "exit_date",
    "exit_price",
    "hold_days",
    "exit_reason",
    "lever_leg_pnl",
]

_DEFAULT_RATIO_HI = 1.8
_DEFAULT_RATIO_LO = round(1.0 / _DEFAULT_RATIO_HI, 10)  # symmetric inverse


# ---------- utils ----------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    _ensure_parent(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not path or (not os.path.isfile(path)):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _normalize_date_col(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns:
        for c in ["Date", "DATE", "timestamp", "time", "Time"]:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break
    if "date" not in df.columns:
        raise SystemExit("ERROR: price csv missing date column (date/Date/DATE/time/timestamp)")

    df["date_ts"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_ts"]).copy()
    df = df.sort_values("date_ts").reset_index(drop=True)
    df["date"] = df["date_ts"].dt.date.astype(str)
    return df


def _find_price_col(df: pd.DataFrame, user_col: Optional[str]) -> str:
    if user_col:
        if user_col not in df.columns:
            raise SystemExit(f"ERROR: --price_col '{user_col}' not found in csv columns")
        return user_col

    cands = ["adjclose", "adj_close", "adj close", "adjClose", "Adj Close", "close", "Close"]
    cols_lc = {c.lower(): c for c in df.columns}
    for k in cands:
        if k.lower() in cols_lc:
            return cols_lc[k.lower()]

    # Fallback (best-effort): pick first numeric column (warn loudly).
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            print(f"WARNING: price_col not specified; falling back to first numeric column: {c!r}")
            return c

    raise SystemExit("ERROR: no numeric price column found in csv")


def _calc_bb_z(price: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=ddof)
    sd = sd.replace(0.0, np.nan)
    z = (price - ma) / sd
    z = z.replace([np.inf, -np.inf], np.nan)
    return z


def _daily_interest(principal: float, apr: float, trading_days: int) -> float:
    if principal <= 0.0 or apr <= 0.0 or trading_days <= 0:
        return 0.0
    return float(principal) * float(apr) / float(trading_days)


def _to_finite_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return v


def _safe_label(x: Any) -> str:
    try:
        if isinstance(x, pd.Timestamp):
            return x.date().isoformat()
    except Exception:
        pass
    return str(x)


def _max_drawdown(eq: pd.Series) -> Dict[str, Any]:
    """
    Max drawdown on equity series.
    NOTE: We DO NOT forward-fill NaN (to avoid masking real gaps).
    We only convert non-finite to NaN and use nan-aware argmin/argmax.
    """
    if eq is None or len(eq) == 0:
        return {"mdd": None, "peak": None, "trough": None}

    v = pd.to_numeric(eq, errors="coerce").to_numpy(dtype=float)
    v2 = np.where(np.isfinite(v), v, np.nan)

    if np.all(np.isnan(v2)):
        return {"mdd": None, "peak": None, "trough": None}

    running_max = np.maximum.accumulate(np.where(np.isnan(v2), -np.inf, v2))
    running_max = np.where(running_max == -np.inf, np.nan, running_max)
    # v11: defensive guard — disallow non-positive running_max to avoid undefined/ambiguous ratios
    running_max = np.where(running_max <= 0.0, np.nan, running_max)

    dd = (v2 / running_max) - 1.0

    if np.all(np.isnan(dd)):
        return {"mdd": None, "peak": None, "trough": None}

    trough_pos = int(np.nanargmin(dd))
    mdd = float(dd[trough_pos])

    if not np.isfinite(mdd):
        return {"mdd": None, "peak": None, "trough": None}

    if mdd == 0.0:
        return {"mdd": 0.0, "peak": "N/A", "trough": "N/A", "peak_pos": 0, "trough_pos": 0}

    peak_slice = v2[: trough_pos + 1]
    if np.all(np.isnan(peak_slice)):
        return {"mdd": mdd, "peak": None, "trough": None, "peak_pos": None, "trough_pos": trough_pos}

    peak_pos = int(np.nanargmax(peak_slice))

    idx = eq.index
    peak_label = _safe_label(idx[peak_pos]) if len(idx) > peak_pos else None
    trough_label = _safe_label(idx[trough_pos]) if len(idx) > trough_pos else None

    out = {
        "mdd": mdd,
        "peak": peak_label,
        "trough": trough_label,
        "peak_pos": peak_pos,
        "trough_pos": trough_pos,
    }

    if mdd < -1.0:
        out["mdd_warning"] = "equity went negative; mdd < -1.0 is arithmetically valid but may be misleading"

    return out


def _perf_summary(eq: pd.Series, trading_days: int = 252) -> Dict[str, Any]:
    # NOTE: equity series is mark-to-market; end-of-data force-close does NOT create a discontinuity
    # because the last equity point already reflects lever_shares * last_price - borrow_principal + cash.
    eq = pd.to_numeric(eq, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if eq.empty or len(eq) < 3:
        return {"ok": False}

    start = float(eq.iloc[0])
    end = float(eq.iloc[-1])
    n = int(len(eq))
    years = max((n - 1) / float(trading_days), 1e-12)

    cagr = None
    cagr_warning = None
    if start > 0 and end > 0:
        cagr = (end / start) ** (1.0 / years) - 1.0
    else:
        cagr = None
        if start > 0 and end <= 0:
            cagr_warning = "end <= 0; CAGR undefined (negative/zero terminal equity)"
        elif start <= 0:
            cagr_warning = "start <= 0; CAGR undefined"

    rets = eq.pct_change().dropna()
    vol = float(rets.std(ddof=0) * math.sqrt(trading_days)) if len(rets) > 2 else None
    sharpe = (
        (float(rets.mean()) / float(rets.std(ddof=0))) * math.sqrt(trading_days)
        if (len(rets) > 2 and float(rets.std(ddof=0)) > 0)
        else None
    )

    mdd_info = _max_drawdown(eq)

    out = {
        "ok": True,
        "start": start,
        "end": end,
        "n_days": n,
        "years": years,
        "cagr": cagr,
        "vol_ann": vol,
        "sharpe0": sharpe,
        "sharpe_note": "rf=0 assumed",
        "mdd": mdd_info.get("mdd"),
        "mdd_peak": mdd_info.get("peak"),
        "mdd_trough": mdd_info.get("trough"),
        "mdd_warning": mdd_info.get("mdd_warning"),
    }
    if cagr_warning is not None:
        out["cagr_warning"] = cagr_warning
    return out


# ---------- break detection / contamination ----------

def detect_breaks_from_price(df: pd.DataFrame, ratio_hi: float, ratio_lo: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if df is None or len(df) < 2:
        return out

    px = pd.to_numeric(df["price"], errors="coerce").to_numpy(dtype=float)
    dates = df["date"].astype(str).to_numpy()

    for i in range(1, len(px)):
        p0 = float(px[i - 1])
        p1 = float(px[i])
        if not np.isfinite(p0) or not np.isfinite(p1) or p0 <= 0.0:
            continue
        r = p1 / p0
        if (r >= float(ratio_hi)) or (r <= float(ratio_lo)):
            out.append(
                {
                    "idx": int(i),
                    "break_date": str(dates[i]),
                    "prev_date": str(dates[i - 1]),
                    "prev_price": p0,
                    "price": p1,
                    "ratio": float(r),
                }
            )
    return out


def _extract_break_samples_from_stats(stats: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not isinstance(stats, dict):
        return [], None

    cand_paths = [
        ("dq", "break_samples"),
        ("dq", "breaks"),
        ("break_detection", "samples"),
        ("break_detection", "break_samples"),
        ("price_series_breaks",),
    ]

    for p in cand_paths:
        cur: Any = stats
        ok = True
        for k in p:
            if isinstance(cur, dict) and (k in cur):
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, list) and all(isinstance(x, dict) for x in cur):
            return cur, ".".join(p)

    return [], None


def align_break_indices(df: pd.DataFrame, raw_breaks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not raw_breaks:
        return []

    date_to_idx = {str(d): int(i) for i, d in enumerate(df["date"].astype(str).tolist())}
    px = pd.to_numeric(df["price"], errors="coerce").to_numpy(dtype=float)
    dates = df["date"].astype(str).to_numpy()

    out: List[Dict[str, Any]] = []
    for b in raw_breaks:
        if not isinstance(b, dict):
            continue

        idx: Optional[int] = None
        if "idx" in b:
            try:
                idx = int(b["idx"])
            except Exception:
                idx = None
        if idx is None:
            bd = b.get("break_date", b.get("date", None))
            if bd is not None:
                idx = date_to_idx.get(str(bd))

        if idx is None or idx <= 0 or idx >= len(df):
            continue

        prev_i = idx - 1
        p0 = float(px[prev_i]) if np.isfinite(px[prev_i]) else None
        p1 = float(px[idx]) if np.isfinite(px[idx]) else None
        ratio = None
        if p0 is not None and p1 is not None and p0 > 0:
            ratio = float(p1 / p0)

        out.append(
            {
                "idx": int(idx),
                "break_date": str(dates[idx]),
                "prev_date": str(dates[prev_i]),
                "prev_price": p0,
                "price": p1,
                "ratio": float(b.get("ratio", ratio)) if (b.get("ratio", ratio) is not None) else None,
            }
        )

    out.sort(key=lambda x: x["idx"])
    return out


def build_entry_forbidden_mask(
    n: int,
    breaks: List[Dict[str, Any]],
    contam_horizon: int,
    z_clear_days: int,
) -> List[bool]:
    forbid = [False] * int(n)
    if n <= 0 or not breaks:
        return forbid

    ch = max(int(contam_horizon), 0)
    zc = max(int(z_clear_days), 0)

    for b in breaks:
        try:
            bi = int(b["idx"])
        except Exception:
            continue
        lo = max(bi - ch, 0)
        hi = min(bi + zc - 1, n - 1)  # inclusive
        for i in range(lo, hi + 1):
            forbid[i] = True
    return forbid


# ---------- backtest core ----------

@dataclass
class Params:
    bb_window: int
    bb_ddof: int
    entry_z: float
    exit_z: float
    leverage_frac: float
    borrow_apr: float
    max_hold_days: int
    trading_days: int
    skip_contaminated: bool
    contam_horizon: int
    z_clear_days: int


def run_backtest(
    df: pd.DataFrame,
    params: Params,
    forbid_entry_mask: Optional[List[bool]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = df.copy()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"]).copy()
    df = df.sort_values("date_ts").reset_index(drop=True)

    n = int(len(df))
    if n < params.bb_window + 5:
        raise SystemExit("ERROR: not enough rows for bb window")

    df["bb_z"] = _calc_bb_z(df["price"], window=params.bb_window, ddof=params.bb_ddof)

    p0 = float(df["price"].iloc[0])
    if not np.isfinite(p0) or p0 <= 0.0:
        raise SystemExit("ERROR: invalid first price")

    base_shares = 1.0 / p0
    lever_shares_target = max(float(base_shares) * float(params.leverage_frac), 0.0)

    prices = df["price"].to_numpy(dtype=float)
    zs = df["bb_z"].to_numpy(dtype=float)  # NaN stays as np.nan
    dates = df["date"].astype(str).to_numpy()

    lever_shares = 0.0
    borrow_principal = 0.0
    cash = 0.0
    in_lever = False
    hold_days = 0  # entry day sets 0; next row becomes 1
    interest_paid_total = 0.0

    trades: List[Dict[str, Any]] = []
    cur_trade: Optional[Dict[str, Any]] = None

    eq_arr = np.empty(n, dtype=float)
    base_arr = np.empty(n, dtype=float)
    lev_on_arr = np.empty(n, dtype=bool)

    skipped_entries_on_forbidden = 0
    skipped_entries_on_nonpositive_equity = 0
    exit_count_by_z = 0
    exit_count_by_time = 0
    forced_eod_close = 0

    forbid = forbid_entry_mask if (forbid_entry_mask is not None and len(forbid_entry_mask) == n) else [False] * n

    for i in range(n):
        price = float(prices[i])
        z_raw = float(zs[i])  # may be nan
        date = str(dates[i])

        # 1) accrue interest (row-based)
        if in_lever and borrow_principal > 0.0:
            interest = _daily_interest(borrow_principal, params.borrow_apr, params.trading_days)
            cash -= interest
            interest_paid_total += interest
            if cur_trade is not None:
                cur_trade["interest_paid"] = float(cur_trade.get("interest_paid", 0.0) + interest)

        # 2) mark-to-market
        total_shares = base_shares + lever_shares
        equity_now = total_shares * price + cash - borrow_principal
        base_now = base_shares * price

        eq_arr[i] = float(equity_now)
        base_arr[i] = float(base_now)
        lev_on_arr[i] = bool(in_lever)

        # 3) exit logic (even if z is NaN)
        if in_lever:
            hold_days += 1
            exit_by_time = (params.max_hold_days > 0 and hold_days >= params.max_hold_days)

            zf = _to_finite_float(z_raw)
            exit_by_z = (zf is not None and zf >= float(params.exit_z))

            if exit_by_z or exit_by_time:
                proceeds = lever_shares * price
                cash += proceeds
                cash -= borrow_principal

                if cur_trade is not None:
                    cur_trade["exit_date"] = date
                    cur_trade["exit_price"] = price
                    cur_trade["hold_days"] = int(hold_days)
                    cur_trade["exit_reason"] = "exit_z" if exit_by_z else "max_hold_days"
                    # gross P&L (interest excluded; see module docstring)
                    cur_trade["lever_leg_pnl"] = float(proceeds - float(cur_trade.get("borrow_principal", 0.0)))
                    trades.append(cur_trade)

                if exit_by_z:
                    exit_count_by_z += 1
                else:
                    exit_count_by_time += 1

                borrow_principal = 0.0
                lever_shares = 0.0
                in_lever = False
                cur_trade = None
                hold_days = 0

                # Policy: no same-day reentry
                continue

        # 4) entry logic needs finite z
        zf_entry = _to_finite_float(z_raw)
        if zf_entry is None:
            continue

        if (not in_lever) and (zf_entry <= float(params.entry_z)):
            if forbid[i]:
                skipped_entries_on_forbidden += 1
                continue

            if equity_now <= 0.0:
                skipped_entries_on_nonpositive_equity += 1
                continue

            if lever_shares_target <= 0.0:
                continue

            borrow = float(lever_shares_target * price)
            if borrow <= 0.0:
                continue

            borrow_principal = borrow
            lever_shares = lever_shares_target
            in_lever = True
            hold_days = 0

            cur_trade = {
                "entry_date": date,
                "entry_price": price,
                "entry_z": zf_entry,
                "borrow_principal": float(borrow_principal),
                "lever_shares": float(lever_shares),
                "interest_paid": 0.0,
            }

    # --- Force-close any open leveraged position at end of data ---
    open_at_end = bool(in_lever)
    if in_lever and cur_trade is not None and n > 0:
        last_price = float(prices[-1])
        last_date = str(dates[-1])
        proceeds = lever_shares * last_price

        cur_trade["exit_date"] = last_date
        cur_trade["exit_price"] = last_price
        cur_trade["hold_days"] = int(hold_days)
        cur_trade["exit_reason"] = "end_of_data"
        # gross P&L (interest excluded)
        cur_trade["lever_leg_pnl"] = float(proceeds - float(cur_trade.get("borrow_principal", 0.0)))
        trades.append(cur_trade)
        forced_eod_close = 1

        in_lever = False
        borrow_principal = 0.0
        lever_shares = 0.0

    df_out = df[["date", "date_ts", "price", "bb_z"]].copy()
    df_out["equity"] = eq_arr
    df_out["equity_base_only"] = base_arr
    df_out["lever_on"] = lev_on_arr

    summary: Dict[str, Any] = {
        "generated_at_utc": utc_now_iso(),
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "params": {
            "bb_window": params.bb_window,
            "bb_ddof": params.bb_ddof,
            "entry_z": params.entry_z,
            "exit_z": params.exit_z,
            "leverage_frac": params.leverage_frac,
            "borrow_apr": params.borrow_apr,
            "max_hold_days": params.max_hold_days,
            "trading_days": params.trading_days,
            "skip_contaminated": bool(params.skip_contaminated),
            "contam_horizon": int(params.contam_horizon),
            "z_clear_days": int(params.z_clear_days),
        },
        "audit": {
            "rows": int(len(df_out)),
            "start_date": str(df_out["date"].iloc[0]),
            "end_date": str(df_out["date"].iloc[-1]),
            "interest_paid_total": float(interest_paid_total),
            "trades": int(len(trades)),
            "skipped_entries_on_forbidden": int(skipped_entries_on_forbidden),
            "skipped_entries_on_nonpositive_equity": int(skipped_entries_on_nonpositive_equity),
            "exit_count_by_z": int(exit_count_by_z),
            "exit_count_by_time": int(exit_count_by_time),
            "open_at_end": bool(open_at_end),
            "forced_eod_close": int(forced_eod_close),
            "hold_days_semantics": "entry day sets hold_days=0; increments by 1 each subsequent row while in position",
            "same_day_reentry": "not allowed; exit day is always flat",
            "interest_semantics": "row-based accrual while in position; includes the first row after entry (may be interpreted as entry-day accrual depending on timing assumption)",
            "end_of_data_policy": "if open position exists at end, force-close and record trade with exit_reason=end_of_data",
            "equity_csv_last_row_note": (
                "if open_at_end=true, last equity value is mark-to-market while still in position; "
                "numerically equivalent to post-close equity at the same last_price, but trade record is added after loop"
            ),
            "lever_leg_pnl_semantics": "gross P&L for leverage leg (proceeds - principal); net = lever_leg_pnl - interest_paid",
        },
        "perf_leverage": _perf_summary(df_out.set_index("date")["equity"], trading_days=params.trading_days),
        "perf_base_only": _perf_summary(df_out.set_index("date")["equity_base_only"], trading_days=params.trading_days),
        "trades": trades,
    }

    if summary["perf_leverage"].get("ok") and summary["perf_base_only"].get("ok"):
        a = summary["perf_leverage"]
        b = summary["perf_base_only"]
        summary["delta_vs_base"] = {
            "cagr": (a.get("cagr") - b.get("cagr")) if (a.get("cagr") is not None and b.get("cagr") is not None) else None,
            "mdd": (a.get("mdd") - b.get("mdd")) if (a.get("mdd") is not None and b.get("mdd") is not None) else None,
            "sharpe0": (a.get("sharpe0") - b.get("sharpe0")) if (a.get("sharpe0") is not None and b.get("sharpe0") is not None) else None,
        }

    return df_out, summary


# ---------- main ----------

def _add_skip_contaminated_flag(ap: argparse.ArgumentParser) -> None:
    if hasattr(argparse, "BooleanOptionalAction"):
        ap.add_argument(
            "--skip_contaminated",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="If true, forbid entry around detected breaks (default true). Use --no-skip-contaminated to disable.",
        )
    else:
        ap.add_argument("--skip_contaminated", action="store_true", default=True)
        ap.add_argument("--no_skip_contaminated", dest="skip_contaminated", action="store_false")


def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", default="data.csv")
    ap.add_argument("--stats_json", default="stats_latest.json")
    ap.add_argument("--price_col", default=None)

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_ddof", type=int, default=0)

    ap.add_argument("--entry_z", "--enter_z", dest="entry_z", type=float, default=-1.5)
    ap.add_argument("--exit_z", type=float, default=0.0)

    ap.add_argument("--leverage_frac", "--leverage_add", dest="leverage_frac", type=float, default=0.5)
    ap.add_argument("--borrow_apr", type=float, default=0.035)
    ap.add_argument("--max_hold_days", type=int, default=60)
    ap.add_argument("--trading_days", type=int, default=252)

    _add_skip_contaminated_flag(ap)
    ap.add_argument("--contam_horizon", type=int, default=60)
    ap.add_argument("--z_clear_days", type=int, default=60)
    ap.add_argument("--break_ratio_hi", type=float, default=None)
    ap.add_argument("--break_ratio_lo", type=float, default=None)

    ap.add_argument("--out_json", "--out_summary_json", dest="out_json", default="backtest_mvp.json")
    ap.add_argument("--out_equity_csv", default="backtest_mvp_equity.csv")
    ap.add_argument("--out_trades_csv", default="backtest_mvp_trades.csv")

    args = ap.parse_args()

    cache_dir = str(args.cache_dir)

    price_path = os.path.join(cache_dir, str(args.price_csv))
    if not os.path.isfile(price_path):
        raise SystemExit(f"ERROR: missing price csv: {price_path}")

    stats_path = os.path.join(cache_dir, str(args.stats_json))
    stats = _read_json(stats_path)

    ratio_hi = float(args.break_ratio_hi) if args.break_ratio_hi is not None else _DEFAULT_RATIO_HI
    ratio_lo = float(args.break_ratio_lo) if args.break_ratio_lo is not None else _DEFAULT_RATIO_LO

    if isinstance(stats, dict):
        bd = stats.get("break_detection", {})
        if isinstance(bd, dict):
            try:
                if args.break_ratio_hi is None and ("break_ratio_hi" in bd):
                    ratio_hi = float(bd["break_ratio_hi"])
            except Exception:
                pass
            try:
                if args.break_ratio_lo is None and ("break_ratio_lo" in bd):
                    ratio_lo = float(bd["break_ratio_lo"])
            except Exception:
                pass

    df_raw = pd.read_csv(price_path)
    df_raw = _normalize_date_col(df_raw)

    pc = _find_price_col(df_raw, args.price_col)
    df_raw["price"] = pd.to_numeric(df_raw[pc], errors="coerce")
    df_raw = df_raw.dropna(subset=["price"]).copy()

    if isinstance(stats, dict):
        raw_samples, break_samples_source = _extract_break_samples_from_stats(stats)
    else:
        raw_samples, break_samples_source = [], None

    raw_breaks = raw_samples if raw_samples else detect_breaks_from_price(df_raw, ratio_hi, ratio_lo)
    breaks_aligned = align_break_indices(df_raw, raw_breaks)

    forbid_mask = None
    if bool(args.skip_contaminated) and len(breaks_aligned) > 0:
        forbid_mask = build_entry_forbidden_mask(
            n=len(df_raw),
            breaks=breaks_aligned,
            contam_horizon=int(args.contam_horizon),
            z_clear_days=int(args.z_clear_days),
        )

    params = Params(
        bb_window=int(args.bb_window),
        bb_ddof=int(args.bb_ddof),
        entry_z=float(args.entry_z),
        exit_z=float(args.exit_z),
        leverage_frac=float(args.leverage_frac),
        borrow_apr=float(args.borrow_apr),
        max_hold_days=int(args.max_hold_days),
        trading_days=int(args.trading_days),
        skip_contaminated=bool(args.skip_contaminated),
        contam_horizon=int(args.contam_horizon),
        z_clear_days=int(args.z_clear_days),
    )

    df_bt, summary = run_backtest(df_raw, params, forbid_entry_mask=forbid_mask)

    summary["params"].update(
        {
            "cache_dir": cache_dir,
            "price_csv": str(args.price_csv),
            "price_csv_resolved": price_path,
            "stats_json": str(args.stats_json),
            "stats_json_resolved": stats_path if os.path.isfile(stats_path) else None,
            "price_col": str(pc),
            "break_ratio_hi": float(ratio_hi),
            "break_ratio_lo": float(ratio_lo),
            "break_ratio_policy": "ratio_lo defaults to 1/ratio_hi (symmetric inverse) unless overridden",
        }
    )

    summary["audit"].update(
        {
            "breaks_detected": int(len(breaks_aligned)),
            "break_samples_first5": breaks_aligned[:5],
            "break_samples_source": (break_samples_source or "stats_json_unknown_path") if raw_samples else "detect_breaks_from_price",
            "forbid_mask_semantics": "for each break idx b: forbid entry i in [b-contam_horizon, b+z_clear_days-1]",
        }
    )

    out_json_path = os.path.join(cache_dir, str(args.out_json))
    out_eq_path = os.path.join(cache_dir, str(args.out_equity_csv))
    out_tr_path = os.path.join(cache_dir, str(args.out_trades_csv))

    _write_json(out_json_path, summary)

    _ensure_parent(out_eq_path)
    df_bt[["date", "price", "bb_z", "equity", "equity_base_only", "lever_on"]].to_csv(
        out_eq_path, index=False, encoding="utf-8"
    )

    _ensure_parent(out_tr_path)
    trades = summary.get("trades", [])
    if isinstance(trades, list) and len(trades) > 0:
        pd.DataFrame(trades)[TRADE_COLS].to_csv(out_tr_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=TRADE_COLS).to_csv(out_tr_path, index=False, encoding="utf-8")

    print(f"OK: wrote {out_json_path}")
    print(f"OK: wrote {out_eq_path}")
    print(f"OK: wrote {out_tr_path}")


if __name__ == "__main__":
    main()