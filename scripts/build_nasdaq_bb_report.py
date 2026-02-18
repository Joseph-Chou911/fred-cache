#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

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
        return f"{float(x)*100:.{digits}f}%"
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

def staleness_days(max_date_str: str, gen_ts_utc: datetime):
    try:
        d = datetime.strptime(max_date_str, "%Y-%m-%d").date()
    except Exception:
        return "NA"
    return (gen_ts_utc.date() - d).days

def load_json(p: Path):
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def write_section(lines, title: str, obj: dict):
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
    lag = staleness_days(max_date, gen_ts) if max_date != "NA" else "NA"

    lines.append(f"- snippet.generated_at_utc: `{gen}`")
    lines.append(f"- data_as_of (meta.max_date): `{max_date}`  | staleness_days: `{lag}`")
    if meta.get("source") or meta.get("url"):
        lines.append(f"- source: `{meta.get('source','NA')}`  | url: `{meta.get('url','NA')}`")
    lines.append(f"- action_output: **`{action}`**")
    lines.append("")

    # Latest
    lines.append("### Latest")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---:|")
    lines.append(f"| date | `{latest.get('date','NA')}` |")
    lines.append(f"| close | {fmt_num(latest.get('close'), 4)} |")
    lines.append(f"| bb_mid | {fmt_num(latest.get('bb_mid'), 4)} |")
    lines.append(f"| bb_lower | {fmt_num(latest.get('bb_lower'), 4)} |")
    lines.append(f"| bb_upper | {fmt_num(latest.get('bb_upper'), 4)} |")
    lines.append(f"| z | {fmt_num(latest.get('z'), 4)} |")
    lines.append(f"| bandwidth_pct | {fmt_pct_frac(latest.get('bandwidth_pct'), 2)} |")
    lines.append(f"| bandwidth_delta_pct | {fmt_pct_point(latest.get('bandwidth_delta_pct'), 2)} |")
    lines.append(f"| walk_count | {latest.get('walk_count','NA')} |")
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

    write_section(lines, "QQQ (PRICE) — BB(60,2) logclose", price)
    write_section(lines, "VXN (VOL) — BB(60,2) logclose", vxn)

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