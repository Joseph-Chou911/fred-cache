#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from Bank of Taiwan (BOT) daily CSV.

Source:
- Daily CSV: https://rate.bot.com.tw/xrt/flcsv/0/YYYY-MM-DD

Output:
- fx_cache/latest.json
- fx_cache/history.json (append/dedupe by date)

Strict mode (default ON):
- If cannot produce valid USD spot_buy/spot_sell/mid within max_back => exit 1.
- If spot_buy > spot_sell:
  - try deterministic swap; if swap fixes sanity => accept + mark sanity_swapped=true
  - else => treat as parse failure and continue backtracking; if none valid => exit 1
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BOT_DAILY_CSV = "https://rate.bot.com.tw/xrt/flcsv/0/{date}"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _dump_json(path: str, obj: Any) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _today_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def _try_decode(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp950"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="replace")


def _to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x.replace(",", ""))
    except Exception:
        return None


def _find_idx_exact_or_contains(header: List[str], candidates: List[str]) -> Optional[int]:
    """
    Find column index by:
    1) exact match
    2) substring contains
    Candidates ordered by priority.
    """
    h = [c.strip() for c in header]
    # exact first
    for key in candidates:
        for i, col in enumerate(h):
            if col == key:
                return i
    # contains second
    for key in candidates:
        for i, col in enumerate(h):
            if key in col:
                return i
    return None


def _parse_bot_csv(text: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse BOT CSV and return USD spot quote.

    Returns:
      (usd_row or None, audit dict)
    audit includes:
      header, idx_map, parse_error, sanity_swapped, currency_label
    """
    audit: Dict[str, Any] = {
        "header": None,
        "idx_map": None,
        "parse_error": None,
        "sanity_swapped": False,
        "currency_label": None,
    }

    sio = StringIO(text)
    reader = csv.reader(sio)
    rows = list(reader)
    if not rows or len(rows) < 2:
        audit["parse_error"] = "CSV_EMPTY_OR_TOO_SHORT"
        return None, audit

    header = [h.strip() for h in rows[0] if h is not None]
    audit["header"] = header

    # BOT flcsv headers are typically:
    # 幣別, 現金買入, 現金賣出, 即期買入, 即期賣出, ...
    idx_ccy = _find_idx_exact_or_contains(header, ["幣別", "Currency"])
    # IMPORTANT: avoid matching 現金買入/現金賣出
    idx_spot_buy = _find_idx_exact_or_contains(header, ["即期買入", "Spot Buying"])
    idx_spot_sell = _find_idx_exact_or_contains(header, ["即期賣出", "Spot Selling"])

    audit["idx_map"] = {
        "ccy": idx_ccy,
        "spot_buy": idx_spot_buy,
        "spot_sell": idx_spot_sell,
    }

    if idx_ccy is None or idx_spot_buy is None or idx_spot_sell is None:
        audit["parse_error"] = f"HEADER_MISSING idx_ccy={idx_ccy} idx_spot_buy={idx_spot_buy} idx_spot_sell={idx_spot_sell}"
        return None, audit

    usd_row: Optional[Dict[str, Any]] = None
    usd_label: Optional[str] = None

    for r in rows[1:]:
        if not r:
            continue
        ccy = (r[idx_ccy] if idx_ccy < len(r) else "").strip()
        if not ccy:
            continue
        if "USD" in ccy:
            usd_label = ccy
            spot_buy = _to_float(r[idx_spot_buy] if idx_spot_buy < len(r) else "")
            spot_sell = _to_float(r[idx_spot_sell] if idx_spot_sell < len(r) else "")
            usd_row = {"currency": ccy, "spot_buy": spot_buy, "spot_sell": spot_sell}
            break

    audit["currency_label"] = usd_label

    if not usd_row:
        audit["parse_error"] = "USD_ROW_NOT_FOUND"
        return None, audit

    if usd_row["spot_buy"] is None or usd_row["spot_sell"] is None:
        audit["parse_error"] = "USD_VALUES_MISSING"
        return None, audit

    # Sanity: bank buy <= bank sell
    buy = float(usd_row["spot_buy"])
    sell = float(usd_row["spot_sell"])
    if buy > sell:
        # deterministic fix attempt: swap if it resolves sanity
        if sell <= buy:
            # After swap: new_buy = sell, new_sell = buy => should satisfy new_buy <= new_sell (always true here)
            usd_row["spot_buy"], usd_row["spot_sell"] = usd_row["spot_sell"], usd_row["spot_buy"]
            audit["sanity_swapped"] = True
        # re-check after swap
        buy2 = float(usd_row["spot_buy"])
        sell2 = float(usd_row["spot_sell"])
        if buy2 > sell2:
            audit["parse_error"] = f"SANITY_FAIL buy_gt_sell_after_swap buy={buy2} sell={sell2}"
            return None, audit

    return usd_row, audit


def _fetch_for_date(session: requests.Session, date_str: str, timeout: int) -> Tuple[int, bytes, Optional[str], str]:
    url = BOT_DAILY_CSV.format(date=date_str)
    try:
        resp = session.get(url, headers={"User-Agent": UA}, timeout=timeout)
        return resp.status_code, resp.content, None, url
    except Exception as e:
        return 0, b"", str(e), url


def _load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "fx_usdtwd_history_v1", "items": []}
    try:
        obj = _load_json(path)
        if isinstance(obj, dict) and obj.get("schema_version") == "fx_usdtwd_history_v1" and isinstance(obj.get("items"), list):
            return obj
    except Exception:
        pass
    return {"schema_version": "fx_usdtwd_history_v1", "items": []}


def _upsert_history(history: Dict[str, Any], item: Dict[str, Any]) -> None:
    items = history.get("items", [])
    if not isinstance(items, list):
        items = []
    by_date: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("date"), str):
            by_date[it["date"]] = it
    by_date[item["date"]] = item
    history["items"] = [by_date[k] for k in sorted(by_date.keys())]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--strict", action="store_true", help="Enable strict fail (default).")
    ap.add_argument("--no-strict", action="store_true", help="Disable strict fail (debug only).")
    args = ap.parse_args()

    strict = True
    if args.no_strict:
        strict = False
    if args.strict:
        strict = True

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    local_now = _today_local(args.tz)
    d0 = local_now.date()

    session = requests.Session()

    chosen_date: Optional[str] = None
    chosen_url: Optional[str] = None
    status_code: int = 0
    http_err: Optional[str] = None

    usd_row: Optional[Dict[str, Any]] = None
    audit_last: Dict[str, Any] = {}

    for i in range(max(args.max_back, 1)):
        d = d0 - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        sc, content, err, url = _fetch_for_date(session, date_str, args.timeout)

        status_code = sc
        chosen_url = url
        http_err = err

        if sc != 200 or not content:
            continue

        text = _try_decode(content)
        row, aud = _parse_bot_csv(text)
        audit_last = aud

        if row is not None:
            usd_row = row
            chosen_date = date_str
            break

    spot_buy = usd_row.get("spot_buy") if usd_row else None
    spot_sell = usd_row.get("spot_sell") if usd_row else None
    mid: Optional[float] = None
    if spot_buy is not None and spot_sell is not None:
        mid = (float(spot_buy) + float(spot_sell)) / 2.0

    latest = {
        "schema_version": "fx_usdtwd_latest_v1",
        "generated_at_utc": now_utc,
        "source": "BOT",
        "source_url": chosen_url,
        "data_date": chosen_date,
        "usd_twd": {"spot_buy": spot_buy, "spot_sell": spot_sell, "mid": mid},
        "raw": {
            "currency_label": audit_last.get("currency_label"),
            "row": usd_row,
            "parse_error": audit_last.get("parse_error"),
            "header": audit_last.get("header"),
            "idx_map": audit_last.get("idx_map"),
            "sanity_swapped": bool(audit_last.get("sanity_swapped", False)),
        },
        "http": {"status_code": status_code, "error": http_err},
    }
    _dump_json(args.latest_out, latest)

    if chosen_date and mid is not None:
        history = _load_history(args.history)
        _upsert_history(
            history,
            {
                "date": chosen_date,
                "mid": mid,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
                "source_url": chosen_url,
            },
        )
        _dump_json(args.history, history)

    if strict:
        if not chosen_date or spot_buy is None or spot_sell is None or mid is None:
            return 1
        if float(spot_buy) > float(spot_sell):
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())