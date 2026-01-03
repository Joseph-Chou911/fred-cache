"""
fred_cache.py

Outputs:
- cache/latest.csv
- cache/latest.json
- cache/history.json  (JSON array, daily-dedup: keep LAST run per day per series)

Key change (daily dedup):
- history 以 (as_of_date, series_id) 做唯一鍵
- 同一天同一個 series 若你手動重跑，會覆蓋成當天「最後一次」快照
  -> 避免同一天多筆造成 lookback 統計權重偏差

Safety:
- 原子寫入（.tmp -> replace）
- 第一次啟用新規則時，若偵測到 history.json 內存在「同日多筆」或單純非空，
  會先備份一份 cache/history.snapshot.json（僅一次）

Env:
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


def _parse_asof_dt(as_of_ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(as_of_ts)
    except Exception:
        return None


def _asof_date_key(as_of_ts: str) -> Optional[str]:
    dt = _parse_asof_dt(as_of_ts)
    if dt is None:
        return None
    return dt.date().isoformat()  # YYYY-MM-DD


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
# History (JSON array): migrate + daily-dedup + retention
# =====================

def _load_history_array(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            out: List[Dict[str, str]] = []
            for x in data:
                if isinstance(x, dict):
                    out.append(x)
            return out
        return []
    except Exception:
        # Fail-open: if corrupted, don't crash; start fresh
        return []


def _load_history_from_jsonl_if_needed(history_json_path: str, history_jsonl_path: str) -> List[Dict[str, str]]:
    """
    Migration helper:
    - If history.json is empty/missing but history.jsonl exists, read jsonl lines into array.
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


def _latest_date_in_history(history: List[Dict[str, str]]) -> Optional[date]:
    latest: Optional[date] = None
    for row in history:
        as_of_ts = str(row.get("as_of_ts", ""))
        dt = _parse_asof_dt(as_of_ts)
        if dt is None:
            continue
        d = dt.date()
        if latest is None or d > latest:
            latest = d
    return latest


def _apply_retention_daily_map(
    daily_map: Dict[Tuple[str, str], Dict[str, str]],
    unknown_rows: List[Dict[str, str]],
    keep_days: int,
) -> Tuple[Dict[Tuple[str, str], Dict[str, str]], List[Dict[str, str]]]:
    """
    Retention window based on latest as_of_date among known daily keys.
    - daily_map keys: (YYYY-MM-DD, series_id)
    - unknown_rows: rows with unparseable as_of_ts (kept, fail-open)
    """
    if keep_days <= 0:
        return daily_map, unknown_rows

    latest_day: Optional[date] = None
    for (day_str, _sid) in daily_map.keys():
        try:
            d = date.fromisoformat(day_str)
        except Exception:
            continue
        if latest_day is None or d > latest_day:
            latest_day = d

    if latest_day is None:
        return daily_map, unknown_rows

    cutoff_ord = latest_day.toordinal() - keep_days

    kept_map: Dict[Tuple[str, str], Dict[str, str]] = {}
    for (day_str, sid), row in daily_map.items():
        try:
            d = date.fromisoformat(day_str)
        except Exception:
            # If day_str is somehow bad, keep it (fail-open)
            kept_map[(day_str, sid)] = row
            continue
        if d.toordinal() >= cutoff_ord:
            kept_map[(day_str, sid)] = row

    return kept_map, unknown_rows


def _normalize_to_daily_last(history: List[Dict[str, str]]) -> Tuple[Dict[Tuple[str, str], Dict[str, str]], List[Dict[str, str]]]:
    """
    Normalize history to "daily last per series":
    - For parseable as_of_ts: keep the row with max as_of_ts for each (as_of_date, series_id)
    - For unparseable as_of_ts: keep rows separately (fail-open)
    """
    daily_map: Dict[Tuple[str, str], Dict[str, str]] = {}
    unknown_rows: List[Dict[str, str]] = []

    for row in history:
        if not isinstance(row, dict):
            continue
        as_of_ts = str(row.get("as_of_ts", ""))
        sid = str(row.get("series_id", ""))
        day_key = _asof_date_key(as_of_ts)
        if not sid:
            continue

        if day_key is None:
            unknown_rows.append(row)
            continue

        k = (day_key, sid)
        if k not in daily_map:
            daily_map[k] = row
            continue

        # Compare timestamps; keep the later one
        prev_ts = str(daily_map[k].get("as_of_ts", ""))
        prev_dt = _parse_asof_dt(prev_ts)
        curr_dt = _parse_asof_dt(as_of_ts)
        if prev_dt is None or curr_dt is None:
            # Fallback: lexicographic ISO compare (usually safe here)
            if as_of_ts > prev_ts:
                daily_map[k] = row
        else:
            if curr_dt > prev_dt:
                daily_map[k] = row

    return daily_map, unknown_rows


def _should_snapshot(history_json_path: str, snapshot_path: str, history: List[Dict[str, str]]) -> bool:
    """
    Create snapshot once when moving to daily-dedup, to avoid anxiety about irreversible change.
    Rule:
    - If snapshot doesn't exist, and history is non-empty -> snapshot.
    """
    if os.path.exists(snapshot_path):
        return False
    if not history:
        return False
    # Snapshot is cheap; do it once.
    return True


def update_history_json_daily_last(
    history_json_path: str,
    history_jsonl_path: str,
    snapshot_path: str,
    new_rows: List[Dict[str, str]],
    keep_days: int,
) -> None:
    """
    Load (or migrate) history -> (optional snapshot once) -> normalize daily-last -> merge new rows (overwrite same-day same-series)
    -> retention -> write history.json.
    """
    os.makedirs(os.path.dirname(history_json_path), exist_ok=True)

    # Load or migrate
    raw_history = _load_history_from_jsonl_if_needed(history_json_path, history_jsonl_path)

    # One-time snapshot for safety
    if _should_snapshot(history_json_path, snapshot_path, raw_history):
        _atomic_write_text(snapshot_path, json.dumps(raw_history, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"Snapshot created: {snapshot_path}")

    # Normalize existing history to daily-last per series
    daily_map, unknown_rows = _normalize_to_daily_last(raw_history)

    # Merge new rows: overwrite same-day same-series (daily-last behavior)
    overwritten = 0
    appended = 0
    for row in new_rows:
        sid = str(row.get("series_id", ""))
        as_of_ts = str(row.get("as_of_ts", ""))
        day_key = _asof_date_key(as_of_ts)
        if not sid or day_key is None:
            # Shouldn't happen, but fail-open
            unknown_rows.append(row)
            continue

        k = (day_key, sid)
        if k in daily_map:
            overwritten += 1
        else:
            appended += 1
        daily_map[k] = row

    # Retention
    daily_map, unknown_rows = _apply_retention_daily_map(daily_map, unknown_rows, keep_days=keep_days)

    # Rebuild list
    history: List[Dict[str, str]] = list(daily_map.values()) + unknown_rows

    # Stable sort by as_of_ts then series_id
    history.sort(key=lambda r: (str(r.get("as_of_ts", "")), str(r.get("series_id", ""))))

    # Write back
    _atomic_write_text(history_json_path, json.dumps(history, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(
        f"History(JSON daily-last) updated: appended={appended}, overwritten={overwritten}, "
        f"keep_days={keep_days}, total={len(history)}"
    )


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

    # ---- latest.csv ----
    csv_path = "cache/latest.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # ---- latest.json ----
    latest_json_path = "cache/latest.json"
    _atomic_write_text(latest_json_path, json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n")

    # ---- history.json (daily-last) ----
    history_json_path = "cache/history.json"
    history_jsonl_path = "cache/history.jsonl"  # legacy input for migration only
    snapshot_path = "cache/history.snapshot.json"  # one-time safety snapshot

    update_history_json_daily_last(
        history_json_path=history_json_path,
        history_jsonl_path=history_jsonl_path,
        snapshot_path=snapshot_path,
        new_rows=rows,
        keep_days=HISTORY_KEEP_DAYS,
    )

    print(_redact_secrets(f"Wrote {csv_path} + {latest_json_path} + {history_json_path} @ {as_of_ts}"))


if __name__ == "__main__":
    main()