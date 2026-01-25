#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from zoneinfo import ZoneInfo

TZ_TPE = ZoneInfo("Asia/Taipei")

# ---- config ----
MARKET_STATS_PATH = "market_cache/stats_latest.json"

# ✅ unified outputs (ONLY dashboard_bottom_cache)
OUT_LATEST = "dashboard_bottom_cache/latest.json"
OUT_HISTORY = "dashboard_bottom_cache/history.json"
OUT_MD = "dashboard_bottom_cache/report.md"

NEEDED = ["VIX", "SP500", "HYG_IEF_RATIO", "OFR_FSI"]

# risk direction is a RULE (not guessed)
RISK_DIR = {
    "VIX": "HIGH",
    "OFR_FSI": "HIGH",
    "HYG_IEF_RATIO": "LOW",
    "SP500": "LOW",
}

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
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA": return None
        return float(s)
    except Exception:
        return None

def _as_str(x: Any) -> Optional[str]:
    if x is None: return None
    s = str(x)
    if s.strip() == "" or s.strip().upper() == "NA": return None
    return s

def _get(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def _series_signal(z60: Optional[float], p252: Optional[float]) -> Optional[str]:
    # align with your system style (Extreme z, Percentile extremes)
    if z60 is None and p252 is None:
        return None
    if z60 is not None and abs(z60) >= 2.5:
        return "ALERT"
    if z60 is not None and abs(z60) >= 2.0:
        return "WATCH"
    if p252 is not None and (p252 >= 95.0 or p252 <= 5.0):
        return "INFO"
    return "NONE"

def main() -> None:
    run_ts_utc = _utc_now()
    as_of_ts_tpe = _tpe_now()
    git_sha = os.environ.get("GITHUB_SHA", "NA")

    excluded: List[Dict[str, str]] = []

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
    # TRIG_PANIC
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]  # unit %
    trig_panic: Optional[int] = None
    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and vix_val >= 20.0)
        cond_spx = (spx_ret1 is not None and spx_ret1 <= -1.5)
        trig_panic = 1 if (cond_vix or cond_spx) else 0

    # TRIG_SYSTEMIC_VETO
    hyg_z = series_out["HYG_IEF_RATIO"]["w60"]["z"]
    hyg_sig = series_out["HYG_IEF_RATIO"]["series_signal"]
    ofr_z = series_out["OFR_FSI"]["w60"]["z"]
    ofr_sig = series_out["OFR_FSI"]["series_signal"]

    trig_veto: Optional[int] = None
    hyg_can = (hyg_z is not None and hyg_sig in ("WATCH", "ALERT"))
    ofr_can = (ofr_z is not None and ofr_sig in ("WATCH", "ALERT"))

    if not hyg_can and not ofr_can and (hyg_z is None and ofr_z is None):
        excluded.append({"trigger": "TRIG_SYSTEMIC_VETO", "reason": "missing_fields:HYG_IEF_RATIO.w60.z & OFR_FSI.w60.z"})
    else:
        hyg_veto = 1 if (hyg_can and hyg_z <= -2.0) else 0
        ofr_veto = 1 if (ofr_can and ofr_z >= 2.0) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    # TRIG_REVERSAL
    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        # VIX cooling: any negative available metric
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
            if vix_cooling is None: miss.append("VIX(w60.ret1_pct/z_delta/p_delta)")
            if spx_stab is None: miss.append("SP500(w60.ret1_pct)")
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
        "notes": [
            "v0: single source = market_cache/stats_latest.json",
            "signal derived from w60.z and w252.p using deterministic thresholds",
            "ret1_pct unit is percent (%)"
        ],
    }

    _write_json(OUT_LATEST, latest_out)

    # ---- history append (overwrite same TPE day bucket) ----
    def day_key_tpe(iso_ts: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_TPE)
            return dt.date().isoformat()
        except Exception:
            return "NA"

    hist = {"schema_version": "bottom_history_v1", "items": []}
    if os.path.exists(OUT_HISTORY):
        try:
            hist = _read_json(OUT_HISTORY)
            if not isinstance(hist, dict) or "items" not in hist:
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

    dk = day_key_tpe(as_of_ts_tpe)
    new_items = [it for it in hist.get("items", []) if day_key_tpe(it.get("as_of_ts", "NA")) != dk]
    new_items.append(item)
    hist["items"] = new_items
    _write_json(OUT_HISTORY, hist)

    # ---- dashboard markdown ----
    md = []
    md.append("# Bottom Cache Dashboard (v0)\n\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state: **{bottom_state}**\n\n")

    md.append("## Triggers (0/1/NA)\n")
    for k, v in latest_out["triggers"].items():
        md.append(f"- {k}: `{v}`\n")
    md.append("\n")

    if excluded:
        md.append("## Excluded / NA Reasons\n")
        for e in excluded:
            md.append(f"- {e['trigger']}: {e['reason']}\n")
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

    _write_text(OUT_MD, "".join(md))

if __name__ == "__main__":
    main()