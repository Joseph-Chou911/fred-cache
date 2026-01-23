#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_taiwan_margin_financing_plan_b.py

Plan B:
- Primary: WantGoo "資券進出行情" market page (TWSE listed).
- If extraction fails or rows < min_rows: fallback to Official OpenData/CSV.
- Output: taiwan_margin_cache/latest.json (includes TWSE + TPEX series, source meta, data_date per market)

IMPORTANT:
- Stop rules: if a field cannot be extracted reliably -> keep NA (null) and explain in meta.
- We do NOT invent missing values.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests


# -----------------------------
# Config (sources)
# -----------------------------
# WantGoo (confirmed TWSE-listed market page)
WANTGOO_TWSE_URL = "https://www.wantgoo.com/stock/margin-trading/market-price/taiex"

# WantGoo TPEX URL is not reliably discoverable from public HTML (may be JS-routed).
# We still try common guesses; if all fail -> official fallback.
WANTGOO_TPEX_GUESSES = [
    "https://www.wantgoo.com/stock/margin-trading/market-price/otc",
    "https://www.wantgoo.com/stock/margin-trading/market-price/gtsm",
    "https://www.wantgoo.com/stock/margin-trading/market-price/tpex",
]

# Official fallback endpoints (best-effort; these sites occasionally change).
# We keep them as templates; if they fail, we output NA with reasons.
# TWSE margin trading: typically "MI_MARGN" or similar API/CSV.
TWSE_OFFICIAL_FALLBACKS = [
    # JSON-ish (rwd) endpoint (date=YYYYMMDD). selectType may vary; keep generic.
    "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={yyyymmdd}&selectType=MS&response=json",
    "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={yyyymmdd}&response=json",
]

# TPEX margin trading: often has CSV with ROC date (YYY/MM/DD) or ROC YYY/MM/DD
TPEX_OFFICIAL_FALLBACKS = [
    # CSV export endpoints vary; keep multiple guesses.
    "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_balance.php?l=zh-tw&o=csv&d={roc_yyy}/{mm}/{dd}",
    "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_balance.php?l=zh-tw&o=csv&d={roc_yyy}/{mm}/{dd}&s=0,asc",
]


# -----------------------------
# Helpers
# -----------------------------
def http_get(url: str, timeout: int = 20) -> requests.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s or s in {"-", "—", "NA", "N/A", "null"}:
        return None
    s = s.replace(",", "")
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def infer_year_for_mmdd(mm: int, dd: int, today: date) -> int:
    """
    WantGoo table often shows 'MM/DD' without year.
    Rule (conservative):
    - If month > today.month + 1, treat as previous year (handles Jan viewing Dec data).
    - Else treat as current year.
    """
    if mm > today.month + 1:
        return today.year - 1
    return today.year


def parse_mmdd(s: str, today: date) -> Optional[str]:
    s = str(s).strip()
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})\s*$", s)
    if not m:
        return None
    mm = int(m.group(1))
    dd = int(m.group(2))
    yyyy = infer_year_for_mmdd(mm, dd, today)
    try:
        d = date(yyyy, mm, dd)
        return d.isoformat()
    except Exception:
        return None


def ensure_desc_by_date(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def keyfn(r: Dict[str, Any]) -> str:
        return str(r.get("date") or "")
    return sorted(rows, key=keyfn, reverse=True)


# -----------------------------
# WantGoo parsing
# -----------------------------
@dataclass
class SeriesResult:
    market: str  # "TWSE" or "TPEX"
    source: str
    source_url: str
    data_date: Optional[str]  # latest row date
    rows: List[Dict[str, Any]]  # each: {"date": "YYYY-MM-DD", "margin_balance_100m": float}
    notes: List[str]


def parse_wantgoo_market_page(url: str, market: str, min_rows: int) -> SeriesResult:
    notes: List[str] = []
    rows: List[Dict[str, Any]] = []
    data_date: Optional[str] = None

    today = date.today()
    try:
        html = http_get(url).text
    except Exception as e:
        return SeriesResult(
            market=market,
            source="WantGoo",
            source_url=url,
            data_date=None,
            rows=[],
            notes=[f"HTTP 取得失敗：{type(e).__name__}: {e}"],
        )

    # Use pandas.read_html to extract tables
    try:
        tables = pd.read_html(html)
    except Exception as e:
        return SeriesResult(
            market=market,
            source="WantGoo",
            source_url=url,
            data_date=None,
            rows=[],
            notes=[f"read_html 解析失敗：{type(e).__name__}: {e}"],
        )

    # Find the table that includes "融資餘額" and "日期"
    target_df: Optional[pd.DataFrame] = None
    for df in tables:
        cols = [str(c) for c in df.columns]
        col_join = " ".join(cols)
        if ("融資餘額" in col_join) and ("日期" in col_join):
            target_df = df
            break

    if target_df is None:
        return SeriesResult(
            market=market,
            source="WantGoo",
            source_url=url,
            data_date=None,
            rows=[],
            notes=["找不到包含「日期」「融資餘額」欄位的表格（可能頁面改版或需 JS 轉載入）。"],
        )

    # Normalize column names
    df = target_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Identify columns
    date_col = None
    bal_col = None
    for c in df.columns:
        if "日期" in c:
            date_col = c
        if "融資餘額" in c:
            bal_col = c

    if not date_col or not bal_col:
        return SeriesResult(
            market=market,
            source="WantGoo",
            source_url=url,
            data_date=None,
            rows=[],
            notes=[f"欄位辨識失敗：date_col={date_col}, bal_col={bal_col}"],
        )

    # Parse rows
    for _, r in df.iterrows():
        d = parse_mmdd(r.get(date_col), today)
        bal = to_float(r.get(bal_col))
        if d and (bal is not None):
            rows.append({"date": d, "margin_balance_100m": bal})

    rows = ensure_desc_by_date(rows)

    if not rows:
        notes.append("表格存在但無法解析出有效（日期, 融資餘額）列。")
    else:
        data_date = rows[0]["date"]

    if len(rows) < min_rows:
        notes.append(f"有效交易日列數不足：{len(rows)} < {min_rows}")

    return SeriesResult(
        market=market,
        source="WantGoo",
        source_url=url,
        data_date=data_date,
        rows=rows[: max(min_rows, len(rows))],  # keep whatever we have (renderer decides NA)
        notes=notes,
    )


# -----------------------------
# Official fallback parsing (best-effort)
# -----------------------------
def roc_date_parts(d: date) -> Dict[str, str]:
    roc_yyy = str(d.year - 1911)
    return {"roc_yyy": roc_yyy, "mm": f"{d.month:02d}", "dd": f"{d.day:02d}"}


def fetch_official_twse_series(min_rows: int) -> SeriesResult:
    """
    Best-effort: try recent calendar days back until we collect >= min_rows trading-day points,
    each point is the total margin balance (億) at market level.

    If endpoints change -> returns empty with notes.
    """
    market = "TWSE"
    source = "TWSE官方(OpenData/CSV)"
    notes: List[str] = []
    rows: List[Dict[str, Any]] = []

    # We'll try last ~45 calendar days to collect >=21 trading days.
    today = date.today()
    for back in range(0, 60):
        d = today.fromordinal(today.toordinal() - back)
        yyyymmdd = f"{d.year:04d}{d.month:02d}{d.day:02d}"
        success = False

        for tpl in TWSE_OFFICIAL_FALLBACKS:
            url = tpl.format(yyyymmdd=yyyymmdd)
            try:
                j = http_get(url).json()
            except Exception:
                continue

            # This endpoint returns a table-like JSON. We must locate the "融資餘額" total row.
            # Because schemas vary, we do conservative parsing:
            # - Search any nested list rows for a cell containing "融資餘額" or "融資餘額(元/億)" is inconsistent.
            # - If cannot reliably find, skip.
            data = j.get("data") or j.get("tables") or None
            if data is None:
                continue

            # Flatten candidate rows (list of lists)
            candidates: List[List[Any]] = []
            if isinstance(data, list):
                # sometimes data is directly rows
                if data and all(isinstance(x, list) for x in data):
                    candidates = data
                else:
                    # sometimes tables->[{fields, data}]
                    for t in data:
                        if isinstance(t, dict) and isinstance(t.get("data"), list):
                            for rr in t["data"]:
                                if isinstance(rr, list):
                                    candidates.append(rr)

            if not candidates:
                continue

            # Heuristic: pick the row that contains "合計" and has a numeric cell that looks like balance.
            # Without a stable schema, we mark as unreliable if not found.
            found_val: Optional[float] = None
            for rr in candidates:
                joined = " ".join([str(x) for x in rr])
                if "合計" in joined or "總計" in joined:
                    # try find last numeric as balance
                    nums = [to_float(x) for x in rr]
                    nums2 = [x for x in nums if x is not None]
                    if nums2:
                        found_val = nums2[-1]
                        break

            if found_val is None:
                continue

            rows.append({"date": d.isoformat(), "margin_balance_100m": found_val})
            success = True
            source_url = url
            break

        if len(rows) >= min_rows:
            rows = ensure_desc_by_date(rows)
            return SeriesResult(
                market=market,
                source=source,
                source_url=source_url,  # last successful URL
                data_date=rows[0]["date"] if rows else None,
                rows=rows,
                notes=notes,
            )

        if not success:
            continue

    notes.append("官方 TWSE 端點嘗試失敗或無法可靠解析合計融資餘額（可能 API/欄位已變更）。")
    return SeriesResult(
        market=market,
        source=source,
        source_url=TWSE_OFFICIAL_FALLBACKS[0].format(yyyymmdd=f"{date.today():%Y%m%d}"),
        data_date=None,
        rows=[],
        notes=notes,
    )


def fetch_official_tpex_series(min_rows: int) -> SeriesResult:
    """
    Best-effort: try recent calendar days and parse CSV if available.
    """
    market = "TPEX"
    source = "TPEX官方(OpenData/CSV)"
    notes: List[str] = []
    rows: List[Dict[str, Any]] = []

    today = date.today()
    last_url_used = TPEX_OFFICIAL_FALLBACKS[0].format(**roc_date_parts(today))
    for back in range(0, 60):
        d = today.fromordinal(today.toordinal() - back)
        parts = roc_date_parts(d)

        success = False
        for tpl in TPEX_OFFICIAL_FALLBACKS:
            url = tpl.format(**parts)
            try:
                txt = http_get(url).text
            except Exception:
                continue

            # Read CSV: some endpoints return BOM or extra lines.
            try:
                df = pd.read_csv(pd.io.common.StringIO(txt), header=0)
            except Exception:
                continue

            # Try to locate a column containing "融資餘額" and a total row.
            cols = [str(c) for c in df.columns]
            bal_col = None
            for c in cols:
                if "融資餘額" in c:
                    bal_col = c
                    break
            if bal_col is None:
                continue

            # total row heuristic: any row containing "合計" in first column
            found_val: Optional[float] = None
            for _, r in df.iterrows():
                first = str(r.iloc[0])
                if "合計" in first or "總計" in first:
                    found_val = to_float(r.get(bal_col))
                    break

            if found_val is None:
                continue

            rows.append({"date": d.isoformat(), "margin_balance_100m": found_val})
            last_url_used = url
            success = True
            break

        if success and len(rows) >= min_rows:
            rows = ensure_desc_by_date(rows)
            return SeriesResult(
                market=market,
                source=source,
                source_url=last_url_used,
                data_date=rows[0]["date"] if rows else None,
                rows=rows,
                notes=notes,
            )

    notes.append("官方 TPEX 端點嘗試失敗或無法可靠解析合計融資餘額（可能 CSV 格式/欄位已變更）。")
    return SeriesResult(
        market=market,
        source=source,
        source_url=last_url_used,
        data_date=None,
        rows=[],
        notes=notes,
    )


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_rows", type=int, default=21)
    args = ap.parse_args()

    min_rows = int(args.min_rows)

    # TWSE: WantGoo first
    twse = parse_wantgoo_market_page(WANTGOO_TWSE_URL, "TWSE", min_rows)
    if len(twse.rows) < min_rows:
        # fallback official
        off = fetch_official_twse_series(min_rows)
        twse.notes.append("降級：WantGoo 不足以提供 min_rows；改用官方來源。")
        # use official only if it actually yields something
        if off.rows:
            twse = off
        else:
            # keep WantGoo (even if short), but record that official also failed
            twse.notes.extend(off.notes)

    # TPEX: try WantGoo guesses first; if all fail -> official
    tpex_best: Optional[SeriesResult] = None
    for u in WANTGOO_TPEX_GUESSES:
        r = parse_wantgoo_market_page(u, "TPEX", min_rows)
        if r.rows:
            tpex_best = r
            break
    if tpex_best is None or len(tpex_best.rows) < min_rows:
        off = fetch_official_tpex_series(min_rows)
        if tpex_best:
            tpex_best.notes.append("降級：WantGoo 不足以提供 min_rows；改用官方來源。")
        if off.rows:
            tpex = off
        else:
            tpex = tpex_best or SeriesResult(
                market="TPEX",
                source="WantGoo/Official",
                source_url=";".join(WANTGOO_TPEX_GUESSES),
                data_date=None,
                rows=[],
                notes=["WantGoo(猜測URL)與官方來源皆無法可靠取得。"] + off.notes,
            )
    else:
        tpex = tpex_best

    out = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "series": {
            "TWSE": {
                "source": twse.source,
                "source_url": twse.source_url,
                "data_date": twse.data_date,
                "rows": twse.rows[: max(min_rows, len(twse.rows))],
                "notes": twse.notes,
            },
            "TPEX": {
                "source": tpex.source,
                "source_url": tpex.source_url,
                "data_date": tpex.data_date,
                "rows": tpex.rows[: max(min_rows, len(tpex.rows))],
                "notes": tpex.notes,
            },
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()