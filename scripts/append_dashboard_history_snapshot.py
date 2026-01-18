#!/usr/bin/env python3
# scripts/append_dashboard_history_snapshot.py
#
# Append snapshot dashboard outputs into shared dashboard/history.json
# - Reads renderer output JSON: {"meta": {...}, "rows": [...]}
# - Writes/updates dashboard/history.json with schema dash_history_v1
# - Dedup key: (module, stats_as_of_ts) where stats_as_of_ts comes from:
#     meta.stats_as_of_ts OR meta.snapshot_as_of_ts OR meta.as_of_ts
#
# Stored item:
# {
#   "run_ts_utc": "...",
#   "stats_as_of_ts": "...",
#   "module": "...",
#   "series_signals": { "SERIES": "WATCH", ... }
# }

import argparse
import json
import os
from typing import Any, Dict, List, Optional


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-json", required=True, help="dashboard/dashboard_snapshot_latest.json")
    ap.add_argument("--history", default="dashboard/history.json", help="shared history path")
    ap.add_argument("--module", required=True, help="module name for separation, e.g., snapshot_fast")
    ap.add_argument("--max-items", type=int, default=400, help="cap history size")
    args = ap.parse_args()

    inp = load_json(args.in_json)
    if not isinstance(inp, dict):
        raise SystemExit("input must be an object with meta/rows")

    meta = inp.get("meta", {})
    rows = inp.get("rows", [])
    if not isinstance(meta, dict) or not isinstance(rows, list):
        raise SystemExit("invalid input schema")

    run_ts_utc = meta.get("run_ts_utc") or "NA"

    stats_as_of_ts = (
        meta.get("stats_as_of_ts")
        or meta.get("snapshot_as_of_ts")
        or meta.get("as_of_ts")
        or "NA"
    )

    series_signals: Dict[str, str] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        sid = r.get("series")
        sig = r.get("signal_level")
        if isinstance(sid, str) and isinstance(sig, str):
            series_signals[sid] = sig

    new_item = {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": args.module,
        "series_signals": series_signals,
    }

    # load history
    if os.path.exists(args.history):
        hist = load_json(args.history)
        if not isinstance(hist, dict):
            hist = {}
    else:
        hist = {}

    if hist.get("schema_version") != "dash_history_v1":
        hist = {"schema_version": "dash_history_v1", "items": []}

    items = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    # dedup/replace
    replaced = False
    for i in range(len(items)):
        it = items[i]
        if not isinstance(it, dict):
            continue
        if it.get("module") == args.module and it.get("stats_as_of_ts") == stats_as_of_ts:
            items[i] = new_item
            replaced = True
            break

    if not replaced:
        items.append(new_item)

    # cap
    if len(items) > args.max_items:
        items = items[-args.max_items :]

    hist["items"] = items
    save_json(args.history, hist)


if __name__ == "__main__":
    main()