#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fallback cache updater (latest-only).
- Writes: fallback_cache/latest.json
- Sources:
  1) Cboe VIX CSV
  2) U.S. Treasury daily yield curve CSV (10Y/2Y/3M + derived spreads)
  3) Chicago Fed NFCI CSV (nonfinancial leverage subindex)
  4) STOOQ CSV endpoint (indices/futures): ^SPX, ^NDQ, ^DJI, DX.F, CL.F
Design goals:
- Auditable fields: series_id, data_date, value, source_url, notes, as_of_ts
- No history in version A
- Never crash the whole run: per-series NA on failure
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests


# -----------------------------
# Config
# -----------------------------

OUT_DIR = "fallback_cache"
OUT_LATEST_JSON = os.path.join(OUT_DIR, "latest.json")

# Cboe VIX
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

# U.S. Treasury (monthly CSV, you already use this pattern)
# We will compute current YYYYMM in UTC; Treasury data is U.S. dates.
TREASURY_MONTHLY_TEMPLATE = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/all/{yyyymm}"
    "?_format=csv&field_tdr_date_value_month={yyyymm}&page=&type=daily_treasury_yield_curve"
)

# Chicago Fed NFCI (includes subindexes)
CHICAGO_FED_NFCI_CSV = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"

# STOOQ direct CSV endpoint
# Commonly used pattern: https://stooq.com/q/d/l/?s=^dji&i=d  (daily)
# NOTE: STOOQ may change behavior; we guard by validating CSV headers.
STOOQ_CSV_TEMPLATE = "https://stooq.com/q/d/l/?s={symbol}&i={interval}"


# HTTP
UA = "fallback-cache/1.0 (+https://github.com/Joseph-Chou911/fred-cache)"
TIMEOUT = 20


# -----------------------------
# Helpers
# -----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def safe_float(x: str) -> Optional[float]:
    try:
        if x is None:
            return None
        x = str(x).strip()
        if x == "" or x.upper() == "NA" or x.upper() == "N/A":
            return None
        return float(x)
    except Exception:
        return None


def make_na_row(series_id: str, as_of_ts: str, source_url: str = "NA", notes: str = "NA") -> Dict[str, Any]:
    return {
        "series_id": series_id,
        "data_date": "NA",
        "value": "NA",
        "source_url": source_url if source_url else "NA",
        "notes": notes if notes else "NA",
        "as_of_ts": as_of_ts,
    }


def http_get_text(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (text, error). error is None on success.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        return resp.text, None
    except requests.exceptions.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, f"exception:{type(e).__name__}"


# -----------------------------
# Fetchers
# -----------------------------

def fetch_vix(as_of_ts: str) -> Dict[str, Any]:
    """
    Parse Cboe VIX_History.csv and return latest row (Date, VIX Close).
    """
    text, err = http_get_text(CBOE_VIX_CSV)
    if err or not text:
        return make_na_row("VIXCLS", as_of_ts, source_url=CBOE_VIX_CSV, notes=f"ERR:{err or 'empty'}")

    # Expect header includes "DATE" and "CLOSE" or similar
    sio = StringIO(text)
    reader = csv.DictReader(sio)
    rows = list(reader)
    if not rows:
        return make_na_row("VIXCLS", as_of_ts, source_url=CBOE_VIX_CSV, notes="ERR:no_rows")

    # Cboe file is usually newest-first? We will scan for max date.
    best = None
    best_date = None
    for r in rows:
        d = (r.get("DATE") or r.get("Date") or r.get("date") or "").strip()
        v = r.get("CLOSE") or r.get("Close") or r.get("close")
        fv = safe_float(v)
        if not d or fv is None:
            continue
        try:
            dt = datetime.strptime(d, "%m/%d/%Y").date()  # Cboe format
        except Exception:
            continue
        if best_date is None or dt > best_date:
            best_date = dt
            best = fv

    if best_date is None or best is None:
        return make_na_row("VIXCLS", as_of_ts, source_url=CBOE_VIX_CSV, notes="ERR:parse_failed")

    return {
        "series_id": "VIXCLS",
        "data_date": best_date.isoformat(),
        "value": best,
        "source_url": CBOE_VIX_CSV,
        "notes": "WARN:fallback_cboe_vix",
        "as_of_ts": as_of_ts,
    }


def fetch_treasury_yields(as_of_ts: str) -> List[Dict[str, Any]]:
    """
    Parse Treasury daily yield curve for current month; pick latest date.
    Output DGS10, DGS2, UST3M, plus derived T10Y2Y, T10Y3M.
    """
    yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    url = TREASURY_MONTHLY_TEMPLATE.format(yyyymm=yyyymm)
    text, err = http_get_text(url)
    if err or not text:
        # Return NA rows for all
        return [
            make_na_row("DGS10", as_of_ts, source_url=url, notes=f"ERR:{err or 'empty'}"),
            make_na_row("DGS2", as_of_ts, source_url=url, notes=f"ERR:{err or 'empty'}"),
            make_na_row("UST3M", as_of_ts, source_url=url, notes=f"ERR:{err or 'empty'}"),
            make_na_row("T10Y2Y", as_of_ts, source_url=url, notes=f"ERR:{err or 'empty'}"),
            make_na_row("T10Y3M", as_of_ts, source_url=url, notes=f"ERR:{err or 'empty'}"),
        ]

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    rows = list(reader)
    if not rows:
        return [
            make_na_row("DGS10", as_of_ts, source_url=url, notes="ERR:no_rows"),
            make_na_row("DGS2", as_of_ts, source_url=url, notes="ERR:no_rows"),
            make_na_row("UST3M", as_of_ts, source_url=url, notes="ERR:no_rows"),
            make_na_row("T10Y2Y", as_of_ts, source_url=url, notes="ERR:no_rows"),
            make_na_row("T10Y3M", as_of_ts, source_url=url, notes="ERR:no_rows"),
        ]

    # Treasury columns: "Date", "3 Mo", "2 Yr", "10 Yr" etc.
    # We choose the latest date with non-empty 10/2/3m.
    best_date = None
    best_10 = best_2 = best_3m = None

    for r in rows:
        d = (r.get("Date") or r.get("date") or "").strip()
        if not d:
            continue
        try:
            dt = datetime.strptime(d, "%m/%d/%Y").date()
        except Exception:
            continue

        v10 = safe_float(r.get("10 Yr") or r.get("10YR") or r.get("10Y") or r.get("10 yr"))
        v2 = safe_float(r.get("2 Yr") or r.get("2YR") or r.get("2Y") or r.get("2 yr"))
        v3m = safe_float(r.get("3 Mo") or r.get("3MO") or r.get("3M") or r.get("3 mo"))

        # keep if any exists; but spreads need both
        if best_date is None or dt > best_date:
            best_date = dt
            best_10, best_2, best_3m = v10, v2, v3m

    if best_date is None:
        return [
            make_na_row("DGS10", as_of_ts, source_url=url, notes="ERR:date_parse_failed"),
            make_na_row("DGS2", as_of_ts, source_url=url, notes="ERR:date_parse_failed"),
            make_na_row("UST3M", as_of_ts, source_url=url, notes="ERR:date_parse_failed"),
            make_na_row("T10Y2Y", as_of_ts, source_url=url, notes="ERR:date_parse_failed"),
            make_na_row("T10Y3M", as_of_ts, source_url=url, notes="ERR:date_parse_failed"),
        ]

    out: List[Dict[str, Any]] = []
    d_iso = best_date.isoformat()

    def row(series_id: str, val: Optional[float], notes: str) -> Dict[str, Any]:
        if val is None:
            return make_na_row(series_id, as_of_ts, source_url=url, notes="ERR:missing_value")
        return {
            "series_id": series_id,
            "data_date": d_iso,
            "value": val,
            "source_url": url,
            "notes": notes,
            "as_of_ts": as_of_ts,
        }

    out.append(row("DGS10", best_10, "WARN:fallback_treasury_csv"))
    out.append(row("DGS2", best_2, "WARN:fallback_treasury_csv"))
    out.append(row("UST3M", best_3m, "WARN:fallback_treasury_csv"))

    # Derived spreads (only if both inputs exist)
    if best_10 is not None and best_2 is not None:
        out.append({
            "series_id": "T10Y2Y",
            "data_date": d_iso,
            "value": best_10 - best_2,
            "source_url": url,
            "notes": "WARN:derived_from_treasury(10Y-2Y)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append(make_na_row("T10Y2Y", as_of_ts, source_url=url, notes="ERR:missing_input_for_spread"))

    if best_10 is not None and best_3m is not None:
        out.append({
            "series_id": "T10Y3M",
            "data_date": d_iso,
            "value": best_10 - best_3m,
            "source_url": url,
            "notes": "WARN:derived_from_treasury(10Y-3M)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append(make_na_row("T10Y3M", as_of_ts, source_url=url, notes="ERR:missing_input_for_spread"))

    return out


def fetch_chicago_fed_nfci_nonfin_leverage(as_of_ts: str) -> Dict[str, Any]:
    """
    Chicago Fed NFCI CSV includes subindexes. We pull the latest non-empty value of:
      - NFCI Nonfinancial Leverage Subindex
    Column naming can vary; we search headers by keywords.
    """
    text, err = http_get_text(CHICAGO_FED_NFCI_CSV)
    if err or not text:
        return make_na_row("NFCINONFINLEVERAGE", as_of_ts, source_url=CHICAGO_FED_NFCI_CSV, notes=f"ERR:{err or 'empty'}")

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    headers = [h.strip() for h in (reader.fieldnames or [])]

    # Find a column likely representing nonfinancial leverage subindex
    # We try multiple patterns for robustness.
    target_col = None
    patterns = [
        re.compile(r"non.?financial.*leverage", re.IGNORECASE),
        re.compile(r"nonfinancial.*leverage", re.IGNORECASE),
    ]
    for h in headers:
        for p in patterns:
            if p.search(h):
                target_col = h
                break
        if target_col:
            break

    if not target_col:
        return make_na_row("NFCINONFINLEVERAGE", as_of_ts, source_url=CHICAGO_FED_NFCI_CSV, notes="ERR:col_not_found")

    best_date = None
    best_val = None

    for r in reader:
        d = (r.get("DATE") or r.get("Date") or r.get("date") or "").strip()
        if not d:
            continue
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            continue
        v = safe_float(r.get(target_col))
        if v is None:
            continue
        if best_date is None or dt > best_date:
            best_date = dt
            best_val = v

    if best_date is None or best_val is None:
        return make_na_row("NFCINONFINLEVERAGE", as_of_ts, source_url=CHICAGO_FED_NFCI_CSV, notes="ERR:no_valid_rows")

    return {
        "series_id": "NFCINONFINLEVERAGE",
        "data_date": best_date.isoformat(),
        "value": best_val,
        "source_url": CHICAGO_FED_NFCI_CSV,
        "notes": "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
        "as_of_ts": as_of_ts,
    }


def fetch_stooq_latest(symbol: str, interval: str = "d") -> Tuple[Optional[str], Optional[float], Optional[float], Optional[str]]:
    """
    Fetch STOOQ CSV via /q/d/l endpoint and return:
      (latest_date_iso, latest_close, change_pct_1d, error)
    change_pct_1d uses previous close if available.
    """
    url = STOOQ_CSV_TEMPLATE.format(symbol=symbol, interval=interval)
    text, err = http_get_text(url)
    if err or not text:
        return None, None, None, f"ERR:{err or 'empty'}"

    # Validate it looks like CSV (first line starts with "Date," or "DATE,")
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    if not re.match(r"(?i)^date,", first_line):
        # could be HTML / challenge page
        return None, None, None, "ERR:not_csv"

    sio = StringIO(text)
    reader = csv.DictReader(sio)
    rows = list(reader)
    if not rows:
        return None, None, None, "ERR:no_rows"

    # STOOQ CSV commonly sorted ascending by date
    # We take last two valid close rows.
    def parse_row(r: Dict[str, str]) -> Tuple[Optional[datetime], Optional[float]]:
        d = (r.get("Date") or r.get("date") or "").strip()
        c = safe_float(r.get("Close") or r.get("close"))
        if not d or c is None:
            return None, None
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            return None, None
        return dt, c

    valid: List[Tuple[datetime, float]] = []
    for r in rows:
        dt, c = parse_row(r)
        if dt and c is not None:
            valid.append((dt, c))

    if not valid:
        return None, None, None, "ERR:no_valid_data"

    valid.sort(key=lambda x: x[0])
    latest_dt, latest_close = valid[-1]
    change_pct_1d = None
    if len(valid) >= 2:
        prev_dt, prev_close = valid[-2]
        if prev_close != 0:
            change_pct_1d = (latest_close / prev_close - 1.0) * 100.0

    return latest_dt.date().isoformat(), latest_close, change_pct_1d, None


def build_stooq_rows(as_of_ts: str) -> List[Dict[str, Any]]:
    """
    Add coverage: SP500, NASDAQCOM, DJIA, DXY_FUT, WTI_CL_F
    """
    mapping = [
        ("SP500", "^spx", "WARN:fallback_stooq(^SPX)"),
        ("NASDAQCOM", "^ndq", "WARN:fallback_stooq(^NDQ)"),
        ("DJIA", "^dji", "WARN:fallback_stooq(^DJI)"),
        ("DXY_FUT", "dx.f", "WARN:fallback_stooq(DX.F)"),
        ("WTI_CL_F", "cl.f", "WARN:fallback_stooq(CL.F)"),
    ]

    out: List[Dict[str, Any]] = []
    for series_id, symbol, note in mapping:
        url = STOOQ_CSV_TEMPLATE.format(symbol=symbol, interval="d")
        d, v, chg, e = fetch_stooq_latest(symbol, interval="d")
        if e or d is None or v is None:
            out.append(make_na_row(series_id, as_of_ts, source_url=url, notes=e or "ERR:unknown"))
            continue

        row: Dict[str, Any] = {
            "series_id": series_id,
            "data_date": d,
            "value": v,
            "source_url": url,
            "notes": note,
            "as_of_ts": as_of_ts,
        }
        # Optional auditable derived field (won't break consumers expecting minimal schema)
        if chg is not None:
            row["change_pct_1d"] = chg
            row["notes"] = note + ";derived_1d_pct"
        out.append(row)

    return out


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    as_of_ts = utc_now_iso()
    ensure_out_dir()

    rows: List[Dict[str, Any]] = []

    # 1) VIX
    rows.append(fetch_vix(as_of_ts))

    # 2) Treasury yields + spreads
    rows.extend(fetch_treasury_yields(as_of_ts))

    # 3) Chicago Fed NFCI nonfinancial leverage
    rows.append(fetch_chicago_fed_nfci_nonfin_leverage(as_of_ts))

    # 4) STOOQ coverage expansion
    rows.extend(build_stooq_rows(as_of_ts))

    # Keep placeholder if you still want it
    # (You can remove it if it no longer matters)
    rows.append(make_na_row("NFCI_LEVERAGE_SUBINDEX", as_of_ts))

    with open(OUT_LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_LATEST_JSON} rows={len(rows)} as_of_ts={as_of_ts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())