#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from collections import Counter

CAP = 400
TARGET_VALID = 252

HISTORY = Path("cache/history.json")
LITE = Path("cache/history_lite.json")
STATS = Path("cache/stats_latest.json")

# If you want strict series list, keep it in sync with fred_cache.py
SERIES_IDS = [
    "STLFSI4","VIXCLS","BAMLH0A0HYM2","DGS2","DGS10","DTWEXBGS","DCOILWTICO",
    "SP500","NASDAQCOM","DJIA","NFCINONFINLEVERAGE","T10Y2Y","T10Y3M",
]

def is_ymd(s: str) -> bool:
    return isinstance(s, str) and len(s) == 10 and s[4] == "-" and s[7] == "-"

def load_list(p: Path):
    if not p.exists():
        return []
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise SystemExit(f"{p} is not a JSON list")
    return [x for x in obj if isinstance(x, dict)]

def main() -> int:
    # 1) must have stats_latest.json
    if not STATS.exists():
        print("Sanity check failed: stats_latest.json missing")
        return 1
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    if not isinstance(stats, dict) or "series" not in stats or not isinstance(stats["series"], dict):
        print("Sanity check failed: stats_latest.json invalid structure")
        return 1

    # 2) history.json basic integrity
    h = load_list(HISTORY)
    keys = []
    per_series = Counter()
    bad = 0

    for r in h:
        sid = str(r.get("series_id", "")).strip()
        dd  = str(r.get("data_date", "")).strip()
        if (not sid) or (not dd) or dd == "NA" or (not is_ymd(dd)):
            bad += 1
            continue
        keys.append((sid, dd))
        per_series[sid] += 1

    uniq = len(set(keys))
    dedupe_ok = (uniq == len(keys))
    too_many = {sid: c for sid, c in per_series.items() if c > CAP}

    print("history_records =", len(h))
    print("dedupe_ok =", dedupe_ok)
    print("bad_rows  =", bad)
    print("cap_per_series =", CAP)
    print("cap_ok =", len(too_many) == 0)
    if too_many:
        top = sorted(too_many.items(), key=lambda x: x[1], reverse=True)[:10]
        print("cap_violations_top10 =", top)

    if (not dedupe_ok) or bad > 0 or len(too_many) > 0:
        print("Sanity check failed (history.json)")
        return 1

    # 3) history_lite.json: ensure per-series has enough valid points for 252-window stats
    lite = load_list(LITE)
    seen = set()
    valid_cnt = Counter()
    for r in lite:
        sid = str(r.get("series_id", "")).strip()
        dd  = str(r.get("data_date", "")).strip()
        vv  = str(r.get("value", "NA")).strip()
        if not sid or dd == "NA" or not is_ymd(dd) or vv in {"NA", ".", ""}:
            continue
        k = (sid, dd)
        if k in seen:
            continue
        seen.add(k)
        valid_cnt[sid] += 1

    missing_series = [sid for sid in SERIES_IDS if sid not in stats["series"]]
    if missing_series:
        print("Sanity check failed: stats_latest missing series:", missing_series)
        return 1

    insufficient = {sid: valid_cnt.get(sid, 0) for sid in SERIES_IDS if valid_cnt.get(sid, 0) < TARGET_VALID}
    print("lite_valid_target =", TARGET_VALID)
    print("lite_valid_counts =", {sid: valid_cnt.get(sid, 0) for sid in SERIES_IDS})
    if insufficient:
        print("Sanity check failed: history_lite insufficient valid points:", insufficient)
        return 1

    print("Sanity check passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())