#!/usr/bin/env python3
# scripts/render_dashboard_fred_cache.py
#
# Dashboard renderer for fred_cache:
# - Z60/P252 are taken from stats_latest.json (authoritative)
# - Jump uses history_lite.json last 2 points: ret1% = (latest-prev)/abs(prev)*100
# - z_delta60 / p_delta60 remain NA (not computed in mode A)
# - Writes:
#   - dashboard_fred_cache/DASHBOARD.md (markdown table)
#   - dashboard_fred_cache/dashboard_latest.json (machine-readable rows + meta)
#
# This script is intentionally audit-first: no guessing, no silent backfills.

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Helpers
# -------------------------

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _fmt_num(x: Optional[float], nd: int = 6) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "NA"
    # keep readable
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")

def _parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        # python can parse "+00:00" style; "Z" needs handling
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _age_hours(run_ts_utc: datetime, as_of_ts: Optional[str]) -> Optional[float]:
    dt = _parse_iso_dt(as_of_ts)
    if dt is None:
        return None
    # normalize timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = run_ts_utc - dt.astimezone(timezone.utc)
    return delta.total_seconds() / 3600.0

def _html_escape_pipes(s: str) -> str:
    # GitHub markdown table treats | as cell separator.
    return s.replace("|", "&#124;")

def _signal_from_rules(
    z60: Optional[float],
    p252: Optional[float],
    ret1_pct: Optional[float],
) -> Tuple[str, str]:
    """
    Mode A rules:
    - Extreme:
        WATCH if abs(Z60) >= 2
        ALERT if abs(Z60) >= 2.5
        INFO if P252 >=95 or <=5 (but NOT ALERT unless <=2)
        ALERT if P252 <= 2
    - Jump:
        WATCH if abs(ret1_pct) >= 2
    Priority (highest to lowest): ALERT > WATCH > INFO > NONE
    Reason: first matching strongest reason (may combine two if you want; keep simple)
    """
    reasons: List[str] = []

    # Extreme rules
    if p252 is not None and p252 <= 2:
        reasons.append("P252<=2")
        extreme_level = "ALERT"
    elif z60 is not None and abs(z60) >= 2.5:
        reasons.append("abs(Z60)>=2.5")
        extreme_level = "ALERT"
    elif z60 is not None and abs(z60) >= 2:
        reasons.append("abs(Z60)>=2")
        extreme_level = "WATCH"
    elif p252 is not None and (p252 >= 95 or p252 <= 5):
        reasons.append("P252>=95" if p252 >= 95 else "P252<=5")
        extreme_level = "INFO"
    else:
        extreme_level = "NONE"

    # Jump rule
    if ret1_pct is not None and abs(ret1_pct) >= 2:
        reasons.append("abs(ret1%)>=2")
        jump_level = "WATCH"
    else:
        jump_level = "NONE"

    # Combine by severity
    order = {"ALERT": 3, "WATCH": 2, "INFO": 1, "NONE": 0}
    best = extreme_level if order[extreme_level] >= order[jump_level] else jump_level

    if best == "NONE":
        reason = "NA"
    else:
        # keep deterministic: join reasons that correspond to the chosen best level + any same-level
        # simplest: join all, but bounded.
        reason = ";".join(reasons[:3])

    return best, reason


def _tag_from_reason(reason: str) -> str:
    if reason == "NA" or not reason:
        return "NA"
    if "abs(ret1%)>=2" in reason:
        return "JUMP_RET"
    if "abs(Z60)>=" in reason:
        return "EXTREME_Z"
    if "P252" in reason:
        return "LONG_EXTREME"
    return "NA"


# -------------------------
# Load stats + history_lite
# -------------------------

def _extract_stats_series(stats: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Expect structure:
      stats["series"][SERIES_ID]["latest"]...
      stats["series"][SERIES_ID]["windows"]["w60"]["z"]
      stats["series"][SERIES_ID]["windows"]["w252"]["p"]
    """
    out: Dict[str, Dict[str, Any]] = {}
    series = stats.get("series", {})
    if not isinstance(series, dict):
        return out

    for sid, node in series.items():
        if not isinstance(node, dict):
            continue
        latest = node.get("latest", {}) if isinstance(node.get("latest", {}), dict) else {}
        w = node.get("windows", {}) if isinstance(node.get("windows", {}), dict) else {}
        w60 = w.get("w60", {}) if isinstance(w.get("w60", {}), dict) else {}
        w252 = w.get("w252", {}) if isinstance(w.get("w252", {}), dict) else {}

        out[sid] = {
            "data_date": latest.get("data_date"),
            "value": _to_float(latest.get("value")),
            "source_url": latest.get("source_url"),
            "as_of_ts": latest.get("as_of_ts") or stats.get("as_of_ts"),
            "dq": _safe_get(stats, "dq_state", sid),  # optional if present
            "z60": _to_float(w60.get("z")),
            "p252": _to_float(w252.get("p")),
        }
    return out


def _extract_last2_from_history_lite(history_lite: Any) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """
    Returns mapping: series_id -> (prev_value, latest_value) from history_lite.
    Supports common formats:
    - dict with "series": {sid: {"values":[{"data_date":..., "value":...}, ...]}}
    - dict with "series": {sid: [{"data_date":..., "value":...}, ...]}
    - list of records [{series_id, data_date, value}, ...]  (will group and take last2 by data_date)
    """
    out: Dict[str, Tuple[Optional[float], Optional[float]]] = {}

    # Format A: {"series": {...}}
    if isinstance(history_lite, dict) and "series" in history_lite and isinstance(history_lite["series"], dict):
        for sid, node in history_lite["series"].items():
            vals = None
            if isinstance(node, dict) and isinstance(node.get("values"), list):
                vals = node.get("values")
            elif isinstance(node, list):
                vals = node
            if not isinstance(vals, list) or len(vals) < 2:
                continue
            # assume already ordered by data_date asc in your pipeline; take last two
            v_prev = _to_float(vals[-2].get("value") if isinstance(vals[-2], dict) else None)
            v_last = _to_float(vals[-1].get("value") if isinstance(vals[-1], dict) else None)
            out[sid] = (v_prev, v_last)
        return out

    # Format B: list of records
    if isinstance(history_lite, list):
        grouped: Dict[str, List[Tuple[str, Optional[float]]]] = {}
        for r in history_lite:
            if not isinstance(r, dict):
                continue
            sid = r.get("series_id") or r.get("series") or r.get("id")
            dd = r.get("data_date")
            val = _to_float(r.get("value"))
            if not isinstance(sid, str) or not isinstance(dd, str):
                continue
            grouped.setdefault(sid, []).append((dd, val))
        for sid, items in grouped.items():
            # sort by data_date (string YYYY-MM-DD safe)
            items.sort(key=lambda x: x[0])
            if len(items) >= 2:
                out[sid] = (items[-2][1], items[-1][1])
        return out

    return out


def _ret1_pct(prev: Optional[float], latest: Optional[float]) -> Optional[float]:
    if prev is None or latest is None:
        return None
    denom = abs(prev)
    if denom == 0:
        return None
    return (latest - prev) / denom * 100.0


# -------------------------
# Dashboard history (PrevSignal / Streak)
# -------------------------

def _load_dash_history(path: str) -> Dict[str, str]:
    """
    dashboard_fred_cache/history.json schema (dash_history_v1):
      {"schema_version":"dash_history_v1","items":[{... "series_signals":{sid:"WATCH"...}}]}
    We only need last item's series_signals.
    """
    if not os.path.exists(path):
        return {}
    try:
        h = _read_json(path)
        items = h.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            return {}
        last = items[-1]
        ss = last.get("series_signals", {})
        if isinstance(ss, dict):
            return {k: v for k, v in ss.items() if isinstance(k, str) and isinstance(v, str)}
        return {}
    except Exception:
        return {}


def _streak(prev_map: Dict[str, str], sid: str, today: str) -> int:
    """
    Mode A minimal streak:
    - if prev signal equals today and today is WATCH -> 2 (we let append script keep true streak);
      Here we only compute "streak_wa" as:
        0 if today != WATCH
        2 if prev == WATCH and today == WATCH else 1 if today == WATCH
    You can expand later; your append_dashboard_history.py is the real source of truth.
    """
    if today != "WATCH":
        return 0
    prev = prev_map.get(sid)
    if prev == "WATCH":
        return 2
    return 1


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history-lite", required=True)
    ap.add_argument("--history", required=True)  # dashboard history json
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
    last2 = _extract_last2_from_history_lite(hist_lite)

    prev_signals = _load_dash_history(args.history)

    rows: List[Dict[str, Any]] = []

    # stable ordering
    for sid in sorted(stats_series.keys()):
        s = stats_series[sid]

        data_date = s.get("data_date")
        value = s.get("value")
        source_url = s.get("source_url")

        z60 = s.get("z60")
        p252 = s.get("p252")

        # jump (ret1%)
        prev_v, last_v = last2.get(sid, (None, None))
        ret1pct = _ret1_pct(prev_v, last_v)

        signal, reason = _signal_from_rules(z60, p252, ret1pct)
        tag = _tag_from_reason(reason)

        prev_sig = prev_signals.get(sid, "NA")
        delta_sig = "NA"
        if prev_sig != "NA":
            delta_sig = "SAME" if prev_sig == signal else f"{prev_sig}→{signal}"

        age_h = _age_hours(run_ts_dt, s.get("as_of_ts") or stats.get("as_of_ts"))

        row = {
            "series": sid,
            "dq": "OK",  # if you later want dq_state integration
            "age_hours": age_h,
            "data_date": data_date,
            "value": value,
            "z60": z60,
            "p252": p252,
            "z_delta_60": None,   # mode A: not computed
            "p_delta_60": None,   # mode A: not computed
            "ret1_pct": ret1pct,  # note: renamed logically, but MD column keeps ret1_pct60 for compatibility if you want
            "reason": reason,
            "tag": tag,
            "near": "NA",         # mode A: keep NA; you can re-add near later
            "signal_level": signal,
            "prev_signal": prev_sig,
            "delta_signal": delta_sig,
            "streak_wa": _streak(prev_signals, sid, signal),
            "source_url": source_url,
            "effective_as_of_ts": s.get("as_of_ts") or stats.get("as_of_ts"),
        }
        rows.append(row)

    # Summary
    counts = {"ALERT": 0, "WATCH": 0, "INFO": 0, "NONE": 0}
    changed = 0
    watch_streak_ge3 = 0

    for r in rows:
        counts[r["signal_level"]] = counts.get(r["signal_level"], 0) + 1
        if r["delta_signal"] not in ("NA", "SAME"):
            changed += 1
        if isinstance(r.get("streak_wa"), int) and r["streak_wa"] >= 3:
            watch_streak_ge3 += 1

    # Meta (MUST include run_ts_utc / stats_as_of_ts / module for append script)
    meta = {
        "run_ts_utc": run_ts_str,
        "module": args.module,
        "stale_hours": float(args.stale_hours),
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats.get("as_of_ts"),
        "script_version": stats.get("script_version") or _safe_get(stats, "stats_policy", "script_version"),
        "series_count": len(rows),
        "history_path": args.history,
        "history_lite_path": args.history_lite,
        "history_lite_used_for_jump": args.history_lite,
        "streak_calc": "PrevSignal/Streak derived from history.json (dashboard outputs)",
        "jump_calc": "ret1% = (latest-prev)/abs(prev)*100 (from history_lite last 2 points)",
        "signal_rules": (
            "Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), "
            "P252>=95 or <=5 (INFO), P252<=2 (ALERT)); "
            "Jump(abs(ret1%)>=2 -> WATCH)"
        ),
        "summary": {
            "ALERT": counts["ALERT"],
            "WATCH": counts["WATCH"],
            "INFO": counts["INFO"],
            "NONE": counts["NONE"],
            "CHANGED": changed,
            "WATCH_STREAK_GE3": watch_streak_ge3,
        },
    }

    out_obj = {"meta": meta, "rows": rows}

    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    # Markdown output
    md_lines: List[str] = []
    md_lines.append(f"# Risk Dashboard ({args.module})\n")
    md_lines.append(
        f"- Summary: ALERT={counts['ALERT']} / WATCH={counts['WATCH']} / INFO={counts['INFO']} / NONE={counts['NONE']}\n"
    )
    md_lines.append(f"- RUN_TS_UTC: `{run_ts_str}`\n")
    md_lines.append(f"- STATS.generated_at_utc: `{meta.get('stats_generated_at_utc')}`\n")
    md_lines.append(f"- STATS.as_of_ts: `{meta.get('stats_as_of_ts')}`\n")
    md_lines.append(f"- script_version: `{meta.get('script_version')}`\n")
    md_lines.append(f"- stale_hours: `{args.stale_hours}`\n")
    md_lines.append(f"- dash_history: `{args.history}`\n")
    md_lines.append(f"- history_lite_used_for_jump: `{args.history_lite}`\n")
    md_lines.append(f"- jump_calc: `{meta.get('jump_calc')}`\n")
    md_lines.append(f"- signal_rules: `{meta.get('signal_rules')}`\n\n")

    header = [
        "Signal", "Tag", "Near", "PrevSignal", "DeltaSignal", "StreakWA",
        "Series", "DQ", "age_h", "data_date", "value", "z60", "p252",
        "z_delta60", "p_delta60", "ret1_pct", "Reason", "Source", "as_of_ts"
    ]
    md_lines.append("| " + " | ".join(header) + " |\n")
    md_lines.append("|" + "|".join(["---"] * len(header)) + "|\n")

    for r in rows:
        reason = _html_escape_pipes(str(r.get("reason", "NA")))
        line = [
            str(r.get("signal_level", "NA")),
            str(r.get("tag", "NA")),
            str(r.get("near", "NA")),
            str(r.get("prev_signal", "NA")),
            str(r.get("delta_signal", "NA")),
            str(r.get("streak_wa", 0)),
            str(r.get("series", "NA")),
            str(r.get("dq", "NA")),
            _fmt_num(_to_float(r.get("age_hours")), 2),
            str(r.get("data_date", "NA")),
            _fmt_num(_to_float(r.get("value")), 6),
            _fmt_num(_to_float(r.get("z60")), 6),
            _fmt_num(_to_float(r.get("p252")), 6),
            "NA",  # z_delta60 (mode A)
            "NA",  # p_delta60 (mode A)
            _fmt_num(_to_float(r.get("ret1_pct")), 6),
            reason,
            str(r.get("source_url", "NA")),
            str(r.get("effective_as_of_ts", "NA")),
        ]
        md_lines.append("| " + " | ".join(line) + " |\n")

    os.makedirs(os.path.dirname(args.out_md) or ".", exist_ok=True)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.writelines(md_lines)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())