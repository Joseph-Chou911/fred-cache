# scripts/patch_stats.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--path", default="cache/stats_latest.json")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        raise SystemExit(f"missing file: {p}")

    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit("stats_latest.json is not a json object")

    # only patch metadata
    obj["data_commit_sha"] = args.data_sha

    # write compact json + newline
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"patched {p} data_commit_sha={args.data_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())