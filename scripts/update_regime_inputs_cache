#!/usr/bin/env python3
# update_regime_inputs_cache.py
#
# Build regime_inputs_cache:
# - HYG/IEF/TIP daily close from Stooq (full CSV for backfill/incremental)
# - OFR_FSI from OFR CSV
# - Derived HYG_IEF_RATIO (same-date only)
# - Output:
#   - regime_inputs_cache/latest.json  (list[Point dict])
#   - regime_inputs_cache/history_lite.json (list[dict], trimmed per series)
#   - regime_inputs_cache/latest.csv   (optional but useful)

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import requests

OUT_DIR = "regime_inputs_cache"
LATEST_JSON = "latest.json"
LATEST_CSV = "latest.csv"
HISTORY_LITE_JSON = "history_lite.json"

SCRIPT_VERSION = "regime_inputs_cache_v1"
LITE_MAX_POINTS_PER_SERIES = 600

# -------- time helpers --------
def as_of_ts_local_iso() -> str:
    return datetime.now().astimezone().isoformat()

def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# -------- HTTP --------
def http_get(url: str, timeout: int = 25) -> Tuple[Optional[str], Optional[str], int]:
    headers = {
        "User-Agent": f"{SCRIPT_VERSION}/1.0",
        "Accept": "text/csv,application/json,text/plain,*/*",
    }
    try:
        r = requests.get(url, timeout=timeout, headers=headers)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}", r.status_code
        return r.text, None, r.status_code
    except requests.Timeout:
        return None, "timeout", 0
    except Exception as e:
        return None, f"exception:{type(e).__name__}", 0

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

# -------- date normalize (keep minimal, Stooq is YYYY-MM-DD) --------
def normalize_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    ss = str(s).strip()
    if ss == "" or ss.upper() == "NA":
        return None
    if len(ss) >= 10 and ss[4] == "-" and ss[7] == "-":
        return ss[:10]
    return None

# -------- data model --------
@dataclass
class Point:
    as_of_ts: str
    series_id: str
    data_date: str
    value: str
    source_url: str
    notes: str

def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def load_json_list(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def write_latest_csv(path: str, points: List[Point]) -> None:
    fields = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in points:
            w.writerow(p.__dict__)

# -------- Stooq full history fetch --------
def stooq_url(symbol: str, d1: str, d2: str) -> str:
    return f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"

def yyyymmdd_local(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y%m%d")

def fetch_stooq_series(symbol: str, lookback_days: int) -> Tuple[List[Tuple[str, float]], str, str]:
    now = datetime.now().astimezone()
    d2 = yyyymmdd_local(now)
    d1 = yyyymmdd_local(now - timedelta(days=lookback_days))
    url = stooq_url(symbol, d1, d2)
    text, err, _ = http_get(url)
    if err:
        return [], err, url

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return [], "empty_csv", url

    out: List[Tuple[str, float]] = []
    for r in rows:
        dd = normalize_date((r.get("Date") or "").strip())
        close = safe_float(r.get("Close"))
        if dd and close is not None:
            out.append((dd, close))

    if not out:
        return [], "no_valid_rows", url

    # sort by date (compute only)
    out.sort(key=lambda x: x[0])
    return out, "NA", url

# -------- OFR FSI --------
OFR_FSI_CSV_URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"

def fetch_ofr_fsi_series() -> Tuple[List[Tuple[str, float]], str, str]:
    text, err, _ = http_get(OFR_FSI_CSV_URL)
    if err:
        return [], err, OFR_FSI_CSV_URL

    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r]
    if not rows:
        return [], "empty_csv", OFR_FSI_CSV_URL

    # detect date column
    def pick_date(row: dict) -> Optional[str]:
        for k in ["Date", "DATE", "date", "Observation Date"]:
            if k in row and row[k]:
                return normalize_date(row[k])
        # fallback: first column that looks like date
        for k, v in row.items():
            dd = normalize_date(v)
            if dd:
                return dd
        return None

    # detect value column (first non-date numeric)
    def pick_value(row: dict) -> Optional[float]:
        # preferred keys
        preferred = []
        for k in row.keys():
            if not k:
                continue
            lk = k.lower()
            if "fsi" in lk or ("stress" in lk and "index" in lk) or lk == "index":
                preferred.append(k)
        for k in preferred:
            vv = safe_float(row.get(k))
            if vv is not None:
                return vv
        for k, v in row.items():
            if not k:
                continue
            if "date" in k.lower():
                continue
            vv = safe_float(v)
            if vv is not None:
                return vv
        return None

    out: List[Tuple[str, float]] = []
    for r in rows:
        dd = pick_date(r)
        vv = pick_value(r)
        if dd and vv is not None:
            out.append((dd, vv))

    if not out:
        return [], "no_valid_rows", OFR_FSI_CSV_URL

    out.sort(key=lambda x: x[0])
    return out, "NA", OFR_FSI_CSV_URL

# -------- history_lite upsert/trim --------
def merge_lite(existing: List[dict], incoming: List[dict]) -> List[dict]:
    # key: (series_id, data_date) -> keep last
    m: Dict[Tuple[str, str], dict] = {}
    for r in existing:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id") or "").strip()
        dd = normalize_date(r.get("data_date"))
        if not sid or not dd:
            continue
        rr = dict(r)
        rr["series_id"] = sid
        rr["data_date"] = dd
        m[(sid, dd)] = rr

    for r in incoming:
        sid = str(r.get("series_id") or "").strip()
        dd = normalize_date(r.get("data_date"))
        if not sid or not dd:
            continue
        rr = dict(r)
        rr["series_id"] = sid
        rr["data_date"] = dd
        m[(sid, dd)] = rr

    # regroup per series and trim tail
    by: Dict[str, List[dict]] = {}
    for (sid, _dd), rr in m.items():
        by.setdefault(sid, []).append(rr)

    out: List[dict] = []
    for sid, rows in by.items():
        rows.sort(key=lambda x: x["data_date"])
        out.extend(rows[-LITE_MAX_POINTS_PER_SERIES:])

    out.sort(key=lambda x: (x["series_id"], x["data_date"]))
    return out

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--mode", choices=["DAILY", "BACKFILL"], default="DAILY")
    ap.add_argument("--daily-days", type=int, default=30)
    ap.add_argument("--backfill-days", type=int, default=2000)
    args = ap.parse_args()

    out_dir = args.out_dir
    ensure_dir(out_dir)

    as_of = as_of_ts_local_iso()

    # load existing lite
    lite_path = os.path.join(out_dir, HISTORY_LITE_JSON)
    lite_existing = load_json_list(lite_path)

    lookback_days = args.daily_days if args.mode == "DAILY" else args.backfill_days

    points_latest: List[Point] = []
    lite_incoming: List[dict] = []

    def add_latest(series_id: str, data_date: Optional[str], value: Optional[float], url: str, notes: str) -> None:
        dd = normalize_date(data_date) if data_date else None
        if dd is None or value is None:
            points_latest.append(Point(as_of, series_id, dd or "NA", "NA", url, notes))
        else:
            points_latest.append(Point(as_of, series_id, dd, f"{value}", url, notes))

    def add_lite_obs(series_id: str, dd: str, vv: float, url: str, notes: str) -> None:
        lite_incoming.append({
            "as_of_ts": as_of,
            "series_id": series_id,
            "data_date": dd,
            "value": f"{vv}",
            "source_url": url,
            "notes": notes,
        })

    # --- HYG/IEF/TIP series ---
    series_specs = [
        ("HYG_CLOSE", "hyg.us"),
        ("IEF_CLOSE", "ief.us"),
        ("TIP_CLOSE", "tip.us"),
    ]

    latest_map: Dict[str, Tuple[Optional[str], Optional[float], str, str]] = {}

    for sid, sym in series_specs:
        rows, notes, url = fetch_stooq_series(sym, lookback_days)
        if not rows:
            add_latest(sid, None, None, url, notes)
            latest_map[sid] = (None, None, notes, url)
            continue

        # add all rows to lite
        for dd, vv in rows:
            add_lite_obs(sid, dd, vv, url, "NA")

        # latest
        dd_last, vv_last = rows[-1]
        add_latest(sid, dd_last, vv_last, url, notes)
        latest_map[sid] = (dd_last, vv_last, notes, url)

    # --- derived: HYG_IEF_RATIO (same date) ---
    hyg_d, hyg_v, _, _ = latest_map.get("HYG_CLOSE", (None, None, "NA", "NA"))
    ief_d, ief_v, _, _ = latest_map.get("IEF_CLOSE", (None, None, "NA", "NA"))

    ratio_url = "derived:HYG_CLOSE/IEF_CLOSE"
    if hyg_d and ief_d and hyg_d == ief_d and hyg_v is not None and ief_v is not None and ief_v != 0:
        ratio = hyg_v / ief_v
        add_latest("HYG_IEF_RATIO", hyg_d, ratio, ratio_url, "NA")
        add_lite_obs("HYG_IEF_RATIO", hyg_d, ratio, ratio_url, "NA")
    else:
        add_latest("HYG_IEF_RATIO", None, None, ratio_url, "date_mismatch_or_na")

    # --- OFR_FSI (full series; then take latest) ---
    ofr_rows, ofr_notes, ofr_url = fetch_ofr_fsi_series()
    if not ofr_rows:
        # do not block; leave NA, but keep old lite values (merge_lite will preserve)
        add_latest("OFR_FSI", None, None, ofr_url, ofr_notes)
    else:
        # for DAILY mode we can still ingest full, but it's fine; trim later anyway
        for dd, vv in ofr_rows:
            add_lite_obs("OFR_FSI", dd, vv, ofr_url, "NA")
        dd_last, vv_last = ofr_rows[-1]
        add_latest("OFR_FSI", dd_last, vv_last, ofr_url, ofr_notes)

    # merge + trim
    lite_merged = merge_lite(lite_existing, lite_incoming)

    # write outputs
    latest_json_path = os.path.join(out_dir, LATEST_JSON)
    latest_csv_path = os.path.join(out_dir, LATEST_CSV)
    write_json(latest_json_path, [p.__dict__ for p in points_latest])
    write_latest_csv(latest_csv_path, points_latest)
    write_json(lite_path, lite_merged)

if __name__ == "__main__":
    main()