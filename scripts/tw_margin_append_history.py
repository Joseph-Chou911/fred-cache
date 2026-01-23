#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_HISTORY = "taiwan_margin_financing_history_v1"


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


def _history_items_map(items: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    m: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for it in items:
        market = str(it.get("market", "")).strip()
        data_date = str(it.get("data_date", "")).strip()
        if not market or not data_date:
            continue
        m[(market, data_date)] = it
    return m


def _sorted_items(m: Dict[Tuple[str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    # sort by market then date desc (stable, deterministic)
    keys = sorted(m.keys(), key=lambda k: (k[0], k[1]), reverse=False)
    # within market we want date desc, so rebuild per market
    out: List[Dict[str, Any]] = []
    by_market: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for (mk, dd), it in m.items():
        by_market.setdefault(mk, []).append((dd, it))
    for mk in sorted(by_market.keys()):
        rows = sorted(by_market[mk], key=lambda x: x[0], reverse=True)
        out.extend([it for _, it in rows])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = args.outdir
    latest_path = os.path.join(outdir, "latest.json")
    hist_path = os.path.join(outdir, "history.json")

    latest = _read_json(latest_path)
    if not latest or "series" not in latest:
        raise RuntimeError("latest.json 不存在或格式不正確")

    hist = _read_json(hist_path)
    if not hist:
        hist = {
            "schema_version": SCHEMA_HISTORY,
            "generated_at_utc": now_utc_iso(),
            "items": [],
        }

    items: List[Dict[str, Any]] = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    now_ts = now_utc_iso()
    m = _history_items_map(items)

    # Determine whether each market needs seeding
    existing_dates_by_market: Dict[str, set] = {}
    for (mk, dd) in m.keys():
        existing_dates_by_market.setdefault(mk, set()).add(dd)

    for market, s in latest["series"].items():
        source = s.get("source")
        source_url = s.get("source_url")
        rows = s.get("rows") or []
        if not isinstance(rows, list):
            rows = []

        existing_dates = existing_dates_by_market.get(market, set())

        # Seed rule (ONLY ONCE):
        # If market has ZERO existing dates in history AND latest.rows has data -> seed all rows.
        if len(existing_dates) == 0 and len(rows) > 0:
            for r in rows:
                dd = r.get("date")
                if not dd:
                    continue
                it = {
                    "run_ts_utc": now_ts,
                    "market": market,
                    "source": source,
                    "source_url": source_url,
                    "data_date": dd,
                    "balance_yi": r.get("balance_yi"),
                    "chg_yi": r.get("chg_yi"),
                }
                m[(market, dd)] = it
            existing_dates_by_market[market] = {r.get("date") for r in rows if r.get("date")}
            continue

        # Normal daily append/replace: only touch the newest row (if any)
        if len(rows) > 0:
            newest = rows[0]
            dd = newest.get("date")
            if dd:
                it = {
                    "run_ts_utc": now_ts,
                    "market": market,
                    "source": source,
                    "source_url": source_url,
                    "data_date": dd,
                    "balance_yi": newest.get("balance_yi"),
                    "chg_yi": newest.get("chg_yi"),
                }
                # replace-or-insert by (market, data_date)
                m[(market, dd)] = it

    out_items = _sorted_items(m)
    out = {
        "schema_version": SCHEMA_HISTORY,
        "generated_at_utc": now_ts,
        "items": out_items,
    }
    _write_json(hist_path, out)


if __name__ == "__main__":
    main()