#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_private_credit_monitor.py (v1.0)

Purpose
-------
Build a standalone, audit-friendly private credit monitor sidecar.

Design principles
-----------------
- Focus on private-credit-specific blind spots.
- DO NOT recompute public-credit proxies already monitored elsewhere
  (e.g. HY spread, HYG/IEF, OFR_FSI).
- Use deterministic rules and explicit NA handling.
- Prefer a small set of robust market proxies plus manual event/NAV overlays.
- Display-only / advisory-first: this script does not control a parent strategy mode.

Outputs
-------
All outputs go to a dedicated folder (default: private_credit_cache/):
- latest.json
- history.json
- report.md
- inputs/manual_events.json   (template created if absent)
- inputs/manual_nav.json      (template created if absent)

Data layers (v1)
----------------
1) BDC market proxy (auto):
   - Fetch daily close history for a basket of listed BDC names + BIZD ETF
   - Compute z60 / p60 / p252 / ret1 / ret5 / 20D drawdown / breadth

2) NAV overlay (manual, optional):
   - User-maintained latest NAV values for selected BDCs
   - Compute premium/discount to NAV using latest market close

3) Event overlay (manual, optional):
   - User-maintained event flags for private-credit-specific developments
   - Categories include gate / withdrawal_limit / nav_markdown /
     warehouse_tightening / bank_pullback / default_restructuring / pik_stress

4) Optional public-credit context (reference-only, no recomputation):
   - Reads unified_dashboard/latest.json if present and extracts a few series
   - Purely for report context; not used in module signal rules by default

Dependencies
------------
- Python 3.11+
- requests
- pandas
- numpy

Suggested run
-------------
python build_private_credit_monitor.py \
  --out-dir private_credit_cache \
  --unified-json unified_dashboard/latest.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


SCRIPT_NAME = "build_private_credit_monitor.py"
SCRIPT_VERSION = "v1.0"
UTC_NOW = lambda: datetime.now(timezone.utc).replace(microsecond=0)

DEFAULT_BDC_TICKERS = ["ARCC", "BXSL", "OBDC", "FSK", "PSEC"]
DEFAULT_PROXY_TICKERS = ["BIZD"]
ALL_DEFAULT_TICKERS = DEFAULT_BDC_TICKERS + DEFAULT_PROXY_TICKERS

EVENT_CATEGORIES = {
    "redemption_gate",
    "withdrawal_limit",
    "nav_markdown",
    "warehouse_tightening",
    "bank_pullback",
    "default_restructuring",
    "pik_stress",
    "valuation_delay",
    "semi_liquid_stress",
    "other",
}
SEVERITY_ORDER = {"NONE": 0, "WATCH": 1, "ALERT": 2}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build standalone private credit monitor sidecar")
    p.add_argument("--out-dir", default="private_credit_cache", help="Output folder")
    p.add_argument("--manual-events", default=None, help="Path to manual events JSON")
    p.add_argument("--manual-nav", default=None, help="Path to manual NAV JSON")
    p.add_argument("--unified-json", default="unified_dashboard/latest.json", help="Optional unified JSON for reference-only context")
    p.add_argument("--history-max-rows", type=int, default=1000, help="Max rows to keep in history.json")
    p.add_argument("--lookback-calendar-days", type=int, default=600, help="Calendar days to request from stooq")
    p.add_argument("--z-window", type=int, default=60, help="Window for short z-score")
    p.add_argument("--p-window", type=int, default=252, help="Window for long percentile")
    p.add_argument("--event-recent-days", type=int, default=45, help="Recent window for event-based signal rules")
    p.add_argument("--nav-fresh-max-days", type=int, default=120, help="NAV older than this is treated as stale for aggregate rules")
    p.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    p.add_argument("--tickers", default=",".join(ALL_DEFAULT_TICKERS), help="Comma-separated tickers to monitor")
    return p.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: Path, obj: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def create_manual_event_template(path: Path) -> None:
    if path.exists():
        return
    template = {
        "schema_version": "private_credit_manual_events_v1",
        "as_of_date": "YYYY-MM-DD",
        "notes": [
            "Manual event overlay for private-credit-specific stress.",
            "Valid severity: NONE / WATCH / ALERT",
            "Valid category: redemption_gate, withdrawal_limit, nav_markdown, warehouse_tightening, bank_pullback, default_restructuring, pik_stress, valuation_delay, semi_liquid_stress, other",
        ],
        "events": [
            {
                "event_date": "YYYY-MM-DD",
                "category": "withdrawal_limit",
                "entity": "Example fund / lender / platform",
                "severity": "WATCH",
                "title": "Example title",
                "source_url": "https://example.com/article",
                "note": "Free-form note",
            }
        ],
    }
    write_json(path, template)


def create_manual_nav_template(path: Path) -> None:
    if path.exists():
        return
    template = {
        "schema_version": "private_credit_manual_nav_v1",
        "as_of_date": "YYYY-MM-DD",
        "notes": [
            "Manual NAV overlay for selected BDC / proxy names.",
            "nav_date should be the date the reported NAV applies to, e.g. quarter-end.",
            "This script will compare latest market close vs provided NAV.",
        ],
        "items": [
            {
                "ticker": "ARCC",
                "nav": 0.0,
                "nav_date": "YYYY-MM-DD",
                "source_url": "https://example.com/investor-relations",
                "note": "Reported NAV per share",
            }
        ],
    }
    write_json(path, template)


def to_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except Exception:
        return None


def parse_date(x: Any) -> Optional[pd.Timestamp]:
    if x is None or x == "":
        return None
    try:
        ts = pd.to_datetime(x, errors="coerce")
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts).normalize()
    except Exception:
        return None


def percentile_rank(window: pd.Series, value: float) -> Optional[float]:
    if window is None or len(window) == 0 or value is None:
        return None
    s = pd.Series(window).dropna()
    if s.empty:
        return None
    return round(float((s <= value).mean() * 100.0), 6)


def zscore_last(window: pd.Series) -> Optional[float]:
    s = pd.Series(window).dropna()
    if len(s) < 2:
        return None
    mu = float(s.mean())
    sigma = float(s.std(ddof=0))
    if sigma == 0:
        return 0.0
    return round(float((s.iloc[-1] - mu) / sigma), 6)


def safe_pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round(float((a / b - 1.0) * 100.0), 6)


def safe_num(x: Any, digits: int = 6) -> Any:
    if x is None:
        return None
    try:
        return round(float(x), digits)
    except Exception:
        return x


def fetch_stooq_daily(symbol: str, start_date: pd.Timestamp, end_date: pd.Timestamp, timeout: int) -> Tuple[pd.DataFrame, str, Optional[str]]:
    """
    Returns (df, source_url, error_note)
    Expected CSV columns: Date,Open,High,Low,Close,Volume
    """
    ticker = f"{symbol.lower()}.us"
    d1 = start_date.strftime("%Y%m%d")
    d2 = end_date.strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={ticker}&d1={d1}&d2={d2}&i=d"
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        text = r.text.strip()
        if not text or text.lower().startswith("no data"):
            return pd.DataFrame(), url, "ERR:no_data"
        from io import StringIO
        df = pd.read_csv(StringIO(text))
        if df.empty or "Date" not in df.columns or "Close" not in df.columns:
            return pd.DataFrame(), url, "ERR:bad_csv_shape"
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Date", "Close"]).copy()
        df = df.sort_values("Date").reset_index(drop=True)
        return df, url, None
    except Exception as e:
        return pd.DataFrame(), url, f"ERR:{type(e).__name__}:{str(e)[:160]}"


def compute_price_stats(df: pd.DataFrame, z_window: int, p_window: int) -> Dict[str, Any]:
    if df is None or df.empty or len(df) < 3:
        return {
            "data_date": None,
            "close": None,
            "prev_close": None,
            "ret1_pct": None,
            "ret5_pct": None,
            "z60": None,
            "p60": None,
            "p252": None,
            "drawdown_20d_pct": None,
            "ma20": None,
            "price_vs_ma20_pct": None,
            "points": 0,
        }

    closes = df["Close"].astype(float).reset_index(drop=True)
    dates = pd.to_datetime(df["Date"]).reset_index(drop=True)
    last_close = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else None
    ret1 = safe_pct(last_close, prev_close)
    close_5 = float(closes.iloc[-6]) if len(closes) >= 6 else None
    ret5 = safe_pct(last_close, close_5)

    win_z = closes.tail(min(z_window, len(closes)))
    win_p = closes.tail(min(p_window, len(closes)))
    z60 = zscore_last(win_z)
    p60 = percentile_rank(win_z, last_close)
    p252 = percentile_rank(win_p, last_close)

    ma20 = float(closes.tail(min(20, len(closes))).mean()) if len(closes) >= 5 else None
    price_vs_ma20_pct = safe_pct(last_close, ma20) if ma20 else None

    # trailing drawdown vs rolling 20D max, evaluated on last day
    if len(closes) >= 20:
        peak20 = float(closes.tail(20).max())
        dd20 = safe_pct(last_close, peak20)
    else:
        peak20 = None
        dd20 = None

    return {
        "data_date": dates.iloc[-1].strftime("%Y-%m-%d"),
        "close": safe_num(last_close),
        "prev_close": safe_num(prev_close),
        "ret1_pct": safe_num(ret1),
        "ret5_pct": safe_num(ret5),
        "z60": safe_num(z60),
        "p60": safe_num(p60),
        "p252": safe_num(p252),
        "drawdown_20d_pct": safe_num(dd20),
        "ma20": safe_num(ma20),
        "price_vs_ma20_pct": safe_num(price_vs_ma20_pct),
        "points": int(len(closes)),
    }


def compute_basket_summary(rows: List[Dict[str, Any]], basket_tickers: List[str]) -> Dict[str, Any]:
    sub = [r for r in rows if r.get("ticker") in basket_tickers and r.get("close") is not None]
    if not sub:
        return {
            "coverage": 0,
            "median_ret1_pct": None,
            "median_ret5_pct": None,
            "median_z60": None,
            "median_drawdown_20d_pct": None,
            "extreme_z_count": 0,
            "extreme_z_share": None,
            "ret5_le_minus5_count": 0,
            "ret5_le_minus5_share": None,
            "below_ma20_count": 0,
            "below_ma20_share": None,
        }

    def vals(key: str) -> List[float]:
        return [float(r[key]) for r in sub if r.get(key) is not None]

    zvals = vals("z60")
    r1vals = vals("ret1_pct")
    r5vals = vals("ret5_pct")
    ddvals = vals("drawdown_20d_pct")
    ma_gap_vals = vals("price_vs_ma20_pct")

    extreme_z_count = sum(1 for v in zvals if v <= -2.0)
    ret5_bad_count = sum(1 for v in r5vals if v <= -5.0)
    below_ma20_count = sum(1 for v in ma_gap_vals if v < 0)
    coverage = len(sub)

    return {
        "coverage": coverage,
        "median_ret1_pct": safe_num(np.median(r1vals)) if r1vals else None,
        "median_ret5_pct": safe_num(np.median(r5vals)) if r5vals else None,
        "median_z60": safe_num(np.median(zvals)) if zvals else None,
        "median_drawdown_20d_pct": safe_num(np.median(ddvals)) if ddvals else None,
        "extreme_z_count": int(extreme_z_count),
        "extreme_z_share": safe_num(extreme_z_count / coverage * 100.0) if coverage else None,
        "ret5_le_minus5_count": int(ret5_bad_count),
        "ret5_le_minus5_share": safe_num(ret5_bad_count / coverage * 100.0) if coverage else None,
        "below_ma20_count": int(below_ma20_count),
        "below_ma20_share": safe_num(below_ma20_count / coverage * 100.0) if coverage else None,
    }


def load_manual_events(path: Path, recent_days: int) -> Dict[str, Any]:
    raw = read_json(path, default={}) or {}
    events = raw.get("events", []) if isinstance(raw, dict) else []
    today = UTC_NOW().date()
    recent_cutoff = pd.Timestamp(today) - pd.Timedelta(days=recent_days)
    out_rows: List[Dict[str, Any]] = []

    for ev in events:
        if not isinstance(ev, dict):
            continue
        sev = str(ev.get("severity", "WATCH")).upper().strip()
        cat = str(ev.get("category", "other")).strip()
        event_date = parse_date(ev.get("event_date"))
        is_recent = bool(event_date is not None and event_date >= recent_cutoff)
        if sev not in SEVERITY_ORDER:
            sev = "WATCH"
        if cat not in EVENT_CATEGORIES:
            cat = "other"
        out_rows.append({
            "event_date": event_date.strftime("%Y-%m-%d") if event_date is not None else None,
            "category": cat,
            "entity": ev.get("entity"),
            "severity": sev,
            "title": ev.get("title"),
            "source_url": ev.get("source_url"),
            "note": ev.get("note"),
            "is_recent": is_recent,
        })

    recent_rows = [r for r in out_rows if r.get("is_recent")]
    alert_recent = sum(1 for r in recent_rows if r.get("severity") == "ALERT")
    watch_recent = sum(1 for r in recent_rows if r.get("severity") == "WATCH")

    latest_recent_date = None
    dated_recent = [parse_date(r.get("event_date")) for r in recent_rows if r.get("event_date")]
    dated_recent = [d for d in dated_recent if d is not None]
    if dated_recent:
        latest_recent_date = max(dated_recent).strftime("%Y-%m-%d")

    return {
        "path": str(path),
        "schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "as_of_date": raw.get("as_of_date") if isinstance(raw, dict) else None,
        "notes": raw.get("notes") if isinstance(raw, dict) else None,
        "recent_window_days": recent_days,
        "event_count_total": len(out_rows),
        "event_count_recent": len(recent_rows),
        "alert_recent_count": alert_recent,
        "watch_recent_count": watch_recent,
        "latest_recent_event_date": latest_recent_date,
        "events": sorted(out_rows, key=lambda x: (x.get("event_date") or "", x.get("severity") or ""), reverse=True),
    }


def load_manual_nav(path: Path, latest_price_by_ticker: Dict[str, Dict[str, Any]], nav_fresh_max_days: int) -> Dict[str, Any]:
    raw = read_json(path, default={}) or {}
    items = raw.get("items", []) if isinstance(raw, dict) else []
    out_rows: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper().strip()
        nav = to_float(item.get("nav"))
        nav_date = parse_date(item.get("nav_date"))
        px = latest_price_by_ticker.get(ticker, {})
        market_close = to_float(px.get("close"))
        market_date = parse_date(px.get("data_date"))
        premium_discount_pct = safe_pct(market_close, nav) if (market_close is not None and nav is not None) else None
        nav_age_days = None
        fresh_for_rule = False
        if nav_date is not None and market_date is not None:
            nav_age_days = int((market_date - nav_date).days)
            fresh_for_rule = nav_age_days <= nav_fresh_max_days
        out_rows.append({
            "ticker": ticker,
            "nav": safe_num(nav),
            "nav_date": nav_date.strftime("%Y-%m-%d") if nav_date is not None else None,
            "market_close": safe_num(market_close),
            "market_date": market_date.strftime("%Y-%m-%d") if market_date is not None else None,
            "premium_discount_pct": safe_num(premium_discount_pct),
            "nav_age_days": nav_age_days,
            "fresh_for_rule": fresh_for_rule,
            "source_url": item.get("source_url"),
            "note": item.get("note"),
        })

    fresh_rows = [r for r in out_rows if r.get("fresh_for_rule") and r.get("premium_discount_pct") is not None]
    all_rows_with_val = [r for r in out_rows if r.get("premium_discount_pct") is not None]
    median_discount_fresh = np.median([float(r["premium_discount_pct"]) for r in fresh_rows]) if fresh_rows else None
    median_discount_all = np.median([float(r["premium_discount_pct"]) for r in all_rows_with_val]) if all_rows_with_val else None

    if len(fresh_rows) >= 3:
        nav_confidence = "OK"
    elif len(fresh_rows) >= 1:
        nav_confidence = "PARTIAL"
    else:
        nav_confidence = "NA"

    return {
        "path": str(path),
        "schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "as_of_date": raw.get("as_of_date") if isinstance(raw, dict) else None,
        "nav_fresh_max_days": nav_fresh_max_days,
        "coverage_total": len(out_rows),
        "coverage_fresh": len(fresh_rows),
        "median_discount_pct_fresh": safe_num(median_discount_fresh),
        "median_discount_pct_all": safe_num(median_discount_all),
        "confidence": nav_confidence,
        "items": sorted(out_rows, key=lambda x: (x.get("premium_discount_pct") if x.get("premium_discount_pct") is not None else 9999.0)),
    }


def nested_find_series(obj: Any, target_series: str) -> Optional[Dict[str, Any]]:
    """Search recursively for a dict with key 'series' == target_series."""
    if isinstance(obj, dict):
        if str(obj.get("series", "")).upper() == target_series.upper():
            return obj
        for v in obj.values():
            found = nested_find_series(v, target_series)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = nested_find_series(item, target_series)
            if found is not None:
                return found
    return None


def load_reference_context(unified_json_path: Path) -> Dict[str, Any]:
    if not unified_json_path.exists():
        return {
            "enabled": False,
            "note": "reference file not found",
            "source_path": str(unified_json_path),
            "reference_only": True,
        }

    raw = read_json(unified_json_path, default={}) or {}
    refs = {}
    for series in ["BAMLH0A0HYM2", "HYG_IEF_RATIO", "OFR_FSI"]:
        row = nested_find_series(raw, series)
        if row is None:
            refs[series] = {"found": False}
        else:
            refs[series] = {
                "found": True,
                "signal": row.get("signal"),
                "value": row.get("value"),
                "data_date": row.get("data_date"),
                "reason": row.get("reason"),
                "tag": row.get("tag"),
            }
    return {
        "enabled": True,
        "reference_only": True,
        "source_path": str(unified_json_path),
        "series": refs,
    }


def determine_module_signal(
    basket_summary: Dict[str, Any],
    nav_info: Dict[str, Any],
    event_info: Dict[str, Any],
    proxy_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    reasons: List[str] = []
    tags: List[str] = []
    signal = "NONE"

    median_ret5 = basket_summary.get("median_ret5_pct")
    extreme_z_share = basket_summary.get("extreme_z_share")
    median_discount_fresh = nav_info.get("median_discount_pct_fresh")
    nav_cov_fresh = int(nav_info.get("coverage_fresh") or 0)
    alert_recent = int(event_info.get("alert_recent_count") or 0)
    watch_recent = int(event_info.get("watch_recent_count") or 0)

    bizd = next((r for r in proxy_rows if r.get("ticker") == "BIZD"), None)
    bizd_z60 = bizd.get("z60") if bizd else None
    bizd_ret5 = bizd.get("ret5_pct") if bizd else None

    # ALERT rules
    if alert_recent >= 1:
        signal = "ALERT"
        reasons.append(f"recent_manual_event_alert_count={alert_recent}")
        tags.append("EVENT_ALERT")
    elif (
        median_ret5 is not None
        and median_ret5 <= -8.0
        and extreme_z_share is not None
        and extreme_z_share >= 50.0
    ):
        signal = "ALERT"
        reasons.append("bdc_basket_median_ret5<=-8 AND extreme_z_share>=50%")
        tags.append("MARKET_PROXY_STRESS")
    elif (
        median_discount_fresh is not None
        and nav_cov_fresh >= 3
        and median_discount_fresh <= -20.0
    ):
        signal = "ALERT"
        reasons.append("fresh_nav_median_discount<=-20 with coverage>=3")
        tags.append("NAV_DISCOUNT_STRESS")
    elif (
        median_discount_fresh is not None
        and nav_cov_fresh >= 3
        and median_discount_fresh <= -15.0
        and median_ret5 is not None
        and median_ret5 <= -5.0
        and watch_recent >= 1
    ):
        signal = "ALERT"
        reasons.append("fresh_nav_discount<=-15 + basket_ret5<=-5 + recent_watch_event")
        tags.append("COMPOSITE_STRESS")

    # WATCH rules (only if not already ALERT)
    if signal != "ALERT":
        if watch_recent >= 1:
            signal = "WATCH"
            reasons.append(f"recent_manual_event_watch_count={watch_recent}")
            tags.append("EVENT_WATCH")
        elif median_ret5 is not None and median_ret5 <= -4.0:
            signal = "WATCH"
            reasons.append("bdc_basket_median_ret5<=-4")
            tags.append("MARKET_PROXY_WEAK")
        elif extreme_z_share is not None and extreme_z_share >= 40.0:
            signal = "WATCH"
            reasons.append("bdc_basket_extreme_z_share>=40%")
            tags.append("BREADTH_WEAK")
        elif (
            median_discount_fresh is not None
            and nav_cov_fresh >= 3
            and median_discount_fresh <= -10.0
        ):
            signal = "WATCH"
            reasons.append("fresh_nav_median_discount<=-10 with coverage>=3")
            tags.append("NAV_DISCOUNT_WIDE")
        elif bizd_z60 is not None and bizd_z60 <= -2.0:
            signal = "WATCH"
            reasons.append("BIZD z60<=-2")
            tags.append("ETF_PROXY_WEAK")
        elif bizd_ret5 is not None and bizd_ret5 <= -5.0:
            signal = "WATCH"
            reasons.append("BIZD ret5<=-5")
            tags.append("ETF_PROXY_WEAK")

    return {
        "signal": signal,
        "reasons": reasons or ["no_rule_triggered"],
        "tags": tags or ["NONE"],
    }


def infer_confidence(price_rows: List[Dict[str, Any]], nav_info: Dict[str, Any], event_info: Dict[str, Any], basket_tickers: List[str]) -> Dict[str, Any]:
    basket_cov = sum(1 for r in price_rows if r.get("ticker") in basket_tickers and r.get("close") is not None)
    price_conf = "OK" if basket_cov >= max(3, len(basket_tickers) - 1) else ("PARTIAL" if basket_cov >= 2 else "LOW")
    nav_conf = nav_info.get("confidence", "NA")
    event_conf = "OK" if event_info.get("event_count_total", 0) > 0 else "NA"

    # Conservative overall rule
    if price_conf == "LOW":
        overall = "LOW"
    elif nav_conf == "OK" or event_conf == "OK":
        overall = "OK"
    else:
        overall = "PARTIAL"

    return {
        "price_confidence": price_conf,
        "nav_confidence": nav_conf,
        "event_confidence": event_conf,
        "overall_confidence": overall,
        "basket_coverage": basket_cov,
    }


def make_history_row(latest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at_utc": latest["meta"]["generated_at_utc"],
        "module_signal": latest["summary"]["signal"],
        "overall_confidence": latest["summary"]["confidence"]["overall_confidence"],
        "basket_median_ret5_pct": latest["bdc_market_proxy"]["basket_summary"].get("median_ret5_pct"),
        "basket_extreme_z_share": latest["bdc_market_proxy"]["basket_summary"].get("extreme_z_share"),
        "nav_median_discount_pct_fresh": latest["nav_overlay"].get("median_discount_pct_fresh"),
        "nav_coverage_fresh": latest["nav_overlay"].get("coverage_fresh"),
        "event_alert_recent_count": latest["event_overlay"].get("alert_recent_count"),
        "event_watch_recent_count": latest["event_overlay"].get("watch_recent_count"),
        "notes": "append_only_summary_row",
    }


def merge_history(existing: Any, new_row: Dict[str, Any], max_rows: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if isinstance(existing, list):
        rows = [r for r in existing if isinstance(r, dict)]
    rows.append(new_row)
    rows = sorted(rows, key=lambda x: x.get("generated_at_utc", ""))
    if max_rows > 0:
        rows = rows[-max_rows:]
    return rows


def markdown_table(rows: List[Dict[str, Any]], columns: List[Tuple[str, str]]) -> str:
    if not rows:
        return "| note |\n| --- |\n| NA |"
    headers = [c[0] for c in columns]
    keys = [c[1] for c in columns]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        vals = []
        for k in keys:
            v = r.get(k)
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            elif v is None:
                vals.append("NA")
            else:
                vals.append(str(v))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def build_report(latest: Dict[str, Any]) -> str:
    meta = latest["meta"]
    summary = latest["summary"]
    basket = latest["bdc_market_proxy"]["basket_summary"]
    price_rows = latest["bdc_market_proxy"]["items"]
    nav = latest["nav_overlay"]
    events = latest["event_overlay"]
    context = latest["public_credit_context"]

    lines: List[str] = []
    lines.append("# Private Credit Monitor Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- generated_at_utc: `{meta['generated_at_utc']}`")
    lines.append(f"- script: `{meta['script']}`")
    lines.append(f"- script_version: `{meta['script_version']}`")
    lines.append(f"- out_dir: `{meta['out_dir']}`")
    lines.append(f"- signal: **{summary['signal']}**")
    lines.append(f"- overall_confidence: `{summary['confidence']['overall_confidence']}`")
    lines.append(f"- reasons: `{'; '.join(summary['reasons'])}`")
    lines.append(f"- tags: `{','.join(summary['tags'])}`")
    lines.append("")

    lines.append("## 1) BDC Market Proxy")
    for k in [
        "coverage",
        "median_ret1_pct",
        "median_ret5_pct",
        "median_z60",
        "median_drawdown_20d_pct",
        "extreme_z_count",
        "extreme_z_share",
        "ret5_le_minus5_count",
        "ret5_le_minus5_share",
        "below_ma20_count",
        "below_ma20_share",
    ]:
        lines.append(f"- {k}: `{basket.get(k)}`")
    lines.append("")
    lines.append(markdown_table(
        price_rows,
        [
            ("ticker", "ticker"),
            ("class", "class"),
            ("close", "close"),
            ("data_date", "data_date"),
            ("ret1%", "ret1_pct"),
            ("ret5%", "ret5_pct"),
            ("z60", "z60"),
            ("p60", "p60"),
            ("p252", "p252"),
            ("dd20%", "drawdown_20d_pct"),
            ("px_vs_ma20%", "price_vs_ma20_pct"),
            ("source", "source_url"),
            ("note", "note"),
        ],
    ))
    lines.append("")

    lines.append("## 2) NAV Overlay (manual, optional)")
    lines.append(f"- path: `{nav.get('path')}`")
    lines.append(f"- as_of_date: `{nav.get('as_of_date')}`")
    lines.append(f"- confidence: `{nav.get('confidence')}`")
    lines.append(f"- coverage_total: `{nav.get('coverage_total')}`")
    lines.append(f"- coverage_fresh: `{nav.get('coverage_fresh')}`")
    lines.append(f"- median_discount_pct_fresh: `{nav.get('median_discount_pct_fresh')}`")
    lines.append(f"- median_discount_pct_all: `{nav.get('median_discount_pct_all')}`")
    lines.append("")
    lines.append(markdown_table(
        nav.get("items", []),
        [
            ("ticker", "ticker"),
            ("nav", "nav"),
            ("nav_date", "nav_date"),
            ("market_close", "market_close"),
            ("market_date", "market_date"),
            ("premium_discount_pct", "premium_discount_pct"),
            ("nav_age_days", "nav_age_days"),
            ("fresh_for_rule", "fresh_for_rule"),
            ("source", "source_url"),
            ("note", "note"),
        ],
    ))
    lines.append("")

    lines.append("## 3) Event Overlay (manual, optional)")
    lines.append(f"- path: `{events.get('path')}`")
    lines.append(f"- as_of_date: `{events.get('as_of_date')}`")
    lines.append(f"- recent_window_days: `{events.get('recent_window_days')}`")
    lines.append(f"- event_count_total: `{events.get('event_count_total')}`")
    lines.append(f"- event_count_recent: `{events.get('event_count_recent')}`")
    lines.append(f"- alert_recent_count: `{events.get('alert_recent_count')}`")
    lines.append(f"- watch_recent_count: `{events.get('watch_recent_count')}`")
    lines.append(f"- latest_recent_event_date: `{events.get('latest_recent_event_date')}`")
    lines.append("")
    lines.append(markdown_table(
        events.get("events", []),
        [
            ("event_date", "event_date"),
            ("category", "category"),
            ("entity", "entity"),
            ("severity", "severity"),
            ("is_recent", "is_recent"),
            ("title", "title"),
            ("source", "source_url"),
            ("note", "note"),
        ],
    ))
    lines.append("")

    lines.append("## 4) Public Credit Context (reference-only; not recomputed here)")
    lines.append(f"- enabled: `{context.get('enabled')}`")
    lines.append(f"- source_path: `{context.get('source_path')}`")
    lines.append(f"- reference_only: `{context.get('reference_only')}`")
    ctx_rows = []
    for series, row in (context.get("series") or {}).items():
        if row.get("found"):
            ctx_rows.append({"series": series, **row})
        else:
            ctx_rows.append({"series": series, "signal": "NA", "value": None, "data_date": None, "reason": "not_found", "tag": None})
    lines.append("")
    lines.append(markdown_table(
        ctx_rows,
        [
            ("series", "series"),
            ("signal", "signal"),
            ("value", "value"),
            ("data_date", "data_date"),
            ("reason", "reason"),
            ("tag", "tag"),
        ],
    ))
    lines.append("")

    lines.append("## 5) Confidence / DQ")
    conf = summary["confidence"]
    for k, v in conf.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")

    lines.append("## 6) Notes")
    for note in latest.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    inputs_dir = out_dir / "inputs"
    ensure_dir(inputs_dir)

    manual_events_path = Path(args.manual_events) if args.manual_events else inputs_dir / "manual_events.json"
    manual_nav_path = Path(args.manual_nav) if args.manual_nav else inputs_dir / "manual_nav.json"
    unified_json_path = Path(args.unified_json) if args.unified_json else None

    create_manual_event_template(manual_events_path)
    create_manual_nav_template(manual_nav_path)

    tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
    basket_tickers = [t for t in tickers if t in DEFAULT_BDC_TICKERS]
    proxy_tickers = [t for t in tickers if t in DEFAULT_PROXY_TICKERS]
    if not basket_tickers:
        basket_tickers = DEFAULT_BDC_TICKERS.copy()
    if not proxy_tickers:
        proxy_tickers = DEFAULT_PROXY_TICKERS.copy()

    end_date = pd.Timestamp.utcnow().normalize()
    start_date = end_date - pd.Timedelta(days=args.lookback_calendar_days)

    price_rows: List[Dict[str, Any]] = []
    latest_price_by_ticker: Dict[str, Dict[str, Any]] = {}
    source_notes: List[str] = []

    for t in tickers:
        df, source_url, err = fetch_stooq_daily(t, start_date, end_date, timeout=args.timeout)
        stats = compute_price_stats(df, z_window=args.z_window, p_window=args.p_window)
        row = {
            "ticker": t,
            "class": "BDC" if t in basket_tickers else "ETF_PROXY",
            **stats,
            "source_url": source_url,
            "note": err or "OK",
        }
        price_rows.append(row)
        latest_price_by_ticker[t] = row
        if err:
            source_notes.append(f"{t}:{err}")

    basket_summary = compute_basket_summary(price_rows, basket_tickers)
    nav_info = load_manual_nav(manual_nav_path, latest_price_by_ticker, nav_fresh_max_days=args.nav_fresh_max_days)
    event_info = load_manual_events(manual_events_path, recent_days=args.event_recent_days)
    reference_context = load_reference_context(unified_json_path) if unified_json_path else {
        "enabled": False,
        "reference_only": True,
        "note": "disabled",
    }

    signal_info = determine_module_signal(
        basket_summary=basket_summary,
        nav_info=nav_info,
        event_info=event_info,
        proxy_rows=price_rows,
    )
    confidence = infer_confidence(
        price_rows=price_rows,
        nav_info=nav_info,
        event_info=event_info,
        basket_tickers=basket_tickers,
    )

    latest = {
        "meta": {
            "generated_at_utc": UTC_NOW().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "out_dir": str(out_dir),
            "source_policy": "stooq_bdc_proxy + manual_nav_overlay + manual_event_overlay + optional_unified_reference_only",
            "basket_tickers": basket_tickers,
            "proxy_tickers": proxy_tickers,
            "params": {
                "z_window": args.z_window,
                "p_window": args.p_window,
                "lookback_calendar_days": args.lookback_calendar_days,
                "event_recent_days": args.event_recent_days,
                "nav_fresh_max_days": args.nav_fresh_max_days,
            },
        },
        "summary": {
            "signal": signal_info["signal"],
            "reasons": signal_info["reasons"],
            "tags": signal_info["tags"],
            "confidence": confidence,
        },
        "bdc_market_proxy": {
            "status": "OK" if confidence["price_confidence"] != "LOW" else "PARTIAL",
            "items": sorted(price_rows, key=lambda r: (0 if r.get("class") == "BDC" else 1, r.get("ticker"))),
            "basket_summary": basket_summary,
        },
        "nav_overlay": nav_info,
        "event_overlay": event_info,
        "public_credit_context": reference_context,
        "notes": [
            "This module is display-only / advisory-only by design.",
            "HY spread / HYG-IEF / OFR_FSI are NOT recomputed here.",
            "Manual overlays are expected for event flags and latest NAV values.",
            f"data_fetch_notes: {'; '.join(source_notes) if source_notes else 'all price fetches OK'}",
        ],
    }

    latest_json_path = out_dir / "latest.json"
    history_json_path = out_dir / "history.json"
    report_md_path = out_dir / "report.md"

    write_json(latest_json_path, latest)
    existing_history = read_json(history_json_path, default=[])
    history = merge_history(existing_history, make_history_row(latest), max_rows=args.history_max_rows)
    write_json(history_json_path, history)
    report_text = build_report(latest)
    report_md_path.write_text(report_text, encoding="utf-8")

    print(json.dumps({
        "status": "OK",
        "latest_json": str(latest_json_path),
        "history_json": str(history_json_path),
        "report_md": str(report_md_path),
        "manual_events": str(manual_events_path),
        "manual_nav": str(manual_nav_path),
        "signal": latest["summary"]["signal"],
        "confidence": latest["summary"]["confidence"]["overall_confidence"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
