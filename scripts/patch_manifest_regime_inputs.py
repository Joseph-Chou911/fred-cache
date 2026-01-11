#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_manifest_regime_inputs.py

Scheme A (most stable):
- Canonical outputs:
  - regime_inputs_cache/inputs_latest.json
  - regime_inputs_cache/inputs_history_lite.json
  - regime_inputs_cache/features_latest.json
  - regime_inputs_cache/dq_state.json
  - regime_inputs_cache/inputs_schema_out.json
- Compatibility outputs (copies):
  - regime_inputs_cache/latest.json
  - regime_inputs_cache/history_lite.json

This script writes:
- regime_inputs_cache/manifest.json
  with BOTH:
    pinned.inputs_* keys (canonical)
    pinned.latest_json / pinned.history_lite_json (compat)
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "regime_inputs_cache" / "manifest.json"

CANONICAL = {
    "inputs_latest_json": "regime_inputs_cache/inputs_latest.json",
    "inputs_history_lite_json": "regime_inputs_cache/inputs_history_lite.json",
    "features_latest_json": "regime_inputs_cache/features_latest.json",
    "dq_state_json": "regime_inputs_cache/dq_state.json",
    "inputs_schema_out_json": "regime_inputs_cache/inputs_schema_out.json",
}

COMPAT = {
    "latest_json": "regime_inputs_cache/latest.json",
    "history_lite_json": "regime_inputs_cache/history_lite.json",
}


def utc_now():
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_taipei(dt: datetime) -> str:
    if ZoneInfo is None:
        return iso_z(dt)
    return dt.astimezone(ZoneInfo("Asia/Taipei")).isoformat()


def git_rev_parse_head() -> str:
    out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not out or len(out) < 7:
        raise RuntimeError("failed to get git HEAD sha")
    return out


def read_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def build_raw_url(repo: str, sha: str, relpath: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{relpath}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="e.g. Joseph-Chou911/fred-cache")
    ap.add_argument("--script-version", default="regime_inputs_manifest_v2_schemeA")
    args = ap.parse_args()

    now = utc_now()
    sha = git_rev_parse_head()

    obj = read_json(MANIFEST_PATH) if MANIFEST_PATH.exists() else {}
    obj["generated_at_utc"] = iso_z(now)
    obj["as_of_ts"] = iso_taipei(now)  # keep consistent with other files
    obj["script_version"] = args.script_version
    obj["data_commit_sha"] = sha

    pinned = obj.get("pinned", {}) or {}
    # canonical pins
    for k, rel in CANONICAL.items():
        pinned[k] = build_raw_url(args.repo, sha, rel)
    # compat pins
    for k, rel in COMPAT.items():
        pinned[k] = build_raw_url(args.repo, sha, rel)

    obj["pinned"] = pinned

    write_json_atomic(MANIFEST_PATH, obj)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())