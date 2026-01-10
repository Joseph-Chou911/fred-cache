#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from collections import Counter

CAP = 400
LITE_CAP = 252

HISTORY_PATH = Path("cache/history.json")
LITE_PATH = Path("cache/history_lite.json")

def _load_list(p: Path):
    if not p.exists():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def _check(path: Path, cap: int, label: str) -> int:
    h = _load_list(path)
    print(f"{label}_records =", len(h))

    keys = []
    per_series = Counter()
    bad = 0

    for r in h:
        if not isinstance(r, dict):
            bad += 1
            continue
        sid = str(r.get("series_id", ""))
        dd  = str(r.get("data_date", ""))
        if (not sid) or (not dd) or dd == "NA":
            bad += 1
            continue
        keys.append((sid, dd))
        per_series[sid] += 1

    uniq = len(set(keys))
    print(f"{label}_dedupe_ok =", uniq == len(keys))
    print(f"{label}_bad_rows  =", bad)

    too_many = {sid: c for sid, c in per_series.items() if c > cap}
    print(f"{label}_cap_per_series =", cap)
    print(f"{label}_cap_ok =", len(too_many) == 0)
    if too_many:
        top = sorted(too_many.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"{label}_cap_violations_top10 =", top)

    if uniq != len(keys) or bad > 0 or len(too_many) > 0:
        print(f"{label}: Sanity check failed")
        return 1

    print(f"{label}: Sanity check passed")
    return 0

def main() -> int:
    rc1 = _check(HISTORY_PATH, CAP, "history")
    rc2 = _check(LITE_PATH, LITE_CAP, "history_lite")
    return 1 if (rc1 != 0 or rc2 != 0) else 0

if __name__ == "__main__":
    raise SystemExit(main())