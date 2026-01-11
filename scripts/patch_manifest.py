#!/usr/bin/env python3
# scripts/patch_manifest.py
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

MANIFEST_PATH = Path("cache/manifest.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--path", default=str(MANIFEST_PATH))
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        raise SystemExit(f"{p} not found")

    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit("manifest.json is not a JSON object")

    repo = args.repo.strip()
    data_sha = args.data_sha.strip()

    base_data = f"https://raw.githubusercontent.com/{repo}/{data_sha}/cache"

    # Overwrite pinned fully (NO setdefault;避免殘留舊值)
    obj["data_commit_sha"] = data_sha
    obj.setdefault("pinned", {})
    if not isinstance(obj["pinned"], dict):
        obj["pinned"] = {}

    obj["pinned"] = {
        "latest_json": f"{base_data}/latest.json",
        "history_json": f"{base_data}/history.json",
        "history_lite_json": f"{base_data}/history_lite.json",
        "stats_latest_json": f"{base_data}/stats_latest.json",
        "latest_csv": f"{base_data}/latest.csv",
        "dq_state_json": f"{base_data}/dq_state.json",
        "backfill_state_json": f"{base_data}/backfill_state.json",
        "history_snapshot_json": f"{base_data}/history.snapshot.json",

        # 你要的：manifest_json 也指到 DATA_SHA
        "manifest_json": f"{base_data}/manifest.json",
    }

    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] patched manifest pinned.* -> DATA_SHA={data_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())