#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sanity check for TWSE sidecar (roll25_cache/)

Hard FAIL criteria (audit-first):
1) roll25.json / latest_report.json / stats_latest.json must exist
2) used_date must exist in roll25.json
3) used_date.close must NOT be null
4) If stats says mode=FULL or ohlc_status=OK => used_date.high & used_date.low must NOT be null
5) Recent-window coverage must be high enough (default: 252 window, >=95% for close & trade_value)
6) freshness_ok must be true by default (can be downgraded to WARN with ALLOW_STALE=1)

Soft WARN only:
- Older history gaps (e.g. year 2024 missing close/high/low) are allowed as long as recent window is OK.

Environment variables:
- WINDOW_N (default 252)
- MIN_COVERAGE (default 0.95)
- ALLOW_STALE (default "0") => if "1", freshness_ok=false becomes WARN not FAIL
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

CACHE_DIR = "roll25_cache"
ROLL_PATH = os.path.join(CACHE_DIR, "roll25.json")
REPORT_PATH = os.path.join(CACHE_DIR, "latest_report.json")
STATS_PATH = os.path.join(CACHE_DIR, "stats_latest.json")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    if s in ("", "NA", "na", "null", "-", "—", "None"):
        return None
    try:
        return float(s)
    except Exception:
        return None

def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return float(v)
    except Exception:
        return default

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip() in ("1", "true", "TRUE", "yes", "YES")

def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)

def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")

def _ok(msg: str) -> None:
    print(f"[OK] {msg}")

def _find_row(roll: List[Dict[str, Any]], used_date: str) -> Optional[Dict[str, Any]]:
    for r in roll:
        if isinstance(r, dict) and str(r.get("date")) == used_date:
            return r
    return None

def _recent_window(roll: List[Dict[str, Any]], used_date: str, n: int) -> List[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) <= used_date]
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[:n]

def _coverage(rows: List[Dict[str, Any]], key: str) -> Tuple[int, int, float]:
    total = len(rows)
    have = 0
    for r in rows:
        if _safe_float(r.get(key)) is not None:
            have += 1
    cov = (have / total) if total > 0 else 0.0
    return have, total, cov

def main() -> None:
    window_n = _env_int("WINDOW_N", 252)
    min_cov = _env_float("MIN_COVERAGE", 0.95)
    allow_stale = _env_bool("ALLOW_STALE", False)

    for p in (ROLL_PATH, REPORT_PATH, STATS_PATH):
        if not os.path.exists(p):
            _fail(f"missing required file: {p}")

    roll = _read_json(ROLL_PATH)
    report = _read_json(REPORT_PATH)
    stats = _read_json(STATS_PATH)

    if not isinstance(roll, list):
        _fail("roll25.json must be a JSON list")

    used_date = stats.get("used_date") or report.get("used_date") or (report.get("numbers", {}) or {}).get("UsedDate")
    if not used_date or not isinstance(used_date, str):
        _fail("cannot determine used_date from stats/report")

    row = _find_row(roll, used_date)
    if row is None:
        _fail(f"used_date={used_date} not found in roll25.json")

    used_close = _safe_float(row.get("close"))
    if used_close is None:
        _fail(f"used_date={used_date} close is null (used_date must be usable)")

    mode = str(stats.get("mode") or "")
    ohlc_status = str(stats.get("ohlc_status") or "")
    if (mode == "FULL") or (ohlc_status == "OK"):
        if _safe_float(row.get("high")) is None or _safe_float(row.get("low")) is None:
            _fail(f"stats says FULL/OK but used_date={used_date} high/low is null")

    freshness_ok = stats.get("freshness_ok")
    if freshness_ok is False and not allow_stale:
        _fail("freshness_ok=false (set ALLOW_STALE=1 to downgrade to WARN)")
    if freshness_ok is False and allow_stale:
        _warn("freshness_ok=false but ALLOW_STALE=1 => downgraded to WARN")

    recent = _recent_window(roll, used_date, window_n)
    if len(recent) < window_n:
        _warn(f"recent window length {len(recent)} < WINDOW_N={window_n}; coverage still checked on available rows")

    have_c, total_c, cov_c = _coverage(recent, "close")
    have_tv, total_tv, cov_tv = _coverage(recent, "trade_value")

    print(f"[INFO] used_date={used_date} mode={mode} ohlc_status={ohlc_status}")
    print(f"[INFO] recent_window_n={len(recent)} MIN_COVERAGE={min_cov}")
    print(f"[INFO] close_coverage={have_c}/{total_c}={cov_c:.3f} trade_value_coverage={have_tv}/{total_tv}={cov_tv:.3f}")

    if total_c > 0 and cov_c < min_cov:
        _fail(f"close coverage {cov_c:.3f} < {min_cov} in recent window")
    if total_tv > 0 and cov_tv < min_cov:
        _fail(f"trade_value coverage {cov_tv:.3f} < {min_cov} in recent window")

    # Optional: global (all-time) missing summary (WARN only)
    have_all_c, total_all_c, cov_all_c = _coverage([r for r in roll if isinstance(r, dict)], "close")
    have_all_tv, total_all_tv, cov_all_tv = _coverage([r for r in roll if isinstance(r, dict)], "trade_value")
    if cov_all_c < 0.90:
        _warn(f"global close coverage is low (older history has gaps): {have_all_c}/{total_all_c}={cov_all_c:.3f}")
    if cov_all_tv < 0.90:
        _warn(f"global trade_value coverage is low (older history has gaps): {have_all_tv}/{total_all_tv}={cov_all_tv:.3f}")

    _ok("sanity passed")


if __name__ == "__main__":
    main()