#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def _chg_pct(chg: Optional[float], base: Optional[float]) -> Optional[float]:
    if chg is None or base is None or base == 0:
        return None
    return chg / base * 100.0


def _latest_and_base(rows: List[Dict[str, Any]], horizon: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    # rows: newest -> oldest
    if not rows:
        return None, None
    if len(rows) <= horizon:
        return rows[0], None
    return rows[0], rows[horizon]


def _horizon_change(rows: List[Dict[str, Any]], horizon: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    horizon 1/5/20 => base = rows[horizon]
    return (abs_chg, pct, base_date)
    """
    latest, base = _latest_and_base(rows, horizon)
    if latest is None or base is None:
        return None, None, None
    lb = latest.get("balance_yi")
    bb = base.get("balance_yi")
    if lb is None or bb is None:
        return None, None, base.get("date")
    abs_chg = float(lb) - float(bb)
    pct = _chg_pct(abs_chg, float(bb))
    return abs_chg, pct, base.get("date")


def _same_date(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a) and bool(b) and a == b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    series = latest.get("series", {})
    twse = series.get("TWSE", {})
    tpex = series.get("TPEX", {})

    twse_rows = twse.get("rows") or []
    tpex_rows = tpex.get("rows") or []

    twse_date = twse.get("data_date")
    tpex_date = tpex.get("data_date")

    # data-quality rules
    def has_latest(s: Dict[str, Any]) -> bool:
        return bool(s.get("data_date")) and bool(s.get("rows")) and (s.get("rows")[0].get("balance_yi") is not None)

    def enough_hist(s: Dict[str, Any], need: int) -> bool:
        return bool(s.get("rows")) and len(s.get("rows")) >= need

    if not has_latest(twse) or not has_latest(tpex):
        quality = "LOW"
    else:
        if enough_hist(twse, 21) and enough_hist(tpex, 21):
            quality = "OK"
        else:
            quality = "PARTIAL"

    # 結論（僅以 1D 的方向；若缺資料則 NA）
    twse_1d, twse_1d_pct, _ = _horizon_change(twse_rows, 1)
    tpex_1d, tpex_1d_pct, _ = _horizon_change(tpex_rows, 1)

    direction = "NA"
    if twse_1d is not None and tpex_1d is not None and _same_date(twse_date, tpex_date):
        total_1d = twse_1d + tpex_1d
        if total_1d > 0:
            direction = "擴張"
        elif total_1d < 0:
            direction = "收縮"
        else:
            direction = "持平"
    elif twse_1d is not None and tpex_1d is None:
        direction = "NA（上櫃缺值）"
    elif twse_1d is None and tpex_1d is not None:
        direction = "NA（上市缺值）"

    # 2) 資料：融資餘額與「當日融資增減」（用 rows[0].chg_yi / rows[1].balance 做百分比）
    def data_line(label: str, s: Dict[str, Any]) -> Tuple[str, Optional[float], Optional[float], Optional[float], Optional[str], str]:
        rows = s.get("rows") or []
        data_date = s.get("data_date")
        source = s.get("source")
        url = s.get("source_url")
        bal = rows[0].get("balance_yi") if rows else None
        chg = rows[0].get("chg_yi") if rows else None
        base_prev = rows[1].get("balance_yi") if len(rows) >= 2 else None
        pct = _chg_pct(float(chg), float(base_prev)) if (chg is not None and base_prev is not None) else None
        return label, bal, chg, pct, data_date, f"{source}（{url}）"

    twse_dl = data_line("上市(TWSE)", twse)
    tpex_dl = data_line("上櫃(TPEX)", tpex)

    # 合計：只有「最新資料日期相同」才合計；且 1D/5D/20D 也要兩邊基期日一致才計算
    total_allowed = _same_date(twse_date, tpex_date)

    total_bal = None
    total_chg = None
    total_pct = None
    total_date = None
    total_src = "NA"
    if total_allowed:
        total_date = twse_date
        if twse_dl[1] is not None and tpex_dl[1] is not None:
            total_bal = float(twse_dl[1]) + float(tpex_dl[1])
        if twse_dl[2] is not None and tpex_dl[2] is not None:
            total_chg = float(twse_dl[2]) + float(tpex_dl[2])
        # pct 用「前一日合計餘額」當 base（若任一缺就 NA）
        twse_prev = (twse.get("rows") or [None, None])[1].get("balance_yi") if len(twse_rows) >= 2 else None
        tpex_prev = (tpex.get("rows") or [None, None])[1].get("balance_yi") if len(tpex_rows) >= 2 else None
        if total_chg is not None and (twse_prev is not None) and (tpex_prev is not None):
            total_pct = _chg_pct(total_chg, float(twse_prev) + float(tpex_prev))
        total_src = f"TWSE={twse.get('source')} / TPEX={tpex.get('source')}"
    else:
        total_src = f"NA（上市資料日期={twse_date}；上櫃資料日期={tpex_date}；日期不一致或缺值，依規則不得合計）"

    # 3) 計算：1D/5D/20D（horizon=1/5/20）
    def calc_block(rows: List[Dict[str, Any]], name: str) -> str:
        out = [f"### {name}"]
        for h in (1, 5, 20):
            abs_chg, pct, base_date = _horizon_change(rows, h)
            out.append(f"- {h}D：{_fmt_num(abs_chg, 2)} 億元；{_fmt_num(pct, 4)} %（基期日={base_date or 'NA'}）")
        return "\n".join(out)

    # 合計計算（嚴格：最新日與基期日都要一致）
    def total_horizon(h: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        if not total_allowed:
            return None, None, None
        tw_abs, tw_pct, tw_base = _horizon_change(twse_rows, h)
        tp_abs, tp_pct, tp_base = _horizon_change(tpex_rows, h)
        # 兩邊都要有 base 且 base date 相同
        if tw_abs is None or tp_abs is None or tw_base is None or tp_base is None:
            return None, None, None
        if tw_base != tp_base:
            return None, None, None
        # base 合計餘額
        tw_base_bal = twse_rows[h].get("balance_yi") if len(twse_rows) > h else None
        tp_base_bal = tpex_rows[h].get("balance_yi") if len(tpex_rows) > h else None
        if tw_base_bal is None or tp_base_bal is None:
            return None, None, tw_base
        abs_chg = float(tw_abs) + float(tp_abs)
        pct = _chg_pct(abs_chg, float(tw_base_bal) + float(tp_base_bal))
        return abs_chg, pct, tw_base

    total_calc_lines = ["### 合計(上市+上櫃)"]
    for h in (1, 5, 20):
        abs_chg, pct, base_date = total_horizon(h)
        total_calc_lines.append(f"- {h}D：{_fmt_num(abs_chg, 2)} 億元；{_fmt_num(pct, 4)} %（基期日={base_date or 'NA'}）")

    md = []
    md.append("# Taiwan Margin Financing Dashboard\n")
    md.append("## 1) 結論")
    md.append(f"- {direction} + 資料品質 {quality}\n")

    md.append("## 2) 資料")
    md.append(f"- {twse_dl[0]}：融資餘額 {_fmt_num(twse_dl[1],2)} 億元；融資增減 {_fmt_num(twse_dl[2],2)} 億元（%：{_fmt_num(twse_dl[3],4)}）｜資料日期 {twse_dl[4] or 'NA'}｜來源：{twse_dl[5]}")
    md.append(f"- {tpex_dl[0]}：融資餘額 {_fmt_num(tpex_dl[1],2)} 億元；融資增減 {_fmt_num(tpex_dl[2],2)} 億元（%：{_fmt_num(tpex_dl[3],4)}）｜資料日期 {tpex_dl[4] or 'NA'}｜來源：{tpex_dl[5]}")
    md.append(f"- 合計：融資餘額 {_fmt_num(total_bal,2)} 億元；融資增減 {_fmt_num(total_chg,2)} 億元（%：{_fmt_num(total_pct,4)}）｜資料日期 {total_date or 'NA'}｜來源：{total_src}\n")

    md.append("## 3) 計算")
    md.append(calc_block(twse_rows, "上市(TWSE)"))
    md.append("")
    md.append(calc_block(tpex_rows, "上櫃(TPEX)"))
    md.append("")
    md.append("\n".join(total_calc_lines))
    md.append("\n## 4) 主要觸發原因")
    md.append("- 若出現「TPEX 與 TWSE 前 N 筆完全相同」：高機率抓錯頁面（本版已防呆直接把 TPEX 置 NA，避免假 OK）。")
    md.append("- 5D/20D 會是 NA：代表該市場 rows 不足（<6 / <21），或基期日兩市場不一致（合計依規則禁止）。")
    md.append("- 合計只在「上市與上櫃最新資料日期相同」且基期日也一致時才計算，避免跨日錯配。\n")

    md.append("## 5) 下一步觀察重點")
    md.append("- 先確認 TWSE/TPEX 兩個 URL 都能穩定抓到 >=21 交易日（才有資格進 OK）。")
    md.append("- 一旦資料穩定連續，再加上 z60/p60/zΔ60/pΔ60（rolling 視窗）做泡沫訊號，避免斷資料時產生假訊號。")
    md.append("- 若未來要重新挑戰 Yahoo/WantGoo：務必保留「市場識別驗證」與「TPEX≠TWSE」防呆，否則很容易再出現你這次的誤判。")

    _write_text(args.out, "\n".join(md))


if __name__ == "__main__":
    main()