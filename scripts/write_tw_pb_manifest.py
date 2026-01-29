#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Write tw_pb_cache/manifest.json pinned to a given data commit sha.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Dict


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data_sha = args.data_sha
    out = args.out

    repo = "${GITHUB_REPOSITORY}"  # expanded in workflow? keep literal safe if run locally
    # For local runs, user can edit manifest manually; workflow will regenerate with real repo env.

    manifest: Dict[str, object] = {
        "schema_version": "tw_pb_manifest_v1",
        "generated_at_utc": now_utc_iso(),
        "data_commit_sha": data_sha,
        "paths": {
            "history": f"https://raw.githubusercontent.com/{repo}/{data_sha}/tw_pb_cache/history.json",
            "latest": f"https://raw.githubusercontent.com/{repo}/{data_sha}/tw_pb_cache/latest.json",
            "stats_latest": f"https://raw.githubusercontent.com/{repo}/{data_sha}/tw_pb_cache/stats_latest.json",
            "report": f"https://raw.githubusercontent.com/{repo}/{data_sha}/tw_pb_cache/report.md",
        },
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()