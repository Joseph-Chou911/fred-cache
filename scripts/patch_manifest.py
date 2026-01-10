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
    if not isinstance(obj, dict):
        raise SystemExit("cache/manifest.json is not a JSON object")

    # keep existing fields if present
    obj.setdefault("pinned", {})
    obj.setdefault("paths", {})
    obj.setdefault("fs_status", {})

    pinned = obj["pinned"]
    if not isinstance(pinned, dict):
        pinned = {}
        obj["pinned"] = pinned

    base_data = f"https://raw.githubusercontent.com/{repo}/{data_sha}/cache"
    base_main = f"https://raw.githubusercontent.com/{repo}/refs/heads/main/cache"

    # -----------------------------
    # Always pin "data files" to DATA_SHA
    # -----------------------------
    obj["data_commit_sha"] = data_sha

    pinned.update(
        {
            "latest_json": f"{base_data}/latest.json",
            "history_json": f"{base_data}/history.json",
            "history_lite_json": f"{base_data}/history_lite.json",
            "latest_csv": f"{base_data}/latest.csv",
        }
    )

    # Optional but recommended: if these exist in your repo, also pin them to DATA_SHA
    # (Won't break even if consumer ignores them; but helps auditing.)
    # If you don't generate these files, you can remove these keys.
    pinned.setdefault("dq_state_json", f"{base_data}/dq_state.json")
    pinned.setdefault("backfill_state_json", f"{base_data}/backfill_state.json")
    pinned.setdefault("history_snapshot_json", f"{base_data}/history.snapshot.json")

    # -----------------------------
    # Fallback pins (safe defaults)
    # These ensure even if "manifest pin step" fails, you still have usable links.
    # -----------------------------
    pinned.setdefault("manifest_json", f"{base_main}/manifest.json")
    pinned.setdefault("stats_latest_json", f"{base_main}/stats_latest.json")

    # -----------------------------
    # mode=manifest: pin snapshot URLs to MANIFEST_SHA
    # -----------------------------
    if mode == "manifest":
        if not manifest_sha:
            raise SystemExit("--manifest-sha is required when mode=manifest")

        base_manifest = f"https://raw.githubusercontent.com/{repo}/{manifest_sha}/cache"

        # Pin BOTH manifest and stats to MANIFEST_SHA (derived/audit artifacts)
        pinned["manifest_json"] = f"{base_manifest}/manifest.json"
        pinned["stats_latest_json"] = f"{base_manifest}/stats_latest.json"

        obj["manifest_commit_sha"] = manifest_sha
        obj["manifest_commit_sha_v1"] = manifest_sha

    MANIFEST_PATH.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
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