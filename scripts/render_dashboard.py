#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Dashboard renderer (MVP+signals v3: Tag + Near)
# - Reads stats_latest.json and flattens per-series rows
# - Signals: ALERT / WATCH / INFO / NONE (改法 B)
# - Adds:
#     Tag  : which class of trigger fired (EXTREME_Z / JUMP_RET / JUMP_P / JUMP_ZD / LONG_EXTREME)
#     Near : near-threshold hints for jump metrics (within 10% of threshold)
#
# Signal logic (改法 B):
#   Extreme:
#     - |Z60| >= 2.0  (WATCH)
#     - |Z60| >= 2.5  (ALERT)
#     - P252 >= 95 or P252 <= 5  (WATCH/INFO)
#     - P252 <= 2 (ALERT; very extreme low tail)
#   Jump:
#     - |ZΔ60| >= 0.75
#     - |PΔ60| >= 15
#     - |ret1%60| >= 2.0   (percent units; 2.0 == 2%)
#   Level:
#     - INFO  if ONLY long-extreme and no jump and |Z60|<2
#     - ALERT if (|Z60|>=2.5) OR (P252<=2) OR (jump_hits>=2 and includes ZΔ60) OR (|Z60|>=2.0 and jump_hits>=1)
#     - WATCH if (|Z60|>=2.0) OR (P252>=95 or <=5) OR (jump_hits>=1)
#     - NONE  otherwise
#
# Near logic:
#   - within 10% of jump threshold but not crossing it:
#       NEAR:ZΔ60, NEAR:PΔ60, NEAR:ret1%60

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
    """
    True if abs_val is in [ (1-near_frac)*thr, thr ) .
    """
    if abs_val is None:
        return False
    lo = (1.0 - near_frac) * thr
    return (abs_val >= lo) and (abs_val < thr)


def compute_signal_tag_near(row: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """
    Returns (signal_level, reason_str, tag_str, near_str)
    """
    reasons: List[str] = []
    tags: List[str] = []
    nears: List[str] = []

    z60 = row.get("z60")
    p252 = row.get("p252")
    zdel = row.get("z_delta_60")
    pdel = row.get("p_delta_60")
    r1p = row.get("ret1_pct_60")

    az60 = safe_abs(z60)
    azd = safe_abs(zdel)
    apd = safe_abs(pdel)
    ar1p = safe_abs(r1p)

    # -------------------------
    # Extreme checks
    # -------------------------
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
            # EXTREME_Z already tagged

    p252_hi = False
    p252_lo = False
    p252_alert_lo = False
    if isinstance(p252, (int, float)):
        p252_f = float(p252)
        if p252_f >= P252_EXTREME_HI:
            p252_hi = True
            reasons.append(f"P252>={P252_EXTREME_HI:g}")
            tags.append("LONG_EXTREME")
        if p252_f <= P252_EXTREME_LO:
            p252_lo = True
            reasons.append(f"P252<={P252_EXTREME_LO:g}")
            tags.append("LONG_EXTREME")
        if p252_f <= P252_ALERT_LO:
            p252_alert_lo = True
            reasons.append(f"P252<={P252_ALERT_LO:g}")
            # LONG_EXTREME already tagged

    long_extreme_only = (p252_hi or p252_lo) and (not z60_watch)

    # -------------------------
    # Jump checks
    # -------------------------
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

    # -------------------------
    # Level assignment (改法 B)
    # -------------------------
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

    # dedup tags while keeping order
    seen = set()
    tags2: List[str] = []
    for t in tags:
        if t not in seen:
            tags2.append(t)
            seen.add(t)
    tag_str = ",".join(tags2) if tags2 else "NA"

    near_str = ",".join(nears) if nears else "NA"
    return level, reason_str, tag_str, near_str


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
        "Signal", "Tag", "Near", "Series", "DQ", "age_h",
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
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", default="market_cache")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    if not os.path.exists(args.stats):
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "module": args.module,
            "stale_hours": args.stale_hours,
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
        }

        signal_level, reason, tag, near = compute_signal_tag_near(row)
        row["signal_level"] = signal_level
        row["reason"] = reason
        row["tag"] = tag
        row["near"] = near

        rows.append(row)

    # Sorting: Signal (ALERT, WATCH, INFO, NONE), then DQ (MISSING, STALE, OK), then series
    sig_order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    dq_order = {"MISSING": 0, "STALE": 1, "OK": 2}
    rows.sort(key=lambda r: (
        sig_order.get(r.get("signal_level", "NONE"), 9),
        dq_order.get(r.get("dq", "OK"), 9),
        r.get("series", "")
    ))

    write_outputs(args.out_md, args.out_json, meta, rows)


if __name__ == "__main__":
    main()