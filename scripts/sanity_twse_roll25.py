#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

CACHE_DIR = "roll25_cache"
ROLL_PATH = os.path.join(CACHE_DIR, "roll25.json")
STATS_PATH = os.path.join(CACHE_DIR, "stats_latest.json")

RECENT_WINDOW_N = 252
MIN_COVERAGE = 0.95


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None

def _fail(msg: str) -> None:
    print(f"[SANITY][FAIL] {msg}")
    sys.exit(1)

def _ok(msg: str) -> None:
    print(f"[SANITY][OK] {msg}")

def main() -> None:
    if not os.path.exists(ROLL_PATH):
        _fail(f"missing {ROLL_PATH}")
    if not os.path.exists(STATS_PATH):
        _fail(f"missing {STATS_PATH}")

    roll = _read_json(ROLL_PATH)
    stats = _read_json(STATS_PATH)

    if not isinstance(roll, list) or not roll:
        _fail("roll25.json is empty or not a list")

    used_date = str(stats.get("used_date") or "")
    if not used_date:
        _fail("stats_latest.json missing used_date")

    # filter <= used_date, sorted desc
    eligible: List[Dict[str, Any]] = []
    for r in roll:
        if not isinstance(r, dict):
            continue
        d = str(r.get("date") or "")
        if not d or d > used_date:
            continue
        eligible.append(r)

    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    recent = eligible[:RECENT_WINDOW_N]

    if len(recent) < int(RECENT_WINDOW_N * 0.6):
        _fail(f"insufficient recent rows: have {len(recent)} need >= {int(RECENT_WINDOW_N*0.6)}")

    close_ok = sum(1 for r in recent if _safe_float(r.get("close")) is not None)
    tv_ok = sum(1 for r in recent if _safe_float(r.get("trade_value")) is not None)

    close_cov = close_ok / len(recent)
    tv_cov = tv_ok / len(recent)

    print(f"[INFO] used_date={used_date}")
    print(f"[INFO] recent_window_n={len(recent)} MIN_COVERAGE={MIN_COVERAGE}")
    print(f"[INFO] close_coverage={close_ok}/{len(recent)}={close_cov:.3f} trade_value_coverage={tv_ok}/{len(recent)}={tv_cov:.3f}")

    if close_cov < MIN_COVERAGE:
        _fail("close coverage below threshold in recent window (likely parsing/backfill issue)")
    if tv_cov < MIN_COVERAGE:
        _fail("trade_value coverage below threshold in recent window (likely parsing/backfill issue)")

    _ok("sanity passed")


if __name__ == "__main__":
    main()