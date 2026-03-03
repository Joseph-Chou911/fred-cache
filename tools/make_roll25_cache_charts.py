#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_roll25_cache_charts.py (PUBLIC-FACING)

Generate chart_ready.csv + standard charts for roll25_cache (TWSE turnover).
Public-facing tweaks:
- Avoid "Roll25" wording on chart titles (keep it internal only).
- Use plain-language titles/axes; keep (p252/z60/pΔ60) in parentheses.
- Footer is SHORT (no long definitions) to avoid overlap on 1920px exports.
- Watermark moved to TOP-RIGHT (prevents collision with footer).
- Scatter legend placed ABOVE footer (figure-level) to avoid overlap.
- Bar charts: add headroom (ylim up to 105) so top labels don't collide.
- 1-day % change chart uses SIGNED bars (keeps +/-); y-axis always includes 0 with small headroom.

Inputs:
- Prefer: <CACHE_DIR>/roll25.json (points, newest-first)
- Fallback: <CACHE_DIR>/latest_report.json with embedded "cache_roll25" points

Outputs (to --out):
- 00_font_smoketest.png
- chart_ready.csv
- 01_rank252_overview.png
- 02_rank60_jump_abs.png
- 03_z60_vs_rank252_scatter.png
- 04_ret1_abs_pct.png   (NOTE: now SIGNED; filename kept for backward compatibility)
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


def fig_watermark_topright(fig: plt.Figure, text: str) -> None:
    fig.text(0.995, 0.995, text, ha="right", va="top", fontsize=9, alpha=0.35)


def fig_footer_short(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.012, text, ha="left", va="bottom", fontsize=9, alpha=0.85)


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

    df = df.sort_values("date").reset_index(drop=True)

    df["prev_close"] = df["prev_close"].where(df["prev_close"].notna(), df["close"].shift(1))

    if df["pct_change_close"].isna().all() and df["close"].notna().sum() >= 2:
        denom = df["prev_close"]
        ok = denom.notna() & (denom != 0) & df["close"].notna()
        df.loc[ok, "pct_change_close"] = 100.0 * (df.loc[ok, "close"] / denom.loc[ok] - 1.0)

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
    Public series names:
    - TURNOVER: turnover_twd
    - INDEX: close
    - INDEX_%CHG: pct_change_close
    - AMPL_%: amplitude_pct
    - TURNOVERx20: vol_multiplier_20

    Table:
    series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence
    """
    df = df.copy()

    for col in ["turnover_twd", "close", "pct_change_close", "amplitude_pct", "prev_close"]:
        if col not in df.columns:
            df[col] = np.nan

    tv = df["turnover_twd"].astype(float)
    roll_mean_20_prev = tv.shift(1).rolling(window=20, min_periods=min_points_20).mean()
    df["vol_multiplier_20"] = tv / roll_mean_20_prev

    i = len(df) - 1
    if i < 1:
        raise ValueError("Need at least 2 rows for strict adjacency metrics (ret1/Δ).")

    latest = df.iloc[i]
    prev = df.iloc[i - 1]

    def window_vals(series: pd.Series, n: int) -> np.ndarray:
        vals = series.to_numpy(dtype=float)
        vals = vals[~np.isnan(vals)]
        return vals[-n:] if len(vals) >= n else vals

    def latest_zp(series: pd.Series, n: int, v: float) -> Tuple[float, float, str]:
        vals = window_vals(series, n)
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

    series_specs = [
        ("TURNOVER", "turnover_twd", True, True),
        ("INDEX", "close", True, True),
        ("INDEX_%CHG", "pct_change_close", False, False),
        ("AMPL_%", "amplitude_pct", False, False),
        ("TURNOVERx20", "vol_multiplier_20", False, False),
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
# Plotting (public-facing)
# -----------------------------

def font_smoketest(out_png: Path) -> None:
    fig = plt.figure(figsize=(8, 2.2), dpi=160)
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.01, 0.72, "Font smoketest: 中文 / English / 12345", fontsize=14)
    ax.text(0.01, 0.35, "TWSE turnover / index / amplitude / ranks", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_rank252_overview(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    d = df_m.copy()

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    x = np.arange(len(d))
    y = d["p252"].to_numpy(dtype=float)

    ax.bar(x, y)
    ax.set_xticks(x)
    ax.set_xticklabels(d["series"].tolist(), rotation=0)
    ax.set_ylim(0, 105)
    ax.set_ylabel("1Y percentile rank (p252, 0-100)")
    ax.set_title("TWSE Market Snapshot — 1Y Rank (p252)", pad=12)

    for xi, yi in zip(x, y):
        if not math.isnan(yi):
            ax.text(xi, min(yi + 1.2, 104.0), f"{yi:.2f}", ha="center", va="bottom", fontsize=10)

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_rank60_jump_abs(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    d = df_m.copy()
    d = d[~d["pΔ60"].isna()].copy()

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    if d.empty:
        ax.axis("off")
        ax.text(0.01, 0.6, "No pΔ60 data available (all NA).", fontsize=14)
    else:
        x = np.arange(len(d))
        y = d["pΔ60"].to_numpy(dtype=float)

        ax.bar(x, y)
        ax.set_xticks(x)
        ax.set_xticklabels(d["series"].tolist(), rotation=0)
        ax.set_ylim(0, 105)
        ax.set_ylabel("Shock rank (pΔ60, percentile of |Δ1D| within last 60)")
        ax.set_title("Today's Move — 60D Shock Rank (pΔ60)", pad=12)

        for xi, yi in zip(x, y):
            if not math.isnan(yi):
                ax.text(xi, min(yi + 1.2, 104.0), f"{yi:.1f}", ha="center", va="bottom", fontsize=10)

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_z60_vs_rank252_scatter(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    d = df_m.copy()

    fig = plt.figure(figsize=(12, 6.2), dpi=160)
    ax = fig.add_subplot(111)

    for _, row in d.iterrows():
        x = float(row["p252"]) if not pd.isna(row["p252"]) else float("nan")
        y = float(row["z60"]) if not pd.isna(row["z60"]) else float("nan")
        if math.isnan(x) or math.isnan(y):
            continue
        ax.scatter([x], [y], label=str(row["series"]))

    ax.set_xlim(0, 100)
    ax.set_xlabel("1Y rank (p252 percentile)")
    ax.set_ylabel("60D deviation (z60, z-score)")
    ax.set_title("Short-term Deviation vs 1Y Rank (z60 vs p252)", pad=12)

    handles, labels = ax.get_legend_handles_labels()
    if labels:
        fig.legend(
            handles, labels,
            loc="lower center",
            ncol=min(5, len(labels)),
            frameon=False,
            bbox_to_anchor=(0.5, 0.06),
        )

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.14, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_ret1_abs_pct(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    """
    NOTE: kept filename/function name for backward compatibility, but now plots SIGNED ret1%.
    """
    d = df_m.copy()
    d = d[~d["ret1%"].isna()].copy()

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    if d.empty:
        ax.axis("off")
        ax.text(0.01, 0.6, "No 1-day % change data available (all NA).", fontsize=14)
    else:
        x = np.arange(len(d))
        y = d["ret1%"].to_numpy(dtype=float)

        ax.bar(x, y)
        ax.set_xticks(x)
        ax.set_xticklabels(d["series"].tolist(), rotation=0)

        # Always include 0 and keep both +/- directions.
        y_min = float(np.nanmin(y))
        y_max = float(np.nanmax(y))
        y_min = min(y_min, 0.0)
        y_max = max(y_max, 0.0)
        pad = max(0.5, 0.12 * max(abs(y_min), abs(y_max), 1e-9))
        ax.set_ylim(y_min - pad, y_max + pad)

        ax.axhline(0.0, linewidth=1.0, alpha=0.6)

        ax.set_ylabel("1-day % change (signed, %) — descriptive only")
        ax.set_title("1-day % change — Turnover / Index (NOT investment return)", pad=12)

        # Value labels: above for +, below for -
        span = (y_max - y_min) + 2 * pad
        off = 0.03 * span
        for xi, yi in zip(x, y):
            if math.isnan(yi):
                continue
            if yi >= 0:
                ax.text(xi, yi + off, f"{yi:.3f}%", ha="center", va="bottom", fontsize=10)
            else:
                ax.text(xi, yi - off, f"{yi:.3f}%", ha="center", va="top", fontsize=10)

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="roll25_cache", help="roll25 cache directory (default: roll25_cache)")
    ap.add_argument("--out", default="roll25_cache/charts", help="output directory (default: roll25_cache/charts)")
    ap.add_argument("--min-points-volmult", type=int, default=15,
                    help="min points for vol_multiplier_20 avg(last20_before_today) (default: 15)")
    ap.add_argument("--watermark", default="TWSE market daily (local cache)", help="watermark text (top-right)")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out)
    ensure_dir(out_dir)

    points, meta = load_points(cache_dir)
    df_points = points_to_df(points)

    used_dt = parse_date_any(meta.used_date) if meta.used_date else None
    latest_dt = pd.Timestamp(df_points["date"].iloc[-1]).normalize()
    if used_dt is None:
        meta.used_date = latest_dt.strftime("%Y-%m-%d")

    df_m = compute_metrics(df_points, min_points_20=args.min_points_volmult)

    chart_csv = out_dir / "chart_ready.csv"
    df_m.to_csv(chart_csv, index=False, encoding="utf-8")

    not_published = (meta.used_date_status == "DATA_NOT_UPDATED")
    status_note = "today not published yet; using latest available" if not_published else "published"
    age = meta.data_age_days if meta.data_age_days is not None else "NA"
    footer = f"Data as-of {meta.used_date} ({status_note}); age_days={age}; gen_utc={meta.generated_at_utc} | Descriptive only (NOT forecast)."

    font_smoketest(out_dir / "00_font_smoketest.png")
    make_rank252_overview(df_m, out_dir / "01_rank252_overview.png", footer, args.watermark)
    make_rank60_jump_abs(df_m, out_dir / "02_rank60_jump_abs.png", footer, args.watermark)
    make_z60_vs_rank252_scatter(df_m, out_dir / "03_z60_vs_rank252_scatter.png", footer, args.watermark)
    make_ret1_abs_pct(df_m, out_dir / "04_ret1_abs_pct.png", footer, args.watermark)

    print(f"[OK] out_dir={out_dir}")
    print(f"[OK] wrote: {chart_csv}")
    print(f"[OK] wrote: 00..04 pngs")
    print(f"[INFO] points_rows={len(df_points)} date_range={df_points['date'].iloc[0].date()}..{df_points['date'].iloc[-1].date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())