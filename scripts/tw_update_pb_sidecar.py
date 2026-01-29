#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TW PB sidecar (monthly PBR history from WantGoo "price-book-river" page)

Source:
- https://www.wantgoo.com/index/0000/price-book-river

Behavior:
- Download full visible monthly table (YYYY/MM pbr ... monthly_close)
- Write:
  - tw_pb_cache/history.json  (rebuild from parsed table; sorted asc; unique by period)
  - tw_pb_cache/latest.json   (latest_month = most recent period row)
- Strict:
  - If fetch/parse fails => latest.json DOWNGRADED; history.json kept as-is (do NOT overwrite)
- Note:
  - The page also shows an intraday PBR at top; we treat this module as "monthly series" for stats.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

TZ = "Asia/Taipei"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SOURCE_URL = "https://www.wantgoo.com/index/0000/price-book-river"

OUT_LATEST = "tw_pb_cache/latest.json"
OUT_HISTORY = "tw_pb_cache/history.json"


@dataclass
class Result:
    fetch_status: str  # OK / DOWNGRADED
    confidence: str    # OK / DOWNGRADED
    dq_reason: Optional[str]
    rows: List[Dict[str, Any]]  # monthly rows (asc)


def _now() -> Dict[str, str]:
    now_local = datetime.now(ZoneInfo(TZ))
    now_utc = now_local.astimezone(timezone.utc)
    return {
        "generated_at_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_at_local": now_local.isoformat(),
        "timezone": TZ,
    }


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def _safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def _ym_to_date(ym: str) -> str:
    # YYYY/MM -> YYYY-MM-01 (monthly series anchor)
    y, m = ym.split("/")
    return f"{y}-{m}-01"


def fetch_and_parse() -> Result:
    try:
        r = requests.get(
            SOURCE_URL,
            headers={"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
            timeout=25,
        )
        if r.status_code != 200:
            return Result("DOWNGRADED", "DOWNGRADED", f"http_{r.status_code}", [])

        html = r.text

        # Lines like:
        # 2025/12 3.03 4779.47 ... 28963.60
        # We capture:
        # - period (YYYY/MM)
        # - pbr (2nd column)
        # - monthly_close (last column)
        pattern = re.compile(
            r"\b(\d{4}/\d{2})\s+([0-9]+(?:\.[0-9]+)?)\s+"
            r"(?:[0-9]+(?:\.[0-9]+)?\s+){6}"  # 0.5x..3x columns
            r"([0-9]+(?:\.[0-9]+)?)\b"        # monthly close (last)
        )

        matches = pattern.findall(html)
        if not matches:
            return Result("DOWNGRADED", "DOWNGRADED", "parse_failed_no_rows", [])

        tmp: Dict[str, Dict[str, Any]] = {}
        for ym, pbr_s, close_s in matches:
            pbr = _safe_float(pbr_s)
            close = _safe_float(close_s)
            if pbr is None or close is None:
                continue
            tmp[ym] = {
                "period_ym": ym,
                "data_date": _ym_to_date(ym),
                "pbr": pbr,
                "monthly_close": close,
                "source_vendor": "wantgoo",
                "source_url": SOURCE_URL,
                "freq": "MONTHLY",
            }

        if not tmp:
            return Result("DOWNGRADED", "DOWNGRADED", "parse_failed_all_rows_invalid", [])

        rows = list(tmp.values())
        rows.sort(key=lambda x: x["period_ym"])  # asc
        return Result("OK", "OK", None, rows)

    except Exception as e:
        return Result("DOWNGRADED", "DOWNGRADED", f"exception:{type(e).__name__}", [])


def main() -> None:
    meta = _now()
    res = fetch_and_parse()

    # If OK: rewrite history from parsed rows (deterministic)
    if res.fetch_status == "OK":
        _write_json(OUT_HISTORY, res.rows)
        latest_row = res.rows[-1]
        latest = {
            "schema_version": "tw_pb_sidecar_latest_v2",
            "script_fingerprint": "tw_update_pb_sidecar_py@v2_monthly_table",
            **meta,
            "source_vendor": "wantgoo",
            "source_url": SOURCE_URL,
            "fetch_status": "OK",
            "confidence": "OK",
            "dq_reason": None,
            "freq": "MONTHLY",
            "data_date": latest_row["data_date"],
            "period_ym": latest_row["period_ym"],
            "pbr": latest_row["pbr"],
            "monthly_close": latest_row["monthly_close"],
            "series_len": len(res.rows),
            "notes": "Monthly series parsed from river table. z/p stats are based on MONTHLY observations.",
        }
        _write_json(OUT_LATEST, latest)
    else:
        # DOWNGRADED: keep history unchanged (do not overwrite)
        if not os.path.exists(OUT_HISTORY):
            _write_json(OUT_HISTORY, [])
        latest = {
            "schema_version": "tw_pb_sidecar_latest_v2",
            "script_fingerprint": "tw_update_pb_sidecar_py@v2_monthly_table",
            **meta,
            "source_vendor": "wantgoo",
            "source_url": SOURCE_URL,
            "fetch_status": "DOWNGRADED",
            "confidence": "DOWNGRADED",
            "dq_reason": res.dq_reason,
            "freq": "MONTHLY",
            "data_date": None,
            "period_ym": None,
            "pbr": None,
            "monthly_close": None,
            "series_len": len(_read_json(OUT_HISTORY, [])),
            "notes": "Fetch/parse failed; history preserved.",
        }
        _write_json(OUT_LATEST, latest)

    print("Wrote:", OUT_LATEST, OUT_HISTORY)


if __name__ == "__main__":
    main()