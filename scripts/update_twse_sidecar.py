#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWSE sidecar updater (roll25_cache/) - supports daily + month backfill.

Writes (atomic):
  - roll25_cache/roll25.json
  - roll25_cache/latest_report.json
  - roll25_cache/stats_latest.json

Key:
- Daily sources (OpenAPI):
    https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK
    https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
- Backfill sources (monthly, www.twse.com.tw):
    https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date=YYYYMM01
    https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date=YYYYMM01

Backfill logic:
- If --backfill-months > 0:
    fetch last N months, merge into cache (dedupe by date).
- Always keep STORE_CAP entries (>= BACKFILL_LIMIT).
- Stats windows 60 & 252 computed from available values <= used_date.

Notes (output semantics):
- run_day_tag: WEEKDAY / WEEKEND (weekday-only heuristic; NOT exchange calendar)
- used_date_status kept as-is:
    OK_TODAY / DATA_NOT_UPDATED / OK_LATEST / ...
- When used_date_status==DATA_NOT_UPDATED, summary adds:
    "daily endpoint has not published today's row yet"

2026-01-27 ADDITIVE UPDATE (does NOT change existing semantics/values):
- Add derived signals for unified dashboard consumption (volume multiplier, volume amplified,
  new low N, consecutive down days) using existing fields only.
- Add cache_roll25 (newest->oldest) for unified builder compatibility.
  (Keeps existing cache_tail untouched; cache_roll25 is additive.)
- All new fields are additive; existing keys/values are untouched.

2026-02-07 GUARDRAIL UPDATE (additive / non-breaking intent):
- Add HTTP retry/backoff (2s/4s/8s) for transient failures.
- Add automatic fallback to www.twse.com.tw monthly endpoints for current month when OpenAPI is blocked/unavailable,
  even when --backfill-months==0.
- Add cache-preserving merge: if new row has None for a field, keep existing non-None value
  (prevents losing historical OHLC when only one endpoint is degraded).
- Add cache-only degrade path: if both OpenAPI and monthly fallback fail, keep last cache and still emit report/stats
  anchored to cached latest date, with explicit downgrade notes (no guessing / no new data invented).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

CACHE_DIR = "roll25_cache"
SCHEMA_PATH = os.path.join(CACHE_DIR, "twse_schema.json")

ROLL_PATH = os.path.join(CACHE_DIR, "roll25.json")
REPORT_PATH = os.path.join(CACHE_DIR, "latest_report.json")
STATS_PATH = os.path.join(CACHE_DIR, "stats_latest.json")

LOOKBACK_TARGET = 20
BACKFILL_LIMIT = 252
STORE_CAP = 400  # must be >= BACKFILL_LIMIT

# NEW (additive): how many points to embed into latest_report.cache_roll25 for unified builder
REPORT_CACHE_ROLL25_CAP = 200  # keep it bounded; must be >= max(vol_n+1, dd_n, etc.)

UA = "twse-sidecar/2.1 (+github-actions)"


# ----------------- helpers -----------------

def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)

def _read_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _atomic_write_json(path: str, obj: Any) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
    os.replace(tmp, path)

def _load_schema() -> Dict[str, Any]:
    if not os.path.exists(SCHEMA_PATH):
        raise RuntimeError(f"Missing schema file: {SCHEMA_PATH}")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _tz(schema: Dict[str, Any]) -> ZoneInfo:
    return ZoneInfo(schema.get("timezone", "Asia/Taipei"))

def _now_tz(tz: ZoneInfo) -> datetime:
    return datetime.now(tz=tz)

def _today_tz(tz: ZoneInfo) -> date:
    return _now_tz(tz).date()

def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5

def _http_get_json(url: str, timeout: int = 25, *, max_tries: int = 3) -> Any:
    """
    Guardrail: retry/backoff on transient network / gateway errors.
    - Deterministic backoff: 2s, 4s, 8s
    - Does NOT "guess" payload; on final failure it raises.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL is missing/empty")

    headers = {"Accept": "application/json", "User-Agent": UA}
    backoffs = [2, 4, 8]
    last_err: Optional[BaseException] = None

    for i in range(max_tries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            # retry only if we still have attempts
            if i + 1 >= max_tries:
                break
            # deterministic backoff
            try:
                import time
                time.sleep(backoffs[min(i, len(backoffs) - 1)])
            except Exception:
                pass

    raise RuntimeError(f"HTTP GET failed after {max_tries} tries: {url} ; last_err={last_err}")

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s in ("", "NA", "na", "null", "-", "—"):
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

def _roc_slash_to_iso(roc: str) -> Optional[str]:
    m = re.match(r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$", roc.strip())
    if not m:
        return None
    y = int(m.group(1)) + 1911
    mo = int(m.group(2))
    da = int(m.group(3))
    try:
        return date(y, mo, da).isoformat()
    except Exception:
        return None

def _roc_compact_to_iso(compact: str) -> Optional[str]:
    s = compact.strip()
    if not re.match(r"^\d{7}$", s):
        return None
    try:
        roc_y = int(s[:3])
        mo = int(s[3:5])
        da = int(s[5:7])
        y = roc_y + 1911
        return date(y, mo, da).isoformat()
    except Exception:
        return None

def _parse_date_any(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if s == "":
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            return None
    iso = _roc_slash_to_iso(s)
    if iso:
        return iso
    iso2 = _roc_compact_to_iso(s)
    if iso2:
        return iso2
    return None

def _unwrap_to_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("data", "result", "records", "items", "aaData", "dataset"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        if all(not isinstance(v, list) for v in payload.values()):
            return [payload]
    return []

def _pick_first_key(row: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in row:
            return row.get(k)
    return None

def _month_yyyymm01(d: date) -> str:
    return f"{d.year:04d}{d.month:02d}01"

def _month_add(d: date, delta_months: int) -> date:
    y = d.year
    m = d.month + delta_months
    while m <= 0:
        y -= 1
        m += 12
    while m > 12:
        y += 1
        m -= 12
    return date(y, m, 1)

def _iter_months_back(d_today: date, months: int) -> List[str]:
    base = date(d_today.year, d_today.month, 1)
    out: List[str] = []
    for i in range(months):
        mm = _month_add(base, -i)
        out.append(_month_yyyymm01(mm))
    return out


# ----------------- parsing daily -----------------

@dataclass
class FmtRow:
    date: str
    trade_value: Optional[int]
    close: Optional[float]
    change: Optional[float]

def _parse_fmtqik_rows(payload: Any, schema: Dict[str, Any]) -> List[FmtRow]:
    s = schema["fmtqik"]
    rows = _unwrap_to_rows(payload)
    out: List[FmtRow] = []
    for r in rows:
        d = _parse_date_any(_pick_first_key(r, s["date_keys"]))
        if not d:
            continue
        tv = _safe_int(_pick_first_key(r, s["trade_value_keys"]))
        close = _safe_float(_pick_first_key(r, s["close_keys"]))
        chg = _safe_float(_pick_first_key(r, s["change_keys"]))
        out.append(FmtRow(d, tv, close, chg))
    out.sort(key=lambda x: x.date)
    return out

@dataclass
class OhlcRow:
    date: str
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]

def _parse_ohlc_rows(payload: Any, schema: Dict[str, Any]) -> List[OhlcRow]:
    s = schema["mi_5mins_hist"]
    rows = _unwrap_to_rows(payload)
    out: List[OhlcRow] = []
    for r in rows:
        d = _parse_date_any(_pick_first_key(r, s["date_keys"]))
        if not d:
            continue
        high = _safe_float(_pick_first_key(r, s["high_keys"]))
        low = _safe_float(_pick_first_key(r, s["low_keys"]))
        close = _safe_float(_pick_first_key(r, s["close_keys"]))
        out.append(OhlcRow(d, high, low, close))
    out.sort(key=lambda x: x.date)
    return out


# ----------------- parsing monthly (www.twse.com.tw) -----------------

def _parse_twse_monthly_fmtqik(payload: Any) -> List[FmtRow]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    fields = payload.get("fields")
    if not isinstance(data, list) or not data:
        return []
    if isinstance(data[0], dict):
        return []
    idx: Dict[str, int] = {}
    if isinstance(fields, list):
        for i, f in enumerate(fields):
            if isinstance(f, str):
                idx[f.strip()] = i

    def pick(row: List[Any], candidates: List[str]) -> Any:
        for c in candidates:
            if c in idx and idx[c] < len(row):
                return row[idx[c]]
        return None

    out: List[FmtRow] = []
    for row in data:
        if not isinstance(row, list):
            continue
        d = _parse_date_any(pick(row, ["日期", "Date", "date"]))
        if not d:
            continue
        tv = _safe_int(pick(row, ["成交金額", "TradeValue"]))
        close = _safe_float(pick(row, ["收盤指數", "收盤", "TAIEX", "Close"]))
        chg = _safe_float(pick(row, ["漲跌點數", "漲跌", "Change"]))
        out.append(FmtRow(d, tv, close, chg))
    out.sort(key=lambda x: x.date)
    return out

def _parse_twse_monthly_ohlc(payload: Any) -> List[OhlcRow]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    fields = payload.get("fields")
    if not isinstance(data, list) or not data:
        return []
    if isinstance(data[0], dict):
        return []
    idx: Dict[str, int] = {}
    if isinstance(fields, list):
        for i, f in enumerate(fields):
            if isinstance(f, str):
                idx[f.strip()] = i

    def pick(row: List[Any], candidates: List[str]) -> Any:
        for c in candidates:
            if c in idx and idx[c] < len(row):
                return row[idx[c]]
        return None

    out: List[OhlcRow] = []
    for row in data:
        if not isinstance(row, list):
            continue
        d = _parse_date_any(pick(row, ["日期", "Date", "date"]))
        if not d:
            continue
        high = _safe_float(pick(row, ["最高指數", "最高", "HighestIndex", "High"]))
        low = _safe_float(pick(row, ["最低指數", "最低", "LowestIndex", "Low"]))
        close = _safe_float(pick(row, ["收盤指數", "收盤", "ClosingIndex", "Close"]))
        out.append(OhlcRow(d, high, low, close))
    out.sort(key=lambda x: x.date)
    return out


# ----------------- cache logic -----------------

def _merge_row_keep_existing_non_none(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guardrail: prevent losing cached values when new fetch is degraded.
    Rule: for each key in new, only overwrite if new[key] is not None.
    """
    out = dict(existing) if isinstance(existing, dict) else {}
    if not isinstance(new, dict):
        return out
    for k, v in new.items():
        if k == "date":
            out["date"] = new.get("date")
            continue
        if v is not None:
            out[k] = v
    return out

def _merge_roll(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    m: Dict[str, Dict[str, Any]] = {}
    for it in existing:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    for it in new_items:
        if isinstance(it, dict) and "date" in it:
            d = str(it["date"])
            if d in m:
                m[d] = _merge_row_keep_existing_non_none(m[d], it)
            else:
                m[d] = it
    merged = list(m.values())
    merged.sort(key=lambda x: str(x.get("date", "")), reverse=True)  # newest->oldest
    merged = merged[:STORE_CAP]
    dates = [str(x.get("date", "")) for x in merged if isinstance(x, dict)]
    dedupe_ok = (len(dates) == len(set(dates)))
    return merged, dedupe_ok

def _latest_date(dates: List[str]) -> Optional[str]:
    return max(dates) if dates else None

def _pick_used_date(today: date, fmt_dates_sorted_asc: List[str]) -> Tuple[str, str, str]:
    """
    Return (used_date, run_day_tag, used_date_status)

    run_day_tag: WEEKDAY / WEEKEND (weekday-only heuristic; NOT exchange calendar)
    used_date_status:
      - OK_TODAY if today's row exists in daily/backfill merged dates
      - DATA_NOT_UPDATED if weekday but today's row absent (daily endpoint lag)
      - OK_LATEST if weekend (use latest available)
      - FMTQIK_EMPTY if no rows
    """
    if not fmt_dates_sorted_asc:
        return ("NA", "WEEKDAY", "FMTQIK_EMPTY")

    today_iso = today.isoformat()
    latest = _latest_date(fmt_dates_sorted_asc) or fmt_dates_sorted_asc[-1]

    run_day_tag = "WEEKEND" if _is_weekend(today) else "WEEKDAY"

    if _is_weekend(today):
        return (latest, run_day_tag, "OK_LATEST")

    if today_iso not in fmt_dates_sorted_asc:
        return (latest, run_day_tag, "DATA_NOT_UPDATED")

    return (today_iso, run_day_tag, "OK_TODAY")

def _extract_lookback(roll: List[Dict[str, Any]], used_date: str) -> List[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) <= used_date]
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[:LOOKBACK_TARGET]

def _find_dminus1(roll: List[Dict[str, Any]], used_date: str) -> Optional[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) < used_date]
    if not eligible:
        return None
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[0]

def _build_items_from_maps(
    fmt_by_date: Dict[str, FmtRow],
    ohlc_by_date: Dict[str, OhlcRow],
    dates_desc: List[str],
    limit: int
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in dates_desc[:limit]:
        f = fmt_by_date.get(d)
        o = ohlc_by_date.get(d)
        close = (f.close if f else None) or (o.close if o else None)
        out.append({
            "date": d,
            "close": close,
            "change": (f.change if f else None),
            "trade_value": (f.trade_value if f else None),
            "high": (o.high if o else None),
            "low": (o.low if o else None),
        })
    return out


# ----------------- stats helpers -----------------

def _avg(xs: List[float]) -> Optional[float]:
    return (sum(xs) / len(xs)) if xs else None

def _std_pop(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    mu = _avg(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return var ** 0.5

def _percentile_tie_aware(x: float, xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    less = sum(1 for v in xs if v < x)
    equal = sum(1 for v in xs if v == x)
    n = len(xs)
    return 100.0 * (less + 0.5 * equal) / n

def _calc_amplitude_pct(high: float, low: float, prev_close: float) -> Optional[float]:
    if prev_close == 0:
        return None
    return (high - low) / prev_close * 100.0

def _index_by_date(roll: List[Dict[str, Any]], used_date: str) -> Dict[str, Dict[str, Any]]:
    m: Dict[str, Dict[str, Any]] = {}
    for r in roll:
        if not isinstance(r, dict):
            continue
        d = str(r.get("date", ""))
        if not d or d > used_date:
            continue
        m[d] = r
    return m

def _dates_desc(m: Dict[str, Dict[str, Any]]) -> List[str]:
    return sorted(m.keys(), reverse=True)

def _series_value_desc(m: Dict[str, Dict[str, Any]], key: str) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for d in _dates_desc(m):
        v = _safe_float(m[d].get(key))
        if v is None:
            continue
        out.append((d, float(v)))
    return out

def _series_pct_change_desc(m: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
    ds = _dates_desc(m)
    out: List[Tuple[str, float]] = []
    for i, d in enumerate(ds):
        c = _safe_float(m[d].get("close"))
        if c is None or i + 1 >= len(ds):
            continue
        dprev = ds[i + 1]
        pc = _safe_float(m[dprev].get("close"))
        if pc is None or pc == 0:
            continue
        out.append((d, (c - pc) / pc * 100.0))
    return out

def _series_amplitude_pct_desc(m: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
    ds = _dates_desc(m)
    out: List[Tuple[str, float]] = []
    for i, d in enumerate(ds):
        h = _safe_float(m[d].get("high"))
        l = _safe_float(m[d].get("low"))
        if h is None or l is None:
            continue
        if i + 1 >= len(ds):
            continue
        dprev = ds[i + 1]
        pc = _safe_float(m[dprev].get("close"))
        if pc is None or pc == 0:
            continue
        out.append((d, (h - l) / pc * 100.0))
    return out

def _window_take(values_desc: List[Tuple[str, float]], n: int, used_date: str) -> List[float]:
    xs: List[float] = []
    for d, v in values_desc:
        if d > used_date:
            continue
        xs.append(float(v))
        if len(xs) >= n:
            break
    return xs

def _calc_stats_for_series(values_desc: List[Tuple[str, float]], used_date: str, win: int) -> Dict[str, Any]:
    x = None
    for d, v in values_desc:
        if d == used_date:
            x = float(v)
            break
    xs = _window_take(values_desc, win, used_date)
    n_actual = len(xs)
    if x is None or n_actual == 0:
        return {"value": x, "window_n_target": win, "window_n_actual": n_actual, "z": None, "p": None}
    mu = _avg(xs)
    sd = _std_pop(xs)
    z = None
    if mu is not None and sd is not None and sd != 0:
        z = (x - mu) / sd
    p = _percentile_tie_aware(x, xs)
    return {
        "value": x,
        "window_n_target": win,
        "window_n_actual": n_actual,
        "z": None if z is None else round(float(z), 6),
        "p": None if p is None else round(float(p), 3),
    }


# ----------------- ADDITIVE unified-friendly derived signals -----------------

def _take_trade_values_desc(m: Dict[str, Dict[str, Any]], used_date: str, n: int) -> List[float]:
    xs: List[float] = []
    for d in _dates_desc(m):
        if d > used_date:
            continue
        tv = _safe_float(m[d].get("trade_value"))
        if tv is None:
            continue
        xs.append(float(tv))
        if len(xs) >= n:
            break
    return xs

def _take_closes_desc(m: Dict[str, Dict[str, Any]], used_date: str, n: int) -> List[float]:
    xs: List[float] = []
    for d in _dates_desc(m):
        if d > used_date:
            continue
        c = _safe_float(m[d].get("close"))
        if c is None:
            continue
        xs.append(float(c))
        if len(xs) >= n:
            break
    return xs

def _consecutive_down_days(series_ret_desc: List[Tuple[str, float]], used_date: str, max_n: int = 60) -> Optional[int]:
    """
    Count consecutive days where daily return < 0 starting from used_date.
    Returns None if used_date return is missing.
    """
    mret = {d: float(v) for d, v in series_ret_desc}
    if used_date not in mret:
        return None
    cnt = 0
    for d, v in series_ret_desc:
        if d > used_date:
            continue
        if cnt >= max_n:
            break
        if float(v) < 0:
            cnt += 1
        else:
            break
    return cnt

def _new_low_n(today_close: Optional[float], closes_desc: List[float], n: int, min_points: int) -> Optional[int]:
    """
    Return n if today's close <= min(last n closes), else 0.
    If insufficient points -> None.
    """
    if today_close is None:
        return None
    if len(closes_desc) < min_points:
        return None
    window = closes_desc[:n]
    if len(window) < min_points:
        return None
    mn = min(window) if window else None
    if mn is None:
        return None
    return n if today_close <= mn else 0

def _vol_multiplier(today_tv: Optional[float], tv_desc: List[float], n: int, min_points: int) -> Optional[float]:
    """
    vol_multiplier = today_trade_value / avg(last n trade_values)
    NOTE: current implementation uses 'last n' INCLUDING UsedDate's value if present,
          to keep additive update non-breaking. If you want "prior n" exclude today,
          change window to tv_desc[1:n+1] and re-calibrate thresholds.
    If insufficient points -> None.
    """
    if today_tv is None:
        return None
    if len(tv_desc) < min_points:
        return None
    window = tv_desc[:n]
    if len(window) < min_points:
        return None
    mu = _avg(window)
    if mu is None or mu == 0:
        return None
    return float(today_tv) / float(mu)

def _volume_amplified(mult: Optional[float], threshold: float) -> Optional[bool]:
    if mult is None:
        return None
    return bool(mult >= threshold)


# ----------------- fetch strategy (guardrail) -----------------

def _fetch_month_current(schema: Dict[str, Any], today: date) -> Tuple[List[FmtRow], List[OhlcRow], List[str]]:
    """
    Fetch current month from www.twse.com.tw monthly endpoints.
    Returns (fmt_rows, ohlc_rows, notes)
    """
    notes: List[str] = []
    backfill = schema.get("backfill", {})
    bf_fmt_tpl = backfill.get("fmtqik_url_tpl")
    bf_ohlc_tpl = backfill.get("mi_5mins_hist_url_tpl")

    if not isinstance(bf_fmt_tpl, str) or "{yyyymm01}" not in bf_fmt_tpl:
        notes.append("monthly_fallback_fmtqik_tpl_missing")
        return ([], [], notes)
    if not isinstance(bf_ohlc_tpl, str) or "{yyyymm01}" not in bf_ohlc_tpl:
        notes.append("monthly_fallback_mi_5mins_hist_tpl_missing")
        return ([], [], notes)

    yyyymm01 = _month_yyyymm01(date(today.year, today.month, 1))
    try:
        url = bf_fmt_tpl.format(yyyymm01=yyyymm01)
        p = _http_get_json(url)
        fmt_rows = _parse_twse_monthly_fmtqik(p)
    except Exception as e:
        notes.append(f"monthly_fallback_fmtqik_failed:{e}")
        fmt_rows = []

    try:
        url = bf_ohlc_tpl.format(yyyymm01=yyyymm01)
        p = _http_get_json(url)
        ohlc_rows = _parse_twse_monthly_ohlc(p)
    except Exception as e:
        notes.append(f"monthly_fallback_ohlc_failed:{e}")
        ohlc_rows = []

    if fmt_rows:
        notes.append(f"monthly_fallback_used:yyyymm01={yyyymm01}")
    return (fmt_rows, ohlc_rows, notes)


# ----------------- main -----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-months", type=int, default=0, help="Fetch last N months from www.twse.com.tw monthly endpoints")
    ap.add_argument("--prefer-monthly", action="store_true",
                    help="Guardrail: skip OpenAPI and use monthly endpoints first (useful when OpenAPI is blocked)")
    args = ap.parse_args()

    try:
        schema = _load_schema()
    except Exception as e:
        print(f"[FATAL] schema load failed: {e}")
        sys.exit(1)

    tz = _tz(schema)
    _ensure_cache_dir()

    existing_roll = _read_json_file(ROLL_PATH, default=[])
    if not isinstance(existing_roll, list):
        existing_roll = []

    today = _today_tz(tz)

    # ---- 1) DAILY fetch (OpenAPI) ----
    daily_fmt_rows: List[FmtRow] = []
    daily_ohlc_rows: List[OhlcRow] = []

    daily = schema.get("daily", {})
    daily_fmt_url = daily.get("fmtqik_url")
    daily_ohlc_url = daily.get("mi_5mins_hist_url")

    # Diagnostics (additive)
    fetch_notes: List[str] = []
    fetch_plan = "openapi_primary"
    if args.prefer_monthly:
        fetch_plan = "monthly_primary(--prefer-monthly)"

    if not isinstance(daily_fmt_url, str) or not daily_fmt_url.strip():
        fetch_notes.append("daily_fmtqik_url_missing")
    if not isinstance(daily_ohlc_url, str) or not daily_ohlc_url.strip():
        fetch_notes.append("daily_mi_5mins_hist_url_missing")

    daily_ok = True

    if (not args.prefer_monthly) and (not _is_weekend(today)) and isinstance(daily_fmt_url, str) and daily_fmt_url.strip():
        try:
            fmt_raw = _http_get_json(daily_fmt_url)
            daily_fmt_rows = _parse_fmtqik_rows(fmt_raw, schema)
            if not daily_fmt_rows:
                daily_ok = False
                fetch_notes.append("openapi_fmtqik_parsed_0_rows")
        except Exception as e:
            daily_ok = False
            fetch_notes.append(f"openapi_fmtqik_failed:{e}")
    else:
        daily_ok = False
        if args.prefer_monthly:
            fetch_notes.append("openapi_skipped_prefer_monthly")
        elif _is_weekend(today):
            fetch_notes.append("openapi_skipped_weekend")
        else:
            fetch_notes.append("openapi_skipped_missing_url")

    if (not args.prefer_monthly) and isinstance(daily_ohlc_url, str) and daily_ohlc_url.strip():
        try:
            ohlc_raw = _http_get_json(daily_ohlc_url)
            daily_ohlc_rows = _parse_ohlc_rows(ohlc_raw, schema)
        except Exception as e:
            fetch_notes.append(f"openapi_ohlc_failed(downgrade):{e}")
            daily_ohlc_rows = []
    else:
        daily_ohlc_rows = []
        if args.prefer_monthly:
            fetch_notes.append("openapi_ohlc_skipped_prefer_monthly")

    # ---- 1b) Monthly fallback for current month (guardrail) ----
    month_fmt_rows: List[FmtRow] = []
    month_ohlc_rows: List[OhlcRow] = []
    month_notes: List[str] = []

    if not daily_fmt_rows:
        fetch_plan = "monthly_fallback_current_month"
        month_fmt_rows, month_ohlc_rows, month_notes = _fetch_month_current(schema, today)
        fetch_notes.extend(month_notes)

    # ---- 2) BACKFILL fetch (monthly historical) ----
    backfill_fmt_rows: List[FmtRow] = []
    backfill_ohlc_rows: List[OhlcRow] = []

    backfill = schema.get("backfill", {})
    bf_fmt_tpl = backfill.get("fmtqik_url_tpl")
    bf_ohlc_tpl = backfill.get("mi_5mins_hist_url_tpl")

    if args.backfill_months and args.backfill_months > 0:
        if not isinstance(bf_fmt_tpl, str) or "{yyyymm01}" not in bf_fmt_tpl:
            print("[FATAL] schema.backfill.fmtqik_url_tpl missing/invalid (needs '{yyyymm01}')")
            sys.exit(1)
        if not isinstance(bf_ohlc_tpl, str) or "{yyyymm01}" not in bf_ohlc_tpl:
            print("[FATAL] schema.backfill.mi_5mins_hist_url_tpl missing/invalid (needs '{yyyymm01}')")
            sys.exit(1)

        print(f"[INFO] backfill_months={args.backfill_months} enabled.")
        yyyymm01_list = _iter_months_back(today, args.backfill_months)
        for yyyymm01 in yyyymm01_list:
            try:
                url = bf_fmt_tpl.format(yyyymm01=yyyymm01)
                p = _http_get_json(url)
                backfill_fmt_rows.extend(_parse_twse_monthly_fmtqik(p))
            except Exception as e:
                print(f"[WARN] backfill FMTQIK month={yyyymm01} failed: {e}")
            try:
                url = bf_ohlc_tpl.format(yyyymm01=yyyymm01)
                p = _http_get_json(url)
                backfill_ohlc_rows.extend(_parse_twse_monthly_ohlc(p))
            except Exception as e:
                print(f"[WARN] backfill MI_5MINS_HIST month={yyyymm01} failed: {e}")

    # ---- 3) Merge rows (OpenAPI/month-fallback/backfill) ----
    fmt_rows = (daily_fmt_rows or []) + (month_fmt_rows or []) + (backfill_fmt_rows or [])
    ohlc_rows = (daily_ohlc_rows or []) + (month_ohlc_rows or []) + (backfill_ohlc_rows or [])

    cache_only_mode = False
    cache_only_reason = ""

    if not fmt_rows:
        # Guardrail: allow cache-only degrade (no guessing, no new data)
        if existing_roll:
            cache_only_mode = True
            cache_only_reason = "no_fmt_rows_from_openapi_or_monthly; using_existing_cache_only"
            fetch_notes.append(cache_only_reason)
        else:
            print("[FATAL] no usable FMTQIK rows from openapi/monthly/backfill and no existing cache.")
            sys.exit(1)

    if cache_only_mode:
        # build fmt_by_date & ohlc_by_date from cache (best-effort)
        fmt_by_date = {}
        ohlc_by_date = {}
        for r in existing_roll:
            if not isinstance(r, dict):
                continue
            d = str(r.get("date", "")).strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                continue
            # note: cache already stores unified row; reuse
            tv = _safe_int(r.get("trade_value"))
            close = _safe_float(r.get("close"))
            chg = _safe_float(r.get("change"))
            fmt_by_date[d] = FmtRow(d, tv, close, chg)
            high = _safe_float(r.get("high"))
            low = _safe_float(r.get("low"))
            oclose = _safe_float(r.get("close"))
            ohlc_by_date[d] = OhlcRow(d, high, low, oclose)
    else:
        fmt_by_date = {r.date: r for r in fmt_rows}
        ohlc_by_date = {r.date: r for r in ohlc_rows}

    fmt_dates_asc = sorted(fmt_by_date.keys())
    used_date, run_day_tag, used_date_status = _pick_used_date(today, fmt_dates_asc)
    if used_date == "NA":
        print("[FATAL] UsedDate could not be determined.")
        sys.exit(1)

    fmt_dates_desc = sorted(fmt_by_date.keys(), reverse=True)
    new_items = _build_items_from_maps(fmt_by_date, ohlc_by_date, fmt_dates_desc, limit=BACKFILL_LIMIT)

    merged_roll, dedupe_ok = _merge_roll(existing_roll, new_items)

    lookback = _extract_lookback(merged_roll, used_date)
    n_actual = len(lookback)
    oldest = lookback[-1]["date"] if lookback else "NA"

    # freshness
    freshness_ok = True
    freshness_age_days = None
    try:
        used_dt = datetime.fromisoformat(str(used_date)).date()
        freshness_age_days = (today - used_dt).days
        if freshness_age_days > 7:
            freshness_ok = False
    except Exception:
        freshness_ok = False

    # used row
    m_used = _index_by_date(merged_roll, used_date)
    row_used = m_used.get(used_date, {})

    ohlc_ok = bool(
        row_used
        and _safe_float(row_used.get("high")) is not None
        and _safe_float(row_used.get("low")) is not None
    )
    mode = "FULL" if ohlc_ok else "MISSING_OHLC"
    ohlc_status = "OK" if ohlc_ok else "MISSING"

    # D-1
    dminus1 = _find_dminus1(merged_roll, used_date)
    used_dminus1 = dminus1["date"] if dminus1 else "NA"
    prev_close = _safe_float(dminus1.get("close")) if dminus1 else None

    today_close = _safe_float(row_used.get("close"))
    today_trade_value = _safe_float(row_used.get("trade_value"))
    today_change = _safe_float(row_used.get("change"))
    high = _safe_float(row_used.get("high"))
    low = _safe_float(row_used.get("low"))

    pct_change = None
    if today_close is not None and prev_close is not None and prev_close != 0:
        pct_change = (today_close - prev_close) / prev_close * 100.0

    amplitude_pct = None
    if ohlc_ok and prev_close is not None and prev_close != 0 and high is not None and low is not None:
        amplitude_pct = _calc_amplitude_pct(high, low, prev_close)

    is_down_day = (pct_change is not None and pct_change < 0) or (today_change is not None and today_change < 0)

    # summary prefix + extra note for DATA_NOT_UPDATED
    prefix = ""
    extra_note = ""
    if run_day_tag == "WEEKEND":
        prefix = "今日為週末；"
    elif used_date_status == "DATA_NOT_UPDATED":
        prefix = "今日資料未更新；"
        extra_note = "；daily endpoint has not published today's row yet"

    if cache_only_mode:
        prefix = "資料來源降級(僅使用既有快取)；" + prefix
        extra_note += "；cache-only degrade (no new fetch)"

    summary = f"{prefix}UsedDate={used_date}：Mode={mode}；freshness_ok={freshness_ok}{extra_note}"

    # -------- ADDITIVE derived signals for unified (do not change existing values) --------
    VOL_WIN = 20
    VOL_MIN_POINTS = 15
    VOL_THRESHOLD = 1.5

    NEWLOW_N = 60
    NEWLOW_MIN_POINTS = 40

    m_all = _index_by_date(merged_roll, used_date)
    tv_desc = _take_trade_values_desc(m_all, used_date, VOL_WIN)
    closes_desc = _take_closes_desc(m_all, used_date, NEWLOW_N)

    vol_mult_20 = _vol_multiplier(today_trade_value, tv_desc, VOL_WIN, VOL_MIN_POINTS)
    volume_ampl = _volume_amplified(vol_mult_20, VOL_THRESHOLD)

    new_low_n = _new_low_n(today_close, closes_desc, NEWLOW_N, NEWLOW_MIN_POINTS)

    series_ret = _series_pct_change_desc(m_all)
    cons_down = _consecutive_down_days(series_ret, used_date, max_n=60)

    additive_signal = {
        "VolumeAmplified": volume_ampl,
        "VolAmplified": volume_ampl,          # alias
        "NewLow_N": new_low_n,
        "ConsecutiveBreak": cons_down,
        "LookbackNTarget": LOOKBACK_TARGET,
        "LookbackNActual": n_actual,
        "VolMultiplier": None if vol_mult_20 is None else round(float(vol_mult_20), 6),
        "VolumeMultiplier": None if vol_mult_20 is None else round(float(vol_mult_20), 6),
        "VolWin": VOL_WIN,
        "VolThreshold": VOL_THRESHOLD,
        "NewLowWin": NEWLOW_N,
    }

    # NEW (additive): cache_roll25 for unified builder
    cache_roll25 = merged_roll[: max(LOOKBACK_TARGET + 5, min(REPORT_CACHE_ROLL25_CAP, len(merged_roll)))]

    latest_report = {
        "generated_at": _now_tz(tz).isoformat(),
        "timezone": str(tz),
        "summary": summary,

        # GUARDRAIL DIAGNOSTICS (additive)
        "fetch": {
            "fetch_plan": fetch_plan,
            "notes": fetch_notes[:50],  # keep bounded
        },

        "numbers": {
            "UsedDate": used_date,
            "Close": None if today_close is None else round(float(today_close), 2),
            "PctChange": None if pct_change is None else round(float(pct_change), 6),
            "TradeValue": None if today_trade_value is None else int(round(float(today_trade_value))),
            "AmplitudePct": None if amplitude_pct is None else round(float(amplitude_pct), 6),

            # ADDITIVE unified-friendly numbers (do not remove/alter existing keys)
            "VolMultiplier": None if vol_mult_20 is None else round(float(vol_mult_20), 6),
            "VolumeMultiplier": None if vol_mult_20 is None else round(float(vol_mult_20), 6),
            "LookbackNTarget": LOOKBACK_TARGET,
            "LookbackNActual": n_actual,
        },
        "signal": {
            # existing keys (unchanged)
            "DownDay": None if (pct_change is None and today_change is None) else bool(is_down_day),
            "OhlcMissing": (not ohlc_ok),
            "UsedDateStatus": used_date_status,
            "RunDayTag": run_day_tag,

            # ADDITIVE keys
            **additive_signal,
        },
        "action": "維持風險控管紀律；如資料延遲或 OHLC 缺失，避免做過度解讀，待資料補齊再對照完整條件。",
        "caveats": "\n".join([
            f"Sources: daily_fmtqik={daily_fmt_url} ; daily_mi_5mins_hist={daily_ohlc_url}",
            f"Sources: backfill_fmtqik_tpl={bf_fmt_tpl} ; backfill_mi_5mins_hist_tpl={bf_ohlc_tpl}",
            "run_day_tag is weekday-only heuristic (not exchange calendar)",
            f"BackfillMonths={args.backfill_months} | BackfillLimit={BACKFILL_LIMIT} | StoreCap={STORE_CAP} | LookbackTarget={LOOKBACK_TARGET}",
            f"Mode={mode} | OHLC={ohlc_status} | UsedDate={used_date} | UsedDminus1={used_dminus1}",
            f"RunDayTag={run_day_tag} | UsedDateStatus={used_date_status}",
            f"freshness_ok={freshness_ok} | freshness_age_days={freshness_age_days}",
            f"dedupe_ok={dedupe_ok}",
            f"REPORT_CACHE_ROLL25_CAP={REPORT_CACHE_ROLL25_CAP} (cache_roll25 points embedded in latest_report)",
            # additive derived definition audit line
            f"ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last{VOL_WIN}) "
            f"(min_points={VOL_MIN_POINTS}); VolumeAmplified=(>= {VOL_THRESHOLD}); "
            f"NewLow_N: {NEWLOW_N} if close<=min(close_last{NEWLOW_N}) (min_points={NEWLOW_MIN_POINTS}) else 0; "
            f"ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.",
            "ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).",
            "GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).",
        ]),
        "run_day_tag": run_day_tag,
        "used_date_status": used_date_status,
        "tag": run_day_tag,
        "freshness_ok": freshness_ok,
        "freshness_age_days": freshness_age_days,
        "mode": mode,
        "ohlc_status": ohlc_status,
        "used_date": used_date,
        "used_dminus1": used_dminus1,
        "lookback_n_actual": n_actual,
        "lookback_oldest": oldest,

        # EXISTING (kept): cache_tail
        "cache_tail": merged_roll[:25],

        # NEW (additive): unified builder expects this key
        "cache_roll25": cache_roll25,
    }

    # stats
    series_close = _series_value_desc(m_all, "close")
    series_tv = _series_value_desc(m_all, "trade_value")
    series_ret2 = _series_pct_change_desc(m_all)
    series_amp = _series_amplitude_pct_desc(m_all)

    stats = {
        "schema_version": "twse_stats_v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_at_local": _now_tz(tz).isoformat(),
        "timezone": str(tz),

        "used_date": used_date,
        "run_day_tag": run_day_tag,
        "used_date_status": used_date_status,

        "freshness_ok": freshness_ok,
        "freshness_age_days": freshness_age_days,

        "mode": mode,
        "ohlc_status": ohlc_status,

        "backfill_months": args.backfill_months,
        "backfill_limit": BACKFILL_LIMIT,
        "store_cap": STORE_CAP,

        # GUARDRAIL DIAGNOSTICS (additive)
        "fetch": {
            "fetch_plan": fetch_plan,
            "cache_only_mode": cache_only_mode,
            "cache_only_reason": cache_only_reason,
            "notes": fetch_notes[:50],
        },

        "series": {
            "close": {
                "asof": used_date,
                "win60": _calc_stats_for_series(series_close, used_date, 60),
                "win252": _calc_stats_for_series(series_close, used_date, 252),
                "window_note": {"n_total_available": len(series_close)}
            },
            "trade_value": {
                "asof": used_date,
                "win60": _calc_stats_for_series(series_tv, used_date, 60),
                "win252": _calc_stats_for_series(series_tv, used_date, 252),
                "window_note": {"n_total_available": len(series_tv)}
            },
            "pct_change": {
                "asof": used_date,
                "win60": _calc_stats_for_series(series_ret2, used_date, 60),
                "win252": _calc_stats_for_series(series_ret2, used_date, 252),
                "window_note": {
                    "n_total_available": len(series_ret2),
                    "note": "pct_change needs D-1 close; with backfill_limit=252, max pct_change points are typically <=251."
                }
            },
            "amplitude_pct": {
                "asof": used_date,
                "win60": _calc_stats_for_series(series_amp, used_date, 60),
                "win252": _calc_stats_for_series(series_amp, used_date, 252),
                "window_note": {
                    "n_total_available": len(series_amp),
                    "note": "amplitude_pct needs high/low + D-1 close; if OHLC missing, series is sparse and windows may be incomplete."
                }
            }
        },

        # ADDITIVE derived (for unified if it prefers stats)
        "derived": {
            "lookback_n_target": LOOKBACK_TARGET,
            "lookback_n_actual": n_actual,
            "vol_multiplier_20": None if vol_mult_20 is None else round(float(vol_mult_20), 6),
            "volume_amplified": volume_ampl,
            "new_low_n": new_low_n,
            "consecutive_down_days": cons_down,
            "definition": {
                "vol_win": VOL_WIN,
                "vol_threshold": VOL_THRESHOLD,
                "vol_min_points": VOL_MIN_POINTS,
                "newlow_win": NEWLOW_N,
                "newlow_min_points": NEWLOW_MIN_POINTS
            }
        },

        "sources": {
            "daily_fmtqik_url": daily_fmt_url,
            "daily_mi_5mins_hist_url": daily_ohlc_url,
            "backfill_fmtqik_url_tpl": bf_fmt_tpl,
            "backfill_mi_5mins_hist_url_tpl": bf_ohlc_tpl
        }
    }

    _atomic_write_json(ROLL_PATH, merged_roll)
    _atomic_write_json(REPORT_PATH, latest_report)
    _atomic_write_json(STATS_PATH, stats)

    print("TWSE sidecar updated:")
    print(f"  UsedDate={used_date} Mode={mode} freshness_ok={freshness_ok} age_days={freshness_age_days}")
    print(f"  run_day_tag={run_day_tag} used_date_status={used_date_status}")
    print(f"  roll_records={len(merged_roll)} dedupe_ok={dedupe_ok}")
    print(f"  close_n={len(series_close)} tv_n={len(series_tv)} ret_n={len(series_ret2)} amp_n={len(series_amp)}")
    print(f"  ADDITIVE: vol_multiplier_20={None if vol_mult_20 is None else round(float(vol_mult_20), 6)} "
          f"VolumeAmplified={volume_ampl} NewLow_N={new_low_n} ConsecutiveBreak={cons_down}")
    print(f"  ADDITIVE: latest_report.cache_roll25 points={len(cache_roll25)} (newest->oldest)")
    print(f"  GUARDRAIL: fetch_plan={fetch_plan} cache_only_mode={cache_only_mode}")
    print(f"  wrote: {ROLL_PATH}, {REPORT_PATH}, {STATS_PATH}")


if __name__ == "__main__":
    main()
