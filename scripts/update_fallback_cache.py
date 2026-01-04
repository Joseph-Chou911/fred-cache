#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fallback cache updater (Version A)
- Writes: fallback_cache/latest.json
- Dependencies: requests>=2.31.0 (only)

Covered (current):
- VIXCLS (CBOE VIX_History.csv)
- DGS10, DGS2, UST3M (US Treasury daily yield curve CSV by month)
- T10Y2Y, T10Y3M (derived from treasury yields)
- NFCINONFINLEVERAGE (Chicago Fed NFCI CSV; robust parsing)
- SP500, NASDAQCOM, DJIA (stooq indices; with derived 1d pct)
- DCOILWTICO (WTI spot proxy via DataHub EIA open data wti-daily.csv)

Intentionally NOT covered in vA:
- DXY futures from stooq (dx.f) & WTI futures (cl.f): often blocked/empty
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests


# -------------------------
# Config
# -------------------------

OUT_DIR = "fallback_cache"
OUT_FILE = os.path.join(OUT_DIR, "latest.json")

URL_CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

# US Treasury daily yield curve (month-scoped)
# Example pattern you already used:
# https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve
TREASURY_BASE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{yyyymm}"
TREASURY_QS = "?_format=csv&field_tdr_date_value_month={yyyymm}&page=&type=daily_treasury_yield_curve"

URL_CHICAGOFED_NFCI = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"

# DataHub oil-prices (EIA open data)
# CSV header: Date,Price
URL_DATAHUB_WTI_DAILY = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"

# Stooq indices CSV endpoint
# header: Date,Open,High,Low,Close,Volume
STOOQ_CSV = "https://stooq.com/q/d/l/?s={symbol}&i=d"


# -------------------------
# Utilities
# -------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sleep_backoff(attempt: int) -> None:
    # attempt: 1..3
    secs = 2 ** attempt  # 2,4,8
    time.sleep(secs)


def http_get_text(url: str, timeout: int = 30, max_retries: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (text, error_code)
    error_code in { 'HTTP_<status>', 'timeout', 'request', 'empty' }
    """
    headers = {
        "User-Agent": "fallback-cache-bot/1.0 (+https://github.com/Joseph-Chou911/fred-cache)"
    }

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code != 200:
                err = f"HTTP_{r.status_code}"
                if attempt < max_retries:
                    sleep_backoff(attempt)
                    continue
                return None, err

            text = r.text
            if not text:
                # empty response body
                if attempt < max_retries:
                    sleep_backoff(attempt)
                    continue
                return None, "empty"

            return text, None

        except requests.Timeout:
            if attempt < max_retries:
                sleep_backoff(attempt)
                continue
            return None, "timeout"
        except requests.RequestException:
            if attempt < max_retries:
                sleep_backoff(attempt)
                continue
            return None, "request"

    return None, "unknown"


def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def write_json_atomic(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def to_float(s: Any) -> Optional[float]:
    try:
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return float(s)
        s2 = str(s).strip()
        if s2 == "" or s2.upper() == "NA" or s2 == ".":
            return None
        return float(s2)
    except Exception:
        return None


def parse_date_any(s: str) -> Optional[str]:
    """
    Accepts:
    - YYYY-MM-DD
    - MM/DD/YYYY
    Returns ISO 'YYYY-MM-DD' string or None
    """
    s = (s or "").strip()
    if not s:
        return None

    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def make_na(series_id: str, source_url: str, err: str, as_of_ts: str) -> Dict[str, Any]:
    return {
        "series_id": series_id,
        "data_date": "NA",
        "value": "NA",
        "source_url": source_url if source_url else "NA",
        "notes": f"ERR:{err}",
        "as_of_ts": as_of_ts,
    }


# -------------------------
# Fetchers
# -------------------------

def fetch_cboe_vix(as_of_ts: str) -> Dict[str, Any]:
    text, err = http_get_text(URL_CBOE_VIX)
    if err:
        return make_na("VIXCLS", URL_CBOE_VIX, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    # Expect columns like: DATE, OPEN, HIGH, LOW, CLOSE
    last_valid: Optional[Tuple[str, float]] = None

    for row in reader:
        d = parse_date_any(row.get("DATE") or row.get("Date") or row.get("date") or "")
        v = to_float(row.get("CLOSE") or row.get("Close") or row.get("close"))
        if d and v is not None:
            last_valid = (d, v)

    if not last_valid:
        return make_na("VIXCLS", URL_CBOE_VIX, "no_valid_rows", as_of_ts)

    d, v = last_valid
    return {
        "series_id": "VIXCLS",
        "data_date": d,
        "value": v,
        "source_url": URL_CBOE_VIX,
        "notes": "WARN:fallback_cboe_vix",
        "as_of_ts": as_of_ts,
    }


def fetch_treasury_yields(as_of_ts: str) -> List[Dict[str, Any]]:
    """
    Returns rows for: DGS10, DGS2, UST3M + derived spreads (T10Y2Y, T10Y3M)
    """
    yyyymm = datetime.now().strftime("%Y%m")
    url = TREASURY_BASE.format(yyyymm=yyyymm) + TREASURY_QS.format(yyyymm=yyyymm)

    text, err = http_get_text(url)
    if err:
        # return NA set
        out = [
            make_na("DGS10", url, err, as_of_ts),
            make_na("DGS2", url, err, as_of_ts),
            make_na("UST3M", url, err, as_of_ts),
            make_na("T10Y2Y", url, err, as_of_ts),
            make_na("T10Y3M", url, err, as_of_ts),
        ]
        return out

    sio = StringIO(text)
    reader = csv.DictReader(sio)

    # Treasury file uses "Date" and columns like "3 Mo", "2 Yr", "10 Yr"
    last_row: Optional[Dict[str, str]] = None
    for row in reader:
        # keep last non-empty date row
        if (row.get("Date") or "").strip():
            last_row = row

    if not last_row:
        out = [
            make_na("DGS10", url, "no_valid_rows", as_of_ts),
            make_na("DGS2", url, "no_valid_rows", as_of_ts),
            make_na("UST3M", url, "no_valid_rows", as_of_ts),
            make_na("T10Y2Y", url, "no_valid_rows", as_of_ts),
            make_na("T10Y3M", url, "no_valid_rows", as_of_ts),
        ]
        return out

    d = parse_date_any(last_row.get("Date", ""))
    if not d:
        d = "NA"

    v10 = to_float(last_row.get("10 Yr"))
    v2 = to_float(last_row.get("2 Yr"))
    v3m = to_float(last_row.get("3 Mo"))

    out: List[Dict[str, Any]] = []

    def row_or_na(series_id: str, val: Optional[float], notes: str) -> Dict[str, Any]:
        if d == "NA" or val is None:
            return make_na(series_id, url, "missing", as_of_ts)
        return {
            "series_id": series_id,
            "data_date": d,
            "value": val,
            "source_url": url,
            "notes": notes,
            "as_of_ts": as_of_ts,
        }

    out.append(row_or_na("DGS10", v10, "WARN:fallback_treasury_csv"))
    out.append(row_or_na("DGS2", v2, "WARN:fallback_treasury_csv"))
    out.append(row_or_na("UST3M", v3m, "WARN:fallback_treasury_csv"))

    # derived spreads
    if d != "NA" and (v10 is not None) and (v2 is not None):
        out.append({
            "series_id": "T10Y2Y",
            "data_date": d,
            "value": float(v10 - v2),
            "source_url": url,
            "notes": "WARN:derived_from_treasury(10Y-2Y)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append(make_na("T10Y2Y", url, "missing_inputs", as_of_ts))

    if d != "NA" and (v10 is not None) and (v3m is not None):
        out.append({
            "series_id": "T10Y3M",
            "data_date": d,
            "value": float(v10 - v3m),
            "source_url": url,
            "notes": "WARN:derived_from_treasury(10Y-3M)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append(make_na("T10Y3M", url, "missing_inputs", as_of_ts))

    return out


def _pick_nfci_date_col(fieldnames: List[str]) -> Optional[str]:
    # prefer exact common names, else any containing 'date'
    for c in ("DATE", "Date", "date", "observation_date", "Observation Date"):
        if c in fieldnames:
            return c
    for c in fieldnames:
        if "date" in c.lower():
            return c
    return None


def _pick_nfci_nonfin_leverage_col(fieldnames: List[str]) -> Optional[str]:
    # Try several fuzzy heuristics
    candidates = []
    for c in fieldnames:
        cl = c.lower().strip()
        score = 0
        if "non" in cl and "fin" in cl:
            score += 2
        if "nonfinancial" in cl:
            score += 4
        if "lever" in cl:
            score += 3
        if "subindex" in cl:
            score += 1
        if score > 0:
            candidates.append((score, c))
    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0][1] if candidates else None


def fetch_chicagofed_nfci_nonfin_leverage(as_of_ts: str) -> Dict[str, Any]:
    text, err = http_get_text(URL_CHICAGOFED_NFCI)
    if err:
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    if not reader.fieldnames:
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, "no_headers", as_of_ts)

    date_col = _pick_nfci_date_col(reader.fieldnames)
    val_col = _pick_nfci_nonfin_leverage_col(reader.fieldnames)

    if not date_col or not val_col:
        missing = []
        if not date_col:
            missing.append("date_col")
        if not val_col:
            missing.append("value_col")
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, "missing_" + "_".join(missing), as_of_ts)

    last_valid: Optional[Tuple[str, float]] = None
    for row in reader:
        d = parse_date_any(row.get(date_col, ""))
        v = to_float(row.get(val_col))
        if d and v is not None:
            last_valid = (d, v)

    if not last_valid:
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, "no_valid_rows", as_of_ts)

    d, v = last_valid
    return {
        "series_id": "NFCINONFINLEVERAGE",
        "data_date": d,
        "value": v,
        "source_url": URL_CHICAGOFED_NFCI,
        "notes": "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
        "as_of_ts": as_of_ts,
    }


def fetch_datahub_wti_daily(as_of_ts: str) -> Dict[str, Any]:
    text, err = http_get_text(URL_DATAHUB_WTI_DAILY)
    if err:
        return make_na("DCOILWTICO", URL_DATAHUB_WTI_DAILY, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    # header: Date,Price
    last_valid: Optional[Tuple[str, float]] = None
    for row in reader:
        d = parse_date_any(row.get("Date") or row.get("DATE") or row.get("date") or "")
        v = to_float(row.get("Price") or row.get("PRICE") or row.get("price"))
        if d and v is not None:
            last_valid = (d, v)

    if not last_valid:
        return make_na("DCOILWTICO", URL_DATAHUB_WTI_DAILY, "no_valid_rows", as_of_ts)

    d, v = last_valid
    return {
        "series_id": "DCOILWTICO",
        "data_date": d,
        "value": v,
        "source_url": URL_DATAHUB_WTI_DAILY,
        "notes": "WARN:fallback_datahub_oil_prices(wti-daily)",
        "as_of_ts": as_of_ts,
    }


def fetch_stooq_index(series_id: str, symbol: str, as_of_ts: str) -> Dict[str, Any]:
    url = STOOQ_CSV.format(symbol=symbol)
    text, err = http_get_text(url)
    if err:
        return make_na(series_id, url, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    rows: List[Tuple[str, float]] = []
    for row in reader:
        d = parse_date_any(row.get("Date") or row.get("DATE") or row.get("date") or "")
        close = to_float(row.get("Close") or row.get("CLOSE") or row.get("close"))
        if d and close is not None:
            rows.append((d, close))

    if len(rows) < 1:
        return make_na(series_id, url, "no_valid_rows", as_of_ts)

    d_last, v_last = rows[-1]

    out: Dict[str, Any] = {
        "series_id": series_id,
        "data_date": d_last,
        "value": v_last,
        "source_url": url,
        "notes": f"WARN:fallback_stooq({symbol});derived_1d_pct",
        "as_of_ts": as_of_ts,
    }

    if len(rows) >= 2 and rows[-2][1] != 0:
        prev = rows[-2][1]
        out["change_pct_1d"] = (v_last / prev - 1.0) * 100.0
    else:
        out["notes"] = f"WARN:fallback_stooq({symbol});missing_prev_close"

    return out


# -------------------------
# Main
# -------------------------

def main() -> int:
    as_of_ts = utc_now_iso()
    ensure_out_dir()

    items: List[Dict[str, Any]] = []

    # VIX
    items.append(fetch_cboe_vix(as_of_ts))

    # Treasury yields + spreads
    items.extend(fetch_treasury_yields(as_of_ts))

    # NFCI nonfinancial leverage
    items.append(fetch_chicagofed_nfci_nonfin_leverage(as_of_ts))

    # Equity indices via stooq
    items.append(fetch_stooq_index("SP500", "^spx", as_of_ts))
    items.append(fetch_stooq_index("NASDAQCOM", "^ndq", as_of_ts))
    items.append(fetch_stooq_index("DJIA", "^dji", as_of_ts))

    # WTI spot via DataHub
    items.append(fetch_datahub_wti_daily(as_of_ts))

    write_json_atomic(OUT_FILE, items)

    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())