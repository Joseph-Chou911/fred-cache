#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX cache: USD/TWD rate from Bank of Taiwan (BOT) daily CSV.

Key goals:
- Deterministic, auditable, minimal fetch: 1 request per run.
- Weekend/holiday safe: backtrack date until data exists (max_back).
- Encoding tolerant: try utf-8-sig, utf-8, then cp950.
- Support multiple BOT CSV layouts:
  A) Classic spot layout: columns like 「即期買入 / 即期賣出」 (or English Spot Buying/Selling)
  B) Forward-like layout (遠期匯率頁常見): header has TWO '即期' columns (buy block + sell block),
     e.g. 幣別,匯率,即期,遠期10天,...,匯率,即期,遠期10天,...

Source:
- Daily CSV: https://rate.bot.com.tw/xrt/flcsv/0/YYYY-MM-DD  (BOT)

Output:
- fx_cache/latest.json
- fx_cache/history.json (append/dedupe by date)

Strict mode:
- If --strict is set, exit non-zero unless:
  * data_date exists
  * spot_buy and spot_sell exist
  * spot_sell >= spot_buy  (sanity check)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
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


def _find_idx_contains(header: List[str], keys: List[str]) -> Optional[int]:
    for k in keys:
        for i, h in enumerate(header):
            if k in h:
                return i
    return None


def _find_all_idx_contains(header: List[str], key: str) -> List[int]:
    out: List[int] = []
    for i, h in enumerate(header):
        if key in h:
            out.append(i)
    return out


def _parse_bot_csv(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Dict[str, Any]]:
    """
    Return: (usd_row_dict, currency_label, parse_dbg)

    usd_row_dict schema:
    {
      "currency": <str>,
      "spot_buy": <float|None>,
      "spot_sell": <float|None>,
      "layout": "classic" | "dual_block",
      "idx": {...},
      "raw_row": [...],
      "raw_header": [...]
    }
    """
    dbg: Dict[str, Any] = {"layout": "unknown", "reason": "NA"}

    sio = StringIO(text)
    reader = csv.reader(sio)
    rows = list(reader)
    if not rows or len(rows) < 2:
        dbg["reason"] = "csv_empty_or_too_short"
        return None, None, dbg

    header = [h.strip() for h in rows[0]]
    dbg["raw_header_preview"] = header[:20]

    # currency column
    idx_ccy = _find_idx_contains(header, ["幣別", "Currency"])
    if idx_ccy is None:
        idx_ccy = 0

    # ---- Layout A: classic spot layout (即期買入/即期賣出) ----
    idx_spot_buy = _find_idx_contains(header, ["即期買入", "Spot Buying", "SpotBuy"])
    idx_spot_sell = _find_idx_contains(header, ["即期賣出", "Spot Selling", "SpotSell"])

    if idx_spot_buy is not None and idx_spot_sell is not None:
        dbg["layout"] = "classic"
        dbg["reason"] = "matched_classic_headers"
        chosen_layout = "classic"
    else:
        # ---- Layout B: dual-block layout (two '即期' columns: buy-block + sell-block) ----
        # Common in forward-rate-like tables:
        # 幣別,匯率,即期,遠期10天,...,匯率,即期,遠期10天,...
        idxs_jq = _find_all_idx_contains(header, "即期")
        if len(idxs_jq) >= 2:
            idx_spot_buy = idxs_jq[0]
            idx_spot_sell = idxs_jq[1]
            dbg["layout"] = "dual_block"
            dbg["reason"] = "matched_dual_block_即期"
            chosen_layout = "dual_block"
        else:
            dbg["layout"] = "unknown"
            dbg["reason"] = "cannot_find_spot_columns"
            return None, None, dbg

    usd_row: Optional[Dict[str, Any]] = None
    usd_label: Optional[str] = None

    for r in rows[1:]:
        if not r:
            continue
        ccy = (r[idx_ccy] if idx_ccy < len(r) else "").strip()
        if not ccy:
            continue
        # match USD row (possible: "美金 (USD)" / "USD" / contains "(USD)" / etc.)
        if "USD" in ccy:
            usd_label = ccy
            buy_raw = r[idx_spot_buy] if (idx_spot_buy is not None and idx_spot_buy < len(r)) else ""
            sell_raw = r[idx_spot_sell] if (idx_spot_sell is not None and idx_spot_sell < len(r)) else ""
            spot_buy = _to_float(buy_raw)
            spot_sell = _to_float(sell_raw)

            usd_row = {
                "currency": ccy,
                "spot_buy": spot_buy,
                "spot_sell": spot_sell,
                "layout": chosen_layout,
                "idx": {"ccy": idx_ccy, "spot_buy": idx_spot_buy, "spot_sell": idx_spot_sell},
                "raw_row": r,
                "raw_header": header,
                "raw_cells": {"spot_buy_raw": buy_raw, "spot_sell_raw": sell_raw},
            }
            break

    return usd_row, usd_label, dbg


def _fetch_for_date(session: requests.Session, date_str: str, timeout: int) -> Tuple[int, bytes, Optional[str], str]:
    url = BOT_DAILY_CSV.format(date=date_str)
    try:
        resp = session.get(url, headers={"User-Agent": UA}, timeout=timeout)
        return resp.status_code, resp.content, None, url
    except Exception as e:
        return 0, b"", str(e), url


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--latest-out", default="fx_cache/latest.json")
    ap.add_argument("--history", default="fx_cache/history.json")
    ap.add_argument("--max-back", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 1) if spot rates are missing/invalid.")
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
    parse_dbg: Dict[str, Any] = {}

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
        row, label, dbg = _parse_bot_csv(text)
        parse_dbg = dbg
        # Accept only if we got both spot_buy and spot_sell
        if row and row.get("spot_buy") is not None and row.get("spot_sell") is not None:
            usd_row = row
            usd_label = label
            chosen_date = date_str
            break

    spot_buy = usd_row.get("spot_buy") if usd_row else None
    spot_sell = usd_row.get("spot_sell") if usd_row else None
    mid: Optional[float] = None
    if spot_buy is not None and spot_sell is not None:
        mid = (spot_buy + spot_sell) / 2.0

    # strict sanity: sell should be >= buy (otherwise columns are likely mis-mapped)
    strict_ok = bool(
        chosen_date
        and spot_buy is not None
        and spot_sell is not None
        and mid is not None
        and spot_sell >= spot_buy
    )

    latest = {
        "schema_version": "fx_usdtwd_latest_v1",
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
            "parse_dbg": parse_dbg,
        },
        "http": {"status_code": status_code, "error": http_err},
    }
    _dump_json(args.latest_out, latest)

    # Update history only if we got a valid mid and strict sanity passes (avoid polluting history)
    if chosen_date and mid is not None and spot_buy is not None and spot_sell is not None and spot_sell >= spot_buy:
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

    # One-line audit log for GitHub Actions
    print(
        "FX(BOT) strict_ok={ok} date={date} spot_buy={b} spot_sell={s} mid={m} http={http} err={err} url={url}".format(
            ok=str(strict_ok).lower(),
            date=chosen_date or "NA",
            b="None" if spot_buy is None else f"{spot_buy:.6f}",
            s="None" if spot_sell is None else f"{spot_sell:.6f}",
            m="None" if mid is None else f"{mid:.6f}",
            http=status_code,
            err=(http_err or "NA"),
            url=(chosen_url or "NA"),
        )
    )

    if args.strict and not strict_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())