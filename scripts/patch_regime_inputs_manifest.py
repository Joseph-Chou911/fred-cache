#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "regime_inputs_cache" / "manifest.json"

def iso_z_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="e.g. Joseph-Chou911/fred-cache")
    ap.add_argument("--data-sha", required=True, help="commit sha that contains the data files")
    ap.add_argument("--script-version", default="regime_inputs_manifest_v1")
    args = ap.parse_args()

    base = f"https://raw.githubusercontent.com/{args.repo}/{args.data_sha}/regime_inputs_cache"

    obj = {
        "generated_at_utc": iso_z_now(),
        "as_of_ts": iso_z_now(),
        "script_version": args.script_version,
        "data_commit_sha": args.data_sha,
        "pinned": {
            "latest_json": f"{base}/latest.json",
            "history_lite_json": f"{base}/history_lite.json",
            "dq_state_json": f"{base}/dq_state.json",
            "inputs_schema_out_json": f"{base}/inputs_schema_out.json"
        }
    }

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())