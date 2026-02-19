#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# ===== Audit stamp (use this to prove which script generated the artifact) =====
BUILD_SCRIPT_FINGERPRINT = "fetch_tw0050_chip_overlay@2026-02-19.v5"

TWSE_T86_TPL = "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999"
TWSE_TWT72U_TPL = "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB"

# Yuanta PCF page (contains: Posting Date, Trade Date, Total Outstanding Shares, Net Change)
YUANTA_PCF_URL_TPL = "https://www.yuantaetfs.com/tradeInfo/pcf/{stock_no}"


def utc_now_iso_millis() -> str:
    # e.g. 2026-02-19T09:34:46.855Z
    dt = datetime.now(timezone.utc)
    ms = int(dt.microsecond / 1000)
    dt2 = dt.replace(microsecond=0)
    return dt2.isoformat().replace("+00:00", "Z").replace("Z", f".{ms:03d}Z")


def safe_get(d: Any, k: str, default=None):
    try:
        if isinstance(d, dict):
            return d.get(k, default)
        return default
    except Exception:
        return default


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def parse_iso_ymd(s: str) -> Optional[date]:
    """
    Accept:
      - YYYY-MM-DD
      - YYYY/MM/DD
      - YYYYMMDD
    """
    if not s:
        return None
    s = str(s).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.strptime(s, "%Y-%m-%d").date()
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", s):
            return datetime.strptime(s, "%Y/%m/%d").date()
        if re.fullmatch(r"\d{8}", s):
            return datetime.strptime(s, "%Y%m%d").date()
    except Exception:
        return None
    return None


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _strip_num(s: Any) -> Optional[float]:
    if s is None:
        return None
    try:
        t = str(s).strip()
        if t == "" or t in {"-", "N/A", "NA", "None"}:
            return None
        t = t.replace(",", "")
        return float(t)
    except Exception:
        return None


def _strip_int(s: Any) -> Optional[int]:
    v = _strip_num(s)
    if v is None:
        return None
    try:
        return int(round(v))
    except Exception:
        return None


@dataclass
class FetchCfg:
    timeout: float = 15.0
    retries: int = 3
    backoff: float = 1.5


def http_get_text(url: str, cfg: FetchCfg) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (text, err)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; chip_overlay_bot/1.0; +https://github.com/)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
        "Connection": "close",
    }
    last_err = None
    for i in range(max(1, cfg.retries)):
        try:
            r = requests.get(url, headers=headers, timeout=cfg.timeout)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text, None
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if i < cfg.retries - 1:
                time.sleep(cfg.backoff * (2**i))
    return None, last_err


def http_get_json(url: str, cfg: FetchCfg) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Returns (json, err)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; chip_overlay_bot/1.0; +https://github.com/)",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
        "Connection": "close",
    }
    last_err = None
    for i in range(max(1, cfg.retries)):
        try:
            r = requests.get(url, headers=headers, timeout=cfg.timeout)
            r.raise_for_status()
            return r.json(), None
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if i < cfg.retries - 1:
                time.sleep(cfg.backoff * (2**i))
    return None, last_err


def _find_field_idx(fields: List[str], predicates: List[str]) -> Optional[int]:
    """
    Find first field index that contains ALL keywords in predicates.
    """
    if not fields:
        return None
    for i, f in enumerate(fields):
        ff = str(f)
        ok = True
        for kw in predicates:
            if kw not in ff:
                ok = False
                break
        if ok:
            return i
    return None


def _pick_row_by_stock(data_rows: List[List[Any]], stock_no: str) -> Optional[List[Any]]:
    """
    TWSE responses usually return rows as list[list[str]].
    We pick row where col0 == stock_no after strip.
    """
    if not isinstance(data_rows, list):
        return None
    for row in data_rows:
        try:
            if not isinstance(row, list) or len(row) == 0:
                continue
            if str(row[0]).strip() == str(stock_no).strip():
                return row
        except Exception:
            continue
    return None


def fetch_t86_one_day(stock_no: str, ymd_str: str, cfg: FetchCfg) -> Dict[str, Any]:
    url = TWSE_T86_TPL.format(ymd=ymd_str)
    out: Dict[str, Any] = {"dq": [], "fields": [], "raw_row": None, "col_idx": {}}
    j, err = http_get_json(url, cfg)
    if j is None:
        out["dq"].append("T86_FETCH_FAILED")
        out["dq"].append(f"T86_ERR:{err}")
        return out

    fields = safe_get(j, "fields", []) or []
    data_rows = safe_get(j, "data", []) or []
    out["fields"] = fields

    row = _pick_row_by_stock(data_rows, stock_no)
    if not row:
        out["dq"].append("T86_EMPTY")
        return out

    out["raw_row"] = row

    # robust index lookup by field names
    idx_foreign = _find_field_idx(fields, ["外陸資買賣超股數"])
    idx_trust = _find_field_idx(fields, ["投信買賣超股數"])
    # "自營商買賣超股數" (aggregate) exists and is what we want as dealer net
    idx_dealer = _find_field_idx(fields, ["自營商買賣超股數"])
    idx_total3 = _find_field_idx(fields, ["三大法人買賣超股數"])

    # fallback (older fixed layout)
    if idx_foreign is None:
        idx_foreign = 4
    if idx_trust is None:
        idx_trust = 10
    if idx_dealer is None:
        idx_dealer = 11
    if idx_total3 is None:
        idx_total3 = 18

    out["col_idx"] = {"foreign": idx_foreign, "trust": idx_trust, "dealer": idx_dealer, "total3": idx_total3}

    def at(i: int) -> Optional[int]:
        try:
            if i < 0 or i >= len(row):
                return None
            return _strip_int(row[i])
        except Exception:
            return None

    out["foreign_net_shares"] = at(idx_foreign) if idx_foreign is not None else None
    out["trust_net_shares"] = at(idx_trust) if idx_trust is not None else None
    out["dealer_net_shares"] = at(idx_dealer) if idx_dealer is not None else None
    out["total3_net_shares"] = at(idx_total3) if idx_total3 is not None else None
    return out


def fetch_twt72u_one_day(stock_no: str, ymd_str: str, cfg: FetchCfg) -> Dict[str, Any]:
    url = TWSE_TWT72U_TPL.format(ymd=ymd_str)
    out: Dict[str, Any] = {"dq": [], "fields": [], "raw_row": None, "col_idx": {}}
    j, err = http_get_json(url, cfg)
    if j is None:
        out["dq"].append("TWT72U_FETCH_FAILED")
        out["dq"].append(f"TWT72U_ERR:{err}")
        return out

    fields = safe_get(j, "fields", []) or []
    data_rows = safe_get(j, "data", []) or []
    out["fields"] = fields

    row = _pick_row_by_stock(data_rows, stock_no)
    if not row:
        out["dq"].append("TWT72U_EMPTY")
        return out

    out["raw_row"] = row

    # Robust index lookup by field names
    idx_shares_end = _find_field_idx(fields, ["本日借券餘額股"])
    idx_close = _find_field_idx(fields, ["本日收盤價"])
    idx_mv = _find_field_idx(fields, ["借券餘額市值"])

    # fallback fixed layout
    if idx_shares_end is None:
        idx_shares_end = 5
    if idx_close is None:
        idx_close = 6
    if idx_mv is None:
        idx_mv = 7

    out["col_idx"] = {"shares_end": idx_shares_end, "close": idx_close, "mv": idx_mv}

    def at_int(i: int) -> Optional[int]:
        try:
            if i < 0 or i >= len(row):
                return None
            return _strip_int(row[i])
        except Exception:
            return None

    def at_float(i: int) -> Optional[float]:
        try:
            if i < 0 or i >= len(row):
                return None
            return _strip_num(row[i])
        except Exception:
            return None

    out["borrow_shares"] = at_int(idx_shares_end) if idx_shares_end is not None else None
    out["close"] = at_float(idx_close) if idx_close is not None else None
    # mv might be big int
    mv = None
    if idx_mv is not None and idx_mv < len(row):
        try:
            mv = _strip_num(row[idx_mv])
        except Exception:
            mv = None
    out["borrow_mv_ntd"] = mv
    return out


def parse_yuanta_pcf_units(html: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse units from Yuanta PCF page.
    Expect fields exist (English headings):
      - Posting Date：YYYY-MM-DD HH:MM:SS
      - Trade Date: YYYY/MM/DD
      - Total Outstanding Shares -> number with commas
      - Net Change in Outstanding Shares -> number with commas
    Returns (etf_units_dict, dq_list)
    """
    dq: List[str] = []
    etf: Dict[str, Any] = {
        "source": "yuanta_pcf",
        "source_url": None,
        "trade_date": None,
        "posting_dt": None,
        "units_outstanding": None,
        "units_chg_1d": None,
        "dq": [],
    }

    if not html:
        dq.append("ETF_UNITS_PCF_EMPTY_HTML")
        etf["dq"] = dq
        return etf, dq

    # normalize full-width colon and whitespace
    t = html.replace("\uFF1A", ":")
    # collapse multiple spaces but keep newlines meaningful for regex \s
    t = re.sub(r"[ \t\r\f\v]+", " ", t)

    # Posting Date
    m = re.search(r"Posting Date\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2})", t)
    if m:
        etf["posting_dt"] = m.group(1)
    else:
        dq.append("ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND")

    # Trade Date (there are multiple occurrences; use the first one after 'Trade Date')
    m = re.search(r"Trade Date\s*:\s*([0-9]{4}/[0-9]{2}/[0-9]{2})", t)
    if m:
        etf["trade_date"] = m.group(1)
    else:
        dq.append("ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND")

    def find_number_after(label: str, max_chars: int = 400) -> Optional[int]:
        idx = t.find(label)
        if idx < 0:
            return None
        snippet = t[idx : idx + max_chars]
        mm = re.search(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,})", snippet)
        if not mm:
            return None
        try:
            return int(mm.group(1).replace(",", ""))
        except Exception:
            return None

    units = find_number_after("Total Outstanding Shares")
    if units is None:
        # fallback (in case label changes slightly)
        units = find_number_after("Outstanding Shares")
    if units is not None:
        etf["units_outstanding"] = units
    else:
        dq.append("ETF_UNITS_PCF_OUTSTANDING_NOT_FOUND")

    chg = find_number_after("Net Change in Outstanding Shares")
    if chg is None:
        chg = find_number_after("Net Change")
    if chg is not None:
        etf["units_chg_1d"] = chg
    else:
        dq.append("ETF_UNITS_PCF_NET_CHANGE_NOT_FOUND")

    if (
        etf["posting_dt"] is None
        and etf["trade_date"] is None
        and etf["units_outstanding"] is None
        and etf["units_chg_1d"] is None
    ):
        dq.append("ETF_UNITS_PCF_PARSE_ALL_MISSING")

    etf["dq"] = dq
    return etf, dq


def fetch_etf_units(stock_no: str, cfg: FetchCfg, pcf_url: Optional[str]) -> Tuple[Dict[str, Any], List[str]]:
    url = pcf_url or YUANTA_PCF_URL_TPL.format(stock_no=str(stock_no).strip())
    html, err = http_get_text(url, cfg)
    if html is None:
        etf = {
            "source": "yuanta_pcf",
            "source_url": url,
            "trade_date": None,
            "posting_dt": None,
            "units_outstanding": None,
            "units_chg_1d": None,
            "dq": ["ETF_UNITS_FETCH_FAILED", f"ETF_UNITS_ERR:{err}"],
        }
        return etf, etf["dq"]

    etf, dq = parse_yuanta_pcf_units(html)
    etf["source_url"] = url
    return etf, dq


def build_overlay(
    stock_no: str,
    stats_path: str,
    window_n: int,
    cfg: FetchCfg,
    pcf_url: Optional[str] = None,
) -> Dict[str, Any]:
    if not os.path.exists(stats_path):
        raise SystemExit(f"ERROR: stats_path not found: {stats_path}")

    s = load_json(stats_path)
    meta = safe_get(s, "meta", {}) or {}
    last_date_s = safe_get(meta, "last_date", None) or safe_get(safe_get(s, "latest", {}), "date", None)
    last_dt = parse_iso_ymd(str(last_date_s)) if last_date_s else None
    if last_dt is None:
        raise SystemExit(f"ERROR: cannot parse meta.last_date from stats_latest.json: {last_date_s}")

    aligned_last_date = ymd(last_dt)

    per_day: List[Dict[str, Any]] = []
    t86_days_used: List[str] = []
    foreign_sum = 0
    trust_sum = 0
    dealer_sum = 0
    total3_sum = 0

    # We must include non-trading days until we collect >= window_n valid trading days for aggregation.
    # Max lookback is defensive to avoid infinite loop.
    max_lookback = max(30, window_n * 8)
    got = 0
    cur = last_dt

    while got < window_n and len(per_day) < max_lookback:
        ds = ymd(cur)
        day_entry: Dict[str, Any] = {
            "date": ds,
            "dq": [],
            "sources": {
                "t86": TWSE_T86_TPL.format(ymd=ds),
                "twt72u": TWSE_TWT72U_TPL.format(ymd=ds),
            },
        }

        t86 = fetch_t86_one_day(stock_no, ds, cfg)
        twt72u = fetch_twt72u_one_day(stock_no, ds, cfg)

        day_entry["t86"] = t86
        day_entry["twt72u"] = twt72u

        # mark non-trading / no-data
        is_t86_ok = ("T86_EMPTY" not in (t86.get("dq") or [])) and (t86.get("raw_row") is not None)
        is_twt_ok = ("TWT72U_EMPTY" not in (twt72u.get("dq") or [])) and (twt72u.get("raw_row") is not None)
        if (not is_t86_ok) and (not is_twt_ok):
            day_entry["dq"].append("NON_TRADING_OR_NO_DATA")

        # use day for aggregation only if T86 is OK (we want consistent window definition)
        if is_t86_ok:
            f = t86.get("foreign_net_shares")
            t = t86.get("trust_net_shares")
            d = t86.get("dealer_net_shares")
            tt = t86.get("total3_net_shares")
            # be defensive: only count when all are present ints
            if all(isinstance(x, int) for x in [f, t, d, tt]):
                foreign_sum += int(f)
                trust_sum += int(t)
                dealer_sum += int(d)
                total3_sum += int(tt)
                t86_days_used.append(ds)
                got += 1

        per_day.append(day_entry)
        cur = cur - timedelta(days=1)

    # Borrow summary: use the latest two available TWT72U rows in per_day
    def _borrow_rec(e: Dict[str, Any]) -> Optional[Tuple[str, Optional[int], Optional[float]]]:
        tw = safe_get(e, "twt72u", {}) or {}
        bs = safe_get(tw, "borrow_shares", None)
        mv = safe_get(tw, "borrow_mv_ntd", None)
        if bs is None and mv is None:
            return None
        return (str(e.get("date")), bs, mv)

    borrow_rows = [r for r in (_borrow_rec(e) for e in per_day) if r is not None]
    borrow_summary: Dict[str, Any] = {
        "asof_date": None,
        "borrow_shares": None,
        "borrow_shares_chg_1d": None,
        "borrow_mv_ntd": None,
        "borrow_mv_ntd_chg_1d": None,
    }
    if borrow_rows:
        # per_day is newest -> oldest
        asof_date, bs, mv = borrow_rows[0]
        borrow_summary["asof_date"] = asof_date
        borrow_summary["borrow_shares"] = bs
        borrow_summary["borrow_mv_ntd"] = mv

        if len(borrow_rows) >= 2:
            _, bs_prev, mv_prev = borrow_rows[1]
            if bs is not None and bs_prev is not None:
                borrow_summary["borrow_shares_chg_1d"] = int(bs) - int(bs_prev)
            if mv is not None and mv_prev is not None:
                borrow_summary["borrow_mv_ntd_chg_1d"] = float(mv) - float(mv_prev)

    # T86 aggregate (keep day order ascending for readability)
    t86_agg = {
        "window_n": window_n,
        "days_used": list(reversed(t86_days_used)),
        "foreign_net_shares_sum": int(foreign_sum),
        "trust_net_shares_sum": int(trust_sum),
        "dealer_net_shares_sum": int(dealer_sum),
        "total3_net_shares_sum": int(total3_sum),
    }

    # ETF units
    etf_units, etf_dq = fetch_etf_units(stock_no, cfg, pcf_url=pcf_url)

    # extra alignment check: ETF trade_date vs aligned_last_date
    if etf_units.get("trade_date"):
        td = parse_iso_ymd(str(etf_units["trade_date"]))
        if td is not None and ymd(td) != aligned_last_date:
            etf_dq = list(etf_dq or [])
            etf_dq.append("ETF_UNITS_DATE_MISALIGNED")
            etf_units["dq"] = etf_dq

    dq_flags: List[str] = []
    # Promote ETF dq to top-level (only key ones)
    if etf_dq:
        dq_flags.append("ETF_UNITS_FETCH_FAILED") if "ETF_UNITS_FETCH_FAILED" in etf_dq else None
        if "ETF_UNITS_PCF_PARSE_ALL_MISSING" in etf_dq:
            dq_flags.append("ETF_UNITS_PCF_PARSE_ALL_MISSING")
        if "ETF_UNITS_DATE_MISALIGNED" in etf_dq:
            dq_flags.append("ETF_UNITS_DATE_MISALIGNED")

    # final payload
    payload: Dict[str, Any] = {
        "meta": {
            "run_ts_utc": utc_now_iso_millis(),
            "script_fingerprint": BUILD_SCRIPT_FINGERPRINT,
            "stock_no": str(stock_no),
            "window_n": int(window_n),
            "timeout": float(cfg.timeout),
            "retries": int(cfg.retries),
            "backoff": float(cfg.backoff),
            "aligned_last_date": aligned_last_date,
        },
        "sources": {
            "t86_tpl": TWSE_T86_TPL,
            "twt72u_tpl": TWSE_TWT72U_TPL,
            "pcf_url": etf_units.get("source_url") or (pcf_url or YUANTA_PCF_URL_TPL.format(stock_no=str(stock_no))),
        },
        "dq": {"flags": dq_flags},
        "data": {
            "borrow_summary": borrow_summary,
            "etf_units": etf_units,
            "per_day": per_day,
            "t86_agg": t86_agg,
        },
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()

    # ---- compatibility knobs ----
    ap.add_argument("--cache_dir", default=None, help="optional; used to infer default stats_path/out")
    ap.add_argument("--out", default=None, help="output json path (preferred arg name)")
    ap.add_argument("--out_path", default=None, help="alias of --out (backward compatible)")
    ap.add_argument("--stats_path", default=None, help="path to stats_latest.json")
    ap.add_argument("--stock_no", default="0050")
    ap.add_argument("--window_n", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)

    # optional override for Yuanta PCF URL (debug / mirror)
    ap.add_argument("--pcf_url", default=None)

    args = ap.parse_args()

    # Resolve out path
    out_path = args.out or args.out_path
    stats_path = args.stats_path

    # cache_dir is OPTIONAL now (fix your workflow error)
    if args.cache_dir:
        if stats_path is None:
            stats_path = os.path.join(args.cache_dir, "stats_latest.json")
        if out_path is None:
            out_path = os.path.join(args.cache_dir, "chip_overlay.json")

    if stats_path is None:
        raise SystemExit("ERROR: missing --stats_path (or provide --cache_dir to infer it)")
    if out_path is None:
        raise SystemExit("ERROR: missing --out (or provide --cache_dir to infer it)")

    cfg = FetchCfg(timeout=float(args.timeout), retries=int(args.retries), backoff=float(args.backoff))

    payload = build_overlay(
        stock_no=str(args.stock_no).strip(),
        stats_path=str(stats_path),
        window_n=int(args.window_n),
        cfg=cfg,
        pcf_url=args.pcf_url,
    )

    write_json(str(out_path), payload)
    print(f"Wrote chip overlay: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())