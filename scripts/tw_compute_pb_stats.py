#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        return None, None, f"INSUFFICIENT_HISTORY:{len(values)}/{n}"
    w = values[-n:]
    x = w[-1]
    mu = _mean(w)
    sd = _std_pop(w, mu)
    if sd == 0:
        return 0.0, _percentile_leq(w, x), "STD_ZERO"
    return (x - mu) / sd, _percentile_leq(w, x), None


def main() -> None:
    meta = _now()
    hist = _read_json(IN_HIST, default=[])
    latest = _read_json(IN_LATEST, default={})

    pbr_series = [r["pbr"] for r in hist if isinstance(r.get("pbr"), (int, float))]

    z60, p60, r60 = _calc_window(pbr_series, 60)
    z252, p252, r252 = _calc_window(pbr_series, 252)

    out = {
        "schema_version": "tw_pb_sidecar_stats_latest_v2",
        "script_fingerprint": "tw_compute_pb_stats_py@v2_pbr_only",
        **meta,
        "source_vendor": latest.get("source_vendor"),
        "source_url": latest.get("source_url"),
        "freq": latest.get("freq"),
        "data_date": latest.get("data_date"),
        "period_ym": latest.get("period_ym"),
        "fetch_status": latest.get("fetch_status"),
        "confidence": latest.get("confidence"),
        "dq_reason": latest.get("dq_reason"),
        "series_len": len(pbr_series),
        "pbr": {
            "value": latest.get("pbr"),
            "z60": z60,
            "p60": p60,
            "z252": z252,
            "p252": p252,
            "na_reason_60": r60,
            "na_reason_252": r252,
        },
        "notes": "MONTHLY series. z/p windows are observation-count based. Expect z252/p252 to be NA until >=252 monthly points exist.",
    }

    _write_json(OUT_STATS, out)
    print("Wrote:", OUT_STATS)


if __name__ == "__main__":
    main()