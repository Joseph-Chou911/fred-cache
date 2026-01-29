#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tz", default="Asia/Taipei")
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    gen_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    gen_local = datetime.now(tz).isoformat()

    data_sha = args.data_sha
    # NOTE: repo name is filled at runtime by workflow echo; manifest stays generic and pinned to SHA.
    manifest = {
        "schema_version": "tw_pb_manifest_v1",
        "generated_at_utc": gen_utc,
        "generated_at_local": gen_local,
        "timezone": args.tz,
        "data_commit_sha": data_sha,
        "paths": {
            "latest": f"tw_pb_cache/latest.json",
            "history": f"tw_pb_cache/history.json",
            "stats_latest": f"tw_pb_cache/stats_latest.json",
            "report": f"tw_pb_cache/report.md",
        },
        "pinned_urls": {
            "latest": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/tw_pb_cache/latest.json",
            "history": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/tw_pb_cache/history.json",
            "stats_latest": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/tw_pb_cache/stats_latest.json",
            "report": f"https://raw.githubusercontent.com/{{REPO}}/{data_sha}/tw_pb_cache/report.md",
        },
        "notes": [
            "Replace {REPO} with owner/repo when consuming pinned_urls.",
            "This manifest is pinned to data_commit_sha for auditability.",
        ],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()