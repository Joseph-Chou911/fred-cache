#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# append_dashboard_history.py (DAILY bucket)
# - Reads dashboard_latest.json (renderer output)
# - Appends/Upserts into dashboard/history.json with DAILY bucket_date (Asia/Taipei)
#
# Key (DAILY):
#   (module, ruleset_id, bucket_date)
#
# Behavior:
# - If same key exists, overwrite it (so re-runs in same day do NOT increase streak)
# - Otherwise append
# - Keep max-items (default 400)
#
# Schema:
#   dash_history_v3: items[*] include bucket_date + audit keys

import argparse
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List


DEFAULT_TZ = "Asia/Taipei"


def _get_tzinfo(tz_name: str):
    try:
        from zoneinfo import ZoneInfo  # type: ignore
        return ZoneInfo(tz_name)
    except Exception:
        if tz_name == "Asia/Taipei":
            return timezone(timedelta(hours=8))
        return timezone.utc


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts2 = ts.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(ts2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def bucket_date_from_stats_asof(stats_as_of_ts: Optional[str], tz_name: str, run_ts_utc: datetime) -> str:
    tzinfo = _get_tzinfo(tz_name)
    dt = parse_iso(stats_as_of_ts)
    if dt is None:
        dt = run_ts_utc
    return dt.astimezone(tzinfo).date().isoformat()


def pick_meta(latest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expect renderer output schema:
      {
        "meta": {...},
        "rows": [...],
        "series_signals": {...}
      }
    But keep some compatibility fallbacks.
    """
    m = latest.get("meta") if isinstance(latest.get("meta"), dict) else {}

    return {
        "run_ts_utc": m.get("run_ts_utc") or latest.get("run_ts_utc"),
        "stats_as_of_ts": m.get("stats_as_of_ts") or latest.get("stats_as_of_ts"),
        "module": m.get("module") or latest.get("module"),
        "ruleset_id": m.get("ruleset_id") or latest.get("ruleset_id"),
        "script_fingerprint": m.get("script_fingerprint") or latest.get("script_fingerprint"),
        "tz": m.get("tz") or latest.get("tz"),
        "bucket_date": m.get("bucket_date") or latest.get("bucket_date"),
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
        return {"schema_version": "dash_history_v3", "items": []}

    try:
        h = load_json(path)
    except Exception:
        return {"schema_version": "dash_history_v3", "items": []}

    if not isinstance(h, dict):
        return {"schema_version": "dash_history_v3", "items": []}

    if "items" not in h or not isinstance(h["items"], list):
        h["items"] = []

    # Upgrade schema_version if missing/older; keep items as-is
    sv = h.get("schema_version")
    if not isinstance(sv, str) or not sv:
        h["schema_version"] = "dash_history_v3"

    return h


def upsert_daily_item(items: List[Dict[str, Any]], new_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Upsert by (module, ruleset_id, bucket_date).
    If found, overwrite existing (keep position or replace by rewriting).
    """
    k_module = new_item.get("module")
    k_ruleset = new_item.get("ruleset_id")
    k_bucket = new_item.get("bucket_date")

    out: List[Dict[str, Any]] = []
    replaced = False

    for it in items:
        if not isinstance(it, dict):
            continue
        if (
            it.get("module") == k_module
            and it.get("ruleset_id") == k_ruleset
            and it.get("bucket_date") == k_bucket
        ):
            out.append(new_item)
            replaced = True
        else:
            out.append(it)

    if not replaced:
        out.append(new_item)

    # sort by bucket_date asc, tie-break by run_ts_utc asc
    def _key(x: Dict[str, Any]):
        return (str(x.get("bucket_date", "")), str(x.get("run_ts_utc", "")))

    out.sort(key=_key)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="dashboard_latest.json (render output)")
    ap.add_argument("--history", required=True, help="dashboard/history.json")
    ap.add_argument("--max-items", type=int, default=400)
    ap.add_argument("--tz", default=DEFAULT_TZ)
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
    tz_name = meta.get("tz") or args.tz

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
        raise SystemExit("dashboard_latest.json meta missing: " + "/".join(missing))

    # derive bucket_date (authoritative: meta.bucket_date; else from stats_as_of_ts)
    bucket_date = meta.get("bucket_date")
    if not bucket_date:
        rt = parse_iso(run_ts_utc) or datetime.now(timezone.utc)
        bucket_date = bucket_date_from_stats_asof(stats_as_of_ts, tz_name, rt)

    series_signals = build_series_signals(latest)
    if not series_signals:
        raise SystemExit(
            "dashboard_latest.json missing series signals: need either series_signals{} or rows[].(series, signal_level)"
        )

    history = load_or_init_history(args.history)
    items = history.get("items", [])
    if not isinstance(items, list):
        items = []

    new_item = {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "ruleset_id": ruleset_id,
        "script_fingerprint": script_fingerprint,
        "tz": tz_name,
        "bucket_date": bucket_date,
        "series_signals": series_signals,
    }

    items2 = upsert_daily_item(items, new_item)

    # cap
    if args.max_items > 0 and len(items2) > args.max_items:
        items2 = items2[-args.max_items :]

    history["schema_version"] = "dash_history_v3"
    history["items"] = items2

    dump_json(args.history, history)
    print(f"OK: upserted daily history item. bucket_date={bucket_date} total_items={len(items2)}")


if __name__ == "__main__":
    main()