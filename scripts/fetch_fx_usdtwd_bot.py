#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from BOT xrt page (HTML) with robust parsing.

Key:
- 1 request per run.
- Parse page date + quote time + USD cash/spot buy/sell from xrt page.
- Robust: strip HTML tags -> text, then regex on text.
- Backward compatible args: --tz, --max-back accepted (max-back ignored).

Outputs:
- fx_cache/latest.json
- fx_cache/history.json (upsert by date)

Strict:
- require data_date + spot_buy + spot_sell + spot_sell>=spot_buy
"""

from __future__ import annotations

import argparse
import html as htmllib
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
        resp.encoding = "utf-8"
        return resp.status_code, resp.text, None
    except Exception as e:
        return 0, "", str(e)


def _html_to_text(html: str) -> str:
    # Unescape entities and drop tags -> text
    s = htmllib.unescape(html)
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_xrt_text(text: str, tz_name: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    We parse on "flattened" text.

    Targets (Chinese page):
    - page date: 2026/01/26 ... 本行營業時間牌告匯率
    - quote time: 牌價最新掛牌時間：2026/01/26 14:38
    - USD row: 美金 (USD) ... <cash_buy> <cash_sell> <spot_buy> <spot_sell>

    If Chinese anchors fail, we also try English-like anchors.
    """
    dbg: Dict[str, Any] = {
        "format": "xrt_text_v2",
        "reason": "NA",
        "text_len": len(text),
        "text_head": text[:220],
        "text_has_usd": ("USD" in text),
        "text_has_zh_usd": ("美金" in text and "USD" in text),
    }

    # (1) page date
    page_date = None
    m1 = re.search(r"(\d{4}/\d{2}/\d{2})\s*本行", text)
    if m1:
        page_date = m1.group(1)
    else:
        # fallback: any yyyy/mm/dd near "Foreign Exchange Rate" (English page)
        m1b = re.search(r"(\d{4}/\d{2}/\d{2}).{0,40}Foreign Exchange Rate", text, flags=re.IGNORECASE)
        if m1b:
            page_date = m1b.group(1)

    # (2) quote time (optional but preferred)
    quote_dt_iso = None
    m2 = re.search(r"牌價最新掛牌時間[:：]\s*(\d{4}/\d{2}/\d{2})\s*(\d{2}:\d{2})", text)
    if m2:
        tz = ZoneInfo(tz_name)
        dt = datetime.strptime(f"{m2.group(1)} {m2.group(2)}", "%Y/%m/%d %H:%M").replace(tzinfo=tz)
        quote_dt_iso = dt.isoformat()

    # (3) USD numbers: cash_buy cash_sell spot_buy spot_sell (as in the table snippet)
    cash_buy = cash_sell = spot_buy = spot_sell = None

    # Preferred: Chinese anchor
    m3 = re.search(
        r"美金\s*\(USD\).*?(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)",
        text
    )
    if not m3:
        # Fallback: any USD anchor then capture 4 floats after it (avoid grabbing forwards, keep it local window)
        m3 = re.search(
            r"USD.{0,120}?(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)",
            text
        )

    if m3:
        cash_buy = _to_float(m3.group(1))
        cash_sell = _to_float(m3.group(2))
        spot_buy = _to_float(m3.group(3))
        spot_sell = _to_float(m3.group(4))

    if not page_date:
        dbg["reason"] = "cannot_find_page_date"
        return None, dbg
    if spot_buy is None or spot_sell is None:
        dbg["reason"] = "cannot_find_usd_spot"
        dbg["usd_match_window"] = text[text.find("USD")-80:text.find("USD")+220] if "USD" in text else "NA"
        return None, dbg

    data_date = page_date.replace("/", "-")

    parsed = {
        "data_date": data_date,
        "quote_time_local": quote_dt_iso,
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
    ap.add_argument("--tz", default="Asia/Taipei", help="Accepted for backward compatibility; used for quote_time_local tz.")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10, help="(legacy) ignored")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--source-url", default=BOT_XRT_PAGE)
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    session = requests.Session()
    status_code, html, http_err = _fetch(session, args.source_url, args.timeout)

    parsed: Optional[Dict[str, Any]] = None
    parse_dbg: Dict[str, Any] = {"format": "xrt_text_v2", "reason": "http_not_200_or_empty"}

    text = ""
    if status_code == 200 and html:
        text = _html_to_text(html)
        parsed, parse_dbg = _parse_xrt_text(text, args.tz)

    data_date = parsed.get("data_date") if parsed else None
    spot_buy = parsed["usd_twd"]["spot_buy"] if parsed else None
    spot_sell = parsed["usd_twd"]["spot_sell"] if parsed else None

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
        "usd_twd": {"spot_buy": spot_buy, "spot_sell": spot_sell, "mid": mid},
        "raw": {
            "parse_dbg": parse_dbg,
            "text_head": (text[:220] if text else None),
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
        "FX(BOT:XRT_HTML_v2) strict_ok={ok} date={date} spot_buy={b} spot_sell={s} mid={m} http={http} reason={reason}".format(
            ok=str(strict_ok).lower(),
            date=data_date or "NA",
            b="None" if spot_buy is None else f"{spot_buy:.6f}",
            s="None" if spot_sell is None else f"{spot_sell:.6f}",
            m="None" if mid is None else f"{mid:.6f}",
            http=status_code,
            reason=parse_dbg.get("reason", "NA"),
        )
    )

    if args.strict and not strict_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())