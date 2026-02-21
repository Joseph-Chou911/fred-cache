#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


RENDER_FINGERPRINT = "render_tw0050_forward_return_conditional_report@2026-02-21.v2"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _pct(x: Any, nd: int = 2) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x)*100:.{nd}f}%"
    except Exception:
        return "N/A"


def _f(x: Any, nd: int = 6) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.{nd}f}"
    except Exception:
        return "N/A"


def _i(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return str(int(x))
    except Exception:
        return "N/A"


def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        if k not in cur:
            return default
        cur = cur[k]
    return cur


def _parse_inputs(spec: str) -> List[Tuple[str, str]]:
    """
    spec examples:
      - "all:tw0050_bb_cache/forward_return_conditional.json"
      - "all:...json,5y:..._5y.json,3y:..._3y.json"
      - "...json" (label derived from filename)
    """
    out: List[Tuple[str, str]] = []
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for p in parts:
        if ":" in p:
            label, path = p.split(":", 1)
            label = label.strip() or "input"
            path = path.strip()
        else:
            path = p
            base = os.path.basename(path)
            label = os.path.splitext(base)[0]
        out.append((label, path))
    if not out:
        raise SystemExit("ERROR: empty --inputs")
    return out


def _render_bucket_table(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    order = ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]
    rows_by = {r.get("bucket_canonical"): r for r in rows if isinstance(r, dict)}
    for bk in order:
        r = rows_by.get(bk)
        if not r:
            continue
        lines.append(
            "| {bk} | {n} | {hit} | {p90} | {p50} | {p25} | {p10} | {p05} | {mn} |".format(
                bk=bk,
                n=_i(r.get("n")),
                hit=_pct(r.get("hit_rate")),
                p90=_pct(r.get("p90")),
                p50=_pct(r.get("p50")),
                p25=_pct(r.get("p25")),
                p10=_pct(r.get("p10")),
                p05=_pct(r.get("p05")),
                mn=_pct(r.get("min")),
            )
        )
    return "\n".join(lines)


def _render_min_audit_table(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("| bucket | n | min | entry_date | entry_price | future_date | future_price |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    order = ["<=-2", "(-2,-1.5]", "(-1.5,1.5)", "[1.5,2)", ">=2"]
    rows_by = {r.get("bucket_canonical"): r for r in rows if isinstance(r, dict)}
    for bk in order:
        r = rows_by.get(bk)
        if not r:
            continue
        lines.append(
            "| {bk} | {n} | {mn} | {ed} | {ep} | {fd} | {fp} |".format(
                bk=bk,
                n=_i(r.get("n")),
                mn=_pct(r.get("min")),
                ed=str(r.get("min_entry_date", "N/A")),
                ep=_f(r.get("min_entry_price"), 6),
                fd=str(r.get("min_future_date", "N/A")),
                fp=_f(r.get("min_future_price"), 6),
            )
        )
    return "\n".join(lines)


def _find_row_for_bucket(rows: List[Dict[str, Any]], bucket: str) -> Optional[Dict[str, Any]]:
    for r in rows:
        if isinstance(r, dict) and r.get("bucket_canonical") == bucket:
            return r
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--inputs",
        required=True,
        help="Comma list of [label:]path. Example: all:tw0050_bb_cache/forward_return_conditional.json,5y:..._5y.json,3y:..._3y.json",
    )
    ap.add_argument("--out_md", required=True)
    args = ap.parse_args()

    items = _parse_inputs(args.inputs)
    blobs: List[Tuple[str, Dict[str, Any], str]] = []

    for label, path in items:
        if not os.path.isfile(path):
            raise SystemExit(f"ERROR: missing input json: {path}")
        j = _read_json(path)
        blobs.append((label, j, path))

    # choose a "primary" (first) for header fields
    prim = blobs[0][1]

    lines: List[str] = []
    lines.append("# 0050 Forward Return Conditional Report")
    lines.append("")
    lines.append(f"- renderer_fingerprint: `{RENDER_FINGERPRINT}`")
    lines.append(f"- report_generated_at_utc: `{utc_now_iso()}`")
    lines.append(f"- inputs: `{', '.join([f'{lb}:{p}' for lb, _, p in blobs])}`")
    lines.append("")

    # quick compare (current bucket only), if multiple inputs
    if len(blobs) >= 2:
        cur_bucket = _get(prim, ["forward_return_conditional", "current", "current_bucket_canonical"], default=None)
        lines.append("## Compare (current bucket across windows)")
        if cur_bucket is None:
            lines.append("- current_bucket_canonical: `N/A`")
            lines.append("")
        else:
            lines.append(f"- current_bucket_canonical: `{cur_bucket}`")
            lines.append("")
            # per horizon table
            horizons = ["10D", "20D"]
            for hz in horizons:
                lines.append(f"### {hz} (CLEAN) — current bucket")
                lines.append("| window | n | hit_rate | p50 | p05 | min |")
                lines.append("| --- | --- | --- | --- | --- | --- |")
                for label, j, _path in blobs:
                    rows = _get(j, ["forward_return_conditional", "horizons", hz, "clean", "by_bucket"], default=[])
                    r = _find_row_for_bucket(rows, cur_bucket)
                    if not r:
                        lines.append(f"| {label} | N/A | N/A | N/A | N/A | N/A |")
                    else:
                        lines.append(
                            "| {w} | {n} | {hit} | {p50} | {p05} | {mn} |".format(
                                w=label,
                                n=_i(r.get("n")),
                                hit=_pct(r.get("hit_rate")),
                                p50=_pct(r.get("p50")),
                                p05=_pct(r.get("p05")),
                                mn=_pct(r.get("min")),
                            )
                        )
                lines.append("")

    # render each input fully
    for label, j, path in blobs:
        meta = _get(j, ["meta"], default={})
        frc = _get(j, ["forward_return_conditional"], default={})
        dq = _get(j, ["dq"], default={})

        lines.append(f"## Window: {label}")
        lines.append(f"- input_json: `{path}`")
        lines.append(f"- input_generated_at_utc: `{meta.get('generated_at_utc','N/A')}`")
        lines.append(f"- input_build_script_fingerprint: `{meta.get('build_script_fingerprint','N/A')}`")
        lines.append(f"- decision_mode: `{j.get('decision_mode','N/A')}`")
        lines.append(f"- scheme: `{frc.get('scheme','N/A')}`")
        lines.append(f"- bb_window,k,ddof: `{frc.get('bb_window','N/A')}`, `{frc.get('bb_k','N/A')}`, `{frc.get('bb_ddof','N/A')}`")
        lines.append("")

        # Meta
        lines.append("### Meta")
        for k in [
            "cache_dir",
            "price_calc",
            "stats_last_date",
            "price_last_date",
            "rows_price_csv",
            "price_csv",
            "stats_json",
            "out_json",
            "stats_path",
            "stats_build_fingerprint",
            "stats_generated_at_utc",
            "lookback_years",
            "lookback_start_date",
        ]:
            if k in meta:
                lines.append(f"- {k}: `{meta.get(k)}`")
        lines.append("")

        # DQ
        lines.append("### Data Quality (DQ)")
        lines.append("- flags:")
        for f in dq.get("flags", []) or []:
            lines.append(f"  - `{f}`")
        lines.append("- notes:")
        for n in dq.get("notes", []) or []:
            lines.append(f"  - {n}")
        lines.append("")

        # Policy
        pol = frc.get("policy", {}) if isinstance(frc.get("policy", {}), dict) else {}
        lines.append("### Policy")
        lines.append(f"- decision_mode: `{pol.get('decision_mode','N/A')}`")
        lines.append(f"- raw_usable: `{pol.get('raw_usable','N/A')}`")
        lines.append(f"- raw_policy: `{pol.get('raw_policy','N/A')}`")
        lines.append("")

        # Break detection
        bd = frc.get("break_detection", {}) if isinstance(frc.get("break_detection", {}), dict) else {}
        lines.append("### Break detection")
        lines.append(f"- thresholds: hi={_f(bd.get('break_ratio_hi'), 6)}, lo={_f(bd.get('break_ratio_lo'), 10)}")
        lines.append(f"- break_count_stats: `{bd.get('break_count_stats','N/A')}`")
        lines.append(f"- break_count_detected: `{bd.get('break_count_detected','N/A')}`")
        bs = bd.get("break_samples", []) or []
        if bs:
            lines.append("")
            lines.append("#### break_samples (first up to 5)")
            lines.append("| idx | break_date | prev_date | prev_price | price | ratio |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for r in bs[:5]:
                lines.append(
                    "| {i} | {d} | {pd} | {pp} | {p} | {ra} |".format(
                        i=r.get("break_index", "N/A"),
                        d=r.get("break_date", "N/A"),
                        pd=r.get("prev_date", "N/A"),
                        pp=_f(r.get("prev_price"), 6),
                        p=_f(r.get("price"), 6),
                        ra=_f(r.get("ratio"), 12),
                    )
                )
        lines.append("")

        # Current
        cur = frc.get("current", {}) if isinstance(frc.get("current", {}), dict) else {}
        lines.append("### Current")
        lines.append(f"- asof_date: `{cur.get('asof_date','N/A')}`")
        lines.append(f"- current_bb_z: `{_f(cur.get('current_bb_z'), 6)}`")
        lines.append(f"- current_bucket_key: `{cur.get('current_bucket_key','N/A')}`")
        lines.append(f"- current_bucket_canonical: `{cur.get('current_bucket_canonical','N/A')}`")
        lines.append("")

        # Horizons
        hz_map = frc.get("horizons", {}) if isinstance(frc.get("horizons", {}), dict) else {}
        for hz in ["10D", "20D"]:
            if hz not in hz_map:
                continue
            hobj = hz_map.get(hz, {})
            lines.append(f"### Horizon {hz}")
            lines.append(f"- excluded_by_break_mask: `{hobj.get('excluded_by_break_mask','N/A')}`")
            lines.append("")

            # CLEAN
            clean = hobj.get("clean", {})
            lines.append("#### CLEAN")
            lines.append("_Primary for interpretation (per policy)._")
            lines.append(f"- definition: `{_get(clean, ['definition'], 'N/A')}`")
            lines.append(f"- n_total: `{_get(clean, ['n_total'], 'N/A')}`")
            lines.append("")
            lines.append(_render_bucket_table(_get(clean, ["by_bucket"], default=[])))
            lines.append("")
            lines.append("#### CLEAN — min_audit_by_bucket")
            lines.append(_render_min_audit_table(_get(clean, ["min_audit_by_bucket"], default=[])))
            lines.append("")

            # RAW
            raw = hobj.get("raw", {})
            lines.append("#### RAW")
            lines.append("_Audit-only._")
            lines.append(f"- definition: `{_get(raw, ['definition'], 'N/A')}`")
            lines.append(f"- n_total: `{_get(raw, ['n_total'], 'N/A')}`")
            lines.append("")
            lines.append(_render_bucket_table(_get(raw, ["by_bucket"], default=[])))
            lines.append("")
            lines.append("#### RAW — min_audit_by_bucket")
            lines.append(_render_min_audit_table(_get(raw, ["min_audit_by_bucket"], default=[])))
            lines.append("")

            # excluded sample
            es = hobj.get("excluded_entries_sample", []) or []
            if es:
                lines.append("#### excluded_entries_sample (first up to 5)")
                lines.append("| entry_idx | entry_date | entry_price | first_break_idx | first_break_date | break_ratio |")
                lines.append("| --- | --- | --- | --- | --- | --- |")
                for r in es[:5]:
                    lines.append(
                        "| {ei} | {ed} | {ep} | {bi} | {bd} | {br} |".format(
                            ei=r.get("entry_index", "N/A"),
                            ed=r.get("entry_date", "N/A"),
                            ep=_f(r.get("entry_price"), 6),
                            bi=r.get("first_break_index_in_window", "N/A"),
                            bd=r.get("first_break_date_in_window", "N/A"),
                            br=_f(r.get("break_ratio"), 12),
                        )
                    )
                lines.append("")

    # write markdown
    out_md = args.out_md
    out_dir = os.path.dirname(out_md)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    print(f"OK: wrote {out_md}")


if __name__ == "__main__":
    main()