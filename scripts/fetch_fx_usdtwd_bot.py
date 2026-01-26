#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from Bank of Taiwan (BOT) CSV (single request per run).

Why this version:
- The per-day endpoint /xrt/flcsv/0/YYYY-MM-DD may not exist on weekends/holidays,
  and "today" file may not be published yet at your run time.
- Use the USD 3-month CSV endpoint instead:
  https://rate.bot.com.tw/xrt/flcsv/0/L3M/USD/1
  which includes explicit dates (YYYYMMDD). We take the latest available row.

Output:
- fx_cache/latest.json
- fx_cache/history.json (append/dedupe by date)

Strict mode:
- If --strict is set, exit non-zero unless:
  * data_date exists
  * spot_buy and spot_sell exist
  * spot_sell >= spot_buy (sanity check)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BOT_USD_L3M_CSV = "https://rate.bot.com.tw/xrt/flcsv/0/L3M/USD/1"


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


def _yyyymmdd_to_yyyy_mm_dd(s: str) -> Optional[str]:
    s = (s or "").strip()
    if not re.fullmatch(r"\d{8}", s):
        return None
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "fx_usdtwd_history_v1", "items": []}
    try:
        obj = _load_json(path)
        if (
            isinstance(obj, dict)
            and obj.get("schema_version") == "fx_usdtwd_history_v1"
            and isinstance(obj.get("items"), list)
        ):
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


def _fetch(session: requests.Session, url: str, timeout: int) -> Tuple[int, bytes, Optional[str]]:
    try:
        resp = session.get(url, headers={"User-Agent": UA}, timeout=timeout)
        return resp.status_code, resp.content, None
    except Exception as e:
        return 0, b"", str(e)


def _parse_usd_l3m_csv(text: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse BOT L3M/USD/1 CSV.

    Expected common row (no header):
      YYYYMMDD,USD,本行買入,<cash_buy>,<spot_buy>,本行賣出,<cash_sell>,<spot_sell>

    Return:
      (parsed, dbg)
    parsed schema:
      {
        "data_date": "YYYY-MM-DD",
        "spot_buy": float|None,
        "spot_sell": float|None,
        "cash_buy": float|None,
        "cash_sell": float|None,
        "raw_row": [...],
      }
    """
    dbg: Dict[str, Any] = {"format": "unknown", "reason": "NA"}

    rows = list(csv.reader(StringIO(text)))
    if not rows:
        dbg["reason"] = "csv_empty"
        return None, dbg

    # Some variants might include a header row; detect by first cell not being YYYYMMDD.
    # We will scan rows and pick the FIRST valid data row (assumed latest).
    for r in rows:
        if not r or len(r) < 5:
            continue

        first = (r[0] or "").strip()
        date_iso = _yyyymmdd_to_yyyy_mm_dd(first)
        if not date_iso:
            continue

        # currency field may be at r[1] for this endpoint
        ccy = (r[1] if len(r) > 1 else "").strip()
        if ccy and "USD" not in ccy:
            # Should be USD for this endpoint, but be defensive
            continue

        # Common pattern length >= 8:
        # [0]=date, [1]=USD, [2]=buy_label, [3]=cash_buy, [4]=spot_buy, [5]=sell_label, [6]=cash_sell, [7]=spot_sell
        cash_buy = _to_float(r[3]) if len(r) > 3 else None
        spot_buy = _to_float(r[4]) if len(r) > 4 else None
        cash_sell = _to_float(r[6]) if len(r) > 6 else None
        spot_sell = _to_float(r[7]) if len(r) > 7 else None

        dbg["format"] = "l3m_usd_row"
        dbg["reason"] = "matched_yyyymmdd_row"
        dbg["row_len"] = len(r)

        return (
            {
                "data_date": date_iso,
                "cash_buy": cash_buy,
                "cash_sell": cash_sell,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
                "raw_row": r,
            },
            dbg,
        )

    dbg["reason"] = "no_valid_data_row_found"
    dbg["rows_preview"] = rows[:3]
    return None, dbg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 1) if spot rates are missing/invalid.")
    ap.add_argument("--source-url", default=BOT_USD_L3M_CSV)
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    session = requests.Session()
    status_code, content, http_err = _fetch(session, args.source_url, args.timeout)

    chosen_url = args.source_url
    parsed: Optional[Dict[str, Any]] = None
    parse_dbg: Dict[str, Any] = {}

    if status_code == 200 and content:
        text = _try_decode(content)
        parsed, parse_dbg = _parse_usd_l3m_csv(text)
    else:
        parse_dbg = {"format": "unknown", "reason": "http_not_200_or_empty"}

    data_date = parsed.get("data_date") if parsed else None
    spot_buy = parsed.get("spot_buy") if parsed else None
    spot_sell = parsed.get("spot_sell") if parsed else None

    mid: Optional[float] = None
    if spot_buy is not None and spot_sell is not None:
        mid = (spot_buy + spot_sell) / 2.0

    strict_ok = bool(
        data_date
        and spot_buy is not None
        and spot_sell is not None
        and mid is not None
        and spot_sell >= spot_buy
    )

    latest = {
        "schema_version": "fx_usdtwd_latest_v1",
        "generated_at_utc": now_utc,
        "source": "BOT",
        "source_url": chosen_url,
        "data_date": data_date,
        "usd_twd": {
            "spot_buy": spot_buy,
            "spot_sell": spot_sell,
            "mid": mid,
        },
        "raw": {
            "parsed": parsed,
            "parse_dbg": parse_dbg,
        },
        "http": {"status_code": status_code, "error": http_err},
    }
    _dump_json(args.latest_out, latest)

    if strict_ok:
        history = _load_history(args.history)
        _upsert_history(
            history,
            {
                "date": data_date,
                "mid": mid,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
                "source_url": chosen_url,
            },
        )
        _dump_json(args.history, history)

    print(
        "FX(BOT:L3M/USD/1) strict_ok={ok} date={date} spot_buy={b} spot_sell={s} mid={m} http={http} err={err} url={url}".format(
            ok=str(strict_ok).lower(),
            date=data_date or "NA",
            b="None" if spot_buy is None else f"{spot_buy:.6f}",
            s="None" if spot_sell is None else f"{spot_sell:.6f}",
            m="None" if mid is None else f"{mid:.6f}",
            http=status_code,
            err=(http_err or "NA"),
            url=(chosen_url or "NA"),
        )
    )

    if args.strict and not strict_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())