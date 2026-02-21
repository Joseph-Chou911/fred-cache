#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ===== Audit stamp =====
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_forward_return_conditional@2026-02-21.v7_2"


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


def _infer_price_last_date(df: pd.DataFrame, date_ts_col: str = "date_ts") -> Optional[str]:
    if df.empty or date_ts_col not in df.columns:
        return None
    try:
        s = pd.to_datetime(df[date_ts_col], errors="coerce").dropna()
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

    Note: if multiple rows share the minimum return, the first occurrence (by index order) is used.
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

    fut_pos = t_pos + horizon
    if 0 <= fut_pos < len(df_all):
        fut = df_all.iloc[fut_pos]
        out["min_future_date"] = str(fut["date"])
        out["min_future_price"] = float(fut["price"])
    else:
        out["min_future_date"] = None
        out["min_future_price"] = None

    return out


def _current_bucket_key(z: float) -> Dict[str, str]:
    if z >= 2.0:
        return {"key": "z_ge_2.0", "canonical": ">=2"}
    if z <= -2.0:
        return {"key": "z_le_-2.0", "canonical": "<=-2"}
    if -2.0 < z <= -1.5:
        return {"key": "z_-2.0_to_-1.5", "canonical": "(-2,-1.5]"}
    if -1.5 < z < 1.5:
        return {"key": "z_-1.5_to_1.5", "canonical": "(-1.5,1.5)"}
    return {"key": "z_1.5_to_2.0", "canonical": "[1.5,2)"}


def _parse_horizons(s: str) -> List[int]:
    out: List[int] = []
    for part in str(s).split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise SystemExit("ERROR: --horizons empty")
    return out


def _normalize_date_col(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns:
        for c in ["Date", "DATE", "timestamp", "time", "Time"]:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break
    _ensure_required(df, ["date"])
    df["date_ts"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_ts"]).sort_values("date_ts")
    df["date"] = df["date_ts"].dt.date.astype(str)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", required=True)
    ap.add_argument("--stats_json", required=True)
    ap.add_argument("--out_json", required=True)

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)  # kept for meta consistency
    ap.add_argument("--bb_ddof", type=int, default=0)
    ap.add_argument("--horizons", default="10,20")

    ap.add_argument("--break_ratio_hi", type=float, default=1.8)
    ap.add_argument("--break_ratio_lo", type=float, default=0.5555555556)

    ap.add_argument("--raw_min_contam_threshold", type=float, default=-0.40)

    # NEW (Phase 1): lookback window
    ap.add_argument("--lookback_years", type=int, default=0, help="0=all; e.g. 3 or 5 for last N years only")
    ap.add_argument("--break_samples_n", type=int, default=5)
    ap.add_argument("--excluded_entries_sample_n", type=int, default=5)

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
    break_count_stats = _pick(stats, [["meta", "break_detection", "break_count"]], default=None)

    # ----- read price csv -----
    df_raw = pd.read_csv(price_path)
    df_raw = _normalize_date_col(df_raw)

    price_col = _find_price_col(df_raw)
    df_raw["price"] = pd.to_numeric(df_raw[price_col], errors="coerce")
    df_raw = df_raw.dropna(subset=["price"]).copy()

    # final cleaned full series (df_all)
    df = df_raw.sort_values("date_ts").reset_index(drop=True)
    df["t_pos"] = np.arange(len(df), dtype=int)
    rows_price_csv = int(len(df))

    price_last_date = _infer_price_last_date(df, "date_ts")

    # compute bb_z on full series
    df["bb_z"] = _calc_bb_z(df["price"], window=int(args.bb_window), ddof=int(args.bb_ddof))
    df["bb_z"] = df["bb_z"].replace([np.inf, -np.inf], np.nan)

    # compute forward returns on full series
    horizons = _parse_horizons(args.horizons)
    for h in horizons:
        df[f"ret_{h}D"] = _forward_return(df["price"], horizon=h)

    # break detection on the same price series you compute returns on
    break_pos = _detect_break_positions(df["price"], hi=float(args.break_ratio_hi), lo=float(args.break_ratio_lo))
    break_count_detected = int(len(break_pos))

    # break_samples (first N)
    break_samples: List[Dict[str, Any]] = []
    max_bs = max(0, int(args.break_samples_n))
    if max_bs > 0 and break_count_detected > 0:
        for i in break_pos[:max_bs]:
            if i <= 0 or i >= len(df):
                continue
            prev = df.iloc[i - 1]
            cur = df.iloc[i]
            ratio = float(cur["price"]) / float(prev["price"]) if float(prev["price"]) != 0.0 else math.nan
            break_samples.append(
                {
                    "break_index": int(i),
                    "break_date": str(cur["date"]),
                    "prev_date": str(prev["date"]),
                    "prev_price": float(prev["price"]),
                    "price": float(cur["price"]),
                    "ratio": float(ratio) if np.isfinite(ratio) else None,
                }
            )

    # lookback mask (aligned to df)
    lookback_years = int(args.lookback_years)
    if lookback_years > 0:
        max_dt = pd.to_datetime(df["date_ts"]).max()
        cutoff = max_dt - pd.DateOffset(years=lookback_years)
        lookback_mask = (df["date_ts"] >= cutoff)
        lookback_start_date = cutoff.date().isoformat()
    else:
        lookback_mask = pd.Series(True, index=df.index, dtype=bool)
        lookback_start_date = None

    # base mask: z exists
    base_z = df["bb_z"].notna() & np.isfinite(df["bb_z"].astype(float))

    out: Dict[str, Any] = {
        "decision_mode": "clean_only",
        "meta": {
            "generated_at_utc": utc_now_iso(),
            "build_script_fingerprint": BUILD_SCRIPT_FINGERPRINT,
            "cache_dir": cache_dir,
            "price_csv": args.price_csv,
            "stats_json": args.stats_json,
            "out_json": args.out_json,
            "price_calc": price_calc,
            "stats_path": stats_path,
            "stats_last_date": stats_last_date,
            "bb_window_stats": bb_window_stats,
            "bb_k_stats": _to_float(bb_k_stats),
            "stats_build_fingerprint": stats_build_fingerprint,
            "stats_generated_at_utc": stats_generated_at_utc,
            "price_last_date": price_last_date,
            "rows_price_csv": rows_price_csv,
            "lookback_years": lookback_years,
            "lookback_start_date": lookback_start_date,
        },
        "dq": {"flags": [], "notes": []},
        "forward_return_conditional": {
            "schema": "hier",
            "scheme": "bb_z_5bucket_v1",
            "thresholds": {"extreme": 2.0, "near": 1.5},
            "bb_window": int(args.bb_window),
            "bb_k": float(args.bb_k),
            "bb_ddof": int(args.bb_ddof),
            "policy": {
                "decision_mode": "clean_only",
                "raw_usable": False,
                "raw_policy": "audit_only_do_not_use",
            },
            "break_detection": {
                "break_ratio_hi": float(args.break_ratio_hi),
                "break_ratio_lo": float(args.break_ratio_lo),
                "break_count_stats": break_count_stats,
                "break_count_detected": break_count_detected,
                "break_samples": break_samples,
            },
            "horizons": {},
            "current": {},
            "self_check": {"enabled": False, "by_horizon": {}},
        },
    }

    # --- Audit cross-check: break_count from stats vs detected from price_csv series ---
    if break_count_stats is not None:
        try:
            bc_stats_i = int(break_count_stats)
            if bc_stats_i != break_count_detected:
                out["dq"]["flags"].append("BREAK_COUNT_MISMATCH_STATS_VS_DETECTED")
                out["dq"]["notes"].append(
                    f"break_count mismatch: stats={bc_stats_i} vs detected={break_count_detected}; "
                    "forward_return_conditional uses detected breaks from price_csv series."
                )
        except Exception:
            out["dq"]["flags"].append("BREAK_COUNT_STATS_NONINT")
            out["dq"]["notes"].append(f"break_count_stats non-int: {break_count_stats!r}")

    # --- Audit note: hi/lo symmetry check (lo should be approx 1/hi) ---
    try:
        hi = float(args.break_ratio_hi)
        lo = float(args.break_ratio_lo)
        if np.isfinite(hi) and hi > 0.0 and np.isfinite(lo) and lo > 0.0:
            expected_lo = 1.0 / hi
            if abs(lo - expected_lo) > 1e-6:
                out["dq"]["flags"].append("BREAK_RATIO_LO_ASYMMETRIC")
                out["dq"]["notes"].append(
                    f"break_ratio_lo={lo} != 1/break_ratio_hi={expected_lo}; "
                    "this may be intentional, but can drift if only hi is adjusted."
                )
    except Exception:
        pass

    # current fields (prefer stats.latest.bb_z)
    current_asof = _pick(stats, [["latest", "date"], ["meta", "last_date"], ["last_date"]], default=None)
    current_z = _pick(stats, [["latest", "bb_z"]], default=None)
    if current_z is None:
        try:
            current_z = float(df["bb_z"].iloc[-1])
        except Exception:
            current_z = None

    if current_z is not None and np.isfinite(float(current_z)):
        zf = float(current_z)
        ck = _current_bucket_key(zf)
        out["forward_return_conditional"]["current"] = {
            "asof_date": current_asof,
            "current_bb_z": zf,
            "current_bucket_key": ck["key"],
            "current_bucket_canonical": ck["canonical"],
        }
    else:
        out["forward_return_conditional"]["current"] = {
            "asof_date": current_asof,
            "current_bb_z": None,
            "current_bucket_key": None,
            "current_bucket_canonical": None,
        }

    def summarize_mode(h: int, mode_name: str, mask: pd.Series) -> Dict[str, Any]:
        # Defensive: ensure bb_z is present (avoid NaN silently mapping to '>=2')
        dfm = df.loc[mask & df["bb_z"].notna()].copy()
        ret_col = f"ret_{h}D"

        if dfm.empty:
            return {
                "definition": f"scheme=bb_z_5bucket_v1; horizon={h}D; mode={mode_name}",
                "n_total": 0,
                "by_bucket": [],
                "min_audit_by_bucket": [],
            }

        # bucket
        dfm["bucket_canonical"] = dfm["bb_z"].astype(float).map(lambda z: _bucket_from_z(float(z)))

        by_bucket: List[Dict[str, Any]] = []
        min_audit_by_bucket: List[Dict[str, Any]] = []

        for bk in ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]:
            part = dfm[dfm["bucket_canonical"] == bk]
            n = int(len(part))
            if n == 0:
                continue

            s = part[ret_col].astype(float)
            rec = {
                "bucket_canonical": bk,
                "n": n,
                "hit_rate": float((s > 0).mean()),
                "p90": _quantile(s, 0.90),
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

    def first_break_in_window(t: int, h: int) -> Optional[int]:
        # find min i in break_pos with t < i <= t+h
        if break_pos.size == 0:
            return None
        lo = t + 1
        hi = t + h
        idx = int(np.searchsorted(break_pos, lo, side="left"))
        if idx < len(break_pos) and int(break_pos[idx]) <= hi:
            return int(break_pos[idx])
        return None

    # build horizons
    raw_global_min: Optional[float] = None
    mins_collect: List[float] = []

    for h in horizons:
        ret_col = f"ret_{h}D"
        base_mask_h = lookback_mask & base_z & df[ret_col].notna()

        # raw (audit-only)
        raw_obj = summarize_mode(h, "raw", base_mask_h)

        # clean mask: exclude windows contaminated by breaks
        contam_arr = _contam_mask_from_breaks(len(df), break_pos, horizon=h)
        contam = pd.Series(contam_arr, index=df.index)

        clean_mask_h = base_mask_h & (~contam)
        clean_obj = summarize_mode(h, "clean", clean_mask_h)

        excluded_by_break_mask = int((base_mask_h & contam).sum())

        # excluded_entries_sample (first N)
        excluded_entries_sample: List[Dict[str, Any]] = []
        max_es = max(0, int(args.excluded_entries_sample_n))
        if max_es > 0 and excluded_by_break_mask > 0:
            idxs = df.index[(base_mask_h & contam)].tolist()[:max_es]
            for idx in idxs:
                row = df.loc[idx]
                tpos = int(row["t_pos"])
                bi = first_break_in_window(tpos, h)
                if bi is None or bi <= 0 or bi >= len(df):
                    continue
                br = df.iloc[bi]
                br_prev = df.iloc[bi - 1]
                ratio = float(br["price"]) / float(br_prev["price"]) if float(br_prev["price"]) != 0.0 else math.nan
                excluded_entries_sample.append(
                    {
                        "entry_index": int(tpos),
                        "entry_date": str(row["date"]),
                        "entry_price": float(row["price"]),
                        "first_break_index_in_window": int(bi),
                        "first_break_date_in_window": str(br["date"]),
                        "break_prev_date": str(br_prev["date"]),
                        "break_prev_price": float(br_prev["price"]),
                        "break_price": float(br["price"]),
                        "break_ratio": float(ratio) if np.isfinite(ratio) else None,
                    }
                )

        out["forward_return_conditional"]["horizons"][f"{h}D"] = {
            "raw": raw_obj,
            "clean": clean_obj,
            "excluded_by_break_mask": excluded_by_break_mask,
            "excluded_entries_sample": excluded_entries_sample,
        }

        if excluded_by_break_mask > 0:
            out["dq"]["notes"].append(f"horizon={h}D excluded_by_break_mask={excluded_by_break_mask}")

        # collect raw mins for contamination decision
        for row2 in raw_obj.get("by_bucket", []):
            mv = row2.get("min")
            if mv is not None:
                try:
                    mins_collect.append(float(mv))
                except Exception:
                    pass

    # DQ: warn raw contamination by global min threshold
    if mins_collect:
        try:
            raw_global_min = float(min(mins_collect))
        except Exception:
            raw_global_min = None

    raw_usable = True
    if raw_global_min is not None and raw_global_min <= float(args.raw_min_contam_threshold):
        raw_usable = False
        out["dq"]["flags"].append("RAW_MODE_HAS_SPLIT_OUTLIERS")
        out["dq"]["notes"].append(
            f"raw_global_min={raw_global_min:.6f} <= {float(args.raw_min_contam_threshold):.2f}; "
            "treat raw as contaminated (split/outlier). Use clean_only."
        )

    # finalize policy + decision_mode
    out["decision_mode"] = "clean_only"
    out["forward_return_conditional"]["policy"] = {
        "decision_mode": "clean_only",
        "raw_usable": bool(raw_usable),
        "raw_policy": "audit_only_do_not_use" if not raw_usable else "audit_ok_prefer_clean",
    }

    _write_json(out_path, out)
    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()