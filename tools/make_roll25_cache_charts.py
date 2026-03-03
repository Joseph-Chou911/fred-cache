#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_roll25_cache_charts.py

Generate chart_ready.csv + standard charts for roll25_cache (TWSE turnover).

Template-compatible with make_market_cache_charts.py:
- No in-axes annotation boxes (avoid covering data + avoid duplicate notes).
- Legend moved to BELOW (figure-level) when needed.
- Long audit notes placed BELOW (figure-level bottom_note).
- Watermark stays at bottom-right.
- Audit-first: if data missing/insufficient -> NA (no guessing).

Inputs:
- Prefer: <CACHE_DIR>/roll25.json (points, newest-first)
- Fallback: <CACHE_DIR>/latest_report.json with embedded "cache_roll25" points

Expected roll25.json fields (your example):
- date (YYYY-MM-DD)
- close (float)
- change (float; point change, Close - PrevClose)
- trade_value (int; turnover TWD)
- high (float)
- low (float)

Outputs (to --out):
- 00_font_smoketest.png
- chart_ready.csv
- 01_rank252_overview.png
- 02_rank60_jump_abs.png
- 03_z60_vs_rank252_scatter.png
- 04_ret1_abs_pct.png
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt


# -----------------------------
# Utilities (audit-first)
# -----------------------------

def read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.strip()
            if x == "" or x.upper() == "NA":
                return None
            x = x.replace(",", "")
        return float(x)
    except Exception:
        return None


def parse_date_any(s: Any) -> Optional[pd.Timestamp]:
    if s is None:
        return None
    if isinstance(s, (pd.Timestamp, datetime)):
        return pd.Timestamp(s).normalize()
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return pd.to_datetime(datetime.strptime(t, fmt)).normalize()
        except Exception:
            pass

    try:
        return pd.to_datetime(t).normalize()
    except Exception:
        return None


def tie_aware_percentile(values: np.ndarray, v: float) -> float:
    """
    Percentile in [0,100] using: (less + 0.5*equal)/n * 100
    """
    n = len(values)
    if n == 0:
        return float("nan")
    less = np.sum(values < v)
    equal = np.sum(values == v)
    return 100.0 * (less + 0.5 * equal) / n


def zscore_ddof0(values: np.ndarray, v: float) -> float:
    """
    z = (v - mean)/std, population std (ddof=0).
    If std=0 -> 0.
    """
    if len(values) == 0:
        return float("nan")
    mu = float(np.mean(values))
    sd = float(np.std(values, ddof=0))
    if sd == 0.0:
        return 0.0
    return (v - mu) / sd


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def fig_watermark(fig: plt.Figure, text: str) -> None:
    fig.text(0.995, 0.015, text, ha="right", va="bottom", fontsize=8, alpha=0.45)


def fig_bottom_note(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.015, text, ha="left", va="bottom", fontsize=8, alpha=0.85)


# -----------------------------
# Data parsing
# -----------------------------

@dataclass
class Meta:
    generated_at_utc: str
    generated_at_local: str
    timezone: str
    used_date: str
    used_date_status: str
    data_age_days: Optional[int]
    freshness_ok: Optional[bool]
    mode: Optional[str]
    ohlc_status: Optional[str]
    source: str


def deep_find_first(d: Any, keys: List[str]) -> Optional[Any]:
    """
    Find first matching key (case-insensitive) anywhere in nested dict/list.
    """
    keyset = {k.lower() for k in keys}

    def _walk(x: Any) -> Optional[Any]:
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower() in keyset:
                    return v
            for _, v in x.items():
                got = _walk(v)
                if got is not None:
                    return got
        elif isinstance(x, list):
            for it in x:
                got = _walk(it)
                if got is not None:
                    return got
        return None

    return _walk(d)


def load_points(cache_dir: Path) -> Tuple[List[Dict[str, Any]], Meta]:
    """
    Load roll25 points (newest-first) and meta.
    Prefer roll25.json; fallback latest_report.json embedded cache_roll25.
    """
    latest_report_path = cache_dir / "latest_report.json"
    roll25_path = cache_dir / "roll25.json"

    latest_report = None
    if latest_report_path.exists():
        latest_report = read_json(latest_report_path)

    if roll25_path.exists():
        points = read_json(roll25_path)
        if not isinstance(points, list) or len(points) == 0:
            raise ValueError(f"{roll25_path} exists but is empty or not a list.")
        source = "roll25.json"
    else:
        if latest_report is None:
            raise FileNotFoundError(f"Neither {roll25_path} nor {latest_report_path} exists.")
        points = deep_find_first(latest_report, ["cache_roll25", "roll25_points", "points"])
        if points is None or not isinstance(points, list) or len(points) == 0:
            raise ValueError("Fallback failed: latest_report.json has no embedded roll25 points (cache_roll25).")
        source = "latest_report.json::cache_roll25"

    tz = deep_find_first(latest_report, ["timezone", "tz"]) if latest_report else None
    tz = str(tz) if tz else "Asia/Taipei"

    used_date = deep_find_first(latest_report, ["as_of_data_date", "UsedDate", "used_date"]) if latest_report else None
    used_date = str(used_date) if used_date else ""

    used_date_status = deep_find_first(latest_report, ["UsedDateStatus", "used_date_status"]) if latest_report else None
    used_date_status = str(used_date_status) if used_date_status else "NA"

    data_age_days = deep_find_first(latest_report, ["data_age_days", "freshness_age_days"]) if latest_report else None
    try:
        data_age_days = int(data_age_days) if data_age_days is not None else None
    except Exception:
        data_age_days = None

    freshness_ok = deep_find_first(latest_report, ["freshness_ok"]) if latest_report else None
    if isinstance(freshness_ok, str):
        freshness_ok = freshness_ok.strip().lower() in ("true", "1", "yes", "ok")

    mode = deep_find_first(latest_report, ["mode"]) if latest_report else None
    mode = str(mode) if mode is not None else None

    ohlc_status = deep_find_first(latest_report, ["ohlc_status", "OhlcStatus"]) if latest_report else None
    ohlc_status = str(ohlc_status) if ohlc_status is not None else None

    gen_utc = deep_find_first(latest_report, ["generated_at_utc", "RUN_TS_UTC", "run_ts_utc"]) if latest_report else None
    gen_utc = str(gen_utc) if gen_utc else now_utc_iso()

    gen_local = deep_find_first(latest_report, ["generated_at_local"]) if latest_report else None
    gen_local = str(gen_local) if gen_local else ""

    meta = Meta(
        generated_at_utc=gen_utc,
        generated_at_local=gen_local,
        timezone=tz,
        used_date=used_date,
        used_date_status=used_date_status,
        data_age_days=data_age_days,
        freshness_ok=freshness_ok if isinstance(freshness_ok, bool) else None,
        mode=mode,
        ohlc_status=ohlc_status,
        source=source,
    )
    return points, meta


def points_to_df(points: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize points into a dataframe with columns:
    date, turnover_twd, close, change, prev_close, pct_change_close, amplitude_pct

    Audit-first:
    - Drop rows without parseable date (no silent coercion).
    - Sort ascending for plotting & strict adjacency computations.
    """
    date_keys = ["date", "Date", "d", "trade_date", "TradeDate", "交易日期", "日期"]
    turnover_keys = [
        "turnover_twd", "TURNOVER_TWD", "trade_value", "TradeValue", "tradeValue",
        "成交金額", "成交金額(元)", "成交金額(新台幣)", "trade_value_twd"
    ]
    close_keys = ["close", "Close", "CLOSE", "收盤價", "收盤", "close_price"]
    change_keys = ["change", "Change", "chg", "漲跌", "漲跌點數", "change_pts"]
    pct_keys = [
        "pct_change", "pct_change_close", "PCT_CHANGE_CLOSE", "change_pct", "ChangePercent",
        "漲跌百分比", "漲跌幅(%)", "報酬率"
    ]
    amp_keys = ["amplitude_pct", "AMPLITUDE_PCT", "amplitude", "振幅", "AmplitudePct"]
    high_keys = ["high", "High", "最高價", "最高"]
    low_keys = ["low", "Low", "最低價", "最低"]
    prev_close_keys = ["prev_close", "PrevClose", "前收盤價", "昨收", "previous_close"]

    rows: List[Dict[str, Any]] = []
    for p in points:
        if not isinstance(p, dict):
            continue

        dt = None
        for k in date_keys:
            if k in p:
                dt = parse_date_any(p.get(k))
                break

        tv = None
        for k in turnover_keys:
            if k in p:
                tv = safe_float(p.get(k))
                break

        c = None
        for k in close_keys:
            if k in p:
                c = safe_float(p.get(k))
                break

        chg = None
        for k in change_keys:
            if k in p:
                chg = safe_float(p.get(k))
                break

        pc = None
        for k in pct_keys:
            if k in p:
                pc = safe_float(p.get(k))
                break

        amp = None
        for k in amp_keys:
            if k in p:
                amp = safe_float(p.get(k))
                break

        hi = None
        lo = None
        prev_c = None

        for k in high_keys:
            if k in p:
                hi = safe_float(p.get(k))
                break
        for k in low_keys:
            if k in p:
                lo = safe_float(p.get(k))
                break
        for k in prev_close_keys:
            if k in p:
                prev_c = safe_float(p.get(k))
                break

        # If prev_close missing but close+change exists, derive prev_close = close - change
        if prev_c is None and c is not None and chg is not None:
            prev_c = c - chg

        rows.append(
            {
                "date": dt,
                "turnover_twd": tv,
                "close": c,
                "change": chg,
                "prev_close": prev_c,
                "pct_change_close": pc,
                "amplitude_pct": amp,
                "high": hi,
                "low": lo,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No usable rows parsed from points (df is empty).")

    df = df[~df["date"].isna()].copy()
    if df.empty:
        raise ValueError("All rows missing parseable date; cannot proceed.")

    # roll25.json is newest-first; sort ascending for strict adjacency + plotting
    df = df.sort_values("date").reset_index(drop=True)

    # If prev_close still NA, fill from strict adjacency previous close in ascending order
    df["prev_close"] = df["prev_close"].where(df["prev_close"].notna(), df["close"].shift(1))

    # Derive pct_change_close if missing and close+prev_close available
    if df["pct_change_close"].isna().all() and df["close"].notna().sum() >= 2:
        denom = df["prev_close"]
        ok = denom.notna() & (denom != 0) & df["close"].notna()
        df.loc[ok, "pct_change_close"] = 100.0 * (df.loc[ok, "close"] / denom.loc[ok] - 1.0)

    # Derive amplitude_pct if missing and high/low exists
    # Policy: denominator prefer prev_close (= close - change) when available; else fallback close.
    if df["amplitude_pct"].isna().all():
        denom = df["prev_close"].where(df["prev_close"].notna(), df["close"])
        ok = df["high"].notna() & df["low"].notna() & denom.notna() & (denom != 0)
        df.loc[ok, "amplitude_pct"] = 100.0 * (df.loc[ok, "high"] - df.loc[ok, "low"]) / denom.loc[ok]

    return df


# -----------------------------
# Metrics (Z/P table compatible)
# -----------------------------

def compute_metrics(df: pd.DataFrame, min_points_20: int = 15) -> pd.DataFrame:
    """
    Compute market_cache-like table for latest day:
    series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence

    Notes:
    - z-score uses ddof=0 population std.
    - percentile is tie-aware (less + 0.5*equal).
    - zΔ60/pΔ60 computed on ABS 1D change vs last 60 ABS deltas (strict adjacency).
    - ret1% uses strict adjacency simple return.
    - Suppression policy (audit-friendly):
      PCT_CHANGE_CLOSE / AMPLITUDE_PCT / VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60.
    """
    df = df.copy()

    for col in ["turnover_twd", "close", "pct_change_close", "amplitude_pct", "prev_close"]:
        if col not in df.columns:
            df[col] = np.nan

    # vol_multiplier_20 = today_trade_value / avg(trade_value_last20_before_today)
    tv = df["turnover_twd"].astype(float)
    roll_mean_20_prev = tv.shift(1).rolling(window=20, min_periods=min_points_20).mean()
    df["vol_multiplier_20"] = tv / roll_mean_20_prev

    i = len(df) - 1
    if i < 1:
        raise ValueError("Need at least 2 rows for strict adjacency metrics (ret1/Δ).")

    latest = df.iloc[i]
    prev = df.iloc[i - 1]

    def window_vals(series: pd.Series, n: int) -> np.ndarray:
        # Keep time order; take trailing n
        vals = series.to_numpy(dtype=float)
        vals = vals[~np.isnan(vals)]
        if len(vals) == 0:
            return np.array([], dtype=float)
        return vals[-n:] if len(vals) >= n else vals

    def latest_zp(series: pd.Series, n: int, v: float) -> Tuple[float, float, str]:
        vals = window_vals(series, n)
        # conservative minimum: at least 10 points (or n if n<10)
        need = min(n, 10)
        if len(vals) < need:
            return (float("nan"), float("nan"), "DOWNGRADED")
        return (zscore_ddof0(vals, v), tie_aware_percentile(vals, v), "OK")

    def latest_delta_zp(series: pd.Series, n: int, v_today: float, v_prev: float) -> Tuple[float, float, str]:
        s = series.astype(float)
        deltas = np.abs(s - s.shift(1)).to_numpy(dtype=float)
        deltas = deltas[~np.isnan(deltas)]
        if len(deltas) == 0:
            return (float("nan"), float("nan"), "DOWNGRADED")
        deltas_win = deltas[-n:] if len(deltas) >= n else deltas
        need = min(n, 10)
        if len(deltas_win) < need:
            return (float("nan"), float("nan"), "DOWNGRADED")
        d_today = abs(v_today - v_prev)
        return (zscore_ddof0(deltas_win, d_today), tie_aware_percentile(deltas_win, d_today), "OK")

    def ret1_pct(v_today: float, v_prev: float) -> float:
        if math.isnan(v_today) or math.isnan(v_prev) or v_prev == 0:
            return float("nan")
        return 100.0 * (v_today / v_prev - 1.0)

    # Series definitions
    series_specs = [
        ("TURNOVER_TWD", "turnover_twd", True, True),
        ("CLOSE", "close", True, True),
        ("PCT_CHANGE_CLOSE", "pct_change_close", False, False),
        ("AMPLITUDE_PCT", "amplitude_pct", False, False),
        ("VOL_MULTIPLIER_20", "vol_multiplier_20", False, False),
    ]

    out_rows: List[Dict[str, Any]] = []
    for name, col, allow_ret1, allow_delta in series_specs:
        v = safe_float(latest.get(col))
        v = float("nan") if v is None else float(v)

        z60, p60, c60 = latest_zp(df[col], 60, v)
        z252, p252, c252 = latest_zp(df[col], 252, v)

        if allow_delta:
            v_prev = safe_float(prev.get(col))
            v_prev = float("nan") if v_prev is None else float(v_prev)
            zD60, pD60, cd = latest_delta_zp(df[col], 60, v, v_prev)
        else:
            zD60, pD60, cd = (float("nan"), float("nan"), "OK")

        if allow_ret1:
            v_prev = safe_float(prev.get(col))
            v_prev = float("nan") if v_prev is None else float(v_prev)
            r1 = ret1_pct(v, v_prev)
        else:
            r1 = float("nan")

        conf = "OK"
        if (c60 != "OK") or (c252 != "OK") or (allow_delta and cd != "OK"):
            conf = "DOWNGRADED"

        out_rows.append(
            {
                "series": name,
                "value": v,
                "z60": z60,
                "p60": p60,
                "z252": z252,
                "p252": p252,
                "zΔ60": zD60,
                "pΔ60": pD60,
                "ret1%": r1,
                "confidence": conf,
            }
        )

    return pd.DataFrame(out_rows)


# -----------------------------
# Plotting (template-compatible)
# -----------------------------

def font_smoketest(out_png: Path) -> None:
    fig = plt.figure(figsize=(8, 2.2), dpi=160)
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.01, 0.72, "Font smoketest: 中文 / English / 12345", fontsize=14)
    ax.text(0.01, 0.35, "台股成交熱度、振幅、漲跌幅、20日放大倍數", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def short_label(series: str) -> str:
    m = {
        "TURNOVER_TWD": "TURNOVER",
        "CLOSE": "CLOSE",
        "PCT_CHANGE_CLOSE": "PCT_CHG",
        "AMPLITUDE_PCT": "AMPL",
        "VOL_MULTIPLIER_20": "VOLx20",
    }
    return m.get(series, series)


def make_rank252_overview(df_m: pd.DataFrame, out_png: Path, bottom: str, watermark: str) -> None:
    d = df_m.copy()
    d["label"] = d["series"].map(short_label)

    fig = plt.figure(figsize=(10, 5.2), dpi=160)
    ax = fig.add_subplot(111)

    x = np.arange(len(d))
    y = d["p252"].to_numpy(dtype=float)

    ax.bar(x, y)
    ax.set_xticks(x)
    ax.set_xticklabels(d["label"].tolist(), rotation=0)
    ax.set_ylim(0, 100)
    ax.set_ylabel("p252 (percentile)")
    ax.set_title("Roll25 Overview — p252 (Position in last ~252 trading days)")

    for xi, yi in zip(x, y):
        if not math.isnan(yi):
            ax.text(xi, yi + 1.2, f"{yi:.2f}", ha="center", va="bottom", fontsize=9)

    fig_bottom_note(fig, bottom)
    fig_watermark(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_rank60_jump_abs(df_m: pd.DataFrame, out_png: Path, bottom: str, watermark: str) -> None:
    d = df_m.copy()
    d = d[~d["pΔ60"].isna()].copy()

    if d.empty:
        fig = plt.figure(figsize=(10, 4.8), dpi=160)
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.01, 0.6, "No pΔ60 data available (all NA).", fontsize=14)
        fig_bottom_note(fig, bottom)
        fig_watermark(fig, watermark)
        fig.tight_layout(rect=[0, 0.06, 1, 1])
        fig.savefig(out_png, bbox_inches="tight")
        plt.close(fig)
        return

    d["label"] = d["series"].map(short_label)

    fig = plt.figure(figsize=(10, 5.2), dpi=160)
    ax = fig.add_subplot(111)
    x = np.arange(len(d))
    y = d["pΔ60"].to_numpy(dtype=float)

    ax.bar(x, y)
    ax.set_xticks(x)
    ax.set_xticklabels(d["label"].tolist(), rotation=0)
    ax.set_ylim(0, 100)
    ax.set_ylabel("pΔ60 (percentile of |Δ1D| vs last 60)")
    ax.set_title("Jump Rank — pΔ60 (Abs 1-day change vs last 60 trading days)")

    for xi, yi in zip(x, y):
        if not math.isnan(yi):
            ax.text(xi, yi + 1.2, f"{yi:.1f}", ha="center", va="bottom", fontsize=9)

    fig_bottom_note(fig, bottom)
    fig_watermark(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_z60_vs_rank252_scatter(df_m: pd.DataFrame, out_png: Path, bottom: str, watermark: str) -> None:
    d = df_m.copy()
    d["label"] = d["series"].map(short_label)

    fig = plt.figure(figsize=(10, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    # scatter each point; label via legend (no in-axes annotations)
    for _, row in d.iterrows():
        x = float(row["p252"]) if not pd.isna(row["p252"]) else float("nan")
        y = float(row["z60"]) if not pd.isna(row["z60"]) else float("nan")
        if math.isnan(x) or math.isnan(y):
            continue
        ax.scatter([x], [y], label=row["label"])

    ax.set_xlim(0, 100)
    ax.set_xlabel("p252 (percentile)")
    ax.set_ylabel("z60 (z-score)")
    ax.set_title("Scatter — z60 vs p252 (Roll25 key series)")

    handles, labels = ax.get_legend_handles_labels()
    if labels:
        fig.legend(handles, labels, loc="lower center", ncol=min(5, len(labels)),
                   frameon=False, bbox_to_anchor=(0.5, 0.01))

    fig_bottom_note(fig, bottom)
    fig_watermark(fig, watermark)
    fig.tight_layout(rect=[0, 0.10, 1, 1])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_ret1_abs_pct(df_m: pd.DataFrame, out_png: Path, bottom: str, watermark: str) -> None:
    d = df_m.copy()
    d = d[~d["ret1%"].isna()].copy()

    if d.empty:
        fig = plt.figure(figsize=(10, 4.8), dpi=160)
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.01, 0.6, "No ret1% data available (all NA).", fontsize=14)
        fig_bottom_note(fig, bottom)
        fig_watermark(fig, watermark)
        fig.tight_layout(rect=[0, 0.06, 1, 1])
        fig.savefig(out_png, bbox_inches="tight")
        plt.close(fig)
        return

    d["label"] = d["series"].map(short_label)

    fig = plt.figure(figsize=(10, 5.2), dpi=160)
    ax = fig.add_subplot(111)

    x = np.arange(len(d))
    y = d["ret1%"].to_numpy(dtype=float)

    ax.bar(x, np.abs(y))
    ax.set_xticks(x)
    ax.set_xticklabels(d["label"].tolist(), rotation=0)
    ax.set_ylabel("|ret1%| (abs 1-day change, %)")
    ax.set_title("Abs 1-day change — |ret1%| (only for non-suppressed series)")

    for xi, yi in zip(x, y):
        if not math.isnan(yi):
            ax.text(xi, abs(yi) + 0.25, f"{yi:.3f}%", ha="center", va="bottom", fontsize=9)

    fig_bottom_note(fig, bottom)
    fig_watermark(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="roll25_cache", help="roll25 cache directory (default: roll25_cache)")
    ap.add_argument("--out", default="out_roll25_charts", help="output directory")
    ap.add_argument("--min-points-volmult", type=int, default=15,
                    help="min points for vol_multiplier_20 avg(last20_before_today) (default: 15)")
    ap.add_argument("--watermark", default="roll25_cache charts", help="watermark text")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out)
    ensure_dir(out_dir)

    points, meta = load_points(cache_dir)
    df_points = points_to_df(points)

    # Determine effective used_date (prefer meta, fallback latest df date)
    used_dt = parse_date_any(meta.used_date) if meta.used_date else None
    latest_dt = pd.Timestamp(df_points["date"].iloc[-1]).normalize()
    if used_dt is None:
        meta.used_date = latest_dt.strftime("%Y-%m-%d")
    else:
        # If meta used_date mismatches latest date, keep meta but show mismatch in bottom note (audit visibility)
        pass

    # Build metrics table
    df_m = compute_metrics(df_points, min_points_20=args.min_points_volmult)

    # Save chart_ready.csv
    chart_csv = out_dir / "chart_ready.csv"
    df_m.to_csv(chart_csv, index=False, encoding="utf-8")

    # Bottom note & watermark
    mismatch = ""
    if meta.used_date and meta.used_date != latest_dt.strftime("%Y-%m-%d"):
        mismatch = f" | latest_row_date={latest_dt.strftime('%Y-%m-%d')} (mismatch)"

    bottom = (
        f"UsedDate={meta.used_date} ({meta.used_date_status})"
        f"{mismatch}; age_days={meta.data_age_days if meta.data_age_days is not None else 'NA'}; "
        f"freshness_ok={meta.freshness_ok if meta.freshness_ok is not None else 'NA'}; "
        f"mode={meta.mode if meta.mode else 'NA'}; ohlc={meta.ohlc_status if meta.ohlc_status else 'NA'}; "
        f"src={meta.source}; gen_utc={meta.generated_at_utc}"
    )

    # 00 smoketest
    font_smoketest(out_dir / "00_font_smoketest.png")

    # Charts (template naming)
    make_rank252_overview(df_m, out_dir / "01_rank252_overview.png", bottom, args.watermark)
    make_rank60_jump_abs(df_m, out_dir / "02_rank60_jump_abs.png", bottom, args.watermark)
    make_z60_vs_rank252_scatter(df_m, out_dir / "03_z60_vs_rank252_scatter.png", bottom, args.watermark)
    make_ret1_abs_pct(df_m, out_dir / "04_ret1_abs_pct.png", bottom, args.watermark)

    print(f"[OK] out_dir={out_dir}")
    print(f"[OK] wrote: {chart_csv}")
    print(f"[OK] wrote: 00..04 pngs")
    print(f"[INFO] points_rows={len(df_points)} date_range={df_points['date'].iloc[0].date()}..{df_points['date'].iloc[-1].date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())