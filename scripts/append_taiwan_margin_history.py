#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append / seed taiwan_margin_cache/history.json from latest.json (audit-first, safe-write)

Key goals:
- Date canonicalization: accept YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD => canonical YYYY-MM-DD.
- STRICT NO GUESSING: if a date can't be safely parsed => invalid => skip for append/seed/dedup key.
- Protect existing history.json: if latest is missing/invalid => do NOT overwrite history.
- Dedup key uses canonical date: (market, canonical_data_date).
- Keep max_items overall across markets.

Design notes:
- Legacy items lacking data_date_canon are "upgraded" if (and only if) data_date is safely canonicalizable.
- Non-canonical items are preserved (up to a cap) for audit/cleanup, but won't crowd out canonical latest items.
- audit.warnings is bounded to avoid unbounded growth.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, date as _date
from typing import Any, Dict, List, Optional, Tuple


# ----------------- constants -----------------

MAX_WARNINGS = 120  # keep last N warnings to avoid file bloat
NONCANON_KEEP_CAP_MIN = 20
NONCANON_KEEP_CAP_MAX = 120  # absolute cap on non-canonical items kept after trimming


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
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def cap_warnings(audit: Dict[str, Any]) -> None:
    """
    Bound warnings list size to avoid unbounded growth.
    Keep most recent MAX_WARNINGS entries.
    """
    w = audit.get("warnings")
    if not isinstance(w, list):
        audit["warnings"] = []
        return
    if len(w) > MAX_WARNINGS:
        audit["warnings"] = w[-MAX_WARNINGS:]


# ----------------- date canonicalization (STRICT, NO GUESSING) -----------------

_DATE_RE = re.compile(r"^\s*(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})\s*$")


def canon_ymd(s: Any) -> Optional[str]:
    """
    Canonicalize YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD -> YYYY-MM-DD
    STRICT: validate using datetime.date to catch leap years & invalid month-ends.
    If cannot safely parse -> None (NO GUESSING, NO MM/DD inference).
    """
    if s is None:
        return None
    ss = str(s).strip()
    m = _DATE_RE.match(ss)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        _date(y, mo, d)  # strict validation (leap year, month-end)
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except Exception:
        return None


# ----------------- history load -----------------

def load_or_empty_history(path: str) -> Dict[str, Any]:
    run_ts = now_utc_iso()
    base = {
        "schema_version": "taiwan_margin_financing_history_v1",
        "generated_at_utc": run_ts,
        "items": [],
        "audit": {
            "generated_at_utc": run_ts,
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
            obj["audit"] = {"generated_at_utc": run_ts, "warnings": [], "stats": {}}
        if "warnings" not in obj["audit"] or not isinstance(obj["audit"].get("warnings"), list):
            obj["audit"]["warnings"] = []
        if "stats" not in obj["audit"] or not isinstance(obj["audit"].get("stats"), dict):
            obj["audit"]["stats"] = {}

        return obj
    except Exception as e:
        base["audit"]["warnings"].append(f"history load failed: {type(e).__name__}: {e}")
        cap_warnings(base["audit"])
        return base


# ----------------- item helpers -----------------

def make_item(run_ts_utc: str, market: str, series_obj: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    raw_date = row.get("date")
    can_date = canon_ymd(raw_date)
    return {
        "run_ts_utc": run_ts_utc,
        "market": market,
        "source": series_obj.get("source"),
        "source_url": series_obj.get("source_url"),
        "data_date": can_date if can_date else (str(raw_date) if raw_date is not None else None),
        "data_date_canon": can_date if can_date else None,
        "balance_yi": row.get("balance_yi"),
        "chg_yi": row.get("chg_yi"),
    }


def is_valid_item_for_dedup(it: Dict[str, Any]) -> bool:
    """
    Dedup-eligible only if market present and canonical date exists.
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


def has_valid_market(items: List[Dict[str, Any]], market: str) -> bool:
    """
    Seed decision helper:
    Consider a market as 'having data' if any item:
      - matches market
      - has data_date_canon OR data_date is safely canonicalizable (NO GUESSING)
    This avoids seeding when only legacy-but-upgradable items exist.
    """
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("market") != market:
            continue
        if it.get("data_date_canon"):
            return True
        if canon_ymd(it.get("data_date")):
            return True
    return False


def find_row_by_date(rows: List[Dict[str, Any]], dd_canon: str, audit: Dict[str, Any], market: str) -> Optional[Dict[str, Any]]:
    """
    Find row(s) where canon(row.date) == dd_canon.
    Warn if multiple matches; use the first deterministically.
    """
    matches: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if canon_ymd(r.get("date")) == dd_canon:
            matches.append(r)

    if not matches:
        return None

    if len(matches) > 1:
        audit["warnings"].append(f"latest: {market} has multiple rows for data_date={dd_canon}; using first")

    return matches[0]


# ----------------- legacy upgrade (root-cause fix) -----------------

def upgrade_legacy_items(items: List[Dict[str, Any]], audit: Dict[str, Any]) -> int:
    """
    Upgrade legacy items:
    - If data_date_canon is missing BUT data_date is safely canonicalizable,
      then set data_date_canon and normalize data_date to canonical.
    NO GUESSING.
    """
    upgraded = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("data_date_canon"):
            continue
        can = canon_ymd(it.get("data_date"))
        if can:
            it["data_date_canon"] = can
            it["data_date"] = can
            upgraded += 1

    if upgraded:
        audit["warnings"].append(f"normalize: upgraded {upgraded} legacy items by canonicalizing data_date")
    return upgraded


def normalize_dedup_keep_latest(items: List[Dict[str, Any]], audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enforce uniqueness for dedup-eligible items by (market, data_date_canon).
    Keep item with max run_ts_utc (ISO8601 sortable).
    Keep non-dedup-eligible items as passthrough, but record a warning count.
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

        prev = best.get(k)
        if prev is None:
            best[k] = it
        else:
            if str(it.get("run_ts_utc") or "") >= str(prev.get("run_ts_utc") or ""):
                best[k] = it

    if noncanon_cnt:
        audit["warnings"].append(f"normalize: kept {noncanon_cnt} non-canonical-date items without dedup")

    return list(best.values()) + passthrough


# ----------------- trimming policy (avoid accidental legacy wipe) -----------------

def _noncanon_sort_key(it: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Deterministic ordering for non-canonical items:
    sort by run_ts_utc, then market, then data_date (string).
    """
    run_ts = str(it.get("run_ts_utc") or "")
    mkt = str(it.get("market") or "")
    dd = str(it.get("data_date") or "")
    return (run_ts, mkt, dd)


def _canon_sort_key(it: Dict[str, Any]) -> Tuple[str, str]:
    """
    Canonical items can be ordered by (data_date_canon, run_ts_utc).
    """
    dd = str(it.get("data_date_canon") or "")
    run_ts = str(it.get("run_ts_utc") or "")
    return (dd, run_ts)


def trim_items(items: List[Dict[str, Any]], max_items: int, audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Keep max_items overall, with controlled retention of non-canonical items:
    - Keep up to noncanon_cap non-canonical items (latest by run_ts_utc), so legacy isn't silently wiped,
      but also won't crowd out canonical latest data.
    - Remaining capacity goes to canonical items (latest by date/run_ts).
    """
    canon: List[Dict[str, Any]] = []
    noncanon: List[Dict[str, Any]] = []

    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("data_date_canon"):
            canon.append(it)
        else:
            noncanon.append(it)

    # Determine cap for non-canonical retention
    noncanon_cap = max(NONCANON_KEEP_CAP_MIN, min(NONCANON_KEEP_CAP_MAX, max_items // 4))
    noncanon.sort(key=_noncanon_sort_key)
    if len(noncanon) > noncanon_cap:
        dropped = len(noncanon) - noncanon_cap
        audit["warnings"].append(f"trim: dropped {dropped} non-canonical items (cap={noncanon_cap})")
        noncanon = noncanon[-noncanon_cap:]

    # Remaining capacity for canonical items
    remain = max_items - len(noncanon)
    if remain < 0:
        # This should be rare due to cap, but handle defensively
        audit["warnings"].append("trim: non-canonical items exceed max_items after cap; truncating further by run_ts_utc")
        noncanon.sort(key=_noncanon_sort_key)
        noncanon = noncanon[-max_items:]
        return noncanon

    canon.sort(key=_canon_sort_key)
    if len(canon) > remain:
        dropped = len(canon) - remain
        audit["warnings"].append(f"trim: dropped {dropped} canonical items to fit max_items={max_items}")
        canon = canon[-remain:]

    # Final deterministic order: canonical first (time-ordered), then non-canonical (time-ordered)
    out = canon + noncanon
    return out


# ----------------- latest validation -----------------

def extract_appendable_row(
    latest: Dict[str, Any],
    market: str,
    audit: Dict[str, Any],
) -> Optional[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """
    Return (dd_canon, series_obj, row) if we can safely append for this market.
    Conditions:
    - series exists and is dict
    - data_date exists and is canon-able
    - rows contains a row whose canon(date)==dd_canon (warn if multiple)
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

    row = find_row_by_date([r for r in rows if isinstance(r, dict)], dd_canon, audit, market)
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
        cap_warnings(audit)
        eprint(f"[append_history] latest load failed -> keep history unchanged: {type(e).__name__}: {e}")
        return

    # Determine if we have at least one market that is appendable.
    appendable: Dict[str, Tuple[str, Dict[str, Any], Dict[str, Any]]] = {}
    for mkt in ("TWSE", "TPEX"):
        got = extract_appendable_row(latest, mkt, audit)
        if got:
            appendable[mkt] = got

    if not appendable:
        audit["warnings"].append("latest has no appendable markets; history NOT updated to avoid wipe")
        cap_warnings(audit)
        eprint("[append_history] no appendable markets in latest -> history NOT updated (protect existing)")
        return

    # Seed rule: only if history has NO VALID (or safely-upgradable) items for a market.
    seed_added = 0
    seed_skipped_bad_date = 0
    for market in ("TWSE", "TPEX"):
        if has_valid_market(items, market):
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

    # Upgrade legacy items so they can participate in dedup (NO GUESSING).
    upgraded_legacy = upgrade_legacy_items(items, audit)

    # Normalize duplicates
    before_n = len(items)
    items = normalize_dedup_keep_latest(items, audit)
    after_n = len(items)

    # Trim with controlled retention of non-canonical items
    items_before_trim = len(items)
    items = trim_items(items, args.max_items, audit)
    items_after_trim = len(items)
    if items_after_trim != items_before_trim:
        audit["warnings"].append(f"trim: items {items_before_trim} -> {items_after_trim} (max_items={args.max_items})")

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
        "legacy_upgraded": upgraded_legacy,
    }

    cap_warnings(audit)

    out = {
        "schema_version": "taiwan_margin_financing_history_v1",
        "generated_at_utc": run_ts,
        "items": items,
        "audit": audit,
    }

    write_json_atomic(args.history, out)
    eprint(
        "[append_history] OK: "
        f"seed_added={seed_added}, append_added={append_added}, legacy_upgraded={upgraded_legacy}, final_items={len(items)}"
    )


if __name__ == "__main__":
    main()