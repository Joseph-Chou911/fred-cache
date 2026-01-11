#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
market_cache/patch_manifest_market_cache.py

Patch market_cache/manifest.json to pin raw URLs to a specific DATA_SHA.
This is intentionally separated so workflow can:
1) commit data files -> get DATA_SHA
2) patch manifest to point to DATA_SHA -> commit manifest
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import argparse

MANIFEST_PATH = Path("market_cache/manifest.json")

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo, e.g. Joseph-Chou911/fred-cache")
    ap.add_argument("--data-sha", required=True, help="commit sha that contains data files")
    args = ap.parse_args()

    if not MANIFEST_PATH.exists():
        # create a minimal manifest if missing
        obj = {}
    else:
        obj = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    as_of_ts = utc_now_iso()
    base = f"https://raw.githubusercontent.com/{args.repo}/{args.data_sha}/market_cache"

    obj.update({
        "generated_at_utc": as_of_ts,
        "as_of_ts": as_of_ts,
        "data_commit_sha": args.data_sha,
        "pinned": {
            "latest_json": f"{base}/latest.json",
            "history_lite_json": f"{base}/history_lite.json",
            "stats_latest_json": f"{base}/stats_latest.json",
        },
        "paths": {
            "latest_json": "market_cache/latest.json",
            "history_lite_json": "market_cache/history_lite.json",
            "stats_latest_json": "market_cache/stats_latest.json",
            "manifest_json": "market_cache/manifest.json",
        },
    })

    MANIFEST_PATH.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] patched {MANIFEST_PATH} -> data_sha={args.data_sha}")

if __name__ == "__main__":
    main()