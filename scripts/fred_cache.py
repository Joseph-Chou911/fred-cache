# scripts/fred_cache.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRED cache generator (per-series history upsert + cap_per_series + backfill/self-heal + stats precompute)

Outputs (under ./cache):
- latest.csv            : one row per series_id (latest observation for this run)
- latest.json           : array of records (same as latest.csv)
- history.json          : rolling store, key=(series_id, data_date); same data_date reruns overwrite by as_of_ts
                           keep last CAP_PER_SERIES per series; JSON array (record-per-line) for citation
- history_lite.json     : per series keep last BACKFILL_TARGET_VALID records; JSON array (record-per-line)
- stats_latest.json     : precomputed metrics per series (ma/dev/z/p + ret1), to reduce prompt loading
                          NOTE: stats_latest.json includes stats_policy.script_version for version governance
- history.snapshot.json : snapshot of this run's latest.json
- dq_state.json         : lightweight data-quality state
- backfill_state.json   : per-series last_attempt bookkeeping (+ attempted_success flag)
- manifest.json         : pinned URLs + policies + fs status

Gap Backfill (方案B):
- Detect "recent missing business-day gap" between:
    last_seen_valid_data_date in existing history.json
    vs latest_data_date fetched in this run (limit=1)
- If business_days_gap > GAP_BUSINESS_DAYS_THRESHOLD, fetch a small recent window
  (GAP_BACKFILL_FETCH_LIMIT) and merge, to self-heal recent missing dates even when
  total valid count already >= BACKFILL_TARGET_VALID.

Notes:
- attempted_success is updated after merge (counts_after). gap_backfill may increase counts_after even if
  self-heal backfill skipped (already enough). This is acceptable and expected: attempted_success reflects
  "overall usable history" regardless of which mechanism contributed.
- fs_status in dq_state.json/manifest.json is a snapshot of write/read statuses up to that point.
  Because manifest.json is written LAST, its own write status (manifest_json_write) cannot be recorded
  into dq_state.json or manifest.fs_status without a second write pass (intentionally avoided).

Env:
- FRED_API_KEY (required)
- TIMEZONE (optional, default "Asia/Taipei")
- GITHUB_REPOSITORY (optional)
- DATA_SHA (optional) commit sha that contains the data files (preferred for pinned)
- GITHUB_SHA fallback
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date as date_cls
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

# -------------------------
# network policy
# -------------------------
TIMEOUT_SECS = 20
MAX_ATTEMPTS = 3
BACKOFF_SCHEDULE = [2, 4, 8]
RETRY_STATUS = {429, 500, 502, 503, 504}

# -------------------------
# history policy
# -------------------------
CAP_PER_SERIES = 400  # keep last N records PER series (records keyed by (series_id, data_date))

# -------------------------
# backfill policy
# -------------------------
BACKFILL_TARGET_VALID = 252
BACKFILL_FETCH_LIMIT = 420  # safe ceiling for daily series with gaps

# -------------------------
# GAP backfill policy (方案B)
# -------------------------
GAP_BACKFILL_ENABLE = True
GAP_BACKFILL_FETCH_LIMIT = 30
GAP_BUSINESS_DAYS_THRESHOLD = 1
GAP_BACKFILL_MAX_CALLS_PER_RUN = 6

# -------------------------
# stats policy (version-governed)
# -------------------------
STATS_W60 = 60
STATS_W252 = 252
STATS_STD_DDOF = 0
RET1_MODE = "delta"

PERCENTILE_METHOD = "P = count(x<=latest)/n * 100"
WINDOW_DEFINITION = "last N valid points (not calendar days)"

STATS_SCRIPT_VERSION = "stats_v1_ddof0_w60_w252_pct_le_ret1_delta"

TAIPEI_TZ_FALLBACK = timezone(timedelta(hours=8))


def _warn(label: str, st: str) -> None:
    print(f"[WARN] failed to write {label}: {st}", file=sys.stderr)


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


def _safe_source_url_latest(series_id: str) -> str:
    return _safe_source_url(series_id, 1)


def _safe_source_url_backfill(series_id: str, limit_n: int) -> str:
    return _safe_source_url(series_id, limit_n)


def _redact_secrets(s: str) -> str:
    if not s:
        return s
    api_key = os.getenv("FRED_API_KEY", "")
    if api_key and api_key in s:
        s = s.replace(api_key, "***REDACTED***")
    s = re.sub(r"api_key=[^&\s]+", "api_key=***REDACTED***", s, flags=re.IGNORECASE)
    return s


def _is_ymd(s: str) -> bool:
    return isinstance(s, str) and len(s) == 10 and s[4] == "-" and s[7] == "-"


def _parse_ymd_date(dd: str) -> Optional[date_cls]:
    if not _is_ymd(dd):
        return None
    try:
        return datetime.strptime(dd, "%Y-%m-%d").date()
    except Exception:
        return None


def _business_days_inclusive(a: date_cls, b: date_cls) -> int:
    """Count business days (Mon-Fri) in [a, b] inclusive using O(1) weeks + O(1) remainder."""
    if b < a:
        return 0
    total_days = (b - a).days + 1
    full_weeks, rem = divmod(total_days, 7)
    cnt = full_weeks * 5
    start_wd = a.weekday()  # 0=Mon..6=Sun
    for i in range(rem):
        if (start_wd + i) % 7 < 5:
            cnt += 1
    return cnt


def _business_days_between_excl_start_incl_end(start_dd: str, end_dd: str) -> Optional[int]:
    """
    Count business days (Mon-Fri) between start and end:
    - exclude start date
    - include end date
    Returns None if inputs invalid.
    Note: does NOT account for market holidays (weekday heuristic only).
    """
    s = _parse_ymd_date(start_dd)
    e = _parse_ymd_date(end_dd)
    if s is None or e is None:
        return None
    if e <= s:
        return 0
    return _business_days_inclusive(s + timedelta(days=1), e)


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
                "source_url": _safe_source_url_latest(series_id),
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
                "source_url": _safe_source_url_latest(series_id),
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
                "source_url": _safe_source_url_latest(series_id),
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
                "source_url": _safe_source_url_latest(series_id),
                "notes": "warn:no_observations",
            },
            warn="no_observations",
            attempts=attempts,
            status=last_status,
        )

    o0 = obs[0]
    dd = str(o0.get("date", "NA"))
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
            "data_date": dd,
            "value": value_out,
            "source_url": _safe_source_url_latest(series_id),
            "notes": notes,
        },
        warn=warn,
        err=None,
        attempts=attempts,
        status=last_status,
    )


def fetch_recent_observations(
    session: requests.Session, series_id: str, as_of_ts: str, limit_n: int, note_tag: str = "backfill"
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Fetch a window of recent observations (desc), filter invalid values.
    Returns (rows, meta) where meta is audit info (attempts/status/err_code/count_raw/count_kept).
    note_tag:
      - "backfill"      : self-heal until target_valid
      - "gap_backfill"  : heal recent missing business-day gaps (方案B)
    """
    api_key = os.getenv("FRED_API_KEY", "")

    meta: Dict[str, Any] = {
        "series_id": series_id,
        "limit": int(limit_n),
        "purpose": str(note_tag),
        "attempts": 0,
        "http_status": "NA",
        "err": "NA",
        "count_raw": 0,
        "count_kept": 0,
        "source_url": _safe_source_url_backfill(series_id, limit_n),
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

        note = str(note_tag)
        if attempts > 1:
            note = f"{note_tag}_warn:retried_{attempts}x"

        out.append(
            {
                "as_of_ts": as_of_ts,
                "series_id": series_id,
                "data_date": dd,
                "value": vv,
                "source_url": _safe_source_url_backfill(series_id, limit_n),
                "notes": note,
            }
        )

    meta["count_kept"] = len(out)
    meta["err"] = "NA"
    return out, meta


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
    This is the "可引用格式": avoids one super-long line and makes line citations feasible.
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


def _to_float(s: str) -> Optional[float]:
    try:
        if s is None:
            return None
        ss = str(s).strip()
        if ss in {"", "NA", "."}:
            return None
        return float(ss)
    except Exception:
        return None


def _upsert_history_per_series(
    existing: List[Dict[str, Any]],
    new_rows: List[Dict[str, str]],
    cap_per_series: int = CAP_PER_SERIES,
) -> List[Dict[str, str]]:
    """
    Key = (series_id, data_date)
    Same (series_id, data_date) reruns overwrite by keeping the greatest as_of_ts.
    Keep only last `cap_per_series` records per series by (data_date, as_of_ts).
    Output format stays list[dict].
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
    """
    Count valid points per series using the SAME validity criteria as stats:
    - must have YMD date
    - value must be parseable by _to_float()
    - de-dup by (series_id, data_date)
    """
    counts: Dict[str, int] = {}
    seen: Dict[Tuple[str, str], bool] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id", "")).strip()
        dd = str(r.get("data_date", "")).strip()
        if not sid or not _is_ymd(dd) or dd == "NA":
            continue
        vv = str(r.get("value", "NA")).strip()
        if _to_float(vv) is None:
            continue
        key = (sid, dd)
        if key in seen:
            continue
        seen[key] = True
        counts[sid] = counts.get(sid, 0) + 1
    return counts


def _make_history_lite(rows: List[Dict[str, str]], per_series_keep: int) -> List[Dict[str, str]]:
    """From full history list, keep only last `per_series_keep` records per series by (data_date, as_of_ts)."""
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


def _latest_valid_data_date_in_history(existing_hist: List[Dict[str, Any]], series_id: str) -> str:
    """
    Return the max data_date for a series from existing history where value is valid and date is YMD.
    Returns "NA" if none.
    """
    best_dd = "NA"
    for r in existing_hist:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id", "")).strip()
        if sid != series_id:
            continue
        dd = str(r.get("data_date", "")).strip()
        if not _is_ymd(dd) or dd == "NA":
            continue
        vv = str(r.get("value", "NA")).strip()
        if _to_float(vv) is None:
            continue
        if best_dd == "NA" or dd > best_dd:
            best_dd = dd
    return best_dd


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
            "stats_latest_json": "NA",
            "latest_csv": "NA",
            "manifest_json": "NA",
        }
    base = f"https://raw.githubusercontent.com/{repo}/{sha}/cache"
    return {
        "latest_json": f"{base}/latest.json",
        "history_json": f"{base}/history.json",
        "history_lite_json": f"{base}/history_lite.json",
        "stats_latest_json": f"{base}/stats_latest.json",
        "latest_csv": f"{base}/latest.csv",
        "manifest_json": f"{base}/manifest.json",
    }


def _mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / float(len(xs))


def _std(xs: List[float], ddof: int = 0) -> Optional[float]:
    n = len(xs)
    if n <= ddof:
        return None
    mu = _mean(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / float(n - ddof)
    if var < 0:
        return None
    return math.sqrt(var)


def _percentile_le(latest: float, xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    le = sum(1 for x in xs if x <= latest)
    return 100.0 * float(le) / float(len(xs))


def _series_points_from_history_lite(lite_rows: List[Dict[str, Any]], series_id: str) -> List[Tuple[str, float]]:
    pts: List[Tuple[str, float]] = []
    for r in lite_rows:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("series_id", "")).strip()
        if sid != series_id:
            continue
        dd = str(r.get("data_date", "")).strip()
        if not _is_ymd(dd):
            continue
        vf = _to_float(str(r.get("value", "NA")))
        if vf is None:
            continue
        pts.append((dd, vf))
    pts.sort(key=lambda x: x[0])
    dedup: Dict[str, float] = {}
    for dd, v in pts:
        dedup[dd] = v
    out = sorted(dedup.items(), key=lambda x: x[0])
    return [(dd, float(v)) for dd, v in out]


def _compute_stats_for_series(series_id: str, points: List[Tuple[str, float]], source_url_latest: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "series_id": series_id,
        "latest": {"data_date": "NA", "value": "NA", "source_url": source_url_latest},
        "windows": {
            "w60": {"n": 0, "start_date": "NA", "end_date": "NA"},
            "w252": {"n": 0, "start_date": "NA", "end_date": "NA"},
        },
        "metrics": {
            "ma60": "NA",
            "dev60": "NA",
            "z60": "NA",
            "p60": "NA",
            "z252": "NA",
            "p252": "NA",
            "ret1": "NA",
            "ret1_mode": RET1_MODE,
        },
        "calc_policy": {
            "std_ddof": STATS_STD_DDOF,
            "percentile_method": PERCENTILE_METHOD,
            "z_method": "z = (latest - mean(window)) / std(window)",
            "window_definition": WINDOW_DEFINITION,
        },
    }

    if not points:
        return out

    latest_dd, latest_v = points[-1]
    out["latest"]["data_date"] = latest_dd
    out["latest"]["value"] = latest_v

    if len(points) >= 2:
        _prev_dd, prev_v = points[-2]
        out["metrics"]["ret1"] = latest_v - prev_v

    if len(points) >= STATS_W60:
        w60_pts = points[-STATS_W60:]
        xs60 = [v for _dd, v in w60_pts]
        out["windows"]["w60"]["n"] = len(xs60)
        out["windows"]["w60"]["start_date"] = w60_pts[0][0]
        out["windows"]["w60"]["end_date"] = w60_pts[-1][0]

        mu60 = _mean(xs60)
        sd60 = _std(xs60, ddof=STATS_STD_DDOF)
        if mu60 is not None:
            out["metrics"]["ma60"] = mu60
        if sd60 is not None:
            out["metrics"]["dev60"] = sd60
        if mu60 is not None and sd60 is not None and sd60 != 0.0:
            out["metrics"]["z60"] = (latest_v - mu60) / sd60
        p60 = _percentile_le(latest_v, xs60)
        out["metrics"]["p60"] = p60 if p60 is not None else "NA"
    else:
        out["windows"]["w60"]["n"] = len(points)

    if len(points) >= STATS_W252:
        w252_pts = points[-STATS_W252:]
        xs252 = [v for _dd, v in w252_pts]
        out["windows"]["w252"]["n"] = len(xs252)
        out["windows"]["w252"]["start_date"] = w252_pts[0][0]
        out["windows"]["w252"]["end_date"] = w252_pts[-1][0]

        mu252 = _mean(xs252)
        sd252 = _std(xs252, ddof=STATS_STD_DDOF)
        if mu252 is not None and sd252 is not None and sd252 != 0.0:
            out["metrics"]["z252"] = (latest_v - mu252) / sd252
        p252 = _percentile_le(latest_v, xs252)
        out["metrics"]["p252"] = p252 if p252 is not None else "NA"
    else:
        out["windows"]["w252"]["n"] = len(points)

    return out


def _compute_stats_latest(lite_rows: List[Dict[str, Any]], as_of_ts: str, data_commit_sha: str) -> Dict[str, Any]:
    series_out: Dict[str, Any] = {}
    for sid in SERIES_IDS:
        pts = _series_points_from_history_lite(lite_rows, sid)
        src = _safe_source_url_latest(sid)
        series_out[sid] = _compute_stats_for_series(sid, pts, source_url_latest=src)

    return {
        "generated_at_utc": _now_utc_iso(),
        "as_of_ts": as_of_ts,
        "data_commit_sha": data_commit_sha,
        "series_count": len(SERIES_IDS),
        "stats_policy": {
            "script_version": STATS_SCRIPT_VERSION,
            "windows": {"w60": STATS_W60, "w252": STATS_W252},
            "std_ddof": STATS_STD_DDOF,
            "ret1_mode": RET1_MODE,
            "percentile_method": PERCENTILE_METHOD,
            "window_definition": WINDOW_DEFINITION,
            "source": "history_lite.json",
        },
        "series": series_out,
    }


def main() -> int:
    tz = _tzinfo()
    as_of_ts = _now_iso(tz)
    generated_at_utc = _now_utc_iso()

    session = requests.Session()
    session.headers.update({"User-Agent": "fred-cache/4.3-gap-backfill"})

    rows: List[Dict[str, str]] = []

    dq: Dict[str, Any] = {
        "as_of_ts": as_of_ts,
        "generated_at_utc": generated_at_utc,
        "fs": {},
        "series": {},
        "summary": {"ok": 0, "warn": 0, "err": 0},
        "gap_backfill": {
            "enabled": bool(GAP_BACKFILL_ENABLE),
            "policy": {
                "business_days_threshold": GAP_BUSINESS_DAYS_THRESHOLD,
                "fetch_limit": GAP_BACKFILL_FETCH_LIMIT,
                "max_calls_per_run": GAP_BACKFILL_MAX_CALLS_PER_RUN,
                "business_day_heuristic": "Mon-Fri only; holidays not modeled",
            },
            "detected": {},
            "attempted": {},
            "meta": {},
            "call_count": 0,
            "skipped_due_to_budget": [],
        },
        "backfill": {
            "target_valid": BACKFILL_TARGET_VALID,
            "fetch_limit": BACKFILL_FETCH_LIMIT,
            "attempted": {},
            "meta": {},
        },
    }

    # 1) Fetch latest (1 obs per series)
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
    stats_latest_json = CACHE_DIR / "stats_latest.json"
    history_snapshot = CACHE_DIR / "history.snapshot.json"
    dq_state = CACHE_DIR / "dq_state.json"
    backfill_state_path = CACHE_DIR / "backfill_state.json"
    manifest = CACHE_DIR / "manifest.json"

    # 2) Write latest outputs
    try:
        _write_csv(latest_csv, rows)
        dq["fs"]["latest_csv"] = "ok"
    except Exception as e:
        st = f"err:csv_write_exc:{type(e).__name__}"
        dq["fs"]["latest_csv"] = st
        _warn("latest.csv", st)

    ok, st = _write_json_compact(latest_json, rows)
    dq["fs"]["latest_json"] = st
    if not ok:
        _warn("latest.json", st)

    ok, st = _write_json_compact(history_snapshot, rows)
    dq["fs"]["history_snapshot_write"] = st
    if not ok:
        _warn("history.snapshot.json", st)

    # 3) Load existing history
    existing_hist, read_status = _load_json_list(history_json)
    dq["fs"]["history_json_read"] = read_status

    # 4) Load backfill state
    backfill_state, backfill_state_read = _load_json_dict(backfill_state_path)
    dq["fs"]["backfill_state_read"] = backfill_state_read
    if "series" not in backfill_state or not isinstance(backfill_state.get("series"), dict):
        backfill_state = {"series": {}}

    counts_before = _count_valid_per_series(existing_hist)
    dq["backfill"]["counts_before"] = counts_before

    # 4.5) GAP backfill (方案B)
    gap_rows: List[Dict[str, str]] = []
    if GAP_BACKFILL_ENABLE:
        calls_used = 0
        for sid in SERIES_IDS:
            latest_dd = str(dq["series"].get(sid, {}).get("data_date", "NA")).strip()
            last_seen_dd = _latest_valid_data_date_in_history(existing_hist, sid)

            if not _is_ymd(latest_dd) or latest_dd == "NA":
                dq["gap_backfill"]["attempted"][sid] = "skip:latest_dd_invalid"
                continue
            if not _is_ymd(last_seen_dd) or last_seen_dd == "NA":
                dq["gap_backfill"]["attempted"][sid] = "skip:last_seen_missing"
                continue
            if latest_dd <= last_seen_dd:
                dq["gap_backfill"]["attempted"][sid] = "skip:no_forward_gap"
                continue

            bd_gap = _business_days_between_excl_start_incl_end(last_seen_dd, latest_dd)
            dq["gap_backfill"]["detected"][sid] = {
                "last_seen_dd": last_seen_dd,
                "latest_dd": latest_dd,
                "business_days_gap_excl_start_incl_end": bd_gap if bd_gap is not None else "NA",
            }

            if bd_gap is None:
                dq["gap_backfill"]["attempted"][sid] = "skip:bd_gap_na"
                continue

            if bd_gap <= GAP_BUSINESS_DAYS_THRESHOLD:
                dq["gap_backfill"]["attempted"][sid] = f"skip:bd_gap<=threshold ({bd_gap}<={GAP_BUSINESS_DAYS_THRESHOLD})"
                continue

            if calls_used >= GAP_BACKFILL_MAX_CALLS_PER_RUN:
                dq["gap_backfill"]["attempted"][sid] = "skip:call_budget_exhausted"
                dq["gap_backfill"]["skipped_due_to_budget"].append(
                    {"series_id": sid, "last_seen_dd": last_seen_dd, "latest_dd": latest_dd, "bd_gap": bd_gap}
                )
                continue

            bf_rows, meta = fetch_recent_observations(session, sid, as_of_ts, GAP_BACKFILL_FETCH_LIMIT, note_tag="gap_backfill")
            dq["gap_backfill"]["meta"][sid] = meta
            calls_used += 1
            dq["gap_backfill"]["call_count"] = calls_used

            filtered: List[Dict[str, str]] = []
            for r in bf_rows:
                dd = str(r.get("data_date", "NA")).strip()
                if not _is_ymd(dd) or dd == "NA":
                    continue
                if dd <= last_seen_dd:
                    continue
                if dd > latest_dd:
                    continue
                filtered.append(r)

            if filtered:
                gap_rows.extend(filtered)
                dq["gap_backfill"]["attempted"][sid] = f"ok:added_rows={len(filtered)}"
            else:
                dq["gap_backfill"]["attempted"][sid] = "warn:no_rows_after_filter"

            backfill_state["series"].setdefault(sid, {})
            backfill_state["series"][sid]["last_gap_backfill"] = {
                "at": as_of_ts,
                "last_seen_dd": last_seen_dd,
                "latest_dd": latest_dd,
                "bd_gap": bd_gap,
                "fetch_limit": GAP_BACKFILL_FETCH_LIMIT,
                "meta_err": meta.get("err", "NA"),
                "http_status": meta.get("http_status", "NA"),
                "attempts": meta.get("attempts", "NA"),
                "count_raw": meta.get("count_raw", "NA"),
                "count_kept": meta.get("count_kept", "NA"),
                "added_after_filter": len(filtered),
            }

    # 5) Self-heal backfill
    backfill_rows: List[Dict[str, str]] = []
    for sid in SERIES_IDS:
        have = int(counts_before.get(sid, 0))
        series_state = backfill_state["series"].get(sid, {})
        attempted_success = bool(series_state.get("attempted_success", False))

        if have >= BACKFILL_TARGET_VALID:
            dq["backfill"]["attempted"][sid] = "skip:already_enough"
            backfill_state["series"].setdefault(sid, {})
            backfill_state["series"][sid]["attempted_success"] = True
            backfill_state["series"][sid]["last_attempt"] = {"at": as_of_ts, "note": "skip:already_enough", "have_after": have}
            continue

        if attempted_success and have < BACKFILL_TARGET_VALID:
            dq["backfill"]["attempted"][sid] = f"retry:stale_success_flag (have={have} < {BACKFILL_TARGET_VALID})"
        else:
            dq["backfill"]["attempted"][sid] = f"attempt (have={have} < {BACKFILL_TARGET_VALID})"

        bf_rows, meta = fetch_recent_observations(session, sid, as_of_ts, BACKFILL_FETCH_LIMIT, note_tag="backfill")
        dq["backfill"]["meta"][sid] = meta

        backfill_state["series"].setdefault(sid, {})
        backfill_state["series"][sid].setdefault("attempted_success", False)
        backfill_state["series"][sid]["last_attempt"] = {
            "at": as_of_ts,
            "have_before": have,
            "fetch_limit": BACKFILL_FETCH_LIMIT,
            "target_valid": BACKFILL_TARGET_VALID,
            "err": meta.get("err", "NA"),
            "http_status": meta.get("http_status", "NA"),
            "attempts": meta.get("attempts", "NA"),
            "count_raw": meta.get("count_raw", "NA"),
            "count_kept": meta.get("count_kept", "NA"),
        }

        if bf_rows:
            backfill_rows.extend(bf_rows)

    # 6) Merge
    merged_hist = _upsert_history_per_series(existing_hist, gap_rows, cap_per_series=CAP_PER_SERIES)
    merged_hist = _upsert_history_per_series(merged_hist, backfill_rows, cap_per_series=CAP_PER_SERIES)
    merged_hist = _upsert_history_per_series(merged_hist, rows, cap_per_series=CAP_PER_SERIES)

    counts_after = _count_valid_per_series(merged_hist)
    dq["backfill"]["counts_after"] = counts_after

    # 7) Update attempted_success + have_after
    for sid in SERIES_IDS:
        have_after = int(counts_after.get(sid, 0))
        backfill_state["series"].setdefault(sid, {})
        backfill_state["series"][sid]["attempted_success"] = bool(have_after >= BACKFILL_TARGET_VALID)
        la = backfill_state["series"][sid].get("last_attempt", {})
        if isinstance(la, dict):
            la["have_after"] = have_after
            backfill_state["series"][sid]["last_attempt"] = la

    ok, st = _write_json_pretty(backfill_state_path, backfill_state)
    dq["fs"]["backfill_state_write"] = st
    if not ok:
        _warn("backfill_state.json", st)

    ok, st = _write_json_array_record_per_line(history_json, merged_hist)
    dq["fs"]["history_json_write"] = st
    if not ok:
        _warn("history.json", st)

    lite_hist = _make_history_lite(merged_hist, per_series_keep=BACKFILL_TARGET_VALID)
    ok, st = _write_json_array_record_per_line(history_lite_json, lite_hist)
    dq["fs"]["history_lite_json_write"] = st
    if not ok:
        _warn("history_lite.json", st)

    data_sha = _data_sha()
    stats_obj = _compute_stats_latest(lite_hist, as_of_ts=as_of_ts, data_commit_sha=data_sha)
    ok, st = _write_json_compact(stats_latest_json, stats_obj)
    dq["fs"]["stats_latest_json_write"] = st
    if not ok:
        _warn("stats_latest.json", st)

    ok, st = _write_json_compact(dq_state, dq)
    dq["fs"]["dq_state_write"] = st
    if not ok:
        _warn("dq_state.json", st)

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
            "stats_latest_json": str(stats_latest_json.as_posix()),
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
            "history_lite_target_per_series": BACKFILL_TARGET_VALID,
            "backfill_policy": "self_heal_until_target_valid; fetch_limit_used_when_needed",
            "gap_backfill_policy": {
                "enabled": bool(GAP_BACKFILL_ENABLE),
                "business_days_threshold": GAP_BUSINESS_DAYS_THRESHOLD,
                "fetch_limit": GAP_BACKFILL_FETCH_LIMIT,
                "max_calls_per_run": GAP_BACKFILL_MAX_CALLS_PER_RUN,
                "business_day_heuristic": "Mon-Fri only; holidays not modeled",
                "purpose": "heal recent missing dates even if already >= target_valid",
            },
        },
        "stats_policy": {
            "script_version": STATS_SCRIPT_VERSION,
            "windows": {"w60": STATS_W60, "w252": STATS_W252},
            "std_ddof": STATS_STD_DDOF,
            "ret1_mode": RET1_MODE,
            "percentile_method": PERCENTILE_METHOD,
            "window_definition": WINDOW_DEFINITION,
            "source": "history_lite.json",
        },
        "fs_status": dq.get("fs", {}),
    }

    ok, st = _write_json_pretty(manifest, manifest_obj)
    if not ok:
        _warn("manifest.json", st)

    print(
        "Wrote "
        f"{latest_csv} + {latest_json} + {history_json} + {history_lite_json} + {stats_latest_json} + "
        f"{history_snapshot} + {dq_state} + {backfill_state_path} + {manifest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())