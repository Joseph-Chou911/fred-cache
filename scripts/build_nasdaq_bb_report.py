#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_nasdaq_bb_report.py

Reads:
- nasdaq_bb_cache/snippet_price_qqq.json
- nasdaq_bb_cache/snippet_vxn.json (optional)

Writes:
- nasdaq_bb_cache/report.md

Key audit fixes:
1) 15-second summary chooses the correct VXN historical bucket based on trigger_reason:
   - If trigger_reason indicates position_in_band and C_poswatch exists -> use C_poswatch
   - Else if B_highvol exists -> use B_highvol
   - Else: omit tail line
2) The summary's confidence for VXN matches the selected bucket (not hardwired to B).
3) VXN section renders C_poswatch bucket (if present) with its own confidence.
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
    """Format a number as percent string WITHOUT multiplying (expects already in % units)."""
    if x is None:
        return ""
    try:
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{v:.{nd}f}%"
    except Exception:
        return ""


def _fmt_ratio_to_pct(r: Any, nd: int = 2) -> str:
    """Format ratio (0.0654) to percent string (6.54%)."""
    if r is None:
        return ""
    try:
        v = float(r)
        if pd.isna(v):
            return ""
        return f"{v * 100.0:.{nd}f}%"
    except Exception:
        return ""


def _md_code(s: Any) -> str:
    """Wrap value in markdown inline code backticks, but do not double-wrap if already `...`."""
    if s is None:
        return ""
    if isinstance(s, str) and s.startswith("`") and s.endswith("`"):
        return s
    return f"`{s}`"


def _table_kv(d: Dict[str, Any]) -> str:
    """
    Render a dict as a 2-col markdown table.

    If a value is already a backticked string (e.g. `601.3000`), keep it as-is.
    """
    lines = ["| field | value |", "|---|---:|"]
    for k, v in d.items():
        if isinstance(v, bool):
            s = _md_code(v)
        elif isinstance(v, int):
            s = f"{v}"
        elif isinstance(v, float):
            s = f"{v:.6f}"
        elif v is None:
            s = ""
        else:
            if isinstance(v, str) and v.startswith("`") and v.endswith("`"):
                s = v
            else:
                s = _md_code(v)
        lines.append(f"| {k} | {s} |")
    return "\n".join(lines)


def _build_15s_summary(price: Dict[str, Any], vxn: Optional[Dict[str, Any]]) -> str:
    """
    Build a compact, 15-second summary using existing snippet fields only.
    - QQQ line ends with (conf=...)
    - VXN line ends with a single (conf=...), matched to the referenced bucket.
    """
    # ---- PRICE (QQQ) ----
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

    p_close = _fmt_float(p_latest.get("close"), 4)
    p_date = p_latest.get("date", "")
    p_dist_lo = _fmt_pct(p_latest.get("distance_to_lower_pct"), 3)
    p_dist_hi = _fmt_pct(p_latest.get("distance_to_upper_pct"), 3)

    def _dd_to_pct(x) -> str:
        if x is None:
            return ""
        try:
            v = float(x) * 100.0
            return f"{v:.2f}%"
        except Exception:
            return ""

    dd_p50 = _dd_to_pct(p_hist.get("p50"))
    dd_p10 = _dd_to_pct(p_hist.get("p10"))
    dd_min = _dd_to_pct(p_hist.get("min"))

    price_line = (
        f"- **QQQ** ({p_date} close={p_close}) → **{p_action}**"
        + (f" (reason={p_reason})" if p_reason else "")
        + (f"; dist_to_lower={p_dist_lo}" if p_dist_lo else "")
        + (f"; dist_to_upper={p_dist_hi}" if p_dist_hi else "")
        + (
            f"; 20D forward_mdd: p50={dd_p50}, p10={dd_p10}, min={dd_min}"
            if (dd_p50 or dd_p10 or dd_min)
            else ""
        )
        + f" (conf={p_conf})"
    )

    # ---- VXN (optional) ----
    if not vxn:
        vxn_line = "- **VXN**: (missing) — VOL context not available."
        return "## 15秒摘要\n\n" + price_line + "\n" + vxn_line + "\n"

    v_meta = vxn.get("meta", {}) or {}
    v_latest = vxn.get("latest", {}) or {}
    v_hist = vxn.get("historical_simulation", {}) or {}
    v_action = vxn.get("action_output", "")
    v_reason = vxn.get("trigger_reason", "")

    v_gen = vxn.get("generated_at_utc", "")
    v_max_date = v_meta.get("max_date", "")
    v_stale_days = _staleness_days(v_gen, v_max_date)
    v_stale_flag = _staleness_flag(v_stale_days)

    v_close = _fmt_float(v_latest.get("close"), 4)
    v_date = v_latest.get("date", "")
    v_z = _fmt_float(v_latest.get("z"), 4)
    v_pos = _fmt_float(v_latest.get("position_in_band"), 3)
    v_bw_d = _fmt_pct(v_latest.get("bandwidth_delta_pct"), 2)

    hist_dict = v_hist if isinstance(v_hist, dict) else {}
    c = hist_dict.get("C_poswatch")
    b = hist_dict.get("B_highvol")

    def _ru_to_pct(x) -> str:
        if x is None:
            return ""
        try:
            v = float(x) * 100.0
            return f"{v:.1f}%"
        except Exception:
            return ""

    reason_lc = (v_reason or "").lower()

    # choose bucket
    use_c = False
    if isinstance(c, dict):
        if ("position_in_band" in reason_lc) or ("pos=" in reason_lc):
            use_c = True

    tail_label = ""
    tail_p90 = ""
    tail_n = None
    tail_sample = None

    if use_c:
        tail_label = "Pos-WATCH (C)"
        tail_p90 = _ru_to_pct(c.get("p90"))
        tail_n = c.get("sample_size")
        tail_sample = tail_n
    elif isinstance(b, dict):
        tail_label = "High-Vol tail (B)"
        tail_p90 = _ru_to_pct(b.get("p90"))
        tail_n = b.get("sample_size")
        tail_sample = tail_n

    v_conf, _ = _confidence(tail_sample, v_stale_flag)

    vxn_line = (
        f"- **VXN** ({v_date} close={v_close}) → **{v_action}**"
        + (f" (reason={v_reason})" if v_reason else "")
        + (f"; z={v_z}" if v_z else "")
        + (f"; pos={v_pos}" if v_pos else "")
        + (f"; bwΔ={v_bw_d}" if v_bw_d else "")
        + (f"; {tail_label} p90 runup={tail_p90} (n={tail_n})" if (tail_label and tail_p90) else "")
        + f" (conf={v_conf})"
    )

    return "## 15秒摘要\n\n" + price_line + "\n" + vxn_line + "\n"


def _render_price_section(price: Dict[str, Any]) -> str:
    meta = price.get("meta", {})
    latest = price.get("latest", {}) or {}
    gen = price.get("generated_at_utc", "")
    max_date = meta.get("max_date", "")
    stale_days = _staleness_days(gen, max_date)
    stale_flag = _staleness_flag(stale_days)

    hist = price.get("historical_simulation", {}) or {}
    n = hist.get("sample_size")
    conf_level, conf_reason = _confidence(n, stale_flag)

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
        "bandwidth_pct": _md_code(_fmt_ratio_to_pct(latest.get("bandwidth_pct"), 2)),
        "bandwidth_delta_pct": _md_code(_fmt_pct(latest.get("bandwidth_delta_pct"), 2)),
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
        tr = price.get("trigger_reason") or ""
        out.append(f"- trigger_reason: `{tr}`\n")
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
    latest = vxn.get("latest", {}) or {}
    gen = vxn.get("generated_at_utc", "")
    max_date = meta.get("max_date", "")
    stale_days = _staleness_days(gen, max_date)
    stale_flag = _staleness_flag(stale_days)

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
        "bandwidth_pct": _md_code(_fmt_ratio_to_pct(latest.get("bandwidth_pct"), 2)),
        "bandwidth_delta_pct": _md_code(_fmt_pct(latest.get("bandwidth_delta_pct"), 2)),
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
        tr = vxn.get("trigger_reason") or ""
        out.append(f"- trigger_reason: `{tr}`\n")
    else:
        out.append("")

    out.append("### Latest\n")
    out.append(_table_kv(latest_view))

    hist = vxn.get("historical_simulation", {}) or {}
    out.append("### Historical simulation (conditional)\n")

    if isinstance(hist, dict):
        # C) pos-based watch bucket (if present)
        if "C_poswatch" in hist:
            c = hist["C_poswatch"] or {}
            n_c = c.get("sample_size")
            conf_c, reason_c = _confidence(n_c, stale_flag)
            out.append("#### C) Position-based WATCH (pos >= threshold)\n")
            out.append(f"- confidence: **`{conf_c}`** ({reason_c})\n")
            out.append(_table_kv(c))
            out.append("")

        # A) / B) z-based buckets
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

    # 15-second executive summary
    lines.append(_build_15s_summary(price, vxn))
    lines.append("")

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
    p.add_argument("--cache_dir", "--out_dir", dest="cache_dir", default="nasdaq_bb_cache")
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