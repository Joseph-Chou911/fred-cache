#!/usr/bin/env python3
# scripts/render_dashboard_fred_cache.py
#
# Standalone renderer for FRED cache dashboard
# Output folder recommended: dashboard_fred_cache/
#
# Features:
# - Reason uses abs(...)
# - Summary counts (ALERT/WATCH/INFO/NONE, CHANGED, WATCH_STREAK>=3)
# - PrevSignal/Streak derived from dashboard_fred_cache/history.json
# - DeltaSignal computed from PrevSignal
#
# Input:
#   --stats cache/stats_latest.json
# History:
#   --history dashboard_fred_cache/history.json

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_STALE_HOURS = 72.0

Z60_WATCH_ABS = 2.0
Z60_ALERT_ABS = 2.5

P252_EXTREME_HI = 95.0
P252_EXTREME_LO = 5.0
P252_ALERT_LO = 2.0

ZDELTA60_JUMP_ABS = 0.75
PDELTA60_JUMP_ABS = 15.0
RET1PCT60_JUMP_ABS = 2.0

NEAR_FRAC = 0.10
STREAK_HISTORY_MAX = 120


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


def compute_signal_tag_near(
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

    seen = set()
    tags2: List[str] = []
    for t in tags:
        if t not in seen:
            tags2.append(t)
            seen.add(t)
    tag_str = ",".join(tags2) if tags2 else "NA"

    near_str = ",".join(nears) if nears else "NA"
    return level, reason_str, tag_str, near_str


def load_history(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        items = obj.get("items", [])
        if isinstance(items, list):
            snaps = [x for x in items if isinstance(x, dict)]
            return snaps[-STREAK_HISTORY_MAX:]
    except Exception:
        pass
    return []


def build_timeline(snaps: List[Dict[str, Any]], module: str) -> Dict[str, List[str]]:
    tl: Dict[str, List[str]] = {}
    for snap in snaps:
        if snap.get("module") != module:
            continue
        sigs = snap.get("series_signals")
        if not isinstance(sigs, dict):
            continue
        for sid, sig in sigs.items():
            if isinstance(sid, str) and isinstance(sig, str):
                tl.setdefault(sid, []).append(sig)
    return tl


def prev_and_streak(series_id: str, today: str, timeline: Dict[str, List[str]]) -> Tuple[str, int]:
    hist = timeline.get(series_id, [])
    prev = hist[-1] if hist else "NA"
    if today not in ("WATCH", "ALERT"):
        return prev, 0
    streak = 1
    for s in reversed(hist):
        if s in ("WATCH", "ALERT"):
            streak += 1
        else:
            break
    return prev, streak


def delta_signal(prev: str, today: str) -> str:
    if prev in (None, "", "NA"):
        return "NA"
    if prev == today:
        return "SAME"
    return f"{prev}→{today}"


def summary_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"ALERT": 0, "WATCH": 0, "INFO": 0, "NONE": 0}
    changed = 0
    watch_ge3 = 0
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
                    watch_ge3 += 1
            except Exception:
                pass
    counts["CHANGED"] = changed
    counts["WATCH_STREAK_GE3"] = watch_ge3
    return counts


def write_outputs(out_md: str, out_json: str, meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    payload = {"meta": meta, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    s = summary_counts(rows)

    lines: List[str] = []
    lines.append(f"# Risk Dashboard ({meta.get('module','')})")
    lines.append("")
    lines.append(
        f"- Summary: ALERT={s['ALERT']} / WATCH={s['WATCH']} / INFO={s['INFO']} / NONE={s['NONE']}; "
        f"CHANGED={s['CHANGED']}; WATCH_STREAK>=3={s['WATCH_STREAK_GE3']}"
    )
    lines.append(f"- RUN_TS_UTC: `{meta.get('run_ts_utc','')}`")
    lines.append(f"- STATS.generated_at_utc: `{meta.get('stats_generated_at_utc','')}`")
    lines.append(f"- STATS.as_of_ts: `{meta.get('stats_as_of_ts','')}`")
    lines.append(f"- script_version: `{meta.get('script_version','')}`")
    lines.append(f"- stale_hours: `{meta.get('stale_hours','')}`")
    lines.append(f"- dash_history: `{meta.get('history_path','NA')}`")
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
        "Signal", "Tag", "Near", "PrevSignal", "DeltaSignal", "StreakWA",
        "Series", "DQ", "age_h",
        "data_date", "value",
        "z60", "p252", "z_delta60", "p_delta60", "ret1_pct60",
        "Reason", "Source", "as_of_ts"
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for r in rows:
        lines.append("| " + " | ".join([
            md_escape_cell(r.get("signal_level", "NONE")),
            md_escape_cell(r.get("tag", "NA")),
            md_escape_cell(r.get("near", "NA")),
            md_escape_cell(r.get("prev_signal", "NA")),
            md_escape_cell(r.get("delta_signal", "NA")),
            md_escape_cell(fmt(r.get("streak_wa"), nd=0)),
            md_escape_cell(r.get("series", "")),
            md_escape_cell(r.get("dq", "")),
            md_escape_cell(fmt(r.get("age_hours"), nd=2)),
            md_escape_cell(fmt(r.get("data_date"))),
            md_escape_cell(fmt(r.get("value"), nd=6)),
            md_escape_cell(fmt(r.get("z60"), nd=6)),
            md_escape_cell(fmt(r.get("p252"), nd=6)),
            md_escape_cell(fmt(r.get("z_delta_60"), nd=6)),
            md_escape_cell(fmt(r.get("p_delta_60"), nd=6)),
            md_escape_cell(fmt(r.get("ret1_pct_60"), nd=6)),
            md_escape_cell(r.get("reason")),
            md_escape_cell(r.get("source_url")),
            md_escape_cell(r.get("as_of_ts")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", default="fred_cache")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    if not os.path.exists(args.stats):
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "module": args.module,
            "stale_hours": args.stale_hours,
            "history_path": args.history,
            "streak_calc": "disabled (missing stats file)",
            "error": f"stats missing: {args.stats}",
        }
        write_outputs(args.out_md, args.out_json, meta, [])
        return

    with open(args.stats, "r", encoding="utf-8") as f:
        stats = json.load(f)

    snaps = load_history(args.history)
    timeline = build_timeline(snaps, args.module)

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "stale_hours": args.stale_hours,
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats.get("as_of_ts"),
        "script_version": stats.get("script_version"),
        "series_count": stats.get("series_count"),
        "history_path": args.history,
        "streak_calc": "PrevSignal/Streak derived from history.json (dashboard outputs)",
        "history_items_used": len(snaps),
    }

    series = stats.get("series", {})
    if not isinstance(series, dict):
        series = {}

    rows: List[Dict[str, Any]] = []
    for sid, s in series.items():
        if not isinstance(s, dict):
            continue

        latest = s.get("latest", {}) if isinstance(s.get("latest"), dict) else {}
        w60 = get_w(s, "w60")
        w252 = get_w(s, "w252")

        latest_asof_dt = parse_iso(latest.get("as_of_ts"))
        dq, age_hours = dq_from_ts(run_ts, latest_asof_dt, args.stale_hours)

        lvl, reason, tag, near = compute_signal_tag_near(
            z60=w60.get("z"),
            p252=w252.get("p"),
            zdel60=w60.get("z_delta"),
            pdel60=w60.get("p_delta"),
            ret1pct60=w60.get("ret1_pct"),
        )

        prev, streak = prev_and_streak(sid, lvl, timeline)
        dlt = delta_signal(prev, lvl)

        rows.append({
            "series": sid,
            "dq": dq,
            "age_hours": age_hours,
            "data_date": latest.get("data_date"),
            "value": latest.get("value"),
            "z60": w60.get("z"),
            "p252": w252.get("p"),
            "z_delta_60": w60.get("z_delta"),
            "p_delta_60": w60.get("p_delta"),
            "ret1_pct_60": w60.get("ret1_pct"),
            "reason": reason,
            "tag": tag,
            "near": near,
            "signal_level": lvl,
            "prev_signal": prev,
            "delta_signal": dlt,
            "streak_wa": streak,
            "source_url": latest.get("source_url"),
            "as_of_ts": latest.get("as_of_ts"),
        })

    sig_order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    dq_order = {"MISSING": 0, "STALE": 1, "OK": 2}

    def delta_rank(r: Dict[str, Any]) -> int:
        d = r.get("delta_signal")
        if d == "NA":
            return 2
        if d == "SAME":
            return 1
        return 0

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
        delta_rank(r),
        watch_near_rank(r),
        streak_rank(r),
        dq_order.get(r.get("dq", "OK"), 9),
        r.get("series", ""),
    ))

    write_outputs(args.out_md, args.out_json, meta, rows)


if __name__ == "__main__":
    main()