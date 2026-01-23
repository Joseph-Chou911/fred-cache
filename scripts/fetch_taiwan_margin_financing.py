#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch Taiwan margin-financing balances (TWSE listed + TPEX OTC).

Scheme 2: HiStock-first (stable for GitHub Actions).
- Do NOT invent numbers.
- If parsing fails, emit NA + notes for audit.

Output: taiwan_margin_cache/latest.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from zoneinfo import ZoneInfo


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HISTOCK_TWSE_URL = "https://histock.tw/stock/three.aspx?m=mg"
HISTOCK_TPEX_URL = "https://histock.tw/stock/three.aspx?m=mg&no=TWOI"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _col_to_str(c: Any) -> str:
    """
    Handle normal columns and MultiIndex columns.
    """
    if isinstance(c, tuple):
        return " ".join([str(x).strip() for x in c if str(x).strip() != ""]).strip()
    return str(c).strip()


def _safe_float(x: Any) -> Optional[float]:
    """
    Accept values like:
      "3,717.3", "3,717.3 億", " +39.9", "-34.8", "—"
    Strip anything not digit/dot/plus/minus.
    """
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "NA", "—", "-", "–", "None", "nan"):
        return None
    s = s.replace(",", "")
    # keep only 0-9 . + -
    s2 = re.sub(r"[^0-9\.\+\-]", "", s)
    if s2 in ("", "+", "-"):
        return None
    try:
        return float(s2)
    except Exception:
        return None


def _norm_date(s: Any, tz: str = "Asia/Taipei") -> Optional[str]:
    """
    Accept:
      YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD
      MM/DD or M/D (HiStock sometimes shows without year)
    For MM/DD, infer year from 'today' in Asia/Taipei:
      - base_year = today.year
      - if month > today.month + 1 => treat as previous year (year boundary)
    """
    if s is None:
        return None
    ss = str(s).strip()
    if not ss:
        return None

    # YYYY/MM/DD style
    m = re.search(r"(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})", ss)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # MM/DD style
    m2 = re.search(r"^(\d{1,2})[\/\-.](\d{1,2})$", ss)
    if m2:
        mo, d = int(m2.group(1)), int(m2.group(2))
        now_local = datetime.now(ZoneInfo(tz))
        y = now_local.year
        # year boundary guard (e.g., Jan抓到12/31)
        if mo > now_local.month + 1:
            y -= 1
        return f"{y:04d}-{mo:02d}-{d:02d}"

    return None


def http_get(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            timeout=timeout,
        )
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text, None
    except Exception as e:
        return None, f"HTTP 取得失敗：{type(e).__name__}: {e}"


def parse_histock_table(html: str, market: str) -> Tuple[Optional[str], List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    rows: List[Dict[str, Any]] = []

    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except Exception as e:
        return None, [], [f"HiStock 解析失敗：{type(e).__name__}: {e}"]

    if not tables:
        return None, [], ["HiStock 找不到任何表格（read_html=0 tables）"]

    target = None
    target_cols: List[str] = []
    for df in tables:
        cols = [_col_to_str(c) for c in df.columns]
        joined = " ".join(cols)
        if ("日期" in joined) and ("融資" in joined or "餘額" in joined):
            target = df
            target_cols = cols
            break

    if target is None:
        for df in tables:
            cols = [_col_to_str(c) for c in df.columns]
            if any("日期" in c for c in cols):
                target = df
                target_cols = cols
                notes.append("HiStock：未精準命中欄位名稱，改用第一張含『日期』欄的表")
                break

    if target is None:
        return None, [], ["HiStock：無法定位含日期的資料表"]

    df = target.copy()
    # normalize columns (keep original mapping)
    col_map = {c: _col_to_str(c) for c in df.columns}
    df.rename(columns=col_map, inplace=True)
    cols = list(df.columns)

    # debug columns
    notes.append("HiStock 欄位：" + " | ".join(cols[:30]))

    date_col = next((c for c in cols if "日期" in c), None)
    if date_col is None:
        return None, [], ["HiStock：找不到『日期』欄（欄名可能改版）"] + notes

    # balance column: be more tolerant
    bal_col = None
    for c in cols:
        if ("融資" in c and "餘額" in c) or ("融資餘額" in c) or ("融資" in c and "億" in c):
            bal_col = c
            break
    if bal_col is None:
        # last resort: any column containing 融資
        bal_col = next((c for c in cols if "融資" in c), None)
    if bal_col is None:
        return None, [], ["HiStock：找不到『融資餘額』相關欄位（欄位可能改版）"] + notes

    # change column: tolerant match
    chg_col = None
    for c in cols:
        if ("增減" in c) or ("變動" in c) or ("增幅" in c):
            chg_col = c
            break
    if chg_col is None:
        notes.append("HiStock：找不到『增減/變動』欄，chg_yi 將輸出 NA")

    # debug first few raw dates
    raw_dates = [str(x) for x in df[date_col].head(5).tolist()]
    notes.append("HiStock 原始日期樣本：" + ", ".join(raw_dates))

    for _, r in df.iterrows():
        d = _norm_date(r.get(date_col, None))
        if not d:
            continue
        bal = _safe_float(r.get(bal_col, None))
        if bal is None:
            continue
        chg = _safe_float(r.get(chg_col, None)) if chg_col else None
        rows.append({"date": d, "balance_yi": float(bal), "chg_yi": float(chg) if chg is not None else None})

    rows.sort(key=lambda x: x["date"], reverse=True)
    data_date = rows[0]["date"] if rows else None

    if not rows:
        notes.append("HiStock：解析後 rows=0（常見原因：日期無年份/MM-DD 格式或數值含單位未清除）")

    return data_date, rows, notes


def build_empty_series(source: str, source_url: str, notes: List[str]) -> Dict[str, Any]:
    return {"source": source, "source_url": source_url, "data_date": None, "rows": [], "notes": notes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheme", type=int, default=2, choices=[2])
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_rows", type=int, default=21)
    args = ap.parse_args()

    out: Dict[str, Any] = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": now_utc_iso(),
        "series": {
            "TWSE": build_empty_series("NA", "NA", []),
            "TPEX": build_empty_series("NA", "NA", []),
        },
    }

    def set_series(mkt: str, source: str, url: str, data_date: Optional[str], rows: List[Dict[str, Any]], notes: List[str]) -> None:
        out["series"][mkt] = {
            "source": source,
            "source_url": url,
            "data_date": data_date,
            "rows": rows,
            "notes": notes,
        }

    # TWSE
    html, err = http_get(HISTOCK_TWSE_URL)
    if err or not html:
        set_series("TWSE", "HiStock", HISTOCK_TWSE_URL, None, [], [err or "HiStock TWSE: 空回應"])
    else:
        dd, rows, notes = parse_histock_table(html, "TWSE")
        if dd and len(rows) >= args.min_rows:
            set_series("TWSE", "HiStock", HISTOCK_TWSE_URL, dd, rows[: args.min_rows * 2], notes)
        else:
            notes.append(f"HiStock TWSE rows 不足以提供 min_rows={args.min_rows}（實得 {len(rows)}）")
            set_series("TWSE", "HiStock", HISTOCK_TWSE_URL, dd, rows[: args.min_rows * 2], notes)

    # TPEX
    html, err = http_get(HISTOCK_TPEX_URL)
    if err or not html:
        set_series("TPEX", "HiStock", HISTOCK_TPEX_URL, None, [], [err or "HiStock TPEX: 空回應"])
    else:
        dd, rows, notes = parse_histock_table(html, "TPEX")
        if dd and len(rows) >= args.min_rows:
            set_series("TPEX", "HiStock", HISTOCK_TPEX_URL, dd, rows[: args.min_rows * 2], notes)
        else:
            notes.append(f"HiStock TPEX rows 不足以提供 min_rows={args.min_rows}（實得 {len(rows)}）")
            set_series("TPEX", "HiStock", HISTOCK_TPEX_URL, dd, rows[: args.min_rows * 2], notes)

    out["series"]["TWSE"]["notes"].append("Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。")
    out["series"]["TPEX"]["notes"].append("Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()