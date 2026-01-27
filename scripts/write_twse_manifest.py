#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True, help="Git commit SHA that contains the updated data files")
    ap.add_argument("--out", required=True, help="Output manifest path (e.g., roll25_cache/manifest.json)")
    args = ap.parse_args()

    data_sha = args.data_sha.strip()

    # IMPORTANT: do not hardcode repo; GitHub Actions will show GITHUB_REPOSITORY, but this script is generic.
    # The workflow prints snapshot URLs; this manifest is a machine-readable "pinned pointers" object.
    manifest = {
        "schema_version": "twse_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "data_commit_sha": data_sha,
        "paths": {
            "roll25": "roll25_cache/roll25.json",
            "latest_report": "roll25_cache/latest_report.json",
            "stats_latest": "roll25_cache/stats_latest.json",
        },
        "pinned_raw_urls": {
            "roll25": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/roll25_cache/roll25.json",
            "latest_report": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/roll25_cache/latest_report.json",
            "stats_latest": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/roll25_cache/stats_latest.json",
        },
        "notes": [
            "Replace {REPO} with your GitHub repository (owner/repo).",
            "This manifest is pinned to data_commit_sha and should be immutable once committed.",
        ]
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Wrote manifest: {args.out}")
    print(f"data_commit_sha={data_sha}")

if __name__ == "__main__":
    main()