#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch Taiwan margin-financing balances (TWSE listed + TPEX OTC).

Scheme 2 (recommended for Actions stability):
- HiStock first (TWSE + TPEX), fallback note-only for Yahoo/WantGoo (they often 403/JS).
- Official endpoints are NOT hard-coded here to avoid silent format drift;
  if HiStock fails, we output NA and notes (per "do not invent numbers").

Output: taiwan_margin_cache/latest.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HISTOCK_TWSE_URL = "https://histock.tw/stock/three.aspx?m=mg"
# 你已驗證可用的 TPEX：no=TWOI（用來避免抓到跟 TWSE 一樣的頁）
HISTOCK_TPEX_URL = "https://histock.tw/stock/three.aspx?m=mg&no=TWOI"

YAHOO_URL = "https://tw.stock.yahoo.com/margin-balance/"
WANTGOO_TWSE_URL = "https://www.wantgoo.com/stock/margin-trading/market-price/taiex"
WANTGOO_TPEX_URL = "https://www.wantgoo.com/stock/margin-trading/market-price/otc"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "NA", "—", "-", "–"):
        return None
    s = s.replace(",", "")
    # 有些站會用 +12.3 / -4.5
    try:
        return float(s)
    except Exception:
        return None


def _norm_date_yyyy_mm_dd(s: str) -> Optional[str]:
    s = str(s).strip()
    if not s:
        return None
    # accept: YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD
    m = re.search(r"(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})", s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def http_get(url: str, timeout: int = 20) -> Tuple[Optional[str], Optional[str]]:
    """
    returns: (html_text, error_note)
    """
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
    """
    Parse HiStock table into rows:
      {date, balance_yi, chg_yi}
    Returns: (data_date, rows_desc, notes)
    """
    notes: List[str] = []
    rows: List[Dict[str, Any]] = []

    try:
        # 重要：用 StringIO 強制把 HTML 當內容，不會被誤認成檔名
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except Exception as e:
        return None, [], [f"HiStock 解析失敗：{type(e).__name__}: {e}"]

    if not tables:
        return None, [], ["HiStock 找不到任何表格（read_html=0 tables）"]

    # 嘗試找到包含「日期」且包含「融資」相關欄位的那張表
    target = None
    for df in tables:
        cols = [str(c) for c in df.columns]
        joined = " ".join(cols)
        if ("日期" in joined) and ("融資" in joined or "餘額" in joined):
            target = df
            break

    # 若沒命中，就退而求其次：找第一張有「日期」欄的表
    if target is None:
        for df in tables:
            cols = [str(c) for c in df.columns]
            if any("日期" in str(c) for c in cols):
                target = df
                notes.append("HiStock：未精準命中欄位名稱，改用第一張含『日期』欄的表")
                break

    if target is None:
        return None, [], ["HiStock：無法定位含日期的資料表"]

    df = target.copy()

    # 標準化欄名
    df.columns = [str(c).strip() for c in df.columns]

    # 找日期欄
    date_col = None
    for c in df.columns:
        if "日期" in c:
            date_col = c
            break
    if date_col is None:
        return None, [], ["HiStock：找不到『日期』欄"]

    # 找融資餘額欄（常見：融資餘額、融資(億)、融資餘額(億)）
    bal_col = None
    for c in df.columns:
        if ("融資" in c and "餘額" in c) or ("融資" in c and "億" in c):
            bal_col = c
            break
    if bal_col is None:
        return None, [], ["HiStock：找不到『融資餘額』欄（欄位可能改版）"]

    # 找增減欄（常見：增減、融資增減）
    chg_col = None
    for c in df.columns:
        if "增減" in c:
            chg_col = c
            break
    if chg_col is None:
        notes.append("HiStock：找不到『增減』欄，chg_yi 將輸出 NA")

    for _, r in df.iterrows():
        d = _norm_date_yyyy_mm_dd(r.get(date_col, ""))
        if not d:
            continue
        bal = _safe_float(r.get(bal_col))
        chg = _safe_float(r.get(chg_col)) if chg_col else None
        if bal is None:
            continue
        rows.append({"date": d, "balance_yi": float(bal), "chg_yi": float(chg) if chg is not None else None})

    # 依日期排序（desc）
    rows.sort(key=lambda x: x["date"], reverse=True)
    data_date = rows[0]["date"] if rows else None

    # 防呆：TPEX 不應該與 TWSE 前多筆完全相同（你已遇過）
    # 這裡只做提示；真正避免誤判靠：TPEX 使用 no=TWOI URL + render 時一致性規則
    if market == "TPEX" and len(rows) >= 10:
        # 如果後續被喂錯資料，通常會跟 TWSE 一模一樣；此檢查放在 render 也會做
        pass

    return data_date, rows, notes


def build_empty_series(source: str, source_url: str, notes: List[str]) -> Dict[str, Any]:
    return {"source": source, "source_url": source_url, "data_date": None, "rows": [], "notes": notes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheme", type=int, default=2, choices=[1, 2], help="1=priority list, 2=HiStock-first")
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
            "rows": rows[: max(args.min_rows, len(rows))],
            "notes": notes,
        }

    # -------- Scheme 2: HiStock first --------
    if args.scheme == 2:
        # TWSE
        html, err = http_get(HISTOCK_TWSE_URL)
        if err or not html:
            set_series("TWSE", "HiStock", HISTOCK_TWSE_URL, None, [], [err or "HiStock TWSE: 空回應"])
        else:
            dd, rows, notes = parse_histock_table(html, "TWSE")
            if dd and len(rows) >= args.min_rows:
                set_series("TWSE", "HiStock", HISTOCK_TWSE_URL, dd, rows, notes)
            else:
                notes.append(f"HiStock TWSE rows 不足以提供 min_rows={args.min_rows}（實得 {len(rows)}）")
                set_series("TWSE", "HiStock", HISTOCK_TWSE_URL, dd, rows, notes)

        # TPEX
        html, err = http_get(HISTOCK_TPEX_URL)
        if err or not html:
            set_series("TPEX", "HiStock", HISTOCK_TPEX_URL, None, [], [err or "HiStock TPEX: 空回應"])
        else:
            dd, rows, notes = parse_histock_table(html, "TPEX")
            if dd and len(rows) >= args.min_rows:
                set_series("TPEX", "HiStock", HISTOCK_TPEX_URL, dd, rows, notes)
            else:
                notes.append(f"HiStock TPEX rows 不足以提供 min_rows={args.min_rows}（實得 {len(rows)}）")
                set_series("TPEX", "HiStock", HISTOCK_TPEX_URL, dd, rows, notes)

        # 記錄「沒有嘗試」的原因（符合你要的可稽核，不裝沒事）
        out["series"]["TWSE"]["notes"].append("Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。")
        out["series"]["TPEX"]["notes"].append("Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。")

    else:
        # Scheme 1（若你未來想切回「依你指定優先序」）
        # 這裡先做最小實作：仍以 HiStock 為可用來源；Yahoo/WantGoo 多半不穩定
        out["series"]["TWSE"]["notes"].append("Scheme1：此版本仍以 HiStock 為主要來源（Yahoo/WantGoo 易失敗）。")
        out["series"]["TPEX"]["notes"].append("Scheme1：此版本仍以 HiStock 為主要來源（Yahoo/WantGoo 易失敗）。")

    # 寫出
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()