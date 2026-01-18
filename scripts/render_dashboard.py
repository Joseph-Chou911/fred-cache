#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Render merged risk dashboard from two feeds:
#   - market_cache/{stats_latest.json, history_lite.json}   (history schema: dict w/ ["series"] usually)
#   - cache/{stats_latest.json, history_lite.json}          (history schema: list)
#
# Fixes in this version:
# 1) Robust DQ extraction (avoid "DQ = NA for everything")
# 2) Robust z_delta60 / p_delta252 extraction (multiple possible key layouts)
# 3) ret1_pct computed from HISTORY values, NOT from "delta points" mistakenly treated as percent
#
# Output: markdown table + header

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SCRIPT_FINGERPRINT = "render_dashboard_py_fix_dq_and_ret1pct_from_history_2026-01-18"


# -------------------------
# Utilities
# -------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            if math.isnan(x) or math.isinf(x):
                return None
            return float(x)
        if isinstance(x, str):
            s = x.strip()
            if s == "" or s.lower() in ("na", "nan", "null", "none"):
                return None
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        return None
    except Exception:
        return None

def get_nested(d: Any, path: List[Any]) -> Any:
    cur = d
    for p in path:
        if cur is None:
            return None
        if isinstance(p, int):
            if not isinstance(cur, list) or p < 0 or p >= len(cur):
                return None
            cur = cur[p]
        else:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
    return cur

def first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None

def parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        # Accept "Z"
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2)
    except Exception:
        return None

def hours_since(ts_iso: Optional[str], run_ts: datetime) -> Optional[float]:
    dt = parse_iso_dt(ts_iso)
    if not dt:
        return None
    delta = run_ts - dt.astimezone(timezone.utc)
    return delta.total_seconds() / 3600.0

def ymd_from_obs(obs: Dict[str, Any]) -> Optional[str]:
    # Prefer explicit date fields
    return first_non_none(
        obs.get("data_date"),
        obs.get("date"),
        get_nested(obs, ["latest", "data_date"]),
        get_nested(obs, ["latest", "date"]),
    )

# -------------------------
# History normalization
# -------------------------

def normalize_history(history_raw: Any) -> Tuple[str, str, Dict[str, List[Dict[str, Any]]]]:
    """
    Return (schema, unwrap, series_map)
    series_map: { series_id: [ {date/value/...}, ... ] }
    """
    # Case A: list schema: [ {series_id, history:[...]} , ... ]
    if isinstance(history_raw, list):
        series_map: Dict[str, List[Dict[str, Any]]] = {}
        for item in history_raw:
            if not isinstance(item, dict):
                continue
            sid = item.get("series_id") or item.get("id") or item.get("series")
            hist = item.get("history") or item.get("observations") or item.get("data")
            if isinstance(sid, str) and isinstance(hist, list):
                series_map[sid] = [h for h in hist if isinstance(h, dict)]
        return ("list", "root", series_map)

    # Case B: dict schema
    if isinstance(history_raw, dict):
        # common wrapper: {"series": {SID: {"history":[...]}, ...}}
        if isinstance(history_raw.get("series"), dict):
            series_map: Dict[str, List[Dict[str, Any]]] = {}
            for sid, node in history_raw["series"].items():
                if not isinstance(sid, str) or not isinstance(node, dict):
                    continue
                hist = node.get("history") or node.get("observations") or node.get("data")
                if isinstance(hist, list):
                    series_map[sid] = [h for h in hist if isinstance(h, dict)]
            return ("dict", "series", series_map)

        # alternative: {"history": {SID:[...]}}
        if isinstance(history_raw.get("history"), dict):
            series_map = {}
            for sid, hist in history_raw["history"].items():
                if isinstance(sid, str) and isinstance(hist, list):
                    series_map[sid] = [h for h in hist if isinstance(h, dict)]
            return ("dict", "history", series_map)

        # unknown dict schema
        return ("dict", "unknown", {})

    return ("unknown", "unknown", {})

def latest_two_from_history(series_hist: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Return (latest_obs, prev_obs) by scanning from end.
    Assumes series_hist already in chronological order in your cache;
    but we still fallback by selecting the last two observations that have numeric value.
    """
    # scan from end for numeric values
    latest = None
    prev = None
    for obs in reversed(series_hist):
        if not isinstance(obs, dict):
            continue
        v = safe_float(obs.get("value"))
        if v is None:
            continue
        if latest is None:
            latest = obs
        elif prev is None:
            prev = obs
            break
    return latest, prev


# -------------------------
# Stats parsing (robust)
# -------------------------

def extract_dq(series_node: Dict[str, Any]) -> str:
    """
    Try common dq layouts.
    Return "OK"/"WARN"/"FAIL"/"NA" etc.
    """
    # Common layouts we've seen:
    # series_node["dq"]["status"]
    # series_node["dq_state"]["status"]
    # series_node["latest"]["dq"]["status"]
    # series_node["latest"]["dq_status"]
    candidates = [
        get_nested(series_node, ["dq", "status"]),
        get_nested(series_node, ["dq_state", "status"]),
        get_nested(series_node, ["latest", "dq", "status"]),
        get_nested(series_node, ["latest", "dq_status"]),
        series_node.get("dq_status"),
        series_node.get("dq"),
    ]
    v = first_non_none(*candidates)
    if isinstance(v, str) and v.strip():
        return v.strip()
    if isinstance(v, dict):
        s = v.get("status")
        if isinstance(s, str) and s.strip():
            return s.strip()
    return "NA"

def extract_stat_num(series_node: Dict[str, Any], key: str) -> Optional[float]:
    """
    Try multiple possible locations for a stat numeric field.
    Example keys: z60, p252, z_delta60, p_delta252, ret1, ret1_pct
    """
    paths = [
        [key],
        ["stats", key],
        ["features", key],
        ["latest", key],
        ["latest", "stats", key],
        ["latest", "features", key],
    ]
    for p in paths:
        v = get_nested(series_node, p)
        f = safe_float(v)
        if f is not None:
            return f
    return None

def extract_latest_value(series_node: Dict[str, Any]) -> Optional[float]:
    return safe_float(get_nested(series_node, ["latest", "value"])) or safe_float(series_node.get("value"))

def extract_latest_date(series_node: Dict[str, Any]) -> Optional[str]:
    d = get_nested(series_node, ["latest", "data_date"]) or get_nested(series_node, ["latest", "date"]) or series_node.get("data_date")
    return d if isinstance(d, str) and d.strip() else None

def extract_source_url(series_node: Dict[str, Any]) -> str:
    u = get_nested(series_node, ["latest", "source_url"]) or series_node.get("source_url")
    if isinstance(u, str) and u.strip():
        return u.strip()
    # allow "DERIVED"
    if series_node.get("source") == "DERIVED":
        return "DERIVED"
    return "NA"

def extract_as_of_ts(series_root: Dict[str, Any]) -> Optional[str]:
    # prefer as_of_ts, fallback generated_at_utc
    a = series_root.get("as_of_ts")
    g = series_root.get("generated_at_utc")
    if isinstance(a, str) and a.strip():
        return a.strip()
    if isinstance(g, str) and g.strip():
        return g.strip()
    return None


# -------------------------
# Signal logic (your rules, minimal)
# -------------------------

def compute_signal_and_tags(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
    p_delta252: Optional[float],
    ret1_pct: Optional[float],
    data_lag_d: Optional[float],
    data_lag_thr_d: float,
) -> Tuple[str, str, str, str]:
    """
    Returns (Signal, Tag, Near, Reason)
    Signal: ALERT/WATCH/INFO/NONE
    """
    tags: List[str] = []
    near: str = "NA"
    reason: str = "NA"

    # Stale clamp rule
    stale_data = (data_lag_d is not None and data_lag_d > data_lag_thr_d)
    if stale_data:
        tags.append("STALE_DATA")
        reason = f"STALE_DATA(lag_d={data_lag_d:.0f}>thr_d={data_lag_thr_d:.0f})"

    # Jump: ONLY |ZΔ60|>=0.75 => WATCH (unless stale clamp later)
    jump = (z_delta60 is not None and abs(z_delta60) >= 0.75)
    if jump:
        tags.append("JUMP_ZD")
        if reason == "NA":
            reason = "|ZΔ60|>=0.75"

    # Extreme: |Z60|>=2 => WATCH; |Z60|>=2.5 => ALERT
    extreme_watch = (z60 is not None and abs(z60) >= 2.0)
    extreme_alert = (z60 is not None and abs(z60) >= 2.5)
    if extreme_alert:
        tags.append("EXTREME_Z")
        if reason == "NA":
            reason = "|Z60|>=2.5"
    elif extreme_watch:
        tags.append("EXTREME_Z")
        if reason == "NA":
            reason = "|Z60|>=2"

    # P extreme: P252>=95 or <=5 => INFO (only if no extreme_z and no jump)
    p_extreme = (p252 is not None and (p252 >= 95.0 or p252 <= 5.0))
    if p_extreme:
        tags.append("LONG_EXTREME")
        if reason == "NA":
            reason = "P252>=95.0 or <=5.0"

    # ret1% informational tag only (no escalation)
    if ret1_pct is not None and abs(ret1_pct) >= 2.0:
        tags.append("INFO_RET")

    # near rule: within 10% of thresholds (ZΔ60 / PΔ252 / ret1%)
    # thresholds: 0.75 for |ZΔ60|; 15 for |PΔ252|; 2 for |ret1%|
    # within 10% => >= 0.675, >= 13.5, >= 1.8
    if z_delta60 is not None and abs(z_delta60) >= 0.675:
        near = "NEAR:ZΔ60"
    elif p_delta252 is not None and abs(p_delta252) >= 13.5:
        near = "NEAR:PΔ252"
    elif ret1_pct is not None and abs(ret1_pct) >= 1.8:
        near = "NEAR:ret1%"

    # decide signal
    signal = "NONE"
    if extreme_alert:
        signal = "ALERT"
    elif extreme_watch or jump:
        signal = "WATCH"
    elif p_extreme:
        signal = "INFO"

    # stale clamp: clamp to INFO (and keep tags)
    if stale_data and signal in ("ALERT", "WATCH"):
        signal = "INFO"

    tag_str = ",".join(tags) if tags else "NA"
    return signal, tag_str, near, reason


# -------------------------
# Main merge
# -------------------------

def load_feed(feed_name: str, stats_path: str, history_path: str) -> Dict[str, Any]:
    stats = read_json(stats_path)
    history_raw = read_json(history_path)
    hist_schema, hist_unwrap, series_map = normalize_history(history_raw)

    return {
        "feed": feed_name,
        "stats_path": stats_path,
        "history_path": history_path,
        "stats": stats,
        "history_raw": history_raw,
        "history_schema": hist_schema,
        "history_unwrap": hist_unwrap,
        "history_series_map": series_map,
        "as_of_ts": extract_as_of_ts(stats) if isinstance(stats, dict) else None,
        "generated_at_utc": stats.get("generated_at_utc") if isinstance(stats, dict) else None,
        "script_version": stats.get("script_version") if isinstance(stats, dict) else None,
        "series_root": stats.get("series") if isinstance(stats, dict) else {},
    }

def compute_data_lag_days(run_ts: datetime, data_date: Optional[str]) -> Optional[float]:
    if not data_date or not isinstance(data_date, str):
        return None
    try:
        dt = datetime.fromisoformat(data_date)
    except Exception:
        try:
            dt = datetime.strptime(data_date, "%Y-%m-%d")
        except Exception:
            return None
    # treat dt as date (00:00 UTC) – coarse, OK for monitoring
    dt_utc = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    lag = run_ts - dt_utc
    return lag.total_seconds() / 86400.0

def fmt(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        # keep readable
        return f"{x:.6g}"
    return str(x)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output markdown path, e.g. dashboard/risk_dashboard_merged.md")
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    # Config (paths relative to repo root)
    stale_hours_default = 36.0
    stale_overrides = {"STLFSI4": 240.0, "NFCINONFINLEVERAGE": 240.0, "BAMLH0A0HYM2": 72.0}

    data_lag_default_days = 2.0
    data_lag_overrides_days = {
        "STLFSI4": 10.0,
        "NFCINONFINLEVERAGE": 10.0,
        "OFR_FSI": 7.0,
        "BAMLH0A0HYM2": 3.0,
        "DGS2": 3.0,
        "DGS10": 3.0,
        "VIXCLS": 3.0,
        "T10Y2Y": 3.0,
        "T10Y3M": 3.0,
    }

    feeds = [
        load_feed("market_cache", "market_cache/stats_latest.json", "market_cache/history_lite.json"),
        load_feed("cache", "cache/stats_latest.json", "cache/history_lite.json"),
    ]

    # Merge rows from both feeds (keep both if duplicate series across feeds)
    rows: List[Dict[str, Any]] = []

    for f in feeds:
        series_root = f["series_root"]
        if not isinstance(series_root, dict):
            series_root = {}

        series_map = f["history_series_map"]

        for sid, snode in series_root.items():
            if not isinstance(sid, str) or not isinstance(snode, dict):
                continue

            latest_value = extract_latest_value(snode)
            data_date = extract_latest_date(snode)
            source_url = extract_source_url(snode)
            dq = extract_dq(snode)

            # age_h from as_of_ts (stats as_of)
            as_of_ts = f["as_of_ts"]
            age_h = hours_since(as_of_ts, run_ts)

            stale_h = float(stale_overrides.get(sid, stale_hours_default))

            # data lag days (from data_date)
            lag_d = compute_data_lag_days(run_ts, data_date)
            lag_thr = float(data_lag_overrides_days.get(sid, data_lag_default_days))

            # Extract stats fields (robust)
            z60 = extract_stat_num(snode, "z60")
            p252 = extract_stat_num(snode, "p252")
            z_delta60 = extract_stat_num(snode, "z_delta60")
            p_delta252 = extract_stat_num(snode, "p_delta252")

            # --- ret1_pct FIX: compute from HISTORY (latest-prev)/prev*100 ---
            ret1_pct = None
            if sid in series_map:
                h_latest, h_prev = latest_two_from_history(series_map[sid])
                v_latest = safe_float(h_latest.get("value")) if h_latest else None
                v_prev = safe_float(h_prev.get("value")) if h_prev else None
                if v_latest is not None and v_prev not in (None, 0.0):
                    ret1_pct = (v_latest - v_prev) / v_prev * 100.0

            # If still None, try stats key "ret1_pct" (some feeds may provide correct pct already)
            if ret1_pct is None:
                ret1_pct = extract_stat_num(snode, "ret1_pct")

            # Near/Signal/Tags/Reason
            signal, tag, near, reason = compute_signal_and_tags(
                z60=z60,
                p252=p252,
                z_delta60=z_delta60,
                p_delta252=p_delta252,
                ret1_pct=ret1_pct,
                data_lag_d=lag_d,
                data_lag_thr_d=lag_thr,
            )

            rows.append({
                "Signal": signal,
                "Tag": tag,
                "Near": near,
                "PrevSignal": "NONE",   # if you want PrevSignal+Streak, keep your existing logic; not changed here
                "StreakWA": 0,
                "Feed": f["feed"],
                "Series": sid,
                "DQ": dq,
                "age_h": age_h,
                "stale_h": stale_h,
                "data_lag_d": lag_d,
                "data_lag_thr_d": lag_thr,
                "data_date": data_date,
                "value": latest_value,
                "z60": z60,
                "p252": p252,
                "z_delta60": z_delta60,
                "p_delta252": p_delta252,
                "ret1_pct": ret1_pct,
                "Reason": reason,
                "Source": source_url,
                "as_of_ts": as_of_ts or "NA",
            })

    # Stable ordering: by Signal severity then Feed then Series
    sev = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows.sort(key=lambda r: (sev.get(r["Signal"], 9), str(r["Feed"]), str(r["Series"])))

    # Render markdown
    out_lines: List[str] = []
    out_lines.append("# Risk Dashboard (merged)\n")
    out_lines.append(f"- SCRIPT_FINGERPRINT: `{SCRIPT_FINGERPRINT}`")
    out_lines.append(f"- RUN_TS_UTC: `{run_ts.isoformat()}`")
    out_lines.append(f"- stale_hours_default: `{stale_hours_default:g}`")
    out_lines.append(f"- stale_overrides: `{json.dumps(stale_overrides, ensure_ascii=False)}`")
    out_lines.append(f"- data_lag_default_days: `{data_lag_default_days:g}`")
    out_lines.append(f"- data_lag_overrides_days: `{json.dumps(data_lag_overrides_days, ensure_ascii=False)}`\n")

    # Feed metadata
    for f in feeds:
        out_lines.append(f"- {f['feed']}.stats: `{f['stats_path']}`")
        out_lines.append(f"- {f['feed']}.history: `{f['history_path']}`")
        out_lines.append(f"- {f['feed']}.history_schema: `{f['history_schema']}`")
        out_lines.append(f"- {f['feed']}.history_unwrap: `{f['history_unwrap']}`")
        out_lines.append(f"- {f['feed']}.history_series_count: `{len(f['history_series_map'])}`")
        out_lines.append(f"- {f['feed']}.as_of_ts: `{f['as_of_ts']}`")
        out_lines.append(f"- {f['feed']}.generated_at_utc: `{f['generated_at_utc']}`")
        out_lines.append(f"- {f['feed']}.script_version: `{f['script_version']}`\n")

    out_lines.append("- signal_rules: `Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); Jump(ONLY |ZΔ60|>=0.75); Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)`\n")

    headers = [
        "Signal","Tag","Near","PrevSignal","StreakWA","Feed","Series","DQ",
        "age_h","stale_h","data_lag_d","data_lag_thr_d",
        "data_date","value","z60","p252","z_delta60","p_delta252","ret1_pct",
        "Reason","Source","as_of_ts"
    ]
    out_lines.append("| " + " | ".join(headers) + " |")
    out_lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for r in rows:
        out_lines.append("| " + " | ".join([
            fmt(r.get("Signal")),
            fmt(r.get("Tag")),
            fmt(r.get("Near")),
            fmt(r.get("PrevSignal")),
            fmt(r.get("StreakWA")),
            fmt(r.get("Feed")),
            fmt(r.get("Series")),
            fmt(r.get("DQ")),
            fmt(r.get("age_h")),
            fmt(r.get("stale_h")),
            fmt(r.get("data_lag_d")),
            fmt(r.get("data_lag_thr_d")),
            fmt(r.get("data_date")),
            fmt(r.get("value")),
            fmt(r.get("z60")),
            fmt(r.get("p252")),
            fmt(r.get("z_delta60")),
            fmt(r.get("p_delta252")),
            fmt(r.get("ret1_pct")),
            fmt(r.get("Reason")),
            fmt(r.get("Source")),
            fmt(r.get("as_of_ts")),
        ]) + " |")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"OK: wrote {args.out}")

if __name__ == "__main__":
    main()