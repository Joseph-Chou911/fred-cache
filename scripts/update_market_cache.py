#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
market_cache/update_market_cache.py

Fetch + normalize + compute stats for:
- OFR_FSI (OFR CSV)
- VIX (CBOE VIX_History.csv)
- SP500 (Stooq ^SPX)
- HYG_IEF_RATIO (derived from Stooq HYG.US / IEF.US closes)

Outputs (in market_cache/):
- latest.json
- history_lite.json
- stats_latest.json

Design goals:
- auditable: keep source URLs (ratio keeps both URLs + formula notes)
- no guessing: insufficient window -> NA
- lite history: keep last N points per series (default 400) enough for w252
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen


OUT_DIR = os.path.join("market_cache")
LATEST_PATH = os.path.join(OUT_DIR, "latest.json")
HISTORY_LITE_PATH = os.path.join(OUT_DIR, "history_lite.json")
STATS_LATEST_PATH = os.path.join(OUT_DIR, "stats_latest.json")

SCRIPT_VERSION = "market_cache_v1_stats_zp_w60_w252_ret1_ma60_lite400"
LITE_KEEP_N = int(os.environ.get("LITE_KEEP_N", "400"))

# Primary sources (user-specified)
URL_OFR_FSI = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"
URL_VIX_CBOE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

# Stooq endpoints (CSV download)
def stooq_daily_url(symbol: str) -> str:
    # Examples: ^spx, hyg.us, ief.us
    return f"https://stooq.com/q/d/l/?s={symbol}&i=d"

URL_SPX = stooq_daily_url("^spx")
URL_HYG = stooq_daily_url("hyg.us")
URL_IEF = stooq_daily_url("ief.us")

# Optional fallback for VIX (NOT used unless you enable it)
URL_VIX_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"


@dataclass
class Point:
    date: str  # YYYY-MM-DD
    value: float


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    # best-effort decode
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_csv_points_generic(text: str, date_col_hint: str = "date") -> Tuple[List[Point], List[str]]:
    """
    Parse a CSV where:
    - there is a header row
    - date column is named like 'date' (case-insensitive) OR first column
    - value column is the first non-date numeric-like column (or second column)
    Returns: (points_sorted_asc, header_fields)
    """
    rows = list(csv.reader(text.splitlines()))
    if not rows or len(rows) < 2:
        raise ValueError("CSV has no data rows")

    header = [h.strip() for h in rows[0]]
    header_lc = [h.lower() for h in header]

    # detect date column
    if date_col_hint.lower() in header_lc:
        date_idx = header_lc.index(date_col_hint.lower())
    else:
        date_idx = 0  # fallback

    # detect value column (first non-date column)
    value_idx = None
    for i, h in enumerate(header_lc):
        if i == date_idx:
            continue
        # prefer something that looks like "fsi" / "value" / "close"
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
        # normalize date (expect YYYY-MM-DD)
        if "/" in d:
            # very defensive parse for unexpected formats
            try:
                dt = datetime.strptime(d, "%m/%d/%Y")
                d = dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        pts.append(Point(d, v))

    # sort asc by date (string sort works for YYYY-MM-DD)
    pts.sort(key=lambda x: x.date)
    return pts, header


def parse_stooq_ohlc(text: str) -> List[Point]:
    """
    Stooq CSV download typically includes:
    Date,Open,High,Low,Close,Volume
    We use Close.
    """
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
    # P = count(x_i <= x) / n * 100
    n = len(xs)
    if n == 0:
        return float("nan")
    c = sum(1 for v in xs if v <= x)
    return c / n * 100.0


def window_stats(values: List[Point], w: int) -> Dict[str, object]:
    if len(values) < w:
        return {
            "n": len(values),
            "window": w,
            "start_date": values[0].date if values else None,
            "end_date": values[-1].date if values else None,
            "mean": None,
            "std": None,
            "z": None,
            "p": None,
            "ma": None,
            "dev_ma": None,
        }
    win = values[-w:]
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


def to_lite(values: List[Point], keep_n: int) -> List[Dict[str, object]]:
    v = values[-keep_n:] if len(values) > keep_n else values
    return [{"date": p.date, "value": p.value} for p in v]


def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def main() -> None:
    ensure_out_dir()
    as_of_ts = utc_now_iso()

    # ---- Fetch raw series ----
    # OFR_FSI
    ofr_text = http_get_text(URL_OFR_FSI)
    ofr_pts, ofr_header = parse_csv_points_generic(ofr_text, date_col_hint="date")

    # VIX (CBOE)
    vix_text = http_get_text(URL_VIX_CBOE)
    # CBOE VIX_History.csv header is typically DATE,OPEN,HIGH,LOW,CLOSE
    vix_pts, vix_header = parse_csv_points_generic(vix_text, date_col_hint="date")

    # SP500 via Stooq ^SPX
    spx_text = http_get_text(URL_SPX)
    spx_pts = parse_stooq_ohlc(spx_text)

    # HYG / IEF via Stooq
    hyg_text = http_get_text(URL_HYG)
    ief_text = http_get_text(URL_IEF)
    hyg_pts = parse_stooq_ohlc(hyg_text)
    ief_pts = parse_stooq_ohlc(ief_text)
    ratio_pts = align_ratio(hyg_pts, ief_pts)

    # ---- Build normalized series dict ----
    series_map: Dict[str, Dict[str, object]] = {}

    def add_series(series_id: str, pts: List[Point], source_url: str, extra: Optional[Dict[str, object]] = None) -> None:
        latest = pts[-1]
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
            out.append(Point(d, v))
        out.sort(key=lambda x: x.date)
        return out

    stats_series: Dict[str, object] = {}
    for sid, obj in series_map.items():
        pts = pts_from_lite(obj["history_lite"])  # already lite, but sorted
        latest = pts[-1]
        w60 = window_stats(pts, 60)
        w252 = window_stats(pts, 252)
        stats_series[sid] = {
            "series_id": sid,
            "latest": {
                "data_date": latest.date,
                "value": latest.value,
                "source_url": obj["latest"]["source_url"],
                "as_of_ts": as_of_ts,
            },
            "windows": {
                "w60": {**w60, "ret1": ret1_delta(pts)},
                "w252": {**w252, "ret1": ret1_delta(pts)},
            },
        }
        # carry extra provenance for derived series
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
        "ret1_mode": "delta",
        "series_count": len(stats_series),
        "series": stats_series,
    }
    with open(STATS_LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(stats_obj, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote: {LATEST_PATH}")
    print(f"[OK] wrote: {HISTORY_LITE_PATH}")
    print(f"[OK] wrote: {STATS_LATEST_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERR] {type(e).__name__}: {e}", file=sys.stderr)
        raise