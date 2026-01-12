#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_PATH = Path("market_cache/manifest.json")


def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_manifest(repo: str, data_sha: str) -> dict:
    now = utc_now_iso_z()
    base = f"https://raw.githubusercontent.com/{repo}/{data_sha}/market_cache"

    return {
        "generated_at_utc": now,
        "as_of_ts": now,
        "data_commit_sha": data_sha,
        "pinned": {
            "latest_json": f"{base}/latest.json",
            "history_lite_json": f"{base}/history_lite.json",
            "stats_latest_json": f"{base}/stats_latest.json",
            "dq_state_json": f"{base}/dq_state.json",
        },
        "paths": {
            "latest_json": "market_cache/latest.json",
            "history_lite_json": "market_cache/history_lite.json",
            "stats_latest_json": "market_cache/stats_latest.json",
            "dq_state_json": "market_cache/dq_state.json",
            "manifest_json": "market_cache/manifest.json",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="e.g. Joseph-Chou911/fred-cache (from GITHUB_REPOSITORY)")
    ap.add_argument("--data-sha", required=True, help="commit sha that contains the data files")
    args = ap.parse_args()

    repo = args.repo.strip()
    data_sha = args.data_sha.strip()

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    if MANIFEST_PATH.exists():
        # patch in-place but keep unknown fields if user adds later
        obj = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        patched = build_manifest(repo, data_sha)

        # keep extra top-level keys if any, but refresh core fields
        obj["generated_at_utc"] = patched["generated_at_utc"]
        obj["as_of_ts"] = patched["as_of_ts"]
        obj["data_commit_sha"] = patched["data_commit_sha"]

        obj.setdefault("pinned", {})
        obj.setdefault("paths", {})

        obj["pinned"].update(patched["pinned"])
        obj["paths"].update(patched["paths"])
    else:
        obj = build_manifest(repo, data_sha)

    MANIFEST_PATH.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[OK] patched market_cache/manifest.json (pinned + paths, include dq_state_json)")


if __name__ == "__main__":
    main()