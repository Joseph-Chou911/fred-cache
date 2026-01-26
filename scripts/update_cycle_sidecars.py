#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update cycle sidecars:
- inflation_realrate_cache: FRED DFII10, T10YIE
- asset_proxy_cache: Stooq ETF close (gld.us, iau.us, vnq.us, iyr.us)

Features:
- Always fetch latest (for latest.json / latest.csv and incremental history append).
- Optional backfill:
  - --backfill_start YYYY-MM-DD (required to trigger backfill)
  - --backfill_end YYYY-MM-DD (optional, default=today UTC)
  - Backfill is one-time guarded by <cache>/backfill_done.flag unless --force_backfill.

History:
- Stored as JSON list of rows:
  {as_of_ts, series_id, data_date, value, source_url, notes}
- Dedupe key: (series_id, data_date)
- Sorted by (data_date, series_id) and capped by max_rows.

Audit / secrets:
- Persisted FRED source_url redacts api_key (REDACTED).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

RETRY_STATUSES = {429, 502, 503, 504}

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# -------------------------
# Generic helpers
# -------------------------

def now_iso(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def write_json(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)

def write_text(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
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
    # retry: 2s, 4s, 8s
    headers = {"User-Agent": UA}
    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
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
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return obj
        # tolerate dict schema {items:[...]}
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

    out.sort(key=lambda r: (r.get("data_date", ""), r.get("series_id", "")))

    if max_rows > 0 and len(out) > max_rows:
        out = out[-max_rows:]

    return out

def parse_ymd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def today_utc_ymd() -> str:
    return datetime.utcnow().date().strftime("%Y-%m-%d")

def has_backfill_done_flag(out_dir: str) -> bool:
    return os.path.exists(os.path.join(out_dir, "backfill_done.flag"))

def write_backfill_done_flag(out_dir: str, start: str, end: str, run_as_of_ts: str) -> None:
    path = os.path.join(out_dir, "backfill_done.flag")
    txt = f"backfill_done: start={start} end={end} as_of_ts={run_as_of_ts}"
    write_text(path, txt)

# -------------------------
# FRED
# -------------------------

FRED_OBS_URL_TMPL = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={series_id}&api_key={api_key}&file_type=json"
)

def fred_url(series_id: str, api_key: str) -> str:
    return FRED_OBS_URL_TMPL.format(series_id=series_id, api_key=api_key)

def fred_safe_url(series_id: str) -> str:
    return FRED_OBS_URL_TMPL.format(series_id=series_id, api_key="REDACTED")

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

    url = fred_url(series_id, api_key) + "&sort_order=desc&limit=1"
    safe_url = fred_safe_url(series_id) + "&sort_order=desc&limit=1"

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
        v = (o0.get("value") or "NA")
        d = (o0.get("date") or "NA")
        if v == ".":
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": d,
                "value": "NA",
                "source_url": safe_url,
                "notes": "NA (value='.')",
            }

        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": d,
            "value": v,
            "source_url": safe_url,
            "notes": "NA",
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

def fetch_fred_range_rows(
    series_id: str,
    api_key: Optional[str],
    as_of_ts: str,
    start_ymd: str,
    end_ymd: str,
) -> List[Dict[str, str]]:
    """
    Return many rows (per observation date) for backfill.
    """
    if not api_key:
        return []

    # observation_start / observation_end
    url = (
        fred_url(series_id, api_key)
        + f"&sort_order=asc&observation_start={start_ymd}&observation_end={end_ymd}"
    )
    safe_url = (
        fred_safe_url(series_id)
        + f"&sort_order=asc&observation_start={start_ymd}&observation_end={end_ymd}"
    )

    resp = http_get_with_backoff(url)
    if resp.status_code != 200:
        return []

    data = resp.json()
    obs = data.get("observations") or []
    out: List[Dict[str, str]] = []
    for o in obs:
        dd = (o.get("date") or "").strip()
        vv = (o.get("value") or "").strip()
        if not dd or not vv or vv == ".":
            continue
        out.append({
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": dd,
            "value": vv,
            "source_url": safe_url,
            "notes": "NA",
        })
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

def fetch_stooq_range_rows(sym: str, as_of_ts: str, start_ymd: str, end_ymd: str) -> List[Dict[str, str]]:
    """
    start_ymd/end_ymd are YYYY-MM-DD
    Stooq needs yyyymmdd.
    """
    d1 = start_ymd.replace("-", "")
    d2 = end_ymd.replace("-", "")
    url = STOOQ_URL_TMPL.format(sym=sym, d1=d1, d2=d2)

    series_id = f"{sym.upper()}_CLOSE"
    resp = http_get_with_backoff(url)
    if resp.status_code != 200:
        return []

    rows = parse_stooq_csv(resp.text)
    if not rows:
        return []

    out: List[Dict[str, str]] = []
    # Keep only valid (Date, Close)
    for r in rows:
        dd = (r.get("Date") or "").strip()
        c = (r.get("Close") or "").strip()
        if not dd or not c or c.lower() == "nan":
            continue
        out.append({
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": dd,
            "value": c,
            "source_url": url,
            "notes": "NA",
        })
    return out


# -------------------------
# Sidecars (runners)
# -------------------------

def run_inflation_realrate_cache(
    tz: str,
    fred_key: Optional[str],
    backfill_start: Optional[str],
    backfill_end: Optional[str],
    force_backfill: bool,
) -> None:
    out_dir = "inflation_realrate_cache"
    ensure_dir(out_dir)

    as_of_ts = now_iso(tz)
    series = ["DFII10", "T10YIE"]

    # Optional backfill
    if backfill_start:
        end = backfill_end or today_utc_ymd()
        flag_ok = has_backfill_done_flag(out_dir)
        if force_backfill or (not flag_ok):
            all_rows: List[Dict[str, str]] = []
            for s in series:
                all_rows.extend(fetch_fred_range_rows(s, fred_key, as_of_ts, backfill_start, end))
            hist_path = os.path.join(out_dir, "history.json")
            hist = load_history(hist_path)
            hist2 = upsert_history(hist, all_rows, max_rows=5000)
            write_json(hist_path, hist2)
            write_backfill_done_flag(out_dir, backfill_start, end, as_of_ts)

    # Always fetch latest
    latest = [fetch_fred_latest(s, fred_key, as_of_ts) for s in series]

    write_json(os.path.join(out_dir, "latest.json"), latest)
    write_csv_latest(os.path.join(out_dir, "latest.csv"), latest)

    # Append latest into history
    hist_path = os.path.join(out_dir, "history.json")
    hist = load_history(hist_path)
    hist2 = upsert_history(hist, latest, max_rows=5000)
    write_json(hist_path, hist2)


def run_asset_proxy_cache(
    tz: str,
    backfill_start: Optional[str],
    backfill_end: Optional[str],
    force_backfill: bool,
) -> None:
    out_dir = "asset_proxy_cache"
    ensure_dir(out_dir)

    as_of_ts = now_iso(tz)

    syms = ["gld.us", "iau.us", "vnq.us", "iyr.us"]

    # Optional backfill
    if backfill_start:
        end = backfill_end or today_utc_ymd()
        flag_ok = has_backfill_done_flag(out_dir)
        if force_backfill or (not flag_ok):
            all_rows: List[Dict[str, str]] = []
            for sym in syms:
                all_rows.extend(fetch_stooq_range_rows(sym, as_of_ts, backfill_start, end))
            hist_path = os.path.join(out_dir, "history.json")
            hist = load_history(hist_path)
            hist2 = upsert_history(hist, all_rows, max_rows=8000)
            write_json(hist_path, hist2)
            write_backfill_done_flag(out_dir, backfill_start, end, as_of_ts)

    # Always fetch latest
    latest = [fetch_stooq_latest_close(sym, as_of_ts) for sym in syms]

    write_json(os.path.join(out_dir, "latest.json"), latest)
    write_csv_latest(os.path.join(out_dir, "latest.csv"), latest)

    hist_path = os.path.join(out_dir, "history.json")
    hist = load_history(hist_path)
    hist2 = upsert_history(hist, latest, max_rows=8000)
    write_json(hist_path, hist2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--backfill_start", default="", help="YYYY-MM-DD (optional)")
    ap.add_argument("--backfill_end", default="", help="YYYY-MM-DD (optional)")
    ap.add_argument("--force_backfill", action="store_true", help="ignore backfill_done.flag")
    args = ap.parse_args()

    tz = args.tz
    backfill_start = args.backfill_start.strip() or None
    backfill_end = args.backfill_end.strip() or None

    # Basic validation (fail-fast)
    if backfill_start:
        try:
            parse_ymd(backfill_start)
        except Exception:
            raise SystemExit("backfill_start must be YYYY-MM-DD")
    if backfill_end:
        try:
            parse_ymd(backfill_end)
        except Exception:
            raise SystemExit("backfill_end must be YYYY-MM-DD")

    fred_key = os.getenv("FRED_API_KEY")

    run_inflation_realrate_cache(tz, fred_key, backfill_start, backfill_end, args.force_backfill)
    run_asset_proxy_cache(tz, backfill_start, backfill_end, args.force_backfill)


if __name__ == "__main__":
    main()