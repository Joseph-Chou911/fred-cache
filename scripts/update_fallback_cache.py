#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


# ---------------------------
# Config
# ---------------------------

OUT_DIR = os.path.join(os.getcwd(), "fallback_cache")
OUT_PATH = os.path.join(OUT_DIR, "latest.json")

SCRIPT_VERSION = os.environ.get("FALLBACK_SCRIPT_VERSION", "fallback_vA_official_no_key_20260104_lock_02")

# If you absolutely want "no FRED at all", set ALLOW_FREDGRAPH=0 in workflow env.
ALLOW_FREDGRAPH = os.environ.get("ALLOW_FREDGRAPH", "1").strip() not in ("0", "false", "False", "")

TIMEOUT_SEC = float(os.environ.get("HTTP_TIMEOUT_SEC", "25"))
RETRIES = int(os.environ.get("HTTP_RETRIES", "3"))
BACKOFF_S = [2, 4, 8]  # max 3 tries

DEBUG_HEADERS = os.environ.get("DEBUG_HEADERS", "0").strip() in ("1", "true", "True")


# ---------------------------
# Helpers
# ---------------------------

BOM = "\ufeff"

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() in ("na", "nan", "."):
            return None
        return float(s)
    except Exception:
        return None

def normalize_date_to_iso(d: Any) -> Optional[str]:
    """
    Accept:
      - YYYY-MM-DD
      - MM/DD/YYYY
      - YYYY/MM/DD
      - may include BOM
    Return:
      - YYYY-MM-DD or None
    """
    if d is None:
        return None
    s = str(d).strip().replace(BOM, "")
    if not s or s.lower() == "na":
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return None

def canon_key(s: Any) -> str:
    """
    Canonicalize a column name:
    - remove BOM
    - lower
    - strip spaces
    - remove spaces/underscores/dashes/dots
    """
    if s is None:
        return ""
    t = str(s).replace(BOM, "").strip().lower()
    for ch in (" ", "_", "-", ".", "\t", "\r", "\n"):
        t = t.replace(ch, "")
    return t

def http_get_text(url: str, *, timeout: float = TIMEOUT_SEC) -> Tuple[bool, str, str]:
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

def build_field_map(fieldnames: List[str]) -> Dict[str, str]:
    """
    Return mapping: canonical_key -> original_fieldname
    """
    m: Dict[str, str] = {}
    for f in fieldnames:
        ck = canon_key(f)
        if ck and ck not in m:
            m[ck] = f
    return m

def pick_last_valid_from_csv(text: str, date_col_candidates: List[str], value_col: str) -> Tuple[Optional[str], Optional[float]]:
    if not text.strip():
        return None, None

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return None, None

    field_map = build_field_map(reader.fieldnames)

    date_key = None
    for cand in date_col_candidates:
        ck = canon_key(cand)
        if ck in field_map:
            date_key = field_map[ck]
            break

    val_key = None
    vck = canon_key(value_col)
    if vck in field_map:
        val_key = field_map[vck]

    if DEBUG_HEADERS:
        print("[DEBUG] CSV fieldnames:", reader.fieldnames)
        print("[DEBUG] canonical map keys:", list(field_map.keys())[:30])

    if not date_key or not val_key:
        return None, None

    last_date = None
    last_val = None
    for row in reader:
        d_iso = normalize_date_to_iso(row.get(date_key))
        v = safe_float(row.get(val_key))
        if d_iso and v is not None:
            last_date, last_val = d_iso, v

    return last_date, last_val

def find_col_by_tokens(fieldnames: List[str], tokens: List[str]) -> Optional[str]:
    """
    Find a column whose canonical key contains all tokens (canonicalized).
    """
    f_map = build_field_map(fieldnames)
    for ck, orig in f_map.items():
        ok = True
        for t in tokens:
            if canon_key(t) not in ck:
                ok = False
                break
        if ok:
            return orig
    return None


# ---------------------------
# Fetchers
# ---------------------------

def fetch_cboe_vix() -> Dict[str, Any]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:cboe_fetch_failed({err})"}

    d, v = pick_last_valid_from_csv(text, ["DATE", "Date"], "CLOSE")
    if not d or v is None:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:cboe_no_valid_rows"}

    return {"data_date": d, "value": v, "source_url": url, "notes": "WARN:fallback_cboe_vix"}

def treasury_month_url(yyyymm: str) -> str:
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{yyyymm}"
        "?_format=csv&field_tdr_date_value_month="
        f"{yyyymm}&page=&type=daily_treasury_yield_curve"
    )

def fetch_treasury_yields() -> Dict[str, Any]:
    now = datetime.now(timezone.utc).date()
    yyyymm_cur = f"{now.year}{now.month:02d}"
    yyyymm_prev = f"{now.year - 1}12" if now.month == 1 else f"{now.year}{now.month - 1:02d}"

    candidates = [treasury_month_url(yyyymm_cur), treasury_month_url(yyyymm_prev)]
    best_date: Optional[str] = None
    best_payload: Dict[str, Any] = {}

    for url in candidates:
        ok, text, err = http_get_text(url)
        if not ok:
            continue

        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            continue

        field_map = build_field_map(reader.fieldnames)
        date_key = field_map.get(canon_key("Date"))
        # Treasury typical: "3 Mo", "2 Yr", "10 Yr" (spacing may vary)
        c_3m = find_col_by_tokens(reader.fieldnames, ["3", "mo"])
        c_2y = find_col_by_tokens(reader.fieldnames, ["2", "yr"])
        c_10y = find_col_by_tokens(reader.fieldnames, ["10", "yr"])

        if DEBUG_HEADERS:
            print("[DEBUG] Treasury fields:", reader.fieldnames)
            print("[DEBUG] date_key:", date_key, "3m:", c_3m, "2y:", c_2y, "10y:", c_10y)

        if not date_key or not c_3m or not c_2y or not c_10y:
            continue

        last: Optional[Tuple[str, float, float, float]] = None
        for row in reader:
            d_iso = normalize_date_to_iso(row.get(date_key))
            y3m = safe_float(row.get(c_3m))
            y2y = safe_float(row.get(c_2y))
            y10y = safe_float(row.get(c_10y))
            if d_iso and y3m is not None and y2y is not None and y10y is not None:
                last = (d_iso, y3m, y2y, y10y)

        if last:
            d_iso, y3m, y2y, y10y = last
            if best_date is None or d_iso > best_date:
                best_date = d_iso
                best_payload = {
                    "data_date": d_iso,
                    "UST3M": y3m,
                    "DGS2": y2y,
                    "DGS10": y10y,
                    "source_url": url,
                    "notes": "WARN:fallback_treasury_csv",
                }

    if best_date is None:
        return {
            "data_date": "NA",
            "UST3M": "NA",
            "DGS2": "NA",
            "DGS10": "NA",
            "source_url": candidates[0],
            "notes": "ERR:treasury_no_valid_rows",
        }
    return best_payload

def fetch_chicagofed_nfci_nonfin_leverage() -> Dict[str, Any]:
    url = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:chicagofed_fetch_failed({err})"}
    if not text.strip():
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:chicagofed_empty"}

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:chicagofed_no_header"}

    # date column
    field_map = build_field_map(reader.fieldnames)
    date_key = field_map.get(canon_key("DATE")) or field_map.get(canon_key("Date"))

    # value column:
    # 1) exact canonical match NFCINONFINLEVERAGE
    val_key = field_map.get(canon_key("NFCINONFINLEVERAGE"))
    # 2) fallback token match: "nfci" + "nonfin" + "lever"
    if not val_key:
        val_key = find_col_by_tokens(reader.fieldnames, ["nfci", "nonfin", "lever"])
    # 3) fallback token match: "nonfinancial" + "leverage"
    if not val_key:
        val_key = find_col_by_tokens(reader.fieldnames, ["nonfinancial", "leverage"])

    if DEBUG_HEADERS:
        print("[DEBUG] ChicagoFed fields:", reader.fieldnames)
        print("[DEBUG] date_key:", date_key, "val_key:", val_key)

    if not date_key or not val_key:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:chicagofed_nfci_missing_col"}

    last_date = None
    last_val = None
    for row in reader:
        d_iso = normalize_date_to_iso(row.get(date_key))
        v = safe_float(row.get(val_key))
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

def fetch_stooq_index(symbol: str) -> Dict[str, Any]:
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:stooq_fetch_failed({err})"}

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:stooq_no_header"}

    rows: List[Tuple[str, float]] = []
    for row in reader:
        d_iso = normalize_date_to_iso(row.get("Date") or row.get(f"{BOM}Date"))
        c = safe_float(row.get("Close"))
        if d_iso and c is not None:
            rows.append((d_iso, c))

    if len(rows) < 1:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:empty"}

    rows.sort(key=lambda x: x[0])
    last_d, last_c = rows[-1]
    out: Dict[str, Any] = {
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
    url = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"
    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:datahub_fetch_failed({err})"}

    d, v = pick_last_valid_from_csv(text, ["DATE", "Date"], "Price")
    if not d or v is None:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:datahub_no_valid_rows"}

    return {
        "data_date": d,
        "value": v,
        "source_url": url,
        "notes": "WARN:nonofficial_datahub_oil_prices(wti-daily)",
    }

def fetch_fredgraph_series(series_id: str) -> Dict[str, Any]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    if not ALLOW_FREDGRAPH:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "NA"}

    ok, text, err = http_get_text(url)
    if not ok:
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": f"ERR:fredgraph_fetch_failed({err})"}

    # Robust parse: handle BOM in DATE and in series column
    d, v = pick_last_valid_from_csv(text, ["DATE", "Date"], series_id)
    if not d or v is None:
        # as extra debug: try detect actual value column name (sometimes includes spaces or BOM)
        if DEBUG_HEADERS:
            rdr = csv.DictReader(text.splitlines())
            print("[DEBUG] FREDGRAPH fields:", rdr.fieldnames)
        return {"data_date": "NA", "value": "NA", "source_url": url, "notes": "ERR:fredgraph_no_valid_rows"}

    return {
        "data_date": d,
        "value": v,
        "source_url": url,
        "notes": "WARN:fredgraph_no_key",
    }


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    as_of_ts = utc_now_iso()
    ensure_out_dir()

    out: List[Dict[str, Any]] = []

    out.append({
        "series_id": "__META__",
        "data_date": datetime.now(timezone.utc).date().isoformat(),
        "value": SCRIPT_VERSION,
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts,
    })

    # VIX
    vix = fetch_cboe_vix()
    out.append({"series_id": "VIXCLS", **vix, "as_of_ts": as_of_ts})

    # Treasury
    tsy = fetch_treasury_yields()
    tsy_date = tsy.get("data_date", "NA")
    tsy_url = tsy.get("source_url", "NA")
    tsy_notes = tsy.get("notes", "NA")

    def add_tsy(sid: str, val: Any, note_override: Optional[str] = None) -> None:
        out.append({
            "series_id": sid,
            "data_date": tsy_date if val != "NA" else "NA",
            "value": val,
            "source_url": tsy_url,
            "notes": note_override or (tsy_notes if val != "NA" else "ERR:treasury_no_valid_rows"),
            "as_of_ts": as_of_ts,
        })

    add_tsy("DGS10", tsy.get("DGS10", "NA"))
    add_tsy("DGS2", tsy.get("DGS2", "NA"))
    add_tsy("UST3M", tsy.get("UST3M", "NA"))

    d10 = safe_float(tsy.get("DGS10"))
    d2 = safe_float(tsy.get("DGS2"))
    d3m = safe_float(tsy.get("UST3M"))

    if d10 is not None and d2 is not None:
        add_tsy("T10Y2Y", d10 - d2, "WARN:derived_from_treasury(10Y-2Y)")
    else:
        add_tsy("T10Y2Y", "NA", "ERR:derived_failed(10Y-2Y)")

    if d10 is not None and d3m is not None:
        add_tsy("T10Y3M", d10 - d3m, "WARN:derived_from_treasury(10Y-3M)")
    else:
        add_tsy("T10Y3M", "NA", "ERR:derived_failed(10Y-3M)")

    # Chicago Fed NFCI
    nfci = fetch_chicagofed_nfci_nonfin_leverage()
    out.append({"series_id": "NFCINONFINLEVERAGE", **nfci, "as_of_ts": as_of_ts})

    # HY OAS via fredgraph.csv (no key)
    hy = fetch_fredgraph_series("BAMLH0A0HYM2")
    out.append({"series_id": "BAMLH0A0HYM2", **hy, "as_of_ts": as_of_ts})

    # Equity indices (non-official)
    for sid, sym in [("SP500", "^spx"), ("NASDAQCOM", "^ndq"), ("DJIA", "^dji")]:
        r = fetch_stooq_index(sym)
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

    # WTI (non-official)
    wti = fetch_wti_datahub()
    out.append({"series_id": "DCOILWTICO", **wti, "as_of_ts": as_of_ts})

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()