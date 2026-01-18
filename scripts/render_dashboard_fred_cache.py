#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _load_ndjson_or_json_array(path: str) -> List[Dict[str, Any]]:
    raw = _read_text(path).strip()
    if not raw:
        return []
    if raw[0] == "[":
        data = json.loads(raw)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def _parse_dt(s: str) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _fmt_num(x: Optional[float], nd: int = 6) -> str:
    if x is None:
        return "NA"
    try:
        if math.isnan(x) or math.isinf(x):
            return "NA"
    except Exception:
        return "NA"
    s = f"{x:.{nd}f}"
    if s.startswith("-0.000000"):
        s = s.replace("-0.000000", "0.000000")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def _percentile_le(window: List[float], x: float) -> Optional[float]:
    if not window:
        return None
    n = len(window)
    cnt = sum(1 for v in window if v <= x)
    return cnt / n * 100.0


def _zscore_ddof0(window: List[float], x: float) -> Optional[float]:
    if not window:
        return None
    n = len(window)
    mean = sum(window) / n
    var = sum((v - mean) ** 2 for v in window) / n
    if var <= 0:
        return None
    std = math.sqrt(var)
    return (x - mean) / std


def _sort_key_hist(rec: Dict[str, Any]) -> Tuple[str, str, str]:
    series = str(rec.get("series_id") or rec.get("series") or "")
    data_date = str(rec.get("data_date") or "")
    as_of_ts = str(rec.get("as_of_ts") or rec.get("effective_as_of_ts") or "")
    return (series, data_date, as_of_ts)


@dataclass
class Row:
    series: str
    dq: str
    age_h: Optional[float]
    data_date: str
    value: Optional[float]
    z60: Optional[float]
    p252: Optional[float]
    z_delta60: Optional[float]
    p_delta60: Optional[float]
    ret1_pct: Optional[float]
    reason: str
    tag: str
    near: str
    signal: str
    prev_signal: str
    delta_signal: str
    streak_wa: int
    source_url: str
    as_of_ts: str


MODULE = "fred_cache"

PATH_STATS = "cache/stats_latest.json"
PATH_HISTORY_LITE = "cache/history_lite.json"
PATH_DQ_STATE = "cache/dq_state.json"  # optional

OUT_DIR = "dashboard_fred_cache"
OUT_MD = os.path.join(OUT_DIR, "dashboard.md")   # dashboard.md
OUT_HISTORY = os.path.join(OUT_DIR, "history.json")

STALE_HOURS_DEFAULT = 72.0

TH_ZDELTA = 0.75
TH_PDELTA = 20.0
TH_RET1P = 2.0

# NEAR_RATIO = 0.90 means "within 10% of thresholds"
NEAR_RATIO = 0.90


def _load_dq_map() -> Dict[str, str]:
    if not os.path.exists(PATH_DQ_STATE):
        return {}
    try:
        dq = _load_json(PATH_DQ_STATE)
    except Exception:
        return {}

    out: Dict[str, str] = {}
    if isinstance(dq, dict):
        if isinstance(dq.get("series"), dict):
            for k, v in dq["series"].items():
                if isinstance(v, dict):
                    val = v.get("dq") or v.get("status")
                    if isinstance(val, str):
                        out[str(k)] = val
        for k, v in dq.items():
            if k == "series":
                continue
            if isinstance(v, dict):
                val = v.get("dq") or v.get("status")
                if isinstance(val, str):
                    out[str(k)] = val
            elif isinstance(v, str):
                out[str(k)] = v
    return out


def _group_history_lite(recs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in recs:
        sid = r.get("series_id") or r.get("series")
        if not sid:
            continue
        sid = str(sid)
        by.setdefault(sid, []).append(r)
    for sid in list(by.keys()):
        by[sid].sort(key=_sort_key_hist)
    return by


def _compute_prev_window_metrics(
    series_hist: List[Dict[str, Any]],
    window_n: int = 60
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if len(series_hist) < 2:
        return (None, None, None)

    prev_rec = series_hist[-2]
    last_rec = series_hist[-1]

    prev_val = _safe_float(prev_rec.get("value"))
    last_val = _safe_float(last_rec.get("value"))
    if prev_val is None or last_val is None:
        return (None, None, None)

    upto_prev = series_hist[: len(series_hist) - 1]
    vals: List[float] = []
    for rec in upto_prev:
        v = _safe_float(rec.get("value"))
        if v is not None:
            vals.append(v)

    if len(vals) < window_n:
        prev_z60 = None
        prev_p60 = None
    else:
        win = vals[-window_n:]
        prev_z60 = _zscore_ddof0(win, prev_val)
        prev_p60 = _percentile_le(win, prev_val)

    if prev_val == 0:
        ret1_pct = None
    else:
        ret1_pct = (last_val - prev_val) / abs(prev_val) * 100.0

    return (prev_z60, prev_p60, ret1_pct)


def _near_flags(z_delta60: Optional[float], p_delta60: Optional[float], ret1_pct: Optional[float]) -> str:
    flags: List[str] = []
    if z_delta60 is not None and abs(z_delta60) >= TH_ZDELTA * NEAR_RATIO:
        flags.append("NEAR:ZΔ60")
    if p_delta60 is not None and abs(p_delta60) >= TH_PDELTA * NEAR_RATIO:
        flags.append("NEAR:PΔ60")
    if ret1_pct is not None and abs(ret1_pct) >= TH_RET1P * NEAR_RATIO:
        flags.append("NEAR:ret1%")
    return "+".join(flags) if flags else "NA"


def _jump_vote(
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float]
) -> Tuple[bool, List[str]]:
    hits = 0
    reasons: List[str] = []
    if z_delta60 is not None and abs(z_delta60) >= TH_ZDELTA:
        hits += 1
        reasons.append("abs(zΔ60)>=0.75")
    if p_delta60 is not None and abs(p_delta60) >= TH_PDELTA:
        hits += 1
        reasons.append("abs(pΔ60)>=20")
    if ret1_pct is not None and abs(ret1_pct) >= TH_RET1P:
        hits += 1
        reasons.append("abs(ret1%)>=2")
    return (hits >= 2, reasons)


def _signal_for_series(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float]
) -> Tuple[str, str, str, str]:
    reasons: List[str] = []
    signal = "NONE"

    if p252 is not None:
        if p252 <= 2:
            signal = "ALERT"
            reasons.append("P252<=2")
        elif p252 >= 95 or p252 <= 5:
            if signal != "ALERT":
                signal = "INFO"
            reasons.append("P252>=95" if p252 >= 95 else "P252<=5")

    if z60 is not None:
        if abs(z60) >= 2.5:
            signal = "ALERT"
            reasons.append("abs(Z60)>=2.5")
        elif abs(z60) >= 2:
            if signal != "ALERT":
                signal = "WATCH"
            reasons.append("abs(Z60)>=2")

    jump_hit, jump_reasons = _jump_vote(z_delta60, p_delta60, ret1_pct)
    if jump_hit and signal != "ALERT":
        if signal in ("NONE", "INFO"):
            signal = "WATCH"
        reasons.extend(jump_reasons)

    near = _near_flags(z_delta60, p_delta60, ret1_pct)

    tag = "NA"
    if z60 is not None and abs(z60) >= 2:
        tag = "EXTREME_Z"
    elif p252 is not None and (p252 >= 95 or p252 <= 5):
        tag = "LONG_EXTREME"
    else:
        has_delta = any(r.startswith("abs(zΔ60)") or r.startswith("abs(pΔ60)") for r in jump_reasons)
        has_ret = any(r.startswith("abs(ret1%)") for r in jump_reasons)
        if has_delta:
            tag = "JUMP_DELTA"
        elif has_ret:
            tag = "JUMP_RET"

    reason = ";".join(reasons) if reasons else "NA"
    return (signal, tag, near, reason)


def _load_dash_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "dash_history_v1", "items": []}
    try:
        obj = _load_json(path)
        if isinstance(obj, dict) and isinstance(obj.get("items"), list):
            return obj
    except Exception:
        pass
    return {"schema_version": "dash_history_v1", "items": []}


def _snapshot_key(it: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Key used to collapse reruns of the SAME snapshot.
    We intentionally ignore run_ts_utc. We care about the data snapshot identity.
    """
    module = str(it.get("module") or "")
    asof = str(it.get("stats_as_of_ts") or "")
    ss = it.get("series_signals")
    if not isinstance(ss, dict):
        ss = {}
    ss_norm = json.dumps(ss, sort_keys=True, ensure_ascii=False)
    return (module, asof, ss_norm)


def _normalize_history_inplace(hist_obj: Dict[str, Any]) -> bool:
    """
    Compress consecutive duplicate snapshots so reruns do not inflate streak.
    Also removes earlier duplicates across the file (keeps first occurrence per key order).
    Returns True if modified.
    """
    items = hist_obj.get("items")
    if not isinstance(items, list) or not items:
        return False

    new_items: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()

    for it in items:
        if not isinstance(it, dict):
            continue
        k = _snapshot_key(it)
        # If you want to only collapse consecutive duplicates (not global),
        # replace `seen` logic with `last_k` comparison.
        if k in seen:
            continue
        seen.add(k)
        new_items.append(it)

    if len(new_items) != len(items):
        hist_obj["items"] = new_items
        hist_obj["schema_version"] = "dash_history_v1"
        return True
    return False


def _prev_signal_from_history(hist_obj: Dict[str, Any]) -> Dict[str, str]:
    items = hist_obj.get("items", [])
    if not isinstance(items, list) or not items:
        return {}
    last = items[-1]
    if not isinstance(last, dict):
        return {}
    series_signals = last.get("series_signals")
    if isinstance(series_signals, dict):
        return {str(k): str(v) for k, v in series_signals.items()}
    return {}


def _compute_streak(prev_hist_obj: Dict[str, Any], series: str, today_signal: str) -> int:
    if today_signal != "WATCH":
        return 0
    items = prev_hist_obj.get("items", [])
    if not isinstance(items, list) or not items:
        return 1
    streak = 0
    for it in reversed(items):
        if not isinstance(it, dict):
            continue
        ss = it.get("series_signals")
        if not isinstance(ss, dict):
            continue
        sig = ss.get(series)
        if sig == "WATCH":
            streak += 1
        else:
            break
    return streak + 1


def _delta_signal(prev: str, curr: str) -> str:
    if prev in ("", "NA", None):
        return "NA"
    if prev == curr:
        return "SAME"
    return f"{prev}→{curr}"


def _should_append_history(hist_obj: Dict[str, Any], new_item: Dict[str, Any]) -> bool:
    """
    Idempotent append: if last entry represents the same snapshot, don't append.
    """
    items = hist_obj.get("items", [])
    if not isinstance(items, list) or not items:
        return True
    last = items[-1]
    if not isinstance(last, dict):
        return True
    return _snapshot_key(last) != _snapshot_key(new_item)


def main() -> None:
    run_ts_utc = datetime.now(timezone.utc)

    stats = _load_json(PATH_STATS)
    stats_generated = _parse_dt(str(stats.get("generated_at_utc") or ""))
    stats_as_of_ts = str(stats.get("as_of_ts") or "NA")
    script_version = str(stats.get("stats_policy", {}).get("script_version") or stats.get("script_version") or "NA")

    series_map = stats.get("series", {})
    if not isinstance(series_map, dict):
        series_map = {}

    age_h = None
    if stats_generated is not None:
        age_h = (run_ts_utc - stats_generated).total_seconds() / 3600.0

    dq_map = _load_dq_map()

    hl_recs = _load_ndjson_or_json_array(PATH_HISTORY_LITE) if os.path.exists(PATH_HISTORY_LITE) else []
    hl_by = _group_history_lite(hl_recs)

    # Load history then normalize BEFORE computing streak
    hist_obj = _load_dash_history(OUT_HISTORY)
    modified = _normalize_history_inplace(hist_obj)
    if modified:
        _write_text(OUT_HISTORY, json.dumps(hist_obj, ensure_ascii=False, indent=2) + "\n")

    prev_map = _prev_signal_from_history(hist_obj)

    rows: List[Row] = []
    series_signals_out: Dict[str, str] = {}

    for sid in sorted(series_map.keys()):
        item = series_map.get(sid, {})
        if not isinstance(item, dict):
            continue

        latest = item.get("latest", {}) if isinstance(item.get("latest"), dict) else {}
        metrics = item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {}

        data_date = str(latest.get("data_date") or "NA")
        value = _safe_float(latest.get("value"))
        source_url = str(latest.get("source_url") or "NA")

        z60 = _safe_float(metrics.get("z60"))
        p252 = _safe_float(metrics.get("p252"))
        p60_latest = _safe_float(metrics.get("p60"))

        prev_z60, prev_p60, ret1_pct = _compute_prev_window_metrics(hl_by.get(sid, []), window_n=60)
        z_delta60 = (z60 - prev_z60) if (z60 is not None and prev_z60 is not None) else None
        p_delta60 = (p60_latest - prev_p60) if (p60_latest is not None and prev_p60 is not None) else None

        signal, tag, near, reason = _signal_for_series(z60, p252, z_delta60, p_delta60, ret1_pct)

        prev_signal = prev_map.get(sid, "NA")
        delta_signal = _delta_signal(prev_signal, signal)
        streak_wa = _compute_streak(hist_obj, sid, signal)

        dq = dq_map.get(sid, "OK")

        rows.append(Row(
            series=sid, dq=dq, age_h=age_h, data_date=data_date, value=value,
            z60=z60, p252=p252, z_delta60=z_delta60, p_delta60=p_delta60, ret1_pct=ret1_pct,
            reason=reason, tag=tag, near=near, signal=signal,
            prev_signal=prev_signal, delta_signal=delta_signal, streak_wa=streak_wa,
            source_url=source_url, as_of_ts=stats_as_of_ts,
        ))
        series_signals_out[sid] = signal

    def _cnt(sig: str) -> int:
        return sum(1 for r in rows if r.signal == sig)

    alert_n = _cnt("ALERT")
    watch_n = _cnt("WATCH")
    info_n = _cnt("INFO")
    none_n = _cnt("NONE")

    changed_n = sum(1 for r in rows if r.delta_signal not in ("NA", "SAME"))
    watch_streak_ge3 = sum(1 for r in rows if r.signal == "WATCH" and r.streak_wa >= 3)

    order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows.sort(key=lambda r: (order.get(r.signal, 9), r.series))

    md: List[str] = []
    md.append(f"# Risk Dashboard ({MODULE})\n")
    md.append(f"- Summary: ALERT={alert_n} / WATCH={watch_n} / INFO={info_n} / NONE={none_n}; CHANGED={changed_n}; WATCH_STREAK>=3={watch_streak_ge3}")
    md.append(f"- RUN_TS_UTC: `{run_ts_utc.isoformat()}`")
    md.append(f"- STATS.generated_at_utc: `{stats.get('generated_at_utc','NA')}`")
    md.append(f"- STATS.as_of_ts: `{stats_as_of_ts}`")
    md.append(f"- script_version: `{script_version}`")
    md.append(f"- stale_hours: `{STALE_HOURS_DEFAULT}`")
    md.append(f"- dash_history: `{OUT_HISTORY}`")
    md.append(f"- history_lite_used_for_jump: `{PATH_HISTORY_LITE}`")
    md.append("- jump_calc: `ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)`")
    md.append(
        "- signal_rules: "
        "`Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); "
        "Jump(2/3 vote: abs(zΔ60)>=0.75, abs(pΔ60)>=20, abs(ret1%)>=2 -> WATCH); "
        "Near(within 10% of jump thresholds)`\n"
    )

    cols = [
        "Signal","Tag","Near","PrevSignal","DeltaSignal","StreakWA",
        "Series","DQ","age_h","data_date","value","z60","p252",
        "z_delta60","p_delta60","ret1_pct","Reason","Source","as_of_ts"
    ]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "|".join(["---"] * len(cols)) + "|")

    for r in rows:
        md.append("| " + " | ".join([
            r.signal, r.tag, r.near, r.prev_signal, r.delta_signal, str(r.streak_wa),
            r.series, r.dq, _fmt_num(r.age_h, 2), r.data_date, _fmt_num(r.value, 6),
            _fmt_num(r.z60, 6), _fmt_num(r.p252, 6),
            _fmt_num(r.z_delta60, 6), _fmt_num(r.p_delta60, 6),
            _fmt_num(r.ret1_pct, 6),
            r.reason, r.source_url, r.as_of_ts
        ]) + " |")

    _write_text(OUT_MD, "\n".join(md) + "\n")

    # Idempotent append using snapshot identity
    new_item = {
        "run_ts_utc": run_ts_utc.isoformat(),
        "stats_as_of_ts": stats_as_of_ts,
        "module": MODULE,
        "series_signals": series_signals_out,
    }

    items = hist_obj.get("items")
    if not isinstance(items, list):
        items = []

    if _should_append_history(hist_obj, new_item):
        items.append(new_item)

    hist_obj["schema_version"] = "dash_history_v1"
    hist_obj["items"] = items
    _write_text(OUT_HISTORY, json.dumps(hist_obj, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()