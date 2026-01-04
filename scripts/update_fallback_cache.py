#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union

import requests

UA = "fred-cache-fallback/1.1 (+github actions; official/no-key first)"
TIMEOUT = 25
OUT_PATH = "fallback_cache/latest.json"


def utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_date(s: str) -> str:
    """
    Normalize date string to YYYY-MM-DD if possible.
    Supports:
      - YYYY-MM-DD
      - MM/DD/YYYY (CBOE)
    """
    s = (s or "").strip()
    if not s:
        return "NA"
    # YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # MM/DD/YYYY
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"
    return s  # leave as-is if unknown


def safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def norm_key(s: str) -> str:
    """
    Normalize header keys aggressively:
      - lowercase
      - replace NBSP
      - remove all non-alphanumerics
    """
    if s is None:
        return ""
    s = s.replace("\u00A0", " ").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def http_get_text(url: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        resp.encoding = resp.encoding or "utf-8"
        return resp.text, None
    except requests.RequestException as e:
        return None, f"request_exc:{type(e).__name__}"


def ensure_out_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def debug(msg: str) -> None:
    if os.getenv("DEBUG", "0") == "1":
        print(f"[DEBUG] {msg}")


# -------------------------
# FRED series HTML parser (no key)
# -------------------------
_OBS_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*:\s*([0-9,.\-]+)")

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

    # Critical fix: replace NBSP so regex can match
    html = html.replace("\u00A0", " ")

    matches = _OBS_RE.findall(html)
    debug(f"FRED {series_id} regex_matches={len(matches)}")

    cleaned: List[Tuple[str, float]] = []
    for d, v_raw in matches:
        v_raw = v_raw.strip()
        if v_raw == ".":
            continue
        v = safe_float(v_raw.replace(",", ""))
        if v is None:
            continue
        cleaned.append((d, v))

    if not cleaned:
        # dump a small hint for debugging
        debug(f"FRED {series_id} first_500_chars={html[:500]!r}")
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
        if len(cleaned) >= 2:
            prev_date, prev_val = cleaned[1]
            if prev_val != 0:
                out["change_pct_1d"] = (latest_val - prev_val) / prev_val * 100.0
                out["notes"] = "WARN:fallback_fred_series_html;derived_1d_pct"
            else:
                out["notes"] = "WARN:fallback_fred_series_html;ERR:prev_zero"
        else:
            out["notes"] = "WARN:fallback_fred_series_html;ERR:no_prev_row_for_1d"

    return out


# -------------------------
# CBOE VIX CSV (official, no key)
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

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {
            "series_id": "VIXCLS",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:cboe_vix_empty",
            "as_of_ts": as_of_ts,
        }

    reader = csv.reader(lines)
    header = next(reader, [])
    hk = [norm_key(h) for h in header]
    debug(f"CBOE header_keys={hk}")

    # Find DATE and CLOSE columns robustly
    date_i = hk.index("date") if "date" in hk else 0
    close_i = hk.index("close") if "close" in hk else min(4, len(hk) - 1)

    last_valid = None
    for row in reader:
        if len(row) <= max(date_i, close_i):
            continue
        d = row[date_i].strip()
        c = row[close_i].strip()
        v = safe_float(c)
        if v is None:
            continue
        last_valid = (d, v)

    if not last_valid:
        return {
            "series_id": "VIXCLS",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:cboe_vix_no_valid_rows",
            "as_of_ts": as_of_ts,
        }

    d, v = last_valid
    return {
        "series_id": "VIXCLS",
        "data_date": normalize_date(d),  # normalize MM/DD/YYYY -> YYYY-MM-DD
        "value": v,
        "source_url": url,
        "notes": "WARN:fallback_cboe_vix",
        "as_of_ts": as_of_ts,
    }


# -------------------------
# US Treasury daily yield curve CSV (official, no key)
# -------------------------
def fetch_treasury_yields(as_of_ts: str) -> List[Dict[str, Union[str, float]]]:
    yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{yyyymm}"
        "?_format=csv&field_tdr_date_value_month="
        f"{yyyymm}&page=&type=daily_treasury_yield_curve"
    )

    text, err = http_get_text(url)
    if text is None:
        debug(f"Treasury fetch failed: {err}")
        return [{
            "series_id": sid, "data_date": "NA", "value": "NA",
            "source_url": url, "notes": f"ERR:treasury_fetch:{err}", "as_of_ts": as_of_ts
        } for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M")]

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return [{
            "series_id": sid, "data_date": "NA", "value": "NA",
            "source_url": url, "notes": "ERR:treasury_empty", "as_of_ts": as_of_ts
        } for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M")]

    reader = csv.reader(lines)
    header = next(reader, [])
    hk = [norm_key(h) for h in header]
    debug(f"Treasury header_keys={hk}")

    def find_col(*candidates: str) -> Optional[int]:
        for cand in candidates:
            ck = norm_key(cand)
            if ck in hk:
                return hk.index(ck)
        return None

    # fuzzy find by common normalized forms
    date_i = find_col("Date")  # -> "date"
    mo3_i = None
    y2_i = None
    y10_i = None

    # Because header could be like "3 Mo", "3 MO", etc. We'll scan keys:
    for i, k in enumerate(hk):
        if date_i is None and k == "date":
            date_i = i
        if mo3_i is None and k in ("3mo", "3month", "3months"):
            mo3_i = i
        if y2_i is None and k in ("2yr", "2year", "2years"):
            y2_i = i
        if y10_i is None and k in ("10yr", "10year", "10years"):
            y10_i = i

    # If still None, try regex-like contains
    for i, raw in enumerate(header):
        k = norm_key(raw)
        if mo3_i is None and "3" in k and "mo" in k:
            mo3_i = i
        if y2_i is None and "2" in k and "yr" in k:
            y2_i = i
        if y10_i is None and "10" in k and "yr" in k:
            y10_i = i

    if date_i is None or y2_i is None or y10_i is None:
        debug(f"Treasury missing cols: date_i={date_i}, y2_i={y2_i}, y10_i={y10_i}, mo3_i={mo3_i}")
        return [{
            "series_id": sid, "data_date": "NA", "value": "NA",
            "source_url": url, "notes": "ERR:treasury_missing_cols", "as_of_ts": as_of_ts
        } for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M")]

    rows = list(reader)
    # scan backward for last row with numeric 10Y and 2Y
    latest_row = None
    for row in reversed(rows):
        if len(row) <= max(date_i, y2_i, y10_i):
            continue
        d = row[date_i].strip()
        v10 = safe_float(row[y10_i].strip().replace("%", ""))
        v2 = safe_float(row[y2_i].strip().replace("%", ""))
        v3m = None
        if mo3_i is not None and len(row) > mo3_i:
            v3m = safe_float(row[mo3_i].strip().replace("%", ""))
        if v10 is None or v2 is None:
            continue
        latest_row = (d, v10, v2, v3m)
        break

    if latest_row is None:
        debug("Treasury scanned all rows but no numeric 10Y/2Y found.")
        return [{
            "series_id": sid, "data_date": "NA", "value": "NA",
            "source_url": url, "notes": "ERR:treasury_no_valid_rows", "as_of_ts": as_of_ts
        } for sid in ("DGS10", "DGS2", "UST3M", "T10Y2Y", "T10Y3M")]

    d, v10, v2, v3m = latest_row
    d = normalize_date(d)

    out: List[Dict[str, Union[str, float]]] = [
        {"series_id": "DGS10", "data_date": d, "value": v10, "source_url": url, "notes": "WARN:fallback_treasury_csv", "as_of_ts": as_of_ts},
        {"series_id": "DGS2",  "data_date": d, "value": v2,  "source_url": url, "notes": "WARN:fallback_treasury_csv", "as_of_ts": as_of_ts},
        {"series_id": "T10Y2Y","data_date": d, "value": v10 - v2, "source_url": url, "notes": "WARN:derived_from_treasury(10Y-2Y)", "as_of_ts": as_of_ts},
    ]

    if v3m is not None:
        out.append({"series_id": "UST3M", "data_date": d, "value": v3m, "source_url": url, "notes": "WARN:fallback_treasury_csv", "as_of_ts": as_of_ts})
        out.append({"series_id": "T10Y3M","data_date": d, "value": v10 - v3m, "source_url": url, "notes": "WARN:derived_from_treasury(10Y-3M)", "as_of_ts": as_of_ts})
    else:
        out.append({"series_id": "UST3M", "data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:treasury_missing_3m", "as_of_ts": as_of_ts})
        out.append({"series_id": "T10Y3M","data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:treasury_missing_3m", "as_of_ts": as_of_ts})

    return out


# -------------------------
# Chicago Fed NFCI CSV (official, no key)
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

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {
            "series_id": "NFCINONFINLEVERAGE",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:chicagofed_nfci_empty",
            "as_of_ts": as_of_ts,
        }

    reader = csv.reader(lines)
    header = next(reader, [])
    hk = [norm_key(h) for h in header]
    debug(f"NFCI header_keys(first20)={hk[:20]}")

    # date column
    date_i = hk.index("date") if "date" in hk else 0

    # find leverage column by normalized key match
    target = "nfcinonfinleverage"
    val_i = hk.index(target) if target in hk else None

    # fallback: contains nonfinancial + leverage
    if val_i is None:
        for i, k in enumerate(hk):
            if "nonfinancial" in k and "leverage" in k:
                val_i = i
                break

    if val_i is None:
        debug(f"NFCI missing leverage col. header_raw={header[:25]}")
        return {
            "series_id": "NFCINONFINLEVERAGE",
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": "ERR:chicagofed_nfci_missing_col",
            "as_of_ts": as_of_ts,
        }

    rows = list(reader)
    for row in reversed(rows):
        if len(row) <= max(date_i, val_i):
            continue
        d = normalize_date(row[date_i].strip())
        v = safe_float(row[val_i].strip())
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


def main() -> int:
    as_of_ts = utc_now_z()

    rows: List[Dict[str, Union[str, float]]] = [{
        "series_id": "__META__",
        "data_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "value": "fallback_vA_official_no_key",
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts,
    }]

    # Official no-key sources
    rows.append(fetch_cboe_vix(as_of_ts))
    rows.extend(fetch_treasury_yields(as_of_ts))
    rows.append(fetch_nfci_nonfin_leverage(as_of_ts))

    # FRED series HTML (no key) - now NBSP-safe
    rows.append(fetch_fred_series_from_html("STLFSI4", want_change_pct_1d=False, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("BAMLH0A0HYM2", want_change_pct_1d=False, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("DTWEXBGS", want_change_pct_1d=False, as_of_ts=as_of_ts))
    rows.append(fetch_fred_series_from_html("DCOILWTICO", want_change_pct_1d=False, as_of_ts=as_of_ts))

    # Equity indices: FRED + derived 1D%
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