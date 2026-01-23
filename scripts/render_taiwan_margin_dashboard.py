#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Taiwan margin financing dashboard.

Rules (per your spec):
- Report TWSE/TPEX balances + chg (and chg% = chg/baseline_balance*100 if baseline exists)
- 1D/5D/20D baselines use "back N trading days" by row index (not calendar days)
- Total (TWSE+TPEX) only computed if TWSE and TPEX latest dates are identical;
  and for each horizon, baseline dates must also match, else NA for total horizon.
- Missing values => NA (no guessing)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_num(x: Any, nd: int = 2) -> str:
    if x is None:
        return "NA"
    if not isinstance(x, (int, float)):
        return "NA"
    return f"{x:.{nd}f}"


def pct(change: Optional[float], base: Optional[float]) -> Optional[float]:
    if change is None or base is None:
        return None
    if base == 0:
        return None
    return change / base * 100.0


def pick_baseline(rows_desc: List[Dict[str, Any]], n: int) -> Tuple[Optional[str], Optional[float]]:
    """
    rows_desc[0] = latest
    baseline for nD = rows_desc[n] (e.g. 1D baseline is index 1)
    """
    if len(rows_desc) <= n:
        return None, None
    r = rows_desc[n]
    d = r.get("date")
    b = r.get("balance_yi")
    if not isinstance(d, str) or not isinstance(b, (int, float)):
        return None, None
    return d, float(b)


def get_latest(rows_desc: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    if not rows_desc:
        return None, None, None
    r0 = rows_desc[0]
    d0 = r0.get("date")
    b0 = r0.get("balance_yi")
    c0 = r0.get("chg_yi")
    return (d0 if isinstance(d0, str) else None,
            float(b0) if isinstance(b0, (int, float)) else None,
            float(c0) if isinstance(c0, (int, float)) else None)


def calc_horizon(rows_desc: List[Dict[str, Any]], n: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    returns: (abs_change, pct_change, baseline_date)
    abs_change = latest_balance - baseline_balance
    pct_change = abs_change / baseline_balance * 100
    """
    ld, lb, _ = get_latest(rows_desc)
    bd, bb = pick_baseline(rows_desc, n)
    if lb is None or bb is None or bd is None:
        return None, None, None
    ch = lb - bb
    return ch, pct(ch, bb), bd


def dq_label(twse_ok: bool, tpex_ok: bool, twse_hist_ok: bool, tpex_hist_ok: bool) -> str:
    if not twse_ok or not tpex_ok:
        return "LOW"
    if twse_hist_ok and tpex_hist_ok:
        return "OK"
    return "PARTIAL"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = load_json(args.latest)
    hist = load_json(args.history)

    series = latest.get("series", {})
    twse = series.get("TWSE", {})
    tpex = series.get("TPEX", {})

    twse_rows = twse.get("rows", []) or []
    tpex_rows = tpex.get("rows", []) or []

    twse_date, twse_bal, twse_chg = get_latest(twse_rows)
    tpex_date, tpex_bal, tpex_chg = get_latest(tpex_rows)

    # history 是否足夠計算 20D：需要 index 20 存在 => rows 至少 21
    twse_hist_ok = len(twse_rows) >= 21
    tpex_hist_ok = len(tpex_rows) >= 21

    twse_ok = twse_date is not None and twse_bal is not None
    tpex_ok = tpex_date is not None and tpex_bal is not None

    quality = dq_label(twse_ok, tpex_ok, twse_hist_ok, tpex_hist_ok)

    # 判斷擴張/收縮/持平：用「可得市場的 1D」；若兩市場都有且同日，用合計 1D
    # 但仍不做猜測：若 1D 缺就 NA
    twse_1d_abs, _, _ = calc_horizon(twse_rows, 1)
    tpex_1d_abs, _, _ = calc_horizon(tpex_rows, 1)

    trend = "NA"
    if twse_date and tpex_date and twse_date == tpex_date:
        # 合計 1D 需基期日也一致
        twse_bd, twse_bb = pick_baseline(twse_rows, 1)
        tpex_bd, tpex_bb = pick_baseline(tpex_rows, 1)
        if twse_bal is not None and tpex_bal is not None and twse_bb is not None and tpex_bb is not None and twse_bd == tpex_bd:
            total_1d = (twse_bal + tpex_bal) - (twse_bb + tpex_bb)
            if total_1d > 0:
                trend = "擴張"
            elif total_1d < 0:
                trend = "收縮"
            else:
                trend = "持平"
        else:
            trend = "NA"
    else:
        # 退而求其次：看可得者
        if twse_1d_abs is not None and tpex_1d_abs is not None:
            s = twse_1d_abs + tpex_1d_abs
            trend = "擴張" if s > 0 else ("收縮" if s < 0 else "持平")
        elif twse_1d_abs is not None:
            trend = "擴張" if twse_1d_abs > 0 else ("收縮" if twse_1d_abs < 0 else "持平")
        elif tpex_1d_abs is not None:
            trend = "擴張" if tpex_1d_abs > 0 else ("收縮" if tpex_1d_abs < 0 else "持平")

    # 當日增減%（用「上一交易日餘額」當基期）
    twse_prev_date, twse_prev_bal = pick_baseline(twse_rows, 1)
    tpex_prev_date, tpex_prev_bal = pick_baseline(tpex_rows, 1)
    twse_chg_pct = pct(twse_chg, twse_prev_bal) if twse_chg is not None else None
    tpex_chg_pct = pct(tpex_chg, tpex_prev_bal) if tpex_chg is not None else None

    # Horizon calcs
    twse_5d_abs, twse_5d_pct, twse_5d_base_d = calc_horizon(twse_rows, 5)
    twse_20d_abs, twse_20d_pct, twse_20d_base_d = calc_horizon(twse_rows, 20)

    tpex_5d_abs, tpex_5d_pct, tpex_5d_base_d = calc_horizon(tpex_rows, 5)
    tpex_20d_abs, tpex_20d_pct, tpex_20d_base_d = calc_horizon(tpex_rows, 20)

    # Total rules
    total_latest_date = None
    total_bal = None
    total_chg = None
    total_chg_pct = None

    if twse_date and tpex_date and twse_date == tpex_date and twse_bal is not None and tpex_bal is not None:
        total_latest_date = twse_date
        total_bal = twse_bal + tpex_bal
        if twse_chg is not None and tpex_chg is not None:
            total_chg = twse_chg + tpex_chg
            # total chg% 也需基期同日（上一交易日）
            if twse_prev_date and tpex_prev_date and twse_prev_date == tpex_prev_date and twse_prev_bal is not None and tpex_prev_bal is not None:
                total_chg_pct = pct(total_chg, twse_prev_bal + tpex_prev_bal)

    def total_horizon(n: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        if not (twse_date and tpex_date and twse_date == tpex_date):
            return None, None, None
        ld1, lb1, _ = get_latest(twse_rows)
        ld2, lb2, _ = get_latest(tpex_rows)
        bd1, bb1 = pick_baseline(twse_rows, n)
        bd2, bb2 = pick_baseline(tpex_rows, n)
        if lb1 is None or lb2 is None or bb1 is None or bb2 is None or bd1 is None or bd2 is None:
            return None, None, None
        if bd1 != bd2:
            return None, None, None
        ch = (lb1 + lb2) - (bb1 + bb2)
        return ch, pct(ch, bb1 + bb2), bd1

    total_1d_abs2, total_1d_pct2, total_1d_base = total_horizon(1)
    total_5d_abs2, total_5d_pct2, total_5d_base = total_horizon(5)
    total_20d_abs2, total_20d_pct2, total_20d_base = total_horizon(20)

    # Markdown
    lines: List[str] = []
    lines.append("# Taiwan Margin Financing Dashboard")
    lines.append("")
    lines.append("## 1) 結論")
    lines.append(f"- {trend} + 資料品質 {quality}")
    lines.append("")
    lines.append("## 2) 資料")
    lines.append(
        f"- 上市(TWSE)：融資餘額 {fmt_num(twse_bal,2)} 億元；融資增減 {fmt_num(twse_chg,2)} 億元（%：{fmt_num(twse_chg_pct,4)}）｜資料日期 {twse_date or 'NA'}｜來源：{twse.get('source','NA')}（{twse.get('source_url','NA')}）"
    )
    lines.append(
        f"- 上櫃(TPEX)：融資餘額 {fmt_num(tpex_bal,2)} 億元；融資增減 {fmt_num(tpex_chg,2)} 億元（%：{fmt_num(tpex_chg_pct,4)}）｜資料日期 {tpex_date or 'NA'}｜來源：{tpex.get('source','NA')}（{tpex.get('source_url','NA')}）"
    )

    if total_latest_date is None:
        lines.append(f"- 合計：NA（上市資料日期={twse_date or 'NA'}；上櫃資料日期={tpex_date or 'NA'}；日期不一致或缺值，依規則不得合計）")
    else:
        lines.append(
            f"- 合計：融資餘額 {fmt_num(total_bal,2)} 億元；融資增減 {fmt_num(total_chg,2)} 億元（%：{fmt_num(total_chg_pct,4)}）｜資料日期 {total_latest_date}｜來源：TWSE={twse.get('source','NA')} / TPEX={tpex.get('source','NA')}"
        )

    lines.append("")
    lines.append("## 3) 計算")

    lines.append("### 上市(TWSE)")
    lines.append(f"- 1D：{fmt_num(twse_1d_abs,2)} 億元；{fmt_num(pct(twse_1d_abs, twse_prev_bal),4)} %（基期日={twse_prev_date or 'NA'}）")
    lines.append(f"- 5D：{fmt_num(twse_5d_abs,2)} 億元；{fmt_num(twse_5d_pct,4)} %（基期日={twse_5d_base_d or 'NA'}）")
    lines.append(f"- 20D：{fmt_num(twse_20d_abs,2)} 億元；{fmt_num(twse_20d_pct,4)} %（基期日={twse_20d_base_d or 'NA'}）")

    lines.append("")
    lines.append("### 上櫃(TPEX)")
    lines.append(f"- 1D：{fmt_num(tpex_1d_abs,2)} 億元；{fmt_num(pct(tpex_1d_abs, tpex_prev_bal),4)} %（基期日={tpex_prev_date or 'NA'}）")
    lines.append(f"- 5D：{fmt_num(tpex_5d_abs,2)} 億元；{fmt_num(tpex_5d_pct,4)} %（基期日={tpex_5d_base_d or 'NA'}）")
    lines.append(f"- 20D：{fmt_num(tpex_20d_abs,2)} 億元；{fmt_num(tpex_20d_pct,4)} %（基期日={tpex_20d_base_d or 'NA'}）")

    lines.append("")
    lines.append("### 合計(上市+上櫃)")
    lines.append(f"- 1D：{fmt_num(total_1d_abs2,2)} 億元；{fmt_num(total_1d_pct2,4)} %（基期日={total_1d_base or 'NA'}）")
    lines.append(f"- 5D：{fmt_num(total_5d_abs2,2)} 億元；{fmt_num(total_5d_pct2,4)} %（基期日={total_5d_base or 'NA'}）")
    lines.append(f"- 20D：{fmt_num(total_20d_abs2,2)} 億元；{fmt_num(total_20d_pct2,4)} %（基期日={total_20d_base or 'NA'}）")

    lines.append("")
    lines.append("## 4) 主要觸發原因")
    lines.append("- Yahoo/WantGoo 常見 JS/403 或反爬，會導致抓取不穩；Scheme2 以 HiStock 優先降低失敗率。")
    lines.append("- 合計嚴格規則：只要上市/上櫃最新日或基期日不一致，就不計算合計（避免跨日錯配）。")
    lines.append("- 5D/20D 若為 NA：代表該市場 rows 不足（<6 / <21）或基期缺值，依規則不補猜。")

    lines.append("")
    lines.append("## 5) 下一步觀察重點")
    lines.append("- 先確保 TWSE/TPEX 都能穩定抓到 >=21 交易日，再往 z60/p60/zΔ60/pΔ60 擴充，避免斷資料假訊號。")
    lines.append("- 若未來要回到 Yahoo/WantGoo：必須保留『市場識別驗證』與『TPEX≠TWSE』防呆，否則很容易誤判。")
    lines.append("- 若 HiStock 偶發失敗，可再加一個“官方 OpenData”備援，但要把資料品質降級為 PARTIAL 並在資料段標示。")

    lines.append("")
    lines.append(f"_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()