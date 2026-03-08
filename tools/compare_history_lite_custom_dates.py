#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compare_history_lite_custom_dates.py

Compare latest ("now") vs user-specified custom date list
from cache/history_lite.json.

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

Core behavior
-------------
For each series_id:
1. Sort by data_date
2. Use the latest row as "now"
3. For each requested target date:
   - find the nearest row on or before that date
4. Compute:
   - abs_change = latest_value - past_value
   - pct_change = (latest_value / past_value - 1) * 100
   - gap_days   = target_date - matched_past_date

Usage examples
--------------
# Compare all series against three event dates
python tools/compare_history_lite_custom_dates.py \
  --dates 2025-04-02,2025-04-07,2025-04-10

# Compare a single series
python tools/compare_history_lite_custom_dates.py \
  --series BAMLH0A0HYM2 \
  --dates 2025-04-02,2025-04-07,2025-04-10

# Write JSON / CSV
python tools/compare_history_lite_custom_dates.py \
  --dates 2025-04-02,2025-04-07,2025-04-10 \
  --json-out cache/custom_date_compare.json \
  --csv-out cache/custom_date_compare.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
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


def compare_one_series_against_dates(
    rows: List[Row],
    target_dates: List[datetime],
) -> List[Dict[str, Any]]:
    latest = rows[-1]
    out: List[Dict[str, Any]] = []

    for target in target_dates:
        past = pick_on_or_before(rows, target)

        if past is None:
            out.append({
                "series_id": latest.series_id,
                "latest_date": latest.data_date.date().isoformat(),
                "latest_value": latest.value,
                "target_date": target.date().isoformat(),
                "matched_past_date": None,
                "gap_days": None,
                "past_value": None,
                "abs_change": None,
                "pct_change": None,
                "status": "NO_PAST_DATA",
            })
            continue

        abs_change = latest.value - past.value
        pct_change = None if past.value == 0 else (latest.value / past.value - 1.0) * 100.0
        gap_days = (target.date() - past.data_date.date()).days

        out.append({
            "series_id": latest.series_id,
            "latest_date": latest.data_date.date().isoformat(),
            "latest_value": latest.value,
            "target_date": target.date().isoformat(),
            "matched_past_date": past.data_date.date().isoformat(),
            "gap_days": gap_days,
            "past_value": past.value,
            "abs_change": abs_change,
            "pct_change": pct_change,
            "status": "OK",
        })

    return out


def fmt(x: Any, digits: int = 2) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def print_report(results: Dict[str, List[Dict[str, Any]]]) -> None:
    for series_id, rows in results.items():
        print("\n" + "=" * 140)
        print(f"Series: {series_id}")
        print("=" * 140)
        print(
            f"{'TargetDate':>10} | {'LatestDate':>10} | {'Latest':>12} | "
            f"{'MatchedPast':>10} | {'GapDays':>7} | {'Past':>12} | "
            f"{'AbsChange':>12} | {'PctChange%':>12} | {'Status':>12}"
        )
        print("-" * 140)

        for r in rows:
            print(
                f"{fmt(r['target_date']):>10} | "
                f"{fmt(r['latest_date']):>10} | "
                f"{fmt(r['latest_value']):>12} | "
                f"{fmt(r['matched_past_date']):>10} | "
                f"{fmt(r['gap_days'], 0):>7} | "
                f"{fmt(r['past_value']):>12} | "
                f"{fmt(r['abs_change']):>12} | "
                f"{fmt(r['pct_change']):>12} | "
                f"{fmt(r['status']):>12}"
            )


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, results: Dict[str, List[Dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "series_id",
        "latest_date",
        "latest_value",
        "target_date",
        "matched_past_date",
        "gap_days",
        "past_value",
        "abs_change",
        "pct_change",
        "status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for _, rows in results.items():
            for r in rows:
                writer.writerow(r)


def parse_target_dates(dates_str: str) -> List[datetime]:
    out: List[datetime] = []
    for item in dates_str.split(","):
        item = item.strip()
        if not item:
            continue
        dt = parse_date(item)
        if dt is None:
            raise ValueError(f"Invalid date in --dates: {item}")
        out.append(dt)

    if not out:
        raise ValueError("No valid target dates provided in --dates")

    out.sort()
    return out


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
        help="Optional series_id filter, e.g. BAMLH0A0HYM2"
    )
    parser.add_argument(
        "--dates",
        required=True,
        help="Comma-separated target dates, e.g. 2025-04-02,2025-04-07,2025-04-10"
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

    input_path = Path(args.file)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    target_dates = parse_target_dates(args.dates)
    rows = load_rows(input_path)
    grouped = dedupe_and_group(rows)

    if args.series:
        grouped = {k: v for k, v in grouped.items() if k == args.series}
        if not grouped:
            raise ValueError(f"series_id not found: {args.series}")

    results: Dict[str, List[Dict[str, Any]]] = {}
    for series_id, srows in grouped.items():
        if not srows:
            continue
        results[series_id] = compare_one_series_against_dates(srows, target_dates)

    print_report(results)

    meta = {
        "source_file": str(input_path),
        "series_filter": args.series,
        "target_dates": [d.date().isoformat() for d in target_dates],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }

    if args.json_out:
        write_json(Path(args.json_out), meta)

    if args.csv_out:
        write_csv(Path(args.csv_out), results)


if __name__ == "__main__":
    main()