#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plan B (HiStock) fetcher for Taiwan margin financing balances.

Outputs:
- taiwan_margin_cache/latest.json

We fetch BOTH:
- TWSE (listed): https://histock.tw/stock/three.aspx?m=mg
- TPEX (OTC):    https://histock.tw/stock/three.aspx?m=mg&o=otc

We extract at least `min_rows` recent trading-day rows (if available).
Each row contains:
- date (YYYY-MM-DD)
- balance_yi (億)
- chg_yi (億)  (融資增加(億), can be negative)

Stop-rule friendly:
- If parsing fails, write rows=[] and put error notes.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_json(path: str, obj: Any) -> None:
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    return s


def _get_with_retry(url: str, timeout: int = 20, retries: int = 4, backoff: float = 1.2) -> str:
    s = _session()
    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            r = s.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            time.sleep(backoff * (2 ** i))
    raise RuntimeError(f"HTTP 取得失敗：{type(last_err).__name__}: {last_err}")


def _to_float(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    s = s.replace(",", "")
    # allow "—" or non-numeric
    try:
        return float(s)
    except Exception:
        return None


def _infer_year(month: int, day: int, today: datetime) -> int:
    """
    Table shows MM/DD without year. Infer year using "today" (local timezone handled by runner TZ env).
    Heuristic:
    - Normally use current year.
    - If today is Jan/Feb and month is Nov/Dec, it's last year.
    """
    y = today.year
    if today.month <= 2 and month >= 11:
        return y - 1
    return y


def _parse_histock_table(html: str, today: datetime, min_rows: int) -> Tuple[List[Dict[str, Any]], Optional[str], List[str]]:
    """
    Returns: (rows_desc, latest_date, notes)
    rows_desc: newest -> oldest
    """
    notes: List[str] = []
    soup = BeautifulSoup(html, "lxml")

    tables = soup.find_all("table")
    target = None

    def _headers_match(ths: List[str]) -> bool:
        # Must contain 日期 + 融資餘額 + 融資增加
        joined = " ".join(ths)
        return ("日期" in joined) and ("融資餘額" in joined) and ("融資增加" in joined)

    for t in tables:
        ths = [th.get_text(strip=True) for th in t.find_all("th")]
        if ths and _headers_match(ths):
            target = t
            break

    if target is None:
        # fallback: try to find by text blocks then parse line-wise
        text = soup.get_text("\n", strip=True)
        # Example line: 01/22 3,717.3 39.9 ...
        rx = re.compile(r"^\s*(\d{2})/(\d{2})\s+([\d,]+\.\d+|[\d,]+)\s+([\-]?[\d,]+\.\d+|[\-]?[\d,]+)\b")
        rows: List[Dict[str, Any]] = []
        for line in text.splitlines():
            m = rx.match(line)
            if not m:
                continue
            mm = int(m.group(1))
            dd = int(m.group(2))
            bal = _to_float(m.group(3))
            chg = _to_float(m.group(4))
            if bal is None or chg is None:
                continue
            yy = _infer_year(mm, dd, today)
            date_iso = f"{yy:04d}-{mm:02d}-{dd:02d}"
            rows.append({"date": date_iso, "balance_yi": round(bal, 2), "chg_yi": round(chg, 2)})
        if not rows:
            notes.append("HiStock 解析失敗：找不到包含「日期/融資餘額/融資增加」的表格或可解析列。")
            return [], None, notes
        # assume already newest->oldest on page; keep first ~30
        rows = rows[: max(min_rows, 30)]
        latest_date = rows[0]["date"] if rows else None
        return rows, latest_date, notes

    # parse rows from target table
    body_rows = target.find_all("tr")
    rows_out: List[Dict[str, Any]] = []
    for tr in body_rows:
        tds = tr.find_all("td")
        if not tds or len(tds) < 3:
            continue
        date_s = tds[0].get_text(strip=True)  # e.g., 01/22
        m = re.match(r"^(\d{2})/(\d{2})$", date_s)
        if not m:
            continue
        mm = int(m.group(1))
        dd = int(m.group(2))

        bal = _to_float(tds[1].get_text(strip=True))
        chg = _to_float(tds[2].get_text(strip=True))
        if bal is None or chg is None:
            continue

        yy = _infer_year(mm, dd, today)
        date_iso = f"{yy:04d}-{mm:02d}-{dd:02d}"
        rows_out.append({"date": date_iso, "balance_yi": round(bal, 2), "chg_yi": round(chg, 2)})

    if not rows_out:
        notes.append("HiStock 解析失敗：表格存在但未解析到有效資料列。")
        return [], None, notes

    rows_out = rows_out[: max(min_rows, 30)]
    latest_date = rows_out[0]["date"]
    return rows_out, latest_date, notes


def fetch_market(name: str, url: str, min_rows: int) -> Dict[str, Any]:
    today_local = datetime.now()  # runner uses TZ=Asia/Taipei in workflow env
    out: Dict[str, Any] = {
        "source": "HiStock",
        "source_url": url,
        "data_date": None,
        "rows": [],
        "notes": [],
    }
    try:
        html = _get_with_retry(url)
        rows, latest_date, notes = _parse_histock_table(html, today_local, min_rows=min_rows)
        out["rows"] = rows
        out["data_date"] = latest_date
        out["notes"].extend(notes)
        if len(rows) < min_rows:
            out["notes"].append(f"資料列不足：僅 {len(rows)} 列（min_rows={min_rows}）。")
    except Exception as e:
        out["notes"].append(str(e))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output latest.json path")
    ap.add_argument("--min_rows", type=int, default=21, help="minimum trading-day rows per market")
    args = ap.parse_args()

    twse_url = "https://histock.tw/stock/three.aspx?m=mg"
    tpex_url = "https://histock.tw/stock/three.aspx?m=mg&o=otc"

    twse = fetch_market("TWSE", twse_url, args.min_rows)
    tpex = fetch_market("TPEX", tpex_url, args.min_rows)

    obj = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": _now_utc_iso(),
        "series": {
            "TWSE": twse,
            "TPEX": tpex,
        },
    }
    _write_json(args.out, obj)


if __name__ == "__main__":
    main()