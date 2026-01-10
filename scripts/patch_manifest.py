#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

MANIFEST_PATH = Path("cache/manifest.json")

def patch(repo: str, data_sha: str, manifest_sha: str | None, mode: str) -> None:
    if not MANIFEST_PATH.exists():
        raise SystemExit("cache/manifest.json not found")

    obj = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    # keep existing fields if present
    obj.setdefault("pinned", {})
    obj.setdefault("paths", {})
    obj.setdefault("fs_status", {})

    base_data = f"https://raw.githubusercontent.com/{repo}/{data_sha}/cache"

    # Always pin to DATA_SHA for data files
    obj["data_commit_sha"] = data_sha
    obj["pinned"].update({
        "latest_json": f"{base_data}/latest.json",
        "history_json": f"{base_data}/history.json",
        "history_lite_json": f"{base_data}/history_lite.json",
        "stats_latest_json": f"{base_data}/stats_latest.json",
        "latest_csv": f"{base_data}/latest.csv",
        # fallback: still reachable even if snapshot pin step fails
        "manifest_json": f"https://raw.githubusercontent.com/{repo}/refs/heads/main/cache/manifest.json",
    })

    if mode == "manifest":
        if not manifest_sha:
            raise SystemExit("--manifest-sha is required when mode=manifest")
        base_manifest = f"https://raw.githubusercontent.com/{repo}/{manifest_sha}/cache"
        obj["pinned"]["manifest_json"] = f"{base_manifest}/manifest.json"
        obj["manifest_commit_sha"] = manifest_sha
        obj["manifest_commit_sha_v1"] = manifest_sha

    MANIFEST_PATH.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--manifest-sha", default=None)
    ap.add_argument("--mode", choices=["data", "manifest"], required=True)
    args = ap.parse_args()

    patch(args.repo, args.data_sha, args.manifest_sha, args.mode)
    print(f"[OK] patched manifest: mode={args.mode}")

if __name__ == "__main__":
    main()