#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nav_sec_pipeline.py

Purpose
-------
Standalone, audit-friendly NAV extraction pipeline for BDC / investment-company
style filings, designed around a conservative review workflow:

manual NAV override
  -> SEC auto fetch
    -> XBRL first
    -> filing document fallback
      -> candidate scoring
      -> date binding
      -> DQ / review / exclude
      -> optional premium/discount overlay using raw market close

This script is intentionally conservative. It prefers returning fewer usable NAVs
rather than accepting weak candidates.

What this script does
---------------------
1) Creates a manual NAV template if none exists.
2) Optionally fetches latest raw close from yfinance (best-effort, optional).
3) Resolves ticker -> CIK from SEC.
4) Tries XBRL companyconcept first.
5) If needed, tries XBRL companyfacts discovery.
6) If still needed, scans filing documents via HTML table / direct regex /
   implied NAV fallback.
7) Binds dates conservatively.
8) Applies deterministic DQ rules.
9) Merges manual override over auto rows.
10) Writes JSON + markdown outputs.

Notes
-----
- This is a clean reimplementation of the pipeline architecture, not a byte-for-
  byte extraction of your legacy script.
- Some heuristics are necessarily simplified because the full legacy helper
  stack was not included here.
- SEC access requires a real User-Agent containing contact information.

Dependencies
------------
Required:
  requests
Optional:
  yfinance   (for raw close overlay)
  beautifulsoup4 (for better HTML table parsing)

Example
-------
python nav_sec_pipeline.py \
  --tickers ARCC,BXSL,OBDC,FSK,PSEC \
  --out-dir nav_only_cache \
  --manual-nav manual_nav.json \
  --sec-user-agent "Your Name your_email@example.com" \
  --nav-auto-max-filings 6 \
  --sec-max-docs-per-filing 5 \
  --sec-use-cache
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import math
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None

try:
    import yfinance as yf  # type: ignore
except Exception:  # pragma: no cover
    yf = None


SCRIPT_NAME = "nav_sec_pipeline.py"
SCRIPT_VERSION = "v1.0.1"

DEFAULT_TICKERS = ["ARCC", "BXSL", "OBDC", "FSK", "PSEC"]
DEFAULT_OUT_DIR = "nav_only_cache"
DEFAULT_TIMEOUT = 20
DEFAULT_MAX_FILINGS = 6
DEFAULT_MAX_DOCS_PER_FILING = 5
DEFAULT_NAV_FRESH_MAX_DAYS = 150
DEFAULT_MIN_MATCH_SCORE = 45.0

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_XBRL_COMPANYCONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{concept}.json"
)
SEC_XBRL_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
SEC_ARCHIVES_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/index.json"
SEC_ARCHIVES_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{name}"

ACCEPTED_FORMS = {
    "10-Q",
    "10-K",
    "8-K",
    "10-Q/A",
    "10-K/A",
    "8-K/A",
}

XBRL_NAV_STANDARD_CONCEPTS = [
    ("us-gaap", "NetAssetValuePerShare"),
]

NAV_KEYWORDS = [
    "net asset value per share",
    "nav per share",
    "net assets attributable to common stockholders per share",
    "net assets applicable to common stockholders per share",
    "net asset value attributable to common stockholders per share",
]

NAV_ROW_LABEL_RE = re.compile(
    r"\b(net\s+asset\s+value\s+per\s+share|nav\s+per\s+share|net\s+assets?.{0,40}?per\s+share)\b",
    re.I,
)

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b. %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
]

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t\.?|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RE = re.compile(
    rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|{MONTH_RE}\s+\d{{1,2}},\s*\d{{4}})\b",
    re.I,
)

NUMBER_RE = r"(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
DIRECT_NAV_REGEX_SPECS: List[Tuple[str, float]] = [
    (
        rf"\bnet\s+asset\s+value\s+per\s+share\b[^\n\r$%0-9]{{0,100}}\$?\s*{NUMBER_RE}",
        95.0,
    ),
    (
        rf"\bnav\s+per\s+share\b[^\n\r$%0-9]{{0,80}}\$?\s*{NUMBER_RE}",
        90.0,
    ),
    (
        rf"\bnet\s+assets?.{{0,60}}?per\s+share\b[^\n\r$%0-9]{{0,100}}\$?\s*{NUMBER_RE}",
        82.0,
    ),
]

IMPLIED_NAV_REGEX_SPECS: List[Tuple[re.Pattern[str], float]] = [
    (
        re.compile(
            rf"closing\s+price[^\n\r$]{{0,60}}\$\s*(?P<price>\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)"
            rf"[^\n\r]{{0,140}}?(?P<side>discount|premium)\s+of\s+(?P<pct>\d{{1,3}}(?:\.\d+)?)%\s+to\s+(?:its\s+)?(?:net\s+asset\s+value|NAV)",
            re.I,
        ),
        72.0,
    ),
    (
        re.compile(
            rf"(?P<side>discount|premium)\s+of\s+(?P<pct>\d{{1,3}}(?:\.\d+)?)%\s+to\s+(?:its\s+)?(?:net\s+asset\s+value|NAV)"
            rf"[^\n\r]{{0,140}}?closing\s+price[^\n\r$]{{0,60}}\$\s*(?P<price>\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)",
            re.I,
        ),
        70.0,
    ),
]

SUSPICIOUS_SNIPPET_TERMS = {
    "estimated",
    "estimate",
    "illustrative",
    "example",
    "pro forma",
    "hypothetical",
    "sensitivity",
    "range",
    "guidance",
}

HARD_SKIP_TERMS = {
    "total return",
    "yield on nav",
    "nav return",
    "percentage of nav",
    "debt to nav",
    "nav growth",
    "book value multiple",
    "portfolio yield",
    "cash distribution",
    "dividend yield",
}

NEGATIVE_CONTEXT_TERMS = {
    "previous quarter",
    "prior quarter",
    "year ago",
    "comparison",
    "compared with",
    "versus",
    "vs.",
}

XBRL_METHODS = {"xbrl_companyconcept", "xbrl_companyfacts_discovery"}


@dataclass
class Candidate:
    ticker: str
    source: str
    method: str
    nav: Optional[float]
    filing_date: Optional[str] = None
    nav_date: Optional[str] = None
    date_source: Optional[str] = None
    match_score: float = 0.0
    snippet: str = ""
    accession_no: Optional[str] = None
    form: Optional[str] = None
    doc_name: Optional[str] = None
    doc_url: Optional[str] = None
    xbrl_taxonomy: Optional[str] = None
    xbrl_concept: Optional[str] = None
    price_obs_date: Optional[str] = None
    price_obs_close: Optional[float] = None
    implied_side: Optional[str] = None
    implied_pct: Optional[float] = None
    review_flags: Optional[List[str]] = None
    notes: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["review_flags"] = list(self.review_flags or [])
        d["notes"] = list(self.notes or [])
        return d


def today_utc_date() -> dt.date:
    return dt.datetime.utcnow().date()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def parse_date_any(value: Any) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in DATE_PATTERNS:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except Exception:
            pass
    m = DATE_RE.search(s)
    if m:
        token = m.group(0)
        for fmt in DATE_PATTERNS:
            try:
                return dt.datetime.strptime(token, fmt).date()
            except Exception:
                pass
    return None


def date_to_str(value: Optional[dt.date]) -> Optional[str]:
    return value.isoformat() if value else None


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clip(text: str, n: int = 220) -> str:
    text = clean_text(text)
    return text if len(text) <= n else text[: n - 3] + "..."


def sha1_str(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Accept-Encoding": "gzip, deflate", "Accept": "*/*"})
    return s


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(
        self,
        session: requests.Session,
        sec_user_agent: str,
        cache_dir: Path,
        use_cache: bool,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session
        self.sec_user_agent = sec_user_agent
        self.cache_dir = cache_dir
        self.use_cache = use_cache
        self.timeout = timeout
        ensure_dir(cache_dir)

    def _cache_path(self, url: str, suffix: str) -> Path:
        return self.cache_dir / f"{sha1_str(url)}{suffix}"

    def get_text(self, url: str, is_sec: bool = False) -> str:
        cache_path = self._cache_path(url, ".txt")
        if self.use_cache and cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="ignore")

        headers = {}
        if is_sec:
            headers["User-Agent"] = self.sec_user_agent
        delays = [0, 2, 4, 8]
        last_exc: Optional[Exception] = None
        for i, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
                if resp.status_code == 200:
                    text = resp.text
                    if self.use_cache:
                        cache_path.write_text(text, encoding="utf-8")
                    return text
                if resp.status_code in {403, 404}:
                    raise FetchError(f"HTTP {resp.status_code} for {url}")
                if resp.status_code in {429, 500, 502, 503, 504}:
                    last_exc = FetchError(f"HTTP {resp.status_code} for {url}, attempt={i}")
                    continue
                raise FetchError(f"HTTP {resp.status_code} for {url}")
            except Exception as exc:
                last_exc = exc
        raise FetchError(str(last_exc) if last_exc else f"fetch failed for {url}")

    def get_json(self, url: str, is_sec: bool = False) -> Any:
        cache_path = self._cache_path(url, ".json")
        if self.use_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        text = self.get_text(url, is_sec=is_sec)
        data = json.loads(text)
        if self.use_cache:
            cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data


def create_manual_nav_template(path: Path, tickers: Sequence[str]) -> None:
    if path.exists():
        return
    ensure_dir(path.parent)
    template = []
    for t in tickers:
        template.append(
            {
                "ticker": t,
                "nav": 0.0,
                "nav_date": "YYYY-MM-DD",
                "source": "manual",
                "note": "fill nav and nav_date to override auto SEC row",
            }
        )
    write_json(path, template)


def load_manual_nav_rows(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    data = read_json(path)
    rows: Dict[str, Dict[str, Any]] = {}
    if not isinstance(data, list):
        return rows
    for item in data:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        nav = to_float(item.get("nav"))
        nav_date = parse_date_any(item.get("nav_date"))
        if not ticker or nav is None or nav <= 0 or not nav_date:
            continue
        rows[ticker] = {
            "ticker": ticker,
            "source": "manual",
            "method": "manual_override",
            "nav": round(nav, 6),
            "nav_date": nav_date.isoformat(),
            "date_source": "manual",
            "match_score": 100.0,
            "snippet": str(item.get("note") or "manual override"),
            "review_flags": [],
            "notes": [str(item.get("note") or "manual override")],
        }
    return rows


def normalize_cik(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = re.sub(r"\D", "", str(value))
    return s or None


def get_sec_ticker_to_cik_map(fetcher: Fetcher) -> Dict[str, str]:
    data = fetcher.get_json(SEC_TICKER_MAP_URL, is_sec=True)
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        values: Iterable[Any] = data.values()
    else:
        values = data
    for item in values:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        cik = normalize_cik(item.get("cik_str"))
        if ticker and cik:
            out[ticker] = cik
    return out


def choose_best_xbrl_candidate(candidates: Sequence[Candidate], market_date: dt.date) -> Optional[Candidate]:
    if not candidates:
        return None

    def key(c: Candidate) -> Tuple[int, int, float, float]:
        nav_date = parse_date_any(c.nav_date)
        filing_date = parse_date_any(c.filing_date)
        nav_ok = 1 if nav_date and nav_date <= market_date else 0
        filing_ord = filing_date.toordinal() if filing_date else 0
        nav_ord = nav_date.toordinal() if nav_date else 0
        return (nav_ok, nav_ord, filing_ord, c.match_score)

    ranked = sorted(candidates, key=key, reverse=True)
    return ranked[0] if ranked else None


def extract_best_date_from_xbrl_fact(fact: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    end_date = parse_date_any(fact.get("end"))
    filed = parse_date_any(fact.get("filed"))
    if end_date:
        return end_date.isoformat(), "xbrl_end"
    if filed:
        return filed.isoformat(), "xbrl_filed_review_only"
    return None, None


def fetch_xbrl_companyconcept_nav_candidates(
    fetcher: Fetcher,
    cik: str,
    ticker: str,
    market_date: dt.date,
) -> List[Candidate]:
    candidates: List[Candidate] = []
    cik10 = cik.zfill(10)
    for taxonomy, concept in XBRL_NAV_STANDARD_CONCEPTS:
        url = SEC_XBRL_COMPANYCONCEPT_URL.format(cik10=cik10, taxonomy=taxonomy, concept=concept)
        try:
            data = fetcher.get_json(url, is_sec=True)
        except Exception:
            continue
        units = data.get("units", {}) if isinstance(data, dict) else {}
        for unit_name, facts in units.items():
            if not isinstance(facts, list):
                continue
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                val = to_float(fact.get("val"))
                if val is None or val <= 0:
                    continue
                nav_date, date_source = extract_best_date_from_xbrl_fact(fact)
                filing_date = date_to_str(parse_date_any(fact.get("filed")))
                c = Candidate(
                    ticker=ticker,
                    source="sec_xbrl",
                    method="xbrl_companyconcept",
                    nav=round(val, 6),
                    filing_date=filing_date,
                    nav_date=nav_date,
                    date_source=date_source,
                    match_score=100.0 if concept == "NetAssetValuePerShare" else 88.0,
                    snippet=f"{taxonomy}:{concept} unit={unit_name}",
                    xbrl_taxonomy=taxonomy,
                    xbrl_concept=concept,
                    notes=[f"unit={unit_name}"],
                    review_flags=[],
                )
                nd = parse_date_any(c.nav_date)
                if nd and nd <= market_date:
                    candidates.append(c)
                elif nd is None:
                    candidates.append(c)
    return candidates


def navish_score(text: str) -> float:
    t = clean_text(text).lower()
    score = 0.0
    for kw in NAV_KEYWORDS:
        if kw in t:
            score += 30.0
    if "net asset" in t and "per share" in t:
        score += 18.0
    if "nav" in t and "share" in t:
        score += 12.0
    return score


def fetch_xbrl_companyfacts_nav_candidates(
    fetcher: Fetcher,
    cik: str,
    ticker: str,
    market_date: dt.date,
) -> List[Candidate]:
    candidates: List[Candidate] = []
    cik10 = cik.zfill(10)
    url = SEC_XBRL_COMPANYFACTS_URL.format(cik10=cik10)
    try:
        data = fetcher.get_json(url, is_sec=True)
    except Exception:
        return candidates

    facts_root = data.get("facts", {}) if isinstance(data, dict) else {}
    if not isinstance(facts_root, dict):
        return candidates

    for taxonomy, concepts in facts_root.items():
        if not isinstance(concepts, dict):
            continue
        for concept_name, meta in concepts.items():
            if not isinstance(meta, dict):
                continue
            label = str(meta.get("label") or "")
            desc = str(meta.get("description") or "")
            text = f"{concept_name} {label} {desc}"
            score = navish_score(text)
            if score < 30:
                continue
            units = meta.get("units", {})
            if not isinstance(units, dict):
                continue
            for unit_name, facts in units.items():
                if not isinstance(facts, list):
                    continue
                for fact in facts:
                    if not isinstance(fact, dict):
                        continue
                    val = to_float(fact.get("val"))
                    if val is None or val <= 0:
                        continue
                    nav_date, date_source = extract_best_date_from_xbrl_fact(fact)
                    filing_date = date_to_str(parse_date_any(fact.get("filed")))
                    c = Candidate(
                        ticker=ticker,
                        source="sec_xbrl",
                        method="xbrl_companyfacts_discovery",
                        nav=round(val, 6),
                        filing_date=filing_date,
                        nav_date=nav_date,
                        date_source=date_source,
                        match_score=min(95.0, score),
                        snippet=f"{taxonomy}:{concept_name} | {clip(label or desc, 120)} | unit={unit_name}",
                        xbrl_taxonomy=taxonomy,
                        xbrl_concept=concept_name,
                        notes=[f"label={clip(label, 120)}", f"unit={unit_name}"],
                        review_flags=[],
                    )
                    nd = parse_date_any(c.nav_date)
                    if nd and nd <= market_date:
                        candidates.append(c)
                    elif nd is None:
                        candidates.append(c)
    return candidates


def get_recent_filing_candidates(
    fetcher: Fetcher,
    cik: str,
    max_filings: int,
) -> List[Dict[str, Any]]:
    cik10 = cik.zfill(10)
    url = SEC_SUBMISSIONS_URL.format(cik10=cik10)
    try:
        data = fetcher.get_json(url, is_sec=True)
    except Exception:
        return []

    recent = ((data or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []
    primary_descs = recent.get("primaryDocDescription") or []
    report_dates = recent.get("reportDate") or []

    n = min(len(forms), len(dates), len(accessions), len(primary_docs))
    out: List[Dict[str, Any]] = []
    for i in range(n):
        form = str(forms[i]).strip()
        if form not in ACCEPTED_FORMS:
            continue
        fd = parse_date_any(dates[i])
        if not fd:
            continue
        out.append(
            {
                "form": form,
                "filing_date": fd.isoformat(),
                "accession_no": str(accessions[i]),
                "primary_document": str(primary_docs[i]),
                "primary_doc_description": str(primary_descs[i]) if i < len(primary_descs) else "",
                "report_date": str(report_dates[i]) if i < len(report_dates) else "",
            }
        )
    out.sort(key=lambda x: x["filing_date"], reverse=True)
    return out[:max_filings]


def score_doc_name(name: str, primary_document: str) -> float:
    n = name.lower()
    score = 0.0
    if n == primary_document.lower():
        score += 100.0
    if n.endswith((".htm", ".html", ".txt")):
        score += 25.0
    if "99" in n or "ex99" in n or "ex-99" in n:
        score += 20.0
    for kw in ["earn", "result", "release", "supplement", "presentation", "press", "quarter"]:
        if kw in n:
            score += 8.0
    if any(kw in n for kw in ["graph", "xsd", "xml", "zip", "jpg", "png", "gif"]):
        score -= 20.0
    return score


def get_sec_document_candidates_for_filing(
    fetcher: Fetcher,
    cik: str,
    filing: Dict[str, Any],
    max_docs_per_filing: int,
) -> List[Dict[str, Any]]:
    accession_no = str(filing["accession_no"])
    nodash = accession_no.replace("-", "")
    url = SEC_ARCHIVES_INDEX_URL.format(cik=str(int(cik)), accession_nodash=nodash)
    try:
        data = fetcher.get_json(url, is_sec=True)
    except Exception:
        return []

    items = (((data or {}).get("directory") or {}).get("item")) or []
    docs: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        sc = score_doc_name(name, str(filing.get("primary_document") or ""))
        if sc <= 0:
            continue
        docs.append(
            {
                "name": name,
                "score": sc,
                "url": SEC_ARCHIVES_DOC_URL.format(
                    cik=str(int(cik)), accession_nodash=nodash, name=name
                ),
            }
        )
    docs.sort(key=lambda x: x["score"], reverse=True)
    return docs[:max_docs_per_filing]


def extract_dates_near(text: str) -> List[dt.date]:
    out: List[dt.date] = []
    for m in DATE_RE.finditer(text):
        d = parse_date_any(m.group(0))
        if d:
            out.append(d)
    return out


def choose_effective_nav_date(
    explicit_nav_date: Optional[dt.date],
    doc_period_anchor: Optional[dt.date],
    filing_date: Optional[dt.date],
) -> Tuple[Optional[dt.date], Optional[str]]:
    if explicit_nav_date:
        return explicit_nav_date, "explicit_nav_date"
    if doc_period_anchor:
        return doc_period_anchor, "doc_period_anchor"
    if filing_date:
        return filing_date, "filing_date_inferred_review_only"
    return None, None


def first_plausible_numeric(cells: Sequence[str]) -> Optional[float]:
    for cell in cells:
        m = re.search(r"\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", cell)
        if not m:
            continue
        val = to_float(m.group(1))
        if val is not None and 0 < val < 1000:
            return val
    return None


def extract_doc_period_anchor_from_table(header_cells: Sequence[str], filing_date: Optional[dt.date]) -> Optional[dt.date]:
    best: Optional[dt.date] = None
    for cell in header_cells:
        d = parse_date_any(cell)
        if not d:
            continue
        if filing_date and d > filing_date:
            continue
        if best is None or d > best:
            best = d
    return best


def extract_nav_candidates_from_html_tables(
    html_text: str,
    ticker: str,
    filing: Dict[str, Any],
    doc: Dict[str, Any],
) -> List[Candidate]:
    candidates: List[Candidate] = []
    if BeautifulSoup is None:
        return candidates
    soup = BeautifulSoup(html_text, "html.parser")
    filing_date = parse_date_any(filing.get("filing_date"))
    for table in soup.find_all("table"):
        rows: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            continue
        header = rows[0]
        anchor = extract_doc_period_anchor_from_table(header, filing_date)
        for row in rows[1:]:
            if not row:
                continue
            label = clean_text(row[0]).lower()
            if not NAV_ROW_LABEL_RE.search(label):
                continue
            nav = first_plausible_numeric(row[1:])
            if nav is None:
                continue
            eff_date, date_source = choose_effective_nav_date(None, anchor, filing_date)
            cand = Candidate(
                ticker=ticker,
                source="sec_filing_doc",
                method="html_table_anchor",
                nav=round(nav, 6),
                filing_date=date_to_str(filing_date),
                nav_date=date_to_str(eff_date),
                date_source=date_source,
                match_score=92.0 if anchor else 70.0,
                snippet=clip(" | ".join(row), 220),
                accession_no=str(filing.get("accession_no") or ""),
                form=str(filing.get("form") or ""),
                doc_name=str(doc.get("name") or ""),
                doc_url=str(doc.get("url") or ""),
                review_flags=[] if anchor else ["REVIEW_COLUMN_ORDER_AMBIGUOUS"],
                notes=["html_table"],
            )
            candidates.append(cand)
    return candidates


def detect_comparison_value(snippet: str) -> bool:
    s = clean_text(snippet).lower()
    return any(term in s for term in NEGATIVE_CONTEXT_TERMS)


def detect_hard_skip(snippet: str) -> bool:
    s = clean_text(snippet).lower()
    return any(term in s for term in HARD_SKIP_TERMS)


def detect_suspicious_terms(snippet: str) -> bool:
    s = clean_text(snippet).lower()
    return any(term in s for term in SUSPICIOUS_SNIPPET_TERMS)


def extract_direct_nav_candidates_from_text(
    text: str,
    ticker: str,
    filing: Dict[str, Any],
    doc: Dict[str, Any],
) -> List[Candidate]:
    out: List[Candidate] = []
    filing_date = parse_date_any(filing.get("filing_date"))
    clean = clean_text(text)
    for pattern, base_score in DIRECT_NAV_REGEX_SPECS:
        for m in re.finditer(pattern, clean, flags=re.I):
            num = to_float(m.group("num"))
            if num is None or num <= 0 or num > 1000:
                continue
            start = max(0, m.start() - 220)
            end = min(len(clean), m.end() + 220)
            snippet = clean[start:end]
            nearby_dates = extract_dates_near(snippet)
            explicit_date = max(nearby_dates) if nearby_dates else None
            eff_date, date_source = choose_effective_nav_date(explicit_date, None, filing_date)
            review_flags: List[str] = []
            if "%" in snippet:
                review_flags.append("REVIEW_PERCENT_CONTEXT")
            if detect_comparison_value(snippet):
                review_flags.append("REVIEW_COMPARISON_VALUE")
            if detect_suspicious_terms(snippet):
                review_flags.append("REVIEW_SNIPPET_TERMS")
            cand = Candidate(
                ticker=ticker,
                source="sec_filing_doc",
                method="direct_regex",
                nav=round(num, 6),
                filing_date=date_to_str(filing_date),
                nav_date=date_to_str(eff_date),
                date_source=date_source,
                match_score=base_score - (8.0 if "%" in snippet else 0.0),
                snippet=clip(snippet, 220),
                accession_no=str(filing.get("accession_no") or ""),
                form=str(filing.get("form") or ""),
                doc_name=str(doc.get("name") or ""),
                doc_url=str(doc.get("url") or ""),
                review_flags=review_flags,
                notes=["direct_regex"],
            )
            out.append(cand)
    return out


def extract_implied_nav_candidates_from_text(
    text: str,
    ticker: str,
    filing: Dict[str, Any],
    doc: Dict[str, Any],
) -> List[Candidate]:
    out: List[Candidate] = []
    filing_date = parse_date_any(filing.get("filing_date"))
    clean = clean_text(text)
    for rx, base_score in IMPLIED_NAV_REGEX_SPECS:
        for m in rx.finditer(clean):
            side = str(m.group("side") or "").strip().lower()
            pct = to_float(m.group("pct"))
            price = to_float(m.group("price"))
            if pct is None or price is None or pct < 0 or pct >= 99 or price <= 0:
                continue
            if side == "discount":
                denom = 1.0 - pct / 100.0
            else:
                denom = 1.0 + pct / 100.0
            if denom <= 0:
                continue
            nav = price / denom
            start = max(0, m.start() - 220)
            end = min(len(clean), m.end() + 220)
            snippet = clean[start:end]
            nearby_dates = extract_dates_near(snippet)
            explicit_date = max(nearby_dates) if nearby_dates else None
            eff_date, date_source = choose_effective_nav_date(explicit_date, None, filing_date)
            review_flags: List[str] = ["REVIEW_IMPLIED_NAV"]
            if detect_comparison_value(snippet):
                review_flags.append("REVIEW_COMPARISON_VALUE")
            if detect_suspicious_terms(snippet):
                review_flags.append("REVIEW_SNIPPET_TERMS")
            cand = Candidate(
                ticker=ticker,
                source="sec_filing_doc",
                method="implied_nav",
                nav=round(nav, 6),
                filing_date=date_to_str(filing_date),
                nav_date=date_to_str(eff_date),
                date_source=date_source,
                match_score=base_score,
                snippet=clip(snippet, 220),
                accession_no=str(filing.get("accession_no") or ""),
                form=str(filing.get("form") or ""),
                doc_name=str(doc.get("name") or ""),
                doc_url=str(doc.get("url") or ""),
                price_obs_close=round(price, 6),
                implied_side=side,
                implied_pct=round(pct, 6),
                review_flags=review_flags,
                notes=["implied_nav"],
            )
            out.append(cand)
    return out


def extract_nav_candidates_from_document(
    fetcher: Fetcher,
    ticker: str,
    filing: Dict[str, Any],
    doc: Dict[str, Any],
) -> List[Candidate]:
    try:
        text = fetcher.get_text(str(doc["url"]), is_sec=True)
    except Exception:
        return []

    candidates: List[Candidate] = []
    lower_name = str(doc.get("name") or "").lower()
    if lower_name.endswith((".htm", ".html")):
        candidates.extend(extract_nav_candidates_from_html_tables(text, ticker, filing, doc))
    plain = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    plain = re.sub(r"<style.*?</style>", " ", plain, flags=re.I | re.S)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = clean_text(plain)
    candidates.extend(extract_direct_nav_candidates_from_text(plain, ticker, filing, doc))
    candidates.extend(extract_implied_nav_candidates_from_text(plain, ticker, filing, doc))
    return candidates


def fetch_latest_raw_close(ticker: str) -> Tuple[Optional[str], Optional[float], str]:
    if yf is None:
        return None, None, "yfinance_not_installed"
    try:
        hist = yf.Ticker(ticker).history(period="7d", auto_adjust=False)
        if hist is None or hist.empty:
            return None, None, "yfinance_empty"
        last_idx = hist.index[-1]
        close = to_float(hist["Close"].iloc[-1])
        if close is None:
            return None, None, "close_na"
        if hasattr(last_idx, "date"):
            d = last_idx.date().isoformat()
        else:
            d = str(last_idx)[:10]
        return d, round(close, 6), "ok"
    except Exception as exc:
        return None, None, f"yfinance_error:{exc.__class__.__name__}"


def candidate_priority(c: Dict[str, Any]) -> Tuple[float, int, int, float]:
    method_rank = {
        "xbrl_companyconcept": 5,
        "xbrl_companyfacts_discovery": 4,
        "html_table_anchor": 3,
        "direct_regex": 2,
        "implied_nav": 1,
        "manual_override": 6,
    }.get(str(c.get("method") or ""), 0)
    nav_date = parse_date_any(c.get("nav_date"))
    filing_date = parse_date_any(c.get("filing_date"))
    nav_ord = nav_date.toordinal() if nav_date else 0
    filing_ord = filing_date.toordinal() if filing_date else 0
    return (float(c.get("match_score") or 0.0), method_rank, nav_ord, filing_ord)


def is_high_confidence_xbrl_row(row: Dict[str, Any]) -> bool:
    method = str(row.get("method") or "")
    source = str(row.get("source") or "")
    score = float(row.get("match_score") or 0.0)
    nav_date = parse_date_any(row.get("nav_date"))
    return (
        source == "sec_xbrl"
        and method in XBRL_METHODS
        and score >= 90.0
        and nav_date is not None
    )


def finalize_nav_row_dq(
    row: Dict[str, Any],
    market_date: dt.date,
    nav_fresh_max_days: int,
    min_match_score: float,
) -> Dict[str, Any]:
    nav = to_float(row.get("nav"))
    nav_date = parse_date_any(row.get("nav_date"))
    filing_date = parse_date_any(row.get("filing_date"))
    market_close = to_float(row.get("market_close"))
    snippet = str(row.get("snippet") or "")
    review_flags = list(row.get("review_flags") or [])
    notes = list(row.get("notes") or [])

    dq_status = "OK"
    used_in_stats = True

    if nav is None or nav <= 0:
        dq_status = "EXCLUDED_INVALID_NAV"
        used_in_stats = False
    elif nav_date is None:
        dq_status = "EXCLUDED_NAV_DATE_INVALID"
        used_in_stats = False
    elif nav_date > market_date:
        dq_status = "EXCLUDED_NAV_DATE_INVALID"
        used_in_stats = False
    elif float(row.get("match_score") or 0.0) < min_match_score:
        dq_status = "EXCLUDED_LOW_MATCH_SCORE"
        used_in_stats = False
    elif detect_hard_skip(snippet):
        dq_status = "EXCLUDED_CONTEXT_HARD_SKIP"
        used_in_stats = False
    elif str(row.get("date_source") or "") == "filing_date_inferred_review_only":
        dq_status = "REVIEW_NAV_DATE_INFERRED"
        used_in_stats = False
    elif "REVIEW_COMPARISON_VALUE" in review_flags:
        dq_status = "REVIEW_COMPARISON_VALUE"
        used_in_stats = False
    elif "REVIEW_COLUMN_ORDER_AMBIGUOUS" in review_flags:
        dq_status = "REVIEW_COLUMN_ORDER_AMBIGUOUS"
        used_in_stats = False
    elif "REVIEW_PERCENT_CONTEXT" in review_flags:
        dq_status = "REVIEW_PERCENT_CONTEXT"
        used_in_stats = False
    elif "REVIEW_SNIPPET_TERMS" in review_flags:
        dq_status = "REVIEW_SNIPPET_TERMS"
        used_in_stats = False
    elif "REVIEW_IMPLIED_NAV" in review_flags:
        dq_status = "REVIEW_IMPLIED_NAV"
        used_in_stats = False

    premium_discount_pct: Optional[float] = None
    if nav and market_close and nav > 0:
        premium_discount_pct = (market_close / nav - 1.0) * 100.0
        row["premium_discount_pct"] = round(premium_discount_pct, 6)

        if dq_status == "OK" and premium_discount_pct > 50:
            dq_status = "EXCLUDED_PREMIUM_TOO_HIGH"
            used_in_stats = False
        elif dq_status == "OK" and premium_discount_pct > 30:
            dq_status = "REVIEW_PREMIUM_HIGH"
            used_in_stats = False
        elif dq_status == "OK" and premium_discount_pct < -50:
            if is_high_confidence_xbrl_row(row):
                dq_status = "REVIEW_DISCOUNT_TOO_DEEP"
                used_in_stats = False
                notes.append("deep_discount_preserved_for_review_high_confidence_xbrl")
            else:
                dq_status = "EXCLUDED_DISCOUNT_TOO_DEEP"
                used_in_stats = False
        elif dq_status == "OK" and premium_discount_pct < -30:
            dq_status = "REVIEW_DISCOUNT_DEEP"
            used_in_stats = False
    else:
        row["premium_discount_pct"] = None

    nav_age_days: Optional[int] = None
    if nav_date:
        nav_age_days = (market_date - nav_date).days
    row["nav_age_days"] = nav_age_days
    row["dq_status"] = dq_status
    row["used_in_stats"] = used_in_stats
    row["fresh_for_rule"] = bool(
        used_in_stats
        and nav_age_days is not None
        and 0 <= nav_age_days <= nav_fresh_max_days
        and row.get("premium_discount_pct") is not None
    )

    if filing_date and nav_date and filing_date < nav_date:
        notes.append("filing_date_before_nav_date_check")
    row["review_flags"] = review_flags
    row["notes"] = notes
    return row


def build_nav_overlay(
    manual_rows: Dict[str, Dict[str, Any]],
    auto_rows: Dict[str, Dict[str, Any]],
    market_map: Dict[str, Dict[str, Any]],
    market_date: dt.date,
    nav_fresh_max_days: int,
    min_match_score: float,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    all_tickers = sorted(set(manual_rows) | set(auto_rows) | set(market_map))
    for ticker in all_tickers:
        base = dict(auto_rows.get(ticker, {}))
        if ticker in manual_rows:
            base = dict(manual_rows[ticker])
            base["auto_replaced"] = ticker in auto_rows
        if not base:
            base = {
                "ticker": ticker,
                "source": "none",
                "method": "none",
                "nav": None,
                "match_score": 0.0,
                "review_flags": [],
                "notes": ["no_nav_candidate"],
            }
        base["ticker"] = ticker
        m = market_map.get(ticker, {})
        base["report_date"] = date_to_str(market_date)
        base["market_date"] = date_to_str(market_date)
        base["market_price_date"] = m.get("market_price_date")
        base["market_close"] = m.get("market_close")
        base["market_price_status"] = m.get("market_price_status")
        out.append(finalize_nav_row_dq(base, market_date, nav_fresh_max_days, min_match_score))
    out.sort(key=lambda x: x["ticker"])
    return out


def summarize_rows(rows: Sequence[Dict[str, Any]], nav_fresh_max_days: int) -> Dict[str, Any]:
    usable = [r for r in rows if r.get("used_in_stats")]
    fresh = [r for r in rows if r.get("fresh_for_rule")]
    rows_with_pd = [r for r in rows if r.get("premium_discount_pct") is not None]
    pd_usable = [float(r["premium_discount_pct"]) for r in usable if r.get("premium_discount_pct") is not None]
    pd_all_rows = [float(r["premium_discount_pct"]) for r in rows_with_pd]
    pd_fresh = [float(r["premium_discount_pct"]) for r in fresh if r.get("premium_discount_pct") is not None]

    def median(xs: Sequence[float]) -> Optional[float]:
        if not xs:
            return None
        ys = sorted(xs)
        n = len(ys)
        mid = n // 2
        if n % 2 == 1:
            return ys[mid]
        return (ys[mid - 1] + ys[mid]) / 2.0

    coverage_total = len([r for r in rows if to_float(r.get("nav")) is not None])
    coverage_usable = len(usable)
    coverage_fresh = len(fresh)
    coverage_all_with_pd = len(rows_with_pd)
    confidence = "LOW"
    if coverage_fresh >= 4:
        confidence = "HIGH"
    elif coverage_fresh >= 2:
        confidence = "PARTIAL"

    return {
        "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "script": SCRIPT_NAME,
        "script_version": SCRIPT_VERSION,
        "coverage_total": coverage_total,
        "coverage_usable": coverage_usable,
        "coverage_fresh": coverage_fresh,
        "coverage_all_with_pd": coverage_all_with_pd,
        "nav_fresh_max_days": nav_fresh_max_days,
        "median_discount_pct_usable": None if median(pd_usable) is None else round(median(pd_usable), 6),
        "median_discount_pct_all_rows": None if median(pd_all_rows) is None else round(median(pd_all_rows), 6),
        "median_discount_pct_fresh": None if median(pd_fresh) is None else round(median(pd_fresh), 6),
        "confidence": confidence,
    }


def select_best_auto_candidate(candidates: Sequence[Candidate], market_date: dt.date) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    ranked = sorted(
        (c.to_dict() for c in candidates),
        key=lambda d: (
            candidate_priority(d),
            1 if parse_date_any(d.get("nav_date")) and parse_date_any(d.get("nav_date")) <= market_date else 0,
        ),
        reverse=True,
    )
    return ranked[0] if ranked else None


def fetch_auto_nav_rows_from_sec(
    fetcher: Fetcher,
    tickers: Sequence[str],
    market_date: dt.date,
    nav_auto_max_filings: int,
    sec_max_docs_per_filing: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    meta: Dict[str, Any] = {
        "ticker_map_ok": False,
        "ticker_errors": {},
    }
    rows: Dict[str, Dict[str, Any]] = {}
    try:
        ticker_map = get_sec_ticker_to_cik_map(fetcher)
        meta["ticker_map_ok"] = True
    except Exception as exc:
        meta["ticker_map_ok"] = False
        meta["ticker_map_error"] = str(exc)
        return rows, meta

    for ticker in tickers:
        t = ticker.upper()
        cik = ticker_map.get(t)
        if not cik:
            meta["ticker_errors"][t] = "ticker_not_found_in_sec_map"
            continue

        per_ticker_candidates: List[Candidate] = []

        ccands = fetch_xbrl_companyconcept_nav_candidates(fetcher, cik, t, market_date)
        per_ticker_candidates.extend(ccands)
        best_xbrl = choose_best_xbrl_candidate(per_ticker_candidates, market_date)

        if best_xbrl is None:
            fcands = fetch_xbrl_companyfacts_nav_candidates(fetcher, cik, t, market_date)
            per_ticker_candidates.extend(fcands)
            best_xbrl = choose_best_xbrl_candidate(per_ticker_candidates, market_date)

        if best_xbrl is None:
            filings = get_recent_filing_candidates(fetcher, cik, nav_auto_max_filings)
            for filing in filings:
                docs = get_sec_document_candidates_for_filing(fetcher, cik, filing, sec_max_docs_per_filing)
                for doc in docs:
                    extracted = extract_nav_candidates_from_document(fetcher, t, filing, doc)
                    per_ticker_candidates.extend(extracted)

        best = best_xbrl.to_dict() if best_xbrl else select_best_auto_candidate(per_ticker_candidates, market_date)
        if best:
            best["cik"] = cik
            rows[t] = best
        else:
            meta["ticker_errors"][t] = "no_usable_candidate_found"

    return rows, meta


def render_markdown_report(summary: Dict[str, Any], rows: Sequence[Dict[str, Any]], auto_meta: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# NAV SEC Pipeline Report")
    lines.append("")
    lines.append("## Summary")
    for k in [
        "generated_at_utc",
        "script",
        "script_version",
        "coverage_total",
        "coverage_usable",
        "coverage_fresh",
        "coverage_all_with_pd",
        "nav_fresh_max_days",
        "median_discount_pct_usable",
        "median_discount_pct_all_rows",
        "median_discount_pct_fresh",
        "confidence",
    ]:
        lines.append(f"- {k}: `{summary.get(k)}`")
    lines.append("")
    lines.append("## Interpretation Notes")
    lines.append("- `median_discount_pct_usable`: median using only rows with `used_in_stats=true`")
    lines.append("- `median_discount_pct_all_rows`: median using all rows that have a calculable premium/discount, even if DQ marked them as review/excluded")
    lines.append("- `median_discount_pct_fresh`: median using rows with `fresh_for_rule=true`")
    lines.append("")
    lines.append("## SEC Fetch Meta")
    lines.append(f"- ticker_map_ok: `{auto_meta.get('ticker_map_ok')}`")
    if auto_meta.get("ticker_map_error"):
        lines.append(f"- ticker_map_error: `{clip(str(auto_meta.get('ticker_map_error')), 180)}`")
    err_map = auto_meta.get("ticker_errors") or {}
    if err_map:
        lines.append("- ticker_errors:")
        for k, v in sorted(err_map.items()):
            lines.append(f"  - {k}: `{v}`")
    lines.append("")
    lines.append("## Rows")
    lines.append("")
    lines.append("| ticker | source | method | nav | nav_date | report_date | market_price_date | market_close | premium_discount_pct | dq_status | used_in_stats | fresh_for_rule | review_flags | snippet |")
    lines.append("|---|---|---|---:|---|---|---|---:|---:|---|---|---|---|---|")
    for r in rows:
        snippet = str(r.get("snippet") or "").replace("|", "\\|")
        review_flags = ",".join(str(x) for x in (r.get("review_flags") or []))
        lines.append(
            "| {ticker} | {source} | {method} | {nav} | {nav_date} | {report_date} | {market_price_date} | {market_close} | {premium_discount_pct} | {dq_status} | {used_in_stats} | {fresh_for_rule} | {review_flags} | {snippet} |".format(
                ticker=r.get("ticker"),
                source=r.get("source"),
                method=r.get("method"),
                nav=r.get("nav"),
                nav_date=r.get("nav_date"),
                report_date=r.get("report_date"),
                market_price_date=r.get("market_price_date"),
                market_close=r.get("market_close"),
                premium_discount_pct=r.get("premium_discount_pct"),
                dq_status=r.get("dq_status"),
                used_in_stats=r.get("used_in_stats"),
                fresh_for_rule=r.get("fresh_for_rule"),
                review_flags=clip(review_flags, 80).replace("|", "\\|"),
                snippet=clip(snippet, 120),
            )
        )
    lines.append("")
    lines.append("## Detailed Rows (JSON preview)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(rows, ensure_ascii=False, indent=2)[:7000])
    lines.append("```")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            safe_row = {}
            for k in fieldnames:
                v = row.get(k)
                if isinstance(v, (list, dict)):
                    safe_row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    safe_row[k] = v
            writer.writerow(safe_row)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Standalone SEC NAV pipeline")
    p.add_argument("--tickers", default=",".join(DEFAULT_TICKERS), help="Comma-separated tickers")
    p.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory")
    p.add_argument("--manual-nav", default="manual_nav.json", help="Path to manual nav JSON")
    p.add_argument(
        "--nav-auto-source",
        default="sec",
        choices=["sec", "none"],
        help="Auto NAV source",
    )
    p.add_argument("--sec-user-agent", required=True, help="SEC User-Agent with contact info")
    p.add_argument("--nav-auto-max-filings", type=int, default=DEFAULT_MAX_FILINGS)
    p.add_argument("--sec-max-docs-per-filing", type=int, default=DEFAULT_MAX_DOCS_PER_FILING)
    p.add_argument("--sec-use-cache", action="store_true", help="Enable local SEC cache")
    p.add_argument("--cache-dir", default=".sec_cache", help="Cache directory")
    p.add_argument("--market-date", default="", help="Override market date YYYY-MM-DD")
    p.add_argument("--nav-fresh-max-days", type=int, default=DEFAULT_NAV_FRESH_MAX_DAYS)
    p.add_argument("--min-match-score", type=float, default=DEFAULT_MIN_MATCH_SCORE)
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    tickers = [x.strip().upper() for x in str(args.tickers).split(",") if x.strip()]
    if not tickers:
        print("ERROR: no tickers specified", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    manual_path = Path(args.manual_nav)
    create_manual_nav_template(manual_path, tickers)

    if args.market_date:
        market_date = parse_date_any(args.market_date)
        if not market_date:
            print(f"ERROR: invalid --market-date: {args.market_date}", file=sys.stderr)
            return 2
    else:
        market_date = today_utc_date()

    session = make_session()
    fetcher = Fetcher(
        session=session,
        sec_user_agent=args.sec_user_agent,
        cache_dir=Path(args.cache_dir),
        use_cache=bool(args.sec_use_cache),
    )

    manual_rows = load_manual_nav_rows(manual_path)
    market_map: Dict[str, Dict[str, Any]] = {}
    for t in tickers:
        price_date, close, status = fetch_latest_raw_close(t)
        market_map[t] = {
            "market_price_date": price_date,
            "market_close": close,
            "market_price_status": status,
        }

    auto_rows: Dict[str, Dict[str, Any]] = {}
    auto_meta: Dict[str, Any] = {"ticker_map_ok": None, "ticker_errors": {}}
    if args.nav_auto_source == "sec":
        auto_rows, auto_meta = fetch_auto_nav_rows_from_sec(
            fetcher=fetcher,
            tickers=tickers,
            market_date=market_date,
            nav_auto_max_filings=int(args.nav_auto_max_filings),
            sec_max_docs_per_filing=int(args.sec_max_docs_per_filing),
        )

    rows = build_nav_overlay(
        manual_rows=manual_rows,
        auto_rows=auto_rows,
        market_map=market_map,
        market_date=market_date,
        nav_fresh_max_days=int(args.nav_fresh_max_days),
        min_match_score=float(args.min_match_score),
    )
    summary = summarize_rows(rows, nav_fresh_max_days=int(args.nav_fresh_max_days))

    write_json(out_dir / "nav_rows.json", rows)
    write_json(out_dir / "nav_summary.json", summary)
    write_json(out_dir / "nav_auto_meta.json", auto_meta)
    write_csv(out_dir / "nav_rows.csv", rows)
    (out_dir / "nav_report.md").write_text(
        render_markdown_report(summary, rows, auto_meta), encoding="utf-8"
    )

    print(json.dumps({"summary": summary, "out_dir": str(out_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
