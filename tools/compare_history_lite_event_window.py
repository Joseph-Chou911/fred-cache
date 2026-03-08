#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compare_history_lite_event_window.py

Build event windows from cache/history_lite.json.

Expected input schema:
[
  {
    "as_of_ts": "2026-01-10T11:57:32+08:00",
    "series_id": "BAMLH0A0HYM2",
    "data_date": "2025-03-21",
    "value": "3.21",
    "source_url": "...",
    "notes": "..."
  },
  ...
]

Purpose
-------
For each series and each event date:
1. Find the event base observation on or before event_date
2. Build a relative-day window from D-pre_days ... D+post_days
3. For each relative day, match the nearest observation on or before target_date
4. Output long-format rows for audit / later pivoting

Key fields in output
--------------------
- series_id
- event_date
- rel_day
- target_date
- matched_date
- gap_days
- value
- event_matched_date
- event_value
- abs_change_vs_event
- pct_change_vs_event
- status

Status meanings
---------------
- OK             : matched and gap_days <= max_gap_days
- STALE_MATCH    : matched, but gap_days > max_gap_days
- NO_MATCH       : no observation on or before target_date
- NO_EVENT_BASE  : no observation on or before event_date

Usage examples
--------------
# All series, compare two event windows
python tools/compare_history_lite_event_window.py \
  --event-dates 2025-04-07,2026-03-05 \
  --pre-days 10 \
  --post-days 10

# Single series
python tools/compare_history_lite_event_window.py \
  --series SP500 \
  --event-dates 2025-04-07,2026-03-05 \
  --pre-days 10 \
  --post-days 10

# Write outputs
python tools/compare_history_lite_event_window.py \
  --event-dates 2025-04-07,2026-03-05 \
  --pre-days 10 \
  --post-days 10 \
  --json-out cache/compare/event_window.json \
  --csv-out cache/compare/event_window.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Row:
    series_id: str
    data_date: datetime
    value: float
    as_of_ts: Optional[str]
    source_url: Optional[str]
    notes: Optional[str]
    raw: Dict[str, Any]


def parse_date(s: Any) -> Optional[datetime]:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_float(x: Any) -> Optional[float]:
    if x is None:
        return None

    if isinstance(x, (int, float)):
        v = float(x)
        return v if math.isfinite(v) else None

    s = str(x).strip().replace(",", "")
    if not s or s in {".", "NA", "NaN", "nan", "null", "None"}:
        return None

    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def load_rows(path: Path) -> List[Row]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    if not isinstance(obj, list):
        raise ValueError("history_lite.json must be a list of dict rows")

    out: List[Row] = []
    for r in obj:
        if not isinstance(r, dict):
            continue

        series_id = str(r.get("series_id", "")).strip()
        data_date = parse_date(r.get("data_date"))
        value = parse_float(r.get("value"))

        if not series_id or data_date is None or value is None:
            continue

        out.append(
            Row(
                series_id=series_id,
                data_date=data_date,
                value=value,
                as_of_ts=r.get("as_of_ts"),
                source_url=r.get("source_url"),
                notes=r.get("notes"),
                raw=r,
            )
        )

    if not out:
        raise ValueError("No valid rows parsed from history_lite.json")

    return out


def dedupe_and_group(rows: List[Row]) -> Dict[str, List[Row]]:
    """
    Same series_id + same date => keep the last row encountered.
    """
    grouped_raw: Dict[str, Dict[str, Row]] = defaultdict(dict)

    for row in rows:
        key = row.data_date.date().isoformat()
        grouped_raw[row.series_id][key] = row

    grouped: Dict[str, List[Row]] = {}
    for series_id, by_date in grouped_raw.items():
        srows = list(by_date.values())
        srows.sort(key=lambda x: x.data_date)
        grouped[series_id] = srows

    return grouped


def pick_on_or_before(rows: List[Row], target_date: datetime) -> Optional[Row]:
    dates = [r.data_date for r in rows]
    idx = bisect_right(dates, target_date) - 1
    if idx >= 0:
        return rows[idx]
    return None


def parse_event_dates(dates_str: str) -> List[datetime]:
    out: List[datetime] = []
    for item in dates_str.split(","):
        item = item.strip()
        if not item:
            continue
        dt = parse_date(item)
        if dt is None:
            raise ValueError(f"Invalid date in --event-dates: {item}")
        out.append(dt)

    if not out:
        raise ValueError("No valid event dates provided in --event-dates")

    # keep stable sorted order for reproducibility
    out.sort()
    return out


def build_event_window_for_series(
    rows: List[Row],
    event_dates: List[datetime],
    pre_days: int,
    post_days: int,
    max_gap_days: int,
) -> List[Dict[str, Any]]:
    latest = rows[-1]
    out: List[Dict[str, Any]] = []

    for event_dt in event_dates:
        event_base = pick_on_or_before(rows, event_dt)

        if event_base is None:
            # still emit rows so the event is auditable
            for rel_day in range(-pre_days, post_days + 1):
                target_dt = event_dt + timedelta(days=rel_day)
                out.append({
                    "series_id": latest.series_id,
                    "latest_date": latest.data_date.date().isoformat(),
                    "latest_value": latest.value,
                    "event_date": event_dt.date().isoformat(),
                    "event_matched_date": None,
                    "event_base_gap_days": None,
                    "event_value": None,
                    "rel_day": rel_day,
                    "target_date": target_dt.date().isoformat(),
                    "matched_date": None,
                    "gap_days": None,
                    "value": None,
                    "abs_change_vs_event": None,
                    "pct_change_vs_event": None,
                    "status": "NO_EVENT_BASE",
                })
            continue

        event_base_gap_days = (event_dt.date() - event_base.data_date.date()).days
        event_value = event_base.value
        event_matched_date = event_base.data_date.date().isoformat()

        for rel_day in range(-pre_days, post_days + 1):
            target_dt = event_dt + timedelta(days=rel_day)
            matched = pick_on_or_before(rows, target_dt)

            if matched is None:
                out.append({
                    "series_id": latest.series_id,
                    "latest_date": latest.data_date.date().isoformat(),
                    "latest_value": latest.value,
                    "event_date": event_dt.date().isoformat(),
                    "event_matched_date": event_matched_date,
                    "event_base_gap_days": event_base_gap_days,
                    "event_value": event_value,
                    "rel_day": rel_day,
                    "target_date": target_dt.date().isoformat(),
                    "matched_date": None,
                    "gap_days": None,
                    "value": None,
                    "abs_change_vs_event": None,
                    "pct_change_vs_event": None,
                    "status": "NO_MATCH",
                })
                continue

            gap_days = (target_dt.date() - matched.data_date.date()).days
            value = matched.value
            abs_change = value - event_value
            pct_change = None if event_value == 0 else (value / event_value - 1.0) * 100.0

            status = "OK"
            if gap_days > max_gap_days:
                status = "STALE_MATCH"

            out.append({
                "series_id": latest.series_id,
                "latest_date": latest.data_date.date().isoformat(),
                "latest_value": latest.value,
                "event_date": event_dt.date().isoformat(),
                "event_matched_date": event_matched_date,
                "event_base_gap_days": event_base_gap_days,
                "event_value": event_value,
                "rel_day": rel_day,
                "target_date": target_dt.date().isoformat(),
                "matched_date": matched.data_date.date().isoformat(),
                "gap_days": gap_days,
                "value": value,
                "abs_change_vs_event": abs_change,
                "pct_change_vs_event": pct_change,
                "status": status,
            })

    return out


def fmt(x: Any, digits: int = 2) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def print_summary(results: List[Dict[str, Any]], sample_rows: int = 20) -> None:
    print("=" * 120)
    print("Event Window Summary")
    print("=" * 120)

    if not results:
        print("No result rows.")
        return

    series_count = len({r["series_id"] for r in results})
    event_count = len({(r["series_id"], r["event_date"]) for r in results})
    status_counts = Counter(r["status"] for r in results)

    print(f"total_rows   : {len(results)}")
    print(f"series_count : {series_count}")
    print(f"event_pairs  : {event_count}")
    print(f"status_count : {dict(status_counts)}")

    print("\nSample rows:")
    print(
        f"{'Series':>16} | {'EventDate':>10} | {'RelDay':>6} | {'TargetDate':>10} | "
        f"{'MatchedDate':>10} | {'Gap':>4} | {'Value':>12} | {'ΔvsEvent':>12} | {'Status':>12}"
    )
    print("-" * 120)

    for r in results[:sample_rows]:
        print(
            f"{fmt(r['series_id']):>16} | "
            f"{fmt(r['event_date']):>10} | "
            f"{fmt(r['rel_day'], 0):>6} | "
            f"{fmt(r['target_date']):>10} | "
            f"{fmt(r['matched_date']):>10} | "
            f"{fmt(r['gap_days'], 0):>4} | "
            f"{fmt(r['value']):>12} | "
            f"{fmt(r['abs_change_vs_event']):>12} | "
            f"{fmt(r['status']):>12}"
        )


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "series_id",
        "latest_date",
        "latest_value",
        "event_date",
        "event_matched_date",
        "event_base_gap_days",
        "event_value",
        "rel_day",
        "target_date",
        "matched_date",
        "gap_days",
        "value",
        "abs_change_vs_event",
        "pct_change_vs_event",
        "status",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        default="cache/history_lite.json",
        help="Input JSON path"
    )
    parser.add_argument(
        "--series",
        default=None,
        help="Optional series_id filter, e.g. SP500"
    )
    parser.add_argument(
        "--event-dates",
        required=True,
        help="Comma-separated event dates, e.g. 2025-04-07,2026-03-05"
    )
    parser.add_argument(
        "--pre-days",
        type=int,
        default=10,
        help="Number of calendar days before event date"
    )
    parser.add_argument(
        "--post-days",
        type=int,
        default=10,
        help="Number of calendar days after event date"
    )
    parser.add_argument(
        "--max-gap-days",
        type=int,
        default=7,
        help="Mark as STALE_MATCH if matched_date is older than this many days from target_date"
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional JSON output path"
    )
    parser.add_argument(
        "--csv-out",
        default=None,
        help="Optional CSV output path"
    )
    args = parser.parse_args()

    if args.pre_days < 0 or args.post_days < 0:
        raise ValueError("--pre-days and --post-days must be >= 0")

    if args.max_gap_days < 0:
        raise ValueError("--max-gap-days must be >= 0")

    input_path = Path(args.file)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    event_dates = parse_event_dates(args.event_dates)
    rows = load_rows(input_path)
    grouped = dedupe_and_group(rows)

    if args.series:
        grouped = {k: v for k, v in grouped.items() if k == args.series}
        if not grouped:
            raise ValueError(f"series_id not found: {args.series}")

    result_rows: List[Dict[str, Any]] = []
    for series_id, srows in grouped.items():
        if not srows:
            continue
        result_rows.extend(
            build_event_window_for_series(
                rows=srows,
                event_dates=event_dates,
                pre_days=args.pre_days,
                post_days=args.post_days,
                max_gap_days=args.max_gap_days,
            )
        )

    print_summary(result_rows, sample_rows=20)

    meta = {
        "source_file": str(input_path),
        "series_filter": args.series,
        "event_dates": [d.date().isoformat() for d in event_dates],
        "pre_days": args.pre_days,
        "post_days": args.post_days,
        "max_gap_days": args.max_gap_days,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": len(result_rows),
        "results": result_rows,
    }

    if args.json_out:
        write_json(Path(args.json_out), meta)

    if args.csv_out:
        write_csv(Path(args.csv_out), result_rows)


if __name__ == "__main__":
    main()