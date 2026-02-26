#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_backtest_mvp.py

Render backtest_tw0050_leverage_mvp suite json (lite or full) into a compact Markdown report.

v15 (2026-02-26):
- ADD(ci): if running in GitHub Actions, also publish the rendered Markdown into $GITHUB_STEP_SUMMARY
  so you can read the report directly from the workflow run Summary on mobile.
  * This is display-only. No change to ranking, filtering, or Semantic1 logic.
  * Also prints a short preview to stdout (workflow logs) for quick inspection.

v14 (2026-02-26):
- ADD(print): expose tactical exit params in Strategies table so "tp/sl bounce-and-run" is auditable:
  * exit_mode, exit_z, take_profit_pct, stop_loss_pct, max_hold_days, entry_z, leverage_frac
  * This is display-only. No change to ranking, filtering, or Semantic1 logic.

v13 (2026-02-24):
- ADD(DQ): compare JSON post_neg_days vs equity CSV post neg_days_count (date >= post_start_date)
  and mark DQ_MISMATCH when they differ.
  * This does NOT change backtest, thresholds, or Semantic1 eligibility.
  * Purpose: make the semantics mismatch explicit (post segment "new start" vs full-equity sliced-by-date).

v12 (2026-02-24):
- Semantic1 ("new start") for Post-only View:
  * Post-only PASS/WATCH eligibility is decided ONLY by Post-only rules.
  * Do NOT let renderer_filter_v4 (suite_hard_fail / FULL hard fails) exclude Post-only PASS/WATCH rows.
  * Still annotate PASS/WATCH rows with a note if suite_hard_fail=true (FULL period blowup risk), but keep them listed.
  * Keep the rest of v11 structure: ranking policy block, strategies table, exclusions, always-vs-trend,
    post-only PASS/WATCH tables, and suite_hard_fail date evidence (best-effort from per-strategy equity CSV).

Assumptions:
- Suite JSON is produced by backtest_tw0050_leverage_mvp.py v26.7+ (per-strategy equity CSV enabled).
- Equity curve CSV pattern (best-effort):
    equity_curve.*__<strategy_id>.csv  (located in the same directory as --in_json)

DQ note (important):
- JSON post_neg_days is computed on the POST SEGMENT backtest, which normalizes equity to 1.0 at post start.
- equity CSV is the FULL backtest equity curve; filtering by date>=post_start_date does NOT re-normalize.
- Therefore DQ_MISMATCH is often a "semantic mismatch" indicator, not necessarily a bug.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


SCRIPT_FINGERPRINT = "render_backtest_mvp@2026-02-26.v15.publish_step_summary"


# =========================
# utils
# =========================
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


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        if isinstance(x, bool):
            return int(x)
        if isinstance(x, (int, np.integer)):
            return int(x)
        v = _to_float(x)
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


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
    v = _to_int(x)
    return "N/A" if v is None else str(v)


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


def _bool_flag(x: Any) -> bool:
    # avoid treating "False" as True
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    return False


def _is_github_actions() -> bool:
    return str(os.environ.get("GITHUB_ACTIONS", "")).strip().lower() == "true"


def _publish_to_github_step_summary(md: str, in_json: str, out_md: str) -> None:
    """
    Publish markdown into GitHub Actions Summary if $GITHUB_STEP_SUMMARY is available.
    Keep it robust: never fail the workflow because of summary write errors.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    try:
        os.makedirs(os.path.dirname(summary_path) or ".", exist_ok=True)
    except Exception:
        # ignore
        pass

    # GitHub summary has size limits; be conservative.
    # (We avoid guessing exact limit; truncate to reduce risk of failure.)
    max_chars = 700_000
    body = md
    truncated = False
    if len(body) > max_chars:
        body = body[:max_chars]
        truncated = True

    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("## Backtest MVP Report\n\n")
            f.write(f"- in_json: `{_escape_md_cell(in_json)}`\n")
            f.write(f"- out_md: `{_escape_md_cell(out_md)}`\n")
            f.write(f"- renderer_fingerprint: `{SCRIPT_FINGERPRINT}`\n\n")
            f.write("<details>\n")
            f.write("<summary>Open rendered markdown</summary>\n\n")
            f.write(body)
            if truncated:
                f.write("\n\n> NOTE: Summary content truncated (size guard). Please download artifact / open out_md for full report.\n")
            f.write("\n\n</details>\n\n")
    except Exception:
        # Do not break the run if summary write fails.
        return


def _print_preview(md: str, max_lines: int = 80) -> None:
    """
    Print a short preview to stdout (workflow logs) for quick inspection on mobile.
    """
    try:
        lines = md.splitlines()
        print("---- report preview (head) ----")
        for i, ln in enumerate(lines[:max_lines]):
            print(ln)
        if len(lines) > max_lines:
            print(f"... (truncated preview; total_lines={len(lines)})")
        print("---- end preview ----")
    except Exception:
        return


# =========================
# parsing / extraction
# =========================
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
        "rv20_skipped": (audit.get("skipped_entries_on_rv20") if isinstance(audit, dict) else None),
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
    entry_z = (params.get("entry_z") if isinstance(params, dict) else None)

    leverage_frac = (params.get("leverage_frac") if isinstance(params, dict) else None)
    L = _leverage_mult_from_params(params if isinstance(params, dict) else {})

    # v14: tactical exit params (display-only)
    exit_mode = (params.get("exit_mode") if isinstance(params, dict) else None)
    exit_z = (params.get("exit_z") if isinstance(params, dict) else None)
    take_profit_pct = (params.get("take_profit_pct") if isinstance(params, dict) else None)
    stop_loss_pct = (params.get("stop_loss_pct") if isinstance(params, dict) else None)
    max_hold_days = (params.get("max_hold_days") if isinstance(params, dict) else None)

    full = _extract_full_metrics(strat)
    post = _extract_post_metrics(strat)
    gg = _extract_gonogo(strat)

    suite_hf = strat.get("suite_hard_fail")
    suite_hard_fail = _bool_flag(suite_hf)

    return {
        "id": sid,
        "ok": ok,
        "suite_hard_fail": suite_hard_fail,
        "entry_mode": entry_mode,
        "entry_z": entry_z,
        "leverage_frac": leverage_frac,
        "L": L,
        "exit_mode": exit_mode,
        "exit_z": exit_z,
        "take_profit_pct": take_profit_pct,
        "stop_loss_pct": stop_loss_pct,
        "max_hold_days": max_hold_days,
        **full,
        **post,
        "post_gonogo": gg.get("decision"),
        "post_gonogo_rule": gg.get("rule_id"),
        "post_gonogo_conditions": gg.get("conditions"),
        "post_gonogo_reasons": gg.get("reasons"),
        "rank_basis": _rank_basis(bool(post.get("post_ok"))),
        "hard_fail_reasons_from_suite": strat.get("hard_fail_reasons"),
        # v13 DQ placeholders (filled later)
        "equity_csv_path": None,
        "csv_post_neg_days_count": None,
        "dq_post_neg_days": "N/A",
        "dq_post_neg_days_detail": None,
    }


# =========================
# policy: sorting / filtering / exclusion reasons
# =========================
def _finite_or_neginf(x: Any) -> float:
    v = _to_float(x)
    return float(v) if v is not None else float("-inf")


def _sort_rows_like_policy(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Follow suite policy:
    prefer post (calmar desc, sharpe0 desc) when post_ok=True; else fallback to full
    Deterministic tie-breaker by strategy_id.
    """
    def key(r: Dict[str, Any]) -> Tuple[float, float, str]:
        rid = _fmt_str(r.get("id"))
        if _bool_flag(r.get("post_ok")):
            return (_finite_or_neginf(r.get("post_calmar")), _finite_or_neginf(r.get("post_sharpe0")), rid)
        return (_finite_or_neginf(r.get("full_calmar")), _finite_or_neginf(r.get("full_sharpe0")), rid)

    return sorted(rows, key=key, reverse=True)


def _hard_fail_reasons_for_segment(seg_name: str, mdd: Any, eq_min: Any, neg_days: Any) -> List[str]:
    """
    Hard fail:
    - equity_min <= 0
    - equity_negative_days > 0
    - mdd <= -100% (<= -1.0)
    """
    out: List[str] = []

    vmdd = _to_float(mdd)
    veq = _to_float(eq_min)
    vneg = _to_float(neg_days)

    if vmdd is not None and vmdd <= -1.0:
        out.append(f"HARD_FAIL_{seg_name}_MDD_LE_-100PCT")
    if veq is not None and veq <= 0.0:
        out.append(f"HARD_FAIL_{seg_name}_EQUITY_MIN_LE_0")
    if vneg is not None and vneg > 0.0:
        out.append(f"HARD_FAIL_{seg_name}_NEG_DAYS_GT_0")

    return out


def _missing_rank_metrics_reason(basis: str) -> str:
    return f"EXCLUDE_MISSING_RANK_METRICS_{basis.upper()}"


def _is_missing_rank_metrics(r: Dict[str, Any], basis: str) -> bool:
    if basis == "post":
        return (_to_float(r.get("post_calmar")) is None) or (_to_float(r.get("post_sharpe0")) is None)
    return (_to_float(r.get("full_calmar")) is None) or (_to_float(r.get("full_sharpe0")) is None)


def _exclusion_reasons_renderer_filter_v4(r: Dict[str, Any]) -> List[str]:
    """
    Renderer filter policy v4:
    exclude(ok=false);
    exclude(suite_hard_fail=true);
    exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post);
    exclude(post_gonogo=NO_GO);
    exclude(missing rank metrics on chosen basis);
    """
    reasons: List[str] = []

    # ok=false
    if not bool(r.get("ok")):
        reasons.append("EXCLUDE_OK_FALSE")

    # suite_hard_fail=true
    if _bool_flag(r.get("suite_hard_fail")):
        reasons.append("EXCLUDE_SUITE_HARD_FAIL_TRUE")

    # hard fails on full/post
    reasons += _hard_fail_reasons_for_segment(
        "FULL", r.get("full_mdd"), r.get("full_equity_min"), r.get("full_neg_days")
    )
    reasons += _hard_fail_reasons_for_segment(
        "POST", r.get("post_mdd"), r.get("post_equity_min"), r.get("post_neg_days")
    )

    # post gonogo
    if _fmt_str(r.get("post_gonogo")) == "NO_GO":
        reasons.append("EXCLUDE_POST_GONOGO_NO_GO")

    # missing rank metrics on chosen basis
    basis = _fmt_str(r.get("rank_basis"))
    if basis not in ("post", "full"):
        basis = "full"
    if _is_missing_rank_metrics(r, basis):
        reasons.append(_missing_rank_metrics_reason(basis))

    return reasons


def _is_eligible_for_recommendation_renderer_v4(r: Dict[str, Any]) -> bool:
    return len(_exclusion_reasons_renderer_filter_v4(r)) == 0


def _rank_key_on_basis(r: Dict[str, Any], basis: str) -> Tuple[float, float, str]:
    rid = _fmt_str(r.get("id"))
    if basis == "post":
        return (_finite_or_neginf(r.get("post_calmar")), _finite_or_neginf(r.get("post_sharpe0")), rid)
    return (_finite_or_neginf(r.get("full_calmar")), _finite_or_neginf(r.get("full_sharpe0")), rid)


def _topn_recommended_renderer_v4(rows: List[Dict[str, Any]], n: int = 3) -> List[str]:
    eligible = [r for r in rows if _is_eligible_for_recommendation_renderer_v4(r)]
    eligible_sorted = sorted(
        eligible,
        key=lambda r: _rank_key_on_basis(r, _fmt_str(r.get("rank_basis"))),
        reverse=True,
    )
    return [str(r.get("id")) for r in eligible_sorted[:n]]


# =========================
# always vs trend compare
# =========================
def _find_strategy_by_id(rows: List[Dict[str, Any]], sid: str) -> Optional[Dict[str, Any]]:
    for r in rows:
        if _fmt_str(r.get("id")) == sid:
            return r
    return None


def _compare_two_rows(r1: Dict[str, Any], r2: Dict[str, Any], basis: str) -> str:
    """
    winner=calmar desc, then sharpe0 desc, then id
    returns winner id
    """
    k1 = _rank_key_on_basis(r1, basis)
    k2 = _rank_key_on_basis(r2, basis)
    if k1[0] > k2[0]:
        return _fmt_str(r1.get("id"))
    if k1[0] < k2[0]:
        return _fmt_str(r2.get("id"))
    if k1[1] > k2[1]:
        return _fmt_str(r1.get("id"))
    if k1[1] < k2[1]:
        return _fmt_str(r2.get("id"))
    return min(_fmt_str(r1.get("id")), _fmt_str(r2.get("id")))


def _always_vs_trend_table(rows: List[Dict[str, Any]], trend_rule: str) -> List[str]:
    """
    compare_v2: for same L, compare post if both post_ok else full;
    winner=calmar desc, then sharpe0 desc, then id

    If either side excluded by renderer filter v4, show N/A with exclusion notes.
    """
    tr = str(trend_rule or "price_gt_ma60").strip() or "price_gt_ma60"

    lines: List[str] = []
    lines.append("## Deterministic Always vs Trend (checkmarks)")
    lines.append("compare_policy: `compare_v2: for same L, compare post if both post_ok else full; winner=calmar desc, then sharpe0 desc, then id; trend_id uses suite trend_rule`")
    lines.append(f"trend_rule: `{tr}`")
    lines.append("")
    lines.append("| L | basis | trend_id | always_id | winner | verdict |")
    lines.append("|---:|---|---|---|---|---|")

    for L in ["1.1x", "1.2x", "1.3x", "1.5x"]:
        trend_id = f"trend_leverage_{tr}_{L}"
        always_id = f"always_leverage_{L}"

        rt = _find_strategy_by_id(rows, trend_id)
        ra = _find_strategy_by_id(rows, always_id)

        if rt is None or ra is None:
            lines.append(f"| {L} | N/A | {trend_id} | {always_id} | N/A | N/A (missing strategy) |")
            continue

        ex_t = _exclusion_reasons_renderer_filter_v4(rt)
        ex_a = _exclusion_reasons_renderer_filter_v4(ra)

        if ex_t or ex_a:
            t_note = f"trend excluded: {', '.join(ex_t)}" if ex_t else "trend OK"
            a_note = f"always excluded: {', '.join(ex_a)}" if ex_a else "always OK"
            lines.append(f"| {L} | N/A | {trend_id} | {always_id} | N/A | N/A ({t_note}; {a_note}) |")
            continue

        basis = "post" if (_bool_flag(rt.get("post_ok")) and _bool_flag(ra.get("post_ok"))) else "full"
        winner = _compare_two_rows(rt, ra, basis)
        verdict = "WIN:trend" if winner == trend_id else ("WIN:always" if winner == always_id else "WIN:tiebreak")
        lines.append(f"| {L} | {basis} | {trend_id} | {always_id} | {winner} | {verdict} |")

    lines.append("")
    return lines


# =========================
# suite_hard_fail evidence + DQ from equity CSV (best-effort)
# =========================
def _find_equity_csv(in_json_path: str, strategy_id: str) -> Optional[str]:
    base_dir = os.path.dirname(os.path.abspath(in_json_path)) or "."
    sid = str(strategy_id)
    pats = [
        os.path.join(base_dir, f"equity_curve.*__{sid}.csv"),
        os.path.join(base_dir, f"*equity_curve*__{sid}.csv"),
    ]
    cands: List[str] = []
    for p in pats:
        cands.extend(glob.glob(p))
    cands = [c for c in cands if os.path.isfile(c)]
    if not cands:
        return None
    # stable selection: shortest path then lexicographic
    cands = sorted(cands, key=lambda x: (len(x), x))
    return cands[0]


def _read_equity_csv_dates_and_equity(path: str) -> Tuple[List[str], List[float]]:
    dates: List[str] = []
    eqs: List[float] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [], []
        if "date" not in reader.fieldnames or "equity" not in reader.fieldnames:
            return [], []
        for row in reader:
            d = row.get("date")
            e = row.get("equity")
            if d is None:
                continue
            v = _to_float(e)
            if v is None:
                continue
            dates.append(str(d))
            eqs.append(float(v))
    return dates, eqs


def _equity_evidence_from_series(dates: List[str], eqs: List[float], date_ge: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute:
    - equity_min_date (date of min equity)
    - neg_days_count, neg_days_first_date, neg_days_last_date
    Optionally filter to dates >= date_ge (ISO string compare).
    """
    if not dates or not eqs or len(dates) != len(eqs):
        return {"ok": False, "error": "empty series"}

    idxs = list(range(len(dates)))
    if date_ge:
        dge = str(date_ge)
        idxs = [i for i in idxs if str(dates[i]) >= dge]

    if not idxs:
        return {"ok": False, "error": "no rows after date_ge filter"}

    # min equity
    min_i = min(idxs, key=lambda i: eqs[i])
    equity_min_date = dates[min_i]

    # negative days
    neg_idxs = [i for i in idxs if eqs[i] < 0.0]
    neg_count = int(len(neg_idxs))
    neg_first = dates[neg_idxs[0]] if neg_idxs else None
    neg_last = dates[neg_idxs[-1]] if neg_idxs else None

    return {
        "ok": True,
        "equity_min_date": equity_min_date,
        "neg_days_first_date": neg_first,
        "neg_days_last_date": neg_last,
        "neg_days_count": neg_count,
    }


def _attach_equity_dq_fields(in_json_path: str, rows: List[Dict[str, Any]]) -> None:
    """
    v13:
    Fill per-row fields:
      - equity_csv_path
      - csv_post_neg_days_count (neg_days_count from equity CSV for date>=post_start_date)
      - dq_post_neg_days: OK / DQ_MISMATCH / N/A
      - dq_post_neg_days_detail
    """
    for r in rows:
        sid = _fmt_str(r.get("id"))
        post_start = _fmt_str(r.get("post_start_date"))
        csv_path = _find_equity_csv(in_json_path, sid)
        r["equity_csv_path"] = csv_path

        if not csv_path:
            r["dq_post_neg_days"] = "N/A"
            r["dq_post_neg_days_detail"] = "equity_csv_not_found"
            continue

        dates, eqs = _read_equity_csv_dates_and_equity(csv_path)
        if not dates:
            r["dq_post_neg_days"] = "N/A"
            r["dq_post_neg_days_detail"] = "equity_csv_unreadable"
            continue

        post_ev = _equity_evidence_from_series(dates, eqs, date_ge=post_start if post_start != "N/A" else None)
        if not post_ev.get("ok"):
            r["dq_post_neg_days"] = "N/A"
            r["dq_post_neg_days_detail"] = f"equity_csv_post_ev_error:{_fmt_str(post_ev.get('error'))}"
            continue

        csv_neg = _to_int(post_ev.get("neg_days_count"))
        r["csv_post_neg_days_count"] = csv_neg

        json_neg = _to_int(r.get("post_neg_days"))
        if json_neg is None or csv_neg is None:
            r["dq_post_neg_days"] = "N/A"
            r["dq_post_neg_days_detail"] = f"json={_fmt_str(json_neg)};csv={_fmt_str(csv_neg)}"
            continue

        if int(json_neg) != int(csv_neg):
            r["dq_post_neg_days"] = "DQ_MISMATCH"
            r["dq_post_neg_days_detail"] = f"json_post_neg_days={json_neg};csv_post_neg_days_count={csv_neg}"
        else:
            r["dq_post_neg_days"] = "OK"
            r["dq_post_neg_days_detail"] = f"json_post_neg_days={json_neg};csv_post_neg_days_count={csv_neg}"


def _suite_hard_fail_evidence_block(in_json_path: str, r: Dict[str, Any]) -> List[str]:
    """
    Best-effort evidence for suite_hard_fail strategies.
    Includes v13 DQ line.
    """
    lines: List[str] = []
    sid = _fmt_str(r.get("id"))
    post_start = _fmt_str(r.get("post_start_date"))
    csv_path = _find_equity_csv(in_json_path, sid)

    lines.append("- suite_hard_fail_evidence (from equity CSV, best-effort):")
    if not csv_path:
        lines.append("  - status: `N/A` (equity csv not found)")
        return lines

    dates, eqs = _read_equity_csv_dates_and_equity(csv_path)
    if not dates:
        lines.append(f"  - equity_csv: `{csv_path}`")
        lines.append("  - status: `N/A` (could not read date/equity columns)")
        return lines

    full_ev = _equity_evidence_from_series(dates, eqs, date_ge=None)
    post_ev = _equity_evidence_from_series(dates, eqs, date_ge=post_start if post_start != "N/A" else None)

    lines.append(f"  - equity_csv: `{csv_path}`")

    # v13 DQ line (JSON vs CSV)
    dq = _fmt_str(r.get("dq_post_neg_days"))
    dq_detail = _fmt_str(r.get("dq_post_neg_days_detail"))
    lines.append(f"  - dq_post_neg_days (json vs csv, date>=post_start): `{dq}`; detail: `{dq_detail}`")

    lines.append("  - FULL:")
    if full_ev.get("ok"):
        lines.append(f"    - equity_min_date: `{_fmt_str(full_ev.get('equity_min_date'))}`")
        lines.append(f"    - neg_days_first_date: `{_fmt_str(full_ev.get('neg_days_first_date'))}`")
        lines.append(f"    - neg_days_last_date: `{_fmt_str(full_ev.get('neg_days_last_date'))}`")
        lines.append(f"    - neg_days_count: `{_fmt_int(full_ev.get('neg_days_count'))}`")
    else:
        lines.append(f"    - status: `N/A` ({_fmt_str(full_ev.get('error'))})")

    lines.append("  - POST (date >= post_start_date) [NOTE: this is FULL equity sliced by date, not post-segment normalized]:")
    lines.append(f"    - post_start_date: `{post_start}`")
    if post_ev.get("ok"):
        lines.append(f"    - equity_min_date: `{_fmt_str(post_ev.get('equity_min_date'))}`")
        lines.append(f"    - neg_days_first_date: `{_fmt_str(post_ev.get('neg_days_first_date'))}`")
        lines.append(f"    - neg_days_last_date: `{_fmt_str(post_ev.get('neg_days_last_date'))}`")
        lines.append(f"    - neg_days_count: `{_fmt_int(post_ev.get('neg_days_count'))}`")
    else:
        lines.append(f"    - status: `N/A` ({_fmt_str(post_ev.get('error'))})")

    return lines


# =========================
# Post-only view (Semantic1)
# =========================
def _post_only_policy_v3_reasons(r: Dict[str, Any], pass_th: float, watch_lo: float, watch_hi: float, mdd_floor: float) -> List[str]:
    """
    Post-only policy v3:
    require post_ok=true;
    exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%);
    exclude post_gonogo=NO_GO;
    exclude missing post rank metrics;
    PASS gate: post_delta_sharpe >= pass_th
    WATCH gate: watch_lo <= post_delta_sharpe < watch_hi
    post_MDD floor: post_mdd >= mdd_floor
    (FULL and suite_hard_fail are ignored for eligibility in Semantic1)
    """
    rs: List[str] = []

    if not _bool_flag(r.get("post_ok")):
        rs.append("EXCLUDE_POST_OK_FALSE")
        return rs

    rs += _hard_fail_reasons_for_segment("POST", r.get("post_mdd"), r.get("post_equity_min"), r.get("post_neg_days"))

    if _fmt_str(r.get("post_gonogo")) == "NO_GO":
        rs.append("EXCLUDE_POST_GONOGO_NO_GO")

    if _to_float(r.get("post_calmar")) is None or _to_float(r.get("post_sharpe0")) is None:
        rs.append("EXCLUDE_MISSING_RANK_METRICS_POST")

    dsh = _to_float(r.get("post_delta_sharpe0_vs_base"))
    if dsh is None:
        rs.append("EXCLUDE_POST_DELTA_SHARPE_MISSING")
    else:
        if dsh < float(watch_lo):
            rs.append(f"EXCLUDE_POST_DELTA_SHARPE_LT_{watch_lo}")

    pmdd = _to_float(r.get("post_mdd"))
    if pmdd is not None and pmdd < float(mdd_floor):
        rs.append(f"EXCLUDE_POST_MDD_LT_{mdd_floor}")

    return rs


def _post_only_bucket(r: Dict[str, Any], pass_th: float, watch_lo: float, watch_hi: float) -> str:
    dsh = _to_float(r.get("post_delta_sharpe0_vs_base"))
    if dsh is None:
        return "EXCLUDE"
    if dsh >= float(pass_th):
        return "PASS"
    if float(watch_lo) <= dsh < float(watch_hi):
        return "WATCH"
    return "EXCLUDE"


def _post_only_section_semantic1(rows: List[Dict[str, Any]]) -> List[str]:
    pass_th = -0.03
    watch_lo = -0.05
    watch_hi = -0.03
    mdd_floor = -0.4

    lines: List[str] = []
    lines.append("## Post-only View (After Singularity / Ignore FULL)")
    lines.append(
        "post_only_policy_v3_semantic1: `require post_ok=true; exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%); "
        "exclude post_gonogo=NO_GO; exclude missing post rank metrics; "
        f"PASS gate: require post_ΔSharpe>= {pass_th}; "
        f"WATCH gate: require {watch_lo}<=post_ΔSharpe<{watch_hi}; "
        f"post_MDD floor: require post_MDD>= {mdd_floor} (i.e. not worse than -40%); "
        "ignore FULL and ignore suite_hard_fail for eligibility (Semantic1=new start).`"
    )
    lines.append("- dq_check_v13: `Compare JSON post_neg_days (post-segment normalized) vs equity CSV neg_days_count on date>=post_start_date (full-equity sliced). DQ_MISMATCH usually indicates semantic mismatch, not necessarily a bug.`")

    excluded: List[Tuple[str, List[str]]] = []
    pass_rows: List[Dict[str, Any]] = []
    watch_rows: List[Dict[str, Any]] = []

    for r in rows:
        rs = _post_only_policy_v3_reasons(r, pass_th=pass_th, watch_lo=watch_lo, watch_hi=watch_hi, mdd_floor=mdd_floor)
        if rs:
            excluded.append((_fmt_str(r.get("id")), rs))
            continue

        bucket = _post_only_bucket(r, pass_th=pass_th, watch_lo=watch_lo, watch_hi=watch_hi)
        if bucket == "PASS":
            pass_rows.append(r)
        elif bucket == "WATCH":
            watch_rows.append(r)
        else:
            excluded.append((_fmt_str(r.get("id")), ["EXCLUDE_POST_DELTA_SHARPE_LT_-0.05"]))

    pass_rows = sorted(pass_rows, key=lambda r: _rank_key_on_basis(r, "post"), reverse=True)
    watch_rows = sorted(watch_rows, key=lambda r: _rank_key_on_basis(r, "post"), reverse=True)

    top3_pass = [str(r.get("id")) for r in pass_rows[:3]]
    top3_watch = [str(r.get("id")) for r in watch_rows[:3]]
    warn_full = [str(r.get("id")) for r in (pass_rows + watch_rows) if _bool_flag(r.get("suite_hard_fail"))]
    dq_mis = [str(r.get("id")) for r in (pass_rows + watch_rows) if _fmt_str(r.get("dq_post_neg_days")) == "DQ_MISMATCH"]

    lines.append(f"- top3_post_only_PASS: `{', '.join(top3_pass) if top3_pass else 'N/A'}`")
    lines.append(f"- top3_post_only_WATCH: `{', '.join(top3_watch) if top3_watch else 'N/A'}`")
    lines.append(f"- post_only_total: `{len(rows)}`; pass: `{len(pass_rows)}`; watch: `{len(watch_rows)}`; excluded: `{len(excluded)}`")
    lines.append(f"- post_only_warn_full_blowup (suite_hard_fail=true): `{', '.join(warn_full) if warn_full else 'N/A'}`")
    lines.append(f"- post_only_dq_mismatch_post_neg_days: `{', '.join(dq_mis) if dq_mis else 'N/A'}`")
    lines.append("")

    def _note_for_post_only(r: Dict[str, Any]) -> str:
        notes: List[str] = []
        if _bool_flag(r.get("suite_hard_fail")):
            notes.append("WARNING: suite_hard_fail=true (FULL period floor violated; Semantic2 risk)")
        if _fmt_str(r.get("dq_post_neg_days")) == "DQ_MISMATCH":
            notes.append(f"DQ_MISMATCH(post_neg_days): {_fmt_str(r.get('dq_post_neg_days_detail'))}")
        return "; ".join(notes) if notes else ""

    lines.append("### PASS (deploy-grade, strict; Semantic1=new start)")
    lines.append("| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for r in pass_rows[:10]:
        lines.append(
            "| {id} | {cagr} | {mdd} | {sh} | {cal} | {dsh} | {note} |".format(
                id=_escape_md_cell(r.get("id")),
                cagr=_fmt_pct(r.get("post_cagr")),
                mdd=_fmt_pct(r.get("post_mdd")),
                sh=_fmt_num(r.get("post_sharpe0"), nd=3),
                cal=_fmt_num(r.get("post_calmar"), nd=3),
                dsh=_fmt_num(r.get("post_delta_sharpe0_vs_base"), nd=3),
                note=_escape_md_cell(_note_for_post_only(r)) or " ",
            )
        )
    lines.append("")

    lines.append("### WATCH (research-grade, not for deploy; Semantic1=new start)")
    lines.append("| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for r in watch_rows[:10]:
        lines.append(
            "| {id} | {cagr} | {mdd} | {sh} | {cal} | {dsh} | {note} |".format(
                id=_escape_md_cell(r.get("id")),
                cagr=_fmt_pct(r.get("post_cagr")),
                mdd=_fmt_pct(r.get("post_mdd")),
                sh=_fmt_num(r.get("post_sharpe0"), nd=3),
                cal=_fmt_num(r.get("post_calmar"), nd=3),
                dsh=_fmt_num(r.get("post_delta_sharpe0_vs_base"), nd=3),
                note=_escape_md_cell(_note_for_post_only(r)) or " ",
            )
        )
    lines.append("")

    lines.append("### Post-only Exclusions (reasons)")
    if excluded:
        for sid, rs in sorted(excluded, key=lambda x: x[0]):
            lines.append(f"- {sid}: `{', '.join(rs)}`")
    else:
        lines.append("- N/A (no exclusions)")
    lines.append("")

    return lines


# =========================
# render md
# =========================
def _render_md(obj: Dict[str, Any], in_json_path: str) -> str:
    gen_at = obj.get("generated_at_utc") or obj.get("generated_at") or obj.get("generated_at_ts")
    fp = obj.get("script_fingerprint") or obj.get("build_script_fingerprint")
    suite_ok = obj.get("suite_ok")
    if suite_ok is None and "ok" in obj:
        suite_ok = obj.get("ok")

    compare = obj.get("compare") or {}
    ranking_policy = compare.get("ranking_policy")
    top3_raw = compare.get("top3_by_policy")

    trend_rule = _get(obj, ["strategy_suite", "trend_rule"], default="price_gt_ma60")

    full_note = (
        "FULL_* metrics may be impacted by data singularity around 2014 (price series anomaly/adjustment). "
        "Treat FULL as audit-only; prefer POST for decision and ranking."
    )

    renderer_filter_policy = (
        "renderer_rank_filter_v4: exclude(ok=false); "
        "exclude(suite_hard_fail=true); "
        "exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post); "
        "exclude(post_gonogo=NO_GO); "
        "exclude(missing rank metrics on chosen basis); "
        "NOTE: eq50 gate disabled (basis_equity_min<=0.5 removed; equity_min semantics not aligned with MDD)."
    )

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
    lines.append(f"- renderer_filter_policy: `{renderer_filter_policy}`")
    lines.append(f"- full_segment_note: `{full_note}`")

    strategies = _strategy_list(obj)
    rows = [_mk_row(s) for s in strategies]

    # v13 DQ enrichment (best-effort)
    _attach_equity_dq_fields(in_json_path=in_json_path, rows=rows)

    rows_sorted = _sort_rows_like_policy(rows)
    top3_rec = _topn_recommended_renderer_v4(rows, n=3)

    lines.append(f"- top3_recommended: `{', '.join(top3_rec) if top3_rec else 'N/A'}`")
    if isinstance(top3_raw, list):
        lines.append(f"- top3_raw_from_suite: `{', '.join([str(x) for x in top3_raw])}`")
    else:
        lines.append(f"- top3_raw_from_suite: `{_fmt_str(top3_raw)}`")
    lines.append("")

    lines.append("## Strategies")
    lines.append("note_full: `FULL_* columns may be contaminated by a known data singularity issue. Do not use FULL alone for go/no-go; use POST_* as primary.`")
    lines.append("")

    # v14: insert tactical params columns (display-only)
    lines.append(
        "| id | ok | suite_hard_fail | entry_mode | entry_z | lev_frac | L | exit_mode | exit_z | TP | SL | max_hold | "
        "full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | "
        "post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔMDD | post_ΔSharpe | "
        "post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades | rv20_skipped | post_neg_days_csv | dq_post_neg_days |"
    )
    lines.append(
        "|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|"
        "---:|---:|---:|---:|---:|---:|---:|"
        "---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        "---|---|---:|---:|---:|---:|---:|---:|---:|---|"
    )

    for r in rows_sorted:
        lines.append(
            "| {id} | {ok} | {shf} | {entry_mode} | {entry_z} | {lev_frac} | {L} | {exit_mode} | {exit_z} | {tp} | {sl} | {mhd} | "
            "{full_cagr} | {full_mdd} | {full_sh} | {full_calmar} | {dcagr} | {dmdd} | {dsh} | "
            "{post_ok} | {split} | {post_start} | {post_n} | {post_years} | {post_cagr} | {post_mdd} | {post_sh} | {post_calmar} | {post_dcagr} | {post_dmdd} | {post_dsh} | "
            "{gonogo} | {rank_basis} | {neg_days} | {eq_min} | {post_neg_days} | {post_eq_min} | {trades} | {rv20} | {post_neg_days_csv} | {dq} |".format(
                id=_escape_md_cell(r.get("id")),
                ok=_escape_md_cell(r.get("ok")),
                shf=_escape_md_cell(r.get("suite_hard_fail")),
                entry_mode=_escape_md_cell(r.get("entry_mode")),
                entry_z=_fmt_num(r.get("entry_z"), nd=2) if _to_float(r.get("entry_z")) is not None else "N/A",
                lev_frac=_fmt_num(r.get("leverage_frac"), nd=2) if _to_float(r.get("leverage_frac")) is not None else "N/A",
                L=_fmt_num(r.get("L"), nd=2) if _to_float(r.get("L")) is not None else "N/A",
                exit_mode=_escape_md_cell(r.get("exit_mode")),
                exit_z=_fmt_num(r.get("exit_z"), nd=2) if _to_float(r.get("exit_z")) is not None else "N/A",
                tp=_fmt_pct(r.get("take_profit_pct"), nd=2),
                sl=_fmt_pct(r.get("stop_loss_pct"), nd=2),
                mhd=_fmt_int(r.get("max_hold_days")),
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
                rv20=_fmt_int(r.get("rv20_skipped")),
                post_neg_days_csv=_fmt_int(r.get("csv_post_neg_days_count")),
                dq=_escape_md_cell(r.get("dq_post_neg_days")),
            )
        )

    lines.append("")

    lines.append("## Exclusions (not eligible for recommendation)")
    total = len(rows)
    eligible_rows = [r for r in rows if _is_eligible_for_recommendation_renderer_v4(r)]
    excluded_rows = [r for r in rows if not _is_eligible_for_recommendation_renderer_v4(r)]

    suite_hf_n = 0
    hard_fail = 0
    post_no_go = 0
    ok_false = 0
    missing_rank = 0

    for r in excluded_rows:
        rs = _exclusion_reasons_renderer_filter_v4(r)
        if "EXCLUDE_SUITE_HARD_FAIL_TRUE" in rs:
            suite_hf_n += 1
        if any(s.startswith("HARD_FAIL_") for s in rs):
            hard_fail += 1
        if "EXCLUDE_POST_GONOGO_NO_GO" in rs:
            post_no_go += 1
        if "EXCLUDE_OK_FALSE" in rs:
            ok_false += 1
        if any(s.startswith("EXCLUDE_MISSING_RANK_METRICS_") for s in rs):
            missing_rank += 1

    lines.append(f"- total_strategies: `{total}`")
    lines.append(f"- eligible: `{len(eligible_rows)}`")
    lines.append(
        f"- excluded: `{len(excluded_rows)}` "
        f"(suite_hard_fail={suite_hf_n}, hard_fail_fullpost={hard_fail}, post_NO_GO={post_no_go}, ok_false={ok_false}, missing_rank_metrics={missing_rank})"
    )
    lines.append("")

    for r in sorted(excluded_rows, key=lambda x: _fmt_str(x.get("id"))):
        rid = _fmt_str(r.get("id"))
        rs = _exclusion_reasons_renderer_filter_v4(r)
        lines.append(f"- {rid}: `{', '.join(rs)}`")

    lines.append("")
    lines.extend(_always_vs_trend_table(rows, trend_rule=str(trend_rule)))
    lines.extend(_post_only_section_semantic1(rows))

    lines.append("## Post Go/No-Go Details (compact)")
    any_details = False
    for r in rows_sorted:
        dec = _fmt_str(r.get("post_gonogo"))
        if dec != "N/A" or _bool_flag(r.get("post_ok")):
            any_details = True
            lines.append(f"### {_escape_md_cell(r.get('id'))}")
            lines.append(f"- decision: `{dec}`")
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

            # suite_hard_fail evidence
            if _bool_flag(r.get("suite_hard_fail")):
                lines.append(f"- suite_hard_fail: `true`")
                hfr = r.get("hard_fail_reasons_from_suite")
                if isinstance(hfr, list) and hfr:
                    for msg in hfr[:5]:
                        lines.append(f"  - {str(msg)}")
                lines.append("")
                lines.extend(_suite_hard_fail_evidence_block(in_json_path, r))
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

    in_json = str(args.in_json)
    obj = _read_json(in_json)
    md = _render_md(obj, in_json_path=in_json)

    out_md = str(args.out_md)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)

    print("OK: wrote", out_md)

    # v15: publish to GitHub Actions summary + print preview for mobile logs
    if _is_github_actions():
        _publish_to_github_step_summary(md=md, in_json=in_json, out_md=out_md)
        _print_preview(md, max_lines=80)


if __name__ == "__main__":
    main()