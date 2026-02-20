#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ===== Audit stamp =====
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_bb_report@2026-02-20.v11"


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


def fmt_price2(x: Any) -> str:
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


def fmt_signed_pct2(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):+.2f}%"
    except Exception:
        return "N/A"


def fmt_pct1(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.1f}%"
    except Exception:
        return "N/A"


def fmt_int(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{int(float(x)):,}"
    except Exception:
        return "N/A"


def fmt_yi_from_ntd(x: Any, digits: int = 1) -> str:
    """
    NTD -> 億 (1e8 NTD)
    """
    try:
        if x is None:
            return "N/A"
        yi = float(x) / 1e8
        return f"{yi:,.{digits}f}"
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


def normalize_date_key(x: Any) -> Optional[str]:
    """
    Normalize dates:
      - "2026-02-11" -> "20260211"
      - "20260211" -> "20260211"
    """
    try:
        if x is None:
            return None
        if isinstance(x, datetime):
            return x.strftime("%Y%m%d")
        s = str(x).strip()
        if not s:
            return None
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10].replace("-", "")
        if len(s) == 8 and s.isdigit():
            return s
        dt = pd.to_datetime(s, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y%m%d")
    except Exception:
        return None


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


def _pct(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _above_upper_lower_from_dist(dist_to_upper_pct: Any, dist_to_lower_pct: Any) -> Tuple[str, str]:
    """
    dist_to_upper_pct can be negative when above upper.
    dist_to_lower_pct can be negative when below lower.

    Returns:
      above_upper_pct_str: "0.37%" else "0.00%"
      below_lower_pct_str: "0.81%" else "0.00%"
    """
    du = _pct(dist_to_upper_pct)
    dl = _pct(dist_to_lower_pct)

    above_upper = None if du is None else (-du if du < 0 else 0.0)
    below_lower = None if dl is None else (-dl if dl < 0 else 0.0)

    au_s = "N/A" if above_upper is None else f"{above_upper:.2f}%"
    bl_s = "N/A" if below_lower is None else f"{below_lower:.2f}%"
    return au_s, bl_s


def _dq_compact(dq_flags: List[str]) -> str:
    if not dq_flags:
        return "(none)"
    priority_prefix = (
        "PRICE_",
        "FWD_MDD_",
        "TWSE_",
        "YF_",
        "RAW_",
        "CHIP_",
        "MARGIN_",
    )
    pri = [f for f in dq_flags if any(f.startswith(p) for p in priority_prefix)]
    rest = [f for f in dq_flags if f not in pri]
    ordered = pri + rest
    cap = 6
    if len(ordered) <= cap:
        return ", ".join(ordered)
    return ", ".join(ordered[:cap]) + f", ... (+{len(ordered) - cap})"


def _extract_fwd_outlier_days(dq_flags: List[str]) -> List[int]:
    """
    Parse flags like:
      FWD_MDD_OUTLIER_MIN_RAW_20D -> [20]
      FWD_MDD_OUTLIER_MIN_RAW_10D -> [10]
    """
    days: List[int] = []
    for f in dq_flags:
        if not isinstance(f, str):
            continue
        if not f.startswith("FWD_MDD_OUTLIER_MIN_RAW_"):
            continue
        if not f.endswith("D"):
            continue
        try:
            tail = f.split("_")[-1]  # e.g. "20D"
            if tail.endswith("D"):
                n = int(tail[:-1])
                days.append(n)
        except Exception:
            continue
    days = sorted(set(days))
    return days


def _dq_core_and_fwd_summary(dq_flags: List[str]) -> Tuple[str, str]:
    """
    For quick summary:
      - core DQ excludes horizon-specific FWD outlier flags
      - fwd_outlier shows parsed horizons, e.g. "20D" or "(none)"
    """
    flags = [str(x) for x in dq_flags if isinstance(x, str)]
    core = [f for f in flags if not f.startswith("FWD_MDD_OUTLIER_MIN_RAW_")]
    days = _extract_fwd_outlier_days(flags)
    fwd = "(none)" if not days else ",".join([f"{d}D" for d in days])
    return _dq_compact(core), fwd


def _filter_fwd_outlier_flags_for_horizon(dq_flags: List[str], horizon_days: int) -> List[str]:
    """
    Only keep forward-outlier flags relevant to this horizon.
    """
    flags = [f for f in dq_flags if isinstance(f, str)]
    suff = f"_{horizon_days}D"
    specific = sorted([f for f in flags if f.startswith("FWD_MDD_OUTLIER_MIN_RAW") and f.endswith(suff)])
    if specific:
        return specific
    generic = sorted([f for f in flags if f == "FWD_MDD_OUTLIER_MIN_RAW"])
    return generic


def build_forward_line(label: str, fwd: Dict[str, Any], dq_flags: List[str], horizon_days: int) -> str:
    n = safe_get(fwd, "n", 0)
    p50 = safe_get(fwd, "p50")
    p10 = safe_get(fwd, "p10")
    p05 = safe_get(fwd, "p05")
    mn = safe_get(fwd, "min")

    line = (
        f"- {label} distribution (n={n}): "
        f"p50={fmt4(p50)}; p10={fmt4(p10)}; p05={fmt4(p05)}; min={fmt4(mn)}"
    )

    med = safe_get(fwd, "min_entry_date")
    mfd = safe_get(fwd, "min_future_date")
    mep = safe_get(fwd, "min_entry_price")
    mfp = safe_get(fwd, "min_future_price")
    if med and mfd and mep is not None and mfp is not None:
        line += f" (min_window: {med}->{mfd}; {fmt4(mep)}->{fmt4(mfp)})"

    sflags = set([str(x) for x in (dq_flags or []) if isinstance(x, str)])
    if "RAW_OUTLIER_EXCLUDED_BY_CLEAN" in sflags:
        line += " [DQ:RAW_OUTLIER_EXCLUDED_BY_CLEAN]"

    outlier_flags = _filter_fwd_outlier_flags_for_horizon(list(sflags), horizon_days)
    for f in outlier_flags[:2]:
        line += f" [DQ:{f}]"
    if len(outlier_flags) > 2:
        line += f" [DQ:+{len(outlier_flags) - 2}]"

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


def build_regime_line(regime: Dict[str, Any]) -> Optional[str]:
    if not isinstance(regime, dict) or not regime:
        return None
    tag = safe_get(regime, "tag", "N/A")
    allowed = bool(safe_get(regime, "allowed", False))
    inputs = safe_get(regime, "inputs", {}) or {}
    rv_pctl = safe_get(inputs, "rv_ann_pctl", None)
    return f"- regime(relative_pctl): **{tag}**; allowed={str(allowed).lower()}; rv20_pctl={fmt2(rv_pctl)}"


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
    return rows[:n]  # newest first


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


def margin_overlay_struct(
    margin_json: Dict[str, Any],
    price_last_date: str,
    window_n: int,
    threshold_yi: float,
) -> Dict[str, Any]:
    series = safe_get(margin_json, "series", {}) or {}
    twse = safe_get(series, "TWSE", {}) or {}
    tpex = safe_get(series, "TPEX", {}) or {}

    twse_rows = safe_get(twse, "rows", []) or []
    tpex_rows = safe_get(tpex, "rows", []) or []

    twse_last = twse_rows[0]["date"] if (isinstance(twse_rows, list) and len(twse_rows) > 0) else None
    tpex_last = tpex_rows[0]["date"] if (isinstance(tpex_rows, list) and len(tpex_rows) > 0) else None
    margin_last_date = twse_last or tpex_last or "N/A"

    aligned = (normalize_date_key(margin_last_date) == normalize_date_key(price_last_date))
    align_tag = "ALIGNED" if aligned else "MISALIGNED"

    twse_n = take_last_n_rows(twse_rows, window_n)
    tpex_n = take_last_n_rows(tpex_rows, window_n)

    twse_sum = sum_chg(twse_n)
    tpex_sum = sum_chg(tpex_n)
    total_sum = twse_sum + tpex_sum

    twse_state = margin_state(twse_sum, threshold_yi)
    tpex_state = margin_state(tpex_sum, threshold_yi)
    total_state = margin_state(total_sum, threshold_yi)

    data_date = safe_get(twse, "data_date", None) or safe_get(tpex, "data_date", None) or "N/A"
    gen_utc = safe_get(margin_json, "generated_at_utc", "N/A")

    return {
        "generated_at_utc": gen_utc,
        "data_date": data_date,
        "margin_last_date": margin_last_date,
        "align_tag": align_tag,
        "aligned": aligned,
        "window_n": window_n,
        "threshold_yi": threshold_yi,
        "twse_sum": twse_sum,
        "tpex_sum": tpex_sum,
        "total_sum": total_sum,
        "twse_state": twse_state,
        "tpex_state": tpex_state,
        "total_state": total_state,
    }


def margin_overlay_block(
    margin_json: Dict[str, Any],
    price_last_date: str,
    window_n: int,
    threshold_yi: float,
) -> Tuple[List[str], Optional[str]]:
    lines: List[str] = []

    info = margin_overlay_struct(
        margin_json=margin_json,
        price_last_date=price_last_date,
        window_n=window_n,
        threshold_yi=threshold_yi,
    )

    series = safe_get(margin_json, "series", {}) or {}
    twse = safe_get(series, "TWSE", {}) or {}
    tpex = safe_get(series, "TPEX", {}) or {}
    twse_rows = safe_get(twse, "rows", []) or []
    tpex_rows = safe_get(tpex, "rows", []) or []

    twse_last = twse_rows[0]["date"] if (isinstance(twse_rows, list) and len(twse_rows) > 0) else None
    tpex_last = tpex_rows[0]["date"] if (isinstance(tpex_rows, list) and len(tpex_rows) > 0) else None

    def latest_balance(rows: List[Dict[str, Any]]) -> Optional[float]:
        try:
            if not rows:
                return None
            return float(rows[0].get("balance_yi"))
        except Exception:
            return None

    def latest_chg(rows: List[Dict[str, Any]]) -> Optional[float]:
        try:
            if not rows:
                return None
            return float(rows[0].get("chg_yi"))
        except Exception:
            return None

    twse_bal = latest_balance(twse_rows)
    tpex_bal = latest_balance(tpex_rows)
    total_bal = (twse_bal + tpex_bal) if (twse_bal is not None and tpex_bal is not None) else None

    twse_chg_today = latest_chg(twse_rows)
    tpex_chg_today = latest_chg(tpex_rows)

    quick = (
        f"- margin({window_n}D,thr={threshold_yi:.2f}億): TOTAL {info['total_sum']:.2f} 億 => **{info['total_state']}**; "
        f"TWSE {info['twse_sum']:.2f} / TPEX {info['tpex_sum']:.2f}; "
        f"margin_date={info['margin_last_date']}, price_last_date={price_last_date} ({info['align_tag']}); data_date={info['data_date']}"
    )

    lines.append("## Margin Overlay（融資）")
    lines.append("")
    lines.append(f"- overlay_generated_at_utc: `{info['generated_at_utc']}`")
    lines.append(f"- data_date: `{info['data_date']}`")
    lines.append(f"- params: window_n={window_n}, threshold_yi={threshold_yi:.2f}")
    lines.append(
        f"- date_alignment: margin_latest_date=`{info['margin_last_date']}` vs price_last_date=`{price_last_date}` => **{info['align_tag']}**"
    )
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

    lines.append(
        f"| TWSE | {twse_last or 'N/A'} | {fmt_yi(twse_bal)} | {fmt_yi(twse_chg_today)} | {info['twse_sum']:.1f} | {info['twse_state']} | {len(take_last_n_rows(twse_rows, window_n))} |"
    )
    lines.append(
        f"| TPEX | {tpex_last or 'N/A'} | {fmt_yi(tpex_bal)} | {fmt_yi(tpex_chg_today)} | {info['tpex_sum']:.1f} | {info['tpex_state']} | {len(take_last_n_rows(tpex_rows, window_n))} |"
    )
    lines.append(
        f"| TOTAL | {info['margin_last_date']} | {fmt_yi(total_bal)} | N/A | {info['total_sum']:.1f} | {info['total_state']} | N/A |"
    )
    lines.append("")
    lines.append("### Margin Sources")
    lines.append("")
    lines.append(f"- TWSE source: `{safe_get(twse, 'source', 'N/A')}`")
    lines.append(f"- TWSE url: `{safe_get(twse, 'source_url', 'N/A')}`")
    lines.append(f"- TPEX source: `{safe_get(tpex, 'source', 'N/A')}`")
    lines.append(f"- TPEX url: `{safe_get(tpex, 'source_url', 'N/A')}`")
    lines.append("")

    return lines, quick


def read_chip_overlay(path: str) -> Optional[Dict[str, Any]]:
    if not path or (not os.path.exists(path)):
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def chip_overlay_block(
    chip_json: Dict[str, Any],
    price_last_date: str,
    expect_window_n: int,
) -> Tuple[List[str], Optional[str], List[str]]:
    lines: List[str] = []
    dq_extra: List[str] = []

    meta = safe_get(chip_json, "meta", {}) or {}
    data = safe_get(chip_json, "data", {}) or {}
    sources = safe_get(chip_json, "sources", {}) or {}
    root_dq = safe_get(safe_get(chip_json, "dq", {}) or {}, "flags", []) or []

    run_ts_utc = safe_get(meta, "run_ts_utc", "N/A")
    stock_no = safe_get(meta, "stock_no", "N/A")
    window_n = safe_get(meta, "window_n", None)
    aligned_last_date = safe_get(meta, "aligned_last_date", None)

    aligned = (normalize_date_key(aligned_last_date) == normalize_date_key(price_last_date))
    align_tag = "ALIGNED" if aligned else "MISALIGNED"
    if not aligned:
        dq_extra.append("CHIP_OVERLAY_MISALIGNED")

    try:
        if (window_n is not None) and (expect_window_n is not None) and (int(window_n) != int(expect_window_n)):
            dq_extra.append("CHIP_OVERLAY_WINDOW_MISMATCH")
    except Exception:
        dq_extra.append("CHIP_OVERLAY_WINDOW_MISMATCH")

    borrow = safe_get(data, "borrow_summary", {}) or {}
    t86 = safe_get(data, "t86_agg", {}) or {}
    etf_units = safe_get(data, "etf_units", {}) or {}
    etf_units_dq = safe_get(etf_units, "dq", []) or []

    total3_sum = safe_get(t86, "total3_net_shares_sum")
    foreign_sum = safe_get(t86, "foreign_net_shares_sum")
    trust_sum = safe_get(t86, "trust_net_shares_sum")
    dealer_sum = safe_get(t86, "dealer_net_shares_sum")

    b_asof = safe_get(borrow, "asof_date")
    b_shares = safe_get(borrow, "borrow_shares")
    b_shares_chg = safe_get(borrow, "borrow_shares_chg_1d")
    b_mv = safe_get(borrow, "borrow_mv_ntd")
    b_mv_chg = safe_get(borrow, "borrow_mv_ntd_chg_1d")

    quick = (
        f"- chip_overlay(T86+TWT72U,{expect_window_n}D): "
        f"total3_5D={fmt_int(total3_sum)}; foreign={fmt_int(foreign_sum)}; trust={fmt_int(trust_sum)}; dealer={fmt_int(dealer_sum)}; "
        f"borrow_shares={fmt_int(b_shares)} (Δ1D={fmt_int(b_shares_chg)}); borrow_mv(億)={fmt_yi_from_ntd(b_mv)} (Δ1D={fmt_yi_from_ntd(b_mv_chg)}); "
        f"asof={b_asof}; price_last_date={price_last_date} ({align_tag})"
    )

    lines.append("## Chip Overlay（籌碼：TWSE T86 + TWT72U）")
    lines.append("")
    lines.append(f"- overlay_generated_at_utc: `{run_ts_utc}`")
    lines.append(f"- stock_no: `{stock_no}`")
    lines.append(f"- overlay_window_n: `{window_n if window_n is not None else 'N/A'}` (expect={expect_window_n})")
    lines.append(
        f"- date_alignment: overlay_aligned_last_date=`{aligned_last_date}` vs price_last_date=`{price_last_date}` => **{align_tag}**"
    )
    lines.append("")

    lines.append("### Borrow Summary（借券：TWT72U）")
    lines.append("")
    lines.append(
        md_table_kv(
            [
                ["asof_date", str(b_asof) if b_asof is not None else "N/A"],
                ["borrow_shares", fmt_int(b_shares)],
                ["borrow_shares_chg_1d", fmt_int(b_shares_chg)],
                ["borrow_mv_ntd(億)", fmt_yi_from_ntd(b_mv)],
                ["borrow_mv_ntd_chg_1d(億)", fmt_yi_from_ntd(b_mv_chg)],
            ]
        )
    )
    lines.append("")

    lines.append(f"### T86 Aggregate（法人：{expect_window_n}D sum）")
    lines.append("")
    days_used = safe_get(t86, "days_used", []) or []
    lines.append(
        md_table_kv(
            [
                ["days_used", ", ".join([str(x) for x in days_used]) if days_used else "N/A"],
                ["foreign_net_shares_sum", fmt_int(foreign_sum)],
                ["trust_net_shares_sum", fmt_int(trust_sum)],
                ["dealer_net_shares_sum", fmt_int(dealer_sum)],
                ["total3_net_shares_sum", fmt_int(total3_sum)],
            ]
        )
    )
    lines.append("")

    lines.append("### ETF Units（受益權單位）")
    lines.append("")
    lines.append(
        md_table_kv(
            [
                ["units_outstanding", fmt_int(safe_get(etf_units, "units_outstanding"))],
                ["units_chg_1d", fmt_int(safe_get(etf_units, "units_chg_1d"))],
                ["dq", ", ".join([str(x) for x in etf_units_dq]) if etf_units_dq else "(none)"],
            ]
        )
    )
    lines.append("")

    lines.append("### Chip Overlay Sources")
    lines.append("")
    lines.append(f"- T86 template: `{safe_get(sources, 't86_tpl', 'N/A')}`")
    lines.append(f"- TWT72U template: `{safe_get(sources, 'twt72u_tpl', 'N/A')}`")
    lines.append("")

    if root_dq or etf_units_dq:
        lines.append("### Chip Overlay DQ")
        lines.append("")
        if root_dq:
            for fl in root_dq:
                lines.append(f"- {fl}")
        if etf_units_dq:
            for fl in etf_units_dq:
                lines.append(f"- {fl}")
        lines.append("")

    for fl in root_dq:
        if isinstance(fl, str) and fl.strip():
            dq_extra.append(f"CHIP_OVERLAY:{fl}")
    for fl in etf_units_dq:
        if isinstance(fl, str) and fl.strip():
            dq_extra.append(f"CHIP_OVERLAY:{fl}")

    return lines, quick, dq_extra


def _pick_forward_blocks(s: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], str, str, int, int]:
    meta = s.get("meta", {}) or {}
    days20 = int(safe_get(meta, "fwd_days", 20))
    days10 = int(safe_get(meta, "fwd_days_short", 10))

    fwd20 = s.get("forward_mdd_clean", None)
    label20 = f"forward_mdd_clean_{days20}D"
    if not isinstance(fwd20, dict) or not fwd20:
        fwd20 = s.get("forward_mdd", {}) or {}
        label20 = f"forward_mdd_{days20}D"

    fwd10 = s.get("forward_mdd10_clean", None)
    label10 = f"forward_mdd_clean_{days10}D"
    if not isinstance(fwd10, dict) or not fwd10:
        fwd10 = s.get("forward_mdd10", None)
        label10 = f"forward_mdd_{days10}D"
    if not isinstance(fwd10, dict) or not fwd10:
        fwd10 = {}

    return fwd20, fwd10, label20, label10, days20, days10


def _infer_forward_mode_primary(meta: Dict[str, Any], fwd20_label: str) -> str:
    v = safe_get(meta, "forward_mode_primary", None)
    if isinstance(v, str) and v.strip():
        return v.strip()
    if isinstance(fwd20_label, str) and "clean" in fwd20_label:
        return "clean"
    if isinstance(fwd20_label, str) and fwd20_label.startswith("forward_mdd_"):
        return "raw"
    return "N/A"


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _best_price_used(latest: Dict[str, Any]) -> Optional[float]:
    for k in ["price_used", "adjclose", "close"]:
        v = _to_float(safe_get(latest, k))
        if v is not None:
            return v
    return None


def _calc_level(price: Optional[float], mdd: Optional[float]) -> Optional[float]:
    if price is None or mdd is None:
        return None
    try:
        return float(price) * (1.0 + float(mdd))
    except Exception:
        return None


def build_deterministic_action_block(
    *,
    meta: Dict[str, Any],
    latest: Dict[str, Any],
    trend: Dict[str, Any],
    vol: Dict[str, Any],
    regime: Dict[str, Any],
    fwd20: Dict[str, Any],
    fwd10: Dict[str, Any],
    dq_flags: List[str],
    margin_info: Optional[Dict[str, Any]],
    accumulate_z: float,
    no_chase_z: float,
) -> List[str]:
    """
    Deterministic, report-only action guidance.
    Uses:
      - latest.state, latest.bb_z, latest.price_used
      - regime.allowed, regime.inputs.rv_ann_pctl, regime.tag
      - trend.state
      - forward_mdd quantiles (unconditional)
      - (optional) margin_info.total_state when aligned
    """
    lines: List[str] = []
    lines.append("## Deterministic Action (report-only; non-predictive)")
    lines.append("")
    lines.append("- policy: deterministic rules on existing stats fields only (no forecast; no chip dependence)")
    lines.append("")

    last_date = safe_get(meta, "last_date", "N/A")
    price = _best_price_used(latest)
    state = str(safe_get(latest, "state", "N/A"))
    bb_z = _to_float(safe_get(latest, "bb_z"))
    trend_state = str(safe_get(trend, "state", "N/A"))

    allowed = bool(safe_get(regime, "allowed", False))
    tag = str(safe_get(regime, "tag", "N/A"))
    inputs = safe_get(regime, "inputs", {}) or {}
    rv_pctl = _to_float(safe_get(inputs, "rv_ann_pctl"))
    params = safe_get(regime, "params", {}) or {}
    rv_pctl_max = _to_float(safe_get(params, "rv_pctl_max"))
    if rv_pctl_max is None:
        rv_pctl_max = 60.0

    # margin (optional, aligned only)
    margin_state_use = "N/A"
    margin_note = "margin: N/A"
    if isinstance(margin_info, dict) and margin_info:
        if bool(margin_info.get("aligned", False)):
            margin_state_use = str(margin_info.get("total_state", "N/A"))
            margin_note = f"margin(aligned): total_state={margin_state_use}, total_sum={margin_info.get('total_sum', 'N/A')}"
        else:
            margin_note = "margin: MISALIGNED (ignored in action)"
            margin_state_use = "MISALIGNED"

    # DQ core
    flags_str = [str(x) for x in dq_flags if isinstance(x, str)]
    dq_core_str, _ = _dq_core_and_fwd_summary(flags_str)

    # Determine bucket
    state_upper = ("UPPER" in state)
    state_lower = ("LOWER" in state)

    decision_path: List[str] = []
    if not allowed:
        action_bucket = "HOLD_DEFENSIVE_ONLY"
        decision_path.append("regime.allowed=false => gate_closed")
    else:
        decision_path.append("regime.allowed=true => gate_open")
        if state_upper or (bb_z is not None and bb_z >= float(no_chase_z)):
            action_bucket = "NO_CHASE"
            decision_path.append(f"upper_stretch: state_has_UPPER={str(state_upper).lower()} or bb_z>={no_chase_z}")
        elif state_lower or (bb_z is not None and bb_z <= float(accumulate_z)):
            action_bucket = "ACCUMULATE_TRANCHE"
            decision_path.append(f"accumulate_zone: state_has_LOWER={str(state_lower).lower()} or bb_z<={accumulate_z}")
        else:
            action_bucket = "BASE_DCA_ONLY"
            decision_path.append("mid_band => base_dca_only")

    # Conservative leverage/pledge policy (report-only)
    # Default: disallow leverage when gate closed OR in upper stretch OR market deleveraging (aligned).
    pledge_policy = "DISALLOW"
    pledge_reason: List[str] = []
    if not allowed:
        pledge_reason.append("regime gate closed")
    if action_bucket in ("NO_CHASE", "HOLD_DEFENSIVE_ONLY"):
        pledge_reason.append(f"action_bucket={action_bucket}")
    if margin_state_use == "DELEVERAGING":
        pledge_reason.append("market deleveraging (margin 5D)")
    if not pledge_reason:
        pledge_policy = "CONSIDER_ONLY_WITH_OWN_RULES"
        pledge_reason.append("no hard veto triggered (still risk-managed)")

    # Build tranche levels from unconditional quantiles (reference only; not conditional on state)
    tranche_rows: List[List[str]] = []
    if price is not None:
        # 10D
        p10_10 = _to_float(safe_get(fwd10, "p10"))
        p05_10 = _to_float(safe_get(fwd10, "p05"))
        # 20D
        p10_20 = _to_float(safe_get(fwd20, "p10"))
        p05_20 = _to_float(safe_get(fwd20, "p05"))

        def add_row(label: str, mdd: Optional[float]):
            if mdd is None:
                return
            lvl = _calc_level(price, mdd)
            tranche_rows.append(
                [
                    label,
                    fmt_signed_pct2(float(mdd) * 100.0),
                    fmt_price2(lvl),
                ]
            )

        add_row("10D p10 (uncond)", p10_10)
        add_row("10D p05 (uncond)", p05_10)
        add_row("20D p10 (uncond)", p10_20)
        add_row("20D p05 (uncond)", p05_20)

    # Present inputs
    lines.append(md_table_kv([
        ["last_date", str(last_date)],
        ["price_used", fmt_price2(price)],
        ["bb_state", state],
        ["bb_z", fmt4(bb_z)],
        ["trend_state", trend_state],
        ["regime_tag", f"**{tag}**"],
        ["regime_allowed", str(allowed).lower()],
        ["rv20_percentile", fmt2(rv_pctl)],
        ["rv_pctl_max", fmt2(rv_pctl_max)],
        ["dq_core", dq_core_str],
        ["margin_note", margin_note],
    ]))
    lines.append("")

    # Present bucket + path
    lines.append(md_table_kv([
        ["action_bucket", f"**{action_bucket}**"],
        ["accumulate_z_threshold", fmt4(accumulate_z)],
        ["no_chase_z_threshold", fmt4(no_chase_z)],
        ["pledge_policy", f"**{pledge_policy}**"],
        ["pledge_veto_reasons", "; ".join(pledge_reason) if pledge_reason else "(none)"],
    ]))
    lines.append("")
    lines.append("### decision_path")
    for p in decision_path:
        lines.append(f"- {p}")
    lines.append("")

    if tranche_rows:
        lines.append("### tranche_levels (reference; unconditional forward_mdd quantiles)")
        lines.append("")
        lines.append("| level | drawdown | price_level |")
        lines.append("|---|---:|---:|")
        for a, b, c in tranche_rows:
            lines.append(f"| {a} | {b} | {c} |")
        lines.append("")
        lines.append("- note: tranche_levels are derived from *unconditional* forward_mdd quantiles; they are not conditioned on current bb_state.")
        lines.append("")

    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default="report.md")
    ap.add_argument("--tail_days", type=int, default=15)
    ap.add_argument("--tail_n", type=int, default=None)

    ap.add_argument("--margin_json", default="taiwan_margin_cache/latest.json")
    ap.add_argument("--margin_window_n", type=int, default=5)
    ap.add_argument("--margin_threshold_yi", type=float, default=100.0)

    ap.add_argument("--chip_overlay_json", default=None)
    ap.add_argument("--chip_window_n", type=int, default=5)

    # deterministic action params
    ap.add_argument("--accumulate_z", type=float, default=-1.5, help="bb_z <= accumulate_z => ACCUMULATE_TRANCHE")
    ap.add_argument("--no_chase_z", type=float, default=1.5, help="bb_z >= no_chase_z => NO_CHASE")

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

    fwd20, fwd10, fwd20_label, fwd10_label, fwd_days, fwd_days_short = _pick_forward_blocks(s)

    dq = s.get("dq", {"flags": [], "notes": []}) or {}
    dq_flags = dq.get("flags") or []
    dq_notes = dq.get("notes") or []

    trend = s.get("trend", {}) or {}
    vol = s.get("vol", {}) or {}
    atr = s.get("atr", {}) or {}
    regime = s.get("regime", {}) or {}

    ticker = safe_get(meta, "ticker", "0050.TW")
    last_date = safe_get(meta, "last_date", "N/A")
    bb_window = safe_get(meta, "bb_window", 60)
    bb_k = safe_get(meta, "bb_k", 2.0)
    price_calc = safe_get(meta, "price_calc", "adjclose")
    data_source = safe_get(meta, "data_source", "yfinance_yahoo_or_twse_fallback")

    forward_mode_primary = _infer_forward_mode_primary(meta, fwd20_label)

    state = safe_get(latest, "state", "N/A")
    bb_z = safe_get(latest, "bb_z")

    bb_pos_clip = safe_get(latest, "bb_pos")
    bb_pos_raw = safe_get(latest, "bb_pos_raw")
    if bb_pos_raw is None:
        bb_pos_raw = safe_get(latest, "pos_raw")

    dist_to_lower = safe_get(latest, "dist_to_lower_pct")
    dist_to_upper = safe_get(latest, "dist_to_upper_pct")

    above_upper_pct_str, below_lower_pct_str = _above_upper_lower_from_dist(dist_to_upper, dist_to_lower)

    bw_geo = safe_get(latest, "band_width_geo_pct")
    if bw_geo is None:
        bw_geo = safe_get(latest, "band_width_pct")
    bw_std = safe_get(latest, "band_width_std_pct")

    chip_path = args.chip_overlay_json
    if chip_path is None:
        chip_path = os.path.join(args.cache_dir, "chip_overlay.json")

    # optional margin struct (for deterministic action block)
    margin_json = read_margin_latest(args.margin_json)
    margin_info: Optional[Dict[str, Any]] = None
    if margin_json is not None:
        try:
            margin_info = margin_overlay_struct(
                margin_json=margin_json,
                price_last_date=str(last_date),
                window_n=int(args.margin_window_n),
                threshold_yi=float(args.margin_threshold_yi),
            )
        except Exception:
            margin_info = None

    # ===== report =====
    lines: List[str] = []
    lines.append("# 0050 BB(60,2) + forward_mdd Report")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{utc_now_iso()}`")
    lines.append(f"- build_script_fingerprint: `{BUILD_SCRIPT_FINGERPRINT}`")
    lines.append(f"- stats_path: `{stats_path}`")
    lines.append(f"- data_source: `{data_source}`")
    lines.append(f"- ticker: `{ticker}`")
    lines.append(f"- last_date: `{last_date}`")
    lines.append(f"- bb_window,k: `{bb_window}`, `{bb_k}`")
    lines.append(f"- forward_window_days: `{fwd_days}`")
    lines.append(f"- forward_window_days_short: `{fwd_days_short}`")
    lines.append(f"- forward_mode_primary: `{forward_mode_primary}`")
    lines.append(f"- price_calc: `{price_calc}`")
    lines.append(f"- chip_overlay_path: `{chip_path}`")
    lines.append("")

    # ===== Quick summary =====
    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{state}**; "
        f"bb_z={fmt4(bb_z)}; "
        f"pos={fmt4(bb_pos_clip)} (raw={fmt4(bb_pos_raw)}); "
        f"bw_geo={fmt_pct2(bw_geo)}; bw_std={fmt_pct2(bw_std)}"
    )

    dq_core_str, fwd_outlier_str = _dq_core_and_fwd_summary([str(x) for x in dq_flags if isinstance(x, str)])
    lines.append(
        f"- dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}; "
        f"above_upper={above_upper_pct_str}; below_lower={below_lower_pct_str}; "
        f"DQ={dq_core_str}; FWD_OUTLIER={fwd_outlier_str}"
    )

    lines.append(build_forward_line(fwd20_label, fwd20, dq_flags, fwd_days))
    if isinstance(fwd10, dict) and fwd10:
        lines.append(build_forward_line(fwd10_label, fwd10, dq_flags, fwd_days_short))

    if isinstance(trend, dict) and trend:
        lines.append(build_trend_line(trend))
    if isinstance(vol, dict) and vol and isinstance(atr, dict) and atr:
        lines.append(build_vol_line(vol, atr))

    reg_line = build_regime_line(regime)
    if reg_line:
        lines.append(reg_line)

    if margin_json is not None:
        _, margin_quick = margin_overlay_block(
            margin_json=margin_json,
            price_last_date=str(last_date),
            window_n=int(args.margin_window_n),
            threshold_yi=float(args.margin_threshold_yi),
        )
        if margin_quick:
            lines.append(margin_quick)

    chip_json = read_chip_overlay(chip_path)
    chip_dq_extra: List[str] = []
    if chip_json is not None:
        _, chip_quick, chip_dq_extra = chip_overlay_block(
            chip_json=chip_json,
            price_last_date=str(last_date),
            expect_window_n=int(args.chip_window_n),
        )
        if chip_quick:
            lines.append(chip_quick)
    else:
        lines.append(f"- chip_overlay(T86+TWT72U): N/A (missing `{chip_path}`) [DQ:CHIP_OVERLAY_MISSING]")
        chip_dq_extra.append("CHIP_OVERLAY_MISSING")

    lines.append("")

    # ===== Deterministic Action Block =====
    lines.extend(
        build_deterministic_action_block(
            meta=meta,
            latest=latest,
            trend=trend,
            vol=vol,
            regime=regime,
            fwd20=fwd20,
            fwd10=fwd10,
            dq_flags=dq_flags,
            margin_info=margin_info,
            accumulate_z=float(args.accumulate_z),
            no_chase_z=float(args.no_chase_z),
        )
    )

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
                ["pos_in_band (clipped)", fmt4(bb_pos_clip)],
                ["pos_in_band_raw (unclipped)", fmt4(bb_pos_raw)],
                ["dist_to_lower", fmt_pct2(dist_to_lower)],
                ["dist_to_upper", fmt_pct2(dist_to_upper)],
                ["above_upper_pct", above_upper_pct_str],
                ["below_lower_pct", below_lower_pct_str],
                ["band_width_geo_pct (upper/lower-1)", fmt_pct2(bw_geo)],
                ["band_width_std_pct ((upper-lower)/ma)", fmt_pct2(bw_std)],
            ]
        )
    )
    lines.append("")

    # ===== Trend & Vol =====
    if (isinstance(trend, dict) and trend) or (isinstance(vol, dict) and vol) or (isinstance(atr, dict) and atr):
        lines.append("## Trend & Vol Filters")
        lines.append("")
        if isinstance(trend, dict) and trend:
            lines.append(
                md_table_kv(
                    [
                        ["trend_ma_days", str(safe_get(trend, "trend_ma_days", "N/A"))],
                        ["trend_ma_last", fmt4(safe_get(trend, "trend_ma_last"))],
                        ["trend_slope_days", str(safe_get(trend, "trend_slope_days", "N/A"))],
                        ["trend_slope_pct", fmt_pct2(safe_get(trend, "trend_slope_pct"))],
                        ["price_vs_trend_ma_pct", fmt_pct2(safe_get(trend, "price_vs_trend_ma_pct"))],
                        ["trend_state", str(safe_get(trend, "state", "N/A"))],
                    ]
                )
            )
            lines.append("")

        if isinstance(vol, dict) and vol:
            rv_ann = safe_get(vol, "rv_ann")
            rv_pct = None if rv_ann is None else float(rv_ann) * 100.0
            lines.append(
                md_table_kv(
                    [
                        ["rv_days", str(safe_get(vol, "rv_days", "N/A"))],
                        ["rv_ann(%)", fmt_pct1(rv_pct)],
                        ["rv20_percentile", fmt2(safe_get(vol, "rv_ann_pctl"))],
                        ["rv_hist_n", str(safe_get(vol, "rv_hist_n", "N/A"))],
                        [
                            "rv_hist_q20(%)",
                            fmt_pct1(
                                None
                                if safe_get(vol, "rv_hist_q20") is None
                                else float(safe_get(vol, "rv_hist_q20")) * 100.0
                            ),
                        ],
                        [
                            "rv_hist_q50(%)",
                            fmt_pct1(
                                None
                                if safe_get(vol, "rv_hist_q50") is None
                                else float(safe_get(vol, "rv_hist_q50")) * 100.0
                            ),
                        ],
                        [
                            "rv_hist_q80(%)",
                            fmt_pct1(
                                None
                                if safe_get(vol, "rv_hist_q80") is None
                                else float(safe_get(vol, "rv_hist_q80")) * 100.0
                            ),
                        ],
                    ]
                )
            )
            lines.append("")

        if isinstance(atr, dict) and atr:
            lines.append(
                md_table_kv(
                    [
                        ["atr_days", str(safe_get(atr, "atr_days", "N/A"))],
                        ["atr", fmt4(safe_get(atr, "atr"))],
                        ["atr_pct", fmt_pct2(safe_get(atr, "atr_pct"))],
                        ["tr_mode", str(safe_get(atr, "tr_mode", "N/A"))],
                    ]
                )
            )
            lines.append("")

    # ===== Regime =====
    lines.append("## Regime Tag")
    lines.append("")
    if isinstance(regime, dict) and regime:
        inputs = safe_get(regime, "inputs", {}) or {}
        params = safe_get(regime, "params", {}) or {}
        passes = safe_get(regime, "passes", {}) or {}
        reasons = safe_get(regime, "reasons", []) or []

        rv_ann = safe_get(inputs, "rv_ann")
        rv_pct = None if rv_ann is None else float(rv_ann) * 100.0

        lines.append(
            md_table_kv(
                [
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
                ]
            )
        )
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

    def has_min_audit_block(fwd: Dict[str, Any]) -> bool:
        return isinstance(fwd, dict) and all(
            k in fwd for k in ["min_entry_date", "min_entry_price", "min_future_date", "min_future_price"]
        )

    # 20D
    lines.append("### forward_mdd (primary)")
    lines.append("")
    lines.append(f"- block_used: `{fwd20_label}`")
    lines.append(f"- definition: `{safe_get(fwd20, 'definition', 'N/A')}`")
    lines.append("")
    lines.append("| quantile | value |")
    lines.append("|---|---:|")
    lines.append(f"| p50 | {fmt4(safe_get(fwd20, 'p50'))} |")
    lines.append(f"| p25 | {fmt4(safe_get(fwd20, 'p25'))} |")
    lines.append(f"| p10 | {fmt4(safe_get(fwd20, 'p10'))} |")
    lines.append(f"| p05 | {fmt4(safe_get(fwd20, 'p05'))} |")
    lines.append(f"| min | {fmt4(safe_get(fwd20, 'min'))} |")
    lines.append("")
    lines.append("#### forward_mdd Min Audit Trail")
    lines.append("")
    if has_min_audit_block(fwd20):
        lines.append("| item | value |")
        lines.append("|---|---:|")
        lines.append(f"| min_entry_date | {safe_get(fwd20, 'min_entry_date')} |")
        lines.append(f"| min_entry_price | {fmt4(safe_get(fwd20, 'min_entry_price'))} |")
        lines.append(f"| min_future_date | {safe_get(fwd20, 'min_future_date')} |")
        lines.append(f"| min_future_price | {fmt4(safe_get(fwd20, 'min_future_price'))} |")
    else:
        keys = sorted(list(fwd20.keys())) if isinstance(fwd20, dict) else []
        lines.append("- min audit fields are missing in forward block.")
        lines.append(f"- forward_mdd keys: `{', '.join(keys)}`")
    lines.append("")

    # 10D
    lines.append("### forward_mdd10 (primary)")
    lines.append("")
    if isinstance(fwd10, dict) and fwd10:
        lines.append(f"- block_used: `{fwd10_label}`")
        lines.append(f"- definition: `{safe_get(fwd10, 'definition', 'N/A')}`")
        lines.append("")
        lines.append("| quantile | value |")
        lines.append("|---|---:|")
        lines.append(f"| p50 | {fmt4(safe_get(fwd10, 'p50'))} |")
        lines.append(f"| p25 | {fmt4(safe_get(fwd10, 'p25'))} |")
        lines.append(f"| p10 | {fmt4(safe_get(fwd10, 'p10'))} |")
        lines.append(f"| p05 | {fmt4(safe_get(fwd10, 'p05'))} |")
        lines.append(f"| min | {fmt4(safe_get(fwd10, 'min'))} |")
        lines.append("")
        lines.append("#### forward_mdd10 Min Audit Trail")
        lines.append("")
        if has_min_audit_block(fwd10):
            lines.append("| item | value |")
            lines.append("|---|---:|")
            lines.append(f"| min_entry_date | {safe_get(fwd10, 'min_entry_date')} |")
            lines.append(f"| min_entry_price | {fmt4(safe_get(fwd10, 'min_entry_price'))} |")
            lines.append(f"| min_future_date | {safe_get(fwd10, 'min_future_date')} |")
            lines.append(f"| min_future_price | {fmt4(safe_get(fwd10, 'min_future_price'))} |")
        else:
            keys = sorted(list(fwd10.keys())) if isinstance(fwd10, dict) else []
            lines.append("- min audit fields are missing in forward block.")
            lines.append(f"- forward_mdd10 keys: `{', '.join(keys)}`")
        lines.append("")
    else:
        lines.append("- forward_mdd10 block is missing in stats_latest.json.")
        lines.append("")

    # ===== Chip overlay =====
    if chip_json is not None:
        cb_lines, _, _ = chip_overlay_block(
            chip_json=chip_json,
            price_last_date=str(last_date),
            expect_window_n=int(args.chip_window_n),
        )
        lines.extend(cb_lines)
    else:
        lines.append("## Chip Overlay（籌碼：TWSE T86 + TWT72U）")
        lines.append("")
        lines.append(f"- chip_overlay: `N/A` (missing `{chip_path}`)")
        lines.append("")

    # ===== Margin overlay =====
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
    flags_str = [str(x) for x in dq_flags if isinstance(x, str)]
    if not flags_str:
        lines.append("- (none)")
    else:
        for fl in flags_str:
            lines.append(f"- {fl}")

    notes_str = [str(x) for x in dq_notes if isinstance(x, str) and str(x).strip()]
    if notes_str:
        lines.append("")
        lines.append("### DQ Notes")
        lines.append("")
        for nt in notes_str:
            lines.append(f"- note: {nt}")

    if chip_dq_extra:
        lines.append("")
        lines.append("### Chip Overlay DQ (extra)")
        for fl in chip_dq_extra:
            lines.append(f"- {fl}")

    lines.append("")

    # ===== Caveats =====
    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    lines.append("- Deterministic Action 是規則輸出（report-only），不代表可獲利保證。")
    lines.append("- tranche_levels 使用的是 *unconditional* forward_mdd 分位數（非條件化），僅作風險尺。")
    lines.append("- pos_in_band 會顯示 clipped 值（0..1）與 raw 值（可超界，用於稽核）。")
    lines.append("- dist_to_upper/lower 可能為負值（代表超出通道）；報表已額外提供 above_upper / below_lower 以避免符號誤讀。")
    lines.append("- band_width 同時提供兩種定義：geo=(upper/lower-1)、std=(upper-lower)/ma；請勿混用解讀。")
    lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，為未還原價格，forward_mdd 可能被除權息/企業行動污染，DQ 會標示。")
    lines.append("- Trend/Vol/ATR 是濾網與風險量級提示，不是進出場保證；資料不足會以 DQ 明示。")
    lines.append("- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；日期不對齊時 deterministic action 會忽略其狀態。")
    lines.append("- Chip overlay（T86/TWT72U）為籌碼/借券描述；ETF 申贖、避險行為可能影響解讀，建議只做輔助註記。")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())