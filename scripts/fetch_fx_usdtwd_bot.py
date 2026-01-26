#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from Bank of Taiwan (BOT) xrt page (HTML).

Why this version:
- L3M/USD/1 (history-series CSV) may lag behind the real-time board rate.
- The xrt page shows the *current* board rate with:
  - page date (YYYY/MM/DD)
  - quote time (YYYY/MM/DD HH:MM)
  - USD cash + spot buy/sell (spot shown with 2 decimals on the page)

Goal:
- 1 request per run (deterministic)
- Extract:
  * data_date (YYYY-MM-DD)
  * quote_time_local (YYYY-MM-DDTHH:MM:SS+08:00)
  * spot_buy, spot_sell (2-decimal as displayed)
- Write:
  * fx_cache/latest.json
  * fx_cache/history.json (upsert by date)

Backward compatibility:
- Accept legacy args: --tz, --max-back (ignored)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BOT_XRT_PAGE = "https://rate.bot.com.tw/xrt?Lang=zh-TW"


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


def _to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x.replace(",", ""))
    except Exception:
        return None


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


def _fetch(session: requests.Session, url: str, timeout: int) -> Tuple[int, str, Optional[str]]:
    try:
        resp = session.get(url, headers={"User-Agent": UA}, timeout=timeout)
        # BOT page is UTF-8 HTML
        resp.encoding = "utf-8"
        return resp.status_code, resp.text, None
    except Exception as e:
        return 0, "", str(e)


def _parse_xrt_html(html: str, tz_name: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Extract:
    - page_date: 'YYYY/MM/DD' from header
    - quote_time: 'YYYY/MM/DD HH:MM' from "牌價最新掛牌時間"
    - USD spot_buy/spot_sell (2-decimal as displayed)

    Returns (parsed, dbg)
    """
    dbg: Dict[str, Any] = {"format": "xrt_html", "reason": "NA"}

    # 1) page date (header line contains: "#  2026/01/26 本行 ...")
    m_date = re.search(r"#\s*(\d{4}/\d{2}/\d{2})\s+本行", html)
    page_date = m_date.group(1) if m_date else None

    # 2) quote time (line contains: "牌價最新掛牌時間：2026/01/26 14:38")
    m_qt = re.search(r"牌價最新掛牌時間：\s*(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2})", html)
    qt_date = m_qt.group(1) if m_qt else None
    qt_hm = m_qt.group(2) if m_qt else None

    # 3) USD row: we anchor near "美金 (USD)" then capture 4 numbers (cash buy/sell, spot buy/sell)
    # The HTML content usually contains a segment like:
    # 美金 (USD) ... 31.06 31.73 31.41  31.51 ...
    m_usd = re.search(
        r"美金\s*\(USD\)[\s\S]{0,400}?\s(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)",
        html
    )
    cash_buy = cash_sell = spot_buy = spot_sell = None
    if m_usd:
        cash_buy = _to_float(m_usd.group(1))
        cash_sell = _to_float(m_usd.group(2))
        spot_buy = _to_float(m_usd.group(3))
        spot_sell = _to_float(m_usd.group(4))

    if not page_date:
        dbg["reason"] = "cannot_find_page_date"
        return None, dbg
    if not (spot_buy is not None and spot_sell is not None):
        dbg["reason"] = "cannot_find_usd_spot"
        return None, dbg

    # data_date ISO
    data_date = page_date.replace("/", "-")

    # quote_time_local ISO (best-effort). If quote time missing, use page date 00:00.
    tz = ZoneInfo(tz_name)
    if qt_date and qt_hm:
        # qt_date should match page_date, but we won't assume
        dt = datetime.strptime(f"{qt_date} {qt_hm}", "%Y/%m/%d %H:%M").replace(tzinfo=tz)
    else:
        dt = datetime.strptime(page_date, "%Y/%m/%d").replace(tzinfo=tz)
        dbg["quote_time_note"] = "missing_quote_time_fallback_to_midnight"

    parsed = {
        "data_date": data_date,
        "quote_time_local": dt.isoformat(),
        "usd_twd": {
            "cash_buy": cash_buy,
            "cash_sell": cash_sell,
            "spot_buy": spot_buy,
            "spot_sell": spot_sell,
        },
    }
    dbg["reason"] = "ok"
    return parsed, dbg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei", help="(legacy) accepted; used only for quote_time_local tz")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10, help="(legacy) ignored")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 1) if spot rates are missing/invalid.")
    ap.add_argument("--source-url", default=BOT_XRT_PAGE)
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    session = requests.Session()
    status_code, html, http_err = _fetch(session, args.source_url, args.timeout)

    parsed: Optional[Dict[str, Any]] = None
    parse_dbg: Dict[str, Any] = {"format": "xrt_html", "reason": "http_not_200_or_empty"}

    if status_code == 200 and html:
        parsed, parse_dbg = _parse_xrt_html(html, args.tz)

    data_date = parsed.get("data_date") if parsed else None
    spot_buy = parsed["usd_twd"].get("spot_buy") if parsed else None
    spot_sell = parsed["usd_twd"].get("spot_sell") if parsed else None

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
        "source_url": args.source_url,
        "data_date": data_date,
        "quote_time_local": (parsed.get("quote_time_local") if parsed else None),
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
                "source_url": args.source_url,
                "quote_time_local": latest.get("quote_time_local"),
            },
        )
        _dump_json(args.history, history)

    print(
        "FX(BOT:XRT_HTML) strict_ok={ok} date={date} spot_buy={b} spot_sell={s} mid={m} http={http} err={err} url={url}".format(
            ok=str(strict_ok).lower(),
            date=data_date or "NA",
            b="None" if spot_buy is None else f"{spot_buy:.6f}",
            s="None" if spot_sell is None else f"{spot_sell:.6f}",
            m="None" if mid is None else f"{mid:.6f}",
            http=status_code,
            err=(http_err or "NA"),
            url=(args.source_url or "NA"),
        )
    )

    if args.strict and not strict_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())