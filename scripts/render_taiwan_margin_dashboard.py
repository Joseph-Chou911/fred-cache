#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_taiwan_margin_dashboard.py

Render markdown dashboard with fixed structure (Traditional Chinese):
1) 結論
2) 資料
3) 計算
4) 主要觸發原因
5) 下一步觀察重點

Data quality:
- OK: TWSE+TPEX both have latest date and >=21 rows (to compute 1D/5D/20D).
- PARTIAL: TWSE+TPEX latest exist but missing some 5D/20D history.
- LOW: missing either TWSE or TPEX latest balance/date.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:,.{nd}f}"


def safe_get_balance(rows: List[Dict[str, Any]], idx: int) -> Optional[float]:
    if idx < 0 or idx >= len(rows):
        return None
    v = rows[idx].get("margin_balance_100m")
    return float(v) if isinstance(v, (int, float)) else None


def compute_change(rows: List[Dict[str, Any]], lag: int) -> Tuple[Optional[float], Optional[float]]:
    """
    rows are sorted desc by date: rows[0]=latest
    lag=1 -> 1D base is rows[1]
    lag=5 -> 5D base is rows[5]
    lag=20 -> 20D base is rows[20]
    returns (abs_change, pct_change)
    pct = abs_change / base * 100
    """
    latest = safe_get_balance(rows, 0)
    base = safe_get_balance(rows, lag)
    if latest is None or base is None:
        return None, None
    abs_chg = latest - base
    pct_chg = (abs_chg / base * 100.0) if base != 0 else None
    return abs_chg, pct_chg


def market_latest(rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[float]]:
    if not rows:
        return None, None
    d = rows[0].get("date")
    v = rows[0].get("margin_balance_100m")
    return (str(d) if d else None), (float(v) if isinstance(v, (int, float)) else None)


def classify_quality(twse_rows: List[Dict[str, Any]], tpex_rows: List[Dict[str, Any]]) -> str:
    twse_d, twse_v = market_latest(twse_rows)
    tpex_d, tpex_v = market_latest(tpex_rows)
    if not twse_d or twse_v is None or not tpex_d or tpex_v is None:
        return "LOW"
    # need >=21 for both
    if len(twse_rows) >= 21 and len(tpex_rows) >= 21:
        return "OK"
    return "PARTIAL"


def trend_word(abs_1d_twse: Optional[float], abs_1d_tpex: Optional[float]) -> str:
    # conservative: decide from available 1D changes only
    vals = [v for v in [abs_1d_twse, abs_1d_tpex] if v is not None]
    if not vals:
        return "NA"
    s = sum(vals)
    if s > 0:
        return "擴張"
    if s < 0:
        return "收縮"
    return "持平"


def md_link(text: str, url: str) -> str:
    return f"[{text}]({url})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)  # kept for future; not strictly required now
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = load_json(args.latest)
    series = latest.get("series", {})

    twse = series.get("TWSE", {})
    tpex = series.get("TPEX", {})

    twse_rows = twse.get("rows", []) or []
    tpex_rows = tpex.get("rows", []) or []

    # ensure desc by date already; assume fetcher did it.

    q = classify_quality(twse_rows, tpex_rows)

    # 1D for narrative
    twse_1d_abs, twse_1d_pct = compute_change(twse_rows, 1)
    tpex_1d_abs, tpex_1d_pct = compute_change(tpex_rows, 1)
    overall_trend = trend_word(twse_1d_abs, tpex_1d_abs)

    # latest
    twse_d, twse_v = market_latest(twse_rows)
    tpex_d, tpex_v = market_latest(tpex_rows)

    # total only if same data_date
    total_same_day = (twse_d is not None and tpex_d is not None and twse_d == tpex_d)
    total_v = (twse_v + tpex_v) if (total_same_day and twse_v is not None and tpex_v is not None) else None

    # For section 2: "融資增減" uses 1D vs previous trading day
    twse_chg_abs, twse_chg_pct = twse_1d_abs, twse_1d_pct
    tpex_chg_abs, tpex_chg_pct = tpex_1d_abs, tpex_1d_pct

    if total_same_day:
        # construct total synthetic rows by aligning index (strict: require both have enough rows)
        # For 1D/5D/20D we only compute if both have lag data.
        def total_change(lag: int) -> Tuple[Optional[float], Optional[float]]:
            lv0 = safe_get_balance(twse_rows, 0)
            rv0 = safe_get_balance(tpex_rows, 0)
            lvb = safe_get_balance(twse_rows, lag)
            rvb = safe_get_balance(tpex_rows, lag)
            if None in (lv0, rv0, lvb, rvb):
                return None, None
            latest_sum = lv0 + rv0
            base_sum = lvb + rvb
            abs_chg = latest_sum - base_sum
            pct_chg = (abs_chg / base_sum * 100.0) if base_sum != 0 else None
            return abs_chg, pct_chg

        total_1d_abs, total_1d_pct = total_change(1)
    else:
        total_1d_abs, total_1d_pct = None, None

    # compute 1D/5D/20D
    twse_5d_abs, twse_5d_pct = compute_change(twse_rows, 5)
    twse_20d_abs, twse_20d_pct = compute_change(twse_rows, 20)

    tpex_5d_abs, tpex_5d_pct = compute_change(tpex_rows, 5)
    tpex_20d_abs, tpex_20d_pct = compute_change(tpex_rows, 20)

    if total_same_day:
        def total_change(lag: int) -> Tuple[Optional[float], Optional[float]]:
            lv0 = safe_get_balance(twse_rows, 0)
            rv0 = safe_get_balance(tpex_rows, 0)
            lvb = safe_get_balance(twse_rows, lag)
            rvb = safe_get_balance(tpex_rows, lag)
            if None in (lv0, rv0, lvb, rvb):
                return None, None
            latest_sum = lv0 + rv0
            base_sum = lvb + rvb
            abs_chg = latest_sum - base_sum
            pct_chg = (abs_chg / base_sum * 100.0) if base_sum != 0 else None
            return abs_chg, pct_chg

        total_5d_abs, total_5d_pct = total_change(5)
        total_20d_abs, total_20d_pct = total_change(20)
    else:
        total_5d_abs = total_5d_pct = total_20d_abs = total_20d_pct = None

    # Prepare sources for section 2
    twse_src = twse.get("source", "NA")
    twse_url = twse.get("source_url", "")
    tpex_src = tpex.get("source", "NA")
    tpex_url = tpex.get("source_url", "")

    # Conclusion line
    conclusion = f"融資呈現{overall_trend}；資料品質 {q}"

    # Section 4 triggers (conservative, based only on computed values; no speculation)
    triggers: List[str] = []
    if twse_1d_abs is not None:
        triggers.append(f"上市（TWSE）1D 融資增減為 {fmt_num(twse_1d_abs)} 億元（{fmt_num(twse_1d_pct)}%）。")
    else:
        triggers.append("上市（TWSE）1D 融資增減無法計算（資料不足或缺值）。")

    if tpex_1d_abs is not None:
        triggers.append(f"上櫃（TPEX）1D 融資增減為 {fmt_num(tpex_1d_abs)} 億元（{fmt_num(tpex_1d_pct)}%）。")
    else:
        triggers.append("上櫃（TPEX）1D 融資增減無法計算（資料不足或缺值）。")

    if not total_same_day:
        triggers.append(f"上市資料日期={twse_d or 'NA'}、上櫃資料日期={tpex_d or 'NA'} 不一致 → 合計欄位依規則輸出 NA。")
    else:
        if total_1d_abs is not None:
            triggers.append(f"合計（同日）1D 融資增減為 {fmt_num(total_1d_abs)} 億元（{fmt_num(total_1d_pct)}%）。")
        else:
            triggers.append("合計（同日）1D 融資增減仍無法計算（兩市場基期資料不足）。")

    # Next watchpoints (process-focused)
    watchpoints = [
        "確認下一交易日兩市場資料日期是否同步（若不同步，合計仍需維持 NA，避免誤判）。",
        "觀察 5D/20D 是否由 NA 轉為可計算（代表歷史列數補齊到足夠交易日）。",
        "若 1D 與 5D 同向且幅度擴大，再把它當成「槓桿情緒變化」訊號進一步對照成交額/波動指標。",
    ]

    # Render markdown with fixed structure
    lines: List[str] = []
    lines.append("# Taiwan Margin-Financing Dashboard（方案B）\n")
    lines.append("## 1) 結論")
    lines.append(f"- {conclusion}\n")

    lines.append("## 2) 資料")
    lines.append(f"- 上市（TWSE）資料日期：**{twse_d or 'NA'}**；來源：{twse_src} {md_link('連結', twse_url) if twse_url else ''}")
    lines.append(f"  - 融資餘額（億元）：**{fmt_num(twse_v)}**")
    lines.append(f"  - 融資增減（億元、%）：**{fmt_num(twse_chg_abs)}** 億元，**{fmt_num(twse_chg_pct)}**%\n")

    lines.append(f"- 上櫃（TPEX）資料日期：**{tpex_d or 'NA'}**；來源：{tpex_src} {md_link('連結', tpex_url) if tpex_url else ''}")
    lines.append(f"  - 融資餘額（億元）：**{fmt_num(tpex_v)}**")
    lines.append(f"  - 融資增減（億元、%）：**{fmt_num(tpex_chg_abs)}** 億元，**{fmt_num(tpex_chg_pct)}**%\n")

    if total_same_day:
        lines.append(f"- 合計（上市+上櫃）資料日期：**{twse_d}**（兩市場同日）")
        lines.append(f"  - 融資餘額（億元）：**{fmt_num(total_v)}**")
        lines.append(f"  - 融資增減（億元、%）：**{fmt_num(total_1d_abs)}** 億元，**{fmt_num(total_1d_pct)}**%\n")
    else:
        lines.append("- 合計（上市+上櫃）：**NA**（上市與上櫃最新資料日期不同，依規則不計算合計）\n")

    lines.append("## 3) 計算")
    lines.append("- 百分比定義＝變化(億元)/基期餘額(億元)*100；5D/20D 基期＝往回第 5/第 20 個交易日（列序）。\n")

    lines.append("### 上市（TWSE）")
    lines.append(f"- 1D：{fmt_num(twse_1d_abs)} 億元，{fmt_num(twse_1d_pct)}%")
    lines.append(f"- 5D：{fmt_num(twse_5d_abs)} 億元，{fmt_num(twse_5d_pct)}%")
    lines.append(f"- 20D：{fmt_num(twse_20d_abs)} 億元，{fmt_num(twse_20d_pct)}%\n")

    lines.append("### 上櫃（TPEX）")
    lines.append(f"- 1D：{fmt_num(tpex_1d_abs)} 億元，{fmt_num(tpex_1d_pct)}%")
    lines.append(f"- 5D：{fmt_num(tpex_5d_abs)} 億元，{fmt_num(tpex_5d_pct)}%")
    lines.append(f"- 20D：{fmt_num(tpex_20d_abs)} 億元，{fmt_num(tpex_20d_pct)}%\n")

    lines.append("### 合計（上市+上櫃）")
    lines.append(f"- 1D：{fmt_num(total_1d_abs)} 億元，{fmt_num(total_1d_pct)}%")
    lines.append(f"- 5D：{fmt_num(total_5d_abs)} 億元，{fmt_num(total_5d_pct)}%")
    lines.append(f"- 20D：{fmt_num(total_20d_abs)} 億元，{fmt_num(total_20d_pct)}%\n")

    lines.append("## 4) 主要觸發原因")
    for t in triggers[:3]:
        lines.append(f"- {t}")
    lines.append("")

    lines.append("## 5) 下一步觀察重點")
    for w in watchpoints[:3]:
        lines.append(f"- {w}")
    lines.append("")

    # Add extraction notes (for audit)
    twse_notes = twse.get("notes", []) or []
    tpex_notes = tpex.get("notes", []) or []
    if twse_notes or tpex_notes:
        lines.append("## 附註（資料擷取/降級紀錄）")
        if twse_notes:
            lines.append("- 上市（TWSE）：")
            for n in twse_notes:
                lines.append(f"  - {n}")
        if tpex_notes:
            lines.append("- 上櫃（TPEX）：")
            for n in tpex_notes:
                lines.append(f"  - {n}")
        lines.append("")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()