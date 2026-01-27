#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render roll25_cache/report.md from roll25_cache/latest_report.json (+ stats_latest.json).

Design goals:
- Deterministic output: no "now()" timestamps.
- No external fetch.
- No impact to existing computation logic (read-only rendering).
- If inputs unchanged => report.md unchanged => avoids meaningless commits.
- Still safe for workflow mtime check (file is always written by this run; content may be identical).

Inputs:
- --latest-report roll25_cache/latest_report.json
- --stats        roll25_cache/stats_latest.json (optional but recommended)
Output:
- --out          roll25_cache/report.md

Notes:
- Uses latest_report["generated_at"] as the "version stamp" (data-derived), not runtime.
- Focuses on "成交量狀況" readability:
  - TradeValue (TWD)
  - VolMultiplier / VolumeMultiplier vs threshold (from latest_report.signal)
  - TradeValue stats (z/p) from stats_latest.json if available
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Tuple


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _fmt_int(n: Any) -> str:
    if isinstance(n, bool):
        return "NA"
    if isinstance(n, int):
        return f"{n:,}"
    if isinstance(n, float) and n.is_integer():
        return f"{int(n):,}"
    return "NA"


def _fmt_float(x: Any, nd: int = 6) -> str:
    if isinstance(x, bool):
        return "NA"
    if isinstance(x, (int, float)):
        return f"{float(x):.{nd}f}"
    return "NA"


def _fmt_pct(x: Any, nd: int = 3) -> str:
    s = _fmt_float(x, nd=nd)
    return "NA" if s == "NA" else f"{s}%"


def _fmt_bool(x: Any) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    return "NA"


def _extract_stats_trade_value(stats: Dict[str, Any]) -> Dict[str, Any]:
    # Expected:
    # stats["series"]["trade_value"]["win60"] = {value, z, p, window_n_actual...}
    tv = _safe_get(stats, "series", "trade_value")
    if not isinstance(tv, dict):
        return {"ok": False}

    win60 = tv.get("win60") if isinstance(tv.get("win60"), dict) else None
    win252 = tv.get("win252") if isinstance(tv.get("win252"), dict) else None

    def pull(win: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(win, dict):
            return {"value": None, "z": None, "p": None, "n_actual": None, "n_target": None}
        return {
            "value": win.get("value"),
            "z": win.get("z"),
            "p": win.get("p"),
            "n_actual": win.get("window_n_actual"),
            "n_target": win.get("window_n_target"),
        }

    return {
        "ok": True,
        "asof": tv.get("asof"),
        "win60": pull(win60),
        "win252": pull(win252),
        "n_total_available": _safe_get(tv, "window_note", "n_total_available"),
    }


def _interpret_volume(mult: Any, threshold: Any, tv_stats: Dict[str, Any]) -> str:
    """
    Deterministic interpretation, conservative:
    - primary: vol_multiplier vs threshold (if available)
    - secondary: z/p of TradeValue (if available)
    """
    lines = []

    # Primary rule: multiplier
    if isinstance(mult, (int, float)) and isinstance(threshold, (int, float)):
        m = float(mult)
        th = float(threshold)
        if m >= th:
            lines.append(f"- 依倍數判讀：vol_multiplier={m:.3f} ≥ {th:.3f} → **放量（觸發門檻）**")
        else:
            lines.append(f"- 依倍數判讀：vol_multiplier={m:.3f} < {th:.3f} → **未達放量門檻**")
    elif isinstance(mult, (int, float)):
        lines.append(f"- 依倍數判讀：vol_multiplier={float(mult):.3f}，但缺少 threshold → **無法用門檻判斷**")
    else:
        lines.append("- 依倍數判讀：vol_multiplier=NA → **無法用門檻判斷**")

    # Secondary: z/p (60D/252D)
    if tv_stats.get("ok") is True:
        w60 = tv_stats.get("win60", {})
        w252 = tv_stats.get("win252", {})
        z60 = w60.get("z")
        p60 = w60.get("p")
        z252 = w252.get("z")
        p252 = w252.get("p")

        # Only interpret if present
        hint = []
        if isinstance(z60, (int, float)) or isinstance(p60, (int, float)):
            hint.append(f"60D z={_fmt_float(z60, 3)}, p={_fmt_float(p60, 1)}")
        if isinstance(z252, (int, float)) or isinstance(p252, (int, float)):
            hint.append(f"252D z={_fmt_float(z252, 3)}, p={_fmt_float(p252, 1)}")
        if hint:
            lines.append(f"- 位階參考（TradeValue）：{'; '.join(hint)}")
        else:
            lines.append("- 位階參考（TradeValue）：z/p 皆為 NA")
    else:
        lines.append("- 位階參考（TradeValue）：stats_latest.json 缺失或格式不符 → NA")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest-report", default="roll25_cache/latest_report.json")
    ap.add_argument("--stats", default="roll25_cache/stats_latest.json")
    ap.add_argument("--out", default="roll25_cache/report.md")
    args = ap.parse_args()

    latest = _load_json(args.latest_report)
    stats: Optional[Dict[str, Any]] = None
    if os.path.exists(args.stats):
        try:
            s = _load_json(args.stats)
            stats = s if isinstance(s, dict) else None
        except Exception:
            stats = None

    if not isinstance(latest, dict):
        raise SystemExit("[FATAL] latest_report.json is not a JSON object.")

    gen_at = latest.get("generated_at") if isinstance(latest.get("generated_at"), str) else "NA"
    tz = latest.get("timezone") if isinstance(latest.get("timezone"), str) else "NA"
    summary = latest.get("summary") if isinstance(latest.get("summary"), str) else "NA"

    nums = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    sig = latest.get("signal") if isinstance(latest.get("signal"), dict) else {}

    used_date = nums.get("UsedDate") if isinstance(nums.get("UsedDate"), str) else latest.get("used_date")
    if not isinstance(used_date, str):
        used_date = "NA"

    trade_value = nums.get("TradeValue")
    vol_mult = nums.get("VolMultiplier")
    vol_mult2 = nums.get("VolumeMultiplier")
    # prefer VolMultiplier if present
    vol_multiplier = vol_mult if isinstance(vol_mult, (int, float)) else vol_mult2

    pct_change = nums.get("PctChange")
    amp_pct = nums.get("AmplitudePct")
    close = nums.get("Close")

    used_date_status = sig.get("UsedDateStatus") if isinstance(sig.get("UsedDateStatus"), str) else latest.get("used_date_status")
    if not isinstance(used_date_status, str):
        used_date_status = "NA"

    run_day_tag = sig.get("RunDayTag") if isinstance(sig.get("RunDayTag"), str) else latest.get("run_day_tag")
    if not isinstance(run_day_tag, str):
        run_day_tag = "NA"

    ohlc_missing = sig.get("OhlcMissing")
    volume_amplified = sig.get("VolumeAmplified")
    vol_threshold = sig.get("VolThreshold")

    newlow_n = sig.get("NewLow_N")
    cons_break = sig.get("ConsecutiveBreak")
    down_day = sig.get("DownDay")

    lookback_target = nums.get("LookbackNTarget")
    lookback_actual = nums.get("LookbackNActual")

    freshness_ok = latest.get("freshness_ok")
    freshness_age_days = latest.get("freshness_age_days")
    mode = latest.get("mode")
    ohlc_status = latest.get("ohlc_status")

    tv_stats = _extract_stats_trade_value(stats) if isinstance(stats, dict) else {"ok": False}

    # Build deterministic report (no runtime stamp)
    lines = []
    lines.append("# TWSE Roll25 (Turnover) Report")
    lines.append("")
    lines.append("## 1) Audit Header")
    lines.append(f"- source_latest_report: `{args.latest_report}`")
    lines.append(f"- source_stats_latest: `{args.stats}`")
    lines.append(f"- latest_report.generated_at: `{gen_at}`")
    lines.append(f"- timezone: `{tz}`")
    lines.append(f"- UsedDate (data date): `{used_date}`")
    lines.append(f"- run_day_tag (from latest_report): `{run_day_tag}`")
    lines.append(f"- used_date_status: `{used_date_status}`")
    lines.append("")

    lines.append("## 2) Summary (from latest_report)")
    lines.append(f"- `{summary}`")
    lines.append("")

    lines.append("## 3) 成交量狀況（可讀版）")
    lines.append(f"- Turnover (TradeValue, TWD): `{_fmt_int(trade_value)}`")
    lines.append(f"- vol_multiplier (20D avg): `{_fmt_float(vol_multiplier, 3)}`")
    lines.append(f"- vol_threshold: `{_fmt_float(vol_threshold, 3)}`")
    lines.append(f"- signals.VolumeAmplified: `{_fmt_bool(volume_amplified)}`")
    lines.append("")
    lines.append("### 3.1 判斷邏輯（固定規則、無猜測）")
    lines.append(_interpret_volume(vol_multiplier, vol_threshold, tv_stats))
    lines.append("")

    lines.append("## 4) 價格/波動概況")
    lines.append(f"- Close: `{_fmt_float(close, 2)}`")
    lines.append(f"- PctChange (D vs D-1): `{_fmt_pct(pct_change, 3)}`")
    lines.append(f"- AmplitudePct (High-Low vs prev close): `{_fmt_pct(amp_pct, 3)}`")
    lines.append(f"- signals.DownDay: `{_fmt_bool(down_day)}`")
    lines.append("")

    lines.append("## 5) 市場行為 Signals（供 cross_module / heated_market 用）")
    lines.append(f"- signals.NewLow_N: `{_fmt_int(newlow_n)}`")
    lines.append(f"- signals.ConsecutiveBreak: `{_fmt_int(cons_break)}`")
    lines.append("")
    lines.append("> 解讀提醒：NewLow_N=0 表示未創近 N 日新低；ConsecutiveBreak=0 表示未出現連續下跌（日報酬<0）延伸。")
    lines.append("")

    lines.append("## 6) Data Quality / Confidence 線索")
    lines.append(f"- ohlc_status: `{ohlc_status if isinstance(ohlc_status, str) else 'NA'}`")
    lines.append(f"- signals.OhlcMissing: `{_fmt_bool(ohlc_missing)}`")
    lines.append(f"- freshness_ok: `{_fmt_bool(freshness_ok)}`")
    lines.append(f"- freshness_age_days: `{_fmt_int(freshness_age_days)}`")
    lines.append(f"- mode: `{mode if isinstance(mode, str) else 'NA'}`")
    lines.append(f"- LookbackNActual/Target: `{_fmt_int(lookback_actual)}/{_fmt_int(lookback_target)}`")
    lines.append("")

    lines.append("## 7) TradeValue 位階（stats_latest.json）")
    if tv_stats.get("ok") is True:
        w60 = tv_stats["win60"]
        w252 = tv_stats["win252"]
        lines.append(f"- asof: `{tv_stats.get('asof')}`")
        lines.append(f"- 60D: value={_fmt_float(w60.get('value'), 3)}, z={_fmt_float(w60.get('z'), 3)}, p={_fmt_float(w60.get('p'), 1)}, n={_fmt_int(w60.get('n_actual'))}/{_fmt_int(w60.get('n_target'))}")
        lines.append(f"- 252D: value={_fmt_float(w252.get('value'), 3)}, z={_fmt_float(w252.get('z'), 3)}, p={_fmt_float(w252.get('p'), 1)}, n={_fmt_int(w252.get('n_actual'))}/{_fmt_int(w252.get('n_target'))}")
        lines.append(f"- points_total_available(trade_value): `{_fmt_int(tv_stats.get('n_total_available'))}`")
    else:
        lines.append("- NA (stats_latest.json missing/invalid)")
    lines.append("")

    lines.append("## 8) Notes (deterministic)")
    lines.append("- 本報告不含任何 runtime timestamp，僅以 latest_report.generated_at 代表資料版本。")
    lines.append("- 本報告僅做可讀化彙整，不改變 roll25_cache 的任何運算結果。")
    lines.append("")

    text = "\n".join(lines)
    _atomic_write_text(args.out, text)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())