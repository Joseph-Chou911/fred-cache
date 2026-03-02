#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_market_cache_charts.py

Generate chart-ready CSV + a few standard charts from dashboard/DASHBOARD.md.

Design goals:
- Avoid p60/p252 ambiguity by renaming to rank_* columns.
- Robust markdown table extraction (search for a table that contains 'Signal' and 'Series').
- Fail loudly with actionable diagnostics if the table format changes.
- No imports from your repo modules (only stdlib + pandas + matplotlib).
- Charts use ENGLISH labels/titles to avoid CI CJK font/tofu issues.

Outputs (to --out):
- chart_ready.csv
- 01_rank252_overview.png
- 02_rank60_jump_abs.png
- 03_z60_vs_rank252_scatter.png
- 04_ret1_abs_pct.png
"""

import argparse
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import matplotlib
matplotlib.use("Agg", force=True)  # deterministic in CI
import matplotlib.pyplot as plt


# Columns that are expected numeric if present
NUM_COLS = [
    "age_h", "value", "z60", "p60", "p252", "z252",
    "z_poschg60", "p_poschg60", "ret1_pct1d_absPrev",
    "StreakHist", "StreakWA",
]

# Rename to reduce ambiguity for humans/other AIs
RENAME = {
    "p60": "rank_60_obs_pct",            # percentile rank over last ~60 obs
    "p252": "rank_252_obs_pct",          # percentile rank over last ~252 obs
    "p_poschg60": "rank_60_delta_pp",    # percentile-point change vs yesterday
    "z_poschg60": "z_60_delta",
    "ret1_pct1d_absPrev": "ret1_abs_pct",
    "Series": "series",
    "Signal": "signal",
    "Tag": "tag",
    "DQ": "dq",
    "data_date": "data_date",
    "as_of_ts": "as_of_ts",
}

# English labels (avoid tofu in CI)
EN = {
    "rank_252_obs_pct": "Rank over last 252 obs (%)",
    "rank_60_delta_pp": "Rank change over last 60 (|Δ|, pp)",
    "z60": "z60 (std over last 60)",
    "ret1_abs_pct": "Abs 1-day move (%)",
}


def _peek_context(lines: List[str], idx: int, radius: int = 10) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    out = []
    for i in range(lo, hi):
        prefix = ">> " if i == idx else "   "
        out.append(f"{prefix}{i+1:04d}: {lines[i]}")
    return "\n".join(out)


def extract_markdown_table(report_text: str) -> Tuple[pd.DataFrame, int]:
    """
    Find the markdown table that contains the dashboard rows.
    We search for a header line that:
    - starts with '|'
    - contains 'Signal' and 'Series' columns (your format)
    """
    lines = report_text.splitlines()

    header_idx: Optional[int] = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        if "| Signal " in s and "| Series " in s:
            header_idx = i
            break

    if header_idx is None:
        # fallback: sometimes header might be "| Signal | ... | Series | ..."
        for i, line in enumerate(lines):
            s = line.strip()
            if not (s.startswith("|") and s.endswith("|")):
                continue
            if "Signal" in s and "Series" in s:
                header_idx = i
                break

    if header_idx is None:
        raise ValueError(
            "Cannot find dashboard markdown table (must contain 'Signal' and 'Series').\n"
            "Check dashboard/DASHBOARD.md table header names."
        )

    if header_idx + 1 >= len(lines):
        raise ValueError("Header found but no separator line after it.")

    header_line = lines[header_idx].strip()
    sep_line = lines[header_idx + 1].strip()

    if "---" not in sep_line:
        ctx = _peek_context(lines, header_idx)
        raise ValueError(
            "Separator line (|---|---|) not found right after header.\n"
            f"Context:\n{ctx}"
        )

    cols = [c.strip() for c in header_line.split("|")[1:-1]]

    rows = []
    j = header_idx + 2
    while j < len(lines):
        s = lines[j].strip()
        if not (s.startswith("|") and s.endswith("|")):
            break
        row = [c.strip() for c in s.split("|")[1:-1]]
        if len(row) == len(cols):
            rows.append(row)
        j += 1

    if not rows:
        ctx = _peek_context(lines, header_idx)
        raise ValueError(
            "Header found but no data rows parsed.\n"
            f"Context:\n{ctx}"
        )

    df = pd.DataFrame(rows, columns=cols)
    return df, header_idx


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace({"NA": pd.NA, "N/A": pd.NA, "": pd.NA})
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def ensure_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)


def save_chart_rank252(df: pd.DataFrame, outdir: Path,
                       p_watch_lo: float = 5.0, p_watch_hi: float = 95.0, p_alert_lo: float = 2.0) -> None:
    if "rank_252_obs_pct" not in df.columns:
        return

    d = df.copy().dropna(subset=["rank_252_obs_pct", "series"])
    if d.empty:
        return

    d = d.sort_values("rank_252_obs_pct", ascending=True)

    plt.figure(figsize=(12, 6))
    plt.barh(d["series"], d["rank_252_obs_pct"])
    plt.axvline(p_watch_lo, linestyle="--")
    plt.axvline(p_watch_hi, linestyle="--")
    plt.axvline(p_alert_lo, linestyle=":")
    plt.xlabel(EN["rank_252_obs_pct"])
    plt.title("Long-window rank overview (252 obs)")
    plt.tight_layout()
    plt.savefig(outdir / "01_rank252_overview.png", dpi=200)
    plt.close()


def save_chart_rank60_jump_abs(df: pd.DataFrame, outdir: Path, jump_p_threshold: float = 15.0) -> None:
    if "rank_60_delta_pp" not in df.columns:
        return

    d = df.copy().dropna(subset=["rank_60_delta_pp", "series"])
    if d.empty:
        return

    d["abs_rank60_jump_pp"] = d["rank_60_delta_pp"].abs()
    d = d.sort_values("abs_rank60_jump_pp", ascending=True)

    plt.figure(figsize=(12, 6))
    plt.barh(d["series"], d["abs_rank60_jump_pp"])
    plt.axvline(jump_p_threshold, linestyle="--")
    plt.xlabel(EN["rank_60_delta_pp"])
    plt.title("Short-window jump strength (|Δ rank60|)")
    plt.tight_layout()
    plt.savefig(outdir / "02_rank60_jump_abs.png", dpi=200)
    plt.close()


def save_chart_scatter(df: pd.DataFrame, outdir: Path,
                       extreme_z_watch: float = 2.0, extreme_z_alert: float = 2.5,
                       p_watch_lo: float = 5.0, p_watch_hi: float = 95.0) -> None:
    need = {"z60", "rank_252_obs_pct", "series"}
    if not need.issubset(set(df.columns)):
        return

    d = df.copy().dropna(subset=["z60", "rank_252_obs_pct", "series"])
    if d.empty:
        return

    plt.figure(figsize=(10, 6))
    plt.scatter(d["z60"], d["rank_252_obs_pct"])

    for _, r in d.iterrows():
        plt.text(r["z60"], r["rank_252_obs_pct"], str(r["series"]), fontsize=9)

    plt.axhline(p_watch_lo, linestyle="--")
    plt.axhline(p_watch_hi, linestyle="--")
    plt.axvline(extreme_z_watch, linestyle="--")
    plt.axvline(-extreme_z_watch, linestyle="--")
    plt.axvline(extreme_z_alert, linestyle=":")
    plt.axvline(-extreme_z_alert, linestyle=":")

    plt.xlabel(EN["z60"])
    plt.ylabel(EN["rank_252_obs_pct"])
    plt.title("z60 vs rank252 (quick locate extremes)")
    plt.tight_layout()
    plt.savefig(outdir / "03_z60_vs_rank252_scatter.png", dpi=200)
    plt.close()


def save_chart_ret1_abs(df: pd.DataFrame, outdir: Path, jump_ret_threshold: float = 2.0) -> None:
    if "ret1_abs_pct" not in df.columns:
        return

    d = df.copy().dropna(subset=["ret1_abs_pct", "series"])
    if d.empty:
        return

    d = d.sort_values("ret1_abs_pct", ascending=True)

    plt.figure(figsize=(12, 6))
    plt.barh(d["series"], d["ret1_abs_pct"])
    plt.axvline(jump_ret_threshold, linestyle="--")
    plt.xlabel(EN["ret1_abs_pct"])
    plt.title("Abs 1-day move overview (|ret1|%)")
    plt.tight_layout()
    plt.savefig(outdir / "04_ret1_abs_pct.png", dpi=200)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="Path to dashboard markdown, e.g. dashboard/DASHBOARD.md")
    ap.add_argument("--out", required=True, help="Output directory, e.g. dashboard/charts/market_cache")

    # thresholds aligned with your ruleset defaults (signals_v8)
    ap.add_argument("--jump-p", type=float, default=15.0)
    ap.add_argument("--jump-ret", type=float, default=2.0)
    ap.add_argument("--extreme-z-watch", type=float, default=2.0)
    ap.add_argument("--extreme-z-alert", type=float, default=2.5)
    ap.add_argument("--p-watch-lo", type=float, default=5.0)
    ap.add_argument("--p-watch-hi", type=float, default=95.0)
    ap.add_argument("--p-alert-lo", type=float, default=2.0)

    args = ap.parse_args()

    report_path = Path(args.report)
    outdir = Path(args.out)
    ensure_outdir(outdir)

    if not report_path.exists():
        raise FileNotFoundError(f"report not found: {report_path}")

    text = report_path.read_text(encoding="utf-8")
    df_raw, header_idx = extract_markdown_table(text)

    # numeric cleanup
    df_raw = coerce_numeric(df_raw)

    # rename for ambiguity-proof sharing
    df = df_raw.rename(columns=RENAME)

    # sanity: must contain series
    if "series" not in df.columns:
        ctx = _peek_context(text.splitlines(), header_idx)
        raise ValueError(
            "Table parsed but missing 'Series' column (renamed or removed?).\n"
            f"Context:\n{ctx}"
        )

    # Export a chart-ready CSV with safe column names
    csv_path = outdir / "chart_ready.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Standard charts
    save_chart_rank252(df, outdir, p_watch_lo=args.p_watch_lo, p_watch_hi=args.p_watch_hi, p_alert_lo=args.p_alert_lo)
    save_chart_rank60_jump_abs(df, outdir, jump_p_threshold=args.jump_p)
    save_chart_scatter(df, outdir,
                       extreme_z_watch=args.extreme_z_watch, extreme_z_alert=args.extreme_z_alert,
                       p_watch_lo=args.p_watch_lo, p_watch_hi=args.p_watch_hi)
    save_chart_ret1_abs(df, outdir, jump_ret_threshold=args.jump_ret)

    print(f"OK: wrote {csv_path} and charts to {outdir}")


if __name__ == "__main__":
    main()