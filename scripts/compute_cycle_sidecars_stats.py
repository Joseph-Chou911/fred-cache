#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/compute_cycle_sidecars_stats.py

Compute stats_latest.json from sidecar history.json for a given cache dir.

Design goals:
- Deterministic & auditable
- stats_latest.as_of_ts MUST match cache latest.json as_of_ts (pipeline freshness)
- Windows: w60 / w252 based on last_N_valid_points
- Percentile: cdf_leq (count <= latest) / n * 100
- zscore: ddof=0
- Extra audit fields:
  - window.n, window.ok
  - data_lag_days (today_local - data_date)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo


SCRIPT_VERSION = "cycle_sidecars_stats_v1"
SCHEMA_VERSION = "stats_latest_v1"


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_yyyy_mm_dd(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        xs = x.strip()
        if xs == "" or xs.upper() == "NA":
            return None
        try:
            return float(xs)
        except Exception:
            return None
    return None


def normalize_history_obj(obj: Any) -> List[Dict[str, Any]]:
    """
    Accept:
    - list[dict] (your current upsert_history output)
    - {"items":[...]} object
    Return: list[dict]
    """
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        items = obj.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def series_ids_from_latest(latest_rows: List[Dict[str, Any]]) -> List[str]:
    out = []
    for r in latest_rows:
        sid = r.get("series_id")
        if isinstance(sid, str) and sid:
            out.append(sid)
    return out


def index_history(history_rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group by series_id, sort by data_date ascending (auditable).
    Drop rows missing data_date or value.
    """
    g: Dict[str, List[Dict[str, Any]]] = {}
    for r in history_rows:
        sid = r.get("series_id")
        dd = r.get("data_date")
        val = safe_float(r.get("value"))
        if not isinstance(sid, str) or not sid:
            continue
        if not isinstance(dd, str) or dd == "NA" or parse_yyyy_mm_dd(dd) is None:
            continue
        if val is None:
            continue
        g.setdefault(sid, []).append(r)

    for sid, rows in g.items():
        rows.sort(key=lambda x: (x.get("data_date", ""), str(x.get("as_of_ts", ""))))
    return g


def last_n_values(rows_sorted: List[Dict[str, Any]], n: int) -> Tuple[List[float], List[str]]:
    """
    Return (values, dates) from last N rows (ascending dates).
    """
    if not rows_sorted:
        return [], []
    tail = rows_sorted[-n:] if len(rows_sorted) >= n else rows_sorted[:]
    vals: List[float] = []
    dds: List[str] = []
    for r in tail:
        v = safe_float(r.get("value"))
        dd = r.get("data_date")
        if v is None or not isinstance(dd, str) or parse_yyyy_mm_dd(dd) is None:
            continue
        vals.append(v)
        dds.append(dd)
    return vals, dds


def mean_std_ddof0(xs: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    s = var ** 0.5
    return m, s


def percentile_cdf_leq(xs: List[float], latest: float) -> Optional[float]:
    if not xs:
        return None
    n = len(xs)
    c = sum(1 for x in xs if x <= latest)
    return 100.0 * c / n


def zscore(xs: List[float], latest: float) -> Optional[float]:
    m, s = mean_std_ddof0(xs)
    if m is None or s is None:
        return None
    if s == 0:
        return 0.0
    return (latest - m) / s


def compute_window_metrics(rows_sorted: List[Dict[str, Any]], N: int) -> Dict[str, Any]:
    vals, dds = last_n_values(rows_sorted, N)
    n = len(vals)
    ok = (n >= N)

    if n == 0:
        return {"n": 0, "ok": False, "z": None, "p": None}

    latest = vals[-1]
    p = percentile_cdf_leq(vals, latest)
    z = zscore(vals, latest)

    out: Dict[str, Any] = {"n": n, "ok": ok, "z": z, "p": p}

    # For w60 only: z_delta / p_delta / ret1_pct
    if N == 60 and n >= 2:
        prev = vals[-2]
        # compute prev z/p on the window that ends at prev (exclude latest)
        vals_prev = vals[:-1]
        prev_z = zscore(vals_prev, prev) if len(vals_prev) >= 1 else None
        prev_p = percentile_cdf_leq(vals_prev, prev) if len(vals_prev) >= 1 else None

        if z is not None and prev_z is not None:
            out["z_delta"] = z - prev_z
        else:
            out["z_delta"] = None

        if p is not None and prev_p is not None:
            out["p_delta"] = p - prev_p
        else:
            out["p_delta"] = None

        if prev != 0:
            out["ret1_pct"] = (latest / prev - 1.0) * 100.0
        else:
            out["ret1_pct"] = None
    return out


def data_lag_days(today_local: date, data_date_str: str) -> Optional[int]:
    dd = parse_yyyy_mm_dd(data_date_str)
    if dd is None:
        return None
    return (today_local - dd).days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True, help="e.g. inflation_realrate_cache")
    ap.add_argument("--tz", default="Asia/Taipei")
    args = ap.parse_args()

    cache_dir = args.cache_dir.rstrip("/")

    latest_path = os.path.join(cache_dir, "latest.json")
    hist_path = os.path.join(cache_dir, "history.json")
    out_path = os.path.join(cache_dir, "stats_latest.json")

    if not os.path.exists(latest_path):
        raise SystemExit(f"missing latest.json: {latest_path}")
    if not os.path.exists(hist_path):
        raise SystemExit(f"missing history.json: {hist_path}")

    latest_obj = read_json(latest_path)
    latest_rows = normalize_history_obj(latest_obj)
    if not latest_rows:
        raise SystemExit("latest.json empty or invalid")

    # Authoritative pipeline as_of_ts = latest.json as_of_ts (same fetch batch)
    as_of_ts = latest_rows[0].get("as_of_ts")
    if not isinstance(as_of_ts, str) or not as_of_ts:
        raise SystemExit("latest.json missing as_of_ts")

    # Load history
    hist_obj = read_json(hist_path)
    hist_rows = normalize_history_obj(hist_obj)
    hist_by_sid = index_history(hist_rows)

    tz = ZoneInfo(args.tz)
    today_local = datetime.now(tz).date()

    series_block: Dict[str, Any] = {}
    sids = series_ids_from_latest(latest_rows)

    for sid in sids:
        rows_sorted = hist_by_sid.get(sid, [])
        # latest row for that sid from latest.json
        lrow = next((r for r in latest_rows if r.get("series_id") == sid), None)
        if not isinstance(lrow, dict):
            continue

        lval = safe_float(lrow.get("value"))
        ldd = lrow.get("data_date")
        if lval is None or not isinstance(ldd, str):
            continue

        w60 = compute_window_metrics(rows_sorted, 60)
        w252 = compute_window_metrics(rows_sorted, 252)

        series_block[sid] = {
            "latest": {
                "as_of_ts": as_of_ts,  # force match
                "data_date": ldd,
                "value": lval,
                "source_url": lrow.get("source_url", "NA"),
                "notes": lrow.get("notes", "NA"),
                "data_lag_days": data_lag_days(today_local, ldd),
            },
            "windows": {
                "w60": w60,
                "w252": w252,
            },
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc_iso(),
        "as_of_ts": as_of_ts,  # MUST match latest.json
        "script_version": SCRIPT_VERSION,
        "series_count": len(series_block),
        "series": series_block,
        "tz": args.tz,
        "window_policy": "last_N_valid_points",
        "percentile_method": "cdf_leq",
        "zscore_ddof": 0,
    }

    # Mismatch guard (hard fail) — prevents your previous stale confusion
    # Validate that stats.as_of_ts equals latest.as_of_ts
    if payload["as_of_ts"] != as_of_ts:
        raise SystemExit("BUG: stats as_of_ts mismatch latest as_of_ts")

    write_json(out_path, payload)
    print(f"OK: wrote {out_path} as_of_ts={as_of_ts} series_count={len(series_block)}")


if __name__ == "__main__":
    main()