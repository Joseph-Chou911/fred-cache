#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_market_cache_charts.py

Generate chart-ready CSV + standard charts from dashboard/DASHBOARD.md.

Fix for "tofu Chinese in charts":
- Use a CJK font by *file path* (FontProperties(fname=...)).
- Force-apply that FontProperties to every axes text element (title/xlabel/ylabel/ticks/texts)
  right before savefig, to prevent matplotlib fallback fonts from rendering Chinese.

Outputs (to --out):
- 00_font_smoketest.png
- chart_ready.csv
- 01_rank252_overview.png
- 02_rank60_jump_abs.png
- 03_z60_vs_rank252_scatter.png
- 04_ret1_abs_pct.png
"""

import argparse
from pathlib import Path
from typing import List, Tuple, Optional
import glob

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.ft2font import FT2Font


# -----------------------------
# Data defs
# -----------------------------

NUM_COLS = [
    "age_h", "value", "z60", "p60", "p252", "z252",
    "z_poschg60", "p_poschg60", "ret1_pct1d_absPrev",
    "StreakHist", "StreakWA",
]

RENAME = {
    "p60": "rank_60_obs_pct",
    "p252": "rank_252_obs_pct",
    "p_poschg60": "rank_60_delta_pp",
    "z_poschg60": "z_60_delta",
    "ret1_pct1d_absPrev": "ret1_abs_pct",
    "Series": "series",
    "Signal": "signal",
    "Tag": "tag",
    "DQ": "dq",
    "data_date": "data_date",
    "as_of_ts": "as_of_ts",
}

ZH = {
    "rank_252_obs_pct": "近252筆位階（%）",
    "rank_60_delta_pp": "近60位階變化（百分位點）",
    "z60": "z60（近60標準化偏離）",
    "ret1_abs_pct": "單日變化幅度（%）",
}

CJK_FP: Optional[FontProperties] = None


# -----------------------------
# Font handling (CJK)
# -----------------------------

def _font_supports_text(font_path: str, text: str) -> bool:
    """Glyph coverage check by charmap presence."""
    try:
        ft = FT2Font(font_path)
        cmap = ft.get_charmap()
        for ch in text:
            if ch.isspace():
                continue
            if ord(ch) not in cmap:
                return False
        return True
    except Exception:
        return False


def setup_cjk_font(verbose: bool = True) -> None:
    """
    Prefer NotoSansCJK-Regular.ttc if present (GitHub Actions + fonts-noto-cjk).
    If not present, fallback to any Noto CJK TTC/OTF/TTF that supports our Traditional sample.
    """
    global CJK_FP

    # Ensure deterministic backend in CI
    matplotlib.use("Agg", force=True)

    # Traditional sample (includes chars that often break with JP-only face)
    sample = "中文冒煙測試：長窗口位階總覽（近252筆）近60位階變化（百分位點）單日變動幅度"

    preferred_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    candidates: List[str] = []
    for p in preferred_paths:
        if Path(p).exists():
            candidates.append(p)

    # Fallback: scan common dirs for Noto CJK font files
    if not candidates:
        patterns = [
            "/usr/share/fonts/**/NotoSansCJK-*.ttc",
            "/usr/share/fonts/**/NotoSansCJK-*.otf",
            "/usr/share/fonts/**/NotoSansCJK-*.ttf",
            "/usr/share/fonts/**/NotoSerifCJK-*.ttc",
            "/usr/share/fonts/**/NotoSerifCJK-*.otf",
            "/usr/share/fonts/**/NotoSerifCJK-*.ttf",
        ]
        for pat in patterns:
            candidates.extend(glob.glob(pat, recursive=True))

    # Pick first font file that truly supports the Traditional sample
    selected_path = None
    for p in candidates:
        if Path(p).exists() and _font_supports_text(p, sample):
            selected_path = p
            break

    if selected_path is None:
        CJK_FP = None
        plt.rcParams["axes.unicode_minus"] = False
        if verbose:
            print("[charts] font_selected=DEFAULT(no usable CJK font found)")
        return

    CJK_FP = FontProperties(fname=selected_path)
    plt.rcParams["axes.unicode_minus"] = False

    if verbose:
        print("[charts] font_selected=FILE")
        print(f"[charts] font_path={selected_path}")


def apply_cjk_to_axes(ax) -> None:
    """Force-apply CJK FontProperties to all text elements on an axes."""
    if CJK_FP is None:
        return

    # Title / axis labels
    ax.title.set_fontproperties(CJK_FP)
    ax.xaxis.label.set_fontproperties(CJK_FP)
    ax.yaxis.label.set_fontproperties(CJK_FP)

    # Tick labels
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontproperties(CJK_FP)

    # Annotations / texts
    for t in ax.texts:
        t.set_fontproperties(CJK_FP)


def save_font_smoketest(outdir: Path) -> None:
    """A tiny image to validate Chinese rendering end-to-end."""
    fig, ax = plt.subplots(figsize=(9, 2.2))
    ax.axis("off")
    ax.text(
        0.01, 0.65,
        "中文冒煙測試：長窗口位階總覽（近252筆）",
        fontsize=16,
        fontproperties=CJK_FP
    )
    ax.text(
        0.01, 0.20,
        "如果這行是豆腐字＝字型沒生效或缺字形",
        fontsize=12,
        fontproperties=CJK_FP
    )
    fig.tight_layout()
    fig.savefig(outdir / "00_font_smoketest.png", dpi=200)
    plt.close(fig)


# -----------------------------
# Markdown parsing
# -----------------------------

def _peek_context(lines: List[str], idx: int, radius: int = 10) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    out = []
    for i in range(lo, hi):
        prefix = ">> " if i == idx else "   "
        out.append(f"{prefix}{i+1:04d}: {lines[i]}")
    return "\n".join(out)


def extract_markdown_table(report_text: str) -> Tuple[pd.DataFrame, int]:
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
        j += 1

    if not rows:
        ctx = _peek_context(lines, header_idx)
        raise ValueError(f"找到表頭但沒有任何資料列。\n附近內容：\n{ctx}")

    return pd.DataFrame(rows, columns=cols), header_idx


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace({"NA": pd.NA, "N/A": pd.NA, "": pd.NA})
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def ensure_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Charts
# -----------------------------

def save_chart_rank252(df: pd.DataFrame, outdir: Path,
                       p_watch_lo: float = 5.0, p_watch_hi: float = 95.0, p_alert_lo: float = 2.0) -> None:
    if "rank_252_obs_pct" not in df.columns:
        return

    d = df.copy().dropna(subset=["rank_252_obs_pct", "series"])
    if d.empty:
        return
    d = d.sort_values("rank_252_obs_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(d["series"], d["rank_252_obs_pct"])
    ax.axvline(p_watch_lo, linestyle="--")
    ax.axvline(p_watch_hi, linestyle="--")
    ax.axvline(p_alert_lo, linestyle=":")

    ax.set_xlabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"))
    ax.set_title("長窗口位階總覽（近252筆）")

    apply_cjk_to_axes(ax)

    fig.tight_layout()
    fig.savefig(outdir / "01_rank252_overview.png", dpi=200)
    plt.close(fig)


def save_chart_rank60_jump_abs(df: pd.DataFrame, outdir: Path, jump_p_threshold: float = 15.0) -> None:
    if "rank_60_delta_pp" not in df.columns:
        return

    d = df.copy().dropna(subset=["rank_60_delta_pp", "series"])
    if d.empty:
        return

    d["abs_rank60_jump_pp"] = d["rank_60_delta_pp"].abs()
    d = d.sort_values("abs_rank60_jump_pp", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(d["series"], d["abs_rank60_jump_pp"])
    ax.axvline(jump_p_threshold, linestyle="--")

    ax.set_xlabel("近60位階變化（百分位點，|Δ|）")
    ax.set_title("短窗口跳動強度（近60位階變化）")

    apply_cjk_to_axes(ax)

    fig.tight_layout()
    fig.savefig(outdir / "02_rank60_jump_abs.png", dpi=200)
    plt.close(fig)


def save_chart_scatter(df: pd.DataFrame, outdir: Path,
                       extreme_z_watch: float = 2.0, extreme_z_alert: float = 2.5,
                       p_watch_lo: float = 5.0, p_watch_hi: float = 95.0) -> None:
    need = {"z60", "rank_252_obs_pct", "series"}
    if not need.issubset(set(df.columns)):
        return

    d = df.copy().dropna(subset=["z60", "rank_252_obs_pct", "series"])
    if d.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(d["z60"], d["rank_252_obs_pct"])

    for _, r in d.iterrows():
        ax.text(r["z60"], r["rank_252_obs_pct"], str(r["series"]), fontsize=9)

    ax.axhline(p_watch_lo, linestyle="--")
    ax.axhline(p_watch_hi, linestyle="--")
    ax.axvline(extreme_z_watch, linestyle="--")
    ax.axvline(-extreme_z_watch, linestyle="--")
    ax.axvline(extreme_z_alert, linestyle=":")
    ax.axvline(-extreme_z_alert, linestyle=":")

    ax.set_xlabel(ZH.get("z60", "z60"))
    ax.set_ylabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"))
    ax.set_title("z60 × 長窗口位階（快速定位『極端+位階』）")

    apply_cjk_to_axes(ax)

    fig.tight_layout()
    fig.savefig(outdir / "03_z60_vs_rank252_scatter.png", dpi=200)
    plt.close(fig)


def save_chart_ret1_abs(df: pd.DataFrame, outdir: Path, jump_ret_threshold: float = 2.0) -> None:
    if "ret1_abs_pct" not in df.columns:
        return

    d = df.copy().dropna(subset=["ret1_abs_pct", "series"])
    if d.empty:
        return
    d = d.sort_values("ret1_abs_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(d["series"], d["ret1_abs_pct"])
    ax.axvline(jump_ret_threshold, linestyle="--")

    ax.set_xlabel(ZH.get("ret1_abs_pct", "ret1_abs_pct"))
    ax.set_title("單日變動幅度總覽（|ret1|%）")

    apply_cjk_to_axes(ax)

    fig.tight_layout()
    fig.savefig(outdir / "04_ret1_abs_pct.png", dpi=200)
    plt.close(fig)


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="Path to dashboard markdown, e.g. dashboard/DASHBOARD.md")
    ap.add_argument("--out", required=True, help="Output directory, e.g. dashboard/charts/market_cache")

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

    setup_cjk_font(verbose=True)
    save_font_smoketest(outdir)

    if not report_path.exists():
        raise FileNotFoundError(f"report not found: {report_path}")

    text = report_path.read_text(encoding="utf-8")
    df_raw, header_idx = extract_markdown_table(text)

    df_raw = coerce_numeric(df_raw)
    df = df_raw.rename(columns=RENAME)

    if "series" not in df.columns:
        ctx = _peek_context(text.splitlines(), header_idx)
        raise ValueError(
            "解析表格成功但缺少 'Series' 欄位（或已改名）。\n"
            f"附近內容：\n{ctx}"
        )

    csv_path = outdir / "chart_ready.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    save_chart_rank252(df, outdir, p_watch_lo=args.p_watch_lo, p_watch_hi=args.p_watch_hi, p_alert_lo=args.p_alert_lo)
    save_chart_rank60_jump_abs(df, outdir, jump_p_threshold=args.jump_p)
    save_chart_scatter(df, outdir,
                       extreme_z_watch=args.extreme_z_watch, extreme_z_alert=args.extreme_z_alert,
                       p_watch_lo=args.p_watch_lo, p_watch_hi=args.p_watch_hi)
    save_chart_ret1_abs(df, outdir, jump_ret_threshold=args.jump_ret)

    print(f"OK: wrote {csv_path} and charts to {outdir}")


if __name__ == "__main__":
    main()