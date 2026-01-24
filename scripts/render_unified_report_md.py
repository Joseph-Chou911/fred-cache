#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List

NA = "NA"

def read_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def fmt(x: Any) -> str:
    if x is None:
        return NA
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)

def g(d: Dict[str, Any], key: str, default: Any = None) -> Any:
    return d.get(key, default) if isinstance(d, dict) else default

def safe_path(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur

def margin_5d_sum(twm_latest: Dict[str, Any], which: str) -> Dict[str, Any]:
    # expects schema: taiwan_margin_financing_latest_v1
    series = g(twm_latest, "series", {})
    blk = g(series, which, {})
    rows = g(blk, "rows", [])
    s = 0.0
    n = 0
    if isinstance(rows, list):
        for r in rows[:5]:
            try:
                s += float(r.get("chg_yi"))
                n += 1
            except Exception:
                pass
    return {
        "data_date": g(blk, "data_date", NA),
        "latest": rows[0] if isinstance(rows, list) and rows else None,
        "sum_last_n": s,
        "n": n,
        "source_url": g(blk, "source_url", NA),
    }

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    args = ap.parse_args()

    u = read_json(args.inp)
    modules = g(u, "modules", {})

    def status(name: str) -> str:
        return fmt(safe_path(modules, [name, "status"], NA))

    out: List[str] = []
    out.append("# Unified Risk Dashboard Report")
    out.append("")
    out.append("## Module Status")
    out.append(f"- market_cache: {status('market_cache')}")
    out.append(f"- fred_cache: {status('fred_cache')}")
    out.append(f"- taiwan_margin_financing: {status('taiwan_margin_financing')}")
    out.append("")
    out.append(f"- unified_generated_at_utc: {fmt(g(u, 'generated_at_utc', NA))}")
    out.append("")

    # market (best-effort)
    m = safe_path(modules, ["market_cache", "dashboard_latest"], None)
    out.append("## market_cache (best-effort summary)")
    if isinstance(m, dict):
        meta = g(m, "meta", {})
        out.append(f"- as_of_ts: {fmt(g(meta, 'stats_as_of_ts', NA))}")
        out.append(f"- run_ts_utc: {fmt(g(meta, 'run_ts_utc', NA))}")
        out.append(f"- series_count: {fmt(g(meta, 'series_count', NA))}")
        out.append("")
    else:
        out.append("- NA (missing/failed)")
        out.append("")

    # fred (best-effort)
    f = safe_path(modules, ["fred_cache", "dashboard_latest"], None)
    out.append("## fred_cache (best-effort summary)")
    if isinstance(f, dict):
        meta = g(f, "meta", {})
        summ = g(meta, "summary", {})
        out.append(f"- as_of_ts: {fmt(g(meta, 'stats_as_of_ts', NA))}")
        out.append(f"- run_ts_utc: {fmt(g(meta, 'run_ts_utc', NA))}")
        if isinstance(summ, dict):
            out.append(f"- ALERT/WATCH/INFO/NONE: {fmt(summ.get('ALERT'))}/{fmt(summ.get('WATCH'))}/{fmt(summ.get('INFO'))}/{fmt(summ.get('NONE'))}")
            out.append(f"- CHANGED: {fmt(summ.get('CHANGED'))}")
        out.append("")
    else:
        out.append("- NA (missing/failed)")
        out.append("")

    # taiwan margin
    t = safe_path(modules, ["taiwan_margin_financing", "latest"], None)
    out.append("## taiwan_margin_financing (TWSE/TPEX)")
    if isinstance(t, dict):
        twse = margin_5d_sum(t, "TWSE")
        tpex = margin_5d_sum(t, "TPEX")

        out.append(f"### TWSE (data_date={fmt(twse['data_date'])})")
        out.append(f"- source_url: {fmt(twse['source_url'])}")
        if twse["latest"]:
            out.append(f"- latest: date={fmt(twse['latest'].get('date'))}, balance_yi={fmt(twse['latest'].get('balance_yi'))}, chg_yi={fmt(twse['latest'].get('chg_yi'))}")
        out.append(f"- sum_chg_yi_last{twse['n']}: {fmt(twse['sum_last_n'])}")
        out.append("")

        out.append(f"### TPEX (data_date={fmt(tpex['data_date'])})")
        out.append(f"- source_url: {fmt(tpex['source_url'])}")
        if tpex["latest"]:
            out.append(f"- latest: date={fmt(tpex['latest'].get('date'))}, balance_yi={fmt(tpex['latest'].get('balance_yi'))}, chg_yi={fmt(tpex['latest'].get('chg_yi'))}")
        out.append(f"- sum_chg_yi_last{tpex['n']}: {fmt(tpex['sum_last_n'])}")
        out.append("")
    else:
        out.append("- NA (missing/failed)")
        out.append("")

    Path(args.outp).parent.mkdir(parents=True, exist_ok=True)
    Path(args.outp).write_text("\n".join(out), encoding="utf-8")

if __name__ == "__main__":
    main()