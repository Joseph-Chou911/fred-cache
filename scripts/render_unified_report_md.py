#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render unified_dashboard/latest.json into report.md

Adds:
- roll25_derived (realized vol / max drawdown)
- fx_usdtwd section (BOT USD/TWD mid + deterministic signal)

This renderer does NOT recompute; it only formats fields already in unified JSON.
If a field is missing => prints NA.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _fmt(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return f"{x:.{nd}f}"
    return str(x)


def _fmt_int(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="unified_dashboard/latest.json")
    ap.add_argument("--out", dest="out_path", default="report.md")
    args = ap.parse_args()

    uni = _load_json(args.in_path)
    rendered_at_utc = _now_utc_z()

    modules = uni.get("modules", {}) if isinstance(uni, dict) else {}
    market = modules.get("market_cache", {})
    fred = modules.get("fred_cache", {})
    roll25 = modules.get("roll25_cache", {})
    twm = modules.get("taiwan_margin_financing", {})
    fx = modules.get("fx_usdtwd", {})

    lines: List[str] = []
    lines.append("# Unified Risk Dashboard Report\n")

    # Module status
    lines.append("## Module Status")
    lines.append(f"- market_cache: {_safe_get(market,'status') or 'NA'}")
    lines.append(f"- fred_cache: {_safe_get(fred,'status') or 'NA'}")
    lines.append(f"- roll25_cache: {_safe_get(roll25,'status') or 'NA'}")
    lines.append(f"- taiwan_margin_financing: {_safe_get(twm,'status') or 'NA'}")
    lines.append(f"- fx_usdtwd: {_safe_get(fx,'status') or 'NA'}")
    lines.append(f"- unified_generated_at_utc: {uni.get('generated_at_utc','NA')}\n")

    # market_cache detailed (reuse your existing style; minimal fields)
    m_dash = _safe_get(market, "dashboard_latest") or {}
    m_meta = _safe_get(m_dash, "meta") or {}
    m_rows = _safe_get(m_dash, "rows") or []
    lines.append("## market_cache (detailed)")
    lines.append(f"- as_of_ts: {m_meta.get('stats_as_of_ts','NA')}")
    lines.append(f"- run_ts_utc: {m_meta.get('run_ts_utc','NA')}")
    lines.append(f"- ruleset_id: {m_meta.get('ruleset_id','NA')}")
    lines.append(f"- script_fingerprint: {m_meta.get('script_fingerprint','NA')}")
    lines.append(f"- script_version: {m_meta.get('script_version','NA')}")
    lines.append(f"- series_count: {m_meta.get('series_count','NA')}\n")

    if isinstance(m_rows, list) and m_rows:
        hdr = ["series","signal","dir","market_class","value","data_date","age_h","z60","p60","p252","zΔ60","pΔ60","ret1%60","reason","tag","prev","delta","streak_hist","streak_wa","source"]
        rws: List[List[str]] = []
        for it in m_rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag","NA")
            mclass = "NONE"
            if isinstance(tag, str):
                if "LONG_EXTREME" in tag:
                    mclass = "LONG"
                if "EXTREME_Z" in tag:
                    mclass = "LEVEL" if mclass == "NONE" else f"{mclass}+LEVEL"
                if "JUMP" in tag:
                    mclass = "JUMP" if mclass == "NONE" else f"{mclass}+JUMP"
            rws.append([
                str(it.get("series","NA")),
                str(it.get("signal_level","NA")),
                str(it.get("dir","NA")),
                mclass,
                _fmt(it.get("value"),6),
                str(it.get("data_date","NA")),
                _fmt(it.get("age_hours"),6),
                _fmt(it.get("z60"),6),
                _fmt(it.get("p60"),6),
                _fmt(it.get("p252"),6),
                _fmt(it.get("z_delta60"),6),
                _fmt(it.get("p_delta60"),6),
                _fmt(it.get("ret1_pct60"),6),
                str(it.get("reason","NA")),
                str(tag),
                str(it.get("prev_signal","NA")),
                str(it.get("delta_signal","NA")),
                _fmt_int(it.get("streak_hist")),
                _fmt_int(it.get("streak_wa")),
                str(it.get("source_url","NA")),
            ])
        lines.append(_md_table(hdr, rws))
        lines.append("")

    # fred_cache
    f_dash = _safe_get(fred, "dashboard_latest") or {}
    f_meta = _safe_get(f_dash, "meta") or {}
    f_rows = _safe_get(f_dash, "rows") or []
    lines.append("## fred_cache (ALERT+WATCH+INFO)")
    lines.append(f"- as_of_ts: {f_meta.get('stats_as_of_ts','NA')}")
    lines.append(f"- run_ts_utc: {f_meta.get('run_ts_utc','NA')}")
    lines.append(f"- ruleset_id: {f_meta.get('ruleset_id','NA')}")
    lines.append(f"- script_fingerprint: {f_meta.get('script_fingerprint','NA')}")
    lines.append(f"- script_version: {f_meta.get('script_version','NA')}")
    summ = f_meta.get("summary", {})
    if isinstance(summ, dict):
        lines.append(f"- ALERT: {summ.get('ALERT','NA')}")
        lines.append(f"- WATCH: {summ.get('WATCH','NA')}")
        lines.append(f"- INFO: {summ.get('INFO','NA')}")
        lines.append(f"- NONE: {summ.get('NONE','NA')}")
        lines.append(f"- CHANGED: {summ.get('CHANGED','NA')}\n")
    else:
        lines.append("")

    # Keep your full-table behavior: print all rows
    if isinstance(f_rows, list) and f_rows:
        hdr = ["series","signal","fred_dir","fred_class","value","data_date","age_h","z60","p60","p252","zΔ60","pΔ60","ret1%","reason","tag","prev","delta","source"]
        rws: List[List[str]] = []
        for it in f_rows:
            if not isinstance(it, dict):
                continue
            tag = it.get("tag","NA")
            fclass = "NONE"
            if isinstance(tag, str):
                if "LONG_EXTREME" in tag:
                    fclass = "LONG"
                elif "EXTREME_Z" in tag:
                    fclass = "LEVEL"
                elif "JUMP" in tag:
                    fclass = "JUMP"
            rws.append([
                str(it.get("series","NA")),
                str(it.get("signal_level","NA")),
                str(it.get("fred_dir","NA")),
                fclass,
                _fmt(it.get("value"),6),
                str(it.get("data_date","NA")),
                _fmt(it.get("age_hours"),6),
                _fmt(it.get("z60"),6),
                _fmt(it.get("p60"),6),
                _fmt(it.get("p252"),6),
                _fmt(it.get("z_delta_60"),6),
                _fmt(it.get("p_delta_60"),6),
                _fmt(it.get("ret1_pct"),6),
                str(it.get("reason","NA")),
                str(tag),
                str(it.get("prev_signal","NA")),
                str(it.get("delta_signal","NA")),
                str(it.get("source_url","NA")),
            ])
        lines.append(_md_table(hdr, rws))
        lines.append("")

    # roll25_cache (core fields from latest report)
    r_latest = _safe_get(roll25, "latest_report") or {}
    r_core = _safe_get(roll25, "core") or {}  # if you still have core elsewhere, keep NA
    if not r_core and isinstance(r_latest, dict):
        # derive minimal core from report itself
        nums = r_latest.get("numbers", {}) if isinstance(r_latest.get("numbers"), dict) else {}
        sigs = r_latest.get("signal", {}) if isinstance(r_latest.get("signal"), dict) else {}
        r_core = {
            "UsedDate": nums.get("UsedDate") or r_latest.get("used_date"),
            "tag": r_latest.get("tag"),
            "risk_level": r_latest.get("risk_level"),
            "turnover_twd": nums.get("TradeValue"),
            "turnover_unit": "TWD",
            "volume_multiplier": nums.get("VolumeMultiplier"),
            "vol_multiplier": nums.get("VolMultiplier"),
            "amplitude_pct": nums.get("AmplitudePct"),
            "pct_change": nums.get("PctChange"),
            "close": nums.get("Close"),
            "signals": sigs,
            "LookbackNTarget": 20,
            "LookbackNActual": r_latest.get("lookback_n_actual"),
        }

    lines.append("## roll25_cache (TW turnover)")
    lines.append(f"- status: {_safe_get(roll25,'status') or 'NA'}")
    lines.append(f"- UsedDate: {_fmt(r_core.get('UsedDate'),0)}")
    lines.append(f"- tag: {r_core.get('tag','NA')}")
    lines.append(f"- risk_level: {r_core.get('risk_level','NA')}")
    lines.append(f"- turnover_twd: {_fmt(r_core.get('turnover_twd'),0)}")
    lines.append(f"- turnover_unit: {r_core.get('turnover_unit','NA')}")
    lines.append(f"- volume_multiplier: {_fmt(r_core.get('volume_multiplier'),3)}")
    lines.append(f"- vol_multiplier: {_fmt(r_core.get('vol_multiplier'),3)}")
    lines.append(f"- amplitude_pct: {_fmt(r_core.get('amplitude_pct'),3)}")
    lines.append(f"- pct_change: {_fmt(r_core.get('pct_change'),3)}")
    lines.append(f"- close: {_fmt(r_core.get('close'),2)}")
    lines.append(f"- LookbackNTarget: {_fmt_int(r_core.get('LookbackNTarget'))}")
    lines.append(f"- LookbackNActual: {_fmt_int(r_core.get('LookbackNActual'))}")

    sigs = r_core.get("signals", {})
    if isinstance(sigs, dict):
        for k in ["DownDay","VolumeAmplified","VolAmplified","NewLow_N","ConsecutiveBreak","OhlcMissing"]:
            lines.append(f"- signals.{k}: {_fmt(sigs.get(k),0)}")
    lines.append("")

    # roll25 derived
    r_der = _safe_get(roll25, "derived") or {}
    lines.append("### roll25_derived (realized vol / drawdown)")
    lines.append(f"- status: {r_der.get('status','NA')}")
    params = r_der.get("params", {}) if isinstance(r_der.get("params"), dict) else {}
    lines.append(f"- vol_n: {_fmt_int(params.get('vol_n'))}")
    lines.append(f"- realized_vol_N_annualized_pct: {_fmt(r_der.get('realized_vol_N_annualized_pct'),6)}")
    lines.append(f"- realized_vol_points_used: {_fmt_int(r_der.get('realized_vol_points_used'))}")
    lines.append(f"- dd_n: {_fmt_int(params.get('dd_n'))}")
    lines.append(f"- max_drawdown_N_pct: {_fmt(r_der.get('max_drawdown_N_pct'),6)}")
    lines.append(f"- max_drawdown_points_used: {_fmt_int(r_der.get('max_drawdown_points_used'))}")
    lines.append(f"- confidence: {r_der.get('confidence','NA')}")
    lines.append("")

    # fx section
    fx_der = _safe_get(fx, "derived") or {}
    lines.append("## FX (USD/TWD)")
    lines.append(f"- status: {_safe_get(fx,'status') or 'NA'}")
    lines.append(f"- data_date: {fx_der.get('data_date','NA')}")
    lines.append(f"- source_url: {fx_der.get('source_url','NA')}")
    usd = fx_der.get("usd_twd", {}) if isinstance(fx_der.get("usd_twd"), dict) else {}
    lines.append(f"- spot_buy: {_fmt(usd.get('spot_buy'),6)}")
    lines.append(f"- spot_sell: {_fmt(usd.get('spot_sell'),6)}")
    lines.append(f"- mid: {_fmt(usd.get('mid'),6)}")
    mom = fx_der.get("momentum", {}) if isinstance(fx_der.get("momentum"), dict) else {}
    lines.append(f"- ret1_pct: {_fmt(mom.get('ret1_pct'),6)} (from {mom.get('ret1_from','NA')} to {mom.get('ret1_to','NA')})")
    lines.append(f"- chg_5d_pct: {_fmt(mom.get('chg_5d_pct'),6)} (from {mom.get('chg_5d_from','NA')} to {mom.get('chg_5d_to','NA')})")
    lines.append(f"- dir: {fx_der.get('dir','NA')}")
    lines.append(f"- fx_signal: {fx_der.get('fx_signal','NA')}")
    lines.append(f"- fx_reason: {fx_der.get('fx_reason','NA')}")
    lines.append(f"- fx_confidence: {fx_der.get('fx_confidence','NA')}")
    lines.append("")

    # taiwan margin financing (keep your existing; minimal print)
    tw_latest = _safe_get(twm, "latest") or {}
    lines.append("## taiwan_margin_financing (TWSE/TPEX)")
    lines.append(f"- status: {_safe_get(twm,'status') or 'NA'}")
    lines.append(f"- schema_version: {tw_latest.get('schema_version','NA')}")
    lines.append(f"- generated_at_utc: {tw_latest.get('generated_at_utc','NA')}")
    lines.append("")

    # footer
    lines.append(f"<!-- rendered_at_utc: {rendered_at_utc} -->\n")

    text = "\n".join(lines)
    with open(args.out_path, "w", encoding="utf-8") as f:
        f.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())