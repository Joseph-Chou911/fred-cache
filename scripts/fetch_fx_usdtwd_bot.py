#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from BOT.

Primary:
- BOT xrt HTML page (zh-TW) parsed via "windowed" regex on flattened text.

Fallback:
- BOT CSV endpoint (L3M/USD/1) parsed by headers (即期買入/即期賣出).

Key guarantees:
- 1 request per attempt; will do up to 2 attempts (primary + fallback).
- Require data_date + spot_buy + spot_sell + spot_sell >= spot_buy.
- Dynamic sanity range to block wrong-currency capture (e.g., HKD~4.x).
  Range is derived from recent history median, with guardrails.
- latest.json always written (even on failure); history.json only updated on strict_ok.

Outputs:
- fx_cache/latest.json
- fx_cache/history.json (upsert by date)

Backward compatible args:
- --tz, --max-back accepted (max-back ignored)

Notes:
- quote_time_local is parsed from HTML when available; for CSV fallback it's usually None.
"""

from __future__ import annotations

import argparse
import csv
import html as htmllib
import json
import os
import re
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BOT_XRT_PAGE = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
BOT_CSV_L3M_USD = "https://rate.bot.com.tw/xrt/flcsv/0/L3M/USD/1"

# Dynamic sanity settings
SANITY_LOOKBACK_N = 120          # recent history points used
SANITY_MIN_POINTS = 20           # minimum points to enable dynamic range
SANITY_FACTOR_LOW = 0.60         # lower bound = median * factor
SANITY_FACTOR_HIGH = 1.60        # upper bound = median * factor
SANITY_GUARD_MIN = 10.0          # hard guard minimum (very wide)
SANITY_GUARD_MAX = 80.0          # hard guard maximum (very wide)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _dump_json(path: str, obj: Any) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x.replace(",", ""))
    except Exception:
        return None


def _load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": "fx_usdtwd_history_v1", "items": []}
    try:
        obj = _load_json(path)
        if (
            isinstance(obj, dict)
            and obj.get("schema_version") == "fx_usdtwd_history_v1"
            and isinstance(obj.get("items"), list)
        ):
            return obj
    except Exception:
        pass
    return {"schema_version": "fx_usdtwd_history_v1", "items": []}


def _upsert_history(history: Dict[str, Any], item: Dict[str, Any]) -> None:
    items = history.get("items", [])
    if not isinstance(items, list):
        items = []
    by_date: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("date"), str):
            by_date[it["date"]] = it
    by_date[item["date"]] = item
    history["items"] = [by_date[k] for k in sorted(by_date.keys())]


def _fetch(session: requests.Session, url: str, timeout: int) -> Tuple[int, str, Optional[str]]:
    try:
        resp = session.get(url, headers={"User-Agent": UA}, timeout=timeout)
        resp.encoding = "utf-8"
        return resp.status_code, resp.text, None
    except Exception as e:
        return 0, "", str(e)


def _html_to_text(html: str) -> str:
    # Unescape entities and drop tags -> text (structure is lost; we therefore bind parsing to a local window)
    s = htmllib.unescape(html)
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _slice_window(text: str, start: int, pre: int = 80, post: int = 700) -> str:
    a = max(0, start - pre)
    b = min(len(text), start + post)
    return text[a:b]


def _compute_sanity_range(history: Dict[str, Any]) -> Tuple[Tuple[float, float], Dict[str, Any]]:
    """
    Dynamic range based on recent median, with hard guard rails.

    If insufficient history -> returns (SANITY_GUARD_MIN, SANITY_GUARD_MAX).
    """
    dbg: Dict[str, Any] = {
        "mode": "fallback_wide",
        "lookback_n": SANITY_LOOKBACK_N,
        "min_points": SANITY_MIN_POINTS,
        "factor_low": SANITY_FACTOR_LOW,
        "factor_high": SANITY_FACTOR_HIGH,
        "guard": [SANITY_GUARD_MIN, SANITY_GUARD_MAX],
        "points_used": 0,
        "median": None,
        "range": [SANITY_GUARD_MIN, SANITY_GUARD_MAX],
        "reason": "insufficient_history",
    }

    items = history.get("items", [])
    mids: List[float] = []
    if isinstance(items, list):
        # take recent by date order (history is kept sorted, but don't assume; sort safely)
        tmp = []
        for it in items:
            if isinstance(it, dict):
                d = it.get("date")
                m = it.get("mid")
                if isinstance(d, str) and isinstance(m, (int, float)):
                    tmp.append((d, float(m)))
        tmp.sort(key=lambda x: x[0])
        for _, m in tmp[-SANITY_LOOKBACK_N:]:
            if m == m and m > 0:  # exclude NaN/invalid
                mids.append(m)

    if len(mids) < SANITY_MIN_POINTS:
        return (SANITY_GUARD_MIN, SANITY_GUARD_MAX), dbg

    med = statistics.median(mids)
    low = med * SANITY_FACTOR_LOW
    high = med * SANITY_FACTOR_HIGH

    # clamp with hard guards (wide enough to avoid accidental blocking under regime drift)
    low = max(SANITY_GUARD_MIN, low)
    high = min(SANITY_GUARD_MAX, high)

    # ensure low < high even in pathological cases
    if not (low < high):
        return (SANITY_GUARD_MIN, SANITY_GUARD_MAX), {
            **dbg,
            "mode": "fallback_wide",
            "points_used": len(mids),
            "median": med,
            "reason": "degenerate_dynamic_range",
        }

    dbg.update(
        {
            "mode": "dynamic_median",
            "points_used": len(mids),
            "median": med,
            "range": [low, high],
            "reason": "ok",
        }
    )
    return (low, high), dbg


def _parse_xrt_text_usd(text: str, tz_name: str, sanity_rng: Tuple[float, float]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse USD row from flattened BOT xrt text.

    Fixes:
    - allow integer or decimal (e.g., cash_buy can be "31" without decimals)
    - parse only inside a local window near the USD anchor to avoid grabbing HKD numbers elsewhere
    - apply dynamic sanity check on mid
    """
    low, high = sanity_rng
    dbg: Dict[str, Any] = {
        "format": "xrt_text_v4_dynamic_sanity",
        "reason": "NA",
        "text_len": len(text),
        "text_head": text[:220],
        "text_has_usd": ("USD" in text),
        "text_has_zh_usd": ("美金" in text and "USD" in text),
        "sanity_range": [low, high],
    }

    # (1) page date
    page_date = None
    m1 = re.search(r"(\d{4}/\d{2}/\d{2})\s*本行", text)
    if m1:
        page_date = m1.group(1)
    else:
        m1b = re.search(r"(\d{4}/\d{2}/\d{2}).{0,40}Foreign Exchange Rate", text, flags=re.IGNORECASE)
        if m1b:
            page_date = m1b.group(1)

    # (2) quote time (optional)
    quote_dt_iso = None
    m2 = re.search(r"牌價最新掛牌時間[:：]\s*(\d{4}/\d{2}/\d{2})\s*(\d{2}:\d{2})", text)
    if m2:
        tz = ZoneInfo(tz_name)
        dt = datetime.strptime(f"{m2.group(1)} {m2.group(2)}", "%Y/%m/%d %H:%M").replace(tzinfo=tz)
        quote_dt_iso = dt.isoformat()

    if not page_date:
        dbg["reason"] = "cannot_find_page_date"
        return None, dbg

    # (3) USD row values
    num = r"(\d+(?:\.\d+)?)"  # int or decimal
    cash_buy = cash_sell = spot_buy = spot_sell = None

    anchor = re.search(r"美金\s*\(USD\)", text)
    if anchor:
        w = _slice_window(text, anchor.start(), pre=80, post=700)
        dbg["usd_anchor"] = "zh:美金(USD)"
        dbg["usd_window"] = w[:520]
        m3 = re.search(rf"美金\s*\(USD\).*?{num}\s+{num}\s+{num}\s+{num}", w)
        if m3:
            cash_buy = _to_float(m3.group(1))
            cash_sell = _to_float(m3.group(2))
            spot_buy = _to_float(m3.group(3))
            spot_sell = _to_float(m3.group(4))
    else:
        dbg["usd_anchor"] = "zh:missing"

    if spot_buy is None or spot_sell is None:
        anchor2 = re.search(r"\(USD\)", text)
        if anchor2:
            w2 = _slice_window(text, anchor2.start(), pre=80, post=700)
            dbg["usd_anchor2"] = "en:(USD)"
            dbg["usd_window2"] = w2[:520]
            m3b = re.search(rf"USD.{0,180}?{num}\s+{num}\s+{num}\s+{num}", w2)
            if m3b:
                cash_buy = _to_float(m3b.group(1))
                cash_sell = _to_float(m3b.group(2))
                spot_buy = _to_float(m3b.group(3))
                spot_sell = _to_float(m3b.group(4))
        else:
            dbg["usd_anchor2"] = "en:missing"

    if spot_buy is None or spot_sell is None:
        dbg["reason"] = "cannot_find_usd_spot"
        dbg["extracted"] = {"cash_buy": cash_buy, "cash_sell": cash_sell, "spot_buy": spot_buy, "spot_sell": spot_sell}
        return None, dbg

    mid = (spot_buy + spot_sell) / 2.0
    if not (low <= mid <= high):
        dbg["reason"] = "sanity_fail_mid_out_of_range"
        dbg["extracted"] = {
            "cash_buy": cash_buy,
            "cash_sell": cash_sell,
            "spot_buy": spot_buy,
            "spot_sell": spot_sell,
            "mid": mid,
        }
        return None, dbg

    data_date = page_date.replace("/", "-")
    parsed = {
        "data_date": data_date,
        "quote_time_local": quote_dt_iso,
        "usd_twd": {
            "cash_buy": cash_buy,
            "cash_sell": cash_sell,
            "spot_buy": spot_buy,
            "spot_sell": spot_sell,
        },
    }
    dbg["reason"] = "ok"
    dbg["extracted"] = {"cash_buy": cash_buy, "cash_sell": cash_sell, "spot_buy": spot_buy, "spot_sell": spot_sell, "mid": mid}
    return parsed, dbg


def _parse_bot_csv_usd(csv_text: str, sanity_rng: Tuple[float, float]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse BOT CSV (flcsv) output and extract the latest USD row.

    Expected columns (common BOT export):
    - 資料日期, 幣別, 現金買入, 現金賣出, 即期買入, 即期賣出
    """
    low, high = sanity_rng
    dbg: Dict[str, Any] = {
        "format": "bot_csv_v1",
        "reason": "NA",
        "sanity_range": [low, high],
        "text_len": len(csv_text),
        "text_head": csv_text[:220],
    }

    # Use csv.reader to be robust against quoted commas
    rows: List[List[str]] = []
    try:
        for r in csv.reader(csv_text.splitlines()):
            if r and any(cell.strip() for cell in r):
                rows.append(r)
    except Exception as e:
        dbg["reason"] = f"csv_parse_error:{type(e).__name__}"
        return None, dbg

    if not rows:
        dbg["reason"] = "csv_empty"
        return None, dbg

    header = rows[0]
    # Normalize header names
    def norm(s: str) -> str:
        return (s or "").strip()

    h = [norm(x) for x in header]

    # Find indices by header keywords (Chinese)
    def find_idx(keys: List[str]) -> Optional[int]:
        for i, col in enumerate(h):
            for k in keys:
                if k in col:
                    return i
        return None

    idx_date = find_idx(["資料日期", "日期", "Date"])
    idx_ccy = find_idx(["幣別", "幣", "Currency"])
    idx_cash_buy = find_idx(["現金買入", "Cash Buying"])
    idx_cash_sell = find_idx(["現金賣出", "Cash Selling"])
    idx_spot_buy = find_idx(["即期買入", "Spot Buying"])
    idx_spot_sell = find_idx(["即期賣出", "Spot Selling"])

    if idx_date is None or idx_spot_buy is None or idx_spot_sell is None:
        dbg["reason"] = "csv_missing_required_headers"
        dbg["headers"] = h[:]
        return None, dbg

    # Iterate data rows; pick latest by date
    best: Optional[Dict[str, Any]] = None

    for r in rows[1:]:
        if idx_date >= len(r):
            continue
        d_raw = norm(r[idx_date])
        if not d_raw:
            continue

        # date format can be YYYY/MM/DD
        m = re.match(r"(\d{4})/(\d{2})/(\d{2})", d_raw)
        if not m:
            continue
        date_iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        # If currency column exists, ensure USD (defensive; though endpoint already USD)
        if idx_ccy is not None and idx_ccy < len(r):
            ccy = norm(r[idx_ccy]).upper()
            if "USD" not in ccy:
                continue

        sb = _to_float(r[idx_spot_buy]) if idx_spot_buy < len(r) else None
        ss = _to_float(r[idx_spot_sell]) if idx_spot_sell < len(r) else None
        if sb is None or ss is None:
            continue

        cb = _to_float(r[idx_cash_buy]) if (idx_cash_buy is not None and idx_cash_buy < len(r)) else None
        cs = _to_float(r[idx_cash_sell]) if (idx_cash_sell is not None and idx_cash_sell < len(r)) else None

        mid = (sb + ss) / 2.0
        if not (low <= mid <= high):
            # For CSV fallback we still enforce sanity (dynamic, wide guardrails)
            continue

        cand = {
            "data_date": date_iso,
            "quote_time_local": None,
            "usd_twd": {"cash_buy": cb, "cash_sell": cs, "spot_buy": sb, "spot_sell": ss},
            "_mid": mid,
        }

        if best is None or cand["data_date"] > best["data_date"]:
            best = cand

    if best is None:
        dbg["reason"] = "csv_no_valid_rows_after_filters"
        return None, dbg

    dbg["reason"] = "ok"
    dbg["extracted"] = {
        "cash_buy": best["usd_twd"]["cash_buy"],
        "cash_sell": best["usd_twd"]["cash_sell"],
        "spot_buy": best["usd_twd"]["spot_buy"],
        "spot_sell": best["usd_twd"]["spot_sell"],
        "mid": best["_mid"],
        "data_date": best["data_date"],
    }
    parsed = {
        "data_date": best["data_date"],
        "quote_time_local": None,
        "usd_twd": best["usd_twd"],
    }
    return parsed, dbg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei", help="Accepted for backward compatibility; used for quote_time_local tz.")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10, help="(legacy) ignored")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--source-url", default=BOT_XRT_PAGE)
    ap.add_argument("--fallback-csv-url", default=BOT_CSV_L3M_USD)
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load history early for dynamic sanity range
    history_obj = _load_history(args.history)
    sanity_rng, sanity_dbg = _compute_sanity_range(history_obj)

    session = requests.Session()

    # --- Primary attempt: HTML ---
    p_status, p_body, p_err = _fetch(session, args.source_url, args.timeout)
    p_text = ""
    p_parsed: Optional[Dict[str, Any]] = None
    p_dbg: Dict[str, Any] = {"format": "xrt_text_v4_dynamic_sanity", "reason": "http_not_200_or_empty"}
    if p_status == 200 and p_body:
        p_text = _html_to_text(p_body)
        p_parsed, p_dbg = _parse_xrt_text_usd(p_text, args.tz, sanity_rng)

    used_source = "BOT_HTML"
    parsed = p_parsed
    parse_dbg = p_dbg
    dq_reason: Optional[str] = None

    # --- Fallback: CSV if primary failed ---
    f_status, f_body, f_err = 0, "", None
    f_dbg: Optional[Dict[str, Any]] = None
    if parsed is None:
        used_source = "BOT_CSV_FALLBACK"
        dq_reason = f"primary_failed:{p_dbg.get('reason','NA')}"
        f_status, f_body, f_err = _fetch(session, args.fallback_csv_url, args.timeout)
        if f_status == 200 and f_body:
            parsed2, f_dbg2 = _parse_bot_csv_usd(f_body, sanity_rng)
            f_dbg = f_dbg2
            if parsed2 is not None:
                parsed = parsed2
                parse_dbg = {
                    "format": "composite",
                    "reason": "ok_fallback_csv",
                    "primary": p_dbg,
                    "fallback": f_dbg2,
                    "sanity": sanity_dbg,
                }
            else:
                parse_dbg = {
                    "format": "composite",
                    "reason": "fallback_failed",
                    "primary": p_dbg,
                    "fallback": f_dbg2,
                    "sanity": sanity_dbg,
                }
        else:
            parse_dbg = {
                "format": "composite",
                "reason": "fallback_http_failed_or_empty",
                "primary": p_dbg,
                "fallback": {
                    "format": "bot_csv_v1",
                    "reason": "http_not_200_or_empty",
                    "http_status": f_status,
                    "http_error": f_err,
                },
                "sanity": sanity_dbg,
            }
    else:
        # Primary ok: attach sanity dbg for audit
        parse_dbg = {**p_dbg, "sanity": sanity_dbg}

    data_date = parsed.get("data_date") if parsed else None
    spot_buy = parsed["usd_twd"]["spot_buy"] if parsed else None
    spot_sell = parsed["usd_twd"]["spot_sell"] if parsed else None
    quote_time_local = parsed.get("quote_time_local") if parsed else None

    mid: Optional[float] = None
    if spot_buy is not None and spot_sell is not None:
        mid = (spot_buy + spot_sell) / 2.0

    strict_ok = bool(
        data_date
        and spot_buy is not None
        and spot_sell is not None
        and mid is not None
        and spot_sell >= spot_buy
    )

    if not strict_ok and dq_reason is None:
        dq_reason = f"parse_failed:{parse_dbg.get('reason','NA')}"

    latest = {
        "schema_version": "fx_usdtwd_latest_v1",
        "generated_at_utc": now_utc,
        "source": "BOT",
        "source_url": (args.source_url if used_source == "BOT_HTML" else args.fallback_csv_url),
        "data_date": data_date,
        "quote_time_local": quote_time_local,
        "usd_twd": {"spot_buy": spot_buy, "spot_sell": spot_sell, "mid": mid},
        # new fields: dq_reason + dbg (kept under raw)
        "dq_reason": (None if strict_ok else dq_reason),
        "raw": {
            "used_source": used_source,
            "sanity": sanity_dbg,
            "parse_dbg": parse_dbg,
            "text_head": (p_text[:220] if p_text else None),
            "csv_head": (f_body[:220] if (used_source != "BOT_HTML" and f_body) else None),
        },
        "http": {
            "status_code": p_status,
            "error": p_err,
        },
        "http_fallback": {
            "status_code": f_status,
            "error": f_err,
        },
    }
    _dump_json(args.latest_out, latest)

    if strict_ok:
        history = history_obj  # reuse loaded object
        _upsert_history(
            history,
            {
                "date": data_date,
                "mid": mid,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
                "source_url": latest.get("source_url"),
                "quote_time_local": quote_time_local,
            },
        )
        _dump_json(args.history, history)

    print(
        "FX(BOT) strict_ok={ok} used={used} date={date} spot_buy={b} spot_sell={s} mid={m} "
        "http_p={hp} http_f={hf} reason={reason}".format(
            ok=str(strict_ok).lower(),
            used=used_source,
            date=data_date or "NA",
            b="None" if spot_buy is None else f"{spot_buy:.6f}",
            s="None" if spot_sell is None else f"{spot_sell:.6f}",
            m="None" if mid is None else f"{mid:.6f}",
            hp=p_status,
            hf=f_status,
            reason=parse_dbg.get("reason", "NA"),
        )
    )

    if args.strict and not strict_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())