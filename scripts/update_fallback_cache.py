#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fallback cache (方案A)：官方/免key優先，但允許非官方備援；以「不中斷」為最高優先。
輸出：fallback_cache/latest.json （JSON array）
"""

import csv
import json
import os
import re
import time
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

import requests


# ----------------------------
# Config
# ----------------------------
SCRIPT_VERSION = os.getenv("FALLBACK_SCRIPT_VERSION", "fallback_vA_official_no_key_lock")

OUT_PATH = os.getenv("FALLBACK_OUT_PATH", "fallback_cache/latest.json")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))

# backoff: 2s -> 4s -> 8s (最多3次)
BACKOFF_S = [2, 4, 8]

# 類瀏覽器 headers：降低「回 HTML / 被擋」機率
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# ----------------------------
# Helpers
# ----------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canon_key(s: str) -> str:
    """
    更強的欄位容錯：
    - 全小寫
    - 移除所有非英數字（包含空白、底線、破折號、冒號、括號等）
    """
    if s is None:
        return ""
    s = s.strip().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def looks_like_html(text: str) -> bool:
    t = text.lstrip().lower()
    return t.startswith("<!doctype html") or t.startswith("<html") or ("<html" in t[:500]) or ("access denied" in t[:500])


def parse_date_to_iso(d: str) -> Optional[str]:
    """
    支援：
    - YYYY-MM-DD
    - MM/DD/YYYY
    - M/D/YYYY
    - YYYY/MM/DD
    """
    if not d:
        return None
    d = d.strip()
    # 常見：2026-01-02
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(d, fmt).date().isoformat()
        except ValueError:
            pass
    # 常見：01/02/2026（CBOE）
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(d, fmt).date().isoformat()
        except ValueError:
            pass
    # 嘗試 M/D/YYYY（有些CSV不補零）
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", d)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(yy, mm, dd).isoformat()
        except ValueError:
            return None
    return None


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s in ("", ".", "NA", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def http_get_text(url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    具備重試/backoff；回傳 (text, status_code, err_note)
    err_note 用於 notes（可稽核）
    """
    last_err = None
    for i in range(RETRY_MAX):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
            status = resp.status_code
            text = resp.text if resp is not None else None
            if status >= 200 and status < 300 and text:
                return text, status, None
            last_err = f"http_status_{status}_or_empty"
        except Exception as e:
            last_err = f"exception:{type(e).__name__}"
        # backoff
        if i < len(BACKOFF_S):
            time.sleep(BACKOFF_S[i])
    return None, None, last_err


def csv_last_valid_row(
    csv_text: str,
    value_col_hint: str,
    date_col_candidates: List[str],
) -> Tuple[Optional[str], Optional[float], str]:
    """
    從 CSV 找到最後一筆有效（value 可轉 float 且 date 可解析）資料
    回傳 (data_date_iso, value_float, note)
    """
    if not csv_text or not ("," in csv_text.splitlines()[0]):
        return None, None, "ERR:csv_header_invalid"

    if looks_like_html(csv_text):
        return None, None, "ERR:html_instead_of_csv"

    reader = csv.DictReader(csv_text.splitlines())
    if not reader.fieldnames:
        return None, None, "ERR:no_fieldnames"

    # 找 date col
    date_col = None
    fns = reader.fieldnames
    fns_ck = {canon_key(c): c for c in fns}

    for c in date_col_candidates:
        ck = canon_key(c)
        if ck in fns_ck:
            date_col = fns_ck[ck]
            break
    if date_col is None:
        # 常見：DATE / Date / observation_date
        # 若沒有，盡量抓第一欄
        date_col = fns[0]

    # 找 value col（允許 hint 不一致）
    value_col = None
    hint_ck = canon_key(value_col_hint)
    if hint_ck in fns_ck:
        value_col = fns_ck[hint_ck]
    else:
        # 退一步：找包含 hint 的欄位
        for c in fns:
            if hint_ck and hint_ck in canon_key(c):
                value_col = c
                break

    if value_col is None:
        return None, None, "ERR:value_col_not_found"

    last_good_date = None
    last_good_val = None

    for row in reader:
        d_raw = (row.get(date_col) or "").strip()
        v_raw = row.get(value_col)

        d_iso = parse_date_to_iso(d_raw)
        v = safe_float(v_raw)
        if d_iso and (v is not None):
            last_good_date = d_iso
            last_good_val = v

    if last_good_date is None or last_good_val is None:
        return None, None, "ERR:no_valid_rows"

    return last_good_date, last_good_val, "OK"


def chicagofed_find_nonfin_leverage_col(fieldnames: List[str]) -> Optional[str]:
    """
    Chicago Fed NFCI CSV 欄位常有命名變化，這裡用「去除非英數」後的 token 判斷。
    目標：nonfinancial leverage subindex
    """
    targets = [
        # 最理想：同時包含 nfci / nonfinancial / leverage
        ["nfci", "nonfinancial", "leverage"],
        # 有些會縮寫 nonfin
        ["nfci", "nonfin", "lever"],
        # 有些沒有 nfci 字樣，但有 nonfinancial leverage
        ["nonfinancial", "leverage"],
    ]

    ck_map = {canon_key(fn): fn for fn in fieldnames}

    for fn in fieldnames:
        ck = canon_key(fn)
        for toks in targets:
            if all(t in ck for t in toks):
                return fn

    # 次佳：直接找最短匹配（避免欄位多時誤判）
    for ck, orig in ck_map.items():
        if ("nonfinancial" in ck or "nonfin" in ck) and ("leverage" in ck or "lever" in ck):
            return orig

    return None


def build_item(series_id: str, data_date: Any, value: Any, source_url: str, notes: str, as_of_ts: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
    item = {
        "series_id": series_id,
        "data_date": data_date if data_date is not None else "NA",
        "value": value if value is not None else "NA",
        "source_url": source_url if source_url else "NA",
        "notes": notes if notes else "NA",
        "as_of_ts": as_of_ts,
    }
    if extra:
        item.update(extra)
    return item


# ----------------------------
# Fetchers
# ----------------------------
def fetch_vix(as_of_ts: str) -> Dict[str, Any]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, _, err = http_get_text(url)
    if not text:
        return build_item("VIXCLS", "NA", "NA", url, f"ERR:fetch_failed:{err}", as_of_ts)

    d, v, note = csv_last_valid_row(
        text,
        value_col_hint="CLOSE",
        date_col_candidates=["DATE", "Date"],
    )
    if note != "OK":
        return build_item("VIXCLS", "NA", "NA", url, f"ERR:vix_{note}", as_of_ts)

    return build_item("VIXCLS", d, v, url, "WARN:fallback_cboe_vix", as_of_ts)


def fetch_treasury_curve(as_of_ts: str) -> List[Dict[str, Any]]:
    # 你原本成功的月參數路徑：202601。這裡自動用 UTC 當月（避免每月要改）
    yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    base = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{yyyymm}"
        f"?_format=csv&field_tdr_date_value_month={yyyymm}&page=&type=daily_treasury_yield_curve"
    )

    text, _, err = http_get_text(base)
    if not text:
        na = build_item("DGS10", "NA", "NA", base, f"ERR:treasury_fetch_failed:{err}", as_of_ts)
        return [na]

    # treasury 欄位可能是：Date, 1 Mo, 2 Mo, 3 Mo, ... 2 Yr, 10 Yr 等
    # 我們抓 10Y / 2Y / 3M，並衍生 T10Y2Y / T10Y3M
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return [build_item("DGS10", "NA", "NA", base, "ERR:treasury_no_fieldnames", as_of_ts)]

    fns = reader.fieldnames
    # 找 date 欄
    date_col = None
    for cand in ["Date", "DATE"]:
        if cand in fns:
            date_col = cand
            break
    if date_col is None:
        date_col = fns[0]

    # 容錯找欄位（不同命名）
    def pick_col(possible: List[str]) -> Optional[str]:
        for p in possible:
            for fn in fns:
                if canon_key(fn) == canon_key(p):
                    return fn
        # 再退：contains
        for p in possible:
            pck = canon_key(p)
            for fn in fns:
                if pck and pck in canon_key(fn):
                    return fn
        return None

    col_10y = pick_col(["10 Yr", "10Y", "10 yr", "10-year", "10year"])
    col_2y = pick_col(["2 Yr", "2Y", "2 yr", "2-year", "2year"])
    col_3m = pick_col(["3 Mo", "3M", "3 mo", "3-month", "3month"])

    last = None
    for row in reader:
        d_iso = parse_date_to_iso((row.get(date_col) or "").strip())
        if not d_iso:
            continue
        # 只更新 last（最後一筆）
        last = (d_iso, row)

    if not last:
        return [build_item("DGS10", "NA", "NA", base, "ERR:treasury_no_valid_rows", as_of_ts)]

    d_iso, row = last
    v10 = safe_float(row.get(col_10y)) if col_10y else None
    v2 = safe_float(row.get(col_2y)) if col_2y else None
    v3m = safe_float(row.get(col_3m)) if col_3m else None

    out: List[Dict[str, Any]] = []
    if v10 is None:
        out.append(build_item("DGS10", "NA", "NA", base, "ERR:treasury_missing_10y", as_of_ts))
    else:
        out.append(build_item("DGS10", d_iso, v10, base, "WARN:fallback_treasury_csv", as_of_ts))

    if v2 is None:
        out.append(build_item("DGS2", "NA", "NA", base, "ERR:treasury_missing_2y", as_of_ts))
    else:
        out.append(build_item("DGS2", d_iso, v2, base, "WARN:fallback_treasury_csv", as_of_ts))

    if v3m is None:
        out.append(build_item("UST3M", "NA", "NA", base, "ERR:treasury_missing_3m", as_of_ts))
    else:
        out.append(build_item("UST3M", d_iso, v3m, base, "WARN:fallback_treasury_csv", as_of_ts))

    # derived spreads
    if (v10 is not None) and (v2 is not None):
        out.append(build_item("T10Y2Y", d_iso, (v10 - v2), base, "WARN:derived_from_treasury(10Y-2Y)", as_of_ts))
    else:
        out.append(build_item("T10Y2Y", "NA", "NA", base, "ERR:treasury_cannot_derive_10y2y", as_of_ts))

    if (v10 is not None) and (v3m is not None):
        out.append(build_item("T10Y3M", d_iso, (v10 - v3m), base, "WARN:derived_from_treasury(10Y-3M)", as_of_ts))
    else:
        out.append(build_item("T10Y3M", "NA", "NA", base, "ERR:treasury_cannot_derive_10y3m", as_of_ts))

    return out


def fetch_nfci_nonfin_leverage(as_of_ts: str) -> Dict[str, Any]:
    url = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
    text, _, err = http_get_text(url)
    if not text:
        return build_item("NFCINONFINLEVERAGE", "NA", "NA", url, f"ERR:chicagofed_fetch_failed:{err}", as_of_ts)

    if looks_like_html(text):
        return build_item("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:chicagofed_html_instead_of_csv", as_of_ts)

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return build_item("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:chicagofed_no_fieldnames", as_of_ts)

    date_col = None
    for cand in ["Date", "DATE", "observation_date", "Observation Date"]:
        for fn in reader.fieldnames:
            if canon_key(fn) == canon_key(cand):
                date_col = fn
                break
        if date_col:
            break
    if not date_col:
        date_col = reader.fieldnames[0]

    value_col = chicagofed_find_nonfin_leverage_col(reader.fieldnames)
    if not value_col:
        return build_item("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:chicagofed_nfci_missing_col", as_of_ts)

    last_good_date = None
    last_good_val = None
    for row in reader:
        d_iso = parse_date_to_iso((row.get(date_col) or "").strip())
        v = safe_float(row.get(value_col))
        if d_iso and v is not None:
            last_good_date = d_iso
            last_good_val = v

    if last_good_date is None or last_good_val is None:
        return build_item("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:chicagofed_no_valid_rows", as_of_ts)

    return build_item(
        "NFCINONFINLEVERAGE",
        last_good_date,
        last_good_val,
        url,
        "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
        as_of_ts,
    )


def fetch_fredgraph_series(series_id: str, as_of_ts: str) -> Dict[str, Any]:
    # 免 key：fredgraph.csv
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    text, _, err = http_get_text(url)
    if not text:
        return build_item(series_id, "NA", "NA", url, f"ERR:fredgraph_fetch_failed:{err}", as_of_ts)

    d, v, note = csv_last_valid_row(
        text,
        value_col_hint=series_id,
        date_col_candidates=["DATE", "Date", "observation_date"],
    )
    if note != "OK":
        # 很多時候其實是回 HTML（被擋），這裡會變成 ERR:html_instead_of_csv
        return build_item(series_id, "NA", "NA", url, f"ERR:fredgraph_{note}", as_of_ts)

    # 特別標示：目前這是「免key備援」，不把它當成主來源
    return build_item(series_id, d, v, url, f"WARN:fredgraph_no_key({series_id})", as_of_ts)


def fetch_stooq_index(symbol: str, series_id: str, as_of_ts: str) -> Dict[str, Any]:
    # stooq 下載 CSV：Date,Open,High,Low,Close,Volume
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    text, _, err = http_get_text(url)
    if not text:
        return build_item(series_id, "NA", "NA", url, f"ERR:stooq_fetch_failed:{err}", as_of_ts)

    if looks_like_html(text):
        return build_item(series_id, "NA", "NA", url, "ERR:stooq_html_instead_of_csv", as_of_ts)

    rows = list(csv.DictReader(text.splitlines()))
    if len(rows) < 2:
        return build_item(series_id, "NA", "NA", url, "ERR:stooq_not_enough_rows", as_of_ts)

    # 取最後一筆與倒數第二筆，推導 1D%
    last = rows[-1]
    prev = rows[-2]

    d_iso = parse_date_to_iso((last.get("Date") or last.get("DATE") or "").strip())
    close_last = safe_float(last.get("Close"))
    close_prev = safe_float(prev.get("Close"))

    if not d_iso or close_last is None:
        return build_item(series_id, "NA", "NA", url, "ERR:stooq_last_row_invalid", as_of_ts)

    extra = {}
    note = f"WARN:nonofficial_stooq({symbol});derived_1d_pct"
    if close_prev is not None and close_prev != 0:
        extra["change_pct_1d"] = (close_last / close_prev - 1.0) * 100.0
    else:
        note = f"WARN:nonofficial_stooq({symbol});missing_prev_close"

    return build_item(series_id, d_iso, close_last, url, note, as_of_ts, extra=extra)


def fetch_wti_datahub(as_of_ts: str) -> Dict[str, Any]:
    # 非官方備援
    url = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"
    text, _, err = http_get_text(url)
    if not text:
        return build_item("DCOILWTICO", "NA", "NA", url, f"ERR:datahub_fetch_failed:{err}", as_of_ts)

    d, v, note = csv_last_valid_row(
        text,
        value_col_hint="Price",
        date_col_candidates=["Date", "DATE"],
    )
    if note != "OK":
        return build_item("DCOILWTICO", "NA", "NA", url, f"ERR:datahub_{note}", as_of_ts)

    return build_item("DCOILWTICO", d, v, url, "WARN:nonofficial_datahub_oil_prices(wti-daily)", as_of_ts)


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    as_of_ts = utc_now_iso()
    items: List[Dict[str, Any]] = []

    # META
    items.append(build_item("__META__", date.today().isoformat(), SCRIPT_VERSION, "NA", "INFO:script_version", as_of_ts))

    # 1) VIX (官方 CBOE，免 key)
    items.append(fetch_vix(as_of_ts))

    # 2) Treasury (官方，免 key) + spreads derived
    items.extend(fetch_treasury_curve(as_of_ts))

    # 3) NFCI nonfinancial leverage (官方 Chicago Fed，免 key)
    items.append(fetch_nfci_nonfin_leverage(as_of_ts))

    # 4) HY OAS（免 key 優先嘗試：FRED graph CSV）
    #    你要求補這個；但若 FRED 偶發回 HTML，這裡會自動 NA，不崩
    items.append(fetch_fredgraph_series("BAMLH0A0HYM2", as_of_ts))

    # 5) Equity indices（非官方 stooq 備援 + 1D%）
    items.append(fetch_stooq_index("^spx", "SP500", as_of_ts))
    items.append(fetch_stooq_index("^ndq", "NASDAQCOM", as_of_ts))
    items.append(fetch_stooq_index("^dji", "DJIA", as_of_ts))

    # 6) WTI（非官方 datahub 備援）
    items.append(fetch_wti_datahub(as_of_ts))

    # Write JSON
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote {OUT_PATH} rows={len(items)} as_of_ts={as_of_ts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())