import csv
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


# -----------------------------
# Utilities
# -----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def taipei_now_iso() -> str:
    # e.g. 2026-01-04T10:15:30+08:00
    return datetime.now(TAIPEI_TZ).replace(microsecond=0).isoformat()


def git_head_sha() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if re.fullmatch(r"[0-9a-f]{40}", out):
            return out
    except Exception:
        pass
    return "NA"


def safe_float(x: str) -> Optional[float]:
    try:
        s = (x or "").strip()
        if s == "" or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None


def backoff_get(url: str, timeout: int = 25, max_retries: int = 3) -> requests.Response:
    """
    Retry on transient errors: 429/5xx/timeout/connection errors
    Backoff: 2s -> 4s -> 8s (max 3 retries)
    """
    last_err = None
    waits = [0, 2, 4, 8]
    for i in range(min(max_retries + 1, len(waits))):
        if waits[i]:
            time.sleep(waits[i])
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "fallback-cache-bot/1.0"})
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = RuntimeError(f"HTTP {r.status_code} for {url}")
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"GET failed after retries: {url} :: {last_err}")


# -----------------------------
# Cache row schema (compatible with your latest.json style)
# -----------------------------

@dataclass
class CacheRow:
    series_id: str
    data_date: str     # YYYY-MM-DD or "NA"
    value: object      # float or "NA"
    source_url: str
    notes: str
    as_of_ts: str      # cache generation timestamp


def make_row(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str, as_of_ts: str) -> CacheRow:
    return CacheRow(
        series_id=series_id,
        data_date=data_date if data_date else "NA",
        value=value if value is not None else "NA",
        source_url=source_url if source_url else "NA",
        notes=notes if notes else "NA",
        as_of_ts=as_of_ts,
    )


def row_to_dict(r: CacheRow) -> Dict:
    return {
        "series_id": r.series_id,
        "data_date": r.data_date,
        "value": r.value,
        "source_url": r.source_url,
        "notes": r.notes,
        "as_of_ts": r.as_of_ts,
    }


# -----------------------------
# Fetchers (fallback sources)
# -----------------------------

def fetch_cboe_vix_last_close() -> Tuple[str, float, str]:
    """
    Cboe VIX daily history CSV. Use last row CLOSE.
    """
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    r = backoff_get(url)
    lines = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise RuntimeError("Cboe VIX CSV too short")

    header = [h.strip().upper() for h in lines[0].split(",")]
    if "DATE" not in header or "CLOSE" not in header:
        raise RuntimeError(f"Cboe VIX CSV header unexpected: {header}")

    date_i = header.index("DATE")
    close_i = header.index("CLOSE")

    last = [c.strip() for c in lines[-1].split(",")]
    d = last[date_i]  # YYYY-MM-DD
    v = safe_float(last[close_i])
    if v is None:
        raise RuntimeError("Cboe VIX close is NA")
    return d, v, url


def fetch_treasury_yield_curve_last_row(month_yyyymm: Optional[str] = None) -> Tuple[str, Dict[str, float], str]:
    """
    U.S. Treasury TextView table (no key).
    Extract latest row yields: 3M, 2Y, 10Y (if present).
    """
    if month_yyyymm is None:
        month_yyyymm = datetime.now(TAIPEI_TZ).strftime("%Y%m")

    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView"
        f"?type=daily_treasury_yield_curve&field_tdr_date_value_month={month_yyyymm}"
    )
    r = backoff_get(url)
    html = r.text

    # Find table rows with <td> cells, where first cell is date MM/DD/YYYY
    tr_blocks = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S | re.I)
    data_rows: List[List[str]] = []
    for blk in tr_blocks:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", blk, flags=re.S | re.I)
        if not tds:
            continue
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in tds]
        if cells and re.fullmatch(r"\d{2}/\d{2}/\d{4}", cells[0]):
            data_rows.append(cells)

    if not data_rows:
        raise RuntimeError("Treasury TextView parse found no data rows (month may be empty or layout changed).")

    last = data_rows[-1]
    mm, dd, yyyy = last[0].split("/")
    data_date = f"{yyyy}-{mm}-{dd}"

    # Typical column positions:
    # Date, 1 Mo, 1.5 Mo, 2 Mo, 3 Mo, 4 Mo, 6 Mo, 1 Yr, 2 Yr, 3 Yr, 5 Yr, 7 Yr, 10 Yr, 20 Yr, 30 Yr
    def get(idx: int) -> Optional[float]:
        if idx >= len(last):
            return None
        return safe_float(last[idx])

    out: Dict[str, float] = {}
    y_3m = get(4)
    y_2y = get(8)
    y_10y = get(12)

    if y_3m is not None:
        out["3M"] = y_3m
    if y_2y is not None:
        out["2Y"] = y_2y
    if y_10y is not None:
        out["10Y"] = y_10y

    if not out:
        raise RuntimeError("Treasury last row parsed but yields all NA (layout changed).")

    return data_date, out, url


def fetch_chicagofed_nfci_csv_last() -> Tuple[str, Dict[str, float], str]:
    """
    Chicago Fed NFCI data CSV.
    Conservative mapping:
      - only map to NFCINONFINLEVERAGE if column name contains BOTH 'nonfinancial' and 'leverage'
      - otherwise, if we see a generic leverage subindex column, store as NFCI_LEVERAGE_SUBINDEX
    """
    url = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
    r = backoff_get(url)
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    reader = csv.DictReader(lines)
    rows = list(reader)
    if not rows:
        raise RuntimeError("Chicago Fed NFCI CSV empty")

    last = rows[-1]

    # Date column heuristic
    date_key = None
    for k in last.keys():
        lk = k.strip().lower()
        if lk in ("date", "observation_date"):
            date_key = k
            break
    if date_key is None:
        date_key = list(last.keys())[0]

    d_raw = (last.get(date_key) or "").strip()
    # Normalize MM/DD/YYYY -> YYYY-MM-DD if needed
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", d_raw):
        mm, dd, yyyy = d_raw.split("/")
        data_date = f"{yyyy}-{mm}-{dd}"
    else:
        data_date = d_raw[:10] if len(d_raw) >= 10 else d_raw

    out: Dict[str, float] = {}

    for k, v in last.items():
        lk = k.strip().lower()
        fv = safe_float(v or "")
        if fv is None:
            continue

        # overall NFCI (optional)
        if lk == "nfci" or lk.endswith(" nfci") or lk.endswith("_nfci"):
            out["NFCI"] = fv

        # conservative mapping to nonfinancial leverage
        if "nonfinancial" in lk and "leverage" in lk:
            out["NFCINONFINLEVERAGE"] = fv

        # generic leverage subindex (only if nonfinancial leverage not found)
        if "leverage" in lk and "subindex" in lk and "NFCINONFINLEVERAGE" not in out:
            out["NFCI_LEVERAGE_SUBINDEX"] = fv

    return data_date, out, url


# -----------------------------
# Build latest-only cache
# -----------------------------

def build_latest_rows(as_of_ts: str) -> List[CacheRow]:
    """
    Always output a stable set of series_ids (fill NA if missing),
    so your dashboard can reliably look them up.
    """
    expected = [
        "VIXCLS",
        "DGS10",
        "DGS2",
        "T10Y2Y",
        "T10Y3M",
        "NFCINONFINLEVERAGE",
        "NFCI_LEVERAGE_SUBINDEX",  # will be NA unless discovered (or used as non-equal fallback)
    ]

    rows: Dict[str, CacheRow] = {sid: make_row(sid, None, None, "NA", "NA", as_of_ts) for sid in expected}

    # 1) VIX from Cboe
    try:
        d, v, src = fetch_cboe_vix_last_close()
        rows["VIXCLS"] = make_row("VIXCLS", d, v, src, "WARN:fallback_cboe_vix", as_of_ts)
    except Exception as e:
        rows["VIXCLS"] = make_row("VIXCLS", None, None, "NA", f"ERR:cboe_vix:{type(e).__name__}", as_of_ts)

    # 2) Treasury yields -> DGS10/DGS2 and derived spreads
    treasury_month = os.environ.get("TREASURY_MONTH")  # optional: YYYYMM
    try:
        d, y, src = fetch_treasury_yield_curve_last_row(treasury_month)
        if "10Y" in y:
            rows["DGS10"] = make_row("DGS10", d, y["10Y"], src, "WARN:fallback_treasury", as_of_ts)
        else:
            rows["DGS10"] = make_row("DGS10", None, None, src, "ERR:treasury_missing_10y", as_of_ts)

        if "2Y" in y:
            rows["DGS2"] = make_row("DGS2", d, y["2Y"], src, "WARN:fallback_treasury", as_of_ts)
        else:
            rows["DGS2"] = make_row("DGS2", None, None, src, "ERR:treasury_missing_2y", as_of_ts)

        if "10Y" in y and "2Y" in y:
            rows["T10Y2Y"] = make_row("T10Y2Y", d, y["10Y"] - y["2Y"], src, "WARN:derived_from_treasury(10Y-2Y)", as_of_ts)
        else:
            rows["T10Y2Y"] = make_row("T10Y2Y", None, None, src, "ERR:treasury_insufficient_for_10y2y", as_of_ts)

        if "10Y" in y and "3M" in y:
            rows["T10Y3M"] = make_row("T10Y3M", d, y["10Y"] - y["3M"], src, "WARN:derived_from_treasury(10Y-3M)", as_of_ts)
        else:
            # common if 3M column missing or parse changed; do NOT guess
            rows["T10Y3M"] = make_row("T10Y3M", None, None, src, "WARN:treasury_no_3m_or_parse_missing", as_of_ts)

    except Exception as e:
        rows["DGS10"] = make_row("DGS10", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)
        rows["DGS2"] = make_row("DGS2", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)
        rows["T10Y2Y"] = make_row("T10Y2Y", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)
        rows["T10Y3M"] = make_row("T10Y3M", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)

    # 3) Chicago Fed NFCI -> conservative leverage mapping
    try:
        d, m, src = fetch_chicagofed_nfci_csv_last()
        if "NFCINONFINLEVERAGE" in m:
            rows["NFCINONFINLEVERAGE"] = make_row(
                "NFCINONFINLEVERAGE",
                d,
                m["NFCINONFINLEVERAGE"],
                src,
                "WARN:fallback_chicagofed_nfci(nonfinancial leverage)",
                as_of_ts,
            )
        elif "NFCI_LEVERAGE_SUBINDEX" in m:
            # Do NOT pretend it's identical to NFCINONFINLEVERAGE
            rows["NFCI_LEVERAGE_SUBINDEX"] = make_row(
                "NFCI_LEVERAGE_SUBINDEX",
                d,
                m["NFCI_LEVERAGE_SUBINDEX"],
                src,
                "WARN:fallback_chicagofed_nfci(leverage subindex; not mapped to nonfinancial leverage)",
                as_of_ts,
            )
            rows["NFCINONFINLEVERAGE"] = make_row(
                "NFCINONFINLEVERAGE",
                None,
                None,
                src,
                "WARN:chicagofed_no_explicit_nonfinancial_leverage_column",
                as_of_ts,
            )
        else:
            rows["NFCINONFINLEVERAGE"] = make_row(
                "NFCINONFINLEVERAGE",
                None,
                None,
                src,
                "WARN:chicagofed_nfci_no_leverage_columns_found",
                as_of_ts,
            )
    except Exception as e:
        rows["NFCINONFINLEVERAGE"] = make_row(
            "NFCINONFINLEVERAGE",
            None,
            None,
            "NA",
            f"ERR:chicagofed_nfci:{type(e).__name__}",
            as_of_ts,
        )

    # Keep a consistent order
    return [rows[sid] for sid in expected]


def write_outputs(out_dir: str, latest_rows: List[CacheRow]) -> None:
    os.makedirs(out_dir, exist_ok=True)

    latest = [row_to_dict(r) for r in latest_rows]

    # latest.json
    latest_path = os.path.join(out_dir, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    # manifest.json (standalone)
    manifest = {
        "generated_at_utc": utc_now_iso(),
        "as_of_ts": taipei_now_iso(),
        "data_commit_sha": git_head_sha(),
        "sources": {
            "cboe_vix_csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
            "treasury_textview": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve",
            "chicagofed_nfci_csv": "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv",
        },
        "files": {
            "latest_json": f"{out_dir}/latest.json",
            "manifest_json": f"{out_dir}/manifest.json",
            "latest_csv": f"{out_dir}/latest.csv",
        },
        "notes": "Standalone fallback cache (latest-only). Does NOT produce history.json.",
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # latest.csv (debug / human-readable)
    csv_path = os.path.join(out_dir, "latest.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["series_id", "data_date", "value", "source_url", "notes", "as_of_ts"],
        )
        w.writeheader()
        for r in latest:
            w.writerow(r)

    print(f"[OK] wrote: {latest_path}, {manifest_path}, {csv_path}")


def main() -> None:
    out_dir = os.environ.get("FALLBACK_OUT_DIR", "fallback_cache")
    as_of_ts = utc_now_iso()

    latest_rows = build_latest_rows(as_of_ts=as_of_ts)
    write_outputs(out_dir, latest_rows)


if __name__ == "__main__":
    main()