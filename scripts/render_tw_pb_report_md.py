#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_tw_pb_report_md.py

Render tw_pb_cache/latest.json + stats_latest.json into report.md

Adds:
- Historical Context (non-trigger): user-provided MacroMicro anchor (2000-03 P/B=3.08)
- Simple deterministic comparisons vs anchor (only if latest PBR is available)

This renderer does NOT recompute data; it only formats existing fields.
If a field is missing => prints NA/None deterministically.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional


# --------------------------------------------------------------------
# Historical anchor (context-only, NOT a trigger)
# Source: MacroMicro chart tooltip (user-provided screenshot)
# --------------------------------------------------------------------
ANCHOR_LABEL = "HISTORICAL_ANCHOR (USER_PROVIDED_SCREENSHOT)"
ANCHOR_PERIOD = "2000-03"
ANCHOR_PB = 3.08
ANCHOR_VENDOR = "MacroMicro"
ANCHOR_NOTE = "Context-only; NOT used for deterministic signals (triggers rely on p60/p252 once available)."


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt(x: Any) -> str:
    return "None" if x is None else str(x)


def fmt_float(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "None"
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "None"


def try_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x))
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest: Dict[str, Any] = read_json(args.latest)
    stats: Dict[str, Any] = read_json(args.stats)

    latest_pbr = try_float(latest.get("pbr"))
    latest_close = try_float(latest.get("close"))

    # Anchor comparisons (deterministic; context only)
    anchor_delta = None
    anchor_ratio = None
    anchor_cmp = "NA"
    if latest_pbr is not None:
        anchor_delta = latest_pbr - ANCHOR_PB
        anchor_ratio = latest_pbr / ANCHOR_PB if ANCHOR_PB != 0 else None
        if latest_pbr > ANCHOR_PB:
            anchor_cmp = "GT"
        elif latest_pbr < ANCHOR_PB:
            anchor_cmp = "LT"
        else:
            anchor_cmp = "EQ"

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
        f"- PBR: `{fmt_float(latest_pbr, 4)}`",
        f"- Close: `{fmt_float(latest_close, 2)}`",
        "",
    ]

    stats_sec = [
        "## 3) Stats (z / percentile)",
        f"- z60: `{fmt(stats.get('z60'))}` / p60: `{fmt(stats.get('p60'))}` / na_reason_60: `{fmt(stats.get('na_reason_60'))}`",
        f"- z252: `{fmt(stats.get('z252'))}` / p252: `{fmt(stats.get('p252'))}` / na_reason_252: `{fmt(stats.get('na_reason_252'))}`",
        "",
    ]

    # Historical anchor section (context only)
    hist_sec = [
        "## 4) Historical Context (non-trigger)",
        f"- label: `{ANCHOR_LABEL}`",
        f"- vendor: `{ANCHOR_VENDOR}`",
        f"- anchor_period: `{ANCHOR_PERIOD}`",
        f"- anchor_pb: `{fmt_float(ANCHOR_PB, 2)}`",
        f"- note: {ANCHOR_NOTE}",
        "",
        "### 4.1) Anchor comparison (context only)",
        f"- latest_pb: `{fmt_float(latest_pbr, 4)}`",
        f"- compare_to_anchor: `{anchor_cmp}` (GT/LT/EQ/NA)",
        f"- delta_vs_anchor: `{fmt_float(anchor_delta, 4)}`",
        f"- ratio_vs_anchor: `{fmt_float(anchor_ratio, 4)}`",
        "",
    ]

    caveats = [
        "## 5) Caveats",
        "- History builds forward only (NO historical backfill; NO inferred dates).",
        "- This module appends the page's latest PBR into history.json on each successful run.",
        "- z/p requires enough observations; NA is expected until the history grows (no guessing).",
        "- Data source is third-party. Treat absolute thresholds cautiously; definition may differ from other vendors.",
        "- The historical anchor in section 4 is derived from a user-provided screenshot tooltip; it is included as context only.",
        "",
    ]

    content = "\n".join([title] + summary + latest_sec + stats_sec + hist_sec + caveats)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()