#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_video_pack.py

Build an "episode pack" for video/script production by combining:
- roll25_cache/stats_latest.json
- taiwan_margin_cache/latest.json
- tw0050_bb_cache/stats_latest.json

Outputs (flat) to out_dir:
- episode_pack.json
- episode_outline.md
- episode_data.md  (DATA-ONLY, audit-first)

Audit-first:
- keep raw inputs
- best-effort extracts with picked_path trace
- explicit warnings (missing/stale/date_misaligned)
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo


SCHEMA_VERSION = "episode_pack_schema_v1"
BUILD_FINGERPRINT = "build_video_pack@v1.3.data_md_out_and_tz_fix"


TZ_NAME = "Asia/Taipei"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_local() -> datetime:
    return datetime.now(ZoneInfo(TZ_NAME))


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

    s = str(x).strip()
    # YYYY-MM-DD...
    if len(s) >= 10 and len(s) >= 10 and s[4] == "-" and s[7] == "-":
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


def fmt_float(x: Any, nd: int = 2) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.{nd}f}"
    except Exception:
        return "N/A"


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
    extracts.append(
        {
            "field": field,
            "value": v,
            "picked_from": paths,
            "picked_path": p,
        }
    )


def add_extract_formula(extracts: List[Dict[str, Any]], field: str, value: Any, formula: str) -> None:
    extracts.append(
        {
            "field": field,
            "value": value,
            "picked_from": [formula],
            "picked_path": "FORMULA",
        }
    )


def _extract_map(ext_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {e.get("field"): e.get("value") for e in ext_list or []}


def build_outline(pack: Dict[str, Any]) -> str:
    """
    Light outline (data-first, minimal narrative).
    You can paste episode_data.md back to ChatGPT for polishing into a richer script.
    """
    tz = pack.get("timezone", TZ_NAME)
    day = pack.get("day_key_local", "N/A")
    warnings = pack.get("warnings", [])
    inp = pack.get("inputs", {})
    ext = pack.get("extracts_best_effort", {})

    def w(s: str) -> str:
        return s + "\n"

    out = ""
    out += w("# 投資日記 Episode Outline（roll25 + taiwan margin + tw0050_bb）")
    out += w("")
    out += w(f"- 產出日：{day}（{tz}）")
    out += w("- 輸出：episode_pack.json, episode_outline.md, episode_data.md")
    out += w(f"- warnings: {', '.join(warnings) if warnings else 'NONE'}")
    out += w("")

    # 10s summary: data-only
    out += w("## 今日 10 秒總結（只列數據）")
    r_ext = _extract_map(ext.get("roll25", []))
    m_ext = _extract_map(ext.get("margin", []))
    t_ext = _extract_map(ext.get("tw0050_bb", []))

    if "trade_value_win60_z" in r_ext and "trade_value_win60_p" in r_ext:
        out += w(f"- 成交熱度(20D)：z={fmt_float(r_ext.get('trade_value_win60_z'),3)} / p={fmt_float(r_ext.get('trade_value_win60_p'),3)}")
    if "trade_value_win252_z" in r_ext and "trade_value_win252_p" in r_ext:
        out += w(f"- 成交熱度(252D)：z={fmt_float(r_ext.get('trade_value_win252_z'),3)} / p={fmt_float(r_ext.get('trade_value_win252_p'),3)}")
    if "twse_balance_yi" in m_ext and "twse_chg_yi" in m_ext:
        out += w(f"- TWSE 融資(億)：餘額={fmt_float(m_ext.get('twse_balance_yi'),1)} / 日變動={fmt_float(m_ext.get('twse_chg_yi'),1)}")
    if "tpex_balance_yi" in m_ext and "tpex_chg_yi" in m_ext:
        out += w(f"- TPEX 融資(億)：餘額={fmt_float(m_ext.get('tpex_balance_yi'),1)} / 日變動={fmt_float(m_ext.get('tpex_chg_yi'),1)}")
    if "bb_state" in t_ext and "bb_z" in t_ext and "adjclose" in t_ext:
        out += w(f"- 0050：{t_ext.get('bb_state')} / bb_z={fmt_float(t_ext.get('bb_z'),3)} / 價格={fmt_float(t_ext.get('adjclose'),2)}")
    out += w("")

    # per module meta
    out += w("## 1) roll25（成交熱度）")
    r = inp.get("roll25", {})
    out += w(f"- as_of={r.get('as_of_date') or 'N/A'} / age_days={r.get('age_days') if r.get('age_days') is not None else 'N/A'} / mode={r_ext.get('mode','N/A')}")
    out += w("")

    out += w("## 2) taiwan margin（槓桿動向）")
    m = inp.get("taiwan_margin", {})
    out += w(f"- as_of={m.get('as_of_date') or 'N/A'} / age_days={m.get('age_days') if m.get('age_days') is not None else 'N/A'}")
    out += w("")

    out += w("## 3) tw0050_bb（0050 技術位置）")
    t = inp.get("tw0050_bb", {})
    out += w(f"- as_of={t.get('as_of_date') or 'N/A'} / age_days={t.get('age_days') if t.get('age_days') is not None else 'N/A'}")
    out += w("")
    out += w("## 提示")
    out += w("- 詳細數據與欄位來源請看 episode_data.md（可直接貼回來讓我幫你潤飾成口播稿）。")
    return out


def build_data_md(pack: Dict[str, Any]) -> str:
    """
    DATA-ONLY markdown with path/formula trace.
    No advice, no narrative claims.
    """
    tz = pack.get("timezone", TZ_NAME)
    day = pack.get("day_key_local", "N/A")
    warnings = pack.get("warnings", [])
    inp = pack.get("inputs", {})
    ext = pack.get("extracts_best_effort", {})

    def w(s: str) -> str:
        return s + "\n"

    def section(title: str) -> str:
        return f"## {title}\n\n"

    def kv(k: str, v: Any) -> str:
        return f"- {k}: {v}\n"

    def ext_table(ext_list: List[Dict[str, Any]]) -> str:
        out = ""
        out += "| field | value | picked_path |\n"
        out += "|---|---:|---|\n"
        for e in ext_list or []:
            field = e.get("field")
            val = e.get("value")
            picked_path = e.get("picked_path") or "N/A"
            # keep value JSON-ish but compact
            if isinstance(val, float):
                sval = fmt_float(val, 6).rstrip("0").rstrip(".")
            else:
                sval = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
            out += f"| {field} | {sval} | {picked_path} |\n"
        out += "\n"
        return out

    out = ""
    out += w("# Episode Data (DATA-ONLY)")
    out += w("")
    out += w(f"- day_key_local: {day} ({tz})")
    out += w(f"- generated_at_utc: {pack.get('generated_at_utc','N/A')}")
    out += w(f"- generated_at_local: {pack.get('generated_at_local','N/A')}")
    out += w(f"- build_fingerprint: {pack.get('build_fingerprint','N/A')}")
    out += w(f"- warnings: {', '.join(warnings) if warnings else 'NONE'}")
    out += w("")

    # Inputs summary
    out += section("Inputs (as_of / age_days / fingerprint)")
    for k in ["roll25", "taiwan_margin", "tw0050_bb"]:
        v = inp.get(k, {})
        out += kv(k, f"as_of={v.get('as_of_date')} age_days={v.get('age_days')} fingerprint={v.get('fingerprint')}")
    out += w("")

    # roll25 extracts
    out += section("roll25 extracts")
    out += ext_table(ext.get("roll25", []))

    # margin extracts
    out += section("taiwan_margin extracts")
    out += ext_table(ext.get("margin", []))

    # tw0050 extracts
    out += section("tw0050_bb extracts")
    out += ext_table(ext.get("tw0050_bb", []))

    # dq notes (trim)
    tw_raw = deep_get(pack, "raw.tw0050_bb") or {}
    dq_notes = deep_get(tw_raw, "dq.notes") or []
    if isinstance(dq_notes, list) and dq_notes:
        out += section("tw0050_bb dq.notes (first 6)")
        for s in dq_notes[:6]:
            out += w(f"- {s}")
        out += w("")

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tw0050", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--margin", required=True)
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tw = load_json(args.tw0050)
    r25 = load_json(args.roll25)
    m = load_json(args.margin)

    # local/utc stamps
    local_now = now_local()
    day_key_local = local_now.date().isoformat()

    # as_of extraction (match current JSON structures)
    tw_asof_raw, tw_asof_path = pick_first(tw, ["meta.last_date", "latest.date", "meta.lastDate", "last_date", "date"])
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

    # date misalignment
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

    # fingerprints
    tw_fp = deep_get(tw, "meta.script_fingerprint")
    r25_fp = deep_get(r25, "script_fingerprint") or deep_get(r25, "schema_version")
    m_fp = deep_get(m, "schema_version")

    # extracts
    extracts_tw: List[Dict[str, Any]] = []
    extracts_r25: List[Dict[str, Any]] = []
    extracts_m: List[Dict[str, Any]] = []

    # roll25
    add_extract(extracts_r25, "mode", r25, ["mode"])
    add_extract(extracts_r25, "used_date", r25, ["used_date"])
    add_extract(extracts_r25, "trade_value_win60_value", r25, ["series.trade_value.win60.value"])
    add_extract(extracts_r25, "trade_value_win60_z", r25, ["series.trade_value.win60.z"])
    add_extract(extracts_r25, "trade_value_win60_p", r25, ["series.trade_value.win60.p"])
    add_extract(extracts_r25, "trade_value_win252_value", r25, ["series.trade_value.win252.value"])
    add_extract(extracts_r25, "trade_value_win252_z", r25, ["series.trade_value.win252.z"])
    add_extract(extracts_r25, "trade_value_win252_p", r25, ["series.trade_value.win252.p"])
    add_extract(extracts_r25, "close_win252_z", r25, ["series.close.win252.z"])
    add_extract(extracts_r25, "close_win252_p", r25, ["series.close.win252.p"])
    add_extract(extracts_r25, "vol_multiplier_20", r25, ["derived.vol_multiplier_20"])
    add_extract(extracts_r25, "volume_amplified", r25, ["derived.volume_amplified"])
    add_extract(extracts_r25, "new_low_n", r25, ["derived.new_low_n"])
    add_extract(extracts_r25, "consecutive_down_days", r25, ["derived.consecutive_down_days"])

    # margin - latest row
    add_extract(extracts_m, "twse_data_date", m, ["series.TWSE.data_date"])
    add_extract(extracts_m, "twse_balance_yi", m, ["series.TWSE.rows.0.balance_yi"])
    add_extract(extracts_m, "twse_chg_yi", m, ["series.TWSE.rows.0.chg_yi"])
    add_extract(extracts_m, "tpex_data_date", m, ["series.TPEX.data_date"])
    add_extract(extracts_m, "tpex_balance_yi", m, ["series.TPEX.rows.0.balance_yi"])
    add_extract(extracts_m, "tpex_chg_yi", m, ["series.TPEX.rows.0.chg_yi"])

    twse_rows = deep_get(m, "series.TWSE.rows") or []
    tpex_rows = deep_get(m, "series.TPEX.rows") or []

    def _sum_chg(rows: Any, n: int) -> Optional[float]:
        if not isinstance(rows, list) or not rows:
            return None
        vals = []
        for r in rows[:n]:
            v = r.get("chg_yi") if isinstance(r, dict) else None
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if not vals:
            return None
        return float(sum(vals))

    twse_bal = deep_get(m, "series.TWSE.rows.0.balance_yi")
    tpex_bal = deep_get(m, "series.TPEX.rows.0.balance_yi")
    twse_chg = deep_get(m, "series.TWSE.rows.0.chg_yi")
    tpex_chg = deep_get(m, "series.TPEX.rows.0.chg_yi")

    if isinstance(twse_bal, (int, float)) and isinstance(tpex_bal, (int, float)):
        add_extract_formula(
            extracts_m, "total_balance_yi", float(twse_bal) + float(tpex_bal),
            "series.TWSE.rows.0.balance_yi + series.TPEX.rows.0.balance_yi"
        )
    if isinstance(twse_chg, (int, float)) and isinstance(tpex_chg, (int, float)):
        add_extract_formula(
            extracts_m, "total_chg_yi", float(twse_chg) + float(tpex_chg),
            "series.TWSE.rows.0.chg_yi + series.TPEX.rows.0.chg_yi"
        )

    s3_twse = _sum_chg(twse_rows, 3)
    s3_tpex = _sum_chg(tpex_rows, 3)
    if s3_twse is not None:
        add_extract_formula(extracts_m, "twse_chg_sum_3rows", s3_twse, "sum(series.TWSE.rows[0:3].chg_yi)")
    if s3_tpex is not None:
        add_extract_formula(extracts_m, "tpex_chg_sum_3rows", s3_tpex, "sum(series.TPEX.rows[0:3].chg_yi)")
    if s3_twse is not None and s3_tpex is not None:
        add_extract_formula(extracts_m, "total_chg_sum_3rows", s3_twse + s3_tpex, "twse_chg_sum_3rows + tpex_chg_sum_3rows")

    def _is_30rows_high_balance(rows: Any) -> Optional[bool]:
        if not isinstance(rows, list) or len(rows) < 2:
            return None
        vals = []
        for r in rows[:30]:
            v = r.get("balance_yi") if isinstance(r, dict) else None
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if not vals:
            return None
        return float(vals[0]) >= max(vals)

    hi_twse = _is_30rows_high_balance(twse_rows)
    hi_tpex = _is_30rows_high_balance(tpex_rows)
    if hi_twse is not None:
        add_extract_formula(extracts_m, "twse_is_30rows_high_balance", hi_twse, "rows[0].balance_yi == max(rows[0:30].balance_yi)")
    if hi_tpex is not None:
        add_extract_formula(extracts_m, "tpex_is_30rows_high_balance", hi_tpex, "rows[0].balance_yi == max(rows[0:30].balance_yi)")

    # tw0050_bb
    add_extract(extracts_tw, "last_date", tw, ["meta.last_date", "latest.date"])
    add_extract(extracts_tw, "adjclose", tw, ["latest.adjclose", "latest.price_used"])
    add_extract(extracts_tw, "bb_ma", tw, ["latest.bb_ma"])
    add_extract(extracts_tw, "bb_upper", tw, ["latest.bb_upper"])
    add_extract(extracts_tw, "bb_lower", tw, ["latest.bb_lower"])
    add_extract(extracts_tw, "bb_z", tw, ["latest.bb_z"])
    add_extract(extracts_tw, "bb_state", tw, ["latest.state"])
    add_extract(extracts_tw, "dist_to_upper_pct", tw, ["latest.dist_to_upper_pct"])
    add_extract(extracts_tw, "dist_to_lower_pct", tw, ["latest.dist_to_lower_pct"])
    add_extract(extracts_tw, "trend_state", tw, ["trend.state"])
    add_extract(extracts_tw, "price_vs_200ma_pct", tw, ["trend.price_vs_trend_ma_pct"])
    add_extract(extracts_tw, "trend_slope_pct", tw, ["trend.trend_slope_pct"])
    add_extract(extracts_tw, "rv_ann", tw, ["vol.rv_ann"])
    add_extract(extracts_tw, "rv_ann_pctl", tw, ["vol.rv_ann_pctl"])
    add_extract(extracts_tw, "regime_allowed", tw, ["regime.allowed"])
    add_extract(extracts_tw, "pledge_action_bucket", tw, ["pledge.decision.action_bucket"])
    add_extract(extracts_tw, "pledge_veto_reasons", tw, ["pledge.decision.veto_reasons"])

    # tranche levels (already computed in tw stats)
    levels = deep_get(tw, "pledge.unconditional_tranche_levels.levels")
    if isinstance(levels, list) and levels:
        add_extract(extracts_tw, "tranche_levels", tw, ["pledge.unconditional_tranche_levels.levels"])

    pack: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "build_fingerprint": BUILD_FINGERPRINT,
        "generated_at_utc": utc_now_iso(),
        "generated_at_local": local_now.replace(microsecond=0).isoformat(),
        "timezone": TZ_NAME,
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
        "warnings": sorted(list(dict.fromkeys(warnings))),
        "extracts_best_effort": {
            "tw0050_bb": extracts_tw,
            "roll25": extracts_r25,
            "margin": extracts_m,
        },
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
    outline_path = out_dir / "episode_outline.md"
    data_path = out_dir / "episode_data.md"

    dump_json(str(pack_path), pack)
    outline_path.write_text(build_outline(pack), encoding="utf-8")
    data_path.write_text(build_data_md(pack), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())