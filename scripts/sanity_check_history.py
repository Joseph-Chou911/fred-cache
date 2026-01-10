#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sanity checks for FRED cache files.

Checks:
A) cache/history.json
  - Valid JSON list
  - Each row is dict and has required keys
  - data_date format YYYY-MM-DD (or row is counted as bad)
  - No duplicate (series_id, data_date)
  - cap_per_series <= CAP
  - Optional: ordering check (series_id asc, data_date asc, as_of_ts asc)

B) cache/history_lite.json
  - Same structural checks as history.json
  - Per-series count <= TARGET_VALID (252 by default)

C) cache/backfill_state.json (v2 last_attempt only)
  - schema_version == "backfill_state_v2_last_attempt_only"
  - For each series: only allowed keys exist (strict)
  - done/have_valid/target_valid consistency
  - cooldown_runs_left / consecutive_no_progress are non-negative ints
  - If done==True then have_valid >= target_valid
  - last_attempt_* fields exist (may be "NA") and are type-safe

Exit code:
  0 = pass
  1 = fail
"""

import json
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Tuple

# ---- Tunables (keep in sync with fred_cache.py) ----
CAP = 400
TARGET_VALID = 252
FETCH_LIMIT = 420  # informational only; not enforced strictly

HISTORY_PATH = Path("cache/history.json")
HISTORY_LITE_PATH = Path("cache/history_lite.json")
BACKFILL_STATE_PATH = Path("cache/backfill_state.json")

BACKFILL_SCHEMA_V2 = "backfill_state_v2_last_attempt_only"

REQUIRED_ROW_KEYS = {"as_of_ts", "series_id", "data_date", "value", "source_url", "notes"}

ALLOWED_BACKFILL_TOP_KEYS = {
    "schema_version",
    "as_of_ts",
    "generated_at_utc",
    "target_valid",
    "fetch_limit",
    "series",
}

ALLOWED_BACKFILL_SERIES_KEYS = {
    "done",
    "have_valid",
    "target_valid",
    "fetch_limit",
    "last_attempt_at",
    "last_http_status",
    "last_attempts",
    "last_err",
    "last_count_raw",
    "last_count_kept",
    "consecutive_no_progress",
    "cooldown_runs_left",
}


def is_ymd(s: Any) -> bool:
    return isinstance(s, str) and len(s) == 10 and s[4] == "-" and s[7] == "-"


def safe_load_json(path: Path) -> Tuple[Any, str]:
    if not path.exists():
        return None, "missing_file"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj, "ok"
    except Exception as e:
        return None, f"json_load_error:{type(e).__name__}"


def check_history_like(path: Path, cap_per_series: int, enforce_sorted: bool, per_series_max: int = 0) -> Tuple[bool, Dict[str, Any]]:
    """
    per_series_max:
      0 -> do not enforce per-series max
      >0 -> enforce per-series count <= per_series_max
    """
    report: Dict[str, Any] = {"path": str(path), "ok": True}
    obj, st = safe_load_json(path)
    report["read_status"] = st
    if st != "ok":
        report["ok"] = False
        report["reason"] = "cannot_read_json"
        return False, report

    if not isinstance(obj, list):
        report["ok"] = False
        report["reason"] = "not_a_list"
        return False, report

    rows: List[Dict[str, Any]] = []
    bad_rows = 0
    missing_keys = 0

    keys_seen = []
    per_series = Counter()

    # for sorting check
    last_sort_key = None
    ordering_ok = True

    for i, r in enumerate(obj):
        if not isinstance(r, dict):
            bad_rows += 1
            continue

        # required keys
        if not REQUIRED_ROW_KEYS.issubset(set(r.keys())):
            missing_keys += 1
            # still try to extract minimal fields
        sid = str(r.get("series_id", "")).strip()
        dd = str(r.get("data_date", "")).strip()
        as_of = str(r.get("as_of_ts", "")).strip()

        if (not sid) or (not dd) or dd == "NA" or (not is_ymd(dd)) or (not as_of):
            bad_rows += 1
            continue

        rows.append(r)
        keys_seen.append((sid, dd))
        per_series[sid] += 1

        if enforce_sorted:
            k = (sid, dd, as_of)
            if last_sort_key is not None and k < last_sort_key:
                ordering_ok = False
            last_sort_key = k

    uniq = len(set(keys_seen))
    report["records_raw"] = len(obj)
    report["records_valid"] = len(rows)
    report["bad_rows"] = bad_rows
    report["missing_keys_rows"] = missing_keys
    report["dedupe_ok"] = (uniq == len(keys_seen))
    report["ordering_ok"] = ordering_ok if enforce_sorted else "skipped"

    # cap check
    too_many = {sid: c for sid, c in per_series.items() if c > cap_per_series}
    report["cap_per_series"] = cap_per_series
    report["cap_ok"] = (len(too_many) == 0)
    if too_many:
        report["cap_violations_top10"] = sorted(too_many.items(), key=lambda x: x[1], reverse=True)[:10]

    # per_series_max check (lite)
    if per_series_max > 0:
        too_many_lite = {sid: c for sid, c in per_series.items() if c > per_series_max}
        report["per_series_max"] = per_series_max
        report["per_series_max_ok"] = (len(too_many_lite) == 0)
        if too_many_lite:
            report["per_series_max_violations_top10"] = sorted(too_many_lite.items(), key=lambda x: x[1], reverse=True)[:10]
    else:
        report["per_series_max"] = 0
        report["per_series_max_ok"] = "skipped"

    ok = True
    if bad_rows > 0:
        ok = False
    if uniq != len(keys_seen):
        ok = False
    if len(too_many) > 0:
        ok = False
    if enforce_sorted and not ordering_ok:
        ok = False
    if per_series_max > 0 and report["per_series_max_ok"] is False:
        ok = False
    if missing_keys > 0:
        ok = False

    report["ok"] = ok
    return ok, report


def _is_int_nonneg(x: Any) -> bool:
    return isinstance(x, int) and x >= 0


def check_backfill_state_v2(path: Path) -> Tuple[bool, Dict[str, Any]]:
    report: Dict[str, Any] = {"path": str(path), "ok": True}
    obj, st = safe_load_json(path)
    report["read_status"] = st
    if st == "missing_file":
        # allow missing file for first-ever run
        report["ok"] = True
        report["note"] = "missing_file_allowed"
        return True, report
    if st != "ok":
        report["ok"] = False
        report["reason"] = "cannot_read_json"
        return False, report
    if not isinstance(obj, dict):
        report["ok"] = False
        report["reason"] = "not_a_dict"
        return False, report

    # top-level strict keys
    top_keys = set(obj.keys())
    unknown_top = sorted(list(top_keys - ALLOWED_BACKFILL_TOP_KEYS))
    report["unknown_top_keys"] = unknown_top
    if unknown_top:
        report["ok"] = False
        report["reason"] = "unknown_top_keys_present"
        return False, report

    schema = obj.get("schema_version", "NA")
    report["schema_version"] = schema
    if schema != BACKFILL_SCHEMA_V2:
        report["ok"] = False
        report["reason"] = "schema_version_mismatch"
        return False, report

    series = obj.get("series", {})
    if not isinstance(series, dict):
        report["ok"] = False
        report["reason"] = "series_not_dict"
        return False, report

    bad_series = 0
    unknown_series_keys_total = 0
    done_inconsistent = 0
    negative_int_fields = 0

    for sid, s in series.items():
        if not isinstance(sid, str) or not isinstance(s, dict):
            bad_series += 1
            continue

        s_keys = set(s.keys())
        unknown = s_keys - ALLOWED_BACKFILL_SERIES_KEYS
        unknown_series_keys_total += len(unknown)
        if unknown:
            bad_series += 1
            continue

        done = bool(s.get("done", False))
        have_valid = s.get("have_valid", 0)
        target_valid = s.get("target_valid", TARGET_VALID)

        try:
            have_valid_i = int(have_valid)
            target_valid_i = int(target_valid)
        except Exception:
            bad_series += 1
            continue

        if done and have_valid_i < target_valid_i:
            done_inconsistent += 1

        cnp = s.get("consecutive_no_progress", 0)
        cd = s.get("cooldown_runs_left", 0)
        if not _is_int_nonneg(cnp) or not _is_int_nonneg(cd):
            negative_int_fields += 1

        # last_attempt fields presence (type-safe; allow "NA")
        for k in ["last_attempt_at", "last_http_status", "last_attempts", "last_err", "last_count_raw", "last_count_kept"]:
            if k not in s:
                bad_series += 1
                break

    report["series_count"] = len(series)
    report["bad_series"] = bad_series
    report["unknown_series_keys_total"] = unknown_series_keys_total
    report["done_inconsistent"] = done_inconsistent
    report["negative_int_fields"] = negative_int_fields

    ok = True
    if bad_series > 0:
        ok = False
    if unknown_series_keys_total > 0:
        ok = False
    if done_inconsistent > 0:
        ok = False
    if negative_int_fields > 0:
        ok = False

    report["ok"] = ok
    return ok, report


def main() -> int:
    # History
    ok_h, rep_h = check_history_like(
        HISTORY_PATH,
        cap_per_series=CAP,
        enforce_sorted=True,
        per_series_max=0,
    )

    # History lite
    ok_l, rep_l = check_history_like(
        HISTORY_LITE_PATH,
        cap_per_series=CAP,          # still must respect global cap
        enforce_sorted=True,
        per_series_max=TARGET_VALID, # lite must be <= target_valid
    )

    # Backfill state v2
    ok_b, rep_b = check_backfill_state_v2(BACKFILL_STATE_PATH)

    # Print summary (human friendly)
    print("=== sanity_check_history.py ===")
    print("[A] history.json")
    print("  path =", rep_h.get("path"))
    print("  read_status =", rep_h.get("read_status"))
    print("  records_raw =", rep_h.get("records_raw"))
    print("  records_valid =", rep_h.get("records_valid"))
    print("  dedupe_ok =", rep_h.get("dedupe_ok"))
    print("  bad_rows =", rep_h.get("bad_rows"))
    print("  missing_keys_rows =", rep_h.get("missing_keys_rows"))
    print("  cap_per_series =", rep_h.get("cap_per_series"))
    print("  cap_ok =", rep_h.get("cap_ok"))
    print("  ordering_ok =", rep_h.get("ordering_ok"))
    if rep_h.get("cap_ok") is False:
        print("  cap_violations_top10 =", rep_h.get("cap_violations_top10"))

    print("[B] history_lite.json")
    print("  path =", rep_l.get("path"))
    print("  read_status =", rep_l.get("read_status"))
    print("  records_raw =", rep_l.get("records_raw"))
    print("  records_valid =", rep_l.get("records_valid"))
    print("  dedupe_ok =", rep_l.get("dedupe_ok"))
    print("  bad_rows =", rep_l.get("bad_rows"))
    print("  missing_keys_rows =", rep_l.get("missing_keys_rows"))
    print("  per_series_max =", rep_l.get("per_series_max"))
    print("  per_series_max_ok =", rep_l.get("per_series_max_ok"))
    print("  ordering_ok =", rep_l.get("ordering_ok"))
    if rep_l.get("per_series_max_ok") is False:
        print("  per_series_max_violations_top10 =", rep_l.get("per_series_max_violations_top10"))

    print("[C] backfill_state.json (v2)")
    print("  path =", rep_b.get("path"))
    print("  read_status =", rep_b.get("read_status"))
    if rep_b.get("read_status") == "missing_file":
        print("  note =", rep_b.get("note"))
    else:
        print("  schema_version =", rep_b.get("schema_version"))
        print("  unknown_top_keys =", rep_b.get("unknown_top_keys"))
        print("  series_count =", rep_b.get("series_count"))
        print("  bad_series =", rep_b.get("bad_series"))
        print("  unknown_series_keys_total =", rep_b.get("unknown_series_keys_total"))
        print("  done_inconsistent =", rep_b.get("done_inconsistent"))
        print("  negative_int_fields =", rep_b.get("negative_int_fields"))

    ok_all = ok_h and ok_l and ok_b
    if ok_all:
        print("Sanity check passed")
        return 0

    print("Sanity check failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())