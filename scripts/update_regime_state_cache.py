import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Tuple, Dict, Any

import requests

# -------------------------
# Outputs / Names
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
    # Runner TZ is set in workflow; this produces explicit offset like +08:00
    return datetime.now().astimezone().isoformat()

def local_today_str() -> str:
    return datetime.now().astimezone().date().isoformat()

def parse_iso_dt(s: str) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    ss = s.strip()
    if not ss:
        return None
    try:
        # handle trailing Z
        if ss.endswith("Z"):
            ss = ss[:-1] + "+00:00"
        return datetime.fromisoformat(ss)
    except Exception:
        return None

def normalize_date(s: Any) -> str:
    """
    Normalize date strings into 'YYYY-MM-DD'. If cannot parse -> 'NA'.
    Handles:
      - YYYY-MM-DD
      - YYYY-MM-DDTHH:MM:SS
      - YYYY-MM-DDTHH:MM:SS+08:00
      - MM/DD/YYYY
      - '2026-01-06T00:00:00'
      - '01/06/2026'
    """
    if s is None:
        return "NA"
    if isinstance(s, (date, datetime)):
        return s.date().isoformat() if isinstance(s, datetime) else s.isoformat()
    ss = str(s).strip()
    if not ss or ss.upper() == "NA":
        return "NA"

    # ISO date at front
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", ss)
    if m:
        return m.group(1)

    # US style
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(ss, fmt)
            return dt.date().isoformat()
        except Exception:
            pass

    # Try ISO datetime parse
    dt = parse_iso_dt(ss)
    if dt:
        return dt.date().isoformat()

    return "NA"

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
# Treasury (XML endpoint that contains an HTML table)
# -------------------------
def treasury_xml_url(data_kind: str, yyyymm: str) -> str:
    # data_kind:
    #  - daily_treasury_yield_curve
    #  - daily_treasury_real_yield_curve
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data={data_kind}&field_tdr_date_value_month={yyyymm}"
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

def _strip_tags(html: str) -> str:
    # crude tag stripper; enough for treasury table cells
    txt = re.sub(r"<[^>]+>", "", html)
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&")
    return txt.strip()

def _extract_html_table_rows(blob: str) -> List[List[str]]:
    """
    Try to extract rows from an HTML table.
    Returns list of rows, each row is list of cell strings.
    """
    rows: List[List[str]] = []
    # Find <tr>...</tr>
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", blob, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        row = [_strip_tags(c) for c in cells]
        # remove empty rows
        if any(c.strip() for c in row):
            rows.append(row)
    return rows

def parse_treasury_xml_table_to_series(xml_text: str) -> Tuple[Dict[str, float], str]:
    """
    Parse Treasury XML page and return:
      - mapping {YYYY-MM-DD: value_10y}
      - notes
    Strategy:
      - look for an embedded HTML table and parse it.
      - identify 10Y column by header cell containing '10' and ('yr' or 'year').
      - identify date column by header 'date' or by cell that looks like a date.
    """
    # Some pages embed HTML in CDATA; we just search for <table
    if "<table" not in xml_text.lower():
        return {}, "no_table_found"

    # take first table section (best effort)
    m = re.search(r"(<table[^>]*>.*?</table>)", xml_text, flags=re.IGNORECASE | re.DOTALL)
    table_html = m.group(1) if m else xml_text

    rows = _extract_html_table_rows(table_html)
    if len(rows) < 2:
        return {}, "table_rows_insufficient"

    header = rows[0]
    # find date col
    date_idx = None
    for i, h in enumerate(header):
        if "date" in h.lower():
            date_idx = i
            break
    if date_idx is None:
        date_idx = 0  # fallback

    # find 10y col
    ten_idx = None
    for i, h in enumerate(header):
        hl = h.lower()
        if "10" in hl and ("yr" in hl or "year" in hl):
            ten_idx = i
            break
    if ten_idx is None:
        # fuzzy: look for "bc_10year" rendered, etc.
        for i, h in enumerate(header):
            hl = h.lower().replace(" ", "")
            if "10year" in hl or "10yr" in hl:
                ten_idx = i
                break
    if ten_idx is None:
        return {}, "missing_10y_column"

    out: Dict[str, float] = {}
    for r in rows[1:]:
        if len(r) <= max(date_idx, ten_idx):
            continue
        d_raw = r[date_idx].strip()
        v_raw = r[ten_idx].strip()
        dd = normalize_date(d_raw)
        vv = safe_float(v_raw)
        if dd != "NA" and vv is not None:
            out[dd] = vv

    if not out:
        return {}, "no_parseable_points"
    return out, "NA"

def fetch_treasury_10y_from_xml(data_kind: str) -> Tuple[Optional[str], Optional[float], str, str, Dict[str, float]]:
    """
    Fetch current/previous month and parse full month table into mapping (date->10y).
    Return:
      (latest_date, latest_value, notes, source_url_used, series_map)
    """
    last_notes = "NA"
    last_url = "NA"
    last_map: Dict[str, float] = {}

    for yyyymm in yyyymm_candidates(2):
        url = treasury_xml_url(data_kind, yyyymm)
        xml_text, err = http_get(url)
        last_url = url
        if err:
            last_notes = err
            continue
        mp, notes = parse_treasury_xml_table_to_series(xml_text)
        last_notes = notes
        last_map = mp
        if mp:
            # pick latest date in this mapping
            latest_d = sorted(mp.keys())[-1]
            return latest_d, mp[latest_d], "NA", url, mp

    return None, None, last_notes, last_url, last_map

# -------------------------
# CBOE VIX CSV + Stooq fallback
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
    # CBOE CSV usually has "DATE" and "CLOSE" (or "VIX Close")
    d_raw = (last.get("DATE") or last.get("Date") or "").strip()
    dd = normalize_date(d_raw)
    close = None
    for k in ("CLOSE", "Close", "VIX Close", "VIX_Close"):
        if k in last:
            close = safe_float(last.get(k))
            break
    if close is None:
        # fallback: pick first numeric
        for _, v in last.items():
            vv = safe_float(v)
            if vv is not None:
                close = vv
                break
    if dd == "NA" or close is None:
        return None, None, "cboe_parse_fail", url

    return dd, close, "NA", url

def stooq_daily_series(symbol: str, lookback_days: int = 160) -> Tuple[List[Tuple[str, float]], str, str]:
    """
    Returns list of (YYYY-MM-DD, close), sorted ascending.
    """
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err = http_get(url)
    if err:
        return [], err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    out: List[Tuple[str, float]] = []
    for r in rows:
        d_raw = (r.get("Date") or "").strip()
        dd = normalize_date(d_raw)
        close = safe_float(r.get("Close"))
        if dd != "NA" and close is not None:
            out.append((dd, close))
    if not out:
        return [], "empty_csv", url
    out.sort(key=lambda x: x[0])
    return out, "NA", url

def stooq_daily_close(symbol: str, lookback_days: int = 14) -> Tuple[Optional[str], Optional[float], str, str]:
    series, notes, url = stooq_daily_series(symbol, lookback_days=max(lookback_days, 14))
    if not series:
        return None, None, notes, url
    d, v = series[-1]
    return d, v, "NA", url

def vix_latest_with_fallback() -> Tuple[Optional[str], Optional[float], str, str]:
    d, v, n, u = cboe_vix_latest()
    if d and v is not None:
        return d, v, "NA", u

    # fallback to stooq: try '^vix' then 'vix'
    for sym in ("^vix", "vix"):
        sd, sv, sn, su = stooq_daily_close(sym, 30)
        if sd and sv is not None:
            return sd, sv, f"{n};stooq_ok({sym})", su

    return None, None, f"{n};stooq_empty_csv", u

# -------------------------
# OFR FSI direct CSV
# -------------------------
def ofr_fsi_latest_from_csv() -> Tuple[Optional[str], Optional[float], str, str]:
    url = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"
    text, err = http_get(url)
    if err:
        return None, None, err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv", url

    last = rows[-1]
    # try common columns
    d_raw = (last.get("date") or last.get("Date") or last.get("DATE") or "").strip()
    dd = normalize_date(d_raw)

    # value column may be fsi, value, index, etc.
    val = None
    for k in last.keys():
        if not k:
            continue
        kl = k.lower().strip()
        if kl in ("fsi", "value", "index", "ofr_fsi"):
            val = safe_float(last.get(k))
            if val is not None:
                break
    if val is None:
        # fallback: first numeric column excluding date-like column
        for k, v in last.items():
            if k and "date" in k.lower():
                continue
            vv = safe_float(v)
            if vv is not None:
                val = vv
                break

    if dd == "NA" or val is None:
        return None, None, "parse_fail", url

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

def normalize_and_dedup_history(rows: List[dict]) -> List[dict]:
    """
    Normalize data_date to YYYY-MM-DD, then deduplicate by (series_id, data_date),
    keeping the latest as_of_ts.
    """
    best: Dict[Tuple[str, str], dict] = {}

    def ts_key(r: dict) -> datetime:
        dt = parse_iso_dt(str(r.get("as_of_ts") or ""))
        return dt if dt else datetime(1970, 1, 1, tzinfo=timezone.utc)

    for r in rows:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id") or "").strip()
        if not sid:
            continue
        dd = normalize_date(r.get("data_date"))
        r2 = dict(r)
        r2["data_date"] = dd

        key = (sid, dd)
        if key not in best:
            best[key] = r2
        else:
            if ts_key(r2) >= ts_key(best[key]):
                best[key] = r2

    out = list(best.values())
    # stable sort for readability
    out.sort(key=lambda x: (str(x.get("data_date") or "9999-99-99"), str(x.get("series_id") or "")))
    # clamp length
    if len(out) > MAX_HISTORY_ROWS:
        out = out[-MAX_HISTORY_ROWS:]
    return out

def upsert_history(hist: List[dict], p: Point) -> List[dict]:
    """
    Unique by (series_id, data_date). data_date must already be normalized.
    Keep the latest by as_of_ts.
    """
    key = (p.series_id, p.data_date)
    p_dt = parse_iso_dt(p.as_of_ts) or datetime(1970, 1, 1, tzinfo=timezone.utc)

    # build index map (small enough; but keep O(n) simple)
    for i in range(len(hist) - 1, -1, -1):
        r = hist[i]
        if r.get("series_id") == key[0] and r.get("data_date") == key[1]:
            old_dt = parse_iso_dt(str(r.get("as_of_ts") or "")) or datetime(1970, 1, 1, tzinfo=timezone.utc)
            if p_dt >= old_dt:
                hist[i] = p.__dict__
            return hist

    hist.append(p.__dict__)
    if len(hist) > MAX_HISTORY_ROWS:
        hist = hist[-MAX_HISTORY_ROWS:]
    return hist

# -------------------------
# Credit axis: MA60 deviation for HYG/IEF ratio (computed from Stooq series)
# -------------------------
def compute_ratio_ma60_deviation(hyg_sym: str = "hyg.us", ief_sym: str = "ief.us", lookback_days: int = 200) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float], str]:
    """
    Returns:
      (date_used, ratio_today, ma60, dev, notes)
    dev = ratio_today / ma60 - 1
    """
    hyg_series, hyg_notes, _ = stooq_daily_series(hyg_sym, lookback_days=lookback_days)
    ief_series, ief_notes, _ = stooq_daily_series(ief_sym, lookback_days=lookback_days)

    if not hyg_series or not ief_series:
        return None, None, None, None, f"stooq_series_missing(hyg={hyg_notes},ief={ief_notes})"

    # align by date
    hyg_map = {d: v for d, v in hyg_series}
    ief_map = {d: v for d, v in ief_series}
    common_dates = sorted(set(hyg_map.keys()) & set(ief_map.keys()))
    if len(common_dates) < 60:
        return None, None, None, None, f"stooq_common_lt_60({len(common_dates)})"

    # ratio series
    ratio_series: List[Tuple[str, float]] = []
    for d in common_dates:
        if ief_map[d] == 0:
            continue
        ratio_series.append((d, hyg_map[d] / ief_map[d]))

    if len(ratio_series) < 60:
        return None, None, None, None, f"ratio_series_lt_60({len(ratio_series)})"

    # latest
    date_used, ratio_today = ratio_series[-1]
    last60 = [v for _, v in ratio_series[-60:]]
    ma60 = sum(last60) / 60.0
    if ma60 == 0:
        return date_used, ratio_today, None, None, "ma60_zero"
    dev = ratio_today / ma60 - 1.0
    return date_used, ratio_today, ma60, dev, "NA"

# -------------------------
# Regime classification (outputs regime_state + confidence + reasons[])
# -------------------------
def classify_regime(
    vix: Optional[float],
    be10y: Optional[float],
    credit_dev: Optional[float],
    ofr_fsi: Optional[float],
    ofr_ok: bool,
    force_confidence_cap_low_if_credit_missing: bool = True,
) -> Tuple[str, str, List[str]]:
    reasons: List[str] = []

    # ---- panic axis ----
    panic_level = "NA"
    if vix is None:
        reasons.append("panic=NA(VIX=NA)")
    else:
        if vix <= 18:
            panic_level = "LOW"
        elif vix <= 25:
            panic_level = "MID"
        else:
            panic_level = "HIGH"
        reasons.append(f"panic={panic_level}(VIX={vix})")

    # ---- inflation expectation axis ----
    infl_level = "NA"
    if be10y is None:
        reasons.append("inflation_expect=NA(BE10Y=NA)")
    else:
        if be10y <= 1.5:
            infl_level = "LOW"
        elif be10y <= 2.75:
            infl_level = "MID"
        else:
            infl_level = "HIGH"
        reasons.append(f"inflation_expect={infl_level}(BE10Y={be10y})")

    # ---- credit axis (MA60 deviation) ----
    credit_level = "NA"
    if credit_dev is None:
        reasons.append("credit_dev=NA")
    else:
        # user-specified: MA60 deviation threshold ±1%
        if credit_dev <= -0.01:
            credit_level = "RISK_OFF"
        elif credit_dev >= 0.01:
            credit_level = "RISK_ON"
        else:
            credit_level = "NEUTRAL"
        reasons.append(f"credit_dev={credit_level}({credit_dev:+.2%})")

    # ---- optional OFR ----
    if ofr_ok and ofr_fsi is not None:
        reasons.append(f"OFR_FSI=OK({ofr_fsi})")
    else:
        # treat NA as normal degradation
        reasons.append("OFR_FSI=NA (optional; normal degradation)")

    # ---- regime decision (simple & auditable) ----
    # Keep conservative mapping: don't overclaim without credit axis.
    if panic_level == "HIGH" and credit_level == "RISK_OFF":
        regime = "RISK_OFF_STRESS"
    elif panic_level == "LOW" and credit_level == "RISK_ON" and infl_level in ("MID", "HIGH"):
        regime = "RISK_ON"
    else:
        regime = "NEUTRAL_MIXED"

    # ---- confidence ----
    core_available = 0
    if vix is not None:
        core_available += 1
    if be10y is not None:
        core_available += 1
    if credit_dev is not None:
        core_available += 1

    if core_available == 3:
        confidence = "HIGH"
    elif core_available == 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # cap rule: if credit missing => cap LOW
    if force_confidence_cap_low_if_credit_missing and credit_dev is None:
        if confidence != "LOW":
            reasons.append("confidence_cap=LOW(credit_unavailable)")
        confidence = "LOW"

    return regime, confidence, reasons

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
    for i, r in enumerate(latest[:80]):
        if not isinstance(r, dict):
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} not dict")
        missing = required - set(r.keys())
        if missing:
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} missing keys {sorted(list(missing))}")

    # history basic check (loadable)
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

    # load + normalize + dedup existing history (this is the key to avoid duplicates)
    hist_raw = load_json_list(history_path)
    hist = normalize_and_dedup_history(hist_raw)

    points: List[Point] = []

    def add(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str):
        dd = normalize_date(data_date)
        if dd == "NA" or value is None:
            points.append(Point(as_of, series_id, "NA" if dd == "NA" else dd, "NA", source_url, notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, dd, f"{value}", source_url, notes))

    # ---- Treasury 10Y nominal & real ----
    nom_d, nom_v, nom_notes, nom_url, nom_map = fetch_treasury_10y_from_xml("daily_treasury_yield_curve")
    real_d, real_v, real_notes, real_url, real_map = fetch_treasury_10y_from_xml("daily_treasury_real_yield_curve")

    add("NOMINAL_10Y", nom_d, nom_v, nom_url, nom_notes if nom_notes != "NA" else "NA")
    add("REAL_10Y", real_d, real_v, real_url, real_notes if real_notes != "NA" else "NA")

    # ---- BE10Y: choose latest common date within available month maps (more robust than strict latest==latest) ----
    be_d = None
    be_v = None
    be_notes = "NA"
    be_url = f"{nom_url} + {real_url}".strip()

    if nom_map and real_map:
        common = sorted(set(nom_map.keys()) & set(real_map.keys()))
        if common:
            be_d = common[-1]  # latest intersection date
            be_v = nom_map[be_d] - real_map[be_d]
        else:
            be_notes = "no_common_date_between_nominal_real"
    else:
        be_notes = "date_mismatch_or_na"

    add("BE10Y_PROXY", be_d, be_v, be_url, be_notes)

    # ---- VIX ----
    vix_d, vix_v, vix_notes, vix_url = vix_latest_with_fallback()
    add("VIX_PROXY", vix_d, vix_v, vix_url, vix_notes)

    # ---- Stooq closes (HYG/IEF/TIP) ----
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 120)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 120)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 120)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    # ratios (for storage / reporting; regime credit axis uses MA60 deviation computed from series)
    hyg_ief_ratio = None
    ratio_date = None
    ratio_notes = "NA"
    if hyg_c is not None and ief_c is not None and hyg_d and ief_d and normalize_date(hyg_d) == normalize_date(ief_d) and ief_c != 0:
        hyg_ief_ratio = hyg_c / ief_c
        ratio_date = normalize_date(hyg_d)
    else:
        ratio_notes = "date_mismatch_or_na"
    add("HYG_IEF_RATIO", ratio_date, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_date = None
    tip_ratio_notes = "NA"
    if tip_c is not None and ief_c is not None and tip_d and ief_d and normalize_date(tip_d) == normalize_date(ief_d) and ief_c != 0:
        tip_ief_ratio = tip_c / ief_c
        tip_ratio_date = normalize_date(tip_d)
    else:
        tip_ratio_notes = "date_mismatch_or_na"
    add("TIP_IEF_RATIO", tip_ratio_date, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # ---- OFR FSI (direct CSV, but optional) ----
    ofr_d, ofr_v, ofr_notes, ofr_url = ofr_fsi_latest_from_csv()
    if ofr_d and ofr_v is not None:
        add("OFR_FSI", ofr_d, ofr_v, ofr_url, ofr_notes)
        ofr_ok = True
    else:
        # keep field but mark as normal degradation; do not fail regime
        add("OFR_FSI", None, None, "https://www.financialresearch.gov/financial-stress-index/", "NA (optional; normal degradation)")
        ofr_ok = False

    # ---- Credit axis (MA60 deviation) ----
    credit_date, ratio_today, ma60, dev, credit_calc_notes = compute_ratio_ma60_deviation()
    # record internal diagnostic only via reasons; we don't add extra series_id to keep schema minimal

    # ---- Regime classification ----
    vix_val = vix_v
    be_val = be_v
    credit_dev = dev if (dev is not None and credit_calc_notes == "NA") else None

    regime, confidence, reasons = classify_regime(
        vix=vix_val,
        be10y=be_val,
        credit_dev=credit_dev,
        ofr_fsi=ofr_v,
        ofr_ok=ofr_ok,
        force_confidence_cap_low_if_credit_missing=True,
    )

    # If credit axis unavailable, expose why (auditable)
    if credit_dev is None:
        reasons.insert(2, f"credit_dev_unavailable({credit_calc_notes})")
    else:
        # include ma60 value for audit (no extra series id)
        reasons.insert(2, f"credit_ma60={ma60}")

    # add regime points (data_date should be today's local date)
    today = local_today_str()
    points.append(Point(as_of, "REGIME_STATE", today, regime, "NA", "NA"))
    points.append(Point(as_of, "REGIME_CONFIDENCE", today, confidence, "NA", "NA"))
    points.append(Point(as_of, "REGIME_REASONS", today, json.dumps(reasons, ensure_ascii=False), "NA", "NA"))

    # ---- Upsert into history ----
    # Only store non-NA dates in history to prevent pollution
    for p in points:
        p.data_date = normalize_date(p.data_date)
        if p.data_date != "NA":
            hist = upsert_history(hist, p)

    # Final normalize+dedup again (safety), then write
    hist = normalize_and_dedup_history(hist)

    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()