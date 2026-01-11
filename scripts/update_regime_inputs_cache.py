#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regime_inputs_cache updater (standalone)

Outputs:
- regime_inputs_cache/latest.json
- regime_inputs_cache/history_lite.json
- regime_inputs_cache/dq_state.json
- regime_inputs_cache/inputs_schema_out.json  (frozen, for downstream audit)

Design goals:
- Serial fetch (no parallel)
- Retry with backoff: 2s -> 4s -> 8s
- No guessing: if required columns not found, mark ERR for that series
- Auditable notes: record CSV header + chosen date/value columns + row counts
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "regime_inputs_cache"

SCHEMA_IN = OUT_DIR / "inputs_schema.json"
LATEST_OUT = OUT_DIR / "latest.json"
HISTORY_OUT = OUT_DIR / "history_lite.json"
DQ_OUT = OUT_DIR / "dq_state.json"
SCHEMA_OUT = OUT_DIR / "inputs_schema_out.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_taipei(dt: datetime) -> str:
    if ZoneInfo is None:
        # fallback: still output UTC if zoneinfo missing
        return iso_z(dt)
    return dt.astimezone(ZoneInfo("Asia/Taipei")).isoformat()


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def http_get_text(url: str, timeout_sec: int) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "regime_inputs_cache/1.0 (+https://github.com/)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read()
    # Try utf-8, fallback latin-1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def retry_fetch(url: str, timeout_sec: int, backoff: List[int]) -> str:
    last_err: Optional[Exception] = None
    for i, wait_s in enumerate([0] + backoff):
        if wait_s:
            time.sleep(wait_s)
        try:
            return http_get_text(url, timeout_sec=timeout_sec)
        except Exception as e:
            last_err = e
            # continue retry
    raise RuntimeError(f"fetch_failed after retries: {type(last_err).__name__}: {last_err}")  # type: ignore[arg-type]


def normalize_date(s: str, fmts: List[str]) -> str:
    s = (s or "").strip()
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    raise ValueError(f"unsupported date format: {s}")


def safe_float(x: str) -> float:
    x = (x or "").strip().replace(",", "")
    return float(x)


def pick_column(header: List[str], candidates: List[str], kind: str) -> Optional[str]:
    # exact match (case-insensitive) first
    lower_map = {h.lower(): h for h in header}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    # heuristic fallback: contains keyword (for OFR FSI)
    if kind == "date":
        for h in header:
            if "date" in h.lower():
                return h
    if kind == "value":
        for h in header:
            lh = h.lower()
            if ("fsi" in lh) and ("date" not in lh):
                return h
    return None


def parse_csv_latest_by_max_date(
    csv_text: str,
    date_col: str,
    value_col: str,
    date_formats: List[str],
) -> Tuple[str, float, int]:
    """
    Returns: (max_data_date, value_at_max_date, parsed_row_count)
    Strategy: scan all rows; choose the row with lexicographically largest normalized date.
    """
    reader = csv.DictReader(csv_text.splitlines())
    rows = 0
    best_date: Optional[str] = None
    best_value: Optional[float] = None

    for r in reader:
        if not r:
            continue
        rows += 1
        d_raw = r.get(date_col, "")
        v_raw = r.get(value_col, "")
        if not d_raw or not v_raw:
            continue
        try:
            d = normalize_date(d_raw, date_formats)
            v = safe_float(v_raw)
        except Exception:
            continue
        if (best_date is None) or (d > best_date):
            best_date, best_value = d, v

    if best_date is None or best_value is None:
        raise RuntimeError("no valid (date,value) rows after parsing")
    return best_date, best_value, rows


def staleness_days(data_date: str, now_utc: datetime) -> Optional[int]:
    try:
        d = datetime.strptime(data_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int((now_utc - d).total_seconds() // 86400)
    except Exception:
        return None


def dedup_preserve_order(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in history:
        key = (r.get("series_id"), r.get("data_date"), r.get("value"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main() -> int:
    now = utc_now()
    run_utc = iso_z(now)
    run_taipei = iso_taipei(now)

    schema = load_json(SCHEMA_IN, None)
    if not schema:
        raise SystemExit(f"Missing inputs schema: {SCHEMA_IN}")

    defaults = schema.get("defaults", {})
    timeout_sec = int(defaults.get("timeout_sec", 25))
    backoff = defaults.get("backoff_seconds", [2, 4, 8])
    if not isinstance(backoff, list) or not backoff:
        backoff = [2, 4, 8]

    # load existing history (lite)
    history: List[Dict[str, Any]] = load_json(HISTORY_OUT, default=[])

    latest_obj: Dict[str, Any] = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_taipei,
        "script_version": "regime_inputs_cache_v1",
        "series": {}
    }

    dq: Dict[str, Any] = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_taipei,
        "script_version": "regime_inputs_cache_v1",
        "status": "OK",
        "errors": [],
        "warnings": [],
        "per_series": {}
    }

    for s in schema.get("series", []):
        series_id = s.get("series_id")
        url = s.get("url")
        date_candidates = s.get("date_col_candidates", [])
        value_candidates = s.get("value_col_candidates", [])
        date_formats = s.get("date_formats", ["%Y-%m-%d"])
        expected_max = s.get("expected_max_staleness_days", None)

        entry = {
            "series_id": series_id,
            "data_date": None,
            "value": None,
            "source_url": url,
            "as_of_ts": run_taipei,
            "notes": None
        }

        per = {
            "ok": False,
            "source_url": url,
            "http": {"retried": True, "timeout_sec": timeout_sec, "backoff_seconds": backoff},
            "csv": {"header": None, "date_col": None, "value_col": None, "parsed_rows": None},
            "data_date": None,
            "value": None,
            "staleness_days": None,
            "expected_max_staleness_days": expected_max,
            "error": None
        }

        try:
            if not url:
                raise RuntimeError("missing url")

            csv_text = retry_fetch(url, timeout_sec=timeout_sec, backoff=backoff)

            # Parse header
            lines = [ln for ln in csv_text.splitlines() if ln.strip()]
            if not lines:
                raise RuntimeError("empty csv")

            header_reader = csv.reader([lines[0]])
            header = next(header_reader)
            header = [h.strip() for h in header if h is not None]
            per["csv"]["header"] = header

            date_col = pick_column(header, date_candidates, kind="date")
            value_col = pick_column(header, value_candidates, kind="value")

            # If still missing and only 2 columns, use (col0 as date, col1 as value) BUT record WARN
            if (date_col is None or value_col is None) and len(header) == 2:
                date_col = header[0]
                value_col = header[1]
                dq["status"] = "WARN" if dq["status"] == "OK" else dq["status"]
                dq["warnings"].append(f"{series_id}: used 2-col fallback (date={date_col}, value={value_col})")

            if date_col is None or value_col is None:
                raise RuntimeError(f"cannot_detect_columns header={header}")

            per["csv"]["date_col"] = date_col
            per["csv"]["value_col"] = value_col

            data_date, value, parsed_rows = parse_csv_latest_by_max_date(
                csv_text=csv_text,
                date_col=date_col,
                value_col=value_col,
                date_formats=date_formats
            )
            per["csv"]["parsed_rows"] = parsed_rows

            entry["data_date"] = data_date
            entry["value"] = value
            entry["notes"] = f"ok; header={header}; date_col={date_col}; value_col={value_col}; parsed_rows={parsed_rows}"

            per["ok"] = True
            per["data_date"] = data_date
            per["value"] = value

            sd = staleness_days(data_date, now)
            per["staleness_days"] = sd
            if expected_max is not None and sd is not None and sd > int(expected_max):
                dq["status"] = "WARN" if dq["status"] == "OK" else dq["status"]
                dq["warnings"].append(f"{series_id}: staleness_days={sd} > expected_max={expected_max}")

        except Exception as e:
            dq["status"] = "ERR"
            err = f"{series_id}: {type(e).__name__}: {e}"
            dq["errors"].append(err)
            entry["notes"] = f"ERR: {err}"
            per["error"] = err

        latest_obj["series"][series_id] = entry
        dq["per_series"][series_id] = per

        # Append history record (auditable, even if failed)
        history.append({
            "series_id": series_id,
            "data_date": entry["data_date"],
            "value": entry["value"],
            "source_url": entry["source_url"],
            "as_of_ts": run_taipei,
            "notes": entry["notes"]
        })

    history = dedup_preserve_order(history)

    # Freeze schema used in this run (for audit downstream)
    schema_out = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_taipei,
        "frozen_from": str(SCHEMA_IN),
        "schema": schema
    }

    write_json_atomic(LATEST_OUT, latest_obj)
    write_json_atomic(HISTORY_OUT, history)
    write_json_atomic(DQ_OUT, dq)
    write_json_atomic(SCHEMA_OUT, schema_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())