#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Dashboard renderer (v5.2: merge 2 feeds + Tag + Near + Streak)
#
# Fixes included:
# - history_lite.json top-level may be LIST (not dict)
# - history list rows may have value as STRING (e.g. "2.68") -> parse to float
# - robust parsing + never crash run (streak degrades to NA/0)
#
# Inputs:
#   Feed1 (primary): --stats market_cache/stats_latest.json --history market_cache/history_lite.json
#   Feed2 (secondary): --stats2 cache/stats_latest.json --history2 cache/history_lite.json
#
# Output:
#   - dashboard/DASHBOARD.md
#   - dashboard/dashboard_latest.json
#
# Signals (改法 B):
# - Extreme: |Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT)
# - Long extreme: P252>=95 or <=5 (WATCH/INFO), very low tail P252<=2 (ALERT)
# - Jump: |ZΔ60|>=0.75 OR |PΔ60|>=15 OR |ret1%60|>=2
# - Near: within 10% of jump thresholds (but not crossing)
# - INFO if only long-extreme and no jump and |Z60|<2
#
# Streak:
# - PrevSignal: previous point's derived signal
# - StreakWA: consecutive points (from latest backwards) that are WATCH/ALERT
#
# Audit note:
# - Today signal uses stats_latest.json metrics (authoritative)
# - PrevSignal/Streak are recomputed from history_lite values using same signal rules
#   with rolling windows W60/W252 on last N points.

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Tunables
# -------------------------
DEFAULT_STALE_HOURS = 36.0

# Per-series stale-hour overrides (avoid turning slow-updating series into constant STALE)
STALE_OVERRIDES_HOURS: Dict[str, float] = {
    "STLFSI4": 240.0,              # 10 days
    "NFCINONFINLEVERAGE": 240.0,   # 10 days
    "BAMLH0A0HYM2": 72.0,          # 3 days
    # If curve series often stale in practice, consider 72h:
    # "T10Y2Y": 72.0,
    # "T10Y3M": 72.0,
}

# Extreme thresholds
Z60_WATCH_ABS = 2.0
Z60_ALERT_ABS = 2.5

P252_EXTREME_HI = 95.0
P252_EXTREME_LO = 5.0
P252_ALERT_LO = 2.0  # very extreme low tail

# Jump thresholds
ZDELTA60_JUMP_ABS = 0.75
PDELTA60_JUMP_ABS = 15.0
RET1PCT60_JUMP_ABS = 2.0  # percent units

# Near window: within X% of threshold
NEAR_FRAC = 0.10  # 10%

# Streak lookback
STREAK_LOOKBACK_MAX = 30

# Local recompute windows (match your stats policy)
W60 = 60
W252 = 252


# -------------------------
# Helpers
# -------------------------
def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts2 = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts2)
    except Exception:
        return None


def safe_abs(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return abs(float(x))
    return None


def fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        s = f"{x:.{nd}f}"
        return s.rstrip("0").rstrip(".")
    return str(x)


def is_near(abs_val: Optional[float], thr: float, near_frac: float) -> bool:
    if abs_val is None:
        return False
    lo = (1.0 - near_frac) * thr
    return (abs_val >= lo) and (abs_val < thr)


def mean_std_ddof0(vals: List[float]) -> Tuple[float, float]:
    n = len(vals)
    if n == 0:
        return 0.0, 0.0
    m = sum(vals) / n
    var = sum((x - m) ** 2 for x in vals) / n
    return m, var ** 0.5


def percentile_leq(vals: List[float], x: float) -> float:
    n = len(vals)
    if n == 0:
        return 0.0
    c = sum(1 for v in vals if v <= x)
    return (c / n) * 100.0


def stale_hours_for_series(series_id: str, default_hours: float) -> float:
    return float(STALE_OVERRIDES_HOURS.get(series_id, default_hours))


def dq_from_ts(run_ts: datetime, as_of_ts: Optional[datetime], stale_hours: float) -> Tuple[str, Optional[float]]:
    if as_of_ts is None:
        return "MISSING", None
    age_hours = (run_ts - as_of_ts).total_seconds() / 3600.0
    return ("STALE" if age_hours > stale_hours else "OK"), age_hours


def get_w(series_obj: Dict[str, Any], key: str) -> Dict[str, Any]:
    w = series_obj.get("windows", {})
    if not isinstance(w, dict):
        return {}
    wk = w.get(key, {})
    return wk if isinstance(wk, dict) else {}


def to_float_or_none(v: Any) -> Optional[float]:
    """Accept numeric or numeric-string; reject '.', '', None, non-numeric."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s in ("", ".", "NA", "N/A", "null", "None"):
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


# -------------------------
# Signal logic
# -------------------------
def compute_signal_tag_near_from_metrics(
    z60: Optional[float],
    p252: Optional[float],
    zdel60: Optional[float],
    pdel60: Optional[float],
    ret1pct60: Optional[float],
) -> Tuple[str, str, str, str]:
    reasons: List[str] = []
    tags: List[str] = []
    nears: List[str] = []

    az60 = safe_abs(z60)
    azd = safe_abs(zdel60)
    apd = safe_abs(pdel60)
    ar1p = safe_abs(ret1pct60)

    # Extreme checks
    z60_watch = False
    z60_alert = False
    if az60 is not None:
        if az60 >= Z60_WATCH_ABS:
            z60_watch = True
            reasons.append(f"|Z60|>={Z60_WATCH_ABS:g}")
            tags.append("EXTREME_Z")
        if az60 >= Z60_ALERT_ABS:
            z60_alert = True
            reasons.append(f"|Z60|>={Z60_ALERT_ABS:g}")

    p252_hi = False
    p252_lo = False
    p252_alert_lo = False
    if isinstance(p252, (int, float)):
        p = float(p252)
        if p >= P252_EXTREME_HI:
            p252_hi = True
            reasons.append(f"P252>={P252_EXTREME_HI:g}")
            tags.append("LONG_EXTREME")
        if p <= P252_EXTREME_LO:
            p252_lo = True
            reasons.append(f"P252<={P252_EXTREME_LO:g}")
            tags.append("LONG_EXTREME")
        if p <= P252_ALERT_LO:
            p252_alert_lo = True
            reasons.append(f"P252<={P252_ALERT_LO:g}")

    long_extreme_only = (p252_hi or p252_lo) and (not z60_watch)

    # Jump checks
    jump_hits = 0
    has_zdelta_jump = False

    if azd is not None and azd >= ZDELTA60_JUMP_ABS:
        reasons.append(f"|ZΔ60|>={ZDELTA60_JUMP_ABS:g}")
        tags.append("JUMP_ZD")
        jump_hits += 1
        has_zdelta_jump = True
    else:
        if is_near(azd, ZDELTA60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:ZΔ60")

    if apd is not None and apd >= PDELTA60_JUMP_ABS:
        reasons.append(f"|PΔ60|>={PDELTA60_JUMP_ABS:g}")
        tags.append("JUMP_P")
        jump_hits += 1
    else:
        if is_near(apd, PDELTA60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:PΔ60")

    if ar1p is not None and ar1p >= RET1PCT60_JUMP_ABS:
        reasons.append(f"|ret1%60|>={RET1PCT60_JUMP_ABS:g}")
        tags.append("JUMP_RET")
        jump_hits += 1
    else:
        if is_near(ar1p, RET1PCT60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:ret1%60")

    # Level assignment (改法 B)
    if long_extreme_only and jump_hits == 0:
        level = "INFO"
    else:
        if z60_alert or p252_alert_lo or (jump_hits >= 2 and has_zdelta_jump) or (z60_watch and jump_hits >= 1):
            level = "ALERT"
        elif z60_watch or p252_hi or p252_lo or jump_hits >= 1:
            level = "WATCH"
        else:
            level = "NONE"

    reason_str = ";".join(reasons) if reasons else "NA"

    # Dedup tags preserving order
    seen = set()
    tags2: List[str] = []
    for t in tags:
        if t not in seen:
            tags2.append(t)
            seen.add(t)
    tag_str = ",".join(tags2) if tags2 else "NA"

    near_str = ",".join(nears) if nears else "NA"
    return level, reason_str, tag_str, near_str


# -------------------------
# history_lite: build index (supports dict OR list top-level, string values)
# -------------------------
def normalize_points(arr: List[Any]) -> List[Tuple[str, float]]:
    pts: List[Tuple[str, float]] = []
    for it in arr:
        if isinstance(it, dict):
            d = it.get("date") or it.get("data_date") or it.get("d") or it.get("Date")
            raw_v = it.get("value") if "value" in it else it.get("v") or it.get("Value")
            fv = to_float_or_none(raw_v)
            if isinstance(d, str) and fv is not None:
                pts.append((d, fv))
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            d, raw_v = it[0], it[1]
            fv = to_float_or_none(raw_v)
            if isinstance(d, str) and fv is not None:
                pts.append((d, fv))
    pts.sort(key=lambda x: x[0])
    return pts


def build_history_index(history_obj: Any) -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns {series_id: [(date, value), ...]} sorted by date.
    Supports:
      - dict with {"series": {sid: [...] / {...}}}
      - list of rows like [{"series_id": "...", "data_date": "...", "value": "2.68"}, ...]
      - list of rows like [{"series":"...", "d":"...", "v":"..."}, ...]
    """
    idx: Dict[str, List[Tuple[str, float]]] = {}

    # Case 1: dict schema
    if isinstance(history_obj, dict):
        series = history_obj.get("series")
        if isinstance(series, dict):
            for sid, s in series.items():
                pts: List[Tuple[str, float]] = []
                if isinstance(s, dict):
                    for key in ("data", "history", "points", "values"):
                        arr = s.get(key)
                        if isinstance(arr, list):
                            pts = normalize_points(arr)
                            break
                    if not pts:
                        # date->value mapping
                        if all(isinstance(k, str) for k in s.keys()):
                            tmp: List[Tuple[str, float]] = []
                            for k, v in s.items():
                                fv = to_float_or_none(v)
                                if fv is not None:
                                    tmp.append((k, fv))
                            tmp.sort(key=lambda x: x[0])
                            pts = tmp
                elif isinstance(s, list):
                    pts = normalize_points(s)

                if pts:
                    idx[sid] = pts
        return idx

    # Case 2: list schema (flat rows)
    if isinstance(history_obj, list):
        for it in history_obj:
            if not isinstance(it, dict):
                continue
            sid = it.get("series_id") or it.get("series") or it.get("id") or it.get("Series")
            d = it.get("date") or it.get("data_date") or it.get("d") or it.get("Date")
            raw_v = it.get("value") if "value" in it else (it.get("v") if "v" in it else it.get("Value"))
            fv = to_float_or_none(raw_v)
            if isinstance(sid, str) and isinstance(d, str) and fv is not None:
                idx.setdefault(sid, []).append((d, fv))

        for sid, pts in idx.items():
            pts.sort(key=lambda x: x[0])
        return idx

    return {}


def compute_prevsignal_and_streak(history_index: Dict[str, List[Tuple[str, float]]], series_id: str) -> Tuple[str, int]:
    pts = history_index.get(series_id, [])
    if len(pts) < 2:
        return "NA", 0

    pts = pts[-max(STREAK_LOOKBACK_MAX, 2):]
    vals = [v for _, v in pts]
    n = len(vals)

    signals: List[str] = []
    for i in range(n):
        x = vals[i]
        prev = vals[i - 1] if i - 1 >= 0 else None

        w60_vals = vals[max(0, i - (W60 - 1)) : i + 1]
        m60, sd60 = mean_std_ddof0(w60_vals)
        z60 = None if sd60 == 0 else (x - m60) / sd60

        w252_vals = vals[max(0, i - (W252 - 1)) : i + 1]
        p252 = percentile_leq(w252_vals, x)

        if i - 1 >= 0:
            x_prev = vals[i - 1]

            w60_prev = vals[max(0, (i - 1) - (W60 - 1)) : (i - 1) + 1]
            m60p, sd60p = mean_std_ddof0(w60_prev)
            z60_prev = None if sd60p == 0 else (x_prev - m60p) / sd60p

            w252_prev = vals[max(0, (i - 1) - (W252 - 1)) : (i - 1) + 1]
            p252_prev = percentile_leq(w252_prev, x_prev)

            zdel60 = None if (z60 is None or z60_prev is None) else (z60 - z60_prev)
            pdel60 = p252 - p252_prev
        else:
            zdel60 = None
            pdel60 = None

        if prev is None or abs(prev) < 1e-12:
            ret1pct60 = None
        else:
            ret1pct60 = ((x - prev) / abs(prev)) * 100.0

        sig, _, _, _ = compute_signal_tag_near_from_metrics(
            z60=z60, p252=p252, zdel60=zdel60, pdel60=pdel60, ret1pct60=ret1pct60
        )
        signals.append(sig)

    prev_signal = signals[-2] if len(signals) >= 2 else "NA"

    streak = 0
    for s in reversed(signals):
        if s in ("WATCH", "ALERT"):
            streak += 1
        else:
            break

    return prev_signal, streak


# -------------------------
# I/O + render
# -------------------------
def load_json_if_exists(path: Optional[str]) -> Any:
    if not path:
        return None
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def iter_series(stats: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    s = stats.get("series", {})
    return s if isinstance(s, dict) else {}


def write_outputs(out_md: str, out_json: str, meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    payload = {"meta": meta, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines: List[str] = []
    lines.append("# Risk Dashboard (merged)")
    lines.append("")
    lines.append(f"- RUN_TS_UTC: `{meta.get('run_ts_utc','')}`")
    lines.append(f"- stale_hours_default: `{meta.get('stale_hours_default','')}`")
    lines.append(f"- stale_overrides: `{meta.get('stale_overrides','')}`")
    lines.append(f"- FEED1.stats: `{meta.get('feed1_stats','')}`")
    lines.append(f"- FEED1.history: `{meta.get('feed1_history','')}`")
    lines.append(f"- FEED1.history_schema: `{meta.get('feed1_history_schema','')}`")
    lines.append(f"- FEED1.history_series_count: `{meta.get('feed1_history_series_count','')}`")
    lines.append(f"- FEED1.as_of_ts: `{meta.get('feed1_as_of_ts','')}`")
    lines.append(f"- FEED1.generated_at_utc: `{meta.get('feed1_generated_at_utc','')}`")
    lines.append(f"- FEED1.script_version: `{meta.get('feed1_script_version','')}`")
    lines.append(f"- FEED2.stats: `{meta.get('feed2_stats','')}`")
    lines.append(f"- FEED2.history: `{meta.get('feed2_history','')}`")
    lines.append(f"- FEED2.history_schema: `{meta.get('feed2_history_schema','')}`")
    lines.append(f"- FEED2.history_series_count: `{meta.get('feed2_history_series_count','')}`")
    lines.append(f"- FEED2.as_of_ts: `{meta.get('feed2_as_of_ts','')}`")
    lines.append(f"- FEED2.generated_at_utc: `{meta.get('feed2_generated_at_utc','')}`")
    lines.append(f"- FEED2.script_version: `{meta.get('feed2_script_version','')}`")
    lines.append(
        "- signal_rules: "
        f"`Extreme(|Z60|>={Z60_WATCH_ABS:g} (WATCH), |Z60|>={Z60_ALERT_ABS:g} (ALERT), "
        f"P252>={P252_EXTREME_HI:g} or <={P252_EXTREME_LO:g} (WATCH/INFO), P252<={P252_ALERT_LO:g} (ALERT)); "
        f"Jump(|ZΔ60|>={ZDELTA60_JUMP_ABS:g} OR |PΔ60|>={PDELTA60_JUMP_ABS:g} OR |ret1%60|>={RET1PCT60_JUMP_ABS:g}); "
        f"Near(within {NEAR_FRAC*100:.0f}% of jump thresholds); "
        "INFO if only long-extreme and no jump and |Z60|<2`"
    )
    lines.append("")

    header = [
        "Signal", "Tag", "Near", "PrevSignal", "StreakWA",
        "Feed", "Series", "DQ", "age_h", "stale_h",
        "data_date", "value",
        "z60", "p252",
        "z_delta60", "p_delta60", "ret1_pct60",
        "Reason", "Source", "as_of_ts"
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for r in rows:
        lines.append("| " + " | ".join([
            r.get("signal_level", "NONE"),
            r.get("tag", "NA"),
            r.get("near", "NA"),
            r.get("prev_signal", "NA"),
            fmt(r.get("streak_wa"), nd=0),
            r.get("feed", ""),
            r.get("series", ""),
            r.get("dq", ""),
            fmt(r.get("age_hours"), nd=2),
            fmt(r.get("stale_hours"), nd=2),
            fmt(r.get("data_date")),
            fmt(r.get("value"), nd=6),
            fmt(r.get("z60"), nd=6),
            fmt(r.get("p252"), nd=6),
            fmt(r.get("z_delta_60"), nd=6),
            fmt(r.get("p_delta_60"), nd=6),
            fmt(r.get("ret1_pct_60"), nd=6),
            fmt(r.get("reason")),
            fmt(r.get("source_url")),
            fmt(r.get("as_of_ts")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--stats2", default=None)
    ap.add_argument("--history2", default=None)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    stats1 = load_json_if_exists(args.stats)
    hist1_raw = load_json_if_exists(args.history)
    stats2 = load_json_if_exists(args.stats2) if args.stats2 else None
    hist2_raw = load_json_if_exists(args.history2) if args.history2 else None

    if not isinstance(stats1, dict):
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "stale_hours_default": args.stale_hours,
            "stale_overrides": json.dumps(STALE_OVERRIDES_HOURS, ensure_ascii=False),
            "feed1_stats": args.stats,
            "feed1_history": args.history,
            "feed2_stats": args.stats2 or "NA",
            "feed2_history": args.history2 or "NA",
            "error": f"missing/invalid primary stats: {args.stats}",
        }
        write_outputs(args.out_md, args.out_json, meta, [])
        return

    hist1_index = build_history_index(hist1_raw)
    hist2_index = build_history_index(hist2_raw) if isinstance(stats2, dict) else {}

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "stale_hours_default": args.stale_hours,
        "stale_overrides": json.dumps(STALE_OVERRIDES_HOURS, ensure_ascii=False),
        "feed1_stats": args.stats,
        "feed1_history": args.history,
        "feed1_history_schema": type(hist1_raw).__name__ if hist1_raw is not None else "None",
        "feed1_history_series_count": len(hist1_index),
        "feed1_as_of_ts": stats1.get("as_of_ts"),
        "feed1_generated_at_utc": stats1.get("generated_at_utc"),
        "feed1_script_version": stats1.get("script_version"),
        "feed2_stats": args.stats2 or "NA",
        "feed2_history": args.history2 or "NA",
        "feed2_history_schema": type(hist2_raw).__name__ if hist2_raw is not None else "None",
        "feed2_history_series_count": len(hist2_index),
        "feed2_as_of_ts": (stats2.get("as_of_ts") if isinstance(stats2, dict) else None),
        "feed2_generated_at_utc": (stats2.get("generated_at_utc") if isinstance(stats2, dict) else None),
        "feed2_script_version": (stats2.get("script_version") if isinstance(stats2, dict) else None),
        "streak_calc": "recompute from history_lite values; ret1% denom = abs(prev_value) else NA",
    }

    s1 = iter_series(stats1)
    s2 = iter_series(stats2) if isinstance(stats2, dict) else {}

    merged: List[Tuple[str, str, Dict[str, Any]]] = []
    seen_ids = set()

    for sid, sobj in s1.items():
        if isinstance(sobj, dict):
            merged.append(("market_cache", sid, sobj))
            seen_ids.add(sid)

    for sid, sobj in s2.items():
        if sid in seen_ids:
            continue
        if isinstance(sobj, dict):
            merged.append(("cache", sid, sobj))
            seen_ids.add(sid)

    rows: List[Dict[str, Any]] = []
    for feed, sid, sobj in merged:
        latest = sobj.get("latest", {}) if isinstance(sobj.get("latest"), dict) else {}
        w60 = get_w(sobj, "w60")
        w252 = get_w(sobj, "w252")

        stale_h = stale_hours_for_series(sid, args.stale_hours)
        latest_asof_dt = parse_iso(latest.get("as_of_ts"))
        dq, age_hours = dq_from_ts(run_ts, latest_asof_dt, stale_h)

        signal_level, reason, tag, near = compute_signal_tag_near_from_metrics(
            z60=w60.get("z"),
            p252=w252.get("p"),
            zdel60=w60.get("z_delta"),
            pdel60=w60.get("p_delta"),
            ret1pct60=w60.get("ret1_pct"),
        )

        # Streak source selection; NEVER crash the whole run
        try:
            if feed == "market_cache":
                prev_signal, streak = compute_prevsignal_and_streak(hist1_index, sid)
            else:
                prev_signal, streak = compute_prevsignal_and_streak(hist2_index, sid)
        except Exception:
            prev_signal, streak = "NA", 0

        rows.append({
            "feed": feed,
            "series": sid,
            "dq": dq,
            "age_hours": age_hours,
            "stale_hours": stale_h,
            "data_date": latest.get("data_date"),
            "value": latest.get("value"),
            "as_of_ts": latest.get("as_of_ts"),
            "source_url": latest.get("source_url"),
            "z60": w60.get("z"),
            "p252": w252.get("p"),
            "z_delta_60": w60.get("z_delta"),
            "p_delta_60": w60.get("p_delta"),
            "ret1_pct_60": w60.get("ret1_pct"),
            "signal_level": signal_level,
            "reason": reason,
            "tag": tag,
            "near": near,
            "prev_signal": prev_signal,
            "streak_wa": streak,
        })

    # Sorting:
    # 1) Signal: ALERT, WATCH, INFO, NONE
    # 2) For WATCH: Near!=NA first, then higher streak first
    # 3) DQ: MISSING, STALE, OK
    # 4) Feed: market_cache first, then series
    sig_order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    dq_order = {"MISSING": 0, "STALE": 1, "OK": 2}
    feed_order = {"market_cache": 0, "cache": 1}

    def watch_near_rank(r: Dict[str, Any]) -> int:
        if r.get("signal_level") != "WATCH":
            return 9
        return 0 if r.get("near") not in (None, "NA", "") else 1

    def streak_rank(r: Dict[str, Any]) -> int:
        try:
            return -int(r.get("streak_wa") or 0)
        except Exception:
            return 0

    rows.sort(key=lambda r: (
        sig_order.get(r.get("signal_level", "NONE"), 9),
        watch_near_rank(r),
        streak_rank(r),
        dq_order.get(r.get("dq", "OK"), 9),
        feed_order.get(r.get("feed", ""), 9),
        r.get("series", ""),
    ))

    write_outputs(args.out_md, args.out_json, meta, rows)


if __name__ == "__main__":
    main()