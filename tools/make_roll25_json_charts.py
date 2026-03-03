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
- 10_close_series.png
- 11_trade_value_series.png
- 12_trade_value_p252.png          (+ guides + last value + short note)
- 13_trade_value_z252.png          (+ short note)
- 14_amplitude_pct.png
- 15_amplitude_p252.png            (+ guides + last value + short note)
- 16_close_p252.png                (+ guides + last value + short note)
- 17_trade_value_p60.png           (+ guides + last value + short note)
- roll25_chart_ready.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt


PERCENTILE_GUIDES = [50, 80, 90, 95, 99]


def load_roll25_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def save_fig(fig, out_path: Path) -> None:
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


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


def add_percentile_guides(ax) -> None:
    """Add horizontal reference lines for percentiles: 50/80/90/95/99."""
    for lvl in PERCENTILE_GUIDES:
        ax.axhline(lvl, linewidth=0.8, alpha=0.25)


def annotate_last_value(ax, x: pd.Series, y: pd.Series, fmt: str = "{:.1f}") -> None:
    """Mark + label the last NON-NaN point of a series."""
    xs = pd.to_datetime(x, errors="coerce")
    ys = pd.to_numeric(y, errors="coerce")
    valid = (~xs.isna()) & (~ys.isna())
    if not bool(valid.any()):
        return

    last_idx = valid[valid].index[-1]
    x_last = xs.loc[last_idx]
    y_last = float(ys.loc[last_idx])

    ax.plot([x_last], [y_last], marker="o", markersize=4)

    if y_last >= 95:
        xytext = (6, -10)
        va = "top"
    else:
        xytext = (6, 10)
        va = "bottom"

    ax.annotate(
        fmt.format(y_last),
        xy=(x_last, y_last),
        xytext=xytext,
        textcoords="offset points",
        ha="left",
        va=va,
    )


def add_bottom_note(fig, text: str) -> None:
    """
    Add a short explanation note at the bottom-left of the figure.
    Keep it 1 line to avoid turning into a 'teaching slide'.
    """
    fig.text(0.01, 0.01, text, ha="left", va="bottom", fontsize=9, alpha=0.85)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roll25_json", required=True, help="Path to roll25.json (list of records)")
    ap.add_argument("--out_dir", required=True, help="Output directory for charts")
    ap.add_argument("--max_points", default="400", help="Max points to plot (most recent). Default 400")
    args = ap.parse_args()

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

    # 1) Close series
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["close"])
    ax.set_title(f"TWSE close (as_of={asof})", pad=16)
    ax.set_ylabel("Close")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    save_fig(fig, out_dir / "10_close_series.png")

    # 2) Trade value series
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["trade_value"])
    ax.set_title(f"TWSE trade_value (as_of={asof})", pad=16)
    ax.set_ylabel("Trade value")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    save_fig(fig, out_dir / "11_trade_value_series.png")

    # 3) Trade value p252  (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["tv_p252"])
    add_percentile_guides(ax)
    annotate_last_value(ax, df["date"], df["tv_p252"])
    ax.set_title(f"Trade value percentile rank (252D ~ 1Y) (as_of={asof})", pad=16)
    ax.set_ylabel("Percentile rank (0-100)")
    ax.set_ylim(0, 100)
    add_bottom_note(fig, "Note: percentile rank = today's position within the last 252 trading days (0-100).")
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "12_trade_value_p252.png")

    # 4) Trade value z252  (+ note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["tv_z252"])
    ax.set_title(f"Trade value z-score (252D ~ 1Y) (as_of={asof})", pad=16)
    ax.set_ylabel("Z-score")
    add_bottom_note(fig, "Note: z-score = (x - mean) / std within the last 252 trading days.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "13_trade_value_z252.png")

    # 5) Amplitude pct
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["amplitude_pct"])
    ax.set_title(f"amplitude_pct (as_of={asof})", pad=16)
    ax.set_ylabel("Amplitude %")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    save_fig(fig, out_dir / "14_amplitude_pct.png")

    # 6) Amplitude p252  (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["amp_p252"])
    add_percentile_guides(ax)
    annotate_last_value(ax, df["date"], df["amp_p252"])
    ax.set_title(f"Amplitude percentile rank (252D ~ 1Y) (as_of={asof})", pad=16)
    ax.set_ylabel("Percentile rank (0-100)")
    ax.set_ylim(0, 100)
    add_bottom_note(fig, "Note: percentile rank = today's position within the last 252 trading days (0-100).")
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "15_amplitude_p252.png")

    # 7) Close p252  (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["close_p252"])
    add_percentile_guides(ax)
    annotate_last_value(ax, df["date"], df["close_p252"])
    ax.set_title(f"Close percentile rank (252D ~ 1Y) (as_of={asof})", pad=16)
    ax.set_ylabel("Percentile rank (0-100)")
    ax.set_ylim(0, 100)
    add_bottom_note(fig, "Note: percentile rank = today's position within the last 252 trading days (0-100).")
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "16_close_p252.png")

    # 8) Trade value p60  (+ guides + last value + note)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["tv_p60"])
    add_percentile_guides(ax)
    annotate_last_value(ax, df["date"], df["tv_p60"])
    ax.set_title(f"Trade value percentile rank (60D ~ 3M) (as_of={asof})", pad=16)
    ax.set_ylabel("Percentile rank (0-100)")
    ax.set_ylim(0, 100)
    add_bottom_note(fig, "Note: percentile rank = today's position within the last 60 trading days (0-100).")
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    save_fig(fig, out_dir / "17_trade_value_p60.png")

    # Optional: export a chart-ready CSV for manual edits
    csv_path = out_dir / "roll25_chart_ready.csv"
    df_out = df[[
        "date", "close", "trade_value", "ret_pct", "amplitude_pct",
        "tv_z60", "tv_p60", "tv_z252", "tv_p252",
        "close_z60", "close_p60", "close_z252", "close_p252",
        "amp_z60", "amp_p60", "amp_z252", "amp_p252",
    ]].copy()
    df_out.to_csv(csv_path, index=False, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())