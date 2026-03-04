#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_roll25_json_charts.py

Long-series charts from roll25_cache/roll25.json (list of daily records).

Reads:
- roll25.json: [{date, close, change, trade_value, high, low}, ...]

Writes PNG charts to --out_dir.

Audit-first:
- Uses only the fields in roll25.json.
- Computes derived series with explicit definitions:
  * ret_pct: (close/prev_close - 1) * 100
  * amplitude_pct: (high-low)/prev_close * 100
  * rolling z: (x-mean)/std, std uses ddof=0
  * rolling percentile p: ECDF percentile = 100*(n_less + 0.5*n_equal)/n

Charts:
- 10_close_series.png                (+ last value)
- 11_trade_value_series.png          (+ last value)
- 12_trade_value_p252.png            (+ guides + last value + short note)
- 13_trade_value_z252.png            (+ note + last value)
- 14_amplitude_pct.png               (+ last value)
- 15_amplitude_p252.png              (+ guides + last value + short note)
- 16_close_p252.png                  (+ guides + last value + short note)
- 17_trade_value_p60.png             (+ guides + last value + short note)
- roll25_chart_ready.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


PERCENTILE_GUIDES = [50, 80, 90, 95, 99]


# -----------------------
# i18n / labels
# -----------------------
TEXT = {
    "en": {
        "twse_close_title": "TWSE close",
        "twse_trade_value_title": "TWSE trade_value",
        "close_ylabel": "Close",
        "trade_value_ylabel": "Trade value",
        "percentile_rank_ylabel": "Percentile rank (0-100)",
        "zscore_ylabel": "Z-score",
        "amplitude_pct_title": "amplitude_pct",
        "amplitude_pct_ylabel": "Amplitude %",
        "trade_value_percentile_rank": "Trade value percentile rank",
        "trade_value_zscore": "Trade value z-score",
        "close_percentile_rank": "Close percentile rank",
        "amplitude_percentile_rank": "Amplitude percentile rank",
        "win_252": "252D ~ 1Y",
        "win_60": "60D ~ 3M",
        "note_percentile_252": "Note: percentile rank = today's position within the last 252 trading days (0-100).",
        "note_percentile_60": "Note: percentile rank = today's position within the last 60 trading days (0-100).",
        "note_z_252": "Note: z-score = (x - mean) / std within the last 252 trading days.",
    },
    "zh": {
        "twse_close_title": "加權指數收盤",
        "twse_trade_value_title": "大盤成交金額",
        "close_ylabel": "指數點位",
        "trade_value_ylabel": "成交金額",
        "percentile_rank_ylabel": "百分位排名（0–100）",
        "zscore_ylabel": "Z 分數",
        "amplitude_pct_title": "振幅（%）",
        "amplitude_pct_ylabel": "振幅（%）",
        "trade_value_percentile_rank": "成交金額百分位排名",
        "trade_value_zscore": "成交金額 Z 分數",
        "close_percentile_rank": "收盤指數百分位排名",
        "amplitude_percentile_rank": "振幅百分位排名",
        "win_252": "近 252 個交易日 ≈ 1 年",
        "win_60": "近 60 個交易日 ≈ 3 個月",
        "note_percentile_252": "註：百分位排名＝今日數值在近 252 個交易日的相對位置（0–100）。",
        "note_percentile_60": "註：百分位排名＝今日數值在近 60 個交易日的相對位置（0–100）。",
        "note_z_252": "註：Z 分數＝（今日值－近 252 日平均）÷ 近 252 日標準差。",
    },
}


def apply_cjk_font_if_needed(lang: str) -> None:
    """
    Make CJK work on GitHub Actions ubuntu runners (fonts-noto-cjk installed in your workflow).
    This is intentionally "best-effort": if the font name differs, matplotlib will fallback.
    """
    if lang != "zh":
        return
    plt.rcParams["font.sans-serif"] = [
        "Noto Sans CJK TC",
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "Noto Sans CJK KR",
        "Noto Sans",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def t(lang: str, key: str) -> str:
    if lang not in TEXT:
        lang = "en"
    return TEXT[lang].get(key, TEXT["en"].get(key, key))


# -----------------------
# IO helpers
# -----------------------
def load_roll25_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def save_fig(fig, out_path: Path) -> None:
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# -----------------------
# math helpers
# -----------------------
def ecdf_percentile(window: np.ndarray, x: float) -> Optional[float]:
    """
    Percentile definition:
      p = 100 * (count(<x) + 0.5*count(==x)) / n
    """
    w = window[~np.isnan(window)]
    n = w.size
    if n <= 0:
        return None
    less = np.sum(w < x)
    eq = np.sum(w == x)
    return 100.0 * (less + 0.5 * eq) / float(n)


def rolling_z_and_p(series: np.ndarray, window: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute rolling z-score and ECDF percentile using a fixed-size trailing window.
    Only produces values when at least `window` points are available (non-NaN).
    """
    n = series.size
    z = np.full(n, np.nan, dtype=float)
    p = np.full(n, np.nan, dtype=float)

    for i in range(n):
        start = max(0, i - window + 1)
        w = series[start : i + 1].astype(float)

        w_valid = w[~np.isnan(w)]
        if w_valid.size < window:
            continue

        x = float(series[i])
        if np.isnan(x):
            continue

        mu = float(np.mean(w_valid))
        sd = float(np.std(w_valid, ddof=0))
        if sd > 0:
            z[i] = (x - mu) / sd

        pp = ecdf_percentile(w_valid, x)
        if pp is not None:
            p[i] = pp

    return z, p


# -----------------------
# chart helpers
# -----------------------
def add_percentile_guides(ax) -> None:
    """Add horizontal reference lines for percentiles: 50/80/90/95/99."""
    for lvl in PERCENTILE_GUIDES:
        ax.axhline(lvl, linewidth=0.8, alpha=0.25)


def format_compact_number(v: float) -> str:
    """
    Compact formatter for large numbers (e.g., trade_value).
    Uses K/M/B/T (thousand/million/billion/trillion).
    """
    av = abs(v)
    if av >= 1e12:
        return f"{v/1e12:.2f}T"
    if av >= 1e9:
        return f"{v/1e9:.2f}B"
    if av >= 1e6:
        return f"{v/1e6:.2f}M"
    if av >= 1e3:
        return f"{v/1e3:.2f}K"
    return f"{v:.0f}"


def annotate_last_value(
    ax,
    x: pd.Series,
    y: pd.Series,
    *,
    fmt: str = "{:.1f}",
    formatter: Optional[Callable[[float], str]] = None,
    marker_size: float = 5.0,
) -> None:
    """
    Mark + label the last NON-NaN point of a series.
    - Adds a small circle at the last point.
    - Adds a value label near the point (auto places to reduce clipping).
    """
    xs = pd.to_datetime(x, errors="coerce")
    ys = pd.to_numeric(y, errors="coerce")
    valid = (~xs.isna()) & (~ys.isna())
    if not bool(valid.any()):
        return

    last_idx = valid[valid].index[-1]
    x_last = xs.loc[last_idx]
    y_last = float(ys.loc[last_idx])

    # marker (last effective point)
    ax.plot([x_last], [y_last], marker="o", markersize=marker_size)

    # label
    label = formatter(y_last) if formatter is not None else fmt.format(y_last)

    # Make sure axis limits are materialized before we decide label placement
    # (Agg backend usually works without draw(), but this is safer.)
    try:
        ax.figure.canvas.draw()
    except Exception:
        pass

    # Decide label side (avoid right-edge clipping)
    try:
        x_num = mdates.date2num(x_last.to_pydatetime())
    except Exception:
        x_num = mdates.date2num(pd.to_datetime(x_last).to_pydatetime())

    xmin, xmax = ax.get_xlim()
    xspan = max(xmax - xmin, 1e-9)
    near_right = x_num > (xmax - 0.03 * xspan)

    # Decide vertical offset (avoid top clipping)
    ymin, ymax = ax.get_ylim()
    yspan = max(ymax - ymin, 1e-9)
    y_pos = (y_last - ymin) / yspan
    near_top = y_pos > 0.88

    dx = -6 if near_right else 6
    ha = "right" if near_right else "left"
    dy = -10 if near_top else 10
    va = "top" if near_top else "bottom"

    ax.annotate(
        label,
        xy=(x_last, y_last),
        xytext=(dx, dy),
        textcoords="offset points",
        ha=ha,
        va=va,
    )


def add_bottom_note(fig, text: str) -> None:
    """
    Add a short explanation note at the bottom-left of the figure.
    Keep it 1 line to avoid turning into a 'teaching slide'.
    """
    fig.text(0.01, 0.01, text, ha="left", va="bottom", fontsize=9, alpha=0.85)


# -----------------------
# main
# -----------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roll25_json", required=True, help="Path to roll25.json (list of records)")
    ap.add_argument("--out_dir", required=True, help="Output directory for charts")
    ap.add_argument("--max_points", default="400", help="Max points to plot (most recent). Default 400")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"], help="Chart language: zh or en (default: zh)")
    args = ap.parse_args()

    lang = args.lang
    apply_cjk_font_if_needed(lang)

    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    rows = load_roll25_json(args.roll25_json)
    if not isinstance(rows, list) or not rows:
        raise SystemExit("roll25.json is empty or not a list.")

    df = pd.DataFrame(rows)
    if "date" not in df.columns:
        raise SystemExit("roll25.json missing 'date' field.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    max_points = int(args.max_points)
    if len(df) > max_points:
        df = df.iloc[-max_points:].reset_index(drop=True)

    for c in ["close", "trade_value", "high", "low"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["prev_close"] = df["close"].shift(1)
    df["ret_pct"] = (df["close"] / df["prev_close"] - 1.0) * 100.0
    df["amplitude_pct"] = (df["high"] - df["low"]) / df["prev_close"] * 100.0

    tv = df["trade_value"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    amp = df["amplitude_pct"].to_numpy(dtype=float)

    z60_tv, p60_tv = rolling_z_and_p(tv, 60)
    z252_tv, p252_tv = rolling_z_and_p(tv, 252)
    z60_close, p60_close = rolling_z_and_p(close, 60)
    z252_close, p252_close = rolling_z_and_p(close, 252)
    z60_amp, p60_amp = rolling_z_and_p(amp, 60)
    z252_amp, p252_amp = rolling_z_and_p(amp, 252)

    df["tv_z60"] = z60_tv
    df["tv_p60"] = p60_tv
    df["tv_z252"] = z252_tv
    df["tv_p252"] = p252_tv

    df["close_z60"] = z60_close
    df["close_p60"] = p60_close
    df["close_z252"] = z252_close
    df["close_p252"] = p252_close

    df["amp_z60"] = z60_amp
    df["amp_p60"] = p60_amp
    df["amp_z252"] = z252_amp
    df["amp_p252"] = p252_amp

    asof = df["date"].max().date().isoformat()

    # 1) Close series (+ last value)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["close"])
    annotate_last_value(ax, df["date"], df["close"], fmt="{:,.0f}")
    ax.set_title(f"{t(lang,'twse_close_title')} (as_of={asof})", pad=16)
    ax.set_ylabel(t(lang, "close_ylabel"))
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    save_fig(fig, out_dir / "10_close_series.png")

    # 2) Trade value series (+ last value)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["trade_value"])
    annotate_last_value(ax, df["date"], df["trade_value"], formatter=format_compact_number)
    ax.set_title(f"{t(lang,'twse_trade_value_title')} (as_of={asof})", pad=16)
    ax.set_ylabel(t(lang, "trade_value_ylabel"))
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    save_fig(fig, out_dir / "11_trade_value_series.png")

    # 3) Trade value p252 (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["tv_p252"])
    add_percentile_guides(ax)
    ax.set_ylim(0, 100)  # set first so annotation placement uses correct ylim
    annotate_last_value(ax, df["date"], df["tv_p252"], fmt="{:.1f}")
    ax.set_title(
        f"{t(lang,'trade_value_percentile_rank')} ({t(lang,'win_252')}) (as_of={asof})",
        pad=16,
    )
    ax.set_ylabel(t(lang, "percentile_rank_ylabel"))
    add_bottom_note(fig, t(lang, "note_percentile_252"))
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "12_trade_value_p252.png")

    # 4) Trade value z252 (+ note + last value)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["tv_z252"])
    annotate_last_value(ax, df["date"], df["tv_z252"], fmt="{:.2f}")
    ax.set_title(
        f"{t(lang,'trade_value_zscore')} ({t(lang,'win_252')}) (as_of={asof})",
        pad=16,
    )
    ax.set_ylabel(t(lang, "zscore_ylabel"))
    add_bottom_note(fig, t(lang, "note_z_252"))
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "13_trade_value_z252.png")

    # 5) Amplitude pct (+ last value)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["amplitude_pct"])
    annotate_last_value(ax, df["date"], df["amplitude_pct"], fmt="{:.2f}")
    ax.set_title(f"{t(lang,'amplitude_pct_title')} (as_of={asof})", pad=16)
    ax.set_ylabel(t(lang, "amplitude_pct_ylabel"))
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    save_fig(fig, out_dir / "14_amplitude_pct.png")

    # 6) Amplitude p252 (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["amp_p252"])
    add_percentile_guides(ax)
    ax.set_ylim(0, 100)
    annotate_last_value(ax, df["date"], df["amp_p252"], fmt="{:.1f}")
    ax.set_title(
        f"{t(lang,'amplitude_percentile_rank')} ({t(lang,'win_252')}) (as_of={asof})",
        pad=16,
    )
    ax.set_ylabel(t(lang, "percentile_rank_ylabel"))
    add_bottom_note(fig, t(lang, "note_percentile_252"))
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "15_amplitude_p252.png")

    # 7) Close p252 (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["close_p252"])
    add_percentile_guides(ax)
    ax.set_ylim(0, 100)
    annotate_last_value(ax, df["date"], df["close_p252"], fmt="{:.1f}")
    ax.set_title(
        f"{t(lang,'close_percentile_rank')} ({t(lang,'win_252')}) (as_of={asof})",
        pad=16,
    )
    ax.set_ylabel(t(lang, "percentile_rank_ylabel"))
    add_bottom_note(fig, t(lang, "note_percentile_252"))
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "16_close_p252.png")

    # 8) Trade value p60 (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["tv_p60"])
    add_percentile_guides(ax)
    ax.set_ylim(0, 100)
    annotate_last_value(ax, df["date"], df["tv_p60"], fmt="{:.1f}")
    ax.set_title(
        f"{t(lang,'trade_value_percentile_rank')} ({t(lang,'win_60')}) (as_of={asof})",
        pad=16,
    )
    ax.set_ylabel(t(lang, "percentile_rank_ylabel"))
    add_bottom_note(fig, t(lang, "note_percentile_60"))
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "17_trade_value_p60.png")

    # Export chart-ready CSV (kept in English column names for audit/repro)
    csv_path = out_dir / "roll25_chart_ready.csv"
    df_out = df[
        [
            "date",
            "close",
            "trade_value",
            "ret_pct",
            "amplitude_pct",
            "tv_z60",
            "tv_p60",
            "tv_z252",
            "tv_p252",
            "close_z60",
            "close_p60",
            "close_z252",
            "close_p252",
            "amp_z60",
            "amp_p60",
            "amp_z252",
            "amp_p252",
        ]
    ].copy()
    df_out.to_csv(csv_path, index=False, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())