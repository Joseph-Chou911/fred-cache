#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "regime_inputs_cache"

CONFIG_PATH = OUT_DIR / "inputs_config.json"
LATEST_PATH = OUT_DIR / "inputs_latest.json"
HIST_LITE_PATH = OUT_DIR / "inputs_history_lite.json"
SCHEMA_PATH = OUT_DIR / "inputs_schema.json"
DQ_PATH = OUT_DIR / "dq_state.json"

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def parse_date_yyyy_mm_dd(s: str) -> str:
    # Normalize to YYYY-MM-DD; raise on failure
    s = s.strip()
    # Common cases
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {s}")

def safe_float(x: str) -> float:
    x = x.strip()
    # allow commas
    x = x.replace(",", "")
    return float(x)

def http_get_text(url: str, timeout: int) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "regime_inputs_cache/1.0 (+https://github.com/)"
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # Try utf-8; fallback latin-1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")

def fetch_stooq_daily(symbol: str, timeout: int) -> Tuple[str, float, str]:
    # https://stooq.com/q/d/l/?s=hyg.us&i=d
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    text = http_get_text(url, timeout=timeout)
    rows = list(csv.DictReader(text.splitlines()))
    # stooq returns ascending dates; take last non-empty close
    rows = [r for r in rows if r.get("Date") and r.get("Close")]
    if not rows:
        raise RuntimeError("No rows found in Stooq response")
    last = rows[-1]
    data_date = parse_date_yyyy_mm_dd(last["Date"])
    value = safe_float(last["Close"])
    return data_date, value, url

def fetch_csv_max_date(url: str, date_col: str, value_col: str, timeout: int) -> Tuple[str, float, str]:
    text = http_get_text(url, timeout=timeout)
    reader = csv.DictReader(text.splitlines())
    best_date: Optional[str] = None
    best_value: Optional[float] = None
    for row in reader:
        if not row:
            continue
        if date_col not in row or value_col not in row:
            # allow case-insensitive matching
            keys = {k.lower(): k for k in row.keys() if k}
            dc = keys.get(date_col.lower())
            vc = keys.get(value_col.lower())
            if not dc or not vc:
                continue
            d_raw = row.get(dc, "")
            v_raw = row.get(vc, "")
        else:
            d_raw = row.get(date_col, "")
            v_raw = row.get(value_col, "")
        if not d_raw or not v_raw:
            continue
        try:
            d = parse_date_yyyy_mm_dd(d_raw)
            v = safe_float(v_raw)
        except Exception:
            continue
        if (best_date is None) or (d > best_date):
            best_date, best_value = d, v
    if best_date is None or best_value is None:
        raise RuntimeError("Failed to find (date,value) in CSV")
    return best_date, best_value, url

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def write_json_atomic(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def dedup_preserve_order(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for r in records:
        key = (r.get("series_id"), r.get("data_date"), r.get("value"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def calc_staleness_days(data_date: str, now_utc: datetime) -> Optional[int]:
    try:
        d = datetime.strptime(data_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        delta = now_utc - d
        return int(delta.total_seconds() // 86400)
    except Exception:
        return None

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cfg = load_json(CONFIG_PATH, None)
    if not cfg:
        raise SystemExit(f"Missing config: {CONFIG_PATH}")

    as_of_ts = utc_now_iso()
    now_dt = datetime.now(timezone.utc)

    latest: Dict[str, Any] = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": "regime_inputs_cache_v1",
        "series": {}
    }

    dq: Dict[str, Any] = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "script_version": "regime_inputs_cache_v1",
        "status": "OK",
        "errors": [],
        "warnings": [],
        "per_series": {}
    }

    history: List[Dict[str, Any]] = load_json(HIST_LITE_PATH, default=[])

    for s in cfg.get("series", []):
        series_id = s.get("series_id")
        fetcher = s.get("fetcher")
        timeout = int(cfg.get("default_timeout_sec", 20))
        expected_max = s.get("expected_max_staleness_days", None)

        entry = {
            "series_id": series_id,
            "data_date": None,
            "value": None,
            "source_url": None,
            "as_of_ts": as_of_ts,
            "notes": None
        }

        per = {
            "ok": False,
            "fetcher": fetcher,
            "data_date": None,
            "value": None,
            "source_url": None,
            "staleness_days": None,
            "expected_max_staleness_days": expected_max,
            "error": None
        }

        try:
            if fetcher == "stooq_daily":
                symbol = s["symbol"]
                data_date, value, source_url = fetch_stooq_daily(symbol, timeout)
            elif fetcher == "csv_max_date":
                url = s["url"]
                date_col = s["date_col"]
                value_col = s["value_col"]
                data_date, value, source_url = fetch_csv_max_date(url, date_col, value_col, timeout)
            else:
                raise RuntimeError(f"Unsupported fetcher: {fetcher}")

            entry.update({
                "data_date": data_date,
                "value": value,
                "source_url": source_url
            })
            per.update({
                "ok": True,
                "data_date": data_date,
                "value": value,
                "source_url": source_url
            })

            staleness = calc_staleness_days(data_date, now_dt)
            per["staleness_days"] = staleness

            if expected_max is not None and staleness is not None and staleness > int(expected_max):
                dq["status"] = "WARN" if dq["status"] == "OK" else dq["status"]
                msg = f"{series_id} staleness_days={staleness} > expected_max={expected_max}"
                dq["warnings"].append(msg)

        except Exception as e:
            dq["status"] = "ERR"
            err = f"{series_id} fetch failed: {type(e).__name__}: {e}"
            dq["errors"].append(err)
            entry["notes"] = "ERR:fetch_failed"
            per["error"] = err

        latest["series"][series_id] = entry
        dq["per_series"][series_id] = per

        # Append to history even if value is None (auditable); but tag notes
        history.append({
            "series_id": series_id,
            "data_date": entry["data_date"],
            "value": entry["value"],
            "source_url": entry["source_url"],
            "as_of_ts": as_of_ts,
            "notes": entry["notes"]
        })

    # Dedup and write
    history = dedup_preserve_order(history)

    schema = {
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "schema_version": "inputs_schema_v1",
        "fields": ["series_id", "data_date", "value", "source_url", "as_of_ts", "notes"],
        "series_list": [s.get("series_id") for s in cfg.get("series", [])]
    }

    write_json_atomic(LATEST_PATH, latest)
    write_json_atomic(HIST_LITE_PATH, history)
    write_json_atomic(DQ_PATH, dq)
    write_json_atomic(SCHEMA_PATH, schema)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())