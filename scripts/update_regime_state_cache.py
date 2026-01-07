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

# v3.1: minimal necessary fixes
SCRIPT_VERSION = "regime_state_cache_v3_1"
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

def http_get_json(url: str, timeout: int = 25) -> Tuple[Optional[dict], Optional[str]]:
    text, err = http_get(url, timeout=timeout)
    if err:
        return None, err
    try:
        return json.loads(text), None
    except Exception:
        return None, "json_parse_fail"

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
# Treasury CSV URLs (source-of-truth endpoints)
# -------------------------
def treasury_csv_url(kind: str, yyyymm: str) -> str:
    """
    Use Treasury "all/{YYYYMM}?_format=csv..." endpoints (more stable than TextView HTML).
    """
    base = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    if kind == "nominal":
        return (
            f"{base}daily-treasury-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_yield_curve"
        )
    if kind == "real":
        return (
            f"{base}daily-treasury-real-yield-curve-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_real_yield_curve"
        )
    raise ValueError("unknown kind")

def yyyymm_candidates(n_months: int = 3) -> List[str]:
    """
    v3.1: try current + previous 2 months to handle month boundary / delayed posting.
    """
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

def _normalize_key(k: str) -> str:
    return (k or "").strip().lower().replace("\ufeff", "")

def parse_latest_10y_from_treasury_csv(csv_text: str) -> Tuple[Optional[str], Optional[float], str, Optional[str]]:
    """
    v3.1: robust parse
    - Accept Treasury CSV
    - Find the 10Y column name (nominal/real CSV differs)
    - Scan from last row backwards to find first numeric 10Y value
    Returns (data_date, value_10y, notes, used_col_name)
    """
    try:
        reader = csv.DictReader(csv_text.splitlines())
        rows = [r for r in reader if isinstance(r, dict) and r]
    except Exception:
        return None, None, "csv_parse_fail", None

    if not rows:
        return None, None, "empty_csv", None

    # Determine date key
    # Treasury uses "Date" typically; be tolerant
    sample_keys = list(rows[0].keys() or [])
    date_key = None
    for k in sample_keys:
        kk = _normalize_key(k)
        if kk in ("date",):
            date_key = k
            break
    if date_key is None:
        # fallback: pick first key that looks like date
        for k in sample_keys:
            kk = _normalize_key(k)
            if "date" in kk:
                date_key = k
                break

    # Identify 10Y column
    # Nominal often has "10 Yr"; Real often has "10 Yr"
    col_10y = None
    key_map = { _normalize_key(k): k for k in (sample_keys or []) }

    # Preferred exact matches
    preferred = ["10 yr", "10 yr.", "10 yr ", "10 year", "10-year", "10 yr treasury", "10 year treasury"]
    for p in preferred:
        if p in key_map:
            col_10y = key_map[p]
            break

    # Treasury CSV commonly: "10 Yr"
    if col_10y is None:
        for k in sample_keys:
            kk = _normalize_key(k)
            if kk in ("10 yr", "10yr", "10 yr "):
                col_10y = k
                break

    # Fuzzy: contains 10 and (yr/year)
    if col_10y is None:
        for k in sample_keys:
            kk = _normalize_key(k)
            if ("10" in kk) and (("yr" in kk) or ("year" in kk)):
                col_10y = k
                break

    if col_10y is None:
        # Provide last row date if possible
        last_date = None
        if date_key:
            last_date = (rows[-1].get(date_key) or "").strip() or None
        return last_date, None, "missing_10y_column", None

    # Scan backwards for first numeric 10Y
    for r in reversed(rows):
        d = None
        if date_key:
            d = (r.get(date_key) or "").strip() or None
        v = safe_float(r.get(col_10y))
        if d and (v is not None):
            return d, v, "NA", col_10y

    # If we never found numeric 10Y, return the last date to aid debugging
    last_date = None
    if date_key:
        last_date = (rows[-1].get(date_key) or "").strip() or None
    return last_date, None, "no_numeric_10y_found", col_10y

# -------------------------
# Stooq (fallback / proxies)
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 14) -> Tuple[Optional[str], Optional[float], str, str]:
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err = http_get(url)
    if err:
        return None, None, err, url

    try:
        reader = csv.DictReader(text.splitlines())
        rows = [r for r in reader if r]
    except Exception:
        return None, None, "csv_parse_fail", url

    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    date = (last.get("Date") or "").strip() or None
    close = safe_float(last.get("Close"))
    if close is None:
        return date, None, "na_or_parse_fail", url

    return date, close, "NA", url

# -------------------------
# VIX primary: CBOE daily prices (JSON)
# fallback: Stooq
# -------------------------
def vix_latest_primary_then_fallback() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    Primary: CBOE daily_prices endpoint (JSON). This is more stable than scraping.
    Fallback: Stooq vix daily close.
    """
    primary_url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.json"
    obj, err = http_get_json(primary_url, timeout=25)
    if not err and isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, list) and data:
            # find last row with numeric close
            # row schema often: [ "YYYY-MM-DD", open, high, low, close ]
            for row in reversed(data):
                if not isinstance(row, list) or len(row) < 5:
                    continue
                d = str(row[0]).strip()
                close = safe_float(row[4])
                if d and close is not None:
                    return d, close, "NA", primary_url
            # If no numeric close in tail
            return None, None, "cboe_no_numeric_close", primary_url

    # Primary failed -> fallback Stooq
    d, c, n, u = stooq_daily_close("vix", 21)
    if c is not None and d:
        # record that we used fallback
        return d, c, "fallback_stooq", u
    # Both failed
    return None, None, f"cboe_{err or 'unknown'};stooq_{n}", primary_url

# -------------------------
# OFR FSI (explicitly degradable)
# -------------------------
def _extract_candidate_links(html: str) -> List[str]:
    """
    Multi-strategy link extraction:
    - direct csv/zip links
    - links containing key tokens (fsi/stress/download/data) even if not csv
    """
    if not html:
        return []

    # 1) Direct csv/zip
    direct = re.findall(r"https?://[^\"'\s>]+?\.(?:csv|zip)(?:\?[^\"'\s>]*)?", html, flags=re.IGNORECASE)

    # 2) Any link href, later filter by keywords
    hrefs = re.findall(r'href=["\'](https?://[^"\']+)["\']', html, flags=re.IGNORECASE)

    # Normalize and combine
    links = []
    seen = set()
    for u in direct + hrefs:
        if not u:
            continue
        uu = u.strip()
        if uu in seen:
            continue
        seen.add(uu)
        links.append(uu)

    # Rank candidates: prefer ones with fsi/stress and csv
    def score(u: str) -> int:
        ul = u.lower()
        s = 0
        if ul.endswith(".csv") or ".csv?" in ul:
            s += 50
        if ul.endswith(".zip") or ".zip?" in ul:
            s += 20
        if "fsi" in ul:
            s += 20
        if "stress" in ul:
            s += 15
        if "download" in ul:
            s += 10
        if "data" in ul:
            s += 5
        return s

    links.sort(key=score, reverse=True)
    return links

def ofr_fsi_latest_degradable() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    v3.1: explicitly degradable.
    - Try to locate a usable CSV/ZIP link via multiple heuristics
    - If only ZIP found, mark as zip_not_supported_in_v3_1 (still degradable)
    - If no usable link, return NA with reason
    """
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    html, err = http_get(page_url, timeout=25)
    if err:
        return None, None, f"page_{err}", page_url

    links = _extract_candidate_links(html)
    if not links:
        return None, None, "data_link_not_found_in_html", page_url

    # Try best candidates that are csv or zip first
    tried = 0
    last_err = None
    for u in links:
        ul = u.lower()
        if not (ul.endswith(".csv") or ".csv?" in ul or ul.endswith(".zip") or ".zip?" in ul):
            # Skip non-data links in v3.1 (keep degradable)
            continue
        tried += 1
        if tried > 6:
            break

        if ul.endswith(".zip") or ".zip?" in ul:
            # Not supported but explicitly degradable
            return None, None, "zip_not_supported_in_v3_1", u

        content, err2 = http_get(u, timeout=25)
        if err2:
            last_err = f"data_{err2}"
            continue

        try:
            reader = csv.DictReader(content.splitlines())
            rows = [r for r in reader if r]
        except Exception:
            last_err = "csv_parse_fail"
            continue

        if not rows:
            last_err = "empty_csv"
            continue

        # Find last row with a numeric value
        # Try to detect date key and value key
        keys = list(rows[0].keys() or [])
        date_key = None
        for k in keys:
            kk = _normalize_key(k)
            if kk == "date" or "date" in kk:
                date_key = k
                break

        # Determine value key preference
        # Some OFR csv might have column names like "OFR FSI", "FSI", etc.
        def pick_value_from_row(r: Dict[str, str]) -> Optional[float]:
            # Preferred by column name
            for k in keys:
                kk = _normalize_key(k)
                if ("fsi" in kk) or ("stress" in kk) or ("index" in kk):
                    vv = safe_float(r.get(k))
                    if vv is not None:
                        return vv
            # Fallback: first numeric field
            for k in keys:
                vv = safe_float(r.get(k))
                if vv is not None:
                    return vv
            return None

        for r in reversed(rows):
            d = None
            if date_key:
                d = (r.get(date_key) or "").strip() or None
            v = pick_value_from_row(r)
            if v is not None:
                # If date missing, still return v with NA date (degradable)
                return (d or "NA"), v, "NA" if d else "missing_date_in_csv", u

        last_err = "no_numeric_value_found"

    if last_err:
        return None, None, f"data_link_unusable:{last_err}", page_url

    # We had links, but none were csv/zip
    return None, None, "no_csv_or_zip_links_found", page_url

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
    for i, r in enumerate(latest[:100]):  # sample first 100
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
                # IMPORTANT: keep manifest_json pointing to branch latest (stable link) as you finalized
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
            # keep NA rows in latest.json, but make reason explicit
            points.append(Point(as_of, series_id, data_date or "NA", "NA", source_url or "NA", notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, data_date, f"{value}", source_url or "NA", notes))

    # -------------------------
    # Treasury 10Y nominal & real (CSV endpoints only; robust backward scan)
    # -------------------------
    nom_date = real_date = None
    nom10 = real10 = None
    nom_notes = real_notes = "NA"
    nom_url_used = real_url_used = "NA"

    # nominal
    for yyyymm in yyyymm_candidates(3):
        url = treasury_csv_url("nominal", yyyymm)
        text, err = http_get(url, timeout=25)
        if err:
            nom_notes, nom_url_used = err, url
            continue
        d, v, notes, used_col = parse_latest_10y_from_treasury_csv(text)
        nom_notes, nom_url_used = notes, url
        if d and v is not None:
            nom_date, nom10 = d, v
            break

    # real
    for yyyymm in yyyymm_candidates(3):
        url = treasury_csv_url("real", yyyymm)
        text, err = http_get(url, timeout=25)
        if err:
            real_notes, real_url_used = err, url
            continue
        d, v, notes, used_col = parse_latest_10y_from_treasury_csv(text)
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
    be_source = "NA"
    if nom10 is not None and real10 is not None and nom_date and real_date and nom_date == real_date:
        be10 = nom10 - real10
        be_date = nom_date
        be_source = f"{nom_url_used} + {real_url_used}"
    else:
        be_notes = "date_mismatch_or_na"
        be_source = f"{nom_url_used} + {real_url_used}".strip()
    add("BE10Y_PROXY", be_date, be10, be_source, be_notes)

    # -------------------------
    # VIX (primary CBOE JSON; fallback Stooq)
    # -------------------------
    vix_date, vix_close, vix_notes, vix_url = vix_latest_primary_then_fallback()
    add("VIX_PROXY", vix_date, vix_close, vix_url, vix_notes)

    # -------------------------
    # Credit proxies: HYG/IEF and TIP/IEF (Stooq)
    # -------------------------
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 21)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 21)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 21)

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

    # -------------------------
    # OFR FSI (explicitly degradable; best-effort)
    # -------------------------
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest_degradable()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # upsert into history (avoid polluting history with NA dates)
    for p in points:
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)


if __name__ == "__main__":
    main()