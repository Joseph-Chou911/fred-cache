#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

# ===== Audit stamp (use this to prove which script generated the report) =====
BUILD_SCRIPT_FINGERPRINT = "build_tw0050_bb_report@2026-02-19.v3"


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


def safe_get(d: Dict[str, Any], k: str, default=None):
    try:
        return d.get(k, default)
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

    # FIX: accept both old/new flag names
    flags = set(dq_flags or [])
    if ("FWD_MDD_OUTLIER_MIN_RAW" in flags) or ("FWD_MDD_OUTLIER_MIN" in flags):
        line += " [DQ:FWD_MDD_OUTLIER_MIN_RAW]"

    return line


def _fmt_yi(x: Any) -> str:
    # 融資單位：億
    try:
        if x is None:
            return "N/A"
        return f"{float(x):,.1f}"
    except Exception:
        return "N/A"


def _margin_quick_line(mo: Optional[Dict[str, Any]], last_date: str) -> str:
    """
    Build one-line summary for quick section.
    """
    if not isinstance(mo, dict):
        return "- margin (N/A): overlay missing"

    params = mo.get("params", {}) or {}
    n = params.get("window_n", "N/A")
    thr = params.get("threshold_yi", "N/A")

    total = mo.get("total", {}) or {}
    twse = mo.get("twse", {}) or {}
    tpex = mo.get("tpex", {}) or {}

    data_date = mo.get("data_date") or mo.get("generated_at_utc") or "N/A"
    # Alignment: compare margin latest_date vs price last_date
    margin_latest_date = twse.get("latest_date") or tpex.get("latest_date") or "N/A"
    align = "ALIGNED" if (margin_latest_date == last_date and margin_latest_date != "N/A") else "MISMATCH"

    total_chg = total.get("chg_nd_yi")
    total_state = total.get("state_nd") or mo.get("states", {}).get("total_state_nd") or "N/A"
    twse_chg = twse.get("chg_nd_yi")
    tpex_chg = tpex.get("chg_nd_yi")

    return (
        f"- margin({n}D,thr={thr}億): TOTAL { _fmt_yi(total_chg) } 億 => **{total_state}**; "
        f"TWSE { _fmt_yi(twse_chg) } / TPEX { _fmt_yi(tpex_chg) }; "
        f"margin_date={margin_latest_date}, price_last_date={last_date} ({align}); data_date={data_date}"
    )


def _margin_section(mo: Optional[Dict[str, Any]], last_date: str) -> List[str]:
    """
    Render a detailed section (markdown).
    """
    lines: List[str] = []
    lines.append("## Margin Overlay（融資）")
    lines.append("")
    if not isinstance(mo, dict):
        lines.append("- margin_overlay is missing in stats_latest.json.")
        lines.append("")
        return lines

    params = mo.get("params", {}) or {}
    n = params.get("window_n", "N/A")
    thr = params.get("threshold_yi", "N/A")

    source = mo.get("source", {}) or {}
    gen = mo.get("generated_at_utc", "N/A")
    data_date = mo.get("data_date", "N/A")

    twse = mo.get("twse", {}) or {}
    tpex = mo.get("tpex", {}) or {}
    total = mo.get("total", {}) or {}
    states = mo.get("states", {}) or {}

    margin_latest_date = twse.get("latest_date") or tpex.get("latest_date") or "N/A"
    align = "ALIGNED" if (margin_latest_date == last_date and margin_latest_date != "N/A") else "MISMATCH"

    lines.append(f"- overlay_generated_at_utc: `{gen}`")
    lines.append(f"- data_date: `{data_date}`")
    lines.append(f"- params: window_n={n}, threshold_yi={thr}")
    lines.append(f"- date_alignment: margin_latest_date=`{margin_latest_date}` vs price_last_date=`{last_date}` => **{align}**")
    lines.append("")
    lines.append("| scope | latest_date | balance(億) | chg_today(億) | chg_ND_sum(億) | state_ND | rows_used |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    def row(scope: str, obj: Dict[str, Any], state: Any) -> str:
        return (
            f"| {scope} | {obj.get('latest_date','N/A')} | {_fmt_yi(obj.get('latest_balance_yi'))} | "
            f"{_fmt_yi(obj.get('latest_chg_yi'))} | {_fmt_yi(obj.get('chg_nd_yi'))} | "
            f"{state or 'N/A'} | {obj.get('rows_used', 'N/A')} |"
        )

    lines.append(row("TWSE", twse, states.get("twse_state_nd")))
    lines.append(row("TPEX", tpex, states.get("tpex_state_nd")))
    lines.append(
        f"| TOTAL | {margin_latest_date} | {_fmt_yi(total.get('latest_balance_yi'))} | N/A | "
        f"{_fmt_yi(total.get('chg_nd_yi'))} | {states.get('total_state_nd') or total.get('state_nd') or 'N/A'} | N/A |"
    )
    lines.append("")

    # Sources (as plain text; do not embed raw URLs if you prefer)
    lines.append("### Margin Sources")
    lines.append("")
    lines.append(f"- TWSE source: `{source.get('twse')}`")
    lines.append(f"- TWSE url: `{source.get('twse_url')}`")
    lines.append(f"- TPEX source: `{source.get('tpex')}`")
    lines.append(f"- TPEX url: `{source.get('tpex_url')}`")
    lines.append("")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", default="tw0050_bb_cache")
    ap.add_argument("--out", default="report.md")
    ap.add_argument("--tail_days", type=int, default=15)  # workflow compatibility
    ap.add_argument("--tail_n", type=int, default=None)   # alias; overrides tail_days
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

    # NEW: margin overlay (from stats_latest.json)
    margin_overlay = s.get("margin_overlay", None)

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

    lines.append("## 快速摘要（非預測，僅狀態）")
    lines.append(
        f"- state: **{state}**; bb_z={fmt4(bb_z)}; pos_in_band={fmt4(bb_pos)}; "
        f"dist_to_lower={fmt_pct2(dist_to_lower)}; dist_to_upper={fmt_pct2(dist_to_upper)}"
    )
    lines.append(build_forward_line(fwd, dq_flags, fwd_days))
    # NEW: margin one-liner
    lines.append(_margin_quick_line(margin_overlay, last_date))
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

    # Min audit trail (or explicit missing-field message)
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

    # NEW: Margin section (detailed)
    lines.extend(_margin_section(margin_overlay, last_date))

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
        # Keep your current one-line style "- FLAG: note"
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
    lines.append("- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；若日期不對齊應降低解讀權重。")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())