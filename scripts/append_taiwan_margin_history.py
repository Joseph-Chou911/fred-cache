#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append / seed taiwan_margin_cache/history.json from latest.json

Rules:
- If history missing or empty: seed by latest.series[market].rows (descending dates)
- Else: append only latest data_date for each market (if present)
- Dedup key: (market, data_date). If exists, replace the LAST match.
- Keep max_items (overall across markets).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


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
    if not os.path.exists(path):
        return {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": now_utc_iso(), "items": []}
    try:
        obj = read_json(path)
        if not isinstance(obj, dict) or "items" not in obj or not isinstance(obj["items"], list):
            return {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": now_utc_iso(), "items": []}
        return obj
    except Exception:
        return {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": now_utc_iso(), "items": []}


def upsert(items: List[Dict[str, Any]], new_item: Dict[str, Any]) -> None:
    key = (new_item.get("market"), new_item.get("data_date"))
    last_idx = None
    for i, it in enumerate(items):
        if (it.get("market"), it.get("data_date")) == key:
            last_idx = i
    if last_idx is not None:
        items[last_idx] = new_item
    else:
        items.append(new_item)


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

    # detect empty history => seed from latest.rows
    if len(items) == 0:
        for market in ("TWSE", "TPEX"):
            s = (latest.get("series") or {}).get(market) or {}
            rows = s.get("rows") or []
            # seed all rows (already sorted desc in fetch)
            for row in rows:
                if not row.get("date") or row.get("balance_yi") is None:
                    continue
                upsert(items, make_item(run_ts, market, s, row))
    else:
        # append only latest day per market
        for market in ("TWSE", "TPEX"):
            s = (latest.get("series") or {}).get(market) or {}
            dd = s.get("data_date")
            rows = s.get("rows") or []
            if not dd or not rows:
                continue
            top = rows[0]
            if top.get("date") != dd:
                # safety: do not append if mismatch
                continue
            if top.get("balance_yi") is None:
                continue
            upsert(items, make_item(run_ts, market, s, top))

    # keep only last max_items by data_date then run_ts
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