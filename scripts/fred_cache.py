#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRED cache generator

Outputs (under ./cache):
- latest.csv            : one row per series_id (latest observation)
- latest.json           : array of records (same as latest.csv)
- history.jsonl         : append-only log of records (one JSON object per line)
- history.json          : compact view: latest record per series_id (from history.jsonl)
- history.snapshot.json : snapshot of this run's latest.json (for audit)
- dq_state.json         : lightweight data-quality state
- manifest.json         : metadata + pinned raw URLs (including pinned.manifest_json)

Environment variables:
- FRED_API_KEY (required)
- TIMEZONE (optional, default "Asia/Taipei")

GitHub Actions recommended env:
- GITHUB_REPOSITORY (owner/repo)  e.g. "Joseph-Chou911/fred-cache"
- DATA_SHA (optional) commit sha you want pinned to (data commit)
    If not provided, will fall back to GITHUB_SHA.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
CACHE_DIR = Path("cache")

# You can add/remove series here.
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
    # extras you asked about
    "NFCINONFINLEVERAGE",
    "T10Y2Y",
    "T10Y3M",
]

CSV_FIELDNAMES = ["as_of_ts", "series_id", "data_date", "value", "source_url", "notes"]

# network policy
TIMEOUT_SECS = 20
MAX_ATTEMPTS = 3
BACKOFF_SECS = [2, 4, 8]
RETRY_STATUS = {429, 500, 502, 503, 504}


def _tzinfo() -> timezone:
    tz_name = os.getenv("TIMEZONE", "Asia/Taipei")
    if ZoneInfo is None:
        # Fallback: fixed offset +08:00 if zoneinfo unavailable
        if tz_name == "Asia/Taipei":
            return timezone.utc  # will still output UTC; better than crashing
        return timezone.utc
    try:
        return ZoneInfo(tz_name)  # type: ignore[arg-type]
    except Exception:
        return ZoneInfo("Asia/Taipei")  # type: ignore[arg-type]


def _now_iso(tz) -> str:
    return datetime.now(tz).replace(microsecond=0).isoformat()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_source_url(series_id: str) -> str:
    # DO NOT include api_key
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    # stable order for readability (not required, but nicer)
    qs = "&".join([f"{k}={requests.utils.quote(str(params[k]))}" for k in ["series_id", "file_type", "sort_order", "limit"]])
    return f"{BASE_URL}?{qs}"


def _redact_secrets(s: str) -> str:
    if not s:
        return s
    api_key = os.getenv("FRED_API_KEY", "")
    if api_key and api_key in s:
        s = s.replace(api_key, "***REDACTED***")
    # mask any api_key=xxxx in text
    s = re.sub(r"api_key=[^&\s]+", "api_key=***REDACTED***", s, flags=re.IGNORECASE)
    return s


@dataclass
class FetchResult:
    record: Dict[str, str]
    warn: Optional[str] = None
    err: Optional[str] = None
    attempts: int = 0
    status: Optional[int] = None


def _http_get_with_retry(session: requests.Session, url: str, params: Dict[str, Any]) -> Tuple[Optional[requests.Response], Optional[str], int, Optional[int]]:
    """
    Returns: (response or None, error_code string or None, attempts_used, last_status)
    error_code examples: timeout, http_429, http_500, req_exc:...
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
                # retry
                if attempt < MAX_ATTEMPTS:
                    time.sleep(BACKOFF_SECS[i])
                    continue
                return None, f"http_{r.status_code}", attempt, last_status
            # non-retryable
            return None, f"http_{r.status_code}", attempt, last_status
        except requests.Timeout:
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECS[i])
                continue
            return None, "timeout", attempt, last_status
        except requests.RequestException as e:
            code = f"req_exc:{type(e).__name__}"
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECS[i])
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
                "source_url": _safe_source_url(series_id),
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
        # if retried (attempts>1), mark warn as well
        warn = f"warn:retried_{attempts}x" if attempts > 1 else None
        return FetchResult(
            record={
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(series_id),
                "notes": notes,
            },
            warn=warn,
            err=err_code,
            attempts=attempts,
            status=last_status,
        )

    # parse JSON
    try:
        payload = r.json()
    except Exception:
        return FetchResult(
            record={
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": "NA",
                "value": "NA",
                "source_url": _safe_source_url(series_id),
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
                "source_url": _safe_source_url(series_id),
                "notes": "warn:no_observations",
            },
            warn="no_observations",
            attempts=attempts,
            status=last_status,
        )

    o0 = obs[0]
    date = str(o0.get("date", "NA"))
    value = str(o0.get("value", "NA"))

    # missing value patterns FRED sometimes uses "."
    if value.strip() in {"", "NA", "."}:
        notes = "warn:missing_value"
        warn = "missing_value"
        value_out = "NA"
    else:
        notes = "NA"
        warn = None
        value_out = value

    # If we retried at least once but succeeded, keep a warn tag
    if attempts > 1 and notes == "NA":
        notes = f"warn:retried_{attempts}x"
        warn = f"retried_{attempts}x"

    return FetchResult(
        record={
            "as_of_ts": as_of_ts,
            "series_id": series_id,
            "data_date": date,
            "value": value_out,
            "source_url": _safe_source_url(series_id),
            "notes": notes,
        },
        warn=warn,
        err=None,
        attempts=attempts,
        status=last_status,
    )


def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "NA") for k in CSV_FIELDNAMES})


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def _append_jsonl(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    out: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # ignore malformed line; do not crash
                continue
    return out


def _latest_per_series(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Pick latest record per series_id based on as_of_ts (ISO string).
    Assumes as_of_ts sortable lexicographically (ISO-8601).
    """
    best: Dict[str, Dict[str, str]] = {}
    for r in records:
        sid = r.get("series_id", "")
        if not sid:
            continue
        prev = best.get(sid)
        if prev is None or str(r.get("as_of_ts", "")) > str(prev.get("as_of_ts", "")):
            best[sid] = r
    # stable output order: by series_id
    return [best[sid] for sid in sorted(best.keys())]


def _repo_slug() -> str:
    return os.getenv("GITHUB_REPOSITORY", "Joseph-Chou911/fred-cache")


def _data_sha() -> str:
    # DATA_SHA is the data commit sha (after push) if workflow exports it.
    # fallback: GITHUB_SHA (workflow run sha)
    return os.getenv("DATA_SHA") or os.getenv("GITHUB_SHA") or "NA"


def _pinned_urls(repo: str, sha: str) -> Dict[str, str]:
    if sha == "NA":
        # pinned not available
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
        "manifest_json": f"{base}/manifest.json",
    }


def main() -> int:
    tz = _tzinfo()
    as_of_ts = _now_iso(tz)
    generated_at_utc = _now_utc_iso()

    session = requests.Session()
    session.headers.update({"User-Agent": "fred-cache/1.0"})

    rows: List[Dict[str, str]] = []
    dq: Dict[str, Any] = {
        "as_of_ts": as_of_ts,
        "generated_at_utc": generated_at_utc,
        "series": {},
        "summary": {"ok": 0, "warn": 0, "err": 0},
    }

    for sid in SERIES_IDS:
        res = fetch_latest_obs(session, sid, as_of_ts)
        # safety: ensure no secrets in any stored text
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

    # write latest outputs
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    latest_csv = CACHE_DIR / "latest.csv"
    latest_json = CACHE_DIR / "latest.json"
    history_jsonl = CACHE_DIR / "history.jsonl"
    history_json = CACHE_DIR / "history.json"
    history_snapshot = CACHE_DIR / "history.snapshot.json"
    dq_state = CACHE_DIR / "dq_state.json"
    manifest = CACHE_DIR / "manifest.json"

    _write_csv(latest_csv, rows)
    _write_json(latest_json, rows)

    # history append
    _append_jsonl(history_jsonl, rows)

    # rebuild history.json as "latest per series" from history.jsonl
    all_hist = _read_jsonl(history_jsonl)
    compact = _latest_per_series(all_hist)
    _write_json(history_json, compact)

    # snapshot of this run (full)
    _write_json(history_snapshot, rows)

    # dq state
    _write_json(dq_state, dq)

    # manifest
    repo = _repo_slug()
    sha = _data_sha()
    manifest_obj = {
        "generated_at_utc": generated_at_utc,
        "as_of_ts": as_of_ts,
        "data_commit_sha": sha,
        "pinned": _pinned_urls(repo, sha),
        "paths": {
            "latest_csv": str(latest_csv.as_posix()),
            "latest_json": str(latest_json.as_posix()),
            "history_jsonl": str(history_jsonl.as_posix()),
            "history_json": str(history_json.as_posix()),
            "history_snapshot_json": str(history_snapshot.as_posix()),
            "dq_state_json": str(dq_state.as_posix()),
        },
    }
    _write_json(manifest, manifest_obj)

    # minimal stdout (no secrets)
    print(f"Wrote {latest_csv} + {latest_json} + {history_jsonl} + {history_json} + {history_snapshot} + {dq_state} + {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())