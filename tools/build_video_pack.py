#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_video_pack.py

Build an "episode pack" for video/script production by combining:
- roll25_cache/stats_latest.json
- taiwan_margin_cache/latest.json
- tw0050_bb_cache/stats_latest.json

Outputs (flat):
- episode_pack.json
- episode_outline.md

Audit-first:
- keep raw inputs
- best-effort extracts with picked_from path trace
- explicit warnings (missing/stale/date_misaligned)
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


SCHEMA_VERSION = "episode_pack_schema_v1"
BUILD_FINGERPRINT = "build_video_pack@v1.1.nested_paths"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def fmt_pct(x: Any, nd: int = 2) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x):.{nd}f}%"
    except Exception:
        return "N/A"


@dataclass
class Extract:
    field: str
    value: Any
    picked_from: List[str]


def add_extract(extracts: List[Dict[str, Any]], field: str, obj: Dict[str, Any], paths: List[str]) -> None:
    v, p = pick_first(obj, paths)
    if v is None:
        return
    extracts.append({"field": field, "value": v, "picked_from": paths})


def build_outline(pack: Dict[str, Any]) -> str:
    tz = pack.get("timezone", "Asia/Taipei")
    day = pack.get("day_key_local", "N/A")
    warnings = pack.get("warnings", [])
    inp = pack.get("inputs", {})
    ext = pack.get("extracts_best_effort", {})

    def wline(s: str) -> str:
        return s + "\n"

    out = ""
    out += wline("# 投資日記 Episode Outline（roll25 + taiwan margin + tw0050_bb）")
    out += wline("")
    out += wline(f"- 產出日：{day}（{tz}）")
    out += wline("- 輸出：episode_pack.json, episode_outline.md")
    out += wline(f"- warnings: {', '.join(warnings) if warnings else 'NONE'}")
    out += wline("")

    out += wline("## 開場（20秒）")
    out += wline("- 今天用三個訊號整理市場位置：成交熱度（roll25）、槓桿動向（margin）、0050 技術位置（BB）。")
    if warnings:
        out += wline("- ⚠️ 本集偵測到 warnings：僅做「狀態描述」，避免跨模組因果推論。")
    out += wline("")

    # roll25
    r = inp.get("roll25", {})
    r_asof = r.get("as_of_date") or "N/A"
    r_age = r.get("age_days")
    out += wline("## 1) 成交熱度（roll25）（60秒）")
    out += wline(f"- as_of：{r_asof}；age_days={r_age if r_age is not None else 'N/A'}")
    # Pull key numbers from extracts if present
    roll_ext = {e["field"]: e["value"] for e in ext.get("roll25", [])}
    if "mode" in roll_ext:
        out += wline(f"- mode: {roll_ext['mode']}")
    if "trade_value_win60_z" in roll_ext and "trade_value_win60_p" in roll_ext:
        out += wline(f"- 20日成交金額熱度：z={fmt_float(roll_ext['trade_value_win60_z'],3)} / p={fmt_float(roll_ext['trade_value_win60_p'],3)}")
    if "trade_value_win252_z" in roll_ext and "trade_value_win252_p" in roll_ext:
        out += wline(f"- 252日成交金額熱度：z={fmt_float(roll_ext['trade_value_win252_z'],3)} / p={fmt_float(roll_ext['trade_value_win252_p'],3)}")
    out += wline("")

    # margin
    m = inp.get("taiwan_margin", {})
    m_asof = m.get("as_of_date") or "N/A"
    m_age = m.get("age_days")
    out += wline("## 2) 槓桿動向（taiwan margin）（60秒）")
    out += wline(f"- as_of：{m_asof}；age_days={m_age if m_age is not None else 'N/A'}")
    m_ext = {e["field"]: e["value"] for e in ext.get("margin", [])}
    if "twse_balance_yi" in m_ext and "twse_chg_yi" in m_ext:
        out += wline(f"- TWSE 融資餘額(億)：{fmt_float(m_ext['twse_balance_yi'],1)}；當日變動(億)：{fmt_float(m_ext['twse_chg_yi'],1)}")
    if "tpex_balance_yi" in m_ext and "tpex_chg_yi" in m_ext:
        out += wline(f"- TPEX 融資餘額(億)：{fmt_float(m_ext['tpex_balance_yi'],1)}；當日變動(億)：{fmt_float(m_ext['tpex_chg_yi'],1)}")
    if "total_balance_yi" in m_ext and "total_chg_yi" in m_ext:
        out += wline(f"- 合計（TWSE+TPEX）餘額(億)：{fmt_float(m_ext['total_balance_yi'],1)}；變動(億)：{fmt_float(m_ext['total_chg_yi'],1)}")
    out += wline("")

    # tw0050_bb
    t = inp.get("tw0050_bb", {})
    t_asof = t.get("as_of_date") or "N/A"
    t_age = t.get("age_days")
    out += wline("## 3) 0050 位置（tw0050_bb）（80秒）")
    out += wline(f"- as_of：{t_asof}；age_days={t_age if t_age is not None else 'N/A'}")
    t_ext = {e["field"]: e["value"] for e in ext.get("tw0050_bb", [])}
    if "bb_state" in t_ext and "bb_z" in t_ext:
        out += wline(f"- BB 狀態：{t_ext['bb_state']}；bb_z={fmt_float(t_ext['bb_z'],3)}")
    if "adjclose" in t_ext:
        out += wline(f"- 價格（adjclose）：{fmt_float(t_ext['adjclose'],2)}")
    if "regime_allowed" in t_ext:
        out += wline(f"- Regime gate（允許風險開槓/加碼）：{t_ext['regime_allowed']}")
    if "pledge_action_bucket" in t_ext:
        out += wline(f"- 你自己的質押指引：{t_ext['pledge_action_bucket']}")
    out += wline("")

    out += wline("## 收尾（20秒）")
    out += wline("- 免責：非投資建議。資料可能落後/不一致（見 warnings）。歷史統計不保證未來。")
    out += wline("- 行動句（模板）：若風險訊號升溫，優先守住現金流與部位上限；若訊號降溫，再考慮分批與再平衡。")
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

    # --- day key local ---
    day_key_local = datetime.now().astimezone().date().isoformat()

    # --- as_of extraction (match YOUR real JSON structure) ---
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

    # staleness rule (you can tune)
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

    # fingerprints
    tw_fp = deep_get(tw, "meta.script_fingerprint")
    r25_fp = deep_get(r25, "script_fingerprint") or deep_get(r25, "schema_version")
    m_fp = deep_get(m, "schema_version")

    # --- extracts_best_effort ---
    extracts_tw: List[Dict[str, Any]] = []
    extracts_r25: List[Dict[str, Any]] = []
    extracts_m: List[Dict[str, Any]] = []

    # roll25: mode + trade_value heat
    add_extract(extracts_r25, "mode", r25, ["mode"])
    add_extract(extracts_r25, "used_date", r25, ["used_date"])
    add_extract(extracts_r25, "trade_value_win60_z", r25, ["series.trade_value.win60.z"])
    add_extract(extracts_r25, "trade_value_win60_p", r25, ["series.trade_value.win60.p"])
    add_extract(extracts_r25, "trade_value_win252_z", r25, ["series.trade_value.win252.z"])
    add_extract(extracts_r25, "trade_value_win252_p", r25, ["series.trade_value.win252.p"])

    # margin: latest row for TWSE/TPEX + totals
    add_extract(extracts_m, "twse_data_date", m, ["series.TWSE.data_date"])
    add_extract(extracts_m, "twse_balance_yi", m, ["series.TWSE.rows.0.balance_yi"])
    add_extract(extracts_m, "twse_chg_yi", m, ["series.TWSE.rows.0.chg_yi"])
    add_extract(extracts_m, "tpex_data_date", m, ["series.TPEX.data_date"])
    add_extract(extracts_m, "tpex_balance_yi", m, ["series.TPEX.rows.0.balance_yi"])
    add_extract(extracts_m, "tpex_chg_yi", m, ["series.TPEX.rows.0.chg_yi"])

    twse_bal = deep_get(m, "series.TWSE.rows.0.balance_yi")
    tpex_bal = deep_get(m, "series.TPEX.rows.0.balance_yi")
    twse_chg = deep_get(m, "series.TWSE.rows.0.chg_yi")
    tpex_chg = deep_get(m, "series.TPEX.rows.0.chg_yi")
    if isinstance(twse_bal, (int, float)) and isinstance(tpex_bal, (int, float)):
        extracts_m.append({"field": "total_balance_yi", "value": twse_bal + tpex_bal, "picked_from": ["series.TWSE.rows.0.balance_yi + series.TPEX.rows.0.balance_yi"]})
    if isinstance(twse_chg, (int, float)) and isinstance(tpex_chg, (int, float)):
        extracts_m.append({"field": "total_chg_yi", "value": twse_chg + tpex_chg, "picked_from": ["series.TWSE.rows.0.chg_yi + series.TPEX.rows.0.chg_yi"]})

    # tw0050_bb: latest state + z + regime + pledge decision
    add_extract(extracts_tw, "last_date", tw, ["meta.last_date", "latest.date"])
    add_extract(extracts_tw, "adjclose", tw, ["latest.adjclose", "latest.price_used"])
    add_extract(extracts_tw, "bb_z", tw, ["latest.bb_z"])
    add_extract(extracts_tw, "bb_state", tw, ["latest.state"])
    add_extract(extracts_tw, "regime_allowed", tw, ["regime.allowed"])
    add_extract(extracts_tw, "pledge_action_bucket", tw, ["pledge.decision.action_bucket"])

    pack: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "build_fingerprint": BUILD_FINGERPRINT,
        "generated_at_utc": utc_now_iso(),
        "generated_at_local": datetime.now().astimezone().isoformat(),
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
        "warnings": sorted(list(dict.fromkeys(warnings))),  # unique keep order-ish
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
    md_path = out_dir / "episode_outline.md"
    dump_json(str(pack_path), pack)
    md = build_outline(pack)
    md_path.write_text(md, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())