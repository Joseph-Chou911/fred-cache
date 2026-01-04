#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fallback cache updater (no-key / mostly official first)

Outputs:
  - fallback_cache/latest.json
  - fallback_cache/latest.csv
  - fallback_cache/manifest.json

Dependency:
  - requests
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


# =========================
# Config
# =========================

SCRIPT_VERSION = "fallback_vA_official_no_key_lock"

OUT_DIR = Path("fallback_cache")
LATEST_JSON = OUT_DIR / "latest.json"
LATEST_CSV = OUT_DIR / "latest.csv"
MANIFEST_JSON = OUT_DIR / "manifest.json"

UA = "fred-cache-fallback/1.0 (+github-actions)"
TIMEOUT = 20

# Sources (official / no-key first)
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

TREASURY_DAILY_CURVE_TEMPLATE = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/all/{yyyymm}?"
    "_format=csv&field_tdr_date_value_month={yyyymm}&page=&type=daily_treasury_yield_curve"
)

CHICAGO_FED_NFCI_CSV = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"

# FRED "graph" CSV endpoints (usually no key required)
FRED_GRAPH_CSV_TEMPLATE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

# Non-official backups (explicitly labeled)
STOOQ_DAILY_TEMPLATE = "https://stooq.com/q/d/l/?s={symbol}&i=d"
DATAHUB_WTI_DAILY = "https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv"


# =========================
# Utilities
# =========================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def iso_utc(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def sleep_polite(sec: float = 0.2) -> None:
    time.sleep(sec)

def http_get_text(url: str) -> str:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.upper() in {"NA", "N/A", "NULL", "NONE"}:
        return None
    # FRED often uses "." for missing
    if s == ".":
        return None
    try:
        return float(s)
    except Exception:
        return None

def normalize_date_to_iso(d: str) -> Optional[str]:
    """
    Accepts common formats:
      - YYYY-MM-DD
      - MM/DD/YYYY
      - M/D/YYYY
      - YYYY/MM/DD
    Returns YYYY-MM-DD or None
    """
    if not d:
        return None
    s = str(d).strip()
    if s.upper() in {"NA", "N/A", "NULL", "NONE", "."}:
        return None

    # Try a few common formats
    fmts = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Some CSVs may include time or extra spaces; attempt split
    try:
        s2 = s.split()[0]
        for f in ["%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"]:
            try:
                dt = datetime.strptime(s2, f)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    except Exception:
        pass

    return None

def yyyymm_candidates(now_utc: datetime) -> List[str]:
    """Return [current YYYYMM, previous YYYYMM] to survive month boundary."""
    y = now_utc.year
    m = now_utc.month
    cur = f"{y}{m:02d}"
    if m == 1:
        prev = f"{y-1}12"
    else:
        prev = f"{y}{m-1:02d}"
    return [cur, prev]

def raw_branch_url(owner_repo: str, branch: str, path: str) -> str:
    # using refs/heads style for clarity
    return f"https://raw.githubusercontent.com/{owner_repo}/refs/heads/{branch}/{path}"

def raw_pinned_url(owner_repo: str, sha: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner_repo}/{sha}/{path}"

def get_repo_owner_repo() -> Optional[str]:
    # GitHub provides GITHUB_REPOSITORY like "Joseph-Chou911/fred-cache"
    return os.environ.get("GITHUB_REPOSITORY")

def get_sha() -> Optional[str]:
    return os.environ.get("GITHUB_SHA")


# =========================
# Output row model
# =========================

def make_row(
    series_id: str,
    data_date: Any,
    value: Any,
    source_url: str,
    notes: str,
    as_of_ts: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "series_id": series_id,
        "data_date": data_date if data_date is not None else "NA",
        "value": value if value is not None else "NA",
        "source_url": source_url if source_url else "NA",
        "notes": notes if notes else "NA",
        "as_of_ts": as_of_ts,
    }
    if extra:
        row.update(extra)
    return row


# =========================
# Fetchers
# =========================

def fetch_cboe_vix(as_of_ts: str) -> Dict[str, Any]:
    """
    CBOE VIX history CSV typically has columns like:
      DATE, OPEN, HIGH, LOW, CLOSE
    Date often in MM/DD/YYYY.
    We take the latest valid CLOSE.
    """
    url = CBOE_VIX_CSV
    try:
        text = http_get_text(url)
        reader = csv.DictReader(text.splitlines())
        best_date = None
        best_val = None
        for r in reader:
            d = normalize_date_to_iso(r.get("DATE") or r.get("Date") or r.get("date") or "")
            v = safe_float(r.get("CLOSE") or r.get("Close") or r.get("close"))
            if d and v is not None:
                if best_date is None or d > best_date:
                    best_date, best_val = d, v
        if best_date is None or best_val is None:
            return make_row("VIXCLS", "NA", "NA", url, "ERR:no_valid_rows", as_of_ts)
        return make_row("VIXCLS", best_date, best_val, url, "WARN:fallback_cboe_vix", as_of_ts)
    except Exception as e:
        return make_row("VIXCLS", "NA", "NA", url, f"ERR:{type(e).__name__}", as_of_ts)

def fetch_treasury_curve(as_of_ts: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Treasury daily yield curve CSV.
    We need:
      - DGS10 (10 Yr)
      - DGS2  (2 Yr)
      - UST3M (3 Mo)
      - T10Y2Y derived (10Y-2Y)
      - T10Y3M derived (10Y-3M)

    CSV columns often:
      Date, 1 Mo, 2 Mo, 3 Mo, ..., 2 Yr, ..., 10 Yr, ...
    """
    now = utc_now()
    months = yyyymm_candidates(now)

    last_row = None
    last_url = None
    last_date = None

    def pick_col(row: Dict[str, str], candidates: List[str]) -> Optional[str]:
        # match by normalized header
        keys = list(row.keys())
        norm_map = {k: "".join(k.strip().lower().split()) for k in keys if k is not None}
        for cand in candidates:
            c = "".join(cand.strip().lower().split())
            for k, nk in norm_map.items():
                if nk == c:
                    return k
        return None

    try:
        for yyyymm in months:
            url = TREASURY_DAILY_CURVE_TEMPLATE.format(yyyymm=yyyymm)
            try:
                text = http_get_text(url)
                reader = csv.DictReader(text.splitlines())
                for r in reader:
                    d_raw = r.get("Date") or r.get("DATE") or r.get("date") or ""
                    d = normalize_date_to_iso(d_raw)
                    if not d:
                        continue
                    if last_date is None or d > last_date:
                        last_date = d
                        last_row = r
                        last_url = url
                if last_row and last_url:
                    break
            except Exception:
                continue

        if not last_row or not last_url or not last_date:
            err = make_row("DGS10", "NA", "NA", TREASURY_DAILY_CURVE_TEMPLATE.format(yyyymm=months[0]), "ERR:treasury_no_valid_rows", as_of_ts)
            na2 = make_row("DGS2", "NA", "NA", err["source_url"], "ERR:treasury_no_valid_rows", as_of_ts)
            na3 = make_row("UST3M", "NA", "NA", err["source_url"], "ERR:treasury_no_valid_rows", as_of_ts)
            na4 = make_row("T10Y2Y", "NA", "NA", err["source_url"], "ERR:treasury_no_valid_rows", as_of_ts)
            na5 = make_row("T10Y3M", "NA", "NA", err["source_url"], "ERR:treasury_no_valid_rows", as_of_ts)
            return err, na2, na3, na4, na5

        col_10y = pick_col(last_row, ["10 Yr", "10Year", "10y", "10yr"])
        col_2y = pick_col(last_row, ["2 Yr", "2Year", "2y", "2yr"])
        col_3m = pick_col(last_row, ["3 Mo", "3Month", "3m", "3mo"])

        v10 = safe_float(last_row.get(col_10y)) if col_10y else None
        v2 = safe_float(last_row.get(col_2y)) if col_2y else None
        v3m = safe_float(last_row.get(col_3m)) if col_3m else None

        r10 = make_row("DGS10", last_date, v10 if v10 is not None else "NA", last_url,
                       "WARN:fallback_treasury_csv" if v10 is not None else "ERR:missing_10y", as_of_ts)
        r2 = make_row("DGS2", last_date, v2 if v2 is not None else "NA", last_url,
                      "WARN:fallback_treasury_csv" if v2 is not None else "ERR:missing_2y", as_of_ts)
        r3m = make_row("UST3M", last_date, v3m if v3m is not None else "NA", last_url,
                       "WARN:fallback_treasury_csv" if v3m is not None else "ERR:missing_3m", as_of_ts)

        t10y2y = (v10 - v2) if (v10 is not None and v2 is not None) else None
        t10y3m = (v10 - v3m) if (v10 is not None and v3m is not None) else None

        r_t10y2y = make_row("T10Y2Y", last_date, t10y2y if t10y2y is not None else "NA", last_url,
                            "WARN:derived_from_treasury(10Y-2Y)" if t10y2y is not None else "ERR:cannot_derive(10Y-2Y)",
                            as_of_ts)
        r_t10y3m = make_row("T10Y3M", last_date, t10y3m if t10y3m is not None else "NA", last_url,
                            "WARN:derived_from_treasury(10Y-3M)" if t10y3m is not None else "ERR:cannot_derive(10Y-3M)",
                            as_of_ts)
        return r10, r2, r3m, r_t10y2y, r_t10y3m

    except Exception as e:
        base_url = TREASURY_DAILY_CURVE_TEMPLATE.format(yyyymm=months[0])
        err = make_row("DGS10", "NA", "NA", base_url, f"ERR:{type(e).__name__}", as_of_ts)
        na2 = make_row("DGS2", "NA", "NA", base_url, f"ERR:{type(e).__name__}", as_of_ts)
        na3 = make_row("UST3M", "NA", "NA", base_url, f"ERR:{type(e).__name__}", as_of_ts)
        na4 = make_row("T10Y2Y", "NA", "NA", base_url, f"ERR:{type(e).__name__}", as_of_ts)
        na5 = make_row("T10Y3M", "NA", "NA", base_url, f"ERR:{type(e).__name__}", as_of_ts)
        return err, na2, na3, na4, na5

def fetch_chicagofed_nfci_nonfin_leverage(as_of_ts: str) -> Dict[str, Any]:
    """
    Chicago Fed NFCI CSV.
    We try to locate DATE column and NFCINONFINLEVERAGE column (case-insensitive).
    """
    url = CHICAGO_FED_NFCI_CSV
    try:
        text = http_get_text(url)
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            return make_row("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:missing_headers", as_of_ts)

        # normalize headers
        norm = {h: "".join(h.strip().upper().split()) for h in reader.fieldnames if h}
        date_key = None
        for h, nh in norm.items():
            if nh in {"DATE", "DATES"}:
                date_key = h
                break
        if not date_key:
            # sometimes "TIME" or similar; last resort: find any header containing 'DATE'
            for h, nh in norm.items():
                if "DATE" in nh:
                    date_key = h
                    break
        if not date_key:
            return make_row("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:missing_date_col", as_of_ts)

        target_key = None
        # preferred exact code
        for h, nh in norm.items():
            if nh == "NFCINONFINLEVERAGE":
                target_key = h
                break
        # fallback: contains code
        if not target_key:
            for h, nh in norm.items():
                if "NFCINONFINLEVERAGE" in nh:
                    target_key = h
                    break

        if not target_key:
            return make_row("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:chicagofed_nfci_missing_col", as_of_ts)

        best_date = None
        best_val = None
        for r in reader:
            d = normalize_date_to_iso(r.get(date_key, ""))
            v = safe_float(r.get(target_key))
            if d and v is not None:
                if best_date is None or d > best_date:
                    best_date, best_val = d, v

        if best_date is None or best_val is None:
            return make_row("NFCINONFINLEVERAGE", "NA", "NA", url, "ERR:no_valid_rows", as_of_ts)

        return make_row(
            "NFCINONFINLEVERAGE",
            best_date,
            best_val,
            url,
            "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
            as_of_ts,
        )

    except Exception as e:
        return make_row("NFCINONFINLEVERAGE", "NA", "NA", url, f"ERR:{type(e).__name__}", as_of_ts)

def fetch_fredgraph_series(series_id: str, as_of_ts: str) -> Dict[str, Any]:
    """
    FRED graph CSV: DATE, <series_id>
    Some values may be '.'.
    """
    url = FRED_GRAPH_CSV_TEMPLATE.format(series_id=series_id)
    try:
        text = http_get_text(url)
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            return make_row(series_id, "NA", "NA", url, "ERR:fredgraph_missing_headers", as_of_ts)

        # find date col
        date_key = None
        for h in reader.fieldnames:
            if h and h.strip().upper() == "DATE":
                date_key = h
                break
        if not date_key:
            date_key = reader.fieldnames[0]

        # find value col (series id)
        val_key = None
        for h in reader.fieldnames:
            if h and h.strip().upper() == series_id.upper():
                val_key = h
                break
        if not val_key:
            # often second column
            if len(reader.fieldnames) >= 2:
                val_key = reader.fieldnames[1]

        best_date = None
        best_val = None
        for r in reader:
            d = normalize_date_to_iso(r.get(date_key, ""))
            v = safe_float(r.get(val_key, "")) if val_key else None
            if d and v is not None:
                if best_date is None or d > best_date:
                    best_date, best_val = d, v

        if best_date is None or best_val is None:
            return make_row(series_id, "NA", "NA", url, "ERR:fredgraph_no_valid_rows", as_of_ts)

        return make_row(series_id, best_date, best_val, url, f"WARN:fredgraph_no_key({series_id})", as_of_ts)

    except Exception as e:
        return make_row(series_id, "NA", "NA", url, f"ERR:{type(e).__name__}", as_of_ts)

def fetch_stooq_index(series_id: str, symbol: str, as_of_ts: str) -> Dict[str, Any]:
    """
    Stooq daily CSV: Date,Open,High,Low,Close,Volume
    We take latest Close, and 1-day pct change from prior Close.
    """
    url = STOOQ_DAILY_TEMPLATE.format(symbol=symbol)
    try:
        text = http_get_text(url)
        reader = csv.DictReader(text.splitlines())
        rows = []
        for r in reader:
            d = normalize_date_to_iso(r.get("Date") or r.get("DATE") or "")
            c = safe_float(r.get("Close") or r.get("CLOSE"))
            if d and c is not None:
                rows.append((d, c))
        if not rows:
            return make_row(series_id, "NA", "NA", url, "ERR:empty", as_of_ts)

        rows.sort(key=lambda x: x[0])
        last_d, last_c = rows[-1]
        extra = {}

        if len(rows) >= 2:
            prev_d, prev_c = rows[-2]
            if prev_c is not None and prev_c != 0:
                extra["change_pct_1d"] = (last_c - prev_c) / prev_c * 100.0

        return make_row(
            series_id,
            last_d,
            last_c,
            url,
            f"WARN:nonofficial_stooq({symbol});derived_1d_pct",
            as_of_ts,
            extra=extra if extra else None,
        )
    except Exception as e:
        return make_row(series_id, "NA", "NA", url, f"ERR:{type(e).__name__}", as_of_ts)

def fetch_datahub_wti(as_of_ts: str) -> Dict[str, Any]:
    """
    datahub.io WTI daily CSV: Date, Price
    """
    url = DATAHUB_WTI_DAILY
    try:
        text = http_get_text(url)
        reader = csv.DictReader(text.splitlines())
        best_date = None
        best_val = None
        for r in reader:
            d = normalize_date_to_iso(r.get("Date") or r.get("DATE") or r.get("date") or "")
            v = safe_float(r.get("Price") or r.get("price"))
            if d and v is not None:
                if best_date is None or d > best_date:
                    best_date, best_val = d, v
        if best_date is None or best_val is None:
            return make_row("DCOILWTICO", "NA", "NA", url, "ERR:no_valid_rows", as_of_ts)
        return make_row("DCOILWTICO", best_date, best_val, url, "WARN:nonofficial_datahub_oil_prices(wti-daily)", as_of_ts)
    except Exception as e:
        return make_row("DCOILWTICO", "NA", "NA", url, f"ERR:{type(e).__name__}", as_of_ts)


# =========================
# Writers
# =========================

def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    # Collect union of keys for stable schema
    keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def build_manifest(owner_repo: Optional[str], sha: Optional[str], generated_at_utc: str, as_of_ts: str) -> Dict[str, Any]:
    # Provide both branch and pinned links for auditability
    branch = "main"
    base = "fallback_cache"

    manifest: Dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "as_of_ts": as_of_ts,
        "data_commit_sha": sha if sha else "NA",
        "script_version": SCRIPT_VERSION,
        "paths": {
            "latest_json": str(LATEST_JSON),
            "latest_csv": str(LATEST_CSV),
            "manifest_json": str(MANIFEST_JSON),
        },
        "branch": {},
        "pinned": {},
    }

    if owner_repo:
        manifest["branch"] = {
            "latest_json": raw_branch_url(owner_repo, branch, f"{base}/latest.json"),
            "latest_csv": raw_branch_url(owner_repo, branch, f"{base}/latest.csv"),
            "manifest_json": raw_branch_url(owner_repo, branch, f"{base}/manifest.json"),
        }
        if sha and sha != "NA":
            manifest["pinned"] = {
                "latest_json": raw_pinned_url(owner_repo, sha, f"{base}/latest.json"),
                "latest_csv": raw_pinned_url(owner_repo, sha, f"{base}/latest.csv"),
                "manifest_json": raw_pinned_url(owner_repo, sha, f"{base}/manifest.json"),
            }
        else:
            manifest["pinned"] = {
                "latest_json": "NA",
                "latest_csv": "NA",
                "manifest_json": "NA",
            }
    else:
        manifest["branch"] = {"latest_json": "NA", "latest_csv": "NA", "manifest_json": "NA"}
        manifest["pinned"] = {"latest_json": "NA", "latest_csv": "NA", "manifest_json": "NA"}

    return manifest


# =========================
# Main
# =========================

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    as_of = iso_utc(now)
    generated_at = iso_utc(now)

    owner_repo = get_repo_owner_repo()
    sha = get_sha()

    rows: List[Dict[str, Any]] = []

    # META row (always changes)
    rows.append(
        make_row(
            "__META__",
            now.strftime("%Y-%m-%d"),
            SCRIPT_VERSION,
            "NA",
            "INFO:script_version",
            as_of,
        )
    )

    # 1) VIX (official no-key)
    rows.append(fetch_cboe_vix(as_of))
    sleep_polite()

    # 2) Treasury (official no-key)
    r10, r2, r3m, r_t10y2y, r_t10y3m = fetch_treasury_curve(as_of)
    rows.extend([r10, r2, r3m, r_t10y2y, r_t10y3m])
    sleep_polite()

    # 3) Chicago Fed NFCI (official no-key)
    rows.append(fetch_chicagofed_nfci_nonfin_leverage(as_of))
    sleep_polite()

    # 4) HY OAS (prefer no-key via FRED graph CSV; you already confirmed it works)
    rows.append(fetch_fredgraph_series("BAMLH0A0HYM2", as_of))
    sleep_polite()

    # 5) Equity indices (non-official; explicitly labeled)
    rows.append(fetch_stooq_index("SP500", "^spx", as_of))
    sleep_polite()
    rows.append(fetch_stooq_index("NASDAQCOM", "^ndq", as_of))
    sleep_polite()
    rows.append(fetch_stooq_index("DJIA", "^dji", as_of))
    sleep_polite()

    # 6) WTI (non-official fallback)
    rows.append(fetch_datahub_wti(as_of))

    # Write outputs
    write_json(LATEST_JSON, rows)
    write_csv(LATEST_CSV, rows)

    manifest = build_manifest(owner_repo, sha, generated_at, as_of)
    write_json(MANIFEST_JSON, manifest)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception as e:
        # Hard guard: never crash silently
        sys.stderr.write(f"[FATAL] {type(e).__name__}: {e}\n")
        raise SystemExit(2)