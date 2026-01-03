"""
fred_cache.py

Fetch latest observations for selected FRED series and write audit-friendly outputs:
- cache/latest.csv
- cache/latest.json
- cache/history.jsonl   (append-only with dedupe + rolling retention)

Design goals:
- 可審計：source_url 不含 api_key
- 安全：FRED_API_KEY 只用於 request；最後一道防線遮蔽
- 穩定：最小可控重試（timeout/連線錯誤/指定 5xx）+ backoff
- 一致：CSV 欄位固定，LF 換行，notes 使用 warn/err
- 可追溯：追加寫入 history.jsonl，並做去重與保留期限，避免 repo 無限制膨脹

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
        v = int(raw)
        return v
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

# Retry policy (minimal & auditable)
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


def _parse_iso_date(d: str) -> Optional[date]:
    """Parse YYYY-MM-DD to date; return None if not parseable."""
    try:
        return date.fromisoformat(d)
    except Exception:
        return None


def _parse_asof_date(as_of_ts: str) -> Optional[date]:
    """
    Parse ISO datetime string like 2026-01-03T14:01:39+08:00 -> date(2026,1,3)
    """
    try:
        # datetime.fromisoformat handles offset
        dt = datetime.fromisoformat(as_of_ts)
        return dt.date()
    except Exception:
        return None


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
# History (JSONL): dedupe + retention
# =====================

def _make_history_key(row: Dict[str, str]) -> str:
    """
    Dedupe key: as_of_ts + series_id
    - as_of_ts is run timestamp (same for all series in one run)
    - series_id identifies the metric
    This prevents duplicates if the workflow reruns the same minute.
    """
    return f"{row.get('as_of_ts','NA')}|{row.get('series_id','NA')}"


def _load_existing_keys(history_path: str) -> set[str]:
    """
    Load existing dedupe keys from history.jsonl.
    For performance, this scans the file once.
    Given daily runs + small file size (<= few MB/year), this is acceptable.
    """
    keys: set[str] = set()
    if not os.path.exists(history_path):
        return keys

    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    keys.add(_make_history_key(obj))
            except Exception:
                # If a line is corrupted, skip it (do not crash the run)
                continue
    return keys


def _apply_retention(all_lines: List[str], keep_days: int) -> List[str]:
    """
    Keep only lines whose as_of_ts date is within keep_days from the latest as_of date.
    If cannot parse date, keep the line (fail-open, do not lose data silently).
    """
    if keep_days <= 0:
        return all_lines  # retention disabled

    latest_date: Optional[date] = None
    parsed: List[Tuple[Optional[date], str]] = []

    for line in all_lines:
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            asof = obj.get("as_of_ts", "")
            d = _parse_asof_date(asof)
        except Exception:
            d = None
        parsed.append((d, s))
        if d is not None:
            if latest_date is None or d > latest_date:
                latest_date = d

    if latest_date is None:
        # can't parse any dates -> keep all
        return [s for _, s in parsed]

    cutoff = latest_date.toordinal() - keep_days
    kept: List[str] = []
    for d, s in parsed:
        if d is None:
            kept.append(s)  # fail-open
        else:
            if d.toordinal() >= cutoff:
                kept.append(s)

    return kept


def update_history_jsonl(history_path: str, new_rows: List[Dict[str, str]], keep_days: int) -> None:
    """
    Append new rows to history.jsonl with dedupe, then apply retention.
    """
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    existing_keys = _load_existing_keys(history_path)

    # 1) Append new unique lines
    appended = 0
    with open(history_path, "a", encoding="utf-8") as f:
        for row in new_rows:
            k = _make_history_key(row)
            if k in existing_keys:
                continue
            # compact JSON per line
            line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            f.write(line + "\n")
            existing_keys.add(k)
            appended += 1

    # 2) Retention rewrite (only if file exists and keep_days enabled)
    if keep_days > 0:
        with open(history_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        kept_lines = _apply_retention(lines, keep_days=keep_days)

        # Rewrite only if something was dropped (avoid unnecessary diffs)
        if len(kept_lines) != len([ln for ln in lines if ln.strip()]):
            with open(history_path, "w", encoding="utf-8") as f:
                for ln in kept_lines:
                    if ln.strip():
                        f.write(ln.strip() + "\n")

    print(f"History updated: appended={appended}, keep_days={keep_days}")


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

    # ---- Write latest CSV ----
    csv_path = "cache/latest.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    # ---- Write latest JSON ----
    json_path = "cache/latest.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(rows, jf, ensure_ascii=False, separators=(",", ":"))
        jf.write("\n")

    # ---- Update history JSONL ----
    history_path = "cache/history.jsonl"
    update_history_jsonl(history_path, rows, keep_days=HISTORY_KEEP_DAYS)

    print(_redact_secrets(f"Wrote {csv_path} + {json_path} + {history_path} @ {as_of_ts}"))


if __name__ == "__main__":
    main()