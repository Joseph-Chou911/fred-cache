#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List, Tuple

NA = "NA"

# -----------------------
# helpers
# -----------------------
def read_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def fmt(x: Any) -> str:
    if x is None:
        return NA
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
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

def get_any(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Try multiple possible keys (for schema drift)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d:
            return d.get(k)
    return default

def md_kv(lines: List[str], k: str, v: Any) -> None:
    lines.append(f"- {k}: {fmt(v)}")

def md_table(lines: List[str], headers: List[str], rows: List[List[Any]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(fmt(x) for x in r) + " |")

def rank_signal(level: str) -> int:
    order = {"ALERT": 4, "WATCH": 3, "INFO": 2, "NONE": 1}
    return order.get(level or "", 0)

def pick_rows(rows: List[Dict[str, Any]], allowed_levels: Tuple[str, ...]) -> List[Dict[str, Any]]:
    out = [r for r in rows if g(r, "signal_level") in allowed_levels]
    out.sort(key=lambda r: (-rank_signal(g(r, "signal_level", "")), str(g(r, "series", ""))))
    return out

# -----------------------
# margin stats
# -----------------------
def margin_stats(twm_latest: Dict[str, Any], which: str) -> Dict[str, Any]:
    series = g(twm_latest, "series", {})
    blk = g(series, which, {})
    rows = g(blk, "rows", [])
    chgs: List[float] = []
    if isinstance(rows, list):
        for r in rows[:5]:
            try:
                chgs.append(float(r.get("chg_yi")))
            except Exception:
                pass

    s = sum(chgs) if chgs else 0.0
    n = len(chgs)
    pos = sum(1 for x in chgs if x > 0) if chgs else 0
    neg = sum(1 for x in chgs if x < 0) if chgs else 0
    mx = max(chgs) if chgs else None
    mn = min(chgs) if chgs else None

    latest = rows[0] if isinstance(rows, list) and rows else None

    return {
        "data_date": g(blk, "data_date", NA),
        "source_url": g(blk, "source_url", NA),
        "latest": latest,
        "sum_last5": s,
        "avg_last5": (s / n) if n else None,
        "pos_days_last5": pos,
        "neg_days_last5": neg,
        "max_chg_last5": mx,
        "min_chg_last5": mn,
        "n_used": n,
    }

# -----------------------
# extract rows
# -----------------------
def extract_market_rows(market_latest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = g(market_latest, "rows", [])
    return rows if isinstance(rows, list) else []

def extract_fred_rows(fred_latest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = g(fred_latest, "rows", [])
    return rows if isinstance(rows, list) else []

# -----------------------
# meta sniffing (for audit)
# -----------------------
def meta_summary(dash_latest: Dict[str, Any]) -> Dict[str, Any]:
    meta = g(dash_latest, "meta", {})
    summ = g(meta, "summary", {})
    return {
        "stats_as_of_ts": g(meta, "stats_as_of_ts", NA),
        "run_ts_utc": g(meta, "run_ts_utc", NA),
        "ruleset_id": g(meta, "ruleset_id", NA),
        "script_fingerprint": g(meta, "script_fingerprint", NA),
        "script_version": g(meta, "script_version", NA),
        "series_count": g(meta, "series_count", NA),
        "summary": summ if isinstance(summ, dict) else {},
    }

def warn_if_schema_drift(lines: List[str], m_meta: Dict[str, Any], f_meta: Dict[str, Any]) -> None:
    # Simple audit warnings
    if m_meta.get("ruleset_id") not in (NA, None) and f_meta.get("ruleset_id") not in (NA, None):
        if fmt(m_meta.get("ruleset_id")) != fmt(f_meta.get("ruleset_id")):
            lines.append(f"- WARNING: ruleset_id mismatch (market={fmt(m_meta.get('ruleset_id'))}, fred={fmt(f_meta.get('ruleset_id'))})")
    if m_meta.get("script_fingerprint") not in (NA, None) and f_meta.get("script_fingerprint") not in (NA, None):
        if fmt(m_meta.get("script_fingerprint")) != fmt(f_meta.get("script_fingerprint")):
            lines.append(f"- WARNING: script_fingerprint mismatch (market={fmt(m_meta.get('script_fingerprint'))}, fred={fmt(f_meta.get('script_fingerprint'))})")

# -----------------------
# normalize per-row fields (key variants)
# -----------------------
def norm_row_value(r: Dict[str, Any], key_variants: List[str]) -> Any:
    return get_any(r, key_variants, None)

def norm_zdelta(r: Dict[str, Any]) -> Any:
    return norm_row_value(r, ["z_delta60", "z_delta_60", "zΔ60", "zDelta60"])

def norm_pdelta(r: Dict[str, Any]) -> Any:
    return norm_row_value(r, ["p_delta60", "p_delta_60", "pΔ60", "pDelta60"])

def norm_ret1(r: Dict[str, Any]) -> Any:
    return norm_row_value(r, ["ret1_pct60", "ret1_pct", "ret1%", "ret1_pct_60", "ret1Pct60"])

# -----------------------
# resonance matrix (strict intersection only)
# -----------------------
def build_resonance(mrows: List[Dict[str, Any]], frows: List[Dict[str, Any]]) -> List[List[Any]]:
    # strict: same series name
    fmap = {str(g(r, "series", "")): r for r in frows if isinstance(r, dict)}
    out: List[List[Any]] = []
    for mr in mrows:
        s = str(g(mr, "series", ""))
        if not s or s not in fmap:
            continue
        fr = fmap[s]
        out.append([
            s,
            g(mr, "signal_level"),
            g(fr, "signal_level"),
            g(mr, "reason"),
            g(fr, "reason"),
            g(mr, "data_date"),
            g(fr, "data_date"),
            g(mr, "source_url"),
            g(fr, "source_url"),
        ])
    out.sort(key=lambda x: str(x[0]))
    return out

# -----------------------
# render
# -----------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    args = ap.parse_args()

    u = read_json(args.inp)
    modules = g(u, "modules", {})

    def status(name: str) -> str:
        return fmt(safe_path(modules, [name, "status"], NA))

    lines: List[str] = []
    lines.append("# Unified Risk Dashboard Report")
    lines.append("")

    # -----------------------
    # status
    # -----------------------
    lines.append("## Module Status")
    md_kv(lines, "market_cache", status("market_cache"))
    md_kv(lines, "fred_cache", status("fred_cache"))
    md_kv(lines, "taiwan_margin_financing", status("taiwan_margin_financing"))
    md_kv(lines, "unified_generated_at_utc", g(u, "generated_at_utc", NA))
    lines.append("")

    # -----------------------
    # market_cache
    # -----------------------
    m = safe_path(modules, ["market_cache", "dashboard_latest"], None)
    lines.append("## market_cache (detailed)")
    mrows: List[Dict[str, Any]] = []
    m_meta = {"ruleset_id": NA, "script_fingerprint": NA}
    if isinstance(m, dict):
        m_meta = meta_summary(m)
        md_kv(lines, "as_of_ts", m_meta.get("stats_as_of_ts"))
        md_kv(lines, "run_ts_utc", m_meta.get("run_ts_utc"))
        md_kv(lines, "ruleset_id", m_meta.get("ruleset_id"))
        md_kv(lines, "script_fingerprint", m_meta.get("script_fingerprint"))
        md_kv(lines, "script_version", m_meta.get("script_version"))
        md_kv(lines, "series_count", m_meta.get("series_count"))
        lines.append("")

        mrows = extract_market_rows(m)
        headers = [
            "series","signal","dir","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%60",
            "reason","tag","prev","delta","streak_hist","streak_wa","source"
        ]
        table_rows: List[List[Any]] = []
        for r in mrows:
            table_rows.append([
                g(r,"series"),
                g(r,"signal_level"),
                g(r,"dir"),
                g(r,"value"),
                g(r,"data_date"),
                g(r,"age_hours"),
                g(r,"z60"),
                g(r,"p60"),
                g(r,"p252"),
                norm_zdelta(r),
                norm_pdelta(r),
                norm_ret1(r),
                g(r,"reason"),
                g(r,"tag"),
                g(r,"prev_signal"),
                g(r,"delta_signal"),
                g(r,"streak_hist"),
                g(r,"streak_wa"),
                g(r,"source_url"),
            ])
        md_table(lines, headers, table_rows)
        lines.append("")
    else:
        lines.append("- NA (missing/failed)")
        lines.append("")

    # -----------------------
    # fred_cache
    # -----------------------
    f = safe_path(modules, ["fred_cache", "dashboard_latest"], None)
    lines.append("## fred_cache (ALERT+WATCH+INFO)")  # <- 修正標題
    frows: List[Dict[str, Any]] = []
    f_meta = {"ruleset_id": NA, "script_fingerprint": NA}
    if isinstance(f, dict):
        f_meta = meta_summary(f)
        summ = f_meta.get("summary", {})
        md_kv(lines, "as_of_ts", f_meta.get("stats_as_of_ts"))
        md_kv(lines, "run_ts_utc", f_meta.get("run_ts_utc"))
        md_kv(lines, "ruleset_id", f_meta.get("ruleset_id"))
        md_kv(lines, "script_fingerprint", f_meta.get("script_fingerprint"))
        md_kv(lines, "script_version", f_meta.get("script_version"))
        if isinstance(summ, dict):
            md_kv(lines, "ALERT", summ.get("ALERT"))
            md_kv(lines, "WATCH", summ.get("WATCH"))
            md_kv(lines, "INFO", summ.get("INFO"))
            md_kv(lines, "NONE", summ.get("NONE"))
            md_kv(lines, "CHANGED", summ.get("CHANGED"))
        lines.append("")

        frows = extract_fred_rows(f)
        focus = pick_rows(frows, ("ALERT","WATCH","INFO"))
        headers = [
            "series","signal","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%",
            "reason","tag","prev","delta","source"
        ]
        table_rows = []
        for r in focus:
            table_rows.append([
                g(r,"series"),
                g(r,"signal_level"),
                g(r,"value"),
                g(r,"data_date"),
                g(r,"age_hours"),
                g(r,"z60"),
                g(r,"p60"),
                g(r,"p252"),
                norm_zdelta(r),
                norm_pdelta(r),
                norm_ret1(r),
                g(r,"reason"),
                g(r,"tag"),
                g(r,"prev_signal"),
                g(r,"delta_signal"),
                g(r,"source_url"),
            ])
        md_table(lines, headers, table_rows)
        lines.append("")
    else:
        lines.append("- NA (missing/failed)")
        lines.append("")

    # -----------------------
    # audit warnings (ruleset/script mismatch)
    # -----------------------
    lines.append("## Audit Notes")
    warn_if_schema_drift(lines, m_meta, f_meta)
    lines.append("")

    # -----------------------
    # resonance matrix (strict intersection)
    # -----------------------
    lines.append("## Resonance Matrix (strict: same series)")
    rrows = build_resonance(mrows, frows)
    if rrows:
        headers = ["series","market_signal","fred_signal","market_reason","fred_reason","market_date","fred_date","market_source","fred_source"]
        md_table(lines, headers, rrows)
    else:
        lines.append("- NA (no strict overlaps)")
    lines.append("")

    # -----------------------
    # taiwan margin
    # -----------------------
    t = safe_path(modules, ["taiwan_margin_financing", "latest"], None)
    lines.append("## taiwan_margin_financing (TWSE/TPEX)")
    if isinstance(t, dict):
        twse = margin_stats(t, "TWSE")
        tpex = margin_stats(t, "TPEX")

        for name, blk in [("TWSE", twse), ("TPEX", tpex)]:
            lines.append(f"### {name} (data_date={fmt(blk['data_date'])})")
            md_kv(lines, "source_url", blk["source_url"])
            if blk["latest"]:
                md_kv(lines, "latest.date", blk["latest"].get("date"))
                md_kv(lines, "latest.balance_yi", blk["latest"].get("balance_yi"))
                md_kv(lines, "latest.chg_yi", blk["latest"].get("chg_yi"))
            md_kv(lines, f"sum_chg_yi_last{blk['n_used']}", blk["sum_last5"])
            md_kv(lines, f"avg_chg_yi_last{blk['n_used']}", blk["avg_last5"])
            md_kv(lines, f"pos_days_last{blk['n_used']}", blk["pos_days_last5"])
            md_kv(lines, f"neg_days_last{blk['n_used']}", blk["neg_days_last5"])
            md_kv(lines, f"max_chg_last{blk['n_used']}", blk["max_chg_last5"])
            md_kv(lines, f"min_chg_last{blk['n_used']}", blk["min_chg_last5"])
            lines.append("")
    else:
        lines.append("- NA (missing/failed)")
        lines.append("")

    outp = Path(args.outp)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    main()