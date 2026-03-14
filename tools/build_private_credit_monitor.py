#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_private_credit_monitor.py (v1.11c)

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

v1.11c changes
--------------
- Keep v1.11b structure / audit philosophy
- Fix doc_period_anchor selection:
  * choose the best anchor <= filing_date when possible
  * prefer period-ended / year-ended anchors over generic as-of anchors
- Fix candidate_value_role inference:
  * use match-local clause instead of full large snippet
  * reduce false "comparison" classification caused by unrelated nearby text
- Keep filing-date-only fallback as REVIEW_ONLY
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


SCRIPT_NAME = "build_private_credit_monitor.py"
SCRIPT_VERSION = "v1.11c"
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

PREFERRED_CONTEXT_MODULES: Dict[str, List[str]] = {
    "BAMLH0A0HYM2": ["fred_cache", "market_cache"],
    "HYG_IEF_RATIO": ["market_cache", "fred_cache"],
    "OFR_FSI": ["market_cache", "fred_cache"],
}

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_ARCHIVES_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"
SEC_ARCHIVES_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"

AUTO_NAV_ALLOWED_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A", "8-K", "8-K/A"}

REQUEST_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
REQUEST_RETRY_SLEEP_SECONDS = [2, 4, 8]

DIRECT_NAV_REGEX_SPECS = [
    (
        "strict_nav_with_dollar",
        re.compile(
            r"(?:net asset value per share|net assets per share|nav per share)"
            r"[^0-9$]{0,60}\$([0-9]{1,3}(?:\.[0-9]{1,4})?)",
            re.I,
        ),
    ),
    (
        "nav_value_after_phrase",
        re.compile(
            r"(?:net asset value per share|net assets per share|nav per share)"
            r"[^0-9$]{0,30}(?:was|of|:|=)?[^0-9$]{0,10}([0-9]{1,3}(?:\.[0-9]{1,4})?)",
            re.I,
        ),
    ),
    (
        "net_asset_value_of_x_per_share",
        re.compile(
            r"net asset value[^0-9$]{0,80}of[^0-9$]{0,40}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*per share",
            re.I,
        ),
    ),
    (
        "nav_attributable_to_common_stock",
        re.compile(
            r"(?:net asset value|nav)[^0-9$]{0,100}(?:attributable to common stock|for common stockholders)"
            r"[^0-9$]{0,60}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*per share",
            re.I,
        ),
    ),
    (
        "net_assets_attributable_per_share",
        re.compile(
            r"net assets[^0-9$]{0,100}(?:attributable to common stock|for common stockholders)"
            r"[^0-9$]{0,60}\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*per share",
            re.I,
        ),
    ),
]

IMPLIED_NAV_REGEX_SPECS = [
    (
        "closing_price_discount_to_nav",
        re.compile(
            r"(?:closing sales price|last reported closing sales price|closing price)[^$]{0,160}"
            r"\$([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*per share"
            r"[^%]{0,320}?(discount|premium)\s+of\s+(?:approximately\s+)?([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*%"
            r"[^.]{0,260}?net asset value per share",
            re.I,
        ),
    ),
]

PATTERN_BASE_SCORE = {
    "strict_nav_with_dollar": 6.0,
    "nav_value_after_phrase": 4.2,
    "net_asset_value_of_x_per_share": 5.6,
    "nav_attributable_to_common_stock": 6.8,
    "net_assets_attributable_per_share": 6.2,
    "closing_price_discount_to_nav": 8.5,
}

DIRECT_PATTERN_EXTRA_PENALTY = {
    "strict_nav_with_dollar": 0.0,
    "nav_value_after_phrase": 0.8,
    "net_asset_value_of_x_per_share": 0.2,
    "nav_attributable_to_common_stock": 0.1,
    "net_assets_attributable_per_share": 0.2,
}

SUSPICIOUS_SNIPPET_TERMS = [
    "notes due",
    "interest rate",
    "coupon",
    "yield",
    "weighted average",
    "dividend",
    "distribution",
    "fee",
    "expense ratio",
    "leverage ratio",
    "effective rate",
    "unsecured notes",
    "secured notes",
    "senior notes",
    "convertible notes",
    "preferred stock",
    "preferred shares",
    "vwap",
    "settlement amount",
    "ioc settlement amount",
    "stockholders approved the sale of shares",
]

MONTH_HINTS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
]

MONTH_TOKEN_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

ASOF_DATE_REGEX_SPECS = [
    (
        "as_of_monthname",
        re.compile(
            r"\bas of\s+([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "period_ended_monthname",
        re.compile(
            r"\b(?:for the (?:three|six|nine|twelve)\s+months ended|for the fiscal year ended|for the quarter ended|for the period ended|quarter ended|year ended)\s+"
            r"([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "as_of_numeric",
        re.compile(
            r"\bas of\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "period_ended_numeric",
        re.compile(
            r"\b(?:for the (?:three|six|nine|twelve)\s+months ended|for the fiscal year ended|for the quarter ended|for the period ended|quarter ended|year ended)\s+"
            r"([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
]

PRICE_OBS_DATE_REGEX_SPECS = [
    (
        "price_on_monthname",
        re.compile(
            r"\bon\s+([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})"
            r"[^.]{0,260}?(?:last reported )?closing(?: sales)? price",
            re.I,
        ),
    ),
    (
        "price_asof_monthname",
        re.compile(
            r"\bas of\s+([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})"
            r"[^.]{0,260}?(?:last reported )?closing(?: sales)? price",
            re.I,
        ),
    ),
    (
        "price_on_numeric",
        re.compile(
            r"\bon\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})"
            r"[^.]{0,260}?(?:last reported )?closing(?: sales)? price",
            re.I,
        ),
    ),
    (
        "price_asof_numeric",
        re.compile(
            r"\bas of\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})"
            r"[^.]{0,260}?(?:last reported )?closing(?: sales)? price",
            re.I,
        ),
    ),
]

NAV_REF_DATE_REGEX_SPECS = [
    (
        "nav_reported_asof_monthname",
        re.compile(
            r"net asset value per share(?: reported by us)?[^.]{0,220}?\bas of\s+"
            r"([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "nav_asof_monthname",
        re.compile(
            r"net asset value per share[^.]{0,220}?\bas of\s+"
            r"([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "nav_period_ended_monthname",
        re.compile(
            r"net asset value per share[^.]{0,260}?\b(?:for the (?:three|six|nine|twelve)\s+months ended|for the fiscal year ended|for the quarter ended|for the period ended|quarter ended|year ended)\s+"
            r"([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "nav_reported_asof_numeric",
        re.compile(
            r"net asset value per share(?: reported by us)?[^.]{0,220}?\bas of\s+"
            r"([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "nav_asof_numeric",
        re.compile(
            r"net asset value per share[^.]{0,220}?\bas of\s+"
            r"([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "nav_period_ended_numeric",
        re.compile(
            r"net asset value per share[^.]{0,260}?\b(?:for the (?:three|six|nine|twelve)\s+months ended|for the fiscal year ended|for the quarter ended|for the period ended|quarter ended|year ended)\s+"
            r"([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
]

DOC_PERIOD_DATE_REGEX_SPECS = [
    (
        "doc_period_ended_monthname",
        re.compile(
            r"\b(?:for the (?:three|six|nine|twelve)\s+months ended|for the fiscal year ended|for the quarter ended|for the period ended|quarter ended|year ended)\s+"
            r"([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "doc_as_of_monthname",
        re.compile(
            r"\bas of\s+([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "doc_period_ended_numeric",
        re.compile(
            r"\b(?:for the (?:three|six|nine|twelve)\s+months ended|for the fiscal year ended|for the quarter ended|for the period ended|quarter ended|year ended)\s+"
            r"([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
    (
        "doc_as_of_numeric",
        re.compile(
            r"\bas of\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})",
            re.I,
        ),
    ),
]

HARD_SKIP_CONTEXT_REGEX_SPECS = [
    ("example_context", re.compile(r"\bfor (?:example|instance)\b", re.I)),
    ("hypothetical_nav_if", re.compile(r"\bif the (?:most recently computed|current) nav(?: per share)?\b", re.I)),
    ("sell_below_nav", re.compile(r"\bsell(?:ing)? (?:our )?common stock below net asset value\b", re.I)),
    ("stockholder_approval_below_nav", re.compile(r"\b(?:maintain|obtain) any stockholder approval[^.]{0,180}\bbelow net asset value\b", re.I)),
]

CONTEXT_PENALTY_REGEX_SPECS = [
    ("reg_1940_act", re.compile(r"\b1940 act\b", re.I), 1.2),
    ("preferred_stock", re.compile(r"\bpreferred (?:stock|shares)\b", re.I), 1.0),
    ("vwap_context", re.compile(r"\bvwap\b", re.I), 0.8),
    ("settlement_amount", re.compile(r"\b(?:ioc )?settlement amount\b", re.I), 1.0),
    ("merger_accounting", re.compile(r"\bmerger accounting\b", re.I), 1.0),
    ("stock_repurchase_impact", re.compile(r"\bstock repurchase programs?\b|\bincremental impact\b|\bimpact on nav\b", re.I), 0.8),
    ("risk_factors", re.compile(r"\brisk factors\b", re.I), 0.5),
]

SECTION_BONUS_REGEX_SPECS = [
    ("market_common_equity", re.compile(r"market for (?:registrant(?:'s)?|our) common (?:equity|stock)|common stock price range", re.I), 1.0),
    ("nav_section", re.compile(r"\bnet asset value\b|\bfinancial highlights\b|\bper share data\b", re.I), 0.8),
    ("shareholder_returns", re.compile(r"\bmarket value of our common stock\b|\bpremium\s*/\s*\(discount\)\b", re.I), 0.6),
]

HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_SCRIPT_STYLE_RE = re.compile(r"<(?:script|style|noscript)[^>]*>.*?</(?:script|style|noscript)>", re.I | re.S)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HTML_BLOCK_BREAK_RE = re.compile(r"</?(?:br|p|div|tr|li|ul|ol|table|section|article|h[1-6])\b[^>]*>", re.I)
HTML_CELL_BREAK_RE = re.compile(r"</?(?:td|th)\b[^>]*>", re.I)
WHITESPACE_RE = re.compile(r"\s+")
YEAR_RE = re.compile(r"\b20[0-9]{2}\b")
NUMERIC_TOKEN_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:\.[0-9]{1,4})?)")
COMPARISON_PHRASE_RE = re.compile(r"\b(compared to|compares to|versus|vs\.?)\b", re.I)

AUTO_NAV_MIN_MATCH_SCORE = 3.0
AUTO_NAV_REVIEW_PREMIUM_PCT = 15.0
AUTO_NAV_EXCLUDE_PREMIUM_PCT = 25.0
AUTO_NAV_REVIEW_DISCOUNT_PCT = -45.0
AUTO_NAV_MAX_CANDIDATES_PER_FILING = 12


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
    p.add_argument("--nav-auto-source", default="sec", choices=["sec", "off"], help="Auto NAV source")
    p.add_argument("--sec-user-agent", default="private-credit-monitor/1.11c your_email@example.com", help="SEC User-Agent header")
    p.add_argument("--nav-auto-max-filings", type=int, default=6, help="Max recent filings to scan per ticker for NAV extraction")
    p.add_argument("--sec-max-docs-per-filing", type=int, default=5, help="Max SEC docs to scan per filing after document scoring")
    p.add_argument("--sec-use-cache", action="store_true", help="Use local SEC response cache")
    p.add_argument("--sec-cache-dir", default=None, help="Override SEC cache dir (default: <out-dir>/sec_cache)")
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
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_text(path: Path, default: Optional[str] = None) -> Optional[str]:
    if not path.exists():
        return default
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


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
            "nav_date should be the NAV as-of date, e.g. quarter-end.",
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


def normalize_ts_naive(x: Any) -> Optional[pd.Timestamp]:
    if x is None or x == "":
        return None
    try:
        ts = pd.Timestamp(x)
        if pd.isna(ts):
            return None
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        return pd.Timestamp(ts).normalize()
    except Exception:
        return None


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
    return normalize_ts_naive(x)


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


def dedupe_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def norm_flag_token(s: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(s).upper()).strip("_")
    return token or "UNKNOWN"


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

    dd20 = safe_pct(last_close, float(closes.tail(20).max())) if len(closes) >= 20 else None

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

    coverage = len(sub)
    extreme_z_count = sum(1 for v in zvals if v <= -2.0)
    ret5_bad_count = sum(1 for v in r5vals if v <= -5.0)
    below_ma20_count = sum(1 for v in ma_gap_vals if v < 0)

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

    dated_recent = [parse_date(r.get("event_date")) for r in recent_rows if r.get("event_date")]
    dated_recent = [d for d in dated_recent if d is not None]
    latest_recent_date = max(dated_recent).strftime("%Y-%m-%d") if dated_recent else None

    return {
        "path": str(path),
        "schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "as_of_date": raw.get("as_of_date") if isinstance(raw, dict) else None,
        "notes": raw.get("notes") if isinstance(raw, dict) else None,
        "recent_window_days": recent_days,
        "raw_row_count": len(out_rows),
        "template_excluded_count": len(out_rows) - len(valid_rows),
        "event_count_total": len(valid_rows),
        "event_count_recent": len(recent_rows),
        "alert_recent_count": sum(1 for r in recent_rows if r.get("severity") == "ALERT"),
        "watch_recent_count": sum(1 for r in recent_rows if r.get("severity") == "WATCH"),
        "latest_recent_event_date": latest_recent_date,
        "events": sorted(out_rows, key=lambda x: (x.get("event_date") or "", x.get("severity") or ""), reverse=True),
    }


def clean_snippet(s: str, max_len: int = 280) -> str:
    s = WHITESPACE_RE.sub(" ", (s or "")).strip()
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def sanitize_inline_code_text(s: Any) -> str:
    text = "NA" if s is None else str(s)
    return text.replace("`", "'")


def extract_local_snippet(text: str, start: int, end: int, radius: int = 180) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return clean_snippet(text[lo:hi], max_len=320)


def has_month_or_asof_hint(snippet_lower: str) -> bool:
    if " as of " in snippet_lower:
        return True
    return bool(any(m in snippet_lower for m in MONTH_HINTS) and YEAR_RE.search(snippet_lower))


def has_suspicious_terms(snippet_lower: str) -> bool:
    return any(term in snippet_lower for term in SUSPICIOUS_SNIPPET_TERMS)


def is_date_component_near_number(text: str, num_start: int, num_end: int) -> bool:
    left = text[max(0, num_start - 25):num_start].lower()
    right = text[num_end:min(len(text), num_end + 15)].lower()
    has_month_left = any(m in left for m in MONTH_HINTS)
    has_year_right = bool(re.search(r",?\s*20[0-9]{2}", right))
    return bool(has_month_left and has_year_right)


def normalize_month_token(token: str) -> Optional[int]:
    t = (token or "").strip().lower().rstrip(".")
    return MONTH_TOKEN_MAP.get(t)


def make_ts(year: int, month: int, day: int) -> Optional[pd.Timestamp]:
    try:
        return pd.Timestamp(year=year, month=month, day=day).normalize()
    except Exception:
        return None


def parse_date_match(label: str, m: re.Match) -> Optional[pd.Timestamp]:
    try:
        if label.endswith("monthname"):
            month = normalize_month_token(m.group(1))
            day = int(m.group(2))
            year = int(m.group(3))
            if month is None:
                return None
            return make_ts(year=year, month=month, day=day)
        a = int(m.group(1))
        b = int(m.group(2))
        year = int(m.group(3))
        return make_ts(year=year, month=a, day=b)
    except Exception:
        return None


def collect_date_matches_from_ctx(
    ctx: str,
    specs: List[Tuple[str, re.Pattern]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, (label, pat) in enumerate(specs):
        for m in pat.finditer(ctx):
            ts = parse_date_match(label, m)
            if ts is None:
                continue
            out.append({
                "ts": ts,
                "label": label,
                "text": clean_snippet(m.group(0), max_len=140),
                "priority": idx,
                "start": m.start(),
            })
    return out


def extract_best_date_from_ctx(
    ctx: str,
    specs: List[Tuple[str, re.Pattern]],
) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    matches = collect_date_matches_from_ctx(ctx, specs)
    if not matches:
        return None, None, None

    matches = sorted(matches, key=lambda x: (x["priority"], -x["ts"].value))
    best = matches[0]
    return best["ts"], best["label"], best["text"]


def extract_best_date_from_ctx_latest(
    ctx: str,
    specs: List[Tuple[str, re.Pattern]],
) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    matches = collect_date_matches_from_ctx(ctx, specs)
    if not matches:
        return None, None, None

    matches = sorted(matches, key=lambda x: (-x["ts"].value, x["priority"]))
    best = matches[0]
    return best["ts"], best["label"], best["text"]


def extract_nav_asof_date(text: str, start: int, end: int) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    lo = max(0, start - 500)
    hi = min(len(text), end + 500)
    return extract_best_date_from_ctx(text[lo:hi], ASOF_DATE_REGEX_SPECS)


def extract_price_obs_date(text: str, start: int, end: int) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    lo = max(0, start - 550)
    hi = min(len(text), end + 300)
    return extract_best_date_from_ctx(text[lo:hi], PRICE_OBS_DATE_REGEX_SPECS)


def extract_nav_ref_date_for_implied(text: str, start: int, end: int) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    lo = max(0, start - 240)
    hi = min(len(text), end + 650)
    return extract_best_date_from_ctx(text[lo:hi], NAV_REF_DATE_REGEX_SPECS)


def doc_anchor_label_rank(label: str) -> int:
    label = str(label or "").lower()
    if "period_ended" in label:
        return 0
    if "as_of" in label:
        return 1
    return 9


def extract_doc_period_anchor(
    text: str,
    upper_bound: Optional[pd.Timestamp] = None,
) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    if not text:
        return None, None, None

    ctx = text[:20000]
    matches = collect_date_matches_from_ctx(ctx, DOC_PERIOD_DATE_REGEX_SPECS)
    if not matches:
        return None, None, None

    ub = normalize_ts_naive(upper_bound)
    if ub is not None:
        bounded = [m for m in matches if m["ts"] <= ub]
        if bounded:
            matches = bounded

    matches = sorted(
        matches,
        key=lambda x: (
            -x["ts"].value,
            doc_anchor_label_rank(x["label"]),
            x["priority"],
            x["start"],
        )
    )
    best = matches[0]
    return best["ts"], best["label"], best["text"]


def build_local_role_context(text: str, start: int, end: int) -> str:
    lo = max(0, start - 40)
    hi = min(len(text), end + 120)
    return clean_snippet(text[lo:hi], max_len=240)


def infer_candidate_value_role(
    snippet: str,
    matched_value: Optional[float],
    pattern_label: str,
    local_role_ctx: Optional[str] = None,
) -> Tuple[str, bool, bool]:
    ctx = local_role_ctx or snippet or ""
    ctx_lower = ctx.lower()

    numeric_tokens = NUMERIC_TOKEN_RE.findall(ctx)
    multi_value_row_flag = len(numeric_tokens) >= 2

    if matched_value is not None:
        value_token = str(safe_num(matched_value, 4)).rstrip("0").rstrip(".")
    else:
        value_token = ""

    value_pos = ctx.find(value_token) if value_token else -1
    compare_matches = list(COMPARISON_PHRASE_RE.finditer(ctx_lower))
    comparison_context_flag = bool(compare_matches)

    role = "ambiguous"

    if comparison_context_flag and value_pos >= 0:
        before_window = ctx_lower[max(0, value_pos - 40):value_pos]
        after_window = ctx_lower[value_pos:min(len(ctx_lower), value_pos + 80)]

        current_intro_flag = bool(
            value_token and re.search(
                r"\b(?:net asset value|nav)[^|.;]{0,40}(?:was|of|:|=)?[^|.;]{0,20}\$?\s*"
                + re.escape(value_token),
                ctx_lower,
                re.I,
            )
        )

        compare_before_close = bool(COMPARISON_PHRASE_RE.search(before_window))
        compare_after_close = bool(COMPARISON_PHRASE_RE.search(after_window))

        if current_intro_flag:
            role = "current"
        elif compare_before_close:
            role = "comparison"
        elif compare_after_close:
            role = "current"
        else:
            role = "ambiguous"
    else:
        if multi_value_row_flag:
            if pattern_label in {"nav_value_after_phrase", "strict_nav_with_dollar"}:
                role = "current_first_column"
            else:
                role = "current_table_like"
        else:
            role = "current_single_value"

    return role, comparison_context_flag, multi_value_row_flag


def analyze_candidate_context(text: str, start: int, end: int, extraction_method: str) -> Dict[str, Any]:
    lo = max(0, start - 1200)
    hi = min(len(text), end + 1200)
    ctx = text[lo:hi]

    hard_skip_tags: List[str] = []
    penalty_tags: List[str] = []
    bonus_tags: List[str] = []

    penalty_total = 0.0
    bonus_total = 0.0

    for label, pat in HARD_SKIP_CONTEXT_REGEX_SPECS:
        if pat.search(ctx):
            hard_skip_tags.append(label)

    for label, pat, amt in CONTEXT_PENALTY_REGEX_SPECS:
        if pat.search(ctx):
            penalty_total += amt
            penalty_tags.append(label)

    for label, pat, amt in SECTION_BONUS_REGEX_SPECS:
        if pat.search(ctx):
            bonus_total += amt
            bonus_tags.append(label)

    if extraction_method == "direct":
        if re.search(r"(?:^|[\s.;])\$?\d+\s*represents\b", ctx, re.I):
            penalty_total += 1.0
            penalty_tags.append("footnote_represents")
        if re.search(r"\bif the market price on the payment date\b", ctx, re.I):
            penalty_total += 0.8
            penalty_tags.append("payment_date_example")
        if re.search(r"\bmost recently computed nav per share\b", ctx, re.I) and re.search(r"\bfor example\b", ctx, re.I):
            hard_skip_tags.append("example_context")

    return {
        "hard_skip_context_flag": bool(hard_skip_tags),
        "hard_skip_context_tags": dedupe_keep_order(hard_skip_tags),
        "context_penalty_total": round(float(penalty_total), 3),
        "context_penalty_tags": dedupe_keep_order(penalty_tags),
        "section_bonus_total": round(float(bonus_total), 3),
        "section_bonus_tags": dedupe_keep_order(bonus_tags),
    }


def score_direct_nav_candidate(
    *,
    value: float,
    pattern_label: str,
    snippet: str,
    market_close: Optional[float],
    percent_context_flag: bool,
    suspicious_terms_flag: bool,
    date_component_flag: bool,
    dollar_near_value: bool,
    nav_ref_present: bool,
    context_penalty_total: float,
    section_bonus_total: float,
    hard_skip_context_flag: bool,
    candidate_value_role: str,
    comparison_context_flag: bool,
    multi_value_row_flag: bool,
) -> float:
    snippet_lower = snippet.lower()
    score = float(PATTERN_BASE_SCORE.get(pattern_label, 3.0))

    if dollar_near_value:
        score += 1.0
    if "net asset value per share" in snippet_lower:
        score += 0.8
    elif "nav per share" in snippet_lower:
        score += 0.5
    if has_month_or_asof_hint(snippet_lower):
        score += 0.5
    if nav_ref_present:
        score += 0.4
    else:
        score -= 0.5

    if candidate_value_role in {"current_first_column", "current_table_like", "current_single_value", "current"}:
        score += 0.4
    if multi_value_row_flag:
        score += 0.3
    if comparison_context_flag and candidate_value_role == "comparison":
        score -= 1.2

    score += float(section_bonus_total)
    score -= float(context_penalty_total)
    score -= float(DIRECT_PATTERN_EXTRA_PENALTY.get(pattern_label, 0.0))

    if not dollar_near_value and pattern_label != "strict_nav_with_dollar":
        score -= 0.5
    if percent_context_flag:
        score -= 1.5
    if suspicious_terms_flag:
        score -= 2.0
    if date_component_flag:
        score -= 5.0
    if hard_skip_context_flag:
        score -= 4.0

    if market_close is not None and market_close > 0 and value > 0:
        prem = (market_close / value - 1.0) * 100.0
        if prem > AUTO_NAV_EXCLUDE_PREMIUM_PCT:
            score -= 2.0
        elif prem > AUTO_NAV_REVIEW_PREMIUM_PCT:
            score -= 0.8

    return round(score, 3)


def score_implied_nav_candidate(
    *,
    snippet: str,
    price_obs_present: bool,
    nav_ref_present: bool,
    price_obs_before_or_equal_ref_check: Optional[bool],
    context_penalty_total: float,
    section_bonus_total: float,
    hard_skip_context_flag: bool,
) -> float:
    snippet_lower = snippet.lower()
    score = float(PATTERN_BASE_SCORE.get("closing_price_discount_to_nav", 8.0))

    if "discount" in snippet_lower or "premium" in snippet_lower:
        score += 0.8
    if "closing sales price" in snippet_lower or "closing price" in snippet_lower:
        score += 0.6
    if "net asset value per share" in snippet_lower:
        score += 0.8

    score += float(section_bonus_total)
    score -= float(context_penalty_total)

    score += 0.4 if price_obs_present else -0.8
    score += 0.8 if nav_ref_present else -1.0

    if price_obs_before_or_equal_ref_check is True:
        score += 0.4
    elif price_obs_before_or_equal_ref_check is False:
        score -= 0.6

    if hard_skip_context_flag:
        score -= 3.0

    return round(score, 3)


def extract_nav_candidates_from_text(
    text: str,
    market_close: Optional[float] = None,
    max_candidates: int = AUTO_NAV_MAX_CANDIDATES_PER_FILING,
) -> List[Dict[str, Any]]:
    if not text:
        return []

    candidates: List[Dict[str, Any]] = []
    seen = set()

    for pattern_label, pat in DIRECT_NAV_REGEX_SPECS:
        for m in pat.finditer(text):
            val = to_float(m.group(1))
            if val is None or not (0.5 <= val <= 100.0):
                continue

            snippet = extract_local_snippet(text, m.start(), m.end(), radius=180)
            snippet_lower = snippet.lower()

            num_lo = max(0, m.start(1) - 25)
            num_hi = min(len(text), m.end(1) + 20)
            num_context = clean_snippet(text[num_lo:num_hi], max_len=120)
            num_context_lower = num_context.lower()

            percent_context_flag = ("%" in num_context) or (" percent" in num_context_lower)
            suspicious_terms_flag = has_suspicious_terms(snippet_lower)
            date_component_flag = is_date_component_near_number(text, m.start(1), m.end(1))
            dollar_near_value = "$" in text[max(0, m.start(1) - 6):m.start(1)]

            local_role_ctx = build_local_role_context(text, m.start(), m.end())
            candidate_value_role, comparison_context_flag, multi_value_row_flag = infer_candidate_value_role(
                snippet=snippet,
                matched_value=float(val),
                pattern_label=pattern_label,
                local_role_ctx=local_role_ctx,
            )

            nav_ref_date, nav_ref_date_source, nav_ref_match_text = extract_nav_asof_date(text, m.start(), m.end())

            if comparison_context_flag and candidate_value_role == "current":
                nav_ref_date = None
                nav_ref_date_source = None
                nav_ref_match_text = None

            context_info = analyze_candidate_context(text, m.start(), m.end(), extraction_method="direct")

            score = score_direct_nav_candidate(
                value=float(val),
                pattern_label=pattern_label,
                snippet=snippet,
                market_close=market_close,
                percent_context_flag=percent_context_flag,
                suspicious_terms_flag=suspicious_terms_flag,
                date_component_flag=date_component_flag,
                dollar_near_value=dollar_near_value,
                nav_ref_present=bool(nav_ref_date is not None),
                context_penalty_total=float(context_info["context_penalty_total"]),
                section_bonus_total=float(context_info["section_bonus_total"]),
                hard_skip_context_flag=bool(context_info["hard_skip_context_flag"]),
                candidate_value_role=candidate_value_role,
                comparison_context_flag=comparison_context_flag,
                multi_value_row_flag=multi_value_row_flag,
            )

            premium_discount_est = None
            if market_close is not None and market_close > 0:
                premium_discount_est = safe_num((market_close / float(val) - 1.0) * 100.0)

            key = ("direct", round(float(val), 4), pattern_label, snippet[:140])
            if key in seen:
                continue
            seen.add(key)

            candidates.append({
                "extraction_method": "direct",
                "nav": round(float(val), 6),
                "matched_pattern": pattern_label,
                "matched_snippet": snippet,
                "num_context": num_context,
                "percent_context_flag": percent_context_flag,
                "suspicious_terms_flag": suspicious_terms_flag,
                "date_component_flag": date_component_flag,
                "match_score": score,
                "premium_discount_est": premium_discount_est,
                "price_obs_date": None,
                "price_obs_date_source": None,
                "price_obs_match_text": None,
                "nav_ref_date": nav_ref_date.strftime("%Y-%m-%d") if nav_ref_date is not None else None,
                "nav_ref_date_source": nav_ref_date_source,
                "nav_ref_match_text": nav_ref_match_text,
                "hard_skip_context_flag": context_info["hard_skip_context_flag"],
                "hard_skip_context_tags": context_info["hard_skip_context_tags"],
                "context_penalty_total": context_info["context_penalty_total"],
                "context_penalty_tags": context_info["context_penalty_tags"],
                "section_bonus_total": context_info["section_bonus_total"],
                "section_bonus_tags": context_info["section_bonus_tags"],
                "candidate_value_role": candidate_value_role,
                "comparison_context_flag": comparison_context_flag,
                "multi_value_row_flag": multi_value_row_flag,
                "date_binding_mode": "local_nav_ref" if nav_ref_date is not None else "none_yet",
                "local_role_ctx": local_role_ctx,
            })

    for pattern_label, pat in IMPLIED_NAV_REGEX_SPECS:
        for m in pat.finditer(text):
            price = to_float(m.group(1))
            rel = str(m.group(2) or "").lower().strip()
            pct = to_float(m.group(3))
            if price is None or pct is None or price <= 0 or pct < 0 or pct >= 95:
                continue

            if rel == "discount":
                nav = price / (1.0 - pct / 100.0)
            elif rel == "premium":
                nav = price / (1.0 + pct / 100.0)
            else:
                continue

            if not (0.5 <= nav <= 100.0):
                continue

            snippet = extract_local_snippet(text, m.start(), m.end(), radius=180)
            price_obs_date, price_obs_date_source, price_obs_match_text = extract_price_obs_date(text, m.start(), m.end())
            nav_ref_date, nav_ref_date_source, nav_ref_match_text = extract_nav_ref_date_for_implied(text, m.start(), m.end())
            context_info = analyze_candidate_context(text, m.start(), m.end(), extraction_method="implied")

            ordering_check: Optional[bool] = None
            if price_obs_date is not None and nav_ref_date is not None:
                ordering_check = bool(nav_ref_date <= price_obs_date)

            score = score_implied_nav_candidate(
                snippet=snippet,
                price_obs_present=bool(price_obs_date is not None),
                nav_ref_present=bool(nav_ref_date is not None),
                price_obs_before_or_equal_ref_check=ordering_check,
                context_penalty_total=float(context_info["context_penalty_total"]),
                section_bonus_total=float(context_info["section_bonus_total"]),
                hard_skip_context_flag=bool(context_info["hard_skip_context_flag"]),
            )

            premium_discount_est = None
            if market_close is not None and market_close > 0:
                premium_discount_est = safe_num((market_close / float(nav) - 1.0) * 100.0)

            key = ("implied", round(float(nav), 4), pattern_label, snippet[:140])
            if key in seen:
                continue
            seen.add(key)

            candidates.append({
                "extraction_method": "implied_from_price_and_rel",
                "nav": round(float(nav), 6),
                "matched_pattern": pattern_label,
                "matched_snippet": snippet,
                "num_context": clean_snippet(snippet, max_len=160),
                "percent_context_flag": False,
                "suspicious_terms_flag": False,
                "date_component_flag": False,
                "match_score": score,
                "premium_discount_est": premium_discount_est,
                "derived_from_price": safe_num(price),
                "derived_from_rel": rel,
                "derived_from_pct": safe_num(pct),
                "price_obs_date": price_obs_date.strftime("%Y-%m-%d") if price_obs_date is not None else None,
                "price_obs_date_source": price_obs_date_source,
                "price_obs_match_text": price_obs_match_text,
                "nav_ref_date": nav_ref_date.strftime("%Y-%m-%d") if nav_ref_date is not None else None,
                "nav_ref_date_source": nav_ref_date_source,
                "nav_ref_match_text": nav_ref_match_text,
                "hard_skip_context_flag": context_info["hard_skip_context_flag"],
                "hard_skip_context_tags": context_info["hard_skip_context_tags"],
                "context_penalty_total": context_info["context_penalty_total"],
                "context_penalty_tags": context_info["context_penalty_tags"],
                "section_bonus_total": context_info["section_bonus_total"],
                "section_bonus_tags": context_info["section_bonus_tags"],
                "candidate_value_role": "current_implied",
                "comparison_context_flag": False,
                "multi_value_row_flag": False,
                "date_binding_mode": "local_nav_ref" if nav_ref_date is not None else "none_yet",
                "local_role_ctx": None,
            })

    candidates = sorted(
        candidates,
        key=lambda x: (
            -(float(x.get("match_score") or -999)),
            0 if x.get("extraction_method") == "implied_from_price_and_rel" else 1,
            x.get("matched_pattern") or "",
            -(float(x.get("nav") or 0)),
        )
    )

    trimmed = candidates[:max_candidates]
    for idx, c in enumerate(trimmed, start=1):
        c["candidate_rank"] = idx
        c["candidate_count"] = len(candidates)

    return trimmed


def choose_effective_nav_date(
    nav_ref_date: Optional[pd.Timestamp],
    filing_date: Optional[pd.Timestamp],
    market_date: Optional[pd.Timestamp],
    today_utc: Optional[pd.Timestamp],
    doc_period_anchor: Optional[pd.Timestamp] = None,
    candidate_value_role: Optional[str] = None,
    comparison_context_flag: bool = False,
    multi_value_row_flag: bool = False,
) -> Tuple[Optional[pd.Timestamp], str, str]:
    nav_ref_date = normalize_ts_naive(nav_ref_date)
    filing_date = normalize_ts_naive(filing_date)
    market_date = normalize_ts_naive(market_date)
    today_utc = normalize_ts_naive(today_utc)
    doc_period_anchor = normalize_ts_naive(doc_period_anchor)

    upper_bounds_for_ref = [d for d in [filing_date, market_date, today_utc] if d is not None]
    if nav_ref_date is not None and all(nav_ref_date <= ub for ub in upper_bounds_for_ref):
        return nav_ref_date, "nav_ref_extracted", "local_nav_ref"

    can_use_doc_anchor = candidate_value_role in {
        "current",
        "current_first_column",
        "current_table_like",
        "current_single_value",
        "current_implied",
    } or (multi_value_row_flag and candidate_value_role not in {"comparison"})

    upper_bounds_for_doc = [d for d in [filing_date, market_date, today_utc] if d is not None]
    if doc_period_anchor is not None and can_use_doc_anchor and all(doc_period_anchor <= ub for ub in upper_bounds_for_doc):
        if comparison_context_flag:
            return doc_period_anchor, "doc_period_anchor_extracted", "doc_period_anchor_after_comparison_guard"
        return doc_period_anchor, "doc_period_anchor_extracted", "doc_period_anchor"

    upper_bounds_for_filing = [d for d in [market_date, today_utc] if d is not None]
    if filing_date is not None:
        if all(filing_date <= ub for ub in upper_bounds_for_filing):
            return filing_date, "filing_date_inferred_review_only", "filing_date_fallback"
        return None, "nav_date_future_rejected", "invalid_future_date"

    return None, "nav_date_unknown", "unknown"


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
    nav_date_source: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ticker = str(ticker or "").upper().strip()
    px = latest_price_by_ticker.get(ticker, {})
    market_close = to_float(px.get("close"))
    market_date = parse_date(px.get("data_date"))

    valid_for_stats = bool(ticker and nav is not None and nav > 0 and nav_date is not None)
    premium_discount_pct = safe_pct(market_close, nav) if (valid_for_stats and market_close is not None) else None

    nav_age_days = None
    fresh_for_rule = False
    structurally_reliable_nav_date = nav_date_source in {"manual_input", "nav_ref_extracted", "doc_period_anchor_extracted"}

    if valid_for_stats and nav_date is not None and market_date is not None:
        nav_age_days = int((market_date - nav_date).days)
        fresh_for_rule = bool(
            structurally_reliable_nav_date and
            nav_age_days is not None and
            0 <= nav_age_days <= nav_fresh_max_days and
            premium_discount_pct is not None
        )

    row = {
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
        "structurally_reliable_nav_date": structurally_reliable_nav_date,
        "nav_date_source": nav_date_source,
    }
    if extra_fields:
        row.update(extra_fields)
    return row


def finalize_nav_row_dq(row: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(row)
    source_kind = str(row.get("source_kind") or "").strip()

    if source_kind == "manual":
        row["review_flag"] = "NONE"
        row["dq_status"] = "MANUAL_VALID" if row.get("valid_for_stats") else "MANUAL_INVALID"
        row["used_in_stats"] = bool(row.get("valid_for_stats"))
        row.setdefault("match_score", None)
        row.setdefault("matched_pattern", None)
        row.setdefault("matched_snippet", None)
        row.setdefault("candidate_rank", None)
        row.setdefault("candidate_count", None)
        row.setdefault("percent_context_flag", False)
        row.setdefault("suspicious_terms_flag", False)
        row.setdefault("date_component_flag", False)
        row.setdefault("extraction_method", "manual")
        row.setdefault("filing_date", None)
        row.setdefault("price_obs_date", None)
        row.setdefault("price_obs_date_source", None)
        row.setdefault("price_obs_match_text", None)
        row.setdefault("nav_ref_date_extracted", None)
        row.setdefault("nav_ref_date_source", None)
        row.setdefault("nav_ref_match_text", None)
        row.setdefault("hard_skip_context_flag", False)
        row.setdefault("hard_skip_context_tags", [])
        row.setdefault("context_penalty_total", 0.0)
        row.setdefault("context_penalty_tags", [])
        row.setdefault("section_bonus_total", 0.0)
        row.setdefault("section_bonus_tags", [])
        row.setdefault("doc_name", None)
        row.setdefault("doc_score", None)
        row.setdefault("doc_period_anchor", None)
        row.setdefault("doc_period_anchor_source", None)
        row.setdefault("doc_period_anchor_match_text", None)
        row.setdefault("candidate_value_role", "manual")
        row.setdefault("comparison_context_flag", False)
        row.setdefault("multi_value_row_flag", False)
        row.setdefault("date_binding_mode", "manual_input")
        row.setdefault("local_role_ctx", None)
        return row

    used = bool(row.get("valid_for_stats"))
    dq_status = "OK" if used else "INVALID"
    flags: List[str] = []

    nav_date_source = str(row.get("nav_date_source") or "")
    candidate_value_role = str(row.get("candidate_value_role") or "")

    if nav_date_source == "filing_date_inferred_review_only":
        used = False
        dq_status = "REVIEW_NAV_DATE_INFERRED"
        flags.append("NAV_DATE_INFERRED_FROM_FILING")
    elif nav_date_source in {"nav_date_unknown", "nav_date_future_rejected"}:
        used = False
        dq_status = "EXCLUDED_NAV_DATE_INVALID"
        flags.append(f"NAV_DATE_STATUS_{norm_flag_token(nav_date_source)}")

    if candidate_value_role == "comparison":
        used = False
        if dq_status == "OK":
            dq_status = "REVIEW_COMPARISON_VALUE"
        flags.append("CANDIDATE_VALUE_IS_COMPARISON")

    hard_skip_tags = list(row.get("hard_skip_context_tags") or [])
    if row.get("hard_skip_context_flag"):
        used = False
        flags.extend([f"CONTEXT_HARD_SKIP_{norm_flag_token(t)}" for t in hard_skip_tags])

    match_score = to_float(row.get("match_score"))
    if match_score is not None and match_score < AUTO_NAV_MIN_MATCH_SCORE:
        used = False
        if dq_status == "OK":
            dq_status = "EXCLUDED_LOW_MATCH_SCORE"
        flags.append(f"LOW_MATCH_SCORE_LT_{AUTO_NAV_MIN_MATCH_SCORE}")

    if bool(row.get("date_component_flag")):
        used = False
        dq_status = "EXCLUDED_DATE_COMPONENT"
        flags.append("DATE_COMPONENT_NEAR_MATCH")

    premium_discount_pct = to_float(row.get("premium_discount_pct"))
    if premium_discount_pct is not None:
        if premium_discount_pct > AUTO_NAV_EXCLUDE_PREMIUM_PCT:
            used = False
            dq_status = "EXCLUDED_PREMIUM_TOO_HIGH"
            flags.append(f"PREMIUM_GT_{int(AUTO_NAV_EXCLUDE_PREMIUM_PCT)}")
        elif premium_discount_pct > AUTO_NAV_REVIEW_PREMIUM_PCT:
            used = False
            if dq_status == "OK":
                dq_status = "REVIEW_PREMIUM_HIGH"
            flags.append(f"PREMIUM_GT_{int(AUTO_NAV_REVIEW_PREMIUM_PCT)}")
        elif premium_discount_pct <= AUTO_NAV_REVIEW_DISCOUNT_PCT:
            used = False
            if dq_status == "OK":
                dq_status = "REVIEW_DISCOUNT_DEEP"
            flags.append(f"DISCOUNT_LE_{int(AUTO_NAV_REVIEW_DISCOUNT_PCT)}")

    if bool(row.get("percent_context_flag")):
        used = False
        if dq_status == "OK":
            dq_status = "REVIEW_PERCENT_CONTEXT"
        flags.append("PERCENT_NEAR_MATCH")

    if bool(row.get("suspicious_terms_flag")):
        used = False
        if dq_status == "OK":
            dq_status = "REVIEW_SNIPPET_TERMS"
        flags.append("SUSPICIOUS_SNIPPET_TERMS")

    if row.get("hard_skip_context_flag"):
        dq_status = "EXCLUDED_CONTEXT_HARD_SKIP"

    row["review_flag"] = "|".join(dedupe_keep_order(flags)) if flags else "NONE"
    row["dq_status"] = dq_status
    row["used_in_stats"] = bool(used and row.get("valid_for_stats") and dq_status == "OK")
    return row


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
        nav_date = parse_date(item.get("nav_date"))
        row = make_nav_overlay_row(
            ticker=str(item.get("ticker", "")).upper().strip(),
            nav=to_float(item.get("nav")),
            nav_date=nav_date,
            source_url=item.get("source_url"),
            note=item.get("note"),
            source_kind="manual",
            latest_price_by_ticker=latest_price_by_ticker,
            nav_fresh_max_days=nav_fresh_max_days,
            nav_date_source="manual_input",
            extra_fields={
                "filing_date": None,
                "price_obs_date": None,
                "price_obs_date_source": None,
                "price_obs_match_text": None,
                "nav_ref_date_extracted": nav_date.strftime("%Y-%m-%d") if nav_date is not None else None,
                "nav_ref_date_source": "manual_input",
                "nav_ref_match_text": None,
                "hard_skip_context_flag": False,
                "hard_skip_context_tags": [],
                "context_penalty_total": 0.0,
                "context_penalty_tags": [],
                "section_bonus_total": 0.0,
                "section_bonus_tags": [],
                "doc_name": None,
                "doc_score": None,
                "doc_period_anchor": None,
                "doc_period_anchor_source": None,
                "doc_period_anchor_match_text": None,
                "candidate_value_role": "manual",
                "comparison_context_flag": False,
                "multi_value_row_flag": False,
                "date_binding_mode": "manual_input",
                "local_role_ctx": None,
            },
        )
        row = finalize_nav_row_dq(row)
        rows.append(row)

    valid_count = sum(1 for r in rows if r.get("valid_for_stats"))
    return {
        "path": str(path),
        "schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "as_of_date": raw.get("as_of_date") if isinstance(raw, dict) else None,
        "notes": raw.get("notes") if isinstance(raw, dict) else None,
        "raw_row_count": len(rows),
        "template_excluded_count": len(rows) - valid_count,
        "items": rows,
    }


def cache_key_path(cache_dir: Optional[Path], url: str, ext: str) -> Optional[Path]:
    if cache_dir is None:
        return None
    ensure_dir(cache_dir)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.{ext}"


def is_retryable_exception(e: Exception) -> bool:
    if isinstance(e, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(e, requests.HTTPError):
        status = getattr(getattr(e, "response", None), "status_code", None)
        return status in REQUEST_RETRYABLE_STATUS
    return False


def sec_http_get(session: requests.Session, url: str, timeout: int) -> requests.Response:
    last_err: Optional[Exception] = None
    max_attempts = len(REQUEST_RETRY_SLEEP_SECONDS) + 1

    for attempt in range(1, max_attempts + 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code in REQUEST_RETRYABLE_STATUS:
                raise requests.HTTPError(
                    f"retryable_http_status:{r.status_code}",
                    response=r,
                )
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            retryable = is_retryable_exception(e)
            if not retryable or attempt >= max_attempts:
                raise
            time.sleep(REQUEST_RETRY_SLEEP_SECONDS[attempt - 1])

    if last_err is not None:
        raise last_err
    raise RuntimeError("sec_http_get_unknown_error")


def sec_fetch_json(
    session: requests.Session,
    url: str,
    timeout: int,
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> Any:
    cache_path = cache_key_path(cache_dir, url, "json") if use_cache else None
    if cache_path and cache_path.exists():
        cached = read_json(cache_path, default=None)
        if cached is not None:
            return cached

    r = sec_http_get(session, url, timeout=timeout)
    obj = r.json()

    if cache_path is not None:
        write_json(cache_path, obj)
    return obj


def sec_fetch_text(
    session: requests.Session,
    url: str,
    timeout: int,
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> str:
    cache_path = cache_key_path(cache_dir, url, "txt") if use_cache else None
    if cache_path and cache_path.exists():
        cached = read_text(cache_path, default=None)
        if cached is not None:
            return cached

    r = sec_http_get(session, url, timeout=timeout)
    text = r.text

    if cache_path is not None:
        write_text(cache_path, text)
    return text


def get_sec_ticker_to_cik_map(
    session: requests.Session,
    timeout: int,
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> Dict[str, str]:
    raw = sec_fetch_json(session, SEC_TICKER_MAP_URL, timeout=timeout, cache_dir=cache_dir, use_cache=use_cache)
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
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> List[Dict[str, Any]]:
    url = SEC_SUBMISSIONS_URL.format(cik10=cik10)
    raw = sec_fetch_json(session, url, timeout=timeout, cache_dir=cache_dir, use_cache=use_cache)

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

        accession_nodash = accession.replace("-", "")
        cik_int = str(int(cik10))

        out.append({
            "form": form,
            "filing_date": filing_date,
            "accession_number": accession,
            "accession_nodash": accession_nodash,
            "cik_int": cik_int,
            "primary_document": primary_doc,
            "source_url": SEC_ARCHIVES_DOC_URL.format(
                cik_int=cik_int,
                accession_nodash=accession_nodash,
                primary_doc=primary_doc,
            ),
        })

    return out


def score_sec_document_name(doc_name: str, primary_document: str) -> int:
    name = str(doc_name or "").strip()
    lower = name.lower()
    primary_lower = str(primary_document or "").strip().lower()

    if not lower:
        return -999

    if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".zip", ".xls", ".xlsx", ".pdf")):
        return -999
    if lower.endswith((".xsd", ".xml")):
        return -999
    if any(x in lower for x in ["_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"]):
        return -999

    score = 0
    if lower == primary_lower:
        score += 100

    if lower.endswith((".htm", ".html")):
        score += 12
    elif lower.endswith(".txt"):
        score += 10
    else:
        return -999

    if re.search(r"(?:ex|exhibit)[\-_ ]?99", lower):
        score += 55
    if re.search(r"99[\._\- ]?1", lower):
        score += 35
    if re.search(r"99[\._\- ]?2", lower):
        score += 25

    for term, pts in [
        ("earnings", 30),
        ("results", 24),
        ("release", 22),
        ("supplement", 22),
        ("presentation", 16),
        ("investor", 10),
        ("press", 10),
        ("quarter", 8),
        ("qtr", 8),
    ]:
        if term in lower:
            score += pts

    if lower.endswith(".txt"):
        score += 5

    if "index" in lower:
        score -= 20

    return score


def get_sec_document_candidates_for_filing(
    session: requests.Session,
    filing: Dict[str, Any],
    timeout: int,
    max_docs_per_filing: int,
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    notes: List[str] = []

    primary_doc = str(filing.get("primary_document") or "").strip()
    accession_nodash = str(filing.get("accession_nodash") or "").strip()
    cik_int = str(filing.get("cik_int") or "").strip()

    docs: List[Dict[str, Any]] = []
    seen_urls = set()

    primary_url = filing.get("source_url")
    if primary_url:
        docs.append({
            "doc_name": primary_doc,
            "url": primary_url,
            "doc_score": score_sec_document_name(primary_doc, primary_doc),
            "doc_source": "primary_document",
        })
        seen_urls.add(primary_url)

    index_url = SEC_ARCHIVES_INDEX_URL.format(cik_int=cik_int, accession_nodash=accession_nodash)
    try:
        raw = sec_fetch_json(session, index_url, timeout=timeout, cache_dir=cache_dir, use_cache=use_cache)
        items = (((raw or {}).get("directory") or {}).get("item") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            score = score_sec_document_name(name, primary_doc)
            if score < 0:
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{name}"
            if url in seen_urls:
                continue
            docs.append({
                "doc_name": name,
                "url": url,
                "doc_score": score,
                "doc_source": "filing_index",
            })
            seen_urls.add(url)
    except Exception as e:
        notes.append(f"WARN:index_fetch:{type(e).__name__}:{str(e)[:120]}")

    docs = sorted(
        docs,
        key=lambda x: (
            -(int(x.get("doc_score") or -999)),
            0 if x.get("doc_source") == "primary_document" else 1,
            x.get("doc_name") or "",
        )
    )

    trimmed = docs[:max(1, max_docs_per_filing)]
    return trimmed, notes


def filing_html_to_text(raw_text: str) -> str:
    text = html_lib.unescape(raw_text or "")
    text = text.replace("&nbsp;", " ")
    text = HTML_COMMENT_RE.sub(" ", text)
    text = HTML_SCRIPT_STYLE_RE.sub(" ", text)
    text = HTML_CELL_BREAK_RE.sub(" | ", text)
    text = HTML_BLOCK_BREAK_RE.sub("\n", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def fetch_auto_nav_rows_from_sec(
    tickers: List[str],
    latest_price_by_ticker: Dict[str, Dict[str, Any]],
    nav_fresh_max_days: int,
    timeout: int,
    sec_user_agent: str,
    nav_auto_max_filings: int,
    sec_max_docs_per_filing: int,
    sec_cache_dir: Optional[Path],
    sec_use_cache: bool,
) -> Dict[str, Any]:
    session = make_requests_session(sec_user_agent)

    out_rows: List[Dict[str, Any]] = []
    notes: List[str] = []
    attempted = 0
    found = 0
    today_utc = normalize_ts_naive(UTC_NOW())

    try:
        ticker_map = get_sec_ticker_to_cik_map(
            session,
            timeout=timeout,
            cache_dir=(sec_cache_dir / "ticker_map") if sec_cache_dir else None,
            use_cache=sec_use_cache,
        )
    except Exception as e:
        return {
            "enabled": True,
            "source": "sec_filings_regex_v7_docscan_v11c",
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
        if not cik10:
            notes.append(f"{ticker}:ERR:no_cik")
            continue

        try:
            filings = get_sec_filing_candidates(
                session,
                cik10,
                timeout=timeout,
                cache_dir=(sec_cache_dir / "submissions") if sec_cache_dir else None,
                use_cache=sec_use_cache,
            )
        except Exception as e:
            notes.append(f"{ticker}:ERR:submissions:{type(e).__name__}:{str(e)[:120]}")
            continue

        if not filings:
            notes.append(f"{ticker}:ERR:no_recent_filing_candidates")
            continue

        chosen_row: Optional[Dict[str, Any]] = None
        fallback_review_row: Optional[Dict[str, Any]] = None
        market_date = parse_date((latest_price_by_ticker.get(ticker) or {}).get("data_date"))
        market_close = to_float((latest_price_by_ticker.get(ticker) or {}).get("close"))

        for filing in filings[:max(1, nav_auto_max_filings)]:
            filing_date = parse_date(filing.get("filing_date"))

            try:
                docs_to_scan, doc_notes = get_sec_document_candidates_for_filing(
                    session=session,
                    filing=filing,
                    timeout=timeout,
                    max_docs_per_filing=sec_max_docs_per_filing,
                    cache_dir=(sec_cache_dir / "filing_index") if sec_cache_dir else None,
                    use_cache=sec_use_cache,
                )
                for dn in doc_notes:
                    notes.append(f"{ticker}:{filing.get('form')}:{filing.get('filing_date')}:{dn}")
            except Exception as e:
                notes.append(f"{ticker}:WARN:doc_candidates:{filing.get('form')}:{type(e).__name__}:{str(e)[:100]}")
                docs_to_scan = [{
                    "doc_name": filing.get("primary_document"),
                    "url": filing.get("source_url"),
                    "doc_score": score_sec_document_name(str(filing.get("primary_document") or ""), str(filing.get("primary_document") or "")),
                    "doc_source": "primary_document",
                }]

            filing_had_any_candidates = False

            for doc in docs_to_scan:
                try:
                    raw_text = sec_fetch_text(
                        session,
                        doc["url"],
                        timeout=timeout,
                        cache_dir=(sec_cache_dir / "docs") if sec_cache_dir else None,
                        use_cache=sec_use_cache,
                    )
                    text = filing_html_to_text(raw_text)
                except Exception as e:
                    notes.append(
                        f"{ticker}:WARN:doc_fetch:{filing.get('form')}:{filing.get('filing_date')}:"
                        f"{doc.get('doc_name')}:{type(e).__name__}:{str(e)[:100]}"
                    )
                    continue

                doc_period_anchor, doc_period_anchor_source, doc_period_anchor_match_text = extract_doc_period_anchor(
                    text=text,
                    upper_bound=filing_date,
                )

                candidates = extract_nav_candidates_from_text(
                    text=text,
                    market_close=market_close,
                    max_candidates=AUTO_NAV_MAX_CANDIDATES_PER_FILING,
                )
                if not candidates:
                    continue

                filing_had_any_candidates = True

                for cand in candidates:
                    nav_ref_date = parse_date(cand.get("nav_ref_date"))
                    effective_nav_date, nav_date_source, date_binding_mode = choose_effective_nav_date(
                        nav_ref_date=nav_ref_date,
                        filing_date=filing_date,
                        market_date=market_date,
                        today_utc=today_utc,
                        doc_period_anchor=doc_period_anchor,
                        candidate_value_role=str(cand.get("candidate_value_role") or ""),
                        comparison_context_flag=bool(cand.get("comparison_context_flag")),
                        multi_value_row_flag=bool(cand.get("multi_value_row_flag")),
                    )

                    row = make_nav_overlay_row(
                        ticker=ticker,
                        nav=to_float(cand.get("nav")),
                        nav_date=effective_nav_date,
                        source_url=doc["url"],
                        note=(
                            f"auto_sec:{filing.get('form')}:{filing.get('filing_date')}:"
                            f"doc={doc.get('doc_name')}:doc_score={doc.get('doc_score')}:"
                            f"candidate_rank={cand.get('candidate_rank')}"
                        ),
                        source_kind="auto_sec",
                        latest_price_by_ticker=latest_price_by_ticker,
                        nav_fresh_max_days=nav_fresh_max_days,
                        nav_date_source=nav_date_source,
                        extra_fields={
                            "filing_form": filing.get("form"),
                            "filing_date": filing.get("filing_date"),
                            "match_score": cand.get("match_score"),
                            "matched_pattern": cand.get("matched_pattern"),
                            "matched_snippet": cand.get("matched_snippet"),
                            "candidate_rank": cand.get("candidate_rank"),
                            "candidate_count": cand.get("candidate_count"),
                            "percent_context_flag": cand.get("percent_context_flag"),
                            "suspicious_terms_flag": cand.get("suspicious_terms_flag"),
                            "date_component_flag": cand.get("date_component_flag"),
                            "extraction_method": cand.get("extraction_method"),
                            "derived_from_price": cand.get("derived_from_price"),
                            "derived_from_rel": cand.get("derived_from_rel"),
                            "derived_from_pct": cand.get("derived_from_pct"),
                            "price_obs_date": cand.get("price_obs_date"),
                            "price_obs_date_source": cand.get("price_obs_date_source"),
                            "price_obs_match_text": cand.get("price_obs_match_text"),
                            "nav_ref_date_extracted": cand.get("nav_ref_date"),
                            "nav_ref_date_source": cand.get("nav_ref_date_source"),
                            "nav_ref_match_text": cand.get("nav_ref_match_text"),
                            "hard_skip_context_flag": cand.get("hard_skip_context_flag"),
                            "hard_skip_context_tags": cand.get("hard_skip_context_tags"),
                            "context_penalty_total": cand.get("context_penalty_total"),
                            "context_penalty_tags": cand.get("context_penalty_tags"),
                            "section_bonus_total": cand.get("section_bonus_total"),
                            "section_bonus_tags": cand.get("section_bonus_tags"),
                            "doc_name": doc.get("doc_name"),
                            "doc_score": doc.get("doc_score"),
                            "doc_source": doc.get("doc_source"),
                            "doc_period_anchor": doc_period_anchor.strftime("%Y-%m-%d") if doc_period_anchor is not None else None,
                            "doc_period_anchor_source": doc_period_anchor_source,
                            "doc_period_anchor_match_text": doc_period_anchor_match_text,
                            "candidate_value_role": cand.get("candidate_value_role"),
                            "comparison_context_flag": cand.get("comparison_context_flag"),
                            "multi_value_row_flag": cand.get("multi_value_row_flag"),
                            "date_binding_mode": date_binding_mode,
                            "local_role_ctx": cand.get("local_role_ctx"),
                        },
                    )
                    row = finalize_nav_row_dq(row)

                    if fallback_review_row is None:
                        fallback_review_row = row
                    else:
                        prev_score = to_float(fallback_review_row.get("match_score")) or -999.0
                        curr_score = to_float(row.get("match_score")) or -999.0
                        prev_doc_score = to_float(fallback_review_row.get("doc_score")) or -999.0
                        curr_doc_score = to_float(row.get("doc_score")) or -999.0
                        if (curr_score, curr_doc_score) > (prev_score, prev_doc_score):
                            fallback_review_row = row

                    if row.get("used_in_stats"):
                        chosen_row = row
                        break

                if chosen_row is not None:
                    break

            if chosen_row is not None:
                break

            if not filing_had_any_candidates:
                notes.append(
                    f"{ticker}:INFO:no_match_in_filing:{filing.get('form')}:{filing.get('filing_date')}:"
                    f"docs_scanned={len(docs_to_scan)}"
                )

        if chosen_row is not None:
            out_rows.append(chosen_row)
            found += 1
            notes.append(
                f"{ticker}:OK:{chosen_row.get('filing_form')}:{chosen_row.get('filing_date')}:"
                f"doc={chosen_row.get('doc_name')}:doc_score={chosen_row.get('doc_score')}:"
                f"score={chosen_row.get('match_score')}:dq={chosen_row.get('dq_status')}:"
                f"method={chosen_row.get('extraction_method')}:nav_date_source={chosen_row.get('nav_date_source')}:"
                f"date_binding_mode={chosen_row.get('date_binding_mode')}"
            )
        elif fallback_review_row is not None:
            out_rows.append(fallback_review_row)
            found += 1
            notes.append(
                f"{ticker}:REVIEW_ONLY:{fallback_review_row.get('filing_form')}:{fallback_review_row.get('filing_date')}:"
                f"doc={fallback_review_row.get('doc_name')}:doc_score={fallback_review_row.get('doc_score')}:"
                f"score={fallback_review_row.get('match_score')}:dq={fallback_review_row.get('dq_status')}:"
                f"method={fallback_review_row.get('extraction_method')}:nav_date_source={fallback_review_row.get('nav_date_source')}:"
                f"date_binding_mode={fallback_review_row.get('date_binding_mode')}"
            )
        else:
            notes.append(f"{ticker}:ERR:no_nav_match")

    return {
        "enabled": True,
        "source": "sec_filings_regex_v7_docscan_v11c",
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
    manual_rows = list(manual["items"])
    auto_rows = list(auto_nav_result.get("rows") or [])

    effective_by_ticker: Dict[str, Dict[str, Any]] = {}

    for r in auto_rows:
        if r.get("used_in_stats"):
            effective_by_ticker[r["ticker"]] = r

    manual_override_tickers: List[str] = []
    for r in manual_rows:
        if r.get("used_in_stats"):
            if r["ticker"] in effective_by_ticker:
                manual_override_tickers.append(r["ticker"])
                for auto_r in auto_rows:
                    if auto_r.get("ticker") == r["ticker"] and auto_r.get("used_in_stats"):
                        auto_r["used_in_stats"] = False
                        auto_r["dq_status"] = "OVERRIDDEN_BY_MANUAL"
                        auto_r["review_flag"] = "OVERRIDDEN_BY_MANUAL"
            effective_by_ticker[r["ticker"]] = r

    effective_rows = list(effective_by_ticker.values())

    display_rows = sorted(
        auto_rows + manual_rows,
        key=lambda x: (
            0 if x.get("used_in_stats") else 1,
            x.get("ticker") or "",
            x.get("source_kind") or "",
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

    auto_total_count = len(auto_rows)
    auto_used_in_stats_count = sum(1 for r in auto_rows if r.get("source_kind") == "auto_sec" and r.get("used_in_stats"))
    auto_review_count = sum(1 for r in auto_rows if str(r.get("dq_status") or "").startswith("REVIEW"))
    auto_excluded_count = sum(1 for r in auto_rows if str(r.get("dq_status") or "").startswith("EXCLUDED"))
    auto_review_only_count = sum(1 for r in auto_rows if r.get("source_kind") == "auto_sec" and not r.get("used_in_stats"))
    manual_used_in_stats_count = sum(1 for r in manual_rows if r.get("used_in_stats"))
    manual_invalid_count = sum(1 for r in manual_rows if not r.get("valid_for_stats"))
    effective_auto_count = sum(1 for r in effective_rows if r.get("source_kind") == "auto_sec")
    effective_manual_count = sum(1 for r in effective_rows if r.get("source_kind") == "manual")

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
        "auto_total_count": auto_total_count,
        "auto_used_in_stats_count": auto_used_in_stats_count,
        "auto_review_count": auto_review_count,
        "auto_excluded_count": auto_excluded_count,
        "auto_review_only_count": auto_review_only_count,
        "manual_used_in_stats_count": manual_used_in_stats_count,
        "manual_invalid_count": manual_invalid_count,
        "effective_auto_count": effective_auto_count,
        "effective_manual_count": effective_manual_count,
        "effective_structural_count": len(effective_rows),
        "effective_structural_fresh_count": len(fresh_rows),
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


def determine_proxy_signal(basket_summary: Dict[str, Any], proxy_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        median_ret5 is not None and median_ret5 <= -8.0 and
        extreme_z_share is not None and extreme_z_share >= 50.0 and
        below_ma20_share is not None and below_ma20_share >= 80.0
    ):
        signal = "ALERT"
        reasons.append("bdc_basket_median_ret5<=-8 AND extreme_z_share>=50% AND below_ma20_share>=80%")
        tags.append("MARKET_PROXY_STRESS")

    if signal != "ALERT":
        if median_ret5 is not None and median_ret5 <= -4.0 and below_ma20_share is not None and below_ma20_share >= 80.0:
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

    return {"signal": signal, "reasons": reasons or ["no_proxy_rule_triggered"], "tags": tags or ["NONE"]}


def determine_structural_signal(nav_info: Dict[str, Any], event_info: Dict[str, Any]) -> Dict[str, Any]:
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
    elif median_discount_fresh is not None and nav_cov_fresh >= 3 and median_discount_fresh <= -20.0:
        signal = "ALERT"
        reasons.append("fresh_nav_median_discount<=-20 with coverage>=3")
        tags.append("NAV_DISCOUNT_STRESS")
    elif median_discount_fresh is not None and nav_cov_fresh >= 3 and median_discount_fresh <= -15.0 and watch_recent >= 1:
        signal = "ALERT"
        reasons.append("fresh_nav_discount<=-15 with coverage>=3 + recent_watch_event")
        tags.append("COMPOSITE_STRESS")

    if signal != "ALERT":
        if watch_recent >= 1:
            signal = "WATCH"
            reasons.append(f"recent_manual_event_watch_count={watch_recent}")
            tags.append("EVENT_WATCH")
        elif median_discount_fresh is not None and nav_cov_fresh >= 3 and median_discount_fresh <= -10.0:
            signal = "WATCH"
            reasons.append("fresh_nav_median_discount<=-10 with coverage>=3")
            tags.append("NAV_DISCOUNT_WIDE")

    return {"signal": signal, "reasons": reasons or ["no_structural_rule_triggered"], "tags": tags or ["NONE"]}


def combine_signals(proxy_info: Dict[str, Any], structural_info: Dict[str, Any]) -> Dict[str, Any]:
    proxy_signal = proxy_info["signal"]
    structural_signal = structural_info["signal"]

    proxy_rank = SEVERITY_ORDER.get(proxy_signal, 0)
    structural_rank = SEVERITY_ORDER.get(structural_signal, 0)

    combined_signal = "ALERT" if max(proxy_rank, structural_rank) == 2 else ("WATCH" if max(proxy_rank, structural_rank) == 1 else "NONE")

    if proxy_rank > 0 and structural_rank == 0:
        basis = "PROXY_ONLY"
    elif proxy_rank == 0 and structural_rank > 0:
        basis = "STRUCTURAL_ONLY"
    elif proxy_rank > 0 and structural_rank > 0:
        basis = "MIXED"
    else:
        basis = "NONE"

    reasons: List[str] = []
    tags: List[str] = []
    if proxy_rank > 0:
        reasons.extend([f"proxy:{x}" for x in proxy_info.get("reasons", [])])
        tags.extend([f"proxy:{x}" for x in proxy_info.get("tags", [])])
    if structural_rank > 0:
        reasons.extend([f"structural:{x}" for x in structural_info.get("reasons", [])])
        tags.extend([f"structural:{x}" for x in structural_info.get("tags", [])])

    return {
        "combined_signal": combined_signal,
        "signal_basis": basis,
        "reasons": reasons or ["no_rule_triggered"],
        "tags": tags or ["NONE"],
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
    event_conf = "OK" if event_valid_total >= 1 else ("TEMPLATE_ONLY" if event_raw_count >= 1 else "NA")

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
    rows = [r for r in existing if isinstance(r, dict)] if isinstance(existing, list) else []
    rows.append(new_row)
    rows = sorted(rows, key=lambda x: x.get("generated_at_utc", ""))
    return rows[-max_rows:] if max_rows > 0 else rows


def escape_markdown_cell(v: Any) -> str:
    if isinstance(v, float):
        s = f"{v:.6f}"
    elif v is None:
        s = "NA"
    else:
        s = str(v)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\\", "\\\\")
    s = s.replace("|", "\\|")
    s = s.replace("\n", "<br>")
    return s


def markdown_table(rows: List[Dict[str, Any]], columns: List[Tuple[str, str]]) -> str:
    if not rows:
        return "| note |\n| --- |\n| NA |"
    headers = [escape_markdown_cell(c[0]) for c in columns]
    keys = [c[1] for c in columns]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        vals = [escape_markdown_cell(r.get(k)) for k in keys]
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
        "coverage", "median_ret1_pct", "median_ret5_pct", "median_z60",
        "median_drawdown_20d_pct", "extreme_z_count", "extreme_z_share",
        "ret5_le_minus5_count", "ret5_le_minus5_share", "below_ma20_count",
        "below_ma20_share",
    ]:
        lines.append(f"- {k}: `{basket.get(k)}`")
    lines.append("")
    lines.append(markdown_table(
        price_rows,
        [
            ("ticker", "ticker"), ("class", "class"), ("close", "close"), ("data_date", "data_date"),
            ("ret1%", "ret1_pct"), ("ret5%", "ret5_pct"), ("z60", "z60"), ("p60", "p60"),
            ("p252", "p252"), ("dd20%", "drawdown_20d_pct"), ("px_vs_ma20%", "price_vs_ma20_pct"),
            ("source", "source_url"), ("note", "note"),
        ],
    ))
    lines.append("")

    lines.append("## 2) NAV Overlay (manual + auto SEC, optional)")
    for k in [
        "path", "as_of_date", "confidence", "raw_row_count", "template_excluded_count",
        "manual_valid_count", "auto_enabled", "auto_source", "auto_attempted_count",
        "auto_found_count", "manual_override_tickers", "coverage_total", "coverage_fresh",
        "median_discount_pct_fresh", "median_discount_pct_all",
    ]:
        lines.append(f"- {k}: `{nav.get(k)}`")
    lines.append("")
    lines.append("### Coverage decomposition")
    for k in [
        "auto_total_count", "auto_used_in_stats_count", "auto_review_count", "auto_excluded_count",
        "auto_review_only_count", "manual_used_in_stats_count", "manual_invalid_count",
        "effective_auto_count", "effective_manual_count", "effective_structural_count",
        "effective_structural_fresh_count",
    ]:
        lines.append(f"- {k}: `{nav.get(k)}`")
    lines.append("")
    lines.append(markdown_table(
        nav.get("items", []),
        [
            ("ticker", "ticker"),
            ("source_kind", "source_kind"),
            ("doc_name", "doc_name"),
            ("doc_score", "doc_score"),
            ("doc_period_anchor", "doc_period_anchor"),
            ("candidate_role", "candidate_value_role"),
            ("date_binding_mode", "date_binding_mode"),
            ("extraction_method", "extraction_method"),
            ("used_in_stats", "used_in_stats"),
            ("dq_status", "dq_status"),
            ("review_flag", "review_flag"),
            ("match_score", "match_score"),
            ("matched_pattern", "matched_pattern"),
            ("price_obs_date", "price_obs_date"),
            ("nav_ref_date", "nav_ref_date_extracted"),
            ("nav_date_used", "nav_date"),
            ("nav_date_source", "nav_date_source"),
            ("filing_date", "filing_date"),
            ("market_close", "market_close"),
            ("market_date", "market_date"),
            ("premium_discount_pct", "premium_discount_pct"),
            ("nav_age_days", "nav_age_days"),
            ("fresh_for_rule", "fresh_for_rule"),
            ("source", "source_url"),
            ("note", "note"),
        ],
    ))

    auto_snippets = [r for r in nav.get("items", []) if r.get("source_kind") == "auto_sec"]
    if auto_snippets:
        lines.append("")
        lines.append("### NAV auto match snippets")
        for r in auto_snippets:
            lines.append(
                f"- {r.get('ticker')} | used_in_stats={r.get('used_in_stats')} | "
                f"dq_status={r.get('dq_status')} | doc={r.get('doc_name')} | doc_score={r.get('doc_score')} | "
                f"candidate_role={r.get('candidate_value_role')} | date_binding_mode={r.get('date_binding_mode')} | "
                f"score={r.get('match_score')} | pattern={r.get('matched_pattern')} | method={r.get('extraction_method')}"
            )
            lines.append(f"  - snippet: `{sanitize_inline_code_text(r.get('matched_snippet'))}`")
            if r.get("price_obs_match_text"):
                lines.append(f"  - price_obs_match: `{sanitize_inline_code_text(r.get('price_obs_match_text'))}`")
            if r.get("nav_ref_match_text"):
                lines.append(f"  - nav_ref_match: `{sanitize_inline_code_text(r.get('nav_ref_match_text'))}`")
            if r.get("doc_period_anchor_match_text"):
                lines.append(f"  - doc_period_anchor_match: `{sanitize_inline_code_text(r.get('doc_period_anchor_match_text'))}`")
            if r.get("local_role_ctx"):
                lines.append(f"  - local_role_ctx: `{sanitize_inline_code_text(r.get('local_role_ctx'))}`")
            if r.get("hard_skip_context_tags"):
                lines.append(f"  - context_hard_skip: `{sanitize_inline_code_text(','.join(r.get('hard_skip_context_tags') or []))}`")
            if r.get("context_penalty_tags"):
                lines.append(f"  - context_penalties: `{sanitize_inline_code_text(','.join(r.get('context_penalty_tags') or []))}`")
            if r.get("section_bonus_tags"):
                lines.append(f"  - section_bonus: `{sanitize_inline_code_text(','.join(r.get('section_bonus_tags') or []))}`")
            if r.get("derived_from_price") is not None:
                lines.append(
                    f"  - implied_from: price={r.get('derived_from_price')} | "
                    f"rel={r.get('derived_from_rel')} | pct={r.get('derived_from_pct')}"
                )

    if nav.get("auto_notes"):
        lines.append("")
        lines.append("### NAV auto fetch notes")
        for note in nav.get("auto_notes", []):
            lines.append(f"- {note}")
    lines.append("")

    lines.append("## 3) Event Overlay (manual, optional)")
    for k in [
        "path", "as_of_date", "recent_window_days", "raw_row_count", "template_excluded_count",
        "event_count_total", "event_count_recent", "alert_recent_count", "watch_recent_count",
        "latest_recent_event_date",
    ]:
        lines.append(f"- {k}: `{events.get(k)}`")
    lines.append("")
    lines.append(markdown_table(
        events.get("events", []),
        [
            ("event_date", "event_date"), ("category", "category"), ("entity", "entity"),
            ("severity", "severity"), ("is_recent", "is_recent"), ("valid_for_stats", "valid_for_stats"),
            ("template_excluded", "template_excluded"), ("title", "title"), ("source", "source_url"),
            ("note", "note"),
        ],
    ))
    lines.append("")

    lines.append("## 4) Public Credit Context (reference-only; not recomputed here)")
    lines.append(f"- enabled: `{context.get('enabled')}`")
    lines.append(f"- source_path: `{context.get('source_path')}`")
    lines.append(f"- reference_only: `{context.get('reference_only')}`")
    ctx_rows: List[Dict[str, Any]] = []
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
            ("series", "series"), ("source_module", "source_module"), ("signal", "signal"),
            ("value", "value"), ("data_date", "data_date"), ("reason", "reason"), ("tag", "tag"),
        ],
    ))
    lines.append("")

    lines.append("## 5) Confidence / DQ")
    for k, v in summary["confidence"].items():
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

    sec_cache_dir = Path(args.sec_cache_dir) if args.sec_cache_dir else (out_dir / "sec_cache")
    if args.sec_use_cache:
        ensure_dir(sec_cache_dir)

    manual_events_path = Path(args.manual_events) if args.manual_events else inputs_dir / "manual_events.json"
    manual_nav_path = Path(args.manual_nav) if args.manual_nav else inputs_dir / "manual_nav.json"
    unified_json_path = Path(args.unified_json) if args.unified_json else None

    create_manual_event_template(manual_events_path)
    create_manual_nav_template(manual_nav_path)

    tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
    basket_tickers = [t for t in tickers if t in DEFAULT_BDC_TICKERS] or DEFAULT_BDC_TICKERS.copy()
    proxy_tickers = [t for t in tickers if t in DEFAULT_PROXY_TICKERS] or DEFAULT_PROXY_TICKERS.copy()

    end_date = normalize_ts_naive(UTC_NOW())
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
            sec_max_docs_per_filing=args.sec_max_docs_per_filing,
            sec_cache_dir=sec_cache_dir if args.sec_use_cache else None,
            sec_use_cache=bool(args.sec_use_cache),
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

    proxy_signal_info = determine_proxy_signal(basket_summary=basket_summary, proxy_rows=price_rows)
    structural_signal_info = determine_structural_signal(nav_info=nav_info, event_info=event_info)
    combined_signal_info = combine_signals(proxy_info=proxy_signal_info, structural_info=structural_signal_info)
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
            "source_policy": "stooq_bdc_proxy + manual_nav_overlay + auto_sec_nav_v7_docscan_v11c + manual_event_overlay + optional_unified_reference_only",
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
                "sec_max_docs_per_filing": args.sec_max_docs_per_filing,
                "sec_use_cache": bool(args.sec_use_cache),
                "sec_cache_dir": str(sec_cache_dir) if args.sec_use_cache else None,
                "auto_nav_min_match_score": AUTO_NAV_MIN_MATCH_SCORE,
                "auto_nav_review_premium_pct": AUTO_NAV_REVIEW_PREMIUM_PCT,
                "auto_nav_exclude_premium_pct": AUTO_NAV_EXCLUDE_PREMIUM_PCT,
                "auto_nav_review_discount_pct": AUTO_NAV_REVIEW_DISCOUNT_PCT,
            },
        },
        "summary": {
            "signal": combined_signal_info["combined_signal"],
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
            "Auto NAV from SEC excludes date-component contamination and all REVIEW rows from structural stats.",
            "Implied NAV extraction from price + premium/discount sentences is enabled to reduce false data loss.",
            "v1.11c keeps SEC retry/backoff and optional cache for fetch stability.",
            "v1.11c keeps filing index doc scan instead of primaryDocument-only logic.",
            "v1.11c filters doc_period_anchor toward dates <= filing_date when possible.",
            "v1.11c uses match-local role context to reduce false comparison classification.",
            "v1.11c keeps filing-date-only NAV dating as REVIEW_ONLY, excluded from structural stats.",
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
    report_md_path.write_text(build_report(latest), encoding="utf-8")

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