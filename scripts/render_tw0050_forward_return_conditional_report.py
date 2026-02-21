#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_tw0050_forward_return_conditional_report.py

Pure renderer (audit-first):
- Reads forward_return_conditional.json (v6 schema) and renders a standalone Markdown report.
- Does NOT recompute any stats/quantiles/returns.
- NA-safe: missing fields => prints "N/A".
- Optional: read stats_latest.json only to display alignment hints (no recompute).

Example:
  python render_tw0050_forward_return_conditional_report.py \
    --cache_dir tw0050_bb_cache \
    --in_json forward_return_conditional.json \
    --out_md forward_return_conditional_report.md \
    --stats_json stats_latest.json
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple


# ===== Audit stamp =====
BUILD_SCRIPT_FINGERPRINT = "render_tw0050_forward_return_conditional_report@2026-02-21.v1"


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_get(d: Any, path: List[str]) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        if k not in cur:
            return None
        cur = cur[k]
    return cur


def _pick(d: Dict[str, Any], paths: List[List[str]], default: Any = None) -> Any:
    for p in paths:
        v = _safe_get(d, p)
        if v is not None:
            return v
    return default


def _na(x: Any, default: str = "N/A") -> str:
    if x is None:
        return default
    s = str(x)
    return s if s.strip() != "" else default


def _fmt_pct(x: Any, digits: int = 2) -> str:
    try:
        if x is None:
            return "N/A"
        v = float(x) * 100.0
        return f"{v:.{digits}f}%"
    except Exception:
        return "N/A"


def _fmt_float(x: Any, digits: int = 6) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.{digits}f}"
    except Exception:
        return "N/A"


def _fmt_int(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return str(int(x))
    except Exception:
        return "N/A"


def _md_escape(s: str) -> str:
    # Minimal escape for Markdown table cells.
    return s.replace("|", "\\|")


def _table(headers: List[str], rows: List[List[str]]) -> str:
    if not headers:
        return ""
    out = []
    out.append("| " + " | ".join(_md_escape(h) for h in headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        rr = r + [""] * max(0, len(headers) - len(r))
        out.append("| " + " | ".join(_md_escape(_na(c, "")) for c in rr[: len(headers)]) + " |")
    return "\n".join(out)


def _render_meta(meta: Dict[str, Any]) -> str:
    lines = []
    lines.append("## Meta")
    kv = [
        ("generated_at_utc", _na(meta.get("generated_at_utc"))),
        ("build_script_fingerprint", _na(meta.get("build_script_fingerprint"))),
        ("cache_dir", _na(meta.get("cache_dir"))),
        ("price_calc", _na(meta.get("price_calc"))),
        ("stats_last_date", _na(meta.get("stats_last_date"))),
        ("price_last_date", _na(meta.get("price_last_date"))),
        ("rows_price_csv", _na(meta.get("rows_price_csv"))),
        ("price_csv", _na(meta.get("price_csv"))),
        ("stats_json", _na(meta.get("stats_json"))),
        ("out_json", _na(meta.get("out_json"))),
        ("stats_path", _na(meta.get("stats_path"))),
        ("stats_build_fingerprint", _na(meta.get("stats_build_fingerprint"))),
        ("stats_generated_at_utc", _na(meta.get("stats_generated_at_utc"))),
    ]
    for k, v in kv:
        if v != "N/A":
            lines.append(f"- {k}: `{v}`")
    if len(lines) == 2:
        lines.append("- (no meta fields)")
    return "\n".join(lines)


def _render_dq(dq: Dict[str, Any]) -> str:
    lines = []
    lines.append("## Data Quality (DQ)")
    flags = dq.get("flags") if isinstance(dq.get("flags"), list) else []
    notes = dq.get("notes") if isinstance(dq.get("notes"), list) else []
    if flags:
        lines.append("- flags:")
        for f in flags:
            lines.append(f"  - `{_na(f)}`")
    else:
        lines.append("- flags: (none)")
    if notes:
        lines.append("- notes:")
        for n in notes:
            lines.append(f"  - {_na(n)}")
    else:
        lines.append("- notes: (none)")
    return "\n".join(lines)


def _render_policy(frc: Dict[str, Any], decision_mode: Optional[str]) -> str:
    lines = []
    lines.append("## Policy")
    pol = frc.get("policy") if isinstance(frc.get("policy"), dict) else {}
    lines.append(f"- decision_mode: `{_na(pol.get('decision_mode', decision_mode))}`")
    lines.append(f"- raw_usable: `{_na(pol.get('raw_usable'))}`")
    lines.append(f"- raw_policy: `{_na(pol.get('raw_policy'))}`")
    return "\n".join(lines)


def _render_breaks(bd: Dict[str, Any]) -> str:
    lines = []
    lines.append("## Break detection")
    lines.append(
        "- thresholds: "
        f"hi={_fmt_float(bd.get('break_ratio_hi'), 6)}, "
        f"lo={_fmt_float(bd.get('break_ratio_lo'), 10)}"
    )
    lines.append(f"- break_count_stats: `{_na(bd.get('break_count_stats'))}`")
    lines.append(f"- break_count_detected: `{_na(bd.get('break_count_detected'))}`")

    samples = bd.get("break_samples") if isinstance(bd.get("break_samples"), list) else []
    if not samples:
        lines.append("- break_samples: (none)")
        return "\n".join(lines)

    lines.append("")
    lines.append("### break_samples (first up to 5)")
    headers = ["idx", "break_date", "prev_date", "prev_price", "price", "ratio"]
    rows = []
    for s in samples[:5]:
        if not isinstance(s, dict):
            continue
        rows.append(
            [
                _fmt_int(s.get("break_index")),
                _na(s.get("break_date")),
                _na(s.get("prev_date")),
                _fmt_float(s.get("prev_price"), 6),
                _fmt_float(s.get("price"), 6),
                _fmt_float(s.get("ratio"), 12),
            ]
        )
    lines.append(_table(headers, rows))
    return "\n".join(lines)


def _render_current(cur: Dict[str, Any]) -> str:
    lines = []
    lines.append("## Current")
    lines.append(f"- asof_date: `{_na(cur.get('asof_date'))}`")
    lines.append(f"- current_bb_z: `{_fmt_float(cur.get('current_bb_z'), 6)}`")
    lines.append(f"- current_bucket_key: `{_na(cur.get('current_bucket_key'))}`")
    lines.append(f"- current_bucket_canonical: `{_na(cur.get('current_bucket_canonical'))}`")
    return "\n".join(lines)


def _render_horizon_block(hk: str, hv: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"## Horizon {hk}")

    ex = hv.get("excluded_by_break_mask")
    if ex is not None:
        lines.append(f"- excluded_by_break_mask: `{_na(ex)}`")

    # Render Clean summary table (primary)
    clean = hv.get("clean") if isinstance(hv.get("clean"), dict) else {}
    raw = hv.get("raw") if isinstance(hv.get("raw"), dict) else {}

    def _summary_table(obj: Dict[str, Any], title: str, is_primary: bool) -> str:
        sub = []
        sub.append(f"### {title}")
        if is_primary:
            sub.append("_Primary for interpretation (per policy)._")
        else:
            sub.append("_Audit-only._")

        sub.append(f"- definition: `{_na(obj.get('definition'))}`")
        sub.append(f"- n_total: `{_na(obj.get('n_total'))}`")

        by_bucket = obj.get("by_bucket") if isinstance(obj.get("by_bucket"), list) else []
        if not by_bucket:
            sub.append("")
            sub.append("(no by_bucket rows)")
            return "\n".join(sub)

        headers = ["bucket", "n", "hit_rate", "p90", "p50", "p25", "p10", "p05", "min"]
        rows = []
        for r in by_bucket:
            if not isinstance(r, dict):
                continue
            rows.append(
                [
                    _na(r.get("bucket_canonical")),
                    _fmt_int(r.get("n")),
                    _fmt_pct(r.get("hit_rate"), 2),
                    _fmt_pct(r.get("p90"), 2),
                    _fmt_pct(r.get("p50"), 2),
                    _fmt_pct(r.get("p25"), 2),
                    _fmt_pct(r.get("p10"), 2),
                    _fmt_pct(r.get("p05"), 2),
                    _fmt_pct(r.get("min"), 2),
                ]
            )
        sub.append("")
        sub.append(_table(headers, rows))
        return "\n".join(sub)

    def _min_audit(obj: Dict[str, Any], title: str) -> str:
        sub = []
        sub.append(f"### {title} — min_audit_by_bucket")
        mab = obj.get("min_audit_by_bucket") if isinstance(obj.get("min_audit_by_bucket"), list) else []
        if not mab:
            sub.append("(none)")
            return "\n".join(sub)

        headers = [
            "bucket",
            "n",
            "min",
            "entry_date",
            "entry_price",
            "future_date",
            "future_price",
        ]
        rows = []
        for r in mab:
            if not isinstance(r, dict):
                continue
            rows.append(
                [
                    _na(r.get("bucket_canonical")),
                    _fmt_int(r.get("n")),
                    _fmt_pct(r.get("min"), 2),
                    _na(r.get("min_entry_date")),
                    _fmt_float(r.get("min_entry_price"), 6),
                    _na(r.get("min_future_date")),
                    _fmt_float(r.get("min_future_price"), 6),
                ]
            )
        sub.append(_table(headers, rows))
        return "\n".join(sub)

    # Clean first (primary)
    lines.append(_summary_table(clean, "CLEAN", is_primary=True))
    lines.append(_min_audit(clean, "CLEAN"))

    # Raw next (audit-only)
    lines.append(_summary_table(raw, "RAW", is_primary=False))
    lines.append(_min_audit(raw, "RAW"))

    # Optional excluded entries sample
    exs = hv.get("excluded_entries_sample")
    if isinstance(exs, list) and exs:
        lines.append("### excluded_entries_sample (first up to 5)")
        headers = [
            "entry_idx",
            "entry_date",
            "entry_price",
            "first_break_idx",
            "first_break_date",
            "break_ratio",
        ]
        rows = []
        for r in exs[:5]:
            if not isinstance(r, dict):
                continue
            rows.append(
                [
                    _fmt_int(r.get("entry_index")),
                    _na(r.get("entry_date")),
                    _fmt_float(r.get("entry_price"), 6),
                    _fmt_int(r.get("first_break_index_in_window")),
                    _na(r.get("first_break_date_in_window")),
                    _fmt_float(r.get("break_ratio"), 12),
                ]
            )
        lines.append(_table(headers, rows))

    return "\n\n".join(lines)


def _render_alignment_hint(stats: Dict[str, Any], meta: Dict[str, Any], frc_cur: Dict[str, Any]) -> str:
    # Optional: show a small hint if dates mismatch. No failure, only display.
    lines = []
    lines.append("## Alignment hints (optional)")
    stats_last = _pick(stats, [["meta", "last_date"], ["last_date"]], default=None)
    report_stats_last = meta.get("stats_last_date")
    price_last = meta.get("price_last_date")
    cur_asof = frc_cur.get("asof_date")

    if stats_last is None and report_stats_last is None:
        lines.append("- stats_last_date: N/A (stats_json missing or no last_date field)")
        return "\n".join(lines)

    lines.append(f"- stats_last_date (from stats_json): `{_na(stats_last)}`")
    lines.append(f"- stats_last_date (recorded in forward_return_conditional.json): `{_na(report_stats_last)}`")
    lines.append(f"- price_last_date (from forward_return_conditional.json): `{_na(price_last)}`")
    lines.append(f"- current.asof_date (from forward_return_conditional.json): `{_na(cur_asof)}`")

    # Basic mismatch notes
    notes = []
    if stats_last is not None and report_stats_last is not None and str(stats_last) != str(report_stats_last):
        notes.append("stats_last_date mismatch between stats_json and forward_return_conditional.json meta.")
    if report_stats_last is not None and cur_asof is not None and str(report_stats_last) != str(cur_asof):
        notes.append("current.asof_date differs from meta.stats_last_date (check how current_z was sourced).")
    if report_stats_last is not None and price_last is not None and str(report_stats_last) != str(price_last):
        notes.append("price_last_date differs from stats_last_date (possible data lag).")

    if notes:
        lines.append("- notes:")
        for n in notes:
            lines.append(f"  - {n}")
    else:
        lines.append("- notes: (no obvious mismatches detected)")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--in_json", default="forward_return_conditional.json")
    ap.add_argument("--out_md", default="forward_return_conditional_report.md")
    ap.add_argument("--stats_json", default=None, help="Optional. If provided, only used for alignment hints.")
    args = ap.parse_args()

    cache_dir = args.cache_dir
    in_path = os.path.join(cache_dir, args.in_json)
    out_path = os.path.join(cache_dir, args.out_md)
    stats_path = os.path.join(cache_dir, args.stats_json) if args.stats_json else None

    if not os.path.isfile(in_path):
        raise SystemExit(f"ERROR: missing input json: {in_path}")

    doc = _read_json(in_path)
    decision_mode = doc.get("decision_mode")

    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    dq = doc.get("dq") if isinstance(doc.get("dq"), dict) else {}
    frc = doc.get("forward_return_conditional") if isinstance(doc.get("forward_return_conditional"), dict) else {}

    hdr = []
    hdr.append("# 0050 Forward Return Conditional Report")
    hdr.append("")
    hdr.append(f"- renderer_fingerprint: `{BUILD_SCRIPT_FINGERPRINT}`")
    hdr.append(f"- input_json: `{_na(args.in_json)}`")
    if meta.get("generated_at_utc") is not None:
        hdr.append(f"- input_generated_at_utc: `{_na(meta.get('generated_at_utc'))}`")
    if meta.get("build_script_fingerprint") is not None:
        hdr.append(f"- input_build_script_fingerprint: `{_na(meta.get('build_script_fingerprint'))}`")
    hdr.append(f"- decision_mode: `{_na(decision_mode)}`")

    # Forward_return_conditional top fields
    scheme = frc.get("scheme")
    bb_window = frc.get("bb_window")
    bb_k = frc.get("bb_k")
    bb_ddof = frc.get("bb_ddof")
    hdr.append(f"- scheme: `{_na(scheme)}`")
    hdr.append(f"- bb_window,k,ddof: `{_na(bb_window)}`, `{_na(bb_k)}`, `{_na(bb_ddof)}`")

    sections: List[str] = []
    sections.append("\n".join(hdr))
    sections.append(_render_meta(meta))
    sections.append(_render_dq(dq))
    sections.append(_render_policy(frc, decision_mode))

    bd = frc.get("break_detection") if isinstance(frc.get("break_detection"), dict) else {}
    sections.append(_render_breaks(bd))

    cur = frc.get("current") if isinstance(frc.get("current"), dict) else {}
    sections.append(_render_current(cur))

    # Horizons
    horizons = frc.get("horizons") if isinstance(frc.get("horizons"), dict) else {}
    if horizons:
        # Deterministic order if keys like "10D","20D"
        def _hkey(k: str) -> Tuple[int, str]:
            try:
                return (int(k.replace("D", "")), k)
            except Exception:
                return (10**9, k)

        for hk in sorted(horizons.keys(), key=_hkey):
            hv = horizons.get(hk)
            if isinstance(hv, dict):
                sections.append(_render_horizon_block(hk, hv))
    else:
        sections.append("## Horizons\n(no horizons found)")

    # Optional alignment hints
    if stats_path and os.path.isfile(stats_path):
        try:
            stats = _read_json(stats_path)
            sections.append(_render_alignment_hint(stats, meta, cur))
        except Exception:
            sections.append("## Alignment hints (optional)\n- stats_json provided but failed to read/parse.")
    else:
        sections.append("## Alignment hints (optional)\n- stats_json: (not provided)")

    # Write
    body = "\n\n".join(sections).rstrip() + "\n"
    os.makedirs(cache_dir, exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, out_path)
    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()