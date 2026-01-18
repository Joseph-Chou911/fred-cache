#!/usr/bin/env python3
# scripts/render_snapshot_dashboard.py
#
# Snapshot dashboard renderer (方案A)
# - Input: JSON array (list of {series_id,data_date,value,source_url,notes,as_of_ts,...})
# - Output:
#   - dashboard/DASHBOARD_SNAPSHOT.md
#   - dashboard/dashboard_snapshot_latest.json
# - Uses dashboard/history.json for PrevSignal/DeltaSignal/StreakWA (module-separated)
#
# Signal logic (穩健、低噪音、以不中斷為優先):
#   1) DQ=MISSING -> ALERT (tag=MISSING)
#   2) age_h > stale_hours -> WATCH (tag=STALE)；若 age_h >= 2*stale_hours -> ALERT
#   3) notes startswith "ERROR:" -> ALERT
#   4) notes startswith "WARN:" -> WATCH
#   5) else -> INFO
#
# Near:
#   - NEAR:STALE if age_h within 10% below stale_hours (>= 0.9*stale_hours and < stale_hours)
#
# Summary:
#   - ALERT/WATCH/INFO/NONE counts
#   - CHANGED (Delta != SAME and != NA)
#   - WATCH_STREAK>=3

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_STALE_HOURS = 36.0
NEAR_FRAC = 0.10
STREAK_HISTORY_MAX = 180  # more than enough

LEVELS = ("ALERT", "WATCH", "INFO", "NONE")


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts2 = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts2)
    except Exception:
        return None


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


def dq_and_age(run_ts: datetime, as_of_ts: Optional[str], stale_hours: float) -> Tuple[str, Optional[float]]:
    dt = parse_iso(as_of_ts)
    if dt is None:
        return "MISSING", None
    age_h = (run_ts - dt).total_seconds() / 3600.0
    if age_h > stale_hours:
        return "STALE", age_h
    return "OK", age_h


def is_near_stale(age_h: Optional[float], stale_hours: float) -> bool:
    if age_h is None:
        return False
    return (age_h >= (1.0 - NEAR_FRAC) * stale_hours) and (age_h < stale_hours)


def normalize_notes(notes: Any) -> str:
    if notes is None:
        return ""
    return str(notes).strip()


def classify_notes_tag(notes: str) -> str:
    # Prefer leading severity prefix
    if notes.startswith("ERROR:"):
        return "ERROR"
    if notes.startswith("WARN:"):
        # try to extract short tag after WARN:
        rest = notes[len("WARN:"):].strip()
        # cut at ';' or '(' if present
        for sep in (";", "("):
            if sep in rest:
                rest = rest.split(sep, 1)[0].strip()
        return rest or "WARN"
    if notes.startswith("INFO:"):
        rest = notes[len("INFO:"):].strip()
        for sep in (";", "("):
            if sep in rest:
                rest = rest.split(sep, 1)[0].strip()
        return rest or "INFO"

    # fallback tags for common patterns
    low = notes.lower()
    if "derived" in low:
        return "DERIVED"
    if "nonofficial" in low:
        return "NONOFFICIAL"
    if "no_key" in low:
        return "NO_KEY"
    return "NA"


def compute_signal(dq: str, age_h: Optional[float], stale_hours: float, notes: str) -> Tuple[str, str]:
    """
    Returns (level, reason)
    """
    if dq == "MISSING":
        return "ALERT", "DQ=MISSING"

    # Staleness escalation
    if age_h is not None and age_h > stale_hours:
        if age_h >= 2.0 * stale_hours:
            return "ALERT", f"STALE>=2x({stale_hours:g}h)"
        return "WATCH", f"STALE>{stale_hours:g}h"

    # Notes-based
    if notes.startswith("ERROR:"):
        return "ALERT", "NOTES=ERROR"
    if notes.startswith("WARN:"):
        return "WATCH", "NOTES=WARN"

    return "INFO", "OK"


def load_history(path: Optional[str]) -> List[Dict[str, Any]]:
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


def build_timeline(history_snaps: List[Dict[str, Any]], module: str) -> Dict[str, List[str]]:
    tl: Dict[str, List[str]] = {}
    for snap in history_snaps:
        if snap.get("module") != module:
            continue
        sigs = snap.get("series_signals")
        if not isinstance(sigs, dict):
            continue
        for sid, sig in sigs.items():
            if isinstance(sid, str) and isinstance(sig, str):
                tl.setdefault(sid, []).append(sig)
    return tl


def compute_prev_and_streak(sid: str, today: str, tl: Dict[str, List[str]]) -> Tuple[str, int]:
    hist = tl.get(sid, [])
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


def delta(prev: str, today: str) -> str:
    if not prev or prev == "NA":
        return "NA"
    if prev == today:
        return "SAME"
    return f"{prev}→{today}"


def compute_summary(rows: List[Dict[str, Any]]) -> Dict[str, int]:
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


def write_outputs(out_md: str, out_json: str, meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    payload = {"meta": meta, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    s = compute_summary(rows)

    lines: List[str] = []
    lines.append(f"# Risk Dashboard Snapshot ({meta.get('module','')})")
    lines.append("")
    lines.append(
        f"- Summary: ALERT={s['ALERT']} / WATCH={s['WATCH']} / INFO={s['INFO']} / NONE={s['NONE']}; "
        f"CHANGED={s['CHANGED']}; WATCH_STREAK>=3={s['WATCH_STREAK_GE3']}"
    )
    lines.append(f"- RUN_TS_UTC: `{meta.get('run_ts_utc','')}`")
    lines.append(f"- SNAPSHOT.as_of_ts: `{meta.get('snapshot_as_of_ts','')}`")
    lines.append(f"- snapshot_script_version: `{meta.get('snapshot_script_version','')}`")
    lines.append(f"- stale_hours: `{meta.get('stale_hours','')}`")
    lines.append(f"- input_snapshot: `{meta.get('input_snapshot','')}`")
    lines.append(f"- dash_history: `{meta.get('dash_history_path','NA')}`")
    lines.append(f"- streak_calc: `{meta.get('streak_calc','NA')}`")
    lines.append(
        "- signal_rules: "
        "`DQ=MISSING->ALERT; STALE>stale_hours->WATCH; STALE>=2x->ALERT; NOTES:ERROR->ALERT; NOTES:WARN->WATCH; else INFO; "
        "Near=within 10% below staleness threshold`"
    )
    lines.append("")

    header = [
        "Signal", "Tag", "Near", "PrevSignal", "DeltaSignal", "StreakWA",
        "Series", "DQ", "age_h",
        "data_date", "value", "change_pct_1d",
        "notes", "Source", "as_of_ts"
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
            md_escape_cell(fmt(r.get("change_pct_1d"), nd=6)),
            md_escape_cell(r.get("notes", "")),
            md_escape_cell(r.get("source_url", "")),
            md_escape_cell(r.get("as_of_ts", "")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, help="Path to snapshot JSON array (e.g., fallback_cache/latest.json)")
    ap.add_argument("--dash-history", default="dashboard/history.json", help="Path to shared dashboard history.json")
    ap.add_argument("--module", default="snapshot_fast", help="Module name stored in history for separation")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    if not os.path.exists(args.snapshot):
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "module": args.module,
            "stale_hours": args.stale_hours,
            "input_snapshot": args.snapshot,
            "dash_history_path": args.dash_history,
            "streak_calc": "disabled (missing snapshot)",
            "error": f"snapshot missing: {args.snapshot}",
        }
        write_outputs(args.out_md, args.out_json, meta, [])
        return

    with open(args.snapshot, "r", encoding="utf-8") as f:
        arr = json.load(f)

    if not isinstance(arr, list):
        raise SystemExit("Snapshot must be a JSON array")

    # Extract __META__ if present
    meta_item = None
    for it in arr:
        if isinstance(it, dict) and it.get("series_id") == "__META__":
            meta_item = it
            break

    snapshot_as_of_ts = None
    snapshot_script_version = None
    if isinstance(meta_item, dict):
        snapshot_as_of_ts = meta_item.get("as_of_ts")
        snapshot_script_version = meta_item.get("value")

    # If not provided, fallback to max as_of_ts across entries
    if not snapshot_as_of_ts:
        best = None
        for it in arr:
            if not isinstance(it, dict):
                continue
            ts = parse_iso(it.get("as_of_ts"))
            if ts and (best is None or ts > best):
                best = ts
        snapshot_as_of_ts = best.isoformat().replace("+00:00", "Z") if best else "NA"

    history_snaps = load_history(args.dash_history)
    timeline = build_timeline(history_snaps, args.module)

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "stale_hours": args.stale_hours,
        "input_snapshot": args.snapshot,
        "dash_history_path": args.dash_history,
        "snapshot_as_of_ts": snapshot_as_of_ts,
        "snapshot_script_version": snapshot_script_version or "NA",
        "streak_calc": "PrevSignal/StreakWA derived from dashboard/history.json (past renderer outputs) + today's signal",
        "history_items_used": len(history_snaps),
    }

    rows: List[Dict[str, Any]] = []

    for it in arr:
        if not isinstance(it, dict):
            continue
        sid = it.get("series_id")
        if not isinstance(sid, str) or sid == "__META__":
            continue

        notes = normalize_notes(it.get("notes"))
        dq, age_h = dq_and_age(run_ts, it.get("as_of_ts"), args.stale_hours)

        level, reason = compute_signal(dq, age_h, args.stale_hours, notes)
        tag = classify_notes_tag(notes)
        near = "NEAR:STALE" if is_near_stale(age_h, args.stale_hours) else "NA"

        prev, streak = compute_prev_and_streak(sid, level, timeline)
        d = delta(prev, level)

        row = {
            "series": sid,
            "dq": dq,
            "age_hours": age_h,
            "data_date": it.get("data_date"),
            "value": it.get("value"),
            "change_pct_1d": it.get("change_pct_1d"),
            "notes": notes if notes else "NA",
            "source_url": it.get("source_url") or "NA",
            "as_of_ts": it.get("as_of_ts") or "NA",

            "signal_level": level,
            "reason": reason,
            "tag": tag,
            "near": near,

            "prev_signal": prev,
            "delta_signal": d,
            "streak_wa": streak,
        }
        rows.append(row)

    # Sorting: ALERT/WATCH first, then CHANGED first, then WATCH_NEAR, then streak desc, then oldest first (age desc)
    sig_order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}

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
        return 0 if r.get("near") not in ("NA", "", None) else 1

    def streak_rank(r: Dict[str, Any]) -> int:
        try:
            return -int(r.get("streak_wa") or 0)
        except Exception:
            return 0

    def age_rank(r: Dict[str, Any]) -> float:
        ah = r.get("age_hours")
        if isinstance(ah, (int, float)):
            return -float(ah)  # older first
        return 0.0

    rows.sort(key=lambda r: (
        sig_order.get(r.get("signal_level", "NONE"), 9),
        delta_rank(r),
        watch_near_rank(r),
        streak_rank(r),
        age_rank(r),
        r.get("series", ""),
    ))

    write_outputs(args.out_md, args.out_json, meta, rows)


if __name__ == "__main__":
    main()