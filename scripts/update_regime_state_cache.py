import argparse
import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict

import requests

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

# Optional: allow borrowing missing values from fallback_cache
ENABLE_BORROW_FROM_FALLBACK = True
FALLBACK_MANIFEST_URL = "https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/refs/heads/main/fallback_cache/manifest.json"

# -------------------------
# Time helpers
# -------------------------
def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def as_of_ts_local_iso() -> str:
    # Runner TZ is set in workflow; this produces explicit offset like +08:00
    return datetime.now().astimezone().isoformat()

def normalize_date_to_iso(s: Optional[str]) -> Optional[str]:
    """
    Normalize common date formats:
    - 'YYYY-MM-DD' -> same
    - 'MM/DD/YYYY' -> 'YYYY-MM-DD'
    - otherwise: return original stripped
    """
    if not s:
        return None
    ss = str(s).strip()
    if not ss:
        return None
    # ISO already
    if re.match(r"^\d{4}-\d{2}-\d{2}$", ss):
        return ss
    # US format
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", ss)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{yy:04d}-{mm:02d}-{dd:02d}"
    return ss

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
def treasury_csv_url(kind: str, yyyymm: str) -> str:
    # monthly CSV (your original approach)
    if kind == "nominal":
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"daily-treasury-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_yield_curve"
        )
    if kind == "real":
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"daily-treasury-real-yield-curve-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_real_yield_curve"
        )
    raise ValueError("unknown kind")

def treasury_xml_url(kind: str, yyyymm: str) -> str:
    # XML feed (more stable than monthly CSV in practice)
    if kind == "nominal":
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
            f"?data=daily_treasury_yield_curve&field_tdr_date_value_month={yyyymm}"
        )
    if kind == "real":
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
            f"?data=daily_treasury_real_yield_curve&field_tdr_date_value_month={yyyymm}"
        )
    raise ValueError("unknown kind")

def yyyymm_candidates(n_months: int = 6) -> List[str]:
    now = datetime.now().astimezone()
    out = []
    y, m = now.year, now.month
    for i in range(n_months):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        out.append(f"{yy:04d}{mm:02d}")
    return out

def parse_latest_10y_from_treasury_csv(csv_text: str) -> Tuple[Optional[str], Optional[float], str, Optional[str]]:
    """
    Returns (data_date_iso, value_10y, notes, used_col_name)
    """
    reader = csv.DictReader(csv_text.splitlines())
    rows = [r for r in reader if r and any((str(v).strip() if v is not None else "") for v in r.values())]
    if not rows:
        return None, None, "empty_csv", None

    last = rows[-1]
    raw_date = (last.get("Date") or last.get("date") or last.get("DATE") or "").strip()
    date_iso = normalize_date_to_iso(raw_date)

    # common 10Y names
    candidates = ["10 Yr", "10 yr", "10 Year", "10 year", "10-year", "10 Year Treasury", "10 Yr Treasury"]
    col = None
    for c in candidates:
        if c in last:
            col = c
            break

    # fuzzy fallback
    if col is None:
        for k in (last.keys() or []):
            if not k:
                continue
            kk = k.lower()
            if ("10" in kk) and (("yr" in kk) or ("year" in kk)):
                col = k
                break

    if col is None:
        return date_iso, None, "missing_10y_column", None

    val = safe_float(last.get(col))
    if val is None:
        return date_iso, None, "na_or_parse_fail", col

    return date_iso, val, "NA", col

def parse_latest_10y_from_treasury_xml(xml_text: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Best-effort parser for Treasury XML feed.
    We look for the last <m:properties> block and extract:
      - a date field (NEW_DATE/DATE)
      - a 10Y field (BC_10YEAR or any tag that contains '10' and 'YEAR')
    """
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return None, None, "xml_parse_fail"

    # find all "properties" nodes (namespace varies)
    props_nodes = []
    for el in root.iter():
        tag = el.tag.lower()
        if tag.endswith("properties"):
            props_nodes.append(el)

    if not props_nodes:
        return None, None, "xml_no_properties"

    last_props = props_nodes[-1]

    date_iso: Optional[str] = None
    val_10y: Optional[float] = None

    # extract date
    for ch in list(last_props):
        t = ch.tag.lower()
        if t.endswith("new_date") or t.endswith("date"):
            date_iso = normalize_date_to_iso((ch.text or "").strip())
            break

    # extract 10Y
    # prefer BC_10YEAR (nominal) / TC_10YEAR (real) if exists, else fuzzy
    preferred_suffixes = ["bc_10year", "tc_10year", "tenyear", "10year"]
    # pass 1: preferred
    for ch in list(last_props):
        t = ch.tag.lower()
        for suf in preferred_suffixes:
            if t.endswith(suf):
                vv = safe_float((ch.text or "").strip())
                if vv is not None:
                    val_10y = vv
                    break
        if val_10y is not None:
            break
    # pass 2: fuzzy
    if val_10y is None:
        for ch in list(last_props):
            t = ch.tag.lower()
            if ("10" in t) and ("year" in t):
                vv = safe_float((ch.text or "").strip())
                if vv is not None:
                    val_10y = vv
                    break

    if date_iso is None:
        return None, val_10y, "xml_missing_date"
    if val_10y is None:
        return date_iso, None, "xml_missing_10y"

    return date_iso, val_10y, "NA"

def treasury_latest_10y(kind: str) -> Tuple[Optional[str], Optional[float], str, str]:
    """
    Try XML first (for up to 6 months), then CSV fallback.
    Returns (data_date_iso, value_10y, notes, source_url_used)
    """
    last_err = "NA"
    last_url = "NA"

    for yyyymm in yyyymm_candidates(6):
        url = treasury_xml_url(kind, yyyymm)
        text, err = http_get(url)
        if err:
            last_err, last_url = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(text)
        last_err, last_url = notes, url
        if d and v is not None and notes == "NA":
            return d, v, "NA", url

    for yyyymm in yyyymm_candidates(6):
        url = treasury_csv_url(kind, yyyymm)
        text, err = http_get(url)
        if err:
            last_err, last_url = err, url
            continue
        d, v, notes, _ = parse_latest_10y_from_treasury_csv(text)
        last_err, last_url = notes, url
        if d and v is not None and notes == "NA":
            return d, v, "NA", url

    return None, None, last_err, last_url

# -------------------------
# VIX (CBOE CSV first, Stooq fallback)
# -------------------------
def vix_from_cboe_csv() -> Tuple[Optional[str], Optional[float], str, str]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get(url)
    if err:
        return None, None, f"cboe_{err}", url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader]
    if not rows:
        return None, None, "cboe_empty_csv", url

    last = rows[-1]
    raw_date = (last.get("DATE") or last.get("Date") or last.get("date") or "").strip()
    date_iso = normalize_date_to_iso(raw_date)

    # Try common close columns
    close = None
    for k in ["CLOSE", "Close", "close"]:
        if k in last:
            close = safe_float(last.get(k))
            break
    if close is None:
        # fallback: first numeric field
        for _, v in last.items():
            vv = safe_float(v)
            if vv is not None:
                close = vv
                break

    if close is None:
        return date_iso, None, "cboe_na_or_parse_fail", url

    return date_iso, close, "NA", url

# -------------------------
# Stooq
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 20) -> Tuple[Optional[str], Optional[float], str, str]:
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err = http_get(url)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    date_iso = normalize_date_to_iso((last.get("Date") or "").strip())
    close = safe_float(last.get("Close"))
    if close is None:
        return date_iso, None, "na_or_parse_fail", url

    return date_iso, close, "NA", url

def vix_proxy() -> Tuple[Optional[str], Optional[float], str, str]:
    d, v, notes, url = vix_from_cboe_csv()
    if d and v is not None and notes == "NA":
        return d, v, "NA", url

    # fallback to Stooq: try ^vix first (more common)
    d2, v2, n2, u2 = stooq_daily_close("^vix", 30)
    if d2 and v2 is not None and n2 == "NA":
        return d2, v2, "WARN:stooq_vix", u2

    # last fallback: old symbol 'vix' (your v2 used this)
    d3, v3, n3, u3 = stooq_daily_close("vix", 30)
    if d3 and v3 is not None and n3 == "NA":
        return d3, v3, "WARN:stooq_vix(symbol=vix)", u3

    return None, None, f"{notes};stooq_{n2};stooq2_{n3}", url

# -------------------------
# OFR FSI (explicit degradable)
# -------------------------
def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    html, err = http_get(page_url)
    if err:
        return None, None, f"page_{err}", page_url

    # best-effort: look for any csv/zip links in html
    links = re.findall(r"https?://[^\"']+\.(?:csv|zip)", html, flags=re.IGNORECASE)
    links = [u for u in links if ("fsi" in u.lower()) or ("stress" in u.lower())]
    if not links:
        # explicit degradable result (not a bug)
        return None, None, "NO_PUBLIC_CSV_LINK", page_url

    data_url = links[0]
    content, err2 = http_get(data_url)
    if err2:
        return None, None, f"data_{err2}", data_url

    if data_url.lower().endswith(".zip"):
        return None, None, "zip_not_supported_in_v3", data_url

    reader = csv.DictReader(content.splitlines())
    rows = [r for r in reader]
    if not rows:
        return None, None, "empty_csv", data_url

    last = rows[-1]
    date_iso = normalize_date_to_iso((last.get("Date") or last.get("date") or "").strip())

    val = None
    for k, v in last.items():
        if k and ("fsi" in k.lower() or "stress" in k.lower() or "index" in k.lower()):
            vv = safe_float(v)
            if vv is not None:
                val = vv
                break
    if val is None:
        for _, v in last.items():
            vv = safe_float(v)
            if vv is not None:
                val = vv
                break

    if val is None:
        return date_iso, None, "parse_fail", data_url

    return date_iso, val, "NA", data_url

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
# Borrow from fallback-cache (optional)
# -------------------------
def try_borrow_from_fallback() -> Dict[str, dict]:
    """
    Returns dict: series_id -> record from fallback_cache latest.json
    """
    text, err = http_get(FALLBACK_MANIFEST_URL)
    if err:
        return {}

    try:
        m = json.loads(text)
    except Exception:
        return {}

    pinned = (m.get("pinned") or {})
    latest_url = pinned.get("latest_json")
    if not latest_url:
        return {}

    t2, err2 = http_get(latest_url)
    if err2:
        return {}

    try:
        rows = json.loads(t2)
    except Exception:
        return {}

    out: Dict[str, dict] = {}
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("series_id"):
                out[str(r["series_id"])] = r
    return out

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
        dd = normalize_date_to_iso(data_date) if data_date else None
        if not dd or value is None:
            points.append(Point(as_of, series_id, dd or "NA", "NA", source_url or "NA", notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, dd, f"{value}", source_url or "NA", notes))

    # Treasury 10Y nominal & real
    nom_date, nom10, nom_notes, nom_url_used = treasury_latest_10y("nominal")
    real_date, real10, real_notes, real_url_used = treasury_latest_10y("real")

    add("NOMINAL_10Y", nom_date, nom10, nom_url_used, nom_notes)
    add("REAL_10Y", real_date, real10, real_url_used, real_notes)

    # Breakeven proxy (only if same date)
    be10 = None
    be_date = None
    be_notes = "NA"
    if (nom10 is not None) and (real10 is not None) and nom_date and real_date and (nom_date == real_date):
        be10 = nom10 - real10
        be_date = nom_date
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url_used} + {real_url_used}".strip(), be_notes)

    # VIX (CBOE CSV first)
    vix_date, vix_close, vix_notes, vix_url = vix_proxy()
    add("VIX_PROXY", vix_date, vix_close, vix_url, vix_notes)

    # Credit proxies: HYG/IEF and TIP/IEF (Stooq)
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 30)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 30)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 30)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    hyg_ief_ratio = None
    ratio_date = None
    ratio_notes = "NA"
    if hyg_c is not None and ief_c is not None and hyg_d and ief_d and normalize_date_to_iso(hyg_d) == normalize_date_to_iso(ief_d):
        hyg_ief_ratio = hyg_c / ief_c
        ratio_date = hyg_d
    else:
        ratio_notes = "date_mismatch_or_na"
    add("HYG_IEF_RATIO", ratio_date, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_date = None
    tip_ratio_notes = "NA"
    if tip_c is not None and ief_c is not None and tip_d and ief_d and normalize_date_to_iso(tip_d) == normalize_date_to_iso(ief_d):
        tip_ief_ratio = tip_c / ief_c
        tip_ratio_date = tip_d
    else:
        tip_ratio_notes = "date_mismatch_or_na"
    add("TIP_IEF_RATIO", tip_ratio_date, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # OFR FSI (explicit degradable)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # Optional: borrow missing values from fallback_cache
    if ENABLE_BORROW_FROM_FALLBACK:
        fb = try_borrow_from_fallback()
        # If VIX missing, borrow VIXCLS as VIX_PROXY
        for p in points:
            if p.series_id == "VIX_PROXY" and (p.value == "NA" or p.data_date == "NA"):
                r = fb.get("VIXCLS")
                if r:
                    dd = normalize_date_to_iso(str(r.get("data_date") or ""))
                    vv = safe_float(r.get("value"))
                    src = str(r.get("source_url") or "NA")
                    p.data_date = dd or "NA"
                    p.value = str(vv) if vv is not None else "NA"
                    p.source_url = src
                    p.notes = f"BORROWED:fallback_cache;{r.get('notes','NA')}"
        # If NOMINAL_10Y missing, borrow DGS10
        for p in points:
            if p.series_id == "NOMINAL_10Y" and (p.value == "NA" or p.data_date == "NA"):
                r = fb.get("DGS10")
                if r:
                    dd = normalize_date_to_iso(str(r.get("data_date") or ""))
                    vv = safe_float(r.get("value"))
                    src = str(r.get("source_url") or "NA")
                    p.data_date = dd or "NA"
                    p.value = str(vv) if vv is not None else "NA"
                    p.source_url = src
                    p.notes = f"BORROWED:fallback_cache;{r.get('notes','NA')}"

    # upsert into history (avoid NA dates)
    for p in points:
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()