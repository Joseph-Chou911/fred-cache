#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

Goals:
- Market-cache-like Z/P table: z60/p60/z252/p252 + zΔ60/pΔ60 + ret1%
- Column names aligned to market_cache style: zΔ60, pΔ60, ret1%
- NO external fetch. Local files only.
- Conservative NA handling:
  - ret1% + zΔ60/pΔ60 are meaningful only for TURNOVER_TWD and CLOSE.
  - For PCT_CHANGE_CLOSE / AMPLITUDE_PCT / VOL_MULTIPLIER_20, ret1% and zΔ60/pΔ60 => NA to avoid misleading ratios.
- z-score uses population std (ddof=0).
- Percentile is tie-aware: (count_less + 0.5*count_equal)/n * 100.

Inputs (defaults):
- roll25_cache/latest_report.json
- roll25_cache/roll25.json

Output (default):
- roll25_cache/report.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ---------------- I/O ----------------

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


def _iso_local_tpe() -> str:
    # Avoid zoneinfo dependency; assume Asia/Taipei = UTC+8 (DST-free)
    dt = datetime.now(timezone.utc).astimezone(timezone.utc)
    dt_tpe = dt.astimezone(timezone.utc).replace(tzinfo=timezone.utc).astimezone(
        timezone.utc
    )
    # Instead of risking wrong conversion, just stamp local from latest_report if available;
    # This function kept for fallback only.
    return datetime.now().astimezone().isoformat()


# ---------------- Helpers: parsing roll25.json ----------------

def _as_float(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace(",", "")
        if s == "":
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _pick(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return None


def _extract_rows_roll25_json(obj: Any) -> List[Dict[str, Any]]:
    """
    Accepts common shapes:
    - list[dict]
    - {"rows": [...]}
    - {"items": [...]}
    - {"data": [...]}
    """
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("rows", "items", "data"):
            v = obj.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize to:
    - date: str (YYYY-MM-DD)
    - turnover_twd: float (trade value)
    - close: float
    - pct_change_close: float (percent, not fraction)
    - amplitude_pct: float (percent)
    - vol_multiplier_20: float (ratio)
    """
    out: List[Dict[str, Any]] = []

    # We allow multiple possible key names to maximize compatibility.
    date_keys = ["date", "Date", "ymd", "YMD"]
    tv_keys = ["turnover_twd", "trade_value", "TradeValue", "tv", "成交金額", "turnover"]
    close_keys = ["close", "Close", "收盤價"]
    pct_keys = ["pct_change", "PctChange", "pct_change_close", "漲跌幅", "pct"]
    amp_keys = ["amplitude_pct", "AmplitudePct", "振幅", "amplitude"]
    vm_keys = ["vol_multiplier_20", "VolMultiplier", "volume_multiplier", "VolumeMultiplier", "vol_multiplier"]

    for r in rows:
        date = _pick(r, date_keys)
        if not isinstance(date, str) or len(date) < 8:
            continue

        tv = _as_float(_pick(r, tv_keys))
        close = _as_float(_pick(r, close_keys))
        pct = _as_float(_pick(r, pct_keys))
        amp = _as_float(_pick(r, amp_keys))
        vm = _as_float(_pick(r, vm_keys))

        out.append(
            {
                "date": date[:10],
                "turnover_twd": tv,
                "close": close,
                "pct_change_close": pct,
                "amplitude_pct": amp,
                "vol_multiplier_20": vm,
            }
        )

    # Sort by date ascending (chronological)
    out.sort(key=lambda x: x["date"])
    # Dedup by date (keep last occurrence)
    dedup: Dict[str, Dict[str, Any]] = {}
    for r in out:
        dedup[r["date"]] = r
    out2 = [dedup[k] for k in sorted(dedup.keys())]
    return out2


def _compute_pct_change_from_close(rows: List[Dict[str, Any]]) -> None:
    """
    If pct_change_close missing, compute from close.
    pct_change_close = (close_t - close_{t-1}) / abs(close_{t-1}) * 100
    """
    prev_close: Optional[float] = None
    for r in rows:
        c = r.get("close")
        if isinstance(c, (int, float)):
            c = float(c)
        else:
            c = None

        if r.get("pct_change_close") is None and c is not None and prev_close not in (None, 0.0):
            r["pct_change_close"] = (c - float(prev_close)) / abs(float(prev_close)) * 100.0

        if c is not None:
            prev_close = c


def _compute_vol_multiplier_20(rows: List[Dict[str, Any]], min_points: int = 15, win: int = 20) -> None:
    """
    vol_multiplier_20 = today_turnover / avg(turnover_last20)
    Conservative definition:
    - Use trailing window of up to 20 points INCLUDING today.
    - Require at least min_points non-null turnovers in window; else keep None.
    """
    tvs: List[Optional[float]] = [r.get("turnover_twd") if isinstance(r.get("turnover_twd"), (int, float)) else None for r in rows]
    for i in range(len(rows)):
        if rows[i].get("vol_multiplier_20") is not None:
            continue
        tv_i = tvs[i]
        if tv_i is None:
            continue
        start = max(0, i - (win - 1))
        window = [x for x in tvs[start : i + 1] if isinstance(x, (int, float))]
        if len(window) < min_points:
            continue
        avg = sum(float(x) for x in window) / float(len(window))
        if avg != 0:
            rows[i]["vol_multiplier_20"] = float(tv_i) / abs(avg)


# ---------------- Stats: z / percentile ----------------

def _mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / float(len(xs))


def _std_pop(xs: List[float]) -> Optional[float]:
    # ddof=0
    n = len(xs)
    if n <= 0:
        return None
    mu = _mean(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / float(n)
    if var < 0:
        var = 0.0
    return math.sqrt(var)


def _zscore(x: float, xs: List[float]) -> Optional[float]:
    mu = _mean(xs)
    sd = _std_pop(xs)
    if mu is None or sd is None or sd == 0:
        return None
    return (x - mu) / sd


def _percentile_tie_aware(x: float, xs: List[float]) -> Optional[float]:
    n = len(xs)
    if n <= 0:
        return None
    less = sum(1 for v in xs if v < x)
    equal = sum(1 for v in xs if v == x)
    return (less + 0.5 * equal) / float(n) * 100.0


def _fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return f"{float(x):.{nd}f}"
    return "NA"


# ---------------- Window extraction ----------------

def _find_index_by_date(rows: List[Dict[str, Any]], used_date: str) -> Optional[int]:
    for i, r in enumerate(rows):
        if r.get("date") == used_date:
            return i
    return None


def _window_end_at(rows: List[Dict[str, Any]], idx: int, key: str, win: int) -> List[float]:
    start = max(0, idx - (win - 1))
    vals: List[float] = []
    for r in rows[start : idx + 1]:
        v = r.get(key)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    # Important: require full window length (no partial) for comparability
    if len(vals) != win:
        return []
    return vals


def _delta60_value(rows: List[Dict[str, Any]], idx: int, key: str, lag: int = 60) -> Optional[float]:
    if idx - lag < 0:
        return None
    v0 = rows[idx].get(key)
    v1 = rows[idx - lag].get(key)
    if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
        return float(v0) - float(v1)
    return None


def _delta60_series_window(rows: List[Dict[str, Any]], idx: int, key: str, win: int = 60, lag: int = 60) -> List[float]:
    """
    Build a delta series of length=win, ending at idx:
    deltas at t = (x_t - x_{t-lag}) for t in [idx-(win-1) .. idx]
    Requires all points exist.
    """
    out: List[float] = []
    start = idx - (win - 1)
    if start < 0:
        return []
    for t in range(start, idx + 1):
        d = _delta60_value(rows, t, key, lag=lag)
        if d is None:
            return []
        out.append(float(d))
    return out


def _ret1_pct(rows: List[Dict[str, Any]], idx: int, key: str) -> Optional[float]:
    if idx - 1 < 0:
        return None
    v0 = rows[idx].get(key)
    v1 = rows[idx - 1].get(key)
    if not isinstance(v0, (int, float)) or not isinstance(v1, (int, float)):
        return None
    v1f = float(v1)
    if v1f == 0:
        return None
    return (float(v0) - v1f) / abs(v1f) * 100.0


# ---------------- Render ----------------

def build_report(latest: Dict[str, Any], rows: List[Dict[str, Any]], out_path: str) -> None:
    generated_at_utc = _now_utc_z()

    generated_at_local = latest.get("generated_at") if isinstance(latest.get("generated_at"), str) else "NA"
    tz = latest.get("timezone") if isinstance(latest.get("timezone"), str) else "NA"
    summary = latest.get("summary") if isinstance(latest.get("summary"), str) else "NA"

    nums = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sig = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date = nums.get("UsedDate") if isinstance(nums.get("UsedDate"), str) else "NA"
    used_date_status = sig.get("UsedDateStatus") if isinstance(sig.get("UsedDateStatus"), str) else "NA"
    run_day_tag = sig.get("RunDayTag") if isinstance(sig.get("RunDayTag"), str) else "NA"

    turnover = nums.get("TradeValue")
    close = nums.get("Close")
    pct_change = nums.get("PctChange")
    amp = nums.get("AmplitudePct")
    vol_mult = nums.get("VolMultiplier")

    # Locate index for UsedDate to compute windows ending at that date
    idx = _find_index_by_date(rows, used_date) if isinstance(used_date, str) else None

    # Series definitions
    series_defs = [
        ("TURNOVER_TWD", "turnover_twd", turnover),
        ("CLOSE", "close", close),
        ("PCT_CHANGE_CLOSE", "pct_change_close", pct_change),
        ("AMPLITUDE_PCT", "amplitude_pct", amp),
        ("VOL_MULTIPLIER_20", "vol_multiplier_20", vol_mult),
    ]

    # Gating: only these series are allowed to show ret1% and zΔ60/pΔ60
    allow_ret_and_delta = {"TURNOVER_TWD", "CLOSE"}

    # Compute table rows
    table_rows: List[Dict[str, Any]] = []
    for name, key, fallback_value in series_defs:
        row_out: Dict[str, Any] = {"series": name}

        if idx is None:
            # Cannot align to UsedDate; we still show current value from latest_report
            cur = _as_float(fallback_value)
            row_out.update(
                {
                    "value": cur,
                    "z60": None,
                    "p60": None,
                    "z252": None,
                    "p252": None,
                    "zΔ60": None,
                    "pΔ60": None,
                    "ret1%": None,
                    "confidence": "DOWNGRADED",
                }
            )
            table_rows.append(row_out)
            continue

        # Current value from aligned roll25.json if possible, else fallback to latest_report
        cur_val = rows[idx].get(key)
        cur = float(cur_val) if isinstance(cur_val, (int, float)) else _as_float(fallback_value)
        row_out["value"] = cur

        # windows
        w60 = _window_end_at(rows, idx, key, 60)
        w252 = _window_end_at(rows, idx, key, 252)

        z60 = _zscore(cur, w60) if cur is not None and w60 else None
        p60 = _percentile_tie_aware(cur, w60) if cur is not None and w60 else None
        z252 = _zscore(cur, w252) if cur is not None and w252 else None
        p252 = _percentile_tie_aware(cur, w252) if cur is not None and w252 else None

        # deltas & ret1 (gated)
        if name in allow_ret_and_delta:
            dcur = _delta60_value(rows, idx, key, lag=60) if cur is not None else None
            dwin = _delta60_series_window(rows, idx, key, win=60, lag=60) if cur is not None else []
            zD = _zscore(dcur, dwin) if (dcur is not None and dwin) else None
            pD = _percentile_tie_aware(dcur, dwin) if (dcur is not None and dwin) else None
            r1 = _ret1_pct(rows, idx, key)
        else:
            zD = None
            pD = None
            r1 = None

        # confidence: OK only when the stats that should exist (given gating) are all computable
        need_ok = True
        if w60 == [] or w252 == []:
            need_ok = False
        if name in allow_ret_and_delta:
            # require delta window and ret1
            if zD is None or pD is None or r1 is None:
                need_ok = False

        row_out.update(
            {
                "z60": z60,
                "p60": p60,
                "z252": z252,
                "p252": p252,
                "zΔ60": zD,
                "pΔ60": pD,
                "ret1%": r1,
                "confidence": "OK" if need_ok else "DOWNGRADED",
            }
        )
        table_rows.append(row_out)

    # Render markdown
    lines: List[str] = []
    lines.append("# Roll25 Cache Report (TWSE Turnover)")
    lines.append("## 1) Summary")
    lines.append(f"- generated_at_utc: `{generated_at_utc}`")
    lines.append(f"- generated_at_local: `{generated_at_local}`")
    lines.append(f"- timezone: `{tz}`")
    lines.append(f"- UsedDate: `{used_date}`")
    lines.append(f"- UsedDateStatus: `{used_date_status}`")
    lines.append(f"- RunDayTag: `{run_day_tag}`")
    lines.append(f"- summary: {summary}")
    lines.append("")
    lines.append("## 2) Key Numbers (from latest_report.json)")
    lines.append(f"- turnover_twd: `{_fmt(turnover, 0)}`")
    lines.append(f"- close: `{_fmt(close, 2)}`")
    lines.append(f"- pct_change: `{_fmt(pct_change, 6)}`")
    lines.append(f"- amplitude_pct: `{_fmt(amp, 6)}`")
    lines.append(f"- volume_multiplier_20: `{_fmt(vol_mult, 6)}`")
    lines.append("")
    lines.append("## 3) Market Behavior Signals (from latest_report.json)")
    lines.append(f"- DownDay: `{_fmt(sig.get('DownDay'))}`")
    lines.append(f"- VolumeAmplified: `{_fmt(sig.get('VolumeAmplified'))}`")
    lines.append(f"- VolAmplified: `{_fmt(sig.get('VolAmplified'))}`")
    lines.append(f"- NewLow_N: `{_fmt(sig.get('NewLow_N'))}`")
    lines.append(f"- ConsecutiveBreak: `{_fmt(sig.get('ConsecutiveBreak'))}`")
    lines.append("")
    lines.append("## 4) Data Quality Flags (from latest_report.json)")
    lines.append(f"- OhlcMissing: `{_fmt(sig.get('OhlcMissing'))}`")
    lines.append(f"- freshness_ok: `{_fmt(latest.get('freshness_ok'))}`")
    lines.append(f"- ohlc_status: `{_fmt(latest.get('ohlc_status'))}`")
    lines.append(f"- mode: `{_fmt(latest.get('mode'))}`")
    lines.append("")
    lines.append("## 5) Z/P Table (market_cache-like; computed from roll25.json)")
    lines.append("| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in table_rows:
        lines.append(
            "| {series} | {value} | {z60} | {p60} | {z252} | {p252} | {zD} | {pD} | {ret1} | {conf} |".format(
                series=r["series"],
                value=_fmt(r.get("value"), 6),
                z60=_fmt(r.get("z60"), 6),
                p60=_fmt(r.get("p60"), 3),
                z252=_fmt(r.get("z252"), 6),
                p252=_fmt(r.get("p252"), 3),
                zD=_fmt(r.get("zΔ60"), 6),
                pD=_fmt(r.get("pΔ60"), 3),
                ret1=_fmt(r.get("ret1%"), 6),
                conf=r.get("confidence", "NA"),
            )
        )
    lines.append("")
    lines.append("## 6) Audit Notes")
    lines.append("- This report is computed from local files only (no external fetch).")
    lines.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    lines.append("- ret1% and zΔ60/pΔ60 are only computed for TURNOVER_TWD and CLOSE; other series show NA to avoid misleading ratios.")
    lines.append("- If insufficient points for any required window, corresponding stats remain NA and confidence is DOWNGRADED (no guessing).")
    lines.append("")
    lines.append("## 7) Caveats / Sources (from latest_report.json)")
    cav = latest.get("caveats")
    if isinstance(cav, str) and cav.strip():
        lines.append("```")
        lines.append(cav.rstrip())
        lines.append("```")
    else:
        lines.append("```")
        lines.append("NA")
        lines.append("```")

    _write_text(out_path, "\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default="roll25_cache/latest_report.json")
    ap.add_argument("--roll25", default="roll25_cache/roll25.json")
    ap.add_argument("--out", default="roll25_cache/report.md")
    args = ap.parse_args()

    latest = _load_json(args.latest)
    roll25_obj = _load_json(args.roll25)

    rows_raw = _extract_rows_roll25_json(roll25_obj)
    rows = _normalize_rows(rows_raw)

    # Fill missing derived fields conservatively (only if not present)
    _compute_pct_change_from_close(rows)
    _compute_vol_multiplier_20(rows, min_points=15, win=20)

    build_report(latest, rows, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())