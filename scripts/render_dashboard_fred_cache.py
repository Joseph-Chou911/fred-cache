#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_dashboard_fred_cache.py

Goal:
- Render a risk dashboard for fred_cache using:
  A) cache/stats_latest.json (authoritative for latest level + z60/p252 when present)
  B) cache/history_lite.json (optional) to recompute "jump" metrics:
     z_delta60 / p_delta60 / ret1_pct60 (and optionally z60/p252, but only if recompute succeeds)

Key properties:
- Never overwrite good metrics from stats_latest with NA.
- history_lite loader supports multiple shapes:
  1) JSON object with {"series": {...}} style
  2) JSON array of records
  3) JSON Lines: one JSON record per line
  4) JSON Lines: each line is a JSON array of records

Records expected to contain at least:
  series_id, data_date, value
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# -----------------------
# Utilities
# -----------------------

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # tolerate "Z"
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.lower() in ("na", "nan", "none", "."):
            return None
        return float(s)
    except Exception:
        return None

def _md_escape_cell(s: Any) -> str:
    if s is None:
        return "NA"
    text = str(s)
    # Avoid breaking markdown table. We avoid '|' entirely in reasons now, but keep safe.
    text = text.replace("|", "&#124;")
    text = text.replace("\n", " ")
    return text if text != "" else "NA"

def _pct_le(values: List[float], x: float) -> float:
    # P = count(v <= x)/n * 100
    n = len(values)
    if n <= 0:
        return float("nan")
    c = 0
    for v in values:
        if v <= x:
            c += 1
    return (c / n) * 100.0

def _mean_std(values: List[float]) -> Tuple[float, float]:
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    m = sum(values) / n
    var = 0.0
    for v in values:
        var += (v - m) ** 2
    var = var / n  # ddof=0
    return m, math.sqrt(var)

def _zscore(values: List[float], x: float) -> float:
    m, sd = _mean_std(values)
    if not (sd > 0):
        return float("nan")
    return (x - m) / sd

def _ret1_pct(prev: Optional[float], cur: Optional[float]) -> float:
    if prev is None or cur is None:
        return float("nan")
    denom = abs(prev)
    if denom == 0:
        return float("nan")
    return ((cur - prev) / denom) * 100.0

# -----------------------
# Load stats_latest.json
# -----------------------

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------
# Load history_lite.json (robust)
# -----------------------

def load_history_lite_records(path: str) -> List[Dict[str, Any]]:
    """
    Return list of records: {"series_id":..., "data_date":..., "value":...}
    Supports:
      - full JSON object
      - JSON array
      - JSON lines (record per line)
      - JSON lines (array per line)
    """
    if not path or not os.path.exists(path):
        return []

    # peek first non-empty char
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    stripped = content.lstrip()
    if not stripped:
        return []

    first = stripped[0]

    # Case 1/2: whole-file JSON
    if first in ("{", "["):
        try:
            obj = json.loads(content)
            return normalize_history_lite_obj(obj)
        except Exception:
            # fall back to JSONL parsing
            pass

    # Case 3/4: JSONL
    records: List[Dict[str, Any]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        records.extend(normalize_history_lite_obj(item))
    return records

def normalize_history_lite_obj(obj: Any) -> List[Dict[str, Any]]:
    """
    Normalize various shapes into list of record dicts.
    Recognizes:
      - {"series": {"ID": [{"data_date":..,"value":..}, ...], ...}}
      - {"series": [{"series_id":..,"data_date":..,"value":..}, ...]} (rare)
      - [{"series_id":..,"data_date":..,"value":..}, ...]
      - {"series_id":..,"data_date":..,"value":..} single record
    """
    out: List[Dict[str, Any]] = []

    if obj is None:
        return out

    # If obj is a list of records
    if isinstance(obj, list):
        for it in obj:
            out.extend(normalize_history_lite_obj(it))
        return out

    # If obj is a dict with "series"
    if isinstance(obj, dict) and "series" in obj:
        s = obj.get("series")
        # series could be dict mapping series_id -> list
        if isinstance(s, dict):
            for sid, arr in s.items():
                if isinstance(arr, list):
                    for row in arr:
                        if isinstance(row, dict):
                            rec = {
                                "series_id": sid,
                                "data_date": row.get("data_date") or row.get("date") or row.get("d"),
                                "value": row.get("value") or row.get("v"),
                            }
                            out.append(rec)
                elif isinstance(arr, dict):
                    rec = {
                        "series_id": sid,
                        "data_date": arr.get("data_date") or arr.get("date") or arr.get("d"),
                        "value": arr.get("value") or arr.get("v"),
                    }
                    out.append(rec)
            return out

        # series could be a list of dict records
        if isinstance(s, list):
            for row in s:
                if isinstance(row, dict):
                    if "series_id" in row:
                        out.append({
                            "series_id": row.get("series_id"),
                            "data_date": row.get("data_date") or row.get("date") or row.get("d"),
                            "value": row.get("value") or row.get("v"),
                        })
            return out

    # If obj looks like a single record
    if isinstance(obj, dict) and ("series_id" in obj) and ("value" in obj or "v" in obj):
        out.append({
            "series_id": obj.get("series_id"),
            "data_date": obj.get("data_date") or obj.get("date") or obj.get("d"),
            "value": obj.get("value") or obj.get("v"),
        })
        return out

    return out

def build_series_values(records: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, float]]]:
    """
    Return series_id -> list[(data_date, value)] sorted by data_date asc.
    """
    m: Dict[str, List[Tuple[str, float]]] = {}
    for r in records:
        sid = (r.get("series_id") or "").strip()
        dd = (r.get("data_date") or "").strip()
        val = _safe_float(r.get("value"))
        if not sid or not dd or val is None:
            continue
        m.setdefault(sid, []).append((dd, val))
    for sid in list(m.keys()):
        # sort by date string YYYY-MM-DD; assuming normalized in your pipeline
        m[sid].sort(key=lambda x: x[0])
    return m

# -----------------------
# Signal rules (same as market_cache)
# -----------------------

@dataclass
class SignalResult:
    signal: str
    tag: str
    near: str
    reason: str

def eval_signal(z60: float, p252: float, z_d60: float, p_d60: float, r1p60: float) -> SignalResult:
    """
    Rules (same as you defined):
    Extreme:
      - abs(Z60)>=2 => WATCH
      - abs(Z60)>=2.5 => ALERT
      - P252>=95 or <=5 => INFO/WATCH (INFO if only long-extreme and no jump and abs(Z60)<2)
      - P252<=2 => ALERT
    Jump:
      - abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2
    Near:
      - within 10% of jump thresholds
    """
    # helpers
    def _is_nan(x: float) -> bool:
        return isinstance(x, float) and math.isnan(x)

    has_jump = False
    near_tags: List[str] = []
    tags: List[str] = []
    reasons: List[str] = []

    # Jump checks
    if not _is_nan(z_d60) and abs(z_d60) >= 0.75:
        has_jump = True
        tags.append("JUMP_ZD")
        reasons.append("abs(ZΔ60)>=0.75")
    elif not _is_nan(z_d60) and abs(z_d60) >= 0.75 * 0.9:
        near_tags.append("NEAR:ZΔ60")

    if not _is_nan(p_d60) and abs(p_d60) >= 15:
        has_jump = True
        tags.append("JUMP_PD")
        reasons.append("abs(PΔ60)>=15")
    elif not _is_nan(p_d60) and abs(p_d60) >= 15 * 0.9:
        near_tags.append("NEAR:PΔ60")

    if not _is_nan(r1p60) and abs(r1p60) >= 2:
        has_jump = True
        tags.append("JUMP_RET")
        reasons.append("abs(ret1%60)>=2")
    elif not _is_nan(r1p60) and abs(r1p60) >= 2 * 0.9:
        near_tags.append("NEAR:ret1%60")

    # Extreme checks
    long_extreme = False
    extreme_z = False

    if not _is_nan(z60) and abs(z60) >= 2:
        extreme_z = True
        tags.append("EXTREME_Z")
        reasons.append("abs(Z60)>=2")
    if not _is_nan(z60) and abs(z60) >= 2.5:
        tags.append("EXTREME_Z_HI")
        reasons.append("abs(Z60)>=2.5")

    if not _is_nan(p252) and (p252 >= 95 or p252 <= 5):
        long_extreme = True
        tags.append("LONG_EXTREME")
        if p252 <= 2:
            tags.append("LONG_EXTREME_HI")
            reasons.append("P252<=2")
        else:
            reasons.append("P252>=95" if p252 >= 95 else "P252<=5")

    # Determine signal level
    # ALERT cases
    if (not _is_nan(z60) and abs(z60) >= 2.5) or (not _is_nan(p252) and p252 <= 2):
        return SignalResult("ALERT", tags[0] if tags else "NA", near_tags[0] if near_tags else "NA", ";".join(reasons) if reasons else "NA")

    # WATCH cases
    if has_jump or extreme_z:
        return SignalResult("WATCH", tags[0] if tags else "NA", near_tags[0] if near_tags else "NA", ";".join(reasons) if reasons else "NA")

    # INFO: only long-extreme and no jump and abs(Z60)<2
    if long_extreme:
        # if z60 is nan, we still allow INFO (conservative)
        if (_is_nan(z60) or abs(z60) < 2) and (not has_jump):
            return SignalResult("INFO", "LONG_EXTREME", near_tags[0] if near_tags else "NA", ";".join(reasons) if reasons else "NA")

    return SignalResult("NONE", "NA", near_tags[0] if near_tags else "NA", "NA")

# -----------------------
# Main renderer
# -----------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, help="Path to cache/stats_latest.json")
    ap.add_argument("--history-lite", required=False, default="", help="Path to cache/history_lite.json (optional, for jump recompute)")
    ap.add_argument("--history", required=True, help="dashboard history.json (for Prev/Delta/Streak)")
    ap.add_argument("--out-md", required=True, help="output markdown path")
    ap.add_argument("--out-json", required=True, help="output json path (latest dashboard payload)")
    ap.add_argument("--module", required=True, help="module name, e.g., fred_cache")
    ap.add_argument("--stale-hours", type=float, default=72.0)
    args = ap.parse_args()

    run_ts_utc = _now_utc_iso()

    stats = load_json(args.stats)

    stats_gen = stats.get("generated_at_utc") or "NA"
    stats_asof = stats.get("as_of_ts") or "NA"
    script_ver = stats.get("script_version") or stats.get("stats_policy", {}).get("script_version") or "NA"

    # compute stale_hours from stats.generated_at_utc
    stale_hours = float("nan")
    dt_gen = _parse_iso(stats_gen)
    dt_run = _parse_iso(run_ts_utc)
    if dt_gen and dt_run:
        stale_hours = (dt_run - dt_gen).total_seconds() / 3600.0

    # Load stats series
    series_obj = stats.get("series", {})
    # Each series expected:
    # series[ID].latest.{data_date,value,source_url,as_of_ts}, windows.w60.{z}, windows.w252.{p}, etc.
    rows: List[Dict[str, Any]] = []

    # Optional: load history_lite and build per-series arrays for jump recompute
    hist_records = load_history_lite_records(args.history_lite) if args.history_lite else []
    hist_map = build_series_values(hist_records) if hist_records else {}

    # dashboard history for prev/delta/streak (simple format from your append script)
    prev_map: Dict[str, str] = {}
    streak_map: Dict[str, int] = {}
    try:
        if os.path.exists(args.history):
            h = load_json(args.history)
            # accept either {"schema_version":..., "items":[...]} or direct list
            items = h.get("items") if isinstance(h, dict) else h
            if isinstance(items, list) and len(items) > 0:
                last = items[-1]
                ss = last.get("series_signals", {}) if isinstance(last, dict) else {}
                if isinstance(ss, dict):
                    for k, v in ss.items():
                        prev_map[str(k)] = str(v)
    except Exception:
        prev_map = {}

    def calc_streak(series_id: str, cur_signal: str) -> int:
        # only count WATCH/ALERT
        if cur_signal not in ("WATCH", "ALERT"):
            return 0
        # naive: if prev is same WATCH/ALERT then 2 else 1
        prev = prev_map.get(series_id, "NA")
        if prev in ("WATCH", "ALERT") and prev == cur_signal:
            return 2
        if prev in ("WATCH", "ALERT") and prev != cur_signal:
            return 1
        if prev == "NA":
            return 1
        return 1

    # Build row per series
    for sid, sdata in series_obj.items():
        latest = (sdata or {}).get("latest", {}) if isinstance(sdata, dict) else {}
        data_date = latest.get("data_date") or "NA"
        value = _safe_float(latest.get("value"))
        source_url = latest.get("source_url") or "NA"
        as_of_ts = latest.get("as_of_ts") or stats_asof

        # DQ
        dq_state = stats.get("dq_state", {})
        dq = "OK"
        if isinstance(dq_state, dict):
            # if present, try map
            dq_series = dq_state.get("series", {})
            if isinstance(dq_series, dict) and sid in dq_series:
                dq = str(dq_series[sid].get("status") or "OK")
        # fallback: if metrics missing -> still OK; dq should not be guessed beyond what exists

        # Metrics from stats (baseline)
        w60 = (sdata.get("windows", {}) or {}).get("w60", {}) if isinstance(sdata, dict) else {}
        w252 = (sdata.get("windows", {}) or {}).get("w252", {}) if isinstance(sdata, dict) else {}

        z60 = _safe_float(w60.get("z"))
        p252 = _safe_float(w252.get("p"))

        # Jump metrics baseline (may not exist in fred stats)
        z_d60 = _safe_float(w60.get("z_delta"))
        p_d60 = _safe_float(w60.get("p_delta"))
        r1p60 = _safe_float(w60.get("ret1_pct"))

        # If history_lite exists and has enough points: recompute jump metrics safely
        if sid in hist_map:
            vals = hist_map[sid]
            # Need at least 2 points for ret1/deltas, and >=60/252 for z/p if desired
            if len(vals) >= 2:
                # Latest point from history, align by last entry
                prev_dd, prev_v = vals[-2]
                cur_dd, cur_v = vals[-1]

                # If data_date differs, keep stats data_date (authoritative) but compute jump from hist anyway
                # Build windows for z/p computations
                # z60 uses last 60 values; p252 uses last 252
                last60 = [v for (_, v) in vals[-60:]] if len(vals) >= 60 else []
                last252 = [v for (_, v) in vals[-252:]] if len(vals) >= 252 else []

                # recompute z60/p252 only if enough points
                z60_r = float("nan")
                p252_r = float("nan")
                if len(last60) >= 60:
                    z60_r = _zscore(last60, cur_v)
                if len(last252) >= 252:
                    p252_r = _pct_le(last252, cur_v)

                # recompute deltas based on recomputed z/p when available,
                # else fall back to stats z/p if those are present
                # compute prev z60 / prev p252 using windows ending at prev point if possible
                z_prev = float("nan")
                p_prev = float("nan")
                if len(vals) >= 61:
                    prev60 = [v for (_, v) in vals[-61:-1]]
                    if len(prev60) == 60:
                        z_prev = _zscore(prev60, prev_v)
                if len(vals) >= 253:
                    prev252 = [v for (_, v) in vals[-253:-1]]
                    if len(prev252) == 252:
                        p_prev = _pct_le(prev252, prev_v)

                # Decide final z60/p252 to use (do NOT overwrite with NaN)
                if not math.isnan(z60_r):
                    z60 = z60_r
                if not math.isnan(p252_r):
                    p252 = p252_r

                # z_delta60: use recomputed if both z's available, else keep existing
                if not math.isnan(z60) and not math.isnan(z_prev):
                    z_d60 = z60 - z_prev

                # p_delta60
                if (p252 is not None) and (not math.isnan(p252)) and (not math.isnan(p_prev)):
                    p_d60 = p252 - p_prev

                # ret1_pct60
                r1p60_r = _ret1_pct(prev_v, cur_v)
                if not math.isnan(r1p60_r):
                    r1p60 = r1p60_r

        # Normalize NAs
        def _to_num_or_nan(x: Optional[float]) -> float:
            if x is None:
                return float("nan")
            return float(x)

        z60_f = _to_num_or_nan(z60)
        p252_f = _to_num_or_nan(p252)
        z_d60_f = _to_num_or_nan(z_d60)
        p_d60_f = _to_num_or_nan(p_d60)
        r1p60_f = _to_num_or_nan(r1p60)

        sig = eval_signal(z60_f, p252_f, z_d60_f, p_d60_f, r1p60_f)

        prev_sig = prev_map.get(sid, "NA")
        if prev_sig == "NA":
            delta_sig = "NA"
        elif prev_sig == sig.signal:
            delta_sig = "SAME"
        else:
            delta_sig = f"{prev_sig}→{sig.signal}"

        streak = calc_streak(sid, sig.signal)

        # age_h: use stats_asof as time reference (same as your other dashboards)
        age_h = "NA"
        dt_asof = _parse_iso(stats_asof) or _parse_iso(as_of_ts)
        if dt_asof and dt_run:
            age_h = round((dt_run - dt_asof).total_seconds() / 3600.0, 2)

        rows.append({
            "Signal": sig.signal,
            "Tag": sig.tag if sig.tag else "NA",
            "Near": sig.near if sig.near else "NA",
            "PrevSignal": prev_sig,
            "DeltaSignal": delta_sig,
            "StreakWA": streak,
            "Series": sid,
            "DQ": dq,
            "age_h": age_h,
            "data_date": data_date,
            "value": value,
            "z60": z60_f,
            "p252": p252_f,
            "z_delta60": z_d60_f,
            "p_delta60": p_d60_f,
            "ret1_pct60": r1p60_f,
            "Reason": sig.reason,
            "Source": source_url,
            "as_of_ts": stats_asof,
        })

    # Summary counts
    def _count(sig: str) -> int:
        return sum(1 for r in rows if r["Signal"] == sig)

    changed_n = sum(1 for r in rows if r["DeltaSignal"] not in ("NA", "SAME"))
    watch_streak_ge3 = sum(1 for r in rows if (r["Signal"] in ("WATCH", "ALERT") and int(r["StreakWA"]) >= 3))

    summary = f"ALERT={_count('ALERT')} / WATCH={_count('WATCH')} / INFO={_count('INFO')} / NONE={_count('NONE')}; CHANGED={changed_n}; WATCH_STREAK>=3={watch_streak_ge3}"

    # Sort: ALERT > WATCH > INFO > NONE, then by Series
    order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows.sort(key=lambda r: (order.get(r["Signal"], 9), str(r["Series"])))

    # Build dashboard latest json (for append script)
    latest_payload = {
        "schema_version": "dashboard_latest_v1",
        "module": args.module,
        "run_ts_utc": run_ts_utc,
        "stats_generated_at_utc": stats_gen,
        "stats_as_of_ts": stats_asof,
        "script_version": script_ver,
        "summary": summary,
        "series_signals": {r["Series"]: r["Signal"] for r in rows},
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(latest_payload, f, ensure_ascii=False, indent=2)

    # Write markdown
    lines: List[str] = []
    lines.append(f"# Risk Dashboard ({args.module})")
    lines.append("")
    lines.append(f"- Summary: {summary}")
    lines.append(f"- RUN_TS_UTC: `{run_ts_utc}`")
    lines.append(f"- STATS.generated_at_utc: `{stats_gen}`")
    lines.append(f"- STATS.as_of_ts: `{stats_asof}`")
    lines.append(f"- script_version: `{script_ver}`")
    lines.append(f"- stale_hours: `{round(stale_hours, 2) if isinstance(stale_hours, float) and not math.isnan(stale_hours) else 'NA'}`")
    lines.append(f"- dash_history: `{args.history}`")
    if args.history_lite:
        lines.append(f"- history_lite_used_for_jump: `{args.history_lite}`")
        lines.append(f"- jump_calc: `recompute z60/p252/zΔ60/pΔ60/ret1%60 from history_lite values; ret1% denom = abs(prev_value) else NA`")
    lines.append(f"- streak_calc: `PrevSignal/Streak derived from history.json (dashboard outputs)`")
    lines.append(f"- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`")
    lines.append("")
    headers = [
        "Signal","Tag","Near","PrevSignal","DeltaSignal","StreakWA","Series","DQ","age_h",
        "data_date","value","z60","p252","z_delta60","p_delta60","ret1_pct60","Reason","Source","as_of_ts"
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    def fmt_num(x: Any) -> str:
        if x is None:
            return "NA"
        if isinstance(x, float) and math.isnan(x):
            return "NA"
        if isinstance(x, float):
            # compact
            return f"{x:.6g}"
        return str(x)

    for r in rows:
        cells = []
        for h in headers:
            v = r.get(h)
            if h in ("value","z60","p252","z_delta60","p_delta60","ret1_pct60"):
                cells.append(_md_escape_cell(fmt_num(v)))
            else:
                cells.append(_md_escape_cell(v))
        lines.append("| " + " | ".join(cells) + " |")

    os.makedirs(os.path.dirname(args.out_md), exist_ok=True)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()