#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TW PB sidecar: TAIEX P/B ratio (PBR) from StatementDog public page (HTML).

Outputs:
- tw_pb_cache/latest.json
- tw_pb_cache/history.json  (upsert by date)
- tw_pb_cache/stats_latest.json (z60/p60/z252/p252 computed from history PBR series)

Design constraints:
- Deterministic, audit-friendly.
- If fetch or parse fails => DOWNGRADED and preserve NA (do NOT guess).
- History is built forward by daily runs. Optional tiny backfill uses "昨日" shown on the page if available.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import requests

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SOURCE_URL = "https://statementdog.com/taiex"
OUTDIR_DEFAULT = "tw_pb_cache"

SCHEMA_LATEST = "tw_pb_latest_v1"
SCHEMA_STATS = "tw_pb_stats_latest_v1"

SCRIPT_FINGERPRINT = "update_tw_pb_sidecar_py@v1"


def now_ts(tz: ZoneInfo) -> Tuple[str, str]:
    utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    local = datetime.now(tz).isoformat()
    return utc, local


def read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def safe_float(s: str) -> Optional[float]:
    try:
        s = s.strip().replace(",", "")
        return float(s)
    except Exception:
        return None


@dataclass
class Parsed:
    data_date: Optional[str]          # YYYY-MM-DD
    close: Optional[float]
    pbr: Optional[float]
    pbr_yesterday: Optional[float]


def parse_statementdog(html: str) -> Parsed:
    # last update: "最後更新：2026/01/29"
    m = re.search(r"最後更新：\s*(\d{4})/(\d{2})/(\d{2})", html)
    data_date = None
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        data_date = f"{y}-{mo}-{d}"

    # close: the page contains:
    # "上市指數收盤" then a number line
    close = None
    m2 = re.search(r"上市指數收盤\s*([\d,]+(?:\.\d+)?)", html)
    if m2:
        close = safe_float(m2.group(1))

    # pbr: "台股股價淨值比" then number then "倍"
    pbr = None
    m3 = re.search(r"台股股價淨值比\s*([\d,]+(?:\.\d+)?)\s*倍", html)
    if m3:
        pbr = safe_float(m3.group(1))

    # yesterday pbr: "昨日 3.43 倍" appears after PBR block; keep it as optional
    pbr_y = None
    m4 = re.search(r"台股股價淨值比.*?昨日\s*([\d,]+(?:\.\d+)?)\s*倍", html, flags=re.S)
    if m4:
        pbr_y = safe_float(m4.group(1))

    return Parsed(data_date=data_date, close=close, pbr=pbr, pbr_yesterday=pbr_y)


def percentile_rank(window: List[float], x: float) -> float:
    # Deterministic inclusive percentile: % of values <= x
    if not window:
        return float("nan")
    le = sum(1 for v in window if v <= x)
    return (le / len(window)) * 100.0


def zscore(window: List[float], x: float) -> Optional[float]:
    # sample std (ddof=1). If std==0 or insufficient => NA
    n = len(window)
    if n < 2:
        return None
    mean = sum(window) / n
    var = sum((v - mean) ** 2 for v in window) / (n - 1)
    if var <= 0:
        return None
    return (x - mean) / (var ** 0.5)


def compute_stats(pbr_series: List[Tuple[str, float]], latest_date: Optional[str]) -> Dict[str, Any]:
    # pbr_series: list of (date, pbr) sorted ascending
    out: Dict[str, Any] = {
        "schema_version": SCHEMA_STATS,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "generated_at_utc": None,
        "generated_at_local": None,
        "timezone": "Asia/Taipei",
        "data_date": latest_date,
        "series_len_pbr": len(pbr_series),
        "z60": None,
        "p60": None,
        "na_reason_60": None,
        "z252": None,
        "p252": None,
        "na_reason_252": None,
        "window_60": {"n": 0, "from": None, "to": None},
        "window_252": {"n": 0, "from": None, "to": None},
    }
    return out


def fill_stats_values(stats: Dict[str, Any], pbr_series: List[Tuple[str, float]]) -> None:
    if not pbr_series:
        stats["na_reason_60"] = "INSUFFICIENT_HISTORY:0/60"
        stats["na_reason_252"] = "INSUFFICIENT_HISTORY:0/252"
        return

    latest_date, latest_pbr = pbr_series[-1]
    stats["data_date"] = latest_date

    def compute_for_window(w: int) -> Tuple[Optional[float], Optional[float], Optional[str], Dict[str, Any]]:
        if len(pbr_series) < w:
            return None, None, f"INSUFFICIENT_HISTORY:{len(pbr_series)}/{w}", {"n": len(pbr_series), "from": pbr_series[0][0], "to": latest_date}
        window = [v for (_, v) in pbr_series[-w:]]
        z = zscore(window, latest_pbr)
        p = percentile_rank(window, latest_pbr)
        return z, p, None, {"n": w, "from": pbr_series[-w][0], "to": latest_date}

    z60, p60, r60, w60meta = compute_for_window(60)
    z252, p252, r252, w252meta = compute_for_window(252)

    stats["z60"] = z60
    stats["p60"] = p60
    stats["na_reason_60"] = r60
    stats["window_60"] = w60meta

    stats["z252"] = z252
    stats["p252"] = p252
    stats["na_reason_252"] = r252
    stats["window_252"] = w252meta


def upsert_history(history: List[Dict[str, Any]], date: str, close: Optional[float], pbr: Optional[float]) -> List[Dict[str, Any]]:
    # remove same date
    history = [r for r in history if r.get("date") != date]
    history.append({"date": date, "close": close, "pbr": pbr})
    history.sort(key=lambda r: r.get("date") or "")
    return history


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--outdir", default=OUTDIR_DEFAULT)
    ap.add_argument("--backfill-days", default="0")
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    outdir = args.outdir
    backfill_days = int(args.backfill_days or "0")

    gen_utc, gen_local = now_ts(tz)

    latest_path = os.path.join(outdir, "latest.json")
    hist_path = os.path.join(outdir, "history.json")
    stats_path = os.path.join(outdir, "stats_latest.json")

    latest: Dict[str, Any] = {
        "schema_version": SCHEMA_LATEST,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "generated_at_utc": gen_utc,
        "generated_at_local": gen_local,
        "timezone": args.tz,
        "source_vendor": "statementdog",
        "source_class": "THIRD_PARTY",
        "source_url": SOURCE_URL,
        "fetch_status": None,
        "confidence": None,
        "dq_reason": None,
        "data_date": None,
        "close": None,
        "pbr": None,
        "notes": [],
    }

    # Fetch
    try:
        resp = requests.get(
            SOURCE_URL,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
                "Connection": "close",
            },
            timeout=20,
        )
        if resp.status_code != 200:
            latest["fetch_status"] = "DOWNGRADED"
            latest["confidence"] = "DOWNGRADED"
            latest["dq_reason"] = f"http_{resp.status_code}"
            write_json(latest_path, latest)
            # keep stats/history unchanged if fetch failed
            if not os.path.exists(hist_path):
                write_json(hist_path, [])
            if not os.path.exists(stats_path):
                write_json(stats_path, compute_stats([], None))
            return
        html = resp.text
    except Exception as e:
        latest["fetch_status"] = "DOWNGRADED"
        latest["confidence"] = "DOWNGRADED"
        latest["dq_reason"] = "fetch_failed"
        latest["notes"].append(str(e))
        write_json(latest_path, latest)
        if not os.path.exists(hist_path):
            write_json(hist_path, [])
        if not os.path.exists(stats_path):
            write_json(stats_path, compute_stats([], None))
        return

    parsed = parse_statementdog(html)

    # Validate parse
    if parsed.data_date is None or parsed.pbr is None:
        latest["fetch_status"] = "DOWNGRADED"
        latest["confidence"] = "DOWNGRADED"
        latest["dq_reason"] = "parse_failed_or_missing_fields"
    else:
        latest["fetch_status"] = "OK"
        latest["confidence"] = "OK"
        latest["dq_reason"] = None

    latest["data_date"] = parsed.data_date
    latest["close"] = parsed.close
    latest["pbr"] = parsed.pbr

    # Load history and upsert
    history = read_json(hist_path, [])
    if not isinstance(history, list):
        history = []

    if parsed.data_date and parsed.pbr is not None:
        history = upsert_history(history, parsed.data_date, parsed.close, parsed.pbr)

    # Tiny backfill (optional): use the "昨日 PBR" as a hint for previous calendar day
    # WARNING: date mapping assumes "昨日" corresponds to previous trading day; if market holidays, it may be wrong.
    # Therefore we only do it when user explicitly asks backfill-days>0 AND we can infer a date safely.
    if backfill_days > 0 and parsed.data_date and parsed.pbr_yesterday is not None:
        try:
            d0 = datetime.strptime(parsed.data_date, "%Y-%m-%d")
            d_prev = (d0 - timedelta(days=1)).strftime("%Y-%m-%d")
            # insert only if not exists
            if all(r.get("date") != d_prev for r in history):
                history = upsert_history(history, d_prev, None, parsed.pbr_yesterday)
        except Exception:
            pass

    write_json(latest_path, latest)
    write_json(hist_path, history)

    # Build pbr_series from history
    pbr_series: List[Tuple[str, float]] = []
    for r in history:
        dt = r.get("date")
        pv = r.get("pbr")
        if isinstance(dt, str) and isinstance(pv, (int, float)):
            pbr_series.append((dt, float(pv)))
    pbr_series.sort(key=lambda x: x[0])

    stats = compute_stats(pbr_series, parsed.data_date)
    stats["generated_at_utc"] = gen_utc
    stats["generated_at_local"] = gen_local
    stats["timezone"] = args.tz
    fill_stats_values(stats, pbr_series)

    write_json(stats_path, stats)


if __name__ == "__main__":
    main()