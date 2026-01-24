#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def try_read(path: str) -> Dict[str, Any]:
    p = Path(path)
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def outcome_to_status(outcome: str) -> str:
    # steps.<id>.outcome: success | failure | cancelled | skipped
    if outcome == "success":
        return "OK"
    if outcome in ("failure", "cancelled"):
        return "FAILED"
    return "MISSING"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market_in", required=True)
    ap.add_argument("--fred_in", required=True)
    ap.add_argument("--twmargin_in", required=True)
    ap.add_argument("--market_outcome", required=True)
    ap.add_argument("--fred_outcome", required=True)
    ap.add_argument("--twmargin_outcome", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    market = try_read(args.market_in)
    fred = try_read(args.fred_in)
    twm = try_read(args.twmargin_in)

    unified = {
        "schema_version": "unified_dashboard_latest_v1",
        "generated_at_utc": now_utc(),
        "inputs": {
            "market_in": args.market_in,
            "fred_in": args.fred_in,
            "twmargin_in": args.twmargin_in,
        },
        "modules": {
            "market_cache": {
                "status": outcome_to_status(args.market_outcome),
                "dashboard_latest": market if market else None,
            },
            "fred_cache": {
                "status": outcome_to_status(args.fred_outcome),
                "dashboard_latest": fred if fred else None,
            },
            "taiwan_margin_financing": {
                "status": outcome_to_status(args.twmargin_outcome),
                "latest": twm if twm else None,   # 你這份檔名就是 latest.json
            },
        }
    }

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()