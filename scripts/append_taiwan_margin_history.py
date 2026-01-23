#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append taiwan margin latest.json into history.json with dedup by (market, data_date).

History schema:
{
  "schema_version": "taiwan_margin_financing_history_v1",
  "items": [
    {
      "run_ts_utc": "...",
      "market": "TWSE"|"TPEX",
      "source": "...",
      "source_url": "...",
      "data_date": "YYYY-MM-DD",
      "balance_yi": <float>,
      "chg_yi": <float>
    }, ...
  ]
}
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def pick_latest_row(rows: List[Dict[str, Any]], data_date: Optional[str]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    if data_date:
        for r in rows:
            if r.get("date") == data_date:
                return r
    return rows[0]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=600)
    args = ap.parse_args()

    latest = read_json(args.latest)
    if not latest or "series" not in latest:
        raise RuntimeError("latest.json schema not found or invalid")

    hist = read_json(args.history)
    if not hist:
        hist = {"schema_version": "taiwan_margin_financing_history_v1", "items": []}

    items: List[Dict[str, Any]] = hist.get("items", [])
    run_ts = utc_now_iso()

    for market in ["TWSE", "TPEX"]:
        s = latest["series"].get(market, {})
        data_date = s.get("data_date")
        rows = s.get("rows", [])
        row0 = pick_latest_row(rows, data_date)
        if not data_date or not row0:
            # cannot append without reliable date+row
            continue

        new_item = {
            "run_ts_utc": run_ts,
            "market": market,
            "source": s.get("source"),
            "source_url": s.get("source_url"),
            "data_date": data_date,
            "balance_yi": row0.get("balance_yi"),
            "chg_yi": row0.get("chg_yi"),
        }

        # dedup: replace last match of (market, data_date)
        key_market = market
        key_date = data_date
        replaced = False
        for i in range(len(items) - 1, -1, -1):
            if items[i].get("market") == key_market and items[i].get("data_date") == key_date:
                items[i] = new_item
                replaced = True
                break
        if not replaced:
            items.append(new_item)

    # trim
    if len(items) > args.max_items:
        items = items[-args.max_items:]

    hist["items"] = items
    write_json(args.history, hist)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())