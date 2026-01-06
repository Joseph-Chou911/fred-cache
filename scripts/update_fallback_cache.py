#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fallback cache (Version A): "official/no-key first", allow non-official for coverage.
Outputs:
  - fallback_cache/latest.json
  - fallback_cache/latest.csv
  - fallback_cache/manifest.json
Dependencies: requests>=2.31.0

B version changes (retry/backoff + audit-friendly errors):
- Add retry/backoff (2/4/8 sec, max 3 attempts) on 429/5xx, timeout, connection errors.
- Include HTTP status / attempts in ERR notes for audit.
- Round derived spreads to avoid float tail (e.g., 0.5299999999999998 -> 0.53).
- Keep output schema unchanged.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests


# =========================
# Config
# =========================
SCRIPT_VERSION = "fallback_vA_official_no_key_lock"
OUT_DIR = "fallback_cache"

# Sources
CBOE_VIX_CSV_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
CHICAGOFED_NFCI_CSV_URL = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
FREDGRAPH_CSV_FMT = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

# Stooq (non-official)
STOOQ_DAILY_FMT = "https://stooq.com/q/d/l/?s={symbol}&i=d"
# Oil (non-official)
DATAHUB_WTI_DAILY_CSV = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"

# Network retry policy (B version)
TIMEOUT_SECS_DEFAULT = 30
MAX_ATTEMPTS = 3
BACKOFF_SCHEDULE = [2, 4, 8]
RETRY_STATUS = {429, 500, 502, 503, 504}


# =========================
# Helpers
# =========================
def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _round(x: Optional[float], nd: int = 3) -> Optional[float]:
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except Exception:
        return None


def _try_parse_date(s: str) -> Optional[str]:
    """Return ISO date YYYY-MM-DD if parseable, else None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None

    fmts = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _try_parse_float(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.upper() == "NA":
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def atomic_write_text(path: str, content: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    os.replace(tmp, path)


def atomic_write_json(path: str, obj) -> None:
    content = json.dumps(obj, ensure_ascii=False, indent=2)
    atomic_write_text(path, content + "\n")


def _is_retryable_exception(e: Exception) -> bool:
    # Timeout + connection-ish errors are retryable; generic RequestException also often transient
    return isinstance(
        e,
        (
            requests.Timeout,
            requests.ConnectionError,
            requests.ChunkedEncodingError,
            requests.ContentDecodingError,
            requests.TooManyRedirects,
            requests.RequestException,
        ),
    )


def http_get_text(
    session: requests.Session,
    url: str,
    timeout_sec: int = TIMEOUT_SECS_DEFAULT,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (text, err_note). err_note starts with ERR:...
    Retry/backoff: 2s -> 4s -> 8s (max 3 attempts) on:
      - HTTP 429/5xx
      - timeout / connection-ish exceptions
    Audit: include status + attempts in err_note.
    """
    last_status: Optional[int] = None
    last_err: Optional[str] = None

    for i in range(MAX_ATTEMPTS):
        attempt = i + 1
        try:
            resp = session.get(url, timeout=timeout_sec)
            last_status = resp.status_code

            if resp.status_code == 200:
                # utf-8-sig handles BOM
                text = resp.content.decode("utf-8-sig", errors="replace")
                return text, None

            # Non-200
            if resp.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SCHEDULE[i])
                continue

            last_err = f"ERR:http(status={resp.status_code},attempts={attempt})"
            return None, last_err

        except Exception as e:
            # Retry on transient exceptions
            retryable = _is_retryable_exception(e)
            err_type = type(e).__name__

            if retryable and attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SCHEDULE[i])
                last_err = f"ERR:http_exc({err_type},attempts={attempt})"
                continue

            # Final failure
            if isinstance(e, requests.Timeout):
                return None, f"ERR:timeout(attempts={attempt})"
            return None, f"ERR:http_exc({err_type},attempts={attempt})"

    # Should not reach here
    if last_status is not None:
        return None, f"ERR:http(status={last_status},attempts={MAX_ATTEMPTS})"
    return None, last_err or f"ERR:http_unknown(attempts={MAX_ATTEMPTS})"


# =========================
# Fetchers
# =========================
def fetch_cboe_vix_close(session: requests.Session, timeout_sec: int = TIMEOUT_SECS_DEFAULT) -> Tuple[Optional[str], Optional[float], str]:
    """
    CBOE VIX history CSV has Date, Open, High, Low, Close.
    Return latest (date_iso, close, notes)
    """
    text, err = http_get_text(session, CBOE_VIX_CSV_URL, timeout_sec=timeout_sec)
    if err:
        return None, None, f"{err}:cboe_vix"

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows = list(reader)
    if not rows:
        return None, None, "ERR:empty:cboe_vix"

    best_date = None
    best_close = None

    for r in rows:
        d = _try_parse_date(r.get("DATE") or r.get("Date") or r.get("date") or "")
        c = _try_parse_float(r.get("CLOSE") or r.get("Close") or r.get("close") or "")
        if d is None or c is None:
            continue
        if best_date is None or d > best_date:
            best_date = d
            best_close = c

    if best_date is None or best_close is None:
        return None, None, "ERR:no_valid_rows:cboe_vix"

    return best_date, best_close, "WARN:fallback_cboe_vix"


def _month_yyyymm(dt_utc: datetime) -> str:
    return dt_utc.strftime("%Y%m")


def _prev_month_yyyymm(dt_utc: datetime) -> str:
    y = dt_utc.year
    m = dt_utc.month
    if m == 1:
        return f"{y-1}12"
    return f"{y}{m-1:02d}"


def _build_treasury_month_url(yyyymm: str) -> str:
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{yyyymm}"
        "?_format=csv"
        f"&field_tdr_date_value_month={yyyymm}"
        "&page=&type=daily_treasury_yield_curve"
    )


def _pick_treasury_col(fieldnames: List[str], want: str) -> Optional[str]:
    if not fieldnames:
        return None

    targets = []
    if want == "10":
        targets = ["10 Yr", "10 yr", "10Y", "10-Year", "10 Year"]
    elif want == "2":
        targets = ["2 Yr", "2 yr", "2Y", "2-Year", "2 Year"]
    elif want == "3m":
        targets = ["3 Mo", "3 mo", "3M", "3-Mo", "3 Month", "3 months"]
    for t in targets:
        if t in fieldnames:
            return t

    for f in fieldnames:
        low = f.lower().strip()
        if want == "10" and ("10" in low and ("yr" in low or "year" in low)):
            return f
        if want == "2" and (low.startswith("2") and ("yr" in low or "year" in low)):
            return f
        if want == "3m" and ("3" in low and ("mo" in low or "month" in low)):
            return f
    return None


def fetch_treasury_yields(
    session: requests.Session, timeout_sec: int = TIMEOUT_SECS_DEFAULT
) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float], str, str]:
    """
    Return (date_iso, y10, y2, y3m, source_url, notes)
    Tries current month then previous month.
    """
    now = datetime.now(timezone.utc)
    candidates = [_month_yyyymm(now), _prev_month_yyyymm(now)]

    last_err = None
    for yyyymm in candidates:
        url = _build_treasury_month_url(yyyymm)
        text, err = http_get_text(session, url, timeout_sec=timeout_sec)
        if err:
            last_err = f"{err}:treasury_csv"
            continue

        f = io.StringIO(text)
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
        if not rows:
            last_err = "ERR:treasury_empty"
            continue

        date_col = None
        for c in ["Date", "date", "DATE"]:
            if c in fieldnames:
                date_col = c
                break
        if not date_col:
            date_col = fieldnames[0] if fieldnames else None

        c10 = _pick_treasury_col(fieldnames, "10")
        c2 = _pick_treasury_col(fieldnames, "2")
        c3m = _pick_treasury_col(fieldnames, "3m")

        if not date_col or not c10 or not c2 or not c3m:
            last_err = "ERR:treasury_missing_cols"
            continue

        best_date = None
        best_10 = None
        best_2 = None
        best_3m = None

        for r in rows:
            d = _try_parse_date(r.get(date_col, ""))
            y10 = _try_parse_float(r.get(c10, ""))
            y2 = _try_parse_float(r.get(c2, ""))
            y3m = _try_parse_float(r.get(c3m, ""))
            if d is None:
                continue
            if y10 is None or y2 is None or y3m is None:
                continue
            if best_date is None or d > best_date:
                best_date = d
                best_10 = y10
                best_2 = y2
                best_3m = y3m

        if best_date is None:
            last_err = "ERR:treasury_no_valid_rows"
            continue

        return best_date, best_10, best_2, best_3m, url, "WARN:fallback_treasury_csv"

    return None, None, None, None, _build_treasury_month_url(candidates[0]), last_err or "ERR:treasury_no_valid_rows"


def _pick_date_field(fieldnames: List[str], rows: List[Dict[str, str]]) -> Optional[str]:
    if not fieldnames:
        return None

    candidates = ["date", "Date", "DATE", "week", "Week", "WEEK", "observation_date", "TIME", "time"]
    for c in candidates:
        if c in fieldnames:
            return c

    for f in fieldnames[:6]:
        ok = 0
        total = 0
        for r in rows[:60]:
            total += 1
            if _try_parse_date(r.get(f, "")) is not None:
                ok += 1
        if total > 0 and ok / total >= 0.6:
            return f

    return None


def _pick_nonfin_leverage_field(fieldnames: List[str]) -> Optional[str]:
    if not fieldnames:
        return None

    known = [
        "NFCINONFINLEVERAGE",
        "NFCI_NONFIN_LEVERAGE",
        "Nonfinancial Leverage Subindex",
        "Nonfinancial leverage subindex",
    ]
    for k in known:
        if k in fieldnames:
            return k

    for f in fieldnames:
        low = f.strip().lower()
        if ("nonfinancial" in low and "leverage" in low) or (("non" in low and "fin" in low) and "leverage" in low):
            return f

    return None


def fetch_chicagofed_nfci_nonfin_leverage(session: requests.Session, timeout_sec: int = TIMEOUT_SECS_DEFAULT) -> Tuple[Optional[str], Optional[float], str]:
    """
    Return (data_date_iso, value, notes)
    """
    text, err = http_get_text(session, CHICAGOFED_NFCI_CSV_URL, timeout_sec=timeout_sec)
    if err:
        return None, None, f"{err}:chicagofed_nfci"

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames or []
    rows: List[Dict[str, str]] = []
    try:
        for r in reader:
            rows.append(r)
    except Exception as e:
        return None, None, f"ERR:chicagofed_csv_parse({type(e).__name__})"

    if not rows or not fieldnames:
        return None, None, "ERR:chicagofed_empty"

    date_field = _pick_date_field(fieldnames, rows)
    if not date_field:
        return None, None, "ERR:missing_date_col"

    val_field = _pick_nonfin_leverage_field(fieldnames)
    if not val_field:
        return None, None, "ERR:chicagofed_nfci_missing_col"

    best_date = None
    best_val = None
    for r in rows:
        d = _try_parse_date(r.get(date_field, ""))
        v = _try_parse_float(r.get(val_field, ""))
        if d is None or v is None:
            continue
        if best_date is None or d > best_date:
            best_date = d
            best_val = v

    if best_date is None or best_val is None:
        return None, None, "ERR:no_valid_rows"

    return best_date, best_val, "WARN:fallback_chicagofed_nfci(nonfinancial leverage)"


def fetch_fredgraph_last_value(session: requests.Session, series_id: str, timeout_sec: int = TIMEOUT_SECS_DEFAULT) -> Tuple[Optional[str], Optional[float], str, str]:
    """
    FRED fredgraph CSV is generally "no key".
    Return (date_iso, value, source_url, notes)
    """
    url = FREDGRAPH_CSV_FMT.format(series_id=series_id)
    text, err = http_get_text(session, url, timeout_sec=timeout_sec)
    if err:
        return None, None, url, f"{err}:fredgraph"

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows = list(reader)
    if not rows:
        return None, None, url, "ERR:fredgraph_empty"

    date_col = None
    for c in ["DATE", "Date", "date"]:
        if reader.fieldnames and c in reader.fieldnames:
            date_col = c
            break
    if not date_col:
        date_col = (reader.fieldnames[0] if reader.fieldnames else None)

    val_col = series_id if (reader.fieldnames and series_id in reader.fieldnames) else None
    if not val_col:
        if reader.fieldnames and len(reader.fieldnames) >= 2:
            val_col = reader.fieldnames[1]

    best_date = None
    best_val = None

    for r in rows:
        d = _try_parse_date(r.get(date_col, "")) if date_col else None
        v = _try_parse_float(r.get(val_col, "")) if val_col else None
        if d is None or v is None:
            continue
        if best_date is None or d > best_date:
            best_date = d
            best_val = v

    if best_date is None or best_val is None:
        return None, None, url, "ERR:fredgraph_no_valid_rows"

    return best_date, best_val, url, f"WARN:fredgraph_no_key({series_id})"


def fetch_stooq_index(session: requests.Session, symbol: str, timeout_sec: int = TIMEOUT_SECS_DEFAULT) -> Tuple[Optional[str], Optional[float], Optional[float], str]:
    """
    Return (date_iso, close, change_pct_1d, notes)
    """
    url = STOOQ_DAILY_FMT.format(symbol=symbol)
    text, err = http_get_text(session, url, timeout_sec=timeout_sec)
    if err:
        return None, None, None, f"{err}:stooq({symbol})"

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows = list(reader)
    if len(rows) < 1:
        return None, None, None, "ERR:empty"

    def get_close(row) -> Optional[float]:
        return _try_parse_float(row.get("Close") or row.get("CLOSE") or row.get("close"))

    candidates = []
    for r in rows:
        d = _try_parse_date(r.get("Date") or r.get("DATE") or r.get("date") or "")
        c = get_close(r)
        if d and c is not None:
            candidates.append((d, c))
    if not candidates:
        return None, None, None, "ERR:no_valid_rows"

    candidates.sort(key=lambda x: x[0])
    d1, c1 = candidates[-1]
    change = None
    if len(candidates) >= 2:
        d0, c0 = candidates[-2]
        if c0 and c0 != 0:
            change = (c1 - c0) / c0 * 100.0
            change = _round(change, 6)

    return d1, c1, change, f"WARN:nonofficial_stooq({symbol});derived_1d_pct"


def fetch_datahub_wti(session: requests.Session, timeout_sec: int = TIMEOUT_SECS_DEFAULT) -> Tuple[Optional[str], Optional[float], str]:
    """
    datahub wti-daily.csv columns typically: Date, Price
    """
    text, err = http_get_text(session, DATAHUB_WTI_DAILY_CSV, timeout_sec=timeout_sec)
    if err:
        return None, None, f"{err}:datahub_wti"

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows = list(reader)
    if not rows:
        return None, None, "ERR:empty"

    best_date = None
    best_val = None
    for r in rows:
        d = _try_parse_date(r.get("Date") or r.get("DATE") or r.get("date") or "")
        v = _try_parse_float(r.get("Price") or r.get("price") or r.get("VALUE") or r.get("Value") or "")
        if d is None or v is None:
            continue
        if best_date is None or d > best_date:
            best_date = d
            best_val = v

    if best_date is None or best_val is None:
        return None, None, "ERR:no_valid_rows"

    return best_date, best_val, "WARN:nonofficial_datahub_oil_prices(wti-daily)"


# =========================
# Output builders
# =========================
def records_to_csv(records: List[Dict]) -> str:
    fieldnames = ["series_id", "data_date", "value", "source_url", "notes", "as_of_ts", "change_pct_1d"]

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    for r in records:
        row = {k: r.get(k, "") for k in fieldnames}
        writer.writerow(row)
    return out.getvalue()


def build_manifest(repo: str, ref: str, as_of_ts: str) -> Dict:
    base_raw = f"https://raw.githubusercontent.com/{repo}/{ref}/{OUT_DIR}"
    return {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": SCRIPT_VERSION,
        "pinned": {
            "latest_json": f"{base_raw}/latest.json",
            "latest_csv": f"{base_raw}/latest.csv",
            "manifest_json": f"{base_raw}/manifest.json",
        },
        "notes": "Fallback cache; prefers official/no-key sources, allows non-official for coverage.",
    }


# =========================
# Main
# =========================
def main() -> int:
    as_of_ts = utc_now_iso_z()
    ensure_dir(OUT_DIR)

    # Use a session for connection reuse + consistent headers
    session = requests.Session()
    session.headers.update({"User-Agent": "fallback-cache/1.0"})

    records: List[Dict] = []

    # Meta record
    records.append({
        "series_id": "__META__",
        "data_date": utc_today_iso(),
        "value": SCRIPT_VERSION,
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts
    })

    # VIX (official no-key)
    vix_date, vix_val, vix_note = fetch_cboe_vix_close(session)
    records.append({
        "series_id": "VIXCLS",
        "data_date": vix_date if vix_date else "NA",
        "value": vix_val if (vix_val is not None) else "NA",
        "source_url": CBOE_VIX_CSV_URL,
        "notes": vix_note,
        "as_of_ts": as_of_ts
    })

    # Treasury yields (official no-key)
    t_date, y10, y2, y3m, t_url, t_note = fetch_treasury_yields(session)
    records.append({
        "series_id": "DGS10",
        "data_date": t_date if t_date else "NA",
        "value": y10 if (y10 is not None) else "NA",
        "source_url": t_url,
        "notes": t_note if t_date else (t_note or "ERR:treasury_no_valid_rows"),
        "as_of_ts": as_of_ts
    })
    records.append({
        "series_id": "DGS2",
        "data_date": t_date if t_date else "NA",
        "value": y2 if (y2 is not None) else "NA",
        "source_url": t_url,
        "notes": t_note if t_date else (t_note or "ERR:treasury_no_valid_rows"),
        "as_of_ts": as_of_ts
    })
    records.append({
        "series_id": "UST3M",
        "data_date": t_date if t_date else "NA",
        "value": y3m if (y3m is not None) else "NA",
        "source_url": t_url,
        "notes": t_note if t_date else (t_note or "ERR:treasury_no_valid_rows"),
        "as_of_ts": as_of_ts
    })

    # Derived spreads (round to avoid float tails)
    if t_date and (y10 is not None) and (y2 is not None):
        v = _round(y10 - y2, 3)
        records.append({
            "series_id": "T10Y2Y",
            "data_date": t_date,
            "value": v if (v is not None) else "NA",
            "source_url": t_url,
            "notes": "WARN:derived_from_treasury(10Y-2Y)" if (v is not None) else "ERR:derived_round_failed(10Y-2Y)",
            "as_of_ts": as_of_ts
        })
    else:
        records.append({
            "series_id": "T10Y2Y",
            "data_date": "NA",
            "value": "NA",
            "source_url": t_url,
            "notes": "ERR:derived_missing_inputs(10Y-2Y)",
            "as_of_ts": as_of_ts
        })

    if t_date and (y10 is not None) and (y3m is not None):
        v = _round(y10 - y3m, 3)
        records.append({
            "series_id": "T10Y3M",
            "data_date": t_date,
            "value": v if (v is not None) else "NA",
            "source_url": t_url,
            "notes": "WARN:derived_from_treasury(10Y-3M)" if (v is not None) else "ERR:derived_round_failed(10Y-3M)",
            "as_of_ts": as_of_ts
        })
    else:
        records.append({
            "series_id": "T10Y3M",
            "data_date": "NA",
            "value": "NA",
            "source_url": t_url,
            "notes": "ERR:derived_missing_inputs(10Y-3M)",
            "as_of_ts": as_of_ts
        })

    # Chicago Fed NFCI Nonfinancial Leverage (official no-key)
    nfci_date, nfci_val, nfci_note = fetch_chicagofed_nfci_nonfin_leverage(session)
    records.append({
        "series_id": "NFCINONFINLEVERAGE",
        "data_date": nfci_date if nfci_date else "NA",
        "value": nfci_val if (nfci_val is not None) else "NA",
        "source_url": CHICAGOFED_NFCI_CSV_URL,
        "notes": nfci_note if nfci_note else "NA",
        "as_of_ts": as_of_ts
    })

    # HY OAS (no-key via fredgraph)
    hy_date, hy_val, hy_url, hy_note = fetch_fredgraph_last_value(session, "BAMLH0A0HYM2")
    records.append({
        "series_id": "BAMLH0A0HYM2",
        "data_date": hy_date if hy_date else "NA",
        "value": hy_val if (hy_val is not None) else "NA",
        "source_url": hy_url,
        "notes": hy_note,
        "as_of_ts": as_of_ts
    })

    # Equity indices (non-official)
    sp_date, sp_val, sp_chg, sp_note = fetch_stooq_index(session, "^spx")
    records.append({
        "series_id": "SP500",
        "data_date": sp_date if sp_date else "NA",
        "value": sp_val if (sp_val is not None) else "NA",
        "source_url": STOOQ_DAILY_FMT.format(symbol="^spx"),
        "notes": sp_note,
        "as_of_ts": as_of_ts,
        "change_pct_1d": sp_chg if (sp_chg is not None) else ""
    })

    nd_date, nd_val, nd_chg, nd_note = fetch_stooq_index(session, "^ndq")
    records.append({
        "series_id": "NASDAQCOM",
        "data_date": nd_date if nd_date else "NA",
        "value": nd_val if (nd_val is not None) else "NA",
        "source_url": STOOQ_DAILY_FMT.format(symbol="^ndq"),
        "notes": nd_note,
        "as_of_ts": as_of_ts,
        "change_pct_1d": nd_chg if (nd_chg is not None) else ""
    })

    dj_date, dj_val, dj_chg, dj_note = fetch_stooq_index(session, "^dji")
    records.append({
        "series_id": "DJIA",
        "data_date": dj_date if dj_date else "NA",
        "value": dj_val if (dj_val is not None) else "NA",
        "source_url": STOOQ_DAILY_FMT.format(symbol="^dji"),
        "notes": dj_note,
        "as_of_ts": as_of_ts,
        "change_pct_1d": dj_chg if (dj_chg is not None) else ""
    })

    # Oil (non-official)
    oil_date, oil_val, oil_note = fetch_datahub_wti(session)
    records.append({
        "series_id": "DCOILWTICO",
        "data_date": oil_date if oil_date else "NA",
        "value": oil_val if (oil_val is not None) else "NA",
        "source_url": DATAHUB_WTI_DAILY_CSV,
        "notes": oil_note,
        "as_of_ts": as_of_ts
    })

    # Write outputs
    latest_json_path = os.path.join(OUT_DIR, "latest.json")
    latest_csv_path = os.path.join(OUT_DIR, "latest.csv")
    manifest_path = os.path.join(OUT_DIR, "manifest.json")

    atomic_write_json(latest_json_path, records)
    atomic_write_text(latest_csv_path, records_to_csv(records))

    # Build manifest (workflow will overwrite with pinned SHA later; keep this best-effort)
    repo = os.getenv("GITHUB_REPOSITORY", "").strip() or "UNKNOWN/UNKNOWN"
    ref = os.getenv("GITHUB_REF_NAME", "").strip() or "main"
    manifest = build_manifest(repo=repo, ref=ref, as_of_ts=as_of_ts)
    atomic_write_json(manifest_path, manifest)

    # Print to stdout (useful for Actions logs)
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())