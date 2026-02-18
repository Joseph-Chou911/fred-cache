#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build nasdaq_bb_cache/report.md from snippet JSON files.

Inputs (under --cache_dir):
  - snippet_price.json
  - snippet_vxn.json (optional)

Output:
  - report.md (default: <cache_dir>/report.md)

CLI compatibility:
  - Accepts --cache_dir (primary)
  - Also accepts --in_dir / --out_dir as aliases (some workflows use these)

Notes:
- staleness_days computed as: date(snippet.generated_at_utc) - meta.max_date
- staleness_flag: OK if <=2 days else HIGH
- confidence: if staleness_flag != OK => LOW; else by sample_size: <30 LOW, 30-79 MED, >=80 HIGH
- VXN overall confidence: max(conf_A, conf_B)
- This script DOES NOT "fix" snippet metrics; it reports what exists and flags invariant violations.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Any, Dict, Optional, Tuple, List


# -------------------------
# helpers: time / parsing
# -------------------------

def parse_iso_utc(ts: str) -> datetime:
    # Accept "2026-02-18T05:59:48Z" or ISO with offset
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def parse_yyyy_mm_dd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def safe_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def fmt_float(x: Any, nd: int = 4) -> str:
    if x is None:
        return "NA"
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "NA"


def fmt_pct_from_decimal(x: Any, nd: int = 2) -> str:
    """x is decimal, e.g. -0.023 -> -2.30%"""
    if x is None:
        return "NA"
    try:
        return f"{float(x)*100.0:.{nd}f}%"
    except Exception:
        return "NA"


def fmt_pct_from_number(x: Any, nd: int = 2) -> str:
    """x is already in percent points, e.g. 0.781 -> 0.78%"""
    if x is None:
        return "NA"
    try:
        return f"{float(x):.{nd}f}%"
    except Exception:
        return "NA"


def conf_from(staleness_flag: str, n: Optional[int]) -> str:
    if staleness_flag != "OK":
        return "LOW"
    if n is None:
        return "LOW"
    if n < 30:
        return "LOW"
    if n < 80:
        return "MED"
    return "HIGH"


def conf_rank(c: str) -> int:
    return {"LOW": 1, "MED": 2, "HIGH": 3}.get(c, 0)


def max_conf(*cs: str) -> str:
    best = "LOW"
    for c in cs:
        if conf_rank(c) > conf_rank(best):
            best = c
    return best


@dataclass
class Staleness:
    days: Optional[int]
    flag: str


def compute_staleness(snippet_generated_at_utc: str, meta_max_date: Optional[str]) -> Staleness:
    if not snippet_generated_at_utc or not meta_max_date:
        return Staleness(days=None, flag="NA")
    try:
        gen_d = parse_iso_utc(snippet_generated_at_utc).date()
        asof_d = parse_yyyy_mm_dd(meta_max_date)
        days = (gen_d - asof_d).days
        flag = "OK" if days <= 2 else "HIGH"
        return Staleness(days=days, flag=flag)
    except Exception:
        return Staleness(days=None, flag="NA")


# -------------------------
# markdown render helpers
# -------------------------

def md_kv_table(rows: List[Tuple[str, str]]) -> str:
    out = []
    out.append("| field | value |")
    out.append("|---|---:|")
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def md_header_line(k: str, v: str) -> str:
    return f"- {k}: {v}"


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------
# report builders
# -------------------------

def build_price_section(price: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    gen = safe_get(price, "generated_at_utc", "NA")
    meta_max_date = safe_get(price, "meta.max_date", None)
    st = compute_staleness(gen, meta_max_date)

    src = safe_get(price, "meta.source", "NA")
    url = safe_get(price, "meta.url", "NA")

    action = safe_get(price, "action_output", "NA")
    reason = safe_get(price, "trigger_reason", "none")

    latest = safe_get(price, "latest", {}) or {}
    hist = safe_get(price, "historical_simulation", {}) or {}

    n = hist.get("sample_size")
    conf = conf_from(st.flag, n if isinstance(n, int) else None)

    # Invariant check (audit)
    inv_warn = []
    if hist.get("metric") == "forward_mdd":
        # expected <= 0
        for key in ["p10", "p50", "p90", "mean", "max"]:
            v = hist.get(key)
            if isinstance(v, (int, float)) and v > 1e-12:
                inv_warn.append("PRICE forward_mdd has positive values (expected <= 0). Check computation.")
                break

    lines = []
    lines.append("## QQQ (PRICE) — BB(60,2) logclose\n")
    lines.append(md_header_line("snippet.generated_at_utc", f"`{gen}`"))
    lines.append(md_header_line("data_as_of (meta.max_date)", f"`{meta_max_date}`  | staleness_days: `{st.days}`  | staleness_flag: **`{st.flag}`**"))
    lines.append(md_header_line("source", f"`{src}`  | url: `{url}`"))
    lines.append(md_header_line("action_output", f"**`{action}`**"))
    lines.append(md_header_line("trigger_reason", f"`{reason}`"))
    lines.append("")

    # Latest table
    latest_rows = [
        ("date", f"`{latest.get('date','NA')}`"),
        ("close", f"`{fmt_float(latest.get('close'),4)}`"),
        ("bb_mid", f"`{fmt_float(latest.get('bb_mid'),4)}`"),
        ("bb_lower", f"`{fmt_float(latest.get('bb_lower'),4)}`"),
        ("bb_upper", f"`{fmt_float(latest.get('bb_upper'),4)}`"),
        ("z", f"`{fmt_float(latest.get('z'),4)}`"),
        ("trigger_z_le_-2", f"`{bool(latest.get('trigger_z_le_-2', False))}`"),
        ("distance_to_lower_pct", f"`{fmt_pct_from_number(latest.get('distance_to_lower_pct'),3)}`"),
        ("distance_to_upper_pct", f"`{fmt_pct_from_number(latest.get('distance_to_upper_pct'),3)}`"),
        ("position_in_band", f"`{fmt_float(latest.get('position_in_band'),3)}`"),
        ("bandwidth_pct", f"`{fmt_float(latest.get('bandwidth_pct'),4)}`"),
        ("bandwidth_delta_pct", f"`{fmt_pct_from_number(latest.get('bandwidth_delta_pct'),2)}`"),
        ("walk_lower_count", str(latest.get("walk_lower_count", 0))),
    ]
    lines.append("### Latest\n")
    lines.append(md_kv_table(latest_rows))
    lines.append("\n")

    # Historical simulation table
    lines.append("### Historical simulation (conditional)\n")
    lines.append(f"- confidence: **`{conf}`** (sample_size={n} ({'30-79' if isinstance(n,int) and 30 <= n <= 79 else ('<30' if isinstance(n,int) and n < 30 else ('>=80' if isinstance(n,int) and n >= 80 else 'NA')}))\n")
    hist_rows = [
        ("metric", f"`{hist.get('metric','NA')}`"),
        ("metric_interpretation", f"`{hist.get('metric_interpretation','NA')}`"),
        ("z_thresh", f"`{fmt_float(hist.get('z_thresh'),6)}`"),
        ("horizon_days", str(hist.get("horizon_days", "NA"))),
        ("cooldown_bars", str(hist.get("cooldown_bars", "NA"))),
        ("sample_size", str(hist.get("sample_size", "NA"))),
        ("p10", f"`{fmt_float(hist.get('p10'),6)}`"),
        ("p50", f"`{fmt_float(hist.get('p50'),6)}`"),
        ("p90", f"`{fmt_float(hist.get('p90'),6)}`"),
        ("mean", f"`{fmt_float(hist.get('mean'),6)}`"),
        ("min", f"`{fmt_float(hist.get('min'),6)}`"),
        ("max", f"`{fmt_float(hist.get('max'),6)}`"),
    ]
    lines.append(md_kv_table(hist_rows))
    lines.append("\n")

    return "\n".join(lines), {
        "gen": gen,
        "asof": meta_max_date,
        "st": st,
        "action": action,
        "reason": reason,
        "latest": latest,
        "hist": hist,
        "conf": conf,
        "inv_warn": inv_warn,
    }


def build_vxn_section(vxn: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    gen = safe_get(vxn, "generated_at_utc", "NA")
    meta_max_date = safe_get(vxn, "meta.max_date", None)
    st = compute_staleness(gen, meta_max_date)

    src = safe_get(vxn, "meta.source", "NA")
    url = safe_get(vxn, "meta.url", "NA")

    selected_source = safe_get(vxn, "selected_source", "NA")
    fallback_used = safe_get(vxn, "fallback_used", False)

    action = safe_get(vxn, "action_output", "NA")
    reason = safe_get(vxn, "trigger_reason", "none")
    active_regime = safe_get(vxn, "active_regime", "NONE")
    tail_b_applicable = bool(safe_get(vxn, "tail_B_applicable", False))

    latest = safe_get(vxn, "latest", {}) or {}
    hist = safe_get(vxn, "historical_simulation", {}) or {}

    hist_a = hist.get("A", {}) if isinstance(hist.get("A"), dict) else {}
    hist_b = hist.get("B", {}) if isinstance(hist.get("B"), dict) else {}

    nA = hist_a.get("sample_size") if isinstance(hist_a.get("sample_size"), int) else None
    nB = hist_b.get("sample_size") if isinstance(hist_b.get("sample_size"), int) else None

    confA = conf_from(st.flag, nA)
    confB = conf_from(st.flag, nB)
    conf_overall = max_conf(confA, confB)

    # Invariant check (audit)
    inv_warn = []
    # expected >= 0
    for bucket_name, bucket in [("A", hist_a), ("B", hist_b)]:
        if bucket.get("metric") == "forward_max_runup":
            for key in ["p10", "p50", "p90", "mean", "min"]:
                v = bucket.get(key)
                if isinstance(v, (int, float)) and v < -1e-12:
                    inv_warn.append(f"VXN forward_max_runup bucket {bucket_name} has negative values (expected >= 0). Check computation.")
                    break

    lines = []
    lines.append("## VXN (VOL) — BB(60,2) logclose\n")
    lines.append(md_header_line("snippet.generated_at_utc", f"`{gen}`"))
    lines.append(md_header_line("data_as_of (meta.max_date)", f"`{meta_max_date}`  | staleness_days: `{st.days}`  | staleness_flag: **`{st.flag}`**"))
    lines.append(md_header_line("source", f"`{src}`  | url: `{url}`"))
    lines.append(md_header_line("selected_source", f"`{selected_source}` | fallback_used: `{bool(fallback_used)}`"))
    lines.append(md_header_line("action_output", f"**`{action}`**"))
    lines.append(md_header_line("trigger_reason", f"`{reason}`"))
    lines.append(md_header_line("active_regime", f"`{active_regime}`"))
    lines.append(md_header_line("tail_B_applicable", f"`{tail_b_applicable}`"))
    lines.append("")

    latest_rows = [
        ("date", f"`{latest.get('date','NA')}`"),
        ("close", f"`{fmt_float(latest.get('close'),4)}`"),
        ("bb_mid", f"`{fmt_float(latest.get('bb_mid'),4)}`"),
        ("bb_lower", f"`{fmt_float(latest.get('bb_lower'),4)}`"),
        ("bb_upper", f"`{fmt_float(latest.get('bb_upper'),4)}`"),
        ("z", f"`{fmt_float(latest.get('z'),4)}`"),
        ("trigger_z_le_-2 (A_lowvol)", f"`{bool(latest.get('trigger_z_le_-2', False))}`"),
        ("trigger_z_ge_2 (B_highvol)", f"`{bool(latest.get('trigger_z_ge_2', False))}`"),
        ("distance_to_lower_pct", f"`{fmt_pct_from_number(latest.get('distance_to_lower_pct'),3)}`"),
        ("distance_to_upper_pct", f"`{fmt_pct_from_number(latest.get('distance_to_upper_pct'),3)}`"),
        ("position_in_band", f"`{fmt_float(latest.get('position_in_band'),3)}`"),
        ("bandwidth_pct", f"`{fmt_float(latest.get('bandwidth_pct'),4)}`"),
        ("bandwidth_delta_pct", f"`{fmt_pct_from_number(latest.get('bandwidth_delta_pct'),2)}`"),
        ("walk_upper_count", str(latest.get("walk_upper_count", 0))),
    ]
    lines.append("### Latest\n")
    lines.append(md_kv_table(latest_rows))
    lines.append("\n")

    lines.append("### Historical simulation (conditional)\n")

    # A
    lines.append("#### A) Low-Vol / Complacency (z <= threshold)\n")
    lines.append(f"- confidence: **`{confA}`** (sample_size={hist_a.get('sample_size','NA')} ({'<30' if isinstance(nA,int) and nA < 30 else ('30-79' if isinstance(nA,int) and 30 <= nA <= 79 else ('>=80' if isinstance(nA,int) and nA >= 80 else 'NA')}))\n")
    rowsA = [
        ("metric", f"`{hist_a.get('metric','NA')}`"),
        ("metric_interpretation", f"`{hist_a.get('metric_interpretation','NA')}`"),
        ("z_thresh", f"`{fmt_float(hist_a.get('z_thresh'),6)}`"),
        ("horizon_days", str(hist_a.get("horizon_days", "NA"))),
        ("cooldown_bars", str(hist_a.get("cooldown_bars", "NA"))),
        ("sample_size", str(hist_a.get("sample_size", "NA"))),
        ("p10", f"`{fmt_float(hist_a.get('p10'),6)}`"),
        ("p50", f"`{fmt_float(hist_a.get('p50'),6)}`"),
        ("p90", f"`{fmt_float(hist_a.get('p90'),6)}`"),
        ("mean", f"`{fmt_float(hist_a.get('mean'),6)}`"),
        ("min", f"`{fmt_float(hist_a.get('min'),6)}`"),
        ("max", f"`{fmt_float(hist_a.get('max'),6)}`"),
    ]
    lines.append(md_kv_table(rowsA))
    lines.append("\n")

    # B
    lines.append("#### B) High-Vol / Stress (z >= threshold)\n")
    lines.append(f"- confidence: **`{confB}`** (sample_size={hist_b.get('sample_size','NA')} ({'<30' if isinstance(nB,int) and nB < 30 else ('30-79' if isinstance(nB,int) and 30 <= nB <= 79 else ('>=80' if isinstance(nB,int) and nB >= 80 else 'NA')}))\n")
    rowsB = [
        ("metric", f"`{hist_b.get('metric','NA')}`"),
        ("metric_interpretation", f"`{hist_b.get('metric_interpretation','NA')}`"),
        ("z_thresh", f"`{fmt_float(hist_b.get('z_thresh'),6)}`"),
        ("horizon_days", str(hist_b.get("horizon_days", "NA"))),
        ("cooldown_bars", str(hist_b.get("cooldown_bars", "NA"))),
        ("sample_size", str(hist_b.get("sample_size", "NA"))),
        ("p10", f"`{fmt_float(hist_b.get('p10'),6)}`"),
        ("p50", f"`{fmt_float(hist_b.get('p50'),6)}`"),
        ("p90", f"`{fmt_float(hist_b.get('p90'),6)}`"),
        ("mean", f"`{fmt_float(hist_b.get('mean'),6)}`"),
        ("min", f"`{fmt_float(hist_b.get('min'),6)}`"),
        ("max", f"`{fmt_float(hist_b.get('max'),6)}`"),
    ]
    lines.append(md_kv_table(rowsB))
    lines.append("\n")

    return "\n".join(lines), {
        "gen": gen,
        "asof": meta_max_date,
        "st": st,
        "action": action,
        "reason": reason,
        "latest": latest,
        "histA": hist_a,
        "histB": hist_b,
        "confA": confA,
        "confB": confB,
        "conf": conf_overall,
        "active_regime": active_regime,
        "tail_B_applicable": tail_b_applicable,
        "inv_warn": inv_warn,
    }


def build_15s_summary(price_ctx: Dict[str, Any], vxn_ctx: Optional[Dict[str, Any]]) -> str:
    # PRICE summary
    p_date = price_ctx["latest"].get("date", "NA")
    p_close = price_ctx["latest"].get("close", None)
    p_action = price_ctx["action"]
    p_reason = price_ctx["reason"]

    p_dl = fmt_pct_from_number(price_ctx["latest"].get("distance_to_lower_pct"), 3)
    p_du = fmt_pct_from_number(price_ctx["latest"].get("distance_to_upper_pct"), 3)

    p_hist = price_ctx["hist"]
    p50 = fmt_pct_from_decimal(p_hist.get("p50"), 2)
    p10 = fmt_pct_from_decimal(p_hist.get("p10"), 2)
    pmin = fmt_pct_from_decimal(p_hist.get("min"), 2)
    pconf = price_ctx["conf"]

    line_price = (
        f"- **QQQ** ({p_date} close={fmt_float(p_close,4)}) → **{p_action}** "
        f"(reason={p_reason}); dist_to_lower={p_dl}; dist_to_upper={p_du}; "
        f"20D forward_mdd: p50={p50}, p10={p10}, min={pmin} (conf={pconf})"
    )

    # VXN summary (optional)
    if not vxn_ctx:
        return "## 15秒摘要\n\n" + line_price + "\n"

    v_date = vxn_ctx["latest"].get("date", "NA")
    v_close = vxn_ctx["latest"].get("close", None)
    v_action = vxn_ctx["action"]
    v_reason = vxn_ctx["reason"]
    v_z = fmt_float(vxn_ctx["latest"].get("z"), 4)
    v_pos = fmt_float(vxn_ctx["latest"].get("position_in_band"), 3)
    v_bw_delta = fmt_pct_from_number(vxn_ctx["latest"].get("bandwidth_delta_pct"), 2)

    tail_app = bool(vxn_ctx.get("tail_B_applicable", False))
    b_p90 = fmt_pct_from_decimal(vxn_ctx["histB"].get("p90"), 1)
    b_n = vxn_ctx["histB"].get("sample_size", "NA")
    v_conf = vxn_ctx["conf"]

    line_vxn = (
        f"- **VXN** ({v_date} close={fmt_float(v_close,4)}) → **{v_action}** "
        f"(reason={v_reason}); z={v_z}; pos={v_pos}; bwΔ={v_bw_delta}; "
        f"High-Vol tail (B, applicable={'true' if tail_app else 'false'}) p90 runup={b_p90} (n={b_n}) (conf={v_conf})"
    )

    return "## 15秒摘要\n\n" + line_price + "\n" + line_vxn + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default=None, help="Directory containing snippet_*.json; report.md will be written here by default.")
    # Compatibility aliases
    ap.add_argument("--in_dir", default=None, help="Alias of --cache_dir")
    ap.add_argument("--out_dir", default=None, help="Alias of --cache_dir (older workflows)")
    ap.add_argument("--report_path", default=None, help="Explicit output path for report.md (optional)")
    ap.add_argument("--quiet", action="store_true")

    args = ap.parse_args()

    cache_dir = args.cache_dir or args.in_dir or args.out_dir
    if not cache_dir:
        cache_dir = "nasdaq_bb_cache"

    price_path = os.path.join(cache_dir, "snippet_price.json")
    vxn_path = os.path.join(cache_dir, "snippet_vxn.json")

    if not os.path.exists(price_path):
        raise SystemExit(f"Missing required file: {price_path}")

    price = load_json(price_path)
    vxn = load_json(vxn_path) if os.path.exists(vxn_path) else None

    report_path = args.report_path or os.path.join(cache_dir, "report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    price_section, price_ctx = build_price_section(price)
    vxn_section, vxn_ctx = (build_vxn_section(vxn) if vxn else ("", None))

    # warnings
    warnings: List[str] = []
    warnings.extend(price_ctx.get("inv_warn", []))
    if vxn_ctx:
        warnings.extend(vxn_ctx.get("inv_warn", []))

    report_lines = []
    report_lines.append("# Nasdaq BB Monitor Report (QQQ + VXN)\n")
    report_lines.append(f"- report_generated_at_utc: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')}`\n")
    report_lines.append(build_15s_summary(price_ctx, vxn_ctx))
    report_lines.append("\n")
    report_lines.append(price_section)
    report_lines.append("\n")
    if vxn_section:
        report_lines.append(vxn_section)
        report_lines.append("\n")

    report_lines.append("---\n")
    report_lines.append("Notes:\n")
    report_lines.append("- `staleness_days` = snippet 的 `generated_at_utc` 日期 − `meta.max_date`；週末/假期可能放大此值。\n")
    report_lines.append("- PRICE 的 `forward_mdd` **理論上**應永遠 `<= 0`（0 代表未回撤）。\n")
    report_lines.append("- VOL 的 `forward_max_runup` **理論上**應永遠 `>= 0`（數值越大代表波動「再爆衝」風險越大）。\n")
    report_lines.append("- `confidence` 規則：若 `staleness_flag!=OK` 則直接降為 LOW；否則依 sample_size：<30=LOW，30-79=MED，>=80=HIGH。\n")
    report_lines.append("- `trigger_reason` 用於稽核 action_output 被哪條規則觸發。\n")

    if warnings:
        report_lines.append("\n⚠️ Data Quality warnings:\n")
        for w in warnings:
            report_lines.append(f"- {w}\n")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines).rstrip() + "\n")

    if not args.quiet:
        print(report_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())