# scripts/build_tw0050_bb_report.py
# -*- coding: utf-8 -*-
"""
Build markdown report from cache_dir/stats_latest.json and cache_dir/prices.csv (tail).

Example:
  python scripts/build_tw0050_bb_report.py --cache_dir tw0050_bb_cache --out report.md
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fmt4(x: Any) -> str:
    try:
        return f"{float(x):.4f}"
    except Exception:
        return "N/A"


def fmt_pct2(x: Any) -> str:
    try:
        return f"{float(x):.2f}%"
    except Exception:
        return "N/A"


def safe_get(d: Dict[str, Any], k: str, default=None):
    return d.get(k, default)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prices_tail(cache_dir: str, n: int = 15) -> Optional[pd.DataFrame]:
    p = os.path.join(cache_dir, "prices.csv")
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    if df.empty:
        return None
    if "date" not in df.columns:
        return None
    # Normalize columns if present
    keep = [c for c in ["date", "close", "adjclose", "volume"] if c in df.columns]
    df = df[keep].copy()
    # Coerce numeric
    for c in ["close", "adjclose", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("date")
    return df.tail(n)


def md_table_kv(rows: List[List[str]]) -> str:
    out = []
    out.append("| item | value |")
    out.append("|---|---:|")
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def md_table_prices(df: pd.DataFrame) -> str:
    cols = df.columns.tolist()
    # Force ordering if possible
    order = ["date", "close", "adjclose", "volume"]
    cols = [c for c in order if c in cols]
    out = []
    out.append("| date | close | adjclose | volume |")
    out.append("|---|---:|---:|---:|")
    for _, r in df.iterrows():
        date = str(r.get("date", ""))
        close = fmt4(r.get("close"))
        adj = fmt4(r.get("adjclose"))
        vol = r.get("volume")
        try:
            vol_s = f"{int(float(vol))}"
        except Exception:
            vol_s = "N/A"
        out.append(f"| {date} | {close} | {adj} | {vol_s} |")
    return "\n".join(out)


def build_forward_line(fwd: Dict[str, Any], dq_flags: List[str]) -> str:
    n = safe_get(fwd, "n", 0)
    p50 = safe_get(fwd, "p50", None)
    p10 = safe_get(fwd, "p10", None)
    p05 = safe_get(fwd, "p05", None)
    mn = safe_get(fwd, "min", None)

    line = (
        f"- forward_mdd(20D) distribution (n={n}): "
        f"p50={fmt4(p50)}; p10={fmt4(p10)}; p05={fmt4(p05)}; min={fmt4(mn)}"
    )

    # If min-entry details exist, append audit snippet
    med = safe_get(fwd, "min_entry_date", None)
    mfd = safe_get(fwd, "min_future_date", None)
    mep = safe_get(fwd, "min_entry_price", None)
    mfp = safe_get(fwd, "min_future_price", None)
    if med and mfd and mep is not None and mfp is not None:
        line += f" (min_window: {med}->{mfd}; {fmt4(mep)}->{fmt4(mfp)})"

    if "FWD_MDD_OUTLIER_MIN" in set(dq_flags):
        line += " [DQ:FWD_MDD_OUTLIER_MIN]"

    return line


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default="report.md")
    args = ap.parse_args()

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    if not os.path.exists(stats_path):
        raise SystemExit(f"ERROR: missing {stats_path}")

    s = load_json(stats_path)

    meta = s.get("meta", {})
    latest = s.get("latest", {})
    fwd = s.get("forward_mdd", {})
    dq = s.get("dq", {"flags": [], "notes": []})
    dq_flags = dq.get("flags") or []
    dq_notes = dq.get("notes") or []

    ticker = safe_get(meta, "ticker", "0050.TW")
    last_date = safe_get(meta, "last_date", "N/A")
    bb_window = safe_get(meta, "bb_window", 60)
    bb_k = safe_get(meta, "bb_k", 2.0)
    fwd_days = safe_get(meta, "fwd_days", 20)
    price_calc = safe_get(meta, "price_calc", "adjclose")
    data_source = safe_get(meta, "data_source", "yfinance_yahoo_or_twse_fallback")

    # Snapshot fields
    state = safe_get(latest, "state", "N/A")
    bb_z = safe_get(latest, "bb_z", None)
    bb_pos = safe_get(latest, "bb_pos", None)
    dist_to_lower = safe_get(latest, "dist_to_lower_pct", None)
    dist_to_upper = safe_get(latest, "dist_to_upper_pct", None)

    report_lines: List[str] = []

    report_lines.append("# 0050 BB(60,2) + forward_mdd(20D) Report")
    report_lines.append("")
    report_lines.append(f"- report_generated_at_utc: `{utc_now_iso()}`")
    report_lines.append(f"- data_source: `{data_source}`")
    report_lines.append(f"- ticker: `{ticker}`")
    report_lines.append(f"- last_date: `{last_date}`")
    report_lines.append(f"- bb_window,k: `{bb_window}`, `{bb_k}`")
    report_lines.append(f"- forward_window_days: `{fwd_days}`")
    report_lines.append(f"- price_calc: `{price_calc}`")
    report_lines.append("")
    report_lines.append("## 快速摘要（非預測，僅狀態）")
    report_lines.append(
        f"- state: **{state}**; bb_z={fmt4(bb_z)}; pos_in_band={fmt4(bb_pos)}; "
        f"dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}"
    )
    report_lines.append(build_forward_line(fwd, dq_flags))
    report_lines.append("")

    report_lines.append("## Latest Snapshot")
    report_lines.append("")
    report_lines.append(
        md_table_kv(
            [
                ["close", fmt4(safe_get(latest, "close"))],
                ["adjclose", fmt4(safe_get(latest, "adjclose"))],
                ["price_used", fmt4(safe_get(latest, "price_used"))],
                ["bb_ma", fmt4(safe_get(latest, "bb_ma"))],
                ["bb_sd", fmt4(safe_get(latest, "bb_sd"))],
                ["bb_upper", fmt4(safe_get(latest, "bb_upper"))],
                ["bb_lower", fmt4(safe_get(latest, "bb_lower"))],
                ["bb_z", fmt4(safe_get(latest, "bb_z"))],
                ["pos_in_band", fmt4(safe_get(latest, "bb_pos"))],
                ["dist_to_lower", fmt_pct2(safe_get(latest, "dist_to_lower_pct"))],
                ["dist_to_upper", fmt_pct2(safe_get(latest, "dist_to_upper_pct"))],
            ]
        )
    )
    report_lines.append("")

    report_lines.append("## forward_mdd Distribution")
    report_lines.append("")
    report_lines.append(f"- definition: `{safe_get(fwd, 'definition', 'N/A')}`")
    report_lines.append("")
    report_lines.append("| quantile | value |")
    report_lines.append("|---|---:|")
    report_lines.append(f"| p50 | {fmt4(safe_get(fwd, 'p50'))} |")
    report_lines.append(f"| p25 | {fmt4(safe_get(fwd, 'p25'))} |")
    report_lines.append(f"| p10 | {fmt4(safe_get(fwd, 'p10'))} |")
    report_lines.append(f"| p05 | {fmt4(safe_get(fwd, 'p05'))} |")
    report_lines.append(f"| min | {fmt4(safe_get(fwd, 'min'))} |")

    # If min details exist, show an extra audit section
    med = safe_get(fwd, "min_entry_date", None)
    mfd = safe_get(fwd, "min_future_date", None)
    if med and mfd:
        report_lines.append("")
        report_lines.append("### forward_mdd Min Audit Trail")
        report_lines.append("")
        report_lines.append("| item | value |")
        report_lines.append("|---|---:|")
        report_lines.append(f"| min_entry_date | {med} |")
        report_lines.append(f"| min_entry_price | {fmt4(safe_get(fwd, 'min_entry_price'))} |")
        report_lines.append(f"| min_future_date | {mfd} |")
        report_lines.append(f"| min_future_price | {fmt4(safe_get(fwd, 'min_future_price'))} |")

    report_lines.append("")

    tail_df = load_prices_tail(args.cache_dir, n=15)
    report_lines.append("## Recent Raw Prices (tail)")
    report_lines.append("")
    if tail_df is None:
        report_lines.append("_No prices.csv tail available._")
    else:
        report_lines.append(md_table_prices(tail_df))
    report_lines.append("")

    report_lines.append("## Data Quality Flags")
    report_lines.append("")
    if not dq_flags:
        report_lines.append("- (none)")
    else:
        report_lines.append("- flags:")
        for fl in dq_flags:
            report_lines.append(f"  - `{fl}`")
        if dq_notes:
            report_lines.append("- notes:")
            for nt in dq_notes:
                report_lines.append(f"  - {nt}")
    report_lines.append("")

    report_lines.append("## Caveats")
    report_lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    report_lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。")
    report_lines.append("")

    out_text = "\n".join(report_lines)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out_text)

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())