#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_roll25_cache_charts.py (PUBLIC-FACING / 全中文)

Generate chart_ready.csv + standard charts for roll25_cache (TWSE turnover).

對外版（全中文）重點：
- 圖表標題/座標/圖例/頁尾/浮水印：全中文（保留 p252 / z60 / pΔ60 這類「指標代碼」在括號內）。
- 避免使用「Roll25」字樣（保留在程式內部與資料夾命名即可）。
- 頁尾維持「單行、短句」，避免 1920px 輸出時與圖面元素擠在一起。
- 浮水印固定在右上角（避免與頁尾碰撞）。
- Scatter 圖例放在頁尾上方（figure-level），避免遮住點。
- 長條圖預留 headroom，避免頂端數值與圖表標題擠在一起。

重要提醒（避免誤導觀眾）：
- TURNOVER 這裡使用的是 trade_value（成交金額，TWD），不是「成交量（張數）」。
- pΔ60（本圖表用法）代表「|Δ1日| 的強度百分位」，不分漲跌方向。

Outputs (to --out):
- 00_font_smoketest.png
- chart_ready.csv
- 01_rank252_overview.png
- 02_rank60_jump_abs.png
- 03_z60_vs_rank252_scatter.png
- 04_ret1_signed_pct.png   (保留正負號)
- 04_ret1_abs_pct.png      (真正的 abs 版本：|ret1%|)
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
# Matplotlib font (best-effort for CJK)
# -----------------------------

def set_cjk_font_best_effort() -> None:
    """
    Best-effort CJK font fallback for GitHub Actions runners.
    Won't fail if fonts are missing; matplotlib will fallback silently.
    """
    try:
        matplotlib.rcParams["font.sans-serif"] = [
            "Noto Sans CJK TC",
            "Noto Sans CJK SC",
            "Noto Sans CJK JP",
            "Microsoft JhengHei",
            "PingFang TC",
            "Heiti TC",
            "SimHei",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass


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
    date, turnover_twd, close, change, prev_close, pct_change_close, amplitude_pct, high, low

    Audit-first:
    - Drop rows without parseable date (no silent coercion).
    - Sort ascending for plotting & strict adjacency computations.

    補齊策略（重要更新）：
    - pct_change_close：針對「缺值的列」逐列補齊（用 close/prev_close 計算），而非整欄全 NA 才補。
    - amplitude_pct：針對「缺值的列」逐列補齊（用 (high-low)/denom 計算），而非整欄全 NA 才補。
      denom 優先 prev_close，若缺則 fallback close。
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

        # prev_close 推導：若缺 prev_close 但有 close + change，則 prev_close = close - change
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

    # 若 prev_close 仍缺，先用「前一日 close」補（用於最基本的回報率推導）
    df["prev_close"] = df["prev_close"].where(df["prev_close"].notna(), df["close"].shift(1))

    # -----------------------------
    # (1) pct_change_close：逐列補齊缺值
    # pct = 100 * (close/prev_close - 1)
    # -----------------------------
    denom_pc = df["prev_close"]
    ok_pc = (
        df["pct_change_close"].isna()
        & df["close"].notna()
        & denom_pc.notna()
        & (denom_pc != 0)
    )
    df.loc[ok_pc, "pct_change_close"] = 100.0 * (df.loc[ok_pc, "close"] / denom_pc.loc[ok_pc] - 1.0)

    # -----------------------------
    # (2) amplitude_pct：逐列補齊缺值
    # amp = 100 * (high-low)/denom, denom 優先 prev_close，否則 fallback close
    # -----------------------------
    denom_amp = df["prev_close"].where(df["prev_close"].notna(), df["close"])
    ok_amp = (
        df["amplitude_pct"].isna()
        & df["high"].notna()
        & df["low"].notna()
        & denom_amp.notna()
        & (denom_amp != 0)
    )
    df.loc[ok_amp, "amplitude_pct"] = 100.0 * (df.loc[ok_amp, "high"] - df.loc[ok_amp, "low"]) / denom_amp.loc[ok_amp]

    return df


# -----------------------------
# Metrics
# -----------------------------

def compute_metrics(df: pd.DataFrame, min_points_20: int = 15) -> pd.DataFrame:
    df = df.copy()

    for col in ["turnover_twd", "close", "pct_change_close", "amplitude_pct", "prev_close"]:
        if col not in df.columns:
            df[col] = np.nan

    # vol_multiplier_20：用「前 20 日（不含今天）」的成交金額均值當分母
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

    def latest_delta_zp_abs(series: pd.Series, n: int, v_today: float, v_prev: float) -> Tuple[float, float, str]:
        """
        Δ強度（不分方向）：用 |Δ| 做排名。
        deltas_win = |s_t - s_{t-1}| 的近 n 日視窗
        d_today    = |v_today - v_prev|
        """
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
            zD60, pD60, cd = latest_delta_zp_abs(df[col], 60, v, v_prev)
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
                "zΔ60": zD60,   # Δ強度（abs）
                "pΔ60": pD60,   # Δ強度（abs）
                "ret1%": r1,
                "confidence": conf,
            }
        )

    return pd.DataFrame(out_rows)


# -----------------------------
# Plotting (全中文)
# -----------------------------

def series_label_zh(series_key: str) -> str:
    m = {
        "TURNOVER": "成交金額",
        "INDEX": "加權指數",
        "INDEX_%CHG": "指數漲跌幅(%)",
        "AMPL_%": "振幅(%)",
        "TURNOVERx20": "成交金額倍數(相對20日均值)",
    }
    return m.get(series_key, series_key)


def font_smoketest(out_png: Path) -> None:
    fig = plt.figure(figsize=(8, 2.2), dpi=160)
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.01, 0.72, "字型測試：中文 / English / 12345", fontsize=14)
    ax.text(0.01, 0.35, "成交金額 / 加權指數 / 振幅 / 位階指標", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_rank252_overview(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    d = df_m.copy()
    d["label_zh"] = d["series"].map(series_label_zh)

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    x = np.arange(len(d))
    y = d["p252"].to_numpy(dtype=float)

    ax.bar(x, y)
    ax.set_xticks(x)
    ax.set_xticklabels(d["label_zh"].tolist(), rotation=0)
    ax.set_ylim(0, 105)
    ax.set_ylabel("近一年位階（p252，百分位 0–100）")
    ax.set_title("台股市場快照：近一年位階（p252）", pad=12)

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
    d["label_zh"] = d["series"].map(series_label_zh)

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    if d.empty:
        ax.axis("off")
        ax.text(0.01, 0.6, "目前沒有可用的 pΔ60 資料（皆為 NA）。", fontsize=14)
    else:
        x = np.arange(len(d))
        y = d["pΔ60"].to_numpy(dtype=float)

        ax.bar(x, y)
        ax.set_xticks(x)
        ax.set_xticklabels(d["label_zh"].tolist(), rotation=0)
        ax.set_ylim(0, 105)
        ax.set_ylabel("60日變動強度位階（pΔ60：|Δ1日| 在近60日中的百分位；不分漲跌）")
        ax.set_title("今日波動強度：60日位階（pΔ60，取 |Δ| 不分方向）", pad=12)

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
    d["label_zh"] = d["series"].map(series_label_zh)

    fig = plt.figure(figsize=(12, 6.2), dpi=160)
    ax = fig.add_subplot(111)

    for _, row in d.iterrows():
        x = float(row["p252"]) if not pd.isna(row["p252"]) else float("nan")
        y = float(row["z60"]) if not pd.isna(row["z60"]) else float("nan")
        if math.isnan(x) or math.isnan(y):
            continue
        ax.scatter([x], [y], label=str(row["label_zh"]))

    ax.set_xlim(0, 100)
    ax.set_xlabel("近一年位階（p252：百分位）")
    ax.set_ylabel("近60日偏離（z60：z-score）")
    ax.set_title("短期偏離 vs 近一年位階（z60 vs p252）", pad=12)

    handles, labels = ax.get_legend_handles_labels()
    if labels:
        fig.legend(
            handles, labels,
            loc="lower center",
            ncol=min(3, len(labels)),
            frameon=False,
            bbox_to_anchor=(0.5, 0.06),
        )

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.14, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_ret1_signed_pct(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    d = df_m.copy()
    d = d[~d["ret1%"].isna()].copy()
    d["label_zh"] = d["series"].map(series_label_zh)

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    if d.empty:
        ax.axis("off")
        ax.text(0.01, 0.6, "目前沒有可用的 1 日變動（%）資料（皆為 NA）。", fontsize=14)
    else:
        x = np.arange(len(d))
        y = d["ret1%"].to_numpy(dtype=float)

        ax.bar(x, y)
        ax.axhline(0.0, linewidth=1.0)
        ax.set_xticks(x)
        ax.set_xticklabels(d["label_zh"].tolist(), rotation=0)
        ax.set_ylabel("1 日變動（%）— 保留正負號（描述用途）")
        ax.set_title("1 日變動（%）：成交金額 / 加權指數（非投資建議）", pad=12)

        max_abs = float(np.nanmax(np.abs(y))) if len(y) else 0.0
        if not np.isfinite(max_abs) or max_abs <= 0.0:
            max_abs = 1.0
        pad = max_abs * 0.18
        ax.set_ylim(-(max_abs + pad), (max_abs + pad))

        for xi, yi in zip(x, y):
            if math.isnan(yi):
                continue
            if yi >= 0:
                ax.text(xi, yi + max_abs * 0.04, f"{yi:.3f}%", ha="center", va="bottom", fontsize=10)
            else:
                ax.text(xi, yi - max_abs * 0.04, f"{yi:.3f}%", ha="center", va="top", fontsize=10)

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def make_ret1_abs_pct(df_m: pd.DataFrame, out_png: Path, footer: str, watermark: str) -> None:
    """
    真正的 abs 版本：y = |ret1%|，不分方向，只看幅度。
    """
    d = df_m.copy()
    d = d[~d["ret1%"].isna()].copy()
    d["label_zh"] = d["series"].map(series_label_zh)

    fig = plt.figure(figsize=(12, 5.6), dpi=160)
    ax = fig.add_subplot(111)

    if d.empty:
        ax.axis("off")
        ax.text(0.01, 0.6, "目前沒有可用的 1 日變動幅度（%）資料（皆為 NA）。", fontsize=14)
    else:
        x = np.arange(len(d))
        y_signed = d["ret1%"].to_numpy(dtype=float)
        y = np.abs(y_signed)

        ax.bar(x, y)
        ax.set_xticks(x)
        ax.set_xticklabels(d["label_zh"].tolist(), rotation=0)
        ax.set_ylabel("1 日變動幅度（%）— 取 |ret1%|（不分方向）")
        ax.set_title("1 日變動幅度（%）：成交金額 / 加權指數（非投資建議）", pad=12)

        max_v = float(np.nanmax(y)) if len(y) else 0.0
        if not np.isfinite(max_v) or max_v <= 0.0:
            max_v = 1.0
        pad = max_v * 0.22
        ax.set_ylim(0.0, max_v + pad)

        for xi, yi in zip(x, y):
            if math.isnan(yi):
                continue
            ax.text(xi, yi + max_v * 0.04, f"{yi:.3f}%", ha="center", va="bottom", fontsize=10)

    fig_footer_short(fig, footer)
    fig_watermark_topright(fig, watermark)
    fig.tight_layout(rect=[0, 0.06, 1, 0.98])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    set_cjk_font_best_effort()

    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="roll25_cache", help="roll25 cache directory (default: roll25_cache)")
    ap.add_argument("--out", default="roll25_cache/charts", help="output directory (default: roll25_cache/charts)")
    ap.add_argument("--min-points-volmult", type=int, default=15,
                    help="min points for vol_multiplier_20 avg(last20_before_today) (default: 15)")
    ap.add_argument("--watermark", default="台股市場快照（本機快取）", help="浮水印文字（右上角）")
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
    note = "（今日尚未公布，採用最新可得）" if not_published else ""
    age = meta.data_age_days if meta.data_age_days is not None else "NA"
    footer = f"資料截至 {meta.used_date}{note}｜age_days={age}｜gen_utc={meta.generated_at_utc}｜僅供描述（非預測/非建議）"

    font_smoketest(out_dir / "00_font_smoketest.png")
    make_rank252_overview(df_m, out_dir / "01_rank252_overview.png", footer, args.watermark)
    make_rank60_jump_abs(df_m, out_dir / "02_rank60_jump_abs.png", footer, args.watermark)
    make_z60_vs_rank252_scatter(df_m, out_dir / "03_z60_vs_rank252_scatter.png", footer, args.watermark)

    # 04：兩種版本都輸出，且檔名語意一致
    make_ret1_signed_pct(df_m, out_dir / "04_ret1_signed_pct.png", footer, args.watermark)
    make_ret1_abs_pct(df_m, out_dir / "04_ret1_abs_pct.png", footer, args.watermark)

    print(f"[OK] out_dir={out_dir}")
    print(f"[OK] wrote: {chart_csv}")
    print("[OK] wrote: 00..04 pngs (04 includes signed + abs)")
    print(f"[INFO] points_rows={len(df_points)} date_range={df_points['date'].iloc[0].date()}..{df_points['date'].iloc[-1].date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())