#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fallback cache updater (Version A: official/no-key priority)

Goal:
- Produce fallback_cache/latest.json
- Never crash the whole run because one source fails
- Prefer official + no-key sources where practical
- For HY OAS (BAMLH0A0HYM2): use FRED fredgraph.csv (no API key, stable CSV),
  NOT HTML parsing. This is the most reliable "no-key" way in practice.

Output rows schema (compatible with your existing format):
  series_id, data_date, value, source_url, notes, as_of_ts
  optional: change_pct_1d (for equity indices)
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

import requests


# ---------------------------
# Config
# ---------------------------

OUT_DIR = os.path.join(os.getcwd(), "fallback_cache")
OUT_PATH = os.path.join(OUT_DIR, "latest.json")

SCRIPT_VERSION = os.environ.get("FALLBACK_SCRIPT_VERSION", "fallback_vA_official_no_key_20260104_lock_01")

# If you absolutely want "no FRED at all", set ALLOW_FREDGRAPH=0 in workflow env.
ALLOW_FREDGRAPH = os.environ.get("ALLOW_FREDGRAPH", "1").strip() not in ("0", "false", "False", "")

TIMEOUT_SEC = float(os.environ.get("HTTP_TIMEOUT_SEC", "20"))
RETRIES = int(os.environ.get("HTTP_RETRIES", "3"))

# Backoff schedule required by your spec
BACKOFF_S = [2, 4, 8]  # max 3 tries


# ---------------------------
# Helpers
# ---------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def today_utc() -> date:
    return datetime.now(timezone.utc).date()

def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

def safe_float(x: str) -> Optional[float]:
    try:
        if x is None:
            return None
        x = str(x).strip()
        if x == "" or x.lower() == "na" or x == ".":
            return None
        return float(x)
    except Exception:
        return None

def normalize_date_to_iso(d: str) -> Optional[str]:
    """
    Accept:
      - YYYY-MM-DD
      - MM/DD/YYYY
      - YYYY/MM/DD
    Return:
      - YYYY-MM-DD or None
    """
    if d is None:
        return None
    s = str(d).strip()
    if not s or s.lower() == "na":
        return None

    # Try ISO first
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return None

def http_get_text(url: str, *, timeout: float = TIMEOUT_SEC) -> Tuple[bool, str, str]:
    """
    Returns (ok, text, err_note)
    Backoff retries: 2s -> 4s -> 8s (max 3 tries)
    """
    last_err = ""
    headers = {
        "User-Agent": "fallback-cache-bot/1.0 (+https://github.com/Joseph-Chou911/fred-cache)",
        "Accept": "*/*",
    }
    for i in range(RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code in (429, 502, 503, 504):
                last_err = f"http_{r.status_code}"
                if i < len(BACKOFF_S):
                    time.sleep(BACKOFF_S[i])
                continue
            r.raise_for_status()
            return True, r.text, ""
        except Exception as e:
            last_err = f"exc:{type(e).__name__}"
            if i < len(BACKOFF_S):
                time.sleep(BACKOFF_S[i])
    return False, "", last_err

def pick_last_valid_from_csv(text: str, date_col_candidates: List[str], value_col: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Generic CSV parser:
    - Find date column name among candidates (case-insensitive)
    - Find value column by exact name (case-insensitive)
    - Return last row with valid date and numeric value
    """
    if not text.strip():
        return None, None

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return None, None

    # Map fieldnames case-insensitively
    fields = {f.lower().strip(): f for f in reader.fieldnames if f}
    date_key = None
    for cand in date_col_candidates:
        if cand.lower() in fields:
            date_key = fields[cand.lower()]
            break

    # Value column
    val_key = None
    if value_col.lower() in fields:
        val_key = fields[value_col.lower()]

    if not date_key or not val_key:
        return None, None

    last_date = None
    last_val = None
    for row in reader:
        d_raw = row.get(date_key, "")
        v_raw = row.get(val_key, "")
        d_iso = normalize_date_to_iso(d_raw)
        v = safe_float(v_raw)
        if d_iso and v is not None:
            last_date, last_val = d_iso, v

    return last_date, last_val


# ---------------------------
# Fetchers
# ---------------------------

def fetch_cboe_vix() -> Dict[str, Any]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:cboe_fetch_failed({err})"}

    # VIX_History.csv typically has columns: DATE, OPEN, HIGH, LOW, CLOSE
    d, v = pick_last_valid_from_csv(text, ["DATE", "Date"], "CLOSE")
    if not d or v is None:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:cboe_no_valid_rows"}

    return {"data_date": d, "value": v, "source_url": url, "notes": "WARN:fallback_cboe_vix"}


def treasury_month_url(yyyymm: str) -> str:
    # Example you already use (keep it)
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{yyyymm}"
        "?_format=csv&field_tdr_date_value_month="
        f"{yyyymm}&page=&type=daily_treasury_yield_curve"
    )

def fetch_treasury_yields() -> Dict[str, Any]:
    """
    Pull latest available yields from U.S. Treasury daily yield curve.
    Robustness: try current month and previous month; pick the newest date.
    """
    # Determine current and previous month in UTC
    now = datetime.now(timezone.utc).date()
    yyyymm_cur = f"{now.year}{now.month:02d}"
    # previous month
    if now.month == 1:
        yyyymm_prev = f"{now.year - 1}12"
    else:
        yyyymm_prev = f"{now.year}{now.month - 1:02d}"

    candidates = [treasury_month_url(yyyymm_cur), treasury_month_url(yyyymm_prev)]
    best: Tuple[Optional[str], Dict[str, Any]] = (None, {})

    for url in candidates:
        ok, text, err = http_get_text(url)
        if not ok:
            continue

        # Treasury CSV usually has "Date" and columns like "3 Mo", "2 Yr", "10 Yr"
        # We'll parse all rows and keep the last valid row with needed cols.
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            continue

        # Normalize fieldnames
        fields = {f.lower().strip(): f for f in reader.fieldnames if f}
        date_key = fields.get("date")
        c_3m = fields.get("3 mo") or fields.get("3 mo.")
        c_2y = fields.get("2 yr") or fields.get("2 yr.")
        c_10y = fields.get("10 yr") or fields.get("10 yr.")
        if not date_key or not c_3m or not c_2y or not c_10y:
            continue

        last_row = None
        last_date_iso = None
        for row in reader:
            d_iso = normalize_date_to_iso(row.get(date_key, ""))
            y3m = safe_float(row.get(c_3m, ""))
            y2y = safe_float(row.get(c_2y, ""))
            y10y = safe_float(row.get(c_10y, ""))
            if d_iso and (y3m is not None) and (y2y is not None) and (y10y is not None):
                last_row = (d_iso, y3m, y2y, y10y)
                last_date_iso = d_iso

        if last_row and last_date_iso:
            # Pick the newest date across candidate files
            if best[0] is None or last_date_iso > best[0]:
                d_iso, y3m, y2y, y10y = last_row
                best = (last_date_iso, {
                    "data_date": d_iso,
                    "UST3M": y3m,
                    "DGS2": y2y,
                    "DGS10": y10y,
                    "source_url": url,
                    "notes": "WARN:fallback_treasury_csv",
                })

    if best[0] is None:
        # Keep the current month url as the “attempted” source_url for auditability
        return {
            "data_date": "NA",
            "UST3M": "NA",
            "DGS2": "NA",
            "DGS10": "NA",
            "source_url": candidates[0],
            "notes": "ERR:treasury_no_valid_rows",
        }
    return best[1]


def fetch_chicagofed_nfci_nonfin_leverage() -> Dict[str, Any]:
    url = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:chicagofed_fetch_failed({err})"}

    # This CSV historically contains DATE + many columns including NFCINONFINLEVERAGE.
    # We do a tolerant scan:
    # - detect a date column (DATE/Date) or fallback to first column
    # - detect the target column by exact match (case-insensitive)
    if not text.strip():
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:chicagofed_empty"}

    reader = csv.reader(text.splitlines())
    rows = list(reader)
    if not rows or len(rows) < 2:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:chicagofed_no_rows"}

    header = [h.strip() for h in rows[0]]
    header_lc = [h.lower() for h in header]

    # date col
    if "date" in header_lc:
        date_idx = header_lc.index("date")
    else:
        # fallback: assume first col is date if it parses
        date_idx = 0

    # target col
    target = "nfcinonfinleverage"
    if target in header_lc:
        val_idx = header_lc.index(target)
    else:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:chicagofed_nfci_missing_col"}

    last_date = None
    last_val = None
    for r in rows[1:]:
        if len(r) <= max(date_idx, val_idx):
            continue
        d_iso = normalize_date_to_iso(r[date_idx])
        v = safe_float(r[val_idx])
        if d_iso and v is not None:
            last_date, last_val = d_iso, v

    if not last_date or last_val is None:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:no_valid_rows"}

    return {
        "data_date": last_date,
        "value": last_val,
        "source_url": url,
        "notes": "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
    }


def fetch_stooq_index(symbol: str, label: str) -> Dict[str, Any]:
    """
    Non-official: stooq free daily CSV.
    Example:
      ^spx -> https://stooq.com/q/d/l/?s=^spx&i=d
    We'll derive 1D% from last two closes (allowed because this source provides both days).
    """
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:stooq_fetch_failed({err})"}

    # stooq header: Date,Open,High,Low,Close,Volume
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:stooq_no_header"}

    rows = []
    for row in reader:
        d_iso = normalize_date_to_iso(row.get("Date", ""))
        c = safe_float(row.get("Close", ""))
        if d_iso and c is not None:
            rows.append((d_iso, c))

    if len(rows) < 1:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:empty"}

    rows.sort(key=lambda x: x[0])
    last_d, last_c = rows[-1]

    out = {
        "data_date": last_d,
        "value": last_c,
        "source_url": url,
        "notes": f"WARN:nonofficial_stooq({symbol});derived_1d_pct",
    }

    if len(rows) >= 2:
        prev_d, prev_c = rows[-2]
        if prev_c != 0:
            out["change_pct_1d"] = (last_c - prev_c) / prev_c * 100.0

    return out


def fetch_wti_datahub() -> Dict[str, Any]:
    """
    Non-official: datahub oil prices dataset (public).
    Keep because you already used it successfully.
    """
    url = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:datahub_fetch_failed({err})"}

    # header might be Date,Price
    d, v = pick_last_valid_from_csv(text, ["Date", "DATE"], "Price")
    if not d or v is None:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:datahub_no_valid_rows"}

    return {
        "data_date": d,
        "value": v,
        "source_url": url,
        "notes": "WARN:nonofficial_datahub_oil_prices(wti-daily)",
    }


def fetch_fredgraph_series(series_id: str) -> Dict[str, Any]:
    """
    FRED 'fredgraph.csv' endpoint:
      https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>
    No API key required.
    Much more stable than parsing HTML.
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    if not ALLOW_FREDGRAPH:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "NA"}

    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:fredgraph_fetch_failed({err})"}

    # Header: DATE,<SERIES_ID>
    d, v = pick_last_valid_from_csv(text, ["DATE", "Date"], series_id)
    if not d or v is None:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:fredgraph_no_valid_rows"}

    return {
        "data_date": d,
        "value": v,
        "source_url": url,
        "notes": "WARN:fredgraph_no_key",
    }


# ---------------------------
# Main assembly
# ---------------------------

def main() -> None:
    as_of_ts = utc_now_iso()
    ensure_out_dir()

    out: List[Dict[str, Any]] = []

    # Meta row
    out.append({
        "series_id": "__META__",
        "data_date": datetime.now(timezone.utc).date().isoformat(),
        "value": SCRIPT_VERSION,
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts,
    })

    # VIX (official-ish: CBOE)
    vix = fetch_cboe_vix()
    out.append({
        "series_id": "VIXCLS",
        **vix,
        "as_of_ts": as_of_ts,
    })

    # Treasury yields (official: U.S. Treasury)
    tsy = fetch_treasury_yields()
    tsy_date = tsy.get("data_date", "NA")
    tsy_url = tsy.get("source_url", "NA")
    tsy_notes = tsy.get("notes", "NA")

    def add_tsy_series(sid: str, val: Any) -> None:
        out.append({
            "series_id": sid,
            "data_date": tsy_date if val != "NA" else "NA",
            "value": val,
            "source_url": tsy_url,
            "notes": tsy_notes if val != "NA" else "ERR:treasury_no_valid_rows",
            "as_of_ts": as_of_ts,
        })

    add_tsy_series("DGS10", tsy.get("DGS10", "NA"))
    add_tsy_series("DGS2", tsy.get("DGS2", "NA"))
    add_tsy_series("UST3M", tsy.get("UST3M", "NA"))

    # Spreads derived from Treasury (still “official” because inputs are)
    d10 = safe_float(str(tsy.get("DGS10", "NA")))
    d2 = safe_float(str(tsy.get("DGS2", "NA")))
    d3m = safe_float(str(tsy.get("UST3M", "NA")))

    if d10 is not None and d2 is not None:
        out.append({
            "series_id": "T10Y2Y",
            "data_date": tsy_date,
            "value": d10 - d2,
            "source_url": tsy_url,
            "notes": "WARN:derived_from_treasury(10Y-2Y)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append({
            "series_id": "T10Y2Y",
            "data_date": "NA",
            "value": "NA",
            "source_url": tsy_url,
            "notes": "ERR:derived_failed(10Y-2Y)",
            "as_of_ts": as_of_ts,
        })

    if d10 is not None and d3m is not None:
        out.append({
            "series_id": "T10Y3M",
            "data_date": tsy_date,
            "value": d10 - d3m,
            "source_url": tsy_url,
            "notes": "WARN:derived_from_treasury(10Y-3M)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append({
            "series_id": "T10Y3M",
            "data_date": "NA",
            "value": "NA",
            "source_url": tsy_url,
            "notes": "ERR:derived_failed(10Y-3M)",
            "as_of_ts": as_of_ts,
        })

    # Chicago Fed NFCI nonfinancial leverage (official: Chicago Fed)
    nfci = fetch_chicagofed_nfci_nonfin_leverage()
    out.append({
        "series_id": "NFCINONFINLEVERAGE",
        **nfci,
        "as_of_ts": as_of_ts,
    })

    # HY OAS (BAMLH0A0HYM2) - No key (fredgraph CSV).
    # If you decide "no FRED even in fallback", set ALLOW_FREDGRAPH=0 and it will be NA (but won't crash).
    hy = fetch_fredgraph_series("BAMLH0A0HYM2")
    out.append({
        "series_id": "BAMLH0A0HYM2",
        **hy,
        "as_of_ts": as_of_ts,
    })

    # Market indices (non-official: stooq)
    for sid, symbol in [("SP500", "^spx"), ("NASDAQCOM", "^ndq"), ("DJIA", "^dji")]:
        r = fetch_stooq_index(symbol, sid)
        row = {
            "series_id": sid,
            "data_date": r.get("data_date", "NA"),
            "value": r.get("value", "NA"),
            "source_url": r.get("source_url", "NA"),
            "notes": r.get("notes", "NA"),
            "as_of_ts": as_of_ts,
        }
        if "change_pct_1d" in r:
            row["change_pct_1d"] = r["change_pct_1d"]
        out.append(row)

    # WTI (non-official: datahub)
    wti = fetch_wti_datahub()
    out.append({
        "series_id": "DCOILWTICO",
        **wti,
        "as_of_ts": as_of_ts,
    })

    # Write output
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()