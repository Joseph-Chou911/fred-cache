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
        "ruleset_id": "...",
        "script_fingerprint": "...",
        "series_signals": {...}
      }

    B) Render output schema:
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
    """
    # 1) flat
    run_ts_utc = latest.get("run_ts_utc")
    stats_as_of_ts = latest.get("stats_as_of_ts")
    module = latest.get("module")
    ruleset_id = latest.get("ruleset_id")
    script_fingerprint = latest.get("script_fingerprint")

    # 2) nested meta fallback
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
    if "schema_version" not in h:
        h["schema_version"] = "dash_history_v2"
    return h


def should_replace_last(items: list, module: str, stats_as_of_ts: str, ruleset_id: Optional[str]) -> bool:
    """
    Rerun guard:
    If the last item has the same (module + stats_as_of_ts + ruleset_id),
    replace it instead of appending. This prevents streak inflation on reruns.
    """
    if not items:
        return False
    last = items[-1]
    if not isinstance(last, dict):
        return False
    if last.get("module") != module:
        return False
    if last.get("stats_as_of_ts") != stats_as_of_ts:
        return False
    # ruleset_id may be None for legacy; still handle safely
    if ruleset_id is not None:
        return last.get("ruleset_id") == ruleset_id
    return True


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
    if not script_fingerprint:
        missing.append("script_fingerprint")

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
        "ruleset_id": ruleset_id,
        "script_fingerprint": script_fingerprint,
        "series_signals": series_signals,
    }

    # Rerun guard: replace last if same stats snapshot
    replaced = False
    if should_replace_last(items, module, stats_as_of_ts, ruleset_id):
        items[-1] = new_item
        replaced = True
    else:
        items.append(new_item)

    # cap
    if args.max_items > 0 and len(items) > args.max_items:
        items = items[-args.max_items :]

    history["items"] = items
    history["schema_version"] = "dash_history_v2"
    dump_json(args.history, history)

    if replaced:
        print(f"OK: replaced last history item (rerun guard). total_items={len(items)}")
    else:
        print(f"OK: appended history item. total_items={len(items)}")


if __name__ == "__main__":
    main()