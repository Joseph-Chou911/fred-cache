#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

Audit-grade alignment rules:
- All displayed VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to UsedDate.
- ret1% is STRICT adjacency: prev = next older row after UsedDate (no jumping).
- zΔ60/pΔ60 are computed on DELTA series (today - prev) over last 60 deltas (anchored).
- Date ordering uses parsed date (not string sort).

Stats:
- z-score uses population std (ddof=0)
- percentile is tie-aware: (less + 0.5*equal) / n * 100

DQ checks:
- AMPLITUDE mismatch: abs(latest - derived@UsedDate) > threshold => AMPLITUDE row DOWNGRADED + note
- CLOSE pct mismatch: abs(ret1_close - latest_pct_change) > threshold => CLOSE row DOWNGRADED + note

IMPORTANT (2026-01-xx fix):
- AMPLITUDE_PCT derived from roll25.json now prefers prev_close denominator if possible:
  prev_close = close - change
  amplitude = (high - low) / abs(prev_close) * 100
  fallback only if prev_close unavailable: (high - low) / abs(close) * 100
This aligns the definition with latest_report.json AmplitudePct (commonly based on prev close).

VOLATILITY BANDS (Approximation; audit-safe):
- sigma_win_list (default: 20,60) computed from last N DAILY % returns anchored at UsedDate.
- horizon scaling uses sqrt(T) (T in trading days).
- 1-tail 95% uses z=1.645 (VaR-like one-sided yardstick).
- 2-tail 95% uses z=1.96 (central 95% interval yardstick).
- stress sigma: sigma_stress = max(sigma60, sigma20) * stress_mult (default: 1.5; can set 2.0)
  This is a heuristic to partially compensate for regime shift / fat tail underestimation.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


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


def _now_local_iso() -> str:
    return datetime.now().astimezone().isoformat()


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

def _parse_date(s: Any, *, default_year: Optional[int] = None) -> Optional[date]:
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None

    # normalize separators
    t2 = t.replace(".", "-").replace("/", "-")

    # YYYY-MM-DD
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
        try:
            return date(default_year, mo, d)
        except Exception:
            return None

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
    out: List[float] = []
    for i in range(len(series_nf) - 1):
        a = series_nf[i]
        b = series_nf[i + 1]
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            continue
        a = float(a); b = float(b)
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
        for k in ("items", "rows", "data", "roll25"):
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


def _row_date_key(r: Dict[str, Any], default_year: Optional[int]) -> Optional[date]:
    raw = r.get("date")
    if isinstance(raw, str):
        return _parse_date(raw, default_year=default_year)
    return None


def _sort_rows_by_date_desc(rows: List[Dict[str, Any]], used_date: Optional[date]) -> List[Dict[str, Any]]:
    default_year = used_date.year if used_date else datetime.now().year

    keyed: List[Tuple[date, Dict[str, Any]]] = []
    for r in rows:
        d = _row_date_key(r, default_year)
        if d is None:
            continue
        keyed.append((d, r))

    keyed.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in keyed]


def _series_turnover(rows_nf: List[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for r in rows_nf:
        out.append(_get_float(r, "turnover_twd", "trade_value", "TradeValue", "turnover") or float("nan"))
    return out


def _series_close(rows_nf: List[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for r in rows_nf:
        out.append(_get_float(r, "close", "Close") or float("nan"))
    return out


def _derive_amplitude_pct_prevclose_first(r: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """
    Derive amplitude% from a roll25.json row.

    Policy:
    1) If high/low exist:
       - prefer prev_close denominator if change exists: prev_close = close - change
       - else fallback to close denominator
    2) If cannot derive, fall back to stored amplitude_pct/AmplitudePct if present.

    Returns: (amplitude_pct, denom_tag)
      denom_tag in {"prev_close", "close", "amp_field", "na"}
    """
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
    out: List[float] = []
    for r in rows_nf:
        amp, _tag = _derive_amplitude_pct_prevclose_first(r)
        if amp is not None and math.isfinite(float(amp)):
            out.append(float(amp))
        else:
            out.append(float("nan"))
    return out


def _series_pct_change_close_from_close(close_nf: List[float]) -> List[float]:
    out: List[float] = []
    for i in range(len(close_nf) - 1):
        a = close_nf[i]
        b = close_nf[i + 1]
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            out.append(float("nan"))
            continue
        a = float(a); b = float(b)
        if not (math.isfinite(a) and math.isfinite(b)) or b == 0:
            out.append(float("nan"))
            continue
        out.append((a - b) / abs(b) * 100.0)
    out.append(float("nan"))
    return out


def _series_vol_multiplier_20(turnover_nf: List[float], min_points: int = 15, win: int = 20) -> List[float]:
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
        w = []
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

    # windows are taken from anchor forward (newer->older), i.e. series_nf[anchor_idx:]
    tail = series_nf[anchor_idx:]

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
        # strict adjacency at anchor: prev is anchor_idx+1
        prev = None
        if anchor_idx + 1 < len(series_nf):
            pv = series_nf[anchor_idx + 1]
            prev = float(pv) if isinstance(pv, (int, float)) and math.isfinite(float(pv)) else None

        r1 = _ret1_pct_strict(v, prev)
        if r1 is None:
            conf = "DOWNGRADED"

        # delta series computed on tail (anchor..older)
        deltas = _delta_series_nf(tail)  # deltas[0] corresponds to anchor - next
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
    Build daily % returns series anchored at UsedDate:
      ret[0] = (close[anchor] - close[anchor+1]) / abs(close[anchor+1]) * 100
    Returns newest->older returns for the anchor tail.
    """
    out: List[float] = []
    if anchor_idx < 0 or anchor_idx >= len(close_nf):
        return out

    tail = close_nf[anchor_idx:]  # close at [anchor, older...]
    for i in range(len(tail) - 1):
        a = tail[i]
        b = tail[i + 1]
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            continue
        a = float(a); b = float(b)
        if not (math.isfinite(a) and math.isfinite(b)) or b == 0:
            continue
        out.append((a - b) / abs(b) * 100.0)
    return out


def _compute_sigma_daily_pct(returns_pct: List[float], win: int) -> Tuple[Optional[float], str]:
    """
    sigma_daily_% = population std of last N daily % returns (anchored).
    returns_pct is newest->older.
    """
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
    """
    Returns (md_table_rows, meta)
    """
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
        # Still render T rows with NA so report stays deterministic/auditable.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--out", required=True)

    ap.add_argument("--amp-mismatch-abs-threshold", type=float,
                    default=float(os.getenv("AMP_MISMATCH_ABS_THRESHOLD", "0.01")))
    ap.add_argument("--close-pct-mismatch-abs-threshold", type=float,
                    default=float(os.getenv("CLOSE_PCT_MISMATCH_ABS_THRESHOLD", "0.05")))

    # Vol bands controls
    ap.add_argument("--sigma-win-list", default=os.getenv("SIGMA_WIN_LIST", "20,60"),
                    help="comma list of return windows for sigma_daily (e.g., 20,60)")
    ap.add_argument("--sigma-base-win", type=int, default=int(os.getenv("SIGMA_BASE_WIN", "60")),
                    help="base sigma window (must be in sigma-win-list ideally)")
    ap.add_argument("--t-list", default=os.getenv("VOL_BANDS_T_LIST", "10,12,15"),
                    help="comma list of trading days horizons (e.g., 10,12,15)")
    ap.add_argument("--stress-mult", type=float, default=float(os.getenv("STRESS_MULT", "1.5")),
                    help="stress multiplier for sigma_stress = max(sigma60, sigma20)*mult (e.g., 1.5 or 2.0)")

    args = ap.parse_args()

    latest = _load_json(args.latest)
    roll25_hist = _load_json(args.roll25)

    gen_utc = _now_utc_z()
    gen_local = _now_local_iso()

    tz = latest.get("timezone") if isinstance(latest, dict) and isinstance(latest.get("timezone"), str) else "NA"
    summary = _safe_get(latest, "summary")
    numbers = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sig = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date_s = numbers.get("UsedDate") if isinstance(numbers.get("UsedDate"), str) else None
    used_date_dt = _parse_date(used_date_s) if used_date_s else None

    used_date = used_date_s if used_date_s else "NA"
    used_date_status = sig.get("UsedDateStatus") if isinstance(sig.get("UsedDateStatus"), str) else "NA"
    run_day_tag = sig.get("RunDayTag") if isinstance(sig.get("RunDayTag"), str) else "NA"

    turnover_latest = numbers.get("TradeValue")
    close_latest = numbers.get("Close")
    pct_change_latest = numbers.get("PctChange")
    amp_latest = numbers.get("AmplitudePct")
    vol_mult_latest = numbers.get("VolumeMultiplier")

    rows_raw = _extract_rows_roll25_json(roll25_hist)
    rows = _sort_rows_by_date_desc(rows_raw, used_date_dt)

    # build date index map (newest-first)
    default_year = used_date_dt.year if used_date_dt else datetime.now().year
    row_dates: List[date] = []
    for r in rows:
        d = _row_date_key(r, default_year)
        if d is not None:
            row_dates.append(d)

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

    # if anchor not found, fallback to 0 (but downgrade confidence via DQ note)
    dq_notes: List[str] = []
    if anchor_idx < 0:
        anchor_idx = 0
        dq_notes.append("UsedDate anchor not found in roll25.json after date-parse; fallback to newest row (index 0).")

    st_turnover = _anchored_stats(turnover_nf, anchor_idx, want_delta_and_ret1=True)
    st_close = _anchored_stats(close_nf, anchor_idx, want_delta_and_ret1=True)

    st_pct = _anchored_stats(pctchg_nf, anchor_idx, want_delta_and_ret1=False)
    st_amp = _anchored_stats(amp_nf, anchor_idx, want_delta_and_ret1=False)
    st_volm = _anchored_stats(volmult_nf, anchor_idx, want_delta_and_ret1=False, require_full_252=False)

    # --- DQ: amplitude mismatch (latest vs derived@UsedDate) ---
    amp_conf_override: Optional[str] = None
    if isinstance(amp_latest, (int, float)) and math.isfinite(float(amp_latest)):
        amp_used = st_amp.value  # derived from roll25.json at anchor
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
                f"(UsedDate={used_date})"
            )

    # ---------------- Volatility Bands computation ----------------
    sigma_win_list = _parse_int_list(args.sigma_win_list, default=[20, 60])
    sigma_base_win = int(args.sigma_base_win) if int(args.sigma_base_win) > 0 else 60
    t_list = _parse_int_list(args.t_list, default=[10, 12, 15])
    stress_mult = float(args.stress_mult) if float(args.stress_mult) > 0 else 1.5

    # level anchor: prefer latest_report.Close else roll25@UsedDate derived
    level_anchor: Optional[float] = None
    if isinstance(close_latest, (int, float)) and math.isfinite(float(close_latest)):
        level_anchor = float(close_latest)
    elif isinstance(st_close.value, (int, float)) and math.isfinite(float(st_close.value)):
        level_anchor = float(st_close.value)

    # compute returns anchored at UsedDate
    returns_pct = _anchored_daily_returns_pct_from_close(close_nf, anchor_idx)

    sigma_map: Dict[int, Optional[float]] = {}
    sigma_reason: Dict[int, str] = {}
    for w in sigma_win_list:
        if w <= 0:
            continue
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

    # base bands (as requested; usually sigma60)
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

    # stress sigma: max(sigma60, sigma20) * stress_mult
    stress_conf = "OK"
    stress_note_parts: List[str] = []
    sigma_candidates: List[float] = []
    if isinstance(sigma60, (int, float)) and math.isfinite(float(sigma60)):
        sigma_candidates.append(float(sigma60))
    if isinstance(sigma20, (int, float)) and math.isfinite(float(sigma20)):
        sigma_candidates.append(float(sigma20))

    sigma_stress: Optional[float] = None
    if sigma_candidates:
        sigma_stress = max(sigma_candidates) * stress_mult
        if sigma20 is None:
            stress_note_parts.append("sigma20 unavailable; stress uses sigma60 only.")
    else:
        sigma_stress = None
        stress_conf = "DOWNGRADED"
        stress_note_parts.append("sigma20/sigma60 both unavailable; cannot compute stress bands.")

    if level_anchor is None:
        stress_conf = "DOWNGRADED"
        stress_note_parts.append("Level anchor unavailable.")

    stress_note_parts.append(f"stress_mult={_fmt(stress_mult)}; sigma_stress=max(sigma60,sigma20)*mult")
    stress_note = " ".join(stress_note_parts).strip()

    stress_table_rows, _stress_meta = _bands_table(
        level=level_anchor if level_anchor is not None else float("nan"),
        sigma_daily_pct=sigma_stress,
        sigma_win=9999,  # synthetic
        t_list=t_list,
        label="STRESS",
        confidence=stress_conf,
        note=stress_note,
    )

    # ---------------- markdown build ----------------
    md: List[str] = []
    md.append("# Roll25 Cache Report (TWSE Turnover)")
    md.append("## 1) Summary")
    md.append(f"- generated_at_utc: `{gen_utc}`")
    md.append(f"- generated_at_local: `{gen_local}`")
    md.append(f"- timezone: `{tz}`")
    md.append(f"- UsedDate: `{used_date}`")
    md.append(f"- UsedDateStatus: `{used_date_status}`")
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
    md.append("## 5) Z/P Table (market_cache-like; computed from roll25.json)")

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

    table.append(_row("TURNOVER_TWD", st_turnover, value_override=turnover_latest if isinstance(turnover_latest, (int, float)) else None))
    table.append(_row("CLOSE", st_close, value_override=close_latest if isinstance(close_latest, (int, float)) else None, force_conf=close_conf_override))
    table.append(_row("PCT_CHANGE_CLOSE", st_pct, value_override=pct_change_latest if isinstance(pct_change_latest, (int, float)) else None, suppress_delta_ret=True))
    table.append(_row("AMPLITUDE_PCT", st_amp, value_override=amp_latest if isinstance(amp_latest, (int, float)) else None, suppress_delta_ret=True, force_conf=amp_conf_override))
    table.append(_row("VOL_MULTIPLIER_20", st_volm, value_override=vol_mult_latest if isinstance(vol_mult_latest, (int, float)) else None, suppress_delta_ret=True))

    md.append(_md_table(table))
    md.append("")

    # 5.1 Base bands (two-tail columns included)
    md.append("## 5.1) Volatility Bands (sigma; approximation)")
    md.append(f"- sigma_win_list (daily % returns): `{','.join(str(x) for x in sigma_win_list)}` (population std; ddof=0)")
    md.append(f"- sigma_base_win: `{_fmt(float(sigma_base_win))}` (BASE bands)")
    md.append(f"- T list (trading days): `{','.join(str(x) for x in t_list)}`")
    md.append(f"- level anchor: `{_fmt(level_anchor)}` (prefer latest_report.Close else roll25@UsedDate)")
    md.append("")
    md.append(f"- sigma20_daily_%: `{_fmt(sigma20)}` (reason: `{sigma_reason.get(20, 'NA')}`)")
    md.append(f"- sigma60_daily_%: `{_fmt(sigma60)}` (reason: `{sigma_reason.get(60, 'NA')}`)")
    md.append("")
    md.append(_md_table(base_table_rows))
    md.append("")

    # 5.2 Stress bands (separate section; no changes to 5.1 table shape beyond extra columns)
    md.append("## 5.2) Stress Bands (regime-shift guardrail; heuristic)")
    md.append(f"- sigma_stress_daily_%: `{_fmt(sigma_stress)}` (policy: max(sigma60,sigma20) * stress_mult)")
    md.append(f"- stress_mult: `{_fmt(stress_mult)}`")
    md.append("")
    md.append(_md_table(stress_table_rows))
    md.append("")
    md.append("- Interpretation notes:")
    md.append("  - These bands assume iid + normal approximation of daily returns; this is NOT a guarantee and will understate tail risk in regime shifts.")
    md.append("  - 1-tail 95% uses z=1.645 (one-sided yardstick). 2-tail 95% uses z=1.96 (central 95% interval yardstick).")
    md.append("  - Stress bands are heuristic; they are meant to be conservative-ish, not statistically exact.")
    md.append("")

    md.append("## 6) Audit Notes")
    md.append("- This report is computed from local files only (no external fetch).")
    md.append("- Date ordering uses parsed dates (not string sort).")
    md.append("- All VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to UsedDate.")
    md.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    md.append("- ret1% is STRICT adjacency at UsedDate (UsedDate vs next older row); if missing => NA (no jumping).")
    md.append("- zΔ60/pΔ60 are computed on delta series (today - prev) over last 60 deltas (anchored), not (z_today - z_prev).")
    md.append("- AMPLITUDE derived policy: prefer prev_close (= close - change) as denominator when available; fallback to close.")
    md.append(f"- AMPLITUDE mismatch threshold: {args.amp_mismatch_abs_threshold} (abs(latest - derived@UsedDate) > threshold => DOWNGRADED).")
    md.append(f"- CLOSE pct mismatch threshold: {args.close_pct_mismatch_abs_threshold} (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).")
    md.append("- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.")
    md.append("- VOL_BANDS: sigma computed from anchored DAILY % returns; horizon scaling uses sqrt(T).")
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