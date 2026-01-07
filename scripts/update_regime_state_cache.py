import argparse
import csv
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict
from urllib.parse import urljoin

import requests

# -------------------------
# Paths / Outputs
# -------------------------
DEFAULT_OUT_DIR = "regime_state_cache"
LATEST_JSON_NAME = "latest.json"
LATEST_CSV_NAME = "latest.csv"
HISTORY_JSON_NAME = "history.json"
MANIFEST_JSON_NAME = "manifest.json"

SCRIPT_VERSION = "regime_state_cache_v1"
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
def http_get_text(url: str, timeout: int = 20) -> Tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": f"{SCRIPT_VERSION}/1.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        # requests will guess encoding; for CSV/html it is fine
        return r.text, None
    except requests.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, f"exception:{type(e).__name__}"


def http_get_bytes(url: str, timeout: int = 30) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": f"{SCRIPT_VERSION}/1.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.content, None
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
# Treasury CSV URLs (source-of-truth endpoints)
# -------------------------
def treasury_csv_url(kind: str, yyyymm: str) -> str:
    """
    Minimal fix:
    - real curve endpoint on Treasury is commonly "par real yield curve rates"
      (slug includes 'par-real-...'), not the previous 'real-yield-curve-rates'.
    - nominal kept as-is for minimal change.
    """
    if kind == "nominal":
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"daily-treasury-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_yield_curve"
        )
    if kind == "real":
        # FIX #1: use Par Real Yield Curve endpoint slug
        return (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"daily-treasury-par-real-yield-curve-rates.csv/all/{yyyymm}"
            f"?_format=csv&field_tdr_date_value_month={yyyymm}&type=daily_treasury_par_real_yield_curve"
        )
    raise ValueError("unknown kind")


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
    Returns (data_date, value_10y, notes, used_col_name)
    """
    reader = csv.DictReader(csv_text.splitlines())
    rows = [r for r in reader if r and any((v or "").strip() for v in r.values() if isinstance(v, str))]
    if not rows:
        return None, None, "empty_csv", None

    last = rows[-1]
    date = (last.get("Date") or last.get("date") or last.get("DATE") or "").strip() or None

    # Try common 10Y column names
    candidates = [
        "10 Yr",
        "10 yr",
        "10 Year",
        "10 year",
        "10-year",
        "10-Year",
        "10 YR",
        "10YR",
        "10 yr.",
        "10 Yr.",
    ]
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
            if ("10" in kk or "10y" in kk) and ("yr" in kk or "year" in kk):
                col = k
                break

    if col is None:
        return date, None, "missing_10y_column", None

    val = safe_float(last.get(col))
    if val is None:
        return date, None, "na_or_parse_fail", col

    return date, val, "NA", col


# -------------------------
# Stooq (ETF/Proxy)
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 14) -> Tuple[Optional[str], Optional[float], str, str]:
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err = http_get_text(url)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    date = (last.get("Date") or "").strip() or None
    close = safe_float(last.get("Close"))
    if close is None:
        return date, None, "na_or_parse_fail", url

    return date, close, "NA", url


# -------------------------
# VIX (more robust than Stooq 'vix' symbol)
# -------------------------
def vix_cboe_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    FIX #2: replace fragile Stooq 'vix' lookup with a stable CBOE CSV endpoint.
    We only need the latest row (Date + VIX Close).
    """
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get_text(url, timeout=30)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    # Typical columns: DATE, OPEN, HIGH, LOW, CLOSE
    date = (last.get("DATE") or last.get("Date") or "").strip() or None
    close = safe_float(last.get("CLOSE") or last.get("Close") or last.get("close"))
    if close is None:
        return date, None, "na_or_parse_fail", url

    return date, close, "NA", url


# -------------------------
# OFR FSI (robust link handling + ZIP support)
# -------------------------
def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    """
    FIX #3: handle relative links and ZIP payloads.
    Strategy:
      - Fetch OFR FSI page HTML.
      - Extract href/src links that end with .csv or .zip (relative or absolute).
      - urljoin() to absolute.
      - Prefer links containing 'fsi' or 'stress' keywords.
      - If zip: download bytes, extract first CSV, parse.
      - Parse last row, pick a numeric column that looks like FSI/stress/index; else first numeric.
    """
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    html, err = http_get_text(page_url)
    if err:
        return None, None, f"page_{err}", page_url

    # Collect candidate file links from href/src attributes (relative OR absolute)
    # Example patterns: href="/path/file.csv", href="https://.../file.zip"
    raw_links = re.findall(r"""(?:href|src)\s*=\s*["']([^"']+\.(?:csv|zip)(?:\?[^"']*)?)["']""", html, flags=re.IGNORECASE)
    if not raw_links:
        # Fallback: any visible absolute link ending in csv/zip
        raw_links = re.findall(r"https?://[^\"']+\.(?:csv|zip)(?:\?[^\"']*)?", html, flags=re.IGNORECASE)

    links_abs = [urljoin(page_url, u) for u in raw_links]
    # De-dup while preserving order
    seen = set()
    links_abs = [u for u in links_abs if not (u in seen or seen.add(u))]

    if not links_abs:
        return None, None, "data_link_not_found_in_html", page_url

    # Prefer more likely data links
    preferred = []
    others = []
    for u in links_abs:
        lu = u.lower()
        if "fsi" in lu or "stress" in lu or "financial-stress" in lu:
            preferred.append(u)
        else:
            others.append(u)
    candidates = preferred + others

    # Try candidates in order until success
    last_err = "unknown"
    last_url = candidates[0]
    for data_url in candidates[:5]:  # keep minimal attempts
        last_url = data_url
        if data_url.lower().endswith(".zip") or ".zip?" in data_url.lower():
            b, errb = http_get_bytes(data_url, timeout=40)
            if errb:
                last_err = f"data_{errb}"
                continue
            try:
                zf = zipfile.ZipFile(io.BytesIO(b))
                # pick first csv inside
                csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    last_err = "zip_no_csv"
                    continue
                content = zf.read(csv_names[0]).decode("utf-8", errors="replace")
            except Exception as e:
                last_err = f"zip_parse_fail:{type(e).__name__}"
                continue
        else:
            content, err2 = http_get_text(data_url, timeout=30)
            if err2:
                last_err = f"data_{err2}"
                continue

        reader = csv.DictReader(content.splitlines())
        rows = [r for r in reader if r]
        if not rows:
            last_err = "empty_csv"
            continue

        last = rows[-1]
        date = (last.get("Date") or last.get("date") or last.get("DATE") or "").strip() or None

        val = None
        # Prefer column names hinting stress index
        for k, v in last.items():
            if not k:
                continue
            kk = k.lower()
            if ("fsi" in kk) or ("stress" in kk) or ("index" in kk):
                vv = safe_float(v)
                if vv is not None:
                    val = vv
                    break
        # Fallback: first numeric cell
        if val is None:
            for _, v in last.items():
                vv = safe_float(v)
                if vv is not None:
                    val = vv
                    break

        if val is None:
            last_err = "parse_fail"
            continue

        return date, val, "NA", data_url

    return None, None, last_err, last_url


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
            w.writerow(
                {
                    "as_of_ts": p.as_of_ts,
                    "series_id": p.series_id,
                    "data_date": p.data_date,
                    "value": p.value,
                    "source_url": p.source_url,
                    "notes": p.notes,
                }
            )


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
                "manifest_json": f"https://raw.githubusercontent.com/Joseph-Chou911/fred-cache/{data_sha}/{out_dir}/{MANIFEST_JSON_NAME}",
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
            points.append(
                Point(
                    as_of,
                    series_id,
                    data_date or "NA",
                    "NA",
                    source_url,
                    notes if notes != "NA" else "missing",
                )
            )
        else:
            points.append(Point(as_of, series_id, data_date, f"{value}", source_url, notes))

    # Treasury 10Y nominal & real (try current + previous month)
    nom_date = real_date = None
    nom10 = real10 = None
    nom_notes = real_notes = "NA"
    nom_url_used = real_url_used = ""

    for yyyymm in yyyymm_candidates(2):
        url = treasury_csv_url("nominal", yyyymm)
        text, err = http_get_text(url)
        if err:
            nom_notes, nom_url_used = err, url
            continue
        d, v, notes, _ = parse_latest_yield_from_treasury(text)
        nom_notes, nom_url_used = notes, url
        if d and v is not None:
            nom_date, nom10 = d, v
            break

    for yyyymm in yyyymm_candidates(2):
        url = treasury_csv_url("real", yyyymm)
        text, err = http_get_text(url)
        if err:
            real_notes, real_url_used = err, url
            continue
        d, v, notes, _ = parse_latest_yield_from_treasury(text)
        real_notes, real_url_used = notes, url
        if d and v is not None:
            real_date, real10 = d, v
            break

    add("NOMINAL_10Y", nom_date, nom10, nom_url_used or "NA", nom_notes)
    add("REAL_10Y", real_date, real10, real_url_used or "NA", real_notes)

    # Breakeven proxy (only if same date)
    be10 = None
    be_date = None
    be_notes = "NA"
    if nom10 is not None and real10 is not None and nom_date and real_date and nom_date == real_date:
        be10 = nom10 - real10
        be_date = nom_date
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url_used} + {real_url_used}".strip(), be_notes)

    # VIX from CBOE (more reliable)
    vix_date, vix_close, vix_notes, vix_url = vix_cboe_latest()
    add("VIX_PROXY", vix_date, vix_close, vix_url, vix_notes)

    # Credit proxies: HYG/IEF and TIP/IEF (Stooq)
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

    # OFR FSI (robust)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # upsert into history
    for p in points:
        if p.data_date != "NA":  # keep NA rows in latest, but avoid polluting history with NA dates
            hist = upsert_history(hist, p)

    # write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)


if __name__ == "__main__":
    main()