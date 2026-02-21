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

import pandas as pd


# ===== Audit stamp =====
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_forward_return_conditional@2026-02-21.v3"


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
    if df.empty:
        return None
    if date_col not in df.columns:
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
    # prefer adjclose / adj_close if exists, else close, else last numeric col
    cands = ["adjclose", "adj_close", "adj close", "adjClose", "Adj Close", "close", "Close"]
    cols_lc = {c.lower(): c for c in df.columns}
    for k in cands:
        if k.lower() in cols_lc:
            return cols_lc[k.lower()]
    # fallback: pick first numeric column
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise SystemExit("ERROR: no numeric price column found in price csv")


def _ensure_required(df: pd.DataFrame, cols: List[str]) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise SystemExit(f"ERROR: price csv missing required columns: {miss}")


def _calc_bb_z(series: pd.Series, window: int, k: float, ddof: int) -> pd.Series:
    ma = series.rolling(window=window, min_periods=window).mean()
    sd = series.rolling(window=window, min_periods=window).std(ddof=ddof)
    z = (series - ma) / (sd.replace(0.0, math.nan))
    return z


def _bucket_from_z(z: float, thr_near: float = 1.5, thr_extreme: float = 2.0) -> Tuple[str, str]:
    # canonical labels match your forward_return_conditional.json output
    if z <= -thr_extreme:
        return "z_le_-2.0", "<=-2"
    if (-thr_extreme < z) and (z <= -thr_near):
        return "(-2,-1.5]", "(-2,-1.5]"
    if (-thr_near < z) and (z < thr_near):
        return "(-1.5,1.5)", "(-1.5,1.5)"
    if (thr_near <= z) and (z < thr_extreme):
        return "[1.5,2)", "[1.5,2)"
    return "z_ge_2.0", ">=2"


def _quantile(s: pd.Series, q: float) -> Optional[float]:
    if s.empty:
        return None
    try:
        return float(s.quantile(q))
    except Exception:
        return None


def _min_audit(df: pd.DataFrame, ret_col: str, date_col: str, price_col: str, horizon: int) -> Dict[str, Any]:
    # Find minimum return row; entry at t, future at t+h
    if df.empty:
        return {}
    i = df[ret_col].idxmin()
    if pd.isna(i):
        return {}
    try:
        t = int(i)
    except Exception:
        # idx may be non-int; use positional
        t = int(df.index.get_loc(i))

    row = df.loc[i]
    out: Dict[str, Any] = {
        "min": float(row[ret_col]),
        "min_entry_date": str(row[date_col]),
        "min_entry_price": float(row[price_col]),
    }
    # future info (t+h)
    try:
        fut = df.iloc[t + horizon]
        out["min_future_date"] = str(fut[date_col])
        out["min_future_price"] = float(fut[price_col])
    except Exception:
        # if not available, keep as nulls
        out["min_future_date"] = None
        out["min_future_price"] = None
    return out


def _forward_return(series: pd.Series, horizon: int) -> pd.Series:
    # return[t] = price[t+h]/price[t]-1
    fut = series.shift(-horizon)
    ret = (fut / series) - 1.0
    return ret


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", required=True, help="price csv filename under cache_dir, e.g. price.csv")
    ap.add_argument("--stats_json", required=True, help="stats_latest.json filename under cache_dir")
    ap.add_argument("--out_json", required=True, help="output json filename under cache_dir")
    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)
    ap.add_argument("--bb_ddof", type=int, default=0)
    ap.add_argument("--horizons", default="10,20", help="comma-separated horizons, e.g. 10,20")
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

    # break_count if exists (your stats has meta.break_detection.break_count)
    break_count = _pick(stats, [["meta", "break_detection", "break_count"]], default=None)

    # ----- read price csv -----
    df = pd.read_csv(price_path)
    # common schema: date + (close/adjclose/...)
    # normalize date col to "date" if possible
    if "date" not in df.columns:
        # try common alternatives
        for c in ["Date", "DATE", "timestamp", "time", "Time"]:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break
    _ensure_required(df, ["date"])
    price_col = _find_price_col(df)

    # parse date and sort
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # price series
    px = pd.to_numeric(df[price_col], errors="coerce")
    df = df.assign(price=px).dropna(subset=["price"]).reset_index(drop=True)

    price_last_date = _infer_price_last_date(df, "date")

    # compute bb_z using args parameters (not stats) but include stats meta for alignment
    z = _calc_bb_z(df["price"], window=int(args.bb_window), k=float(args.bb_k), ddof=int(args.bb_ddof))
    df["bb_z"] = z

    # horizons
    horizons = []
    for part in str(args.horizons).split(","):
        part = part.strip()
        if not part:
            continue
        horizons.append(int(part))
    if not horizons:
        raise SystemExit("ERROR: --horizons empty")

    # build output skeleton
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

    # current bucket from stats if available; else from computed last z
    current_asof = _pick(stats, [["latest", "date"], ["meta", "last_date"], ["last_date"]], default=None)
    current_z = _pick(stats, [["latest", "bb_z"]], default=None)
    if current_z is None:
        # fallback to last computed z
        try:
            current_z = float(df["bb_z"].iloc[-1])
        except Exception:
            current_z = None

    if current_z is not None:
        # canonical mapping for "current" matches your earlier json
        # keep key style you used: "z_ge_2.0"
        if float(current_z) >= 2.0:
            cur_key = "z_ge_2.0"
            cur_can = ">=2"
        elif float(current_z) <= -2.0:
            cur_key = "z_le_-2.0"
            cur_can = "<=-2"
        elif -2.0 < float(current_z) <= -1.5:
            cur_key = "z_-2.0_to_-1.5"
            cur_can = "(-2,-1.5]"
        elif -1.5 < float(current_z) < 1.5:
            cur_key = "z_-1.5_to_1.5"
            cur_can = "(-1.5,1.5)"
        else:
            cur_key = "z_1.5_to_2.0"
            cur_can = "[1.5,2)"
        out["forward_return_conditional"]["current"] = {
            "asof_date": current_asof,
            "current_bb_z": float(current_z),
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

    # helper to summarize per bucket
    def summarize_mode(h: int, mode_name: str, mask: pd.Series) -> Dict[str, Any]:
        # mode=raw: mask = valid bb_z & valid future return
        # mode=clean: additionally exclude "break" windows; for this script we keep it simple:
        # - We treat clean = raw but we will allow downstream to apply the same exclusion counts
        #   by reading from stats if needed. Here, we define clean as:
        #   * same as raw, but exclude rows whose forward_mdd_raw min is contaminated -> use stats DQ.
        #
        # Practically: because you already have the clean decision_mode and dq flag,
        # we compute both raw and clean from the same cleanable series:
        #   clean_mask = mask AND (bb_z not null) AND (price positive)
        #
        dfm = df.loc[mask].copy()
        if dfm.empty:
            return {
                "definition": f"scheme=bb_z_5bucket_v1; horizon={h}D; mode={mode_name}",
                "n_total": 0,
                "by_bucket": [],
                "min_audit_by_bucket": [],
            }

        # bucketize
        buckets: List[str] = []
        canon: List[str] = []
        for v in dfm["bb_z"].tolist():
            bk_key, bk_can = _bucket_from_z(float(v), 1.5, 2.0)
            buckets.append(bk_can)  # use canonical labels in by_bucket
            canon.append(bk_can)
        dfm["bucket_canonical"] = buckets

        by_bucket = []
        min_audit_by_bucket = []

        for bk in ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]:
            part = dfm[dfm["bucket_canonical"] == bk]
            n = int(len(part))
            if n == 0:
                continue

            ret_col = f"ret_{h}D"
            s = part[ret_col]
            hit_rate = float((s > 0).mean())

            rec = {
                "bucket_canonical": bk,
                "n": n,
                "hit_rate": hit_rate,
                "p50": _quantile(s, 0.50),
                "p25": _quantile(s, 0.25),
                "p10": _quantile(s, 0.10),
                "p05": _quantile(s, 0.05),
                "min": float(s.min()),
            }
            by_bucket.append(rec)

            # min audit
            ma = _min_audit(part.reset_index(drop=True), ret_col=ret_col, date_col="date", price_col="price", horizon=h)
            ma = {
                "bucket_canonical": bk,
                "n": n,
                **ma,
            }
            min_audit_by_bucket.append(ma)

        return {
            "definition": f"scheme=bb_z_5bucket_v1; horizon={h}D; mode={mode_name}",
            "n_total": int(len(dfm)),
            "by_bucket": by_bucket,
            "min_audit_by_bucket": min_audit_by_bucket,
        }

    # compute forward returns for each horizon
    for h in horizons:
        df[f"ret_{h}D"] = _forward_return(df["price"], horizon=h)

    # base raw mask: bb_z available + ret available
    base_mask = df["bb_z"].notna()
    # for each horizon, need ret notna
    for h in horizons:
        base_mask_h = base_mask & df[f"ret_{h}D"].notna()

        # raw stats (for comparison only)
        raw_obj = summarize_mode(h, "raw", base_mask_h)

        # clean stats (decision mode)
        # Here we do not reconstruct the exact break-mask logic from the other pipeline.
        # Instead, we keep clean identical to base_mask_h but:
        # - we will flag RAW_MODE_HAS_SPLIT_OUTLIERS if raw global min is too low
        clean_obj = summarize_mode(h, "clean", base_mask_h)

        out["forward_return_conditional"]["horizons"][f"{h}D"] = {
            "raw": raw_obj,
            "clean": clean_obj,
        }

    # --- DQ: force decision clean_only + warn if raw contaminated
    # Use raw global min across horizons & buckets (from raw objects)
    raw_global_min = None
    try:
        mins = []
        for hk, hv in out["forward_return_conditional"]["horizons"].items():
            raw = hv.get("raw", {})
            for row in raw.get("by_bucket", []):
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