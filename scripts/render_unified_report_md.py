#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
scripts/render_unified_report_md.py

修正重點（audit-first）：
1) 修正 class 判讀：
   - 新增 LEVEL（由 EXTREME_Z tag 決定）
   - JUMP 只由 tag 決定（JUMP* / JUMP_DELTA / JUMP_RET），不再用 reason 內的 "abs(" 亂判
   - LONG 由 LONG_EXTREME tag 決定
   - 複合型：若同時命中 LONG + JUMP（或 LONG + LEVEL / JUMP + LEVEL 等）則用 "+" 串接（例如 LONG+JUMP）
2) 修正 resonance_level：
   - STRUCTURAL_VS_SHOCK：structural={LONG,LEVEL} vs shock={JUMP} 的交叉
   - 其他維持一致性規則
3) Audit Notes 文字同步更新（與實作一致）

你原先要求「2、3都要」：
- (2) fred_dir：維持固定 mapping table（不從數值推論）
- (3) market_class / fred_class：在 market 表、fred 表、共振矩陣都一致出現
"""

from __future__ import annotations

import argparse
import json
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
# extraction
# -----------------------
def extract_market_rows(market_latest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = g(market_latest, "rows", [])
    return rows if isinstance(rows, list) else []

def extract_fred_rows(fred_latest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = g(fred_latest, "rows", [])
    return rows if isinstance(rows, list) else []

def rank_signal(level: str) -> int:
    order = {"ALERT": 4, "WATCH": 3, "INFO": 2, "NONE": 1}
    return order.get(level or "", 0)

def pick_rows(rows: List[Dict[str, Any]], allowed_levels: Tuple[str, ...]) -> List[Dict[str, Any]]:
    out = [r for r in rows if g(r, "signal_level") in allowed_levels]
    out.sort(key=lambda r: (-rank_signal(g(r, "signal_level", "")), str(g(r, "series", ""))))
    return out

# -----------------------
# (2) fred_dir mapping (audit-table)
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
# (3) class from tag (deterministic; audit-safe)
# -----------------------
def classify_row(tag: Any, reason: Any) -> str:
    """
    class definitions (deterministic):
      - LONG  : tag contains LONG_EXTREME
      - JUMP  : tag contains any JUMP* OR tag in {JUMP_DELTA, JUMP_RET}
      - LEVEL : tag contains EXTREME_Z
      - Composite: join by '+' in stable order (LONG, LEVEL, JUMP)
      - NONE  : otherwise

    NOTE: do NOT use `reason` substring "abs(" as a jump detector; abs(Z60)>=2 is LEVEL.
    `reason` is kept only for compatibility in signature.
    """
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

# -----------------------
# alias mapping
# -----------------------
ALIASES: List[Tuple[str, str, str]] = [
    ("VIX", "VIXCLS", "VIX↔VIXCLS"),
]

# -----------------------
# resonance
# -----------------------
def resonance_level(market_signal: str, fred_signal: str, market_class: str, fred_class: str) -> str:
    ms = market_signal or NA
    fs = fred_signal or NA
    mc = market_class or "NONE"
    fc = fred_class or "NONE"

    structural = {"LONG", "LEVEL"}
    shock = {"JUMP"}

    # composite support: treat "LONG+JUMP" etc. as set membership
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
        if ms == fs and ("STRICT", ms, fs) in seen:
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

    # sort by resonance importance
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

    lines.append("## Module Status")
    md_kv(lines, "market_cache", status("market_cache"))
    md_kv(lines, "fred_cache", status("fred_cache"))
    md_kv(lines, "taiwan_margin_financing", status("taiwan_margin_financing"))
    md_kv(lines, "unified_generated_at_utc", g(u, "generated_at_utc", NA))
    lines.append("")

    # -----------------------
    # market_cache (detailed)  -> add market_class
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

        market_rows = extract_market_rows(m)

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
    # fred_cache (ALERT+WATCH+INFO) -> add fred_dir + fred_class
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

        fred_rows = extract_fred_rows(f)
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
        rows: List[List[Any]] = []
        for r in resonance:
            rows.append([
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
        md_table(lines, headers, rows)
        lines.append("")
    else:
        lines.append(f"- {NA} (no overlapping/alias pairs)")
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
        lines.append(f"- {NA} (missing/failed)")
        lines.append("")

    outp = Path(args.outp)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    main()