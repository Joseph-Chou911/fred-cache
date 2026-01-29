#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = "Asia/Taipei"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    now_local = datetime.now(ZoneInfo(TZ))
    now_utc = now_local.astimezone(timezone.utc)
    repo = os.environ.get("GITHUB_REPOSITORY", "UNKNOWN/UNKNOWN")

    manifest = {
        "schema_version": "tw_pb_sidecar_manifest_v1",
        "generated_at_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_at_local": now_local.isoformat(),
        "timezone": TZ,
        "data_commit_sha": args.data_sha,
        "paths": {
            "latest": "tw_pb_cache/latest.json",
            "history": "tw_pb_cache/history.json",
            "stats_latest": "tw_pb_cache/stats_latest.json",
            "report": "tw_pb_cache/report.md",
        },
        "pinned_urls": {
            "latest": f"https://raw.githubusercontent.com/{repo}/{args.data_sha}/tw_pb_cache/latest.json",
            "history": f"https://raw.githubusercontent.com/{repo}/{args.data_sha}/tw_pb_cache/history.json",
            "stats_latest": f"https://raw.githubusercontent.com/{repo}/{args.data_sha}/tw_pb_cache/stats_latest.json",
            "report": f"https://raw.githubusercontent.com/{repo}/{args.data_sha}/tw_pb_cache/report.md",
        },
        "notes": "THIRD_PARTY source (wantgoo).",
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()