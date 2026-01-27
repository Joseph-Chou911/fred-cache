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
    return cur


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--amp-mismatch-abs-threshold", type=float, default=float(os.getenv("AMP_MISMATCH_ABS_THRESHOLD", "0.01")))
    ap.add_argument("--close-pct-mismatch-abs-threshold", type=float, default=float(os.getenv("CLOSE_PCT_MISMATCH_ABS_THRESHOLD", "0.05")))
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
                dq_notes.append(
                    f"AMPLITUDE_PCT mismatch: abs(latest_report.AmplitudePct - roll25@UsedDate) = {diff:.6f} > {args.amp_mismatch_abs_threshold}"
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
    md.append("## 6) Audit Notes")
    md.append("- This report is computed from local files only (no external fetch).")
    md.append("- Date ordering uses parsed dates (not string sort).")
    md.append("- All VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to UsedDate.")
    md.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    md.append("- ret1% is STRICT adjacency at UsedDate (UsedDate vs next older row); if missing => NA (no jumping).")
    md.append("- zΔ60/pΔ60 are computed on delta series (today - prev) over last 60 deltas (anchored), not (z_today - z_prev).")
    md.append(f"- AMPLITUDE mismatch threshold: {args.amp_mismatch_abs_threshold} (abs(latest - roll25@UsedDate) > threshold => DOWNGRADED).")
    md.append(f"- CLOSE pct mismatch threshold: {args.close_pct_mismatch_abs_threshold} (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).")
    md.append("- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.")
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