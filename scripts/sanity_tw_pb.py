#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    base = "tw_pb_cache"
    latest_p = os.path.join(base, "latest.json")
    hist_p = os.path.join(base, "history.json")
    stats_p = os.path.join(base, "stats_latest.json")

    for p in (latest_p, hist_p, stats_p):
        if not os.path.exists(p):
            fail(f"missing required file: {p}")

    latest: Dict[str, Any] = read_json(latest_p)
    hist: Any = read_json(hist_p)
    stats: Dict[str, Any] = read_json(stats_p)

    if latest.get("schema_version") != "tw_pb_latest_v1":
        fail("latest.schema_version mismatch")
    if stats.get("schema_version") != "tw_pb_stats_latest_v1":
        fail("stats.schema_version mismatch")
    if not isinstance(hist, list):
        fail("history must be a list")

    # If fetch_status OK => must have data_date + pbr
    if latest.get("fetch_status") == "OK":
        if not latest.get("data_date"):
            fail("latest OK but data_date is missing")
        if latest.get("pbr") is None:
            fail("latest OK but pbr is None")

    # Check history date sort
    dates = [r.get("date") for r in hist if isinstance(r, dict)]
    dates2 = [d for d in dates if isinstance(d, str)]
    if dates2 != sorted(dates2):
        fail("history is not sorted by date ascending")

    # If latest has data_date and pbr, ensure history contains that date
    ld = latest.get("data_date")
    if isinstance(ld, str) and latest.get("pbr") is not None:
        if all(r.get("date") != ld for r in hist if isinstance(r, dict)):
            fail("latest data_date not found in history")

    # stats series len should match count of numeric pbr in history (or be <=, but not >)
    pbr_count = 0
    for r in hist:
        if isinstance(r, dict) and isinstance(r.get("pbr"), (int, float)):
            pbr_count += 1
    if isinstance(stats.get("series_len_pbr"), int):
        if stats["series_len_pbr"] != pbr_count:
            fail(f"stats.series_len_pbr ({stats['series_len_pbr']}) != numeric pbr count in history ({pbr_count})")

    print("[PASS] tw_pb_cache sanity OK")


if __name__ == "__main__":
    main()