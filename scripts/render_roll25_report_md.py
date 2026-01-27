#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

Key fixes (important):
- ret1% and zΔ60/pΔ60 are computed using STRICT adjacency (index 0 vs index 1).
  If day-1 is missing, we output NA (NO "skip missing" / NO jumping).
- z/p windows are computed by taking the newest N finite points in-order.
  If insufficient points for a required window => NA and confidence DOWNGRADED.

Definitions:
- z-score: population std (ddof=0)
- percentile: tie-aware (less + 0.5*equal) / n * 100
- zΔ60/pΔ60: statistics on delta series (today - prev) over last 60 deltas
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
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
        # stable formatting
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
    return cur


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
    """
    Take newest N finite points in-order from series (newest-first).
    Does NOT reorder; does NOT jump for ret1 computation; only for window stats.
    """
    out: List[float] = []
    for v in series_nf:
        if isinstance(v, (int, float)) and math.isfinite(float(v)):
            out.append(float(v))
            if len(out) >= n:
                break
    if len(out) < n:
        return None
    return out


def _strict_ret1_pct(series_nf: List[float]) -> Optional[float]:
    """
    Strict adjacency: uses series_nf[0] and series_nf[1] only.
    If either is missing/non-finite => NA (no jumping).
    """
    if len(series_nf) < 2:
        return None
    a = series_nf[0]
    b = series_nf[1]
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return None
    a = float(a)
    b = float(b)
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    if b == 0:
        return None
    return (a - b) / abs(b) * 100.0


def _strict_delta_today(series_nf: List[float]) -> Optional[float]:
    """
    Strict adjacency: delta_today = series_nf[0] - series_nf[1]
    """
    if len(series_nf) < 2:
        return None
    a = series_nf[0]
    b = series_nf[1]
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return None
    a = float(a)
    b = float(b)
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    return a - b


def _delta_series_nf(series_nf: List[float]) -> List[float]:
    """
    Delta series aligned to adjacency: delta[i] = series[i] - series[i+1]
    Only keep finite deltas where both points are finite.
    """
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


@dataclass
class RowStats:
    value: Optional[float]
    z60: Optional[float]
    p60: Optional[float]
    z252: Optional[float]
    p252: Optional[float]
    zD60: Optional[float]   # printed as zΔ60
    pD60: Optional[float]   # printed as pΔ60
    ret1: Optional[float]   # printed as ret1%
    confidence: str         # OK / DOWNGRADED


def _compute_level_stats(
    series_nf: List[float],
    *,
    want_delta_and_ret1: bool,
    require_full_252: bool = True,
) -> RowStats:
    """
    series_nf is newest-first, may contain nan/None.
    """
    # value (today) must be finite for meaningful output
    if not series_nf:
        return RowStats(None, None, None, None, None, None, None, None, "DOWNGRADED")

    v0 = series_nf[0]
    if not isinstance(v0, (int, float)):
        v = None
    else:
        v = float(v0)
        if not math.isfinite(v):
            v = None

    conf = "OK"

    w60 = _take_newest_finite(series_nf, 60)
    w252 = _take_newest_finite(series_nf, 252)

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
        # ret1 strictly adjacent
        r1 = _strict_ret1_pct(series_nf)
        if r1 is None:
            conf = "DOWNGRADED"

        # zΔ60/pΔ60 on delta series, but today's delta must be strictly adjacent
        d_today = _strict_delta_today(series_nf)
        deltas = _delta_series_nf(series_nf)
        d60 = _take_newest_finite(deltas, 60)
        if d_today is not None and d60 is not None:
            zD60 = _z_score_pop(d_today, d60)
            pD60 = _percentile_tie_aware(d_today, d60)
        else:
            conf = "DOWNGRADED"

    return RowStats(v, z60, p60, z252, p252, zD60, pD60, r1, conf)


# -------------- roll25.json parsing --------------

def _extract_rows_roll25_json(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("items", "rows", "data", "roll25"):
            v = obj.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _sort_newest_first(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(r: Dict[str, Any]) -> str:
        d = r.get("date")
        return d if isinstance(d, str) else ""
    return sorted(rows, key=key, reverse=True)


def _get_float(r: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        v = r.get(k)
        if isinstance(v, (int, float)):
            f = float(v)
            if math.isfinite(f):
                return f
    return None


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


def _series_pct_change_close_from_close(close_nf: List[float]) -> List[float]:
    """
    pct_change[t] = (close[t] - close[t+1]) / abs(close[t+1]) * 100
    Strict adjacency per step, but this is a SERIES (not ret1 field).
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


def _series_amplitude_pct(rows_nf: List[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for r in rows_nf:
        amp = _get_float(r, "amplitude_pct", "AmplitudePct")
        if amp is not None:
            out.append(amp)
            continue
        h = _get_float(r, "high", "High")
        l = _get_float(r, "low", "Low")
        c = _get_float(r, "close", "Close")
        if h is not None and l is not None and c is not None and c != 0:
            out.append((h - l) / abs(c) * 100.0)
        else:
            out.append(float("nan"))
    return out


def _series_vol_multiplier_20(turnover_nf: List[float], min_points: int = 15, win: int = 20) -> List[float]:
    """
    vol_multiplier_20[t] = turnover[t] / avg(turnover[t+1..t+win]) (exclude today)
    Require at least min_points finite values in the avg window.
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


# -------------- markdown helpers --------------

def _md_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    out = []
    out.append("| " + " | ".join(rows[0]) + " |")
    out.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--amp-mismatch-abs-threshold", type=float, default=float(os.getenv("AMP_MISMATCH_ABS_THRESHOLD", "0.01")))
    args = ap.parse_args()

    latest = _load_json(args.latest)
    roll25_hist = _load_json(args.roll25)

    gen_utc = _now_utc_z()
    gen_local = _now_local_iso()

    tz = latest.get("timezone") if isinstance(latest, dict) and isinstance(latest.get("timezone"), str) else "NA"
    summary = _safe_get(latest, "summary")
    numbers = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sig = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date = numbers.get("UsedDate") if isinstance(numbers.get("UsedDate"), str) else "NA"
    used_date_status = sig.get("UsedDateStatus") if isinstance(sig.get("UsedDateStatus"), str) else "NA"
    run_day_tag = sig.get("RunDayTag") if isinstance(sig.get("RunDayTag"), str) else "NA"

    turnover_latest = numbers.get("TradeValue")
    close_latest = numbers.get("Close")
    pct_change_latest = numbers.get("PctChange")
    amp_latest = numbers.get("AmplitudePct")
    vol_mult_latest = numbers.get("VolumeMultiplier")

    rows = _sort_newest_first(_extract_rows_roll25_json(roll25_hist))

    turnover_nf = _series_turnover(rows)
    close_nf = _series_close(rows)
    pctchg_nf = _series_pct_change_close_from_close(close_nf)
    amp_nf = _series_amplitude_pct(rows)
    volmult_nf = _series_vol_multiplier_20(turnover_nf, min_points=15, win=20)

    turnover_nf, close_nf, pctchg_nf, amp_nf, volmult_nf = _truncate_to_common_length(
        turnover_nf, close_nf, pctchg_nf, amp_nf, volmult_nf
    )

    st_turnover = _compute_level_stats(turnover_nf, want_delta_and_ret1=True)
    st_close = _compute_level_stats(close_nf, want_delta_and_ret1=True)

    # PCT_CHANGE_CLOSE: show z/p on the series itself, suppress delta/ret
    st_pct = _compute_level_stats(pctchg_nf, want_delta_and_ret1=False)

    # AMPLITUDE_PCT: value from latest_report; stats from roll25.json; suppress delta/ret
    st_amp = _compute_level_stats(amp_nf, want_delta_and_ret1=False)

    # VOL_MULTIPLIER_20: value from latest_report; stats from derived volmult_nf; suppress delta/ret
    # z252 needs 252 finite points of volmult, but volmult starts having valid values only after enough history.
    st_volm = _compute_level_stats(volmult_nf, want_delta_and_ret1=False)

    # amplitude mismatch note (optional, conservative)
    amp_conf_override: Optional[str] = None
    amp_mismatch_note: Optional[str] = None
    if isinstance(amp_latest, (int, float)) and used_date != "NA":
        amp_used = None
        for r in rows:
            if r.get("date") == used_date:
                a = _get_float(r, "amplitude_pct", "AmplitudePct")
                if a is None:
                    h = _get_float(r, "high", "High")
                    l = _get_float(r, "low", "Low")
                    c = _get_float(r, "close", "Close")
                    if h is not None and l is not None and c is not None and c != 0:
                        a = (h - l) / abs(c) * 100.0
                amp_used = a
                break
        if isinstance(amp_used, (int, float)) and math.isfinite(float(amp_used)):
            diff = abs(float(amp_latest) - float(amp_used))
            if diff > float(args.amp_mismatch_abs_threshold):
                amp_conf_override = "DOWNGRADED"
                amp_mismatch_note = f"AMPLITUDE_PCT mismatch: abs(latest - roll25_derived@UsedDate) = {diff:.6f} > {args.amp_mismatch_abs_threshold}"

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
    table.append(_row("CLOSE", st_close, value_override=close_latest if isinstance(close_latest, (int, float)) else None))
    table.append(_row("PCT_CHANGE_CLOSE", st_pct, value_override=pct_change_latest if isinstance(pct_change_latest, (int, float)) else None, suppress_delta_ret=True))
    table.append(_row("AMPLITUDE_PCT", st_amp, value_override=amp_latest if isinstance(amp_latest, (int, float)) else None, suppress_delta_ret=True, force_conf=amp_conf_override))
    table.append(_row("VOL_MULTIPLIER_20", st_volm, value_override=vol_mult_latest if isinstance(vol_mult_latest, (int, float)) else None, suppress_delta_ret=True))

    md.append(_md_table(table))
    md.append("")
    md.append("## 6) Audit Notes")
    md.append("- This report is computed from local files only (no external fetch).")
    md.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    md.append("- ret1% uses STRICT adjacency (series[0] vs series[1]); if day-1 missing => NA (no jumping).")
    md.append("- zΔ60/pΔ60 are computed on the delta series (today - prev) over the last 60 deltas, not (z_today - z_prev).")
    md.append("- AMPLITUDE_PCT value uses latest_report.json:numbers.AmplitudePct; stats use roll25.json series (amplitude_pct or derived from H/L/C).")
    md.append(f"- AMPLITUDE_PCT mismatch check: abs(latest - roll25_derived@UsedDate) > {args.amp_mismatch_abs_threshold} => DQ note + AMPLITUDE row confidence=DOWNGRADED.")
    if amp_mismatch_note:
        md.append(f"- DQ_NOTE: {amp_mismatch_note}")
    md.append("- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.")
    md.append("- If insufficient points for any required full window, corresponding stats remain NA and confidence is DOWNGRADED (no guessing).")
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