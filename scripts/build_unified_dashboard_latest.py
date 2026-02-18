#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build unified dashboard JSON from module outputs.

Adds:
- roll25_derived: N-day realized volatility (annualized) + max drawdown
- fx_usdtwd: USD/TWD spot mid (BOT) + ret1/chg_5d + deterministic signal rule
- taiwan_margin_financing.cross_module:
  - margin_signal (derived from TWSE chg_yi last5 if not present)
  - roll25_heated_market (derived from roll25 report MARKET signals only)
  - roll25_data_quality_issue (derived from roll25 report DATA QUALITY only)
  - roll25_confidence (DOWNGRADED when lookback not full or unknown)
  - consistency (CONVERGENCE/DIVERGENCE) based on margin_signal × roll25_heated_market
  - deterministic rationale

NEW (2026-01-26):
- Optional merge-in (display-only; NO impact to unified logic):
  - inflation_realrate_cache/dashboard_latest.json
  - asset_proxy_cache/dashboard_latest.json

NEW (2026-02-18):
- Optional merge-in nasdaq_bb_cache (display-only; NO impact to unified logic):
  - Reads from a directory (default: nasdaq_bb_cache/)
  - Supports the files you currently generate:
    - snippet_price_qqq.us.json / snippet_price_qqq.json
    - snippet_vxn.json
    - snippet_price_^ndx.json (optional)

NO external fetch here. Pure merge + deterministic calculations.

Inputs:
- dashboard/dashboard_latest.json
- dashboard_fred_cache/dashboard_latest.json
- taiwan_margin_cache/latest.json
- roll25_cache/latest_report.json
- fx_cache/latest.json (+ fx_cache/history.json)
- [optional] inflation_realrate_cache/dashboard_latest.json
- [optional] asset_proxy_cache/dashboard_latest.json
- [optional] nasdaq_bb_cache/ (dir)

Output:
- unified_dashboard/latest.json (or any path you pass)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Common helpers
# ----------------------------


def _norm_key(s: Any) -> str:
    """Normalize keys for case/format-insensitive matching."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _find_first_existing(base_dir: str, candidates: List[str]) -> Optional[str]:
    """Return the first existing filename within base_dir, or None."""
    for name in candidates:
        p = os.path.join(base_dir, name)
        if os.path.exists(p):
            return name
    return None


def _find_first_existing(base_dir: str, candidates: List[str]) -> Optional[str]:
    """Return first existing filename under base_dir from candidates."""
    for name in candidates:
        p = os.path.join(base_dir, name)
        if os.path.exists(p):
            return name
    return None


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _dump_json(path: str, obj: Any) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _to_float(x: Any) -> Optional[float]:
    """
    Conservative float parser:
    - int/float => float
    - str => parse first number; supports optional '%' suffix
    - otherwise => None
    """
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s or s.upper() == "NA" or s.upper() == "N/A":
            return None
        # keep only a leading numeric token, allow - and .
        m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except Exception:
            return None
    return None


# ---------- Roll25 derived metrics ----------

def _extract_roll25_closes(roll25_latest_report: Dict[str, Any]) -> List[float]:
    arr = roll25_latest_report.get("cache_roll25")
    out: List[float] = []
    if isinstance(arr, list):
        for it in arr:
            if isinstance(it, dict):
                v = it.get("close")
                if isinstance(v, (int, float)):
                    out.append(float(v))
    return out  # newest->oldest


def _realized_vol_annualized_pct(closes_newest_first: List[float], n: int) -> Tuple[Optional[float], int]:
    if n <= 0:
        return None, 0
    if len(closes_newest_first) < n + 1:
        return None, 0

    closes = closes_newest_first[: n + 1]
    rets: List[float] = []
    for i in range(n):
        c_new = closes[i]
        c_old = closes[i + 1]
        if c_new <= 0 or c_old <= 0:
            return None, 0
        rets.append(math.log(c_new / c_old))

    if len(rets) < 2:
        return None, len(rets)

    mean = sum(rets) / len(rets)
    var = sum((xx - mean) ** 2 for xx in rets) / (len(rets) - 1)
    vol_daily = math.sqrt(max(var, 0.0))
    vol_ann = vol_daily * math.sqrt(252.0)
    return vol_ann * 100.0, len(rets)


def _max_drawdown_pct(closes_newest_first: List[float], n: int) -> Tuple[Optional[float], int]:
    if n <= 1:
        return None, 0
    if len(closes_newest_first) < n:
        return None, 0

    series = list(reversed(closes_newest_first[:n]))  # oldest->newest
    peak = -1e100
    max_dd = 0.0
    for c in series:
        if c > peak:
            peak = c
        if peak > 0:
            dd = (c / peak) - 1.0
            if dd < max_dd:
                max_dd = dd
    return max_dd * 100.0, len(series)


def _extract_lookback_target_from_roll25_report(roll_obj: Dict[str, Any]) -> Optional[int]:
    for path in [
        ("core", "LookbackNTarget"),
        ("numbers", "LookbackNTarget"),
        ("LookbackNTarget",),
    ]:
        v = _safe_get(roll_obj, *path) if len(path) > 1 else roll_obj.get(path[0])
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)

    cav = roll_obj.get("caveats")
    if isinstance(cav, str):
        m = re.search(r"LookbackNTarget=(\d+)", cav)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None


def _extract_useddate_from_roll25_report(roll_obj: Dict[str, Any]) -> Optional[str]:
    v = _safe_get(roll_obj, "numbers", "UsedDate")
    if isinstance(v, str):
        return v
    v2 = roll_obj.get("used_date")
    if isinstance(v2, str):
        return v2
    return None


def _infer_run_day_tag_from_utc_z(generated_at_utc_z: str) -> str:
    try:
        dt_utc = datetime.strptime(generated_at_utc_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        dt_tpe = dt_utc.astimezone(timezone(timedelta(hours=8)))
        wd = dt_tpe.weekday()
        return "NON_TRADING_DAY" if wd >= 5 else "TRADING_DAY"
    except Exception:
        return "NA"


def _max_roll25_date(latest_report: Dict[str, Any]) -> Optional[str]:
    arr = latest_report.get("cache_roll25")
    if not isinstance(arr, list) or not arr:
        return None
    dates: List[str] = []
    for r in arr:
        if isinstance(r, dict) and isinstance(r.get("date"), str):
            dates.append(r["date"])
    return max(dates) if dates else None


def _compute_used_date_status_v1(latest_report: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    used_date = _extract_useddate_from_roll25_report(latest_report)
    ohlc_status = latest_report.get("ohlc_status") if isinstance(latest_report.get("ohlc_status"), str) else None
    freshness_ok = latest_report.get("freshness_ok")
    latest_row_date = _max_roll25_date(latest_report)

    dbg = {
        "used_date": used_date or "NA",
        "latest_row_date": latest_row_date or "NA",
        "ohlc_status": ohlc_status or "NA",
        "freshness_ok": freshness_ok if isinstance(freshness_ok, bool) else "NA",
    }

    if not isinstance(used_date, str) or not used_date:
        return "MISSING_USED_DATE", dbg

    if isinstance(ohlc_status, str) and ohlc_status.upper() == "MISSING":
        return "DATA_NOT_UPDATED", dbg

    if freshness_ok is False:
        return "DATA_NOT_UPDATED", dbg

    if isinstance(latest_row_date, str) and latest_row_date:
        if used_date == latest_row_date:
            return "OK_LATEST", dbg
        return "DATA_NOT_UPDATED", dbg

    return "UNKNOWN_LATEST_ROW_DATE", dbg


def _roll25_heated_rule_v2_split(roll_obj: Dict[str, Any]) -> Dict[str, Any]:
    tag_legacy = roll_obj.get("tag")
    risk_level = roll_obj.get("risk_level")
    nums = roll_obj.get("numbers") if isinstance(roll_obj.get("numbers"), dict) else {}
    sigs = roll_obj.get("signal") if isinstance(roll_obj.get("signal"), dict) else {}

    used_date = _extract_useddate_from_roll25_report(roll_obj)

    def _b(x: Any) -> bool:
        return bool(x) is True

    market_keys = ["DownDay", "VolumeAmplified", "VolAmplified", "NewLow_N", "ConsecutiveBreak"]
    market_hits = {k: _b(sigs.get(k)) for k in market_keys}
    heated_market = any(market_hits.values())

    ohlc_missing_signal = _b(sigs.get("OhlcMissing"))
    ohlc_status = roll_obj.get("ohlc_status") if isinstance(roll_obj.get("ohlc_status"), str) else None
    freshness_ok = roll_obj.get("freshness_ok") if isinstance(roll_obj.get("freshness_ok"), bool) else None

    used_date_status, used_date_status_dbg = _compute_used_date_status_v1(roll_obj)
    used_date_status_bad = used_date_status in {"DATA_NOT_UPDATED", "MISSING_USED_DATE", "UNKNOWN_LATEST_ROW_DATE"}

    data_quality_hits = {
        "OhlcMissing(signal)": ohlc_missing_signal,
        "OHLCStatusMissing(field)": (isinstance(ohlc_status, str) and ohlc_status.upper() == "MISSING"),
        "FreshnessNotOK(field)": (freshness_ok is False),
        "UsedDateStatusBad(derived)": bool(used_date_status_bad),
    }
    data_quality_issue = any(data_quality_hits.values())

    lookback_actual = roll_obj.get("lookback_n_actual")
    if not isinstance(lookback_actual, int):
        la2 = nums.get("LookbackNActual")
        if isinstance(la2, int):
            lookback_actual = la2

    lookback_target = _extract_lookback_target_from_roll25_report(roll_obj)

    confidence = "OK"
    if not isinstance(lookback_actual, int):
        confidence = "DOWNGRADED"
    elif lookback_target is None:
        confidence = "DOWNGRADED"
    elif lookback_actual < lookback_target:
        confidence = "DOWNGRADED"

    window_note = (
        f"LookbackNActual={lookback_actual}/{lookback_target} (window_not_full)"
        if isinstance(lookback_actual, int) and isinstance(lookback_target, int) and lookback_actual < lookback_target
        else (
            f"LookbackNActual={lookback_actual}/{lookback_target}"
            if isinstance(lookback_actual, int)
            else "LookbackNActual=NA"
        )
    )

    return {
        "roll25_heated_market": bool(heated_market),
        "roll25_data_quality_issue": bool(data_quality_issue),
        "roll25_heated": bool(heated_market),  # legacy == market only
        "roll25_confidence": confidence,
        "roll25_rationale": {
            "rule_market": "heated_market=True if any market-behavior signals true else False",
            "rule_data_quality": "data_quality_issue=True if any data-quality flags true else False",
            "used_date_selection_tag(tag_legacy)": tag_legacy if isinstance(tag_legacy, str) else "NA",
            "risk_level": risk_level if isinstance(risk_level, str) else "NA",
            "window_note": window_note,
            "signals_market_used": {
                "DownDay": sigs.get("DownDay", False),
                "VolumeAmplified": sigs.get("VolumeAmplified", False),
                "VolAmplified": sigs.get("VolAmplified", False),
                "NewLow_N": sigs.get("NewLow_N", False),
                "ConsecutiveBreak": sigs.get("ConsecutiveBreak", False),
            },
            "signals_data_quality_used": {
                "OhlcMissing": sigs.get("OhlcMissing", False),
                "ohlc_status": ohlc_status if isinstance(ohlc_status, str) else "NA",
                "freshness_ok": freshness_ok if isinstance(freshness_ok, bool) else "NA",
                "used_date_status": used_date_status,
                "used_date_status_dbg": used_date_status_dbg,
            },
            "market_hits": market_hits,
            "data_quality_hits": data_quality_hits,
            "used_date": used_date or "NA",
        },
    }


# ---------- Margin signal (TWSE) ----------

def _extract_twm_series(twm_obj: Dict[str, Any], market: str) -> Optional[Dict[str, Any]]:
    series = _safe_get(twm_obj, "series")
    if not isinstance(series, dict):
        return None
    node = series.get(market)
    return node if isinstance(node, dict) else None


def _derive_margin_signal_rule_v1_from_twm(twm_obj: Dict[str, Any]) -> Dict[str, Any]:
    twse = _extract_twm_series(twm_obj, "TWSE") or {}
    rows = twse.get("rows")
    chgs: List[float] = []
    if isinstance(rows, list):
        for it in rows[:10]:
            if isinstance(it, dict):
                v = it.get("chg_yi")
                if isinstance(v, (int, float)):
                    chgs.append(float(v))

    last5 = chgs[:5]
    points = len(last5)
    sum_last5 = sum(last5) if points > 0 else 0.0
    pos_days = sum(1 for xx in last5 if xx > 0)
    latest_chg = last5[0] if points >= 1 else None

    signal = "NA"
    rule_hit = "NA"
    if points >= 1:
        hit_watch = (
            (points >= 5 and sum_last5 >= 100.0)
            or (points >= 5 and pos_days >= 4 and latest_chg is not None and latest_chg >= 40.0)
        )
        hit_info = (
            (points >= 5 and sum_last5 >= 60.0)
            or (points >= 5 and pos_days >= 3 and latest_chg is not None and latest_chg >= 30.0)
        )
        if hit_watch:
            signal = "WATCH"
            rule_hit = "WATCH if sum_last5>=100 OR (pos_days>=4 AND latest_chg>=40)"
        elif hit_info:
            signal = "INFO"
            rule_hit = "INFO if sum_last5>=60 OR (pos_days>=3 AND latest_chg>=30)"
        else:
            signal = "NONE"
            rule_hit = "below thresholds"

    confidence = "OK" if points >= 5 else "DOWNGRADED"
    data_date = twse.get("data_date") if isinstance(twse.get("data_date"), str) else None

    return {
        "margin_signal": signal,
        "margin_signal_source": "DERIVED.rule_v1(TWSE_chg_yi_last5)",
        "margin_rationale": {
            "method": "derived_rule",
            "basis": "TWSE chg_yi last5",
            "chg_last5": last5,
            "sum_last5": sum_last5,
            "pos_days_last5": pos_days,
            "latest_chg": latest_chg,
            "rule_version": "rule_v1",
            "rule_hit": rule_hit,
            "confidence": confidence,
            "twse_data_date": data_date or "NA",
        },
    }


def _get_margin_signal_prefer_structured(twm_obj: Dict[str, Any]) -> Dict[str, Any]:
    cm = twm_obj.get("cross_module")
    if isinstance(cm, dict) and isinstance(cm.get("margin_signal"), str):
        return {
            "margin_signal": cm.get("margin_signal", "NA"),
            "margin_signal_source": cm.get("margin_signal_source", "STRUCTURED"),
            "margin_rationale": cm.get("margin_rationale", {"method": "structured_or_unknown"}),
        }
    return _derive_margin_signal_rule_v1_from_twm(twm_obj)


def _date_alignment(twm_obj: Dict[str, Any], roll_obj: Dict[str, Any]) -> Dict[str, Any]:
    twse = _extract_twm_series(twm_obj, "TWSE") or {}
    twm_date = twse.get("data_date") if isinstance(twse.get("data_date"), str) else None
    used_date = _extract_useddate_from_roll25_report(roll_obj)
    used_date_match = (twm_date is not None and used_date is not None and twm_date == used_date)
    return {
        "twmargin_date": twm_date or "NA",
        "roll25_used_date": used_date or "NA",
        "used_date_match": bool(used_date_match),
        "note": "confirm-only; does not change signal",
    }


def _consistency_rule_v1(margin_signal: str, roll25_heated_market: bool) -> Dict[str, Any]:
    ms = margin_signal or "NA"
    heated = bool(roll25_heated_market)
    diverge = ((ms in ("WATCH", "ALERT")) and (not heated)) or ((ms == "NONE") and heated)
    return {
        "consistency": "DIVERGENCE" if diverge else "CONVERGENCE",
        "consistency_rule": "Deterministic Margin×Roll25MarketHeat (rule_v1).",
    }


# ---------- FX derived metrics ----------

def _load_fx_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        obj = _load_json(path)
        items = obj.get("items") if isinstance(obj, dict) else None
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict) and isinstance(x.get("date"), str)]
    except Exception:
        return []
    return []


def _fx_ret1_and_chg5(history_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    mids: List[float] = []
    dates: List[str] = []
    for it in history_items:
        mid = it.get("mid")
        if isinstance(mid, (int, float)) and isinstance(it.get("date"), str):
            mids.append(float(mid))
            dates.append(it["date"])

    out: Dict[str, Any] = {
        "ret1_pct": None,
        "ret1_from": None,
        "ret1_to": None,
        "chg_5d_pct": None,
        "chg_5d_from": None,
        "chg_5d_to": None,
        "points": len(mids),
    }
    if len(mids) >= 2:
        prev = mids[-2]
        last = mids[-1]
        if prev != 0:
            out["ret1_pct"] = (last - prev) / abs(prev) * 100.0
            out["ret1_from"] = dates[-2]
            out["ret1_to"] = dates[-1]
    if len(mids) >= 6:
        base = mids[-6]
        last = mids[-1]
        if base != 0:
            out["chg_5d_pct"] = (last - base) / abs(base) * 100.0
            out["chg_5d_from"] = dates[-6]
            out["chg_5d_to"] = dates[-1]
    return out


def _fx_signal_rule_v1(ret1_pct: Optional[float], chg_5d_pct: Optional[float], points: int) -> Dict[str, Any]:
    def _abs(x: Optional[float]) -> Optional[float]:
        return None if x is None else abs(float(x))

    a1 = _abs(ret1_pct)
    a5 = _abs(chg_5d_pct)

    signal = "NA"
    reason = "NA"
    if a1 is not None or a5 is not None:
        hit_watch = ((a5 is not None and a5 >= 1.5) or (a1 is not None and a1 >= 1.0))
        hit_info = ((a5 is not None and a5 >= 1.0) or (a1 is not None and a1 >= 0.7))
        if hit_watch:
            signal = "WATCH"
            reason = "abs(chg_5d%)>=1.5 OR abs(ret1%)>=1.0"
        elif hit_info:
            signal = "INFO"
            reason = "abs(chg_5d%)>=1.0 OR abs(ret1%)>=0.7"
        else:
            signal = "NONE"
            reason = "below thresholds"

    confidence = "OK"
    if points < 2 or a1 is None:
        confidence = "DOWNGRADED"
    elif points < 6 or a5 is None:
        confidence = "DOWNGRADED"

    return {
        "fx_signal": signal,
        "fx_reason": reason,
        "fx_rule_version": "rule_v1",
        "fx_confidence": confidence,
    }


# ---------- Optional module loader (display-only) ----------

def _load_optional(path: str) -> Tuple[str, Any]:
    """
    Optional input:
    - If file missing => status=MISSING
    - If JSON invalid => status=ERROR: <...>
    - If OK => status=OK and obj
    """
    try:
        if not os.path.exists(path):
            return "MISSING", None
        return "OK", _load_json(path)
    except Exception as e:
        return f"ERROR: {type(e).__name__}", None


def _listdir_safe(path: str) -> List[str]:
    try:
        return sorted(os.listdir(path))
    except Exception:
        return []


def _pick_existing(base_dir: str, candidates: List[str]) -> Optional[str]:
    for fn in candidates:
        p = os.path.join(base_dir, fn)
        if os.path.exists(p):
            return p
    return None


def _path_to_str(path: Tuple[Any, ...]) -> str:
    if not path:
        return "root"
    parts: List[str] = ["root"]
    for p in path:
        if isinstance(p, int):
            parts.append(f"[{p}]")
        else:
            # dot-escape minimally
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(p)):
                parts.append(f".{p}")
            else:
                parts.append(f"[{json.dumps(str(p), ensure_ascii=False)}]")
    return "".join(parts)


def _iter_dict_nodes(obj: Any, path: Tuple[Any, ...] = (), max_nodes: int = 2000) -> List[Tuple[Tuple[Any, ...], Dict[str, Any]]]:
    """
    Return a flat list of (path, dict_node) for all dict nodes found within obj.
    Deterministic DFS order.
    """
    out: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []
    stack: List[Tuple[Tuple[Any, ...], Any]] = [(path, obj)]
    while stack and len(out) < max_nodes:
        p, cur = stack.pop()
        if isinstance(cur, dict):
            out.append((p, cur))
            # deterministic: push reversed so first key visited first
            for k in reversed(list(cur.keys())):
                stack.append((p + (k,), cur.get(k)))
        elif isinstance(cur, list):
            for i in reversed(range(len(cur))):
                stack.append((p + (i,), cur[i]))
    return out


def _find_any_key(d: Dict[str, Any], keys: List[str]) -> Tuple[Any, Optional[Tuple[Any, ...]]]:
    for k in keys:
        if k in d:
            return d.get(k), (k,)
    return None, None


def _find_any_key_one_level_nested(d: Dict[str, Any], wrappers: List[str], keys: List[str]) -> Tuple[Any, Optional[Tuple[Any, ...]]]:
    # check wrapper dicts one level deep (common schemas)
    for w in wrappers:
        node = d.get(w)
        if isinstance(node, dict):
            v, kp = _find_any_key(node, keys)
            if kp is not None:
                return v, (w,) + kp
    return None, None


def _score_candidate(d: Dict[str, Any], kind: str) -> int:
    # scoring weights prioritize having price/value + signal + band stats
    date_keys = ["data_date", "date", "as_of_date", "asof", "as_of", "day", "dt", "used_date"]
    close_keys = ["close", "Close", "adj_close", "last", "last_close", "px_last", "price", "value", "Value"]
    signal_keys = ["signal", "tag", "state", "mode", "status", "bb_signal"]
    z_keys = ["z", "zscore", "z_score", "bb_z", "z_bb", "z60"]
    pos_keys = [
        "position_in_band",
        "pos_in_band",
        "band_pos",
        "positionInBand",
        "bandPosition",
        "position",
        "percent_b",
        "percentB",
        "pct_b",
        "pctB",
        "%b",
    ]
    dl_keys = ["dist_to_lower", "dist_lower", "dist_lower_pct", "lower_dist", "pct_to_lower"]
    du_keys = ["dist_to_upper", "dist_upper", "dist_upper_pct", "upper_dist", "pct_to_upper"]
    wrappers = ["numbers", "price", "stats", "bb", "bands", "band", "data", "row", "latest", "last", "out", "result", "metrics"]

    score = 0

    # date
    v, _ = _find_any_key(d, date_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, ["meta"] + wrappers, date_keys)
    if v is not None:
        score += 1

    # close/value
    v, _ = _find_any_key(d, close_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, wrappers, close_keys)
    if v is not None:
        score += 3

    # signal
    v, _ = _find_any_key(d, signal_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, wrappers, signal_keys)
    if v is not None:
        score += 2

    # z
    v, _ = _find_any_key(d, z_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, wrappers, z_keys)
    if v is not None:
        score += 2

    # position in band
    v, _ = _find_any_key(d, pos_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, wrappers, pos_keys)
    if v is not None:
        score += 2

    # dist to lower/upper
    v, _ = _find_any_key(d, dl_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, wrappers, dl_keys)
    if v is not None:
        score += 1

    v, _ = _find_any_key(d, du_keys)
    if v is None:
        v, _ = _find_any_key_one_level_nested(d, wrappers, du_keys)
    if v is not None:
        score += 1

    # kind hint
    k = d.get("kind")
    if isinstance(k, str) and k.upper() == kind.upper():
        score += 1

    return score


def _select_best_candidate(obj: Any, kind: str) -> Tuple[Optional[Dict[str, Any]], str, int]:
    """
    Return (best_dict_node, best_path_str, best_score).
    If no dict nodes exist, returns (None, "NA", 0).
    """
    nodes = _iter_dict_nodes(obj)
    best: Optional[Dict[str, Any]] = None
    best_path = "NA"
    best_score = 0
    best_depth = 10**9

    for p, d in nodes:
        sc = _score_candidate(d, kind)
        depth = len(p)
        if (sc > best_score) or (sc == best_score and depth < best_depth):
            best = d
            best_score = sc
            best_depth = depth
            best_path = _path_to_str(p)

    return best, best_path, best_score


def _parse_nasdaq_report_md(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Best-effort parse for report.md produced by nasdaq BB scripts.
    Only used as fallback to fill missing fields.
    """
    out: Dict[str, Dict[str, Any]] = {}

    # Example line (from your pasted report.md):
    # - **QQQ** (2026-02-17 close=601.3000) → **NEAR_LOWER_BAND (MONITOR)** (reason=z<=-1.5); dist_to_lower=0.781%; dist_to_upper=5.927%; ...
    pat = re.compile(
        r"\*\*(?P<sym>[A-Z0-9\^]+)\*\*"
        r"\s*\((?P<date>\d{4}-\d{2}-\d{2})\s+(?:close|value)=(?P<cv>[-+0-9\.,]+)\)"
        r"\s*→\s*\*\*(?P<sig>[^*]+)\*\*"
        r".*?dist_to_lower=(?P<dl>[-+0-9\.]+)%"
        r";\s*dist_to_upper=(?P<du>[-+0-9\.]+)%",
        re.IGNORECASE,
    )

    for m in pat.finditer(text):
        sym = m.group("sym").upper()
        dd = m.group("date")
        cv = _to_float(m.group("cv"))
        dl = _to_float(m.group("dl"))
        du = _to_float(m.group("du"))
        sig = m.group("sig").strip()

        out[sym] = {
            "data_date": dd,
            "close_or_value": cv,
            "signal": sig,
            "dist_to_lower": dl,
            "dist_to_upper": du,
        }

    return out


def _extract_symbol_block(obj: Any, kind: str, report_fallback: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Return (block, dbg) where block is the normalized symbol dict and dbg is internal debug for errors[] only.
    """
    candidate, cand_path, cand_score = _select_best_candidate(obj, kind)
    base = candidate if isinstance(candidate, dict) else (obj if isinstance(obj, dict) else {})
    dbg: Dict[str, Any] = {"candidate_path": cand_path, "candidate_score": cand_score}

    # Try keys at base, then common wrappers.
    wrappers = ["numbers", "price", "stats", "bb", "bands", "band", "data", "row", "latest", "last", "out", "result", "metrics"]
    date_keys = ["data_date", "date", "as_of_date", "asof", "as_of", "day", "dt", "used_date"]
    close_keys = ["close", "Close", "adj_close", "last", "last_close", "px_last", "price"]
    value_keys = ["value", "Value", "close", "Close"]
    signal_keys = ["signal", "tag", "state", "mode", "status", "bb_signal"]
    z_keys = ["z", "zscore", "z_score", "bb_z", "z_bb", "z60"]
    pos_keys = [
        "position_in_band",
        "pos_in_band",
        "band_pos",
        "positionInBand",
        "bandPosition",
        "position",
        "percent_b",
        "percentB",
        "pct_b",
        "pctB",
        "%b",
    ]
    dl_keys = ["dist_to_lower", "dist_lower", "dist_lower_pct", "lower_dist", "pct_to_lower"]
    du_keys = ["dist_to_upper", "dist_upper", "dist_upper_pct", "upper_dist", "pct_to_upper"]

    def _pick(keys: List[str]) -> Tuple[Any, str]:
        v, kp = _find_any_key(base, keys)
        if kp is not None:
            return v, _path_to_str(kp)
        v, kp = _find_any_key_one_level_nested(base, ["meta"] + wrappers, keys)
        if kp is not None:
            return v, _path_to_str(kp)
        return None, "NA"

    # date
    raw_date, date_path = _pick(date_keys)
    if raw_date is None and isinstance(obj, dict):
        # last resort: root meta
        v = _safe_get(obj, "meta", "data_date")
        if isinstance(v, str):
            raw_date, date_path = v, "root.meta.data_date"

    data_date = raw_date if isinstance(raw_date, str) else "NA"

    # close/value
    raw_close, close_path = _pick(close_keys)
    raw_value, value_path = _pick(value_keys)

    # Choose close vs value by kind
    raw_cv = None
    cv_path = "NA"
    if kind.upper() == "VXN":
        raw_cv = raw_value if raw_value is not None else raw_close
        cv_path = value_path if raw_value is not None else close_path
    else:
        raw_cv = raw_close if raw_close is not None else raw_value
        cv_path = close_path if raw_close is not None else value_path

    cv = _to_float(raw_cv)
    close = cv if kind.upper() != "VXN" else "NA"
    value = cv if kind.upper() == "VXN" else "NA"

    # signal (string)
    raw_sig, sig_path = _pick(signal_keys)
    signal = raw_sig.strip() if isinstance(raw_sig, str) and raw_sig.strip() else "NA"

    # z / position / dist
    raw_z, z_path = _pick(z_keys)
    z = _to_float(raw_z)

    raw_pos, pos_path = _pick(pos_keys)
    position_in_band = _to_float(raw_pos)

    raw_dl, dl_path = _pick(dl_keys)
    dist_to_lower = _to_float(raw_dl)

    raw_du, du_path = _pick(du_keys)
    dist_to_upper = _to_float(raw_du)

    # Fallback from report.md (only fill missing, never override extracted numeric values)
    fb = report_fallback or {}
    fb_sym = fb if isinstance(fb, dict) else {}
    if data_date == "NA" and isinstance(fb_sym.get("data_date"), str):
        data_date = fb_sym["data_date"]
    if cv is None and isinstance(fb_sym.get("close_or_value"), (int, float)):
        cv = float(fb_sym["close_or_value"])
        close = cv if kind.upper() != "VXN" else "NA"
        value = cv if kind.upper() == "VXN" else "NA"
    if signal == "NA" and isinstance(fb_sym.get("signal"), str):
        signal = fb_sym["signal"]
    if dist_to_lower is None and isinstance(fb_sym.get("dist_to_lower"), (int, float)):
        dist_to_lower = float(fb_sym["dist_to_lower"])
    if dist_to_upper is None and isinstance(fb_sym.get("dist_to_upper"), (int, float)):
        dist_to_upper = float(fb_sym["dist_to_upper"])

    dbg.update(
        {
            "paths": {
                "data_date": date_path,
                "close_or_value": cv_path,
                "signal": sig_path,
                "z": z_path,
                "position_in_band": pos_path,
                "dist_to_lower": dl_path,
                "dist_to_upper": du_path,
            }
        }
    )

    block = {
        "data_date": data_date,
        "close": close if isinstance(close, (int, float)) else "NA",
        "value": value if isinstance(value, (int, float)) else "NA",
        "close_or_value": cv if isinstance(cv, (int, float)) else "NA",
        "signal": signal,
        "z": z if isinstance(z, (int, float)) else "NA",
        "position_in_band": position_in_band if isinstance(position_in_band, (int, float)) else "NA",
        "dist_to_lower": dist_to_lower if isinstance(dist_to_lower, (int, float)) else "NA",
        "dist_to_upper": dist_to_upper if isinstance(dist_to_upper, (int, float)) else "NA",
        "kind": kind,
    }
    return block, dbg


def _load_nasdaq_bb_cache_dir(base_dir: str) -> Tuple[str, Dict[str, Any]]:
    """
    Load nasdaq_bb_cache output directory for display-only merge.

    Expected files (best-effort):
    - snippet_price_qqq.us.json (preferred) or snippet_price_qqq.json
    - snippet_vxn.json
    - snippet_price_^ndx.json

    Robust parsing:
    - Select best candidate dict node by heuristic scoring (handles nested schemas).
    - Fallback fill from report.md (if present) for date/close/signal/dist values.
    """
    if not os.path.isdir(base_dir):
        return "MISSING", {
            "note": "display-only; not used for positioning/mode/cross_module",
            "dir": base_dir,
            "files_found": [],
        }

    files = sorted(os.listdir(base_dir))
    report_path = os.path.join(base_dir, "report.md")

    # report.md fallback
    report_fallback_all: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(report_path):
        try:
            report_fallback_all = _parse_nasdaq_report_md(_read_text(report_path))
        except Exception:
            report_fallback_all = {}

    # choose snippet files
    p_qqq = _find_first_existing(base_dir, ["snippet_price_qqq.us.json", "snippet_price_qqq.json"])
    p_vxn = _find_first_existing(base_dir, ["snippet_vxn.json"])
    p_ndx = _find_first_existing(base_dir, ["snippet_price_^ndx.json", "snippet_price_ndx.json", "snippet_price_ndx.us.json"])

    files_used = {
        "QQQ": (os.path.join(base_dir, p_qqq) if p_qqq else "NA"),
        "VXN": (os.path.join(base_dir, p_vxn) if p_vxn else "NA"),
        "NDX": (os.path.join(base_dir, p_ndx) if p_ndx else "NA"),
    }

    errors: Dict[str, str] = {"QQQ": "NA", "VXN": "NA", "NDX": "NA"}
    out: Dict[str, Any] = {
        "note": "display-only; not used for positioning/mode/cross_module",
        "dir": base_dir,
        "files_found": files,
        "files_used": files_used,
        "errors": errors,
    }

    def _load_one(path: str) -> Any:
        return _load_json(path)

    def _load_and_extract(kind: str, path: Optional[str]) -> Dict[str, Any]:
        if not path:
            errors[kind] = "MISSING_SNIPPET"
            return {
                "data_date": "NA",
                "close": "NA",
                "value": "NA",
                "close_or_value": "NA",
                "signal": "NA",
                "z": "NA",
                "position_in_band": "NA",
                "dist_to_lower": "NA",
                "dist_to_upper": "NA",
                "kind": kind,
            }

        full = os.path.join(base_dir, path)
        try:
            obj = _load_one(full)
        except Exception as e:
            errors[kind] = f"READ_ERROR:{type(e).__name__}"
            return {
                "data_date": "NA",
                "close": "NA",
                "value": "NA",
                "close_or_value": "NA",
                "signal": "NA",
                "z": "NA",
                "position_in_band": "NA",
                "dist_to_lower": "NA",
                "dist_to_upper": "NA",
                "kind": kind,
            }

        fb = report_fallback_all.get(kind.upper(), {})
        block, dbg = _extract_symbol_block(obj, kind, report_fallback=fb)

        # If still nothing parsed, surface debug in errors (display-only)
        all_na = all(block.get(k) == "NA" for k in ["data_date", "close_or_value", "signal", "z", "position_in_band", "dist_to_lower", "dist_to_upper"])
        if all_na and errors.get(kind, "NA") == "NA":
            errors[kind] = f"PARSE_NO_FIELDS:{dbg.get('candidate_path','NA')}/score={dbg.get('candidate_score','NA')}"
        elif errors.get(kind, "NA") == "NA":
            # keep NA; but if some key paths are NA, still okay
            pass

        return block

    out["QQQ"] = _load_and_extract("QQQ", p_qqq)
    out["VXN"] = _load_and_extract("VXN", p_vxn)
    out["NDX"] = _load_and_extract("NDX", p_ndx)

    return "OK", out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market-in", default="dashboard/dashboard_latest.json")
    ap.add_argument("--fred-in", default="dashboard_fred_cache/dashboard_latest.json")
    ap.add_argument("--twmargin-in", default="taiwan_margin_cache/latest.json")
    ap.add_argument("--roll25-in", default="roll25_cache/latest_report.json")
    ap.add_argument("--fx-in", default="fx_cache/latest.json")
    ap.add_argument("--fx-history", default="fx_cache/history.json")

    # ✅ optional dashboards (display-only; do not affect calculations)
    ap.add_argument("--inflation-in", default="inflation_realrate_cache/dashboard_latest.json")
    ap.add_argument("--assetproxy-in", default="asset_proxy_cache/dashboard_latest.json")

    # ✅ NEW optional dir (display-only; do not affect calculations)
    ap.add_argument("--nasdaqbb-dir", default="nasdaq_bb_cache")

    ap.add_argument("--out", default="unified_dashboard/latest.json")
    ap.add_argument("--roll25-vol-n", type=int, default=int(os.getenv("ROLL25_VOL_N", "10")))
    ap.add_argument("--roll25-dd-n", type=int, default=int(os.getenv("ROLL25_DD_N", "10")))
    args = ap.parse_args()

    generated_at_utc = _now_utc_z()
    run_day_tag = _infer_run_day_tag_from_utc_z(generated_at_utc)

    def _load_or_fail(path: str) -> Tuple[str, Any]:
        try:
            return "OK", _load_json(path)
        except Exception as e:
            return f"ERROR: {e}", None

    market_status, market_obj = _load_or_fail(args.market_in)
    fred_status, fred_obj = _load_or_fail(args.fred_in)
    twm_status, twm_obj = _load_or_fail(args.twmargin_in)
    roll_status, roll_obj = _load_or_fail(args.roll25_in)
    fx_status, fx_obj = _load_or_fail(args.fx_in)

    # ✅ optional loads (never break unified)
    infl_status, infl_obj = _load_optional(args.inflation_in)
    ap_status, ap_obj = _load_optional(args.assetproxy_in)

    # ✅ optional nasdaq bb dir load (never break unified)
    nbb_status, nbb_obj = _load_nasdaq_bb_cache_dir(args.nasdaqbb_dir)

    # roll25 derived
    roll25_derived: Dict[str, Any] = {"status": "NA"}
    roll25_core: Dict[str, Any] = {}
    if roll_status == "OK" and isinstance(roll_obj, dict):
        closes_newest = _extract_roll25_closes(roll_obj)
        vol_pct, vol_pts = _realized_vol_annualized_pct(closes_newest, args.roll25_vol_n)
        dd_pct, dd_pts = _max_drawdown_pct(closes_newest, args.roll25_dd_n)

        lookback_actual = roll_obj.get("lookback_n_actual")
        lookback_target = _extract_lookback_target_from_roll25_report(roll_obj)

        confidence = "OK"
        if not isinstance(lookback_actual, int):
            confidence = "DOWNGRADED"
        elif lookback_target is None:
            confidence = "DOWNGRADED"
        elif lookback_actual < lookback_target:
            confidence = "DOWNGRADED"

        roll25_derived = {
            "status": "OK",
            "params": {"vol_n": args.roll25_vol_n, "dd_n": args.roll25_dd_n},
            "realized_vol_N_annualized_pct": vol_pct,
            "realized_vol_points_used": vol_pts,
            "max_drawdown_N_pct": dd_pct,
            "max_drawdown_points_used": dd_pts,
            "confidence": confidence,
            "notes": [
                "Realized vol uses log returns, sample std (ddof=1), annualized by sqrt(252).",
                "Max drawdown computed on chronological closes within N points.",
            ],
            "lookback": {
                "LookbackNActual": lookback_actual if isinstance(lookback_actual, int) else "NA",
                "LookbackNTarget": lookback_target if isinstance(lookback_target, int) else "NA",
            },
        }

        used_date = _extract_useddate_from_roll25_report(roll_obj)
        used_date_selection_tag = roll_obj.get("tag") if isinstance(roll_obj.get("tag"), str) else "NA"
        tag_legacy = used_date_selection_tag
        used_date_status, used_date_status_dbg = _compute_used_date_status_v1(roll_obj)

        nums = roll_obj.get("numbers") if isinstance(roll_obj.get("numbers"), dict) else {}
        sigs = roll_obj.get("signal") if isinstance(roll_obj.get("signal"), dict) else {}

        roll25_core = {
            "UsedDate": used_date or "NA",
            "run_day_tag": run_day_tag,
            "used_date_status": used_date_status,
            "used_date_status_dbg": used_date_status_dbg,
            "used_date_selection_tag": used_date_selection_tag,
            "tag_legacy": tag_legacy,
            "risk_level": roll_obj.get("risk_level") if isinstance(roll_obj.get("risk_level"), str) else "NA",
            "turnover_twd": nums.get("TradeValue"),
            "turnover_unit": "TWD",
            "close": nums.get("Close"),
            "pct_change": nums.get("PctChange"),
            "amplitude_pct": nums.get("AmplitudePct"),
            "volume_multiplier": nums.get("VolumeMultiplier"),
            "vol_multiplier": nums.get("VolMultiplier"),
            "LookbackNTarget": _extract_lookback_target_from_roll25_report(roll_obj),
            "LookbackNActual": roll_obj.get("lookback_n_actual") if isinstance(roll_obj.get("lookback_n_actual"), int) else None,
            "signals": {
                "DownDay": sigs.get("DownDay"),
                "VolumeAmplified": sigs.get("VolumeAmplified"),
                "VolAmplified": sigs.get("VolAmplified"),
                "NewLow_N": sigs.get("NewLow_N"),
                "ConsecutiveBreak": sigs.get("ConsecutiveBreak"),
                "OhlcMissing": sigs.get("OhlcMissing"),
            },
            "ohlc_status": roll_obj.get("ohlc_status") if isinstance(roll_obj.get("ohlc_status"), str) else "NA",
            "freshness_ok": roll_obj.get("freshness_ok") if isinstance(roll_obj.get("freshness_ok"), bool) else "NA",
        }

    # fx derived
    fx_derived: Dict[str, Any] = {"status": "NA"}
    fx_hist_items = _load_fx_history(args.fx_history)
    if fx_status == "OK" and isinstance(fx_obj, dict):
        data_date = fx_obj.get("data_date")
        mid = _safe_get(fx_obj, "usd_twd", "mid")
        spot_buy = _safe_get(fx_obj, "usd_twd", "spot_buy")
        spot_sell = _safe_get(fx_obj, "usd_twd", "spot_sell")
        src_url = fx_obj.get("source_url")

        mom = _fx_ret1_and_chg5(fx_hist_items)
        sig = _fx_signal_rule_v1(mom.get("ret1_pct"), mom.get("chg_5d_pct"), mom.get("points", 0))

        dir_label = "NA"
        if isinstance(mom.get("ret1_pct"), (int, float)):
            dir_label = "TWD_STRONG" if mom["ret1_pct"] < 0 else "TWD_WEAK"

        fx_derived = {
            "status": "OK",
            "source": fx_obj.get("source"),
            "source_url": src_url,
            "data_date": data_date,
            "usd_twd": {"spot_buy": spot_buy, "spot_sell": spot_sell, "mid": mid},
            "momentum": mom,
            "dir": dir_label,
            **sig,
        }

    # cross_module (Margin×Roll25MarketHeat)
    cross_module: Dict[str, Any] = {}
    if twm_status == "OK" and isinstance(twm_obj, dict) and roll_status == "OK" and isinstance(roll_obj, dict):
        ms = _get_margin_signal_prefer_structured(twm_obj)
        r25 = _roll25_heated_rule_v2_split(roll_obj)
        align = _date_alignment(twm_obj, roll_obj)

        heated_market = bool(r25.get("roll25_heated_market", False))
        data_quality_issue = bool(r25.get("roll25_data_quality_issue", False))
        cons = _consistency_rule_v1(str(ms.get("margin_signal", "NA")), heated_market)

        cross_module = {
            "margin_signal": ms.get("margin_signal", "NA"),
            "margin_signal_source": ms.get("margin_signal_source", "NA"),
            "margin_rationale": ms.get("margin_rationale", {"method": "NA"}),
            "roll25_heated_market": heated_market,
            "roll25_data_quality_issue": data_quality_issue,
            "roll25_heated": bool(r25.get("roll25_heated", False)),
            "roll25_confidence": r25.get("roll25_confidence", "NA"),
            "consistency": cons.get("consistency", "NA"),
            "rationale": {
                "consistency_rule": cons.get("consistency_rule", "NA"),
                "roll25_rationale": r25.get("roll25_rationale", {"rule_market": "NA", "rule_data_quality": "NA"}),
                "date_alignment": align,
                "note": (
                    "consistency uses roll25_heated_market only; "
                    "roll25_data_quality_issue does NOT flip consistency, but should downgrade trust in interpretation."
                ),
            },
        }

    unified = {
        "schema_version": "unified_dashboard_latest_v1",
        "generated_at_utc": generated_at_utc,
        "run_day_tag": run_day_tag,
        "inputs": {
            "market_in": args.market_in,
            "fred_in": args.fred_in,
            "twmargin_in": args.twmargin_in,
            "roll25_in": args.roll25_in,
            "fx_in": args.fx_in,
            "fx_history": args.fx_history,
            # ✅ optional
            "inflation_in": args.inflation_in,
            "assetproxy_in": args.assetproxy_in,
            # ✅ NEW optional
            "nasdaqbb_dir": args.nasdaqbb_dir,
        },
        "modules": {
            "market_cache": {
                "status": "OK" if market_status == "OK" else market_status,
                "dashboard_latest": market_obj,
            },
            "fred_cache": {
                "status": "OK" if fred_status == "OK" else fred_status,
                "dashboard_latest": fred_obj,
            },
            "roll25_cache": {
                "status": "OK" if roll_status == "OK" else roll_status,
                "latest_report": roll_obj,
                "core": roll25_core if roll25_core else None,
                "derived": roll25_derived,
            },
            "taiwan_margin_financing": {
                "status": "OK" if twm_status == "OK" else twm_status,
                "latest": twm_obj,
                "cross_module": cross_module if cross_module else None,
            },
            "fx_usdtwd": {
                "status": "OK" if fx_status == "OK" else fx_status,
                "latest": fx_obj,
                "derived": fx_derived,
            },

            # ✅ optional modules (display-only)
            "inflation_realrate_cache": {
                "status": "OK" if infl_status == "OK" else infl_status,
                "dashboard_latest": infl_obj if infl_status == "OK" else None,
            },
            "asset_proxy_cache": {
                "status": "OK" if ap_status == "OK" else ap_status,
                "dashboard_latest": ap_obj if ap_status == "OK" else None,
            },

            # ✅ NEW optional module (display-only)
            "nasdaq_bb_cache": {
                "status": "OK" if nbb_status == "OK" else nbb_status,
                "note": "display-only; not used for positioning/mode/cross_module",
                "dashboard_latest": nbb_obj if nbb_status == "OK" else nbb_obj,
            },
        },
        "audit_notes": [
            "Roll25 derived metrics are computed from roll25_cache/latest_report.json only (no external fetch).",
            "FX derived metrics are computed from fx_cache/history.json (local) + fx_cache/latest.json (local).",
            "Margin×Roll25 cross_module is computed deterministically from twmargin latest + roll25 latest only (no external fetch).",
            "Signal rules are deterministic; missing data => NA and confidence downgrade (no guessing).",
            "Roll25 semantics: run_day_tag derived from unified builder run date (Asia/Taipei); used_date_status computed deterministically from roll25 latest_report; used_date_selection_tag (tag_legacy) preserves roll25 latest_report.tag.",
            "Roll25 split: roll25_heated_market (market behavior only) and roll25_data_quality_issue (data quality only).",
            "Consistency uses roll25_heated_market only; data quality issue does not force DIVERGENCE/CONVERGENCE flip, but should downgrade interpretation confidence.",
            "Backward compatibility: roll25_heated (legacy) == roll25_heated_market.",
            "Optional modules inflation_realrate_cache / asset_proxy_cache are merged for display only; they do not affect positioning matrix or cross_module.",
            "Optional module nasdaq_bb_cache is merged for display only; it does not affect positioning matrix or cross_module.",
        ],
    }

    # avoid emitting null nodes for cleanliness
    if unified["modules"]["taiwan_margin_financing"].get("cross_module") is None:
        unified["modules"]["taiwan_margin_financing"].pop("cross_module", None)
    if unified["modules"]["roll25_cache"].get("core") is None:
        unified["modules"]["roll25_cache"].pop("core", None)

    _dump_json(args.out, unified)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
