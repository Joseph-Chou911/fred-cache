#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Two-cache fetcher with optional backfill for:
1) inflation_realrate_cache: FRED series (DFII10, T10YIE)
2) asset_proxy_cache: Stooq ETF closes (GLD/IAU/VNQ/IYR)

Key behaviors:
- Default mode (no backfill args): fetch latest only, append to history.json (dedupe by series_id+data_date).
- Backfill mode (--backfill_start): fetch full daily history in range, upsert into history.json, then also append latest.
- Audit-friendly: persisted source_url never leaks FRED API key (REDACTED).
- Retry backoff on transient statuses: 2s, 4s, 8s.
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

RETRY_STATUSES = {429, 502, 503, 504}


# -------------------------
# Generic helpers
# -------------------------

def now_iso(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def write_csv_latest(path: str, rows: List[Dict[str, str]]) -> None:
    tmp = path + ".tmp"
    fieldnames = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else str(r.get(k))) for k in fieldnames})
    os.replace(tmp, path)


def http_get_with_backoff(url: str, timeout: int = 20) -> requests.Response:
    """
    retry: 2s, 4s, 8s (attempts=4 total)
    """
    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code in RETRY_STATUSES and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            return resp
        except requests.RequestException:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    raise RuntimeError("http_get_with_backoff unreachable")


def load_history(path: str) -> List[Dict[str, str]]:
    """
    history.json format: a JSON list of row dicts (same fields as latest rows).
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
            if isinstance(obj, list):
                return obj
            # tolerate legacy dict wrapper: {"items":[...]}
            if isinstance(obj, dict) and isinstance(obj.get("items"), list):
                return obj["items"]
            return []
    except Exception:
        return []


def upsert_history(history: List[Dict[str, str]], new_rows: List[Dict[str, str]], max_rows: int) -> List[Dict[str, str]]:
    """
    Dedupe rule: (series_id, data_date)
    - Same day rerun won't duplicate.
    - Keep earliest stored row for that key (stable & auditable).
    """
    seen = set()
    out: List[Dict[str, str]] = []

    for r in history:
        key = (r.get("series_id"), r.get("data_date"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    for r in new_rows:
        sid = r.get("series_id")
        dd = r.get("data_date")
        if not sid or not dd or dd == "NA":
            continue
        key = (sid, dd)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    # Sort makes it easy to audit & diff
    out.sort(key=lambda r: (r.get("data_date", ""), r.get("series_id", "")))

    if len(out) > max_rows:
        out = out[-max_rows:]

    return out


def parse_iso_date_yyyy_mm_dd(s: str) -> str:
    """
    Validate/normalize a YYYY-MM-DD string. Raises ValueError if invalid.
    """
    dt = datetime.strptime(s, "%Y-%m-%d")
    return dt.date().isoformat()


# -------------------------
# FRED (IMPORTANT: redact api_key in persisted source_url)
# -------------------------

FRED_OBS_URL_TMPL = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={series_id}&api_key={api_key}&file_type=json"
    "&sort_order=desc&limit=1"
)

FRED_OBS_RANGE_URL_TMPL = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={series_id}&api_key={api_key}&file_type=json"
    "&sort_order=asc"
    "&observation_start={start}&observation_end={end}"
    "&limit={limit}&offset={offset}"
)


def fred_url(series_id: str, api_key: str) -> str:
    return FRED_OBS_URL_TMPL.format(series_id=series_id, api_key=api_key)


def fred_safe_url(series_id: str) -> str:
    # Persisted URL for audit WITHOUT leaking secrets
    return FRED_OBS_URL_TMPL.format(series_id=series_id, api_key="REDACTED")


def fred_range_url(series_id: str, api_key: str, start: str, end: str, limit: int, offset: int) -> str:
    return FRED_OBS_RANGE_URL_TMPL.format(
        series_id=series_id, api_key=api_key, start=start, end=end, limit=limit, offset=offset
    )


def fred_safe_range_url(series_id: str, start: str, end: str, limit: int, offset: int) -> str:
    return FRED_OBS_RANGE_URL_TMPL.format(
        series_id=series_id, api_key="REDACTED", start=start, end=end, limit=limit, offset=offset
    )


def fetch_fred_latest(series_id: str, api_key: Optional[str], as_of_ts: str) -> Dict[str, str]:
    if not api_key:
        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": "NA",
            "notes": "NA (missing FRED_API_KEY)",
        }

    url = fred_url(series_id, api_key)
    safe_url = fred_safe_url(series_id)

    try:
        resp = http_get_with_backoff(url)
        if resp.status_code != 200:
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": safe_url,
                "notes": f"NA (HTTP {resp.status_code})",
            }

        data = resp.json()
        obs = data.get("observations") or []
        if not obs:
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": safe_url,
                "notes": "NA (no observations)",
            }

        o0 = obs[0]
        v = (o0.get("value") or "NA").strip()
        d = (o0.get("date") or "NA").strip()

        if v == "." or v == "":
            v = "NA"

        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": d,
            "value": v,
            "source_url": safe_url,
            "notes": "NA" if v != "NA" and d != "NA" else "NA (missing value/date)",
        }

    except Exception as e:
        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": safe_url,
            "notes": f"NA (exception: {type(e).__name__})",
        }


def fetch_fred_history_range(
    series_id: str,
    api_key: Optional[str],
    as_of_ts: str,
    start: str,
    end: str,
    page_limit: int = 10000,
) -> List[Dict[str, str]]:
    """
    Fetch full history in [start, end] (inclusive), daily.
    - Uses pagination with limit/offset.
    - Skips FRED missing values '.'.
    - Persists safe_url with REDACTED.
    """
    if not api_key:
        return [{
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": "NA",
            "notes": "NA (missing FRED_API_KEY)",
        }]

    out: List[Dict[str, str]] = []
    offset = 0

    while True:
        url = fred_range_url(series_id, api_key, start, end, page_limit, offset)
        safe_url = fred_safe_range_url(series_id, start, end, page_limit, offset)

        try:
            resp = http_get_with_backoff(url)
        except Exception as e:
            out.append({
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": safe_url,
                "notes": f"NA (exception: {type(e).__name__})",
            })
            break

        if resp.status_code != 200:
            out.append({
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": safe_url,
                "notes": f"NA (HTTP {resp.status_code})",
            })
            break

        data = resp.json()
        obs = data.get("observations") or []
        if not obs:
            break

        for o in obs:
            d = (o.get("date") or "").strip()
            v = (o.get("value") or "").strip()
            if not d or not v or v == ".":
                continue
            out.append({
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": d,
                "value": v,
                "source_url": safe_url,
                "notes": "NA",
            })

        if len(obs) < page_limit:
            break
        offset += page_limit

    return out


# -------------------------
# STOOQ
# -------------------------

STOOQ_URL_TMPL = "https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"


def parse_stooq_csv(text: str) -> List[Dict[str, str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    reader = csv.DictReader(lines)
    return list(reader)


def fetch_stooq_latest_close(sym: str, as_of_ts: str, lookback_days: int = 30) -> Dict[str, str]:
    today = datetime.utcnow().date()
    d2 = today.strftime("%Y%m%d")
    d1 = (today - timedelta(days=lookback_days)).strftime("%Y%m%d")
    url = STOOQ_URL_TMPL.format(sym=sym, d1=d1, d2=d2)

    series_id = f"{sym.upper()}_CLOSE"

    try:
        resp = http_get_with_backoff(url)
        if resp.status_code != 200:
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": f"NA (HTTP {resp.status_code})",
            }

        rows = parse_stooq_csv(resp.text)
        if not rows:
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": "NA (empty CSV)",
            }

        rows_sorted = sorted(rows, key=lambda r: r.get("Date", ""))
        last = None
        for r in reversed(rows_sorted):
            d = (r.get("Date") or "").strip()
            c = (r.get("Close") or "").strip()
            if d and c and c.lower() != "nan":
                last = r
                break

        if not last:
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": "NA (no valid Close)",
            }

        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": (last.get("Date") or "NA").strip(),
            "value": (last.get("Close") or "NA").strip(),
            "source_url": url,
            "notes": "NA",
        }

    except Exception as e:
        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": f"NA (exception: {type(e).__name__})",
        }


def fetch_stooq_history_close(sym: str, as_of_ts: str, start_yyyymmdd: str, end_yyyymmdd: str) -> List[Dict[str, str]]:
    """
    Fetch full daily history in [start_yyyymmdd, end_yyyymmdd] from Stooq CSV.
    """
    url = STOOQ_URL_TMPL.format(sym=sym, d1=start_yyyymmdd, d2=end_yyyymmdd)
    series_id = f"{sym.upper()}_CLOSE"
    out: List[Dict[str, str]] = []

    try:
        resp = http_get_with_backoff(url)
        if resp.status_code != 200:
            return [{
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": f"NA (HTTP {resp.status_code})",
            }]

        rows = parse_stooq_csv(resp.text)
        if not rows:
            return [{
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": "NA (empty CSV)",
            }]

        for r in rows:
            d = (r.get("Date") or "").strip()
            c = (r.get("Close") or "").strip()
            if not d or not c or c.lower() == "nan":
                continue
            out.append({
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": d,
                "value": c,
                "source_url": url,
                "notes": "NA",
            })

        return out

    except Exception as e:
        return [{
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": url,
            "notes": f"NA (exception: {type(e).__name__})",
        }]


# -------------------------
# Sidecars
# -------------------------

def run_inflation_realrate_cache(
    tz: str,
    fred_key: Optional[str],
    backfill_start: Optional[str],
    backfill_end: Optional[str],
) -> None:
    out_dir = "inflation_realrate_cache"
    ensure_dir(out_dir)

    as_of_ts = now_iso(tz)
    series = ["DFII10", "T10YIE"]

    # Always fetch latest (cheap, fast)
    latest = [fetch_fred_latest(s, fred_key, as_of_ts) for s in series]
    write_json(os.path.join(out_dir, "latest.json"), latest)
    write_csv_latest(os.path.join(out_dir, "latest.csv"), latest)

    # Update history
    hist_path = os.path.join(out_dir, "history.json")
    hist = load_history(hist_path)

    new_rows: List[Dict[str, str]] = list(latest)

    if backfill_start:
        # FRED date format: YYYY-MM-DD
        start = parse_iso_date_yyyy_mm_dd(backfill_start)
        end = parse_iso_date_yyyy_mm_dd(backfill_end) if backfill_end else datetime.utcnow().date().isoformat()

        backfilled: List[Dict[str, str]] = []
        for s in series:
            backfilled.extend(fetch_fred_history_range(s, fred_key, as_of_ts, start=start, end=end))
        # Append latest as well (even if backfill includes it; upsert will dedupe)
        new_rows = backfilled + latest

    # If you backfill years, keep a larger cap
    hist2 = upsert_history(hist, new_rows, max_rows=400000)
    write_json(hist_path, hist2)


def run_asset_proxy_cache(
    tz: str,
    backfill_start: Optional[str],
    backfill_end: Optional[str],
) -> None:
    out_dir = "asset_proxy_cache"
    ensure_dir(out_dir)

    as_of_ts = now_iso(tz)

    # Gold proxies + REIT proxies via Stooq ETF close
    syms = ["gld.us", "iau.us", "vnq.us", "iyr.us"]

    # Always fetch latest
    latest = [fetch_stooq_latest_close(sym, as_of_ts) for sym in syms]
    write_json(os.path.join(out_dir, "latest.json"), latest)
    write_csv_latest(os.path.join(out_dir, "latest.csv"), latest)

    # Update history
    hist_path = os.path.join(out_dir, "history.json")
    hist = load_history(hist_path)

    new_rows: List[Dict[str, str]] = list(latest)

    if backfill_start:
        # Stooq needs YYYYMMDD; accept YYYY-MM-DD input
        start = parse_iso_date_yyyy_mm_dd(backfill_start).replace("-", "")
        end_iso = parse_iso_date_yyyy_mm_dd(backfill_end) if backfill_end else datetime.utcnow().date().isoformat()
        end = end_iso.replace("-", "")

        backfilled: List[Dict[str, str]] = []
        for sym in syms:
            backfilled.extend(fetch_stooq_history_close(sym, as_of_ts, start, end))
        new_rows = backfilled + latest

    hist2 = upsert_history(hist, new_rows, max_rows=600000)
    write_json(hist_path, hist2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")

    # Optional backfill range:
    # - If --backfill_start is provided: do backfill + latest.
    # - If not provided: latest only (your current behavior).
    ap.add_argument(
        "--backfill_start",
        default=None,
        help="YYYY-MM-DD. If provided, backfill history from this date to backfill_end (or today UTC).",
    )
    ap.add_argument(
        "--backfill_end",
        default=None,
        help="YYYY-MM-DD. Optional end date for backfill (inclusive). Default is today (UTC).",
    )

    args = ap.parse_args()

    # FRED key from env
    fred_key = os.getenv("FRED_API_KEY")

    run_inflation_realrate_cache(args.tz, fred_key, args.backfill_start, args.backfill_end)
    run_asset_proxy_cache(args.tz, args.backfill_start, args.backfill_end)


if __name__ == "__main__":
    main()