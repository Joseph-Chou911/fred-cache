#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo


def raw_url(repo: str, sha: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path.lstrip('/')}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True, help="Commit SHA that contains the data files (roll25 + latest_report).")
    ap.add_argument("--out", required=True, help="Output path for manifest.json (e.g., roll25_cache/manifest.json).")
    args = ap.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "<OWNER>/<REPO>")
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz).isoformat()

    data_sha = args.data_sha.strip()

    manifest = {
        "generated_at_taipei": now,
        "as_of_ts": now,

        # Authoritative immutable snapshot for DATA
        "data_commit_sha": data_sha,

        # Convenience URL (latest). This one is NOT immutable.
        "main_manifest_url": raw_url(repo, "refs/heads/main", "roll25_cache/manifest.json"),

        # Pinned immutable URLs for DATA snapshot
        "pinned_data": {
            "schema_json": raw_url(repo, data_sha, "roll25_cache/twse_schema.json"),
            "roll25_json": raw_url(repo, data_sha, "roll25_cache/roll25.json"),
            "latest_report_json": raw_url(repo, data_sha, "roll25_cache/latest_report.json"),
        },
    }

    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=False)

    print(f"manifest written: {out_path}")
    print(f"data_commit_sha: {data_sha}")


if __name__ == "__main__":
    main()