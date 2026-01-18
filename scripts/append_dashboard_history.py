#!/usr/bin/env python3
# scripts/append_dashboard_history.py
#
# Append current dashboard_latest.json signals into dashboard/history.json
# so that PrevSignal/StreakWA is audit-consistent with produced outputs.
#
# History schema:
# {
#   "schema_version": "dash_history_v1",
#   "items": [
#     {
#       "run_ts_utc": "...",
#       "stats_as_of_ts": "...",
#       "module": "market_cache",
#       "series_signals": { "VIX": "NONE", "SP500": "INFO", ... }
#     },
#     ...
#   ]
# }
#
# Dedup rule:
#   - If an existing item has same (module, stats_as_of_ts), replace it (idempotent).
# Retention:
#   - Keep last --max-items (default 400)

import argparse
import json
import os
from typing import Any, Dict, List


SCHEMA_VERSION = "dash_history_v1"


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="Path to dashboard/dashboard_latest.json")
    ap.add_argument("--history", required=True, help="Path to dashboard/history.json")
    ap.add_argument("--max-items", type=int, default=400)
    args = ap.parse_args()

    latest = load_json(args.latest)
    meta = latest.get("meta", {})
    rows = latest.get("rows", [])

    if not isinstance(meta, dict) or not isinstance(rows, list):
        raise SystemExit("Invalid dashboard_latest.json: meta/rows missing or wrong type")

    run_ts_utc = meta.get("run_ts_utc")
    stats_as_of_ts = meta.get("stats_as_of_ts")
    module = meta.get("module")

    if not (isinstance(run_ts_utc, str) and isinstance(stats_as_of_ts, str) and isinstance(module, str)):
        raise SystemExit("dashboard_latest.json meta missing run_ts_utc/stats_as_of_ts/module")

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
        "module": module,
        "series_signals": series_signals,
    }

    # Load existing history (if any)
    if os.path.exists(args.history):
        hist = load_json(args.history)
    else:
        hist = {"schema_version": SCHEMA_VERSION, "items": []}

    if not isinstance(hist, dict):
        hist = {"schema_version": SCHEMA_VERSION, "items": []}

    items = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    # Dedup by (module, stats_as_of_ts)
    out: List[Dict[str, Any]] = []
    replaced = False
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("module") == module and it.get("stats_as_of_ts") == stats_as_of_ts:
            out.append(new_item)
            replaced = True
        else:
            out.append(it)

    if not replaced:
        out.append(new_item)

    # Retention
    if len(out) > args.max_items:
        out = out[-args.max_items :]

    hist["schema_version"] = SCHEMA_VERSION
    hist["items"] = out

    save_json(args.history, hist)


if __name__ == "__main__":
    main()