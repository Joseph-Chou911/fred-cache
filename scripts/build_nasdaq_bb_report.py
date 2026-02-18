#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_nasdaq_bb_report.py

Reads:
- nasdaq_bb_cache/snippet_price_qqq.json
- nasdaq_bb_cache/snippet_vxn.json (optional)

Writes:
- nasdaq_bb_cache/report.md

Key usage (Suggestion #2):
- VXN 15s summary displays:
    High-Vol tail (B, applicable=<tail_B_applicable>) ...
- VXN section includes:
    - active_regime
    - tail_B_applicable
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
    try:
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{v:.{nd}f}"
    except Exception:
        return ""


def _fmt_pct(x: Any, nd: int = 3) -> str:
    # x already in percent units
    try:
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{v:.{nd}f}%"
    except Exception:
        return ""


def _md_code(s: Any) -> str:
    if s is None:
        return ""
    if isinstance(s, str) and s.startswith("`") and s.endswith("`"):
        return s
    return f"`{s}`"


def _table_kv(rows: Dict[str, Any]) -> str:
    lines = ["| field | value |", "|---|---:|"]
    for k, v in rows.items():
        if isinstance(v, bool):
            lines.append(f"| {k} | `{v}` |")
        elif isinstance(v, int):
            lines.append(f"| {k} | {v} |")
        elif isinstance(v, float):
            lines.append(f"| {k} | `{v:.6f}` |")
        elif v is None:
            lines.append(f"| {k} |  |")
        else:
            # keep already-backticked strings
            if isinstance(v, str) and v.startswith("`") and v.endswith("`"):
                lines.append(f"| {k} | {v} |")
            else:
                lines.append(f"| {k} | `{v}` |")
    return "\n".join(lines)


def _dd_to_pct(x: Any) -> str:
    try:
        v = float(x) * 100.0
        return f"{v:.2f}%"
    except Exception:
        return ""


def _ru_to_pct(x: Any) -> str:
    try:
        v = float(x) * 100.0
        return f"{v:.1f}%"
    except Exception:
        return ""


def _build_15s_summary(price: Dict[str, Any], vxn: Optional[Dict[str, Any]]) -> str:
    # ---- QQQ line ----
    p_meta = price.get("meta", {}) or {}
    p_latest = price.get("latest", {}) or {}
    p_hist = price.get("historical_simulation", {}) or {}
    p_action = price.get("action_output", "")
    p_reason = price.get("trigger_reason", "")

    p_gen = price.get("generated_at_utc", "")
    p_max_date = p_meta.get("max_date", "")
    p_stale_days = _staleness_days(p_gen, p_max_date)
    p_stale_flag = _staleness_flag(p_stale_days)
    p_conf, _ = _confidence(p_hist.get("sample_size"), p_stale_flag)

    p_date = p_latest.get("date", "")
    p_close = _fmt_float(p_latest.get("close"), 4)
    p_dist_lo = _fmt_pct(p_latest.get("distance_to_lower_pct"), 3)
    p_dist_hi = _fmt_pct(p_latest.get("distance_to_upper_pct"), 3)

    dd_p50 = _dd_to_pct(p_hist.get("p50"))
    dd_p10 = _dd_to_pct(p_hist.get("p10"))
    dd_min = _dd_to_pct(p_hist.get("min"))

    qqq_line = (
        f"- **QQQ** ({p_date} close={p_close}) → **{p_action}**"
        + (f" (reason={p_reason})" if p_reason else "")
        + (f"; dist_to_lower={p_dist_lo}" if p_dist_lo else "")
        + (f"; dist_to_upper={p_dist_hi}" if p_dist_hi else "")
        + (f"; 20D forward_mdd: p50={dd_p50}, p10={dd_p10}, min={dd_min}" if (dd_p50 or dd_p10 or dd_min) else "")
        + f" (conf={p_conf})"
    )

    # ---- VXN line ----
    if not vxn:
        vxn_line = "- **VXN**: (missing) — VOL context not available."
        return "## 15秒摘要\n\n" + qqq_line + "\n" + vxn_line + "\n"

    v_meta = vxn.get("meta", {}) or {}
    v_latest = vxn.get("latest", {}) or {}
    v_hist = vxn.get("historical_simulation", {}) or {}
    v_action = vxn.get("action_output", "")
    v_reason = vxn.get("trigger_reason", "")

    v_gen = vxn.get("generated_at_utc", "")
    v_max_date = v_meta.get("max_date", "")
    v_stale_days = _staleness_days(v_gen, v_max_date)
    v_stale_flag = _staleness_flag(v_stale_days)

    v_date = v_latest.get("date", "")
    v_close = _fmt_float(v_latest.get("close"), 4)
    v_z = _fmt_float(v_latest.get("z"), 4)
    v_pos = _fmt_float(v_latest.get("position_in_band"), 3)
    v_bw_d = _fmt_pct(v_latest.get("bandwidth_delta_pct"), 2)

    # Suggestion #2 usage:
    applicable = vxn.get("tail_B_applicable", None)
    if isinstance(applicable, bool):
        applicable_str = "true" if applicable else "false"
    else:
        applicable_str = "unknown"

    b = None
    if isinstance(v_hist, dict):
        b = v_hist.get("B_highvol", None)

    ru_b_p90 = ""
    b_n = None
    if isinstance(b, dict):
        ru_b_p90 = _ru_to_pct(b.get("p90"))
        b_n = b.get("sample_size")

    # confidence shown in summary: if we reference B tail, use B's confidence; else fallback
    if isinstance(b, dict):
        v_conf, _ = _confidence(b.get("sample_size"), v_stale_flag)
    else:
        v_conf, _ = _confidence(v_hist.get("sample_size") if isinstance(v_hist, dict) else None, v_stale_flag)

    vxn_line = (
        f"- **VXN** ({v_date} close={v_close}) → **{v_action}**"
        + (f" (reason={v_reason})" if v_reason else "")
        + (f"; z={v_z}" if v_z else "")
        + (f"; pos={v_pos}" if v_pos else "")
        + (f"; bwΔ={v_bw_d}" if v_bw_d else "")
        + (f"; High-Vol tail (B, applicable={applicable_str}) p90 runup={ru_b_p90} (n={b_n})" if ru_b_p90 else "")
        + f" (conf={v_conf})"
    )

    return "## 15秒摘要\n\n" + qqq_line + "\n" + vxn_line + "\n"


def _render_price(price: Dict[str, Any]) -> str:
    meta = price.get("meta", {}) or {}
    latest = price.get("latest", {}) or {}
    hist = price.get("historical_simulation", {}) or {}

    gen = price.get("generated_at_utc", "")
    max_date = meta.get("max_date", "")
    stale_days = _staleness_days(gen, max_date)
    stale_flag = _staleness_flag(stale_days)

    conf, conf_reason = _confidence(hist.get("sample_size"), stale_flag)

    latest_view = {
        "date": _md_code(latest.get("date")),
        "close": _md_code(_fmt_float(latest.get("close"), 4)),
        "bb_mid": _md_code(_fmt_float(latest.get("bb_mid"), 4)),
        "bb_lower": _md_code(_fmt_float(latest.get("bb_lower"), 4)),
        "bb_upper": _md_code(_fmt_float(latest.get("bb_upper"), 4)),
        "z": _md_code(_fmt_float(latest.get("z"), 4)),
        "trigger_z_le_-2": latest.get("trigger_z_le_-2"),
        "distance_to_lower_pct": _md_code(_fmt_pct(latest.get("distance_to_lower_pct"), 3)),
        "distance_to_upper_pct": _md_code(_fmt_pct(latest.get("distance_to_upper_pct"), 3)),
        "position_in_band": _md_code(_fmt_float(latest.get("position_in_band"), 3)),
        "bandwidth_pct": _md_code(_fmt_float(latest.get("bandwidth_pct"), 4)),
        "bandwidth_delta_pct": _md_code(_fmt_pct(latest.get("bandwidth_delta_pct"), 2)),
        "walk_lower_count": latest.get("walk_lower_count"),
    }

    out = []
    out.append("## QQQ (PRICE) — BB(60,2) logclose\n")
    out.append(f"- snippet.generated_at_utc: `{gen}`")
    out.append(f"- data_as_of (meta.max_date): `{max_date}`  | staleness_days: `{stale_days}`  | staleness_flag: **`{stale_flag}`**")
    out.append(f"- source: `{meta.get('source','')}`  | url: `{meta.get('url','')}`")
    out.append(f"- action_output: **`{price.get('action_output','')}`**")
    if price.get("trigger_reason"):
        out.append(f"- trigger_reason: `{price.get('trigger_reason')}`\n")
    else:
        out.append("")

    out.append("### Latest\n")
    out.append(_table_kv(latest_view))

    out.append("\n### Historical simulation (conditional)\n")
    out.append(f"- confidence: **`{conf}`** ({conf_reason})\n")
    out.append(_table_kv(hist))
    out.append("")
    return "\n".join(out)


def _render_vxn(vxn: Dict[str, Any]) -> str:
    meta = vxn.get("meta", {}) or {}
    latest = vxn.get("latest", {}) or {}
    hist = vxn.get("historical_simulation", {}) or {}

    gen = vxn.get("generated_at_utc", "")
    max_date = meta.get("max_date", "")
    stale_days = _staleness_days(gen, max_date)
    stale_flag = _staleness_flag(stale_days)

    active_regime = vxn.get("active_regime", "UNKNOWN")
    tail_B_applicable = vxn.get("tail_B_applicable", None)

    latest_view = {
        "date": _md_code(latest.get("date")),
        "close": _md_code(_fmt_float(latest.get("close"), 4)),
        "bb_mid": _md_code(_fmt_float(latest.get("bb_mid"), 4)),
        "bb_lower": _md_code(_fmt_float(latest.get("bb_lower"), 4)),
        "bb_upper": _md_code(_fmt_float(latest.get("bb_upper"), 4)),
        "z": _md_code(_fmt_float(latest.get("z"), 4)),
        "trigger_z_le_-2 (A_lowvol)": latest.get("trigger_z_le_-2"),
        "trigger_z_ge_2 (B_highvol)": latest.get("trigger_z_ge_2"),
        "distance_to_lower_pct": _md_code(_fmt_pct(latest.get("distance_to_lower_pct"), 3)),
        "distance_to_upper_pct": _md_code(_fmt_pct(latest.get("distance_to_upper_pct"), 3)),
        "position_in_band": _md_code(_fmt_float(latest.get("position_in_band"), 3)),
        "bandwidth_pct": _md_code(_fmt_float(latest.get("bandwidth_pct"), 4)),
        "bandwidth_delta_pct": _md_code(_fmt_pct(latest.get("bandwidth_delta_pct"), 2)),
        "walk_upper_count": latest.get("walk_upper_count"),
    }

    out = []
    out.append("## VXN (VOL) — BB(60,2) logclose\n")
    out.append(f"- snippet.generated_at_utc: `{gen}`")
    out.append(f"- data_as_of (meta.max_date): `{max_date}`  | staleness_days: `{stale_days}`  | staleness_flag: **`{stale_flag}`**")
    out.append(f"- source: `{meta.get('source','')}`  | url: `{meta.get('url','')}`")
    if "selected_source" in meta:
        out.append(f"- selected_source: `{meta.get('selected_source')}` | fallback_used: `{meta.get('fallback_used')}`")
    out.append(f"- action_output: **`{vxn.get('action_output','')}`**")
    if vxn.get("trigger_reason"):
        out.append(f"- trigger_reason: `{vxn.get('trigger_reason')}`")
    # Suggestion #2 fields for audit clarity
    out.append(f"- active_regime: `{active_regime}`")
    out.append(f"- tail_B_applicable: `{tail_B_applicable}`\n")

    out.append("### Latest\n")
    out.append(_table_kv(latest_view))

    out.append("### Historical simulation (conditional)\n")

    a = hist.get("A_lowvol") if isinstance(hist, dict) else None
    b = hist.get("B_highvol") if isinstance(hist, dict) else None

    if isinstance(a, dict):
        conf_a, reason_a = _confidence(a.get("sample_size"), stale_flag)
        out.append("#### A) Low-Vol / Complacency (z <= threshold)\n")
        out.append(f"- confidence: **`{conf_a}`** ({reason_a})\n")
        out.append(_table_kv(a))
        out.append("")

    if isinstance(b, dict):
        conf_b, reason_b = _confidence(b.get("sample_size"), stale_flag)
        out.append("#### B) High-Vol / Stress (z >= threshold)\n")
        out.append(f"- confidence: **`{conf_b}`** ({reason_b})\n")
        out.append(_table_kv(b))
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

    lines.append(_build_15s_summary(price, vxn))
    lines.append("")

    lines.append(_render_price(price))

    if vxn is not None:
        lines.append("")
        lines.append(_render_vxn(vxn))

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