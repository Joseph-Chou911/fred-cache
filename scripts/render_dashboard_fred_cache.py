#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------
# Utilities
# -----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def try_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def safe_abs(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return abs(x)

def fmt_num(x: Optional[float], nd=6) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "NA"
    # keep it compact
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")

def get_window(stats_series: Dict[str, Any], w: str) -> Optional[Dict[str, Any]]:
    # stats_latest.json: series -> windows -> w60/w252
    wmap = stats_series.get("windows", {})
    if not isinstance(wmap, dict):
        return None
    return wmap.get(w)

def get_stats_script_version(stats: Dict[str, Any]) -> str:
    # some variants store script_version at top-level; some store under stats_policy.script_version
    sv = stats.get("script_version")
    if sv:
        return str(sv)
    sp = stats.get("stats_policy", {})
    if isinstance(sp, dict) and sp.get("script_version"):
        return str(sp.get("script_version"))
    return "NA"

def parse_history_lite_for_last_two_values(history_lite_path: str) -> Dict[str, List[Tuple[str, float]]]:
    """
    Return mapping: series_id -> list of (data_date, value) sorted by data_date asc
    Supports:
      - JSON array: [{"series_id":..., "data_date":..., "value":...}, ...]
      - NDJSON: one json object per line
      - dict with key 'series' or similar is NOT assumed (we keep it simple).
    """
    out: Dict[str, List[Tuple[str, float]]] = {}

    with open(history_lite_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if not raw:
        return out

    # Try JSON array first
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                for rec in arr:
                    if not isinstance(rec, dict):
                        continue
                    sid = rec.get("series_id") or rec.get("series") or rec.get("Series")
                    dd = rec.get("data_date") or rec.get("date") or rec.get("Date")
                    val = try_float(rec.get("value") if "value" in rec else rec.get("Value"))
                    if not sid or not dd or val is None:
                        continue
                    out.setdefault(str(sid), []).append((str(dd), float(val)))
        except Exception:
            pass
    else:
        # NDJSON
        lines = raw.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            sid = rec.get("series_id") or rec.get("series") or rec.get("Series")
            dd = rec.get("data_date") or rec.get("date") or rec.get("Date")
            val = try_float(rec.get("value") if "value" in rec else rec.get("Value"))
            if not sid or not dd or val is None:
                continue
            out.setdefault(str(sid), []).append((str(dd), float(val)))

    # sort + dedup by date (keep last value if duplicate dates)
    for sid, rows in out.items():
        rows.sort(key=lambda x: x[0])
        ded: Dict[str, float] = {}
        for dd, v in rows:
            ded[dd] = v
        out[sid] = [(dd, ded[dd]) for dd in sorted(ded.keys())]

    return out

def calc_ret1_pct(latest: Optional[float], prev: Optional[float]) -> Optional[float]:
    if latest is None or prev is None:
        return None
    denom = abs(prev)
    if denom == 0:
        return None
    return (latest - prev) / denom * 100.0

# -----------------------------
# Signal logic
# -----------------------------

def classify_signal(
    z60: Optional[float],
    p252: Optional[float],
    ret1_pct: Optional[float],
) -> Tuple[str, str, str, str]:
    """
    Return: (signal, tag, near, reason)
    Implements rules (partial for fred_cache):
      - Extreme:
        abs(Z60)>=2 -> WATCH
        abs(Z60)>=2.5 -> ALERT
        P252>=95 or <=5 -> INFO/WATCH (if abs(Z60)>=2 treat higher)
        P252<=2 -> ALERT
      - Jump:
        abs(ret1%60)>=2 -> WATCH (tag=JUMP_RET)
      - INFO if only long-extreme and no jump and abs(Z60)<2
    Note: fred_cache doesn't reliably produce z_delta/p_delta; we use ret1_pct as the "sudden move" detector.
    """
    tag = "NA"
    near = "NA"
    reason = "NA"

    az = safe_abs(z60)
    ap = p252
    ar = safe_abs(ret1_pct)

    # Jump first (sudden move)
    if ar is not None and ar >= 2.0:
        return ("WATCH", "JUMP_RET", "NA", "abs(ret1%60)>=2")

    # Extreme by Z
    if az is not None and az >= 2.5:
        return ("ALERT", "EXTREME_Z", "NA", "abs(Z60)>=2.5")
    if az is not None and az >= 2.0:
        # near jump threshold check (within 10% of 2.0 -> 1.8)
        if ar is not None and ar >= 1.8:
            near = "NEAR:ret1%60"
        return ("WATCH", "EXTREME_Z", near, "abs(Z60)>=2")

    # Long extreme by percentile
    if ap is not None:
        if ap <= 2.0:
            return ("ALERT", "LONG_EXTREME", "NA", "P252<=2")
        if ap >= 95.0 or ap <= 5.0:
            # Only long-extreme without abs(Z60)>=2 and no jump => INFO
            return ("INFO", "LONG_EXTREME", "NA", "P252>=95" if ap >= 95.0 else "P252<=5")

    return ("NONE", "NA", "NA", "NA")

# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, help="Path to cache/stats_latest.json")
    ap.add_argument("--history-lite", required=True, help="Path to cache/history_lite.json (for jump calc)")
    ap.add_argument("--history", required=True, help="Path to dashboard_fred_cache/history.json (used only for path display; append script updates it)")
    ap.add_argument("--out-md", required=True, help="Output markdown path")
    ap.add_argument("--out-json", required=True, help="Output json path for append_dashboard_history.py")
    ap.add_argument("--module", required=True, help="Module name, e.g., fred_cache")
    ap.add_argument("--stale-hours", type=float, default=72.0)
    args = ap.parse_args()

    run_ts_utc = utc_now_iso()
    stats = load_json(args.stats)

    stats_generated = stats.get("generated_at_utc", "NA")
    stats_as_of = stats.get("as_of_ts", "NA")
    script_version = get_stats_script_version(stats)

    # Parse history_lite to get ret1% (sudden move)
    hist_map = parse_history_lite_for_last_two_values(args.history_lite)

    series_obj = stats.get("series", {})
    if not isinstance(series_obj, dict):
        raise SystemExit("stats_latest.json missing top-level 'series' dict")

    rows: List[Dict[str, Any]] = []
    series_signals: Dict[str, str] = {}

    for sid, sdata in series_obj.items():
        if not isinstance(sdata, dict):
            continue

        latest = sdata.get("latest", {}) if isinstance(sdata.get("latest"), dict) else {}
        data_date = latest.get("data_date", "NA")
        value = try_float(latest.get("value"))
        source_url = latest.get("source_url", "NA")
        as_of_ts = latest.get("as_of_ts", stats_as_of)  # fallback to top-level as_of_ts

        # DQ is from dq_state.json normally; but stats_latest may not carry it.
        # We'll mark OK unless caller enriches; you can wire dq_state later if you want.
        dq = "OK"

        # Pull z60 from w60.z; pull p252 from w252.p
        w60 = get_window(sdata, "w60") or {}
        w252 = get_window(sdata, "w252") or {}

        z60 = try_float(w60.get("z"))
        p252 = try_float(w252.get("p"))

        # Jump calc via history_lite (ret1% using abs(prev) denom)
        ret1_pct60 = None
        if sid in hist_map and len(hist_map[sid]) >= 2:
            prev_dd, prev_v = hist_map[sid][-2]
            last_dd, last_v = hist_map[sid][-1]
            # Ensure latest aligns with last point; if not, still compute using last two points we have
            ret1_pct60 = calc_ret1_pct(last_v, prev_v)

        signal, tag, near, reason = classify_signal(z60, p252, ret1_pct60)

        series_signals[str(sid)] = signal

        rows.append({
            "Signal": signal,
            "Tag": tag,
            "Near": near,
            "Series": str(sid),
            "DQ": dq,
            "data_date": data_date,
            "value": value,
            "z60": z60,
            "p252": p252,
            "ret1_pct60": ret1_pct60,
            "Reason": reason,
            "Source": source_url,
            "as_of_ts": as_of_ts,
        })

    # Summary stats
    cnt = {"ALERT": 0, "WATCH": 0, "INFO": 0, "NONE": 0}
    for r in rows:
        cnt[r["Signal"]] = cnt.get(r["Signal"], 0) + 1

    # Note: CHANGED / streak are calculated from dashboard history; append script handles that.
    # We keep Summary line in markdown minimal here; your renderer can be expanded later if you want.

    # Write dashboard_latest.json for append_dashboard_history.py
    out_json_obj = {
        "schema_version": "dashboard_latest_v1",
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of,
        "module": args.module,
        "series_signals": series_signals,
    }
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out_json_obj, f, ensure_ascii=False, indent=2)

    # Write markdown
    os.makedirs(os.path.dirname(args.out_md) or ".", exist_ok=True)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(f"# Risk Dashboard ({args.module})\n\n")
        f.write(f"- Summary: ALERT={cnt['ALERT']} / WATCH={cnt['WATCH']} / INFO={cnt['INFO']} / NONE={cnt['NONE']}\n")
        f.write(f"- RUN_TS_UTC: `{run_ts_utc}`\n")
        f.write(f"- STATS.generated_at_utc: `{stats_generated}`\n")
        f.write(f"- STATS.as_of_ts: `{stats_as_of}`\n")
        f.write(f"- script_version: `{script_version}`\n")
        f.write(f"- stale_hours: `{args.stale_hours}`\n")
        f.write(f"- dash_history: `{args.history}`\n")
        f.write(f"- history_lite_used_for_jump: `{args.history_lite}`\n")
        f.write(f"- jump_calc: `ret1% = (latest-prev)/abs(prev)*100 (from history_lite last 2 points)`\n")
        f.write(f"- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(abs(ret1%60)>=2 -> WATCH)`\n\n")

        headers = [
            "Signal","Tag","Near","Series","DQ","data_date","value","z60","p252","ret1_pct60","Reason","Source","as_of_ts"
        ]
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"]*len(headers)) + "|\n")
        for r in rows:
            f.write("| " + " | ".join([
                str(r["Signal"]),
                str(r["Tag"]),
                str(r["Near"]),
                str(r["Series"]),
                str(r["DQ"]),
                str(r["data_date"]),
                fmt_num(r["value"], nd=6),
                fmt_num(r["z60"], nd=6),
                fmt_num(r["p252"], nd=6),
                fmt_num(r["ret1_pct60"], nd=6),
                str(r["Reason"]),
                str(r["Source"]),
                str(r["as_of_ts"]),
            ]) + " |\n")

if __name__ == "__main__":
    main()