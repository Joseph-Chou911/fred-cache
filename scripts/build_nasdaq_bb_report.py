#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_nasdaq_bb_report.py

Reads:
- snippet_price.json
- snippet_vxn.json (optional)

Writes:
- report.md

Formatting-focused:
- Convert bandwidth_pct ratio -> percent for readability
- Compute staleness_days + confidence
- Show B-tail stats with an explicit applicable flag to avoid misleading emphasis
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone, date
from typing import Any, Dict, Optional


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_iso_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.fromisoformat(s).date()


def _staleness_days(generated_at_utc: str, max_date: Optional[str]) -> Optional[int]:
    if not max_date:
        return None
    gen = _parse_iso_dt(generated_at_utc).date()
    md = _parse_date(max_date)
    if not md:
        return None
    return (gen - md).days


def _staleness_flag(days: Optional[int]) -> str:
    if days is None:
        return "NA"
    return "OK" if days <= 2 else "HIGH"


def _confidence(sample_size: Optional[int], staleness_flag: str) -> str:
    if staleness_flag != "OK":
        return "LOW"
    if sample_size is None:
        return "LOW"
    if sample_size < 30:
        return "LOW"
    if sample_size < 80:
        return "MED"
    return "HIGH"


def _fmt_float(v: Any, nd: int = 4) -> str:
    if v is None:
        return "NA"
    try:
        return f"{float(v):.{nd}f}"
    except Exception:
        return "NA"


def _fmt_pct(v: Any, nd: int = 3) -> str:
    if v is None:
        return "NA"
    try:
        return f"{float(v):.{nd}f}%"
    except Exception:
        return "NA"


def _fmt_ratio_as_pct(r: Any, nd: int = 2) -> str:
    if r is None:
        return "NA"
    try:
        return f"{float(r) * 100.0:.{nd}f}%"
    except Exception:
        return "NA"


def build_report(price: Dict[str, Any], vxn: Optional[Dict[str, Any]]) -> str:
    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    p_meta = price.get("meta", {})
    p_latest = price.get("latest", {})
    p_hist = price.get("historical_simulation", {}) or {}
    p_st_days = _staleness_days(price.get("generated_at_utc", now_utc), p_meta.get("max_date"))
    p_st_flag = _staleness_flag(p_st_days)
    p_conf = _confidence(p_hist.get("sample_size"), p_st_flag)

    if vxn:
        v_meta = vxn.get("meta", {})
        v_latest = vxn.get("latest", {})
        v_hist = vxn.get("historical_simulation", {}) or {}
        v_st_days = _staleness_days(vxn.get("generated_at_utc", now_utc), v_meta.get("max_date"))
        v_st_flag = _staleness_flag(v_st_days)
        b = (v_hist.get("B") or {})
        v_conf = _confidence(b.get("sample_size"), v_st_flag)
    else:
        v_meta = v_latest = v_hist = {}
        v_st_days = None
        v_st_flag = "NA"
        v_conf = "NA"

    def _as_pct(x: Any) -> str:
        if x is None:
            return "NA"
        try:
            return f"{float(x) * 100.0:.2f}%"
        except Exception:
            return "NA"

    lines = []
    lines.append("# Nasdaq BB Monitor Report (QQQ + VXN)\n\n")
    lines.append(f"- report_generated_at_utc: `{now_utc}`\n\n")

    lines.append("## 15秒摘要\n\n")

    q_date = p_latest.get("date", "NA")
    q_close = _fmt_float(p_latest.get("close"), 4)
    q_action = price.get("action_output", "NA")
    q_reason = price.get("trigger_reason", "NA")
    q_dl = _fmt_pct(p_latest.get("distance_to_lower_pct"), 3)
    q_du = _fmt_pct(p_latest.get("distance_to_upper_pct"), 3)
    lines.append(
        f"- **QQQ** ({q_date} close={q_close}) → **{q_action}** (reason={q_reason}); "
        f"dist_to_lower={q_dl}; dist_to_upper={q_du}; "
        f"20D forward_mdd: p50={_as_pct(p_hist.get('p50'))}, p10={_as_pct(p_hist.get('p10'))}, "
        f"min={_as_pct(p_hist.get('min'))} (conf={p_conf})\n"
    )

    if vxn:
        v_latest = vxn.get("latest", {})
        v_date = v_latest.get("date", "NA")
        v_close = _fmt_float(v_latest.get("close"), 4)
        v_action = vxn.get("action_output", "NA")
        v_reason = vxn.get("trigger_reason", "NA")
        v_z = _fmt_float(v_latest.get("z"), 4)
        v_pos = _fmt_float(v_latest.get("position_in_band"), 3)
        v_bw_delta = _fmt_pct(v_latest.get("bandwidth_delta_pct"), 2)

        b = (v_hist.get("B") or {})
        tail_app = bool(vxn.get("tail_B_applicable", False))
        lines.append(
            f"- **VXN** ({v_date} close={v_close}) → **{v_action}** (reason={v_reason}); "
            f"z={v_z}; pos={v_pos}; bwΔ={v_bw_delta}; "
            f"High-Vol tail (B, applicable={str(tail_app).lower()}) p90 runup={_as_pct(b.get('p90'))} "
            f"(n={b.get('sample_size','NA')}) (conf={v_conf})\n"
        )
    else:
        lines.append("- **VXN**: disabled\n")

    lines.append("\n\n## QQQ (PRICE) — BB(60,2) logclose\n\n")
    lines.append(f"- snippet.generated_at_utc: `{price.get('generated_at_utc','NA')}`\n")
    lines.append(f"- data_as_of (meta.max_date): `{p_meta.get('max_date','NA')}`  | staleness_days: `{p_st_days}`  | staleness_flag: **`{p_st_flag}`**\n")
    lines.append(f"- source: `{p_meta.get('source','NA')}`  | url: `{p_meta.get('url','NA')}`\n")
    lines.append(f"- action_output: **`{price.get('action_output','NA')}`**\n")
    lines.append(f"- trigger_reason: `{price.get('trigger_reason','NA')}`\n\n")

    lines.append("### Latest\n\n| field | value |\n|---|---:|\n")
    latest_fields = [
        ("date", f"`{p_latest.get('date','NA')}`"),
        ("close", f"`{_fmt_float(p_latest.get('close'),4)}`"),
        ("bb_mid", f"`{_fmt_float(p_latest.get('bb_mid'),4)}`"),
        ("bb_lower", f"`{_fmt_float(p_latest.get('bb_lower'),4)}`"),
        ("bb_upper", f"`{_fmt_float(p_latest.get('bb_upper'),4)}`"),
        ("z", f"`{_fmt_float(p_latest.get('z'),4)}`"),
        ("trigger_z_le_-2", f"`{p_latest.get('trigger_z_le_-2','NA')}`"),
        ("distance_to_lower_pct", f"`{_fmt_pct(p_latest.get('distance_to_lower_pct'),3)}`"),
        ("distance_to_upper_pct", f"`{_fmt_pct(p_latest.get('distance_to_upper_pct'),3)}`"),
        ("position_in_band", f"`{_fmt_float(p_latest.get('position_in_band'),3)}`"),
        ("bandwidth_pct", f"`{_fmt_ratio_as_pct(p_latest.get('bandwidth_pct'),2)}`"),
        ("bandwidth_delta_pct", f"`{_fmt_pct(p_latest.get('bandwidth_delta_pct'),2)}`"),
        ("walk_lower_count", f"`{p_latest.get('walk_lower_count','NA')}`"),
    ]
    for k, v in latest_fields:
        lines.append(f"| {k} | {v} |\n")

    lines.append("\n### Historical simulation (conditional)\n\n")
    lines.append(f"- confidence: **`{p_conf}`** (sample_size={p_hist.get('sample_size','NA')})\n\n")
    lines.append("| field | value |\n|---|---:|\n")
    for k in ["metric","metric_interpretation","z_thresh","horizon_days","cooldown_bars","sample_size","p10","p50","p90","mean","min","max"]:
        val = p_hist.get(k, "NA")
        if isinstance(val, float):
            lines.append(f"| {k} | `{val:.6f}` |\n")
        else:
            lines.append(f"| {k} | `{val}` |\n")

    if vxn:
        v_meta = vxn.get("meta", {})
        v_latest = vxn.get("latest", {})
        v_hist = vxn.get("historical_simulation", {}) or {}
        lines.append("\n\n## VXN (VOL) — BB(60,2) logclose\n\n")
        lines.append(f"- snippet.generated_at_utc: `{vxn.get('generated_at_utc','NA')}`\n")
        lines.append(f"- data_as_of (meta.max_date): `{v_meta.get('max_date','NA')}`  | staleness_days: `{v_st_days}`  | staleness_flag: **`{v_st_flag}`**\n")
        lines.append(f"- source: `{v_meta.get('source','NA')}`  | url: `{v_meta.get('url','NA')}`\n")
        lines.append(f"- selected_source: `{vxn.get('selected_source','NA')}` | fallback_used: `{vxn.get('fallback_used','NA')}`\n")
        lines.append(f"- action_output: **`{vxn.get('action_output','NA')}`**\n")
        lines.append(f"- trigger_reason: `{vxn.get('trigger_reason','NA')}`\n")
        lines.append(f"- active_regime: `{vxn.get('active_regime','NA')}`\n")
        lines.append(f"- tail_B_applicable: `{vxn.get('tail_B_applicable','NA')}`\n\n")

        lines.append("### Latest\n\n| field | value |\n|---|---:|\n")
        v_latest_fields = [
            ("date", f"`{v_latest.get('date','NA')}`"),
            ("close", f"`{_fmt_float(v_latest.get('close'),4)}`"),
            ("bb_mid", f"`{_fmt_float(v_latest.get('bb_mid'),4)}`"),
            ("bb_lower", f"`{_fmt_float(v_latest.get('bb_lower'),4)}`"),
            ("bb_upper", f"`{_fmt_float(v_latest.get('bb_upper'),4)}`"),
            ("z", f"`{_fmt_float(v_latest.get('z'),4)}`"),
            ("trigger_z_le_-2 (A_lowvol)", f"`{v_latest.get('trigger_z_le_-2','NA')}`"),
            ("trigger_z_ge_2 (B_highvol)", f"`{v_latest.get('trigger_z_ge_2','NA')}`"),
            ("distance_to_lower_pct", f"`{_fmt_pct(v_latest.get('distance_to_lower_pct'),3)}`"),
            ("distance_to_upper_pct", f"`{_fmt_pct(v_latest.get('distance_to_upper_pct'),3)}`"),
            ("position_in_band", f"`{_fmt_float(v_latest.get('position_in_band'),3)}`"),
            ("bandwidth_pct", f"`{_fmt_ratio_as_pct(v_latest.get('bandwidth_pct'),2)}`"),
            ("bandwidth_delta_pct", f"`{_fmt_pct(v_latest.get('bandwidth_delta_pct'),2)}`"),
            ("walk_upper_count", f"`{v_latest.get('walk_upper_count','NA')}`"),
        ]
        for k, v in v_latest_fields:
            lines.append(f"| {k} | {v} |\n")

        lines.append("\n### Historical simulation (conditional)\n\n")

        def _render_block(title: str, blk: Dict[str, Any], conf: str) -> None:
            lines.append(f"#### {title}\n\n")
            lines.append(f"- confidence: **`{conf}`** (sample_size={blk.get('sample_size','NA')})\n\n")
            lines.append("| field | value |\n|---|---:|\n")
            for k in ["metric","metric_interpretation","z_thresh","horizon_days","cooldown_bars","sample_size","p10","p50","p90","mean","min","max"]:
                val = blk.get(k, "NA")
                if isinstance(val, float):
                    lines.append(f"| {k} | `{val:.6f}` |\n")
                else:
                    lines.append(f"| {k} | `{val}` |\n")

        a = (v_hist.get("A") or {})
        b = (v_hist.get("B") or {})
        a_conf = _confidence(a.get("sample_size"), v_st_flag)
        b_conf = _confidence(b.get("sample_size"), v_st_flag)
        _render_block("A) Low-Vol / Complacency (z <= threshold)", a, a_conf)
        lines.append("\n")
        _render_block("B) High-Vol / Stress (z >= threshold)", b, b_conf)

    lines.append("\n\n---\nNotes:\n")
    lines.append("- `staleness_days` = snippet 的 `generated_at_utc` 日期 − `meta.max_date`；週末/假期可能放大此值。\n")
    lines.append("- PRICE 的 `forward_mdd` 應永遠 `<= 0`（0 代表未回撤）。\n")
    lines.append("- VOL 的 `forward_max_runup` 應永遠 `>= 0`（數值越大代表波動「再爆衝」風險越大）。\n")
    lines.append("- `confidence` 規則：若 `staleness_flag!=OK` 則直接降為 LOW；否則依 sample_size：<30=LOW，30-79=MED，>=80=HIGH。\n")
    lines.append("- `trigger_reason` 用於稽核 action_output 被哪條規則觸發。\n")
    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", default="nasdaq_bb_cache")
    ap.add_argument("--out_md", default=None)
    ap.add_argument("--price_snippet", default=None)
    ap.add_argument("--vxn_snippet", default=None)
    args = ap.parse_args()

    in_dir = args.in_dir
    out_md = args.out_md or os.path.join(in_dir, "report.md")
    price_path = args.price_snippet or os.path.join(in_dir, "snippet_price.json")
    vxn_path = args.vxn_snippet or os.path.join(in_dir, "snippet_vxn.json")

    price = _read_json(price_path)
    vxn = _read_json(vxn_path) if os.path.exists(vxn_path) else None

    md = build_report(price, vxn)
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())