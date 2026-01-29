#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_taiwan_margin_dashboard.py

Render Taiwan margin financing dashboard from latest.json + history.json

Key guarantees
- Δ/Δ% strictly computed from history balance series (not site chg column).
- 合計 only if (TWSE latest date == TPEX latest date) AND horizon base_date matches.
- roll25_cache is confirm-only: read repo JSON only; never fetch external data here.
- Deterministic Margin × Roll25 resonance classification (no guessing).
- roll25 lookback inadequacy -> NOTE (info-only; does NOT affect margin_quality).
- maint_ratio (proxy) is display-only (NOT signal input).

Resonance policy
- strict: require same-day match AND roll25 not stale (UsedDateStatus != DATA_NOT_UPDATED). Otherwise resonance=NA.
- latest: use latest available roll25 to classify resonance even if stale/date mismatch, but set resonance_confidence=DOWNGRADED and add resonance_note.

Noise control
- roll25 window NOTE appears once only (in Summary, when strict match but window inadequate/NA).
- 2.2 does NOT repeat the window note.
- NA reasons for resonance are standardized: (原因：ROLL25_STALE / ROLL25_MISSING / ROLL25_MISMATCH / ROLL25_FIELDS_INSUFFICIENT)
- Checks use fixed PASS/NOTE/FAIL semantics.

Display tweak (requested)
- In 2.1, derived risk_level is shown as 低/中/高(derived) when raw is NA.
- If UsedDateStatus=DATA_NOT_UPDATED, risk_level display gets “（stale）” suffix to avoid misread.
- Use existing resonance_confidence naming consistently across sections.

Maint ratio trend metrics (added; display-only)
- maint_ratio_1d_delta_pctpt: today - prev (pct-pt)
- maint_ratio_1d_pct_change: (today - prev) / prev * 100 (%)
- maint_ratio_policy: PROXY_TREND_ONLY
- maint_ratio_confidence: DOWNGRADED (always; proxy trend only, not absolute level)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ----------------- basic utils -----------------
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


def mark_pass() -> str:
    return "✅（PASS）"


def mark_fail() -> str:
    return "❌（FAIL）"


def mark_note(msg: str) -> str:
    return f"⚠️（NOTE）（{msg}）"


def line_check(name: str, status: str, detail: Optional[str] = None) -> str:
    """
    status must be one of: PASS / NOTE / FAIL
    """
    icon = {"PASS": mark_pass(), "NOTE": "⚠️（NOTE）", "FAIL": mark_fail()}.get(status, "⚠️（NOTE）")
    if detail is None or detail == "":
        return f"- {name}：{icon}"
    if status == "NOTE":
        return f"- {name}：{icon}（{detail}）"
    # PASS/FAIL with details
    return f"- {name}：{icon}（{detail}）"


def _get(d: Dict[str, Any], k: str, default: Any = None) -> Any:
    return d.get(k, default) if isinstance(d, dict) else default


# ----------------- margin series & calcs -----------------
def build_series_from_history(history_items: List[Dict[str, Any]], market: str) -> List[Tuple[str, float]]:
    tmp: Dict[str, float] = {}
    for it in history_items:
        if it.get("market") != market:
            continue
        d = it.get("data_date")
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
        return {
            "delta": None,
            "pct": None,
            "base_date": None,
            "latest": None,
            "base": None,
            "ok": False,
            "reason": "latest date mismatch/NA",
        }

    if tw["base_date"] is None or tp["base_date"] is None:
        return {
            "delta": None,
            "pct": None,
            "base_date": None,
            "latest": None,
            "base": None,
            "ok": False,
            "reason": "insufficient history",
        }

    if tw["base_date"] != tp["base_date"]:
        return {
            "delta": None,
            "pct": None,
            "base_date": None,
            "latest": None,
            "base": None,
            "ok": False,
            "reason": "base_date mismatch",
        }

    latest_tot = twse_s[0][1] + tpex_s[0][1]
    base_tot = twse_s[n][1] + tpex_s[n][1]
    delta = latest_tot - base_tot
    pct = (delta / base_tot * 100.0) if base_tot != 0 else None

    return {"delta": delta, "pct": pct, "base_date": tw["base_date"], "latest": latest_tot, "base": base_tot, "ok": True, "reason": ""}


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


# ----------------- latest.json extractors -----------------
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
    return str(meta.get("source") or "NA"), str(meta.get("source_url") or "NA")


# ----------------- check helpers -----------------
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


# ----------------- roll25 (confirm-only) -----------------
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


def roll25_used_date(roll: Dict[str, Any]) -> Optional[str]:
    ud = _get(_get(roll, "numbers", {}), "UsedDate", None)
    return str(ud) if ud else None


def roll25_used_date_status(roll: Dict[str, Any]) -> Optional[str]:
    sig = _get(roll, "signal", {})
    if isinstance(sig, dict):
        uds = sig.get("UsedDateStatus", None)
        return str(uds) if uds else None
    return None


def roll25_is_heated(roll: Dict[str, Any]) -> Optional[bool]:
    """
    Strict heated flag (bool) used for resonance.
    - If risk_level exists and is in {中,高} -> heated True
    - Or any signal flags True -> heated True
    - If fields insufficient -> None
    """
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
            if isinstance(v, (int, float)):
                flags.append(v > 0)
            else:
                flags.append(bool(v))

    risk_heated = (str(risk) in ("中", "高")) if risk is not None else False
    return bool(risk_heated or any(flags))


def roll25_risk_level_display(roll: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (display, raw).
    raw: roll['risk_level'] if exists else 'NA'
    display:
      - if raw in {低,中,高} -> raw
      - else derived from available flags count:
          0 -> 低(derived)
          1 -> 中(derived)
          >=2 -> 高(derived)
      - if cannot assess -> 'NA'
    """
    raw = _get(roll, "risk_level", None)
    raw_s = str(raw) if raw is not None else "NA"

    if raw_s in ("低", "中", "高"):
        return raw_s, raw_s

    sig = _get(roll, "signal", {})
    if not isinstance(sig, dict):
        return "NA", raw_s

    cnt = 0
    for k in ("VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak"):
        v = sig.get(k, None)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            if v > 0:
                cnt += 1
        else:
            if bool(v):
                cnt += 1

    if cnt >= 2:
        return "高(derived)", raw_s
    if cnt == 1:
        return "中(derived)", raw_s
    return "低(derived)", raw_s


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


def determine_resonance(margin_signal: str, roll: Dict[str, Any]) -> Tuple[str, str, Optional[str]]:
    """
    Returns (label, rationale, na_code).
    na_code is only set when label == "NA".
    """
    heated = roll25_is_heated(roll)
    if heated is None:
        return ("NA", "roll25 heated 判定欄位不足 => resonance NA (strict)", "ROLL25_FIELDS_INSUFFICIENT")

    hot = bool(heated)
    ms_hot = (margin_signal in ("WATCH", "ALERT"))

    if ms_hot and hot:
        return ("RESONANCE", "Margin(WATCH/ALERT) and roll25 heated", None)
    if ms_hot and (not hot):
        return ("DIVERGENCE", "Margin(WATCH/ALERT) but roll25 not heated", None)
    if (not ms_hot) and hot:
        return ("MARKET_SHOCK_ONLY", "roll25 heated but Margin not heated", None)
    return ("QUIET", "no resonance rule triggered", None)


def resonance_na(label: str, code: Optional[str]) -> str:
    if label != "NA" or not code:
        return label
    return f"{label}（原因：{code}）"


# ----------------- maint_ratio (proxy; display-only) -----------------
def load_maint_json(path: str, kind: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        obj = read_json(path)
        if not isinstance(obj, dict):
            return None, f"{kind} JSON not an object"
        return obj, None
    except FileNotFoundError:
        return None, f"{kind} file not found: {path}"
    except Exception as e:
        return None, f"{kind} read failed: {type(e).__name__}: {e}"


def maint_hist_items(hist_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = hist_obj.get("items", [])
    if not isinstance(items, list):
        return []
    out = [it for it in items if isinstance(it, dict) and it.get("data_date")]
    out.sort(key=lambda x: str(x.get("data_date")), reverse=True)
    return out


def maint_head5(hist_items: List[Dict[str, Any]]) -> List[Tuple[str, Optional[float]]]:
    out: List[Tuple[str, Optional[float]]] = []
    for it in hist_items[:5]:
        d = str(it.get("data_date") or "NA")
        v = it.get("maint_ratio_pct")
        out.append((d, float(v) if isinstance(v, (int, float)) else None))
    return out


def maint_check_head5_dates_strict(hist_items: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if len(hist_items) < 2:
        return False, f"head5 insufficient (history_rows={len(hist_items)})"
    dates = [str(it.get("data_date")) for it in hist_items[:5] if it.get("data_date")]
    ok, msg = check_head5_strict_desc_unique(dates)
    if ok:
        return True, "OK"
    return False, msg


def maint_derive_1d_trend(
    maint_latest: Optional[Dict[str, Any]],
    maint_hist_list: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Returns:
      - delta_pctpt: today - prev (pct-pt)
      - pct_change: (today - prev) / prev * 100 (%)
      - note: diagnostic string (for auditing)
    Uses ONLY existing JSON data. No external fetch.

    Priority:
      1) Use maint_latest.maint_ratio_pct as today.
      2) Use history list to find prev:
         - If hist[0] matches latest.data_date and hist has >=2, prev=hist[1]
         - Else if hist has >=1 and hist[0] is different date, treat hist[0] as prev (best-effort)
    """
    if not isinstance(maint_latest, dict):
        return None, None, "maint_latest missing"
    today = maint_latest.get("maint_ratio_pct")
    today_date = maint_latest.get("data_date")
    if not isinstance(today, (int, float)):
        return None, None, "maint_latest.maint_ratio_pct missing/non-numeric"

    if not maint_hist_list:
        return None, None, "maint_hist missing/empty"

    # helper to parse numeric
    def _num(x: Any) -> Optional[float]:
        return float(x) if isinstance(x, (int, float)) else None

    # candidate prev
    prev: Optional[float] = None
    prev_date: Optional[str] = None

    # strict-ish match: hist[0] is same date as latest -> prev should be hist[1]
    h0d = str(maint_hist_list[0].get("data_date") or "")
    if today_date is not None and h0d == str(today_date):
        if len(maint_hist_list) >= 2:
            prev = _num(maint_hist_list[1].get("maint_ratio_pct"))
            prev_date = str(maint_hist_list[1].get("data_date") or "NA")
            if prev is None:
                return None, None, "maint_hist[1].maint_ratio_pct missing/non-numeric"
        else:
            return None, None, "maint_hist has <2 rows; cannot compute 1D trend"
    else:
        # best-effort: treat hist[0] as prev if it's a different date
        prev = _num(maint_hist_list[0].get("maint_ratio_pct"))
        prev_date = str(maint_hist_list[0].get("data_date") or "NA")
        if prev is None:
            return None, None, "maint_hist[0].maint_ratio_pct missing/non-numeric"
        # note: may not be true D-1 if history gap exists
        # still acceptable as trend-only, but mark note
        # (report will already label proxy & downgraded)
    delta = float(today) - float(prev)
    pct_change = (delta / float(prev) * 100.0) if float(prev) != 0.0 else None

    note = f"trend_from: today={today}({today_date}), prev={prev}({prev_date})"
    return delta, pct_change, note


# ----------------- main -----------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--roll25", default="roll25_cache/latest_report.json")
    ap.add_argument("--maint", default="taiwan_margin_cache/maint_ratio_latest.json")
    ap.add_argument("--maint-hist", default="taiwan_margin_cache/maint_ratio_history.json")
    ap.add_argument("--resonance-policy", choices=["strict", "latest"], default="latest")
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

    # ---------- Margin data quality checks (these determine margin_quality) ----------
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

    # ---------- roll25 confirm-only ----------
    roll, roll_err = load_roll25(args.roll25)
    roll_ok = (roll is not None and roll_err is None)

    roll_used = roll25_used_date(roll) if roll else None
    roll_used_status = roll25_used_date_status(roll) if roll else None

    roll_risk_level_disp, roll_risk_level_raw = (("NA", "NA") if not roll_ok or not roll else roll25_risk_level_display(roll))
    if roll_used_status == "DATA_NOT_UPDATED" and roll_risk_level_disp != "NA":
        roll_risk_level_disp = f"{roll_risk_level_disp}（stale）"

    strict_same_day = bool(roll_ok and roll_used and twse_meta_date and (roll_used == twse_meta_date))
    strict_not_stale = bool(roll_ok and (roll_used_status is None or roll_used_status != "DATA_NOT_UPDATED"))
    strict_roll_match = bool(strict_same_day and strict_not_stale)

    resonance_policy = args.resonance_policy
    resonance_label: str = "NA"
    resonance_rationale: str = "NA"
    resonance_code: Optional[str] = None
    resonance_confidence: str = "DOWNGRADED"
    resonance_note: Optional[str] = None

    if not roll_ok or roll is None:
        c6_status = "NOTE"
        c6_msg = f"roll25 missing/unreadable ({roll_err or 'unknown'})"
        resonance_label = "NA"
        resonance_rationale = "roll25 missing => cannot classify resonance"
        resonance_code = "ROLL25_MISSING"
        resonance_confidence = "DOWNGRADED"
        resonance_note = None
    else:
        if roll_used_status == "DATA_NOT_UPDATED":
            c6_status = "NOTE"
            if strict_same_day:
                c6_msg = f"roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) | UsedDate({roll_used or 'NA'}) == TWSE({twse_meta_date or 'NA'})"
            else:
                c6_msg = f"roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) | UsedDate({roll_used or 'NA'}) vs TWSE({twse_meta_date or 'NA'})"
        else:
            if (roll_used is None) or (twse_meta_date is None):
                c6_status = "NOTE"
                c6_msg = f"UsedDate({roll_used or 'NA'}) vs TWSE({twse_meta_date or 'NA'}) (NA)"
            elif roll_used != twse_meta_date:
                c6_status = "FAIL"
                c6_msg = f"UsedDate({roll_used}) != TWSE({twse_meta_date})"
            else:
                c6_status = "PASS"
                c6_msg = "OK"

        if resonance_policy == "strict":
            if not strict_roll_match:
                resonance_label = "NA"
                if not strict_same_day:
                    resonance_code = "ROLL25_MISMATCH"
                    resonance_rationale = "roll25 date mismatch => strict same-day match not satisfied"
                elif roll_used_status == "DATA_NOT_UPDATED":
                    resonance_code = "ROLL25_STALE"
                    resonance_rationale = "roll25 stale (DATA_NOT_UPDATED) => strict same-day match not satisfied"
                else:
                    resonance_code = "ROLL25_MISSING"
                    resonance_rationale = "roll25 UsedDate/TWSE meta_date missing => strict same-day match not satisfied"
                resonance_confidence = "DOWNGRADED"
            else:
                resonance_label, resonance_rationale, resonance_code = determine_resonance(margin_signal, roll)
                resonance_confidence = "OK" if resonance_label != "NA" else "DOWNGRADED"
        else:
            resonance_label, resonance_rationale, resonance_code = determine_resonance(margin_signal, roll)
            if not strict_same_day or (roll_used_status == "DATA_NOT_UPDATED"):
                resonance_confidence = "DOWNGRADED"
                if roll_used_status == "DATA_NOT_UPDATED":
                    resonance_note = "roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）"
                    resonance_code = resonance_code or "ROLL25_STALE"
                elif not strict_same_day:
                    resonance_note = "roll25 date mismatch，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）"
                    resonance_code = resonance_code or "ROLL25_MISMATCH"
            else:
                resonance_confidence = "OK"
                resonance_note = None

    c7_status: str
    c7_msg: str
    roll25_window_note: Optional[str] = None
    if roll_ok and strict_roll_match and roll is not None:
        lb_ok, lb_msg = roll25_lookback_note(roll, default_target=20)
        if lb_ok is True:
            c7_status, c7_msg = "PASS", lb_msg
        else:
            c7_status, c7_msg = "NOTE", lb_msg
            roll25_window_note = lb_msg
    else:
        c7_status = "NOTE"
        if roll_ok and roll_used_status == "DATA_NOT_UPDATED":
            c7_msg = "skipped: roll25 stale (DATA_NOT_UPDATED)"
        else:
            c7_msg = "skipped: roll25 strict mismatch/missing"

    # ---------- maint_ratio (proxy; display-only) ----------
    maint_latest, maint_err = load_maint_json(args.maint, "maint") if args.maint else (None, "maint path not provided")
    maint_ok = (maint_latest is not None and maint_err is None)

    maint_hist_obj, maint_hist_err = load_maint_json(args.maint_hist, "maint_hist") if args.maint_hist else (None, "maint_hist path not provided")
    maint_hist_ok = (maint_hist_obj is not None and maint_hist_err is None)

    maint_hist_list: List[Dict[str, Any]] = maint_hist_items(maint_hist_obj) if maint_hist_ok and maint_hist_obj else []
    maint_head = maint_head5(maint_hist_list) if maint_hist_list else []

    # Added trend metrics (display-only)
    maint_ratio_policy = "PROXY_TREND_ONLY"
    maint_ratio_confidence = "DOWNGRADED"  # fixed: proxy trend only, not absolute level
    maint_ratio_1d_delta_pctpt: Optional[float] = None
    maint_ratio_1d_pct_change: Optional[float] = None
    maint_ratio_trend_note: Optional[str] = None

    if maint_ok:
        dlt, pchg, note = maint_derive_1d_trend(maint_latest, maint_hist_list)
        maint_ratio_1d_delta_pctpt = dlt
        maint_ratio_1d_pct_change = pchg
        maint_ratio_trend_note = note

    # Check-10: latest vs history[0] date (info-only)
    c10_status, c10_msg = "NOTE", "skipped: maint latest/history missing"
    if maint_ok and maint_hist_list:
        ld = _get(maint_latest, "data_date", None)
        hd = maint_hist_list[0].get("data_date")
        if ld and hd and str(ld) == str(hd):
            c10_status, c10_msg = "PASS", "OK"
        else:
            c10_status, c10_msg = "NOTE", f"latest.data_date({ld or 'NA'}) != hist[0].data_date({hd or 'NA'})"
    elif maint_ok and not maint_hist_list:
        c10_status, c10_msg = "NOTE", "head5 insufficient (history_rows=0)"
    elif (not maint_ok) and maint_hist_list:
        c10_status, c10_msg = "NOTE", "maint latest missing"

    # Check-11: head5 strict desc & unique (info-only)
    if maint_hist_list:
        c11_ok, c11_msg = maint_check_head5_dates_strict(maint_hist_list)
        c11_status = "PASS" if c11_ok else "NOTE"
    else:
        c11_status, c11_msg = "NOTE", "head5 insufficient (history_rows=0)"

    top_conf = latest.get("confidence", None) if isinstance(latest, dict) else None
    top_fetch = latest.get("fetch_status", None) if isinstance(latest, dict) else None
    top_dq = latest.get("dq_reason", None) if isinstance(latest, dict) else None
    has_top_quality = (top_conf is not None) or (top_fetch is not None) or (top_dq is not None)

    # ---------- render markdown ----------
    md: List[str] = []
    md.append("# Taiwan Margin Financing Dashboard")
    md.append("")
    md.append("## 1) 結論")
    md.append(f"- 狀態：{state_label}｜信號：{margin_signal}｜資料品質：{margin_quality}")
    md.append(f"  - rationale: {rationale}")

    if has_top_quality:
        md.append(f"- 上游資料狀態（latest.json）：confidence={top_conf or 'NA'}｜fetch_status={top_fetch or 'NA'}｜dq_reason={top_dq or 'NA'}")
    else:
        md.append(f"- 上游資料狀態（latest.json）：{mark_note('top-level confidence/fetch_status/dq_reason 未提供；不做 PASS/FAIL')}")

    md.append(f"- 一致性判定（Margin × Roll25）：{resonance_na(resonance_label, resonance_code)}")
    md.append(f"  - rationale: {resonance_rationale}")
    md.append(f"  - resonance_policy: {resonance_policy}")
    if resonance_note:
        md.append(f"  - resonance_note: {resonance_note}")
    md.append(f"  - resonance_confidence: {resonance_confidence}")
    if roll25_window_note:
        md.append(f"  - roll25_window_note: {roll25_window_note}")
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
    md.append(f"- maint_path: {args.maint if args.maint else 'NA'}")
    md.append(f"- maint_ratio_policy: {maint_ratio_policy}")
    md.append(f"- maint_ratio_confidence: {maint_ratio_confidence}")

    if maint_ok and maint_latest is not None:
        md.append(f"- data_date: {_get(maint_latest,'data_date','NA')}｜maint_ratio_pct: {_get(maint_latest,'maint_ratio_pct','NA')}")
        md.append(
            f"- maint_ratio_1d_delta_pctpt: {fmt_num(maint_ratio_1d_delta_pctpt, 6)}"
            f"｜maint_ratio_1d_pct_change: {fmt_num(maint_ratio_1d_pct_change, 6)}"
        )
        if maint_ratio_trend_note:
            md.append(f"- maint_ratio_trend_note: {maint_ratio_trend_note}")

        md.append(
            f"- totals: financing_amount_twd={_get(maint_latest,'total_financing_amount_twd','NA')}, "
            f"collateral_value_twd={_get(maint_latest,'total_collateral_value_twd','NA')}"
        )
        md.append(
            f"- coverage: included_count={_get(maint_latest,'included_count','NA')}, "
            f"missing_price_count={_get(maint_latest,'missing_price_count','NA')}"
        )
        md.append(
            f"- quality: fetch_status={_get(maint_latest,'fetch_status','NA')}, "
            f"confidence={_get(maint_latest,'confidence','NA')}, "
            f"dq_reason={_get(maint_latest,'dq_reason','NA')}"
        )
    else:
        md.append(f"- maint_error: {maint_err or 'maint missing'}")

    md.append("")
    md.append("## 2.0.1) 大盤融資維持率（history；display-only）")
    md.append(f"- maint_hist_path: {args.maint_hist if args.maint_hist else 'NA'}")
    if maint_hist_ok and maint_hist_obj is not None:
        md.append(f"- history_rows: {len(maint_hist_list)}")
        if maint_head:
            md.append(f"- head5: {maint_head}")
        else:
            md.append("- head5: NA（insufficient）")
    else:
        md.append(f"- maint_hist_error: {maint_hist_err or 'maint_hist missing'}")
    md.append("")

    md.append("## 2.1) 台股成交量/波動（roll25_cache；confirm-only）")
    md.append(f"- roll25_path: {args.roll25}")
    if roll_ok and roll is not None:
        md.append(
            f"- UsedDate: {roll_used or 'NA'}｜UsedDateStatus: {roll_used_status or 'NA'}｜"
            f"risk_level: {roll_risk_level_disp}｜risk_level_raw: {roll_risk_level_raw}｜tag: {_get(roll,'tag','NA')}"
        )
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
        md.append(f"- resonance_confidence: {resonance_confidence}")
    else:
        md.append(f"- roll25_error: {roll_err or 'roll25 missing'}")
        md.append(f"- resonance_confidence: {resonance_confidence}")
    md.append("")

    md.append("## 2.2) 一致性判定（Margin × Roll25 共振）")
    md.append("- 規則（deterministic，不猜）：")
    md.append("  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE")
    md.append("  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）")
    md.append("  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）")
    md.append("  4. 其餘 → QUIET")
    md.append(f"- 判定：{resonance_na(resonance_label, resonance_code)}（{resonance_rationale}）")
    md.append(f"- resonance_confidence: {resonance_confidence}")
    if resonance_note:
        md.append(f"- resonance_note: {resonance_note}")
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
    md.append("- roll25 若顯示 UsedDateStatus=DATA_NOT_UPDATED：代表資料延遲；Check-6 以 NOTE 呈現（非抓錯檔）。")
    md.append(f"- resonance_policy={resonance_policy}：strict 需同日且非 stale；latest 允許 stale/date mismatch 但會 resonance_confidence=DOWNGRADED。")
    md.append("- maint_ratio 為 proxy（display-only）：僅看趨勢與變化（Δ），不得用 proxy 絕對水位做門檻判斷。")
    md.append("")

    md.append("## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint 僅供對照）")
    md.append(f"- Check-0 latest.json top-level quality：{mark_note('field may be absent; does not affect margin_quality')}")
    md.append(line_check("Check-1 TWSE meta_date==series[0].date", "PASS" if c1_tw_ok else "FAIL"))
    md.append(line_check("Check-1 TPEX meta_date==series[0].date", "PASS" if c1_tp_ok else "FAIL"))
    md.append(line_check("Check-2 TWSE head5 dates 嚴格遞減且無重複", "PASS" if c2_tw_ok else "FAIL", None if c2_tw_ok else c2_tw_msg))
    md.append(line_check("Check-2 TPEX head5 dates 嚴格遞減且無重複", "PASS" if c2_tp_ok else "FAIL", None if c2_tp_ok else c2_tp_msg))
    md.append(line_check("Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁", "PASS" if c3_ok else "FAIL", None if c3_ok else c3_msg))
    md.append(line_check("Check-4 TWSE history rows>=21", "PASS" if c4_tw_ok else "FAIL", c4_tw_msg))
    md.append(line_check("Check-4 TPEX history rows>=21", "PASS" if c4_tp_ok else "FAIL", c4_tp_msg))
    md.append(line_check("Check-5 TWSE 20D base_date 存在於 series", "PASS" if c5_tw_ok else "FAIL", None if c5_tw_ok else c5_tw_msg))
    md.append(line_check("Check-5 TPEX 20D base_date 存在於 series", "PASS" if c5_tp_ok else "FAIL", None if c5_tp_ok else c5_tp_msg))

    md.append(line_check("Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）", c6_status, c6_msg))
    md.append(line_check("Check-7 roll25 Lookback window（info）", c7_status, c7_msg))

    md.append(line_check("Check-8 maint_ratio latest readable（info）", "PASS" if maint_ok else "NOTE", "OK" if maint_ok else (maint_err or "maint missing")))
    md.append(line_check("Check-9 maint_ratio history readable（info）", "PASS" if maint_hist_ok else "NOTE", "OK" if maint_hist_ok else (maint_hist_err or "maint_hist missing")))
    md.append(line_check("Check-10 maint latest vs history[0] date（info）", c10_status, c10_msg))
    md.append(line_check("Check-11 maint history head5 dates 嚴格遞減且無重複（info）", c11_status, c11_msg))

    md.append("")
    md.append(f"_generated_at_utc: {latest.get('generated_at_utc', now_utc_iso())}_")
    md.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()