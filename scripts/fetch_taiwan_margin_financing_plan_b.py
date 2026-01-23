#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plan B: Taiwan margin-financing (TWSE + TPEX) daily totals.

Source priority (per market):
1) Yahoo奇摩股市「資券餘額」
2) WantGoo「資券進出行情」
3) HiStock
4) Official (last fallback)

Output: latest.json (audit-friendly)
- records actual source used per market
- records source_url(s), data_date, extracted rows (>=min_rows if possible), notes with downgrade reasons
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# ---------- utils ----------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def write_json(path: str, obj: Any) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    })
    return s

def http_get_text(url: str, timeout: int = 20) -> str:
    s = _session()
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

def http_get_bytes(url: str, timeout: int = 20) -> bytes:
    s = _session()
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content

def safe_float(s: str) -> Optional[float]:
    # allow "2,925.89" "-2.97"
    s = s.strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None

def norm_date_yyyy_mm_dd(raw: str) -> Optional[str]:
    raw = raw.strip()
    # Yahoo uses YYYY/MM/DD
    m = re.match(r"^(\d{4})/(\d{2})/(\d{2})$", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # also accept YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if m:
        return raw
    return None

# ---------- data model ----------

@dataclass
class SeriesResult:
    source: str
    source_url: str
    data_date: Optional[str]
    rows: List[Dict[str, Any]]  # each: {date, balance_yi, chg_yi, chg_pct? (optional)}
    notes: List[str]

def empty_result(source: str, url: str, note: str) -> SeriesResult:
    return SeriesResult(source=source, source_url=url, data_date=None, rows=[], notes=[note])

# ---------- Yahoo parser ----------

YAHOO_URL = "https://tw.stock.yahoo.com/margin-balance/"

def parse_yahoo_twse_table(html: str, min_rows: int) -> SeriesResult:
    """
    Yahoo page renders TWSE table in HTML; OTC tab often lazy-loaded (may not be present).
    We extract the first table rows:
      date
      融資增減(億元)  融資餘額(億元)
    """
    notes: List[str] = []
    soup = BeautifulSoup(html, "lxml")

    # Heuristic: find rows that look like YYYY/MM/DD in text, then read subsequent numeric bullets.
    # Yahoo's SSR markup is not stable; we use robust regex scan on text blocks.
    text = soup.get_text("\n", strip=True)

    # Capture blocks: date then next two numbers (chg, balance) in that order
    # Example sequence in text: 2026/01/20  -9.61  3,388.44 ...
    pattern = re.compile(
        r"(\d{4}/\d{2}/\d{2})\s+([+-]?\d+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)"
    )
    rows: List[Dict[str, Any]] = []
    for m in pattern.finditer(text):
        d = norm_date_yyyy_mm_dd(m.group(1))
        chg = safe_float(m.group(2))
        bal = safe_float(m.group(3))
        if d and chg is not None and bal is not None:
            rows.append({"date": d, "chg_yi": chg, "balance_yi": bal})

    # Deduplicate by date keeping first occurrence (page may repeat content in nav/SEO blocks)
    seen = set()
    dedup: List[Dict[str, Any]] = []
    for r in rows:
        if r["date"] in seen:
            continue
        seen.add(r["date"])
        dedup.append(r)

    if len(dedup) < min_rows:
        notes.append(f"Yahoo(TWSE) 抽取列數不足：{len(dedup)} < {min_rows}（可能頁面結構變更或抓到重複/非表格文字）")

    data_date = dedup[0]["date"] if dedup else None
    return SeriesResult(
        source="Yahoo",
        source_url=YAHOO_URL,
        data_date=data_date,
        rows=dedup[:max(min_rows, len(dedup))],
        notes=notes,
    )

# ---------- WantGoo / HiStock (light wrappers; may fail with 403 or no market totals) ----------

WANTGOO_TWSE = "https://www.wantgoo.com/stock/margin-trading/market-price/taiex"
WANTGOO_TPEX = "https://www.wantgoo.com/stock/margin-trading/market-price/otc"

def try_wantgoo(url: str, min_rows: int) -> SeriesResult:
    try:
        html = http_get_text(url, timeout=20)
        soup = BeautifulSoup(html, "lxml")
        # Expect a table with date + margin balance; since layout may change, we implement a generic scan:
        text = soup.get_text("\n", strip=True)
        # Try: YYYY/MM/DD then ... balance (億元) maybe.
        pattern = re.compile(r"(\d{4}/\d{2}/\d{2}).{0,40}?([+-]?\d+(?:\.\d+)?).{0,20}?([\d,]+(?:\.\d+)?)")
        rows: List[Dict[str, Any]] = []
        for m in pattern.finditer(text):
            d = norm_date_yyyy_mm_dd(m.group(1))
            chg = safe_float(m.group(2))
            bal = safe_float(m.group(3))
            if d and chg is not None and bal is not None:
                rows.append({"date": d, "chg_yi": chg, "balance_yi": bal})
        # dedup
        seen = set()
        out = []
        for r in rows:
            if r["date"] in seen:
                continue
            seen.add(r["date"])
            out.append(r)
        data_date = out[0]["date"] if out else None
        notes = []
        if len(out) < min_rows:
            notes.append(f"WantGoo 抽取列數不足：{len(out)} < {min_rows}")
        return SeriesResult("WantGoo", url, data_date, out, notes)
    except Exception as e:
        return empty_result("WantGoo", url, f"HTTP/解析失敗：{type(e).__name__}: {e}")

def try_histock_market_totals(market: str, min_rows: int) -> SeriesResult:
    # HiStock沒有穩定公開「市場融資餘額(億元)歷史表」的保證入口；這裡先保留結構，避免你誤以為一定可用。
    return empty_result("HiStock", f"(NA:{market})", "未實作：HiStock 無穩定可審計的市場總額歷史表入口（避免誤抓個股頁）")

# ---------- Official fallback (last resort) ----------
# Note: Official endpoints vary; we keep placeholders + explicit NA if unreliable.

def try_official_twse(min_rows: int) -> SeriesResult:
    # Placeholder: implement only if you decide to pin down TWSE API format and test it.
    return empty_result(
        "Official",
        "https://www.twse.com.tw/exchangeReport/MI_MARGN",
        "未啟用：官方 TWSE 端點需要釐清欄位/格式後再啟用（避免錯算市場總額）"
    )

def try_official_tpex(min_rows: int) -> SeriesResult:
    # Placeholder: implement only if you decide to pin down TPEx API format and test it.
    return empty_result(
        "Official",
        "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php",
        "未啟用：官方 TPEX 端點需要釐清參數/格式後再啟用（避免錯算市場總額）"
    )

# ---------- orchestrator ----------

def fetch_twse(min_rows: int) -> SeriesResult:
    # 1) Yahoo
    try:
        html = http_get_text(YAHOO_URL, timeout=20)
        r = parse_yahoo_twse_table(html, min_rows=min_rows)
        if r.rows and len(r.rows) >= min_rows and r.data_date:
            return r
    except Exception as e:
        r = empty_result("Yahoo", YAHOO_URL, f"Yahoo 解析失敗：{type(e).__name__}: {e}")

    # 2) WantGoo
    wg = try_wantgoo(WANTGOO_TWSE, min_rows=min_rows)
    if wg.rows and len(wg.rows) >= min_rows and wg.data_date:
        return wg

    # 3) HiStock
    hs = try_histock_market_totals("TWSE", min_rows=min_rows)
    if hs.rows and len(hs.rows) >= min_rows and hs.data_date:
        return hs

    # 4) Official
    off = try_official_twse(min_rows=min_rows)
    return off if off.rows else SeriesResult(
        source=off.source,
        source_url=off.source_url,
        data_date=None,
        rows=[],
        notes=[*r.notes, *wg.notes, *hs.notes, *off.notes] if "r" in locals() else [*wg.notes, *hs.notes, *off.notes],
    )

def fetch_tpex(min_rows: int) -> SeriesResult:
    # 1) Yahoo (OTC often lazy-loaded; likely not available in SSR => will fail)
    try:
        html = http_get_text(YAHOO_URL, timeout=20)
        # Try to parse OTC as well; if SSR doesn't include, rows will be insufficient => fall through.
        r = parse_yahoo_twse_table(html, min_rows=min_rows)  # same parser; will mostly be TWSE SSR
        # Guard: If we can't prove it's OTC, do not accept it.
        # (We require explicit evidence; otherwise treat as not available.)
        return empty_result("Yahoo", YAHOO_URL, "Yahoo(OTC) 多數情況為前端載入，SSR 無法可靠取得（避免把 TWSE 當 OTC）")
    except Exception as e:
        _ = e  # continue

    # 2) WantGoo
    wg = try_wantgoo(WANTGOO_TPEX, min_rows=min_rows)
    if wg.rows and len(wg.rows) >= min_rows and wg.data_date:
        return wg

    # 3) HiStock (not implemented)
    hs = try_histock_market_totals("TPEX", min_rows=min_rows)
    if hs.rows and len(hs.rows) >= min_rows and hs.data_date:
        return hs

    # 4) Official (placeholder)
    off = try_official_tpex(min_rows=min_rows)
    return off if off.rows else SeriesResult(
        source=off.source,
        source_url=off.source_url,
        data_date=None,
        rows=[],
        notes=[*wg.notes, *hs.notes, *off.notes],
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_rows", type=int, default=21)
    args = ap.parse_args()

    out: Dict[str, Any] = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": utc_now_iso(),
        "series": {}
    }

    twse = fetch_twse(args.min_rows)
    tpex = fetch_tpex(args.min_rows)

    out["series"]["TWSE"] = {
        "source": twse.source,
        "source_url": twse.source_url,
        "data_date": twse.data_date,
        "rows": twse.rows,
        "notes": twse.notes,
    }
    out["series"]["TPEX"] = {
        "source": tpex.source,
        "source_url": tpex.source_url,
        "data_date": tpex.data_date,
        "rows": tpex.rows,
        "notes": tpex.notes,
    }

    write_json(args.out, out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())