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

UA = "twse-sidecar/2.0 (+github-actions)"


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

def _http_get_json(url: str, timeout: int = 25) -> Any:
    headers = {"Accept": "application/json", "User-Agent": UA}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

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
    idx = {}
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
    idx = {}
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

def _merge_roll(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    m: Dict[str, Dict[str, Any]] = {}
    for it in existing:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    for it in new_items:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    merged = list(m.values())
    merged.sort(key=lambda x: str(x.get("date", "")), reverse=True)
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


# ----------------- main -----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-months", type=int, default=0, help="Fetch last N months from www.twse.com.tw monthly endpoints")
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

    daily_ok = True
    try:
        fmt_raw = _http_get_json(daily_fmt_url)
        daily_fmt_rows = _parse_fmtqik_rows(fmt_raw, schema)
        if not daily_fmt_rows:
            daily_ok = False
            print("[WARN] daily FMTQIK parsed 0 rows.")
    except Exception as e:
        daily_ok = False
        print(f"[WARN] daily FMTQIK fetch/parse failed: {e}")

    try:
        ohlc_raw = _http_get_json(daily_ohlc_url)
        daily_ohlc_rows = _parse_ohlc_rows(ohlc_raw, schema)
    except Exception as e:
        print(f"[WARN] daily MI_5MINS_HIST fetch/parse failed (downgrade): {e}")
        daily_ohlc_rows = []

    # ---- 2) BACKFILL fetch (monthly) ----
    backfill_fmt_rows: List[FmtRow] = []
    backfill_ohlc_rows: List[OhlcRow] = []

    backfill = schema.get("backfill", {})
    bf_fmt_tpl = backfill.get("fmtqik_url_tpl")
    bf_ohlc_tpl = backfill.get("mi_5mins_hist_url_tpl")

    if args.backfill_months and args.backfill_months > 0:
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

    # ---- 3) Merge daily + backfill rows ----
    fmt_rows = (daily_fmt_rows or []) + (backfill_fmt_rows or [])
    ohlc_rows = (daily_ohlc_rows or []) + (backfill_ohlc_rows or [])

    if not fmt_rows:
        print("[FATAL] no usable FMTQIK rows from daily/backfill after parsing.")
        sys.exit(1)

    fmt_by_date: Dict[str, FmtRow] = {}
    for r in fmt_rows:
        fmt_by_date[r.date] = r
    ohlc_by_date: Dict[str, OhlcRow] = {}
    for r in ohlc_rows:
        ohlc_by_date[r.date] = r

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
        prefix = "今日非交易日；"
    elif used_date_status == "DATA_NOT_UPDATED":
        prefix = "今日資料未更新；"
        extra_note = " daily endpoint has not published today's row yet"

    summary = f"{prefix}UsedDate={used_date}：Mode={mode}；freshness_ok={freshness_ok}{extra_note}"

    latest_report = {
        "generated_at": _now_tz(tz).isoformat(),
        "timezone": str(tz),
        "summary": summary,
        "numbers": {
            "UsedDate": used_date,
            "Close": None if today_close is None else round(float(today_close), 2),
            "PctChange": None if pct_change is None else round(float(pct_change), 6),
            "TradeValue": None if today_trade_value is None else int(round(float(today_trade_value))),
            "AmplitudePct": None if amplitude_pct is None else round(float(amplitude_pct), 6),
        },
        "signal": {
            "DownDay": None if (pct_change is None and today_change is None) else bool(is_down_day),
            "OhlcMissing": (not ohlc_ok),
            "UsedDateStatus": used_date_status,
            "RunDayTag": run_day_tag,
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
        "cache_tail": merged_roll[:25],
    }

    # stats
    m = _index_by_date(merged_roll, used_date)
    series_close = _series_value_desc(m, "close")
    series_tv = _series_value_desc(m, "trade_value")
    series_ret = _series_pct_change_desc(m)
    series_amp = _series_amplitude_pct_desc(m)

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
                "win60": _calc_stats_for_series(series_ret, used_date, 60),
                "win252": _calc_stats_for_series(series_ret, used_date, 252),
                "window_note": {
                    "n_total_available": len(series_ret),
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
    print(f"  close_n={len(series_close)} tv_n={len(series_tv)} ret_n={len(series_ret)} amp_n={len(series_amp)}")
    print(f"  wrote: {ROLL_PATH}, {REPORT_PATH}, {STATS_PATH}")


if __name__ == "__main__":
    main()