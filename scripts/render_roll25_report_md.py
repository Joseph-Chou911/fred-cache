#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_roll25_report_md.py

Render roll25_cache/report.md from:
- roll25_cache/latest_report.json (authoritative for UsedDate + signals + dq flags)
- roll25_cache/dashboard_latest.json (stats table: z60/p60/z252/p252/zD60/pD60/ret1)

NO external fetch.

Output:
- roll25_cache/report.md
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_num(x: Any, digits: int = 3) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _md_table(rows: List[Dict[str, Any]]) -> str:
    cols = ["series", "value", "z60", "p60", "z252", "p252", "zD60", "pD60", "ret1_pct", "confidence"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows:
        line = "| " + " | ".join([
            str(r.get("series", "NA")),
            _fmt_num(r.get("value"), 6),
            _fmt_num(r.get("z60"), 6),
            _fmt_num(r.get("p60"), 3),
            _fmt_num(r.get("z252"), 6),
            _fmt_num(r.get("p252"), 3),
            _fmt_num(r.get("zD60"), 6),
            _fmt_num(r.get("pD60"), 3),
            _fmt_num(r.get("ret1_pct"), 6),
            str(r.get("confidence", "NA")),
        ]) + " |"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default="roll25_cache/latest_report.json")
    ap.add_argument("--dash", default="roll25_cache/dashboard_latest.json")
    ap.add_argument("--out", default="roll25_cache/report.md")
    args = ap.parse_args()

    latest = _read_json(args.latest)
    dash = _read_json(args.dash)

    nums = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sigs = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date = nums.get("UsedDate")
    used_date_status = sigs.get("UsedDateStatus") if "UsedDateStatus" in sigs else latest.get("used_date_status")
    run_day_tag = sigs.get("RunDayTag") if "RunDayTag" in sigs else latest.get("run_day_tag")

    # key market numbers
    tv = nums.get("TradeValue")
    close = nums.get("Close")
    pct_chg = nums.get("PctChange")
    amp = nums.get("AmplitudePct")
    vol_mult = nums.get("VolumeMultiplier") if nums.get("VolumeMultiplier") is not None else nums.get("VolMultiplier")

    # signals
    down_day = sigs.get("DownDay")
    vol_amp = sigs.get("VolumeAmplified") if "VolumeAmplified" in sigs else sigs.get("VolAmplified")
    new_low_n = sigs.get("NewLow_N")
    cons_break = sigs.get("ConsecutiveBreak")
    ohlc_missing = sigs.get("OhlcMissing")

    # dashboard table
    table = dash.get("table") if isinstance(dash, dict) else None
    if not isinstance(table, list):
        table = []

    generated_at_utc = _now_utc_z()
    generated_at_local = latest.get("generated_at")
    tz = latest.get("timezone")

    # build markdown
    out: List[str] = []
    out.append("# Roll25 Cache Report (TWSE Turnover)\n")
    out.append("## 1) Summary\n")
    out.append(f"- generated_at_utc: `{generated_at_utc}`\n")
    out.append(f"- generated_at_local: `{generated_at_local}`\n")
    out.append(f"- timezone: `{tz}`\n")
    out.append(f"- UsedDate: `{used_date}`\n")
    out.append(f"- UsedDateStatus: `{used_date_status}`\n")
    out.append(f"- RunDayTag: `{run_day_tag}`\n")
    out.append(f"- summary: {latest.get('summary','NA')}\n")

    out.append("\n## 2) Key Numbers (from latest_report.json)\n")
    out.append(f"- turnover_twd: `{tv}`\n")
    out.append(f"- close: `{_fmt_num(close, 2)}`\n")
    out.append(f"- pct_change: `{_fmt_num(pct_chg, 6)}`\n")
    out.append(f"- amplitude_pct: `{_fmt_num(amp, 6)}`\n")
    out.append(f"- volume_multiplier_20: `{_fmt_num(vol_mult, 6)}`\n")

    out.append("\n## 3) Market Behavior Signals (from latest_report.json)\n")
    out.append(f"- DownDay: `{_fmt_num(down_day)}`\n")
    out.append(f"- VolumeAmplified: `{_fmt_num(vol_amp)}`\n")
    out.append(f"- NewLow_N: `{_fmt_num(new_low_n)}`\n")
    out.append(f"- ConsecutiveBreak: `{_fmt_num(cons_break)}`\n")

    out.append("\n## 4) Data Quality Flags (from latest_report.json)\n")
    out.append(f"- OhlcMissing: `{_fmt_num(ohlc_missing)}`\n")
    out.append(f"- freshness_ok: `{_fmt_num(latest.get('freshness_ok'))}`\n")
    out.append(f"- freshness_age_days: `{_fmt_num(latest.get('freshness_age_days'))}`\n")
    out.append(f"- ohlc_status: `{latest.get('ohlc_status','NA')}`\n")
    out.append(f"- mode: `{latest.get('mode','NA')}`\n")

    out.append("\n## 5) Z/P Table (market_cache-like; computed from roll25.json)\n")
    out.append(_md_table([r for r in table if isinstance(r, dict)]))

    out.append("\n## 6) Audit Notes\n")
    out.append("- This report is computed from local files only (no external fetch).\n")
    out.append("- z-score uses population std (ddof=0). Percentile is tie-aware.\n")
    out.append("- If insufficient points, corresponding stats remain NA (no guessing).\n")

    cav = latest.get("caveats")
    if isinstance(cav, str) and cav.strip():
        out.append("\n## 7) Caveats / Sources (from latest_report.json)\n")
        out.append("```\n")
        out.append(cav.rstrip() + "\n")
        out.append("```\n")

    _write_text(args.out, "".join(out))
    print(f"OK wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())