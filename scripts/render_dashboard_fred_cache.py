#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# =========================
# Configuration (ONE place)
# =========================

MODULE = "fred_cache"

STATS_PATH = "cache/stats_latest.json"
HISTORY_LITE_PATH = "cache/history_lite.json"

OUT_DIR = "dashboard_fred_cache"
OUT_MD = os.path.join(OUT_DIR, "dashboard.md")
OUT_HISTORY = os.path.join(OUT_DIR, "history.json")

STALE_HOURS_DEFAULT = 72.0

# --- Extreme thresholds ---
TH_Z_WATCH = 2.0
TH_Z_ALERT = 2.5

TH_P_INFO_HIGH = 95.0
TH_P_INFO_LOW = 5.0
TH_P_ALERT_LOW = 2.0  # <=2 => ALERT

# --- Jump thresholds (2/3 vote => WATCH) ---
TH_ZDELTA = 0.75
TH_PDELTA = 20.0
TH_RET1P = 2.0

# NEAR if within 10% below threshold
NEAR_RATIO = 0.90

# History cap (keep last N dashboard runs)
DASH_HISTORY_CAP = 400

# Compute prev-window z/p only if we have at least this many points in window
MIN_WINDOW_N_FOR_ZP = 10


# =========================
# Helpers
# =========================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def parse_iso_dt(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA" or s.lower() == "null":
            return None
        return float(s)
    except Exception:
        return None

def mean_std(values: List[float], ddof: int = 0) -> Tuple[Optional[float], Optional[float]]:
    n = len(values)
    if n == 0:
        return None, None
    mu = sum(values) / n
    if n - ddof <= 0:
        return mu, None
    var = sum((v - mu) ** 2 for v in values) / (n - ddof)
    sd = math.sqrt(var)
    return mu, sd

def percentile_le(values: List[float], x: float) -> Optional[float]:
    n = len(values)
    if n == 0:
        return None
    c = sum(1 for v in values if v <= x)
    return (c / n) * 100.0

def abs_or_none(x: Optional[float]) -> Optional[float]:
    return None if x is None else abs(x)

def fmt_num(x: Any, nd: int = 6) -> str:
    if x is None:
        return "NA"
    try:
        xf = float(x)
        if math.isnan(xf) or math.isinf(xf):
            return "NA"
        if abs(xf - round(xf)) < 1e-12:
            return str(int(round(xf)))
        return f"{xf:.{nd}f}".rstrip("0").rstrip(".")
    except Exception:
        return "NA"

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_json_array_or_jsonlines(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return []
    if text[0] == "[":
        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                return [x for x in arr if isinstance(x, dict)]
        except Exception:
            pass
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
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


# =========================
# Data models
# =========================

@dataclass
class JumpParts:
    z_delta60: Optional[float]
    p_delta60: Optional[float]
    ret1_pct: Optional[float]
    near_tokens: List[str]
    vote_hits: List[str]  # true hits only (for 2/3 vote)

@dataclass
class Row:
    series: str
    dq: str
    age_hours: float            # <-- FIX: add this
    data_date: str
    value: Optional[float]
    z60: Optional[float]
    p252: Optional[float]
    z_delta60: Optional[float]
    p_delta60: Optional[float]
    ret1_pct: Optional[float]
    source_url: str
    as_of_ts: str

    signal: str
    tag: str
    near: str
    reason: str

    prev_signal: str
    delta_signal: str
    streak_wa: int


# =========================
# Core computations
# =========================

def compute_jump_parts_for_series(
    stats_series_obj: Dict[str, Any],
    hist_values: List[Tuple[str, float]],
    ddof: int = 0,
) -> JumpParts:
    metrics = (stats_series_obj.get("metrics") or {})
    z60_latest = safe_float(metrics.get("z60"))
    p60_latest = safe_float(metrics.get("p60"))  # pΔ60 uses p60
    z_delta60: Optional[float] = None
    p_delta60: Optional[float] = None
    ret1_pct: Optional[float] = None
    near_tokens: List[str] = []
    true_hits: List[str] = []

    if len(hist_values) < 2:
        return JumpParts(None, None, None, ["NA"], [])

    prev_date, prev_val = hist_values[-2]
    latest_date, latest_val = hist_values[-1]

    if abs(prev_val) > 0:
        ret1_pct = (latest_val - prev_val) / abs(prev_val) * 100.0

    window_end_prev = [v for (_d, v) in hist_values[:-1]]
    window_prev = window_end_prev[-60:] if len(window_end_prev) >= 1 else []

    if len(window_prev) >= MIN_WINDOW_N_FOR_ZP and z60_latest is not None:
        mu, sd = mean_std(window_prev, ddof=ddof)
        if mu is not None and sd is not None and sd > 0:
            z60_prev = (prev_val - mu) / sd
            z_delta60 = z60_latest - z60_prev

    if len(window_prev) >= MIN_WINDOW_N_FOR_ZP and p60_latest is not None:
        p60_prev = percentile_le(window_prev, prev_val)
        if p60_prev is not None:
            p_delta60 = p60_latest - p60_prev

    def add_near(x: Optional[float], th: float, label: str) -> None:
        if x is None:
            return
        ax = abs(x)
        if ax >= th:
            near_tokens.append(f"NEAR:{label}")
        elif ax >= th * NEAR_RATIO:
            near_tokens.append(f"NEAR:{label}")

    def is_hit(x: Optional[float], th: float) -> bool:
        return (x is not None) and (abs(x) >= th)

    add_near(z_delta60, TH_ZDELTA, "ZΔ60")
    add_near(p_delta60, TH_PDELTA, "PΔ60")
    add_near(ret1_pct, TH_RET1P, "ret1%")

    if is_hit(z_delta60, TH_ZDELTA):
        true_hits.append("ZΔ60")
    if is_hit(p_delta60, TH_PDELTA):
        true_hits.append("PΔ60")
    if is_hit(ret1_pct, TH_RET1P):
        true_hits.append("ret1%")

    if not near_tokens:
        near_tokens = ["NA"]

    return JumpParts(z_delta60, p_delta60, ret1_pct, near_tokens, true_hits)


def decide_signal_tag_reason(
    z60: Optional[float],
    p252: Optional[float],
    jump: JumpParts,
) -> Tuple[str, str, str, str]:
    reasons: List[str] = []
    near = "+".join(jump.near_tokens) if jump.near_tokens else "NA"

    abs_z60 = abs_or_none(z60)
    vote_cnt = len(jump.vote_hits)
    jump_vote = vote_cnt >= 2

    is_alert = False
    is_watch = False
    is_info = False

    if abs_z60 is not None and abs_z60 >= TH_Z_ALERT:
        is_alert = True
        reasons.append(f"abs(Z60)>={fmt_num(TH_Z_ALERT, 2)}")
    if p252 is not None and p252 <= TH_P_ALERT_LOW:
        is_alert = True
        reasons.append(f"P252<={fmt_num(TH_P_ALERT_LOW, 2)}")

    if abs_z60 is not None and abs_z60 >= TH_Z_WATCH:
        is_watch = True
        reasons.append(f"abs(Z60)>={fmt_num(TH_Z_WATCH, 2)}")

    if jump_vote:
        is_watch = True
        comp = []
        if "ZΔ60" in jump.vote_hits:
            comp.append(f"abs(zΔ60)>={fmt_num(TH_ZDELTA, 2)}")
        if "PΔ60" in jump.vote_hits:
            comp.append(f"abs(pΔ60)>={fmt_num(TH_PDELTA, 2)}")
        if "ret1%" in jump.vote_hits:
            comp.append(f"abs(ret1%)>={fmt_num(TH_RET1P, 2)}")
        if comp:
            reasons.append(";".join(comp))

    if p252 is not None and (p252 >= TH_P_INFO_HIGH or p252 <= TH_P_INFO_LOW):
        is_info = True
        reasons.append(f"P252>=95" if p252 >= TH_P_INFO_HIGH else f"P252<=5")

    signal = "NONE"
    if is_alert:
        signal = "ALERT"
    elif is_watch:
        signal = "WATCH"
    elif is_info:
        signal = "INFO"

    tag = "NA"
    if signal == "ALERT":
        if p252 is not None and p252 <= TH_P_ALERT_LOW:
            tag = "EXTREME_P"
        else:
            tag = "EXTREME_Z"
    elif signal == "WATCH":
        if jump_vote:
            tag = "JUMP_DELTA" if (("ZΔ60" in jump.vote_hits) or ("PΔ60" in jump.vote_hits)) else "JUMP_RET"
        else:
            tag = "EXTREME_Z"
    elif signal == "INFO":
        tag = "LONG_EXTREME"

    if not reasons:
        reason = "NA"
    else:
        seen = set()
        uniq = []
        for r in reasons:
            if r not in seen:
                uniq.append(r)
                seen.add(r)
        reason = ";".join(uniq)

    return signal, tag, near, reason


def signal_priority(sig: str) -> int:
    return {"ALERT": 0, "WATCH": 1, "INFO": 2, "NONE": 3}.get(sig, 9)


# =========================
# Dashboard history
# =========================

def load_dash_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "dash_history_v1", "items": []}
    try:
        obj = load_json_file(path)
        if isinstance(obj, dict) and "items" in obj and isinstance(obj["items"], list):
            return obj
    except Exception:
        pass
    return {"schema_version": "dash_history_v1", "items": []}

def get_prev_series_signals(history_obj: Dict[str, Any]) -> Dict[str, str]:
    items = history_obj.get("items") or []
    if not items:
        return {}
    last = items[-1]
    ss = last.get("series_signals") or {}
    return {k: str(v) for k, v in ss.items()}

def get_prev_watch_streaks(history_obj: Dict[str, Any]) -> Dict[str, int]:
    items = history_obj.get("items") or []
    if not items:
        return {}
    last = items[-1]
    streaks = last.get("watch_streaks") or {}
    out: Dict[str, int] = {}
    if isinstance(streaks, dict):
        for k, v in streaks.items():
            try:
                out[k] = int(v)
            except Exception:
                out[k] = 0
    return out

def update_dash_history(
    history_obj: Dict[str, Any],
    run_ts_utc: str,
    stats_as_of_ts: str,
    module: str,
    series_signals: Dict[str, str],
    watch_streaks: Dict[str, int],
) -> Dict[str, Any]:
    items = history_obj.get("items") or []
    items.append({
        "run_ts_utc": run_ts_utc,
        "stats_as_of_ts": stats_as_of_ts,
        "module": module,
        "series_signals": series_signals,
        "watch_streaks": watch_streaks,
    })
    if len(items) > DASH_HISTORY_CAP:
        items = items[-DASH_HISTORY_CAP:]
    history_obj["schema_version"] = "dash_history_v1"
    history_obj["items"] = items
    return history_obj


# =========================
# Markdown rendering
# =========================

def md_escape(s: str) -> str:
    return s.replace("|", "\\|")

def render_markdown(
    module: str,
    run_ts_utc: str,
    stats_generated_at_utc: str,
    stats_as_of_ts: str,
    script_version: str,
    stale_hours: float,
    history_path: str,
    history_lite_path: str,
    jump_calc: str,
    signal_rules: str,
    rows: List[Row],
    summary: Dict[str, int],
) -> str:
    lines: List[str] = []
    lines.append(f"# Risk Dashboard ({module})")
    lines.append("")
    lines.append(
        f"- Summary: ALERT={summary['ALERT']} / WATCH={summary['WATCH']} / INFO={summary['INFO']} / NONE={summary['NONE']}; "
        f"CHANGED={summary['CHANGED']}; WATCH_STREAK>=3={summary['WATCH_STREAK_GTE3']}"
    )
    lines.append(f"- RUN_TS_UTC: `{run_ts_utc}`")
    lines.append(f"- STATS.generated_at_utc: `{stats_generated_at_utc}`")
    lines.append(f"- STATS.as_of_ts: `{stats_as_of_ts}`")
    lines.append(f"- script_version: `{script_version}`")
    lines.append(f"- stale_hours: `{fmt_num(stale_hours, 1)}`")
    lines.append(f"- dash_history: `{history_path}`")
    lines.append(f"- history_lite_used_for_jump: `{history_lite_path}`")
    lines.append(f"- jump_calc: `{jump_calc}`")
    lines.append(f"- signal_rules: `{signal_rules}`")
    lines.append("")
    lines.append("| Signal | Tag | Near | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct | Reason | Source | as_of_ts |")
    lines.append("|---|---|---|---|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|")

    for r in rows:
        lines.append(
            "| "
            + " | ".join([
                md_escape(r.signal),
                md_escape(r.tag),
                md_escape(r.near),
                md_escape(r.prev_signal),
                md_escape(r.delta_signal),
                str(r.streak_wa),
                md_escape(r.series),
                md_escape(r.dq),
                fmt_num(r.age_hours, 2),  # <-- now exists
                md_escape(r.data_date),
                fmt_num(r.value, 6),
                fmt_num(r.z60, 6),
                fmt_num(r.p252, 6),
                fmt_num(r.z_delta60, 6),
                fmt_num(r.p_delta60, 6),
                fmt_num(r.ret1_pct, 6),
                md_escape(r.reason),
                md_escape(r.source_url),
                md_escape(r.as_of_ts),
            ])
            + " |"
        )

    lines.append("")
    return "\n".join(lines)


# =========================
# Main
# =========================

def main() -> int:
    run_dt = utc_now()
    run_ts_utc = run_dt.isoformat()

    stats = load_json_file(STATS_PATH)
    stats_generated_at_utc = str(stats.get("generated_at_utc", "NA"))
    stats_as_of_ts = str(stats.get("as_of_ts", "NA"))
    script_version = str((stats.get("stats_policy") or {}).get("script_version", stats.get("script_version", "NA")))

    # age_h = RUN_TS_UTC - STATS.generated_at_utc (global, same for all rows)
    age_h: float = float("nan")
    try:
        gen_dt = parse_iso_dt(stats_generated_at_utc)
        age_h = (run_dt - gen_dt).total_seconds() / 3600.0
    except Exception:
        age_h = float("nan")

    stale_hours = safe_float(stats.get("stale_hours")) or STALE_HOURS_DEFAULT

    hist_recs = load_json_array_or_jsonlines(HISTORY_LITE_PATH)
    series_to_values: Dict[str, List[Tuple[str, float]]] = {}
    for rec in hist_recs:
        sid = rec.get("series_id") or rec.get("series") or rec.get("Series") or rec.get("id")
        if not sid:
            continue
        v = safe_float(rec.get("value"))
        d = rec.get("data_date") or rec.get("date") or rec.get("Date")
        if v is None or not d:
            continue
        series_to_values.setdefault(str(sid), []).append((str(d), float(v)))
    for sid, arr in series_to_values.items():
        arr.sort(key=lambda x: x[0])

    dash_hist = load_dash_history(OUT_HISTORY)
    prev_signals = get_prev_series_signals(dash_hist)
    prev_watch_streaks = get_prev_watch_streaks(dash_hist)

    stats_series = stats.get("series") or {}
    if not isinstance(stats_series, dict):
        raise RuntimeError("stats_latest.json: series field is not a dict")

    rows: List[Row] = []
    new_series_signals: Dict[str, str] = {}
    new_watch_streaks: Dict[str, int] = {}

    jump_calc = "ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)"
    signal_rules = (
        f"Extreme(abs(Z60)>={TH_Z_WATCH} (WATCH), abs(Z60)>={TH_Z_ALERT} (ALERT), "
        f"P252>={TH_P_INFO_HIGH} or <={TH_P_INFO_LOW} (INFO), P252<={TH_P_ALERT_LOW} (ALERT)); "
        f"Jump(2/3 vote: abs(zΔ60)>={TH_ZDELTA}, abs(pΔ60)>={TH_PDELTA}, abs(ret1%)>={TH_RET1P} -> WATCH); "
        f"Near(within {int((1-NEAR_RATIO)*100)}% of jump thresholds)"
    )

    ddof = int((stats.get("stats_policy") or {}).get("std_ddof", 0) or 0)

    for sid, sobj in stats_series.items():
        sid = str(sid)
        latest = (sobj.get("latest") or {})
        metrics = (sobj.get("metrics") or {})

        data_date = str(latest.get("data_date", "NA"))
        value = safe_float(latest.get("value"))
        z60 = safe_float(metrics.get("z60"))
        p252 = safe_float(metrics.get("p252"))
        source_url = str(latest.get("source_url", latest.get("source", "NA")))

        hist_vals = series_to_values.get(sid, [])
        jump = compute_jump_parts_for_series(
            stats_series_obj=sobj,
            hist_values=hist_vals,
            ddof=ddof,
        )

        signal, tag, near, reason = decide_signal_tag_reason(z60=z60, p252=p252, jump=jump)

        prev_sig = prev_signals.get(sid, "NONE")
        delta_signal = "SAME" if prev_sig == signal else f"{prev_sig}→{signal}"

        if signal == "WATCH":
            streak = (prev_watch_streaks.get(sid, 0) + 1) if prev_sig == "WATCH" else 1
        else:
            streak = 0

        new_series_signals[sid] = signal
        new_watch_streaks[sid] = streak

        dq = "OK"

        rows.append(Row(
            series=sid,
            dq=dq,
            age_hours=age_h,         # <-- FIX: populate
            data_date=data_date,
            value=value,
            z60=z60,
            p252=p252,
            z_delta60=jump.z_delta60,
            p_delta60=jump.p_delta60,
            ret1_pct=jump.ret1_pct,
            source_url=source_url,
            as_of_ts=stats_as_of_ts,

            signal=signal,
            tag=tag,
            near=near,
            reason=reason,

            prev_signal=prev_sig,
            delta_signal=delta_signal,
            streak_wa=streak,
        ))

    summary = {"ALERT": 0, "WATCH": 0, "INFO": 0, "NONE": 0, "CHANGED": 0, "WATCH_STREAK_GTE3": 0}
    for r in rows:
        summary[r.signal] += 1
        if r.delta_signal != "SAME":
            summary["CHANGED"] += 1
        if r.signal == "WATCH" and r.streak_wa >= 3:
            summary["WATCH_STREAK_GTE3"] += 1

    rows.sort(key=lambda r: (signal_priority(r.signal), r.series))

    ensure_dir(OUT_DIR)

    md = render_markdown(
        module=MODULE,
        run_ts_utc=run_ts_utc,
        stats_generated_at_utc=stats_generated_at_utc,
        stats_as_of_ts=stats_as_of_ts,
        script_version=script_version,
        stale_hours=stale_hours,
        history_path=OUT_HISTORY,
        history_lite_path=HISTORY_LITE_PATH,
        jump_calc=jump_calc,
        signal_rules=signal_rules,
        rows=rows,
        summary=summary,
    )

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    dash_hist = update_dash_history(
        dash_hist,
        run_ts_utc=run_ts_utc,
        stats_as_of_ts=stats_as_of_ts,
        module=MODULE,
        series_signals=new_series_signals,
        watch_streaks=new_watch_streaks,
    )
    with open(OUT_HISTORY, "w", encoding="utf-8") as f:
        json.dump(dash_hist, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())