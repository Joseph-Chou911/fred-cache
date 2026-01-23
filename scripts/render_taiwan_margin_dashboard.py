#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _now_utc_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fmt_num(x: Optional[float], ndigits: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{ndigits}f}"


def _fmt_pct(x: Optional[float], ndigits: int = 4) -> str:
    if x is None:
        return "NA"
    return f"{x:.{ndigits}f}"


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _pick_primary_url(series_obj: Dict[str, Any]) -> str:
    u = series_obj.get("source_url") or ""
    # allow multi-url; keep as-is but trimmed
    return str(u).strip()


def _series_from_latest(latest: Dict[str, Any], market: str) -> Tuple[Optional[str], List[Dict[str, Any]], str, str]:
    """
    Returns: (data_date, rows_desc, source, source_url)
    rows_desc: list of {"date","balance_yi","chg_yi"} in DESC date order (latest first)
    """
    s = latest.get("series", {}).get(market, {}) or {}
    data_date = s.get("data_date")
    rows = s.get("rows", []) or []
    source = str(s.get("source") or "NA")
    source_url = _pick_primary_url(s)
    # normalize rows
    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        d = r.get("date")
        bal = _safe_float(r.get("balance_yi"))
        chg = _safe_float(r.get("chg_yi"))
        if d and bal is not None:
            out_rows.append({"date": str(d), "balance_yi": bal, "chg_yi": chg})
    return (str(data_date) if data_date else None, out_rows, source, source_url)


def _series_from_history(history: Dict[str, Any], market: str) -> Tuple[Optional[str], List[Dict[str, Any]], str, str]:
    """
    Build time series from history items.
    Returns (latest_date, rows_desc, source, source_url) where:
      - latest_date inferred from max(data_date)
      - source/source_url from the latest item (not perfect, but auditable)
    """
    items = history.get("items", []) or []
    # Dedup by date: keep last occurrence
    by_date: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if str(it.get("market", "")).upper() != market.upper():
            continue
        d = it.get("data_date")
        if not d:
            continue
        by_date[str(d)] = it

    if not by_date:
        return (None, [], "NA", "")

    # Sort dates desc
    dates = sorted(by_date.keys(), reverse=True)
    rows_desc: List[Dict[str, Any]] = []
    for d in dates:
        it = by_date[d]
        bal = _safe_float(it.get("balance_yi"))
        chg = _safe_float(it.get("chg_yi"))
        if bal is None:
            continue
        rows_desc.append({"date": d, "balance_yi": bal, "chg_yi": chg})

    latest_date = dates[0] if dates else None
    latest_item = by_date.get(latest_date, {})
    source = str(latest_item.get("source") or "NA")
    source_url = str(latest_item.get("source_url") or "").strip()
    return (latest_date, rows_desc, source, source_url)


def _calc_horizon(rows_desc: List[Dict[str, Any]], h: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    horizon h in trading days back:
      - 1D uses idx 1
      - 5D uses idx 5
      - 20D uses idx 20
    Returns (delta, pct, base_date)
      pct = delta / base_balance * 100
    """
    if not rows_desc or len(rows_desc) <= h:
        return (None, None, None)
    latest = rows_desc[0]
    base = rows_desc[h]
    latest_bal = _safe_float(latest.get("balance_yi"))
    base_bal = _safe_float(base.get("balance_yi"))
    if latest_bal is None or base_bal is None or base_bal == 0:
        return (None, None, base.get("date"))
    delta = latest_bal - base_bal
    pct = (delta / base_bal) * 100.0
    return (delta, pct, str(base.get("date")))


def _latest_chg_pct(latest_row: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    For the "融資增減(%)" field in section 2:
    Use chg_yi / previous_balance * 100 (previous trading day).
    If missing, NA.
    """
    if not latest_row:
        return None
    # if chg provided but we don't know base balance, caller should compute with series
    return None


def _data_quality(twse_ok: bool, tpex_ok: bool, twse_h20: bool, tpex_h20: bool, twse_h5: bool, tpex_h5: bool) -> str:
    if not (twse_ok and tpex_ok):
        return "LOW"
    if twse_h20 and tpex_h20 and twse_h5 and tpex_h5:
        return "OK"
    return "PARTIAL"


def _trend_word(twse_1d: Optional[float], tpex_1d: Optional[float]) -> str:
    # prefer total direction if both exist; else based on available
    vals = [v for v in [twse_1d, tpex_1d] if v is not None]
    if not vals:
        return "NA"
    s = sum(vals)
    if s > 0:
        return "擴張"
    if s < 0:
        return "收縮"
    return "持平"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="Path to taiwan_margin_cache/latest.json")
    ap.add_argument("--out", required=True, help="Output markdown path")
    ap.add_argument("--history", required=False, default=None, help="Optional path to taiwan_margin_cache/history.json")
    args = ap.parse_args()

    latest = _load_json(args.latest)
    history = None
    if args.history and os.path.exists(args.history):
        try:
            history = _load_json(args.history)
        except Exception:
            history = None

    # Build series (history preferred)
    if history is not None:
        twse_date_h, twse_rows_h, twse_src_h, twse_url_h = _series_from_history(history, "TWSE")
        tpex_date_h, tpex_rows_h, tpex_src_h, tpex_url_h = _series_from_history(history, "TPEX")
    else:
        twse_date_h, twse_rows_h, twse_src_h, twse_url_h = (None, [], "NA", "")
        tpex_date_h, tpex_rows_h, tpex_src_h, tpex_url_h = (None, [], "NA", "")

    twse_date_l, twse_rows_l, twse_src_l, twse_url_l = _series_from_latest(latest, "TWSE")
    tpex_date_l, tpex_rows_l, tpex_src_l, tpex_url_l = _series_from_latest(latest, "TPEX")

    # choose series: history if has rows, else latest
    twse_rows = twse_rows_h if twse_rows_h else twse_rows_l
    tpex_rows = tpex_rows_h if tpex_rows_h else tpex_rows_l

    twse_date = twse_date_h if twse_rows_h else twse_date_l
    tpex_date = tpex_date_h if tpex_rows_h else tpex_date_l

    twse_src = twse_src_h if twse_rows_h else twse_src_l
    tpex_src = tpex_src_h if tpex_rows_h else tpex_src_l
    twse_url = twse_url_h if twse_rows_h else twse_url_l
    tpex_url = tpex_url_h if tpex_rows_h else tpex_url_l

    # Latest row / balances
    twse_latest = twse_rows[0] if twse_rows else None
    tpex_latest = tpex_rows[0] if tpex_rows else None

    twse_bal = _safe_float(twse_latest.get("balance_yi")) if twse_latest else None
    tpex_bal = _safe_float(tpex_latest.get("balance_yi")) if tpex_latest else None
    twse_chg = _safe_float(twse_latest.get("chg_yi")) if twse_latest else None
    tpex_chg = _safe_float(tpex_latest.get("chg_yi")) if tpex_latest else None

    # "融資增減(%)" in section 2: use 1D base (previous trading day balance)
    def chg_pct(rows_desc: List[Dict[str, Any]]) -> Optional[float]:
        if len(rows_desc) < 2:
            return None
        latest_r = rows_desc[0]
        prev_r = rows_desc[1]
        chg = _safe_float(latest_r.get("chg_yi"))
        prev_bal = _safe_float(prev_r.get("balance_yi"))
        if chg is None or prev_bal is None or prev_bal == 0:
            return None
        return (chg / prev_bal) * 100.0

    twse_chg_pct = chg_pct(twse_rows) if twse_rows else None
    tpex_chg_pct = chg_pct(tpex_rows) if tpex_rows else None

    # Horizon calculations per market
    twse_1d, twse_1d_pct, twse_1d_base = _calc_horizon(twse_rows, 1)
    twse_5d, twse_5d_pct, twse_5d_base = _calc_horizon(twse_rows, 5)
    twse_20d, twse_20d_pct, twse_20d_base = _calc_horizon(twse_rows, 20)

    tpex_1d, tpex_1d_pct, tpex_1d_base = _calc_horizon(tpex_rows, 1)
    tpex_5d, tpex_5d_pct, tpex_5d_base = _calc_horizon(tpex_rows, 5)
    tpex_20d, tpex_20d_pct, tpex_20d_base = _calc_horizon(tpex_rows, 20)

    # Data-quality
    twse_ok = twse_date is not None and twse_bal is not None
    tpex_ok = tpex_date is not None and tpex_bal is not None
    twse_h5 = twse_5d is not None
    tpex_h5 = tpex_5d is not None
    twse_h20 = twse_20d is not None
    tpex_h20 = tpex_20d is not None
    quality = _data_quality(twse_ok, tpex_ok, twse_h20, tpex_h20, twse_h5, tpex_h5)

    # Total rules: only if latest dates match
    total_latest_allowed = (twse_date is not None and tpex_date is not None and twse_date == tpex_date)

    total_bal = (twse_bal + tpex_bal) if (total_latest_allowed and twse_bal is not None and tpex_bal is not None) else None
    total_chg = (twse_chg + tpex_chg) if (total_latest_allowed and twse_chg is not None and tpex_chg is not None) else None

    # Total "chg %" uses total_chg / (twse_prev + tpex_prev)
    def total_chg_pct_calc(tw_rows: List[Dict[str, Any]], tp_rows: List[Dict[str, Any]]) -> Optional[float]:
        if not total_latest_allowed:
            return None
        if len(tw_rows) < 2 or len(tp_rows) < 2:
            return None
        tw_prev = _safe_float(tw_rows[1].get("balance_yi"))
        tp_prev = _safe_float(tp_rows[1].get("balance_yi"))
        if tw_prev is None or tp_prev is None:
            return None
        base = tw_prev + tp_prev
        if base == 0 or total_chg is None:
            return None
        return (total_chg / base) * 100.0

    total_chg_pct = total_chg_pct_calc(twse_rows, tpex_rows)

    # Total horizons: require base dates match as well (avoid mismatched trading days)
    def total_horizon(h: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        if not total_latest_allowed:
            return (None, None, None)
        if len(twse_rows) <= h or len(tpex_rows) <= h:
            return (None, None, None)
        tw_base_date = str(twse_rows[h].get("date"))
        tp_base_date = str(tpex_rows[h].get("date"))
        if tw_base_date != tp_base_date:
            return (None, None, None)
        tw_latest_bal = _safe_float(twse_rows[0].get("balance_yi"))
        tp_latest_bal = _safe_float(tpex_rows[0].get("balance_yi"))
        tw_base_bal = _safe_float(twse_rows[h].get("balance_yi"))
        tp_base_bal = _safe_float(tpex_rows[h].get("balance_yi"))
        if None in [tw_latest_bal, tp_latest_bal, tw_base_bal, tp_base_bal]:
            return (None, None, tw_base_date)
        base = tw_base_bal + tp_base_bal
        latest_sum = tw_latest_bal + tp_latest_bal
        if base == 0:
            return (None, None, tw_base_date)
        delta = latest_sum - base
        pct = (delta / base) * 100.0
        return (delta, pct, tw_base_date)

    total_1d, total_1d_pct, total_1d_base = total_horizon(1)
    total_5d, total_5d_pct, total_5d_base = total_horizon(5)
    total_20d, total_20d_pct, total_20d_base = total_horizon(20)

    trend = _trend_word(twse_1d, tpex_1d)

    # Compose markdown
    lines: List[str] = []
    lines.append("# Taiwan Margin Financing Dashboard")
    lines.append("")
    lines.append("## 1) 結論")
    lines.append(f"- {trend} + 資料品質 {quality}")
    lines.append("")
    lines.append("## 2) 資料")
    lines.append(
        f"- 上市(TWSE)：融資餘額 {_fmt_num(twse_bal,2)} 億元；融資增減 {_fmt_num(twse_chg,2)} 億元（%：{_fmt_pct(twse_chg_pct,4)}）｜資料日期 {twse_date or 'NA'}｜來源：{twse_src}（{twse_url or 'NA'}）"
    )
    lines.append(
        f"- 上櫃(TPEX)：融資餘額 {_fmt_num(tpex_bal,2)} 億元；融資增減 {_fmt_num(tpex_chg,2)} 億元（%：{_fmt_pct(tpex_chg_pct,4)}）｜資料日期 {tpex_date or 'NA'}｜來源：{tpex_src}（{tpex_url or 'NA'}）"
    )
    if total_latest_allowed:
        lines.append(
            f"- 合計：融資餘額 {_fmt_num(total_bal,2)} 億元；融資增減 {_fmt_num(total_chg,2)} 億元（%：{_fmt_pct(total_chg_pct,4)}）｜資料日期 {twse_date}｜來源：TWSE={twse_src} / TPEX={tpex_src}"
        )
    else:
        lines.append(
            f"- 合計：NA（上市資料日期={twse_date or 'NA'}；上櫃資料日期={tpex_date or 'NA'}；日期不一致或缺值，依規則不得合計）"
        )

    lines.append("")
    lines.append("## 3) 計算")
    lines.append("### 上市(TWSE)")
    lines.append(f"- 1D：{_fmt_num(twse_1d,2)} 億元；{_fmt_pct(twse_1d_pct,4)} %（基期日={twse_1d_base or 'NA'}）")
    lines.append(f"- 5D：{_fmt_num(twse_5d,2)} 億元；{_fmt_pct(twse_5d_pct,4)} %（基期日={twse_5d_base or 'NA'}）")
    lines.append(f"- 20D：{_fmt_num(twse_20d,2)} 億元；{_fmt_pct(twse_20d_pct,4)} %（基期日={twse_20d_base or 'NA'}）")
    lines.append("")
    lines.append("### 上櫃(TPEX)")
    lines.append(f"- 1D：{_fmt_num(tpex_1d,2)} 億元；{_fmt_pct(tpex_1d_pct,4)} %（基期日={tpex_1d_base or 'NA'}）")
    lines.append(f"- 5D：{_fmt_num(tpex_5d,2)} 億元；{_fmt_pct(tpex_5d_pct,4)} %（基期日={tpex_5d_base or 'NA'}）")
    lines.append(f"- 20D：{_fmt_num(tpex_20d,2)} 億元；{_fmt_pct(tpex_20d_pct,4)} %（基期日={tpex_20d_base or 'NA'}）")
    lines.append("")
    lines.append("### 合計(上市+上櫃)")
    lines.append(f"- 1D：{_fmt_num(total_1d,2)} 億元；{_fmt_pct(total_1d_pct,4)} %（基期日={total_1d_base or 'NA'}）")
    lines.append(f"- 5D：{_fmt_num(total_5d,2)} 億元；{_fmt_pct(total_5d_pct,4)} %（基期日={total_5d_base or 'NA'}）")
    lines.append(f"- 20D：{_fmt_num(total_20d,2)} 億元；{_fmt_pct(total_20d_pct,4)} %（基期日={total_20d_base or 'NA'}）")

    lines.append("")
    lines.append("## 4) 主要觸發原因")
    lines.append("- 若出現 NA：通常是來源頁面改版/反爬，或交易日列數不足（<6 / <21），或 history 缺該市場。")
    lines.append("- 合計嚴格規則：僅在 TWSE 與 TPEX 最新資料日期一致時才允許合計；且各 horizon 基期日需一致，否則該 horizon 合計輸出 NA。")
    lines.append("- 若出現 TWSE/TPEX 數列異常相同：高機率抓錯頁面或市場識別失敗，應立即降級或停用該來源。")

    lines.append("")
    lines.append("## 5) 下一步觀察重點")
    lines.append("- 先確保 TWSE/TPEX 兩市場都能穩定連續抓到 >=21 交易日（才有資格維持 OK）。")
    lines.append("- 若未來加入 z60/p60/zΔ60/pΔ60：務必基於「交易日序列」且缺值不補，否則容易產生假訊號。")
    lines.append("- 若你要做泡沫監控：建議再加「融資餘額/成交金額」或「融資餘額/市值」類的比值指標，單看餘額容易受盤勢規模放大影響。")

    lines.append("")
    lines.append(f"_generated_at_utc: {_now_utc_iso_z()}_")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()