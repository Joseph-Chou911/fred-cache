#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute stats_latest.json for sidecar caches in a schema compatible with scripts/render_dashboard.py.

Inputs per cache:
- <cache>/history.json : list rows {as_of_ts, series_id, data_date, value, source_url, notes}

Outputs per cache:
- <cache>/stats_latest.json

Windows:
- w60: z, p, z_delta, p_delta, ret1_pct
- w252: z, p

Definitions (deterministic):
- z-score: population std (ddof=0). If std==0 => z=0.
- percentile p: CDF(<=) * 100.  p = 100 * count(v_i <= latest) / n
- Window policy: last N valid numeric points (not calendar-aligned)

Notes:
- This guarantees schema compatibility for unified_dashboard to read without recalculation.
- If you need p252 numerically identical to market_cache, you must copy the percentile definition from the stats generator used by market_cache.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# IO
# -------------------------

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)

def now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# -------------------------
# Parse helpers
# -------------------------

def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() == "NA" or s == ".":
        return None
    try:
        return float(s)
    except Exception:
        return None

def is_ymd(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 10:
        return False
    return (s[4] == "-" and s[7] == "-")


# -------------------------
# Stats
# -------------------------

def mean(xs: List[float]) -> float:
    return sum(xs) / float(len(xs))

def pop_std(xs: List[float]) -> float:
    m = mean(xs)
    var = sum((x - m) ** 2 for x in xs) / float(len(xs))
    return math.sqrt(var)

def zscore(latest: float, window: List[float]) -> float:
    m = mean(window)
    sd = pop_std(window)
    if sd == 0.0:
        return 0.0
    return (latest - m) / sd

def percentile_cdf_leq(latest: float, window: List[float]) -> float:
    n = len(window)
    if n <= 0:
        return float("nan")
    le = sum(1 for v in window if v <= latest)
    return 100.0 * le / float(n)

def safe_num(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(x)

def compute_w_stats(vals: List[float], n: int) -> Tuple[Optional[float], Optional[float]]:
    if len(vals) < n:
        return None, None
    w = vals[-n:]
    latest = w[-1]
    z = zscore(latest, w)
    p = percentile_cdf_leq(latest, w)
    return safe_num(z), safe_num(p)

def compute_w60_with_deltas(vals: List[float]) -> Dict[str, Optional[float]]:
    if len(vals) < 60:
        return {"z": None, "p": None, "z_delta": None, "p_delta": None, "ret1_pct": None}

    z_t, p_t = compute_w_stats(vals, 60)

    # previous window ending at t-1
    if len(vals) >= 61:
        z_prev, p_prev = compute_w_stats(vals[:-1], 60)
    else:
        z_prev, p_prev = None, None

    z_delta = (z_t - z_prev) if (z_t is not None and z_prev is not None) else None
    p_delta = (p_t - p_prev) if (p_t is not None and p_prev is not None) else None

    # ret1%
    v_t = vals[-1]
    v_prev = vals[-2] if len(vals) >= 2 else None
    ret1_pct = (100.0 * (v_t / v_prev - 1.0)) if (v_prev is not None and v_prev != 0.0) else None

    return {
        "z": safe_num(z_t),
        "p": safe_num(p_t),
        "z_delta": safe_num(z_delta),
        "p_delta": safe_num(p_delta),
        "ret1_pct": safe_num(ret1_pct),
    }


# -------------------------
# Load / build
# -------------------------

def load_history_list(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    obj = read_json(path)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        return obj["items"]
    return []

def build_series_from_history(history: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    series_id -> rows sorted by data_date asc.
    row includes: data_date, value(float), as_of_ts, source_url
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in history:
        sid = (r.get("series_id") or "").strip()
        dd = (r.get("data_date") or "").strip()
        val = to_float(r.get("value"))
        if not sid or not dd or dd == "NA" or not is_ymd(dd) or val is None:
            continue
        out.setdefault(sid, []).append({
            "data_date": dd,
            "value": float(val),
            "as_of_ts": r.get("as_of_ts"),
            "source_url": r.get("source_url"),
        })
    for sid in list(out.keys()):
        out[sid].sort(key=lambda x: x["data_date"])
    return out

def make_stats_latest(cache_dir: str, tz: str, script_version: str) -> Dict[str, Any]:
    hist_path = os.path.join(cache_dir, "history.json")
    history = load_history_list(hist_path)
    series_rows = build_series_from_history(history)

    series_obj: Dict[str, Any] = {}

    # choose a global as_of_ts (max string) from last row of each series
    as_of_ts_max: Optional[str] = None
    for sid, rows in series_rows.items():
        if not rows:
            continue
        a = rows[-1].get("as_of_ts")
        if isinstance(a, str) and a:
            if as_of_ts_max is None or a > as_of_ts_max:
                as_of_ts_max = a

    for sid, rows in series_rows.items():
        if not rows:
            continue

        vals = [float(x["value"]) for x in rows]
        latest_row = rows[-1]

        latest = {
            "as_of_ts": latest_row.get("as_of_ts") or as_of_ts_max or "NA",
            "data_date": latest_row.get("data_date") or "NA",
            "value": latest_row.get("value"),
            "source_url": latest_row.get("source_url") or "NA",
            "notes": "NA",
        }

        w60 = compute_w60_with_deltas(vals)
        z252, p252 = compute_w_stats(vals, 252)
        w252 = {"z": z252, "p": p252}

        series_obj[sid] = {
            "latest": latest,
            "windows": {
                "w60": w60,
                "w252": w252,
            },
        }

    payload = {
        "schema_version": "stats_latest_v1",
        "generated_at_utc": now_utc_z(),
        "as_of_ts": as_of_ts_max or now_utc_z(),
        "script_version": script_version,
        "series_count": len(series_obj),
        "series": series_obj,

        # audit metadata
        "tz": tz,
        "window_policy": "last_N_valid_points",
        "percentile_method": "cdf_leq",
        "zscore_ddof": 0,
    }
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--script-version", default="cycle_sidecars_stats_v1")
    args = ap.parse_args()

    for cache_dir in ("inflation_realrate_cache", "asset_proxy_cache"):
        if not os.path.isdir(cache_dir):
            continue
        payload = make_stats_latest(cache_dir, args.tz, args.script_version)
        write_json(os.path.join(cache_dir, "stats_latest.json"), payload)
        print(f"[OK] wrote {cache_dir}/stats_latest.json (series_count={payload.get('series_count')})")


if __name__ == "__main__":
    main()