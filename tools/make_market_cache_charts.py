#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_market_cache_charts.py

Generate chart-ready CSV + standard charts from dashboard/DASHBOARD.md.

Hard fix for Chinese tofu in CI:
- Use a CJK font by *file path* (FontProperties(fname=...)).
- Apply that FontProperties at *creation time* (set_title/set_xlabel/set_ylabel/text),
  AND re-apply to axes objects before savefig (defensive).
- Emit a smoketest that uses *axes title/xlabel* (same path as real charts).
- Print audit logs: which font file is actually attached to title/xlabel.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple, Optional
import glob

import matplotlib
matplotlib.use("Agg", force=True)  # deterministic backend in CI

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
    Use NotoSansCJK-Regular.ttc if present (fonts-noto-cjk on ubuntu-latest).
    If not, scan common dirs for Noto CJK files that support our Traditional sample.
    """
    global CJK_FP

    sample = "長窗口位階總覽（近252筆）近60位階變化（百分位點）單日變動幅度中文冒煙測試"

    preferred = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    candidates: List[str] = []

    if Path(preferred).exists():
        candidates.append(preferred)

    # Fallback scan
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
    """Force-apply CJK FontProperties to all text elements on an axes."""
    if CJK_FP is None:
        return

    ax.title.set_fontproperties(CJK_FP)
    ax.xaxis.label.set_fontproperties(CJK_FP)
    ax.yaxis.label.set_fontproperties(CJK_FP)

    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontproperties(CJK_FP)

    for t in ax.texts:
        t.set_fontproperties(CJK_FP)


def log_axes_fonts(ax, tag: str) -> None:
    """Audit: show what font file title/xlabel are actually bound to."""
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
    """
    Smoketest using *axes title/xlabel* (same code path as real charts),
    not just ax.text.
    """
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

    ax.set_xlabel(ZH.get("rank_252_obs_pct", "rank_252_obs_pct"), fontproperties=CJK_FP)
    ax.set_title("長窗口位階總覽（近252筆）", fontproperties=CJK_FP)

    apply_cjk_to_axes(ax)
    log_axes_fonts(ax, "rank252")

    fig.tight_layout()
    fig.savefig(outdir / "01_rank252_overview.png", dpi=200)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True)
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

    (outdir / "chart_ready.csv").write_bytes(
        df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    )

    # For brevity: keep only rank252 here; you can copy the same pattern to other charts
    save_chart_rank252(df, outdir)

    print(f"OK: wrote charts to {outdir}")


if __name__ == "__main__":
    main()