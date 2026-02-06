#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append / seed taiwan_margin_cache/history.json from latest.json (audit-first, safe-write)

Key goals:
- Date canonicalization: accept YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD => canonical YYYY-MM-DD.
- NO GUESSING: if a date can't be safely parsed => treat as invalid and SKIP append/seed for that row.
- Protect existing history.json: if latest is missing/invalid (e.g., fetch failed) => do NOT overwrite history.
- Dedup key uses canonical date: (market, canonical_data_date).
- Keep max_items overall across markets (by (canonical_data_date, run_ts_utc)).

Behavior changes vs previous:
1) We validate latest.json structure and require at least one market has an appendable row (date == data_date).
   If not, we do not write history at all (to avoid wiping on fetch failures).
2) We keep non-canonical items already in history, but:
   - they are not used for dedup keys (since we can't safely compare dates),
   - they are kept and recorded in audit.warnings so you can clean them later.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ----------------- basics -----------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: str, obj: Any) -> None:
    """
    Atomic-ish write: write to temp then replace.
    Avoid partial writes that could corrupt history.json.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


# ----------------- date canonicalization (NO GUESSING) -----------------

_DATE_RE = re.compile(r"^\s*(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})\s*$")


def canon_ymd(s: Any) -> Optional[str]:
    """
    Canonicalize YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD -> YYYY-MM-DD
    If cannot safely parse -> None (NO GUESSING, NO MM/DD inference here).
    """
    if s is None:
        return None
    ss = str(s).strip()
    m = _DATE_RE.match(ss)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


# ----------------- history load -----------------

def load_or_empty_history(path: str) -> Dict[str, Any]:
    base = {
        "schema_version": "taiwan_margin_financing_history_v1",
        "generated_at_utc": now_utc_iso(),
        "items": [],
        "audit": {
            "generated_at_utc": now_utc_iso(),
            "warnings": [],
            "stats": {},
        },
    }
    if not os.path.exists(path):
        return base

    try:
        obj = read_json(path)
        if not isinstance(obj, dict):
            return base
        items = obj.get("items")
        if not isinstance(items, list):
            return base

        # Ensure audit exists (do not destroy existing audit)
        if "audit" not in obj or not isinstance(obj.get("audit"), dict):
            obj["audit"] = {"generated_at_utc": now_utc_iso(), "warnings": [], "stats": {}}
        if "warnings" not in obj["audit"] or not isinstance(obj["audit"].get("warnings"), list):
            obj["audit"]["warnings"] = []
        if "stats" not in obj["audit"] or not isinstance(obj["audit"].get("stats"), dict):
            obj["audit"]["stats"] = {}

        return obj
    except Exception as e:
        base["audit"]["warnings"].append(f"history load failed: {type(e).__name__}: {e}")
        return base


# ----------------- item helpers -----------------

def make_item(run_ts_utc: str, market: str, series_obj: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    # canonicalize date if possible; keep both raw & canonical for auditability
    raw_date = row.get("date")
    can_date = canon_ymd(raw_date)
    return {
        "run_ts_utc": run_ts_utc,
        "market": market,
        "source": series_obj.get("source"),
        "source_url": series_obj.get("source_url"),
        # data_date is stored as canonical if possible; else raw (but we mark it)
        "data_date": can_date if can_date else (str(raw_date) if raw_date is not None else None),
        "data_date_canon": can_date if can_date else None,
        "balance_yi": row.get("balance_yi"),
        "chg_yi": row.get("chg_yi"),
    }


def is_valid_item_for_dedup(it: Dict[str, Any]) -> bool:
    """
    An item is "dedup-eligible" only if market is present and canonical date exists.
    We do NOT guess canonical date.
    """
    mkt = str(it.get("market") or "").strip()
    dd = it.get("data_date_canon")
    return bool(mkt) and isinstance(dd, str) and bool(dd)


def dedup_key(it: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    if not isinstance(it, dict):
        return None
    if not is_valid_item_for_dedup(it):
        return None
    return (str(it.get("market")).strip(), str(it.get("data_date_canon")))


def upsert(items: List[Dict[str, Any]], new_item: Dict[str, Any], audit: Dict[str, Any]) -> None:
    """
    Upsert by canonical (market, date). If canonical missing, append as-is but warn.
    """
    k = dedup_key(new_item)
    if k is None:
        audit["warnings"].append(
            f"upsert: new_item missing canonical date; kept without dedup. market={new_item.get('market')}, data_date={new_item.get('data_date')}"
        )
        items.append(new_item)
        return

    for i, it in enumerate(items):
        if dedup_key(it) == k:
            items[i] = new_item
            return
    items.append(new_item)


def has_market(items: List[Dict[str, Any]], market: str) -> bool:
    for it in items:
        if isinstance(it, dict) and it.get("market") == market:
            return True
    return False


def find_row_by_date(rows: List[Dict[str, Any]], dd_canon: str) -> Optional[Dict[str, Any]]:
    """
    Find the row where canon(row.date) == dd_canon.
    NO GUESSING: if row.date isn't canon-able, it won't match.
    """
    for r in rows:
        if not isinstance(r, dict):
            continue
        if canon_ymd(r.get("date")) == dd_canon:
            return r
    return None


def normalize_dedup_keep_latest(items: List[Dict[str, Any]], audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enforce uniqueness for dedup-eligible items by (market, data_date_canon).
    Keep item with max run_ts_utc.
    Keep non-dedup-eligible items untouched, but record a warning count.
    """
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    passthrough: List[Dict[str, Any]] = []
    noncanon_cnt = 0

    for it in items:
        if not isinstance(it, dict):
            continue
        k = dedup_key(it)
        if k is None:
            noncanon_cnt += 1
            passthrough.append(it)
            continue

        if k not in best:
            best[k] = it
        else:
            prev = best[k]
            if str(it.get("run_ts_utc") or "") >= str(prev.get("run_ts_utc") or ""):
                best[k] = it

    if noncanon_cnt:
        audit["warnings"].append(f"normalize: kept {noncanon_cnt} non-canonical-date items without dedup")

    # Return combined: canonical deduped + passthrough (kept)
    return list(best.values()) + passthrough


def sort_key(it: Dict[str, Any]) -> Tuple[str, str]:
    """
    Sort by canonical date then run_ts_utc. Non-canonical dates sort first (empty key).
    We keep deterministic output while avoiding wrong ordering assumptions.
    """
    dd = str(it.get("data_date_canon") or "")
    run_ts = str(it.get("run_ts_utc") or "")
    return (dd, run_ts)


# ----------------- latest validation -----------------

def extract_appendable_row(latest: Dict[str, Any], market: str, audit: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """
    Return (dd_canon, series_obj, row) if we can safely append for this market.
    Conditions:
    - series exists and is dict
    - data_date exists and is canon-able
    - rows is list and contains a row whose canon(date)==dd_canon
    - row has balance_yi not None
    """
    series_all = latest.get("series") or {}
    if not isinstance(series_all, dict):
        audit["warnings"].append("latest: series missing or not a dict")
        return None

    s = series_all.get(market) or {}
    if not isinstance(s, dict):
        audit["warnings"].append(f"latest: series[{market}] missing or not a dict")
        return None

    dd_raw = s.get("data_date")
    dd_canon = canon_ymd(dd_raw)
    if not dd_canon:
        audit["warnings"].append(f"latest: {market} data_date not canonicalizable: {dd_raw}")
        return None

    rows = s.get("rows") or []
    if not isinstance(rows, list) or not rows:
        audit["warnings"].append(f"latest: {market} rows missing/empty")
        return None

    row = find_row_by_date([r for r in rows if isinstance(r, dict)], dd_canon)
    if row is None:
        audit["warnings"].append(f"latest: {market} cannot find row matching data_date={dd_canon} (no guessing)")
        return None

    if row.get("balance_yi") is None:
        audit["warnings"].append(f"latest: {market} matched row has balance_yi=None; skip append")
        return None

    return (dd_canon, s, row)


# ----------------- main -----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--max_items", type=int, default=800)
    args = ap.parse_args()

    run_ts = now_utc_iso()

    # Load history first (so we can keep it intact if latest is bad)
    hist = load_or_empty_history(args.history)
    items: List[Dict[str, Any]] = hist.get("items", [])
    if not isinstance(items, list):
        items = []

    audit = hist.get("audit")
    if not isinstance(audit, dict):
        audit = {"generated_at_utc": run_ts, "warnings": [], "stats": {}}
    if "warnings" not in audit or not isinstance(audit.get("warnings"), list):
        audit["warnings"] = []
    if "stats" not in audit or not isinstance(audit.get("stats"), dict):
        audit["stats"] = {}

    # Read latest; if missing/invalid => do NOT write history (protect existing)
    try:
        latest = read_json(args.latest)
        if not isinstance(latest, dict):
            raise ValueError("latest is not a dict")
    except Exception as e:
        audit["warnings"].append(f"latest load failed: {type(e).__name__}: {e}")
        eprint(f"[append_history] latest load failed -> keep history unchanged: {type(e).__name__}: {e}")
        # Do not write history to avoid overwriting with empty.
        return

    # Determine if we have at least one market that is appendable.
    appendable: Dict[str, Tuple[str, Dict[str, Any], Dict[str, Any]]] = {}
    for mkt in ("TWSE", "TPEX"):
        got = extract_appendable_row(latest, mkt, audit)
        if got:
            appendable[mkt] = got

    if not appendable:
        # This is the critical "do not destroy history" protection.
        # If fetch failed, latest often has empty rows/data_date None -> we skip writing.
        audit["warnings"].append("latest has no appendable markets; history NOT updated to avoid wipe")
        eprint("[append_history] no appendable markets in latest -> history NOT updated (protect existing)")
        return

    # Seed rule: only if history has NO items for a market.
    # Seed uses latest.rows, but only rows with canon(date) + balance_yi.
    seed_added = 0
    seed_skipped_bad_date = 0
    for market in ("TWSE", "TPEX"):
        if has_market(items, market):
            continue
        series_all = latest.get("series") or {}
        s = series_all.get(market) if isinstance(series_all, dict) else None
        rows = (s or {}).get("rows") if isinstance(s, dict) else None
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("balance_yi") is None:
                continue
            can = canon_ymd(row.get("date"))
            if not can:
                seed_skipped_bad_date += 1
                continue
            upsert(items, make_item(run_ts, market, s, row), audit)
            seed_added += 1

    # Append rule: append only the latest data_date row per appendable market
    append_added = 0
    for market, (_dd_canon, s, row) in appendable.items():
        upsert(items, make_item(run_ts, market, s, row), audit)
        append_added += 1

    # Normalize duplicates defensively
    before_n = len(items)
    items = normalize_dedup_keep_latest(items, audit)
    after_n = len(items)

    # Keep only last max_items by (canonical_date, run_ts). Non-canon sort first; we keep tail.
    items.sort(key=sort_key)
    if len(items) > args.max_items:
        items = items[-args.max_items :]

    # Update audit stats
    audit["generated_at_utc"] = run_ts
    audit["stats"] = {
        "run_ts_utc": run_ts,
        "history_items_before": before_n,
        "history_items_after_dedup": after_n,
        "history_items_final": len(items),
        "seed_added": seed_added,
        "seed_skipped_bad_date": seed_skipped_bad_date,
        "append_added": append_added,
        "appendable_markets": sorted(list(appendable.keys())),
        "max_items": args.max_items,
    }

    out = {
        "schema_version": "taiwan_margin_financing_history_v1",
        "generated_at_utc": run_ts,
        "items": items,
        "audit": audit,
    }

    write_json_atomic(args.history, out)
    eprint(f"[append_history] OK: seed_added={seed_added}, append_added={append_added}, final_items={len(items)}")


if __name__ == "__main__":
    main()