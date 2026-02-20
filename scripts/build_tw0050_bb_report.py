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
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_bb_report@2026-02-21.v15"


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
        "PLEDGE_",
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
    Supports patterns:
      - FWD_MDD_OUTLIER_MIN_RAW_20D
      - FWD_MDD_OUTLIER_MIN_RAW_20D_SOMETHING
      - FWD_MDD_OUTLIER_MIN_RAW_20D|... (we only parse the *_20D part if present)
    """
    days: List[int] = []
    for f in dq_flags:
        if not isinstance(f, str):
            continue
        if "FWD_MDD_OUTLIER_MIN_RAW_" not in f:
            continue
        try:
            # find token like "20D"
            parts = f.split("_")
            for tok in parts[::-1]:
                if tok.endswith("D") and tok[:-1].isdigit():
                    days.append(int(tok[:-1]))
                    break
        except Exception:
            continue
    return sorted(set(days))


def _dq_core_and_fwd_summary(dq_flags: List[str]) -> Tuple[str, str]:
    flags = [str(x) for x in dq_flags if isinstance(x, str)]
    core = [f for f in flags if "FWD_MDD_OUTLIER_MIN_RAW_" not in f]
    days = _extract_fwd_outlier_days(flags)
    fwd = "(none)" if not days else ",".join([f"{d}D" for d in days])
    return _dq_compact(core), fwd


def _filter_fwd_outlier_flags_for_horizon(dq_flags: List[str], horizon_days: int) -> List[str]:
    """
    Accept both:
      - exact suffix "_{horizon_days}D"
      - any flag containing "_{horizon_days}D" (e.g., "_20D_SOMETHING")
    """
    flags = [f for f in dq_flags if isinstance(f, str)]
    key = f"_{horizon_days}D"
    specific = sorted([f for f in flags if ("FWD_MDD_OUTLIER_MIN_RAW" in f and key in f)])
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
    bd = safe_get(meta, "break_detection", {}) or {}
    v = safe_get(bd, "forward_mode_primary", None)
    if isinstance(v, str) and v.strip():
        return v.strip()

    v2 = safe_get(meta, "forward_mode_primary", None)
    if isinstance(v2, str) and v2.strip():
        return v2.strip()

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


# ---------------- Pledge block extraction (from stats) ----------------

def extract_pledge_from_stats(s: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a normalized pledge structure:
      {
        "present": bool,
        "version": str,
        "scope": str,
        "decision": {action_bucket, pledge_policy, veto_reasons[]},
        "thresholds": {accumulate_z_threshold, no_chase_z_threshold, require_regime_allowed},
        "uncond_levels": [{"label","drawdown","price_level"}],
        "price_anchor": float|None,
        "note": str|None,
        "dq": []  # optional local dq flags for renderer
      }
    """
    out: Dict[str, Any] = {
        "present": False,
        "version": "N/A",
        "scope": "N/A",
        "decision": {},
        "thresholds": {},
        "uncond_levels": [],
        "price_anchor": None,
        "note": None,
        "dq": [],
    }
    pledge = safe_get(s, "pledge", None)
    if not isinstance(pledge, dict) or not pledge:
        return out

    out["present"] = True
    out["version"] = str(safe_get(pledge, "version", "N/A"))
    out["scope"] = str(safe_get(pledge, "scope", "N/A"))

    dec = safe_get(pledge, "decision", {}) or {}
    out["decision"] = {
        "action_bucket": safe_get(dec, "action_bucket", None),
        "pledge_policy": safe_get(dec, "pledge_policy", None),
        "veto_reasons": safe_get(dec, "veto_reasons", []) or [],
    }

    thr = safe_get(pledge, "thresholds", {}) or {}
    out["thresholds"] = {
        "accumulate_z_threshold": safe_get(thr, "accumulate_z_threshold", None),
        "no_chase_z_threshold": safe_get(thr, "no_chase_z_threshold", None),
        "require_regime_allowed": safe_get(thr, "require_regime_allowed", None),
    }

    un = safe_get(pledge, "unconditional_tranche_levels", {}) or {}
    out["price_anchor"] = _to_float(safe_get(un, "price_anchor"))
    out["note"] = safe_get(un, "note", None)

    levels = safe_get(un, "levels", []) or []
    norm_levels: List[Dict[str, Any]] = []
    if isinstance(levels, list):
        for it in levels:
            if not isinstance(it, dict):
                continue
            norm_levels.append(
                {
                    "label": str(safe_get(it, "label", "N/A")),
                    "drawdown": _to_float(safe_get(it, "drawdown")),
                    "price_level": _to_float(safe_get(it, "price_level")),
                }
            )
    out["uncond_levels"] = norm_levels
    return out


def pledge_decision_is_usable(p: Dict[str, Any]) -> bool:
    if not isinstance(p, dict) or not p.get("present", False):
        return False
    dec = p.get("decision", {}) or {}
    pol = safe_get(dec, "pledge_policy", None)
    if not isinstance(pol, str) or not pol.strip():
        return False
    return True


def _string_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        out = []
        for it in x:
            if isinstance(it, str) and it.strip():
                out.append(it.strip())
        return out
    if isinstance(x, str) and x.strip():
        return [x.strip()]
    return []


def _join_semicolon(xs: List[str]) -> str:
    ys = [x for x in xs if isinstance(x, str) and x.strip()]
    return "; ".join(ys) if ys else "(none)"


# ---------------- Deterministic action (renderer) + pledge merge ----------------

def compute_renderer_action_bucket(
    *,
    latest_state: str,
    bb_z: Optional[float],
    regime_allowed: bool,
    accumulate_z: float,
    no_chase_z: float,
) -> Tuple[str, List[str]]:
    """
    Returns (action_bucket, decision_path_lines)
    Note: This is the existing renderer logic (v1-style), gated by regime_allowed.
    """
    state_upper = ("UPPER" in latest_state)
    state_lower = ("LOWER" in latest_state)

    path: List[str] = []
    if not regime_allowed:
        path.append("regime.allowed=false => gate_closed")
        return "HOLD_DEFENSIVE_ONLY", path

    path.append("regime.allowed=true => gate_open")
    if state_upper or (bb_z is not None and bb_z >= float(no_chase_z)):
        path.append(f"upper_stretch: state_has_UPPER={str(state_upper).lower()} or bb_z>={no_chase_z}")
        return "NO_CHASE", path

    if state_lower or (bb_z is not None and bb_z <= float(accumulate_z)):
        path.append(f"accumulate_zone: state_has_LOWER={str(state_lower).lower()} or bb_z<={accumulate_z}")
        return "ACCUMULATE_TRANCHE", path

    path.append("mid_band => base_dca_only")
    return "BASE_DCA_ONLY", path


def compute_renderer_pledge_policy(
    *,
    action_bucket: str,
    regime_allowed: bool,
    margin_info: Optional[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """
    Renderer overlay policy (v1):
      - DISALLOW when regime gate closed OR action bucket is NO_CHASE/HOLD_DEFENSIVE_ONLY
      - DISALLOW when margin aligned and DELEVERAGING
      - otherwise CONSIDER_ONLY_WITH_OWN_RULES
    """
    reasons: List[str] = []
    if not regime_allowed:
        reasons.append("regime gate closed")
    if action_bucket in ("NO_CHASE", "HOLD_DEFENSIVE_ONLY"):
        reasons.append(f"action_bucket={action_bucket}")

    if isinstance(margin_info, dict) and margin_info and bool(margin_info.get("aligned", False)):
        if str(margin_info.get("total_state", "")).upper() == "DELEVERAGING":
            reasons.append("market deleveraging (margin 5D)")

    if reasons:
        return "DISALLOW", reasons
    return "CONSIDER_ONLY_WITH_OWN_RULES", ["no hard veto triggered (still risk-managed)"]


# ---------------- Pledge Guidance v2 (report-only sizing; NOT gated by regime.allowed) ----------------

def compute_pledge_v2_zone(
    *,
    latest_state: str,
    bb_z: Optional[float],
    accumulate_z: float,
    no_chase_z: float,
) -> Tuple[str, List[str]]:
    """
    Zone decision independent of regime.allowed:
      - NO_CHASE if state has UPPER or bb_z >= no_chase_z
      - ACCUMULATE_ZONE if state has LOWER or bb_z <= accumulate_z
      - MID otherwise
    """
    path: List[str] = []
    state_upper = ("UPPER" in latest_state)
    state_lower = ("LOWER" in latest_state)

    if state_upper or (bb_z is not None and bb_z >= float(no_chase_z)):
        path.append(f"no_chase: state_has_UPPER={str(state_upper).lower()} or bb_z>={no_chase_z}")
        return "NO_CHASE", path

    if state_lower or (bb_z is not None and bb_z <= float(accumulate_z)):
        path.append(f"accumulate: state_has_LOWER={str(state_lower).lower()} or bb_z<={accumulate_z}")
        return "ACCUMULATE_ZONE", path

    path.append("mid => wait_or_dca_only")
    return "MID", path


def compute_pledge_v2_sizing(
    *,
    zone: str,
    rv20_pctl: Optional[float],
    margin_info: Optional[Dict[str, Any]],
    dq_flags: List[str],
) -> Dict[str, Any]:
    """
    Report-only sizing proposal.
    Output keys:
      policy: DISALLOW / ALLOW_REDUCED / ALLOW_FULL
      size_factor: 0.0..1.0  (fraction of user's own max pledge capacity; max capacity is external)
      reasons: list[str]
      bands: dict
      multipliers: dict
      cooldown_sessions_hint: int
    """
    out: Dict[str, Any] = {
        "policy": "DISALLOW",
        "size_factor": 0.0,
        "reasons": [],
        "bands": {"pctl_full_le": 60.0, "pctl_half_le": 80.0, "pctl_quarter_le": 90.0},
        "multipliers": {},
        "cooldown_sessions_hint": 0,
    }

    if zone != "ACCUMULATE_ZONE":
        out["reasons"].append(f"zone={zone} (require ACCUMULATE_ZONE)")
        return out

    base_factor = 0.0
    if rv20_pctl is None:
        base_factor = 0.25
        out["reasons"].append("rv20_pctl missing => default conservative 0.25")
    else:
        p = float(rv20_pctl)
        if p <= out["bands"]["pctl_full_le"]:
            base_factor = 1.0
        elif p <= out["bands"]["pctl_half_le"]:
            base_factor = 0.5
        elif p <= out["bands"]["pctl_quarter_le"]:
            base_factor = 0.25
        else:
            base_factor = 0.0
            out["reasons"].append(f"rv20_pctl>{out['bands']['pctl_quarter_le']} => DISALLOW")

    factor = float(base_factor)
    out["multipliers"]["base_from_rv20_pctl"] = factor

    if isinstance(margin_info, dict) and margin_info and bool(margin_info.get("aligned", False)):
        if str(margin_info.get("total_state", "")).upper() == "DELEVERAGING":
            factor *= 0.5
            out["multipliers"]["margin_deleveraging_x"] = 0.5
            out["reasons"].append("margin aligned: DELEVERAGING => size_factor * 0.5 + cooldown hint")
            out["cooldown_sessions_hint"] = 2

    flags = set([str(x) for x in dq_flags if isinstance(x, str)])
    if "PRICE_SERIES_BREAK_DETECTED" in flags:
        factor = min(factor, 0.25)
        out["multipliers"]["dq_price_break_cap"] = 0.25
        out["reasons"].append("DQ: PRICE_SERIES_BREAK_DETECTED => cap size_factor at 0.25")

    if any(f.startswith("YF_") for f in flags) or any(f.startswith("TWSE_") for f in flags):
        factor = min(factor, 0.5)
        out["multipliers"]["dq_source_cap"] = 0.5
        out["reasons"].append("DQ: YF_/TWSE_ flags present => cap size_factor at 0.5")

    factor = max(0.0, min(1.0, float(factor)))
    out["size_factor"] = round(factor, 4)

    if factor <= 0.0:
        out["policy"] = "DISALLOW"
        if not out["reasons"]:
            out["reasons"].append("size_factor<=0")
    elif factor < 1.0:
        out["policy"] = "ALLOW_REDUCED"
        if not out["reasons"]:
            out["reasons"].append("reduced sizing due to risk controls")
    else:
        out["policy"] = "ALLOW_FULL"
        if not out["reasons"]:
            out["reasons"].append("rv20_pctl in low band; no additional caps applied")

    return out


def build_tranche_plan_from_levels(
    tranche_rows: List[List[str]],
    size_factor: float,
) -> Tuple[List[List[str]], str]:
    """
    tranche_rows: [[label, drawdown_str, price_level_str], ...]
    returns:
      plan_rows: [[tranche, level, target_frac_of_max_str, price_level], ...]
      note: str
    """
    if not tranche_rows or size_factor <= 0:
        return [], "no tranche plan (size_factor<=0 or levels missing)"

    m = min(len(tranche_rows), 4)
    levels = tranche_rows[:m]

    if m == 1:
        weights = [1.0]
    elif m == 2:
        weights = [0.5, 0.5]
    elif m == 3:
        weights = [0.4, 0.3, 0.3]
    else:
        weights = [0.4, 0.3, 0.2, 0.1]

    plan: List[List[str]] = []
    for i, (lvl, w) in enumerate(zip(levels, weights), start=1):
        label = str(lvl[0])
        price_level = str(lvl[2])
        frac = size_factor * float(w)  # 0..1
        # IMPORTANT: show fraction as percent
        frac_str = fmt_pct2(frac * 100.0)
        plan.append([f"T{i}", label, frac_str, price_level])

    note = "target_frac_of_max is fraction of your own max pledge capacity (defined outside this report)"
    return plan, note


def build_unconditional_tranche_rows(
    *,
    price: Optional[float],
    fwd20: Dict[str, Any],
    fwd10: Dict[str, Any],
    pledge_stats: Dict[str, Any],
) -> Tuple[List[List[str]], str]:
    """
    Returns tranche_rows: [[label, drawdown_str, price_level_str], ...]
    and source_note.
    """
    tranche_rows: List[List[str]] = []
    un_levels = safe_get(pledge_stats, "uncond_levels", []) or []
    if isinstance(un_levels, list) and un_levels:
        for it in un_levels:
            if not isinstance(it, dict):
                continue
            lbl = str(safe_get(it, "label", "N/A"))
            dd = _to_float(safe_get(it, "drawdown"))
            pl = _to_float(safe_get(it, "price_level"))
            tranche_rows.append([lbl, fmt_signed_pct2(None if dd is None else dd * 100.0), fmt_price2(pl)])
        anchor = safe_get(pledge_stats, "price_anchor", None)
        if anchor is not None:
            return tranche_rows, f"source: stats (price_anchor={fmt_price2(anchor)})"
        return tranche_rows, "source: stats"

    if price is None:
        return [], "source: none (price missing)"

    def add_row(label: str, mdd: Optional[float]):
        if mdd is None:
            return
        try:
            lvl = float(price) * (1.0 + float(mdd))
        except Exception:
            lvl = None
        tranche_rows.append([label, fmt_signed_pct2(float(mdd) * 100.0), fmt_price2(lvl)])

    p10_10 = _to_float(safe_get(fwd10, "p10"))
    p05_10 = _to_float(safe_get(fwd10, "p05"))
    p10_20 = _to_float(safe_get(fwd20, "p10"))
    p05_20 = _to_float(safe_get(fwd20, "p05"))

    add_row("10D_p10_uncond", p10_10)
    add_row("10D_p05_uncond", p05_10)
    add_row("20D_p10_uncond", p10_20)
    add_row("20D_p05_uncond", p05_20)

    return tranche_rows, "source: renderer (computed from forward_mdd quantiles; unconditional reference only)"


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
    pledge_stats: Dict[str, Any],
    accumulate_z_cli: Optional[float],
    no_chase_z_cli: Optional[float],
) -> List[str]:
    """
    Deterministic, report-only action guidance.

    Priority:
      1) pledge decision from stats (if usable) as baseline
      2) renderer overlay computes additional veto (e.g., margin deleveraging)
      3) final pledge_policy = DISALLOW if either baseline or overlay veto says DISALLOW

    Adds:
      - Pledge Guidance v2: report-only sizing proposal not gated by regime.allowed
    """
    lines: List[str] = []
    lines.append("## Deterministic Action (report-only; non-predictive)")
    lines.append("")
    lines.append("- policy: deterministic rules on existing stats fields only (no forecast)")
    lines.append("")

    last_date = safe_get(meta, "last_date", "N/A")
    price = _best_price_used(latest)
    state = str(safe_get(latest, "state", "N/A"))
    bb_z = _to_float(safe_get(latest, "bb_z"))
    trend_state = str(safe_get(trend, "state", "N/A"))

    regime_allowed = bool(safe_get(regime, "allowed", False))
    tag = str(safe_get(regime, "tag", "N/A"))
    inputs = safe_get(regime, "inputs", {}) or {}
    rv_pctl = _to_float(safe_get(inputs, "rv_ann_pctl"))
    params = safe_get(regime, "params", {}) or {}
    rv_pctl_max = _to_float(safe_get(params, "rv_pctl_max"))
    if rv_pctl_max is None:
        rv_pctl_max = 60.0

    acc_thr = accumulate_z_cli
    nc_thr = no_chase_z_cli
    if acc_thr is None:
        acc_thr = _to_float(safe_get(safe_get(pledge_stats, "thresholds", {}), "accumulate_z_threshold"))
    if nc_thr is None:
        nc_thr = _to_float(safe_get(safe_get(pledge_stats, "thresholds", {}), "no_chase_z_threshold"))
    if acc_thr is None:
        acc_thr = -1.5
    if nc_thr is None:
        nc_thr = 1.5

    margin_note = "margin: N/A"
    if isinstance(margin_info, dict) and margin_info:
        if bool(margin_info.get("aligned", False)):
            margin_note = f"margin(aligned): total_state={margin_info.get('total_state','N/A')}, total_sum={margin_info.get('total_sum','N/A')}"
        else:
            margin_note = "margin: MISALIGNED (ignored in overlay)"

    flags_str = [str(x) for x in dq_flags if isinstance(x, str)]
    dq_core_str, _ = _dq_core_and_fwd_summary(flags_str)

    action_bucket_renderer, decision_path = compute_renderer_action_bucket(
        latest_state=state, bb_z=bb_z, regime_allowed=regime_allowed, accumulate_z=acc_thr, no_chase_z=nc_thr
    )
    pledge_policy_renderer, pledge_veto_renderer = compute_renderer_pledge_policy(
        action_bucket=action_bucket_renderer, regime_allowed=regime_allowed, margin_info=margin_info
    )

    pledge_source = "renderer"
    pledge_policy_stats = "N/A"
    pledge_action_bucket_stats = "N/A"
    pledge_veto_stats: List[str] = []
    pledge_version = safe_get(pledge_stats, "version", "N/A")
    pledge_scope = safe_get(pledge_stats, "scope", "N/A")

    if pledge_decision_is_usable(pledge_stats):
        pledge_source = "stats"
        dec = safe_get(pledge_stats, "decision", {}) or {}
        pledge_policy_stats = str(safe_get(dec, "pledge_policy", "N/A"))
        pledge_action_bucket_stats = str(safe_get(dec, "action_bucket", "N/A"))
        pledge_veto_stats = _string_list(safe_get(dec, "veto_reasons", []))

    overlay_applied = False
    final_reasons: List[str] = []
    if pledge_source == "stats":
        final_policy = pledge_policy_stats
        final_reasons.extend([f"stats:{x}" for x in pledge_veto_stats] if pledge_veto_stats else [])
        if str(pledge_policy_renderer).upper() == "DISALLOW" and str(pledge_policy_stats).upper() != "DISALLOW":
            overlay_applied = True
            final_policy = "DISALLOW"
            final_reasons.extend([f"overlay:{x}" for x in pledge_veto_renderer] if pledge_veto_renderer else [])
    else:
        final_policy = pledge_policy_renderer
        final_reasons.extend([f"overlay:{x}" for x in pledge_veto_renderer] if pledge_veto_renderer else [])

    pledge_mismatch = False
    if pledge_source == "stats":
        if str(pledge_policy_stats).upper() != str(pledge_policy_renderer).upper():
            pledge_mismatch = True

    tranche_rows, tranche_source_note = build_unconditional_tranche_rows(
        price=price, fwd20=fwd20, fwd10=fwd10, pledge_stats=pledge_stats
    )

    lines.append(md_table_kv([
        ["last_date", str(last_date)],
        ["price_used", fmt_price2(price)],
        ["bb_state", state],
        ["bb_z", fmt4(bb_z)],
        ["trend_state", trend_state],
        ["regime_tag", f"**{tag}**"],
        ["regime_allowed", str(regime_allowed).lower()],
        ["rv20_percentile", fmt2(rv_pctl)],
        ["rv_pctl_max", fmt2(rv_pctl_max)],
        ["dq_core", dq_core_str],
        ["margin_note", margin_note],
        ["pledge_block_in_stats", str(bool(safe_get(pledge_stats,'present',False))).lower()],
        ["pledge_version", str(pledge_version)],
        ["pledge_scope", str(pledge_scope)],
        ["pledge_source", str(pledge_source)],
        ["pledge_overlay_applied", str(bool(overlay_applied)).lower()],
    ]))
    lines.append("")

    lines.append(md_table_kv([
        ["action_bucket_renderer", f"**{action_bucket_renderer}**"],
        ["pledge_policy_renderer", f"**{pledge_policy_renderer}**"],
        ["pledge_veto_reasons_renderer", _join_semicolon(pledge_veto_renderer)],
        ["action_bucket_stats", str(pledge_action_bucket_stats)],
        ["pledge_policy_stats", str(pledge_policy_stats)],
        ["pledge_veto_reasons_stats", _join_semicolon(pledge_veto_stats)],
        ["pledge_policy(final)", f"**{final_policy}**"],
        ["pledge_veto_reasons(final)", _join_semicolon(final_reasons)],
        ["accumulate_z_threshold", fmt4(acc_thr)],
        ["no_chase_z_threshold", fmt4(nc_thr)],
        ["pledge_mismatch(stats_vs_renderer)", str(bool(pledge_mismatch)).lower()],
    ]))
    lines.append("")

    lines.append("### decision_path (renderer)")
    for p in decision_path:
        lines.append(f"- {p}")
    lines.append("")

    if tranche_rows:
        lines.append("### tranche_levels (reference; unconditional)")
        lines.append("")
        lines.append("| level | drawdown | price_level |")
        lines.append("|---|---:|---:|")
        for a, b, c in tranche_rows:
            lines.append(f"| {a} | {b} | {c} |")
        lines.append("")
        lines.append(f"- {tranche_source_note}")
        lines.append("")

    lines.append("### Pledge Guidance v2 (report-only; sizing proposal)")
    lines.append("")
    lines.append("- Purpose: convert binary gate into deterministic size_factor (0..1) using rv20_percentile bands.")
    lines.append("- Note: v2 is NOT gated by regime.allowed; it uses rv20_percentile directly and remains conservative under DQ/margin stress.")
    lines.append("")

    zone_v2, zone_path = compute_pledge_v2_zone(
        latest_state=state, bb_z=bb_z, accumulate_z=acc_thr, no_chase_z=nc_thr
    )
    v2 = compute_pledge_v2_sizing(
        zone=zone_v2, rv20_pctl=rv_pctl, margin_info=margin_info, dq_flags=dq_flags
    )

    lines.append(md_table_kv([
        ["v2_zone", f"**{zone_v2}**"],
        ["rv20_percentile", fmt2(rv_pctl)],
        ["v2_policy", f"**{v2.get('policy','N/A')}**"],
        ["size_factor(0..1)", fmt4(v2.get("size_factor"))],
        ["cooldown_sessions_hint", str(int(v2.get("cooldown_sessions_hint", 0)))],
        ["v2_reasons", _join_semicolon(_string_list(v2.get("reasons", [])))],
    ]))
    lines.append("")

    lines.append("#### v2_zone_path (independent of regime.allowed)")
    for p in zone_path:
        lines.append(f"- {p}")
    lines.append("")

    try:
        sf = float(v2.get("size_factor", 0.0) or 0.0)
    except Exception:
        sf = 0.0

    plan_rows, plan_note = build_tranche_plan_from_levels(tranche_rows, sf)
    lines.append("#### v2_tranche_plan (reference-only; scaled by size_factor)")
    lines.append("")
    if plan_rows:
        lines.append("| tranche | level | target_frac_of_max | price_level |")
        lines.append("|---|---|---:|---:|")
        for t, lvl, frac, pl in plan_rows:
            lines.append(f"| {t} | {lvl} | {frac} | {pl} |")
        lines.append("")
        lines.append(f"- note: {plan_note}")
        lines.append("- note: tranche levels are unconditional references; do not treat them as guaranteed fills.")
    else:
        lines.append(f"- {plan_note}")
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

    ap.add_argument("--accumulate_z", type=float, default=None, help="bb_z <= accumulate_z => ACCUMULATE_TRANCHE (override)")
    ap.add_argument("--no_chase_z", type=float, default=None, help="bb_z >= no_chase_z => NO_CHASE (override)")

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

    pledge_stats = extract_pledge_from_stats(s)

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
    lines.append(f"- pledge_block_in_stats: `{str(bool(safe_get(pledge_stats,'present',False))).lower()}`")
    if bool(safe_get(pledge_stats, "present", False)):
        lines.append(f"- pledge_version: `{safe_get(pledge_stats,'version','N/A')}`")
        lines.append(f"- pledge_scope: `{safe_get(pledge_stats,'scope','N/A')}`")
    lines.append("")

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
            pledge_stats=pledge_stats,
            accumulate_z_cli=args.accumulate_z,
            no_chase_z_cli=args.no_chase_z,
        )
    )

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
                        ["rv_hist_q20(%)", fmt_pct1(None if safe_get(vol, "rv_hist_q20") is None else float(safe_get(vol, "rv_hist_q20")) * 100.0)],
                        ["rv_hist_q50(%)", fmt_pct1(None if safe_get(vol, "rv_hist_q50") is None else float(safe_get(vol, "rv_hist_q50")) * 100.0)],
                        ["rv_hist_q80(%)", fmt_pct1(None if safe_get(vol, "rv_hist_q80") is None else float(safe_get(vol, "rv_hist_q80")) * 100.0)],
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

    lines.append("## forward_mdd Distribution")
    lines.append("")

    def has_min_audit_block(fwd: Dict[str, Any]) -> bool:
        return isinstance(fwd, dict) and all(
            k in fwd for k in ["min_entry_date", "min_entry_price", "min_future_date", "min_future_price"]
        )

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

    if margin_json is not None:
        mb_lines, _ = margin_overlay_block(
            margin_json=margin_json,
            price_last_date=str(last_date),
            window_n=int(args.margin_window_n),
            threshold_yi=float(args.margin_threshold_yi),
        )
        lines.extend(mb_lines)

    lines.append(f"## Recent Raw Prices (tail {tail_n})")
    lines.append("")
    tail_df = load_prices_tail(args.cache_dir, n=tail_n)
    if tail_df is None:
        lines.append("_No data.csv / prices.csv tail available._")
    else:
        lines.append(md_table_prices(tail_df))
    lines.append("")

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

    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    lines.append("- Deterministic Action 是規則輸出（report-only），不代表可獲利保證。")
    lines.append("- tranche_levels 優先使用 stats 內 pledge.unconditional_tranche_levels.levels；若不存在才由 renderer 用分位數重算。")
    lines.append("- dist_to_upper/lower 可能為負值（代表超出通道）；報表額外提供 above_upper / below_lower 以避免符號誤讀。")
    lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，為未還原價格，forward_mdd 可能被企業行動污染，DQ 會標示。")
    lines.append("- 融資 overlay 屬於市場整體槓桿 proxy；日期不對齊時 overlay 會標示 MISALIGNED。")
    lines.append("- Pledge Guidance v2 為報告層 sizing 提案：不改 stats，不構成投資建議。")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())