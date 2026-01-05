#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from collections import Counter
from typing import Any, Dict, List

ROLL25_PATH = "roll25_cache/roll25.json"
CAP_LIMIT = 25

def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def main() -> None:
    print("Sanity check (twse roll25 coverage)\n")

    roll = _read_json(ROLL25_PATH, default=[])
    if not isinstance(roll, list):
        roll = []

    dates: List[str] = []
    for r in roll:
        if isinstance(r, dict) and "date" in r:
            dates.append(str(r["date"]))

    # roll is stored newest -> oldest, but we don't assume; compute
    unique_dates = sorted(set(dates), reverse=True)
    rows_per_day = dict(Counter(dates))
    dedupe_ok = (len(dates) == len(set(dates)))

    roll_records = len(roll)
    cap_ok = (roll_records <= CAP_LIMIT)

    date_range = "NA"
    if unique_dates:
        date_range = f"{unique_dates[0]} .. {unique_dates[-1]}"

    print(f"roll_records = {roll_records}")
    print(f"date_range   = {date_range}")
    print(f"days_in_roll = {unique_dates}")
    print(f"rows_per_day = {rows_per_day}")
    print(f"dedupe_ok    = {dedupe_ok}")
    print(f"cap_limit    = {CAP_LIMIT}  cap_ok = {cap_ok}")

if __name__ == "__main__":
    main()