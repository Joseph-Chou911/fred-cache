#!/usr/bin/env python3
# update_regime_state_cache.py
#
# v4 minimal+auditable:
# - Normalize dates to 'YYYY-MM-DD' to avoid history duplicates
# - HYG/IEF credit state uses MA60 deviation (±1%) when history>=60
# - If history<60: credit state degrades (no absolute-value fallback unless you add it)
# - OFR_FSI kept but treated as OPTIONAL (NA is normal degradation; does not block)
# - Treasury NOMINAL_10Y / REAL_10Y via Treasury XML endpoints (more reliable than CSV month URLs)
# - VIX via CBOE CSV; Stooq as fallback
#
# Output files:
#   latest.json, latest.csv, history.json, manifest.json

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any

import requests

# -------------------------
# Paths / Outputs
# -------------------------
DEFAULT_OUT_DIR = "regime_state_cache"
LATEST_JSON_NAME = "latest.json"
LATEST_CSV_NAME = "latest.csv"
HISTORY_JSON_NAME = "history.json"
MANIFEST_JSON_NAME = "manifest.json"

SCRIPT_VERSION = "regime_state_cache_v4"
MAX_HISTORY_ROWS = 5000

# -------------------------
# Time helpers
# -------------------------
def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def as_of_ts_local_iso() -> str:
    # Runner TZ is set in workflow; this produces explicit offset like +08:00
    return datetime.now().astimezone().isoformat()

# -------------------------
# Date normalization (avoid history duplicates)
# -------------------------
def normalize_date(s: Optional[str]) -> Optional[str]:
    """
    Normalize date strings to 'YYYY-MM-DD' when possible.
    - Treasury XML often yields 'YYYY-MM-DDT00:00:00' -> 'YYYY-MM-DD'
    - Stooq uses 'YYYY-MM-DD'
    - Keep other formats as-is if we can't safely normalize.
    """
    if s is None:
        return None
    t = str(s).strip()
    if t == "" or t.upper() == "NA":
        return None

    # ISO with time
    if "T" in t and len(t) >= 10:
        head = t.split("T")[0]
        if len(head) == 10 and head[4] == "-" and head[7] == "-":
            return head
        return head

    # Already YYYY-MM-DD
    if len(t) == 10 and t[4] == "-" and t[7] == "-":
        return t

    # Common US format like 01/02/2026 -> convert to YYYY-MM-DD if unambiguous
    # Treasury CSV used to return MM/DD/YYYY; keep support just in case.
    if re.match(r"^\d{2}/\d{2}/\d{4}$", t):
        mm, dd, yy = t.split("/")
        try:
            dt = datetime(int(yy), int(mm), int(dd))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return t

    return t

# -------------------------
# HTTP helpers
# -------------------------
def http_get(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": f"{SCRIPT_VERSION}/1.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.text, None
    except requests.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, f"exception:{type(e).__name__}"

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
# Stooq (ETF prices / fallback VIX)
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 30) -> Tuple[Optional[str], Optional[float], str, str]:
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err = http_get(url)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    date = normalize_date((last.get("Date") or "").strip()) or None
    close = safe_float(last.get("Close"))
    if close is None or date is None:
        return date, None, "na_or_parse_fail", url

    return date, close, "NA", url

# -------------------------
# VIX (CBOE official CSV, fallback to Stooq)
# -------------------------
def vix_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    Try CBOE VIX CSV (public). If blocked/changed, fallback to Stooq 'vix'.
    """
    cboe_url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get(cboe_url)
    if not err and text:
        # CSV columns typically: DATE, OPEN, HIGH, LOW, CLOSE
        reader = csv.DictReader(text.splitlines())
        rows = [r for r in reader if r]
        if rows:
            last = rows[-1]
            # Try common keys
            date = normalize_date((last.get("DATE") or last.get("Date") or "").strip()) or None
            close = safe_float(last.get("CLOSE") or last.get("Close"))
            if date and close is not None:
                return date, close, "NA", cboe_url
            return date, None, "cboe_parse_fail", cboe_url
        return None, None, "cboe_empty_csv", cboe_url

    # Fallback: Stooq
    d, c, n, u = stooq_daily_close("vix", 30)
    if d and c is not None:
        return d, c, f"fallback_stooq({n})" if n != "NA" else "fallback_stooq", u
    # return combined reason
    reason = f"cboe_{err};stooq_{n}" if err else f"cboe_ok_but_empty;stooq_{n}"
    return None, None, reason, cboe_url

# -------------------------
# Treasury XML endpoints (more reliable than monthly CSV)
# -------------------------
def treasury_xml_url(kind: str, yyyymm: str) -> str:
    """
    Treasury offers an XML endpoint for daily yield curve series by month.
    """
    if kind == "nominal":
        data = "daily_treasury_yield_curve"
    elif kind == "real":
        data = "daily_treasury_real_yield_curve"
    else:
        raise ValueError("unknown kind")
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data={data}&field_tdr_date_value_month={yyyymm}"
    )

def yyyymm_candidates(n_months: int = 3) -> List[str]:
    now = datetime.now().astimezone()
    out = []
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
    Parse Treasury XML and return latest (date, 10Y, notes).
    We do a best-effort extraction:
      - Find all <d:NEW_DATE>YYYY-MM-DDT00:00:00</d:NEW_DATE>
      - For each record, find the 'BC_10YEAR' field value
    """
    # Dates can appear multiple times; we try to extract record blocks.
    # This is intentionally simple (no extra dependencies).
    # Approach: split by "<entry>" and parse inside.
    entries = xml_text.split("<entry")
    if len(entries) <= 1:
        return None, None, "xml_no_entries"

    last_date = None
    last_val = None

    for chunk in entries[1:]:
        # Date
        mdate = re.search(r"<d:NEW_DATE[^>]*>([^<]+)</d:NEW_DATE>", chunk)
        if not mdate:
            continue
        dt_raw = mdate.group(1).strip()
        dt = normalize_date(dt_raw)  # 'YYYY-MM-DD'
        if not dt:
            continue

        # 10Y field: for nominal it's usually BC_10YEAR; for real it's also BC_10YEAR in that dataset.
        m10 = re.search(r"<d:BC_10YEAR[^>]*>([^<]+)</d:BC_10YEAR>", chunk)
        if not m10:
            continue
        v = safe_float(m10.group(1).strip())
        if v is None:
            continue

        # Keep the latest by date (lexicographic works for YYYY-MM-DD)
        if last_date is None or dt > last_date:
            last_date = dt
            last_val = v

    if last_date is None or last_val is None:
        return None, None, "xml_parse_fail_10y"

    return last_date, last_val, "NA"

# -------------------------
# OFR FSI (keep field, but do not pursue reliable scraping)
# -------------------------
def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    Keep OFR_FSI field, but treat NA as normal degradation.
    In v4 we do not attempt aggressive scraping; we only return NA with clear note.
    """
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    return None, None, "NO_PUBLIC_CSV_LINK", page_url

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

def upsert_history(hist: List[dict], p: Point) -> List[dict]:
    # unique by (series_id, data_date)
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("series_id") == p.series_id and hist[i].get("data_date") == p.data_date:
            hist[i] = p.__dict__
            return hist
    hist.append(p.__dict__)
    if len(hist) > MAX_HISTORY_ROWS:
        hist = hist[-MAX_HISTORY_ROWS:]
    return hist

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
    for i, r in enumerate(latest[:80]):  # sample
        if not isinstance(r, dict):
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} not dict")
        missing = required - set(r.keys())
        if missing:
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} missing keys {sorted(list(missing))}")

    # history basic check
    _ = load_json_list(history_json)

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
# MA helpers (for HYG/IEF MA60 deviation)
# -------------------------
def extract_series_history_values(history_rows: List[Dict[str, Any]], series_id: str) -> List[Tuple[str, float]]:
    """
    Return list of (data_date, value_float) sorted by data_date ascending, distinct by date.
    NA/parse-fail excluded.
    If multiple rows for same date exist, keep the first encountered after sorting stability:
      - we normalize date first then keep earliest occurrence for that date.
    """
    tmp: List[Tuple[str, float]] = []
    for r in (history_rows or []):
        if not isinstance(r, dict):
            continue
        if r.get("series_id") != series_id:
            continue
        dd = normalize_date(r.get("data_date"))
        vv = safe_float(r.get("value"))
        if not dd or vv is None:
            continue
        tmp.append((dd, vv))

    # Sort by date; keep first per date
    tmp.sort(key=lambda x: x[0])
    out: List[Tuple[str, float]] = []
    seen = set()
    for dd, vv in tmp:
        if dd in seen:
            continue
        seen.add(dd)
        out.append((dd, vv))
    return out

def sma_last_n(values: List[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    w = values[-n:]
    return sum(w) / float(n)

# -------------------------
# Regime classification (MA60 deviation for HYG/IEF)
# -------------------------
def classify_regime_state(latest_rows: List[Dict[str, Any]], history_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Outputs:
      - regime_state: str
      - confidence: str  ('HIGH'|'MEDIUM'|'LOW')
      - reasons: List[str]

    Core used series (must exist in latest with numeric values):
      - VIX_PROXY
      - BE10Y_PROXY
      - REAL_10Y
      - HYG_IEF_RATIO  (credit state uses MA60 deviation when history>=60)

    OFR_FSI:
      - optional; NA is normal degradation and does not penalize confidence.
    """
    by_id: Dict[str, Dict[str, Any]] = {r.get("series_id"): r for r in (latest_rows or []) if isinstance(r, dict)}

    def get_val(series_id: str) -> Optional[float]:
        r = by_id.get(series_id) or {}
        return safe_float(r.get("value"))

    def get_date(series_id: str) -> Optional[str]:
        r = by_id.get(series_id) or {}
        return normalize_date(r.get("data_date"))

    def get_notes(series_id: str) -> str:
        r = by_id.get(series_id) or {}
        return str(r.get("notes") or "NA")

    reasons: List[str] = []

    vix = get_val("VIX_PROXY")
    vix_date = get_date("VIX_PROXY")

    hygief = get_val("HYG_IEF_RATIO")
    hygief_date = get_date("HYG_IEF_RATIO")

    be10 = get_val("BE10Y_PROXY")
    be10_date = get_date("BE10Y_PROXY")

    real10 = get_val("REAL_10Y")
    real10_date = get_date("REAL_10Y")

    ofr = get_val("OFR_FSI")
    ofr_date = get_date("OFR_FSI")

    # --- core availability check ---
    core_missing = []
    if vix is None: core_missing.append("VIX_PROXY")
    if hygief is None: core_missing.append("HYG_IEF_RATIO")
    if be10 is None: core_missing.append("BE10Y_PROXY")
    if real10 is None: core_missing.append("REAL_10Y")

    if core_missing:
        reasons.append(f"core_missing={','.join(core_missing)}")
        if ofr is None:
            reasons.append("OFR_FSI=NA (optional; normal degradation)")
        return {
            "regime_state": "UNKNOWN_INSUFFICIENT_DATA",
            "confidence": "LOW",
            "reasons": reasons,
        }

    # OFR optional (never blocks)
    if ofr is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")
    else:
        reasons.append(f"OFR_FSI available: {ofr} (date={ofr_date or 'NA'})")

    # Surface non-NA notes (audit)
    for sid in ["VIX_PROXY", "HYG_IEF_RATIO", "BE10Y_PROXY", "REAL_10Y", "OFR_FSI"]:
        n = get_notes(sid)
        if n and n != "NA":
            reasons.append(f"{sid}.notes={n}")

    # --- Panic axis (VIX): consistent with your dashboard thresholds
    if vix >= 20:
        panic = "HIGH"
    elif vix >= 16:
        panic = "MID"
    else:
        panic = "LOW"

    # --- Credit axis (HYG/IEF): MA60 deviation ±1%
    # dev = ratio_t/MA60 - 1
    # risk-on: dev >= +0.01; neutral: (-0.01, +0.01); risk-off: dev <= -0.01
    credit = "NEUTRAL"
    dev = None
    ma60 = None

    hist_series = extract_series_history_values(history_rows, "HYG_IEF_RATIO")
    if len(hist_series) >= 60:
        vals = [v for _, v in hist_series]
        ma60 = sma_last_n(vals, 60)
        if ma60 and ma60 != 0.0:
            dev = (hygief / ma60) - 1.0
            if dev >= 0.01:
                credit = "RISK_ON"
            elif dev <= -0.01:
                credit = "RISK_OFF"
            else:
                credit = "NEUTRAL"
            reasons.append(f"HYG/IEF MA60 deviation: ratio={hygief:.6f}, MA60={ma60:.6f}, dev={dev*100:.2f}% -> {credit}")
        else:
            reasons.append("HYG/IEF history present but MA60 invalid (zero/None) -> credit=NEUTRAL")
    else:
        reasons.append(f"HYG/IEF history<{60} -> MA60/dev disabled -> credit=NEUTRAL (degraded)")

    # --- Inflation / deflation axis (Breakeven proxy)
    if be10 >= 2.5:
        infl = "HIGH_INFL"
    elif be10 <= 1.2:
        infl = "DEF_SCAR"
    else:
        infl = "MID"

    # --- Real-rate axis
    if real10 >= 1.5:
        real = "TIGHT"
    elif real10 <= 0.5:
        real = "EASY"
    else:
        real = "MID"

    # --- Map to regime_state (state-machine friendly)
    if panic == "HIGH" and credit == "RISK_OFF":
        regime = "CRISIS_RISK_OFF"
        reasons.append(f"rule: panic=HIGH(VIX={vix}) & credit=RISK_OFF(MA60_dev={('NA' if dev is None else f'{dev:.4f}')})")
    elif (panic in ["MID", "HIGH"] and credit != "RISK_ON") or (credit == "RISK_OFF" and real == "TIGHT"):
        regime = "DEFENSIVE"
        reasons.append(f"rule: defensive via panic={panic}, credit={credit}, real={real}")
    elif infl == "HIGH_INFL" and real == "TIGHT" and panic != "LOW":
        regime = "STAGFLATION_PRESSURE"
        reasons.append(f"rule: infl=HIGH(BE10Y={be10}) & real=TIGHT(REAL10Y={real10}) & panic={panic}")
    elif infl == "HIGH_INFL" and credit == "RISK_ON" and panic == "LOW":
        regime = "OVERHEATING_RISK_ON"
        reasons.append(f"rule: infl=HIGH & credit=RISK_ON & panic=LOW")
    elif infl == "DEF_SCAR" and panic != "HIGH" and credit != "RISK_OFF":
        regime = "DISINFLATION"
        reasons.append(f"rule: infl=LOW(BE10Y={be10}) with no panic-high and not credit risk-off")
    elif panic == "LOW" and credit in ["NEUTRAL", "RISK_ON"] and infl == "MID":
        regime = "GOLDILOCKS"
        reasons.append(f"rule: panic=LOW & credit in neutral/risk-on & infl=MID")
    else:
        regime = "MIXED_TRANSITION"
        reasons.append(f"rule: mixed -> panic={panic}, credit={credit}, infl={infl}, real={real}")

    # --- Confidence scoring (auditable)
    # Start MEDIUM; promote to HIGH only if core dates align AND MA60 available.
    confidence = "MEDIUM"
    core_dates = [vix_date, hygief_date, be10_date, real10_date]
    core_dates = [d for d in core_dates if d]
    if core_dates and len(set(core_dates)) == 1:
        if len(hist_series) >= 60 and dev is not None:
            confidence = "HIGH"
            reasons.append(f"confidence=HIGH: core_dates_aligned={core_dates[0]} and MA60 enabled")
        else:
            confidence = "MEDIUM"
            reasons.append(f"confidence=MEDIUM: core_dates_aligned={core_dates[0]} but MA60 disabled (history<60)")
    else:
        # dates mismatch -> do not drop to LOW automatically; just document.
        if core_dates:
            reasons.append(f"core_dates_mismatch={sorted(list(set(core_dates)))}")
        else:
            reasons.append("core_dates_unavailable")
            confidence = "LOW"

    return {
        "regime_state": regime,
        "confidence": confidence,
        "reasons": reasons,
    }

# -------------------------
# Main
# -------------------------
def main():
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
                "manifest_json": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/refs/heads/main/{out_dir}/{MANIFEST_JSON_NAME}",
            },
        }
        write_json(manifest_path, manifest)
        return

    # -------- generate data files --------
    as_of = as_of_ts_local_iso()

    hist = load_json_list(history_path)
    points: List[Point] = []

    def add(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str):
        dd = normalize_date(data_date)  # normalize to avoid history duplicates
        if not dd or value is None:
            points.append(Point(as_of, series_id, dd or "NA", "NA", source_url or "NA", notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, dd, f"{value}", source_url or "NA", notes))

    # Treasury 10Y nominal & real via XML (try current + previous months)
    nom_date = real_date = None
    nom10 = real10 = None
    nom_notes = real_notes = "NA"
    nom_url_used = real_url_used = "NA"

    for yyyymm in yyyymm_candidates(3):
        url = treasury_xml_url("nominal", yyyymm)
        text, err = http_get(url)
        if err:
            nom_notes, nom_url_used = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(text)
        nom_notes, nom_url_used = notes, url
        if d and v is not None:
            nom_date, nom10 = d, v
            break

    for yyyymm in yyyymm_candidates(3):
        url = treasury_xml_url("real", yyyymm)
        text, err = http_get(url)
        if err:
            real_notes, real_url_used = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(text)
        real_notes, real_url_used = notes, url
        if d and v is not None:
            real_date, real10 = d, v
            break

    add("NOMINAL_10Y", nom_date, nom10, nom_url_used, nom_notes)
    add("REAL_10Y", real_date, real10, real_url_used, real_notes)

    # Breakeven proxy (only if same date)
    be10 = None
    be_date = None
    be_notes = "NA"
    if nom10 is not None and real10 is not None and nom_date and real_date and normalize_date(nom_date) == normalize_date(real_date):
        be10 = nom10 - real10
        be_date = normalize_date(nom_date)
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url_used} + {real_url_used}", be_notes)

    # VIX (official CSV, fallback stooq)
    vix_date, vix_val, vix_notes, vix_url = vix_latest()
    add("VIX_PROXY", vix_date, vix_val, vix_url, vix_notes)

    # Credit proxies: HYG/IEF and TIP/IEF (Stooq ETFs)
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 30)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 30)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 30)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    hyg_ief_ratio = None
    ratio_date = None
    ratio_notes = "NA"
    if hyg_c is not None and ief_c is not None and hyg_d and ief_d and normalize_date(hyg_d) == normalize_date(ief_d):
        hyg_ief_ratio = hyg_c / ief_c
        ratio_date = normalize_date(hyg_d)
    else:
        ratio_notes = "date_mismatch_or_na"
    add("HYG_IEF_RATIO", ratio_date, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_date = None
    tip_ratio_notes = "NA"
    if tip_c is not None and ief_c is not None and tip_d and ief_d and normalize_date(tip_d) == normalize_date(ief_d):
        tip_ief_ratio = tip_c / ief_c
        tip_ratio_date = normalize_date(tip_d)
    else:
        tip_ratio_notes = "date_mismatch_or_na"
    add("TIP_IEF_RATIO", tip_ratio_date, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # OFR FSI (kept, but not pursued)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # Upsert into history (avoid NA dates)
    for p in points:
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # ---- regime classification rows (stored in latest + csv; optional to keep in history) ----
    cls = classify_regime_state([p.__dict__ for p in points], hist)

    today = normalize_date(as_of.split("T")[0]) or "NA"
    points.append(Point(as_of, "REGIME_STATE", today, cls["regime_state"], "NA", "NA"))
    points.append(Point(as_of, "REGIME_CONFIDENCE", today, cls["confidence"], "NA", "NA"))
    reasons_str = json.dumps(cls.get("reasons", []), ensure_ascii=False)
    points.append(Point(as_of, "REGIME_REASONS", today, reasons_str, "NA", "NA"))

    # If you DO NOT want regime rows in history, uncomment below:
    # for p in points[-3:]:
    #     pass
    # Otherwise they will be upserted too (since data_date != "NA"):
    for p in points[-3:]:
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # Write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()