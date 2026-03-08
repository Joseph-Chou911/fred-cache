#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compare_history_lite.py

Compare latest vs past periods from cache/history_lite.json.

Expected input schema (confirmed by sample):
[
  {
    "as_of_ts": "...",
    "series_id": "BAMLH0A0HYM2",
    "data_date": "2025-03-21",
    "value": "3.21",
    "source_url": "...",
    "notes": "..."
  },
  ...
]

Features:
- group by series_id
- sort by data_date
- compare latest value vs past windows
- choose nearest record on or before target date
- output terminal table
- optional JSON / CSV output
- optional series filter

Usage:
    python compare_history_lite.py
    python compare_history_lite.py --series BAMLH0A0HYM2
    python compare_history_lite.py --periods 7,30,90,180,365
    python compare_history_lite.py --json-out out.json
    python compare_history_lite.py --csv-out out.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_right
from collections import defaultdict
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
    grouped_raw: Dict[str, Dict[str, Row]] = defaultdict(dict)

    # same series_id + same date => keep last row encountered
    for row in rows:
        grouped_raw[row.series_id][row.data_date.date().isoformat()] = row

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


def compare_one_series(rows: List[Row], periods: List[int]) -> List[Dict[str, Any]]:
    latest = rows[-1]
    out: List[Dict[str, Any]] = []

    for d in periods:
        target = latest.data_date - timedelta(days=d)
        past = pick_on_or_before(rows, target)

        if past is None:
            out.append({
                "series_id": latest.series_id,
                "latest_date": latest.data_date.date().isoformat(),
                "latest_value": latest.value,
                "period_days": d,
                "target_date": target.date().isoformat(),
                "past_date": None,
                "past_value": None,
                "abs_change": None,
                "pct_change": None,
                "status": "NO_PAST_DATA",
            })
            continue

        abs_change = latest.value - past.value
        pct_change = None if past.value == 0 else (latest.value / past.value - 1.0) * 100.0

        out.append({
            "series_id": latest.series_id,
            "latest_date": latest.data_date.date().isoformat(),
            "latest_value": latest.value,
            "period_days": d,
            "target_date": target.date().isoformat(),
            "past_date": past.data_date.date().isoformat(),
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
        print("\n" + "=" * 120)
        print(f"Series: {series_id}")
        print("=" * 120)
        print(
            f"{'Period':>8} | {'LatestDate':>10} | {'Latest':>12} | {'TargetDate':>10} | "
            f"{'PastDate':>10} | {'Past':>12} | {'AbsChange':>12} | {'PctChange%':>12} | {'Status':>12}"
        )
        print("-" * 120)

        for r in rows:
            print(
                f"{str(r['period_days']) + 'D':>8} | "
                f"{fmt(r['latest_date']):>10} | "
                f"{fmt(r['latest_value']):>12} | "
                f"{fmt(r['target_date']):>10} | "
                f"{fmt(r['past_date']):>10} | "
                f"{fmt(r['past_value']):>12} | "
                f"{fmt(r['abs_change']):>12} | "
                f"{fmt(r['pct_change']):>12} | "
                f"{fmt(r['status']):>12}"
            )


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, results: Dict[str, List[Dict[str, Any]]]) -> None:
    fieldnames = [
        "series_id",
        "latest_date",
        "latest_value",
        "period_days",
        "target_date",
        "past_date",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="cache/history_lite.json", help="Input JSON path")
    parser.add_argument("--series", default=None, help="Optional series_id filter")
    parser.add_argument("--periods", default="7,30,90,180,365", help="Comma-separated lookback days")
    parser.add_argument("--json-out", default=None, help="Optional JSON output path")
    parser.add_argument("--csv-out", default=None, help="Optional CSV output path")
    args = parser.parse_args()

    periods = [int(x.strip()) for x in args.periods.split(",") if x.strip()]

    rows = load_rows(Path(args.file))
    grouped = dedupe_and_group(rows)

    if args.series:
        grouped = {k: v for k, v in grouped.items() if k == args.series}
        if not grouped:
            raise ValueError(f"series_id not found: {args.series}")

    results: Dict[str, List[Dict[str, Any]]] = {}
    for series_id, srows in grouped.items():
        if not srows:
            continue
        results[series_id] = compare_one_series(srows, periods)

    print_report(results)

    meta = {
        "source_file": args.file,
        "series_filter": args.series,
        "periods": periods,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }

    if args.json_out:
        write_json(Path(args.json_out), meta)

    if args.csv_out:
        write_csv(Path(args.csv_out), results)


if __name__ == "__main__":
    main()