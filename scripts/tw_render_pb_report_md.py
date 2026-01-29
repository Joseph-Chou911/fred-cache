#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = "Asia/Taipei"


def _read(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = _read(args.latest)
    stats = _read(args.stats)

    now_local = datetime.now(ZoneInfo(TZ))
    now_utc = now_local.astimezone(timezone.utc)

    lines = []
    lines.append("# TW PB Sidecar Report (TAIEX P/B)")
    lines.append("")
    lines.append("## 1) Summary")
    lines.append(f"- generated_at_utc: `{now_utc.replace(microsecond=0).isoformat().replace('+00:00','Z')}`")
    lines.append(f"- generated_at_local: `{now_local.isoformat()}`")
    lines.append(f"- timezone: `{TZ}`")
    lines.append(f"- source_vendor: `{latest.get('source_vendor')}` (THIRD_PARTY)")
    lines.append(f"- source_url: `{latest.get('source_url')}`")
    lines.append(f"- fetch_status: `{latest.get('fetch_status')}` / confidence: `{latest.get('confidence')}` / dq_reason: `{latest.get('dq_reason')}`")
    lines.append(f"- data_date: `{latest.get('data_date')}` data_time_local: `{latest.get('data_time_local')}`")
    lines.append("")
    lines.append("## 2) Latest Values")
    lines.append(f"- PBR: `{latest.get('pbr')}`")
    lines.append(f"- PER: `{latest.get('per')}`")
    lines.append(f"- Dividend Yield (%): `{latest.get('dividend_yield_pct')}`")
    lines.append("")
    lines.append("## 3) Stats (z / percentile)")
    lines.append("")
    for k in ["pbr", "per", "dividend_yield_pct"]:
        obj = stats.get(k, {})
        lines.append(f"### {k}")
        lines.append(f"- value: `{obj.get('value')}`")
        lines.append(f"- z60: `{obj.get('z60')}` / p60: `{obj.get('p60')}` / na_reason_60: `{obj.get('na_reason_60')}`")
        lines.append(f"- z252: `{obj.get('z252')}` / p252: `{obj.get('p252')}` / na_reason_252: `{obj.get('na_reason_252')}`")
        lines.append("")

    lines.append("## 4) Caveats")
    lines.append("- THIRD_PARTY aggregated source; HTML structure may change => parse failure possible.")
    lines.append("- Windows are observation-count based; schedule determines effective frequency.")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    main()