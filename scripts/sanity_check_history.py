# scripts/sanity_check_history.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sanity check for history/stats governance.

Hard rules:
- stats_latest.json MUST contain:
  - as_of_ts
  - stats_policy.script_version
- If manifest.json exists and contains stats_policy.script_version:
  - stats_latest.stats_policy.script_version must match manifest.stats_policy.script_version

This prevents "pretty but wrong" reports when stats definitions change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


CACHE_DIR = Path("cache")
MANIFEST = CACHE_DIR / "manifest.json"
STATS = CACHE_DIR / "stats_latest.json"


def _load_json(path: Path) -> Tuple[Any, str]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "ok"
    except Exception as e:
        return None, f"bad_json:{type(e).__name__}"


def _get(d: Dict[str, Any], keys: str, default=None):
    cur: Any = d
    for k in keys.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def main() -> int:
    errors = []
    warns = []

    stats_obj, st_stats = _load_json(STATS)
    if st_stats != "ok" or not isinstance(stats_obj, dict):
        errors.append(f"stats_latest.json not readable ({st_stats})")
        print("\n".join(errors), file=sys.stderr)
        return 2

    # required: as_of_ts
    stats_as_of = _get(stats_obj, "as_of_ts", None)
    if not isinstance(stats_as_of, str) or not stats_as_of:
        errors.append("stats_latest.json missing required field: as_of_ts")

    # required: stats_policy.script_version
    stats_ver = _get(stats_obj, "stats_policy.script_version", None)
    if not isinstance(stats_ver, str) or not stats_ver:
        errors.append("stats_latest.json missing required field: stats_policy.script_version")

    # optional: compare with manifest
    manifest_obj, st_manifest = _load_json(MANIFEST)
    if st_manifest == "ok" and isinstance(manifest_obj, dict):
        man_ver = _get(manifest_obj, "stats_policy.script_version", None)
        if isinstance(man_ver, str) and man_ver:
            if isinstance(stats_ver, str) and stats_ver and stats_ver != man_ver:
                errors.append(
                    f"stats_policy.script_version mismatch: stats_latest={stats_ver} vs manifest={man_ver}"
                )
        else:
            warns.append("manifest.json has no stats_policy.script_version (recommended to add)")

    # print result
    if warns:
        print("[WARN]")
        for w in warns:
            print(" -", w)

    if errors:
        print("[ERROR]", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        return 2

    print("OK: sanity_check_history passed (stats_policy.script_version present and consistent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())