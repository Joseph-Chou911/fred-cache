"""
fred_cache.py

Fetch latest observations for selected FRED series and write audit-friendly outputs:
- cache/latest.csv
- cache/latest.json

Design goals:
- 可審計：source_url 不含 api_key，保留 series/endpoint/查核資訊
- 安全：FRED_API_KEY 只用於 request，不寫入檔案、不輸出到 log；最後一道防線做遮蔽
- 穩定：加入「最小可控」重試（timeout/連線錯誤/指定 5xx）+ backoff
- 一致：CSV 欄位固定，LF 換行，notes 使用可分類的 warn/err 格式
- 便於解析：同時輸出 JSON（不依賴換行，適合 web.run 讀取）

Environment variables:
- FRED_API_KEY: required
- TIMEZONE: optional, default "Asia/Taipei"
"""

from __future__ import annotations

import os
import re
import csv
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from typing import Dict, List, Optional

import requests


# =====================
# Config
# =====================

FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
if not FRED_API_KEY:
    raise SystemExit("Missing FRED_API_KEY env var (set it in GitHub Actions Secrets).")

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))

# Added: NFCINONFINLEVERAGE, T10Y2Y, T10Y3M
SERIES: List[str] = [
    "STLFSI4",
    "VIXCLS",
    "BAMLH0A0HYM2",
    "DGS2",
    "DGS10",
    "T10Y2Y",
    "T10Y3M",
    "NFCINONFINLEVERAGE",
    "DTWEXBGS",
    "DCOILWTICO",
    "SP500",
    "NASDAQCOM",
    "DJIA",
]

BASE = "https://api.stlouisfed.org/fred/series/observations"
FIELDNAMES = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]

# Retry policy (minimal & auditable)
RETRYABLE_STATUS = {500, 502, 503, 504}
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 20


# =====================
# Helpers
# =====================

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
    Last line of defense: redact any api_key values if present.
    """
    if not s:
        return s

    # If the exact key appears anywhere, remove it.
    if FRED_API_KEY and FRED_API_KEY in s:
        s = s.replace(FRED_API_KEY, "***REDACTED***")

    # Redact any api_key=VALUE pattern (case-insensitive).
    s = re.sub(r"(?i)(api_key=)[^&\s]+", r"\1***REDACTED***", s)
    return s


def _get_with_retry(url: str, params: dict, timeout: int = TIMEOUT_SECONDS) -> requests.Response:
    """
    Minimal, auditable retry:
    - Retry on Timeout / ConnectionError
    - Retry on HTTP 5xx in RETRYABLE_STATUS
    Backoff: 1s -> 2s (for attempts 1->2 and 2->3)
    """
    last_exc: Optional[BaseException] = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)

            # Retry certain 5xx before raise_for_status
            if r.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(f"retryable_status:{r.status_code}", response=r)

            r.raise_for_status()
            return r

        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_exc = e
            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt)  # 1s, 2s
                continue
            raise

    # Should not reach here, but keep type-checkers happy
    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected retry flow: no response and no exception.")


# =====================
# Core
# =====================

def fetch_latest_obs(series_id: str) -> Dict[str, str]:
    """
    Fetch the latest observation for a given FRED series.
    Returns a dict matching the CSV/JSON schema (without as_of_ts; caller adds it).
    """
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,  # used only for request; NEVER store/log request URL
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }

    r = _get_with_retry(BASE, params=params, timeout=TIMEOUT_SECONDS)
    data = r.json()

    obs = data.get("observations") or []
    if not obs:
        return {
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": _redact_secrets(_safe_source_url(series_id)),
            "notes": "warn:no_observations",
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
        "notes": "NA",
    }


# =====================
# Main
# =====================

def main() -> None:
    as_of_ts = datetime.now(tz=TZ).isoformat(timespec="seconds")

    rows: List[Dict[str, str]] = []
    for sid in SERIES:
        try:
            row = fetch_latest_obs(sid)
        except Exception as e:
            row = {
                "series_id": sid,
                "data_date": "NA",
                "value": "NA",
                "source_url": _redact_secrets(_safe_source_url(sid)),
                "notes": f"err:fetch:{type(e).__name__}",
            }

        row["as_of_ts"] = as_of_ts
        rows.append(row)

    os.makedirs("cache", exist_ok=True)

    # ---- Write CSV ----
    csv_path = "cache/latest.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
            lineterminator="\n",  # consistent LF newlines
        )
        w.writeheader()
        w.writerows(rows)

    # ---- Write JSON ----
    json_path = "cache/latest.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        # JSON whitespace is irrelevant for parsers; keep compact & robust
        json.dump(rows, jf, ensure_ascii=False, separators=(",", ":"))
        jf.write("\n")

    print(_redact_secrets(f"Wrote {csv_path} + {json_path} with {len(rows)} rows @ {as_of_ts}"))


if __name__ == "__main__":
    main()