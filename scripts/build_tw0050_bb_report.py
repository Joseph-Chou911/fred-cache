#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

BUILD_SCRIPT_FINGERPRINT = "build_tw0050_bb_report@2026-02-19.v4"


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


def safe_get(d: Dict[str, Any], k: str, default=None):
    try:
        return d.get(k, default)
    except Exception:
        return default


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    label = str(safe_get(fwd, "label", "") or "")
    n = safe_get(fwd, "n", 0)
    p50 = safe_get(fwd, "p50")
    p10 = safe_get(fwd, "p10")
    p05 = safe_get(fwd, "p05")
    mn = safe_get(fwd, "min")

    line = (
        f"- forward_mdd({fwd_days}D) distribution (n={n}): "
        f"p50={fmt4(p50)}; p10={fmt4(p10)}; p05={fmt4(p05)}; min={fmt4(mn)}"
    )

    med = safe_get(fwd, "min_entry_date")
    mfd = safe_get(fwd, "min_future_date")
    mep = safe_get(fwd, "min_entry_price")
    mfp = safe_get(fwd, "min_future_price")
    if med and mfd and mep is not None and mfp is not None:
        line += f" (min_window: {med}->{mfd}; {fmt4(mep)}->{fmt4(mfp)})"

    dq_set = set(dq_flags or [])
    # Avoid misleading tag: if primary is clean, but raw had outlier, state it clearly.
    if "FWD_MDD_OUTLIER_MIN_RAW" in dq_set:
        if "clean" in label:
            line += " [DQ:RAW_OUTLIER_EXCLUDED]"
        elif "raw" in label:
            line += " [DQ:FWD_MDD_OUTLIER_MIN_RAW]"
        else:
            line += " [DQ:FWD_MDD_OUTLIER_MIN_RAW]"

    # backward compatibility
    if "FWD_MDD_OUTLIER_MIN" in dq_set and "FWD_MDD_OUTLIER_MIN_RAW" not in dq_set:
        line += " [DQ:FWD_MDD_OUTLIER_MIN]"

    return line


def build_trend_line(trend: Dict[str, Any]) -> str:
    if not isinstance(trend, dict) or not trend:
        return "- trend_filter: N/A"
    ma_days = safe_get(trend, "ma_days", "N/A")
    slope_days = safe_get(trend, "slope_days", "N/A")
    thr = safe_get(trend, "slope_thr_pct", "N/A")
    pvs = safe_get(trend, "price_vs_ma_pct")
    slope = safe_get(trend, "slope_pct")
    st = safe_get(trend, "state", "NA")
    return (
        f"- trend_filter(MA{ma_days},slope{int(slope_days)}D,thr={fmt2(thr)}%): "
        f"price_vs_ma={fmt_pct2(pvs)}; slope={fmt_pct2(slope)} => **{st}**"
    )


def build_vol_line(vol: Dict[str, Any]) -> str:
    if not isinstance(vol, dict) or not vol:
        return "- vol_filter: N/A"
    rv_days = safe_get(vol, "rv_days", "N/A")
    rv_ann = safe_get(vol, "rv_ann")
    atr_days = safe_get(vol, "atr_days", "N/A")
    atr = safe_get(vol, "atr")
    atr_pct = safe_get(vol, "atr_pct")
    # rv_ann is fraction, convert to %
    rv_ann_pct = (float(rv_ann) * 100.0) if rv_ann is not None else None
    return (
        f"- vol_filter(RV{rv_days},ATR{atr_days}): "
        f"rv_ann={fmt_pct1(rv_ann_pct)}; atr={fmt4(atr)} ({fmt_pct2(atr_pct)})"
    )


def _fmt_yi1(x: Any) -> str:
    try:
        return f"{float(x):,.1f}"
    except Exception:
        return "N/A"


def _margin_state(sum_chg: float, thr: float) -> str:
    if sum_chg <= -thr:
        return "DELEVERAGING"
    if sum_chg >= thr:
        return "LEVERAGING"
    return "NEUTRAL"


def load_margin_overlay(margin_json_path: str) -> Optional[Dict[str, Any]]:
    if not margin_json_path or not os.path.exists(margin_json_path):
        return None
    try:
        return load_json(margin_json_path)
    except Exception:
        return None


def compute_margin_overlay(
    mj: Dict[str, Any],
    window_n: int,
    threshold_yi: float
) -> Optional[Dict[str, Any]]:
    """
    mj: taiwan_margin_cache/latest.json structure (TWSE & TPEX)
    Returns dict with computed sums and alignment-ready info.
    """
    if not mj or "series" not in mj:
        return None

    gen_utc = safe_get(mj, "generated_at_utc")
    series = mj.get("series", {}) or {}
    tw = series.get("TWSE", {}) or {}
    tp = series.get("TPEX", {}) or {}

    def _scope_pack(scope_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rows = scope_obj.get("rows") or []
        if not rows:
            return None
        # rows are typically latest-first; take first window_n
        use = rows[:window_n]
        chgs = []
        for r in use:
            v = r.get("chg_yi")
            try:
                chgs.append(float(v))
            except Exception:
                chgs.append(float("nan"))
        chgs = [x for x in chgs if pd.notna(x)]
        if not chgs:
            return None
        sum_chg = float(sum(chgs))
        latest = rows[0]
        return {
            "source": scope_obj.get("source"),
            "source_url": scope_obj.get("source_url"),
            "data_date": scope_obj.get("data_date"),
            "latest_date": latest.get("date"),
            "balance_yi": latest.get("balance_yi"),
            "chg_today_yi": latest.get("chg_yi"),
            "chg_nd_sum_yi": sum_chg,
            "rows_used": len(use),
            "state_nd": _margin_state(sum_chg, threshold_yi),
        }

    twp = _scope_pack(tw)
    tpp = _scope_pack(tp)
    if twp is None and tpp is None:
        return None

    total_sum = 0.0
    total_balance = 0.0
    if twp and isinstance(twp.get("chg_nd_sum_yi"), float):
        total_sum += float(twp["chg_nd_sum_yi"])
    if tpp and isinstance(tpp.get("chg_nd_sum_yi"), float):
        total_sum += float(tpp["chg_nd_sum_yi"])
    if twp and twp.get("balance_yi") is not None:
        total_balance += float(twp["balance_yi"])
    if tpp and tpp.get("balance_yi") is not None:
        total_balance += float(tpp["balance_yi"])

    # choose latest date for total (prefer TWSE if exists, else TPEX)
    latest_date = (twp.get("latest_date") if twp else None) or (tpp.get("latest_date") if tpp else None)
    data_date = (twp.get("data_date") if twp else None) or (tpp.get("data_date") if tpp else None)

    return {
        "overlay_generated_at_utc": gen_utc,
        "data_date": data_date,
        "params": {"window_n": window_n, "threshold_yi": threshold_yi},
        "TWSE": twp,
        "TPEX": tpp,
        "TOTAL": {
            "latest_date": latest_date,
            "balance_yi": total_balance if total_balance > 0 else None,
            "chg_nd_sum_yi": total_sum,
            "state_nd": _margin_state(total_sum, threshold_yi),
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default=None)
    ap.add_argument("--tail_days", type=int, default=15)  # workflow compatibility
    ap.add_argument("--tail_n", type=int, default=None)   # alias; overrides tail_days

    # Margin overlay
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
    trend = s.get("trend", {}) or {}
    vol = s.get("vol", {}) or {}

    dq = s.get("dq", {"flags": [], "notes": []}) or {}
    dq_flags = dq.get("flags") or []
    dq_notes = dq.get("notes") or []

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

    # Margin overlay
    margin_json_path = args.margin_json
    mj = load_margin_overlay(margin_json_path)
    margin = compute_margin_overlay(mj, window_n=int(args.margin_window_n), threshold_yi=float(args.margin_threshold_yi)) if mj else None

    price_last_date = last_date
    margin_alignment = None
    margin_summary_line = None
    if margin and margin.get("TOTAL"):
        m_latest = safe_get(margin["TOTAL"], "latest_date")
        m_data_date = safe_get(margin, "data_date")
        aligned = (m_latest == price_last_date)
        margin_alignment = "ALIGNED" if aligned else "NOT_ALIGNED"

        total_sum = safe_get(margin["TOTAL"], "chg_nd_sum_yi")
        total_state = safe_get(margin["TOTAL"], "state_nd", "N/A")

        tw_sum = safe_get((margin.get("TWSE") or {}), "chg_nd_sum_yi")
        tp_sum = safe_get((margin.get("TPEX") or {}), "chg_nd_sum_yi")

        margin_summary_line = (
            f"- margin({int(args.margin_window_n)}D,thr={fmt2(args.margin_threshold_yi)}億): "
            f"TOTAL {fmt2(total_sum)} 億 => **{total_state}**; "
            f"TWSE {fmt2(tw_sum)} / TPEX {fmt2(tp_sum)}; "
            f"margin_date={m_latest}, price_last_date={price_last_date} ({margin_alignment}); "
            f"data_date={m_data_date}"
        )

    out_path = args.out or os.path.join(args.cache_dir, "report.md")

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

    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{state}**; bb_z={fmt4(bb_z)}; pos_in_band={fmt4(bb_pos)}; "
        f"dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}"
    )
    lines.append(build_forward_line(fwd, dq_flags, fwd_days))
    lines.append(build_trend_line(trend))
    lines.append(build_vol_line(vol))
    if margin_summary_line:
        lines.append(margin_summary_line)
    lines.append("")

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

    lines.append("## Trend & Vol Filters")
    lines.append("")
    if isinstance(trend, dict) and trend:
        lines.append(md_table_kv([
            ["trend_ma_days", str(safe_get(trend, "ma_days", "N/A"))],
            ["trend_ma_last", fmt4(safe_get(trend, "ma_last"))],
            ["trend_slope_days", str(safe_get(trend, "slope_days", "N/A"))],
            ["trend_slope_pct", fmt_pct2(safe_get(trend, "slope_pct"))],
            ["price_vs_trend_ma_pct", fmt_pct2(safe_get(trend, "price_vs_ma_pct"))],
            ["trend_state", str(safe_get(trend, "state", "NA"))],
        ]))
    else:
        lines.append("_No trend data in stats_latest.json._")
    lines.append("")
    if isinstance(vol, dict) and vol:
        rv_ann = safe_get(vol, "rv_ann")
        rv_ann_pct = (float(rv_ann) * 100.0) if rv_ann is not None else None
        lines.append(md_table_kv([
            ["rv_days", str(safe_get(vol, "rv_days", "N/A"))],
            ["rv_ann(%)", fmt_pct1(rv_ann_pct)],
            ["atr_days", str(safe_get(vol, "atr_days", "N/A"))],
            ["atr", fmt4(safe_get(vol, "atr"))],
            ["atr_pct", fmt_pct2(safe_get(vol, "atr_pct"))],
        ]))
    else:
        lines.append("_No vol data in stats_latest.json._")
    lines.append("")

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

    # Margin section (detailed)
    if margin:
        lines.append("## Margin Overlay（融資）")
        lines.append("")
        lines.append(f"- overlay_generated_at_utc: `{safe_get(margin, 'overlay_generated_at_utc', 'N/A')}`")
        lines.append(f"- data_date: `{safe_get(margin, 'data_date', 'N/A')}`")
        lines.append(f"- params: window_n={int(args.margin_window_n)}, threshold_yi={fmt2(args.margin_threshold_yi)}")
        if margin_alignment:
            lines.append(
                f"- date_alignment: margin_latest_date=`{safe_get(margin.get('TOTAL', {}), 'latest_date', 'N/A')}` "
                f"vs price_last_date=`{price_last_date}` => **{margin_alignment}**"
            )
        lines.append("")
        lines.append("| scope | latest_date | balance(億) | chg_today(億) | chg_ND_sum(億) | state_ND | rows_used |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")

        def _row(scope: str, pack: Optional[Dict[str, Any]], rows_used: Any) -> List[str]:
            if not pack:
                return [scope, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]
            return [
                scope,
                str(safe_get(pack, "latest_date", "N/A")),
                _fmt_yi1(safe_get(pack, "balance_yi")),
                _fmt_yi1(safe_get(pack, "chg_today_yi")),
                _fmt_yi1(safe_get(pack, "chg_nd_sum_yi")),
                str(safe_get(pack, "state_nd", "N/A")),
                str(rows_used),
            ]

        twp = margin.get("TWSE")
        tpp = margin.get("TPEX")
        tot = margin.get("TOTAL")

        lines.append("| " + " | ".join(_row("TWSE", twp, safe_get(twp or {}, "rows_used", "N/A"))) + " |")
        lines.append("| " + " | ".join(_row("TPEX", tpp, safe_get(tpp or {}, "rows_used", "N/A"))) + " |")
        # TOTAL chg_today not meaningful -> N/A
        lines.append("| " + " | ".join([
            "TOTAL",
            str(safe_get(tot or {}, "latest_date", "N/A")),
            _fmt_yi1(safe_get(tot or {}, "balance_yi")),
            "N/A",
            _fmt_yi1(safe_get(tot or {}, "chg_nd_sum_yi")),
            str(safe_get(tot or {}, "state_nd", "N/A")),
            "N/A",
        ]) + " |")
        lines.append("")
        lines.append("### Margin Sources")
        lines.append("")
        if twp:
            lines.append(f"- TWSE source: `{safe_get(twp, 'source', 'N/A')}`")
            lines.append(f"- TWSE url: `{safe_get(twp, 'source_url', 'N/A')}`")
        if tpp:
            lines.append(f"- TPEX source: `{safe_get(tpp, 'source', 'N/A')}`")
            lines.append(f"- TPEX url: `{safe_get(tpp, 'source_url', 'N/A')}`")
        lines.append("")

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

    lines.append("## Caveats")
    lines.append("- BB 與 forward_mdd 是描述性統計，不是方向預測。")
    lines.append("- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。")
    lines.append("- Trend/Vol/ATR 是濾網與風險量級提示，不是進出場保證；若資料不足會以 DQ 明示。")
    lines.append("- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；若日期不對齊應降低解讀權重。")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())