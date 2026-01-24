#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD spot rate from Bank of Taiwan (BOT) daily CSV.

STRICT goals:
- Deterministic, auditable, minimal fetch: 1 request per run.
- Weekend/holiday safe: backtrack date until data exists (max_back).
- Parse BOT "本行買入/本行賣出" layout robustly.
- STRICT FAIL:
  - HTTP not 200 (after backtrack) OR
  - Cannot parse USD spot buy/sell OR
  - spot_buy > spot_sell OR
  - spot values missing

Source:
- Daily CSV: https://rate.bot.com.tw/xrt/flcsv/0/YYYY-MM-DD

Outputs:
- fx_cache/latest.json
- fx_cache/history.json (upsert by date)

Notes:
- BOT is "牌告匯率" (bank posted), not interbank live price.
- Forward rates (遠期) are different instruments; do not compare to spot.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests
from zoneinfo import ZoneInfo

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BOT_DAILY_CSV = "https://rate.bot.com.tw/xrt/flcsv/0/{date}"

SCHEMA_LATEST = "fx_usdtwd_latest_v1"
SCHEMA_HISTORY = "fx_usdtwd_history_v1"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _dump_json(path: str, obj: Any) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _load_json(path: str) -> Any:
    return json.loads(_read_text(path))


def _today_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def _try_decode(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp950"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="replace")


def _to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x.replace(",", ""))
    except Exception:
        return None


def _fetch_for_date(session: requests.Session, date_str: str, timeout: int) -> Tuple[int, bytes, Optional[str], str]:
    url = BOT_DAILY_CSV.format(date=date_str)
    try:
        resp = session.get(url, headers={"User-Agent": UA}, timeout=timeout)
        return resp.status_code, resp.content, None, url
    except Exception as e:
        return 0, b"", str(e), url


def _read_csv_rows(text: str) -> List[List[str]]:
    sio = StringIO(text)
    reader = csv.reader(sio)
    rows = []
    for r in reader:
        if not r:
            continue
        rr = [c.strip() for c in r]
        if any(x != "" for x in rr):
            rows.append(rr)
    return rows


def _is_yyyymmdd(s: str) -> bool:
    return bool(re.fullmatch(r"\d{8}", (s or "").strip()))


def _find_idx(header: List[str], keys: List[str]) -> Optional[int]:
    for k in keys:
        for i, h in enumerate(header):
            if k in (h or ""):
                return i
    return None


def _parse_bot_csv_usd_spot(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Returns: (usd_row_dict, currency_label)

    Supports two common BOT CSV layouts:
    1) Two-row per currency (daily CSV):
       header: 幣別, 匯率, 現金, 即期, 遠期10天, ...
       rows:  USD, 本行買入, <cash>, <spot>, <fwd10>...
              USD, 本行賣出, <cash>, <spot>, <fwd10>...

    2) Single-row combined (some endpoints):
       header: 資料日期, 幣別, 匯率, 現金, 即期, 匯率, 現金, 即期
       row:    20260121, USD, 本行買入, <cash>, <spot>, 本行賣出, <cash>, <spot>

    STRICT:
    - Must extract spot_buy/spot_sell as floats.
    - Must satisfy spot_buy <= spot_sell.
    """
    rows = _read_csv_rows(text)
    if len(rows) < 2:
        return None, None

    header = rows[0]

    # Detect layout 2 (single-row combined): header contains two "匯率" and two "即期"
    # Example snippet: 資料日期,幣別,匯率,現金,即期,匯率,現金,即期
    if any("資料日期" in h for h in header) and header.count("匯率") >= 2 and header.count("即期") >= 2:
        # indices
        idx_date = _find_idx(header, ["資料日期", "Date"])
        idx_ccy = _find_idx(header, ["幣別", "Currency"])
        # first block
        idx_rate1 = 2 if len(header) > 2 else None  # usually "匯率"
        idx_cash1 = _find_idx(header, ["現金"])
        idx_spot1 = _find_idx(header, ["即期"])
        # second block: find the second occurrence of "匯率/現金/即期"
        # safest: locate positions by scanning header
        rate_pos = [i for i, h in enumerate(header) if h == "匯率"]
        spot_pos = [i for i, h in enumerate(header) if h == "即期"]
        cash_pos = [i for i, h in enumerate(header) if h == "現金"]
        if idx_date is None or idx_ccy is None or len(rate_pos) < 2 or len(spot_pos) < 2 or len(cash_pos) < 2:
            return None, None

        rate1_i, rate2_i = rate_pos[0], rate_pos[1]
        cash1_i, cash2_i = cash_pos[0], cash_pos[1]
        spot1_i, spot2_i = spot_pos[0], spot_pos[1]

        for r in rows[1:]:
            if idx_ccy >= len(r):
                continue
            ccy = r[idx_ccy]
            if "USD" not in ccy:
                continue

            # expect: ... 本行買入, cash1, spot1, 本行賣出, cash2, spot2
            buy_tag = r[rate1_i] if rate1_i < len(r) else ""
            sell_tag = r[rate2_i] if rate2_i < len(r) else ""
            if "本行買入" not in buy_tag or "本行賣出" not in sell_tag:
                continue

            spot_buy = _to_float(r[spot1_i] if spot1_i < len(r) else "")
            spot_sell = _to_float(r[spot2_i] if spot2_i < len(r) else "")
            if spot_buy is None or spot_sell is None:
                return None, None
            if spot_buy > spot_sell:
                return None, None

            return (
                {"currency": ccy, "spot_buy": spot_buy, "spot_sell": spot_sell},
                ccy,
            )

        return None, None

    # Layout 1 (two-row per currency, daily CSV)
    idx_ccy = _find_idx(header, ["幣別", "Currency"])
    idx_kind = _find_idx(header, ["匯率"])  # this column holds 本行買入/本行賣出
    idx_spot = _find_idx(header, ["即期", "Spot"])
    if idx_ccy is None:
        idx_ccy = 0
    if idx_kind is None:
        # STRICT: no fallback guessing
        return None, None
    if idx_spot is None:
        return None, None

    buy_row: Optional[List[str]] = None
    sell_row: Optional[List[str]] = None
    usd_label: Optional[str] = None

    for r in rows[1:]:
        if idx_ccy >= len(r) or idx_kind >= len(r):
            continue
        ccy = r[idx_ccy]
        kind = r[idx_kind]
        if "USD" not in ccy:
            continue
        usd_label = ccy
        if "本行買入" in kind:
            buy_row = r
        elif "本行賣出" in kind:
            sell_row = r

        if buy_row is not None and sell_row is not None:
            break

    if buy_row is None or sell_row is None or usd_label is None:
        return None, None

    spot_buy = _to_float(buy_row[idx_spot] if idx_spot < len(buy_row) else "")
    spot_sell = _to_float(sell_row[idx_spot] if idx_spot < len(sell_row) else "")
    if spot_buy is None or spot_sell is None:
        return None, None
    if spot_buy > spot_sell:
        return None, None

    return {"currency": usd_label, "spot_buy": spot_buy, "spot_sell": spot_sell}, usd_label


def _load_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"schema_version": SCHEMA_HISTORY, "items": []}
    try:
        obj = _load_json(path)
        if isinstance(obj, dict) and obj.get("schema_version") == SCHEMA_HISTORY and isinstance(obj.get("items"), list):
            return obj
    except Exception:
        pass
    return {"schema_version": SCHEMA_HISTORY, "items": []}


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    local_now = _today_local(args.tz)
    d0 = local_now.date()

    session = requests.Session()

    chosen_date: Optional[str] = None
    chosen_url: Optional[str] = None
    status_code: int = 0
    http_err: Optional[str] = None
    usd_row: Optional[Dict[str, Any]] = None
    usd_label: Optional[str] = None
    parse_err: Optional[str] = None

    for i in range(max(args.max_back, 1)):
        d = d0 - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        sc, content, err, url = _fetch_for_date(session, date_str, args.timeout)
        status_code = sc
        chosen_url = url
        http_err = err

        if sc != 200 or not content:
            continue

        text = _try_decode(content)
        row, label = _parse_bot_csv_usd_spot(text)
        if row and row.get("spot_buy") is not None and row.get("spot_sell") is not None:
            usd_row = row
            usd_label = label
            chosen_date = date_str
            parse_err = None
            break
        else:
            parse_err = "PARSE_FAIL_OR_INVALID_SPOT"

    spot_buy = usd_row.get("spot_buy") if usd_row else None
    spot_sell = usd_row.get("spot_sell") if usd_row else None
    mid: Optional[float] = None
    if spot_buy is not None and spot_sell is not None:
        mid = (spot_buy + spot_sell) / 2.0

    strict_ok = (
        (status_code == 200)
        and (http_err is None)
        and (chosen_date is not None)
        and (spot_buy is not None)
        and (spot_sell is not None)
        and (spot_buy <= spot_sell)
        and (mid is not None)
    )

    latest = {
        "schema_version": SCHEMA_LATEST,
        "generated_at_utc": now_utc,
        "source": "BOT",
        "source_url": chosen_url,
        "data_date": chosen_date,
        "usd_twd": {
            "spot_buy": spot_buy,
            "spot_sell": spot_sell,
            "mid": mid,
        },
        "raw": {
            "currency_label": usd_label,
            "row": usd_row,
        },
        "http": {"status_code": status_code, "error": http_err},
        "parse": {"ok": bool(strict_ok), "error": None if strict_ok else (parse_err or "STRICT_FAIL")},
    }
    _dump_json(args.latest_out, latest)

    # Update history only if strict OK
    if strict_ok and chosen_date and mid is not None:
        history = _load_history(args.history)
        _upsert_history(
            history,
            {
                "date": chosen_date,
                "mid": mid,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
                "source_url": chosen_url,
            },
        )
        _dump_json(args.history, history)

    # Print a short, audit-friendly line (visible in Actions logs)
    print(
        f"FX(BOT) strict_ok={str(strict_ok).lower()} "
        f"date={chosen_date or 'NA'} spot_buy={spot_buy} spot_sell={spot_sell} mid={mid} "
        f"http={status_code} err={http_err or 'NA'} url={chosen_url or 'NA'}"
    )

    return 0 if strict_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())