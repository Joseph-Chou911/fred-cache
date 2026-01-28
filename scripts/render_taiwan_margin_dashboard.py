#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_taiwan_margin_dashboard.py

Render Taiwan margin financing dashboard from latest.json + history.json

Key guarantees
- Δ/Δ% strictly computed from history balance series (not site chg column).
- 合計 only if (TWSE latest date == TPEX latest date) AND horizon base_date matches.
- roll25_cache is confirm-only: read repo JSON only; never fetch external data here.
- maint_ratio (proxy) is display-only: never affects margin_signal.
- Deterministic Margin × Roll25 resonance classification (no guessing).
- roll25 lookback inadequacy -> confidence NOTE (does NOT affect margin_quality).

Noise control
- roll25 window NOTE appears once only (in Summary).
- 2.2 does NOT repeat the same window note again.

This version fixes
- Do NOT treat missing latest.json top-level quality fields as FAIL.
- If roll25 indicates UsedDateStatus=DATA_NOT_UPDATED, show Check-6 as NOTE (stale), not FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


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


def line_check(name: str, ok: bool, msg: str) -> str:
    if ok:
        return f"- {name}：{yesno(True)}" if msg == "OK" else f"- {name}：{yesno(True)}（{msg}）"
    return f"- {name}：{yesno(False)}（{msg}）"


def line_note(name: str, msg: str) -> str:
    return f"- {name}：⚠️（NOTE）（{msg}）"


def _get(d: Any, k: str, default: Any = None) -> Any:
    return d.get(k, default) if isinstance(d, dict) else default


def norm_date_str(d: Any) -> Optional[str]:
    """
    Normalize date into YYYY-MM-DD if possible.
    Accepts:
      - YYYY-MM-DD
      - YYYYMMDD
    """
    if d is None:
        return None
    s = str(d).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s if s else None


def build_series_from_history(history_items: List[Dict[str, Any]], market: str) -> List[Tuple[str, float]]:
    tmp: Dict[str, float] = {}
    for it in history_items:
        if it.get("market") != market:
            continue
        d = norm_date_str(it.get("data_date"))
        b = it.get("balance_yi")
        if d and isinstance(b, (int, float)):
            tmp[str(d)] = float(b)
    return sorted(tmp.items(), key=lambda x: x[0], reverse=True)


def latest_balance_from_series(series: List[Tuple[str, float]]) -> Optional[float]:
    return series[0][1] if series else None


def latest_date_from_series(series: List[Tuple[str, float]]) -> Optional[str]:
    return series[0][0] if series else None


def calc_horizon(series: List[Tuple[str, float]], n: int) -> Dict[str, Any]:
    need = n + 1
    if len(series) < need:
        return {"delta": None, "pct": None, "base_date": None, "latest": None, "base": None}

    latest_d, latest_v = series[0]
    base_d, base_v = series[n]

    delta = latest_v - base_v
    pct = (delta / base_v * 100.0) if base_v != 0 else None

    return {"delta": delta, "pct": pct, "base_date": base_d, "latest": latest_v, "base": base_v}


def total_calc(
    twse_s: List[Tuple[str, float]],
    tpex_s: List[Tuple[str, float]],
    n: int,
    twse_meta_date: Optional[str],
    tpex_meta_date: Optional[str],
) -> Dict[str, Any]:
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

    latest_tot = twse_s[0][1] + tpex_s[0][1]
    base_tot = twse_s[n][1] + tpex_s[n][1]
    delta = latest_tot - base_tot
    pct = (delta / base_tot * 100.0) if base_tot != 0 else None

    return {"delta": delta, "pct": pct, "base_date": tw["base_date"], "latest": latest_tot, "base": base_tot,
            "ok": True, "reason": ""}


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
    return norm_date_str(meta.get("data_date"))


def extract_source(latest_obj: Dict[str, Any], market: str) -> Tuple[str, str]:
    series = latest_obj.get("series") or {}
    meta = series.get(market) or {}
    return str(meta.get("source") or "NA"), str(meta.get("source_url") or "NA")


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
        d = norm_date_str(r.get("date")) or "NA"
        b = r.get("balance_yi")
        out.append((str(d), float(b) if isinstance(b, (int, float)) else None))
    return out


def load_roll25(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        obj = read_json(path)
        if not isinstance(obj, dict):
            return None, "roll25 JSON not an object"
        return obj, None
    except FileNotFoundError:
        return None, f"roll25 file not found: {path}"
    except Exception as e:
        return None, f"roll25 read failed: {type(e).__name__}: {e}"


def load_maint(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path:
        return None, "maint path not provided"
    try:
        obj = read_json(path)
        if not isinstance(obj, dict):
            return None, "maint JSON not an object"
        return obj, None
    except FileNotFoundError:
        return None, f"maint file not found: {path}"
    except Exception as e:
        return None, f"maint read failed: {type(e).__name__}: {e}"


def roll25_used_date(roll: Dict[str, Any]) -> Optional[str]:
    ud = _get(_get(roll, "numbers", {}), "UsedDate", None)
    return norm_date_str(ud)


def roll25_used_date_status(roll: Dict[str, Any]) -> Optional[str]:
    # your roll25 report keeps this in signal.UsedDateStatus
    sig = _get(roll, "signal", {})
    uds = _get(sig, "UsedDateStatus", None)
    return str(uds) if uds is not None else None


def roll25_is_heated(roll: Dict[str, Any]) -> Optional[bool]:
    risk = _get(roll, "risk_level", None)
    sig = _get(roll, "signal", {})
    if risk is None and not isinstance(sig, dict):
        return None

    flags: List[bool] = []
    if isinstance(sig, dict):
        for k in ("VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak"):
            v = sig.get(k, None)
            if v is None:
                continue
            flags.append(bool(v))

    risk_heated = (str(risk) in ("中", "高")) if risk is not None else False
    return bool(risk_heated or any(flags))


def roll25_lookback_note(roll: Dict[str, Any], default_target: int = 20) -> Tuple[Optional[bool], str]:
    n_actual = _get(roll, "lookback_n_actual", None)
    n_target = _get(roll, "lookback_n_target", None)
    if n_target is None:
        n_target = default_target

    if n_actual is None:
        return None, "LookbackNActual=NA（cannot assess window adequacy）"
    try:
        na = int(n_actual)
        nt = int(n_target)
    except Exception:
        return None, f"LookbackNActual/Target not int (actual={n_actual}, target={n_target})"

    if na >= nt:
        return True, f"LookbackNActual={na}/{nt}（OK）"
    return False, f"LookbackNActual={na}/{nt}（window 未滿 → 信心降級）"


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

    state = "擴張" if tot20_pct >= 8.0 else ("收縮" if tot20_pct <= -8.0 else "中性")

    if (tot20_pct >= 8.0) and (tot1_pct is not None) and (tot5_pct is not None) and (tot1_pct < 0.0) and (tot5_pct < 0.0):
        return (state, "ALERT", "20D expansion + 1D%<0 and 5D%<0 (possible deleveraging)")

    watch = False
    if tot20_pct >= 8.0:
        if (tot1_pct is not None and tot1_pct >= 0.8):
            watch = True
        if (spread20 is not None and spread20 >= 3.0):
            watch = True
        if (accel is not None and accel >= 0.25):
            watch = True

    if watch:
        return (state, "WATCH", "20D expansion + (1D%>=0.8 OR Spread20>=3 OR Accel>=0.25)")

    if (tot20_pct >= 8.0) and (accel is not None) and (tot1_pct is not None):
        if (accel <= 0.0) and (tot1_pct < 0.3):
            return (state, "INFO", "cool-down candidate: Accel<=0 and 1D%<0.3 (needs 2–3 consecutive confirmations)")

    return (state, "NONE", "no rule triggered")


def determine_resonance(margin_signal: str, roll: Optional[Dict[str, Any]], strict_ok: bool) -> Tuple[str, str]:
    if roll is None or not strict_ok:
        return ("NA", "roll25 missing/mismatch => resonance NA (strict)")

    heated = roll25_is_heated(roll)
    if heated is None:
        return ("NA", "roll25 heated 判定欄位不足 => resonance NA (strict)")

    hot = bool(heated)
    ms_hot = (margin_signal in ("WATCH", "ALERT"))

    if ms_hot and hot:
        return ("RESONANCE", "Margin(WATCH/ALERT) and roll25 heated")
    if ms_hot and (not hot):
        return ("DIVERGENCE", "Margin(WATCH/ALERT) but roll25 not heated")
    if (not ms_hot) and hot:
        return ("MARKET_SHOCK_ONLY", "roll25 heated but Margin not heated")
    return ("QUIET", "no resonance rule triggered")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--roll25", default="roll25_cache/latest_report.json")
    ap.add_argument("--maint", default="", help="Optional maint_ratio_latest.json (proxy; display only)")
    args = ap.parse_args()

    latest = read_json(args.latest)
    hist = read_json(args.history)
    items = hist.get("items", []) if isinstance(hist, dict) else []
    if not isinstance(items, list):
        items = []

    # Top-level quality fields may not exist (your current latest.json doesn't have them)
    has_top_quality_fields = any(k in latest for k in ("fetch_status", "confidence", "dq_reason"))
    top_fetch_status = str(latest.get("fetch_status") or "NA")
    top_confidence = str(latest.get("confidence") or "NA")
    top_dq_reason = str(latest.get("dq_reason") or "NA")
    top_quality_ok: Optional[bool] = None
    if has_top_quality_fields:
        top_quality_ok = (top_fetch_status == "OK" and top_confidence == "OK")

    twse_s = build_series_from_history(items, "TWSE")
    tpex_s = build_series_from_history(items, "TPEX")

    twse_rows = extract_latest_rows(latest, "TWSE")
    tpex_rows = extract_latest_rows(latest, "TPEX")

    twse_meta_date = extract_meta_date(latest, "TWSE")
    tpex_meta_date = extract_meta_date(latest, "TPEX")

    twse_src, twse_url = extract_source(latest, "TWSE")
    tpex_src, tpex_url = extract_source(latest, "TPEX")

    twse_head_dates = [norm_date_str(r.get("date")) for r in twse_rows[:3] if r.get("date")]
    twse_tail_dates = [norm_date_str(r.get("date")) for r in twse_rows[-3:] if r.get("date")]
    tpex_head_dates = [norm_date_str(r.get("date")) for r in tpex_rows[:3] if r.get("date")]
    tpex_tail_dates = [norm_date_str(r.get("date")) for r in tpex_rows[-3:] if r.get("date")]

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

    # margin checks
    c1_tw_ok = (twse_meta_date is not None) and (latest_date_from_series(twse_s) is not None) and (twse_meta_date == latest_date_from_series(twse_s))
    c1_tp_ok = (tpex_meta_date is not None) and (latest_date_from_series(tpex_s) is not None) and (tpex_meta_date == latest_date_from_series(tpex_s))

    twse_dates_from_rows = [norm_date_str(r.get("date")) for r in twse_rows if r.get("date")]
    tpex_dates_from_rows = [norm_date_str(r.get("date")) for r in tpex_rows if r.get("date")]
    twse_dates_from_rows = [d for d in twse_dates_from_rows if d]
    tpex_dates_from_rows = [d for d in tpex_dates_from_rows if d]

    c2_tw_ok, c2_tw_msg = check_head5_strict_desc_unique([str(d) for d in twse_dates_from_rows])
    c2_tp_ok, c2_tp_msg = check_head5_strict_desc_unique([str(d) for d in tpex_dates_from_rows])

    if len(twse_rows) >= 5 and len(tpex_rows) >= 5:
        c3_ok = (head5_pairs(twse_rows) != head5_pairs(tpex_rows))
        c3_msg = "OK" if c3_ok else "head5 identical (date+balance) => likely wrong page"
    else:
        c3_ok, c3_msg = False, "insufficient rows for head5 comparison"

    c4_tw_ok, c4_tw_msg = check_min_rows(twse_s, 21)
    c4_tp_ok, c4_tp_msg = check_min_rows(tpex_s, 21)

    c5_tw_ok, c5_tw_msg = check_base_date_in_series(twse_s, tw20.get("base_date"), "TWSE_20D")
    c5_tp_ok, c5_tp_msg = check_base_date_in_series(tpex_s, tp20.get("base_date"), "TPEX_20D")

    margin_any_fail = (
        (not c1_tw_ok) or (not c1_tp_ok) or
        (not c2_tw_ok) or (not c2_tp_ok) or
        (not c3_ok) or
        (not c4_tw_ok) or (not c4_tp_ok) or
        (not c5_tw_ok) or (not c5_tp_ok)
    )
    margin_quality = "PARTIAL" if margin_any_fail else "OK"

    # IMPORTANT: only downgrade based on top-level quality if those fields exist
    if top_quality_ok is False:
        margin_quality = "PARTIAL"

    # roll25 confirm-only
    roll, roll_err = load_roll25(args.roll25)
    roll_ok = (roll is not None and roll_err is None)
    roll_used = roll25_used_date(roll) if roll else None
    roll_used_status = roll25_used_date_status(roll) if roll else None
    strict_roll_match = bool(roll_ok and twse_meta_date and roll_used and (roll_used == twse_meta_date))

    # Check-6 display policy:
    # - strict match => OK
    # - if roll indicates DATA_NOT_UPDATED => NOTE (stale) rather than FAIL
    # - otherwise => FAIL
    c6_roll_ok = strict_roll_match
    c6_roll_msg = "OK" if c6_roll_ok else f"UsedDate({roll_used or 'NA'}) != TWSE meta_date({twse_meta_date or 'NA'})"

    c7_lb_ok: Optional[bool] = None
    c7_lb_msg: str = "roll25 missing"
    if roll_ok and roll is not None:
        c7_lb_ok, c7_lb_msg = roll25_lookback_note(roll, default_target=20)

    resonance_label, resonance_rationale = determine_resonance(margin_signal, roll, strict_roll_match)

    # roll25 window note shown ONCE in Summary only
    roll25_window_note: Optional[str] = None
    if strict_roll_match and (c7_lb_ok is False or c7_lb_ok is None):
        roll25_window_note = c7_lb_msg

    # maint (proxy) display-only
    maint, maint_err = load_maint(args.maint)
    maint_ok = (maint is not None and maint_err is None)

    # render
    md: List[str] = []
    md.append("# Taiwan Margin Financing Dashboard")
    md.append("")
    md.append("## 1) 結論")
    md.append(f"- 狀態：{state_label}｜信號：{margin_signal}｜資料品質：{margin_quality}")
    md.append(f"  - rationale: {rationale}")

    if has_top_quality_fields:
        md.append(f"- 上游資料狀態（latest.json）：confidence={top_confidence}｜fetch_status={top_fetch_status}｜dq_reason={top_dq_reason}")
    else:
        md.append("- 上游資料狀態（latest.json）：⚠️（NOTE）（top-level confidence/fetch_status/dq_reason 未提供；不做 PASS/FAIL）")

    if resonance_label != "NA":
        md.append(f"- 一致性判定（Margin × Roll25）：{resonance_label}")
        md.append(f"  - rationale: {resonance_rationale}")
        if roll25_window_note:
            md.append(f"  - roll25_window_note: {roll25_window_note}")
    else:
        md.append(f"- 一致性判定（Margin × Roll25）：NA")
        # make the reason more explicit when stale
        if roll_ok and roll_used_status == "DATA_NOT_UPDATED":
            md.append("  - rationale: roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) => strict same-day match not satisfied")
        else:
            md.append(f"  - rationale: {resonance_rationale}")
        if roll_err:
            md.append(f"  - roll25_error: {roll_err}")
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

    md.append("## 2.0) 大盤融資維持率（proxy；僅供參考，不作為信號輸入）")
    md.append(f"- maint_path: {args.maint or 'NA'}")
    if maint_ok and maint is not None:
        md.append(f"- data_date: {_get(maint,'data_date','NA')}")
        md.append(f"- maint_ratio_pct(proxy): {_get(maint,'maint_ratio_pct','NA')}")
        md.append(f"- confidence: {_get(maint,'confidence','NA')}｜dq_reason: {_get(maint,'dq_reason','NA')}")
        md.append(f"- included_count: {_get(maint,'included_count','NA')}｜missing_price_count: {_get(maint,'missing_price_count','NA')}")
        md.append("- note: 此為由公開表格推算之 proxy，口徑可能與外部平台不同；只建議用於趨勢觀察，不建議用絕對值設閾值。")
    else:
        md.append(f"- maint_error: {maint_err or 'maint missing'}")
    md.append("")

    md.append("## 2.1) 台股成交量/波動（roll25_cache；confirm-only）")
    md.append(f"- roll25_path: {args.roll25}")
    if roll_ok and roll is not None:
        md.append(f"- UsedDate: {roll_used or 'NA'}｜UsedDateStatus: {roll_used_status or 'NA'}｜risk_level: {_get(roll,'risk_level','NA')}｜tag: {_get(roll,'tag','NA')}")
        md.append(f"- summary: {_get(roll,'summary','NA')}")
        nums = _get(roll, "numbers", {})
        md.append(
            "- numbers: "
            f"Close={_get(nums,'Close','NA')}, "
            f"PctChange={_get(nums,'PctChange','NA')}%, "
            f"TradeValue={_get(nums,'TradeValue','NA')}, "
            f"VolumeMultiplier={_get(nums,'VolumeMultiplier','NA')}, "
            f"AmplitudePct={_get(nums,'AmplitudePct','NA')}%, "
            f"VolMultiplier={_get(nums,'VolMultiplier','NA')}"
        )
        sig = _get(roll, "signal", {})
        md.append(
            "- signals: "
            f"DownDay={_get(sig,'DownDay','NA')}, "
            f"VolumeAmplified={_get(sig,'VolumeAmplified','NA')}, "
            f"VolAmplified={_get(sig,'VolAmplified','NA')}, "
            f"NewLow_N={_get(sig,'NewLow_N','NA')}, "
            f"ConsecutiveBreak={_get(sig,'ConsecutiveBreak','NA')}, "
            f"OhlcMissing={_get(sig,'OhlcMissing','NA')}"
        )
        md.append(f"- action: {_get(roll,'action','NA')}")
        md.append(f"- caveats: {_get(roll,'caveats','NA')}")
        md.append(f"- generated_at: {_get(roll,'generated_at','NA')} ({_get(roll,'timezone','NA')})")
    else:
        md.append(f"- roll25_error: {roll_err or 'roll25 missing'}")
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
    md.append("- roll25 若顯示 UsedDateStatus=DATA_NOT_UPDATED：代表資料延遲，Check-6 以 NOTE 呈現（非抓錯檔）。")
    md.append("- maint_ratio 為 proxy（display-only）：不作為 margin_signal 的輸入，僅供趨勢觀察。")
    md.append("")

    md.append("## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint 僅供對照）")
    if has_top_quality_fields:
        md.append(f"- Check-0 latest.json top-level quality OK：{yesno(bool(top_quality_ok))}（confidence={top_confidence}, fetch_status={top_fetch_status}, dq_reason={top_dq_reason}）")
    else:
        md.append(line_note("Check-0 latest.json top-level quality", "field not provided (skip pass/fail)"))

    md.append(f"- Check-1 TWSE meta_date==series[0].date：{yesno(c1_tw_ok)}")
    md.append(f"- Check-1 TPEX meta_date==series[0].date：{yesno(c1_tp_ok)}")
    md.append(line_check("Check-2 TWSE head5 dates 嚴格遞減且無重複", c2_tw_ok, c2_tw_msg))
    md.append(line_check("Check-2 TPEX head5 dates 嚴格遞減且無重複", c2_tp_ok, c2_tp_msg))
    md.append(line_check("Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁", c3_ok, c3_msg))
    md.append(line_check("Check-4 TWSE history rows>=21", c4_tw_ok, c4_tw_msg))
    md.append(line_check("Check-4 TPEX history rows>=21", c4_tp_ok, c4_tp_msg))
    md.append(line_check("Check-5 TWSE 20D base_date 存在於 series", c5_tw_ok, c5_tw_msg))
    md.append(line_check("Check-5 TPEX 20D base_date 存在於 series", c5_tp_ok, c5_tp_msg))

    # Check-6 policy
    if strict_roll_match:
        md.append("- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：✅（OK）")
    else:
        if roll_ok and roll_used_status == "DATA_NOT_UPDATED":
            md.append(line_note("Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）", f"roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) | {c6_roll_msg}"))
        else:
            md.append(line_check("Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）", False, f"{c6_roll_msg} or roll25 missing"))

    if strict_roll_match and c7_lb_ok is True:
        md.append(f"- Check-7 roll25 Lookback window（info）：✅（OK）（{c7_lb_msg}）")
    elif strict_roll_match:
        md.append(f"- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（{c7_lb_msg}）")
    else:
        md.append("- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（skipped: roll25 strict mismatch/missing）")

    if args.maint:
        if maint_ok and maint is not None:
            md.append(f"- Check-8 maint_ratio file readable（info）：✅（OK）（confidence={_get(maint,'confidence','NA')}, dq_reason={_get(maint,'dq_reason','NA')}）")
        else:
            md.append(f"- Check-8 maint_ratio file readable（info）：❌（FAIL）（{maint_err or 'maint missing'}）")
    else:
        md.append("- Check-8 maint_ratio file readable（info）：⚠️（NOTE）（skipped: --maint not provided）")
    md.append("")

    md.append(f"_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_")
    md.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()