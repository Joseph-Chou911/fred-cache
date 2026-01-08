#!/usr/bin/env python3
# update_regime_state_cache.py
#
# regime_state_cache_v3_3
# - OFR_FSI: use explicit CSV endpoint first: https://www.financialresearch.gov/financial-stress-index/data/fsi.csv
# - VIX: CBOE CSV primary, Stooq fallback
# - Treasury: XML endpoints (nominal + real) and compute BE10Y_PROXY when same-date
# - Regime state: outputs REGIME_STATE + REGIME_CONFIDENCE + REGIME_REASONS
# - Credit axis: HYG/IEF uses MA60 deviation (>=60 history points), else credit unavailable and confidence capped LOW
# - Date normalization to YYYY-MM-DD to prevent history duplication

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date as dt_date
from typing import Dict, List, Optional, Tuple

import requests

# -------------------------
# Outputs
# -------------------------
DEFAULT_OUT_DIR = "regime_state_cache"
LATEST_JSON_NAME = "latest.json"
LATEST_CSV_NAME = "latest.csv"
HISTORY_JSON_NAME = "history.json"
MANIFEST_JSON_NAME = "manifest.json"

SCRIPT_VERSION = "regime_state_cache_v3_3"
MAX_HISTORY_ROWS = 5000

# -------------------------
# Time helpers
# -------------------------
def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def as_of_ts_local_iso() -> str:
    # Runner TZ is set in workflow; produces explicit offset like +08:00
    return datetime.now().astimezone().isoformat()

# -------------------------
# Date normalization
# -------------------------
_DATE_PATTERNS = [
    # YYYY-MM-DD
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    # YYYY-MM-DDTHH:MM:SS (we take date part)
    (None, re.compile(r"^\d{4}-\d{2}-\d{2}T")),
    # MM/DD/YYYY
    ("%m/%d/%Y", re.compile(r"^\d{2}/\d{2}/\d{4}$")),
    # M/D/YYYY (loose)
    ("%m/%d/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
]

def normalize_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    ss = str(s).strip()
    if ss == "" or ss.upper() == "NA":
        return None

    # ISO datetime -> date
    if "T" in ss and re.match(r"^\d{4}-\d{2}-\d{2}T", ss):
        return ss[:10]

    # try patterns
    for fmt, pat in _DATE_PATTERNS:
        if pat.match(ss):
            if fmt is None:
                return ss[:10]
            try:
                d = datetime.strptime(ss, fmt).date()
                return d.strftime("%Y-%m-%d")
            except Exception:
                pass

    # last resort: extract yyyy-mm-dd
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ss)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    return None

# -------------------------
# HTTP helpers
# -------------------------
def http_get(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[str], int]:
    headers = {
        "User-Agent": f"{SCRIPT_VERSION}/1.0",
        "Accept": "text/csv,application/xml,application/json,text/plain,*/*",
    }
    try:
        r = requests.get(url, timeout=timeout, headers=headers)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}", r.status_code
        # Some endpoints may return utf-8 with BOM etc.
        return r.text, None, r.status_code
    except requests.Timeout:
        return None, "timeout", 0
    except Exception as e:
        return None, f"exception:{type(e).__name__}", 0

def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

# -------------------------
# Stooq daily close
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 120) -> Tuple[Optional[str], Optional[float], str, str]:
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err, _ = http_get(url)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    raw_date = (last.get("Date") or "").strip()
    dd = normalize_date(raw_date)
    close = safe_float(last.get("Close"))
    if dd is None:
        return None, close, "date_parse_fail", url
    if close is None:
        return dd, None, "na_or_parse_fail", url
    return dd, close, "NA", url

# -------------------------
# CBOE VIX (CSV primary)
# -------------------------
def cboe_vix_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err, _ = http_get(url)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    # CBOE uses "DATE" or "Date" typically
    raw_date = (last.get("DATE") or last.get("Date") or last.get("date") or "").strip()
    dd = normalize_date(raw_date)
    # Close col name varies; try common keys
    v = None
    for k in ["CLOSE", "Close", "close"]:
        if k in last:
            v = safe_float(last.get(k))
            break
    if v is None:
        # sometimes "VIX Close" etc.
        for k, val in last.items():
            if not k:
                continue
            if "close" in k.lower():
                vv = safe_float(val)
                if vv is not None:
                    v = vv
                    break

    if dd is None:
        return None, v, "date_parse_fail", url
    if v is None:
        return dd, None, "na_or_parse_fail", url
    return dd, v, "NA", url

def vix_latest_with_fallback() -> Tuple[Optional[str], Optional[float], str, str]:
    d, v, n, u = cboe_vix_latest()
    if d and v is not None:
        return d, v, n, u
    # fallback to Stooq "vix"
    d2, v2, n2, u2 = stooq_daily_close("vix", 60)
    if d2 and v2 is not None:
        return d2, v2, f"fallback_stooq({n};{n2})", u2
    return None, None, f"cboe_{n};stooq_{n2}", u

# -------------------------
# Treasury XML (nominal + real)
# -------------------------
def treasury_xml_url(data_key: str, yyyymm: str) -> str:
    # data_key: daily_treasury_yield_curve or daily_treasury_real_yield_curve
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data={data_key}&field_tdr_date_value_month={yyyymm}"
    )

def yyyymm_candidates(n_months: int = 2) -> List[str]:
    now = datetime.now().astimezone()
    out: List[str] = []
    y, m = now.year, now.month
    for i in range(n_months):
        mm = m - i
        yy = y
        if mm <= 0:
            mm += 12
            yy -= 1
        out.append(f"{yy:04d}{mm:02d}")
    return out

def parse_latest_10y_from_treasury_xml(xml_text: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Returns (data_date_yyyy_mm_dd, value_10y, notes)
    Uses simple regex parsing:
      - find last <d:NEW_DATE>...</d:NEW_DATE> (or <NEW_DATE>)
      - within same entry, find 10Y field:
          - nominal: <d:BC_10YEAR>...</d:BC_10YEAR>
          - real:    <d:TC_10YEAR>...</d:TC_10YEAR>
    If unknown, attempt both.
    """
    # find entries: each <m:properties> ... </m:properties>
    props = re.findall(r"<m:properties>.*?</m:properties>", xml_text, flags=re.DOTALL | re.IGNORECASE)
    if not props:
        # sometimes namespaces differ; try without m:
        props = re.findall(r"<properties>.*?</properties>", xml_text, flags=re.DOTALL | re.IGNORECASE)
    if not props:
        return None, None, "xml_no_properties"

    last = props[-1]

    def find_tag(text: str, tag: str) -> Optional[str]:
        # handle d:TAG or TAG
        m = re.search(rf"<(?:d:)?{tag}[^>]*>(.*?)</(?:d:)?{tag}>", text, flags=re.DOTALL | re.IGNORECASE)
        if not m:
            return None
        return (m.group(1) or "").strip()

    raw_date = find_tag(last, "NEW_DATE")
    dd = normalize_date(raw_date)

    # nominal / real tag candidates
    val_txt = find_tag(last, "BC_10YEAR")  # nominal
    if val_txt is None:
        val_txt = find_tag(last, "TC_10YEAR")  # real

    # additional fallback: any 10year-like tag
    if val_txt is None:
        m2 = re.search(r"<(?:d:)?([A-Z_]*10YEAR)[^>]*>(.*?)</(?:d:)?\1>", last, flags=re.DOTALL | re.IGNORECASE)
        if m2:
            val_txt = (m2.group(2) or "").strip()

    v = safe_float(val_txt)
    if dd is None:
        return None, v, "xml_date_parse_fail"
    if v is None:
        return dd, None, "xml_parse_fail_10y"
    return dd, v, "NA"

def treasury_10y_latest(data_key: str) -> Tuple[Optional[str], Optional[float], str, str]:
    last_err = "NA"
    last_url = "NA"
    for yyyymm in yyyymm_candidates(2):
        url = treasury_xml_url(data_key, yyyymm)
        text, err, _ = http_get(url)
        if err:
            last_err, last_url = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(text)
        last_err, last_url = notes, url
        if d and v is not None:
            return d, v, "NA", url
    return None, None, last_err, last_url

# -------------------------
# OFR FSI (explicit CSV endpoint)
# -------------------------
def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    Primary: explicit CSV endpoint
      https://www.financialresearch.gov/financial-stress-index/data/fsi.csv

    If it fails, we degrade cleanly (NO_PUBLIC_CSV_LINK / HTTP / timeout).
    We intentionally do NOT chase HTML parsing reliability anymore.
    """
    url = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"
    text, err, _ = http_get(url)
    if err:
        # Degrade explicitly; caller treats NA as normal degradation.
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]

    # Date column variations
    raw_date = (
        (last.get("Date") or last.get("DATE") or last.get("date") or last.get("Observation Date") or "").strip()
    )
    dd = normalize_date(raw_date)

    # Find value column:
    val = None
    preferred_keys: List[str] = []
    for k in last.keys():
        if not k:
            continue
        lk = k.lower()
        if "fsi" in lk or ("stress" in lk and "index" in lk) or lk == "index":
            preferred_keys.append(k)

    for k in preferred_keys:
        vv = safe_float(last.get(k))
        if vv is not None:
            val = vv
            break

    if val is None:
        # fallback: first numeric field excluding date-ish columns
        for k, v0 in last.items():
            if not k:
                continue
            lk = k.lower()
            if "date" in lk:
                continue
            vv = safe_float(v0)
            if vv is not None:
                val = vv
                break

    if dd is None:
        return None, val, "date_parse_fail", url
    if val is None:
        return dd, None, "na_or_parse_fail", url
    return dd, val, "NA", url

# -------------------------
# Data model
# -------------------------
@dataclass
class Point:
    as_of_ts: str
    series_id: str
    data_date: str
    value: str
    source_url: str
    notes: str

def load_json_list(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_latest_csv(path: str, points: List[Point]) -> None:
    fields = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in points:
            w.writerow({
                "as_of_ts": p.as_of_ts,
                "series_id": p.series_id,
                "data_date": p.data_date,
                "value": p.value,
                "source_url": p.source_url,
                "notes": p.notes,
            })

def upsert_history(hist: List[dict], p: Point) -> List[dict]:
    # unique by (series_id, data_date) AFTER normalization
    if p.data_date == "NA":
        return hist
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("series_id") == p.series_id and hist[i].get("data_date") == p.data_date:
            hist[i] = p.__dict__
            return hist
    hist.append(p.__dict__)
    if len(hist) > MAX_HISTORY_ROWS:
        hist = hist[-MAX_HISTORY_ROWS:]
    return hist

def normalize_history_inplace(hist: List[dict]) -> List[dict]:
    """
    Normalize all history data_date to YYYY-MM-DD and deduplicate by (series_id, data_date),
    keeping the last occurrence.
    """
    m: Dict[Tuple[str, str], dict] = {}
    for r in hist:
        sid = str(r.get("series_id") or "").strip()
        raw_dd = r.get("data_date")
        dd = normalize_date(raw_dd)
        if not sid or not dd:
            continue
        rr = dict(r)
        rr["series_id"] = sid
        rr["data_date"] = dd
        m[(sid, dd)] = rr  # keep last
    # stable-ish ordering by (data_date, series_id)
    out = list(m.values())
    out.sort(key=lambda x: (x.get("data_date", ""), x.get("series_id", "")))
    if len(out) > MAX_HISTORY_ROWS:
        out = out[-MAX_HISTORY_ROWS:]
    return out

# -------------------------
# Validation
# -------------------------
def validate_data(out_dir: str) -> None:
    latest_json = os.path.join(out_dir, LATEST_JSON_NAME)
    latest_csv = os.path.join(out_dir, LATEST_CSV_NAME)
    history_json = os.path.join(out_dir, HISTORY_JSON_NAME)

    if not os.path.exists(latest_json):
        raise SystemExit("VALIDATE_DATA_FAIL: missing latest.json")
    if not os.path.exists(latest_csv):
        raise SystemExit("VALIDATE_DATA_FAIL: missing latest.csv")
    if not os.path.exists(history_json):
        raise SystemExit("VALIDATE_DATA_FAIL: missing history.json")

    latest = load_json_list(latest_json)
    if not latest:
        raise SystemExit("VALIDATE_DATA_FAIL: latest.json empty or not list")

    required = {"as_of_ts", "series_id", "data_date", "value", "source_url", "notes"}
    for i, r in enumerate(latest[:100]):  # sample first 100
        if not isinstance(r, dict):
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} not dict")
        missing = required - set(r.keys())
        if missing:
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} missing keys {sorted(list(missing))}")

    hist = load_json_list(history_json)
    if hist is None:
        raise SystemExit("VALIDATE_DATA_FAIL: history.json not loadable")

def validate_manifest(out_dir: str) -> None:
    manifest_path = os.path.join(out_dir, MANIFEST_JSON_NAME)
    if not os.path.exists(manifest_path):
        raise SystemExit("VALIDATE_MANIFEST_FAIL: missing manifest.json")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
    except Exception:
        raise SystemExit("VALIDATE_MANIFEST_FAIL: manifest.json not json")

    if not isinstance(m, dict):
        raise SystemExit("VALIDATE_MANIFEST_FAIL: manifest root not dict")

    if "data_commit_sha" not in m or not m["data_commit_sha"]:
        raise SystemExit("VALIDATE_MANIFEST_FAIL: missing data_commit_sha")

    pinned = (m.get("pinned") or {})
    for k in ["latest_json", "latest_csv", "history_json", "manifest_json"]:
        if k not in pinned or not pinned[k]:
            raise SystemExit(f"VALIDATE_MANIFEST_FAIL: pinned missing {k}")

# -------------------------
# Regime classification
# -------------------------
def _get_latest_value(points: List[Point], series_id: str) -> Optional[float]:
    for p in points:
        if p.series_id == series_id:
            return safe_float(p.value)
    return None

def _get_latest_date(points: List[Point], series_id: str) -> Optional[str]:
    for p in points:
        if p.series_id == series_id:
            dd = normalize_date(p.data_date)
            return dd
    return None

def _collect_history_series(hist: List[dict], series_id: str) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for r in hist:
        if (r.get("series_id") or "") != series_id:
            continue
        dd = normalize_date(r.get("data_date"))
        v = safe_float(r.get("value"))
        if dd and v is not None:
            out.append((dd, v))
    # unique by date keep last, then sort
    m: Dict[str, float] = {}
    for dd, v in out:
        m[dd] = v
    out2 = list(m.items())
    out2.sort(key=lambda x: x[0])
    return out2

def _ma(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / float(len(values))

def compute_regime_state(points: List[Point], hist: List[dict]) -> Tuple[str, str, List[str]]:
    """
    Returns (regime_state, confidence, reasons[])
    OFR_FSI may be NA and is treated as normal degradation (should not lower confidence).
    """
    reasons: List[str] = []

    vix = _get_latest_value(points, "VIX_PROXY")
    be10 = _get_latest_value(points, "BE10Y_PROXY")

    # ---- panic axis (VIX) ----
    panic: Optional[str] = None
    if vix is None:
        reasons.append("panic=NA(VIX=NA)")
    else:
        # simple buckets
        if vix >= 35:
            panic = "HIGH"
        elif vix >= 20:
            panic = "MED"
        else:
            panic = "LOW"
        reasons.append(f"panic={panic}(VIX={vix})")

    # ---- inflation expectation axis (BE10Y) ----
    infl: Optional[str] = None
    if be10 is None:
        reasons.append("inflation_expect=NA(BE10Y=NA)")
    else:
        if be10 >= 3.0:
            infl = "HIGH"
        elif be10 >= 1.5:
            infl = "MID"
        else:
            infl = "LOW"
        reasons.append(f"inflation_expect={infl}(BE10Y={be10})")

    # ---- credit axis via HYG/IEF MA60 deviation ----
    credit: Optional[str] = None
    dev_pct: Optional[float] = None

    # prefer the ratio we already compute
    ratio_now = _get_latest_value(points, "HYG_IEF_RATIO")
    if ratio_now is None:
        reasons.append("credit=NA(HYG_IEF_RATIO=NA)")
    else:
        series = _collect_history_series(hist, "HYG_IEF_RATIO")
        if len(series) < 60:
            reasons.append(f"credit_dev_unavailable(history_lt_60({len(series)}))")
        else:
            last60 = [v for (_, v) in series[-60:]]
            ma60 = _ma(last60)
            if ma60 is None or ma60 == 0:
                reasons.append("credit_dev_unavailable(ma60=NA)")
            else:
                dev_pct = (ratio_now / ma60 - 1.0) * 100.0
                # threshold: +/-1% from MA60 (Scheme A)
                if dev_pct <= -1.0:
                    credit = "TIGHT"
                elif dev_pct >= 1.0:
                    credit = "EASY"
                else:
                    credit = "NEUTRAL"
                reasons.append(f"credit={credit}(dev_pct={dev_pct:.2f}%)")

    # ---- OFR FSI is optional ----
    ofr = _get_latest_value(points, "OFR_FSI")
    if ofr is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")
    else:
        reasons.append(f"OFR_FSI=OK({ofr})")

    # ---- decide regime ----
    # If core missing, return UNKNOWN
    core_missing: List[str] = []
    if vix is None:
        core_missing.append("VIX_PROXY")
    if be10 is None:
        core_missing.append("BE10Y_PROXY")

    if core_missing:
        return "UNKNOWN_INSUFFICIENT_DATA", "LOW", [f"core_missing={','.join(core_missing)}"] + reasons

    # Base mapping (keep it simple and auditable)
    # Crisis if panic HIGH and (infl LOW or credit TIGHT)
    if panic == "HIGH" and ((infl == "LOW") or (credit == "TIGHT")):
        regime = "CRISIS_RISK"
    # Overheating if infl HIGH and panic LOW and credit EASY/NEUTRAL
    elif infl == "HIGH" and panic == "LOW" and (credit in (None, "EASY", "NEUTRAL")):
        regime = "OVERHEATING"
    # Stagflation-ish if infl HIGH and panic MED/HIGH
    elif infl == "HIGH" and panic in ("MED", "HIGH"):
        regime = "STAGFLATION_RISK"
    # Defensive if panic MED and (credit TIGHT or infl LOW)
    elif panic == "MED" and (credit == "TIGHT" or infl == "LOW"):
        regime = "DEFENSIVE"
    else:
        regime = "NEUTRAL_MIXED"

    # ---- confidence ----
    # Start at MEDIUM if cores present; upgrade to HIGH only if credit is available.
    confidence = "MEDIUM"
    if credit is None:
        # cap LOW if credit unavailable (per your rule)
        confidence = "LOW"
        reasons.append("confidence_cap=LOW(credit_unavailable)")
    else:
        # if credit available and both axes are non-extreme -> MED/HIGH
        confidence = "HIGH" if (panic in ("LOW", "MED") and infl in ("LOW", "MID", "HIGH")) else "MEDIUM"

    return regime, confidence, reasons

# -------------------------
# Main
# -------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--write-manifest", action="store_true")
    ap.add_argument("--data-commit-sha", default="")
    ap.add_argument("--validate-data", action="store_true")
    ap.add_argument("--validate-manifest", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir
    ensure_dir(out_dir)

    latest_json_path = os.path.join(out_dir, LATEST_JSON_NAME)
    latest_csv_path = os.path.join(out_dir, LATEST_CSV_NAME)
    history_path = os.path.join(out_dir, HISTORY_JSON_NAME)
    manifest_path = os.path.join(out_dir, MANIFEST_JSON_NAME)

    if args.validate_data:
        validate_data(out_dir)
        return

    if args.validate_manifest:
        validate_manifest(out_dir)
        return

    if args.write_manifest:
        if not args.data_commit_sha:
            raise SystemExit("Missing --data-commit-sha for --write-manifest")
        data_sha = args.data_commit_sha
        manifest = {
            "script_version": SCRIPT_VERSION,
            "generated_at_utc": utc_iso(),
            "as_of_ts": as_of_ts_local_iso(),
            "data_commit_sha": data_sha,
            "pinned": {
                "latest_json": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/{data_sha}/{out_dir}/{LATEST_JSON_NAME}",
                "latest_csv": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/{data_sha}/{out_dir}/{LATEST_CSV_NAME}",
                "history_json": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/{data_sha}/{out_dir}/{HISTORY_JSON_NAME}",
                # IMPORTANT: manifest is usually read from main branch
                "manifest_json": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/refs/heads/main/{out_dir}/{MANIFEST_JSON_NAME}",
            },
        }
        write_json(manifest_path, manifest)
        return

    # -------- generate data files --------
    as_of = as_of_ts_local_iso()
    today_local = datetime.now().astimezone().date().strftime("%Y-%m-%d")

    # Load + normalize existing history (prevents duplication across date formats)
    hist_raw = load_json_list(history_path)
    hist = normalize_history_inplace(hist_raw)

    points: List[Point] = []

    def add(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str) -> None:
        dd = normalize_date(data_date) if data_date else None
        if dd is None or value is None:
            points.append(Point(as_of, series_id, dd or "NA", "NA", source_url, notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, dd, f"{value}", source_url, notes))

    # Treasury 10Y nominal & real
    nom_d, nom_v, nom_n, nom_u = treasury_10y_latest("daily_treasury_yield_curve")
    real_d, real_v, real_n, real_u = treasury_10y_latest("daily_treasury_real_yield_curve")
    add("NOMINAL_10Y", nom_d, nom_v, nom_u, nom_n)
    add("REAL_10Y", real_d, real_v, real_u, real_n)

    # Breakeven proxy only if same date
    be10 = None
    be_d = None
    be_notes = "NA"
    if nom_v is not None and real_v is not None and nom_d and real_d:
        nd = normalize_date(nom_d)
        rd = normalize_date(real_d)
        if nd and rd and nd == rd:
            be10 = nom_v - real_v
            be_d = nd
        else:
            be_notes = "date_mismatch_or_na"
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_d, be10, f"{nom_u} + {real_u}".strip(), be_notes)

    # VIX (CBOE primary, Stooq fallback)
    vix_d, vix_v, vix_n, vix_u = vix_latest_with_fallback()
    add("VIX_PROXY", vix_d, vix_v, vix_u, vix_n)

    # Stooq ETFs: HYG/IEF/TIP
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 120)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 120)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 120)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    # Ratios (only if same date)
    hyg_ief_ratio = None
    ratio_date = None
    ratio_notes = "NA"
    if hyg_c is not None and ief_c is not None and hyg_d and ief_d:
        hd = normalize_date(hyg_d)
        idd = normalize_date(ief_d)
        if hd and idd and hd == idd:
            hyg_ief_ratio = hyg_c / ief_c
            ratio_date = hd
        else:
            ratio_notes = "date_mismatch_or_na"
    else:
        ratio_notes = "date_mismatch_or_na"
    add("HYG_IEF_RATIO", ratio_date, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_date = None
    tip_ratio_notes = "NA"
    if tip_c is not None and ief_c is not None and tip_d and ief_d:
        td = normalize_date(tip_d)
        idd = normalize_date(ief_d)
        if td and idd and td == idd:
            tip_ief_ratio = tip_c / ief_c
            tip_ratio_date = td
        else:
            tip_ratio_notes = "date_mismatch_or_na"
    else:
        tip_ratio_notes = "date_mismatch_or_na"
    add("TIP_IEF_RATIO", tip_ratio_date, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # OFR FSI (explicit CSV)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest()
    # keep as NA if failed; state machine treats as normal degradation
    if ofr_d and ofr_v is not None:
        add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)
    else:
        add("OFR_FSI", None, None, "https://www.financialresearch.gov/financial-stress-index/", "NO_PUBLIC_CSV_LINK (ignored; normal degradation)")

    # Upsert current points into history (exclude NA dates)
    for p in points:
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # Compute regime and append meta points
    regime_state, confidence, reasons = compute_regime_state(points, hist)

    # data_date for regime outputs uses "today local"
    points.append(Point(as_of, "REGIME_STATE", today_local, regime_state, "NA", "NA"))
    points.append(Point(as_of, "REGIME_CONFIDENCE", today_local, confidence, "NA", "NA"))
    points.append(Point(as_of, "REGIME_REASONS", today_local, json.dumps(reasons, ensure_ascii=False), "NA", "NA"))

    # Write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()