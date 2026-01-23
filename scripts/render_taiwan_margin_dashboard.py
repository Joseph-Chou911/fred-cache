#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Taiwan margin financing dashboard from latest.json + history.json

Principles:
- Use balance series from history for Δ and Δ% (not site-provided chg_yi).
- 合計 only if TWSE/TPEX latest date matches AND baseline dates for horizon match.
- Output audit-friendly markdown with NA handling.

Hardening (audit / anti-misparse):
- Quality downgrade rule (medium): any check fails => PARTIAL
  Check-1: latest.meta.data_date == history_series[0].date (TWSE/TPEX individually)
  Check-2: last 5 dates strictly descending and unique (TWSE/TPEX individually)
  Check-3: TWSE/TPEX head-5 dates AND head-5 balances are exactly identical => suspicious -> fail
- Label gating: only when quality == OK, output {擴張/收縮/中性}; else NA(品質不足)
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
    Dedup by date (keep last).
    """
    out: List[Tuple[str, float]] = []
    for it in history_items:
        if it.get("market") != market:
            continue
        d = it.get("data_date")
        b = it.get("balance_yi")
        if d and isinstance(b, (int, float)):
            out.append((str(d), float(b)))

    tmp: Dict[str, float] = {}
    for d, b in out:
        tmp[d] = b

    out2 = sorted(tmp.items(), key=lambda x: x[0], reverse=True)
    return out2


def latest_balance(series: List[Tuple[str, float]]) -> Optional[float]:
    return series[0][1] if series else None


def calc_horizon(series: List[Tuple[str, float]], n: int) -> Dict[str, Any]:
    """
    n=1 -> 1D (need 2 points)
    n=5 -> 5D (need 6 points)
    n=20 -> 20D (need 21 points)
    """
    need = n + 1
    if len(series) < need:
        return {"delta": None, "pct": None, "base_date": None, "base_val": None, "latest_val": None}

    latest_d, latest_v = series[0]
    base_d, base_v = series[n]
    delta = latest_v - base_v
    pct = (delta / base_v * 100.0) if base_v != 0 else None
    return {
        "delta": delta,
        "pct": pct,
        "base_date": base_d,
        "base_val": base_v,
        "latest_val": latest_v,
    }


def check_meta_date_matches_series(meta_date: Optional[str], series: List[Tuple[str, float]]) -> Tuple[bool, str]:
    if not meta_date:
        return False, "meta.data_date=NA"
    if not series:
        return False, "history_series=empty"
    s0 = series[0][0]
    if str(meta_date) != str(s0):
        return False, f"meta.data_date({meta_date}) != series[0].date({s0})"
    return True, "OK"


def check_head_dates_desc_unique(series: List[Tuple[str, float]], k: int = 5) -> Tuple[bool, str, List[str]]:
    if len(series) < k:
        return False, f"rows<{k}", [d for d, _ in series]
    head = [d for d, _ in series[:k]]

    # unique
    if len(set(head)) != len(head):
        return False, "head_dates has duplicates", head

    # strictly descending for YYYY-MM-DD strings
    # (string compare works for ISO date)
    for i in range(len(head) - 1):
        if not (head[i] > head[i + 1]):
            return False, f"not strictly descending at {head[i]} -> {head[i+1]}", head

    return True, "OK", head


def check_twse_tpex_identical_head5(tw: List[Tuple[str, float]], tp: List[Tuple[str, float]], k: int = 5) -> Tuple[bool, str]:
    if len(tw) < k or len(tp) < k:
        return True, "SKIP(rows<5)"
    tw_head_d = [d for d, _ in tw[:k]]
    tp_head_d = [d for d, _ in tp[:k]]
    if tw_head_d != tp_head_d:
        return True, "OK"
    tw_head_b = [b for _, b in tw[:k]]
    tp_head_b = [b for _, b in tp[:k]]
    if tw_head_b == tp_head_b:
        return False, "TWSE/TPEX head5 dates & balances identical (suspicious, likely mis-parse)"
    return True, "OK"


def total_calc(twse_s: List[Tuple[str, float]], tpex_s: List[Tuple[str, float]], n: int,
               twse_date: Optional[str], tpex_date: Optional[str]) -> Dict[str, Any]:
    """
    合計 only if:
    - latest dates match (non-NA and equal)
    - base dates match for horizon n
    - both series have enough length
    """
    if not twse_date or not tpex_date or twse_date != tpex_date:
        return {"delta": None, "pct": None, "base_date": None, "base_val": None, "latest_val": None, "ok": False,
                "reason": "latest date mismatch/NA"}

    tw = calc_horizon(twse_s, n)
    tp = calc_horizon(tpex_s, n)

    if tw["base_date"] is None or tp["base_date"] is None:
        return {"delta": None, "pct": None, "base_date": None, "base_val": None, "latest_val": None, "ok": False,
                "reason": "insufficient history"}

    if tw["base_date"] != tp["base_date"]:
        return {"delta": None, "pct": None, "base_date": None, "base_val": None, "latest_val": None, "ok": False,
                "reason": "base_date mismatch"}

    if len(twse_s) < n + 1 or len(tpex_s) < n + 1:
        return {"delta": None, "pct": None, "base_date": None, "base_val": None, "latest_val": None, "ok": False,
                "reason": "insufficient history"}

    latest_tot = twse_s[0][1] + tpex_s[0][1]
    base_tot = twse_s[n][1] + tpex_s[n][1]
    delta = latest_tot - base_tot
    pct = (delta / base_tot * 100.0) if base_tot != 0 else None
    return {
        "delta": delta,
        "pct": pct,
        "base_date": tw["base_date"],
        "base_val": base_tot,
        "latest_val": latest_tot,
        "ok": True,
        "reason": "",
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

    L = latest.get("series") or {}
    twse_meta = L.get("TWSE") or {}
    tpex_meta = L.get("TPEX") or {}
    twse_date = twse_meta.get("data_date")
    tpex_date = tpex_meta.get("data_date")

    # horizon calcs
    tw1 = calc_horizon(twse_s, 1)
    tw5 = calc_horizon(twse_s, 5)
    tw20 = calc_horizon(twse_s, 20)

    tp1 = calc_horizon(tpex_s, 1)
    tp5 = calc_horizon(tpex_s, 5)
    tp20 = calc_horizon(tpex_s, 20)

    tot1 = total_calc(twse_s, tpex_s, 1, twse_date, tpex_date)
    tot5 = total_calc(twse_s, tpex_s, 5, twse_date, tpex_date)
    tot20 = total_calc(twse_s, tpex_s, 20, twse_date, tpex_date)

    # --- Audit checks (any fail => PARTIAL) ---
    c1_tw_ok, c1_tw_msg = check_meta_date_matches_series(twse_date, twse_s)
    c1_tp_ok, c1_tp_msg = check_meta_date_matches_series(tpex_date, tpex_s)

    c2_tw_ok, c2_tw_msg, tw_head = check_head_dates_desc_unique(twse_s, 5)
    c2_tp_ok, c2_tp_msg, tp_head = check_head_dates_desc_unique(tpex_s, 5)

    c3_ok, c3_msg = check_twse_tpex_identical_head5(twse_s, tpex_s, 5)

    any_check_fail = (not c1_tw_ok) or (not c1_tp_ok) or (not c2_tw_ok) or (not c2_tp_ok) or (not c3_ok)

    # Base quality (must have both markets latest date + value)
    base_quality_ok = (twse_date is not None) and (tpex_date is not None) and (latest_balance(twse_s) is not None) and (latest_balance(tpex_s) is not None)
    quality = "OK" if base_quality_ok and (not any_check_fail) else ("PARTIAL" if base_quality_ok else "LOW")

    # label gating: only when quality == OK
    label = "NA（品質不足）"
    if quality == "OK" and tot20.get("pct") is not None:
        p = float(tot20["pct"])
        if p >= 8.0:
            label = "擴張"
        elif p <= -8.0:
            label = "收縮"
        else:
            label = "中性"

    # meta sources for display
    def src_text(meta: Dict[str, Any]) -> str:
        s = meta.get("source") or "NA"
        u = meta.get("source_url") or "NA"
        return f"{s}（{u}）"

    twse_src = src_text(twse_meta)
    tpex_src = src_text(tpex_meta)

    # quick debug lines (rows/head/tail)
    def series_debug(series: List[Tuple[str, float]]) -> Tuple[int, List[str], List[str]]:
        n = len(series)
        head_dates = [d for d, _ in series[:3]]
        tail_dates = [d for d, _ in series[-3:]] if n >= 3 else [d for d, _ in series]
        return n, head_dates, tail_dates

    tw_rows, tw_head3, tw_tail3 = series_debug(twse_s)
    tp_rows, tp_head3, tp_tail3 = series_debug(tpex_s)

    md: List[str] = []
    md.append("# Taiwan Margin Financing Dashboard\n")

    md.append("## 1) 結論")
    md.append(f"- {label} + 資料品質 {quality}\n")

    md.append("## 2) 資料")
    md.append(f"- 上市(TWSE)：融資餘額 {fmt_num(latest_balance(twse_s),2)} 億元｜資料日期 {twse_date or 'NA'}｜來源：{twse_src}")
    md.append(f"  - rows={tw_rows}｜head_dates={tw_head3}｜tail_dates={tw_tail3}")
    md.append(f"- 上櫃(TPEX)：融資餘額 {fmt_num(latest_balance(tpex_s),2)} 億元｜資料日期 {tpex_date or 'NA'}｜來源：{tpex_src}")
    md.append(f"  - rows={tp_rows}｜head_dates={tp_head3}｜tail_dates={tp_tail3}")

    if twse_date and tpex_date and (twse_date == tpex_date) and (latest_balance(twse_s) is not None) and (latest_balance(tpex_s) is not None):
        md.append(f"- 合計：融資餘額 {fmt_num(latest_balance(twse_s)+latest_balance(tpex_s),2)} 億元｜資料日期 {twse_date}｜來源：TWSE=HiStock / TPEX=HiStock")
    else:
        md.append("- 合計：NA（上市與上櫃最新資料日期不一致或缺值，依規則不得合計）")
    md.append("")

    md.append("## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）")

    md.append("### 上市(TWSE)")
    md.append(f"- 1D：Δ={fmt_num(tw1['delta'],2)} 億元；Δ%={fmt_pct(tw1['pct'],4)} %｜latest={fmt_num(tw1['latest_val'],2)}｜base={fmt_num(tw1['base_val'],2)}（基期日={tw1['base_date'] or 'NA'}）")
    md.append(f"- 5D：Δ={fmt_num(tw5['delta'],2)} 億元；Δ%={fmt_pct(tw5['pct'],4)} %｜latest={fmt_num(tw5['latest_val'],2)}｜base={fmt_num(tw5['base_val'],2)}（基期日={tw5['base_date'] or 'NA'}）")
    md.append(f"- 20D：Δ={fmt_num(tw20['delta'],2)} 億元；Δ%={fmt_pct(tw20['pct'],4)} %｜latest={fmt_num(tw20['latest_val'],2)}｜base={fmt_num(tw20['base_val'],2)}（基期日={tw20['base_date'] or 'NA'}）\n")

    md.append("### 上櫃(TPEX)")
    md.append(f"- 1D：Δ={fmt_num(tp1['delta'],2)} 億元；Δ%={fmt_pct(tp1['pct'],4)} %｜latest={fmt_num(tp1['latest_val'],2)}｜base={fmt_num(tp1['base_val'],2)}（基期日={tp1['base_date'] or 'NA'}）")
    md.append(f"- 5D：Δ={fmt_num(tp5['delta'],2)} 億元；Δ%={fmt_pct(tp5['pct'],4)} %｜latest={fmt_num(tp5['latest_val'],2)}｜base={fmt_num(tp5['base_val'],2)}（基期日={tp5['base_date'] or 'NA'}）")
    md.append(f"- 20D：Δ={fmt_num(tp20['delta'],2)} 億元；Δ%={fmt_pct(tp20['pct'],4)} %｜latest={fmt_num(tp20['latest_val'],2)}｜base={fmt_num(tp20['base_val'],2)}（基期日={tp20['base_date'] or 'NA'}）\n")

    md.append("### 合計(上市+上櫃)")
    md.append(f"- 1D：Δ={fmt_num(tot1['delta'],2)} 億元；Δ%={fmt_pct(tot1['pct'],4)} %｜latest={fmt_num(tot1['latest_val'],2)}｜base={fmt_num(tot1['base_val'],2)}（基期日={tot1['base_date'] or 'NA'}）")
    md.append(f"- 5D：Δ={fmt_num(tot5['delta'],2)} 億元；Δ%={fmt_pct(tot5['pct'],4)} %｜latest={fmt_num(tot5['latest_val'],2)}｜base={fmt_num(tot5['base_val'],2)}（基期日={tot5['base_date'] or 'NA'}）")
    md.append(f"- 20D：Δ={fmt_num(tot20['delta'],2)} 億元；Δ%={fmt_pct(tot20['pct'],4)} %｜latest={fmt_num(tot20['latest_val'],2)}｜base={fmt_num(tot20['base_val'],2)}（基期日={tot20['base_date'] or 'NA'}）\n")

    md.append("## 4) 稽核備註")
    md.append("- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。")
    md.append("- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。")
    md.append("- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。")
    md.append("")

    md.append("## 5) 反方審核檢查（任一失敗 → PARTIAL）")
    md.append(f"- Check-1 TWSE meta_date==series[0].date：{'✅' if c1_tw_ok else '❌'}（{c1_tw_msg}）")
    md.append(f"- Check-1 TPEX meta_date==series[0].date：{'✅' if c1_tp_ok else '❌'}（{c1_tp_msg}）")
    md.append(f"- Check-2 TWSE head5 dates 嚴格遞減且無重複：{'✅' if c2_tw_ok else '❌'}（{c2_tw_msg}）")
    md.append(f"- Check-2 TPEX head5 dates 嚴格遞減且無重複：{'✅' if c2_tp_ok else '❌'}（{c2_tp_msg}）")
    md.append(f"- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：{'✅' if c3_ok else '❌'}（{c3_msg}）")
    md.append(f"\n_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_\n")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()