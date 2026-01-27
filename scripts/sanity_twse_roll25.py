#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os

CACHE_DIR = "roll25_cache"
REPORT_PATH = os.path.join(CACHE_DIR, "latest_report.json")
STATS_PATH = os.path.join(CACHE_DIR, "stats_latest.json")
ROLL_PATH = os.path.join(CACHE_DIR, "roll25.json")

def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def fail(msg: str) -> None:
    print(f"[SANITY][FAIL] {msg}")
    sys.exit(1)

def main() -> None:
    for p in (REPORT_PATH, STATS_PATH, ROLL_PATH):
        if not os.path.exists(p):
            fail(f"missing required file: {p}")

    report = _load(REPORT_PATH)
    stats = _load(STATS_PATH)
    roll = _load(ROLL_PATH)

    # Basic shape checks
    if not isinstance(roll, list):
        fail("roll25.json must be a JSON list")

    used_date_r = report.get("used_date") or report.get("numbers", {}).get("UsedDate")
    used_date_s = stats.get("used_date")
    if not used_date_r or not used_date_s or str(used_date_r) != str(used_date_s):
        fail(f"used_date mismatch: report={used_date_r} stats={used_date_s}")

    # Ensure trade_value is present
    tv = report.get("numbers", {}).get("TradeValue")
    if tv is None:
        fail("latest_report.numbers.TradeValue is null (FMTQIK parsing likely broken)")

    # CRITICAL: close series must exist; otherwise your z/p windows are meaningless
    close_total = stats.get("series", {}).get("close", {}).get("window_note", {}).get("n_total_available")
    if close_total in (None, 0):
        fail("stats_latest.series.close.window_note.n_total_available is 0 -> close series missing (backfill/parser broken)")

    # If run_day_tag says trading day, Close SHOULD NOT be null (even if DATA_NOT_UPDATED you still have latest close)
    run_day_tag = stats.get("run_day_tag")
    close_value = report.get("numbers", {}).get("Close")
    if run_day_tag in ("TRADING_DAY", "NON_TRADING_DAY") and close_value is None:
        fail(f"latest_report.numbers.Close is null while run_day_tag={run_day_tag} -> close mapping broken")

    # Dedupe: dates should be unique
    dates = [x.get("date") for x in roll if isinstance(x, dict) and x.get("date")]
    if len(dates) != len(set(dates)):
        fail("roll25.json contains duplicate dates (dedupe broken)")

    print("[SANITY][OK] TWSE sidecar outputs look consistent.")

if __name__ == "__main__":
    main()