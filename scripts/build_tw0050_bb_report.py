#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build a Markdown report from tw0050_bb_cache/stats_latest.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

DEFAULT_TZ = "Asia/Taipei"


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def local_today(tz_name: str) -> date:
    if ZoneInfo is None:
        return datetime.now().date()
    return datetime.now(ZoneInfo(tz_name)).date()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt_pct(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}%"


def fmt_f(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def fmt_ret(x: Optional[float], nd: int = 2) -> str:
    # x is decimal return (e.g., -0.123)
    if x is None:
        return "NA"
    return f"{(x * 100.0):.{nd}f}%"


def age_note(stale_days: Optional[int]) -> str:
    if stale_days is None:
        return "data_age_days: NA"
    return f"data_age_days(local): {stale_days}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build TW0050 BB(60,2)+forward_mdd report")
    ap.add_argument("--cache_dir", default="tw0050_bb_cache", help="Cache dir containing stats_latest.json")
    ap.add_argument("--output", default="report_tw0050_bb.md", help="Output markdown file")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"Local timezone label (default: {DEFAULT_TZ})")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    stats_path = cache_dir / "stats_latest.json"
    if not stats_path.exists():
        raise FileNotFoundError(f"Missing stats_latest.json at: {stats_path}")

    stats = read_json(stats_path)
    meta: Dict[str, Any] = stats.get("meta", {})
    dq: Dict[str, Any] = stats.get("dq", {})
    latest: Dict[str, Any] = stats.get("latest", {})
    fwd: Dict[str, Any] = stats.get("forward_mdd", {})

    run_ts_utc = utc_now_iso()

    # basic fields
    symbol = meta.get("symbol", "NA")
    as_of_date = meta.get("as_of_date", "NA")
    window = meta.get("window", "NA")
    k = meta.get("k", "NA")
    horizon = meta.get("horizon", "NA")
    z_th = meta.get("z_threshold", "NA")
    data_source = meta.get("data_source", "NA")
    price_basis = meta.get("price_basis", "NA")
    bb_base = meta.get("bb_base", "NA")
    script_fp = meta.get("script_fingerprint", "NA")

    stale_days = dq.get("stale_days_local", None)
    fetch_ok = dq.get("fetch_ok", False)
    insufficient = dq.get("insufficient_history", False)

    # latest values
    px = latest.get("price", None)
    z = latest.get("z", None)
    pos = latest.get("pos", None)
    dlow = latest.get("dist_to_lower_pct", None)
    dup = latest.get("dist_to_upper_pct", None)
    state = latest.get("state", "NA")
    reason = latest.get("state_reason", "NA")

    # forward mdd stats
    all_days = fwd.get("all_days", {})
    cond = fwd.get("cond_on_z_le_threshold", {})

    lines = []
    lines.append(f"# TW0050 BB Monitor Report (BB({window},{k}) + forward_mdd({horizon}D))")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{run_ts_utc}`")
    lines.append(f"- symbol: `{symbol}`")
    lines.append(f"- as_of_date: `{as_of_date}`")
    lines.append(f"- data_source: `{data_source}` | price_basis: `{price_basis}` | bb_base: `{bb_base}`")
    lines.append(f"- script_fingerprint: `{script_fp}`")
    lines.append(f"- {age_note(stale_days)} | fetch_ok: `{fetch_ok}` | insufficient_history: `{insufficient}`")
    lines.append("")

    lines.append("## 15秒摘要")
    lines.append("")
    lines.append(
        f"- **{symbol}** (as_of={as_of_date} price={fmt_f(px, 4)}) → **{state}** (reason={reason}); "
        f"z={fmt_f(z, 3)}, pos={fmt_f(pos, 3)}, dist_to_lower={fmt_pct(dlow, 2)}, dist_to_upper={fmt_pct(dup, 2)}"
    )
    lines.append(
        f"- forward_mdd({horizon}D) cond(z<={z_th}): n={cond.get('n','NA')}, "
        f"p50={fmt_ret(cond.get('p50', None), 2)}, p10={fmt_ret(cond.get('p10', None), 2)}, "
        f"min={fmt_ret(cond.get('min', None), 2)} (conf={cond.get('conf','NA')})"
    )
    lines.append("")

    lines.append("## 指標明細")
    lines.append("")
    lines.append("| item | value |")
    lines.append("|---|---:|")
    lines.append(f"| price | {fmt_f(px, 4)} |")
    lines.append(f"| sma({window}) | {fmt_f(latest.get('sma', None), 4)} |")
    lines.append(f"| std({window}, ddof=0) | {fmt_f(latest.get('std', None), 6)} |")
    lines.append(f"| upper | {fmt_f(latest.get('upper', None), 4)} |")
    lines.append(f"| lower | {fmt_f(latest.get('lower', None), 4)} |")
    lines.append(f"| z | {fmt_f(z, 3)} |")
    lines.append(f"| position_in_band | {fmt_f(pos, 3)} |")
    lines.append(f"| dist_to_lower | {fmt_pct(dlow, 2)} |")
    lines.append(f"| dist_to_upper | {fmt_pct(dup, 2)} |")
    lines.append("")

    lines.append("## forward_mdd 定義與分佈")
    lines.append("")
    lines.append(f"- 定義：`{fwd.get('definition','NA')}`")
    lines.append("")
    lines.append("### 全樣本（不分 z）")
    lines.append("")
    lines.append(
        f"- n={all_days.get('n','NA')}, p50={fmt_ret(all_days.get('p50', None), 2)}, "
        f"p10={fmt_ret(all_days.get('p10', None), 2)}, min={fmt_ret(all_days.get('min', None), 2)} "
        f"(conf={all_days.get('conf','NA')})"
    )
    lines.append("")
    lines.append(f"### 條件樣本（z <= {z_th}）")
    lines.append("")
    lines.append(
        f"- n={cond.get('n','NA')}, p50={fmt_ret(cond.get('p50', None), 2)}, "
        f"p10={fmt_ret(cond.get('p10', None), 2)}, min={fmt_ret(cond.get('min', None), 2)} "
        f"(conf={cond.get('conf','NA')})"
    )
    lines.append("")

    lines.append("## 資料品質提醒（務實版）")
    lines.append("")
    notes = dq.get("notes", [])
    if not fetch_ok:
        lines.append("- 本次抓價失敗（fetch_ok=false），請先檢查資料源/網路/代號。")
    if stale_days is not None and stale_days > 2:
        lines.append(f"- 資料可能偏舊：local age={stale_days} 天（若遇到連假/週末，屬合理現象）。")
    if insufficient:
        lines.append("- 歷史資料不足以穩定估計（insufficient_history=true），forward_mdd 統計可信度會被動下修。")
    for n in notes:
        lines.append(f"- {n}")
    if not notes and fetch_ok and not insufficient and (stale_days is None or stale_days <= 2):
        lines.append("- 無特殊 dq 訊號。")
    lines.append("")

    lines.append("## Repro")
    lines.append("")
    repro = stats.get("repro", {}).get("command", None)
    if repro:
        lines.append("```bash")
        lines.append(repro)
        lines.append("```")
    else:
        lines.append("- NA")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())