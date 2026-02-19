#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build a human-readable Markdown report from stats_latest.json + data.csv.
Standalone: does not depend on your other dashboard modules.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fmt(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    try:
        if isinstance(x, (int, np.integer)):
            return str(int(x))
        xf = float(x)
        if np.isnan(xf):
            return "NA"
        return f"{xf:.{nd}f}"
    except Exception:
        return "NA"


def _fmt_pct(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    try:
        xf = float(x)
        if np.isnan(xf):
            return "NA"
        return f"{xf:.{nd}f}%"
    except Exception:
        return "NA"


def main() -> None:
    p = argparse.ArgumentParser(description="Build 0050 BB(60,2) + forward_mdd(20D) Markdown report.")
    p.add_argument("--cache_dir", default="tw0050_bb_cache", help="Cache directory.")
    p.add_argument("--out", default=None, help="Output markdown path. Default: <cache_dir>/report.md")
    p.add_argument("--tail_days", type=int, default=15, help="Show last N rows in a table. Default: 15")
    args = p.parse_args()

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    data_path = os.path.join(args.cache_dir, "data.csv")
    out_path = args.out or os.path.join(args.cache_dir, "report.md")

    if not os.path.exists(stats_path):
        raise SystemExit(f"ERROR: missing {stats_path}")
    if not os.path.exists(data_path):
        raise SystemExit(f"ERROR: missing {data_path}")

    with open(stats_path, "r", encoding="utf-8") as f:
        stats: Dict[str, Any] = json.load(f)

    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")

    meta = stats.get("meta", {})
    dq = stats.get("dq", {})
    latest = stats.get("latest", {})
    fwd = stats.get("forward_mdd", {})

    # Build tail table (use columns if present; else minimal)
    cols = []
    for c in ["close", "adjclose", "volume"]:
        if c in df.columns:
            cols.append(c)
    tail = df[cols].tail(args.tail_days).copy()

    # Compose markdown
    lines = []
    lines.append("# 0050 BB(60,2) + forward_mdd(20D) Report")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{utc_now_iso()}`")
    lines.append(f"- data_source: `{meta.get('data_source','NA')}`")
    lines.append(f"- ticker: `{meta.get('ticker','NA')}`")
    lines.append(f"- last_date: `{meta.get('last_date','NA')}`")
    lines.append(f"- bb_window,k: `{meta.get('bb_window','NA')}`, `{meta.get('bb_k','NA')}`")
    lines.append(f"- forward_window_days: `{meta.get('fwd_days','NA')}`")
    lines.append(f"- price_calc: `{meta.get('price_calc','NA')}`")
    lines.append("")

    # 15-sec summary style
    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{latest.get('state','NA')}**; "
        f"bb_z={_fmt(latest.get('bb_z'),3)}; "
        f"pos_in_band={_fmt(latest.get('bb_pos'),3)}; "
        f"dist_to_lower={_fmt_pct(latest.get('dist_to_lower_pct'),2)}; "
        f"dist_to_upper={_fmt_pct(latest.get('dist_to_upper_pct'),2)}"
    )
    lines.append(
        f"- forward_mdd({meta.get('fwd_days','NA')}D) distribution (n={fwd.get('n','NA')}): "
        f"p50={_fmt(fwd.get('p50'),4)}; p10={_fmt(fwd.get('p10'),4)}; p05={_fmt(fwd.get('p05'),4)}; min={_fmt(fwd.get('min'),4)}"
    )
    lines.append("")

    lines.append("## Latest Snapshot")
    lines.append("")
    lines.append("| item | value |")
    lines.append("|---|---:|")
    lines.append(f"| close | {_fmt(latest.get('close'),4)} |")
    lines.append(f"| adjclose | {_fmt(latest.get('adjclose'),4)} |")
    lines.append(f"| price_used | {_fmt(latest.get('price_used'),4)} |")
    lines.append(f"| bb_ma | {_fmt(latest.get('bb_ma'),4)} |")
    lines.append(f"| bb_sd | {_fmt(latest.get('bb_sd'),4)} |")
    lines.append(f"| bb_upper | {_fmt(latest.get('bb_upper'),4)} |")
    lines.append(f"| bb_lower | {_fmt(latest.get('bb_lower'),4)} |")
    lines.append(f"| bb_z | {_fmt(latest.get('bb_z'),4)} |")
    lines.append(f"| pos_in_band | {_fmt(latest.get('bb_pos'),4)} |")
    lines.append(f"| dist_to_lower | {_fmt_pct(latest.get('dist_to_lower_pct'),2)} |")
    lines.append(f"| dist_to_upper | {_fmt_pct(latest.get('dist_to_upper_pct'),2)} |")
    lines.append("")

    lines.append("## forward_mdd Distribution")
    lines.append("")
    lines.append(f"- definition: `{fwd.get('definition','NA')}`")
    lines.append("")
    lines.append("| quantile | value |")
    lines.append("|---|---:|")
    lines.append(f"| p50 | {_fmt(fwd.get('p50'),4)} |")
    lines.append(f"| p25 | {_fmt(fwd.get('p25'),4)} |")
    lines.append(f"| p10 | {_fmt(fwd.get('p10'),4)} |")
    lines.append(f"| p05 | {_fmt(fwd.get('p05'),4)} |")
    lines.append(f"| min | {_fmt(fwd.get('min'),4)} |")
    lines.append("")

    lines.append("## Recent Raw Prices (tail)")
    lines.append("")
    if not tail.empty:
        lines.append("| date | " + " | ".join(tail.columns) + " |")
        lines.append("|---|" + "|".join(["---:"] * len(tail.columns)) + "|")
        for idx, r in tail.iterrows():
            items = []
            for c in tail.columns:
                v = r[c]
                if c == "volume":
                    items.append(str(int(v)) if pd.notna(v) else "NA")
                else:
                    items.append(_fmt(v, 4))
            lines.append(f"| {idx.date().isoformat()} | " + " | ".join(items) + " |")
    else:
        lines.append("- NA (tail table empty)")
    lines.append("")

    lines.append("## Data Quality Flags")
    lines.append("")
    flags = dq.get("flags", []) or []
    notes = dq.get("notes", []) or []
    if not flags:
        lines.append("- (none)")
    else:
        for i, fl in enumerate(flags):
            note = notes[i] if i < len(notes) else ""
            lines.append(f"- {fl}: {note}")

    lines.append("")
    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是**描述性統計**，不是方向預測。")
    lines.append("- 資料源為 Yahoo Finance，可能出現延遲、回補或欄位變動；已在 dq flags 留痕。")
    lines.append("- 預設用 Adj Close 計算（較適合長期含配息/分割的比較）；若你要純價格技術面，可改用 `--price_col close`。")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()