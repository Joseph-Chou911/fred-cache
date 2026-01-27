#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill TWSE daily index series for roll25_cache, up to N trading days.

Design goals (audit-first):
- No guessing. If fetch/parse fails => exit non-zero.
- Deterministic: you tell me the end date and limit; we walk backwards day by day.
- Rate-limit friendly: retry with backoff (2s,4s,8s).
- Output:
  - roll25_cache/roll25.json (merged, newest-first, dedup by date)
  - roll25_cache/latest_report.json (optional: you can re-run update_twse_sidecar.py after backfill)

Notes:
- This script assumes you have a TWSE endpoint that can query a specific date via `date=YYYYMMDD`.
- If your environment cannot access those endpoints, it will fail loudly.
"""

from __future__ import annotations

import json
import os
import sys
import time
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

CACHE_DIR = "roll25_cache"
ROLL25_PATH = os.path.join(CACHE_DIR, "roll25.json")

# --- Candidate endpoints (date-parameterized) ---
# You may need to adjust these if TWSE changes formats.
FMTQIK_URL_TMPL = "https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymmdd}"
MI_5MINS_HIST_URL_TMPL = "https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymmdd}"

UA = "twse-backfill/1.0 (+github-actions)"

# ---------- helpers ----------

def _ensure_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)

def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _atomic_write(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
    os.replace(tmp, path)

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == "" or s.upper() == "NA" or s.lower() == "null":
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None

def _safe_int(x: Any) -> Optional[int]:
    f = _safe_float(x)
    if f is None:
        return None
    try:
        return int(round(f))
    except Exception:
        return None

def _yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")

def _iso(d: date) -> str:
    return d.isoformat()

def _http_get_json(url: str, timeout: int = 25) -> Any:
    headers = {"Accept": "application/json", "User-Agent": UA}
    # retry w/ backoff
    for i, sleep_s in enumerate([0, 2, 4, 8], start=1):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = (i == 4)
            print(f"[WARN] GET failed (try {i}/4): {url} err={e}")
            if last:
                raise
    raise RuntimeError("unreachable")

def _unwrap_rows(payload: Any) -> List[Dict[str, Any]]:
    # common TWSE json patterns
    if isinstance(payload, dict):
        for k in ("data", "result", "records", "items", "aaData", "dataset"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, (dict, list, tuple, str, int, float))]
    if isinstance(payload, list):
        return payload  # might be list-of-dicts or list-of-lists
    return []

def _find_number_in_row(row: Any, idx: int) -> Optional[float]:
    # row may be list-like
    try:
        if isinstance(row, (list, tuple)) and idx < len(row):
            return _safe_float(row[idx])
    except Exception:
        return None
    return None

# ---------- parsing (best-effort but strict failure on "no usable") ----------

@dataclass
class Daily:
    date_iso: str
    close: Optional[float]
    change: Optional[float]
    trade_value: Optional[int]
    high: Optional[float]
    low: Optional[float]

def _parse_fmtqik_one_day(payload: Any, target_iso: str) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    """
    Return (close, change, trade_value) for target date.
    This is strict: if we cannot locate target date info, return (None,None,None).
    """
    rows = _unwrap_rows(payload)

    # TWSE website json often returns list-of-lists under 'data'
    # If list-of-lists: we must infer columns; that varies. We'll try a few patterns.
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        data = payload["data"]
        # Try find date column present in each row
        for row in data:
            if not isinstance(row, (list, tuple)):
                continue
            # Look for YYYY/MM/DD or YYYY-MM-DD in any cell
            row_str = " ".join([str(x) for x in row])
            if target_iso in row_str or target_iso.replace("-", "/") in row_str:
                # Heuristic indexes are not guaranteed; so we fail unless we can identify numbers safely.
                # Minimal safe approach: extract first 3 numeric-like fields after the date cell.
                nums = [ _safe_float(x) for x in row if _safe_float(x) is not None ]
                # Expect at least close and trade value; if not enough, treat as unusable.
                if len(nums) < 2:
                    return (None, None, None)

                # We cannot safely know which is which without schema. So: refuse to guess.
                return (None, None, None)

    # If list-of-dicts style: try keys
    if isinstance(payload, list):
        dict_rows = [r for r in payload if isinstance(r, dict)]
        for r in dict_rows:
            d = str(r.get("Date") or r.get("date") or r.get("日期") or "").strip()
            # normalize
            if d == target_iso or d.replace("/", "-") == target_iso:
                close = _safe_float(r.get("TAIEX") or r.get("Close") or r.get("close") or r.get("收盤指數") or r.get("收盤"))
                chg = _safe_float(r.get("Change") or r.get("change") or r.get("漲跌點數") or r.get("漲跌"))
                tv = _safe_int(r.get("TradeValue") or r.get("tradeValue") or r.get("成交金額"))
                return (close, chg, tv)

    return (None, None, None)

def _parse_ohlc_one_day(payload: Any, target_iso: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (high, low). Strictly return None if cannot locate.
    """
    if isinstance(payload, list):
        dict_rows = [r for r in payload if isinstance(r, dict)]
        for r in dict_rows:
            d = str(r.get("Date") or r.get("date") or r.get("日期") or "").strip()
            if d == target_iso or d.replace("/", "-") == target_iso:
                high = _safe_float(r.get("HighestIndex") or r.get("High") or r.get("high") or r.get("最高") or r.get("最高價"))
                low  = _safe_float(r.get("LowestIndex") or r.get("Low")  or r.get("low")  or r.get("最低") or r.get("最低價"))
                return (high, low)

    # TWSE website json may also be dict with "data": list-of-lists
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        data = payload["data"]
        for row in data:
            if not isinstance(row, (list, tuple)):
                continue
            row_str = " ".join([str(x) for x in row])
            if target_iso in row_str or target_iso.replace("-", "/") in row_str:
                # Cannot safely map columns without schema => refuse guessing
                return (None, None)

    return (None, None)

# ---------- merge ----------

def _merge(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    m: Dict[str, Dict[str, Any]] = {}
    for it in existing:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    for it in new_items:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    merged = list(m.values())
    merged.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    dates = [str(x.get("date", "")) for x in merged]
    return merged, (len(dates) == len(set(dates)))

# ---------- main ----------

def main() -> None:
    _ensure_dir()

    limit = int(os.environ.get("BACKFILL_LIMIT", "252").strip() or "252")
    end_iso = os.environ.get("BACKFILL_END_DATE", "").strip()  # optional: YYYY-MM-DD
    tz_name = os.environ.get("TZ", "Asia/Taipei")

    tz = ZoneInfo(tz_name)
    today_local = datetime.now(tz=tz).date()
    end_date = today_local if not end_iso else date.fromisoformat(end_iso)

    existing = _read_json(ROLL25_PATH, default=[])
    if not isinstance(existing, list):
        existing = []

    got: List[Dict[str, Any]] = []
    d = end_date
    hard_days = 800  # safety cap: don't scan forever

    print(f"[INFO] backfill start: end_date={end_date.isoformat()} limit={limit} tz={tz_name}")

    for _ in range(hard_days):
        iso = _iso(d)
        ymd = _yyyymmdd(d)

        fmt_url = FMTQIK_URL_TMPL.format(yyyymmdd=ymd)
        ohlc_url = MI_5MINS_HIST_URL_TMPL.format(yyyymmdd=ymd)

        try:
            fmt_raw = _http_get_json(fmt_url)
        except Exception as e:
            # If endpoint doesn't support date, you'll likely fail here.
            print(f"[ERROR] FMTQIK fetch failed for {iso}: {e}")
            sys.exit(1)

        try:
            ohlc_raw = _http_get_json(ohlc_url)
        except Exception as e:
            # OHLC is allowed to be missing; keep None (degrade), but we still want close+tv
            print(f"[WARN] OHLC fetch failed for {iso}: {e}")
            ohlc_raw = None

        close, chg, tv = _parse_fmtqik_one_day(fmt_raw, iso)
        high, low = (None, None)
        if ohlc_raw is not None:
            high, low = _parse_ohlc_one_day(ohlc_raw, iso)

        # STRICT: we must at least have close + trade_value to accept a day
        if close is None or tv is None:
            # likely non-trading day or parse mismatch; skip silently but log
            print(f"[SKIP] {iso} (close/trade_value missing) close={close} tv={tv}")
        else:
            got.append({
                "date": iso,
                "close": close,
                "change": chg,
                "trade_value": int(tv),
                "high": high,
                "low": low,
            })
            print(f"[OK] {iso} close={close} tv={tv} high={high} low={low}  (got={len(got)})")

        if len(got) >= limit:
            break

        d = d - timedelta(days=1)

    if not got:
        print("[FATAL] Backfill got 0 usable days. This usually means: endpoint not date-parameterized OR parse mismatch.")
        sys.exit(2)

    merged, dedupe_ok = _merge(existing, got)
    _atomic_write(ROLL25_PATH, merged)

    print(f"[DONE] backfill wrote: {ROLL25_PATH}")
    print(f"       new_days={len(got)} merged_total={len(merged)} dedupe_ok={dedupe_ok}")

    if not dedupe_ok:
        print("[FATAL] dedupe failed (duplicate dates).")
        sys.exit(3)

if __name__ == "__main__":
    main()