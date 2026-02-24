#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_backtest_mvp.py

Render backtest_tw0050_leverage_mvp suite json (lite or full) into a compact Markdown report.

v11 (2026-02-24):
- ADD(evidence): For strategies with suite_hard_fail=true, try to locate per-strategy equity CSV and print:
  * full_equity_min_date
  * full_neg_days_first_date / full_neg_days_last_date
  * post_equity_min_date / post_neg_days_first_date / post_neg_days_last_date (post_start_date-based)
- Robust file lookup:
  * If suite JSON provides any equity csv mapping, use it.
  * Else search cache_dir for files containing both "<strategy_id>" and "equity" and ending with ".csv".
  * Fallback: if strategy_id == export_strategy_id, also try "backtest_mvp_equity.csv" in cache_dir.
- Keep v10 structure:
  * Ranking (policy) + renderer_filter_policy_v4 + full_segment_note
  * Strategies table (ALL strategies, sorted by suite policy)
  * Exclusions (eligible/excluded + per-strategy reasons)
  * Deterministic Always vs Trend compare table (trend_rule from suite)
  * Post-only View: PASS/WATCH (post_only_policy_v3)
  * Post Go/No-Go Details (compact) + suite_hard_fail reasons + NEW evidence dates when available

Notes:
- This renderer is best-effort on equity evidence: if per-strategy equity CSV is not available, prints N/A.
- Equity CSV expected columns: "date" and "equity" (as produced by backtest script export). Extra columns ignored.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


SCRIPT_FINGERPRINT = "render_backtest_mvp@2026-02-24.v11.suite_hard_fail_date_evidence"


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


def _is_true(x: Any) -> bool:
    return x is True


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


def _extract_suite_hard_fail(strat: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    backtest side may emit:
      - suite_hard_fail: bool
      - hard_fail: bool (legacy)
      - hard_fail_reasons: list[str]
    """
    shf = None
    if "suite_hard_fail" in strat:
        shf = bool(strat.get("suite_hard_fail"))
    elif "hard_fail" in strat:
        shf = bool(strat.get("hard_fail"))
    else:
        shf = False

    reasons: List[str] = []
    r = strat.get("suite_hard_fail_reasons")
    if isinstance(r, list):
        reasons = [str(x) for x in r if x is not None]
    else:
        r2 = strat.get("hard_fail_reasons")
        if isinstance(r2, list):
            reasons = [str(x) for x in r2 if x is not None]
    return bool(shf), reasons


def _extract_rv20_skipped(audit: Any) -> Optional[int]:
    if not isinstance(audit, dict):
        return None
    # v26.5+ suggests this key
    for k in ["skipped_entries_on_rv20", "rv20_skipped", "skipped_rv20"]:
        if k in audit:
            try:
                return int(audit.get(k))
            except Exception:
                return None
    return None


def _extract_full_metrics(strat: Dict[str, Any]) -> Dict[str, Any]:
    perf = strat.get("perf") or {}
    lev = perf.get("leverage") or {}
    delta = perf.get("delta_vs_base") or {}
    audit = strat.get("audit") or {}

    suite_hf, suite_hf_reasons = _extract_suite_hard_fail(strat)

    return {
        "suite_hard_fail": suite_hf,
        "suite_hard_fail_reasons": suite_hf_reasons,
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
        "rv20_skipped": _extract_rv20_skipped(audit),
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
        "rank_basis": _rank_basis(bool(post.get("post_ok"))),
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
        if _is_true(r.get("post_ok")):
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

    if not bool(r.get("ok")):
        reasons.append("EXCLUDE_OK_FALSE")

    if bool(r.get("suite_hard_fail")):
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


def _is_eligible_for_recommendation_v4(r: Dict[str, Any]) -> bool:
    return len(_exclusion_reasons_renderer_filter_v4(r)) == 0


def _rank_key_on_basis(r: Dict[str, Any], basis: str) -> Tuple[float, float, str]:
    rid = _fmt_str(r.get("id"))
    if basis == "post":
        return (_finite_or_neginf(r.get("post_calmar")), _finite_or_neginf(r.get("post_sharpe0")), rid)
    return (_finite_or_neginf(r.get("full_calmar")), _finite_or_neginf(r.get("full_sharpe0")), rid)


def _topn_recommended_v4(rows: List[Dict[str, Any]], n: int = 3) -> List[str]:
    eligible = [r for r in rows if _is_eligible_for_recommendation_v4(r)]
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


def _always_vs_trend_table_v2(rows: List[Dict[str, Any]], trend_rule: str) -> List[str]:
    """
    compare_v2: for same L, compare post if both post_ok else full;
    winner=calmar desc, then sharpe0 desc, then id
    trend_id uses suite trend_rule.
    If either side excluded by renderer filter v4, show N/A with exclusion notes.
    """
    lines: List[str] = []
    lines.append("## Deterministic Always vs Trend (checkmarks)")
    lines.append("compare_policy: `compare_v2: for same L, compare post if both post_ok else full; winner=calmar desc, then sharpe0 desc, then id; trend_id uses suite trend_rule`")
    lines.append(f"trend_rule: `{_fmt_str(trend_rule)}`")
    lines.append("")
    lines.append("| L | basis | trend_id | always_id | winner | verdict |")
    lines.append("|---:|---|---|---|---|---|")

    for L in ["1.1x", "1.2x", "1.3x", "1.5x"]:
        trend_id = f"trend_leverage_{trend_rule}_{L}"
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

        basis = "post" if (_is_true(rt.get("post_ok")) and _is_true(ra.get("post_ok"))) else "full"
        winner = _compare_two_rows(rt, ra, basis)
        verdict = "WIN:trend" if winner == trend_id else ("WIN:always" if winner == always_id else "WIN:tiebreak")
        lines.append(f"| {L} | {basis} | {trend_id} | {always_id} | {winner} | {verdict} |")

    lines.append("")
    return lines


# =========================
# post-only view PASS/WATCH
# =========================
_POST_ONLY_PASS_DELTA_SHARPE_GE = -0.03
_POST_ONLY_WATCH_DELTA_SHARPE_LO = -0.05
_POST_ONLY_WATCH_DELTA_SHARPE_HI = -0.03
_POST_ONLY_POST_MDD_FLOOR = -0.40


def _post_only_reasons_v3(r: Dict[str, Any]) -> List[str]:
    """
    post_only_policy_v3:
      require post_ok=true;
      exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%);
      exclude post_gonogo=NO_GO;
      exclude missing post rank metrics;
      PASS gate: require post_ΔSharpe >= -0.03;
      WATCH gate: require -0.05 <= post_ΔSharpe < -0.03 (not excluded, but classified as WATCH);
      post_MDD floor: require post_MDD >= -0.4;
      ignore FULL and ignore suite_hard_fail.
    This function returns exclusion reasons only (WATCH is not excluded).
    """
    reasons: List[str] = []

    if not bool(r.get("ok")):
        reasons.append("EXCLUDE_OK_FALSE")

    if not bool(r.get("post_ok")):
        reasons.append("EXCLUDE_POST_OK_FALSE")
        return reasons

    # post hard fails
    reasons += _hard_fail_reasons_for_segment(
        "POST", r.get("post_mdd"), r.get("post_equity_min"), r.get("post_neg_days")
    )

    if _fmt_str(r.get("post_gonogo")) == "NO_GO":
        reasons.append("EXCLUDE_POST_GONOGO_NO_GO")

    if (_to_float(r.get("post_calmar")) is None) or (_to_float(r.get("post_sharpe0")) is None):
        reasons.append("EXCLUDE_MISSING_RANK_METRICS_POST")

    # MDD floor
    pmdd = _to_float(r.get("post_mdd"))
    if pmdd is not None and pmdd < float(_POST_ONLY_POST_MDD_FLOOR):
        reasons.append("EXCLUDE_POST_MDD_LT_-0.4")

    # delta sharpe gates
    dsh = _to_float(r.get("post_delta_sharpe0_vs_base"))
    if dsh is None:
        reasons.append("EXCLUDE_POST_DELTA_SHARPE_MISSING")
    else:
        # Exclude only if below WATCH lower bound
        if dsh < float(_POST_ONLY_WATCH_DELTA_SHARPE_LO):
            reasons.append("EXCLUDE_POST_DELTA_SHARPE_LT_-0.05")

    return reasons


def _post_only_class_v3(r: Dict[str, Any]) -> str:
    """
    Returns one of: PASS, WATCH, EXCLUDED.
    """
    ex = _post_only_reasons_v3(r)
    if ex:
        return "EXCLUDED"

    dsh = _to_float(r.get("post_delta_sharpe0_vs_base"))
    if dsh is None:
        return "EXCLUDED"

    if dsh >= float(_POST_ONLY_PASS_DELTA_SHARPE_GE):
        return "PASS"
    if float(_POST_ONLY_WATCH_DELTA_SHARPE_LO) <= dsh < float(_POST_ONLY_WATCH_DELTA_SHARPE_HI):
        return "WATCH"
    # between -0.05 and -0.03 is already WATCH; below -0.05 excluded; above -0.03 PASS
    return "EXCLUDED"


def _post_only_rank_key(r: Dict[str, Any]) -> Tuple[float, float, str]:
    rid = _fmt_str(r.get("id"))
    return (_finite_or_neginf(r.get("post_calmar")), _finite_or_neginf(r.get("post_sharpe0")), rid)


# =========================
# equity evidence (CSV)
# =========================
def _default_cache_dir(obj: Dict[str, Any], in_json_path: str) -> str:
    # prefer suite inputs.cache_dir if present
    cd = _get(obj, ["inputs", "cache_dir"], default=None)
    if isinstance(cd, str) and cd.strip():
        return cd.strip()
    # else, directory of input json
    return os.path.dirname(os.path.abspath(in_json_path)) or "."


def _equity_csv_map_from_obj(obj: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Optional mapping from suite json, if present:
      - obj["outputs"]["equity_csv_by_strategy"]
      - obj["equity_csv_by_strategy"]
    """
    cand1 = _get(obj, ["outputs", "equity_csv_by_strategy"], default=None)
    if isinstance(cand1, dict):
        out = {}
        for k, v in cand1.items():
            if k is None or v is None:
                continue
            out[str(k)] = str(v)
        return out or None

    cand2 = obj.get("equity_csv_by_strategy")
    if isinstance(cand2, dict):
        out = {}
        for k, v in cand2.items():
            if k is None or v is None:
                continue
            out[str(k)] = str(v)
        return out or None

    return None


def _find_equity_csv_for_strategy(
    *,
    cache_dir: str,
    sid: str,
    export_sid: Optional[str],
    equity_map: Optional[Dict[str, str]],
) -> Optional[str]:
    """
    Best-effort search order:
    1) equity_map[sid] if provided and exists
    2) scan cache_dir for "*<sid>*equity*.csv"
    3) if sid == export_sid, also try "backtest_mvp_equity.csv"
    Returns absolute path if found.
    """
    if equity_map and sid in equity_map:
        p = equity_map[sid]
        # allow relative paths relative to cache_dir
        p2 = p
        if not os.path.isabs(p2):
            p2 = os.path.join(cache_dir, p2)
        if os.path.isfile(p2):
            return os.path.abspath(p2)

    if os.path.isdir(cache_dir):
        try:
            files = sorted(os.listdir(cache_dir))
        except Exception:
            files = []
        sid_lc = sid.lower()
        cands: List[str] = []
        for fn in files:
            fn_lc = fn.lower()
            if not fn_lc.endswith(".csv"):
                continue
            if "equity" not in fn_lc:
                continue
            if sid_lc in fn_lc:
                cands.append(fn)
        if cands:
            # choose shortest name then lexicographic
            cands_sorted = sorted(cands, key=lambda x: (len(x), x))
            p3 = os.path.join(cache_dir, cands_sorted[0])
            if os.path.isfile(p3):
                return os.path.abspath(p3)

        # fallback for exported strategy
        if export_sid is not None and sid == export_sid:
            p4 = os.path.join(cache_dir, "backtest_mvp_equity.csv")
            if os.path.isfile(p4):
                return os.path.abspath(p4)

    return None


def _load_equity_series(csv_path: str) -> Optional[List[Tuple[str, float]]]:
    """
    Load (date_str, equity_float) list.
    Expected columns: date, equity
    Dates assumed ISO-like; we keep first 10 chars (YYYY-MM-DD).
    """
    if not csv_path or (not os.path.isfile(csv_path)):
        return None

    out: List[Tuple[str, float]] = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return None
            # column name normalization
            cols = {c.lower(): c for c in reader.fieldnames if isinstance(c, str)}
            date_col = cols.get("date") or cols.get("date_ts") or cols.get("date_time") or cols.get("datetime")
            eq_col = cols.get("equity")
            if date_col is None or eq_col is None:
                return None

            for row in reader:
                ds = row.get(date_col)
                ev = row.get(eq_col)
                if ds is None or ev is None:
                    continue
                ds2 = str(ds).strip()
                if len(ds2) >= 10:
                    ds2 = ds2[:10]
                v = _to_float(ev)
                if v is None:
                    continue
                out.append((ds2, float(v)))
    except Exception:
        return None

    return out or None


def _equity_evidence_from_series(
    ser: List[Tuple[str, float]],
    *,
    start_date_inclusive: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute:
      - equity_min, equity_min_date
      - neg_days_count, neg_first_date, neg_last_date
    If start_date_inclusive provided, filter to date >= start_date.
    """
    if not ser:
        return {"ok": False}

    filt: List[Tuple[str, float]] = []
    if start_date_inclusive and isinstance(start_date_inclusive, str) and start_date_inclusive.strip():
        sd = start_date_inclusive.strip()[:10]
        for d, e in ser:
            if isinstance(d, str) and d[:10] >= sd:
                filt.append((d[:10], e))
    else:
        filt = [(d[:10], e) for d, e in ser if isinstance(d, str)]

    if not filt:
        return {"ok": False, "note": "empty after start_date filter"}

    # equity min
    emin = None
    emin_date = None
    for d, e in filt:
        if not np.isfinite(e):
            continue
        if emin is None or e < float(emin):
            emin = float(e)
            emin_date = d

    # neg days range
    neg_dates = [d for d, e in filt if np.isfinite(e) and float(e) < 0.0]
    neg_cnt = len(neg_dates)

    out = {
        "ok": True,
        "equity_min": emin,
        "equity_min_date": emin_date,
        "neg_days_count": neg_cnt,
        "neg_first_date": (min(neg_dates) if neg_dates else None),
        "neg_last_date": (max(neg_dates) if neg_dates else None),
    }
    return out


def _evidence_block_for_strategy(
    *,
    obj: Dict[str, Any],
    in_json_path: str,
    sid: str,
    post_start_date: Optional[str],
) -> Dict[str, Any]:
    """
    Returns evidence dict with keys:
      - full: {...}
      - post: {...}
      - csv_path: str|None
      - ok: bool
    """
    cache_dir = _default_cache_dir(obj, in_json_path)
    export_sid = _get(obj, ["outputs", "export_strategy_id"], default=None)
    if not isinstance(export_sid, str):
        export_sid = None

    eq_map = _equity_csv_map_from_obj(obj)
    p = _find_equity_csv_for_strategy(cache_dir=cache_dir, sid=sid, export_sid=export_sid, equity_map=eq_map)
    if p is None:
        return {"ok": False, "csv_path": None, "note": "equity csv not found"}

    ser = _load_equity_series(p)
    if not ser:
        return {"ok": False, "csv_path": p, "note": "failed to load equity series"}

    full = _equity_evidence_from_series(ser, start_date_inclusive=None)
    post = _equity_evidence_from_series(ser, start_date_inclusive=post_start_date)

    return {"ok": True, "csv_path": p, "full": full, "post": post}


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

    # trend_rule (for compare table naming)
    trend_rule = _get(obj, ["strategy_suite", "trend_rule"], default="price_gt_ma60")
    if not isinstance(trend_rule, str) or not trend_rule.strip():
        trend_rule = "price_gt_ma60"

    full_note = (
        "FULL_* metrics may be impacted by data singularity around 2014 (price series anomaly/adjustment). "
        "Treat FULL as audit-only; prefer POST for decision and ranking."
    )

    renderer_filter_policy = (
        "renderer_rank_filter_v4: exclude(ok=false); exclude(suite_hard_fail=true); "
        "exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post); "
        "exclude(post_gonogo=NO_GO); exclude(missing rank metrics on chosen basis); "
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

    # build rows
    strategies = _strategy_list(obj)
    rows = [_mk_row(s) for s in strategies]
    rows_sorted = _sort_rows_like_policy(rows)

    top3_rec = _topn_recommended_v4(rows, n=3)
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

    # exclusions summary (renderer filter v4)
    lines.append("## Exclusions (not eligible for recommendation)")
    total = len(rows)
    eligible_rows = [r for r in rows if _is_eligible_for_recommendation_v4(r)]
    excluded_rows = [r for r in rows if not _is_eligible_for_recommendation_v4(r)]

    suite_hf = 0
    hard_fail = 0
    post_no_go = 0
    ok_false = 0
    missing_rank = 0

    for r in excluded_rows:
        rs = _exclusion_reasons_renderer_filter_v4(r)
        if "EXCLUDE_SUITE_HARD_FAIL_TRUE" in rs:
            suite_hf += 1
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
        f"(suite_hard_fail={suite_hf}, hard_fail_fullpost={hard_fail}, post_NO_GO={post_no_go}, ok_false={ok_false}, missing_rank_metrics={missing_rank})"
    )
    lines.append("")

    for r in sorted(excluded_rows, key=lambda x: _fmt_str(x.get("id"))):
        rid = _fmt_str(r.get("id"))
        rs = _exclusion_reasons_renderer_filter_v4(r)
        lines.append(f"- {rid}: `{', '.join(rs)}`")

    lines.append("")

    # Always vs Trend compare section
    lines.extend(_always_vs_trend_table_v2(rows, trend_rule=trend_rule))

    # Post-only View (PASS/WATCH)
    lines.append("## Post-only View (After Singularity / Ignore FULL)")
    lines.append(
        "post_only_policy_v3: `require post_ok=true; exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%); "
        "exclude post_gonogo=NO_GO; exclude missing post rank metrics; "
        f"PASS gate: require post_ΔSharpe>= {_POST_ONLY_PASS_DELTA_SHARPE_GE}; "
        f"WATCH gate: require {_POST_ONLY_WATCH_DELTA_SHARPE_LO}<=post_ΔSharpe<{_POST_ONLY_WATCH_DELTA_SHARPE_HI}; "
        f"post_MDD floor: require post_MDD>= {_POST_ONLY_POST_MDD_FLOOR} (i.e. not worse than -40%); "
        "ignore FULL and ignore suite_hard_fail.`"
    )

    cls_map = {r["id"]: _post_only_class_v3(r) for r in rows}
    pass_rows = [r for r in rows if cls_map.get(r["id"]) == "PASS"]
    watch_rows = [r for r in rows if cls_map.get(r["id"]) == "WATCH"]
    excl_rows_po = [r for r in rows if cls_map.get(r["id"]) == "EXCLUDED"]

    pass_sorted = sorted(pass_rows, key=_post_only_rank_key, reverse=True)
    watch_sorted = sorted(watch_rows, key=_post_only_rank_key, reverse=True)

    top3_pass = [str(r["id"]) for r in pass_sorted[:3]]
    top3_watch = [str(r["id"]) for r in watch_sorted[:3]]

    # would-be pass/watch but excluded by renderer v4
    would_be = []
    for r in pass_sorted + watch_sorted:
        if not _is_eligible_for_recommendation_v4(r):
            would_be.append(str(r.get("id")))

    lines.append(f"- top3_post_only_PASS: `{', '.join(top3_pass) if top3_pass else 'N/A'}`")
    lines.append(f"- top3_post_only_WATCH: `{', '.join(top3_watch) if top3_watch else 'N/A'}`")
    lines.append(f"- post_only_total: `{len(rows)}`; pass: `{len(pass_rows)}`; watch: `{len(watch_rows)}`; excluded: `{len(excl_rows_po)}`")
    lines.append(f"- would_be_pass_or_watch_post_only_but_excluded_by_renderer_v4: `{', '.join(would_be) if would_be else 'N/A'}`")
    lines.append("")

    # PASS table
    lines.append("### PASS (deploy-grade, strict)")
    lines.append("| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for r in pass_sorted:
        note = ""
        exv4 = _exclusion_reasons_renderer_filter_v4(r)
        if exv4:
            note = f"excluded_by_renderer_v4: {', '.join(exv4)}"
        lines.append(
            "| {id} | {cagr} | {mdd} | {sh} | {cal} | {dsh} | {note} |".format(
                id=_escape_md_cell(r.get("id")),
                cagr=_fmt_pct(r.get("post_cagr")),
                mdd=_fmt_pct(r.get("post_mdd")),
                sh=_fmt_num(r.get("post_sharpe0"), nd=3),
                cal=_fmt_num(r.get("post_calmar"), nd=3),
                dsh=_fmt_num(r.get("post_delta_sharpe0_vs_base"), nd=3),
                note=_escape_md_cell(note) if note else " ",
            )
        )
    lines.append("")

    # WATCH table
    lines.append("### WATCH (research-grade, not for deploy)")
    lines.append("| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for r in watch_sorted:
        note = ""
        exv4 = _exclusion_reasons_renderer_filter_v4(r)
        if exv4:
            note = f"excluded_by_renderer_v4: {', '.join(exv4)}"
        lines.append(
            "| {id} | {cagr} | {mdd} | {sh} | {cal} | {dsh} | {note} |".format(
                id=_escape_md_cell(r.get("id")),
                cagr=_fmt_pct(r.get("post_cagr")),
                mdd=_fmt_pct(r.get("post_mdd")),
                sh=_fmt_num(r.get("post_sharpe0"), nd=3),
                cal=_fmt_num(r.get("post_calmar"), nd=3),
                dsh=_fmt_num(r.get("post_delta_sharpe0_vs_base"), nd=3),
                note=_escape_md_cell(note) if note else " ",
            )
        )
    lines.append("")

    # Post-only Exclusions list
    lines.append("### Post-only Exclusions (reasons)")
    for r in sorted(excl_rows_po, key=lambda x: _fmt_str(x.get("id"))):
        rid = _fmt_str(r.get("id"))
        rs = _post_only_reasons_v3(r)
        lines.append(f"- {rid}: `{', '.join(rs)}`")
    lines.append("")

    # Post go/no-go details + suite_hard_fail evidence
    lines.append("## Post Go/No-Go Details (compact)")
    any_details = False
    for r in rows_sorted:
        dec = _fmt_str(r.get("post_gonogo"))
        if dec != "N/A" or _is_true(r.get("post_ok")):
            any_details = True
            rid = _escape_md_cell(r.get("id"))
            lines.append(f"### {rid}")
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

            # suite_hard_fail info if present
            if bool(r.get("suite_hard_fail")):
                lines.append("- suite_hard_fail: `true`")
                shr = r.get("suite_hard_fail_reasons")
                if isinstance(shr, list) and shr:
                    for msg in shr[:8]:
                        lines.append(f"  - {str(msg)}")
                else:
                    lines.append("  - N/A (no suite hard fail reasons in JSON)")
                lines.append("")

                # NEW: evidence dates via equity csv (best-effort)
                ev = _evidence_block_for_strategy(
                    obj=obj,
                    in_json_path=in_json_path,
                    sid=_fmt_str(r.get("id")),
                    post_start_date=_fmt_str(r.get("post_start_date")) if r.get("post_start_date") is not None else None,
                )
                lines.append("- suite_hard_fail_evidence (from equity CSV, best-effort):")
                if not ev.get("ok"):
                    lines.append(f"  - status: `N/A` ({_fmt_str(ev.get('note'))})")
                else:
                    lines.append(f"  - equity_csv: `{_escape_md_cell(ev.get('csv_path'))}`")

                    full_ev = ev.get("full") or {}
                    if isinstance(full_ev, dict) and full_ev.get("ok"):
                        lines.append("  - FULL:")
                        lines.append(f"    - equity_min_date: `{_fmt_str(full_ev.get('equity_min_date'))}`")
                        lines.append(f"    - neg_days_first_date: `{_fmt_str(full_ev.get('neg_first_date'))}`")
                        lines.append(f"    - neg_days_last_date: `{_fmt_str(full_ev.get('neg_last_date'))}`")
                        lines.append(f"    - neg_days_count: `{_fmt_str(full_ev.get('neg_days_count'))}`")
                    else:
                        lines.append("  - FULL: `N/A`")

                    post_ev = ev.get("post") or {}
                    if isinstance(post_ev, dict) and post_ev.get("ok"):
                        lines.append("  - POST (date >= post_start_date):")
                        lines.append(f"    - post_start_date: `{_fmt_str(r.get('post_start_date'))}`")
                        lines.append(f"    - equity_min_date: `{_fmt_str(post_ev.get('equity_min_date'))}`")
                        lines.append(f"    - neg_days_first_date: `{_fmt_str(post_ev.get('neg_first_date'))}`")
                        lines.append(f"    - neg_days_last_date: `{_fmt_str(post_ev.get('neg_last_date'))}`")
                        lines.append(f"    - neg_days_count: `{_fmt_str(post_ev.get('neg_days_count'))}`")
                    else:
                        lines.append("  - POST: `N/A`")
                lines.append("")

    if not any_details:
        lines.append("- N/A (no post_gonogo details found in JSON)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_json", required=True, help="input json path (lite or full)")
    ap.add_argument("--out_md", required=True, help="output markdown path")
    # Optional hint: in case suite inputs.cache_dir is relative / not resolvable in your runtime.
    # This script will still default to obj.inputs.cache_dir, else directory of in_json.
    # We keep this arg for flexibility without breaking existing callers.
    ap.add_argument("--cache_dir", default=None, help="optional cache dir override for equity csv search")
    args = ap.parse_args()

    obj = _read_json(str(args.in_json))

    # If user passes --cache_dir, override obj.inputs.cache_dir in-memory (renderer-only).
    if args.cache_dir:
        if "inputs" not in obj or not isinstance(obj.get("inputs"), dict):
            obj["inputs"] = {}
        obj["inputs"]["cache_dir"] = str(args.cache_dir)

    md = _render_md(obj, in_json_path=str(args.in_json))

    out_md = str(args.out_md)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)

    print("OK: wrote", out_md)


if __name__ == "__main__":
    main()