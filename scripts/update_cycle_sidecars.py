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
    # retry: 2s, 4s, 8s
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
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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

    if len(out) > max_rows:
        out = out[-max_rows:]

    return out

# -------------------------
# FRED
# -------------------------

FRED_OBS_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={series_id}&api_key={api_key}&file_type=json"
    "&sort_order=desc&limit=1"
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

    url = FRED_OBS_URL.format(series_id=series_id, api_key=api_key)
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
        data = resp.json()
        obs = data.get("observations") or []
        if not obs:
            return {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": url,
                "notes": "NA (no observations)",
            }
        o0 = obs[0]
        return {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": o0.get("date", "NA"),
            "value": o0.get("value", "NA"),
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

# -------------------------
# Sidecars
# -------------------------

def run_inflation_realrate_cache(tz: str, fred_key: Optional[str]) -> None:
    out_dir = "inflation_realrate_cache"
    ensure_dir(out_dir)

    as_of_ts = now_iso(tz)
    series = ["DFII10", "T10YIE"]
    latest = [fetch_fred_latest(s, fred_key, as_of_ts) for s in series]

    write_json(os.path.join(out_dir, "latest.json"), latest)
    write_csv_latest(os.path.join(out_dir, "latest.csv"), latest)

    hist_path = os.path.join(out_dir, "history.json")
    hist = load_history(hist_path)
    hist2 = upsert_history(hist, latest, max_rows=1200)
    write_json(hist_path, hist2)

def run_asset_proxy_cache(tz: str) -> None:
    out_dir = "asset_proxy_cache"
    ensure_dir(out_dir)

    as_of_ts = now_iso(tz)

    # Gold proxies + REIT proxies via Stooq ETF close
    syms = ["gld.us", "iau.us", "vnq.us", "iyr.us"]
    latest = [fetch_stooq_latest_close(sym, as_of_ts) for sym in syms]

    write_json(os.path.join(out_dir, "latest.json"), latest)
    write_csv_latest(os.path.join(out_dir, "latest.csv"), latest)

    hist_path = os.path.join(out_dir, "history.json")
    hist = load_history(hist_path)
    hist2 = upsert_history(hist, latest, max_rows=2000)
    write_json(hist_path, hist2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    args = ap.parse_args()

    fred_key = os.getenv("FRED_API_KEY")

    run_inflation_realrate_cache(args.tz, fred_key)
    run_asset_proxy_cache(args.tz)

if __name__ == "__main__":
    main()