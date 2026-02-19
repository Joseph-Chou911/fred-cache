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

# ===== Audit stamp =====
BUILD_SCRIPT_FINGERPRINT = "fetch_tw0050_chip_overlay@2026-02-19.v6"

TWSE_T86_TPL = "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999"
TWSE_TWT72U_TPL = "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB"
YUANTA_PCF_URL_TPL = "https://www.yuantaetfs.com/tradeInfo/pcf/{stock_no}"


def utc_now_iso_millis() -> str:
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


def _pick_row_by_stock(data_rows: List[List[Any]], stock_no: str) -> Optional[List[Any]]:
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


# ---------- Field index helpers (T86) ----------

def _idx_exact(fields: List[str], exact: str) -> Optional[int]:
    for i, f in enumerate(fields or []):
        if str(f).strip() == exact:
            return i
    return None


def _idx_contains(fields: List[str], contains: str, exclude_contains: Optional[str] = None) -> Optional[int]:
    for i, f in enumerate(fields or []):
        s = str(f)
        if contains in s:
            if exclude_contains and exclude_contains in s:
                continue
            return i
    return None


def _t86_idx_foreign(fields: List[str]) -> Optional[int]:
    # Prefer exact
    exact = "外陸資買賣超股數(不含外資自營商)"
    i = _idx_exact(fields, exact)
    if i is not None:
        return i
    # fallback contains
    return _idx_contains(fields, "外陸資買賣超股數")


def _t86_idx_trust(fields: List[str]) -> Optional[int]:
    exact = "投信買賣超股數"
    i = _idx_exact(fields, exact)
    if i is not None:
        return i
    return _idx_contains(fields, "投信買賣超股數")


def _t86_idx_dealer(fields: List[str]) -> Optional[int]:
    # IMPORTANT: exclude 外資自營商
    exact = "自營商買賣超股數"
    i = _idx_exact(fields, exact)
    if i is not None:
        return i
    return _idx_contains(fields, "自營商買賣超股數", exclude_contains="外資自營商")


def _t86_idx_total3(fields: List[str]) -> Optional[int]:
    exact = "三大法人買賣超股數"
    i = _idx_exact(fields, exact)
    if i is not None:
        return i
    return _idx_contains(fields, "三大法人買賣超股數")


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

    idx_foreign = _t86_idx_foreign(fields)
    idx_trust = _t86_idx_trust(fields)
    idx_dealer = _t86_idx_dealer(fields)
    idx_total3 = _t86_idx_total3(fields)

    # fallback fixed layout (TWSE usually stable)
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

    out["foreign_net_shares"] = at(idx_foreign)
    out["trust_net_shares"] = at(idx_trust)
    out["dealer_net_shares"] = at(idx_dealer)
    out["total3_net_shares"] = at(idx_total3)
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

    def idx_contains(label: str) -> Optional[int]:
        for i, f in enumerate(fields):
            if label in str(f):
                return i
        return None

    idx_shares_end = idx_contains("本日借券餘額股")
    idx_close = idx_contains("本日收盤價")
    idx_mv = idx_contains("借券餘額市值")

    if idx_shares_end is None:
        idx_shares_end = 5
    if idx_close is None:
        idx_close = 6
    if idx_mv is None:
        idx_mv = 7

    out["col_idx"] = {"shares_end": idx_shares_end, "close": idx_close, "mv": idx_mv}

    out["borrow_shares"] = _strip_int(row[idx_shares_end]) if idx_shares_end < len(row) else None
    out["close"] = _strip_num(row[idx_close]) if idx_close < len(row) else None
    out["borrow_mv_ntd"] = _strip_num(row[idx_mv]) if idx_mv < len(row) else None
    return out


# ---------- Yuanta PCF parsing ----------

_DATE_RE_LIST = [
    # YYYY-MM-DD HH:MM:SS
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2})",
    # YYYY-MM-DD
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})",
    # YYYY/MM/DD
    r"([0-9]{4}/[0-9]{2}/[0-9]{2})",
]

def _find_first_date(snippet: str) -> Optional[str]:
    for pat in _DATE_RE_LIST:
        m = re.search(pat, snippet)
        if m:
            return m.group(1)
    return None


def parse_yuanta_pcf_units(html: str) -> Tuple[Dict[str, Any], List[str]]:
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

    # normalize
    t = html.replace("\uFF1A", ":")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)

    # helper: find near a label within N chars
    def near(label_variants: List[str], span: int = 900) -> Optional[str]:
        for lab in label_variants:
            idx = t.find(lab)
            if idx >= 0:
                return t[idx : idx + span]
        return None

    # Posting date (English + Chinese variants)
    sn = near(["Posting Date", "公告日期", "揭示日期", "資料日期", "更新時間"])
    if sn:
        d = _find_first_date(sn)
        if d:
            etf["posting_dt"] = d
        else:
            dq.append("ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND")
    else:
        dq.append("ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND")

    # Trade date (English + Chinese variants)
    sn = near(["Trade Date", "交易日", "交易日期"])
    if sn:
        d = _find_first_date(sn)
        if d:
            etf["trade_date"] = d
        else:
            dq.append("ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND")
    else:
        dq.append("ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND")

    def find_number_after(label_variants: List[str], max_chars: int = 900) -> Optional[int]:
        for lab in label_variants:
            idx = t.find(lab)
            if idx < 0:
                continue
            snippet = t[idx : idx + max_chars]
            mm = re.search(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,})", snippet)
            if not mm:
                continue
            try:
                return int(mm.group(1).replace(",", ""))
            except Exception:
                continue
        return None

    units = find_number_after(["Total Outstanding Shares", "Outstanding Shares", "流通在外", "流通單位", "發行單位數"])
    if units is not None:
        etf["units_outstanding"] = units
    else:
        dq.append("ETF_UNITS_PCF_OUTSTANDING_NOT_FOUND")

    chg = find_number_after(["Net Change in Outstanding Shares", "Net Change", "增減", "日增減", "淨增減"])
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


def build_overlay(stock_no: str, stats_path: str, window_n: int, cfg: FetchCfg, pcf_url: Optional[str]) -> Dict[str, Any]:
    if not os.path.exists(stats_path):
        raise SystemExit(f"ERROR: stats_path not found: {stats_path}")

    s = load_json(stats_path)
    meta = safe_get(s, "meta", {}) or {}
    last_date_s = safe_get(meta, "last_date", None)
    last_dt = parse_iso_ymd(str(last_date_s)) if last_date_s else None
    if last_dt is None:
        raise SystemExit(f"ERROR: cannot parse meta.last_date from stats_latest.json: {last_date_s}")

    aligned_last_date = ymd(last_dt)

    per_day: List[Dict[str, Any]] = []
    t86_days_used: List[str] = []
    foreign_sum = trust_sum = dealer_sum = total3_sum = 0

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

        is_t86_ok = ("T86_EMPTY" not in (t86.get("dq") or [])) and (t86.get("raw_row") is not None)
        is_twt_ok = ("TWT72U_EMPTY" not in (twt72u.get("dq") or [])) and (twt72u.get("raw_row") is not None)
        if (not is_t86_ok) and (not is_twt_ok):
            day_entry["dq"].append("NON_TRADING_OR_NO_DATA")

        if is_t86_ok:
            f = t86.get("foreign_net_shares")
            t = t86.get("trust_net_shares")
            d = t86.get("dealer_net_shares")
            tt = t86.get("total3_net_shares")
            if all(isinstance(x, int) for x in [f, t, d, tt]):
                foreign_sum += int(f)
                trust_sum += int(t)
                dealer_sum += int(d)
                total3_sum += int(tt)
                t86_days_used.append(ds)
                got += 1

        per_day.append(day_entry)
        cur = cur - timedelta(days=1)

    # Borrow summary: latest two available
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

    t86_agg = {
        "window_n": window_n,
        "days_used": list(reversed(t86_days_used)),
        "foreign_net_shares_sum": int(foreign_sum),
        "trust_net_shares_sum": int(trust_sum),
        "dealer_net_shares_sum": int(dealer_sum),
        "total3_net_shares_sum": int(total3_sum),
    }

    etf_units, etf_dq = fetch_etf_units(stock_no, cfg, pcf_url=pcf_url)

    # Only escalate to top-level flags if units cannot be obtained (dates missing alone should not break report)
    dq_flags: List[str] = []
    if etf_dq:
        if "ETF_UNITS_FETCH_FAILED" in etf_dq:
            dq_flags.append("ETF_UNITS_FETCH_FAILED")
        if "ETF_UNITS_PCF_PARSE_ALL_MISSING" in etf_dq:
            dq_flags.append("ETF_UNITS_PCF_PARSE_ALL_MISSING")
        if (etf_units.get("units_outstanding") is None) or (etf_units.get("units_chg_1d") is None):
            # missing key numeric values => treat as important
            dq_flags.append("ETF_UNITS_VALUE_MISSING")

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
    ap.add_argument("--cache_dir", default=None, help="optional; used to infer default stats_path/out")
    ap.add_argument("--out", default=None, help="output json path (preferred)")
    ap.add_argument("--out_path", default=None, help="alias of --out")
    ap.add_argument("--stats_path", default=None, help="path to stats_latest.json")
    ap.add_argument("--stock_no", default="0050")
    ap.add_argument("--window_n", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)
    ap.add_argument("--pcf_url", default=None)
    args = ap.parse_args()

    out_path = args.out or args.out_path
    stats_path = args.stats_path

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