#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
from pathlib import Path
from collections import Counter

CAP_PER_SERIES = 400
LITE_TARGET = 252

HISTORY_PATH = Path("cache/history.json")
LITE_PATH = Path("cache/history_lite.json")
STATS_PATH = Path("cache/stats_latest.json")

REQUIRED_FIELDS = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]


def _is_ymd(s: str) -> bool:
    return isinstance(s, str) and len(s) == 10 and s[4] == "-" and s[7] == "-"


def _to_float(v) -> bool:
    try:
        if v is None:
            return False
        s = str(v).strip()
        if s in {"", "NA", "."}:
            return False
        float(s)
        return True
    except Exception:
        return False


def _load_list(p: Path):
    if not p.exists():
        return [], "missing"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            return obj, "ok"
        return [], "not_list"
    except Exception as e:
        return [], f"bad_json:{type(e).__name__}"


def _load_dict(p: Path):
    if not p.exists():
        return {}, "missing"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj, "ok"
        return {}, "not_dict"
    except Exception as e:
        return {}, f"bad_json:{type(e).__name__}"


def _check_history_like(rows, cap: int, label: str):
    keys = []
    per_series = Counter()
    bad = 0
    missing_field = 0
    bad_date = 0
    bad_value = 0

    for r in rows:
        if not isinstance(r, dict):
            bad += 1
            continue

        for f in REQUIRED_FIELDS:
            if f not in r:
                missing_field += 1
                break

        sid = str(r.get("series_id", "")).strip()
        dd = str(r.get("data_date", "")).strip()
        vv = r.get("value", "NA")

        if (not sid) or (not dd) or dd == "NA":
            bad += 1
            continue
        if not _is_ymd(dd):
            bad_date += 1
            continue
        if not _to_float(vv):
            bad_value += 1
            continue

        keys.append((sid, dd))
        per_series[sid] += 1

    uniq = len(set(keys))
    dedupe_ok = (uniq == len(keys))

    too_many = {sid: c for sid, c in per_series.items() if c > cap}
    cap_ok = (len(too_many) == 0)

    print(f"[{label}] records =", len(rows))
    print(f"[{label}] dedupe_ok =", dedupe_ok)
    print(f"[{label}] bad_rows =", bad)
    print(f"[{label}] missing_field =", missing_field)
    print(f"[{label}] bad_date =", bad_date)
    print(f"[{label}] bad_value =", bad_value)
    print(f"[{label}] cap_per_series =", cap)
    print(f"[{label}] cap_ok =", cap_ok)
    if too_many:
        top = sorted(too_many.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"[{label}] cap_violations_top10 =", top)

    ok = True
    if not dedupe_ok:
        ok = False
    if bad > 0 or missing_field > 0 or bad_date > 0 or bad_value > 0:
        ok = False
    if not cap_ok:
        ok = False
    return ok, per_series


def _check_stats(stats: dict):
    ok = True
    if not isinstance(stats, dict):
        print("[stats] not a dict")
        return False

    series = stats.get("series")
    if not isinstance(series, dict):
        print("[stats] missing/invalid series")
        return False

    # Minimal checks: for each series, latest must exist; window n must be ints; metric values NA or finite numbers
    bad = 0
    for sid, obj in series.items():
        if not isinstance(obj, dict):
            bad += 1
            continue

        latest = obj.get("latest", {})
        if not isinstance(latest, dict):
            bad += 1
            continue
        dd = latest.get("data_date", "NA")
        vv = latest.get("value", "NA")
        if dd != "NA" and not _is_ymd(str(dd)):
            bad += 1

        windows = obj.get("windows", {})
        if not isinstance(windows, dict):
            bad += 1
            continue
        for wkey in ["w60", "w252"]:
            w = windows.get(wkey, {})
            if not isinstance(w, dict):
                bad += 1
                continue
            n = w.get("n", None)
            if not isinstance(n, int):
                bad += 1

        metrics = obj.get("metrics", {})
        if not isinstance(metrics, dict):
            bad += 1
            continue

        def _num_or_na(x):
            if x == "NA":
                return True
            if isinstance(x, (int, float)):
                return math.isfinite(float(x))
            return False

        for k in ["ma60", "dev60", "z60", "p60", "z252", "p252", "ret1"]:
            if k in metrics and not _num_or_na(metrics.get(k)):
                bad += 1

    print("[stats] series_keys =", len(series))
    print("[stats] bad_fields =", bad)
    if bad > 0:
        ok = False
    return ok


def main() -> int:
    h, hs = _load_list(HISTORY_PATH)
    lite, ls = _load_list(LITE_PATH)
    stats, ss = _load_dict(STATS_PATH)

    print("history_status =", hs)
    print("lite_status    =", ls)
    print("stats_status   =", ss)

    ok_all = True

    ok_h, per_series_h = _check_history_like(h, CAP_PER_SERIES, "history")
    ok_l, per_series_l = _check_history_like(lite, LITE_TARGET, "lite")
    ok_s = _check_stats(stats) if ss == "ok" else False

    if not ok_h:
        ok_all = False
    if not ok_l:
        ok_all = False
    if not ok_s:
        ok_all = False

    # Extra: lite should never exceed history per series (soft check)
    # If history missing, skip.
    if hs == "ok" and ls == "ok":
        overs = []
        for sid, c in per_series_l.items():
            if c > per_series_h.get(sid, 0):
                overs.append((sid, c, per_series_h.get(sid, 0)))
        if overs:
            print("[soft] lite_exceeds_history =", overs[:10])
            ok_all = False

    if not ok_all:
        print("Sanity check failed")
        return 1

    print("Sanity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())