#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Render TW PB sidecar report from latest.json + stats_latest.json + history.json.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict


def load(p: str) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt(x: Any) -> str:
    if x is None:
        return "None"
    if isinstance(x, float):
        return f"{x:.6g}"
    return str(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = load(args.latest)
    stats = load(args.stats)
    hist = load(args.history)

    source_vendor = latest.get("source_vendor")
    endpoint = latest.get("endpoint")
    fetch_status = latest.get("fetch_status")
    confidence = latest.get("confidence")
    dq_reason = latest.get("dq_reason")
    data_date = latest.get("data_date")
    latest_row = latest.get("latest") or {}

    series_len_rows = stats.get("series_len_rows")
    series_len_pbr = stats.get("series_len_pbr")

    pbr = latest_row.get("pbr")
    close = latest_row.get("close")
    date = latest_row.get("date")

    s = stats.get("stats", {})
    z60 = s.get("z60")
    p60 = s.get("p60")
    na60 = s.get("na_reason_60")
    z252 = s.get("z252")
    p252 = s.get("p252")
    na252 = s.get("na_reason_252")

    md = []
    md.append("# TW PB Sidecar Report (TAIEX P/B, DAILY)\n")
    md.append("## 1) Summary")
    md.append(f"- source_vendor: `{source_vendor}` (OFFICIAL)")
    md.append(f"- endpoint: `{endpoint}`")
    md.append(f"- fetch_status: `{fetch_status}` / confidence: `{confidence}` / dq_reason: `{dq_reason}`")
    md.append(f"- data_date: `{data_date}` / latest_row_date: `{date}`")
    md.append(f"- series_len_rows: `{series_len_rows}` / series_len_pbr: `{series_len_pbr}`\n")

    md.append("## 2) Latest")
    md.append(f"- date: `{date}`")
    md.append(f"- PBR: `{fmt(pbr)}`")
    md.append(f"- Close: `{fmt(close)}`\n")

    md.append("## 3) Stats (z / percentile)")
    md.append(f"- z60: `{fmt(z60)}` / p60: `{fmt(p60)}` / na_reason_60: `{fmt(na60)}`")
    md.append(f"- z252: `{fmt(z252)}` / p252: `{fmt(p252)}` / na_reason_252: `{fmt(na252)}`\n")

    md.append("## 4) Caveats")
    md.append("- This module uses TWSE RWD monthly-query endpoint to assemble a DAILY trading-day series.")
    md.append("- If TWSE response schema changes (fields renamed), extraction may degrade to DOWNGRADED with empty_rows.")
    md.append("- No interpolation; NA is preserved.\n")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()