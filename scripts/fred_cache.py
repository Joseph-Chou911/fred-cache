"""
fred_cache.py (FRED cache + audit + daily history)

Outputs:
- cache/latest.csv
- cache/latest.json
- cache/history.json            (daily cumulative; (as_of_date, series_id) unique, keep last run per day)
- cache/history.snapshot.json   (one-time snapshot before first normalization/migration)

Core:
- Fetch latest observation via FRED API (JSON endpoint)
- Fetch series page HTML meta:
    - Updated:
    - Next Release Date:
- Quality uses schedule first:
    - If next_release_date is known:
        * If as_of_date <= next_release_date + grace: do NOT penalize staleness (OK unless other errors)
        * If overdue > grace: WARN/ERR by overdue severity
    - Else fallback to staleness thresholds

Env:
- FRED_API_KEY (required)
- TIMEZONE (optional; default Asia/Taipei)
- HISTORY_KEEP_DAYS (optional; default 730)
- RELEASE_GRACE_DAYS (optional; default 2)   # tolerance after next release date
- OVERDUE_WARN_DAYS (optional; default 1)    # overdue days beyond grace => WARN
- OVERDUE_ERR_DAYS (optional; default 7)     # overdue days beyond grace => ERR
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

# Schedule-based quality knobs
RELEASE_GRACE_DAYS = _read_int_env("RELEASE_GRACE_DAYS", 2)
OVERDUE_WARN_DAYS = _read_int_env("OVERDUE_WARN_DAYS", 1)
OVERDUE_ERR_DAYS = _read_int_env("OVERDUE_ERR_DAYS", 7)

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
FRED_SERIES_PAGE = "https://fred.stlouisfed.org/series/"

FIELDNAMES = [
    "as_of_ts",
    "as_of_date",
    "series_id",
    "data_date",
    "value",
    "staleness_days",
    "fred_updated",
    "next_release_date",
    "release_overdue_days",
    "quality",
    "source_url",
    "notes",
]

RETRYABLE_STATUS = {500, 502, 503, 504}
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 20

# fallback staleness thresholds (only used when next_release_date is NA)
DEFAULT_WARN_STALE_DAYS = 7
DEFAULT_ERR_STALE_DAYS = 30

PER_SERIES_WARN_DAYS: Dict[str, int] = {
    "STLFSI4": 10,
    "NFCINONFINLEVERAGE": 10,
    "DTWEXBGS": 10,
}
PER_SERIES_ERR_DAYS: Dict[str, int] = {
    "STLFSI4": 45,
    "NFCINONFINLEVERAGE": 45,
    "DTWEXBGS": 45,
}


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


def _get_with_retry(url: str, params: Optional[dict] = None, timeout: int = TIMEOUT_SECONDS) -> requests.Response:
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
    try:
        return date.fromisoformat(d)
    except Exception:
        return None


def _asof_date_str(as_of_ts: str) -> Optional[str]:
    try:
        dt = datetime.fromisoformat(as_of_ts)
        return dt.date().isoformat()
    except Exception:
        return None


def _atomic_write_text(path: str, content: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def _snapshot_once(snapshot_path: str, raw_history: List[Dict[str, str]]) -> None:
    if os.path.exists(snapshot_path):
        return
    if not raw_history:
        return
    _atomic_write_text(snapshot_path, json.dumps(raw_history, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Snapshot created: {snapshot_path}")


def _parse_english_date_to_iso(s: str) -> Optional[str]:
    """
    Parse date like 'Jan 5, 2026' -> '2026-01-05'
    Return None if cannot parse.
    """
    s = s.strip()
    if not s or s == "NA":
        return None
    # normalize multiple spaces
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except Exception:
            continue
    return None


# =====================
# Fetch (Obs + Meta)
# =====================

def fetch_latest_obs(series_id: str) -> Dict[str, str]:
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
            "source_url": _safe_source_url(series_id),
            "notes": "warn:no_observations",
        }

    latest = obs[0]
    val = str(latest.get("value", "NA"))
    if val == ".":
        val = "NA"

    return {
        "series_id": series_id,
        "data_date": str(latest.get("date", "NA")),
        "value": val,
        "source_url": _safe_source_url(series_id),
        "notes": "NA",
    }


def fetch_series_meta(series_id: str) -> Dict[str, str]:
    """
    Fetch series HTML page and parse:
    - Updated: <text>
    - Next Release Date: <text>
    Fail-open: return NA if parsing fails.
    """
    url = f"{FRED_SERIES_PAGE}{series_id}"
    try:
        r = _get_with_retry(url, params=None, timeout=TIMEOUT_SECONDS)
        html = r.text

        # Try several patterns (FRED HTML can change)
        # We keep captured text short to avoid accidental huge matches.
        def _find(label: str) -> str:
            # Example: "Updated:  Dec 29, 2025 3:44 PM CST"
            # Example: "Next Release Date:  Jan 5, 2026"
            pat = rf"{re.escape(label)}\s*:\s*([^<\n\r]+)"
            m = re.search(pat, html, flags=re.IGNORECASE)
            if not m:
                return "NA"
            return m.group(1).strip()

        updated_raw = _find("Updated")
        next_raw = _find("Next Release Date")

        next_iso = _parse_english_date_to_iso(next_raw) if next_raw != "NA" else None

        return {
            "fred_updated": updated_raw if updated_raw else "NA",
            "next_release_date": next_iso if next_iso else "NA",
            "meta_url": url,
            "meta_notes": "NA",
        }
    except Exception as e:
        return {
            "fred_updated": "NA",
            "next_release_date": "NA",
            "meta_url": url,
            "meta_notes": f"warn:meta_fetch:{type(e).__name__}",
        }


# =====================
# Quality / staleness
# =====================

def _compute_staleness_days(as_of_date: str, data_date: str) -> Optional[int]:
    d_asof = _parse_iso_date(as_of_date)
    d_data = _parse_iso_date(data_date)
    if d_asof is None or d_data is None:
        return None
    return (d_asof - d_data).days


def _compute_overdue_days(as_of_date: str, next_release_date: str, grace_days: int) -> Optional[int]:
    d_asof = _parse_iso_date(as_of_date)
    d_next = _parse_iso_date(next_release_date)
    if d_asof is None or d_next is None:
        return None
    overdue = (d_asof - d_next).days - grace_days
    return max(0, overdue)


def _judge_quality(
    series_id: str,
    value: str,
    staleness_days: Optional[int],
    next_release_date: str,
    overdue_days: Optional[int],
    notes: str,
    meta_notes: str,
) -> Tuple[str, str]:
    """
    Return (quality, notes).

    Priority:
    1) Hard errors
    2) Schedule-based overdue if next_release_date is known
    3) Fallback staleness thresholds (when next_release_date is NA)
    """
    # hard errors
    if notes.startswith("err:"):
        return "ERR", notes
    if value == "NA":
        return "ERR", "err:value_na"
    if notes.startswith("warn:no_observations"):
        return "WARN", notes

    # meta fetch warning (don't break)
    if meta_notes.startswith("warn:"):
        # keep as WARN unless schedule says OK; we want visibility
        meta_warn = meta_notes
    else:
        meta_warn = "NA"

    # schedule-based
    if next_release_date != "NA":
        # overdue_days is already (as_of - next_release - grace), floored at 0
        if overdue_days is None:
            return "WARN", "warn:overdue_na"
        if overdue_days >= OVERDUE_ERR_DAYS:
            return "ERR", f"err:overdue:{overdue_days}d"
        if overdue_days >= OVERDUE_WARN_DAYS:
            return "WARN", f"warn:overdue:{overdue_days}d"

        # Not overdue => OK (but if meta fetch had warn, downgrade to WARN)
        if meta_warn != "NA":
            return "WARN", meta_warn
        return "OK", "NA"

    # fallback staleness thresholds
    if staleness_days is None:
        return ("WARN", meta_warn) if meta_warn != "NA" else ("WARN", "warn:staleness_na")

    warn_th = PER_SERIES_WARN_DAYS.get(series_id, DEFAULT_WARN_STALE_DAYS)
    err_th = PER_SERIES_ERR_DAYS.get(series_id, DEFAULT_ERR_STALE_DAYS)

    if staleness_days >= err_th:
        return "ERR", f"err:stale:{staleness_days}d"
    if staleness_days >= warn_th:
        return "WARN", f"warn:stale:{staleness_days}d"

    if meta_warn != "NA":
        return "WARN", meta_warn
    return "OK", "NA"


# =====================
# History (daily cumulative)
# =====================

def _load_history_array(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []
    except Exception:
        return []


def _load_history_from_jsonl_if_needed(history_json_path: str, history_jsonl_path: str) -> List[Dict[str, str]]:
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


def _normalize_to_daily_last(history: List[Dict[str, str]]) -> Tuple[Dict[Tuple[str, str], Dict[str, str]], List[Dict[str, str]]]:
    daily_map: Dict[Tuple[str, str], Dict[str, str]] = {}
    unknown_rows: List[Dict[str, str]] = []

    def _dt(ts: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    for row in history:
        as_of_ts = str(row.get("as_of_ts", ""))
        sid = str(row.get("series_id", ""))
        day = _asof_date_str(as_of_ts)

        if not sid:
            continue
        if day is None:
            unknown_rows.append(row)
            continue

        k = (day, sid)
        if k not in daily_map:
            daily_map[k] = row
            continue

        prev_ts = str(daily_map[k].get("as_of_ts", ""))
        prev_dt = _dt(prev_ts)
        curr_dt = _dt(as_of_ts)
        if prev_dt is None or curr_dt is None:
            if as_of_ts > prev_ts:
                daily_map[k] = row
        else:
            if curr_dt > prev_dt:
                daily_map[k] = row

    return daily_map, unknown_rows


def _apply_retention(daily_map: Dict[Tuple[str, str], Dict[str, str]], keep_days: int) -> Dict[Tuple[str, str], Dict[str, str]]:
    if keep_days <= 0:
        return daily_map

    latest: Optional[date] = None
    for (day_str, _sid) in daily_map.keys():
        d = _parse_iso_date(day_str)
        if d is None:
            continue
        if latest is None or d > latest:
            latest = d

    if latest is None:
        return daily_map

    cutoff_ord = latest.toordinal() - keep_days

    kept: Dict[Tuple[str, str], Dict[str, str]] = {}
    for (day_str, sid), row in daily_map.items():
        d = _parse_iso_date(day_str)
        if d is None:
            kept[(day_str, sid)] = row
            continue
        if d.toordinal() >= cutoff_ord:
            kept[(day_str, sid)] = row

    return kept


def update_history_json_daily_cumulative(
    history_json_path: str,
    history_jsonl_path: str,
    snapshot_path: str,
    new_rows: List[Dict[str, str]],
    keep_days: int,
) -> None:
    raw_history = _load_history_from_jsonl_if_needed(history_json_path, history_jsonl_path)
    _snapshot_once(snapshot_path, raw_history)

    daily_map, unknown_rows = _normalize_to_daily_last(raw_history)

    appended = 0
    overwritten = 0

    for row in new_rows:
        sid = str(row.get("series_id", ""))
        day = str(row.get("as_of_date", ""))
        if not sid or not day or day == "NA":
            unknown_rows.append(row)
            continue

        k = (day, sid)
        if k in daily_map:
            overwritten += 1
        else:
            appended += 1
        daily_map[k] = row  # overwrite same-day same-series

    daily_map = _apply_retention(daily_map, keep_days=keep_days)

    history_out: List[Dict[str, str]] = list(daily_map.values()) + unknown_rows
    history_out.sort(key=lambda r: (str(r.get("as_of_date", "")), str(r.get("series_id", "")), str(r.get("as_of_ts", ""))))

    _atomic_write_text(history_json_path, json.dumps(history_out, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(
        f"History(JSON daily cumulative) updated: appended={appended}, overwritten={overwritten}, "
        f"keep_days={keep_days}, total={len(history_out)}"
    )


# =====================
# Main
# =====================

def main() -> None:
    now = datetime.now(tz=TZ)
    as_of_ts = now.isoformat(timespec="seconds")
    as_of_date = now.date().isoformat()

    rows: List[Dict[str, str]] = []

    for sid in SERIES:
        # 1) obs
        try:
            obs = fetch_latest_obs(sid)
        except Exception as e:
            obs = {
                "series_id": sid,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(sid),
                "notes": f"err:fetch:{type(e).__name__}",
            }

        # 2) meta (Updated + Next Release Date)
        meta = fetch_series_meta(sid)

        # 3) staleness + overdue
        st = _compute_staleness_days(as_of_date, str(obs.get("data_date", "NA")))
        st_str = "NA" if st is None else str(st)

        next_rel = str(meta.get("next_release_date", "NA"))
        overdue = _compute_overdue_days(as_of_date, next_rel, RELEASE_GRACE_DAYS) if next_rel != "NA" else None
        overdue_str = "NA" if overdue is None else str(overdue)

        quality, notes = _judge_quality(
            series_id=sid,
            value=str(obs.get("value", "NA")),
            staleness_days=st,
            next_release_date=next_rel,
            overdue_days=overdue,
            notes=str(obs.get("notes", "NA")),
            meta_notes=str(meta.get("meta_notes", "NA")),
        )

        row = {
            "as_of_ts": as_of_ts,
            "as_of_date": as_of_date,
            "series_id": sid,
            "data_date": str(obs.get("data_date", "NA")),
            "value": str(obs.get("value", "NA")),
            "staleness_days": st_str,
            "fred_updated": str(meta.get("fred_updated", "NA")),
            "next_release_date": next_rel,
            "release_overdue_days": overdue_str,
            "quality": quality,
            "source_url": _redact_secrets(str(obs.get("source_url", ""))),
            "notes": notes,
        }
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
    _atomic_write_text(latest_json_path, json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n")

    # history.json daily cumulative
    history_json_path = "cache/history.json"
    history_jsonl_path = "cache/history.jsonl"  # legacy input only
    snapshot_path = "cache/history.snapshot.json"

    update_history_json_daily_cumulative(
        history_json_path=history_json_path,
        history_jsonl_path=history_jsonl_path,
        snapshot_path=snapshot_path,
        new_rows=rows,
        keep_days=HISTORY_KEEP_DAYS,
    )

    print(_redact_secrets(f"Wrote {csv_path} + {latest_json_path} + {history_json_path} @ {as_of_ts}"))


if __name__ == "__main__":
    main()