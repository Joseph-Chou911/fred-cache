#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# ===== Audit stamp =====
SCRIPT_FINGERPRINT = "fetch_tw0050_chip_overlay@2026-02-19.v3"

# ===== Sources =====
T86_TPL = "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999"
TWT72U_TPL = "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB"
# Yuanta 0050 PCF page (units outstanding, net change)
YUANTA_PCF_0050_URL = "https://www.yuantaetfs.com/tradeInfo/pcf/0050"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"


def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}", flush=True)


def _info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x).strip().replace(",", "")
        if s == "" or s.upper() == "N/A":
            return None
        return int(float(s))
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if s == "" or s.upper() == "N/A":
            return None
        return float(s)
    except Exception:
        return None


def _ymd_from_iso_date(iso_ymd: str) -> Optional[str]:
    """
    Input: '2026-02-11' -> '20260211'
    """
    try:
        s = str(iso_ymd).strip()
        if re.fullmatch(r"\d{8}", s):
            return s
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y%m%d")
    except Exception:
        return None


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


@dataclass
class HttpCfg:
    timeout: float
    retries: int
    backoff: float


def http_get(url: str, cfg: HttpCfg) -> Tuple[Optional[requests.Response], List[str]]:
    """
    Returns (response_or_none, dq_flags)
    """
    dq: List[str] = []
    headers = {"User-Agent": UA, "Accept": "*/*"}
    last_err = None
    for i in range(cfg.retries):
        try:
            r = requests.get(url, headers=headers, timeout=cfg.timeout)
            if r.status_code == 200:
                return r, dq
            last_err = f"status={r.status_code}"
            dq.append(f"HTTP_STATUS_{r.status_code}")
        except Exception as e:
            last_err = repr(e)
            dq.append("HTTP_EXCEPTION")
        # backoff
        if i < cfg.retries - 1:
            time.sleep(cfg.backoff * (2 ** i))
    if last_err:
        _warn(f"GET failed: {url} ({last_err})")
    return None, dq


# =========================
# PCF (Yuanta) parser
# =========================
def parse_yuanta_pcf_units(html: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Best-effort parser for:
      - Trade Date
      - Posting Date
      - Total Outstanding Shares
      - Net Change in Outstanding Shares

    Output dict:
      {
        "source": "yuanta_pcf",
        "source_url": "...",
        "trade_date": "YYYYMMDD" or None,
        "posting_dt": "YYYY-MM-DD HH:MM:SS" or raw string or None,
        "units_outstanding": int or None,
        "units_chg_1d": int or None,
        "raw_snippet": "...optional small snippet..."
      }
    DQ flags for missing fields / parse failure.
    """
    dq: List[str] = []
    out: Dict[str, Any] = {
        "source": "yuanta_pcf",
        "source_url": YUANTA_PCF_0050_URL,
        "trade_date": None,
        "posting_dt": None,
        "units_outstanding": None,
        "units_chg_1d": None,
    }

    if not html or len(html) < 200:
        dq.append("ETF_UNITS_PCF_EMPTY_HTML")
        return out, dq

    # Normalize whitespace for regex scanning
    s = re.sub(r"\s+", " ", html)

    # --- Trade Date ---
    # English label commonly: "Trade Date"
    m = re.search(r"Trade\s*Date[^0-9]{0,30}(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s, re.IGNORECASE)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        out["trade_date"] = f"{y:04d}{mo:02d}{d:02d}"
    else:
        dq.append("ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND")

    # --- Posting Date ---
    # English label: "Posting Date"
    m = re.search(
        r"Posting\s*Date[^0-9]{0,30}(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}:\d{2}:\d{2})",
        s,
        re.IGNORECASE,
    )
    if m:
        y, mo, d, t = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        out["posting_dt"] = f"{y:04d}-{mo:02d}-{d:02d} {t}"
    else:
        # not fatal
        dq.append("ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND")

    # --- Total Outstanding Shares ---
    # English label: "Total Outstanding Shares"
    # Try a few patterns to be robust vs HTML changes.
    patterns_outstanding = [
        r"Total\s*Outstanding\s*Shares[^0-9]{0,60}([0-9][0-9,]{3,})",
        r"Outstanding\s*Shares[^0-9]{0,60}([0-9][0-9,]{3,})",
    ]
    outstanding = None
    for pat in patterns_outstanding:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            outstanding = _to_int(m.group(1))
            if outstanding is not None:
                break
    if outstanding is None:
        dq.append("ETF_UNITS_PCF_OUTSTANDING_NOT_FOUND")
    out["units_outstanding"] = outstanding

    # --- Net Change in Outstanding Shares ---
    patterns_chg = [
        r"Net\s*Change\s*in\s*Outstanding\s*Shares[^0-9\-\+]{0,60}([+\-]?[0-9][0-9,]{1,})",
        r"Net\s*Change[^0-9\-\+]{0,60}([+\-]?[0-9][0-9,]{1,})",
    ]
    chg = None
    for pat in patterns_chg:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            chg = _to_int(m.group(1))
            if chg is not None:
                break
    if chg is None:
        dq.append("ETF_UNITS_PCF_NET_CHANGE_NOT_FOUND")
    out["units_chg_1d"] = chg

    # Provide a small snippet for audit (keep small; no huge HTML dump)
    try:
        # find where "Total Outstanding Shares" occurs
        idx = s.lower().find("total outstanding shares")
        if idx >= 0:
            out["raw_snippet"] = s[max(0, idx - 80): idx + 220]
        else:
            # fallback snippet near "Trade Date"
            idx = s.lower().find("trade date")
            if idx >= 0:
                out["raw_snippet"] = s[max(0, idx - 80): idx + 220]
    except Exception:
        pass

    # If both numbers missing, treat as fetch failed rather than "not implemented"
    if out["units_outstanding"] is None and out["units_chg_1d"] is None:
        dq.append("ETF_UNITS_FETCH_FAILED")

    return out, dq


def fetch_etf_units_from_pcf(cfg: HttpCfg) -> Tuple[Dict[str, Any], List[str]]:
    r, dq_http = http_get(YUANTA_PCF_0050_URL, cfg)
    if r is None:
        out = {
            "source": "yuanta_pcf",
            "source_url": YUANTA_PCF_0050_URL,
            "trade_date": None,
            "posting_dt": None,
            "units_outstanding": None,
            "units_chg_1d": None,
        }
        dq = list(dq_http) + ["ETF_UNITS_FETCH_FAILED"]
        return out, dq
    parsed, dq_parse = parse_yuanta_pcf_units(r.text)
    dq = list(dq_http) + list(dq_parse)
    return parsed, dq


# =========================
# TWSE endpoints
# =========================
def twse_fetch_json(url: str, cfg: HttpCfg) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    r, dq_http = http_get(url, cfg)
    if r is None:
        return None, list(dq_http) + ["TWSE_FETCH_FAILED"]
    try:
        j = r.json()
        return j, dq_http
    except Exception:
        return None, list(dq_http) + ["TWSE_JSON_PARSE_FAILED"]


def pick_row_by_stock(data_rows: List[List[Any]], stock_no: str) -> Optional[List[Any]]:
    """
    TWSE JSON payload usually has "data": [ [...], [...], ...]
    First col often is stock code.
    """
    for row in data_rows:
        try:
            if not row:
                continue
            if str(row[0]).strip() == str(stock_no).strip():
                return row
        except Exception:
            continue
    return None


def parse_t86(j: Dict[str, Any], stock_no: str) -> Tuple[Dict[str, Any], List[str]]:
    dq: List[str] = []
    out: Dict[str, Any] = {"dq": []}

    if not isinstance(j, dict):
        dq.append("T86_BAD_JSON")
        out["dq"] = dq
        return out, dq

    fields = j.get("fields") or []
    data = j.get("data") or []

    if not fields or not data:
        dq.append("T86_EMPTY")
        out["dq"] = dq
        out["fields"] = fields
        return out, dq

    row = pick_row_by_stock(data, stock_no)
    if row is None:
        dq.append("T86_ROW_NOT_FOUND")
        out["dq"] = dq
        out["fields"] = fields
        return out, dq

    out["fields"] = fields
    out["raw_row"] = row

    # map column indexes (based on your previous design)
    # foreign net: "外陸資買賣超股數(不含外資自營商)" usually index 4 (0-based?) in row list
    # trust net: "投信買賣超股數" usually index 10
    # dealer net: "自營商買賣超股數" usually index 11
    # total3 net: "三大法人買賣超股數" usually last index 18
    # We'll locate by field name to be safer.
    def idx_of(name: str) -> Optional[int]:
        try:
            return fields.index(name)
        except Exception:
            return None

    idx_foreign = idx_of("外陸資買賣超股數(不含外資自營商)")
    idx_trust = idx_of("投信買賣超股數")
    idx_dealer = idx_of("自營商買賣超股數")
    idx_total3 = idx_of("三大法人買賣超股數")

    # fallback to your historic assumption if not found
    if idx_foreign is None:
        idx_foreign = 4
        dq.append("T86_COL_FALLBACK_FOREIGN_4")
    if idx_trust is None:
        idx_trust = 10
        dq.append("T86_COL_FALLBACK_TRUST_10")
    if idx_dealer is None:
        idx_dealer = 11
        dq.append("T86_COL_FALLBACK_DEALER_11")
    if idx_total3 is None:
        idx_total3 = 18
        dq.append("T86_COL_FALLBACK_TOTAL3_18")

    def get_int(i: int) -> Optional[int]:
        try:
            return _to_int(row[i])
        except Exception:
            return None

    foreign = get_int(idx_foreign)
    trust = get_int(idx_trust)
    dealer = get_int(idx_dealer)
    total3 = get_int(idx_total3)

    out["col_idx"] = {
        "foreign": idx_foreign,
        "trust": idx_trust,
        "dealer": idx_dealer,
        "total3": idx_total3,
    }
    out["foreign_net_shares"] = foreign
    out["trust_net_shares"] = trust
    out["dealer_net_shares"] = dealer
    out["total3_net_shares"] = total3

    out["dq"] = dq
    return out, dq


def parse_twt72u(j: Dict[str, Any], stock_no: str) -> Tuple[Dict[str, Any], List[str]]:
    dq: List[str] = []
    out: Dict[str, Any] = {"dq": []}

    if not isinstance(j, dict):
        dq.append("TWT72U_BAD_JSON")
        out["dq"] = dq
        return out, dq

    fields = j.get("fields") or []
    data = j.get("data") or []

    if not fields or not data:
        dq.append("TWT72U_EMPTY")
        out["dq"] = dq
        out["fields"] = fields
        return out, dq

    row = pick_row_by_stock(data, stock_no)
    if row is None:
        dq.append("TWT72U_ROW_NOT_FOUND")
        out["dq"] = dq
        out["fields"] = fields
        return out, dq

    out["fields"] = fields
    out["raw_row"] = row

    # Identify:
    # - shares_end: "本日借券餘額股(4)=(1)+(2)-(3)"
    # - close: "本日收盤價(5)單位：元"
    # - mv: "借券餘額市值單位：元(6)=(4)*(5)"
    def idx_of(name: str) -> Optional[int]:
        try:
            return fields.index(name)
        except Exception:
            return None

    idx_shares_end = idx_of("本日借券餘額股(4)=(1)+(2)-(3)")
    idx_close = idx_of("本日收盤價(5)單位：元")
    idx_mv = idx_of("借券餘額市值單位：元(6)=(4)*(5)")

    # fallback to your v2 structure (shares_end=5, close=6, mv=7)
    if idx_shares_end is None:
        idx_shares_end = 5
        dq.append("TWT72U_COL_FALLBACK_SHARES_END_5")
    if idx_close is None:
        idx_close = 6
        dq.append("TWT72U_COL_FALLBACK_CLOSE_6")
    if idx_mv is None:
        idx_mv = 7
        dq.append("TWT72U_COL_FALLBACK_MV_7")

    shares_end = _to_int(row[idx_shares_end])
    close = _to_float(row[idx_close])
    mv = _to_float(row[idx_mv])

    out["col_idx"] = {"shares_end": idx_shares_end, "close": idx_close, "mv": idx_mv}
    out["borrow_shares"] = shares_end
    out["borrow_mv_ntd"] = mv
    out["close"] = close
    out["dq"] = dq
    return out, dq


# =========================
# Window helpers
# =========================
def infer_days_from_per_day(per_day: List[Dict[str, Any]]) -> List[str]:
    ds = []
    for it in per_day:
        d = it.get("date")
        if isinstance(d, str) and re.fullmatch(r"\d{8}", d):
            ds.append(d)
    return ds


def compute_t86_agg(per_day: List[Dict[str, Any]], window_n: int) -> Dict[str, Any]:
    """
    Sum last `window_n` available days that have T86 row.
    Note: per_day is built in chronological request order; we will use the most recent `window_n` by date.
    """
    rows = []
    for it in per_day:
        t86 = it.get("t86") or {}
        if isinstance(t86, dict) and t86.get("dq") == [] and t86.get("raw_row") is not None:
            rows.append(it)

    # sort by date, take last window_n
    def key_fn(x):
        return x.get("date") or ""

    rows = sorted(rows, key=key_fn)
    used = rows[-window_n:] if window_n > 0 else rows

    def get_int(it: Dict[str, Any], k: str) -> int:
        v = ((it.get("t86") or {}).get(k))
        return int(v) if isinstance(v, int) else int(v) if isinstance(v, float) else int(v) if isinstance(v, str) and v.isdigit() else (v if isinstance(v, int) else 0)

    def safe_int(v: Any) -> int:
        iv = _to_int(v)
        return int(iv) if iv is not None else 0

    foreign_sum = 0
    trust_sum = 0
    dealer_sum = 0
    total3_sum = 0
    days_used: List[str] = []

    for it in used:
        d = it.get("date")
        if isinstance(d, str):
            days_used.append(d)
        t86 = it.get("t86") or {}
        foreign_sum += safe_int(t86.get("foreign_net_shares"))
        trust_sum += safe_int(t86.get("trust_net_shares"))
        dealer_sum += safe_int(t86.get("dealer_net_shares"))
        total3_sum += safe_int(t86.get("total3_net_shares"))

    return {
        "window_n": window_n,
        "days_used": days_used,
        "foreign_net_shares_sum": foreign_sum,
        "trust_net_shares_sum": trust_sum,
        "dealer_net_shares_sum": dealer_sum,
        "total3_net_shares_sum": total3_sum,
    }


def compute_borrow_summary(per_day: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Use the latest available day in per_day that has TWT72U borrow_shares & borrow_mv_ntd.
    Also compute 1-day change if the previous day exists.
    """
    items = sorted(per_day, key=lambda x: x.get("date") or "")
    latest = None
    prev = None
    for it in reversed(items):
        twt = it.get("twt72u") or {}
        if isinstance(twt, dict) and twt.get("borrow_shares") is not None:
            latest = it
            break
    if latest is None:
        return {
            "asof_date": None,
            "borrow_shares": None,
            "borrow_shares_chg_1d": None,
            "borrow_mv_ntd": None,
            "borrow_mv_ntd_chg_1d": None,
        }

    # find prev available
    latest_date = latest.get("date")
    found_latest = False
    for it in reversed(items):
        if it is latest:
            found_latest = True
            continue
        if not found_latest:
            continue
        twt = it.get("twt72u") or {}
        if isinstance(twt, dict) and twt.get("borrow_shares") is not None:
            prev = it
            break

    lt = latest.get("twt72u") or {}
    asof = latest_date
    shares = lt.get("borrow_shares")
    mv = lt.get("borrow_mv_ntd")

    shares_chg = None
    mv_chg = None
    if prev is not None:
        pv = prev.get("twt72u") or {}
        pshares = pv.get("borrow_shares")
        pmv = pv.get("borrow_mv_ntd")
        if shares is not None and pshares is not None:
            try:
                shares_chg = int(shares) - int(pshares)
            except Exception:
                shares_chg = None
        if mv is not None and pmv is not None:
            try:
                mv_chg = float(mv) - float(pmv)
            except Exception:
                mv_chg = None

    return {
        "asof_date": asof,
        "borrow_shares": shares,
        "borrow_shares_chg_1d": shares_chg,
        "borrow_mv_ntd": mv,
        "borrow_mv_ntd_chg_1d": mv_chg,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--stats_path", required=True)
    ap.add_argument("--out_path", required=True)
    ap.add_argument("--window_n", type=int, default=5)
    ap.add_argument("--stock_no", default="0050")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)

    args = ap.parse_args()

    ensure_dir(args.cache_dir)

    cfg = HttpCfg(timeout=float(args.timeout), retries=int(args.retries), backoff=float(args.backoff))

    # ---- read stats to get price_last_date ----
    if not os.path.exists(args.stats_path):
        raise SystemExit(f"ERROR: stats_path not found: {args.stats_path}")
    stats = load_json(args.stats_path)
    meta = stats.get("meta", {}) or {}
    price_last_date_iso = meta.get("last_date")
    if not price_last_date_iso:
        raise SystemExit("ERROR: stats_latest.json missing meta.last_date")
    price_last_ymd = _ymd_from_iso_date(str(price_last_date_iso))
    if not price_last_ymd:
        raise SystemExit(f"ERROR: cannot parse meta.last_date: {price_last_date_iso}")

    # We will fetch TWSE days: [last_date - (window_n+buffer)] is unknown without calendar,
    # so we will just attempt backward by scanning stats price tail dates if available.
    # But your current overlay expects exactly 5 days; you already accept "days_used" subset.
    # We'll attempt a simple approach: use the last N dates from data.csv if exists; else use last_date and go backwards 1 day repeatedly.
    # Because you already accept daily accumulation, we'll follow: take latest N trading days present in stats history if it exists.
    # To keep deterministic, we will generate candidate dates by walking backward one day at a time and collecting successful TWSE responses.
    window_n = max(1, int(args.window_n))
    stock_no = str(args.stock_no).strip()

    # ---- fetch PCF units first ----
    etf_units, dq_units = fetch_etf_units_from_pcf(cfg)

    # alignment check between PCF trade_date and price_last_ymd
    if etf_units.get("trade_date") and str(etf_units["trade_date"]) != str(price_last_ymd):
        dq_units.append("ETF_UNITS_DATE_MISALIGNED")

    # ---- fetch TWSE per day ----
    per_day: List[Dict[str, Any]] = []
    dq_flags_global: List[str] = []

    # Candidate dates: walk backward from price_last_ymd until we collect window_n+1 (to support 1D deltas) successful per_day items.
    # cap to avoid infinite loop
    collected = 0
    need_collect = max(window_n + 1, window_n)
    cap_days = 40  # enough to cross holidays
    try:
        start_dt = datetime.strptime(price_last_ymd, "%Y%m%d")
    except Exception:
        start_dt = datetime.now()

    for i in range(cap_days):
        dt = start_dt
        # subtract i days
        cand = dt.timestamp() - i * 86400
        cand_dt = datetime.fromtimestamp(cand)
        ymd = cand_dt.strftime("%Y%m%d")

        # fetch T86
        t86_url = T86_TPL.format(ymd=ymd)
        j86, dq86 = twse_fetch_json(t86_url, cfg)
        # If no data, still record day with dq but continue
        t86_parsed, dq86p = parse_t86(j86 or {}, stock_no)
        dq86_all = list(dq86) + list(dq86p)
        t86_parsed["dq"] = dq86_all

        # fetch TWT72U
        twt_url = TWT72U_TPL.format(ymd=ymd)
        j72, dq72 = twse_fetch_json(twt_url, cfg)
        twt_parsed, dq72p = parse_twt72u(j72 or {}, stock_no)
        dq72_all = list(dq72) + list(dq72p)
        twt_parsed["dq"] = dq72_all

        day_obj = {
            "date": ymd,
            "dq": [],
            "sources": {"t86": t86_url, "twt72u": twt_url},
            "t86": t86_parsed,
            "twt72u": twt_parsed,
        }

        # day-level dq: if both endpoints have "row not found"/"empty" this is likely non-trading day; mark and skip count
        day_dq: List[str] = []
        # identify non-trading / no-row day
        t86_bad = any(x in dq86_all for x in ["T86_EMPTY", "T86_ROW_NOT_FOUND"])
        twt_bad = any(x in dq72_all for x in ["TWT72U_EMPTY", "TWT72U_ROW_NOT_FOUND"])
        if t86_bad and twt_bad:
            day_dq.append("NON_TRADING_OR_NO_DATA")
            day_obj["dq"] = day_dq
            per_day.append(day_obj)
            continue

        # count as usable day if at least one side has usable fields
        per_day.append(day_obj)
        collected += 1
        if collected >= need_collect:
            break

    # aligned_last_date: use max date in per_day that is not NON_TRADING
    aligned_last_date = None
    for it in sorted(per_day, key=lambda x: x.get("date") or ""):
        if "NON_TRADING_OR_NO_DATA" in (it.get("dq") or []):
            continue
        aligned_last_date = it.get("date")

    # Build aggregates (use window_n most recent usable days)
    # Filter out non-trading
    usable = [it for it in per_day if "NON_TRADING_OR_NO_DATA" not in (it.get("dq") or [])]
    usable_sorted = sorted(usable, key=lambda x: x.get("date") or "")
    usable_tail = usable_sorted[-window_n:] if len(usable_sorted) >= window_n else usable_sorted

    # But keep per_day as collected raw (including non-trading marks) for audit.
    t86_agg = compute_t86_agg(usable_sorted, window_n=window_n)
    borrow_summary = compute_borrow_summary(usable_sorted)

    # Compose final output
    out: Dict[str, Any] = {
        "meta": {
            "run_ts_utc": utc_now_iso_z(),
            "script_fingerprint": SCRIPT_FINGERPRINT,
            "stock_no": stock_no,
            "window_n": window_n,
            "timeout": cfg.timeout,
            "retries": cfg.retries,
            "backoff": cfg.backoff,
            "aligned_last_date": aligned_last_date,
        },
        "sources": {
            "t86_tpl": T86_TPL,
            "twt72u_tpl": TWT72U_TPL,
            "pcf_url": YUANTA_PCF_0050_URL,
        },
        "dq": {
            "flags": sorted(list(set(dq_flags_global))),
        },
        "data": {
            "borrow_summary": borrow_summary,
            "etf_units": {
                "source": etf_units.get("source"),
                "source_url": etf_units.get("source_url"),
                "trade_date": etf_units.get("trade_date"),
                "posting_dt": etf_units.get("posting_dt"),
                "units_outstanding": etf_units.get("units_outstanding"),
                "units_chg_1d": etf_units.get("units_chg_1d"),
                "dq": sorted(list(set(dq_units))),
            },
            "per_day": per_day,
            "t86_agg": t86_agg,
        },
    }

    # If ETF units fully missing, carry a clearer top-level dq note (still keep section dq)
    if out["data"]["etf_units"]["units_outstanding"] is None and out["data"]["etf_units"]["units_chg_1d"] is None:
        out["dq"]["flags"] = sorted(list(set(out["dq"]["flags"] + ["ETF_UNITS_FETCH_FAILED"])))

    # Write json
    with open(args.out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    _info(f"Wrote: {args.out_path}")
    _info(f"price_last_date_iso={price_last_date_iso} price_last_ymd={price_last_ymd} aligned_last_date={aligned_last_date}")
    _info(f"etf_units.trade_date={out['data']['etf_units'].get('trade_date')} dq={out['data']['etf_units'].get('dq')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())