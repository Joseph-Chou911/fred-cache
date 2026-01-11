#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time backfill for regime_inputs_cache inputs_history_lite.json

- Reads regime_inputs_cache/inputs_config.json
- Fetches full CSV for each series
- Parses all valid (date, value) points
- Takes last N points (N=250 by default) by data_date
- Appends into inputs_history_lite.json with auditable notes
- Dedups by (series_id, data_date, value), preserving order

Supported fetchers:
- csv_max_date: uses url + date_col + value_col, but here we parse ALL rows (not only latest)
- stooq_daily: uses Stooq daily CSV symbol, parse Date+Close

Usage:
  python scripts/backfill_regime_inputs_history.py --n 250
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "regime_inputs_cache"

CONFIG_PATH = OUT_DIR / "inputs_config.json"
HIST_LITE_PATH = OUT_DIR / "inputs_history_lite.json"
BACKFILL_REPORT_PATH = OUT_DIR / "backfill_report.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_taipei(dt: datetime) -> str:
    if ZoneInfo is None:
        return iso_z(dt)
    return dt.astimezone(ZoneInfo("Asia/Taipei")).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def http_get_text(url: str, timeout_sec: int) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "regime_inputs_cache_backfill/1.0 (+https://github.com/)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def retry_fetch(url: str, timeout_sec: int, backoff: List[int]) -> str:
    last_err: Optional[Exception] = None
    for wait_s in [0] + backoff:
        if wait_s:
            time.sleep(wait_s)
        try:
            return http_get_text(url, timeout_sec=timeout_sec)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"fetch_failed after retries: {type(last_err).__name__}: {last_err}")  # type: ignore[arg-type]


def parse_date_yyyy_mm_dd(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {s}")


def safe_float(x: str) -> float:
    x = (x or "").strip().replace(",", "")
    return float(x)


def dedup_preserve_order(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in records:
        key = (r.get("series_id"), r.get("data_date"), r.get("value"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def stooq_url(symbol: str) -> str:
    return f"https://stooq.com/q/d/l/?s={symbol}&i=d"


def parse_stooq_all_points(csv_text: str) -> Tuple[List[Tuple[str, float]], Dict[str, Any]]:
    rows = list(csv.DictReader(csv_text.splitlines()))
    pts: List[Tuple[str, float]] = []
    bad = 0
    for r in rows:
        d_raw = r.get("Date")
        c_raw = r.get("Close")
        if not d_raw or not c_raw:
            bad += 1
            continue
        try:
            d = parse_date_yyyy_mm_dd(d_raw)
            v = safe_float(c_raw)
            pts.append((d, v))
        except Exception:
            bad += 1
            continue
    meta = {"rows_total": len(rows), "rows_valid": len(pts), "rows_bad": bad, "date_col": "Date", "value_col": "Close"}
    return pts, meta


def parse_csv_all_points(csv_text: str, date_col: str, value_col: str) -> Tuple[List[Tuple[str, float]], Dict[str, Any]]:
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("empty csv")

    header = next(csv.reader([lines[0]]))
    header = [h.strip() for h in header]

    reader = csv.DictReader(lines)
    pts: List[Tuple[str, float]] = []
    bad = 0
    rows = 0
    for r in reader:
        rows += 1
        d_raw = r.get(date_col, "")
        v_raw = r.get(value_col, "")
        if not d_raw or not v_raw:
            bad += 1
            continue
        try:
            d = parse_date_yyyy_mm_dd(d_raw)
            v = safe_float(v_raw)
            pts.append((d, v))
        except Exception:
            bad += 1
            continue

    meta = {
        "header": header,
        "rows_total": rows,
        "rows_valid": len(pts),
        "rows_bad": bad,
        "date_col": date_col,
        "value_col": value_col
    }
    return pts, meta


def take_last_n_by_date(points: List[Tuple[str, float]], n: int) -> List[Tuple[str, float]]:
    # sort by date ascending, then take last n
    points_sorted = sorted(points, key=lambda x: x[0])
    if n <= 0:
        return []
    return points_sorted[-n:]


def main() -> int:
    now = utc_now()
    run_utc = iso_z(now)
    run_tpe = iso_taipei(now)

    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250)
    args = ap.parse_args()
    n = int(args.n)

    cfg = load_json(CONFIG_PATH, None)
    if not cfg:
        raise SystemExit(f"Missing config: {CONFIG_PATH}")

    timeout = int(cfg.get("default_timeout_sec", 25))
    backoff = cfg.get("backoff_seconds", [2, 4, 8])
    if not isinstance(backoff, list) or not backoff:
        backoff = [2, 4, 8]

    history: List[Dict[str, Any]] = load_json(HIST_LITE_PATH, default=[])

    report: Dict[str, Any] = {
        "generated_at_utc": run_utc,
        "as_of_ts": run_tpe,
        "script_version": "backfill_regime_inputs_history_v1",
        "n": n,
        "per_series": {},
        "errors": []
    }

    for s in cfg.get("series", []):
        sid = s.get("series_id")
        fetcher = s.get("fetcher")
        if not sid or not fetcher:
            continue

        try:
            if fetcher == "stooq_daily":
                symbol = s["symbol"]
                url = stooq_url(symbol)
                text = retry_fetch(url, timeout_sec=timeout, backoff=backoff)
                pts, meta = parse_stooq_all_points(text)

            elif fetcher == "csv_max_date":
                url = s["url"]
                date_col = s["date_col"]
                value_col = s["value_col"]
                text = retry_fetch(url, timeout_sec=timeout, backoff=backoff)
                pts, meta = parse_csv_all_points(text, date_col=date_col, value_col=value_col)

            else:
                raise RuntimeError(f"unsupported fetcher: {fetcher}")

            pts_n = take_last_n_by_date(pts, n=n)

            appended = 0
            for d, v in pts_n:
                history.append({
                    "series_id": sid,
                    "data_date": d,
                    "value": v,
                    "source_url": url,
                    "as_of_ts": run_tpe,
                    "notes": f"backfill_n{n}; fetcher={fetcher}; {meta}"
                })
                appended += 1

            report["per_series"][sid] = {
                "fetcher": fetcher,
                "source_url": url,
                "points_total_valid": meta.get("rows_valid"),
                "points_selected": len(pts_n),
                "selected_oldest": pts_n[0][0] if pts_n else None,
                "selected_newest": pts_n[-1][0] if pts_n else None
            }

        except Exception as e:
            msg = f"{sid}: {type(e).__name__}: {e}"
            report["errors"].append(msg)
            report["per_series"][sid] = {"fetcher": fetcher, "error": msg}

    history = dedup_preserve_order(history)

    write_json_atomic(HIST_LITE_PATH, history)
    write_json_atomic(BACKFILL_REPORT_PATH, report)

    print(json.dumps({
        "ok": True,
        "history_records": len(history),
        "backfill_report": str(BACKFILL_REPORT_PATH)
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())