#!/usr/bin/env python3
# update_regime_state_cache.py
#
# v3.1 MINIMAL PATCH:
# - Credit axis: use HYG/IEF ratio deviation vs MA60; bootstrap fallback MA30/MA20 if insufficient history
# - Confidence cap: if credit axis uses MA<60 (bootstrap) => confidence cannot be HIGH (cap to MEDIUM)
# - Keep: OFR_FSI field but treat NA as normal degradation
# - Normalize date format to YYYY-MM-DD to avoid history duplicates
#
# NOTE: This file intentionally does NOT implement "nearest-week/month pairing" for BE10Y when REAL_10Y fails.

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
# Outputs
# -------------------------
DEFAULT_OUT_DIR = "regime_state_cache"
LATEST_JSON_NAME = "latest.json"
LATEST_CSV_NAME = "latest.csv"
HISTORY_JSON_NAME = "history.json"
MANIFEST_JSON_NAME = "manifest.json"

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

def to_yyyymm(dt: datetime) -> str:
    return f"{dt.year:04d}{dt.month:02d}"

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

def normalize_date_yyyy_mm_dd(s: Optional[str]) -> Optional[str]:
    """
    Normalize various date strings into YYYY-MM-DD.
    Accepts:
      - '2026-01-06'
      - '2026-01-06T00:00:00'
      - '01/02/2026'
      - '2026-01-06T00:00:00Z' (best effort)
    Returns None if cannot parse.
    """
    if not s:
        return None
    ss = str(s).strip()
    if ss == "" or ss.upper() == "NA":
        return None

    # strip time part
    if "T" in ss:
        ss = ss.split("T", 1)[0].strip()

    # YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", ss)
    if m:
        return ss

    # MM/DD/YYYY
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", ss)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(yy, mm, dd).strftime("%Y-%m-%d")
        except Exception:
            return None

    # YYYY/MM/DD
    m = re.match(r"^(\d{4})/(\d{2})/(\d{2})$", ss)
    if m:
        yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(yy, mm, dd).strftime("%Y-%m-%d")
        except Exception:
            return None

    return None

def today_local_yyyy_mm_dd() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")

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
# Treasury (XML endpoint)
# -------------------------
def treasury_xml_url(data_name: str, yyyymm: str) -> str:
    # Example:
    # https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=202601
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data={data_name}&field_tdr_date_value_month={yyyymm}"
    )

def _iter_row_dicts_from_treasury_xml(xml_text: str) -> List[Dict[str, str]]:
    """
    Treasury XML is a Drupal-ish export. We parse it generically:
    - Find all elements that look like <row> ... <field_name>value</field_name> ...
    - Build dict per row.
    """
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    rows: List[Dict[str, str]] = []

    # common possibilities: root contains <response><row>...
    # We'll treat any element named 'row' (case-insensitive, ignoring namespace) as a row container.
    def local_name(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    for el in root.iter():
        if local_name(el.tag).lower() == "row":
            d: Dict[str, str] = {}
            for child in list(el):
                k = local_name(child.tag)
                v = (child.text or "").strip()
                if k:
                    d[k] = v
            if d:
                rows.append(d)

    # Some exports use <item> instead of <row>
    if not rows:
        for el in root.iter():
            if local_name(el.tag).lower() in ("item", "record"):
                d = {}
                for child in list(el):
                    k = local_name(child.tag)
                    v = (child.text or "").strip()
                    if k:
                        d[k] = v
                if d:
                    rows.append(d)

    return rows

def parse_latest_10y_from_treasury_xml(xml_text: str) -> Tuple[Optional[str], Optional[float], str, Optional[str]]:
    """
    Returns (data_date_norm, value_10y, notes, used_key_name)
    - data_date_norm is YYYY-MM-DD
    """
    rows = _iter_row_dicts_from_treasury_xml(xml_text)
    if not rows:
        return None, None, "xml_no_rows", None

    # Find a date key candidate
    # Likely keys: 'NEW_DATE' / 'DATE' / 'Date' / 'record_date' / 'd:record_date' etc (namespace removed earlier)
    def pick_date(d: Dict[str, str]) -> Optional[str]:
        for k, v in d.items():
            kk = k.lower()
            if "date" in kk:
                nd = normalize_date_yyyy_mm_dd(v)
                if nd:
                    return nd
        # fallback: sometimes "YYYY-MM-DD 00:00:00"
        for v in d.values():
            nd = normalize_date_yyyy_mm_dd(v)
            if nd:
                return nd
        return None

    # Try to pick a 10Y key
    def pick_10y_key(d: Dict[str, str]) -> Optional[str]:
        # First pass: keys that contain 10 and (yr/year)
        for k in d.keys():
            kk = k.lower()
            if "10" in kk and ("yr" in kk or "year" in kk):
                return k
        # Second pass: common treasury patterns
        commons = [
            "BC_10YEAR", "bc_10year", "bc_10yr", "BC_10YR",
            "TEN_YEAR", "ten_year", "d:BC_10YEAR", "BC10YEAR",
        ]
        for c in commons:
            if c in d:
                return c
        return None

    # Use the last row that has parseable date and 10y
    # But some exports are not strictly sorted; we scan all, keep best by date max.
    best_date: Optional[str] = None
    best_val: Optional[float] = None
    best_key: Optional[str] = None

    for row in rows:
        dt = pick_date(row)
        if not dt:
            continue
        k10 = pick_10y_key(row)
        if not k10:
            continue
        val = safe_float(row.get(k10))
        if val is None:
            continue

        if best_date is None or dt > best_date:
            best_date = dt
            best_val = val
            best_key = k10

    if best_date is None or best_val is None:
        # more diagnostic: if we had rows but can't find 10y
        # detect if date exists but no 10y key
        any_date = any(normalize_date_yyyy_mm_dd(v) for r in rows for v in r.values())
        if any_date:
            return None, None, "xml_parse_fail_10y", None
        return None, None, "xml_parse_fail", None

    return best_date, best_val, "NA", best_key

# -------------------------
# CBOE VIX (primary) + Stooq fallback
# -------------------------
def vix_from_cboe_csv() -> Tuple[Optional[str], Optional[float], str, str]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get(url, timeout=25)
    if err:
        return None, None, f"cboe_{err}", url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, "cboe_empty_csv", url

    last = rows[-1]
    # Common columns: DATE, CLOSE
    d_raw = (last.get("DATE") or last.get("Date") or last.get("date") or "").strip()
    c_raw = (last.get("CLOSE") or last.get("Close") or last.get("close") or "").strip()

    d = normalize_date_yyyy_mm_dd(d_raw)
    v = safe_float(c_raw)
    if not d or v is None:
        return d, None, "cboe_parse_fail", url
    return d, v, "NA", url

# -------------------------
# Stooq daily CSV (fallback / proxies)
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 35) -> Tuple[Optional[str], Optional[float], str, str]:
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
    date_raw = (last.get("Date") or "").strip()
    close = safe_float(last.get("Close"))

    d = normalize_date_yyyy_mm_dd(date_raw)
    if close is None:
        return d, None, "na_or_parse_fail", url
    return d, close, "NA", url

def vix_from_stooq() -> Tuple[Optional[str], Optional[float], str, str]:
    # Stooq symbol for VIX is often "vix"
    d, c, n, u = stooq_daily_close("vix", lookback_days=35)
    return d, c, n, u

# -------------------------
# OFR FSI (explicitly degradable; do not chase)
# -------------------------
def ofr_fsi_latest_degradable() -> Tuple[Optional[str], Optional[float], str, str]:
    # Keep the field, but don't try hard. If not available, return NA with clear note.
    page_url = "https://www.financialresearch.gov/financial-stress-index/"
    html, err = http_get(page_url, timeout=25)
    if err:
        return None, None, f"PAGE_{err} (ignored; normal degradation)", page_url

    # Many times there is no stable public CSV link we can scrape reliably.
    # We intentionally do NOT chase zip/csv links. Return NA with explicit note.
    _ = html  # unused on purpose
    return None, None, "NO_PUBLIC_CSV_LINK (ignored; normal degradation)", page_url

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
    # unique by (series_id, data_date) -- assumes data_date already normalized
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
    for i, r in enumerate(latest[:80]):
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
# Regime classification helpers
# -------------------------
def _latest_value(points: List[Point], series_id: str) -> Optional[float]:
    for p in points:
        if p.series_id == series_id:
            return safe_float(p.value)
    return None

def _latest_date(points: List[Point], series_id: str) -> Optional[str]:
    for p in points:
        if p.series_id == series_id:
            d = normalize_date_yyyy_mm_dd(p.data_date)
            return d
    return None

def _collect_history_series(hist: List[dict], series_id: str) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for r in hist:
        if r.get("series_id") != series_id:
            continue
        d = normalize_date_yyyy_mm_dd(r.get("data_date"))
        v = safe_float(r.get("value"))
        if not d or v is None:
            continue
        out.append((d, v))
    out.sort(key=lambda x: x[0])
    return out

def calc_ratio_ma_dev(
    hist: List[dict],
    ratio_series_id: str,
    ratio_today: Optional[float],
    ratio_date: Optional[str],
    target_window: int = 60,
    bootstrap_windows: List[int] = [30, 20],
) -> Tuple[Optional[float], Optional[int], str]:
    """
    Compute deviation = (ratio_today / MA(window) - 1).
    Primary: MA60. If insufficient history, bootstrap MA30 then MA20.
    Returns (dev, used_window, note)
      note may include: history_lt_XX, ma_zero, etc.
    """
    if ratio_today is None or not ratio_date:
        return None, None, "ratio_missing"

    series = _collect_history_series(hist, ratio_series_id)

    # Need MA window history ending at ratio_date (inclusive).
    # We compute MA over last N values whose date <= ratio_date.
    def dev_for_window(w: int) -> Tuple[Optional[float], Optional[int], str]:
        eligible = [v for (d, v) in series if d <= ratio_date]
        if len(eligible) < w:
            return None, None, f"history_lt_{w}({len(eligible)})"
        window_vals = eligible[-w:]
        ma = sum(window_vals) / float(w)
        if ma == 0:
            return None, None, "ma_zero"
        return (ratio_today / ma) - 1.0, w, "NA"

    dev, used_w, note = dev_for_window(target_window)
    if dev is not None:
        return dev, used_w, note

    for w in bootstrap_windows:
        d2, uw2, note2 = dev_for_window(w)
        if d2 is not None:
            return d2, uw2, f"bootstrap_ma={w}"
    return None, None, note  # last failure reason from MA60 attempt

def classify_regime(points: List[Point], hist: List[dict]) -> Tuple[str, str, List[str]]:
    """
    Outputs:
      regime_state: str
      confidence: 'LOW'|'MEDIUM'|'HIGH'
      reasons: list[str]
    Rules are intentionally conservative and auditable.
    OFR_FSI can be NA and is treated as normal degradation (does not reduce confidence).
    """
    reasons: List[str] = []

    vix = _latest_value(points, "VIX_PROXY")
    be10 = _latest_value(points, "BE10Y_PROXY")

    # Credit axis: HYG/IEF ratio dev vs MA (60 primary; 30/20 bootstrap).
    ratio = _latest_value(points, "HYG_IEF_RATIO")
    ratio_date = _latest_date(points, "HYG_IEF_RATIO")
    credit_dev, credit_win, credit_note = calc_ratio_ma_dev(
        hist=hist,
        ratio_series_id="HYG_IEF_RATIO",
        ratio_today=ratio,
        ratio_date=ratio_date,
        target_window=60,
        bootstrap_windows=[30, 20],
    )

    # Panic axis (VIX)
    if vix is None:
        panic = "NA"
        reasons.append("core_missing=VIX_PROXY")
    else:
        if vix < 18:
            panic = "LOW"
        elif vix < 25:
            panic = "MED"
        else:
            panic = "HIGH"
        reasons.append(f"panic={panic}(VIX={vix})")

    # Inflation expectation axis (BE10Y)
    if be10 is None:
        infl = "NA"
        reasons.append("core_missing=BE10Y_PROXY")
    else:
        if be10 < 1.2:
            infl = "LOW"
        elif be10 > 2.5:
            infl = "HIGH"
        else:
            infl = "MID"
        reasons.append(f"inflation_expect={infl}(BE10Y={be10})")

    # Credit axis (MA deviation)
    credit_axis = "NA"
    if credit_dev is None or credit_win is None:
        reasons.append(f"credit_dev_unavailable({credit_note})")
    else:
        # Threshold per your spec: MA60 deviation ±1%
        # dev <= -1% : credit deteriorating / risk-off pressure
        # dev >= +1% : credit improving / risk-on
        if credit_dev <= -0.01:
            credit_axis = "RISK_OFF"
        elif credit_dev >= 0.01:
            credit_axis = "RISK_ON"
        else:
            credit_axis = "NEUTRAL"
        reasons.append(f"credit={credit_axis}(dev={credit_dev:.4f},ma={credit_win})")

    # OFR optional
    ofr = _latest_value(points, "OFR_FSI")
    if ofr is None:
        reasons.append("OFR_FSI=NA (optional; normal degradation)")
    else:
        reasons.append(f"OFR_FSI={ofr} (optional)")

    # Confidence baseline (only core axes: VIX + BE10Y are core, credit is auxiliary-but-important)
    core_missing = []
    if vix is None:
        core_missing.append("VIX_PROXY")
    if be10 is None:
        core_missing.append("BE10Y_PROXY")

    if core_missing:
        confidence = "LOW"
        regime = "UNKNOWN_INSUFFICIENT_DATA"
        reasons.insert(0, f"core_missing={','.join(core_missing)}")
        # Even if credit available, without both core axes we stay UNKNOWN by design.
        return regime, confidence, reasons

    # Now we have both core axes.
    # Decide regime conservatively.
    # Mapping logic:
    # - If panic HIGH -> stress regime; inflation LOW amplifies deflation-crisis vibe.
    # - If credit RISK_OFF + panic MED/HIGH -> defensive.
    # - If inflation HIGH + panic LOW + credit RISK_ON/NEUTRAL -> overheating-ish.
    # - Else neutral mixed.

    if panic == "HIGH":
        if infl == "LOW":
            regime = "CRISIS_DEFLATION"
        elif infl == "HIGH":
            regime = "CRISIS_STAGFLATION_RISK"
        else:
            regime = "CRISIS_STRESS"
    elif panic == "MED":
        if infl == "LOW" or credit_axis == "RISK_OFF":
            regime = "DEFENSIVE"
        elif infl == "HIGH":
            regime = "OVERHEATING_RISK"
        else:
            regime = "NEUTRAL_MIXED"
    else:  # panic LOW
        if infl == "HIGH" and credit_axis in ("RISK_ON", "NEUTRAL", "NA"):
            regime = "OVERHEATING_RISK"
        elif infl == "LOW" and credit_axis == "RISK_OFF":
            regime = "DEFENSIVE"
        else:
            regime = "NEUTRAL_MIXED"

    # Confidence: HIGH only if credit axis computed with MA60 AND not NA.
    # MEDIUM if credit axis is NA or uses bootstrap MA30/MA20
    # LOW already handled above when core missing.
    confidence = "MEDIUM"
    if credit_dev is not None and credit_win == 60:
        confidence = "HIGH"
    else:
        confidence = "MEDIUM"

    # v3.1 PATCH: confidence cap when using bootstrap MA<60
    # (Already enforced by above logic; keep explicit reason for auditability.)
    if credit_win is not None and credit_win < 60:
        if confidence == "HIGH":
            confidence = "MEDIUM"
        reasons.append(f"confidence_cap=MEDIUM(credit_ma={credit_win})")

    return regime, confidence, reasons

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

    def add(series_id: str, data_date_raw: Optional[str], value: Optional[float], source_url: str, notes: str):
        data_date = normalize_date_yyyy_mm_dd(data_date_raw) if data_date_raw else None
        if not data_date or value is None:
            points.append(Point(as_of, series_id, data_date or "NA", "NA", source_url, notes if notes != "NA" else "missing"))
        else:
            points.append(Point(as_of, series_id, data_date, f"{value}", source_url, notes))

    # Treasury 10Y nominal & real via XML (try current + previous month)
    nom_date = real_date = None
    nom10 = real10 = None
    nom_notes = real_notes = "NA"
    nom_url_used = real_url_used = ""

    for yyyymm in yyyymm_candidates(2):
        url = treasury_xml_url("daily_treasury_yield_curve", yyyymm)
        xml_text, err = http_get(url)
        if err:
            nom_notes, nom_url_used = err, url
            continue
        d, v, notes, _key = parse_latest_10y_from_treasury_xml(xml_text)
        nom_notes, nom_url_used = notes, url
        if d and v is not None:
            nom_date, nom10 = d, v
            break

    for yyyymm in yyyymm_candidates(2):
        url = treasury_xml_url("daily_treasury_real_yield_curve", yyyymm)
        xml_text, err = http_get(url)
        if err:
            real_notes, real_url_used = err, url
            continue
        d, v, notes, _key = parse_latest_10y_from_treasury_xml(xml_text)
        real_notes, real_url_used = notes, url
        if d and v is not None:
            real_date, real10 = d, v
            break

    add("NOMINAL_10Y", nom_date, nom10, nom_url_used or "NA", nom_notes)
    add("REAL_10Y", real_date, real10, real_url_used or "NA", real_notes)

    # Breakeven proxy: only if same date
    be10 = None
    be_date = None
    be_notes = "NA"
    if nom10 is not None and real10 is not None and nom_date and real_date and nom_date == real_date:
        be10 = nom10 - real10
        be_date = nom_date
    else:
        be_notes = "date_mismatch_or_na"
    add("BE10Y_PROXY", be_date, be10, f"{nom_url_used} + {real_url_used}".strip(), be_notes)

    # VIX: CBOE CSV primary, Stooq fallback
    vix_d, vix_v, vix_n, vix_u = vix_from_cboe_csv()
    if vix_v is None:
        sd, sv, sn, su = vix_from_stooq()
        # combine note
        note = f"{vix_n};stooq_{sn}"
        add("VIX_PROXY", sd, sv, su, note)
    else:
        add("VIX_PROXY", vix_d, vix_v, vix_u, vix_n)

    # Stooq closes
    hyg_d, hyg_c, hyg_n, hyg_u = stooq_daily_close("hyg.us", 35)
    ief_d, ief_c, ief_n, ief_u = stooq_daily_close("ief.us", 35)
    tip_d, tip_c, tip_n, tip_u = stooq_daily_close("tip.us", 35)

    add("HYG_CLOSE", hyg_d, hyg_c, hyg_u, hyg_n)
    add("IEF_CLOSE", ief_d, ief_c, ief_u, ief_n)
    add("TIP_CLOSE", tip_d, tip_c, tip_u, tip_n)

    # Ratios (require same date)
    hyg_ief_ratio = None
    ratio_date = None
    ratio_notes = "NA"
    if hyg_c is not None and ief_c is not None and hyg_d and ief_d and normalize_date_yyyy_mm_dd(hyg_d) == normalize_date_yyyy_mm_dd(ief_d):
        hyg_ief_ratio = hyg_c / ief_c
        ratio_date = normalize_date_yyyy_mm_dd(hyg_d)
    else:
        ratio_notes = "date_mismatch_or_na"
    add("HYG_IEF_RATIO", ratio_date, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_date = None
    tip_ratio_notes = "NA"
    if tip_c is not None and ief_c is not None and tip_d and ief_d and normalize_date_yyyy_mm_dd(tip_d) == normalize_date_yyyy_mm_dd(ief_d):
        tip_ief_ratio = tip_c / ief_c
        tip_ratio_date = normalize_date_yyyy_mm_dd(tip_d)
    else:
        tip_ratio_notes = "date_mismatch_or_na"
    add("TIP_IEF_RATIO", tip_ratio_date, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # OFR FSI (degradable)
    ofr_d, ofr_v, ofr_n, ofr_u = ofr_fsi_latest_degradable()
    add("OFR_FSI", ofr_d, ofr_v, ofr_u, ofr_n)

    # Update history with non-NA dates only
    for p in points:
        if p.data_date != "NA":
            # ensure normalized date in history
            p_norm = Point(p.as_of_ts, p.series_id, normalize_date_yyyy_mm_dd(p.data_date) or p.data_date, p.value, p.source_url, p.notes)
            hist = upsert_history(hist, p_norm)

    # Regime state + confidence + reasons
    regime_state, conf, reasons = classify_regime(points, hist)

    today = today_local_yyyy_mm_dd()
    points.append(Point(as_of, "REGIME_STATE", today, regime_state, "NA", "NA"))
    points.append(Point(as_of, "REGIME_CONFIDENCE", today, conf, "NA", "NA"))
    points.append(Point(as_of, "REGIME_REASONS", today, json.dumps(reasons, ensure_ascii=False), "NA", "NA"))

    # Write files
    write_json(latest_json_path, [p.__dict__ for p in points])
    write_latest_csv(latest_csv_path, points)
    write_json(history_path, hist)

if __name__ == "__main__":
    main()