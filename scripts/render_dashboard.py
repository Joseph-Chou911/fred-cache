#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_dashboard.py (merged)

Purpose:
- Merge two feeds:
  (A) market_cache/stats_latest.json + market_cache/history_lite.json
  (B) cache/stats_latest.json + cache/history_lite.json
- Produce a single Markdown dashboard table with:
  Signal / Tag / Near / PrevSignal / StreakWA / Feed / Series / DQ / age_h / stale_h / data_lag_d / thr / data_date / value / z60 / p252 / z_delta60 / p_delta252 / ret1_pct / Reason / Source / as_of_ts

Design constraints:
- Audit-first: never guess numeric values. If metrics missing -> NA.
- Robust schema autodetect across multiple historical script versions.

Output folder:
- default: dashboard/risk_dashboard_merged.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# -------------------------
# Utilities
# -------------------------

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))

def _to_float(x: Any) -> Optional[float]:
    if _is_number(x):
        return float(x)
    if isinstance(x, str):
        try:
            v = float(x)
            if math.isnan(v):
                return None
            return v
        except Exception:
            return None
    return None

def _fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, str):
        return x
    fx = _to_float(x)
    if fx is None:
        return "NA"
    # keep enough precision for audit; trim trailing zeros
    s = f"{fx:.{nd}f}".rstrip("0").rstrip(".")
    return s if s else "0"

def _fmt_int(x: Any) -> str:
    if x is None:
        return "NA"
    fx = _to_float(x)
    if fx is None:
        return "NA"
    return str(int(round(fx)))

def _parse_date_ymd(s: str) -> Optional[datetime]:
    # expects YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def _parse_iso_dt(s: str) -> Optional[datetime]:
    # supports "Z"
    try:
        ss = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ss)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _hours_between(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 3600.0

def _days_lag(run_ts_utc: datetime, data_date_ymd: str) -> Optional[int]:
    d = _parse_date_ymd(data_date_ymd)
    if not d:
        return None
    # Compare date-only lag in UTC (audit-friendly)
    run_date = run_ts_utc.date()
    data_date = d.date()
    return (run_date - data_date).days

def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        if k not in cur:
            return None
        cur = cur[k]
    return cur

def _pick_first(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return None

# -------------------------
# Feed schema autodetect
# -------------------------

@dataclass
class FeedMeta:
    name: str
    stats_path: str
    history_path: str
    stats_as_of_ts: str
    stats_generated_at_utc: str
    script_version: str
    series_map: Dict[str, Any]
    history_obj: Any

def _extract_script_version(stats_obj: Any) -> str:
    if not isinstance(stats_obj, dict):
        return "NA"

    # common variants
    for k in ["script_version", "scriptVersion", "version"]:
        v = stats_obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # older schema: stats_policy.script_version
    sp = stats_obj.get("stats_policy")
    if isinstance(sp, dict):
        v = sp.get("script_version")
        if isinstance(v, str) and v.strip():
            return v.strip()

    return "NA"

def _extract_ts(stats_obj: Any) -> Tuple[str, str]:
    if not isinstance(stats_obj, dict):
        return ("NA", "NA")
    gen = stats_obj.get("generated_at_utc") or stats_obj.get("generated_at") or stats_obj.get("generatedAt")
    aso = stats_obj.get("as_of_ts") or stats_obj.get("as_of") or stats_obj.get("asOfTs")
    gen_s = gen if isinstance(gen, str) else "NA"
    aso_s = aso if isinstance(aso, str) else "NA"
    return (aso_s, gen_s)

def _extract_series_map(stats_obj: Any) -> Dict[str, Any]:
    """
    Expect stats_obj["series"] as dict; otherwise return {}.
    """
    if isinstance(stats_obj, dict):
        s = stats_obj.get("series")
        if isinstance(s, dict):
            return s
    return {}

def _unwrap_history_series(history_obj: Any) -> Tuple[str, Dict[str, Any]]:
    """
    Supports:
    1) dict with {"series": {...}}  => unwrap=series
    2) list of items each with series_id => unwrap=root(list)
    Returns (unwrap_mode, mapping series_id -> series_history_blob)
    """
    if isinstance(history_obj, dict):
        if isinstance(history_obj.get("series"), dict):
            return ("series", history_obj["series"])
        # sometimes {"data": {"SERIES": ...}}
        if isinstance(history_obj.get("data"), dict):
            return ("data", history_obj["data"])

    if isinstance(history_obj, list):
        m: Dict[str, Any] = {}
        for it in history_obj:
            if isinstance(it, dict):
                sid = it.get("series_id") or it.get("series") or it.get("id")
                if isinstance(sid, str) and sid.strip():
                    m[sid.strip()] = it
        return ("root", m)

    return ("NA", {})

def _extract_history_points(series_history_blob: Any) -> List[Dict[str, Any]]:
    """
    Try to get a list of point dicts from a series history blob.
    Possible keys: history, data, points, observations.
    """
    if not isinstance(series_history_blob, dict):
        return []

    for k in ["history", "data", "points", "observations", "obs"]:
        v = series_history_blob.get(k)
        if isinstance(v, list):
            # ensure dict points
            pts = [p for p in v if isinstance(p, dict)]
            return pts

    # Sometimes structure: {"values":[...]}
    v = series_history_blob.get("values")
    if isinstance(v, list):
        return [p for p in v if isinstance(p, dict)]

    return []

def _point_date_key(p: Dict[str, Any]) -> Optional[str]:
    for k in ["data_date", "date", "dt", "time", "timestamp"]:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            # prefer YYYY-MM-DD
            if len(v.strip()) >= 10 and v.strip()[4] == "-" and v.strip()[7] == "-":
                return v.strip()[:10]
            return v.strip()
    return None

def _sort_points_desc(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # stable sort by date if parsable; otherwise keep original order reversed (assume older->newer)
    def key_fn(p: Dict[str, Any]) -> Tuple[int, str]:
        dk = _point_date_key(p) or ""
        d = _parse_date_ymd(dk) or _parse_iso_dt(dk)
        if d:
            return (0, d.isoformat())
        return (1, dk)

    pts = points[:]
    # if looks already newest-first (first date > last date), keep; else sort
    if len(pts) >= 2:
        d0 = _parse_date_ymd((_point_date_key(pts[0]) or "")[:10])
        d1 = _parse_date_ymd((_point_date_key(pts[-1]) or "")[:10])
        if d0 and d1 and d0 >= d1:
            return pts
    # otherwise sort by key, then reverse to newest first
    pts.sort(key=key_fn)
    pts.reverse()
    return pts

# -------------------------
# Metrics extraction (robust)
# -------------------------

def _extract_latest_blob(series_blob: Any) -> Dict[str, Any]:
    if isinstance(series_blob, dict):
        latest = series_blob.get("latest")
        if isinstance(latest, dict):
            return latest
    return {}

def _extract_dq(series_blob: Any, latest_blob: Dict[str, Any]) -> str:
    """
    Try multiple keys to locate dq state string.
    """
    # candidates may exist on series_blob or latest_blob
    candidates: List[Any] = []

    if isinstance(series_blob, dict):
        candidates.append(series_blob.get("dq"))
        candidates.append(series_blob.get("dq_state"))
        candidates.append(series_blob.get("dqState"))
        candidates.append(series_blob.get("dq_status"))

    candidates.append(latest_blob.get("dq"))
    candidates.append(latest_blob.get("dq_state"))
    candidates.append(latest_blob.get("dqState"))
    candidates.append(latest_blob.get("dq_status"))

    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
        if isinstance(c, dict):
            for k in ["state", "status", "dq_state", "dqStatus"]:
                v = c.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return "NA"

def _extract_metrics_blob(series_blob: Any) -> Dict[str, Any]:
    """
    Returns a dict that may contain z/p/deltas/ret fields.
    Try in order: series_blob["stats"] / ["metrics"] / ["features"] / series_blob itself.
    """
    if not isinstance(series_blob, dict):
        return {}

    for k in ["stats", "metrics", "features", "feature", "calc", "computed"]:
        v = series_blob.get(k)
        if isinstance(v, dict):
            return v

    # sometimes metrics are directly on series_blob
    return series_blob

def _extract_metric_value(m: Dict[str, Any], key_variants: List[str]) -> Optional[float]:
    for k in key_variants:
        if k in m:
            return _to_float(m.get(k))

    # try window nesting, e.g. m["w60"]["z"], m["w252"]["p"]
    # Support: w60 / w252 / windows / window
    # z60
    if any(k in key_variants for k in ["z60", "z_w60", "zscore60", "z_score60"]):
        for wk in ["w60", "W60", "window60", "win60"]:
            w = m.get(wk)
            if isinstance(w, dict):
                for zk in ["z", "zscore", "z_score", "z_abs", "zAbs"]:
                    v = _to_float(w.get(zk))
                    if v is not None:
                        return v
    # p252
    if any(k in key_variants for k in ["p252", "p_w252", "pct252", "percentile252"]):
        for wk in ["w252", "W252", "window252", "win252"]:
            w = m.get(wk)
            if isinstance(w, dict):
                for pk in ["p", "pct", "percentile", "P", "pctl"]:
                    v = _to_float(w.get(pk))
                    if v is not None:
                        return v

    return None

def _extract_all_metrics(series_blob: Any) -> Dict[str, Optional[float]]:
    m = _extract_metrics_blob(series_blob)

    out: Dict[str, Optional[float]] = {}

    out["z60"] = _extract_metric_value(m, ["z60", "z_w60", "zscore60", "z_score60"])
    out["p252"] = _extract_metric_value(m, ["p252", "p_w252", "pct252", "percentile252"])

    out["z_delta60"] = _extract_metric_value(
        m,
        ["z_delta60", "z_d60", "zDelta60", "z_delta_w60", "z_delta"]
    )

    # delta percentile: some scripts use p_delta60, others p_delta252
    out["p_delta252"] = _extract_metric_value(
        m,
        ["p_delta252", "pDelta252", "p_delta_w252", "p_delta"]
    )
    if out["p_delta252"] is None:
        out["p_delta252"] = _extract_metric_value(m, ["p_delta60", "pDelta60", "p_delta_w60"])

    # ret fields: ret1_pct / ret1_pct60 / ret1
    out["ret1_pct"] = _extract_metric_value(
        m,
        ["ret1_pct", "ret1Pct", "ret1_pct60", "ret1_pct_w60", "ret1"]
    )

    # if "ret1" is raw delta, but you store pct, we still treat as number and print; no guessing conversion.

    return out

# -------------------------
# Signal rules
# -------------------------

@dataclass
class RuleConfig:
    z_ext_watch: float = 2.0
    z_ext_alert: float = 2.5
    p_ext_hi: float = 95.0
    p_ext_lo: float = 5.0
    p_alert_lo: float = 2.0
    z_jump: float = 0.75
    near_ratio: float = 0.10  # within 10%

def _signal_rank(sig: str) -> int:
    return {"ALERT": 3, "WATCH": 2, "INFO": 1, "NONE": 0}.get(sig, 0)

def _compute_signal_and_tags(
    metrics: Dict[str, Optional[float]],
    data_lag_d: Optional[int],
    lag_thr_d: Optional[int],
    rule: RuleConfig
) -> Tuple[str, List[str], List[str], str]:
    """
    Returns (Signal, Tags[], Near[], Reason)
    """
    tags: List[str] = []
    near: List[str] = []

    z60 = metrics.get("z60")
    p252 = metrics.get("p252")
    z_d = metrics.get("z_delta60")
    p_d = metrics.get("p_delta252")
    ret = metrics.get("ret1_pct")

    # Jump rule: ONLY |ZΔ60|>=0.75 (as you specified)
    jump = False
    if z_d is not None and abs(z_d) >= rule.z_jump:
        jump = True
        tags.append("JUMP_ZD")

    # Extreme rule
    extreme_z = False
    if z60 is not None:
        if abs(z60) >= rule.z_ext_watch:
            extreme_z = True
            tags.append("EXTREME_Z")
        if abs(z60) >= rule.z_ext_alert:
            tags.append("EXTREME_Z_ALERT")

    long_extreme = False
    if p252 is not None:
        if p252 >= rule.p_ext_hi or p252 <= rule.p_ext_lo:
            long_extreme = True
            tags.append("LONG_EXTREME")

    # info-only tags
    if p_d is not None and abs(p_d) >= 15:
        tags.append("INFO_PΔ")
    if ret is not None and abs(ret) >= 2:
        tags.append("INFO_RET")

    # Near thresholds (only for: z_delta, p_delta, ret)
    def _near(name: str, val: Optional[float], thr: float):
        if val is None:
            return
        if abs(val) >= (1.0 - rule.near_ratio) * thr and abs(val) < thr:
            near.append(f"NEAR:{name}")

    _near("ZΔ60", z_d, rule.z_jump)
    _near("PΔ252", p_d, 15.0)
    _near("ret1%", ret, 2.0)

    # Base signal
    signal = "NONE"
    reason = "NA"

    if extreme_z and z60 is not None and abs(z60) >= rule.z_ext_alert:
        signal = "ALERT"
        reason = f"|Z60|>={rule.z_ext_alert}"
    elif extreme_z:
        signal = "WATCH"
        reason = f"|Z60|>={rule.z_ext_watch}"
    elif jump:
        signal = "WATCH"
        reason = f"|ZΔ60|>={rule.z_jump}"
    elif long_extreme:
        # INFO if only long-extreme and no jump and |Z60|<2
        signal = "INFO"
        reason = f"P252>={rule.p_ext_hi} or <={rule.p_ext_lo}"
    else:
        signal = "NONE"
        reason = "NA"

    # Stale data clamp
    if data_lag_d is not None and lag_thr_d is not None and data_lag_d > lag_thr_d:
        tags.append("STALE_DATA")
        # clamp to INFO (unless NONE already)
        if _signal_rank(signal) > _signal_rank("INFO"):
            signal = "INFO"
        if signal == "WATCH" or signal == "ALERT":
            signal = "INFO"
        reason = f"STALE_DATA(lag_d={data_lag_d}>thr_d={lag_thr_d})"

    # normalize tags
    tags = sorted(set(tags), key=lambda x: ("STALE_DATA" in x, x))
    return (signal, tags, near, reason)

# -------------------------
# PrevSignal / Streak from history
# -------------------------

def _compute_signal_from_point(
    point: Dict[str, Any],
    rule: RuleConfig
) -> Optional[str]:
    """
    Try to compute signal from a historical point if it contains metrics fields.
    If point lacks metrics, return None.
    """
    # gather metrics from point directly
    m: Dict[str, Optional[float]] = {}

    # allow point to have nested stats/metrics too
    blob = point
    if isinstance(point.get("stats"), dict):
        blob = point["stats"]
    elif isinstance(point.get("metrics"), dict):
        blob = point["metrics"]

    def g(keys: List[str]) -> Optional[float]:
        for k in keys:
            if k in blob:
                v = _to_float(blob.get(k))
                if v is not None:
                    return v
        return None

    m["z60"] = g(["z60", "z_w60", "z"])
    m["p252"] = g(["p252", "p_w252", "p", "pct", "percentile"])
    m["z_delta60"] = g(["z_delta60", "z_d60", "zDelta60", "z_delta"])
    m["p_delta252"] = g(["p_delta252", "pDelta252", "p_delta", "p_delta60"])
    m["ret1_pct"] = g(["ret1_pct", "ret1_pct60", "ret1"])

    # If none of key metrics exist, cannot compute
    if all(v is None for v in m.values()):
        return None

    sig, _, _, _ = _compute_signal_and_tags(
        metrics=m,
        data_lag_d=None,  # do not stale-clamp historical
        lag_thr_d=None,
        rule=rule
    )
    return sig

def _prev_and_streak_from_history(
    history_obj: Any,
    series_id: str,
    current_signal: str,
    rule: RuleConfig
) -> Tuple[str, int]:
    """
    Returns (PrevSignal, StreakWA)
    - PrevSignal: signal of previous point (second newest) if computable else NONE
    - StreakWA: consecutive count of same signal as current_signal starting from newest point
    """
    unwrap_mode, hmap = _unwrap_history_series(history_obj)
    if not hmap or series_id not in hmap:
        return ("NONE", 0)

    pts = _extract_history_points(hmap[series_id])
    if not pts:
        return ("NONE", 0)

    pts = _sort_points_desc(pts)

    # compute signals per point until missing
    sigs: List[str] = []
    for p in pts:
        s = _compute_signal_from_point(p, rule)
        if s is None:
            break
        sigs.append(s)

    if not sigs:
        return ("NONE", 0)

    prev = sigs[1] if len(sigs) >= 2 else "NONE"

    streak = 0
    for s in sigs:
        if s == current_signal:
            streak += 1
        else:
            break

    return (prev, streak)

# -------------------------
# Build dashboard rows
# -------------------------

@dataclass
class Row:
    signal: str
    tag: str
    near: str
    prev_signal: str
    streak: int
    feed: str
    series: str
    dq: str
    age_h: float
    stale_h: float
    data_lag_d: str
    data_lag_thr_d: str
    data_date: str
    value: str
    z60: str
    p252: str
    z_delta60: str
    p_delta252: str
    ret1_pct: str
    reason: str
    source: str
    as_of_ts: str

def _build_rows_for_feed(
    feed: FeedMeta,
    run_ts: datetime,
    stale_default_h: float,
    stale_overrides: Dict[str, float],
    lag_default_d: int,
    lag_overrides: Dict[str, int],
    rule: RuleConfig
) -> List[Row]:
    rows: List[Row] = []

    as_of = feed.stats_as_of_ts
    gen = feed.stats_generated_at_utc
    # "age_h" uses generated_at_utc/as_of_ts if parseable; prefer generated_at_utc
    base_ts = _parse_iso_dt(gen) or _parse_iso_dt(as_of)
    age_h_default = _hours_between(run_ts, base_ts) if base_ts else float("nan")

    for series_id, sblob in feed.series_map.items():
        if not isinstance(series_id, str):
            continue
        if not isinstance(sblob, dict):
            continue

        latest = _extract_latest_blob(sblob)

        data_date = latest.get("data_date") or latest.get("date") or latest.get("dataDate") or "NA"
        if not isinstance(data_date, str) or not data_date:
            data_date = "NA"

        val = latest.get("value")
        source_url = latest.get("source_url") or latest.get("source") or latest.get("url") or sblob.get("source_url") or "NA"
        as_of_ts = latest.get("as_of_ts") or sblob.get("as_of_ts") or as_of
        if not isinstance(as_of_ts, str) or not as_of_ts:
            as_of_ts = "NA"

        dq = _extract_dq(sblob, latest)

        # age_h: if series has its own as_of_ts use that; else feed age
        s_asof = latest.get("as_of_ts")
        s_ts = _parse_iso_dt(s_asof) if isinstance(s_asof, str) else None
        if s_ts:
            age_h = _hours_between(run_ts, s_ts)
        else:
            age_h = age_h_default

        stale_h = float(stale_overrides.get(series_id, stale_default_h))

        # lag days
        lag_thr = int(lag_overrides.get(series_id, lag_default_d))
        lag_d = _days_lag(run_ts, data_date) if data_date != "NA" else None

        metrics = _extract_all_metrics(sblob)

        signal, tags, near, reason = _compute_signal_and_tags(
            metrics=metrics,
            data_lag_d=lag_d,
            lag_thr_d=lag_thr,
            rule=rule
        )

        prev_signal, streak = _prev_and_streak_from_history(
            history_obj=feed.history_obj,
            series_id=series_id,
            current_signal=signal,
            rule=rule
        )

        rows.append(
            Row(
                signal=signal,
                tag=",".join(tags) if tags else "NA",
                near=",".join(near) if near else "NA",
                prev_signal=prev_signal,
                streak=streak,
                feed=feed.name,
                series=series_id,
                dq=dq,
                age_h=age_h if _is_number(age_h) else float("nan"),
                stale_h=stale_h,
                data_lag_d=str(lag_d) if lag_d is not None else "NA",
                data_lag_thr_d=str(lag_thr) if lag_thr is not None else "NA",
                data_date=data_date,
                value=_fmt(val, nd=6),
                z60=_fmt(metrics.get("z60"), nd=6),
                p252=_fmt(metrics.get("p252"), nd=6),
                z_delta60=_fmt(metrics.get("z_delta60"), nd=6),
                p_delta252=_fmt(metrics.get("p_delta252"), nd=6),
                ret1_pct=_fmt(metrics.get("ret1_pct"), nd=6),
                reason=reason,
                source=str(source_url) if isinstance(source_url, str) else "NA",
                as_of_ts=as_of_ts,
            )
        )

    return rows

def _sort_rows(rows: List[Row]) -> List[Row]:
    # rank by signal, then by series
    def key(r: Row) -> Tuple[int, str]:
        return (-_signal_rank(r.signal), r.series)
    return sorted(rows, key=key)

def _md_escape(s: str) -> str:
    # keep pipes safe
    return s.replace("|", "\\|")

def _write_markdown(
    out_path: str,
    fingerprint: str,
    run_ts: datetime,
    stale_default_h: float,
    stale_overrides: Dict[str, float],
    lag_default_d: int,
    lag_overrides: Dict[str, int],
    feeds: List[FeedMeta],
    signal_rules: str,
    rows: List[Row],
) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    lines: List[str] = []
    lines.append("# Risk Dashboard (merged)")
    lines.append("")
    lines.append(f"- SCRIPT_FINGERPRINT: `{fingerprint}`")
    lines.append(f"- RUN_TS_UTC: `{run_ts.isoformat()}`")
    lines.append(f"- stale_hours_default: `{_fmt(stale_default_h, nd=1)}`")
    lines.append(f"- stale_overrides: `{json.dumps(stale_overrides, ensure_ascii=False)}`")
    lines.append(f"- data_lag_default_days: `{lag_default_d}`")
    lines.append(f"- data_lag_overrides_days: `{json.dumps(lag_overrides, ensure_ascii=False)}`")
    lines.append("")

    for fd in feeds:
        unwrap_mode, hmap = _unwrap_history_series(fd.history_obj)
        series_cnt = len(hmap)
        lines.append(f"- {fd.name}.stats: `{fd.stats_path}`")
        lines.append(f"- {fd.name}.history: `{fd.history_path}`")
        lines.append(f"- {fd.name}.history_schema: `{type(fd.history_obj).__name__}`")
        lines.append(f"- {fd.name}.history_unwrap: `{unwrap_mode}`")
        lines.append(f"- {fd.name}.history_series_count: `{series_cnt}`")
        lines.append(f"- {fd.name}.as_of_ts: `{fd.stats_as_of_ts}`")
        lines.append(f"- {fd.name}.generated_at_utc: `{fd.stats_generated_at_utc}`")
        lines.append(f"- {fd.name}.script_version: `{fd.script_version}`")
        lines.append("")

    lines.append(f"- signal_rules: `{signal_rules}`")
    lines.append("")

    header = [
        "Signal","Tag","Near","PrevSignal","StreakWA","Feed","Series","DQ",
        "age_h","stale_h","data_lag_d","data_lag_thr_d","data_date","value",
        "z60","p252","z_delta60","p_delta252","ret1_pct","Reason","Source","as_of_ts"
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"]*len(header)) + "|")

    for r in rows:
        row = [
            r.signal,
            _md_escape(r.tag),
            _md_escape(r.near),
            r.prev_signal,
            str(r.streak),
            r.feed,
            r.series,
            r.dq,
            _fmt(r.age_h, nd=2),
            _fmt(r.stale_h, nd=0),
            r.data_lag_d,
            r.data_lag_thr_d,
            r.data_date,
            r.value,
            r.z60,
            r.p252,
            r.z_delta60,
            r.p_delta252,
            r.ret1_pct,
            _md_escape(r.reason),
            _md_escape(r.source),
            _md_escape(r.as_of_ts),
        ]
        lines.append("| " + " | ".join(row) + " |")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dashboard/risk_dashboard_merged.md")
    ap.add_argument("--stale-hours-default", type=float, default=36.0)
    ap.add_argument("--stale-overrides-json", default='{"STLFSI4": 240.0, "NFCINONFINLEVERAGE": 240.0, "BAMLH0A0HYM2": 72.0}')
    ap.add_argument("--data-lag-default-days", type=int, default=2)
    ap.add_argument("--data-lag-overrides-json", default='{"STLFSI4": 10, "NFCINONFINLEVERAGE": 10, "OFR_FSI": 7, "BAMLH0A0HYM2": 3, "DGS2": 3, "DGS10": 3, "VIXCLS": 3, "T10Y2Y": 3, "T10Y3M": 3}')
    ap.add_argument("--fingerprint", default="render_dashboard_py_fix_history_autodetect_and_staleh_2026-01-18")

    # feed paths
    ap.add_argument("--market-stats", default="market_cache/stats_latest.json")
    ap.add_argument("--market-history", default="market_cache/history_lite.json")
    ap.add_argument("--fred-stats", default="cache/stats_latest.json")
    ap.add_argument("--fred-history", default="cache/history_lite.json")

    args = ap.parse_args()

    run_ts = _utc_now()

    try:
        stale_overrides = json.loads(args.stale_overrides_json)
        if not isinstance(stale_overrides, dict):
            stale_overrides = {}
    except Exception:
        stale_overrides = {}

    try:
        lag_overrides = json.loads(args.data_lag_overrides_json)
        if not isinstance(lag_overrides, dict):
            lag_overrides = {}
    except Exception:
        lag_overrides = {}

    rule = RuleConfig()

    # Load feeds
    market_stats = _read_json(args.market_stats)
    market_hist = _read_json(args.market_history)
    mc_asof, mc_gen = _extract_ts(market_stats)
    mc_ver = _extract_script_version(market_stats)
    mc_series = _extract_series_map(market_stats)

    fred_stats = _read_json(args.fred_stats)
    fred_hist = _read_json(args.fred_history)
    fc_asof, fc_gen = _extract_ts(fred_stats)
    fc_ver = _extract_script_version(fred_stats)
    fc_series = _extract_series_map(fred_stats)

    feeds: List[FeedMeta] = [
        FeedMeta(
            name="market_cache",
            stats_path=args.market_stats,
            history_path=args.market_history,
            stats_as_of_ts=mc_asof,
            stats_generated_at_utc=mc_gen,
            script_version=mc_ver,
            series_map=mc_series,
            history_obj=market_hist,
        ),
        FeedMeta(
            name="cache",
            stats_path=args.fred_stats,
            history_path=args.fred_history,
            stats_as_of_ts=fc_asof,
            stats_generated_at_utc=fc_gen,
            script_version=fc_ver,
            series_map=fc_series,
            history_obj=fred_hist,
        ),
    ]

    signal_rules = (
        "Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); "
        "Jump(ONLY |ZΔ60|>=0.75); "
        "Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); "
        "PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); "
        "StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)"
    )

    # Build rows
    all_rows: List[Row] = []
    for fd in feeds:
        all_rows.extend(
            _build_rows_for_feed(
                feed=fd,
                run_ts=run_ts,
                stale_default_h=args.stale_hours_default,
                stale_overrides={k: float(v) for k, v in stale_overrides.items() if _to_float(v) is not None},
                lag_default_d=args.data_lag_default_days,
                lag_overrides={k: int(v) for k, v in lag_overrides.items() if isinstance(v, int)},
                rule=rule
            )
        )

    all_rows = _sort_rows(all_rows)

    _write_markdown(
        out_path=args.out,
        fingerprint=args.fingerprint,
        run_ts=run_ts,
        stale_default_h=args.stale_hours_default,
        stale_overrides={k: float(v) for k, v in stale_overrides.items() if _to_float(v) is not None},
        lag_default_d=args.data_lag_default_days,
        lag_overrides={k: int(v) for k, v in lag_overrides.items() if isinstance(v, int)},
        feeds=feeds,
        signal_rules=signal_rules,
        rows=all_rows,
    )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())