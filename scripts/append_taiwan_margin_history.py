#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Append / Seed taiwan_margin_cache/history.json from latest.json.

Rules:
- If history missing or empty -> seed ALL latest.rows for each market (bulk seed).
- Else -> append only the latest day row (rows[0]) for each market.
- Deduplicate by (market, data_date): keep LAST (newest run replaces older).
- Keep at most --max_items newest items by run_ts_utc order after dedup (safe).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _history_items(obj: Any) -> List[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return []
    items = obj.get("items")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return []


def _make_item(run_ts_utc: str, market: str, source: str, source_url: str, row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_ts_utc": run_ts_utc,
        "market": market,
        "source": source,
        "source_url": source_url,
        "data_date": row.get("date"),
        "balance_yi": row.get("balance_yi"),
        "chg_yi": row.get("chg_yi"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=800)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    if not isinstance(latest, dict) or "series" not in latest:
        raise SystemExit("latest.json 格式錯誤或缺 series")

    hist = _read_json(args.history)
    items = _history_items(hist)
    history_is_empty = len(items) == 0

    run_ts_utc = now_utc_iso()

    new_items: List[Dict[str, Any]] = []
    series = latest.get("series", {})

    for market in ["TWSE", "TPEX"]:
        s = series.get(market, {})
        source = s.get("source", "NA")
        source_url = s.get("source_url", "NA")
        rows = s.get("rows", [])
        if not isinstance(rows, list) or len(rows) == 0:
            # no append for this market
            continue

        if history_is_empty:
            # seed ALL rows (bulk)
            for r in rows:
                if isinstance(r, dict) and r.get("date") is not None:
                    new_items.append(_make_item(run_ts_utc, market, source, source_url, r))
        else:
            # append only latest row
            r0 = rows[0]
            if isinstance(r0, dict) and r0.get("date") is not None:
                new_items.append(_make_item(run_ts_utc, market, source, source_url, r0))

    merged = items + new_items

    # Dedup by (market, data_date): keep LAST occurrence
    dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []
    for it in merged:
        m = it.get("market")
        d = it.get("data_date")
        if not m or not d:
            continue
        key = (str(m), str(d))
        if key not in dedup:
            order.append(key)
        dedup[key] = it

    # preserve original order, but with last write wins
    out_items = [dedup[k] for k in order if k in dedup]

    # If too many, keep tail (most recent appended are at end)
    if len(out_items) > args.max_items:
        out_items = out_items[-args.max_items :]

    out = {
        "schema_version": "taiwan_margin_financing_history_v1",
        "generated_at_utc": run_ts_utc,
        "items": out_items,
    }

    _write_json(args.history, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())