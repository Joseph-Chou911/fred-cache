#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_nasdaq_bb_report.py

Build a readable Markdown report from:
- nasdaq_bb_cache/snippet_price_qqq.us.json
- nasdaq_bb_cache/snippet_vxn.json

Output:
- nasdaq_bb_cache/report.md  (ONLY)

Enhancements:
- QQQ: add trigger flag (z<=-2), distance_to_lower_pct, position_in_band (0..1)
- VXN: staleness_flag based on staleness_days
- Show attempt_errors (if present) to audit fallback behavior (e.g., CBOE -> FRED).
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone


# ---------------------------
# Formatting helpers
# ---------------------------

def parse_iso_utc(s: str):
    # expects "YYYY-MM-DDTHH:MM:SSZ"
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def fmt_num(x, digits=4):
    if x is None:
        return "NA"
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return "NA"


def fmt_pct_frac(x, digits=2):
    # x is fraction, e.g. 0.123 => 12.3%
    if x is None:
        return "NA"
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except Exception:
        return "NA"


def fmt_pct_point(x, digits=2):
    # x already in percent points, e.g. +12.3 => +12.3%
    if x is None:
        return "NA"
    try:
        return f"{float(x):+.{digits}f}%"
    except Exception:
        return "NA"


def load_json(p: Path):
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def staleness_days(max_date_str: str, gen_ts_utc: datetime):
    try:
        d = datetime.strptime(max_date_str, "%Y-%m-%d").date()
    except Exception:
        return None
    return (gen_ts_utc.date() - d).days


def staleness_flag(days: int | None) -> str:
    """
    Practical flags:
    - None => NA
    - 0..2 => OK
    - 3..4 => WARN
    - >=5  => HIGH
    """
    if days is None:
        return "NA"
    if days <= 2:
        return "OK"
    if days <= 4:
        return "WARN"
    return "HIGH"


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


# ---------------------------
# Derived metrics for QQQ
# ---------------------------

def distance_to_lower_pct(close: float | None, lower: float | None) -> float | None:
    """
    (close - lower) / lower
    """
    if close is None or lower is None:
        return None
    if lower == 0:
        return None
    return (close - lower) / lower


def position_in_band(close: float | None, lower: float | None, upper: float | None) -> float | None:
    """
    (close - lower) / (upper - lower), clipped to [0, 1] if data is sane
    """
    if close is None or lower is None or upper is None:
        return None
    denom = (upper - lower)
    if denom == 0:
        return None
    val = (close - lower) / denom
    # Don't over-polish: keep as-is if NaN
    if val != val:
        return None
    # Clip for readability (but only if finite)
    if val < 0:
        return 0.0
    if val > 1:
        return 1.0
    return val


def add_attempt_errors_block(lines, attempt_errors):
    if not attempt_errors:
        return
    # Render as a collapsible HTML block; GitHub supports <details> in Markdown.
    lines.append("<details>")
    lines.append("<summary>Data source fallback log (attempt_errors)</summary>")
    lines.append("")
    for e in attempt_errors:
        lines.append(f"- {e}")
    lines.append("")
    lines.append("</details>")
    lines.append("")


# ---------------------------
# Section writer
# ---------------------------

def write_section(lines, title: str, obj: dict, section_kind: str):
    """
    section_kind: "price" or "vol"
    """
    lines.append(f"## {title}")
    lines.append("")

    if obj is None:
        lines.append("> NA (snippet not found)")
        lines.append("")
        return

    gen = obj.get("generated_at_utc")
    gen_ts = parse_iso_utc(gen) if gen else datetime.now(timezone.utc)

    meta = obj.get("meta", {}) or {}
    latest = obj.get("latest", {}) or {}
    hist = obj.get("historical_simulation", {}) or {}
    action = obj.get("action_output", "NA")

    max_date = meta.get("max_date", "NA")
    lag = staleness_days(max_date, gen_ts) if max_date != "NA" else None
    lag_flag = staleness_flag(lag)

    lines.append(f"- snippet.generated_at_utc: `{gen}`")
    lines.append(f"- data_as_of (meta.max_date): `{max_date}`  | staleness_days: `{lag if lag is not None else 'NA'}`  | staleness_flag: **`{lag_flag}`**")
    if meta.get("source") or meta.get("url"):
        lines.append(f"- source: `{meta.get('source','NA')}`  | url: `{meta.get('url','NA')}`")
    lines.append(f"- action_output: **`{action}`**")
    lines.append("")

    # If there were fallback attempts, show them
    add_attempt_errors_block(lines, meta.get("attempt_errors"))

    # Latest derived metrics
    close = safe_float(latest.get("close"))
    lower = safe_float(latest.get("bb_lower"))
    upper = safe_float(latest.get("bb_upper"))
    z = safe_float(latest.get("z"))

    trig = None
    if z is not None:
        trig = (z <= -2.0)

    dist_lower = distance_to_lower_pct(close, lower)
    pos_band = position_in_band(close, lower, upper)

    # Latest table
    lines.append("### Latest")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---:|")
    lines.append(f"| date | `{latest.get('date','NA')}` |")
    lines.append(f"| close | {fmt_num(close, 4)} |")
    lines.append(f"| bb_mid | {fmt_num(latest.get('bb_mid'), 4)} |")
    lines.append(f"| bb_lower | {fmt_num(lower, 4)} |")
    lines.append(f"| bb_upper | {fmt_num(upper, 4)} |")
    lines.append(f"| z | {fmt_num(z, 4)} |")
    lines.append(f"| trigger_z_le_-2 | `{trig if trig is not None else 'NA'}` |")

    # Derived fields (only meaningful for price, but harmless for vol too)
    lines.append(f"| distance_to_lower_pct | {fmt_pct_frac(dist_lower, 3)} |")
    lines.append(f"| position_in_band | {fmt_num(pos_band, 3)} |")

    lines.append(f"| bandwidth_pct | {fmt_pct_frac(latest.get('bandwidth_pct'), 2)} |")
    lines.append(f"| bandwidth_delta_pct | {fmt_pct_point(latest.get('bandwidth_delta_pct'), 2)} |")
    lines.append(f"| walk_count | {latest.get('walk_count','NA')} |")
    lines.append("")

    # Extra caution note for VOL staleness
    if section_kind == "vol" and lag is not None and lag > 2:
        lines.append("> ⚠️ VXN data is stale (lag > 2 days). Treat VOL-based interpretation as lower confidence.")
        lines.append("")

    # Historical simulation
    lines.append("### Historical simulation (conditional)")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---:|")
    lines.append(f"| metric | `{hist.get('metric','NA')}` |")
    lines.append(f"| metric_interpretation | `{hist.get('metric_interpretation','NA')}` |")
    lines.append(f"| z_thresh | {hist.get('z_thresh','NA')} |")
    lines.append(f"| horizon_days | {hist.get('horizon_days','NA')} |")
    lines.append(f"| cooldown_bars | {hist.get('cooldown_bars','NA')} |")
    lines.append(f"| sample_size | {hist.get('sample_size','NA')} |")
    lines.append(f"| p50 | {fmt_num(hist.get('p50'), 6)} |")
    lines.append(f"| p90 | {fmt_num(hist.get('p90'), 6)} |")
    lines.append(f"| mean | {fmt_num(hist.get('mean'), 6)} |")
    lines.append(f"| min | {fmt_num(hist.get('min'), 6)} |")
    lines.append(f"| max | {fmt_num(hist.get('max'), 6)} |")
    lines.append("")


# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", default="nasdaq_bb_cache")
    ap.add_argument("--out", default="nasdaq_bb_cache/report.md")
    ap.add_argument("--price_snippet", default="snippet_price_qqq.us.json")
    ap.add_argument("--vxn_snippet", default="snippet_vxn.json")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_path = Path(args.out)

    price = load_json(in_dir / args.price_snippet)
    vxn = load_json(in_dir / args.vxn_snippet)

    now_utc = datetime.now(timezone.utc)

    lines = []
    lines.append("# Nasdaq BB Monitor Report (QQQ + VXN)")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}`")
    lines.append("")

    write_section(lines, "QQQ (PRICE) — BB(60,2) logclose", price, section_kind="price")
    write_section(lines, "VXN (VOL) — BB(60,2) logclose", vxn, section_kind="vol")

    lines.append("---")
    lines.append("Notes:")
    lines.append("- `staleness_days` 以 snippet 的 `generated_at_utc` 日期減 `meta.max_date` 計算；週末/假期可能放大此值。")
    lines.append("- PRICE 的 `historical_simulation.metric=forward_mdd` 應永遠 `<= 0`（0 代表未回撤）。")
    lines.append("- VXN 的 `historical_simulation.metric=forward_max_runup` 應永遠 `>= 0`（數值越大代表波動爆衝風險越大）。")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()