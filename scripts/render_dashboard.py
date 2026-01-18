#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Dashboard renderer (MVP+signals v4: Tag + Near + Streak from history_lite)
#
# Inputs:
#   - stats_latest.json (current day computed stats + sources)
#   - history_lite.json (time series values) -> used to compute PrevSignal + StreakWA
#
# Signals: ALERT / WATCH / INFO / NONE (改法 B)
# Tags: EXTREME_Z / JUMP_ZD / JUMP_P / JUMP_RET / LONG_EXTREME
# Near: within 10% of jump thresholds (but not crossing)
#
# IMPORTANT (audit note):
#   - PrevSignal/StreakWA are computed locally from history_lite values by re-deriving:
#       z60, p252, zΔ60, pΔ60, ret1%60
#     then applying the same signal rules.
#   - ret1% uses denom = abs(prev_value) when prev_value != 0; otherwise NA.
#     This may differ from upstream edge-case handling when prev is near 0.
#
# DQ:
#   - OK / STALE / MISSING based on latest.as_of_ts age

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Tunables (defaults)
# -------------------------
DEFAULT_STALE_HOURS = 36.0

# Extreme thresholds
Z60_WATCH_ABS = 2.0
Z60_ALERT_ABS = 2.5

P252_EXTREME_HI = 95.0
P252_EXTREME_LO = 5.0
P252_ALERT_LO = 2.0  # very extreme low tail

# Jump thresholds
ZDELTA60_JUMP_ABS = 0.75
PDELTA60_JUMP_ABS = 15.0
RET1PCT60_JUMP_ABS = 2.0  # percent units

# Near window: within X% of threshold
NEAR_FRAC = 0.10  # 10%

# Streak lookback (number of most recent points to compute signals for)
STREAK_LOOKBACK_MAX = 30

# Windows
W60 = 60
W252 = 252


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


def safe_abs(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return abs(float(x))
    return None


def is_near(abs_val: Optional[float], thr: float, near_frac: float) -> bool:
    if abs_val is None:
        return False
    lo = (1.0 - near_frac) * thr
    return (abs_val >= lo) and (abs_val < thr)


def mean_std_ddof0(vals: List[float]) -> Tuple[float, float]:
    n = len(vals)
    if n == 0:
        return 0.0, 0.0
    m = sum(vals) / n
    var = sum((x - m) ** 2 for x in vals) / n
    return m, var ** 0.5


def percentile_leq(vals: List[float], x: float) -> float:
    n = len(vals)
    if n == 0:
        return 0.0
    c = sum(1 for v in vals if v <= x)
    return (c / n) * 100.0


def compute_signal_tag_near_from_metrics(
    z60: Optional[float],
    p252: Optional[float],
    zdel60: Optional[float],
    pdel60: Optional[float],
    ret1pct60: Optional[float],
) -> Tuple[str, str, str, str]:
    """
    Returns (signal_level, reason_str, tag_str, near_str)
    Same rules as your current dashboard, but takes metrics directly.
    """
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
            reasons.append(f"|Z60|>={Z60_WATCH_ABS:g}")
            tags.append("EXTREME_Z")
        if az60 >= Z60_ALERT_ABS:
            z60_alert = True
            reasons.append(f"|Z60|>={Z60_ALERT_ABS:g}")

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
        reasons.append(f"|ZΔ60|>={ZDELTA60_JUMP_ABS:g}")
        tags.append("JUMP_ZD")
        jump_hits += 1
        has_zdelta_jump = True
    else:
        if is_near(azd, ZDELTA60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:ZΔ60")

    if apd is not None and apd >= PDELTA60_JUMP_ABS:
        reasons.append(f"|PΔ60|>={PDELTA60_JUMP_ABS:g}")
        tags.append("JUMP_P")
        jump_hits += 1
    else:
        if is_near(apd, PDELTA60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:PΔ60")

    if ar1p is not None and ar1p >= RET1PCT60_JUMP_ABS:
        reasons.append(f"|ret1%60|>={RET1PCT60_JUMP_ABS:g}")
        tags.append("JUMP_RET")
        jump_hits += 1
    else:
        if is_near(ar1p, RET1PCT60_JUMP_ABS, NEAR_FRAC):
            nears.append("NEAR:ret1%60")

    # Level assignment (改法 B)
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


def parse_history_points(history_obj: Dict[str, Any], series_id: str) -> List[Tuple[str, float]]:
    """
    Attempt to extract [(date_str, value_float), ...] for a series from history_lite.json.
    Supports several plausible schemas.
    """
    series = history_obj.get("series", {})
    if not isinstance(series, dict):
        return []

    s = series.get(series_id)
    if s is None:
        return []

    # Case A: s is dict with a list under common keys
    if isinstance(s, dict):
        for key in ("data", "history", "points", "values"):
            arr = s.get(key)
            if isinstance(arr, list):
                return normalize_points(arr)
        # Case B: s itself might be a dict with date->value mapping
        if all(isinstance(k, str) for k in s.keys()):
            # try date->value mapping
            pts: List[Tuple[str, float]] = []
            for k, v in s.items():
                if isinstance(v, (int, float)):
                    pts.append((k, float(v)))
            pts.sort(key=lambda x: x[0])
            return pts

    # Case C: s is already a list of points
    if isinstance(s, list):
        return normalize_points(s)

    return []


def normalize_points(arr: List[Any]) -> List[Tuple[str, float]]:
    pts: List[Tuple[str, float]] = []
    for it in arr:
        if isinstance(it, dict):
            d = it.get("date") or it.get("data_date") or it.get("d")
            v = it.get("value") if "value" in it else it.get("v")
            if isinstance(d, str) and isinstance(v, (int, float)):
                pts.append((d, float(v)))
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            d, v = it[0], it[1]
            if isinstance(d, str) and isinstance(v, (int, float)):
                pts.append((d, float(v)))
    pts.sort(key=lambda x: x[0])
    return pts


def compute_prevsignal_and_streak(history_obj: Dict[str, Any], series_id: str) -> Tuple[str, int]:
    """
    From history values, compute signals for last STREAK_LOOKBACK_MAX points,
    then return (PrevSignal, StreakWA).
    """
    pts = parse_history_points(history_obj, series_id)
    if len(pts) < 2:
        return "NA", 0

    # Use last lookback points
    pts = pts[-max(STREAK_LOOKBACK_MAX, 2):]

    dates = [d for d, _ in pts]
    vals = [v for _, v in pts]
    n = len(vals)

    # For each i, compute z60/p252/zΔ60/pΔ60/ret1%60 using value windows up to i
    signals: List[str] = []
    for i in range(n):
        x = vals[i]
        prev = vals[i - 1] if i - 1 >= 0 else None

        # w60 window ending at i (last 60 valid points)
        w60_vals = vals[max(0, i - (W60 - 1)) : i + 1]
        m60, sd60 = mean_std_ddof0(w60_vals)
        z60 = None if sd60 == 0 else (x - m60) / sd60

        # w252 percentile window ending at i
        w252_vals = vals[max(0, i - (W252 - 1)) : i + 1]
        p252 = percentile_leq(w252_vals, x)

        # deltas based on previous day's z/p (computed with its own windows)
        if i - 1 >= 0:
            x_prev = vals[i - 1]
            w60_prev = vals[max(0, (i - 1) - (W60 - 1)) : (i - 1) + 1]
            m60p, sd60p = mean_std_ddof0(w60_prev)
            z60_prev = None if sd60p == 0 else (x_prev - m60p) / sd60p

            w252_prev = vals[max(0, (i - 1) - (W252 - 1)) : (i - 1) + 1]
            p252_prev = percentile_leq(w252_prev, x_prev)

            zdel60 = None if (z60 is None or z60_prev is None) else (z60 - z60_prev)
            pdel60 = p252 - p252_prev
        else:
            zdel60 = None
            pdel60 = None

        # ret1%60 (percent units) based on prev value denom
        if prev is None or abs(prev) < 1e-12:
            ret1pct60 = None
        else:
            ret1pct60 = ((x - prev) / abs(prev)) * 100.0

        sig, _, _, _ = compute_signal_tag_near_from_metrics(
            z60=z60,
            p252=p252,
            zdel60=zdel60,
            pdel60=pdel60,
            ret1pct60=ret1pct60,
        )
        signals.append(sig)

    # PrevSignal is signal at previous point (n-2)
    prev_signal = signals[-2] if len(signals) >= 2 else "NA"

    # StreakWA: count backwards from latest while signal in {WATCH, ALERT}
    streak = 0
    for s in reversed(signals):
        if s in ("WATCH", "ALERT"):
            streak += 1
        else:
            break

    return prev_signal, streak


def write_outputs(out_md: str, out_json: str, meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    payload = {"meta": meta, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines: List[str] = []
    lines.append(f"# Risk Dashboard ({meta.get('module','')})")
    lines.append("")
    lines.append(f"- RUN_TS_UTC: `{meta.get('run_ts_utc','')}`")
    lines.append(f"- STATS.generated_at_utc: `{meta.get('stats_generated_at_utc','')}`")
    lines.append(f"- STATS.as_of_ts: `{meta.get('stats_as_of_ts','')}`")
    lines.append(f"- script_version: `{meta.get('script_version','')}`")
    lines.append(f"- stale_hours: `{meta.get('stale_hours','')}`")
    lines.append(f"- history_used_for_streak: `{meta.get('history_path','NA')}`")
    lines.append(f"- streak_calc: `{meta.get('streak_calc','NA')}`")
    lines.append(
        "- signal_rules: "
        f"`Extreme(|Z60|>={Z60_WATCH_ABS:g} (WATCH), |Z60|>={Z60_ALERT_ABS:g} (ALERT), "
        f"P252>={P252_EXTREME_HI:g} or <={P252_EXTREME_LO:g} (WATCH/INFO), P252<={P252_ALERT_LO:g} (ALERT)); "
        f"Jump(|ZΔ60|>={ZDELTA60_JUMP_ABS:g} OR |PΔ60|>={PDELTA60_JUMP_ABS:g} OR |ret1%60|>={RET1PCT60_JUMP_ABS:g}); "
        f"Near(within {NEAR_FRAC*100:.0f}% of jump thresholds); "
        "INFO if only long-extreme and no jump and |Z60|<2`"
    )
    lines.append("")

    header = [
        "Signal", "Tag", "Near", "PrevSignal", "StreakWA",
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
            r.get("signal_level", "NONE"),
            r.get("tag", "NA"),
            r.get("near", "NA"),
            r.get("prev_signal", "NA"),
            fmt(r.get("streak_wa"), nd=0),
            r.get("series", ""),
            r.get("dq", ""),
            fmt(r.get("age_hours"), nd=2),
            fmt(r.get("data_date")),
            fmt(r.get("value"), nd=6),
            fmt(r.get("z60"), nd=6),
            fmt(r.get("p252"), nd=6),
            fmt(r.get("z_delta_60"), nd=6),
            fmt(r.get("p_delta_60"), nd=6),
            fmt(r.get("ret1_pct_60"), nd=6),
            fmt(r.get("reason")),
            fmt(r.get("source_url")),
            fmt(r.get("as_of_ts")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, help="Path to stats_latest.json (repo path)")
    ap.add_argument("--history", default=None, help="Path to history_lite.json (repo path). If omitted, streak disabled.")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", default="market_cache")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    history_obj: Optional[Dict[str, Any]] = None
    if args.history and os.path.exists(args.history):
        try:
            with open(args.history, "r", encoding="utf-8") as f:
                history_obj = json.load(f)
        except Exception:
            history_obj = None

    if not os.path.exists(args.stats):
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "module": args.module,
            "stale_hours": args.stale_hours,
            "history_path": args.history or "NA",
            "streak_calc": "disabled (missing stats file)",
            "error": f"stats file missing: {args.stats}",
        }
        write_outputs(args.out_md, args.out_json, meta, [])
        return

    with open(args.stats, "r", encoding="utf-8") as f:
        stats = json.load(f)

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "stale_hours": args.stale_hours,
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats.get("as_of_ts"),
        "script_version": stats.get("script_version"),
        "series_count": stats.get("series_count"),
        "history_path": args.history or "NA",
        "streak_calc": (
            "recompute z60/p252/zΔ60/pΔ60/ret1% from history_lite values; "
            "ret1% denom = abs(prev_value) else NA"
        ) if history_obj is not None else "disabled (history missing/unreadable)",
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

        # Signal/Tag/Near based on stats_latest metrics (authoritative for "today")
        signal_level, reason, tag, near = compute_signal_tag_near_from_metrics(
            z60=w60.get("z"),
            p252=w252.get("p"),
            zdel60=w60.get("z_delta"),
            pdel60=w60.get("p_delta"),
            ret1pct60=w60.get("ret1_pct"),
        )

        # PrevSignal/Streak from history_lite
        if history_obj is not None:
            prev_signal, streak = compute_prevsignal_and_streak(history_obj, sid)
        else:
            prev_signal, streak = "NA", 0

        row: Dict[str, Any] = {
            "module": args.module,
            "series": sid,
            "value": latest.get("value"),
            "data_date": latest.get("data_date"),
            "as_of_ts": latest.get("as_of_ts"),
            "source_url": latest.get("source_url"),
            "dq": dq,
            "age_hours": age_hours,

            # short window stats (w60)
            "z60": w60.get("z"),
            "p60": w60.get("p"),
            "ret1_delta_60": w60.get("ret1_delta"),
            "ret1_pct_60": w60.get("ret1_pct"),
            "dev_ma_60": w60.get("dev_ma"),
            "z_delta_60": w60.get("z_delta"),
            "p_delta_60": w60.get("p_delta"),

            # long window stats (w252)
            "z252": w252.get("z"),
            "p252": w252.get("p"),

            # signals
            "signal_level": signal_level,
            "reason": reason,
            "tag": tag,
            "near": near,

            # streak
            "prev_signal": prev_signal,
            "streak_wa": streak,
        }

        rows.append(row)

    # Sorting:
    # 1) Signal (ALERT, WATCH, INFO, NONE)
    # 2) For WATCH only: Near!=NA first, then higher streak first
    # 3) DQ (MISSING, STALE, OK)
    # 4) series name
    sig_order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    dq_order = {"MISSING": 0, "STALE": 1, "OK": 2}

    def watch_near_rank(r: Dict[str, Any]) -> int:
        if r.get("signal_level") != "WATCH":
            return 9
        return 0 if r.get("near") not in (None, "NA", "") else 1

    def streak_rank(r: Dict[str, Any]) -> int:
        # higher streak first -> negative
        try:
            return -int(r.get("streak_wa") or 0)
        except Exception:
            return 0

    rows.sort(key=lambda r: (
        sig_order.get(r.get("signal_level", "NONE"), 9),
        watch_near_rank(r),
        streak_rank(r),
        dq_order.get(r.get("dq", "OK"), 9),
        r.get("series", ""),
    ))

    write_outputs(args.out_md, args.out_json, meta, rows)


if __name__ == "__main__":
    main()