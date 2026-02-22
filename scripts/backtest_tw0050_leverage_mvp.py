#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_tw0050_leverage_mvp.py

MVP backtest: "fixed base position + opportunistic leveraged add-on"
- Base leg: always fully invested (1.0 notional at t0) using PRICE_COL (ideally adjclose).
- Leverage leg: when entry trigger fires, borrow (leverage_frac * equity) to buy extra shares.
  Exit when z >= exit_z OR max_hold_days reached.

CRITICAL FIX (v4):
- Read break_samples (or thresholds) from stats_latest.json and build a contamination mask.
- Skip entries that fall into contaminated windows to avoid trading on known broken segments
  (e.g., 2014-01-02 ratio~0.249).

Contamination mask (conservative, deterministic):
For each detected break at index b:
- forbid entry indices in [b - contam_horizon,  b + z_clear_days - 1]
  where contam_horizon defaults to max_hold_days,
        z_clear_days defaults to bb_window (rolling window contamination after break).

This aims to:
(1) prevent opening trades that could include the break during the hold window
(2) prevent using contaminated BB-z until the rolling window clears

Notes:
- This patch does NOT "heal" or adjust price levels; it only prevents contaminated entries.
- If your price series is fundamentally mis-scaled across a long segment, you still need a clean source
  for a truly valid backtest. This script will at least stop the most obvious false entries.

Outputs:
- JSON summary (out_json)
- Optional equity CSV (out_equity_csv)
- Optional trades CSV (out_trades_csv)
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


SCRIPT_FINGERPRINT = "backtest_tw0050_leverage_mvp@2026-02-22.v4.cleanmask"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.upper() in ("NA", "N/A", "NONE", "NULL"):
            return None
        return float(s)
    except Exception:
        return None


def _pick_price_col(df: pd.DataFrame, requested: str) -> str:
    req = requested.strip()
    if req in df.columns:
        return req

    # common aliases
    aliases = {
        "adjclose": ["adjclose", "adj_close", "adj close", "Adj Close", "AdjClose"],
        "close": ["close", "Close", "CLOSE"],
        "date": ["date", "Date", "DATE"],
    }

    # if requested is "adjclose", try its aliases
    key = req.lower().replace("_", "").replace(" ", "")
    for k, opts in aliases.items():
        k2 = k.lower().replace("_", "").replace(" ", "")
        if key == k2:
            for c in opts:
                if c in df.columns:
                    return c

    # otherwise try exact-ish normalize match
    norm_cols = {c.lower().replace("_", "").replace(" ", ""): c for c in df.columns}
    if key in norm_cols:
        return norm_cols[key]

    raise ValueError(f"price_col not found: requested={requested!r}, columns={list(df.columns)[:20]}...")


def load_price_csv(path: str, price_col: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"price_csv not found: {path}")

    df = pd.read_csv(path)

    # find date column
    date_col = None
    for c in ("date", "Date", "DATE"):
        if c in df.columns:
            date_col = c
            break

    if date_col is None:
        # heuristic: if first column is date-like
        c0 = df.columns[0]
        try:
            pd.to_datetime(df[c0].iloc[0])
            date_col = c0
        except Exception:
            raise ValueError("Cannot find a date column. Expect a 'date'/'Date' column or date-like first column.")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=False)
    df = df.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)
    df = df.set_index(date_col)

    pcol = _pick_price_col(df, price_col)
    px = df[pcol].apply(_safe_float)
    df = df.assign(price=px).dropna(subset=["price"])
    df = df[df["price"] > 0].copy()

    # normalize index to date (no tz) for cleaner JSON
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["price"]]


def compute_bb_z(price: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=ddof)
    z = (price - ma) / sd
    z = z.replace([float("inf"), float("-inf")], pd.NA)
    return z


def detect_breaks_from_price(
    df: pd.DataFrame, ratio_hi: float, ratio_lo: float
) -> List[Dict[str, Any]]:
    """Detect breaks by consecutive price ratio thresholds."""
    p = df["price"].values
    idx = df.index
    out: List[Dict[str, Any]] = []
    for i in range(1, len(p)):
        prev = p[i - 1]
        cur = p[i]
        if prev <= 0:
            continue
        r = cur / prev
        if r > ratio_hi or r < ratio_lo:
            out.append(
                {
                    "idx": i,
                    "break_date": idx[i].strftime("%Y-%m-%d"),
                    "prev_date": idx[i - 1].strftime("%Y-%m-%d"),
                    "prev_price": float(prev),
                    "price": float(cur),
                    "ratio": float(r),
                }
            )
    return out


def load_break_info_from_stats(stats_json_path: Optional[str]) -> Tuple[Optional[float], Optional[float], List[Dict[str, Any]]]:
    """
    Try to read:
      - break_ratio_hi / break_ratio_lo from stats_latest.json["break_detection"]
      - break_samples from various likely locations
    Returns (hi, lo, samples)
    """
    if not stats_json_path:
        return None, None, []

    if not os.path.exists(stats_json_path):
        # do not fail hard; allow fallback detection from price CSV
        return None, None, []

    with open(stats_json_path, "r", encoding="utf-8") as f:
        st = json.load(f)

    bd = st.get("break_detection") or {}
    hi = _safe_float(bd.get("break_ratio_hi"))
    lo = _safe_float(bd.get("break_ratio_lo"))

    # common places to stash samples
    samples = (
        st.get("break_samples")
        or bd.get("break_samples")
        or (st.get("dq") or {}).get("break_samples")
        or []
    )

    # normalize samples shape if present
    norm: List[Dict[str, Any]] = []
    if isinstance(samples, list):
        for s in samples:
            if isinstance(s, dict):
                # require at least break_date
                if "break_date" in s or ("date" in s and "idx" in s):
                    d = dict(s)
                    if "break_date" not in d and "date" in d:
                        d["break_date"] = d["date"]
                    norm.append(d)
    return hi, lo, norm


def align_break_indices(df: pd.DataFrame, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure each sample has a valid integer 'idx' aligned to df row positions.
    If sample idx exists but date mismatches, re-align by date.
    If sample idx missing, align by break_date.
    """
    out: List[Dict[str, Any]] = []
    date_to_pos = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(df.index)}
    for s in samples:
        d = dict(s)
        bdate = str(d.get("break_date", "")).strip()
        s_idx = d.get("idx", None)
        idx_pos: Optional[int] = None

        if s_idx is not None:
            try:
                idx_pos = int(s_idx)
                if 0 <= idx_pos < len(df):
                    # verify date
                    df_date = df.index[idx_pos].strftime("%Y-%m-%d")
                    if bdate and df_date != bdate and bdate in date_to_pos:
                        idx_pos = date_to_pos[bdate]
                else:
                    idx_pos = None
            except Exception:
                idx_pos = None

        if idx_pos is None:
            if bdate and bdate in date_to_pos:
                idx_pos = date_to_pos[bdate]

        if idx_pos is None:
            # skip unalignable
            continue

        d["idx"] = int(idx_pos)
        if not bdate:
            d["break_date"] = df.index[idx_pos].strftime("%Y-%m-%d")
        out.append(d)
    return out


def build_entry_forbidden_mask(
    n: int,
    breaks: List[Dict[str, Any]],
    contam_horizon: int,
    z_clear_days: int,
) -> List[bool]:
    """
    forbid entry indices in [b - contam_horizon, b + z_clear_days - 1] for each break b
    (inclusive range).
    """
    forbid = [False] * n
    for b in breaks:
        bi = int(b["idx"])
        start = max(0, bi - int(contam_horizon))
        end = min(n - 1, bi + int(z_clear_days) - 1)
        for i in range(start, end + 1):
            forbid[i] = True
    return forbid


def _max_drawdown(eq: pd.Series) -> Tuple[float, str, str]:
    """
    Return (mdd, peak_date, trough_date).
    mdd is <= 0 (e.g., -0.25 means -25%).
    Robust to datetime index (no int() casting of idxmin()).
    """
    if eq.empty:
        return float("nan"), "N/A", "N/A"

    v = eq.values.astype(float)
    n = len(v)
    running_max = v[0]
    running_max_i = 0

    best_dd = 0.0
    best_peak_i = 0
    best_trough_i = 0

    for i in range(1, n):
        if v[i] > running_max:
            running_max = v[i]
            running_max_i = i
        dd = (v[i] / running_max) - 1.0
        if dd < best_dd:
            best_dd = dd
            best_peak_i = running_max_i
            best_trough_i = i

    peak_date = eq.index[best_peak_i].strftime("%Y-%m-%d")
    trough_date = eq.index[best_trough_i].strftime("%Y-%m-%d")
    return float(best_dd), peak_date, trough_date


def _perf(eq: pd.Series, trading_days: int) -> Dict[str, Any]:
    if eq.empty:
        return {"ok": False}

    start = float(eq.iloc[0])
    end = float(eq.iloc[-1])
    n_days = int(len(eq))
    years = n_days / float(trading_days) if trading_days > 0 else float("nan")

    cagr = float("nan")
    if years and years > 0 and start > 0 and end > 0:
        cagr = (end / start) ** (1.0 / years) - 1.0

    rets = eq.pct_change().fillna(0.0)
    mu = float(rets.mean())
    sd = float(rets.std(ddof=0))
    vol_ann = sd * math.sqrt(trading_days) if trading_days > 0 else float("nan")
    sharpe0 = (mu / sd) * math.sqrt(trading_days) if (sd > 0 and trading_days > 0) else float("nan")

    mdd, peak, trough = _max_drawdown(eq)

    return {
        "ok": True,
        "start": start,
        "end": end,
        "n_days": n_days,
        "years": years,
        "cagr": cagr,
        "vol_ann": vol_ann,
        "sharpe0": sharpe0,
        "mdd": mdd,
        "mdd_peak": peak,
        "mdd_trough": trough,
    }


@dataclass
class Position:
    entry_i: int
    entry_date: str
    entry_price: float
    entry_z: float
    borrow_principal: float
    lever_shares: float


def run_backtest(
    df: pd.DataFrame,
    z: pd.Series,
    forbid_entry: List[bool],
    entry_z: float,
    exit_z: float,
    leverage_frac: float,
    borrow_apr: float,
    max_hold_days: int,
    trading_days: int,
) -> Tuple[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Returns:
      df_bt: columns [price, z, eq_base, eq_leverage]
      summary: perf + audit
      trades: list of trade dicts
    """
    price = df["price"]
    idx = df.index
    n = len(df)

    # Base leg: always in the market
    base_shares = 1.0 / float(price.iloc[0])
    eq_base = base_shares * price

    # Leverage leg state
    pos: Optional[Position] = None
    interest_paid_total = 0.0
    trades: List[Dict[str, Any]] = []
    skipped_entries = 0

    # For "crossing" logic: only enter on first day crossing into <= entry_z
    prev_z = float("nan")

    # Preallocate equity series for leverage
    eq_lev = pd.Series(index=idx, dtype=float)

    for i in range(n):
        p = float(price.iloc[i])
        zi = z.iloc[i]
        zi_f = float(zi) if pd.notna(zi) else float("nan")

        base_val = float(eq_base.iloc[i])

        # Compute equity under current position state (mark-to-market)
        if pos is None:
            eq_lev.iloc[i] = base_val
        else:
            hold_days = i - pos.entry_i
            interest_accrued = pos.borrow_principal * borrow_apr * (hold_days / float(trading_days))
            lever_val = pos.lever_shares * p
            eq_lev.iloc[i] = base_val + lever_val - pos.borrow_principal - interest_accrued

        # Decide exits/entries at end of day i (using today's z)
        if pos is not None:
            hold_days = i - pos.entry_i
            exit_reason = None

            # If we ever step into a forbidden region while holding, force exit to avoid using broken segment
            if forbid_entry[i]:
                exit_reason = "forced_exit_on_forbidden_day"
            elif pd.notna(zi) and zi_f >= exit_z:
                exit_reason = "exit_z"
            elif hold_days >= max_hold_days:
                exit_reason = "max_hold_days"

            if exit_reason is not None:
                # realize trade
                exit_date = idx[i].strftime("%Y-%m-%d")
                exit_price = p
                # interest paid over hold_days (trading days)
                interest_paid = pos.borrow_principal * borrow_apr * (hold_days / float(trading_days))
                interest_paid_total += interest_paid

                exit_value = pos.lever_shares * exit_price
                lever_leg_pnl_gross = exit_value - pos.borrow_principal  # before interest (matches v3-style)

                trades.append(
                    {
                        "entry_date": pos.entry_date,
                        "entry_price": pos.entry_price,
                        "entry_z": pos.entry_z,
                        "borrow_principal": pos.borrow_principal,
                        "lever_shares": pos.lever_shares,
                        "interest_paid": interest_paid,
                        "exit_date": exit_date,
                        "exit_price": exit_price,
                        "hold_days": hold_days,
                        "exit_reason": exit_reason,
                        "lever_leg_pnl": lever_leg_pnl_gross,
                    }
                )
                pos = None

        # Entry (only if flat)
        if pos is None:
            # enter only when z crosses down into <= entry_z
            crossed = (pd.notna(zi) and zi_f <= entry_z and (pd.isna(prev_z) or float(prev_z) > entry_z))
            if crossed:
                if forbid_entry[i]:
                    skipped_entries += 1
                else:
                    # borrow based on current equity (base-only because flat)
                    equity_now = float(eq_lev.iloc[i])
                    borrow_principal = max(0.0, equity_now * leverage_frac)
                    lever_shares = borrow_principal / p if p > 0 else 0.0

                    pos = Position(
                        entry_i=i,
                        entry_date=idx[i].strftime("%Y-%m-%d"),
                        entry_price=p,
                        entry_z=zi_f,
                        borrow_principal=borrow_principal,
                        lever_shares=lever_shares,
                    )

        prev_z = zi_f

    df_bt = pd.DataFrame(
        {
            "price": price,
            "z": z,
            "eq_base": eq_base,
            "eq_leverage": eq_lev,
            "forbid_entry": pd.Series(forbid_entry, index=idx).astype(bool),
        },
        index=idx,
    )

    summary = {
        "interest_paid_total": interest_paid_total,
        "trades": len(trades),
        "skipped_entries_on_forbidden": skipped_entries,
    }
    return df_bt, summary, trades


def main() -> None:
    ap = argparse.ArgumentParser(description="MVP backtest: base + leveraged add-on triggered by BB-z")

    ap.add_argument("--price_csv", default="tw0050_bb_cache/data.csv", help="Path to price CSV (must include date column).")
    ap.add_argument("--price_col", default="adjclose", help="Price column name (e.g., adjclose).")

    ap.add_argument("--stats_json", default="tw0050_bb_cache/stats_latest.json", help="stats_latest.json for break info (optional).")

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_ddof", type=int, default=0)

    ap.add_argument("--entry_z", type=float, default=-1.5)
    ap.add_argument("--exit_z", type=float, default=0.0)

    # aliases for your earlier CLI attempts
    ap.add_argument("--enter_z", type=float, default=None, help="Alias for --entry_z")
    ap.add_argument("--leverage_frac", type=float, default=0.5)
    ap.add_argument("--leverage_add", type=float, default=None, help="Alias for --leverage_frac")

    ap.add_argument("--borrow_apr", type=float, default=0.035)
    ap.add_argument("--max_hold_days", type=int, default=60)
    ap.add_argument("--trading_days", type=int, default=252)

    # break thresholds fallback if stats_json is missing
    ap.add_argument("--break_ratio_hi", type=float, default=1.8)
    ap.add_argument("--break_ratio_lo", type=float, default=0.5555555556)

    # contamination policy
    ap.add_argument("--skip_contaminated", action="store_true", default=True)
    ap.add_argument("--no_skip_contaminated", action="store_true", default=False)
    ap.add_argument("--contam_horizon", type=int, default=None, help="Days before break to forbid entries (default=max_hold_days).")
    ap.add_argument("--z_clear_days", type=int, default=None, help="Days after break to forbid entries (default=bb_window).")

    ap.add_argument("--out_json", default="backtest_summary.json")
    ap.add_argument("--out_summary_json", default=None, help="Alias for --out_json")
    ap.add_argument("--out_equity_csv", default=None)
    ap.add_argument("--out_trades_csv", default=None)

    args = ap.parse_args()

    # apply aliases
    if args.enter_z is not None:
        args.entry_z = float(args.enter_z)
    if args.leverage_add is not None:
        args.leverage_frac = float(args.leverage_add)
    if args.out_summary_json is not None:
        args.out_json = args.out_summary_json

    skip_contaminated = bool(args.skip_contaminated) and (not bool(args.no_skip_contaminated))

    df = load_price_csv(args.price_csv, args.price_col)
    z = compute_bb_z(df["price"], window=int(args.bb_window), ddof=int(args.bb_ddof))

    # breaks from stats_json if available; else detect from price
    hi_s, lo_s, samples = load_break_info_from_stats(args.stats_json)
    ratio_hi = float(hi_s) if hi_s is not None else float(args.break_ratio_hi)
    ratio_lo = float(lo_s) if lo_s is not None else float(args.break_ratio_lo)

    breaks = align_break_indices(df, samples) if samples else []
    if not breaks:
        breaks = detect_breaks_from_price(df, ratio_hi=ratio_hi, ratio_lo=ratio_lo)

    contam_horizon = int(args.contam_horizon) if args.contam_horizon is not None else int(args.max_hold_days)
    z_clear_days = int(args.z_clear_days) if args.z_clear_days is not None else int(args.bb_window)

    forbid = [False] * len(df)
    if skip_contaminated and breaks:
        forbid = build_entry_forbidden_mask(
            n=len(df),
            breaks=align_break_indices(df, breaks) if isinstance(breaks, list) else [],
            contam_horizon=contam_horizon,
            z_clear_days=z_clear_days,
        )

    df_bt, bt_audit, trades = run_backtest(
        df=df,
        z=z,
        forbid_entry=forbid,
        entry_z=float(args.entry_z),
        exit_z=float(args.exit_z),
        leverage_frac=float(args.leverage_frac),
        borrow_apr=float(args.borrow_apr),
        max_hold_days=int(args.max_hold_days),
        trading_days=int(args.trading_days),
    )

    perf_leverage = _perf(df_bt["eq_leverage"], int(args.trading_days))
    perf_base = _perf(df_bt["eq_base"], int(args.trading_days))

    delta = {
        "cagr": (perf_leverage.get("cagr", float("nan")) - perf_base.get("cagr", float("nan")))
        if (perf_leverage.get("ok") and perf_base.get("ok"))
        else float("nan"),
        "mdd": (perf_leverage.get("mdd", float("nan")) - perf_base.get("mdd", float("nan")))
        if (perf_leverage.get("ok") and perf_base.get("ok"))
        else float("nan"),
        "sharpe0": (perf_leverage.get("sharpe0", float("nan")) - perf_base.get("sharpe0", float("nan")))
        if (perf_leverage.get("ok") and perf_base.get("ok"))
        else float("nan"),
    }

    out = {
        "generated_at_utc": utc_now_iso(),
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "params": {
            "bb_window": int(args.bb_window),
            "bb_ddof": int(args.bb_ddof),
            "entry_z": float(args.entry_z),
            "exit_z": float(args.exit_z),
            "leverage_frac": float(args.leverage_frac),
            "borrow_apr": float(args.borrow_apr),
            "max_hold_days": int(args.max_hold_days),
            "trading_days": int(args.trading_days),
            "skip_contaminated": bool(skip_contaminated),
            "contam_horizon": int(contam_horizon),
            "z_clear_days": int(z_clear_days),
            "break_ratio_hi": float(ratio_hi),
            "break_ratio_lo": float(ratio_lo),
        },
        "audit": {
            "rows": int(len(df_bt)),
            "start_date": df_bt.index[0].strftime("%Y-%m-%d") if len(df_bt) else "N/A",
            "end_date": df_bt.index[-1].strftime("%Y-%m-%d") if len(df_bt) else "N/A",
            "interest_paid_total": float(bt_audit.get("interest_paid_total", 0.0)),
            "trades": int(bt_audit.get("trades", 0)),
            "skipped_entries_on_forbidden": int(bt_audit.get("skipped_entries_on_forbidden", 0)),
            "breaks_detected": int(len(breaks)) if isinstance(breaks, list) else 0,
            "break_samples_first5": (breaks[:5] if isinstance(breaks, list) else []),
            "forbid_mask_semantics": "for each break idx b: forbid entry i in [b-contam_horizon, b+z_clear_days-1]",
        },
        "perf_leverage": perf_leverage,
        "perf_base_only": perf_base,
        "delta_vs_base": delta,
        "trades": trades,
    }

    # write outputs
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    if args.out_equity_csv:
        df_bt[["price", "z", "eq_base", "eq_leverage", "forbid_entry"]].to_csv(args.out_equity_csv, index_label="date")

    if args.out_trades_csv:
        pd.DataFrame(trades).to_csv(args.out_trades_csv, index=False)

    print(f"OK: wrote {args.out_json}")
    if args.out_equity_csv:
        print(f"OK: wrote {args.out_equity_csv}")
    if args.out_trades_csv:
        print(f"OK: wrote {args.out_trades_csv}")


if __name__ == "__main__":
    main()