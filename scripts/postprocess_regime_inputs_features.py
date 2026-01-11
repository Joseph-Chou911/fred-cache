#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
postprocess_regime_inputs_features.py

Goals (minimal-intrusive):
1) Read regime_inputs_cache/inputs_history_lite.json (list of points)
2) Read regime_inputs_cache/inputs_latest.json (optional; upsert into history)
3) Ensure history is normalized + dedup by (series_id, data_date), preserve order
4) Compute rolling features for windows: 60 & 252 (MA/dev_pct/z/p)
5) Write regime_inputs_cache/features_latest.json
6) Print per-series counts; optionally fail if history shrank vs previous snapshot
"""

import argparse
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

CACHE_DIR = "regime_inputs_cache"
HIST_PATH = os.path.join(CACHE_DIR, "inputs_history_lite.json")
LATEST_PATH = os.path.join(CACHE_DIR, "inputs_latest.json")
FEAT_PATH = os.path.join(CACHE_DIR, "features_latest.json")

WINDOWS = [60, 252]

_DATE_PATTERNS = [
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    (None,      re.compile(r"^\d{4}-\d{2}-\d{2}T")),  # ISO datetime
    ("%m/%d/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
]

def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def normalize_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    ss = str(s).strip()
    if ss == "" or ss.upper() == "NA":
        return None
    if "T" in ss and re.match(r"^\d{4}-\d{2}-\d{2}T", ss):
        return ss[:10]
    for fmt, pat in _DATE_PATTERNS:
        if pat.match(ss):
            if fmt is None:
                return ss[:10]
            try:
                return datetime.strptime(ss, fmt).date().strftime("%Y-%m-%d")
            except Exception:
                return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ss)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None

def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None

def load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

def normalize_points_list(obj) -> List[dict]:
    """
    Expect list[dict] with keys: series_id, data_date, value, source_url, as_of_ts, notes
    Keep only valid (series_id, data_date). value can be NA but will be ignored in stats.
    Dedup by (series_id, data_date) overwrite in-place (preserve order).
    """
    if not isinstance(obj, list):
        return []
    out: List[dict] = []
    idx: Dict[Tuple[str, str], int] = {}

    for r in obj:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id") or "").strip()
        dd = normalize_date(r.get("data_date"))
        if not sid or not dd:
            continue
        rr = dict(r)
        rr["series_id"] = sid
        rr["data_date"] = dd

        key = (sid, dd)
        if key in idx:
            out[idx[key]] = rr
        else:
            idx[key] = len(out)
            out.append(rr)
    return out

def upsert_latest_into_history(history: List[dict], latest: List[dict]) -> List[dict]:
    if not latest:
        return history
    # build index for quick overwrite (but preserve order)
    idx: Dict[Tuple[str, str], int] = {}
    for i, r in enumerate(history):
        sid = r.get("series_id")
        dd = r.get("data_date")
        if sid and dd:
            idx[(sid, dd)] = i

    for r in latest:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id") or "").strip()
        dd = normalize_date(r.get("data_date"))
        if not sid or not dd:
            continue
        rr = dict(r)
        rr["series_id"] = sid
        rr["data_date"] = dd
        key = (sid, dd)
        if key in idx:
            history[idx[key]] = rr
        else:
            history.append(rr)
            idx[key] = len(history) - 1
    return history

def build_series(history: List[dict]) -> Dict[str, List[Tuple[str, float]]]:
    """
    -> {series_id: sorted list of (date, value)}
    (sort is only for computation; we do not reorder history file here)
    """
    m: Dict[str, Dict[str, float]] = {}
    for r in history:
        sid = r.get("series_id")
        dd = r.get("data_date")
        v = safe_float(r.get("value"))
        if not sid or not dd or v is None:
            continue
        m.setdefault(sid, {})
        m[sid][dd] = v  # keep last per date
    out: Dict[str, List[Tuple[str, float]]] = {}
    for sid, dm in m.items():
        items = list(dm.items())
        items.sort(key=lambda x: x[0])
        out[sid] = items
    return out

def mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / float(len(xs))

def std_ddof0(xs: List[float]) -> Optional[float]:
    if len(xs) < 2:
        return 0.0 if len(xs) == 1 else None
    mu = mean(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / float(len(xs))
    return math.sqrt(var)

def percentile_le(xs: List[float], x: float) -> Optional[float]:
    if not xs:
        return None
    c = sum(1 for v in xs if v <= x)
    return c / float(len(xs)) * 100.0

def compute_features(series: Dict[str, List[Tuple[str, float]]]) -> Dict[str, dict]:
    """
    For each series:
      latest (date,value)
      for each window: n, ma, dev_pct, z, p
    """
    out: Dict[str, dict] = {}
    for sid, items in series.items():
        if not items:
            continue
        last_dd, last_v = items[-1]
        vals_all = [v for (_, v) in items]
        out[sid] = {
            "latest": {"data_date": last_dd, "value": last_v},
            "windows": {}
        }
        for w in WINDOWS:
            if len(vals_all) < w:
                out[sid]["windows"][f"w{w}"] = {"n": len(vals_all), "ma": None, "dev_pct": None, "z": None, "p": None}
                continue
            win = vals_all[-w:]
            ma = mean(win)
            sd = std_ddof0(win)
            dev_pct = None if (ma is None or ma == 0) else (last_v / ma - 1.0) * 100.0
            z = None
            if ma is not None and sd is not None and sd != 0:
                z = (last_v - ma) / sd
            p = percentile_le(win, last_v)
            out[sid]["windows"][f"w{w}"] = {"n": w, "ma": ma, "dev_pct": dev_pct, "z": z, "p": p}
    return out

def series_counts(history: List[dict]) -> Dict[str, int]:
    c: Dict[str, int] = {}
    for r in history:
        sid = r.get("series_id")
        v = safe_float(r.get("value"))
        dd = r.get("data_date")
        if not sid or not dd or v is None:
            continue
        c[sid] = c.get(sid, 0) + 1
    return c

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-window", type=int, default=252, help="warn threshold; MA252 needs >=252 valid points")
    ap.add_argument("--write-back-history", action="store_true", help="rewrite inputs_history_lite.json after normalize/upsert")
    ap.add_argument("--counts-in", default="", help="optional path to previous counts json for shrink check")
    ap.add_argument("--shrink-hard-fail", action="store_true", help="exit 2 if any series count shrinks vs counts-in")
    args = ap.parse_args()

    hist_raw = load_json(HIST_PATH)
    history = normalize_points_list(hist_raw)

    latest_raw = load_json(LATEST_PATH)
    latest = normalize_points_list(latest_raw) if isinstance(latest_raw, list) else []

    # upsert latest into history
    history = upsert_latest_into_history(history, latest)

    # recompute normalized again (dedup in-place)
    history = normalize_points_list(history)

    if args.write_back_history:
        write_json(HIST_PATH, history)

    counts = series_counts(history)

    # optional shrink check
    if args.counts_in:
        prev = load_json(args.counts_in)
        if isinstance(prev, dict):
            shrunk = []
            for sid, n0 in prev.items():
                n1 = counts.get(sid, 0)
                if n1 < int(n0):
                    shrunk.append((sid, int(n0), n1))
            if shrunk:
                print("SHRINK_DETECTED:")
                for sid, a, b in shrunk:
                    print(f"  {sid}: prev={a} now={b}")
                if args.shrink-hard-fail:
                    raise SystemExit(2)

    # compute features
    series = build_series(history)
    feats = compute_features(series)

    # dq summary (simple, auditable)
    warn_series = [sid for sid, n in counts.items() if n < args.min_window]
    dq = {
        "generated_at_utc": utc_iso(),
        "min_window_required": args.min_window,
        "series_counts": counts,
        "warn_series_lt_min_window": warn_series,
        "status": "OK" if len(warn_series) == 0 else "WARN",
    }

    out = {
        "generated_at_utc": utc_iso(),
        "windows": {"w60": 60, "w252": 252},
        "features_policy": {
            "std_ddof": 0,
            "percentile_method": "P = count(x<=latest)/n * 100 (within window)",
            "window_definition": "last N valid points (not calendar days)",
        },
        "series": feats,
        "dq": dq,
    }
    write_json(FEAT_PATH, out)

    # print counts summary
    print("== series valid-point counts ==")
    for sid in sorted(counts.keys()):
        print(f"{sid}: {counts[sid]}")
    print(f"== features_latest.json written: {FEAT_PATH} ==")
    print(f"== dq status: {dq['status']} (warn_series={len(warn_series)}) ==")

if __name__ == "__main__":
    main()