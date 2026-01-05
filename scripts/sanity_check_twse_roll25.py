#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from collections import Counter
from typing import Any, Dict, List

ROLL25_PATH = os.path.join("cache", "roll25.json")
CAP = 25

def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def main() -> None:
    roll = _read_json(ROLL25_PATH, default=[])
    if not isinstance(roll, list):
        roll = []

    # Collect dates
    dates = []
    for r in roll:
        if isinstance(r, dict) and "date" in r:
            dates.append(str(r["date"]))

    # Count duplicates
    c = Counter(dates)
    dedupe_ok = all(v == 1 for v in c.values())

    # rows_per_day (for TWSE roll25 should be 1 per date)
    rows_per_day: Dict[str, int] = dict(sorted(c.items()))

    # days list (sorted)
    days_in_roll = sorted(rows_per_day.keys())

    cap_ok = len(roll) <= CAP

    print("Sanity check (twse roll25 coverage)")
    print("")
    print(f"roll_records   = {len(roll)}")
    print(f"days_in_roll   = {days_in_roll}")
    print(f"rows_per_day   = {rows_per_day}")
    print(f"dedupe_ok      = {dedupe_ok}")
    print(f"cap_records    = {CAP} cap_ok = {cap_ok}")

if __name__ == "__main__":
    main()