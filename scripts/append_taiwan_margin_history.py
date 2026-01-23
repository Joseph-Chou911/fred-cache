#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
append_taiwan_margin_history.py

- Reads latest.json (which contains per-market rows)
- Maintains history.json:
  {
    "schema_version": "...",
    "items": {
      "TWSE": [{"date": "...", "margin_balance_100m": ...}, ...],
      "TPEX": [...]
    }
  }
- Dedup by (market, date): keep the newest occurrence.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def dedup_by_date(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for r in rows:
        d = r.get("date")
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(r)
    return out


def sort_desc(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: str(r.get("date") or ""), reverse=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=400)
    args = ap.parse_args()

    latest = load_json(args.latest)
    if not latest or "series" not in latest:
        raise SystemExit("latest.json schema mismatch: missing series")

    hist = load_json(args.history)
    if not hist:
        hist = {
            "schema_version": "taiwan_margin_financing_history_v1",
            "generated_at_utc": None,
            "items": {"TWSE": [], "TPEX": []},
        }

    for mkt in ["TWSE", "TPEX"]:
        new_rows = latest["series"].get(mkt, {}).get("rows", []) or []
        old_rows = hist.get("items", {}).get(mkt, []) or []

        combined = new_rows + old_rows
        combined = sort_desc(dedup_by_date(sort_desc(combined)))
        combined = combined[: int(args.max_items)]

        hist["items"][mkt] = combined

    hist["generated_at_utc"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    write_json(args.history, hist)


if __name__ == "__main__":
    main()