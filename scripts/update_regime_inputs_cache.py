#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_regime_inputs_cache.py (minimal, auditable)

Outputs (regime_inputs_cache/):
  - inputs_latest.json          (list[point])
  - inputs_history_lite.json    (list[point], upserted, order-preserving)
  - dq_state.json               (simple data quality summary)
  - inputs_schema_out.json      (stable schema/info)

Points schema:
  {
    "as_of_ts": "...",          # local ISO w/ offset
    "series_id": "HYG_CLOSE",
    "data_date": "YYYY-MM-DD",
    "value": "123.45" or "NA",
    "source_url": "...",
    "notes": "NA" or "WARN:...."
  }
"""

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import requests

OUT_DIR = "regime_inputs_cache"
LATEST_NAME = "inputs_latest.json"
HIST_NAME = "inputs_history_lite.json"
DQ_NAME = "dq_state.json"
SCHEMA_OUT_NAME = "inputs_schema_out.json"

MAX_HISTORY_ROWS = 8000  # keep ample room; MA252 needs >=252 points/series

# -------------------------
# time helpers
# -------------------------
def as_of_ts_local_iso() -> str:
    return datetime.now().astimezone().isoformat()

def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# -------------------------
# parsing helpers
# -------------------------
_DATE_PATTERNS = [
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    (None,      re.compile(r"^\d{4}-\d{2}-\d{2}T")),  # ISO datetime -> take date
    ("%m/%d/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
]

def normalize_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    ss = str(s).strip()
    if ss == "" or ss.upper() == "NA":
        return None
    if "T" in ss and re.match(r"^\d{4}-\d{2}-\d{2}T", ss):
        return ss[:10]
    for fmt, pat in _DATE_PATTERNS:
        if pat.match(ss):
            if fmt is None:
                return ss[:10]
            try:
                d = datetime.strptime(ss, fmt).date()
                return d.strftime("%Y-%m-%d")
            except Exception:
                return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ss)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None

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

# -------------------------
# http
# -------------------------
def http_get(url: str, timeout: int = 25) -> Tuple[Optional[str], str]:
    headers = {
        "User-Agent": "regime_inputs_cache/1.0",
        "Accept": "text/csv,application/json,text/plain,*/*",
    }
    try:
        r = requests.get(url, timeout=timeout, headers=headers)
        if r.status_code != 200:
            return None, f"HTTP_{r.status_code}"
        return r.text, "NA"
    except requests.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, f"exception:{type(e).__name__}"

# -------------------------
# data fetchers
# -------------------------
def stooq_daily_close(symbol: str, lookback_days: int = 400) -> Tuple[Optional[str], Optional[float], str]:
    # Stooq daily history CSV; we take last row
    now = datetime.now().astimezone()
    d2 = now.strftime("%Y%m%d")
    d1 = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    text, err = http_get(url)
    if err != "NA":
        return None, None, f"WARN:stooq_fetch_fail({err})|{url}"

    reader = csv.DictReader((text or "").splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, f"WARN:stooq_empty_csv|{url}"

    last = rows[-1]
    dd = normalize_date(last.get("Date"))
    close = safe_float(last.get("Close"))
    if dd is None:
        return None, close, f"WARN:stooq_date_parse_fail|{url}"
    if close is None:
        return dd, None, f"WARN:stooq_close_parse_fail|{url}"
    return dd, close, f"NA|{url}"

def cboe_vix_latest() -> Tuple[Optional[str], Optional[float], str]:
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    text, err = http_get(url)
    if err != "NA":
        return None, None, f"WARN:cboe_vix_fetch_fail({err})|{url}"

    reader = csv.DictReader((text or "").splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, f"WARN:cboe_vix_empty_csv|{url}"

    last = rows[-1]
    raw_date = (last.get("DATE") or last.get("Date") or "").strip()
    dd = normalize_date(raw_date)

    v = None
    for k in ["CLOSE", "Close", "close"]:
        if k in last:
            v = safe_float(last.get(k))
            break

    if dd is None:
        return None, v, f"WARN:cboe_vix_date_parse_fail|{url}"
    if v is None:
        return dd, None, f"WARN:cboe_vix_close_parse_fail|{url}"
    return dd, v, f"NA|{url}"

OFR_FSI_CSV_URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"

def ofr_fsi_latest() -> Tuple[Optional[str], Optional[float], str]:
    text, err = http_get(OFR_FSI_CSV_URL)
    if err != "NA":
        return None, None, f"WARN:ofr_fsi_fetch_fail({err})|{OFR_FSI_CSV_URL}"

    reader = csv.DictReader((text or "").splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return None, None, f"WARN:ofr_fsi_empty_csv|{OFR_FSI_CSV_URL}"

    last = rows[-1]
    raw_date = (last.get("Date") or last.get("DATE") or last.get("date") or "").strip()
    dd = normalize_date(raw_date)

    # try best-effort locate numeric column
    val = None
    preferred = []
    for k in last.keys():
        lk = (k or "").lower()
        if lk == "date":
            continue
        if "fsi" in lk or "index" in lk or ("stress" in lk and "financial" in lk):
            preferred.append(k)

    for k in preferred:
        vv = safe_float(last.get(k))
        if vv is not None:
            val = vv
            break

    if val is None:
        for k, v0 in last.items():
            if k and "date" in k.lower():
                continue
            vv = safe_float(v0)
            if vv is not None:
                val = vv
                break

    if dd is None:
        return None, val, f"WARN:ofr_fsi_date_parse_fail|{OFR_FSI_CSV_URL}"
    if val is None:
        return dd, None, f"WARN:ofr_fsi_value_parse_fail|{OFR_FSI_CSV_URL}"
    return dd, val, f"NA|{OFR_FSI_CSV_URL}"

# -------------------------
# IO model
# -------------------------
@dataclass
class Point:
    as_of_ts: str
    series_id: str
    data_date: str
    value: str
    source_url: str
    notes: str

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

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
        f.write("\n")

def normalize_history_preserve_order(hist: List[dict]) -> List[dict]:
    """
    Normalize + dedup by (series_id, data_date) but DO NOT global sort.
    Overwrite in-place on duplicates to keep stable order.
    """
    out: List[dict] = []
    idx: Dict[Tuple[str, str], int] = {}

    for r in hist:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id") or "").strip()
        dd = normalize_date(r.get("data_date"))
        if not sid or not dd:
            continue

        rr = dict(r)
        rr["series_id"] = sid
        rr["data_date"] = dd

        key = (sid, dd)
        if key in idx:
            out[idx[key]] = rr
        else:
            idx[key] = len(out)
            out.append(rr)

    if len(out) > MAX_HISTORY_ROWS:
        out = out[-MAX_HISTORY_ROWS:]
    return out

def upsert_history(hist: List[dict], p: Point) -> List[dict]:
    if p.data_date == "NA" or p.value == "NA":
        return hist
    key = (p.series_id, p.data_date)

    # search backward for speed
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("series_id") == key[0] and hist[i].get("data_date") == key[1]:
            hist[i] = p.__dict__
            return hist

    hist.append(p.__dict__)
    if len(hist) > MAX_HISTORY_ROWS:
        hist = hist[-MAX_HISTORY_ROWS:]
    return hist

def count_valid_points(hist: List[dict]) -> Dict[str, int]:
    c: Dict[str, int] = {}
    for r in hist:
        sid = r.get("series_id")
        dd = normalize_date(r.get("data_date"))
        v = safe_float(r.get("value"))
        if sid and dd and v is not None:
            c[sid] = c.get(sid, 0) + 1
    return c

# -------------------------
# main
# -------------------------
def main() -> None:
    ensure_dir(OUT_DIR)

    latest_path = os.path.join(OUT_DIR, LATEST_NAME)
    hist_path = os.path.join(OUT_DIR, HIST_NAME)
    dq_path = os.path.join(OUT_DIR, DQ_NAME)
    schema_path = os.path.join(OUT_DIR, SCHEMA_OUT_NAME)

    as_of = as_of_ts_local_iso()

    # Load existing history and normalize (order-preserving)
    hist_raw = load_json_list(hist_path)
    hist = normalize_history_preserve_order(hist_raw)

    points: List[Point] = []

    def add_point(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str) -> None:
        dd = normalize_date(data_date) if data_date else None
        if dd is None or value is None:
            points.append(Point(as_of, series_id, dd or "NA", "NA", source_url, notes))
        else:
            points.append(Point(as_of, series_id, dd, f"{value}", source_url, notes))

    # --- HYG/IEF/TIP closes (Stooq) ---
    hyg_d, hyg_v, hyg_meta = stooq_daily_close("hyg.us")
    ief_d, ief_v, ief_meta = stooq_daily_close("ief.us")
    tip_d, tip_v, tip_meta = stooq_daily_close("tip.us")

    def meta_to_notes(meta: str) -> Tuple[str, str]:
        # meta format: "NA|url" or "WARN:...|url"
        if "|" in meta:
            n, u = meta.split("|", 1)
            return n, u
        return meta, "NA"

    hyg_n, hyg_u = meta_to_notes(hyg_meta)
    ief_n, ief_u = meta_to_notes(ief_meta)
    tip_n, tip_u = meta_to_notes(tip_meta)

    add_point("HYG_CLOSE", hyg_d, hyg_v, hyg_u, hyg_n)
    add_point("IEF_CLOSE", ief_d, ief_v, ief_u, ief_n)
    add_point("TIP_CLOSE", tip_d, tip_v, tip_u, tip_n)

    # --- Ratios (same date only) ---
    hyg_ief_ratio = None
    ratio_dd = None
    ratio_notes = "WARN:date_mismatch_or_na"
    if hyg_v is not None and ief_v is not None and hyg_d and ief_d:
        hd = normalize_date(hyg_d)
        idd = normalize_date(ief_d)
        if hd and idd and hd == idd:
            hyg_ief_ratio = hyg_v / ief_v
            ratio_dd = hd
            ratio_notes = "NA"
    add_point("HYG_IEF_RATIO", ratio_dd, hyg_ief_ratio, "https://stooq.com/", ratio_notes)

    tip_ief_ratio = None
    tip_ratio_dd = None
    tip_ratio_notes = "WARN:date_mismatch_or_na"
    if tip_v is not None and ief_v is not None and tip_d and ief_d:
        td = normalize_date(tip_d)
        idd = normalize_date(ief_d)
        if td and idd and td == idd:
            tip_ief_ratio = tip_v / ief_v
            tip_ratio_dd = td
            tip_ratio_notes = "NA"
    add_point("TIP_IEF_RATIO", tip_ratio_dd, tip_ief_ratio, "https://stooq.com/", tip_ratio_notes)

    # --- OFR FSI ---
    ofr_d, ofr_v, ofr_meta = ofr_fsi_latest()
    ofr_notes, ofr_url = meta_to_notes(ofr_meta)
    add_point("OFR_FSI", ofr_d, ofr_v, ofr_url, ofr_notes)

    # --- VIX (CBOE primary; fallback Stooq) ---
    vix_d, vix_v, vix_meta = cboe_vix_latest()
    vix_notes, vix_url = meta_to_notes(vix_meta)
    if vix_d and vix_v is not None:
        add_point("VIX", vix_d, vix_v, vix_url, vix_notes)
    else:
        # fallback stooq "vix"
        sd, sv, smeta = stooq_daily_close("vix")
        sn, su = meta_to_notes(smeta)
        if sd and sv is not None:
            add_point("VIX", sd, sv, su, f"WARN:fallback_stooq({vix_notes};{sn})")
        else:
            add_point("VIX", None, None, vix_url, f"WARN:both_fail({vix_notes};{sn})")

    # Write latest
    write_json(latest_path, [p.__dict__ for p in points])

    # Upsert into history (exclude NA)
    for p in points:
        hist = upsert_history(hist, p)

    # Normalize again (dedup stable)
    hist = normalize_history_preserve_order(hist)
    write_json(hist_path, hist)

    # DQ summary
    counts = count_valid_points(hist)
    core = ["HYG_CLOSE", "IEF_CLOSE", "TIP_CLOSE", "HYG_IEF_RATIO", "TIP_IEF_RATIO", "OFR_FSI", "VIX"]
    missing = [s for s in core if counts.get(s, 0) == 0]
    warn_lt60 = [s for s in core if 0 < counts.get(s, 0) < 60]
    warn_lt252 = [s for s in core if 0 < counts.get(s, 0) < 252]

    dq = {
        "generated_at_utc": utc_iso(),
        "as_of_ts": as_of,
        "status": "OK" if not missing else "WARN",
        "series_counts": counts,
        "missing_series": missing,
        "warn_lt_60": warn_lt60,
        "warn_lt_252": warn_lt252,
        "notes": "Window definition = last N valid points; MA60/MA252 computed downstream (features).",
    }
    write_json(dq_path, dq)

    # Schema (stable)
    schema = {
        "generated_at_utc": utc_iso(),
        "as_of_ts": as_of,
        "schema_version": "inputs_schema_v1_minimal",
        "point_fields": ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"],
        "series": {
            "HYG_CLOSE": {"source": "stooq", "symbol": "hyg.us"},
            "IEF_CLOSE": {"source": "stooq", "symbol": "ief.us"},
            "TIP_CLOSE": {"source": "stooq", "symbol": "tip.us"},
            "HYG_IEF_RATIO": {"derived_from": ["HYG_CLOSE", "IEF_CLOSE"], "rule": "same-date only"},
            "TIP_IEF_RATIO": {"derived_from": ["TIP_CLOSE", "IEF_CLOSE"], "rule": "same-date only"},
            "OFR_FSI": {"source": "financialresearch.gov", "url": OFR_FSI_CSV_URL},
            "VIX": {"source": "cboe (primary), stooq (fallback)", "url": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"},
        },
    }
    write_json(schema_path, schema)

    # Console summary
    print("OK: wrote inputs_latest.json / inputs_history_lite.json / dq_state.json / inputs_schema_out.json")
    print("series_counts:", json.dumps(counts, ensure_ascii=False))

if __name__ == "__main__":
    main()