#!/usr/bin/env python3
# scripts/render_dashboard_fred_cache.py
#
# fred_cache dashboard renderer with "sudden move" support via cache/history_lite.json.
#
# Inputs:
#   --stats        cache/stats_latest.json (used for meta + as-of timestamps; metrics optional)
#   --history      dashboard_fred_cache/history.json (dashboard output history for Prev/Delta/Streak)
#   --history-lite cache/history_lite.json (for recomputing z60/p252 + zΔ60/pΔ60/ret1%60)
#
# Key goals:
# - Keep auditable, deterministic computation using repo files only (no external fetch).
# - Recompute from history_lite values:
#     z60, p252, zΔ60, pΔ60, ret1%60
#   (ret1% denom = abs(prev_value) else NA)
# - Fall back gracefully when history_lite missing or insufficient points.

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_STALE_HOURS = 72.0

# ---- Signal thresholds (same family as market_cache) ----
Z60_WATCH_ABS = 2.0
Z60_ALERT_ABS = 2.5

P252_EXTREME_HI = 95.0
P252_EXTREME_LO = 5.0
P252_ALERT_LO = 2.0

ZDELTA60_JUMP_ABS = 0.75
PDELTA60_JUMP_ABS = 15.0
RET1PCT60_JUMP_ABS = 2.0

NEAR_FRAC = 0.10
STREAK_HISTORY_MAX = 180


# -------------------------
# Utils
# -------------------------
def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    ts2 = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts2)
    except Exception:
        return None


def dq_from_ts(run_ts: datetime, as_of_dt: Optional[datetime], stale_hours: float) -> Tuple[str, Optional[float]]:
    if as_of_dt is None:
        return "MISSING", None
    age_hours = (run_ts - as_of_dt).total_seconds() / 3600.0
    return ("STALE" if age_hours > stale_hours else "OK"), age_hours


def fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        s = f"{x:.{nd}f}"
        return s.rstrip("0").rstrip(".")
    return str(x)


def md_escape_cell(x: Any) -> str:
    s = str(x) if x is not None else "NA"
    s = s.replace("|", "&#124;")  # protect markdown table
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


def mean_std_ddof0(xs: List[float]) -> Tuple[Optional[float], Optional[float]]:
    n = len(xs)
    if n == 0:
        return None, None
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / n
    std = var ** 0.5
    return m, std


def percentile_le(xs: List[float], latest: float) -> Optional[float]:
    n = len(xs)
    if n == 0:
        return None
    c = sum(1 for x in xs if x <= latest)
    return (c / n) * 100.0


# -------------------------
# Signal logic
# -------------------------
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

    # INFO rule: long-extreme only + no jump + abs(Z60)<2
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


# -------------------------
# dashboard history (Prev/Delta/Streak)
# -------------------------
def load_dash_history(path: str) -> List[Dict[str, Any]]:
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
        return []
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


# -------------------------
# history_lite parsing + recompute
# -------------------------
def parse_history_lite(path: str) -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns: { series_id: [(data_date, value), ...] } sorted by data_date asc
    Supports:
      - NDJSON (one JSON object per line)
      - JSON array of records
      - JSON object containing list-like under known keys (best-effort)
    Record expected keys:
      - series_id or series
      - data_date or date
      - value
    """
    out: Dict[str, List[Tuple[str, float]]] = {}

    if not path or (not os.path.exists(path)):
        return out

    def add_rec(series_id: str, data_date: str, value: Any) -> None:
        if not isinstance(series_id, str) or not series_id:
            return
        if not isinstance(data_date, str) or not data_date:
            return
        if not isinstance(value, (int, float)):
            return
        out.setdefault(series_id, []).append((data_date, float(value)))

    # Try to detect format by reading first non-empty bytes
    with open(path, "r", encoding="utf-8") as f:
        head = ""
        while True:
            ch = f.read(1)
            if not ch:
                break
            if ch.strip():
                head = ch
                break

    # JSON array
    if head == "[":
        with open(path, "r", encoding="utf-8") as f:
            arr = json.load(f)
        if isinstance(arr, list):
            for r in arr:
                if not isinstance(r, dict):
                    continue
                sid = r.get("series_id") or r.get("series")
                dd = r.get("data_date") or r.get("date")
                val = r.get("value")
                add_rec(sid, dd, val)

    # JSON object (might wrap records)
    elif head == "{":
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        # common patterns: obj["data"] or obj["items"] or obj["records"]
        cand = None
        for k in ("data", "items", "records", "rows"):
            if isinstance(obj.get(k), list):
                cand = obj.get(k)
                break
        if cand is None and isinstance(obj.get("series"), dict):
            # series -> list of points
            for sid, s in obj["series"].items():
                if isinstance(s, dict) and isinstance(s.get("values"), list):
                    for p in s["values"]:
                        if not isinstance(p, dict):
                            continue
                        dd = p.get("data_date") or p.get("date")
                        val = p.get("value")
                        add_rec(sid, dd, val)
        else:
            if isinstance(cand, list):
                for r in cand:
                    if not isinstance(r, dict):
                        continue
                    sid = r.get("series_id") or r.get("series")
                    dd = r.get("data_date") or r.get("date")
                    val = r.get("value")
                    add_rec(sid, dd, val)

    # NDJSON fallback
    else:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not isinstance(r, dict):
                    continue
                sid = r.get("series_id") or r.get("series")
                dd = r.get("data_date") or r.get("date")
                val = r.get("value")
                add_rec(sid, dd, val)

    # sort and keep unique by data_date (last wins)
    for sid, pts in out.items():
        # if duplicates exist, keep last
        m: Dict[str, float] = {}
        for dd, v in pts:
            m[dd] = v
        pts2 = sorted(m.items(), key=lambda t: t[0])
        out[sid] = [(dd, v) for dd, v in pts2]

    return out


def compute_from_history(points: List[Tuple[str, float]]) -> Dict[str, Optional[float]]:
    """
    From full chronological points, compute:
      z60, p252, zΔ60, pΔ60, ret1%60
    Using "last N valid points" windows (not calendar days).
    """
    vals = [v for _, v in points if isinstance(v, (int, float))]
    if len(vals) < 2:
        return {"z60": None, "p252": None, "z_delta60": None, "p_delta60": None, "ret1_pct60": None}

    latest = vals[-1]
    prev = vals[-2]

    # ret1%60
    denom = abs(prev)
    if denom > 0:
        ret1_pct = ((latest - prev) / denom) * 100.0
    else:
        ret1_pct = None

    # current windows
    w60 = vals[-60:] if len(vals) >= 60 else []
    w252 = vals[-252:] if len(vals) >= 252 else []

    z60 = None
    if len(w60) >= 60:
        m, s = mean_std_ddof0(w60)
        if m is not None and s is not None and s > 0:
            z60 = (latest - m) / s

    p252 = None
    if len(w252) >= 252:
        p252 = percentile_le(w252, latest)

    # previous windows (exclude latest)
    z60_prev = None
    p60 = None
    p60_prev = None

    if len(vals) >= 61:
        w60_prev = vals[-61:-1]  # 60 points ending at prev
        m0, s0 = mean_std_ddof0(w60_prev)
        if m0 is not None and s0 is not None and s0 > 0:
            z60_prev = (prev - m0) / s0

        # p60 today/prev for pΔ60 (consistent with market_cache idea)
        p60 = percentile_le(w60, latest) if len(w60) == 60 else None
        p60_prev = percentile_le(w60_prev, prev) if len(w60_prev) == 60 else None

    z_delta = None
    if z60 is not None and z60_prev is not None:
        z_delta = z60 - z60_prev

    p_delta = None
    if p60 is not None and p60_prev is not None:
        p_delta = p60 - p60_prev

    return {
        "z60": z60,
        "p252": p252,
        "z_delta60": z_delta,
        "p_delta60": p_delta,
        "ret1_pct60": ret1_pct,
    }


# -------------------------
# Meta
# -------------------------
def pick_script_version(stats: Dict[str, Any]) -> Optional[str]:
    sv = stats.get("script_version")
    if isinstance(sv, str) and sv:
        return sv
    sp = stats.get("stats_policy")
    if isinstance(sp, dict):
        sv2 = sp.get("script_version")
        if isinstance(sv2, str) and sv2:
            return sv2
    return None


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
    lines.append(f"- history_lite_used_for_jump: `{meta.get('history_lite_path','NA')}`")
    lines.append(f"- streak_calc: `{meta.get('streak_calc','NA')}`")
    lines.append(f"- jump_calc: `{meta.get('jump_calc','NA')}`")
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
            md_escape_cell(r.get("effective_as_of_ts")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--history-lite", required=True)
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
            "history_lite_path": args.history_lite,
            "streak_calc": "disabled (missing stats file)",
            "jump_calc": "disabled (missing stats file)",
            "error": f"stats missing: {args.stats}",
        }
        write_outputs(args.out_md, args.out_json, meta, [])
        return

    with open(args.stats, "r", encoding="utf-8") as f:
        stats = json.load(f)

    stats_as_of_ts = stats.get("as_of_ts") if isinstance(stats.get("as_of_ts"), str) else None
    stats_as_of_dt = parse_iso(stats_as_of_ts)

    # dashboard history for Prev/Delta/Streak
    snaps = load_dash_history(args.history)
    timeline = build_timeline(snaps, args.module)

    # history_lite for sudden-move recompute
    hl = parse_history_lite(args.history_lite)

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "stale_hours": args.stale_hours,
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats_as_of_ts,
        "script_version": pick_script_version(stats),
        "series_count": stats.get("series_count"),
        "history_path": args.history,
        "history_lite_path": args.history_lite,
        "streak_calc": "PrevSignal/Streak derived from history.json (dashboard outputs)",
        "jump_calc": "recompute z60/p252/zΔ60/pΔ60/ret1%60 from history_lite values; ret1% denom = abs(prev_value) else NA",
        "history_items_used": len(snaps),
        "history_lite_series": len(hl),
    }

    series = stats.get("series", {})
    if not isinstance(series, dict):
        series = {}

    rows: List[Dict[str, Any]] = []

    for sid, s in series.items():
        if not isinstance(s, dict):
            continue

        latest = s.get("latest", {}) if isinstance(s.get("latest"), dict) else {}

        # Effective as_of_ts:
        # prefer per-series latest.as_of_ts if present; else fall back to stats.as_of_ts
        eff_as_of_ts = latest.get("as_of_ts") if isinstance(latest.get("as_of_ts"), str) else stats_as_of_ts
        eff_as_of_dt = parse_iso(eff_as_of_ts)

        dq, age_hours = dq_from_ts(run_ts, eff_as_of_dt or stats_as_of_dt, args.stale_hours)

        # Recompute signals from history_lite (if available)
        comp = compute_from_history(hl.get(sid, [])) if sid in hl else {
            "z60": None, "p252": None, "z_delta60": None, "p_delta60": None, "ret1_pct60": None
        }

        z60 = comp.get("z60")
        p252 = comp.get("p252")
        zdel60 = comp.get("z_delta60")
        pdel60 = comp.get("p_delta60")
        ret1pct60 = comp.get("ret1_pct60")

        lvl, reason, tag, near = compute_signal_tag_near(z60, p252, zdel60, pdel60, ret1pct60)

        prev, streak = prev_and_streak(sid, lvl, timeline)
        dlt = delta_signal(prev, lvl)

        rows.append({
            "series": sid,
            "dq": dq,
            "age_hours": age_hours,
            "data_date": latest.get("data_date"),
            "value": latest.get("value"),
            "z60": z60,
            "p252": p252,
            "z_delta_60": zdel60,
            "p_delta_60": pdel60,
            "ret1_pct_60": ret1pct60,
            "reason": reason,
            "tag": tag,
            "near": near,
            "signal_level": lvl,
            "prev_signal": prev,
            "delta_signal": dlt,
            "streak_wa": streak,
            "source_url": latest.get("source_url"),
            "effective_as_of_ts": eff_as_of_ts or "NA",
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