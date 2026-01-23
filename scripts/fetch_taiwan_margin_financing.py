#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from lxml import html


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# ✅ HiStock 正確端點
HISTOCK_TWSE_URL = "https://histock.tw/stock/three.aspx?m=mg"         # 上市
HISTOCK_TPEX_URL = "https://histock.tw/stock/three.aspx?m=mg&no=TWOI" # 上櫃（關鍵修正）


@dataclass
class Row:
    date: str          # YYYY-MM-DD
    balance_yi: float  # 融資餘額(億)
    chg_yi: float      # 融資增加(億)（可正可負）


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: str) -> Optional[float]:
    x = x.strip().replace(",", "")
    if x in ("", "-", "—", "NA", "N/A", "null", "None"):
        return None
    try:
        return float(x)
    except Exception:
        return None


def _http_get(url: str, timeout: int = 20) -> Tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _infer_year_for_mmdd_rows(mmdd_list: List[str], now_local_year: int) -> List[str]:
    """
    mmdd_list: ["01/22","01/21","12/31",...] 預期為「由新到舊」
    規則：往回走時若月份從 1 跳到 12（數字變大），代表跨年，year -= 1
    """
    out: List[str] = []
    year = now_local_year
    prev_m: Optional[int] = None
    for mmdd in mmdd_list:
        m, d = mmdd.split("/")
        m_i = int(m)
        d_i = int(d)
        if prev_m is not None and m_i > prev_m:
            year -= 1
        out.append(f"{year:04d}-{m_i:02d}-{d_i:02d}")
        prev_m = m_i
    return out


def _parse_histock_table(page_html: str, now_local_year: int) -> Tuple[List[Row], List[str]]:
    """
    HiStock 頁面內有一張「近三十日...」表，欄位包含：
    日期、融資餘額(億)、融資增加(億)
    """
    notes: List[str] = []
    doc = html.fromstring(page_html)

    # 嘗試抓表格列（用文字內容匹配欄位名）
    tables = doc.xpath("//table")
    if not tables:
        return [], ["找不到任何 table（可能改版）"]

    target_rows: List[Tuple[str, str, str]] = []
    header_hit = False

    for tb in tables:
        # 把這張表的文字做一次掃描，判斷是否為目標表
        txt = " ".join([t.strip() for t in tb.xpath(".//text()") if t.strip()])
        if ("融資餘額" not in txt) or ("融資增加" not in txt):
            continue

        # 抓 tr
        trs = tb.xpath(".//tr")
        for tr in trs:
            cells = [c.strip() for c in tr.xpath(".//th//text() | .//td//text()") if c.strip()]
            if not cells:
                continue
            if ("融資餘額" in " ".join(cells)) and ("融資增加" in " ".join(cells)):
                header_hit = True
                continue
            # 目標資料列常見格式：["01/22","3717.3","39.9", ...]
            if re.match(r"^\d{2}/\d{2}$", cells[0]) and len(cells) >= 3:
                target_rows.append((cells[0], cells[1], cells[2]))

        if header_hit and target_rows:
            break

    if not target_rows:
        return [], ["找不到目標資料列（表格結構可能變更）"]

    mmdd = [r[0] for r in target_rows]
    dates = _infer_year_for_mmdd_rows(mmdd, now_local_year=now_local_year)

    out: List[Row] = []
    for (d_mmdd, bal_s, chg_s), d_iso in zip(target_rows, dates):
        bal = _safe_float(bal_s)
        chg = _safe_float(chg_s)
        if bal is None or chg is None:
            continue
        out.append(Row(date=d_iso, balance_yi=bal, chg_yi=chg))

    if not out:
        notes.append("資料列存在但數值無法解析（可能是格式改變）")

    return out, notes


def _rows_signature(rows: List[Row], n: int = 10) -> List[Tuple[str, float, float]]:
    sig: List[Tuple[str, float, float]] = []
    for r in rows[:n]:
        sig.append((r.date, float(r.balance_yi), float(r.chg_yi)))
    return sig


def _build_series(market: str, url: str, min_rows: int, now_local_year: int) -> Dict[str, Any]:
    series: Dict[str, Any] = {
        "source": "HiStock",
        "source_url": url,
        "data_date": None,
        "rows": [],
        "notes": [],
    }

    page, err = _http_get(url)
    if err:
        series["notes"].append(f"HTTP 取得失敗：{err}")
        return series

    rows, notes = _parse_histock_table(page, now_local_year=now_local_year)
    series["notes"].extend(notes)

    if len(rows) < min_rows:
        series["notes"].append(f"交易日列數不足：{len(rows)} < min_rows={min_rows}")

    # 由新到舊（HiStock 通常已是新到舊；保險再排一次）
    rows = sorted(rows, key=lambda x: x.date, reverse=True)

    if rows:
        series["data_date"] = rows[0].date
        series["rows"] = [{"date": r.date, "balance_yi": r.balance_yi, "chg_yi": r.chg_yi} for r in rows]

    return series


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_rows", type=int, default=21)
    args = ap.parse_args()

    # 以 Asia/Taipei 的「今年」做跨年推斷基準（簡化：用 UTC+8 的 year）
    now_local_year = (datetime.now(timezone.utc).timestamp() + 8 * 3600)
    now_local_year = datetime.fromtimestamp(now_local_year, tz=timezone.utc).year

    twse = _build_series("TWSE", HISTOCK_TWSE_URL, args.min_rows, now_local_year)
    tpex = _build_series("TPEX", HISTOCK_TPEX_URL, args.min_rows, now_local_year)

    # ✅ 防呆：若兩邊 rows 幾乎完全相同，判定 TPEX 抓錯（你目前遇到的狀況）
    twse_rows = twse.get("rows", [])
    tpex_rows = tpex.get("rows", [])
    if twse_rows and tpex_rows:
        if _rows_signature([Row(**r) for r in twse_rows], 10) == _rows_signature([Row(**r) for r in tpex_rows], 10):
            tpex["notes"].append("防呆觸發：TPEX 與 TWSE 前 10 筆完全相同，疑似抓到同一市場頁面；TPEX 置為 NA 以避免假 OK。")
            tpex["data_date"] = None
            tpex["rows"] = []

    out = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": _utc_now_iso(),
        "series": {"TWSE": twse, "TPEX": tpex},
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()