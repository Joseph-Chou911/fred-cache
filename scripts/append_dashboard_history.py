#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
from typing import Any, Dict, Optional


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def pick_meta(latest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Support both schemas:

    A) Flat schema:
      {
        "run_ts_utc": "...",
        "stats_as_of_ts": "...",
        "module": "...",
        "series_signals": {...}
      }

    B) Render output schema:
      {
        "meta": {
          "run_ts_utc": "...",
          "stats_as_of_ts": "...",
          "module": "..."
        },
        "rows": [...]
      }
    """
    # 1) flat
    run_ts_utc = latest.get("run_ts_utc")
    stats_as_of_ts = latest.get("stats_as_of_ts")
    module = latest.get("module")

    # 2) nested meta fallback
    m = latest.get("meta") if isinstance(latest.get("meta"), dict) else {}
    if not run_ts_utc:
        run_ts_utc = m.get("run_ts_utc")
    if not stats_as_of_ts:
        stats_as_of_ts = m.get("stats_as_of_ts")
    if not module:
        module = m.get("module")

    return {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
    }


def build_series_signals(latest: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Prefer latest["series_signals"] if exists; else derive from rows:
      rows[i].series + rows[i].signal_level
    """
    ss = latest.get("series_signals")
    if isinstance(ss, dict) and ss:
        # normalize values to str
        out = {}
        for k, v in ss.items():
            if k is None:
                continue
            out[str(k)] = str(v) if v is not None else "NA"
        return out

    rows = latest.get("rows")
    if isinstance(rows, list) and rows:
        out: Dict[str, str] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            sid = r.get("series")
            sig = r.get("signal_level")
            if not sid or not sig:
                continue
            out[str(sid)] = str(sig)
        return out if out else None

    return None


def load_or_init_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "dash_history_v1", "items": []}

    try:
        h = load_json(path)
    except Exception:
        return {"schema_version": "dash_history_v1", "items": []}

    if not isinstance(h, dict):
        return {"schema_version": "dash_history_v1", "items": []}
    if "items" not in h or not isinstance(h["items"], list):
        h["items"] = []
    if "schema_version" not in h:
        h["schema_version"] = "dash_history_v1"
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="dashboard_latest.json (render output)")
    ap.add_argument("--history", required=True, help="dashboard/history.json")
    ap.add_argument("--max-items", type=int, default=180)
    args = ap.parse_args()

    latest = load_json(args.latest)
    if not isinstance(latest, dict):
        raise SystemExit("dashboard_latest.json must be a JSON object")

    meta = pick_meta(latest)
    run_ts_utc = meta.get("run_ts_utc")
    stats_as_of_ts = meta.get("stats_as_of_ts")
    module = meta.get("module")

    missing = []
    if not run_ts_utc:
        missing.append("run_ts_utc")
    if not stats_as_of_ts:
        missing.append("stats_as_of_ts")
    if not module:
        missing.append("module")

    if missing:
        raise SystemExit(
            "dashboard_latest.json meta missing " + "/".join(missing)
            + " (accepts either top-level or meta.*)"
        )

    series_signals = build_series_signals(latest)
    if not series_signals:
        raise SystemExit(
            "dashboard_latest.json missing series signals: "
            "need either top-level series_signals{} or rows[].(series, signal_level)"
        )

    history = load_or_init_history(args.history)
    items = history.get("items", [])

    new_item = {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "series_signals": series_signals,
    }

    items.append(new_item)

    # cap
    if args.max_items > 0 and len(items) > args.max_items:
        items = items[-args.max_items :]

    history["items"] = items
    dump_json(args.history, history)

    print(f"OK: appended history item. total_items={len(items)}")


if __name__ == "__main__":
    main()