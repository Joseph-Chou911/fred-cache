#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRED cache generator (per-series rolling history by data_date, audit-friendly)

Outputs (under ./cache):
- latest.csv            : one row per series_id (latest observation for this run)
- latest.json           : array of records (same as latest.csv)
- history.json          : rolling time-series store (per series per data_date), cap per series
- history.snapshot.json : snapshot of this run's latest.json (for audit)
- dq_state.json         : lightweight data-quality state (includes read/write health notes)
- manifest.json         : metadata + pinned raw URLs (DATA_SHA preferred, else GITHUB_SHA)

Environment variables:
- FRED_API_KEY (required)
- TIMEZONE (optional, default "Asia/Taipei")

GitHub Actions recommended env:
- GITHUB_REPOSITORY (owner/repo)  e.g. "Joseph-Chou911/fred-cache"
- DATA_SHA (optional) commit sha that contains the data files (preferred for pinned)
- GITHUB_SHA fallback
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

# history policy (per series cap)
FETCH_LIMIT_PER_SERIES = 400  # API observations limit per series per run
HISTORY_CAP_PER_SERIES = 400  # rolling cap per series (by data_date)

# deterministic Taipei fallback
TAIPEI_TZ_FALLBACK = timezone(timedelta(hours=8))


def _tzinfo():
    """
    Returns tzinfo. Must never crash; ultimate fallback is fixed +08:00 for Asia/Taipei.
    """
    tz_name = (os.getenv("TIMEZONE", "Asia/Taipei") or "").strip() or "Asia/Taipei"

    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)  # type: ignore[arg-type]
        except Exception:
            try:
                return ZoneInfo("Asia/Taipei")  # type: ignore[arg-type]
            except Exception:
                return TAIPEI_TZ_FALLBACK

    # No ZoneInfo available
    if tz_name == "Asia/Taipei":
        return TAIPEI_TZ_FALLBACK
    return timezone.utc


def _now_iso(tz) -> str:
    return datetime.now(tz).replace(microsecond=0).isoformat()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_source_url(series_id: str, limit: int) -> str:
    # DO NOT include api_key
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    qs = "&".join(
        [f"{k}={requests.utils.quote(str(params[k]))}" for k in ["series_id", "file_type", "sort_order", "limit"]]
    )
    return f"{BASE_URL}?{qs}"


def _redact_secrets(s: str) -> str:
    if not s:
        return s
    api_key = os.getenv("FRED_API_KEY", "")
    if api_key and api_key in s:
        s = s.replace(api_key, "***REDACTED***")
    s = re.sub(r"api_key=[^&\s]+", "api_key=***REDACTED***", s, flags=re.IGNORECASE)
    return s


def _is_missing_value(v: str) -> bool:
    v2 = (v or "").strip()
    return v2 in {"", "NA", ".", "nan", "NaN"}


@dataclass
class FetchSeriesResult:
    latest_record: Dict[str, str]
    history_rows: List[Dict[str, str]]
    warn: Optional[str] = None
    err: Optional[str] = None
    attempts: int = 0
    status: Optional[int] = None
    obs_count: int = 0


def _http_get_with_retry(
    session: requests.Session, url: str, params: Dict[str, Any]
) -> Tuple[Optional[requests.Response], Optional[str], int, Optional[int]]:
    """
    Returns: (response or None, error_code or None, attempts_used, last_status)
    """
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

            # non-retryable HTTP errors
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


def fetch_series_observations(session: requests.Session, series_id: str, as_of_ts: str) -> FetchSeriesResult:
    """
    - latest_record: based on observations[0] (even if missing -> value=NA w/ warn)
    - history_rows: up to FETCH_LIMIT_PER_SERIES rows keyed by (series_id, data_date)
    """
    api_key = os.getenv("FRED_API_KEY", "")

    if not api_key or len(api_key) < 10:
        latest = {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": _safe_source_url(series_id, FETCH_LIMIT_PER_SERIES),
            "notes": "err:missing_api_key",
        }
        return FetchSeriesResult(
            latest_record=latest,
            history_rows=[],
            err="missing_api_key",
            attempts=0,
            status=None,
            obs_count=0,
        )

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": FETCH_LIMIT_PER_SERIES,
    }

    r, err_code, attempts, last_status = _http_get_with_retry(session, BASE_URL, params)
    src_url = _safe_source_url(series_id, FETCH_LIMIT_PER_SERIES)

    if r is None:
        notes = f"err:{err_code}"
        warn = f"warn:retried_{attempts}x" if attempts > 1 else None
        latest = {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": src_url,
            "notes": notes,
        }
        return FetchSeriesResult(
            latest_record=latest,
            history_rows=[],
            warn=warn,
            err=err_code,
            attempts=attempts,
            status=last_status,
            obs_count=0,
        )

    try:
        payload = r.json()
    except Exception:
        latest = {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": src_url,
            "notes": "err:bad_json",
        }
        return FetchSeriesResult(
            latest_record=latest,
            history_rows=[],
            err="bad_json",
            attempts=attempts,
            status=last_status,
            obs_count=0,
        )

    obs = payload.get("observations", [])
    if not isinstance(obs, list) or not obs:
        latest = {
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": "NA",
            "value": "NA",
            "source_url": src_url,
            "notes": "warn:no_observations",
        }
        return FetchSeriesResult(
            latest_record=latest,
            history_rows=[],
            warn="no_observations",
            attempts=attempts,
            status=last_status,
            obs_count=0,
        )

    # latest = first observation (may be missing)
    o0 = obs[0] if isinstance(obs[0], dict) else {}
    latest_date = str(o0.get("date", "NA"))
    latest_value_raw = str(o0.get("value", "NA"))
    if _is_missing_value(latest_value_raw):
        latest_value = "NA"
        latest_notes = "warn:missing_value"
        latest_warn = "missing_value"
    else:
        latest_value = latest_value_raw
        latest_notes = "NA"
        latest_warn = None

    if attempts > 1 and latest_notes == "NA":
        latest_notes = f"warn:retried_{attempts}x"
        latest_warn = f"retried_{attempts}x"

    latest = {
        "as_of_ts": as_of_ts,
        "series_id": series_id,
        "data_date": latest_date,
        "value": latest_value,
        "source_url": src_url,
        "notes": latest_notes,
    }

    # history rows (up to limit)
    hist_rows: List[Dict[str, str]] = []
    for x in obs:
        if not isinstance(x, dict):
            continue
        d = str(x.get("date", "NA"))
        v_raw = str(x.get("value", "NA"))
        if d == "NA" or not d:
            continue

        if _is_missing_value(v_raw):
            v_out = "NA"
            n_out = "warn:missing_value"
        else:
            v_out = v_raw
            n_out = "NA"

        hist_rows.append(
            {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": d,
                "value": v_out,
                "source_url": src_url,
                "notes": n_out,
            }
        )

    # If we retried and latest is NA-less, we already annotated latest; keep history notes as-is (per row).
    # Count of obs returned:
    obs_count = len(hist_rows)

    return FetchSeriesResult(
        latest_record=latest,
        history_rows=hist_rows,
        warn=latest_warn,
        err=None,
        attempts=attempts,
        status=last_status,
        obs_count=obs_count,
    )


def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "NA") for k in CSV_FIELDNAMES})


def _write_json(path: Path, obj: Any) -> Tuple[bool, str]:
    """
    Write JSON. Never raises (returns ok flag + status).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return True, "ok"
    except PermissionError:
        return False, "err:permission"
    except OSError as e:
        return False, f"err:oserror:{type(e).__name__}"
    except Exception as e:
        return False, f"err:write_exc:{type(e).__name__}"


def _load_json_list(path: Path) -> Tuple[List[Dict[str, Any]], str]:
    """
    Load JSON list safely. Never raises.
    Returns (list, status_code).
    """
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


def _parse_date_key(d: str) -> str:
    # FRED dates are "YYYY-MM-DD" (lex sortable).
    return (d or "").strip()


def _upsert_timeseries_history(
    existing: List[Dict[str, Any]],
    new_rows: List[Dict[str, str]],
    cap_per_series: int = HISTORY_CAP_PER_SERIES,
) -> List[Dict[str, str]]:
    """
    Key = (series_id, data_date)
    Overwrite by keeping the greatest as_of_ts if same key appears.
    After merge, cap per series by keeping last `cap_per_series` points by data_date.
    """
    best: Dict[Tuple[str, str], Dict[str, str]] = {}

    def take(r_any: Dict[str, Any]) -> None:
        sid = str(r_any.get("series_id", ""))
        d = str(r_any.get("data_date", ""))
        as_of_ts = str(r_any.get("as_of_ts", ""))
        if not sid or not d or not as_of_ts:
            return

        rec: Dict[str, str] = {
            "as_of_ts": as_of_ts,
            "series_id": sid,
            "data_date": d,
            "value": str(r_any.get("value", "NA")),
            "source_url": str(r_any.get("source_url", "NA")),
            "notes": str(r_any.get("notes", "NA")),
        }

        key = (sid, d)
        prev = best.get(key)
        if prev is None or as_of_ts > prev.get("as_of_ts", ""):
            best[key] = rec

    for r in existing:
        if isinstance(r, dict):
            take(r)

    for r in new_rows:
        take(r)  # type: ignore[arg-type]

    # group by series_id
    by_sid: Dict[str, List[Dict[str, str]]] = {}
    for rec in best.values():
        by_sid.setdefault(rec.get("series_id", "NA"), []).append(rec)

    capped_all: List[Dict[str, str]] = []
    for sid, recs in by_sid.items():
        # sort by data_date (lex works for YYYY-MM-DD)
        recs.sort(key=lambda r: _parse_date_key(r.get("data_date", "")))
        if len(recs) > cap_per_series:
            recs = recs[-cap_per_series:]
        capped_all.extend(recs)

    # deterministic order: series_id then data_date
    capped_all.sort(key=lambda r: (r.get("series_id", ""), _parse_date_key(r.get("data_date", ""))))
    return capped_all


def _repo_slug() -> str:
    return os.getenv("GITHUB_REPOSITORY", "Joseph-Chou911/fred-cache")


def _data_sha() -> str:
    return os.getenv("DATA_SHA") or os.getenv("GITHUB_SHA") or "NA"


def _pinned_urls(repo: str, sha: str) -> Dict[str, str]:
    if sha == "NA":
        return {
            "latest_json": "NA",
            "history_json": "NA",
            "latest_csv": "NA",
            "manifest_json": "NA",
        }
    base = f"https://raw.githubusercontent.com/{repo}/{sha}/cache"
    return {
        "latest_json": f"{base}/latest.json",
        "history_json": f"{base}/history.json",
        "latest_csv": f"{base}/latest.csv",
        "manifest_json": f"{base}/manifest.json",  # workflow may patch
    }


def main() -> int:
    tz = _tzinfo()
    as_of_ts = _now_iso(tz)
    generated_at_utc = _now_utc_iso()

    session = requests.Session()
    session.headers.update({"User-Agent": "fred-cache/3.0"})

    latest_rows: List[Dict[str, str]] = []
    hist_new_rows: List[Dict[str, str]] = []

    dq: Dict[str, Any] = {
        "as_of_ts": as_of_ts,
        "generated_at_utc": generated_at_utc,
        "fs": {},
        "series": {},
        "summary": {"ok": 0, "warn": 0, "err": 0},
        "history_policy": {
            "key": "(series_id, data_date)",
            "cap_per_series": HISTORY_CAP_PER_SERIES,
            "fetch_limit_per_series": FETCH_LIMIT_PER_SERIES,
        },
    }

    for sid in SERIES_IDS:
        res = fetch_series_observations(session, sid, as_of_ts)

        # redact any secrets defensively
        latest_rec = {k: _redact_secrets(str(v)) for k, v in res.latest_record.items()}
        latest_rows.append(latest_rec)

        for r in res.history_rows:
            rr = {k: _redact_secrets(str(v)) for k, v in r.items()}
            hist_new_rows.append(rr)

        note = latest_rec.get("notes", "NA")
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
            "latest_data_date": latest_rec.get("data_date", "NA"),
            "latest_value": latest_rec.get("value", "NA"),
            "obs_count_returned": res.obs_count,
        }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    latest_csv = CACHE_DIR / "latest.csv"
    latest_json = CACHE_DIR / "latest.json"
    history_json = CACHE_DIR / "history.json"
    history_snapshot = CACHE_DIR / "history.snapshot.json"
    dq_state = CACHE_DIR / "dq_state.json"
    manifest = CACHE_DIR / "manifest.json"

    # latest outputs (this run)
    try:
        _write_csv(latest_csv, latest_rows)
        dq["fs"]["latest_csv"] = "ok"
    except Exception as e:
        dq["fs"]["latest_csv"] = f"err:csv_write_exc:{type(e).__name__}"

    ok, st = _write_json(latest_json, latest_rows)
    dq["fs"]["latest_json"] = st

    # history.json (time-series upsert + per-series cap)
    existing_hist, read_status = _load_json_list(history_json)
    dq["fs"]["history_json_read"] = read_status

    merged_hist = _upsert_timeseries_history(existing_hist, hist_new_rows, cap_per_series=HISTORY_CAP_PER_SERIES)
    ok, st = _write_json(history_json, merged_hist)
    dq["fs"]["history_json_write"] = st

    # snapshot of this run (audit)
    ok, st = _write_json(history_snapshot, latest_rows)
    dq["fs"]["history_snapshot_write"] = st

    # dq state
    ok, st = _write_json(dq_state, dq)
    if not ok:
        print(f"[WARN] failed to write dq_state.json: {st}", file=sys.stderr)

    # manifest (index)
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
            "history_snapshot_json": str(history_snapshot.as_posix()),
            "dq_state_json": str(dq_state.as_posix()),
        },
        "history_policy": {
            "fetch_limit_per_series": FETCH_LIMIT_PER_SERIES,
            "cap_per_series": HISTORY_CAP_PER_SERIES,
            "key": "(series_id, data_date)",
            "rerun_behavior": "same (series_id,data_date) overwritten_by_latest_as_of_ts",
            "cap_behavior": "keep_last_N_by_data_date_per_series",
        },
        "fs_status": dq.get("fs", {}),
    }

    ok, st = _write_json(manifest, manifest_obj)
    if not ok:
        print(f"[WARN] failed to write manifest.json: {st}", file=sys.stderr)

    print(f"Wrote {latest_csv} + {latest_json} + {history_json} + {history_snapshot} + {dq_state} + {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())