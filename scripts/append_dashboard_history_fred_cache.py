#!/usr/bin/env python3
# scripts/append_dashboard_history_fred_cache.py
#
# Append/replace dashboard snapshot into dashboard_fred_cache/history.json
# Key: (module, stats_as_of_ts)

import argparse
import json
import os
from typing import Any, Dict, List, Tuple


SCHEMA_VERSION = "dash_history_v1"
MAX_ITEMS = 2000


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": SCHEMA_VERSION, "items": []}
    try:
        obj = load_json(path)
        if not isinstance(obj, dict):
            return {"schema_version": SCHEMA_VERSION, "items": []}
        if "items" not in obj or not isinstance(obj.get("items"), list):
            obj["items"] = []
        if "schema_version" not in obj:
            obj["schema_version"] = SCHEMA_VERSION
        return obj
    except Exception:
        return {"schema_version": SCHEMA_VERSION, "items": []}


def build_item(dash_latest: Dict[str, Any], module: str) -> Dict[str, Any]:
    meta = dash_latest.get("meta", {})
    rows = dash_latest.get("rows", [])

    run_ts_utc = meta.get("run_ts_utc") if isinstance(meta, dict) else None
    stats_as_of_ts = meta.get("stats_as_of_ts") if isinstance(meta, dict) else None

    if not isinstance(run_ts_utc, str) or not run_ts_utc:
        run_ts_utc = "NA"
    if not isinstance(stats_as_of_ts, str) or not stats_as_of_ts:
        stats_as_of_ts = "NA"

    series_signals: Dict[str, str] = {}
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict):
                continue
            sid = r.get("series")
            sig = r.get("signal_level")
            if isinstance(sid, str) and sid and isinstance(sig, str) and sig:
                series_signals[sid] = sig

    return {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "series_signals": series_signals,
    }


def key_of(item: Dict[str, Any]) -> Tuple[str, str]:
    return (str(item.get("module", "")), str(item.get("stats_as_of_ts", "")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dash-latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--module", required=True)
    args = ap.parse_args()

    dash_latest = load_json(args.dash_latest)
    if not isinstance(dash_latest, dict):
        raise SystemExit("dash_latest is not a json object")

    new_item = build_item(dash_latest, args.module)
    hist = load_history(args.history)

    items: List[Dict[str, Any]] = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    new_key = key_of(new_item)

    replaced = False
    out_items: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if key_of(it) == new_key:
            out_items.append(new_item)
            replaced = True
        else:
            out_items.append(it)

    if not replaced:
        out_items.append(new_item)

    if len(out_items) > MAX_ITEMS:
        out_items = out_items[-MAX_ITEMS:]

    hist["schema_version"] = SCHEMA_VERSION
    hist["items"] = out_items

    save_json(args.history, hist)


if __name__ == "__main__":
    main()