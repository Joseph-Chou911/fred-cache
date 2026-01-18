#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Risk Dashboard renderer (merged feeds)
# - Merge 2 feeds (e.g., market_cache + cache)
# - Compute tags/near/signal with noise-controlled rules
# - Read history_lite.json for streak + (when needed) deltas
# - Clamp signals to INFO when data_date lag exceeds per-series threshold
#
# v5.6 change (per your request):
# - data_lag_overrides_days: add {DGS2,DGS10,VIXCLS,T10Y2Y,T10Y3M}=3
#
# Usage (example):
#   python scripts/render_dashboard.py \
#     --stats market_cache/stats_latest.json --history market_cache/history_lite.json \
#     --stats2 cache/stats_latest.json --history2 cache/history_lite.json \
#     --out-md dashboard/DASHBOARD.md --out-json dashboard/dashboard_latest.json \
#     --module merged --stale-hours 36
#
from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

# -------------------------
# Defaults (tuned for your repo)
# -------------------------

DEFAULT_STALE_HOURS = 36.0
STALE_OVERRIDES_HOURS: Dict[str, float] = {
    "STLFSI4": 240.0,
    "NFCINONFINLEVERAGE": 240.0,
    "BAMLH0A0HYM2": 72.0,
}

DATA_LAG_DEFAULT_DAYS = 2
DATA_LAG_OVERRIDES_DAYS: Dict[str, int] = {
    "STLFSI4": 10,
    "NFCINONFINLEVERAGE": 10,
    "OFR_FSI": 7,
    "BAMLH0A0HYM2": 3,
    # v5.6: weekend-friendly overrides
    "DGS2": 3,
    "DGS10": 3,
    "VIXCLS": 3,
    "T10Y2Y": 3,
    "T10Y3M": 3,
}

# Signal thresholds
TH_Z60_WATCH = 2.0
TH_Z60_ALERT = 2.5
TH_P252_EXTREME_HI = 95.0
TH_P252_EXTREME_LO = 5.0
TH_P252_ALERT_LO = 2.0

TH_ZD60_JUMP = 0.75
TH_PDELTA252_INFO = 15.0
TH_RET1PCT_INFO = 2.0

NEAR_FRACTION = 0.10  # within 10% of threshold


# -------------------------
# Helpers
# -------------------------

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_text(path: str, s: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)

def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    # accept "Z" or "+00:00"
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d or not isinstance(d, str):
        return None
    try:
        return date.fromisoformat(d.strip())
    except Exception:
        return None

def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "" or s.lower() in {"na", "nan", "null"}:
            return None
        try:
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None
    return None

def _mean_std_ddof0(vals: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not vals:
        return None, None
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    sd = math.sqrt(var)
    return m, sd

def _percentile_le(vals: List[float], x: float) -> Optional[float]:
    if not vals:
        return None
    n = len(vals)
    cnt = sum(1 for v in vals if v <= x)
    return (cnt / n) * 100.0

def _fmt(x: Optional[float], nd: int = 6) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")

def _fmt_int(x: Optional[int]) -> str:
    if x is None:
        return "NA"
    return str(x)

def _signal_rank(sig: str) -> int:
    return {"ALERT": 3, "WATCH": 2, "INFO": 1, "NONE": 0}.get(sig, 0)

def _max_signal(a: str, b: str) -> str:
    return a if _signal_rank(a) >= _signal_rank(b) else b

def _near(th: float, val: Optional[float]) -> bool:
    if val is None:
        return False
    lo = th * (1.0 - NEAR_FRACTION)
    return lo <= abs(val) < th

def _near_signed(th: float, val: Optional[float]) -> bool:
    if val is None:
        return False
    lo = th * (1.0 - NEAR_FRACTION)
    return lo <= val < th


# -------------------------
# History loaders
# -------------------------

def _history_to_series_map(history_obj: Any) -> Dict[str, List[Tuple[date, float]]]:
    """
    Support both schemas:
    A) dict: {"SERIES":[{"data_date":..., "value":...}, ...], ...}
    B) list: [{"series_id":..., "data_date":..., "value":...}, ...]
    Returns: series_id -> sorted list of (data_date, value)
    """
    out: Dict[str, List[Tuple[date, float]]] = {}

    if isinstance(history_obj, dict):
        for sid, rows in history_obj.items():
            if not isinstance(rows, list):
                continue
            pts: List[Tuple[date, float]] = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                dd = _parse_date(r.get("data_date"))
                vv = _to_float(r.get("value"))
                if dd is None or vv is None:
                    continue
                pts.append((dd, vv))
            pts.sort(key=lambda t: t[0])
            if pts:
                out[sid] = pts
        return out

    if isinstance(history_obj, list):
        for r in history_obj:
            if not isinstance(r, dict):
                continue
            sid = r.get("series_id")
            if not isinstance(sid, str) or not sid:
                continue
            dd = _parse_date(r.get("data_date"))
            vv = _to_float(r.get("value"))
            if dd is None or vv is None:
                continue
            out.setdefault(sid, []).append((dd, vv))
        for sid in list(out.keys()):
            out[sid].sort(key=lambda t: t[0])
        return out

    return out


# -------------------------
# Metrics extraction / computation
# -------------------------

@dataclass
class SeriesMetrics:
    series_id: str
    data_date: Optional[date]
    value: Optional[float]
    source: str
    as_of_ts: Optional[str]

    z60: Optional[float]
    p252: Optional[float]
    z_delta60: Optional[float]
    p_delta252: Optional[float]
    ret1_pct: Optional[float]

def _extract_from_stats_native(stats: Dict[str, Any], sid: str) -> Optional[SeriesMetrics]:
    """
    For market_cache stats schema (series -> latest + windows[w60,w252] with z/p and deltas).
    """
    s = stats.get("series", {}).get(sid)
    if not isinstance(s, dict):
        return None
    latest = s.get("latest", {})
    if not isinstance(latest, dict):
        latest = {}
    dd = _parse_date(latest.get("data_date"))
    val = _to_float(latest.get("value"))
    as_of_ts = latest.get("as_of_ts") if isinstance(latest.get("as_of_ts"), str) else stats.get("as_of_ts")
    src = latest.get("source_url") or "NA"
    if isinstance(src, list):
        src = "DERIVED"

    windows = s.get("windows", {})
    if not isinstance(windows, dict):
        windows = {}

    w60 = windows.get("w60", {})
    w252 = windows.get("w252", {})
    if not isinstance(w60, dict):
        w60 = {}
    if not isinstance(w252, dict):
        w252 = {}

    z60 = _to_float(w60.get("z"))
    p252 = _to_float(w252.get("p"))
    z_delta60 = _to_float(w60.get("z_delta"))
    p_delta252 = _to_float(w252.get("p_delta"))  # align with your renamed column
    ret1_pct = _to_float(w60.get("ret1_pct"))

    return SeriesMetrics(
        series_id=sid,
        data_date=dd,
        value=val,
        source=str(src),
        as_of_ts=as_of_ts if isinstance(as_of_ts, str) else None,
        z60=z60,
        p252=p252,
        z_delta60=z_delta60,
        p_delta252=p_delta252,
        ret1_pct=ret1_pct,
    )

def _extract_from_stats_policy(stats: Dict[str, Any], sid: str) -> Optional[SeriesMetrics]:
    """
    For cache stats_v1 schema:
      series -> latest + metrics{z60,p252,ret1} (no deltas)
    """
    s = stats.get("series", {}).get(sid)
    if not isinstance(s, dict):
        return None
    latest = s.get("latest", {})
    if not isinstance(latest, dict):
        latest = {}
    dd = _parse_date(latest.get("data_date"))
    val = _to_float(latest.get("value"))
    src = latest.get("source_url") or "NA"
    m = s.get("metrics", {})
    if not isinstance(m, dict):
        m = {}

    z60 = _to_float(m.get("z60"))
    p252 = _to_float(m.get("p252"))
    # We'll compute deltas + ret1_pct from history for consistency
    return SeriesMetrics(
        series_id=sid,
        data_date=dd,
        value=val,
        source=str(src),
        as_of_ts=stats.get("as_of_ts") if isinstance(stats.get("as_of_ts"), str) else None,
        z60=z60,
        p252=p252,
        z_delta60=None,
        p_delta252=None,
        ret1_pct=None,
    )

def _compute_deltas_from_history(
    sid: str,
    latest_date: Optional[date],
    series_pts: List[Tuple[date, float]],
    w60: int = 60,
    w252: int = 252,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute:
      z_delta60 = z60(latest) - z60(prev)
      p_delta252 = p252(latest) - p252(prev)
      ret1_pct = (latest-prev)/abs(prev)*100
    Requires at least 2 points and ability to locate latest and prev index by date.
    """
    if latest_date is None or not series_pts:
        return None, None, None
    # find latest index by date
    idx = None
    for i, (d, _) in enumerate(series_pts):
        if d == latest_date:
            idx = i
            break
    if idx is None or idx == 0:
        return None, None, None

    prev_idx = idx - 1
    prev_val = series_pts[prev_idx][1]
    cur_val = series_pts[idx][1]

    # ret1_pct
    if prev_val == 0:
        ret1_pct = None
    else:
        ret1_pct = (cur_val - prev_val) / abs(prev_val) * 100.0

    def _z_at(end_i: int) -> Optional[float]:
        start = max(0, end_i - (w60 - 1))
        window = [v for _, v in series_pts[start : end_i + 1]]
        if len(window) < min(10, w60):  # avoid nonsense if too short
            return None
        m, sd = _mean_std_ddof0(window)
        if m is None or sd is None or sd == 0:
            return None
        return (window[-1] - m) / sd

    def _p252_at(end_i: int) -> Optional[float]:
        start = max(0, end_i - (w252 - 1))
        window = [v for _, v in series_pts[start : end_i + 1]]
        if len(window) < min(30, w252):  # need some mass
            return None
        return _percentile_le(window, window[-1])

    z_cur = _z_at(idx)
    z_prev = _z_at(prev_idx)
    z_delta = (z_cur - z_prev) if (z_cur is not None and z_prev is not None) else None

    p_cur = _p252_at(idx)
    p_prev = _p252_at(prev_idx)
    p_delta = (p_cur - p_prev) if (p_cur is not None and p_prev is not None) else None

    return z_delta, p_delta, ret1_pct


# -------------------------
# Signal logic
# -------------------------

def _compute_signal_tag_near(metrics: SeriesMetrics) -> Tuple[str, str, str, str]:
    """
    Returns: (signal_raw, tag_csv, near_str, reason)
    signal_raw ignores stale_data clamp.
    """
    tags: List[str] = []
    nears: List[str] = []
    reason_parts: List[str] = []
    signal = "NONE"

    # Extreme by Z60
    if metrics.z60 is not None:
        if abs(metrics.z60) >= TH_Z60_ALERT:
            signal = _max_signal(signal, "ALERT")
            tags.append("EXTREME_Z")
            reason_parts.append(f"|Z60|>={TH_Z60_ALERT:g}")
        elif abs(metrics.z60) >= TH_Z60_WATCH:
            signal = _max_signal(signal, "WATCH")
            tags.append("EXTREME_Z")
            reason_parts.append(f"|Z60|>={TH_Z60_WATCH:g}")

    # Jump only by ZΔ60
    if metrics.z_delta60 is not None:
        if abs(metrics.z_delta60) >= TH_ZD60_JUMP:
            signal = _max_signal(signal, "WATCH")
            tags.append("JUMP_ZD")
            reason_parts.append(f"|ZΔ60|>={TH_ZD60_JUMP:g}")
        elif _near(TH_ZD60_JUMP, metrics.z_delta60):
            nears.append("NEAR:ZΔ60")

    # Long extreme by P252 (no escalation if only long-extreme + no |Z60|>=2 and no Jump)
    if metrics.p252 is not None:
        if metrics.p252 <= TH_P252_ALERT_LO:
            signal = _max_signal(signal, "ALERT")
            tags.append("LONG_EXTREME")
            reason_parts.append(f"P252<={TH_P252_ALERT_LO:g}")
        elif metrics.p252 >= TH_P252_EXTREME_HI or metrics.p252 <= TH_P252_EXTREME_LO:
            # if not already WATCH/ALERT, mark INFO
            if _signal_rank(signal) < _signal_rank("WATCH"):
                signal = _max_signal(signal, "INFO")
            tags.append("LONG_EXTREME")
            reason_parts.append("P252>=95" if metrics.p252 >= TH_P252_EXTREME_HI else "P252<=5")

    # INFO-only tags (no escalation)
    if metrics.p_delta252 is not None:
        if abs(metrics.p_delta252) >= TH_PDELTA252_INFO:
            tags.append("INFO_PΔ")
        elif _near(TH_PDELTA252_INFO, metrics.p_delta252):
            nears.append("NEAR:PΔ252")

    if metrics.ret1_pct is not None:
        if abs(metrics.ret1_pct) >= TH_RET1PCT_INFO:
            tags.append("INFO_RET")
        elif _near(TH_RET1PCT_INFO, metrics.ret1_pct):
            nears.append("NEAR:ret1%")

    tag_csv = ",".join(dict.fromkeys(tags)) if tags else "NA"
    near_str = ",".join(dict.fromkeys(nears)) if nears else "NA"
    reason = ";".join(reason_parts) if reason_parts else "NA"

    return signal, tag_csv, near_str, reason


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--stats2", default=None)
    ap.add_argument("--history2", default=None)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", default="merged")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    # Load previous dashboard json for prevsignal/streak
    prev_map: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(args.out_json):
        try:
            prev = _read_json(args.out_json)
            prev_rows = prev.get("rows", {})
            if isinstance(prev_rows, dict):
                prev_map = prev_rows
        except Exception:
            prev_map = {}

    # Load feed1
    stats1 = _read_json(args.stats)
    hist1_obj = _read_json(args.history)
    hist1 = _history_to_series_map(hist1_obj)
    feed1_asof = _parse_ts(stats1.get("as_of_ts") if isinstance(stats1.get("as_of_ts"), str) else stats1.get("generated_at_utc"))
    feed1_gen = stats1.get("generated_at_utc")
    feed1_ver = stats1.get("script_version")
    feed1_schema = "dict" if isinstance(hist1_obj, dict) else ("list" if isinstance(hist1_obj, list) else "unknown")

    # Load feed2 (optional)
    stats2 = None
    hist2_obj = None
    hist2 = {}
    feed2_asof = None
    feed2_gen = None
    feed2_ver = None
    feed2_schema = None
    if args.stats2 and args.history2:
        stats2 = _read_json(args.stats2)
        hist2_obj = _read_json(args.history2)
        hist2 = _history_to_series_map(hist2_obj)
        feed2_asof = _parse_ts(stats2.get("as_of_ts") if isinstance(stats2.get("as_of_ts"), str) else stats2.get("generated_at_utc"))
        feed2_gen = stats2.get("generated_at_utc")
        # Prefer stats_policy.script_version if present
        if isinstance(stats2.get("stats_policy"), dict) and isinstance(stats2["stats_policy"].get("script_version"), str):
            feed2_ver = stats2["stats_policy"]["script_version"]
        else:
            feed2_ver = stats2.get("script_version")
        feed2_schema = "dict" if isinstance(hist2_obj, dict) else ("list" if isinstance(hist2_obj, list) else "unknown")

    # Build series universe
    series_ids: List[Tuple[str, str]] = []  # (feed, sid)
    for sid in (stats1.get("series", {}) or {}).keys():
        if isinstance(sid, str):
            series_ids.append(("market_cache", sid))
    if stats2:
        for sid in (stats2.get("series", {}) or {}).keys():
            if isinstance(sid, str):
                series_ids.append(("cache", sid))

    # Dedup (feed,sid)
    seen = set()
    series_ids = [x for x in series_ids if (x not in seen and not seen.add(x))]

    # Assemble rows
    rows_out: Dict[str, Dict[str, Any]] = {}
    table_rows: List[Dict[str, Any]] = []

    # Metadata header items for MD
    stale_overrides = STALE_OVERRIDES_HOURS.copy()
    data_lag_overrides = DATA_LAG_OVERRIDES_DAYS.copy()

    def stale_h_for(sid: str) -> float:
        return float(stale_overrides.get(sid, args.stale_hours))

    def data_lag_thr_for(sid: str) -> int:
        return int(data_lag_overrides.get(sid, DATA_LAG_DEFAULT_DAYS))

    for feed, sid in series_ids:
        if feed == "market_cache":
            m = _extract_from_stats_native(stats1, sid)
            hist_map = hist1
            feed_asof = feed1_asof
        else:
            if stats2 is None:
                continue
            m = _extract_from_stats_policy(stats2, sid)
            hist_map = hist2
            feed_asof = feed2_asof

        if m is None:
            continue

        # If deltas missing, compute from history (feed2 primarily)
        pts = hist_map.get(sid, [])
        if (m.z_delta60 is None or m.p_delta252 is None or m.ret1_pct is None) and pts:
            zd, pd, rp = _compute_deltas_from_history(sid, m.data_date, pts)
            if m.z_delta60 is None:
                m.z_delta60 = zd
            if m.p_delta252 is None:
                m.p_delta252 = pd
            if m.ret1_pct is None:
                m.ret1_pct = rp

        # Compute signal/tags/near (raw)
        signal_raw, tag_csv, near_str, reason_raw = _compute_signal_tag_near(m)

        # Prev signal/streak (based on raw, so stale clamp doesn't reset streak)
        prev_key = f"{feed}:{sid}"
        prev_rec = prev_map.get(prev_key, {})
        prev_signal = prev_rec.get("signal", "NONE") if isinstance(prev_rec, dict) else "NONE"
        prev_streak = prev_rec.get("streakWA", 0) if isinstance(prev_rec, dict) else 0
        if not isinstance(prev_streak, int):
            try:
                prev_streak = int(prev_streak)
            except Exception:
                prev_streak = 0
        streakWA = (prev_streak + 1) if signal_raw in {"WATCH", "ALERT"} else 0

        # Age / DQ
        age_h = None
        if feed_asof is not None:
            age_h = (run_ts - feed_asof).total_seconds() / 3600.0
        stale_h = stale_h_for(sid)
        dq = "OK" if (age_h is not None and age_h <= stale_h) else ("MISSING" if age_h is None else "STALE")

        # Data lag clamp
        data_lag_d = None
        if m.data_date is not None:
            data_lag_d = (run_ts.date() - m.data_date).days
        data_lag_thr_d = data_lag_thr_for(sid)

        signal = signal_raw
        reason = reason_raw

        tags_list = [] if tag_csv == "NA" else tag_csv.split(",")
        if data_lag_d is not None and data_lag_d > data_lag_thr_d:
            # clamp to INFO + STALE_DATA (match your output)
            signal = "INFO"
            if "STALE_DATA" not in tags_list:
                tags_list.append("STALE_DATA")
            reason = f"STALE_DATA(lag_d={data_lag_d}>thr_d={data_lag_thr_d})"

        tag_csv2 = ",".join([t for t in tags_list if t]) if tags_list else "NA"

        row = {
            "Signal": signal,
            "Tag": tag_csv2,
            "Near": near_str,
            "PrevSignal": prev_signal,
            "StreakWA": streakWA,
            "Feed": feed,
            "Series": sid,
            "DQ": dq,
            "age_h": None if age_h is None else round(age_h, 2),
            "stale_h": stale_h,
            "data_lag_d": data_lag_d,
            "data_lag_thr_d": data_lag_thr_d,
            "data_date": m.data_date.isoformat() if m.data_date else "NA",
            "value": m.value,
            "z60": m.z60,
            "p252": m.p252,
            "z_delta60": m.z_delta60,
            "p_delta252": m.p_delta252,
            "ret1_pct": m.ret1_pct,
            "Reason": reason,
            "Source": m.source,
            "as_of_ts": m.as_of_ts or "NA",
        }

        # Persist row for next run
        rows_out[prev_key] = {
            "signal": signal,
            "signal_raw": signal_raw,
            "streakWA": streakWA,
            "updated_at_utc": run_ts.isoformat(),
        }

        table_rows.append(row)

    # Sort: Signal desc, then Feed, then Series
    def _sort_key(r: Dict[str, Any]) -> Tuple[int, str, str]:
        return (-_signal_rank(r["Signal"]), str(r["Feed"]), str(r["Series"]))

    table_rows.sort(key=_sort_key)

    # Build MD
    # Feed metadata
    def _ts_str(dt: Optional[datetime]) -> str:
        return dt.isoformat() if dt else "NA"

    md_lines: List[str] = []
    md_lines.append(f"# Risk Dashboard ({args.module})\n")
    md_lines.append(f"- RUN_TS_UTC: `{run_ts.isoformat()}`")
    md_lines.append(f"- stale_hours_default: `{args.stale_hours}`")
    md_lines.append(f"- stale_overrides: `{json.dumps(stale_overrides, ensure_ascii=False)}`")
    md_lines.append(f"- data_lag_default_days: `{DATA_LAG_DEFAULT_DAYS}`")
    md_lines.append(f"- data_lag_overrides_days: `{json.dumps(data_lag_overrides, ensure_ascii=False)}`")
    md_lines.append(f"- FEED1.stats: `{args.stats}`")
    md_lines.append(f"- FEED1.history: `{args.history}`")
    md_lines.append(f"- FEED1.history_schema: `{feed1_schema}`")
    md_lines.append(f"- FEED1.history_series_count: `{len(set(hist1.keys()))}`")
    md_lines.append(f"- FEED1.as_of_ts: `{stats1.get('as_of_ts','NA')}`")
    md_lines.append(f"- FEED1.generated_at_utc: `{feed1_gen if isinstance(feed1_gen,str) else 'NA'}`")
    md_lines.append(f"- FEED1.script_version: `{feed1_ver if isinstance(feed1_ver,str) else 'None'}`")

    if stats2 is not None:
        md_lines.append(f"- FEED2.stats: `{args.stats2}`")
        md_lines.append(f"- FEED2.history: `{args.history2}`")
        md_lines.append(f"- FEED2.history_schema: `{feed2_schema}`")
        md_lines.append(f"- FEED2.history_series_count: `{len(set(hist2.keys()))}`")
        md_lines.append(f"- FEED2.as_of_ts: `{stats2.get('as_of_ts','NA')}`")
        md_lines.append(f"- FEED2.generated_at_utc: `{feed2_gen if isinstance(feed2_gen,str) else 'NA'}`")
        md_lines.append(f"- FEED2.script_version: `{feed2_ver if isinstance(feed2_ver,str) else 'None'}`")

    md_lines.append(
        "- signal_rules: `"
        "Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), "
        "P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); "
        "Jump(ONLY |ZΔ60|>=0.75); "
        "Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); "
        "PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); "
        "StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)`"
    )
    md_lines.append("")

    # Table
    headers = [
        "Signal","Tag","Near","PrevSignal","StreakWA","Feed","Series","DQ",
        "age_h","stale_h","data_lag_d","data_lag_thr_d",
        "data_date","value","z60","p252","z_delta60","p_delta252","ret1_pct",
        "Reason","Source","as_of_ts"
    ]
    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for r in table_rows:
        md_lines.append(
            "| "
            + " | ".join([
                str(r["Signal"]),
                str(r["Tag"]),
                str(r["Near"]),
                str(r["PrevSignal"]),
                str(r["StreakWA"]),
                str(r["Feed"]),
                str(r["Series"]),
                str(r["DQ"]),
                _fmt(_to_float(r["age_h"]), 2) if r["age_h"] is not None else "NA",
                _fmt(_to_float(r["stale_h"]), 0),
                _fmt_int(r["data_lag_d"] if isinstance(r["data_lag_d"], int) else None),
                _fmt_int(r["data_lag_thr_d"] if isinstance(r["data_lag_thr_d"], int) else None),
                str(r["data_date"]),
                _fmt(_to_float(r["value"]), 6),
                _fmt(_to_float(r["z60"]), 6),
                _fmt(_to_float(r["p252"]), 6),
                _fmt(_to_float(r["z_delta60"]), 6),
                _fmt(_to_float(r["p_delta252"]), 6),
                _fmt(_to_float(r["ret1_pct"]), 6),
                str(r["Reason"]),
                str(r["Source"]),
                str(r["as_of_ts"]),
            ])
            + " |"
        )

    _write_text(args.out_md, "\n".join(md_lines) + "\n")

    # Output json for next run
    out_obj = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "stale_hours_default": args.stale_hours,
        "stale_overrides": stale_overrides,
        "data_lag_default_days": DATA_LAG_DEFAULT_DAYS,
        "data_lag_overrides_days": data_lag_overrides,
        "rows": rows_out,
    }
    _write_json(args.out_json, out_obj)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())