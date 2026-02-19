#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build markdown report for 0050 BB(60,2) + forward_mdd(20D).

Inputs (expected in cache_dir):
  - stats_latest.json   (required)
  - data.csv OR prices.csv (optional; for Recent Raw Prices tail)

CLI:
  --cache_dir <dir>   (default: tw0050_bb_cache)
  --out <path>        (default: report.md)
  --tail_days <N>     (default: 15)   # compatible with your workflow
  --tail_n <N>        (optional)      # alias; if provided, overrides tail_days
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
        if x is None:
            return "N/A"
        return f"{float(x):.4f}"
    except Exception:
        return "N/A"


def fmt_pct2(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.2f}%"
    except Exception:
        return "N/A"


def safe_get(d: Dict[str, Any], k: str, default=None):
    try:
        return d.get(k, default)
    except Exception:
        return default


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prices_tail(cache_dir: str, n: int) -> Optional[pd.DataFrame]:
    """
    Prefer data.csv (from compute script). If absent, try prices.csv.
    Normalizes to columns: date, close, adjclose, volume
    """
    candidates = [
        os.path.join(cache_dir, "data.csv"),
        os.path.join(cache_dir, "prices.csv"),
    ]
    path = None
    for p in candidates:
        if os.path.exists(p):
            path = p
            break
    if path is None:
        return None

    df = pd.read_csv(path)
    if df.empty:
        return None

    # normalize date column
    if "date" not in df.columns:
        # some csv may have Date
        if "Date" in df.columns:
            df.rename(columns={"Date": "date"}, inplace=True)
        else:
            return None

    # normalize columns naming
    colmap = {c: c.lower() for c in df.columns}
    df.rename(columns=colmap, inplace=True)

    keep = []
    for c in ["date", "close", "adjclose", "volume"]:
        if c in df.columns:
            keep.append(c)

    if "adjclose" not in keep and "adj close" in df.columns:
        df.rename(columns={"adj close": "adjclose"}, inplace=True)
        keep.append("adjclose")

    if "close" not in keep:
        return None

    if "adjclose" not in keep:
        df["adjclose"] = df["close"]
        keep.append("adjclose")

    if "volume" not in keep:
        df["volume"] = pd.NA
        keep.append("volume")

    df = df[keep].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    # coerce numeric
    for c in ["close", "adjclose", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.tail(n)


def md_table_kv(rows: List[List[str]]) -> str:
    out = ["| item | value |", "|---|---:|"]
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def md_table_prices(df: pd.DataFrame) -> str:
    out = ["| date | close | adjclose | volume |", "|---|---:|---:|---:|"]
    for _, r in df.iterrows():
        d = r["date"]
        d_str = d.strftime("%Y-%m-%d") if not pd.isna(d) else "N/A"
        close = fmt4(r.get("close"))
        adj = fmt4(r.get("adjclose"))
        vol = r.get("volume")
        try:
            vol_s = f"{int(float(vol))}"
        except Exception:
            vol_s = "N/A"
        out.append(f"| {d_str} | {close} | {adj} | {vol_s} |")
    return "\n".join(out)


def build_forward_line(fwd: Dict[str, Any], dq_flags: List[str], fwd_days: int) -> str:
    n = safe_get(fwd, "n", 0)
    p50 = safe_get(fwd, "p50")
    p10 = safe_get(fwd, "p10")
    p05 = safe_get(fwd, "p05")
    mn = safe_get(fwd, "min")

    line = (
        f"- forward_mdd({fwd_days}D) distribution (n={n}): "
        f"p50={fmt4(p50)}; p10={fmt4(p10)}; p05={fmt4(p05)}; min={fmt4(mn)}"
    )

    # If audit trail exists, append
    med = safe_get(fwd, "min_entry_date")
    mfd = safe_get(fwd, "min_future_date")
    mep = safe_get(fwd, "min_entry_price")
    mfp = safe_get(fwd, "min_future_price")
    if med and mfd and mep is not None and mfp is not None:
        line += f" (min_window: {med}->{mfd}; {fmt4(mep)}->{fmt4(mfp)})"

    if "FWD_MDD_OUTLIER_MIN" in set(dq_flags):
        line += " [DQ:FWD_MDD_OUTLIER_MIN]"

    return line


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default="report.md")
    # Your workflow passes this:
    ap.add_argument("--tail_days", type=int, default=15, help="Tail rows for raw prices table.")
    # Alias (optional): overrides tail_days if provided
    ap.add_argument("--tail_n", type=int, default=None, help="Alias of tail_days (higher priority).")
    args = ap.parse_args()

    tail_n = args.tail_n if args.tail_n is not None else args.tail_days
    if tail_n <= 0:
        tail_n = 15

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    if not os.path.exists(stats_path):
        raise SystemExit(f"ERROR: missing {stats_path}")

    s = load_json(stats_path)
    meta = s.get("meta", {}) or {}
    latest = s.get("latest", {}) or {}
    fwd = s.get("forward_mdd", {}) or {}
    dq = s.get("dq", {"flags": [], "notes": []}) or {}
    dq_flags = dq.get("flags") or []
    dq_notes = dq.get("notes") or []

    ticker = safe_get(meta, "ticker", "0050.TW")
    last_date = safe_get(meta, "last_date", "N/A")
    bb_window = safe_get(meta, "bb_window", 60)
    bb_k = safe_get(meta, "bb_k", 2.0)
    fwd_days = int(safe_get(meta, "fwd_days", 20))
    price_calc = safe_get(meta, "price_calc", "adjclose")
    data_source = safe_get(meta, "data_source", "yfinance_yahoo_or_twse_fallback")

    state = safe_get(latest, "state", "N/A")
    bb_z = safe_get(latest, "bb_z")
    bb_pos = safe_get(latest, "bb_pos")
    dist_to_lower = safe_get(latest, "dist_to_lower_pct")
    dist_to_upper = safe_get(latest, "dist_to_upper_pct")

    lines: List[str] = []
    lines.append("# 0050 BB(60,2) + forward_mdd(20D) Report")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{utc_now_iso()}`")
    lines.append(f"- data_source: `{data_source}`")
    lines.append(f"- ticker: `{ticker}`")
    lines.append(f"- last_date: `{last_date}`")
    lines.append(f"- bb_window,k: `{bb_window}`, `{bb_k}`")
    lines.append(f"- forward_window_days: `{fwd_days}`")
    lines.append(f"- price_calc: `{price_calc}`")
    lines.append("")
    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{state}**; bb_z={fmt4(bb_z)}; pos_in_band={fmt4(bb_pos)}; "
        f"dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}"
    )
    lines.append(build_forward_line(fwd, dq_flags, fwd_days))
    lines.append("")

    lines.append("## Latest Snapshot")
    lines.append("")
    lines.append(
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
    lines.append("")

    lines.append("## forward_mdd Distribution")
    lines.append("")
    lines.append(f"- definition: `{safe_get(fwd, 'definition', 'N/A')}`")
    lines.append("")
    lines.append("| quantile | value |")
    lines.append("|---|---:|")
    lines.append(f"| p50 | {fmt4(safe_get(fwd, 'p50'))} |")
    lines.append(f"| p25 | {fmt4(safe_get(fwd, 'p25'))} |")
    lines.append(f"| p10 | {fmt4(safe_get(fwd, 'p10'))} |")
    lines.append(f"| p05 | {fmt4(safe_get(fwd, 'p05'))} |")
    lines.append(f"| min | {fmt4(safe_get(fwd, 'min'))} |")

    med = safe_get(fwd, "min_entry_date")
    mfd = safe_get(fwd, "min_future_date")
    if med and mfd:
        lines.append("")
        lines.append("### forward_mdd Min Audit Trail")
        lines.append("")
        lines.append("| item | value |")
        lines.append("|---|---:|")
        lines.append(f"| min_entry_date | {med} |")
        lines.append(f"| min_entry_price | {fmt4(safe_get(fwd, 'min_entry_price'))} |")
        lines.append(f"| min_future_date | {mfd} |")
        lines.append(f"| min_future_price | {fmt4(safe_get(fwd, 'min_future_price'))} |")

    lines.append("")
    lines.append(f"## Recent Raw Prices (tail {tail_n})")
    lines.append("")
    tail_df = load_prices_tail(args.cache_dir, n=tail_n)
    if tail_df is None:
        lines.append("_No data.csv / prices.csv tail available._")
    else:
        lines.append(md_table_prices(tail_df))
    lines.append("")

    lines.append("## Data Quality Flags")
    lines.append("")
    if not dq_flags:
        lines.append("- (none)")
    else:
        lines.append("- flags:")
        for fl in dq_flags:
            lines.append(f"  - `{fl}`")
        if dq_notes:
            lines.append("- notes:")
            for nt in dq_notes:
                lines.append(f"  - {nt}")
    lines.append("")
    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())