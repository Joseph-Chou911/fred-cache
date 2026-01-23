#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Append + seed history for Taiwan margin financing.

Rules:
- If history file doesn't exist OR items is empty:
  => SEED using latest.series[MARKET].rows (ALL rows; newest->oldest)
- Otherwise:
  => append only the latest row (rows[0]) per market.

Dedup:
- Key = (market, data_date)
- Keep the LAST written item for the same key.

Outputs:
- taiwan_margin_cache/history.json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {
            "schema_version": "taiwan_margin_financing_history_v1",
            "generated_at_utc": _now_utc_iso(),
            "items": [],
        }
    try:
        obj = _read_json(path)
        if not isinstance(obj, dict):
            raise ValueError("history is not dict")
        if "items" not in obj or not isinstance(obj["items"], list):
            obj["items"] = []
        if "schema_version" not in obj:
            obj["schema_version"] = "taiwan_margin_financing_history_v1"
        return obj
    except Exception:
        # if corrupted, start fresh but keep safe
        return {
            "schema_version": "taiwan_margin_financing_history_v1",
            "generated_at_utc": _now_utc_iso(),
            "items": [],
        }


def _dedup_keep_last(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Replace last matching key (market, data_date)
    out: List[Dict[str, Any]] = []
    idx: Dict[Tuple[str, str], int] = {}
    for it in items:
        mkt = str(it.get("market", ""))
        dt = str(it.get("data_date", ""))
        if not mkt or not dt:
            # keep malformed too, but no dedup key
            out.append(it)
            continue
        key = (mkt, dt)
        if key in idx:
            out[idx[key]] = it
        else:
            idx[key] = len(out)
            out.append(it)
    return out


def _make_item(run_ts_utc: str, market: str, source: str, source_url: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    dt = row.get("date")
    bal = row.get("balance_yi")
    chg = row.get("chg_yi")
    if not dt or bal is None or chg is None:
        return None
    try:
        bal_f = float(bal)
        chg_f = float(chg)
    except Exception:
        return None
    return {
        "run_ts_utc": run_ts_utc,
        "market": market,
        "source": source,
        "source_url": source_url,
        "data_date": dt,
        "balance_yi": round(bal_f, 2),
        "chg_yi": round(chg_f, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=800)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    hist = _load_history(args.history)

    items: List[Dict[str, Any]] = hist.get("items", [])
    run_ts = _now_utc_iso()

    def _get_series(market: str) -> Dict[str, Any]:
        return (latest.get("series") or {}).get(market) or {}

    def _seed_or_append(market: str) -> List[Dict[str, Any]]:
        s = _get_series(market)
        source = s.get("source") or "NA"
        source_url = s.get("source_url") or "NA"
        rows = s.get("rows") or []
        out_new: List[Dict[str, Any]] = []
        if not isinstance(rows, list) or not rows:
            return out_new

        # seed if history empty
        if len(items) == 0:
            for r in rows:
                it = _make_item(run_ts, market, source, source_url, r)
                if it:
                    out_new.append(it)
        else:
            it = _make_item(run_ts, market, source, source_url, rows[0])
            if it:
                out_new.append(it)
        return out_new

    new_items: List[Dict[str, Any]] = []
    new_items.extend(_seed_or_append("TWSE"))
    new_items.extend(_seed_or_append("TPEX"))

    items2 = items + new_items
    items2 = _dedup_keep_last(items2)

    # Keep only last max_items (by insertion order). This is stable and audit-friendly.
    if len(items2) > args.max_items:
        items2 = items2[-args.max_items :]

    hist["generated_at_utc"] = run_ts
    hist["items"] = items2

    _write_json(args.history, hist)


if __name__ == "__main__":
    main()