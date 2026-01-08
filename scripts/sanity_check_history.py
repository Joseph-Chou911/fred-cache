#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from collections import Counter

CAP = 400
HISTORY_PATH = Path("cache/history.json")

def main() -> int:
    h = json.loads(HISTORY_PATH.read_text(encoding="utf-8")) if HISTORY_PATH.exists() else []
    print("history_records =", len(h))

    keys = []
    per_series = Counter()
    bad = 0

    for r in h:
        sid = str(r.get("series_id", ""))
        dd  = str(r.get("data_date", ""))
        if (not sid) or (not dd) or dd == "NA":
            bad += 1
            continue
        keys.append((sid, dd))
        per_series[sid] += 1

    uniq = len(set(keys))
    print("dedupe_ok =", uniq == len(keys))
    print("bad_rows  =", bad)

    too_many = {sid: c for sid, c in per_series.items() if c > CAP}
    print("cap_per_series =", CAP)
    print("cap_ok =", len(too_many) == 0)
    if too_many:
        top = sorted(too_many.items(), key=lambda x: x[1], reverse=True)[:10]
        print("cap_violations_top10 =", top)

    if uniq != len(keys) or bad > 0 or len(too_many) > 0:
        print("Sanity check failed")
        return 1

    print("Sanity check passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())