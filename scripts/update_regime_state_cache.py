#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_regime_state_cache.py  (v3.3.1)
- Treasury: XML primary (+ CSV fallback)
- VIX: CBOE CSV primary (+ Stooq fallback)
- OFR FSI: use official CSV https://www.financialresearch.gov/financial-stress-index/data/fsi.csv
- Credit axis: HYG/IEF ratio vs MA60 deviation
- Regime output: REGIME_STATE + REGIME_CONFIDENCE + REGIME_REASONS
- IMPORTANT: if BE10Y_PROXY missing this run, allow carry-forward from recent history (<= 7 days) WITH explicit reasons
- Date normalization + history dedup (avoid duplicates due to mixed date formats)
"""

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

import requests
from xml.etree import ElementTree as ET

# -------------------------
# Paths / Outputs
# -------------------------
OUT_DIR = "regime_state_cache"
LATEST_JSON = os.path.join(OUT_DIR, "latest.json")
LATEST_CSV = os.path.join(OUT_DIR, "latest.csv")
HISTORY_JSON = os.path.join(OUT_DIR, "history.json")
MANIFEST_JSON = os.path.join(OUT_DIR, "manifest.json")

# -------------------------
# Config
# -------------------------
SCRIPT_VERSION = "regime_state_cache_v3_3_1"

MAX_HISTORY_ROWS = 5000  # plenty; dedup keeps it compact

# Stooq symbols
SYMBOL_HYG = "hyg.us"
SYMBOL_IEF = "ief.us"
SYMBOL_TIP = "tip.us"
SYMBOL_VIX_FALLBACK = "^vix"  # stooq index

STOOQ_URL_TMPL = "https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"

# CBOE VIX official
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

# OFR FSI official
OFR_FSI_CSV = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"

# US Treasury XML (Drupal Views output)
TREASURY_XML_TMPL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data={data}&field_tdr_date_value_month={yyyymm}"
)

# US Treasury CSV fallback (some months may 404 for real curve on older patterns; keep as fallback only)
TREASURY_CSV_TMPL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "{csv_name}/all/{yyyymm}?_format=csv&field_tdr_date_value_month={yyyymm}&type={type_name}"
)

TREASURY_NOMINAL_DATA = "daily_treasury_yield_curve"
TREASURY_REAL_DATA = "daily_treasury_real_yield_curve"

TREASURY_NOMINAL_CSV_NAME = "daily-treasury-rates.csv"
TREASURY_REAL_CSV_NAME = "daily-treasury-real-yield-curve-rates.csv"
TREASURY_NOMINAL_TYPE = "daily_treasury_yield_curve"
TREASURY_REAL_TYPE = "daily_treasury_real_yield_curve"

# Regime thresholds (keep conservative; adjust later if you want)
VIX_LOW_TH = 20.0
VIX_HIGH_TH = 30.0

BE_LOW_TH = 1.5
BE_HIGH_TH = 3.0

CREDIT_DEV_ON_TH_PCT = +1.0   # ratio above MA60 by +1% => credit improving
CREDIT_DEV_OFF_TH_PCT = -1.0  # ratio below MA60 by -1% => credit deteriorating

# MA requirements / confidence caps
MA_WINDOW = 60
CREDIT_MIN_POINTS_LOW_CAP = 20   # if <20 points, confidence must be LOW
CREDIT_MIN_POINTS_MED_CAP = 60   # if <60 points, confidence <= MEDIUM

# carry-forward window for BE10Y_PROXY when missing
BE_CARRY_FORWARD_MAX_AGE_DAYS = 7

# treasury pairing tolerance if exact match missing
TREASURY_PAIR_NEAREST_MAX_DAYS = 7

# HTTP
DEFAULT_TIMEOUT = 20
MAX_RETRIES = 3
BACKOFFS = [2, 4, 8]

TZ_TAIPEI = timezone(timedelta(hours=8))


# -------------------------
# Helpers: time/date
# -------------------------
def now_taipei_iso() -> str:
    return datetime.now(TZ_TAIPEI).isoformat(timespec="microseconds")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def yyyymm_for(dt: date) -> str:
    return f"{dt.year:04d}{dt.month:02d}"


def parse_date_any(s: str) -> Optional[str]:
    """
    Normalize various date formats into YYYY-MM-DD.
    Accepts: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, MM/DD/YYYY, DD-Mon-YYYY, etc.
    Returns None if cannot parse.
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.upper() == "NA":
        return None

    # If ISO date already
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s

    # ISO datetime
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ].*$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{yy:04d}-{mm:02d}-{dd:02d}"

    # Try a few common strptime patterns
    for fmt in ("%Y/%m/%d", "%d-%b-%Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


def parse_float_safe(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None


# -------------------------
# Helpers: HTTP
# -------------------------
def http_get_text(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (text, err_note)
    """
    headers = {
        "User-Agent": "fred-cache-bot/1.0 (requests)",
        "Accept": "*/*",
    }
    last_err = None
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
            else:
                return r.text, None
        except Exception as e:
            last_err = f"EXC:{type(e).__name__}"
        if i < len(BACKOFFS):
            time.sleep(BACKOFFS[i])
    return None, last_err or "unknown_error"


def http_get_bytes(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[Optional[bytes], Optional[str]]:
    headers = {
        "User-Agent": "fred-cache-bot/1.0 (requests)",
        "Accept": "*/*",
    }
    last_err = None
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
            else:
                return r.content, None
        except Exception as e:
            last_err = f"EXC:{type(e).__name__}"
        if i < len(BACKOFFS):
            time.sleep(BACKOFFS[i])
    return None, last_err or "unknown_error"


# -------------------------
# History IO + normalization/dedup
# -------------------------
def load_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def normalize_and_dedup_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Dedup by (series_id, data_date) keeping the one with latest as_of_ts.
    Also normalizes data_date into YYYY-MM-DD where possible.
    """
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def asof_key(r: Dict[str, Any]) -> str:
        s = str(r.get("as_of_ts", "")).strip()
        return s

    for r in rows:
        sid = str(r.get("series_id", "")).strip()
        d0 = r.get("data_date", "NA")
        d = parse_date_any(str(d0)) or "NA"
        r2 = dict(r)
        r2["series_id"] = sid
        r2["data_date"] = d

        if not sid or d == "NA":
            # keep but key it uniquely by as_of_ts to avoid collapsing different NA rows
            # (these should be rare; we still keep them as evidence)
            k = (sid or "__EMPTY__", f"NA::{asof_key(r2)}")
        else:
            k = (sid, d)

        if k not in best:
            best[k] = r2
        else:
            # keep the newer as_of_ts if possible
            if asof_key(r2) >= asof_key(best[k]):
                best[k] = r2

    out = list(best.values())

    # Sort stable: by series_id then data_date then as_of_ts
    def sort_key(r: Dict[str, Any]) -> Tuple[str, str, str]:
        return (
            str(r.get("series_id", "")),
            str(r.get("data_date", "")),
            str(r.get("as_of_ts", "")),
        )

    out.sort(key=sort_key)
    return out[-MAX_HISTORY_ROWS:]


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_latest_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "NA") for k in fields})


def upsert_today(history: List[Dict[str, Any]], new_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = history + new_rows
    merged = normalize_and_dedup_history(merged)
    return merged


def get_recent_history_value(
    history: List[Dict[str, Any]],
    series_id: str,
    max_age_days: int,
    ref_date: str,
) -> Tuple[Optional[Tuple[str, float]], Optional[str]]:
    """
    Find latest (data_date, value) for series_id within max_age_days before ref_date.
    Returns ((data_date, value), note) or (None, reason)
    """
    ref_iso = parse_date_any(ref_date)
    if not ref_iso:
        return None, "bad_ref_date"
    try:
        ref_dt = datetime.strptime(ref_iso, "%Y-%m-%d").date()
    except Exception:
        return None, "bad_ref_date"

    best_dd = None
    best_val = None

    for r in history:
        if str(r.get("series_id", "")).strip() != series_id:
            continue
        dd = parse_date_any(str(r.get("data_date", "")))
        if not dd:
            continue
        v = parse_float_safe(r.get("value"))
        if v is None:
            continue
        try:
            ddt = datetime.strptime(dd, "%Y-%m-%d").date()
        except Exception:
            continue
        age = (ref_dt - ddt).days
        if age < 0:
            continue
        if age <= max_age_days:
            if best_dd is None or ddt > datetime.strptime(best_dd, "%Y-%m-%d").date():
                best_dd = dd
                best_val = v

    if best_dd is None or best_val is None:
        return None, "no_recent_history"
    return (best_dd, best_val), None


# -------------------------
# Treasury parsing
# -------------------------
def parse_treasury_xml_rows(xml_text: str) -> List[Dict[str, str]]:
    """
    Treasury XML is not guaranteed stable; this parser is defensive:
    - collects <row>...</row> if present
    - else tries to parse table-like nodes
    Returns list of dict fields (lowercased keys).
    """
    xml_text = xml_text.strip()
    # Some responses may include leading junk; attempt to find first '<'
    lt = xml_text.find("<")
    if lt > 0:
        xml_text = xml_text[lt:]

    root = ET.fromstring(xml_text)

    rows = []
    # Common pattern: <response><results><result> or <row>
    # We'll accept any element named "row" or "item" or "result"
    candidates = []
    for tag in ("row", "item", "result"):
        candidates.extend(root.findall(f".//{tag}"))

    if not candidates:
        # fallback: if the doc uses "entry"
        candidates = root.findall(".//entry")

    for e in candidates:
        d: Dict[str, str] = {}
        for child in list(e):
            key = child.tag.lower()
            val = (child.text or "").strip()
            d[key] = val
        if d:
            rows.append(d)

    return rows


def treasury_pick_date_and_10y(rows: List[Dict[str, str]], is_real: bool) -> Optional[Tuple[str, float]]:
    """
    Find the most recent row with a 10Y column.
    Returns (YYYY-MM-DD, value).
    """
    if not rows:
        return None

    # identify date key and 10y key candidates
    date_keys = [k for k in rows[0].keys() if "date" in k]
    # 10y columns vary. We'll scan keys that look like 10-year.
    def find_10y_key(keys: List[str]) -> Optional[str]:
        # preference: explicit 10year
        prefs = [
            "bc_10year",
            "bc_10yr",
            "ten_yr",
            "tenyear",
            "real_10year",
            "real_10yr",
            "t10y",
            "dgs10",
            "10year",
            "10yr",
        ]
        keys_l = [k.lower() for k in keys]
        for p in prefs:
            for k in keys_l:
                if p in k:
                    return k
        # otherwise regex
        for k in keys_l:
            if re.search(r"\b10\b", k) and ("year" in k or "yr" in k):
                return k
        return None

    # normalize each row: find date + 10y value
    best_dt = None
    best_val = None

    for r in rows:
        keys = list(r.keys())
        dk = None
        if date_keys:
            dk = date_keys[0]
        else:
            # search any key containing date
            for k in keys:
                if "date" in k.lower():
                    dk = k
                    break
        if not dk:
            continue

        tenk = find_10y_key(keys)
        if not tenk:
            continue

        dd = parse_date_any(r.get(dk, ""))
        if not dd:
            continue

        v = parse_float_safe(r.get(tenk, ""))
        if v is None:
            continue

        if best_dt is None or dd > best_dt:
            best_dt = dd
            best_val = v

    if best_dt is None or best_val is None:
        return None
    return best_dt, best_val


def fetch_treasury_10y(data_name: str, yyyymm: str) -> Tuple[Optional[Tuple[str, float]], str, str]:
    """
    Fetch 10Y from Treasury:
    Returns (result, source_url, notes)
    """
    # XML primary
    xml_url = TREASURY_XML_TMPL.format(data=data_name, yyyymm=yyyymm)
    txt, err = http_get_text(xml_url)
    if txt is not None:
        try:
            rows = parse_treasury_xml_rows(txt)
            is_real = (data_name == TREASURY_REAL_DATA)
            picked = treasury_pick_date_and_10y(rows, is_real=is_real)
            if picked:
                return picked, xml_url, "NA"
            else:
                return None, xml_url, "xml_parse_no_10y"
        except Exception:
            return None, xml_url, "xml_parse_fail_10y"

    # CSV fallback
    if data_name == TREASURY_NOMINAL_DATA:
        csv_url = TREASURY_CSV_TMPL.format(
            csv_name=TREASURY_NOMINAL_CSV_NAME, yyyymm=yyyymm, type_name=TREASURY_NOMINAL_TYPE
        )
    else:
        csv_url = TREASURY_CSV_TMPL.format(
            csv_name=TREASURY_REAL_CSV_NAME, yyyymm=yyyymm, type_name=TREASURY_REAL_TYPE
        )

    b, err2 = http_get_bytes(csv_url)
    if b is None:
        return None, csv_url, err2 or "csv_fail"
    try:
        text = b.decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, csv_url, "csv_empty"
        reader = csv.DictReader(lines)
        best_dd = None
        best_v = None
        for row in reader:
            dd = parse_date_any(row.get("Date") or row.get("date") or row.get("DATE") or "")
            if not dd:
                continue
            # common headers: "10 Yr" / "10 Yr" etc
            ten_candidates = ["10 Yr", "10 yr", "10YR", "10 YR", "10-year", "10 Year", "10-Year"]
            val = None
            for k in ten_candidates:
                if k in row:
                    val = row.get(k)
                    break
            if val is None:
                # brute search: first key containing "10" and "Yr/Year"
                for k in row.keys():
                    lk = k.lower()
                    if "10" in lk and ("yr" in lk or "year" in lk):
                        val = row.get(k)
                        break
            v = parse_float_safe(val)
            if v is None:
                continue
            if best_dd is None or dd > best_dd:
                best_dd = dd
                best_v = v
        if best_dd and best_v is not None:
            return (best_dd, best_v), csv_url, "WARN:treasury_csv_fallback"
        return None, csv_url, "csv_parse_no_10y"
    except Exception:
        return None, csv_url, "csv_parse_fail"


def nearest_match(
    target_dd: str, candidates: Dict[str, float], max_days: int
) -> Optional[Tuple[str, float, int]]:
    """
    Find nearest date in candidates to target_dd within max_days.
    candidates keys are YYYY-MM-DD
    Returns (dd, val, abs_days)
    """
    try:
        t = datetime.strptime(target_dd, "%Y-%m-%d").date()
    except Exception:
        return None
    best = None
    for dd, v in candidates.items():
        try:
            d = datetime.strptime(dd, "%Y-%m-%d").date()
        except Exception:
            continue
        delta = abs((t - d).days)
        if delta <= max_days:
            if best is None or delta < best[2] or (delta == best[2] and dd > best[0]):
                best = (dd, v, delta)
    return best


# -------------------------
# VIX / Stooq
# -------------------------
def fetch_cboe_vix_latest() -> Tuple[Optional[Tuple[str, float]], str, str]:
    b, err = http_get_bytes(CBOE_VIX_CSV)
    if b is None:
        return None, CBOE_VIX_CSV, f"cboe_{err}"
    try:
        text = b.decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, CBOE_VIX_CSV, "cboe_empty"
        # Find last data line (skip headers)
        # VIX_History.csv has columns: DATE, OPEN, HIGH, LOW, CLOSE
        last = None
        for ln in reversed(lines[1:]):
            if ln and not ln.startswith("DATE"):
                last = ln
                break
        if not last:
            return None, CBOE_VIX_CSV, "cboe_no_last_row"
        parts = [p.strip() for p in last.split(",")]
        if len(parts) < 5:
            return None, CBOE_VIX_CSV, "cboe_bad_row"
        dd = parse_date_any(parts[0])
        v = parse_float_safe(parts[4])
        if not dd or v is None:
            return None, CBOE_VIX_CSV, "cboe_bad_values"
        return (dd, v), CBOE_VIX_CSV, "NA"
    except Exception:
        return None, CBOE_VIX_CSV, "cboe_parse_fail"


def fetch_stooq_last_close(sym: str, lookback_days: int = 120) -> Tuple[Optional[Tuple[str, float]], str, str]:
    d2 = datetime.now(TZ_TAIPEI).date()
    d1 = d2 - timedelta(days=lookback_days)
    url = STOOQ_URL_TMPL.format(sym=sym, d1=d1.strftime("%Y%m%d"), d2=d2.strftime("%Y%m%d"))
    txt, err = http_get_text(url)
    if txt is None:
        return None, url, err or "stooq_fail"
    try:
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, url, "stooq_empty_csv"
        reader = csv.DictReader(lines)
        best_dd = None
        best_close = None
        for row in reader:
            dd = parse_date_any(row.get("Date", "") or row.get("date", ""))
            if not dd:
                continue
            close = parse_float_safe(row.get("Close", "") or row.get("close", ""))
            if close is None:
                continue
            if best_dd is None or dd > best_dd:
                best_dd = dd
                best_close = close
        if best_dd and best_close is not None:
            return (best_dd, best_close), url, "NA"
        return None, url, "stooq_no_close"
    except Exception:
        return None, url, "stooq_parse_fail"


# -------------------------
# OFR FSI
# -------------------------
def fetch_ofr_fsi_latest() -> Tuple[Optional[Tuple[str, float]], str, str]:
    txt, err = http_get_text(OFR_FSI_CSV)
    if txt is None:
        return None, OFR_FSI_CSV, err or "ofr_fail"
    try:
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, OFR_FSI_CSV, "ofr_empty"
        reader = csv.DictReader(lines)
        # Expect columns like "date","value" but be defensive
        best_dd = None
        best_v = None
        for row in reader:
            dd = parse_date_any(row.get("date") or row.get("Date") or row.get("DATE") or "")
            if not dd:
                continue
            # value column might be "fsi" or similar
            v = None
            for k in row.keys():
                if k.lower() in ("fsi", "value", "index", "ofr_fsi", "stress_index"):
                    v = row.get(k)
                    break
            if v is None:
                # fallback: first numeric-looking field
                for k in row.keys():
                    if k.lower().startswith("value"):
                        v = row.get(k)
                        break
            fv = parse_float_safe(v)
            if fv is None:
                continue
            if best_dd is None or dd > best_dd:
                best_dd = dd
                best_v = fv
        if best_dd and best_v is not None:
            return (best_dd, best_v), OFR_FSI_CSV, "NA"
        return None, OFR_FSI_CSV, "ofr_no_values"
    except Exception:
        return None, OFR_FSI_CSV, "ofr_parse_fail"


# -------------------------
# Credit axis (HYG/IEF) MA60 deviation
# -------------------------
def calc_ma_from_history(
    history: List[Dict[str, Any]],
    series_id: str,
    upto_date: str,
    window: int = MA_WINDOW,
) -> Tuple[Optional[float], int]:
    """
    Compute MA(window) using last N values <= upto_date (by data_date).
    Returns (ma, n_used)
    """
    upto = parse_date_any(upto_date)
    if not upto:
        return None, 0

    vals = []
    for r in history:
        if str(r.get("series_id", "")).strip() != series_id:
            continue
        dd = parse_date_any(str(r.get("data_date", "")))
        if not dd:
            continue
        if dd > upto:
            continue
        v = parse_float_safe(r.get("value"))
        if v is None:
            continue
        vals.append((dd, v))

    vals.sort(key=lambda x: x[0])
    if not vals:
        return None, 0

    tail = [v for _, v in vals[-window:]]
    if not tail:
        return None, 0
    ma = sum(tail) / len(tail)
    return ma, len(tail)


# -------------------------
# Regime classification
# -------------------------
def classify_regime(
    vix: Optional[float],
    be10y: Optional[float],
    credit_dev_pct: Optional[float],
    ofr_fsi: Optional[float],
    credit_points_used: int,
    used_be_carry_forward: Optional[str],
) -> Tuple[str, str, List[str]]:
    """
    Returns (regime_state, confidence, reasons[])
    """
    reasons: List[str] = []

    # Panic axis
    panic_level = "NA"
    if vix is None:
        panic_level = "NA"
        reasons.append("panic=NA(VIX=NA)")
    else:
        if vix >= VIX_HIGH_TH:
            panic_level = "HIGH"
        elif vix >= VIX_LOW_TH:
            panic_level = "MID"
        else:
            panic_level = "LOW"
        reasons.append(f"panic={panic_level}(VIX={vix:g})")

    # Inflation expectation axis
    infl_level = "NA"
    if be10y is None:
        infl_level = "NA"
        reasons.append("inflation_expect=NA(BE10Y=NA)")
    else:
        if be10y >= BE_HIGH_TH:
            infl_level = "HIGH"
        elif be10y < BE_LOW_TH:
            infl_level = "LOW"
        else:
            infl_level = "MID"
        if used_be_carry_forward:
            reasons.append(f"inflation_expect={infl_level}(BE10Y={be10y:g};carry_forward_from={used_be_carry_forward})")
        else:
            reasons.append(f"inflation_expect={infl_level}(BE10Y={be10y:g})")

    # Credit axis
    credit_level = "NA"
    if credit_dev_pct is None:
        credit_level = "NA"
        reasons.append("credit_dev=NA")
    else:
        if credit_dev_pct <= CREDIT_DEV_OFF_TH_PCT:
            credit_level = "RISK_OFF"
        elif credit_dev_pct >= CREDIT_DEV_ON_TH_PCT:
            credit_level = "RISK_ON"
        else:
            credit_level = "NEUTRAL"
        reasons.append(f"credit_dev={credit_level}({credit_dev_pct:+.2f}%)")
        reasons.append(f"credit_points_used={credit_points_used}")

    # OFR FSI (optional, but now we usually have it)
    if ofr_fsi is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")
        ofr_level = "NA"
    else:
        # Positive often indicates stress; negative indicates calmer
        if ofr_fsi > 0:
            ofr_level = "HIGH"
        elif ofr_fsi > -1:
            ofr_level = "MID"
        else:
            ofr_level = "LOW"
        reasons.append(f"OFR_FSI={ofr_level}({ofr_fsi:g})")

    # Regime state (keep output vocabulary stable)
    # Core: if VIX missing -> UNKNOWN
    if vix is None:
        regime = "UNKNOWN_INSUFFICIENT_DATA"
    else:
        # high panic dominates
        if panic_level == "HIGH":
            regime = "RISK_OFF"
        else:
            # credit risk-off with even moderate panic -> RISK_OFF
            if credit_level == "RISK_OFF" and panic_level in ("MID", "HIGH"):
                regime = "RISK_OFF"
            # benign panic + credit improving + inflation not high -> RISK_ON
            elif panic_level == "LOW" and credit_level == "RISK_ON" and infl_level in ("LOW", "MID", "NA"):
                regime = "RISK_ON"
            else:
                regime = "NEUTRAL_MIXED"

    # Base confidence
    # We treat: VIX is required; BE10Y and credit improve confidence; OFR optional.
    base_conf = "LOW"
    have_vix = vix is not None
    have_be = be10y is not None
    have_credit = credit_dev_pct is not None
    used_be_fallback = used_be_carry_forward is not None

    if have_vix and have_be and have_credit and not used_be_fallback:
        base_conf = "HIGH"
    elif have_vix and ((have_be and have_credit) or (have_be and not have_credit) or (have_credit and not have_be)):
        base_conf = "MEDIUM"
    elif have_vix:
        base_conf = "LOW"
    else:
        base_conf = "LOW"

    # Confidence caps (important for auditability)
    conf = base_conf
    if have_credit:
        if credit_points_used < CREDIT_MIN_POINTS_LOW_CAP:
            conf = "LOW"
            reasons.append("confidence_cap=LOW(credit_points_lt_20)")
        elif credit_points_used < CREDIT_MIN_POINTS_MED_CAP:
            if conf == "HIGH":
                conf = "MEDIUM"
                reasons.append("confidence_cap=MEDIUM(credit_points_lt_60)")
    else:
        # if credit unavailable at all, cap at LOW
        if conf != "LOW":
            conf = "LOW"
        reasons.append("confidence_cap=LOW(credit_unavailable)")

    # If BE used carry-forward, cap at MEDIUM
    if used_be_fallback and conf == "HIGH":
        conf = "MEDIUM"
        reasons.append("confidence_cap=MEDIUM(BE_carry_forward_used)")

    # If both BE and credit missing, keep LOW no matter what
    if (not have_be) and (not have_credit):
        conf = "LOW"
        reasons.append("confidence_cap=LOW(core_axes_missing(be+credit))")

    return regime, conf, reasons


# -------------------------
# Main build
# -------------------------
def build_rows() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (latest_rows, history_rows_updated)
    """
    as_of_ts = now_taipei_iso()
    today_iso = datetime.now(TZ_TAIPEI).date().strftime("%Y-%m-%d")

    history = normalize_and_dedup_history(load_history(HISTORY_JSON))

    latest_rows: List[Dict[str, Any]] = []
    new_history_rows: List[Dict[str, Any]] = []

    # Treasury: try this month then previous month if needed
    today = datetime.now(TZ_TAIPEI).date()
    yyyymm_list = [yyyymm_for(today), yyyymm_for((today.replace(day=1) - timedelta(days=1)))]

    # NOMINAL_10Y
    nominal = None
    nominal_url = "NA"
    nominal_notes = "NA"
    for yyyymm in yyyymm_list:
        picked, url, notes = fetch_treasury_10y(TREASURY_NOMINAL_DATA, yyyymm)
        nominal_url = url
        nominal_notes = notes
        if picked:
            nominal = picked
            break
    if nominal:
        dd, v = nominal
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "NOMINAL_10Y", "data_date": dd, "value": f"{v:g}", "source_url": nominal_url, "notes": nominal_notes}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "NOMINAL_10Y", "data_date": "NA", "value": "NA", "source_url": nominal_url, "notes": nominal_notes}
        )

    # REAL_10Y
    real = None
    real_url = "NA"
    real_notes = "NA"
    for yyyymm in yyyymm_list:
        picked, url, notes = fetch_treasury_10y(TREASURY_REAL_DATA, yyyymm)
        real_url = url
        real_notes = notes
        if picked:
            real = picked
            break
    if real:
        dd, v = real
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "REAL_10Y", "data_date": dd, "value": f"{v:g}", "source_url": real_url, "notes": real_notes}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "REAL_10Y", "data_date": "NA", "value": "NA", "source_url": real_url, "notes": real_notes}
        )

    # BE10Y_PROXY (nominal - real) pairing logic
    be10y = None
    be_dd = None
    be_notes = "NA"
    be_url = f"{nominal_url} + {real_url}"

    nominal_map = {}
    real_map = {}
    if nominal:
        nominal_map[nominal[0]] = nominal[1]
    if real:
        real_map[real[0]] = real[1]

    if nominal and real:
        nd, nv = nominal
        rd, rv = real
        if nd == rd:
            be_dd = nd
            be10y = nv - rv
        else:
            # try nearest-match within N days
            near = nearest_match(nd, real_map, TREASURY_PAIR_NEAREST_MAX_DAYS)
            if near:
                rd2, rv2, delta = near
                be_dd = nd
                be10y = nv - rv2
                be_notes = f"WARN:nearest_real_match(delta_days={delta},real_date={rd2})"
            else:
                be_notes = "date_mismatch_or_na"

    if be10y is not None and be_dd is not None:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "BE10Y_PROXY", "data_date": be_dd, "value": f"{be10y:g}", "source_url": be_url, "notes": be_notes}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "BE10Y_PROXY", "data_date": "NA", "value": "NA", "source_url": be_url, "notes": be_notes}
        )

    # VIX_PROXY
    vix = None
    vix_url = "NA"
    vix_notes = "NA"
    picked, url, notes = fetch_cboe_vix_latest()
    vix_url = url
    vix_notes = notes
    if picked:
        dd, vv = picked
        vix = vv
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "VIX_PROXY", "data_date": dd, "value": f"{vv:g}", "source_url": vix_url, "notes": vix_notes}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        # stooq fallback
        picked2, url2, notes2 = fetch_stooq_last_close(SYMBOL_VIX_FALLBACK, lookback_days=365)
        if picked2:
            dd, vv = picked2
            vix = vv
            latest_rows.append(
                {"as_of_ts": as_of_ts, "series_id": "VIX_PROXY", "data_date": dd, "value": f"{vv:g}", "source_url": url2, "notes": f"WARN:stooq_vix_fallback({notes2})"}
            )
            new_history_rows.append(dict(latest_rows[-1]))
        else:
            latest_rows.append(
                {"as_of_ts": as_of_ts, "series_id": "VIX_PROXY", "data_date": "NA", "value": "NA", "source_url": vix_url, "notes": f"{vix_notes};stooq_fail"}
            )

    # Stooq closes: HYG, IEF, TIP
    hyg_close = None
    ief_close = None
    tip_close = None

    for sid, sym in [("HYG_CLOSE", SYMBOL_HYG), ("IEF_CLOSE", SYMBOL_IEF), ("TIP_CLOSE", SYMBOL_TIP)]:
        picked, url, notes = fetch_stooq_last_close(sym, lookback_days=120)
        if picked:
            dd, vv = picked
            latest_rows.append(
                {"as_of_ts": as_of_ts, "series_id": sid, "data_date": dd, "value": f"{vv:g}", "source_url": url, "notes": notes}
            )
            new_history_rows.append(dict(latest_rows[-1]))
            if sid == "HYG_CLOSE":
                hyg_close = (dd, vv)
            elif sid == "IEF_CLOSE":
                ief_close = (dd, vv)
            else:
                tip_close = (dd, vv)
        else:
            latest_rows.append(
                {"as_of_ts": as_of_ts, "series_id": sid, "data_date": "NA", "value": "NA", "source_url": url, "notes": notes}
            )

    # Ratios
    hyg_ief_ratio = None
    tip_ief_ratio = None
    ratio_dd = None

    if hyg_close and ief_close and hyg_close[0] == ief_close[0] and ief_close[1] != 0:
        ratio_dd = hyg_close[0]
        hyg_ief_ratio = hyg_close[1] / ief_close[1]
    if tip_close and ief_close and tip_close[0] == ief_close[0] and ief_close[1] != 0:
        tip_ief_ratio = tip_close[1] / ief_close[1]

    if hyg_ief_ratio is not None and ratio_dd is not None:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "HYG_IEF_RATIO", "data_date": ratio_dd, "value": f"{hyg_ief_ratio:.16g}", "source_url": "https://stooq.com/", "notes": "NA"}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "HYG_IEF_RATIO", "data_date": "NA", "value": "NA", "source_url": "https://stooq.com/", "notes": "ratio_date_mismatch_or_na"}
        )

    if tip_ief_ratio is not None and ief_close and tip_close and tip_close[0] == ief_close[0]:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "TIP_IEF_RATIO", "data_date": tip_close[0], "value": f"{tip_ief_ratio:.16g}", "source_url": "https://stooq.com/", "notes": "NA"}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "TIP_IEF_RATIO", "data_date": "NA", "value": "NA", "source_url": "https://stooq.com/", "notes": "ratio_date_mismatch_or_na"}
        )

    # OFR FSI
    ofr_val = None
    ofr_picked, ofr_url, ofr_notes = fetch_ofr_fsi_latest()
    if ofr_picked:
        dd, vv = ofr_picked
        ofr_val = vv
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "OFR_FSI", "data_date": dd, "value": f"{vv:g}", "source_url": ofr_url, "notes": ofr_notes}
        )
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append(
            {"as_of_ts": as_of_ts, "series_id": "OFR_FSI", "data_date": "NA", "value": "NA", "source_url": ofr_url, "notes": ofr_notes}
        )

    # Merge history (dedup) before regime calcs so MA uses latest
    history2 = upsert_today(history, new_history_rows)

    # Credit MA60 deviation
    credit_dev_pct = None
    credit_points_used = 0
    if hyg_ief_ratio is not None and ratio_dd is not None:
        ma, n_used = calc_ma_from_history(history2, "HYG_IEF_RATIO", upto_date=ratio_dd, window=MA_WINDOW)
        credit_points_used = n_used
        if ma is not None and ma != 0:
            credit_dev_pct = (hyg_ief_ratio - ma) / ma * 100.0

    # Inflation expectation: prefer current-run BE10Y_PROXY; if missing, carry-forward from history (<= 7 days)
    used_be_carry_from = None
    be_for_regime = be10y

    if be_for_regime is None:
        # use today's date for window reference, but "carry-forward" is about most recent available before today
        found, why = get_recent_history_value(
            history2, "BE10Y_PROXY", max_age_days=BE_CARRY_FORWARD_MAX_AGE_DAYS, ref_date=today_iso
        )
        if found:
            dd, vv = found
            be_for_regime = vv
            used_be_carry_from = dd

    # Regime classification
    regime, conf, reasons = classify_regime(
        vix=vix,
        be10y=be_for_regime,
        credit_dev_pct=credit_dev_pct,
        ofr_fsi=ofr_val,
        credit_points_used=credit_points_used,
        used_be_carry_forward=used_be_carry_from,
    )

    # Append regime outputs (data_date uses "today" to make the log easy to read)
    latest_rows.append(
        {"as_of_ts": as_of_ts, "series_id": "REGIME_STATE", "data_date": today_iso, "value": regime, "source_url": "NA", "notes": "NA"}
    )
    latest_rows.append(
        {"as_of_ts": as_of_ts, "series_id": "REGIME_CONFIDENCE", "data_date": today_iso, "value": conf, "source_url": "NA", "notes": "NA"}
    )
    latest_rows.append(
        {"as_of_ts": as_of_ts, "series_id": "REGIME_REASONS", "data_date": today_iso, "value": json.dumps(reasons, ensure_ascii=False), "source_url": "NA", "notes": "NA"}
    )

    # Put regime rows into history too (dedup by date ensures one per day)
    new_history_rows.extend([dict(latest_rows[-3]), dict(latest_rows[-2]), dict(latest_rows[-1])])
    history3 = upsert_today(history2, new_history_rows)

    return latest_rows, history3


def write_manifest() -> None:
    """
    Keep manifest minimal. Your workflow can overwrite 'data_commit_sha' and pinned links later if you want.
    """
    m = {
        "script_version": SCRIPT_VERSION,
        "generated_at_utc": utc_now_iso(),
        "as_of_ts": now_taipei_iso(),
        "data_commit_sha": "PENDING",
        "pinned": {
            "latest_json": "PENDING",
            "latest_csv": "PENDING",
            "history_json": "PENDING",
            "manifest_json": "PENDING",
        },
    }
    write_json(MANIFEST_JSON, m)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()

    # allow override out dir
    global OUT_DIR, LATEST_JSON, LATEST_CSV, HISTORY_JSON, MANIFEST_JSON
    OUT_DIR = args.out_dir
    LATEST_JSON = os.path.join(OUT_DIR, "latest.json")
    LATEST_CSV = os.path.join(OUT_DIR, "latest.csv")
    HISTORY_JSON = os.path.join(OUT_DIR, "history.json")
    MANIFEST_JSON = os.path.join(OUT_DIR, "manifest.json")

    latest_rows, history_rows = build_rows()

    write_json(LATEST_JSON, latest_rows)
    write_latest_csv(LATEST_CSV, latest_rows)
    write_json(HISTORY_JSON, history_rows)
    write_manifest()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())