#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sanity check for TWSE sidecar outputs (NO NETWORK, NO WRITES).

Checks:
  - roll25_cache/roll25.json exists, is list, date unique, non-empty
  - roll25_cache/latest_report.json exists, contains required keys, used_date matches roll max(date)
  - roll25_cache/stats_latest.json exists, contains required series keys
  - Basic invariants: mode/ohlc_status consistent with OhlcMissing, freshness fields present
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

CACHE_DIR = "roll25_cache"
ROLL_PATH = os.path.join(CACHE_DIR, "roll25.json")
REPORT_PATH = os.path.join(CACHE_DIR, "latest_report.json")
STATS_PATH = os.path.join(CACHE_DIR, "stats_latest.json")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _fail(msg: str, code: int = 1) -> None:
    print(f"[SANITY][FAIL] {msg}")
    sys.exit(code)

def _warn(msg: str) -> None:
    print(f"[SANITY][WARN] {msg}")

def _ok(msg: str) -> None:
    print(f"[SANITY][OK] {msg}")

def _is_iso_date(s: str) -> bool:
    try:
        datetime.fromisoformat(s).date()
        return True
    except Exception:
        return False

def main() -> None:
    for p in (ROLL_PATH, REPORT_PATH, STATS_PATH):
        if not os.path.exists(p):
            _fail(f"missing required file: {p}")

    roll = _read_json(ROLL_PATH)
    if not isinstance(roll, list):
        _fail("roll25.json must be a JSON list")
    if len(roll) == 0:
        _fail("roll25.json is empty")

    dates: List[str] = []
    for i, r in enumerate(roll):
        if not isinstance(r, dict):
            _fail(f"roll25.json item[{i}] must be an object")
        d = str(r.get("date", ""))
        if not d:
            _fail(f"roll25.json item[{i}] missing date")
        if not _is_iso_date(d):
            _fail(f"roll25.json item[{i}] date not ISO yyyy-mm-dd: {d}")
        dates.append(d)

    if len(dates) != len(set(dates)):
        _fail("roll25.json has duplicate dates (dedupe failed)")

    max_date = max(dates)
    _ok(f"roll25.json ok: n={len(roll)} max_date={max_date} unique_dates=OK")

    report = _read_json(REPORT_PATH)
    if not isinstance(report, dict):
        _fail("latest_report.json must be an object")

    for k in ("used_date", "mode", "ohlc_status", "freshness_ok", "run_day_tag", "used_date_status", "signal", "numbers"):
        if k not in report:
            _fail(f"latest_report.json missing key: {k}")

    used_date = str(report.get("used_date"))
    if used_date != max_date:
        _fail(f"latest_report.used_date({used_date}) != roll.max_date({max_date})")

    mode = str(report.get("mode"))
    ohlc_status = str(report.get("ohlc_status"))
    sig = report.get("signal", {})
    ohlc_missing = None
    if isinstance(sig, dict):
        ohlc_missing = sig.get("OhlcMissing")

    if mode == "FULL" and ohlc_status != "OK":
        _fail("mode=FULL but ohlc_status!=OK")
    if mode == "MISSING_OHLC" and ohlc_status != "MISSING":
        _fail("mode=MISSING_OHLC but ohlc_status!=MISSING")

    if ohlc_missing is not None:
        if bool(ohlc_missing) and mode != "MISSING_OHLC":
            _fail("signal.OhlcMissing=true but mode!=MISSING_OHLC")
        if (not bool(ohlc_missing)) and mode != "FULL":
            _warn("signal.OhlcMissing=false but mode!=FULL (check data integrity)")

    _ok(f"latest_report.json ok: used_date={used_date} mode={mode} ohlc_status={ohlc_status}")

    stats = _read_json(STATS_PATH)
    if not isinstance(stats, dict):
        _fail("stats_latest.json must be an object")

    if stats.get("used_date") != used_date:
        _fail(f"stats_latest.used_date({stats.get('used_date')}) != report.used_date({used_date})")

    series = stats.get("series")
    if not isinstance(series, dict):
        _fail("stats_latest.json missing series object")

    for s in ("close", "trade_value", "pct_change", "amplitude_pct"):
        if s not in series:
            _fail(f"stats_latest.series missing: {s}")
        for w in ("win60", "win252"):
            if w not in series[s]:
                _fail(f"stats_latest.series.{s} missing: {w}")

    _ok("stats_latest.json ok: required series/wins present")

    print("[SANITY] PASS")

if __name__ == "__main__":
    main()