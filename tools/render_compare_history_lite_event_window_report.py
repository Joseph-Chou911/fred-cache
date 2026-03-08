#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_compare_history_lite_event_window_report.py

Pure renderer for compare_history_lite_event_window.py JSON output.

Reads:
- compare_history_lite_event_window_out.json

Writes:
- report.md

Design goals
------------
- Pure render only: does NOT recompute source series history
- Audit-first: only formats fields already present in input JSON
- Deterministic summaries / flags
- Markdown friendly for GitHub reading

Usage
-----
python tools/render_compare_history_lite_event_window_report.py \
  --input cache/compare/compare_history_lite_event_window_out.json \
  --output cache/compare/report.md

Optional:
python tools/render_compare_history_lite_event_window_report.py \
  --input cache/compare/compare_history_lite_event_window_out.json \
  --output cache/compare/report.md \
  --focus-series BAMLH0A0HYM2,VIXCLS,SP500,NASDAQCOM,DCOILWTICO,DGS10,DGS2,T10Y2Y,T10Y3M,STLFSI4,NFCINONFINLEVERAGE,DTWEXBGS
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_FOCUS_SERIES = [
    "BAMLH0A0HYM2",
    "VIXCLS",
    "SP500",
    "NASDAQCOM",
    "DCOILWTICO",
    "DGS10",
    "DGS2",
    "T10Y2Y",
    "T10Y3M",
    "STLFSI4",
    "NFCINONFINLEVERAGE",
    "DTWEXBGS",
]

DEFAULT_REL_DAYS = [-10, -5, -3, 0, 1, 3, 5, 10]


def fmt_num(x: Any, digits: int = 2) -> str:
    if x is None:
        return "NA"
    if isinstance(x, (int, float)):
        return f"{x:.{digits}f}"
    return str(x)


def fmt_int(x: Any) -> str:
    if x is None:
        return "NA"
    return str(int(x))


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("Input JSON must be a dict")
    return obj


def build_index(results: List[Dict[str, Any]]) -> Dict[Tuple[str, str, int], Dict[str, Any]]:
    idx: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for r in results:
        series_id = str(r.get("series_id"))
        event_date = str(r.get("event_date"))
        rel_day = int(r.get("rel_day"))
        idx[(series_id, event_date, rel_day)] = r
    return idx


def group_by_series_event(results: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        grouped[(str(r.get("series_id")), str(r.get("event_date")))].append(r)
    for k in grouped:
        grouped[k].sort(key=lambda x: int(x.get("rel_day", 0)))
    return grouped


def unique_in_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def get_row(
    idx: Dict[Tuple[str, str, int], Dict[str, Any]],
    series_id: str,
    event_date: str,
    rel_day: int,
) -> Optional[Dict[str, Any]]:
    return idx.get((series_id, event_date, rel_day))


def get_metric(
    idx: Dict[Tuple[str, str, int], Dict[str, Any]],
    series_id: str,
    event_date: str,
    rel_day: int,
    field: str,
) -> Any:
    r = get_row(idx, series_id, event_date, rel_day)
    if r is None:
        return None
    return r.get(field)


def status_count_for_event(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    return dict(Counter(str(r.get("status")) for r in rows))


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def pct_change(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """
    return b vs a, i.e. (b/a -1)*100
    """
    if a is None or b is None or a == 0:
        return None
    return (b / a - 1.0) * 100.0


def abs_change(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return b - a


def make_event_flags(
    idx: Dict[Tuple[str, str, int], Dict[str, Any]],
    event_date: str,
) -> List[str]:
    """
    Deterministic report-only flags.
    """
    flags: List[str] = []

    # VIX shock
    vix_m5 = safe_float(get_metric(idx, "VIXCLS", event_date, -5, "value"))
    vix_0 = safe_float(get_metric(idx, "VIXCLS", event_date, 0, "value"))
    if vix_m5 is not None and vix_0 is not None:
        dv = abs_change(vix_m5, vix_0)
        pv = pct_change(vix_m5, vix_0)
        if dv is not None and pv is not None:
            if dv >= 10 or pv >= 50:
                flags.append(f"VIX shock: D-5 {vix_m5:.2f} → D0 {vix_0:.2f} (Δ {dv:.2f}, {pv:.1f}%)")

    # HY spread shock
    hy_m5 = safe_float(get_metric(idx, "BAMLH0A0HYM2", event_date, -5, "value"))
    hy_0 = safe_float(get_metric(idx, "BAMLH0A0HYM2", event_date, 0, "value"))
    if hy_m5 is not None and hy_0 is not None:
        dh = abs_change(hy_m5, hy_0)
        ph = pct_change(hy_m5, hy_0)
        if dh is not None and ph is not None:
            if dh >= 0.50 or ph >= 15:
                flags.append(f"HY spread shock: D-5 {hy_m5:.2f} → D0 {hy_0:.2f} (Δ {dh:.2f}, {ph:.1f}%)")

    # Equity drawdown
    spx_m5 = safe_float(get_metric(idx, "SP500", event_date, -5, "value"))
    spx_0 = safe_float(get_metric(idx, "SP500", event_date, 0, "value"))
    if spx_m5 is not None and spx_0 is not None:
        ps = pct_change(spx_m5, spx_0)
        if ps is not None and ps <= -5:
            flags.append(f"SP500 drawdown: D-5 {spx_m5:.2f} → D0 {spx_0:.2f} ({ps:.1f}%)")

    ndx_m5 = safe_float(get_metric(idx, "NASDAQCOM", event_date, -5, "value"))
    ndx_0 = safe_float(get_metric(idx, "NASDAQCOM", event_date, 0, "value"))
    if ndx_m5 is not None and ndx_0 is not None:
        pn = pct_change(ndx_m5, ndx_0)
        if pn is not None and pn <= -6:
            flags.append(f"NASDAQ drawdown: D-5 {ndx_m5:.2f} → D0 {ndx_0:.2f} ({pn:.1f}%)")

    # Oil shock or oil slump
    oil_m5 = safe_float(get_metric(idx, "DCOILWTICO", event_date, -5, "value"))
    oil_0 = safe_float(get_metric(idx, "DCOILWTICO", event_date, 0, "value"))
    if oil_m5 is not None and oil_0 is not None:
        po = pct_change(oil_m5, oil_0)
        if po is not None:
            if po >= 8:
                flags.append(f"Oil shock up: D-5 {oil_m5:.2f} → D0 {oil_0:.2f} ({po:.1f}%)")
            elif po <= -8:
                flags.append(f"Oil shock down: D-5 {oil_m5:.2f} → D0 {oil_0:.2f} ({po:.1f}%)")

    # Financial stress
    stl_0 = safe_float(get_metric(idx, "STLFSI4", event_date, 0, "value"))
    stl_p4 = safe_float(get_metric(idx, "STLFSI4", event_date, 4, "value"))
    if stl_0 is not None and stl_p4 is not None:
        ds = abs_change(stl_0, stl_p4)
        if ds is not None and (stl_p4 > 0.2 or ds >= 0.2):
            flags.append(f"Financial stress up: D0 {stl_0:.4f} → D+4 {stl_p4:.4f} (Δ {ds:.4f})")

    if not flags:
        flags.append("No deterministic major-shock flag triggered by current rule set.")

    return flags


def render_snapshot_table(
    idx: Dict[Tuple[str, str, int], Dict[str, Any]],
    series_id: str,
    event_dates: List[str],
    rel_days: List[int],
) -> str:
    lines: List[str] = []
    lines.append(f"### {series_id}")
    lines.append("")
    header = ["rel_day"]
    for ev in event_dates:
        header.extend([f"{ev} value", f"{ev} status", f"{ev} matched"])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for rd in rel_days:
        row = [str(rd)]
        for ev in event_dates:
            r = get_row(idx, series_id, ev, rd)
            if r is None:
                row.extend(["NA", "NA", "NA"])
            else:
                row.extend([
                    fmt_num(r.get("value")),
                    str(r.get("status", "NA")),
                    str(r.get("matched_date", "NA")),
                ])
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    return "\n".join(lines)


def render_event_meta_section(
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]],
    event_dates: List[str],
    series_ids: List[str],
) -> str:
    lines: List[str] = []
    lines.append("## Event Base / Data Quality")
    lines.append("")
    lines.append("| series_id | event_date | event_matched_date | event_base_gap_days | status_counts |")
    lines.append("|---|---:|---:|---:|---|")

    for s in series_ids:
        for ev in event_dates:
            rows = grouped.get((s, ev), [])
            if not rows:
                lines.append(f"| {s} | {ev} | NA | NA | NA |")
                continue
            first = rows[0]
            event_matched_date = first.get("event_matched_date")
            base_gap = first.get("event_base_gap_days")
            sc = status_count_for_event(rows)
            lines.append(
                f"| {s} | {ev} | {event_matched_date} | {fmt_int(base_gap)} | `{sc}` |"
            )

    lines.append("")
    return "\n".join(lines)


def render_key_comparison_table(
    idx: Dict[Tuple[str, str, int], Dict[str, Any]],
    event_dates: List[str],
) -> str:
    """
    Compare key metrics between first two event dates.
    """
    if len(event_dates) < 2:
        return ""

    ev_a, ev_b = event_dates[0], event_dates[1]
    key_rows = [
        ("BAMLH0A0HYM2", "HY spread", -5, 0),
        ("VIXCLS", "VIX", -5, 0),
        ("SP500", "SP500", -5, 0),
        ("NASDAQCOM", "NASDAQ", -5, 0),
        ("DCOILWTICO", "WTI oil", -5, 0),
        ("DGS10", "10Y yield", -5, 0),
        ("DGS2", "2Y yield", -5, 0),
        ("T10Y2Y", "10Y-2Y", -5, 0),
        ("T10Y3M", "10Y-3M", -5, 0),
        ("STLFSI4", "STLFSI4", 0, 4),
    ]

    lines: List[str] = []
    lines.append("## Direct Comparison: Event A vs Event B")
    lines.append("")
    lines.append(f"- Event A: `{ev_a}`")
    lines.append(f"- Event B: `{ev_b}`")
    lines.append("")
    lines.append("| metric | window | Event A | Event B |")
    lines.append("|---|---|---:|---:|")

    for series_id, label, rd1, rd2 in key_rows:
        a1 = safe_float(get_metric(idx, series_id, ev_a, rd1, "value"))
        a2 = safe_float(get_metric(idx, series_id, ev_a, rd2, "value"))
        b1 = safe_float(get_metric(idx, series_id, ev_b, rd1, "value"))
        b2 = safe_float(get_metric(idx, series_id, ev_b, rd2, "value"))

        if rd1 == rd2:
            win_label = f"D{rd1:+d}"
        else:
            win_label = f"D{rd1:+d} → D{rd2:+d}"

        def cell(v1: Optional[float], v2: Optional[float]) -> str:
            if v1 is None or v2 is None:
                return "NA"
            d = v2 - v1
            if v1 != 0:
                p = (v2 / v1 - 1.0) * 100.0
                return f"{v1:.2f} → {v2:.2f} (Δ {d:.2f}, {p:.1f}%)"
            return f"{v1:.2f} → {v2:.2f} (Δ {d:.2f})"

        lines.append(f"| {label} | {win_label} | {cell(a1, a2)} | {cell(b1, b2)} |")

    lines.append("")
    return "\n".join(lines)


def render_event_flags_section(
    idx: Dict[Tuple[str, str, int], Dict[str, Any]],
    event_dates: List[str],
) -> str:
    lines: List[str] = []
    lines.append("## Deterministic Event Flags")
    lines.append("")
    for ev in event_dates:
        lines.append(f"### {ev}")
        flags = make_event_flags(idx, ev)
        for f in flags:
            lines.append(f"- {f}")
        lines.append("")
    return "\n".join(lines)


def render_summary_section(
    meta: Dict[str, Any],
    results: List[Dict[str, Any]],
) -> str:
    status_counts = Counter(str(r.get("status")) for r in results)
    series_count = len(unique_in_order([str(r.get("series_id")) for r in results]))
    event_count = len(unique_in_order([str(r.get("event_date")) for r in results]))

    lines: List[str] = []
    lines.append("# Event Window Comparison Report")
    lines.append("")
    lines.append("- report_type: `compare_history_lite_event_window_renderer.v1`")
    lines.append(f"- source_json: `{meta.get('source_file', 'NA')}`")
    lines.append(f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- input_generated_at: `{meta.get('generated_at', 'NA')}`")
    lines.append(f"- event_dates: `{meta.get('event_dates', [])}`")
    lines.append(f"- pre_days / post_days: `{meta.get('pre_days', 'NA')}` / `{meta.get('post_days', 'NA')}`")
    lines.append(f"- max_gap_days: `{meta.get('max_gap_days', 'NA')}`")
    lines.append(f"- row_count: `{meta.get('row_count', len(results))}`")
    lines.append(f"- series_count: `{series_count}`")
    lines.append(f"- event_count: `{event_count}`")
    lines.append(f"- status_counts: `{dict(status_counts)}`")
    lines.append("")
    lines.append("## Interpretation Notes")
    lines.append("")
    lines.append("- This file is a **pure render** from event-window JSON; it does not re-fetch or re-compute source data.")
    lines.append("- `STALE_MATCH` means the renderer is showing the latest on-or-before value, but the matched point is older than `max_gap_days` from target date.")
    lines.append("- For low-frequency series, `event_matched_date` may be earlier than `event_date`; check `event_base_gap_days` before drawing strong conclusions.")
    lines.append("- For sign-changing series such as `T10Y3M`, `STLFSI4`, `NFCINONFINLEVERAGE`, percentage changes can be misleading; prioritize level / sign / direction.")
    lines.append("")
    return "\n".join(lines)


def build_report(
    meta: Dict[str, Any],
    focus_series: List[str],
) -> str:
    results = meta.get("results", [])
    if not isinstance(results, list):
        raise ValueError("meta['results'] must be a list")

    idx = build_index(results)
    grouped = group_by_series_event(results)

    event_dates = unique_in_order([str(x) for x in meta.get("event_dates", [])])
    if not event_dates:
        event_dates = unique_in_order([str(r.get("event_date")) for r in results])

    available_series = unique_in_order([str(r.get("series_id")) for r in results])
    final_series = [s for s in focus_series if s in available_series]
    if not final_series:
        final_series = available_series

    parts: List[str] = []
    parts.append(render_summary_section(meta, results))
    parts.append(render_event_flags_section(idx, event_dates))
    parts.append(render_key_comparison_table(idx, event_dates))
    parts.append(render_event_meta_section(grouped, event_dates, final_series))

    parts.append("## Focus Series Snapshots")
    parts.append("")
    for s in final_series:
        parts.append(render_snapshot_table(idx, s, event_dates, DEFAULT_REL_DAYS))

    return "\n".join(parts).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="cache/compare/compare_history_lite_event_window_out.json",
        help="Input JSON path from compare_history_lite_event_window.py",
    )
    parser.add_argument(
        "--output",
        default="cache/compare/report.md",
        help="Output markdown report path",
    )
    parser.add_argument(
        "--focus-series",
        default=",".join(DEFAULT_FOCUS_SERIES),
        help="Comma-separated focus series list",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    meta = load_json(input_path)

    focus_series = [x.strip() for x in str(args.focus_series).split(",") if x.strip()]
    if not focus_series:
        focus_series = DEFAULT_FOCUS_SERIES

    report = build_report(meta, focus_series)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(report)

    print(f"Wrote report: {output_path}")


if __name__ == "__main__":
    main()