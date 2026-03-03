#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_roll25_json_charts.py

Long-series charts from roll25.json (list of daily rows: date, close, high, low, trade_value, change).

Design goal:
- "History / trend" only (lines & rolling metrics).
- Output PNGs + chart_manifest.json (audit-first).
- Provide chart_ready.csv for downstream usage.

Computed fields (best-effort; skips missing/null):
- pct_change: close / prev_close - 1
- amplitude_pct: (high - low) / prev_close * 100
  (matches your stats_latest.json note: amplitude needs high/low + D-1 close)
- vol_multiplier_20: trade_value / rolling_mean_20(trade_value), with min_periods=15
- zscore_winN: (x - mean) / std over rolling window N (std ddof=0), min_periods=N
- pctl_winN: rolling percentile of "today's x" within last N points:
    p = mean(window_values <= last_value) * 100
  (ties counted as <=)

Outputs (to --out_dir):
- 01_roll25_close.png
- 02_roll25_trade_value.png
- 03_roll25_vol_multiplier_20.png
- 04_roll25_trade_value_z60_z252.png        (skips lines if insufficient history)
- 05_roll25_trade_value_p60_p252.png        (skips lines if insufficient history)
- 06_roll25_pct_change.png
- 07_roll25_amplitude_pct.png
- roll25_chart_ready.csv
- chart_manifest.json

Dependencies:
- matplotlib, numpy, pandas
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

try:
    import pandas as pd  # noqa: E402
except Exception as e:  # pragma: no cover
    raise SystemExit("pandas is required for this script. Please `pip install pandas numpy matplotlib`.") from e


TZ_NAME_DEFAULT = "Asia/Taipei"
MANIFEST_SCHEMA = "chart_manifest_v1"
SCRIPT_FINGERPRINT = "make_roll25_json_charts@v1.longseries_plus_manifest"


# -----------------------------
# Helpers (audit-first)
# -----------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, list):
        raise ValueError("roll25.json must be a JSON list of rows.")
    out: List[Dict[str, Any]] = []
    for x in obj:
        if isinstance(x, dict):
            out.append(x)
    return out


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def set_font_defaults() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Noto Sans CJK TC",
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "Microsoft JhengHei",
        "PingFang TC",
        "Heiti TC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def save_fig(fig: plt.Figure, out_path: Path, dpi: int) -> Dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    b = out_path.read_bytes()
    w_in, h_in = fig.get_size_inches()
    return {
        "file": out_path.name,
        "path": str(out_path),
        "sha256": sha256_bytes(b),
        "dpi": dpi,
        "size_inches": [float(w_in), float(h_in)],
    }


# -----------------------------
# Rolling stats
# -----------------------------
def rolling_zscore(s: pd.Series, window: int) -> pd.Series:
    mu = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std(ddof=0)
    return (s - mu) / sd


def rolling_percentile_last(s: pd.Series, window: int) -> pd.Series:
    # p = mean(window_values <= last_value) * 100
    def _p(arr: np.ndarray) -> float:
        if arr.size == 0:
            return np.nan
        last = arr[-1]
        return float(np.mean(arr <= last) * 100.0)

    return s.rolling(window, min_periods=window).apply(_p, raw=True)


# -----------------------------
# Charts
# -----------------------------
def _format_date_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5)


def chart_close(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    d = df.dropna(subset=["close"])
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.plot(d["date"], d["close"])
    ax.set_title(f"TWSE Close (roll25.json) | last={d['date'].max().date().isoformat()}")
    ax.set_ylabel("Close")
    _format_date_axis(ax)
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "01_roll25_close.png", dpi=dpi)
    meta["title"] = "Close line"
    return meta


def chart_trade_value(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    d = df.dropna(subset=["trade_value"])
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    # Scale to trillion for readability (no color styling)
    ax.plot(d["date"], d["trade_value"] / 1e12)
    ax.set_title(f"Trade Value (TWD trillion) | last={d['date'].max().date().isoformat()}")
    ax.set_ylabel("TWD (trillion)")
    _format_date_axis(ax)
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "02_roll25_trade_value.png", dpi=dpi)
    meta["title"] = "Trade value line (trillion TWD)"
    return meta


def chart_vol_multiplier(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    d = df.dropna(subset=["vol_multiplier_20"])
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.plot(d["date"], d["vol_multiplier_20"])
    ax.axhline(1.5, linewidth=1.0)  # threshold line (default style)
    ax.set_title("Vol multiplier (trade_value / 20D mean) | threshold=1.5")
    ax.set_ylabel("Multiplier")
    _format_date_axis(ax)
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "03_roll25_vol_multiplier_20.png", dpi=dpi)
    meta["title"] = "Vol multiplier 20D"
    return meta


def chart_trade_value_z(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    cols = ["trade_value_z60", "trade_value_z252"]
    d = df.dropna(subset=cols, how="all")
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    if df["trade_value_z60"].notna().any():
        ax.plot(df["date"], df["trade_value_z60"], label="z60")
    if df["trade_value_z252"].notna().any():
        ax.plot(df["date"], df["trade_value_z252"], label="z252")
    ax.axhline(0.0, linewidth=1.0)
    ax.set_title("Trade value z-score (rolling)")
    ax.set_ylabel("z")
    _format_date_axis(ax)
    ax.legend(loc="upper left")
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "04_roll25_trade_value_z60_z252.png", dpi=dpi)
    meta["title"] = "Trade value z60 & z252"
    return meta


def chart_trade_value_p(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    cols = ["trade_value_p60", "trade_value_p252"]
    d = df.dropna(subset=cols, how="all")
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    if df["trade_value_p60"].notna().any():
        ax.plot(df["date"], df["trade_value_p60"], label="p60")
    if df["trade_value_p252"].notna().any():
        ax.plot(df["date"], df["trade_value_p252"], label="p252")
    ax.set_ylim(0, 100)
    ax.set_title("Trade value percentile (rolling)")
    ax.set_ylabel("Percentile (0-100)")
    _format_date_axis(ax)
    ax.legend(loc="upper left")
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "05_roll25_trade_value_p60_p252.png", dpi=dpi)
    meta["title"] = "Trade value p60 & p252"
    return meta


def chart_pct_change(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    d = df.dropna(subset=["pct_change"])
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.bar(d["date"], d["pct_change"] * 100.0, width=1.0)
    ax.axhline(0.0, linewidth=1.0)
    ax.set_title("Daily % change (computed from close)")
    ax.set_ylabel("%")
    _format_date_axis(ax)
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "06_roll25_pct_change.png", dpi=dpi)
    meta["title"] = "Daily pct_change (bar)"
    return meta


def chart_amplitude(df: pd.DataFrame, out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    d = df.dropna(subset=["amplitude_pct"])
    if d.empty:
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.plot(d["date"], d["amplitude_pct"])
    ax.set_title("Amplitude % = (high-low)/prev_close*100 (best-effort)")
    ax.set_ylabel("%")
    _format_date_axis(ax)
    fig.tight_layout()
    meta = save_fig(fig, out_dir / "07_roll25_amplitude_pct.png", dpi=dpi)
    meta["title"] = "Amplitude % line"
    return meta


def write_chart_ready_csv(df: pd.DataFrame, out_dir: Path) -> Path:
    out_path = out_dir / "roll25_chart_ready.csv"
    cols = [
        "date",
        "close",
        "trade_value",
        "pct_change",
        "amplitude_pct",
        "vol_multiplier_20",
        "trade_value_z60",
        "trade_value_z252",
        "trade_value_p60",
        "trade_value_p252",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    df_out = df.copy()
    df_out["date"] = df_out["date"].dt.date.astype(str)
    df_out[cols].to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def build_manifest(
    out_dir: Path,
    input_json_path: Path,
    data_as_of: str,
    charts_meta: List[Dict[str, Any]],
    warnings: List[str],
) -> Dict[str, Any]:
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "generated_at_utc": utc_now_iso(),
        "timezone": TZ_NAME_DEFAULT,
        "data_as_of": data_as_of,
        "input_files": {
            "roll25_json": str(input_json_path),
            "roll25_json_sha256": sha256_file(input_json_path),
        },
        "warnings": sorted(list(dict.fromkeys([str(x) for x in warnings]))),
        "charts": charts_meta,
    }
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_json", required=True, help="Path to roll25.json")
    ap.add_argument("--out_dir", required=True, help="Output directory for PNGs + manifest")
    ap.add_argument("--dpi", default="160", help="PNG dpi (default 160 for 1280x720 at 8x4.5)")
    args = ap.parse_args()

    set_font_defaults()

    in_path = Path(args.in_json)
    out_dir = Path(args.out_dir)
    dpi = int(args.dpi)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_json_list(in_path)
    if not rows:
        dump_json(out_dir / "chart_manifest.json", build_manifest(out_dir, in_path, "N/A", [], ["no_rows_in_roll25_json"]))
        return 0

    df = pd.DataFrame(rows)

    # normalize columns
    if "date" not in df.columns:
        raise ValueError("roll25.json rows must include 'date' (YYYY-MM-DD).")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    for col in ["close", "trade_value", "high", "low"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    # computed fields
    df["prev_close"] = df["close"].shift(1)
    df["pct_change"] = (df["close"] / df["prev_close"]) - 1.0

    # amplitude needs (high, low, prev_close)
    df["amplitude_pct"] = (df["high"] - df["low"]) / df["prev_close"] * 100.0

    # vol_multiplier_20: trade_value / rolling_mean_20
    tv = df["trade_value"]
    tv_mean20 = tv.rolling(20, min_periods=15).mean()
    df["vol_multiplier_20"] = tv / tv_mean20

    # rolling z/p for trade_value
    df["trade_value_z60"] = rolling_zscore(tv, 60)
    df["trade_value_z252"] = rolling_zscore(tv, 252)
    df["trade_value_p60"] = rolling_percentile_last(tv, 60)
    df["trade_value_p252"] = rolling_percentile_last(tv, 252)

    # data_as_of = last date in file
    data_as_of = df["date"].max().date().isoformat()

    charts_meta: List[Dict[str, Any]] = []
    warnings: List[str] = []

    m1 = chart_close(df, out_dir, dpi)
    if m1:
        charts_meta.append(m1)
    else:
        warnings.append("close_chart_skipped_no_data")

    m2 = chart_trade_value(df, out_dir, dpi)
    if m2:
        charts_meta.append(m2)
    else:
        warnings.append("trade_value_chart_skipped_no_data")

    m3 = chart_vol_multiplier(df, out_dir, dpi)
    if m3:
        charts_meta.append(m3)
    else:
        warnings.append("vol_multiplier_chart_skipped_no_data_or_insufficient_history")

    m4 = chart_trade_value_z(df, out_dir, dpi)
    if m4:
        charts_meta.append(m4)
    else:
        warnings.append("z_chart_skipped_insufficient_history")

    m5 = chart_trade_value_p(df, out_dir, dpi)
    if m5:
        charts_meta.append(m5)
    else:
        warnings.append("p_chart_skipped_insufficient_history")

    m6 = chart_pct_change(df, out_dir, dpi)
    if m6:
        charts_meta.append(m6)
    else:
        warnings.append("pct_change_chart_skipped_no_data")

    m7 = chart_amplitude(df, out_dir, dpi)
    if m7:
        charts_meta.append(m7)
    else:
        warnings.append("amplitude_chart_skipped_no_data")

    # chart_ready.csv
    csv_path = write_chart_ready_csv(df, out_dir)
    charts_meta.append(
        {
            "file": csv_path.name,
            "path": str(csv_path),
            "sha256": sha256_file(csv_path),
            "title": "roll25_chart_ready.csv (time series table)",
        }
    )

    manifest = build_manifest(out_dir, in_path, data_as_of, charts_meta, warnings)
    dump_json(out_dir / "chart_manifest.json", manifest)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())