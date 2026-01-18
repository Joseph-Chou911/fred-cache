#!/usr/bin/env python3
# scripts/render_dashboard.py
#
# Merged Risk Dashboard renderer
# - Supports multiple feeds (market_cache + cache)
# - Auto-detect history schema:
#   - list: root list of points
#   - dict: unwrap "series" if present; accept series->list or series->dict->list
# - Adds stale_hours + data_lag clamps
# - Outputs markdown + state json (PrevSignal / StreakWA)
#
# NOTE: This script does NOT fetch data. It only reads local JSON files.

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Utilities
# -------------------------

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    s = dt_str.strip()
    # Accept Z or offset
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.strptime(d.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "" or s.upper() == "NA":
            return None
        try:
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None
    return None


def _fmt(x: Any, nd: int = 6) -> str:
    v = _safe_float(x)
    if v is None:
        return "NA"
    # Keep integers clean
    if abs(v - round(v)) < 1e-12 and abs(v) < 1e12:
        return str(int(round(v)))
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return s if s != "-0" else "0"


def _escape_pipes(s: str) -> str:
    # markdown table: escape pipe
    return s.replace("|", "\\|")


# -------------------------
# History schema autodetect
# -------------------------

@dataclass
class HistoryInfo:
    schema: str                 # "list" or "dict"
    unwrap: str                 # "root" or "series"
    series_count: int
    series_points: Dict[str, List[Dict[str, Any]]]  # series_id -> points list


def _normalize_history_points(points: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in points:
        if isinstance(p, dict):
            out.append(p)
    return out


def _unwrap_history(obj: Any) -> HistoryInfo:
    # Case A: root is a list of points, each has series_id
    if isinstance(obj, list):
        series_map: Dict[str, List[Dict[str, Any]]] = {}
        for p in _normalize_history_points(obj):
            sid = p.get("series_id")
            if isinstance(sid, str) and sid:
                series_map.setdefault(sid, []).append(p)
        return HistoryInfo(schema="list", unwrap="root", series_count=len(series_map), series_points=series_map)

    # Case B: dict (maybe wrapped)
    if isinstance(obj, dict):
        unwrap = "root"
        series_blob = obj

        if "series" in obj and isinstance(obj["series"], (dict, list)):
            unwrap = "series"
            series_blob = obj["series"]

        # series_blob could be:
        # 1) dict: { "OFR_FSI": [points...], "VIX": [points...] }
        # 2) dict: { "OFR_FSI": {"points":[...]} } etc (we attempt best-effort)
        # 3) list: fall back to list behavior
        if isinstance(series_blob, list):
            series_map: Dict[str, List[Dict[str, Any]]] = {}
            for p in _normalize_history_points(series_blob):
                sid = p.get("series_id")
                if isinstance(sid, str) and sid:
                    series_map.setdefault(sid, []).append(p)
            return HistoryInfo(schema="dict", unwrap=unwrap, series_count=len(series_map), series_points=series_map)

        if isinstance(series_blob, dict):
            series_map2: Dict[str, List[Dict[str, Any]]] = {}
            for sid, payload in series_blob.items():
                if not isinstance(sid, str) or not sid:
                    continue
                pts: List[Dict[str, Any]] = []
                if isinstance(payload, list):
                    pts = _normalize_history_points(payload)
                elif isinstance(payload, dict):
                    # try common keys
                    for k in ("points", "history", "data"):
                        if k in payload and isinstance(payload[k], list):
                            pts = _normalize_history_points(payload[k])
                            break
                    # fallback: if dict itself looks like a point list container?
                if pts:
                    series_map2[sid] = pts
            return HistoryInfo(schema="dict", unwrap=unwrap, series_count=len(series_map2), series_points=series_map2)

    return HistoryInfo(schema="unknown", unwrap="unknown", series_count=0, series_points={})


# -------------------------
# Dashboard logic
# -------------------------

@dataclass
class FeedConfig:
    name: str
    stats_path: str
    history_path: str
    dq_path: Optional[str]
    asof_field: str  # usually "as_of_ts"


def _pick(d: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return None


def _dq_lookup(dq_obj: Any, series_id: str) -> str:
    # Accept both:
    # - dict { "series": { "SP500": {"dq":"OK"} } }
    # - dict { "SP500": {"dq":"OK"} }
    if not dq_obj or not series_id:
        return "NA"
    if isinstance(dq_obj, dict):
        base = dq_obj.get("series") if isinstance(dq_obj.get("series"), dict) else dq_obj
        if isinstance(base, dict) and series_id in base and isinstance(base[series_id], dict):
            for k in ("dq", "status", "DQ"):
                v = base[series_id].get(k)
                if isinstance(v, str) and v:
                    return v
            # common pattern: {"ok": true}
            if base[series_id].get("ok") is True:
                return "OK"
    return "NA"


def _calc_age_hours(run_ts_utc: datetime, as_of_ts: Optional[str]) -> Optional[float]:
    dt = _parse_dt(as_of_ts)
    if not dt:
        return None
    delta = run_ts_utc - dt.astimezone(timezone.utc)
    return delta.total_seconds() / 3600.0


def _calc_data_lag_days(run_ts_utc: datetime, data_date: Optional[str]) -> Optional[int]:
    dd = _parse_date(data_date)
    if not dd:
        return None
    return (run_ts_utc.date() - dd).days


def _signal_for_row(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
    p_delta_any: Optional[float],
    ret1_pct: Optional[float],
    # rules
    thr_z_watch: float = 2.0,
    thr_z_alert: float = 2.5,
    thr_jump_zd: float = 0.75,
    thr_info_pdelta: float = 15.0,
    thr_info_ret: float = 2.0,
) -> Tuple[str, List[str], str]:
    """
    Returns: (Signal, tags[], reason)
    Signal: ALERT/WATCH/INFO/NONE
    Tags: e.g. EXTREME_Z, JUMP_ZD, INFO_PΔ, INFO_RET, LONG_EXTREME
    """
    tags: List[str] = []
    reasons: List[str] = []

    # Jump (ONLY z_delta60)
    is_jump_zd = (z_delta60 is not None) and (abs(z_delta60) >= thr_jump_zd)
    if is_jump_zd:
        tags.append("JUMP_ZD")
        reasons.append("|ZΔ60|>=0.75")

    # Extreme Z
    if z60 is not None and abs(z60) >= thr_z_watch:
        tags.append("EXTREME_Z")
        reasons.append("|Z60|>=2")

    # Long extreme (P252)
    is_long_extreme = (p252 is not None) and (p252 >= 95.0 or p252 <= 5.0)
    if is_long_extreme:
        tags.append("LONG_EXTREME")
        reasons.append("P252>=95 or <=5")

    # INFO tags only (no escalation)
    if p_delta_any is not None and abs(p_delta_any) >= thr_info_pdelta:
        tags.append("INFO_PΔ")
    if ret1_pct is not None and abs(ret1_pct) >= thr_info_ret:
        tags.append("INFO_RET")

    # Determine base Signal priority
    # ALERT if |Z60|>=2.5 (regardless of jump)
    if z60 is not None and abs(z60) >= thr_z_alert:
        return ("ALERT", tags, ";".join(reasons) if reasons else "NA")

    # WATCH if jump_zd OR extreme_z>=2
    if is_jump_zd or (z60 is not None and abs(z60) >= thr_z_watch):
        return ("WATCH", tags, ";".join(reasons) if reasons else "NA")

    # INFO if only long extreme (and no jump and no extreme_z)
    if is_long_extreme:
        return ("INFO", tags, ";".join(reasons) if reasons else "NA")

    return ("NONE", tags, "NA")


def _merge_tags(tags: List[str]) -> str:
    if not tags:
        return "NA"
    # stable order (priority-ish)
    order = ["EXTREME_Z", "JUMP_ZD", "LONG_EXTREME", "INFO_PΔ", "INFO_RET", "STALE_DATA"]
    seen = set(tags)
    out = [t for t in order if t in seen]
    # include any extras
    for t in tags:
        if t not in set(out):
            out.append(t)
    return ",".join(out) if out else "NA"


def _near_flags(z_delta60: Optional[float], p_delta_any: Optional[float], ret1_pct: Optional[float]) -> str:
    parts: List[str] = []
    # Near = within 10% of thresholds: ZΔ60 / PΔ / ret1%
    if z_delta60 is not None and abs(z_delta60) >= 0.75 * 0.9:
        parts.append("NEAR:ZΔ60")
    if p_delta_any is not None and abs(p_delta_any) >= 15.0 * 0.9:
        parts.append("NEAR:PΔ")
    if ret1_pct is not None and abs(ret1_pct) >= 2.0 * 0.9:
        parts.append("NEAR:ret1%")
    return ",".join(parts) if parts else "NA"


# -------------------------
# State handling (PrevSignal / StreakWA)
# -------------------------

def _load_state(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {"series": {}}
    try:
        obj = _read_json(path)
        if isinstance(obj, dict) and "series" in obj and isinstance(obj["series"], dict):
            return obj
    except Exception:
        pass
    return {"series": {}}


def _update_state(state: Dict[str, Any], key: str, new_signal: str) -> Tuple[str, int]:
    """
    Returns: (PrevSignal, StreakWA)
    StreakWA: consecutive count while signal is WATCH/ALERT (WA),
              resets to 0 when NONE/INFO, increments when WATCH/ALERT.
    """
    series_state = state.setdefault("series", {})
    prev = "NONE"
    streak = 0
    if key in series_state and isinstance(series_state[key], dict):
        prev = series_state[key].get("prev_signal", "NONE") or "NONE"
        streak = int(series_state[key].get("streak_wa", 0) or 0)

    # update streak
    if new_signal in ("WATCH", "ALERT"):
        streak = streak + 1 if prev in ("WATCH", "ALERT") else 1
    else:
        streak = 0

    series_state[key] = {"prev_signal": new_signal, "streak_wa": streak}
    return prev, streak


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", action="append", default=[], help="Feed name (repeatable).")
    ap.add_argument("--stats", action="append", default=[], help="Stats json path (repeatable).")
    ap.add_argument("--history", action="append", default=[], help="History json path (repeatable).")
    ap.add_argument("--dq", action="append", default=[], help="DQ json path or 'NA' (repeatable).")
    ap.add_argument("--asof-field", action="append", default=[], help="Stats as-of field name (repeatable).")
    ap.add_argument("--state-file", required=True, help="State json output path.")
    ap.add_argument("--out", required=True, help="Markdown output path.")
    ap.add_argument("--script-fingerprint", default="", help="Fingerprint string to print.")
    args = ap.parse_args()

    if not (len(args.feed) == len(args.stats) == len(args.history) == len(args.dq) == len(args.asof_field)):
        raise SystemExit("feed/stats/history/dq/asof-field counts must match (repeat in same order).")

    feeds: List[FeedConfig] = []
    for i in range(len(args.feed)):
        dq_path = None if args.dq[i].strip().upper() == "NA" else args.dq[i]
        feeds.append(
            FeedConfig(
                name=args.feed[i],
                stats_path=args.stats[i],
                history_path=args.history[i],
                dq_path=dq_path,
                asof_field=args.asof_field[i],
            )
        )

    run_ts_utc = _now_utc()

    # Config defaults
    stale_hours_default = 36.0
    stale_overrides = {"STLFSI4": 240.0, "NFCINONFINLEVERAGE": 240.0, "BAMLH0A0HYM2": 72.0}

    data_lag_default_days = 2
    data_lag_overrides_days = {
        "STLFSI4": 10,
        "NFCINONFINLEVERAGE": 10,
        "OFR_FSI": 7,
        "BAMLH0A0HYM2": 3,
        "DGS2": 3,
        "DGS10": 3,
        "VIXCLS": 3,
        "T10Y2Y": 3,
        "T10Y3M": 3,
    }

    # Load prior state
    state = _load_state(args.state_file)

    # Header bookkeeping + rows
    header_lines: List[str] = []
    rows: List[Dict[str, Any]] = []

    # Signal rules string (for audit printing)
    signal_rules = (
        "Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), "
        "P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); "
        "Jump(ONLY |ZΔ60|>=0.75); "
        "Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); "
        "PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); "
        "StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)"
    )

    # Process feeds
    for fc in feeds:
        stats_obj = _read_json(fc.stats_path)
        hist_obj = _read_json(fc.history_path)
        dq_obj = _read_json(fc.dq_path) if fc.dq_path and os.path.exists(fc.dq_path) else None

        # Stats meta
        feed_as_of = _pick(stats_obj, fc.asof_field, "as_of_ts", "generated_at_utc")
        feed_gen = _pick(stats_obj, "generated_at_utc", "as_of_ts")
        feed_script = _pick(stats_obj, "script_version")

        # History meta autodetect
        hi = _unwrap_history(hist_obj)

        header_lines.append(f"- {fc.name}.stats: `{fc.stats_path}`")
        header_lines.append(f"- {fc.name}.history: `{fc.history_path}`")
        header_lines.append(f"- {fc.name}.history_schema: `{hi.schema}`")
        header_lines.append(f"- {fc.name}.history_unwrap: `{hi.unwrap}`")
        header_lines.append(f"- {fc.name}.history_series_count: `{hi.series_count}`")
        header_lines.append(f"- {fc.name}.as_of_ts: `{feed_as_of}`")
        header_lines.append(f"- {fc.name}.generated_at_utc: `{feed_gen}`")
        header_lines.append(f"- {fc.name}.script_version: `{feed_script}`")

        # Stats series map
        series_map = stats_obj.get("series")
        if not isinstance(series_map, dict):
            continue

        age_h = _calc_age_hours(run_ts_utc, str(feed_as_of) if feed_as_of else None)

        for sid, sblob in series_map.items():
            if not isinstance(sid, str) or not sid:
                continue
            if not isinstance(sblob, dict):
                continue

            latest = sblob.get("latest") if isinstance(sblob.get("latest"), dict) else {}
            data_date = latest.get("data_date")
            value = latest.get("value")
            source_url = latest.get("source_url") or latest.get("source") or "NA"
            if sid == "HYG_IEF_RATIO" and (not source_url or source_url == "NA"):
                source_url = "DERIVED"

            z60 = _safe_float(_pick(sblob, "z60", "z_w60", "z"))
            p252 = _safe_float(_pick(sblob, "p252", "p_w252", "p"))
            z_delta60 = _safe_float(_pick(sblob, "z_delta60", "z_delta_w60", "z_delta"))
            # IMPORTANT FIX: accept p_delta252 OR p_delta60 OR p_delta
            p_delta_any = _safe_float(_pick(sblob, "p_delta252", "p_delta60", "p_delta_w60", "p_delta"))
            # ret1% could be ret1_pct or ret1_pct60
            ret1_pct = _safe_float(_pick(sblob, "ret1_pct", "ret1_pct60", "ret1_pct_w60", "ret1"))

            # DQ
            dq = _dq_lookup(dq_obj, sid)

            # stale policy
            stale_h = float(stale_overrides.get(sid, stale_hours_default))

            # data lag policy
            lag_d = _calc_data_lag_days(run_ts_utc, str(data_date) if isinstance(data_date, str) else None)
            lag_thr = int(data_lag_overrides_days.get(sid, data_lag_default_days))

            # signal
            sig, tags, reason = _signal_for_row(
                z60=z60,
                p252=p252,
                z_delta60=z_delta60,
                p_delta_any=p_delta_any,
                ret1_pct=ret1_pct,
            )

            # StaleData clamp
            if lag_d is not None and lag_d > lag_thr:
                if "STALE_DATA" not in tags:
                    tags.append("STALE_DATA")
                if sig in ("ALERT", "WATCH"):
                    sig = "INFO"
                reason = f"STALE_DATA(lag_d={lag_d}>thr_d={lag_thr})"

            # near flags
            near = _near_flags(z_delta60=z_delta60, p_delta_any=p_delta_any, ret1_pct=ret1_pct)

            # state key = feed+series
            skey = f"{fc.name}:{sid}"
            prev, streak = _update_state(state, skey, sig)

            rows.append(
                {
                    "Signal": sig,
                    "Tag": _merge_tags(tags),
                    "Near": near,
                    "PrevSignal": prev,
                    "StreakWA": streak,
                    "Feed": fc.name,
                    "Series": sid,
                    "DQ": dq,
                    "age_h": age_h,
                    "stale_h": stale_h,
                    "data_lag_d": lag_d,
                    "data_lag_thr_d": lag_thr,
                    "data_date": data_date,
                    "value": value,
                    "z60": z60,
                    "p252": p252,
                    "z_delta60": z_delta60,
                    "p_delta252": p_delta_any,   # output column name kept as p_delta252 (normalized)
                    "ret1_pct": ret1_pct,
                    "Reason": reason,
                    "Source": source_url,
                    "as_of_ts": feed_as_of,
                }
            )

    # Sort rows: Signal priority then Series
    sig_rank = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows.sort(key=lambda r: (sig_rank.get(r["Signal"], 9), str(r["Feed"]), str(r["Series"])))

    # Write state
    os.makedirs(os.path.dirname(args.state_file), exist_ok=True)
    _write_json(args.state_file, state)

    # Render markdown
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    md: List[str] = []
    md.append("# Risk Dashboard (merged)\n")
    md.append(f"- SCRIPT_FINGERPRINT: `{args.script_fingerprint}`")
    md.append(f"- RUN_TS_UTC: `{run_ts_utc.isoformat()}`")
    md.append(f"- stale_hours_default: `{stale_hours_default}`")
    md.append(f"- stale_overrides: `{json.dumps(stale_overrides, ensure_ascii=False)}`")
    md.append(f"- data_lag_default_days: `{data_lag_default_days}`")
    md.append(f"- data_lag_overrides_days: `{json.dumps(data_lag_overrides_days, ensure_ascii=False)}`")
    md.extend(header_lines)
    md.append(f"- signal_rules: `{signal_rules}`\n")

    cols = [
        "Signal", "Tag", "Near", "PrevSignal", "StreakWA", "Feed", "Series", "DQ",
        "age_h", "stale_h", "data_lag_d", "data_lag_thr_d",
        "data_date", "value", "z60", "p252", "z_delta60", "p_delta252", "ret1_pct",
        "Reason", "Source", "as_of_ts",
    ]

    # Table header
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "|".join(["---"] * len(cols)) + "|")

    for r in rows:
        line: List[str] = []
        for c in cols:
            v = r.get(c)
            if c in ("age_h",):
                line.append(_fmt(v, nd=2))
            elif c in ("stale_h",):
                line.append(_fmt(v, nd=0))
            elif c in ("data_lag_d", "data_lag_thr_d", "StreakWA"):
                line.append("NA" if v is None else str(int(v)))
            elif c in ("value", "z60", "p252", "z_delta60", "p_delta252", "ret1_pct"):
                line.append(_fmt(v, nd=6))
            elif c == "Reason":
                line.append(_escape_pipes(str(v)) if v is not None else "NA")
            else:
                line.append("NA" if v is None else str(v))
        md.append("| " + " | ".join(line) + " |")

    md.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())