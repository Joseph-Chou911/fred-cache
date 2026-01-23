#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": _utc_now_z(), "items": []}
    try:
        obj = _read_json(path)
        if not isinstance(obj, dict):
            raise ValueError("history is not dict")
        if "items" not in obj or not isinstance(obj["items"], list):
            obj["items"] = []
        if obj.get("schema_version") != "taiwan_margin_financing_history_v1":
            # 不強制中斷，避免你舊檔壞掉就卡住
            obj["schema_version"] = "taiwan_margin_financing_history_v1"
        return obj
    except Exception:
        return {"schema_version": "taiwan_margin_financing_history_v1", "generated_at_utc": _utc_now_z(), "items": []}


def _key(item: Dict[str, Any]) -> Tuple[str, str]:
    # 用 market + data_date 去重（這是你每日一筆的實際主鍵）
    return (str(item.get("market") or ""), str(item.get("data_date") or ""))


def _count_market_items(items: List[Dict[str, Any]], market: str) -> int:
    m = market.upper()
    return sum(1 for it in items if str(it.get("market", "")).upper() == m)


def _seed_from_latest(latest: Dict[str, Any], market: str) -> List[Dict[str, Any]]:
    series = (latest.get("series") or {}).get(market, {})
    rows = series.get("rows") or []
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = r.get("date")
        if not d:
            continue
        out.append(
            {
                "run_ts_utc": latest.get("generated_at_utc") or _utc_now_z(),
                "market": market,
                "source": series.get("source"),
                "source_url": series.get("source_url"),
                "data_date": d,
                "balance_yi": r.get("balance_yi"),
                "chg_yi": r.get("chg_yi"),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--seed_min_rows", type=int, default=21, help="history 太短時，以 latest.rows 補種的最低交易日筆數門檻")
    ap.add_argument("--max_items", type=int, default=1200)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    hist = _load_history(args.history)
    items: List[Dict[str, Any]] = hist.get("items", [])

    # 1) 若 history 太短：用 latest.rows 一次補滿（每市場各自判定）
    for market in ["TWSE", "TPEX"]:
        if _count_market_items(items, market) < args.seed_min_rows:
            seed_items = _seed_from_latest(latest, market)
            # 只在 seed_items 本身足夠時才補，避免把空 rows 寫進 history
            if len(seed_items) >= args.seed_min_rows:
                items.extend(seed_items)

    # 2) 永遠再寫入「最新日」一筆（可覆蓋同日）
    run_ts = latest.get("generated_at_utc") or _utc_now_z()
    series = latest.get("series") or {}
    for market in ["TWSE", "TPEX"]:
        s = series.get(market) or {}
        data_date = s.get("data_date")
        rows = s.get("rows") or []
        if not data_date or not rows:
            continue
        # 找到 data_date 那一列
        row0 = None
        for r in rows:
            if r.get("date") == data_date:
                row0 = r
                break
        if not row0:
            row0 = rows[0]
        items.append(
            {
                "run_ts_utc": run_ts,
                "market": market,
                "source": s.get("source"),
                "source_url": s.get("source_url"),
                "data_date": data_date,
                "balance_yi": row0.get("balance_yi"),
                "chg_yi": row0.get("chg_yi"),
            }
        )

    # 3) 去重：同 (market, data_date) 只留最後一筆（rerun 覆蓋）
    dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []
    for it in items:
        k = _key(it)
        if k not in dedup:
            order.append(k)
        dedup[k] = it  # 後來覆蓋先前

    merged = [dedup[k] for k in order if k[0] and k[1]]

    # 4) 裁切：保留最後 max_items（但仍維持 market/date 混合序）
    if len(merged) > args.max_items:
        merged = merged[-args.max_items :]

    hist["generated_at_utc"] = run_ts
    hist["items"] = merged
    _write_json(args.history, hist)


if __name__ == "__main__":
    main()