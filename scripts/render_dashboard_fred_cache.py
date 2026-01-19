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
    # trim
    return s.rstrip("0").rstrip(".") if "." in s else s


def _fmt_dbg(x: Optional[float], nd: int = 12) -> str:
    """Debug format: keep high precision (bounded to nd), but still trim trailing zeros."""
    if x is None:
        return "NA"
    try:
        if math.isnan(x) or math.isinf(x):
            return "NA"
    except Exception:
        return "NA"
    s = f"{x:.{nd}f}"
    if s.startswith("-0.000000000000"):
        s = s.replace("-0.000000000000", "0.000000000000")
    return s.rstrip("0").rstrip(".") if "." in s else s


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

    # from stats_latest.json (metrics)
    z60: Optional[float]
    p252: Optional[float]
    p60_latest: Optional[float]

    # computed from history_lite window ending at prev
    prev_value: Optional[float]
    last_value: Optional[float]
    prev_z60: Optional[float]
    prev_p60: Optional[float]

    # derived deltas / returns
    z_delta60: Optional[float]
    p_delta60: Optional[float]
    ret1_pct: Optional[float]

    # jump audit
    jump_hits: int
    hitbits: str
    dbg: str

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
OUT_MD = os.path.join(OUT_DIR, "dashboard.md")
OUT_HISTORY = os.path.join(OUT_DIR, "history.json")

STALE_HOURS_DEFAULT = 72.0

TH_ZDELTA = 0.75
TH_PDELTA = 20.0
TH_RET1P = 2.0
NEAR_RATIO = 0.90

# boundary epsilon to avoid "prints as 20 but compares <20"
EPS_Z = 1e-12
EPS_P = 1e-9
EPS_R = 1e-9

STREAK_BASIS_TEXT = "distinct snapshots (snapshot_id); re-run same snapshot does not increment"

# ret1% guard (avoid blow-ups when prev is near 0)
RET1_DENOM_EPS = 1e-3
RET1_GUARD_TEXT = "ret1% guard: if abs(prev_value)<1e-3 -> ret1%=NA (avoid near-zero denom blow-ups)"
TH_EPS_TEXT = f"threshold_eps: Z={EPS_Z}, P={EPS_P}, R={EPS_R} (avoid rounding/float boundary mismatch)"

# output format control
AGE_ND = 2
VALUE_ND = 4
Z_ND = 4
P_ND = 3
DELTA_ND = 4
RET1_ND = 3
DBG_ND = 12
OUTPUT_FORMAT_TEXT = (
    f"display_nd: age={AGE_ND}, value={VALUE_ND}, z={Z_ND}, p={P_ND}, delta={DELTA_ND}, ret1={RET1_ND}; "
    f"dbg_nd={DBG_ND} (dbg only for Near/Jump)"
)


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
) -> Tuple[
    Optional[float], Optional[float], Optional[float],  # prev_z60, prev_p60, ret1_pct
    Optional[float], Optional[float]                    # prev_value, last_value
]:
    """
    Returns:
      prev_z60 (computed using window ending at prev)
      prev_p60 (computed using window ending at prev)
      ret1_pct = (last-prev)/abs(prev)*100, BUT guarded:
        if abs(prev) < RET1_DENOM_EPS -> None
      prev_value, last_value (audit)
    """
    if len(series_hist) < 2:
        return (None, None, None, None, None)

    prev_rec = series_hist[-2]
    last_rec = series_hist[-1]

    prev_val = _safe_float(prev_rec.get("value"))
    last_val = _safe_float(last_rec.get("value"))
    if prev_val is None or last_val is None:
        return (None, None, None, prev_val, last_val)

    # window up to (and including) prev
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

    if abs(prev_val) < RET1_DENOM_EPS:
        ret1_pct = None
    else:
        ret1_pct = (last_val - prev_val) / abs(prev_val) * 100.0

    return (prev_z60, prev_p60, ret1_pct, prev_val, last_val)


def _near_flags(z_delta60: Optional[float], p_delta60: Optional[float], ret1_pct: Optional[float]) -> str:
    flags: List[str] = []
    if z_delta60 is not None and abs(z_delta60) >= TH_ZDELTA * NEAR_RATIO:
        flags.append("NEAR:ZΔ60")
    if p_delta60 is not None and abs(p_delta60) >= TH_PDELTA * NEAR_RATIO:
        flags.append("NEAR:PΔ60")
    if ret1_pct is not None and abs(ret1_pct) >= TH_RET1P * NEAR_RATIO:
        flags.append("NEAR:ret1%")
    return "+".join(flags) if flags else "NA"


def _jump_hits_and_reasons(
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float]
) -> Tuple[int, str, List[str]]:
    hits = 0
    bits: List[str] = []
    reasons: List[str] = []

    if z_delta60 is not None and abs(z_delta60) + EPS_Z >= TH_ZDELTA:
        hits += 1
        bits.append("Z")
        reasons.append("abs(zΔ60)>=0.75")
    if p_delta60 is not None and abs(p_delta60) + EPS_P >= TH_PDELTA:
        hits += 1
        bits.append("P")
        reasons.append("abs(pΔ60)>=20")
    if ret1_pct is not None and abs(ret1_pct) + EPS_R >= TH_RET1P:
        hits += 1
        bits.append("R")
        reasons.append("abs(ret1%)>=2")

    hitbits = "+".join(bits) if bits else "NA"
    return hits, hitbits, reasons


def _jump_vote(
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float]
) -> Tuple[bool, int, str, List[str]]:
    hits, hitbits, reasons = _jump_hits_and_reasons(z_delta60, p_delta60, ret1_pct)
    return (hits >= 2, hits, hitbits, reasons)


def _signal_for_series(
    z60: Optional[float],
    p252: Optional[float],
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float]
) -> Tuple[str, str, str, str, int, str]:
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

    jump_hit, jump_hits, hitbits, jump_reasons = _jump_vote(z_delta60, p_delta60, ret1_pct)
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
        if hitbits != "NA":
            if "Z" in hitbits or "P" in hitbits:
                tag = "JUMP_DELTA"
            elif "R" in hitbits:
                tag = "JUMP_RET"

    reason = ";".join(reasons) if reasons else "NA"
    return (signal, tag, near, reason, jump_hits, hitbits)


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


def _get_data_commit_sha(stats: Any) -> Optional[str]:
    try:
        if isinstance(stats, dict):
            v = stats.get("data_commit_sha")
            if isinstance(v, str) and v:
                return v
            meta = stats.get("meta")
            if isinstance(meta, dict):
                v = meta.get("data_commit_sha")
                if isinstance(v, str) and v:
                    return v
    except Exception:
        pass
    return None


def _get_stats_generated_at_utc(stats: Any) -> Optional[str]:
    try:
        if isinstance(stats, dict):
            v = stats.get("generated_at_utc")
            if isinstance(v, str) and v:
                return v
            meta = stats.get("meta")
            if isinstance(meta, dict):
                v = meta.get("generated_at_utc")
                if isinstance(v, str) and v:
                    return v
    except Exception:
        pass
    return None


def _make_snapshot_id(stats_as_of_ts: str, stats_generated_at_utc: Optional[str], data_commit_sha: Optional[str]) -> str:
    if data_commit_sha:
        return f"commit:{data_commit_sha}"
    if stats_generated_at_utc:
        return f"gen:{stats_generated_at_utc}"
    return f"asof:{stats_as_of_ts}"


def _item_snapshot_id(item: Dict[str, Any]) -> str:
    if isinstance(item.get("snapshot_id"), str) and item["snapshot_id"]:
        return item["snapshot_id"]
    dc = item.get("data_commit_sha")
    if isinstance(dc, str) and dc:
        return f"commit:{dc}"
    gen = item.get("stats_generated_at_utc")
    if isinstance(gen, str) and gen:
        return f"gen:{gen}"
    asof = item.get("stats_as_of_ts")
    if isinstance(asof, str) and asof:
        return f"asof:{asof}"
    return "asof:NA"


def _item_key(item: Dict[str, Any]) -> Tuple[str, str]:
    module = str(item.get("module") or "NA")
    snap = _item_snapshot_id(item)
    return (module, snap)


def _normalize_history_items(items: List[Any]) -> List[Dict[str, Any]]:
    key_order: List[Tuple[str, str]] = []
    last_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        k = _item_key(it)
        if k not in last_by_key:
            key_order.append(k)
        last_by_key[k] = it
    return [last_by_key[k] for k in key_order]


def _migrate_asof_to_commit(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    m: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        module = str(it.get("module") or "NA")
        asof = it.get("stats_as_of_ts")
        if not isinstance(asof, str) or not asof:
            continue
        snap = it.get("snapshot_id")
        sha = it.get("data_commit_sha")
        if isinstance(snap, str) and snap.startswith("commit:") and isinstance(sha, str) and sha:
            m[(module, asof)] = (snap, sha)

    if not m:
        return items

    for it in items:
        if not isinstance(it, dict):
            continue
        if isinstance(it.get("snapshot_id"), str) and it["snapshot_id"]:
            continue
        module = str(it.get("module") or "NA")
        asof = it.get("stats_as_of_ts")
        if not isinstance(asof, str) or not asof:
            continue
        key = (module, asof)
        if key in m:
            snap, sha = m[key]
            it["snapshot_id"] = snap
            if not (isinstance(it.get("data_commit_sha"), str) and it["data_commit_sha"]):
                it["data_commit_sha"] = sha
    return items


def _prev_signal_from_history(hist_obj: Dict[str, Any], exclude_key: Tuple[str, str]) -> Dict[str, str]:
    items = hist_obj.get("items", [])
    if not isinstance(items, list) or not items:
        return {}
    norm = _normalize_history_items(items)
    last: Optional[Dict[str, Any]] = None
    for it in reversed(norm):
        if _item_key(it) == exclude_key:
            continue
        last = it
        break
    if not last:
        return {}
    series_signals = last.get("series_signals")
    if isinstance(series_signals, dict):
        return {str(k): str(v) for k, v in series_signals.items()}
    return {}


def _compute_streak(hist_obj: Dict[str, Any], series: str, today_signal: str, exclude_key: Tuple[str, str]) -> int:
    if today_signal != "WATCH":
        return 0
    items = hist_obj.get("items", [])
    if not isinstance(items, list) or not items:
        return 1
    norm = _normalize_history_items(items)

    streak = 0
    for it in reversed(norm):
        if _item_key(it) == exclude_key:
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


def _last_hist_value(series_hist: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[float]]:
    if not series_hist:
        return (None, None)
    last = series_hist[-1]
    dd = last.get("data_date")
    vv = _safe_float(last.get("value"))
    return (str(dd) if isinstance(dd, str) and dd else None, vv)


def _values_equal(a: Optional[float], b: Optional[float], rel_tol: float = 1e-12, abs_tol: float = 1e-12) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


def _alignment_check(
    series_map: Dict[str, Any],
    hl_by: Dict[str, List[Dict[str, Any]]],
    max_examples: int = 3
) -> Dict[str, Any]:
    if not isinstance(series_map, dict) or not series_map:
        return {"alignment": "NA", "checked": 0, "mismatch": 0, "missing_hl": 0, "examples": []}

    checked = 0
    mismatch = 0
    missing_hl = 0
    examples: List[str] = []

    for sid in sorted(series_map.keys()):
        item = series_map.get(sid, {})
        if not isinstance(item, dict):
            continue
        latest = item.get("latest", {}) if isinstance(item.get("latest"), dict) else {}
        s_dd = latest.get("data_date")
        s_v = _safe_float(latest.get("value"))
        s_dd_s = str(s_dd) if isinstance(s_dd, str) and s_dd else None

        hl_hist = hl_by.get(sid, [])
        if not hl_hist:
            checked += 1
            missing_hl += 1
            if len(examples) < max_examples:
                examples.append(f"{sid}: stats({s_dd_s},{_fmt_num(s_v, VALUE_ND)}) vs hl(MISSING)")
            continue

        h_dd, h_v = _last_hist_value(hl_hist)
        checked += 1

        if s_dd_s is None or h_dd is None or s_v is None or h_v is None:
            mismatch += 1
            if len(examples) < max_examples:
                examples.append(f"{sid}: stats({s_dd_s},{_fmt_num(s_v, VALUE_ND)}) vs hl({h_dd},{_fmt_num(h_v, VALUE_ND)})")
            continue

        date_mismatch = (s_dd_s != h_dd)
        val_mismatch = (not _values_equal(s_v, h_v))

        if date_mismatch or val_mismatch:
            mismatch += 1
            if len(examples) < max_examples:
                examples.append(f"{sid}: stats({s_dd_s},{_fmt_num(s_v, VALUE_ND)}) vs hl({h_dd},{_fmt_num(h_v, VALUE_ND)})")

    alignment = "PASS" if mismatch == 0 else "FAIL"
    return {"alignment": alignment, "checked": checked, "mismatch": mismatch, "missing_hl": missing_hl, "examples": examples}


def _dbg_for_row(
    near: str,
    jump_hits: int,
    z_delta60: Optional[float],
    p_delta60: Optional[float],
    ret1_pct: Optional[float],
    p60_latest: Optional[float],
    prev_p60: Optional[float],
    z60: Optional[float],
    prev_z60: Optional[float],
    prev_value: Optional[float],
    last_value: Optional[float],
) -> str:
    """
    Emit DBG only when Near!=NA or jump_hits>0, to keep the table quiet in normal cases.
    Include p60 / prev_p60 / prev_z60 / prev_value / last_value for audit of edge cases.
    """
    if near == "NA" and jump_hits <= 0:
        return "NA"

    parts: List[str] = []
    parts.append(f"p60={_fmt_dbg(p60_latest, DBG_ND)}")
    parts.append(f"prev_p60={_fmt_dbg(prev_p60, DBG_ND)}")
    parts.append(f"z60={_fmt_dbg(z60, DBG_ND)}")
    parts.append(f"prev_z60={_fmt_dbg(prev_z60, DBG_ND)}")
    parts.append(f"prev_v={_fmt_dbg(prev_value, DBG_ND)}")
    parts.append(f"last_v={_fmt_dbg(last_value, DBG_ND)}")
    parts.append(f"zΔ60={_fmt_dbg(z_delta60, DBG_ND)}")
    parts.append(f"pΔ60={_fmt_dbg(p_delta60, DBG_ND)}")
    parts.append(f"ret1%={_fmt_dbg(ret1_pct, DBG_ND)}")
    return ";".join(parts)


def main() -> None:
    run_ts_utc = datetime.now(timezone.utc)

    stats = _load_json(PATH_STATS)
    stats_as_of_ts = str(stats.get("as_of_ts") or "NA")
    stats_generated_at_utc = _get_stats_generated_at_utc(stats)
    data_commit_sha = _get_data_commit_sha(stats)
    snapshot_id = _make_snapshot_id(stats_as_of_ts, stats_generated_at_utc, data_commit_sha)
    current_hist_key = (MODULE, snapshot_id)

    stats_generated = _parse_dt(str(stats.get("generated_at_utc") or ""))
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

    align = _alignment_check(series_map, hl_by, max_examples=3)

    hist_obj = _load_dash_history(OUT_HISTORY)
    if isinstance(hist_obj.get("items"), list):
        migrated = _migrate_asof_to_commit([x for x in hist_obj["items"] if isinstance(x, dict)])
        hist_obj["items"] = _normalize_history_items(migrated)

    prev_map = _prev_signal_from_history(hist_obj, exclude_key=current_hist_key)

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

        prev_z60, prev_p60, ret1_pct, prev_value, last_value = _compute_prev_window_metrics(
            hl_by.get(sid, []),
            window_n=60
        )

        z_delta60 = (z60 - prev_z60) if (z60 is not None and prev_z60 is not None) else None
        p_delta60 = (p60_latest - prev_p60) if (p60_latest is not None and prev_p60 is not None) else None

        signal, tag, near, reason, jump_hits, hitbits = _signal_for_series(z60, p252, z_delta60, p_delta60, ret1_pct)

        dbg = _dbg_for_row(
            near=near,
            jump_hits=jump_hits,
            z_delta60=z_delta60,
            p_delta60=p_delta60,
            ret1_pct=ret1_pct,
            p60_latest=p60_latest,
            prev_p60=prev_p60,
            z60=z60,
            prev_z60=prev_z60,
            prev_value=prev_value,
            last_value=last_value,
        )

        prev_signal = prev_map.get(sid, "NA")
        delta_signal = _delta_signal(prev_signal, signal)
        streak_wa = _compute_streak(hist_obj, sid, signal, exclude_key=current_hist_key)

        dq = dq_map.get(sid, "OK")

        rows.append(Row(
            series=sid, dq=dq, age_h=age_h, data_date=data_date, value=value,
            z60=z60, p252=p252, p60_latest=p60_latest,
            prev_value=prev_value, last_value=last_value, prev_z60=prev_z60, prev_p60=prev_p60,
            z_delta60=z_delta60, p_delta60=p_delta60, ret1_pct=ret1_pct,
            jump_hits=jump_hits, hitbits=hitbits, dbg=dbg,
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

    near_n = sum(1 for r in rows if r.near != "NA")
    jump_1of3_n = sum(1 for r in rows if r.jump_hits == 1 and r.signal not in ("WATCH", "ALERT"))

    order = {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}
    rows.sort(key=lambda r: (order.get(r.signal, 9), r.series))

    md: List[str] = []
    md.append(f"# Risk Dashboard ({MODULE})\n")
    md.append(
        f"- Summary: ALERT={alert_n} / WATCH={watch_n} / INFO={info_n} / NONE={none_n}; "
        f"CHANGED={changed_n}; WATCH_STREAK>=3={watch_streak_ge3}; NEAR={near_n}; JUMP_1of3={jump_1of3_n}"
    )
    md.append(f"- RUN_TS_UTC: `{run_ts_utc.isoformat()}`")
    md.append(f"- STATS.generated_at_utc: `{stats.get('generated_at_utc','NA')}`")
    md.append(f"- STATS.as_of_ts: `{stats_as_of_ts}`")
    if stats_generated_at_utc:
        md.append(f"- STATS.generated_at_utc(norm): `{stats_generated_at_utc}`")
    if data_commit_sha:
        md.append(f"- STATS.data_commit_sha: `{data_commit_sha}`")
    md.append(f"- snapshot_id: `{snapshot_id}`")
    md.append(f"- streak_basis: `{STREAK_BASIS_TEXT}`")
    md.append(f"- streak_calc: `basis=snapshot_id; consecutive WATCH across prior distinct snapshots; re-run same snapshot excluded`")
    md.append(f"- script_version: `{script_version}`")
    md.append(f"- stale_hours: `{STALE_HOURS_DEFAULT}`")
    md.append(f"- dash_history: `{OUT_HISTORY}`")
    md.append(f"- history_lite_used_for_jump: `{PATH_HISTORY_LITE}`")
    md.append(f"- ret1_guard: `{RET1_GUARD_TEXT}`")
    md.append(f"- threshold_eps: `{TH_EPS_TEXT}`")
    md.append(f"- output_format: `{OUTPUT_FORMAT_TEXT}`")

    md.append(
        f"- alignment: `{align.get('alignment','NA')}`; checked={align.get('checked',0)}; "
        f"mismatch={align.get('mismatch',0)}; hl_missing={align.get('missing_hl',0)}"
    )
    ex = align.get("examples", [])
    if isinstance(ex, list) and ex:
        md.append(f"- alignment_examples: `{ ' | '.join(str(x) for x in ex) }`")

    md.append("- jump_calc: `ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)`")
    md.append(
        "- signal_rules: "
        "`Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); "
        "Jump(2/3 vote: abs(zΔ60)>=0.75, abs(pΔ60)>=20, abs(ret1%)>=2 -> WATCH); "
        "Near(within 10% of jump thresholds)`\n"
    )

    cols = [
        "Signal", "Tag", "Near",
        "JUMP_HITS", "HITBITS", "DBG",
        "PrevSignal", "DeltaSignal", "StreakWA",
        "Series", "DQ", "age_h", "data_date", "value", "z60", "p252",
        "z_delta60", "p_delta60", "ret1_pct", "Reason", "Source", "as_of_ts"
    ]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "|".join(["---"] * len(cols)) + "|")

    for r in rows:
        md.append("| " + " | ".join([
            r.signal, r.tag, r.near,
            str(r.jump_hits), r.hitbits, r.dbg,
            r.prev_signal, r.delta_signal, str(r.streak_wa),
            r.series, r.dq, _fmt_num(r.age_h, AGE_ND), r.data_date, _fmt_num(r.value, VALUE_ND),
            _fmt_num(r.z60, Z_ND), _fmt_num(r.p252, P_ND),
            _fmt_num(r.z_delta60, DELTA_ND), _fmt_num(r.p_delta60, DELTA_ND),
            _fmt_num(r.ret1_pct, RET1_ND),
            r.reason, r.source_url, r.as_of_ts
        ]) + " |")

    _write_text(OUT_MD, "\n".join(md) + "\n")

    new_item = {
        "run_ts_utc": run_ts_utc.isoformat(),
        "module": MODULE,
        "stats_as_of_ts": stats_as_of_ts,
        "stats_generated_at_utc": stats_generated_at_utc or None,
        "data_commit_sha": data_commit_sha or None,
        "snapshot_id": snapshot_id,
        "series_signals": series_signals_out,
    }

    items = hist_obj.get("items")
    if not isinstance(items, list):
        items = []

    key_order: List[Tuple[str, str]] = []
    last_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for it in items:
        if not isinstance(it, dict):
            continue
        k = _item_key(it)
        if k not in last_by_key:
            key_order.append(k)
        last_by_key[k] = it

    new_k = (MODULE, snapshot_id)
    if new_k not in last_by_key:
        key_order.append(new_k)
    last_by_key[new_k] = new_item

    norm_items = [last_by_key[k] for k in key_order]

    hist_obj["schema_version"] = "dash_history_v1"
    hist_obj["items"] = norm_items
    _write_text(OUT_HISTORY, json.dumps(hist_obj, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()