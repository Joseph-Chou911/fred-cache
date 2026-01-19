#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# scripts/append_dashboard_history.py
#
# Supports:
# - Always write ruleset_id + script_fingerprint into history items (if present)
# - History schema: dash_history_v2
#
# Dedupe modes:
# - as_of_ts (default): dedupe/overwrite by (module, ruleset_id, stats_as_of_ts)
# - signals: only append when series_signals changed for the same (module, ruleset_id);
#            otherwise overwrite the LAST item for that (module, ruleset_id)
#
# Notes:
# - "signals" mode is usually what you want for streak logic: upstream reruns
#   won't bloat history if signals are unchanged.

import argparse
import hashlib
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
    run_ts_utc = latest.get("run_ts_utc")
    stats_as_of_ts = latest.get("stats_as_of_ts")
    module = latest.get("module")
    ruleset_id = latest.get("ruleset_id")
    script_fingerprint = latest.get("script_fingerprint")

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

    items = h.get("items")
    if not isinstance(items, list):
        h["items"] = []

    h["schema_version"] = "dash_history_v2"
    return h


def canonical_signals_json(series_signals: Dict[str, str]) -> str:
    # stable ordering => stable hash
    return json.dumps(series_signals, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def signals_sig(series_signals: Dict[str, str]) -> str:
    s = canonical_signals_json(series_signals).encode("utf-8")
    return hashlib.sha1(s).hexdigest()  # audit-friendly, sufficient for dedupe


def dedupe_key_asof(module: str, ruleset_id: str, stats_as_of_ts: str) -> Tuple[str, str, str]:
    return (str(module), str(ruleset_id), str(stats_as_of_ts))


def dedupe_key_mod(module: str, ruleset_id: str) -> Tuple[str, str]:
    return (str(module), str(ruleset_id))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="dashboard_latest.json (render output)")
    ap.add_argument("--history", required=True, help="dashboard/history.json")
    ap.add_argument("--max-items", type=int, default=400)
    ap.add_argument(
        "--dedupe",
        choices=["as_of_ts", "signals"],
        default="as_of_ts",
        help="Deduplication mode: as_of_ts(default) or signals",
    )
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

    sig = signals_sig(series_signals)

    history = load_or_init_history(args.history)
    items_any = history.get("items", [])
    items: list = items_any if isinstance(items_any, list) else []

    new_item: Dict[str, Any] = {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "ruleset_id": ruleset_id,
        "script_fingerprint": script_fingerprint or "NA",
        "series_signals": series_signals,
        # extra audit field; safe for old renderers to ignore
        "series_signals_sig": sig,
    }

    action = "NA"

    if args.dedupe == "as_of_ts":
        # ---- dedupe/overwrite by (module, ruleset_id, stats_as_of_ts) ----
        k_new = dedupe_key_asof(module, ruleset_id, stats_as_of_ts)

        last_match_idx: Optional[int] = None
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            m = it.get("module")
            r = it.get("ruleset_id")
            s = it.get("stats_as_of_ts")
            if m and r and s and dedupe_key_asof(m, r, s) == k_new:
                last_match_idx = i

        if last_match_idx is None:
            items.append(new_item)
            action = "append"
        else:
            items[last_match_idx] = new_item
            action = f"overwrite@index={last_match_idx}"

    else:
        # ---- signals mode: only append when signals changed for same (module, ruleset_id) ----
        k_mod = dedupe_key_mod(module, ruleset_id)

        # find last item for this module+ruleset
        last_idx: Optional[int] = None
        last_sig: Optional[str] = None
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            m = it.get("module")
            r = it.get("ruleset_id")
            if not (m and r):
                continue
            if dedupe_key_mod(m, r) != k_mod:
                continue
            last_idx = i
            # prefer stored sig; fallback compute if missing
            it_sig = it.get("series_signals_sig")
            if isinstance(it_sig, str) and it_sig:
                last_sig = it_sig
            else:
                it_ss = it.get("series_signals")
                if isinstance(it_ss, dict) and it_ss:
                    try:
                        last_sig = signals_sig({str(k): str(v) for k, v in it_ss.items()})
                    except Exception:
                        last_sig = None

        if last_idx is None:
            items.append(new_item)
            action = "append(first_for_module_ruleset)"
        else:
            if last_sig is not None and last_sig == sig:
                items[last_idx] = new_item
                action = f"overwrite_last_same_signals@index={last_idx}"
            else:
                items.append(new_item)
                action = "append(signals_changed)"

    # cap
    if args.max_items > 0 and len(items) > args.max_items:
        items = items[-args.max_items :]

    history["items"] = items
    dump_json(args.history, history)

    print(f"OK: {action}. dedupe={args.dedupe}. total_items={len(items)}")


if __name__ == "__main__":
    main()