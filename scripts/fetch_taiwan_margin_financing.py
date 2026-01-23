#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheme2 (HiStock-only) fetcher for TWSE/TPEX margin financing.

Key points:
- Parse dates incl. MM/DD without year.
- Parse numeric cells that may include units.
- Map change column to HiStock's "融資增加(億)" (or similar), not "增減".
- Still safe if change column missing: keep chg_yi=None.
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
    if isinstance(c, tuple):
        return " ".join([str(x).strip() for x in c if str(x).strip()]).strip()
    return str(c).strip()


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "NA", "—", "-", "–", "None", "nan"):
        return None
    s = s.replace(",", "")
    s2 = re.sub(r"[^0-9\.\+\-]", "", s)
    if s2 in ("", "+", "-"):
        return None
    try:
        return float(s2)
    except Exception:
        return None


def _norm_date(s: Any, tz: str = "Asia/Taipei") -> Optional[str]:
    if s is None:
        return None
    ss = str(s).strip()
    if not ss:
        return None

    m = re.search(r"(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})", ss)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    m2 = re.search(r"^(\d{1,2})[\/\-.](\d{1,2})$", ss)
    if m2:
        mo, d = int(m2.group(1)), int(m2.group(2))
        now_local = datetime.now(ZoneInfo(tz))
        y = now_local.year
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


def _find_cols(cols: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (date_col, balance_col, change_col) based on HiStock column naming.

    Observed:
      日期 | 融資餘額(億) | 融資增加(億) | ...
    """
    date_col = next((c for c in cols if "日期" in c), None)

    bal_col = None
    for c in cols:
        if ("融資" in c and "餘額" in c):
            bal_col = c
            break
    if bal_col is None:
        bal_col = next((c for c in cols if "融資" in c), None)

    chg_col = None
    # prefer explicit "融資增加" / "融資減少"
    for c in cols:
        if ("融資" in c) and (("增加" in c) or ("減少" in c) or ("增減" in c) or ("變動" in c)):
            chg_col = c
            break
    # fallback generic
    if chg_col is None:
        for c in cols:
            if ("增加" in c) or ("減少" in c) or ("增減" in c) or ("變動" in c):
                chg_col = c
                break

    return date_col, bal_col, chg_col


def parse_histock(html: str) -> Tuple[Optional[str], List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    rows: List[Dict[str, Any]] = []

    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except Exception as e:
        return None, [], [f"HiStock 解析失敗：{type(e).__name__}: {e}"]

    if not tables:
        return None, [], ["HiStock 找不到任何表格（read_html=0 tables）"]

    # pick first table containing 日期 + 融資
    target = None
    for df in tables:
        cols = [_col_to_str(c) for c in df.columns]
        joined = " ".join(cols)
        if ("日期" in joined) and ("融資" in joined):
            target = df
            break

    if target is None:
        return None, [], ["HiStock：無法定位含『日期』+『融資』的資料表"]

    df = target.copy()
    df.columns = [_col_to_str(c) for c in df.columns]
    cols = list(df.columns)

    notes.append("HiStock 欄位：" + " | ".join(cols[:40]))

    date_col, bal_col, chg_col = _find_cols(cols)
    if date_col is None or bal_col is None:
        return None, [], ["HiStock：找不到必要欄位（日期/融資餘額）"] + notes

    if chg_col is None:
        notes.append("HiStock：找不到『融資增加/減少/變動』欄，chg_yi 將輸出 NA")

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
        rows.append(
            {
                "date": d,
                "balance_yi": float(bal),
                "chg_yi": float(chg) if chg is not None else None,
            }
        )

    rows.sort(key=lambda x: x["date"], reverse=True)
    data_date = rows[0]["date"] if rows else None
    return data_date, rows, notes


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
            "TWSE": {"source": "NA", "source_url": "NA", "data_date": None, "rows": [], "notes": []},
            "TPEX": {"source": "NA", "source_url": "NA", "data_date": None, "rows": [], "notes": []},
        },
    }

    def set_series(mkt: str, url: str, html: Optional[str], err: Optional[str]) -> None:
        if err or not html:
            out["series"][mkt] = {
                "source": "HiStock",
                "source_url": url,
                "data_date": None,
                "rows": [],
                "notes": [err or "HiStock 空回應"],
            }
            return

        dd, rows, notes = parse_histock(html)
        if len(rows) < args.min_rows:
            notes.append(f"HiStock {mkt} rows 不足以提供 min_rows={args.min_rows}（實得 {len(rows)}）")
        notes.append("Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。")

        out["series"][mkt] = {
            "source": "HiStock",
            "source_url": url,
            "data_date": dd,
            "rows": rows,
            "notes": notes,
        }

    html, err = http_get(HISTOCK_TWSE_URL)
    set_series("TWSE", HISTOCK_TWSE_URL, html, err)

    html, err = http_get(HISTOCK_TPEX_URL)
    set_series("TPEX", HISTOCK_TPEX_URL, html, err)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()