#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append / seed taiwan_margin_cache/history.json from latest.json

Rules (hardened):
- If history missing/invalid: start empty then seed.
- Seed rule:
  - If history has NO items for a market, seed that market from latest.series[market].rows (descending dates).
- Append rule:
  - For each market, append only latest data_date row, but DO NOT assume rows[0] matches data_date.
  - Find the row whose date == data_date.
- Dedup key: (market, data_date)
  - Upsert: replace existing key with the new item (new run_ts).
  - Final normalize: remove any accidental duplicates by keeping the latest run_ts per key.
- Keep max_items overall across markets (by (data_date, run_ts)).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_or_empty_history(path: str) -> Dict[str, Any]:
    base = {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": now_utc_iso(), "items": []}
    if not os.path.exists(path):
        return base
    try:
        obj = read_json(path)
        if not isinstance(obj, dict):
            return base
        items = obj.get("items")
        if not isinstance(items, list):
            return base
        return obj
    except Exception:
        return base


def make_item(run_ts_utc: str, market: str, series_obj: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_ts_utc": run_ts_utc,
        "market": market,
        "source": series_obj.get("source"),
        "source_url": series_obj.get("source_url"),
        "data_date": row.get("date"),
        "balance_yi": row.get("balance_yi"),
        "chg_yi": row.get("chg_yi"),
    }


def upsert(items: List[Dict[str, Any]], new_item: Dict[str, Any]) -> None:
    key = (new_item.get("market"), new_item.get("data_date"))
    # replace the first found; if duplicates exist, we'll normalize later anyway
    for i, it in enumerate(items):
        if (it.get("market"), it.get("data_date")) == key:
            items[i] = new_item
            return
    items.append(new_item)


def has_market(items: List[Dict[str, Any]], market: str) -> bool:
    for it in items:
        if it.get("market") == market:
            return True
    return False


def find_row_by_date(rows: List[Dict[str, Any]], dd: str) -> Dict[str, Any] | None:
    for r in rows:
        if isinstance(r, dict) and r.get("date") == dd:
            return r
    return None


def normalize_dedup_keep_latest(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enforce uniqueness by (market, data_date).
    If duplicates exist, keep the one with max run_ts_utc (string compare works for ISO Z).
    """
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for it in items:
        m = str(it.get("market") or "")
        d = str(it.get("data_date") or "")
        if not m or not d:
            continue
        k = (m, d)
        if k not in best:
            best[k] = it
        else:
            prev = best[k]
            if str(it.get("run_ts_utc") or "") >= str(prev.get("run_ts_utc") or ""):
                best[k] = it
    return list(best.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=800)
    args = ap.parse_args()

    latest = read_json(args.latest)
    hist = load_or_empty_history(args.history)

    run_ts = now_utc_iso()
    items: List[Dict[str, Any]] = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    series_all = latest.get("series") or {}

    # 1) Seed missing market (even when history is non-empty)
    for market in ("TWSE", "TPEX"):
        if not has_market(items, market):
            s = series_all.get(market) or {}
            rows = s.get("rows") or []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if not row.get("date") or row.get("balance_yi") is None:
                        continue
                    upsert(items, make_item(run_ts, market, s, row))

    # 2) Append only latest day per market (robust row pick)
    for market in ("TWSE", "TPEX"):
        s = series_all.get(market) or {}
        dd = s.get("data_date")
        rows = s.get("rows") or []
        if not dd or not isinstance(rows, list) or not rows:
            continue

        row = find_row_by_date([r for r in rows if isinstance(r, dict)], str(dd))
        if row is None:
            # safety: do not append if cannot find matching date row
            continue
        if row.get("balance_yi") is None:
            continue

        upsert(items, make_item(run_ts, market, s, row))

    # 3) Normalize duplicates defensively
    items = normalize_dedup_keep_latest(items)

    # 4) Keep only last max_items by (data_date, run_ts)
    def _k(it: Dict[str, Any]) -> Tuple[str, str]:
        return (str(it.get("data_date") or ""), str(it.get("run_ts_utc") or ""))

    items.sort(key=_k)  # ascending
    if len(items) > args.max_items:
        items = items[-args.max_items :]

    out = {
        "schema_version": "taiwan_margin_financing_history_v1",
        "generated_at_utc": run_ts,
        "items": items,
    }
    write_json(args.history, out)


if __name__ == "__main__":
    main()