#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch TWSE official data and compute a *proxy* of "market margin maintenance ratio".

Proxy definition:
  maint_ratio_pct = ( Σ_i (fin_shares_i * close_i * 1000) / total_financing_amount_twd ) * 100

- fin_shares_i: financing balance shares (張) for security i, from TWSE MI_MARGN JSON
- close_i: closing price for security i, from TWSE MI_INDEX JSON
- total_financing_amount_twd: market total financing balance amount.

v6 hardening (vs v5):
- Prevent mis-picking "融券 今日餘額" when MI_MARGN fields do NOT explicitly say '融資'.
  Strategy:
  1) Prefer column whose field text contains ('融資' AND '餘額') (+bonus for '今日')
  2) If not found, detect *two repeated groups* of trading/balance columns in the same table
     (融資 group then 融券 group), and pick the first group's '今日餘額' column.
     We locate group boundaries by repeated patterns like 買進/賣出/現金(或現券)償還/前日餘額/今日餘額.
  3) If still ambiguous, fallback to the first '今日餘額' occurrence, but mark confidence DOWNGRADED.

- Keep audit-friendly notes:
  - table titles + fields previews
  - fin_pick_method + chosen indices

Other robustness:
- Retries with backoff (2s, 4s, 8s)
- Adds cache-buster '_' (ms timestamp)
- Adds browser-like headers + Referer
- Checks 'stat' != 'OK' early

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
    # S1: preferred root keys
    for key in ("tfootData_two", "tfootDataTwo", "tfootData"):
        v = margn.get(key)
        if _is_list_of_lists(v):
            got = _scan_rows_for_total(v)  # type: ignore[arg-type]
            if got:
                val, why = got
                return val, f"S1_root:{key}:{why}"

    # S2/S3: tables
    tables = margn.get("tables")
    if isinstance(tables, list):
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

            # S3: any list-of-lists inside table (including 'data')
            for k, v in t.items():
                if _is_list_of_lists(v):
                    got = _scan_rows_for_total(v)  # type: ignore[arg-type]
                    if got:
                        val, why = got
                        return val, f"S3_{prefix}:{k}:{why}"

    # S4: deep scan
    for path, block in _deep_iter_list_of_lists(margn):
        got = _scan_rows_for_total(block)
        if got:
            val, why = got
            return val, f"S4_deep:{path}:{why}"

    return None, "not_found"

def _norm_field(x: Any) -> str:
    s = str(x)
    s = re.sub(r"\s+", "", s)
    s = s.replace("\u3000", "")
    s = re.sub(r"[()（）\[\]【】<>《》:：/／\-—_]", "", s)
    return s

def _find_all_indices(fields_norm: List[str], token: str) -> List[int]:
    return [i for i, f in enumerate(fields_norm) if token in f]

def _find_repeated_group_bounds(fields_norm: List[str]) -> Optional[Tuple[int, int]]:
    """
    Try to detect that this table contains two groups (融資 then 融券) by finding a second occurrence
    of a common group-start token among: 買進,賣出,前日餘額,今日餘額,償還.
    Return (group1_start, group2_start) indices if found.
    """
    # group-start candidates that often appear at both groups
    starts = ["買進", "賣出", "前日餘額", "今日餘額"]
    cand_positions: List[int] = []

    # find repeated occurrences for each token; keep the 2nd occurrence as possible group2 start
    for tok in starts:
        idxs = _find_all_indices(fields_norm, tok)
        if len(idxs) >= 2:
            cand_positions.append(idxs[1])

    if not cand_positions:
        return None

    group2_start = min(cand_positions)

    # group1 start: the first occurrence among the same tokens
    group1_positions: List[int] = []
    for tok in starts:
        idxs = _find_all_indices(fields_norm, tok)
        if idxs:
            group1_positions.append(idxs[0])
    if not group1_positions:
        return None
    group1_start = min(group1_positions)

    # sanity: group2_start should be after group1_start by at least a few columns
    if group2_start <= group1_start + 2:
        return None

    return group1_start, group2_start

def _pick_fin_today_idx(fields: List[Any]) -> Tuple[Optional[int], str, bool]:
    """
    Pick financing-balance column index.

    Returns (fin_idx, method, is_confident)

    method:
      - explicit_finz: found ('融資' AND '餘額') column
      - grouped_first_today: inferred two groups; pick first group's 今日餘額
      - fallback_first_today: pick first 今日餘額; low confidence
    """
    fn = [_norm_field(f) for f in fields]

    # 1) explicit融資餘額 preferred
    best_i = None
    best_score = -1
    for i, sf in enumerate(fn):
        if ("融資" in sf) and ("餘額" in sf):
            score = 10
            if "今日" in sf:
                score += 5
            if "張" in sf:
                score += 1
            if score > best_score:
                best_score = score
                best_i = i
    if best_i is not None:
        return best_i, "explicit_finz", True

    # 2) group inference: pick first group's 今日餘額
    bounds = _find_repeated_group_bounds(fn)
    if bounds is not None:
        group1_start, group2_start = bounds
        # find 今日餘額 within [group1_start, group2_start)
        for i in range(group1_start, group2_start):
            if "今日餘額" in fn[i] or fn[i] == "今日餘額":
                return i, f"grouped_first_today:g1={group1_start},g2={group2_start}", True
        # if no exact 今日餘額, allow '餘額' with 今日 keyword
        for i in range(group1_start, group2_start):
            if ("今日" in fn[i]) and ("餘額" in fn[i]):
                return i, f"grouped_first_today_loose:g1={group1_start},g2={group2_start}", True

    # 3) fallback: first 今日餘額 occurrence (low confidence)
    for i, sf in enumerate(fn):
        if "今日餘額" in sf:
            return i, "fallback_first_today", False

    return None, "not_found", False

def _pick_code_idx(fields: List[Any]) -> Optional[int]:
    fn = [_norm_field(f) for f in fields]
    for i, sf in enumerate(fn):
        if "證券代號" in sf or "股票代號" in sf:
            return i
    for i, sf in enumerate(fn):
        if "代號" in sf:
            return i
    return None

def _extract_fin_shares_from_fields_data(fields: List[Any], data: List[Any]) -> Tuple[Dict[str, int], str, bool]:
    code_idx = _pick_code_idx(fields)
    fin_idx, method, confident = _pick_fin_today_idx(fields)

    if code_idx is None or fin_idx is None:
        return {}, f"missing_cols:code_idx={code_idx},fin_idx={fin_idx},method={method}", False

    out: Dict[str, int] = {}
    for row in data:
        if not isinstance(row, list) or len(row) <= max(code_idx, fin_idx):
            continue
        code = str(row[code_idx]).strip()
        if not code or code in ("合計", "總計", "說明"):
            continue
        shares = parse_int(row[fin_idx])
        if shares is None:
            continue
        out[code] = shares

    return out, f"ok:code_idx={code_idx},fin_idx={fin_idx},method={method}", confident

def extract_financing_shares_by_code(margn: Dict[str, Any], debug_notes: List[str]) -> Tuple[Dict[str, int], str, bool]:
    """
    Extract per-security financing '今日餘額' (張).

    Returns (map, status, confident)
    """
    # A) root
    fields = margn.get("fields")
    data = margn.get("data")
    if isinstance(fields, list) and isinstance(data, list):
        out, status, conf = _extract_fin_shares_from_fields_data(fields, data)
        if out:
            return out, f"root:{status}", conf

    # B) tables
    tables = margn.get("tables")
    if isinstance(tables, list):
        for ti, t in enumerate(tables):
            if not isinstance(t, dict):
                continue
            title = str(t.get("title") or "")
            fields = t.get("fields")
            data = t.get("data")

            if isinstance(fields, list):
                preview = ",".join(_norm_field(x) for x in fields[:12])
                debug_notes.append(f"margn_table[{ti}]_title={title or 'NA'}")
                debug_notes.append(f"margn_table[{ti}]_fields_preview={preview}")

            if isinstance(fields, list) and isinstance(data, list):
                out, status, conf = _extract_fin_shares_from_fields_data(fields, data)
                if out:
                    return out, f"table[{ti}]:{title}:{status}" if title else f"table[{ti}]:{status}", conf

    return {}, "fin_table_not_found", False

def extract_close_by_code(mi_index: Dict[str, Any], debug_notes: List[str]) -> Tuple[Dict[str, float], str]:
    # prefer fields9/data9
    fields9 = mi_index.get("fields9")
    data9 = mi_index.get("data9")
    if isinstance(fields9, list) and isinstance(data9, list):
        out, status = _extract_close_from_fields_data(fields9, data9, code_key="證券代號", close_key="收盤價")
        if out:
            return out, f"fields9:{status}"

    # fallback tables
    tables = mi_index.get("tables")
    if isinstance(tables, list):
        for ti, t in enumerate(tables[:3]):
            if isinstance(t, dict) and isinstance(t.get("fields"), list):
                title = str(t.get("title") or "")
                preview = ",".join(_norm_field(x) for x in t["fields"][:12])
                debug_notes.append(f"mi_index_table[{ti}]_title={title or 'NA'}")
                debug_notes.append(f"mi_index_table[{ti}]_fields_preview={preview}")

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
    fn = [_norm_field(f) for f in fields]
    for i, sf in enumerate(fn):
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
        "script_fingerprint": "fetch_twse_market_maint_ratio_py@v6_guard_short_table_grouping",
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
            if total_amt_twd is None:
                raise RuntimeError(f"total_financing_amount_not_found:{total_src}")

            fin_shares, fin_src, fin_conf = extract_financing_shares_by_code(margn, latest["notes"])
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

            close_by_code, px_src = extract_close_by_code(mi_index, latest["notes"])
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
        # confidence downgraded if financing column pick relied on weak fallback
        latest["confidence"] = "OK" if fin_conf else "DOWNGRADED"
        latest["dq_reason"] = "" if fin_conf else "fin_col_pick_low_confidence"
        latest["data_date"] = f"{date_yyyymmdd[0:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
        latest["total_financing_amount_twd"] = int(total_amt_twd)
        latest["total_collateral_value_twd"] = int(round(total_collateral))
        latest["maint_ratio_pct"] = round(float(maint), 6)
        latest["included_count"] = int(included)
        latest["missing_price_count"] = int(missing_px)
        latest["notes"].append(f"total_financing_amount: {total_src}")
        latest["notes"].append(f"fin_shares: {fin_src}")
        latest["notes"].append(f"fin_pick_confident: {bool(fin_conf)}")
        latest["notes"].append(f"close_prices: {px_src}")

        if args.history.strip():
            hist_item = {
                "data_date": latest["data_date"],
                "maint_ratio_pct": latest["maint_ratio_pct"],
                "total_financing_amount_twd": latest["total_financing_amount_twd"],
                "total_collateral_value_twd": latest["total_collateral_value_twd"],
                "included_count": latest["included_count"],
                "missing_price_count": latest["missing_price_count"],
                "confidence": latest["confidence"],
                "dq_reason": latest["dq_reason"],
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