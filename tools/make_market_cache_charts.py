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

Outputs (to --out):
- chart_ready.csv
- 01_rank252_overview.png
- 02_rank60_jump_abs.png
- 03_z60_vs_rank252_scatter.png
- 04_ret1_abs_pct.png (optional but usually useful)
"""

import argparse
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import matplotlib.pyplot as plt


# Columns that are expected numeric if present
NUM_COLS = [
    "age_h", "value", "z60", "p60", "p252", "z252",
    "z_poschg60", "p_poschg60", "ret1_pct1d_absPrev",
    "StreakHist", "StreakWA",
]

# Rename to reduce ambiguity for humans/other AIs
RENAME = {
    "p60": "rank_60_obs_pct",            # 近60筆位階(%)
    "p252": "rank_252_obs_pct",          # 近252筆位階(%)
    "p_poschg60": "rank_60_delta_pp",    # 近60位階變化(百分位點)
    "z_poschg60": "z_60_delta",
    "ret1_pct1d_absPrev": "ret1_abs_pct",
    "Series": "series",
    "Signal": "signal",
    "Tag": "tag",
    "DQ": "dq",
    "data_date": "data_date",
    "as_of_ts": "as_of_ts",
}

# Optional Chinese labels for chart axes/titles (keep data columns English for scripts)
ZH = {
    "rank_252_obs_pct": "近252筆位階（%）",
    "rank_60_delta_pp": "近60位階變化（百分位點）",
    "z60": "z60（近60標準化偏離）",
    "ret1_abs_pct": "單日變化幅度（%）",
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
        # Must contain both Signal and Series to avoid catching other tables
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
            "找不到 dashboard markdown table（需要包含 'Signal' 與 'Series' 欄位）。\n"
            "請檢查 dashboard/DASHBOARD.md 是否仍包含那張表，或表頭是否已改名。"
        )

    # The next line should be separator like |---|---|
    if header_idx + 1 >= len(lines):
        raise ValueError("表頭行存在但後面沒有分隔線。")

    header_line = lines[header_idx].strip()
    sep_line = lines[header_idx + 1].strip()

    if "---" not in sep_line:
        ctx = _peek_context(lines, header_idx)
        raise ValueError(
            "表頭後未找到 markdown 分隔線（|---|---|）。\n"
            f"附近內容：\n{ctx}"
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
        else:
            # ignore malformed row but fail if it's clearly within the main table
            pass
        j += 1

    if not rows:
        ctx = _peek_context(lines, header_idx)
        raise ValueError(
            "找到表頭但沒有任何資料列。\n"
            f"附近內容：\n{ctx}"
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

    d = df.copy()
    d = d.dropna(subset=["rank_252_obs_pct", "series"])
    if d.empty:
        return

    d = d.sort_values("rank_252_obs_pct", ascending=True)

    plt.figure(figsize=(12, 6))
    plt.barh(d["series"], d["rank_252_obs_pct"])
    plt.axvline(p_watch_lo, linestyle="--")
    plt.axvline(p_watch_hi, linestyle="--")
    plt.axvline(p_alert_lo, linestyle=":")
    plt.xlabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"))
    plt.title("長窗口位階總覽（近252筆）")
    plt.tight_layout()
    plt.savefig(outdir / "01_rank252_overview.png", dpi=200)
    plt.close()


def save_chart_rank60_jump_abs(df: pd.DataFrame, outdir: Path, jump_p_threshold: float = 15.0) -> None:
    if "rank_60_delta_pp" not in df.columns:
        return

    d = df.copy()
    d = d.dropna(subset=["rank_60_delta_pp", "series"])
    if d.empty:
        return

    d["abs_rank60_jump_pp"] = d["rank_60_delta_pp"].abs()
    d = d.sort_values("abs_rank60_jump_pp", ascending=True)

    plt.figure(figsize=(12, 6))
    plt.barh(d["series"], d["abs_rank60_jump_pp"])
    plt.axvline(jump_p_threshold, linestyle="--")
    plt.xlabel("近60位階變化（百分位點，|Δ|）")
    plt.title("短窗口跳動強度（近60位階變化）")
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

    # label points; if too crowded later, we can add a flag to disable labels
    for _, r in d.iterrows():
        plt.text(r["z60"], r["rank_252_obs_pct"], str(r["series"]), fontsize=9)

    plt.axhline(p_watch_lo, linestyle="--")
    plt.axhline(p_watch_hi, linestyle="--")
    plt.axvline(extreme_z_watch, linestyle="--")
    plt.axvline(-extreme_z_watch, linestyle="--")
    plt.axvline(extreme_z_alert, linestyle=":")
    plt.axvline(-extreme_z_alert, linestyle=":")

    plt.xlabel(ZH.get("z60", "z60"))
    plt.ylabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"))
    plt.title("z60 × 長窗口位階（快速定位『極端+位階』）")
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
    plt.xlabel(ZH.get("ret1_abs_pct", "ret1_abs_pct"))
    plt.title("單日變動幅度總覽（|ret1|%）")
    plt.tight_layout()
    plt.savefig(outdir / "04_ret1_abs_pct.png", dpi=200)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="Path to dashboard markdown, e.g. dashboard/DASHBOARD.md")
    ap.add_argument("--out", required=True, help="Output directory, e.g. dashboard/charts/market_cache")

    # Keep thresholds aligned with your ruleset defaults (signals_v8)
    ap.add_argument("--jump-p", type=float, default=15.0, help="Jump threshold for abs(PΔ60) in percentile points")
    ap.add_argument("--jump-ret", type=float, default=2.0, help="Jump threshold for abs(ret1%1d)")
    ap.add_argument("--extreme-z-watch", type=float, default=2.0, help="Extreme Z watch threshold")
    ap.add_argument("--extreme-z-alert", type=float, default=2.5, help="Extreme Z alert threshold")
    ap.add_argument("--p-watch-lo", type=float, default=5.0, help="Low percentile watch threshold (p252)")
    ap.add_argument("--p-watch-hi", type=float, default=95.0, help="High percentile watch threshold (p252)")
    ap.add_argument("--p-alert-lo", type=float, default=2.0, help="Low percentile alert threshold (p252)")

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
            "解析表格成功但缺少 'Series' 欄位（或已改名）。\n"
            f"附近內容：\n{ctx}"
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