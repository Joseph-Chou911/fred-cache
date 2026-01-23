#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append taiwan margin financing history.

Key behavior:
- If history is empty OR missing a market, seed from latest.series[market].rows (all rows, not just latest day).
- Deduplicate by (market, data_date) keep the newest run_ts_utc.
- Keep max_items.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=400)
    args = ap.parse_args()

    latest = load_json(args.latest)
    if not latest or "series" not in latest:
        raise SystemExit("latest.json 缺少 series")

    hist = load_json(args.history)
    if not hist:
        hist = {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": now_utc_iso(), "items": []}

    items: List[Dict[str, Any]] = [x for x in hist.get("items", []) if isinstance(x, dict)]

    # 建索引：最後一次出現的位置（用於覆蓋）
    index: Dict[Tuple[str, str], int] = {}
    for i, it in enumerate(items):
        m = it.get("market")
        d = it.get("data_date")
        if isinstance(m, str) and isinstance(d, str):
            index[(m, d)] = i

    run_ts = now_utc_iso()

    def upsert_one(market: str, source: str, source_url: str, data_date: str, balance_yi: float, chg_yi: float | None) -> None:
        nonlocal items, index
        key = (market, data_date)
        obj = {
            "run_ts_utc": run_ts,
            "market": market,
            "source": source,
            "source_url": source_url,
            "data_date": data_date,
            "balance_yi": float(balance_yi),
            "chg_yi": float(chg_yi) if chg_yi is not None else None,
        }
        if key in index:
            items[index[key]] = obj
        else:
            items.append(obj)
            index[key] = len(items) - 1

    # 先判斷目前 history 是否已包含某市場的任何資料；若沒有就用 latest.rows 全量 seed
    existing_markets = set([it.get("market") for it in items if isinstance(it.get("market"), str)])

    for market in ("TWSE", "TPEX"):
        s = latest["series"].get(market, {})
        source = s.get("source", "NA")
        source_url = s.get("source_url", "NA")
        rows = s.get("rows", []) or []

        if market not in existing_markets and rows:
            # 種子：把 latest.rows 全塞進 history（你要求的）
            for r in rows:
                d = r.get("date")
                bal = r.get("balance_yi")
                chg = r.get("chg_yi", None)
                if isinstance(d, str) and isinstance(bal, (int, float)):
                    upsert_one(market, source, source_url, d, float(bal), float(chg) if isinstance(chg, (int, float)) else None)

        # 日常：至少 upsert 最新一筆（若有）
        if rows:
            r0 = rows[0]
            d0 = r0.get("date")
            bal0 = r0.get("balance_yi")
            chg0 = r0.get("chg_yi", None)
            if isinstance(d0, str) and isinstance(bal0, (int, float)):
                upsert_one(market, source, source_url, d0, float(bal0), float(chg0) if isinstance(chg0, (int, float)) else None)

    # 以日期排序（同市場先後不重要，但整體可讀性好）
    # 注意：這裡用字串排序 YYYY-MM-DD OK
    items.sort(key=lambda it: (it.get("market", ""), it.get("data_date", "")), reverse=True)

    # 截斷
    items = items[: args.max_items]

    hist["generated_at_utc"] = now_utc_iso()
    hist["items"] = items
    save_json(args.history, hist)


if __name__ == "__main__":
    main()