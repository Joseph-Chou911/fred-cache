#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    try:
        return f"{x:,.{nd}f}"
    except Exception:
        return "NA"

def pct(change: Optional[float], base: Optional[float]) -> Optional[float]:
    if change is None or base is None:
        return None
    if base == 0:
        return None
    return change / base * 100.0

def calc_changes(rows: List[Dict[str, Any]]) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """
    rows are in descending date order (latest first).
    Return:
      "1D": (abs, pct)
      "5D": (abs, pct) where base is rows[5]
      "20D": (abs, pct) where base is rows[20]
    """
    out: Dict[str, Tuple[Optional[float], Optional[float]]] = {"1D": (None, None), "5D": (None, None), "20D": (None, None)}
    if not rows:
        return out

    latest = rows[0].get("balance_yi")
    # 1D: base rows[1]
    if len(rows) >= 2:
        base = rows[1].get("balance_yi")
        if latest is not None and base is not None:
            chg = latest - base
            out["1D"] = (chg, pct(chg, base))

    # 5D base rows[5]
    if len(rows) >= 6:
        base = rows[5].get("balance_yi")
        if latest is not None and base is not None:
            chg = latest - base
            out["5D"] = (chg, pct(chg, base))

    # 20D base rows[20]
    if len(rows) >= 21:
        base = rows[20].get("balance_yi")
        if latest is not None and base is not None:
            chg = latest - base
            out["20D"] = (chg, pct(chg, base))

    return out

def pick_series_latest(latest: Dict[str, Any], market: str) -> Tuple[Optional[str], Optional[float], Optional[float], str, str]:
    s = latest["series"].get(market, {})
    data_date = s.get("data_date")
    rows = s.get("rows", [])
    source = s.get("source", "NA")
    url = s.get("source_url", "NA")
    if not data_date or not rows:
        return (data_date, None, None, source, url)
    r0 = rows[0]
    return (data_date, r0.get("balance_yi"), r0.get("chg_yi"), source, url)

def build_market_rows_from_history(history: Dict[str, Any], market: str, want_n: int = 21) -> List[Dict[str, Any]]:
    items = history.get("items", [])
    # filter market, sort by data_date desc
    filt = [x for x in items if x.get("market") == market and x.get("data_date")]
    filt.sort(key=lambda x: x["data_date"], reverse=True)
    # dedup by data_date keeping first (latest run_ts)
    seen = set()
    out = []
    for x in filt:
        d = x["data_date"]
        if d in seen:
            continue
        seen.add(d)
        out.append({"date": d, "balance_yi": x.get("balance_yi")})
        if len(out) >= want_n:
            break
    return out

def data_quality(latest: Dict[str, Any], hist: Dict[str, Any]) -> str:
    twse_date = latest["series"].get("TWSE", {}).get("data_date")
    tpex_date = latest["series"].get("TPEX", {}).get("data_date")
    if not twse_date or not tpex_date:
        return "LOW"
    twse_rows = build_market_rows_from_history(hist, "TWSE", 21)
    tpex_rows = build_market_rows_from_history(hist, "TPEX", 21)
    if len(twse_rows) >= 21 and len(tpex_rows) >= 21:
        return "OK"
    return "PARTIAL"

def summary_word(change_1d_twse: Optional[float], change_1d_tpex: Optional[float]) -> str:
    # conservative: only decide if both available; else use available; else "NA"
    vals = [v for v in [change_1d_twse, change_1d_tpex] if v is not None]
    if not vals:
        return "NA"
    total = sum(vals)
    if abs(total) < 0.01:
        return "持平"
    return "擴張" if total > 0 else "收縮"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = read_json(args.latest)
    hist = read_json(args.history)

    # latest snapshot values
    twse_date, twse_bal, twse_chg, twse_src, twse_url = pick_series_latest(latest, "TWSE")
    tpex_date, tpex_bal, tpex_chg, tpex_src, tpex_url = pick_series_latest(latest, "TPEX")

    # history windows for calc (use trading-day index by row order)
    twse_hist21 = build_market_rows_from_history(hist, "TWSE", 21)
    tpex_hist21 = build_market_rows_from_history(hist, "TPEX", 21)

    twse_changes = calc_changes(twse_hist21)
    tpex_changes = calc_changes(tpex_hist21)

    # total (only if same date)
    can_total = (twse_date is not None and tpex_date is not None and twse_date == tpex_date
                 and twse_bal is not None and tpex_bal is not None)

    total_date = twse_date if can_total else None
    total_bal = (twse_bal + tpex_bal) if can_total else None

    # For total changes, we need aligned dates; otherwise NA by rule.
    total_changes = {"1D": (None, None), "5D": (None, None), "20D": (None, None)}
    total_chg_1d = None
    if can_total:
        # build total series by date intersection of both history lists, then take latest 21 trading days by shared dates
        tw_map = {r["date"]: r["balance_yi"] for r in twse_hist21}
        tp_map = {r["date"]: r["balance_yi"] for r in tpex_hist21}
        common_dates = [d for d in tw_map.keys() if d in tp_map]
        common_dates.sort(reverse=True)
        total_series = [{"date": d, "balance_yi": (tw_map[d] + tp_map[d])} for d in common_dates[:21]]
        total_changes = calc_changes(total_series)
        total_chg_1d = total_changes["1D"][0]

    q = data_quality(latest, hist)

    # 1) 結論
    s_word = summary_word(twse_changes["1D"][0], tpex_changes["1D"][0])
    conclusion = f"{s_word}（以 1D 合計方向判讀；若缺市場資料則以可得者近似） + 資料品質 {q}"

    # 2) 資料段（含日期一致性說明）
    lines: List[str] = []
    lines.append("# Taiwan Margin Financing Dashboard\n")
    lines.append("## 1) 結論\n")
    lines.append(f"- {conclusion}\n")

    lines.append("## 2) 資料\n")
    lines.append(f"- 上市(TWSE)：融資餘額 {fmt_num(twse_bal)} 億元；融資增減 {fmt_num(twse_chg)} 億元（%：NA；此欄需基期才可算）｜資料日期 {twse_date or 'NA'}｜來源：{twse_src}（{twse_url}）\n")
    lines.append(f"- 上櫃(TPEX)：融資餘額 {fmt_num(tpex_bal)} 億元；融資增減 {fmt_num(tpex_chg)} 億元（%：NA；此欄需基期才可算）｜資料日期 {tpex_date or 'NA'}｜來源：{tpex_src}（{tpex_url}）\n")
    if can_total:
        lines.append(f"- 合計：融資餘額 {fmt_num(total_bal)} 億元；融資增減（億元、%）將於 3) 計算段以 1D/5D/20D 定義計算｜資料日期 {total_date}\n")
    else:
        lines.append(f"- 合計：NA（上市資料日期={twse_date or 'NA'}；上櫃資料日期={tpex_date or 'NA'}；日期不一致或缺值，依規則不得合計）\n")

    # 3) 計算段
    def render_calc_block(name: str, changes: Dict[str, Tuple[Optional[float], Optional[float]]]) -> List[str]:
        out: List[str] = []
        out.append(f"### {name}\n")
        for k in ["1D", "5D", "20D"]:
            a, p = changes.get(k, (None, None))
            out.append(f"- {k}：{fmt_num(a)} 億元；{fmt_num(p)} %\n")
        return out

    lines.append("## 3) 計算\n")
    lines += render_calc_block("上市(TWSE)", twse_changes)
    lines += render_calc_block("上櫃(TPEX)", tpex_changes)
    if can_total:
        lines += render_calc_block("合計(上市+上櫃)", total_changes)
    else:
        lines.append("### 合計(上市+上櫃)\n- 1D：NA\n- 5D：NA\n- 20D：NA\n")

    # 4) 主要觸發原因（不猜；只給“資料面”原因）
    lines.append("## 4) 主要觸發原因\n")
    lines.append("- 若出現 403/解析失敗：多半為站點反爬/前端載入導致無法取得歷史表。\n")
    lines.append("- 若 5D/20D 為 NA：代表 history 交易日筆數不足（未滿 6/21 筆）。\n")
    lines.append("- 若合計為 NA：上市與上櫃資料日期不一致，依你的防誤判規則禁止合計。\n")

    # 5) 下一步觀察重點
    lines.append("## 5) 下一步觀察重點\n")
    lines.append("- 先把來源穩定下來：優先確保 TWSE/TPEX 都能穩定抓到 >=21 交易日，再談 z60/p60 等統計。\n")
    lines.append("- 若 WantGoo 長期 403：建議直接移除 WantGoo 或改成“只做人為備援”，避免每天浪費重試時間。\n")
    lines.append("- 一旦資料連續：再擴充 dashboard 加入 z60/p60/zΔ60/pΔ60（基於 history 交易日序列），並加上異常門檻通知。\n")

    write_text(args.out, "".join(lines))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())