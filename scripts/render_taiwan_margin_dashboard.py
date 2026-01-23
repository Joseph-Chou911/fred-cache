#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Taiwan margin financing dashboard from latest.json + history.json

Principles:
- Use balance series from history for Δ and Δ% (not site-provided chg_yi).
- 合計 only if TWSE/TPEX latest date matches AND baseline dates for horizon match.
- Output audit-friendly markdown with NA handling.
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
    """
    out: List[Tuple[str, float]] = []
    for it in history_items:
        if it.get("market") != market:
            continue
        d = it.get("data_date")
        b = it.get("balance_yi")
        if d and isinstance(b, (int, float)):
            out.append((str(d), float(b)))
    # dedup by date keep last
    tmp: Dict[str, float] = {}
    for d, b in out:
        tmp[d] = b
    out2 = sorted(tmp.items(), key=lambda x: x[0], reverse=True)
    return out2


def calc_horizon(series: List[Tuple[str, float]], n: int) -> Dict[str, Any]:
    """
    n=1 -> 1D (need 2 points)
    n=5 -> 5D (need 6 points)
    n=20 -> 20D (need 21 points)
    """
    need = n + 1
    if len(series) < need:
        return {"delta": None, "pct": None, "base_date": None}
    latest_d, latest_v = series[0]
    base_d, base_v = series[n]
    delta = latest_v - base_v
    pct = (delta / base_v * 100.0) if base_v != 0 else None
    return {"delta": delta, "pct": pct, "base_date": base_d}


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

    # latest snapshot info (for display)
    L = latest.get("series") or {}
    twse_meta = L.get("TWSE") or {}
    tpex_meta = L.get("TPEX") or {}
    twse_date = twse_meta.get("data_date")
    tpex_date = tpex_meta.get("data_date")

    def latest_balance(series: List[Tuple[str, float]]) -> Optional[float]:
        return series[0][1] if series else None

    # compute horizons
    tw1 = calc_horizon(twse_s, 1)
    tw5 = calc_horizon(twse_s, 5)
    tw20 = calc_horizon(twse_s, 20)

    tp1 = calc_horizon(tpex_s, 1)
    tp5 = calc_horizon(tpex_s, 5)
    tp20 = calc_horizon(tpex_s, 20)

    # total only if latest date matches and base dates match per horizon
    total_ok_latest = (twse_date is not None) and (twse_date == tpex_date)

    def total_h(tw: Dict[str, Any], tp: Dict[str, Any]) -> Dict[str, Any]:
        if not total_ok_latest:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "latest date mismatch/NA"}
        if tw.get("base_date") is None or tp.get("base_date") is None:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "insufficient history"}
        if tw["base_date"] != tp["base_date"]:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "base_date mismatch"}
        # build totals
        latest_tot = (latest_balance(twse_s) or 0.0) + (latest_balance(tpex_s) or 0.0)
        base_tot = (twse_s[{"1":1,"5":5,"20":20}.get(str(len([tw])),"1")][1] if False else None)  # dummy
        # compute directly from series indexes
        # infer n from base_date position in twse_s
        n = next((i for i, (d, _) in enumerate(twse_s) if d == tw["base_date"]), None)
        if n is None:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "index not found"}
        base_tot = twse_s[n][1] + tpex_s[n][1]
        delta = latest_tot - base_tot
        pct = (delta / base_tot * 100.0) if base_tot != 0 else None
        return {"delta": delta, "pct": pct, "base_date": tw["base_date"], "ok": True, "reason": ""}

    # safer total calc using n explicitly
    def total_calc(n: int) -> Dict[str, Any]:
        tw = calc_horizon(twse_s, n)
        tp = calc_horizon(tpex_s, n)
        if not total_ok_latest:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "latest date mismatch/NA"}
        if tw["base_date"] is None or tp["base_date"] is None:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "insufficient history"}
        if tw["base_date"] != tp["base_date"]:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "base_date mismatch"}
        if len(twse_s) < n + 1 or len(tpex_s) < n + 1:
            return {"delta": None, "pct": None, "base_date": None, "ok": False, "reason": "insufficient history"}
        latest_tot = twse_s[0][1] + tpex_s[0][1]
        base_tot = twse_s[n][1] + tpex_s[n][1]
        delta = latest_tot - base_tot
        pct = (delta / base_tot * 100.0) if base_tot != 0 else None
        return {"delta": delta, "pct": pct, "base_date": tw["base_date"], "ok": True, "reason": ""}

    tot1 = total_calc(1)
    tot5 = total_calc(5)
    tot20 = total_calc(20)

    # simple qualitative label (expansion if 20D pct >= 8%, else neutral)
    # keep conservative; only when calculable
    label = "NA"
    if tot20["pct"] is not None:
        label = "擴張" if tot20["pct"] >= 8.0 else ("收縮" if tot20["pct"] <= -8.0 else "中性")

    quality = "OK" if (twse_date and tpex_date and total_ok_latest) else "PARTIAL"

    twse_src = f'{twse_meta.get("source")}（{twse_meta.get("source_url")}）'
    tpex_src = f'{tpex_meta.get("source")}（{tpex_meta.get("source_url")}）'

    md = []
    md.append("# Taiwan Margin Financing Dashboard\n")
    md.append("## 1) 結論")
    md.append(f"- {label} + 資料品質 {quality}\n")

    md.append("## 2) 資料")
    md.append(f"- 上市(TWSE)：融資餘額 {fmt_num(latest_balance(twse_s),2)} 億元｜資料日期 {twse_date or 'NA'}｜來源：{twse_src}")
    md.append(f"- 上櫃(TPEX)：融資餘額 {fmt_num(latest_balance(tpex_s),2)} 億元｜資料日期 {tpex_date or 'NA'}｜來源：{tpex_src}")
    if total_ok_latest and latest_balance(twse_s) is not None and latest_balance(tpex_s) is not None:
        md.append(f"- 合計：融資餘額 {fmt_num(latest_balance(twse_s)+latest_balance(tpex_s),2)} 億元｜資料日期 {twse_date}｜來源：TWSE/TPEX=HiStock")
    else:
        md.append(f"- 合計：NA（日期不一致或缺值，依規則不得合計）")
    md.append("")

    md.append("## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）")
    md.append("### 上市(TWSE)")
    md.append(f"- 1D：{fmt_num(tw1['delta'],2)} 億元；{fmt_pct(tw1['pct'],4)} %（基期日={tw1['base_date'] or 'NA'}）")
    md.append(f"- 5D：{fmt_num(tw5['delta'],2)} 億元；{fmt_pct(tw5['pct'],4)} %（基期日={tw5['base_date'] or 'NA'}）")
    md.append(f"- 20D：{fmt_num(tw20['delta'],2)} 億元；{fmt_pct(tw20['pct'],4)} %（基期日={tw20['base_date'] or 'NA'}）\n")

    md.append("### 上櫃(TPEX)")
    md.append(f"- 1D：{fmt_num(tp1['delta'],2)} 億元；{fmt_pct(tp1['pct'],4)} %（基期日={tp1['base_date'] or 'NA'}）")
    md.append(f"- 5D：{fmt_num(tp5['delta'],2)} 億元；{fmt_pct(tp5['pct'],4)} %（基期日={tp5['base_date'] or 'NA'}）")
    md.append(f"- 20D：{fmt_num(tp20['delta'],2)} 億元；{fmt_pct(tp20['pct'],4)} %（基期日={tp20['base_date'] or 'NA'}）\n")

    md.append("### 合計(上市+上櫃)")
    md.append(f"- 1D：{fmt_num(tot1['delta'],2)} 億元；{fmt_pct(tot1['pct'],4)} %（基期日={tot1['base_date'] or 'NA'}）")
    md.append(f"- 5D：{fmt_num(tot5['delta'],2)} 億元；{fmt_pct(tot5['pct'],4)} %（基期日={tot5['base_date'] or 'NA'}）")
    md.append(f"- 20D：{fmt_num(tot20['delta'],2)} 億元；{fmt_pct(tot20['pct'],4)} %（基期日={tot20['base_date'] or 'NA'}）\n")

    md.append("## 4) 稽核備註")
    md.append("- 若 HiStock 改版導致欄名變動：fetch 會在 latest.json 的 notes 輸出欄名，方便定位。")
    md.append("- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算變化，避免依賴單一欄位。")
    md.append(f"\n_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_\n")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()