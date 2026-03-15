
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_private_credit_nav_overlay.py (v0.1-split)

Purpose
-------
Standalone NAV-only sidecar extracted from build_private_credit_monitor.py.

Scope
-----
- Fetch latest market close for selected BDC tickers via yfinance
- Load manual NAV overlay rows
- Optionally auto-discover NAV from SEC
  * XBRL companyconcept first
  * XBRL companyfacts discovery second
  * HTML / regex / table parsing as fallback
- Apply deterministic DQ / review rules
- Output a single audit-friendly JSON file

Notes
-----
- This script intentionally excludes BDC market proxy / event overlay / unified context.
- Manual valid rows override auto SEC rows for the same ticker.
- Output is JSON-first.
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
import yfinance as yf


SCRIPT_NAME = "build_private_credit_nav_overlay.py"
SCRIPT_VERSION = "v0.1-split"
UTC_NOW = lambda: datetime.now(timezone.utc).replace(microsecond=0)

DEFAULT_BDC_TICKERS = ["ARCC", "BXSL", "OBDC", "FSK", "PSEC"]

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_ARCHIVES_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"
SEC_ARCHIVES_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"
SEC_XBRL_COMPANYCONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{concept}.json"
SEC_XBRL_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

AUTO_NAV_ALLOWED_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A", "8-K", "8-K/A"}
REQUEST_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
REQUEST_RETRY_SLEEP_SECONDS = [2, 4, 8]

XBRL_STANDARD_TAXONOMIES = {"us-gaap", "ifrs-full", "dei", "srt"}
XBRL_NAV_STANDARD_CONCEPTS = [("us-gaap", "NetAssetValuePerShare")]
XBRL_NAV_LABEL_KEYWORDS = [
    "net asset value per share",
    "net assets per share",
    "nav per share",
]

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
        re.compile(r"\bas of\s+([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})", re.I),
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
        re.compile(r"\bas of\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})", re.I),
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
        re.compile(r"\bas of\s+([A-Za-z]{3,9}\.?)\s+([0-9]{1,2}),\s*(20[0-9]{2})", re.I),
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
        re.compile(r"\bas of\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})", re.I),
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

HTML_TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.I | re.S)
HTML_TR_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.I | re.S)
HTML_TDTH_RE = re.compile(r"<(td|th)\b([^>]*)>(.*?)</\1>", re.I | re.S)
HTML_COLSPAN_RE = re.compile(r'\bcolspan\s*=\s*["\']?([0-9]+)', re.I)
MDY_DATE_RE = re.compile(r"\b([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})\b")
MONTHNAME_DATE_RE = re.compile(r"\b([A-Za-z]{3,9}\.?)[ ]+([0-9]{1,2}),[ ]*(20[0-9]{2})\b", re.I)

AUTO_NAV_MIN_MATCH_SCORE = 3.0
AUTO_NAV_REVIEW_PREMIUM_PCT = 15.0
AUTO_NAV_EXCLUDE_PREMIUM_PCT = 25.0
AUTO_NAV_REVIEW_DISCOUNT_PCT = -45.0
AUTO_NAV_MAX_CANDIDATES_PER_FILING = 12


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build standalone private credit NAV overlay JSON")
    p.add_argument("--out-dir", default="private_credit_cache", help="Output folder")
    p.add_argument("--output-json", default=None, help="Optional output JSON path (default: <out-dir>/nav_latest.json)")
    p.add_argument("--manual-nav", default=None, help="Path to manual NAV JSON")
    p.add_argument("--history-max-rows", type=int, default=1000, help="Max rows for nav_history.json")
    p.add_argument("--lookback-calendar-days", type=int, default=120, help="Calendar days to request from yfinance")
    p.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    p.add_argument("--tickers", default=",".join(DEFAULT_BDC_TICKERS), help="Comma-separated tickers to monitor")
    p.add_argument("--nav-fresh-max-days", type=int, default=120, help="NAV older than this is treated as stale for structural coverage")
    p.add_argument("--nav-auto-source", default="sec", choices=["sec", "off"], help="Auto NAV source")
    p.add_argument("--sec-user-agent", default="private-credit-nav-overlay/0.1 your_email@example.com", help="SEC User-Agent header")
    p.add_argument("--nav-auto-max-filings", type=int, default=6, help="Max recent filings to scan per ticker")
    p.add_argument("--sec-max-docs-per-filing", type=int, default=5, help="Max SEC docs to scan per filing")
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


def create_manual_nav_template(path: Path) -> None:
    if path.exists():
        return
    template = {
        "schema_version": "private_credit_manual_nav_v1",
        "as_of_date": "YYYY-MM-DD",
        "notes": [
            "Manual NAV overlay for selected BDC names.",
            "nav_date should be the NAV as-of date, e.g. quarter-end.",
            "This script compares latest market close vs provided NAV.",
            "Template rows are excluded from statistics until valid.",
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


def fetch_yfinance_daily(symbol: str, start_date: pd.Timestamp, end_date: pd.Timestamp, timeout: int) -> Tuple[pd.DataFrame, str, Optional[str]]:
    start_ts = normalize_ts_naive(start_date)
    end_ts = normalize_ts_naive(end_date)
    if start_ts is None or end_ts is None:
        return pd.DataFrame(), f"yfinance://{symbol}", "ERR:bad_date_range"

    end_exclusive = end_ts + pd.Timedelta(days=1)
    url = (
        f"yfinance://{symbol}"
        f"?start={start_ts.strftime('%Y-%m-%d')}"
        f"&end={end_exclusive.strftime('%Y-%m-%d')}"
        f"&interval=1d&auto_adjust=false&actions=true"
    )

    try:
        df = yf.download(
            symbol,
            start=start_ts.strftime("%Y-%m-%d"),
            end=end_exclusive.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=False,
            actions=True,
            progress=False,
            threads=False,
            timeout=timeout,
        )

        if df is None or df.empty:
            return pd.DataFrame(), url, "ERR:no_data"

        if isinstance(df.columns, pd.MultiIndex):
            flat_cols = []
            for col in df.columns:
                flat_cols.append(col[0] if isinstance(col, tuple) else col)
            df.columns = flat_cols

        df = df.reset_index()
        if "Date" not in df.columns:
            if "Datetime" in df.columns:
                df = df.rename(columns={"Datetime": "Date"})
            else:
                df = df.rename(columns={df.columns[0]: "Date"})

        for col in ["Close", "Adj Close", "Dividends", "Stock Splits"]:
            if col not in df.columns:
                if col == "Adj Close" and "Close" in df.columns:
                    df[col] = df["Close"]
                else:
                    df[col] = 0.0 if col in {"Dividends", "Stock Splits"} else np.nan

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for col in ["Close", "Adj Close", "Dividends", "Stock Splits"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
        if "Adj Close" in df.columns:
            df["Adj Close"] = df["Adj Close"].fillna(df["Close"])
        if df.empty:
            return pd.DataFrame(), url, "ERR:empty_after_clean"

        return df[["Date", "Close", "Adj Close", "Dividends", "Stock Splits"]].copy(), url, None
    except Exception as e:
        return pd.DataFrame(), url, f"ERR:{type(e).__name__}:{str(e)[:160]}"


def compute_latest_market_snapshot(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {
            "data_date": None,
            "close": None,
            "adj_close": None,
            "prev_close": None,
            "ret1_pct": None,
            "points": 0,
        }

    work = df.copy()
    work["Date"] = pd.to_datetime(work["Date"], errors="coerce")
    work["Close"] = pd.to_numeric(work["Close"], errors="coerce")
    work["Adj Close"] = pd.to_numeric(work["Adj Close"], errors="coerce")
    work = work.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)

    if work.empty:
        return {
            "data_date": None,
            "close": None,
            "adj_close": None,
            "prev_close": None,
            "ret1_pct": None,
            "points": 0,
        }

    last_close = float(work["Close"].iloc[-1])
    last_adj = float(work["Adj Close"].iloc[-1]) if "Adj Close" in work.columns and not pd.isna(work["Adj Close"].iloc[-1]) else last_close
    prev_close = float(work["Close"].iloc[-2]) if len(work) >= 2 else None
    ret1 = safe_pct(last_close, prev_close)

    return {
        "data_date": work["Date"].iloc[-1].strftime("%Y-%m-%d"),
        "close": safe_num(last_close),
        "adj_close": safe_num(last_adj),
        "prev_close": safe_num(prev_close),
        "ret1_pct": safe_num(ret1),
        "points": int(len(work)),
    }


def clean_snippet(s: str, max_len: int = 280) -> str:
    s = WHITESPACE_RE.sub(" ", (s or "")).strip()
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


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


def collect_date_matches_from_ctx(ctx: str, specs: List[Tuple[str, re.Pattern]]) -> List[Dict[str, Any]]:
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


def extract_best_date_from_ctx(ctx: str, specs: List[Tuple[str, re.Pattern]]) -> Tuple[Optional[pd.Timestamp], Optional[str], Optional[str]]:
    matches = collect_date_matches_from_ctx(ctx, specs)
    if not matches:
        return None, None, None
    matches = sorted(matches, key=lambda x: (x["priority"], -x["ts"].value))
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

    value_token = str(safe_num(matched_value, 4)).rstrip("0").rstrip(".") if matched_value is not None else ""
    value_pos = ctx.find(value_token) if value_token else -1
    comparison_context_flag = bool(list(COMPARISON_PHRASE_RE.finditer(ctx_lower)))

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


def _clean_html_cell_text(s: str) -> str:
    x = html_lib.unescape(s or "")
    x = HTML_COMMENT_RE.sub(" ", x)
    x = HTML_SCRIPT_STYLE_RE.sub(" ", x)
    x = HTML_TAG_RE.sub(" ", x)
    x = WHITESPACE_RE.sub(" ", x)
    return x.strip()


def _cell_colspan(attrs: str) -> int:
    m = HTML_COLSPAN_RE.search(attrs or "")
    if not m:
        return 1
    try:
        return max(1, int(m.group(1)))
    except Exception:
        return 1


def _parse_mdy_date_cell(text: str) -> Optional[pd.Timestamp]:
    if not text:
        return None

    m = MDY_DATE_RE.search(text)
    if m:
        try:
            return pd.Timestamp(year=int(m.group(3)), month=int(m.group(1)), day=int(m.group(2))).normalize()
        except Exception:
            pass

    m2 = MONTHNAME_DATE_RE.search(text)
    if m2:
        try:
            month = normalize_month_token(m2.group(1))
            if month is not None:
                return pd.Timestamp(year=int(m2.group(3)), month=month, day=int(m2.group(2))).normalize()
        except Exception:
            pass

    return None


def _extract_unique_nearby_dates(ctx: str, limit: int = 6) -> List[pd.Timestamp]:
    out: List[pd.Timestamp] = []
    seen = set()

    for pat_label, pat in [("generic_monthname", MONTHNAME_DATE_RE), ("generic_numeric", MDY_DATE_RE)]:
        for m in pat.finditer(ctx or ""):
            try:
                if pat_label == "generic_monthname":
                    month = normalize_month_token(m.group(1))
                    if month is None:
                        continue
                    ts = pd.Timestamp(year=int(m.group(3)), month=month, day=int(m.group(2))).normalize()
                else:
                    ts = pd.Timestamp(year=int(m.group(3)), month=int(m.group(1)), day=int(m.group(2))).normalize()
            except Exception:
                continue

            key = ts.strftime("%Y-%m-%d")
            if key in seen:
                continue
            seen.add(key)
            out.append(ts)

    out = sorted(out, key=lambda x: x.value)
    return out[-limit:]


def _extract_row_values_after_nav_label(ctx: str, max_values: int = 4) -> List[float]:
    if not ctx:
        return []

    m = re.search(r"(?:net asset value per share|net assets per share|nav per share)", ctx, re.I)
    if not m:
        return []

    tail = ctx[m.end():m.end() + 180]
    tokens = re.findall(r"\$?[0-9]{1,3}(?:\.[0-9]{1,4})?|[A-Za-z][A-Za-z\-]*|[%xX]", tail)

    values: List[float] = []
    started = False
    for tok in tokens:
        clean = tok.replace("$", "").strip()
        if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,4})?", clean):
            try:
                values.append(float(clean))
                started = True
                if len(values) >= max_values:
                    break
                continue
            except Exception:
                continue
        if started:
            break

    return values


def extract_nearby_header_bound_candidate(
    text: str,
    start: int,
    end: int,
    doc_period_anchor: Optional[pd.Timestamp],
    market_close: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    anchor = normalize_ts_naive(doc_period_anchor)
    if anchor is None:
        return None

    header_ctx = text[max(0, start - 1600):start]
    row_ctx = text[max(0, start - 40):min(len(text), end + 220)]

    nearby_dates = _extract_unique_nearby_dates(header_ctx, limit=6)
    row_values = _extract_row_values_after_nav_label(row_ctx, max_values=4)

    if len(nearby_dates) < 2 or len(row_values) < 2:
        return None

    candidate_dates = nearby_dates[-len(row_values):]
    if len(candidate_dates) != len(row_values):
        return None

    try:
        bound_index = next(i for i, d in enumerate(candidate_dates) if d == anchor)
    except StopIteration:
        return None

    if bound_index >= len(row_values):
        return None

    bound_val = row_values[bound_index]
    if bound_val is None or not (0.5 <= bound_val <= 100.0):
        return None

    premium_discount_est = None
    if market_close is not None and market_close > 0:
        premium_discount_est = safe_num((market_close / float(bound_val) - 1.0) * 100.0)

    return {
        "extraction_method": "nearby_header_anchor",
        "nav": round(float(bound_val), 6),
        "matched_pattern": "nearby_header_nav_per_share_anchor",
        "matched_snippet": clean_snippet(row_ctx, max_len=320),
        "num_context": clean_snippet(row_ctx, max_len=200),
        "percent_context_flag": False,
        "suspicious_terms_flag": False,
        "date_component_flag": False,
        "match_score": 10.9,
        "premium_discount_est": premium_discount_est,
        "price_obs_date": None,
        "price_obs_date_source": None,
        "price_obs_match_text": None,
        "nav_ref_date": anchor.strftime("%Y-%m-%d"),
        "nav_ref_date_source": "nearby_header_exact_anchor",
        "nav_ref_match_text": anchor.strftime("%Y-%m-%d"),
        "hard_skip_context_flag": False,
        "hard_skip_context_tags": [],
        "context_penalty_total": 0.0,
        "context_penalty_tags": [],
        "section_bonus_total": 0.6,
        "section_bonus_tags": ["nearby_header_anchor"],
        "candidate_value_role": "current_bound_by_nearby_header",
        "comparison_context_flag": False,
        "multi_value_row_flag": True,
        "date_binding_mode": "nearby_header_anchor",
        "local_role_ctx": clean_snippet(row_ctx, max_len=180),
        "table_header_dates": [d.strftime("%Y-%m-%d") for d in candidate_dates],
        "table_row_values": [safe_num(v) for v in row_values],
        "table_bound_index": bound_index,
        "table_index": None,
        "table_row_index": None,
    }


def _parse_numeric_cell_value(text: str) -> Optional[float]:
    if text is None:
        return None
    s = _clean_html_cell_text(text)
    if not s or s in {"-", "—", "NA", "N/A", "$"}:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1].strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        try:
            return float(s)
        except Exception:
            return None
    return None


def _parse_html_tables(raw_html: str) -> List[List[List[str]]]:
    if not raw_html or "<table" not in raw_html.lower():
        return []
    tables: List[List[List[str]]] = []
    for table_html in HTML_TABLE_RE.findall(raw_html):
        table_rows: List[List[str]] = []
        for tr_html in HTML_TR_RE.findall(table_html):
            cells: List[str] = []
            for m in HTML_TDTH_RE.finditer(tr_html):
                attrs = m.group(2) or ""
                inner = m.group(3) or ""
                text = _clean_html_cell_text(inner)
                colspan = _cell_colspan(attrs)
                for _ in range(colspan):
                    cells.append(text)
            if cells:
                table_rows.append(cells)
        if table_rows:
            tables.append(table_rows)
    return tables


def _is_nav_per_share_label(text: str) -> bool:
    s = _clean_html_cell_text(text).lower()
    return (
        "net asset value per share" in s
        or s == "nav per share"
        or "asset value per share" in s
    )


def extract_nav_candidates_from_html_tables(
    raw_html: str,
    doc_period_anchor: Optional[pd.Timestamp],
    market_close: Optional[float] = None,
) -> List[Dict[str, Any]]:
    anchor = normalize_ts_naive(doc_period_anchor)
    if anchor is None or not raw_html:
        return []

    candidates: List[Dict[str, Any]] = []
    tables = _parse_html_tables(raw_html)
    if not tables:
        return candidates

    for table_idx, rows in enumerate(tables):
        header_idx = None
        header_dates: List[Optional[pd.Timestamp]] = []

        for i, row in enumerate(rows[:8]):
            parsed_dates = [_parse_mdy_date_cell(cell) for cell in row]
            if sum(d is not None for d in parsed_dates) >= 2:
                header_idx = i
                header_dates = parsed_dates
                break

        if header_idx is None:
            continue

        for row_idx in range(header_idx + 1, len(rows)):
            row = rows[row_idx]
            if not row:
                continue
            label = row[0] if row else ""
            if not _is_nav_per_share_label(label):
                continue

            max_len = min(len(row), len(header_dates))
            bound_idx = None
            bound_val = None
            for idx in range(max_len):
                d = header_dates[idx]
                if d is None or d != anchor:
                    continue
                v = _parse_numeric_cell_value(row[idx])
                if v is None:
                    continue
                bound_idx = idx
                bound_val = v
                break

            if bound_idx is None or bound_val is None:
                continue

            premium_discount_est = None
            if market_close is not None and market_close > 0:
                premium_discount_est = safe_num((market_close / float(bound_val) - 1.0) * 100.0)

            candidates.append({
                "extraction_method": "html_table_exact_anchor",
                "nav": round(float(bound_val), 6),
                "matched_pattern": "html_table_nav_per_share_anchor",
                "matched_snippet": clean_snippet(" | ".join(row), max_len=320),
                "num_context": clean_snippet(" | ".join(row), max_len=200),
                "percent_context_flag": False,
                "suspicious_terms_flag": False,
                "date_component_flag": False,
                "match_score": 12.5,
                "premium_discount_est": premium_discount_est,
                "price_obs_date": None,
                "price_obs_date_source": None,
                "price_obs_match_text": None,
                "nav_ref_date": anchor.strftime("%Y-%m-%d"),
                "nav_ref_date_source": "html_table_header_exact_anchor",
                "nav_ref_match_text": anchor.strftime("%m/%d/%Y"),
                "hard_skip_context_flag": False,
                "hard_skip_context_tags": [],
                "context_penalty_total": 0.0,
                "context_penalty_tags": [],
                "section_bonus_total": 0.8,
                "section_bonus_tags": ["html_table_nav_row"],
                "candidate_value_role": "current_bound_by_table_anchor",
                "comparison_context_flag": False,
                "multi_value_row_flag": True,
                "date_binding_mode": "html_table_exact_anchor",
                "local_role_ctx": clean_snippet(label, max_len=120),
                "table_header_dates": [d.strftime("%Y-%m-%d") if d is not None else None for d in header_dates],
                "table_row_values": [_parse_numeric_cell_value(cell) for cell in row],
                "table_bound_index": bound_idx,
                "table_index": table_idx,
                "table_row_index": row_idx,
            })

    return candidates


def extract_nav_candidates_from_text(
    text: str,
    market_close: Optional[float] = None,
    max_candidates: int = AUTO_NAV_MAX_CANDIDATES_PER_FILING,
    raw_html: Optional[str] = None,
    doc_period_anchor: Optional[pd.Timestamp] = None,
) -> List[Dict[str, Any]]:
    if not text and not raw_html:
        return []

    candidates: List[Dict[str, Any]] = []
    seen = set()

    if raw_html and doc_period_anchor is not None:
        for cand in extract_nav_candidates_from_html_tables(raw_html=raw_html, doc_period_anchor=doc_period_anchor, market_close=market_close):
            key = ("html_table_exact_anchor", round(float(cand.get("nav") or 0), 4), cand.get("matched_snippet", "")[:140])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(cand)

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

            if doc_period_anchor is not None and candidate_value_role == "current_first_column" and multi_value_row_flag:
                nearby_cand = extract_nearby_header_bound_candidate(
                    text=text,
                    start=m.start(),
                    end=m.end(),
                    doc_period_anchor=doc_period_anchor,
                    market_close=market_close,
                )
                if nearby_cand is not None:
                    nearby_key = ("nearby_header_anchor", round(float(nearby_cand.get("nav") or 0), 4), nearby_cand.get("matched_snippet", "")[:140])
                    if nearby_key not in seen:
                        seen.add(nearby_key)
                        candidates.append(nearby_cand)

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
                "table_header_dates": None,
                "table_row_values": None,
                "table_bound_index": None,
                "table_index": None,
                "table_row_index": None,
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
                "table_header_dates": None,
                "table_row_values": None,
                "table_bound_index": None,
                "table_index": None,
                "table_row_index": None,
            })

    extraction_priority = {
        "html_table_exact_anchor": 0,
        "nearby_header_anchor": 1,
        "implied_from_price_and_rel": 2,
        "direct": 3,
    }

    candidates = sorted(
        candidates,
        key=lambda x: (
            extraction_priority.get(str(x.get("extraction_method") or ""), 9),
            -(float(x.get("match_score") or -999)),
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
        "current_bound_by_table_anchor",
        "current_bound_by_nearby_header",
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
    structurally_reliable_nav_date = nav_date_source in {
        "manual_input",
        "nav_ref_extracted",
        "doc_period_anchor_extracted",
        "xbrl_fact_end_date",
    }

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
        row.setdefault("table_header_dates", None)
        row.setdefault("table_row_values", None)
        row.setdefault("table_bound_index", None)
        row.setdefault("table_index", None)
        row.setdefault("table_row_index", None)
        row.setdefault("xbrl_taxonomy", None)
        row.setdefault("xbrl_concept", None)
        row.setdefault("xbrl_label", None)
        row.setdefault("xbrl_unit", None)
        return row

    used = bool(row.get("valid_for_stats"))
    dq_status = "OK" if used else "INVALID"
    flags: List[str] = []

    nav_date_source = str(row.get("nav_date_source") or "")
    candidate_value_role = str(row.get("candidate_value_role") or "")
    extraction_method = str(row.get("extraction_method") or "")

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

    if (
        extraction_method == "direct"
        and candidate_value_role == "current_first_column"
        and bool(row.get("doc_period_anchor"))
        and bool(row.get("multi_value_row_flag"))
    ):
        used = False
        if dq_status == "OK":
            dq_status = "REVIEW_COLUMN_ORDER_AMBIGUOUS"
        flags.append("COLUMN_ORDER_AMBIGUOUS_FIRST_COLUMN_WITH_ANCHOR")

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
                "table_header_dates": None,
                "table_row_values": None,
                "table_bound_index": None,
                "table_index": None,
                "table_row_index": None,
                "xbrl_taxonomy": None,
                "xbrl_concept": None,
                "xbrl_label": None,
                "xbrl_unit": None,
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
                raise requests.HTTPError(f"retryable_http_status:{r.status_code}", response=r)
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


def _norm_phrase(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _xbrl_nav_label_match(concept: str, label: Optional[str] = None, description: Optional[str] = None) -> bool:
    hay = " | ".join([_norm_phrase(concept), _norm_phrase(label), _norm_phrase(description)])
    if _norm_phrase(concept) == "netassetvaluepershare":
        return True
    return any(_norm_phrase(k) in hay for k in XBRL_NAV_LABEL_KEYWORDS)


def _extract_xbrl_candidates_from_fact_payload(
    payload: Dict[str, Any],
    *,
    taxonomy: str,
    concept: str,
    source_url: str,
    extraction_method: str,
    match_score: float,
    role: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    label = payload.get("label") if isinstance(payload, dict) else None
    description = payload.get("description") if isinstance(payload, dict) else None
    units = (payload or {}).get("units", {}) if isinstance(payload, dict) else {}

    for unit_name, facts in units.items():
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            form = str(fact.get("form") or "").upper().strip()
            if form and form not in AUTO_NAV_ALLOWED_FORMS:
                continue
            end_ts = parse_date(fact.get("end"))
            filed_ts = parse_date(fact.get("filed"))
            val = to_float(fact.get("val"))
            if end_ts is None or val is None or not (0.5 <= val <= 100.0):
                continue
            out.append({
                "nav": round(float(val), 6),
                "nav_date": end_ts.strftime("%Y-%m-%d"),
                "filing_date": filed_ts.strftime("%Y-%m-%d") if filed_ts is not None else None,
                "filing_form": form or None,
                "source_url": source_url,
                "xbrl_taxonomy": taxonomy,
                "xbrl_concept": concept,
                "xbrl_label": label,
                "xbrl_description": description,
                "xbrl_unit": unit_name,
                "match_score": safe_num(match_score),
                "matched_pattern": f"{taxonomy}:{concept}",
                "matched_snippet": clean_snippet(f"XBRL fact {taxonomy}:{concept} end={end_ts.strftime('%Y-%m-%d')} val={safe_num(val)} unit={unit_name}", max_len=220),
                "extraction_method": extraction_method,
                "candidate_value_role": role,
                "nav_ref_date": end_ts.strftime("%Y-%m-%d"),
                "nav_ref_date_source": "xbrl_fact_end_date",
                "nav_ref_match_text": end_ts.strftime("%Y-%m-%d"),
                "price_obs_date": None,
                "price_obs_date_source": None,
                "price_obs_match_text": None,
                "percent_context_flag": False,
                "suspicious_terms_flag": False,
                "date_component_flag": False,
                "hard_skip_context_flag": False,
                "hard_skip_context_tags": [],
                "context_penalty_total": 0.0,
                "context_penalty_tags": [],
                "section_bonus_total": 1.0,
                "section_bonus_tags": ["xbrl_api"],
                "comparison_context_flag": False,
                "multi_value_row_flag": False,
                "date_binding_mode": "xbrl_fact_end_date",
                "local_role_ctx": clean_snippet(str(label or concept), max_len=140),
                "table_header_dates": None,
                "table_row_values": None,
                "table_bound_index": None,
                "table_index": None,
                "table_row_index": None,
            })
    return out


def fetch_xbrl_companyconcept_nav_candidates(
    session: requests.Session,
    cik10: str,
    timeout: int,
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    candidates: List[Dict[str, Any]] = []
    notes: List[str] = []
    for taxonomy, concept in XBRL_NAV_STANDARD_CONCEPTS:
        url = SEC_XBRL_COMPANYCONCEPT_URL.format(cik10=cik10, taxonomy=taxonomy, concept=concept)
        try:
            payload = sec_fetch_json(session, url, timeout=timeout, cache_dir=cache_dir, use_cache=use_cache)
        except Exception as e:
            notes.append(f"companyconcept:{taxonomy}:{concept}:{type(e).__name__}:{str(e)[:80]}")
            continue
        candidates.extend(_extract_xbrl_candidates_from_fact_payload(
            payload,
            taxonomy=taxonomy,
            concept=concept,
            source_url=url,
            extraction_method="xbrl_companyconcept",
            match_score=20.0,
            role="current_xbrl_standard_concept",
        ))
    return candidates, notes


def fetch_xbrl_companyfacts_nav_candidates(
    session: requests.Session,
    cik10: str,
    timeout: int,
    cache_dir: Optional[Path] = None,
    use_cache: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    url = SEC_XBRL_COMPANYFACTS_URL.format(cik10=cik10)
    try:
        raw = sec_fetch_json(session, url, timeout=timeout, cache_dir=cache_dir, use_cache=use_cache)
    except Exception as e:
        return [], [f"companyfacts:{type(e).__name__}:{str(e)[:100]}"]

    candidates: List[Dict[str, Any]] = []
    facts_root = (raw or {}).get("facts", {}) if isinstance(raw, dict) else {}
    for taxonomy, concept_map in facts_root.items():
        if taxonomy not in XBRL_STANDARD_TAXONOMIES or not isinstance(concept_map, dict):
            continue
        for concept, payload in concept_map.items():
            if not isinstance(payload, dict):
                continue
            if not _xbrl_nav_label_match(concept, payload.get("label"), payload.get("description")):
                continue
            candidates.extend(_extract_xbrl_candidates_from_fact_payload(
                payload,
                taxonomy=taxonomy,
                concept=concept,
                source_url=url,
                extraction_method="xbrl_companyfacts",
                match_score=17.0,
                role="current_xbrl_discovered_concept",
            ))
    return candidates, []


def _choose_best_xbrl_candidate(
    candidates: List[Dict[str, Any]],
    market_date: Optional[pd.Timestamp],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    mkt = normalize_ts_naive(market_date)
    usable = []
    for c in candidates:
        end_ts = parse_date(c.get("nav_date"))
        filed_ts = parse_date(c.get("filing_date"))
        if end_ts is None:
            continue
        if mkt is not None and end_ts > mkt:
            continue
        usable.append((end_ts, filed_ts or pd.Timestamp("1900-01-01"), c))
    if not usable:
        return None
    usable = sorted(usable, key=lambda x: (x[0].value, x[1].value, float(x[2].get("match_score") or 0.0)), reverse=True)
    return usable[0][2]


def build_nav_row_from_xbrl_candidate(
    *,
    ticker: str,
    cand: Dict[str, Any],
    latest_price_by_ticker: Dict[str, Dict[str, Any]],
    nav_fresh_max_days: int,
) -> Dict[str, Any]:
    nav_date = parse_date(cand.get("nav_date"))
    row = make_nav_overlay_row(
        ticker=ticker,
        nav=to_float(cand.get("nav")),
        nav_date=nav_date,
        source_url=cand.get("source_url"),
        note=(
            f"auto_xbrl:{cand.get('extraction_method')}:{cand.get('xbrl_taxonomy')}:{cand.get('xbrl_concept')}:"
            f"filed={cand.get('filing_date')}:end={cand.get('nav_date')}"
        ),
        source_kind="auto_sec",
        latest_price_by_ticker=latest_price_by_ticker,
        nav_fresh_max_days=nav_fresh_max_days,
        nav_date_source="xbrl_fact_end_date",
        extra_fields={
            "filing_form": cand.get("filing_form"),
            "filing_date": cand.get("filing_date"),
            "match_score": cand.get("match_score"),
            "matched_pattern": cand.get("matched_pattern"),
            "matched_snippet": cand.get("matched_snippet"),
            "candidate_rank": 1,
            "candidate_count": 1,
            "percent_context_flag": False,
            "suspicious_terms_flag": False,
            "date_component_flag": False,
            "extraction_method": cand.get("extraction_method"),
            "derived_from_price": None,
            "derived_from_rel": None,
            "derived_from_pct": None,
            "price_obs_date": None,
            "price_obs_date_source": None,
            "price_obs_match_text": None,
            "nav_ref_date_extracted": cand.get("nav_ref_date"),
            "nav_ref_date_source": cand.get("nav_ref_date_source"),
            "nav_ref_match_text": cand.get("nav_ref_match_text"),
            "hard_skip_context_flag": False,
            "hard_skip_context_tags": [],
            "context_penalty_total": 0.0,
            "context_penalty_tags": [],
            "section_bonus_total": cand.get("section_bonus_total", 1.0),
            "section_bonus_tags": cand.get("section_bonus_tags") or ["xbrl_api"],
            "doc_name": f"{cand.get('xbrl_taxonomy')}:{cand.get('xbrl_concept')}",
            "doc_score": 250,
            "doc_source": "xbrl_api",
            "doc_period_anchor": cand.get("nav_date"),
            "doc_period_anchor_source": "xbrl_fact_end_date",
            "doc_period_anchor_match_text": cand.get("nav_date"),
            "candidate_value_role": cand.get("candidate_value_role"),
            "comparison_context_flag": False,
            "multi_value_row_flag": False,
            "date_binding_mode": "xbrl_fact_end_date",
            "local_role_ctx": cand.get("local_role_ctx"),
            "table_header_dates": None,
            "table_row_values": None,
            "table_bound_index": None,
            "table_index": None,
            "table_row_index": None,
            "xbrl_taxonomy": cand.get("xbrl_taxonomy"),
            "xbrl_concept": cand.get("xbrl_concept"),
            "xbrl_label": cand.get("xbrl_label"),
            "xbrl_unit": cand.get("xbrl_unit"),
        },
    )
    return finalize_nav_row_dq(row)


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
    return docs[:max(1, max_docs_per_filing)], notes


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
            "source": "sec_xbrl_first_v1_docscan_fallback_v0.1-split",
            "attempted_count": 0,
            "found_count": 0,
            "rows": [],
            "notes": [f"ERR:ticker_map:{type(e).__name__}:{str(e)[:160]}"],
        }

    for ticker in tickers:
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

        xbrl_candidates: List[Dict[str, Any]] = []
        concept_candidates, concept_notes = fetch_xbrl_companyconcept_nav_candidates(
            session=session,
            cik10=cik10,
            timeout=timeout,
            cache_dir=(sec_cache_dir / "xbrl_companyconcept") if sec_cache_dir else None,
            use_cache=sec_use_cache,
        )
        for n in concept_notes:
            notes.append(f"{ticker}:XBRL_NOTE:{n}")
        xbrl_candidates.extend(concept_candidates)

        if not xbrl_candidates:
            facts_candidates, facts_notes = fetch_xbrl_companyfacts_nav_candidates(
                session=session,
                cik10=cik10,
                timeout=timeout,
                cache_dir=(sec_cache_dir / "xbrl_companyfacts") if sec_cache_dir else None,
                use_cache=sec_use_cache,
            )
            for n in facts_notes:
                notes.append(f"{ticker}:XBRL_NOTE:{n}")
            xbrl_candidates.extend(facts_candidates)

        best_xbrl = _choose_best_xbrl_candidate(xbrl_candidates, market_date=market_date)
        if best_xbrl is not None:
            xbrl_row = build_nav_row_from_xbrl_candidate(
                ticker=ticker,
                cand=best_xbrl,
                latest_price_by_ticker=latest_price_by_ticker,
                nav_fresh_max_days=nav_fresh_max_days,
            )
            if xbrl_row.get("used_in_stats"):
                chosen_row = xbrl_row
            else:
                fallback_review_row = xbrl_row

        if chosen_row is not None:
            out_rows.append(chosen_row)
            found += 1
            notes.append(
                f"{ticker}:OK_XBRL:{chosen_row.get('filing_form')}:{chosen_row.get('filing_date')}:"
                f"doc={chosen_row.get('doc_name')}:score={chosen_row.get('match_score')}:"
                f"dq={chosen_row.get('dq_status')}:method={chosen_row.get('extraction_method')}"
            )
            continue

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
                    raw_html=raw_text,
                    doc_period_anchor=doc_period_anchor,
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
                            "table_header_dates": cand.get("table_header_dates"),
                            "table_row_values": cand.get("table_row_values"),
                            "table_bound_index": cand.get("table_bound_index"),
                            "table_index": cand.get("table_index"),
                            "table_row_index": cand.get("table_row_index"),
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
        "source": "sec_xbrl_first_v1_docscan_fallback_v0.1-split",
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


def make_history_row(latest: Dict[str, Any]) -> Dict[str, Any]:
    nav = latest["nav_overlay"]
    return {
        "generated_at_utc": latest["meta"]["generated_at_utc"],
        "coverage_total": nav.get("coverage_total"),
        "coverage_fresh": nav.get("coverage_fresh"),
        "median_discount_pct_fresh": nav.get("median_discount_pct_fresh"),
        "median_discount_pct_all": nav.get("median_discount_pct_all"),
        "confidence": nav.get("confidence"),
        "notes": "append_only_nav_summary_row",
    }


def merge_history(existing: Any, new_row: Dict[str, Any], max_rows: int) -> List[Dict[str, Any]]:
    rows = [r for r in existing if isinstance(r, dict)] if isinstance(existing, list) else []
    rows.append(new_row)
    rows = sorted(rows, key=lambda x: x.get("generated_at_utc", ""))
    return rows[-max_rows:] if max_rows > 0 else rows


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    inputs_dir = out_dir / "inputs"
    ensure_dir(inputs_dir)

    sec_cache_dir = Path(args.sec_cache_dir) if args.sec_cache_dir else (out_dir / "sec_cache")
    if args.sec_use_cache:
        ensure_dir(sec_cache_dir)

    manual_nav_path = Path(args.manual_nav) if args.manual_nav else inputs_dir / "manual_nav.json"
    create_manual_nav_template(manual_nav_path)

    tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
    if not tickers:
        tickers = DEFAULT_BDC_TICKERS.copy()

    end_date = normalize_ts_naive(UTC_NOW())
    start_date = end_date - pd.Timedelta(days=args.lookback_calendar_days)

    price_rows: List[Dict[str, Any]] = []
    latest_price_by_ticker_nav: Dict[str, Dict[str, Any]] = {}
    source_notes: List[str] = []

    for t in tickers:
        df, source_url, err = fetch_yfinance_daily(t, start_date, end_date, timeout=args.timeout)
        stats = compute_latest_market_snapshot(df)
        note_parts: List[str] = [err or "OK"]
        row = {
            "ticker": t,
            **stats,
            "source_url": source_url,
            "note": "|".join(str(x) for x in note_parts if x not in [None, ""]),
        }
        price_rows.append(row)
        latest_price_by_ticker_nav[t] = {
            "ticker": t,
            "close": stats.get("close"),
            "data_date": stats.get("data_date"),
            "source_url": source_url,
            "note": err or "OK",
            "adj_close": stats.get("adj_close"),
        }
        if err:
            source_notes.append(f"{t}:{err}")

    if args.nav_auto_source == "sec":
        auto_nav_result = fetch_auto_nav_rows_from_sec(
            tickers=tickers,
            latest_price_by_ticker=latest_price_by_ticker_nav,
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
        latest_price_by_ticker=latest_price_by_ticker_nav,
        nav_fresh_max_days=args.nav_fresh_max_days,
        auto_nav_result=auto_nav_result,
    )

    latest = {
        "meta": {
            "generated_at_utc": UTC_NOW().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "out_dir": str(out_dir),
            "source_policy": "yfinance_raw_close_for_nav_overlay + manual_nav_overlay + auto_sec_nav_xbrl_first_v0.1-split",
            "tickers": tickers,
            "params": {
                "lookback_calendar_days": args.lookback_calendar_days,
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
        "price_snapshot": sorted(price_rows, key=lambda r: r.get("ticker") or ""),
        "nav_overlay": nav_info,
        "notes": [
            "Standalone NAV-only sidecar.",
            "Manual valid rows override auto SEC rows for the same ticker.",
            "Auto NAV from SEC uses XBRL first and document scan fallback.",
            "Filing-date-only NAV dating remains REVIEW_ONLY and is excluded from stats.",
            f"data_fetch_notes: {'; '.join(source_notes) if source_notes else 'all price fetches OK'}",
        ],
    }

    latest_json_path = Path(args.output_json) if args.output_json else (out_dir / "nav_latest.json")
    history_json_path = out_dir / "nav_history.json"

    write_json(latest_json_path, latest)
    existing_history = read_json(history_json_path, default=[])
    history = merge_history(existing_history, make_history_row(latest), max_rows=args.history_max_rows)
    write_json(history_json_path, history)

    print(json.dumps({
        "status": "OK",
        "latest_json": str(latest_json_path),
        "history_json": str(history_json_path),
        "manual_nav": str(manual_nav_path),
        "coverage_total": nav_info.get("coverage_total"),
        "coverage_fresh": nav_info.get("coverage_fresh"),
        "confidence": nav_info.get("confidence"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
