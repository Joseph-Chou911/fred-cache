import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo


def utc_now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(timespec="seconds")


def now_iso(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def raw_url(repo: str, sha: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"


def build_manifest(repo: str, data_sha: str, out_dir: str, tz: str) -> dict:
    return {
        "generated_at_utc": utc_now_iso(),
        "as_of_ts": now_iso(tz),
        "data_commit_sha": data_sha,
        "pinned": {
            "latest_json": raw_url(repo, data_sha, f"{out_dir}/latest.json"),
            "history_json": raw_url(repo, data_sha, f"{out_dir}/history.json"),
            "latest_csv": raw_url(repo, data_sha, f"{out_dir}/latest.csv"),
        },
        "notes": [
            "This manifest intentionally pins DATA files to data_commit_sha.",
            "The manifest itself is pinned by the URL (MANIFEST_SHA) used to fetch this manifest.json.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data-sha", required=True)
    ap.add_argument("--tz", default="Asia/Taipei")
    args = ap.parse_args()

    for out_dir in ["inflation_realrate_cache", "asset_proxy_cache"]:
        os.makedirs(out_dir, exist_ok=True)
        manifest = build_manifest(args.repo, args.data_sha, out_dir, args.tz)
        write_json(os.path.join(out_dir, "manifest.json"), manifest)


if __name__ == "__main__":
    main()