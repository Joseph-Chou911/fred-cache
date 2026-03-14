#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_private_credit_monitor.py (v1.4)

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

v1.4 changes
------------
- Keep v1.3 Public Credit Context extraction fixes
- Add auto NAV fetch from official SEC endpoints:
  * company_tickers.json -> ticker to CIK
  * submissions JSON -> recent filing candidates
  * filing document text regex -> NAV per share extraction
- Manual NAV remains supported and overrides auto NAV for same ticker
- Event overlay remains manual

Outputs
-------
All outputs go to a dedicated folder (default: private_credit_cache/):
- latest.json
- history.json
- report.md
- inputs/manual_events.json   (template created if absent)
- inputs/manual_nav.json      (template created if absent)

Data layers
-----------
1) BDC market proxy (auto)
2) NAV overlay (manual + optional auto SEC)
3) Event overlay (manual, optional)
4) Optional public-credit context (reference-only, no recomputation)

Dependencies
------------
- Python 3.11+
- requests
- pandas
- numpy
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


SCRIPT_NAME = "build_private_credit_monitor.py"
SCRIPT_VERSION = "v1.4"
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

# Public Credit Context preferred module mapping
PREFERRED_CONTEXT_MODULES: Dict[str, List[str]] = {
    "BAMLH0A0HYM2": ["fred_cache", "market_cache"],
    "HYG_IEF_RATIO": ["market_cache", "fred_cache"],
    "OFR_FSI": ["market_cache", "fred_cache"],
}

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_ARCHIVES_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"

AUTO_NAV_ALLOWED_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A", "8-K", "8-K/A"}

NAV_REGEX_PATTERNS = [
    re.compile(r"net asset value per share[^0-9$]{0,120}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)", re.I),
    re.compile(r"net assets per share[^0-9$]{0,120}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)", re.I),
    re.compile(r"nav per share[^0-9$]{0,120}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)", re.I),
    re.compile(r"net asset value[^0-9$]{0,80}of[^0-9$]{0,40}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*per share", re.I),
]

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


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

    # auto NAV from SEC
    p.add_argument("--nav-auto-source", default="sec", choices=["sec", "off"], help="Auto NAV source")
    p.add_argument("--sec-user-agent", default="private-credit-monitor/1.4 contact@example.com", help="SEC User-Agent header")
    p.add_argument("--nav-auto-max-filings", type=int, default=6, help="Max recent filings to scan per ticker for NAV extraction")
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
            "Template rows are excluded from counts/statistics until they become valid.",
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
            "Template rows are excluded from counts/statistics until they become valid.",
            "Manual valid rows override auto SEC NAV rows for the same ticker.",
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


def is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def pick_first(row: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in row and row.get(k) not in [None, ""]:
            return row.get(k)
    return None


def make_requests_session(user_agent: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if user_agent:
        headers["User-Agent"] = user_agent
    s.headers.update(headers)
    return s


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

    if len(closes) >= 20:
        peak20 = float(closes.tail(20).max())
        dd20 = safe_pct(last_close, peak20)
    else:
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

        if sev not in SEVERITY_ORDER:
            sev = "WATCH"
        if cat not in EVENT_CATEGORIES:
            cat = "other"

        has_meaningful_text = any([
            is_nonempty_str(ev.get("entity")),
            is_nonempty_str(ev.get("title")),
            is_nonempty_str(ev.get("source_url")),
            is_nonempty_str(ev.get("note")),
        ])

        valid_for_stats = bool(event_date is not None and has_meaningful_text)
        is_recent = bool(valid_for_stats and event_date >= recent_cutoff)

        out_rows.append({
            "event_date": event_date.strftime("%Y-%m-%d") if event_date is not None else None,
            "category": cat,
            "entity": ev.get("entity"),
            "severity": sev,
            "title": ev.get("title"),
            "source_url": ev.get("source_url"),
            "note": ev.get("note"),
            "is_recent": is_recent,
            "valid_for_stats": valid_for_stats,
            "template_excluded": not valid_for_stats,
        })

    valid_rows = [r for r in out_rows if r.get("valid_for_stats")]
    recent_rows = [r for r in valid_rows if r.get("is_recent")]

    alert_recent = sum(1 for r in recent_rows if r.get("severity") == "ALERT")
    watch_recent = sum(1 for r in recent_rows if r.get("severity") == "WATCH")

    latest_recent_date = None
    dated_recent = [parse_date(r.get("event_date")) for r in recent_rows if r.get("event_date")]
    dated_recent = [d for d in dated_recent if d is not None]
    if dated_recent:
        latest_recent_date = max(dated_recent).strftime("%Y-%m-%d")

    raw_row_count = len(out_rows)
    valid_count = len(valid_rows)
    template_excluded_count = raw_row_count - valid_count

    return {
        "path": str(path),
        "schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "as_of_date": raw.get("as_of_date") if isinstance(raw, dict) else None,
        "notes": raw.get("notes") if isinstance(raw, dict) else None,
        "recent_window_days": recent_days,
        "raw_row_count": raw_row_count,
        "template_excluded_count": template_excluded_count,
        "event_count_total": valid_count,
        "event_count_recent": len(recent_rows),
        "alert_recent_count": alert_recent,
        "watch_recent_count": watch_recent,
        "latest_recent_event_date": latest_recent_date,
        "events": sorted(out_rows, key=lambda x: (x.get("event_date") or "", x.get("severity") or ""), reverse=True),
    }


def make_nav_overlay_row(
    *,
    ticker: str,
    nav: Optional[float],
    nav_date: Optional[pd.Timestamp],
    source_url: Optional[str],
    note: Optional[str],
    source_kind: str,
    latest_price_by_ticker: Dict[str, Dict[str, Any]],
    nav_fresh_max_days: int,
) -> Dict[str, Any]:
    ticker = str(ticker or "").upper().strip()
    px = latest_price_by_ticker.get(ticker, {})
    market_close = to_float(px.get("close"))
    market_date = parse_date(px.get("data_date"))

    valid_for_stats = bool(ticker and nav is not None and nav > 0 and nav_date is not None)
    premium_discount_pct = safe_pct(market_close, nav) if (valid_for_stats and market_close is not None) else None

    nav_age_days = None
    fresh_for_rule = False
    if valid_for_stats and nav_date is not None and market_date is not None:
        nav_age_days = int((market_date - nav_date).days)
        fresh_for_rule = bool(nav_age_days <= nav_fresh_max_days and premium_discount_pct is not None)

    return {
        "ticker": ticker,
        "nav": safe_num(nav),
        "nav_date": nav_date.strftime("%Y-%m-%d") if nav_date is not None else None,
        "market_close": safe_num(market_close),
        "market_date": market_date.strftime("%Y-%m-%d") if market_date is not None else None,
        "premium_discount_pct": safe_num(premium_discount_pct),
        "nav_age_days": nav_age_days,
        "fresh_for_rule": fresh_for_rule,
        "valid_for_stats": valid_for_stats,
        "template_excluded": not valid_for_stats,
        "source_url": source_url,
        "note": note,
        "source_kind": source_kind,
    }


def load_manual_nav_rows(
    path: Path,
    latest_price_by_ticker: Dict[str, Dict[str, Any]],
    nav_fresh_max_days: int,
) -> Dict[str, Any]:
    raw = read_json(path, default={}) or {}
    items = raw.get("items", []) if isinstance(raw, dict) else []
    rows: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        row = make_nav_overlay_row(
            ticker=str(item.get("ticker", "")).upper().strip(),
            nav=to_float(item.get("nav")),
            nav_date=parse_date(item.get("nav_date")),
            source_url=item.get("source_url"),
            note=item.get("note"),
            source_kind="manual",
            latest_price_by_ticker=latest_price_by_ticker,
            nav_fresh_max_days=nav_fresh_max_days,
        )
        rows.append(row)

    raw_row_count = len(rows)
    valid_count = sum(1 for r in rows if r.get("valid_for_stats"))
    template_excluded_count = raw_row_count - valid_count

    return {
        "path": str(path),
        "schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "as_of_date": raw.get("as_of_date") if isinstance(raw, dict) else None,
        "notes": raw.get("notes") if isinstance(raw, dict) else None,
        "raw_row_count": raw_row_count,
        "template_excluded_count": template_excluded_count,
        "items": rows,
    }


def sec_fetch_json(session: requests.Session, url: str, timeout: int) -> Any:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def sec_fetch_text(session: requests.Session, url: str, timeout: int) -> str:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def get_sec_ticker_to_cik_map(session: requests.Session, timeout: int) -> Dict[str, str]:
    raw = sec_fetch_json(session, SEC_TICKER_MAP_URL, timeout=timeout)
    out: Dict[str, str] = {}
    if isinstance(raw, dict):
        for _, item in raw.items():
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "")).upper().strip()
            cik_str = str(item.get("cik_str", "")).strip()
            if ticker and cik_str.isdigit():
                out[ticker] = cik_str.zfill(10)
    return out


def get_sec_filing_candidates(
    session: requests.Session,
    cik10: str,
    timeout: int,
) -> List[Dict[str, Any]]:
    url = SEC_SUBMISSIONS_URL.format(cik10=cik10)
    raw = sec_fetch_json(session, url, timeout=timeout)

    recent = (((raw or {}).get("filings") or {}).get("recent") or {})
    forms = recent.get("form", []) or []
    filing_dates = recent.get("filingDate", []) or []
    accession_numbers = recent.get("accessionNumber", []) or []
    primary_documents = recent.get("primaryDocument", []) or []

    n = min(len(forms), len(filing_dates), len(accession_numbers), len(primary_documents))
    out: List[Dict[str, Any]] = []

    for i in range(n):
        form = str(forms[i] or "").strip().upper()
        if form not in AUTO_NAV_ALLOWED_FORMS:
            continue

        filing_date = str(filing_dates[i] or "").strip()
        accession = str(accession_numbers[i] or "").strip()
        primary_doc = str(primary_documents[i] or "").strip()
        if not filing_date or not accession or not primary_doc:
            continue

        out.append({
            "form": form,
            "filing_date": filing_date,
            "accession_number": accession,
            "primary_document": primary_doc,
            "source_url": SEC_ARCHIVES_DOC_URL.format(
                cik_int=str(int(cik10)),
                accession_nodash=accession.replace("-", ""),
                primary_doc=primary_doc,
            ),
        })

    # recent arrays are usually latest-first; keep order
    return out


def filing_html_to_text(raw_text: str) -> str:
    text = html_lib.unescape(raw_text or "")
    text = HTML_TAG_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def extract_nav_per_share_from_text(text: str, market_close: Optional[float] = None) -> Tuple[Optional[float], Optional[str]]:
    if not text:
        return None, None

    candidates: List[Tuple[float, str]] = []

    for pat in NAV_REGEX_PATTERNS:
        for m in pat.finditer(text):
            val = to_float(m.group(1))
            if val is None:
                continue
            if not (0.5 <= val <= 100.0):
                continue
            candidates.append((float(val), pat.pattern))

    if not candidates:
        return None, None

    # dedupe while keeping first pattern hit
    dedup: List[Tuple[float, str]] = []
    seen_vals = set()
    for val, pat in candidates:
        key = round(val, 4)
        if key in seen_vals:
            continue
        seen_vals.add(key)
        dedup.append((val, pat))

    if market_close is None or market_close <= 0:
        best_val, best_pat = dedup[0]
        return round(best_val, 6), best_pat

    def score(item: Tuple[float, str]) -> float:
        val = item[0]
        ratio = val / market_close if market_close > 0 else 1.0
        if ratio <= 0:
            return 1e9
        return abs(math.log(ratio))

    best_val, best_pat = sorted(dedup, key=score)[0]
    return round(best_val, 6), best_pat


def fetch_auto_nav_rows_from_sec(
    tickers: List[str],
    latest_price_by_ticker: Dict[str, Dict[str, Any]],
    nav_fresh_max_days: int,
    timeout: int,
    sec_user_agent: str,
    nav_auto_max_filings: int,
) -> Dict[str, Any]:
    session = make_requests_session(sec_user_agent)

    out_rows: List[Dict[str, Any]] = []
    notes: List[str] = []
    attempted = 0
    found = 0

    try:
        ticker_map = get_sec_ticker_to_cik_map(session, timeout=timeout)
    except Exception as e:
        return {
            "enabled": True,
            "source": "sec_filings_regex",
            "attempted_count": 0,
            "found_count": 0,
            "rows": [],
            "notes": [f"ERR:ticker_map:{type(e).__name__}:{str(e)[:160]}"],
        }

    for ticker in tickers:
        if ticker not in DEFAULT_BDC_TICKERS:
            continue
        attempted += 1

        cik10 = ticker_map.get(ticker)
        market_close = to_float((latest_price_by_ticker.get(ticker) or {}).get("close"))

        if not cik10:
            notes.append(f"{ticker}:ERR:no_cik")
            continue

        try:
            candidates = get_sec_filing_candidates(session, cik10, timeout=timeout)
        except Exception as e:
            notes.append(f"{ticker}:ERR:submissions:{type(e).__name__}:{str(e)[:120]}")
            continue

        if not candidates:
            notes.append(f"{ticker}:ERR:no_recent_filing_candidates")
            continue

        matched = False
        for cand in candidates[:max(1, nav_auto_max_filings)]:
            url = cand["source_url"]
            try:
                raw_text = sec_fetch_text(session, url, timeout=timeout)
                text = filing_html_to_text(raw_text)
                nav_val, pat = extract_nav_per_share_from_text(text, market_close=market_close)
                if nav_val is None:
                    continue

                nav_date = parse_date(cand.get("filing_date"))
                note = f"auto_sec:{cand.get('form')}:{cand.get('filing_date')}:pattern_match"
                if pat:
                    note += f":regex={pat[:80]}"

                row = make_nav_overlay_row(
                    ticker=ticker,
                    nav=nav_val,
                    nav_date=nav_date,
                    source_url=url,
                    note=note,
                    source_kind="auto_sec",
                    latest_price_by_ticker=latest_price_by_ticker,
                    nav_fresh_max_days=nav_fresh_max_days,
                )
                out_rows.append(row)
                found += 1
                matched = True
                notes.append(f"{ticker}:OK:{cand.get('form')}:{cand.get('filing_date')}")
                break
            except Exception as e:
                notes.append(f"{ticker}:WARN:doc_fetch:{cand.get('form')}:{type(e).__name__}:{str(e)[:100]}")
                continue

        if not matched:
            notes.append(f"{ticker}:ERR:no_nav_match")

    return {
        "enabled": True,
        "source": "sec_filings_regex",
        "attempted_count": attempted,
        "found_count": found,
        "rows": out_rows,
        "notes": notes,
    }


def build_nav_overlay(
    manual_nav_path: Path,
    latest_price_by_ticker: Dict[str, Dict[str, Any]],
    nav_fresh_max_days: int,
    auto_nav_result: Dict[str, Any],
) -> Dict[str, Any]:
    manual = load_manual_nav_rows(manual_nav_path, latest_price_by_ticker, nav_fresh_max_days)
    manual_rows = manual["items"]
    auto_rows = list(auto_nav_result.get("rows") or [])

    # effective rows: auto first, then manual valid rows override same ticker
    effective_by_ticker: Dict[str, Dict[str, Any]] = {}

    for r in auto_rows:
        if r.get("valid_for_stats"):
            effective_by_ticker[r["ticker"]] = r

    manual_override_tickers: List[str] = []
    for r in manual_rows:
        if r.get("valid_for_stats"):
            if r["ticker"] in effective_by_ticker:
                manual_override_tickers.append(r["ticker"])
            effective_by_ticker[r["ticker"]] = r

    effective_rows = list(effective_by_ticker.values())
    invalid_manual_rows = [r for r in manual_rows if not r.get("valid_for_stats")]

    display_rows = sorted(
        effective_rows + invalid_manual_rows,
        key=lambda x: (
            0 if x.get("valid_for_stats") else 1,
            x.get("ticker") or "",
        )
    )

    rows_with_discount = [r for r in effective_rows if r.get("premium_discount_pct") is not None]
    fresh_rows = [r for r in rows_with_discount if r.get("fresh_for_rule")]

    median_discount_fresh = np.median([float(r["premium_discount_pct"]) for r in fresh_rows]) if fresh_rows else None
    median_discount_all = np.median([float(r["premium_discount_pct"]) for r in rows_with_discount]) if rows_with_discount else None

    if len(fresh_rows) >= 3:
        nav_confidence = "OK"
    elif len(fresh_rows) >= 1:
        nav_confidence = "PARTIAL"
    elif len(effective_rows) >= 1:
        nav_confidence = "LIMITED"
    elif int(manual.get("raw_row_count") or 0) > 0:
        nav_confidence = "TEMPLATE_ONLY"
    else:
        nav_confidence = "NA"

    return {
        "path": str(manual_nav_path),
        "schema_version": manual.get("schema_version"),
        "as_of_date": manual.get("as_of_date"),
        "nav_fresh_max_days": nav_fresh_max_days,
        "raw_row_count": manual.get("raw_row_count"),
        "template_excluded_count": manual.get("template_excluded_count"),
        "manual_valid_count": sum(1 for r in manual_rows if r.get("valid_for_stats")),
        "auto_enabled": bool(auto_nav_result.get("enabled")),
        "auto_source": auto_nav_result.get("source"),
        "auto_attempted_count": int(auto_nav_result.get("attempted_count") or 0),
        "auto_found_count": int(auto_nav_result.get("found_count") or 0),
        "auto_notes": auto_nav_result.get("notes") or [],
        "manual_override_tickers": sorted(set(manual_override_tickers)),
        "coverage_total": len(effective_rows),
        "coverage_fresh": len(fresh_rows),
        "median_discount_pct_fresh": safe_num(median_discount_fresh),
        "median_discount_pct_all": safe_num(median_discount_all),
        "confidence": nav_confidence,
        "items": display_rows,
    }


def collect_series_candidates(obj: Any, target_series: str, out: List[Dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if str(obj.get("series", "")).upper() == target_series.upper():
            out.append(obj)
        for v in obj.values():
            collect_series_candidates(v, target_series, out)
    elif isinstance(obj, list):
        for item in obj:
            collect_series_candidates(item, target_series, out)


def score_series_candidate(row: Dict[str, Any]) -> int:
    score = 0
    if pick_first(row, ["signal_level", "signal"]) not in [None, ""]:
        score += 100
    if row.get("value") not in [None, ""]:
        score += 10
    if row.get("data_date") not in [None, ""]:
        score += 5
    if row.get("reason") not in [None, ""]:
        score += 2
    if row.get("tag") not in [None, ""]:
        score += 1
    return score


def normalize_context_row(row: Dict[str, Any], source_module: str) -> Dict[str, Any]:
    signal = pick_first(row, ["signal_level", "signal", "status", "state"])
    if signal in [None, ""]:
        signal = "NA_SOURCE_MISSING"

    return {
        "signal": signal,
        "value": pick_first(row, ["value", "close", "last", "last_value"]),
        "data_date": pick_first(row, ["data_date", "date", "last_date"]),
        "reason": pick_first(row, ["reason", "notes"]),
        "tag": pick_first(row, ["tag", "tags"]),
        "source_module": source_module,
    }


def get_best_candidate_from_obj(obj: Any, series: str) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    collect_series_candidates(obj, series, candidates)
    if not candidates:
        return None
    return sorted(candidates, key=score_series_candidate, reverse=True)[0]


def get_module_rows(unified_raw: Dict[str, Any], module_name: str) -> List[Dict[str, Any]]:
    try:
        rows = (
            unified_raw.get("modules", {})
            .get(module_name, {})
            .get("dashboard_latest", {})
            .get("rows", [])
        )
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def find_series_in_rows(rows: List[Dict[str, Any]], series: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if isinstance(row, dict) and str(row.get("series", "")).upper() == series.upper():
            return row
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
    refs: Dict[str, Any] = {}

    for series in ["BAMLH0A0HYM2", "HYG_IEF_RATIO", "OFR_FSI"]:
        preferred_modules = PREFERRED_CONTEXT_MODULES.get(series, [])

        chosen_row: Optional[Dict[str, Any]] = None
        chosen_module: Optional[str] = None

        for module_name in preferred_modules:
            rows = get_module_rows(raw, module_name)
            row = find_series_in_rows(rows, series)
            if row is None:
                continue
            chosen_row = row
            chosen_module = module_name
            break

        if chosen_row is None:
            fallback = get_best_candidate_from_obj(raw, series)
            if fallback is not None:
                chosen_row = fallback
                chosen_module = "fallback_recursive"

        if chosen_row is None:
            refs[series] = {"found": False}
        else:
            refs[series] = {"found": True, **normalize_context_row(chosen_row, chosen_module or "unknown")}

    return {
        "enabled": True,
        "reference_only": True,
        "source_path": str(unified_json_path),
        "series": refs,
    }


def determine_proxy_signal(
    basket_summary: Dict[str, Any],
    proxy_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    reasons: List[str] = []
    tags: List[str] = []
    signal = "NONE"

    median_ret5 = basket_summary.get("median_ret5_pct")
    extreme_z_share = basket_summary.get("extreme_z_share")
    ret5_bad_share = basket_summary.get("ret5_le_minus5_share")
    below_ma20_share = basket_summary.get("below_ma20_share")

    bizd = next((r for r in proxy_rows if r.get("ticker") == "BIZD"), None)
    bizd_z60 = bizd.get("z60") if bizd else None
    bizd_ret5 = bizd.get("ret5_pct") if bizd else None

    if (
        median_ret5 is not None
        and median_ret5 <= -8.0
        and extreme_z_share is not None
        and extreme_z_share >= 50.0
        and below_ma20_share is not None
        and below_ma20_share >= 80.0
    ):
        signal = "ALERT"
        reasons.append("bdc_basket_median_ret5<=-8 AND extreme_z_share>=50% AND below_ma20_share>=80%")
        tags.append("MARKET_PROXY_STRESS")

    if signal != "ALERT":
        if (
            median_ret5 is not None
            and median_ret5 <= -4.0
            and below_ma20_share is not None
            and below_ma20_share >= 80.0
        ):
            signal = "WATCH"
            reasons.append("bdc_basket_median_ret5<=-4 AND below_ma20_share>=80%")
            tags.append("MARKET_PROXY_WEAK")
        elif extreme_z_share is not None and extreme_z_share >= 40.0:
            signal = "WATCH"
            reasons.append("bdc_basket_extreme_z_share>=40%")
            tags.append("BREADTH_WEAK")
        elif ret5_bad_share is not None and ret5_bad_share >= 40.0:
            signal = "WATCH"
            reasons.append("bdc_basket_ret5_le_minus5_share>=40%")
            tags.append("BREADTH_WEAK")
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
        "reasons": reasons or ["no_proxy_rule_triggered"],
        "tags": tags or ["NONE"],
    }


def determine_structural_signal(
    nav_info: Dict[str, Any],
    event_info: Dict[str, Any],
) -> Dict[str, Any]:
    reasons: List[str] = []
    tags: List[str] = []
    signal = "NONE"

    median_discount_fresh = nav_info.get("median_discount_pct_fresh")
    nav_cov_fresh = int(nav_info.get("coverage_fresh") or 0)
    alert_recent = int(event_info.get("alert_recent_count") or 0)
    watch_recent = int(event_info.get("watch_recent_count") or 0)

    if alert_recent >= 1:
        signal = "ALERT"
        reasons.append(f"recent_manual_event_alert_count={alert_recent}")
        tags.append("EVENT_ALERT")
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
        and watch_recent >= 1
    ):
        signal = "ALERT"
        reasons.append("fresh_nav_discount<=-15 with coverage>=3 + recent_watch_event")
        tags.append("COMPOSITE_STRESS")

    if signal != "ALERT":
        if watch_recent >= 1:
            signal = "WATCH"
            reasons.append(f"recent_manual_event_watch_count={watch_recent}")
            tags.append("EVENT_WATCH")
        elif (
            median_discount_fresh is not None
            and nav_cov_fresh >= 3
            and median_discount_fresh <= -10.0
        ):
            signal = "WATCH"
            reasons.append("fresh_nav_median_discount<=-10 with coverage>=3")
            tags.append("NAV_DISCOUNT_WIDE")

    return {
        "signal": signal,
        "reasons": reasons or ["no_structural_rule_triggered"],
        "tags": tags or ["NONE"],
    }


def combine_signals(proxy_info: Dict[str, Any], structural_info: Dict[str, Any]) -> Dict[str, Any]:
    proxy_signal = proxy_info["signal"]
    structural_signal = structural_info["signal"]

    proxy_rank = SEVERITY_ORDER.get(proxy_signal, 0)
    structural_rank = SEVERITY_ORDER.get(structural_signal, 0)

    if max(proxy_rank, structural_rank) == 2:
        combined_signal = "ALERT"
    elif max(proxy_rank, structural_rank) == 1:
        combined_signal = "WATCH"
    else:
        combined_signal = "NONE"

    if proxy_rank > 0 and structural_rank == 0:
        basis = "PROXY_ONLY"
    elif proxy_rank == 0 and structural_rank > 0:
        basis = "STRUCTURAL_ONLY"
    elif proxy_rank > 0 and structural_rank > 0:
        basis = "MIXED"
    else:
        basis = "NONE"

    reasons = []
    tags = []
    if proxy_rank > 0:
        reasons.extend([f"proxy:{x}" for x in proxy_info.get("reasons", [])])
        tags.extend([f"proxy:{x}" for x in proxy_info.get("tags", [])])
    if structural_rank > 0:
        reasons.extend([f"structural:{x}" for x in structural_info.get("reasons", [])])
        tags.extend([f"structural:{x}" for x in structural_info.get("tags", [])])

    if not reasons:
        reasons = ["no_rule_triggered"]
    if not tags:
        tags = ["NONE"]

    return {
        "combined_signal": combined_signal,
        "signal_basis": basis,
        "reasons": reasons,
        "tags": tags,
    }


def infer_confidence(
    price_rows: List[Dict[str, Any]],
    nav_info: Dict[str, Any],
    event_info: Dict[str, Any],
    basket_tickers: List[str],
) -> Dict[str, Any]:
    basket_cov = sum(1 for r in price_rows if r.get("ticker") in basket_tickers and r.get("close") is not None)

    price_conf = "OK" if basket_cov >= max(3, len(basket_tickers) - 1) else ("PARTIAL" if basket_cov >= 2 else "LOW")
    nav_conf = nav_info.get("confidence", "NA")

    event_valid_total = int(event_info.get("event_count_total") or 0)
    event_raw_count = int(event_info.get("raw_row_count") or 0)
    if event_valid_total >= 1:
        event_conf = "OK"
    elif event_raw_count >= 1:
        event_conf = "TEMPLATE_ONLY"
    else:
        event_conf = "NA"

    if nav_conf == "OK" and event_conf == "OK":
        structural_conf = "OK"
    elif nav_conf in {"OK", "PARTIAL", "LIMITED"} or event_conf == "OK":
        structural_conf = "PARTIAL"
    elif nav_conf == "TEMPLATE_ONLY" or event_conf == "TEMPLATE_ONLY":
        structural_conf = "PROXY_ONLY"
    else:
        structural_conf = "NA"

    if price_conf == "LOW":
        overall = "LOW"
    elif structural_conf == "OK":
        overall = "OK"
    elif structural_conf == "PARTIAL":
        overall = "PARTIAL"
    elif price_conf == "OK":
        overall = "PROXY_ONLY"
    else:
        overall = "PARTIAL"

    return {
        "price_confidence": price_conf,
        "nav_confidence": nav_conf,
        "event_confidence": event_conf,
        "structural_confidence": structural_conf,
        "overall_confidence": overall,
        "basket_coverage": basket_cov,
    }


def make_history_row(latest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at_utc": latest["meta"]["generated_at_utc"],
        "proxy_signal": latest["summary"]["proxy_signal"],
        "structural_signal": latest["summary"]["structural_signal"],
        "combined_signal": latest["summary"]["combined_signal"],
        "signal_basis": latest["summary"]["signal_basis"],
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
    lines.append(f"- proxy_signal: **{summary['proxy_signal']}**")
    lines.append(f"- structural_signal: **{summary['structural_signal']}**")
    lines.append(f"- combined_signal: **{summary['combined_signal']}**")
    lines.append(f"- signal_basis: `{summary['signal_basis']}`")
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

    lines.append("## 2) NAV Overlay (manual + auto SEC, optional)")
    lines.append(f"- path: `{nav.get('path')}`")
    lines.append(f"- as_of_date: `{nav.get('as_of_date')}`")
    lines.append(f"- confidence: `{nav.get('confidence')}`")
    lines.append(f"- raw_row_count: `{nav.get('raw_row_count')}`")
    lines.append(f"- template_excluded_count: `{nav.get('template_excluded_count')}`")
    lines.append(f"- manual_valid_count: `{nav.get('manual_valid_count')}`")
    lines.append(f"- auto_enabled: `{nav.get('auto_enabled')}`")
    lines.append(f"- auto_source: `{nav.get('auto_source')}`")
    lines.append(f"- auto_attempted_count: `{nav.get('auto_attempted_count')}`")
    lines.append(f"- auto_found_count: `{nav.get('auto_found_count')}`")
    lines.append(f"- manual_override_tickers: `{nav.get('manual_override_tickers')}`")
    lines.append(f"- coverage_total: `{nav.get('coverage_total')}`")
    lines.append(f"- coverage_fresh: `{nav.get('coverage_fresh')}`")
    lines.append(f"- median_discount_pct_fresh: `{nav.get('median_discount_pct_fresh')}`")
    lines.append(f"- median_discount_pct_all: `{nav.get('median_discount_pct_all')}`")
    lines.append("")
    lines.append(markdown_table(
        nav.get("items", []),
        [
            ("ticker", "ticker"),
            ("source_kind", "source_kind"),
            ("nav", "nav"),
            ("nav_date", "nav_date"),
            ("market_close", "market_close"),
            ("market_date", "market_date"),
            ("premium_discount_pct", "premium_discount_pct"),
            ("nav_age_days", "nav_age_days"),
            ("fresh_for_rule", "fresh_for_rule"),
            ("valid_for_stats", "valid_for_stats"),
            ("template_excluded", "template_excluded"),
            ("source", "source_url"),
            ("note", "note"),
        ],
    ))
    if nav.get("auto_notes"):
        lines.append("")
        lines.append("### NAV auto fetch notes")
        for note in nav.get("auto_notes", []):
            lines.append(f"- {note}")
    lines.append("")

    lines.append("## 3) Event Overlay (manual, optional)")
    lines.append(f"- path: `{events.get('path')}`")
    lines.append(f"- as_of_date: `{events.get('as_of_date')}`")
    lines.append(f"- recent_window_days: `{events.get('recent_window_days')}`")
    lines.append(f"- raw_row_count: `{events.get('raw_row_count')}`")
    lines.append(f"- template_excluded_count: `{events.get('template_excluded_count')}`")
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
            ("valid_for_stats", "valid_for_stats"),
            ("template_excluded", "template_excluded"),
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
            ctx_rows.append({
                "series": series,
                "signal": "NA",
                "value": None,
                "data_date": None,
                "reason": "not_found",
                "tag": None,
                "source_module": None,
            })
    lines.append("")
    lines.append(markdown_table(
        ctx_rows,
        [
            ("series", "series"),
            ("source_module", "source_module"),
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

    if args.nav_auto_source == "sec":
        auto_nav_result = fetch_auto_nav_rows_from_sec(
            tickers=tickers,
            latest_price_by_ticker=latest_price_by_ticker,
            nav_fresh_max_days=args.nav_fresh_max_days,
            timeout=args.timeout,
            sec_user_agent=args.sec_user_agent,
            nav_auto_max_filings=args.nav_auto_max_filings,
        )
    else:
        auto_nav_result = {
            "enabled": False,
            "source": "off",
            "attempted_count": 0,
            "found_count": 0,
            "rows": [],
            "notes": ["auto_nav_disabled"],
        }

    nav_info = build_nav_overlay(
        manual_nav_path=manual_nav_path,
        latest_price_by_ticker=latest_price_by_ticker,
        nav_fresh_max_days=args.nav_fresh_max_days,
        auto_nav_result=auto_nav_result,
    )
    event_info = load_manual_events(manual_events_path, recent_days=args.event_recent_days)
    reference_context = load_reference_context(unified_json_path) if unified_json_path else {
        "enabled": False,
        "reference_only": True,
        "note": "disabled",
    }

    proxy_signal_info = determine_proxy_signal(
        basket_summary=basket_summary,
        proxy_rows=price_rows,
    )
    structural_signal_info = determine_structural_signal(
        nav_info=nav_info,
        event_info=event_info,
    )
    combined_signal_info = combine_signals(
        proxy_info=proxy_signal_info,
        structural_info=structural_signal_info,
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
            "source_policy": "stooq_bdc_proxy + manual_nav_overlay + auto_sec_nav + manual_event_overlay + optional_unified_reference_only",
            "basket_tickers": basket_tickers,
            "proxy_tickers": proxy_tickers,
            "params": {
                "z_window": args.z_window,
                "p_window": args.p_window,
                "lookback_calendar_days": args.lookback_calendar_days,
                "event_recent_days": args.event_recent_days,
                "nav_fresh_max_days": args.nav_fresh_max_days,
                "nav_auto_source": args.nav_auto_source,
                "nav_auto_max_filings": args.nav_auto_max_filings,
            },
        },
        "summary": {
            "signal": combined_signal_info["combined_signal"],  # backward compatibility
            "proxy_signal": proxy_signal_info["signal"],
            "structural_signal": structural_signal_info["signal"],
            "combined_signal": combined_signal_info["combined_signal"],
            "signal_basis": combined_signal_info["signal_basis"],
            "proxy_reasons": proxy_signal_info["reasons"],
            "structural_reasons": structural_signal_info["reasons"],
            "reasons": combined_signal_info["reasons"],
            "proxy_tags": proxy_signal_info["tags"],
            "structural_tags": structural_signal_info["tags"],
            "tags": combined_signal_info["tags"],
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
            "Manual overlays are expected for event flags and may override auto NAV values.",
            "Template / invalid manual rows are excluded from coverage/count/median statistics.",
            "combined_signal should be interpreted together with signal_basis and structural_confidence.",
            "Public Credit Context mirrors unified signal from preferred source modules when available.",
            "Auto NAV from SEC uses heuristic regex extraction on official filing text and may fail; manual valid rows override auto rows.",
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
        "signal": latest["summary"]["combined_signal"],
        "signal_basis": latest["summary"]["signal_basis"],
        "confidence": latest["summary"]["confidence"]["overall_confidence"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()