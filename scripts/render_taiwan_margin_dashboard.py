#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Render dashboard markdown for Taiwan margin-financing.

- Uses latest.series[market].rows as the authoritative trading-day sequence.
- 1D base = rows[1]
- 5D base = rows[5]
- 20D base = rows[20]
- If insufficient rows -> NA
- TOTAL only computed if:
  - latest date same for TWSE & TPEX
  - and base date same for TWSE & TPEX at each horizon
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def _fmt_pct(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def _get_row(rows: List[Dict[str, Any]], idx: int) -> Optional[Dict[str, Any]]:
    if not isinstance(rows, list):
        return None
    if idx < 0 or idx >= len(rows):
        return None
    r = rows[idx]
    return r if isinstance(r, dict) else None


def _calc_change(rows: List[Dict[str, Any]], horizon: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    horizon in {1,5,20}
    base index = horizon
    returns: (abs_change, pct_change, base_date)
    pct_change = abs_change / base_balance * 100
    """
    if horizon not in (1, 5, 20):
        return None, None, None
    r0 = _get_row(rows, 0)
    rb = _get_row(rows, horizon)
    if not r0 or not rb:
        return None, None, None
    b0 = r0.get("balance_yi")
    bb = rb.get("balance_yi")
    d0 = r0.get("date")
    db = rb.get("date")
    if b0 is None or bb is None or db is None:
        return None, None, None
    abs_chg = float(b0) - float(bb)
    pct = (abs_chg / float(bb) * 100.0) if float(bb) != 0 else None
    return abs_chg, pct, str(db)


def _infer_quality(twse: Dict[str, Any], tpex: Dict[str, Any], min_rows: int = 21) -> str:
    twse_ok = isinstance(twse.get("rows"), list) and len(twse["rows"]) >= min_rows and twse.get("data_date")
    tpex_ok = isinstance(tpex.get("rows"), list) and len(tpex["rows"]) >= min_rows and tpex.get("data_date")

    if not twse.get("data_date") or not tpex.get("data_date"):
        return "LOW"
    if twse_ok and tpex_ok:
        # if mixed sources, downgrade to PARTIAL
        if twse.get("source") != tpex.get("source"):
            return "PARTIAL"
        return "OK"
    return "PARTIAL"


def _direction_label(abs_1d_twse: Optional[float], abs_1d_tpex: Optional[float]) -> str:
    # Conservative: if both available and sum>0 => 擴張; <0 => 收縮; else 持平/NA
    vals = [v for v in [abs_1d_twse, abs_1d_tpex] if v is not None]
    if len(vals) == 0:
        return "NA"
    s = sum(vals)
    if s > 0:
        return "擴張"
    if s < 0:
        return "收縮"
    return "持平"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    series = latest.get("series", {})
    twse = series.get("TWSE", {}) if isinstance(series, dict) else {}
    tpex = series.get("TPEX", {}) if isinstance(series, dict) else {}

    twse_rows = twse.get("rows", []) if isinstance(twse, dict) else []
    tpex_rows = tpex.get("rows", []) if isinstance(tpex, dict) else []

    quality = _infer_quality(twse, tpex, min_rows=21)

    # Latest data
    twse_r0 = _get_row(twse_rows, 0)
    tpex_r0 = _get_row(tpex_rows, 0)

    twse_date = twse.get("data_date")
    tpex_date = tpex.get("data_date")

    twse_bal = float(twse_r0["balance_yi"]) if twse_r0 and twse_r0.get("balance_yi") is not None else None
    tpex_bal = float(tpex_r0["balance_yi"]) if tpex_r0 and tpex_r0.get("balance_yi") is not None else None

    twse_chg = float(twse_r0["chg_yi"]) if twse_r0 and twse_r0.get("chg_yi") is not None else None
    tpex_chg = float(tpex_r0["chg_yi"]) if tpex_r0 and tpex_r0.get("chg_yi") is not None else None

    # For "資料段" percent: use 1D base percent if possible
    twse_1d_abs, twse_1d_pct, twse_1d_base = _calc_change(twse_rows, 1)
    tpex_1d_abs, tpex_1d_pct, tpex_1d_base = _calc_change(tpex_rows, 1)

    # TOTAL (data row) only if same latest date
    total_allowed_latest = (twse_date is not None) and (tpex_date is not None) and (twse_date == tpex_date)

    total_bal = (twse_bal + tpex_bal) if (total_allowed_latest and twse_bal is not None and tpex_bal is not None) else None
    total_chg = (twse_chg + tpex_chg) if (total_allowed_latest and twse_chg is not None and tpex_chg is not None) else None

    # total pct (data row) uses combined 1D base if base date match
    total_data_pct = None
    if total_allowed_latest and twse_1d_base and tpex_1d_base and (twse_1d_base == tpex_1d_base):
        # base balances:
        twse_base = _get_row(twse_rows, 1).get("balance_yi") if _get_row(twse_rows, 1) else None
        tpex_base = _get_row(tpex_rows, 1).get("balance_yi") if _get_row(tpex_rows, 1) else None
        if twse_base is not None and tpex_base is not None:
            base_total = float(twse_base) + float(tpex_base)
            if base_total != 0 and total_chg is not None:
                # Use balance-diff based abs change for consistency
                abs_total_1d = (twse_1d_abs or 0.0) + (tpex_1d_abs or 0.0)
                total_data_pct = abs_total_1d / base_total * 100.0

    # Calculations per horizon
    horizons = [1, 5, 20]
    calc = {
        "TWSE": {h: _calc_change(twse_rows, h) for h in horizons},
        "TPEX": {h: _calc_change(tpex_rows, h) for h in horizons},
    }

    # TOTAL per horizon requires:
    # - latest dates same
    # - base dates same for that horizon
    total_calc: Dict[int, Tuple[Optional[float], Optional[float], Optional[str]]] = {}
    for h in horizons:
        tw_abs, tw_pct, tw_bd = calc["TWSE"][h]
        tp_abs, tp_pct, tp_bd = calc["TPEX"][h]
        if not total_allowed_latest or (tw_bd is None) or (tp_bd is None) or (tw_bd != tp_bd):
            total_calc[h] = (None, None, None)
            continue
        # base balances
        tw_base_row = _get_row(twse_rows, h)
        tp_base_row = _get_row(tpex_rows, h)
        if not tw_base_row or not tp_base_row:
            total_calc[h] = (None, None, None)
            continue
        tw_base = tw_base_row.get("balance_yi")
        tp_base = tp_base_row.get("balance_yi")
        if tw_base is None or tp_base is None:
            total_calc[h] = (None, None, None)
            continue
        base_total = float(tw_base) + float(tp_base)
        abs_total = (tw_abs or 0.0) + (tp_abs or 0.0) if (tw_abs is not None and tp_abs is not None) else None
        pct_total = (abs_total / base_total * 100.0) if (abs_total is not None and base_total != 0) else None
        total_calc[h] = (abs_total, pct_total, tw_bd)

    # Conclusion direction based on available 1D abs
    direction = _direction_label(twse_1d_abs, tpex_1d_abs)

    # Reasons (keep conservative)
    reasons: List[str] = []
    if direction == "擴張":
        reasons.append("融資餘額近 1D/5D/20D 方向多為上升（擴張），顯示槓桿需求增加。")
    elif direction == "收縮":
        reasons.append("融資餘額近 1D/5D/20D 方向偏下降（收縮），顯示去槓桿或風險偏好降溫。")
    else:
        reasons.append("可用資料不足或 1D 變化接近 0，暫不判定方向。")

    if quality != "OK":
        reasons.append(f"資料品質為 {quality}：可能因單一市場缺值/交易日列數不足或來源混用，需避免過度解讀。")

    if total_allowed_latest:
        reasons.append("上市與上櫃最新資料日期一致，因此合計可計算；若未來出現日期不一致，合計將依規則輸出 NA。")
    else:
        reasons.append("上市與上櫃最新資料日期不一致或缺值，合計依規則輸出 NA（避免跨日錯配）。")

    # Next watchpoints
    watch: List[str] = [
        "先盯「合計 20D%」是否持續攀升：若融資餘額加速擴張，泡沫/脆弱性風險通常上升（但需搭配成交量與波動指標交叉驗證）。",
        "若未來要加 z60/p60/zΔ60/pΔ60：請以 history 連續累積 ≥60/252 交易日後再啟用，並保留 NA 規則避免假訊號。",
        "定期檢查資料來源是否改版：一旦出現 TWSE/TPEX 前 N 筆高度相似或市場識別缺失，應自動降級來源並標記 PARTIAL/LOW。",
    ]

    # Render markdown
    lines: List[str] = []
    lines.append("# Taiwan Margin Financing Dashboard")
    lines.append("")
    lines.append("## 1) 結論")
    lines.append(f"- {direction} + 資料品質 {quality}")
    lines.append("")
    lines.append("## 2) 資料")
    lines.append(
        f"- 上市(TWSE)：融資餘額 {_fmt_num(twse_bal,2)} 億元；融資增減 {_fmt_num(twse_chg,2)} 億元（%：{_fmt_pct(twse_1d_pct,4)}）"
        f"｜資料日期 {twse_date or 'NA'}｜來源：{twse.get('source','NA')}（{twse.get('source_url','NA')}）"
    )
    lines.append(
        f"- 上櫃(TPEX)：融資餘額 {_fmt_num(tpex_bal,2)} 億元；融資增減 {_fmt_num(tpex_chg,2)} 億元（%：{_fmt_pct(tpex_1d_pct,4)}）"
        f"｜資料日期 {tpex_date or 'NA'}｜來源：{tpex.get('source','NA')}（{tpex.get('source_url','NA')}）"
    )

    if total_allowed_latest:
        lines.append(
            f"- 合計：融資餘額 {_fmt_num(total_bal,2)} 億元；融資增減 {_fmt_num(total_chg,2)} 億元（%：{_fmt_pct(total_data_pct,4)}）"
            f"｜資料日期 {twse_date}｜來源：TWSE={twse.get('source','NA')} / TPEX={tpex.get('source','NA')}"
        )
    else:
        lines.append(
            f"- 合計：NA（上市資料日期={twse_date or 'NA'}；上櫃資料日期={tpex_date or 'NA'}；日期不一致或缺值，依規則不得合計）"
        )

    lines.append("")
    lines.append("## 3) 計算")
    lines.append("### 上市(TWSE)")
    for h in horizons:
        abs_chg, pct, base_d = calc["TWSE"][h]
        lines.append(f"- {h}D：{_fmt_num(abs_chg,2)} 億元；{_fmt_pct(pct,4)} %（基期日={base_d or 'NA'}）")

    lines.append("")
    lines.append("### 上櫃(TPEX)")
    for h in horizons:
        abs_chg, pct, base_d = calc["TPEX"][h]
        lines.append(f"- {h}D：{_fmt_num(abs_chg,2)} 億元；{_fmt_pct(pct,4)} %（基期日={base_d or 'NA'}）")

    lines.append("")
    lines.append("### 合計(上市+上櫃)")
    for h in horizons:
        abs_chg, pct, base_d = total_calc[h]
        if abs_chg is None or pct is None or base_d is None:
            lines.append(f"- {h}D：NA（需上市/上櫃最新日一致，且該 horizon 基期日一致；否則依規則不得合計）")
        else:
            lines.append(f"- {h}D：{_fmt_num(abs_chg,2)} 億元；{_fmt_pct(pct,4)} %（基期日={base_d}）")

    lines.append("")
    lines.append("## 4) 主要觸發原因")
    for r in reasons[:3]:
        lines.append(f"- {r}")

    lines.append("")
    lines.append("## 5) 下一步觀察重點")
    for w in watch[:3]:
        lines.append(f"- {w}")

    lines.append("")
    lines.append(f"_generated_at_utc: {now_utc_iso()}_")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())