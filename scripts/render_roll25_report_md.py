#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

Design goals:
- Audit-first, deterministic, local-files-only.
- "Key Numbers" come from latest_report.json (authoritative for the latest used_date snapshot).
- Z/P stats are computed from roll25.json history (up to UsedDate).
- AMPLITUDE_PCT special handling:
  - value shown in table uses latest_report.json:numbers.AmplitudePct (authoritative display)
  - stats series comes from roll25.json (amplitude_pct if present, else derived from high/low/close)
  - mismatch check between latest_report amplitude and roll25-derived amplitude-at-UsedDate:
      abs(diff) > AMP_MISMATCH_ABS_THRESHOLD => DQ flag + confidence downgrade for AMPLITUDE row

Stats:
- z-score uses population std (ddof=0) to match your roll25 report convention.
- percentile is tie-aware: (less + 0.5*equal)/n*100
- zΔ60 / pΔ60 / ret1% are computed ONLY for TURNOVER_TWD and CLOSE (to avoid misleading ratios).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ----------------- IO -----------------

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


def _now_local_iso(tz_str: str = "Asia/Taipei") -> str:
    # Keep it simple: rely on TZ env in runner; else show +00:00
    try:
        # If TZ is set in runner to Asia/Taipei, datetime.now() will be local-ish for report readability.
        return datetime.now().astimezone().isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ----------------- Data normalization -----------------

def _normalize_roll25_items(roll25_obj: Any) -> List[Dict[str, Any]]:
    """
    Accept flexible shapes:
    - {"items":[{...},{...}]}
    - {"rows":[...]}
    - [ {...}, {...} ]
    Returns list of dict rows with "date" as str if available, sorted ascending by date.
    """
    rows: List[Any] = []
    if isinstance(roll25_obj, dict):
        if isinstance(roll25_obj.get("items"), list):
            rows = roll25_obj["items"]
        elif isinstance(roll25_obj.get("rows"), list):
            rows = roll25_obj["rows"]
        elif isinstance(roll25_obj.get("data"), list):
            rows = roll25_obj["data"]
        else:
            # fallback: sometimes a dict keyed by date, but we won't guess—return empty
            rows = []
    elif isinstance(roll25_obj, list):
        rows = roll25_obj
    else:
        rows = []

    out: List[Dict[str, Any]] = []
    for it in rows:
        if isinstance(it, dict) and isinstance(it.get("date"), str):
            out.append(it)

    # Sort by YYYY-MM-DD lexicographically is safe
    out.sort(key=lambda x: x.get("date", ""))
    return out


def _filter_upto_date(items_asc: List[Dict[str, Any]], used_date: str) -> List[Dict[str, Any]]:
    return [r for r in items_asc if isinstance(r.get("date"), str) and r["date"] <= used_date]


def _find_row_by_date(items_asc: List[Dict[str, Any]], date: str) -> Optional[Dict[str, Any]]:
    # items are sorted asc, so linear scan is fine given <=400 caps
    for r in items_asc:
        if r.get("date") == date:
            return r
    return None


# ----------------- Metrics extraction (history series) -----------------

def _num(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _get_turnover_twd(row: Dict[str, Any]) -> Optional[float]:
    # Common keys
    for k in ["trade_value", "turnover_twd", "TradeValue", "value", "tv", "tradeValue"]:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _get_close(row: Dict[str, Any]) -> Optional[float]:
    for k in ["close", "Close"]:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _get_pct_change_close(row: Dict[str, Any]) -> Optional[float]:
    # Prefer explicit pct_change field if present
    for k in ["pct_change", "pct_change_close", "PctChange", "pctChange"]:
        v = _num(row.get(k))
        if v is not None:
            return v
    # Else compute if close & prev close available is not possible per-row; return None to avoid guessing
    return None


def _get_high(row: Dict[str, Any]) -> Optional[float]:
    for k in ["high", "High"]:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _get_low(row: Dict[str, Any]) -> Optional[float]:
    for k in ["low", "Low"]:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _get_amplitude_pct_from_row_or_derive(row: Dict[str, Any]) -> Optional[float]:
    # Prefer explicit amplitude_pct field
    for k in ["amplitude_pct", "AmplitudePct", "amplitudePct"]:
        v = _num(row.get(k))
        if v is not None:
            return v

    # Derive if H/L/C exist: (high-low)/close*100
    h = _get_high(row)
    l = _get_low(row)
    c = _get_close(row)
    if h is None or l is None or c is None or c == 0:
        return None
    return (h - l) / abs(c) * 100.0


def _get_vol_multiplier_20(row: Dict[str, Any]) -> Optional[float]:
    # Some datasets store vol multiplier as "vol_multiplier_20", "VolMultiplier", etc.
    for k in ["vol_multiplier_20", "VolMultiplier", "VolumeMultiplier", "volMultiplier", "volumeMultiplier"]:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _build_series(items_upto: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns series as list of (date, value), only when value is numeric.
    """
    out: Dict[str, List[Tuple[str, float]]] = {
        "TURNOVER_TWD": [],
        "CLOSE": [],
        "PCT_CHANGE_CLOSE": [],
        "AMPLITUDE_PCT": [],
        "VOL_MULTIPLIER_20": [],
    }

    for r in items_upto:
        d = r.get("date")
        if not isinstance(d, str):
            continue

        tv = _get_turnover_twd(r)
        if tv is not None:
            out["TURNOVER_TWD"].append((d, tv))

        c = _get_close(r)
        if c is not None:
            out["CLOSE"].append((d, c))

        pc = _get_pct_change_close(r)
        if pc is not None:
            out["PCT_CHANGE_CLOSE"].append((d, pc))

        amp = _get_amplitude_pct_from_row_or_derive(r)
        if amp is not None:
            out["AMPLITUDE_PCT"].append((d, amp))

        vm = _get_vol_multiplier_20(r)
        if vm is not None:
            out["VOL_MULTIPLIER_20"].append((d, vm))

    return out


# ----------------- Stats helpers -----------------

def _pop_mean_std(xs: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / len(xs)  # ddof=0
    sd = math.sqrt(max(var, 0.0))
    return m, sd


def _zscore(value: float, window: List[float]) -> Optional[float]:
    m, sd = _pop_mean_std(window)
    if m is None or sd is None:
        return None
    if sd == 0:
        return 0.0
    return (value - m) / sd


def _percentile_tie_aware(value: float, window: List[float]) -> Optional[float]:
    n = len(window)
    if n == 0:
        return None
    less = sum(1 for x in window if x < value)
    eq = sum(1 for x in window if x == value)
    return (less + 0.5 * eq) / n * 100.0


def _ret1_pct(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    prev = values[-2]
    last = values[-1]
    if prev == 0:
        return None
    return (last - prev) / abs(prev) * 100.0


def _delta_pct_series(values: List[float]) -> List[float]:
    out: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        cur = values[i]
        if prev == 0:
            continue
        out.append((cur - prev) / abs(prev) * 100.0)
    return out


def _window_tail(values: List[float], n: int) -> List[float]:
    if n <= 0:
        return []
    if len(values) < n:
        return []
    return values[-n:]


def _fmt_num(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        # human-friendly but stable
        ax = abs(x)
        if ax >= 1e12:
            return f"{x:.0f}"
        if ax >= 1e9:
            return f"{x:.0f}"
        if ax >= 1e6:
            return f"{x:.0f}"
        if ax >= 1000:
            return f"{x:.2f}".rstrip("0").rstrip(".")
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "NA"
    return f"{x:.6f}".rstrip("0").rstrip(".")


def _confidence_for_window(points: int, need: int) -> str:
    return "OK" if points >= need else "DOWNGRADED"


# ----------------- Main render -----------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest-report", default="roll25_cache/latest_report.json")
    ap.add_argument("--roll25-json", default="roll25_cache/roll25.json")
    ap.add_argument("--out", default="roll25_cache/report.md")
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--win60", type=int, default=60)
    ap.add_argument("--win252", type=int, default=252)
    ap.add_argument("--amp-mismatch-abs-threshold", type=float, default=float(os.getenv("AMP_MISMATCH_ABS_THRESHOLD", "0.01")))
    args = ap.parse_args()

    # Load inputs
    latest = _load_json(args.latest_report)
    roll25 = _load_json(args.roll25_json)

    # From latest_report.json (authoritative for summary & key numbers)
    generated_local = latest.get("generated_at")
    tz = latest.get("timezone") if isinstance(latest.get("timezone"), str) else args.tz
    summary = latest.get("summary") if isinstance(latest.get("summary"), str) else "NA"

    nums = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sig = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date = nums.get("UsedDate") if isinstance(nums.get("UsedDate"), str) else "NA"
    used_date_status = sig.get("UsedDateStatus") if isinstance(sig.get("UsedDateStatus"), str) else "NA"
    run_day_tag = sig.get("RunDayTag") if isinstance(sig.get("RunDayTag"), str) else "NA"

    turnover_twd = _num(nums.get("TradeValue"))
    close = _num(nums.get("Close"))
    pct_change = _num(nums.get("PctChange"))
    amplitude_pct_latest = _num(nums.get("AmplitudePct"))
    vol_mult_20 = _num(nums.get("VolumeMultiplier"))  # in your latest_report, both VolMultiplier and VolumeMultiplier exist

    # Market behavior signals
    down_day = sig.get("DownDay", False)
    volume_amp = sig.get("VolumeAmplified", False)
    vol_amp = sig.get("VolAmplified", False)
    new_low_n = sig.get("NewLow_N", 0)
    cons_break = sig.get("ConsecutiveBreak", 0)

    # Data quality flags
    ohlc_missing = sig.get("OhlcMissing", False)
    freshness_ok = latest.get("freshness_ok") if isinstance(latest.get("freshness_ok"), bool) else "NA"
    ohlc_status = latest.get("ohlc_status") if isinstance(latest.get("ohlc_status"), str) else "NA"
    mode = latest.get("mode") if isinstance(latest.get("mode"), str) else "NA"

    # History series (roll25.json) up to UsedDate
    items_asc = _normalize_roll25_items(roll25)
    dq_notes: List[str] = []

    items_upto: List[Dict[str, Any]] = []
    if isinstance(used_date, str) and used_date != "NA":
        items_upto = _filter_upto_date(items_asc, used_date)
    else:
        items_upto = items_asc[:]  # fallback, but should rarely happen

    series_map = _build_series(items_upto)

    # Build table rows
    # - value in table uses latest_report numbers when available
    # - stats use roll25.json series
    table_rows: List[Dict[str, Any]] = []

    def _compute_stats(series_key: str, value_for_display: Optional[float], compute_delta_ret: bool) -> Dict[str, Any]:
        pts = series_map.get(series_key, [])
        vals = [v for (_d, v) in pts]
        points = len(vals)

        # windows
        w60 = _window_tail(vals, args.win60)
        w252 = _window_tail(vals, args.win252)

        # z/p
        z60 = _zscore(vals[-1], w60) if points >= args.win60 else None
        p60 = _percentile_tie_aware(vals[-1], w60) if points >= args.win60 else None
        z252 = _zscore(vals[-1], w252) if points >= args.win252 else None
        p252 = _percentile_tie_aware(vals[-1], w252) if points >= args.win252 else None

        # delta stats only for selected series
        zD60 = None
        pD60 = None
        ret1 = None
        if compute_delta_ret:
            ret1 = _ret1_pct(vals)
            deltas = _delta_pct_series(vals)  # len = points-1
            # Use last win60 deltas, require >= win60 deltas => >= win60+1 points
            if len(deltas) >= args.win60:
                wD60 = deltas[-args.win60:]
                zD60 = _zscore(deltas[-1], wD60)
                pD60 = _percentile_tie_aware(deltas[-1], wD60)

        # confidence requires full windows for z/p fields; delta requires win60+1 points
        conf = "OK"
        if points < min(args.win60, args.win252):
            # Still allow partial windows? You asked "full window only" => downgrade
            conf = "DOWNGRADED"
        if compute_delta_ret and points < (args.win60 + 1):
            conf = "DOWNGRADED"

        # display value
        disp = value_for_display if value_for_display is not None else (vals[-1] if vals else None)

        return {
            "series": series_key,
            "value": disp,
            "z60": z60,
            "p60": p60,
            "z252": z252,
            "p252": p252,
            "zΔ60": zD60,
            "pΔ60": pD60,
            "ret1%": ret1,
            "confidence": conf,
            "points": points,
        }

    # TURNOVER, CLOSE
    table_rows.append(_compute_stats("TURNOVER_TWD", turnover_twd, compute_delta_ret=True))
    table_rows.append(_compute_stats("CLOSE", close, compute_delta_ret=True))

    # PCT_CHANGE_CLOSE: value from latest_report, stats from roll25.json (if available)
    table_rows.append(_compute_stats("PCT_CHANGE_CLOSE", pct_change, compute_delta_ret=False))

    # AMPLITUDE_PCT: value from latest_report numbers.AmplitudePct (authoritative display),
    # stats from roll25.json derived/field series.
    amp_row = _compute_stats("AMPLITUDE_PCT", amplitude_pct_latest, compute_delta_ret=False)

    # Mismatch check (authoritative latest amplitude vs roll25-derived amplitude at used_date)
    amp_hist_at_used: Optional[float] = None
    if isinstance(used_date, str) and used_date != "NA":
        r_used = _find_row_by_date(items_upto, used_date)
        if isinstance(r_used, dict):
            amp_hist_at_used = _get_amplitude_pct_from_row_or_derive(r_used)

    amp_mismatch = None
    if amplitude_pct_latest is not None and amp_hist_at_used is not None:
        amp_mismatch = amplitude_pct_latest - amp_hist_at_used
        if abs(amp_mismatch) > float(args.amp_mismatch_abs_threshold):
            dq_notes.append(
                f"[DQ] amplitude_value_mismatch: latest_report.AmplitudePct={amplitude_pct_latest:.6f} "
                f"vs roll25_json(derived@UsedDate)={amp_hist_at_used:.6f}; diff={amp_mismatch:+.6f} "
                f"(threshold={args.amp_mismatch_abs_threshold})"
            )
            # Downgrade AMPLITUDE row confidence only (does not mutate other series)
            amp_row["confidence"] = "DOWNGRADED"

    # Embed mismatch debug fields (audit)
    amp_row["_audit"] = {
        "value_source": "latest_report.json:numbers.AmplitudePct",
        "stats_source": "roll25.json:amplitude_pct OR derived(H/L/C)",
        "roll25_json_amp_at_used_date": amp_hist_at_used if amp_hist_at_used is not None else "NA",
        "mismatch_diff": amp_mismatch if amp_mismatch is not None else "NA",
        "mismatch_abs_threshold": args.amp_mismatch_abs_threshold,
    }
    table_rows.append(amp_row)

    # VOL_MULTIPLIER_20
    table_rows.append(_compute_stats("VOL_MULTIPLIER_20", vol_mult_20, compute_delta_ret=False))

    # Render markdown
    gen_utc = _now_utc_z()
    gen_local = _now_local_iso(tz)

    def _md_bool(x: Any) -> str:
        return "true" if bool(x) else "false"

    lines: List[str] = []
    lines.append("# Roll25 Cache Report (TWSE Turnover)")
    lines.append("## 1) Summary")
    lines.append(f"- generated_at_utc: `{gen_utc}`")
    lines.append(f"- generated_at_local: `{gen_local}`")
    lines.append(f"- timezone: `{tz}`")
    lines.append(f"- UsedDate: `{used_date}`")
    lines.append(f"- UsedDateStatus: `{used_date_status}`")
    lines.append(f"- RunDayTag: `{run_day_tag}`")
    lines.append(f"- summary: {summary}")
    lines.append("")
    lines.append("## 2) Key Numbers (from latest_report.json)")
    lines.append(f"- turnover_twd: `{_fmt_num(turnover_twd)}`")
    lines.append(f"- close: `{_fmt_num(close)}`")
    lines.append(f"- pct_change: `{_fmt_num(pct_change)}`")
    lines.append(f"- amplitude_pct: `{_fmt_num(amplitude_pct_latest)}`")
    lines.append(f"- volume_multiplier_20: `{_fmt_num(vol_mult_20)}`")
    lines.append("")
    lines.append("## 3) Market Behavior Signals (from latest_report.json)")
    lines.append(f"- DownDay: `{_md_bool(down_day)}`")
    lines.append(f"- VolumeAmplified: `{_md_bool(volume_amp)}`")
    lines.append(f"- VolAmplified: `{_md_bool(vol_amp)}`")
    lines.append(f"- NewLow_N: `{_fmt_num(_num(new_low_n) if not isinstance(new_low_n, bool) else None) if not isinstance(new_low_n, int) else str(new_low_n)}`")
    lines.append(f"- ConsecutiveBreak: `{_fmt_num(_num(cons_break) if not isinstance(cons_break, bool) else None) if not isinstance(cons_break, int) else str(cons_break)}`")
    lines.append("")
    lines.append("## 4) Data Quality Flags (from latest_report.json)")
    lines.append(f"- OhlcMissing: `{_md_bool(ohlc_missing)}`")
    lines.append(f"- freshness_ok: `{_fmt_num(freshness_ok) if freshness_ok in ('NA', True, False) else _fmt_num(freshness_ok)}`")
    lines.append(f"- ohlc_status: `{ohlc_status}`")
    lines.append(f"- mode: `{mode}`")
    lines.append("")

    if dq_notes:
        lines.append("## 4.1) Data Quality Notes (derived checks)")
        for n in dq_notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## 5) Z/P Table (market_cache-like; computed from roll25.json)")
    lines.append("| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    # stable ordering
    for r in table_rows:
        lines.append(
            f"| {r['series']} "
            f"| {_fmt_num(r['value'])} "
            f"| {_fmt_pct(r['z60'])} "
            f"| {_fmt_pct(r['p60'])} "
            f"| {_fmt_pct(r['z252'])} "
            f"| {_fmt_pct(r['p252'])} "
            f"| {_fmt_pct(r['zΔ60'])} "
            f"| {_fmt_pct(r['pΔ60'])} "
            f"| {_fmt_pct(r['ret1%'])} "
            f"| {r['confidence']} |"
        )

    lines.append("")
    lines.append("## 6) Audit Notes")
    lines.append("- This report is computed from local files only (no external fetch).")
    lines.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    lines.append("- AMPLITUDE_PCT value uses latest_report.json:numbers.AmplitudePct; stats use roll25.json series (amplitude_pct or derived from H/L/C).")
    lines.append(f"- AMPLITUDE_PCT mismatch check: abs(latest - roll25_derived@UsedDate) > {args.amp_mismatch_abs_threshold} => DQ note + AMPLITUDE row confidence=DOWNGRADED.")
    lines.append("- ret1% and zΔ60/pΔ60 are only computed for TURNOVER_TWD and CLOSE; other series show NA to avoid misleading ratios.")
    lines.append("- If insufficient points for any required full window, corresponding stats remain NA and confidence is DOWNGRADED (no guessing).")
    lines.append("")
    lines.append("## 7) Caveats / Sources (from latest_report.json)")
    lines.append("```")
    cav = latest.get("caveats")
    if isinstance(cav, str) and cav.strip():
        lines.append(cav.rstrip())
    else:
        # Fallback: include any source fields if present
        lines.append("NA")
    lines.append("```")
    lines.append("")

    _write_text(args.out, "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())