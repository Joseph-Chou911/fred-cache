#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_tw0050_forward_return_conditional.py

Minimal, audit-first forward return + hit-rate conditional stats by bb_z buckets.
- Reads cached prices (prefer cache_dir/price.csv) with adjclose.
- Computes BB(60,2) z-score, maps into 5 buckets (same scheme as forward_mdd_conditional).
- Computes forward_return for horizons (10D, 20D) and per-bucket:
    n, hit_rate, p50/p25/p10/p05/min, and min audit trail.
- Writes a single JSON: forward_return_conditional.json

Notes:
- This script does NOT modify existing stats_latest.json (keeps main pipeline stable).
- Includes basic break detection (ratio hi/lo) to offer clean mode (exclude windows crossing breaks).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


BUILD_SCRIPT_FINGERPRINT = "build_tw0050_forward_return_conditional@2026-02-21.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and x.strip().upper() in ("N/A", "NA", ""):
            return None
        return float(x)
    except Exception:
        return None


def _quantiles(s: pd.Series, qs: List[float]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    if s is None or len(s) == 0:
        for q in qs:
            out[f"p{int(q*100):02d}"] = None
        return out
    qv = s.quantile(qs, interpolation="linear")
    for q in qs:
        out[f"p{int(q*100):02d}"] = float(qv.loc[q])
    return out


def bucket_from_z(z: float) -> Tuple[str, str]:
    # raw_key, canonical
    if z <= -2.0:
        return "z_le_-2.0", "<=-2"
    if -2.0 < z <= -1.5:
        return "-2.0_to_-1.5", "(-2,-1.5]"
    if -1.5 < z < 1.5:
        return "-1.5_to_1.5", "(-1.5,1.5)"
    if 1.5 <= z < 2.0:
        return "1.5_to_2.0", "[1.5,2)"
    return "z_ge_2.0", ">=2"


CANON_ORDER = ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]


def load_prices(cache_dir: str, price_csv: str) -> Tuple[pd.DataFrame, List[str]]:
    dq: List[str] = []
    path = os.path.join(cache_dir, price_csv)
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing price csv: {path}")

    df = pd.read_csv(path)
    # Expect columns: date, close, adjclose, volume (your cache likely has these)
    # Try common variants.
    date_col = None
    for c in ("date", "Date", "datetime"):
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        raise ValueError("price csv missing date column (expected 'date' or 'Date')")

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)

    # normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    if "adjclose" not in df.columns and "adj_close" in df.columns:
        df = df.rename(columns={"adj_close": "adjclose"})
    if "close" not in df.columns:
        raise ValueError("price csv missing 'close' column")
    if "adjclose" not in df.columns:
        dq.append("ADJCLOSE_MISSING_FALLBACK_TO_CLOSE")
        df["adjclose"] = df["close"]

    df = df.rename(columns={date_col.lower(): "date"})
    df["adjclose"] = pd.to_numeric(df["adjclose"], errors="coerce")
    df = df.dropna(subset=["date", "adjclose"])
    return df[["date", "adjclose"]].copy(), dq


def compute_break_flags(price: pd.Series, hi: float, lo: float) -> pd.Series:
    # break at t if ratio price[t]/price[t-1] exceeds thresholds
    ratio = price / price.shift(1)
    flag = (ratio > hi) | (ratio < lo)
    flag = flag.fillna(False)
    return flag


def windows_contaminated_by_breaks(break_flag: pd.Series, horizon: int) -> pd.Series:
    # For entry t (index i), contaminated if any break occurs in (t, t+horizon]
    # breaks_in_window = csum[i+h] - csum[i] > 0
    csum = break_flag.astype(int).cumsum()
    csum_h = csum.shift(-horizon)
    w = (csum_h - csum) > 0
    w = w.fillna(True)  # tail without full horizon -> treat as contaminated (will be dropped anyway)
    return w


def build_forward_return_stats(
    df: pd.DataFrame,
    bb_window: int,
    bb_k: float,
    bb_ddof: int,
    horizons: List[int],
    break_hi: float,
    break_lo: float,
) -> Tuple[Dict[str, Any], List[str]]:
    dq: List[str] = []
    s = df["adjclose"].astype(float)
    dates = df["date"]

    ma = s.rolling(bb_window, min_periods=bb_window).mean()
    sd = s.rolling(bb_window, min_periods=bb_window).std(ddof=bb_ddof)
    z = (s - ma) / sd

    # bucket series
    raw_keys: List[str] = []
    canons: List[str] = []
    for v in z.tolist():
        if v is None or pd.isna(v):
            raw_keys.append("UNKNOWN")
            canons.append("UNKNOWN")
        else:
            rk, cn = bucket_from_z(float(v))
            raw_keys.append(rk)
            canons.append(cn)

    break_flag = compute_break_flags(s, hi=break_hi, lo=break_lo)

    out: Dict[str, Any] = {
        "schema": "hier",
        "scheme": "bb_z_5bucket_v1",
        "thresholds": {"extreme": 2.0, "near": 1.5},
        "bb_window": bb_window,
        "bb_k": bb_k,
        "bb_ddof": bb_ddof,
        "break_detection": {"break_ratio_hi": break_hi, "break_ratio_lo": break_lo},
        "horizons": {},
        "current": {},
    }

    # current (last valid z)
    last_valid_idx = z.last_valid_index()
    if last_valid_idx is None:
        dq.append("NO_VALID_BB_Z")
    else:
        cur_z = float(z.loc[last_valid_idx])
        rk, cn = bucket_from_z(cur_z)
        out["current"] = {
            "asof_date": dates.loc[last_valid_idx].date().isoformat(),
            "current_bb_z": cur_z,
            "current_bucket_key": rk,
            "current_bucket_canonical": cn,
        }

    qs = [0.50, 0.25, 0.10, 0.05]

    for h in horizons:
        fwd_ret = s.shift(-h) / s - 1.0
        contaminated = windows_contaminated_by_breaks(break_flag, horizon=h)

        base = pd.DataFrame(
            {
                "date": dates,
                "price": s,
                "bb_z": z,
                "bucket_key": raw_keys,
                "bucket_canonical": canons,
                "fwd_ret": fwd_ret,
            }
        )

        # valid rows: have z and have forward return
        base_valid = base.dropna(subset=["bb_z", "fwd_ret"]).copy()
        base_valid = base_valid[base_valid["bucket_canonical"] != "UNKNOWN"]

        # raw mode
        mode_raw = base_valid.copy()

        # clean mode: exclude windows impacted by breaks
        clean_mask = (~contaminated).loc[mode_raw.index]
        mode_clean = mode_raw[clean_mask].copy()

        def summarize(mode_df: pd.DataFrame, mode_name: str) -> Dict[str, Any]:
            block: Dict[str, Any] = {
                "definition": f"scheme=bb_z_5bucket_v1; horizon={h}D; mode={mode_name}",
                "n_total": int(len(mode_df)),
                "by_bucket": [],
                "min_audit_by_bucket": [],
            }
            for cn in CANON_ORDER:
                sub = mode_df[mode_df["bucket_canonical"] == cn]
                n = int(len(sub))
                if n == 0:
                    item = {
                        "bucket_canonical": cn,
                        "n": 0,
                        "hit_rate": None,
                        "p50": None,
                        "p25": None,
                        "p10": None,
                        "p05": None,
                        "min": None,
                    }
                    block["by_bucket"].append(item)
                    block["min_audit_by_bucket"].append(
                        {"bucket_canonical": cn, "n": 0, "min": None, "min_entry_date": None, "min_future_date": None}
                    )
                    continue

                ret = sub["fwd_ret"].astype(float)
                hit_rate = float((ret > 0).mean())

                qd = _quantiles(ret, qs)
                ret_min = float(ret.min())

                # min audit trail
                # find first idx of min
                idx_min = ret.idxmin()
                entry_date = mode_df.loc[idx_min, "date"]
                entry_price = float(mode_df.loc[idx_min, "price"])
                # future point at +h
                # idx_min is index into original df; future index is idx_min + h (since df is contiguous by row)
                fut_i = idx_min + h
                if fut_i < len(df):
                    future_date = df.loc[fut_i, "date"]
                    future_price = float(df.loc[fut_i, "adjclose"])
                else:
                    future_date = None
                    future_price = None

                item = {
                    "bucket_canonical": cn,
                    "n": n,
                    "hit_rate": hit_rate,
                    "p50": qd["p50"],
                    "p25": qd["p25"],
                    "p10": qd["p10"],
                    "p05": qd["p05"],
                    "min": ret_min,
                }
                block["by_bucket"].append(item)

                block["min_audit_by_bucket"].append(
                    {
                        "bucket_canonical": cn,
                        "n": n,
                        "min": ret_min,
                        "min_entry_date": entry_date.date().isoformat() if entry_date is not None else None,
                        "min_entry_price": entry_price,
                        "min_future_date": future_date.date().isoformat() if future_date is not None else None,
                        "min_future_price": future_price,
                    }
                )
            return block

        out["horizons"][f"{h}D"] = {
            "raw": summarize(mode_raw, "raw"),
            "clean": summarize(mode_clean, "clean"),
        }

    return out, dq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--price_csv", default="price.csv")
    ap.add_argument("--stats_json", default="stats_latest.json")
    ap.add_argument("--out_json", default="forward_return_conditional.json")
    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)
    ap.add_argument("--bb_ddof", type=int, default=0)  # set to 1 if your main script uses ddof=1
    ap.add_argument("--horizons", default="10,20")
    ap.add_argument("--break_ratio_hi", type=float, default=1.8)
    ap.add_argument("--break_ratio_lo", type=float, default=0.5555555556)
    ap.add_argument("--bb_z_eps", type=float, default=1e-3)  # tolerance for last bb_z check vs stats
    args = ap.parse_args()

    meta: Dict[str, Any] = {
        "generated_at_utc": utc_now_iso(),
        "build_script_fingerprint": BUILD_SCRIPT_FINGERPRINT,
        "cache_dir": args.cache_dir,
        "price_calc": "adjclose",
    }
    dq: List[str] = []

    df, dq0 = load_prices(args.cache_dir, args.price_csv)
    dq.extend(dq0)

    # Optional: read stats_latest.json for alignment check & params
    stats_path = os.path.join(args.cache_dir, args.stats_json)
    stats = None
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
            meta["stats_path"] = stats_path
            meta["stats_last_date"] = stats.get("last_date")
            # If present, override bb params to match main pipeline
            meta["bb_window_stats"] = stats.get("bb_window")
            meta["bb_k_stats"] = stats.get("bb_k")
        except Exception:
            dq.append("STATS_JSON_READ_FAILED")

    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]

    fr_block, dq_fr = build_forward_return_stats(
        df=df,
        bb_window=args.bb_window,
        bb_k=args.bb_k,
        bb_ddof=args.bb_ddof,
        horizons=horizons,
        break_hi=args.break_ratio_hi,
        break_lo=args.break_ratio_lo,
    )
    dq.extend(dq_fr)

    # Consistency check: last bb_z vs stats_latest (if available)
    if stats is not None:
        stats_bb_z = _safe_float(stats.get("bb_z"))
        cur_z = _safe_float(fr_block.get("current", {}).get("current_bb_z"))
        if stats_bb_z is not None and cur_z is not None:
            if abs(stats_bb_z - cur_z) > args.bb_z_eps:
                dq.append("BB_Z_MISMATCH_VS_STATS")
                meta["bb_z_stats"] = stats_bb_z
                meta["bb_z_computed"] = cur_z
                meta["bb_z_abs_diff"] = abs(stats_bb_z - cur_z)

    out = {
        "meta": meta,
        "dq": {"flags": dq, "notes": []},
        "forward_return_conditional": fr_block,
    }

    out_path = os.path.join(args.cache_dir, args.out_json)
    os.makedirs(args.cache_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote: {out_path}")
    if dq:
        print("[DQ]", ", ".join(dq))


if __name__ == "__main__":
    main()