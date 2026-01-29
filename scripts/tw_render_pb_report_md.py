#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json


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
    p = stats.get("pbr", {})

    lines = []
    lines.append("# TW PB Sidecar Report (TAIEX P/B, MONTHLY)")
    lines.append("")
    lines.append("## 1) Summary")
    lines.append(f"- source_vendor: `{latest.get('source_vendor')}` (THIRD_PARTY)")
    lines.append(f"- source_url: `{latest.get('source_url')}`")
    lines.append(f"- fetch_status: `{latest.get('fetch_status')}` / confidence: `{latest.get('confidence')}` / dq_reason: `{latest.get('dq_reason')}`")
    lines.append(f"- freq: `{latest.get('freq')}`")
    lines.append(f"- period_ym: `{latest.get('period_ym')}` / data_date: `{latest.get('data_date')}`")
    lines.append(f"- series_len: `{latest.get('series_len')}`")
    lines.append("")
    lines.append("## 2) Latest (from monthly table)")
    lines.append(f"- PBR: `{latest.get('pbr')}`")
    lines.append(f"- Monthly Close: `{latest.get('monthly_close')}`")
    lines.append("")
    lines.append("## 3) Stats (z / percentile)")
    lines.append(f"- z60: `{p.get('z60')}` / p60: `{p.get('p60')}` / na_reason_60: `{p.get('na_reason_60')}`")
    lines.append(f"- z252: `{p.get('z252')}` / p252: `{p.get('p252')}` / na_reason_252: `{p.get('na_reason_252')}`")
    lines.append("")
    lines.append("## 4) Caveats")
    lines.append("- This module uses the MONTHLY river table series for stats; intraday values are not used for z/p.")
    lines.append("- z252/p252 will remain NA until >=252 monthly observations exist (likely unavailable with current public table).")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    main()