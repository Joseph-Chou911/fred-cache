#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheme2 (HiStock-only) fetcher for TWSE/TPEX margin financing.

Improvements (audit-first, backward compatible):
- More robust MM/DD year inference (choose best candidate vs "month+1" heuristic).
- Table selection: prefer tables where required cols exist and parsed rows are maximal.
- HTTP retry + backoff.
- Add optional audit fields: fetched_at_utc, http_error, rows_count.
- NEW (audit-first): emit chg_yi_unit extracted from HiStock column name (e.g., "融資增加(億)").
  * If unit cannot be extracted => NA (no guessing).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone, date
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


def _best_mmdd_year(mo: int, dd: int, tz: str = "Asia/Taipei") -> Optional[int]:
    """
    Robust year inference for MM/DD (no year):
    - Consider current year and previous year candidates.
    - Choose the candidate that is not too far in the future (<= today + 1 day),
      and is closest to today by absolute day distance.
    """
    today = datetime.now(ZoneInfo(tz)).date()
    candidates: List[Tuple[int, Optional[date]]] = []
    for y in (today.year, today.year - 1):
        try:
            candidates.append((y, date(y, mo, dd)))
        except Exception:
            candidates.append((y, None))

    valid: List[Tuple[int, date]] = [(y, d) for y, d in candidates if d is not None]
    if not valid:
        return None

    # prefer not future > today+1
    best: Optional[Tuple[int, date]] = None
    best_score: Optional[int] = None
    for y, d in valid:
        # allow small forward drift (timezone / site update)
        if d > date.fromordinal(today.toordinal() + 1):  # today + 1 day
            continue
        score = abs((today - d).days)
        if best is None or best_score is None or score < best_score:
            best = (y, d)
            best_score = score

    if best is None:
        # fallback: choose the closest even if slightly future
        y, _d = min(valid, key=lambda x: abs((today - x[1]).days))
        return y
    return best[0]


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
        y = _best_mmdd_year(mo, d, tz=tz)
        if y is None:
            return None
        return f"{y:04d}-{mo:02d}-{d:02d}"

    return None


def http_get(url: str, timeout: int = 25, tries: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    Simple retry + backoff to reduce flaky failures.
    """
    last_err: Optional[str] = None
    for i in range(tries):
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
            last_err = f"HTTP 取得失敗：{type(e).__name__}: {e}"
            # backoff: 0.8s, 1.6s, 3.2s ...
            if i < tries - 1:
                time.sleep(0.8 * (2 ** i))
    return None, last_err


# ---------- NEW: unit extraction (audit-first; no guessing) ----------

def _extract_unit_from_colname(col: Optional[str]) -> Dict[str, Any]:
    """
    Extract unit from column name like:
      - '融資餘額(億)'
      - '融資增加(億)'
      - full-width parentheses: '融資增加（億）'

    Audit-first:
    - If cannot extract => NA (no guessing).
    - We record what we saw (raw unit string) and where it came from (source).

    Returns:
      {"code": "...", "label": "...", "raw": "...", "source": "..."}
    """
    if not isinstance(col, str) or not col.strip():
        return {"code": "NA", "label": "NA", "raw": "NA", "source": "NA"}

    s = col.strip()

    # Support half-width and full-width parentheses.
    m = re.search(r"[(（]([^）)]+)[)）]", s)
    raw_unit = m.group(1).strip() if m else ""

    if not raw_unit:
        return {"code": "NA", "label": "NA", "raw": "NA", "source": f"colname:{s}"}

    # Conservative mapping: reflect what HiStock shows, do not assert currency/scale.
    if raw_unit == "億":
        return {"code": "UNIT_YI", "label": "億", "raw": raw_unit, "source": f"colname:{s}"}
    if raw_unit == "萬":
        return {"code": "UNIT_WAN", "label": "萬", "raw": raw_unit, "source": f"colname:{s}"}

    # Unknown unit: keep raw
    return {"code": "UNIT_RAW", "label": raw_unit, "raw": raw_unit, "source": f"colname:{s}"}


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


def _parse_rows(df: pd.DataFrame, date_col: str, bal_col: str, chg_col: Optional[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
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
    return rows


def parse_histock(html: str) -> Tuple[Optional[str], List[Dict[str, Any]], List[str], Dict[str, Any]]:
    """
    Returns:
      (data_date, rows, notes, chg_yi_unit)
    """
    notes: List[str] = []
    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except Exception as e:
        return None, [], [f"HiStock 解析失敗：{type(e).__name__}: {e}"], {"code": "NA", "label": "NA", "raw": "NA", "source": "NA"}

    if not tables:
        return None, [], ["HiStock 找不到任何表格（read_html=0 tables）"], {"code": "NA", "label": "NA", "raw": "NA", "source": "NA"}

    # Evaluate all candidate tables; choose best by:
    # 1) has required columns (date+balance)
    # 2) parsed rows count maximal
    best_rows: List[Dict[str, Any]] = []
    best_notes: List[str] = []
    best_dd: Optional[str] = None
    best_cols: Optional[List[str]] = None
    best_bal_col: Optional[str] = None
    best_chg_col: Optional[str] = None

    for idx, df in enumerate(tables):
        cols = [_col_to_str(c) for c in df.columns]
        joined = " ".join(cols)
        if ("日期" not in joined) or ("融資" not in joined):
            continue

        date_col, bal_col, chg_col = _find_cols(cols)
        if date_col is None or bal_col is None:
            continue

        df2 = df.copy()
        df2.columns = cols

        local_notes: List[str] = []
        local_notes.append(f"候選表[{idx}]欄位：" + " | ".join(cols[:40]))
        if chg_col is None:
            local_notes.append(f"候選表[{idx}]：找不到『融資增加/減少/變動』欄，chg_yi 將輸出 NA")

        raw_dates = [str(x) for x in df2[date_col].head(5).tolist()]
        local_notes.append(f"候選表[{idx}]原始日期樣本：" + ", ".join(raw_dates))

        rows = _parse_rows(df2, date_col, bal_col, chg_col)
        local_notes.append(f"候選表[{idx}]解析rows={len(rows)}")

        if len(rows) > len(best_rows):
            best_rows = rows
            best_notes = local_notes
            best_dd = rows[0]["date"] if rows else None
            best_cols = cols
            best_bal_col = bal_col
            best_chg_col = chg_col

    if not best_rows:
        # fallback: keep earlier behavior but provide audit hint
        return None, [], ["HiStock：無法定位可解析的『日期+融資餘額』資料表（可能改版）"], {"code": "NA", "label": "NA", "raw": "NA", "source": "NA"}

    # final notes: record chosen table cols
    notes.extend(best_notes)
    if best_cols:
        notes.append("HiStock 最終採用欄位：" + " | ".join(best_cols[:40]))

    # NEW: extract unit metadata from chosen change column name
    chg_unit = _extract_unit_from_colname(best_chg_col)
    notes.append(f"unit.chg_yi from col='{best_chg_col}': {chg_unit}")

    return best_dd, best_rows, notes, chg_unit


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
        fetched_at = now_utc_iso()

        if err or not html:
            out["series"][mkt] = {
                "source": "HiStock",
                "source_url": url,
                "data_date": None,
                "rows": [],
                "notes": [err or "HiStock 空回應"],
                # NEW: unit metadata (audit-first)
                "chg_yi_unit": {"code": "NA", "label": "NA", "raw": "NA", "source": "NA"},
                # optional audit fields
                "fetched_at_utc": fetched_at,
                "http_error": err or "HiStock empty response",
                "rows_count": 0,
            }
            return

        dd, rows, notes, chg_unit = parse_histock(html)
        if len(rows) < args.min_rows:
            notes.append(f"HiStock {mkt} rows 不足以提供 min_rows={args.min_rows}（實得 {len(rows)}）")
        notes.append("Scheme2：未強求 Yahoo/WantGoo（常見 JS/403），以 HiStock 為主。")

        out["series"][mkt] = {
            "source": "HiStock",
            "source_url": url,
            "data_date": dd,
            "rows": rows,
            "notes": notes,
            # NEW: unit metadata (audit-first)
            "chg_yi_unit": chg_unit,
            # optional audit fields
            "fetched_at_utc": fetched_at,
            "http_error": None,
            "rows_count": len(rows),
        }

    html, err = http_get(HISTOCK_TWSE_URL)
    set_series("TWSE", HISTOCK_TWSE_URL, html, err)

    html, err = http_get(HISTOCK_TPEX_URL)
    set_series("TPEX", HISTOCK_TPEX_URL, html, err)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()