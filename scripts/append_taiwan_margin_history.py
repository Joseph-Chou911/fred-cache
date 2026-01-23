#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _key(item: Dict[str, Any]) -> Tuple[str, str]:
    # unique by (market, data_date)
    return (str(item.get("market")), str(item.get("data_date")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=400)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    series = latest.get("series", {})

    hist: Dict[str, Any]
    if os.path.exists(args.history):
        hist = _read_json(args.history)
        if hist.get("schema_version") != "taiwan_margin_financing_history_v1":
            # 若你曾用過舊 schema，直接重建（避免混亂）
            hist = {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": _utc_now_iso(), "items": []}
    else:
        hist = {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": _utc_now_iso(), "items": []}

    items: List[Dict[str, Any]] = [x for x in hist.get("items", []) if isinstance(x, dict)]

    # 既有索引
    idx: Dict[Tuple[str, str], int] = {}
    for i, it in enumerate(items):
        idx[_key(it)] = i

    run_ts = _utc_now_iso()

    def market_has_any(mkt: str) -> bool:
        return any(it.get("market") == mkt for it in items)

    # ✅ 逐 market seed：該市場在 history 沒有任何紀錄 → 用 latest.rows 一次補滿
    for mkt in ("TWSE", "TPEX"):
        s = series.get(mkt, {})
        rows = s.get("rows") or []
        if not rows:
            continue

        if not market_has_any(mkt):
            # seed all available rows (from latest snapshot)
            for r in rows:
                it = {
                    "run_ts_utc": run_ts,
                    "market": mkt,
                    "source": s.get("source"),
                    "source_url": s.get("source_url"),
                    "data_date": r.get("date"),
                    "balance_yi": r.get("balance_yi"),
                    "chg_yi": r.get("chg_yi"),
                }
                k = _key(it)
                if k in idx:
                    items[idx[k]] = it
                else:
                    idx[k] = len(items)
                    items.append(it)

        else:
            # normal append latest day only
            r0 = rows[0]
            it = {
                "run_ts_utc": run_ts,
                "market": mkt,
                "source": s.get("source"),
                "source_url": s.get("source_url"),
                "data_date": r0.get("date"),
                "balance_yi": r0.get("balance_yi"),
                "chg_yi": r0.get("chg_yi"),
            }
            k = _key(it)
            if k in idx:
                items[idx[k]] = it
            else:
                idx[k] = len(items)
                items.append(it)

    # sort by date desc within market, but keep markets mixed OK
    items = sorted(items, key=lambda x: (x.get("market", ""), x.get("data_date", "")), reverse=True)

    # cap
    if len(items) > args.max_items:
        items = items[: args.max_items]

    hist["generated_at_utc"] = _utc_now_iso()
    hist["items"] = items
    _write_json(args.history, hist)


if __name__ == "__main__":
    main()