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
    return datetime.now(TAIPEI_TZ).replace(microsecond=0).isoformat()


def yyyymm_taipei(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now(TAIPEI_TZ)
    return dt.strftime("%Y%m")


def prev_month_yyyymm(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now(TAIPEI_TZ)
    y = dt.year
    m = dt.month
    if m == 1:
        return f"{y-1}12"
    return f"{y}{m-1:02d}"


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
        if s == "" or s.upper() in ("NA", "N/A"):
            return None
        return float(s)
    except Exception:
        return None


def normalize_date(s: str) -> str:
    """
    Normalize to YYYY-MM-DD when possible.
    Accepts:
      - YYYY-MM-DD
      - MM/DD/YYYY
    Otherwise returns original trimmed (or "NA").
    """
    s = (s or "").strip()
    if not s:
        return "NA"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        mm, dd, yyyy = s.split("/")
        return f"{yyyy}-{mm}-{dd}"
    if len(s) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s[:10]):
        return s[:10]
    return s


def backoff_get(url: str, timeout: int = 25, max_retries: int = 3) -> requests.Response:
    """
    Retry on transient errors: 429/5xx/timeouts/connection errors
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
# Cache row schema
# -----------------------------

@dataclass
class CacheRow:
    series_id: str
    data_date: str     # YYYY-MM-DD or "NA"
    value: object      # float or "NA"
    source_url: str
    notes: str
    as_of_ts: str      # cache generation timestamp (UTC ISO)


def make_row(series_id: str, data_date: Optional[str], value: Optional[float], source_url: str, notes: str, as_of_ts: str) -> CacheRow:
    return CacheRow(
        series_id=series_id,
        data_date=normalize_date(data_date or "NA"),
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
    Date is usually YYYY-MM-DD already.
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
    d = normalize_date(last[date_i])
    v = safe_float(last[close_i])
    if v is None:
        raise RuntimeError("Cboe VIX close is NA")
    return d, v, url


def treasury_csv_url(month_yyyymm: str) -> str:
    """
    Treasury 'Download CSV' endpoint (with month param).
    """
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/all/{month_yyyymm}"
        f"?_format=csv&field_tdr_date_value_month={month_yyyymm}&page=&type=daily_treasury_yield_curve"
    )


def fetch_treasury_yield_curve_last_row(month_yyyymm: Optional[str] = None) -> Tuple[str, Dict[str, float], str]:
    """
    Use Treasury 'Download CSV' and parse by column names.
    Needed columns: '3 Mo', '2 Yr', '10 Yr'.
    Walk backward to find the latest row with at least one needed value.
    If current month CSV is empty, try previous month once.
    """
    if month_yyyymm is None:
        month_yyyymm = yyyymm_taipei()

    url = treasury_csv_url(month_yyyymm)
    r = backoff_get(url)

    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    reader = csv.DictReader(lines)
    rows = list(reader)

    if not rows:
        pm = prev_month_yyyymm()
        url2 = treasury_csv_url(pm)
        r2 = backoff_get(url2)
        lines2 = [ln for ln in r2.text.splitlines() if ln.strip()]
        reader2 = csv.DictReader(lines2)
        rows = list(reader2)
        url = url2

    if not rows:
        raise RuntimeError("Treasury CSV empty (current and previous month).")

    def f(row: Dict[str, str], col: str) -> Optional[float]:
        v = (row.get(col) or "").strip()
        if v.upper() in ("", "NA", "N/A"):
            return None
        try:
            return float(v)
        except Exception:
            return None

    last_row = None
    for row in reversed(rows):
        if f(row, "10 Yr") is not None or f(row, "2 Yr") is not None or f(row, "3 Mo") is not None:
            last_row = row
            break

    if last_row is None:
        raise RuntimeError("Treasury CSV has rows but none contain 3 Mo / 2 Yr / 10 Yr values.")

    data_date = normalize_date(last_row.get("Date", "NA"))

    out: Dict[str, float] = {}
    y_3m = f(last_row, "3 Mo")
    y_2y = f(last_row, "2 Yr")
    y_10y = f(last_row, "10 Yr")

    if y_3m is not None:
        out["3M"] = y_3m
    if y_2y is not None:
        out["2Y"] = y_2y
    if y_10y is not None:
        out["10Y"] = y_10y

    if not out:
        raise RuntimeError("Treasury CSV parsed but all needed columns are missing/NA on latest row.")

    return data_date, out, url


def fetch_chicagofed_nfci_csv_last() -> Tuple[str, Dict[str, float], str]:
    """
    Chicago Fed NFCI data CSV.
    Conservative mapping:
      - map to NFCINONFINLEVERAGE only if column name contains BOTH 'nonfinancial' and 'leverage'
      - else if a generic leverage subindex exists, store as NFCI_LEVERAGE_SUBINDEX (not mapped)
    """
    url = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
    r = backoff_get(url)

    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    reader = csv.DictReader(lines)
    rows = list(reader)
    if not rows:
        raise RuntimeError("Chicago Fed NFCI CSV empty")

    last = rows[-1]

    date_key = None
    for k in last.keys():
        lk = k.strip().lower()
        if lk in ("date", "observation_date"):
            date_key = k
            break
    if date_key is None:
        date_key = list(last.keys())[0]

    data_date = normalize_date(last.get(date_key, "NA"))

    out: Dict[str, float] = {}

    for k, v in last.items():
        lk = k.strip().lower()
        fv = safe_float(v or "")
        if fv is None:
            continue

        if lk == "nfci" or lk.endswith(" nfci") or lk.endswith("_nfci"):
            out["NFCI"] = fv

        if "nonfinancial" in lk and "leverage" in lk:
            out["NFCINONFINLEVERAGE"] = fv

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

    Added:
      - UST3M: explicit 3-month Treasury yield from Treasury CSV ("3 Mo")
    """
    expected = [
        "VIXCLS",
        "DGS10",
        "DGS2",
        "UST3M",
        "T10Y2Y",
        "T10Y3M",
        "NFCINONFINLEVERAGE",
        "NFCI_LEVERAGE_SUBINDEX",
    ]

    rows: Dict[str, CacheRow] = {sid: make_row(sid, None, None, "NA", "NA", as_of_ts) for sid in expected}

    # 1) VIX from Cboe
    try:
        d, v, src = fetch_cboe_vix_last_close()
        rows["VIXCLS"] = make_row("VIXCLS", d, v, src, "WARN:fallback_cboe_vix", as_of_ts)
    except Exception as e:
        rows["VIXCLS"] = make_row("VIXCLS", None, None, "NA", f"ERR:cboe_vix:{type(e).__name__}", as_of_ts)

    # 2) Treasury yields -> DGS10/DGS2/UST3M and derived spreads
    treasury_month = os.environ.get("TREASURY_MONTH")  # optional YYYYMM override
    try:
        d, y, src = fetch_treasury_yield_curve_last_row(treasury_month)

        if "10Y" in y:
            rows["DGS10"] = make_row("DGS10", d, y["10Y"], src, "WARN:fallback_treasury_csv", as_of_ts)
        else:
            rows["DGS10"] = make_row("DGS10", None, None, src, "ERR:treasury_missing_10y", as_of_ts)

        if "2Y" in y:
            rows["DGS2"] = make_row("DGS2", d, y["2Y"], src, "WARN:fallback_treasury_csv", as_of_ts)
        else:
            rows["DGS2"] = make_row("DGS2", None, None, src, "ERR:treasury_missing_2y", as_of_ts)

        if "3M" in y:
            rows["UST3M"] = make_row("UST3M", d, y["3M"], src, "WARN:fallback_treasury_csv", as_of_ts)
        else:
            rows["UST3M"] = make_row("UST3M", None, None, src, "WARN:treasury_missing_3m", as_of_ts)

        if "10Y" in y and "2Y" in y:
            rows["T10Y2Y"] = make_row(
                "T10Y2Y",
                d,
                y["10Y"] - y["2Y"],
                src,
                "WARN:derived_from_treasury(10Y-2Y)",
                as_of_ts,
            )
        else:
            rows["T10Y2Y"] = make_row("T10Y2Y", None, None, src, "ERR:treasury_insufficient_for_10y2y", as_of_ts)

        # Now derived from explicit UST3M (if present)
        if "10Y" in y and "3M" in y:
            rows["T10Y3M"] = make_row(
                "T10Y3M",
                d,
                y["10Y"] - y["3M"],
                src,
                "WARN:derived_from_treasury(10Y-3M)",
                as_of_ts,
            )
        else:
            rows["T10Y3M"] = make_row("T10Y3M", None, None, src, "WARN:treasury_no_3m_or_latest_missing", as_of_ts)

    except Exception as e:
        rows["DGS10"] = make_row("DGS10", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)
        rows["DGS2"] = make_row("DGS2", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)
        rows["UST3M"] = make_row("UST3M", None, None, "NA", f"ERR:treasury:{type(e).__name__}", as_of_ts)
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

    return [rows[sid] for sid in expected]


def write_outputs(out_dir: str, latest_rows: List[CacheRow]) -> None:
    os.makedirs(out_dir, exist_ok=True)

    latest = [row_to_dict(r) for r in latest_rows]

    # latest.json
    latest_path = os.path.join(out_dir, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    # manifest.json (standalone, latest-only)
    manifest = {
        "generated_at_utc": utc_now_iso(),
        "as_of_ts": taipei_now_iso(),
        "data_commit_sha": git_head_sha(),
        "sources": {
            "cboe_vix_csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
            "treasury_daily_csv": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv",
            "chicagofed_nfci_csv": "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv",
        },
        "files": {
            "latest_json": f"{out_dir}/latest.json",
            "manifest_json": f"{out_dir}/manifest.json",
            "latest_csv": f"{out_dir}/latest.csv",
        },
        "notes": "Standalone fallback cache (latest-only). Adds UST3M. Does NOT produce history.json.",
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # latest.csv (debug)
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