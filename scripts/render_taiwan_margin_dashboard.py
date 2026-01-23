#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_taiwan_margin_dashboard.py

Render Taiwan margin financing dashboard from latest.json + history.json

Principles
- Use balance series from history for Δ and Δ% (not site-provided chg_yi).
- 合計 only if TWSE/TPEX latest date matches AND baseline dates for horizon match.
- Output audit-friendly markdown with NA handling.

品質降級（中等規則）
- 任一 Check 失敗 → PARTIAL

提前示警（基於本檔可得欄位，不引入外部行情）
- INFO / WATCH / ALERT 以合計(20D,5D,1D)與 TPEX vs TWSE 擴張差作判斷
- 加入簡單加速度：Accel = 1D% - (5D% / 5)（若資料不足則 NA）
- 加入風險偏好分層：Spread20 = TPEX_20D% - TWSE_20D%（若資料不足則 NA）
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# IO / formatting helpers
# ---------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def fmt_pct(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def yesno(ok: bool) -> str:
    return "✅（OK）" if ok else "❌（FAIL）"


def parse_ymd(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


# ---------------------------
# Data build / calc
# ---------------------------

def build_series_from_history(history_items: List[Dict[str, Any]], market: str) -> List[Tuple[str, float]]:
    """
    Return list of (date, balance) sorted desc by date.
    Dedup by date (keep last seen).
    """
    tmp: Dict[str, float] = {}
    for it in history_items:
        if it.get("market") != market:
            continue
        d = it.get("data_date")
        b = it.get("balance_yi")
        if d and isinstance(b, (int, float)):
            tmp[str(d)] = float(b)
    # YYYY-MM-DD lexical order == chronological order
    out = sorted(tmp.items(), key=lambda x: x[0], reverse=True)
    return out


def latest_balance_from_series(series: List[Tuple[str, float]]) -> Optional[float]:
    return series[0][1] if series else None


def latest_date_from_series(series: List[Tuple[str, float]]) -> Optional[str]:
    return series[0][0] if series else None


def calc_horizon(series: List[Tuple[str, float]], n: int) -> Dict[str, Any]:
    """
    n=1 -> 1D (need 2 points)
    n=5 -> 5D (need 6 points)
    n=20 -> 20D (need 21 points)
    """
    need = n + 1
    if len(series) < need:
        return {"delta": None, "pct": None, "base_date": None, "latest": None, "base": None}

    latest_d, latest_v = series[0]
    base_d, base_v = series[n]

    delta = latest_v - base_v
    pct = (delta / base_v * 100.0) if base_v != 0 else None

    return {
        "delta": delta,
        "pct": pct,
        "base_date": base_d,
        "latest": latest_v,
        "base": base_v,
    }


def total_calc(
    twse_s: List[Tuple[str, float]],
    tpex_s: List[Tuple[str, float]],
    n: int,
    twse_meta_date: Optional[str],
    tpex_meta_date: Optional[str],
) -> Dict[str, Any]:
    """
    合計 only if:
    - latest meta dates exist and match
    - both series have n+1 points
    - base_date for horizon matches (i.e., same base date)
    """
    tw = calc_horizon(twse_s, n)
    tp = calc_horizon(tpex_s, n)

    if (twse_meta_date is None) or (tpex_meta_date is None) or (twse_meta_date != tpex_meta_date):
        return {"delta": None, "pct": None, "base_date": None, "latest": None, "base": None, "ok": False,
                "reason": "latest date mismatch/NA"}

    if tw["base_date"] is None or tp["base_date"] is None:
        return {"delta": None, "pct": None, "base_date": None, "latest": None, "base": None, "ok": False,
                "reason": "insufficient history"}

    if tw["base_date"] != tp["base_date"]:
        return {"delta": None, "pct": None, "base_date": None, "latest": None, "base": None, "ok": False,
                "reason": "base_date mismatch"}

    if len(twse_s) < n + 1 or len(tpex_s) < n + 1:
        return {"delta": None, "pct": None, "base_date": None, "latest": None, "base": None, "ok": False,
                "reason": "insufficient history"}

    latest_tot = twse_s[0][1] + tpex_s[0][1]
    base_tot = twse_s[n][1] + tpex_s[n][1]
    delta = latest_tot - base_tot
    pct = (delta / base_tot * 100.0) if base_tot != 0 else None

    return {
        "delta": delta,
        "pct": pct,
        "base_date": tw["base_date"],
        "latest": latest_tot,
        "base": base_tot,
        "ok": True,
        "reason": "",
    }


# ---------------------------
# Latest meta extraction
# ---------------------------

def extract_latest_rows(latest_obj: Dict[str, Any], market: str) -> List[Dict[str, Any]]:
    series = latest_obj.get("series") or {}
    meta = series.get(market) or {}
    rows = meta.get("rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def extract_meta_date(latest_obj: Dict[str, Any], market: str) -> Optional[str]:
    series = latest_obj.get("series") or {}
    meta = series.get(market) or {}
    d = meta.get("data_date")
    return str(d) if d else None


def extract_source(latest_obj: Dict[str, Any], market: str) -> Tuple[str, str]:
    series = latest_obj.get("series") or {}
    meta = series.get(market) or {}
    src = meta.get("source") or "NA"
    url = meta.get("source_url") or "NA"
    return str(src), str(url)


# ---------------------------
# Checks (any fail => PARTIAL)
# ---------------------------

def check_min_rows(series: List[Tuple[str, float]], min_rows: int) -> Tuple[bool, str]:
    if len(series) < min_rows:
        return False, f"rows<{min_rows} (rows={len(series)})"
    return True, f"rows={len(series)}"


def check_base_date_in_series(series: List[Tuple[str, float]], base_date: Optional[str], tag: str) -> Tuple[bool, str]:
    if base_date is None:
        return False, f"{tag}.base_date=NA"
    dates = {d for d, _ in series}
    if base_date not in dates:
        return False, f"{tag}.base_date({base_date}) not found in series dates"
    return True, "OK"


def check_head5_strict_desc_unique(dates: List[str]) -> Tuple[bool, str]:
    head = dates[:5]
    if len(head) < 5:
        return False, f"head5 insufficient (n={len(head)})"
    # parseable?
    parsed = [parse_ymd(d) for d in head]
    if any(p is None for p in parsed):
        return False, "head5 contains non-YYYY-MM-DD date"
    # unique
    if len(set(head)) != len(head):
        return False, "duplicates in head5"
    # strict decreasing by date
    for i in range(len(parsed) - 1):
        if not (parsed[i] > parsed[i + 1]):
            return False, f"not strictly decreasing at i={i} ({head[i]} !> {head[i+1]})"
    return True, "OK"


def head5_pairs(rows: List[Dict[str, Any]]) -> List[Tuple[str, Optional[float]]]:
    out: List[Tuple[str, Optional[float]]] = []
    for r in rows[:5]:
        d = r.get("date")
        b = r.get("balance_yi")
        out.append((str(d) if d else "NA", float(b) if isinstance(b, (int, float)) else None))
    return out


# ---------------------------
# Early-warning signal logic
# ---------------------------

def safe_float(x: Any) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) else None


def calc_accel(pct_1d: Optional[float], pct_5d: Optional[float]) -> Optional[float]:
    """
    Accel = 1D% - (5D%/5). If any NA => NA
    """
    if pct_1d is None or pct_5d is None:
        return None
    return pct_1d - (pct_5d / 5.0)


def decide_signal(
    tot20_pct: Optional[float],
    tot5_pct: Optional[float],
    tot1_pct: Optional[float],
    spread20: Optional[float],
) -> Tuple[str, str]:
    """
    INFO / WATCH / ALERT based on available data only (no guessing).
    Returns (signal, rationale).
    """
    # If we can't compute 20D total pct, we refuse to label
    if tot20_pct is None:
        return "NA", "insufficient data (tot20_pct=NA)"

    # Base trend gate: 20D expansion/contraction band
    expansion = tot20_pct >= 8.0
    contraction = tot20_pct <= -8.0

    # If neither expansion nor contraction, we keep it neutral informational
    if not expansion and not contraction:
        # still can flag WATCH if short-term shock exists, but keep conservative:
        if tot1_pct is not None and abs(tot1_pct) >= 1.2:
            return "WATCH", "neutral 20D but large 1D swing (|1D%|>=1.2)"
        return "INFO", "20D within neutral band (|20D%|<8)"

    # Expansion regime
    if expansion:
        # Deleveraging alert: 20D high but 1D and 5D both negative
        if (tot1_pct is not None and tot5_pct is not None) and (tot1_pct < 0.0 and tot5_pct < 0.0):
            return "ALERT", "20D expansion but 1D%<0 and 5D%<0 (possible deleveraging)"
        # WATCH: acceleration or speculative tilt
        if tot1_pct is not None and tot1_pct >= 0.8:
            return "WATCH", "20D expansion + 1D%>=0.8 (leveraging acceleration)"
        if spread20 is not None and spread20 >= 3.0:
            return "WATCH", "20D expansion + TPEX-TWSE 20D spread>=3 (risk appetite hotter in TPEX)"
        # Otherwise INFO
        if tot5_pct is not None and tot5_pct > 0.0:
            return "INFO", "20D expansion + 5D%>0 (trend build-up)"
        return "INFO", "20D expansion (limited short-horizon confirmation)"

    # Contraction regime
    if contraction:
        # In contraction, any additional short-term negative confirms risk-off
        if (tot1_pct is not None and tot1_pct <= -0.8) or (tot5_pct is not None and tot5_pct < 0.0):
            return "WATCH", "20D contraction with short-term weakness"
        return "INFO", "20D contraction (short-horizon data limited)"

    return "NA", "unreachable"


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    latest = read_json(args.latest)
    hist = read_json(args.history)

    items = hist.get("items", []) if isinstance(hist, dict) else []
    if not isinstance(items, list):
        items = []

    # Build history series (used for Δ/Δ%)
    twse_s = build_series_from_history(items, "TWSE")
    tpex_s = build_series_from_history(items, "TPEX")

    # Latest meta + rows (used for quick sanity)
    twse_rows = extract_latest_rows(latest, "TWSE")
    tpex_rows = extract_latest_rows(latest, "TPEX")

    twse_meta_date = extract_meta_date(latest, "TWSE")
    tpex_meta_date = extract_meta_date(latest, "TPEX")

    twse_src, twse_url = extract_source(latest, "TWSE")
    tpex_src, tpex_url = extract_source(latest, "TPEX")

    twse_head_dates = [str(r.get("date")) for r in twse_rows[:3] if r.get("date")]
    twse_tail_dates = [str(r.get("date")) for r in twse_rows[-3:] if r.get("date")]
    tpex_head_dates = [str(r.get("date")) for r in tpex_rows[:3] if r.get("date")]
    tpex_tail_dates = [str(r.get("date")) for r in tpex_rows[-3:] if r.get("date")]

    # Horizons (from history series)
    tw1 = calc_horizon(twse_s, 1)
    tw5 = calc_horizon(twse_s, 5)
    tw20 = calc_horizon(twse_s, 20)

    tp1 = calc_horizon(tpex_s, 1)
    tp5 = calc_horizon(tpex_s, 5)
    tp20 = calc_horizon(tpex_s, 20)

    tot1 = total_calc(twse_s, tpex_s, 1, twse_meta_date, tpex_meta_date)
    tot5 = total_calc(twse_s, tpex_s, 5, twse_meta_date, tpex_meta_date)
    tot20 = total_calc(twse_s, tpex_s, 20, twse_meta_date, tpex_meta_date)

    # Derived metrics
    tot1_pct = safe_float(tot1.get("pct"))
    tot5_pct = safe_float(tot5.get("pct"))
    tot20_pct = safe_float(tot20.get("pct"))

    tw20_pct = safe_float(tw20.get("pct"))
    tp20_pct = safe_float(tp20.get("pct"))
    spread20 = (tp20_pct - tw20_pct) if (tp20_pct is not None and tw20_pct is not None) else None

    accel = calc_accel(tot1_pct, tot5_pct)

    # Label (conservative): only when 20D total pct calculable
    label = "NA"
    if tot20_pct is not None:
        if tot20_pct >= 8.0:
            label = "擴張"
        elif tot20_pct <= -8.0:
            label = "收縮"
        else:
            label = "中性"

    # ---------------------------
    # Checks (any fail => PARTIAL)
    # ---------------------------

    # Check-1: meta_date == history_series[0].date
    c1_tw_ok = (twse_meta_date is not None) and (latest_date_from_series(twse_s) is not None) and \
               (twse_meta_date == latest_date_from_series(twse_s))
    c1_tp_ok = (tpex_meta_date is not None) and (latest_date_from_series(tpex_s) is not None) and \
               (tpex_meta_date == latest_date_from_series(tpex_s))

    # Check-2: head5 dates strictly decreasing and unique (use latest.rows)
    twse_dates_from_rows = [str(r.get("date")) for r in twse_rows if r.get("date")]
    tpex_dates_from_rows = [str(r.get("date")) for r in tpex_rows if r.get("date")]
    c2_tw_ok, c2_tw_msg = check_head5_strict_desc_unique(twse_dates_from_rows)
    c2_tp_ok, c2_tp_msg = check_head5_strict_desc_unique(tpex_dates_from_rows)

    # Check-3: TWSE/TPEX head5 identical (date+balance) => likely wrong page
    if len(twse_rows) >= 5 and len(tpex_rows) >= 5:
        c3_ok = head5_pairs(twse_rows) != head5_pairs(tpex_rows)
        c3_msg = "OK" if c3_ok else "head5 identical (date+balance) => likely wrong page"
    else:
        c3_ok = False
        c3_msg = "insufficient rows for head5 comparison"

    # Check-4: history rows>=21 (Δ/Δ% depends on history series)
    c4_tw_ok, c4_tw_msg = check_min_rows(twse_s, 21)
    c4_tp_ok, c4_tp_msg = check_min_rows(tpex_s, 21)

    # Check-5: 20D base_date exists in series
    c5_tw_ok, c5_tw_msg = check_base_date_in_series(twse_s, tw20.get("base_date"), "TWSE_20D")
    c5_tp_ok, c5_tp_msg = check_base_date_in_series(tpex_s, tp20.get("base_date"), "TPEX_20D")

    any_fail = (
        (not c1_tw_ok) or (not c1_tp_ok) or
        (not c2_tw_ok) or (not c2_tp_ok) or
        (not c3_ok) or
        (not c4_tw_ok) or (not c4_tp_ok) or
        (not c5_tw_ok) or (not c5_tp_ok)
    )
    quality = "PARTIAL" if any_fail else "OK"

    # ---------------------------
    # Early-warning signal (does NOT override quality)
    # ---------------------------
    signal, rationale = decide_signal(tot20_pct, tot5_pct, tot1_pct, spread20)

    # ---------------------------
    # Render markdown
    # ---------------------------
    md: List[str] = []
    md.append("# Taiwan Margin Financing Dashboard")
    md.append("")
    md.append("## 1) 結論")
    md.append(f"- 狀態：{label}｜信號：{signal}｜資料品質：{quality}")
    md.append(f"  - rationale: {rationale}")
    md.append("")

    md.append("## 2) 資料")
    md.append(
        f"- 上市(TWSE)：融資餘額 {fmt_num(latest_balance_from_series(twse_s),2)} 億元｜資料日期 {twse_meta_date or 'NA'}｜來源：{twse_src}（{twse_url}）"
    )
    md.append(f"  - rows={len(twse_rows)}｜head_dates={twse_head_dates}｜tail_dates={twse_tail_dates}")

    md.append(
        f"- 上櫃(TPEX)：融資餘額 {fmt_num(latest_balance_from_series(tpex_s),2)} 億元｜資料日期 {tpex_meta_date or 'NA'}｜來源：{tpex_src}（{tpex_url}）"
    )
    md.append(f"  - rows={len(tpex_rows)}｜head_dates={tpex_head_dates}｜tail_dates={tpex_tail_dates}")

    # total balance (only if latest dates match and both latest balances exist)
    if (twse_meta_date is not None) and (twse_meta_date == tpex_meta_date) and \
       (latest_balance_from_series(twse_s) is not None) and (latest_balance_from_series(tpex_s) is not None):
        md.append(
            f"- 合計：融資餘額 {fmt_num(latest_balance_from_series(twse_s)+latest_balance_from_series(tpex_s),2)} 億元｜資料日期 {twse_meta_date}｜來源：TWSE=HiStock / TPEX=HiStock"
        )
    else:
        md.append("- 合計：NA（日期不一致或缺值，依規則不得合計）")
    md.append("")

    md.append("## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）")
    md.append("### 上市(TWSE)")
    md.append(
        f"- 1D：Δ={fmt_num(tw1['delta'],2)} 億元；Δ%={fmt_pct(tw1['pct'],4)} %｜latest={fmt_num(tw1['latest'],2)}｜base={fmt_num(tw1['base'],2)}（基期日={tw1['base_date'] or 'NA'}）"
    )
    md.append(
        f"- 5D：Δ={fmt_num(tw5['delta'],2)} 億元；Δ%={fmt_pct(tw5['pct'],4)} %｜latest={fmt_num(tw5['latest'],2)}｜base={fmt_num(tw5['base'],2)}（基期日={tw5['base_date'] or 'NA'}）"
    )
    md.append(
        f"- 20D：Δ={fmt_num(tw20['delta'],2)} 億元；Δ%={fmt_pct(tw20['pct'],4)} %｜latest={fmt_num(tw20['latest'],2)}｜base={fmt_num(tw20['base'],2)}（基期日={tw20['base_date'] or 'NA'}）"
    )
    md.append("")

    md.append("### 上櫃(TPEX)")
    md.append(
        f"- 1D：Δ={fmt_num(tp1['delta'],2)} 億元；Δ%={fmt_pct(tp1['pct'],4)} %｜latest={fmt_num(tp1['latest'],2)}｜base={fmt_num(tp1['base'],2)}（基期日={tp1['base_date'] or 'NA'}）"
    )
    md.append(
        f"- 5D：Δ={fmt_num(tp5['delta'],2)} 億元；Δ%={fmt_pct(tp5['pct'],4)} %｜latest={fmt_num(tp5['latest'],2)}｜base={fmt_num(tp5['base'],2)}（基期日={tp5['base_date'] or 'NA'}）"
    )
    md.append(
        f"- 20D：Δ={fmt_num(tp20['delta'],2)} 億元；Δ%={fmt_pct(tp20['pct'],4)} %｜latest={fmt_num(tp20['latest'],2)}｜base={fmt_num(tp20['base'],2)}（基期日={tp20['base_date'] or 'NA'}）"
    )
    md.append("")

    md.append("### 合計(上市+上櫃)")
    md.append(
        f"- 1D：Δ={fmt_num(safe_float(tot1.get('delta')),2)} 億元；Δ%={fmt_pct(tot1_pct,4)} %｜latest={fmt_num(safe_float(tot1.get('latest')),2)}｜base={fmt_num(safe_float(tot1.get('base')),2)}（基期日={tot1.get('base_date') or 'NA'}）"
    )
    md.append(
        f"- 5D：Δ={fmt_num(safe_float(tot5.get('delta')),2)} 億元；Δ%={fmt_pct(tot5_pct,4)} %｜latest={fmt_num(safe_float(tot5.get('latest')),2)}｜base={fmt_num(safe_float(tot5.get('base')),2)}（基期日={tot5.get('base_date') or 'NA'}）"
    )
    md.append(
        f"- 20D：Δ={fmt_num(safe_float(tot20.get('delta')),2)} 億元；Δ%={fmt_pct(tot20_pct,4)} %｜latest={fmt_num(safe_float(tot20.get('latest')),2)}｜base={fmt_num(safe_float(tot20.get('base')),2)}（基期日={tot20.get('base_date') or 'NA'}）"
    )
    md.append("")

    md.append("## 4) 提前示警輔助指標（不引入外部資料）")
    md.append(f"- Accel = 1D% - (5D%/5)：{fmt_pct(accel,4)}")
    md.append(f"- Spread20 = TPEX_20D% - TWSE_20D%：{fmt_pct(spread20,4)}")
    md.append("")

    md.append("## 5) 稽核備註")
    md.append("- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。")
    md.append("- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。")
    md.append("- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。")
    md.append("")

    md.append("## 6) 反方審核檢查（任一失敗 → PARTIAL）")
    md.append(f"- Check-1 TWSE meta_date==series[0].date：{yesno(c1_tw_ok)}")
    md.append(f"- Check-1 TPEX meta_date==series[0].date：{yesno(c1_tp_ok)}")
    md.append(f"- Check-2 TWSE head5 dates 嚴格遞減且無重複：{yesno(c2_tw_ok)}（{c2_tw_msg}）")
    md.append(f"- Check-2 TPEX head5 dates 嚴格遞減且無重複：{yesno(c2_tp_ok)}（{c2_tp_msg}）")
    md.append(f"- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：{yesno(c3_ok)}（{c3_msg}）")
    md.append(f"- Check-4 TWSE history rows>=21：{yesno(c4_tw_ok)}（{c4_tw_msg}）")
    md.append(f"- Check-4 TPEX history rows>=21：{yesno(c4_tp_ok)}（{c4_tp_msg}）")
    md.append(f"- Check-5 TWSE 20D base_date 存在於 series：{yesno(c5_tw_ok)}（{c5_tw_msg}）")
    md.append(f"- Check-5 TPEX 20D base_date 存在於 series：{yesno(c5_tp_ok)}（{c5_tp_msg}）")
    md.append("")

    md.append(f"_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_")
    md.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()