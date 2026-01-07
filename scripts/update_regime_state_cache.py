import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any

import requests
import xml.etree.ElementTree as ET

# -------------------------
# Paths / Outputs
# -------------------------
DEFAULT_OUT_DIR = "regime_state_cache"
LATEST_JSON_NAME = "latest.json"
LATEST_CSV_NAME = "latest.csv"
HISTORY_JSON_NAME = "history.json"
MANIFEST_JSON_NAME = "manifest.json"

SCRIPT_VERSION = "regime_state_cache_v3"
MAX_HISTORY_ROWS = 5000

# -------------------------
# Time helpers
# -------------------------
def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def as_of_ts_local_iso() -> str:
    # Runner TZ is set in workflow; this produces explicit offset like +08:00
    return datetime.now().astimezone().isoformat()

def today_local_yyyymmdd() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")

# -------------------------
# Date normalization (CRITICAL: avoid history duplicates)
# -------------------------
def normalize_date(s: Optional[str]) -> Optional[str]:
    """
    Normalize to YYYY-MM-DD.
    Accepts:
      - YYYY-MM-DD
      - YYYY-MM-DDTHH:MM:SS
      - MM/DD/YYYY
    Returns None if cannot parse.
    """
    if not s:
        return None
    ss = str(s).strip()
    if not ss:
        return None

    # YYYY-MM-DD or YYYY-MM-DDTHH...
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", ss)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # MM/DD/YYYY
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", ss)
    if m:
        mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"

    return None

# -------------------------
# HTTP helpers
# -------------------------
def http_get(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": f"{SCRIPT_VERSION}/1.0",
                "Accept": "*/*",
            },
        )
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
# Treasury endpoints
# -------------------------
def treasury_xml_url(data: str, yyyymm: str) -> str:
    # data: daily_treasury_yield_curve / daily_treasury_real_yield_curve
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data={data}&field_tdr_date_value_month={yyyymm}"
    )

def yyyymm_candidates(n_months: int = 6) -> List[str]:
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

def _xml_rows_to_dicts(xml_text: str) -> List[Dict[str, str]]:
    """
    Parse Treasury XML to list of dict rows (best-effort).
    Strategy:
      - find elements that look like "row" nodes: they have children incl a date-ish field.
      - build dict of child_tag -> child_text
    """
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    rows: List[Dict[str, str]] = []
    # Heuristic: a "row" has multiple children and at least one child tag contains "date"
    for node in root.iter():
        children = list(node)
        if len(children) < 2:
            continue
        has_date = any(("date" in (c.tag or "").lower()) for c in children)
        if not has_date:
            continue
        row: Dict[str, str] = {}
        for c in children:
            tag = (c.tag or "").strip()
            txt = (c.text or "").strip()
            if tag:
                row[tag] = txt
        if row:
            rows.append(row)
    return rows

def parse_latest_10y_from_treasury_xml(xml_text: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Return (data_date_yyyy_mm_dd, value_10y, notes)
    Notes:
      - Robust field matching: any field whose name contains '10' and ('year' or 'yr')
    """
    rows = _xml_rows_to_dicts(xml_text)
    if not rows:
        return None, None, "xml_no_rows"

    # Identify date key candidates
    def get_date_from_row(r: Dict[str, str]) -> Optional[str]:
        for k, v in r.items():
            if "date" in k.lower():
                return normalize_date(v)
        return None

    # Identify 10y key candidates
    def get_10y_from_row(r: Dict[str, str]) -> Optional[float]:
        best = None
        for k, v in r.items():
            kk = k.lower()
            if "10" in kk and ("year" in kk or "yr" in kk):
                vv = safe_float(v)
                if vv is not None:
                    best = vv
                    break
        if best is not None:
            return best
        # fallback: sometimes column naming is odd; try any numeric field that contains '10'
        for k, v in r.items():
            kk = k.lower()
            if "10" in kk:
                vv = safe_float(v)
                if vv is not None:
                    return vv
        return None

    extracted: List[Tuple[str, float]] = []
    for r in rows:
        d = get_date_from_row(r)
        v = get_10y_from_row(r)
        if d and v is not None:
            extracted.append((d, v))

    if not extracted:
        return None, None, "xml_parse_fail_10y"

    extracted.sort(key=lambda x: x[0])
    d_last, v_last = extracted[-1]
    return d_last, v_last, "NA"

def fetch_latest_treasury_10y(data_kind: str) -> Tuple[Optional[str], Optional[float], str, str]:
    """
    data_kind:
      - "nominal" -> daily_treasury_yield_curve
      - "real"    -> daily_treasury_real_yield_curve
    Returns (data_date, value, notes, source_url)
    """
    data = "daily_treasury_yield_curve" if data_kind == "nominal" else "daily_treasury_real_yield_curve"
    last_err = "NA"
    last_url = "NA"

    for yyyymm in yyyymm_candidates(6):
        url = treasury_xml_url(data=data, yyyymm=yyyymm)
        xml_text, err = http_get(url)
        if err:
            last_err, last_url = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(xml_text)
        last_err, last_url = notes, url
        if d and v is not None and notes == "NA":
            return d, v, "NA", url

    # If we get here, nothing usable
    return None, None, last_err, last_url

# -------------------------
# CBOE VIX CSV (primary) + Stooq fallback
# -------------------------
def cboe_vix_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get(url)
    if err:
        return None, None, f"cboe_{err}", url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "cboe_empty_csv", url

    last = rows[-1]
    date_raw = (last.get("DATE") or last.get("Date") or last.get("date") or "").strip()
    d = normalize_date(date_raw)
    v = safe_float(last.get("CLOSE") or last.get("Close") or last.get("close"))
    if not d or v is None:
        return d, None, "cboe_parse_fail", url
    return d, v, "NA", url

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
    date = normalize_date((last.get("Date") or "").strip())
    close = safe_float(last.get("Close"))
    if not date or close is None:
        return date, None, "na_or_parse_fail", url

    return date, close, "NA", url

def vix_proxy_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    d, v, notes, url = cboe_vix_latest()
    if notes == "NA" and d and v is not None:
        return d, v, "NA", url
    # fallback to Stooq
    d2, v2, n2, u2 = stooq_daily_close("vix", 30)
    if d2 and v2 is not None and n2 == "NA":
        return d2, v2, f"{notes};stooq_ok", u2
    return None, None, f"{notes};stooq_{n2}", url

# -------------------------
# OFR FSI (intentionally not fetched; normal degradation)
# -------------------------
def ofr_fsi_placeholder() -> Tuple[Optional[str], Optional[float], str, str]:
    return None, None, "NO_PUBLIC_CSV_LINK (ignored; normal degradation)", "https://www.financialresearch.gov/financial-stress-index/"

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

    _ = load_json_list(history_json)  # just ensure loadable

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
# Helpers for regime calc
# -------------------------
def build_latest_map(points: List[Point]) -> Dict[str, Point]:
    return {p.series_id: p for p in points}

def extract_series_history(hist: List[dict], series_id: str) -> List[Tuple[str, float]]:
    """
    Return sorted list of (data_date, value_float) with normalized dates and valid floats.
    Deduplicate by date (keep first encountered).
    """
    seen = set()
    out: List[Tuple[str, float]] = []
    for r in hist:
        if (r.get("series_id") or "") != series_id:
            continue
        d = normalize_date(r.get("data_date"))
        v = safe_float(r.get("value"))
        if not d or v is None:
            continue
        if d in seen:
            continue
        seen.add(d)
        out.append((d, v))
    out.sort(key=lambda x: x[0])
    return out

def sma_last(values: List[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    window = values[-n:]
    return sum(window) / float(n)

def calc_hyg_ief_dev_ma60(latest_ratio: Optional[float], hist_pairs: List[Tuple[str, float]]) -> Tuple[Optional[float], Optional[float], str]:
    """
    Returns (ma60, dev, notes)
    dev = latest_ratio / ma60 - 1
    """
    if latest_ratio is None:
        return None, None, "ratio_na"
    if len(hist_pairs) < 60:
        return None, None, f"history_lt_60({len(hist_pairs)})"
    ma60 = sma_last([v for _, v in hist_pairs], 60)
    if ma60 is None or ma60 == 0:
        return None, None, "ma60_na_or_zero"
    dev = latest_ratio / ma60 - 1.0
    return ma60, dev, "NA"

def classify_regime_state(
    latest_map: Dict[str, Point],
    hist: List[dict],
) -> Tuple[str, str, List[str]]:
    """
    Minimal state classifier:
      Inputs (core):
        - VIX_PROXY
        - BE10Y_PROXY (breakeven proxy)
        - HYG_IEF dev vs MA60 (credit risk-on/off)
      OFR_FSI is OPTIONAL and NA is normal degradation (should not reduce confidence).

    Output:
      (regime_state, confidence, reasons[])
    """
    reasons: List[str] = []

    # ---- VIX ----
    vix_p = latest_map.get("VIX_PROXY")
    vix = safe_float(vix_p.value) if vix_p else None
    if vix is None:
        reasons.append("core_missing=VIX_PROXY")
    else:
        if vix >= 20:
            reasons.append(f"panic=HIGH(VIX={vix})")
        elif vix >= 16:
            reasons.append(f"panic=MED(VIX={vix})")
        else:
            reasons.append(f"panic=LOW(VIX={vix})")

    # ---- Breakeven ----
    be_p = latest_map.get("BE10Y_PROXY")
    be = safe_float(be_p.value) if be_p else None
    if be is None:
        reasons.append("core_missing=BE10Y_PROXY")
        infl_bucket = None
    else:
        if be >= 2.5:
            infl_bucket = "HIGH"
        elif be >= 1.5:
            infl_bucket = "MID"
        else:
            infl_bucket = "LOW"
        reasons.append(f"inflation_expect={infl_bucket}(BE10Y={be})")

    # ---- Credit (HYG/IEF MA60 dev) ----
    ratio_p = latest_map.get("HYG_IEF_RATIO")
    ratio = safe_float(ratio_p.value) if ratio_p else None
    hist_ratio = extract_series_history(hist, "HYG_IEF_RATIO")
    ma60, dev, dev_note = calc_hyg_ief_dev_ma60(ratio, hist_ratio)
    credit_bucket = None
    if dev is None:
        # allow degrade: if MA60 not available, treat credit as unknown, not fatal by itself
        reasons.append(f"credit_dev_unavailable({dev_note})")
    else:
        if dev >= 0.01:
            credit_bucket = "RISK_ON"
        elif dev <= -0.01:
            credit_bucket = "RISK_OFF"
        else:
            credit_bucket = "NEUTRAL"
        reasons.append(f"credit={credit_bucket}(dev={dev:.4f},ma60={ma60:.6f},ratio={ratio:.6f})")

    # ---- OFR optional ----
    ofr_p = latest_map.get("OFR_FSI")
    ofr_val = safe_float(ofr_p.value) if ofr_p else None
    if ofr_val is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")

    # ---- Regime decision ----
    # Determine how many core signals we truly have:
    core_present = 0
    if vix is not None:
        core_present += 1
    if be is not None:
        core_present += 1
    if dev is not None:
        core_present += 1

    # Confidence: based on core_present (OFR ignored)
    if core_present >= 3:
        confidence = "HIGH"
    elif core_present == 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # If too little info, avoid pretending we know
    if core_present <= 1:
        return "UNKNOWN_INSUFFICIENT_DATA", "LOW", reasons

    # Map to a small set of regimes (minimal & auditable)
    panic_high = (vix is not None and vix >= 20)
    panic_med = (vix is not None and 16 <= vix < 20)
    panic_low = (vix is not None and vix < 16)

    infl_high = (infl_bucket == "HIGH")
    infl_low = (infl_bucket == "LOW")

    credit_off = (credit_bucket == "RISK_OFF")
    credit_on = (credit_bucket == "RISK_ON")

    # Crisis / Defensive first
    if (panic_high or panic_med) and credit_off and infl_low:
        return "CRISIS_CRASH", confidence, reasons
    if (panic_high or panic_med) and credit_off:
        return "DEFENSIVE_RISK_OFF", confidence, reasons

    # Overheating / Goldilocks
    if panic_low and infl_high:
        return "OVERHEATING_INFLATION", confidence, reasons
    if panic_low and (not infl_low) and credit_on:
        return "GOLDILOCKS_RISK_ON", confidence, reasons

    # Fallback
    return "NEUTRAL_MIXED", confidence, reasons

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
                # IMPORTANT: manifest points to branch latest (audit entry), NOT data SHA
                "manifest_json": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/refs/heads/main/{out_dir}/{MANIFEST_JSON_NAME}",
            },
        }
        write_json(manifest_path, manifest)
        return

    # -------- generate data files --------
    as_of = as_of_ts_local_iso()
    hist = load_json_list(history_path)
    points: List[Point] = []

    def add(series_id: str, data_date_raw: Optional[str], value: Optional[float], source_url: str, notes: str):
        d = normalize_date(data_date_raw)
        if not d or value is None:
            points.append(Point(as_of, series_id, d or "NA", "NA", source_url or "NA", notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, d, f"{value}", source_url or "NA", notes))

    # --- Treasury 10Y nominal & real ---
    nom_d, nom_v, nom_notes, nom_url = fetch_latest_treasury_10y("nominal")
    real_d, real_v, real_notes, real_url = fetch_latest_treasury_10y("real")

    add("NOMINAL_10Y", nom_d, nom_v, nom_url, nom_notes)
    add("REAL_10Y", real_d, real_v, real_url, real_notes)

    # Breakeven proxy (only if same normalized date)
    be10 = None
    be_date = None
    be_notes = "NA"
    if nom_v is not None and real_v is not None and nom_d and real_d and normalize_date(nom_d) == normalize_date(real_d):
        be10 = nom_v - real_v
        be_date = normalize_date(nom_d)
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url} + {real_url}".strip(), be_notes)

    # --- VIX proxy (CBOE primary; Stooq fallback) ---
    vix_d, vix_v, vix_notes, vix_url = vix_proxy_latest()
    add("VIX_PROXY", vix_d, vix_v, vix_url, vix_notes)

    # --- Credit proxies via Stooq ---
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 30)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 30)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 30)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    # ratios (only if same normalized date)
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

    # --- OFR FSI (kept but not fetched) ---
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_placeholder()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # ---- Update history (only rows with valid dates) ----
    for p in points:
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # ---- Regime classification (minimal; uses updated hist in-memory) ----
    latest_map = build_latest_map(points)
    regime_state, confidence, reasons = classify_regime_state(latest_map, hist)

    # Store regime outputs as additional "series"
    d_today = today_local_yyyymmdd()
    points.append(Point(as_of, "REGIME_STATE", d_today, regime_state, "NA", "NA"))
    points.append(Point(as_of, "REGIME_CONFIDENCE", d_today, confidence, "NA", "NA"))
    points.append(Point(as_of, "REGIME_REASONS", d_today, json.dumps(reasons, ensure_ascii=False), "NA", "NA"))

    # write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()