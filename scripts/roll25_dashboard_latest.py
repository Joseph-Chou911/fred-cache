#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roll25_dashboard_latest.py

Build roll25_cache/dashboard_latest.json from local roll25_cache/roll25.json + latest_report.json only.
NO external fetch.

Goal:
- Provide a market_cache-like stats table with:
  value, z60, p60, z252, p252, zΔ60, pΔ60, ret1_pct
- Deterministic, NA-safe, auditable.
- Does NOT modify any existing files; it only writes dashboard_latest.json.

Definitions (audit-friendly):
- Window stats (z/p) computed on "level" series values within last N points (including today/as_of).
- z-score uses population std (ddof=0) to match existing update_twse_sidecar.py behavior.
- Percentile is tie-aware: pct = 100*(#less + 0.5*#equal)/n
- delta60(t) = value(t) - value(t+60) in date-desc indexing (t is newer)
- zΔ60/pΔ60 computed from last 60 delta60 points (when available)
- ret1_pct(t) = (value(t) - value(t+1)) / abs(value(t+1)) * 100

Series built:
- TURNOVER_TWD: trade_value
- CLOSE: close
- PCT_CHANGE_CLOSE: derived from CLOSE ret1% (same as close daily return)
- AMPLITUDE_PCT: derived per day using (high-low)/prev_close*100 when high/low and prev_close exist
- VOL_MULTIPLIER_20: derived per day using tv_t / avg(tv_{t..t+19}); requires min_points

Outputs:
- roll25_cache/dashboard_latest.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _atomic_write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
    os.replace(tmp, path)


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        s = str(x).strip().replace(",", "")
        if s in ("", "NA", "na", "null", "-", "—"):
            return None
        return float(s)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    v = _safe_float(x)
    if v is None:
        return None
    try:
        return int(round(v))
    except Exception:
        return None


def _avg(xs: List[float]) -> Optional[float]:
    return None if not xs else (sum(xs) / len(xs))


def _std_pop(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    mu = _avg(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / len(xs)  # ddof=0
    return math.sqrt(max(var, 0.0))


def _percentile_tie_aware(x: float, xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    less = sum(1 for v in xs if v < x)
    eq = sum(1 for v in xs if v == x)
    n = len(xs)
    return 100.0 * (less + 0.5 * eq) / n


def _window_take(values_desc: List[Tuple[str, float]], win: int) -> List[float]:
    xs: List[float] = []
    for _, v in values_desc:
        xs.append(float(v))
        if len(xs) >= win:
            break
    return xs


def _calc_zp(value: Optional[float], window_values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if value is None or not window_values:
        return None, None
    mu = _avg(window_values)
    sd = _std_pop(window_values)
    z = None
    if mu is not None and sd is not None and sd != 0:
        z = (float(value) - mu) / sd
    p = _percentile_tie_aware(float(value), window_values)
    return (None if z is None else round(float(z), 6),
            None if p is None else round(float(p), 3))


def _build_values_desc(rows_desc: List[Dict[str, Any]], key: str) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for r in rows_desc:
        d = r.get("date")
        if not isinstance(d, str):
            continue
        v = _safe_float(r.get(key))
        if v is None:
            continue
        out.append((d, float(v)))
    return out  # already desc if rows_desc is desc


def _ret1_pct_from_values_desc(values_desc: List[Tuple[str, float]]) -> Optional[float]:
    if len(values_desc) < 2:
        return None
    v0 = values_desc[0][1]
    v1 = values_desc[1][1]
    if v1 == 0:
        return None
    return round((v0 - v1) / abs(v1) * 100.0, 6)


def _delta60_series_desc(values_desc: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    # values_desc is newest->oldest
    vs = [v for _, v in values_desc]
    ds = [d for d, _ in values_desc]
    out: List[Tuple[str, float]] = []
    for i in range(len(vs)):
        j = i + 60
        if j >= len(vs):
            break
        out.append((ds[i], float(vs[i]) - float(vs[j])))
    return out  # newest->older, aligned with ds


def _calc_row_stats(series_name: str, values_desc: List[Tuple[str, float]]) -> Dict[str, Any]:
    value = values_desc[0][1] if values_desc else None
    data_date = values_desc[0][0] if values_desc else "NA"

    win60 = _window_take(values_desc, 60)
    win252 = _window_take(values_desc, 252)

    z60, p60 = _calc_zp(value, win60)
    z252, p252 = _calc_zp(value, win252)

    # delta60 stats
    d60_desc = _delta60_series_desc(values_desc)
    d60_value = d60_desc[0][1] if d60_desc else None
    d60_win = _window_take(d60_desc, 60)
    zD60, pD60 = _calc_zp(d60_value, d60_win)

    ret1 = _ret1_pct_from_values_desc(values_desc)

    return {
        "series": series_name,
        "data_date": data_date,
        "value": value,
        "z60": z60,
        "p60": p60,
        "z252": z252,
        "p252": p252,
        "zD60": zD60,
        "pD60": pD60,
        "ret1_pct": ret1,
        "window_note": {
            "n_level_available": len(values_desc),
            "n_delta60_available": len(d60_desc),
        },
    }


def _derive_amplitude_pct_rows(rows_desc: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    # amplitude(date) needs high/low of that date + prev_close (next older date close)
    out: List[Tuple[str, float]] = []
    for i in range(len(rows_desc) - 1):
        r = rows_desc[i]
        r_prev = rows_desc[i + 1]
        d = r.get("date")
        if not isinstance(d, str):
            continue
        high = _safe_float(r.get("high"))
        low = _safe_float(r.get("low"))
        prev_close = _safe_float(r_prev.get("close"))
        if high is None or low is None or prev_close is None or prev_close == 0:
            continue
        amp = (high - low) / prev_close * 100.0
        out.append((d, float(amp)))
    return out


def _derive_pct_change_close_rows(rows_desc: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for i in range(len(rows_desc) - 1):
        r = rows_desc[i]
        r_prev = rows_desc[i + 1]
        d = r.get("date")
        if not isinstance(d, str):
            continue
        c0 = _safe_float(r.get("close"))
        c1 = _safe_float(r_prev.get("close"))
        if c0 is None or c1 is None or c1 == 0:
            continue
        out.append((d, (c0 - c1) / c1 * 100.0))
    return out


def _derive_vol_multiplier_20_rows(rows_desc: List[Dict[str, Any]], win: int = 20, min_points: int = 15) -> List[Tuple[str, float]]:
    # multiplier(date i) = tv_i / avg(tv_i..tv_{i+win-1}), requires enough points in that window
    tvs: List[Optional[float]] = [_safe_float(r.get("trade_value")) for r in rows_desc]
    dates: List[str] = [str(r.get("date")) for r in rows_desc]
    out: List[Tuple[str, float]] = []
    for i in range(len(rows_desc)):
        window = tvs[i:i + win]
        window_clean = [x for x in window if x is not None]
        if len(window_clean) < min_points:
            continue
        tv0 = tvs[i]
        if tv0 is None:
            continue
        mu = sum(window_clean) / len(window_clean)
        if mu == 0:
            continue
        out.append((dates[i], float(tv0) / float(mu)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roll", default="roll25_cache/roll25.json")
    ap.add_argument("--latest", default="roll25_cache/latest_report.json")
    ap.add_argument("--out", default="roll25_cache/dashboard_latest.json")
    ap.add_argument("--vol-win", type=int, default=20)
    ap.add_argument("--vol-min-points", type=int, default=15)
    args = ap.parse_args()

    roll_obj = _read_json(args.roll)
    latest = _read_json(args.latest)

    if not isinstance(roll_obj, list):
        raise SystemExit("[FATAL] roll25.json must be a JSON list.")

    used_date = None
    nums = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    if isinstance(nums.get("UsedDate"), str):
        used_date = nums["UsedDate"]

    if not isinstance(used_date, str) or not used_date:
        raise SystemExit("[FATAL] latest_report.json missing numbers.UsedDate")

    # filter rows <= used_date
    rows = [r for r in roll_obj if isinstance(r, dict) and isinstance(r.get("date"), str)]
    rows = [r for r in rows if str(r.get("date")) <= used_date]
    rows.sort(key=lambda x: str(x.get("date")), reverse=True)

    if not rows:
        raise SystemExit("[FATAL] no eligible rows <= UsedDate.")

    # core level series from roll25.json
    turnover_desc = _build_values_desc(rows, "trade_value")
    close_desc = _build_values_desc(rows, "close")

    # derived series
    amp_desc = _derive_amplitude_pct_rows(rows)
    pctchg_close_desc = _derive_pct_change_close_rows(rows)
    volmult_desc = _derive_vol_multiplier_20_rows(rows, win=args.vol_win, min_points=args.vol_min_points)

    table: List[Dict[str, Any]] = []
    table.append(_calc_row_stats("TURNOVER_TWD", turnover_desc))
    table.append(_calc_row_stats("CLOSE", close_desc))
    table.append(_calc_row_stats("PCT_CHANGE_CLOSE", pctchg_close_desc))
    table.append(_calc_row_stats("AMPLITUDE_PCT", amp_desc))
    table.append(_calc_row_stats(f"VOL_MULTIPLIER_{args.vol_win}", volmult_desc))

    # add a simple confidence flag per series (based on 60/252 availability)
    for row in table:
        n_level = row.get("window_note", {}).get("n_level_available", 0)
        conf = "OK"
        if not isinstance(n_level, int) or n_level < 60:
            conf = "DOWNGRADED"
        row["confidence"] = conf
        # z252/p252 only meaningful when >=252
        row["window_note"]["has_252_full"] = bool(isinstance(n_level, int) and n_level >= 252)

    out = {
        "schema_version": "roll25_dashboard_latest_v1",
        "generated_at_utc": _now_utc_z(),
        "inputs": {
            "roll25_json": args.roll,
            "latest_report": args.latest,
        },
        "as_of": {
            "UsedDate": used_date,
            "used_date_status": latest.get("used_date_status") if isinstance(latest.get("used_date_status"), str) else nums.get("UsedDateStatus"),
            "run_day_tag": latest.get("run_day_tag") if isinstance(latest.get("run_day_tag"), str) else None,
        },
        "calc_policy": {
            "zscore_ddof": 0,
            "percentile": "tie_aware",
            "delta60": "value(t) - value(t+60) in date-desc indexing",
            "ret1_pct": "(v0 - v1)/abs(v1)*100",
            "vol_multiplier": {
                "win": args.vol_win,
                "min_points": args.vol_min_points,
                "definition": "tv_t / avg(tv_t..tv_{t+win-1})",
            },
        },
        "table": table,
        "notes": [
            "NO external fetch; computed from local roll25.json only.",
            "If insufficient points, z/p/delta stats are NA (no guessing).",
        ],
    }

    _atomic_write_json(args.out, out)
    print(f"OK wrote: {args.out} (UsedDate={used_date}, rows_used={len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())