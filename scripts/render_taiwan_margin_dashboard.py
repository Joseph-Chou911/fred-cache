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


def _fmt_num(x: Any, nd: int = 2) -> str:
    if x is None:
        return "NA"
    try:
        return f"{float(x):,.{nd}f}"
    except Exception:
        return "NA"


def _calc_change(rows: List[Dict[str, Any]], back_n: int) -> Tuple[Optional[float], Optional[float]]:
    """
    rows: 最新在前（index 0 最新）
    回傳：(delta_abs, delta_pct)
    delta_abs = latest_balance - base_balance
    delta_pct = delta_abs / base_balance * 100
    """
    if not rows or len(rows) <= back_n:
        return None, None
    latest = rows[0].get("financing_balance_bil")
    base = rows[back_n].get("financing_balance_bil")
    if latest is None or base is None or base == 0:
        return None, None
    delta_abs = float(latest) - float(base)
    delta_pct = delta_abs / float(base) * 100.0
    return delta_abs, delta_pct


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = _read_json(args.latest)
    series = latest.get("series", {})

    def market_block(market: str) -> Dict[str, Any]:
        s = series.get(market, {})
        rows = s.get("rows") or []
        data_date = s.get("data_date")
        bal = rows[0].get("financing_balance_bil") if rows else None
        chg = rows[0].get("financing_change_bil") if rows else None

        d1_abs, d1_pct = _calc_change(rows, 1)
        d5_abs, d5_pct = _calc_change(rows, 5)
        d20_abs, d20_pct = _calc_change(rows, 20)

        return {
            "market": market,
            "data_date": data_date,
            "source": s.get("source"),
            "source_url": s.get("source_url"),
            "bal": bal,
            "chg": chg,
            "deltas": {
                "1D": (d1_abs, d1_pct),
                "5D": (d5_abs, d5_pct),
                "20D": (d20_abs, d20_pct),
            },
            "row_count": len(rows),
            "notes": s.get("notes") or [],
        }

    twse = market_block("TWSE")
    tpex = market_block("TPEX")

    # 合計規則：只有日期相同才算
    total_ok = (twse["data_date"] is not None) and (twse["data_date"] == tpex["data_date"])
    total = {
        "market": "TOTAL",
        "data_date": twse["data_date"] if total_ok else None,
        "bal": (float(twse["bal"]) + float(tpex["bal"])) if total_ok and twse["bal"] is not None and tpex["bal"] is not None else None,
        "chg": (float(twse["chg"]) + float(tpex["chg"])) if total_ok and twse["chg"] is not None and tpex["chg"] is not None else None,
        "deltas": {"1D": (None, None), "5D": (None, None), "20D": (None, None)},
        "notes": [],
    }
    if not total_ok:
        total["notes"].append(f"上市資料日期={twse['data_date']}，上櫃資料日期={tpex['data_date']}，日期不一致 => 合計欄位依規則 NA")

    # data-quality
    def has_latest(m: Dict[str, Any]) -> bool:
        return m["data_date"] is not None and m["bal"] is not None

    def has_21(m: Dict[str, Any]) -> bool:
        return m["row_count"] >= 21

    if has_latest(twse) and has_latest(tpex) and has_21(twse) and has_21(tpex):
        dq = "OK"
    elif has_latest(twse) and has_latest(tpex):
        dq = "PARTIAL"
    else:
        dq = "LOW"

    # 一句話摘要（擴張/收縮/持平）：用「最新日融資增減(億)」判斷
    def expand_label(chg: Any) -> str:
        if chg is None:
            return "NA"
        try:
            x = float(chg)
        except Exception:
            return "NA"
        if x > 0:
            return "擴張"
        if x < 0:
            return "收縮"
        return "持平"

    summary = f"融資{expand_label(total['chg'] if total_ok else twse['chg'])} / 資料品質 {dq}"

    md = []
    md.append(f"# Taiwan Margin Financing Dashboard\n")
    md.append(f"- Summary: {summary}\n")
    md.append(f"- generated_at_utc: `{latest.get('generated_at_utc')}`\n")
    md.append("\n")

    def render_one(m: Dict[str, Any]) -> None:
        md.append(f"## {m['market']}\n")
        md.append(f"- data_date: `{m['data_date']}`\n")
        md.append(f"- source: `{m.get('source')}`\n")
        md.append(f"- source_url: {m.get('source_url')}\n")
        md.append(f"- 融資餘額(億): **{_fmt_num(m.get('bal'))}**\n")
        md.append(f"- 融資增減(億): **{_fmt_num(m.get('chg'))}**\n")
        md.append(f"- rows: {m.get('row_count')}\n")
        if m.get("notes"):
            md.append(f"- notes:\n")
            for n in m["notes"]:
                md.append(f"  - {n}\n")
        md.append("\n")
        md.append("| Window | 變化(億) | 變化(%) |\n")
        md.append("|---:|---:|---:|\n")
        for w in ("1D", "5D", "20D"):
            a, p = m["deltas"][w]
            md.append(f"| {w} | {_fmt_num(a)} | {_fmt_num(p)} |\n")
        md.append("\n")

    render_one(twse)
    render_one(tpex)
    render_one(total)

    _write_text(args.out, "".join(md))


if __name__ == "__main__":
    main()