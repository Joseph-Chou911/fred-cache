#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_dashboard.py
- Merge two feeds (market_cache + cache) into one markdown dashboard.
- Audit-first: no guessing; missing -> NA.
- History parser is multi-shape compatible:
    * list[dict] rows with series_id/data_date/value
    * dict series-map with:
        A) list[dict] points: [{"data_date":..., "value":...}, ...]
        B) list[pair] points: [["YYYY-MM-DD", v], ...]
        C) dict columnar: {"data_date":[...], "value":[...]} (or variants)
        D) dict points: {"points":[["YYYY-MM-DD", v], ...]}
- Computes z60, p252, z_delta60, p_delta252, ret1_pct from history using:
    ddof=0, P = count(x<=latest)/n*100
- Signal rules (current "B" style in your latest output):
    Extreme: |Z60|>=2 => WATCH; |Z60|>=2.5 => ALERT
    Long Extreme: P252>=95 or <=5 => INFO (only if no |Z60|>=2 and no Jump)
                 P252<=2 => ALERT
    Jump: ONLY |ZΔ60|>=0.75 => WATCH (unless already ALERT)
    Near: within 10% of thresholds for ZΔ60 / PΔ252 / ret1%
    PΔ252>=15 and |ret1%|>=2 => INFO tags only (no escalation)
    StaleData: if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA
- PrevSignal/StreakWA persist via dashboard_state.json

Usage example:
  python scripts/render_dashboard.py \
    --feed market_cache \
      --stats market_cache/stats_latest.json \
      --history market_cache/history_lite.json \
      --dq market_cache/dq_state.json \
      --asof-field as_of_ts \
    --feed cache \
      --stats cache/stats_latest.json \
      --history cache/history_lite.json \
      --dq cache/dq_state.json \
      --asof-field as_of_ts \
    --state-file dashboard_state.json \
    --out dashboard.md

If --out omitted, prints to stdout.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Helpers: parsing / formatting
# ----------------------------

NA = "NA"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    # Always print UTC Z for RUN_TS
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    # keep microseconds for audit trace like your output
    return dt.isoformat().replace("+00:00", "+00:00")


def _parse_iso_datetime(s: Any) -> Optional[datetime]:
    if not isinstance(s, str) or not s.strip():
        return None
    ss = s.strip()
    try:
        # Accept "Z" or "+00:00"
        if ss.endswith("Z"):
            return datetime.fromisoformat(ss[:-1]).replace(tzinfo=timezone.utc)
        # Some feeds use "2026-01-18T14:57:27+08:00"
        return datetime.fromisoformat(ss)
    except Exception:
        return None


def _parse_date(s: Any) -> Optional[date]:
    if s is None:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    if not isinstance(s, str):
        s = str(s)
    ss = s.strip()
    if not ss:
        return None
    # Expect YYYY-MM-DD
    try:
        return datetime.strptime(ss[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        # NaN guard
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        # Some sources use "."
        try:
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None
    return None


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _safe_get(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return None


# ----------------------------
# History parsing (multi-shape)
# ----------------------------

def _unwrap_history_root(history_obj: Any) -> Tuple[Any, str]:
    """
    Return (root, hint):
      - If dict and contains "series": unwrap to obj["series"] with hint "series"
      - Else: root is history_obj with hint "root"
    """
    if isinstance(history_obj, dict) and "series" in history_obj:
        return history_obj.get("series"), "series"
    return history_obj, "root"


def _looks_like_series_map_dict(d: Dict[str, Any]) -> bool:
    """
    Broader heuristic:
    dict where values look like one of:
      A) list[dict] with data_date/value (or date/value variants)
      B) list[list/tuple] pairs [date, value]
      C) dict with columnar arrays: {"data_date":[...], "value":[...]} (or variants)
      D) dict with "points": [[date, value], ...]
    """
    if not d:
        return False

    def _is_date_key(k: str) -> bool:
        return k in {"data_date", "date", "Date", "dt", "d"}

    def _is_value_key(k: str) -> bool:
        return k in {"value", "Value", "close", "Close", "v"}

    checked = 0
    good = 0

    for _, v in d.items():
        checked += 1
        ok = False

        if isinstance(v, list) and v:
            # A) list[dict]
            if isinstance(v[0], dict):
                kk = set(v[0].keys())
                if any(_is_date_key(k) for k in kk) and any(_is_value_key(k) for k in kk):
                    ok = True
            # B) list[pair]
            elif isinstance(v[0], (list, tuple)) and len(v[0]) >= 2:
                ok = True

        elif isinstance(v, dict) and v:
            # C) columnar
            keys = set(v.keys())
            if any(_is_date_key(k) for k in keys) and any(_is_value_key(k) for k in keys):
                d_arr = _safe_get(v, ["data_date", "date", "Date", "dt", "d"])
                v_arr = _safe_get(v, ["value", "Value", "close", "Close", "v"])
                if isinstance(d_arr, list) and isinstance(v_arr, list):
                    ok = True
            # D) points
            if not ok and isinstance(v.get("points"), list) and v["points"]:
                p0 = v["points"][0]
                if isinstance(p0, (list, tuple)) and len(p0) >= 2:
                    ok = True

        if ok:
            good += 1
        if checked >= 5:
            break

    return good >= 1


def _coerce_points_for_one_series(rows: Any) -> List[Tuple[date, float]]:
    """
    Accept multiple shapes and return sorted [(date, value), ...]
    Shapes:
      1) list[dict] with keys in {data_date/date/Date/d} and {value/close/v}
      2) list[pair] => [date, value]
      3) dict columnar: {data_date:[...], value:[...]} (or variants)
      4) dict with points: {"points":[[date,value], ...]}
    """
    pts: List[Tuple[date, float]] = []

    def get_date(dct: Dict[str, Any]) -> Optional[date]:
        for k in ("data_date", "date", "Date", "dt", "d"):
            if k in dct:
                return _parse_date(dct.get(k))
        return None

    def get_val(dct: Dict[str, Any]) -> Optional[float]:
        for k in ("value", "Value", "close", "Close", "v"):
            if k in dct:
                return _to_float(dct.get(k))
        return None

    # 4) dict with points
    if isinstance(rows, dict) and isinstance(rows.get("points"), list):
        rows = rows["points"]

    # 3) columnar dict
    if isinstance(rows, dict):
        d_arr = None
        v_arr = None
        for k in ("data_date", "date", "Date", "dt", "d"):
            if isinstance(rows.get(k), list):
                d_arr = rows.get(k)
                break
        for k in ("value", "Value", "close", "Close", "v"):
            if isinstance(rows.get(k), list):
                v_arr = rows.get(k)
                break
        if d_arr is not None and v_arr is not None:
            n = min(len(d_arr), len(v_arr))
            for i in range(n):
                dd = _parse_date(d_arr[i] if isinstance(d_arr[i], str) else str(d_arr[i]))
                vv = _to_float(v_arr[i])
                if dd is None or vv is None:
                    continue
                pts.append((dd, vv))
            pts.sort(key=lambda t: t[0])
            return pts

    # 1) list[dict] or 2) list[pair]
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict):
                dd = get_date(r)
                vv = get_val(r)
                if dd is None or vv is None:
                    continue
                pts.append((dd, vv))
            elif isinstance(r, (list, tuple)) and len(r) >= 2:
                dd = _parse_date(str(r[0]))
                vv = _to_float(r[1])
                if dd is None or vv is None:
                    continue
                pts.append((dd, vv))

    pts.sort(key=lambda t: t[0])
    return pts


def _history_to_series_map(history_obj: Any) -> Tuple[Dict[str, List[Tuple[date, float]]], str, str]:
    """
    Support schemas:
    A) dict series-map (many variants, see _coerce_points_for_one_series)
    B) list rows: [{"series_id":..., "data_date":..., "value":...}, ...]
    Plus wrappers, auto-detected by _unwrap_history_root.
    """
    root, hint = _unwrap_history_root(history_obj)

    out: Dict[str, List[Tuple[date, float]]] = {}
    schema = "unknown"

    # A) dict series-map variants
    if isinstance(root, dict):
        schema = "dict"
        for sid, rows in root.items():
            if not isinstance(sid, str) or not sid:
                continue
            pts = _coerce_points_for_one_series(rows)
            if pts:
                out[sid] = pts
        return out, schema, hint

    # B) list of rows
    if isinstance(root, list):
        schema = "list"
        for r in root:
            if not isinstance(r, dict):
                continue
            sid = r.get("series_id")
            if not isinstance(sid, str) or not sid:
                continue
            dd = _parse_date(r.get("data_date") or r.get("date") or r.get("Date") or r.get("d"))
            vv = _to_float(r.get("value") or r.get("Value") or r.get("close") or r.get("Close") or r.get("v"))
            if dd is None or vv is None:
                continue
            out.setdefault(sid, []).append((dd, vv))
        for sid in list(out.keys()):
            out[sid].sort(key=lambda t: t[0])
        return out, schema, hint

    return out, schema, hint


# ----------------------------
# Rolling stats from history
# ----------------------------

def _mean(vals: List[float]) -> float:
    return sum(vals) / float(len(vals))


def _std_ddof0(vals: List[float]) -> float:
    if len(vals) <= 1:
        return 0.0
    m = _mean(vals)
    var = sum((x - m) ** 2 for x in vals) / float(len(vals))
    return math.sqrt(var)


def _percentile_le(vals: List[float], latest: float) -> float:
    # P = count(x<=latest)/n*100
    n = len(vals)
    if n == 0:
        return float("nan")
    c = sum(1 for x in vals if x <= latest)
    return (c / float(n)) * 100.0


def _rolling_window(values: List[float], end_idx: int, n: int) -> Optional[List[float]]:
    # last n points ending at end_idx inclusive
    if end_idx < 0:
        return None
    start = end_idx - n + 1
    if start < 0:
        return None
    w = values[start:end_idx + 1]
    if len(w) != n:
        return None
    return w


def _compute_z_and_p(values: List[float], end_idx: int, w60: int = 60, w252: int = 252) -> Dict[str, Optional[float]]:
    """
    Compute z60 and p252 at the given end_idx.
    z60 uses last 60 points ending at end_idx; p252 uses last 252.
    """
    out: Dict[str, Optional[float]] = {"z60": None, "p252": None}

    w = _rolling_window(values, end_idx, w60)
    if w is not None:
        latest = values[end_idx]
        sd = _std_ddof0(w)
        if sd > 0:
            out["z60"] = (latest - _mean(w)) / sd
        else:
            out["z60"] = 0.0  # constant window -> z=0 (audit: defined behavior)

    w2 = _rolling_window(values, end_idx, w252)
    if w2 is not None:
        latest = values[end_idx]
        out["p252"] = _percentile_le(w2, latest)

    return out


def _compute_ret1_pct(values: List[float], end_idx: int) -> Optional[float]:
    if end_idx <= 0:
        return None
    prev = values[end_idx - 1]
    cur = values[end_idx]
    if prev == 0:
        return None
    return ((cur - prev) / abs(prev)) * 100.0


# ----------------------------
# Signal logic
# ----------------------------

TH_Z_EXTREME_WATCH = 2.0
TH_Z_EXTREME_ALERT = 2.5
TH_ZD_JUMP = 0.75
TH_PD_INFO = 15.0
TH_RET_INFO = 2.0

NEAR_PCT = 0.10  # within 10% of threshold


def _near(th: float, x: Optional[float]) -> bool:
    if x is None:
        return False
    return abs(x) >= (1.0 - NEAR_PCT) * th and abs(x) < th


def _fmt_f(x: Optional[float], nd: int = 6) -> str:
    if x is None:
        return NA
    return f"{x:.{nd}f}".rstrip("0").rstrip(".") if nd > 0 else str(int(round(x)))


def _signal_for_row(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
) -> Tuple[str, List[str], List[str], str]:
    """
    Return (Signal, Tags, NearFlags, Reason)
    Signal: ALERT/WATCH/INFO/NONE
    """
    tags: List[str] = []
    near_flags: List[str] = []
    reasons: List[str] = []

    # Extreme z
    if z60 is not None and abs(z60) >= TH_Z_EXTREME_WATCH:
        tags.append("EXTREME_Z")
        reasons.append("|Z60|>=2")
        sig = "WATCH"
        if abs(z60) >= TH_Z_EXTREME_ALERT:
            sig = "ALERT"
            reasons[-1] = "|Z60|>=2.5"
    else:
        sig = "NONE"

    # Jump (ONLY ZΔ60)
    if z_delta60 is not None and abs(z_delta60) >= TH_ZD_JUMP:
        tags.append("JUMP_ZD")
        reasons.append("|ZΔ60|>=0.75")
        if sig == "NONE":
            sig = "WATCH"

    # Long extreme by p252 (INFO only, unless very extreme low)
    if p252 is not None:
        if p252 <= 2.0:
            # This is severe
            if sig != "ALERT":
                sig = "ALERT"
            if "LONG_EXTREME" not in tags:
                tags.append("LONG_EXTREME")
            reasons.append("P252<=2")
        elif p252 >= 95.0 or p252 <= 5.0:
            # Only INFO if no z-extreme and no jump
            tags.append("LONG_EXTREME")
            if (z60 is None or abs(z60) < TH_Z_EXTREME_WATCH) and (z_delta60 is None or abs(z_delta60) < TH_ZD_JUMP):
                if sig == "NONE":
                    sig = "INFO"
                reasons.append("P252>=95 or <=5")
            else:
                # keep existing (WATCH/ALERT)
                if "P252>=95 or <=5" not in reasons:
                    reasons.append("P252>=95 or <=5")

    # Near flags
    if _near(TH_ZD_JUMP, z_delta60):
        near_flags.append("NEAR:ZΔ60")

    # Reason text
    reason = ";".join(reasons) if reasons else "NA"
    return sig, tags, near_flags, reason


# ----------------------------
# Feed / state models
# ----------------------------

@dataclass
class FeedSpec:
    name: str
    stats_path: str
    history_path: str
    dq_path: Optional[str]
    asof_field: str  # e.g. as_of_ts


def _load_dq_map(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    try:
        obj = _read_json(path)
        if isinstance(obj, dict) and isinstance(obj.get("series"), dict):
            # allow {"series":{"SP500":{"dq":"OK"}...}} or {"series":{"SP500":"OK"}...}
            out: Dict[str, str] = {}
            for sid, v in obj["series"].items():
                if isinstance(v, str):
                    out[sid] = v
                elif isinstance(v, dict):
                    dq = v.get("dq") or v.get("state") or v.get("status")
                    if isinstance(dq, str):
                        out[sid] = dq
            return out
        return {}
    except Exception:
        return {}


def _load_state(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {"version": 1, "rows": {}}
    try:
        obj = _read_json(path)
        if isinstance(obj, dict) and isinstance(obj.get("rows"), dict):
            return obj
    except Exception:
        pass
    return {"version": 1, "rows": {}}


def _save_state(path: str, state: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _state_key(feed: str, series: str) -> str:
    return f"{feed}::{series}"


def _update_streak(state_rows: Dict[str, Any], feed: str, series: str, signal: str) -> Tuple[str, int]:
    """
    Returns (prev_signal, new_streak)
    """
    k = _state_key(feed, series)
    prev = state_rows.get(k, {})
    prev_signal = prev.get("signal", "NONE") if isinstance(prev, dict) else "NONE"
    prev_streak = prev.get("streak", 0) if isinstance(prev, dict) else 0

    if signal == prev_signal:
        new_streak = int(prev_streak) + 1
    else:
        new_streak = 1 if signal != "NONE" else 0

    state_rows[k] = {"signal": signal, "streak": new_streak}
    return prev_signal, new_streak


# ----------------------------
# Rendering
# ----------------------------

def _md_escape(s: str) -> str:
    # minimal; avoid breaking table
    return s.replace("|", "\\|").replace("\n", " ")


def _render_dashboard(
    feeds: List[FeedSpec],
    stale_hours_default: float,
    stale_overrides: Dict[str, float],
    data_lag_default_days: int,
    data_lag_overrides_days: Dict[str, int],
    state_file: str,
    script_fingerprint: str,
) -> str:
    run_ts = _utc_now()

    state = _load_state(state_file) if state_file else {"version": 1, "rows": {}}
    state_rows = state.get("rows", {}) if isinstance(state.get("rows"), dict) else {}

    # Collect feed metadata for header
    header_lines: List[str] = []
    header_lines.append("# Risk Dashboard (merged)\n")
    header_lines.append(f"- SCRIPT_FINGERPRINT: `{script_fingerprint}`")
    header_lines.append(f"- RUN_TS_UTC: `{_iso_z(run_ts)}`")
    header_lines.append(f"- stale_hours_default: `{stale_hours_default}`")
    header_lines.append(f"- stale_overrides: `{json.dumps(stale_overrides, ensure_ascii=False)}`")
    header_lines.append(f"- data_lag_default_days: `{data_lag_default_days}`")
    header_lines.append(f"- data_lag_overrides_days: `{json.dumps(data_lag_overrides_days, ensure_ascii=False)}`")

    # Output table rows
    rows_out: List[Dict[str, Any]] = []

    # signal_rules summary (keep as a single line, like your output)
    signal_rules = (
        "Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), "
        "P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); "
        "Jump(ONLY |ZΔ60|>=0.75); "
        "Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); "
        "PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); "
        "StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)"
    )

    # Process each feed
    for idx, fs in enumerate(feeds, start=1):
        stats = _read_json(fs.stats_path)
        hist_obj = _read_json(fs.history_path)

        dq_map = _load_dq_map(fs.dq_path)

        # feed meta
        feed_asof = _parse_iso_datetime(stats.get(fs.asof_field))
        feed_generated = _parse_iso_datetime(stats.get("generated_at_utc"))
        feed_script = stats.get("script_version") or _safe_get(stats.get("stats_policy", {}), ["script_version"]) or NA

        # history parse
        series_map, hist_schema, hist_hint = _history_to_series_map(hist_obj)

        header_lines.append(f"- FEED{idx}.stats: `{fs.stats_path}`")
        header_lines.append(f"- FEED{idx}.history: `{fs.history_path}`")
        header_lines.append(f"- FEED{idx}.history_schema: `{hist_schema}`")
        header_lines.append(f"- FEED{idx}.history_unwrap: `{hist_hint}`")
        header_lines.append(f"- FEED{idx}.history_series_count: `{len(series_map)}`")
        header_lines.append(f"- FEED{idx}.as_of_ts: `{stats.get(fs.asof_field, NA)}`")
        header_lines.append(f"- FEED{idx}.generated_at_utc: `{stats.get('generated_at_utc', NA)}`")
        header_lines.append(f"- FEED{idx}.script_version: `{feed_script}`")

        # iterate series in stats
        sdict = stats.get("series", {})
        if not isinstance(sdict, dict):
            continue

        for sid, sobj in sdict.items():
            if not isinstance(sid, str) or not isinstance(sobj, dict):
                continue

            latest = sobj.get("latest", {})
            metrics = sobj.get("metrics", {})
            if not isinstance(latest, dict):
                latest = {}
            if not isinstance(metrics, dict):
                metrics = {}

            # data_date/value/source/as_of_ts
            data_date = _parse_date(latest.get("data_date"))
            val = _to_float(latest.get("value"))
            source_url = latest.get("source_url") or latest.get("source") or "DERIVED"
            as_of_ts = latest.get("as_of_ts") or stats.get(fs.asof_field) or NA

            # prefer stats' z60/p252 if available; else compute from history latest
            z60_stats = _to_float(metrics.get("z60"))
            p252_stats = _to_float(metrics.get("p252"))

            # compute from history if possible (also for deltas)
            pts = series_map.get(sid, [])
            values = [v for _, v in pts]
            # find end_idx aligned with stats data_date if possible; else last
            end_idx = None
            if data_date is not None and pts:
                for i in range(len(pts) - 1, -1, -1):
                    if pts[i][0] == data_date:
                        end_idx = i
                        break
            if end_idx is None:
                end_idx = len(values) - 1 if values else -1

            z_p_now = _compute_z_and_p(values, end_idx) if end_idx >= 0 else {"z60": None, "p252": None}
            z60 = z60_stats if z60_stats is not None else z_p_now["z60"]
            p252 = p252_stats if p252_stats is not None else z_p_now["p252"]

            # prev metrics for deltas (computed from history)
            z_delta60 = None
            p_delta252 = None
            if end_idx is not None and end_idx >= 1 and values:
                z_p_prev = _compute_z_and_p(values, end_idx - 1)
                if z60 is not None and z_p_prev["z60"] is not None:
                    z_delta60 = z60 - z_p_prev["z60"]
                if p252 is not None and z_p_prev["p252"] is not None:
                    p_delta252 = p252 - z_p_prev["p252"]

            ret1_pct = _compute_ret1_pct(values, end_idx) if end_idx is not None and end_idx >= 1 else None

            # INFO tags (no escalation)
            info_tags: List[str] = []
            if p_delta252 is not None and abs(p_delta252) >= TH_PD_INFO:
                info_tags.append("INFO_PΔ")
            if ret1_pct is not None and abs(ret1_pct) >= TH_RET_INFO:
                info_tags.append("INFO_RET")

            # Signal / tags / near / reason
            sig, tags, near_flags, reason = _signal_for_row(z60, p252, z_delta60)
            # add INFO-only tags
            tags.extend(info_tags)
            # near for p_delta252, ret1_pct thresholds (for display only)
            if _near(TH_PD_INFO, p_delta252):
                near_flags.append("NEAR:PΔ252")
            if _near(TH_RET_INFO, ret1_pct):
                near_flags.append("NEAR:ret1%")

            # DQ
            dq = dq_map.get(sid, "OK")

            # age_h: run_ts - feed_asof (hours)
            age_h = None
            if feed_asof is not None:
                delta = (run_ts - feed_asof.astimezone(timezone.utc)).total_seconds()
                age_h = delta / 3600.0

            # stale_h: per-series override else default
            stale_h = float(stale_overrides.get(sid, stale_hours_default))

            # data_lag_d: RUN_TS_UTC.date - data_date
            data_lag_d = None
            if data_date is not None:
                data_lag_d = (run_ts.date() - data_date).days

            # data_lag_thr_d override else default
            lag_thr = int(data_lag_overrides_days.get(sid, data_lag_default_days))

            # StaleData clamp
            if data_lag_d is not None and data_lag_d > lag_thr:
                if "STALE_DATA" not in tags:
                    tags.append("STALE_DATA")
                # clamp to INFO (even if WATCH/ALERT)
                sig = "INFO"
                reason = f"STALE_DATA(lag_d={data_lag_d}>thr_d={lag_thr})"

            # PrevSignal + Streak
            prev_signal, streak = _update_streak(state_rows, fs.name, sid, sig)

            rows_out.append({
                "Signal": sig,
                "Tag": ",".join(tags) if tags else NA,
                "Near": ",".join(near_flags) if near_flags else NA,
                "PrevSignal": prev_signal,
                "StreakWA": streak,
                "Feed": fs.name,
                "Series": sid,
                "DQ": dq,
                "age_h": age_h,
                "stale_h": stale_h,
                "data_lag_d": data_lag_d,
                "data_lag_thr_d": lag_thr,
                "data_date": data_date.isoformat() if data_date else NA,
                "value": val,
                "z60": z60,
                "p252": p252,
                "z_delta60": z_delta60,
                "p_delta252": p_delta252,
                "ret1_pct": ret1_pct,
                "Reason": reason,
                "Source": source_url,
                "as_of_ts": as_of_ts,
            })

    # persist state
    if state_file:
        state["rows"] = state_rows
        _save_state(state_file, state)

    # sort: ALERT > WATCH > INFO > NONE, then by Feed/Series
    order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows_out.sort(key=lambda r: (order.get(r["Signal"], 9), str(r["Feed"]), str(r["Series"])))

    # Render markdown
    out_lines: List[str] = []
    out_lines.extend(header_lines)
    out_lines.append(f"- signal_rules: `{signal_rules}`\n")

    # Table header (match your latest columns)
    cols = [
        "Signal", "Tag", "Near", "PrevSignal", "StreakWA", "Feed", "Series", "DQ",
        "age_h", "stale_h", "data_lag_d", "data_lag_thr_d",
        "data_date", "value", "z60", "p252", "z_delta60", "p_delta252", "ret1_pct",
        "Reason", "Source", "as_of_ts",
    ]

    out_lines.append("| " + " | ".join(cols) + " |")
    out_lines.append("|" + "|".join(["---"] * len(cols)) + "|")

    for r in rows_out:
        def g(k: str) -> str:
            v = r.get(k)
            if k in {"age_h", "stale_h"}:
                return _fmt_f(v, 2) if isinstance(v, (int, float)) else NA
            if k in {"value", "z60", "p252", "z_delta60", "p_delta252", "ret1_pct"}:
                return _fmt_f(v, 6)
            if k in {"data_lag_d", "data_lag_thr_d", "StreakWA"}:
                return str(v) if v is not None else NA
            return _md_escape(str(v)) if v is not None else NA

        out_lines.append("| " + " | ".join(g(c) for c in cols) + " |")

    out_lines.append("")  # final newline
    return "\n".join(out_lines)


# ----------------------------
# CLI
# ----------------------------

def _parse_kv_json(s: str) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--feed", action="append", default=[], help="Feed name (repeatable).")
    p.add_argument("--stats", action="append", default=[], help="Stats JSON path (repeatable).")
    p.add_argument("--history", action="append", default=[], help="History JSON path (repeatable).")
    p.add_argument("--dq", action="append", default=[], help="DQ JSON path (repeatable, can be empty).")
    p.add_argument("--asof-field", action="append", default=[], help="as_of field key per feed (repeatable).")

    p.add_argument("--stale-hours-default", type=float, default=36.0)
    p.add_argument("--stale-overrides-json", type=str, default='{"STLFSI4":240.0,"NFCINONFINLEVERAGE":240.0,"BAMLH0A0HYM2":72.0}')
    p.add_argument("--data-lag-default-days", type=int, default=2)
    p.add_argument("--data-lag-overrides-days-json", type=str, default='{"STLFSI4":10,"NFCINONFINLEVERAGE":10,"OFR_FSI":7,"BAMLH0A0HYM2":3,"DGS2":3,"DGS10":3,"VIXCLS":3,"T10Y2Y":3,"T10Y3M":3}')

    p.add_argument("--state-file", type=str, default="dashboard_state.json")
    p.add_argument("--script-fingerprint", type=str, default="render_dashboard_py_fix_history_autodetect_and_staleh_2026-01-18")
    p.add_argument("--out", type=str, default="")

    args = p.parse_args()

    n = len(args.feed)
    if not (len(args.stats) == len(args.history) == n):
        raise SystemExit("ERROR: --feed/--stats/--history must have the same count.")

    # dq/asof-field are optional; pad if missing
    dq_list = list(args.dq)
    while len(dq_list) < n:
        dq_list.append("")
    asof_list = list(args.asof_field)
    while len(asof_list) < n:
        asof_list.append("as_of_ts")

    feeds: List[FeedSpec] = []
    for i in range(n):
        feeds.append(FeedSpec(
            name=args.feed[i],
            stats_path=args.stats[i],
            history_path=args.history[i],
            dq_path=dq_list[i] if dq_list[i] else None,
            asof_field=asof_list[i] if asof_list[i] else "as_of_ts",
        ))

    stale_overrides = _parse_kv_json(args.stale_overrides_json)
    stale_overrides_f: Dict[str, float] = {}
    for k, v in stale_overrides.items():
        if isinstance(k, str):
            vv = _to_float(v)
            if vv is not None:
                stale_overrides_f[k] = float(vv)

    lag_overrides = _parse_kv_json(args.data_lag_overrides_days_json)
    lag_overrides_i: Dict[str, int] = {}
    for k, v in lag_overrides.items():
        if isinstance(k, str):
            if isinstance(v, int):
                lag_overrides_i[k] = v
            else:
                vv = _to_float(v)
                if vv is not None:
                    lag_overrides_i[k] = int(vv)

    md = _render_dashboard(
        feeds=feeds,
        stale_hours_default=float(args.stale_hours_default),
        stale_overrides=stale_overrides_f,
        data_lag_default_days=int(args.data_lag_default_days),
        data_lag_overrides_days=lag_overrides_i,
        state_file=args.state_file,
        script_fingerprint=args.script_fingerprint,
    )

    if args.out:
        _write_text(args.out, md)
    else:
        print(md)


if __name__ == "__main__":
    main()