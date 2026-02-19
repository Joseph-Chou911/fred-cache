#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_tw0050_chip_overlay.py

Fetch 0050 chip overlay from TWSE public endpoints:
- T86 (institutional trading)
- TWT72U (securities lending / borrow balance)

Design goals:
- Audit-friendly JSON with source URLs per day.
- Robust header-based parsing (avoid hard-coded col idx).
- Consistent TWT72U: borrow_shares uses "本日借券餘額股(4)" and mv uses "(6)=(4)*(5)".
- Date alignment: use stats_latest.json last_date (price last date) as anchor when possible.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


SCRIPT_FINGERPRINT = "fetch_tw0050_chip_overlay@2026-02-19.v2"


def utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def safe_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, int):
        return x
    s = str(x).strip()
    if s in ("", "N/A", "NA", "null", "None", "--"):
        return None
    s = s.replace(",", "")
    try:
        return int(s)
    except Exception:
        return None


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (float, int)):
        return float(x)
    s = str(x).strip()
    if s in ("", "N/A", "NA", "null", "None", "--"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def load_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def extract_last_date(stats: dict) -> Optional[str]:
    """
    Return YYYYMMDD string if possible.
    Accept common patterns:
      - stats["last_date"] == "2026-02-11" or "20260211"
      - stats["meta"]["last_date"] / ["price_last_date"] etc.
    """
    candidates = []
    for k in ("last_date", "price_last_date", "aligned_last_date", "asof_date", "as_of_date"):
        if k in stats:
            candidates.append(stats.get(k))
    meta = stats.get("meta", {}) if isinstance(stats.get("meta", {}), dict) else {}
    for k in ("last_date", "price_last_date", "aligned_last_date", "asof_date", "as_of_date", "data_date"):
        if k in meta:
            candidates.append(meta.get(k))

    for v in candidates:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        # accept "YYYY-MM-DD"
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            ymd = s.replace("-", "")
            if ymd.isdigit():
                return ymd
        # accept "YYYYMMDD"
        if len(s) == 8 and s.isdigit():
            return s
    return None


def req_json(url: str, timeout: float, retries: int, backoff: float) -> Tuple[Optional[dict], List[str]]:
    dq: List[str] = []
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                dq.append(f"HTTP_{r.status_code}")
                time.sleep(backoff * (i + 1))
                continue
            j = r.json()
            return j, dq
        except Exception as e:
            dq.append(f"EXC_{type(e).__name__}")
            time.sleep(backoff * (i + 1))
    return None, dq


def find_row_by_stock(data_rows: List[List[str]], stock_no: str) -> Optional[List[str]]:
    target = stock_no.strip()
    for row in data_rows:
        if not row:
            continue
        code = str(row[0]).strip()
        if code == target:
            return row
    return None


def t86_parse(j: dict, stock_no: str) -> Tuple[Optional[dict], List[str]]:
    dq: List[str] = []
    if not isinstance(j, dict):
        return None, ["T86_BAD_JSON"]
    stat = str(j.get("stat", "")).strip()
    if stat and stat.upper() != "OK":
        return None, [f"T86_STAT_{stat}"]

    fields = j.get("fields", [])
    data = j.get("data", [])
    if not isinstance(fields, list) or not isinstance(data, list):
        return None, ["T86_SCHEMA_MISMATCH"]

    row = find_row_by_stock(data, stock_no)
    if row is None:
        return None, ["T86_ROW_NOT_FOUND"]

    # header-based indices
    def idx_of(name: str) -> Optional[int]:
        try:
            return fields.index(name)
        except ValueError:
            return None

    idx_foreign = idx_of("外陸資買賣超股數(不含外資自營商)")
    idx_trust = idx_of("投信買賣超股數")

    # Dealer net: TWSE T86 has "自營商買賣超股數" (overall) plus subcategories later.
    # Prefer the first occurrence of exactly that label.
    idx_dealer = idx_of("自營商買賣超股數")

    idx_total3 = idx_of("三大法人買賣超股數")

    missing = []
    if idx_foreign is None:
        missing.append("foreign")
    if idx_trust is None:
        missing.append("trust")
    if idx_dealer is None:
        missing.append("dealer")
    if idx_total3 is None:
        missing.append("total3")
    if missing:
        dq.append("T86_FIELDS_MISSING_" + "_".join(missing))

    foreign_net = safe_int(row[idx_foreign]) if idx_foreign is not None else None
    trust_net = safe_int(row[idx_trust]) if idx_trust is not None else None
    dealer_net = safe_int(row[idx_dealer]) if idx_dealer is not None else None
    total3_net = safe_int(row[idx_total3]) if idx_total3 is not None else None

    out = {
        "fields": fields,
        "raw_row": row,
        "col_idx": {
            "foreign": idx_foreign,
            "trust": idx_trust,
            "dealer": idx_dealer,
            "total3": idx_total3,
        },
        "foreign_net_shares": foreign_net,
        "trust_net_shares": trust_net,
        "dealer_net_shares": dealer_net,
        "total3_net_shares": total3_net,
        "dq": dq[:],
    }
    return out, dq


def twt72u_parse(j: dict, stock_no: str) -> Tuple[Optional[dict], List[str]]:
    dq: List[str] = []
    if not isinstance(j, dict):
        return None, ["TWT72U_BAD_JSON"]
    stat = str(j.get("stat", "")).strip()
    if stat and stat.upper() != "OK":
        return None, [f"TWT72U_STAT_{stat}"]

    fields = j.get("fields", [])
    data = j.get("data", [])
    if not isinstance(fields, list) or not isinstance(data, list):
        return None, ["TWT72U_SCHEMA_MISMATCH"]

    row = find_row_by_stock(data, stock_no)
    if row is None:
        return None, ["TWT72U_ROW_NOT_FOUND"]

    def idx_of(name: str) -> Optional[int]:
        try:
            return fields.index(name)
        except ValueError:
            return None

    # Use END-OF-DAY borrow balance (4) and mv(6)
    idx_shares_end = idx_of("本日借券餘額股(4)=(1)+(2)-(3)")
    idx_close = idx_of("本日收盤價(5)單位：元")
    idx_mv = idx_of("借券餘額市值單位：元(6)=(4)*(5)")

    missing = []
    if idx_shares_end is None:
        missing.append("shares_end")
    if idx_mv is None:
        missing.append("mv")
    if idx_close is None:
        missing.append("close")
    if missing:
        dq.append("TWT72U_FIELDS_MISSING_" + "_".join(missing))

    shares_end = safe_int(row[idx_shares_end]) if idx_shares_end is not None else None
    mv = safe_float(row[idx_mv]) if idx_mv is not None else None
    close = safe_float(row[idx_close]) if idx_close is not None else None

    out = {
        "fields": fields,
        "raw_row": row,
        "col_idx": {"shares_end": idx_shares_end, "mv": idx_mv, "close": idx_close},
        "borrow_shares": shares_end,
        "borrow_mv_ntd": mv,
        "close": close,
        "dq": dq[:],
    }
    return out, dq


def ymd_to_date(ymd: str) -> dt.date:
    return dt.date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))


def date_to_ymd(d: dt.date) -> str:
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock_no", required=True, help="e.g. 0050")
    ap.add_argument("--stats_path", default="tw0050_bb_cache/stats_latest.json")
    ap.add_argument("--out", default="tw0050_bb_cache/chip_overlay.json")
    ap.add_argument("--window_n", type=int, default=5)
    ap.add_argument("--max_back_days", type=int, default=45)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)
    args = ap.parse_args()

    dq_flags: List[str] = []

    stats = load_json(args.stats_path)
    anchor_ymd = extract_last_date(stats or {}) if stats else None
    if anchor_ymd is None:
        dq_flags.append("PRICE_LAST_DATE_MISSING")
        # fallback to "yesterday" UTC (audit: still mark dq)
        anchor_ymd = date_to_ymd(dt.datetime.utcnow().date() - dt.timedelta(days=1))

    anchor_date = ymd_to_date(anchor_ymd)

    t86_tpl = "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999"
    twt72u_tpl = "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB"

    per_day: List[dict] = []
    got_days = 0

    # Scan backward calendar days until we collect window_n trading days with at least one dataset.
    for k in range(args.max_back_days):
        d = anchor_date - dt.timedelta(days=k)
        ymd = date_to_ymd(d)

        day_dq: List[str] = []
        sources = {"t86": t86_tpl.format(ymd=ymd), "twt72u": twt72u_tpl.format(ymd=ymd)}

        t86_j, t86_req_dq = req_json(sources["t86"], args.timeout, args.retries, args.backoff)
        twt_j, twt_req_dq = req_json(sources["twt72u"], args.timeout, args.retries, args.backoff)

        day_dq.extend([f"T86_{x}" for x in t86_req_dq])
        day_dq.extend([f"TWT72U_{x}" for x in twt_req_dq])

        t86_obj, t86_parse_dq = (None, [])
        if t86_j is not None:
            t86_obj, t86_parse_dq = t86_parse(t86_j, args.stock_no)
        else:
            day_dq.append("T86_FETCH_FAILED")

        twt_obj, twt_parse_dq = (None, [])
        if twt_j is not None:
            twt_obj, twt_parse_dq = twt72u_parse(twt_j, args.stock_no)
        else:
            day_dq.append("TWT72U_FETCH_FAILED")

        # Skip non-trading days (both missing rows)
        if (t86_obj is None) and (twt_obj is None):
            continue

        entry: Dict[str, Any] = {
            "date": ymd,
            "dq": sorted(set(day_dq + t86_parse_dq + twt_parse_dq)),
            "sources": sources,
        }
        if t86_obj is not None:
            entry["t86"] = t86_obj
        if twt_obj is not None:
            entry["twt72u"] = twt_obj

        per_day.append(entry)
        got_days += 1
        if got_days >= (args.window_n + 1):
            break

    per_day.sort(key=lambda x: x["date"])

    # Aggregate T86 over last window_n available days
    t86_days = [x for x in per_day if "t86" in x]
    t86_tail = t86_days[-args.window_n:] if len(t86_days) >= 1 else []
    t86_used_dates = [x["date"] for x in t86_tail]

    def sum_field(key: str) -> Optional[int]:
        vals = []
        for x in t86_tail:
            v = x["t86"].get(key)
            if isinstance(v, int):
                vals.append(v)
        return sum(vals) if vals else None

    t86_agg = {
        "window_n": args.window_n,
        "days_used": t86_used_dates,
        "foreign_net_shares_sum": sum_field("foreign_net_shares"),
        "trust_net_shares_sum": sum_field("trust_net_shares"),
        "dealer_net_shares_sum": sum_field("dealer_net_shares"),
        "total3_net_shares_sum": sum_field("total3_net_shares"),
    }

    # Borrow summary from last two days with twt72u
    twt_days = [x for x in per_day if "twt72u" in x]
    borrow_summary = {
        "asof_date": None,
        "borrow_shares": None,
        "borrow_shares_chg_1d": None,
        "borrow_mv_ntd": None,
        "borrow_mv_ntd_chg_1d": None,
    }

    if twt_days:
        last = twt_days[-1]
        borrow_summary["asof_date"] = last["date"]
        borrow_summary["borrow_shares"] = last["twt72u"].get("borrow_shares")
        borrow_summary["borrow_mv_ntd"] = last["twt72u"].get("borrow_mv_ntd")

        if len(twt_days) >= 2:
            prev = twt_days[-2]
            s0 = prev["twt72u"].get("borrow_shares")
            s1 = last["twt72u"].get("borrow_shares")
            mv0 = prev["twt72u"].get("borrow_mv_ntd")
            mv1 = last["twt72u"].get("borrow_mv_ntd")
            if isinstance(s0, int) and isinstance(s1, int):
                borrow_summary["borrow_shares_chg_1d"] = s1 - s0
            else:
                dq_flags.append("BORROW_SHARES_CHG_1D_NA")
            if isinstance(mv0, (int, float)) and isinstance(mv1, (int, float)):
                borrow_summary["borrow_mv_ntd_chg_1d"] = float(mv1) - float(mv0)
            else:
                dq_flags.append("BORROW_MV_CHG_1D_NA")
        else:
            dq_flags.append("BORROW_CHG_1D_INSUFFICIENT")
    else:
        dq_flags.append("BORROW_DATA_EMPTY")

    out = {
        "meta": {
            "run_ts_utc": utc_now_iso(),
            "script_fingerprint": SCRIPT_FINGERPRINT,
            "stock_no": args.stock_no,
            "window_n": args.window_n,
            "timeout": args.timeout,
            "retries": args.retries,
            "backoff": args.backoff,
            "aligned_last_date": anchor_ymd,
        },
        "sources": {
            "t86_tpl": t86_tpl,
            "twt72u_tpl": twt72u_tpl,
        },
        "dq": {"flags": sorted(set(dq_flags))},
        "data": {
            "borrow_summary": borrow_summary,
            "t86_agg": t86_agg,
            "per_day": per_day,
            "etf_units": {
                "dq": ["ETF_UNITS_ENDPOINT_NOT_IMPLEMENTED"],
                "units_outstanding": None,
                "units_chg_1d": None,
            },
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"OK wrote: {args.out}")
    print("days_collected:", len(per_day), "t86_days:", len(t86_days), "twt72u_days:", len(twt_days))
    if out["dq"]["flags"]:
        print("DQ flags:", out["dq"]["flags"])


if __name__ == "__main__":
    main()