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


def _safe_source_url(series_id: str) -> str:
    """
    Build an audit-friendly URL WITHOUT api_key.
    """
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    return f"{BASE}?{urlencode(params)}"


def _redact_secrets(s: str) -> str:
    """
    Last line of defense: if api_key appears anywhere, redact it.
    """
    if not s:
        return s
    if FRED_API_KEY and FRED_API_KEY in s:
        s = s.replace(FRED_API_KEY, "***REDACTED***")
    # redact any api_key query pattern (case-insensitive-ish minimal)
    s = s.replace("api_key=", "api_key=***REDACTED***")
    s = s.replace("API_KEY=", "API_KEY=***REDACTED***")
    return s


def fetch_latest_obs(series_id: str) -> dict:
    # NOTE: Using api_key in query is fine; we never store r.url and we redact outputs anyway.
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,  # used only for request; NEVER store/log
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }

    r = requests.get(BASE, params=params, timeout=20)
    r.raise_for_status()

    data = r.json()
    obs = (data.get("observations") or [])
    if not obs:
        return {
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": _redact_secrets(_safe_source_url(series_id)),
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
        "source_url": _redact_secrets(_safe_source_url(series_id)),
        "notes": "",
    }


def main() -> None:
    rows = []
    for sid in SERIES:
        try:
            row = fetch_latest_obs(sid)
        except Exception as e:
            row = {
                "series_id": sid,
                "data_date": "NA",
                "value": "NA",
                "source_url": _redact_secrets(_safe_source_url(sid)),
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

    print(_redact_secrets(f"Wrote {out_path} with {len(rows)} rows @ {as_of_ts}"))


if __name__ == "__main__":
    main()
