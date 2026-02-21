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
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_forward_return_conditional@2026-02-21.v6"


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


def _mean(s: pd.Series) -> Optional[float]:
    if s.empty:
        return None
    try:
        return float(s.mean())
    except Exception:
        return None


def _std(s: pd.Series) -> Optional[float]:
    if s.empty:
        return None
    try:
        return float(s.std(ddof=0))
    except Exception:
        return None


def _expected_shortfall(s: pd.Series, q: float) -> Optional[float]:
    """
    ES_q: mean of returns <= quantile(q). For left-tail risk summary.
    Example: q=0.05 => average of worst 5%.
    """
    if s.empty:
        return None
    try:
        thr = s.quantile(q)
        tail = s[s <= thr]
        if tail.empty:
            return None
        return float(tail.mean())
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


def _break_samples(df_all: pd.DataFrame, break_pos: np.ndarray, max_items: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if break_pos.size == 0:
        return out
    px = df_all["price"].astype(float)
    for i in break_pos[:max_items]:
        if i <= 0 or i >= len(df_all):
            continue
        prev = float(px.iloc[i - 1])
        cur = float(px.iloc[i])
        ratio = (cur / prev) if prev != 0.0 else math.nan
        out.append(
            {
                "break_index": int(i),
                "break_date": str(df_all["date"].iloc[i]),
                "prev_date": str(df_all["date"].iloc[i - 1]),
                "prev_price": prev,
                "price": cur,
                "ratio": float(ratio) if np.isfinite(ratio) else None,
            }
        )
        if len(out) >= max_items:
            break
    return out


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


def _excluded_entries_sample(
    df_all: pd.DataFrame,
    break_pos: np.ndarray,
    base_mask: pd.Series,
    contam: np.ndarray,
    horizon: int,
    max_items: int = 5,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if len(df_all) == 0:
        return out

    contam_s = pd.Series(contam, index=df_all.index)
    excluded_idx = np.where((base_mask & contam_s).values)[0]
    if excluded_idx.size == 0:
        return out

    px = df_all["price"].astype(float)
    for t in excluded_idx[:max_items]:
        t = int(t)
        item: Dict[str, Any] = {
            "entry_index": t,
            "entry_date": str(df_all["date"].iloc[t]),
            "entry_price": float(px.iloc[t]),
        }
        cand = break_pos[(break_pos > t) & (break_pos <= t + int(horizon))]
        if cand.size > 0:
            i = int(cand[0])
            prev = float(px.iloc[i - 1]) if i - 1 >= 0 else math.nan
            cur = float(px.iloc[i])
            ratio = (cur / prev) if (np.isfinite(prev) and prev != 0.0) else math.nan
            item.update(
                {
                    "first_break_index_in_window": i,
                    "first_break_date_in_window": str(df_all["date"].iloc[i]),
                    "break_prev_date": str(df_all["date"].iloc[i - 1]) if i - 1 >= 0 else None,
                    "break_prev_price": float(prev) if np.isfinite(prev) else None,
                    "break_price": cur,
                    "break_ratio": float(ratio) if np.isfinite(ratio) else None,
                }
            )
        else:
            item.update(
                {
                    "first_break_index_in_window": None,
                    "first_break_date_in_window": None,
                }
            )
        out.append(item)

    return out


def _min_audit_global(part: pd.DataFrame, df_all: pd.DataFrame, ret_col: str, horizon: int) -> Dict[str, Any]:
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
    ap.add_argument("--break_samples_max", type=int, default=5)
    ap.add_argument("--excluded_samples_max", type=int, default=5)
    ap.add_argument("--emit_extra_moments", action="store_true")
    ap.add_argument("--enable_self_check", action="store_true")
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

    # break detection
    break_pos = _detect_break_positions(df["price"], hi=float(args.break_ratio_hi), lo=float(args.break_ratio_lo))
    break_count_detected = int(break_pos.size)

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
            "rows_price_csv": int(len(df)),
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
                "raw_usable": False,  # will be updated after contamination check
                "raw_policy": "audit_only_do_not_use",  # will be updated after contamination check
            },
            "break_detection": {
                "break_ratio_hi": float(args.break_ratio_hi),
                "break_ratio_lo": float(args.break_ratio_lo),
                "break_count_stats": break_count_stats,
                "break_count_detected": break_count_detected,
                "break_samples": _break_samples(df, break_pos, max_items=int(args.break_samples_max)),
            },
            "horizons": {},
            "current": {},
            "self_check": {"enabled": bool(args.enable_self_check), "by_horizon": {}},
        },
    }

    # Cross-check break_count vs stats
    if break_count_stats is not None:
        try:
            bc_stats_i = int(break_count_stats)
            if bc_stats_i != break_count_detected:
                out["dq"]["flags"].append("BREAK_COUNT_MISMATCH_STATS_VS_DETECTED")
                out["dq"]["notes"].append(
                    f"break_count mismatch: stats={bc_stats_i} vs detected={break_count_detected}; "
                    "forward_return uses detected breaks from price_csv series."
                )
        except Exception:
            out["dq"]["flags"].append("BREAK_COUNT_STATS_NONINT")
            out["dq"]["notes"].append(f"break_count_stats non-int: {break_count_stats!r}")

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

        dfm = dfm[dfm["bb_z"].notna()].copy()
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
            rec: Dict[str, Any] = {
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

            if bool(args.emit_extra_moments):
                rec["mean"] = _mean(s)
                rec["std"] = _std(s)
                rec["es05"] = _expected_shortfall(s, 0.05)

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

    raw_mins_all: List[float] = []

    for h in horizons:
        ret_col = f"ret_{h}D"
        base_mask_h = base_z & df[ret_col].notna()

        raw_obj = summarize_mode(h, "raw", base_mask_h)

        contam = _contam_mask_from_breaks(len(df), break_pos, horizon=h)
        contam_s = pd.Series(contam, index=df.index)
        clean_mask_h = base_mask_h & (~contam_s)

        clean_obj = summarize_mode(h, "clean", clean_mask_h)

        excluded_cnt = int((base_mask_h & contam_s).sum())
        if excluded_cnt > 0:
            out["dq"]["notes"].append(f"horizon={h}D excluded_by_break_mask={excluded_cnt}")

        out["forward_return_conditional"]["horizons"][f"{h}D"] = {
            "raw": raw_obj,
            "clean": clean_obj,
            "excluded_by_break_mask": excluded_cnt,
            "excluded_entries_sample": _excluded_entries_sample(
                df_all=df,
                break_pos=break_pos,
                base_mask=base_mask_h,
                contam=contam,
                horizon=h,
                max_items=int(args.excluded_samples_max),
            ),
        }

        try:
            for row in raw_obj.get("by_bucket", []):
                if row.get("min") is not None:
                    raw_mins_all.append(float(row["min"]))
        except Exception:
            pass

        # ===== Self-check (audit-grade) =====
        if bool(args.enable_self_check):
            # Expected base eligible count is computed from masks (NOT from a formula), to stay robust.
            base_eligible_n = int(base_mask_h.sum())
            clean_n = int(clean_obj.get("n_total", 0))
            excluded_n = int(excluded_cnt)
            # Invariant: clean_n + excluded_n should equal base_eligible_n
            diff = int((clean_n + excluded_n) - base_eligible_n)

            chk: Dict[str, Any] = {
                "horizon": int(h),
                "base_eligible_n": base_eligible_n,
                "clean_n_total": clean_n,
                "excluded_by_break_mask": excluded_n,
                "identity_lhs_clean_plus_excluded": int(clean_n + excluded_n),
                "identity_rhs_base_eligible": base_eligible_n,
                "identity_diff": diff,
                "status": "OK" if diff == 0 else "FAIL",
                "notes": [],
            }

            if diff != 0:
                out["dq"]["flags"].append("SELF_CHECK_COUNT_IDENTITY_FAIL")
                chk["notes"].append(
                    "Expected clean_n_total + excluded_by_break_mask == base_eligible_n, but mismatch detected. "
                    "Potential causes: index misalignment, mask dtype coercion, or accidental row drops."
                )

            # Extra sanity: raw_n_total should match base_eligible_n exactly
            raw_n = int(raw_obj.get("n_total", 0))
            raw_diff = int(raw_n - base_eligible_n)
            chk["raw_n_total"] = raw_n
            chk["raw_minus_base_eligible"] = raw_diff
            if raw_diff != 0:
                out["dq"]["flags"].append("SELF_CHECK_RAW_N_MISMATCH_BASE")
                chk["notes"].append(
                    "raw_n_total != base_eligible_n. Potential causes: bb_z coercion dropping rows, "
                    "or summarize_mode filtering differs from base mask assumptions."
                )

            out["forward_return_conditional"]["self_check"]["by_horizon"][f"{h}D"] = chk

    # DQ: warn raw contamination by global min threshold
    raw_global_min: Optional[float] = None
    if raw_mins_all:
        raw_global_min = float(min(raw_mins_all))

    raw_usable = True
    raw_policy = "ok_to_use"
    if raw_global_min is not None and raw_global_min <= float(args.raw_min_contam_threshold):
        out["dq"]["flags"].append("RAW_MODE_HAS_SPLIT_OUTLIERS")
        out["dq"]["notes"].append(
            f"raw_global_min={raw_global_min:.6f} <= {float(args.raw_min_contam_threshold):.2f}; "
            "treat raw as contaminated (split/outlier). Use clean_only."
        )
        raw_usable = False
        raw_policy = "audit_only_do_not_use"
    else:
        raw_usable = True
        raw_policy = "audit_ok_but_decision_prefers_clean"

    out["forward_return_conditional"]["policy"]["raw_usable"] = bool(raw_usable)
    out["forward_return_conditional"]["policy"]["raw_policy"] = str(raw_policy)

    _write_json(out_path, out)
    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()