#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


# ===== Audit stamp =====
SCRIPT_FINGERPRINT = "backtest_tw0050_leverage_mvp@2026-02-22.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _infer_price_col(df: pd.DataFrame) -> str:
    cands = ["adjclose", "adj_close", "adj close", "adjClose", "Adj Close", "close", "Close"]
    cols_lc = {c.lower(): c for c in df.columns}
    for k in cands:
        if k.lower() in cols_lc:
            return cols_lc[k.lower()]
    # fallback: first numeric
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise SystemExit("ERROR: no numeric price column found in price csv")


def _normalize_date_col(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns:
        for c in ["Date", "DATE", "timestamp", "time", "Time"]:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break
    if "date" not in df.columns:
        raise SystemExit("ERROR: price csv missing date column (expected 'date' or common variants)")
    df["date_ts"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_ts"]).sort_values("date_ts").copy()
    df["date"] = df["date_ts"].dt.date.astype(str)
    return df


def _calc_bb_z(price: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=ddof)
    z = (price - ma) / sd.replace(0.0, np.nan)
    z = z.replace([np.inf, -np.inf], np.nan)
    return z


def _daily_return(price: pd.Series) -> pd.Series:
    # simple returns
    return price.pct_change()


def _max_drawdown(equity: pd.Series) -> Tuple[float, Optional[str], Optional[str]]:
    """
    Returns:
      mdd (<=0), peak_date, trough_date
    """
    if equity.empty:
        return 0.0, None, None
    peak = equity.cummax()
    dd = equity / peak - 1.0
    mdd = float(dd.min())
    if not np.isfinite(mdd):
        return 0.0, None, None
    trough_idx = int(dd.idxmin())
    trough_date = None
    peak_date = None
    try:
        trough_date = str(equity.index[trough_idx])
        # find peak before trough
        peak_val = float(peak.iloc[trough_idx])
        # last index where equity hit peak_val up to trough
        peak_candidates = np.where(np.isclose(peak.iloc[: trough_idx + 1].values, peak_val))[0]
        if peak_candidates.size > 0:
            peak_date = str(equity.index[int(peak_candidates[-1])])
    except Exception:
        pass
    return mdd, peak_date, trough_date


@dataclass
class StrategyParams:
    bb_window: int = 60
    bb_ddof: int = 0
    enter_z: float = -1.5          # add leverage when z <= enter_z
    exit_z: float = 0.0            # remove leverage when z >= exit_z
    max_hold_days: int = 60        # force exit after N trading days (optional guard)
    cooldown_days: int = 0         # after exit, wait N days before re-enter (0=off)
    leverage_add: float = 0.5      # additional exposure on top of base 1.0 (e.g. 0.5 => total 1.5x)
    borrow_apr: float = 0.035      # annual financing cost for leveraged part only (e.g. 0.035 for 3.5%)
    trading_days: int = 252


def run_backtest(df: pd.DataFrame, p: StrategyParams) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Base: always 1.0 exposure.
    Leverage: adds p.leverage_add exposure when in_position=True.
    Cost: charged daily on borrowed notional = p.leverage_add, only when in_position=True.
    Equity evolves by: eq[t] = eq[t-1] * (1 + exposure[t]*r[t] - cost[t])
    """
    df = df.copy()
    df = df.sort_values("date_ts").reset_index(drop=True)

    # compute z and daily returns
    df["bb_z"] = _calc_bb_z(df["price"], window=p.bb_window, ddof=p.bb_ddof)
    df["ret"] = _daily_return(df["price"])

    # only trade when z and ret are finite
    tradable = df["bb_z"].notna() & np.isfinite(df["bb_z"].astype(float)) & df["ret"].notna() & np.isfinite(df["ret"].astype(float))
    df["tradable"] = tradable

    # state machine
    in_pos = False
    hold_days = 0
    cooldown = 0

    exposure = np.zeros(len(df), dtype=float)
    lev_flag = np.zeros(len(df), dtype=int)
    signal = np.array(["HOLD"] * len(df), dtype=object)

    for i in range(len(df)):
        if not bool(df.loc[i, "tradable"]):
            # cannot act; keep prior state but exposure still applies only if we choose to apply it
            # conservative: if data not tradable, we set leverage OFF for that day (avoid accidental leverage on bad rows)
            exposure[i] = 1.0
            lev_flag[i] = 0
            signal[i] = "NOT_TRADABLE"
            continue

        z = float(df.loc[i, "bb_z"])

        # cooldown countdown
        if cooldown > 0:
            cooldown -= 1

        # exit conditions first (risk-first)
        exited = False
        if in_pos:
            hold_days += 1
            if z >= p.exit_z:
                in_pos = False
                hold_days = 0
                exited = True
                if p.cooldown_days > 0:
                    cooldown = p.cooldown_days
                signal[i] = "EXIT_Z"
            elif p.max_hold_days > 0 and hold_days >= p.max_hold_days:
                in_pos = False
                hold_days = 0
                exited = True
                if p.cooldown_days > 0:
                    cooldown = p.cooldown_days
                signal[i] = "EXIT_MAXHOLD"

        # enter
        if (not in_pos) and (not exited) and (cooldown == 0):
            if z <= p.enter_z:
                in_pos = True
                hold_days = 0
                signal[i] = "ENTER"

        # exposure
        if in_pos:
            exposure[i] = 1.0 + float(p.leverage_add)
            lev_flag[i] = 1
            if signal[i] == "HOLD":
                signal[i] = "IN_POS"
        else:
            exposure[i] = 1.0
            lev_flag[i] = 0
            if signal[i] == "HOLD":
                signal[i] = "FLAT_LEV"

    df["exposure"] = exposure
    df["lev_on"] = lev_flag
    df["signal"] = signal

    # financing cost: only on leveraged part
    daily_cost_rate = float(p.borrow_apr) / float(p.trading_days)
    df["fin_cost"] = df["lev_on"].astype(float) * float(p.leverage_add) * daily_cost_rate

    # equity curve (start at 1.0)
    eq = np.ones(len(df), dtype=float)
    for i in range(1, len(df)):
        r = df.loc[i, "ret"]
        if not np.isfinite(r):
            # no move if return missing
            eq[i] = eq[i - 1]
            continue
        gross = float(df.loc[i, "exposure"]) * float(r)
        cost = float(df.loc[i, "fin_cost"])
        eq[i] = eq[i - 1] * (1.0 + gross - cost)

    df["equity"] = eq

    # baseline (buy&hold) equity
    bh = np.ones(len(df), dtype=float)
    for i in range(1, len(df)):
        r = df.loc[i, "ret"]
        bh[i] = bh[i - 1] * (1.0 + (float(r) if np.isfinite(r) else 0.0))
    df["equity_bh"] = bh

    # summarize
    # use rows where equity is defined (all) but dates exist
    start_date = str(df["date"].iloc[0]) if len(df) else None
    end_date = str(df["date"].iloc[-1]) if len(df) else None

    # CAGR uses calendar years between first/last date_ts
    cagr = None
    cagr_bh = None
    years = None
    try:
        t0 = pd.to_datetime(df["date_ts"].iloc[0])
        t1 = pd.to_datetime(df["date_ts"].iloc[-1])
        days = max(1.0, float((t1 - t0).days))
        years = days / 365.25
        if years > 0:
            cagr = float((df["equity"].iloc[-1]) ** (1.0 / years) - 1.0)
            cagr_bh = float((df["equity_bh"].iloc[-1]) ** (1.0 / years) - 1.0)
    except Exception:
        pass

    # MDD
    eq_series = pd.Series(df["equity"].values, index=df["date"].values)
    bh_series = pd.Series(df["equity_bh"].values, index=df["date"].values)
    mdd, mdd_peak, mdd_trough = _max_drawdown(eq_series)
    mdd_bh, mdd_peak_bh, mdd_trough_bh = _max_drawdown(bh_series)

    # trade count: count ENTER signals
    enter_n = int((df["signal"] == "ENTER").sum())
    lev_days = int(df["lev_on"].sum())
    tradable_n = int(df["tradable"].sum())

    summary = {
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "generated_at_utc": utc_now_iso(),
        "date_range": {"start": start_date, "end": end_date},
        "rows": int(len(df)),
        "tradable_rows": tradable_n,
        "params": asdict(p),
        "results": {
            "equity_final": float(df["equity"].iloc[-1]) if len(df) else None,
            "equity_bh_final": float(df["equity_bh"].iloc[-1]) if len(df) else None,
            "years": years,
            "cagr": cagr,
            "cagr_bh": cagr_bh,
            "cagr_diff": (cagr - cagr_bh) if (cagr is not None and cagr_bh is not None) else None,
            "mdd": mdd,
            "mdd_bh": mdd_bh,
            "mdd_diff": (mdd - mdd_bh) if (mdd is not None and mdd_bh is not None) else None,
            "mdd_peak_date": mdd_peak,
            "mdd_trough_date": mdd_trough,
            "mdd_peak_date_bh": mdd_peak_bh,
            "mdd_trough_date_bh": mdd_trough_bh,
            "enter_trades": enter_n,
            "lev_days": lev_days,
        },
        "dq": {
            "notes": [
                "Leverage cost is charged on leveraged notional only: lev_on * leverage_add * (borrow_apr/252).",
                "Exposure is set to 1.0 on NOT_TRADABLE rows (conservative).",
                "This is an MVP backtest (no slippage, no taxes, no margin calls, no constraints).",
            ],
            "flags": [],
        },
    }

    return df, summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True, help="e.g. tw0050_bb_cache")
    ap.add_argument("--price_csv", default="data.csv")
    ap.add_argument("--out_equity_csv", default="equity_curve.csv")
    ap.add_argument("--out_summary_json", default="backtest_summary.json")

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_ddof", type=int, default=0)

    ap.add_argument("--enter_z", type=float, default=-1.5)
    ap.add_argument("--exit_z", type=float, default=0.0)
    ap.add_argument("--max_hold_days", type=int, default=60)
    ap.add_argument("--cooldown_days", type=int, default=0)

    ap.add_argument("--leverage_add", type=float, default=0.5, help="extra exposure beyond base 1.0, e.g. 0.5 => total 1.5x when on")
    ap.add_argument("--borrow_apr", type=float, default=0.035, help="annual financing rate, e.g. 0.035 = 3.5%")

    args = ap.parse_args()

    cache_dir = args.cache_dir
    price_path = os.path.join(cache_dir, args.price_csv)
    out_csv = os.path.join(cache_dir, args.out_equity_csv)
    out_json = os.path.join(cache_dir, args.out_summary_json)

    if not os.path.isfile(price_path):
        raise SystemExit(f"ERROR: missing price csv: {price_path}")

    df_raw = pd.read_csv(price_path)
    df_raw = _normalize_date_col(df_raw)
    price_col = _infer_price_col(df_raw)
    df_raw["price"] = pd.to_numeric(df_raw[price_col], errors="coerce")
    df_raw = df_raw.dropna(subset=["price"]).copy()

    params = StrategyParams(
        bb_window=int(args.bb_window),
        bb_ddof=int(args.bb_ddof),
        enter_z=float(args.enter_z),
        exit_z=float(args.exit_z),
        max_hold_days=int(args.max_hold_days),
        cooldown_days=int(args.cooldown_days),
        leverage_add=float(args.leverage_add),
        borrow_apr=float(args.borrow_apr),
    )

    df_bt, summary = run_backtest(df_raw, params)

    # Write outputs (minimal columns + full)
    cols = ["date", "price", "bb_z", "ret", "tradable", "signal", "lev_on", "exposure", "fin_cost", "equity", "equity_bh"]
    df_bt[cols].to_csv(out_csv, index=False)
    _write_json(out_json, summary)

    print(f"OK: wrote {out_csv}")
    print(f"OK: wrote {out_json}")
    # print short summary for logs
    res = summary.get("results", {})
    print("CAGR:", res.get("cagr"), "BH:", res.get("cagr_bh"), "DIFF:", res.get("cagr_diff"))
    print("MDD :", res.get("mdd"), "BH:", res.get("mdd_bh"), "DIFF:", res.get("mdd_diff"))
    print("Trades:", res.get("enter_trades"), "LevDays:", res.get("lev_days"))


if __name__ == "__main__":
    main()