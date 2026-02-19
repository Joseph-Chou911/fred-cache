#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ===== Audit stamp (use this to prove which script generated the report) =====
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_bb_report@2026-02-19.v5"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fmt4(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.4f}"
    except Exception:
        return "N/A"


def fmt2(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.2f}"
    except Exception:
        return "N/A"


def fmt_pct2(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.2f}%"
    except Exception:
        return "N/A"


def fmt_pct1(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.1f}%"
    except Exception:
        return "N/A"


def safe_get(d: Any, k: str, default=None):
    try:
        if isinstance(d, dict):
            return d.get(k, default)
        return default
    except Exception:
        return default


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prices_tail(cache_dir: str, n: int) -> Optional[pd.DataFrame]:
    """
    Prefer data.csv; fallback to prices.csv.
    Normalize to columns: date, close, adjclose, volume
    """
    candidates = [
        os.path.join(cache_dir, "data.csv"),
        os.path.join(cache_dir, "prices.csv"),
    ]
    path = None
    for p in candidates:
        if os.path.exists(p):
            path = p
            break
    if path is None:
        return None

    df = pd.read_csv(path)
    if df.empty:
        return None

    if "date" not in df.columns and "Date" in df.columns:
        df.rename(columns={"Date": "date"}, inplace=True)
    if "date" not in df.columns:
        return None

    df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)

    if "adj close" in df.columns and "adjclose" not in df.columns:
        df.rename(columns={"adj close": "adjclose"}, inplace=True)

    if "close" not in df.columns:
        return None

    if "adjclose" not in df.columns:
        df["adjclose"] = df["close"]

    if "volume" not in df.columns:
        df["volume"] = pd.NA

    df = df[["date", "close", "adjclose", "volume"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    for c in ["close", "adjclose", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.tail(n)


def md_table_kv(rows: List[List[str]]) -> str:
    out = ["| item | value |", "|---|---:|"]
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def md_table_prices(df: pd.DataFrame) -> str:
    out = ["| date | close | adjclose | volume |", "|---|---:|---:|---:|"]
    for _, r in df.iterrows():
        d = r["date"]
        d_str = d.strftime("%Y-%m-%d") if not pd.isna(d) else "N/A"
        close = fmt4(r.get("close"))
        adj = fmt4(r.get("adjclose"))
        vol = r.get("volume")
        try:
            vol_s = f"{int(float(vol))}"
        except Exception:
            vol_s = "N/A"
        out.append(f"| {d_str} | {close} | {adj} | {vol_s} |")
    return "\n".join(out)


def build_forward_line(fwd: Dict[str, Any], dq_flags: List[str], fwd_days: int) -> str:
    n = safe_get(fwd, "n", 0)
    p50 = safe_get(fwd, "p50")
    p10 = safe_get(fwd, "p10")
    p05 = safe_get(fwd, "p05")
    mn = safe_get(fwd, "min")

    line = (
        f"- forward_mdd({fwd_days}D) distribution (n={n}): "
        f"p50={fmt4(p50)}; p10={fmt4(p10)}; p05={fmt4(p05)}; min={fmt4(mn)}"
    )

    # Append audit trail if exists
    med = safe_get(fwd, "min_entry_date")
    mfd = safe_get(fwd, "min_future_date")
    mep = safe_get(fwd, "min_entry_price")
    mfp = safe_get(fwd, "min_future_price")
    if med and mfd and mep is not None and mfp is not None:
        line += f" (min_window: {med}->{mfd}; {fmt4(mep)}->{fmt4(mfp)})"

    # DQ tags (keep concise)
    sflags = set(dq_flags or [])
    if "RAW_OUTLIER_EXCLUDED" in sflags:
        line += " [DQ:RAW_OUTLIER_EXCLUDED]"
    elif "FWD_MDD_OUTLIER_MIN_RAW" in sflags:
        line += " [DQ:FWD_MDD_OUTLIER_MIN_RAW]"

    return line


def build_trend_line(trend: Dict[str, Any]) -> str:
    ma_days = safe_get(trend, "trend_ma_days", 200)
    slope_days = safe_get(trend, "trend_slope_days", 20)
    thr = safe_get(trend, "trend_slope_thr_pct", 0.50)
    p_vs = safe_get(trend, "price_vs_trend_ma_pct")
    slope = safe_get(trend, "trend_slope_pct")
    state = safe_get(trend, "state", "TREND_NA")
    return (
        f"- trend_filter(MA{ma_days},slope{slope_days}D,thr={fmt_pct2(thr)}): "
        f"price_vs_ma={fmt_pct2(p_vs)}; slope={fmt_pct2(slope)} => **{state}**"
    )


def build_vol_line(vol: Dict[str, Any], atr: Dict[str, Any]) -> str:
    rv_days = safe_get(vol, "rv_days", 20)
    rv_ann = safe_get(vol, "rv_ann")
    atr_days = safe_get(atr, "atr_days", 14)
    atr_v = safe_get(atr, "atr")
    atr_pct = safe_get(atr, "atr_pct")
    rv_pct = None if rv_ann is None else float(rv_ann) * 100.0
    return f"- vol_filter(RV{rv_days},ATR{atr_days}): rv_ann={fmt_pct1(rv_pct)}; atr={fmt4(atr_v)} ({fmt_pct2(atr_pct)})"


def read_margin_latest(path: str) -> Optional[Dict[str, Any]]:
    if not path or (not os.path.exists(path)):
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def margin_state(sum_chg_yi: float, threshold_yi: float) -> str:
    if sum_chg_yi >= threshold_yi:
        return "LEVERAGING"
    if sum_chg_yi <= -threshold_yi:
        return "DELEVERAGING"
    return "NEUTRAL"


def take_last_n_rows(rows: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    if not isinstance(rows, list) or n <= 0:
        return []
    # rows in your latest.json are newest first; keep that assumption but be defensive
    # We want the latest n trading days -> first n
    return rows[:n]


def sum_chg(rows: List[Dict[str, Any]]) -> float:
    s = 0.0
    for r in rows:
        try:
            v = r.get("chg_yi", None)
            if v is None:
                continue
            s += float(v)
        except Exception:
            continue
    return float(s)


def margin_overlay_block(margin_json: Dict[str, Any], price_last_date: str, window_n: int, threshold_yi: float
                         ) -> Tuple[List[str], Optional[str]]:
    """
    Returns:
      - markdown lines for the section
      - quick summary line (or None)
    """
    lines: List[str] = []
    series = safe_get(margin_json, "series", {}) or {}
    twse = safe_get(series, "TWSE", {}) or {}
    tpex = safe_get(series, "TPEX", {}) or {}

    gen_utc = safe_get(margin_json, "generated_at_utc", "N/A")
    data_date = safe_get(twse, "data_date", None) or safe_get(tpex, "data_date", None) or "N/A"

    twse_rows = safe_get(twse, "rows", []) or []
    tpex_rows = safe_get(tpex, "rows", []) or []

    twse_last = twse_rows[0]["date"] if (isinstance(twse_rows, list) and len(twse_rows) > 0) else None
    tpex_last = tpex_rows[0]["date"] if (isinstance(tpex_rows, list) and len(tpex_rows) > 0) else None
    margin_last_date = twse_last or tpex_last or "N/A"

    aligned = (str(margin_last_date) == str(price_last_date))
    align_tag = "ALIGNED" if aligned else "MISALIGNED"

    twse_n = take_last_n_rows(twse_rows, window_n)
    tpex_n = take_last_n_rows(tpex_rows, window_n)

    twse_sum = sum_chg(twse_n)
    tpex_sum = sum_chg(tpex_n)
    total_sum = twse_sum + tpex_sum

    twse_state = margin_state(twse_sum, threshold_yi)
    tpex_state = margin_state(tpex_sum, threshold_yi)
    total_state = margin_state(total_sum, threshold_yi)

    # balances (latest)
    def latest_balance(rows: List[Dict[str, Any]]) -> Optional[float]:
        try:
            if not rows:
                return None
            return float(rows[0].get("balance_yi"))
        except Exception:
            return None

    twse_bal = latest_balance(twse_rows)
    tpex_bal = latest_balance(tpex_rows)
    total_bal = (twse_bal + tpex_bal) if (twse_bal is not None and tpex_bal is not None) else None

    # today's change (latest)
    def latest_chg(rows: List[Dict[str, Any]]) -> Optional[float]:
        try:
            if not rows:
                return None
            return float(rows[0].get("chg_yi"))
        except Exception:
            return None

    twse_chg_today = latest_chg(twse_rows)
    tpex_chg_today = latest_chg(tpex_rows)

    # quick summary line
    quick = (
        f"- margin({window_n}D,thr={threshold_yi:.2f}億): TOTAL {total_sum:.2f} 億 => **{total_state}**; "
        f"TWSE {twse_sum:.2f} / TPEX {tpex_sum:.2f}; "
        f"margin_date={margin_last_date}, price_last_date={price_last_date} ({align_tag}); data_date={data_date}"
    )

    # section lines
    lines.append("## Margin Overlay（融資）")
    lines.append("")
    lines.append(f"- overlay_generated_at_utc: `{gen_utc}`")
    lines.append(f"- data_date: `{data_date}`")
    lines.append(f"- params: window_n={window_n}, threshold_yi={threshold_yi:.2f}")
    lines.append(f"- date_alignment: margin_latest_date=`{margin_last_date}` vs price_last_date=`{price_last_date}` => **{align_tag}**")
    lines.append("")
    lines.append("| scope | latest_date | balance(億) | chg_today(億) | chg_ND_sum(億) | state_ND | rows_used |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    def fmt_yi(x: Optional[float]) -> str:
        try:
            if x is None:
                return "N/A"
            return f"{float(x):,.1f}"
        except Exception:
            return "N/A"

    lines.append(f"| TWSE | {twse_last or 'N/A'} | {fmt_yi(twse_bal)} | {fmt_yi(twse_chg_today)} | {twse_sum:.1f} | {twse_state} | {len(twse_n)} |")
    lines.append(f"| TPEX | {tpex_last or 'N/A'} | {fmt_yi(tpex_bal)} | {fmt_yi(tpex_chg_today)} | {tpex_sum:.1f} | {tpex_state} | {len(tpex_n)} |")
    lines.append(f"| TOTAL | {margin_last_date} | {fmt_yi(total_bal)} | N/A | {total_sum:.1f} | {total_state} | N/A |")
    lines.append("")
    lines.append("### Margin Sources")
    lines.append("")
    lines.append(f"- TWSE source: `{safe_get(twse, 'source', 'N/A')}`")
    lines.append(f"- TWSE url: `{safe_get(twse, 'source_url', 'N/A')}`")
    lines.append(f"- TPEX source: `{safe_get(tpex, 'source', 'N/A')}`")
    lines.append(f"- TPEX url: `{safe_get(tpex, 'source_url', 'N/A')}`")
    lines.append("")

    return lines, quick


def build_regime_line(regime: Dict[str, Any]) -> Optional[str]:
    if not isinstance(regime, dict) or not regime:
        return None
    tag = safe_get(regime, "tag", "N/A")
    allowed = bool(safe_get(regime, "allowed", False))
    inputs = safe_get(regime, "inputs", {}) or {}
    rv_pctl = safe_get(inputs, "rv_ann_pctl", None)
    return f"- regime(relative_pctl): **{tag}**; allowed={str(allowed).lower()}; rv20_pctl={fmt2(rv_pctl)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default="report.md")
    ap.add_argument("--tail_days", type=int, default=15)  # workflow compatibility
    ap.add_argument("--tail_n", type=int, default=None)   # alias; overrides tail_days

    # margin overlay
    ap.add_argument("--margin_json", default="taiwan_margin_cache/latest.json")
    ap.add_argument("--margin_window_n", type=int, default=5)
    ap.add_argument("--margin_threshold_yi", type=float, default=100.0)

    args = ap.parse_args()

    tail_n = args.tail_n if args.tail_n is not None else args.tail_days
    if tail_n <= 0:
        tail_n = 15

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    if not os.path.exists(stats_path):
        raise SystemExit(f"ERROR: missing {stats_path}")

    s = load_json(stats_path)
    meta = s.get("meta", {}) or {}
    latest = s.get("latest", {}) or {}
    fwd = s.get("forward_mdd", {}) or {}
    dq = s.get("dq", {"flags": [], "notes": []}) or {}
    dq_flags = dq.get("flags") or []
    dq_notes = dq.get("notes") or []

    trend = s.get("trend", {}) or {}
    vol = s.get("vol", {}) or {}
    atr = s.get("atr", {}) or {}
    regime = s.get("regime", {}) or {}

    # Detect whether min audit fields exist
    has_min_audit = all(
        k in fwd for k in ["min_entry_date", "min_entry_price", "min_future_date", "min_future_price"]
    )
    fwd_keys_sorted = sorted(list(fwd.keys())) if isinstance(fwd, dict) else []

    ticker = safe_get(meta, "ticker", "0050.TW")
    last_date = safe_get(meta, "last_date", "N/A")
    bb_window = safe_get(meta, "bb_window", 60)
    bb_k = safe_get(meta, "bb_k", 2.0)
    fwd_days = int(safe_get(meta, "fwd_days", 20))
    price_calc = safe_get(meta, "price_calc", "adjclose")
    data_source = safe_get(meta, "data_source", "yfinance_yahoo_or_twse_fallback")

    state = safe_get(latest, "state", "N/A")
    bb_z = safe_get(latest, "bb_z")
    bb_pos = safe_get(latest, "bb_pos")
    dist_to_lower = safe_get(latest, "dist_to_lower_pct")
    dist_to_upper = safe_get(latest, "dist_to_upper_pct")

    lines: List[str] = []
    lines.append("# 0050 BB(60,2) + forward_mdd(20D) Report")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{utc_now_iso()}`")
    lines.append(f"- build_script_fingerprint: `{BUILD_SCRIPT_FINGERPRINT}`")
    lines.append(f"- stats_path: `{stats_path}`")
    lines.append(f"- stats_has_min_audit_fields: `{str(has_min_audit).lower()}`")
    lines.append(f"- data_source: `{data_source}`")
    lines.append(f"- ticker: `{ticker}`")
    lines.append(f"- last_date: `{last_date}`")
    lines.append(f"- bb_window,k: `{bb_window}`, `{bb_k}`")
    lines.append(f"- forward_window_days: `{fwd_days}`")
    lines.append(f"- price_calc: `{price_calc}`")
    lines.append("")

    # ===== Quick summary =====
    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{state}**; bb_z={fmt4(bb_z)}; pos_in_band={fmt4(bb_pos)}; "
        f"dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}"
    )
    lines.append(build_forward_line(fwd, dq_flags, fwd_days))

    # trend/vol quick lines (only if present)
    if isinstance(trend, dict) and trend:
        lines.append(build_trend_line(trend))
    if isinstance(vol, dict) and vol and isinstance(atr, dict) and atr:
        lines.append(build_vol_line(vol, atr))

    # regime quick line
    reg_line = build_regime_line(regime)
    if reg_line:
        lines.append(reg_line)

    # margin quick line (if file exists)
    margin_json = read_margin_latest(args.margin_json)
    margin_quick = None
    if margin_json is not None:
        _, margin_quick = margin_overlay_block(
            margin_json=margin_json,
            price_last_date=str(last_date),
            window_n=int(args.margin_window_n),
            threshold_yi=float(args.margin_threshold_yi),
        )
        if margin_quick:
            lines.append(margin_quick)

    lines.append("")

    # ===== Latest snapshot =====
    lines.append("## Latest Snapshot")
    lines.append("")
    lines.append(
        md_table_kv(
            [
                ["close", fmt4(safe_get(latest, "close"))],
                ["adjclose", fmt4(safe_get(latest, "adjclose"))],
                ["price_used", fmt4(safe_get(latest, "price_used"))],
                ["bb_ma", fmt4(safe_get(latest, "bb_ma"))],
                ["bb_sd", fmt4(safe_get(latest, "bb_sd"))],
                ["bb_upper", fmt4(safe_get(latest, "bb_upper"))],
                ["bb_lower", fmt4(safe_get(latest, "bb_lower"))],
                ["bb_z", fmt4(safe_get(latest, "bb_z"))],
                ["pos_in_band", fmt4(safe_get(latest, "bb_pos"))],
                ["dist_to_lower", fmt_pct2(safe_get(latest, "dist_to_lower_pct"))],
                ["dist_to_upper", fmt_pct2(safe_get(latest, "dist_to_upper_pct"))],
            ]
        )
    )
    lines.append("")

    # ===== Trend & Vol =====
    if (isinstance(trend, dict) and trend) or (isinstance(vol, dict) and vol) or (isinstance(atr, dict) and atr):
        lines.append("## Trend & Vol Filters")
        lines.append("")
        if isinstance(trend, dict) and trend:
            lines.append(md_table_kv([
                ["trend_ma_days", str(safe_get(trend, "trend_ma_days", "N/A"))],
                ["trend_ma_last", fmt4(safe_get(trend, "trend_ma_last"))],
                ["trend_slope_days", str(safe_get(trend, "trend_slope_days", "N/A"))],
                ["trend_slope_pct", fmt_pct2(safe_get(trend, "trend_slope_pct"))],
                ["price_vs_trend_ma_pct", fmt_pct2(safe_get(trend, "price_vs_trend_ma_pct"))],
                ["trend_state", str(safe_get(trend, "state", "N/A"))],
            ]))
            lines.append("")

        if isinstance(vol, dict) and vol:
            rv_ann = safe_get(vol, "rv_ann")
            rv_pct = None if rv_ann is None else float(rv_ann) * 100.0
            lines.append(md_table_kv([
                ["rv_days", str(safe_get(vol, "rv_days", "N/A"))],
                ["rv_ann(%)", fmt_pct1(rv_pct)],
                ["rv20_percentile", fmt2(safe_get(vol, "rv_ann_pctl"))],
                ["rv_hist_n", str(safe_get(vol, "rv_hist_n", "N/A"))],
                ["rv_hist_q20(%)", fmt_pct1(None if safe_get(vol, "rv_hist_q20") is None else float(safe_get(vol, "rv_hist_q20")) * 100.0)],
                ["rv_hist_q50(%)", fmt_pct1(None if safe_get(vol, "rv_hist_q50") is None else float(safe_get(vol, "rv_hist_q50")) * 100.0)],
                ["rv_hist_q80(%)", fmt_pct1(None if safe_get(vol, "rv_hist_q80") is None else float(safe_get(vol, "rv_hist_q80")) * 100.0)],
            ]))
            lines.append("")

        if isinstance(atr, dict) and atr:
            lines.append(md_table_kv([
                ["atr_days", str(safe_get(atr, "atr_days", "N/A"))],
                ["atr", fmt4(safe_get(atr, "atr"))],
                ["atr_pct", fmt_pct2(safe_get(atr, "atr_pct"))],
                ["tr_mode", str(safe_get(atr, "tr_mode", "N/A"))],
            ]))
            lines.append("")

    # ===== Regime section =====
    lines.append("## Regime Tag")
    lines.append("")
    if isinstance(regime, dict) and regime:
        inputs = safe_get(regime, "inputs", {}) or {}
        params = safe_get(regime, "params", {}) or {}
        passes = safe_get(regime, "passes", {}) or {}
        reasons = safe_get(regime, "reasons", []) or []

        rv_ann = safe_get(inputs, "rv_ann")
        rv_pct = None if rv_ann is None else float(rv_ann) * 100.0

        lines.append(md_table_kv([
            ["tag", f"**{safe_get(regime,'tag','N/A')}**"],
            ["allowed", str(bool(safe_get(regime,'allowed', False))).lower()],
            ["trend_state", str(safe_get(inputs, "trend_state", "N/A"))],
            ["rv_ann(%)", fmt_pct1(rv_pct)],
            ["rv20_percentile", fmt2(safe_get(inputs, "rv_ann_pctl"))],
            ["rv_hist_n", str(safe_get(inputs, "rv_hist_n", "N/A"))],
            ["rv_pctl_max", fmt2(safe_get(params, "rv_pctl_max"))],
            ["min_samples", str(safe_get(params, "min_samples", "N/A"))],
            ["pass_trend", str(bool(safe_get(passes, "trend_ok", False))).lower()],
            ["pass_rv_hist", str(bool(safe_get(passes, "rv_hist_ok", False))).lower()],
            ["pass_rv", str(bool(safe_get(passes, "rv_ok", False))).lower()],
            ["bb_state_note", str(safe_get(inputs, "bb_state", "N/A"))],
        ]))
        if reasons:
            lines.append("")
            lines.append("### Regime Notes")
            for r in reasons:
                lines.append(f"- {r}")
        lines.append("")
    else:
        lines.append("_No regime data in stats_latest.json._")
        lines.append("")

    # ===== forward_mdd Distribution =====
    lines.append("## forward_mdd Distribution")
    lines.append("")
    lines.append(f"- definition: `{safe_get(fwd, 'definition', 'N/A')}`")
    lines.append("")
    lines.append("| quantile | value |")
    lines.append("|---|---:|")
    lines.append(f"| p50 | {fmt4(safe_get(fwd, 'p50'))} |")
    lines.append(f"| p25 | {fmt4(safe_get(fwd, 'p25'))} |")
    lines.append(f"| p10 | {fmt4(safe_get(fwd, 'p10'))} |")
    lines.append(f"| p05 | {fmt4(safe_get(fwd, 'p05'))} |")
    lines.append(f"| min | {fmt4(safe_get(fwd, 'min'))} |")
    lines.append("")

    # Min audit trail (or explicit missing-field message)
    lines.append("### forward_mdd Min Audit Trail")
    lines.append("")
    if has_min_audit:
        lines.append("| item | value |")
        lines.append("|---|---:|")
        lines.append(f"| min_entry_date | {safe_get(fwd, 'min_entry_date')} |")
        lines.append(f"| min_entry_price | {fmt4(safe_get(fwd, 'min_entry_price'))} |")
        lines.append(f"| min_future_date | {safe_get(fwd, 'min_future_date')} |")
        lines.append(f"| min_future_price | {fmt4(safe_get(fwd, 'min_future_price'))} |")
    else:
        lines.append("- min audit fields are missing in stats_latest.json.")
        lines.append(f"- forward_mdd keys: `{', '.join(fwd_keys_sorted)}`")
    lines.append("")

    # ===== Margin Overlay =====
    if margin_json is not None:
        mb_lines, _ = margin_overlay_block(
            margin_json=margin_json,
            price_last_date=str(last_date),
            window_n=int(args.margin_window_n),
            threshold_yi=float(args.margin_threshold_yi),
        )
        lines.extend(mb_lines)

    # ===== Prices tail =====
    lines.append(f"## Recent Raw Prices (tail {tail_n})")
    lines.append("")
    tail_df = load_prices_tail(args.cache_dir, n=tail_n)
    if tail_df is None:
        lines.append("_No data.csv / prices.csv tail available._")
    else:
        lines.append(md_table_prices(tail_df))
    lines.append("")

    # ===== DQ =====
    lines.append("## Data Quality Flags")
    lines.append("")
    if not dq_flags:
        lines.append("- (none)")
    else:
        if dq_notes and len(dq_notes) == len(dq_flags):
            for fl, nt in zip(dq_flags, dq_notes):
                lines.append(f"- {fl}: {nt}")
        else:
            for fl in dq_flags:
                lines.append(f"- {fl}")
            for nt in dq_notes:
                lines.append(f"  - note: {nt}")
    lines.append("")

    # ===== Caveats =====
    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。")
    lines.append("- Trend/Vol/ATR 是濾網與風險量級提示，不是進出場保證；若資料不足會以 DQ 明示。")
    lines.append("- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；若日期不對齊應降低解讀權重。")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())