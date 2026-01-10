#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sanity_check_history.py (upgraded, audit-friendly, non-blocking by default)

What it checks:
1) history.json exists & is a JSON list
2) dedupe on (series_id, data_date) (strict)
3) cap_per_series <= CAP (strict)
4) per-series valid-count vs TARGET_VALID (informational by default)
   - "valid" means: data_date is YYYY-MM-DD and value not in {"NA", ".", ""}

Exit code policy (IMPORTANT):
- By default: only fails on structural issues (bad JSON, duplicates, bad rows, cap violations)
- It does NOT fail just because a series has < TARGET_VALID (because some series may be weekly/monthly or missing).
- If you want to fail when under-target, set env: SANITY_FAIL_ON_UNDER_TARGET=1

Recommended env knobs:
- SANITY_CAP=400 (default 400)
- SANITY_TARGET_VALID=252 (default 252)
- SANITY_FAIL_ON_UNDER_TARGET=0/1 (default 0)
- SANITY_VERBOSE=1 (default 1)
"""

import json
import os
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Tuple


HISTORY_PATH = Path("cache/history.json")


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name, "") or "").strip()
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "y", "on"}


def _is_ymd(s: str) -> bool:
    return isinstance(s, str) and len(s) == 10 and s[4] == "-" and s[7] == "-"


def _is_valid_value(v: str) -> bool:
    if not isinstance(v, str):
        return False
    return v.strip() not in {"", "NA", "."}


def _load_json_list(path: Path) -> Tuple[List[Dict[str, Any]], str]:
    if not path.exists():
        return [], "err:missing_file"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [], f"err:read:{type(e).__name__}"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return [], "err:json_decode"
    except Exception as e:
        return [], f"err:json_load:{type(e).__name__}"
    if not isinstance(obj, list):
        return [], "err:not_a_list"

    out: List[Dict[str, Any]] = []
    for x in obj:
        if isinstance(x, dict):
            out.append(x)
    return out, "ok"


def main() -> int:
    CAP = _env_int("SANITY_CAP", 400)
    TARGET_VALID = _env_int("SANITY_TARGET_VALID", 252)
    FAIL_ON_UNDER_TARGET = _env_bool("SANITY_FAIL_ON_UNDER_TARGET", False)
    VERBOSE = _env_bool("SANITY_VERBOSE", True)

    h, st = _load_json_list(HISTORY_PATH)
    print(f"history_path = {HISTORY_PATH.as_posix()}")
    print(f"load_status  = {st}")
    print(f"history_records = {len(h)}")

    # Structural failure if cannot load
    if not st.startswith("ok"):
        print("Sanity check failed (structural): cannot load history.json")
        return 1

    # 1) Basic row checks + dedupe
    keys: List[Tuple[str, str]] = []
    per_series_all = Counter()
    per_series_valid = Counter()
    bad_rows = 0
    dup_rows = 0

    seen = set()

    for r in h:
        sid = str(r.get("series_id", "")).strip()
        dd = str(r.get("data_date", "")).strip()
        vv = str(r.get("value", "NA")).strip()

        if (not sid) or (not dd) or dd == "NA" or (not _is_ymd(dd)):
            bad_rows += 1
            continue

        per_series_all[sid] += 1

        key = (sid, dd)
        if key in seen:
            dup_rows += 1
        else:
            seen.add(key)

        keys.append(key)

        if _is_valid_value(vv):
            per_series_valid[sid] += 1

    uniq = len(set(keys))
    dedupe_ok = (uniq == len(keys))

    print(f"bad_rows = {bad_rows}")
    print(f"dedupe_ok = {dedupe_ok}")
    if not dedupe_ok:
        print(f"duplicate_rows = {dup_rows}")

    # 2) Cap check
    too_many = {sid: c for sid, c in per_series_all.items() if c > CAP}
    print(f"cap_per_series = {CAP}")
    print(f"cap_ok = {len(too_many) == 0}")
    if too_many and VERBOSE:
        top = sorted(too_many.items(), key=lambda x: x[1], reverse=True)[:20]
        print("cap_violations_top20 =", top)

    # 3) Under-target (valid count) report
    under = {sid: c for sid, c in per_series_valid.items() if c < TARGET_VALID}
    # Some series might be missing entirely (should be reported too)
    all_series_seen = set(per_series_all.keys())
    missing_series = []

    # If you want to assert a fixed universe, set SANITY_EXPECT_SERIES_IDS as comma-separated list.
    expect_s = (os.getenv("SANITY_EXPECT_SERIES_IDS", "") or "").strip()
    expected = []
    if expect_s:
        expected = [x.strip() for x in expect_s.split(",") if x.strip()]
        for sid in expected:
            if sid not in all_series_seen:
                missing_series.append(sid)

    print(f"target_valid = {TARGET_VALID}")
    if VERBOSE:
        # show bottom series first (least valid)
        sorted_valid = sorted(per_series_valid.items(), key=lambda x: x[1])
        print("valid_counts (asc) =", sorted_valid[:20])

    print(f"under_target_count = {len(under)}")
    if under and VERBOSE:
        top_under = sorted(under.items(), key=lambda x: x[1])[:50]
        print("under_target_top50 (lowest first) =", top_under)

    if expected:
        print(f"expected_series_n = {len(expected)}")
        print(f"missing_series_n = {len(missing_series)}")
        if missing_series:
            print("missing_series =", missing_series)

    # Fail conditions (structural strict)
    structural_fail = (bad_rows > 0) or (not dedupe_ok) or (len(too_many) > 0)

    # Optional fail on under-target
    under_target_fail = False
    if FAIL_ON_UNDER_TARGET:
        # also treat missing series as fail if expecting fixed universe
        if under or missing_series:
            under_target_fail = True

    if structural_fail:
        print("Sanity check failed (structural): bad_rows and/or duplicates and/or cap violations")
        return 1

    if under_target_fail:
        print("Sanity check failed (policy): under-target valid counts or missing expected series")
        return 1

    print("Sanity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())