import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict

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

SCRIPT_VERSION = "regime_state_cache_v3_2"
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
# Date normalization (CRITICAL)
# -------------------------
_DATE_RE_YYYY_MM_DD = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_RE_MM_DD_YYYY = re.compile(r"^\d{2}/\d{2}/\d{4}$")

def normalize_date(s: Optional[str]) -> Optional[str]:
    """
    Normalize to 'YYYY-MM-DD'.
    Accepts:
      - YYYY-MM-DD
      - YYYY-MM-DDTHH:MM:SS (or with timezone)
      - MM/DD/YYYY
    Returns None if NA/empty/unparseable.
    """
    if s is None:
        return None
    ss = str(s).strip()
    if ss == "" or ss.upper() == "NA":
        return None

    # ISO datetime like 2026-01-06T00:00:00
    if "T" in ss and len(ss) >= 10:
        ss = ss[:10]

    if _DATE_RE_YYYY_MM_DD.match(ss):
        return ss

    if _DATE_RE_MM_DD_YYYY.match(ss):
        # MM/DD/YYYY -> YYYY-MM-DD
        mm = int(ss[0:2])
        dd = int(ss[3:5])
        yy = int(ss[6:10])
        return f"{yy:04d}-{mm:02d}-{dd:02d}"

    # Try a couple more common variants (defensive)
    # e.g. '2026/01/06'
    if re.match(r"^\d{4}/\d{2}/\d{2}$", ss):
        yy, mm, dd = ss.split("/")
        return f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}"

    return None

def parse_as_of_ts(ts: str) -> Optional[datetime]:
    """
    Parse as_of_ts which is isoformat with offset like 2026-01-07T19:47:02.185097+08:00
    """
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None

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
# Treasury (XML) endpoints (more stable than CSV in your case)
# -------------------------
def treasury_xml_url(data: str, yyyymm: str) -> str:
    # data:
    # - daily_treasury_yield_curve
    # - daily_treasury_real_yield_curve
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data={data}&field_tdr_date_value_month={yyyymm}"
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

def _xml_find_text(node: ET.Element, tag_suffix: str) -> Optional[str]:
    """
    Find first element whose tag endswith tag_suffix.
    """
    for el in node.iter():
        if el.tag.lower().endswith(tag_suffix.lower()):
            if el.text is not None:
                return el.text.strip()
    return None

def parse_latest_10y_from_treasury_xml(xml_text: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Returns (data_date_norm, value_10y, notes)
    Notes:
      - "xml_empty"
      - "xml_parse_fail"
      - "xml_parse_fail_10y"
      - "NA"
    """
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return None, None, "xml_parse_fail"

    # Treasury XML typically has repeating entries; we try to pick the last 'entry' with a date and 10y
    entries = [e for e in root.iter() if e.tag.lower().endswith("entry")]
    if not entries:
        return None, None, "xml_empty"

    # iterate from end to find a parseable one
    for ent in reversed(entries):
        # date is commonly in <d:NEW_DATE> or similar; we locate first YYYY-MM-DD-ish via text scan
        raw_date = _xml_find_text(ent, "NEW_DATE") or _xml_find_text(ent, "date")
        date_norm = normalize_date(raw_date)
        # 10y: for nominal: "BC_10YEAR"; for real: "TC_10YEAR"
        raw_10y = _xml_find_text(ent, "BC_10YEAR") or _xml_find_text(ent, "TC_10YEAR")
        v = safe_float(raw_10y)
        if date_norm and v is not None:
            return date_norm, v, "NA"

    # If we reach here, date or 10y missing
    return None, None, "xml_parse_fail_10y"

# -------------------------
# CBOE VIX (CSV) + Stooq fallback
# -------------------------
def cboe_vix_latest_csv() -> Tuple[Optional[str], Optional[float], str, str]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get(url)
    if err:
        return None, None, f"cboe_{err}", url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "cboe_empty_csv", url

    last = rows[-1]
    raw_date = (last.get("DATE") or last.get("Date") or last.get("date") or "").strip()
    date_norm = normalize_date(raw_date)
    # Column can be 'CLOSE' or 'Close'
    v = safe_float(last.get("CLOSE") or last.get("Close") or last.get("close"))
    if not date_norm or v is None:
        return date_norm, None, "cboe_parse_fail", url
    return date_norm, v, "NA", url

def stooq_daily_close(symbol: str, lookback_days: int = 90) -> Tuple[Optional[str], Optional[float], str, str]:
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
    raw_date = (last.get("Date") or "").strip()
    date_norm = normalize_date(raw_date)
    close = safe_float(last.get("Close"))
    if not date_norm or close is None:
        return date_norm, None, "na_or_parse_fail", url

    return date_norm, close, "NA", url

# -------------------------
# OFR FSI (intentionally best-effort; NA is normal degradation)
# -------------------------
def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str, str]:
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    html, err = http_get(page_url)
    if err:
        return None, None, f"page_{err}", page_url

    # Try to find public csv/zip links; if none, treat as expected degradation
    links = re.findall(r"https?://[^\"']+\.(?:csv|zip)", html, flags=re.IGNORECASE)
    if not links:
        return None, None, "NO_PUBLIC_CSV_LINK (ignored; normal degradation)", page_url

    # If we found links, still treat as optional; try first CSV
    data_url = None
    for u in links:
        if u.lower().endswith(".csv"):
            data_url = u
            break
    if not data_url:
        return None, None, "NO_CSV_LINK (ignored; normal degradation)", page_url

    content, err2 = http_get(data_url)
    if err2:
        return None, None, f"data_{err2} (ignored; normal degradation)", data_url

    reader = csv.DictReader(content.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "empty_csv (ignored; normal degradation)", data_url

    last = rows[-1]
    raw_date = (last.get("Date") or last.get("date") or "").strip()
    date_norm = normalize_date(raw_date)

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
        return date_norm, None, "parse_fail (ignored; normal degradation)", data_url

    return date_norm, val, "NA", data_url

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

def normalize_and_dedupe_history(hist: List[dict]) -> List[dict]:
    """
    - Normalize data_date into YYYY-MM-DD
    - Drop rows with unparseable/NA dates
    - Dedupe by (series_id, data_date) keeping latest as_of_ts (if parseable)
    """
    best: Dict[Tuple[str, str], dict] = {}

    for r in hist:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id") or "").strip()
        if not sid:
            continue

        dn = normalize_date(r.get("data_date"))
        if not dn:
            # Do not keep NA-dated rows in history
            continue

        r2 = dict(r)
        r2["data_date"] = dn

        key = (sid, dn)
        if key not in best:
            best[key] = r2
            continue

        # Keep the one with newer as_of_ts if possible
        t_old = parse_as_of_ts(str(best[key].get("as_of_ts") or ""))
        t_new = parse_as_of_ts(str(r2.get("as_of_ts") or ""))
        if t_old and t_new:
            if t_new > t_old:
                best[key] = r2
        else:
            # If can't parse, prefer existing (stable)
            pass

    out = list(best.values())

    # Sort by (series_id, data_date)
    out.sort(key=lambda x: (str(x.get("series_id")), str(x.get("data_date"))))

    # Cap length
    if len(out) > MAX_HISTORY_ROWS:
        out = out[-MAX_HISTORY_ROWS:]
    return out

def upsert_history(hist: List[dict], p: Point) -> List[dict]:
    """
    Unique by (series_id, data_date) after normalization.
    """
    dn = normalize_date(p.data_date)
    if not dn:
        return hist

    # overwrite p's date with normalized
    p = Point(
        as_of_ts=p.as_of_ts,
        series_id=p.series_id,
        data_date=dn,
        value=p.value,
        source_url=p.source_url,
        notes=p.notes,
    )

    key_sid = p.series_id
    key_date = p.data_date

    for i in range(len(hist) - 1, -1, -1):
        if str(hist[i].get("series_id")) == key_sid and normalize_date(hist[i].get("data_date")) == key_date:
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
    for i, r in enumerate(latest[:80]):
        if not isinstance(r, dict):
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} not dict")
        missing = required - set(r.keys())
        if missing:
            raise SystemExit(f"VALIDATE_DATA_FAIL: latest.json row {i} missing keys {sorted(list(missing))}")

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
def _latest_value(points: List[Point], series_id: str) -> Optional[float]:
    for p in points:
        if p.series_id == series_id:
            return safe_float(p.value)
    return None

def _latest_date(points: List[Point], series_id: str) -> Optional[str]:
    for p in points:
        if p.series_id == series_id:
            return normalize_date(p.data_date)
    return None

def _history_series(hist: List[dict], series_id: str) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for r in hist:
        if not isinstance(r, dict):
            continue
        if str(r.get("series_id")) != series_id:
            continue
        dn = normalize_date(r.get("data_date"))
        v = safe_float(r.get("value"))
        if dn and v is not None:
            out.append((dn, v))
    # sort by date
    out.sort(key=lambda x: x[0])
    # dedupe by date keep last
    ded: Dict[str, float] = {}
    for d, v in out:
        ded[d] = v
    out2 = sorted(ded.items(), key=lambda x: x[0])
    return out2

def classify_regime(points: List[Point], hist: List[dict]) -> Tuple[str, str, List[str]]:
    """
    Output:
      - regime_state (str)
      - confidence (LOW/MEDIUM/HIGH)
      - reasons (list[str])
    Rules (simple, auditable):
      Axes:
        Panic axis: VIX
          LOW  : VIX < 20
          MID  : 20 <= VIX < 30
          HIGH : VIX >= 30
        Inflation-expect axis: BE10Y_PROXY
          LOW  : BE < 1.5
          MID  : 1.5 <= BE <= 2.5
          HIGH : BE > 2.5
        Credit axis (MA60 deviation of HYG/IEF ratio):
          Need >=60 distinct daily points in history for HYG_IEF_RATIO.
          dev = (latest - MA60) / MA60
          TIER:
            STRESS (HIGH): dev <= -1%
            NEUTRAL (MID): -1% < dev < +1%
            EASING (LOW) : dev >= +1%
      confidence cap:
        - If credit axis unavailable => confidence MUST be LOW
        - OFR_FSI missing is normal degradation (no cap)
    """
    reasons: List[str] = []

    vix = _latest_value(points, "VIX_PROXY")
    be = _latest_value(points, "BE10Y_PROXY")

    # Panic axis
    panic = None
    if vix is None:
        reasons.append("core_missing=VIX_PROXY")
    else:
        if vix < 20:
            panic = "LOW"
        elif vix < 30:
            panic = "MID"
        else:
            panic = "HIGH"
        reasons.append(f"panic={panic}(VIX={vix})")

    # Inflation-expect axis
    infl = None
    if be is None:
        reasons.append("core_missing=BE10Y_PROXY")
    else:
        if be < 1.5:
            infl = "LOW"
        elif be <= 2.5:
            infl = "MID"
        else:
            infl = "HIGH"
        reasons.append(f"inflation_expect={infl}(BE10Y={be})")

    # Credit axis via MA60 deviation
    credit = None
    credit_dev = None
    series = _history_series(hist, "HYG_IEF_RATIO")
    if len(series) < 60:
        reasons.append(f"credit_dev_unavailable(history_lt_60({len(series)}))")
    else:
        # MA60 over last 60 points, using latest point date/value from series (more robust than latest file)
        last60 = series[-60:]
        vals = [v for _, v in last60]
        ma60 = sum(vals) / 60.0 if vals else None
        latest_ratio = series[-1][1] if series else None
        if ma60 is None or latest_ratio is None or ma60 == 0:
            reasons.append("credit_dev_unavailable(ma60_invalid)")
        else:
            credit_dev = (latest_ratio - ma60) / ma60
            # Tier by ±1%
            if credit_dev <= -0.01:
                credit = "HIGH_STRESS"
            elif credit_dev >= 0.01:
                credit = "LOW_EASING"
            else:
                credit = "MID_NEUTRAL"
            reasons.append(f"credit_dev={credit}({credit_dev:.4f}, MA60={ma60:.6f}, latest={latest_ratio:.6f})")

    # OFR optional
    ofr = _latest_value(points, "OFR_FSI")
    if ofr is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")

    # If core missing -> UNKNOWN
    if panic is None or infl is None:
        state = "UNKNOWN_INSUFFICIENT_DATA"
        # confidence is LOW by definition here
        confidence = "LOW"
        return state, confidence, reasons

    # Map to regime state (simple, conservative)
    # This mapping is intentionally restrained to avoid overfitting.
    if panic == "HIGH" and infl == "LOW":
        state = "CRISIS_DEFLATION_PANIC"
    elif infl == "HIGH" and panic != "HIGH":
        state = "OVERHEATING_INFLATION"
    elif infl == "LOW" and panic == "LOW":
        state = "DISINFLATION_SOFT"
    else:
        state = "NEUTRAL_MIXED"

    # Base confidence
    # Start from MEDIUM if both core present
    confidence = "MEDIUM"

    # If credit axis is available, we can slightly adjust confidence upward in stable regimes
    if credit is not None:
        # If credit is neutral and panic low => a bit more stable
        if state in ("DISINFLATION_SOFT", "NEUTRAL_MIXED") and panic == "LOW" and credit == "MID_NEUTRAL":
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"
    else:
        # CONFIDENCE CAP: without credit axis, do not allow > LOW
        confidence = "LOW"
        reasons.append("confidence_cap=LOW(credit_unavailable)")

    return state, confidence, reasons

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

    # Load and CLEAN history immediately (this is the key to stop duplication)
    hist_raw = load_json_list(history_path)
    hist = normalize_and_dedupe_history(hist_raw)

    points: List[Point] = []

    def add(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str):
        dn = normalize_date(data_date)
        if dn is None or value is None:
            points.append(Point(as_of, series_id, "NA", "NA", source_url, notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, dn, f"{value}", source_url, notes))

    # Treasury 10Y nominal & real via XML (try current + previous month)
    nom_date = real_date = None
    nom10 = real10 = None
    nom_notes = real_notes = "NA"
    nom_url_used = real_url_used = ""

    for yyyymm in yyyymm_candidates(2):
        url = treasury_xml_url("daily_treasury_yield_curve", yyyymm)
        text, err = http_get(url)
        if err:
            nom_notes, nom_url_used = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(text)
        nom_notes, nom_url_used = notes, url
        if d and v is not None:
            nom_date, nom10 = d, v
            break

    for yyyymm in yyyymm_candidates(2):
        url = treasury_xml_url("daily_treasury_real_yield_curve", yyyymm)
        text, err = http_get(url)
        if err:
            real_notes, real_url_used = err, url
            continue
        d, v, notes = parse_latest_10y_from_treasury_xml(text)
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
    if nom10 is not None and real10 is not None and nom_date and real_date:
        nd = normalize_date(nom_date)
        rd = normalize_date(real_date)
        if nd and rd and nd == rd:
            be10 = nom10 - real10
            be_date = nd
        else:
            be_notes = "date_mismatch_or_na"
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url_used} + {real_url_used}".strip(), be_notes)

    # VIX: CBOE CSV first, then stooq fallback
    vix_d, vix_v, vix_n, vix_u = cboe_vix_latest_csv()
    if vix_v is None:
        sd, sv, sn, su = stooq_daily_close("vix", 90)
        # If stooq also fails, keep cboe error + stooq error
        notes = f"{vix_n};stooq_{sn}"
        add("VIX_PROXY", sd, sv, su, notes)
    else:
        add("VIX_PROXY", vix_d, vix_v, vix_u, vix_n)

    # ETF closes via Stooq
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 90)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 90)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 90)

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

    # OFR FSI (optional)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest()
    if ofr_v is None:
        # Keep NA as normal degradation; do not poison confidence
        points.append(Point(as_of, "OFR_FSI", "NA", "NA", ofr_u, ofr_n))
    else:
        add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # Upsert into history (only NA-free dates)
    for p in points:
        dn = normalize_date(p.data_date)
        if dn is None:
            continue
        # do not store REGIME_* in history until after classification (we'll add them too)
        hist = upsert_history(hist, p)

    # Classify regime
    state, conf, reasons = classify_regime(points, hist)

    today = normalize_date(datetime.now().astimezone().strftime("%Y-%m-%d")) or "NA"
    points.append(Point(as_of, "REGIME_STATE", today, state, "NA", "NA"))
    points.append(Point(as_of, "REGIME_CONFIDENCE", today, conf, "NA", "NA"))
    points.append(Point(as_of, "REGIME_REASONS", today, json.dumps(reasons, ensure_ascii=False), "NA", "NA"))

    # Store REGIME_* into history too (same-day will overwrite by upsert)
    for p in points[-3:]:
        hist = upsert_history(hist, p)

    # Final write (history is already normalized + deduped)
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()