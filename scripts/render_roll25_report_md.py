#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/latest_report.json + roll25_cache/roll25.json into roll25_cache/report.md

- Market-cache-like Z/P table: z60/p60/z252/p252 + zΔ60/pΔ60 + ret1%
- Column names aligned to market_cache style: zΔ60, pΔ60, ret1%
- NO external fetch. Local files only.
- Conservative NA handling:
  - ret1% + zΔ60/pΔ60 are meaningful only for TURNOVER_TWD and CLOSE.
  - For PCT_CHANGE_CLOSE / AMPLITUDE_PCT / VOL_MULTIPLIER_20, ret1% and zΔ60/pΔ60 => NA (avoid misleading).
- z-score uses population std (ddof=0).
- Percentile is tie-aware: (less + 0.5*equal)/n * 100.
- Formatting improvements:
  - NewLow_N / ConsecutiveBreak as integers when possible
  - Per-series value decimals (TURNOVER 0, CLOSE 2, pct/amp/ratio 6)
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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
    - pct_change_close: float (percent)
    - amplitude_pct: float (percent)
    - vol_multiplier_20: float (ratio)
    """
    out: List[Dict[str, Any]] = []

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

    # Sort by date ascending
    out.sort(key=lambda x: x["date"])

    # Dedup by date (keep last)
    dedup: Dict[str, Dict[str, Any]] = {}
    for r in out:
        dedup[r["date"]] = r
    out2 = [dedup[k] for k in sorted(dedup.keys())]
    return out2


def _compute_pct_change_from_close(rows: List[Dict[str, Any]]) -> None:
    """
    If pct_change_close missing, compute from close:
    pct_change_close = (close_t - close_{t-1}) / abs(close_{t-1}) * 100
    """
    prev_close: Optional[float] = None
    for r in rows:
        c = r.get("close")
        c = float(c) if isinstance(c, (int, float)) else None

        if r.get("pct_change_close") is None and c is not None and prev_close not in (None, 0.0):
            r["pct_change_close"] = (c - float(prev_close)) / abs(float(prev_close)) * 100.0

        if c is not None:
            prev_close = c


def _compute_vol_multiplier_20(rows: List[Dict[str, Any]], min_points: int = 15, win: int = 20) -> None:
    """
    vol_multiplier_20 = today_turnover / avg(turnover_last20)  (including today)
    Require >= min_points non-null in window.
    """
    tvs: List[Optional[float]] = [
        float(r["turnover_twd"]) if isinstance(r.get("turnover_twd"), (int, float)) else None
        for r in rows
    ]
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
    return (sum(xs) / float(len(xs))) if xs else None


def _std_pop(xs: List[float]) -> Optional[float]:
    n = len(xs)
    if n <= 0:
        return None
    mu = _mean(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / float(n)  # ddof=0
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


# ---------------- Formatting ----------------

def _fmt_num(x: Any, nd: int) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return f"{float(x):.{nd}f}"
    return "NA"


def _fmt_intish(x: Any) -> str:
    """
    If numeric and close to integer -> print integer; else fallback to raw/NA.
    """
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if math.isfinite(x) and abs(x - round(x)) < 1e-9:
            return str(int(round(x)))
        return _fmt_num(x, 6)
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return "NA"
        try:
            f = float(s.replace(",", ""))
            if math.isfinite(f) and abs(f - round(f)) < 1e-9:
                return str(int(round(f)))
            return _fmt_num(f, 6)
        except Exception:
            return s
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
    # Require full window to avoid "120 days pretending to be 252"
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

    idx = _find_index_by_date(rows, used_date) if isinstance(used_date, str) else None

    series_defs = [
        ("TURNOVER_TWD", "turnover_twd", turnover, 0),
        ("CLOSE", "close", close, 2),
        ("PCT_CHANGE_CLOSE", "pct_change_close", pct_change, 6),
        ("AMPLITUDE_PCT", "amplitude_pct", amp, 6),
        ("VOL_MULTIPLIER_20", "vol_multiplier_20", vol_mult, 6),
    ]

    # Only these series get ret1% and zΔ60/pΔ60
    allow_ret_and_delta = {"TURNOVER_TWD", "CLOSE"}

    table_rows: List[Dict[str, Any]] = []
    for name, key, fallback_value, value_nd in series_defs:
        row_out: Dict[str, Any] = {"series": name, "value_nd": value_nd}

        if idx is None:
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

        cur_val = rows[idx].get(key)
        cur = float(cur_val) if isinstance(cur_val, (int, float)) else _as_float(fallback_value)
        row_out["value"] = cur

        w60 = _window_end_at(rows, idx, key, 60)
        w252 = _window_end_at(rows, idx, key, 252)

        z60 = _zscore(cur, w60) if cur is not None and w60 else None
        p60 = _percentile_tie_aware(cur, w60) if cur is not None and w60 else None
        z252 = _zscore(cur, w252) if cur is not None and w252 else None
        p252 = _percentile_tie_aware(cur, w252) if cur is not None and w252 else None

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

        # Confidence rule:
        # - Require w60 and w252 for z/p
        # - For gated series, also require zΔ60/pΔ60/ret1%
        need_ok = True
        if not w60 or not w252:
            need_ok = False
        if name in allow_ret_and_delta:
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
    lines.append(f"- turnover_twd: `{_fmt_num(turnover, 0)}`")
    lines.append(f"- close: `{_fmt_num(close, 2)}`")
    lines.append(f"- pct_change: `{_fmt_num(pct_change, 6)}`")
    lines.append(f"- amplitude_pct: `{_fmt_num(amp, 6)}`")
    lines.append(f"- volume_multiplier_20: `{_fmt_num(vol_mult, 6)}`")
    lines.append("")
    lines.append("## 3) Market Behavior Signals (from latest_report.json)")
    lines.append(f"- DownDay: `{_fmt_intish(sig.get('DownDay'))}`")
    lines.append(f"- VolumeAmplified: `{_fmt_intish(sig.get('VolumeAmplified'))}`")
    lines.append(f"- VolAmplified: `{_fmt_intish(sig.get('VolAmplified'))}`")
    lines.append(f"- NewLow_N: `{_fmt_intish(sig.get('NewLow_N'))}`")
    lines.append(f"- ConsecutiveBreak: `{_fmt_intish(sig.get('ConsecutiveBreak'))}`")
    lines.append("")
    lines.append("## 4) Data Quality Flags (from latest_report.json)")
    lines.append(f"- OhlcMissing: `{_fmt_intish(sig.get('OhlcMissing'))}`")
    lines.append(f"- freshness_ok: `{_fmt_intish(latest.get('freshness_ok'))}`")
    lines.append(f"- ohlc_status: `{latest.get('ohlc_status') if isinstance(latest.get('ohlc_status'), str) else 'NA'}`")
    lines.append(f"- mode: `{latest.get('mode') if isinstance(latest.get('mode'), str) else 'NA'}`")
    lines.append("")
    lines.append("## 5) Z/P Table (market_cache-like; computed from roll25.json)")
    lines.append("| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in table_rows:
        vnd = int(r.get("value_nd", 6))
        lines.append(
            "| {series} | {value} | {z60} | {p60} | {z252} | {p252} | {zD} | {pD} | {ret1} | {conf} |".format(
                series=r["series"],
                value=_fmt_num(r.get("value"), vnd) if r.get("value") is not None else "NA",
                z60=_fmt_num(r.get("z60"), 6),
                p60=_fmt_num(r.get("p60"), 3),
                z252=_fmt_num(r.get("z252"), 6),
                p252=_fmt_num(r.get("p252"), 3),
                zD=_fmt_num(r.get("zΔ60"), 6),
                pD=_fmt_num(r.get("pΔ60"), 3),
                ret1=_fmt_num(r.get("ret1%"), 6),
                conf=r.get("confidence", "NA"),
            )
        )
    lines.append("")
    lines.append("## 6) Audit Notes")
    lines.append("- This report is computed from local files only (no external fetch).")
    lines.append("- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).")
    lines.append("- ret1% and zΔ60/pΔ60 are only computed for TURNOVER_TWD and CLOSE; other series show NA to avoid misleading ratios.")
    lines.append("- If insufficient points for any required full window, corresponding stats remain NA and confidence is DOWNGRADED (no guessing).")
    lines.append("")
    lines.append("## 7) Caveats / Sources (from latest_report.json)")
    cav = latest.get("caveats")
    lines.append("```")
    if isinstance(cav, str) and cav.strip():
        lines.append(cav.rstrip())
    else:
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

    _compute_pct_change_from_close(rows)
    _compute_vol_multiplier_20(rows, min_points=15, win=20)

    build_report(latest, rows, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())