#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union

import requests


UA = "fred-cache-fallback/1.0 (+github actions; official/no-key first)"
TIMEOUT = 20

OUT_PATH = "fallback_cache/latest.json"


def utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def http_get_text(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (text, err)."""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        return resp.text, None
    except requests.RequestException as e:
        return None, f"request_exc:{type(e).__name__}"


def http_get_bytes(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        return resp.content, None
    except requests.RequestException as e:
        return None, f"request_exc:{type(e).__name__}"


# -------------------------
# FRED series HTML parser
# -------------------------
_OBS_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*:\s*([0-9,.\-]+)")


def parse_fred_observations(html: str) -> List[Tuple[str, str]]:
    """
    Return list of (date, value_str) from the page.
    Value_str may be '.' for missing. We'll filter later.
    """
    # Make it easier for regex: normalize NBSP etc.
    # (Keeping it minimal; regex is tolerant.)
    matches = _OBS_RE.findall(html)
    return matches


def fetch_fred_series_from_html(
    series_id: str,
    want_change_pct_1d: bool,
    as_of_ts: str,
) -> Dict[str, Union[str, float]]:
    url = f"https://fred.stlouisfed.org/series/{series_id}"
    html, err = http_get_text(url)
    if html is None:
        return {
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": f"ERR:fred_html_fetch:{err}",
            "as_of_ts": as_of_ts,
        }

    obs = parse_fred_observations(html)
    # Filter out missing '.' and keep numeric
    cleaned: List[Tuple[str, float]] = []
    for d, v_raw in obs:
        v_raw = v_raw.strip()
        if v_raw == ".":
            continue
        v = safe_float(v_raw.replace(",", ""))
        if v is None:
            continue
        cleaned.append((d, v))

    if not cleaned:
        return {
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:fred_html_no_valid_rows",
            "as_of_ts": as_of_ts,
        }

    latest_date, latest_val = cleaned[0]
    out: Dict[str, Union[str, float]] = {
        "series_id": series_id,
        "data_date": latest_date,
        "value": latest_val,
        "source_url": url,
        "notes": "WARN:fallback_fred_series_html",
        "as_of_ts": as_of_ts,
    }

    if want_change_pct_1d:
        # Need previous non-missing
        if len(cleaned) >= 2:
            prev_date, prev_val = cleaned[1]
            if prev_val != 0:
                chg = (latest_val - prev_val) / prev_val * 100.0
                out["change_pct_1d"] = chg
                out["notes"] = "WARN:fallback_fred_series_html;derived_1d_pct"
            else:
                out["notes"] = "WARN:fallback_fred_series_html;ERR:prev_zero"
        else:
            out["notes"] = "WARN:fallback_fred_series_html;ERR:no_prev_row_for_1d"

    return out


# -------------------------
# CBOE VIX CSV
# -------------------------
def fetch_cboe_vix(as_of_ts: str) -> Dict[str, Union[str, float]]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get_text(url)
    if text is None:
        return {
            "series_id": "VIXCLS",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": f"ERR:cboe_vix_fetch:{err}",
            "as_of_ts": as_of_ts,
        }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {
            "series_id": "VIXCLS",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:cboe_vix_empty",
            "as_of_ts": as_of_ts,
        }

    # Find last valid row with close
    header = lines[0].split(",")
    # Expect columns like DATE, OPEN, HIGH, LOW, CLOSE
    # We'll be robust: locate Date and Close by name.
    try:
        date_i = header.index("DATE")
    except ValueError:
        date_i = 0
    close_i = None
    for k, name in enumerate(header):
        if name.strip().upper() == "CLOSE":
            close_i = k
            break
    if close_i is None:
        close_i = min(4, len(header) - 1)

    for ln in reversed(lines[1:]):
        cols = ln.split(",")
        if len(cols) <= max(date_i, close_i):
            continue
        d = cols[date_i].strip()
        c = cols[close_i].strip()
        v = safe_float(c)
        if v is None:
            continue
        return {
            "series_id": "VIXCLS",
            "data_date": d,
            "value": v,
            "source_url": url,
            "notes": "WARN:fallback_cboe_vix",
            "as_of_ts": as_of_ts,
        }

    return {
        "series_id": "VIXCLS",
        "data_date": "NA",
        "value": "NA",
        "source_url": url,
        "notes": "ERR:cboe_vix_no_valid_rows",
        "as_of_ts": as_of_ts,
    }


# -------------------------
# US Treasury daily yield curve CSV (official)
# -------------------------
def fetch_treasury_yields(as_of_ts: str) -> List[Dict[str, Union[str, float]]]:
    # Use current month in URL (UTC month is ok for daily snapshot use)
    yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{yyyymm}"
        "?_format=csv&field_tdr_date_value_month="
        f"{yyyymm}&page=&type=daily_treasury_yield_curve"
    )

    text, err = http_get_text(url)
    if text is None:
        # Return NA rows for the 3 we care about
        out = []
        for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M"):
            out.append({
                "series_id": sid,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": f"ERR:treasury_fetch:{err}",
                "as_of_ts": as_of_ts,
            })
        return out

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        out = []
        for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M"):
            out.append({
                "series_id": sid,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": "ERR:treasury_empty",
                "as_of_ts": as_of_ts,
            })
        return out

    header = [h.strip() for h in lines[0].split(",")]
    idx = {name: i for i, name in enumerate(header)}

    # Common column names on Treasury: "Date", "3 Mo", "2 Yr", "10 Yr"
    def pick_col(candidates: List[str]) -> Optional[int]:
        for c in candidates:
            if c in idx:
                return idx[c]
        return None

    date_i = pick_col(["Date", "DATE"]) or 0
    mo3_i = pick_col(["3 Mo", "3 MO", "3-month", "3 Month"])
    y2_i = pick_col(["2 Yr", "2 YR", "2-year", "2 Year"])
    y10_i = pick_col(["10 Yr", "10 YR", "10-year", "10 Year"])

    # Find last row with numeric 10Y and 2Y
    latest_row = None
    for ln in reversed(lines[1:]):
        cols = [c.strip() for c in ln.split(",")]
        if len(cols) <= max(date_i, y2_i or 0, y10_i or 0):
            continue
        d = cols[date_i]
        v10 = safe_float(cols[y10_i].replace("%", "")) if y10_i is not None else None
        v2 = safe_float(cols[y2_i].replace("%", "")) if y2_i is not None else None
        v3m = safe_float(cols[mo3_i].replace("%", "")) if mo3_i is not None else None
        if v10 is None or v2 is None:
            continue
        latest_row = (d, v10, v2, v3m)
        break

    if latest_row is None:
        out = []
        for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M"):
            out.append({
                "series_id": sid,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": "ERR:treasury_no_valid_rows",
                "as_of_ts": as_of_ts,
            })
        return out

    d, v10, v2, v3m = latest_row
    out: List[Dict[str, Union[str, float]]] = []

    out.append({
        "series_id": "DGS10",
        "data_date": d,
        "value": v10,
        "source_url": url,
        "notes": "WARN:fallback_treasury_csv",
        "as_of_ts": as_of_ts,
    })
    out.append({
        "series_id": "DGS2",
        "data_date": d,
        "value": v2,
        "source_url": url,
        "notes": "WARN:fallback_treasury_csv",
        "as_of_ts": as_of_ts,
    })
    if v3m is not None:
        out.append({
            "series_id": "UST3M",
            "data_date": d,
            "value": v3m,
            "source_url": url,
            "notes": "WARN:fallback_treasury_csv",
            "as_of_ts": as_of_ts,
        })
        out.append({
            "series_id": "T10Y3M",
            "data_date": d,
            "value": v10 - v3m,
            "source_url": url,
            "notes": "WARN:derived_from_treasury(10Y-3M)",
            "as_of_ts": as_of_ts,
        })
    else:
        out.append({
            "series_id": "UST3M",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:treasury_missing_3m",
            "as_of_ts": as_of_ts,
        })
        out.append({
            "series_id": "T10Y3M",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:treasury_missing_3m",
            "as_of_ts": as_of_ts,
        })

    out.append({
        "series_id": "T10Y2Y",
        "data_date": d,
        "value": v10 - v2,
        "source_url": url,
        "notes": "WARN:derived_from_treasury(10Y-2Y)",
        "as_of_ts": as_of_ts,
    })

    return out


# -------------------------
# Chicago Fed NFCI CSV (official)
# -------------------------
def fetch_nfci_nonfin_leverage(as_of_ts: str) -> Dict[str, Union[str, float]]:
    url = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
    text, err = http_get_text(url)
    if text is None:
        return {
            "series_id": "NFCINONFINLEVERAGE",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": f"ERR:chicagofed_nfci_fetch:{err}",
            "as_of_ts": as_of_ts,
        }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {
            "series_id": "NFCINONFINLEVERAGE",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:chicagofed_nfci_empty",
            "as_of_ts": as_of_ts,
        }

    header = [h.strip() for h in lines[0].split(",")]
    idx = {name: i for i, name in enumerate(header)}

    # Common: first column is "date" or "Date"
    date_i = idx.get("date", idx.get("Date", 0))
    # The column name can be exactly this (as you used)
    val_i = idx.get("NFCINONFINLEVERAGE")

    if val_i is None:
        # Fallback: try fuzzy match
        for k, name in enumerate(header):
            if "NFCI" in name and "LEVERAGE" in name and "NONFIN" in name:
                val_i = k
                break

    if val_i is None:
        return {
            "series_id": "NFCINONFINLEVERAGE",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:chicagofed_nfci_missing_col",
            "as_of_ts": as_of_ts,
        }

    # Find last valid numeric row
    for ln in reversed(lines[1:]):
        cols = [c.strip() for c in ln.split(",")]
        if len(cols) <= max(date_i, val_i):
            continue
        d = cols[date_i]
        v = safe_float(cols[val_i])
        if v is None:
            continue
        return {
            "series_id": "NFCINONFINLEVERAGE",
            "data_date": d,
            "value": v,
            "source_url": url,
            "notes": "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
            "as_of_ts": as_of_ts,
        }

    return {
        "series_id": "NFCINONFINLEVERAGE",
        "data_date": "NA",
        "value": "NA",
        "source_url": url,
        "notes": "ERR:chicagofed_nfci_no_valid_rows",
        "as_of_ts": as_of_ts,
    }


def ensure_out_dir(path: str) -> None:
    import os
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def main() -> int:
    as_of_ts = utc_now_z()

    rows: List[Dict[str, Union[str, float]]] = []
    rows.append({
        "series_id": "__META__",
        "data_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "value": "fallback_vA_official_no_key",
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts,
    })

    # Official / no-key priority
    rows.append(fetch_cboe_vix(as_of_ts))
    rows.extend(fetch_treasury_yields(as_of_ts))
    rows.append(fetch_nfci_nonfin_leverage(as_of_ts))

    # FRED series pages (no key)
    # Weekly / stress / spreads / dollar index / oil / equities
    rows.append(fetch_fred_series_from_html("STLFSI4", want_change_pct_1d=False, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("BAMLH0A0HYM2", want_change_pct_1d=False, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("DTWEXBGS", want_change_pct_1d=False, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("DCOILWTICO", want_change_pct_1d=False, as_of_ts=as_of_ts))

    # Equity indices: prefer FRED over nonofficial sites
    rows.append(fetch_fred_series_from_html("SP500", want_change_pct_1d=True, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("NASDAQCOM", want_change_pct_1d=True, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("DJIA", want_change_pct_1d=True, as_of_ts=as_of_ts))

    ensure_out_dir(OUT_PATH)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH} rows={len(rows)} as_of_ts={as_of_ts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())