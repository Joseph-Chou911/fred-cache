#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

NA = "NA"

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

def md_kv(lines: List[str], k: str, v: Any) -> None:
    lines.append(f"- {k}: {fmt(v)}")

def md_table(lines: List[str], headers: List[str], rows: List[List[Any]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(fmt(x) for x in r) + " |")

def split_csvish(s: Any) -> List[str]:
    if not isinstance(s, str) or not s.strip() or s.strip() == NA:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]

# -----------------------
# extraction
# -----------------------
def extract_rows(latest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = g(latest, "rows", [])
    return rows if isinstance(rows, list) else []

def rank_signal(level: str) -> int:
    order = {"ALERT": 4, "WATCH": 3, "INFO": 2, "NONE": 1}
    return order.get(level or "", 0)

def pick_rows(rows: List[Dict[str, Any]], allowed_levels: Tuple[str, ...]) -> List[Dict[str, Any]]:
    out = [r for r in rows if g(r, "signal_level") in allowed_levels]
    out.sort(key=lambda r: (-rank_signal(g(r, "signal_level", "")), str(g(r, "series", ""))))
    return out

# -----------------------
# fred_dir mapping (audit-table)
# -----------------------
FRED_DIR_MAP: Dict[str, str] = {
    "VIXCLS": "HIGH",
    "DGS10": "HIGH",
    "DGS2": "HIGH",
    "T10Y2Y": "HIGH",
    "T10Y3M": "HIGH",
    "STLFSI4": "HIGH",
    "OFR_FSI": "HIGH",
    "BAMLH0A0HYM2": "HIGH",
    "DTWEXBGS": "HIGH",
    "SP500": "HIGH",
    "DJIA": "HIGH",
    "NASDAQCOM": "HIGH",
    "DCOILWTICO": "HIGH",
    "NFCINONFINLEVERAGE": "LOW",
}

def derive_fred_dir(series: Any) -> str:
    s = str(series or "").strip()
    if not s:
        return NA
    return FRED_DIR_MAP.get(s, NA)

# -----------------------
# class from tag (deterministic)
# -----------------------
def classify_row(tag: Any, reason: Any) -> str:
    tags = set(split_csvish(tag))
    is_long = "LONG_EXTREME" in tags
    is_level = "EXTREME_Z" in tags
    is_jump = any(t.startswith("JUMP") for t in tags) or ("JUMP_DELTA" in tags) or ("JUMP_RET" in tags)

    parts: List[str] = []
    if is_long:
        parts.append("LONG")
    if is_level:
        parts.append("LEVEL")
    if is_jump:
        parts.append("JUMP")
    return "+".join(parts) if parts else "NONE"

ALIASES: List[Tuple[str, str, str]] = [
    ("VIX", "VIXCLS", "VIX↔VIXCLS"),
]

def resonance_level(market_signal: str, fred_signal: str, market_class: str, fred_class: str) -> str:
    ms = market_signal or NA
    fs = fred_signal or NA
    mc = market_class or "NONE"
    fc = fred_class or "NONE"

    structural = {"LONG", "LEVEL"}
    shock = {"JUMP"}

    mc_set = set(mc.split("+")) if mc and mc != "NONE" else set()
    fc_set = set(fc.split("+")) if fc and fc != "NONE" else set()

    mc_is_struct = bool(mc_set & structural)
    fc_is_struct = bool(fc_set & structural)
    mc_is_shock = bool(mc_set & shock)
    fc_is_shock = bool(fc_set & shock)

    if (mc_is_struct and fc_is_shock) or (mc_is_shock and fc_is_struct):
        return "STRUCTURAL_VS_SHOCK"

    if ms == fs and ms != NA:
        return "CONCORD_STRONG" if mc == fc else "CONCORD_WEAK"

    if ms != fs and ms != NA and fs != NA:
        return "DISCORD_LEVEL" if mc == fc else "DISCORD_MIXED"

    return "DISCORD_MIXED"

def series_key(series: Any) -> str:
    return str(series or "").strip()

def build_resonance_pairs(market_rows: List[Dict[str, Any]], fred_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    m_by = {series_key(g(r, "series")): r for r in market_rows if series_key(g(r, "series"))}
    f_by = {series_key(g(r, "series")): r for r in fred_rows if series_key(g(r, "series"))}

    out: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()

    # STRICT
    for s in sorted(set(m_by.keys()) & set(f_by.keys())):
        mr, fr = m_by[s], f_by[s]

        m_sig = g(mr, "signal_level", NA)
        f_sig = g(fr, "signal_level", NA)

        m_tag = g(mr, "tag", NA)
        f_tag = g(fr, "tag", NA)

        m_reason = g(mr, "reason", NA)
        f_reason = g(fr, "reason", NA)

        m_dir = g(mr, "dir", NA)
        f_dir = derive_fred_dir(s)

        m_class = classify_row(m_tag, m_reason)
        f_class = classify_row(f_tag, f_reason)

        row = {
            "pair_type": "STRICT",
            "series": s,
            "market_series": s,
            "fred_series": s,
            "market_signal": m_sig,
            "fred_signal": f_sig,
            "market_class": m_class,
            "fred_class": f_class,
            "market_tag": m_tag,
            "fred_tag": f_tag,
            "market_dir": m_dir,
            "fred_dir": f_dir,
            "market_reason": m_reason,
            "fred_reason": f_reason,
            "market_date": g(mr, "data_date", NA),
            "fred_date": g(fr, "data_date", NA),
            "market_source": g(mr, "source_url", NA),
            "fred_source": g(fr, "source_url", NA),
        }
        row["resonance_level"] = resonance_level(m_sig, f_sig, m_class, f_class)

        key = ("STRICT", s, s)
        if key not in seen:
            out.append(row)
            seen.add(key)

    # ALIAS
    for m_name, f_name, label in ALIASES:
        ms, fs = series_key(m_name), series_key(f_name)
        if not ms or not fs:
            continue
        if ms not in m_by or fs not in f_by:
            continue

        mr, fr = m_by[ms], f_by[fs]

        m_sig = g(mr, "signal_level", NA)
        f_sig = g(fr, "signal_level", NA)

        m_tag = g(mr, "tag", NA)
        f_tag = g(fr, "tag", NA)

        m_reason = g(mr, "reason", NA)
        f_reason = g(fr, "reason", NA)

        m_dir = g(mr, "dir", NA)
        f_dir = derive_fred_dir(fs)

        m_class = classify_row(m_tag, m_reason)
        f_class = classify_row(f_tag, f_reason)

        row = {
            "pair_type": "ALIAS",
            "series": label,
            "market_series": ms,
            "fred_series": fs,
            "market_signal": m_sig,
            "fred_signal": f_sig,
            "market_class": m_class,
            "fred_class": f_class,
            "market_tag": m_tag,
            "fred_tag": f_tag,
            "market_dir": m_dir,
            "fred_dir": f_dir,
            "market_reason": m_reason,
            "fred_reason": f_reason,
            "market_date": g(mr, "data_date", NA),
            "fred_date": g(fr, "data_date", NA),
            "market_source": g(mr, "source_url", NA),
            "fred_source": g(fr, "source_url", NA),
        }
        row["resonance_level"] = resonance_level(m_sig, f_sig, m_class, f_class)

        key = ("ALIAS", ms, fs)
        if key not in seen:
            out.append(row)
            seen.add(key)

    order = {
        "CONCORD_STRONG": 1,
        "CONCORD_WEAK": 2,
        "STRUCTURAL_VS_SHOCK": 3,
        "DISCORD_LEVEL": 4,
        "DISCORD_MIXED": 5,
    }
    out.sort(key=lambda r: (order.get(str(r.get("resonance_level")), 99), str(r.get("pair_type")), str(r.get("series"))))
    return out

# -----------------------
# margin stats (renderer side, for TWSE/TPEX block)
# -----------------------
def margin_stats(twm_latest: Dict[str, Any], which: str) -> Dict[str, Any]:
    blk = safe_path(twm_latest, ["series", which], {}) if isinstance(twm_latest, dict) else {}
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
# Unified Risk Judgment (deterministic)
# -----------------------
def count_levels(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    w = sum(1 for r in rows if g(r, "signal_level") == "WATCH")
    a = sum(1 for r in rows if g(r, "signal_level") == "ALERT")
    return w, a

def derive_unified_state(m_has: bool, f_has: bool, r_heated: Any) -> str:
    r = True if str(r_heated).lower() == "true" else False if str(r_heated).lower() == "false" else None
    if m_has and f_has:
        return "RESONANCE_MFR" if r is True else "RESONANCE_MF"
    if m_has and (not f_has):
        return "MARKET_ONLY_HOT" if r is True else "MARKET_ONLY"
    if (not m_has) and f_has:
        return "FRED_ONLY_HOT" if r is True else "FRED_ONLY"
    return "ROLL25_ONLY" if r is True else "QUIET"

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

    lines.append("## Module Status")
    md_kv(lines, "market_cache", status("market_cache"))
    md_kv(lines, "fred_cache", status("fred_cache"))
    md_kv(lines, "roll25_cache", status("roll25_cache"))
    md_kv(lines, "taiwan_margin_financing", status("taiwan_margin_financing"))
    md_kv(lines, "unified_generated_at_utc", g(u, "generated_at_utc", NA))
    lines.append("")

    # -----------------------
    # market_cache (detailed)
    # -----------------------
    m = safe_path(modules, ["market_cache", "dashboard_latest"], None)
    lines.append("## market_cache (detailed)")
    market_rows: List[Dict[str, Any]] = []
    if isinstance(m, dict):
        meta = g(m, "meta", {})
        md_kv(lines, "as_of_ts", g(meta, "stats_as_of_ts", NA))
        md_kv(lines, "run_ts_utc", g(meta, "run_ts_utc", NA))
        md_kv(lines, "ruleset_id", g(meta, "ruleset_id", NA))
        md_kv(lines, "script_fingerprint", g(meta, "script_fingerprint", NA))
        md_kv(lines, "script_version", g(meta, "script_version", NA))
        md_kv(lines, "series_count", g(meta, "series_count", NA))
        lines.append("")

        market_rows = extract_rows(m)
        headers = [
            "series","signal","dir","market_class","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%60",
            "reason","tag","prev","delta","streak_hist","streak_wa","source"
        ]
        table_rows: List[List[Any]] = []
        for r in market_rows:
            m_class = classify_row(g(r, "tag", NA), g(r, "reason", NA))
            table_rows.append([
                g(r,"series"),
                g(r,"signal_level"),
                g(r,"dir"),
                m_class,
                g(r,"value"),
                g(r,"data_date"),
                g(r,"age_hours"),
                g(r,"z60"),
                g(r,"p60"),
                g(r,"p252"),
                g(r,"z_delta60"),
                g(r,"p_delta60"),
                g(r,"ret1_pct60"),
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
        lines.append(f"- {NA} (missing/failed)")
        lines.append("")

    # -----------------------
    # fred_cache (ALERT+WATCH+INFO)
    # -----------------------
    f = safe_path(modules, ["fred_cache", "dashboard_latest"], None)
    lines.append("## fred_cache (ALERT+WATCH+INFO)")
    fred_rows: List[Dict[str, Any]] = []
    if isinstance(f, dict):
        meta = g(f, "meta", {})
        summ = g(meta, "summary", {})
        md_kv(lines, "as_of_ts", g(meta, "stats_as_of_ts", NA))
        md_kv(lines, "run_ts_utc", g(meta, "run_ts_utc", NA))
        md_kv(lines, "ruleset_id", g(meta, "ruleset_id", NA))
        md_kv(lines, "script_fingerprint", g(meta, "script_fingerprint", NA))
        md_kv(lines, "script_version", g(meta, "script_version", NA))
        if isinstance(summ, dict):
            md_kv(lines, "ALERT", summ.get("ALERT"))
            md_kv(lines, "WATCH", summ.get("WATCH"))
            md_kv(lines, "INFO", summ.get("INFO"))
            md_kv(lines, "NONE", summ.get("NONE"))
            md_kv(lines, "CHANGED", summ.get("CHANGED"))
        lines.append("")

        fred_rows = extract_rows(f)
        focus = pick_rows(fred_rows, ("WATCH", "INFO", "ALERT"))

        headers = [
            "series","signal","fred_dir","fred_class","value","data_date","age_h",
            "z60","p60","p252","zΔ60","pΔ60","ret1%",
            "reason","tag","prev","delta","source"
        ]
        table_rows = []
        for r in focus:
            s = g(r, "series", NA)
            f_dir = derive_fred_dir(s)
            f_class = classify_row(g(r, "tag", NA), g(r, "reason", NA))
            table_rows.append([
                s,
                g(r,"signal_level"),
                f_dir,
                f_class,
                g(r,"value"),
                g(r,"data_date"),
                g(r,"age_hours"),
                g(r,"z60"),
                g(r,"p60"),
                g(r,"p252"),
                g(r,"z_delta_60"),
                g(r,"p_delta_60"),
                g(r,"ret1_pct"),
                g(r,"reason"),
                g(r,"tag"),
                g(r,"prev_signal"),
                g(r,"delta_signal"),
                g(r,"source_url"),
            ])
        md_table(lines, headers, table_rows)
        lines.append("")
    else:
        lines.append(f"- {NA} (missing/failed)")
        lines.append("")

    # -----------------------
    # Audit Notes
    # -----------------------
    lines.append("## Audit Notes")
    lines.append(f"- fred_dir is DERIVED (heuristic) from a fixed mapping table in this script (FRED_DIR_MAP). Unmapped series => {NA}.")
    lines.append(
        "- market_class/fred_class are DERIVED from tag only (deterministic): "
        "LONG if tag contains LONG_EXTREME; "
        "LEVEL if tag contains EXTREME_Z; "
        "JUMP if tag contains JUMP* (incl. JUMP_DELTA/JUMP_RET); "
        "otherwise NONE."
    )
    lines.append("- roll25_heated/roll25_confidence are COMPUTED in build_unified_dashboard_latest.py from roll25 JSON only; renderer does not recompute.")
    lines.append("")

    # -----------------------
    # Resonance Matrix
    # -----------------------
    resonance = build_resonance_pairs(market_rows, fred_rows)
    lines.append("## Resonance Matrix (strict + alias)")
    if resonance:
        headers = [
            "resonance_level","pair_type","series",
            "market_series","fred_series",
            "market_signal","fred_signal",
            "market_class","fred_class",
            "market_tag","fred_tag",
            "market_dir","fred_dir",
            "market_reason","fred_reason",
            "market_date","fred_date",
            "market_source","fred_source"
        ]
        rows2: List[List[Any]] = []
        for r in resonance:
            rows2.append([
                r.get("resonance_level", NA),
                r.get("pair_type", NA),
                r.get("series", NA),
                r.get("market_series", NA),
                r.get("fred_series", NA),
                r.get("market_signal", NA),
                r.get("fred_signal", NA),
                r.get("market_class", NA),
                r.get("fred_class", NA),
                r.get("market_tag", NA),
                r.get("fred_tag", NA),
                r.get("market_dir", NA),
                r.get("fred_dir", NA),
                r.get("market_reason", NA),
                r.get("fred_reason", NA),
                r.get("market_date", NA),
                r.get("fred_date", NA),
                r.get("market_source", NA),
                r.get("fred_source", NA),
            ])
        md_table(lines, headers, rows2)
        lines.append("")
    else:
        lines.append(f"- {NA} (no overlapping/alias pairs)")
        lines.append("")

    # -----------------------
    # roll25_cache block
    # -----------------------
    rcore = safe_path(modules, ["roll25_cache", "core"], None)
    lines.append("## roll25_cache (TW turnover)")
    if isinstance(rcore, dict):
        md_kv(lines, "status", status("roll25_cache"))
        for k in [
            "UsedDate","tag","risk_level",
            "turnover_twd","turnover_unit",
            "volume_multiplier","vol_multiplier","amplitude_pct","pct_change","close",
            "LookbackNTarget","LookbackNActual",
        ]:
            md_kv(lines, k, g(rcore, k, NA))

        sigs = g(rcore, "signals", {})
        if isinstance(sigs, dict):
            md_kv(lines, "signals.DownDay", sigs.get("DownDay"))
            md_kv(lines, "signals.VolumeAmplified", sigs.get("VolumeAmplified"))
            md_kv(lines, "signals.VolAmplified", sigs.get("VolAmplified"))
            md_kv(lines, "signals.NewLow_N", sigs.get("NewLow_N"))
            md_kv(lines, "signals.ConsecutiveBreak", sigs.get("ConsecutiveBreak"))
            md_kv(lines, "signals.OhlcMissing", sigs.get("OhlcMissing"))
        lines.append("")

        # roll25_heated/confidence/consistency/margin_signal (from build)
        cross = safe_path(modules, ["taiwan_margin_financing", "cross_module"], {})
        lines.append("### roll25_heated / confidence (from build)")
        md_kv(lines, "roll25_heated", g(cross, "roll25_heated", NA))
        md_kv(lines, "roll25_confidence", g(cross, "roll25_confidence", NA))
        md_kv(lines, "consistency(Margin×Roll25)", g(cross, "consistency", NA))
        md_kv(lines, "margin_signal", g(cross, "margin_signal", NA))
        md_kv(lines, "margin_signal_source", g(cross, "margin_signal_source", NA))
        lines.append("")
    else:
        lines.append(f"- {NA} (missing/failed)")
        lines.append("")

    # -----------------------
    # Unified Risk Judgment (Market + FRED + Roll25)
    # -----------------------
    lines.append("## Unified Risk Judgment (Market + FRED + Roll25)")
    m_w, m_a = count_levels(market_rows)
    f_w, f_a = count_levels(fred_rows)
    cross = safe_path(modules, ["taiwan_margin_financing", "cross_module"], {})
    roll25_heated = g(cross, "roll25_heated", NA)
    roll25_conf = g(cross, "roll25_confidence", NA)

    m_has = (m_w + m_a) > 0
    f_has = (f_w + f_a) > 0
    ustate = derive_unified_state(m_has, f_has, roll25_heated)

    md_kv(lines, "market_WATCH", m_w)
    md_kv(lines, "market_ALERT", m_a)
    md_kv(lines, "fred_WATCH", f_w)
    md_kv(lines, "fred_ALERT", f_a)
    md_kv(lines, "roll25_heated", roll25_heated)
    md_kv(lines, "roll25_confidence", roll25_conf)
    md_kv(lines, "UnifiedState", ustate)
    lines.append("")
    lines.append("- Rule: UnifiedState is derived deterministically from (market has WATCH/ALERT?, fred has WATCH/ALERT?, roll25_heated). No forecast inference.")
    lines.append("")

    # -----------------------
    # taiwan margin block
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
        lines.append(f"- {NA} (missing/failed)")
        lines.append("")

    outp = Path(args.outp)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    main()