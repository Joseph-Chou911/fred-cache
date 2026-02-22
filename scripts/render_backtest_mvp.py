#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_backtest_mvp.py
Pure renderer for backtest_mvp.json -> report.md
- Does NOT recompute anything.
- Summarizes: suite status, top3, per-strategy perf, post_gonogo, key audits.
"""

from __future__ import annotations
import argparse
import json
from typing import Any, Dict, List, Optional


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_pct(x: Any, nd: int = 2) -> str:
    try:
        if x is None:
            return "N/A"
        v = float(x) * 100.0
        return f"{v:.{nd}f}%"
    except Exception:
        return "N/A"


def _fmt_num(x: Any, nd: int = 3) -> str:
    try:
        if x is None:
            return "N/A"
        v = float(x)
        return f"{v:.{nd}f}"
    except Exception:
        return "N/A"


def _get(d: Dict[str, Any], path: List[str], default=None):
    cur: Any = d
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _strategy_brief(s: Dict[str, Any]) -> Dict[str, Any]:
    perf = s.get("perf") or {}
    lev = (perf.get("leverage") or {})
    base = (perf.get("base_only") or {})
    delta = (perf.get("delta_vs_base") or {})
    audit = s.get("audit") or {}
    seg = s.get("segmentation") or {}
    return {
        "strategy_id": s.get("strategy_id"),
        "ok": bool(s.get("ok", True)),
        "entry_mode": _get(s, ["params", "entry_mode"]),
        "L": (1.0 + float(_get(s, ["params", "leverage_frac"], 0.0))) if _get(s, ["params", "leverage_frac"]) is not None else None,
        "full": {
            "cagr": lev.get("cagr"),
            "mdd": lev.get("mdd"),
            "sharpe0": lev.get("sharpe0"),
            "calmar": perf.get("calmar_leverage"),
        },
        "delta_vs_base": {
            "cagr": delta.get("cagr"),
            "mdd": delta.get("mdd"),
            "sharpe0": delta.get("sharpe0"),
        },
        "post_gonogo": _get(s, ["post_gonogo", "decision"]),
        "post_ok": bool(_get(seg, ["enabled"], False) and _get(seg, ["segments", "post", "ok"], False)),
        "post": {
            "cagr": _get(seg, ["segments", "post", "summary", "perf_leverage", "cagr"]),
            "mdd": _get(seg, ["segments", "post", "summary", "perf_leverage", "mdd"]),
            "sharpe0": _get(seg, ["segments", "post", "summary", "perf_leverage", "sharpe0"]),
            "calmar": _get(seg, ["segments", "post", "summary", "calmar_leverage"]),
        },
        "audit": {
            "rows": audit.get("rows"),
            "start": audit.get("start_date"),
            "end": audit.get("end_date"),
            "trades": audit.get("trades"),
            "equity_negative_days": audit.get("equity_negative_days"),
            "equity_min": audit.get("equity_min"),
            "breaks_detected": audit.get("breaks_detected"),
        },
        "error": s.get("error"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_json", required=True)
    ap.add_argument("--out_md", default="backtest_mvp_report.md")
    args = ap.parse_args()

    j = _read_json(args.in_json)

    lines: List[str] = []
    lines.append("# Backtest MVP Summary\n")
    lines.append(f"- generated_at_utc: `{j.get('generated_at_utc')}`")
    lines.append(f"- script_fingerprint: `{j.get('script_fingerprint')}`")
    lines.append(f"- suite_ok: `{j.get('suite_ok')}`")
    if j.get("abort_reason"):
        lines.append(f"- abort_reason: `{j.get('abort_reason')}`")
    lines.append("")

    cmp = j.get("compare") or {}
    top3 = cmp.get("top3_by_policy") or []
    lines.append("## Ranking (policy)")
    lines.append(f"- ranking_policy: `{cmp.get('ranking_policy')}`")
    lines.append(f"- top3_by_policy: `{', '.join(top3) if top3 else 'N/A'}`")
    lines.append("")

    strategies = j.get("strategies") or []
    briefs = [_strategy_brief(s) for s in strategies if isinstance(s, dict)]

    lines.append("## Strategies")
    lines.append("| id | ok | entry_mode | L | full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | post_go/no-go | neg_days | equity_min | trades |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|")
    for b in briefs:
        lines.append(
            f"| {b['strategy_id']} | {str(b['ok'])} | {b['entry_mode']} | {_fmt_num(b['L'],2)} | "
            f"{_fmt_pct(b['full']['cagr'])} | {_fmt_pct(b['full']['mdd'])} | {_fmt_num(b['full']['sharpe0'])} | {_fmt_num(b['full']['calmar'])} | "
            f"{_fmt_pct(b['delta_vs_base']['cagr'])} | {_fmt_pct(b['delta_vs_base']['mdd'])} | {_fmt_num(b['delta_vs_base']['sharpe0'])} | "
            f"{b['post_gonogo']} | {b['audit']['equity_negative_days']} | {_fmt_num(b['audit']['equity_min'],2)} | {b['audit']['trades']} |"
        )
    lines.append("")

    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"OK: wrote {args.out_md}")


if __name__ == "__main__":
    main()