#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ===== Audit stamp =====
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_forward_return_conditional@2026-02-21.v4"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s in ("", "N/A", "NA", "null", "None"):
            return None
        return float(s)
    except Exception:
        return None


def _safe_get(d: Any, path: List[str]) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        if k not in cur:
            return None
        cur = cur[k]
    return cur


def _pick(d: Dict[str, Any], paths: List[List[str]], default: Any = None) -> Any:
    for p in paths:
        v = _safe_get(d, p)
        if v is not None:
            return v
    return default


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _infer_price_last_date(df: pd.DataFrame, date_col: str = "date") -> Optional[str]:
    if df.empty or date_col not in df.columns:
        return None
    try:
        s = pd.to_datetime(df[date_col], errors="coerce")
        s = s.dropna()
        if s.empty:
            return None
        return s.max().date().isoformat()
    except Exception:
        return None


def _find_price_col(df: pd.DataFrame) -> str:
    cands = ["adjclose", "adj_close", "adj close", "adjClose", "Adj Close", "close", "Close"]
    cols_lc = {c.lower(): c for c in df.columns}
    for k in cands:
        if k.lower() in cols_lc:
            return cols_lc[k.lower()]
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise SystemExit("ERROR: no numeric price column found in price csv")


def _ensure_required(df: pd.DataFrame, cols: List[str]) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise SystemExit(f"ERROR: price csv missing required columns: {miss}")


def _calc_bb_z(series: pd.Series, window: int, ddof: int) -> pd.Series:
    ma = series.rolling(window=window, min_periods=window).mean()
    sd = series.rolling(window=window, min_periods=window).std(ddof=ddof)
    z = (series - ma) / (sd.replace(0.0, math.nan))
    return z


def _bucket_from_z(z: float, thr_near: float = 1.5, thr_extreme: float = 2.0) -> str:
    # canonical labels
    if z <= -thr_extreme:
        return "<=-2"
    if (-thr_extreme < z) and (z <= -thr_near):
        return "(-2,-1.5]"
    if (-thr_near < z) and (z < thr_near):
        return "(-1.5,1.5)"
    if (thr_near <= z) and (z < thr_extreme):
        return "[1.5,2)"
    return ">=2"


def _quantile(s: pd.Series, q: float) -> Optional[float]:
    if s.empty:
        return None
    try:
        return float(s.quantile(q))
    except Exception:
        return None


def _forward_return(series: pd.Series, horizon: int) -> pd.Series:
    fut = series.shift(-horizon)
    return (fut / series) - 1.0


def _detect_break_positions(price: pd.Series, hi: float, lo: float) -> np.ndarray:
    """
    break at index i means ratio = price[i] / price[i-1] triggers.
    """
    px = price.astype(float)
    prev = px.shift(1)
    ratio = px / prev
    # ignore invalid ratios
    bad = ratio.isna() | ~np.isfinite(ratio)
    ratio = ratio.mask(bad)
    is_break = (ratio > hi) | (ratio < lo)
    is_break = is_break.fillna(False)
    return np.where(is_break.values)[0]


def _contam_mask_from_breaks(n: int, break_pos: np.ndarray, horizon: int) -> np.ndarray:
    """
    If break occurs at i, it contaminates entries t where t < i <= t+horizon  => t in [i-horizon, i-1]
    Return boolean array length n: True => contaminated.
    """
    if n <= 0 or break_pos.size == 0:
        return np.zeros(n, dtype=bool)

    delta = np.zeros(n + 1, dtype=int)
    for i in break_pos:
        if i <= 0:
            continue
        start = max(0, int(i) - int(horizon))
        end = int(i)  # exclusive
        if start < end:
            delta[start] += 1
            delta[end] -= 1
    cum = np.cumsum(delta[:-1])
    return cum > 0


def _min_audit_global(part: pd.DataFrame, df_all: pd.DataFrame, ret_col: str, horizon: int) -> Dict[str, Any]:
    """
    part contains a subset of rows but MUST keep 't_pos' (global integer position in df_all).
    future row is df_all.iloc[t_pos + horizon].
    """
    if part.empty:
        return {}

    i = part[ret_col].idxmin()
    if pd.isna(i):
        return {}

    row = part.loc[i]
    t_pos = int(row["t_pos"])

    out: Dict[str, Any] = {
        "min": float(row[ret_col]),
        "min_entry_date": str(row["date"]),
        "min_entry_price": float(row["price"]),
    }

    # Because we ensure ret_col notna, t_pos+horizon should be valid; still guard.
    fut_pos = t_pos + horizon
    if 0 <= fut_pos < len(df_all):
        fut = df_all.iloc[fut_pos]
        out["min_future_date"] = str(fut["date"])
        out["min_future_price"] = float(fut["price"])
    else:
        out["min_future_date"] = None
        out["min_future_price"] = None

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", required=True)
    ap.add_argument("--stats_json", required=True)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)  # kept for meta consistency, z calc uses window/sd only
    ap.add_argument("--bb_ddof", type=int, default=0)
    ap.add_argument("--horizons", default="10,20")
    ap.add_argument("--break_ratio_hi", type=float, default=1.8)
    ap.add_argument("--break_ratio_lo", type=float, default=0.5555555556)
    ap.add_argument("--raw_min_contam_threshold", type=float, default=-0.40)
    args = ap.parse_args()

    cache_dir = args.cache_dir
    price_path = os.path.join(cache_dir, args.price_csv)
    stats_path = os.path.join(cache_dir, args.stats_json)
    out_path = os.path.join(cache_dir, args.out_json)

    if not os.path.isfile(price_path):
        raise SystemExit(f"ERROR: missing price csv: {price_path}")
    if not os.path.isfile(stats_path):
        raise SystemExit(f"ERROR: missing stats json: {stats_path}")

    stats = _read_json(stats_path)

    # ----- meta alignment from stats_latest.json -----
    stats_last_date = _pick(stats, [["meta", "last_date"], ["last_date"]], default=None)
    bb_window_stats = _pick(stats, [["meta", "bb_window"], ["bb_window"]], default=None)
    bb_k_stats = _pick(stats, [["meta", "bb_k"], ["bb_k"]], default=None)

    stats_build_fingerprint = _pick(
        stats,
        [
            ["meta", "script_fingerprint"],
            ["script_fingerprint"],
            ["meta", "build_script_fingerprint"],
            ["build_script_fingerprint"],
        ],
        default=None,
    )
    stats_generated_at_utc = _pick(
        stats,
        [
            ["meta", "run_ts_utc"],
            ["run_ts_utc"],
            ["meta", "generated_at_utc"],
            ["generated_at_utc"],
        ],
        default=None,
    )

    price_calc = _pick(stats, [["meta", "price_calc"], ["price_calc"]], default="adjclose")
    break_count = _pick(stats, [["meta", "break_detection", "break_count"]], default=None)

    # ----- read price csv -----
    df = pd.read_csv(price_path)
    if "date" not in df.columns:
        for c in ["Date", "DATE", "timestamp", "time", "Time"]:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break
    _ensure_required(df, ["date"])
    price_col = _find_price_col(df)

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    df["price"] = pd.to_numeric(df[price_col], errors="coerce")
    df = df.dropna(subset=["price"]).reset_index(drop=True)

    # global position for audit mapping
    df["t_pos"] = np.arange(len(df), dtype=int)

    price_last_date = _infer_price_last_date(df, "date")

    # compute bb_z
    df["bb_z"] = _calc_bb_z(df["price"], window=int(args.bb_window), ddof=int(args.bb_ddof))

    # horizons list
    horizons: List[int] = []
    for part in str(args.horizons).split(","):
        part = part.strip()
        if part:
            horizons.append(int(part))
    if not horizons:
        raise SystemExit("ERROR: --horizons empty")

    # compute forward returns
    for h in horizons:
        df[f"ret_{h}D"] = _forward_return(df["price"], horizon=h)

    # break detection on the same price series you compute returns on
    break_pos = _detect_break_positions(df["price"], hi=float(args.break_ratio_hi), lo=float(args.break_ratio_lo))

    out: Dict[str, Any] = {
        "decision_mode": "clean_only",
        "meta": {
            "generated_at_utc": utc_now_iso(),
            "build_script_fingerprint": BUILD_SCRIPT_FINGERPRINT,
            "cache_dir": cache_dir,
            "price_calc": price_calc,
            "stats_path": stats_path,
            "stats_last_date": stats_last_date,
            "bb_window_stats": bb_window_stats,
            "bb_k_stats": _to_float(bb_k_stats),
            "stats_build_fingerprint": stats_build_fingerprint,
            "stats_generated_at_utc": stats_generated_at_utc,
            "price_last_date": price_last_date,
        },
        "dq": {"flags": [], "notes": []},
        "forward_return_conditional": {
            "schema": "hier",
            "scheme": "bb_z_5bucket_v1",
            "thresholds": {"extreme": 2.0, "near": 1.5},
            "bb_window": int(args.bb_window),
            "bb_k": float(args.bb_k),
            "bb_ddof": int(args.bb_ddof),
            "break_detection": {
                "break_ratio_hi": float(args.break_ratio_hi),
                "break_ratio_lo": float(args.break_ratio_lo),
                "break_count": break_count,
            },
            "horizons": {},
            "current": {},
        },
    }

    # current fields (prefer stats.latest.bb_z)
    current_asof = _pick(stats, [["latest", "date"], ["meta", "last_date"], ["last_date"]], default=None)
    current_z = _pick(stats, [["latest", "bb_z"]], default=None)
    if current_z is None:
        try:
            current_z = float(df["bb_z"].iloc[-1])
        except Exception:
            current_z = None

    if current_z is not None:
        zf = float(current_z)
        if zf >= 2.0:
            cur_key, cur_can = "z_ge_2.0", ">=2"
        elif zf <= -2.0:
            cur_key, cur_can = "z_le_-2.0", "<=-2"
        elif -2.0 < zf <= -1.5:
            cur_key, cur_can = "z_-2.0_to_-1.5", "(-2,-1.5]"
        elif -1.5 < zf < 1.5:
            cur_key, cur_can = "z_-1.5_to_1.5", "(-1.5,1.5)"
        else:
            cur_key, cur_can = "z_1.5_to_2.0", "[1.5,2)"
        out["forward_return_conditional"]["current"] = {
            "asof_date": current_asof,
            "current_bb_z": zf,
            "current_bucket_key": cur_key,
            "current_bucket_canonical": cur_can,
        }
    else:
        out["forward_return_conditional"]["current"] = {
            "asof_date": current_asof,
            "current_bb_z": None,
            "current_bucket_key": None,
            "current_bucket_canonical": None,
        }

    def summarize_mode(h: int, mode_name: str, mask: pd.Series) -> Dict[str, Any]:
        dfm = df.loc[mask].copy()
        if dfm.empty:
            return {
                "definition": f"scheme=bb_z_5bucket_v1; horizon={h}D; mode={mode_name}",
                "n_total": 0,
                "by_bucket": [],
                "min_audit_by_bucket": [],
            }

        dfm["bucket_canonical"] = dfm["bb_z"].astype(float).map(lambda z: _bucket_from_z(float(z)))

        by_bucket: List[Dict[str, Any]] = []
        min_audit_by_bucket: List[Dict[str, Any]] = []

        ret_col = f"ret_{h}D"
        for bk in ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]:
            part = dfm[dfm["bucket_canonical"] == bk]
            n = int(len(part))
            if n == 0:
                continue

            s = part[ret_col]
            rec = {
                "bucket_canonical": bk,
                "n": n,
                "hit_rate": float((s > 0).mean()),
                "p50": _quantile(s, 0.50),
                "p25": _quantile(s, 0.25),
                "p10": _quantile(s, 0.10),
                "p05": _quantile(s, 0.05),
                "min": float(s.min()),
            }
            by_bucket.append(rec)

            ma = _min_audit_global(part, df, ret_col=ret_col, horizon=h)
            ma = {"bucket_canonical": bk, "n": n, **ma}
            min_audit_by_bucket.append(ma)

        return {
            "definition": f"scheme=bb_z_5bucket_v1; horizon={h}D; mode={mode_name}",
            "n_total": int(len(dfm)),
            "by_bucket": by_bucket,
            "min_audit_by_bucket": min_audit_by_bucket,
        }

    # base mask: z exists and return exists
    base_z = df["bb_z"].notna()

    # build horizons
    for h in horizons:
        ret_col = f"ret_{h}D"
        base_mask_h = base_z & df[ret_col].notna()

        # raw
        raw_obj = summarize_mode(h, "raw", base_mask_h)

        # clean: exclude windows contaminated by breaks in forward window
        contam = _contam_mask_from_breaks(len(df), break_pos, horizon=h)
        clean_mask_h = base_mask_h & (~pd.Series(contam, index=df.index))

        clean_obj = summarize_mode(h, "clean", clean_mask_h)

        out["forward_return_conditional"]["horizons"][f"{h}D"] = {
            "raw": raw_obj,
            "clean": clean_obj,
        }

        # optional dq note: how many excluded for this horizon
        excluded = int((base_mask_h & pd.Series(contam, index=df.index)).sum())
        if excluded > 0:
            out["dq"]["notes"].append(f"horizon={h}D excluded_by_break_mask={excluded}")

    # DQ: warn raw contamination by global min threshold
    raw_global_min = None
    try:
        mins = []
        for hk, hv in out["forward_return_conditional"]["horizons"].items():
            for row in hv.get("raw", {}).get("by_bucket", []):
                if row.get("min") is not None:
                    mins.append(float(row["min"]))
        if mins:
            raw_global_min = float(min(mins))
    except Exception:
        raw_global_min = None

    if raw_global_min is not None and raw_global_min <= float(args.raw_min_contam_threshold):
        out["dq"]["flags"].append("RAW_MODE_HAS_SPLIT_OUTLIERS")
        out["dq"]["notes"].append(
            f"raw_global_min={raw_global_min:.6f} <= {float(args.raw_min_contam_threshold):.2f}; "
            "treat raw as contaminated (split/outlier). Use clean_only."
        )

    _write_json(out_path, out)
    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()