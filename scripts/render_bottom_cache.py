#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from zoneinfo import ZoneInfo

TZ_TPE = ZoneInfo("Asia/Taipei")

# ---- config ----
MARKET_STATS_PATH = "market_cache/stats_latest.json"

# ✅ unified output folder (all artifacts here)
OUT_DIR = "dashboard_bottom_cache"
OUT_LATEST = f"{OUT_DIR}/latest.json"
OUT_HISTORY = f"{OUT_DIR}/history.json"
OUT_MD = f"{OUT_DIR}/report.md"

NEEDED = ["VIX", "SP500", "HYG_IEF_RATIO", "OFR_FSI"]

# risk direction is a RULE (not guessed)
RISK_DIR = {
    "VIX": "HIGH",
    "OFR_FSI": "HIGH",
    "HYG_IEF_RATIO": "LOW",
    "SP500": "LOW",
}

# v0 thresholds (audit-friendly, deterministic)
TH_VIX = 20.0
TH_SPX_RET1 = -1.5          # unit: percent (%)
TH_HYG_VETO_Z = -2.0
TH_OFR_VETO_Z = 2.0


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tpe_now() -> str:
    return datetime.now(TZ_TPE).isoformat()


def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None


def _as_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x)
    if s.strip() == "" or s.strip().upper() == "NA":
        return None
    return s


def _get(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _series_signal(z60: Optional[float], p252: Optional[float]) -> Optional[str]:
    # Align with your system style (Extreme z, Percentile extremes)
    if z60 is None and p252 is None:
        return None
    if z60 is not None and abs(z60) >= 2.5:
        return "ALERT"
    if z60 is not None and abs(z60) >= 2.0:
        return "WATCH"
    if p252 is not None and (p252 >= 95.0 or p252 <= 5.0):
        return "INFO"
    return "NONE"


def _fmt(x: Any, nd: int = 4) -> str:
    if x is None:
        return "NA"
    try:
        if isinstance(x, float):
            return f"{x:.{nd}f}"
        return str(x)
    except Exception:
        return "NA"


def _day_key_tpe(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_TPE)
        return dt.date().isoformat()
    except Exception:
        return "NA"


def main() -> None:
    run_ts_utc = _utc_now()
    as_of_ts_tpe = _tpe_now()
    git_sha = os.environ.get("GITHUB_SHA", "NA")

    excluded: List[Dict[str, str]] = []

    # ---- read market_cache stats ----
    try:
        root = _read_json(MARKET_STATS_PATH)
        ok_market = True
    except Exception as e:
        root = {}
        ok_market = False
        excluded.append({"trigger": "ALL", "reason": f"read_or_parse_failed:{type(e).__name__}"})

    meta = {
        "generated_at_utc": _as_str(root.get("generated_at_utc")),
        "as_of_ts": _as_str(root.get("as_of_ts")),
        "script_version": _as_str(root.get("script_version")),
        "ret1_mode": _as_str(root.get("ret1_mode")),
        "percentile_method": _as_str(root.get("percentile_method")),
    }

    series_root = root.get("series") if isinstance(root.get("series"), dict) else {}

    # ---- extract series snapshots ----
    series_out: Dict[str, Any] = {}
    for sid in NEEDED:
        s = series_root.get(sid, {}) if isinstance(series_root, dict) else {}
        latest = s.get("latest") if isinstance(s.get("latest"), dict) else {}
        w60 = _get(s, ["windows", "w60"]) if isinstance(_get(s, ["windows", "w60"]), dict) else {}
        w252 = _get(s, ["windows", "w252"]) if isinstance(_get(s, ["windows", "w252"]), dict) else {}

        z60 = _as_float(w60.get("z"))
        p252 = _as_float(w252.get("p"))

        sig = _series_signal(z60, p252)

        series_out[sid] = {
            "series_id": sid,
            "risk_dir": RISK_DIR.get(sid, "NA"),
            "latest": {
                "data_date": _as_str(latest.get("data_date")),
                "value": _as_float(latest.get("value")),
                "as_of_ts": _as_str(latest.get("as_of_ts")) or meta["as_of_ts"] or "NA",
                "source_url": _as_str(latest.get("source_url")) or "NA",
            },
            "w60": {
                "z": z60,
                "p": _as_float(w60.get("p")),
                "ret1_pct": _as_float(w60.get("ret1_pct")),  # unit = percent (%)
                "z_delta": _as_float(w60.get("z_delta")),
                "p_delta": _as_float(w60.get("p_delta")),
            },
            "w252": {
                "z": _as_float(w252.get("z")),
                "p": p252,
            },
            "series_signal": sig or "NA",
        }

    # ---- triggers ----
    # TRIG_PANIC: VIX>=20 OR SP500 ret1%<=-1.5
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]  # unit %
    trig_panic: Optional[int] = None

    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and vix_val >= TH_VIX)
        cond_spx = (spx_ret1 is not None and spx_ret1 <= TH_SPX_RET1)
        trig_panic = 1 if (cond_vix or cond_spx) else 0

    # TRIG_SYSTEMIC_VETO: veto if credit/systemic stress present
    hyg_z = series_out["HYG_IEF_RATIO"]["w60"]["z"]
    hyg_sig = series_out["HYG_IEF_RATIO"]["series_signal"]
    ofr_z = series_out["OFR_FSI"]["w60"]["z"]
    ofr_sig = series_out["OFR_FSI"]["series_signal"]

    trig_veto: Optional[int] = None
    hyg_can = (hyg_z is not None and hyg_sig in ("WATCH", "ALERT"))
    ofr_can = (ofr_z is not None and ofr_sig in ("WATCH", "ALERT"))

    if (hyg_z is None and ofr_z is None):
        excluded.append({"trigger": "TRIG_SYSTEMIC_VETO", "reason": "missing_fields:HYG_IEF_RATIO.w60.z & OFR_FSI.w60.z"})
    else:
        # conservative OR on available parts
        hyg_veto = 1 if (hyg_can and hyg_z is not None and hyg_z <= TH_HYG_VETO_Z) else 0
        ofr_veto = 1 if (ofr_can and ofr_z is not None and ofr_z >= TH_OFR_VETO_Z) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    # TRIG_REVERSAL: only evaluated when panic==1 and veto==0
    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        # VIX cooling: first available metric must be negative
        vix_cooling: Optional[int] = None
        for x in (vix_ret1, vix_zd, vix_pd):
            if x is not None:
                vix_cooling = 1 if x < 0 else 0
                break

        # SP500 stable: ret1% >= 0
        spx_stab: Optional[int] = None
        if spx_ret1 is not None:
            spx_stab = 1 if spx_ret1 >= 0 else 0

        if vix_cooling is None or spx_stab is None:
            miss = []
            if vix_cooling is None:
                miss.append("VIX(w60.ret1_pct/z_delta/p_delta)")
            if spx_stab is None:
                miss.append("SP500(w60.ret1_pct)")
            excluded.append({"trigger": "TRIG_REVERSAL", "reason": "missing_fields:" + "&".join(miss)})
        else:
            trig_rev = 1 if (vix_cooling == 1 and spx_stab == 1) else 0

    # ---- bottom_state ----
    bottom_state = "NA"
    if trig_panic == 0:
        bottom_state = "NONE"
    elif trig_panic == 1:
        if trig_veto == 1:
            bottom_state = "PANIC_BUT_SYSTEMIC"
        elif trig_veto == 0:
            bottom_state = "BOTTOM_CANDIDATE" if trig_rev == 1 else "BOTTOM_WATCH"
        else:
            # veto NA -> conservative
            bottom_state = "BOTTOM_WATCH"
    else:
        bottom_state = "NA"

    # ---- latest.json (unified output) ----
    latest_out = {
        "schema_version": "bottom_cache_v1",
        "generated_at_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "inputs": {
            "market_cache_stats_path": MARKET_STATS_PATH,
            "market_cache_ok": ok_market,
            "market_cache_generated_at_utc": meta["generated_at_utc"] or "NA",
            "market_cache_as_of_ts": meta["as_of_ts"] or "NA",
            "market_cache_script_version": meta["script_version"] or "NA",
            "market_cache_ret1_mode": meta["ret1_mode"] or "NA",
            "market_cache_percentile_method": meta["percentile_method"] or "NA",
        },
        "bottom_state": bottom_state,
        "triggers": {
            "TRIG_PANIC": trig_panic,
            "TRIG_SYSTEMIC_VETO": trig_veto,
            "TRIG_REVERSAL": trig_rev,
        },
        "excluded_triggers": excluded,
        "series": series_out,
        "thresholds_v0": {
            "VIX_panic_ge": TH_VIX,
            "SP500_ret1_panic_le_pct": TH_SPX_RET1,
            "HYG_IEF_RATIO_veto_z_le": TH_HYG_VETO_Z,
            "OFR_FSI_veto_z_ge": TH_OFR_VETO_Z,
        },
        "notes": [
            "v0: single source = market_cache/stats_latest.json",
            "series_signal derived from w60.z and w252.p using deterministic thresholds",
            "ret1_pct unit is percent (%)",
            "outputs unified into dashboard_bottom_cache/{latest.json,history.json,report.md}",
        ],
    }
    _write_json(OUT_LATEST, latest_out)

    # ---- history append (overwrite same TPE day bucket) ----
    hist = {"schema_version": "bottom_history_v1", "items": []}
    if os.path.exists(OUT_HISTORY):
        try:
            hist = _read_json(OUT_HISTORY)
            if not isinstance(hist, dict) or "items" not in hist or not isinstance(hist.get("items"), list):
                hist = {"schema_version": "bottom_history_v1", "items": []}
        except Exception:
            hist = {"schema_version": "bottom_history_v1", "items": []}

    item = {
        "run_ts_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "bottom_state": bottom_state,
        "triggers": latest_out["triggers"],
        "series_signals": {sid: series_out[sid]["series_signal"] for sid in NEEDED},
    }

    dk = _day_key_tpe(as_of_ts_tpe)
    new_items = [it for it in hist.get("items", []) if _day_key_tpe(it.get("as_of_ts", "NA")) != dk]
    new_items.append(item)
    hist["items"] = new_items
    _write_json(OUT_HISTORY, hist)

    # ---- report.md (enhanced, distinct) ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state: **{bottom_state}**\n\n")

    # rationale chain
    md.append("## Rationale (Decision Chain)\n")
    md.append(f"- TRIG_PANIC = `{trig_panic}`  (VIX >= {TH_VIX} OR SP500.ret1% <= {TH_SPX_RET1})\n")
    md.append(f"- TRIG_SYSTEMIC_VETO = `{trig_veto}`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)\n")
    md.append(f"- TRIG_REVERSAL = `{trig_rev}`  (panic & NOT systemic & VIX cooling & SP500 stable)\n")
    if trig_panic == 0:
        md.append("- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）\n")
    elif trig_panic == 1 and trig_veto == 1:
        md.append("- 因 TRIG_SYSTEMIC_VETO=1 → 不抄底（系統性壓力）\n")
    elif trig_panic == 1 and trig_veto == 0 and trig_rev == 1:
        md.append("- panic 且非系統性，並出現冷卻/穩定 → BOTTOM_CANDIDATE\n")
    elif trig_panic == 1 and trig_veto == 0 and trig_rev == 0:
        md.append("- panic 且非系統性，但尚未冷卻/穩定 → BOTTOM_WATCH\n")
    else:
        md.append("- 條件缺失/NA → 保守處理\n")
    md.append("\n")

    # distance-to-trigger (why NONE / how far)
    md.append("## Distance to Triggers (How far from activation)\n")
    if vix_val is not None:
        md.append(f"- VIX panic gap = {TH_VIX} - {vix_val} = **{_fmt(TH_VIX - vix_val, 4)}**  (<=0 means triggered)\n")
    else:
        md.append("- VIX panic gap = NA (missing VIX.latest.value)\n")

    if spx_ret1 is not None:
        md.append(f"- SP500 ret1% gap = {spx_ret1} - ({TH_SPX_RET1}) = **{_fmt(spx_ret1 - TH_SPX_RET1, 4)}**  (<=0 means triggered)\n")
    else:
        md.append("- SP500 ret1% gap = NA (missing SP500.w60.ret1_pct)\n")

    if hyg_z is not None:
        md.append(f"- HYG veto gap (z) = {hyg_z} - ({TH_HYG_VETO_Z}) = **{_fmt(hyg_z - TH_HYG_VETO_Z, 4)}**  (<=0 means systemic veto)\n")
    else:
        md.append("- HYG veto gap (z) = NA (missing HYG_IEF_RATIO.w60.z)\n")

    if ofr_z is not None:
        md.append(f"- OFR veto gap (z) = ({TH_OFR_VETO_Z}) - {ofr_z} = **{_fmt(TH_OFR_VETO_Z - ofr_z, 4)}**  (<=0 means systemic veto)\n")
    else:
        md.append("- OFR veto gap (z) = NA (missing OFR_FSI.w60.z)\n")
    md.append("\n")

    # triggers block
    md.append("## Triggers (0/1/NA)\n")
    for k, v in latest_out["triggers"].items():
        md.append(f"- {k}: `{v}`\n")
    md.append("\n")

    # excluded / NA reasons
    if excluded:
        md.append("## Excluded / NA Reasons\n")
        for e in excluded:
            md.append(f"- {e['trigger']}: {e['reason']}\n")
        md.append("\n")

    # action map
    md.append("## Action Map (v0)\n")
    md.append("- NONE: 維持既定 DCA/資產配置紀律；不把它當成抄底時點訊號\n")
    md.append("- BOTTOM_WATCH: 只做準備（現金/分批計畫/撤退條件），不進場\n")
    md.append("- BOTTOM_CANDIDATE: 允許分批（例如 2–3 段），但需設定撤退條件\n")
    md.append("- PANIC_BUT_SYSTEMIC: 不抄底，先等信用/壓力解除\n")
    md.append("\n")

    # series snapshot
    md.append("## Series Snapshot\n")
    md.append("| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |\n")
    md.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|\n")
    for sid in NEEDED:
        s = series_out[sid]
        md.append(
            f"| {sid} | {s['risk_dir']} | {s['series_signal']} | {s['latest']['data_date'] or 'NA'} | "
            f"{s['latest']['value'] if s['latest']['value'] is not None else 'NA'} | "
            f"{s['w60']['z'] if s['w60']['z'] is not None else 'NA'} | "
            f"{s['w252']['p'] if s['w252']['p'] is not None else 'NA'} | "
            f"{s['w60']['ret1_pct'] if s['w60']['ret1_pct'] is not None else 'NA'} | "
            f"{s['w60']['z_delta'] if s['w60']['z_delta'] is not None else 'NA'} | "
            f"{s['w60']['p_delta'] if s['w60']['p_delta'] is not None else 'NA'} |\n"
        )

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()