#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SCHEMA_LATEST = "taiwan_margin_financing_latest_v1"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_env_timezone() -> str:
    # Used only for "today" baseline (year inference).
    return os.environ.get("TIMEZONE", "Asia/Taipei")


def _parse_float_maybe(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.upper() == "NA" or s == "-" or s.lower() == "nan":
        return None
    # Remove commas, spaces
    s = s.replace(",", "").replace(" ", "")
    # Keep sign/decimal
    try:
        return float(s)
    except Exception:
        # Sometimes like "▲12.3" / "▼-12.3"
        s2 = re.sub(r"[^\d\.\-\+]", "", s)
        try:
            return float(s2) if s2 else None
        except Exception:
            return None


def _infer_year_for_mmdd(mmdd: str, today_local: datetime) -> Optional[str]:
    """
    Convert "MM/DD" to "YYYY-MM-DD" by inferring year from today.
    Rule:
      - assume current year
      - if inferred date is > today + 3 days => subtract 1 year (handles Dec when in Jan)
    """
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})\s*$", mmdd)
    if not m:
        return None
    month = int(m.group(1))
    day = int(m.group(2))
    year = today_local.year
    dt = datetime(year, month, day)
    if dt.date() > (today_local.date() + timedelta(days=3)):
        dt = datetime(year - 1, month, day)
    return dt.strftime("%Y-%m-%d")


def _today_local() -> datetime:
    # We do not rely on system tz database; use offset from UTC via TIMEZONE if needed.
    # In GitHub runner, local tz is UTC; for Taipei we add +8 hours.
    tz = read_env_timezone()
    now = datetime.now(timezone.utc)
    if tz == "Asia/Taipei":
        return (now + timedelta(hours=8)).replace(tzinfo=None)
    # fallback: treat as UTC naive
    return now.replace(tzinfo=None)


def _pick_table(df_list: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """
    HiStock page usually has multiple tables. We pick the one containing a date column
    and a margin balance column.
    """
    for df in df_list:
        cols = [str(c) for c in df.columns]
        joined = "|".join(cols)
        if ("日期" in joined) and ("融資" in joined) and ("餘額" in joined):
            return df
    return None


def _find_col(cols: List[str], patterns: List[str]) -> Optional[str]:
    for p in patterns:
        for c in cols:
            if p in c:
                return c
    return None


def fetch_histock_rows(url: str) -> Tuple[Optional[str], List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    headers = {"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    # pandas.read_html needs lxml installed
    try:
        dfs = pd.read_html(r.text)
    except Exception as e:
        notes.append(f"read_html 失敗: {type(e).__name__}: {e}")
        return None, [], notes

    df = _pick_table(dfs)
    if df is None:
        notes.append("HiStock：找不到包含『日期/融資/餘額』的表格")
        return None, [], notes

    # Normalize column names
    cols = [str(c).strip() for c in df.columns]
    notes.append("HiStock 欄位：" + " | ".join(cols))

    date_col = _find_col(cols, ["日期"])
    bal_col = _find_col(cols, ["融資餘額", "融資餘額(億)", "融資餘額(億) "])
    # chg column variants observed: "融資增減(億)" or "融資增加(億)" or maybe "融資增減"
    chg_col = _find_col(cols, ["融資增減", "融資增加", "增減", "增加"])

    if date_col is None or bal_col is None:
        notes.append("HiStock：必要欄位缺失（日期/融資餘額）")
        return None, [], notes

    if chg_col is None:
        notes.append("HiStock：找不到『增減/增加』欄，chg_yi 將輸出 NA")

    # Convert rows
    today_local = _today_local()

    out_rows: List[Dict[str, Any]] = []
    raw_date_samples: List[str] = []

    for _, row in df.iterrows():
        d_raw = str(row.get(date_col, "")).strip()
        if not d_raw or d_raw.lower() == "nan":
            continue

        raw_date_samples.append(d_raw)

        # date formats:
        # - "2026/01/22" or "2026-01-22" or "01/22"
        d_iso: Optional[str] = None
        m_full = re.match(r"^\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*$", d_raw)
        if m_full:
            y = int(m_full.group(1))
            mo = int(m_full.group(2))
            da = int(m_full.group(3))
            d_iso = f"{y:04d}-{mo:02d}-{da:02d}"
        else:
            d_iso = _infer_year_for_mmdd(d_raw, today_local)

        if d_iso is None:
            continue

        bal = _parse_float_maybe(row.get(bal_col))
        if bal is None:
            continue

        chg = _parse_float_maybe(row.get(chg_col)) if chg_col else None

        out_rows.append({"date": d_iso, "balance_yi": bal, "chg_yi": chg})

    # Sort descending by date
    out_rows.sort(key=lambda x: x["date"], reverse=True)

    if raw_date_samples:
        smp = ", ".join(raw_date_samples[:5])
        notes.append(f"HiStock 原始日期樣本：{smp}")

    data_date = out_rows[0]["date"] if out_rows else None
    return data_date, out_rows, notes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    sources = {
        "TWSE": {
            "source": "HiStock",
            "source_url": "https://histock.tw/stock/three.aspx?m=mg",
        },
        "TPEX": {
            "source": "HiStock",
            "source_url": "https://histock.tw/stock/three.aspx?m=mg&no=TWOI",
        },
    }

    generated_at_utc = now_utc_iso()
    series: Dict[str, Any] = {}

    twse_date, twse_rows, twse_notes = fetch_histock_rows(sources["TWSE"]["source_url"])
    tpex_date, tpex_rows, tpex_notes = fetch_histock_rows(sources["TPEX"]["source_url"])

    # Defensive: prevent "TPEX == TWSE" accidental wrong fetch
    if twse_rows and tpex_rows:
        # Compare first N dates+balances
        N = min(10, len(twse_rows), len(tpex_rows))
        same = 0
        for i in range(N):
            if (twse_rows[i]["date"] == tpex_rows[i]["date"]) and (twse_rows[i]["balance_yi"] == tpex_rows[i]["balance_yi"]):
                same += 1
        if N >= 5 and same == N:
            # suspicious: likely fetched same table; invalidate TPEX
            tpex_rows = []
            tpex_date = None
            tpex_notes = tpex_notes + ["防呆：TPEX 前 N 筆與 TWSE 完全相同，視為抓錯頁面，已將 TPEX 置空（避免假 OK）。"]

    for mkt, meta in sources.items():
        if mkt == "TWSE":
            data_date, rows, notes = twse_date, twse_rows, twse_notes
        else:
            data_date, rows, notes = tpex_date, tpex_rows, tpex_notes

        notes = notes + ["Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。"]

        series[mkt] = {
            "source": meta["source"],
            "source_url": meta["source_url"],
            "data_date": data_date,
            "rows": rows,
            "notes": notes,
        }

    payload = {
        "schema_version": SCHEMA_LATEST,
        "generated_at_utc": generated_at_utc,
        "series": series,
    }

    outpath = os.path.join(outdir, "latest.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()