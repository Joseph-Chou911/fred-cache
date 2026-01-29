#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List


def _read(path: str, default: Any):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    latest = _read("tw_pb_cache/latest.json", {})
    hist: List[Dict[str, Any]] = _read("tw_pb_cache/history.json", [])

    if "schema_version" not in latest:
        print("[FAIL] latest.json missing schema_version")
        sys.exit(1)

    dates = [r.get("data_date") for r in hist if r.get("data_date")]
    if dates != sorted(dates):
        print("[FAIL] history.json not sorted by data_date asc")
        sys.exit(1)

    if len(dates) != len(set(dates)):
        print("[FAIL] history.json has duplicate data_date")
        sys.exit(1)

    fs = latest.get("fetch_status")
    if fs == "OK":
        for k in ["pbr", "per", "dividend_yield_pct"]:
            v = latest.get(k)
            if not isinstance(v, (int, float)):
                print(f"[FAIL] latest.{k} not numeric under OK")
                sys.exit(1)

    print("[PASS] tw_sanity_pb_cache")


if __name__ == "__main__":
    main()