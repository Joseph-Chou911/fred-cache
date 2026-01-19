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
    Accept render output schema:
      {
        "meta": {
          "run_ts_utc": "...",
          "stats_as_of_ts": "...",
          "module": "...",
          "ruleset_id": "...",
          "script_fingerprint": "..."
        },
        "rows": [...],
        "series_signals": {...}
      }

    Also accept legacy flat schema if needed.
    """
    # 1) flat (legacy)
    run_ts_utc = latest.get("run_ts_utc")
    stats_as_of_ts = latest.get("stats_as_of_ts")
    module = latest.get("module")
    ruleset_id = latest.get("ruleset_id")
    script_fingerprint = latest.get("script_fingerprint")

    # 2) nested meta preferred
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
        out = {}
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

    if "items" not in h or not isinstance(h["items"], list):
        h["items"] = []

    # normalize schema_version
    h["schema_version"] = "dash_history_v2"
    return h


def same_key(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """
    Dedupe key: (module, ruleset_id, stats_as_of_ts)
    """
    return (
        a.get("module") == b.get("module")
        and a.get("ruleset_id") == b.get("ruleset_id")
        and a.get("stats_as_of_ts") == b.get("stats_as_of_ts")
    )


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

    required = ["run_ts_utc", "stats_as_of_ts", "module", "ruleset_id", "script_fingerprint"]
    missing = [k for k in required if not meta.get(k)]
    if missing:
        raise SystemExit(
            "dashboard_latest.json meta missing "
            + "/".join(missing)
            + " (expects meta.*; legacy top-level accepted for some fields)"
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
        "run_ts_utc": meta["run_ts_utc"],
        "stats_as_of_ts": meta["stats_as_of_ts"],
        "module": meta["module"],
        "ruleset_id": meta["ruleset_id"],
        "script_fingerprint": meta["script_fingerprint"],
        "series_signals": series_signals,
    }

    # --- DEDUPE (critical for streak meaning) ---
    kept: list = []
    removed = 0
    for it in items:
        if isinstance(it, dict) and same_key(it, new_item):
            removed += 1
            continue
        kept.append(it)

    kept.append(new_item)

    # cap
    if args.max_items > 0 and len(kept) > args.max_items:
        kept = kept[-args.max_items :]

    history["schema_version"] = "dash_history_v2"
    history["items"] = kept
    dump_json(args.history, history)

    print(f"OK: appended history item. removed_same_key={removed} total_items={len(kept)}")


if __name__ == "__main__":
    main()