#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_tw0050_bb_report.py

Goal:
- Read cache_dir/stats_latest.json (required)
- Optionally read cache_dir/chip_overlay.json (if exists)
- Produce a markdown report that includes:
  - core BB stats (best-effort, schema-tolerant)
  - forward_mdd block (best-effort)
  - chip overlay summary (units/borrow/institutions + staleness + dq flags)

Constraints:
- Deterministic: do NOT fetch any web data here.
- Fail-soft: if chip_overlay.json missing or malformed, still produce report.
"""

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Tuple

TZ_TAIPEI = dt.timezone(dt.timedelta(hours=8))


def read_json(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


def fmt_int(x: Any) -> str:
    if isinstance(x, bool) or x is None:
        return "N/A"
    if isinstance(x, (int,)):
        return f"{x:,}"
    if isinstance(x, float):
        return f"{int(x):,}"
    return "N/A"


def fmt_float(x: Any, nd: int = 4) -> str:
    if x is None:
        return "N/A"
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return f"{float(x):.{nd}f}"
    return "N/A"


def fmt_pct(x: Any, nd: int = 2) -> str:
    if x is None:
        return "N/A"
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return f"{float(x)*100.0:.{nd}f}%"
    return "N/A"


def parse_yyyymmdd(s: Any) -> Optional[dt.date]:
    if not isinstance(s, str):
        return None
    s = s.strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return dt.datetime.strptime(s, "%Y%m%d").date()
    except Exception:
        return None


def pick(d: Dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def build_report(stats: Dict[str, Any], chip: Optional[Dict[str, Any]]) -> str:
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_local = now_utc.astimezone(TZ_TAIPEI)

    lines = []
    lines.append("# TW0050 BB(60,2) + ForwardMDD(20D) Report")
    lines.append("")
    lines.append(f"- report_generated_at_utc: `{now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}`")
    lines.append(f"- report_generated_at_local: `{now_local.strftime('%Y-%m-%d %H:%M:%S %z')}`")
    lines.append("")

    # --- Core stats (schema-tolerant) ---
    meta = stats.get("meta", {}) if isinstance(stats, dict) else {}
    lines.append("## 1) Core Stats (from stats_latest.json)")
    lines.append("")
    lines.append(f"- stats.meta.run_ts_utc: `{pick(stats,'meta','run_ts_utc') or 'N/A'}`")
    lines.append(f"- stats.meta.stats_generated_at_utc: `{pick(stats,'meta','stats_generated_at_utc') or 'N/A'}`")
    lines.append(f"- stats.meta.stats_as_of_ts: `{pick(stats,'meta','stats_as_of_ts') or pick(stats,'meta','as_of_ts') or 'N/A'}`")
    lines.append(f"- stats.meta.day_key_local: `{pick(stats,'meta','day_key_local') or stats.get('day_key_local') or 'N/A'}`")
    lines.append("")

    # Try to show last close / band position if present
    last_close = pick(stats, "last", "close") or stats.get("close") or pick(stats, "price", "close") or stats.get("last_close")
    bb = stats.get("bb", {}) if isinstance(stats.get("bb"), dict) else {}
    z = bb.get("z") or stats.get("z") or pick(stats, "bb", "z")
    pos = bb.get("position_in_band") or stats.get("position_in_band")

    lines.append("### Snapshot")
    lines.append("")
    lines.append(f"- close: {fmt_float(last_close, 4)}")
    lines.append(f"- bb.z: {fmt_float(z, 3)}")
    lines.append(f"- bb.position_in_band: {fmt_float(pos, 3)}")
    lines.append("")

    # forward_mdd block (best-effort)
    fwd = stats.get("forward_mdd", {}) if isinstance(stats.get("forward_mdd"), dict) else {}
    if fwd:
        lines.append("### Forward MDD (best-effort)")
        lines.append("")
        lines.append(f"- min_entry_date: `{fwd.get('min_entry_date','N/A')}`")
        lines.append(f"- min_entry_price: {fmt_float(fwd.get('min_entry_price'), 4)}")
        lines.append(f"- min_future_date: `{fwd.get('min_future_date','N/A')}`")
        lines.append(f"- min_future_price: {fmt_float(fwd.get('min_future_price'), 4)}")
        lines.append(f"- forward_mdd_pct: {fmt_pct(fwd.get('forward_mdd_pct'), 2)}")
        lines.append("")

    # --- Chip overlay ---
    lines.append("## 2) Chip Overlay (TWSE T86 + TWT72U + Yuanta PCF)")
    lines.append("")
    if chip is None:
        lines.append("- chip_overlay.json: N/A (file missing or unreadable)")
        lines.append("")
        return "\n".join(lines)

    cmeta = chip.get("meta", {}) if isinstance(chip.get("meta"), dict) else {}
    sources = chip.get("sources", {}) if isinstance(chip.get("sources"), dict) else {}
    dq_flags = pick(chip, "dq", "flags") or []

    aligned_last = cmeta.get("aligned_last_date")
    aligned_date = parse_yyyymmdd(aligned_last)
    data_age_days = None
    if aligned_date is not None:
        data_age_days = (now_local.date() - aligned_date).days

    lines.append(f"- chip.meta.run_ts_utc: `{cmeta.get('run_ts_utc','N/A')}`")
    lines.append(f"- chip.meta.aligned_last_date: `{aligned_last or 'N/A'}`")
    lines.append(f"- chip.data_age_days (local): `{data_age_days if data_age_days is not None else 'N/A'}`")
    lines.append(f"- dq.flags: `{dq_flags}`")
    lines.append("")
    lines.append("### Sources (for audit)")
    lines.append("")
    lines.append(f"- T86: `{sources.get('t86_tpl','N/A')}`")
    lines.append(f"- TWT72U: `{sources.get('twt72u_tpl','N/A')}`")
    lines.append(f"- PCF: `{sources.get('pcf_url','N/A')}`")
    lines.append("")

    data = chip.get("data", {}) if isinstance(chip.get("data"), dict) else {}
    units = data.get("etf_units", {}) if isinstance(data.get("etf_units"), dict) else {}
    borrow = data.get("borrow_summary", {}) if isinstance(data.get("borrow_summary"), dict) else {}
    agg = data.get("t86_agg", {}) if isinstance(data.get("t86_agg"), dict) else {}
    derived = data.get("derived", {}) if isinstance(data.get("derived"), dict) else {}

    # Compute derived on the fly if missing
    u0 = units.get("units_outstanding")
    du = units.get("units_chg_1d")
    bs = borrow.get("borrow_shares")

    borrow_ratio = derived.get("borrow_ratio")
    units_chg_pct = derived.get("units_chg_pct_1d")
    borrow_ratio_chg_pp = derived.get("borrow_ratio_chg_pp")

    if borrow_ratio is None and isinstance(u0, int) and u0 > 0 and isinstance(bs, int):
        borrow_ratio = bs / u0
    if units_chg_pct is None and isinstance(u0, int) and isinstance(du, int):
        u_prev = u0 - du
        if u_prev > 0:
            units_chg_pct = du / u_prev

    lines.append("### ETF Units (PCF)")
    lines.append("")
    lines.append(f"- trade_date: `{units.get('trade_date','N/A')}`")
    lines.append(f"- posting_dt: `{units.get('posting_dt','N/A')}`")
    lines.append(f"- units_outstanding: {fmt_int(units.get('units_outstanding'))}")
    lines.append(f"- units_chg_1d: {fmt_int(units.get('units_chg_1d'))} ({fmt_pct(units_chg_pct, 3)})")
    lines.append(f"- units.dq: `{units.get('dq', [])}`")
    lines.append("")

    lines.append("### Securities Lending (TWT72U)")
    lines.append("")
    lines.append(f"- asof_date: `{borrow.get('asof_date','N/A')}`")
    lines.append(f"- borrow_shares: {fmt_int(borrow.get('borrow_shares'))}")
    lines.append(f"- borrow_shares_chg_1d: {fmt_int(borrow.get('borrow_shares_chg_1d'))}")
    lines.append(f"- borrow_mv_ntd: {fmt_float(borrow.get('borrow_mv_ntd'), 1)}")
    lines.append(f"- borrow_mv_ntd_chg_1d: {fmt_float(borrow.get('borrow_mv_ntd_chg_1d'), 1)}")
    lines.append(f"- borrow_ratio: {fmt_pct(borrow_ratio, 4)}")
    if borrow_ratio_chg_pp is not None:
        lines.append(f"- borrow_ratio_chg_pp: {fmt_float(borrow_ratio_chg_pp, 4)} pp")
    lines.append("")

    lines.append("### Institutional Net (T86) - Rolling Window Aggregate")
    lines.append("")
    lines.append(f"- window_n: `{agg.get('window_n','N/A')}`")
    lines.append(f"- days_used: `{agg.get('days_used','N/A')}`")
    lines.append(f"- foreign_net_shares_sum: {fmt_int(agg.get('foreign_net_shares_sum'))}")
    lines.append(f"- trust_net_shares_sum: {fmt_int(agg.get('trust_net_shares_sum'))}")
    lines.append(f"- dealer_net_shares_sum: {fmt_int(agg.get('dealer_net_shares_sum'))}")
    lines.append(f"- total3_net_shares_sum: {fmt_int(agg.get('total3_net_shares_sum'))}")
    lines.append("")

    # Staleness warning line (explicit, not speculative)
    if data_age_days is not None and data_age_days > 2:
        lines.append("### Data Quality Note")
        lines.append("")
        lines.append(f"- WARNING: chip overlay data is stale (aligned_last_date={aligned_last}, data_age_days={data_age_days}).")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--tail_days", type=int, default=15)  # retained for compatibility; not used unless you extend
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    stats_path = os.path.join(args.cache_dir, "stats_latest.json")
    stats, err = read_json(stats_path)
    if stats is None:
        raise SystemExit(f"ERROR: failed to read stats_latest.json: {stats_path} ({err})")

    chip_path = os.path.join(args.cache_dir, "chip_overlay.json")
    chip = None
    if os.path.exists(chip_path):
        chip, _ = read_json(chip_path)

    md = build_report(stats, chip)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"OK: wrote {args.out}")


if __name__ == "__main__":
    main()