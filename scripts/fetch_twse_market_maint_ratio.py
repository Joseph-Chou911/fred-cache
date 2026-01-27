#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch TWSE official data and compute a *proxy* of "market margin maintenance ratio".

Definition (proxy):
  maint_ratio_pct = ( Σ_i (fin_shares_i * close_i * 1000) / total_financing_amount_twd ) * 100

Where:
- fin_shares_i: financing balance shares (張) for security i, from TWSE MI_MARGN JSON
- close_i: closing price for security i, from TWSE MI_INDEX JSON
- total_financing_amount_twd: market total financing balance amount, from MI_MARGN footer (融資金額(仟元) 今日餘額)

This is a market-level proxy, NOT "per-account maintenance ratio".
It is still useful as a crowd leverage fragility gauge.

Outputs:
- latest.json (always)
- history.json (upsert by data_date, if --history provided)

Robustness:
- Retries with backoff (2s, 4s, 8s)
- If any critical parse fails => DOWNGRADED, keep nulls.

Notes:
- Endpoints are TWSE official pages (often referenced by data.gov.tw as open data resources).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TWSE_MI_MARGN = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
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

def request_json(url: str, params: Dict[str, str], timeout: int = 20) -> Dict[str, Any]:
    last_err: Optional[str] = None
    for i, backoff in enumerate((2, 4, 8), start=1):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = f"try{i}:{type(e).__name__}:{e}"
            time.sleep(backoff)
    raise RuntimeError(last_err or "request_failed")

def find_table_with_fields(tables: List[Dict[str, Any]], must_have: List[str]) -> Optional[Dict[str, Any]]:
    for t in tables:
        fields = t.get("fields") or []
        if not isinstance(fields, list):
            continue
        ok = True
        for key in must_have:
            if not any(key in str(f) for f in fields):
                ok = False
                break
        if ok:
            return t
    return None

def extract_total_financing_amount_twd(margn: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """
    Prefer tfootData_two row that starts with '融資金額(仟元)' and take its last numeric cell as '今日餘額'.
    Multiply by 1000 to convert 仟元 -> 元.
    """
    # 1) root-level keys
    for k, v in margn.items():
        if "tfoot" in str(k) and isinstance(v, list) and v and isinstance(v[0], list):
            for row in v:
                if not row:
                    continue
                head = str(row[0])
                if "融資金額" in head:
                    # last numeric cell is usually 今日餘額
                    nums = [parse_number(x) for x in row[1:]]
                    nums = [x for x in nums if x is not None]
                    if nums:
                        return int(round(nums[-1] * 1000)), f"from_root:{k}"
    # 2) inside tables
    tables = margn.get("tables") or []
    if isinstance(tables, list):
        for t in tables:
            for k, v in (t or {}).items():
                if "tfoot" in str(k) and isinstance(v, list) and v and isinstance(v[0], list):
                    for row in v:
                        if not row:
                            continue
                        head = str(row[0])
                        if "融資金額" in head:
                            nums = [parse_number(x) for x in row[1:]]
                            nums = [x for x in nums if x is not None]
                            if nums:
                                return int(round(nums[-1] * 1000)), f"from_table:{k}"
    return None, "not_found"

def extract_financing_shares_by_code(margn: Dict[str, Any]) -> Tuple[Dict[str, int], str]:
    """
    Extract per-security financing '今日餘額' (張).
    We look for a table containing '證券代號/股票代號' and '融資' + '今日餘額'.
    """
    tables = margn.get("tables") or []
    if not isinstance(tables, list):
        return {}, "tables_not_found"

    # Candidate tables: must have code and a financing-today-balance column.
    best: Optional[Dict[str, Any]] = None
    for t in tables:
        fields = t.get("fields") or []
        if not isinstance(fields, list):
            continue
        has_code = any(("證券代號" in str(f)) or ("股票代號" in str(f)) for f in fields)
        has_fin_today = any(("融資" in str(f) and "今日" in str(f) and "餘額" in str(f)) for f in fields)
        if has_code and has_fin_today:
            best = t
            break

    if best is None:
        return {}, "fin_table_not_found"

    fields = best.get("fields") or []
    data = best.get("data") or []
    if not isinstance(fields, list) or not isinstance(data, list):
        return {}, "fin_table_bad_shape"

    # locate columns
    code_idx = None
    fin_today_idx = None
    for i, f in enumerate(fields):
        sf = str(f)
        if code_idx is None and (("證券代號" in sf) or ("股票代號" in sf)):
            code_idx = i
        if fin_today_idx is None and ("融資" in sf and "今日" in sf and "餘額" in sf):
            fin_today_idx = i

    if code_idx is None or fin_today_idx is None:
        return {}, "fin_table_missing_cols"

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
    Look for a table with '證券代號' and '收盤價'.
    """
    tables = mi_index.get("tables") or []
    if not isinstance(tables, list):
        return {}, "tables_not_found"

    t = find_table_with_fields(tables, must_have=["證券代號", "收盤價"])
    if t is None:
        return {}, "price_table_not_found"

    fields = t.get("fields") or []
    data = t.get("data") or []
    if not isinstance(fields, list) or not isinstance(data, list):
        return {}, "price_table_bad_shape"

    code_idx = None
    close_idx = None
    for i, f in enumerate(fields):
        sf = str(f)
        if code_idx is None and "證券代號" in sf:
            code_idx = i
        if close_idx is None and "收盤價" in sf:
            close_idx = i
    if code_idx is None or close_idx is None:
        return {}, "price_table_missing_cols"

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

def load_date_from_latest(path: str) -> Optional[str]:
    """
    Try to read a YYYY-MM-DD (or YYYYMMDD) date from an existing latest.json (your margin cache).
    We accept common keys: data_date, date, UsedDate.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        return None

    for k in ("data_date", "date", "UsedDate", "used_date"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            s = v.strip()
            # normalize
            if re.fullmatch(r"\d{8}", s):
                return s
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                return s.replace("-", "")
    return None

def upsert_history(history_path: str, item: Dict[str, Any], max_items: int = 1200) -> None:
    data = {"schema_version": SCHEMA_HISTORY, "items": []}  # default
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass

    items = data.get("items")
    if not isinstance(items, list):
        items = []

    # upsert by data_date
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

    # sort by data_date asc if possible
    def key_fn(x: Dict[str, Any]) -> str:
        return str(x.get("data_date") or "")
    new_items = sorted([x for x in new_items if x.get("data_date")], key=key_fn)

    # cap
    if len(new_items) > max_items:
        new_items = new_items[-max_items:]

    data["schema_version"] = SCHEMA_HISTORY
    data["items"] = new_items

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD (preferred). If omitted, try --date-from.", default="")
    ap.add_argument("--date-from", help="Read date from an existing latest.json (data_date/date/UsedDate).", default="")
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
    if date_yyyymmdd and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_yyyymmdd):
        date_yyyymmdd = date_yyyymmdd.replace("-", "")

    latest: Dict[str, Any] = {
        "schema_version": SCHEMA_LATEST,
        "script_fingerprint": "fetch_twse_market_maint_ratio_py@v1",
        "generated_at_utc": gen_utc,
        "generated_at_local": gen_local,
        "timezone": args.tz,
        "source_urls": {
            "MI_MARGN": TWSE_MI_MARGN,
            "MI_INDEX": TWSE_MI_INDEX,
        },
        "params": {
            "date": date_yyyymmdd or None,
            "exclude_non4": bool(args.exclude_non4),
        },
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
        if not date_yyyymmdd or not re.fullmatch(r"\d{8}", date_yyyymmdd):
            raise ValueError("date_missing_or_invalid")

        # 1) Fetch margin summary + per-security financing shares
        margn = request_json(
            TWSE_MI_MARGN,
            params={"response": "json", "date": date_yyyymmdd, "selectType": "ALL"},
        )

        total_amt_twd, total_src = extract_total_financing_amount_twd(margn)
        fin_shares, fin_src = extract_financing_shares_by_code(margn)

        if total_amt_twd is None:
            raise RuntimeError(f"total_financing_amount_not_found:{total_src}")
        if not fin_shares:
            raise RuntimeError(f"financing_shares_not_found:{fin_src}")

        # optional filtering
        if args.exclude_non4:
            fin_shares = {k: v for k, v in fin_shares.items() if re.fullmatch(r"\d{4}", k)}

        # 2) Fetch close prices
        mi_index = request_json(
            TWSE_MI_INDEX,
            params={"response": "json", "date": date_yyyymmdd, "type": "ALLBUT0999"},
        )
        close_by_code, px_src = extract_close_by_code(mi_index)
        if not close_by_code:
            raise RuntimeError(f"close_prices_not_found:{px_src}")

        # 3) Compute collateral value
        total_collateral = 0.0
        missing_px = 0
        included = 0
        for code, shares in fin_shares.items():
            px = close_by_code.get(code)
            if px is None:
                missing_px += 1
                continue
            # shares are 張, assume 1 張 = 1000 股
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
        latest["maint_ratio_pct"] = round(float(maint), 4)
        latest["included_count"] = int(included)
        latest["missing_price_count"] = int(missing_px)
        latest["notes"].append(f"total_financing_amount: {total_src}")
        latest["notes"].append(f"fin_shares: {fin_src}")
        latest["notes"].append(f"close_prices: {px_src}")

        # history upsert
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

    # write latest.json always
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())