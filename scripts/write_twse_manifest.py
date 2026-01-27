#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

DEFAULT_OUT = "roll25_cache/manifest.json"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True, help="Commit SHA that contains data files")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        print("[FATAL] GITHUB_REPOSITORY env missing.")
        sys.exit(1)

    data_sha = args.data_sha.strip()
    out_path = args.out

    def raw_url(sha: str, path: str) -> str:
        return f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"

    manifest: Dict[str, Any] = {
        "schema_version": "twse_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo": repo,
        "data_commit_sha": data_sha,
        "paths": {
            "roll25": "roll25_cache/roll25.json",
            "latest_report": "roll25_cache/latest_report.json",
            "stats_latest": "roll25_cache/stats_latest.json"
        },
        "urls": {
            "roll25_pinned": raw_url(data_sha, "roll25_cache/roll25.json"),
            "latest_report_pinned": raw_url(data_sha, "roll25_cache/latest_report.json"),
            "stats_latest_pinned": raw_url(data_sha, "roll25_cache/stats_latest.json"),
            "manifest_main": f"https://raw.githubusercontent.com/{repo}/refs/heads/main/{out_path}"
        }
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=False)

    print(f"Wrote manifest: {out_path}")
    print(f"data_commit_sha={data_sha}")

if __name__ == "__main__":
    main()