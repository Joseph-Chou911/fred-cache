#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=800)
    args = ap.parse_args()

    latest = _read_json(args.latest) or {}
    hist = _read_json(args.history) or {"schema_version": "taiwan_margin_financing_history_v1", "items": []}

    items: List[Dict[str, Any]] = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    # 以 (market, data_date) 去重
    def key_of(it: Dict[str, Any]) -> Tuple[str, str]:
        return (str(it.get("market")), str(it.get("data_date")))

    existing = {key_of(it): i for i, it in enumerate(items) if it.get("market") and it.get("data_date")}

    series = latest.get("series", {})
    for market in ("TWSE", "TPEX"):
        s = series.get(market, {})
        data_date = s.get("data_date")
        rows = s.get("rows") or []
        if not data_date or not rows:
            # 沒資料就不寫入 history，避免污染
            continue

        # latest rows[0] = 最新日
        top = rows[0]
        record = {
            "run_ts_utc": latest.get("generated_at_utc", _utc_now_iso()),
            "market": market,
            "source": s.get("source"),
            "source_url": s.get("source_url"),
            "data_date": data_date,
            "financing_balance_bil": top.get("financing_balance_bil"),
            "financing_change_bil": top.get("financing_change_bil"),
        }

        k = (market, data_date)
        if k in existing:
            items[existing[k]] = record
        else:
            items.append(record)

    # 截斷長度（保留最新）
    if len(items) > args.max_items:
        items = items[-args.max_items :]

    hist["items"] = items
    hist["generated_at_utc"] = _utc_now_iso()
    _write_json(args.history, hist)


if __name__ == "__main__":
    main()