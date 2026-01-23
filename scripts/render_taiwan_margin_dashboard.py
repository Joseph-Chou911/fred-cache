#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Render a markdown dashboard for Taiwan margin financing.

Key points:
- Uses latest.series.{TWSE,TPEX}.rows (newest->oldest) for horizon computations.
- 1D base = rows[1]
- 5D base = rows[5] (back 5 trading days, by row index)
- 20D base = rows[20]
- If insufficient rows => NA
- Total (TWSE+TPEX) only computed when:
  - latest dates match (rows[0].date)
  - and for each horizon, base dates also match
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _get_rows(latest: Dict[str, Any], market: str) -> List[Dict[str, Any]]:
    s = (latest.get("series") or {}).get(market) or {}
    rows = s.get("rows") or []
    return rows if isinstance(rows, list) else []


def _get_meta(latest: Dict[str, Any], market: str) -> Tuple[str, str, Optional[str]]:
    s = (latest.get("series") or {}).get(market) or {}
    return (
        str(s.get("source") or "NA"),
        str(s.get("source_url") or "NA"),
        s.get("data_date"),
    )


def _compute_horizon(rows: List[Dict[str, Any]], idx_base: int) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    Returns (abs_change, pct_change, cur_date, base_date)
    pct = abs/base*100
    """
    if not rows or len(rows) <= idx_base:
        return None, None, (rows[0].get("date") if rows else None), None
    cur = rows[0]
    base = rows[idx_base]
    cur_bal = _safe_float(cur.get("balance_yi"))
    base_bal = _safe_float(base.get("balance_yi"))
    if cur_bal is None or base_bal is None or base_bal == 0:
        return None, None, cur.get("date"), base.get("date")
    abs_chg = cur_bal - base_bal
    pct = (abs_chg / base_bal) * 100.0
    return round(abs_chg, 2), round(pct, 4), cur.get("date"), base.get("date")


def _compute_total(
    rows_a: List[Dict[str, Any]],
    rows_b: List[Dict[str, Any]],
    idx_base: int,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    Returns (total_cur_bal, total_abs_change, total_pct_change, cur_date, base_date)
    - total_abs = (a_cur - a_base) + (b_cur - b_base)
    - total_pct = total_abs / (a_base + b_base) * 100
    Strict date alignment:
    - cur dates must match
    - base dates must match
    """
    if not rows_a or not rows_b:
        return None, None, None, None, None
    cur_date_a = rows_a[0].get("date")
    cur_date_b = rows_b[0].get("date")
    if not cur_date_a or not cur_date_b or cur_date_a != cur_date_b:
        return None, None, None, cur_date_a, cur_date_b

    if len(rows_a) <= idx_base or len(rows_b) <= idx_base:
        return None, None, None, cur_date_a, None

    base_date_a = rows_a[idx_base].get("date")
    base_date_b = rows_b[idx_base].get("date")
    if not base_date_a or not base_date_b or base_date_a != base_date_b:
        return None, None, None, cur_date_a, base_date_a or base_date_b

    a_cur = _safe_float(rows_a[0].get("balance_yi"))
    b_cur = _safe_float(rows_b[0].get("balance_yi"))
    a_base = _safe_float(rows_a[idx_base].get("balance_yi"))
    b_base = _safe_float(rows_b[idx_base].get("balance_yi"))
    if None in (a_cur, b_cur, a_base, b_base):
        return None, None, None, cur_date_a, base_date_a

    total_cur = float(a_cur) + float(b_cur)
    total_base = float(a_base) + float(b_base)
    if total_base == 0:
        return round(total_cur, 2), None, None, cur_date_a, base_date_a

    total_abs = total_cur - total_base
    total_pct = (total_abs / total_base) * 100.0
    return round(total_cur, 2), round(total_abs, 2), round(total_pct, 4), cur_date_a, base_date_a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    _ = _read_json(args.history)  # kept for future expansion; not required for calculations here

    twse_rows = _get_rows(latest, "TWSE")
    tpex_rows = _get_rows(latest, "TPEX")

    twse_src, twse_url, twse_date = _get_meta(latest, "TWSE")
    tpex_src, tpex_url, tpex_date = _get_meta(latest, "TPEX")

    # Quality
    has_twse_latest = bool(twse_rows) and bool(twse_date)
    has_tpex_latest = bool(tpex_rows) and bool(tpex_date)

    enough_twse_20d = len(twse_rows) >= 21
    enough_tpex_20d = len(tpex_rows) >= 21

    if has_twse_latest and has_tpex_latest and enough_twse_20d and enough_tpex_20d:
        quality = "OK"
    elif has_twse_latest and has_tpex_latest:
        quality = "PARTIAL"
    else:
        quality = "LOW"

    # Current balances & 1D change for "資料" section
    def _current_balance(rows: List[Dict[str, Any]]) -> Optional[float]:
        return _safe_float(rows[0].get("balance_yi")) if rows else None

    twse_bal = _current_balance(twse_rows)
    tpex_bal = _current_balance(tpex_rows)

    twse_1d_abs, twse_1d_pct, twse_cur_dt, twse_base_dt_1d = _compute_horizon(twse_rows, 1)
    tpex_1d_abs, tpex_1d_pct, tpex_cur_dt, tpex_base_dt_1d = _compute_horizon(tpex_rows, 1)

    # Total current balance only if latest dates match
    total_bal: Optional[float] = None
    total_latest_date: Optional[str] = None
    if twse_cur_dt and tpex_cur_dt and twse_cur_dt == tpex_cur_dt and twse_bal is not None and tpex_bal is not None:
        total_bal = round(twse_bal + tpex_bal, 2)
        total_latest_date = twse_cur_dt

    # Summary direction: based on available 1D (prefer total if valid, else both, else single)
    direction = "NA"
    if total_latest_date is not None:
        # compute total 1D if base dates align
        tot_cur, tot_abs_1d, tot_pct_1d, tot_cur_dt, tot_base_dt = _compute_total(twse_rows, tpex_rows, 1)
        if tot_abs_1d is not None:
            if tot_abs_1d > 0:
                direction = "擴張"
            elif tot_abs_1d < 0:
                direction = "收縮"
            else:
                direction = "持平"
    else:
        # fallback: if both markets have 1D
        if twse_1d_abs is not None and tpex_1d_abs is not None:
            s = twse_1d_abs + tpex_1d_abs
            if s > 0:
                direction = "擴張（以可得市場近似）"
            elif s < 0:
                direction = "收縮（以可得市場近似）"
            else:
                direction = "持平（以可得市場近似）"
        elif twse_1d_abs is not None:
            direction = "擴張" if twse_1d_abs > 0 else ("收縮" if twse_1d_abs < 0 else "持平")
            direction += "（僅上市可得）"
        elif tpex_1d_abs is not None:
            direction = "擴張" if tpex_1d_abs > 0 else ("收縮" if tpex_1d_abs < 0 else "持平")
            direction += "（僅上櫃可得）"

    # 5D/20D
    twse_5d_abs, twse_5d_pct, _, _ = _compute_horizon(twse_rows, 5)
    twse_20d_abs, twse_20d_pct, _, _ = _compute_horizon(twse_rows, 20)

    tpex_5d_abs, tpex_5d_pct, _, _ = _compute_horizon(tpex_rows, 5)
    tpex_20d_abs, tpex_20d_pct, _, _ = _compute_horizon(tpex_rows, 20)

    # Total horizons (strict alignment)
    tot_cur, tot_abs_1d, tot_pct_1d, tot_cur_dt, tot_base_dt_1d = _compute_total(twse_rows, tpex_rows, 1)
    _, tot_abs_5d, tot_pct_5d, _, tot_base_dt_5d = _compute_total(twse_rows, tpex_rows, 5)
    _, tot_abs_20d, tot_pct_20d, _, tot_base_dt_20d = _compute_total(twse_rows, tpex_rows, 20)

    # Data section percentages: use 1D pct if available
    twse_data_pct = twse_1d_pct
    tpex_data_pct = tpex_1d_pct
    total_data_pct = tot_pct_1d

    # Build markdown (fixed structure)
    md = []
    md.append("# Taiwan Margin Financing Dashboard")
    md.append("")
    md.append("## 1) 結論")
    md.append(f"- {direction} + 資料品質 {quality}")
    md.append("")
    md.append("## 2) 資料")
    md.append(
        f"- 上市(TWSE)：融資餘額 {_fmt_num(twse_bal)} 億元；融資增減 {_fmt_num(twse_1d_abs)} 億元（%：{_fmt_num(twse_data_pct, 4)}）｜資料日期 {twse_date or 'NA'}｜來源：{twse_src}（{twse_url}）"
    )
    md.append(
        f"- 上櫃(TPEX)：融資餘額 {_fmt_num(tpex_bal)} 億元；融資增減 {_fmt_num(tpex_1d_abs)} 億元（%：{_fmt_num(tpex_data_pct, 4)}）｜資料日期 {tpex_date or 'NA'}｜來源：{tpex_src}（{tpex_url}）"
    )

    if total_latest_date is None:
        md.append(
            f"- 合計：NA（上市資料日期={twse_date or 'NA'}；上櫃資料日期={tpex_date or 'NA'}；日期不一致或缺值，依規則不得合計）"
        )
    else:
        md.append(
            f"- 合計：融資餘額 {_fmt_num(total_bal)} 億元；融資增減 {_fmt_num(tot_abs_1d)} 億元（%：{_fmt_num(total_data_pct, 4)}）｜資料日期 {total_latest_date}｜來源：TWSE={twse_src} / TPEX={tpex_src}"
        )

    md.append("")
    md.append("## 3) 計算")
    md.append("### 上市(TWSE)")
    md.append(f"- 1D：{_fmt_num(twse_1d_abs)} 億元；{_fmt_num(twse_1d_pct, 4)} %（基期日={twse_base_dt_1d or 'NA'}）")
    md.append(f"- 5D：{_fmt_num(twse_5d_abs)} 億元；{_fmt_num(twse_5d_pct, 4)} %")
    md.append(f"- 20D：{_fmt_num(twse_20d_abs)} 億元；{_fmt_num(twse_20d_pct, 4)} %")
    md.append("")
    md.append("### 上櫃(TPEX)")
    md.append(f"- 1D：{_fmt_num(tpex_1d_abs)} 億元；{_fmt_num(tpex_1d_pct, 4)} %（基期日={tpex_base_dt_1d or 'NA'}）")
    md.append(f"- 5D：{_fmt_num(tpex_5d_abs)} 億元；{_fmt_num(tpex_5d_pct, 4)} %")
    md.append(f"- 20D：{_fmt_num(tpex_20d_abs)} 億元；{_fmt_num(tpex_20d_pct, 4)} %")
    md.append("")
    md.append("### 合計(上市+上櫃)")
    if total_latest_date is None:
        md.append("- 1D：NA")
        md.append("- 5D：NA")
        md.append("- 20D：NA")
    else:
        md.append(f"- 1D：{_fmt_num(tot_abs_1d)} 億元；{_fmt_num(tot_pct_1d, 4)} %（基期日={tot_base_dt_1d or 'NA'}）")
        md.append(f"- 5D：{_fmt_num(tot_abs_5d)} 億元；{_fmt_num(tot_pct_5d, 4)} %（基期日={tot_base_dt_5d or 'NA'}）")
        md.append(f"- 20D：{_fmt_num(tot_abs_20d)} 億元；{_fmt_num(tot_pct_20d, 4)} %（基期日={tot_base_dt_20d or 'NA'}）")

    md.append("")
    md.append("## 4) 主要觸發原因")
    md.append("- 若出現 NA：通常是資料來源頁面改版/反爬，或交易日列數不足（< 6 / < 21）。")
    md.append("- 合計嚴格規則：只要「最新日」或「基期日」任一不一致，就不計算該 horizon 的合計（避免誤判）。")
    md.append("- 若品質顯示 PARTIAL/LOW：表示至少一個市場缺最新值或不足以計算 5D/20D。")
    md.append("")
    md.append("## 5) 下一步觀察重點")
    md.append("- 先把 TWSE/TPEX 都穩定連續抓滿 >=21 交易日（OK）後，再加 z60/p60/zΔ60/pΔ60 的統計模組，避免在資料斷裂時產生假訊號。")
    md.append("- 若 HiStock 偶發失敗：建議在 fetch 內加入替代來源（Yahoo / 官方），但一旦混用來源，品質要降級為 PARTIAL 並在資料段標示。")
    md.append("- 若你要做「泡沫模板」：下一步可把融資餘額做 rolling 視窗（例如 60/252）計算 percentile/zscore，並把觸發門檻獨立成 ruleset。")
    md.append("")
    md.append(f"_generated_at_utc: {_now_utc_iso()}_")

    _write_text(args.out, "\n".join(md))


if __name__ == "__main__":
    main()