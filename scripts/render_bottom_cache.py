#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottom_cache renderer (market_cache single-source) -> dashboard_bottom_cache/*

Outputs (all in ONE folder):
- dashboard_bottom_cache/latest.json
- dashboard_bottom_cache/history.json
- dashboard_bottom_cache/report.md

Design intent (v0+):
- Event-driven "bottom / reversal workflow" signal, not a daily "market state" dashboard.
- Deterministic rules only; no guessing; missing fields => NA + excluded reasons.
- Uses ONLY market_cache/stats_latest.json as the upstream source.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo

TZ_TPE = ZoneInfo("Asia/Taipei")

# ---- config ----
MARKET_STATS_PATH = "market_cache/stats_latest.json"

# ✅ single unified output folder
OUT_DIR = "dashboard_bottom_cache"
OUT_LATEST = f"{OUT_DIR}/latest.json"
OUT_HISTORY = f"{OUT_DIR}/history.json"
OUT_MD = f"{OUT_DIR}/report.md"

# what we need from market_cache
NEEDED = ["VIX", "SP500", "HYG_IEF_RATIO", "OFR_FSI"]

# risk direction is a RULE (not guessed)
RISK_DIR = {
    "VIX": "HIGH",
    "OFR_FSI": "HIGH",
    "HYG_IEF_RATIO": "LOW",
    "SP500": "LOW",
}

# v0 thresholds (keep deterministic)
TH_VIX_PANIC = 20.0
TH_SPX_RET1_PANIC = -1.5     # unit = percent (%)
TH_HYG_VETO_Z = -2.0         # systemic credit stress veto (LOW direction)
TH_OFR_VETO_Z = 2.0          # systemic stress veto (HIGH direction)
HISTORY_SHOW_N = 10          # for report only


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
    """
    Align with your system style:
    - Extreme z: WATCH/ALERT
    - Percentile extremes: INFO
    """
    if z60 is None and p252 is None:
        return None
    if z60 is not None and abs(z60) >= 2.5:
        return "ALERT"
    if z60 is not None and abs(z60) >= 2.0:
        return "WATCH"
    if p252 is not None and (p252 >= 95.0 or p252 <= 5.0):
        return "INFO"
    return "NONE"


def _day_key_tpe_from_iso(iso_ts: str) -> str:
    """
    Convert iso to TPE date key (YYYY-MM-DD). If parse fails -> "NA"
    """
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_TPE)
        return dt.date().isoformat()
    except Exception:
        return "NA"


def _safe_float_str(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    fmt = f"{{:.{nd}f}}"
    return fmt.format(x)


def _pick_first_available_change_pct_1d(series_out: Dict[str, Any], order: List[str]) -> Optional[float]:
    """
    Use existing w60.ret1_pct as the change metric (unit is percent % in your market_cache).
    This helper is for extensibility; currently bottom_cache v0 only uses SP500.
    """
    for sid in order:
        v = series_out.get(sid, {}).get("w60", {}).get("ret1_pct")
        if isinstance(v, (int, float)):
            return float(v)
    return None


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
                "as_of_ts": _as_str(latest.get("as_of_ts")) or meta["as_of_ts"],
                "source_url": _as_str(latest.get("source_url")) or "NA",
            },
            "w60": {
                "z": z60,
                "p": _as_float(w60.get("p")),
                "ret1_pct": _as_float(w60.get("ret1_pct")),   # unit = %
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
    # TRIG_PANIC: VIX >= 20 OR SP500.ret1% <= -1.5
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]  # unit %

    trig_panic: Optional[int] = None
    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and vix_val >= TH_VIX_PANIC)
        cond_spx = (spx_ret1 is not None and spx_ret1 <= TH_SPX_RET1_PANIC)
        trig_panic = 1 if (cond_vix or cond_spx) else 0

    # TRIG_SYSTEMIC_VETO: systemic stress veto via HYG_IEF_RATIO / OFR_FSI
    hyg_z = series_out["HYG_IEF_RATIO"]["w60"]["z"]
    hyg_sig = series_out["HYG_IEF_RATIO"]["series_signal"]
    ofr_z = series_out["OFR_FSI"]["w60"]["z"]
    ofr_sig = series_out["OFR_FSI"]["series_signal"]

    trig_veto: Optional[int] = None
    hyg_can = (hyg_z is not None and hyg_sig in ("WATCH", "ALERT"))
    ofr_can = (ofr_z is not None and ofr_sig in ("WATCH", "ALERT"))

    if hyg_z is None and ofr_z is None:
        excluded.append({"trigger": "TRIG_SYSTEMIC_VETO", "reason": "missing_fields:HYG_IEF_RATIO.w60.z & OFR_FSI.w60.z"})
    else:
        hyg_veto = 1 if (hyg_can and hyg_z <= TH_HYG_VETO_Z) else 0
        ofr_veto = 1 if (ofr_can and ofr_z >= TH_OFR_VETO_Z) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    # TRIG_REVERSAL: panic & NOT systemic & VIX cooling & SP500 stable
    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        # VIX cooling: any first available metric < 0
        vix_cooling: Optional[int] = None
        for x in (vix_ret1, vix_zd, vix_pd):
            if x is not None:
                vix_cooling = 1 if x < 0 else 0
                break

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
            bottom_state = "BOTTOM_WATCH"  # veto NA -> conservative
    else:
        bottom_state = "NA"

    # ---- context flags (non-trigger, but useful) ----
    spx_p252 = series_out["SP500"]["w252"]["p"]
    context_equity_extreme: Optional[int] = None
    if spx_p252 is None:
        context_equity_extreme = None
    else:
        context_equity_extreme = 1 if float(spx_p252) >= 95.0 else 0

    # ---- distances to trigger thresholds (<=0 means triggered) ----
    dist_vix_panic: Optional[float] = None
    if vix_val is not None:
        dist_vix_panic = TH_VIX_PANIC - float(vix_val)

    dist_spx_panic: Optional[float] = None
    if spx_ret1 is not None:
        dist_spx_panic = float(spx_ret1) - TH_SPX_RET1_PANIC  # <=0 triggers

    dist_hyg_veto: Optional[float] = None
    if hyg_z is not None:
        dist_hyg_veto = float(hyg_z) - TH_HYG_VETO_Z          # <=0 veto active (more negative)

    dist_ofr_veto: Optional[float] = None
    if ofr_z is not None:
        dist_ofr_veto = TH_OFR_VETO_Z - float(ofr_z)          # <=0 veto active (>=2)

    # ---- build latest.json ----
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
        "context": {
            "context_equity_extreme_sp500_p252_ge_95": context_equity_extreme,
            "sp500_p252": spx_p252 if spx_p252 is not None else None,
        },
        "distances": {
            "vix_panic_gap": dist_vix_panic,
            "sp500_ret1_panic_gap": dist_spx_panic,
            "hyg_veto_gap_z": dist_hyg_veto,
            "ofr_veto_gap_z": dist_ofr_veto,
        },
        "excluded_triggers": excluded,
        "series": series_out,
        "notes": [
            "v0: single source = market_cache/stats_latest.json",
            "signal derived from w60.z and w252.p using deterministic thresholds",
            "ret1_pct unit is percent (%)",
            "context fields do NOT change triggers; they are informational only"
        ],
    }

    _write_json(OUT_LATEST, latest_out)

    # ---- history.json append (overwrite same TPE day bucket) ----
    hist: Dict[str, Any] = {"schema_version": "bottom_history_v1", "items": []}
    if os.path.exists(OUT_HISTORY):
        try:
            tmp = _read_json(OUT_HISTORY)
            if isinstance(tmp, dict) and isinstance(tmp.get("items"), list):
                hist = tmp
        except Exception:
            hist = {"schema_version": "bottom_history_v1", "items": []}

    item = {
        "run_ts_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "bottom_state": bottom_state,
        "triggers": latest_out["triggers"],
        "context": latest_out["context"],
        "distances": latest_out["distances"],
        "series_signals": {sid: series_out[sid]["series_signal"] for sid in NEEDED},
    }

    dk = _day_key_tpe_from_iso(as_of_ts_tpe)
    old_items = hist.get("items", [])
    if not isinstance(old_items, list):
        old_items = []

    new_items = [it for it in old_items if _day_key_tpe_from_iso(_as_str(it.get("as_of_ts")) or "NA") != dk]
    new_items.append(item)
    hist["items"] = new_items
    _write_json(OUT_HISTORY, hist)

    # ---- analytics on history for report.md ----
    # Sort by as_of_ts (stable) for reporting
    items_sorted: List[Dict[str, Any]] = []
    for it in hist.get("items", []):
        if isinstance(it, dict):
            items_sorted.append(it)

    def _parse_iso(iso: str) -> Tuple[int, str]:
        # return a sortable key
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return (int(dt.timestamp()), iso)
        except Exception:
            return (0, iso)

    items_sorted.sort(key=lambda x: _parse_iso(_as_str(x.get("as_of_ts")) or "NA"))

    # last N
    recent = items_sorted[-HISTORY_SHOW_N:] if len(items_sorted) > 0 else []

    # last non-NONE
    last_non_none: Optional[Dict[str, Any]] = None
    for it in reversed(items_sorted):
        if (it.get("bottom_state") or "NA") not in ("NONE", "NA"):
            last_non_none = it
            break

    # streak of current bottom_state (by distinct TPE day buckets already ensured)
    streak = 0
    cur_state = bottom_state
    for it in reversed(items_sorted):
        if (it.get("bottom_state") or "NA") == cur_state:
            streak += 1
        else:
            break

    # transitions in recent window
    transitions: List[str] = []
    prev_state: Optional[str] = None
    for it in recent:
        st = it.get("bottom_state") or "NA"
        if prev_state is None:
            prev_state = st
            continue
        if st != prev_state:
            transitions.append(f"{prev_state} → {st} @ {_as_str(it.get('as_of_ts')) or 'NA'}")
        prev_state = st

    # top-2 nearest activation distances (smaller positive means closer; <=0 already triggered)
    dist_map = {
        "VIX panic gap (<=0 triggered)": dist_vix_panic,
        "SP500 ret1% gap (<=0 triggered)": dist_spx_panic,
        "HYG veto gap z (<=0 veto)": dist_hyg_veto,
        "OFR veto gap z (<=0 veto)": dist_ofr_veto,
    }

    def _dist_rank_val(x: Optional[float]) -> float:
        if x is None:
            return float("inf")
        # If already triggered (<=0), make it the "closest"
        return -1e9 if x <= 0 else x

    dist_sorted = sorted(dist_map.items(), key=lambda kv: _dist_rank_val(kv[1]))
    top2 = dist_sorted[:2]

    # ---- dashboard markdown ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state: **{bottom_state}**  (streak={streak})\n")
    md.append(f"- market_cache_as_of_ts: `{meta['as_of_ts'] or 'NA'}`\n")
    md.append(f"- market_cache_generated_at_utc: `{meta['generated_at_utc'] or 'NA'}`\n\n")

    md.append("## Rationale (Decision Chain)\n")
    md.append(f"- TRIG_PANIC = `{trig_panic}`  (VIX >= {TH_VIX_PANIC} OR SP500.ret1% <= {TH_SPX_RET1_PANIC})\n")
    md.append(f"- TRIG_SYSTEMIC_VETO = `{trig_veto}`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)\n")
    md.append(f"- TRIG_REVERSAL = `{trig_rev}`  (panic & NOT systemic & VIX cooling & SP500 stable)\n")
    if trig_panic == 0:
        md.append("- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）\n")
    elif trig_panic == 1 and trig_veto == 1:
        md.append("- 已觸發恐慌，但出現系統性 veto → 不抄底（先等信用/壓力解除）\n")
    elif trig_panic == 1 and trig_veto == 0 and trig_rev == 0:
        md.append("- 恐慌成立且無系統性 veto，但尚未看到反轉確認 → BOTTOM_WATCH\n")
    elif trig_panic == 1 and trig_veto == 0 and trig_rev == 1:
        md.append("- 恐慌成立且無系統性 veto，且反轉確認成立 → BOTTOM_CANDIDATE\n")
    md.append("\n")

    md.append("## Distance to Triggers (How far from activation)\n")
    if dist_vix_panic is not None and vix_val is not None:
        md.append(f"- VIX panic gap = {TH_VIX_PANIC} - {vix_val} = **{_safe_float_str(dist_vix_panic, 4)}**  (<=0 means triggered)\n")
    else:
        md.append("- VIX panic gap = NA (missing VIX.latest.value)\n")

    if dist_spx_panic is not None and spx_ret1 is not None:
        md.append(f"- SP500 ret1% gap = {spx_ret1} - ({TH_SPX_RET1_PANIC}) = **{_safe_float_str(dist_spx_panic, 4)}**  (<=0 means triggered)\n")
    else:
        md.append("- SP500 ret1% gap = NA (missing SP500.w60.ret1_pct)\n")

    if dist_hyg_veto is not None and hyg_z is not None:
        md.append(f"- HYG veto gap (z) = {hyg_z} - ({TH_HYG_VETO_Z}) = **{_safe_float_str(dist_hyg_veto, 4)}**  (<=0 means systemic veto)\n")
    else:
        md.append("- HYG veto gap (z) = NA (missing HYG_IEF_RATIO.w60.z)\n")

    if dist_ofr_veto is not None and ofr_z is not None:
        md.append(f"- OFR veto gap (z) = ({TH_OFR_VETO_Z}) - {ofr_z} = **{_safe_float_str(dist_ofr_veto, 4)}**  (<=0 means systemic veto)\n")
    else:
        md.append("- OFR veto gap (z) = NA (missing OFR_FSI.w60.z)\n")

    md.append("\n### Nearest Conditions (Top-2)\n")
    for name, val in top2:
        md.append(f"- {name}: `{_safe_float_str(val, 4)}`\n")
    md.append("\n")

    md.append("## Context (Non-trigger)\n")
    if context_equity_extreme is None:
        md.append("- SP500.p252: NA → cannot evaluate equity extreme context\n")
    else:
        md.append(f"- SP500.p252 = `{_safe_float_str(float(spx_p252), 4) if spx_p252 is not None else 'NA'}`; equity_extreme(p252>=95) = `{context_equity_extreme}`\n")
        if context_equity_extreme == 1:
            md.append("- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）\n")
    md.append("\n")

    md.append("## Triggers (0/1/NA)\n")
    md.append(f"- TRIG_PANIC: `{trig_panic}`\n")
    md.append(f"- TRIG_SYSTEMIC_VETO: `{trig_veto}`\n")
    md.append(f"- TRIG_REVERSAL: `{trig_rev}`\n\n")

    if excluded:
        md.append("## Excluded / NA Reasons\n")
        for e in excluded:
            md.append(f"- {e.get('trigger','NA')}: {e.get('reason','NA')}\n")
        md.append("\n")

    md.append("## Action Map (v0)\n")
    md.append("- NONE: 維持既定 DCA/資產配置紀律；不把它當成抄底時點訊號\n")
    md.append("- BOTTOM_WATCH: 只做準備（現金/分批計畫/撤退條件），不進場\n")
    md.append("- BOTTOM_CANDIDATE: 允許分批（例如 2–3 段），但需設定撤退條件\n")
    md.append("- PANIC_BUT_SYSTEMIC: 不抄底，先等信用/壓力解除\n\n")

    md.append("## Recent History (last 10 buckets)\n")
    if not recent:
        md.append("- NA (history empty)\n\n")
    else:
        md.append("| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | note |\n")
        md.append("|---|---|---|---:|---:|---:|---|\n")
        for it in recent:
            asof = _as_str(it.get("as_of_ts")) or "NA"
            dk2 = _day_key_tpe_from_iso(asof)
            st = it.get("bottom_state") or "NA"
            tr = it.get("triggers") if isinstance(it.get("triggers"), dict) else {}
            p = tr.get("TRIG_PANIC", "NA")
            v = tr.get("TRIG_SYSTEMIC_VETO", "NA")
            r = tr.get("TRIG_REVERSAL", "NA")
            note = ""
            if isinstance(it.get("context"), dict):
                ce = it["context"].get("context_equity_extreme_sp500_p252_ge_95", None)
                if ce == 1:
                    note = "equity_extreme"
            md.append(f"| {dk2} | {asof} | {st} | {p} | {v} | {r} | {note} |\n")
        md.append("\n")

    if transitions:
        md.append("## State Transitions (within recent window)\n")
        for t in transitions:
            md.append(f"- {t}\n")
        md.append("\n")

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

    md.append("\n## Data Sources (single-source policy)\n")
    md.append(f"- market_cache input: `{MARKET_STATS_PATH}`\n")
    md.append("- This dashboard does not fetch external URLs directly; it trusts market_cache to provide `source_url` per series.\n")

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()