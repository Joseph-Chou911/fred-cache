#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_taiwan_margin_dashboard.py

Render Taiwan margin financing dashboard from latest.json + history.json
+ (confirm-only) Read roll25_cache/latest_report.json for TWSE volume/volatility context.

Principles
- Use balance series from history for Δ and Δ% (not site-provided chg_yi).
- 合計 only if TWSE/TPEX latest date matches AND baseline dates for horizon match.
- Output audit-friendly markdown with NA handling.
- roll25 區塊只讀 repo 內既有 JSON（confirm-only）；不在此 workflow 內重抓資料。

品質降級（中等規則）
- 任一 Check 失敗 → PARTIAL
"""

from __future__ import annotations

import argparse
import json
import os
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


def read_json_optional(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return (obj, err). Only dict is accepted; otherwise err."""
    if not path:
        return None, "path=NA"
    if not os.path.exists(path):
        return None, f"file not found: {path}"
    try:
        obj = read_json(path)
        if not isinstance(obj, dict):
            return None, "json root is not dict"
        return obj, None
    except Exception as e:
        return None, f"read/parse error: {type(e).__name__}: {e}"


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


def line_check(name: str, ok: bool, msg: str) -> str:
    """
    Avoid duplicated '(OK)(OK)'.
    - If ok and msg == 'OK' -> only show ✅（OK）
    - If ok and msg != 'OK' -> show ✅（OK）（msg）
    - If fail -> show ❌（FAIL）（msg）
    """
    if ok:
        return f"- {name}：{yesno(True)}" if msg == "OK" else f"- {name}：{yesno(True)}（{msg}）"
    return f"- {name}：{yesno(False)}（{msg}）"


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
    out = sorted(tmp.items(), key=lambda x: x[0], reverse=True)  # YYYY-MM-DD sorts fine as string
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
# Extract / Checks
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
    if len(head) < 2:
        return False, "head5 insufficient"
    if len(set(head)) != len(head):
        return False, "duplicates in head5"
    for i in range(len(head) - 1):
        if not (head[i] > head[i + 1]):
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
# Signal rules (margin)
# ---------------------------

def calc_accel(one_d_pct: Optional[float], five_d_pct: Optional[float]) -> Optional[float]:
    if one_d_pct is None or five_d_pct is None:
        return None
    return one_d_pct - (five_d_pct / 5.0)


def calc_spread20(tpex_20d_pct: Optional[float], twse_20d_pct: Optional[float]) -> Optional[float]:
    if tpex_20d_pct is None or twse_20d_pct is None:
        return None
    return tpex_20d_pct - twse_20d_pct


def determine_signal(
    tot20_pct: Optional[float],
    tot1_pct: Optional[float],
    tot5_pct: Optional[float],
    accel: Optional[float],
    spread20: Optional[float],
) -> Tuple[str, str, str]:
    if tot20_pct is None:
        return ("NA", "NA", "insufficient total_20D% (NA)")

    if tot20_pct >= 8.0:
        state = "擴張"
    elif tot20_pct <= -8.0:
        state = "收縮"
    else:
        state = "中性"

    if (tot20_pct >= 8.0) and (tot1_pct is not None) and (tot5_pct is not None) and (tot1_pct < 0.0) and (tot5_pct < 0.0):
        return (state, "ALERT", "20D expansion + 1D%<0 and 5D%<0 (possible deleveraging)")

    watch_cond = False
    if tot20_pct >= 8.0:
        if (tot1_pct is not None and tot1_pct >= 0.8):
            watch_cond = True
        if (spread20 is not None and spread20 >= 3.0):
            watch_cond = True
        if (accel is not None and accel >= 0.25):
            watch_cond = True
    if watch_cond:
        return (state, "WATCH", "20D expansion + (1D%>=0.8 OR Spread20>=3 OR Accel>=0.25)")

    if (tot20_pct >= 8.0) and (accel is not None) and (tot1_pct is not None):
        if (accel <= 0.0) and (tot1_pct < 0.3):
            return (state, "INFO", "cool-down candidate: Accel<=0 and 1D%<0.3 (needs 2–3 consecutive confirmations)")

    return (state, "NONE", "no rule triggered")


# ---------------------------
# roll25 (confirm-only) helpers
# ---------------------------

def _b(x: Any) -> Optional[bool]:
    if isinstance(x, bool):
        return x
    return None


def _s(x: Any) -> Optional[str]:
    if x is None:
        return None
    ss = str(x).strip()
    return ss if ss else None


def _f(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return float(x)
    return None


def extract_roll25_fields(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize key fields used for markdown & checks.
    Accepts the schema you pasted (latest_report.json).
    """
    numbers = r.get("numbers") if isinstance(r.get("numbers"), dict) else {}
    signal = r.get("signal") if isinstance(r.get("signal"), dict) else {}

    used_date = _s(r.get("used_date")) or _s(numbers.get("UsedDate"))  # allow both
    risk_level = _s(r.get("risk_level"))
    tag = _s(r.get("tag"))
    summary = _s(r.get("summary"))
    action = _s(r.get("action"))
    caveats = _s(r.get("caveats"))
    generated_at = _s(r.get("generated_at"))  # local time string in your roll25
    timezone_name = _s(r.get("timezone"))

    out = {
        "used_date": used_date,
        "risk_level": risk_level,
        "tag": tag,
        "summary": summary,
        "action": action,
        "caveats": caveats,
        "generated_at": generated_at,
        "timezone": timezone_name,
        "numbers": {
            "Close": _f(numbers.get("Close")),
            "PctChange": _f(numbers.get("PctChange")),
            "TradeValue": numbers.get("TradeValue"),
            "VolumeMultiplier": _f(numbers.get("VolumeMultiplier")),
            "AmplitudePct": _f(numbers.get("AmplitudePct")),
            "VolMultiplier": _f(numbers.get("VolMultiplier")),
        },
        "signals": {
            "DownDay": _b(signal.get("DownDay")),
            "VolumeAmplified": _b(signal.get("VolumeAmplified")),
            "VolAmplified": _b(signal.get("VolAmplified")),
            "NewLow_N": _b(signal.get("NewLow_N")),
            "ConsecutiveBreak": _b(signal.get("ConsecutiveBreak")),
            "OhlcMissing": _b(signal.get("OhlcMissing")),
        },
    }
    return out


def roll25_is_heated(roll25: Dict[str, Any]) -> bool:
    """
    Deterministic 'heated' definition (no guessing):
    - risk_level in {"中","高"} OR
    - any key flags are True: VolumeAmplified / VolAmplified / NewLow_N / ConsecutiveBreak
    """
    rl = roll25.get("risk_level")
    if rl in ("中", "高"):
        return True

    sig = roll25.get("signals") if isinstance(roll25.get("signals"), dict) else {}
    for k in ("VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak"):
        if sig.get(k) is True:
            return True
    return False


def classify_resonance(margin_signal: str, roll25: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Return (label, rationale). Deterministic mapping:
    - If roll25 missing => NA
    - If margin_signal in {WATCH, ALERT} and roll25 heated => RESONANCE
    - If margin_signal in {WATCH, ALERT} and roll25 not heated => DIVERGENCE
    - If margin_signal not in {WATCH, ALERT} and roll25 heated => MARKET_SHOCK_ONLY
    - Else => QUIET
    """
    if roll25 is None:
        return ("NA", "roll25 unavailable (confirm-only)")

    heated = roll25_is_heated(roll25)
    if margin_signal in ("WATCH", "ALERT") and heated:
        return ("RESONANCE", "Margin(WATCH/ALERT) + roll25 heated")
    if margin_signal in ("WATCH", "ALERT") and (not heated):
        return ("DIVERGENCE", "Margin(WATCH/ALERT) but roll25 not heated")
    if margin_signal not in ("WATCH", "ALERT") and heated:
        return ("MARKET_SHOCK_ONLY", "roll25 heated but Margin not WATCH/ALERT")
    return ("QUIET", "no resonance condition met")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--roll25", default="roll25_cache/latest_report.json")
    args = ap.parse_args()

    latest = read_json(args.latest)
    hist = read_json(args.history)
    items = hist.get("items", []) if isinstance(hist, dict) else []
    if not isinstance(items, list):
        items = []

    twse_s = build_series_from_history(items, "TWSE")
    tpex_s = build_series_from_history(items, "TPEX")

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

    tw1 = calc_horizon(twse_s, 1)
    tw5 = calc_horizon(twse_s, 5)
    tw20 = calc_horizon(twse_s, 20)

    tp1 = calc_horizon(tpex_s, 1)
    tp5 = calc_horizon(tpex_s, 5)
    tp20 = calc_horizon(tpex_s, 20)

    tot1 = total_calc(twse_s, tpex_s, 1, twse_meta_date, tpex_meta_date)
    tot5 = total_calc(twse_s, tpex_s, 5, twse_meta_date, tpex_meta_date)
    tot20 = total_calc(twse_s, tpex_s, 20, twse_meta_date, tpex_meta_date)

    accel = calc_accel(tot1.get("pct"), tot5.get("pct"))
    spread20 = calc_spread20(tp20.get("pct"), tw20.get("pct"))

    state_label, margin_signal, rationale = determine_signal(
        tot20_pct=tot20.get("pct"),
        tot1_pct=tot1.get("pct"),
        tot5_pct=tot5.get("pct"),
        accel=accel,
        spread20=spread20,
    )

    # -------- roll25 (confirm-only) --------
    roll25_obj, roll25_err = read_json_optional(args.roll25)
    roll25_fields: Optional[Dict[str, Any]] = None
    if roll25_obj is not None and roll25_err is None:
        roll25_fields = extract_roll25_fields(roll25_obj)

    # -------- Checks --------
    c1_tw_ok = (twse_meta_date is not None) and (latest_date_from_series(twse_s) is not None) and (twse_meta_date == latest_date_from_series(twse_s))
    c1_tp_ok = (tpex_meta_date is not None) and (latest_date_from_series(tpex_s) is not None) and (tpex_meta_date == latest_date_from_series(tpex_s))

    twse_dates_from_rows = [str(r.get("date")) for r in twse_rows if r.get("date")]
    tpex_dates_from_rows = [str(r.get("date")) for r in tpex_rows if r.get("date")]
    c2_tw_ok, c2_tw_msg = check_head5_strict_desc_unique(twse_dates_from_rows)
    c2_tp_ok, c2_tp_msg = check_head5_strict_desc_unique(tpex_dates_from_rows)

    if len(twse_rows) >= 5 and len(tpex_rows) >= 5:
        c3_ok = (head5_pairs(twse_rows) != head5_pairs(tpex_rows))
        c3_msg = "OK" if c3_ok else "head5 identical (date+balance) => likely wrong page"
    else:
        c3_ok = False
        c3_msg = "insufficient rows for head5 comparison"

    c4_tw_ok, c4_tw_msg = check_min_rows(twse_s, 21)
    c4_tp_ok, c4_tp_msg = check_min_rows(tpex_s, 21)

    c5_tw_ok, c5_tw_msg = check_base_date_in_series(twse_s, tw20.get("base_date"), "TWSE_20D")
    c5_tp_ok, c5_tp_msg = check_base_date_in_series(tpex_s, tp20.get("base_date"), "TPEX_20D")

    # Check-6: roll25 UsedDate matches TWSE latest date (confirm-only)
    if roll25_fields is None:
        c6_ok = False
        c6_msg = f"roll25 unavailable: {roll25_err or 'NA'}"
    else:
        used = roll25_fields.get("used_date")
        if twse_meta_date is None:
            c6_ok = False
            c6_msg = "TWSE meta_date=NA"
        elif used is None:
            c6_ok = False
            c6_msg = "roll25 UsedDate/used_date=NA"
        else:
            c6_ok = (used == twse_meta_date)
            c6_msg = "OK" if c6_ok else f"UsedDate({used}) != TWSE({twse_meta_date})"

    any_fail = (
        (not c1_tw_ok) or (not c1_tp_ok) or
        (not c2_tw_ok) or (not c2_tp_ok) or
        (not c3_ok) or
        (not c4_tw_ok) or (not c4_tp_ok) or
        (not c5_tw_ok) or (not c5_tp_ok) or
        (not c6_ok)
    )
    quality = "PARTIAL" if any_fail else "OK"

    resonance_label, resonance_rationale = classify_resonance(margin_signal, roll25_fields)

    # -------- Render markdown --------
    md: List[str] = []
    md.append("# Taiwan Margin Financing Dashboard")
    md.append("")
    md.append("## 1) 結論")
    md.append(f"- 狀態：{state_label}｜信號：{margin_signal}｜資料品質：{quality}")
    md.append(f"  - rationale: {rationale}")
    md.append(f"- 一致性判定（Margin × Roll25）：{resonance_label}")
    md.append(f"  - rationale: {resonance_rationale}")
    md.append("")

    md.append("## 1.1) 判定標準（本 dashboard 內建規則）")
    md.append("### 1) WATCH（升溫）")
    md.append("- 條件：20D% ≥ 8 且 (1D% ≥ 0.8 或 Spread20 ≥ 3 或 Accel ≥ 0.25)")
    md.append("- 行動：把你其他風險模組（VIX / 信用 / 成交量）一起對照，確認是不是同向升溫。")
    md.append("")
    md.append("### 2) ALERT（疑似去槓桿）")
    md.append("- 條件：20D% ≥ 8 且 1D% < 0 且 5D% < 0")
    md.append("- 行動：優先看『是否出現連續負值』，因為可能開始踩踏。")
    md.append("")
    md.append("### 3) 解除 WATCH（降溫）")
    md.append("- 條件：20D% 仍高，但 Accel ≤ 0 且 1D% 回到 < 0.3（需連 2–3 次確認）")
    md.append("- 行動：代表短線槓桿加速結束，回到『擴張但不加速』。")
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

    if (twse_meta_date is not None) and (twse_meta_date == tpex_meta_date) and \
       (latest_balance_from_series(twse_s) is not None) and (latest_balance_from_series(tpex_s) is not None):
        md.append(
            f"- 合計：融資餘額 {fmt_num(latest_balance_from_series(twse_s)+latest_balance_from_series(tpex_s),2)} 億元｜資料日期 {twse_meta_date}｜來源：TWSE=HiStock / TPEX=HiStock"
        )
    else:
        md.append("- 合計：NA（日期不一致或缺值，依規則不得合計）")
    md.append("")

    # ---- roll25 block ----
    md.append("## 2.1) 台股成交量/波動（roll25_cache；confirm-only）")
    md.append(f"- roll25_path: {args.roll25}")
    if roll25_fields is None:
        md.append(f"- status: NA（{roll25_err or 'NA'}）")
    else:
        n = roll25_fields.get("numbers", {})
        s = roll25_fields.get("signals", {})
        md.append(f"- UsedDate: {roll25_fields.get('used_date') or 'NA'}｜risk_level: {roll25_fields.get('risk_level') or 'NA'}｜tag: {roll25_fields.get('tag') or 'NA'}")
        md.append(f"- summary: {roll25_fields.get('summary') or 'NA'}")
        md.append(
            "- numbers: "
            f"Close={fmt_num(n.get('Close'),2)}, "
            f"PctChange={fmt_num(n.get('PctChange'),3)}%, "
            f"TradeValue={n.get('TradeValue') if n.get('TradeValue') is not None else 'NA'}, "
            f"VolumeMultiplier={fmt_num(n.get('VolumeMultiplier'),3)}, "
            f"AmplitudePct={fmt_num(n.get('AmplitudePct'),3)}%, "
            f"VolMultiplier={fmt_num(n.get('VolMultiplier'),3)}"
        )
        md.append(
            "- signals: "
            f"DownDay={s.get('DownDay')}, "
            f"VolumeAmplified={s.get('VolumeAmplified')}, "
            f"VolAmplified={s.get('VolAmplified')}, "
            f"NewLow_N={s.get('NewLow_N')}, "
            f"ConsecutiveBreak={s.get('ConsecutiveBreak')}, "
            f"OhlcMissing={s.get('OhlcMissing')}"
        )
        md.append(f"- action: {roll25_fields.get('action') or 'NA'}")
        md.append(f"- caveats: {roll25_fields.get('caveats') or 'NA'}")
        ga = roll25_fields.get("generated_at") or "NA"
        tz = roll25_fields.get("timezone") or "NA"
        md.append(f"- generated_at: {ga} ({tz})")
    md.append("")

    md.append("## 2.2) 一致性判定（Margin × Roll25 共振）")
    md.append("- 規則（deterministic，不猜）：")
    md.append("  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE")
    md.append("  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）")
    md.append("  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）")
    md.append("  4. 其餘 → QUIET")
    md.append(f"- 判定：{resonance_label}（{resonance_rationale}）")
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
        f"- 1D：Δ={fmt_num(tot1.get('delta'),2)} 億元；Δ%={fmt_pct(tot1.get('pct'),4)} %｜latest={fmt_num(tot1.get('latest'),2)}｜base={fmt_num(tot1.get('base'),2)}（基期日={tot1.get('base_date') or 'NA'}）"
    )
    md.append(
        f"- 5D：Δ={fmt_num(tot5.get('delta'),2)} 億元；Δ%={fmt_pct(tot5.get('pct'),4)} %｜latest={fmt_num(tot5.get('latest'),2)}｜base={fmt_num(tot5.get('base'),2)}（基期日={tot5.get('base_date') or 'NA'}）"
    )
    md.append(
        f"- 20D：Δ={fmt_num(tot20.get('delta'),2)} 億元；Δ%={fmt_pct(tot20.get('pct'),4)} %｜latest={fmt_num(tot20.get('latest'),2)}｜base={fmt_num(tot20.get('base'),2)}（基期日={tot20.get('base_date') or 'NA'}）"
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
    md.append("- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。")
    md.append("")

    md.append("## 6) 反方審核檢查（任一失敗 → PARTIAL）")
    md.append(f"- Check-1 TWSE meta_date==series[0].date：{yesno(c1_tw_ok)}")
    md.append(f"- Check-1 TPEX meta_date==series[0].date：{yesno(c1_tp_ok)}")
    md.append(line_check("Check-2 TWSE head5 dates 嚴格遞減且無重複", c2_tw_ok, c2_tw_msg))
    md.append(line_check("Check-2 TPEX head5 dates 嚴格遞減且無重複", c2_tp_ok, c2_tp_msg))
    md.append(line_check("Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁", c3_ok, c3_msg))
    md.append(line_check("Check-4 TWSE history rows>=21", c4_tw_ok, c4_tw_msg))
    md.append(line_check("Check-4 TPEX history rows>=21", c4_tp_ok, c4_tp_msg))
    md.append(line_check("Check-5 TWSE 20D base_date 存在於 series", c5_tw_ok, c5_tw_msg))
    md.append(line_check("Check-5 TPEX 20D base_date 存在於 series", c5_tp_ok, c5_tp_msg))
    md.append(line_check("Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）", c6_ok, c6_msg))
    md.append("")

    md.append(f"_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_")
    md.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()