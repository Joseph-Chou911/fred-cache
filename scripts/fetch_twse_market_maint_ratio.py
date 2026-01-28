#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch TWSE official data and compute a *proxy* of "market margin maintenance ratio".

Proxy definition:
  maint_ratio_pct = ( Σ_i (fin_shares_i * close_i * 1000) / total_financing_amount_twd ) * 100

- fin_shares_i: financing balance shares (張) for security i, from TWSE MI_MARGN JSON
- close_i: closing price for security i, from TWSE MI_INDEX JSON
- total_financing_amount_twd: market total financing balance amount.

IMPORTANT FIX (v4):
TWSE MI_MARGN sometimes returns ONLY:
  { "date": "...", "stat": "OK", "tables": [...] }

and the market total "融資金額(仟元) 今日餘額" may appear NOT in tfootData_two,
but inside a *summary table's data rows* (e.g., row label "融資金額(仟元)").

So this script extracts total financing amount via multiple strategies:
  S1) root footer keys: tfootData_two / tfootData...
  S2) scan each table's footer-like keys (any key containing 'tfoot')
  S3) scan each table's list-of-lists blocks (including 'data') for a row starting with '融資金額'
  S4) deep-scan the whole response for any list-of-lists row starting with '融資金額'

Outputs:
- latest.json (always)
- history.json (upsert by data_date, if --history provided)

Robustness:
- Retries with backoff (2s, 4s, 8s)
- Adds cache-buster '_' (ms timestamp)
- Adds browser-like headers + Referer
- Checks 'stat' != 'OK' early (holiday / not published / throttled message)

Date sourcing:
- --date YYYYMMDD takes priority.
- else --date-from JSON path:
  - try top-level: data_date / date / UsedDate / used_date
  - then try: series.TWSE.data_date
  - then try: series.TWSE.rows[0].date
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Iterable

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TWSE_MI_MARGN = "https://www.twse.com.tw/exchangeReport/MI_MARGN"
TWSE_MI_INDEX = "https://www.twse.com.tw/exchangeReport/MI_INDEX"

SCHEMA_LATEST = "tw_market_maint_ratio_latest_v1"
SCHEMA_HISTORY = "tw_market_maint_ratio_history_v1"

NUM_RE = re.compile(r"-?\d+(?:,\d+)*(?:\.\d+)?")

def now_ts(tz: ZoneInfo) -> Tuple[str, str]:
    dt_utc = datetime.now(timezone.utc)
    dt_local = dt_utc.astimezone(tz)
    return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"), dt_local.isoformat()

def parse_number(s: Any) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    text = str(s).strip()
    if text in ("", "--", "NA", "N/A", "null", "None"):
        return None
    m = NUM_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except Exception:
        return None

def parse_int(s: Any) -> Optional[int]:
    x = parse_number(s)
    if x is None:
        return None
    try:
        return int(round(x))
    except Exception:
        return None

def normalize_date_to_yyyymmdd(s: str) -> Optional[str]:
    ss = s.strip()
    if re.fullmatch(r"\d{8}", ss):
        return ss
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ss):
        return ss.replace("-", "")
    return None

def load_date_from_latest(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        return None

    for k in ("data_date", "date", "UsedDate", "used_date"):
        v = obj.get(k)
        if isinstance(v, str):
            dd = normalize_date_to_yyyymmdd(v)
            if dd:
                return dd

    try:
        v = obj.get("series", {}).get("TWSE", {}).get("data_date")
        if isinstance(v, str):
            dd = normalize_date_to_yyyymmdd(v)
            if dd:
                return dd
    except Exception:
        pass

    try:
        rows = obj.get("series", {}).get("TWSE", {}).get("rows", [])
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            v = rows[0].get("date")
            if isinstance(v, str):
                dd = normalize_date_to_yyyymmdd(v)
                if dd:
                    return dd
    except Exception:
        pass

    return None

def _twse_headers(referer: str) -> Dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": referer,
        "Connection": "keep-alive",
    }

def request_json(session: requests.Session, url: str, params: Dict[str, str], referer: str, timeout: int = 30) -> Dict[str, Any]:
    last_err: Optional[str] = None
    p = dict(params)
    p["_"] = str(int(time.time() * 1000))  # cache buster

    for i, backoff in enumerate((2, 4, 8), start=1):
        try:
            r = session.get(url, params=p, headers=_twse_headers(referer), timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"http_{r.status_code}")
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                text = r.text.lstrip("\ufeff").strip()
                return json.loads(text)
        except Exception as e:
            last_err = f"try{i}:{type(e).__name__}:{e}"
            time.sleep(backoff)
    raise RuntimeError(last_err or "request_failed")

def _stat_guard(obj: Dict[str, Any], name: str) -> None:
    stat = obj.get("stat")
    if stat is None:
        return
    s = str(stat).strip()
    if s.upper() != "OK":
        raise RuntimeError(f"{name}_stat_not_ok:{s}")

def _is_list_of_lists(v: Any) -> bool:
    return isinstance(v, list) and (len(v) == 0 or all(isinstance(x, list) for x in v))

def _scan_rows_for_total(row_block: List[List[Any]]) -> Optional[Tuple[int, str]]:
    """
    Look for a row where row[0] contains '融資金額' and return last numeric cell (仟元) converted to 元.
    """
    for row in row_block:
        if not row:
            continue
        head = str(row[0]).strip()
        if "融資金額" in head:
            nums = [parse_number(x) for x in row[1:]]
            nums = [x for x in nums if x is not None]
            if nums:
                return int(round(nums[-1] * 1000)), "row_label_match"
    return None

def _deep_iter_list_of_lists(obj: Any) -> Iterable[Tuple[str, List[List[Any]]]]:
    """
    Yield (path, block) for any list-of-lists found inside nested dict/list structures.
    """
    stack: List[Tuple[str, Any]] = [("$", obj)]
    while stack:
        path, cur = stack.pop()
        if _is_list_of_lists(cur):
            yield path, cur  # type: ignore[arg-type]
            continue
        if isinstance(cur, dict):
            for k, v in cur.items():
                stack.append((f"{path}.{k}", v))
        elif isinstance(cur, list):
            for i, v in enumerate(cur):
                stack.append((f"{path}[{i}]", v))

def extract_total_financing_amount_twd(margn: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """
    Multi-strategy extraction for market total financing amount (元).

    S1) root footer keys: tfootData_two / tfootDataTwo / tfootData
    S2) scan each table's footer-like keys containing 'tfoot'
    S3) scan each table's list-of-lists blocks (including 'data') for a row label '融資金額'
    S4) deep scan full response for any list-of-lists row label '融資金額'
    """
    # S1: preferred root keys
    for key in ("tfootData_two", "tfootDataTwo", "tfootData"):
        v = margn.get(key)
        if _is_list_of_lists(v):
            got = _scan_rows_for_total(v)  # type: ignore[arg-type]
            if got:
                val, why = got
                return val, f"S1_root:{key}:{why}"

    # tables
    tables = margn.get("tables")
    if isinstance(tables, list):
        # S2/S3: per-table scan
        for ti, t in enumerate(tables):
            if not isinstance(t, dict):
                continue
            title = str(t.get("title") or "")
            prefix = f"table[{ti}]" + (f":{title}" if title else "")

            # S2: footer-like keys
            for k, v in t.items():
                if "tfoot" in str(k).lower() and _is_list_of_lists(v):
                    got = _scan_rows_for_total(v)  # type: ignore[arg-type]
                    if got:
                        val, why = got
                        return val, f"S2_{prefix}:{k}:{why}"

            # S3: scan all list-of-lists blocks inside this table (including data)
            for k, v in t.items():
                if _is_list_of_lists(v):
                    got = _scan_rows_for_total(v)  # type: ignore[arg-type]
                    if got:
                        val, why = got
                        return val, f"S3_{prefix}:{k}:{why}"

    # S4: deep scan full response (last resort)
    for path, block in _deep_iter_list_of_lists(margn):
        got = _scan_rows_for_total(block)
        if got:
            val, why = got
            return val, f"S4_deep:{path}:{why}"

    return None, "not_found"

def extract_financing_shares_by_code(margn: Dict[str, Any]) -> Tuple[Dict[str, int], str]:
    """
    Extract per-security financing '今日餘額' (張).

    Supports:
    - exchangeReport root-level fields/data
    - tables[*].fields/data
    """
    fields = margn.get("fields")
    data = margn.get("data")
    if isinstance(fields, list) and isinstance(data, list):
        out, status = _extract_fin_shares_from_fields_data(fields, data)
        if out:
            return out, f"root:{status}"

    tables = margn.get("tables") or []
    if isinstance(tables, list):
        for t in tables:
            if not isinstance(t, dict):
                continue
            fields = t.get("fields")
            data = t.get("data")
            if isinstance(fields, list) and isinstance(data, list):
                out, status = _extract_fin_shares_from_fields_data(fields, data)
                if out:
                    title = str(t.get("title") or "")
                    return out, f"table:{title}:{status}" if title else f"table:{status}"

    return {}, "fin_table_not_found"

def _extract_fin_shares_from_fields_data(fields: List[Any], data: List[Any]) -> Tuple[Dict[str, int], str]:
    code_idx = None
    fin_today_idx = None
    for i, f in enumerate(fields):
        sf = str(f)
        if code_idx is None and (("股票代號" in sf) or ("證券代號" in sf)):
            code_idx = i
        if fin_today_idx is None and ("融資" in sf and "今日" in sf and "餘額" in sf):
            fin_today_idx = i

    if code_idx is None or fin_today_idx is None:
        return {}, "missing_cols"

    out: Dict[str, int] = {}
    for row in data:
        if not isinstance(row, list) or len(row) <= max(code_idx, fin_today_idx):
            continue
        code = str(row[code_idx]).strip()
        if not code or code in ("合計", "總計", "說明"):
            continue
        shares = parse_int(row[fin_today_idx])
        if shares is None:
            continue
        out[code] = shares

    return out, "ok"

def extract_close_by_code(mi_index: Dict[str, Any]) -> Tuple[Dict[str, float], str]:
    """
    Extract per-security close price from MI_INDEX JSON.

    Prefer:
    - exchangeReport: fields9/data9 contains '證券代號','收盤價'
    Fallback:
    - tables[*] with fields containing '證券代號' + '收盤價'
    """
    fields9 = mi_index.get("fields9")
    data9 = mi_index.get("data9")
    if isinstance(fields9, list) and isinstance(data9, list):
        out, status = _extract_close_from_fields_data(fields9, data9, code_key="證券代號", close_key="收盤價")
        if out:
            return out, f"fields9:{status}"

    tables = mi_index.get("tables") or []
    if isinstance(tables, list):
        for t in tables:
            if not isinstance(t, dict):
                continue
            fields = t.get("fields")
            data = t.get("data")
            if isinstance(fields, list) and isinstance(data, list):
                out, status = _extract_close_from_fields_data(fields, data, code_key="證券代號", close_key="收盤價")
                if out:
                    title = str(t.get("title") or "")
                    return out, f"table:{title}:{status}" if title else f"table:{status}"

    return {}, "price_table_not_found"

def _extract_close_from_fields_data(fields: List[Any], data: List[Any], code_key: str, close_key: str) -> Tuple[Dict[str, float], str]:
    code_idx = None
    close_idx = None
    for i, f in enumerate(fields):
        sf = str(f)
        if code_idx is None and code_key in sf:
            code_idx = i
        if close_idx is None and close_key in sf:
            close_idx = i

    if code_idx is None or close_idx is None:
        return {}, "missing_cols"

    out: Dict[str, float] = {}
    for row in data:
        if not isinstance(row, list) or len(row) <= max(code_idx, close_idx):
            continue
        code = str(row[code_idx]).strip()
        if not code:
            continue
        close = parse_number(row[close_idx])
        if close is None:
            continue
        out[code] = float(close)

    return out, "ok"

def upsert_history(history_path: str, item: Dict[str, Any], max_items: int = 1200) -> None:
    data = {"schema_version": SCHEMA_HISTORY, "items": []}
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass

    items = data.get("items")
    if not isinstance(items, list):
        items = []

    dd = item.get("data_date")
    new_items: List[Dict[str, Any]] = []
    replaced = False
    for it in items:
        if isinstance(it, dict) and it.get("data_date") == dd:
            new_items.append(item)
            replaced = True
        else:
            new_items.append(it if isinstance(it, dict) else {})
    if not replaced:
        new_items.append(item)

    new_items = sorted([x for x in new_items if x.get("data_date")], key=lambda x: str(x.get("data_date") or ""))
    if len(new_items) > max_items:
        new_items = new_items[-max_items:]

    data["schema_version"] = SCHEMA_HISTORY
    data["items"] = new_items

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD (preferred). If omitted, try --date-from.", default="")
    ap.add_argument("--date-from", help="Read date from an existing latest.json", default="")
    ap.add_argument("--out", required=True, help="Output latest.json path")
    ap.add_argument("--history", default="", help="Optional history.json path (upsert by data_date)")
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--exclude-non4", action="store_true", help="Exclude codes not 4 digits (roughly filter ETFs/others)")
    ap.add_argument("--max-history", type=int, default=1200)
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    gen_utc, gen_local = now_ts(tz)

    date_yyyymmdd = args.date.strip()
    if not date_yyyymmdd and args.date_from.strip():
        date_yyyymmdd = load_date_from_latest(args.date_from.strip()) or ""
    date_yyyymmdd = normalize_date_to_yyyymmdd(date_yyyymmdd) or ""

    latest: Dict[str, Any] = {
        "schema_version": SCHEMA_LATEST,
        "script_fingerprint": "fetch_twse_market_maint_ratio_py@v4_total_from_table_rows",
        "generated_at_utc": gen_utc,
        "generated_at_local": gen_local,
        "timezone": args.tz,
        "source_urls": {"MI_MARGN": TWSE_MI_MARGN, "MI_INDEX": TWSE_MI_INDEX},
        "params": {"date": date_yyyymmdd or None, "exclude_non4": bool(args.exclude_non4)},
        "fetch_status": "DOWNGRADED",
        "confidence": "DOWNGRADED",
        "dq_reason": "init",
        "data_date": None,
        "total_financing_amount_twd": None,
        "total_collateral_value_twd": None,
        "maint_ratio_pct": None,
        "included_count": 0,
        "missing_price_count": None,
        "notes": [],
        "error": None,
    }

    margn: Optional[Dict[str, Any]] = None
    mi_index: Optional[Dict[str, Any]] = None

    try:
        if not date_yyyymmdd:
            raise ValueError("date_missing_or_invalid")

        with requests.Session() as s:
            # 1) MI_MARGN
            margn = request_json(
                s,
                TWSE_MI_MARGN,
                params={"response": "json", "date": date_yyyymmdd, "selectType": "ALL"},
                referer="https://www.twse.com.tw/zh/trading/margin/mi-margn.html",
            )
            _stat_guard(margn, "MI_MARGN")

            total_amt_twd, total_src = extract_total_financing_amount_twd(margn)
            fin_shares, fin_src = extract_financing_shares_by_code(margn)

            if total_amt_twd is None:
                raise RuntimeError(f"total_financing_amount_not_found:{total_src}")
            if not fin_shares:
                raise RuntimeError(f"financing_shares_not_found:{fin_src}")

            if args.exclude_non4:
                fin_shares = {k: v for k, v in fin_shares.items() if re.fullmatch(r"\d{4}", k)}

            # 2) MI_INDEX
            mi_index = request_json(
                s,
                TWSE_MI_INDEX,
                params={"response": "json", "date": date_yyyymmdd, "type": "ALLBUT0999"},
                referer="https://www.twse.com.tw/zh/trading/historical/mi-index.html",
            )
            _stat_guard(mi_index, "MI_INDEX")

            close_by_code, px_src = extract_close_by_code(mi_index)
            if not close_by_code:
                raise RuntimeError(f"close_prices_not_found:{px_src}")

            # 3) Merge + compute
            total_collateral = 0.0
            missing_px = 0
            included = 0
            for code, shares in fin_shares.items():
                px = close_by_code.get(code)
                if px is None:
                    missing_px += 1
                    continue
                total_collateral += float(shares) * float(px) * 1000.0
                included += 1

            if included == 0:
                raise RuntimeError("all_prices_missing_after_merge")

            maint = (total_collateral / float(total_amt_twd)) * 100.0

        latest["fetch_status"] = "OK"
        latest["confidence"] = "OK"
        latest["dq_reason"] = ""
        latest["data_date"] = f"{date_yyyymmdd[0:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
        latest["total_financing_amount_twd"] = int(total_amt_twd)
        latest["total_collateral_value_twd"] = int(round(total_collateral))
        latest["maint_ratio_pct"] = round(float(maint), 6)
        latest["included_count"] = int(included)
        latest["missing_price_count"] = int(missing_px)
        latest["notes"].append(f"total_financing_amount: {total_src}")
        latest["notes"].append(f"fin_shares: {fin_src}")
        latest["notes"].append(f"close_prices: {px_src}")

        if args.history.strip():
            hist_item = {
                "data_date": latest["data_date"],
                "maint_ratio_pct": latest["maint_ratio_pct"],
                "total_financing_amount_twd": latest["total_financing_amount_twd"],
                "total_collateral_value_twd": latest["total_collateral_value_twd"],
                "included_count": latest["included_count"],
                "missing_price_count": latest["missing_price_count"],
                "generated_at_utc": gen_utc,
            }
            upsert_history(args.history.strip(), hist_item, max_items=int(args.max_history))

    except Exception as e:
        latest["error"] = str(e)
        latest["dq_reason"] = "fetch_or_parse_failed"
        try:
            if isinstance(margn, dict):
                latest["notes"].append("margn_keys=" + ",".join(sorted(list(margn.keys()))))
                latest["notes"].append("margn_stat=" + str(margn.get("stat")))
                # add count of tables to help audit
                tb = margn.get("tables")
                if isinstance(tb, list):
                    latest["notes"].append(f"margn_tables_n={len(tb)}")
            if isinstance(mi_index, dict):
                latest["notes"].append("mi_index_keys=" + ",".join(sorted(list(mi_index.keys()))))
                latest["notes"].append("mi_index_stat=" + str(mi_index.get("stat")))
        except Exception:
            pass

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())