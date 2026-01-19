#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# scripts/append_dashboard_history.py
#
# A+B compatible:
# - Always write ruleset_id + script_fingerprint into history items (if present in latest/meta)
# - Deduplicate / overwrite by key: (module, ruleset_id, stats_as_of_ts)
#   * If a matching item exists, replace the LAST matching item (rerun guard)
#   * Else append new
#
# C compatible:
# - Renderer ignores legacy items missing ruleset_id, so this appender should always populate it.
#
# History schema: dash_history_v2
# {
#   "schema_version": "dash_history_v2",
#   "items": [
#     {
#       "run_ts_utc": "...",
#       "stats_as_of_ts": "...",
#       "module": "...",
#       "ruleset_id": "signals_v8",
#       "script_fingerprint": "...",
#       "series_signals": {...}
#     }
#   ]
# }

import argparse
import json
import os
from typing import Any, Dict, Optional, Tuple


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
        "ruleset_id": "...",
        "script_fingerprint": "...",
        "series_signals": {...}
      }

    B) Render output schema:
      {
        "meta": {...},
        "rows": [...],
        "series_signals": {...}
      }
    """
    # top-level
    run_ts_utc = latest.get("run_ts_utc")
    stats_as_of_ts = latest.get("stats_as_of_ts")
    module = latest.get("module")
    ruleset_id = latest.get("ruleset_id")
    script_fingerprint = latest.get("script_fingerprint")

    # nested meta fallback
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

    return {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "ruleset_id": ruleset_id,
        "script_fingerprint": script_fingerprint,
    }


def build_series_signals(latest: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Prefer latest["series_signals"] if exists; else derive from rows:
      rows[i].series + rows[i].signal_level
    """
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
        return {"schema_version": "dash_history_v2", "items": []}

    try:
        h = load_json(path)
    except Exception:
        return {"schema_version": "dash_history_v2", "items": []}

    if not isinstance(h, dict):
        return {"schema_version": "dash_history_v2", "items": []}

    items = h.get("items")
    if not isinstance(items, list):
        h["items"] = []

    # force schema_version to v2 (upgrade in place)
    h["schema_version"] = "dash_history_v2"
    return h


def dedupe_key(module: str, ruleset_id: str, stats_as_of_ts: str) -> Tuple[str, str, str]:
    return (str(module), str(ruleset_id), str(stats_as_of_ts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="dashboard_latest.json (render output)")
    ap.add_argument("--history", required=True, help="dashboard/history.json")
    ap.add_argument("--max-items", type=int, default=400)
    args = ap.parse_args()

    latest = load_json(args.latest)
    if not isinstance(latest, dict):
        raise SystemExit("dashboard_latest.json must be a JSON object")

    meta = pick_meta(latest)
    run_ts_utc = meta.get("run_ts_utc")
    stats_as_of_ts = meta.get("stats_as_of_ts")
    module = meta.get("module")
    ruleset_id = meta.get("ruleset_id")
    script_fingerprint = meta.get("script_fingerprint")

    missing = []
    if not run_ts_utc:
        missing.append("run_ts_utc")
    if not stats_as_of_ts:
        missing.append("stats_as_of_ts")
    if not module:
        missing.append("module")
    if not ruleset_id:
        missing.append("ruleset_id")

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
    if not isinstance(items, list):
        items = []

    new_item: Dict[str, Any] = {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "ruleset_id": ruleset_id,
        "script_fingerprint": script_fingerprint or "NA",
        "series_signals": series_signals,
    }

    # ---- A) dedupe / overwrite by (module, ruleset_id, stats_as_of_ts) ----
    k_new = dedupe_key(module, ruleset_id, stats_as_of_ts)

    last_match_idx: Optional[int] = None
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        # Only consider items that have ruleset_id; legacy items won't match anyway
        m = it.get("module")
        r = it.get("ruleset_id")
        s = it.get("stats_as_of_ts")
        if m and r and s and dedupe_key(m, r, s) == k_new:
            last_match_idx = i

    if last_match_idx is None:
        items.append(new_item)
        action = "append"
    else:
        items[last_match_idx] = new_item
        action = f"overwrite@index={last_match_idx}"

    # cap
    if args.max_items > 0 and len(items) > args.max_items:
        items = items[-args.max_items :]

    history["items"] = items
    dump_json(args.history, history)

    print(f"OK: {action}. total_items={len(items)}")


if __name__ == "__main__":
    main()