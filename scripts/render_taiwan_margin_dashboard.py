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

Display tweak
- In 2.1, derived risk_level is shown as 低/中/高(derived) when raw is NA.
- If UsedDateStatus=DATA_NOT_UPDATED, risk_level display gets “（stale）” suffix to avoid misread.
- Use existing resonance_confidence naming consistently across sections.

Maint ratio trend metrics (display-only)
- maint_ratio_1d_delta_pctpt: today - prev (pct-pt)
- maint_ratio_1d_pct_change: (today - prev) / prev * 100 (%)
- maint_ratio_policy: PROXY_TREND_ONLY
- maint_ratio_confidence: DOWNGRADED (always; proxy trend only, not absolute level)

Added (NO LOGIC CHANGE):
- Also emit a machine-readable signals_latest.json for unified dashboard ingestion.
  Default output: taiwan_margin_cache/signals_latest.json
  Use --signals-out to override.

Row-count display fix (NO LOGIC CHANGE):
- Avoid ambiguous "rows=" which mixed two different sources:
  - rows_latest_table: from latest.json series.{market}.rows (page/table rows; often ~30)
  - rows_series: from history.json derived balance series (calc input; often >30)

Threshold calibration (audit-safe; deterministic)
- Support --threshold-policy {fixed,percentile}
- percentile: derive thresholds from history.json distributions using target percentiles
- calibration uses ONLY internal derived metrics (no external fetch):
    - total_20d_pct series (for expansion/contraction thresholds)
    - total_1d_pct series (for watch1d threshold)
    - spread20 series (tpex_20d_pct - twse_20d_pct, strict base-date match per sample)
    - accel series (total_1d_pct - total_5d_pct/5)
- If insufficient samples (< calib_min_n) => fallback to fixed thresholds with explicit reason

OTC Guardrail (display-only, deterministic; does NOT change margin_signal):
- PREWATCH: TPEX_20D% >= (thr_expansion20 - guardrail_prewatch_gap)
  default gap=0.2 => prewatch at 7.8 when thr_expansion20=8.0
- OTC_ALERT: TPEX_20D% >= thr_expansion20 AND TPEX_1D% < 0 AND TPEX_5D% < 0
Purpose: avoid TOTAL-only dilution hiding OTC-led leverage stress early.

Implementation note:
- Guardrail is ON by default (audit-friendly, display-only).
- You can explicitly disable via --disable-otc-guardrail.
- Backward compatible: --enable-otc-guardrail is still accepted (no-op if already enabled).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timezone
from math import floor, ceil
from typing import Any, Dict, List, Optional, Tuple


# ----------------- fixed thresholds (baseline / fallback) -----------------
FIXED_THRESHOLDS: Dict[str, float] = {
    "expansion20": 8.0,        # tot20_pct >= 8 => expansion
    "contraction20": -8.0,     # tot20_pct <= -8 => contraction
    "watch1d": 0.8,            # tot1_pct >= 0.8
    "watchspread20": 3.0,      # spread20 >= 3.0
    "watchaccel": 0.25,        # accel >= 0.25
}


# ----------------- basic utils -----------------
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Any) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


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
    return f"- {name}：{icon}（{detail}）"


def _get(d: Dict[str, Any], k: str, default: Any = None) -> Any:
    return d.get(k, default) if isinstance(d, dict) else default


# ----------------- date parsing / normalization (audit-safe) -----------------
_DATE_YMD = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_DATE_YYYYMMDD = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def _parse_date_any(x: Any) -> Optional[date]:
    """
    Accept:
      - YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
      - YYYYMMDD
    Reject (return None):
      - MM/DD (ambiguous year)
      - anything else
    """
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x

    s = str(x).strip()
    if not s:
        return None

    m = _DATE_YMD.match(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except Exception:
            return None

    m = _DATE_YYYYMMDD.match(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except Exception:
            return None

    return None


def _norm_date_iso(x: Any) -> Optional[str]:
    d = _parse_date_any(x)
    return d.isoformat() if d else None


# ----------------- percentile (deterministic) -----------------
def percentile_value(values: List[float], p: float) -> Optional[float]:
    """
    Deterministic percentile with linear interpolation (numpy-like):
      idx = (p/100) * (n-1)
      v = v[lo]*(1-frac) + v[hi]*frac

    Returns None if values empty or p invalid.
    """
    if not values:
        return None
    if not isinstance(p, (int, float)):
        return None
    if p < 0.0 or p > 100.0:
        return None

    vals = sorted(float(x) for x in values)
    n = len(vals)
    if n == 1:
        return vals[0]

    if p <= 0.0:
        return vals[0]
    if p >= 100.0:
        return vals[-1]

    idx = (p / 100.0) * (n - 1)
    lo = int(floor(idx))
    hi = int(ceil(idx))
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


# ----------------- margin series & calcs -----------------
def build_series_from_history(history_items: List[Dict[str, Any]], market: str) -> List[Tuple[str, float]]:
    """
    Build NEWEST-FIRST series: [(YYYY-MM-DD, balance_yi), ...]
    Deterministic: if duplicates by date appear, last one seen wins (via dict overwrite).
    """
    tmp: Dict[str, float] = {}
    for it in history_items:
        if it.get("market") != market:
            continue
        d_iso = _norm_date_iso(it.get("data_date"))
        b = it.get("balance_yi")
        if d_iso and isinstance(b, (int, float)):
            tmp[d_iso] = float(b)

    pairs = list(tmp.items())
    pairs.sort(key=lambda x: _parse_date_any(x[0]) or date(1900, 1, 1), reverse=True)
    return pairs


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
    thresholds: Dict[str, float],
) -> Tuple[str, str, str]:
    """
    thresholds:
      - expansion20
      - contraction20
      - watch1d
      - watchspread20
      - watchaccel
    """
    if tot20_pct is None:
        return ("NA", "NA", "insufficient total_20D% (NA)")

    thr_exp = thresholds["expansion20"]
    thr_con = thresholds["contraction20"]
    thr_w1 = thresholds["watch1d"]
    thr_ws = thresholds["watchspread20"]
    thr_wa = thresholds["watchaccel"]

    state = "擴張" if tot20_pct >= thr_exp else ("收縮" if tot20_pct <= thr_con else "中性")

    # ALERT: suspected deleveraging inside high expansion regime
    if (tot20_pct >= thr_exp) and (tot1_pct is not None) and (tot5_pct is not None) and (tot1_pct < 0.0) and (tot5_pct < 0.0):
        return (state, "ALERT", "20D expansion + 1D%<0 and 5D%<0 (possible deleveraging)")

    # WATCH: heating candidates under high expansion regime
    watch = False
    if tot20_pct >= thr_exp:
        if (tot1_pct is not None and tot1_pct >= thr_w1):
            watch = True
        if (spread20 is not None and spread20 >= thr_ws):
            watch = True
        if (accel is not None and accel >= thr_wa):
            watch = True

    if watch:
        return (state, "WATCH", "20D expansion + (1D%>=thr OR Spread20>=thr OR Accel>=thr)")

    # INFO: cool-down candidate (kept fixed: accel<=0 and 1D%<0.3)
    if (tot20_pct >= thr_exp) and (accel is not None) and (tot1_pct is not None):
        if (accel <= 0.0) and (tot1_pct < 0.3):
            return (state, "INFO", "cool-down candidate: Accel<=0 and 1D%<0.3 (needs 2–3 consecutive confirmations)")

    return (state, "NONE", "no rule triggered")


# ----------------- OTC Guardrail (display-only) -----------------
def compute_otc_guardrail(
    tp20_pct: Optional[float],
    tp1_pct: Optional[float],
    tp5_pct: Optional[float],
    thr_expansion20: float,
    prewatch_gap: float,
) -> Dict[str, Any]:
    """
    Deterministic, display-only guardrail to avoid TOTAL-only dilution.

    Returns dict:
      - prewatch_threshold: thr_expansion20 - gap
      - prewatch_gap: gap
      - prewatch_hit: bool/None (debug-only; do NOT use as stage)
      - otc_alert_hit: bool/None
      - prewatch_stage: one of {ALERT, PREWATCH, NONE, NA}
      - label: one of {OTC_ALERT, PREWATCH, NONE, NA}  (kept for display compatibility)
      - rationale: string

    Note:
      - OTC_ALERT implies tp20 >= thr_expansion20, so prewatch_hit is typically True.
        Downstream should use prewatch_stage/label, not prewatch_hit.
    """
    prewatch_thr = float(thr_expansion20) - float(prewatch_gap)

    if tp20_pct is None:
        return {
            "prewatch_threshold": prewatch_thr,
            "prewatch_gap": float(prewatch_gap),
            "label": "NA",
            "prewatch_stage": "NA",
            "prewatch_hit": None,
            "otc_alert_hit": None,
            "rationale": "TPEX_20D% is NA => cannot assess OTC guardrail",
        }

    prewatch_hit = bool(tp20_pct >= prewatch_thr)

    # OTC_ALERT: mirror main ALERT logic but on TPEX only, and requires tp20>=thr_expansion20
    otc_alert_hit = (
        (tp20_pct >= thr_expansion20)
        and (tp1_pct is not None)
        and (tp5_pct is not None)
        and (tp1_pct < 0.0)
        and (tp5_pct < 0.0)
    )
    if otc_alert_hit:
        return {
            "prewatch_threshold": prewatch_thr,
            "prewatch_gap": float(prewatch_gap),
            "label": "OTC_ALERT",
            "prewatch_stage": "ALERT",
            "prewatch_hit": prewatch_hit,
            "otc_alert_hit": True,
            "rationale": "TPEX in expansion(>=thr) + 1D%<0 and 5D%<0 (OTC deleveraging shape)",
        }

    if prewatch_hit:
        return {
            "prewatch_threshold": prewatch_thr,
            "prewatch_gap": float(prewatch_gap),
            "label": "PREWATCH",
            "prewatch_stage": "PREWATCH",
            "prewatch_hit": True,
            "otc_alert_hit": False,
            "rationale": "TPEX_20D% approaching expansion threshold (dilution risk for TOTAL-only signal)",
        }

    return {
        "prewatch_threshold": prewatch_thr,
        "prewatch_gap": float(prewatch_gap),
        "label": "NONE",
        "prewatch_stage": "NONE",
        "prewatch_hit": False,
        "otc_alert_hit": False,
        "rationale": "no OTC guardrail triggered",
    }


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
    return _norm_date_iso(d)


def extract_source(latest_obj: Dict[str, Any], market: str) -> Tuple[str, str]:
    series = latest_obj.get("series") or {}
    meta = series.get(market) or {}
    return str(meta.get("source") or "NA"), str(meta.get("source_url") or "NA")


# ----------------- check helpers -----------------
def check_min_rows(series: List[Tuple[str, float]], min_rows: int, label: str = "rows_series") -> Tuple[bool, str]:
    """
    IMPORTANT: This check is for the derived calc-input series (from history.json),
    NOT for latest.json table rows.
    """
    n = len(series)
    if n < min_rows:
        return False, f"{label}<{min_rows} ({label}={n})"
    return True, f"{label}={n}"


def check_base_date_in_series(series: List[Tuple[str, float]], base_date: Optional[str], tag: str) -> Tuple[bool, str]:
    if base_date is None:
        return False, f"{tag}.base_date=NA"
    dates = {d for d, _ in series}
    if base_date not in dates:
        return False, f"{tag}.base_date({base_date}) not found in series dates"
    return True, "OK"


def check_head5_strict_desc_unique(dates_raw: List[Any]) -> Tuple[bool, str]:
    """
    Head5 must satisfy:
      - at least 5 rows (head5 semantics)
      - each of first 5 dates parsable
      - strictly decreasing (newest-first)
      - no duplicates
    """
    head_raw = dates_raw[:5]
    if len(head_raw) < 5:
        return False, f"head5 requires 5 dates, got {len(head_raw)}"

    head: List[date] = []
    for i, x in enumerate(head_raw):
        d = _parse_date_any(x)
        if d is None:
            return False, f"head5[{i}] date parse failed ({x})"
        head.append(d)

    if len(set(head)) != len(head):
        return False, "duplicates in head5"

    for i in range(len(head) - 1):
        if not (head[i] > head[i + 1]):
            return False, f"not strictly decreasing at i={i} ({head[i].isoformat()} !> {head[i+1].isoformat()})"
    return True, "OK"


def head5_pairs(rows: List[Dict[str, Any]]) -> List[Tuple[str, Optional[float]]]:
    out: List[Tuple[str, Optional[float]]] = []
    for r in rows[:5]:
        d_iso = _norm_date_iso(r.get("date"))
        b_raw = r.get("balance_yi", None)
        if b_raw is None:
            b_raw = r.get("balance", None)
        out.append((d_iso if d_iso else "NA", float(b_raw) if isinstance(b_raw, (int, float)) else None))
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
    return _norm_date_iso(ud)


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
    out.sort(key=lambda x: _parse_date_any(x.get("data_date")) or date(1900, 1, 1), reverse=True)
    return out


def maint_head5(hist_items: List[Dict[str, Any]]) -> List[Tuple[str, Optional[float]]]:
    out: List[Tuple[str, Optional[float]]] = []
    for it in hist_items[:5]:
        d_iso = _norm_date_iso(it.get("data_date")) or "NA"
        v = it.get("maint_ratio_pct")
        out.append((d_iso, float(v) if isinstance(v, (int, float)) else None))
    return out


def maint_check_head5_dates_strict(hist_items: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if len(hist_items) < 2:
        return False, f"head5 insufficient (history_rows={len(hist_items)})"
    raw = [it.get("data_date") for it in hist_items[:5]]
    ok, msg = check_head5_strict_desc_unique(raw)
    return (ok, msg)


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
         - Else if hist has >=1 and hist[0] is different date, treat hist[0] as prev (fallback)
    """
    if not isinstance(maint_latest, dict):
        return None, None, "maint_latest missing"
    today = maint_latest.get("maint_ratio_pct")
    today_date_iso = _norm_date_iso(maint_latest.get("data_date"))
    if not isinstance(today, (int, float)):
        return None, None, "maint_latest.maint_ratio_pct missing/non-numeric"

    if not maint_hist_list:
        return None, None, "maint_hist missing/empty"

    def _num(x: Any) -> Optional[float]:
        return float(x) if isinstance(x, (int, float)) else None

    prev: Optional[float] = None
    prev_date_iso: Optional[str] = None

    h0d_iso = _norm_date_iso(maint_hist_list[0].get("data_date"))
    if today_date_iso is not None and h0d_iso == today_date_iso:
        if len(maint_hist_list) >= 2:
            prev = _num(maint_hist_list[1].get("maint_ratio_pct"))
            prev_date_iso = _norm_date_iso(maint_hist_list[1].get("data_date")) or "NA"
            if prev is None:
                return None, None, "maint_hist[1].maint_ratio_pct missing/non-numeric"
        else:
            return None, None, "maint_hist has <2 rows; cannot compute 1D trend"
    else:
        prev = _num(maint_hist_list[0].get("maint_ratio_pct"))
        prev_date_iso = h0d_iso or "NA"
        if prev is None:
            return None, None, "maint_hist[0].maint_ratio_pct missing/non-numeric"

    delta = float(today) - float(prev)
    pct_change = (delta / float(prev) * 100.0) if float(prev) != 0.0 else None

    note = f"trend_from: today={float(today)}({today_date_iso or 'NA'}), prev={float(prev)}({prev_date_iso or 'NA'})"
    return delta, pct_change, note


# ----------------- threshold calibration (percentile policy) -----------------
def _series_index_map(series: List[Tuple[str, float]]) -> Dict[str, int]:
    return {d: i for i, (d, _) in enumerate(series)}


def build_total_series(twse_s: List[Tuple[str, float]], tpex_s: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """
    Build NEWEST-FIRST total series on intersection dates:
      total_balance_yi = twse_balance_yi + tpex_balance_yi
    """
    tw_map = {d: v for d, v in twse_s}
    tp_map = {d: v for d, v in tpex_s}
    common = [d for d in tw_map.keys() if d in tp_map]
    common.sort(key=lambda x: _parse_date_any(x) or date(1900, 1, 1), reverse=True)
    return [(d, float(tw_map[d] + tp_map[d])) for d in common]


def horizon_pct_series_from_balance_series(series: List[Tuple[str, float]], n: int) -> List[float]:
    """
    For each index i where i+n exists, compute pct:
      pct_i = (v_i - v_{i+n}) / v_{i+n} * 100
    """
    out: List[float] = []
    if len(series) < n + 1:
        return out
    for i in range(0, len(series) - n):
        base = series[i + n][1]
        if base == 0:
            continue
        pct = (series[i][1] - base) / base * 100.0
        out.append(float(pct))
    return out


def spread20_series_strict_base_match(
    twse_s: List[Tuple[str, float]],
    tpex_s: List[Tuple[str, float]],
    n: int = 20,
) -> List[float]:
    """
    Compute spread20 per date with STRICT base-date match for the sample:
      spread20(d) = tpex_20d_pct(d) - twse_20d_pct(d)
    """
    out: List[float] = []
    tw_idx = _series_index_map(twse_s)
    tp_idx = _series_index_map(tpex_s)
    common_dates = [d for d in tw_idx.keys() if d in tp_idx]
    common_dates.sort(key=lambda x: _parse_date_any(x) or date(1900, 1, 1), reverse=True)

    for d in common_dates:
        i_tw = tw_idx[d]
        i_tp = tp_idx[d]
        if i_tw + n >= len(twse_s) or i_tp + n >= len(tpex_s):
            continue
        base_tw_d, base_tw_v = twse_s[i_tw + n]
        base_tp_d, base_tp_v = tpex_s[i_tp + n]
        if base_tw_d != base_tp_d:
            continue
        if base_tw_v == 0 or base_tp_v == 0:
            continue
        tw_pct = (twse_s[i_tw][1] - base_tw_v) / base_tw_v * 100.0
        tp_pct = (tpex_s[i_tp][1] - base_tp_v) / base_tp_v * 100.0
        out.append(float(tp_pct - tw_pct))
    return out


def accel_series_from_total(total_series: List[Tuple[str, float]]) -> List[float]:
    """
    accel(d) = total_1d_pct(d) - total_5d_pct(d)/5
    Uses total_series built on intersection dates.
    Need at least 6 rows for a sample.
    """
    out: List[float] = []
    if len(total_series) < 6:
        return out
    for i in range(0, len(total_series) - 5):
        base1 = total_series[i + 1][1]
        base5 = total_series[i + 5][1]
        if base1 == 0 or base5 == 0:
            continue
        pct1 = (total_series[i][1] - base1) / base1 * 100.0
        pct5 = (total_series[i][1] - base5) / base5 * 100.0
        accel = float(pct1) - (float(pct5) / 5.0)
        out.append(accel)
    return out


def calibrate_thresholds(
    policy: str,
    calib_min_n: int,
    pctl_cfg: Dict[str, float],
    twse_s: List[Tuple[str, float]],
    tpex_s: List[Tuple[str, float]],
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Returns:
      thresholds: dict of float thresholds (always filled; uses fallback if needed)
      calib_info: audit info with per-threshold status, sample_n, reason, derived_value
    """
    thresholds = dict(FIXED_THRESHOLDS)
    info: Dict[str, Any] = {
        "policy": policy,
        "calib_min_n": calib_min_n,
        "pctl_cfg": pctl_cfg,
        "fixed_fallback": dict(FIXED_THRESHOLDS),
        "items": {},  # per threshold
    }

    if policy != "percentile":
        info["mode"] = "fixed"
        for k in ("expansion20", "contraction20", "watch1d", "watchspread20", "watchaccel"):
            info["items"][k] = {
                "status": "FIXED",
                "sample_n": None,
                "percentile": None,
                "threshold": thresholds[k],
                "reason": "threshold-policy=fixed",
            }
        return thresholds, info

    total_s = build_total_series(twse_s, tpex_s)

    dist_tot20 = horizon_pct_series_from_balance_series(total_s, 20)
    dist_tot1 = horizon_pct_series_from_balance_series(total_s, 1)
    dist_spread20 = spread20_series_strict_base_match(twse_s, tpex_s, 20)
    dist_accel = accel_series_from_total(total_s)

    def _derive(name: str, dist: List[float], pctl: float) -> Tuple[float, Dict[str, Any]]:
        fallback = FIXED_THRESHOLDS[name]
        if not dist:
            return fallback, {
                "status": "FALLBACK_FIXED",
                "sample_n": 0,
                "percentile": pctl,
                "threshold": fallback,
                "reason": "distribution empty",
            }
        n = len(dist)
        if n < calib_min_n:
            return fallback, {
                "status": "FALLBACK_FIXED",
                "sample_n": n,
                "percentile": pctl,
                "threshold": fallback,
                "reason": f"insufficient samples (n={n} < calib_min_n={calib_min_n})",
            }
        v = percentile_value(dist, pctl)
        if v is None:
            return fallback, {
                "status": "FALLBACK_FIXED",
                "sample_n": n,
                "percentile": pctl,
                "threshold": fallback,
                "reason": "percentile computation failed/invalid p",
            }
        return float(v), {
            "status": "CALIBRATED",
            "sample_n": n,
            "percentile": pctl,
            "threshold": float(v),
            "reason": "OK",
        }

    thr, it = _derive("expansion20", dist_tot20, float(pctl_cfg["expansion20"]))
    thresholds["expansion20"] = thr
    info["items"]["expansion20"] = it

    thr, it = _derive("contraction20", dist_tot20, float(pctl_cfg["contraction20"]))
    thresholds["contraction20"] = thr
    info["items"]["contraction20"] = it

    thr, it = _derive("watch1d", dist_tot1, float(pctl_cfg["watch1d"]))
    thresholds["watch1d"] = thr
    info["items"]["watch1d"] = it

    thr, it = _derive("watchspread20", dist_spread20, float(pctl_cfg["watchspread20"]))
    thresholds["watchspread20"] = thr
    info["items"]["watchspread20"] = it

    thr, it = _derive("watchaccel", dist_accel, float(pctl_cfg["watchaccel"]))
    thresholds["watchaccel"] = thr
    info["items"]["watchaccel"] = it

    info["mode"] = "percentile"
    info["distributions"] = {
        "total_series_rows": len(total_s),
        "dist_total_20d_pct_n": len(dist_tot20),
        "dist_total_1d_pct_n": len(dist_tot1),
        "dist_spread20_n": len(dist_spread20),
        "dist_accel_n": len(dist_accel),
    }
    return thresholds, info


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

    # Threshold calibration args (DEFAULTS = your corrected values)
    ap.add_argument("--threshold-policy", choices=["fixed", "percentile"], default="percentile")
    ap.add_argument("--calib-min-n", type=int, default=60)

    ap.add_argument("--pctl-expansion20", type=float, default=90.0)
    ap.add_argument("--pctl-contraction20", type=float, default=10.0)
    ap.add_argument("--pctl-watch1d", type=float, default=90.0)
    ap.add_argument("--pctl-watchspread20", type=float, default=90.0)
    ap.add_argument("--pctl-watchaccel", type=float, default=90.0)

    # Added: machine-readable output for unified dashboard (no logic change)
    ap.add_argument("--signals-out", default="taiwan_margin_cache/signals_latest.json")

    # OTC guardrail (display-only)
    # Default ON. Backward compatible with --enable-otc-guardrail.
    ap.add_argument("--enable-otc-guardrail", action="store_true", default=None,
                    help="(back-compat) Explicitly enable OTC guardrail (display-only). Default is ON.")
    ap.add_argument("--disable-otc-guardrail", action="store_true", default=None,
                    help="Disable OTC guardrail (display-only).")
    ap.add_argument(
        "--otc-prewatch-gap",
        type=float,
        default=0.2,
        help="PREWATCH if TPEX_20D% >= thr_expansion20 - gap (default 0.2 => 7.8 when thr=8.0)",
    )

    args = ap.parse_args()

    # Guardrail enable logic (tri-state, deterministic)
    # Priority: explicit disable > explicit enable > default ON
    if args.disable_otc_guardrail:
        otc_guardrail_enabled = False
    elif args.enable_otc_guardrail:
        otc_guardrail_enabled = True
    else:
        otc_guardrail_enabled = True  # default ON

    latest = read_json(args.latest)
    hist = read_json(args.history)

    items = hist.get("items", []) if isinstance(hist, dict) else []
    if not isinstance(items, list):
        items = []

    twse_s = build_series_from_history(items, "TWSE")
    tpex_s = build_series_from_history(items, "TPEX")

    twse_rows = extract_latest_rows(latest, "TWSE")
    tpex_rows = extract_latest_rows(latest, "TPEX")

    # Row-count display fix: keep both sources explicitly named.
    twse_rows_latest_table = len(twse_rows)
    tpex_rows_latest_table = len(tpex_rows)
    twse_rows_series = len(twse_s)
    tpex_rows_series = len(tpex_s)

    twse_meta_date = extract_meta_date(latest, "TWSE")
    tpex_meta_date = extract_meta_date(latest, "TPEX")

    twse_src, twse_url = extract_source(latest, "TWSE")
    tpex_src, tpex_url = extract_source(latest, "TPEX")

    def _row_dates_iso(rows: List[Dict[str, Any]], n: int) -> List[str]:
        out: List[str] = []
        for r in rows[:n]:
            d_iso = _norm_date_iso(r.get("date"))
            if d_iso:
                out.append(d_iso)
        return out

    def _row_dates_iso_tail(rows: List[Dict[str, Any]], n: int) -> List[str]:
        out: List[str] = []
        for r in rows[-n:]:
            d_iso = _norm_date_iso(r.get("date"))
            if d_iso:
                out.append(d_iso)
        return out

    twse_head_dates = _row_dates_iso(twse_rows, 3)
    twse_tail_dates = _row_dates_iso_tail(twse_rows, 3)
    tpex_head_dates = _row_dates_iso(tpex_rows, 3)
    tpex_tail_dates = _row_dates_iso_tail(tpex_rows, 3)

    # Compute current horizons (latest point only)
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

    # -------- threshold calibration (percentile / fixed) --------
    pctl_cfg = {
        "expansion20": float(args.pctl_expansion20),
        "contraction20": float(args.pctl_contraction20),
        "watch1d": float(args.pctl_watch1d),
        "watchspread20": float(args.pctl_watchspread20),
        "watchaccel": float(args.pctl_watchaccel),
    }
    thresholds, calib_info = calibrate_thresholds(
        policy=str(args.threshold_policy),
        calib_min_n=int(args.calib_min_n),
        pctl_cfg=pctl_cfg,
        twse_s=twse_s,
        tpex_s=tpex_s,
    )

    # Determine state/signal using calibrated thresholds (TOTAL-only as before)
    state_label, margin_signal, rationale = determine_signal(
        tot20_pct=tot20.get("pct"),
        tot1_pct=tot1.get("pct"),
        tot5_pct=tot5.get("pct"),
        accel=accel,
        spread20=spread20,
        thresholds=thresholds,
    )

    # ---------- OTC Guardrail (display-only; does not affect margin_signal) ----------
    otc_guardrail: Optional[Dict[str, Any]] = None
    if otc_guardrail_enabled:
        otc_guardrail = compute_otc_guardrail(
            tp20_pct=tp20.get("pct"),
            tp1_pct=tp1.get("pct"),
            tp5_pct=tp5.get("pct"),
            thr_expansion20=float(thresholds["expansion20"]),
            prewatch_gap=float(args.otc_prewatch_gap),
        )

    # ---------- Margin data quality checks (these determine margin_quality) ----------
    c1_tw_ok = (twse_meta_date is not None) and (latest_date_from_series(twse_s) is not None) and (twse_meta_date == latest_date_from_series(twse_s))
    c1_tp_ok = (tpex_meta_date is not None) and (latest_date_from_series(tpex_s) is not None) and (tpex_meta_date == latest_date_from_series(tpex_s))

    twse_dates_from_rows_raw = [r.get("date") for r in twse_rows[:5]]
    tpex_dates_from_rows_raw = [r.get("date") for r in tpex_rows[:5]]
    c2_tw_ok, c2_tw_msg = check_head5_strict_desc_unique(twse_dates_from_rows_raw)
    c2_tp_ok, c2_tp_msg = check_head5_strict_desc_unique(tpex_dates_from_rows_raw)

    if len(twse_rows) >= 5 and len(tpex_rows) >= 5:
        c3_ok = (head5_pairs(twse_rows) != head5_pairs(tpex_rows))
        c3_msg = "OK" if c3_ok else "head5 identical (date+balance) => likely wrong page"
    else:
        c3_ok, c3_msg = False, "insufficient rows for head5 comparison"

    c4_tw_ok, c4_tw_msg = check_min_rows(twse_s, 21, label="rows_series")
    c4_tp_ok, c4_tp_msg = check_min_rows(tpex_s, 21, label="rows_series")

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
        ld = _norm_date_iso(_get(maint_latest, "data_date", None))
        hd = _norm_date_iso(maint_hist_list[0].get("data_date"))
        if ld and hd and ld == hd:
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

    # threshold policy summary (audit)
    md.append(f"- threshold_policy: {args.threshold_policy}｜calib_min_n={args.calib_min_n}")
    md.append(
        "  - percentiles: "
        f"expansion20={args.pctl_expansion20}, "
        f"contraction20={args.pctl_contraction20}, "
        f"watch1d={args.pctl_watch1d}, "
        f"watchspread20={args.pctl_watchspread20}, "
        f"watchaccel={args.pctl_watchaccel}"
    )
    md.append(
        "  - thresholds_used: "
        f"expansion20={fmt_pct(thresholds['expansion20'],4)}, "
        f"contraction20={fmt_pct(thresholds['contraction20'],4)}, "
        f"watch1d={fmt_pct(thresholds['watch1d'],4)}, "
        f"watchspread20={fmt_pct(thresholds['watchspread20'],4)}, "
        f"watchaccel={fmt_pct(thresholds['watchaccel'],4)}"
    )
    # per-threshold calibration status (compact)
    if isinstance(calib_info, dict) and isinstance(calib_info.get("items"), dict):
        items_info = calib_info["items"]
        md.append("  - calibration_status:")
        for k in ("expansion20", "contraction20", "watch1d", "watchspread20", "watchaccel"):
            it = items_info.get(k, {})
            md.append(
                f"    - {k}: status={it.get('status','NA')}, "
                f"sample_n={it.get('sample_n','NA')}, "
                f"threshold={it.get('threshold','NA')}, "
                f"reason={it.get('reason','NA')}"
            )

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

    # OTC Guardrail summary line (display-only; does not alter margin_signal)
    if otc_guardrail_enabled:
        md.append(f"- OTC_guardrail（display-only; 不影響主信號）：{_get(otc_guardrail or {}, 'label', 'NA')}｜stage={_get(otc_guardrail or {}, 'prewatch_stage', 'NA')}")
        md.append(f"  - rationale: {_get(otc_guardrail or {}, 'rationale', 'NA')}")
        md.append(
            f"  - thresholds: thr_expansion20={fmt_pct(float(thresholds['expansion20']),4)}, "
            f"prewatch_gap={fmt_pct(float(args.otc_prewatch_gap),4)}, "
            f"prewatch_threshold={fmt_pct(float(_get(otc_guardrail or {}, 'prewatch_threshold', float(thresholds['expansion20'])-float(args.otc_prewatch_gap))),4)}"
        )
    md.append("")

    md.append("## 1.1) 判定標準（本 dashboard 內建規則）")
    md.append("### 0) 門檻來源")
    md.append(f"- threshold_policy={args.threshold_policy}（percentile 若樣本不足會自動 fallback 到 fixed，並在上方 calibration_status 註明）")
    md.append(f"- fixed_baseline: expansion20={FIXED_THRESHOLDS['expansion20']}, contraction20={FIXED_THRESHOLDS['contraction20']}, watch1d={FIXED_THRESHOLDS['watch1d']}, watchspread20={FIXED_THRESHOLDS['watchspread20']}, watchaccel={FIXED_THRESHOLDS['watchaccel']}")
    md.append(f"- thresholds_used: expansion20={fmt_pct(thresholds['expansion20'],4)}, contraction20={fmt_pct(thresholds['contraction20'],4)}, watch1d={fmt_pct(thresholds['watch1d'],4)}, watchspread20={fmt_pct(thresholds['watchspread20'],4)}, watchaccel={fmt_pct(thresholds['watchaccel'],4)}")
    md.append("")

    md.append("### 1) WATCH（升溫）")
    md.append("- 條件：20D% ≥ thr_expansion20 且 (1D% ≥ thr_watch1d 或 Spread20 ≥ thr_watchspread20 或 Accel ≥ thr_watchaccel)")
    md.append("")
    md.append("### 2) ALERT（疑似去槓桿）")
    md.append("- 條件：20D% ≥ thr_expansion20 且 1D% < 0 且 5D% < 0")
    md.append("")
    md.append("### 3) 解除 WATCH（降溫）")
    md.append("- 條件：20D% 仍高，但 Accel ≤ 0 且 1D% 回到 < 0.3（需連 2–3 次確認；此段仍採固定 0.3）")
    md.append("")

    if otc_guardrail_enabled:
        md.append("### 4) OTC Guardrail（display-only；不影響主信號）")
        md.append(f"- PREWATCH：TPEX_20D% ≥ (thr_expansion20 - gap)；gap={fmt_pct(float(args.otc_prewatch_gap),4)}")
        md.append("- OTC_ALERT：TPEX_20D% ≥ thr_expansion20 且 TPEX_1D% < 0 且 TPEX_5D% < 0")
        md.append("- 目的：避免僅看合計（TOTAL-only）時，OTC 端先升溫/轉弱被稀釋而晚報。")
        md.append("")

    md.append("## 2) 資料")
    md.append(
        f"- 上市(TWSE)：融資餘額 {fmt_num(latest_balance_from_series(twse_s),2)} 億元｜資料日期 {twse_meta_date or 'NA'}｜來源：{twse_src}（{twse_url}）"
    )
    md.append(
        f"  - rows_latest_table={twse_rows_latest_table}｜rows_series={twse_rows_series}｜head_dates={twse_head_dates}｜tail_dates={twse_tail_dates}"
    )
    md.append(
        f"- 上櫃(TPEX)：融資餘額 {fmt_num(latest_balance_from_series(tpex_s),2)} 億元｜資料日期 {tpex_meta_date or 'NA'}｜來源：{tpex_src}（{tpex_url}）"
    )
    md.append(
        f"  - rows_latest_table={tpex_rows_latest_table}｜rows_series={tpex_rows_series}｜head_dates={tpex_head_dates}｜tail_dates={tpex_tail_dates}"
    )

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
    md.append(f"- maint_ratio_policy: PROXY_TREND_ONLY")
    md.append(f"- maint_ratio_confidence: DOWNGRADED")

    if maint_ok and maint_latest is not None:
        md.append(f"- data_date: {_norm_date_iso(_get(maint_latest,'data_date','NA')) or 'NA'}｜maint_ratio_pct: {_get(maint_latest,'maint_ratio_pct','NA')}")
        md.append(
            f"- maint_ratio_1d_delta_pctpt: {fmt_num(maint_ratio_1d_delta_pctpt, 6)}"
            f"｜maint_ratio_1d_pct_change: {fmt_num(maint_ratio_1d_pct_change, 6)}"
        )
        if maint_ratio_trend_note:
            md.append(f"- maint_ratio_trend_note: {maint_ratio_trend_note}")
    else:
        md.append(f"- maint_error: {maint_err or 'maint missing'}")

    md.append("")
    md.append("## 2.1) 台股成交量/波動（roll25_cache；confirm-only）")
    md.append(f"- roll25_path: {args.roll25}")
    if roll_ok and roll is not None:
        md.append(
            f"- UsedDate: {roll_used or 'NA'}｜UsedDateStatus: {roll_used_status or 'NA'}｜"
            f"risk_level: {roll_risk_level_disp}｜risk_level_raw: {roll_risk_level_raw}｜tag: {_get(roll,'tag','NA')}"
        )
        md.append(f"- summary: {_get(roll,'summary','NA')}")
        md.append(f"- resonance_confidence: {resonance_confidence}")
    else:
        md.append(f"- roll25_error: {roll_err or 'roll25 missing'}")
        md.append(f"- resonance_confidence: {resonance_confidence}")
    md.append("")

    md.append("## 2.2) 一致性判定（Margin × Roll25 共振）")
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
    md.append("### 上櫃(TPEX)")
    md.append(
        f"- 1D：Δ={fmt_num(tp1['delta'],2)} 億元；Δ%={fmt_pct(tp1['pct'],4)} %｜latest={fmt_num(tp1['latest'],2)}｜base={fmt_num(tp1['base'],2)}（基期日={tp1['base_date'] or 'NA'}）"
    )
    md.append("")

    if otc_guardrail_enabled:
        md.append("## 3.1) OTC Guardrail（display-only；不影響主信號）")
        md.append(f"- stage: {_get(otc_guardrail or {}, 'prewatch_stage', 'NA')}｜label: {_get(otc_guardrail or {}, 'label', 'NA')}")
        md.append(f"- rationale: {_get(otc_guardrail or {}, 'rationale', 'NA')}")
        md.append(
            f"- inputs: TPEX_20D%={fmt_pct(tp20.get('pct'),4)}｜TPEX_1D%={fmt_pct(tp1.get('pct'),4)}｜TPEX_5D%={fmt_pct(tp5.get('pct'),4)}"
        )
        md.append(
            f"- thresholds: thr_expansion20={fmt_pct(float(thresholds['expansion20']),4)}｜prewatch_threshold={fmt_pct(float(_get(otc_guardrail or {}, 'prewatch_threshold', float(thresholds['expansion20'])-float(args.otc_prewatch_gap))),4)}"
        )
        md.append("")

    md.append("## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint/guardrail 僅供對照）")
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
    md.append(line_check("Check-10 maint latest vs history[0] date（info）", c10_status, c10_msg))
    md.append(line_check("Check-11 maint history head5 dates 嚴格遞減且無重複（info）", c11_status, c11_msg))

    if otc_guardrail_enabled:
        md.append(line_check(
            "Check-12 OTC Guardrail（info-only）",
            "NOTE",
            f"stage={_get(otc_guardrail or {}, 'prewatch_stage', 'NA')}, label={_get(otc_guardrail or {}, 'label', 'NA')}, "
            f"prewatch_hit={_get(otc_guardrail or {}, 'prewatch_hit', 'NA')}, otc_alert_hit={_get(otc_guardrail or {}, 'otc_alert_hit', 'NA')}"
        ))

    md.append("")
    generated_at_utc = latest.get("generated_at_utc", None) if isinstance(latest, dict) else None
    if not generated_at_utc:
        generated_at_utc = now_utc_iso()
    md.append(f"_generated_at_utc: {generated_at_utc}_")
    md.append("")

    # write markdown
    out_parent = os.path.dirname(args.out)
    if out_parent:
        os.makedirs(out_parent, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # ---------- emit signals_latest.json ----------
    roll_is_heated: Optional[bool] = None
    if roll_ok and roll is not None:
        roll_is_heated = roll25_is_heated(roll)

    signals: Dict[str, Any] = {
        "schema_version": "tw_margin_signals_latest_v1",
        "module": "taiwan_margin_financing",
        "generated_at_utc": generated_at_utc,
        "generated_at_local": latest.get("generated_at_local", None) if isinstance(latest, dict) else None,
        "data_date": twse_meta_date,
        "state": state_label,
        "signal": margin_signal,
        "margin_quality": margin_quality,
        "rationale": rationale,
        "resonance": resonance_label,
        "resonance_display": resonance_na(resonance_label, resonance_code),
        "resonance_confidence": resonance_confidence,
        "resonance_code": resonance_code,
        "resonance_note": resonance_note,
        "thresholds": {
            "policy": args.threshold_policy,
            "calib_min_n": args.calib_min_n,
            "percentiles": {
                "expansion20": args.pctl_expansion20,
                "contraction20": args.pctl_contraction20,
                "watch1d": args.pctl_watch1d,
                "watchspread20": args.pctl_watchspread20,
                "watchaccel": args.pctl_watchaccel,
            },
            "fixed_baseline": dict(FIXED_THRESHOLDS),
            "used": dict(thresholds),
            "calibration": calib_info,
        },
        "margin": {
            "twse_meta_date": twse_meta_date,
            "tpex_meta_date": tpex_meta_date,
            "twse": {
                "latest_balance_yi": latest_balance_from_series(twse_s),
                "h1": tw1,
                "h5": tw5,
                "h20": tw20,
                "source": {"vendor": twse_src, "source_url": twse_url},
                "rows_series": twse_rows_series,
                "rows_latest_table": twse_rows_latest_table,
            },
            "tpex": {
                "latest_balance_yi": latest_balance_from_series(tpex_s),
                "h1": tp1,
                "h5": tp5,
                "h20": tp20,
                "source": {"vendor": tpex_src, "source_url": tpex_url},
                "rows_series": tpex_rows_series,
                "rows_latest_table": tpex_rows_latest_table,
            },
            "total": {"h1": tot1, "h5": tot5, "h20": tot20},
            "derived": {"accel": accel, "spread20": spread20},
        },
        "roll25": {
            "path": args.roll25,
            "ok": roll_ok,
            "error": roll_err,
            "used_date": roll_used,
            "used_date_status": roll_used_status,
            "risk_level_display": roll_risk_level_disp,
            "risk_level_raw": roll_risk_level_raw,
            "tag": _get(roll, "tag", None) if (roll_ok and roll is not None) else None,
            "is_heated": roll_is_heated,
            "lookback_note": roll25_window_note,
            "strict_same_day": strict_same_day,
            "strict_not_stale": strict_not_stale,
            "strict_roll_match": strict_roll_match,
        },
        "maint_ratio": {
            "policy": "PROXY_TREND_ONLY",
            "confidence": "DOWNGRADED",
            "path_latest": args.maint,
            "path_history": args.maint_hist,
            "ok_latest": maint_ok,
            "ok_history": maint_hist_ok,
            "latest": {
                "data_date": _norm_date_iso(_get(maint_latest, "data_date", None)) if maint_ok and maint_latest else None,
                "maint_ratio_pct": _get(maint_latest, "maint_ratio_pct", None) if maint_ok and maint_latest else None,
                "maint_ratio_1d_delta_pctpt": maint_ratio_1d_delta_pctpt,
                "maint_ratio_1d_pct_change": maint_ratio_1d_pct_change,
                "trend_note": maint_ratio_trend_note,
            },
            "history": {"rows": len(maint_hist_list), "head5": maint_head},
        },
        "otc_guardrail": {
            "enabled": bool(otc_guardrail_enabled),
            "policy": "DISPLAY_ONLY",
            "prewatch_gap": float(args.otc_prewatch_gap),
            "thr_expansion20_used": float(thresholds["expansion20"]),
            "result": otc_guardrail,
        },
        "inputs": {
            "latest_path": args.latest,
            "history_path": args.history,
            "out_md_path": args.out,
            "signals_out_path": args.signals_out,
            "resonance_policy": args.resonance_policy,
            "threshold_policy": args.threshold_policy,
            "calib_min_n": args.calib_min_n,
            "pctl_cfg": pctl_cfg,
            "otc_guardrail": {
                "enabled": bool(otc_guardrail_enabled),
                "disable_flag": bool(args.disable_otc_guardrail) if args.disable_otc_guardrail is not None else False,
                "enable_flag": bool(args.enable_otc_guardrail) if args.enable_otc_guardrail is not None else False,
                "otc_prewatch_gap": float(args.otc_prewatch_gap),
            },
        },
    }

    write_json(args.signals_out, signals)


if __name__ == "__main__":
    main()