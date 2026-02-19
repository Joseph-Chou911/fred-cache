#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# ===== Audit stamp =====
SCRIPT_FINGERPRINT = "fetch_tw0050_chip_overlay@2026-02-19.v4"

TZ_TAIPEI = timezone(timedelta(hours=8))

T86_TPL = "https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999"
TWT72U_TPL = "https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB"

DEFAULT_PCF_URL = "https://www.yuantaetfs.com/tradeInfo/pcf/0050"


def utc_now_iso_msless() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_get(d: Any, k: str, default=None):
    try:
        if isinstance(d, dict):
            return d.get(k, default)
    except Exception:
        pass
    return default


def _strip_commas_to_int(s: Any) -> Optional[int]:
    try:
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return int(s)
        x = str(s).strip()
        if x == "":
            return None
        x = x.replace(",", "")
        return int(float(x))
    except Exception:
        return None


def _strip_commas_to_float(s: Any) -> Optional[float]:
    try:
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return float(s)
        x = str(s).strip()
        if x == "":
            return None
        x = x.replace(",", "")
        return float(x)
    except Exception:
        return None


def _ymd_to_date(ymd: str) -> Optional[datetime]:
    """
    ymd: 'YYYYMMDD'
    return: datetime (00:00) in Taipei tz
    """
    try:
        ymd = str(ymd)
        if len(ymd) != 8:
            return None
        y = int(ymd[0:4])
        m = int(ymd[4:6])
        d = int(ymd[6:8])
        return datetime(y, m, d, tzinfo=TZ_TAIPEI)
    except Exception:
        return None


def _date_to_ymd(dt: datetime) -> str:
    return dt.astimezone(TZ_TAIPEI).strftime("%Y%m%d")


def _parse_stats_last_date(stats: Dict[str, Any]) -> Optional[str]:
    """
    stats_latest.json meta.last_date is typically 'YYYY-MM-DD'
    -> convert to 'YYYYMMDD'
    """
    meta = safe_get(stats, "meta", {}) or {}
    last_date = safe_get(meta, "last_date", None)
    if not last_date:
        return None
    s = str(last_date).strip()
    # common: 2026-02-11
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    # already yyyymmdd
    m2 = re.match(r"^(\d{8})$", s)
    if m2:
        return m2.group(1)
    return None


@dataclass
class HttpCfg:
    timeout: float
    retries: int
    backoff: float


def _http_get_text(url: str, cfg: HttpCfg) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    returns: (text, status_code, error_string)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    last_err = None
    last_status = None
    for i in range(max(1, int(cfg.retries))):
        try:
            r = requests.get(url, headers=headers, timeout=cfg.timeout)
            last_status = r.status_code
            if r.status_code == 200 and r.text:
                return r.text, r.status_code, None
            last_err = f"http_status={r.status_code}"
        except Exception as e:
            last_err = f"exception={type(e).__name__}:{e}"
        # backoff
        if i < cfg.retries - 1:
            time.sleep(cfg.backoff * (i + 1))
    return None, last_status, last_err


def _http_get_json(url: str, cfg: HttpCfg) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]:
    """
    returns: (json_dict, status_code, error_string)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    last_err = None
    last_status = None
    for i in range(max(1, int(cfg.retries))):
        try:
            r = requests.get(url, headers=headers, timeout=cfg.timeout)
            last_status = r.status_code
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict):
                    return j, r.status_code, None
                last_err = "json_not_dict"
            else:
                last_err = f"http_status={r.status_code}"
        except Exception as e:
            last_err = f"exception={type(e).__name__}:{e}"
        if i < cfg.retries - 1:
            time.sleep(cfg.backoff * (i + 1))
    return None, last_status, last_err


def _twse_no_data(j: Dict[str, Any]) -> bool:
    """
    TWSE APIs often return:
      {"stat":"OK", "fields":[...], "data":[...]}
    or {"stat":"No data", ...} / {"stat":"很抱歉，沒有符合條件的資料!"}
    """
    stat = str(safe_get(j, "stat", "") or "").strip()
    if stat and stat.upper() != "OK":
        return True
    data = safe_get(j, "data", None)
    if data is None:
        # sometimes key differs, treat as no data
        return True
    if isinstance(data, list) and len(data) == 0:
        return True
    return False


def _pick_row_by_stock(data_rows: Any, stock_no: str) -> Optional[List[Any]]:
    if not isinstance(data_rows, list):
        return None
    for r in data_rows:
        if isinstance(r, list) and len(r) > 0 and str(r[0]).strip() == str(stock_no):
            return r
    return None


def _parse_t86(j: Dict[str, Any], stock_no: str) -> Tuple[Dict[str, Any], List[str]]:
    dq: List[str] = []
    out: Dict[str, Any] = {"dq": dq, "fields": []}

    if j is None or not isinstance(j, dict) or _twse_no_data(j):
        dq.append("T86_EMPTY")
        return out, dq

    fields = safe_get(j, "fields", []) or []
    data_rows = safe_get(j, "data", []) or []

    out["fields"] = fields if isinstance(fields, list) else []
    row = _pick_row_by_stock(data_rows, stock_no)
    if row is None:
        dq.append("T86_ROW_NOT_FOUND")
        return out, dq

    out["raw_row"] = row

    # Prefer field-name lookup; fallback to known indices
    def idx_of(name: str) -> Optional[int]:
        try:
            return out["fields"].index(name)
        except Exception:
            return None

    idx_foreign = idx_of("外陸資買賣超股數(不含外資自營商)")
    idx_trust = idx_of("投信買賣超股數")
    idx_dealer = idx_of("自營商買賣超股數")
    idx_total3 = idx_of("三大法人買賣超股數")

    # Fallback indices (your earlier col_idx)
    if idx_foreign is None:
        idx_foreign = 4
        dq.append("T86_COLIDX_FALLBACK_FOREIGN")
    if idx_trust is None:
        idx_trust = 10
        dq.append("T86_COLIDX_FALLBACK_TRUST")
    if idx_dealer is None:
        idx_dealer = 11
        dq.append("T86_COLIDX_FALLBACK_DEALER")
    if idx_total3 is None:
        idx_total3 = 18
        dq.append("T86_COLIDX_FALLBACK_TOTAL3")

    out["col_idx"] = {"foreign": idx_foreign, "trust": idx_trust, "dealer": idx_dealer, "total3": idx_total3}

    foreign = _strip_commas_to_int(row[idx_foreign]) if idx_foreign < len(row) else None
    trust = _strip_commas_to_int(row[idx_trust]) if idx_trust < len(row) else None
    dealer = _strip_commas_to_int(row[idx_dealer]) if idx_dealer < len(row) else None
    total3 = _strip_commas_to_int(row[idx_total3]) if idx_total3 < len(row) else None

    if foreign is None:
        dq.append("T86_PARSE_FOREIGN_FAILED")
    if trust is None:
        dq.append("T86_PARSE_TRUST_FAILED")
    if dealer is None:
        dq.append("T86_PARSE_DEALER_FAILED")
    if total3 is None:
        dq.append("T86_PARSE_TOTAL3_FAILED")

    out["foreign_net_shares"] = foreign
    out["trust_net_shares"] = trust
    out["dealer_net_shares"] = dealer
    out["total3_net_shares"] = total3

    return out, dq


def _parse_twt72u(j: Dict[str, Any], stock_no: str) -> Tuple[Dict[str, Any], List[str]]:
    dq: List[str] = []
    out: Dict[str, Any] = {"dq": dq, "fields": []}

    if j is None or not isinstance(j, dict) or _twse_no_data(j):
        dq.append("TWT72U_EMPTY")
        return out, dq

    fields = safe_get(j, "fields", []) or []
    data_rows = safe_get(j, "data", []) or []

    out["fields"] = fields if isinstance(fields, list) else []
    row = _pick_row_by_stock(data_rows, stock_no)
    if row is None:
        dq.append("TWT72U_ROW_NOT_FOUND")
        return out, dq

    out["raw_row"] = row

    def idx_of(name: str) -> Optional[int]:
        try:
            return out["fields"].index(name)
        except Exception:
            return None

    idx_shares_end = idx_of("本日借券餘額股(4)=(1)+(2)-(3)")
    idx_close = idx_of("本日收盤價(5)單位：元")
    idx_mv = idx_of("借券餘額市值單位：元(6)=(4)*(5)")

    # fallback to your previous known mapping
    if idx_shares_end is None:
        idx_shares_end = 5
        dq.append("TWT72U_COLIDX_FALLBACK_SHARES_END")
    if idx_close is None:
        idx_close = 6
        dq.append("TWT72U_COLIDX_FALLBACK_CLOSE")
    if idx_mv is None:
        idx_mv = 7
        dq.append("TWT72U_COLIDX_FALLBACK_MV")

    out["col_idx"] = {"shares_end": idx_shares_end, "close": idx_close, "mv": idx_mv}

    borrow_shares = _strip_commas_to_int(row[idx_shares_end]) if idx_shares_end < len(row) else None
    close = _strip_commas_to_float(row[idx_close]) if idx_close < len(row) else None
    mv = _strip_commas_to_float(row[idx_mv]) if idx_mv < len(row) else None

    if borrow_shares is None:
        dq.append("TWT72U_PARSE_SHARES_FAILED")
    if close is None:
        dq.append("TWT72U_PARSE_CLOSE_FAILED")
    if mv is None:
        dq.append("TWT72U_PARSE_MV_FAILED")

    out["borrow_shares"] = borrow_shares
    out["borrow_mv_ntd"] = mv
    out["close"] = close

    return out, dq


def _parse_yuanta_pcf_units(html: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse from Yuanta PCF HTML text (no JS required):
      - Posting Date：2026-02-11 16:07:55
      - Total Outstanding Shares: 16,191,000,000
      - Net Change in Outstanding Shares: 44,000,000
      - Trade Date: 2026/02/11
    """
    dq: List[str] = []
    out: Dict[str, Any] = {"dq": dq}

    if not html or not isinstance(html, str):
        dq.append("ETF_UNITS_EMPTY_HTML")
        return out, dq

    # Normalize whitespace
    txt = re.sub(r"[ \t\r\f\v]+", " ", html)
    txt = re.sub(r"\n+", "\n", txt)

    # Posting Date (full-width colon '：' or ':')
    m_post = re.search(r"Posting Date[：:]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2})", txt)
    posting_iso = None
    if m_post:
        raw = m_post.group(1).strip()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ_TAIPEI)
            posting_iso = dt.isoformat()
        except Exception:
            dq.append("ETF_UNITS_PCF_POSTING_DATE_PARSE_FAILED")
    else:
        dq.append("ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND")

    # Trade Date (prefer explicit label)
    m_trade = re.search(r"Trade Date:\s*([0-9]{4}/[0-9]{2}/[0-9]{2})", txt)
    trade_ymd = None
    if m_trade:
        raw = m_trade.group(1).strip()
        trade_ymd = raw.replace("/", "")
    else:
        dq.append("ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND")

    # Outstanding
    m_out = re.search(r"Total Outstanding Shares\s*([\d,]+)", txt, flags=re.IGNORECASE)
    units_out = None
    if m_out:
        units_out = _strip_commas_to_int(m_out.group(1))
        if units_out is None:
            dq.append("ETF_UNITS_PCF_OUTSTANDING_PARSE_FAILED")
    else:
        dq.append("ETF_UNITS_PCF_OUTSTANDING_NOT_FOUND")

    # Net change
    m_chg = re.search(r"Net Change in Outstanding Shares\s*([\d,]+)", txt, flags=re.IGNORECASE)
    units_chg = None
    if m_chg:
        units_chg = _strip_commas_to_int(m_chg.group(1))
        if units_chg is None:
            dq.append("ETF_UNITS_PCF_NET_CHANGE_PARSE_FAILED")
    else:
        dq.append("ETF_UNITS_PCF_NET_CHANGE_NOT_FOUND")

    out["source"] = "yuanta_pcf"
    out["trade_date"] = trade_ymd
    out["posting_dt"] = posting_iso
    out["units_outstanding"] = units_out
    out["units_chg_1d"] = units_chg

    # if all key values missing -> treat as failed parse
    if (units_out is None) and (units_chg is None) and (trade_ymd is None) and (posting_iso is None):
        dq.append("ETF_UNITS_PCF_PARSE_ALL_MISSING")

    return out, dq


def _sum_int(values: List[Optional[int]]) -> int:
    s = 0
    for v in values:
        if v is None:
            continue
        try:
            s += int(v)
        except Exception:
            pass
    return s


def main() -> int:
    ap = argparse.ArgumentParser()

    # Make cache_dir optional to fix your workflow error.
    ap.add_argument("--cache_dir", default=None, help="Optional. If omitted, derived from --stats_path or --out.")
    ap.add_argument("--stats_path", required=True, help="Path to tw0050_bb_cache/stats_latest.json")
    ap.add_argument("--out", dest="out_path", required=False, default=None, help="Output json path")
    ap.add_argument("--out_path", dest="out_path2", required=False, default=None, help="Alias for --out")

    ap.add_argument("--stock_no", default="0050")
    ap.add_argument("--window_n", type=int, default=5)

    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff", type=float, default=1.5)

    ap.add_argument("--pcf_url", default=DEFAULT_PCF_URL)
    ap.add_argument("--disable_etf_units", action="store_true", help="Disable fetching ETF units from PCF page")

    args = ap.parse_args()

    stats_path = Path(args.stats_path)
    if not stats_path.exists():
        raise SystemExit(f"ERROR: stats_path not found: {stats_path}")

    # derive cache_dir if missing
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    if cache_dir is None:
        # prefer stats_path parent
        cache_dir = stats_path.parent

    # resolve output path
    out_path = args.out_path if args.out_path is not None else args.out_path2
    if out_path is None:
        out_path = str(cache_dir / "chip_overlay.json")
    out_path_p = Path(out_path)

    # load stats to get last_date for alignment
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    last_ymd = _parse_stats_last_date(stats)
    if not last_ymd:
        raise SystemExit("ERROR: cannot parse meta.last_date from stats_latest.json")

    cfg = HttpCfg(timeout=float(args.timeout), retries=int(args.retries), backoff=float(args.backoff))
    stock_no = str(args.stock_no).strip()
    window_n = int(args.window_n)

    # Build per_day list: walk backwards until we have >= window_n trading days with T86 rows.
    per_day: List[Dict[str, Any]] = []
    t86_valid_days: List[str] = []

    dt0 = _ymd_to_date(last_ymd)
    if dt0 is None:
        raise SystemExit(f"ERROR: cannot parse last_ymd={last_ymd}")

    MAX_LOOKBACK_DAYS = max(20, window_n * 6)  # handle long holidays
    for i in range(MAX_LOOKBACK_DAYS):
        dt = dt0 - timedelta(days=i)
        ymd = _date_to_ymd(dt)

        t86_url = T86_TPL.format(ymd=ymd)
        twt72u_url = TWT72U_TPL.format(ymd=ymd)

        day_obj: Dict[str, Any] = {
            "date": ymd,
            "dq": [],
            "sources": {"t86": t86_url, "twt72u": twt72u_url},
            "t86": {"dq": [], "fields": []},
            "twt72u": {"dq": [], "fields": []},
        }

        j86, _, err86 = _http_get_json(t86_url, cfg)
        j72, _, err72 = _http_get_json(twt72u_url, cfg)

        # Parse
        t86_parsed, dq86 = _parse_t86(j86, stock_no)
        t72_parsed, dq72 = _parse_twt72u(j72, stock_no)

        day_obj["t86"] = t86_parsed
        day_obj["twt72u"] = t72_parsed

        # If both endpoints have no usable data -> mark as non-trading/no-data
        t86_empty = ("T86_EMPTY" in dq86) or ("T86_ROW_NOT_FOUND" in dq86)
        t72_empty = ("TWT72U_EMPTY" in dq72) or ("TWT72U_ROW_NOT_FOUND" in dq72)

        if t86_empty and t72_empty:
            day_obj["dq"].append("NON_TRADING_OR_NO_DATA")
            # retain fetch errors if any
            if err86:
                day_obj["t86"]["dq"] = (day_obj["t86"].get("dq", []) or []) + [f"T86_FETCH:{err86}"]
            if err72:
                day_obj["twt72u"]["dq"] = (day_obj["twt72u"].get("dq", []) or []) + [f"TWT72U_FETCH:{err72}"]
        else:
            # track t86-valid trading days for aggregation
            if not t86_empty and (t86_parsed.get("foreign_net_shares") is not None):
                t86_valid_days.append(ymd)

        per_day.append(day_obj)

        # stop condition: enough t86-valid days collected AND we already included at least one extra day for borrow delta
        if len(t86_valid_days) >= window_n and len(per_day) >= window_n + 1:
            # still keep going a couple more days is unnecessary; stop.
            break

    # per_day currently newest->older (good, matches your existing json)
    # Prepare t86_agg over last window_n valid days (newest->older)
    used_days = t86_valid_days[:window_n]  # newest first
    used_days_set = set(used_days)

    sum_foreign: List[Optional[int]] = []
    sum_trust: List[Optional[int]] = []
    sum_dealer: List[Optional[int]] = []
    sum_total3: List[Optional[int]] = []

    for d in per_day:
        if d.get("date") not in used_days_set:
            continue
        t86 = d.get("t86", {}) or {}
        sum_foreign.append(t86.get("foreign_net_shares"))
        sum_trust.append(t86.get("trust_net_shares"))
        sum_dealer.append(t86.get("dealer_net_shares"))
        sum_total3.append(t86.get("total3_net_shares"))

    # days_used should be ascending (as in your sample)
    days_used_sorted = sorted(list(used_days), key=lambda x: x)

    t86_agg = {
        "window_n": window_n,
        "days_used": days_used_sorted,
        "foreign_net_shares_sum": _sum_int(sum_foreign),
        "trust_net_shares_sum": _sum_int(sum_trust),
        "dealer_net_shares_sum": _sum_int(sum_dealer),
        "total3_net_shares_sum": _sum_int(sum_total3),
    }

    # Borrow summary: use last_ymd (aligned day) and previous available borrow day for delta
    borrow_points: List[Tuple[str, Optional[int], Optional[float], Optional[float]]] = []
    for d in per_day:
        t72 = d.get("twt72u", {}) or {}
        bs = t72.get("borrow_shares")
        mv = t72.get("borrow_mv_ntd")
        close = t72.get("close")
        if bs is None and mv is None:
            continue
        borrow_points.append((d.get("date"), bs, mv, close))

    borrow_summary: Dict[str, Any] = {
        "asof_date": last_ymd,
        "borrow_shares": None,
        "borrow_shares_chg_1d": None,
        "borrow_mv_ntd": None,
        "borrow_mv_ntd_chg_1d": None,
    }

    # borrow_points is newest->older (aligned with per_day)
    # find asof entry
    asof_idx = None
    for i, (d_ymd, _, _, _) in enumerate(borrow_points):
        if d_ymd == last_ymd:
            asof_idx = i
            break

    global_dq_flags: List[str] = []

    if asof_idx is None:
        global_dq_flags.append("BORROW_ASOF_NOT_FOUND")
    else:
        d_ymd, bs, mv, _ = borrow_points[asof_idx]
        borrow_summary["asof_date"] = d_ymd
        borrow_summary["borrow_shares"] = bs
        borrow_summary["borrow_mv_ntd"] = mv

        # previous point for delta (1 trading step)
        if asof_idx + 1 < len(borrow_points):
            _, bs_prev, mv_prev, _ = borrow_points[asof_idx + 1]
            if (bs is not None) and (bs_prev is not None):
                borrow_summary["borrow_shares_chg_1d"] = int(bs) - int(bs_prev)
            else:
                global_dq_flags.append("BORROW_DELTA_SHARES_MISSING")
            if (mv is not None) and (mv_prev is not None):
                borrow_summary["borrow_mv_ntd_chg_1d"] = float(mv) - float(mv_prev)
            else:
                global_dq_flags.append("BORROW_DELTA_MV_MISSING")
        else:
            global_dq_flags.append("BORROW_PREV_DAY_NOT_FOUND")

    # ETF units (PCF)
    etf_units: Dict[str, Any] = {
        "source": "yuanta_pcf",
        "source_url": str(args.pcf_url),
        "trade_date": None,
        "posting_dt": None,
        "units_outstanding": None,
        "units_chg_1d": None,
        "dq": [],
    }

    if args.disable_etf_units:
        etf_units["dq"].append("ETF_UNITS_DISABLED")
        global_dq_flags.append("ETF_UNITS_DISABLED")
    else:
        html, status, err = _http_get_text(str(args.pcf_url), cfg)
        if html is None:
            etf_units["dq"].append("ETF_UNITS_FETCH_FAILED")
            etf_units["dq"].append(f"ETF_UNITS_FETCH_ERR:{err or 'unknown'}")
            if status is not None:
                etf_units["dq"].append(f"ETF_UNITS_FETCH_STATUS:{status}")
            global_dq_flags.append("ETF_UNITS_FETCH_FAILED")
        else:
            parsed, dq_units = _parse_yuanta_pcf_units(html)
            # merge into etf_units
            etf_units.update({k: parsed.get(k) for k in ["trade_date", "posting_dt", "units_outstanding", "units_chg_1d"]})
            etf_units["dq"] = list(dq_units or [])

            # global flag if key fields missing
            if (etf_units.get("units_outstanding") is None) or (etf_units.get("units_chg_1d") is None):
                global_dq_flags.append("ETF_UNITS_FETCH_FAILED")

    # aligned_last_date should be stats last date (ymd)
    aligned_last_date = last_ymd

    out = {
        "meta": {
            "run_ts_utc": utc_now_iso_msless(),
            "script_fingerprint": SCRIPT_FINGERPRINT,
            "stock_no": stock_no,
            "window_n": window_n,
            "timeout": float(args.timeout),
            "retries": int(args.retries),
            "backoff": float(args.backoff),
            "aligned_last_date": aligned_last_date,
        },
        "sources": {
            "t86_tpl": T86_TPL,
            "twt72u_tpl": TWT72U_TPL,
            "pcf_url": str(args.pcf_url),
        },
        "dq": {"flags": sorted(list(dict.fromkeys(global_dq_flags)))},
        "data": {
            "borrow_summary": borrow_summary,
            "etf_units": etf_units,
            "per_day": per_day,
            "t86_agg": t86_agg,
        },
    }

    out_path_p.parent.mkdir(parents=True, exist_ok=True)
    out_path_p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote: {out_path_p}")
    print("aligned_last_date:", aligned_last_date)
    print("dq.flags:", out["dq"]["flags"])
    print("etf_units:", {k: etf_units.get(k) for k in ["trade_date", "posting_dt", "units_outstanding", "units_chg_1d"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())