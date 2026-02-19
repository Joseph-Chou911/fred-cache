#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_tw0050_chip_overlay.py

Purpose:
- Fetch TWSE T86 (institutional net buy/sell) + TWT72U (securities lending) for an ETF (default: 0050)
- Fetch Yuanta ETF PCF page for units outstanding / net change / trade date / posting date
- Align "last date" using stats_latest.json (stats_path), then walk backward by calendar days
  until collecting N trading days (window_n). Non-trading days are included with dq flags.

Design principles:
- Audit-friendly JSON output: include sources URLs, raw rows, field names, derived indices
- Deterministic: no randomness; retry/backoff is deterministic
- Fail-soft on partial data: output dq flags rather than crashing
"""

import argparse
import datetime as dt
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


TZ_TAIPEI = dt.timezone(dt.timedelta(hours=8))


def utc_now_iso_ms() -> str:
    # 2026-02-19T10:10:27.097Z
    now = dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def ymd(d: dt.date) -> str:
    return d.strftime("%Y%m%d")


def parse_int_maybe(s: Any) -> Optional[int]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    if not isinstance(s, str):
        return None
    t = s.strip().replace(",", "")
    if t == "" or t.upper() == "N/A":
        return None
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    return None


def parse_float_maybe(s: Any) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        return None
    t = s.strip().replace(",", "")
    if t == "" or t.upper() == "N/A":
        return None
    try:
        return float(t)
    except Exception:
        return None


def read_aligned_last_date_from_stats(stats_path: str) -> Optional[str]:
    """
    Try best-effort extraction of a local trading date from stats_latest.json.
    Returns YYYYMMDD or None.
    """
    if not stats_path or not os.path.exists(stats_path):
        return None
    try:
        j = json.load(open(stats_path, "r", encoding="utf-8"))
    except Exception:
        return None

    # common patterns
    candidates = []

    # 1) meta.day_key_local = "2026-02-11"
    meta = j.get("meta", {}) if isinstance(j, dict) else {}
    if isinstance(meta, dict):
        v = meta.get("day_key_local")
        if isinstance(v, str):
            candidates.append(v)

        v = meta.get("stats_as_of_ts")
        if isinstance(v, str):
            candidates.append(v)

        v = meta.get("as_of_ts")
        if isinstance(v, str):
            candidates.append(v)

    # 2) root.day_key_local
    v = j.get("day_key_local") if isinstance(j, dict) else None
    if isinstance(v, str):
        candidates.append(v)

    # normalize
    for c in candidates:
        c = c.strip()
        # ISO timestamp
        if re.match(r"^\d{4}-\d{2}-\d{2}T", c):
            try:
                t = dt.datetime.fromisoformat(c.replace("Z", "+00:00"))
                t_local = t.astimezone(TZ_TAIPEI)
                return ymd(t_local.date())
            except Exception:
                pass
        # date only "YYYY-MM-DD"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c):
            try:
                d = dt.date.fromisoformat(c)
                return ymd(d)
            except Exception:
                pass
        # already yyyymmdd
        if re.fullmatch(r"\d{8}", c):
            return c

    return None


def http_get_json(session: requests.Session, url: str, timeout: float, retries: int, backoff: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    last_err = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json(), None
        except Exception as e:
            last_err = str(e)
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
    return None, last_err


def http_get_text(session: requests.Session, url: str, timeout: float, retries: int, backoff: float) -> Tuple[Optional[str], Optional[str]]:
    last_err = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text, None
        except Exception as e:
            last_err = str(e)
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
    return None, last_err


def find_row_by_stock_no(data_rows: List[List[str]], stock_no: str) -> Optional[List[str]]:
    for row in data_rows:
        if not row:
            continue
        if str(row[0]).strip() == stock_no:
            return row
    return None


def t86_fetch_one(session: requests.Session, stock_no: str, date_ymd: str, timeout: float, retries: int, backoff: float) -> Dict[str, Any]:
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_ymd}&selectType=ALLBUT0999"
    out: Dict[str, Any] = {
        "dq": [],
        "fields": [],
        "raw_row": None,
        "col_idx": {},
    }
    j, err = http_get_json(session, url, timeout, retries, backoff)
    if j is None:
        out["dq"].append("T86_FETCH_FAILED")
        out["fetch_error"] = err
        return out

    fields = j.get("fields", [])
    data = j.get("data", [])
    if not fields or not data:
        out["dq"].append("T86_EMPTY")
        return out

    row = find_row_by_stock_no(data, stock_no)
    if row is None:
        out["dq"].append("T86_ROW_NOT_FOUND")
        out["fields"] = fields
        return out

    out["fields"] = fields
    out["raw_row"] = row

    # locate indices by exact field names (robust against column order shifts)
    def idx_of(name: str) -> Optional[int]:
        try:
            return fields.index(name)
        except Exception:
            return None

    idx_foreign = idx_of("外陸資買賣超股數(不含外資自營商)")
    idx_trust = idx_of("投信買賣超股數")
    idx_dealer = idx_of("自營商買賣超股數")
    idx_total3 = idx_of("三大法人買賣超股數")

    # fallback to known positions if fields are non-standard
    # (your current output uses 4,10,11,18)
    if idx_foreign is None and len(fields) > 4:
        idx_foreign = 4
    if idx_trust is None and len(fields) > 10:
        idx_trust = 10
    if idx_dealer is None and len(fields) > 11:
        idx_dealer = 11
    if idx_total3 is None and len(fields) > 18:
        idx_total3 = 18

    out["col_idx"] = {
        "foreign": idx_foreign if idx_foreign is not None else -1,
        "trust": idx_trust if idx_trust is not None else -1,
        "dealer": idx_dealer if idx_dealer is not None else -1,
        "total3": idx_total3 if idx_total3 is not None else -1,
    }

    def get_int(idx: Optional[int]) -> Optional[int]:
        if idx is None or idx < 0:
            return None
        if idx >= len(row):
            return None
        return parse_int_maybe(row[idx])

    foreign = get_int(idx_foreign)
    trust = get_int(idx_trust)
    dealer = get_int(idx_dealer)
    total3 = get_int(idx_total3)

    if foreign is None:
        out["dq"].append("T86_FOREIGN_NET_MISSING")
    if trust is None:
        out["dq"].append("T86_TRUST_NET_MISSING")
    if dealer is None:
        out["dq"].append("T86_DEALER_NET_MISSING")
    if total3 is None:
        out["dq"].append("T86_TOTAL3_NET_MISSING")

    out["foreign_net_shares"] = foreign
    out["trust_net_shares"] = trust
    out["dealer_net_shares"] = dealer
    out["total3_net_shares"] = total3
    return out


def twt72u_fetch_one(session: requests.Session, stock_no: str, date_ymd: str, timeout: float, retries: int, backoff: float) -> Dict[str, Any]:
    url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={date_ymd}&selectType=SLBNLB"
    out: Dict[str, Any] = {
        "dq": [],
        "fields": [],
        "raw_row": None,
        "col_idx": {},
    }
    j, err = http_get_json(session, url, timeout, retries, backoff)
    if j is None:
        out["dq"].append("TWT72U_FETCH_FAILED")
        out["fetch_error"] = err
        return out

    fields = j.get("fields", [])
    data = j.get("data", [])
    if not fields or not data:
        out["dq"].append("TWT72U_EMPTY")
        return out

    row = find_row_by_stock_no(data, stock_no)
    if row is None:
        out["dq"].append("TWT72U_ROW_NOT_FOUND")
        out["fields"] = fields
        return out

    out["fields"] = fields
    out["raw_row"] = row

    def idx_of(name: str) -> Optional[int]:
        try:
            return fields.index(name)
        except Exception:
            return None

    idx_shares_end = idx_of("本日借券餘額股(4)=(1)+(2)-(3)")
    idx_close = idx_of("本日收盤價(5)單位：元")
    idx_mv = idx_of("借券餘額市值單位：元(6)=(4)*(5)")

    # fallback (your output uses 5,6,7)
    if idx_shares_end is None and len(fields) > 5:
        idx_shares_end = 5
    if idx_close is None and len(fields) > 6:
        idx_close = 6
    if idx_mv is None and len(fields) > 7:
        idx_mv = 7

    out["col_idx"] = {
        "shares_end": idx_shares_end if idx_shares_end is not None else -1,
        "close": idx_close if idx_close is not None else -1,
        "mv": idx_mv if idx_mv is not None else -1,
    }

    def get_int(idx: Optional[int]) -> Optional[int]:
        if idx is None or idx < 0:
            return None
        if idx >= len(row):
            return None
        return parse_int_maybe(row[idx])

    def get_float(idx: Optional[int]) -> Optional[float]:
        if idx is None or idx < 0:
            return None
        if idx >= len(row):
            return None
        return parse_float_maybe(row[idx])

    shares_end = get_int(idx_shares_end)
    close = get_float(idx_close)
    mv = get_int(idx_mv)

    if shares_end is None:
        out["dq"].append("TWT72U_SHARES_END_MISSING")
    if close is None:
        out["dq"].append("TWT72U_CLOSE_MISSING")
    if mv is None:
        out["dq"].append("TWT72U_MV_MISSING")

    out["borrow_shares"] = shares_end
    out["close"] = close
    out["borrow_mv_ntd"] = float(mv) if mv is not None else None
    return out


def parse_yuanta_pcf(html: str) -> Dict[str, Any]:
    """
    Best-effort parse of Yuanta PCF page.
    Targets:
      - Trade Date
      - Posting Date (timestamp)
      - Total Outstanding Shares
      - Net Change in Outstanding Shares

    Returns dict with 'trade_date', 'posting_dt', 'units_outstanding', 'units_chg_1d', and dq list.
    """
    dq: List[str] = []
    out: Dict[str, Any] = {
        "trade_date": None,
        "posting_dt": None,
        "units_outstanding": None,
        "units_chg_1d": None,
        "dq": dq,
    }

    # normalize whitespace for regex
    txt = re.sub(r"\s+", " ", html)

    # Multiple language patterns (English / Chinese)
    trade_patterns = [
        r"Trade Date[^0-9]*(\d{4}/\d{2}/\d{2})",
        r"交易日期[^0-9]*(\d{4}/\d{2}/\d{2})",
    ]
    posting_patterns = [
        r"Posting Date[^0-9]*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
        r"公告時間[^0-9]*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
        r"Posting Date[^0-9]*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})",
    ]
    outstanding_patterns = [
        r"Total Outstanding Shares[^0-9]*([0-9][0-9,]+)",
        r"Outstanding Shares[^0-9]*([0-9][0-9,]+)",
        r"流通受益權單位數[^0-9]*([0-9][0-9,]+)",
    ]
    netchg_patterns = [
        r"Net Change in Outstanding Shares[^0-9\-]*(-?[0-9][0-9,]+)",
        r"Net Change[^0-9\-]*(-?[0-9][0-9,]+)",
        r"受益權單位淨變動[^0-9\-]*(-?[0-9][0-9,]+)",
    ]

    def first_match(patterns: List[str]) -> Optional[str]:
        for p in patterns:
            m = re.search(p, txt, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    trade_date = first_match(trade_patterns)
    posting_dt = first_match(posting_patterns)
    outstanding = first_match(outstanding_patterns)
    netchg = first_match(netchg_patterns)

    if trade_date is None:
        dq.append("ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND")
    else:
        out["trade_date"] = trade_date

    if posting_dt is None:
        dq.append("ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND")
    else:
        # normalize posting date to "YYYY-MM-DD HH:MM:SS" if it uses slashes
        posting_dt_norm = posting_dt.replace("/", "-")
        out["posting_dt"] = posting_dt_norm

    units_out = parse_int_maybe(outstanding) if outstanding is not None else None
    if units_out is None:
        dq.append("ETF_UNITS_PCF_OUTSTANDING_NOT_FOUND")
    else:
        out["units_outstanding"] = units_out

    units_chg = parse_int_maybe(netchg) if netchg is not None else None
    if units_chg is None:
        dq.append("ETF_UNITS_PCF_NET_CHANGE_NOT_FOUND")
    else:
        out["units_chg_1d"] = units_chg

    if out["units_outstanding"] is None and out["units_chg_1d"] is None:
        dq.append("ETF_UNITS_PCF_PARSE_ALL_MISSING")

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock_no", required=True, help="e.g. 0050")
    ap.add_argument("--stats_path", default=None, help="path to stats_latest.json to align last date")
    ap.add_argument("--cache_dir", default=None, help="cache directory (optional if --out is provided)")
    ap.add_argument("--out", default=None, help="output json path (recommended)")
    ap.add_argument("--window_n", type=int, default=5, help="number of trading days to aggregate")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)
    args = ap.parse_args()

    if not args.out and not args.cache_dir:
        raise SystemExit("ERROR: must provide either --out or --cache_dir")

    out_path = args.out
    if not out_path:
        out_path = os.path.join(args.cache_dir, "chip_overlay.json")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    aligned = read_aligned_last_date_from_stats(args.stats_path) if args.stats_path else None
    if aligned is None:
        # fallback: today local
        aligned = ymd(dt.datetime.now(TZ_TAIPEI).date())

    aligned_date = dt.datetime.strptime(aligned, "%Y%m%d").date()

    session = requests.Session()
    # TWSE sometimes behaves better with a UA
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; tw0050-bot/1.0; +https://github.com/)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    })

    per_day: List[Dict[str, Any]] = []
    used_days: List[str] = []

    cursor = aligned_date
    # walk backward by calendar day until we got window_n trading days
    while len(used_days) < args.window_n:
        d_ymd = ymd(cursor)
        item: Dict[str, Any] = {
            "date": d_ymd,
            "dq": [],
            "sources": {
                "t86": f"https://www.twse.com.tw/fund/T86?response=json&date={d_ymd}&selectType=ALLBUT0999",
                "twt72u": f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={d_ymd}&selectType=SLBNLB",
            },
        }

        t86 = t86_fetch_one(session, args.stock_no, d_ymd, args.timeout, args.retries, args.backoff)
        twt72u = twt72u_fetch_one(session, args.stock_no, d_ymd, args.timeout, args.retries, args.backoff)
        item["t86"] = t86
        item["twt72u"] = twt72u

        # trading day iff both endpoints have row data (not EMPTY / not ROW_NOT_FOUND)
        is_trading = ("T86_EMPTY" not in t86.get("dq", [])) and ("TWT72U_EMPTY" not in twt72u.get("dq", [])) \
                     and ("T86_ROW_NOT_FOUND" not in t86.get("dq", [])) and ("TWT72U_ROW_NOT_FOUND" not in twt72u.get("dq", []))

        if not is_trading:
            item["dq"].append("NON_TRADING_OR_NO_DATA")
        else:
            used_days.append(d_ymd)

        per_day.append(item)
        cursor = cursor - dt.timedelta(days=1)

        # safety stop to avoid infinite loops (should never hit in practice)
        if len(per_day) > 40:
            break

    # aggregate sums over used days
    foreign_sum = 0
    trust_sum = 0
    dealer_sum = 0
    total3_sum = 0
    used_count = 0

    # borrow summary based on last (most recent) used day and prior used day
    borrow_summary: Dict[str, Any] = {
        "asof_date": None,
        "borrow_shares": None,
        "borrow_shares_chg_1d": None,
        "borrow_mv_ntd": None,
        "borrow_mv_ntd_chg_1d": None,
    }

    # build a map date -> (t86,twt72u) for used days
    used_map: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    for it in per_day:
        d = it["date"]
        if d in used_days:
            used_map[d] = (it["t86"], it["twt72u"])

    # used_days currently in descending order? (because we start from aligned_date backward)
    # yes: first is aligned date if trading day, then earlier dates...
    for d in used_days:
        t86, _ = used_map[d]
        f = t86.get("foreign_net_shares")
        t = t86.get("trust_net_shares")
        dl = t86.get("dealer_net_shares")
        tot = t86.get("total3_net_shares")
        if isinstance(f, int):
            foreign_sum += f
        if isinstance(t, int):
            trust_sum += t
        if isinstance(dl, int):
            dealer_sum += dl
        if isinstance(tot, int):
            total3_sum += tot
        used_count += 1

    # borrow summary
    if used_days:
        d0 = used_days[0]  # most recent used day
        _, tw0 = used_map[d0]
        borrow_summary["asof_date"] = d0
        borrow_summary["borrow_shares"] = tw0.get("borrow_shares")
        borrow_summary["borrow_mv_ntd"] = tw0.get("borrow_mv_ntd")

        if len(used_days) >= 2:
            d1 = used_days[1]
            _, tw1 = used_map[d1]
            s0 = tw0.get("borrow_shares")
            s1 = tw1.get("borrow_shares")
            mv0 = tw0.get("borrow_mv_ntd")
            mv1 = tw1.get("borrow_mv_ntd")
            if isinstance(s0, int) and isinstance(s1, int):
                borrow_summary["borrow_shares_chg_1d"] = s0 - s1
            if isinstance(mv0, (int, float)) and isinstance(mv1, (int, float)):
                borrow_summary["borrow_mv_ntd_chg_1d"] = float(mv0) - float(mv1)

    t86_agg = {
        "window_n": args.window_n,
        "days_used": list(reversed(sorted(used_days))),  # ascending for readability (YYYYMMDD)
        "foreign_net_shares_sum": foreign_sum,
        "trust_net_shares_sum": trust_sum,
        "dealer_net_shares_sum": dealer_sum,
        "total3_net_shares_sum": total3_sum,
    }

    # PCF parse
    pcf_url = f"https://www.yuantaetfs.com/tradeInfo/pcf/{args.stock_no}"
    pcf_html, pcf_err = http_get_text(session, pcf_url, args.timeout, args.retries, args.backoff)
    etf_units = {
        "source": "yuanta_pcf",
        "source_url": pcf_url,
        "trade_date": None,
        "posting_dt": None,
        "units_outstanding": None,
        "units_chg_1d": None,
        "dq": [],
    }
    dq_flags: List[str] = []

    if pcf_html is None:
        etf_units["dq"].append("ETF_UNITS_FETCH_FAILED")
        etf_units["fetch_error"] = pcf_err
        dq_flags.append("ETF_UNITS_FETCH_FAILED")
    else:
        parsed = parse_yuanta_pcf(pcf_html)
        etf_units["trade_date"] = parsed["trade_date"]
        etf_units["posting_dt"] = parsed["posting_dt"]
        etf_units["units_outstanding"] = parsed["units_outstanding"]
        etf_units["units_chg_1d"] = parsed["units_chg_1d"]
        etf_units["dq"] = parsed["dq"]
        # global flag if critical missing
        if (etf_units["units_outstanding"] is None) or (etf_units["units_chg_1d"] is None):
            dq_flags.append("ETF_UNITS_FETCH_FAILED")

    # derived metrics (safe, optional)
    derived: Dict[str, Any] = {}
    try:
        u0 = etf_units.get("units_outstanding")
        du = etf_units.get("units_chg_1d")
        bs = borrow_summary.get("borrow_shares")
        if isinstance(u0, int) and u0 > 0 and isinstance(bs, int):
            derived["borrow_ratio"] = bs / u0  # fraction
        if isinstance(u0, int) and isinstance(du, int):
            u_prev = u0 - du
            if u_prev > 0 and isinstance(borrow_summary.get("borrow_shares"), int) and isinstance(borrow_summary.get("borrow_shares_chg_1d"), int):
                bs0 = borrow_summary["borrow_shares"]
                # infer prev borrow shares
                bs_prev = bs0 - borrow_summary["borrow_shares_chg_1d"]
                derived["borrow_ratio_prev"] = bs_prev / u_prev if u_prev > 0 else None
                if derived.get("borrow_ratio") is not None and derived.get("borrow_ratio_prev") is not None:
                    derived["borrow_ratio_chg_pp"] = (derived["borrow_ratio"] - derived["borrow_ratio_prev"]) * 100.0
            if u_prev > 0:
                derived["units_chg_pct_1d"] = du / u_prev
    except Exception:
        # do not fail
        pass

    out = {
        "meta": {
            "run_ts_utc": utc_now_iso_ms(),
            "script_fingerprint": "fetch_tw0050_chip_overlay@2026-02-19.v7",
            "stock_no": args.stock_no,
            "window_n": args.window_n,
            "timeout": args.timeout,
            "retries": args.retries,
            "backoff": args.backoff,
            "aligned_last_date": aligned,
        },
        "sources": {
            "t86_tpl": "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999",
            "twt72u_tpl": "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB",
            "pcf_url": pcf_url,
        },
        "dq": {
            "flags": dq_flags,
        },
        "data": {
            "borrow_summary": borrow_summary,
            "etf_units": etf_units,
            "per_day": per_day,
            "t86_agg": t86_agg,
            "derived": derived,
        },
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK: wrote {out_path}")
    if dq_flags:
        print("DQ flags:", dq_flags)


if __name__ == "__main__":
    main()