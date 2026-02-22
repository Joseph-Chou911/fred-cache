#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backtest_tw0050_leverage_mvp.py

Audit-first MVP backtest for "base hold + conditional leverage leg" using BB z-score.

v26.4 (2026-02-22):
- FIX(critical): ranking uses bool(...) not identity compare (numpy.bool_ safe).
- FIX(robust): restore try/except guards for CSV writes (compare/equity/trades/post equity).
- FIX(safety): treat MemoryError as critical => abort suite even when --no-fail-fast.
- AUDIT: add skipped_entries_same_day_exit counter (entry signal blocked by exited_today).
- ROBUST: JSON sanitize NaN/Inf to null and enforce allow_nan=False.
- CLEANUP: df_ok filter uses vector boolean ops (ok & ~hard_fail).
- AUDIT: document maintenance_margin_interest_order and cost_on='all' semantics.
- AUDIT: add full_base_price_t0 back to compare rows.

v26.2 (2026-02-22):
- FIX: remove df_cmp.get() regression; use df_cmp["col"] with guaranteed columns.
- FIX: margin_call hold_days semantics aligned with normal exit (record hold_days+1 on trigger day).
- FIX: leftover version string "v24" updated to v26.2.
- REFACTOR: move _run_one_strategy to module-level for testability and clearer dependencies.
- PERF/MEM: after ranking, free large dfs for non-export strategies in results_by_sid.
- FIX: _add_boolopt sets dest consistently for both positive and negative flags.
- FIX: _segment_backtest guard order: validate first_price before min_rows check.

v26.1:
- maint_ratio_mode
- sanity checks
- segment_min_rows_mult
- vectorized break detection core
- export top-ranked strategy outputs
- out_post_equity_csv reuses cached post segment df

v26:
- maintenance margin / margin_call forced close at EOD.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date as _date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

SCHEMA_VERSION = "v26.4"
SCRIPT_FINGERPRINT = "backtest_tw0050_leverage_mvp@2026-02-22.v26.4.minimal_patches"


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
    dups = [c for c in TRADE_COLS if TRADE_COLS.count(c) > 1]
    raise SystemExit(f"ERROR: TRADE_COLS has duplicates: {sorted(set(dups))}")


_DEFAULT_RATIO_HI = 1.8
_DEFAULT_RATIO_LO = round(1.0 / _DEFAULT_RATIO_HI, 10)

MAINT_RATIO_MODES = [
    "equity_over_lever_notional",  # v26 default: equity / (lever_shares*price)
    "equity_over_borrow",          # equity / borrow_principal
    "equity_over_total_notional",  # equity / ((base+lever)*price)
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _json_sanitize(obj: Any, _depth: int = 0, _max_depth: int = 60) -> Any:
    """
    Make obj JSON-safe:
    - convert NaN/Inf/-Inf to None (null)
    - convert numpy scalars to Python scalars
    - convert pandas Timestamp / datetime / date to ISO strings
    - convert dict keys to str
    """
    if _depth > _max_depth:
        return str(obj)

    if obj is None:
        return None

    if isinstance(obj, (str, bool, int)):
        return obj

    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        return obj

    # numpy scalar -> python
    if isinstance(obj, np.generic):
        try:
            return _json_sanitize(obj.item(), _depth=_depth + 1, _max_depth=_max_depth)
        except Exception:
            return None

    # pandas / datetime
    if isinstance(obj, (pd.Timestamp, datetime, _date)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)

    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return str(obj)

    if isinstance(obj, (list, tuple, set)):
        return [_json_sanitize(x, _depth=_depth + 1, _max_depth=_max_depth) for x in list(obj)]

    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k)
            out[ks] = _json_sanitize(v, _depth=_depth + 1, _max_depth=_max_depth)
        return out

    # common containers that might appear
    try:
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return _json_sanitize(obj.to_dict(), _depth=_depth + 1, _max_depth=_max_depth)
    except Exception:
        pass

    # last resort
    try:
        s = str(obj)
        if s in ("nan", "NaN", "inf", "Inf", "-inf", "-Inf"):
            return None
        return s
    except Exception:
        return None


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    _ensure_parent(path)
    tmp = path + ".tmp"

    # v26.4: sanitize NaN/Inf and enforce allow_nan=False => strict JSON
    obj_clean = _json_sanitize(obj)

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj_clean, f, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise


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


def _calc_bb_z(price: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = price.rolling(window=window, min_periods=window).mean()
    sd = price.rolling(window=window, min_periods=window).std(ddof=ddof)
    sd = sd.replace(0.0, np.nan)
    z = (price - ma) / sd
    z = z.replace([np.inf, -np.inf], np.nan)
    return z


def _calc_sma(price: pd.Series, window: int) -> pd.Series:
    return price.rolling(window=window, min_periods=window).mean()


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


def _prepare_df(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
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


def _perf_summary(eq: pd.Series, trading_days: int = 252, perf_ddof: int = 0) -> Dict[str, Any]:
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
    dd = int(perf_ddof)
    vol = float(rets.std(ddof=dd) * math.sqrt(trading_days)) if len(rets) > 2 else None
    sharpe = (
        (float(rets.mean()) / float(rets.std(ddof=dd))) * math.sqrt(trading_days)
        if (len(rets) > 2 and float(rets.std(ddof=dd)) > 0)
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
        "perf_ddof": dd,
        "mdd": mdd_info.get("mdd"),
        "mdd_peak": mdd_info.get("peak"),
        "mdd_trough": mdd_info.get("trough"),
        "mdd_warning": mdd_info.get("mdd_warning"),
    }
    if cagr_warning is not None:
        out["cagr_warning"] = cagr_warning
    return out


def _calmar(perf: Dict[str, Any]) -> Optional[float]:
    if not isinstance(perf, dict) or not perf.get("ok"):
        return None
    c = perf.get("cagr")
    m = perf.get("mdd")
    if c is None or m is None:
        return None
    try:
        c = float(c)
        m = float(m)
    except Exception:
        return None
    if not np.isfinite(c) or not np.isfinite(m):
        return None
    denom = abs(m)
    if denom <= 0.0:
        return None
    return c / denom


def _slip_rate(slip_bps: float) -> float:
    try:
        v = float(slip_bps)
    except Exception:
        return 0.0
    if not np.isfinite(v) or v <= 0.0:
        return 0.0
    return v * 1e-4


def _entry_cost(notional: float, fee_rate: float, slip_rate: float) -> float:
    if not np.isfinite(notional) or not np.isfinite(fee_rate) or not np.isfinite(slip_rate):
        return 0.0
    if notional <= 0.0:
        return 0.0
    fr = max(float(fee_rate), 0.0)
    sr = max(float(slip_rate), 0.0)
    return float(notional) * (fr + sr)


def _exit_cost(notional: float, fee_rate: float, tax_rate: float, slip_rate: float) -> float:
    if (
        not np.isfinite(notional)
        or not np.isfinite(fee_rate)
        or not np.isfinite(tax_rate)
        or not np.isfinite(slip_rate)
    ):
        return 0.0
    if notional <= 0.0:
        return 0.0
    fr = max(float(fee_rate), 0.0)
    tr = max(float(tax_rate), 0.0)
    sr = max(float(slip_rate), 0.0)
    return float(notional) * (fr + tr + sr)


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
        out.append(
            {
                "idx": int(i),
                "break_date": str(dates[i]),
                "prev_date": str(dates[i - 1]),
                "prev_price": float(px[i - 1]) if np.isfinite(px[i - 1]) else None,
                "price": float(px[i]) if np.isfinite(px[i]) else None,
                "ratio": float(ratio[i - 1]) if np.isfinite(ratio[i - 1]) else None,
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

        rr = b.get("ratio", ratio)
        out.append(
            {
                "idx": int(idx),
                "break_date": str(dates[idx]),
                "prev_date": str(dates[prev_i]),
                "prev_price": p0,
                "price": p1,
                "ratio": float(rr) if rr is not None else None,
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
        hi = min(bi + zc - 1, n - 1)
        for i in range(lo, hi + 1):
            forbid[i] = True
    return forbid


def _turnover_from_lever_on(lever_on: pd.Series) -> Optional[float]:
    if lever_on is None:
        return None
    try:
        s = pd.Series(lever_on).astype(bool)
    except Exception:
        return None
    if len(s) < 2:
        return None
    changes = int((s.astype(int).diff().abs().fillna(0) > 0).sum())
    return float(changes) / float(len(s))


def _post_gonogo_decision(segmentation: Dict[str, Any], th: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rule_id": "post_gonogo_v3",
        "applies": False,
        "ok": False,
        "decision": "N/A",
        "interpretation": {
            "NO_GO": "All three post conditions met: stop / do not deploy / do not tune further.",
            "GO_OR_REVIEW": (
                "Stop rule NOT triggered. This is NOT a PASS. "
                "It only means the specific immediate stop rule did not fire."
            ),
        },
        "inputs": {},
        "reasons": [],
        "thresholds": {
            "delta_sharpe0_lt": th.get("delta_sharpe0_lt"),
            "delta_abs_mdd_gt": th.get("delta_abs_mdd_gt"),
            "delta_cagr_lt": th.get("delta_cagr_lt"),
            "rationale": th.get("rationale"),
        },
    }

    if not isinstance(segmentation, dict) or not segmentation.get("enabled"):
        out["reasons"].append("segmentation disabled or missing")
        return out

    seg_post = (segmentation.get("segments", {}) or {}).get("post", {})
    if not isinstance(seg_post, dict) or not seg_post.get("ok"):
        out["reasons"].append("post segment not ok")
        return out

    post_sum = seg_post.get("summary", {}) or {}
    d = (post_sum.get("delta_vs_base") or {})
    pL = (post_sum.get("perf_leverage") or {})
    pB = (post_sum.get("perf_base_only") or {})

    if not (isinstance(pL, dict) and pL.get("ok") and isinstance(pB, dict) and pB.get("ok")):
        out["reasons"].append("post perf missing or not ok")
        return out

    dc = d.get("cagr")
    ds = d.get("sharpe0")

    mL = pL.get("mdd")
    mB = pB.get("mdd")
    delta_abs_mdd = None
    try:
        if mL is not None and mB is not None:
            delta_abs_mdd = abs(float(mL)) - abs(float(mB))
    except Exception:
        delta_abs_mdd = None

    out["applies"] = True
    out["inputs"] = {
        "post_leverage": {"cagr": pL.get("cagr"), "mdd": pL.get("mdd"), "sharpe0": pL.get("sharpe0")},
        "post_base_only": {"cagr": pB.get("cagr"), "mdd": pB.get("mdd"), "sharpe0": pB.get("sharpe0")},
        "delta_vs_base": {"cagr": dc, "sharpe0": ds},
        "delta_abs_mdd": delta_abs_mdd,
    }

    def _is_finite(v: Any) -> bool:
        return _to_finite_float(v) is not None

    if not (_is_finite(ds) and _is_finite(dc) and _is_finite(delta_abs_mdd)):
        out["reasons"].append("missing/invalid numeric inputs for rule evaluation")
        return out

    dsf = float(ds)
    dcf = float(dc)
    dam = float(delta_abs_mdd)

    t_sh = float(th.get("delta_sharpe0_lt", 0.0))
    t_mdd = float(th.get("delta_abs_mdd_gt", 0.0))
    t_cagr = float(th.get("delta_cagr_lt", 0.01))

    cond1 = dsf < t_sh
    cond2 = dam > t_mdd
    cond3 = dcf < t_cagr

    out["ok"] = True
    out["conditions"] = {
        f"delta_sharpe0_lt_{t_sh}": cond1,
        f"delta_abs_mdd_gt_{t_mdd}": cond2,
        f"delta_cagr_lt_{t_cagr}": cond3,
    }

    if cond1 and cond2 and cond3:
        out["decision"] = "NO_GO"
        out["reasons"].append("all 3 post conditions met => stop / do not deploy")
    else:
        out["decision"] = "GO_OR_REVIEW"
        if not cond1:
            out["reasons"].append("delta_sharpe0 not below threshold")
        if not cond2:
            out["reasons"].append("delta_abs_mdd not above threshold (drawdown not worse enough)")
        if not cond3:
            out["reasons"].append("delta_cagr not below threshold")

    return out


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
    entry_mode: str  # "bb" or "always" or "trend"
    trend_rule: str
    trend_ma_fast: int
    trend_ma_slow: int
    perf_ddof: int
    maintenance_margin: float
    maint_ratio_mode: str


def _maint_ratio_semantics(mode: str) -> str:
    m = str(mode).strip()
    if m == "equity_over_borrow":
        return "maint_ratio = equity / borrow_principal (account equity vs loan principal)"
    if m == "equity_over_total_notional":
        return "maint_ratio = equity / ((base_shares+lever_shares)*price) (account equity vs total market value)"
    return "maint_ratio = equity / (lever_shares*price) (account equity vs lever leg notional; v26 default)"


def run_backtest(
    df: pd.DataFrame,
    params: Params,
    forbid_entry_mask: Optional[List[bool]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = _prepare_df(df)

    n = int(len(df))
    if n < params.bb_window + 5:
        raise ValueError("not enough rows for bb window")

    df["bb_z"] = _calc_bb_z(df["price"], window=params.bb_window, ddof=params.bb_ddof)

    ma_fast_n = max(int(params.trend_ma_fast), 1)
    ma_slow_n = max(int(params.trend_ma_slow), 1)
    df["ma_fast"] = _calc_sma(df["price"], window=ma_fast_n)
    df["ma_slow"] = _calc_sma(df["price"], window=ma_slow_n)

    p0 = float(df["price"].iloc[0])
    if not np.isfinite(p0) or p0 <= 0.0:
        raise ValueError("invalid first price")

    base_shares = 1.0 / p0
    lever_shares_target = max(float(base_shares) * float(params.leverage_frac), 0.0)

    prices = df["price"].to_numpy(dtype=float)
    zs = df["bb_z"].to_numpy(dtype=float)
    dates = df["date"].astype(str).to_numpy()
    ma_fast = df["ma_fast"].to_numpy(dtype=float)
    ma_slow = df["ma_slow"].to_numpy(dtype=float)

    lever_shares = 0.0
    borrow_principal = 0.0
    cash = 0.0
    in_lever = False
    hold_days = 0
    interest_paid_total = 0.0

    entry_cost_total = 0.0
    exit_cost_total = 0.0
    cost_paid_total = 0.0

    slip_rate = _slip_rate(params.slip_bps)

    trades: List[Dict[str, Any]] = []
    cur_trade: Optional[Dict[str, Any]] = None

    eq_arr = np.empty(n, dtype=float)
    base_arr = np.empty(n, dtype=float)
    lev_on_arr = np.empty(n, dtype=bool)

    skipped_entries_on_forbidden = 0
    skipped_entries_on_nonpositive_equity = 0
    skipped_entries_same_day_exit = 0  # v26.4 audit

    exit_count_by_exit_z = 0
    exit_count_by_max_hold_days = 0
    exit_count_by_trend_off = 0
    exit_count_by_end_of_data = 0
    forced_eod_close = 0

    margin_call_count = 0
    min_maint_ratio = None

    forbid = forbid_entry_mask if (forbid_entry_mask is not None and len(forbid_entry_mask) == n) else [False] * n

    def _trend_on(i: int) -> bool:
        if params.trend_rule == "price_gt_ma60":
            m = ma_slow[i]
            p = prices[i]
            if not np.isfinite(m) or not np.isfinite(p):
                return False
            return p > m
        f = ma_fast[i]
        s = ma_slow[i]
        if not np.isfinite(f) or not np.isfinite(s):
            return False
        return f > s

    def _entry_signal(i: int) -> bool:
        if params.entry_mode == "always":
            return True
        if params.entry_mode == "trend":
            return _trend_on(i)
        zf_entry = _to_finite_float(zs[i])
        return (zf_entry is not None) and (zf_entry <= float(params.entry_z))

    def _exit_signal(i: int) -> Tuple[bool, str]:
        by_time = (params.max_hold_days > 0 and hold_days >= params.max_hold_days)
        if by_time:
            return True, "max_hold_days"

        if params.entry_mode == "always":
            return False, "none"

        if params.entry_mode == "trend":
            if not _trend_on(i):
                return True, "trend_off"
            return False, "none"

        zf = _to_finite_float(zs[i])
        by_z = (zf is not None and zf >= float(params.exit_z))
        return (by_z, ("exit_z" if by_z else "none"))

    timing_assumption = "assume close-at-EOD on exit date; interest charged for that day before exit"

    def _maint_ratio(equity: float, lever_notional: float, total_notional: float, borrow: float) -> Optional[float]:
        mode = str(params.maint_ratio_mode).strip()
        if mode not in MAINT_RATIO_MODES:
            mode = "equity_over_lever_notional"

        denom = None
        if mode == "equity_over_borrow":
            denom = borrow
        elif mode == "equity_over_total_notional":
            denom = total_notional
        else:
            denom = lever_notional

        if denom is None or denom <= 0.0:
            return None
        if not np.isfinite(equity) or not np.isfinite(denom):
            return None
        return float(equity) / float(denom)

    for i in range(n):
        exited_today = False

        price = float(prices[i])
        z_raw = float(zs[i]) if np.isfinite(zs[i]) else float("nan")
        date = str(dates[i])

        # accrue interest at start of bar if in position
        if in_lever and borrow_principal > 0.0:
            interest = _daily_interest(borrow_principal, params.borrow_apr, params.trading_days)
            cash -= interest
            interest_paid_total += interest
            if cur_trade is not None:
                cur_trade["interest_paid"] = float(cur_trade.get("interest_paid", 0.0) + interest)

        base_now = base_shares * price

        # maintenance margin check BEFORE normal hold_days increment
        if in_lever and float(params.maintenance_margin) > 0.0:
            total_shares_flat = base_shares + lever_shares
            total_notional = float(total_shares_flat * price)
            equity_flat = float(total_notional + cash - borrow_principal)

            lever_notional = float(lever_shares * price)
            mr = _maint_ratio(equity_flat, lever_notional, total_notional, float(borrow_principal))

            if mr is not None:
                if (min_maint_ratio is None) or (mr < float(min_maint_ratio)):
                    min_maint_ratio = float(mr)

            if (mr is not None) and (mr < float(params.maintenance_margin)):
                hold_days_effective = int(hold_days) + 1  # v26.2 alignment

                proceeds = lever_shares * price

                if params.cost_on == "all":
                    notional_exit = (base_shares + lever_shares) * price
                else:
                    notional_exit = lever_shares * price

                exit_cost = _exit_cost(notional_exit, params.fee_rate, params.tax_rate, slip_rate)
                if exit_cost > 0.0:
                    cash -= exit_cost
                    exit_cost_total += exit_cost
                    cost_paid_total += exit_cost

                cash += proceeds
                cash -= borrow_principal

                if cur_trade is not None:
                    cur_trade["exit_date"] = date
                    cur_trade["exit_price"] = price
                    cur_trade["hold_days"] = int(hold_days_effective)
                    cur_trade["exit_reason"] = "margin_call"
                    cur_trade["exit_cost"] = float(exit_cost)
                    cost_paid = float(cur_trade.get("entry_cost", 0.0) + cur_trade.get("exit_cost", 0.0))
                    cur_trade["cost_paid"] = float(cost_paid)
                    lever_leg_pnl = float(proceeds - float(cur_trade.get("borrow_principal", 0.0)))
                    cur_trade["lever_leg_pnl"] = float(lever_leg_pnl)
                    net_after_costs = lever_leg_pnl - float(cur_trade.get("interest_paid", 0.0)) - cost_paid
                    cur_trade["net_lever_pnl_after_costs"] = float(net_after_costs)
                    trades.append(cur_trade)

                margin_call_count += 1

                borrow_principal = 0.0
                lever_shares = 0.0
                in_lever = False
                cur_trade = None
                hold_days = 0

                exited_today = True

        # normal exit logic
        if in_lever:
            hold_days += 1
            exit_now, exit_reason = _exit_signal(i)

            if exit_now:
                proceeds = lever_shares * price

                if params.cost_on == "all":
                    notional_exit = (base_shares + lever_shares) * price
                else:
                    notional_exit = lever_shares * price

                exit_cost = _exit_cost(notional_exit, params.fee_rate, params.tax_rate, slip_rate)
                if exit_cost > 0.0:
                    cash -= exit_cost
                    exit_cost_total += exit_cost
                    cost_paid_total += exit_cost

                cash += proceeds
                cash -= borrow_principal

                if cur_trade is not None:
                    cur_trade["exit_date"] = date
                    cur_trade["exit_price"] = price
                    cur_trade["hold_days"] = int(hold_days)
                    cur_trade["exit_reason"] = str(exit_reason)
                    cur_trade["exit_cost"] = float(exit_cost)
                    cost_paid = float(cur_trade.get("entry_cost", 0.0) + cur_trade.get("exit_cost", 0.0))
                    cur_trade["cost_paid"] = float(cost_paid)
                    lever_leg_pnl = float(proceeds - float(cur_trade.get("borrow_principal", 0.0)))
                    cur_trade["lever_leg_pnl"] = float(lever_leg_pnl)
                    net_after_costs = lever_leg_pnl - float(cur_trade.get("interest_paid", 0.0)) - cost_paid
                    cur_trade["net_lever_pnl_after_costs"] = float(net_after_costs)
                    trades.append(cur_trade)

                if exit_reason == "exit_z":
                    exit_count_by_exit_z += 1
                elif exit_reason == "max_hold_days":
                    exit_count_by_max_hold_days += 1
                elif exit_reason == "trend_off":
                    exit_count_by_trend_off += 1

                borrow_principal = 0.0
                lever_shares = 0.0
                in_lever = False
                cur_trade = None
                hold_days = 0

                exited_today = True

        # entry logic (v26.4: add skipped_entries_same_day_exit)
        if not in_lever:
            if exited_today:
                if _entry_signal(i):
                    skipped_entries_same_day_exit += 1
            else:
                if forbid[i]:
                    if _entry_signal(i):
                        skipped_entries_on_forbidden += 1
                else:
                    if _entry_signal(i):
                        equity_flat = (base_shares + lever_shares) * price + cash - borrow_principal
                        if equity_flat <= 0.0:
                            skipped_entries_on_nonpositive_equity += 1
                        elif lever_shares_target > 0.0:
                            borrow = float(lever_shares_target * price)
                            if borrow > 0.0:
                                if params.cost_on == "all":
                                    notional_entry = (base_shares + lever_shares_target) * price
                                else:
                                    notional_entry = lever_shares_target * price

                                entry_cost = _entry_cost(notional_entry, params.fee_rate, slip_rate)
                                if entry_cost > 0.0:
                                    cash -= entry_cost
                                    entry_cost_total += entry_cost
                                    cost_paid_total += entry_cost

                                borrow_principal = borrow
                                lever_shares = lever_shares_target
                                in_lever = True
                                hold_days = 0

                                zf_entry = _to_finite_float(z_raw)
                                cur_trade = {
                                    "entry_date": date,
                                    "entry_price": price,
                                    "entry_z": zf_entry,
                                    "borrow_principal": float(borrow_principal),
                                    "lever_shares": float(lever_shares),
                                    "entry_cost": float(entry_cost),
                                    "exit_cost": 0.0,
                                    "cost_paid": float(entry_cost),
                                    "interest_paid": 0.0,
                                }

        total_shares_eod = base_shares + lever_shares
        equity_eod = total_shares_eod * price + cash - borrow_principal
        eq_arr[i] = float(equity_eod)
        base_arr[i] = float(base_now)
        lev_on_arr[i] = bool(in_lever)

    open_at_end = bool(in_lever)
    if in_lever and cur_trade is not None and n > 0:
        last_price = float(prices[-1])
        last_date = str(dates[-1])
        proceeds = lever_shares * last_price

        if params.cost_on == "all":
            notional_exit = (base_shares + lever_shares) * last_price
        else:
            notional_exit = lever_shares * last_price

        exit_cost = _exit_cost(notional_exit, params.fee_rate, params.tax_rate, slip_rate)
        if exit_cost > 0.0:
            cash -= exit_cost
            exit_cost_total += exit_cost
            cost_paid_total += exit_cost

        cash += proceeds
        cash -= borrow_principal

        cur_trade["exit_date"] = last_date
        cur_trade["exit_price"] = last_price
        cur_trade["hold_days"] = int(hold_days)
        cur_trade["exit_reason"] = "end_of_data"
        cur_trade["exit_cost"] = float(exit_cost)
        cost_paid = float(cur_trade.get("entry_cost", 0.0) + float(cur_trade.get("exit_cost", 0.0)))
        cur_trade["cost_paid"] = float(cost_paid)
        cur_trade["lever_leg_pnl"] = float(proceeds - float(cur_trade.get("borrow_principal", 0.0)))
        net_after_costs = float(cur_trade["lever_leg_pnl"]) - float(cur_trade.get("interest_paid", 0.0)) - cost_paid
        cur_trade["net_lever_pnl_after_costs"] = float(net_after_costs)
        trades.append(cur_trade)

        forced_eod_close += 1
        exit_count_by_end_of_data += 1

        in_lever = False
        borrow_principal = 0.0
        lever_shares = 0.0
        cur_trade = None

        equity_final = base_shares * last_price + cash
        eq_arr[-1] = float(equity_final)
        lev_on_arr[-1] = False

    df_out = df[["date", "date_ts", "price", "bb_z", "ma_fast", "ma_slow"]].copy()
    df_out["equity"] = eq_arr
    df_out["equity_base_only"] = base_arr
    df_out["lever_on"] = lev_on_arr

    z_ser = pd.to_numeric(df_out["bb_z"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    z_non_nan = int(z_ser.notna().sum())
    first_valid = z_ser.first_valid_index()
    z_first_valid_date = None
    if first_valid is not None:
        try:
            z_first_valid_date = str(df_out.at[first_valid, "date"])
        except Exception:
            z_first_valid_date = None

    perf_leverage = _perf_summary(
        df_out.set_index("date")["equity"],
        trading_days=params.trading_days,
        perf_ddof=params.perf_ddof,
    )
    perf_base = _perf_summary(
        df_out.set_index("date")["equity_base_only"],
        trading_days=params.trading_days,
        perf_ddof=params.perf_ddof,
    )

    equity_min = None
    equity_negative_days = 0
    try:
        eqv = pd.to_numeric(df_out["equity"], errors="coerce").to_numpy(dtype=float)
        eqv2 = eqv[np.isfinite(eqv)]
        if eqv2.size > 0:
            equity_min = float(np.min(eqv2))
        equity_negative_days = int(np.sum(np.isfinite(eqv) & (eqv < 0.0)))
    except Exception:
        equity_min = None
        equity_negative_days = 0

    summary: Dict[str, Any] = {
        "generated_at_utc": utc_now_iso(),
        "schema_version": SCHEMA_VERSION,
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
            "fee_rate": float(params.fee_rate),
            "tax_rate": float(params.tax_rate),
            "slip_bps": float(params.slip_bps),
            "cost_on": str(params.cost_on),
            "entry_mode": str(params.entry_mode),
            "trend_rule": str(params.trend_rule),
            "trend_ma_fast": int(params.trend_ma_fast),
            "trend_ma_slow": int(params.trend_ma_slow),
            "perf_ddof": int(params.perf_ddof),
            "maintenance_margin": float(params.maintenance_margin),
            "maint_ratio_mode": str(params.maint_ratio_mode),
        },
        "audit": {
            "rows": int(len(df_out)),
            "start_date": str(df_out["date"].iloc[0]),
            "end_date": str(df_out["date"].iloc[-1]),
            "base_price_t0": float(p0),
            "base_shares": float(base_shares),
            "lever_shares_target": float(lever_shares_target),
            "bb_z_non_nan": z_non_nan,
            "bb_z_first_valid_date": z_first_valid_date,
            "interest_paid_total": float(interest_paid_total),
            "trades": int(len(trades)),
            "skipped_entries_on_forbidden": int(skipped_entries_on_forbidden),
            "skipped_entries_on_nonpositive_equity": int(skipped_entries_on_nonpositive_equity),
            "skipped_entries_same_day_exit": int(skipped_entries_same_day_exit),  # v26.4 audit
            "equity_negative_days": int(equity_negative_days),
            "equity_min": equity_min,
            "open_at_end": bool(open_at_end),
            "forced_eod_close": int(forced_eod_close),
            "exit_count_by_exit_z": int(exit_count_by_exit_z),
            "exit_count_by_max_hold_days": int(exit_count_by_max_hold_days),
            "exit_count_by_trend_off": int(exit_count_by_trend_off),
            "exit_count_by_end_of_data": int(exit_count_by_end_of_data),
            "margin_call_count": int(margin_call_count),
            "min_maintenance_ratio": float(min_maint_ratio) if min_maint_ratio is not None else None,
            "maintenance_margin": float(params.maintenance_margin),
            "maint_ratio_mode": str(params.maint_ratio_mode),
            "maintenance_ratio_semantics": _maint_ratio_semantics(params.maint_ratio_mode),
            "maintenance_margin_interest_order": (
                "Interest accrues at start of bar BEFORE maintenance check; "
                "margin_call decision uses post-interest cash/equity for that date."
            ),
            "hold_days_semantics": "entry day sets hold_days=0; increments by 1 each subsequent row while in position",
            "hold_days_exit_recording": (
                "normal exit records hold_days after increment (>=1 on first exit day); "
                "margin_call also records hold_days+1 on trigger day for consistency (v26.2)."
            ),
            "same_day_reentry": "blocked (exited_today flag); entry is skipped on the same bar after any exit",
            "interest_semantics": (
                "row-based accrual while in position; charged before exit on the exit date; "
                "timing assumption: close at end-of-day on exit date"
            ),
            "timing_assumption": timing_assumption,
            "end_of_data_policy": "if open position exists at end, force-close and record trade with exit_reason=end_of_data",
            "lever_leg_pnl_semantics": "gross PnL for leverage leg (proceeds - principal); net_after_costs = lever_leg_pnl - interest_paid - cost_paid",
            "costs_enabled": bool((params.fee_rate > 0.0) or (params.tax_rate > 0.0) or (params.slip_bps > 0.0)),
            "cost_on": str(params.cost_on),
            "cost_on_semantics": (
                "cost_on='lever' charges costs on lever leg notional only. "
                "cost_on='all' charges costs on (base+lever) notional for entry/exit as a conservative upper bound; "
                "base leg is held (not liquidated) but still counted in cost_on='all'."
            ),
            "slippage_model": "cash penalty = notional * slip_rate per side; slip_rate = slip_bps * 1e-4",
            "entry_cost_total": float(entry_cost_total),
            "exit_cost_total": float(exit_cost_total),
            "cost_paid_total": float(cost_paid_total),
            "leverage_definition": (
                "lever_shares_target = base_shares(t0) * leverage_frac; not rebalanced => effective leverage drifts with price"
            ),
        },
        "perf_leverage": perf_leverage,
        "perf_base_only": perf_base,
        "calmar_leverage": _calmar(perf_leverage),
        "calmar_base_only": _calmar(perf_base),
        "turnover_proxy": _turnover_from_lever_on(df_out["lever_on"]),
        "trades": trades,
    }

    if perf_leverage.get("ok") and perf_base.get("ok"):
        summary["delta_vs_base"] = {
            "cagr": (perf_leverage.get("cagr") - perf_base.get("cagr"))
            if (perf_leverage.get("cagr") is not None and perf_base.get("cagr") is not None)
            else None,
            "mdd": (perf_leverage.get("mdd") - perf_base.get("mdd"))
            if (perf_leverage.get("mdd") is not None and perf_base.get("mdd") is not None)
            else None,
            "sharpe0": (perf_leverage.get("sharpe0") - perf_base.get("sharpe0"))
            if (perf_leverage.get("sharpe0") is not None and perf_base.get("sharpe0") is not None)
            else None,
        }

    return df_out, summary


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


def _segment_backtest(
    name: str,
    df_seg: pd.DataFrame,
    params: Params,
    ratio_hi: float,
    ratio_lo: float,
    segment_min_rows_mult: float,
) -> Tuple[Dict[str, Any], Optional[pd.DataFrame]]:
    seg_out: Dict[str, Any] = {
        "segment": {
            "name": name,
            "rows_raw": int(len(df_seg)) if df_seg is not None else 0,
            "rows_clean": 0,
            "start_date": None,
            "end_date": None,
            "first_price": None,
        }
    }

    if df_seg is None or df_seg.empty:
        seg_out["ok"] = False
        seg_out["error"] = "empty segment"
        return seg_out, None

    df_clean = _prepare_df(df_seg)
    seg_out["segment"]["rows_clean"] = int(len(df_clean))

    if df_clean.empty:
        seg_out["ok"] = False
        seg_out["error"] = "empty after cleaning (all prices NaN?)"
        return seg_out, None

    seg_out["segment"]["start_date"] = str(df_clean["date"].iloc[0])
    seg_out["segment"]["end_date"] = str(df_clean["date"].iloc[-1])

    p0 = float(df_clean["price"].iloc[0])
    seg_out["segment"]["first_price"] = float(p0) if np.isfinite(p0) else None
    if (not np.isfinite(p0)) or p0 <= 0.0:
        seg_out["ok"] = False
        seg_out["error"] = "invalid first price in segment after cleaning"
        return seg_out, None

    mult = float(segment_min_rows_mult)
    if not np.isfinite(mult) or mult <= 0:
        mult = 3.0

    min_rows = max(int(math.ceil(int(params.bb_window) * mult)), int(params.bb_window) + 5)
    if int(len(df_clean)) < min_rows:
        seg_out["ok"] = False
        seg_out["error"] = (
            f"segment too short for BB warmup: rows_clean={len(df_clean)} min_rows={min_rows} "
            f"(bb_window={params.bb_window}, mult={mult})"
        )
        return seg_out, None

    raw_breaks_seg = detect_breaks_from_price(df_clean, ratio_hi, ratio_lo)
    breaks_aligned_seg = align_break_indices(df_clean, raw_breaks_seg)

    forbid_mask_seg = None
    if params.entry_mode == "bb" and bool(params.skip_contaminated) and len(breaks_aligned_seg) > 0:
        forbid_mask_seg = build_entry_forbidden_mask(
            n=len(df_clean),
            breaks=breaks_aligned_seg,
            contam_horizon=int(params.contam_horizon),
            z_clear_days=int(params.z_clear_days),
        )

    try:
        df_bt, seg_sum = run_backtest(df_clean, params, forbid_entry_mask=forbid_mask_seg)
    except Exception as e:
        seg_out["ok"] = False
        seg_out["error"] = f"exception: {type(e).__name__}: {e}"
        seg_out["breaks"] = {
            "breaks_detected": int(len(breaks_aligned_seg)),
            "break_samples_first5": breaks_aligned_seg[:5],
            "break_samples_source": "detect_breaks_from_price(segment)",
        }
        return seg_out, None

    seg_sum.setdefault("audit", {})
    seg_sum["audit"].update(
        {
            "breaks_detected": int(len(breaks_aligned_seg)),
            "break_samples_first5": breaks_aligned_seg[:5],
            "break_samples_source": "detect_breaks_from_price(segment)",
            "forbid_mask_applied": bool(forbid_mask_seg is not None),
            "forbid_mask_semantics": "for each break idx b: forbid entry i in [b-contam_horizon, b+z_clear_days-1]",
            "forbid_mask_scope_note": "applies forbid mask ONLY when entry_mode == 'bb'",
            "segment_min_rows_mult": float(mult),
            "segment_min_rows": int(min_rows),
        }
    )

    seg_out["ok"] = True
    seg_out["summary"] = seg_sum
    return seg_out, df_bt


def _seg_compare_block(seg_pre: Dict[str, Any], seg_post: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False,
        "basis": "post_minus_pre",
        "metrics": {},
        "notes": [
            "Segments are normalized independently (equity starts at 1.0 in each segment).",
            "Compare block is a summary delta, not a continuous equity backtest across split.",
        ],
    }

    if not (isinstance(seg_pre, dict) and seg_pre.get("ok") and isinstance(seg_post, dict) and seg_post.get("ok")):
        out["error"] = "pre/post not ok"
        return out

    pre_sum = seg_pre.get("summary", {}) or {}
    post_sum = seg_post.get("summary", {}) or {}

    def _get_num(d: Dict[str, Any], k: str) -> Optional[float]:
        v = d.get(k)
        return _to_finite_float(v)

    pre_perf = pre_sum.get("perf_leverage", {}) or {}
    post_perf = post_sum.get("perf_leverage", {}) or {}

    pre_cagr = _get_num(pre_perf, "cagr")
    post_cagr = _get_num(post_perf, "cagr")

    pre_sh = _get_num(pre_perf, "sharpe0")
    post_sh = _get_num(post_perf, "sharpe0")

    pre_mdd = _get_num(pre_perf, "mdd")
    post_mdd = _get_num(post_perf, "mdd")

    pre_calmar = _to_finite_float(pre_sum.get("calmar_leverage"))
    post_calmar = _to_finite_float(post_sum.get("calmar_leverage"))

    def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        return float(b - a)

    out["metrics"] = {
        "pre": {"cagr": pre_cagr, "sharpe0": pre_sh, "mdd": pre_mdd, "calmar": pre_calmar},
        "post": {"cagr": post_cagr, "sharpe0": post_sh, "mdd": post_mdd, "calmar": post_calmar},
        "delta_post_minus_pre": {
            "cagr": _delta(pre_cagr, post_cagr),
            "sharpe0": _delta(pre_sh, post_sh),
            "mdd": _delta(pre_mdd, post_mdd),
            "calmar": _delta(pre_calmar, post_calmar),
        },
    }
    out["ok"] = True
    return out


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


def _add_fail_fast_flag(ap: argparse.ArgumentParser) -> None:
    if hasattr(argparse, "BooleanOptionalAction"):
        ap.add_argument(
            "--fail_fast",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Fail fast on first strategy error (default true). Use --no-fail-fast to continue and record errors.",
        )
    else:
        ap.add_argument("--fail_fast", action="store_true", default=True)
        ap.add_argument("--no_fail_fast", dest="fail_fast", action="store_false")


def _add_boolopt(ap: argparse.ArgumentParser, name: str, default: bool, help_text: str) -> None:
    """
    v26.4: keep explicit dest and add hyphen/underscore aliases for robustness.
    Avoid BooleanOptionalAction here to keep CLI stable across Python versions.
    """
    flag = name.lstrip("-").replace("-", "_")
    # positive flags
    ap.add_argument(name, dest=flag, action="store_true", default=default, help=help_text)
    # add hyphen alias (suppressed)
    if "_" in flag:
        hy = "--" + flag.replace("_", "-")
        if hy != name:
            ap.add_argument(hy, dest=flag, action="store_true", default=default, help=argparse.SUPPRESS)

    # negative flags
    ap.add_argument(f"--no-{flag}", dest=flag, action="store_false", help=argparse.SUPPRESS)
    if "_" in flag:
        ap.add_argument(f"--no-{flag.replace('_', '-')}", dest=flag, action="store_false", help=argparse.SUPPRESS)


def _fmt_lever_mult(L: float) -> str:
    try:
        v = round(float(L), 2)
    except Exception:
        v = float(L)
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s


def _make_params_from_args(args: argparse.Namespace, leverage_frac: float, entry_mode: str, trend_rule: str) -> Params:
    return Params(
        bb_window=int(args.bb_window),
        bb_ddof=int(args.bb_ddof),
        entry_z=float(args.entry_z),
        exit_z=float(args.exit_z),
        leverage_frac=float(leverage_frac),
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
        entry_mode=str(entry_mode),
        trend_rule=str(trend_rule),
        trend_ma_fast=int(args.trend_ma_fast),
        trend_ma_slow=int(args.trend_ma_slow),
        perf_ddof=int(args.perf_ddof),
        maintenance_margin=float(args.maintenance_margin),
        maint_ratio_mode=str(args.maint_ratio_mode),
    )


def _hard_fail_eval(
    *,
    full_audit: Dict[str, Any],
    post_audit: Optional[Dict[str, Any]],
    scope: str,
    equity_le: float,
    any_negative_days: bool,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    def _check(audit: Dict[str, Any], tag: str) -> None:
        if not isinstance(audit, dict):
            return
        emin = _to_finite_float(audit.get("equity_min"))
        neg_days = audit.get("equity_negative_days")
        try:
            nd = int(neg_days) if neg_days is not None else 0
        except Exception:
            nd = 0

        if emin is not None and emin <= float(equity_le):
            reasons.append(f"{tag}: equity_min<= {equity_le} (equity_min={emin})")
        if bool(any_negative_days) and nd > 0:
            reasons.append(f"{tag}: equity_negative_days>0 (neg_days={nd})")

    sc = str(scope).lower().strip()
    if sc not in ["full", "post", "any"]:
        sc = "any"

    # Note: scope="post" checks post only by design (does not include full).
    if sc in ["full", "any"]:
        _check(full_audit, "full")
    if sc in ["post", "any"] and post_audit is not None:
        _check(post_audit, "post")

    return (len(reasons) > 0), reasons


def _run_one_strategy(
    *,
    strategy_id: str,
    df_raw_in: pd.DataFrame,
    params: Params,
    breaks_aligned_in: List[Dict[str, Any]],
    ratio_hi_in: float,
    ratio_lo_in: float,
    forbid_mask_full_in: Optional[List[bool]],
    seg_spec_in: str,
    seg_raw_in: str,
    segment_break_rank: int,
    segment_post_start_date: Optional[str],
    segment_min_rows_mult: float,
    omit_trades: bool,
    gonogo_th_in: Dict[str, Any],
) -> Tuple[Dict[str, Any], pd.DataFrame, Dict[str, Any], Optional[pd.DataFrame], Dict[str, Any]]:
    if params.entry_mode == "always" and int(params.max_hold_days) > 0:
        print(
            f"NOTE: strategy {strategy_id}: entry_mode=always with max_hold_days={params.max_hold_days} "
            "will exit/reenter periodically. With same-day reentry blocked, effective cycle is max_hold_days+1."
        )

    forbid_for_strategy = forbid_mask_full_in if (params.entry_mode == "bb") else None

    df_bt, summary = run_backtest(df_raw_in, params, forbid_entry_mask=forbid_for_strategy)

    segmentation: Dict[str, Any] = {
        "enabled": False,
        "mode": None,
        "split_date": None,
        "post_start_date": None,
        "break_rank": int(segment_break_rank),
        "notes": None,
        "segments": {},
        "compare": None,
        "compare_error": None,
        "compute_cost_note": "Per strategy: full + pre + post backtests (3x). Not optimized in v26.2.",
    }

    post_df_bt: Optional[pd.DataFrame] = None
    disable_tokens = ["none", "off", "disable", "disabled", "0", "false"]

    if seg_spec_in in disable_tokens:
        segmentation["enabled"] = False
        segmentation["mode"] = "none"
        segmentation["notes"] = "segmentation disabled by --segment_split_date=none/off"
    else:
        split_ts: Optional[pd.Timestamp] = None
        if seg_spec_in == "auto":
            rk = int(segment_break_rank)
            if len(breaks_aligned_in) > 0 and 0 <= rk < len(breaks_aligned_in):
                split_ts = _parse_ymd(str(breaks_aligned_in[rk].get("break_date")))
                segmentation["mode"] = "auto_break_rank"
            else:
                msg = f"segment_break_rank={rk} out of range (breaks_detected={len(breaks_aligned_in)}); segmentation disabled"
                print(f"WARNING: {msg}")
                segmentation["enabled"] = False
                segmentation["mode"] = "auto_break_rank"
                segmentation["notes"] = msg
                split_ts = None
        else:
            segmentation["mode"] = "manual"
            split_ts = _parse_ymd(seg_raw_in)
            if split_ts is None:
                print(f"WARNING: could not parse --segment_split_date={seg_raw_in!r} as YYYY-MM-DD; segmentation disabled")

        if split_ts is None:
            if segmentation.get("notes") is None:
                segmentation["enabled"] = False
                segmentation["notes"] = "no valid split_date (auto had no breaks, or manual date parse failed)"
        else:
            post_start_ts = _parse_ymd(segment_post_start_date) if segment_post_start_date else split_ts
            if post_start_ts is None:
                if segment_post_start_date:
                    print(
                        f"WARNING: could not parse --segment_post_start_date={segment_post_start_date!r}; fallback to split_date"
                    )
                post_start_ts = split_ts

            segmentation["enabled"] = True
            segmentation["split_date"] = split_ts.date().isoformat()
            segmentation["post_start_date"] = post_start_ts.date().isoformat()
            segmentation["notes"] = (
                "Each segment equity is normalized to 1.0 at its own start (base_shares=1/segment_first_price). "
                "Segment results are NOT chainable into a single continuous equity curve."
            )

            df_pre = df_raw_in.loc[df_raw_in["date_ts"] < split_ts].copy().reset_index(drop=True)
            df_post = df_raw_in.loc[df_raw_in["date_ts"] >= post_start_ts].copy().reset_index(drop=True)

            seg_pre, _pre_df_bt = _segment_backtest(
                "pre", df_pre, params, ratio_hi_in, ratio_lo_in, float(segment_min_rows_mult)
            )
            seg_post, post_df_bt = _segment_backtest(
                "post", df_post, params, ratio_hi_in, ratio_lo_in, float(segment_min_rows_mult)
            )

            segmentation["segments"]["pre"] = seg_pre
            segmentation["segments"]["post"] = seg_post

            try:
                if seg_pre.get("ok") and seg_post.get("ok"):
                    segmentation["compare"] = _seg_compare_block(seg_pre, seg_post)
            except Exception as e:
                segmentation["compare_error"] = f"{type(e).__name__}: {e}"

    gonogo = _post_gonogo_decision(segmentation, gonogo_th_in)

    out: Dict[str, Any] = {
        "strategy_id": str(strategy_id),
        "ok": True,
        "generated_at_utc": summary.get("generated_at_utc"),
        "schema_version": SCHEMA_VERSION,
        "script_fingerprint": summary.get("script_fingerprint"),
        "params": summary.get("params"),
        "audit": summary.get("audit"),
        "perf": {
            "leverage": summary.get("perf_leverage"),
            "base_only": summary.get("perf_base_only"),
            "calmar_leverage": summary.get("calmar_leverage"),
            "calmar_base_only": summary.get("calmar_base_only"),
            "turnover_proxy": summary.get("turnover_proxy"),
            "delta_vs_base": summary.get("delta_vs_base"),
        },
        "segmentation": segmentation,
        "post_gonogo": gonogo,
        "forbid_mask_scope": "bb_only",
        "forbid_mask_applied": bool(forbid_for_strategy is not None),
    }

    if omit_trades:
        out["trades_omitted"] = True
    else:
        out["trades"] = summary.get("trades", []) if isinstance(summary.get("trades", []), list) else []

    return out, df_bt, segmentation, post_df_bt, summary


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
    ap.add_argument(
        "--allow_inverted_z",
        action="store_true",
        default=False,
        help="If set, allow exit_z < entry_z for bb mode (NOT recommended; can cause strange behavior).",
    )

    ap.add_argument("--leverage_frac", "--leverage_add", dest="leverage_frac", type=float, default=0.5)
    ap.add_argument("--borrow_apr", type=float, default=0.035)

    ap.add_argument("--max_hold_days", type=int, default=0)
    ap.add_argument("--trading_days", type=int, default=252)

    ap.add_argument("--fee_rate", type=float, default=0.001425)
    ap.add_argument("--tax_rate", type=float, default=0.0010)
    ap.add_argument("--slip_bps", type=float, default=5.0)
    ap.add_argument("--cost_on", type=str, default="lever", choices=["lever", "all"])

    ap.add_argument("--perf_ddof", type=int, default=0, choices=[0, 1])

    ap.add_argument("--strategy_suite", type=str, default="all", choices=["all", "single_bb", "bench_only"])
    ap.add_argument(
        "--bench_lever_levels",
        type=str,
        default="1.1,1.2,1.3,1.5",
        help="comma-separated leverage multipliers (e.g. 1.1,1.2,1.3,1.5). leverage_frac = L-1.",
    )

    ap.add_argument("--trend_rule", type=str, default="price_gt_ma60", choices=["price_gt_ma60", "ma20_gt_ma60"])
    ap.add_argument("--trend_ma_fast", type=int, default=20)
    ap.add_argument("--trend_ma_slow", type=int, default=60)

    _add_skip_contaminated_flag(ap)
    _add_fail_fast_flag(ap)
    ap.add_argument("--contam_horizon", type=int, default=60)
    ap.add_argument("--z_clear_days", type=int, default=60)
    ap.add_argument("--break_ratio_hi", type=float, default=None)
    ap.add_argument("--break_ratio_lo", type=float, default=None)

    ap.add_argument("--segment_split_date", default="auto")
    ap.add_argument("--segment_break_rank", type=int, default=0)
    ap.add_argument("--segment_post_start_date", default=None)
    ap.add_argument(
        "--segment_min_rows_mult",
        type=float,
        default=3.0,
        help="Segment min rows = max(bb_window*mult, bb_window+5). Default 3.0 keeps v26 behavior; set 2.0 to relax.",
    )

    ap.add_argument("--omit_trades", action="store_true", default=False)

    ap.add_argument("--gonogo_delta_sharpe0_lt", type=float, default=0.0)
    ap.add_argument("--gonogo_delta_abs_mdd_gt", type=float, default=0.0)
    ap.add_argument("--gonogo_delta_cagr_lt", type=float, default=0.01)
    ap.add_argument(
        "--gonogo_rationale",
        type=str,
        default="stop rule: leverage must not degrade sharpe, must not worsen drawdown, and must add >=1% CAGR vs base in post segment",
    )

    ap.add_argument("--maintenance_margin", type=float, default=0.0)
    ap.add_argument(
        "--maint_ratio_mode",
        type=str,
        default="equity_over_lever_notional",
        choices=MAINT_RATIO_MODES,
        help="Maintenance ratio semantics. Default keeps v26: equity/(lever_shares*price).",
    )

    ap.add_argument("--hard_fail_scope", type=str, default="any", choices=["full", "post", "any"])
    ap.add_argument("--hard_fail_equity_le", type=float, default=0.0)
    _add_boolopt(
        ap,
        "--hard_fail_any_negative_days",
        default=True,
        help_text="If true, any equity_negative_days>0 triggers hard fail (default true). Use --no-hard_fail_any_negative_days (or --no-hard-fail-any-negative-days) to disable.",
    )

    ap.add_argument("--out_json", dest="out_json", default="backtest_mvp.json")
    ap.add_argument("--out_equity_csv", default="backtest_mvp_equity.csv")
    ap.add_argument("--out_trades_csv", default="backtest_mvp_trades.csv")
    ap.add_argument("--out_compare_csv", default="backtest_strategy_compare.csv")
    ap.add_argument("--out_post_equity_csv", default=None)

    args = ap.parse_args()

    # sanity checks
    if int(args.bb_window) < 2:
        raise SystemExit("ERROR: --bb_window must be >= 2")
    if int(args.trading_days) <= 0:
        raise SystemExit("ERROR: --trading_days must be > 0")
    if int(args.max_hold_days) < 0:
        raise SystemExit("ERROR: --max_hold_days must be >= 0")
    if float(args.leverage_frac) < 0.0:
        raise SystemExit("ERROR: --leverage_frac must be >= 0 (negative leverage not supported in this MVP)")
    if int(args.contam_horizon) < 0 or int(args.z_clear_days) < 0:
        raise SystemExit("ERROR: --contam_horizon and --z_clear_days must be >= 0")

    suite = str(args.strategy_suite)
    if suite in ["all", "single_bb"]:
        if (float(args.exit_z) < float(args.entry_z)) and (not bool(args.allow_inverted_z)):
            raise SystemExit("ERROR: exit_z < entry_z for bb strategy. If intentional, set --allow_inverted_z.")

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

    def _parse_levels(s: str) -> List[float]:
        out: List[float] = []
        for part in str(s).split(","):
            p = part.strip()
            if not p:
                continue
            try:
                v = float(p)
            except Exception:
                continue
            if not np.isfinite(v) or v <= 1.0:
                continue
            out.append(v)
        out = sorted(list(dict.fromkeys(out)))
        return out

    bench_levels = _parse_levels(args.bench_lever_levels)
    if not bench_levels:
        bench_levels = [1.1, 1.2, 1.3, 1.5]

    strategies: List[Tuple[str, Params]] = []

    if suite in ["all", "single_bb"]:
        p_bb = _make_params_from_args(
            args=args,
            leverage_frac=float(args.leverage_frac),
            entry_mode="bb",
            trend_rule=str(args.trend_rule),
        )
        strategies.append(("bb_conditional", p_bb))

    if suite in ["all", "bench_only"]:
        for L in bench_levels:
            frac = float(L - 1.0)
            sid = f"always_leverage_{_fmt_lever_mult(L)}x"
            p = _make_params_from_args(args=args, leverage_frac=frac, entry_mode="always", trend_rule=str(args.trend_rule))
            strategies.append((sid, p))

        for L in bench_levels:
            frac = float(L - 1.0)
            sid = f"trend_leverage_{args.trend_rule}_{_fmt_lever_mult(L)}x"
            p = _make_params_from_args(args=args, leverage_frac=frac, entry_mode="trend", trend_rule=str(args.trend_rule))
            strategies.append((sid, p))

    if not strategies:
        raise SystemExit("ERROR: no strategies selected (unexpected).")

    seg_raw = str(args.segment_split_date).strip()
    seg_spec = seg_raw.lower()

    gonogo_th = {
        "delta_sharpe0_lt": float(args.gonogo_delta_sharpe0_lt),
        "delta_abs_mdd_gt": float(args.gonogo_delta_abs_mdd_gt),
        "delta_cagr_lt": float(args.gonogo_delta_cagr_lt),
        "rationale": str(args.gonogo_rationale),
    }

    out_json_path = os.path.join(cache_dir, str(args.out_json))
    out_cmp_path = os.path.join(cache_dir, str(args.out_compare_csv))

    suite_out: Dict[str, Any] = {
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
            "break_ratio_hi": float(ratio_hi),
            "break_ratio_lo": float(ratio_lo),
            "break_ratio_policy": "ratio_lo defaults to 1/ratio_hi (symmetric inverse) unless overridden",
            "breaks_detected": int(len(breaks_aligned)),
            "break_samples_first5": breaks_aligned[:5],
            "break_samples_source": (break_samples_source or "stats_json_unknown_path") if raw_samples else "detect_breaks_from_price",
            "forbid_mask_built": bool(forbid_mask is not None),
            "forbid_mask_scope_note": "applies forbid mask ONLY when entry_mode == 'bb'",
            "gonogo_thresholds": gonogo_th,
            "maintenance_margin": float(args.maintenance_margin),
            "maint_ratio_mode": str(args.maint_ratio_mode),
            "maintenance_ratio_semantics": _maint_ratio_semantics(str(args.maint_ratio_mode)),
            "hard_fail_policy": {
                "scope": str(args.hard_fail_scope),
                "equity_le": float(args.hard_fail_equity_le),
                "any_negative_days": bool(getattr(args, "hard_fail_any_negative_days")),
            },
            "segment_min_rows_mult": float(args.segment_min_rows_mult),
        },
        "strategy_suite": {
            "mode": suite,
            "bench_levels": bench_levels,
            "trend_rule": str(args.trend_rule),
            "trend_ma_fast": int(args.trend_ma_fast),
            "trend_ma_slow": int(args.trend_ma_slow),
            "omit_trades": bool(args.omit_trades),
            "fail_fast": bool(args.fail_fast),
        },
        "strategies": [],
        "compare": {},
        "failed_strategies": [],
        "suite_ok": True,
        "abort_reason": None,
        "outputs": {},
        "notes": [
            "Hard-fail strategies are excluded from ranking.",
            "Maintenance margin forced close approximates margin call at EOD on trigger bar; intraday is not modeled.",
            "Maintenance ratio thresholds are NOT interchangeable across maint_ratio_mode values.",
            "JSON output is sanitized: NaN/Inf are converted to null; allow_nan=False enforced.",
        ],
    }

    compare_rows: List[Dict[str, Any]] = []
    abort_reason: Optional[str] = None

    results_by_sid: Dict[str, Dict[str, Any]] = {}

    for (sid, params) in strategies:
        try:
            strat_obj, df_bt, seg_obj, post_df_bt, summary_full = _run_one_strategy(
                strategy_id=sid,
                df_raw_in=df_raw,
                params=params,
                breaks_aligned_in=breaks_aligned,
                ratio_hi_in=ratio_hi,
                ratio_lo_in=ratio_lo,
                forbid_mask_full_in=forbid_mask,
                seg_spec_in=seg_spec,
                seg_raw_in=seg_raw,
                segment_break_rank=int(args.segment_break_rank),
                segment_post_start_date=args.segment_post_start_date,
                segment_min_rows_mult=float(args.segment_min_rows_mult),
                omit_trades=bool(args.omit_trades),
                gonogo_th_in=gonogo_th,
            )
        except Exception as e:
            err_type = type(e).__name__
            err_msg = f"strategy {sid}: {err_type}: {e}"

            suite_out["failed_strategies"].append(sid)
            suite_out["suite_ok"] = False
            suite_out["strategies"].append({"strategy_id": sid, "ok": False, "error": err_msg, "error_type": err_type})

            compare_rows.append(
                {
                    "strategy_id": sid,
                    "ok": False,
                    "post_ok": False,
                    "rank_basis": "error",
                    "error_type": err_type,
                    "hard_fail": True,
                    "hard_fail_reason": "strategy_error",
                }
            )

            is_critical = isinstance(e, MemoryError)  # v26.4 safety
            if bool(args.fail_fast) or is_critical:
                abort_reason = err_msg
                if is_critical and (not bool(args.fail_fast)):
                    print(f"ERROR: MemoryError treated as critical; aborting suite: {err_msg}")
                break
            else:
                continue

        # hard fail policy evaluation
        post_ok = False
        post_audit = None
        seg = strat_obj.get("segmentation", {}) or {}
        if isinstance(seg, dict) and seg.get("enabled"):
            post_seg = (seg.get("segments", {}) or {}).get("post", {})
            if isinstance(post_seg, dict) and post_seg.get("ok"):
                post_ok = True
                post_sum = post_seg.get("summary", {}) or {}
                post_audit = (post_sum.get("audit") or {})

        full_audit = (strat_obj.get("audit") or {})
        hard_fail, hard_reasons = _hard_fail_eval(
            full_audit=full_audit,
            post_audit=post_audit if isinstance(post_audit, dict) else None,
            scope=str(args.hard_fail_scope),
            equity_le=float(args.hard_fail_equity_le),
            any_negative_days=bool(getattr(args, "hard_fail_any_negative_days")),
        )
        strat_obj["hard_fail"] = bool(hard_fail)
        strat_obj["hard_fail_reasons"] = hard_reasons

        suite_out["strategies"].append(strat_obj)

        results_by_sid[sid] = {
            "df_bt": df_bt,
            "summary_full": summary_full,
            "strat_obj": strat_obj,
            "post_df_bt": post_df_bt,
        }

        perf = (strat_obj.get("perf") or {})
        pl = (perf.get("leverage") or {})
        delta = (perf.get("delta_vs_base") or {})

        post_seg_first_price = None
        post_cagr = None
        post_mdd = None
        post_sharpe0 = None
        post_calmar = None
        post_delta_cagr = None
        post_delta_sharpe0 = None

        if isinstance(seg, dict) and seg.get("enabled"):
            post_seg = (seg.get("segments", {}) or {}).get("post", {})
            if isinstance(post_seg, dict) and post_seg.get("ok"):
                post_sum = post_seg.get("summary", {}) or {}
                post_perf = post_sum.get("perf_leverage", {}) or {}
                post_cagr = post_perf.get("cagr")
                post_mdd = post_perf.get("mdd")
                post_sharpe0 = post_perf.get("sharpe0")
                post_calmar = post_sum.get("calmar_leverage")
                post_delta = post_sum.get("delta_vs_base", {}) or {}
                post_delta_cagr = post_delta.get("cagr")
                post_delta_sharpe0 = post_delta.get("sharpe0")
                try:
                    post_seg_first_price = (post_seg.get("segment") or {}).get("first_price")
                except Exception:
                    post_seg_first_price = None

        rank_basis = "post" if bool(post_ok) else "full"

        row = {
            "strategy_id": sid,
            "entry_mode": (strat_obj.get("params") or {}).get("entry_mode"),
            "leverage_multiplier": (
                1.0 + float((strat_obj.get("params") or {}).get("leverage_frac", 0.0))
                if _to_finite_float((strat_obj.get("params") or {}).get("leverage_frac")) is not None
                else None
            ),
            "maint_ratio_mode": (strat_obj.get("params") or {}).get("maint_ratio_mode"),
            "maintenance_margin": (strat_obj.get("params") or {}).get("maintenance_margin"),
            "full_base_price_t0": (full_audit or {}).get("base_price_t0"),  # v26.4 audit
            "full_cagr": pl.get("cagr"),
            "full_mdd": pl.get("mdd"),
            "full_sharpe0": pl.get("sharpe0"),
            "full_calmar": perf.get("calmar_leverage"),
            "full_turnover_proxy": perf.get("turnover_proxy"),
            "full_delta_cagr_vs_base": delta.get("cagr"),
            "full_delta_mdd_vs_base": delta.get("mdd"),
            "full_delta_sharpe0_vs_base": delta.get("sharpe0"),
            "post_ok": bool(post_ok),
            "post_segment_start_price": post_seg_first_price,
            "post_cagr": post_cagr,
            "post_mdd": post_mdd,
            "post_sharpe0": post_sharpe0,
            "post_calmar": post_calmar,
            "post_delta_cagr_vs_base": post_delta_cagr,
            "post_delta_sharpe0_vs_base": post_delta_sharpe0,
            "post_gonogo": (strat_obj.get("post_gonogo") or {}).get("decision"),
            "rank_basis": rank_basis,
            "hard_fail": bool(hard_fail),
            "hard_fail_reason": "; ".join(hard_reasons) if hard_reasons else None,
            "ok": True,
        }
        compare_rows.append(row)

    suite_out["abort_reason"] = abort_reason
    if abort_reason is not None:
        suite_out["suite_ok"] = False

    df_cmp = pd.DataFrame(compare_rows)

    # Ensure required columns exist
    for col, default in [
        ("strategy_id", None),
        ("ok", False),
        ("hard_fail", False),
        ("post_ok", False),
        ("post_calmar", np.nan),
        ("full_calmar", np.nan),
        ("post_sharpe0", np.nan),
        ("full_sharpe0", np.nan),
    ]:
        if col not in df_cmp.columns:
            df_cmp[col] = default

    df_cmp["ok"] = df_cmp["ok"].fillna(False)
    df_cmp["hard_fail"] = df_cmp["hard_fail"].fillna(False)
    df_cmp["post_ok"] = df_cmp["post_ok"].fillna(False)

    # Cast to bool dtype after fillna to avoid NaN->True pitfalls
    df_cmp["ok"] = df_cmp["ok"].astype(bool)
    df_cmp["hard_fail"] = df_cmp["hard_fail"].astype(bool)
    df_cmp["post_ok"] = df_cmp["post_ok"].astype(bool)

    def _finite_or_neginf(x: Any) -> float:
        v = _to_finite_float(x)
        return float(v) if v is not None else float("-inf")

    def _rank_calmar_row(r: pd.Series) -> float:
        # v26.4 critical fix: avoid identity checks (numpy.bool_ safe)
        if (not bool(r["ok"])) or bool(r["hard_fail"]):
            return float("-inf")
        if bool(r["post_ok"]):
            return _finite_or_neginf(r["post_calmar"])
        return _finite_or_neginf(r["full_calmar"])

    def _rank_sharpe_row(r: pd.Series) -> float:
        if (not bool(r["ok"])) or bool(r["hard_fail"]):
            return float("-inf")
        if bool(r["post_ok"]):
            return _finite_or_neginf(r["post_sharpe0"])
        return _finite_or_neginf(r["full_sharpe0"])

    if not df_cmp.empty:
        df_cmp["_rank_calmar"] = df_cmp.apply(_rank_calmar_row, axis=1)
        df_cmp["_rank_sharpe"] = df_cmp.apply(_rank_sharpe_row, axis=1)
        df_cmp = df_cmp.sort_values(by=["_rank_calmar", "_rank_sharpe"], ascending=[False, False]).reset_index(drop=True)

    # v26.4: safer boolean filter
    df_ok = df_cmp[df_cmp["ok"] & (~df_cmp["hard_fail"])]
    top3 = df_ok["strategy_id"].head(3).tolist() if (not df_ok.empty and "strategy_id" in df_ok.columns) else []

    compare_rows_sorted = (
        df_cmp.drop(columns=[c for c in ["_rank_calmar", "_rank_sharpe"] if c in df_cmp.columns], errors="ignore")
        .to_dict("records")
    )

    suite_out["compare"] = {
        "rows": compare_rows_sorted,
        "ranking_policy": "prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full; EXCLUDE hard_fail",
        "top3_by_policy": top3,
    }

    export_sid: Optional[str] = top3[0] if top3 else (next(iter(results_by_sid.keys()), None))

    suite_out["outputs"] = {
        "export_strategy_id": export_sid,
        "export_policy": "top1_by_compare_policy else first_success",
    }

    # write JSON and compare CSV (v26.4: compare CSV guarded)
    _write_json(out_json_path, suite_out)

    _ensure_parent(out_cmp_path)
    df_cmp_drop = df_cmp.drop(columns=[c for c in ["_rank_calmar", "_rank_sharpe"] if c in df_cmp.columns], errors="ignore")
    try:
        df_cmp_drop.to_csv(out_cmp_path, index=False, encoding="utf-8")
    except Exception as e:
        print(f"WARNING: failed to write compare csv: {e}")

    if export_sid is None or export_sid not in results_by_sid:
        print(f"OK: wrote {out_json_path}")
        print(f"OK: wrote {out_cmp_path}")
        if abort_reason is not None:
            raise SystemExit(f"ERROR: abort due to fail_fast: {abort_reason}")
        raise SystemExit("ERROR: no successful strategy results produced")

    # MEMORY: free non-export big dfs after ranking decided
    for s in list(results_by_sid.keys()):
        if s != export_sid:
            try:
                del results_by_sid[s]["df_bt"]
            except Exception:
                pass
            try:
                del results_by_sid[s]["post_df_bt"]
            except Exception:
                pass

    export_pack = results_by_sid[export_sid]
    df_bt_export: pd.DataFrame = export_pack["df_bt"]
    summary_export: Dict[str, Any] = export_pack["summary_full"]
    post_df_bt_export: Optional[pd.DataFrame] = export_pack.get("post_df_bt")

    out_eq_path = os.path.join(cache_dir, str(args.out_equity_csv))
    _ensure_parent(out_eq_path)
    try:
        df_bt_export[["date", "price", "bb_z", "ma_fast", "ma_slow", "equity", "equity_base_only", "lever_on"]].to_csv(
            out_eq_path, index=False, encoding="utf-8"
        )
    except Exception as e:
        print(f"WARNING: failed to write equity csv: {e}")

    out_tr_path = os.path.join(cache_dir, str(args.out_trades_csv))
    _ensure_parent(out_tr_path)
    try:
        trades_export = summary_export.get("trades", []) if isinstance(summary_export.get("trades", []), list) else []
        if len(trades_export) > 0:
            df_tr = pd.DataFrame(trades_export)
            for c in TRADE_COLS:
                if c not in df_tr.columns:
                    df_tr[c] = np.nan
            df_tr[TRADE_COLS].to_csv(out_tr_path, index=False, encoding="utf-8")
        else:
            pd.DataFrame(columns=TRADE_COLS).to_csv(out_tr_path, index=False, encoding="utf-8")
    except Exception as e:
        print(f"WARNING: failed to write trades csv: {e}")

    print(f"OK: wrote {out_json_path}")
    print(f"OK: wrote {out_cmp_path} (strategy comparison; post-first ranking; hard_fail excluded)")
    print(f"OK: wrote {out_eq_path}  (equity for EXPORTED strategy: {export_sid})")
    print(f"OK: wrote {out_tr_path}  (trades CSV for EXPORTED strategy: {export_sid})")

    if args.out_post_equity_csv:
        out_post_eq = os.path.join(cache_dir, str(args.out_post_equity_csv))
        if post_df_bt_export is not None and isinstance(post_df_bt_export, pd.DataFrame) and (not post_df_bt_export.empty):
            _ensure_parent(out_post_eq)
            try:
                post_df_bt_export[["date", "price", "bb_z", "ma_fast", "ma_slow", "equity", "equity_base_only", "lever_on"]].to_csv(
                    out_post_eq, index=False, encoding="utf-8"
                )
                print(f"OK: wrote {out_post_eq} (post segment equity; EXPORTED strategy; cached)")
            except Exception as e:
                print(f"WARNING: failed to write post equity csv: {e}")
        else:
            print("WARNING: --out_post_equity_csv specified but cached post segment equity is not available; skip writing.")

    if abort_reason is not None:
        raise SystemExit(f"ERROR: abort due to fail_fast: {abort_reason}")


if __name__ == "__main__":
    main()