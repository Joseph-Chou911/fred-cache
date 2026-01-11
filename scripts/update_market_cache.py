#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
market_cache/update_market_cache.py (enhanced)

Fetch + normalize + compute stats for:
- OFR_FSI (OFR CSV)
- VIX (CBOE VIX_History.csv)
- SP500 (Stooq ^SPX)
- HYG_IEF_RATIO (derived from Stooq HYG.US / IEF.US closes)

Outputs (in market_cache/):
- latest.json
- history_lite.json
- stats_latest.json
- dq_state.json  (NEW)

Stats:
- w60 / w252: mean, std(ddof=0), z, p, ma, dev_ma, ret1_delta, ret1_pct (NEW)
- z60_delta / p60_delta, z252_delta / p252_delta (NEW): computed by re-evaluating stats at t and t-1

Design goals:
- auditable: keep source URLs (ratio keeps both URLs + formula notes)
- no guessing: insufficient window -> NA
- lite history: keep last N points per series (default 400) enough for w252
- quality gating: dq_state.json to prevent bad/old data from poisoning downstream
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, date as date_cls
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen


OUT_DIR = os.path.join("market_cache")
LATEST_PATH = os.path.join(OUT_DIR, "latest.json")
HISTORY_LITE_PATH = os.path.join(OUT_DIR, "history_lite.json")
STATS_LATEST_PATH = os.path.join(OUT_DIR, "stats_latest.json")
DQ_STATE_PATH = os.path.join(OUT_DIR, "dq_state.json")

SCRIPT_VERSION = "market_cache_v2_stats_zp_w60_w252_ret1_delta_pct_deltas_dq_lite400"
LITE_KEEP_N = int(os.environ.get("LITE_KEEP_N", "400"))

# Primary sources (user-specified)
URL_OFR_FSI = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"
URL_VIX_CBOE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

# Stooq endpoints (CSV download)
def stooq_daily_url(symbol: str) -> str:
    return f"https://stooq.com/q/d/l/?s={symbol}&i=d"

URL_SPX = stooq_daily_url("^spx")
URL_HYG = stooq_daily_url("hyg.us")
URL_IEF = stooq_daily_url("ief.us")


@dataclass
class Point:
    date: str  # YYYY-MM-DD
    value: float


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_yyyy_mm_dd(s: str) -> Optional[date_cls]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def days_stale(latest_date: str, as_of_utc: str) -> Optional[int]:
    d = parse_yyyy_mm_dd(latest_date)
    if not d:
        return None
    # as_of_utc is ISO Z
    try:
        as_of_dt = datetime.strptime(as_of_utc, "%Y-%m-%dT%H:%M:%SZ").date()
    except Exception:
        return None
    return (as_of_dt - d).days


def http_get_text(url: str, timeout: int = 30) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; market_cache/1.0; +https://github.com/)",
            "Accept": "text/csv,text/plain,*/*",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_csv_points_generic(text: str, date_col_hint: str = "date") -> Tuple[List[Point], List[str], str]:
    """
    Parse a CSV with header:
    - date column name includes date_col_hint (case-insensitive) else first column
    - value column: prefer header containing fsi/value/close; else second column
    Returns: (points_sorted_asc, header_fields, value_col_name)
    """
    rows = list(csv.reader(text.splitlines()))
    if not rows or len(rows) < 2:
        raise ValueError("CSV has no data rows")

    header = [h.strip() for h in rows[0]]
    header_lc = [h.lower() for h in header]

    # date col
    if date_col_hint.lower() in header_lc:
        date_idx = header_lc.index(date_col_hint.lower())
    else:
        date_idx = 0

    # value col
    value_idx = None
    for i, h in enumerate(header_lc):
        if i == date_idx:
            continue
        if any(k in h for k in ("fsi", "value", "close")):
            value_idx = i
            break
    if value_idx is None:
        value_idx = 1 if len(header) > 1 else None
    if value_idx is None:
        raise ValueError("Cannot find value column")

    pts: List[Point] = []
    for r in rows[1:]:
        if len(r) <= max(date_idx, value_idx):
            continue
        d = r[date_idx].strip()
        v_str = r[value_idx].strip()
        if not d or not v_str:
            continue
        try:
            v = float(v_str)
        except Exception:
            continue

        # normalize possible MM/DD/YYYY
        if "/" in d and len(d) <= 10:
            try:
                dt = datetime.strptime(d, "%m/%d/%Y")
                d = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        if parse_yyyy_mm_dd(d) is None:
            continue

        pts.append(Point(d, v))

    pts.sort(key=lambda x: x.date)
    if len(pts) < 10:
        raise ValueError("CSV: too few usable rows after parsing")
    return pts, header, header[value_idx]


def parse_stooq_ohlc(text: str) -> List[Point]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("Stooq CSV: missing header")

    fn = [f.strip() for f in reader.fieldnames]
    fn_lc = [f.lower() for f in fn]

    if "date" not in fn_lc:
        raise ValueError(f"Stooq CSV: missing Date column: {fn}")
    if "close" not in fn_lc:
        raise ValueError(f"Stooq CSV: missing Close column: {fn}")

    pts: List[Point] = []
    for row in reader:
        d = (row.get("Date") or row.get("date") or "").strip()
        c = (row.get("Close") or row.get("close") or "").strip()
        if not d or not c:
            continue
        if parse_yyyy_mm_dd(d) is None:
            continue
        try:
            v = float(c)
        except Exception:
            continue
        pts.append(Point(d, v))

    pts.sort(key=lambda x: x.date)
    if len(pts) < 10:
        raise ValueError("Stooq CSV: too few rows (symbol may be wrong or blocked)")
    return pts


def align_ratio(hyg: List[Point], ief: List[Point]) -> List[Point]:
    m_h = {p.date: p.value for p in hyg}
    m_i = {p.date: p.value for p in ief}
    common = sorted(set(m_h.keys()).intersection(m_i.keys()))
    out: List[Point] = []
    for d in common:
        denom = m_i[d]
        if denom == 0:
            continue
        out.append(Point(d, m_h[d] / denom))
    if len(out) < 10:
        raise ValueError("HYG/IEF ratio: too few aligned points")
    return out


def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs)


def std_ddof0(xs: List[float]) -> float:
    mu = mean(xs)
    var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return math.sqrt(var)


def percentile_le(xs: List[float], x: float) -> float:
    n = len(xs)
    if n == 0:
        return float("nan")
    c = sum(1 for v in xs if v <= x)
    return c / n * 100.0


def window_stats_at(values: List[Point], w: int, idx: int) -> Dict[str, object]:
    """
    Compute window stats ending at values[idx] (inclusive).
    idx must be within list.
    """
    if idx < 0 or idx >= len(values):
        raise IndexError("idx out of range")

    end = idx + 1
    start = end - w
    if start < 0:
        # insufficient window
        return {
            "n": end,
            "window": w,
            "start_date": values[0].date,
            "end_date": values[idx].date,
            "mean": None,
            "std": None,
            "z": None,
            "p": None,
            "ma": None,
            "dev_ma": None,
        }
    win = values[start:end]
    xs = [p.value for p in win]
    x = xs[-1]
    mu = mean(xs)
    sd = std_ddof0(xs)
    z = None if sd == 0 else (x - mu) / sd
    p = percentile_le(xs, x)
    ma = mu
    dev = x - ma
    return {
        "n": w,
        "window": w,
        "start_date": win[0].date,
        "end_date": win[-1].date,
        "mean": mu,
        "std": sd,
        "z": z,
        "p": p,
        "ma": ma,
        "dev_ma": dev,
    }


def ret1_delta(values: List[Point]) -> Optional[float]:
    if len(values) < 2:
        return None
    return values[-1].value - values[-2].value


def ret1_pct(values: List[Point]) -> Optional[float]:
    if len(values) < 2:
        return None
    prev = values[-2].value
    if prev == 0:
        return None
    return (values[-1].value / prev - 1.0) * 100.0


def to_lite(values: List[Point], keep_n: int) -> List[Dict[str, object]]:
    v = values[-keep_n:] if len(values) > keep_n else values
    return [{"date": p.date, "value": p.value} for p in v]


def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def main() -> None:
    ensure_out_dir()
    as_of_ts = utc_now_iso()

    dq_checks: List[Dict[str, object]] = []
    dq_overall = "OK"

    def add_check(series_id: str, check: str, status: str, **kwargs) -> None:
        nonlocal dq_overall
        item = {"series_id": series_id, "check": check, "status": status}
        item.update(kwargs)
        dq_checks.append(item)
        if status == "ERR":
            dq_overall = "ERR"
        elif status == "WARN" and dq_overall != "ERR":
            dq_overall = "WARN"

    # ---- Fetch + parse series ----
    # OFR_FSI
    ofr_text = http_get_text(URL_OFR_FSI)
    ofr_pts, ofr_header, ofr_valcol = parse_csv_points_generic(ofr_text, date_col_hint="date")
    add_check("OFR_FSI", "csv_value_col", "OK", value_col=ofr_valcol)

    # VIX (CBOE)
    vix_text = http_get_text(URL_VIX_CBOE)
    vix_pts, vix_header, vix_valcol = parse_csv_points_generic(vix_text, date_col_hint="date")
    add_check("VIX", "csv_value_col", "OK", value_col=vix_valcol)

    # SP500 via Stooq ^SPX
    spx_text = http_get_text(URL_SPX)
    spx_pts = parse_stooq_ohlc(spx_text)
    add_check("SP500", "stooq_has_close", "OK")

    # HYG / IEF via Stooq
    hyg_text = http_get_text(URL_HYG)
    ief_text = http_get_text(URL_IEF)
    hyg_pts = parse_stooq_ohlc(hyg_text)
    ief_pts = parse_stooq_ohlc(ief_text)
    ratio_pts = align_ratio(hyg_pts, ief_pts)
    add_check("HYG_IEF_RATIO", "aligned_points", "OK", n=len(ratio_pts))

    # ---- Build normalized series dict ----
    series_map: Dict[str, Dict[str, object]] = {}

    def add_series(series_id: str, pts: List[Point], source_url: str, extra: Optional[Dict[str, object]] = None) -> None:
        latest = pts[-1]
        stale = days_stale(latest.date, as_of_ts)
        if stale is None:
            add_check(series_id, "latest_date_parseable", "ERR", latest_date=latest.date)
        else:
            # conservative threshold: >5 calendar days => WARN
            if stale > 5:
                add_check(series_id, "staleness_days", "WARN", staleness_days=stale, latest_date=latest.date)
            else:
                add_check(series_id, "staleness_days", "OK", staleness_days=stale, latest_date=latest.date)

        series_map[series_id] = {
            "series_id": series_id,
            "latest": {
                "data_date": latest.date,
                "value": latest.value,
                "source_url": source_url,
                "as_of_ts": as_of_ts,
            },
            "history_lite": to_lite(pts, LITE_KEEP_N),
        }
        if extra:
            series_map[series_id]["latest"].update(extra)

    add_series("OFR_FSI", ofr_pts, URL_OFR_FSI, extra={"parse_header": ofr_header})
    add_series("VIX", vix_pts, URL_VIX_CBOE, extra={"parse_header": vix_header})
    add_series("SP500", spx_pts, URL_SPX)
    add_series(
        "HYG_IEF_RATIO",
        ratio_pts,
        "DERIVED",
        extra={
            "sources": [URL_HYG, URL_IEF],
            "formula": "HYG_close / IEF_close (aligned by same trading date)",
        },
    )

    # ---- Output latest.json ----
    latest_obj = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": SCRIPT_VERSION,
        "series": {k: v["latest"] for k, v in series_map.items()},
    }
    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(latest_obj, f, ensure_ascii=False, indent=2)

    # ---- Output history_lite.json ----
    history_obj = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": SCRIPT_VERSION,
        "lite_keep_n": LITE_KEEP_N,
        "series": {k: v["history_lite"] for k, v in series_map.items()},
    }
    with open(HISTORY_LITE_PATH, "w", encoding="utf-8") as f:
        json.dump(history_obj, f, ensure_ascii=False, indent=2)

    # ---- Compute stats_latest.json ----
    def pts_from_lite(lite: List[Dict[str, object]]) -> List[Point]:
        out = []
        for r in lite:
            d = str(r["date"])
            v = float(r["value"])
            if parse_yyyy_mm_dd(d) is None:
                continue
            out.append(Point(d, v))
        out.sort(key=lambda x: x.date)
        return out

    stats_series: Dict[str, object] = {}
    for sid, obj in series_map.items():
        pts = pts_from_lite(obj["history_lite"])
        if len(pts) < 2:
            add_check(sid, "min_points>=2", "ERR", n=len(pts))
            continue

        latest = pts[-1]
        prev = pts[-2]

        # window stats at latest (idx=-1) and prev (idx=-2) to get deltas
        idx_latest = len(pts) - 1
        idx_prev = len(pts) - 2

        w60_now = window_stats_at(pts, 60, idx_latest)
        w60_prev = window_stats_at(pts, 60, idx_prev)
        w252_now = window_stats_at(pts, 252, idx_latest)
        w252_prev = window_stats_at(pts, 252, idx_prev)

        # deltas (only if both available)
        def delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
            if a is None or b is None:
                return None
            return a - b

        z60_delta = delta(w60_now.get("z"), w60_prev.get("z"))
        p60_delta = delta(w60_now.get("p"), w60_prev.get("p"))
        z252_delta = delta(w252_now.get("z"), w252_prev.get("z"))
        p252_delta = delta(w252_now.get("p"), w252_prev.get("p"))

        r1d = latest.value - prev.value
        r1p = ret1_pct(pts)

        # bad-tick check using w60 std (if available)
        std60 = w60_now.get("std")
        if isinstance(std60, (int, float)) and std60 not in (0, None):
            if abs(r1d) > 8.0 * float(std60):
                add_check(sid, "bad_tick_ret1_delta_vs_std60", "WARN", ret1_delta=r1d, std60=std60, threshold="8*std60")
            else:
                add_check(sid, "bad_tick_ret1_delta_vs_std60", "OK", ret1_delta=r1d, std60=std60, threshold="8*std60")

        # pack windows + new fields
        w60_out = dict(w60_now)
        w60_out.update({
            "ret1_delta": r1d,
            "ret1_pct": r1p,
            "z_delta": z60_delta,
            "p_delta": p60_delta,
        })

        w252_out = dict(w252_now)
        w252_out.update({
            "ret1_delta": r1d,
            "ret1_pct": r1p,
            "z_delta": z252_delta,
            "p_delta": p252_delta,
        })

        stats_series[sid] = {
            "series_id": sid,
            "latest": {
                "data_date": latest.date,
                "value": latest.value,
                "source_url": obj["latest"]["source_url"],
                "as_of_ts": as_of_ts,
            },
            "windows": {
                "w60": w60_out,
                "w252": w252_out,
            },
        }

        # provenance for derived series
        if sid == "HYG_IEF_RATIO":
            stats_series[sid]["latest"]["sources"] = obj["latest"].get("sources")
            stats_series[sid]["latest"]["formula"] = obj["latest"].get("formula")

    stats_obj = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": SCRIPT_VERSION,
        "windows": {"w60": 60, "w252": 252},
        "std_ddof": 0,
        "percentile_method": "P = count(x<=latest)/n * 100",
        "ret1_mode": "delta+percent",
        "series_count": len(stats_series),
        "series": stats_series,
    }
    with open(STATS_LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(stats_obj, f, ensure_ascii=False, indent=2)

    # ---- Output dq_state.json ----
    dq_obj = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": SCRIPT_VERSION,
        "dq": dq_overall,
        "checks": dq_checks,
    }
    with open(DQ_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(dq_obj, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote: {LATEST_PATH}")
    print(f"[OK] wrote: {HISTORY_LITE_PATH}")
    print(f"[OK] wrote: {STATS_LATEST_PATH}")
    print(f"[OK] wrote: {DQ_STATE_PATH}")
    print(f"[DQ] overall={dq_overall} checks={len(dq_checks)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERR] {type(e).__name__}: {e}", file=sys.stderr)
        raise