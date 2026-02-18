#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_nasdaq_bb_report.py

Reads:
- nasdaq_bb_cache/snippet_price_qqq.json
- nasdaq_bb_cache/snippet_vxn.json (optional)

Writes:
- nasdaq_bb_cache/report.md

Changes:
- Render snippet['trigger_reason'] if present (audit-friendly).
- Historical tables will show p10 automatically because it's now in the dict.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Tuple

import pandas as pd


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _utc_now_iso() -> str:
    return pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _staleness_days(snippet_generated_at_utc: str, data_max_date: str) -> Optional[int]:
    try:
        g = pd.to_datetime(snippet_generated_at_utc, utc=True).date()
        d = pd.to_datetime(data_max_date).date()
        return int((g - d).days)
    except Exception:
        return None


def _staleness_flag(days: Optional[int], warn_gt: int = 2) -> str:
    if days is None:
        return "UNKNOWN"
    return "HIGH" if days > warn_gt else "OK"


def _confidence(sample_size: Optional[int], staleness_flag: str) -> Tuple[str, str]:
    if staleness_flag != "OK":
        return "LOW", f"staleness_flag={staleness_flag}"

    if sample_size is None:
        return "UNKNOWN", "sample_size=None"

    try:
        n = int(sample_size)
    except Exception:
        return "UNKNOWN", f"sample_size={sample_size}"

    if n <= 0:
        return "UNKNOWN", "sample_size<=0"
    if n < 30:
        return "LOW", f"sample_size={n} (<30)"
    if n < 80:
        return "MED", f"sample_size={n} (30-79)"
    return "HIGH", f"sample_size={n} (>=80)"


def _fmt_float(x: Any, nd: int = 4) -> str:
    if x is None:
        return ""
    try:
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{v:.{nd}f}"
    except Exception:
        return ""


def _fmt_pct(x: Any, nd: int = 2) -> str:
    if x is None:
        return ""
    try:
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{v:.{nd}f}%"
    except Exception:
        return ""


def _table_kv(d: Dict[str, Any]) -> str:
    lines = ["| field | value |", "|---|---:|"]
    for k, v in d.items():
        if isinstance(v, bool):
            s = f"`{v}`"
        elif isinstance(v, int):
            s = f"{v}"
        elif isinstance(v, float):
            s = f"{v:.6f}"
        elif v is None:
            s = ""
        else:
            s = f"`{v}`"
        lines.append(f"| {k} | {s} |")
    return "\n".join(lines)


def _render_price_section(price: Dict[str, Any]) -> str:
    meta = price.get("meta", {})
    latest = price.get("latest", {})
    gen = price.get("generated_at_utc", "")
    max_date = meta.get("max_date", "")
    stale_days = _staleness_days(gen, max_date)
    stale_flag = _staleness_flag(stale_days)

    hist = price.get("historical_simulation", {}) or {}
    n = hist.get("sample_size")
    conf_level, conf_reason = _confidence(n, stale_flag)

    latest_view = {
        "date": latest.get("date"),
        "close": f"`{_fmt_float(latest.get('close'), 4)}`",
        "bb_mid": f"`{_fmt_float(latest.get('bb_mid'), 4)}`",
        "bb_lower": f"`{_fmt_float(latest.get('bb_lower'), 4)}`",
        "bb_upper": f"`{_fmt_float(latest.get('bb_upper'), 4)}`",
        "z": f"`{_fmt_float(latest.get('z'), 4)}`",
        "trigger_z_le_-2": latest.get("trigger_z_le_-2"),
        "distance_to_lower_pct": f"`{_fmt_pct(latest.get('distance_to_lower_pct'), 3)}`",
        "distance_to_upper_pct": f"`{_fmt_pct(latest.get('distance_to_upper_pct'), 3)}`",
        "position_in_band": f"`{_fmt_float(latest.get('position_in_band'), 3)}`",
        "bandwidth_pct": f"`{_fmt_pct((latest.get('bandwidth_pct') or 0) * 100.0, 2)}`",
        "bandwidth_delta_pct": f"`{_fmt_pct(latest.get('bandwidth_delta_pct'), 2)}`",
        "walk_lower_count": latest.get("walk_lower_count"),
    }

    out = []
    out.append("## QQQ (PRICE) — BB(60,2) logclose\n")
    out.append(f"- snippet.generated_at_utc: `{gen}`")
    out.append(
        f"- data_as_of (meta.max_date): `{max_date}`  | staleness_days: `{stale_days}`  | staleness_flag: **`{stale_flag}`**"
    )
    out.append(f"- source: `{meta.get('source','')}`  | url: `{meta.get('url','')}`")
    out.append(f"- action_output: **`{price.get('action_output','')}`**")
    if "trigger_reason" in price:
        out.append(f"- trigger_reason: `{price.get('trigger_reason')}`\n")
    else:
        out.append("")

    out.append("### Latest\n")
    out.append(_table_kv(latest_view))

    out.append("\n### Historical simulation (conditional)\n")
    out.append(f"- confidence: **`{conf_level}`** ({conf_reason})\n")
    out.append(_table_kv(hist))
    out.append("")
    return "\n".join(out)


def _render_vxn_section(vxn: Dict[str, Any]) -> str:
    meta = vxn.get("meta", {})
    latest = vxn.get("latest", {})
    gen = vxn.get("generated_at_utc", "")
    max_date = meta.get("max_date", "")
    stale_days = _staleness_days(gen, max_date)
    stale_flag = _staleness_flag(stale_days)

    latest_view = {
        "date": latest.get("date"),
        "close": f"`{_fmt_float(latest.get('close'), 4)}`",
        "bb_mid": f"`{_fmt_float(latest.get('bb_mid'), 4)}`",
        "bb_lower": f"`{_fmt_float(latest.get('bb_lower'), 4)}`",
        "bb_upper": f"`{_fmt_float(latest.get('bb_upper'), 4)}`",
        "z": f"`{_fmt_float(latest.get('z'), 4)}`",
        "trigger_z_le_-2 (A_lowvol)": latest.get("trigger_z_le_-2"),
        "trigger_z_ge_2 (B_highvol)": latest.get("trigger_z_ge_2"),
        "distance_to_lower_pct": f"`{_fmt_pct(latest.get('distance_to_lower_pct'), 3)}`",
        "distance_to_upper_pct": f"`{_fmt_pct(latest.get('distance_to_upper_pct'), 3)}`",
        "position_in_band": f"`{_fmt_float(latest.get('position_in_band'), 3)}`",
        "bandwidth_pct": f"`{_fmt_pct((latest.get('bandwidth_pct') or 0) * 100.0, 2)}`",
        "bandwidth_delta_pct": f"`{_fmt_pct(latest.get('bandwidth_delta_pct'), 2)}`",
        "walk_upper_count": latest.get("walk_upper_count"),
    }

    out = []
    out.append("## VXN (VOL) — BB(60,2) logclose\n")
    out.append(f"- snippet.generated_at_utc: `{gen}`")
    out.append(
        f"- data_as_of (meta.max_date): `{max_date}`  | staleness_days: `{stale_days}`  | staleness_flag: **`{stale_flag}`**"
    )
    out.append(f"- source: `{meta.get('source','')}`  | url: `{meta.get('url','')}`")
    if "selected_source" in meta:
        out.append(f"- selected_source: `{meta.get('selected_source')}` | fallback_used: `{meta.get('fallback_used')}`")
    out.append(f"- action_output: **`{vxn.get('action_output','')}`**")
    if "trigger_reason" in vxn:
        out.append(f"- trigger_reason: `{vxn.get('trigger_reason')}`\n")
    else:
        out.append("")

    out.append("### Latest\n")
    out.append(_table_kv(latest_view))

    hist = vxn.get("historical_simulation", {}) or {}
    out.append("### Historical simulation (conditional)\n")

    if isinstance(hist, dict) and ("A_lowvol" in hist or "B_highvol" in hist):
        if "A_lowvol" in hist:
            a = hist["A_lowvol"] or {}
            n_a = a.get("sample_size")
            conf_a, reason_a = _confidence(n_a, stale_flag)
            out.append("#### A) Low-Vol / Complacency (z <= threshold)\n")
            out.append(f"- confidence: **`{conf_a}`** ({reason_a})\n")
            out.append(_table_kv(a))
            out.append("")
        if "B_highvol" in hist:
            b = hist["B_highvol"] or {}
            n_b = b.get("sample_size")
            conf_b, reason_b = _confidence(n_b, stale_flag)
            out.append("#### B) High-Vol / Stress (z >= threshold)\n")
            out.append(f"- confidence: **`{conf_b}`** ({reason_b})\n")
            out.append(_table_kv(b))
            out.append("")
    else:
        n = hist.get("sample_size") if isinstance(hist, dict) else None
        conf, reason = _confidence(n, stale_flag)
        out.append(f"- confidence: **`{conf}`** ({reason})\n")
        out.append(_table_kv(hist if isinstance(hist, dict) else {}))
        out.append("")

    return "\n".join(out)


def build_report(cache_dir: str) -> str:
    price_path = os.path.join(cache_dir, "snippet_price_qqq.json")
    vxn_path = os.path.join(cache_dir, "snippet_vxn.json")

    if not os.path.exists(price_path):
        raise FileNotFoundError(f"Missing: {price_path}")

    price = _read_json(price_path)
    vxn = _read_json(vxn_path) if os.path.exists(vxn_path) else None

    lines = []
    lines.append("# Nasdaq BB Monitor Report (QQQ + VXN)\n")
    lines.append(f"- report_generated_at_utc: `{_utc_now_iso()}`\n")

    lines.append(_render_price_section(price))

    if vxn is not None:
        lines.append("")
        lines.append(_render_vxn_section(vxn))

    lines.append("\n---\nNotes:")
    lines.append("- `staleness_days` = snippet 的 `generated_at_utc` 日期 − `meta.max_date`；週末/假期可能放大此值。")
    lines.append("- PRICE 的 `forward_mdd` 應永遠 `<= 0`（0 代表未回撤）。")
    lines.append("- VOL 的 `forward_max_runup` 應永遠 `>= 0`（數值越大代表波動「再爆衝」風險越大）。")
    lines.append("- `confidence` 規則：若 `staleness_flag!=OK` 則直接降為 LOW；否則依 sample_size：<30=LOW，30-79=MED，>=80=HIGH。")
    lines.append("- `trigger_reason` 用於稽核 action_output 被哪條規則觸發。")
    lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build nasdaq_bb_cache/report.md from snippet JSON",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--cache_dir", default="nasdaq_bb_cache")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    md = build_report(args.cache_dir)

    out_path = os.path.join(args.cache_dir, "report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())