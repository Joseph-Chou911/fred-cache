#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWSE sidecar updater (roll25_cache/)

Key behaviors:
- Daily primary source: TWSE OpenAPI
  - FMTQIK is required in "daily mode", but in "backfill mode" we allow fallback to TWSE website current-month JSON.
  - MI_5MINS_HIST is optional; missing => downgrade to MISSING_OHLC (but still write).

- Optional monthly backfill (TWSE website JSON):
  - Merge historical rows into cache (dedupe by date).
  - Older gaps are allowed (no guessing).

- Outputs (atomic):
  - roll25_cache/roll25.json
  - roll25_cache/latest_report.json
  - roll25_cache/stats_latest.json

Audit-first:
- Do not invent missing numbers.
- If windows are incomplete for win60/win252 => z/p = None.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import requests

CACHE_DIR = "roll25_cache"
SCHEMA_PATH = os.path.join(CACHE_DIR, "twse_schema.json")

ROLL_PATH = os.path.join(CACHE_DIR, "roll25.json")
REPORT_PATH = os.path.join(CACHE_DIR, "latest_report.json")
STATS_PATH = os.path.join(CACHE_DIR, "stats_latest.json")

LOOKBACK_TARGET = 20
DEFAULT_BACKFILL_LIMIT = 252
STORE_CAP = 400

UA = "twse-sidecar/1.9 (+github-actions)"


# ----------------- helpers -----------------

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

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s in ("", "NA", "na", "null", "-", "—", "None"):
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

def _http_get_json(url: str, timeout: int = 25) -> Any:
    headers = {"Accept": "application/json", "User-Agent": UA}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _http_get_json_retry(url: str, tries: int = 3, timeout: int = 25) -> Any:
    last_err: Optional[Exception] = None
    for i in range(tries):
        try:
            return _http_get_json(url, timeout=timeout)
        except Exception as e:
            last_err = e
            if i == tries - 1:
                break
            # backoff 2s, 4s
            time.sleep(2 ** (i + 1))
    raise last_err or RuntimeError("http_get_json_retry failed")

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
    return None

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

def _diag_payload(name: str, payload: Any) -> None:
    print(f"[DIAG] {name}: type={type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"[DIAG] {name}: top_keys={list(payload.keys())[:40]}")
        # print a few common error fields if exist
        for k in ("stat", "msg", "message", "error", "errors", "code"):
            if k in payload:
                print(f"[DIAG] {name}: {k}={payload.get(k)}")
    elif isinstance(payload, list):
        print(f"[DIAG] {name}: list_len={len(payload)}")
        if payload:
            x0 = payload[0]
            print(f"[DIAG] {name}: row0_type={type(x0).__name__}")
            if isinstance(x0, dict):
                print(f"[DIAG] {name}: row0_keys={list(x0.keys())[:40]}")


# ----------------- openapi parsing -----------------

def _unwrap_openapi_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("data", "result", "records", "items", "aaData", "dataset"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        # single dict row (but might be error)
        if all(not isinstance(v, list) for v in payload.values()):
            return [payload]
    return []

def _pick_first_key(row: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in row:
            return row.get(k)
    return None

@dataclass
class FmtRow:
    date: str
    trade_value: Optional[int]
    close: Optional[float]
    change: Optional[float]

def _parse_openapi_fmtqik(payload: Any, schema: Dict[str, Any]) -> List[FmtRow]:
    s = schema["fmtqik"]
    rows = _unwrap_openapi_rows(payload)
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

def _parse_openapi_ohlc(payload: Any, schema: Dict[str, Any]) -> List[OhlcRow]:
    s = schema["mi_5mins_hist"]
    rows = _unwrap_openapi_rows(payload)
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


# ----------------- website monthly backfill parsing -----------------

def _unwrap_twse_table(payload: Any) -> Tuple[List[str], List[List[Any]]]:
    if not isinstance(payload, dict):
        return ([], [])
    fields = payload.get("fields")
    data_ = payload.get("data")
    if not isinstance(fields, list) or not isinstance(data_, list):
        return ([], [])
    fields_str = [str(x).strip() for x in fields]
    rows: List[List[Any]] = []
    for r in data_:
        if isinstance(r, list):
            rows.append(r)
    return (fields_str, rows)

def _find_field_idx(fields: List[str], candidates: List[str]) -> Optional[int]:
    for i, f in enumerate(fields):
        for c in candidates:
            if f == c:
                return i
    for i, f in enumerate(fields):
        for c in candidates:
            if c in f:
                return i
    return None

def _parse_twse_month_fmtqik(payload: Any) -> List[FmtRow]:
    fields, rows = _unwrap_twse_table(payload)
    if not fields or not rows:
        return []
    i_date = _find_field_idx(fields, ["日期"])
    i_tv = _find_field_idx(fields, ["成交金額"])
    i_close = _find_field_idx(fields, ["發行量加權股價指數", "加權股價指數", "收盤指數"])
    i_chg = _find_field_idx(fields, ["漲跌點數", "漲跌"])
    if i_date is None:
        return []
    out: List[FmtRow] = []
    for r in rows:
        if i_date >= len(r):
            continue
        d = _parse_date_any(r[i_date])
        if not d:
            continue
        tv = _safe_int(r[i_tv]) if (i_tv is not None and i_tv < len(r)) else None
        close = _safe_float(r[i_close]) if (i_close is not None and i_close < len(r)) else None
        chg = _safe_float(r[i_chg]) if (i_chg is not None and i_chg < len(r)) else None
        out.append(FmtRow(d, tv, close, chg))
    out.sort(key=lambda x: x.date)
    return out

def _parse_twse_month_ohlc(payload: Any) -> List[OhlcRow]:
    fields, rows = _unwrap_twse_table(payload)
    if not fields or not rows:
        return []
    i_date = _find_field_idx(fields, ["日期"])
    i_high = _find_field_idx(fields, ["最高指數", "最高"])
    i_low = _find_field_idx(fields, ["最低指數", "最低"])
    i_close = _find_field_idx(fields, ["收盤指數", "收盤"])
    if i_date is None:
        return []
    out: List[OhlcRow] = []
    for r in rows:
        if i_date >= len(r):
            continue
        d = _parse_date_any(r[i_date])
        if not d:
            continue
        high = _safe_float(r[i_high]) if (i_high is not None and i_high < len(r)) else None
        low = _safe_float(r[i_low]) if (i_low is not None and i_low < len(r)) else None
        close = _safe_float(r[i_close]) if (i_close is not None and i_close < len(r)) else None
        out.append(OhlcRow(d, high, low, close))
    out.sort(key=lambda x: x.date)
    return out

def _month_key_yyyymm01(d: date) -> str:
    return f"{d.year:04d}{d.month:02d}01"

def _month_starts_back(today: date, months: int) -> List[str]:
    if months <= 0:
        return []
    cur = date(today.year, today.month, 1)
    out: List[str] = []
    y, m = cur.year, cur.month
    for _ in range(months):
        out.append(f"{y:04d}{m:02d}01")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out  # newest->oldest


# ----------------- cache logic -----------------

def _merge_roll(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]], store_cap: int) -> Tuple[List[Dict[str, Any]], bool]:
    m: Dict[str, Dict[str, Any]] = {}
    for it in existing:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    for it in new_items:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    merged = list(m.values())
    merged.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    merged = merged[:store_cap]
    dates = [str(x.get("date", "")) for x in merged if isinstance(x, dict)]
    dedupe_ok = (len(dates) == len(set(dates)))
    return merged, dedupe_ok

def _latest_date(dates: List[str]) -> Optional[str]:
    return max(dates) if dates else None

def _pick_used_date(today: date, fmt_dates_sorted_asc: List[str]) -> Tuple[str, str, str]:
    if not fmt_dates_sorted_asc:
        return ("NA", "FMTQIK_EMPTY", "FMTQIK_EMPTY")
    today_iso = today.isoformat()
    latest = _latest_date(fmt_dates_sorted_asc) or fmt_dates_sorted_asc[-1]
    if _is_weekend(today):
        return (latest, "NON_TRADING_DAY", "OK_LATEST")
    if today_iso not in fmt_dates_sorted_asc:
        return (latest, "TRADING_DAY", "DATA_NOT_UPDATED")
    return (today_iso, "TRADING_DAY", "OK_TODAY")

def _extract_lookback(roll: List[Dict[str, Any]], used_date: str, n: int) -> List[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) <= used_date]
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[:n]

def _find_dminus1(roll: List[Dict[str, Any]], used_date: str) -> Optional[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) < used_date]
    if not eligible:
        return None
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[0]


# ----------------- series + stats -----------------

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
    if x is None or n_actual < win:
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


# ----------------- build items -----------------

def _items_from_maps(fmt_by_date: Dict[str, FmtRow], ohlc_by_date: Dict[str, OhlcRow], dates_desc: List[str], limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in dates_desc[:limit]:
        f = fmt_by_date.get(d)
        o = ohlc_by_date.get(d)
        close = None
        if f and f.close is not None:
            close = f.close
        elif o and o.close is not None:
            close = o.close
        out.append({
            "date": d,
            "close": close,
            "change": (f.change if f else None),
            "trade_value": (f.trade_value if f else None),
            "high": (o.high if o else None),
            "low": (o.low if o else None),
        })
    return out


# ----------------- main -----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-months", type=int, default=0, help="Months to fetch from www.twse.com.tw endpoints (0 disables).")
    ap.add_argument("--backfill-limit", type=int, default=DEFAULT_BACKFILL_LIMIT, help="How many newest trading dates to merge.")
    ap.add_argument("--daily-tries", type=int, default=3, help="Retry count for daily OpenAPI calls.")
    args = ap.parse_args()

    try:
        schema = _load_schema()
    except Exception as e:
        print(f"[FATAL] schema load failed: {e}")
        sys.exit(1)

    tz = _tz(schema)
    _ensure_dir()

    existing_roll = _read_json(ROLL_PATH, default=[])
    if not isinstance(existing_roll, list):
        existing_roll = []

    sources_out: Dict[str, Any] = {
        "daily_fmtqik_url": schema["fmtqik"]["url"],
        "daily_mi_5mins_hist_url": schema["mi_5mins_hist"]["url"],
    }

    backfill_fmt_tpl = schema.get("backfill_fmtqik_url_tpl")
    backfill_ohlc_tpl = schema.get("backfill_mi_5mins_hist_url_tpl")

    # ---- daily openapi fetch (primary) ----
    daily_fmt_raw = None
    daily_ohlc_raw = None

    try:
        daily_fmt_raw = _http_get_json_retry(schema["fmtqik"]["url"], tries=args.daily_tries)
    except Exception as e:
        print(f"[WARN] daily OpenAPI FMTQIK fetch failed: {e}")
        daily_fmt_raw = None

    try:
        daily_ohlc_raw = _http_get_json_retry(schema["mi_5mins_hist"]["url"], tries=args.daily_tries)
    except Exception as e:
        print(f"[WARN] daily OpenAPI MI_5MINS_HIST fetch failed (downgrade): {e}")
        daily_ohlc_raw = []

    fmt_rows_daily: List[FmtRow] = []
    if daily_fmt_raw is not None:
        fmt_rows_daily = _parse_openapi_fmtqik(daily_fmt_raw, schema)

    # ---- Fallback rule: if daily fmt is unusable AND backfill mode is enabled ----
    daily_source = "openapi"
    if not fmt_rows_daily and args.backfill_months > 0:
        print("[WARN] daily FMTQIK returned no usable rows/dates after parsing; fallback to TWSE website current-month JSON.")
        if daily_fmt_raw is not None:
            _diag_payload("daily_openapi_fmtqik", daily_fmt_raw)

        if not backfill_fmt_tpl:
            print("[FATAL] fallback needed but backfill_fmtqik_url_tpl missing in schema.")
            sys.exit(1)

        try:
            yyyymm01 = _month_key_yyyymm01(_today_tz(tz))
            url = backfill_fmt_tpl.format(yyyymm01=yyyymm01)
            payload = _http_get_json_retry(url, tries=3)
            fmt_rows_daily = _parse_twse_month_fmtqik(payload)
            daily_source = "website_current_month_fallback"
            sources_out["backfill_fmtqik_url_tpl"] = backfill_fmt_tpl
        except Exception as e:
            print(f"[FATAL] fallback current-month FMTQIK failed: {e}")
            sys.exit(1)

    # If still empty => fatal
    if not fmt_rows_daily:
        print("[FATAL] daily FMTQIK returned no usable rows/dates after parsing.")
        if daily_fmt_raw is not None:
            _diag_payload("daily_openapi_fmtqik", daily_fmt_raw)
        sys.exit(1)

    # ---- parse daily ohlc (still optional) ----
    ohlc_rows_daily: List[OhlcRow] = []
    try:
        ohlc_rows_daily = _parse_openapi_ohlc(daily_ohlc_raw, schema) if daily_ohlc_raw is not None else []
    except Exception:
        ohlc_rows_daily = []

    fmt_by_date: Dict[str, FmtRow] = {x.date: x for x in fmt_rows_daily}
    ohlc_by_date: Dict[str, OhlcRow] = {x.date: x for x in ohlc_rows_daily}

    # ---- optional monthly backfill ----
    if args.backfill_months > 0:
        if not backfill_fmt_tpl or not backfill_ohlc_tpl:
            print("[FATAL] backfill_months>0 but schema missing backfill url templates.")
            sys.exit(1)
        sources_out["backfill_fmtqik_url_tpl"] = backfill_fmt_tpl
        sources_out["backfill_mi_5mins_hist_url_tpl"] = backfill_ohlc_tpl

        today = _today_tz(tz)
        month_keys = _month_starts_back(today, args.backfill_months)

        for yyyymm01 in month_keys:
            try:
                url = backfill_fmt_tpl.format(yyyymm01=yyyymm01)
                payload = _http_get_json_retry(url, tries=3)
                rows_m = _parse_twse_month_fmtqik(payload)
                for r in rows_m:
                    fmt_by_date[r.date] = r
            except Exception as e:
                print(f"[WARN] backfill FMTQIK {yyyymm01} failed: {e}")

            try:
                url = backfill_ohlc_tpl.format(yyyymm01=yyyymm01)
                payload = _http_get_json_retry(url, tries=3)
                rows_m = _parse_twse_month_ohlc(payload)
                for r in rows_m:
                    ohlc_by_date[r.date] = r
            except Exception as e:
                print(f"[WARN] backfill MI_5MINS_HIST {yyyymm01} failed: {e}")

    # ---- used_date decision ----
    # Use "daily" source dates for used_date semantics
    fmt_dates_daily_asc = sorted([x.date for x in fmt_rows_daily])
    today = _today_tz(tz)

    used_date, run_day_tag, used_date_status = _pick_used_date(today, fmt_dates_daily_asc)

    if daily_source != "openapi":
        # Override status to make provenance explicit
        if used_date_status in ("OK_TODAY", "DATA_NOT_UPDATED", "OK_LATEST"):
            used_date_status = "OPENAPI_UNAVAILABLE_FALLBACK"
        run_day_tag = "TRADING_DAY"

    if used_date == "NA":
        print("[FATAL] UsedDate could not be determined.")
        sys.exit(1)

    # ---- merge newest backfill_limit from combined maps ----
    backfill_limit = int(args.backfill_limit)
    if backfill_limit <= 0:
        backfill_limit = DEFAULT_BACKFILL_LIMIT

    all_dates_desc = sorted(fmt_by_date.keys(), reverse=True)
    new_items = _items_from_maps(fmt_by_date, ohlc_by_date, all_dates_desc, limit=backfill_limit)

    merged_roll, dedupe_ok = _merge_roll(existing_roll, new_items, store_cap=STORE_CAP)

    # ---- lookback + freshness ----
    lookback = _extract_lookback(merged_roll, used_date, LOOKBACK_TARGET)
    n_actual = len(lookback)
    oldest = lookback[-1]["date"] if lookback else "NA"

    freshness_ok = True
    freshness_age_days: Optional[int] = None
    try:
        used_dt = datetime.fromisoformat(str(used_date)).date()
        freshness_age_days = (today - used_dt).days
        if freshness_age_days > 7:
            freshness_ok = False
    except Exception:
        freshness_ok = False

    # ---- mode / ohlc ----
    m_used = _index_by_date(merged_roll, used_date)
    row_used = m_used.get(used_date, {})

    used_close = _safe_float(row_used.get("close"))
    used_high = _safe_float(row_used.get("high"))
    used_low = _safe_float(row_used.get("low"))

    ohlc_ok = (used_high is not None and used_low is not None)
    mode = "FULL" if ohlc_ok else "MISSING_OHLC"
    ohlc_status = "OK" if ohlc_ok else "MISSING"

    dminus1 = _find_dminus1(merged_roll, used_date)
    used_dminus1 = dminus1["date"] if dminus1 else "NA"
    prev_close = _safe_float(dminus1.get("close")) if dminus1 else None

    pct_change = None
    if used_close is not None and prev_close is not None and prev_close != 0:
        pct_change = (used_close - prev_close) / prev_close * 100.0

    amplitude_pct = None
    if ohlc_ok and prev_close is not None and prev_close != 0 and used_high is not None and used_low is not None:
        amplitude_pct = _calc_amplitude_pct(used_high, used_low, prev_close)

    used_trade_value = _safe_float(row_used.get("trade_value"))
    used_change = _safe_float(row_used.get("change"))

    is_down_day = (pct_change is not None and pct_change < 0) or (used_change is not None and used_change < 0)

    prefix = ""
    if run_day_tag == "NON_TRADING_DAY":
        prefix = "今日非交易日；"
    elif used_date_status == "DATA_NOT_UPDATED":
        prefix = "今日資料未更新；"
    elif used_date_status == "OPENAPI_UNAVAILABLE_FALLBACK":
        prefix = "OpenAPI 不可用，改用 TWSE 網站當月回補；"

    summary = f"{prefix}UsedDate={used_date}：Mode={mode}；freshness_ok={freshness_ok}"

    latest_report = {
        "generated_at": _now_tz(tz).isoformat(),
        "timezone": str(tz),
        "summary": summary,
        "numbers": {
            "UsedDate": used_date,
            "Close": None if used_close is None else round(float(used_close), 2),
            "PctChange": None if pct_change is None else round(float(pct_change), 6),
            "TradeValue": None if used_trade_value is None else int(round(float(used_trade_value))),
            "AmplitudePct": None if amplitude_pct is None else round(float(amplitude_pct), 6),
        },
        "signal": {
            "DownDay": None if (pct_change is None and used_change is None) else bool(is_down_day),
            "OhlcMissing": (not ohlc_ok),
            "UsedDateStatus": used_date_status,
            "RunDayTag": run_day_tag,
            "DailySource": daily_source,
        },
        "action": "維持風險控管紀律；如資料延遲或 OHLC 缺失，避免做過度解讀，待資料補齊再對照完整條件。",
        "caveats": "\n".join([
            f"DailySource={daily_source}",
            f"Sources: daily_fmtqik={schema['fmtqik']['url']} ; daily_mi_5mins_hist={schema['mi_5mins_hist']['url']}",
            f"BackfillMonths={args.backfill_months} | BackfillLimit={backfill_limit} | StoreCap={STORE_CAP} | LookbackTarget={LOOKBACK_TARGET}",
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

    # ---- stats ----
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
        "backfill_limit": backfill_limit,
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
                    "note": "pct_change needs D-1 close; backfill_limit N implies at most N-1 pct_change points."
                }
            },
            "amplitude_pct": {
                "asof": used_date,
                "win60": _calc_stats_for_series(series_amp, used_date, 60),
                "win252": _calc_stats_for_series(series_amp, used_date, 252),
                "window_note": {
                    "n_total_available": len(series_amp),
                    "note": "amplitude_pct needs high/low + D-1 close; if OHLC missing, series is sparse."
                }
            },
        },
        "sources": sources_out,
    }

    _atomic_write_json(ROLL_PATH, merged_roll)
    _atomic_write_json(REPORT_PATH, latest_report)
    _atomic_write_json(STATS_PATH, stats)

    print("TWSE sidecar updated:")
    print(f"  DailySource={daily_source}")
    print(f"  UsedDate={used_date}  Mode={mode}  freshness_ok={freshness_ok} age_days={freshness_age_days}")
    print(f"  run_day_tag={run_day_tag}  used_date_status={used_date_status}")
    print(f"  roll_records={len(merged_roll)}  dedupe_ok={dedupe_ok}")
    print(f"  wrote: {ROLL_PATH}, {REPORT_PATH}, {STATS_PATH}")


if __name__ == "__main__":
    main()