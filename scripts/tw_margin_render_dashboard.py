#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _group_history_by_market(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        mk = str(it.get("market", "")).strip()
        dd = str(it.get("data_date", "")).strip()
        if not mk or not dd:
            continue
        out.setdefault(mk, []).append(it)
    # Sort per market by date desc
    for mk in out.keys():
        out[mk].sort(key=lambda x: str(x.get("data_date", "")), reverse=True)
    return out


def _unique_by_date_desc(rows: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    """
    Return list of (date, balance) unique by date, date desc.
    If duplicates exist, keep the last seen in the input order (but input should already be date desc).
    """
    seen = set()
    out: List[Tuple[str, float]] = []
    for it in rows:
        dd = str(it.get("data_date", "")).strip()
        bal = it.get("balance_yi", None)
        if not dd or bal is None:
            continue
        if dd in seen:
            continue
        seen.add(dd)
        try:
            b = float(bal)
        except Exception:
            continue
        out.append((dd, b))
    return out


def _delta_pct(latest: float, base: float) -> Tuple[float, float]:
    d = latest - base
    pct = (d / abs(base) * 100.0) if base != 0 else float("nan")
    return d, pct


def _calc_horizon(series: List[Tuple[str, float]], idx: int) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """
    idx=1 => 1D base at series[1]
    idx=5 => 5D base at series[5]
    idx=20 => 20D base at series[20]
    Returns (base_date, delta, pct)
    """
    if len(series) <= idx:
        return None, None, None
    latest_date, latest_val = series[0]
    base_date, base_val = series[idx]
    d, pct = _delta_pct(latest_val, base_val)
    return base_date, d, pct


def _fmt_num(x: Optional[float], digits: int = 2) -> str:
    if x is None:
        return "NA"
    try:
        return f"{x:.{digits}f}"
    except Exception:
        return "NA"


def _fmt_pct(x: Optional[float], digits: int = 4) -> str:
    if x is None:
        return "NA"
    try:
        return f"{x:.{digits}f}"
    except Exception:
        return "NA"


def _quality_label(n: int) -> str:
    return "OK" if n >= 21 else "PARTIAL"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = args.outdir
    hist_path = os.path.join(outdir, "history.json")
    latest_path = os.path.join(outdir, "latest.json")
    dash_path = os.path.join(outdir, "dashboard.md")

    hist = _read_json(hist_path)
    latest = _read_json(latest_path)
    if not hist or "items" not in hist:
        raise RuntimeError("history.json 不存在或格式不正確")

    items = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    by_mk = _group_history_by_market(items)

    # Market meta from latest.json (for sources/urls)
    meta = (latest or {}).get("series", {})

    markets = ["TWSE", "TPEX"]
    mk_series: Dict[str, List[Tuple[str, float]]] = {}
    mk_latest_date: Dict[str, Optional[str]] = {}
    mk_latest_balance: Dict[str, Optional[float]] = {}
    mk_src: Dict[str, str] = {}
    mk_url: Dict[str, str] = {}
    mk_n: Dict[str, int] = {}

    for mk in markets:
        rows = by_mk.get(mk, [])
        s = _unique_by_date_desc(rows)
        mk_series[mk] = s
        mk_n[mk] = len(s)
        mk_latest_date[mk] = s[0][0] if s else None
        mk_latest_balance[mk] = s[0][1] if s else None
        mk_src[mk] = str((meta.get(mk) or {}).get("source", "NA"))
        mk_url[mk] = str((meta.get(mk) or {}).get("source_url", "NA"))

    # Determine overall conclusion label
    same_latest = (mk_latest_date["TWSE"] is not None) and (mk_latest_date["TWSE"] == mk_latest_date["TPEX"])
    overall_ok = (mk_n["TWSE"] >= 21) and (mk_n["TPEX"] >= 21) and same_latest
    conclusion = "擴張 + 資料品質 OK" if overall_ok else "NA + 資料品質 PARTIAL"

    # Compute horizons per market
    horizons = [("1D", 1), ("5D", 5), ("20D", 20)]
    mk_calc: Dict[str, Dict[str, Any]] = {mk: {} for mk in markets}

    for mk in markets:
        s = mk_series[mk]
        for label, idx in horizons:
            base_date, d, pct = _calc_horizon(s, idx)
            mk_calc[mk][label] = {"base_date": base_date, "delta": d, "pct": pct}

    # Total calculation with strict alignment
    total_calc: Dict[str, Any] = {}
    for label, idx in horizons:
        # Need both markets enough length and same base dates + same latest dates
        tw = mk_series["TWSE"]
        tx = mk_series["TPEX"]
        if len(tw) <= idx or len(tx) <= idx:
            total_calc[label] = {"base_date": None, "delta": None, "pct": None}
            continue

        tw_latest_date, tw_latest_val = tw[0]
        tx_latest_date, tx_latest_val = tx[0]
        tw_base_date, tw_base_val = tw[idx]
        tx_base_date, tx_base_val = tx[idx]

        if tw_latest_date != tx_latest_date or tw_base_date != tx_base_date:
            total_calc[label] = {"base_date": None, "delta": None, "pct": None}
            continue

        latest_sum = tw_latest_val + tx_latest_val
        base_sum = tw_base_val + tx_base_val
        d, pct = _delta_pct(latest_sum, base_sum)
        total_calc[label] = {"base_date": tw_base_date, "delta": d, "pct": pct}

    # Render markdown
    gen = now_utc_iso()

    lines: List[str] = []
    lines.append("# Taiwan Margin Financing Dashboard\n")
    lines.append("## 1) 結論")
    lines.append(f"- {conclusion}\n")

    lines.append("## 2) 資料")
    for mk, label_zh in [("TWSE", "上市(TWSE)"), ("TPEX", "上櫃(TPEX)")]:
        dd = mk_latest_date[mk] or "NA"
        bal = mk_latest_balance[mk]
        lines.append(
            f"- {label_zh}：融資餘額 {_fmt_num(bal, 2)} 億元｜資料日期 {dd}｜來源：{mk_src[mk]}（{mk_url[mk]}）"
        )
    if same_latest and (mk_latest_balance["TWSE"] is not None) and (mk_latest_balance["TPEX"] is not None):
        lines.append(
            f"- 合計：融資餘額 {_fmt_num(mk_latest_balance['TWSE'] + mk_latest_balance['TPEX'], 2)} 億元｜資料日期 {mk_latest_date['TWSE']}｜來源：TWSE/TPEX={mk_src['TWSE']}"
        )
    else:
        lines.append("- 合計：融資餘額 NA 億元｜資料日期 NA｜來源：TWSE/TPEX=NA（最新日不一致或缺值）")
    lines.append("")

    lines.append("## 3) 計算（以 history.balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）")
    for mk, label_zh in [("TWSE", "上市(TWSE)"), ("TPEX", "上櫃(TPEX)")]:
        lines.append(f"### {label_zh}")
        for lbl, _ in horizons:
            base_date = mk_calc[mk][lbl]["base_date"]
            d = mk_calc[mk][lbl]["delta"]
            pct = mk_calc[mk][lbl]["pct"]
            bd = base_date or "NA"
            lines.append(f"- {lbl}：{_fmt_num(d, 2)} 億元；{_fmt_pct(pct, 4)} %（基期日={bd}）")
        lines.append("")

    lines.append("### 合計(上市+上櫃)")
    for lbl, _ in horizons:
        base_date = total_calc[lbl]["base_date"]
        d = total_calc[lbl]["delta"]
        pct = total_calc[lbl]["pct"]
        bd = base_date or "NA"
        lines.append(f"- {lbl}：{_fmt_num(d, 2)} 億元；{_fmt_pct(pct, 4)} %（基期日={bd}）")
    lines.append("")

    lines.append("## 4) 稽核備註")
    lines.append(f"- TWSE：len(unique_dates)={mk_n['TWSE']} → 品質 {_quality_label(mk_n['TWSE'])}")
    lines.append(f"- TPEX：len(unique_dates)={mk_n['TPEX']} → 品質 {_quality_label(mk_n['TPEX'])}")
    lines.append("- 合計僅在「最新日一致」且「基期日一致」時才計算（避免跨日錯配造成誤判）。")
    lines.append("- history 去重鍵為 (market, data_date)，seed 只會在該 market 尚無任何歷史資料時執行一次。")
    lines.append(f"\n_generated_at_utc: {gen}_\n")

    _write_text(dash_path, "\n".join(lines))


if __name__ == "__main__":
    main()