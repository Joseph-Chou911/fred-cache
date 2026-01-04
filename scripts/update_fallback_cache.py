#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests

# -------------------------
# Config
# -------------------------
OUT_DIR = "fallback_cache"
OUT_FILE = os.path.join(OUT_DIR, "latest.json")

DEBUG_HEADERS_JSON = os.path.join(OUT_DIR, "debug_nfci_headers.json")
DEBUG_FIRSTLINES_TXT = os.path.join(OUT_DIR, "debug_nfci_first_lines.txt")
DEBUG_FREDGRAPH_PREFIX = os.path.join(OUT_DIR, "debug_fredgraph_")  # + {series}.txt

SCRIPT_VERSION = "fallback_vA_official_no_key_20260104_02"

URL_CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

TREASURY_BASE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{yyyymm}"
TREASURY_QS = "?_format=csv&field_tdr_date_value_month={yyyymm}&page=&type=daily_treasury_yield_curve"

URL_CHICAGOFED_NFCI = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"

# FRED (official + no key)
FREDGRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
FRED_SERIES_HTML = "https://fred.stlouisfed.org/series/{series_id}"

# Non-official last resort
URL_DATAHUB_WTI_DAILY = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"
STOOQ_CSV = "https://stooq.com/q/d/l/?s={symbol}&i=d"

UA = "fallback-cache-bot/1.1 (+https://github.com/Joseph-Chou911/fred-cache)"
TIMEOUT = 30


# -------------------------
# Utils
# -------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sleep_backoff(attempt: int) -> None:
    time.sleep(2 ** attempt)  # 2,4,8


def http_get_text(url: str, timeout: int = TIMEOUT, max_retries: int = 3, extra_headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[str], Optional[str]]:
    headers = {"User-Agent": UA}
    if extra_headers:
        headers.update(extra_headers)

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
        if s2 == "" or s2.upper() in ("NA", "N/A") or s2 == ".":
            return None
        return float(s2)
    except Exception:
        return None


def parse_date_any(s: str) -> Optional[str]:
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


def write_nfci_debug(raw_text: str, raw_headers: Optional[List[str]], norm_headers: Optional[List[str]]) -> None:
    first_lines = "\n".join(raw_text.splitlines()[:15])
    with open(DEBUG_FIRSTLINES_TXT, "w", encoding="utf-8") as f:
        f.write(first_lines)
        f.write("\n")

    payload = {
        "raw_headers": raw_headers,
        "normalized_headers": norm_headers,
    }
    with open(DEBUG_HEADERS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_debug_text(path: str, text: str, max_lines: int = 40) -> None:
    lines = text.splitlines()
    head = "\n".join(lines[:max_lines])
    with open(path, "w", encoding="utf-8") as f:
        f.write(head)
        f.write("\n")


def looks_like_html(text: str) -> bool:
    t = text.lstrip().lower()
    return t.startswith("<!doctype html") or t.startswith("<html") or "<html" in t[:500]


def looks_like_csv_with_date(text: str) -> bool:
    # Quick sanity: CSV should have a header containing DATE
    head = "\n".join(text.splitlines()[:3]).lower()
    return "date" in head and ("," in head)


# -------------------------
# Official / no-key: FRED graph CSV + fallback to FRED series HTML
# -------------------------
def fetch_fred_series_html_latest(series_id: str, as_of_ts: str) -> Dict[str, Any]:
    url = FRED_SERIES_HTML.format(series_id=series_id)
    text, err = http_get_text(url, extra_headers={"Accept": "text/html"})
    if err:
        return make_na(series_id, url, err, as_of_ts)
    if looks_like_html(text) is False:
        # Still accept if it is HTML-ish; but if totally weird, record
        pass

    # Try to find the first "YYYY-MM-DD: value" after the word "Observations"
    idx = text.find("Observations")
    hay = text[idx:] if idx != -1 else text

    # Skip "." values; accept numeric (int/float)
    # Example on page: "2025-12-29: 57.89"
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})\s*:\s*([0-9]+(?:\.[0-9]+)?)")
    matches = pattern.findall(hay)
    if not matches:
        # dump some debug
        write_debug_text(f"{DEBUG_FREDGRAPH_PREFIX}{series_id}_html.txt", text)
        return make_na(series_id, url, "html_parse_no_matches", as_of_ts)

    d, v_str = matches[0]
    v = to_float(v_str)
    if v is None:
        write_debug_text(f"{DEBUG_FREDGRAPH_PREFIX}{series_id}_html.txt", text)
        return make_na(series_id, url, "html_parse_bad_value", as_of_ts)

    return {
        "series_id": series_id,
        "data_date": d,
        "value": v,
        "source_url": url,
        "notes": f"WARN:fallback_fred_series_html({series_id})",
        "as_of_ts": as_of_ts,
    }


def fetch_fredgraph_series(series_id: str, as_of_ts: str) -> Dict[str, Any]:
    url = FREDGRAPH.format(series_id=series_id)

    # FRED sometimes behaves differently with Accept/Referer; add both.
    text, err = http_get_text(
        url,
        extra_headers={
            "Accept": "text/csv,text/plain,*/*",
            "Referer": FRED_SERIES_HTML.format(series_id=series_id),
        },
    )
    if err:
        # fallback to HTML
        return fetch_fred_series_html_latest(series_id, as_of_ts)

    # Detect bot/HTML page
    if looks_like_html(text) or (not looks_like_csv_with_date(text)):
        write_debug_text(f"{DEBUG_FREDGRAPH_PREFIX}{series_id}_fredgraph.txt", text)
        # fallback to official HTML series page
        return fetch_fred_series_html_latest(series_id, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    headers = reader.fieldnames or []

    # FRED graph CSV sometimes uses "VALUE" instead of the series_id as column name.
    value_col: Optional[str] = None
    if series_id in headers:
        value_col = series_id
    elif "VALUE" in headers:
        value_col = "VALUE"
    else:
        # pick the 2nd column if it exists
        if len(headers) >= 2:
            value_col = headers[1]

    if not value_col or "DATE" not in headers:
        write_debug_text(f"{DEBUG_FREDGRAPH_PREFIX}{series_id}_fredgraph.txt", text)
        return fetch_fred_series_html_latest(series_id, as_of_ts)

    last_valid: Optional[Tuple[str, float]] = None
    for row in reader:
        d = parse_date_any(row.get("DATE") or "")
        v = to_float(row.get(value_col))
        if d and v is not None:
            last_valid = (d, v)

    if not last_valid:
        write_debug_text(f"{DEBUG_FREDGRAPH_PREFIX}{series_id}_fredgraph.txt", text)
        return fetch_fred_series_html_latest(series_id, as_of_ts)

    d, v = last_valid
    return {
        "series_id": series_id,
        "data_date": d,
        "value": v,
        "source_url": url,
        "notes": f"WARN:fallback_fredgraph_csv({series_id})",
        "as_of_ts": as_of_ts,
    }


# -------------------------
# VIX (publisher feed; no key)
# -------------------------
def fetch_cboe_vix(as_of_ts: str) -> Dict[str, Any]:
    text, err = http_get_text(URL_CBOE_VIX, extra_headers={"Accept": "text/csv,text/plain,*/*"})
    if err:
        return make_na("VIXCLS", URL_CBOE_VIX, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)
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


# -------------------------
# Treasury (official; no key)
# -------------------------
def fetch_treasury_yields(as_of_ts: str) -> List[Dict[str, Any]]:
    yyyymm = datetime.now().strftime("%Y%m")
    url = TREASURY_BASE.format(yyyymm=yyyymm) + TREASURY_QS.format(yyyymm=yyyymm)

    text, err = http_get_text(url, extra_headers={"Accept": "text/csv,text/plain,*/*"})
    if err:
        return [
            make_na("DGS10", url, err, as_of_ts),
            make_na("DGS2", url, err, as_of_ts),
            make_na("UST3M", url, err, as_of_ts),
            make_na("T10Y2Y", url, err, as_of_ts),
            make_na("T10Y3M", url, err, as_of_ts),
        ]

    sio = StringIO(text)
    reader = csv.DictReader(sio)

    last_row: Optional[Dict[str, str]] = None
    for row in reader:
        if (row.get("Date") or "").strip():
            last_row = row

    if not last_row:
        return [
            make_na("DGS10", url, "no_valid_rows", as_of_ts),
            make_na("DGS2", url, "no_valid_rows", as_of_ts),
            make_na("UST3M", url, "no_valid_rows", as_of_ts),
            make_na("T10Y2Y", url, "no_valid_rows", as_of_ts),
            make_na("T10Y3M", url, "no_valid_rows", as_of_ts),
        ]

    d = parse_date_any(last_row.get("Date", "")) or "NA"
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


# -------------------------
# Chicago Fed NFCI (official; no key) - robust
# -------------------------
def _norm(h: str) -> str:
    return (h or "").replace("\ufeff", "").strip()


def _pick_date_norm(norm_headers: List[str]) -> Optional[str]:
    lower_map = {h.lower(): h for h in norm_headers}
    for key in ("date", "observation_date", "week", "period", "time"):
        if key in lower_map:
            return lower_map[key]
    for h in norm_headers:
        l = h.lower()
        if "date" in l or "week" in l:
            return h
    return norm_headers[0] if norm_headers else None


def _pick_nonfin_leverage_norm(norm_headers: List[str]) -> Optional[str]:
    best = None
    best_score = -1
    for h in norm_headers:
        l = h.lower()
        score = 0
        if "nonfinancial" in l or ("non" in l and "fin" in l):
            score += 5
        if "lever" in l:
            score += 5
        if "sub" in l:
            score += 1
        if score > best_score:
            best_score = score
            best = h
    if best_score < 5:
        return None
    return best


def fetch_chicagofed_nfci_nonfin_leverage(as_of_ts: str) -> Dict[str, Any]:
    text, err = http_get_text(URL_CHICAGOFED_NFCI, extra_headers={"Accept": "text/csv,text/plain,*/*"})
    if err:
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)

    raw_headers = list(reader.fieldnames or [])
    if not raw_headers:
        write_nfci_debug(text, raw_headers, None)
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, "no_headers", as_of_ts)

    norm_headers = [_norm(h) for h in raw_headers]
    norm_to_raw = {norm_headers[i]: raw_headers[i] for i in range(len(raw_headers))}

    date_norm = _pick_date_norm(norm_headers)
    val_norm = _pick_nonfin_leverage_norm(norm_headers)

    if not date_norm:
        write_nfci_debug(text, raw_headers, norm_headers)
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, "missing_date_col", as_of_ts)
    if not val_norm:
        write_nfci_debug(text, raw_headers, norm_headers)
        return make_na("NFCINONFINLEVERAGE", URL_CHICAGOFED_NFCI, "missing_value_col", as_of_ts)

    date_col = norm_to_raw[date_norm]
    val_col = norm_to_raw[val_norm]

    last_valid: Optional[Tuple[str, float]] = None
    for row in reader:
        d_raw = (row.get(date_col) or "").strip()
        d = parse_date_any(d_raw)
        v = to_float(row.get(val_col))
        if d and v is not None:
            last_valid = (d, v)

    if not last_valid:
        write_nfci_debug(text, raw_headers, norm_headers)
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


# -------------------------
# Non-official last resort: Stooq indices
# -------------------------
def fetch_stooq_index(series_id: str, symbol: str, as_of_ts: str) -> Dict[str, Any]:
    url = STOOQ_CSV.format(symbol=symbol)
    text, err = http_get_text(url, extra_headers={"Accept": "text/csv,text/plain,*/*"})
    if err:
        return make_na(series_id, url, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)

    rows: List[Tuple[str, float]] = []
    for row in reader:
        d = parse_date_any(row.get("Date") or row.get("date") or "")
        close = to_float(row.get("Close") or row.get("close"))
        if d and close is not None:
            rows.append((d, close))

    if not rows:
        return make_na(series_id, url, "no_valid_rows", as_of_ts)

    d_last, v_last = rows[-1]
    out: Dict[str, Any] = {
        "series_id": series_id,
        "data_date": d_last,
        "value": v_last,
        "source_url": url,
        "notes": f"WARN:nonofficial_stooq({symbol});derived_1d_pct",
        "as_of_ts": as_of_ts,
    }

    if len(rows) >= 2 and rows[-2][1] != 0:
        prev = rows[-2][1]
        out["change_pct_1d"] = (v_last / prev - 1.0) * 100.0
    else:
        out["notes"] = f"WARN:nonofficial_stooq({symbol});missing_prev_close"

    return out


# -------------------------
# Non-official last resort: DataHub WTI
# -------------------------
def fetch_datahub_wti_daily(as_of_ts: str) -> Dict[str, Any]:
    text, err = http_get_text(URL_DATAHUB_WTI_DAILY, extra_headers={"Accept": "text/csv,text/plain,*/*"})
    if err:
        return make_na("DCOILWTICO", URL_DATAHUB_WTI_DAILY, err, as_of_ts)

    sio = StringIO(text)
    reader = csv.DictReader(sio)

    last_valid: Optional[Tuple[str, float]] = None
    for row in reader:
        d = parse_date_any(row.get("Date") or row.get("date") or "")
        v = to_float(row.get("Price") or row.get("price"))
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
        "notes": "WARN:nonofficial_datahub_oil_prices(wti-daily)",
        "as_of_ts": as_of_ts,
    }


def main() -> int:
    as_of_ts = utc_now_iso()
    ensure_out_dir()

    items: List[Dict[str, Any]] = []

    items.append({
        "series_id": "__META__",
        "data_date": as_of_ts[:10],
        "value": SCRIPT_VERSION,
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts,
    })

    # publisher/official feeds
    items.append(fetch_cboe_vix(as_of_ts))
    items.extend(fetch_treasury_yields(as_of_ts))
    items.append(fetch_chicagofed_nfci_nonfin_leverage(as_of_ts))

    # FRED official/no-key: try fredgraph.csv; fallback to series HTML
    items.append(fetch_fredgraph_series("STLFSI4", as_of_ts))
    items.append(fetch_fredgraph_series("BAMLH0A0HYM2", as_of_ts))
    items.append(fetch_fredgraph_series("DTWEXBGS", as_of_ts))

    # WTI: official/no-key first (FRED graph/html), then non-official last resort
    wti_primary = fetch_fredgraph_series("DCOILWTICO", as_of_ts)
    items.append(wti_primary)
    if wti_primary.get("value") == "NA":
        items.append(fetch_datahub_wti_daily(as_of_ts))

    # Indices (non-official)
    items.append(fetch_stooq_index("SP500", "^spx", as_of_ts))
    items.append(fetch_stooq_index("NASDAQCOM", "^ndq", as_of_ts))
    items.append(fetch_stooq_index("DJIA", "^dji", as_of_ts))

    write_json_atomic(OUT_FILE, items)
    print(f"Wrote {OUT_FILE} rows={len(items)} as_of_ts={as_of_ts} version={SCRIPT_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())