#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

Goals:
- Local-only (no external fetch).
- Produce market_cache-like Z/P table: z60/p60/z252/p252 + zΔ60/pΔ60 + ret1%
- Deterministic; missing/insufficient points => NA + confidence DOWNGRADED.
- Define zΔ60/pΔ60 as statistics on "delta series" (today - prev), not (z_today - z_prev).

Series produced:
- TURNOVER_TWD          (level)
- CLOSE                 (level)
- PCT_CHANGE_CLOSE      (already a daily % level; NO ret1% / zΔ60 to avoid double-counting)
- AMPLITUDE_PCT         (level; value uses latest_report.numbers.AmplitudePct; stats from roll25.json)
- VOL_MULTIPLIER_20     (derived from turnover_twd / avg(prev 20 turnover); min_points=15)
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ----------------- IO helpers -----------------

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
    # relies on runner TZ=Asia/Taipei set in yml; still safe without it
    return datetime.now().astimezone().isoformat()


def _fmt(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        # keep stable but not overly long; table itself prints raw where reasonable
        return f"{x:.6f}".rstrip("0").rstrip(".") if abs(x) < 1e12 else f"{x:.0f}"
    return str(x)


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ----------------- Stats helpers -----------------

def _z_score_pop(x: float, arr: List[float]) -> Optional[float]:
    """Population std ddof=0, consistent with your report note."""
    if len(arr) < 2:
        return None
    mean = sum(arr) / len(arr)
    var = sum((v - mean) ** 2 for v in arr) / len(arr)
    sd = math.sqrt(max(var, 0.0))
    if sd == 0:
        return 0.0
    return (x - mean) / sd


def _percentile_tie_aware(x: float, arr: List[float]) -> Optional[float]:
    """
    Tie-aware percentile in [0,100]:
    p = (count_less + 0.5*count_equal) / n * 100
    """
    n = len(arr)
    if n == 0:
        return None
    less = sum(1 for v in arr if v < x)
    eq = sum(1 for v in arr if v == x)
    return (less + 0.5 * eq) / n * 100.0


def _window(arr_newest_first: List[float], n: int) -> Optional[List[float]]:
    if n <= 0:
        return None
    if len(arr_newest_first) < n:
        return None
    return arr_newest_first[:n]


def _ret1_pct(levels_newest_first: List[float]) -> Optional[float]:
    if len(levels_newest_first) < 2:
        return None
    prev = levels_newest_first[1]
    cur = levels_newest_first[0]
    if prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100.0


def _deltas_newest_first(levels_newest_first: List[float]) -> List[float]:
    """delta[t] = level[t] - level[t+1], newest-first aligned (len = len(levels)-1)"""
    out: List[float] = []
    for i in range(len(levels_newest_first) - 1):
        out.append(levels_newest_first[i] - levels_newest_first[i + 1])
    return out


@dataclass
class RowStats:
    value: Optional[float]
    z60: Optional[float]
    p60: Optional[float]
    z252: Optional[float]
    p252: Optional[float]
    zD60: Optional[float]    # will be printed as zΔ60
    pD60: Optional[float]    # will be printed as pΔ60
    ret1: Optional[float]    # will be printed as ret1%
    confidence: str          # OK / DOWNGRADED


def _compute_stats_for_level_series(
    levels_newest_first: List[float],
    *,
    want_delta_and_ret1: bool = True,
    require_full_252: bool = True,
) -> RowStats:
    """
    For level series:
    - z60/p60 on last 60 levels (including today)
    - z252/p252 on last 252 levels (including today)
    - zΔ60/pΔ60 on last 60 deltas (delta series, newest-first)
    - ret1% on today vs prev

    Confidence:
    - OK only if windows used exist; otherwise DOWNGRADED.
    """
    val = levels_newest_first[0] if levels_newest_first else None
    conf = "OK"

    # levels windows
    w60 = _window(levels_newest_first, 60)
    w252 = _window(levels_newest_first, 252)

    z60 = _z_score_pop(val, w60) if (val is not None and w60 is not None) else None
    p60 = _percentile_tie_aware(val, w60) if (val is not None and w60 is not None) else None

    z252 = _z_score_pop(val, w252) if (val is not None and w252 is not None) else None
    p252 = _percentile_tie_aware(val, w252) if (val is not None and w252 is not None) else None

    if require_full_252 and w252 is None:
        conf = "DOWNGRADED"
    if w60 is None:
        conf = "DOWNGRADED"

    zD60 = None
    pD60 = None
    r1 = None
    if want_delta_and_ret1:
        # delta series windows
        deltas = _deltas_newest_first(levels_newest_first)
        d_today = deltas[0] if deltas else None
        d60 = _window(deltas, 60)
        if d_today is not None and d60 is not None:
            zD60 = _z_score_pop(d_today, d60)
            pD60 = _percentile_tie_aware(d_today, d60)
        else:
            conf = "DOWNGRADED"

        r1 = _ret1_pct(levels_newest_first)
        if r1 is None:
            conf = "DOWNGRADED"

    return RowStats(
        value=val,
        z60=z60, p60=p60,
        z252=z252, p252=p252,
        zD60=zD60, pD60=pD60,
        ret1=r1,
        confidence=conf,
    )


# ----------------- roll25.json parsing -----------------

def _extract_rows_roll25_json(obj: Any) -> List[Dict[str, Any]]:
    """
    Accept a few common shapes:
    - {"items":[{...}, ...]}
    - {"rows":[{...}, ...]}
    - [{...}, ...]
    """
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
    # assume YYYY-MM-DD; lexicographic works
    return sorted(rows, key=key, reverse=True)


def _get_float(r: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        v = r.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _series_turnover(rows_nf: List[Dict[str, Any]]) -> Tuple[List[float], List[str]]:
    vals: List[float] = []
    dates: List[str] = []
    for r in rows_nf:
        d = r.get("date")
        tv = _get_float(r, "turnover_twd", "trade_value", "TradeValue", "turnover", "value")
        if isinstance(d, str) and tv is not None:
            dates.append(d)
            vals.append(tv)
    return vals, dates


def _series_close(rows_nf: List[Dict[str, Any]]) -> Tuple[List[float], List[str]]:
    vals: List[float] = []
    dates: List[str] = []
    for r in rows_nf:
        d = r.get("date")
        c = _get_float(r, "close", "Close")
        if isinstance(d, str) and c is not None:
            dates.append(d)
            vals.append(c)
    return vals, dates


def _series_pct_change_close_from_close(close_nf: List[float]) -> List[float]:
    """
    daily pct return (%):
    r[t] = (close[t] - close[t+1]) / abs(close[t+1]) * 100
    newest-first aligned, length = len(close)-1; we pad first element (today) as r[0] using today vs prev.
    For convenience in z/p (needs same length as close series), we define:
    pct_change[t] = r[t] for t=0..len-2; last (oldest) set to NA via omit.
    We'll return a same-length list by appending a placeholder for oldest; renderer will trim to common length.
    """
    out: List[float] = []
    for i in range(len(close_nf) - 1):
        prev = close_nf[i + 1]
        cur = close_nf[i]
        if prev == 0:
            out.append(float("nan"))
        else:
            out.append((cur - prev) / abs(prev) * 100.0)
    # pad for oldest
    out.append(float("nan"))
    return out


def _series_amplitude_pct(rows_nf: List[Dict[str, Any]], close_nf: List[float]) -> List[float]:
    """
    Prefer roll25.json amplitude_pct if present; else derive from (high-low)/close*100 when possible.
    Return same-length list aligned with close_nf when possible; missing points => nan.
    """
    out: List[float] = []
    for idx, r in enumerate(rows_nf):
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
    vol_multiplier_20[t] = turnover[t] / avg(turnover[t+1..t+win])  (exclude today; use prior 20)
    newest-first alignment.
    Require at least min_points available in the avg window to compute; else nan.
    """
    out: List[float] = []
    for i in range(len(turnover_nf)):
        # prior window is i+1 .. i+win
        start = i + 1
        end = i + win + 1
        if start >= len(turnover_nf):
            out.append(float("nan"))
            continue
        window = turnover_nf[start:end]
        window = [x for x in window if isinstance(x, (int, float)) and math.isfinite(x)]
        if len(window) < min_points:
            out.append(float("nan"))
            continue
        avg = sum(window) / len(window)
        if avg == 0:
            out.append(float("nan"))
            continue
        out.append(turnover_nf[i] / avg)
    return out


def _align_and_clean(series: List[float]) -> List[float]:
    """Drop trailing nans at the end is not safe; we keep length but filter when computing windows."""
    return series


def _finite_series(series_nf: List[float]) -> List[float]:
    return [x for x in series_nf if isinstance(x, (int, float)) and math.isfinite(x)]


def _truncate_to_common_length(*series: List[float]) -> List[List[float]]:
    m = min(len(s) for s in series) if series else 0
    return [s[:m] for s in series]


# ----------------- Report rendering -----------------

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
    ap.add_argument("--latest", required=True, help="roll25_cache/latest_report.json")
    ap.add_argument("--roll25", required=True, help="roll25_cache/roll25.json (history)")
    ap.add_argument("--out", required=True, help="roll25_cache/report.md")
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

    turnover = numbers.get("TradeValue")
    close = numbers.get("Close")
    pct_change = numbers.get("PctChange")
    amp_latest = numbers.get("AmplitudePct")
    vol_mult = numbers.get("VolumeMultiplier")

    # Parse roll25 history
    rows = _extract_rows_roll25_json(roll25_hist)
    rows_nf = _sort_newest_first(rows)

    turnover_nf, _ = _series_turnover(rows_nf)
    close_nf, _ = _series_close(rows_nf)

    # Align base series lengths (turnover and close should usually align; we still truncate defensively)
    turnover_nf, close_nf = _truncate_to_common_length(turnover_nf, close_nf)

    pctchg_nf = _series_pct_change_close_from_close(close_nf)
    amp_nf = _series_amplitude_pct(rows_nf, close_nf)
    volmult_nf = _series_vol_multiplier_20(turnover_nf, min_points=15, win=20)

    # truncate all to common length for coherent windows
    turnover_nf, close_nf, pctchg_nf, amp_nf, volmult_nf = _truncate_to_common_length(
        turnover_nf, close_nf, pctchg_nf, amp_nf, volmult_nf
    )

    # For stats computation we need newest-first series with finite values.
    # We'll compute stats on full series (with nans) by filtering inside window steps:
    def _stats_level(series_nf: List[float], want_delta_and_ret1: bool, require_full_252: bool = True) -> RowStats:
        # Keep order; but stats functions need windows; we create filtered windows each time would be expensive.
        # Instead: create "compact" finite series; but then today's index may shift if today's value nan.
        # Here we assume today's value should be finite for our series; otherwise we downgrade.
        s = [float(x) for x in series_nf if isinstance(x, (int, float)) and math.isfinite(x)]
        if not s:
            return RowStats(None, None, None, None, None, None, None, None, "DOWNGRADED")
        return _compute_stats_for_level_series(
            s,
            want_delta_and_ret1=want_delta_and_ret1,
            require_full_252=require_full_252,
        )

    # Compute rows:
    st_turnover = _stats_level(turnover_nf, want_delta_and_ret1=True)
    st_close = _stats_level(close_nf, want_delta_and_ret1=True)

    # PCT_CHANGE_CLOSE: compute z/p on the series itself, but NO ret1 and NO zΔ60 (avoid double counting)
    # We still require full windows for confidence.
    st_pct = _stats_level(pctchg_nf, want_delta_and_ret1=False)

    st_amp = _stats_level(amp_nf, want_delta_and_ret1=False)  # amplitude: no ret1/zΔ60 to avoid confusion
    st_volm = _stats_level(volmult_nf, want_delta_and_ret1=False)  # vol multiplier: no ret1/zΔ60

    # Use latest_report.json values for some display fields (value column):
    # - AMPLITUDE_PCT value uses latest_report numbers.AmplitudePct
    # - VOL_MULTIPLIER_20 value uses latest_report numbers.VolumeMultiplier
    # But z/p stats remain based on history series.
    # Also mismatch check on amplitude at UsedDate between latest_report and roll25-derived (if we can locate it).
    amp_conf_override: Optional[str] = None
    amp_mismatch_note: Optional[str] = None
    if isinstance(amp_latest, (int, float)) and used_date != "NA":
        # find matching date row in rows_nf (they include date)
        amp_used = None
        for r in rows_nf:
            if isinstance(r.get("date"), str) and r["date"] == used_date:
                # derived amplitude for that day (same logic as series)
                a = _get_float(r, "amplitude_pct", "AmplitudePct")
                if a is None:
                    h = _get_float(r, "high", "High")
                    l = _get_float(r, "low", "Low")
                    c = _get_float(r, "close", "Close")
                    if h is not None and l is not None and c is not None and c != 0:
                        a = (h - l) / abs(c) * 100.0
                amp_used = a
                break
        if isinstance(amp_used, (int, float)) and math.isfinite(amp_used):
            if abs(float(amp_latest) - float(amp_used)) > float(args.amp_mismatch_abs_threshold):
                amp_conf_override = "DOWNGRADED"
                amp_mismatch_note = (
                    f"AMPLITUDE_PCT mismatch: abs(latest - roll25_derived@UsedDate) "
                    f"= {abs(float(amp_latest) - float(amp_used)):.6f} > {args.amp_mismatch_abs_threshold}"
                )

    # Build markdown
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
    md.append(f"- turnover_twd: `{_fmt(turnover)}`")
    md.append(f"- close: `{_fmt(close)}`")
    md.append(f"- pct_change: `{_fmt(pct_change)}`")
    md.append(f"- amplitude_pct: `{_fmt(amp_latest)}`")
    md.append(f"- volume_multiplier_20: `{_fmt(vol_mult)}`")
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

    # Table header: match your requested naming
    table = [
        ["series", "value", "z60", "p60", "z252", "p252", "zΔ60", "pΔ60", "ret1%", "confidence"],
    ]

    def _row(name: str, st: RowStats, value_override: Optional[Any] = None, force_conf: Optional[str] = None, suppress_delta_ret: bool = False) -> List[str]:
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

    # TURNOVER_TWD
    table.append(_row("TURNOVER_TWD", st_turnover, value_override=turnover if isinstance(turnover, (int, float)) else st_turnover.value))
    # CLOSE
    table.append(_row("CLOSE", st_close, value_override=close if isinstance(close, (int, float)) else st_close.value))
    # PCT_CHANGE_CLOSE: show value from latest_report (PctChange), but suppress delta/ret
    table.append(_row(
        "PCT_CHANGE_CLOSE",
        st_pct,
        value_override=pct_change if isinstance(pct_change, (int, float)) else st_pct.value,
        suppress_delta_ret=True
    ))
    # AMPLITUDE_PCT: value uses latest_report; stats from history; suppress delta/ret; apply mismatch downgrade if needed
    amp_force_conf = amp_conf_override if amp_conf_override is not None else st_amp.confidence
    table.append(_row(
        "AMPLITUDE_PCT",
        st_amp,
        value_override=amp_latest if isinstance(amp_latest, (int, float)) else st_amp.value,
        force_conf=amp_force_conf,
        suppress_delta_ret=True
    ))
    # VOL_MULTIPLIER_20: value uses latest_report; stats from derived history; suppress delta/ret
    table.append(_row(
        "VOL_MULTIPLIER_20",
        st_volm,
        value_override=vol_mult if isinstance(vol_mult, (int, float)) else st_volm.value,
        suppress_delta_ret=True
    ))

    md.append(_md_table(table))
    md.append("")
    md.append("## 6) Audit Notes")
    md.append("- This report is computed from local files only (no external fetch).")
    md.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
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
        # keep at least some provenance fields if caveats absent
        md.append(_fmt(latest.get("summary")))
    md.append("```")
    md.append("")

    _write_text(args.out, "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())