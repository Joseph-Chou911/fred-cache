#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backtest_tw0050_tactical_cash.py

v2 (2026-02-24):
- ADD(segmentation/post-only): default evaluate ONLY "post" period after detected singularity/break.
  - default --segment_split_date=auto
  - prefer break samples from stats_latest.json (same cache) if available
  - fallback: detect breaks from price by ratio thresholds (hi/lo)
  - default post_start_date EXCLUDES split_date (use next trading row after split), aligned with MVP v26.8 policy
- AUDIT: write segmentation block into JSON output (split_date, post_start_date, policy, break evidence)
- NOTE: equity is normalized to 1.0 at the chosen period start (post). Results are NOT chainable to full period.

Purpose:
- Audit-first, simple "core hold + tactical cash overlay" backtest (NO borrowing / NO leverage).
- Tactical overlay uses MA filter (default MA60) to do low-frequency in/out for price-diff attempts.
- Designed to be easy to paste as a NEW file (no need to modify your long MVP script).

Model (within chosen analysis period, default: post):
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


SCRIPT_FINGERPRINT = "backtest_tw0050_tactical_cash@2026-02-24.v2.post_only_segmentation"
SCHEMA_VERSION = "v2"

_DEFAULT_RATIO_HI = 1.8
_DEFAULT_RATIO_LO = round(1.0 / _DEFAULT_RATIO_HI, 10)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _to_finite_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except Exception:
        return None
    return v if np.isfinite(v) else None


def _json_sanitize(obj: Any, _depth: int = 0, _max_depth: int = 60) -> Any:
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

    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            print(f"WARNING: price_col not specified; falling back to first numeric column: {c!r}")
            return c

    raise SystemExit("ERROR: no numeric price column found in csv")


def _calc_sma(price: pd.Series, window: int) -> pd.Series:
    return price.rolling(window=window, min_periods=window).mean()


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


def _trade_kpis(trades: List[Dict[str, Any]], time_in_market_pct: Optional[float]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "n_trades": 0,
        "win_rate": None,
        "avg_net_pnl": None,
        "profit_factor": None,
        "avg_hold_days": None,
        "time_in_market_pct": time_in_market_pct,
    }
    if not trades:
        return out

    pnls: List[float] = []
    holds: List[int] = []

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


# --------------------------
# Break detection / segmentation (post-only)
# --------------------------

def detect_breaks_from_price(df: pd.DataFrame, ratio_hi: float, ratio_lo: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if df is None or len(df) < 2:
        return out

    px = pd.to_numeric(df["price"], errors="coerce").to_numpy(dtype=float)
    dates = df["date"].astype(str).to_numpy()

    p0 = px[:-1]
    p1 = px[1:]
    valid = np.isfinite(p0) & np.isfinite(p1) & (p0 > 0.0)
    if not np.any(valid):
        return out

    ratio = np.full_like(p1, np.nan, dtype=float)
    ratio[valid] = p1[valid] / p0[valid]

    mask = (ratio >= float(ratio_hi)) | (ratio <= float(ratio_lo))
    idxs = (np.where(mask & np.isfinite(ratio))[0] + 1).astype(int)
    if idxs.size == 0:
        return out

    for i in idxs.tolist():
        j = i - 1
        ratio_val = float(ratio[j]) if (0 <= j < len(ratio) and np.isfinite(ratio[j])) else None
        out.append(
            {
                "idx": int(i),
                "break_date": str(dates[i]),
                "prev_date": str(dates[i - 1]),
                "prev_price": float(px[i - 1]) if np.isfinite(px[i - 1]) else None,
                "price": float(px[i]) if np.isfinite(px[i]) else None,
                "ratio": ratio_val,
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


def _parse_ymd(s: str) -> Optional[pd.Timestamp]:
    if s is None:
        return None
    ss = str(s).strip()
    if not ss:
        return None
    try:
        ts = pd.to_datetime(ss, errors="raise")
        return pd.Timestamp(ts.date())
    except Exception:
        return None


def _default_post_start_next_row(df_raw_in: pd.DataFrame, split_ts: pd.Timestamp) -> Tuple[pd.Timestamp, str]:
    """
    Exclude split day from post by default.
    Choose the next available trading row strictly AFTER split_ts.
    """
    try:
        cand = df_raw_in.loc[df_raw_in["date_ts"] > split_ts, "date_ts"]
        if cand is None or cand.empty:
            return split_ts, "fallback_split_date_no_later_row"
        ts = pd.Timestamp(cand.iloc[0])
        return pd.Timestamp(ts.date()), "next_row_after_split_date (exclude split day)"
    except Exception:
        return split_ts, "fallback_split_date_exception"


def _build_post_df(
    df_raw: pd.DataFrame,
    stats: Optional[Dict[str, Any]],
    seg_split_date: str,
    seg_break_rank: int,
    seg_post_start_date: Optional[str],
    ratio_hi: float,
    ratio_lo: float,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Returns (df_post, segmentation_audit).
    If segmentation can't be applied, df_post == df_raw and enabled=False.
    """
    seg: Dict[str, Any] = {
        "enabled": False,
        "mode": None,
        "split_date": None,
        "post_start_date": None,
        "post_start_policy": None,
        "break_rank": int(seg_break_rank),
        "breaks_detected": 0,
        "break_samples_first5": [],
        "break_samples_source": None,
        "notes": None,
    }

    spec = str(seg_split_date).strip()
    spec_l = spec.lower()

    disable_tokens = ["none", "off", "disable", "disabled", "0", "false"]
    if spec_l in disable_tokens:
        seg["enabled"] = False
        seg["mode"] = "none"
        seg["notes"] = "segmentation disabled by --segment_split_date=none/off"
        return df_raw, seg

    # get break samples: stats first, else detect
    raw_samples: List[Dict[str, Any]] = []
    source = None
    if isinstance(stats, dict):
        raw_samples, source = _extract_break_samples_from_stats(stats)

    breaks = raw_samples if raw_samples else detect_breaks_from_price(df_raw, ratio_hi, ratio_lo)
    seg["breaks_detected"] = int(len(breaks))
    seg["break_samples_first5"] = breaks[:5]
    seg["break_samples_source"] = source if raw_samples else "detect_breaks_from_price"

    split_ts: Optional[pd.Timestamp] = None
    if spec_l == "auto":
        rk = int(seg_break_rank)
        if breaks and 0 <= rk < len(breaks):
            split_ts = _parse_ymd(str(breaks[rk].get("break_date")))
            seg["mode"] = "auto_break_rank"
        else:
            seg["mode"] = "auto_break_rank"
            seg["notes"] = f"auto: break_rank={rk} out of range (breaks_detected={len(breaks)}); segmentation disabled"
            return df_raw, seg
    else:
        seg["mode"] = "manual"
        split_ts = _parse_ymd(spec)
        if split_ts is None:
            seg["notes"] = f"manual: could not parse --segment_split_date={spec!r}; segmentation disabled"
            return df_raw, seg

    if split_ts is None:
        seg["notes"] = "no valid split_date resolved; segmentation disabled"
        return df_raw, seg

    # post_start_date policy
    if seg_post_start_date:
        pst = _parse_ymd(seg_post_start_date)
        if pst is None:
            post_start_ts = split_ts
            post_policy = "manual_override_parse_failed_fallback_split_date"
        else:
            post_start_ts = pst
            post_policy = "manual_override"
    else:
        post_start_ts, post_policy = _default_post_start_next_row(df_raw, split_ts)

    seg["enabled"] = True
    seg["split_date"] = split_ts.date().isoformat()
    seg["post_start_date"] = post_start_ts.date().isoformat()
    seg["post_start_policy"] = post_policy
    seg["notes"] = (
        "post-only evaluation: equity is normalized to 1.0 at post_start_date. "
        "split_date is excluded from post by default (post starts at next trading row)."
    )

    df_post = df_raw.loc[df_raw["date_ts"] >= post_start_ts].copy().reset_index(drop=True)
    if df_post.empty:
        seg["enabled"] = False
        seg["notes"] = "post df empty after applying post_start_date; fallback to full df"
        return df_raw, seg

    return df_post, seg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", default="data.csv")
    ap.add_argument("--price_col", default=None)

    ap.add_argument("--stats_json", default="stats_latest.json")
    ap.add_argument("--segment_split_date", default="auto")
    ap.add_argument("--segment_break_rank", type=int, default=0)
    ap.add_argument("--segment_post_start_date", default=None)
    ap.add_argument("--break_ratio_hi", type=float, default=None)
    ap.add_argument("--break_ratio_lo", type=float, default=None)

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

    stats_path = os.path.join(cache_dir, str(args.stats_json))
    stats = _read_json(stats_path)

    ratio_hi = float(args.break_ratio_hi) if args.break_ratio_hi is not None else _DEFAULT_RATIO_HI
    ratio_lo = float(args.break_ratio_lo) if args.break_ratio_lo is not None else _DEFAULT_RATIO_LO

    # If stats has break_ratio overrides (best-effort)
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

    df = pd.read_csv(price_path)
    df = _normalize_date_col(df)
    pc = _find_price_col(df, args.price_col)
    df["price"] = pd.to_numeric(df[pc], errors="coerce")
    df = df.dropna(subset=["price"]).sort_values("date_ts").reset_index(drop=True)

    # Build post-only df (default: auto)
    df_use, seg_audit = _build_post_df(
        df_raw=df,
        stats=stats,
        seg_split_date=str(args.segment_split_date),
        seg_break_rank=int(args.segment_break_rank),
        seg_post_start_date=args.segment_post_start_date,
        ratio_hi=float(ratio_hi),
        ratio_lo=float(ratio_lo),
    )

    # Basic warmup guard
    if len(df_use) < int(args.ma_window) + 10:
        raise SystemExit(
            f"ERROR: not enough rows after segmentation for ma_window={args.ma_window}; "
            f"rows={len(df_use)}; consider disabling segmentation or lowering ma_window"
        )

    p0 = float(df_use["price"].iloc[0])
    if not np.isfinite(p0) or p0 <= 0:
        raise SystemExit("ERROR: invalid first price in chosen analysis period")

    df_use = df_use.copy()
    df_use["ma"] = _calc_sma(df_use["price"], int(args.ma_window))
    df_use["signal_on"] = (df_use["price"] > df_use["ma"]) & df_use["ma"].notna()

    slip_rate = _slip_rate(float(args.slip_bps))
    fee_rate = float(args.fee_rate)
    tax_rate = float(args.tax_rate)

    # portfolio state (normalized at p0 of analysis period)
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

    for i in range(len(df_use)):
        date = str(df_use.at[i, "date"])
        price = float(df_use.at[i, "price"])
        sig = bool(df_use.at[i, "signal_on"])

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
    if in_pos and len(df_use) > 0:
        last_i = len(df_use) - 1
        date = str(df_use.at[last_i, "date"])
        price = float(df_use.at[last_i, "price"])
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

    df_out = df_use[["date", "date_ts", "price", "ma", "signal_on"]].copy()
    df_out["equity"] = equity
    df_out["equity_base_only"] = equity_base
    df_out["overlay_on"] = overlay_on

    perf = _perf_summary(
        df_out.set_index("date")["equity"],
        trading_days=int(args.trading_days),
        perf_ddof=int(args.perf_ddof),
    )
    perf_base = _perf_summary(
        df_out.set_index("date")["equity_base_only"],
        trading_days=int(args.trading_days),
        perf_ddof=int(args.perf_ddof),
    )

    time_in_market_days = int(sum(1 for x in overlay_on if x))
    time_in_market_pct = float(time_in_market_days / len(overlay_on)) if overlay_on else None

    out_json = {
        "generated_at_utc": utc_now_iso(),
        "schema_version": SCHEMA_VERSION,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "inputs": {
            "cache_dir": cache_dir,
            "price_csv": str(args.price_csv),
            "price_csv_resolved": price_path,
            "stats_json": str(args.stats_json),
            "stats_json_resolved": stats_path if os.path.isfile(stats_path) else None,
            "price_col": str(pc),
            "ma_window": int(args.ma_window),
            "core_frac": float(core_frac),
            "fee_rate": float(fee_rate),
            "tax_rate": float(tax_rate),
            "slip_bps": float(args.slip_bps),
            "slip_rate": float(slip_rate),
            "break_ratio_hi": float(ratio_hi),
            "break_ratio_lo": float(ratio_lo),
            "segment_split_date": str(args.segment_split_date),
            "segment_break_rank": int(args.segment_break_rank),
            "segment_post_start_date": args.segment_post_start_date,
        },
        "segmentation": seg_audit,
        "audit": {
            "rows": int(len(df_out)),
            "start_date": str(df_out["date"].iloc[0]),
            "end_date": str(df_out["date"].iloc[-1]),
            "p0": float(p0),
            "core_shares": float(core_shares),
            "cash0": float(cash0),
            "n_trades": int(len(trades)),
            "time_in_market_days": time_in_market_days,
            "time_in_market_pct": time_in_market_pct,
            "normalization_note": "equity is normalized to 1.0 at analysis period start (default: post). not chainable to full period.",
        },
        "perf": {
            "overlay": perf,
            "base_only": perf_base,
            "calmar_overlay": _calmar(perf),
            "calmar_base_only": _calmar(perf_base),
            "delta_vs_base": {
                "cagr": (perf.get("cagr") - perf_base.get("cagr"))
                if (perf.get("ok") and perf_base.get("ok") and perf.get("cagr") is not None and perf_base.get("cagr") is not None)
                else None,
                "mdd": (perf.get("mdd") - perf_base.get("mdd"))
                if (perf.get("ok") and perf_base.get("ok") and perf.get("mdd") is not None and perf_base.get("mdd") is not None)
                else None,
                "sharpe0": (perf.get("sharpe0") - perf_base.get("sharpe0"))
                if (perf.get("ok") and perf_base.get("ok") and perf.get("sharpe0") is not None and perf_base.get("sharpe0") is not None)
                else None,
            },
        },
        "trade_kpis": _trade_kpis(trades, time_in_market_pct=time_in_market_pct),
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
    if seg_audit.get("enabled"):
        print("NOTE: post-only segmentation enabled:", seg_audit.get("split_date"), "->", seg_audit.get("post_start_date"))


if __name__ == "__main__":
    main()