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
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "episode_pack_schema_v1"
BUILD_FINGERPRINT = "build_video_pack@v1.2.rich_outline_more_extracts"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def add_extract(extracts: List[Dict[str, Any]], field: str, obj: Dict[str, Any], paths: List[str]) -> None:
    v, _p = pick_first(obj, paths)
    if v is None:
        return
    # Keep full candidate paths for audit (best-effort trace)
    extracts.append({"field": field, "value": v, "picked_from": paths})


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _sum_last_n(rows: List[Dict[str, Any]], key: str, n: int) -> Optional[float]:
    if not isinstance(rows, list) or n <= 0:
        return None
    s = 0.0
    cnt = 0
    for it in rows[:n]:
        if not isinstance(it, dict):
            continue
        v = _safe_float(it.get(key))
        if v is None:
            continue
        s += v
        cnt += 1
    return s if cnt > 0 else None


def _is_latest_max(rows: List[Dict[str, Any]], key: str) -> Optional[bool]:
    if not isinstance(rows, list) or not rows:
        return None
    latest = _safe_float(rows[0].get(key)) if isinstance(rows[0], dict) else None
    if latest is None:
        return None
    mx = latest
    ok = True
    for it in rows[1:]:
        if not isinstance(it, dict):
            continue
        v = _safe_float(it.get(key))
        if v is None:
            continue
        if v > mx:
            mx = v
            ok = False
    return ok if mx == latest else False


def build_outline(pack: Dict[str, Any]) -> str:
    tz = pack.get("timezone", "Asia/Taipei")
    day = pack.get("day_key_local", "N/A")
    warnings = pack.get("warnings", [])
    inp = pack.get("inputs", {})
    ext = pack.get("extracts_best_effort", {})

    def s(x: Any) -> str:
        return "N/A" if x is None else str(x)

    def fnum(x: Any, nd: int = 2) -> str:
        return fmt_float(x, nd)

    def vmap(key: str) -> Dict[str, Any]:
        return {e["field"]: e["value"] for e in ext.get(key, []) if isinstance(e, dict) and "field" in e}

    r = inp.get("roll25", {})
    m = inp.get("taiwan_margin", {})
    t = inp.get("tw0050_bb", {})

    rE = vmap("roll25")
    mE = vmap("margin")
    tE = vmap("tw0050_bb")

    out: List[str] = []
    out.append("# 投資日記 Episode Outline（roll25 + taiwan margin + tw0050_bb）\n")
    out.append(f"- 產出日：{day}（{tz}）")
    out.append("- 輸出：episode_pack.json, episode_outline.md")
    out.append(f"- warnings: {', '.join(warnings) if warnings else 'NONE'}\n")

    # ---- 10秒總結 ----
    out.append("## 今日 10 秒總結（先講人話）")
    if warnings:
        out.append("- ⚠️ 偵測到 warnings：本集只做狀態描述，不做跨模組因果推論。")
    out.append(
        f"- **成交熱度**：20日成交金額 z={fnum(rE.get('trade_value_win60_z'),3)} / p={fnum(rE.get('trade_value_win60_p'),3)}；"
        f"252日 z={fnum(rE.get('trade_value_win252_z'),3)} / p={fnum(rE.get('trade_value_win252_p'),3)}"
    )
    out.append(
        f"- **槓桿動向**：TWSE 融資餘額(億)={fnum(mE.get('twse_balance_yi'),1)}（日變動 {fnum(mE.get('twse_chg_yi'),1)}）；"
        f"TPEX={fnum(mE.get('tpex_balance_yi'),1)}（日變動 {fnum(mE.get('tpex_chg_yi'),1)}）"
    )
    out.append(
        f"- **0050 位置**：{s(tE.get('bb_state'))}（bb_z={fnum(tE.get('bb_z'),3)}，價格 {fnum(tE.get('adjclose'),2)}）；"
        f"Regime gate={s(tE.get('regime_allowed'))}；質押指引={s(tE.get('pledge_action_bucket'))}\n"
    )

    # ---- 開場 ----
    out.append("## 開場（20秒）")
    out.append("- 今天用三個訊號整理市場位置：成交熱度（roll25）、槓桿動向（margin）、0050 技術位置（BB）。")
    out.append("- 原則：只講「目前狀態 + 可稽核數字」，不把它包裝成預測。\n")

    # ---- Roll25 ----
    out.append("## 1) 成交熱度（roll25）（60–90秒）")
    out.append(f"- as_of：{s(r.get('as_of_date'))}；age_days={s(r.get('age_days'))}；mode={s(rE.get('mode'))}")
    out.append(
        f"- 成交金額熱度：20日 z={fnum(rE.get('trade_value_win60_z'),3)} / p={fnum(rE.get('trade_value_win60_p'),3)}；"
        f"252日 z={fnum(rE.get('trade_value_win252_z'),3)} / p={fnum(rE.get('trade_value_win252_p'),3)}"
    )
    if rE.get("close_win252_z") is not None and rE.get("close_win252_p") is not None:
        out.append(f"- 指數位置（可選口播）：252日 close z={fnum(rE.get('close_win252_z'),3)} / p={fnum(rE.get('close_win252_p'),3)}")
    if rE.get("vol_multiplier_20") is not None:
        out.append(f"- 放量檢查：vol_multiplier_20={fnum(rE.get('vol_multiplier_20'),3)}；volume_amplified={s(rE.get('volume_amplified'))}")
    out.append("- 一句話狀態：成交與熱度分位偏高，市場有「擁擠交易」的味道。")
    out.append("- 反方審核：高成交 ≠ 必然回檔；多頭趨勢中，高成交可能持續。")
    out.append("- 今天的動作：新增資金優先做再平衡（現金/短債），避免追價式加碼。\n")

    # ---- Margin ----
    out.append("## 2) 槓桿動向（taiwan margin）（60–90秒）")
    out.append(f"- as_of：{s(m.get('as_of_date'))}；age_days={s(m.get('age_days'))}")
    out.append(f"- TWSE：餘額(億)={fnum(mE.get('twse_balance_yi'),1)}；日變動(億)={fnum(mE.get('twse_chg_yi'),1)}")
    out.append(f"- TPEX：餘額(億)={fnum(mE.get('tpex_balance_yi'),1)}；日變動(億)={fnum(mE.get('tpex_chg_yi'),1)}")
    if mE.get("total_balance_yi") is not None and mE.get("total_chg_yi") is not None:
        out.append(f"- 合計：餘額(億)={fnum(mE.get('total_balance_yi'),1)}；日變動(億)={fnum(mE.get('total_chg_yi'),1)}")
    if mE.get("twse_chg_3d_sum_yi") is not None or mE.get("tpex_chg_3d_sum_yi") is not None:
        out.append(
            f"- 近3日累積變動(億)：TWSE={fnum(mE.get('twse_chg_3d_sum_yi'),1)}；TPEX={fnum(mE.get('tpex_chg_3d_sum_yi'),1)}；"
            f"合計={fnum(mE.get('total_chg_3d_sum_yi'),1)}"
        )
    if mE.get("twse_balance_is_30row_high") is not None or mE.get("tpex_balance_is_30row_high") is not None:
        out.append(
            f"- 近30筆是否創高：TWSE={s(mE.get('twse_balance_is_30row_high'))}；TPEX={s(mE.get('tpex_balance_is_30row_high'))}"
        )
    out.append("- 一句話狀態：融資水位與變動方向若偏正，代表市場承擔風險的意願偏高。")
    out.append("- 反方審核：融資增加不等於散戶一定輸；但通常意味著脆弱性上升（遇到急跌時更容易擠兌）。")
    out.append("- 今天的動作：避免新增槓桿；若你已經有槓桿，優先檢查維持率與最大損失上限。\n")

    # ---- TW0050 ----
    out.append("## 3) 0050 位置（tw0050_bb）（90–140秒）")
    out.append(f"- as_of：{s(t.get('as_of_date'))}；age_days={s(t.get('age_days'))}")
    out.append(f"- BB 狀態：{s(tE.get('bb_state'))}；bb_z={fnum(tE.get('bb_z'),3)}；價格(adjclose)={fnum(tE.get('adjclose'),2)}")
    if tE.get("trend_state") is not None or tE.get("price_vs_200ma_pct") is not None:
        out.append(
            f"- 趨勢：trend_state={s(tE.get('trend_state'))}；price_vs_200MA={fnum(tE.get('price_vs_200ma_pct'),2)}%"
        )
    if tE.get("rv_ann_pctl") is not None:
        out.append(f"- 波動分位：RV20 pctl={fnum(tE.get('rv_ann_pctl'),2)}（分位越高代表近期波動相對歷史更偏大）")
    out.append(f"- Gate/指引：regime_allowed={s(tE.get('regime_allowed'))}；pledge_action={s(tE.get('pledge_action_bucket'))}")
    if tE.get("veto_reasons") is not None:
        out.append(f"- VETO 原因（可選口播）：{s(tE.get('veto_reasons'))}")
    if tE.get("tranche_levels") is not None:
        out.append(f"- 分批參考價位（你自己的 tranche levels）：{s(tE.get('tranche_levels'))}")
    out.append("- 一句話狀態：在上軌極端區時，最大的錯誤是『用更高風險去追更高價格』。")
    out.append("- 反方審核：EXTREME_UPPER_BAND 不等於立刻回檔；強勢趨勢可能貼上軌很久。")
    out.append("- 今天的動作：不追價；把加碼改成「等回檔分批」，用 tranche levels 當節奏參考。\n")

    # ---- 收尾 ----
    out.append("## 收尾（20–30秒）")
    out.append("- 免責：非投資建議。本集是狀態描述；高分位數只代表『偏極端』，不保證反轉。")
    out.append("- 下集追蹤：成交熱度是否降溫（pctl 回落）、融資是否轉負、0050 是否脫離上軌極端或 RV 分位下降。")
    out.append("- 行動句：當三訊號同向偏熱時，我只做再平衡與風險上限管理；當訊號降溫且回到可接受區間，才恢復分批投入。")

    return "\n".join(out) + "\n"


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

    # staleness rule (tunable)
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

    # roll25: mode + trade_value heat + close heat + volume signals
    add_extract(extracts_r25, "mode", r25, ["mode"])
    add_extract(extracts_r25, "used_date", r25, ["used_date"])
    add_extract(extracts_r25, "trade_value_win60_z", r25, ["series.trade_value.win60.z"])
    add_extract(extracts_r25, "trade_value_win60_p", r25, ["series.trade_value.win60.p"])
    add_extract(extracts_r25, "trade_value_win252_z", r25, ["series.trade_value.win252.z"])
    add_extract(extracts_r25, "trade_value_win252_p", r25, ["series.trade_value.win252.p"])
    add_extract(extracts_r25, "close_win60_z", r25, ["series.close.win60.z"])
    add_extract(extracts_r25, "close_win60_p", r25, ["series.close.win60.p"])
    add_extract(extracts_r25, "close_win252_z", r25, ["series.close.win252.z"])
    add_extract(extracts_r25, "close_win252_p", r25, ["series.close.win252.p"])
    add_extract(extracts_r25, "vol_multiplier_20", r25, ["derived.vol_multiplier_20"])
    add_extract(extracts_r25, "volume_amplified", r25, ["derived.volume_amplified"])

    # margin: latest row for TWSE/TPEX + totals + 3D sum + 30row high check
    add_extract(extracts_m, "twse_data_date", m, ["series.TWSE.data_date"])
    add_extract(extracts_m, "twse_balance_yi", m, ["series.TWSE.rows.0.balance_yi"])
    add_extract(extracts_m, "twse_chg_yi", m, ["series.TWSE.rows.0.chg_yi"])
    add_extract(extracts_m, "tpex_data_date", m, ["series.TPEX.data_date"])
    add_extract(extracts_m, "tpex_balance_yi", m, ["series.TPEX.rows.0.balance_yi"])
    add_extract(extracts_m, "tpex_chg_yi", m, ["series.TPEX.rows.0.chg_yi"])

    twse_bal = _safe_float(deep_get(m, "series.TWSE.rows.0.balance_yi"))
    tpex_bal = _safe_float(deep_get(m, "series.TPEX.rows.0.balance_yi"))
    twse_chg = _safe_float(deep_get(m, "series.TWSE.rows.0.chg_yi"))
    tpex_chg = _safe_float(deep_get(m, "series.TPEX.rows.0.chg_yi"))

    if twse_bal is not None and tpex_bal is not None:
        extracts_m.append({
            "field": "total_balance_yi",
            "value": twse_bal + tpex_bal,
            "picked_from": ["series.TWSE.rows.0.balance_yi + series.TPEX.rows.0.balance_yi"],
        })
    if twse_chg is not None and tpex_chg is not None:
        extracts_m.append({
            "field": "total_chg_yi",
            "value": twse_chg + tpex_chg,
            "picked_from": ["series.TWSE.rows.0.chg_yi + series.TPEX.rows.0.chg_yi"],
        })

    twse_rows = deep_get(m, "series.TWSE.rows") or []
    tpex_rows = deep_get(m, "series.TPEX.rows") or []
    if isinstance(twse_rows, list):
        v = _sum_last_n(twse_rows, "chg_yi", 3)
        if v is not None:
            extracts_m.append({"field": "twse_chg_3d_sum_yi", "value": v, "picked_from": ["sum(series.TWSE.rows[:3].chg_yi)"]})
        hi = _is_latest_max(twse_rows, "balance_yi")
        if hi is not None:
            extracts_m.append({"field": "twse_balance_is_30row_high", "value": hi, "picked_from": ["latest == max(series.TWSE.rows[:].balance_yi)"]})
    if isinstance(tpex_rows, list):
        v = _sum_last_n(tpex_rows, "chg_yi", 3)
        if v is not None:
            extracts_m.append({"field": "tpex_chg_3d_sum_yi", "value": v, "picked_from": ["sum(series.TPEX.rows[:3].chg_yi)"]})
        hi = _is_latest_max(tpex_rows, "balance_yi")
        if hi is not None:
            extracts_m.append({"field": "tpex_balance_is_30row_high", "value": hi, "picked_from": ["latest == max(series.TPEX.rows[:].balance_yi)"]})

    # total 3D sum best-effort
    tw3 = next((e["value"] for e in extracts_m if e.get("field") == "twse_chg_3d_sum_yi"), None)
    tp3 = next((e["value"] for e in extracts_m if e.get("field") == "tpex_chg_3d_sum_yi"), None)
    tw3f = _safe_float(tw3)
    tp3f = _safe_float(tp3)
    if tw3f is not None and tp3f is not None:
        extracts_m.append({"field": "total_chg_3d_sum_yi", "value": tw3f + tp3f, "picked_from": ["twse_chg_3d_sum_yi + tpex_chg_3d_sum_yi"]})

    # tw0050_bb: latest state + z + regime + pledge decision + trend/vol + veto reasons + tranche levels
    add_extract(extracts_tw, "last_date", tw, ["meta.last_date", "latest.date"])
    add_extract(extracts_tw, "adjclose", tw, ["latest.adjclose", "latest.price_used"])
    add_extract(extracts_tw, "bb_z", tw, ["latest.bb_z"])
    add_extract(extracts_tw, "bb_state", tw, ["latest.state"])
    add_extract(extracts_tw, "regime_allowed", tw, ["regime.allowed"])
    add_extract(extracts_tw, "pledge_action_bucket", tw, ["pledge.decision.action_bucket"])

    add_extract(extracts_tw, "trend_state", tw, ["trend.state"])
    add_extract(extracts_tw, "price_vs_200ma_pct", tw, ["trend.price_vs_trend_ma_pct"])
    add_extract(extracts_tw, "rv_ann_pctl", tw, ["vol.rv_ann_pctl"])
    add_extract(extracts_tw, "veto_reasons", tw, ["pledge.decision.veto_reasons"])

    levels = deep_get(tw, "pledge.unconditional_tranche_levels.levels")
    if isinstance(levels, list) and levels:
        lvl_txt: List[str] = []
        for it in levels[:6]:
            if isinstance(it, dict) and "label" in it and "price_level" in it:
                try:
                    lvl_txt.append(f"{it['label']}={float(it['price_level']):.2f}")
                except Exception:
                    pass
        if lvl_txt:
            extracts_tw.append({
                "field": "tranche_levels",
                "value": ", ".join(lvl_txt),
                "picked_from": ["pledge.unconditional_tranche_levels.levels[:6].(label,price_level)"],
            })

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
    md_path = out_dir / "episode_outline.md"
    dump_json(str(pack_path), pack)
    md = build_outline(pack)
    md_path.write_text(md, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())