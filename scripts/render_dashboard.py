#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Dashboard renderer (MVP + signals v8)  [A+B+C compatible]
# - Tag + Near
# - PrevSignal/Streak from dashboard/history.json
#   * STRICT: only items with matching (module + ruleset_id) are used
#   * Legacy items missing ruleset_id are ignored (方案 C)
# - DeltaSignal (Prev → Today, SAME, NA)
# - Summary counts (ALERT/WATCH/INFO/NONE, CHANGED, WATCH_STREAK>=3)
# - Direction map (HIGH/LOW/RANGE/MOVE) + DirNote (risk-bias annotation)
# - Adds StreakHist (history-only) to make audit clearer
# - Markdown table safety: escape '|'
#
# Inputs:
#   - stats_latest.json
#   - dashboard/history.json
#
# Outputs:
#   - dashboard/DASHBOARD.md
#   - dashboard/dashboard_latest.json  (meta, rows, series_signals)

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_STALE_HOURS = 36.0

# Extreme thresholds
Z60_WATCH_ABS = 2.0
Z60_ALERT_ABS = 2.5

P252_EXTREME_HI = 95.0
P252_EXTREME_LO = 5.0
P252_ALERT_LO = 2.0

# Jump thresholds
ZDELTA60_JUMP_ABS = 0.75
PDELTA60_JUMP_ABS = 15.0
RET1PCT60_JUMP_ABS = 2.0

NEAR_FRAC = 0.10
STREAK_HISTORY_MAX = 120

DEFAULT_RULESET_ID = "signals_v8"
DEFAULT_SCRIPT_FINGERPRINT = "render_dashboard_py_signals_v8"

# -------------------------
# Direction map (minimal extension)
# -------------------------
DIRECTION_MAP: Dict[str, str] = {
    "OFR_FSI": "HIGH",
    "STLFSI4": "HIGH",
    "BAMLH0A0HYM2": "HIGH",
    "NFCINONFINLEVERAGE": "HIGH",

    "SP500": "HIGH",
    "DJIA": "HIGH",
    "NASDAQCOM": "HIGH",

    "VIX": "HIGH",
    "VIXCLS": "HIGH",

    "DTWEXBGS": "HIGH",
    "DCOILWTICO": "HIGH",

    "HYG_IEF_RATIO": "LOW",

    # rates: movement-only in MVP to avoid direction misread
    "DGS2": "MOVE",
    "DGS10": "MOVE",
    "T10Y2Y": "MOVE",
    "T10Y3M": "MOVE",
}


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts2 = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts2)
    except Exception:
        return None


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


def fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        s = f"{x:.{nd}f}"
        return s.rstrip("0").rstrip(".")
    return str(x)


def md_escape_cell(x: Any) -> str:
    s = str(x) if x is not None else "NA"
    s = s.replace("|", "&#124;")
    s = s.replace("\n", "<br>")
    return s


def safe_abs(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return abs(float(x))
    return None


def is_near(abs_val: Optional[float], thr: float, near_frac: float) -> bool:
    if abs_val is None:
        return False
    lo = (1.0 - near_frac) * thr
    return (abs_val >= lo) and (abs_val < thr)


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
            reasons.append(f"abs(Z60)>={Z60_WATCH_ABS:g}")
            tags.append("EXTREME_Z")
        if az60 >= Z60_ALERT_ABS:
            z60_alert = True
            reasons.append(f"abs(Z60)>={Z60_ALERT_ABS:g}")

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
        reasons.append(f"abs(ZΔ60)>={ZDELTA60_JUMP_ABS:g}")
        tags.append("JUMP_ZD")
        jump_hits += 1
        has_zdelta_jump = True
    else:
        if is_near(azd, ZDELTA60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:ZΔ60")

    if apd is not None and apd >= PDELTA60_JUMP_ABS:
        reasons.append(f"abs(PΔ60)>={PDELTA60_JUMP_ABS:g}")
        tags.append("JUMP_P")
        jump_hits += 1
    else:
        if is_near(apd, PDELTA60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:PΔ60")

    if ar1p is not None and ar1p >= RET1PCT60_JUMP_ABS:
        reasons.append(f"abs(ret1%60)>={RET1PCT60_JUMP_ABS:g}")
        tags.append("JUMP_RET")
        jump_hits += 1
    else:
        if is_near(ar1p, RET1PCT60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:ret1%60")

    # Level assignment (signals_v8 / 改法 B)
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

    # dedup tags preserving order
    seen = set()
    tags2: List[str] = []
    for t in tags:
        if t not in seen:
            tags2.append(t)
            seen.add(t)
    tag_str = ",".join(tags2) if tags2 else "NA"

    near_str = ",".join(nears) if nears else "NA"
    return level, reason_str, tag_str, near_str


def load_dashboard_history(path: Optional[str]) -> List[Dict[str, Any]]:
    if not path:
        return []
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        items = obj.get("items", [])
        if isinstance(items, list):
            snaps = [x for x in items if isinstance(x, dict)]
            return snaps[-STREAK_HISTORY_MAX:]
        return []
    except Exception:
        return []


def build_series_signal_timeline(
    history_snaps: List[Dict[str, Any]],
    module: str,
    ruleset_id: str,
) -> Dict[str, List[str]]:
    timeline: Dict[str, List[str]] = {}
    for snap in history_snaps:
        if snap.get("module") != module:
            continue
        if snap.get("ruleset_id") != ruleset_id:
            # legacy items missing ruleset_id ignored
            continue
        sigs = snap.get("series_signals")
        if not isinstance(sigs, dict):
            continue
        for sid, sig in sigs.items():
            if isinstance(sid, str) and isinstance(sig, str):
                timeline.setdefault(sid, []).append(sig)
    return timeline


def compute_prev_and_streaks(
    sid: str,
    today_signal: str,
    timeline: Dict[str, List[str]],
) -> Tuple[str, int, int]:
    """
    Returns (prev_signal, streak_hist, streak_incl_today)

    streak_hist:
      - history-only consecutive WATCH/ALERT ending at last history item
    streak_incl_today:
      - if today is WATCH/ALERT: 1 + (history tail consecutive WATCH/ALERT)
      - else 0
    """
    hist = timeline.get(sid, [])
    prev = hist[-1] if len(hist) >= 1 else "NA"

    # history-only streak
    streak_hist = 0
    for s in reversed(hist):
        if s in ("WATCH", "ALERT"):
            streak_hist += 1
        else:
            break

    # incl-today streak (your previous StreakWA behavior)
    if today_signal not in ("WATCH", "ALERT"):
        streak_incl_today = 0
    else:
        streak_incl_today = 1 + streak_hist

    return prev, streak_hist, streak_incl_today


def compute_delta_signal(prev: str, today: str) -> str:
    if prev == "NA" or prev is None or prev == "":
        return "NA"
    if prev == today:
        return "SAME"
    return f"{prev}→{today}"


def compute_summary_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"ALERT": 0, "WATCH": 0, "INFO": 0, "NONE": 0}
    changed = 0
    watch_streak_ge3 = 0

    for r in rows:
        lvl = r.get("signal_level", "NONE")
        if lvl in counts:
            counts[lvl] += 1

        d = r.get("delta_signal", "NA")
        if isinstance(d, str) and d not in ("NA", "SAME"):
            changed += 1

        if r.get("signal_level") == "WATCH":
            try:
                if int(r.get("streak_wa") or 0) >= 3:
                    watch_streak_ge3 += 1
            except Exception:
                pass

    counts["CHANGED"] = changed
    counts["WATCH_STREAK_GE3"] = watch_streak_ge3
    return counts


def get_direction(series_id: str) -> str:
    d = DIRECTION_MAP.get(series_id)
    if d in ("HIGH", "LOW", "RANGE", "MOVE"):
        return d
    return "MOVE"


def parse_tags(tag_str: str) -> List[str]:
    if not tag_str or tag_str == "NA":
        return []
    parts = [p.strip() for p in tag_str.split(",")]
    return [p for p in parts if p]


def parse_p252_tail(reason: str) -> str:
    if not reason or reason == "NA":
        return "NA"
    if "P252>=" in reason:
        return "HI"
    if "P252<=" in reason:
        return "LO"
    return "NA"


def compute_dir_note(direction: str, reason: str, tags: List[str]) -> str:
    if direction == "MOVE":
        return "MOVE_ONLY"
    if direction == "RANGE":
        return "RANGE_SENSITIVE"

    p_tail = parse_p252_tail(reason)

    if direction in ("HIGH", "LOW") and p_tail in ("HI", "LO"):
        if direction == "HIGH":
            return "RISK_BIAS_UP" if p_tail == "HI" else "RISK_BIAS_DOWN"
        return "RISK_BIAS_UP" if p_tail == "LO" else "RISK_BIAS_DOWN"

    if direction in ("HIGH", "LOW"):
        if any(t.startswith("JUMP_") for t in tags) or ("abs(" in (reason or "")):
            return "DIR_UNCERTAIN_ABS"

    return "NA"


def write_outputs(
    out_md: str,
    out_json: str,
    meta: Dict[str, Any],
    rows: List[Dict[str, Any]],
    series_signals: Dict[str, str],
) -> None:
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)

    payload = {"meta": meta, "rows": rows, "series_signals": series_signals}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    summary = compute_summary_counts(rows)

    lines: List[str] = []
    lines.append(f"# Risk Dashboard ({meta.get('module','')})")
    lines.append("")
    lines.append(
        f"- Summary: ALERT={summary['ALERT']} / WATCH={summary['WATCH']} / INFO={summary['INFO']} / NONE={summary['NONE']}; "
        f"CHANGED={summary['CHANGED']}; WATCH_STREAK>=3={summary['WATCH_STREAK_GE3']}"
    )
    lines.append(f"- SCRIPT_FINGERPRINT: `{meta.get('script_fingerprint','')}`")
    lines.append(f"- RULESET_ID: `{meta.get('ruleset_id','')}`")
    lines.append(f"- RUN_TS_UTC: `{meta.get('run_ts_utc','')}`")
    lines.append(f"- STATS.generated_at_utc: `{meta.get('stats_generated_at_utc','')}`")
    lines.append(f"- STATS.as_of_ts: `{meta.get('stats_as_of_ts','')}`")
    lines.append(f"- script_version: `{meta.get('script_version','')}`")
    lines.append(f"- stale_hours: `{meta.get('stale_hours','')}`")
    lines.append(f"- stats_path: `{meta.get('stats_path','')}`")
    lines.append(f"- dash_history: `{meta.get('dash_history_path','NA')}`")
    lines.append(f"- streak_calc: `{meta.get('streak_calc','NA')}`")
    lines.append(
        "- signal_rules: "
        f"`Extreme(abs(Z60)>={Z60_WATCH_ABS:g} (WATCH), abs(Z60)>={Z60_ALERT_ABS:g} (ALERT), "
        f"P252>={P252_EXTREME_HI:g} or <={P252_EXTREME_LO:g} (WATCH/INFO), P252<={P252_ALERT_LO:g} (ALERT)); "
        f"Jump(abs(ZΔ60)>={ZDELTA60_JUMP_ABS:g} OR abs(PΔ60)>={PDELTA60_JUMP_ABS:g} OR abs(ret1%60)>={RET1PCT60_JUMP_ABS:g}); "
        f"Near(within {NEAR_FRAC*100:.0f}% of jump thresholds); "
        "INFO if only long-extreme and no jump and abs(Z60)<2`"
    )
    lines.append("")

    header = [
        "Signal", "Tag", "Near",
        "Dir", "DirNote",
        "PrevSignal", "DeltaSignal",
        "StreakHist", "StreakWA",
        "Series", "DQ", "age_h",
        "data_date", "value",
        "z60", "p252",
        "z_delta60", "p_delta60", "ret1_pct60",
        "Reason", "Source", "as_of_ts"
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for r in rows:
        lines.append("| " + " | ".join([
            md_escape_cell(r.get("signal_level", "NONE")),
            md_escape_cell(r.get("tag", "NA")),
            md_escape_cell(r.get("near", "NA")),
            md_escape_cell(r.get("dir", "MOVE")),
            md_escape_cell(r.get("dir_note", "NA")),
            md_escape_cell(r.get("prev_signal", "NA")),
            md_escape_cell(r.get("delta_signal", "NA")),
            md_escape_cell(fmt(r.get("streak_hist"), nd=0)),
            md_escape_cell(fmt(r.get("streak_wa"), nd=0)),
            md_escape_cell(r.get("series", "")),
            md_escape_cell(r.get("dq", "")),
            md_escape_cell(fmt(r.get("age_hours"), nd=2)),
            md_escape_cell(fmt(r.get("data_date"))),
            md_escape_cell(fmt(r.get("value"), nd=6)),
            md_escape_cell(fmt(r.get("z60"), nd=6)),
            md_escape_cell(fmt(r.get("p252"), nd=6)),
            md_escape_cell(fmt(r.get("z_delta60"), nd=6)),
            md_escape_cell(fmt(r.get("p_delta60"), nd=6)),
            md_escape_cell(fmt(r.get("ret1_pct60"), nd=6)),
            md_escape_cell(r.get("reason")),
            md_escape_cell(r.get("source_url")),
            md_escape_cell(r.get("as_of_ts")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--dash-history", default=None)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", default="market_cache")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    ap.add_argument("--ruleset-id", default=DEFAULT_RULESET_ID)
    ap.add_argument("--script-fingerprint", default=DEFAULT_SCRIPT_FINGERPRINT)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    sha = os.getenv("GITHUB_SHA", "")
    sha7 = sha[:7] if isinstance(sha, str) and len(sha) >= 7 else ""
    script_fingerprint = args.script_fingerprint
    if sha7 and ("@" not in script_fingerprint):
        script_fingerprint = f"{script_fingerprint}@{sha7}"

    if not os.path.exists(args.stats):
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "module": args.module,
            "ruleset_id": args.ruleset_id,
            "script_fingerprint": script_fingerprint,
            "stale_hours": args.stale_hours,
            "stats_path": args.stats,
            "dash_history_path": args.dash_history or "NA",
            "streak_calc": "disabled (missing stats file)",
            "error": f"stats file missing: {args.stats}",
        }
        write_outputs(args.out_md, args.out_json, meta, [], {})
        return

    with open(args.stats, "r", encoding="utf-8") as f:
        stats = json.load(f)

    history_snaps = load_dashboard_history(args.dash_history)
    timeline = build_series_signal_timeline(history_snaps, args.module, args.ruleset_id)

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "ruleset_id": args.ruleset_id,
        "script_fingerprint": script_fingerprint,
        "stale_hours": args.stale_hours,
        "stats_path": args.stats,
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats.get("as_of_ts"),
        "script_version": stats.get("script_version"),
        "series_count": stats.get("series_count"),
        "dash_history_path": args.dash_history or "NA",
        "streak_calc": "PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today",
        "history_items_loaded": len(history_snaps),
    }

    series = stats.get("series", {})
    if not isinstance(series, dict):
        series = {}

    rows: List[Dict[str, Any]] = []
    series_signals: Dict[str, str] = {}

    for sid, s in series.items():
        if not isinstance(s, dict):
            continue

        sid_str = str(sid)
        latest = s.get("latest", {}) if isinstance(s.get("latest"), dict) else {}
        w60 = get_w(s, "w60")
        w252 = get_w(s, "w252")

        latest_asof_dt = parse_iso(latest.get("as_of_ts"))
        dq, age_hours = dq_from_ts(run_ts, latest_asof_dt, args.stale_hours)

        signal_level, reason, tag, near = compute_signal_tag_near_from_metrics(
            z60=w60.get("z"),
            p252=w252.get("p"),
            zdel60=w60.get("z_delta"),
            pdel60=w60.get("p_delta"),
            ret1pct60=w60.get("ret1_pct"),
        )

        prev_signal, streak_hist, streak_wa = compute_prev_and_streaks(
            sid=sid_str,
            today_signal=signal_level,
            timeline=timeline,
        )
        delta_signal = compute_delta_signal(prev_signal, signal_level)

        series_signals[sid_str] = str(signal_level)

        direction = get_direction(sid_str)
        tags_list = parse_tags(tag)
        dir_note = compute_dir_note(direction, reason, tags_list)

        row: Dict[str, Any] = {
            "module": args.module,
            "ruleset_id": args.ruleset_id,
            "script_fingerprint": script_fingerprint,

            "series": sid_str,
            "value": latest.get("value"),
            "data_date": latest.get("data_date"),
            "as_of_ts": latest.get("as_of_ts"),
            "source_url": latest.get("source_url"),
            "dq": dq,
            "age_hours": age_hours,

            "z60": w60.get("z"),
            "ret1_pct60": w60.get("ret1_pct"),
            "z_delta60": w60.get("z_delta"),
            "p_delta60": w60.get("p_delta"),
            "p252": w252.get("p"),

            "signal_level": signal_level,
            "reason": reason,
            "tag": tag,
            "near": near,

            "dir": direction,
            "dir_note": dir_note,

            "prev_signal": prev_signal,
            "delta_signal": delta_signal,
            "streak_hist": streak_hist,
            "streak_wa": streak_wa,
        }
        rows.append(row)

    sig_order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    dq_order = {"MISSING": 0, "STALE": 1, "OK": 2}

    def watch_near_rank(r: Dict[str, Any]) -> int:
        if r.get("signal_level") != "WATCH":
            return 9
        return 0 if r.get("near") not in (None, "NA", "") else 1

    def streak_rank(r: Dict[str, Any]) -> int:
        try:
            return -int(r.get("streak_wa") or 0)
        except Exception:
            return 0

    def delta_rank(r: Dict[str, Any]) -> int:
        d = r.get("delta_signal")
        if d == "NA":
            return 2
        if d == "SAME":
            return 1
        return 0

    rows.sort(key=lambda r: (
        sig_order.get(r.get("signal_level", "NONE"), 9),
        delta_rank(r),
        watch_near_rank(r),
        streak_rank(r),
        dq_order.get(r.get("dq", "OK"), 9),
        r.get("series", ""),
    ))

    write_outputs(args.out_md, args.out_json, meta, rows, series_signals)


if __name__ == "__main__":
    main()