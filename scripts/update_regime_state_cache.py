#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_regime_state_cache.py  (v3.3.4)

Supported modes:
- default (Generate): fetch -> latest.json/latest.csv/history.json ; manifest.json written with PENDING (or keep existing pinned)
- --validate-data: validate existing data files (latest/history/manifest) and exit
- --validate-manifest: validate manifest.json only and exit
- --write-manifest --data-commit-sha <SHA> [--repo <owner/repo>] :
    write manifest.json where pinned URLs point to the given data commit SHA (raw GitHub URLs)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

import requests
from xml.etree import ElementTree as ET

# -------------------------
# Defaults (can be overridden by CLI)
# -------------------------
OUT_DIR = "regime_state_cache"
LATEST_JSON = os.path.join(OUT_DIR, "latest.json")
LATEST_CSV = os.path.join(OUT_DIR, "latest.csv")
HISTORY_JSON = os.path.join(OUT_DIR, "history.json")
MANIFEST_JSON = os.path.join(OUT_DIR, "manifest.json")

SCRIPT_VERSION = "regime_state_cache_v3_3_4"
MAX_HISTORY_ROWS = 5000

DEFAULT_REPO = "Joseph-Chou911/fred-cache"
DEFAULT_BRANCH = "main"

# Stooq symbols
SYMBOL_HYG = "hyg.us"
SYMBOL_IEF = "ief.us"
SYMBOL_TIP = "tip.us"
SYMBOL_VIX_FALLBACK = "^vix"
STOOQ_URL_TMPL = "https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"

# CBOE VIX
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

# OFR FSI
OFR_FSI_CSV = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"

# US Treasury XML/CSV
TREASURY_XML_TMPL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data={data}&field_tdr_date_value_month={yyyymm}"
)
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

# Regime thresholds
VIX_LOW_TH = 20.0
VIX_HIGH_TH = 30.0
BE_LOW_TH = 1.5
BE_HIGH_TH = 3.0
CREDIT_DEV_ON_TH_PCT = +1.0
CREDIT_DEV_OFF_TH_PCT = -1.0

# MA requirements / confidence caps
MA_WINDOW = 60
CREDIT_MIN_POINTS_LOW_CAP = 20
CREDIT_MIN_POINTS_MED_CAP = 60

# carry-forward window for BE10Y_PROXY when missing
BE_CARRY_FORWARD_MAX_AGE_DAYS = 7

# HTTP
DEFAULT_TIMEOUT = 20
MAX_RETRIES = 3
BACKOFFS = [2, 4, 8]

TZ_TAIPEI = timezone(timedelta(hours=8))


# -------------------------
# Utilities
# -------------------------
def now_taipei_iso() -> str:
    return datetime.now(TZ_TAIPEI).isoformat(timespec="microseconds")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def yyyymm_for(dt: date) -> str:
    return f"{dt.year:04d}{dt.month:02d}"


def parse_date_any(s: str) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.upper() == "NA":
        return None

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ].*$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{yy:04d}-{mm:02d}-{dd:02d}"

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


def http_get_text(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[Optional[str], Optional[str]]:
    headers = {"User-Agent": "fred-cache-bot/1.0 (requests)", "Accept": "*/*"}
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
    headers = {"User-Agent": "fred-cache-bot/1.0 (requests)", "Accept": "*/*"}
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


def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        data = load_json_file(path)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def normalize_and_dedup_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def asof_key(r: Dict[str, Any]) -> str:
        return str(r.get("as_of_ts", "")).strip()

    for r in rows:
        sid = str(r.get("series_id", "")).strip()
        d0 = r.get("data_date", "NA")
        d = parse_date_any(str(d0)) or "NA"
        r2 = dict(r)
        r2["series_id"] = sid
        r2["data_date"] = d

        if not sid or d == "NA":
            k = (sid or "__EMPTY__", f"NA::{asof_key(r2)}")
        else:
            k = (sid, d)

        if k not in best or asof_key(r2) >= asof_key(best[k]):
            best[k] = r2

    out = list(best.values())
    out.sort(
        key=lambda r: (
            str(r.get("series_id", "")),
            str(r.get("data_date", "")),
            str(r.get("as_of_ts", "")),
        )
    )
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
    return normalize_and_dedup_history(history + new_rows)


def get_recent_history_value(
    history: List[Dict[str, Any]],
    series_id: str,
    max_age_days: int,
    ref_date: str,
) -> Tuple[Optional[Tuple[str, float]], Optional[str]]:
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
        if 0 <= age <= max_age_days:
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
    xml_text = xml_text.strip()
    lt = xml_text.find("<")
    if lt > 0:
        xml_text = xml_text[lt:]

    root = ET.fromstring(xml_text)

    rows = []
    candidates = []
    for tag in ("row", "item", "result"):
        candidates.extend(root.findall(f".//{tag}"))
    if not candidates:
        candidates = root.findall(".//entry")

    for e in candidates:
        d: Dict[str, str] = {}
        for child in list(e):
            d[child.tag.lower()] = (child.text or "").strip()
        if d:
            rows.append(d)
    return rows


def treasury_pick_date_and_10y(rows: List[Dict[str, str]]) -> Optional[Tuple[str, float]]:
    if not rows:
        return None

    date_keys = [k for k in rows[0].keys() if "date" in k]

    def find_10y_key(keys: List[str]) -> Optional[str]:
        prefs = [
            "bc_10year",
            "bc_10yr",
            "ten_yr",
            "tenyear",
            "real_10year",
            "real_10yr",
            "t10y",
            "10year",
            "10yr",
        ]
        keys_l = [k.lower() for k in keys]
        for p in prefs:
            for k in keys_l:
                if p in k:
                    return k
        for k in keys_l:
            if re.search(r"\b10\b", k) and ("year" in k or "yr" in k):
                return k
        return None

    best_dt = None
    best_val = None

    for r in rows:
        keys = list(r.keys())
        dk = date_keys[0] if date_keys else next((k for k in keys if "date" in k.lower()), None)
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
            best_dt, best_val = dd, v

    if best_dt is None or best_val is None:
        return None
    return best_dt, best_val


def fetch_treasury_10y(data_name: str, yyyymm: str) -> Tuple[Optional[Tuple[str, float]], str, str]:
    xml_url = TREASURY_XML_TMPL.format(data=data_name, yyyymm=yyyymm)
    txt, err = http_get_text(xml_url)
    if txt is not None:
        try:
            rows = parse_treasury_xml_rows(txt)
            picked = treasury_pick_date_and_10y(rows)
            if picked:
                return picked, xml_url, "NA"
            return None, xml_url, "xml_parse_no_10y"
        except Exception:
            return None, xml_url, "xml_parse_fail_10y"

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
            val = None
            for k in row.keys():
                lk = k.lower()
                if "10" in lk and ("yr" in lk or "year" in lk):
                    val = row.get(k)
                    break
            v = parse_float_safe(val)
            if v is None:
                continue
            if best_dd is None or dd > best_dd:
                best_dd, best_v = dd, v
        if best_dd and best_v is not None:
            return (best_dd, best_v), csv_url, "WARN:treasury_csv_fallback"
        return None, csv_url, "csv_parse_no_10y"
    except Exception:
        return None, csv_url, "csv_parse_fail"


# -------------------------
# Market/OFR fetchers
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
                best_dd, best_close = dd, close
        if best_dd and best_close is not None:
            return (best_dd, best_close), url, "NA"
        return None, url, "stooq_no_close"
    except Exception:
        return None, url, "stooq_parse_fail"


def fetch_ofr_fsi_latest() -> Tuple[Optional[Tuple[str, float]], str, str]:
    txt, err = http_get_text(OFR_FSI_CSV)
    if txt is None:
        return None, OFR_FSI_CSV, err or "ofr_fail"
    try:
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, OFR_FSI_CSV, "ofr_empty"
        reader = csv.DictReader(lines)
        best_dd = None
        best_v = None
        for row in reader:
            dd = parse_date_any(row.get("date") or row.get("Date") or row.get("DATE") or "")
            if not dd:
                continue
            v = None
            for k in row.keys():
                lk = k.lower()
                if lk in ("fsi", "value", "index", "ofr_fsi", "stress_index"):
                    v = row.get(k)
                    break
            if v is None:
                for k in row.keys():
                    if k.lower().startswith("value"):
                        v = row.get(k)
                        break
            fv = parse_float_safe(v)
            if fv is None:
                continue
            if best_dd is None or dd > best_dd:
                best_dd, best_v = dd, fv
        if best_dd and best_v is not None:
            return (best_dd, best_v), OFR_FSI_CSV, "NA"
        return None, OFR_FSI_CSV, "ofr_no_values"
    except Exception:
        return None, OFR_FSI_CSV, "ofr_parse_fail"


# -------------------------
# Credit MA
# -------------------------
def calc_ma_from_history(
    history: List[Dict[str, Any]],
    series_id: str,
    upto_date: str,
    window: int = MA_WINDOW,
) -> Tuple[Optional[float], int]:
    upto = parse_date_any(upto_date)
    if not upto:
        return None, 0
    vals = []
    for r in history:
        if str(r.get("series_id", "")).strip() != series_id:
            continue
        dd = parse_date_any(str(r.get("data_date", "")))
        if not dd or dd > upto:
            continue
        v = parse_float_safe(r.get("value"))
        if v is None:
            continue
        vals.append((dd, v))
    vals.sort(key=lambda x: x[0])
    if not vals:
        return None, 0
    tail = [v for _, v in vals[-window:]]
    return (sum(tail) / len(tail), len(tail)) if tail else (None, 0)


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
    reasons: List[str] = []

    if vix is None:
        reasons.append("panic=NA(VIX=NA)")
        panic_level = "NA"
    else:
        if vix >= VIX_HIGH_TH:
            panic_level = "HIGH"
        elif vix >= VIX_LOW_TH:
            panic_level = "MID"
        else:
            panic_level = "LOW"
        reasons.append(f"panic={panic_level}(VIX={vix:g})")

    if be10y is None:
        reasons.append("inflation_expect=NA(BE10Y=NA)")
        infl_level = "NA"
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

    if credit_dev_pct is None:
        reasons.append("credit_dev=NA")
        credit_level = "NA"
    else:
        if credit_dev_pct <= CREDIT_DEV_OFF_TH_PCT:
            credit_level = "RISK_OFF"
        elif credit_dev_pct >= CREDIT_DEV_ON_TH_PCT:
            credit_level = "RISK_ON"
        else:
            credit_level = "NEUTRAL"
        reasons.append(f"credit_dev={credit_level}({credit_dev_pct:+.2f}%)")
        reasons.append(f"credit_points_used={credit_points_used}")

    if ofr_fsi is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")
    else:
        ofr_level = "HIGH" if ofr_fsi > 0 else ("MID" if ofr_fsi > -1 else "LOW")
        reasons.append(f"OFR_FSI={ofr_level}({ofr_fsi:g})")

    if vix is None:
        regime = "UNKNOWN_INSUFFICIENT_DATA"
    else:
        if panic_level == "HIGH":
            regime = "RISK_OFF"
        elif credit_level == "RISK_OFF" and panic_level in ("MID", "HIGH"):
            regime = "RISK_OFF"
        elif panic_level == "LOW" and credit_level == "RISK_ON" and infl_level in ("LOW", "MID", "NA"):
            regime = "RISK_ON"
        else:
            regime = "NEUTRAL_MIXED"

    have_vix = vix is not None
    have_be = be10y is not None
    have_credit = credit_dev_pct is not None
    used_be_fallback = used_be_carry_forward is not None

    if have_vix and have_be and have_credit and not used_be_fallback:
        base_conf = "HIGH"
    elif have_vix and (have_be or have_credit):
        base_conf = "MEDIUM"
    else:
        base_conf = "LOW"

    conf = base_conf
    if have_credit:
        if credit_points_used < CREDIT_MIN_POINTS_LOW_CAP:
            conf = "LOW"
            reasons.append("confidence_cap=LOW(credit_points_lt_20)")
        elif credit_points_used < CREDIT_MIN_POINTS_MED_CAP and conf == "HIGH":
            conf = "MEDIUM"
            reasons.append("confidence_cap=MEDIUM(credit_points_lt_60)")
    else:
        conf = "LOW"
        reasons.append("confidence_cap=LOW(credit_unavailable)")

    if used_be_fallback and conf == "HIGH":
        conf = "MEDIUM"
        reasons.append("confidence_cap=MEDIUM(BE_carry_forward_used)")

    if (not have_be) and (not have_credit):
        conf = "LOW"
        reasons.append("confidence_cap=LOW(core_axes_missing(be+credit))")

    return regime, conf, reasons


# -------------------------
# Build rows
# -------------------------
def build_rows() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    as_of_ts = now_taipei_iso()
    today_iso = datetime.now(TZ_TAIPEI).date().strftime("%Y-%m-%d")

    history = normalize_and_dedup_history(load_history(HISTORY_JSON))
    latest_rows: List[Dict[str, Any]] = []
    new_history_rows: List[Dict[str, Any]] = []

    today = datetime.now(TZ_TAIPEI).date()
    yyyymm_list = [yyyymm_for(today), yyyymm_for((today.replace(day=1) - timedelta(days=1)))]

    # NOMINAL_10Y
    nominal = None
    nominal_url = "NA"
    nominal_notes = "NA"
    for yyyymm in yyyymm_list:
        picked, url, notes = fetch_treasury_10y(TREASURY_NOMINAL_DATA, yyyymm)
        nominal_url, nominal_notes = url, notes
        if picked:
            nominal = picked
            break
    if nominal:
        dd, v = nominal
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "NOMINAL_10Y", "data_date": dd, "value": f"{v:g}", "source_url": nominal_url, "notes": nominal_notes})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "NOMINAL_10Y", "data_date": "NA", "value": "NA", "source_url": nominal_url, "notes": nominal_notes})

    # REAL_10Y
    real = None
    real_url = "NA"
    real_notes = "NA"
    for yyyymm in yyyymm_list:
        picked, url, notes = fetch_treasury_10y(TREASURY_REAL_DATA, yyyymm)
        real_url, real_notes = url, notes
        if picked:
            real = picked
            break
    if real:
        dd, v = real
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "REAL_10Y", "data_date": dd, "value": f"{v:g}", "source_url": real_url, "notes": real_notes})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "REAL_10Y", "data_date": "NA", "value": "NA", "source_url": real_url, "notes": real_notes})

    # BE10Y_PROXY (simple pairing)
    be10y = None
    be_dd = None
    be_notes = "NA"
    be_url = f"{nominal_url} + {real_url}"

    if nominal and real:
        nd, nv = nominal
        rd, rv = real
        if nd == rd:
            be_dd, be10y = nd, (nv - rv)
        else:
            be_notes = "date_mismatch_or_na"

    if be10y is not None and be_dd is not None:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "BE10Y_PROXY", "data_date": be_dd, "value": f"{be10y:g}", "source_url": be_url, "notes": be_notes})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "BE10Y_PROXY", "data_date": "NA", "value": "NA", "source_url": be_url, "notes": be_notes})

    # VIX
    vix = None
    picked, url, notes = fetch_cboe_vix_latest()
    if picked:
        dd, vv = picked
        vix = vv
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "VIX_PROXY", "data_date": dd, "value": f"{vv:g}", "source_url": url, "notes": notes})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        picked2, url2, notes2 = fetch_stooq_last_close(SYMBOL_VIX_FALLBACK, lookback_days=365)
        if picked2:
            dd, vv = picked2
            vix = vv
            latest_rows.append({"as_of_ts": as_of_ts, "series_id": "VIX_PROXY", "data_date": dd, "value": f"{vv:g}", "source_url": url2, "notes": f"WARN:stooq_vix_fallback({notes2})"})
            new_history_rows.append(dict(latest_rows[-1]))
        else:
            latest_rows.append({"as_of_ts": as_of_ts, "series_id": "VIX_PROXY", "data_date": "NA", "value": "NA", "source_url": url, "notes": f"{notes};stooq_fail"})

    # Stooq closes: HYG, IEF, TIP
    hyg_close = None
    ief_close = None
    tip_close = None

    for sid, sym in [("HYG_CLOSE", SYMBOL_HYG), ("IEF_CLOSE", SYMBOL_IEF), ("TIP_CLOSE", SYMBOL_TIP)]:
        picked, url, notes = fetch_stooq_last_close(sym, lookback_days=120)
        if picked:
            dd, vv = picked
            latest_rows.append({"as_of_ts": as_of_ts, "series_id": sid, "data_date": dd, "value": f"{vv:g}", "source_url": url, "notes": notes})
            new_history_rows.append(dict(latest_rows[-1]))
            if sid == "HYG_CLOSE":
                hyg_close = (dd, vv)
            elif sid == "IEF_CLOSE":
                ief_close = (dd, vv)
            else:
                tip_close = (dd, vv)
        else:
            latest_rows.append({"as_of_ts": as_of_ts, "series_id": sid, "data_date": "NA", "value": "NA", "source_url": url, "notes": notes})

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
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "HYG_IEF_RATIO", "data_date": ratio_dd, "value": f"{hyg_ief_ratio:.16g}", "source_url": "https://stooq.com/", "notes": "NA"})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "HYG_IEF_RATIO", "data_date": "NA", "value": "NA", "source_url": "https://stooq.com/", "notes": "ratio_date_mismatch_or_na"})

    if tip_ief_ratio is not None and ief_close and tip_close and tip_close[0] == ief_close[0]:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "TIP_IEF_RATIO", "data_date": tip_close[0], "value": f"{tip_ief_ratio:.16g}", "source_url": "https://stooq.com/", "notes": "NA"})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "TIP_IEF_RATIO", "data_date": "NA", "value": "NA", "source_url": "https://stooq.com/", "notes": "ratio_date_mismatch_or_na"})

    # OFR FSI
    ofr_val = None
    ofr_picked, ofr_url, ofr_notes = fetch_ofr_fsi_latest()
    if ofr_picked:
        dd, vv = ofr_picked
        ofr_val = vv
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "OFR_FSI", "data_date": dd, "value": f"{vv:g}", "source_url": ofr_url, "notes": ofr_notes})
        new_history_rows.append(dict(latest_rows[-1]))
    else:
        latest_rows.append({"as_of_ts": as_of_ts, "series_id": "OFR_FSI", "data_date": "NA", "value": "NA", "source_url": ofr_url, "notes": ofr_notes})

    # Merge history before regime calcs
    history2 = upsert_today(history, new_history_rows)

    # Credit MA deviation
    credit_dev_pct = None
    credit_points_used = 0
    if hyg_ief_ratio is not None and ratio_dd is not None:
        ma, n_used = calc_ma_from_history(history2, "HYG_IEF_RATIO", upto_date=ratio_dd, window=MA_WINDOW)
        credit_points_used = n_used
        if ma is not None and ma != 0:
            credit_dev_pct = (hyg_ief_ratio - ma) / ma * 100.0

    # BE carry-forward if missing
    used_be_carry_from = None
    be_for_regime = be10y
    if be_for_regime is None:
        found, _ = get_recent_history_value(
            history2,
            "BE10Y_PROXY",
            BE_CARRY_FORWARD_MAX_AGE_DAYS,
            datetime.now(TZ_TAIPEI).date().strftime("%Y-%m-%d"),
        )
        if found:
            dd, vv = found
            be_for_regime = vv
            used_be_carry_from = dd

    regime, conf, reasons = classify_regime(
        vix=vix,
        be10y=be_for_regime,
        credit_dev_pct=credit_dev_pct,
        ofr_fsi=ofr_val,
        credit_points_used=credit_points_used,
        used_be_carry_forward=used_be_carry_from,
    )

    latest_rows.append({"as_of_ts": as_of_ts, "series_id": "REGIME_STATE", "data_date": today_iso, "value": regime, "source_url": "NA", "notes": "NA"})
    latest_rows.append({"as_of_ts": as_of_ts, "series_id": "REGIME_CONFIDENCE", "data_date": today_iso, "value": conf, "source_url": "NA", "notes": "NA"})
    latest_rows.append({"as_of_ts": as_of_ts, "series_id": "REGIME_REASONS", "data_date": today_iso, "value": json.dumps(reasons, ensure_ascii=False), "source_url": "NA", "notes": "NA"})

    new_history_rows.extend([dict(latest_rows[-3]), dict(latest_rows[-2]), dict(latest_rows[-1])])
    history3 = upsert_today(history2, new_history_rows)

    return latest_rows, history3


# -------------------------
# Manifest writing (pinned -> DATA_SHA)
# -------------------------
def _raw_url(repo: str, sha: str, path: str) -> str:
    # Pin to specific commit SHA
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"


def write_manifest_pinned(out_dir: str, repo: str, data_sha: str) -> None:
    rel_latest_json = f"{out_dir}/latest.json"
    rel_latest_csv = f"{out_dir}/latest.csv"
    rel_history_json = f"{out_dir}/history.json"
    rel_manifest_json = f"{out_dir}/manifest.json"

    m = {
        "script_version": SCRIPT_VERSION,
        "generated_at_utc": utc_now_iso(),
        "as_of_ts": now_taipei_iso(),
        "data_commit_sha": data_sha,
        "pinned": {
            "latest_json": _raw_url(repo, data_sha, rel_latest_json),
            "latest_csv": _raw_url(repo, data_sha, rel_latest_csv),
            "history_json": _raw_url(repo, data_sha, rel_history_json),
            "manifest_json": _raw_url(repo, data_sha, rel_manifest_json),
        },
    }
    write_json(os.path.join(out_dir, "manifest.json"), m)


# -------------------------
# Validate mode
# -------------------------
def _is_iso_date_or_na(x: Any) -> bool:
    s = str(x).strip()
    if s.upper() == "NA":
        return True
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", s))


def _validate_rows_schema(rows: Any, name: str) -> List[str]:
    errs: List[str] = []
    if not isinstance(rows, list):
        return [f"{name}: not a list"]
    required = {"as_of_ts", "series_id", "data_date", "value", "source_url", "notes"}
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            errs.append(f"{name}[{i}]: not an object")
            continue
        missing = required - set(r.keys())
        if missing:
            errs.append(f"{name}[{i}]: missing_keys={sorted(missing)}")
        if "data_date" in r and not _is_iso_date_or_na(r["data_date"]):
            errs.append(f"{name}[{i}]: bad_data_date={r.get('data_date')}")
    return errs


def _is_hex_sha(s: str) -> bool:
    s = (s or "").strip()
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", s))


def validate_manifest_only(out_dir: str, repo_hint: Optional[str] = None) -> int:
    manifest_path = os.path.join(out_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"missing_file: {manifest_path}", file=sys.stderr)
        return 1

    try:
        m = load_json_file(manifest_path)
    except Exception as e:
        print(f"manifest.json parse error: {type(e).__name__}", file=sys.stderr)
        return 1

    if not isinstance(m, dict):
        print("manifest.json: not an object", file=sys.stderr)
        return 1

    errs: List[str] = []

    data_sha = str(m.get("data_commit_sha", "")).strip()
    if data_sha.upper() in ("", "NA"):
        errs.append("manifest.json: missing data_commit_sha")
    elif data_sha.upper() == "PENDING":
        errs.append("manifest.json: data_commit_sha is PENDING")
    elif not _is_hex_sha(data_sha):
        errs.append(f"manifest.json: invalid data_commit_sha={data_sha}")

    pinned = m.get("pinned")
    if not isinstance(pinned, dict):
        errs.append("manifest.json: pinned is missing or not an object")
        pinned = {}

    need_keys = ["latest_json", "latest_csv", "history_json", "manifest_json"]
    for k in need_keys:
        v = str(pinned.get(k, "")).strip()
        if not v:
            errs.append(f"manifest.json: pinned.{k} missing")
        elif v.upper() == "PENDING":
            errs.append(f"manifest.json: pinned.{k} is PENDING")

    # If we have a proper SHA, verify pinned URLs contain it (strong sanity check)
    if _is_hex_sha(data_sha):
        for k in need_keys:
            v = str(pinned.get(k, "")).strip()
            if v and v.upper() != "PENDING" and data_sha not in v:
                errs.append(f"manifest.json: pinned.{k} does not include data_commit_sha")

    # If repo_hint is provided, verify pinned URLs contain repo
    if repo_hint:
        for k in need_keys:
            v = str(pinned.get(k, "")).strip()
            if v and v.upper() != "PENDING" and repo_hint not in v:
                errs.append(f"manifest.json: pinned.{k} does not include repo={repo_hint}")

    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1

    print("OK: validate-manifest passed")
    return 0


def validate_data_files(out_dir: str) -> int:
    latest_path = os.path.join(out_dir, "latest.json")
    history_path = os.path.join(out_dir, "history.json")
    manifest_path = os.path.join(out_dir, "manifest.json")

    errs: List[str] = []
    for p in (latest_path, history_path, manifest_path):
        if not os.path.exists(p):
            errs.append(f"missing_file: {p}")

    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1

    try:
        latest = load_json_file(latest_path)
    except Exception as e:
        print(f"latest.json parse error: {type(e).__name__}", file=sys.stderr)
        return 1

    try:
        history = load_json_file(history_path)
    except Exception as e:
        print(f"history.json parse error: {type(e).__name__}", file=sys.stderr)
        return 1

    # schema checks
    errs.extend(_validate_rows_schema(latest, "latest"))
    errs.extend(_validate_rows_schema(history, "history"))

    # history duplicates: (series_id, data_date) unique when data_date != NA
    if isinstance(history, list):
        seen = set()
        for r in history:
            if not isinstance(r, dict):
                continue
            sid = str(r.get("series_id", "")).strip()
            dd = str(r.get("data_date", "")).strip()
            if not sid or dd.upper() == "NA":
                continue
            key = (sid, dd)
            if key in seen:
                errs.append(f"history duplicate: series_id={sid} data_date={dd}")
            else:
                seen.add(key)

    # latest should contain regime fields
    if isinstance(latest, list):
        sids = {str(r.get("series_id", "")).strip() for r in latest if isinstance(r, dict)}
        for needed in ("REGIME_STATE", "REGIME_CONFIDENCE", "REGIME_REASONS"):
            if needed not in sids:
                errs.append(f"latest missing series_id: {needed}")

    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1

    print("OK: validate-data passed")
    return 0


# -------------------------
# Main
# -------------------------
def main() -> int:
    global OUT_DIR, LATEST_JSON, LATEST_CSV, HISTORY_JSON, MANIFEST_JSON

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--validate-data", action="store_true", help="Validate latest/history/manifest files and exit.")
    parser.add_argument("--validate-manifest", action="store_true", help="Validate manifest.json only and exit.")
    parser.add_argument("--write-manifest", action="store_true", help="Write manifest pinned to --data-commit-sha and exit.")
    parser.add_argument("--data-commit-sha", default=None, help="Commit SHA that contains the data files (for pinned manifest).")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo in owner/name form for pinned raw URLs.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch name (kept for compatibility; not used when pinning by SHA).")
    args = parser.parse_args()

    OUT_DIR = args.out_dir
    LATEST_JSON = os.path.join(OUT_DIR, "latest.json")
    LATEST_CSV = os.path.join(OUT_DIR, "latest.csv")
    HISTORY_JSON = os.path.join(OUT_DIR, "history.json")
    MANIFEST_JSON = os.path.join(OUT_DIR, "manifest.json")

    if args.validate_manifest:
        return validate_manifest_only(OUT_DIR, repo_hint=args.repo)

    if args.validate_data:
        return validate_data_files(OUT_DIR)

    if args.write_manifest:
        if not args.data_commit_sha or str(args.data_commit_sha).strip().upper() in ("", "NA", "PENDING"):
            print("error: --write-manifest requires --data-commit-sha <SHA>", file=sys.stderr)
            return 2
        write_manifest_pinned(OUT_DIR, args.repo, args.data_commit_sha.strip())
        print("OK: write-manifest done")
        return 0

    latest_rows, history_rows = build_rows()
    write_json(LATEST_JSON, latest_rows)
    write_latest_csv(LATEST_CSV, latest_rows)
    write_json(HISTORY_JSON, history_rows)

    # Generate mode: keep existing pinned manifest if present; else create placeholder (PENDING)
    if os.path.exists(MANIFEST_JSON):
        try:
            m = load_json_file(MANIFEST_JSON)
            if isinstance(m, dict) and "pinned" in m and "data_commit_sha" in m and str(m.get("data_commit_sha", "")).strip():
                pass
            else:
                raise ValueError("manifest missing pinned")
        except Exception:
            write_json(
                MANIFEST_JSON,
                {
                    "script_version": SCRIPT_VERSION,
                    "generated_at_utc": utc_now_iso(),
                    "as_of_ts": now_taipei_iso(),
                    "data_commit_sha": "PENDING",
                    "pinned": {"latest_json": "PENDING", "latest_csv": "PENDING", "history_json": "PENDING", "manifest_json": "PENDING"},
                },
            )
    else:
        write_json(
            MANIFEST_JSON,
            {
                "script_version": SCRIPT_VERSION,
                "generated_at_utc": utc_now_iso(),
                "as_of_ts": now_taipei_iso(),
                "data_commit_sha": "PENDING",
                "pinned": {"latest_json": "PENDING", "latest_csv": "PENDING", "history_json": "PENDING", "manifest_json": "PENDING"},
            },
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())