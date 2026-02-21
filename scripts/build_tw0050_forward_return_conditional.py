#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_tw0050_forward_return_conditional.py

Purpose (audit-first):
- Compute conditional forward returns (10D/20D) bucketed by BB z-score (BB(60,2) by default).
- Output an audit-friendly JSON artifact: tw0050_bb_cache/forward_return_conditional.json

Key updates in this version (per request):
1) Meta alignment from stats_latest.json:
   - meta.stats_last_date
   - meta.bb_window_stats
   - meta.bb_k_stats
   - meta.stats_build_fingerprint (if present)
   - meta.stats_generated_at_utc (if present)

2) Enforce decision to use CLEAN only:
   - top-level decision_mode = "clean_only"
   - dq.flags includes "RAW_MODE_HAS_SPLIT_OUTLIERS" when raw mode exhibits split-like outliers
     (e.g., extreme raw min <= -0.40)

Notes:
- "raw" is still computed and emitted for diagnostics/audit, but decision_mode states clean-only.
- "clean" excludes forward windows impacted by detected price breaks (ratio outside [lo, hi]).
  For a break at index b, clean excludes entry indices t in [b-N, b-1] (exactly N rows per break),
  matching your observed n_total differences (10/20).

CLI used by your workflow:
  python scripts/build_tw0050_forward_return_conditional.py \
    --cache_dir tw0050_bb_cache \
    --price_csv <csv> \
    --stats_json stats_latest.json \
    --out_json forward_return_conditional.json \
    --bb_window 60 \
    --bb_k 2.0 \
    --bb_ddof 0 \
    --horizons 10,20 \
    --break_ratio_hi 1.8 \
    --break_ratio_lo 0.5555555556
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BUILD_SCRIPT_FINGERPRINT = "build_tw0050_forward_return_conditional@2026-02-21.v2"


# -----------------------------
# Helpers (audit-first, NA-safe)
# -----------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def _get_path(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _pick(d: Dict[str, Any], candidates: List[List[str]]) -> Any:
    for p in candidates:
        v = _get_path(d, p)
        if v is not None:
            return v
    return None


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float, np.floating, np.integer)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.upper() == "N/A":
            return None
        return float(s)
    except Exception:
        return None


def _quantiles(arr: np.ndarray, qs: List[float]) -> Dict[str, Optional[float]]:
    if arr.size == 0:
        return {f"p{int(q*100):02d}": None for q in qs}
    out: Dict[str, Optional[float]] = {}
    for q in qs:
        out[f"p{int(q*100):02d}"] = float(np.quantile(arr, q))
    return out


def _bucket_from_z(z: float, extreme: float = 2.0, near: float = 1.5) -> Tuple[str, str]:
    """
    Returns (bucket_key, bucket_canonical) using scheme bb_z_5bucket_v1:
      <=-2, (-2,-1.5], (-1.5,1.5), [1.5,2), >=2
    """
    if z <= -extreme:
        return ("z_le_-2.0", "<=-2")
    if -extreme < z <= -near:
        return ("-2.0_to_-1.5", "(-2,-1.5]")
    if -near < z < near:
        return ("-1.5_to_1.5", "(-1.5,1.5)")
    if near <= z < extreme:
        return ("1.5_to_2.0", "[1.5,2)")
    return ("z_ge_2.0", ">=2")


BUCKET_ORDER_CANON = ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]


@dataclass
class BreakDetection:
    break_ratio_hi: float
    break_ratio_lo: float


def detect_break_indices(price: np.ndarray, bd: BreakDetection) -> List[int]:
    """
    Detect break indices b where ratio = price[b]/price[b-1] is outside [lo, hi].
    Returns list of indices b (0-based), b>=1.
    """
    breaks: List[int] = []
    for i in range(1, len(price)):
        p0 = price[i - 1]
        p1 = price[i]
        if not np.isfinite(p0) or not np.isfinite(p1) or p0 == 0:
            continue
        r = p1 / p0
        if r > bd.break_ratio_hi or r < bd.break_ratio_lo:
            breaks.append(i)
    return breaks


def clean_valid_mask(n: int, horizon: int, break_indices: List[int]) -> np.ndarray:
    """
    For each break at index b, exclude entry indices t in [b-horizon, b-1] (exactly horizon rows),
    so any forward window (t -> t+horizon) that crosses the break is excluded.
    """
    m = np.ones(n, dtype=bool)
    for b in break_indices:
        start = max(0, b - horizon)
        end = b  # exclude [start, b-1]
        m[start:end] = False
    return m


def load_price_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Date handling
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        # Try first column as date if it looks like date-like
        c0 = df.columns[0]
        df[c0] = pd.to_datetime(df[c0], errors="coerce")
        df = df.rename(columns={c0: "date"})
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Price column selection
    cols = {c.lower(): c for c in df.columns}
    if "adjclose" in cols:
        price_col = cols["adjclose"]
    elif "adj_close" in cols:
        price_col = cols["adj_close"]
    else:
        raise SystemExit(f"ERROR: price csv missing adjclose/adj_close columns: {list(df.columns)}")

    df["price"] = pd.to_numeric(df[price_col], errors="coerce")
    df = df.dropna(subset=["price"]).reset_index(drop=True)

    return df[["date", "price"]]


def compute_bb_z(df: pd.DataFrame, bb_window: int, bb_k: float, bb_ddof: int) -> pd.DataFrame:
    """
    Compute BB mean/std and z-score on level price:
      ma = rolling mean(window)
      sd = rolling std(window, ddof)
      z  = (price - ma) / sd
    """
    s = df["price"].astype(float)
    ma = s.rolling(bb_window, min_periods=bb_window).mean()
    sd = s.rolling(bb_window, min_periods=bb_window).std(ddof=bb_ddof)
    z = (s - ma) / sd.replace(0.0, np.nan)
    out = df.copy()
    out["bb_ma"] = ma
    out["bb_sd"] = sd
    out["bb_z"] = z
    return out


def summarize_mode(
    df: pd.DataFrame,
    horizon: int,
    mode_name: str,
    breaks: List[int],
    bd: BreakDetection,
    thresholds: Dict[str, float],
) -> Dict[str, Any]:
    """
    Create summary for one horizon and one mode (raw/clean).
    Output:
      definition, n_total, by_bucket[], min_audit_by_bucket[]
    """
    extreme = float(thresholds["extreme"])
    near = float(thresholds["near"])

    # forward return
    price = df["price"].to_numpy(dtype=float)
    fwd_price = np.roll(price, -horizon)
    fwd_price[-horizon:] = np.nan
    fwd_ret = (fwd_price / price) - 1.0

    z = df["bb_z"].to_numpy(dtype=float)
    dates = df["date"].dt.strftime("%Y-%m-%d").to_numpy()
    # base validity: have z and fwd_ret
    valid = np.isfinite(z) & np.isfinite(fwd_ret)

    if mode_name == "clean":
        m_clean = clean_valid_mask(len(df), horizon, breaks)
        valid = valid & m_clean

    # bucket assignment
    bucket_key = np.full(len(df), "", dtype=object)
    bucket_canon = np.full(len(df), "", dtype=object)
    for i in range(len(df)):
        if not np.isfinite(z[i]):
            continue
        k, c = _bucket_from_z(float(z[i]), extreme=extreme, near=near)
        bucket_key[i] = k
        bucket_canon[i] = c

    # aggregate by canonical bucket order
    by_bucket: List[Dict[str, Any]] = []
    min_audit: List[Dict[str, Any]] = []

    n_total = int(np.sum(valid))

    for canon in BUCKET_ORDER_CANON:
        m = valid & (bucket_canon == canon)
        vals = fwd_ret[m]
        n = int(vals.size)

        if n == 0:
            by_bucket.append(
                {
                    "bucket_canonical": canon,
                    "n": 0,
                    "hit_rate": None,
                    "p50": None,
                    "p25": None,
                    "p10": None,
                    "p05": None,
                    "min": None,
                }
            )
            min_audit.append(
                {
                    "bucket_canonical": canon,
                    "n": 0,
                    "min": None,
                    "min_entry_date": None,
                    "min_entry_price": None,
                    "min_future_date": None,
                    "min_future_price": None,
                }
            )
            continue

        hit_rate = float(np.mean(vals > 0.0))

        qs = _quantiles(vals, [0.50, 0.25, 0.10, 0.05])
        vmin = float(np.min(vals))

        # min audit trail
        idxs = np.where(m)[0]
        # find first idx achieving min (deterministic)
        min_idx = int(idxs[np.argmin(fwd_ret[idxs])])

        entry_date = str(dates[min_idx])
        entry_price = float(price[min_idx])
        future_idx = min_idx + horizon
        future_date = str(dates[future_idx])
        future_price = float(price[future_idx])

        by_bucket.append(
            {
                "bucket_canonical": canon,
                "n": n,
                "hit_rate": hit_rate,
                "p50": qs["p50"],
                "p25": qs["p25"],
                "p10": qs["p10"],
                "p05": qs["p05"],
                "min": vmin,
            }
        )
        min_audit.append(
            {
                "bucket_canonical": canon,
                "n": n,
                "min": vmin,
                "min_entry_date": entry_date,
                "min_entry_price": entry_price,
                "min_future_date": future_date,
                "min_future_price": future_price,
            }
        )

    return {
        "definition": f"scheme=bb_z_5bucket_v1; horizon={horizon}D; mode={mode_name}",
        "n_total": n_total,
        "by_bucket": by_bucket,
        "min_audit_by_bucket": min_audit,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--price_csv", required=True, help="filename inside cache_dir, e.g. price.csv")
    ap.add_argument("--stats_json", required=True, help="filename inside cache_dir, e.g. stats_latest.json")
    ap.add_argument("--out_json", required=True, help="filename inside cache_dir, e.g. forward_return_conditional.json")

    ap.add_argument("--bb_window", type=int, default=60)
    ap.add_argument("--bb_k", type=float, default=2.0)
    ap.add_argument("--bb_ddof", type=int, default=0)

    ap.add_argument("--horizons", default="10,20", help="comma-separated, e.g. 10,20")
    ap.add_argument("--break_ratio_hi", type=float, default=1.8)
    ap.add_argument("--break_ratio_lo", type=float, default=0.5555555556)

    args = ap.parse_args()

    cache_dir = args.cache_dir
    price_csv_path = os.path.join(cache_dir, args.price_csv)
    stats_path = os.path.join(cache_dir, args.stats_json)
    out_path = os.path.join(cache_dir, args.out_json)

    # ---- Load inputs ----
    if not os.path.isfile(price_csv_path):
        raise SystemExit(f"ERROR: price csv not found: {price_csv_path}")
    if not os.path.isfile(stats_path):
        raise SystemExit(f"ERROR: stats json not found: {stats_path}")

    stats = _read_json(stats_path)
    df_price = load_price_csv(price_csv_path)

    # ---- Meta alignment from stats_latest.json ----
    stats_last_date = _pick(stats, [["last_date"], ["meta", "last_date"], ["stats", "last_date"]])
    bb_window_stats = _pick(stats, [["bb_window"], ["meta", "bb_window"], ["params", "bb_window"], ["bb", "window"]])
    bb_k_stats = _pick(stats, [["bb_k"], ["meta", "bb_k"], ["params", "bb_k"], ["bb", "k"]])

    stats_build_fingerprint = _pick(
        stats,
        [["build_script_fingerprint"], ["meta", "build_script_fingerprint"], ["stats", "build_script_fingerprint"]],
    )
    stats_generated_at_utc = _pick(
        stats,
        [["generated_at_utc"], ["meta", "generated_at_utc"], ["stats", "generated_at_utc"], ["report_generated_at_utc"]],
    )

    # If stats_last_date is missing, fall back to price last date (but mark dq)
    dq_flags: List[str] = []
    dq_notes: List[str] = []

    price_last_date = df_price["date"].iloc[-1].strftime("%Y-%m-%d")

    if stats_last_date is None:
        dq_flags.append("STATS_META_MISSING_LAST_DATE")
        dq_notes.append("stats_last_date not found in stats_latest.json; fell back to price_last_date for asof_date.")
        asof_date = price_last_date
    else:
        asof_date = str(stats_last_date)

    # Align bb_window_stats/bb_k_stats if missing (do NOT guess; just record missing)
    if bb_window_stats is None:
        dq_flags.append("STATS_META_MISSING_BB_WINDOW")
        dq_notes.append("bb_window_stats not found in stats_latest.json (meta alignment incomplete).")
    if bb_k_stats is None:
        dq_flags.append("STATS_META_MISSING_BB_K")
        dq_notes.append("bb_k_stats not found in stats_latest.json (meta alignment incomplete).")

    # ---- Compute BB z & breaks ----
    df_bb = compute_bb_z(df_price, bb_window=int(args.bb_window), bb_k=float(args.bb_k), bb_ddof=int(args.bb_ddof))
    price_arr = df_bb["price"].to_numpy(dtype=float)

    bd = BreakDetection(break_ratio_hi=float(args.break_ratio_hi), break_ratio_lo=float(args.break_ratio_lo))
    breaks = detect_break_indices(price_arr, bd)

    # ---- Compute horizons ----
    horizons = []
    for part in str(args.horizons).split(","):
        part = part.strip()
        if not part:
            continue
        horizons.append(int(part))
    horizons = sorted(set(horizons))
    if not horizons:
        raise SystemExit("ERROR: --horizons is empty after parsing")

    thresholds = {"extreme": 2.0, "near": 1.5}

    horizons_out: Dict[str, Any] = {}
    raw_global_min: Optional[float] = None

    for h in horizons:
        raw = summarize_mode(df_bb, h, "raw", breaks, bd, thresholds)
        clean = summarize_mode(df_bb, h, "clean", breaks, bd, thresholds)

        # Track raw global min for split/outlier detection
        for b in raw.get("by_bucket", []):
            v = _to_float(b.get("min"))
            if v is None:
                continue
            raw_global_min = v if raw_global_min is None else min(raw_global_min, v)

        horizons_out[f"{h}D"] = {"raw": raw, "clean": clean}

    # ---- Current snapshot (based on last available bb_z) ----
    df_valid_z = df_bb.dropna(subset=["bb_z"])
    if len(df_valid_z) == 0:
        raise SystemExit("ERROR: bb_z is all NA; cannot compute current bucket (check bb_window vs data length).")

    last_row = df_valid_z.iloc[-1]
    current_bb_z = float(last_row["bb_z"])
    current_bucket_key, current_bucket_canon = _bucket_from_z(current_bb_z, extreme=thresholds["extreme"], near=thresholds["near"])

    # ---- Enforce decision_mode clean-only + dq flag for raw outliers ----
    # Heuristic: raw min <= -0.40 indicates split-like contamination (your raw showed ~ -0.75).
    if raw_global_min is not None and raw_global_min <= -0.40:
        dq_flags.append("RAW_MODE_HAS_SPLIT_OUTLIERS")
        dq_notes.append(f"raw_global_min={raw_global_min:.6f} <= -0.40; treat raw as contaminated (split/outlier). Use clean_only.")

    out: Dict[str, Any] = {
        "decision_mode": "clean_only",
        "meta": {
            "generated_at_utc": utc_now_iso(),
            "build_script_fingerprint": BUILD_SCRIPT_FINGERPRINT,
            "cache_dir": cache_dir,
            "price_calc": "adjclose",
            "stats_path": stats_path,
            "stats_last_date": stats_last_date,
            "bb_window_stats": bb_window_stats,
            "bb_k_stats": bb_k_stats,
            "stats_build_fingerprint": stats_build_fingerprint,
            "stats_generated_at_utc": stats_generated_at_utc,
            "price_last_date": price_last_date,
        },
        "dq": {"flags": dq_flags, "notes": dq_notes},
        "forward_return_conditional": {
            "schema": "hier",
            "scheme": "bb_z_5bucket_v1",
            "thresholds": thresholds,
            "bb_window": int(args.bb_window),
            "bb_k": float(args.bb_k),
            "bb_ddof": int(args.bb_ddof),
            "break_detection": {
                "break_ratio_hi": bd.break_ratio_hi,
                "break_ratio_lo": bd.break_ratio_lo,
                "break_count": int(len(breaks)),
            },
            "horizons": horizons_out,
            "current": {
                "asof_date": asof_date,
                "current_bb_z": current_bb_z,
                "current_bucket_key": current_bucket_key,
                "current_bucket_canonical": current_bucket_canon,
            },
        },
    }

    _write_json(out_path, out)


if __name__ == "__main__":
    main()