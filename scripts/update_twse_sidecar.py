#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWSE sidecar updater (roll25_cache/) - backfill limit=252 + stats_latest.json

Fetches (1 request each):
  1) FMTQIK (MUST succeed): trade value / close / change
  2) MI_5MINS_HIST (may degrade): OHLC (high/low)

Writes (atomic):
  - roll25_cache/roll25.json
  - roll25_cache/latest_report.json
  - roll25_cache/stats_latest.json

Backfill policy:
  - Build cache items from latest FMTQIK dates (DESC), up to BACKFILL_LIMIT=252.
  - Merge into existing roll cache (dedupe by date), then keep STORE_CAP >= 252.

Stats policy (audit-first, no guessing):
  - Series: close, trade_value, pct_change, amplitude_pct
  - Windows: 60 & 252
  - If insufficient values for a window, z/p are NA (None) and window_n_actual is reported.
  - Percentile uses tie-aware rank: p = 100 * (less + 0.5*equal) / n

Freshness policy:
  - freshness_age_days = (today - used_date).days
  - If > 7 => freshness_ok=False

Run-day tag policy (IMPORTANT):
  - run_day_tag is a WEEKDAY-ONLY HEURISTIC (NOT an exchange calendar).
    - Weekend => NON_TRADING_DAY
    - Weekday => TRADING_DAY
  - Holidays/typhoon suspensions are NOT covered by this heuristic.
  - We persist run_day_tag_method="WEEKDAY_ONLY_HEURISTIC".

UsedDateStatus semantics (IMPORTANT):
  - DATA_NOT_UPDATED means: as of generated_at_local, the DAILY endpoint did NOT publish
    a row whose date equals "today" (local). This is a data publication state, not
    a statement about whether the exchange is open/closed.
"""

from __future__ import annotations

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
STORE_CAP = 400  # must be >= BACKFILL_LIMIT

UA = "twse-sidecar/1.8 (+github-actions)"

RUN_DAY_TAG_METHOD = "WEEKDAY_ONLY_HEURISTIC"


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

def _http_get_json(url: str, timeout: int = 25) -> Any:
    headers = {"Accept": "application/json", "User-Agent": UA}
    r = requests.get(url, headers=headers, timeout=timeout)
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

def _diag_payload(name: str, payload: Any) -> None:
    print(f"[DIAG] {name}: type={type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"[DIAG] {name}: top_keys={list(payload.keys())[:40]}")
    rows = _unwrap_to_rows(payload)
    print(f"[DIAG] {name}: unwrapped_rows={len(rows)}")
    if rows:
        print(f"[DIAG] {name}: row0_keys={list(rows[0].keys())[:40]}")

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

def _get_url(cfg: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for k in keys:
        v = cfg.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def _require_url(schema: Dict[str, Any], section: str, keys: List[str]) -> str:
    cfg = schema.get(section, {})
    if not isinstance(cfg, dict):
        raise KeyError(f"schema['{section}'] missing or not an object")
    url = _get_url(cfg, keys)
    if not url:
        raise KeyError(f"schema['{section}'] missing url keys {keys}")
    return url


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

def _pick_used_date(today: date, fmt_dates_sorted_asc: List[str]) -> Tuple[str, str, str, str]:
    if not fmt_dates_sorted_asc:
        return ("NA", "FMTQIK_EMPTY", "FMTQIK_EMPTY", RUN_DAY_TAG_METHOD)

    today_iso = today.isoformat()
    latest = _latest_date(fmt_dates_sorted_asc) or fmt_dates_sorted_asc[-1]

    if _is_weekend(today):
        return (latest, "NON_TRADING_DAY", "OK_LATEST", RUN_DAY_TAG_METHOD)

    if today_iso not in fmt_dates_sorted_asc:
        return (latest, "TRADING_DAY", "DATA_NOT_UPDATED", RUN_DAY_TAG_METHOD)

    return (today_iso, "TRADING_DAY", "OK_TODAY", RUN_DAY_TAG_METHOD)

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
        return {
            "value": x,
            "window_n_target": win,
            "window_n_actual": n_actual,
            "z": None,
            "p": None,
        }

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

    # Resolve daily URLs (compat: url OR daily_url)
    try:
        fmt_daily_url = _require_url(schema, "fmtqik", ["daily_url", "url"])
    except Exception as e:
        print(f"[FATAL] FMTQIK url missing in schema: {e}")
        sys.exit(1)

    try:
        mi_daily_url = _require_url(schema, "mi_5mins_hist", ["daily_url", "url"])
    except Exception as e:
        print(f"[FATAL] MI_5MINS_HIST url missing in schema: {e}")
        sys.exit(1)

    # Optional backfill templates (for audit display only; scheme-1 does not change fetch behavior)
    fmt_backfill_tpl = None
    mi_backfill_tpl = None
    fmt_cfg = schema.get("fmtqik", {}) if isinstance(schema.get("fmtqik", {}), dict) else {}
    mi_cfg = schema.get("mi_5mins_hist", {}) if isinstance(schema.get("mi_5mins_hist", {}), dict) else {}
    fmt_backfill_tpl = _get_url(fmt_cfg, ["backfill_url_tpl", "url_tpl", "tpl"])
    mi_backfill_tpl = _get_url(mi_cfg, ["backfill_url_tpl", "url_tpl", "tpl"])

    # Fetch FMTQIK (fatal if fails)
    try:
        fmt_raw = _http_get_json(fmt_daily_url)
    except Exception as e:
        print(f"[FATAL] FMTQIK fetch failed: {e}")
        sys.exit(1)

    # Fetch OHLC (non-fatal; allow downgrade)
    try:
        ohlc_raw = _http_get_json(mi_daily_url)
    except Exception as e:
        print(f"[WARN] MI_5MINS_HIST fetch failed (downgrade): {e}")
        ohlc_raw = []

    fmt_rows = _parse_fmtqik(fmt_raw, schema)
    ohlc_rows = _parse_ohlc(ohlc_raw, schema)

    if not fmt_rows:
        print("[FATAL] daily FMTQIK returned no usable rows/dates after parsing.")
        _diag_payload("FMTQIK", fmt_raw)
        sys.exit(1)

    fmt_by_date = {x.date: x for x in fmt_rows}
    ohlc_by_date = {x.date: x for x in ohlc_rows}

    fmt_dates_asc = sorted(fmt_by_date.keys())
    today = _today_tz(tz)

    used_date, run_day_tag, used_date_status, run_day_tag_method = _pick_used_date(today, fmt_dates_asc)
    if used_date == "NA":
        print("[FATAL] UsedDate could not be determined.")
        _diag_payload("FMTQIK", fmt_raw)
        sys.exit(1)

    fmt_dates_desc = sorted(fmt_by_date.keys(), reverse=True)
    new_items = _build_items_backfill(fmt_by_date, ohlc_by_date, fmt_dates_desc, limit=BACKFILL_LIMIT)

    merged_roll, dedupe_ok = _merge_roll(existing_roll, new_items)

    lookback = _extract_lookback(merged_roll, used_date)
    n_actual = len(lookback)
    oldest = lookback[-1]["date"] if lookback else "NA"