#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Dashboard renderer (MVP+signals v2)
# - Reads stats_latest.json and flattens per-series rows
# - Adds simple, auditable anomaly signals: ALERT / WATCH / INFO / NONE
# - Avoids "market meaning" direction rules (no guessed per-series semantics)
#
# Signal logic (改法 B):
#   1) Extreme checks (statical position):
#        - |Z60| >= 2.0  (WATCH)
#        - |Z60| >= 2.5  (ALERT)
#        - P252 >= 95 or P252 <= 5  (WATCH by default)
#        - P252 <= 2 (ALERT; very extreme low)
#   2) Jump checks (short-term acceleration):
#        - |ZΔ60| >= 0.75
#        - |PΔ60| >= 15
#        - |ret1%60| >= 2.0   (ret1_pct is already percent units; 2.0 == 2%)
#   3) Level assignment:
#        - ALERT if (|Z60|>=2.5) OR (P252<=2) OR (jump_hits>=2 and includes ZΔ60) OR (|Z60|>=2.0 and jump_hits>=1)
#        - WATCH if (|Z60|>=2.0) OR (P252>=95 or <=5) OR (jump_hits>=1)
#        - INFO  if ONLY long extreme (P252>=95 or <=5) and NO jump and |Z60|<2.0
#        - NONE  otherwise
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

# Jump thresholds (stricter than v1)
ZDELTA60_JUMP_ABS = 0.75
PDELTA60_JUMP_ABS = 15.0
RET1PCT60_JUMP_ABS = 2.0  # percent units; 2.0 == 2%


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


def compute_signal(row: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (signal_level, reason_str)
    signal_level in: ALERT, WATCH, INFO, NONE
    """
    reasons: List[str] = []

    z60 = row.get("z60")
    p252 = row.get("p252")
    zdel = row.get("z_delta_60")
    pdel = row.get("p_delta_60")
    r1p = row.get("ret1_pct_60")

    # -------------------------
    # Extreme checks
    # -------------------------
    az60 = safe_abs(z60)
    z60_watch = False
    z60_alert = False
    if az60 is not None:
        if az60 >= Z60_WATCH_ABS:
            z60_watch = True
            reasons.append(f"|Z60|>={Z60_WATCH_ABS:g}")
        if az60 >= Z60_ALERT_ABS:
            z60_alert = True
            reasons.append(f"|Z60|>={Z60_ALERT_ABS:g}")

    p252_hi = False
    p252_lo = False
    p252_alert_lo = False
    if isinstance(p252, (int, float)):
        p252_f = float(p252)
        if p252_f >= P252_EXTREME_HI:
            p252_hi = True
            reasons.append(f"P252>={P252_EXTREME_HI:g}")
        if p252_f <= P252_EXTREME_LO:
            p252_lo = True
            reasons.append(f"P252<={P252_EXTREME_LO:g}")
        if p252_f <= P252_ALERT_LO:
            p252_alert_lo = True
            reasons.append(f"P252<={P252_ALERT_LO:g}")

    long_extreme_only = (p252_hi or p252_lo) and (not z60_watch)

    # -------------------------
    # Jump checks
    # -------------------------
    jump_hits = 0
    has_zdelta_jump = False

    azd = safe_abs(zdel)
    if azd is not None and azd >= ZDELTA60_JUMP_ABS:
        reasons.append(f"|ZΔ60|>={ZDELTA60_JUMP_ABS:g}")
        jump_hits += 1
        has_zdelta_jump = True

    apd = safe_abs(pdel)
    if apd is not None and apd >= PDELTA60_JUMP_ABS:
        reasons.append(f"|PΔ60|>={PDELTA60_JUMP_ABS:g}")
        jump_hits += 1

    ar1p = safe_abs(r1p)
    if ar1p is not None and ar1p >= RET1PCT60_JUMP_ABS:
        reasons.append(f"|ret1%60|>={RET1PCT60_JUMP_ABS:g}")
        jump_hits += 1

    # -------------------------
    # Level assignment (改法 B)
    # -------------------------
    # INFO: only long extreme (P252 hi/lo) and no jump and |Z60|<2
    if long_extreme_only and jump_hits == 0:
        level = "INFO"
    else:
        # ALERT conditions:
        # - very high short extreme (|Z60|>=2.5)
        # - very extreme low tail (P252<=2)
        # - acceleration cluster (jump_hits>=2 and includes z_delta jump)
        # - short extreme + any jump
        if z60_alert or p252_alert_lo or (jump_hits >= 2 and has_zdelta_jump) or (z60_watch and jump_hits >= 1):
            level = "ALERT"
        # WATCH conditions:
        # - moderate short extreme OR long extreme OR any jump
        elif z60_watch or p252_hi or p252_lo or jump_hits >= 1:
            level = "WATCH"
        else:
            level = "NONE"

    reason_str = ";".join(reasons) if reasons else "NA"
    return level, reason_str


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
        "INFO if only long-extreme and no jump and |Z60|<2`"
    )
    lines.append("")

    header = [
        "Signal", "Series", "DQ", "age_h",
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

        signal_level, reason = compute_signal(row)
        row["signal_level"] = signal_level
        row["reason"] = reason

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