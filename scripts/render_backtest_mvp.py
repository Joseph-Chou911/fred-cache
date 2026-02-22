#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_backtest_mvp.py

Render backtest_tw0050_leverage_mvp suite json (lite or full) into a compact Markdown report.

v4 (2026-02-23):
- Filtered ranking (renderer_rank_filter_v2):
  * exclude(ok=false)
  * exclude(hard_fail):
      - full/post: equity_min<=0 OR equity_negative_days>0 OR mdd<=-100%
      - basis_fail: (rank_basis segment) equity_min<=0.5  (asset equity down 50% from start => FAIL)
  * exclude(post_gonogo=NO_GO)
  * exclude(missing rank metrics on chosen basis)
- Emit top3_recommended and exclusions summary
- Add deterministic always-vs-trend comparison block with checkmarks on POST basis when available
- Add FULL segment caveat note: FULL_* metrics may be contaminated by known data singularity around 2014;
  treat FULL as audit-only and prefer POST for decision.
- Keep NA-safe behavior; still works with lite JSON (no trades details required)
- Escape Markdown table cells to avoid breaking tables (| and newlines)
- Deterministic sorting tie-breaker by strategy_id
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


SCRIPT_FINGERPRINT = "render_backtest_mvp@2026-02-23.v4.filtered_ranking_v2.fail_eq50.full_note.compare_v1"

# === Deterministic thresholds (audit-grade) ===
# "Exploded / invalid" hard-fail on full/post (kept from prior renderer policy)
HARD_FAIL_MDD_LE_NEG_100 = -1.0  # -100%
HARD_FAIL_EQUITY_MIN_LE = 0.0
HARD_FAIL_NEG_DAYS_GT = 0

# New: "asset equity down 50% from start => fail" on rank_basis segment
BASIS_FAIL_EQUITY_MIN_LE_0_5 = 0.5  # equity_min <= 0.5


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
    if isinstance(obj.get("strategies"), list):
        return [s for s in obj["strategies"] if isinstance(s, dict)]
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
    return "post" if post_ok else "full"


def _mk_row(strat: Dict[str, Any]) -> Dict[str, Any]:
    sid = strat.get("strategy_id", "N/A")
    ok = bool(strat.get("ok")) if "ok" in strat else True

    params = strat.get("params") or {}
    entry_mode = (params.get("entry_mode") if isinstance(params, dict) else None)
    L = _leverage_mult_from_params(params)

    full = _extract_full_metrics(strat)
    post = _extract_post_metrics(strat)
    gg = _extract_gonogo(strat)

    basis = _rank_basis(bool(post.get("post_ok")))

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
    }


def _finite_or_neginf(x: Any) -> float:
    v = _to_float(x)
    return float(v) if v is not None else float("-inf")


def _sort_rows_like_policy(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Policy:
    prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full
    Deterministic tie-breaker by strategy_id.
    """
    def key(r: Dict[str, Any]) -> Tuple[float, float, str]:
        rid = _fmt_str(r.get("id"))
        if _is_true(r.get("post_ok")):
            return (_finite_or_neginf(r.get("post_calmar")), _finite_or_neginf(r.get("post_sharpe0")), rid)
        return (_finite_or_neginf(r.get("full_calmar")), _finite_or_neginf(r.get("full_sharpe0")), rid)

    return sorted(rows, key=key, reverse=True)


def _has_rank_metrics(r: Dict[str, Any]) -> bool:
    if r.get("rank_basis") == "post":
        return _to_float(r.get("post_calmar")) is not None and _to_float(r.get("post_sharpe0")) is not None
    return _to_float(r.get("full_calmar")) is not None and _to_float(r.get("full_sharpe0")) is not None


def _hard_fail_full_post_reasons(r: Dict[str, Any]) -> List[str]:
    """
    Exploded/invalid conditions checked on BOTH full and post (kept from prior policy).
    """
    reasons: List[str] = []

    full_mdd = _to_float(r.get("full_mdd"))
    if full_mdd is not None and full_mdd <= HARD_FAIL_MDD_LE_NEG_100:
        reasons.append("HARD_FAIL_FULL_MDD_LE_-100PCT")

    full_eqmin = _to_float(r.get("full_equity_min"))
    if full_eqmin is not None and full_eqmin <= HARD_FAIL_EQUITY_MIN_LE:
        reasons.append("HARD_FAIL_FULL_EQUITY_MIN_LE_0")

    full_neg = _to_float(r.get("full_neg_days"))
    if full_neg is not None and full_neg > HARD_FAIL_NEG_DAYS_GT:
        reasons.append("HARD_FAIL_FULL_NEG_DAYS_GT_0")

    post_mdd = _to_float(r.get("post_mdd"))
    if post_mdd is not None and post_mdd <= HARD_FAIL_MDD_LE_NEG_100:
        reasons.append("HARD_FAIL_POST_MDD_LE_-100PCT")

    post_eqmin = _to_float(r.get("post_equity_min"))
    if post_eqmin is not None and post_eqmin <= HARD_FAIL_EQUITY_MIN_LE:
        reasons.append("HARD_FAIL_POST_EQUITY_MIN_LE_0")

    post_neg = _to_float(r.get("post_neg_days"))
    if post_neg is not None and post_neg > HARD_FAIL_NEG_DAYS_GT:
        reasons.append("HARD_FAIL_POST_NEG_DAYS_GT_0")

    return reasons


def _basis_fail_reasons(r: Dict[str, Any]) -> List[str]:
    """
    New rule: asset equity down 50% from start => FAIL (equity_min <= 0.5) on rank_basis segment.
    This matches a practical "I would stop / forced de-risk" threshold more directly than MDD.
    """
    reasons: List[str] = []
    if r.get("rank_basis") == "post":
        e = _to_float(r.get("post_equity_min"))
        if e is not None and e <= BASIS_FAIL_EQUITY_MIN_LE_0_5:
            reasons.append("HARD_FAIL_BASIS_POST_EQUITY_MIN_LE_0_5")
    else:
        e = _to_float(r.get("full_equity_min"))
        if e is not None and e <= BASIS_FAIL_EQUITY_MIN_LE_0_5:
            reasons.append("HARD_FAIL_BASIS_FULL_EQUITY_MIN_LE_0_5")
    return reasons


def _filter_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]], Dict[str, int]]:
    """
    renderer_rank_filter_v2:
    - exclude ok=false
    - exclude hard_fail (full/post exploded) + basis_fail(equity_min<=0.5)
    - exclude post_gonogo=NO_GO
    - exclude missing rank metrics on chosen basis
    """
    excluded: Dict[str, List[str]] = {}
    counters = {
        "hard_fail_fullpost": 0,
        "basis_fail_eq50": 0,
        "post_NO_GO": 0,
        "ok_false": 0,
        "missing_rank_metrics": 0,
    }

    eligible: List[Dict[str, Any]] = []

    for r in rows:
        sid = _fmt_str(r.get("id"))
        reasons: List[str] = []

        if not _is_true(r.get("ok")):
            reasons.append("EXCLUDE_OK_FALSE")
            counters["ok_false"] += 1

        hf = _hard_fail_full_post_reasons(r)
        if hf:
            reasons.extend(hf)
            counters["hard_fail_fullpost"] += 1

        bf = _basis_fail_reasons(r)
        if bf:
            reasons.extend(bf)
            counters["basis_fail_eq50"] += 1

        if _fmt_str(r.get("post_gonogo")) == "NO_GO":
            reasons.append("EXCLUDE_POST_GONOGO_NO_GO")
            counters["post_NO_GO"] += 1

        if not _has_rank_metrics(r):
            reasons.append("EXCLUDE_MISSING_RANK_METRICS")
            counters["missing_rank_metrics"] += 1

        if reasons:
            excluded[sid] = reasons
        else:
            eligible.append(r)

    return eligible, excluded, counters


def _policy_compare_pair(trend_row: Dict[str, Any], always_row: Dict[str, Any]) -> Tuple[str, str]:
    """
    Deterministic always vs trend comparison (compare_v1):
    - Prefer POST if BOTH have post_ok=True, else use FULL.
    - Winner = higher calmar; tie-breaker = higher sharpe0; final tie = strategy_id.
    Returns (basis, winner_id).
    """
    use_post = _is_true(trend_row.get("post_ok")) and _is_true(always_row.get("post_ok"))
    if use_post:
        basis = "post"
        t_cal = _finite_or_neginf(trend_row.get("post_calmar"))
        a_cal = _finite_or_neginf(always_row.get("post_calmar"))
        t_sh = _finite_or_neginf(trend_row.get("post_sharpe0"))
        a_sh = _finite_or_neginf(always_row.get("post_sharpe0"))
    else:
        basis = "full"
        t_cal = _finite_or_neginf(trend_row.get("full_calmar"))
        a_cal = _finite_or_neginf(always_row.get("full_calmar"))
        t_sh = _finite_or_neginf(trend_row.get("full_sharpe0"))
        a_sh = _finite_or_neginf(always_row.get("full_sharpe0"))

    if t_cal > a_cal:
        return basis, _fmt_str(trend_row.get("id"))
    if a_cal > t_cal:
        return basis, _fmt_str(always_row.get("id"))

    if t_sh > a_sh:
        return basis, _fmt_str(trend_row.get("id"))
    if a_sh > t_sh:
        return basis, _fmt_str(always_row.get("id"))

    return basis, min(_fmt_str(trend_row.get("id")), _fmt_str(always_row.get("id")))


def _render_comparison_block(rows_all: List[Dict[str, Any]], excluded: Dict[str, List[str]]) -> List[str]:
    by_id = {_fmt_str(r.get("id")): r for r in rows_all}
    lines: List[str] = []
    pairs: List[Tuple[str, str, str]] = []

    for r in rows_all:
        sid = _fmt_str(r.get("id"))
        if sid.startswith("always_leverage_") and sid.endswith("x"):
            suffix = sid[len("always_leverage_"):]  # e.g. "1.2x"
            trend_id = f"trend_leverage_price_gt_ma60_{suffix}"
            if trend_id in by_id:
                pairs.append((suffix, trend_id, sid))

    if not pairs:
        lines.append("## Deterministic Always vs Trend (checkmarks)")
        lines.append("- N/A (no always/trend pairs detected by naming convention)")
        lines.append("")
        return lines

    pairs = sorted(set(pairs), key=lambda x: x[0])

    lines.append("## Deterministic Always vs Trend (checkmarks)")
    lines.append("- compare_policy: `compare_v1: for same L, compare post if both post_ok else full; winner=calmar desc, then sharpe0 desc, then id`")
    lines.append("")
    lines.append("| L | basis | trend_id | always_id | winner | verdict |")
    lines.append("|---:|---|---|---|---|---|")

    for suffix, trend_id, always_id in pairs:
        trend_row = by_id[trend_id]
        always_row = by_id[always_id]

        if trend_id in excluded or always_id in excluded:
            note = []
            if trend_id in excluded:
                note.append(f"trend excluded: {', '.join(excluded[trend_id])}")
            if always_id in excluded:
                note.append(f"always excluded: {', '.join(excluded[always_id])}")
            msg = "; ".join(note)[:160]
            lines.append(f"| {suffix} | N/A | {_escape_md_cell(trend_id)} | {_escape_md_cell(always_id)} | N/A | N/A ({_escape_md_cell(msg)}) |")
            continue

        basis, winner = _policy_compare_pair(trend_row, always_row)
        verdict = "WIN:trend" if winner == trend_id else ("WIN:always" if winner == always_id else "WIN:tie")
        lines.append(f"| {suffix} | {basis} | {_escape_md_cell(trend_id)} | {_escape_md_cell(always_id)} | {_escape_md_cell(winner)} | {verdict} |")

    lines.append("")
    return lines


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

    lines.append("## Ranking (policy)")
    lines.append(f"- ranking_policy: `{_fmt_str(ranking_policy)}`")
    lines.append(
        "- renderer_filter_policy: `renderer_rank_filter_v2: "
        "exclude(ok=false); "
        "exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post; "
        "plus basis_equity_min<=0.5 (asset down 50%) on rank_basis segment); "
        "exclude(post_gonogo=NO_GO); "
        "exclude(missing rank metrics on chosen basis)`"
    )
    lines.append(
        "- full_segment_note: `FULL_* metrics may be impacted by data singularity around 2014 (price series anomaly/adjustment). "
        "Treat FULL as audit-only; prefer POST for decision and ranking.`"
    )

    strategies = _strategy_list(obj)
    rows_all = [_mk_row(s) for s in strategies]

    eligible, excluded, counters = _filter_rows(rows_all)
    eligible_sorted = _sort_rows_like_policy(eligible)

    if eligible_sorted:
        top3_rec = [str(r.get("id")) for r in eligible_sorted[:3]]
        lines.append(f"- top3_recommended: `{', '.join(top3_rec)}`")
    else:
        lines.append("- top3_recommended: `N/A`")

    if isinstance(top3_raw, list):
        lines.append(f"- top3_raw_from_suite: `{', '.join([str(x) for x in top3_raw])}`")
    else:
        lines.append(f"- top3_raw_from_suite: `{_fmt_str(top3_raw)}`")
    lines.append("")

    rows_sorted_all = _sort_rows_like_policy(rows_all)

    lines.append("## Strategies")
    lines.append(
        "- note_full: `FULL_* columns may be contaminated by a known data singularity issue. "
        "Do not use FULL alone for go/no-go; use POST_* as primary.`"
    )
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

    for r in rows_sorted_all:
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

    lines.append("## Exclusions (not eligible for recommendation)")
    total = len(rows_all)
    elig = len(eligible)
    excl = len(excluded)
    lines.append(f"- total_strategies: `{total}`")
    lines.append(f"- eligible: `{elig}`")
    lines.append(
        f"- excluded: `{excl}` "
        f"(hard_fail_fullpost={counters['hard_fail_fullpost']}, basis_fail_eq50={counters['basis_fail_eq50']}, "
        f"post_NO_GO={counters['post_NO_GO']}, ok_false={counters['ok_false']}, missing_rank_metrics={counters['missing_rank_metrics']})"
    )
    lines.append("")

    if excluded:
        for sid in sorted(excluded.keys()):
            rs = ", ".join(excluded[sid])
            lines.append(f"- {sid}: `{rs}`")
        lines.append("")

    lines.extend(_render_comparison_block(rows_all, excluded))

    lines.append("## Post Go/No-Go Details (compact)")
    any_details = False
    for r in rows_sorted_all:
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