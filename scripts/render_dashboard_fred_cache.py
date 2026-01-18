#!/usr/bin/env python3
# scripts/render_dashboard_fred_cache.py
#
# Dashboard renderer for FRED cache
# - Reads pinned stats_latest.json (already computed by cache pipeline)
# - Computes "jump" metrics from history_lite.json:
#     ret1% = (latest - prev) / abs(prev) * 100
#     zΔ60  = z60(latest) - z60(prev_window)
#     pΔ60  = p60(latest) - p60(prev_window)
# - Applies signal rules:
#     Extreme: abs(Z60)>=2 -> WATCH; abs(Z60)>=2.5 -> ALERT
#     Long-extreme: P252>=95 or <=5 -> INFO; P252<=2 -> ALERT
#     Jump (Scheme A): 2-of-3:
#         abs(zΔ60)>=0.75, abs(pΔ60)>=15, abs(ret1%)>=2
#         => if >=2 triggers, then WATCH
#
# Output:
# - dashboard_fred_cache/latest.md (and optional latest.json if you already do)
# - dashboard_fred_cache/history.json (append series_signals snapshot)

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Helpers
# -------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_text(path: str, s: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)

def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)

def safe_abs(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return abs(x)

def fmt_num(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, (int, float)):
        if not math.isfinite(x):
            return "NA"
        # keep integers clean
        if abs(x - int(x)) < 1e-12:
            return str(int(x))
        return f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return str(x)

def fmt_age_h(age_h: Optional[float]) -> str:
    if age_h is None:
        return "NA"
    return fmt_num(age_h, nd=2)

def calc_age_hours(stats_as_of_ts: str, run_ts_utc: str) -> Optional[float]:
    # stats_as_of_ts may be "Z" or "+08:00"; run_ts_utc is ISO with timezone
    try:
        a = datetime.fromisoformat(stats_as_of_ts.replace("Z", "+00:00"))
        r = datetime.fromisoformat(run_ts_utc.replace("Z", "+00:00"))
        return (r - a).total_seconds() / 3600.0
    except Exception:
        return None

def percentile_le(window_vals: List[float], x: float) -> Optional[float]:
    # P = count(v<=x)/n*100
    if not window_vals:
        return None
    n = 0
    c = 0
    for v in window_vals:
        if not is_finite(v):
            continue
        n += 1
        if v <= x:
            c += 1
    if n == 0:
        return None
    return (c / n) * 100.0

def mean_std(vals: List[float], ddof: int = 0) -> Tuple[Optional[float], Optional[float]]:
    xs = [v for v in vals if is_finite(v)]
    n = len(xs)
    if n == 0:
        return (None, None)
    mu = sum(xs) / n
    if n - ddof <= 0:
        return (mu, None)
    var = sum((v - mu) ** 2 for v in xs) / (n - ddof)
    sd = math.sqrt(var)
    return (mu, sd)

def zscore(window_vals: List[float], x: float, ddof: int = 0) -> Optional[float]:
    mu, sd = mean_std(window_vals, ddof=ddof)
    if mu is None or sd is None:
        return None
    if sd == 0:
        return None
    return (x - mu) / sd

def safe_float(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)) and math.isfinite(x):
        return float(x)
    return None


# -------------------------
# History (dashboard outputs)
# -------------------------

def load_dash_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "dash_history_v1", "items": []}
    try:
        obj = load_json(path)
        if not isinstance(obj, dict) or "items" not in obj:
            return {"schema_version": "dash_history_v1", "items": []}
        if not isinstance(obj["items"], list):
            obj["items"] = []
        if "schema_version" not in obj:
            obj["schema_version"] = "dash_history_v1"
        return obj
    except Exception:
        return {"schema_version": "dash_history_v1", "items": []}

def last_series_signal(dash_hist: Dict[str, Any]) -> Dict[str, str]:
    items = dash_hist.get("items", [])
    if not items:
        return {}
    last = items[-1]
    ss = last.get("series_signals", {})
    if isinstance(ss, dict):
        # ensure strings
        out: Dict[str, str] = {}
        for k, v in ss.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out
    return {}

def append_dash_history(
    dash_hist_path: str,
    dash_hist: Dict[str, Any],
    run_ts_utc: str,
    stats_as_of_ts: str,
    module: str,
    series_signals: Dict[str, str],
) -> None:
    item = {
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "series_signals": series_signals,
    }
    dash_hist.setdefault("schema_version", "dash_history_v1")
    dash_hist.setdefault("items", [])
    dash_hist["items"].append(item)
    save_json(dash_hist_path, dash_hist)


# -------------------------
# History lite (FRED cache values)
# -------------------------

@dataclass
class HistPoint:
    data_date: str
    value: float

def load_history_lite(path: str) -> Dict[str, List[HistPoint]]:
    """
    Expect cache/history_lite.json:
    - either dict with "series": {SERIES_ID: [{"data_date":..., "value":...}, ...]}
    - or dict {SERIES_ID: [{"data_date":..., "value":...}, ...]}
    - or list of records with series_id
    We'll try to be tolerant.
    """
    if not os.path.exists(path):
        return {}

    obj = load_json(path)
    series_map: Dict[str, List[Dict[str, Any]]] = {}

    if isinstance(obj, dict):
        if "series" in obj and isinstance(obj["series"], dict):
            for sid, arr in obj["series"].items():
                if isinstance(sid, str) and isinstance(arr, list):
                    series_map[sid] = arr
        else:
            # maybe {SID: [...]} form
            ok = True
            for sid, arr in obj.items():
                if not isinstance(sid, str) or not isinstance(arr, list):
                    ok = False
                    break
            if ok:
                for sid, arr in obj.items():
                    series_map[sid] = arr
    elif isinstance(obj, list):
        # list of records with series_id
        tmp: Dict[str, List[Dict[str, Any]]] = {}
        for rec in obj:
            if not isinstance(rec, dict):
                continue
            sid = rec.get("series_id") or rec.get("series") or rec.get("id")
            if not isinstance(sid, str):
                continue
            tmp.setdefault(sid, []).append(rec)
        series_map = tmp

    out: Dict[str, List[HistPoint]] = {}
    for sid, arr in series_map.items():
        pts: List[HistPoint] = []
        for rec in arr:
            if not isinstance(rec, dict):
                continue
            dd = rec.get("data_date")
            vv = safe_float(rec.get("value"))
            if isinstance(dd, str) and vv is not None:
                pts.append(HistPoint(data_date=dd, value=vv))
        # assume already sorted asc by data_date in your pipeline; if not, sort safely
        pts.sort(key=lambda p: p.data_date)
        out[sid] = pts
    return out

def last_two_points(hist_pts: List[HistPoint]) -> Tuple[Optional[HistPoint], Optional[HistPoint]]:
    if not hist_pts or len(hist_pts) < 2:
        return (None, None)
    return (hist_pts[-2], hist_pts[-1])

def compute_prev_window_metrics(
    hist_pts: List[HistPoint],
    w: int = 60,
    ddof: int = 0,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute z60(prev) and p60(prev) using the window ending at prev point
    (i.e., use last w points ending at prev, and score the prev value).
    If not enough points, return (None, None).
    """
    if len(hist_pts) < w + 1:
        return (None, None)
    # prev point index is -2
    prev_idx = len(hist_pts) - 2
    window = hist_pts[prev_idx - (w - 1) : prev_idx + 1]  # length w
    if len(window) != w:
        return (None, None)
    window_vals = [p.value for p in window]
    prev_val = hist_pts[prev_idx].value
    z_prev = zscore(window_vals, prev_val, ddof=ddof)
    p_prev = percentile_le(window_vals, prev_val)
    return (z_prev, p_prev)

def compute_jump_fields(
    series_id: str,
    history_by_series: Dict[str, List[HistPoint]],
    z60_latest: Optional[float],
    p60_latest: Optional[float],
    ddof: int = 0,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Returns (z_delta60, p_delta60, ret1_pct)
    - z_delta60 = z60_latest - z60_prev_window
    - p_delta60 = p60_latest - p60_prev_window
    - ret1_pct  = (latest-prev)/abs(prev)*100
    """
    pts = history_by_series.get(series_id, [])
    prev, latest = last_two_points(pts)
    if prev is None or latest is None:
        return (None, None, None)

    # ret1%
    ret1_pct: Optional[float] = None
    denom = abs(prev.value)
    if denom > 0:
        ret1_pct = (latest.value - prev.value) / denom * 100.0

    # zΔ60 / pΔ60 need prev window metrics + latest metrics p60/z60
    z_prev, p_prev = compute_prev_window_metrics(pts, w=60, ddof=ddof)
    z_delta: Optional[float] = None
    p_delta: Optional[float] = None

    if z60_latest is not None and z_prev is not None:
        z_delta = z60_latest - z_prev
    if p60_latest is not None and p_prev is not None:
        p_delta = p60_latest - p_prev

    return (z_delta, p_delta, ret1_pct)


# -------------------------
# Signal rules
# -------------------------

def signal_from_rules(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float],
) -> Tuple[str, str, str]:
    """
    Returns (signal_level, tag, reason)
    Scheme A: Jump is WATCH only if >=2 of the 3 jump tests fire.
    """
    reasons: List[str] = []

    # --- Extreme ---
    if z60 is not None and abs(z60) >= 2.5:
        reasons.append("abs(Z60)>=2.5")
        return ("ALERT", "EXTREME_Z", ";".join(reasons))
    if z60 is not None and abs(z60) >= 2.0:
        reasons.append("abs(Z60)>=2")

    # --- Long extreme (P252) ---
    long_reason = None
    if p252 is not None:
        if p252 <= 2.0:
            reasons.append("P252<=2")
            return ("ALERT", "LONG_EXTREME", ";".join(reasons))
        if p252 >= 95.0 or p252 <= 5.0:
            long_reason = "P252>=95" if p252 >= 95.0 else "P252<=5"

    # --- Jump (Scheme A: 2-of-3) ---
    jump_score = 0
    jump_reasons: List[str] = []
    if z_delta60 is not None and abs(z_delta60) >= 0.75:
        jump_score += 1
        jump_reasons.append("abs(zΔ60)>=0.75")
    if p_delta60 is not None and abs(p_delta60) >= 15.0:
        jump_score += 1
        jump_reasons.append("abs(pΔ60)>=15")
    if ret1_pct is not None and abs(ret1_pct) >= 2.0:
        jump_score += 1
        jump_reasons.append("abs(ret1%)>=2")

    # If jump_score>=2 -> WATCH (even if long_extreme is present)
    if jump_score >= 2:
        reasons.extend(jump_reasons)
        # tag prefers delta if present
        tag = "JUMP_DELTA" if any("Δ60" in r for r in jump_reasons) else "JUMP_RET"
        return ("WATCH", tag, ";".join(reasons) if reasons else ";".join(jump_reasons))

    # --- If not jump-score>=2, decide remaining ---
    # If Z60 extreme already added -> WATCH
    if any(r == "abs(Z60)>=2" for r in reasons):
        return ("WATCH", "EXTREME_Z", ";".join(reasons))

    # Long extreme only -> INFO
    if long_reason is not None:
        return ("INFO", "LONG_EXTREME", long_reason)

    return ("NONE", "NA", "NA")


# -------------------------
# Rendering
# -------------------------

def md_escape(s: str) -> str:
    # Minimal escape for markdown table cells
    return s.replace("\n", " ").replace("|", "\\|")

def render_md_table(rows: List[Dict[str, Any]], headers: List[str]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        out.append("| " + " | ".join(md_escape(str(r.get(h, "NA"))) for h in headers) + " |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, help="Path to cache/stats_latest.json")
    ap.add_argument("--history-lite", required=True, help="Path to cache/history_lite.json")
    ap.add_argument("--out-md", required=True, help="Output markdown path")
    ap.add_argument("--dash-history", required=True, help="dashboard history.json path")
    ap.add_argument("--module", default="fred_cache")
    ap.add_argument("--stale-hours", type=float, default=72.0)
    args = ap.parse_args()

    run_ts_utc = utc_now_iso()

    stats = load_json(args.stats)
    stats_generated_at_utc = stats.get("generated_at_utc", "NA")
    stats_as_of_ts = stats.get("as_of_ts", "NA")
    script_version = (
        (stats.get("stats_policy") or {}).get("script_version")
        or stats.get("script_version")
        or "NA"
    )

    age_h = calc_age_hours(str(stats_as_of_ts), run_ts_utc)

    # load history lite for jump fields
    hist_by_series = load_history_lite(args.history_lite)

    # dashboard history (PrevSignal/Streak)
    dash_hist = load_dash_history(args.dash_history)
    prev_map = last_series_signal(dash_hist)

    series_obj = stats.get("series", {})
    if not isinstance(series_obj, dict):
        series_obj = {}

    rows: List[Dict[str, Any]] = []
    series_signals_for_history: Dict[str, str] = {}

    # Compute + render rows
    for series_id, sdata in series_obj.items():
        if not isinstance(series_id, str) or not isinstance(sdata, dict):
            continue

        latest = (sdata.get("latest") or {})
        metrics = (sdata.get("metrics") or {})

        data_date = latest.get("data_date", "NA")
        value = safe_float(latest.get("value"))
        source_url = latest.get("source_url", "NA")

        z60 = safe_float(metrics.get("z60"))
        p252 = safe_float(metrics.get("p252"))
        p60 = safe_float(metrics.get("p60"))

        dq = "OK"  # default; if you have dq_state, plug it here
        # (you can extend later to read cache/dq_state.json)

        # jump fields from history_lite
        z_delta60, p_delta60, ret1_pct = compute_jump_fields(
            series_id=series_id,
            history_by_series=hist_by_series,
            z60_latest=z60,
            p60_latest=p60,
            ddof=0,
        )

        signal_level, tag, reason = signal_from_rules(
            z60=z60,
            p252=p252,
            z_delta60=z_delta60,
            p_delta60=p_delta60,
            ret1_pct=ret1_pct,
        )

        prev_signal = prev_map.get(series_id, "NA")
        delta_signal = "SAME" if prev_signal == signal_level else f"{prev_signal}→{signal_level}"
        series_signals_for_history[series_id] = signal_level

        rows.append(
            {
                "Signal": signal_level,
                "Tag": tag,
                "Near": "NA",  # keep placeholder (you can re-add Near later)
                "PrevSignal": prev_signal,
                "DeltaSignal": delta_signal if prev_signal != "NA" else "NA",
                "Series": series_id,
                "DQ": dq,
                "age_h": fmt_age_h(age_h),
                "data_date": data_date,
                "value": fmt_num(value, nd=6),
                "z60": fmt_num(z60, nd=6),
                "p252": fmt_num(p252, nd=6),
                "z_delta60": fmt_num(z_delta60, nd=6),
                "p_delta60": fmt_num(p_delta60, nd=6),
                "ret1_pct": fmt_num(ret1_pct, nd=6),
                "Reason": reason,
                "Source": source_url,
                "as_of_ts": stats_as_of_ts,
            }
        )

    # Sort: Signal severity then Series
    sev = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows.sort(key=lambda r: (sev.get(r["Signal"], 9), r["Series"]))

    # Summary counts
    cnt_alert = sum(1 for r in rows if r["Signal"] == "ALERT")
    cnt_watch = sum(1 for r in rows if r["Signal"] == "WATCH")
    cnt_info = sum(1 for r in rows if r["Signal"] == "INFO")
    cnt_none = sum(1 for r in rows if r["Signal"] == "NONE")
    cnt_changed = sum(1 for r in rows if r.get("DeltaSignal") not in ("SAME", "NA"))

    # Render markdown
    md_lines: List[str] = []
    md_lines.append("# Risk Dashboard (fred_cache)\n")
    md_lines.append(f"- Summary: ALERT={cnt_alert} / WATCH={cnt_watch} / INFO={cnt_info} / NONE={cnt_none}; CHANGED={cnt_changed}")
    md_lines.append(f"- RUN_TS_UTC: `{run_ts_utc}`")
    md_lines.append(f"- STATS.generated_at_utc: `{stats_generated_at_utc}`")
    md_lines.append(f"- STATS.as_of_ts: `{stats_as_of_ts}`")
    md_lines.append(f"- script_version: `{script_version}`")
    md_lines.append(f"- stale_hours: `{fmt_num(args.stale_hours, nd=2)}`")
    md_lines.append(f"- dash_history: `{args.dash_history}`")
    md_lines.append(f"- history_lite_used_for_jump: `{args.history_lite}`")
    md_lines.append("- jump_calc: `ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev_window); pΔ60=p60(latest)-p60(prev_window)`")
    md_lines.append("- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(2-of-3: abs(zΔ60)>=0.75, abs(pΔ60)>=15, abs(ret1%)>=2 -> WATCH)`\n")

    headers = [
        "Signal","Tag","Near","PrevSignal","DeltaSignal","Series","DQ","age_h","data_date",
        "value","z60","p252","z_delta60","p_delta60","ret1_pct","Reason","Source","as_of_ts"
    ]
    md_lines.append(render_md_table(rows, headers))
    md_lines.append("")

    save_text(args.out_md, "\n".join(md_lines))

    # Append history snapshot (after render)
    append_dash_history(
        dash_hist_path=args.dash_history,
        dash_hist=dash_hist,
        run_ts_utc=run_ts_utc,
        stats_as_of_ts=str(stats_as_of_ts),
        module=args.module,
        series_signals=series_signals_for_history,
    )


if __name__ == "__main__":
    main()