#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


YAHOO_MARGIN_BALANCE_URL = "https://tw.stock.yahoo.com/margin-balance/"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "-", "—", "NA", "N/A", "null", "None"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    # pandas.read_html 有時會給 MultiIndex 欄位
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["".join([str(c) for c in col if str(c) != "nan"]).strip() for col in df.columns.values]
    else:
        df.columns = [str(c).strip() for c in df.columns]
    return df


def _pick_financing_cols(df: pd.DataFrame) -> Tuple[str, str, str]:
    # 尋找「日期 / 融資增減 / 融資餘額」欄位
    date_col = None
    delta_col = None
    bal_col = None

    for c in df.columns:
        if date_col is None and ("日期" in c):
            date_col = c

    # 可能是 "融資增減(億)" / "融資增減" / "融資增減(億)"（MultiIndex flatten 後）
    for c in df.columns:
        if delta_col is None and ("融資" in c and "增減" in c):
            delta_col = c
        if bal_col is None and ("融資" in c and "餘額" in c):
            bal_col = c

    if not (date_col and delta_col and bal_col):
        raise ValueError(f"無法辨識必要欄位：date={date_col}, delta={delta_col}, bal={bal_col}; cols={list(df.columns)}")

    return date_col, delta_col, bal_col


def _fetch_html(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "close",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def _parse_yahoo_tables(html: str) -> Dict[str, List[Dict[str, Any]]]:
    # 讀出頁面上所有 tables（通常：集中市場表一張、櫃買市場表一張）
    dfs = pd.read_html(StringIO(html))
    out: Dict[str, List[Dict[str, Any]]] = {}

    # 過濾掉不相關 table：以是否包含「日期」「融資」「餘額」來判定
    candidates: List[pd.DataFrame] = []
    for df in dfs:
        df = _flatten_columns(df)
        cols = " ".join(df.columns)
        if ("日期" in cols) and ("融資" in cols) and ("餘額" in cols) and ("增減" in cols):
            candidates.append(df)

    if len(candidates) < 2:
        raise ValueError(f"Yahoo table 數量不足（預期>=2：集中+櫃買），實際={len(candidates)}")

    # 依頁面常見順序：第 1 張 = 集中市場(TWSE)，第 2 張 = 櫃買市場(TPEX)
    mapping = [("TWSE", candidates[0]), ("TPEX", candidates[1])]

    for market, df in mapping:
        date_col, delta_col, bal_col = _pick_financing_cols(df)
        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            d = str(r[date_col]).strip()
            # 日期格式通常是 YYYY/MM/DD
            if not re.match(r"^\d{4}/\d{2}/\d{2}$", d):
                continue
            delta = _to_float(r[delta_col])
            bal = _to_float(r[bal_col])
            rows.append({"date": d, "financing_change_bil": delta, "financing_balance_bil": bal})

        if not rows:
            raise ValueError(f"{market} 解析後 rows 為空")

        out[market] = rows

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_rows", type=int, default=21)
    args = ap.parse_args()

    payload: Dict[str, Any] = {
        "schema_version": "taiwan_margin_financing_latest_v1",
        "generated_at_utc": _utc_now_iso(),
        "series": {
            "TWSE": {"source": None, "source_url": None, "data_date": None, "rows": [], "notes": []},
            "TPEX": {"source": None, "source_url": None, "data_date": None, "rows": [], "notes": []},
        },
    }

    try:
        html = _fetch_html(YAHOO_MARGIN_BALANCE_URL)
        parsed = _parse_yahoo_tables(html)

        for market in ("TWSE", "TPEX"):
            rows = parsed[market][: max(args.min_rows, 1)]
            payload["series"][market]["source"] = "Yahoo"
            payload["series"][market]["source_url"] = YAHOO_MARGIN_BALANCE_URL
            payload["series"][market]["rows"] = rows
            payload["series"][market]["data_date"] = rows[0]["date"] if rows else None

            if len(rows) < args.min_rows:
                payload["series"][market]["notes"].append(
                    f"Yahoo 可用交易日筆數不足：rows={len(rows)} < min_rows={args.min_rows}；後續 5D/20D 可能為 NA"
                )

    except Exception as e:
        # 失敗就留下可追溯訊息，不要 silent fail
        for market in ("TWSE", "TPEX"):
            payload["series"][market]["source"] = "Yahoo"
            payload["series"][market]["source_url"] = YAHOO_MARGIN_BALANCE_URL
            payload["series"][market]["notes"].append(f"Yahoo 解析失敗：{type(e).__name__}: {e}")

    # 寫出（確保就算抓不到也會有 latest.json，可 commit 可追查）
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()