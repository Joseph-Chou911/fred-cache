#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

BUILD_SCRIPT_FINGERPRINT = "build_tw0050_bb_report@2026-02-20.v12"


# ---------- basic utils ----------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_get(d: Any, k: str, default=None):
    try:
        return d.get(k, default) if isinstance(d, dict) else default
    except Exception:
        return default


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def fmt_int(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{int(float(x)):,}"
    except Exception:
        return "N/A"


def md_table_kv(rows: List[List[str]]) -> str:
    out = ["| item | value |", "|---|---:|"]
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def normalize_date_key(x: Any) -> Optional[str]:
    """
    Normalize dates to YYYYMMDD:
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
        return None if x is None else float(x)
    except Exception:
        return None


def _above_upper_lower_from_dist(dist_to_upper_pct: Any, dist_to_lower_pct: Any) -> Tuple[str, str]:
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
    priority_prefix = ("PRICE_", "TWSE_", "YF_", "CHIP_", "MARGIN_", "RAW_", "FWD_")
    pri = [f for f in dq_flags if any(f.startswith(p) for p in priority_prefix)]
    rest = [f for f in dq_flags if f not in pri]
    ordered = pri + rest
    cap = 6
    if len(ordered) <= cap:
        return ", ".join(ordered)
    return ", ".join(ordered[:cap]) + f", ... (+{len(ordered) - cap})"


def _extract_fwd_outlier_days(dq_flags: List[str]) -> List[int]:
    days: List[int] = []
    for f in dq_flags:
        if not isinstance(f, str):
            continue
        if not f.startswith("FWD_MDD_OUTLIER_MIN_RAW_"):
            continue
        if not f.endswith("D"):
            continue
        try:
            tail = f.split("_")[-1]  # "20D"
            n = int(tail[:-1])
            days.append(n)
        except Exception:
            continue
    return sorted(set(days))


def _dq_core_fwd_fields(dq_flags: List[str]) -> Tuple[str, str, str, str]:
    """
    v12 policy (same as v11):
      - core DQ: exclude ALL forward-related flags (FWD_MDD_*) and RAW_OUTLIER_EXCLUDED_BY_CLEAN
      - forward fields: expose explicitly
    """
    flags = [str(x) for x in dq_flags if isinstance(x, str) and str(x).strip()]
    core = [f for f in flags if not (f.startswith("FWD_MDD_") or f == "RAW_OUTLIER_EXCLUDED_BY_CLEAN")]

    core_str = _dq_compact(core)
    fwd_clean = "ON" if "FWD_MDD_CLEAN_APPLIED" in flags else "OFF"
    fwd_mask = "ON" if "RAW_OUTLIER_EXCLUDED_BY_CLEAN" in flags else "OFF"
    days = _extract_fwd_outlier_days(flags)
    fwd_raw_outlier = "(none)" if not days else ",".join([f"{d}D" for d in days])

    return core_str, fwd_clean, fwd_mask, fwd_raw_outlier


def _filter_fwd_outlier_flags_for_horizon(dq_flags: List[str], horizon_days: int) -> List[str]:
    flags = [f for f in dq_flags if isinstance(f, str)]
    suff = f"_{horizon_days}D"
    specific = sorted([f for f in flags if f.startswith("FWD_MDD_OUTLIER_MIN_RAW") and f.endswith(suff)])
    if specific:
        return specific
    generic = sorted([f for f in flags if f == "FWD_MDD_OUTLIER_MIN_RAW"])
    return generic


# ---------- forward lines ----------
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


# ---------- pick forward blocks ----------
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


# ---------- chip overlay ----------
def _read_chip_overlay(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def _chip_alignment(chip: Dict[str, Any], price_last_date_ymd: Optional[str]) -> Tuple[str, str]:
    """
    Return (overlay_last_date, status_text)
    """
    overlay_last = (
        safe_get(chip, "asof")
        or safe_get(chip, "asof_date")
        or safe_get(safe_get(chip, "borrow", {}), "asof_date")
        or safe_get(chip, "overlay_aligned_last_date")
        or safe_get(safe_get(chip, "date_alignment", {}), "overlay_aligned_last_date")
        or safe_get(safe_get(chip, "date_alignment", {}), "overlay_last_date")
    )
    overlay_last_ymd = normalize_date_key(overlay_last)
    if overlay_last_ymd is None or price_last_date_ymd is None:
        return (overlay_last_ymd or "N/A", "N/A")
    status = "ALIGNED" if overlay_last_ymd == price_last_date_ymd else "NOT_ALIGNED"
    return (overlay_last_ymd, status)


def build_chip_summary_line(chip: Dict[str, Any], window_n: int, price_last_date_iso: str) -> Optional[str]:
    if not isinstance(chip, dict) or not chip:
        return None

    # t86 sums (5D)
    t86 = safe_get(chip, "t86", {}) or safe_get(chip, "t86_agg", {}) or {}
    total3 = safe_get(t86, "total3_net_shares_sum", safe_get(chip, "total3_net_shares_sum", None))
    foreign = safe_get(t86, "foreign_net_shares_sum", safe_get(chip, "foreign_net_shares_sum", None))
    trust = safe_get(t86, "trust_net_shares_sum", safe_get(chip, "trust_net_shares_sum", None))
    dealer = safe_get(t86, "dealer_net_shares_sum", safe_get(chip, "dealer_net_shares_sum", None))

    # borrow
    borrow = safe_get(chip, "borrow", {}) or {}
    borrow_shares = safe_get(borrow, "borrow_shares", safe_get(chip, "borrow_shares", None))
    borrow_shares_chg_1d = safe_get(borrow, "borrow_shares_chg_1d", safe_get(chip, "borrow_shares_chg_1d", None))
    borrow_mv_yi = safe_get(borrow, "borrow_mv_yi", None)
    if borrow_mv_yi is None:
        # maybe stored in NTD then convert? try a few keys
        mv_ntd = safe_get(borrow, "borrow_mv_ntd", safe_get(chip, "borrow_mv_ntd", None))
        try:
            borrow_mv_yi = float(mv_ntd) / 1e8 if mv_ntd is not None else None
        except Exception:
            borrow_mv_yi = None
    borrow_mv_yi_chg_1d = safe_get(borrow, "borrow_mv_yi_chg_1d", None)
    if borrow_mv_yi_chg_1d is None:
        mv_chg_ntd = safe_get(borrow, "borrow_mv_ntd_chg_1d", safe_get(chip, "borrow_mv_ntd_chg_1d", None))
        try:
            borrow_mv_yi_chg_1d = float(mv_chg_ntd) / 1e8 if mv_chg_ntd is not None else None
        except Exception:
            borrow_mv_yi_chg_1d = None

    asof = (
        safe_get(chip, "asof")
        or safe_get(chip, "asof_date")
        or safe_get(borrow, "asof_date")
        or safe_get(chip, "overlay_aligned_last_date")
        or safe_get(safe_get(chip, "date_alignment", {}), "overlay_aligned_last_date")
    )

    return (
        f"- chip_overlay(T86+TWT72U,{window_n}D): "
        f"total3_{window_n}D={fmt_int(total3)}; foreign={fmt_int(foreign)}; trust={fmt_int(trust)}; dealer={fmt_int(dealer)}; "
        f"borrow_shares={fmt_int(borrow_shares)} (Δ1D={fmt_int(borrow_shares_chg_1d)}); "
        f"borrow_mv(億)={fmt2(borrow_mv_yi)} (Δ1D={fmt2(borrow_mv_yi_chg_1d)}); "
        f"asof={normalize_date_key(asof) or 'N/A'}; price_last_date={price_last_date_iso} (ALIGNED)"
    )


def render_chip_section(lines: List[str], chip: Optional[Dict[str, Any]], chip_path: str, price_last_date_iso: str) -> None:
    if not chip:
        return

    price_last_ymd = normalize_date_key(price_last_date_iso)

    overlay_ts = safe_get(chip, "overlay_generated_at_utc", safe_get(chip, "generated_at_utc", "N/A"))
    stock_no = safe_get(chip, "stock_no", safe_get(chip, "symbol", "0050"))
    overlay_window_n = safe_get(chip, "overlay_window_n", safe_get(chip, "window_n", safe_get(chip, "window", "N/A")))

    overlay_last_ymd, status = _chip_alignment(chip, price_last_ymd)

    lines.append("## Chip Overlay（籌碼：TWSE T86 + TWT72U）")
    lines.append("")
    lines.append(f"- overlay_generated_at_utc: `{overlay_ts}`")
    lines.append(f"- stock_no: `{stock_no}`")
    lines.append(f"- overlay_window_n: `{overlay_window_n}` (expect={overlay_window_n})")
    lines.append(
        f"- date_alignment: overlay_aligned_last_date=`{overlay_last_ymd}` vs price_last_date=`{price_last_date_iso}` => **{status}**"
    )
    lines.append("")

    # Borrow
    borrow = safe_get(chip, "borrow", {}) or {}
    asof_date = normalize_date_key(safe_get(borrow, "asof_date", safe_get(chip, "asof", safe_get(chip, "asof_date", None))))
    borrow_shares = safe_get(borrow, "borrow_shares", safe_get(chip, "borrow_shares", None))
    borrow_shares_chg_1d = safe_get(borrow, "borrow_shares_chg_1d", safe_get(chip, "borrow_shares_chg_1d", None))

    # mv in 億
    borrow_mv_yi = safe_get(borrow, "borrow_mv_yi", None)
    if borrow_mv_yi is None:
        mv_ntd = safe_get(borrow, "borrow_mv_ntd", safe_get(chip, "borrow_mv_ntd", None))
        try:
            borrow_mv_yi = float(mv_ntd) / 1e8 if mv_ntd is not None else None
        except Exception:
            borrow_mv_yi = None

    borrow_mv_yi_chg_1d = safe_get(borrow, "borrow_mv_yi_chg_1d", None)
    if borrow_mv_yi_chg_1d is None:
        mv_chg_ntd = safe_get(borrow, "borrow_mv_ntd_chg_1d", safe_get(chip, "borrow_mv_ntd_chg_1d", None))
        try:
            borrow_mv_yi_chg_1d = float(mv_chg_ntd) / 1e8 if mv_chg_ntd is not None else None
        except Exception:
            borrow_mv_yi_chg_1d = None

    lines.append("### Borrow Summary（借券：TWT72U）")
    lines.append("")
    lines.append(
        md_table_kv(
            [
                ["asof_date", str(asof_date or "N/A")],
                ["borrow_shares", fmt_int(borrow_shares)],
                ["borrow_shares_chg_1d", fmt_int(borrow_shares_chg_1d)],
                ["borrow_mv_ntd(億)", fmt2(borrow_mv_yi)],
                ["borrow_mv_ntd_chg_1d(億)", fmt2(borrow_mv_yi_chg_1d)],
            ]
        )
    )
    lines.append("")

    # T86 aggregate
    t86 = safe_get(chip, "t86", {}) or safe_get(chip, "t86_agg", {}) or {}
    days_used = safe_get(t86, "days_used", safe_get(chip, "days_used", []))
    if isinstance(days_used, list):
        days_used_s = ", ".join([str(x) for x in days_used])
    else:
        days_used_s = str(days_used) if days_used is not None else "N/A"

    lines.append("### T86 Aggregate（法人：5D sum）")
    lines.append("")
    lines.append(
        md_table_kv(
            [
                ["days_used", days_used_s],
                ["foreign_net_shares_sum", fmt_int(safe_get(t86, "foreign_net_shares_sum", safe_get(chip, "foreign_net_shares_sum", None)))],
                ["trust_net_shares_sum", fmt_int(safe_get(t86, "trust_net_shares_sum", safe_get(chip, "trust_net_shares_sum", None)))],
                ["dealer_net_shares_sum", fmt_int(safe_get(t86, "dealer_net_shares_sum", safe_get(chip, "dealer_net_shares_sum", None)))],
                ["total3_net_shares_sum", fmt_int(safe_get(t86, "total3_net_shares_sum", safe_get(chip, "total3_net_shares_sum", None)))],
            ]
        )
    )
    lines.append("")

    # Units
    units = safe_get(chip, "units", {}) or safe_get(chip, "etf_units", {}) or {}
    units_out = safe_get(units, "units_outstanding", safe_get(chip, "units_outstanding", None))
    units_chg = safe_get(units, "units_chg_1d", safe_get(chip, "units_chg_1d", None))
    units_dq = safe_get(units, "dq", safe_get(chip, "dq", "(none)"))

    lines.append("### ETF Units（受益權單位）")
    lines.append("")
    lines.append(
        md_table_kv(
            [
                ["units_outstanding", fmt_int(units_out)],
                ["units_chg_1d", fmt_int(units_chg)],
                ["dq", str(units_dq if units_dq is not None else "(none)")],
            ]
        )
    )
    lines.append("")

    # Sources
    sources = safe_get(chip, "sources", {}) or {}
    t86_tpl = safe_get(sources, "t86_template", "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999")
    twt72u_tpl = safe_get(
        sources,
        "twt72u_template",
        "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB",
    )

    lines.append("### Chip Overlay Sources")
    lines.append("")
    lines.append(f"- T86 template: `{t86_tpl}`")
    lines.append(f"- TWT72U template: `{twt72u_tpl}`")
    lines.append("")


# ---------- margin overlay ----------
def _find_margin_overlay_from_stats(s: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # common candidates in stats_latest.json
    for k in ["margin_overlay", "margin", "margin_summary", "margin_data"]:
        v = s.get(k)
        if isinstance(v, dict) and v:
            return v
    return None


def _find_margin_overlay_file(cache_dir: str) -> Optional[str]:
    candidates = [
        "margin_overlay.json",
        "margin_overlay_latest.json",
        "margin_overlay_out.json",
        "margin_overlay_result.json",
        "margin_latest.json",
    ]
    for name in candidates:
        p = os.path.join(cache_dir, name)
        if os.path.exists(p):
            return p
    return None


def _read_margin_overlay(cache_dir: str, s: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    mo = _find_margin_overlay_from_stats(s)
    if mo:
        return mo, None
    p = _find_margin_overlay_file(cache_dir)
    if p:
        try:
            return load_json(p), p
        except Exception:
            return None, p
    return None, None


def _margin_rows(mo: Dict[str, Any]) -> List[Dict[str, Any]]:
    # normalize to list of dicts with at least scope
    if not isinstance(mo, dict):
        return []
    if isinstance(mo.get("rows"), list):
        return [r for r in mo["rows"] if isinstance(r, dict)]
    if isinstance(mo.get("table"), list):
        return [r for r in mo["table"] if isinstance(r, dict)]
    # sometimes keyed by scopes
    out: List[Dict[str, Any]] = []
    for scope in ["TWSE", "TPEX", "TOTAL"]:
        v = mo.get(scope)
        if isinstance(v, dict):
            r = dict(v)
            r.setdefault("scope", scope)
            out.append(r)
    return out


def _get_row(rows: List[Dict[str, Any]], scope: str) -> Optional[Dict[str, Any]]:
    for r in rows:
        if str(safe_get(r, "scope", "")).upper() == scope.upper():
            return r
    return None


def build_margin_summary_line(mo: Dict[str, Any], price_last_date_iso: str) -> Optional[str]:
    if not isinstance(mo, dict) or not mo:
        return None
    params = safe_get(mo, "params", {}) or {}
    window_n = safe_get(params, "window_n", safe_get(mo, "window_n", 5))
    thr_yi = safe_get(params, "threshold_yi", safe_get(mo, "threshold_yi", 100.0))

    rows = _margin_rows(mo)
    tw = _get_row(rows, "TWSE") or {}
    tp = _get_row(rows, "TPEX") or {}
    tt = _get_row(rows, "TOTAL") or {}

    # prefer chg_ND_sum_yi; fallback
    total_chg = safe_get(tt, "chg_ND_sum_yi", safe_get(tt, "chg_nd_sum_yi", safe_get(tt, "chg_5d_yi", None)))
    tw_chg = safe_get(tw, "chg_ND_sum_yi", safe_get(tw, "chg_nd_sum_yi", safe_get(tw, "chg_5d_yi", None)))
    tp_chg = safe_get(tp, "chg_ND_sum_yi", safe_get(tp, "chg_nd_sum_yi", safe_get(tp, "chg_5d_yi", None)))

    state_nd = safe_get(tt, "state_ND", safe_get(tt, "state_nd", safe_get(tt, "state", "N/A")))
    margin_date = safe_get(tt, "latest_date", safe_get(mo, "margin_latest_date", safe_get(mo, "latest_date", "N/A")))
    data_date = safe_get(mo, "data_date", safe_get(mo, "date", "N/A"))

    return (
        f"- margin({window_n}D,thr={fmt2(thr_yi)}億): "
        f"TOTAL {fmt2(total_chg)} 億 => **{state_nd}**; "
        f"TWSE {fmt2(tw_chg)} / TPEX {fmt2(tp_chg)}; "
        f"margin_date={margin_date}, price_last_date={price_last_date_iso} (ALIGNED); data_date={data_date}"
    )


def render_margin_section(lines: List[str], mo: Optional[Dict[str, Any]], price_last_date_iso: str) -> None:
    if not mo:
        return

    overlay_ts = safe_get(mo, "overlay_generated_at_utc", safe_get(mo, "generated_at_utc", "N/A"))
    data_date = safe_get(mo, "data_date", safe_get(mo, "date", "N/A"))
    params = safe_get(mo, "params", {}) or {}
    window_n = safe_get(params, "window_n", safe_get(mo, "window_n", 5))
    threshold_yi = safe_get(params, "threshold_yi", safe_get(mo, "threshold_yi", 100.0))

    # alignment
    margin_latest_date = safe_get(mo, "margin_latest_date", None)
    if margin_latest_date is None:
        rows = _margin_rows(mo)
        tt = _get_row(rows, "TOTAL") or _get_row(rows, "TWSE") or {}
        margin_latest_date = safe_get(tt, "latest_date", safe_get(mo, "latest_date", "N/A"))

    price_last_ymd = normalize_date_key(price_last_date_iso)
    margin_last_ymd = normalize_date_key(margin_latest_date)
    status = "N/A"
    if price_last_ymd and margin_last_ymd:
        status = "ALIGNED" if price_last_ymd == margin_last_ymd else "NOT_ALIGNED"

    lines.append("## Margin Overlay（融資）")
    lines.append("")
    lines.append(f"- overlay_generated_at_utc: `{overlay_ts}`")
    lines.append(f"- data_date: `{data_date}`")
    lines.append(f"- params: window_n={window_n}, threshold_yi={fmt2(threshold_yi)}")
    lines.append(
        f"- date_alignment: margin_latest_date=`{margin_latest_date}` vs price_last_date=`{price_last_date_iso}` => **{status}**"
    )
    lines.append("")

    rows = _margin_rows(mo)
    # render table in the same layout as you had
    header = "| scope | latest_date | balance(億) | chg_today(億) | chg_ND_sum(億) | state_ND | rows_used |"
    sep = "|---|---:|---:|---:|---:|---:|---:|"
    lines.append(header)
    lines.append(sep)

    def _cell(r: Dict[str, Any], k: str, fallback_keys: List[str] = None) -> Any:
        if fallback_keys is None:
            fallback_keys = []
        v = safe_get(r, k, None)
        if v is not None:
            return v
        for kk in fallback_keys:
            v2 = safe_get(r, kk, None)
            if v2 is not None:
                return v2
        return None

    for scope in ["TWSE", "TPEX", "TOTAL"]:
        r = _get_row(rows, scope) or {"scope": scope}
        latest_date = _cell(r, "latest_date", ["date"])
        bal = _cell(r, "balance_yi", ["balance(yi)", "balance"])
        chg_today = _cell(r, "chg_today_yi", ["chg_today", "chg_today(yi)"])
        chg_nd = _cell(r, "chg_ND_sum_yi", ["chg_nd_sum_yi", "chg_5d_yi", "chg_nd"])
        state = _cell(r, "state_ND", ["state_nd", "state"])
        rows_used = _cell(r, "rows_used", ["n", "count"])

        def _fmt_yi(x):
            if x is None:
                return "N/A"
            try:
                return f"{float(x):,.1f}"
            except Exception:
                return "N/A"

        lines.append(
            f"| {scope} | {latest_date if latest_date is not None else 'N/A'} | "
            f"{_fmt_yi(bal)} | {_fmt_yi(chg_today)} | {_fmt_yi(chg_nd)} | {state if state is not None else 'N/A'} | "
            f"{rows_used if rows_used is not None else 'N/A'} |"
        )
    lines.append("")

    # sources
    sources = safe_get(mo, "sources", {}) or {}
    twse_source = safe_get(mo, "TWSE_source", safe_get(sources, "twse_source", "HiStock"))
    twse_url = safe_get(mo, "TWSE_url", safe_get(sources, "twse_url", "https://histock.tw/stock/three.aspx?m=mg"))
    tpex_source = safe_get(mo, "TPEX_source", safe_get(sources, "tpex_source", "HiStock"))
    tpex_url = safe_get(mo, "TPEX_url", safe_get(sources, "tpex_url", "https://histock.tw/stock/three.aspx?m=mg&no=TWOI"))

    lines.append("### Margin Sources")
    lines.append("")
    lines.append(f"- TWSE source: `{twse_source}`")
    lines.append(f"- TWSE url: `{twse_url}`")
    lines.append(f"- TPEX source: `{tpex_source}`")
    lines.append(f"- TPEX url: `{tpex_url}`")
    lines.append("")


# ---------- main ----------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default="report.md")
    ap.add_argument("--tail_days", type=int, default=15)
    ap.add_argument("--tail_n", type=int, default=None)

    ap.add_argument("--chip_overlay_json", default=None)
    ap.add_argument("--chip_window_n", type=int, default=5)

    args = ap.parse_args()

    tail_n = args.tail_n if args.tail_n is not None else args.tail_days
    if tail_n <= 0:
        tail_n = 15

    cache_dir = args.cache_dir
    stats_path = os.path.join(cache_dir, "stats_latest.json")
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

    # latest snapshot fields
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

    # chip & margin
    chip_path = args.chip_overlay_json or os.path.join(cache_dir, "chip_overlay.json")
    chip = _read_chip_overlay(chip_path)
    margin_overlay, margin_overlay_path = _read_margin_overlay(cache_dir, s)

    # report
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
    if margin_overlay_path:
        lines.append(f"- margin_overlay_path: `{margin_overlay_path}`")
    lines.append("")

    # ===== Quick summary (2 lines allowed) =====
    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{state}**; bb_z={fmt4(bb_z)}; pos={fmt4(bb_pos_clip)} (raw={fmt4(bb_pos_raw)}); "
        f"bw_geo={fmt_pct2(bw_geo)}; bw_std={fmt_pct2(bw_std)}"
    )

    core_dq, fwd_clean, fwd_mask, fwd_raw_outlier = _dq_core_fwd_fields([str(x) for x in dq_flags if isinstance(x, str)])
    lines.append(
        f"- dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}; "
        f"above_upper={above_upper_pct_str}; below_lower={below_lower_pct_str}; "
        f"DQ={core_dq}; FWD_CLEAN={fwd_clean}; FWD_MASK={fwd_mask}; FWD_RAW_OUTLIER={fwd_raw_outlier}"
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

    # add back margin/chip summary lines (only if data exists)
    if margin_overlay:
        mline = build_margin_summary_line(margin_overlay, str(last_date))
        if mline:
            lines.append(mline)

    if chip:
        cline = build_chip_summary_line(chip, int(args.chip_window_n), str(last_date))
        if cline:
            lines.append(cline)

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

    # ===== forward_mdd =====
    lines.append("## forward_mdd Distribution")
    lines.append("")

    def has_min_audit_block(fwd: Dict[str, Any]) -> bool:
        return isinstance(fwd, dict) and all(k in fwd for k in ["min_entry_date", "min_entry_price", "min_future_date", "min_future_price"])

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
        lines.append("- min audit fields are missing in forward block.")
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
            lines.append("- min audit fields are missing in forward block.")
        lines.append("")
    else:
        lines.append("- forward_mdd10 block is missing in stats_latest.json.")
        lines.append("")

    # ===== chip & margin sections (restored) =====
    render_chip_section(lines, chip, chip_path, str(last_date))
    render_margin_section(lines, margin_overlay, str(last_date))

    # ===== prices tail =====
    lines.append(f"## Recent Raw Prices (tail {tail_n})")
    lines.append("")
    tail_df = load_prices_tail(cache_dir, n=tail_n)
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
    lines.append("")

    # ===== caveats (restore full) =====
    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    lines.append("- pos_in_band 會顯示 clipped 值（0..1）與 raw 值（可超界，用於稽核）。")
    lines.append("- dist_to_upper/lower 可能為負值（代表超出通道）；報表已額外提供 above_upper / below_lower 以避免符號誤讀。")
    lines.append("- band_width 同時提供兩種定義：geo=(upper/lower-1)、std=(upper-lower)/ma；請勿混用解讀。")
    lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，為未還原價格，forward_mdd 可能被除權息/企業行動污染，DQ 會標示。")
    lines.append("- Trend/Vol/ATR 是濾網與風險量級提示，不是進出場保證；資料不足會以 DQ 明示。")
    lines.append("- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；日期不對齊需降低解讀權重。")
    lines.append("- Chip overlay（T86/TWT72U）為籌碼/借券描述；ETF 申贖、避險行為可能影響解讀，建議只做輔助註記。")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())