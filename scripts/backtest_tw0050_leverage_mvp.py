#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backtest_tw0050_leverage_mvp.py

Audit-first MVP backtest for "base hold + conditional leverage leg" using BB z-score.

v27.1 (2026-02-22):
- FIX: Restore full main() execution flow and argparse setup.
- FIX: Accrue final overnight interest on T+1 exit day.
- FIX: Clear pending_entry/exit states defensively on margin call.
- FIX: Validate entry_z < exit_z to prevent silent logic failure.
- FIX: Remove risky fallback_numeric in column resolution.
- FEAT: Add calendar gap detection warning and TRADE_COLS schema validation.
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

SCHEMA_VERSION = "v27.1"
SCRIPT_FINGERPRINT = "backtest_tw0050_leverage_mvp@2026-02-22.v27.1.strict_execution"

TRADE_COLS = [
    "entry_date",
    "entry_price",
    "entry_z",
    "borrow_principal",
    "lever_shares",
    "entry_cost",
    "exit_date",
    "exit_price",
    "hold_days",
    "exit_reason",
    "exit_cost",
    "cost_paid",
    "interest_paid",
    "lever_leg_pnl",
    "net_lever_pnl_after_costs",
]

if len(TRADE_COLS) != len(set(TRADE_COLS)):
    raise SystemExit(f"ERROR: TRADE_COLS has duplicates.")

_DEFAULT_RATIO_HI = 1.8
_DEFAULT_RATIO_LO = round(1.0 / _DEFAULT_RATIO_HI, 10)

MAINT_RATIO_MODES = [
    "equity_over_lever_notional",
    "equity_over_borrow",
    "equity_over_total_notional",
]

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

def _write_json(path: str, obj: Dict[str, Any]) -> None:
    _ensure_parent(path)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

def _normalize_date_col(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns:
        for c in ["Date", "DATE", "timestamp", "time", "Time"]:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break
    if "date" not in df.columns:
        raise SystemExit("ERROR: price csv missing date column")

    df["date_ts"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_ts"]).copy()
    df = df.sort_values("date_ts").reset_index(drop=True)
    df["date"] = df["date_ts"].dt.date.astype(str)
    
    # Calculate real calendar days between rows
    df["calendar_days"] = df["date_ts"].diff().dt.days.fillna(1.0)
    df["calendar_days"] = df["calendar_days"].clip(lower=1.0)
    
    # Gap warning
    large_gaps = df[df["calendar_days"] > 10]
    if not large_gaps.empty:
        print(f"WARNING: {len(large_gaps)} gaps > 10 calendar days detected. Check data continuity.")
        
    return df

def _find_col(df: pd.DataFrame, user_col: Optional[str], cands: List[str]) -> str:
    if user_col:
        if user_col not in df.columns:
            raise SystemExit(f"ERROR: column '{user_col}' not found in csv")
        return user_col

    cols_lc = {c.lower(): c for c in df.columns}
    for k in cands:
        if k.lower() in cols_lc:
            return cols_lc[k.lower()]

    raise SystemExit(f"ERROR: required column not found. Candidates were: {cands}. Please specify via arguments.")

def _calc_bb_z(price: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=ddof)
    sd = sd.replace(0.0, np.nan)
    z = (price - ma) / sd
    return z.replace([np.inf, -np.inf], np.nan)

def _calc_sma(price: pd.Series, window: int) -> pd.Series:
    return price.rolling(window=window, min_periods=window).mean()

def _daily_interest(principal: float, apr: float, days: float, year_days: float = 365.0) -> float:
    if principal <= 0.0 or apr <= 0.0 or days <= 0:
        return 0.0
    return float(principal) * float(apr) * (float(days) / year_days)

def _to_finite_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def _safe_label(x: Any) -> str:
    try:
        if isinstance(x, pd.Timestamp):
            return x.date().isoformat()
    except Exception:
        pass
    return str(x)

def _prepare_df(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "open" in df.columns:
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
    else:
        df["open"] = df["price"]
    df = df.dropna(subset=["price"]).copy()
    df = df.sort_values("date_ts").reset_index(drop=True)
    return df

def _max_drawdown(eq: pd.Series) -> Dict[str, Any]:
    if eq is None or len(eq) == 0:
        return {"mdd": None, "peak": None, "trough": None}
    v = pd.to_numeric(eq, errors="coerce").to_numpy(dtype=float)
    v2 = np.where(np.isfinite(v), v, np.nan)
    if np.all(np.isnan(v2)):
        return {"mdd": None, "peak": None, "trough": None}
    running_max = np.maximum.accumulate(np.where(np.isnan(v2), -np.inf, v2))
    running_max = np.where(running_max == -np.inf, np.nan, running_max)
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
    peak_pos = int(np.nanargmax(peak_slice)) if not np.all(np.isnan(peak_slice)) else None
    idx = eq.index
    return {
        "mdd": mdd,
        "peak": _safe_label(idx[peak_pos]) if peak_pos is not None else None,
        "trough": _safe_label(idx[trough_pos]),
        "peak_pos": peak_pos,
        "trough_pos": trough_pos,
    }

def _perf_summary(eq: pd.Series, trading_days: int = 252, perf_ddof: int = 0) -> Dict[str, Any]:
    eq = pd.to_numeric(eq, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if eq.empty or len(eq) < 3:
        return {"ok": False}
    start, end = float(eq.iloc[0]), float(eq.iloc[-1])
    n = int(len(eq))
    years = max((n - 1) / float(trading_days), 1e-12)
    cagr = (end / start) ** (1.0 / years) - 1.0 if start > 0 and end > 0 else None
    rets = eq.pct_change().dropna()
    dd = int(perf_ddof)
    vol = float(rets.std(ddof=dd) * math.sqrt(trading_days)) if len(rets) > 2 else None
    sharpe = ((float(rets.mean()) / float(rets.std(ddof=dd))) * math.sqrt(trading_days) 
              if (len(rets) > 2 and float(rets.std(ddof=dd)) > 0) else None)
    mdd_info = _max_drawdown(eq)
    return {
        "ok": True, "start": start, "end": end, "n_days": n, "years": years,
        "cagr": cagr, "vol_ann": vol, "sharpe0": sharpe,
        "mdd": mdd_info.get("mdd")
    }

def _calmar(perf: Dict[str, Any]) -> Optional[float]:
    if not isinstance(perf, dict) or not perf.get("ok"):
        return None
    c, m = perf.get("cagr"), perf.get("mdd")
    if c is None or m is None:
        return None
    try:
        c, m = float(c), float(m)
        if m == 0.0:
            return None
        return c / abs(m) if np.isfinite(c) and np.isfinite(m) else None
    except Exception:
        pass
    return None

def _slip_rate(slip_bps: float) -> float:
    try:
        v = float(slip_bps)
        return v * 1e-4 if np.isfinite(v) and v > 0.0 else 0.0
    except Exception:
        return 0.0

def _entry_cost(notional: float, fee_rate: float, slip_rate: float) -> float:
    return float(notional) * (max(float(fee_rate), 0.0) + max(float(slip_rate), 0.0)) if notional > 0 else 0.0

def _exit_cost(notional: float, fee_rate: float, tax_rate: float, slip_rate: float) -> float:
    return float(notional) * (max(float(fee_rate), 0.0) + max(float(tax_rate), 0.0) + max(float(slip_rate), 0.0)) if notional > 0 else 0.0

def detect_breaks_from_price(df: pd.DataFrame, ratio_hi: float, ratio_lo: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if df is None or len(df) < 2: return out
    px = pd.to_numeric(df["price"], errors="coerce").to_numpy(dtype=float)
    dates = df["date"].astype(str).to_numpy()
    p0, p1 = px[:-1], px[1:]
    valid = np.isfinite(p0) & np.isfinite(p1) & (p0 > 0.0)
    ratio = np.full_like(p1, np.nan, dtype=float)
    ratio[valid] = p1[valid] / p0[valid]
    mask = (ratio >= float(ratio_hi)) | (ratio <= float(ratio_lo))
    idxs = (np.where(mask & np.isfinite(ratio))[0] + 1).astype(int)
    for i in idxs.tolist():
        out.append({
            "idx": int(i), "break_date": str(dates[i]),
            "prev_price": float(px[i - 1]) if np.isfinite(px[i - 1]) else None,
            "price": float(px[i]) if np.isfinite(px[i]) else None,
        })
    return out

def align_break_indices(df: pd.DataFrame, raw_breaks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    date_to_idx = {str(d): int(i) for i, d in enumerate(df["date"].astype(str).tolist())}
    out: List[Dict[str, Any]] = []
    for b in raw_breaks:
        if not isinstance(b, dict): continue
        idx = int(b.get("idx")) if "idx" in b else date_to_idx.get(str(b.get("break_date", b.get("date"))))
        if idx is not None and 0 < idx < len(df):
            b_copy = b.copy()
            b_copy["idx"] = idx
            out.append(b_copy)
    return sorted(out, key=lambda x: x["idx"])

def build_entry_forbidden_mask(n: int, breaks: List[Dict[str, Any]], contam_horizon: int, z_clear_days: int) -> List[bool]:
    forbid = [False] * int(n)
    for b in breaks:
        bi = int(b["idx"])
        for i in range(max(bi - contam_horizon, 0), min(bi + z_clear_days, n)):
            forbid[i] = True
    return forbid

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
    fee_rate: float
    tax_rate: float
    slip_bps: float
    cost_on: str
    entry_mode: str
    trend_rule: str
    trend_ma_fast: int
    trend_ma_slow: int
    perf_ddof: int
    maintenance_margin: float
    maint_ratio_mode: str

def run_backtest(
    df: pd.DataFrame,
    params: Params,
    forbid_entry_mask: Optional[List[bool]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    
    # Validation
    if params.entry_mode == "bb":
        assert params.entry_z < params.exit_z, f"entry_z ({params.entry_z}) must be < exit_z ({params.exit_z}) to prevent silent logic failure."

    df = _prepare_df(df)
    n = int(len(df))
    if n < params.bb_window + 5:
        raise ValueError("not enough rows for bb window")

    df["bb_z"] = _calc_bb_z(df["price"], window=params.bb_window, ddof=params.bb_ddof)
    df["ma_fast"] = _calc_sma(df["price"], window=max(int(params.trend_ma_fast), 1))
    df["ma_slow"] = _calc_sma(df["price"], window=max(int(params.trend_ma_slow), 1))

    p0 = float(df["price"].iloc[0])
    base_shares = 1.0 / p0
    lever_shares_target = max(float(base_shares) * float(params.leverage_frac), 0.0)

    prices_close = df["price"].to_numpy(dtype=float)
    prices_open = df["open"].to_numpy(dtype=float)
    zs = df["bb_z"].to_numpy(dtype=float)
    dates = df["date"].astype(str).to_numpy()
    ma_fast = df["ma_fast"].to_numpy(dtype=float)
    ma_slow = df["ma_slow"].to_numpy(dtype=float)
    cal_days = df["calendar_days"].to_numpy(dtype=float)

    lever_shares, borrow_principal, cash = 0.0, 0.0, 0.0
    in_lever = False
    hold_days = 0
    interest_paid_total = 0.0
    entry_cost_total, exit_cost_total, cost_paid_total = 0.0, 0.0, 0.0
    slip_rate = _slip_rate(params.slip_bps)

    trades: List[Dict[str, Any]] = []
    cur_trade: Optional[Dict[str, Any]] = None

    eq_arr = np.empty(n, dtype=float)
    base_arr = np.empty(n, dtype=float)
    lev_on_arr = np.empty(n, dtype=bool)

    margin_call_count = 0
    min_maint_ratio = None
    forbid = forbid_entry_mask if (forbid_entry_mask is not None and len(forbid_entry_mask) == n) else [False] * n

    # T+1 Execution State
    pending_entry = False
    pending_exit = False
    pending_exit_reason = ""
    pending_entry_z = np.nan

    def _trend_on(i: int) -> bool:
        if params.trend_rule == "price_gt_ma60":
            return np.isfinite(ma_slow[i]) and prices_close[i] > ma_slow[i]
        return np.isfinite(ma_fast[i]) and np.isfinite(ma_slow[i]) and ma_fast[i] > ma_slow[i]

    def _entry_signal(i: int) -> bool:
        if params.entry_mode == "always": return True
        if params.entry_mode == "trend": return _trend_on(i)
        zf = _to_finite_float(zs[i])
        return (zf is not None) and (zf <= float(params.entry_z))

    def _exit_signal(i: int) -> Tuple[bool, str]:
        if params.max_hold_days > 0 and hold_days >= params.max_hold_days:
            return True, "max_hold_days"
        if params.entry_mode == "always": return False, "none"
        if params.entry_mode == "trend":
            return (not _trend_on(i), "trend_off" if not _trend_on(i) else "none")
        zf = _to_finite_float(zs[i])
        by_z = (zf is not None and zf >= float(params.exit_z))
        return by_z, ("exit_z" if by_z else "none")

    for i in range(n):
        date = str(dates[i])
        price_close = float(prices_close[i])
        price_open = float(prices_open[i])
        days_passed = float(cal_days[i])
        exited_today = False

        base_now = base_shares * price_close

        # 1. Execute Pending Exit (T+1 Open)
        if pending_exit and in_lever:
            # First accrue final day's interest before exiting
            interest = _daily_interest(borrow_principal, params.borrow_apr, days_passed)
            cash -= interest
            interest_paid_total += interest
            if cur_trade is not None:
                cur_trade["interest_paid"] += interest

            proceeds = lever_shares * price_open
            notional_exit = ((base_shares + lever_shares) if params.cost_on == "all" else lever_shares) * price_open
            exit_cost = _exit_cost(notional_exit, params.fee_rate, params.tax_rate, slip_rate)
            
            cash = cash - exit_cost + proceeds - borrow_principal
            exit_cost_total += exit_cost
            cost_paid_total += exit_cost

            if cur_trade is not None:
                cur_trade.update({
                    "exit_date": date, "exit_price": price_open, "hold_days": hold_days,
                    "exit_reason": pending_exit_reason, "exit_cost": exit_cost,
                    "cost_paid": cur_trade.get("entry_cost", 0.0) + exit_cost,
                    "lever_leg_pnl": proceeds - cur_trade.get("borrow_principal", 0.0),
                })
                cur_trade["net_lever_pnl_after_costs"] = cur_trade["lever_leg_pnl"] - cur_trade.get("interest_paid", 0.0) - cur_trade["cost_paid"]
                trades.append(cur_trade)

            in_lever, pending_exit, lever_shares, borrow_principal, hold_days, cur_trade = False, False, 0.0, 0.0, 0, None
            exited_today = True

        # 2. Execute Pending Entry (T+1 Open)
        if pending_entry and not in_lever and not exited_today and not forbid[i]:
            if lever_shares_target > 0.0:
                borrow = float(lever_shares_target * price_open)
                notional_entry = ((base_shares + lever_shares_target) if params.cost_on == "all" else lever_shares_target) * price_open
                entry_cost = _entry_cost(notional_entry, params.fee_rate, slip_rate)

                cash -= entry_cost
                entry_cost_total += entry_cost
                cost_paid_total += entry_cost

                borrow_principal = borrow
                lever_shares = lever_shares_target
                in_lever = True
                hold_days = 0

                cur_trade = {
                    "entry_date": date, "entry_price": price_open, "entry_z": pending_entry_z,
                    "borrow_principal": borrow_principal, "lever_shares": lever_shares,
                    "entry_cost": entry_cost, "exit_cost": 0.0, "cost_paid": entry_cost, "interest_paid": 0.0,
                }
            pending_entry = False

        # 3. Accrue Interest for normal holding days (Calendar Days)
        # Note: If exited in Step 1, in_lever is False, this block is safely skipped.
        if in_lever and borrow_principal > 0.0:
            interest = _daily_interest(borrow_principal, params.borrow_apr, days_passed)
            cash -= interest
            interest_paid_total += interest
            if cur_trade is not None:
                cur_trade["interest_paid"] += interest

        # 4. Intraday Margin Call Check (Using Close Price as proxy for Low)
        if in_lever and float(params.maintenance_margin) > 0.0:
            total_notional = float((base_shares + lever_shares) * price_close)
            
            # NOTE: `cash` inherently holds the ongoing negative balances (from fees & interest).
            # The borrow_principal isn't added to cash at entry (since it's spent immediately on shares),
            # therefore it must be subtracted explicitly here to represent total debt.
            equity_flat = total_notional + cash - borrow_principal
            lever_notional = float(lever_shares * price_close)
            
            denom = borrow_principal if params.maint_ratio_mode == "equity_over_borrow" else (
                    total_notional if params.maint_ratio_mode == "equity_over_total_notional" else lever_notional)
            
            mr = float(equity_flat) / float(denom) if denom > 0 else None
            if mr is not None:
                min_maint_ratio = min(min_maint_ratio, mr) if min_maint_ratio is not None else mr
                if mr < float(params.maintenance_margin):
                    # Force MOC Exit on margin call trigger
                    proceeds = lever_shares * price_close
                    notional_exit = ((base_shares + lever_shares) if params.cost_on == "all" else lever_shares) * price_close
                    exit_cost = _exit_cost(notional_exit, params.fee_rate, params.tax_rate, slip_rate)
                    
                    cash = cash - exit_cost + proceeds - borrow_principal
                    if cur_trade is not None:
                        cur_trade.update({
                            "exit_date": date, "exit_price": price_close, "hold_days": hold_days + 1,
                            "exit_reason": "margin_call", "exit_cost": exit_cost,
                            "cost_paid": cur_trade.get("entry_cost", 0.0) + exit_cost,
                            "lever_leg_pnl": proceeds - cur_trade.get("borrow_principal", 0.0),
                        })
                        cur_trade["net_lever_pnl_after_costs"] = cur_trade["lever_leg_pnl"] - cur_trade.get("interest_paid", 0.0) - cur_trade["cost_paid"]
                        trades.append(cur_trade)

                    in_lever, lever_shares, borrow_principal, hold_days, cur_trade = False, 0.0, 0.0, 0, None
                    exited_today, margin_call_count = True, margin_call_count + 1
                    
                    # Defensively clear states
                    pending_entry = False
                    pending_exit = False

        # 5. Evaluate End of Day Signals for Tomorrow
        if in_lever and not exited_today:
            hold_days += 1
            exit_now, reason = _exit_signal(i)
            if exit_now:
                pending_exit = True
                pending_exit_reason = reason
        elif not in_lever and not exited_today:
            if not forbid[i] and _entry_signal(i):
                pending_entry = True
                pending_entry_z = _to_finite_float(zs[i])

        # Record EOD Equity
        eq_arr[i] = (base_shares + lever_shares) * price_close + cash - borrow_principal
        base_arr[i] = base_now
        lev_on_arr[i] = bool(in_lever)

    # Force close at end of data if still open
    if in_lever and cur_trade is not None and n > 0:
        last_price = float(prices_close[-1])
        proceeds = lever_shares * last_price
        notional_exit = ((base_shares + lever_shares) if params.cost_on == "all" else lever_shares) * last_price
        exit_cost = _exit_cost(notional_exit, params.fee_rate, params.tax_rate, slip_rate)
        cash = cash - exit_cost + proceeds - borrow_principal
        
        cur_trade.update({
            "exit_date": str(dates[-1]), "exit_price": last_price, "hold_days": hold_days,
            "exit_reason": "end_of_data", "exit_cost": exit_cost,
            "cost_paid": cur_trade.get("entry_cost", 0.0) + exit_cost,
            "lever_leg_pnl": proceeds - cur_trade.get("borrow_principal", 0.0),
        })
        cur_trade["net_lever_pnl_after_costs"] = cur_trade["lever_leg_pnl"] - cur_trade.get("interest_paid", 0.0) - cur_trade["cost_paid"]
        trades.append(cur_trade)
        eq_arr[-1] = base_shares * last_price + cash
        lev_on_arr[-1] = False

    # Schema Validation for Output Trades
    if trades:
        missing = set(TRADE_COLS) - set(trades[0].keys())
        assert not missing, f"Trade record missing required schema columns: {missing}"

    df_out = df[["date", "date_ts", "price", "open", "bb_z", "ma_fast", "ma_slow"]].copy()
    df_out["equity"] = eq_arr
    df_out["equity_base_only"] = base_arr
    df_out["lever_on"] = lev_on_arr

    perf_leverage = _perf_summary(df_out.set_index("date")["equity"], trading_days=params.trading_days, perf_ddof=params.perf_ddof)
    perf_base = _perf_summary(df_out.set_index("date")["equity_base_only"], trading_days=params.trading_days, perf_ddof=params.perf_ddof)

    summary: Dict[str, Any] = {
        "generated_at_utc": utc_now_iso(),
        "schema_version": SCHEMA_VERSION,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "audit": {
            "interest_semantics": "Calendar days based accrual. Formula: Principal * APR * (Days_Passed / 365.0). Includes T+1 exit day accrual.",
            "timing_assumption": "T+1 Open Execution: Signal at Close(T), Execute at Open(T+1) to eliminate lookahead bias.",
            "trades": int(len(trades)),
            "margin_call_count": int(margin_call_count),
        },
        "perf_leverage": perf_leverage,
        "perf_base_only": perf_base,
        "calmar_leverage": _calmar(perf_leverage),
        "trades": trades,
    }
    return df_out, summary

def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", default="data.csv")
    ap.add_argument("--price_col", default=None)
    ap.add_argument("--open_col", default=None, help="Column name for Open price used in execution")

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_ddof", type=int, default=0)
    ap.add_argument("--entry_z", "--enter_z", dest="entry_z", type=float, default=-1.5)
    ap.add_argument("--exit_z", type=float, default=0.0)

    ap.add_argument("--leverage_frac", dest="leverage_frac", type=float, default=0.5)
    ap.add_argument("--borrow_apr", type=float, default=0.035)

    ap.add_argument("--max_hold_days", type=int, default=0)
    ap.add_argument("--trading_days", type=int, default=252)

    ap.add_argument("--fee_rate", type=float, default=0.001425)
    ap.add_argument("--tax_rate", type=float, default=0.0010)
    ap.add_argument("--slip_bps", type=float, default=5.0)
    ap.add_argument("--cost_on", type=str, default="lever", choices=["lever", "all"])

    ap.add_argument("--entry_mode", type=str, default="bb", choices=["bb", "always", "trend"])
    ap.add_argument("--trend_rule", type=str, default="price_gt_ma60", choices=["price_gt_ma60", "ma20_gt_ma60"])
    ap.add_argument("--trend_ma_fast", type=int, default=20)
    ap.add_argument("--trend_ma_slow", type=int, default=60)
    ap.add_argument("--perf_ddof", type=int, default=0, choices=[0, 1])

    if hasattr(argparse, "BooleanOptionalAction"):
        ap.add_argument("--skip_contaminated", action=argparse.BooleanOptionalAction, default=True)
    else:
        ap.add_argument("--skip_contaminated", action="store_true", default=True)
        ap.add_argument("--no_skip_contaminated", dest="skip_contaminated", action="store_false")

    ap.add_argument("--contam_horizon", type=int, default=60)
    ap.add_argument("--z_clear_days", type=int, default=60)
    ap.add_argument("--break_ratio_hi", type=float, default=None)
    ap.add_argument("--break_ratio_lo", type=float, default=None)

    ap.add_argument("--maintenance_margin", type=float, default=0.0)
    ap.add_argument(
        "--maint_ratio_mode", type=str, default="equity_over_lever_notional", choices=MAINT_RATIO_MODES
    )

    ap.add_argument("--out_json", dest="out_json", default="backtest_mvp.json")
    ap.add_argument("--out_equity_csv", default="backtest_mvp_equity.csv")
    ap.add_argument("--out_trades_csv", default="backtest_mvp_trades.csv")

    args = ap.parse_args()

    # Load and Normalize Data
    price_path = os.path.join(args.cache_dir, str(args.price_csv))
    df_raw = pd.read_csv(price_path)
    df_raw = _normalize_date_col(df_raw)

    pc = _find_col(df_raw, args.price_col, ["adjclose", "adj_close", "close"])
    df_raw["price"] = pd.to_numeric(df_raw[pc], errors="coerce")
    
    if args.open_col:
        oc = _find_col(df_raw, args.open_col, [args.open_col])
        df_raw["open"] = pd.to_numeric(df_raw[oc], errors="coerce")
    else:
        try:
            oc = _find_col(df_raw, None, ["open"])
            df_raw["open"] = pd.to_numeric(df_raw[oc], errors="coerce")
        except SystemExit:
            print("WARNING: 'open' column not found. Using 'price' (Close) for execution. This causes Lookahead Bias.")
            df_raw["open"] = df_raw["price"]

    df_raw = df_raw.dropna(subset=["price"]).copy()

    # Contamination Setup
    ratio_hi = float(args.break_ratio_hi) if args.break_ratio_hi is not None else _DEFAULT_RATIO_HI
    ratio_lo = float(args.break_ratio_lo) if args.break_ratio_lo is not None else _DEFAULT_RATIO_LO

    raw_breaks = detect_breaks_from_price(df_raw, ratio_hi, ratio_lo)
    breaks_aligned = align_break_indices(df_raw, raw_breaks)

    forbid_mask = None
    if bool(args.skip_contaminated) and len(breaks_aligned) > 0:
        forbid_mask = build_entry_forbidden_mask(
            n=len(df_raw),
            breaks=breaks_aligned,
            contam_horizon=int(args.contam_horizon),
            z_clear_days=int(args.z_clear_days),
        )

    # Param Construction
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
        fee_rate=float(args.fee_rate),
        tax_rate=float(args.tax_rate),
        slip_bps=float(args.slip_bps),
        cost_on=str(args.cost_on),
        entry_mode=str(args.entry_mode),
        trend_rule=str(args.trend_rule),
        trend_ma_fast=int(args.trend_ma_fast),
        trend_ma_slow=int(args.trend_ma_slow),
        perf_ddof=int(args.perf_ddof),
        maintenance_margin=float(args.maintenance_margin),
        maint_ratio_mode=str(args.maint_ratio_mode),
    )

    try:
        df_bt, summary = run_backtest(df_raw, params, forbid_entry_mask=forbid_mask)
    except Exception as e:
        raise SystemExit(f"ERROR during backtest execution: {type(e).__name__}: {e}")

    # Output generation
    out_json_path = os.path.join(args.cache_dir, str(args.out_json))
    out_eq_path = os.path.join(args.cache_dir, str(args.out_equity_csv))
    out_tr_path = os.path.join(args.cache_dir, str(args.out_trades_csv))

    _write_json(out_json_path, summary)
    
    _ensure_parent(out_eq_path)
    df_bt[["date", "price", "open", "bb_z", "ma_fast", "ma_slow", "equity", "equity_base_only", "lever_on"]].to_csv(
        out_eq_path, index=False, encoding="utf-8"
    )

    _ensure_parent(out_tr_path)
    trades_export = summary.get("trades", [])
    if len(trades_export) > 0:
        df_tr = pd.DataFrame(trades_export)
        for c in TRADE_COLS:
            if c not in df_tr.columns:
                df_tr[c] = np.nan
        df_tr[TRADE_COLS].to_csv(out_tr_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=TRADE_COLS).to_csv(out_tr_path, index=False, encoding="utf-8")

    print(f"OK: backtest completed successfully.")
    print(f"OK: wrote {out_json_path}")
    print(f"OK: wrote {out_eq_path}")
    print(f"OK: wrote {out_tr_path}")

if __name__ == "__main__":
    main()
