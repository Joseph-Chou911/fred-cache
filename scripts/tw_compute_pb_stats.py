#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute z60/p60 and z252/p252 for PBR (and PER/Yield, optional).

Inputs:
- tw_pb_cache/history.json
- tw_pb_cache/latest.json

Output:
- tw_pb_cache/stats_latest.json

Rules:
- If insufficient history => stats fields are NA with reason.
- Windows are N=60 and N=252 observations (not necessarily trading days; depends on update frequency).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

TZ = "Asia/Taipei"
IN_HIST = "tw_pb_cache/history.json"
IN_LATEST = "tw_pb_cache/latest.json"
OUT_STATS = "tw_pb_cache/stats_latest.json"


def _now() -> Dict[str, str]:
    now_local = datetime.now(ZoneInfo(TZ))
    now_utc = now_local.astimezone(timezone.utc)
    return {
        "generated_at_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_at_local": now_local.isoformat(),
        "timezone": TZ,
    }


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs)


def _std_pop(xs: List[float], mu: float) -> float:
    var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return var ** 0.5


def _percentile_leq(xs: List[float], x: float) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    c = sum(1 for v in xs if v <= x)
    return 100.0 * c / n


def _calc_window(values: List[float], n: int) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    if len(values) < n:
        return None, None, f"insufficient_history:{len(values)}/{n}"
    w = values[-n:]
    x = w[-1]
    mu = _mean(w)
    sd = _std_pop(w, mu)
    if sd == 0:
        z = 0.0
        reason = "std_zero"
    else:
        z = (x - mu) / sd
        reason = None
    p = _percentile_leq(w, x)
    return z, p, reason


def main() -> None:
    meta = _now()
    hist = _read_json(IN_HIST, default=[])
    latest = _read_json(IN_LATEST, default={})

    pbr_series = [r["pbr"] for r in hist if isinstance(r.get("pbr"), (int, float))]
    per_series = [r["per"] for r in hist if isinstance(r.get("per"), (int, float))]
    yld_series = [r["dividend_yield_pct"] for r in hist if isinstance(r.get("dividend_yield_pct"), (int, float))]

    z60_pbr, p60_pbr, r60_pbr = _calc_window(pbr_series, 60)
    z252_pbr, p252_pbr, r252_pbr = _calc_window(pbr_series, 252)

    z60_per, p60_per, r60_per = _calc_window(per_series, 60)
    z252_per, p252_per, r252_per = _calc_window(per_series, 252)

    z60_y, p60_y, r60_y = _calc_window(yld_series, 60)
    z252_y, p252_y, r252_y = _calc_window(yld_series, 252)

    out = {
        "schema_version": "tw_pb_sidecar_stats_latest_v1",
        "script_fingerprint": "tw_compute_pb_stats_py@v1",
        **meta,
        "source_vendor": latest.get("source_vendor"),
        "source_url": latest.get("source_url"),
        "data_date": latest.get("data_date"),
        "fetch_status": latest.get("fetch_status"),
        "confidence": latest.get("confidence"),
        "dq_reason": latest.get("dq_reason"),
        "series_len": {
            "pbr": len(pbr_series),
            "per": len(per_series),
            "dividend_yield_pct": len(yld_series),
        },
        "pbr": {
            "value": latest.get("pbr"),
            "z60": z60_pbr,
            "p60": p60_pbr,
            "z252": z252_pbr,
            "p252": p252_pbr,
            "na_reason_60": r60_pbr,
            "na_reason_252": r252_pbr,
        },
        "per": {
            "value": latest.get("per"),
            "z60": z60_per,
            "p60": p60_per,
            "z252": z252_per,
            "p252": p252_per,
            "na_reason_60": r60_per,
            "na_reason_252": r252_per,
        },
        "dividend_yield_pct": {
            "value": latest.get("dividend_yield_pct"),
            "z60": z60_y,
            "p60": p60_y,
            "z252": z252_y,
            "p252": p252_y,
            "na_reason_60": r60_y,
            "na_reason_252": r252_y,
        },
        "notes": "Windows are observation-count based (60/252 points). Frequency depends on workflow schedule.",
    }

    _write_json(OUT_STATS, out)
    print("Wrote:", OUT_STATS)


if __name__ == "__main__":
    main()