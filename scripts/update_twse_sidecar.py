#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWSE sidecar updater (roll25_cache/) - backfill limit=252 + stats_latest.json

Daily mode (default, 2 requests):
  1) openapi.twse.com.tw/v1/exchangeReport/FMTQIK
  2) openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST

Backfill mode (--backfill-months N, many requests):
  Uses www.twse.com.tw query-style APIs (monthly) to fetch enough history:
    - https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date=YYYYMM01
    - https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date=YYYYMM01

Writes (atomic):
  - roll25_cache/roll25.json
  - roll25_cache/latest_report.json
  - roll25_cache/stats_latest.json

Notes:
- This script is audit-first: no guessing.
- If OHLC missing, mode downgrades to MISSING_OHLC.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
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
BACKFILL_LIMIT = 252
STORE_CAP = 400  # must be >= BACKFILL_LIMIT to preserve 252-trading-day context

UA = "twse-sidecar/1.7 (+github-actions)"

# Query-style (monthly) endpoints for backfill
TWSE_FMTQIK_MONTHLY = "https://www.twse.com.tw/exchangeReport/FMTQIK"
TWSE_MI_5MINS_HIST_MONTHLY = "https://www.twse.com.tw/indicesReport/MI_5MINS_HIST"


# ----------------- helpers -----------------

def _load_schema() -> Dict[str, Any]:
    if not os.path.exists(SCHEMA_PATH):
        raise RuntimeError(f"Missing schema file: {SCHEMA_PATH}")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _tz(schema: Dict[str, Any]) -> ZoneInfo:
    tz = schema.get("timezone", "Asia/Taipei")
    return ZoneInfo(tz)

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
    if s == "" or s.upper() == "NA" or s.lower() == "null" or s in ("-", "—"):
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

def _http_get_json(url: str, params: Optional[Dict[str, str]] = None, timeout: int = 25) -> Any:
    headers = {"Accept": "application/json", "User-Agent": UA}
    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

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

def _unwrap_to_rows(payload: Any) -> List[Dict[str, Any]]:
    """
    Supports:
    - list[dict] (openapi v1 style)
    - dict with data/result/records/items (list[dict])
    - TWSE query style: dict with fields[list[str]] + data[list[list]]
    """
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if isinstance(payload, dict):
        # TWSE query-style: fields + data (2D)
        fields = payload.get("fields")
        data = payload.get("data")
        if isinstance(fields, list) and isinstance(data, list) and fields and data:
            out: List[Dict[str, Any]] = []
            for row in data:
                if isinstance(row, list) and len(row) == len(fields):
                    out.append({str(fields[i]): row[i] for i in range(len(fields))})
            return out

        for k in ("data", "result", "records", "items", "aaData", "dataset"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]

        # single dict row
        if all(not isinstance(v, list) for v in payload.values()):
            return [payload]

    return []

def _pick_first_key(row: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in row:
            return row.get(k)
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

def _yyyymm01(d: date) -> str:
    return f"{d.year:04d}{d.month:02d}01"

def _month_starts_backwards(today: date, months: int) -> List[str]:
    """
    Return list of YYYYMM01 strings (DESC by time) covering [today .. today-months].
    """
    if months <= 0:
        return []
    y = today.year
    m = today.month
    out: List[str] = []
    for _ in range(months):
        out.append(f"{y:04d}{m:02d}01")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out  # DESC


# ----------------- parsing -----------------

@dataclass
class FmtRow:
    date: str
    trade_value: Optional[int]
    close: Optional[float]
    change: Optional[float]

def _parse_fmtqik(payload: Any, schema: Dict[str, Any]) -> List[FmtRow]:
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

def _parse_ohlc(payload: Any, schema: Dict[str, Any]) -> List[OhlcRow]:
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
    if not fmt_dates_sorted_asc:
        return ("NA", "FMTQIK_EMPTY", "FMTQIK_EMPTY")

    today_iso = today.isoformat()
    latest = _latest_date(fmt_dates_sorted_asc) or fmt_dates_sorted_asc[-1]

    if _is_weekend(today):
        return (latest, "NON_TRADING_DAY", "OK_LATEST")

    if today_iso not in fmt_dates_sorted_asc:
        return (latest, "TRADING_DAY", "DATA_NOT_UPDATED")

    return (today_iso, "TRADING_DAY", "OK_TODAY")

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

def _build_items_backfill(
    fmt_by_date: Dict[str, FmtRow],
    ohlc_by_date: Dict[str, OhlcRow],
    fmt_dates_desc: List[str],
    limit: int
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in fmt_dates_desc[:limit]:
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
    return out  # DESC

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


# ----------------- data fetch modes -----------------

def _fetch_daily_openapi(schema: Dict[str, Any]) -> Tuple[Any, Any]:
    fmt_raw = _http_get_json(schema["fmtqik"]["url"])
    try:
        ohlc_raw = _http_get_json(schema["mi_5mins_hist"]["url"])
    except Exception as e:
        print(f"[WARN] MI_5MINS_HIST fetch failed (downgrade): {e}")
        ohlc_raw = []
    return fmt_raw, ohlc_raw

def _fetch_backfill_monthly(schema: Dict[str, Any], today: date, months: int) -> Tuple[Any, Any]:
    """
    Returns synthetic payloads by concatenating rows across months.
    We keep them as list[dict] so existing parsers work.
    """
    fmt_rows_all: List[Dict[str, Any]] = []
    ohlc_rows_all: List[Dict[str, Any]] = []

    month_keys = _month_starts_backwards(today, months)
    for i, mm01 in enumerate(month_keys, start=1):
        print(f"[BACKFILL] {i}/{len(month_keys)} month={mm01}")

        # FMTQIK monthly
        try:
            fmt_raw = _http_get_json(TWSE_FMTQIK_MONTHLY, params={"response": "json", "date": mm01}, timeout=30)
            fmt_rows_all.extend(_unwrap_to_rows(fmt_raw))
        except Exception as e:
            print(f"[WARN] backfill FMTQIK month={mm01} failed: {e}")

        # MI_5MINS_HIST monthly
        try:
            ohlc_raw = _http_get_json(TWSE_MI_5MINS_HIST_MONTHLY, params={"response": "json", "date": mm01}, timeout=30)
            ohlc_rows_all.extend(_unwrap_to_rows(ohlc_raw))
        except Exception as e:
            print(f"[WARN] backfill MI_5MINS_HIST month={mm01} failed: {e}")

    return fmt_rows_all, ohlc_rows_all


# ----------------- main -----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-months", type=int, default=0, help="Backfill months using www.twse.com.tw monthly APIs (suggested: 18~24)")
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

    # Fetch
    if args.backfill_months and args.backfill_months > 0:
        fmt_raw, ohlc_raw = _fetch_backfill_monthly(schema, today, args.backfill_months)
    else:
        try:
            fmt_raw, ohlc_raw = _fetch_daily_openapi(schema)
        except Exception as e:
            print(f"[FATAL] daily fetch failed: {e}")
            sys.exit(1)

    fmt_rows = _parse_fmtqik(fmt_raw, schema)
    ohlc_rows = _parse_ohlc(ohlc_raw, schema)

    if not fmt_rows:
        print("[FATAL] FMTQIK returned no usable rows/dates after parsing.")
        sys.exit(1)

    fmt_by_date = {x.date: x for x in fmt_rows}
    ohlc_by_date = {x.date: x for x in ohlc_rows}

    fmt_dates_asc = sorted(fmt_by_date.keys())
    used_date, run_day_tag, used_date_status = _pick_used_date(today, fmt_dates_asc)
    if used_date == "NA":
        print("[FATAL] UsedDate could not be determined.")
        sys.exit(1)

    fmt_dates_desc = sorted(fmt_by_date.keys(), reverse=True)
    new_items = _build_items_backfill(fmt_by_date, ohlc_by_date, fmt_dates_desc, limit=BACKFILL_LIMIT)

    merged_roll, dedupe_ok = _merge_roll(existing_roll, new_items)

    lookback = _extract_lookback(merged_roll, used_date)
    n_actual = len(lookback)
    oldest = lookback[-1]["date"] if lookback else "NA"

    # Freshness by used_date age
    freshness_ok = True
    freshness_age_days = None
    try:
        used_dt = datetime.fromisoformat(str(used_date)).date()
        freshness_age_days = (today - used_dt).days
        if freshness_age_days > 7:
            freshness_ok = False
    except Exception:
        freshness_ok = False

    # mode / ohlc status for used_date
    m_used = _index_by_date(merged_roll, used_date)
    row_used = m_used.get(used_date, {})
    ohlc_ok = bool(
        row_used
        and _safe_float(row_used.get("high")) is not None
        and _safe_float(row_used.get("low")) is not None
    )
    mode = "FULL" if ohlc_ok else "MISSING_OHLC"
    ohlc_status = "OK" if ohlc_ok else "MISSING"

    # D-1 info
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

    prefix = ""
    if run_day_tag == "NON_TRADING_DAY":
        prefix = "今日非交易日；"
    elif used_date_status == "DATA_NOT_UPDATED":
        prefix = "今日資料未更新；"

    summary = f"{prefix}UsedDate={used_date}：Mode={mode}；freshness_ok={freshness_ok}"

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
            f"Daily sources: FMTQIK={schema['fmtqik']['url']} ; MI_5MINS_HIST={schema['mi_5mins_hist']['url']}",
            f"Backfill sources: FMTQIK={TWSE_FMTQIK_MONTHLY} ; MI_5MINS_HIST={TWSE_MI_5MINS_HIST_MONTHLY}",
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
                    "note": "pct_change needs D-1 close; with backfill=252, max pct_change points are typically <=251."
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
            "daily_fmtqik_url": schema["fmtqik"]["url"],
            "daily_mi_5mins_hist_url": schema["mi_5mins_hist"]["url"],
            "backfill_fmtqik_url": TWSE_FMTQIK_MONTHLY,
            "backfill_mi_5mins_hist_url": TWSE_MI_5MINS_HIST_MONTHLY,
        }
    }

    _atomic_write_json(ROLL_PATH, merged_roll)
    _atomic_write_json(REPORT_PATH, latest_report)
    _atomic_write_json(STATS_PATH, stats)

    print("TWSE sidecar updated:")
    print(f"  UsedDate={used_date}  Mode={mode}  freshness_ok={freshness_ok} age_days={freshness_age_days}")
    print(f"  run_day_tag={run_day_tag}  used_date_status={used_date_status}")
    print(f"  roll_records={len(merged_roll)}  dedupe_ok={dedupe_ok}")
    print(f"  wrote: {ROLL_PATH}, {REPORT_PATH}, {STATS_PATH}")


if __name__ == "__main__":
    main()