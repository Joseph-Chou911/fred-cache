#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tw_pb_cache sidecar (Wantgoo, TAIEX/0000):

- Fetch: PBR / PER / Dividend Yield for Taiwan TAIEX index (0000) from Wantgoo page
- Output:
  - tw_pb_cache/latest.json
  - tw_pb_cache/history.json  (upsert by data_date)
- Strict / audit:
  - If fetch/parse fails => latest.json marked DOWNGRADED, history NOT modified
  - Keep source_url, generated_at_utc/local, timezone, dq_reason

NOTE:
- THIRD_PARTY aggregated source (wantgoo). Treat as estimate/vendor aggregated.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from zoneinfo import ZoneInfo

import requests

TZ = "Asia/Taipei"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SOURCE_URL = "https://www.wantgoo.com/index/0000/price-to-earning-river"

OUT_LATEST = "tw_pb_cache/latest.json"
OUT_HISTORY = "tw_pb_cache/history.json"


@dataclass
class FetchResult:
    fetch_status: str  # OK / DOWNGRADED
    confidence: str    # OK / DOWNGRADED
    dq_reason: Optional[str]
    data_date: Optional[str]         # YYYY-MM-DD
    data_time_local: Optional[str]   # HH:MM
    per: Optional[float]
    dividend_yield: Optional[float]
    pbr: Optional[float]


def _now(ts_tz: str) -> Dict[str, str]:
    tzinfo = ZoneInfo(ts_tz)
    now_local = datetime.now(tzinfo)
    now_utc = now_local.astimezone(timezone.utc)
    return {
        "generated_at_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_at_local": now_local.isoformat(),
        "timezone": ts_tz,
    }


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def fetch_wantgoo() -> FetchResult:
    try:
        resp = requests.get(
            SOURCE_URL,
            headers={"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
            timeout=20,
        )
        if resp.status_code != 200:
            return FetchResult("DOWNGRADED", "DOWNGRADED", f"http_{resp.status_code}", None, None, None, None, None)

        html = resp.text

        # Parse snippet like:
        # "0000 2026-01-29 13:30 ... 本益比23.22 ... 殖利率2.36 ... 股淨比3.03"
        m_dt = re.search(r"\b0000\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\b", html)
        m_per = re.search(r"本益比\s*([0-9]+(?:\.[0-9]+)?)", html)
        m_yld = re.search(r"殖利率\s*([0-9]+(?:\.[0-9]+)?)", html)
        m_pbr = re.search(r"股淨比\s*([0-9]+(?:\.[0-9]+)?)", html)

        if not (m_dt and m_per and m_yld and m_pbr):
            return FetchResult("DOWNGRADED", "DOWNGRADED", "parse_failed", None, None, None, None, None)

        data_date = m_dt.group(1)
        data_time_local = m_dt.group(2)
        per = _safe_float(m_per.group(1))
        dividend_yield = _safe_float(m_yld.group(1))
        pbr = _safe_float(m_pbr.group(1))

        if per is None or dividend_yield is None or pbr is None:
            return FetchResult("DOWNGRADED", "DOWNGRADED", "numeric_cast_failed", None, None, None, None, None)

        return FetchResult("OK", "OK", None, data_date, data_time_local, per, dividend_yield, pbr)

    except Exception as e:
        return FetchResult("DOWNGRADED", "DOWNGRADED", f"exception:{type(e).__name__}", None, None, None, None, None)


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def upsert_history(history: List[Dict[str, Any]], row: Dict[str, Any]) -> List[Dict[str, Any]]:
    dd = row.get("data_date")
    if not dd:
        return history

    by_date: Dict[str, Dict[str, Any]] = {r.get("data_date"): r for r in history if r.get("data_date")}
    by_date[dd] = row
    out = list(by_date.values())
    out.sort(key=lambda r: r["data_date"])
    return out


def main() -> None:
    meta = _now(TZ)
    r = fetch_wantgoo()

    latest = {
        "schema_version": "tw_pb_sidecar_latest_v1",
        "script_fingerprint": "tw_update_pb_sidecar_py@v1",
        **meta,
        "source_vendor": "wantgoo",
        "source_url": SOURCE_URL,
        "fetch_status": r.fetch_status,
        "confidence": r.confidence,
        "dq_reason": r.dq_reason,
        "data_date": r.data_date,
        "data_time_local": r.data_time_local,
        "per": r.per,
        "dividend_yield_pct": r.dividend_yield,
        "pbr": r.pbr,
        "notes": "THIRD_PARTY aggregated indicator; for research only.",
    }

    _write_json(OUT_LATEST, latest)

    # Only update history when OK and data_date exists
    if r.fetch_status == "OK" and r.data_date:
        hist = _read_json(OUT_HISTORY, default=[])
        row = {
            "data_date": r.data_date,
            "data_time_local": r.data_time_local,
            "per": r.per,
            "dividend_yield_pct": r.dividend_yield,
            "pbr": r.pbr,
            "source_vendor": "wantgoo",
        }
        hist2 = upsert_history(hist, row)
        _write_json(OUT_HISTORY, hist2)
    else:
        # keep history unchanged; if missing, initialize empty
        if not os.path.exists(OUT_HISTORY):
            _write_json(OUT_HISTORY, [])

    print("Wrote:", OUT_LATEST, OUT_HISTORY)


if __name__ == "__main__":
    main()