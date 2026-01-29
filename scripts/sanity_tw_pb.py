#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
scripts/sanity_tw_pb.py

Sanity checks for tw_pb_cache outputs.
- history rows sorted
- date format valid
- latest aligns to last row
- if pbr exists, must be > 0 (basic)
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime


DIR = "tw_pb_cache"


def load(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def die(msg: str):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def main():
    h = load(os.path.join(DIR, "history.json"))
    l = load(os.path.join(DIR, "latest.json"))

    rows = h.get("rows")
    if not isinstance(rows, list):
        die("history.rows missing or not list")

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    prev = None
    for r in rows:
        if not isinstance(r, dict) or "date" not in r:
            die("row invalid")
        ds = r["date"]
        if not isinstance(ds, str) or not date_re.match(ds):
            die(f"bad date format: {ds}")
        # validate date parse
        datetime.strptime(ds, "%Y-%m-%d")

        if prev and ds < prev:
            die("rows not sorted ascending by date")
        prev = ds

        pbr = r.get("pbr")
        if pbr is not None:
            try:
                v = float(pbr)
                if v <= 0:
                    die(f"pbr <= 0 at {ds}: {v}")
            except Exception:
                die(f"pbr not numeric at {ds}: {pbr}")

    latest = l.get("latest")
    if rows:
        if latest != rows[-1]:
            die("latest.json latest != last history row")

    print("[OK] sanity_tw_pb passed")


if __name__ == "__main__":
    main()