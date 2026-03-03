#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_market_cache_charts.py

Generate chart-ready CSV + standard charts from dashboard/DASHBOARD.md.

- Bar charts: legend stays inside (keep text short).
- Scatter chart: NO in-axes annotation boxes; NO legend (avoid duplication).
  Rules are explained ONLY in bottom_note (figure-level).
- Long rule notes are placed BELOW (figure-level bottom_note).
- Watermark stays at bottom-right.
"""

from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Optional

import matplotlib
matplotlib.use("Agg", force=True)

import pandas as pd
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
    global CJK_FP

    sample = "長窗口位階總覽（近252筆）近60位階變化（百分位點）單日變動幅度中文冒煙測試"

    preferred = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    candidates: List[str] = []

    if Path(preferred).exists():
        candidates.append(preferred)

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

    selected = None
    for p in candidates:
        pth = Path(p)
        if not pth.exists():
            continue
        if _font_supports_text(str(pth), sample):
            selected = str(pth)
            break

    if selected is None:
        CJK_FP = None
        plt.rcParams["axes.unicode_minus"] = False
        if verbose:
            print("[charts] font_selected=DEFAULT(no usable CJK font found)")
        return

    CJK_FP = FontProperties(fname=selected)
    plt.rcParams["axes.unicode_minus"] = False
    if verbose:
        print(f"[charts] font_path={selected}")


def apply_cjk_to_axes(ax) -> None:
    if CJK_FP is None:
        return

    ax.title.set_fontproperties(CJK_FP)
    ax.xaxis.label.set_fontproperties(CJK_FP)
    ax.yaxis.label.set_fontproperties(CJK_FP)

    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontproperties(CJK_FP)

    for t in ax.texts:
        t.set_fontproperties(CJK_FP)

    leg = ax.get_legend()
    if leg is not None:
        for t in leg.get_texts():
            t.set_fontproperties(CJK_FP)


def log_axes_fonts(ax, tag: str) -> None:
    try:
        t_fp = ax.title.get_fontproperties()
        x_fp = ax.xaxis.label.get_fontproperties()
        t_file = getattr(t_fp, "get_file", lambda: None)()
        x_file = getattr(x_fp, "get_file", lambda: None)()
        print(f"[charts][font_audit][{tag}] title_font_file={t_file}")
        print(f"[charts][font_audit][{tag}] xlabel_font_file={x_file}")
    except Exception as e:
        print(f"[charts][font_audit][{tag}] ERROR={e}")


def save_font_smoketest(outdir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_title("中文冒煙測試：長窗口位階總覽（近252筆）", fontproperties=CJK_FP)
    ax.set_xlabel("近252筆位階（%）", fontproperties=CJK_FP)
    ax.set_ylabel("測試軸", fontproperties=CJK_FP)

    apply_cjk_to_axes(ax)
    log_axes_fonts(ax, "smoketest")

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
# Figure helpers
# -----------------------------

def legend_kwargs():
    return {"prop": CJK_FP} if CJK_FP is not None else {}


def add_watermark(fig, enabled: bool) -> None:
    if not enabled:
        return
    sha7 = (os.environ.get("GITHUB_SHA", "") or "")[:7]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    text = f"generated_at={ts}"
    if sha7:
        text += f"  sha={sha7}"
    fig.text(0.99, 0.01, text, ha="right", va="bottom", fontsize=9, fontproperties=CJK_FP)


def add_bottom_note(fig, text: str) -> None:
    if not text.strip():
        return
    fig.text(
        0.01, 0.01,
        text,
        ha="left",
        va="bottom",
        fontsize=10,
        fontproperties=CJK_FP,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.9),
    )


def finalize_figure(fig, ax, outpath: Path, bottom_note: str, watermark: bool,
                    rect: Optional[List[float]] = None) -> None:
    """
    rect default leaves bottom space for note/watermark.
    """
    apply_cjk_to_axes(ax)

    if rect is None:
        rect = [0.0, 0.18, 1.0, 1.0]

    fig.tight_layout(rect=rect)
    add_bottom_note(fig, bottom_note)
    add_watermark(fig, watermark)

    fig.savefig(outpath, dpi=200)
    plt.close(fig)


def add_bar_end_labels(ax, bars, fmt: str, x_pad_frac: float = 0.01) -> None:
    xmin, xmax = ax.get_xlim()
    pad = (xmax - xmin) * x_pad_frac if xmax > xmin else 0.5
    for b in bars:
        w = b.get_width()
        y = b.get_y() + b.get_height() / 2.0
        if pd.isna(w):
            continue
        ax.text(
            w + pad, y,
            fmt.format(w),
            va="center", ha="left",
            fontsize=10,
            fontproperties=CJK_FP,
        )


# -----------------------------
# Charts
# -----------------------------

def save_chart_rank252(df: pd.DataFrame, outdir: Path, watermark: bool,
                       p_watch_lo: float = 5.0, p_watch_hi: float = 95.0, p_alert_lo: float = 2.0) -> None:
    if "rank_252_obs_pct" not in df.columns:
        return
    d = df.copy().dropna(subset=["rank_252_obs_pct", "series"])
    if d.empty:
        return
    d = d.sort_values("rank_252_obs_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(d["series"], d["rank_252_obs_pct"])

    ax.axvline(p_watch_lo, linestyle="--", label=f"WATCH {p_watch_lo:g}%")
    ax.axvline(p_watch_hi, linestyle="--", label=f"WATCH {p_watch_hi:g}%")
    ax.axvline(p_alert_lo, linestyle=":", label=f"ALERT {p_alert_lo:g}%")

    ax.set_xlim(0, 100)
    ax.set_xlabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"), fontproperties=CJK_FP)
    ax.set_title("長窗口位階總覽（近252筆）", fontproperties=CJK_FP)
    add_bar_end_labels(ax, bars, "{:.1f}%")
    ax.legend(loc="lower right", **legend_kwargs())

    log_axes_fonts(ax, "rank252")

    bottom_note = (
        "註解：\n"
        "• 條形末端＝當前位階（%）\n"
        f"• 虛線＝WATCH 門檻（{p_watch_lo:g}% / {p_watch_hi:g}%）\n"
        f"• 點線＝ALERT 門檻（{p_alert_lo:g}%）"
    )
    finalize_figure(fig, ax, outdir / "01_rank252_overview.png", bottom_note, watermark)


def save_chart_rank60_jump_abs(df: pd.DataFrame, outdir: Path, watermark: bool,
                              jump_p_threshold: float = 15.0) -> None:
    if "rank_60_delta_pp" not in df.columns:
        return
    d = df.copy().dropna(subset=["rank_60_delta_pp", "series"])
    if d.empty:
        return

    d["abs_rank60_jump_pp"] = d["rank_60_delta_pp"].abs()
    d = d.sort_values("abs_rank60_jump_pp", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(d["series"], d["abs_rank60_jump_pp"])

    ax.axvline(jump_p_threshold, linestyle="--", label=f"JUMP {jump_p_threshold:g}pp")

    ax.set_xlabel("近60位階變化（百分位點，|Δ|）", fontproperties=CJK_FP)
    ax.set_title("短窗口跳動強度（近60位階變化）", fontproperties=CJK_FP)
    add_bar_end_labels(ax, bars, "{:.1f}pp")
    ax.legend(loc="lower right", **legend_kwargs())

    log_axes_fonts(ax, "rank60_jump_abs")

    bottom_note = (
        "註解：\n"
        "• 條形＝|Δ rank60|（百分位點）\n"
        f"• 虛線＝JUMP 門檻（{jump_p_threshold:g}pp）"
    )
    finalize_figure(fig, ax, outdir / "02_rank60_jump_abs.png", bottom_note, watermark)


def save_chart_scatter(df: pd.DataFrame, outdir: Path, watermark: bool,
                       extreme_z_watch: float = 2.0, extreme_z_alert: float = 2.5,
                       p_watch_lo: float = 5.0, p_watch_hi: float = 95.0, p_alert_lo: float = 2.0,
                       label_points: bool = True) -> None:
    need = {"z60", "rank_252_obs_pct", "series"}
    if not need.issubset(set(df.columns)):
        return
    d = df.copy().dropna(subset=["z60", "rank_252_obs_pct", "series"])
    if d.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.scatter(d["z60"], d["rank_252_obs_pct"])

    if label_points:
        for _, r in d.iterrows():
            ax.text(
                r["z60"], r["rank_252_obs_pct"], str(r["series"]),
                fontsize=10, fontproperties=CJK_FP
            )

    # thresholds on axes
    ax.axhline(p_watch_lo, linestyle="--")
    ax.axhline(p_watch_hi, linestyle="--")
    ax.axhline(p_alert_lo, linestyle=":")

    ax.axvline(extreme_z_watch, linestyle="--")
    ax.axvline(-extreme_z_watch, linestyle="--")
    ax.axvline(extreme_z_alert, linestyle=":")
    ax.axvline(-extreme_z_alert, linestyle=":")

    ax.set_xlabel(ZH.get("z60", "z60"), fontproperties=CJK_FP)
    ax.set_ylabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"), fontproperties=CJK_FP)
    ax.set_title("z60 × 長窗口位階（快速定位『極端+位階』）", fontproperties=CJK_FP)

    # IMPORTANT:
    # - NO annotation boxes inside axes
    # - NO legend (avoid duplication with bottom_note)
    log_axes_fonts(ax, "scatter")

    bottom_note = (
        "註解：\n"
        "• 點標＝各序列當前位置\n"
        f"• WATCH（虛線）：|z60|≥{extreme_z_watch:g} 或 p252≤{p_watch_lo:g} / ≥{p_watch_hi:g}\n"
        f"• ALERT（點線）：|z60|≥{extreme_z_alert:g} 或 p252≤{p_alert_lo:g}"
    )

    # Reserve modest bottom space (note + watermark only)
    finalize_figure(
        fig, ax,
        outdir / "03_z60_vs_rank252_scatter.png",
        bottom_note,
        watermark,
        rect=[0.0, 0.20, 1.0, 1.0],
    )


def save_chart_ret1_abs(df: pd.DataFrame, outdir: Path, watermark: bool,
                        jump_ret_threshold: float = 2.0) -> None:
    if "ret1_abs_pct" not in df.columns:
        return
    d = df.copy().dropna(subset=["ret1_abs_pct", "series"])
    if d.empty:
        return
    d = d.sort_values("ret1_abs_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(d["series"], d["ret1_abs_pct"])
    ax.axvline(jump_ret_threshold, linestyle="--", label=f"JUMP {jump_ret_threshold:g}%")

    ax.set_xlabel("單日變化幅度（%）", fontproperties=CJK_FP)
    ax.set_title("單日變動幅度總覽（|ret1|%）", fontproperties=CJK_FP)
    add_bar_end_labels(ax, bars, "{:.2f}%")
    ax.legend(loc="lower right", **legend_kwargs())

    log_axes_fonts(ax, "ret1_abs")

    bottom_note = (
        "註解：\n"
        "• 條形＝|ret1|（單日變化幅度，%）\n"
        f"• 虛線＝JUMP 門檻（{jump_ret_threshold:g}%）"
    )
    finalize_figure(fig, ax, outdir / "04_ret1_abs_pct.png", bottom_note, watermark)


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True)

    ap.add_argument("--jump-p", type=float, default=15.0)
    ap.add_argument("--jump-ret", type=float, default=2.0)
    ap.add_argument("--extreme-z-watch", type=float, default=2.0)
    ap.add_argument("--extreme-z-alert", type=float, default=2.5)
    ap.add_argument("--p-watch-lo", type=float, default=5.0)
    ap.add_argument("--p-watch-hi", type=float, default=95.0)
    ap.add_argument("--p-alert-lo", type=float, default=2.0)

    ap.add_argument("--no-watermark", action="store_true")
    ap.add_argument("--no-point-labels", action="store_true")
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

    watermark = not args.no_watermark
    label_points = not args.no_point_labels

    save_chart_rank252(
        df, outdir, watermark,
        p_watch_lo=args.p_watch_lo, p_watch_hi=args.p_watch_hi, p_alert_lo=args.p_alert_lo
    )
    save_chart_rank60_jump_abs(
        df, outdir, watermark, jump_p_threshold=args.jump_p
    )
    save_chart_scatter(
        df, outdir, watermark,
        extreme_z_watch=args.extreme_z_watch, extreme_z_alert=args.extreme_z_alert,
        p_watch_lo=args.p_watch_lo, p_watch_hi=args.p_watch_hi, p_alert_lo=args.p_alert_lo,
        label_points=label_points
    )
    save_chart_ret1_abs(
        df, outdir, watermark, jump_ret_threshold=args.jump_ret
    )

    print(f"OK: wrote {csv_path} and charts to {outdir}")


if __name__ == "__main__":
    main()