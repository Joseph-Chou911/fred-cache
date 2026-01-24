#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from Bank of Taiwan (BOT) daily CSV.

Design goals:
- Deterministic, auditable, minimal fetch: 1 request per run.
- Persist history locally to compute ret1 / chg_5d without extra network calls.
- Weekend/holiday safe: backtrack date until data exists (max_back).
- Encoding tolerant: try utf-8-sig, then cp950.

Source:
- Daily CSV: https://rate.bot.com.tw/xrt/flcsv/0/YYYY-MM-DD

Output:
- fx_cache/latest.json
- fx_cache/history.json (append/dedupe by date)

Schema (latest):
{
  "schema_version": "fx_usdtwd_latest_v1",
  "generated_at_utc": "...Z",
  "source": "BOT",
  "source_url": "...",
  "data_date": "YYYY-MM-DD",
  "usd_twd": {
     "spot_buy": float|null,
     "spot_sell": float|null,
     "mid": float|null
  },
  "raw": { "currency_label": "...", "row": {...} },
  "http": { "status_code": int, "error": str|null }
}

Schema (history):
{
  "schema_version": "fx_usdtwd_history_v1",
  "items": [
     {"date":"YYYY-MM-DD","mid":float,"spot_buy":float,"spot_sell":float,"source_url":"..."}
  ]
}
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
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
    # last resort
    return b.decode("utf-8", errors="replace")


def _to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x.replace(",", ""))
    except Exception:
        return None


def _parse_bot_csv(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Return: (usd_row_dict, currency_label)
    BOT CSV columns typically include:
    幣別, 現金買入, 現金賣出, 即期買入, 即期賣出, ...
    Sometimes English headings appear depending on locale; we match by position.
    """
    sio = StringIO(text)
    reader = csv.reader(sio)
    rows = list(reader)
    if not rows or len(rows) < 2:
        return None, None

    header = [h.strip() for h in rows[0]]
    # Heuristic: identify indices by header keywords; fallback to common BOT layout
    def _find_idx(keys: List[str]) -> Optional[int]:
        for k in keys:
            for i, h in enumerate(header):
                if k in h:
                    return i
        return None

    idx_ccy = _find_idx(["幣別", "Currency"])
    idx_spot_buy = _find_idx(["即期買入", "Spot Buying", "SpotBuy"])
    idx_spot_sell = _find_idx(["即期賣出", "Spot Selling", "SpotSell"])

    # Fallback to known BOT layout if not found
    if idx_ccy is None:
        idx_ccy = 0
    if idx_spot_buy is None:
        idx_spot_buy = 3
    if idx_spot_sell is None:
        idx_spot_sell = 4

    usd_row: Optional[Dict[str, Any]] = None
    usd_label: Optional[str] = None

    for r in rows[1:]:
        if not r:
            continue
        ccy = (r[idx_ccy] if idx_ccy < len(r) else "").strip()
        if not ccy:
            continue

        # match USD row (possible: "美金 (USD)" or "USD" or includes "(USD)")
        if "USD" in ccy:
            usd_label = ccy
            spot_buy = _to_float(r[idx_spot_buy] if idx_spot_buy < len(r) else "")
            spot_sell = _to_float(r[idx_spot_sell] if idx_spot_sell < len(r) else "")
            usd_row = {
                "currency": ccy,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
            }
            break

    return usd_row, usd_label


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
    # if malformed, keep safe
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
    # sort ascending by date
    out = [by_date[k] for k in sorted(by_date.keys())]
    history["items"] = out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    local_now = _today_local(args.tz)
    # try "today" first; BOT often has data same day; if not, backtrack
    d0 = local_now.date()

    session = requests.Session()

    chosen_date: Optional[str] = None
    chosen_url: Optional[str] = None
    status_code: int = 0
    http_err: Optional[str] = None
    usd_row: Optional[Dict[str, Any]] = None
    usd_label: Optional[str] = None

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
        row, label = _parse_bot_csv(text)
        if row and row.get("spot_buy") is not None and row.get("spot_sell") is not None:
            usd_row = row
            usd_label = label
            chosen_date = date_str
            break

    mid: Optional[float] = None
    spot_buy = usd_row.get("spot_buy") if usd_row else None
    spot_sell = usd_row.get("spot_sell") if usd_row else None
    if spot_buy is not None and spot_sell is not None:
        mid = (spot_buy + spot_sell) / 2.0

    latest = {
        "schema_version": "fx_usdtwd_latest_v1",
        "generated_at_utc": now_utc,
        "source": "BOT",
        "source_url": chosen_url,
        "data_date": chosen_date,
        "usd_twd": {
            "spot_buy": spot_buy,
            "spot_sell": spot_sell,
            "mid": mid,
        },
        "raw": {
            "currency_label": usd_label,
            "row": usd_row,
        },
        "http": {"status_code": status_code, "error": http_err},
    }
    _dump_json(args.latest_out, latest)

    # Update history only if we got a valid mid
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())