#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch TWSE official data and compute a *proxy* of "market margin maintenance ratio".

Proxy:
  maint_ratio_pct = ( Σ_i (fin_shares_i * close_i * 1000) / total_financing_amount_twd ) * 100

Notes:
- fin_shares_i uses MI_MARGN (融資今日餘額, 單位: 張)
- close_i uses MI_INDEX (fields9/data9 收盤價)
- total_financing_amount_twd uses MI_MARGN tfootData_two row '融資金額(仟元)' last numeric cell = 今日餘額 (仟元) -> *1000

Robustness:
- Retries with backoff (2s, 4s, 8s)
- Adds '_' timestamp param to reduce caching issues
- Adds Referer / Accept headers (TWSE sometimes needs browser-like headers)

Outputs:
- latest.json (always)
- history.json (upsert by data_date, if --history provided)
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Use exchangeReport endpoints (more common / consistent schema for JSON fields/data)
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
    # Add cache-buster
    params = dict(params)
    params["_"] = str(int(time.time() * 1000))

    for i, backoff in enumerate((2, 4, 8), start=1):
        try:
            r = session.get(url, params=params, headers=_twse_headers(referer), timeout=timeout)
            # Retry on typical throttling
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"http_{r.status_code}")
            r.raise_for_status()

            # Some endpoints occasionally prepend BOM or whitespace; json() usually handles it but keep safe:
            try:
                return r.json()
            except Exception:
                text = r.text.lstrip("\ufeff").strip()
                return json.loads(text)

        except Exception as e:
            last_err = f"try{i}:{type(e).__name__}:{e}"
            time.sleep(backoff)
    raise RuntimeError(last_err or "request_failed")

def extract_total_financing_amount_twd(margn: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """
    Prefer MI_MARGN root tfootData_two:
      - find row where row[0] contains '融資金額'
      - take last numeric cell as 今日餘額 (仟元) -> *1000
    """
    for key in ("tfootData_two", "tfootDataTwo", "tfootData"):
        v = margn.get(key)
        if isinstance(v, list) and v and isinstance(v[0], list):
            for row in v:
                if not row:
                    continue
                head = str(row[0])
                if "融資金額" in head:
                    nums = [parse_number(x) for x in row[1:]]
                    nums = [x for x in nums if x is not None]
                    if nums:
                        return int(round(nums[-1] * 1000)), f"from_root:{key}"

    # fallback: scan any key containing 'tfoot'
    for k, v in margn.items():
        if "tfoot" in str(k).lower() and isinstance(v, list) and v and isinstance(v[0], list):
            for row in v:
                if row and "融資金額" in str(row[0]):
                    nums = [parse_number(x) for x in row[1:]]
                    nums = [x for x in nums if x is not None]
                    if nums:
                        return int(round(nums[-1] * 1000)), f"from_root_scan:{k}"

    return None, "not_found"

def extract_financing_shares_by_code(margn: Dict[str, Any]) -> Tuple[Dict[str, int], str]:
    """
    MI_MARGN root has:
      - fields: [... '股票代號', ... '融資今日餘額', ...]
      - data: [[...], [...], ...]
    """
    fields = margn.get("fields")
    data = margn.get("data")
    if not isinstance(fields, list) or not isinstance(data, list):
        return {}, "fields_or_data_not_found"

    code_idx = None
    fin_today_idx = None

    for i, f in enumerate(fields):
        sf = str(f)
        if code_idx is None and (("股票代號" in sf) or ("證券代號" in sf)):
            code_idx = i
        if fin_today_idx is None and ("融資" in sf and "今日" in sf and "餘額" in sf):
            fin_today_idx = i

    if code_idx is None or fin_today_idx is None:
        return {}, "missing_cols_in_fields"

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
    MI_INDEX per-security after-hours table typically uses fields9/data9.
    We look for '證券代號' and '收盤價' in fields9.
    """
    fields = mi_index.get("fields9")
    data = mi_index.get("data9")
    if not isinstance(fields, list) or not isinstance(data, list):
        return {}, "fields9_or_data9_not_found"

    code_idx = None
    close_idx = None
    for i, f in enumerate(fields):
        sf = str(f)
        if code_idx is None and "證券代號" in sf:
            code_idx = i
        if close_idx is None and "收盤價" in sf:
            close_idx = i

    if code_idx is None or close_idx is None:
        return {}, "missing_cols_in_fields9"

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
    ap.add_argument("--date", help="YYYYMMDD (required unless --date-from).", default="")
    ap.add_argument("--date-from", help="Read date from an existing latest.json", default="")
    ap.add_argument("--out", required=True, help="Output latest.json path")
    ap.add_argument("--history", default="", help="Optional history.json path (upsert by data_date)")
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--exclude-non4", action="store_true", help="Exclude codes not 4 digits")
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
        "script_fingerprint": "fetch_twse_market_maint_ratio_py@v3_exchangeReport_fields9",
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

            # TWSE often returns {"stat":"OK"} / or "很抱歉..." messages
            stat = str(margn.get("stat") or "").upper()
            if stat and stat != "OK":
                raise RuntimeError(f"MI_MARGN_stat_not_ok:{margn.get('stat')}")

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

            stat2 = str(mi_index.get("stat") or "").upper()
            if stat2 and stat2 != "OK":
                raise RuntimeError(f"MI_INDEX_stat_not_ok:{mi_index.get('stat')}")

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

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())