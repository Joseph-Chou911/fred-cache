#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# A+B+C compatible:
# - Always write ruleset_id + script_fingerprint into history items (if present in latest/meta)
# - Deduplicate / overwrite by key:
#   A) rerun guard (same snapshot): (module, ruleset_id, stats_as_of_ts)
#   B) daily guard (same day): (module, ruleset_id, YYYY-MM-DD(stats_as_of_ts))
#     * This prevents streak inflation when stats_as_of_ts updates multiple times per day.
# - If a matching item exists, replace the LAST matching item (keep chronology)
# - Else append new
#
# History schema: dash_history_v2
# {
#   "schema_version": "dash_history_v2",
#   "items": [ { ... } ]
# }

import argparse
import json
import os
from typing import Any, Dict, Optional, List


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def pick_meta(latest: Dict[str, Any]) -> Dict[str, Any]:
    # legacy flat
    run_ts_utc = latest.get("run_ts_utc")
    stats_as_of_ts = latest.get("stats_as_of_ts")
    module = latest.get("module")
    ruleset_id = latest.get("ruleset_id")
    script_fingerprint = latest.get("script_fingerprint")

    # nested meta preferred
    m = latest.get("meta") if isinstance(latest.get("meta"), dict) else {}
    if not run_ts_utc:
        run_ts_utc = m.get("run_ts_utc")
    if not stats_as_of_ts:
        stats_as_of_ts = m.get("stats_as_of_ts")
    if not module:
        module = m.get("module")
    if not ruleset_id:
        ruleset_id = m.get("ruleset_id")
    if not script_fingerprint:
        script_fingerprint = m.get("script_fingerprint")

    stats_as_of_date = str(stats_as_of_ts)[:10] if stats_as_of_ts else None

    return {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "stats_as_of_date": stats_as_of_date,
        "module": module,
        "ruleset_id": ruleset_id,
        "script_fingerprint": script_fingerprint,
    }


def build_series_signals(latest: Dict[str, Any]) -> Optional[Dict[str, str]]:
    ss = latest.get("series_signals")
    if isinstance(ss, dict) and ss:
        out: Dict[str, str] = {}
        for k, v in ss.items():
            if k is None:
                continue
            out[str(k)] = str(v) if v is not None else "NA"
        return out

    rows = latest.get("rows")
    if isinstance(rows, list) and rows:
        out2: Dict[str, str] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            sid = r.get("series")
            sig = r.get("signal_level")
            if not sid or not sig:
                continue
            out2[str(sid)] = str(sig)
        return out2 if out2 else None

    return None


def load_or_init_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "dash_history_v2", "items": []}

    try:
        h = load_json(path)
    except Exception:
        return {"schema_version": "dash_history_v2", "items": []}

    if not isinstance(h, dict):
        return {"schema_version": "dash_history_v2", "items": []}

    if "items" not in h or not isinstance(h["items"], list):
        h["items"] = []

    h["schema_version"] = "dash_history_v2"
    return h


def key_same_snapshot(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        a.get("module") == b.get("module")
        and a.get("ruleset_id") == b.get("ruleset_id")
        and a.get("stats_as_of_ts") == b.get("stats_as_of_ts")
    )


def key_same_day(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        a.get("module") == b.get("module")
        and a.get("ruleset_id") == b.get("ruleset_id")
        and str(a.get("stats_as_of_ts", ""))[:10] == str(b.get("stats_as_of_ts", ""))[:10]
    )


def replace_last_matching(items: List[Dict[str, Any]], new_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace LAST matching item by:
      1) same snapshot key
      2) else same-day key
    Otherwise append.

    Returns stats about what happened.
    """
    # 1) exact snapshot rerun guard
    last_idx = None
    for i in range(len(items) - 1, -1, -1):
        it = items[i]
        if isinstance(it, dict) and key_same_snapshot(it, new_item):
            last_idx = i
            break
    if last_idx is not None:
        items[last_idx] = new_item
        return {"action": "replace_same_snapshot", "index": last_idx}

    # 2) same-day guard (prevents streak inflation)
    last_idx = None
    for i in range(len(items) - 1, -1, -1):
        it = items[i]
        if isinstance(it, dict) and key_same_day(it, new_item):
            last_idx = i
            break
    if last_idx is not None:
        items[last_idx] = new_item
        return {"action": "replace_same_day", "index": last_idx}

    items.append(new_item)
    return {"action": "append", "index": len(items) - 1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="dashboard_latest.json (render output)")
    ap.add_argument("--history", required=True, help="dashboard/history.json")
    ap.add_argument("--max-items", type=int, default=180)
    args = ap.parse_args()

    latest = load_json(args.latest)
    if not isinstance(latest, dict):
        raise SystemExit("dashboard_latest.json must be a JSON object")

    meta = pick_meta(latest)
    required = ["run_ts_utc", "stats_as_of_ts", "stats_as_of_date", "module", "ruleset_id", "script_fingerprint"]
    missing = [k for k in required if not meta.get(k)]
    if missing:
        raise SystemExit("dashboard_latest.json meta missing " + "/".join(missing))

    series_signals = build_series_signals(latest)
    if not series_signals:
        raise SystemExit("dashboard_latest.json missing series_signals or rows[].(series,signal_level)")

    history = load_or_init_history(args.history)
    items = history.get("items", [])
    if not isinstance(items, list):
        items = []

    # keep only dict items (defensive)
    items2: List[Dict[str, Any]] = [it for it in items if isinstance(it, dict)]

    new_item = {
        "run_ts_utc": meta["run_ts_utc"],
        "stats_as_of_ts": meta["stats_as_of_ts"],
        "module": meta["module"],
        "ruleset_id": meta["ruleset_id"],
        "script_fingerprint": meta["script_fingerprint"],
        "series_signals": series_signals,
    }

    result = replace_last_matching(items2, new_item)

    if args.max_items > 0 and len(items2) > args.max_items:
        items2 = items2[-args.max_items :]

    history["schema_version"] = "dash_history_v2"
    history["items"] = items2
    dump_json(args.history, history)

    print(
        "OK: history updated. "
        f"action={result.get('action')} index={result.get('index')} total_items={len(items2)}"
    )


if __name__ == "__main__":
    main()