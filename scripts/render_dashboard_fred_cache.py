#!/usr/bin/env python3
# scripts/render_dashboard_fred_cache.py
#
# Adds zΔ60 / pΔ60 based on history_lite.json
# - z_delta60 = z60_latest - z60_prev  (prev computed from window ending at prev point)
# - p_delta60 = p60_latest - p60_prev  (p60 computed from window ending at each point)
#
# Requires >=61 valid points in history_lite for a series, else NA.
# Jump rule:
#   WATCH if abs(zΔ60)>=0.75 OR abs(pΔ60)>=15 OR abs(ret1%)>=2
# Extreme rule (same as before):
#   WATCH if abs(Z60)>=2
#   ALERT if abs(Z60)>=2.5
#   INFO if P252>=95 or <=5
#   ALERT if P252<=2
#
# Notes:
# - Uses ddof=0 as your stats_policy indicates.
# - Percentile method: P = count(x<=value)/n * 100  (matches your stats_latest.json)

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _fmt_num(x: Optional[float], nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return "NA"
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")

def _parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _age_hours(run_ts_utc: datetime, as_of_ts: Optional[str]) -> Optional[float]:
    dt = _parse_iso_dt(as_of_ts)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = run_ts_utc - dt.astimezone(timezone.utc)
    return delta.total_seconds() / 3600.0

def _html_escape_pipes(s: str) -> str:
    return s.replace("|", "&#124;")

def _ret1_pct(prev: Optional[float], latest: Optional[float]) -> Optional[float]:
    if prev is None or latest is None:
        return None
    denom = abs(prev)
    if denom == 0:
        return None
    return (latest - prev) / denom * 100.0


def _mean_std(vals: List[float], ddof: int = 0) -> Tuple[Optional[float], Optional[float]]:
    n = len(vals)
    if n == 0:
        return None, None
    mean = sum(vals) / n
    var_denom = n - ddof
    if var_denom <= 0:
        return mean, None
    var = sum((x - mean) ** 2 for x in vals) / var_denom
    std = math.sqrt(var)
    return mean, std

def _zscore(latest: float, window: List[float], ddof: int = 0) -> Optional[float]:
    mean, std = _mean_std(window, ddof=ddof)
    if mean is None or std is None or std == 0:
        return None
    return (latest - mean) / std

def _percentile_le(latest: float, window: List[float]) -> Optional[float]:
    n = len(window)
    if n == 0:
        return None
    cnt = sum(1 for x in window if x <= latest)
    return cnt / n * 100.0


def _signal_from_rules(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float],
) -> Tuple[str, str]:
    """
    Extreme:
      WATCH if abs(Z60) >= 2
      ALERT if abs(Z60) >= 2.5
      INFO  if P252 >=95 or <=5
      ALERT if P252 <=2
    Jump:
      WATCH if abs(zΔ60)>=0.75 OR abs(pΔ60)>=15 OR abs(ret1%)>=2
    Priority: ALERT > WATCH > INFO > NONE
    """
    reasons: List[str] = []

    # Extreme
    if p252 is not None and p252 <= 2:
        reasons.append("P252<=2")
        extreme = "ALERT"
    elif z60 is not None and abs(z60) >= 2.5:
        reasons.append("abs(Z60)>=2.5")
        extreme = "ALERT"
    elif z60 is not None and abs(z60) >= 2:
        reasons.append("abs(Z60)>=2")
        extreme = "WATCH"
    elif p252 is not None and (p252 >= 95 or p252 <= 5):
        reasons.append("P252>=95" if p252 >= 95 else "P252<=5")
        extreme = "INFO"
    else:
        extreme = "NONE"

    # Jump
    jump_hit = False
    if z_delta60 is not None and abs(z_delta60) >= 0.75:
        reasons.append("abs(zΔ60)>=0.75")
        jump_hit = True
    if p_delta60 is not None and abs(p_delta60) >= 15:
        reasons.append("abs(pΔ60)>=15")
        jump_hit = True
    if ret1_pct is not None and abs(ret1_pct) >= 2:
        reasons.append("abs(ret1%)>=2")
        jump_hit = True

    jump = "WATCH" if jump_hit else "NONE"

    order = {"ALERT": 3, "WATCH": 2, "INFO": 1, "NONE": 0}
    best = extreme if order[extreme] >= order[jump] else jump
    if best == "NONE":
        return "NONE", "NA"

    # keep reasons short & stable
    return best, ";".join(reasons[:3])


def _tag_from_reason(reason: str) -> str:
    if not reason or reason == "NA":
        return "NA"
    if "ret1%" in reason:
        return "JUMP_RET"
    if "zΔ60" in reason or "pΔ60" in reason:
        return "JUMP_DELTA"
    if "abs(Z60)" in reason:
        return "EXTREME_Z"
    if "P252" in reason:
        return "LONG_EXTREME"
    return "NA"


def _load_dash_history_last_signals(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    try:
        h = _read_json(path)
        items = h.get("items", [])
        if not isinstance(items, list) or not items:
            return {}
        last = items[-1]
        ss = last.get("series_signals", {})
        if not isinstance(ss, dict):
            return {}
        out: Dict[str, str] = {}
        for k, v in ss.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out
    except Exception:
        return {}


def _extract_stats_series(stats: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Real schema:
      stats["series"][sid]["latest"]{data_date,value,source_url}
      stats["series"][sid]["metrics"]{z60,p60,p252,ret1,...}
    """
    out: Dict[str, Dict[str, Any]] = {}
    series = stats.get("series", {})
    if not isinstance(series, dict):
        return out

    for sid, node in series.items():
        if not isinstance(node, dict):
            continue

        latest = node.get("latest", {})
        metrics = node.get("metrics", {})

        if not isinstance(latest, dict):
            latest = {}
        if not isinstance(metrics, dict):
            metrics = {}

        out[sid] = {
            "data_date": latest.get("data_date"),
            "value": _to_float(latest.get("value")),
            "source_url": latest.get("source_url"),
            "as_of_ts": stats.get("as_of_ts"),
            "z60": _to_float(metrics.get("z60")),
            "p60": _to_float(metrics.get("p60")),
            "p252": _to_float(metrics.get("p252")),
        }
    return out


def _extract_series_values(history_lite: Any) -> Dict[str, List[float]]:
    """
    Returns numeric values per series (ascending order assumed by source; we don't rely on dates for speed).
    Supports:
    - {"series": {sid: {"values":[{data_date,value},...]}}}
    - {"series": {sid: [{data_date,value}, ...]}}
    - list of records [{series_id,data_date,value},...]
    """
    out: Dict[str, List[float]] = {}

    if isinstance(history_lite, dict) and isinstance(history_lite.get("series"), dict):
        for sid, node in history_lite["series"].items():
            vals = None
            if isinstance(node, dict) and isinstance(node.get("values"), list):
                vals = node["values"]
            elif isinstance(node, list):
                vals = node
            if not isinstance(vals, list):
                continue
            arr: List[float] = []
            for r in vals:
                if isinstance(r, dict):
                    v = _to_float(r.get("value"))
                    if v is not None:
                        arr.append(v)
            if arr:
                out[sid] = arr
        return out

    if isinstance(history_lite, list):
        grouped: Dict[str, List[Tuple[str, float]]] = {}
        for r in history_lite:
            if not isinstance(r, dict):
                continue
            sid = r.get("series_id")
            dd = r.get("data_date")
            v = _to_float(r.get("value"))
            if isinstance(sid, str) and isinstance(dd, str) and v is not None:
                grouped.setdefault(sid, []).append((dd, v))
        for sid, items in grouped.items():
            items.sort(key=lambda x: x[0])  # YYYY-MM-DD safe
            out[sid] = [v for _, v in items]
        return out

    return out


def _compute_prev_z_p60(values: List[float], w: int = 60, ddof: int = 0) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Given series values (ascending), compute:
      prev_value, latest_value, z_prev, p60_prev, ret1%
    Also compute z_latest/p60_latest from history if needed, but we mainly need z_prev/p60_prev for delta.

    Needs len(values) >= w+1 (>=61) to compute both windows:
      prev window: values[-(w+1):-1]  (60 points ending at prev)
      latest window: values[-w:]      (60 points ending at latest)
    """
    if len(values) < w + 1:
        return None, None, None, None, None

    prev_val = values[-2]
    latest_val = values[-1]

    prev_window = values[-(w+1):-1]
    latest_window = values[-w:]

    z_prev = _zscore(prev_val, prev_window, ddof=ddof)
    p_prev = _percentile_le(prev_val, prev_window)
    r1 = _ret1_pct(prev_val, latest_val)

    # We don't return z_latest/p_latest here; delta will use stats_latest z60/p60 as "latest".
    return prev_val, latest_val, z_prev, p_prev, r1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history-lite", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--stale-hours", type=float, required=True)
    args = ap.parse_args()

    run_ts_str = _now_utc_iso()
    run_ts_dt = _parse_iso_dt(run_ts_str)
    assert run_ts_dt is not None

    stats = _read_json(args.stats)
    hist_lite = _read_json(args.history_lite)

    stats_series = _extract_stats_series(stats)
    series_vals = _extract_series_values(hist_lite)
    prev_map = _load_dash_history_last_signals(args.history)

    ddof = 0  # your stats_policy uses ddof=0

    rows: List[Dict[str, Any]] = []
    for sid in sorted(stats_series.keys()):
        s = stats_series[sid]
        vals = series_vals.get(sid, [])

        prev_val, latest_val, z_prev, p60_prev, r1 = _compute_prev_z_p60(vals, w=60, ddof=ddof)

        z60_latest = s.get("z60")
        p60_latest = s.get("p60")  # now available from stats_latest.json
        p252 = s.get("p252")

        z_delta60 = None
        p_delta60 = None
        if z60_latest is not None and z_prev is not None:
            z_delta60 = z60_latest - z_prev
        if p60_latest is not None and p60_prev is not None:
            p_delta60 = p60_latest - p60_prev

        signal, reason = _signal_from_rules(z60_latest, p252, z_delta60, p_delta60, r1)
        tag = _tag_from_reason(reason)

        prev_sig = prev_map.get(sid, "NA")
        if prev_sig == "NA":
            delta_sig = "NA"
        else:
            delta_sig = "SAME" if prev_sig == signal else f"{prev_sig}→{signal}"

        age_h = _age_hours(run_ts_dt, s.get("as_of_ts"))

        rows.append({
            "series": sid,
            "dq": "OK",
            "age_hours": age_h,
            "data_date": s.get("data_date"),
            "value": s.get("value"),
            "z60": z60_latest,
            "p60": p60_latest,
            "p252": p252,
            "z_delta_60": z_delta60,
            "p_delta_60": p_delta60,
            "ret1_pct": r1,
            "reason": reason,
            "tag": tag,
            "near": "NA",
            "signal_level": signal,
            "prev_signal": prev_sig,
            "delta_signal": delta_sig,
            "source_url": s.get("source_url"),
            "effective_as_of_ts": s.get("as_of_ts"),
        })

    # Summary
    counts = {"ALERT": 0, "WATCH": 0, "INFO": 0, "NONE": 0}
    changed = 0
    for r in rows:
        counts[r["signal_level"]] = counts.get(r["signal_level"], 0) + 1
        if r["delta_signal"] not in ("NA", "SAME"):
            changed += 1

    script_version = stats.get("script_version")
    if not script_version and isinstance(stats.get("stats_policy"), dict):
        script_version = stats["stats_policy"].get("script_version")

    meta = {
        "run_ts_utc": run_ts_str,
        "module": args.module,
        "stale_hours": float(args.stale_hours),
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats.get("as_of_ts"),
        "script_version": script_version,
        "series_count": len(rows),
        "history_path": args.history,
        "history_lite_path": args.history_lite,
        "history_lite_used_for_jump": args.history_lite,
        "jump_calc": "ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)",
        "signal_rules": (
            "Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), "
            "P252>=95 or <=5 (INFO), P252<=2 (ALERT)); "
            "Jump(abs(zΔ60)>=0.75 OR abs(pΔ60)>=15 OR abs(ret1%)>=2 -> WATCH)"
        ),
        "summary": {
            "ALERT": counts["ALERT"],
            "WATCH": counts["WATCH"],
            "INFO": counts["INFO"],
            "NONE": counts["NONE"],
            "CHANGED": changed,
        },
        "history_lite_series": len(series_vals),
    }

    out_obj = {"meta": meta, "rows": rows}

    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    # Markdown
    md: List[str] = []
    md.append(f"# Risk Dashboard ({args.module})\n\n")
    md.append(f"- Summary: ALERT={counts['ALERT']} / WATCH={counts['WATCH']} / INFO={counts['INFO']} / NONE={counts['NONE']}; CHANGED={changed}\n")
    md.append(f"- RUN_TS_UTC: `{run_ts_str}`\n")
    md.append(f"- STATS.generated_at_utc: `{stats.get('generated_at_utc')}`\n")
    md.append(f"- STATS.as_of_ts: `{stats.get('as_of_ts')}`\n")
    md.append(f"- script_version: `{script_version}`\n")
    md.append(f"- stale_hours: `{args.stale_hours}`\n")
    md.append(f"- dash_history: `{args.history}`\n")
    md.append(f"- history_lite_used_for_jump: `{args.history_lite}`\n")
    md.append(f"- jump_calc: `{meta['jump_calc']}`\n")
    md.append(f"- signal_rules: `{meta['signal_rules']}`\n\n")

    header = ["Signal","Tag","Near","PrevSignal","DeltaSignal","Series","DQ","age_h","data_date","value","z60","p252","z_delta60","p_delta60","ret1_pct","Reason","Source","as_of_ts"]
    md.append("| " + " | ".join(header) + " |\n")
    md.append("|" + "|".join(["---"] * len(header)) + "|\n")

    for r in rows:
        md.append("| " + " | ".join([
            str(r["signal_level"]),
            str(r["tag"]),
            str(r["near"]),
            str(r["prev_signal"]),
            str(r["delta_signal"]),
            str(r["series"]),
            str(r["dq"]),
            _fmt_num(_to_float(r["age_hours"]), 2),
            str(r["data_date"]),
            _fmt_num(_to_float(r["value"]), 6),
            _fmt_num(_to_float(r["z60"]), 6),
            _fmt_num(_to_float(r["p252"]), 6),
            _fmt_num(_to_float(r["z_delta_60"]), 6),
            _fmt_num(_to_float(r["p_delta_60"]), 6),
            _fmt_num(_to_float(r["ret1_pct"]), 6),
            _html_escape_pipes(str(r["reason"])),
            str(r["source_url"]),
            str(r["effective_as_of_ts"]),
        ]) + " |\n")

    os.makedirs(os.path.dirname(args.out_md) or ".", exist_ok=True)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.writelines(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())