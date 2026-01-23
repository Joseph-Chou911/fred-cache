#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Taiwan margin financing dashboard from latest.json + history.json

Principles:
- Use balance series from history for Δ and Δ% (not site-provided chg_yi).
- 合計 only if TWSE/TPEX latest date matches AND baseline dates for horizon match.
- Output audit-friendly markdown with strict NA handling.
- Data quality follows user rules:
  OK: TWSE+TPEX latest present AND enough history for 1D/5D/20D on both markets
  PARTIAL: TWSE+TPEX latest present but missing some 1D/5D/20D histories
  LOW: missing either TWSE or TPEX latest balance/date
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def fmt_pct(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def build_series_from_history(history_items: List[Dict[str, Any]], market: str) -> List[Tuple[str, float]]:
    """
    Return list of (date, balance) sorted desc by date.
    Dedup by date, keep last seen balance for that date.
    """
    tmp: Dict[str, float] = {}
    for it in history_items:
        if it.get("market") != market:
            continue
        d = it.get("data_date")
        b = it.get("balance_yi")
        if d and isinstance(b, (int, float)):
            tmp[str(d)] = float(b)
    return sorted(tmp.items(), key=lambda x: x[0], reverse=True)


def series_stats(series: List[Tuple[str, float]]) -> Dict[str, Any]:
    dates = [d for d, _ in series]
    return {
        "rows_count": len(series),
        "head_dates": dates[:3],
        "tail_dates": dates[-3:] if len(dates) >= 3 else dates,
    }


def latest_balance(series: List[Tuple[str, float]]) -> Optional[float]:
    return series[0][1] if series else None


def calc_horizon(series: List[Tuple[str, float]], n: int) -> Dict[str, Any]:
    """
    n=1 -> 1D (need 2 points)
    n=5 -> 5D (need 6 points)
    n=20 -> 20D (need 21 points)

    Returns:
      latest_date, latest_balance, base_date, base_balance, delta, pct
    """
    need = n + 1
    if len(series) < need:
        return {
            "latest_date": series[0][0] if series else None,
            "latest_balance": latest_balance(series),
            "base_date": None,
            "base_balance": None,
            "delta": None,
            "pct": None,
        }
    latest_d, latest_v = series[0]
    base_d, base_v = series[n]
    delta = latest_v - base_v
    pct = (delta / base_v * 100.0) if base_v != 0 else None
    return {
        "latest_date": latest_d,
        "latest_balance": latest_v,
        "base_date": base_d,
        "base_balance": base_v,
        "delta": delta,
        "pct": pct,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = read_json(args.latest)
    hist = read_json(args.history)
    items = hist.get("items", []) if isinstance(hist, dict) else []

    twse_s = build_series_from_history(items, "TWSE")
    tpex_s = build_series_from_history(items, "TPEX")

    twse_stat = series_stats(twse_s)
    tpex_stat = series_stats(tpex_s)

    # meta (for sources + data_date)
    L = latest.get("series") or {}
    twse_meta = L.get("TWSE") or {}
    tpex_meta = L.get("TPEX") or {}
    twse_date = twse_meta.get("data_date")
    tpex_date = tpex_meta.get("data_date")

    # horizons
    tw1 = calc_horizon(twse_s, 1)
    tw5 = calc_horizon(twse_s, 5)
    tw20 = calc_horizon(twse_s, 20)

    tp1 = calc_horizon(tpex_s, 1)
    tp5 = calc_horizon(tpex_s, 5)
    tp20 = calc_horizon(tpex_s, 20)

    # total rules: latest date must match; and base_date must match per horizon
    total_ok_latest = (twse_date is not None) and (twse_date == tpex_date)

    def total_calc(n: int) -> Dict[str, Any]:
        tw = calc_horizon(twse_s, n)
        tp = calc_horizon(tpex_s, n)

        if not total_ok_latest:
            return {
                "latest_date": None,
                "latest_balance": None,
                "base_date": None,
                "base_balance": None,
                "delta": None,
                "pct": None,
                "ok": False,
                "reason": "latest date mismatch/NA",
            }

        if tw["base_date"] is None or tp["base_date"] is None:
            return {
                "latest_date": twse_date,
                "latest_balance": None,
                "base_date": None,
                "base_balance": None,
                "delta": None,
                "pct": None,
                "ok": False,
                "reason": "insufficient history",
            }

        if tw["base_date"] != tp["base_date"]:
            return {
                "latest_date": twse_date,
                "latest_balance": None,
                "base_date": None,
                "base_balance": None,
                "delta": None,
                "pct": None,
                "ok": False,
                "reason": "base_date mismatch",
            }

        if len(twse_s) < n + 1 or len(tpex_s) < n + 1:
            return {
                "latest_date": twse_date,
                "latest_balance": None,
                "base_date": None,
                "base_balance": None,
                "delta": None,
                "pct": None,
                "ok": False,
                "reason": "insufficient history",
            }

        latest_tot = twse_s[0][1] + tpex_s[0][1]
        base_tot = twse_s[n][1] + tpex_s[n][1]
        delta = latest_tot - base_tot
        pct = (delta / base_tot * 100.0) if base_tot != 0 else None

        return {
            "latest_date": twse_date,
            "latest_balance": latest_tot,
            "base_date": tw["base_date"],
            "base_balance": base_tot,
            "delta": delta,
            "pct": pct,
            "ok": True,
            "reason": "",
        }

    tot1 = total_calc(1)
    tot5 = total_calc(5)
    tot20 = total_calc(20)

    # qualitative label (conservative): only when tot20 pct is calculable
    label = "NA"
    if tot20["pct"] is not None:
        label = "擴張" if tot20["pct"] >= 8.0 else ("收縮" if tot20["pct"] <= -8.0 else "中性")

    # Data quality per your rules
    tw_latest_ok = (twse_date is not None) and (latest_balance(twse_s) is not None)
    tp_latest_ok = (tpex_date is not None) and (latest_balance(tpex_s) is not None)

    if not (tw_latest_ok and tp_latest_ok):
        quality = "LOW"
    else:
        # Need enough history for 1D/5D/20D for BOTH markets => len >= 21
        tw_all = (tw1["delta"] is not None) and (tw5["delta"] is not None) and (tw20["delta"] is not None)
        tp_all = (tp1["delta"] is not None) and (tp5["delta"] is not None) and (tp20["delta"] is not None)
        quality = "OK" if (tw_all and tp_all) else "PARTIAL"

    # sources
    def mk_src(meta: Dict[str, Any]) -> str:
        s = meta.get("source") or "NA"
        u = meta.get("source_url") or "NA"
        return f"{s}（{u}）"

    twse_src = mk_src(twse_meta)
    tpex_src = mk_src(tpex_meta)

    md: List[str] = []
    md.append("# Taiwan Margin Financing Dashboard\n")
    md.append("## 1) 結論")
    md.append(f"- {label} + 資料品質 {quality}\n")

    md.append("## 2) 資料")
    md.append(
        f"- 上市(TWSE)：融資餘額 {fmt_num(latest_balance(twse_s),2)} 億元｜資料日期 {twse_date or 'NA'}｜來源：{twse_src}"
    )
    md.append(
        f"  - rows={twse_stat['rows_count']}｜head_dates={twse_stat['head_dates']}｜tail_dates={twse_stat['tail_dates']}"
    )
    md.append(
        f"- 上櫃(TPEX)：融資餘額 {fmt_num(latest_balance(tpex_s),2)} 億元｜資料日期 {tpex_date or 'NA'}｜來源：{tpex_src}"
    )
    md.append(
        f"  - rows={tpex_stat['rows_count']}｜head_dates={tpex_stat['head_dates']}｜tail_dates={tpex_stat['tail_dates']}"
    )

    if total_ok_latest and (latest_balance(twse_s) is not None) and (latest_balance(tpex_s) is not None):
        md.append(
            f"- 合計：融資餘額 {fmt_num(latest_balance(twse_s)+latest_balance(tpex_s),2)} 億元｜資料日期 {twse_date}｜來源：TWSE={twse_meta.get('source','NA')} / TPEX={tpex_meta.get('source','NA')}"
        )
    else:
        md.append(
            f"- 合計：NA（上市資料日期={twse_date or 'NA'}；上櫃資料日期={tpex_date or 'NA'}；日期不一致或缺值，依規則不得合計）"
        )
    md.append("")

    def line_h(name: str, h: Dict[str, Any]) -> str:
        # Show latest/base balances to make MD self-auditable
        return (
            f"- {name}：Δ={fmt_num(h['delta'],2)} 億元；Δ%={fmt_pct(h['pct'],4)} %"
            f"｜latest={fmt_num(h['latest_balance'],2)}｜base={fmt_num(h['base_balance'],2)}"
            f"（基期日={h['base_date'] or 'NA'}）"
        )

    md.append("## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）")

    md.append("### 上市(TWSE)")
    md.append(line_h("1D", tw1))
    md.append(line_h("5D", tw5))
    md.append(line_h("20D", tw20))
    md.append("")

    md.append("### 上櫃(TPEX)")
    md.append(line_h("1D", tp1))
    md.append(line_h("5D", tp5))
    md.append(line_h("20D", tp20))
    md.append("")

    md.append("### 合計(上市+上櫃)")
    md.append(line_h("1D", tot1))
    md.append(line_h("5D", tot5))
    md.append(line_h("20D", tot20))
    md.append("")

    md.append("## 4) 稽核備註")
    md.append("- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。")
    md.append("- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。")
    md.append("- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。")
    md.append(f"\n_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_\n")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()