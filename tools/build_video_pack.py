#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_video_pack.py

Build an "episode pack" for video/script production by combining:
- roll25_cache/stats_latest.json
- taiwan_margin_cache/latest.json
- tw0050_bb_cache/stats_latest.json

Outputs:
- episode_pack.json (audit-first, includes raw inputs)
- episode_data.md   (data-only brief for later human/LLM narration)
- episode_outline.md (compat; in data mode it's same as episode_data.md)

Design goal:
- The Python script outputs ONLY auditable facts + deterministic computed flags.
- Narration / investment advice is produced later (you paste MD back to ChatGPT for polishing).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "episode_pack_schema_v1"
BUILD_FINGERPRINT = "build_video_pack@v1.2.data_only_flags_more_extracts"


# ---------------------------
# Basic helpers
# ---------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, obj: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def parse_ymd(x: Any) -> Optional[date]:
    """Accept YYYY-MM-DD (optionally with time), YYYYMMDD, int YYYYMMDD."""
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x

    if isinstance(x, int):
        s = str(x)
    else:
        s = str(x).strip()

    # YYYY-MM-DD...
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return None

    # YYYYMMDD
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.strptime(s, "%Y%m%d").date()
        except Exception:
            return None

    return None


def deep_get(obj: Any, path: str) -> Any:
    """
    Get nested value by dotted path. Supports list index by numeric token.
    Example: "series.TWSE.rows.0.date"
    """
    cur = obj
    for token in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(token)
        elif isinstance(cur, list):
            if token.isdigit():
                idx = int(token)
                if 0 <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            else:
                return None
        else:
            return None
    return cur


def pick_first(obj: Dict[str, Any], paths: List[str]) -> Tuple[Any, Optional[str]]:
    for p in paths:
        v = deep_get(obj, p)
        if v is not None:
            return v, p
    return None, None


def compute_age_days(day_key_local: str, as_of: Optional[date]) -> Optional[int]:
    d0 = parse_ymd(day_key_local)
    if d0 is None or as_of is None:
        return None
    return (d0 - as_of).days


def to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def fmt_num(x: Any, nd: int = 2) -> str:
    v = to_float(x)
    if v is None:
        return "N/A"
    return f"{v:.{nd}f}"


def fmt_int(x: Any) -> str:
    try:
        if x is None:
            return "N/A"
        return str(int(x))
    except Exception:
        return "N/A"


def fmt_bool(x: Any) -> str:
    if x is True:
        return "true"
    if x is False:
        return "false"
    return "N/A"


def uniq_keep_order(xs: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


@dataclass
class Extract:
    field: str
    value: Any
    picked_from: List[str]
    picked_path: Optional[str]


def add_extract(extracts: List[Dict[str, Any]], field: str, obj: Dict[str, Any], paths: List[str]) -> None:
    v, p = pick_first(obj, paths)
    if v is None:
        return
    extracts.append({
        "field": field,
        "value": v,
        "picked_from": paths,   # candidate list
        "picked_path": p,       # actual selected path
    })


# ---------------------------
# Computed flags (deterministic)
# ---------------------------

def flag_ge(x: Any, thr: float) -> Optional[bool]:
    v = to_float(x)
    if v is None:
        return None
    return v >= thr


def flag_le(x: Any, thr: float) -> Optional[bool]:
    v = to_float(x)
    if v is None:
        return None
    return v <= thr


def safe_max(xs: List[Optional[float]]) -> Optional[float]:
    ys = [x for x in xs if isinstance(x, (int, float))]
    return max(ys) if ys else None


def safe_sum(xs: List[Optional[float]]) -> Optional[float]:
    ys = [x for x in xs if isinstance(x, (int, float))]
    return sum(ys) if ys else None


def margin_series_rows(m: Dict[str, Any], market: str) -> List[Dict[str, Any]]:
    rows = deep_get(m, f"series.{market}.rows")
    return rows if isinstance(rows, list) else []


def margin_latest(m: Dict[str, Any], market: str) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    rows = margin_series_rows(m, market)
    if not rows:
        return None, None, None
    d = rows[0].get("date")
    bal = to_float(rows[0].get("balance_yi"))
    chg = to_float(rows[0].get("chg_yi"))
    return d, bal, chg


def margin_sum_chg(m: Dict[str, Any], market: str, n: int) -> Optional[float]:
    rows = margin_series_rows(m, market)[:n]
    chgs = [to_float(r.get("chg_yi")) for r in rows]
    return safe_sum(chgs)


def margin_is_30row_high(m: Dict[str, Any], market: str) -> Optional[bool]:
    rows = margin_series_rows(m, market)
    if not rows:
        return None
    bals = [to_float(r.get("balance_yi")) for r in rows]
    cur = bals[0]
    mx = safe_max(bals)
    if cur is None or mx is None:
        return None
    return cur >= mx


def tranche_levels_compact(tw: Dict[str, Any]) -> List[Dict[str, Any]]:
    levels = deep_get(tw, "pledge.unconditional_tranche_levels.levels")
    if not isinstance(levels, list):
        return []
    out = []
    for it in levels:
        if not isinstance(it, dict):
            continue
        out.append({
            "label": it.get("label"),
            "price_level": it.get("price_level"),
            "drawdown": it.get("drawdown"),
        })
    return out


# ---------------------------
# Data-only Markdown report
# ---------------------------

def build_md_data(pack: Dict[str, Any]) -> str:
    tz = pack.get("timezone", "Asia/Taipei")
    day = pack.get("day_key_local", "N/A")
    warnings = pack.get("warnings", [])
    inp = pack.get("inputs", {})
    ext = pack.get("extracts_best_effort", {})
    flags = pack.get("computed_flags", {})

    def w(s: str) -> str:
        return s + "\n"

    out = ""
    out += w("# 投資日記 Data Brief（roll25 + taiwan margin + tw0050_bb）")
    out += w("")
    out += w(f"- day_key_local: {day} ({tz})")
    out += w(f"- generated_at_local: {pack.get('generated_at_local', 'N/A')}")
    out += w(f"- generated_at_utc: {pack.get('generated_at_utc', 'N/A')}")
    out += w(f"- build_fingerprint: {pack.get('build_fingerprint', 'N/A')}")
    out += w(f"- warnings: {', '.join(warnings) if warnings else 'NONE'}")
    out += w("")

    out += w("## 0) Quick facts (for narration later)")
    # Assemble a compact line of the highest-signal numbers (still data-only)
    roll = {e["field"]: e["value"] for e in ext.get("roll25", [])}
    mar = {e["field"]: e["value"] for e in ext.get("margin", [])}
    tw = {e["field"]: e["value"] for e in ext.get("tw0050_bb", [])}

    tv60z = roll.get("trade_value_win60_z")
    tv60p = roll.get("trade_value_win60_p")
    tv252z = roll.get("trade_value_win252_z")
    tv252p = roll.get("trade_value_win252_p")

    out += w(f"- roll25 trade_value heat: 60d z={fmt_num(tv60z,3)} p={fmt_num(tv60p,3)} | 252d z={fmt_num(tv252z,3)} p={fmt_num(tv252p,3)}")
    out += w(f"- margin latest: TWSE bal_yi={fmt_num(mar.get('twse_balance_yi'),1)} chg_yi={fmt_num(mar.get('twse_chg_yi'),1)} | TPEX bal_yi={fmt_num(mar.get('tpex_balance_yi'),1)} chg_yi={fmt_num(mar.get('tpex_chg_yi'),1)}")
    out += w(f"- 0050 latest: state={tw.get('bb_state','N/A')} bb_z={fmt_num(tw.get('bb_z'),3)} price={fmt_num(tw.get('adjclose'),2)} regime_allowed={fmt_bool(tw.get('regime_allowed'))} pledge_action={tw.get('pledge_action_bucket','N/A')}")
    out += w("")

    # roll25 section
    r = inp.get("roll25", {})
    out += w("## 1) roll25 (TWSE Turnover / Heat)")
    out += w(f"- path: {r.get('path','N/A')}")
    out += w(f"- as_of_date: {r.get('as_of_date','N/A')} | age_days: {r.get('age_days','N/A')} | picked_as_of_path: {r.get('picked_as_of_path','N/A')}")
    out += w(f"- fingerprint: {r.get('fingerprint','N/A')}")
    out += w("")
    out += w("### extracts")
    for k in [
        "mode",
        "used_date",
        "trade_value_win60_z", "trade_value_win60_p",
        "trade_value_win252_z", "trade_value_win252_p",
        "close_win252_z", "close_win252_p",
        "pct_change_win60_z", "pct_change_win60_p",
        "amplitude_pct_win60_z", "amplitude_pct_win60_p",
        "vol_multiplier_20", "volume_amplified",
        "new_low_n", "consecutive_down_days",
    ]:
        if k in roll:
            out += w(f"- {k}: {roll[k]}")
    out += w("")
    out += w("### computed_flags (thresholds are explicit)")
    rf = flags.get("roll25", {})
    for k, v in rf.items():
        out += w(f"- {k}: {v}")
    out += w("")

    # margin section
    m = inp.get("taiwan_margin", {})
    out += w("## 2) taiwan_margin (Margin financing)")
    out += w(f"- path: {m.get('path','N/A')}")
    out += w(f"- as_of_date: {m.get('as_of_date','N/A')} | age_days: {m.get('age_days','N/A')} | picked_as_of_path: {m.get('picked_as_of_path','N/A')}")
    out += w(f"- fingerprint: {m.get('fingerprint','N/A')}")
    out += w("")
    out += w("### extracts")
    for k in [
        "twse_data_date", "twse_balance_yi", "twse_chg_yi",
        "tpex_data_date", "tpex_balance_yi", "tpex_chg_yi",
        "total_balance_yi", "total_chg_yi",
        "twse_chg_3d_sum", "tpex_chg_3d_sum", "total_chg_3d_sum",
        "twse_is_30row_high", "tpex_is_30row_high", "total_is_30row_high",
    ]:
        if k in mar:
            out += w(f"- {k}: {mar[k]}")
    out += w("")
    out += w("### computed_flags (thresholds are explicit)")
    mf = flags.get("margin", {})
    for k, v in mf.items():
        out += w(f"- {k}: {v}")
    out += w("")

    # tw0050 section
    t = inp.get("tw0050_bb", {})
    out += w("## 3) tw0050_bb (0050 Bollinger / Trend / Vol / Pledge gate)")
    out += w(f"- path: {t.get('path','N/A')}")
    out += w(f"- as_of_date: {t.get('as_of_date','N/A')} | age_days: {t.get('age_days','N/A')} | picked_as_of_path: {t.get('picked_as_of_path','N/A')}")
    out += w(f"- fingerprint: {t.get('fingerprint','N/A')}")
    dq = t.get("dq_flags", [])
    out += w(f"- dq_flags: {', '.join(dq) if dq else 'NONE'}")
    out += w("")
    out += w("### extracts")
    for k in [
        "last_date",
        "adjclose",
        "bb_state", "bb_z",
        "dist_to_upper_pct", "dist_to_lower_pct",
        "band_width_std_pct", "band_width_geo_pct",
        "trend_state", "price_vs_200ma_pct", "trend_slope_pct",
        "rv_ann", "rv_ann_pctl",
        "regime_allowed",
        "pledge_action_bucket",
        "pledge_veto_reasons",
        "tranche_levels",
    ]:
        if k in tw:
            out += w(f"- {k}: {tw[k]}")
    out += w("")
    out += w("### computed_flags (thresholds are explicit)")
    tf = flags.get("tw0050_bb", {})
    for k, v in tf.items():
        out += w(f"- {k}: {v}")
    out += w("")

    out += w("## 4) Notes")
    out += w("- This MD is data-only. Paste it back to ChatGPT for narration/script polishing.")
    return out


# Optional: keep a narration-ish outline for those who still want it
def build_md_outline_minimal(pack: Dict[str, Any]) -> str:
    # Intentionally minimal and rule-free (still avoids advice)
    tz = pack.get("timezone", "Asia/Taipei")
    day = pack.get("day_key_local", "N/A")
    warnings = pack.get("warnings", [])

    ext = pack.get("extracts_best_effort", {})
    roll = {e["field"]: e["value"] for e in ext.get("roll25", [])}
    mar = {e["field"]: e["value"] for e in ext.get("margin", [])}
    tw = {e["field"]: e["value"] for e in ext.get("tw0050_bb", [])}

    def w(s: str) -> str:
        return s + "\n"

    out = ""
    out += w("# 投資日記 Episode Outline (data-only skeleton)")
    out += w("")
    out += w(f"- day_key_local: {day} ({tz})")
    out += w(f"- warnings: {', '.join(warnings) if warnings else 'NONE'}")
    out += w("")
    out += w("## 今日重點數字")
    out += w(f"- roll25 trade_value 60d z={fmt_num(roll.get('trade_value_win60_z'),3)} p={fmt_num(roll.get('trade_value_win60_p'),3)}")
    out += w(f"- margin TWSE bal={fmt_num(mar.get('twse_balance_yi'),1)} chg={fmt_num(mar.get('twse_chg_yi'),1)}")
    out += w(f"- 0050 state={tw.get('bb_state','N/A')} bb_z={fmt_num(tw.get('bb_z'),3)} price={fmt_num(tw.get('adjclose'),2)}")
    out += w("")
    out += w("## (Paste to ChatGPT) Request")
    out += w("- Please generate a narration script based ONLY on the numbers and flags above, without inventing facts.")
    return out


# ---------------------------
# main
# ---------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tw0050", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--margin", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument(
        "--md_mode",
        choices=["data", "outline", "both"],
        default="data",
        help="data: episode_outline.md == data brief; outline: minimal outline; both: write both variants",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tw = load_json(args.tw0050)
    r25 = load_json(args.roll25)
    m = load_json(args.margin)

    day_key_local = datetime.now().astimezone().date().isoformat()

    # as_of extraction (match current real JSON)
    tw_asof_raw, tw_asof_path = pick_first(tw, ["meta.last_date", "latest.date", "last_date", "date"])
    r25_asof_raw, r25_asof_path = pick_first(r25, ["used_date", "series.trade_value.asof", "series.close.asof", "asof"])
    m_asof_raw, m_asof_path = pick_first(m, ["series.TWSE.data_date", "series.TWSE.rows.0.date", "series.TPEX.data_date"])

    tw_asof = parse_ymd(tw_asof_raw)
    r25_asof = parse_ymd(r25_asof_raw)
    m_asof = parse_ymd(m_asof_raw)

    warnings: List[str] = []
    if tw_asof is None:
        warnings.append("tw0050_as_of_missing")
    if r25_asof is None:
        warnings.append("roll25_as_of_missing")
    if m_asof is None:
        warnings.append("margin_as_of_missing")

    tw_age = compute_age_days(day_key_local, tw_asof)
    r25_age = compute_age_days(day_key_local, r25_asof)
    m_age = compute_age_days(day_key_local, m_asof)

    # staleness rule
    for name, age in [("tw0050", tw_age), ("roll25", r25_age), ("margin", m_age)]:
        if age is not None and age > 2:
            warnings.append(f"{name}_stale_gt2d")

    # date_misaligned: if any as_of differs by >=2 days
    asofs = [d for d in [tw_asof, r25_asof, m_asof] if d is not None]
    if len(asofs) >= 2:
        mx = max(asofs)
        mn = min(asofs)
        if (mx - mn).days >= 2:
            warnings.append("date_misaligned_ge2d")

    # dq flags
    tw_dq_flags = deep_get(tw, "dq.flags") or []
    if not isinstance(tw_dq_flags, list):
        tw_dq_flags = []

    # fingerprints (best-effort)
    tw_fp = deep_get(tw, "meta.script_fingerprint")
    r25_fp = deep_get(r25, "script_fingerprint") or deep_get(r25, "schema_version")
    m_fp = deep_get(m, "schema_version")

    # ---------------------------
    # extracts_best_effort
    # ---------------------------
    extracts_tw: List[Dict[str, Any]] = []
    extracts_r25: List[Dict[str, Any]] = []
    extracts_m: List[Dict[str, Any]] = []

    # roll25
    add_extract(extracts_r25, "mode", r25, ["mode"])
    add_extract(extracts_r25, "used_date", r25, ["used_date"])
    add_extract(extracts_r25, "trade_value_win60_z", r25, ["series.trade_value.win60.z"])
    add_extract(extracts_r25, "trade_value_win60_p", r25, ["series.trade_value.win60.p"])
    add_extract(extracts_r25, "trade_value_win252_z", r25, ["series.trade_value.win252.z"])
    add_extract(extracts_r25, "trade_value_win252_p", r25, ["series.trade_value.win252.p"])

    add_extract(extracts_r25, "close_win252_z", r25, ["series.close.win252.z"])
    add_extract(extracts_r25, "close_win252_p", r25, ["series.close.win252.p"])

    add_extract(extracts_r25, "pct_change_win60_z", r25, ["series.pct_change.win60.z"])
    add_extract(extracts_r25, "pct_change_win60_p", r25, ["series.pct_change.win60.p"])
    add_extract(extracts_r25, "amplitude_pct_win60_z", r25, ["series.amplitude_pct.win60.z"])
    add_extract(extracts_r25, "amplitude_pct_win60_p", r25, ["series.amplitude_pct.win60.p"])

    add_extract(extracts_r25, "vol_multiplier_20", r25, ["derived.vol_multiplier_20"])
    add_extract(extracts_r25, "volume_amplified", r25, ["derived.volume_amplified"])
    add_extract(extracts_r25, "new_low_n", r25, ["derived.new_low_n"])
    add_extract(extracts_r25, "consecutive_down_days", r25, ["derived.consecutive_down_days"])

    # margin: latest + sums + highs
    add_extract(extracts_m, "twse_data_date", m, ["series.TWSE.data_date"])
    add_extract(extracts_m, "twse_balance_yi", m, ["series.TWSE.rows.0.balance_yi"])
    add_extract(extracts_m, "twse_chg_yi", m, ["series.TWSE.rows.0.chg_yi"])
    add_extract(extracts_m, "tpex_data_date", m, ["series.TPEX.data_date"])
    add_extract(extracts_m, "tpex_balance_yi", m, ["series.TPEX.rows.0.balance_yi"])
    add_extract(extracts_m, "tpex_chg_yi", m, ["series.TPEX.rows.0.chg_yi"])

    twse_bal = to_float(deep_get(m, "series.TWSE.rows.0.balance_yi"))
    tpex_bal = to_float(deep_get(m, "series.TPEX.rows.0.balance_yi"))
    twse_chg = to_float(deep_get(m, "series.TWSE.rows.0.chg_yi"))
    tpex_chg = to_float(deep_get(m, "series.TPEX.rows.0.chg_yi"))

    if twse_bal is not None and tpex_bal is not None:
        extracts_m.append({"field": "total_balance_yi", "value": twse_bal + tpex_bal, "picked_from": ["sum(TWSE,TPEX)"], "picked_path": None})
    if twse_chg is not None and tpex_chg is not None:
        extracts_m.append({"field": "total_chg_yi", "value": twse_chg + tpex_chg, "picked_from": ["sum(TWSE,TPEX)"], "picked_path": None})

    twse_3d = margin_sum_chg(m, "TWSE", 3)
    tpex_3d = margin_sum_chg(m, "TPEX", 3)
    if twse_3d is not None:
        extracts_m.append({"field": "twse_chg_3d_sum", "value": twse_3d, "picked_from": ["sum(series.TWSE.rows[:3].chg_yi)"], "picked_path": None})
    if tpex_3d is not None:
        extracts_m.append({"field": "tpex_chg_3d_sum", "value": tpex_3d, "picked_from": ["sum(series.TPEX.rows[:3].chg_yi)"], "picked_path": None})
    if twse_3d is not None and tpex_3d is not None:
        extracts_m.append({"field": "total_chg_3d_sum", "value": twse_3d + tpex_3d, "picked_from": ["sum(TWSE_3d,TPEX_3d)"], "picked_path": None})

    twse_high = margin_is_30row_high(m, "TWSE")
    tpex_high = margin_is_30row_high(m, "TPEX")
    if twse_high is not None:
        extracts_m.append({"field": "twse_is_30row_high", "value": twse_high, "picked_from": ["TWSE latest >= max(last_30)"], "picked_path": None})
    if tpex_high is not None:
        extracts_m.append({"field": "tpex_is_30row_high", "value": tpex_high, "picked_from": ["TPEX latest >= max(last_30)"], "picked_path": None})
    if twse_bal is not None and tpex_bal is not None:
        # total 30-row high check uses per-market rows; best-effort: compare today's total vs max(total per row index) by aligning indexes
        twse_rows = margin_series_rows(m, "TWSE")
        tpex_rows = margin_series_rows(m, "TPEX")
        n = min(len(twse_rows), len(tpex_rows))
        totals = []
        for i in range(n):
            a = to_float(twse_rows[i].get("balance_yi"))
            b = to_float(tpex_rows[i].get("balance_yi"))
            if a is None or b is None:
                totals.append(None)
            else:
                totals.append(a + b)
        cur_total = totals[0] if totals else None
        mx_total = safe_max([t for t in totals if isinstance(t, (int, float))])
        if cur_total is not None and mx_total is not None:
            extracts_m.append({"field": "total_is_30row_high", "value": cur_total >= mx_total, "picked_from": ["(TWSE+TPEX) latest >= max(last_30)"], "picked_path": None})

    # tw0050_bb: price/bb + trend/vol + regime/pledge + tranche levels
    add_extract(extracts_tw, "last_date", tw, ["meta.last_date", "latest.date"])
    add_extract(extracts_tw, "adjclose", tw, ["latest.adjclose", "latest.price_used"])
    add_extract(extracts_tw, "bb_z", tw, ["latest.bb_z"])
    add_extract(extracts_tw, "bb_state", tw, ["latest.state"])

    add_extract(extracts_tw, "dist_to_upper_pct", tw, ["latest.dist_to_upper_pct"])
    add_extract(extracts_tw, "dist_to_lower_pct", tw, ["latest.dist_to_lower_pct"])
    add_extract(extracts_tw, "band_width_std_pct", tw, ["latest.band_width_std_pct"])
    add_extract(extracts_tw, "band_width_geo_pct", tw, ["latest.band_width_geo_pct"])

    add_extract(extracts_tw, "trend_state", tw, ["trend.state"])
    add_extract(extracts_tw, "price_vs_200ma_pct", tw, ["trend.price_vs_trend_ma_pct"])
    add_extract(extracts_tw, "trend_slope_pct", tw, ["trend.trend_slope_pct"])

    add_extract(extracts_tw, "rv_ann", tw, ["vol.rv_ann"])
    add_extract(extracts_tw, "rv_ann_pctl", tw, ["vol.rv_ann_pctl"])

    add_extract(extracts_tw, "regime_allowed", tw, ["regime.allowed"])
    add_extract(extracts_tw, "pledge_action_bucket", tw, ["pledge.decision.action_bucket"])
    add_extract(extracts_tw, "pledge_veto_reasons", tw, ["pledge.decision.veto_reasons"])

    # tranche levels (compact)
    levels = tranche_levels_compact(tw)
    if levels:
        extracts_tw.append({"field": "tranche_levels", "value": levels, "picked_from": ["pledge.unconditional_tranche_levels.levels"], "picked_path": "pledge.unconditional_tranche_levels.levels"})

    # ---------------------------
    # computed flags (deterministic)
    # ---------------------------
    roll_map = {e["field"]: e["value"] for e in extracts_r25}
    mar_map = {e["field"]: e["value"] for e in extracts_m}
    tw_map = {e["field"]: e["value"] for e in extracts_tw}

    computed_flags: Dict[str, Any] = {
        "roll25": {
            "heat_trade_value_p_ge_95_60d": flag_ge(roll_map.get("trade_value_win60_p"), 95.0),
            "heat_trade_value_p_ge_99_252d": flag_ge(roll_map.get("trade_value_win252_p"), 99.0),
            "index_close_p_ge_99_252d": flag_ge(roll_map.get("close_win252_p"), 99.0),
            "volume_amplified": roll_map.get("volume_amplified"),
            "vol_multiplier_20_ge_1p5": flag_ge(roll_map.get("vol_multiplier_20"), 1.5),
        },
        "margin": {
            "twse_is_30row_high": mar_map.get("twse_is_30row_high"),
            "tpex_is_30row_high": mar_map.get("tpex_is_30row_high"),
            "total_is_30row_high": mar_map.get("total_is_30row_high"),
            "total_chg_3d_sum_ge_0": flag_ge(mar_map.get("total_chg_3d_sum"), 0.0),
        },
        "tw0050_bb": {
            "bb_z_ge_2": flag_ge(tw_map.get("bb_z"), 2.0),
            "rv_pctl_ge_80": flag_ge(tw_map.get("rv_ann_pctl"), 80.0),
            "regime_allowed": tw_map.get("regime_allowed"),
            "pledge_action_bucket": tw_map.get("pledge_action_bucket"),
        },
        "thresholds_note": {
            "roll25.heat_trade_value_p_ge_95_60d": "p >= 95",
            "roll25.heat_trade_value_p_ge_99_252d": "p >= 99",
            "roll25.index_close_p_ge_99_252d": "p >= 99",
            "roll25.vol_multiplier_20_ge_1p5": "vol_multiplier_20 >= 1.5",
            "margin.total_chg_3d_sum_ge_0": "sum(chg_yi, last 3) >= 0",
            "tw0050_bb.bb_z_ge_2": "bb_z >= 2.0",
            "tw0050_bb.rv_pctl_ge_80": "rv_ann_pctl >= 80",
        }
    }

    pack: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "build_fingerprint": BUILD_FINGERPRINT,
        "generated_at_utc": utc_now_iso(),
        "generated_at_local": local_now_iso(),
        "timezone": "Asia/Taipei",
        "day_key_local": day_key_local,
        "inputs": {
            "tw0050_bb": {
                "path": args.tw0050,
                "as_of_date": tw_asof.isoformat() if tw_asof else None,
                "age_days": tw_age,
                "dq_flags": tw_dq_flags,
                "fingerprint": tw_fp,
                "picked_as_of_path": tw_asof_path,
            },
            "roll25": {
                "path": args.roll25,
                "as_of_date": r25_asof.isoformat() if r25_asof else None,
                "age_days": r25_age,
                "dq_flags": [],
                "fingerprint": r25_fp,
                "picked_as_of_path": r25_asof_path,
            },
            "taiwan_margin": {
                "path": args.margin,
                "as_of_date": m_asof.isoformat() if m_asof else None,
                "age_days": m_age,
                "dq_flags": [],
                "fingerprint": m_fp,
                "picked_as_of_path": m_asof_path,
            },
        },
        "warnings": uniq_keep_order(sorted(warnings)),
        "extracts_best_effort": {
            "tw0050_bb": extracts_tw,
            "roll25": extracts_r25,
            "margin": extracts_m,
        },
        "computed_flags": computed_flags,
        "raw": {
            "tw0050_bb": tw,
            "roll25": r25,
            "taiwan_margin": m,
        },
        "meta_env": {
            "GITHUB_SHA": os.getenv("GITHUB_SHA"),
            "GITHUB_RUN_ID": os.getenv("GITHUB_RUN_ID"),
            "GITHUB_WORKFLOW": os.getenv("GITHUB_WORKFLOW"),
            "GITHUB_REF_NAME": os.getenv("GITHUB_REF_NAME"),
            "GITHUB_REPOSITORY": os.getenv("GITHUB_REPOSITORY"),
        },
    }

    # write outputs
    pack_path = out_dir / "episode_pack.json"
    data_md_path = out_dir / "episode_data.md"
    outline_md_path = out_dir / "episode_outline.md"

    dump_json(str(pack_path), pack)

    md_data = build_md_data(pack)
    data_md_path.write_text(md_data, encoding="utf-8")

    if args.md_mode == "data":
        # keep workflow compatibility: episode_outline.md is the data brief
        outline_md_path.write_text(md_data, encoding="utf-8")
    elif args.md_mode == "outline":
        md_outline = build_md_outline_minimal(pack)
        outline_md_path.write_text(md_outline, encoding="utf-8")
    else:  # both
        md_outline = build_md_outline_minimal(pack)
        outline_md_path.write_text(md_outline, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())