#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/update_tw_pb_sidecar.py

TW PB cache (TAIEX P/B ratio proxy) from TWSE RWD JSON endpoint.

Design goals (audit-first):
- Deterministic outputs
- History upsert by trading date (ISO yyyy-mm-dd)
- Backfill by months (loop months, fetch that month's table, merge)
- Produce:
  - tw_pb_cache/history.json
  - tw_pb_cache/latest.json
  - tw_pb_cache/stats_latest.json
  - (report.md rendered by separate script)
- Strict NA handling (no guessing).

NOTE:
This module intentionally avoids third-party sources that may block bots (e.g., wantgoo 403).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo


TZ = "Asia/Taipei"
OUT_DIR = "tw_pb_cache"

# Public examples reference this endpoint for market data retrieval. (RWD JSON)
# We keep it configurable via env in case TWSE changes the path.
DEFAULT_ENDPOINT = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def now_local_iso(tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return datetime.now(tz).isoformat(timespec="seconds")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def ym_first_day(ym: str) -> str:
    # ym: YYYYMM -> YYYYMM01
    return ym + "01"


def iter_ym_backfill(end_local: datetime, months: int) -> List[str]:
    # Return list like ["202601", "202512", ...] inclusive of current month, length=months+1 maybe
    y = end_local.year
    m = end_local.month
    out = []
    for k in range(months + 1):
        yy = y
        mm = m - k
        while mm <= 0:
            yy -= 1
            mm += 12
        out.append(f"{yy:04d}{mm:02d}")
    return out


def parse_minguo_date(s: str, fallback_year: int) -> Optional[str]:
    """
    TWSE often returns dates like '115/01/28' (Minguo year) or '2026/01/28'.
    Convert to ISO yyyy-mm-dd.
    """
    s = s.strip()
    # 115/01/28
    m = re.match(r"^(\d{2,4})/(\d{1,2})/(\d{1,2})$", s)
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2))
    d = int(m.group(3))
    if y < 1911:  # minguo
        y = y + 1911
    if y < 1900:  # still weird, fallback
        y = fallback_year
    try:
        dt = datetime(y, mo, d)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s in ("", "—", "-", "NA", "N/A", "null", "None"):
        return None
    s = s.replace(",", "")
    # keep only first numeric pattern
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


@dataclass
class FetchResult:
    ok: bool
    status: str
    dq_reason: Optional[str]
    data: Optional[Dict[str, Any]]
    url: str


def fetch_json(url: str, timeout: int = 20) -> FetchResult:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return FetchResult(False, f"http_{r.status_code}", f"http_{r.status_code}", None, url)
        j = r.json()
        return FetchResult(True, "OK", None, j, url)
    except Exception as e:
        return FetchResult(False, "DOWNGRADED", "fetch_or_parse_failed", None, url)


def extract_rows(j: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Attempt to locate:
      - date
      - close
      - pb (P/B or 淨值比)
    from TWSE response structure.
    Returns: (rows, schema_hint)
    """
    rows: List[Dict[str, Any]] = []
    if not isinstance(j, dict):
        return rows, None

    fields = j.get("fields")
    data = j.get("data")

    if not isinstance(fields, list) or not isinstance(data, list):
        return rows, None

    # identify columns
    def find_col(keys: List[str]) -> Optional[int]:
        for k in keys:
            for i, f in enumerate(fields):
                if k in str(f):
                    return i
        return None

    col_date = find_col(["日期"])
    col_close = find_col(["收盤指數", "收盤", "指數"])
    # P/B could be named 股價淨值比 / 淨值比 / P/B
    col_pb = find_col(["股價淨值比", "淨值比", "P/B", "PBR", "P/B Ratio"])

    schema_hint = f"fields={fields}"

    # fallback year: from query meta if present, else current year
    fallback_year = datetime.now(ZoneInfo(TZ)).year

    for row in data:
        if not isinstance(row, list):
            continue
        ds = None
        if col_date is not None and col_date < len(row):
            ds = parse_minguo_date(str(row[col_date]), fallback_year=fallback_year)
        if not ds:
            continue

        close = None
        if col_close is not None and col_close < len(row):
            close = to_float(row[col_close])

        pb = None
        if col_pb is not None and col_pb < len(row):
            pb = to_float(row[col_pb])

        # keep row even if pb is None (audit), but signal will be downgraded later
        rows.append(
            {
                "date": ds,
                "close": close,
                "pbr": pb,
            }
        )
    return rows, schema_hint


def upsert_history(existing: List[Dict[str, Any]], new_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    m: Dict[str, Dict[str, Any]] = {r["date"]: r for r in existing if isinstance(r, dict) and "date" in r}
    for r in new_rows:
        if not isinstance(r, dict) or "date" not in r:
            continue
        m[r["date"]] = r
    out = list(m.values())
    out.sort(key=lambda x: x["date"])
    return out


def rolling_stats(values: List[float], window: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Compute z-score and percentile of the last value in values[-window:].
    Percentile: rank of last value within window as [0,100].
    """
    if len(values) < window:
        return None, None, f"INSUFFICIENT_HISTORY:{len(values)}/{window}"
    w = values[-window:]
    x = w[-1]
    mu = sum(w) / window
    var = sum((v - mu) ** 2 for v in w) / window
    sd = math.sqrt(var)
    if sd == 0:
        return None, None, "STD_ZERO"
    z = (x - mu) / sd

    # percentile (inclusive rank)
    sorted_w = sorted(w)
    # count <= x
    le = 0
    for v in sorted_w:
        if v <= x:
            le += 1
        else:
            break
    p = (le / window) * 100.0
    return z, p, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default=TZ)
    ap.add_argument("--endpoint", default=os.getenv("TW_PB_ENDPOINT", DEFAULT_ENDPOINT))
    ap.add_argument("--backfill-months", type=int, default=int(os.getenv("BACKFILL_MONTHS", "0")))
    args = ap.parse_args()

    tz = args.tz
    endpoint = args.endpoint.rstrip("?")
    backfill_months = max(0, args.backfill_months)

    ensure_dir(OUT_DIR)

    generated_at_utc = now_utc_iso()
    generated_at_local = now_local_iso(tz)

    # Load existing history
    hist_path = os.path.join(OUT_DIR, "history.json")
    existing = read_json(hist_path)
    existing_rows: List[Dict[str, Any]] = []
    if existing and isinstance(existing.get("rows"), list):
        existing_rows = existing["rows"]

    # Build YM list
    end_local = datetime.now(ZoneInfo(tz))
    ym_list = iter_ym_backfill(end_local, backfill_months)

    all_new: List[Dict[str, Any]] = []
    fetch_status = "OK"
    confidence = "OK"
    dq_reason = None
    schema_hint = None

    # Fetch months
    for ym in ym_list:
        d = ym_first_day(ym)
        url = f"{endpoint}?date={d}&response=json"
        fr = fetch_json(url)
        if not fr.ok or not fr.data:
            fetch_status = "DOWNGRADED"
            confidence = "DOWNGRADED"
            dq_reason = fr.dq_reason or "fetch_failed"
            continue
        rows, hint = extract_rows(fr.data)
        if hint:
            schema_hint = hint
        if rows:
            all_new.extend(rows)
        else:
            # no rows is also a data quality issue
            fetch_status = "DOWNGRADED"
            confidence = "DOWNGRADED"
            dq_reason = dq_reason or "empty_rows"

    merged = upsert_history(existing_rows, all_new)

    # latest
    latest_row = merged[-1] if merged else None

    # stats: use pbr series only where not None
    pbr_series = [r["pbr"] for r in merged if r.get("pbr") is not None]
    z60, p60, na60 = rolling_stats([float(x) for x in pbr_series], 60)
    z252, p252, na252 = rolling_stats([float(x) for x in pbr_series], 252)

    # Derive data_date as latest date with pbr not None (stronger)
    data_date = None
    if merged:
        for r in reversed(merged):
            if r.get("pbr") is not None:
                data_date = r["date"]
                break

    # Write history.json
    history_out = {
        "schema_version": "tw_pb_history_v1",
        "generated_at_utc": generated_at_utc,
        "generated_at_local": generated_at_local,
        "timezone": tz,
        "source_vendor": "twse",
        "source_policy": "RWD_JSON",
        "endpoint": endpoint,
        "backfill_months": backfill_months,
        "fetch_status": fetch_status,
        "confidence": confidence,
        "dq_reason": dq_reason,
        "schema_hint": schema_hint,
        "rows": merged,
    }
    write_json(hist_path, history_out)

    # Write latest.json
    latest_out = {
        "schema_version": "tw_pb_latest_v1",
        "generated_at_utc": generated_at_utc,
        "generated_at_local": generated_at_local,
        "timezone": tz,
        "source_vendor": "twse",
        "source_policy": "RWD_JSON",
        "endpoint": endpoint,
        "fetch_status": fetch_status,
        "confidence": confidence,
        "dq_reason": dq_reason,
        "data_date": data_date,
        "latest": latest_row,
    }
    write_json(os.path.join(OUT_DIR, "latest.json"), latest_out)

    # Write stats_latest.json
    stats_out = {
        "schema_version": "tw_pb_stats_latest_v1",
        "generated_at_utc": generated_at_utc,
        "generated_at_local": generated_at_local,
        "timezone": tz,
        "source_vendor": "twse",
        "source_policy": "RWD_JSON",
        "endpoint": endpoint,
        "fetch_status": fetch_status,
        "confidence": confidence,
        "dq_reason": dq_reason,
        "data_date": data_date,
        "series_len_rows": len(merged),
        "series_len_pbr": len(pbr_series),
        "stats": {
            "z60": z60,
            "p60": p60,
            "na_reason_60": na60,
            "z252": z252,
            "p252": p252,
            "na_reason_252": na252,
        },
    }
    write_json(os.path.join(OUT_DIR, "stats_latest.json"), stats_out)


if __name__ == "__main__":
    main()