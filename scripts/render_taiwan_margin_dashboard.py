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

Added: Threshold calibration (AUDIT-SAFE)
- Support --threshold-policy {fixed,percentile}
- When percentile policy enabled: derive thresholds from history.json distributions via target percentiles
- If insufficient samples or percentile not provided -> fallback to fixed threshold (explicitly marked)
- Calibration uses ONLY internal derived metrics (tot20_pct, tot1_pct, spread20, accel) from aligned TWSE/TPEX dates

Added (NO LOGIC CHANGE):
- Also emit a machine-readable signals_latest.json for unified dashboard ingestion.
  Default output: taiwan_margin_cache/signals_latest.json
  Use --signals-out to override.

Row-count display fix (NO LOGIC CHANGE):
- Avoid ambiguous "rows=" which mixed two different sources:
  - rows_latest_table: from latest.json series.{market}.rows (page/table rows; often ~30)
  - rows_series: from history.json derived balance series (calc input; often >30)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


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
    # PASS/FAIL with details
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


# ----------------- percentile / quantile (audit-safe; deterministic) -----------------
def _is_finite_number(x: Any) -> bool:
    if not isinstance(x, (int, float)):
        return False
    xf = float(x)
    # NaN check
    return xf == xf


def _quantile_linear(values_sorted: List[float], q: float) -> Optional[float]:
    """
    Deterministic linear-interpolated quantile.
    q in [0, 1].
    """
    if not values_sorted:
        return None
    if q <= 0:
        return float(values_sorted[0])
    if q >= 1:
        return float(values_sorted[-1])

    n = len(values_sorted)
    pos = q * (n - 1)
    lo = int(pos)
    hi = lo + 1
    if hi >= n:
        return float(values_sorted[-1])

    frac = pos - lo
    v0 = float(values_sorted[lo])
    v1 = float(values_sorted[hi])
    return v0 + (v1 - v0) * frac


def _dist_summary(values: List[float]) -> Dict[str, Any]:
    vs = [float(v) for v in values if _is_finite_number(v)]
    vs.sort()
    if not vs:
        return {"n": 0, "min": None, "p10": None, "p50": None, "p90": None, "max": None}
    return {
        "n": len(vs),
        "min": float(vs[0]),
        "p10": _quantile_linear(vs, 0.10),
        "p50": _quantile_linear(vs, 0.50),
        "p90": _quantile_linear(vs, 0.90),
        "max": float(vs[-1]),
    }


def _calibrate_threshold(
    *,
    name: str,
    values: List[float],
    target_pct: Optional[float],
    fixed_value: float,
    min_n: int,
) -> Tuple[float, Dict[str, Any]]:
    """
    Returns:
      - used_threshold (float): derived if possible, else fixed_value
      - meta: audit details
    """
    meta: Dict[str, Any] = {
        "name": name,
        "policy": "percentile",
        "target_pct": target_pct,
        "min_n": min_n,
        "fixed_value": fixed_value,
        "used_value": fixed_value,
        "status": "FALLBACK_FIXED",
        "reason": "",
        "dist": _dist_summary(values),
        "derived_value": None,
    }

    if target_pct is None:
        meta["reason"] = "target_pct not provided"
        return fixed_value, meta

    try:
        tp = float(target_pct)
    except Exception:
        meta["reason"] = f"target_pct not numeric ({target_pct})"
        return fixed_value, meta

    if not (0.0 <= tp <= 100.0):
        meta["reason"] = f"target_pct out of range [0,100] ({tp})"
        return fixed_value, meta

    vals = [float(v) for v in values if _is_finite_number(v)]
    vals.sort()
    if len(vals) < int(min_n):
        meta["reason"] = f"insufficient samples (n={len(vals)} < min_n={min_n})"
        return fixed_value, meta

    q = tp / 100.0
    dv = _quantile_linear(vals, q)
    if dv is None:
        meta["reason"] = "quantile computation returned None"
        return fixed_value, meta

    meta["derived_value"] = float(dv)
    meta["used_value"] = float(dv)
    meta["status"] = "CALIBRATED"
    meta["reason"] = "OK"
    return float(dv), meta


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

    # sort by parsed date (not string), newest-first
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
    th: Dict[str, float],
) -> Tuple[str, str, str]:
    """
    th keys (all float):
      - exp20, contr20
      - watch1d, watch_spread20, watch_accel
      - cool_accel, cool_1d
    """
    exp20 = float(th["exp20"])
    contr20 = float(th["contr20"])
    watch1d = float(th["watch1d"])
    watch_spread20 = float(th["watch_spread20"])
    watch_accel = float(th["watch_accel"])
    cool_accel = float(th["cool_accel"])
    cool_1d = float(th["cool_1d"])

    if tot20_pct is None:
        return ("NA", "NA", "insufficient total_20D% (NA)")

    state = "擴張" if tot20_pct >= exp20 else ("收縮" if tot20_pct <= contr20 else "中性")

    if (tot20_pct >= exp20) and (tot1_pct is not None) and (tot5_pct is not None) and (tot1_pct < 0.0) and (tot5_pct < 0.0):
        return (state, "ALERT", "20D expansion + 1D%<0 and 5D%<0 (possible deleveraging)")

    watch = False
    if tot20_pct >= exp20:
        if (tot1_pct is not None and tot1_pct >= watch1d):
            watch = True
        if (spread20 is not None and spread20 >= watch_spread20):
            watch = True
        if (accel is not None and accel >= watch_accel):
            watch = True

    if watch:
        return (state, "WATCH", "20D expansion + (1D%>=TH OR Spread20>=TH OR Accel>=TH)")

    if (tot20_pct >= exp20) and (accel is not None) and (tot1_pct is not None):
        if (accel <= cool_accel) and (tot1_pct < cool_1d):
            return (state, "INFO", "cool-down candidate: Accel<=TH and 1D%<TH (needs 2–3 consecutive confirmations)")

    return (state, "NONE", "no rule triggered")


# ----------------- threshold calibration inputs from aligned series -----------------
def _build_aligned_series(
    twse_s: List[Tuple[str, float]],
    tpex_s: List[Tuple[str, float]],
) -> List[Tuple[str, float, float, float]]:
    """
    Align by date intersection to keep strict comparability.
    Returns NEWEST-FIRST: [(date_iso, twse_balance, tpex_balance, total_balance), ...]
    """
    tw = {d: v for d, v in twse_s}
    tp = {d: v for d, v in tpex_s}
    common = sorted(set(tw.keys()) & set(tp.keys()), key=lambda x: _parse_date_any(x) or date(1900, 1, 1), reverse=True)
    out: List[Tuple[str, float, float, float]] = []
    for d in common:
        tv = float(tw[d])
        pv = float(tp[d])
        out.append((d, tv, pv, tv + pv))
    return out


def _pct_change(latest: float, base: float) -> Optional[float]:
    if base == 0:
        return None
    return (latest - base) / base * 100.0


def _derive_metric_samples(
    aligned: List[Tuple[str, float, float, float]],
) -> Dict[str, Any]:
    """
    Build sample arrays for calibration using aligned series (date intersection).
    Produces list of (asof_date, value) for each metric.
    """
    samples: Dict[str, List[Tuple[str, float]]] = {
        "tot1_pct": [],
        "tot5_pct": [],
        "tot20_pct": [],
        "accel": [],
        "spread20": [],
    }

    n = len(aligned)
    for i in range(n):
        d_i, tw_i, tp_i, tot_i = aligned[i]

        # tot1/tot5/tot20
        tot1: Optional[float] = None
        tot5: Optional[float] = None
        tot20: Optional[float] = None

        if i + 1 < n:
            _, _, _, tot_b = aligned[i + 1]
            tot1 = _pct_change(tot_i, tot_b)
            if tot1 is not None:
                samples["tot1_pct"].append((d_i, float(tot1)))

        if i + 5 < n:
            _, _, _, tot_b = aligned[i + 5]
            tot5 = _pct_change(tot_i, tot_b)
            if tot5 is not None:
                samples["tot5_pct"].append((d_i, float(tot5)))

        if i + 20 < n:
            _, _, _, tot_b = aligned[i + 20]
            tot20 = _pct_change(tot_i, tot_b)
            if tot20 is not None:
                samples["tot20_pct"].append((d_i, float(tot20)))

            # spread20 requires twse_20 and tpex_20 at same offsets (aligned guarantees base-date alignment)
            _, tw_b, tp_b, _ = aligned[i + 20]
            tw20 = _pct_change(tw_i, tw_b)
            tp20 = _pct_change(tp_i, tp_b)
            if (tw20 is not None) and (tp20 is not None):
                samples["spread20"].append((d_i, float(tp20 - tw20)))

        # accel uses tot1 and tot5 when both exist for this i
        if (tot1 is not None) and (tot5 is not None):
            samples["accel"].append((d_i, float(tot1 - (tot5 / 5.0))))

    def _pack(name: str) -> Dict[str, Any]:
        arr = samples[name]
        vals = [v for _, v in arr if _is_finite_number(v)]
        newest = arr[0][0] if arr else None
        oldest = arr[-1][0] if arr else None
        return {
            "n": len(vals),
            "newest_date": newest,
            "oldest_date": oldest,
            "values": vals,  # for calibration use only (not for markdown dumping)
            "dist": _dist_summary(vals),
        }

    return {
        "aligned_rows": len(aligned),
        "aligned_newest_date": aligned[0][0] if aligned else None,
        "aligned_oldest_date": aligned[-1][0] if aligned else None,
        "tot1_pct": _pack("tot1_pct"),
        "tot5_pct": _pack("tot5_pct"),
        "tot20_pct": _pack("tot20_pct"),
        "accel": _pack("accel"),
        "spread20": _pack("spread20"),
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
      - at least 2 rows
      - each of first 5 dates parsable
      - strictly decreasing (newest-first)
      - no duplicates
    """
    head_raw = dates_raw[:5]
    if len(head_raw) < 2:
        return False, "head5 insufficient"

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
        # tolerate alternative balance field names (still deterministic; no guessing)
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
         - Else if hist has >=1 and hist[0] is different date, treat hist[0] as prev (best-effort)
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

    # Added: machine-readable output for unified dashboard (no logic change)
    ap.add_argument("--signals-out", default="taiwan_margin_cache/signals_latest.json")

    # Added: threshold calibration (audit-safe; optional)
    ap.add_argument("--threshold-policy", choices=["fixed", "percentile"], default="fixed")
    ap.add_argument("--calib-min-n", type=int, default=60)

    ap.add_argument("--pctl-expansion20", type=float, default=None)    # tot20_pct >= TH
    ap.add_argument("--pctl-contraction20", type=float, default=None)  # tot20_pct <= TH

    ap.add_argument("--pctl-watch1d", type=float, default=None)        # tot1_pct >= TH
    ap.add_argument("--pctl-watchspread20", type=float, default=None)  # spread20 >= TH
    ap.add_argument("--pctl-watchaccel", type=float, default=None)     # accel >= TH

    ap.add_argument("--pctl-cool1d", type=float, default=None)         # tot1_pct < TH (cool-down)
    ap.add_argument("--pctl-coolaccel", type=float, default=None)      # accel <= TH (cool-down)

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

    # ---------- Thresholds (fixed defaults) ----------
    fixed_th: Dict[str, float] = {
        "exp20": 8.0,
        "contr20": -8.0,
        "watch1d": 0.8,
        "watch_spread20": 3.0,
        "watch_accel": 0.25,
        "cool_accel": 0.0,
        "cool_1d": 0.3,
    }

    # ---------- Threshold calibration (optional; percentile -> threshold) ----------
    threshold_policy = str(args.threshold_policy)
    calib_min_n = int(args.calib_min_n) if int(args.calib_min_n) > 0 else 60

    aligned = _build_aligned_series(twse_s, tpex_s)
    calib_samples = _derive_metric_samples(aligned) if aligned else {
        "aligned_rows": 0,
        "aligned_newest_date": None,
        "aligned_oldest_date": None,
        "tot1_pct": {"n": 0, "newest_date": None, "oldest_date": None, "values": [], "dist": _dist_summary([])},
        "tot5_pct": {"n": 0, "newest_date": None, "oldest_date": None, "values": [], "dist": _dist_summary([])},
        "tot20_pct": {"n": 0, "newest_date": None, "oldest_date": None, "values": [], "dist": _dist_summary([])},
        "accel": {"n": 0, "newest_date": None, "oldest_date": None, "values": [], "dist": _dist_summary([])},
        "spread20": {"n": 0, "newest_date": None, "oldest_date": None, "values": [], "dist": _dist_summary([])},
    }

    calib_meta: Dict[str, Any] = {
        "policy": threshold_policy,
        "calib_min_n": calib_min_n,
        "aligned_rows": calib_samples.get("aligned_rows"),
        "aligned_newest_date": calib_samples.get("aligned_newest_date"),
        "aligned_oldest_date": calib_samples.get("aligned_oldest_date"),
        "targets": {
            "pctl_expansion20": args.pctl_expansion20,
            "pctl_contraction20": args.pctl_contraction20,
            "pctl_watch1d": args.pctl_watch1d,
            "pctl_watchspread20": args.pctl_watchspread20,
            "pctl_watchaccel": args.pctl_watchaccel,
            "pctl_cool1d": args.pctl_cool1d,
            "pctl_coolaccel": args.pctl_coolaccel,
        },
        "per_threshold": {},
        "samples": {
            "tot20_pct": {k: calib_samples["tot20_pct"].get(k) for k in ("n", "newest_date", "oldest_date", "dist")},
            "tot1_pct": {k: calib_samples["tot1_pct"].get(k) for k in ("n", "newest_date", "oldest_date", "dist")},
            "spread20": {k: calib_samples["spread20"].get(k) for k in ("n", "newest_date", "oldest_date", "dist")},
            "accel": {k: calib_samples["accel"].get(k) for k in ("n", "newest_date", "oldest_date", "dist")},
        },
    }

    used_th = dict(fixed_th)
    if threshold_policy == "percentile":
        # tot20 expansion / contraction thresholds
        v_tot20 = calib_samples["tot20_pct"].get("values", [])
        used_th["exp20"], m1 = _calibrate_threshold(
            name="exp20",
            values=v_tot20,
            target_pct=args.pctl_expansion20,
            fixed_value=fixed_th["exp20"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["exp20"] = m1

        used_th["contr20"], m2 = _calibrate_threshold(
            name="contr20",
            values=v_tot20,
            target_pct=args.pctl_contraction20,
            fixed_value=fixed_th["contr20"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["contr20"] = m2

        # watch thresholds
        used_th["watch1d"], m3 = _calibrate_threshold(
            name="watch1d",
            values=calib_samples["tot1_pct"].get("values", []),
            target_pct=args.pctl_watch1d,
            fixed_value=fixed_th["watch1d"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["watch1d"] = m3

        used_th["watch_spread20"], m4 = _calibrate_threshold(
            name="watch_spread20",
            values=calib_samples["spread20"].get("values", []),
            target_pct=args.pctl_watchspread20,
            fixed_value=fixed_th["watch_spread20"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["watch_spread20"] = m4

        used_th["watch_accel"], m5 = _calibrate_threshold(
            name="watch_accel",
            values=calib_samples["accel"].get("values", []),
            target_pct=args.pctl_watchaccel,
            fixed_value=fixed_th["watch_accel"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["watch_accel"] = m5

        # cool-down thresholds (optional)
        used_th["cool_1d"], m6 = _calibrate_threshold(
            name="cool_1d",
            values=calib_samples["tot1_pct"].get("values", []),
            target_pct=args.pctl_cool1d,
            fixed_value=fixed_th["cool_1d"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["cool_1d"] = m6

        used_th["cool_accel"], m7 = _calibrate_threshold(
            name="cool_accel",
            values=calib_samples["accel"].get("values", []),
            target_pct=args.pctl_coolaccel,
            fixed_value=fixed_th["cool_accel"],
            min_n=calib_min_n,
        )
        calib_meta["per_threshold"]["cool_accel"] = m7
    else:
        # fixed policy: explicitly record
        calib_meta["per_threshold"] = {
            k: {
                "name": k,
                "policy": "fixed",
                "fixed_value": fixed_th[k],
                "used_value": fixed_th[k],
                "status": "FIXED_POLICY",
                "reason": "policy=fixed",
            }
            for k in fixed_th.keys()
        }

    # ---------- Determine signal using used thresholds ----------
    state_label, margin_signal, rationale = determine_signal(
        tot20_pct=tot20.get("pct"),
        tot1_pct=tot1.get("pct"),
        tot5_pct=tot5.get("pct"),
        accel=accel,
        spread20=spread20,
        th=used_th,
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

    md.append("## 1.1) 判定標準（本 dashboard 內建規則；顯示『實際採用門檻』）")
    md.append(f"- threshold_policy: {threshold_policy}")
    md.append(
        "- thresholds_used: "
        f"exp20={fmt_num(used_th['exp20'],4)}, "
        f"contr20={fmt_num(used_th['contr20'],4)}, "
        f"watch1d={fmt_num(used_th['watch1d'],4)}, "
        f"watch_spread20={fmt_num(used_th['watch_spread20'],4)}, "
        f"watch_accel={fmt_num(used_th['watch_accel'],4)}, "
        f"cool_accel={fmt_num(used_th['cool_accel'],4)}, "
        f"cool_1d={fmt_num(used_th['cool_1d'],4)}"
    )
    md.append("")
    md.append("### 1) WATCH（升溫）")
    md.append(
        f"- 條件：20D% ≥ {fmt_num(used_th['exp20'],4)} 且 "
        f"(1D% ≥ {fmt_num(used_th['watch1d'],4)} 或 "
        f"Spread20 ≥ {fmt_num(used_th['watch_spread20'],4)} 或 "
        f"Accel ≥ {fmt_num(used_th['watch_accel'],4)})"
    )
    md.append("- 行動：把你其他風險模組（VIX / 信用 / 成交量）一起對照，確認是不是同向升溫。")
    md.append("")
    md.append("### 2) ALERT（疑似去槓桿）")
    md.append(f"- 條件：20D% ≥ {fmt_num(used_th['exp20'],4)} 且 1D% < 0 且 5D% < 0")
    md.append("- 行動：優先看『是否出現連續負值』，因為可能開始踩踏。")
    md.append("")
    md.append("### 3) 解除 WATCH（降溫）")
    md.append(
        f"- 條件：20D% 仍高（≥ {fmt_num(used_th['exp20'],4)}），但 "
        f"Accel ≤ {fmt_num(used_th['cool_accel'],4)} 且 1D% < {fmt_num(used_th['cool_1d'],4)}（需連 2–3 次確認）"
    )
    md.append("- 行動：代表短線槓桿加速結束，回到『擴張但不加速』。")
    md.append("")

    md.append("## 1.2) 門檻校準（目標百分位 → 反推門檻值；資料不足則明確回退固定門檻）")
    md.append(f"- threshold_policy: {threshold_policy}")
    md.append(f"- calib_min_n: {calib_min_n}")
    md.append(
        f"- aligned_date_intersection_rows: {calib_meta.get('aligned_rows','NA')} "
        f"({calib_meta.get('aligned_newest_date','NA')} .. {calib_meta.get('aligned_oldest_date','NA')})"
    )
    md.append("- targets (percentiles): " + str(calib_meta.get("targets", {})))
    if threshold_policy == "percentile":
        # show per-threshold status succinctly
        for k in ("exp20", "contr20", "watch1d", "watch_spread20", "watch_accel", "cool_accel", "cool_1d"):
            m = calib_meta.get("per_threshold", {}).get(k, {})
            md.append(
                f"- {k}: status={m.get('status','NA')}｜target_pct={m.get('target_pct','NA')}｜"
                f"used={fmt_num(m.get('used_value', None), 6)}｜fixed={fmt_num(m.get('fixed_value', None), 6)}｜"
                f"n={_get(_get(m,'dist',{}),'n','NA')}｜reason={m.get('reason','NA')}"
            )
    else:
        md.append("- policy=fixed：不做校準（此段僅做紀錄）")
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
    md.append(f"- maint_ratio_policy: {maint_ratio_policy}")
    md.append(f"- maint_ratio_confidence: {maint_ratio_confidence}")

    if maint_ok and maint_latest is not None:
        md.append(f"- data_date: {_norm_date_iso(_get(maint_latest,'data_date','NA')) or 'NA'}｜maint_ratio_pct: {_get(maint_latest,'maint_ratio_pct','NA')}")
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
    md.append("- rows_latest_table/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。")
    md.append("- rows_series 是計算輸入序列長度（由 history.json 彙整），用於 horizon 計算與 Check-4。")
    md.append("- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。")
    md.append("- roll25 若顯示 UsedDateStatus=DATA_NOT_UPDATED：代表資料延遲；Check-6 以 NOTE 呈現（非抓錯檔）。")
    md.append(f"- resonance_policy={resonance_policy}：strict 需同日且非 stale；latest 允許 stale/date mismatch 但會 resonance_confidence=DOWNGRADED。")
    md.append("- maint_ratio 為 proxy（display-only）：僅看趨勢與變化（Δ），不得用 proxy 絕對水位做門檻判斷。")
    md.append("- threshold calibration：僅在 --threshold-policy percentile 時啟用；資料不足或未提供 target_pct 會明確回退 fixed。")
    md.append("")

    md.append("## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint/校準僅供對照）")
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

    # Check-12: calibration (info-only)
    if threshold_policy == "percentile":
        # if ALL are fallback fixed, mark NOTE
        statuses = [calib_meta.get("per_threshold", {}).get(k, {}).get("status") for k in ("exp20", "contr20", "watch1d", "watch_spread20", "watch_accel")]
        any_calibrated = any(s == "CALIBRATED" for s in statuses if s)
        md.append(line_check("Check-12 threshold calibration applied（info）", "PASS" if any_calibrated else "NOTE",
                             "some thresholds calibrated" if any_calibrated else "no thresholds calibrated (all fallback fixed)"))
    else:
        md.append(line_check("Check-12 threshold calibration applied（info）", "NOTE", "policy=fixed"))

    md.append("")
    generated_at_utc = latest.get("generated_at_utc", None) if isinstance(latest, dict) else None
    if not generated_at_utc:
        generated_at_utc = now_utc_iso()
    md.append(f"_generated_at_utc: {generated_at_utc}_")
    md.append("")

    # write markdown (existing behavior)
    out_parent = os.path.dirname(args.out)
    if out_parent:
        os.makedirs(out_parent, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # ---------- Added: emit signals_latest.json for unified dashboard (NO LOGIC CHANGE) ----------
    roll_is_heated: Optional[bool] = None
    if roll_ok and roll is not None:
        roll_is_heated = roll25_is_heated(roll)

    signals: Dict[str, Any] = {
        "schema_version": "tw_margin_signals_latest_v1",
        "module": "taiwan_margin_financing",
        "generated_at_utc": generated_at_utc,
        "generated_at_local": latest.get("generated_at_local", None) if isinstance(latest, dict) else None,
        # compact summary keys (likely what unified dashboard wants)
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
        # upstream status (pass-through)
        "upstream": {
            "latest_json": {
                "confidence": top_conf,
                "fetch_status": top_fetch,
                "dq_reason": top_dq,
                "has_top_quality": has_top_quality,
            }
        },
        # NEW: thresholds + calibration meta (audit-only; deterministic)
        "thresholds": {
            "policy": threshold_policy,
            "fixed": fixed_th,
            "used": used_th,
            "calibration": calib_meta,
        },
        # core computed numbers (for unified dashboard and auditing)
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
            "total": {
                "h1": tot1,
                "h5": tot5,
                "h20": tot20,
            },
            "derived": {
                "accel": accel,
                "spread20": spread20,
            },
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
            "policy": maint_ratio_policy,
            "confidence": maint_ratio_confidence,
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
                "fetch_status": _get(maint_latest, "fetch_status", None) if maint_ok and maint_latest else None,
                "confidence": _get(maint_latest, "confidence", None) if maint_ok and maint_latest else None,
                "dq_reason": _get(maint_latest, "dq_reason", None) if maint_ok and maint_latest else None,
            },
            "history": {
                "rows": len(maint_hist_list),
                "head5": maint_head,
            },
        },
        "checks": {
            "margin": {
                "c1_tw_ok": c1_tw_ok,
                "c1_tp_ok": c1_tp_ok,
                "c2_tw_ok": c2_tw_ok,
                "c2_tp_ok": c2_tp_ok,
                "c3_ok": c3_ok,
                "c4_tw_ok": c4_tw_ok,
                "c4_tp_ok": c4_tp_ok,
                "c5_tw_ok": c5_tw_ok,
                "c5_tp_ok": c5_tp_ok,
                "margin_any_fail": margin_any_fail,
            },
            "roll25": {
                "check_6_status": c6_status,
                "check_6_msg": c6_msg,
                "check_7_status": c7_status,
                "check_7_msg": c7_msg,
            },
            "maint": {
                "check_10_status": c10_status,
                "check_10_msg": c10_msg,
                "check_11_status": c11_status,
                "check_11_msg": c11_msg,
            },
            "thresholds": {
                "policy": threshold_policy,
            },
        },
        "inputs": {
            "latest_path": args.latest,
            "history_path": args.history,
            "out_md_path": args.out,
            "signals_out_path": args.signals_out,
            "resonance_policy": resonance_policy,
            "threshold_policy": threshold_policy,
            "calib_min_n": calib_min_n,
        },
        # quick sanity snapshot to help detect page mixups without parsing markdown
        "snapshots": {
            "twse_rows": {
                "rows": twse_rows_latest_table,      # backward-compatible: latest table rows
                "rows_series": twse_rows_series,     # new explicit metric
                "head_dates": twse_head_dates,
                "tail_dates": twse_tail_dates,
            },
            "tpex_rows": {
                "rows": tpex_rows_latest_table,
                "rows_series": tpex_rows_series,
                "head_dates": tpex_head_dates,
                "tail_dates": tpex_tail_dates,
            },
        },
    }

    write_json(args.signals_out, signals)


if __name__ == "__main__":
    main()