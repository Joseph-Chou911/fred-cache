#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backtest_tw0050_tactical_cash.py

Purpose:
- Audit-first, simple "core hold + tactical cash overlay" backtest (NO borrowing / NO leverage).
- Tactical overlay uses MA filter (default MA60) to do low-frequency in/out for price-diff attempts.
- Designed to be easy to paste as a NEW file (no need to modify your long MVP script).

Model:
- Initial capital = 1.0 (normalized)
- Core: buy-and-hold shares = core_frac / p0
- Tactical cash = 1 - core_frac
- Signal:
    ON  if price > MA
    OFF otherwise
- When ON: invest all tactical cash (after entry costs) into tactical shares
- When OFF: liquidate all tactical shares (pay exit costs incl tax) back to cash

Costs:
- entry cost: notional * (fee_rate + slip_rate)
- exit  cost: notional * (fee_rate + tax_rate + slip_rate)
- slip_rate = slip_bps * 1e-4

Outputs (written to cache_dir):
- out_json (default: tactical_cash_backtest.json)
- out_equity_csv (default: tactical_cash_equity.csv)
- out_trades_csv (default: tactical_cash_trades.csv)
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone, date as _date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


SCRIPT_FINGERPRINT = "backtest_tw0050_tactical_cash@2026-02-24.v1"
SCHEMA_VERSION = "v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _json_sanitize(obj: Any, _depth: int = 0, _max_depth: int = 50) -> Any:
    if _depth > _max_depth:
        return str(obj)

    if obj is None:
        return None
    if isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.generic):
        try:
            return _json_sanitize(obj.item(), _depth=_depth + 1, _max_depth=_max_depth)
        except Exception:
            return None
    if isinstance(obj, (pd.Timestamp, datetime, _date)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    if isinstance(obj, (list, tuple, set)):
        return [_json_sanitize(x, _depth=_depth + 1, _max_depth=_max_depth) for x in list(obj)]
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            out[str(k)] = _json_sanitize(v, _depth=_depth + 1, _max_depth=_max_depth)
        return out
    try:
        s = str(obj)
        if s.lower() in ("nan", "inf", "-inf"):
            return None
        return s
    except Exception:
        return None


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    _ensure_parent(path)
    tmp = path + ".tmp"
    clean = _json_sanitize(obj)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


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
            print(f"WARNING: price_col not specified; falling back to first numeric column: {c!r}")
            return c

    raise SystemExit("ERROR: no numeric price column found in csv")


def _calc_sma(price: pd.Series, window: int) -> pd.Series:
    return price.rolling(window=window, min_periods=window).mean()


def _to_finite_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except Exception:
        return None
    return v if np.isfinite(v) else None


def _slip_rate(slip_bps: float) -> float:
    v = _to_finite_float(slip_bps)
    if v is None or v <= 0:
        return 0.0
    return float(v) * 1e-4


def _entry_cost(notional: float, fee_rate: float, slip_rate: float) -> float:
    if notional <= 0:
        return 0.0
    fr = max(float(fee_rate), 0.0)
    sr = max(float(slip_rate), 0.0)
    return float(notional) * (fr + sr)


def _exit_cost(notional: float, fee_rate: float, tax_rate: float, slip_rate: float) -> float:
    if notional <= 0:
        return 0.0
    fr = max(float(fee_rate), 0.0)
    tr = max(float(tax_rate), 0.0)
    sr = max(float(slip_rate), 0.0)
    return float(notional) * (fr + tr + sr)


def _max_drawdown(eq: pd.Series) -> Dict[str, Any]:
    eq = pd.to_numeric(eq, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if eq.empty:
        return {"mdd": None, "peak": None, "trough": None}

    v = eq.to_numpy(dtype=float)
    running_max = np.maximum.accumulate(v)
    running_max = np.where(running_max <= 0.0, np.nan, running_max)
    dd = (v / running_max) - 1.0
    if np.all(np.isnan(dd)):
        return {"mdd": None, "peak": None, "trough": None}

    trough_pos = int(np.nanargmin(dd))
    mdd = float(dd[trough_pos])

    peak_pos = int(np.nanargmax(v[: trough_pos + 1])) if trough_pos >= 0 else 0
    idx = eq.index
    peak = str(idx[peak_pos]) if peak_pos < len(idx) else None
    trough = str(idx[trough_pos]) if trough_pos < len(idx) else None
    return {"mdd": mdd, "peak": peak, "trough": trough, "peak_pos": peak_pos, "trough_pos": trough_pos}


def _perf_summary(eq: pd.Series, trading_days: int = 252, perf_ddof: int = 0) -> Dict[str, Any]:
    eq = pd.to_numeric(eq, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if eq.empty or len(eq) < 3:
        return {"ok": False}

    start = float(eq.iloc[0])
    end = float(eq.iloc[-1])
    n = int(len(eq))
    years = max((n - 1) / float(trading_days), 1e-12)

    cagr = (end / start) ** (1.0 / years) - 1.0 if (start > 0 and end > 0) else None

    rets = eq.pct_change().dropna()
    dd = int(perf_ddof)
    vol = float(rets.std(ddof=dd) * math.sqrt(trading_days)) if len(rets) > 2 else None
    sharpe = (
        (float(rets.mean()) / float(rets.std(ddof=dd))) * math.sqrt(trading_days)
        if (len(rets) > 2 and float(rets.std(ddof=dd)) > 0)
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
        "sharpe_note": "rf=0 assumed",
        "perf_ddof": dd,
        "mdd": mdd_info.get("mdd"),
        "mdd_peak": mdd_info.get("peak"),
        "mdd_trough": mdd_info.get("trough"),
    }


def _calmar(perf: Dict[str, Any]) -> Optional[float]:
    if not isinstance(perf, dict) or not perf.get("ok"):
        return None
    c = _to_finite_float(perf.get("cagr"))
    m = _to_finite_float(perf.get("mdd"))
    if c is None or m is None:
        return None
    denom = abs(float(m))
    return float(c) / denom if denom > 0 else None


def _trade_kpis(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "n_trades": 0,
        "win_rate": None,
        "avg_net_pnl": None,
        "profit_factor": None,
        "avg_hold_days": None,
        "time_in_market_pct": None,
    }
    if not trades:
        return out

    pnls: List[float] = []
    holds: List[int] = []
    in_mkt_days: List[int] = []

    for t in trades:
        v = _to_finite_float((t or {}).get("net_pnl_after_costs"))
        if v is not None:
            pnls.append(float(v))
        try:
            holds.append(int((t or {}).get("hold_days", 0) or 0))
        except Exception:
            holds.append(0)

    out["n_trades"] = int(len(pnls))
    if pnls:
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        out["win_rate"] = float(len(wins) / len(pnls))
        out["avg_net_pnl"] = float(np.mean(pnls))
        out["avg_hold_days"] = float(np.mean(holds)) if holds else None
        if losses:
            out["profit_factor"] = float(sum(wins) / abs(sum(losses))) if wins else 0.0
        else:
            out["profit_factor"] = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", default="data.csv")
    ap.add_argument("--price_col", default=None)

    ap.add_argument("--ma_window", type=int, default=60)
    ap.add_argument("--core_frac", type=float, default=0.90)

    ap.add_argument("--trading_days", type=int, default=252)
    ap.add_argument("--perf_ddof", type=int, default=0, choices=[0, 1])

    ap.add_argument("--fee_rate", type=float, default=0.001425)
    ap.add_argument("--tax_rate", type=float, default=0.0010)
    ap.add_argument("--slip_bps", type=float, default=5.0)

    ap.add_argument("--out_json", default="tactical_cash_backtest.json")
    ap.add_argument("--out_equity_csv", default="tactical_cash_equity.csv")
    ap.add_argument("--out_trades_csv", default="tactical_cash_trades.csv")

    args = ap.parse_args()

    if int(args.ma_window) < 2:
        raise SystemExit("ERROR: --ma_window must be >= 2")

    core_frac = float(args.core_frac)
    if (not np.isfinite(core_frac)) or core_frac <= 0.0 or core_frac >= 1.0:
        raise SystemExit("ERROR: --core_frac must be in (0,1), e.g. 0.9 or 0.8")

    cache_dir = str(args.cache_dir)
    price_path = os.path.join(cache_dir, str(args.price_csv))
    if not os.path.isfile(price_path):
        raise SystemExit(f"ERROR: missing price csv: {price_path}")

    df = pd.read_csv(price_path)
    df = _normalize_date_col(df)
    pc = _find_price_col(df, args.price_col)
    df["price"] = pd.to_numeric(df[pc], errors="coerce")
    df = df.dropna(subset=["price"]).sort_values("date_ts").reset_index(drop=True)

    p0 = float(df["price"].iloc[0])
    if not np.isfinite(p0) or p0 <= 0:
        raise SystemExit("ERROR: invalid first price")

    df["ma"] = _calc_sma(df["price"], int(args.ma_window))
    df["signal_on"] = (df["price"] > df["ma"]) & df["ma"].notna()

    slip_rate = _slip_rate(float(args.slip_bps))
    fee_rate = float(args.fee_rate)
    tax_rate = float(args.tax_rate)

    # portfolio state
    core_shares = float(core_frac) / p0
    cash0 = float(1.0 - core_frac)

    cash = float(cash0)
    tac_shares = 0.0
    in_pos = False
    hold_days = 0

    trades: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    equity: List[float] = []
    equity_base: List[float] = []
    overlay_on: List[bool] = []

    for i in range(len(df)):
        date = str(df.at[i, "date"])
        price = float(df.at[i, "price"])
        sig = bool(df.at[i, "signal_on"])

        # exit when signal turns off
        if in_pos and (not sig):
            proceeds = float(tac_shares * price)
            ex_cost = _exit_cost(proceeds, fee_rate, tax_rate, slip_rate)
            cash += (proceeds - ex_cost)

            if cur is not None:
                cur["exit_date"] = date
                cur["exit_price"] = price
                cur["exit_cost"] = float(ex_cost)
                cur["hold_days"] = int(hold_days)
                # net pnl for tactical leg (cash overlay)
                entry_notional = float(cur.get("entry_notional", 0.0))
                entry_cost = float(cur.get("entry_cost", 0.0))
                net_pnl = (proceeds - ex_cost) - (entry_notional + entry_cost)
                cur["net_pnl_after_costs"] = float(net_pnl)
                trades.append(cur)

            tac_shares = 0.0
            in_pos = False
            hold_days = 0
            cur = None

        # enter when signal turns on
        if (not in_pos) and sig:
            avail = float(cash)
            if avail > 0:
                denom = 1.0 + max(fee_rate, 0.0) + max(slip_rate, 0.0)
                entry_notional = float(avail / denom) if denom > 0 else 0.0
                en_cost = _entry_cost(entry_notional, fee_rate, slip_rate)
                shares = float(entry_notional / price) if price > 0 else 0.0
                if shares > 0 and entry_notional > 0:
                    cash -= (entry_notional + en_cost)
                    tac_shares = float(shares)
                    in_pos = True
                    hold_days = 0
                    cur = {
                        "entry_date": date,
                        "entry_price": price,
                        "entry_notional": float(entry_notional),
                        "tac_shares": float(tac_shares),
                        "entry_cost": float(en_cost),
                        "exit_date": None,
                        "exit_price": None,
                        "exit_cost": None,
                        "hold_days": None,
                        "net_pnl_after_costs": None,
                    }

        if in_pos:
            hold_days += 1

        eq = float(core_shares * price + tac_shares * price + cash)
        eq_base = float(core_shares * price + cash0)

        equity.append(eq)
        equity_base.append(eq_base)
        overlay_on.append(bool(in_pos))

    # force close at end if still open
    if in_pos:
        last_i = len(df) - 1
        date = str(df.at[last_i, "date"])
        price = float(df.at[last_i, "price"])
        proceeds = float(tac_shares * price)
        ex_cost = _exit_cost(proceeds, fee_rate, tax_rate, slip_rate)
        cash += (proceeds - ex_cost)

        if cur is not None:
            cur["exit_date"] = date
            cur["exit_price"] = price
            cur["exit_cost"] = float(ex_cost)
            cur["hold_days"] = int(hold_days)
            entry_notional = float(cur.get("entry_notional", 0.0))
            entry_cost = float(cur.get("entry_cost", 0.0))
            net_pnl = (proceeds - ex_cost) - (entry_notional + entry_cost)
            cur["net_pnl_after_costs"] = float(net_pnl)
            trades.append(cur)

        tac_shares = 0.0
        in_pos = False
        hold_days = 0
        cur = None

        equity[-1] = float(core_shares * price + cash)
        overlay_on[-1] = False

    df_out = df[["date", "date_ts", "price", "ma", "signal_on"]].copy()
    df_out["equity"] = equity
    df_out["equity_base_only"] = equity_base
    df_out["overlay_on"] = overlay_on

    perf = _perf_summary(df_out.set_index("date")["equity"], trading_days=int(args.trading_days), perf_ddof=int(args.perf_ddof))
    perf_base = _perf_summary(df_out.set_index("date")["equity_base_only"], trading_days=int(args.trading_days), perf_ddof=int(args.perf_ddof))

    out_json = {
        "generated_at_utc": utc_now_iso(),
        "schema_version": SCHEMA_VERSION,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "inputs": {
            "cache_dir": cache_dir,
            "price_csv": str(args.price_csv),
            "price_csv_resolved": price_path,
            "price_col": str(pc),
            "ma_window": int(args.ma_window),
            "core_frac": float(core_frac),
            "fee_rate": float(fee_rate),
            "tax_rate": float(tax_rate),
            "slip_bps": float(args.slip_bps),
            "slip_rate": float(slip_rate),
        },
        "audit": {
            "rows": int(len(df_out)),
            "start_date": str(df_out["date"].iloc[0]),
            "end_date": str(df_out["date"].iloc[-1]),
            "p0": float(p0),
            "core_shares": float(core_shares),
            "cash0": float(cash0),
            "n_trades": int(len(trades)),
            "time_in_market_days": int(sum(1 for x in overlay_on if x)),
            "time_in_market_pct": float(sum(1 for x in overlay_on if x) / len(overlay_on)) if overlay_on else None,
        },
        "perf": {
            "overlay": perf,
            "base_only": perf_base,
            "calmar_overlay": _calmar(perf),
            "calmar_base_only": _calmar(perf_base),
            "delta_vs_base": {
                "cagr": (perf.get("cagr") - perf_base.get("cagr")) if (perf.get("ok") and perf_base.get("ok") and perf.get("cagr") is not None and perf_base.get("cagr") is not None) else None,
                "mdd": (perf.get("mdd") - perf_base.get("mdd")) if (perf.get("ok") and perf_base.get("ok") and perf.get("mdd") is not None and perf_base.get("mdd") is not None) else None,
                "sharpe0": (perf.get("sharpe0") - perf_base.get("sharpe0")) if (perf.get("ok") and perf_base.get("ok") and perf.get("sharpe0") is not None and perf_base.get("sharpe0") is not None) else None,
            },
        },
        "trade_kpis": _trade_kpis(trades),
        "trades": trades,
    }

    out_json_path = os.path.join(cache_dir, str(args.out_json))
    out_eq_path = os.path.join(cache_dir, str(args.out_equity_csv))
    out_tr_path = os.path.join(cache_dir, str(args.out_trades_csv))

    _write_json(out_json_path, out_json)

    _ensure_parent(out_eq_path)
    df_out[["date", "price", "ma", "signal_on", "equity", "equity_base_only", "overlay_on"]].to_csv(
        out_eq_path, index=False, encoding="utf-8"
    )

    _ensure_parent(out_tr_path)
    pd.DataFrame(trades).to_csv(out_tr_path, index=False, encoding="utf-8")

    print(f"OK: wrote {out_json_path}")
    print(f"OK: wrote {out_eq_path}")
    print(f"OK: wrote {out_tr_path}")


if __name__ == "__main__":
    main()