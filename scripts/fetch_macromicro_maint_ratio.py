#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_macromicro_maint_ratio.py

Sidecar cache: Taiwan "TAIEX Maintenance Margin Ratio" (台灣-大盤融資維持率)
Fetch from MacroMicro *page-displayed* latest value (HTML parse).

Design goals (audit-first, workflow-safe):
- Always write: <outdir>/latest.json  (even when fetch/parse fails)
- Update:        <outdir>/history.json only when confidence == OK
- Never crash parent workflow due to data-source instability:
  - network/parse errors => latest.json with maint_ratio_pct=null + confidence=DOWNGRADED
  - exits 0 unless latest.json cannot be written

Notes:
- This script does NOT download CSV from MacroMicro. It parses the HTML page for the displayed
  latest date/value. MacroMicro may update page structure over time; treat as a best-effort
  sidecar with conservative downgrade rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo


# --------------------------
# Config
# --------------------------

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TZ = "Asia/Taipei"
DEFAULT_OUTDIR = "tw_margin_maint_ratio_cache"

# MacroMicro series page for Taiwan TAIEX Maintenance Margin Ratio
SOURCE_URL = "https://www.macromicro.me/series/23204/taiwan-taiex-maintenance-margin"

LATEST_FN = "latest.json"
HISTORY_FN = "history.json"

SCHEMA_LATEST = "tw_margin_maint_ratio_latest_v1"
SCHEMA_HISTORY = "tw_margin_maint_ratio_history_v1"

SCRIPT_FINGERPRINT = "fetch_macromicro_maint_ratio_py@v1"

# Retry backoff (seconds). Keep short to avoid bloating workflow time.
RETRY_BACKOFF_S = [2, 4, 8]

# Conservative guardrails for sanity checks
PLAUSIBLE_MIN = 80.0
PLAUSIBLE_MAX = 300.0

# Downgrade if data_date is too stale vs today (local)
STALE_MAX_DAYS = 3


# --------------------------
# Helpers
# --------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_now_iso(tz: ZoneInfo) -> str:
    return datetime.now(tz).isoformat()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def safe_mkdir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def write_json(path: str, obj: Any) -> None:
    safe_mkdir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def strip_tags(html: str) -> str:
    # Lightweight: remove tags and compress whitespace
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def parse_latest_date_value_from_html(html: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Extract (data_date, maint_ratio_pct) from HTML text.

    Strategy:
    - Find all occurrences of: YYYY-MM-DD <number> %
    - Choose the maximum date (lexicographically safe for YYYY-MM-DD)
    - Take the first parsed value for that date

    Returns:
      (data_date, value_pct, parse_note)
    """
    text = strip_tags(html)

    # Match e.g. "2026-01-27 173.04%"
    pat = re.compile(r"(\d{4}-\d{2}-\d{2})\s+([0-9]+(?:\.[0-9]+)?)\s*%")
    matches = pat.findall(text)
    if not matches:
        return None, None, "no (YYYY-MM-DD + pct) pattern found"

    by_date: Dict[str, float] = {}
    for d, v in matches:
        if d in by_date:
            continue
        try:
            by_date[d] = float(v)
        except Exception:
            continue

    if not by_date:
        return None, None, "matches found but values not parseable"

    best_date = max(by_date.keys())
    best_val = by_date[best_date]
    return best_date, best_val, f"picked max date from {len(by_date)} unique date matches"


def classify_confidence(
    data_date: Optional[str],
    value: Optional[float],
    local_today: str,
) -> Tuple[str, str]:
    """
    Conservative DQ:
    - OK only if:
      - data_date/value exist
      - value within plausible range
      - data_date <= today
      - not stale by more than STALE_MAX_DAYS
    - else DOWNGRADED
    """
    if data_date is None or value is None:
        return "DOWNGRADED", "missing data_date or value"

    if not (PLAUSIBLE_MIN <= value <= PLAUSIBLE_MAX):
        return "DOWNGRADED", f"value out of plausible range: {value}"

    # Basic validity: YYYY-MM-DD
    try:
        d_dt = datetime.strptime(data_date, "%Y-%m-%d").date()
        t_dt = datetime.strptime(local_today, "%Y-%m-%d").date()
    except Exception:
        return "DOWNGRADED", "date parse failed"

    if d_dt > t_dt:
        return "DOWNGRADED", f"data_date is in the future vs today: {data_date} > {local_today}"

    age_days = (t_dt - d_dt).days
    if age_days > STALE_MAX_DAYS:
        return "DOWNGRADED", f"stale: age_days={age_days} > {STALE_MAX_DAYS}"

    return "OK", "parsed and within guardrails"


def fetch_with_retry(url: str, timeout_s: int = 20) -> Tuple[Optional[requests.Response], Optional[str]]:
    """
    Returns: (response or None, error_str or None)
    Retries on request exceptions and non-200 status codes, with exponential backoff.
    """
    last_err = None
    for i, backoff in enumerate([0] + RETRY_BACKOFF_S):
        if backoff > 0:
            time.sleep(backoff)

        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout_s)
            if r.status_code == 200:
                return r, None
            last_err = f"http_{r.status_code}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"

        if i == len(RETRY_BACKOFF_S):
            break

    return None, last_err


def upsert_history(
    history_obj: Dict[str, Any],
    data_date: str,
    value: float,
    source_url: str,
    fetched_at_utc: str,
) -> Dict[str, Any]:
    items = history_obj.get("items", [])
    if not isinstance(items, list):
        items = []

    by_date: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if isinstance(it, dict) and it.get("data_date"):
            by_date[str(it["data_date"])] = it

    by_date[data_date] = {
        "data_date": data_date,
        "maint_ratio_pct": float(value),
        "source_url": source_url,
        "fetched_at_utc": fetched_at_utc,
    }

    out_items = sorted(by_date.values(), key=lambda x: x["data_date"], reverse=True)
    return {"schema_version": SCHEMA_HISTORY, "items": out_items}


def maybe_save_raw(outdir: str, data_date: Optional[str], raw: bytes, raw_sha256: str) -> Optional[str]:
    """
    Save raw HTML snapshot for audit, if possible.
    Returns saved path (relative) or None.
    """
    try:
        raw_dir = os.path.join(outdir, "raw_html")
        safe_mkdir(raw_dir)
        date_tag = (data_date or "NA").replace("-", "")
        fn = f"macromicro_maint_ratio_{date_tag}_{raw_sha256[:12]}.html"
        path = os.path.join(raw_dir, fn)
        with open(path, "wb") as f:
            f.write(raw)
        return path
    except Exception:
        return None


# --------------------------
# Main
# --------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR)
    ap.add_argument("--save-raw", action="store_true", help="Save raw HTML snapshot under <outdir>/raw_html/")
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    outdir = args.outdir

    safe_mkdir(outdir)
    latest_path = os.path.join(outdir, LATEST_FN)
    history_path = os.path.join(outdir, HISTORY_FN)

    generated_at_utc = utc_now_iso()
    generated_at_local = local_now_iso(tz)
    local_today = datetime.now(tz).date().isoformat()

    data_date: Optional[str] = None
    maint_ratio_pct: Optional[float] = None
    http_status: Optional[int] = None
    raw_sha256: Optional[str] = None
    raw_saved_path: Optional[str] = None

    fetch_status = "DOWNGRADED"
    confidence = "DOWNGRADED"
    dq_reason = "not started"
    parse_note = ""
    error: Optional[str] = None

    # Fetch
    resp, fetch_err = fetch_with_retry(SOURCE_URL, timeout_s=20)
    if resp is None:
        error = fetch_err or "fetch_failed"
        dq_reason = "fetch failed"
    else:
        http_status = resp.status_code
        raw = resp.content or b""
        raw_sha256 = sha256_bytes(raw)

        if args.save_raw:
            # Save once (may update later if we parse a date)
            raw_saved_path = maybe_save_raw(outdir, None, raw, raw_sha256)

        # Parse
        try:
            html = resp.text
            data_date, maint_ratio_pct, parse_note = parse_latest_date_value_from_html(html)

            # If we saved raw without date, optionally re-save using parsed date for nicer naming
            if args.save_raw and raw and raw_sha256:
                raw_saved_path = maybe_save_raw(outdir, data_date, raw, raw_sha256) or raw_saved_path

            confidence, dq_reason = classify_confidence(data_date, maint_ratio_pct, local_today)
            fetch_status = "OK" if confidence == "OK" else "DOWNGRADED"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            dq_reason = "parse error"
            fetch_status = "DOWNGRADED"
            confidence = "DOWNGRADED"

    latest_obj: Dict[str, Any] = {
        "schema_version": SCHEMA_LATEST,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "generated_at_utc": generated_at_utc,
        "generated_at_local": generated_at_local,
        "timezone": args.tz,
        "source_url": SOURCE_URL,
        "http_status": http_status,
        "raw_sha256": raw_sha256,
        "raw_saved_path": raw_saved_path,
        "fetch_status": fetch_status,   # OK / DOWNGRADED
        "confidence": confidence,       # OK / DOWNGRADED
        "dq_reason": dq_reason,
        "parse_note": parse_note,
        "data_date": data_date,
        "maint_ratio_pct": maint_ratio_pct,
        "error": error,
    }

    # Always write latest.json (unless filesystem failure)
    write_json(latest_path, latest_obj)

    # Update history only when OK + data present
    try:
        if confidence == "OK" and data_date and (maint_ratio_pct is not None):
            hist = load_json(history_path)
            if not isinstance(hist, dict):
                hist = {"schema_version": SCHEMA_HISTORY, "items": []}
            hist2 = upsert_history(hist, data_date, float(maint_ratio_pct), SOURCE_URL, generated_at_utc)
            write_json(history_path, hist2)
    except Exception:
        # Do not fail workflow for history issues
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())