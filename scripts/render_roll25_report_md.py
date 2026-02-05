#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

Audit-grade alignment rules:
- All displayed VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to UsedDate (as-of trading date).
- ret1% is STRICT adjacency: prev = next older row after UsedDate (no jumping).
- zΔ60/pΔ60 are computed on DELTA series (today - prev) over last 60 deltas (anchored).
- Date ordering uses parsed date (not string sort).
- SERIES DIRECTION CONTRACT: all *_nf series are NEWEST-FIRST (index 0 = latest date).

Stats:
- z-score uses population std (ddof=0)
- percentile is tie-aware: (less + 0.5*equal) / n * 100

DQ checks:
- AMPLITUDE mismatch: abs(latest - derived@UsedDate) > threshold => AMPLITUDE row DOWNGRADED + note
- CLOSE pct mismatch: abs(ret1_close - latest_pct_change) > threshold => CLOSE row DOWNGRADED + note
- Missing latest fields are explicitly noted (mismatch checks skipped rather than silently omitted).

IMPORTANT (2026-01-xx fix):
- AMPLITUDE_PCT derived from roll25.json now prefers prev_close denominator if possible:
  prev_close = close - change
  amplitude = (high - low) / abs(prev_close) * 100
  fallback only if prev_close unavailable: (high - low) / abs(close) * 100

MM/DD (no year) handling (cross-year safe):
- When a row date is MM/DD, we choose year among {default_year-1, default_year, default_year+1}
  that is closest to a reference date (prefer UsedDate). This avoids cross-year mis-anchor.

VOLATILITY BANDS (Approximation; audit-safe):
- sigma_win_list computed from last N DAILY % returns anchored at UsedDate (population std; ddof=0).
- horizon scaling uses sqrt(T) (T in trading days).
- 1-tail 95% uses z=1.645
- 2-tail 95% uses z=1.96
- stress sigma:
    primary: sigma_stress = max(sigma60, sigma20) * stress_mult
    fallback: if both unavailable, use max(available sigma in effective windows) * stress_mult
              (explicitly noted with chosen window)

REPORTING (noise-control):
- Summary always shows:
    * report_date_local (today, in tz if available)
    * as_of_data_date (UsedDate; latest available)
    * data_age_days = report_date_local - as_of_data_date (calendar days)
  Only if data_age_days > stale_warn_days (default=2), show a warning (might be weekend/holiday).
- UsedDateStatus is kept for audit, but moved to Audit Notes to avoid daily noise.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None  # type: ignore


# ---------------- IO helpers ----------------

def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_tzinfo(tz_name: Optional[str]):
    if not tz_name or not isinstance(tz_name, str):
        return None
    if tz_name == "NA":
        return None
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return None


def _now_local_iso(tz_name: Optional[str]) -> str:
    tzinfo = _get_tzinfo(tz_name)
    if tzinfo is None:
        return datetime.now().astimezone().isoformat()
    return datetime.now(timezone.utc).astimezone(tzinfo).isoformat()


def _today_local_date(tz_name: Optional[str]) -> date:
    tzinfo = _get_tzinfo(tz_name)
    if tzinfo is None:
        return datetime.now().astimezone().date()
    return datetime.now(timezone.utc).astimezone(tzinfo).date()


def _fmt(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if not math.isfinite(x):
            return "NA"
        if abs(x) >= 1e12:
            return f"{x:.0f}"
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return None if cur is None else cur


# ---------------- Date parsing ----------------

_MMDD_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s*$")
_YYYYMMDD_RE = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})\s*$")


def _choose_year_for_mmdd(
    mo: int,
    d: int,
    *,
    default_year: int,
    ref_date: Optional[date],
) -> Optional[date]:
    """
    Cross-year safe: pick year among {default_year-1, default_year, default_year+1}
    that is closest to ref_date. If ref_date is None, use default_year.
    """
    cand_years = [default_year]
    if ref_date is not None:
        cand_years = [default_year - 1, default_year, default_year + 1]

    best: Optional[date] = None
    best_abs_days: Optional[int] = None

    for y in cand_years:
        try:
            dd = date(y, mo, d)
        except Exception:
            continue

        if ref_date is None:
            return dd

        abs_days = abs((dd - ref_date).days)
        if best is None or best_abs_days is None or abs_days < best_abs_days:
            best = dd
            best_abs_days = abs_days

    return best


def _parse_date(
    s: Any,
    *,
    default_year: Optional[int] = None,
    ref_date: Optional[date] = None,
) -> Optional[date]:
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None

    # normalize separators
    t2 = t.replace(".", "-").replace("/", "-")

    # YYYY-MM-DD (and common variants)
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(t2, fmt).date()
        except Exception:
            pass

    # YYYYMMDD
    m = _YYYYMMDD_RE.match(t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except Exception:
            return None

    # MM/DD (needs year)
    m = _MMDD_RE.match(t)
    if m and default_year is not None:
        mo, d = int(m.group(1)), int(m.group(2))
        return _choose_year_for_mmdd(mo, d, default_year=default_year, ref_date=ref_date)

    return None


# ---------------- Stats helpers ----------------

def _z_score_pop(x: float, arr: List[float]) -> Optional[float]:
    if len(arr) < 2:
        return None
    mean = sum(arr) / len(arr)
    var = sum((v - mean) ** 2 for v in arr) / len(arr)
    sd = math.sqrt(max(var, 0.0))
    if sd == 0:
        return 0.0
    return (x - mean) / sd


def _percentile_tie_aware(x: float, arr: List[float]) -> Optional[float]:
    n = len(arr)
    if n == 0:
        return None
    less = sum(1 for v in arr if v < x)
    eq = sum(1 for v in arr if v == x)
    return (less + 0.5 * eq) / n * 100.0


def _take_newest_finite(series_nf: List[float], n: int) -> Optional[List[float]]:
    out: List[float] = []
    for v in series_nf:
        if isinstance(v, (int, float)) and math.isfinite(float(v)):
            out.append(float(v))
            if len(out) >= n:
                break
    if len(out) < n:
        return None
    return out


def _delta_series_nf(series_nf: List[float]) -> List[float]:
    # NEWEST-FIRST contract: delta[today] = series_nf[0] - series_nf[1]
    out: List[float] = []
    for i in range(len(series_nf) - 1):
        a = series_nf[i]
        b = series_nf[i + 1]
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            continue
        a = float(a)
        b = float(b)
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        out.append(a - b)
    return out


def _ret1_pct_strict(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    if b == 0:
        return None
    return (a - b) / abs(b) * 100.0


def _std_pop(arr: List[float]) -> Optional[float]:
    if len(arr) < 2:
        return None
    mean = sum(arr) / len(arr)
    var = sum((v - mean) ** 2 for v in arr) / len(arr)
    return math.sqrt(max(var, 0.0))


@dataclass
class RowStats:
    value: Optional[float]
    z60: Optional[float]
    p60: Optional[float]
    z252: Optional[float]
    p252: Optional[float]
    zD60: Optional[float]   # print zΔ60
    pD60: Optional[float]   # print pΔ60
    ret1: Optional[float]   # print ret1%
    confidence: str         # OK / DOWNGRADED


# ---------------- roll25.json parsing ----------------

def _extract_rows_roll25_json(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("items", "rows", "data", "roll25", "cache_roll25", "cache_roll25_points", "points"):
            v = obj.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _get_float(r: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        v = r.get(k)
        if isinstance(v, (int, float)):
            f = float(v)
            if math.isfinite(f):
                return f
    return None


def _get_row_raw_date(r: Dict[str, Any]) -> Optional[str]:
    raw = r.get("date")
    if isinstance(raw, str):
        return raw
    raw = r.get("Date")
    if isinstance(raw, str):
        return raw
    return None


def _sort_rows_by_date_desc_keyed(
    rows: List[Dict[str, Any]],
    used_date: Optional[date],
    *,
    ref_date: Optional[date],
) -> Tuple[List[Tuple[date, Dict[str, Any]]], Dict[str, Any]]:
    """
    Returns keyed list (date, row) sorted by date desc (NEWEST-FIRST),
    plus diag for audit/debug.
    """
    default_year = used_date.year if used_date else (ref_date.year if ref_date else datetime.now().year)
    ref = used_date or ref_date

    keyed: List[Tuple[date, Dict[str, Any]]] = []
    bad_samples: List[str] = []

    for r in rows:
        raw = _get_row_raw_date(r)
        d = _parse_date(raw, default_year=default_year, ref_date=ref) if raw is not None else None
        if d is None:
            if raw is not None and len(bad_samples) < 3:
                bad_samples.append(str(raw))
            continue
        keyed.append((d, r))

    keyed.sort(key=lambda x: x[0], reverse=True)

    diag = {
        "total_rows": len(rows),
        "kept_rows": len(keyed),
        "dropped_rows": len(rows) - len(keyed),
        "bad_date_samples": bad_samples,
        "default_year": default_year,
        "ref_date": ref.isoformat() if isinstance(ref, date) else "NA",
    }
    return keyed, diag


def _series_turnover(rows_nf: List[Dict[str, Any]]) -> List[float]:
    # NEWEST-FIRST
    out: List[float] = []
    for r in rows_nf:
        out.append(_get_float(r, "turnover_twd", "trade_value", "TradeValue", "turnover", "Turnover") or float("nan"))
    return out


def _series_close(rows_nf: List[Dict[str, Any]]) -> List[float]:
    # NEWEST-FIRST
    out: List[float] = []
    for r in rows_nf:
        out.append(_get_float(r, "close", "Close") or float("nan"))
    return out


def _derive_amplitude_pct_prevclose_first(r: Dict[str, Any]) -> Tuple[Optional[float], str]:
    amp_field = _get_float(r, "amplitude_pct", "AmplitudePct")
    h = _get_float(r, "high", "High")
    l = _get_float(r, "low", "Low")
    c = _get_float(r, "close", "Close")
    chg = _get_float(r, "change", "Change")

    if h is not None and l is not None:
        prev = None
        if c is not None and chg is not None:
            prev = c - chg

        if prev is not None and prev != 0 and math.isfinite(prev):
            return ((h - l) / abs(prev) * 100.0), "prev_close"

        if c is not None and c != 0 and math.isfinite(c):
            return ((h - l) / abs(c) * 100.0), "close"

    if amp_field is not None:
        return amp_field, "amp_field"

    return None, "na"


def _series_amplitude_pct(rows_nf: List[Dict[str, Any]]) -> List[float]:
    # NEWEST-FIRST
    out: List[float] = []
    for r in rows_nf:
        amp, _tag = _derive_amplitude_pct_prevclose_first(r)
        if amp is not None and math.isfinite(float(amp)):
            out.append(float(amp))
        else:
            out.append(float("nan"))
    return out


def _series_pct_change_close_from_close(close_nf: List[float]) -> List[float]:
    """
    NEWEST-FIRST close series -> NEWEST-FIRST pct_change series.
    For last element (oldest row) there is no next older; we append NA to keep alignment.
    """
    out: List[float] = []
    for i in range(len(close_nf) - 1):
        a = close_nf[i]
        b = close_nf[i + 1]
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            out.append(float("nan"))
            continue
        a = float(a)
        b = float(b)
        if not (math.isfinite(a) and math.isfinite(b)) or b == 0:
            out.append(float("nan"))
            continue
        out.append((a - b) / abs(b) * 100.0)
    out.append(float("nan"))
    return out


def _series_vol_multiplier_20(turnover_nf: List[float], min_points: int = 15, win: int = 20) -> List[float]:
    """
    NEWEST-FIRST contract:
    vol_mult[i] = turnover[i] / avg(turnover[i+1 : i+win+1])  (i.e., vs older window)
    This is NOT "future window" under the NEWEST-FIRST contract.
    """
    out: List[float] = []
    for i in range(len(turnover_nf)):
        a = turnover_nf[i]
        if not (isinstance(a, (int, float)) and math.isfinite(float(a))):
            out.append(float("nan"))
            continue

        start = i + 1
        end = i + win + 1
        if start >= len(turnover_nf):
            out.append(float("nan"))
            continue

        window = turnover_nf[start:end]
        w: List[float] = []
        for v in window:
            if isinstance(v, (int, float)):
                fv = float(v)
                if math.isfinite(fv):
                    w.append(fv)
        if len(w) < min_points:
            out.append(float("nan"))
            continue
        avg = sum(w) / len(w)
        if avg == 0:
            out.append(float("nan"))
            continue
        out.append(float(a) / avg)
    return out


def _truncate_to_common_length(*series: List[float]) -> List[List[float]]:
    m = min(len(s) for s in series) if series else 0
    return [s[:m] for s in series]


# ---------------- Anchored stats computation ----------------

def _anchored_stats(
    series_nf: List[float],
    anchor_idx: int,
    *,
    want_delta_and_ret1: bool,
    require_full_252: bool = True,
) -> RowStats:
    conf = "OK"

    if anchor_idx < 0 or anchor_idx >= len(series_nf):
        return RowStats(None, None, None, None, None, None, None, None, "DOWNGRADED")

    v = series_nf[anchor_idx]
    v = float(v) if isinstance(v, (int, float)) and math.isfinite(float(v)) else None
    if v is None:
        conf = "DOWNGRADED"

    tail = series_nf[anchor_idx:]  # NEWEST-FIRST tail anchored at UsedDate index

    w60 = _take_newest_finite(tail, 60)
    w252 = _take_newest_finite(tail, 252)

    z60 = _z_score_pop(v, w60) if (v is not None and w60 is not None) else None
    p60 = _percentile_tie_aware(v, w60) if (v is not None and w60 is not None) else None
    z252 = _z_score_pop(v, w252) if (v is not None and w252 is not None) else None
    p252 = _percentile_tie_aware(v, w252) if (v is not None and w252 is not None) else None

    if w60 is None:
        conf = "DOWNGRADED"
    if require_full_252 and w252 is None:
        conf = "DOWNGRADED"

    zD60 = None
    pD60 = None
    r1 = None

    if want_delta_and_ret1:
        prev = None
        if anchor_idx + 1 < len(series_nf):
            pv = series_nf[anchor_idx + 1]
            prev = float(pv) if isinstance(pv, (int, float)) and math.isfinite(float(pv)) else None

        r1 = _ret1_pct_strict(v, prev)
        if r1 is None:
            conf = "DOWNGRADED"

        deltas = _delta_series_nf(tail)  # NEWEST-FIRST deltas aligned to tail
        d_today = deltas[0] if deltas else None
        d60 = _take_newest_finite(deltas, 60)

        if d_today is not None and d60 is not None:
            zD60 = _z_score_pop(d_today, d60)
            pD60 = _percentile_tie_aware(d_today, d60)
        else:
            conf = "DOWNGRADED"

    return RowStats(v, z60, p60, z252, p252, zD60, pD60, r1, conf)


# ---------------- Volatility bands (anchored; approximation) ----------------

def _anchored_daily_returns_pct_from_close(close_nf: List[float], anchor_idx: int) -> List[float]:
    """
    Returns NEWEST-FIRST daily % returns series anchored at anchor_idx:
    out[0] corresponds to close[anchor_idx] vs close[anchor_idx+1]
    """
    out: List[float] = []
    if anchor_idx < 0 or anchor_idx >= len(close_nf):
        return out
    tail = close_nf[anchor_idx:]
    for i in range(len(tail) - 1):
        a = tail[i]
        b = tail[i + 1]
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            continue
        a = float(a)
        b = float(b)
        if not (math.isfinite(a) and math.isfinite(b)) or b == 0:
            continue
        out.append((a - b) / abs(b) * 100.0)
    return out


def _compute_sigma_daily_pct(returns_pct: List[float], win: int) -> Tuple[Optional[float], str]:
    w = _take_newest_finite(returns_pct, win)
    if w is None:
        return None, f"INSUFFICIENT_RETURNS:{len(returns_pct)}/{win}"
    sd = _std_pop(w)
    if sd is None or not math.isfinite(sd):
        return None, "SIGMA_NA"
    return float(sd), "OK"


def _bands_table(
    *,
    level: float,
    sigma_daily_pct: Optional[float],
    sigma_win: int,
    t_list: List[int],
    z_1tail_95: float = 1.645,
    z_2tail_95: float = 1.96,
    label: str = "BASE",
    confidence: str = "OK",
    note: str = "",
) -> Tuple[List[List[str]], Dict[str, Any]]:
    rows: List[List[str]] = []
    rows.append([
        "T",
        "sigma_daily_%",
        "sigma_T_%",
        "down_1σ",
        "down_95%(1-tail)",
        "down_95%(2-tail)",
        "down_2σ",
        "up_1σ",
        "up_95%(1-tail)",
        "up_95%(2-tail)",
        "up_2σ",
        "confidence",
        "note",
    ])

    meta: Dict[str, Any] = {
        "label": label,
        "sigma_win": sigma_win,
        "sigma_daily_pct": sigma_daily_pct,
        "confidence": confidence,
        "note": note,
    }

    if sigma_daily_pct is None or not math.isfinite(float(level)) or level <= 0:
        for T in t_list:
            rows.append([
                str(T),
                _fmt(sigma_daily_pct),
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                confidence if confidence else "DOWNGRADED",
                note,
            ])
        return rows, meta

    s_daily = float(sigma_daily_pct)
    for T in t_list:
        if T <= 0:
            rows.append([str(T)] + ["NA"] * (len(rows[0]) - 1))
            continue

        sigma_T_pct = s_daily * math.sqrt(float(T))
        sT = sigma_T_pct / 100.0

        down_1 = level * (1.0 - 1.0 * sT)
        up_1 = level * (1.0 + 1.0 * sT)

        down_95_1 = level * (1.0 - z_1tail_95 * sT)
        up_95_1 = level * (1.0 + z_1tail_95 * sT)

        down_95_2 = level * (1.0 - z_2tail_95 * sT)
        up_95_2 = level * (1.0 + z_2tail_95 * sT)

        down_2 = level * (1.0 - 2.0 * sT)
        up_2 = level * (1.0 + 2.0 * sT)

        rows.append([
            str(T),
            _fmt(s_daily),
            _fmt(sigma_T_pct),
            _fmt(down_1),
            _fmt(down_95_1),
            _fmt(down_95_2),
            _fmt(down_2),
            _fmt(up_1),
            _fmt(up_95_1),
            _fmt(up_95_2),
            _fmt(up_2),
            confidence,
            note,
        ])

    return rows, meta


def _bands_pct_mapping_table(
    *,
    sigma_daily_pct: Optional[float],
    t_list: List[int],
    z_1tail_95: float = 1.645,
    z_2tail_95: float = 1.96,
    confidence: str = "OK",
    note: str = "",
) -> List[List[str]]:
    rows: List[List[str]] = []
    rows.append([
        "T",
        "sigma_daily_%",
        "sigma_T_%",
        "pct_1σ",
        "pct_95%(1-tail)",
        "pct_95%(2-tail)",
        "pct_2σ",
        "confidence",
        "note",
    ])

    if sigma_daily_pct is None or not math.isfinite(float(sigma_daily_pct)):
        for T in t_list:
            rows.append([
                str(T),
                _fmt(sigma_daily_pct),
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                confidence if confidence else "DOWNGRADED",
                note,
            ])
        return rows

    s_daily = float(sigma_daily_pct)

    for T in t_list:
        if T <= 0:
            rows.append([str(T)] + ["NA"] * (len(rows[0]) - 1))
            continue
        sigma_T_pct = s_daily * math.sqrt(float(T))
        pct_1 = sigma_T_pct
        pct_95_1 = z_1tail_95 * sigma_T_pct
        pct_95_2 = z_2tail_95 * sigma_T_pct
        pct_2 = 2.0 * sigma_T_pct
        rows.append([
            str(T),
            _fmt(s_daily),
            _fmt(sigma_T_pct),
            f"±{_fmt(pct_1)}",
            f"±{_fmt(pct_95_1)}",
            f"±{_fmt(pct_95_2)}",
            f"±{_fmt(pct_2)}",
            confidence,
            note,
        ])
    return rows


# ---------------- markdown helpers ----------------

def _md_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    out = []
    out.append("| " + " | ".join(rows[0]) + " |")
    out.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _parse_int_list(s: str, *, default: List[int]) -> List[int]:
    if not isinstance(s, str) or not s.strip():
        return default
    out: List[int] = []
    for p in s.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except Exception:
            pass
    return out if out else default


def _unique_sorted_ints(nums: List[int]) -> List[int]:
    s = set()
    out: List[int] = []
    for n in nums:
        try:
            nn = int(n)
        except Exception:
            continue
        if nn <= 0:
            continue
        if nn not in s:
            s.add(nn)
            out.append(nn)
    out.sort()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--out", required=True)

    ap.add_argument("--amp-mismatch-abs-threshold", type=float,
                    default=float(os.getenv("AMP_MISMATCH_ABS_THRESHOLD", "0.01")))
    ap.add_argument("--close-pct-mismatch-abs-threshold", type=float,
                    default=float(os.getenv("CLOSE_PCT_MISMATCH_ABS_THRESHOLD", "0.05")))

    # Staleness warning threshold (calendar days)
    ap.add_argument("--stale-warn-days", type=int,
                    default=int(os.getenv("STALE_WARN_DAYS", "2")),
                    help="Warn only if (report_date_local - as_of_data_date) > this value (calendar days). Default=2")

    # Vol bands controls
    ap.add_argument("--sigma-win-list", default=os.getenv("SIGMA_WIN_LIST", "20,60"),
                    help="comma list of return windows for sigma_daily (e.g., 20,60)")
    ap.add_argument("--sigma-base-win", type=int, default=int(os.getenv("SIGMA_BASE_WIN", "60")),
                    help="base sigma window (BASE bands); will be added to effective windows if missing")
    ap.add_argument("--t-list", default=os.getenv("VOL_BANDS_T_LIST", "10,12,15"),
                    help="comma list of trading days horizons (e.g., 10,12,15)")
    ap.add_argument("--stress-mult", type=float, default=float(os.getenv("STRESS_MULT", "1.5")),
                    help="stress multiplier for sigma_stress (e.g., 1.5 or 2.0)")

    args = ap.parse_args()

    latest = _load_json(args.latest)
    roll25_hist = _load_json(args.roll25)

    tz = latest.get("timezone") if isinstance(latest, dict) and isinstance(latest.get("timezone"), str) else "NA"

    gen_utc = _now_utc_z()
    gen_local = _now_local_iso(tz)
    report_date_local = _today_local_date(tz)

    summary = _safe_get(latest, "summary")
    numbers = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sig = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date_s = numbers.get("UsedDate") if isinstance(numbers.get("UsedDate"), str) else None
    used_date_dt = _parse_date(used_date_s) if used_date_s else None

    as_of_data_date = used_date_s if used_date_s else "NA"
    used_date_status = sig.get("UsedDateStatus") if isinstance(sig.get("UsedDateStatus"), str) else "NA"
    run_day_tag = sig.get("RunDayTag") if isinstance(sig.get("RunDayTag"), str) else "NA"

    # calendar staleness (report_date_local - as_of_data_date)
    data_age_days: Optional[int] = None
    if used_date_dt is not None:
        data_age_days = (report_date_local - used_date_dt).days

    turnover_latest = numbers.get("TradeValue")
    close_latest = numbers.get("Close")
    pct_change_latest = numbers.get("PctChange")
    amp_latest = numbers.get("AmplitudePct")
    vol_mult_latest = numbers.get("VolumeMultiplier")

    # --------- rows extraction with fallback ----------
    rows_raw = _extract_rows_roll25_json(roll25_hist)

    # fallback: if roll25.json missing/empty, use latest_report.cache_roll25
    if not rows_raw and isinstance(latest, dict):
        alt = latest.get("cache_roll25")
        if isinstance(alt, list):
            rows_raw = [x for x in alt if isinstance(x, dict)]

    # sort rows with MM/DD cross-year safe parsing
    keyed, sort_diag = _sort_rows_by_date_desc_keyed(
        rows_raw,
        used_date_dt,
        ref_date=report_date_local,
    )
    rows = [r for _, r in keyed]                  # NEWEST-FIRST
    row_dates = [d for d, _ in keyed]             # NEWEST-FIRST

    dq_notes: List[str] = []

    # date ordering sanity (should be non-increasing)
    bad_order = False
    for i in range(len(row_dates) - 1):
        if row_dates[i] < row_dates[i + 1]:
            bad_order = True
            break
    if bad_order:
        dq_notes.append("Row date order sanity failed: row_dates are not descending after parse/sort (unexpected).")

    if sort_diag.get("dropped_rows", 0) > 0:
        dq_notes.append(
            f"Date parse dropped rows: dropped={sort_diag.get('dropped_rows')} / total={sort_diag.get('total_rows')} "
            f"(bad_samples={sort_diag.get('bad_date_samples')})"
        )

    # anchor index for UsedDate
    anchor_idx = -1
    if used_date_dt is not None:
        for i, d in enumerate(row_dates):
            if d == used_date_dt:
                anchor_idx = i
                break

    turnover_nf = _series_turnover(rows)
    close_nf = _series_close(rows)
    amp_nf = _series_amplitude_pct(rows)

    pctchg_nf = _series_pct_change_close_from_close(close_nf)
    volmult_nf = _series_vol_multiplier_20(turnover_nf, min_points=15, win=20)

    turnover_nf, close_nf, pctchg_nf, amp_nf, volmult_nf = _truncate_to_common_length(
        turnover_nf, close_nf, pctchg_nf, amp_nf, volmult_nf
    )

    if anchor_idx < 0:
        anchor_idx = 0
        dq_notes.append(
            "UsedDate anchor not found in roll25 points after date-parse; fallback to newest row (index 0). "
            f"(UsedDate_raw={as_of_data_date}, UsedDate_parsed={used_date_dt.isoformat() if used_date_dt else 'NA'}, "
            f"rows_kept={len(rows)})"
        )
        if row_dates:
            dq_notes.append(
                f"Row date span (parsed): newest={row_dates[0].isoformat()} oldest={row_dates[-1].isoformat()}"
            )

    if not rows:
        dq_notes.append(
            "No roll25 rows available (roll25.json empty AND latest_report.cache_roll25 missing/empty). "
            "Tables will be NA/downgraded."
        )

    if used_date_dt is None:
        dq_notes.append("UsedDate parse failed; data_age_days cannot be computed; report still renders with local files.")

    # Explicit missing latest fields notes (avoid silent skip)
    if not isinstance(amp_latest, (int, float)):
        dq_notes.append("latest_report.AmplitudePct missing/non-numeric; AMPLITUDE mismatch check skipped.")
    if not isinstance(pct_change_latest, (int, float)):
        dq_notes.append("latest_report.PctChange missing/non-numeric; CLOSE pct mismatch check skipped.")

    st_turnover = _anchored_stats(turnover_nf, anchor_idx, want_delta_and_ret1=True)
    st_close = _anchored_stats(close_nf, anchor_idx, want_delta_and_ret1=True)

    st_pct = _anchored_stats(pctchg_nf, anchor_idx, want_delta_and_ret1=False)
    st_amp = _anchored_stats(amp_nf, anchor_idx, want_delta_and_ret1=False)
    st_volm = _anchored_stats(volmult_nf, anchor_idx, want_delta_and_ret1=False, require_full_252=False)

    # --- DQ: amplitude mismatch (latest vs derived@UsedDate) ---
    amp_conf_override: Optional[str] = None
    if isinstance(amp_latest, (int, float)) and math.isfinite(float(amp_latest)):
        amp_used = st_amp.value
        if isinstance(amp_used, (int, float)) and math.isfinite(float(amp_used)):
            diff = abs(float(amp_latest) - float(amp_used))
            if diff > float(args.amp_mismatch_abs_threshold):
                amp_conf_override = "DOWNGRADED"
                denom_tag = "na"
                if 0 <= anchor_idx < len(rows):
                    _amp_dbg, denom_tag = _derive_amplitude_pct_prevclose_first(rows[anchor_idx])
                dq_notes.append(
                    f"AMPLITUDE_PCT mismatch: abs(latest_report.AmplitudePct - roll25@UsedDate_derived) = {diff:.6f} > {args.amp_mismatch_abs_threshold} "
                    f"(derived_denom={denom_tag})"
                )

    # --- DQ: close pct mismatch (latest pct_change vs computed ret1%) ---
    close_conf_override: Optional[str] = None
    if isinstance(pct_change_latest, (int, float)) and isinstance(st_close.ret1, (int, float)):
        diff = abs(float(pct_change_latest) - float(st_close.ret1))
        if diff > float(args.close_pct_mismatch_abs_threshold):
            close_conf_override = "DOWNGRADED"
            dq_notes.append(
                f"CLOSE pct mismatch: abs(latest_report.PctChange - computed_close_ret1%) = {diff:.6f} > {args.close_pct_mismatch_abs_threshold} "
                f"(UsedDate={as_of_data_date})"
            )

    # ---------------- Volatility Bands computation ----------------
    sigma_win_list_in = _parse_int_list(args.sigma_win_list, default=[20, 60])
    sigma_base_win = int(args.sigma_base_win) if int(args.sigma_base_win) > 0 else 60
    t_list = _parse_int_list(args.t_list, default=[10, 12, 15])
    stress_mult = float(args.stress_mult) if float(args.stress_mult) > 0 else 1.5

    sigma_win_list_eff = _unique_sorted_ints(sigma_win_list_in + [sigma_base_win, 20, 60])

    level_anchor: Optional[float] = None
    if isinstance(close_latest, (int, float)) and math.isfinite(float(close_latest)):
        level_anchor = float(close_latest)
    elif isinstance(st_close.value, (int, float)) and math.isfinite(float(st_close.value)):
        level_anchor = float(st_close.value)

    returns_pct = _anchored_daily_returns_pct_from_close(close_nf, anchor_idx)

    sigma_map: Dict[int, Optional[float]] = {}
    sigma_reason: Dict[int, str] = {}
    for w in sigma_win_list_eff:
        sd, reason = _compute_sigma_daily_pct(returns_pct, w)
        sigma_map[w] = sd
        sigma_reason[w] = reason

    sigma60 = sigma_map.get(60)
    sigma20 = sigma_map.get(20)
    sigma_base = sigma_map.get(sigma_base_win)

    bands_notes: List[str] = []
    base_conf = "OK"
    if level_anchor is None:
        base_conf = "DOWNGRADED"
        bands_notes.append("Level anchor unavailable (latest_report.Close missing and roll25@UsedDate close NA).")
    if sigma_base is None:
        base_conf = "DOWNGRADED"
        bands_notes.append(f"sigma_base (win={sigma_base_win}) unavailable: {sigma_reason.get(sigma_base_win, 'NA')}")

    base_note = "; ".join(bands_notes).strip()

    base_table_rows, _base_meta = _bands_table(
        level=level_anchor if level_anchor is not None else float("nan"),
        sigma_daily_pct=sigma_base,
        sigma_win=sigma_base_win,
        t_list=t_list,
        label="BASE",
        confidence=base_conf,
        note=base_note,
    )
    base_pct_map_rows = _bands_pct_mapping_table(
        sigma_daily_pct=sigma_base,
        t_list=t_list,
        confidence=base_conf,
        note=base_note,
    )

    # stress sigma: primary then fallback (with explicit chosen window)
    stress_conf = "OK"
    stress_note_parts: List[str] = []
    sigma_stress: Optional[float] = None
    stress_chosen_win: Optional[int] = None

    # primary candidates: 60, 20 only
    cand_primary: List[Tuple[int, float]] = []
    if isinstance(sigma60, (int, float)) and math.isfinite(float(sigma60)):
        cand_primary.append((60, float(sigma60)))
    if isinstance(sigma20, (int, float)) and math.isfinite(float(sigma20)):
        cand_primary.append((20, float(sigma20)))

    if cand_primary:
        # choose max sigma (conservative)
        stress_chosen_win, best_sd = max(cand_primary, key=lambda x: x[1])
        sigma_stress = best_sd * stress_mult
        stress_note_parts.append("policy=primary:max(sigma60,sigma20)*mult")
        stress_note_parts.append(f"chosen_win={stress_chosen_win}")
        if sigma20 is None:
            stress_note_parts.append("sigma20 NA; used sigma60 only.")
        if sigma60 is None:
            stress_note_parts.append("sigma60 NA; used sigma20 only.")
    else:
        # fallback among effective windows (explicit chosen window)
        best_w: Optional[int] = None
        best_sd2: Optional[float] = None
        for w in sigma_win_list_eff:
            sd = sigma_map.get(w)
            if isinstance(sd, (int, float)) and math.isfinite(float(sd)):
                fsd = float(sd)
                if best_sd2 is None or fsd > best_sd2:
                    best_sd2 = fsd
                    best_w = w

        if best_sd2 is not None and best_w is not None:
            sigma_stress = best_sd2 * stress_mult
            stress_chosen_win = best_w
            stress_note_parts.append("policy=fallback:max(available_sigma_in_eff_windows)*mult (sigma20/sigma60 both NA)")
            stress_note_parts.append(f"chosen_win={best_w}")
        else:
            sigma_stress = None
            stress_conf = "DOWNGRADED"
            stress_note_parts.append("sigma20/sigma60 NA and no other sigma available; cannot compute stress bands.")

    if level_anchor is None:
        stress_conf = "DOWNGRADED"
        stress_note_parts.append("Level anchor NA.")

    stress_note_parts.append(f"stress_mult={_fmt(stress_mult)}")
    stress_note = " ".join(stress_note_parts).strip()

    stress_table_rows, _stress_meta = _bands_table(
        level=level_anchor if level_anchor is not None else float("nan"),
        sigma_daily_pct=sigma_stress,
        sigma_win=9999,
        t_list=t_list,
        label="STRESS",
        confidence=stress_conf,
        note=stress_note,
    )
    stress_pct_map_rows = _bands_pct_mapping_table(
        sigma_daily_pct=sigma_stress,
        t_list=t_list,
        confidence=stress_conf,
        note=stress_note,
    )

    # ---------------- markdown build ----------------
    md: List[str] = []
    md.append("# Roll25 Cache Report (TWSE Turnover)")
    md.append("## 1) Summary")
    md.append(f"- generated_at_utc: `{gen_utc}`")
    md.append(f"- generated_at_local: `{gen_local}`")
    md.append(f"- report_date_local: `{report_date_local.isoformat()}`")
    md.append(f"- timezone: `{tz}`")
    md.append(f"- as_of_data_date: `{as_of_data_date}` (latest available)")
    md.append(f"- data_age_days: `{_fmt(data_age_days)}` (warn_if > {args.stale_warn_days})")

    if data_age_days is not None and data_age_days > int(args.stale_warn_days):
        md.append(
            f"- ⚠️ staleness_warning: as_of_data_date is {data_age_days} days behind report_date_local "
            f"(可能跨週末/長假；請避免當作「今日盤後」解讀)"
        )

    md.append(f"- RunDayTag: `{run_day_tag}`")
    md.append(f"- summary: {summary if isinstance(summary, str) else 'NA'}")
    md.append("")
    md.append("## 2) Key Numbers (from latest_report.json)")
    md.append(f"- turnover_twd: `{_fmt(turnover_latest)}`")
    md.append(f"- close: `{_fmt(close_latest)}`")
    md.append(f"- pct_change: `{_fmt(pct_change_latest)}`")
    md.append(f"- amplitude_pct: `{_fmt(amp_latest)}`")
    md.append(f"- volume_multiplier_20: `{_fmt(vol_mult_latest)}`")
    md.append("")
    md.append("## 3) Market Behavior Signals (from latest_report.json)")
    md.append(f"- DownDay: `{_fmt(sig.get('DownDay'))}`")
    md.append(f"- VolumeAmplified: `{_fmt(sig.get('VolumeAmplified'))}`")
    md.append(f"- VolAmplified: `{_fmt(sig.get('VolAmplified'))}`")
    md.append(f"- NewLow_N: `{_fmt(sig.get('NewLow_N'))}`")
    md.append(f"- ConsecutiveBreak: `{_fmt(sig.get('ConsecutiveBreak'))}`")
    md.append("")
    md.append("## 4) Data Quality Flags (from latest_report.json)")
    md.append(f"- OhlcMissing: `{_fmt(sig.get('OhlcMissing'))}`")
    md.append(f"- freshness_ok: `{_fmt(latest.get('freshness_ok'))}`")
    md.append(f"- ohlc_status: `{_fmt(latest.get('ohlc_status'))}`")
    md.append(f"- mode: `{_fmt(latest.get('mode'))}`")
    md.append("")
    md.append("## 5) Z/P Table (market_cache-like; computed from roll25 points)")

    table = [
        ["series", "value", "z60", "p60", "z252", "p252", "zΔ60", "pΔ60", "ret1%", "confidence"],
    ]

    def _row(
        name: str,
        st: RowStats,
        *,
        value_override: Optional[Any] = None,
        suppress_delta_ret: bool = False,
        force_conf: Optional[str] = None,
    ) -> List[str]:
        v = value_override if value_override is not None else st.value
        zD = None if suppress_delta_ret else st.zD60
        pD = None if suppress_delta_ret else st.pD60
        r1 = None if suppress_delta_ret else st.ret1
        conf = force_conf if force_conf is not None else st.confidence
        return [
            name,
            _fmt(v),
            _fmt(st.z60),
            _fmt(st.p60),
            _fmt(st.z252),
            _fmt(st.p252),
            _fmt(zD),
            _fmt(pD),
            _fmt(r1),
            conf,
        ]

    table.append(_row(
        "TURNOVER_TWD",
        st_turnover,
        value_override=turnover_latest if isinstance(turnover_latest, (int, float)) else None
    ))
    table.append(_row(
        "CLOSE",
        st_close,
        value_override=close_latest if isinstance(close_latest, (int, float)) else None,
        force_conf=close_conf_override
    ))
    table.append(_row(
        "PCT_CHANGE_CLOSE",
        st_pct,
        value_override=pct_change_latest if isinstance(pct_change_latest, (int, float)) else None,
        suppress_delta_ret=True
    ))
    table.append(_row(
        "AMPLITUDE_PCT",
        st_amp,
        value_override=amp_latest if isinstance(amp_latest, (int, float)) else None,
        suppress_delta_ret=True,
        force_conf=amp_conf_override
    ))
    table.append(_row(
        "VOL_MULTIPLIER_20",
        st_volm,
        value_override=vol_mult_latest if isinstance(vol_mult_latest, (int, float)) else None,
        suppress_delta_ret=True
    ))

    md.append(_md_table(table))
    md.append("")

    md.append("## 5.1) Volatility Bands (sigma; approximation)")
    md.append(f"- sigma_win_list_input: `{','.join(str(x) for x in sigma_win_list_in)}`")
    md.append(f"- sigma_win_list_effective: `{','.join(str(x) for x in sigma_win_list_eff)}` (includes sigma_base_win + 20 + 60 for audit stability)")
    md.append(f"- sigma_base_win: `{_fmt(float(sigma_base_win))}` (BASE bands)")
    md.append(f"- T list (trading days): `{','.join(str(x) for x in t_list)}`")
    md.append(f"- level anchor: `{_fmt(level_anchor)}` (prefer latest_report.Close else roll25@as_of_data_date)")
    md.append("")
    md.append(f"- sigma20_daily_%: `{_fmt(sigma20)}` (reason: `{sigma_reason.get(20, 'NA')}`)")
    md.append(f"- sigma60_daily_%: `{_fmt(sigma60)}` (reason: `{sigma_reason.get(60, 'NA')}`)")
    md.append("")
    md.append(_md_table(base_table_rows))
    md.append("")
    md.append("### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)")
    md.append(_md_table(base_pct_map_rows))
    md.append("")

    md.append("## 5.2) Stress Bands (regime-shift guardrail; heuristic)")
    md.append(f"- sigma_stress_daily_%: `{_fmt(sigma_stress)}` (chosen_win={_fmt(stress_chosen_win)}; policy: primary=max(60,20) else fallback=max(effective) )")
    md.append(f"- stress_mult: `{_fmt(stress_mult)}`")
    md.append("")
    md.append(_md_table(stress_table_rows))
    md.append("")
    md.append("### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)")
    md.append(_md_table(stress_pct_map_rows))
    md.append("")
    md.append("- Interpretation notes:")
    md.append("  - These bands assume iid + normal approximation of daily returns; this is NOT a guarantee and will understate tail risk in regime shifts.")
    md.append("  - 1-tail 95% uses z=1.645 (one-sided yardstick). 2-tail 95% uses z=1.96 (central 95% interval yardstick).")
    md.append("  - Stress bands are heuristic; they are meant to be conservative-ish, not statistically exact.")
    md.append("")

    md.append("## 6) Audit Notes")
    md.append("- This report is computed from local files only (no external fetch).")
    md.append("- SERIES DIRECTION: all series are NEWEST-FIRST (index 0 = latest).")
    md.append("- roll25 points are read from roll25.json; if empty, fallback to latest_report.cache_roll25 (still local).")
    md.append("- Date ordering uses parsed dates (not string sort).")
    md.append("- MM/DD dates (no year) are resolved by choosing year in {Y-1,Y,Y+1} closest to UsedDate (cross-year safe).")
    md.append("- All VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to as_of_data_date (UsedDate).")
    md.append(f"- UsedDateStatus: `{used_date_status}` (kept for audit; not treated as daily alarm).")
    md.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    md.append("- ret1% is STRICT adjacency at as_of_data_date (UsedDate vs next older row); if missing => NA (no jumping).")
    md.append("- zΔ60/pΔ60 are computed on delta series (today - prev) over last 60 deltas (anchored), not (z_today - z_prev).")
    md.append("- AMPLITUDE derived policy: prefer prev_close (= close - change) as denominator when available; fallback to close.")
    md.append(f"- AMPLITUDE mismatch threshold: {args.amp_mismatch_abs_threshold} (abs(latest - derived@UsedDate) > threshold => DOWNGRADED).")
    md.append(f"- CLOSE pct mismatch threshold: {args.close_pct_mismatch_abs_threshold} (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).")
    md.append("- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.")
    md.append("- VOL_BANDS: sigma computed from anchored DAILY % returns; horizon scaling uses sqrt(T).")
    md.append("- Band % Mapping tables (5.1.a/5.2.a) are display-only: they map sigma_T_% to ±% moves; they do NOT alter signals.")
    if dq_notes:
        md.append("- DQ_NOTES:")
        for n in dq_notes:
            md.append(f"  - {n}")
    md.append("")
    md.append("## 7) Caveats / Sources (from latest_report.json)")
    md.append("```")
    cav = latest.get("caveats")
    if isinstance(cav, str) and cav.strip():
        md.append(cav.rstrip())
    else:
        md.append(_fmt(latest.get("summary")))
    md.append("```")
    md.append("")

    _write_text(args.out, "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())