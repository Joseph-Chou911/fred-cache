import argparse
import csv
import json
import os
import re
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

# -------------------------
# Time helpers
# -------------------------
def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def as_of_ts_local_iso() -> str:
    # Runner TZ is set in workflow; this produces explicit offset like +08:00
    return datetime.now().astimezone().isoformat()

def normalize_date_iso(s: Optional[str]) -> Optional[str]:
    """
    Normalize dates into YYYY-MM-DD to avoid BE proxy date mismatch.
    Supports:
      - YYYY-MM-DD
      - MM/DD/YYYY
    """
    if not s:
        return None
    ss = str(s).strip()
    if not ss:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(ss, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return ss  # last resort: keep original (but this may cause mismatches)

# -------------------------
# HTTP helpers
# -------------------------
def http_get(url: str, timeout: int = 20) -> Tuple[Optional[str], Optional[str]]:
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
# Treasury endpoints
# -------------------------
def treasury_csv_url(kind: str, yyyymm: str) -> str:
    """
    NOTE:
      - nominal remains CSV endpoint (works well)
      - real moved to TextView endpoint (HTML table) in v3 (see treasury_real_textview_url)
    """
    if kind == "nominal":
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"daily-treasury-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_yield_curve"
        )
    raise ValueError("unknown kind")

def treasury_real_textview_url(yyyymm: str) -> str:
    """
    v3 fix: use Treasury TextView HTML table for Daily Treasury Real Yield Curve Rates.
    Example pattern observed on Treasury site:
      https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=202512&type=daily_treasury_real_yield_curve
    """
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView"
        f"?field_tdr_date_value={yyyymm}&type=daily_treasury_real_yield_curve"
    )

def yyyymm_candidates(n_months: int = 2) -> List[str]:
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

def parse_latest_yield_from_treasury(csv_text: str) -> Tuple[Optional[str], Optional[float], str, Optional[str]]:
    """
    For nominal CSV:
      Returns (data_date_iso, value_10y, notes, used_col_name)
    """
    reader = csv.DictReader(csv_text.splitlines())
    rows = [r for r in reader if r and any((v or "").strip() for v in r.values() if isinstance(v, str))]
    if not rows:
        return None, None, "empty_csv", None

    last = rows[-1]
    date_raw = (last.get("Date") or last.get("date") or last.get("DATE") or "").strip() or None
    date = normalize_date_iso(date_raw)

    # Try common 10Y column names
    candidates = ["10 Yr", "10 yr", "10 Year", "10 year", "10-year", "10 Year Treasury", "10 Yr Treasury"]
    col = None
    for c in candidates:
        if c in last:
            col = c
            break

    # Fuzzy fallback
    if col is None:
        for k in (last.keys() or []):
            if not k:
                continue
            kk = k.lower()
            if "10" in kk and ("yr" in kk or "year" in kk):
                col = k
                break

    if col is None:
        return date, None, "missing_10y_column", None

    val = safe_float(last.get(col))
    if val is None:
        return date, None, "na_or_parse_fail", col

    return date, val, "NA", col

def parse_latest_real10y_from_textview(html: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    v3: Parse Treasury TextView (HTML) table to get the latest 10Y real yield.
    The table rows include lines like:
      12/31/2025  1.77  1.81  1.91  2.15  2.18
    Columns observed:
      Date, 5 YR, 7 YR, 10 YR, 20 YR, 30 YR
    We capture Date + first 3 numeric cols and take the 3rd numeric as 10Y.
    Returns (data_date_iso, real10y, notes)
    """
    # Extract row-like patterns anywhere in HTML
    # date + at least 3 numeric columns
    pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
    )
    matches = pattern.findall(html)
    if not matches:
        return None, None, "no_table_rows_found"

    date_raw, _v5, _v7, v10 = matches[-1]
    date = normalize_date_iso(date_raw)
    val10 = safe_float(v10)
    if not date or val10 is None:
        return date or None, None, "parse_fail_latest_row"

    return date, val10, "NA"

# -------------------------
# VIX (primary: CBOE official CSV; fallback: Stooq)
# -------------------------
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

def cboe_vix_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    Primary VIX source: CBOE official daily prices CSV.
    Returns (data_date_iso, close, notes, source_url)
    """
    text, err = http_get(CBOE_VIX_CSV)
    if err:
        return None, None, f"cboe_{err}", CBOE_VIX_CSV

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader]
    if not rows:
        return None, None, "cboe_empty_csv", CBOE_VIX_CSV

    last = rows[-1]
    date_raw = (last.get("DATE") or last.get("Date") or last.get("date") or "").strip() or None
    date = normalize_date_iso(date_raw)

    # Common columns in this file: VIX Close / CLOSE
    close = safe_float(last.get("VIX Close") or last.get("CLOSE") or last.get("Close"))
    if close is None:
        # fallback: scan numeric values in row
        for _, v in last.items():
            vv = safe_float(v)
            if vv is not None:
                close = vv
        if close is None:
            return date, None, "cboe_parse_fail", CBOE_VIX_CSV

    return date, close, "NA", CBOE_VIX_CSV

# -------------------------
# Stooq
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 14) -> Tuple[Optional[str], Optional[float], str, str]:
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
    date_raw = (last.get("Date") or "").strip() or None
    date = normalize_date_iso(date_raw)
    close = safe_float(last.get("Close"))
    if close is None:
        return date, None, "na_or_parse_fail", url

    return date, close, "NA", url

# -------------------------
# OFR FSI (explicitly degradable)
# -------------------------
def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    v3: Make OFR_FSI explicitly degradable.
    - If we can't find a usable CSV: return (None, None, "degraded_<reason>", page_url)
    - If data URL is zip: return (None, None, "degraded_zip_not_supported", data_url)
    """
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    html, err = http_get(page_url)
    if err:
        return None, None, f"degraded_page_{err}", page_url

    links = re.findall(r"https?://[^\"']+\.(?:csv|zip)", html, flags=re.IGNORECASE)
    links = [u for u in links if "fsi" in u.lower() or "stress" in u.lower()]
    if not links:
        return None, None, "degraded_data_link_not_found", page_url

    data_url = links[0]
    if data_url.lower().endswith(".zip"):
        return None, None, "degraded_zip_not_supported", data_url

    content, err2 = http_get(data_url)
    if err2:
        return None, None, f"degraded_data_{err2}", data_url

    reader = csv.DictReader(content.splitlines())
    rows = [r for r in reader]
    if not rows:
        return None, None, "degraded_empty_csv", data_url

    last = rows[-1]
    date_raw = (last.get("Date") or last.get("date") or "").strip() or None
    date = normalize_date_iso(date_raw)

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
        return date, None, "degraded_parse_fail", data_url

    return date, val, "NA", data_url

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
    for i, r in enumerate(latest[:50]):  # sample first 50
        if not isinstance(r, dict):
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} not dict")
        missing = required - set(r.keys())
        if missing:
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} missing keys {sorted(list(missing))}")

    # history basic check
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
        if not data_date or value is None:
            points.append(Point(as_of, series_id, data_date or "NA", "NA", source_url, notes))
        else:
            points.append(Point(as_of, series_id, data_date, f"{value}", source_url, notes))

    # Treasury 10Y nominal (CSV, unchanged) & real (TextView HTML, v3 fix)
    nom_date = real_date = None
    nom10 = real10 = None
    nom_notes = real_notes = "NA"
    nom_url_used = real_url_used = ""

    # Nominal 10Y (CSV)
    for yyyymm in yyyymm_candidates(2):
        url = treasury_csv_url("nominal", yyyymm)
        text, err = http_get(url)
        if err:
            nom_notes, nom_url_used = err, url
            continue
        d, v, notes, _ = parse_latest_yield_from_treasury(text)
        nom_notes, nom_url_used = notes, url
        if d and v is not None:
            nom_date, nom10 = d, v
            break

    # Real 10Y (TextView HTML) — v3
    for yyyymm in yyyymm_candidates(2):
        url = treasury_real_textview_url(yyyymm)
        html, err = http_get(url)
        if err:
            real_notes, real_url_used = f"textview_{err}", url
            continue
        d, v, notes = parse_latest_real10y_from_textview(html)
        real_notes, real_url_used = notes, url
        if d and v is not None:
            real_date, real10 = d, v
            break

    add("NOMINAL_10Y", nom_date, nom10, nom_url_used or "NA", nom_notes)
    add("REAL_10Y", real_date, real10, real_url_used or "NA", real_notes)

    # Breakeven proxy (only if same normalized date)
    be10 = None
    be_date = None
    be_notes = "NA"
    if nom10 is not None and real10 is not None and nom_date and real_date and nom_date == real_date:
        be10 = nom10 - real10
        be_date = nom_date
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url_used} + {real_url_used}".strip(), be_notes)

    # VIX (primary: CBOE; fallback: Stooq) — v3
    vix_date, vix_close, vix_notes, vix_url = cboe_vix_latest()
    if vix_close is None:
        # fallback to Stooq
        sd, sc, sn, su = stooq_daily_close("vix", 14)
        # keep evidence of fallback
        vix_date, vix_close = sd, sc
        vix_url = su
        vix_notes = f"fallback_stooq:{sn}" if sn != "NA" else "fallback_stooq"
    add("VIX_PROXY", vix_date, vix_close, vix_url, vix_notes)

    # Credit proxies: HYG/IEF and TIP/IEF
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 14)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 14)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 14)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    hyg_ief_ratio = None
    ratio_date = None
    ratio_notes = "NA"
    if hyg_c is not None and ief_c is not None and hyg_d and ief_d and hyg_d == ief_d:
        hyg_ief_ratio = hyg_c / ief_c
        ratio_date = hyg_d
    else:
        ratio_notes = "date_mismatch_or_na"
    add("HYG_IEF_RATIO", ratio_date, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_date = None
    tip_ratio_notes = "NA"
    if tip_c is not None and ief_c is not None and tip_d and ief_d and tip_d == ief_d:
        tip_ief_ratio = tip_c / ief_c
        tip_ratio_date = tip_d
    else:
        tip_ratio_notes = "date_mismatch_or_na"
    add("TIP_IEF_RATIO", tip_ratio_date, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # OFR FSI — explicitly degradable (v3)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # upsert into history
    for p in points:
        # avoid polluting history with NA dates
        if p.data_date and p.data_date != "NA":
            hist = upsert_history(hist, p)

    # write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)


if __name__ == "__main__":
    main()