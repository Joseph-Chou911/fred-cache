#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

SCRIPT_FINGERPRINT = "backtest_tw0050_leverage_mvp@2026-02-22.v3"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


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

    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise SystemExit("ERROR: no numeric price column found in csv")


def _calc_bb_z(price: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=ddof)
    sd = sd.replace(0.0, np.nan)
    z = (price - ma) / sd
    z = z.replace([np.inf, -np.inf], np.nan)
    return z


def _safe_label(x: Any) -> str:
    try:
        if isinstance(x, pd.Timestamp):
            return x.date().isoformat()
    except Exception:
        pass
    return str(x)


def _max_drawdown(eq: pd.Series) -> Dict[str, Any]:
    if eq is None or len(eq) == 0:
        return {"mdd": None, "peak": None, "trough": None}

    v = pd.to_numeric(eq, errors="coerce").to_numpy(dtype=float)
    if np.all(~np.isfinite(v)):
        return {"mdd": None, "peak": None, "trough": None}

    s = pd.Series(v).replace([np.inf, -np.inf], np.nan).ffill()
    v2 = s.to_numpy(dtype=float)

    running_max = np.maximum.accumulate(v2)
    running_max = np.where(running_max == 0.0, np.nan, running_max)
    dd = (v2 / running_max) - 1.0

    if np.all(~np.isfinite(dd)):
        return {"mdd": None, "peak": None, "trough": None}

    trough_pos = int(np.nanargmin(dd))
    mdd = float(dd[trough_pos])

    peak_slice = v2[: trough_pos + 1]
    peak_pos = int(np.nanargmax(peak_slice))

    idx = eq.index
    peak_label = _safe_label(idx[peak_pos]) if len(idx) > peak_pos else None
    trough_label = _safe_label(idx[trough_pos]) if len(idx) > trough_pos else None

    return {
        "mdd": mdd,
        "peak": peak_label,
        "trough": trough_label,
        "peak_pos": peak_pos,
        "trough_pos": trough_pos,
    }


def _perf_summary(eq: pd.Series, trading_days: int = 252) -> Dict[str, Any]:
    eq = pd.to_numeric(eq, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if eq.empty or len(eq) < 3:
        return {"ok": False}

    start = float(eq.iloc[0])
    end = float(eq.iloc[-1])
    n = int(len(eq))
    years = max((n - 1) / float(trading_days), 1e-12)

    cagr = (end / start) ** (1.0 / years) - 1.0 if start > 0 else None
    rets = eq.pct_change().dropna()

    vol = float(rets.std(ddof=0) * math.sqrt(trading_days)) if len(rets) > 2 else None
    sharpe = (
        (float(rets.mean()) * trading_days) / (float(rets.std(ddof=0)) * math.sqrt(trading_days))
        if (len(rets) > 2 and float(rets.std(ddof=0)) > 0)
        else None
    )

    mdd_info = _max_drawdown(eq)

    return {
        "ok": True,
        "start": start,
        "end": end,
        "n_days": n,
        "years": years,
        "cagr": cagr,
        "vol_ann": vol,
        "sharpe0": sharpe,
        "mdd": mdd_info.get("mdd"),
        "mdd_peak": mdd_info.get("peak"),
        "mdd_trough": mdd_info.get("trough"),
    }


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


def run_backtest(df: pd.DataFrame, params: Params) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = df.copy()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"]).copy()
    df = df.sort_values("date_ts").reset_index(drop=True)
    if len(df) < params.bb_window + 5:
        raise SystemExit("ERROR: not enough rows for bb window")

    df["bb_z"] = _calc_bb_z(df["price"], window=params.bb_window, ddof=params.bb_ddof)

    p0 = float(df["price"].iloc[0])
    base_shares = 1.0 / p0

    lever_shares = 0.0
    borrow_principal = 0.0
    cash = 0.0
    in_lever = False
    hold_days = 0
    interest_paid_total = 0.0

    trades: List[Dict[str, Any]] = []
    cur_trade: Optional[Dict[str, Any]] = None

    eq_list: List[float] = []
    lev_flag: List[int] = []
    borrow_list: List[float] = []
    cash_list: List[float] = []

    for i in range(len(df)):
        price = float(df.loc[i, "price"])
        z = df.loc[i, "bb_z"]
        date = str(df.loc[i, "date"])

        if in_lever and borrow_principal > 0.0:
            daily_rate = float(params.borrow_apr) / float(params.trading_days)
            interest = borrow_principal * daily_rate
            cash -= interest
            interest_paid_total += interest
            if cur_trade is not None:
                cur_trade["interest_paid"] = float(cur_trade.get("interest_paid", 0.0) + interest)

        total_shares = base_shares + lever_shares
        equity = total_shares * price + cash - borrow_principal

        eq_list.append(float(equity))
        lev_flag.append(1 if in_lever else 0)
        borrow_list.append(float(borrow_principal))
        cash_list.append(float(cash))

        if z is None or (isinstance(z, float) and not np.isfinite(z)):
            continue
        zf = float(z)

        if in_lever:
            hold_days += 1
            exit_by_z = (zf >= float(params.exit_z))
            exit_by_time = (params.max_hold_days > 0 and hold_days >= params.max_hold_days)

            if exit_by_z or exit_by_time:
                proceeds = lever_shares * price
                cash += proceeds
                cash -= borrow_principal

                borrow_principal = 0.0
                lever_shares = 0.0
                in_lever = False

                if cur_trade is not None:
                    cur_trade["exit_date"] = date
                    cur_trade["exit_price"] = price
                    cur_trade["hold_days"] = int(hold_days)
                    cur_trade["exit_reason"] = "exit_z" if exit_by_z else "max_hold_days"
                    cur_trade["lever_leg_pnl"] = float((proceeds - cur_trade.get("borrow_principal", 0.0)))
                    trades.append(cur_trade)

                cur_trade = None
                hold_days = 0
                continue

        if (not in_lever) and (zf <= float(params.entry_z)):
            borrow = max(float(params.leverage_frac) * float(equity), 0.0)
            if borrow > 0.0:
                borrow_principal = borrow
                cash += borrow
                lever_shares = cash / price
                cash = 0.0
                in_lever = True
                hold_days = 0

                cur_trade = {
                    "entry_date": date,
                    "entry_price": price,
                    "entry_z": zf,
                    "borrow_principal": float(borrow_principal),
                    "lever_shares": float(lever_shares),
                    "interest_paid": 0.0,
                }

    df_bt = df[["date", "date_ts", "price", "bb_z"]].copy()
    df_bt["equity"] = eq_list
    df_bt["lever_on"] = lev_flag
    df_bt["borrow_principal"] = borrow_list
    df_bt["cash"] = cash_list
    df_bt["equity_base_only"] = (base_shares * df_bt["price"]).astype(float)

    summary = {
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
        },
        "audit": {
            "rows": int(len(df_bt)),
            "start_date": str(df_bt["date"].iloc[0]),
            "end_date": str(df_bt["date"].iloc[-1]),
            "interest_paid_total": float(interest_paid_total),
            "trades": int(len(trades)),
        },
        "perf_leverage": _perf_summary(df_bt.set_index("date")["equity"], trading_days=params.trading_days),
        "perf_base_only": _perf_summary(df_bt.set_index("date")["equity_base_only"], trading_days=params.trading_days),
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

    return df_bt, summary


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", default="data.csv")
    ap.add_argument("--price_col", default=None)

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_ddof", type=int, default=0)

    # accept both new and old flags
    ap.add_argument("--entry_z", "--enter_z", dest="entry_z", type=float, default=-1.5)
    ap.add_argument("--exit_z", type=float, default=0.0)

    ap.add_argument("--leverage_frac", "--leverage_add", dest="leverage_frac", type=float, default=0.2)
    ap.add_argument("--borrow_apr", type=float, default=0.035)
    ap.add_argument("--max_hold_days", type=int, default=60)
    ap.add_argument("--trading_days", type=int, default=252)

    # accept both new and old output flag
    ap.add_argument("--out_json", "--out_summary_json", dest="out_json", default="backtest_mvp.json")
    ap.add_argument("--out_equity_csv", default="backtest_mvp_equity.csv")
    ap.add_argument("--out_trades_csv", default="backtest_mvp_trades.csv")

    args = ap.parse_args()

    cache_dir = args.cache_dir
    price_path = os.path.join(cache_dir, args.price_csv)
    if not os.path.isfile(price_path):
        raise SystemExit(f"ERROR: missing price csv: {price_path}")

    df_raw = _read_csv(price_path)
    df_raw = _normalize_date_col(df_raw)

    pc = _find_price_col(df_raw, args.price_col)
    df_raw["price"] = pd.to_numeric(df_raw[pc], errors="coerce")
    df_raw = df_raw.dropna(subset=["price"]).copy()

    params = Params(
        bb_window=int(args.bb_window),
        bb_ddof=int(args.bb_ddof),
        entry_z=float(args.entry_z),
        exit_z=float(args.exit_z),
        leverage_frac=float(args.leverage_frac),
        borrow_apr=float(args.borrow_apr),
        max_hold_days=int(args.max_hold_days),
        trading_days=int(args.trading_days),
    )

    df_bt, summary = run_backtest(df_raw, params)

    out_json_path = os.path.join(cache_dir, args.out_json)
    out_eq_path = os.path.join(cache_dir, args.out_equity_csv)
    out_tr_path = os.path.join(cache_dir, args.out_trades_csv)

    _write_json(out_json_path, summary)
    df_bt.to_csv(out_eq_path, index=False, encoding="utf-8")

    trades = summary.get("trades", [])
    if isinstance(trades, list) and len(trades) > 0:
        pd.DataFrame(trades).to_csv(out_tr_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame([]).to_csv(out_tr_path, index=False, encoding="utf-8")

    print(f"OK: wrote {out_json_path}")
    print(f"OK: wrote {out_eq_path}")
    print(f"OK: wrote {out_tr_path}")


if __name__ == "__main__":
    main()