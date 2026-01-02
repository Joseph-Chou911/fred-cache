import os
import csv
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

import requests

FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
if not FRED_API_KEY:
    raise SystemExit("Missing FRED_API_KEY env var (set it in GitHub Actions Secrets).")

SERIES = [
    "STLFSI4",
    "VIXCLS",
    "BAMLH0A0HYM2",
    "DGS2",
    "DGS10",
    "DTWEXBGS",
    "DCOILWTICO",
    "SP500",
    "NASDAQCOM",
    "DJIA",
]

TZ = ZoneInfo("Asia/Taipei")
as_of_ts = datetime.now(tz=TZ).isoformat(timespec="seconds")

BASE = "https://api.stlouisfed.org/fred/series/observations"

# Put key in header, not in URL/query string → CSV/Logs won't leak it.
HEADERS = {"X-Api-Key": FRED_API_KEY}

def safe_source_url(series_id: str) -> str:
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    return f"{BASE}?{urlencode(params)}"

def fetch_latest_obs(series_id: str) -> dict:
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()
    obs = (data.get("observations") or [])
    if not obs:
        return {
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": safe_source_url(series_id),
            "notes": "no_observations",
        }

    latest = obs[0]
    val = latest.get("value", "NA")
    if val == ".":
        val = "NA"

    return {
        "series_id": series_id,
        "data_date": latest.get("date", "NA"),
        "value": val,
        "source_url": safe_source_url(series_id),
        "notes": "",
    }

rows = []
for sid in SERIES:
    try:
        row = fetch_latest_obs(sid)
    except Exception as e:
        row = {
            "series_id": sid,
            "data_date": "NA",
            "value": "NA",
            "source_url": safe_source_url(sid),
            "notes": f"fetch_error:{type(e).__name__}",
        }
    row["as_of_ts"] = as_of_ts
    rows.append(row)

os.makedirs("cache", exist_ok=True)
out_path = "cache/latest.csv"

with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(
        f,
        fieldnames=["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"],
    )
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {out_path} with {len(rows)} rows @ {as_of_ts}")
