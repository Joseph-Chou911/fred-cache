#!/usr/bin/env python3
# tools/render_dashboard.py
# Minimal dashboard renderer for market_cache/stats_latest.json
# - No market-threshold judgement by default (avoid guessed rules)
# - Only produces a flat table + basic data freshness DQ

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    # accept "Z" suffix
    ts2 = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts2)
    except Exception:
        return None

def dq_from_ts(run_ts: datetime, as_of_ts: Optional[datetime], stale_hours: float) -> str:
    if as_of_ts is None:
        return "MISSING"
    age_hours = (run_ts - as_of_ts).total_seconds() / 3600.0
    return "STALE" if age_hours > stale_hours else "OK"

def get_w(d: Dict[str, Any], key: str) -> Dict[str, Any]:
    return d.get("windows", {}).get(key, {}) if isinstance(d.get("windows"), dict) else {}

def fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return str(x)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True, help="Path to stats_latest.json (repo path)")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--module", default="market_cache")
    ap.add_argument("--stale-hours", type=float, default=36.0)
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc)

    if not os.path.exists(args.stats):
        rows: List[Dict[str, Any]] = []
        meta = {
            "run_ts_utc": run_ts.isoformat(),
            "module": args.module,
            "error": f"stats file missing: {args.stats}",
        }
        write_outputs(args.out_md, args.out_json, meta, rows)
        return

    with open(args.stats, "r", encoding="utf-8") as f:
        stats = json.load(f)

    meta = {
        "run_ts_utc": run_ts.isoformat(),
        "module": args.module,
        "stats_generated_at_utc": stats.get("generated_at_utc"),
        "stats_as_of_ts": stats.get("as_of_ts"),
        "script_version": stats.get("script_version"),
        "series_count": stats.get("series_count"),
    }

    rows = []
    series = stats.get("series", {})
    if not isinstance(series, dict):
        series = {}

    for sid, s in series.items():
        latest = s.get("latest", {}) if isinstance(s.get("latest"), dict) else {}
        w60 = get_w(s, "w60")
        w252 = get_w(s, "w252")

        latest_asof_dt = parse_iso(latest.get("as_of_ts"))
        dq = dq_from_ts(run_ts, latest_asof_dt, args.stale_hours)

        row = {
            "module": args.module,
            "series": sid,
            "value": latest.get("value"),
            "data_date": latest.get("data_date"),
            "as_of_ts": latest.get("as_of_ts"),
            "source_url": latest.get("source_url"),
            "z60": w60.get("z"),
            "p60": w60.get("p"),
            "ret1_delta_60": w60.get("ret1_delta"),
            "ret1_pct_60": w60.get("ret1_pct"),
            "dev_ma_60": w60.get("dev_ma"),
            "z252": w252.get("z"),
            "p252": w252.get("p"),
            "dq": dq,
            # intentionally no status/trigger unless you later provide explicit rules
            "status": "NA",
            "trigger": "NA",
        }
        rows.append(row)

    # Sort: put worst DQ first, then series name
    dq_order = {"MISSING": 0, "STALE": 1, "OK": 2}
    rows.sort(key=lambda r: (dq_order.get(r.get("dq", "OK"), 9), r.get("series", "")))

    write_outputs(args.out_md, args.out_json, meta, rows)

def write_outputs(out_md: str, out_json: str, meta: Dict[str, Any], rows: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    payload = {"meta": meta, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Markdown
    lines = []
    lines.append(f"# Risk Dashboard ({meta.get('module','')})")
    lines.append("")
    lines.append(f"- RUN_TS_UTC: `{meta.get('run_ts_utc','')}`")
    lines.append(f"- STATS.generated_at_utc: `{meta.get('stats_generated_at_utc','')}`")
    lines.append(f"- STATS.as_of_ts: `{meta.get('stats_as_of_ts','')}`")
    lines.append(f"- script_version: `{meta.get('script_version','')}`")
    lines.append("")

    header = ["Series","DQ","data_date","value","z60","p252","ret1_delta(60)","ret1_pct(60)","Source","as_of_ts"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for r in rows:
        lines.append("| " + " | ".join([
            r.get("series",""),
            r.get("dq",""),
            fmt(r.get("data_date")),
            fmt(r.get("value"), nd=6),
            fmt(r.get("z60"), nd=6),
            fmt(r.get("p252"), nd=6),
            fmt(r.get("ret1_delta_60"), nd=6),
            fmt(r.get("ret1_pct_60"), nd=6),
            fmt(r.get("source_url")),
            fmt(r.get("as_of_ts")),
        ]) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()