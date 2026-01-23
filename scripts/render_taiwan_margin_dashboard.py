#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "NA"


def _pct(delta: Optional[float], base: Optional[float]) -> Optional[float]:
    if delta is None or base is None:
        return None
    try:
        b = float(base)
        if b == 0:
            return None
        return float(delta) / abs(b) * 100.0
    except Exception:
        return None


def _series_from_history(history_items: List[Dict[str, Any]], market: str) -> List[Tuple[str, float]]:
    # 回傳按日期排序的 (date, balance_yi)
    out: List[Tuple[str, float]] = []
    for it in history_items:
        if str(it.get("market", "")).upper() != market:
            continue
        d = it.get("data_date")
        b = it.get("balance_yi")
        if not d or b is None:
            continue
        try:
            out.append((str(d), float(b)))
        except Exception:
            continue
    # sort by date string YYYY-MM-DD（lexicographic OK）
    out.sort(key=lambda x: x[0])
    return out


def _horizon_delta(series: List[Tuple[str, float]], n: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    # n=1 => 1D (need 2 points), n=5 => 5D (need 6 points) ...
    need = n + 1
    if len(series) < need:
        return None, None, None
    latest_date, latest_val = series[-1]
    base_date, base_val = series[-(n + 1)]
    delta = latest_val - base_val
    pct = _pct(delta, base_val)
    return delta, pct, base_date


def _quality(tw_len: int, tp_len: int) -> str:
    if tw_len >= 21 and tp_len >= 21:
        return "OK"
    if tw_len >= 2 or tp_len >= 2:
        return "PARTIAL"
    return "LOW"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    hist = _read_json(args.history)

    items = hist.get("items") or []
    tw = _series_from_history(items, "TWSE")
    tp = _series_from_history(items, "TPEX")

    quality = _quality(len(tw), len(tp))

    # latest info
    s = latest.get("series") or {}
    tw_meta = s.get("TWSE") or {}
    tp_meta = s.get("TPEX") or {}
    tw_date = tw_meta.get("data_date")
    tp_date = tp_meta.get("data_date")

    # deltas
    horizons = [("1D", 1), ("5D", 5), ("20D", 20)]

    def market_block(name: str, series: List[Tuple[str, float]]) -> List[str]:
        lines: List[str] = []
        lines.append(f"### {name}")
        for label, n in horizons:
            d, p, base = _horizon_delta(series, n)
            lines.append(f"- {label}：{_fmt_num(d, 2)} 億元；{_fmt_num(p, 4)} %（基期日={base or 'NA'}）")
        return lines

    # total (strict alignment)
    total_lines: List[str] = []
    total_lines.append("### 合計(上市+上櫃)")
    for label, n in horizons:
        tw_d, tw_p, tw_base = _horizon_delta(tw, n)
        tp_d, tp_p, tp_base = _horizon_delta(tp, n)

        # 合計只在「最新日一致 + 基期日一致」時成立
        if not tw or not tp:
            total_lines.append(f"- {label}：NA")
            continue

        tw_latest_date = tw[-1][0]
        tp_latest_date = tp[-1][0]
        if tw_latest_date != tp_latest_date or (tw_base or "") != (tp_base or ""):
            total_lines.append(f"- {label}：NA（日期錯配：latest {tw_latest_date}/{tp_latest_date} 或 base {tw_base}/{tp_base}）")
            continue

        if tw_d is None or tp_d is None:
            total_lines.append(f"- {label}：NA")
            continue

        delta = tw_d + tp_d
        # 合計% 用合計基期餘額
        tw_base_val = tw[-(n + 1)][1] if len(tw) >= n + 1 else None
        tp_base_val = tp[-(n + 1)][1] if len(tp) >= n + 1 else None
        base_sum = (tw_base_val + tp_base_val) if (tw_base_val is not None and tp_base_val is not None) else None
        pct = _pct(delta, base_sum)
        total_lines.append(f"- {label}：{_fmt_num(delta,2)} 億元；{_fmt_num(pct,4)} %（基期日={tw_base or 'NA'}）")

    # summary (direction by 1D delta sign if available)
    tw_1d, _, _ = _horizon_delta(tw, 1)
    tp_1d, _, _ = _horizon_delta(tp, 1)
    if tw_1d is None and tp_1d is None:
        direction = "NA"
    else:
        sgn = 0.0
        if tw_1d is not None:
            sgn += tw_1d
        if tp_1d is not None:
            sgn += tp_1d
        direction = "擴張" if sgn > 0 else ("收縮" if sgn < 0 else "持平")

    out_lines: List[str] = []
    out_lines.append("# Taiwan Margin Financing Dashboard\n")
    out_lines.append("## 1) 結論")
    out_lines.append(f"- {direction} + 資料品質 {quality}\n")

    out_lines.append("## 2) 資料")
    out_lines.append(f"- 上市(TWSE)：融資餘額 {_fmt_num(tw[-1][1],2) if tw else 'NA'} 億元｜資料日期 {tw_date or 'NA'}｜來源：{tw_meta.get('source','NA')}（{tw_meta.get('source_url','NA')}）")
    out_lines.append(f"- 上櫃(TPEX)：融資餘額 {_fmt_num(tp[-1][1],2) if tp else 'NA'} 億元｜資料日期 {tp_date or 'NA'}｜來源：{tp_meta.get('source','NA')}（{tp_meta.get('source_url','NA')}）")
    if tw and tp and (tw[-1][0] == tp[-1][0]):
        out_lines.append(f"- 合計：融資餘額 {_fmt_num(tw[-1][1] + tp[-1][1],2)} 億元｜資料日期 {tw[-1][0]}｜來源：TWSE/TPEX={tw_meta.get('source','NA')}")
    else:
        out_lines.append("- 合計：NA（上市/上櫃日期不一致或缺值，依規則禁止合計）")
    out_lines.append("")

    out_lines.append("## 3) 計算（以 history.balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）")
    out_lines.extend(market_block("上市(TWSE)", tw))
    out_lines.append("")
    out_lines.extend(market_block("上櫃(TPEX)", tp))
    out_lines.append("")
    out_lines.extend(total_lines)
    out_lines.append("")

    out_lines.append("## 4) 稽核備註")
    out_lines.append("- 若 1D/5D/20D 為 NA：代表 history 該市場交易日筆數不足（<2/<6/<21），或合計日期錯配（防誤判規則）。")
    out_lines.append("- 若 HiStock 改版導致欄名/表格結構變動：請先看 latest.json 的 notes 以定位。")
    out_lines.append("")
    out_lines.append(f"_generated_at_utc: {latest.get('generated_at_utc','NA')}_\n")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))


if __name__ == "__main__":
    main()