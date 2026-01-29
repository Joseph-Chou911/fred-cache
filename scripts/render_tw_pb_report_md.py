#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from typing import Any, Dict


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt(x: Any) -> str:
    return "None" if x is None else str(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest: Dict[str, Any] = read_json(args.latest)
    stats: Dict[str, Any] = read_json(args.stats)

    title = "# TW PB Sidecar Report (TAIEX P/B, DAILY)\n\n"

    summary = [
        "## 1) Summary",
        f"- source_vendor: `{latest.get('source_vendor')}` ({latest.get('source_class')})",
        f"- source_url: `{latest.get('source_url')}`",
        f"- fetch_status: `{latest.get('fetch_status')}` / confidence: `{latest.get('confidence')}` / dq_reason: `{latest.get('dq_reason')}`",
        f"- data_date: `{latest.get('data_date')}`",
        f"- series_len_pbr: `{stats.get('series_len_pbr')}`",
        "",
    ]

    latest_sec = [
        "## 2) Latest",
        f"- date: `{latest.get('data_date')}`",
        f"- PBR: `{fmt(latest.get('pbr'))}`",
        f"- Close: `{fmt(latest.get('close'))}`",
        "",
    ]

    stats_sec = [
        "## 3) Stats (z / percentile)",
        f"- z60: `{fmt(stats.get('z60'))}` / p60: `{fmt(stats.get('p60'))}` / na_reason_60: `{fmt(stats.get('na_reason_60'))}`",
        f"- z252: `{fmt(stats.get('z252'))}` / p252: `{fmt(stats.get('p252'))}` / na_reason_252: `{fmt(stats.get('na_reason_252'))}`",
        "",
    ]

    caveats = [
        "## 4) Caveats",
        "- History builds forward only (NO historical backfill; NO inferred dates).",
        "- This module appends the page's latest PBR into history.json on each successful run.",
        "- z/p requires enough observations; NA is expected until the history grows (no guessing).",
        "- Data source is third-party. Treat absolute thresholds cautiously; definition may differ from other vendors.",
        "",
    ]

    content = "\n".join([title] + summary + latest_sec + stats_sec + caveats)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()