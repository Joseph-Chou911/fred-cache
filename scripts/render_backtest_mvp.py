#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_backtest_mvp.py

Render backtest_tw0050_leverage_mvp suite json (lite or full) into a compact Markdown report.

v3 (2026-02-22):
- Compute renderer-side recommendation using a strict, auditable filter:
  * EXCLUDE ok=false
  * EXCLUDE hard_fail (negative equity / MDD <= -100% / negative equity days)
  * EXCLUDE post_go/no-go == NO_GO
  * EXCLUDE missing rank metrics for the chosen rank_basis (post/full)
- Sort table so eligible strategies come first (same policy order), then excluded ones.
- Report both:
  * top3_recommended (renderer computed)
  * top3_raw_from_suite (if provided) for comparison
- Add an Exclusions section with reasons (audit-friendly)
- Keep NA-safe behavior; still works with lite JSON
- Keep Markdown cell escaping for tables
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


SCRIPT_FINGERPRINT = "render_backtest_mvp@2026-02-22.v3.filtered_ranking_v1"


RENDERER_RANK_FILTER_POLICY = (
    "renderer_rank_filter_v1: exclude(ok=false); exclude(hard_fail: equity_min<=0 or "
    "equity_negative_days>0 or mdd<=-100% on full/post); exclude(post_gonogo=NO_GO); "
    "exclude(missing rank metrics on chosen basis)"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise SystemExit("ERROR: input json must be a dict object")
    return obj


def _to_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return v


def _fmt_pct(x: Any, nd: int = 2) -> str:
    v = _to_float(x)
    if v is None:
        return "N/A"
    return f"{v*100:.{nd}f}%"


def _fmt_num(x: Any, nd: int = 3) -> str:
    v = _to_float(x)
    if v is None:
        return "N/A"
    return f"{v:.{nd}f}"


def _fmt_int(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return str(int(x))
    except Exception:
        return "N/A"


def _fmt_str(x: Any) -> str:
    if x is None:
        return "N/A"
    return str(x)


def _escape_md_cell(x: Any) -> str:
    """
    Escape content used inside Markdown tables.
    - Replace '|' to '\\|' to avoid breaking column boundaries
    - Replace newlines with '<br>' so table remains one row
    """
    s = _fmt_str(x)
    s = s.replace("|", "\\|")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return s


def _get(d: Any, path: List[str], default=None):
    cur = d
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _is_true(x: Any) -> bool:
    return x is True


def _strategy_list(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    # suite output: obj["strategies"] list
    if isinstance(obj.get("strategies"), list):
        return [s for s in obj["strategies"] if isinstance(s, dict)]
    # single strategy output fallback: wrap the root
    if "strategy_id" in obj or "perf" in obj:
        return [obj]
    return []


def _leverage_mult_from_params(params: Dict[str, Any]) -> Optional[float]:
    lf = _to_float((params or {}).get("leverage_frac"))
    if lf is None:
        return None
    return 1.0 + lf


def _extract_trades_n(audit: Any) -> Optional[int]:
    """
    audit may contain:
    - trades_n: int
    - trades: list of trade records
    - trades: int (rare)
    We convert into an int count when possible.
    """
    if not isinstance(audit, dict):
        return None

    if "trades_n" in audit:
        try:
            return int(audit.get("trades_n"))
        except Exception:
            return None

    tr = audit.get("trades")
    if tr is None:
        return None
    if isinstance(tr, list):
        return len(tr)
    try:
        return int(tr)
    except Exception:
        return None


def _extract_full_metrics(strat: Dict[str, Any]) -> Dict[str, Any]:
    perf = strat.get("perf") or {}
    lev = perf.get("leverage") or {}
    delta = perf.get("delta_vs_base") or {}
    audit = strat.get("audit") or {}

    return {
        "full_cagr": lev.get("cagr"),
        "full_mdd": lev.get("mdd"),
        "full_sharpe0": lev.get("sharpe0"),
        "full_calmar": perf.get("calmar_leverage"),
        "full_turnover_proxy": perf.get("turnover_proxy"),
        "full_delta_cagr_vs_base": delta.get("cagr"),
        "full_delta_mdd_vs_base": delta.get("mdd"),
        "full_delta_sharpe0_vs_base": delta.get("sharpe0"),
        "full_equity_min": (audit.get("equity_min") if isinstance(audit, dict) else None),
        "full_neg_days": (audit.get("equity_negative_days") if isinstance(audit, dict) else None),
        "trades_n": _extract_trades_n(audit),
    }


def _extract_post_metrics(strat: Dict[str, Any]) -> Dict[str, Any]:
    seg = strat.get("segmentation") or {}
    enabled = bool(seg.get("enabled")) if isinstance(seg, dict) else False
    split_date = seg.get("split_date") if isinstance(seg, dict) else None
    post_start_date = seg.get("post_start_date") if isinstance(seg, dict) else None

    post_seg = _get(seg, ["segments", "post"], default={}) if isinstance(seg, dict) else {}
    post_ok = bool(post_seg.get("ok")) if isinstance(post_seg, dict) else False

    post_sum = (post_seg.get("summary") or {}) if (isinstance(post_seg, dict) and isinstance(post_seg.get("summary"), dict)) else {}
    post_perf = (post_sum.get("perf_leverage") or {}) if isinstance(post_sum.get("perf_leverage"), dict) else {}
    post_delta = (post_sum.get("delta_vs_base") or {}) if isinstance(post_sum.get("delta_vs_base"), dict) else {}
    post_audit = (post_sum.get("audit") or {}) if isinstance(post_sum.get("audit"), dict) else {}

    return {
        "seg_enabled": enabled,
        "split_date": split_date,
        "post_start_date": post_start_date,
        "post_ok": post_ok,
        "post_n_days": post_perf.get("n_days"),
        "post_years": post_perf.get("years"),
        "post_cagr": post_perf.get("cagr"),
        "post_mdd": post_perf.get("mdd"),
        "post_sharpe0": post_perf.get("sharpe0"),
        "post_calmar": post_sum.get("calmar_leverage"),
        "post_delta_cagr_vs_base": post_delta.get("cagr"),
        "post_delta_mdd_vs_base": post_delta.get("mdd"),
        "post_delta_sharpe0_vs_base": post_delta.get("sharpe0"),
        "post_equity_min": post_audit.get("equity_min"),
        "post_neg_days": post_audit.get("equity_negative_days"),
    }


def _extract_gonogo(strat: Dict[str, Any]) -> Dict[str, Any]:
    gg = strat.get("post_gonogo") or {}
    if not isinstance(gg, dict):
        return {"decision": "N/A", "conditions": None, "reasons": None, "rule_id": None}
    return {
        "decision": gg.get("decision", "N/A"),
        "conditions": gg.get("conditions"),
        "reasons": gg.get("reasons"),
        "rule_id": gg.get("rule_id"),
    }


def _rank_basis(post_ok: bool) -> str:
    # keep the same policy label as your suite: post if post_ok else full
    return "post" if post_ok else "full"


def _mk_row(obj: Dict[str, Any], strat: Dict[str, Any]) -> Dict[str, Any]:
    sid = strat.get("strategy_id", "N/A")
    ok = bool(strat.get("ok")) if "ok" in strat else True

    params = strat.get("params") or {}
    entry_mode = (params.get("entry_mode") if isinstance(params, dict) else None)
    L = _leverage_mult_from_params(params)

    full = _extract_full_metrics(strat)
    post = _extract_post_metrics(strat)
    gg = _extract_gonogo(strat)

    post_ok = bool(post.get("post_ok", False))
    basis = _rank_basis(post_ok)

    return {
        "id": sid,
        "ok": ok,
        "entry_mode": entry_mode,
        "L": L,
        **full,
        **post,
        "post_gonogo": gg.get("decision"),
        "post_gonogo_rule": gg.get("rule_id"),
        "post_gonogo_conditions": gg.get("conditions"),
        "post_gonogo_reasons": gg.get("reasons"),
        "rank_basis": basis,
        # renderer annotations (filled later)
        "hard_fail": False,
        "excluded": False,
        "excluded_reasons": [],
        "eligible": False,
    }


def _finite_or_neginf(x: Any) -> float:
    v = _to_float(x)
    return float(v) if v is not None else float("-inf")


def _has_rank_metrics(r: Dict[str, Any]) -> bool:
    """
    Eligible for ranking requires at least one finite metric for the chosen basis:
    - post basis: post_calmar or post_sharpe0
    - full basis: full_calmar or full_sharpe0
    """
    basis = _fmt_str(r.get("rank_basis"))
    if basis == "post":
        c = _to_float(r.get("post_calmar"))
        s = _to_float(r.get("post_sharpe0"))
        return (c is not None) or (s is not None)
    c = _to_float(r.get("full_calmar"))
    s = _to_float(r.get("full_sharpe0"))
    return (c is not None) or (s is not None)


def _hard_fail_reasons(r: Dict[str, Any]) -> List[str]:
    """
    Hard-fail = survival impossible / not meaningful to recommend.
    Uses only fields already present in suite JSON.
    """
    reasons: List[str] = []

    # FULL hard-fail checks
    mdd_full = _to_float(r.get("full_mdd"))   # expected fractional (e.g., -0.75)
    if mdd_full is not None and mdd_full <= -1.0:
        reasons.append("HARD_FAIL_FULL_MDD_LE_-100PCT")

    eqmin_full = _to_float(r.get("full_equity_min"))
    if eqmin_full is not None and eqmin_full <= 0.0:
        reasons.append("HARD_FAIL_FULL_EQUITY_MIN_LE_0")

    neg_full = None
    try:
        neg_full = int(r.get("full_neg_days")) if r.get("full_neg_days") is not None else None
    except Exception:
        neg_full = None
    if neg_full is not None and neg_full > 0:
        reasons.append("HARD_FAIL_FULL_NEG_DAYS_GT_0")

    # POST hard-fail checks (if present)
    mdd_post = _to_float(r.get("post_mdd"))
    if mdd_post is not None and mdd_post <= -1.0:
        reasons.append("HARD_FAIL_POST_MDD_LE_-100PCT")

    eqmin_post = _to_float(r.get("post_equity_min"))
    if eqmin_post is not None and eqmin_post <= 0.0:
        reasons.append("HARD_FAIL_POST_EQUITY_MIN_LE_0")

    neg_post = None
    try:
        neg_post = int(r.get("post_neg_days")) if r.get("post_neg_days") is not None else None
    except Exception:
        neg_post = None
    if neg_post is not None and neg_post > 0:
        reasons.append("HARD_FAIL_POST_NEG_DAYS_GT_0")

    return reasons


def _apply_renderer_filters(rows: List[Dict[str, Any]]) -> None:
    """
    Mutates rows with:
    - hard_fail
    - excluded / excluded_reasons
    - eligible
    """
    for r in rows:
        reasons: List[str] = []

        ok = bool(r.get("ok"))
        if not ok:
            reasons.append("EXCLUDE_OK_FALSE")

        hf = _hard_fail_reasons(r)
        if hf:
            reasons.extend(hf)

        dec = _fmt_str(r.get("post_gonogo"))
        if dec == "NO_GO":
            reasons.append("EXCLUDE_POST_GONOGO_NO_GO")

        if not _has_rank_metrics(r):
            reasons.append("EXCLUDE_MISSING_RANK_METRICS")

        hard_fail = any(x.startswith("HARD_FAIL_") for x in reasons)
        excluded = len(reasons) > 0

        r["hard_fail"] = hard_fail
        r["excluded"] = excluded
        r["excluded_reasons"] = reasons
        r["eligible"] = (not excluded)


def _sort_rows_like_policy(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # prefer post (calmar desc, sharpe0 desc) when post_ok=True; else fallback to full
    def key(r: Dict[str, Any]) -> Tuple[float, float, str]:
        rid = _fmt_str(r.get("id"))  # tie-breaker for deterministic output
        if _is_true(r.get("post_ok")):
            return (_finite_or_neginf(r.get("post_calmar")), _finite_or_neginf(r.get("post_sharpe0")), rid)
        return (_finite_or_neginf(r.get("full_calmar")), _finite_or_neginf(r.get("full_sharpe0")), rid)

    return sorted(rows, key=key, reverse=True)


def _render_md(obj: Dict[str, Any]) -> str:
    gen_at = obj.get("generated_at_utc") or obj.get("generated_at") or obj.get("generated_at_ts")
    fp = obj.get("script_fingerprint") or obj.get("build_script_fingerprint")
    suite_ok = obj.get("suite_ok")
    if suite_ok is None and "ok" in obj:
        suite_ok = obj.get("ok")

    compare = obj.get("compare") or {}
    ranking_policy = compare.get("ranking_policy")
    top3_raw = compare.get("top3_by_policy")

    lines: List[str] = []
    lines.append("# Backtest MVP Summary")
    lines.append("")
    lines.append(f"- generated_at_utc: `{_fmt_str(gen_at)}`")
    lines.append(f"- script_fingerprint: `{_fmt_str(fp)}`")
    lines.append(f"- renderer_fingerprint: `{SCRIPT_FINGERPRINT}`")
    if suite_ok is not None:
        lines.append(f"- suite_ok: `{_fmt_str(suite_ok)}`")
    lines.append("")

    # build rows
    strategies = _strategy_list(obj)
    rows = [_mk_row(obj, s) for s in strategies]
    _apply_renderer_filters(rows)

    eligible = [r for r in rows if r.get("eligible") is True]
    excluded = [r for r in rows if r.get("eligible") is not True]

    eligible_sorted = _sort_rows_like_policy(eligible)
    excluded_sorted = _sort_rows_like_policy(excluded)
    rows_sorted = eligible_sorted + excluded_sorted

    top3_recommended = [r.get("id") for r in eligible_sorted[:3] if r.get("id") is not None]

    # ranking block
    lines.append("## Ranking (policy)")
    lines.append(f"- ranking_policy: `{_fmt_str(ranking_policy)}`")
    lines.append(f"- renderer_filter_policy: `{RENDERER_RANK_FILTER_POLICY}`")

    if top3_recommended:
        lines.append(f"- top3_recommended: `{', '.join([str(x) for x in top3_recommended])}`")
    else:
        lines.append("- top3_recommended: `N/A (no eligible strategies after filters)`")

    # keep raw top3 from suite for comparison (do not treat as recommendation)
    if isinstance(top3_raw, list):
        lines.append(f"- top3_raw_from_suite: `{', '.join([str(x) for x in top3_raw])}`")
    else:
        lines.append(f"- top3_raw_from_suite: `{_fmt_str(top3_raw)}`")
    lines.append("")

    # table header
    lines.append("## Strategies")
    lines.append(
        "| id | ok | entry_mode | L | "
        "full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | "
        "post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔMDD | post_ΔSharpe | "
        "post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades |"
    )
    lines.append(
        "|---|---:|---|---:|"
        "---:|---:|---:|---:|---:|---:|---:|"
        "---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        "---|---|---:|---:|---:|---:|---:|"
    )

    for r in rows_sorted:
        lines.append(
            "| {id} | {ok} | {entry_mode} | {L} | "
            "{full_cagr} | {full_mdd} | {full_sh} | {full_calmar} | {dcagr} | {dmdd} | {dsh} | "
            "{post_ok} | {split} | {post_start} | {post_n} | {post_years} | {post_cagr} | {post_mdd} | {post_sh} | {post_calmar} | {post_dcagr} | {post_dmdd} | {post_dsh} | "
            "{gonogo} | {rank_basis} | {neg_days} | {eq_min} | {post_neg_days} | {post_eq_min} | {trades} |".format(
                id=_escape_md_cell(r.get("id")),
                ok=_escape_md_cell(r.get("ok")),
                entry_mode=_escape_md_cell(r.get("entry_mode")),
                L=_fmt_num(r.get("L"), nd=2) if _to_float(r.get("L")) is not None else "N/A",
                full_cagr=_fmt_pct(r.get("full_cagr")),
                full_mdd=_fmt_pct(r.get("full_mdd")),
                full_sh=_fmt_num(r.get("full_sharpe0"), nd=3),
                full_calmar=_fmt_num(r.get("full_calmar"), nd=3),
                dcagr=_fmt_pct(r.get("full_delta_cagr_vs_base")),
                dmdd=_fmt_pct(r.get("full_delta_mdd_vs_base")),
                dsh=_fmt_num(r.get("full_delta_sharpe0_vs_base"), nd=3),
                post_ok=_escape_md_cell(r.get("post_ok")),
                split=_escape_md_cell(r.get("split_date")),
                post_start=_escape_md_cell(r.get("post_start_date")),
                post_n=_fmt_int(r.get("post_n_days")),
                post_years=_fmt_num(r.get("post_years"), nd=3),
                post_cagr=_fmt_pct(r.get("post_cagr")),
                post_mdd=_fmt_pct(r.get("post_mdd")),
                post_sh=_fmt_num(r.get("post_sharpe0"), nd=3),
                post_calmar=_fmt_num(r.get("post_calmar"), nd=3),
                post_dcagr=_fmt_pct(r.get("post_delta_cagr_vs_base")),
                post_dmdd=_fmt_pct(r.get("post_delta_mdd_vs_base")),
                post_dsh=_fmt_num(r.get("post_delta_sharpe0_vs_base"), nd=3),
                gonogo=_escape_md_cell(r.get("post_gonogo")),
                rank_basis=_escape_md_cell(r.get("rank_basis")),
                neg_days=_fmt_int(r.get("full_neg_days")),
                eq_min=_fmt_num(r.get("full_equity_min"), nd=2),
                post_neg_days=_fmt_int(r.get("post_neg_days")),
                post_eq_min=_fmt_num(r.get("post_equity_min"), nd=2),
                trades=_fmt_int(r.get("trades_n")),
            )
        )

    lines.append("")

    # exclusions summary (audit-friendly)
    lines.append("## Exclusions (not eligible for recommendation)")
    if excluded_sorted:
        # simple counters
        n_total = len(rows)
        n_elig = len(eligible_sorted)
        n_ex = len(excluded_sorted)
        n_hf = sum(1 for r in excluded_sorted if r.get("hard_fail") is True)
        n_nogo = sum(1 for r in excluded_sorted if "EXCLUDE_POST_GONOGO_NO_GO" in (r.get("excluded_reasons") or []))
        n_okfalse = sum(1 for r in excluded_sorted if "EXCLUDE_OK_FALSE" in (r.get("excluded_reasons") or []))
        n_miss = sum(1 for r in excluded_sorted if "EXCLUDE_MISSING_RANK_METRICS" in (r.get("excluded_reasons") or []))

        lines.append(f"- total_strategies: `{n_total}`")
        lines.append(f"- eligible: `{n_elig}`")
        lines.append(f"- excluded: `{n_ex}` (hard_fail={n_hf}, post_NO_GO={n_nogo}, ok_false={n_okfalse}, missing_rank_metrics={n_miss})")
        lines.append("")
        for r in excluded_sorted:
            rid = _escape_md_cell(r.get("id"))
            rs = r.get("excluded_reasons") or []
            rs_s = ", ".join([_escape_md_cell(x) for x in rs]) if rs else "N/A"
            lines.append(f"- {rid}: `{rs_s}`")
        lines.append("")
    else:
        lines.append("- N/A (no exclusions)")
        lines.append("")

    # optional audit appendix: show NO_GO details (conditions/reasons) for transparency
    lines.append("## Post Go/No-Go Details (compact)")
    any_details = False
    for r in rows_sorted:
        dec = r.get("post_gonogo")
        if dec in ("NO_GO", "GO_OR_REVIEW") or _is_true(r.get("post_ok")):
            any_details = True
            lines.append(f"### {_escape_md_cell(r.get('id'))}")
            lines.append(f"- decision: `{_fmt_str(dec)}`")
            rule_id = r.get("post_gonogo_rule")
            if rule_id is not None:
                lines.append(f"- rule_id: `{_fmt_str(rule_id)}`")
            cond = r.get("post_gonogo_conditions")
            if isinstance(cond, dict):
                parts = [f"{k}={v}" for k, v in cond.items()]
                lines.append(f"- conditions: `{', '.join(parts)}`")
            reasons = r.get("post_gonogo_reasons")
            if isinstance(reasons, list) and reasons:
                for msg in reasons[:5]:
                    lines.append(f"  - {str(msg)}")
            lines.append("")
    if not any_details:
        lines.append("- N/A (no post_gonogo details found in JSON)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_json", required=True, help="input json path (lite or full)")
    ap.add_argument("--out_md", required=True, help="output markdown path")
    args = ap.parse_args()

    obj = _read_json(str(args.in_json))
    md = _render_md(obj)

    out_md = str(args.out_md)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)

    print("OK: wrote", out_md)


if __name__ == "__main__":
    main()