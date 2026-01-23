#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fetch Taiwan market margin-financing balances (融資餘額) for:
- TWSE (上市)
- TPEX (上櫃)

Priority (as requested):
1) Yahoo奇摩股市「資券餘額」
2) WantGoo「資券進出行情」
3) HiStock
4) Official (last fallback; best-effort, may be NA)

Output: taiwan_margin_cache/latest.json
Schema: taiwan_margin_financing_latest_v1
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
import pandas as pd
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_get(url: str, timeout: int = 25, retries: int = 3) -> str:
    last_err: Optional[str] = None
    for i in range(retries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.0 + i * 1.5)
    raise RuntimeError(f"HTTP 取得失敗：{last_err} for url: {url}")


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "-", "—", "NA", "N/A", "None", "null"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _normalize_date_yyyymmdd_to_iso(s: str) -> Optional[str]:
    s = s.strip()
    # allow 2026/01/22 or 2026-01-22
    s = s.replace("/", "-")
    if ISO_DATE_RE.match(s):
        return s
    return None


@dataclass
class SeriesResult:
    source: str
    source_url: str
    data_date: Optional[str]
    rows: List[Dict[str, Any]]
    notes: List[str]


def _validate_rows(rows: List[Dict[str, Any]], min_rows: int) -> Tuple[bool, str]:
    if len(rows) < min_rows:
        return False, f"rows 不足：{len(rows)} < {min_rows}"
    # validate date monotonic (descending)
    dates = [r.get("date") for r in rows]
    if any((d is None) or (not ISO_DATE_RE.match(str(d))) for d in dates):
        return False, "rows.date 格式不一致/缺失"
    return True, "OK"


# -------------------------
# 1) Yahoo (best-effort)
# -------------------------
YAHOO_URL = "https://tw.stock.yahoo.com/margin-balance/"

def _parse_yahoo_table(html: str, market: str) -> SeriesResult:
    """
    Yahoo page often includes a table with market selector.
    SSR reliability for TPEX may be poor; we still attempt.
    """
    notes: List[str] = []
    # pandas read_html requires html5lib (installed in workflow)
    try:
        dfs = pd.read_html(html)
    except Exception as e:
        return SeriesResult(
            source="Yahoo",
            source_url=YAHOO_URL,
            data_date=None,
            rows=[],
            notes=[f"Yahoo 解析失敗：{type(e).__name__}: {e}"],
        )

    # Heuristic: find the dataframe with columns containing "日期" and "融資餘額" / "融資增減"
    target = None
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any("日期" in c for c in cols) and any(("融資" in c and "餘額" in c) for c in cols):
            target = df
            break

    if target is None:
        return SeriesResult(
            source="Yahoo",
            source_url=YAHOO_URL,
            data_date=None,
            rows=[],
            notes=["Yahoo 找不到可用表格（可能前端載入/版面變更）"],
        )

    # Standardize columns by substring match
    col_date = next((c for c in target.columns if "日期" in str(c)), None)
    col_bal = next((c for c in target.columns if ("融資" in str(c) and "餘額" in str(c))), None)
    col_chg = next((c for c in target.columns if ("融資" in str(c) and "增減" in str(c))), None)

    if not col_date or not col_bal or not col_chg:
        return SeriesResult(
            source="Yahoo",
            source_url=YAHOO_URL,
            data_date=None,
            rows=[],
            notes=["Yahoo 欄位不完整（日期/餘額/增減）"],
        )

    rows: List[Dict[str, Any]] = []
    for _, r in target.iterrows():
        d = _normalize_date_yyyymmdd_to_iso(str(r[col_date]))
        bal = _safe_float(r[col_bal])
        chg = _safe_float(r[col_chg])
        if d and (bal is not None) and (chg is not None):
            rows.append({"date": d, "balance_yi": float(bal), "chg_yi": float(chg)})

    if not rows:
        return SeriesResult(
            source="Yahoo",
            source_url=YAHOO_URL,
            data_date=None,
            rows=[],
            notes=["Yahoo 表格列解析後為空（可能格式異常/數值不可讀）"],
        )

    # Ensure descending by date (string ISO sort works)
    rows = sorted(rows, key=lambda x: x["date"], reverse=True)
    data_date = rows[0]["date"]
    notes.append(f"Yahoo({market})：若 TPEX 為前端載入，可能會抓到不完整或錯市場資料，已交由後續防呆檢查處理。")
    return SeriesResult(
        source="Yahoo",
        source_url=YAHOO_URL,
        data_date=data_date,
        rows=rows,
        notes=[] if market == "TWSE" else notes,
    )


# -------------------------
# 2) WantGoo (often 403)
# -------------------------
WANTGOO_TWSE_URLS = [
    "https://www.wantgoo.com/stock/margin-trading/market-price/taiex",
]
WANTGOO_TPEX_URLS = [
    "https://www.wantgoo.com/stock/margin-trading/market-price/otc",
    "https://www.wantgoo.com/stock/margin-trading/market-price/gtsm",
    "https://www.wantgoo.com/stock/margin-trading/market-price/tpex",
]

def _parse_wantgoo(market: str, urls: List[str], min_rows: int) -> SeriesResult:
    notes: List[str] = []
    for url in urls:
        try:
            html = _http_get(url, timeout=25, retries=2)
        except Exception as e:
            notes.append(str(e))
            continue

        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if table is None:
            notes.append(f"WantGoo 未找到 table：{url}")
            continue

        # Try to parse first table with date/balance/chg
        try:
            df = pd.read_html(str(table))[0]
        except Exception as e:
            notes.append(f"WantGoo read_html 失敗：{type(e).__name__}: {e} ({url})")
            continue

        cols = [str(c) for c in df.columns]
        col_date = next((c for c in df.columns if "日期" in str(c)), None)
        col_bal = next((c for c in df.columns if ("融資" in str(c) and "餘額" in str(c))), None)
        col_chg = next((c for c in df.columns if ("融資" in str(c) and "增減" in str(c))), None)
        if not col_date or not col_bal or not col_chg:
            notes.append(f"WantGoo 欄位不完整：{cols} ({url})")
            continue

        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            d = _normalize_date_yyyymmdd_to_iso(str(r[col_date]))
            bal = _safe_float(r[col_bal])
            chg = _safe_float(r[col_chg])
            if d and (bal is not None) and (chg is not None):
                rows.append({"date": d, "balance_yi": float(bal), "chg_yi": float(chg)})

        rows = sorted(rows, key=lambda x: x["date"], reverse=True)
        ok, reason = _validate_rows(rows, min_rows)
        if ok:
            return SeriesResult(
                source="WantGoo",
                source_url=url,
                data_date=rows[0]["date"],
                rows=rows,
                notes=[],
            )
        notes.append(f"WantGoo 解析不足：{reason} ({url})")

    return SeriesResult(
        source="WantGoo",
        source_url=";".join(urls),
        data_date=None,
        rows=[],
        notes=notes if notes else ["WantGoo 無法取得/解析（可能 403 或前端載入）"],
    )


# -------------------------
# 3) HiStock (working fallback)
# -------------------------
HISTOCK_TWSE_URL = "https://histock.tw/stock/three.aspx?m=mg"
HISTOCK_TPEX_URL = "https://histock.tw/stock/three.aspx?m=mg&no=TWOI"

def _histock_market_hint_ok(market: str, html: str) -> bool:
    # Very light identification; do not overfit.
    text = html
    if market == "TWSE":
        # allow "上市" "加權" etc. presence is not guaranteed; keep weak.
        return True
    # TPEX page should often contain "上櫃" or "櫃買" or "OTC"
    return any(k in text for k in ["上櫃", "櫃買", "OTC", "TWOI"])

def _parse_histock(market: str, url: str, min_rows: int) -> SeriesResult:
    try:
        html = _http_get(url, timeout=25, retries=3)
    except Exception as e:
        return SeriesResult(
            source="HiStock",
            source_url=url,
            data_date=None,
            rows=[],
            notes=[str(e)],
        )

    if not _histock_market_hint_ok(market, html):
        return SeriesResult(
            source="HiStock",
            source_url=url,
            data_date=None,
            rows=[],
            notes=[f"HiStock 市場識別字樣不足，疑似抓到非 {market} 頁面（避免誤判）"],
        )

    # HiStock page typically has a table with 日期 / 融資餘額 / 融資增減
    try:
        dfs = pd.read_html(html)
    except Exception as e:
        return SeriesResult(
            source="HiStock",
            source_url=url,
            data_date=None,
            rows=[],
            notes=[f"HiStock read_html 失敗：{type(e).__name__}: {e}"],
        )

    target = None
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any("日期" in c for c in cols) and any(("融資" in c and "餘額" in c) for c in cols):
            target = df
            break

    if target is None:
        return SeriesResult(
            source="HiStock",
            source_url=url,
            data_date=None,
            rows=[],
            notes=["HiStock 找不到可用表格（可能版面變更）"],
        )

    col_date = next((c for c in target.columns if "日期" in str(c)), None)
    col_bal = next((c for c in target.columns if ("融資" in str(c) and "餘額" in str(c))), None)
    col_chg = next((c for c in target.columns if ("融資" in str(c) and "增減" in str(c))), None)

    rows: List[Dict[str, Any]] = []
    for _, r in target.iterrows():
        d = _normalize_date_yyyymmdd_to_iso(str(r[col_date])) if col_date else None
        bal = _safe_float(r[col_bal]) if col_bal else None
        chg = _safe_float(r[col_chg]) if col_chg else None
        if d and (bal is not None) and (chg is not None):
            rows.append({"date": d, "balance_yi": float(bal), "chg_yi": float(chg)})

    rows = sorted(rows, key=lambda x: x["date"], reverse=True)
    ok, reason = _validate_rows(rows, min_rows)
    if not ok:
        return SeriesResult(
            source="HiStock",
            source_url=url,
            data_date=rows[0]["date"] if rows else None,
            rows=rows,
            notes=[f"HiStock 解析不足：{reason}"],
        )
    return SeriesResult(
        source="HiStock",
        source_url=url,
        data_date=rows[0]["date"],
        rows=rows,
        notes=[],
    )


# -------------------------
# 4) Official (last fallback; best-effort, may NA)
# -------------------------
def _official_placeholder(market: str) -> SeriesResult:
    return SeriesResult(
        source="Official",
        source_url="NA",
        data_date=None,
        rows=[],
        notes=["官方來源端點未在此版硬編碼（避免欄位變更造成誤判）；如需再加，建議以可驗證 CSV/OpenData 為準。"],
    )


def _rows_equal_prefix(a: List[Dict[str, Any]], b: List[Dict[str, Any]], n: int = 10) -> bool:
    if len(a) < n or len(b) < n:
        return False
    for i in range(n):
        if (a[i].get("date"), a[i].get("balance_yi"), a[i].get("chg_yi")) != (
            b[i].get("date"),
            b[i].get("balance_yi"),
            b[i].get("chg_yi"),
        ):
            return False
    return True


def fetch_one_market(market: str, min_rows: int) -> SeriesResult:
    """
    Try Yahoo -> WantGoo -> HiStock -> Official
    """
    # Yahoo
    try:
        html = _http_get(YAHOO_URL, timeout=25, retries=2)
        r = _parse_yahoo_table(html, market=market)
        ok, _ = _validate_rows(r.rows, min_rows)
        if ok:
            return r
    except Exception as e:
        r = SeriesResult("Yahoo", YAHOO_URL, None, [], [f"Yahoo 取得/解析失敗：{type(e).__name__}: {e}"])

    # WantGoo
    if market == "TWSE":
        wg = _parse_wantgoo(market, WANTGOO_TWSE_URLS, min_rows=min_rows)
    else:
        wg = _parse_wantgoo(market, WANTGOO_TPEX_URLS, min_rows=min_rows)
    ok, _ = _validate_rows(wg.rows, min_rows)
    if ok:
        return wg

    # HiStock
    url = HISTOCK_TWSE_URL if market == "TWSE" else HISTOCK_TPEX_URL
    hs = _parse_histock(market, url=url, min_rows=min_rows)
    ok, _ = _validate_rows(hs.rows, min_rows)
    if ok:
        return hs

    # Official placeholder
    off = _official_placeholder(market)
    # accumulate notes from previous failures (minimal but useful)
    off.notes = (r.notes if "r" in locals() else []) + wg.notes + hs.notes + off.notes
    return off


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_rows", type=int, default=21)
    args = ap.parse_args()

    twse = fetch_one_market("TWSE", min_rows=args.min_rows)
    tpex = fetch_one_market("TPEX", min_rows=args.min_rows)

    # Hard anti-misread guard: if TWSE and TPEX rows are identical prefix, TPEX is likely wrong.
    if _rows_equal_prefix(twse.rows, tpex.rows, n=10):
        # Force TPEX to NA (do not pretend OK)
        tpex = SeriesResult(
            source=tpex.source,
            source_url=tpex.source_url,
            data_date=None,
            rows=[],
            notes=(tpex.notes + ["TPEX 與 TWSE 前 10 筆完全相同：高機率抓錯頁面，依防誤判規則將 TPEX 置為 NA"]),
        )

    out = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": now_utc_iso(),
        "series": {
            "TWSE": {
                "source": twse.source,
                "source_url": twse.source_url,
                "data_date": twse.data_date,
                "rows": twse.rows,
                "notes": twse.notes,
            },
            "TPEX": {
                "source": tpex.source,
                "source_url": tpex.source_url,
                "data_date": tpex.data_date,
                "rows": tpex.rows,
                "notes": tpex.notes,
            },
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())