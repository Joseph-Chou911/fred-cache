#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_regime_inputs_cache.py (v1_8)

Adds:
- normalize_history(): per series_id sort by data_date asc; keep last record per (series_id, data_date)
- stable output ordering: series_id asc, then data_date asc
Keeps:
- v1_7 clean_history(): drop null/bad_date/bad_value legacy garbage
- never append failed points
- compute MA60/dev/ret1 from strict YYYY-MM-DD valid points, sorted by data_date
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "regime_inputs_cache"

CONFIG_PATH = OUT_DIR / "inputs_config.json"
LATEST_PATH = OUT_DIR / "inputs_latest.json"
HIST_LITE_PATH = OUT_DIR / "inputs_history_lite.json"
DQ_PATH = OUT_DIR / "dq_state.json"
FEATURES_PATH = OUT_DIR / "features_latest.json"

RE_YYYY_MM_DD = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_taipei(dt: datetime) -> str:
    if ZoneInfo is None:
        return iso_z(dt)
    return dt.astimezone(ZoneInfo("Asia/Taipei")).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def http_get_text(url: str, timeout_sec: int) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "regime_inputs_cache/1.8 (+https://github.com/)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def retry_fetch(url: str, timeout_sec: int, backoff: List[int]) -> str:
    last_err: Optional[Exception] = None
    for wait_s in [0] + backoff:
        if wait_s:
            time.sleep(wait_s)
        try:
            return http_get_text(url, timeout_sec=timeout_sec)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"fetch_failed after retries: {type(last_err).__name__}: {last_err}")  # type: ignore[arg-type]


def parse_date_yyyy_mm_dd(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {s}")


def safe_float(x: Any) -> float:
    if x is None:
        raise ValueError("value is None")
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    if s == "":
        raise ValueError("empty value")
    return float(s)


def is_valid_yyyy_mm_dd(d: Any) -> bool:
    if not isinstance(d, str):
        return False
    if not RE_YYYY_MM_DD.match(d):
        return False
    try:
        datetime.strptime(d, "%Y-%m-%d")
        return True
    except Exception:
        return False


def fetch_stooq_daily(symbol: str, timeout: int, backoff: List[int]) -> Tuple[str, float, str, int]:
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    text = retry_fetch(url, timeout_sec=timeout, backoff=backoff)
    rows = list(csv.DictReader(text.splitlines()))
    rows = [r for r in rows if r.get("Date") and r.get("Close")]
    if not rows:
        raise RuntimeError("no valid rows in stooq csv")
    last = rows[-1]
    data_date = parse_date_yyyy_mm_dd(last["Date"])
    value = safe_float(last["Close"])
    return data_date, value, url, len(rows)


def fetch_csv_max_date(
    url: str, date_col: str, value_col: str, timeout: int, backoff: List[int]
) -> Tuple[str, float, str, List[str], int]:
    text = retry_fetch(url, timeout_sec=timeout, backoff=backoff)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("empty csv")

    header = next(csv.reader([lines[0]]))
    header = [h.strip() for h in header]

    reader = csv.DictReader(lines)
    best_date: Optional[str] = None
    best_value: Optional[float] = None
    rows_total = 0

    for row in reader:
        rows_total += 1
        d_raw = row.get(date_col, "")
        v_raw = row.get(value_col, "")
        if not d_raw or not v_raw:
            continue
        try:
            d = parse_date_yyyy_mm_dd(d_raw)
            v = safe_float(v_raw)
        except Exception:
            continue

        if (best_date is None) or (d > best_date):
            best_date, best_value = d, v

    if best_date is None or best_value is None:
        raise RuntimeError(f"no valid (date,value) using date_col={date_col}, value_col={value_col}")

    return best_date, best_value, url, header, rows_total


def staleness_days(data_date: str, now_utc: datetime) -> Optional[int]:
    try:
        d = datetime.strptime(data_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int((now_utc - d).total_seconds() // 86400)
    except Exception:
        return None


def clean_history(history: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    stats = {"kept": 0, "dropped_null": 0, "dropped_bad_date": 0, "dropped_bad_value": 0}
    cleaned: List[Dict[str, Any]] = []

    for r in history:
        d = r.get("data_date")
        v = r.get("value")

        if d is None or v is None:
            stats["dropped_null"] += 1
            continue
        if not is_valid_yyyy_mm_dd(d):
            stats["dropped_bad_date"] += 1
            continue
        try:
            _ = safe_float(v)
        except Exception:
            stats["dropped_bad_value"] += 1
            continue

        cleaned.append(r)
        stats["kept"] += 1

    return cleaned, stats


def normalize_history(history: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Normalize for audit stability:
    - Group by series_id
    - Sort each group by data_date asc, then as_of_ts asc (if present)
    - Keep last record per (series_id, data_date)
    - Output order: series_id asc, then data_date asc

    Returns:
    - normalized history
    - stats: kept_after, dropped_dupe_by_day
    """
    # Group
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in history:
        sid = r.get("series_id")
        if not sid:
            continue
        groups.setdefault(str(sid), []).append(r)

    out: List[Dict[str, Any]] = []
    dropped_dupe = 0
    kept = 0

    for sid in sorted(groups.keys()):
        items = groups[sid]

        def keyfun(x: Dict[str, Any]) -> Tuple[str, str]:
            d = x.get("data_date") or ""
            a = x.get("as_of_ts") or ""
            return (d, a)

        items.sort(key=keyfun)

        # Keep last per day
        last_by_day: Dict[str, Dict[str, Any]] = {}
        for r in items:
            d = r.get("data_date")
            if not isinstance(d, str):
                continue
            if d in last_by_day:
                dropped_dupe += 1
            last_by_day[d] = r

        # Emit in date order
        for d in sorted(last_by_day.keys()):
            out.append(last_by_day[d])
            kept += 1

    return out, {"kept_after": kept, "dropped_dupe_by_day": dropped_dupe}


def round6(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return float(f"{x:.6f}")


def mean(vals: List[float]) -> float:
    return sum(vals) / float(len(vals))


def compute_features(history: List[Dict[str, Any]], series_ids: List[str], window: int = 60) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    for sid in series_ids:
        pts: List[Tuple[str, float]] = []
        latest_source_url: Optional[str] = None

        for r in history:
            if r.get("series_id") != sid:
                continue
            d = r.get("data_date")
            v = r.get("value")
            if d is None or v is None:
                continue
            if not is_valid_yyyy_mm_dd(d):
                continue
            try:
                vv = safe_float(v)
            except Exception:
                continue

            pts.append((d, vv))
            if r.get("source_url"):
                latest_source_url = r.get("source_url")

        pts.sort(key=lambda x: x[0])
        n_valid = len(pts)

        if n_valid == 0:
            out[sid] = {
                "series_id": sid,
                "latest": {"data_date": None, "value": None, "source_url": latest_source_url},
                "w60": {
                    "n_valid": 0,
                    "window_count": 0,
                    "oldest_date": None,
                    "newest_date": None,
                    "ma": None,
                    "dev": None,
                    "window_head_dates": [],
                    "window_tail_dates": [],
                },
                "ret1": None,
                "notes": "NA:no_valid_points_after_cleaning"
            }
            continue

        newest_date, newest_val = pts[-1]
        prev_val = pts[-2][1] if n_valid >= 2 else None

        w_slice = pts[-window:] if n_valid >= window else pts[:]
        window_count = len(w_slice)
        w_old = w_slice[0][0] if window_count else None
        w_new = w_slice[-1][0] if window_count else None

        head_dates = [x[0] for x in w_slice[:3]]
        tail_dates = [x[0] for x in w_slice[-3:]]

        ma_val: Optional[float] = None
        dev_val: Optional[float] = None
        if n_valid >= window:
            ma_val = mean([x[1] for x in w_slice])
            dev_val = newest_val - ma_val

        ret1_val: Optional[float] = None
        if prev_val is not None:
            ret1_val = newest_val - prev_val

        notes = (
            f"policy=last_{window}_valid_points_by_data_date; "
            f"n_valid={n_valid}; window_count={window_count}; strict_date=YYYY-MM-DD"
        )
        if n_valid < window:
            notes += "; WARN:insufficient_points_for_ma60"

        out[sid] = {
            "series_id": sid,
            "latest": {"data_date": newest_date, "value": newest_val, "source_url": latest_source_url},
            "w60": {
                "n_valid": n_valid,
                "window_count": window_count,
                "oldest_date": w_old,
                "newest_date": w_new,
                "ma": round6(ma_val),
                "dev": round6(dev_val),
                "window_head_dates": head_dates,
                "window_tail_dates": tail_dates,
            },
            "ret1": round6(ret1_val),
            "notes": notes
        }

    return out


def main() -> int:
    now = utc_now()
    run_utc = iso_z(now)
    run_tpe = iso_taipei(now)

    cfg = load_json(CONFIG_PATH, None)
    if not cfg:
        raise SystemExit(f"Missing config: {CONFIG_PATH}")

    timeout = int(cfg.get("default_timeout_sec", 25))
    backoff = cfg.get("backoff_seconds", [2, 4, 8])
    if not isinstance(backoff, list) or not backoff:
        backoff = [2, 4, 8]

    # Load + clean + normalize history
    history_raw: List[Dict[str, Any]] = load_json(HIST_LITE_PATH, default=[])
    history_clean, clean_stats = clean_history(history_raw)
    history_norm, norm_stats = normalize_history(history_clean)

    latest: Dict[str, Any] = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_tpe,
        "script_version": "regime_inputs_cache_v1_8_normalizedHistory",
        "series": {}
    }

    dq: Dict[str, Any] = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_tpe,
        "script_version": "regime_inputs_cache_v1_8_normalizedHistory",
        "status": "OK",
        "errors": [],
        "warnings": [],
        "history_cleanup": clean_stats,
        "history_normalize": norm_stats,
        "per_series": {}
    }

    series_cfg = cfg.get("series", [])
    series_ids: List[str] = []

    # Start from normalized history (stable baseline)
    history: List[Dict[str, Any]] = history_norm[:]

    for s in series_cfg:
        sid = s.get("series_id")
        if not sid:
            continue
        series_ids.append(sid)

        fetcher = s.get("fetcher")
        expected_max = s.get("expected_max_staleness_days", None)

        source_url_for_entry: Optional[str] = s.get("url")
        if fetcher == "stooq_daily":
            symbol = s.get("symbol")
            if symbol:
                source_url_for_entry = f"https://stooq.com/q/d/l/?s={symbol}&i=d"

        entry = {
            "series_id": sid,
            "data_date": None,
            "value": None,
            "source_url": source_url_for_entry,
            "as_of_ts": run_tpe,
            "notes": None
        }

        per = {
            "ok": False,
            "fetcher": fetcher,
            "source_url": source_url_for_entry,
            "data_date": None,
            "value": None,
            "staleness_days": None,
            "expected_max_staleness_days": expected_max,
            "error": None
        }

        ok = False
        try:
            if fetcher == "stooq_daily":
                symbol = s["symbol"]
                data_date, value, real_url, parsed_rows = fetch_stooq_daily(symbol, timeout, backoff)
                entry["source_url"] = real_url
                entry["data_date"] = data_date
                entry["value"] = value
                entry["notes"] = f"ok; parsed_rows={parsed_rows}"
                ok = True

            elif fetcher == "csv_max_date":
                url = s["url"]
                date_col = s["date_col"]
                value_col = s["value_col"]
                data_date, value, real_url, header, rows_total = fetch_csv_max_date(
                    url, date_col, value_col, timeout, backoff
                )
                entry["source_url"] = real_url
                entry["data_date"] = data_date
                entry["value"] = value
                entry["notes"] = f"ok; header={header}; date_col={date_col}; value_col={value_col}; parsed_rows={rows_total}"
                ok = True

            else:
                raise RuntimeError(f"unsupported fetcher: {fetcher}")

            per["ok"] = True
            per["data_date"] = entry["data_date"]
            per["value"] = entry["value"]

            sd = staleness_days(entry["data_date"], now)  # type: ignore[arg-type]
            per["staleness_days"] = sd
            if expected_max is not None and sd is not None and sd > int(expected_max):
                dq["status"] = "WARN" if dq["status"] == "OK" else dq["status"]
                dq["warnings"].append(f"{sid}: staleness_days={sd} > expected_max={expected_max}")

        except Exception as e:
            dq["status"] = "ERR"
            err = f"{sid} fetch failed: {type(e).__name__}: {e}"
            dq["errors"].append(err)
            entry["notes"] = f"ERR:{err}"
            per["error"] = err

        latest["series"][sid] = entry
        dq["per_series"][sid] = per

        # Append only on success
        if ok and entry["data_date"] is not None and entry["value"] is not None:
            history.append({
                "series_id": sid,
                "data_date": entry["data_date"],
                "value": entry["value"],
                "source_url": entry["source_url"],
                "as_of_ts": run_tpe,
                "notes": entry["notes"]
            })

    # Re-normalize after appends (ensures stable file each run)
    history2_clean, _ = clean_history(history)
    history2_norm, norm2_stats = normalize_history(history2_clean)
    dq["history_normalize_after_append"] = norm2_stats

    features_series = compute_features(history2_norm, series_ids, window=60)
    features = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_tpe,
        "script_version": "regime_inputs_cache_v1_8_normalizedHistory",
        "features_policy": {
            "window": 60,
            "window_definition": "last 60 valid points ordered by data_date (not calendar days)",
            "ma_definition": "mean of last 60 valid points when n_valid>=60 else NA",
            "dev_definition": "latest - ma (only when ma is available)",
            "ret1_mode": "delta (latest - previous valid point)",
            "rounding": "derived numbers rounded to 6 decimals deterministically",
            "strict_date": "only accept YYYY-MM-DD dates into features window",
            "history_normalized": "inputs_history_lite.json is normalized per series_id/data_date for audit stability",
            "source": "inputs_history_lite.json"
        },
        "series": features_series
    }

    write_json_atomic(LATEST_PATH, latest)
    write_json_atomic(HIST_LITE_PATH, history2_norm)
    write_json_atomic(DQ_PATH, dq)
    write_json_atomic(FEATURES_PATH, features)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())