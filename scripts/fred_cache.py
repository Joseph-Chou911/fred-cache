"""
fred_cache.py

Fetch latest observations for selected FRED series and write audit-friendly outputs:
- cache/latest.csv
- cache/latest.json
- cache/history.json   (JSON array; append with dedupe + rolling retention)

Why history.json (array) instead of history.jsonl:
- 不依賴換行；即使內容被壓成單行仍是合法 JSON，利於 web.run / 任何解析器。

Environment variables:
- FRED_API_KEY: required
- TIMEZONE: optional, default "Asia/Taipei"
- HISTORY_KEEP_DAYS: optional int, default 730
"""

from __future__ import annotations

import os
import re
import csv
import json
import time
from datetime import datetime, date
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from typing import Dict, List, Optional, Tuple

import requests


# =====================
# Config
# =====================

FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
if not FRED_API_KEY:
    raise SystemExit("Missing FRED_API_KEY env var (set it in GitHub Actions Secrets).")

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


HISTORY_KEEP_DAYS = _read_int_env("HISTORY_KEEP_DAYS", 730)

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

RETRYABLE_STATUS = {500, 502, 503, 504}
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 20


# =====================
# Helpers
# =====================

def _safe_source_url(series_id: str) -> str:
    """Build an audit-friendly URL WITHOUT api_key."""
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    return f"{BASE}?{urlencode(params)}"


def _redact_secrets(s: str) -> str:
    """Last line of defense: redact any api_key values if present."""
    if not s:
        return s
    if FRED_API_KEY and FRED_API_KEY in s:
        s = s.replace(FRED_API_KEY, "***REDACTED***")
    s = re.sub(r"(?i)(api_key=)[^&\s]+", r"\1***REDACTED***", s)
    return s


def _get_with_retry(url: str, params: dict, timeout: int = TIMEOUT_SECONDS) -> requests.Response:
    """
    Minimal, auditable retry:
    - Retry on Timeout / ConnectionError
    - Retry on HTTP 5xx in RETRYABLE_STATUS
    Backoff: 1s -> 2s
    """
    last_exc: Optional[BaseException] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
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
    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected retry flow: no response and no exception.")


def _parse_asof_date(as_of_ts: str) -> Optional[date]:
    try:
        dt = datetime.fromisoformat(as_of_ts)
        return dt.date()
    except Exception:
        return None


def _atomic_write_text(path: str, content: str) -> None:
    """Write file atomically to avoid partial writes."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


# =====================
# Core: fetch
# =====================

def fetch_latest_obs(series_id: str) -> Dict[str, str]:
    """Fetch the latest observation for a given FRED series (latest 1)."""
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
# History (JSON array): migrate + dedupe + retention
# =====================

def _make_history_key(row: Dict[str, str]) -> str:
    # Dedupe key: as_of_ts + series_id
    return f"{row.get('as_of_ts','NA')}|{row.get('series_id','NA')}"


def _load_history_array(history_json_path: str) -> List[Dict[str, str]]:
    if not os.path.exists(history_json_path):
        return []
    try:
        with open(history_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            out: List[Dict[str, str]] = []
            for x in data:
                if isinstance(x, dict):
                    out.append(x)
            return out
        return []
    except Exception:
        # If corrupted, do not crash; start fresh
        return []


def _load_history_from_jsonl_if_needed(history_json_path: str, history_jsonl_path: str) -> List[Dict[str, str]]:
    """
    Migration helper:
    - If history.json does not exist (or empty) but history.jsonl exists, read jsonl lines into array.
    """
    if os.path.exists(history_json_path):
        existing = _load_history_array(history_json_path)
        if existing:
            return existing

    if not os.path.exists(history_jsonl_path):
        return []

    migrated: List[Dict[str, str]] = []
    with open(history_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    migrated.append(obj)
            except Exception:
                continue
    return migrated


def _apply_retention(history: List[Dict[str, str]], keep_days: int) -> List[Dict[str, str]]:
    """
    Keep only entries within keep_days from the latest as_of date.
    Fail-open: if as_of_ts missing/unparseable, keep the entry.
    """
    if keep_days <= 0:
        return history

    latest: Optional[date] = None
    parsed: List[Tuple[Optional[date], Dict[str, str]]] = []
    for row in history:
        d = _parse_asof_date(str(row.get("as_of_ts", "")))
        parsed.append((d, row))
        if d is not None:
            if latest is None or d > latest:
                latest = d

    if latest is None:
        return history

    cutoff_ord = latest.toordinal() - keep_days
    kept: List[Dict[str, str]] = []
    for d, row in parsed:
        if d is None:
            kept.append(row)
        else:
            if d.toordinal() >= cutoff_ord:
                kept.append(row)
    return kept


def update_history_json(history_json_path: str, history_jsonl_path: str, new_rows: List[Dict[str, str]], keep_days: int) -> None:
    """
    Load (or migrate) history -> append unique -> apply retention -> write back as JSON array.
    """
    os.makedirs(os.path.dirname(history_json_path), exist_ok=True)

    history = _load_history_from_jsonl_if_needed(history_json_path, history_jsonl_path)

    existing_keys = set()
    for row in history:
        if isinstance(row, dict):
            existing_keys.add(_make_history_key(row))

    appended = 0
    for row in new_rows:
        k = _make_history_key(row)
        if k in existing_keys:
            continue
        history.append(row)
        existing_keys.add(k)
        appended += 1

    history = _apply_retention(history, keep_days=keep_days)

    # Stable ordering helps diffs: sort by as_of_ts then series_id (best-effort)
    def _sort_key(r: Dict[str, str]) -> Tuple[str, str]:
        return (str(r.get("as_of_ts", "")), str(r.get("series_id", "")))

    history.sort(key=_sort_key)

    content = json.dumps(history, ensure_ascii=False, separators=(",", ":")) + "\n"
    _atomic_write_text(history_json_path, content)

    print(f"History(JSON) updated: appended={appended}, keep_days={keep_days}, total={len(history)}")


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

    # latest.csv
    csv_path = "cache/latest.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # latest.json
    latest_json_path = "cache/latest.json"
    _atomic_write_text(
        latest_json_path,
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n"
    )

    # history.json (migrate from history.jsonl if present)
    history_json_path = "cache/history.json"
    history_jsonl_path = "cache/history.jsonl"  # legacy input for migration only
    update_history_json(history_json_path, history_jsonl_path, rows, keep_days=HISTORY_KEEP_DAYS)

    print(_redact_secrets(
        f"Wrote {csv_path} + {latest_json_path} + {history_json_path} @ {as_of_ts}"
    ))


if __name__ == "__main__":
    main()