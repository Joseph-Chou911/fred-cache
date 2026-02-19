#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_tw0050_chip_overlay.py

Goal
- Fetch auditable "chip / positioning" overlays to help interpret:
  {handoff / deleveraging / risk-hedging-rise} vs simple price-only signals.

What it fetches (today + last N trading days, aligned to your price last_date):
1) TWSE T86: 0050 three-institution net (foreign/investment trust/dealer)
2) TWSE TWT72U: 0050 securities lending (stock borrowing) balances (shares + market value)

What it does NOT fetch (kept as NA for now):
- ETF units / shares outstanding time series ("份額") due to unstable public endpoints.

Output
- JSON file with strict NA handling + dq flags + source urls.

Usage (example)
python fetch_tw0050_chip_overlay.py \
  --cache_dir tw0050_bb_cache \
  --stats_path tw0050_bb_cache/stats_latest.json \
  --out_path tw0050_bb_cache/chip_overlay.json \
  --window_n 5 \
  --stock_no 0050
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# Optional: pandas only used for robust HTML fallback parsing
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # type: ignore


SCRIPT_FINGERPRINT = "fetch_tw0050_chip_overlay@2026-02-19.v1"


# ----------------------------
# Helpers: time / IO / parsing
# ----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def warn(msg: str) -> None:
    sys.stderr.write(f"[WARN] {msg}\n")


def info(msg: str) -> None:
    sys.stderr.write(f"[INFO] {msg}\n")


def to_yyyymmdd(date_like: str) -> str:
    """
    Accepts:
      - 'YYYY-MM-DD'
      - 'YYYY/MM/DD'
      - 'YYYYMMDD'
    """
    s = date_like.strip()
    if len(s) == 8 and s.isdigit():
        return s
    s = s.replace("/", "-")
    parts = s.split("-")
    if len(parts) != 3:
        raise ValueError(f"Unrecognized date format: {date_like}")
    y, m, d = parts
    return f"{int(y):04d}{int(m):02d}{int(d):02d}"


def parse_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, int):
        return x
    s = str(x).strip()
    if s == "" or s.upper() in {"N/A", "NA", "--", "NULL"}:
        return None
    # remove commas and spaces
    s = s.replace(",", "").replace(" ", "")
    # parentheses negative
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    # some TWSE values are like "1,234.00" (should be int for shares) -> floor
    try:
        if "." in s:
            return int(float(s))
        return int(s)
    except Exception:
        return None


def parse_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, float):
        return x
    if isinstance(x, int):
        return float(x)
    s = str(x).strip()
    if s == "" or s.upper() in {"N/A", "NA", "--", "NULL"}:
        return None
    s = s.replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except Exception:
        return None


# ----------------------------
# Networking with retry/backoff
# ----------------------------

@dataclass
class FetchResult:
    ok: bool
    url: str
    status_code: Optional[int]
    json_obj: Optional[Dict[str, Any]]
    text: Optional[str]
    error: Optional[str]


def http_get(url: str, timeout: float, retries: int, backoff: float) -> FetchResult:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; audit-fetch/1.0; +https://example.invalid)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
    last_err = None
    last_status = None
    for i in range(max(1, retries)):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            last_status = r.status_code
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                time.sleep(backoff * (2 ** i))
                continue
            # try json first
            try:
                return FetchResult(True, url, r.status_code, r.json(), None, None)
            except Exception:
                # keep html/text for fallback parsing
                return FetchResult(True, url, r.status_code, None, r.text, None)
        except Exception as e:
            last_err = repr(e)
            time.sleep(backoff * (2 ** i))
    return FetchResult(False, url, last_status, None, None, last_err)


# ----------------------------
# TWSE parsers (robust matching)
# ----------------------------

def find_col(fields: List[str], must_have: List[str], must_not_have: Optional[List[str]] = None) -> Optional[int]:
    """
    Find a column index where all 'must_have' substrings appear.
    """
    must_not_have = must_not_have or []
    for i, f in enumerate(fields):
        ok = True
        for k in must_have:
            if k not in f:
                ok = False
                break
        if not ok:
            continue
        for k in must_not_have:
            if k in f:
                ok = False
                break
        if ok:
            return i
    return None


def parse_twse_table_json(js: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    """
    Most TWSE JSON tables look like:
      { "fields": [...], "data": [[...], [...]], ... }
    """
    fields = js.get("fields")
    data = js.get("data")
    if isinstance(fields, list) and isinstance(data, list):
        return [str(x) for x in fields], data
    # Some TWSE endpoints may use 'fields' + 'data' but nested; try fallback keys
    for fk in ("fields1", "fields2", "fields3"):
        if isinstance(js.get(fk), list) and isinstance(js.get("data"), list):
            return [str(x) for x in js[fk]], js["data"]
    raise ValueError("Unrecognized TWSE JSON table structure (no fields/data).")


def parse_t86_for_stock(js: Dict[str, Any], stock_no: str) -> Dict[str, Any]:
    """
    Returns:
      {
        "foreign_net_shares": int|None,
        "trust_net_shares": int|None,
        "dealer_net_shares": int|None,
        "raw_row": [...]
      }
    """
    fields, data = parse_twse_table_json(js)

    # Column names vary slightly; match by substrings
    # foreign
    idx_foreign = (
        find_col(fields, ["外陸資", "買賣超"]) or
        find_col(fields, ["外資", "買賣超"])
    )
    # investment trust
    idx_trust = find_col(fields, ["投信", "買賣超"])
    # dealer
    idx_dealer = find_col(fields, ["自營商", "買賣超"])

    # stock code usually in first column
    row = None
    for r in data:
        if not r:
            continue
        if str(r[0]).strip() == stock_no:
            row = r
            break

    out = {
        "foreign_net_shares": None,
        "trust_net_shares": None,
        "dealer_net_shares": None,
        "dq": [],
        "raw_row": row,
        "fields": fields,
        "col_idx": {"foreign": idx_foreign, "trust": idx_trust, "dealer": idx_dealer},
    }

    if row is None:
        out["dq"].append("T86_STOCK_NOT_FOUND")
        return out

    if idx_foreign is None:
        out["dq"].append("T86_FOREIGN_COL_NOT_FOUND")
    else:
        out["foreign_net_shares"] = parse_int(row[idx_foreign])

    if idx_trust is None:
        out["dq"].append("T86_TRUST_COL_NOT_FOUND")
    else:
        out["trust_net_shares"] = parse_int(row[idx_trust])

    if idx_dealer is None:
        out["dq"].append("T86_DEALER_COL_NOT_FOUND")
    else:
        out["dealer_net_shares"] = parse_int(row[idx_dealer])

    # If parsing failed silently, mark
    if idx_foreign is not None and out["foreign_net_shares"] is None:
        out["dq"].append("T86_FOREIGN_PARSE_NA")
    if idx_trust is not None and out["trust_net_shares"] is None:
        out["dq"].append("T86_TRUST_PARSE_NA")
    if idx_dealer is not None and out["dealer_net_shares"] is None:
        out["dq"].append("T86_DEALER_PARSE_NA")

    return out


def parse_twt72u_for_stock(js_or_html: Dict[str, Any] | str, stock_no: str) -> Dict[str, Any]:
    """
    TWT72U JSON usually includes a table with fields/data.
    HTML fallback: parse with pandas.read_html (if pandas available).

    We aim to extract:
      - borrowing_shares (借券賣出餘額 / 貸株残高 etc.)
      - borrowing_mv (借券賣出餘額市值 / 貸株時価総額 etc.)
    """
    out = {
        "borrow_shares": None,     # int
        "borrow_mv_ntd": None,     # float or int
        "dq": [],
        "raw_row": None,
        "fields": None,
        "col_idx": {},
    }

    # JSON path
    if isinstance(js_or_html, dict):
        try:
            fields, data = parse_twse_table_json(js_or_html)
        except Exception as e:
            out["dq"].append(f"TWT72U_JSON_TABLE_PARSE_FAIL:{e.__class__.__name__}")
            return out

        # typical first col is stock code
        row = None
        for r in data:
            if not r:
                continue
            if str(r[0]).strip() == stock_no:
                row = r
                break
        out["raw_row"] = row
        out["fields"] = fields

        if row is None:
            out["dq"].append("TWT72U_STOCK_NOT_FOUND")
            return out

        # Heuristic: find shares and market value columns by substrings
        idx_shares = (
            find_col(fields, ["借券", "餘額"]) or
            find_col(fields, ["貸株", "残高"]) or
            find_col(fields, ["借券賣出", "餘額"])
        )
        idx_mv = (
            find_col(fields, ["市值"]) or
            find_col(fields, ["時価総額"]) or
            find_col(fields, ["金額"])
        )
        out["col_idx"] = {"shares": idx_shares, "mv": idx_mv}

        if idx_shares is None:
            out["dq"].append("TWT72U_SHARES_COL_NOT_FOUND")
        else:
            out["borrow_shares"] = parse_int(row[idx_shares])
            if out["borrow_shares"] is None:
                out["dq"].append("TWT72U_SHARES_PARSE_NA")

        if idx_mv is None:
            out["dq"].append("TWT72U_MV_COL_NOT_FOUND")
        else:
            out["borrow_mv_ntd"] = parse_float(row[idx_mv])
            if out["borrow_mv_ntd"] is None:
                out["dq"].append("TWT72U_MV_PARSE_NA")

        return out

    # HTML fallback path
    html = js_or_html
    if pd is None:
        out["dq"].append("TWT72U_HTML_FALLBACK_NO_PANDAS")
        return out

    try:
        tables = pd.read_html(html)
        if not tables:
            out["dq"].append("TWT72U_HTML_NO_TABLES")
            return out
        df = tables[0]
        # find code column
        # allow either first column or '證券代號' style
        code_col = None
        for c in df.columns:
            if "代號" in str(c) or "コード" in str(c) or str(c).strip() in {"證券代號", "銘柄コード"}:
                code_col = c
                break
        if code_col is None:
            code_col = df.columns[0]

        row_df = df[df[code_col].astype(str).str.strip() == stock_no]
        if row_df.empty:
            out["dq"].append("TWT72U_HTML_STOCK_NOT_FOUND")
            return out

        r0 = row_df.iloc[0].to_dict()
        out["raw_row"] = r0

        # locate columns
        shares_key = None
        mv_key = None
        for k in r0.keys():
            ks = str(k)
            if shares_key is None and (("借券" in ks and "餘額" in ks) or ("貸株" in ks and "残高" in ks)):
                shares_key = k
            if mv_key is None and (("市值" in ks) or ("時価総額" in ks) or ("金額" in ks)):
                mv_key = k

        if shares_key is None:
            out["dq"].append("TWT72U_HTML_SHARES_COL_NOT_FOUND")
        else:
            out["borrow_shares"] = parse_int(r0.get(shares_key))

        if mv_key is None:
            out["dq"].append("TWT72U_HTML_MV_COL_NOT_FOUND")
        else:
            out["borrow_mv_ntd"] = parse_float(r0.get(mv_key))

        return out

    except Exception as e:
        out["dq"].append(f"TWT72U_HTML_PARSE_FAIL:{e.__class__.__name__}")
        return out


# ----------------------------
# Date alignment (use your existing price history if available)
# ----------------------------

def load_recent_trading_dates(cache_dir: str, last_date_ymd: str, need_n: int) -> List[str]:
    """
    Try to infer trading dates from your cached price series (preferred),
    else fall back to walking backwards by calendar days and keeping those
    that successfully return TWSE data later (not done here).

    Supported candidate files (first hit wins):
      - {cache_dir}/prices.csv
      - {cache_dir}/price.csv
      - {cache_dir}/raw_prices.csv
      - {cache_dir}/data.csv
    Expected date column: 'date' or first column.
    """
    candidates = ["prices.csv", "price.csv", "raw_prices.csv", "data.csv"]
    for fn in candidates:
        p = os.path.join(cache_dir, fn)
        if not os.path.exists(p):
            continue
        if pd is None:
            warn("pandas not available; cannot load trading dates from CSV reliably.")
            break
        try:
            df = pd.read_csv(p)
            if df.empty:
                continue
            if "date" in df.columns:
                col = "date"
            else:
                col = df.columns[0]
            dates = df[col].astype(str).str.strip().tolist()
            dates_ymd = []
            for d in dates:
                try:
                    dates_ymd.append(to_yyyymmdd(d))
                except Exception:
                    continue
            # keep up to last_date_ymd
            dates_ymd = [d for d in dates_ymd if d <= last_date_ymd]
            dates_ymd = sorted(set(dates_ymd))
            if not dates_ymd:
                continue
            tail = dates_ymd[-need_n:]
            return tail
        except Exception as e:
            warn(f"Failed reading {p}: {e}")
            continue

    # Fallback: only last_date
    return [last_date_ymd]


# ----------------------------
# Main fetch logic
# ----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True, help="cache dir that contains your price CSVs")
    ap.add_argument("--stats_path", required=True, help="path to stats_latest.json (to get last_date)")
    ap.add_argument("--out_path", required=True, help="output overlay json path")
    ap.add_argument("--window_n", type=int, default=5, help="rolling window for N-day sums")
    ap.add_argument("--stock_no", type=str, default="0050", help="TWSE stock code (0050)")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)
    args = ap.parse_args()

    dq_flags: List[str] = []
    run_ts_utc = utc_now_iso()

    stats = read_json(args.stats_path)
    # accept either last_date at top-level or nested
    last_date = stats.get("last_date") or stats.get("meta", {}).get("last_date")
    if not last_date:
        dq_flags.append("STATS_LAST_DATE_MISSING")
        warn("stats_latest.json missing last_date; fallback to today-UTC (NOT recommended).")
        last_date_ymd = datetime.now(timezone.utc).strftime("%Y%m%d")
    else:
        last_date_ymd = to_yyyymmdd(str(last_date))

    # Need window_n + 1 dates to compute N-day sums + today delta (conceptually)
    need_n = max(1, args.window_n + 1)
    dates = load_recent_trading_dates(args.cache_dir, last_date_ymd, need_n)
    if len(dates) < need_n:
        dq_flags.append(f"TRADING_DATES_INSUFFICIENT:{len(dates)}<{need_n}")

    # TWSE endpoints (templates)
    # Evidence: community list for T86 + MI_MARGN; TWT72U present on TWSE report pages.
    url_t86_tpl = "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999"
    # TWT72U selectType=SLBNLB (securities lending / borrowing balance by stock)
    url_twt72u_tpl = "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB"
    # HTML fallback for TWT72U (if JSON blocked)
    url_twt72u_html_tpl = "https://www.twse.com.tw/exchangeReport/TWT72U?response=html&date={ymd}&selectType=SLBNLB"

    per_day: List[Dict[str, Any]] = []

    for ymd in dates:
        day_obj: Dict[str, Any] = {
            "date": ymd,
            "t86": None,
            "twt72u": None,
            "dq": [],
            "sources": {},
        }

        # --- T86 ---
        url_t86 = url_t86_tpl.format(ymd=ymd)
        day_obj["sources"]["t86"] = url_t86
        fr = http_get(url_t86, timeout=args.timeout, retries=args.retries, backoff=args.backoff)
        if not fr.ok:
            day_obj["dq"].append(f"T86_FETCH_FAIL:{fr.error}")
        elif fr.json_obj is None:
            day_obj["dq"].append("T86_JSON_NOT_RETURNED")
        else:
            try:
                day_obj["t86"] = parse_t86_for_stock(fr.json_obj, args.stock_no)
            except Exception as e:
                day_obj["dq"].append(f"T86_PARSE_FAIL:{e.__class__.__name__}")

        # --- TWT72U ---
        url_twt72u = url_twt72u_tpl.format(ymd=ymd)
        day_obj["sources"]["twt72u"] = url_twt72u

        fr2 = http_get(url_twt72u, timeout=args.timeout, retries=args.retries, backoff=args.backoff)
        if not fr2.ok:
            # html fallback
            url_html = url_twt72u_html_tpl.format(ymd=ymd)
            day_obj["sources"]["twt72u_html_fallback"] = url_html
            fr2b = http_get(url_html, timeout=args.timeout, retries=args.retries, backoff=args.backoff)
            if not fr2b.ok or (fr2b.text is None):
                day_obj["dq"].append(f"TWT72U_FETCH_FAIL:{fr2.error or fr2b.error}")
            else:
                day_obj["twt72u"] = parse_twt72u_for_stock(fr2b.text, args.stock_no)
                day_obj["dq"].append("TWT72U_USED_HTML_FALLBACK")
        else:
            if fr2.json_obj is not None:
                day_obj["twt72u"] = parse_twt72u_for_stock(fr2.json_obj, args.stock_no)
            elif fr2.text is not None:
                # sometimes server returns html even with response=json
                day_obj["twt72u"] = parse_twt72u_for_stock(fr2.text, args.stock_no)
                day_obj["dq"].append("TWT72U_JSON_ENDPOINT_RETURNED_HTML")
            else:
                day_obj["dq"].append("TWT72U_EMPTY_RESPONSE")

        per_day.append(day_obj)

        # politeness delay (avoid rate limiting)
        time.sleep(0.4)

    # Compute rolling sums (last window_n days, excluding the extra day used for delta)
    # We keep "today" = last element in dates (aligned to stats last_date).
    # For sums: use last window_n elements of per_day excluding the earliest extra.
    per_day_sorted = sorted(per_day, key=lambda x: x["date"])
    # Slice for window
    window_days = per_day_sorted[-args.window_n:] if args.window_n > 0 else per_day_sorted[-1:]

    def sum_nullable(vals: List[Optional[int]]) -> Optional[int]:
        v = [x for x in vals if isinstance(x, int)]
        return sum(v) if v else None

    # Extract T86 nets
    foreign_list = []
    trust_list = []
    dealer_list = []

    for d in window_days:
        t86 = (d.get("t86") or {})
        foreign_list.append(t86.get("foreign_net_shares"))
        trust_list.append(t86.get("trust_net_shares"))
        dealer_list.append(t86.get("dealer_net_shares"))

    t86_agg = {
        "window_n": args.window_n,
        "foreign_net_shares_sum": sum_nullable(foreign_list),
        "trust_net_shares_sum": sum_nullable(trust_list),
        "dealer_net_shares_sum": sum_nullable(dealer_list),
        "days_used": [d["date"] for d in window_days],
    }

    # Extract borrow balances: use last day as level, and delta vs previous day (if available)
    borrow_last = None
    borrow_prev = None
    if len(per_day_sorted) >= 1:
        borrow_last = (per_day_sorted[-1].get("twt72u") or {})
    if len(per_day_sorted) >= 2:
        borrow_prev = (per_day_sorted[-2].get("twt72u") or {})

    def delta(a: Any, b: Any) -> Optional[float]:
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except Exception:
            return None

    borrow_summary = {
        "asof_date": per_day_sorted[-1]["date"] if per_day_sorted else last_date_ymd,
        "borrow_shares": borrow_last.get("borrow_shares") if isinstance(borrow_last, dict) else None,
        "borrow_mv_ntd": borrow_last.get("borrow_mv_ntd") if isinstance(borrow_last, dict) else None,
        "borrow_shares_chg_1d": delta(
            borrow_last.get("borrow_shares") if isinstance(borrow_last, dict) else None,
            borrow_prev.get("borrow_shares") if isinstance(borrow_prev, dict) else None,
        ),
        "borrow_mv_ntd_chg_1d": delta(
            borrow_last.get("borrow_mv_ntd") if isinstance(borrow_last, dict) else None,
            borrow_prev.get("borrow_mv_ntd") if isinstance(borrow_prev, dict) else None,
        ),
    }

    # Shares outstanding / ETF units: NA placeholder (explicit)
    units_summary = {
        "units_outstanding": None,
        "units_chg_1d": None,
        "dq": ["ETF_UNITS_ENDPOINT_NOT_IMPLEMENTED"],
    }

    out = {
        "meta": {
            "run_ts_utc": run_ts_utc,
            "script_fingerprint": SCRIPT_FINGERPRINT,
            "stock_no": args.stock_no,
            "aligned_last_date": last_date_ymd,
            "window_n": args.window_n,
            "timeout": args.timeout,
            "retries": args.retries,
            "backoff": args.backoff,
        },
        "sources": {
            "t86_tpl": url_t86_tpl,
            "twt72u_tpl": url_twt72u_tpl,
            "twt72u_html_fallback_tpl": url_twt72u_html_tpl,
        },
        "data": {
            "per_day": per_day_sorted,
            "t86_agg": t86_agg,
            "borrow_summary": borrow_summary,
            "etf_units": units_summary,
        },
        "dq": {
            "flags": sorted(set(dq_flags)),
        },
    }

    write_json(args.out_path, out)
    info(f"Wrote overlay: {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())