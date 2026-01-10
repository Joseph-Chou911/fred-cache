#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRED cache generator
- per-series history upsert + cap_per_series
- backfill self-heal to reach target_valid observations (effective rows)
- audit-friendly outputs

Outputs (under ./cache):
- latest.csv
- latest.json
- history.json              : JSON array (record-per-line) for citation
- history_lite.json         : per series keep last target_valid records, same format
- history.snapshot.json
- dq_state.json
- backfill_state.json       : v2 (last_attempt only)
- manifest.json

Env:
- FRED_API_KEY (required)
- TIMEZONE (optional, default "Asia/Taipei")
- GITHUB_REPOSITORY (optional)
- DATA_SHA (optional)
- GITHUB_SHA (fallback)
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from zoneinfo import ZoneInfo  # py3.9+
except ImportError:
    ZoneInfo = None  # type: ignore


# -------------------------
# Config
# -------------------------
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
CACHE_DIR = Path("cache")

SERIES_IDS: List[str] = [
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
    "NFCINONFINLEVERAGE",
    "T10Y2Y",
    "T10Y3M",
]

CSV_FIELDNAMES = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]

# network policy
TIMEOUT_SECS = 20
MAX_ATTEMPTS = 3
BACKOFF_SCHEDULE = [2, 4, 8]
RETRY_STATUS = {429, 500, 502, 503, 504}

# history policy
CAP_PER_SERIES = 400  # storage cap (per series)
TARGET_VALID = 252    # statistical window target (effective rows)
FETCH_LIMIT = 420     # request limit for backfill (to compensate missing values)

# backfill behavior
MAX_NO_PROGRESS = 5   # if attempt but no progress for N times, pause attempts for that series
COOLDOWN_RUNS = 3     # after hitting MAX_NO_PROGRESS, skip next N runs (simple throttle)

BACKFILL_STATE_SCHEMA = "backfill_state_v2_last_attempt_only"

# deterministic Taipei fallback
TAIPEI_TZ_FALLBACK = timezone(timedelta(hours=8))


# -------------------------
# Time / Utils
# -------------------------
def _tzinfo():
    """Returns tzinfo. Must never crash; ultimate fallback is fixed +08:00 for Asia/Taipei."""
    tz_name = (os.getenv("TIMEZONE", "Asia/Taipei") or "").strip() or "Asia/Taipei"

    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)  # type: ignore[arg-type]
        except Exception:
            try:
                return ZoneInfo("Asia/Taipei")  # type: ignore[arg-type]
            except Exception:
                return TAIPEI_TZ_FALLBACK

    if tz_name == "Asia/Taipei":
        return TAIPEI_TZ_FALLBACK
    return timezone.utc


def _now_iso(tz) -> str:
    return datetime.now(tz).replace(microsecond=0).isoformat()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_ymd(s: str) -> bool:
    return isinstance(s, str) and len(s) == 10 and s[4] == "-" and s[7] == "-"


def _redact_secrets(s: str) -> str:
    if not s:
        return s
    api_key = os.getenv("FRED_API_KEY", "")
    if api_key and api_key in s:
        s = s.replace(api_key, "***REDACTED***")
    s = re.sub(r"api_key=[^&\s]+", "api_key=***REDACTED***", s, flags=re.IGNORECASE)
    return s


def _safe_source_url(series_id: str, limit_n: int) -> str:
    """DO NOT include api_key in source_url."""
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": int(limit_n),
    }
    qs = "&".join(
        [f"{k}={requests.utils.quote(str(params[k]))}" for k in ["series_id", "file_type", "sort_order", "limit"]]
    )
    return f"{BASE_URL}?{qs}"


# -------------------------
# HTTP
# -------------------------
@dataclass
class FetchResult:
    record: Dict[str, str]
    warn: Optional[str] = None
    err: Optional[str] = None
    attempts: int = 0
    status: Optional[int] = None


def _http_get_with_retry(
    session: requests.Session, url: str, params: Dict[str, Any]
) -> Tuple[Optional[requests.Response], Optional[str], int, Optional[int]]:
    """Returns: (response or None, error_code or None, attempts_used, last_status)"""
    last_status: Optional[int] = None

    for i in range(MAX_ATTEMPTS):
        attempt = i + 1
        try:
            r = session.get(url, params=params, timeout=TIMEOUT_SECS)
            last_status = r.status_code

            if r.status_code == 200:
                return r, None, attempt, last_status

            if r.status_code in RETRY_STATUS:
                if attempt < MAX_ATTEMPTS:
                    time.sleep(BACKOFF_SCHEDULE[i])
                    continue
                return None, f"http_{r.status_code}", attempt, last_status

            return None, f"http_{r.status_code}", attempt, last_status

        except requests.Timeout:
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SCHEDULE[i])
                continue
            return None, "timeout", attempt, last_status

        except requests.RequestException as e:
            code = f"req_exc:{type(e).__name__}"
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SCHEDULE[i])
                continue
            return None, code, attempt, last_status

    return None, "unknown", MAX_ATTEMPTS, last_status


def fetch_latest_obs(session: requests.Session, series_id: str, as_of_ts: str) -> FetchResult:
    api_key = os.getenv("FRED_API_KEY", "")

    if not api_key or len(api_key) < 10:
        return FetchResult(
            record={
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(series_id, 1),
                "notes": "err:missing_api_key",
            },
            err="missing_api_key",
            attempts=0,
            status=None,
        )

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }

    r, err_code, attempts, last_status = _http_get_with_retry(session, BASE_URL, params)

    if r is None:
        notes = f"err:{err_code}"
        warn = f"warn:retried_{attempts}x" if attempts > 1 else None
        return FetchResult(
            record={
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(series_id, 1),
                "notes": notes,
            },
            warn=warn,
            err=err_code,
            attempts=attempts,
            status=last_status,
        )

    try:
        payload = r.json()
    except Exception:
        return FetchResult(
            record={
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(series_id, 1),
                "notes": "err:bad_json",
            },
            err="bad_json",
            attempts=attempts,
            status=last_status,
        )

    obs = payload.get("observations", [])
    if not obs:
        return FetchResult(
            record={
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(series_id, 1),
                "notes": "warn:no_observations",
            },
            warn="no_observations",
            attempts=attempts,
            status=last_status,
        )

    o0 = obs[0]
    date = str(o0.get("date", "NA"))
    value = str(o0.get("value", "NA"))

    if value.strip() in {"", "NA", "."}:
        notes = "warn:missing_value"
        warn = "missing_value"
        value_out = "NA"
    else:
        notes = "NA"
        warn = None
        value_out = value

    if attempts > 1 and notes == "NA":
        notes = f"warn:retried_{attempts}x"
        warn = f"retried_{attempts}x"

    return FetchResult(
        record={
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": date,
            "value": value_out,
            "source_url": _safe_source_url(series_id, 1),
            "notes": notes,
        },
        warn=warn,
        err=None,
        attempts=attempts,
        status=last_status,
    )


def fetch_recent_observations(
    session: requests.Session, series_id: str, as_of_ts: str, limit_n: int
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Backfill a window of recent observations (desc), filter invalid values.
    Returns (rows, meta) where meta is audit info.
    """
    api_key = os.getenv("FRED_API_KEY", "")

    meta: Dict[str, Any] = {
        "series_id": series_id,
        "limit": int(limit_n),
        "attempts": 0,
        "http_status": "NA",
        "err": "NA",
        "count_raw": 0,
        "count_kept": 0,
        "source_url": _safe_source_url(series_id, limit_n),
    }

    if not api_key or len(api_key) < 10:
        meta["err"] = "missing_api_key"
        return [], meta

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": int(limit_n),
    }

    r, err_code, attempts, last_status = _http_get_with_retry(session, BASE_URL, params)
    meta["attempts"] = attempts
    meta["http_status"] = last_status if last_status is not None else "NA"

    if r is None:
        meta["err"] = err_code or "unknown"
        return [], meta

    try:
        payload = r.json()
    except Exception:
        meta["err"] = "bad_json"
        return [], meta

    obs = payload.get("observations", [])
    meta["count_raw"] = len(obs)

    out: List[Dict[str, str]] = []
    for o in obs:
        dd = str(o.get("date", "NA"))
        vv = str(o.get("value", "NA"))

        if vv.strip() in {"", "NA", "."}:
            continue
        if not _is_ymd(dd):
            continue

        note = "backfill"
        if attempts > 1:
            note = f"backfill_warn:retried_{attempts}x"

        out.append(
            {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": dd,
                "value": vv,
                "source_url": _safe_source_url(series_id, limit_n),
                "notes": note,
            }
        )

    meta["count_kept"] = len(out)
    meta["err"] = "NA"
    return out, meta


# -------------------------
# File IO
# -------------------------
def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "NA") for k in CSV_FIELDNAMES})


def _write_json_compact(path: Path, obj: Any) -> Tuple[bool, str]:
    """Write compact JSON (single-line). Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        return True, "ok"
    except PermissionError:
        return False, "err:permission"
    except OSError as e:
        return False, f"err:oserror:{type(e).__name__}"
    except Exception as e:
        return False, f"err:write_exc:{type(e).__name__}"


def _write_json_pretty(path: Path, obj: Any) -> Tuple[bool, str]:
    """Write pretty JSON (indent=2). Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True, "ok"
    except PermissionError:
        return False, "err:permission"
    except OSError as e:
        return False, f"err:oserror:{type(e).__name__}"
    except Exception as e:
        return False, f"err:write_exc:{type(e).__name__}"


def _write_json_array_record_per_line(path: Path, rows: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Write a JSON array but force each record on its own line (valid JSON).
    This is the "可引用格式".
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write("[\n")
            for i, r in enumerate(rows):
                s = json.dumps(r, ensure_ascii=False, separators=(",", ":"))
                if i < len(rows) - 1:
                    f.write(s + ",\n")
                else:
                    f.write(s + "\n")
            f.write("]\n")
        return True, "ok"
    except PermissionError:
        return False, "err:permission"
    except OSError as e:
        return False, f"err:oserror:{type(e).__name__}"
    except Exception as e:
        return False, f"err:write_exc:{type(e).__name__}"


def _load_json_list(path: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Load JSON list safely. Never raises. Returns (list, status_code)."""
    if not path.exists():
        return [], "ok:missing_file"

    try:
        text = path.read_text(encoding="utf-8")
    except PermissionError:
        return [], "err:permission"
    except OSError as e:
        return [], f"err:oserror:{type(e).__name__}"

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return [], "warn:json_decode_error"
    except Exception as e:
        return [], f"err:json_load_exc:{type(e).__name__}"

    if isinstance(obj, list):
        out: List[Dict[str, Any]] = []
        for x in obj:
            if isinstance(x, dict):
                out.append(x)
        return out, "ok"
    return [], "warn:not_a_list"


def _load_json_dict(path: Path) -> Tuple[Dict[str, Any], str]:
    """Load JSON dict safely. Never raises."""
    if not path.exists():
        return {}, "ok:missing_file"
    try:
        text = path.read_text(encoding="utf-8")
    except PermissionError:
        return {}, "err:permission"
    except OSError as e:
        return {}, f"err:oserror:{type(e).__name__}"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {}, "warn:json_decode_error"
    except Exception as e:
        return {}, f"err:json_load_exc:{type(e).__name__}"
    if isinstance(obj, dict):
        return obj, "ok"
    return {}, "warn:not_a_dict"


# -------------------------
# History ops
# -------------------------
def _upsert_history_per_series(
    existing: List[Dict[str, Any]],
    new_rows: List[Dict[str, str]],
    cap_per_series: int = CAP_PER_SERIES,
) -> List[Dict[str, str]]:
    """
    Key = (series_id, data_date)
    Same key reruns overwrite by greatest as_of_ts.
    Keep only last `cap_per_series` per series by (data_date, as_of_ts).
    """
    best: Dict[Tuple[str, str], Dict[str, str]] = {}

    def take(r_any: Dict[str, Any]) -> None:
        sid = str(r_any.get("series_id", "")).strip()
        dd = str(r_any.get("data_date", "")).strip()
        as_of_ts = str(r_any.get("as_of_ts", "")).strip()

        if not sid or not dd or dd == "NA" or not _is_ymd(dd) or not as_of_ts:
            return

        rec: Dict[str, str] = {
            "as_of_ts": as_of_ts,
            "series_id": sid,
            "data_date": dd,
            "value": str(r_any.get("value", "NA")),
            "source_url": str(r_any.get("source_url", "NA")),
            "notes": str(r_any.get("notes", "NA")),
        }

        key = (sid, dd)
        prev = best.get(key)
        if prev is None or as_of_ts > prev.get("as_of_ts", ""):
            best[key] = rec

    for r in existing:
        if isinstance(r, dict):
            take(r)

    for r in new_rows:
        take(r)

    by_series: Dict[str, List[Dict[str, str]]] = {}
    for (sid, _dd), rec in best.items():
        by_series.setdefault(sid, []).append(rec)

    capped: List[Dict[str, str]] = []
    for sid, arr in by_series.items():
        arr.sort(key=lambda x: (x.get("data_date", ""), x.get("as_of_ts", "")))
        if len(arr) > cap_per_series:
            arr = arr[-cap_per_series:]
        capped.extend(arr)

    capped.sort(key=lambda x: (x.get("series_id", ""), x.get("data_date", ""), x.get("as_of_ts", "")))
    return capped


def _count_valid_per_series(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    seen: Dict[Tuple[str, str], bool] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id", "")).strip()
        dd = str(r.get("data_date", "")).strip()
        vv = str(r.get("value", "NA")).strip()
        if not sid or not _is_ymd(dd) or dd == "NA":
            continue
        if vv in {"NA", ".", ""}:
            continue
        key = (sid, dd)
        if key in seen:
            continue
        seen[key] = True
        counts[sid] = counts.get(sid, 0) + 1
    return counts


def _make_history_lite(rows: List[Dict[str, str]], per_series_keep: int) -> List[Dict[str, str]]:
    by_series: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        sid = r.get("series_id", "")
        if not sid:
            continue
        by_series.setdefault(sid, []).append(r)

    lite: List[Dict[str, str]] = []
    for sid, arr in by_series.items():
        arr.sort(key=lambda x: (x.get("data_date", ""), x.get("as_of_ts", "")))
        if len(arr) > per_series_keep:
            arr = arr[-per_series_keep:]
        lite.extend(arr)

    lite.sort(key=lambda x: (x.get("series_id", ""), x.get("data_date", ""), x.get("as_of_ts", "")))
    return lite


# -------------------------
# Backfill state (v2)
# -------------------------
def _init_backfill_state_v2() -> Dict[str, Any]:
    return {
        "schema_version": BACKFILL_STATE_SCHEMA,
        "series": {},
    }


def _normalize_backfill_state_v2(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Force v2 structure. If old state exists, we ignore old fields and keep only what's needed.
    """
    if not isinstance(raw, dict):
        return _init_backfill_state_v2()

    out = _init_backfill_state_v2()
    series = raw.get("series")
    if isinstance(series, dict):
        for sid, s in series.items():
            if not isinstance(sid, str):
                continue
            if not isinstance(s, dict):
                continue
            out["series"][sid] = {
                "done": bool(s.get("done", False)),
                "have_valid": int(s.get("have_valid", 0) or 0),
                "target_valid": int(s.get("target_valid", TARGET_VALID) or TARGET_VALID),
                "fetch_limit": int(s.get("fetch_limit", FETCH_LIMIT) or FETCH_LIMIT),
                "last_attempt_at": str(s.get("last_attempt_at", "NA")),
                "last_http_status": s.get("last_http_status", "NA"),
                "last_attempts": s.get("last_attempts", "NA"),
                "last_err": str(s.get("last_err", "NA")),
                "last_count_raw": s.get("last_count_raw", "NA"),
                "last_count_kept": s.get("last_count_kept", "NA"),
                "consecutive_no_progress": int(s.get("consecutive_no_progress", 0) or 0),
                "cooldown_runs_left": int(s.get("cooldown_runs_left", 0) or 0),
            }
    return out


def _repo_slug() -> str:
    return os.getenv("GITHUB_REPOSITORY", "Joseph-Chou911/fred-cache")


def _data_sha() -> str:
    return os.getenv("DATA_SHA") or os.getenv("GITHUB_SHA") or "NA"


def _pinned_urls(repo: str, sha: str) -> Dict[str, str]:
    if sha == "NA":
        return {
            "latest_json": "NA",
            "history_json": "NA",
            "history_lite_json": "NA",
            "latest_csv": "NA",
            "manifest_json": "NA",
        }
    base = f"https://raw.githubusercontent.com/{repo}/{sha}/cache"
    return {
        "latest_json": f"{base}/latest.json",
        "history_json": f"{base}/history.json",
        "history_lite_json": f"{base}/history_lite.json",
        "latest_csv": f"{base}/latest.csv",
        "manifest_json": f"{base}/manifest.json",
    }


# -------------------------
# Main
# -------------------------
def main() -> int:
    tz = _tzinfo()
    as_of_ts = _now_iso(tz)
    generated_at_utc = _now_utc_iso()

    session = requests.Session()
    session.headers.update({"User-Agent": "fred-cache/3.2"})

    rows: List[Dict[str, str]] = []

    dq: Dict[str, Any] = {
        "as_of_ts": as_of_ts,
        "generated_at_utc": generated_at_utc,
        "fs": {},
        "series": {},
        "summary": {"ok": 0, "warn": 0, "err": 0},
        "backfill": {
            "target_valid": TARGET_VALID,
            "fetch_limit": FETCH_LIMIT,
            "attempted": {},
            "meta": {},
            "counts_before": {},
            "counts_after": {},
        },
    }

    # 1) Fetch latest
    for sid in SERIES_IDS:
        res = fetch_latest_obs(session, sid, as_of_ts)
        rec = {k: _redact_secrets(str(v)) for k, v in res.record.items()}
        rows.append(rec)

        note = rec.get("notes", "NA")
        if note.startswith("err:"):
            dq["summary"]["err"] += 1
        elif note.startswith("warn:"):
            dq["summary"]["warn"] += 1
        else:
            dq["summary"]["ok"] += 1

        dq["series"][sid] = {
            "notes": note,
            "attempts": res.attempts,
            "http_status": res.status if res.status is not None else "NA",
            "data_date": rec.get("data_date", "NA"),
            "value": rec.get("value", "NA"),
        }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    latest_csv = CACHE_DIR / "latest.csv"
    latest_json = CACHE_DIR / "latest.json"
    history_json = CACHE_DIR / "history.json"
    history_lite_json = CACHE_DIR / "history_lite.json"
    history_snapshot = CACHE_DIR / "history.snapshot.json"
    dq_state = CACHE_DIR / "dq_state.json"
    backfill_state_path = CACHE_DIR / "backfill_state.json"
    manifest = CACHE_DIR / "manifest.json"

    # 2) Write latest outputs
    try:
        _write_csv(latest_csv, rows)
        dq["fs"]["latest_csv"] = "ok"
    except Exception as e:
        dq["fs"]["latest_csv"] = f"err:csv_write_exc:{type(e).__name__}"

    ok, st = _write_json_compact(latest_json, rows)
    dq["fs"]["latest_json"] = st

    ok, st = _write_json_compact(history_snapshot, rows)
    dq["fs"]["history_snapshot_write"] = st

    # 3) Load existing history
    existing_hist, read_status = _load_json_list(history_json)
    dq["fs"]["history_json_read"] = read_status

    counts_before = _count_valid_per_series(existing_hist)
    dq["backfill"]["counts_before"] = counts_before

    # 4) Load backfill state (v2)
    raw_state, st_read = _load_json_dict(backfill_state_path)
    dq["fs"]["backfill_state_read"] = st_read
    state = _normalize_backfill_state_v2(raw_state)
    series_state: Dict[str, Any] = state.get("series", {})
    if not isinstance(series_state, dict):
        series_state = {}
        state["series"] = series_state

    # 5) Decide / attempt backfill
    backfill_rows: List[Dict[str, str]] = []
    attempt_meta: Dict[str, Dict[str, Any]] = {}

    for sid in SERIES_IDS:
        have_before = int(counts_before.get(sid, 0))

        # If already enough, skip (hard rule, independent of state flags)
        if have_before >= TARGET_VALID:
            dq["backfill"]["attempted"][sid] = "skip:already_enough"
            continue

        # cooldown / no-progress throttle (optional but useful)
        s = series_state.get(sid, {}) if isinstance(series_state.get(sid, {}), dict) else {}
        cooldown_left = int(s.get("cooldown_runs_left", 0) or 0)
        if cooldown_left > 0:
            s["cooldown_runs_left"] = cooldown_left - 1
            series_state[sid] = s
            dq["backfill"]["attempted"][sid] = f"skip:cooldown_runs_left={cooldown_left}"
            continue

        # If this series has been stuck too long, enter cooldown
        cnp = int(s.get("consecutive_no_progress", 0) or 0)
        if cnp >= MAX_NO_PROGRESS:
            s["cooldown_runs_left"] = COOLDOWN_RUNS
            series_state[sid] = s
            dq["backfill"]["attempted"][sid] = f"skip:too_many_no_progress (cnp={cnp})"
            continue

        # Attempt backfill using FETCH_LIMIT (not just 252)
        bf_rows, meta = fetch_recent_observations(session, sid, as_of_ts, FETCH_LIMIT)
        attempt_meta[sid] = meta
        dq["backfill"]["meta"][sid] = meta

        if len(bf_rows) > 0:
            backfill_rows.extend(bf_rows)
            dq["backfill"]["attempted"][sid] = "attempted:true"
        else:
            dq["backfill"]["attempted"][sid] = f"attempted:false (err={meta.get('err','NA')})"

    # 6) Merge: existing + backfill + latest
    merged_hist = _upsert_history_per_series(existing_hist, backfill_rows, cap_per_series=CAP_PER_SERIES)
    merged_hist = _upsert_history_per_series(merged_hist, rows, cap_per_series=CAP_PER_SERIES)

    counts_after = _count_valid_per_series(merged_hist)
    dq["backfill"]["counts_after"] = counts_after

    # 7) Update backfill_state v2 using *post-merge* counts (authoritative)
    for sid in SERIES_IDS:
        have_before = int(counts_before.get(sid, 0))
        have_after = int(counts_after.get(sid, 0))
        done = have_after >= TARGET_VALID

        s = series_state.get(sid, {}) if isinstance(series_state.get(sid, {}), dict) else {}
        prev_cnp = int(s.get("consecutive_no_progress", 0) or 0)

        attempted_this_run = sid in attempt_meta
        progress = have_after - have_before

        if attempted_this_run:
            if progress <= 0:
                new_cnp = prev_cnp + 1
            else:
                new_cnp = 0
        else:
            new_cnp = prev_cnp  # unchanged

        # If we reached target, reset counters (keep it calm)
        if done:
            new_cnp = 0
            s["cooldown_runs_left"] = 0

        # Always record authoritative snapshot fields
        s["done"] = bool(done)
        s["have_valid"] = int(have_after)
        s["target_valid"] = int(TARGET_VALID)
        s["fetch_limit"] = int(FETCH_LIMIT)
        s["consecutive_no_progress"] = int(new_cnp)
        s["cooldown_runs_left"] = int(s.get("cooldown_runs_left", 0) or 0)

        # Only update last_attempt_* if attempted this run
        if attempted_this_run:
            meta = attempt_meta[sid]
            s["last_attempt_at"] = as_of_ts
            s["last_http_status"] = meta.get("http_status", "NA")
            s["last_attempts"] = meta.get("attempts", "NA")
            s["last_err"] = meta.get("err", "NA")
            s["last_count_raw"] = meta.get("count_raw", "NA")
            s["last_count_kept"] = meta.get("count_kept", "NA")

        # Ensure keys exist even before first attempt
        s.setdefault("last_attempt_at", "NA")
        s.setdefault("last_http_status", "NA")
        s.setdefault("last_attempts", "NA")
        s.setdefault("last_err", "NA")
        s.setdefault("last_count_raw", "NA")
        s.setdefault("last_count_kept", "NA")

        series_state[sid] = s

    state["schema_version"] = BACKFILL_STATE_SCHEMA
    state["as_of_ts"] = as_of_ts
    state["generated_at_utc"] = generated_at_utc
    state["target_valid"] = TARGET_VALID
    state["fetch_limit"] = FETCH_LIMIT

    ok, st = _write_json_pretty(backfill_state_path, state)
    dq["fs"]["backfill_state_write"] = st

    # 8) Write history outputs
    ok, st = _write_json_array_record_per_line(history_json, merged_hist)  # type: ignore[arg-type]
    dq["fs"]["history_json_write"] = st

    lite_hist = _make_history_lite(merged_hist, per_series_keep=TARGET_VALID)
    ok, st = _write_json_array_record_per_line(history_lite_json, lite_hist)  # type: ignore[arg-type]
    dq["fs"]["history_lite_json_write"] = st

    # 9) Write dq_state.json (compact)
    ok, st = _write_json_compact(dq_state, dq)
    if not ok:
        print(f"[WARN] failed to write dq_state.json: {st}", file=sys.stderr)
    dq["fs"]["dq_state_write"] = st

    # 10) Write manifest.json (pretty)
    repo = _repo_slug()
    sha = _data_sha()

    manifest_obj: Dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "as_of_ts": as_of_ts,
        "data_commit_sha": sha,
        "pinned": _pinned_urls(repo, sha),
        "paths": {
            "latest_csv": str(latest_csv.as_posix()),
            "latest_json": str(latest_json.as_posix()),
            "history_json": str(history_json.as_posix()),
            "history_lite_json": str(history_lite_json.as_posix()),
            "history_snapshot_json": str(history_snapshot.as_posix()),
            "dq_state_json": str(dq_state.as_posix()),
            "backfill_state_json": str(backfill_state_path.as_posix()),
        },
        "history_policy": {
            "format": "list",
            "key": "(series_id, data_date)",
            "same_key_rerun": "overwrite_by_latest_as_of_ts",
            "cap_per_series": CAP_PER_SERIES,
            "ordering": "series_id asc, data_date asc, as_of_ts asc",
            "history_json_format": "json_array_record_per_line",
            "history_lite_target_per_series": TARGET_VALID,
            "backfill_policy": {
                "target_valid": TARGET_VALID,
                "fetch_limit": FETCH_LIMIT,
                "no_progress_guard": {"max_no_progress": MAX_NO_PROGRESS, "cooldown_runs": COOLDOWN_RUNS},
                "state_schema": BACKFILL_STATE_SCHEMA,
            },
        },
        "fs_status": dq.get("fs", {}),
    }

    ok, st = _write_json_pretty(manifest, manifest_obj)
    if not ok:
        print(f"[WARN] failed to write manifest.json: {st}", file=sys.stderr)

    print(
        f"Wrote {latest_csv} + {latest_json} + {history_json} + {history_lite_json} + "
        f"{history_snapshot} + {dq_state} + {backfill_state_path} + {manifest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())