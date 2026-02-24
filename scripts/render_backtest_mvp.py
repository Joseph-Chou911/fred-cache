#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_backtest_mvp.py

Render backtest_tw0050_leverage_mvp suite json (lite or full) into a compact Markdown report.

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


SCRIPT_FINGERPRINT = "render_backtest_mvp@2026-02-24.v12.post_only_semantic1_no_renderer_v4_gate"


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


def _bool_flag(x: Any) -> bool:
    # avoid treating "False" as True
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    return False


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
    L = _leverage_mult_from_params(params)

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
        "L": L,
        **full,
        **post,
        "post_gonogo": gg.get("decision"),
        "post_gonogo_rule": gg.get("rule_id"),
        "post_gonogo_conditions": gg.get("conditions"),
        "post_gonogo_reasons": gg.get("reasons"),
        "rank_basis": _rank_basis(bool(post.get("post_ok"))),
        "hard_fail_reasons_from_suite": strat.get("hard_fail_reasons"),
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
# suite_hard_fail evidence from equity CSV (best-effort)
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


def _suite_hard_fail_evidence_block(in_json_path: str, r: Dict[str, Any]) -> List[str]:
    """
    Best-effort evidence for suite_hard_fail strategies.
    """
    lines: List[str] = []
    sid = _fmt_str(r.get("id"))
    post_start = _fmt_str(r.get("post_start_date"))
    csv_path = _find_equity_csv(in_json_path, sid)

    if not csv_path:
        lines.append("- suite_hard_fail_evidence (from equity CSV, best-effort):")
        lines.append("  - status: `N/A` (equity csv not found)")
        return lines

    dates, eqs = _read_equity_csv_dates_and_equity(csv_path)
    if not dates:
        lines.append("- suite_hard_fail_evidence (from equity CSV, best-effort):")
        lines.append(f"  - equity_csv: `{csv_path}`")
        lines.append("  - status: `N/A` (could not read date/equity columns)")
        return lines

    full_ev = _equity_evidence_from_series(dates, eqs, date_ge=None)
    post_ev = _equity_evidence_from_series(dates, eqs, date_ge=post_start if post_start != "N/A" else None)

    lines.append("- suite_hard_fail_evidence (from equity CSV, best-effort):")
    lines.append(f"  - equity_csv: `{csv_path}`")

    lines.append("  - FULL:")
    if full_ev.get("ok"):
        lines.append(f"    - equity_min_date: `{_fmt_str(full_ev.get('equity_min_date'))}`")
        lines.append(f"    - neg_days_first_date: `{_fmt_str(full_ev.get('neg_days_first_date'))}`")
        lines.append(f"    - neg_days_last_date: `{_fmt_str(full_ev.get('neg_days_last_date'))}`")
        lines.append(f"    - neg_days_count: `{_fmt_int(full_ev.get('neg_days_count'))}`")
    else:
        lines.append(f"    - status: `N/A` ({_fmt_str(full_ev.get('error'))})")

    lines.append("  - POST (date >= post_start_date):")
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
        elif dsh < float(pass_th):
            # between [watch_lo, pass_th) -> WATCH band, not PASS, but still eligible for WATCH if other gates pass
            pass

    pmdd = _to_float(r.get("post_mdd"))
    if pmdd is not None and pmdd < float(mdd_floor):
        rs.append(f"EXCLUDE_POST_MDD_LT_{mdd_floor}")

    return rs


def _post_only_bucket(r: Dict[str, Any], pass_th: float, watch_lo: float, watch_hi: float) -> str:
    """
    Return PASS / WATCH / EXCLUDE based on post_delta_sharpe, assuming other excludes already checked separately.
    """
    dsh = _to_float(r.get("post_delta_sharpe0_vs_base"))
    if dsh is None:
        return "EXCLUDE"
    if dsh >= float(pass_th):
        return "PASS"
    if float(watch_lo) <= dsh < float(watch_hi):
        return "WATCH"
    return "EXCLUDE"


def _post_only_section_semantic1(rows: List[Dict[str, Any]]) -> List[str]:
    """
    v12: Semantic1 - Post-only PASS/WATCH lists are not filtered by renderer_v4 at all.
    Still annotate rows with suite_hard_fail=true as a warning note.
    """
    # thresholds (keep v11 defaults)
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

    # classify
    excluded: List[Tuple[str, List[str]]] = []
    pass_rows: List[Dict[str, Any]] = []
    watch_rows: List[Dict[str, Any]] = []

    for r in rows:
        rs = _post_only_policy_v3_reasons(r, pass_th=pass_th, watch_lo=watch_lo, watch_hi=watch_hi, mdd_floor=mdd_floor)

        # If ANY hard fail / missing / gonogo / mdd floor / too-bad sharpe => exclude
        # But allow WATCH band (delta_sharpe in [watch_lo, pass_th)) if it didn't trip "LT_watch_lo".
        # We detect LT_watch_lo by the explicit reason.
        if rs:
            # special case: if the ONLY delta-sharpe-related "issue" is being in WATCH band (i.e. no LT_watch_lo, no missing),
            # then it's not an exclusion reason. We keep rs as-is because we didn't add an "EXCLUDE" marker for WATCH band.
            # Here we exclude only if rs contains a real excluding token.
            excluding = True
            # If rs contains ONLY post_delta_sharpe_in_watch_band (we don't store such token), nothing to do.
            # So this stays True.
            excluded.append((_fmt_str(r.get("id")), rs))
            continue

        bucket = _post_only_bucket(r, pass_th=pass_th, watch_lo=watch_lo, watch_hi=watch_hi)
        if bucket == "PASS":
            pass_rows.append(r)
        elif bucket == "WATCH":
            watch_rows.append(r)
        else:
            # should be rare (already handled by rs)
            excluded.append((_fmt_str(r.get("id")), ["EXCLUDE_POST_DELTA_SHARPE_LT_-0.05"]))

    # sort within buckets by post calmar/sharpe
    pass_rows = sorted(pass_rows, key=lambda r: _rank_key_on_basis(r, "post"), reverse=True)
    watch_rows = sorted(watch_rows, key=lambda r: _rank_key_on_basis(r, "post"), reverse=True)

    top3_pass = [str(r.get("id")) for r in pass_rows[:3]]
    top3_watch = [str(r.get("id")) for r in watch_rows[:3]]

    # list those that are PASS/WATCH but suite_hard_fail=true (warn only)
    warn_full = [str(r.get("id")) for r in (pass_rows + watch_rows) if _bool_flag(r.get("suite_hard_fail"))]

    lines.append(f"- top3_post_only_PASS: `{', '.join(top3_pass) if top3_pass else 'N/A'}`")
    lines.append(f"- top3_post_only_WATCH: `{', '.join(top3_watch) if top3_watch else 'N/A'}`")
    lines.append(f"- post_only_total: `{len(rows)}`; pass: `{len(pass_rows)}`; watch: `{len(watch_rows)}`; excluded: `{len(excluded)}`")
    lines.append(f"- post_only_warn_full_blowup (suite_hard_fail=true): `{', '.join(warn_full) if warn_full else 'N/A'}`")
    lines.append("")

    def _note_for_post_only(r: Dict[str, Any]) -> str:
        notes: List[str] = []
        if _bool_flag(r.get("suite_hard_fail")):
            notes.append("WARNING: suite_hard_fail=true (FULL period floor violated; Semantic2 risk)")
        return "; ".join(notes) if notes else ""

    # PASS table
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

    # WATCH table
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

    # exclusions list
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

    # FULL singularity note
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

    # ranking block
    lines.append("## Ranking (policy)")
    lines.append(f"- ranking_policy: `{_fmt_str(ranking_policy)}`")
    lines.append(f"- renderer_filter_policy: `{renderer_filter_policy}`")
    lines.append(f"- full_segment_note: `{full_note}`")

    strategies = _strategy_list(obj)
    rows = [_mk_row(s) for s in strategies]
    rows_sorted = _sort_rows_like_policy(rows)

    top3_rec = _topn_recommended_renderer_v4(rows, n=3)
    lines.append(f"- top3_recommended: `{', '.join(top3_rec) if top3_rec else 'N/A'}`")

    if isinstance(top3_raw, list):
        lines.append(f"- top3_raw_from_suite: `{', '.join([str(x) for x in top3_raw])}`")
    else:
        lines.append(f"- top3_raw_from_suite: `{_fmt_str(top3_raw)}`")
    lines.append("")

    # strategies table (ALL rows, sorted by suite policy)
    lines.append("## Strategies")
    lines.append("note_full: `FULL_* columns may be contaminated by a known data singularity issue. Do not use FULL alone for go/no-go; use POST_* as primary.`")
    lines.append("")
    lines.append(
        "| id | ok | suite_hard_fail | entry_mode | L | "
        "full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | "
        "post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔMDD | post_ΔSharpe | "
        "post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades | rv20_skipped |"
    )
    lines.append(
        "|---|---:|---:|---|---:|"
        "---:|---:|---:|---:|---:|---:|---:|"
        "---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        "---|---|---:|---:|---:|---:|---:|---:|"
    )

    for r in rows_sorted:
        lines.append(
            "| {id} | {ok} | {shf} | {entry_mode} | {L} | "
            "{full_cagr} | {full_mdd} | {full_sh} | {full_calmar} | {dcagr} | {dmdd} | {dsh} | "
            "{post_ok} | {split} | {post_start} | {post_n} | {post_years} | {post_cagr} | {post_mdd} | {post_sh} | {post_calmar} | {post_dcagr} | {post_dmdd} | {post_dsh} | "
            "{gonogo} | {rank_basis} | {neg_days} | {eq_min} | {post_neg_days} | {post_eq_min} | {trades} | {rv20} |".format(
                id=_escape_md_cell(r.get("id")),
                ok=_escape_md_cell(r.get("ok")),
                shf=_escape_md_cell(r.get("suite_hard_fail")),
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
                rv20=_fmt_int(r.get("rv20_skipped")),
            )
        )

    lines.append("")

    # exclusions summary (renderer v4)
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

    # Always vs Trend compare section
    lines.extend(_always_vs_trend_table(rows, trend_rule=str(trend_rule)))

    # Post-only view (Semantic1)
    lines.extend(_post_only_section_semantic1(rows))

    # Post go/no-go details + suite_hard_fail evidence
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
                # if suite stored hard_fail_reasons, show them
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


if __name__ == "__main__":
    main()