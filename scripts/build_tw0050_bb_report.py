#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build TW0050 BB Monitor Report (Markdown)

Reads:
- <cache_dir>/stats_latest.json  (required)

Writes:
- <output> (default: <cache_dir>/report_tw0050_bb.md)

Update highlights:
- Supports direction-complete conditional stats:
  * z <= z_threshold_cheap (default -1.5)
  * z >= z_threshold_hot   (default +1.5)
  * z >= z_threshold_hot2  (default +2.0)
- 15-second summary auto-selects the most relevant conditional bucket based on latest z.
- Prints dq notes (including split-heal notes) for auditability.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and x == x  # NaN check


def fmt_num(x: Any, nd: int = 4) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return str(x)
    if _is_num(x):
        return f"{float(x):.{nd}f}"
    return str(x)


def fmt_num_compact(x: Any, nd: int = 2) -> str:
    if x is None or not _is_num(x):
        return "NA"
    return f"{float(x):.{nd}f}"


def fmt_pct_from_pct_value(x: Any, nd: int = 2) -> str:
    """
    Input x is already in percent unit (e.g. 27.60 means 27.60%)
    """
    if x is None or not _is_num(x):
        return "NA"
    return f"{float(x):.{nd}f}%"


def safe_get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def choose_relevant_bucket(
    latest_z: Optional[float],
    thr_cheap: float,
    thr_hot: float,
    thr_hot2: float,
    all_days: Dict[str, Any],
    cheap: Dict[str, Any],
    hot: Dict[str, Any],
    hot2: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Pick conditional stats that match latest_z direction; fall back to all_days.
    """
    if latest_z is None or not _is_num(latest_z):
        return ("all", all_days)

    z = float(latest_z)
    if z <= thr_cheap:
        return (f"cond(z<={thr_cheap:g})", cheap)
    if z >= thr_hot2:
        return (f"cond(z>={thr_hot2:g})", hot2)
    if z >= thr_hot:
        return (f"cond(z>={thr_hot:g})", hot)
    return ("all (no extreme z)", all_days)


def fmt_mdd_stats_line(prefix: str, stats: Dict[str, Any]) -> str:
    n = stats.get("n", 0)
    p50 = stats.get("p50", None)
    p10 = stats.get("p10", None)
    mn = stats.get("min", None)
    conf = stats.get("conf", "NA")
    return (
        f"- {prefix}: n={n}, p50={fmt_pct_from_pct_value(p50*100 if _is_num(p50) and abs(p50) < 2 else p50, 2) if _is_num(p50) else 'NA'}, "
        f"p10={fmt_pct_from_pct_value(p10*100 if _is_num(p10) and abs(p10) < 2 else p10, 2) if _is_num(p10) else 'NA'}, "
        f"min={fmt_pct_from_pct_value(mn*100 if _is_num(mn) and abs(mn) < 2 else mn, 2) if _is_num(mn) else 'NA'} (conf={conf})"
    )


def maybe_as_pct_already(x: Any) -> Any:
    """
    Some older stats used raw decimals (e.g. -0.0181) while reports display percents.
    In your current pipeline, forward_mdd stats are in decimal units (e.g. -0.0181).
    We will keep them as decimals internally and format as percent below.
    """
    return x


def fmt_mdd_stats_inline(stats: Dict[str, Any]) -> str:
    """
    forward_mdd stats are decimals (e.g. -0.0181) => print as percents.
    """
    n = stats.get("n", 0)
    p50 = stats.get("p50", None)
    p10 = stats.get("p10", None)
    mn = stats.get("min", None)
    conf = stats.get("conf", "NA")

    def dec_to_pct(v: Any) -> str:
        if v is None or not _is_num(v):
            return "NA"
        return f"{float(v) * 100:.2f}%"

    return f"n={n}, p50={dec_to_pct(p50)}, p10={dec_to_pct(p10)}, min={dec_to_pct(mn)} (conf={conf})"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build TW0050 BB report from stats_latest.json")
    ap.add_argument("--cache_dir", required=True, help="Directory containing stats_latest.json")
    ap.add_argument("--output", default=None, help="Output markdown path (default: <cache_dir>/report_tw0050_bb.md)")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    stats_path = cache_dir / "stats_latest.json"
    stats = read_json(stats_path)

    meta = stats.get("meta", {})
    dq = stats.get("dq", {})
    latest = stats.get("latest", {})
    fwd = stats.get("forward_mdd", {})

    output_path = Path(args.output) if args.output else (cache_dir / "report_tw0050_bb.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_generated_at_utc = safe_get(meta, "run_ts_utc", "NA")
    symbol = safe_get(meta, "symbol", "NA")
    as_of_date = safe_get(meta, "as_of_date", "NA")
    data_source = safe_get(meta, "data_source", "NA")
    price_basis = safe_get(meta, "price_basis", "NA")
    bb_base = safe_get(meta, "bb_base", "NA")
    script_fp = safe_get(meta, "script_fingerprint", "NA")

    stale_days = dq.get("stale_days_local", None)
    fetch_ok = dq.get("fetch_ok", None)
    insufficient_history = dq.get("insufficient_history", None)

    window = safe_get(meta, "window", "NA")
    k = safe_get(meta, "k", "NA")
    horizon = safe_get(meta, "horizon", "NA")

    price = latest.get("price", None)
    sma = latest.get("sma", None)
    std = latest.get("std", None)
    upper = latest.get("upper", None)
    lower = latest.get("lower", None)
    z = latest.get("z", None)
    pos = latest.get("pos", None)
    dist_lo = latest.get("dist_to_lower_pct", None)
    dist_up = latest.get("dist_to_upper_pct", None)
    state = latest.get("state", "NA")
    state_reason = latest.get("state_reason", "NA")

    definition = fwd.get("definition", "NA")
    all_days = fwd.get("all_days", {})
    conditional = fwd.get("conditional", {})

    # thresholds (prefer meta; fallback if missing)
    thr_cheap = float(safe_get(meta, "z_threshold_cheap", safe_get(meta, "z_threshold", -1.5)))
    thr_hot = float(safe_get(meta, "z_threshold_hot", 1.5))
    thr_hot2 = float(safe_get(meta, "z_threshold_hot2", 2.0))

    cheap = conditional.get("cheap_side", {})
    hot = conditional.get("hot_side", {})
    hot2 = conditional.get("hot_side_extreme", {})

    # Backward compatibility: if only legacy field exists
    if not cheap and "cond_on_z_le_threshold" in fwd:
        cheap = fwd.get("cond_on_z_le_threshold", {})

    chosen_label, chosen_stats = choose_relevant_bucket(z, thr_cheap, thr_hot, thr_hot2, all_days, cheap, hot, hot2)

    dq_notes = dq.get("notes", [])
    if not isinstance(dq_notes, list):
        dq_notes = []

    repro_cmd = safe_get(stats, "repro.command", None)

    md = []
    md.append(f"# TW0050 BB Monitor Report (BB({window},{k}) + forward_mdd({horizon}D))\n")
    md.append(f"- report_generated_at_utc: `{report_generated_at_utc}`")
    md.append(f"- symbol: `{symbol}`")
    md.append(f"- as_of_date: `{as_of_date}`")
    md.append(f"- data_source: `{data_source}` | price_basis: `{price_basis}` | bb_base: `{bb_base}`")
    md.append(f"- script_fingerprint: `{script_fp}`")
    md.append(f"- data_age_days(local): {stale_days} | fetch_ok: `{fetch_ok}` | insufficient_history: `{insufficient_history}`\n")

    # 15s summary
    md.append("## 15秒摘要\n")
    md.append(
        f"- **{symbol}** (as_of={as_of_date} price={fmt_num(price,4)}) → **{state}** "
        f"(reason={state_reason}); z={fmt_num_compact(z,3)}, pos={fmt_num_compact(pos,3)}, "
        f"dist_to_lower={fmt_pct_from_pct_value(dist_lo,2)}, dist_to_upper={fmt_pct_from_pct_value(dist_up,2)}"
    )
    md.append(
        f"- forward_mdd({horizon}D) **{chosen_label}**: {fmt_mdd_stats_inline(chosen_stats)}\n"
    )

    # details table
    md.append("## 指標明細\n")
    md.append("| item | value |")
    md.append("|---|---:|")
    md.append(f"| price | {fmt_num(price,4)} |")
    md.append(f"| sma({window}) | {fmt_num(sma,4)} |")
    md.append(f"| std({window}, ddof=0) | {fmt_num(std,6)} |")
    md.append(f"| upper | {fmt_num(upper,4)} |")
    md.append(f"| lower | {fmt_num(lower,4)} |")
    md.append(f"| z | {fmt_num_compact(z,3)} |")
    md.append(f"| position_in_band | {fmt_num_compact(pos,3)} |")
    md.append(f"| dist_to_lower | {fmt_pct_from_pct_value(dist_lo,2)} |")
    md.append(f"| dist_to_upper | {fmt_pct_from_pct_value(dist_up,2)} |\n")

    # forward_mdd section
    md.append("## forward_mdd 定義與分佈\n")
    md.append(f"- 定義：`{definition}`\n")

    md.append("### 全樣本（不分 z）\n")
    md.append(f"- {fmt_mdd_stats_inline(all_days)}\n")

    # Conditional sections (print if available)
    md.append(f"### 條件樣本（z <= {thr_cheap:g}）\n")
    md.append(f"- {fmt_mdd_stats_inline(cheap) if cheap else 'NA'}\n")

    md.append(f"### 條件樣本（z >= {thr_hot:g}）\n")
    md.append(f"- {fmt_mdd_stats_inline(hot) if hot else 'NA'}\n")

    md.append(f"### 條件樣本（z >= {thr_hot2:g}）\n")
    md.append(f"- {fmt_mdd_stats_inline(hot2) if hot2 else 'NA'}\n")

    # dq notes
    md.append("## 資料品質提醒（務實版）\n")
    if _is_num(stale_days) and int(stale_days) > 3:
        md.append(f"- 資料可能偏舊：local age={int(stale_days)} 天（連假/週末可能合理；但短期位階訊號請避免當作即時依據）。")
    else:
        md.append("- 資料新鮮度在可接受範圍（仍建議搭配交易日/休市狀態理解）。")

    if dq_notes:
        for n in dq_notes:
            md.append(f"- {str(n)}")
    else:
        md.append("- dq.notes: NA")

    md.append("")  # blank line

    # repro
    md.append("## Repro\n")
    if repro_cmd:
        md.append("```bash")
        md.append(repro_cmd)
        md.append("```")
    else:
        md.append("```bash")
        md.append(f"python {Path(__file__)} --cache_dir {cache_dir}")
        md.append("```")

    md_text = "\n".join(md).rstrip() + "\n"
    output_path.write_text(md_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())