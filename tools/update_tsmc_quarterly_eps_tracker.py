#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v3.0)

Design goals
------------
1) Seed-first:
   - Bootstrap seeds are the primary source of truth for quarterly EPS values.
   - Script no longer relies on DuckDuckGo or front-end site discovery.

2) Verification, not discovery:
   - Try to verify seed records via SEC data.sec.gov submissions JSON + 6-K documents.
   - If seed already contains manual verification candidates, try those first.
   - Then probe direct seed URLs (article_url / page_url / pdf_url) as low-priority fallback.

3) Auditability:
   - Keep per-quarter discovery_debug/attempt logs.
   - Explicitly classify block pages (Cloudflare/security/captcha).
   - Never overwrite seed EPS from scraped values; only mark verified / failed.

Dependencies
------------
Required:
- requests

Optional:
- pypdf   (recommended, for PDF verification)
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

try:
    from pypdf import PdfReader  # type: ignore
    HAVE_PYPDF = True
except Exception:
    PdfReader = None  # type: ignore
    HAVE_PYPDF = False


SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v3.0"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.5
DEFAULT_SEC_CIK = "0001046179"  # TSMC
DEFAULT_SEC_USER_AGENT = "tsmc-eps-tracker/3.0 (personal research)"
DEFAULT_SEC_LOOKBACK_DAYS = 45

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

SOURCE_PRIORITY = {
    "tsmc_seed_record": 20,
    "tsmc_existing_record": 10,
}

QUARTER_NUM_TO_CN = {1: "第一", 2: "第二", 3: "第三", 4: "第四"}
QUARTER_CN_TO_NUM = {v: k for k, v in QUARTER_NUM_TO_CN.items()}
QUARTER_NUM_TO_EN_WORD = {1: "first", 2: "second", 3: "third", 4: "fourth"}
QUARTER_EN_WORD_TO_NUM = {v: k for k, v in QUARTER_NUM_TO_EN_WORD.items()}

MONTH_NAME_TO_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# --------------------------------------------------------------------
# Seed-first data
# - You can manually add verification_candidates for future quarters.
# - verification_candidates should be direct SEC/official document URLs.
# --------------------------------------------------------------------
BOOTSTRAP_SEEDS: List[Dict[str, Any]] = [
    {
        "quarter": "2024Q4",
        "eps": 14.45,
        "source": "tsmc_seed_record",
        "as_of_date": "2025-01-16",
        "article_title": "台積公司2024年第四季每股盈餘新台幣14.45元",
        "article_url": "https://pr.tsmc.com/chinese/news/3201",
        "quarter_end_date": "December 31, 2024",
        "quarter_word": "fourth",
        "page_url": "https://pr.tsmc.com/chinese/news/3201",
    },
    {
        "quarter": "2025Q1",
        "eps": 13.94,
        "source": "tsmc_seed_record",
        "as_of_date": "2025-04-17",
        "article_title": "台積公司2025年第一季每股盈餘新台幣13.94元",
        "article_url": "https://pr.tsmc.com/chinese/news/3222",
        "quarter_end_date": "March 31, 2025",
        "quarter_word": "first",
        "page_url": "https://pr.tsmc.com/chinese/news/3222",
    },
    {
        "quarter": "2025Q2",
        "eps": 15.36,
        "source": "tsmc_seed_record",
        "as_of_date": "2025-07-17",
        "article_title": "台積公司2025年第二季每股盈餘新台幣15.36元",
        "article_url": "https://pr.tsmc.com/chinese/news/3249",
        "page_url": "https://pr.tsmc.com/chinese/news/3249",
        "quarter_end_date": "June 30, 2025",
        "quarter_word": "second",
        "verification_candidates": [
            "https://www.sec.gov/Archives/edgar/data/1046179/000104617925000093/tsm-boardx20250812x6k.htm"
        ],
    },
    {
        "quarter": "2025Q3",
        "eps": 17.44,
        "source": "tsmc_seed_record",
        "as_of_date": "2025-10-16",
        "article_title": "台積公司2025年第三季每股盈餘新台幣17.44元",
        "article_url": "https://pr.tsmc.com/chinese/news/3264",
        "page_url": "https://pr.tsmc.com/chinese/news/3264",
        "quarter_end_date": "September 30, 2025",
        "quarter_word": "third",
    },
    {
        "quarter": "2025Q4",
        "eps": 19.50,
        "source": "tsmc_seed_record",
        "as_of_date": "2026-01-15",
        "article_title": "台積公司2025年第四季每股盈餘新台幣19.50元",
        "article_url": "https://pr.tsmc.com/chinese/news/3281",
        "page_url": "https://pr.tsmc.com/chinese/news/3281",
        "quarter_end_date": "December 31, 2025",
        "quarter_word": "fourth",
        "verification_candidates": [
            "https://www.sec.gov/Archives/edgar/data/1046179/000104617926000008/tsm-20260115x6k.htm"
        ],
    },
]

DATE_RE_LIST = [
    re.compile(r"發佈日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})"),
    re.compile(r"發言日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})"),
    re.compile(r"公告日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})"),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{4}/\d{2}/\d{2})\b"),
]

EN_DATE_RE_LIST = [
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s*(\d{4})\b",
        re.I,
    ),
]

OFFICIAL_TITLE_RE = re.compile(
    r"台積公司(\d{4})年(第一|第二|第三|第四)季每股盈餘新台幣([0-9]+(?:\.[0-9]+)?)元"
)
CN_TITLE_RE = re.compile(r"台積公司(\d{4})年(第一|第二|第三|第四)季每股盈餘")
QUARTER_CN_YEAR_RE = re.compile(r"(\d{4})年(第一|第二|第三|第四)季")
QUARTER_Q_RE_1 = re.compile(r"(\d{4})\s*[Qq]([1-4])")
QUARTER_Q_RE_2 = re.compile(r"[Qq]([1-4])\s*(?:FY|fy)?\s*(\d{4})")
QUARTER_EN_YEAR_RE_1 = re.compile(r"\b(first|second|third|fourth)\s+quarter\s+(?:of\s+)?(\d{4})\b", re.I)
QUARTER_EN_YEAR_RE_2 = re.compile(r"\b(\d{4})\s+(first|second|third|fourth)\s+quarter\b", re.I)
QUARTER_EN_YEAR_RE_3 = re.compile(r"\b([1-4])Q\s*'?(\d{2,4})\b", re.I)

COMPANY_HINT_RE = re.compile(r"(台積電|台積公司|TSMC|Taiwan Semiconductor)", re.I)

EPS_PATTERNS = [
    re.compile(r"每股盈餘(?:為)?新台幣\s*([0-9]+(?:\.[0-9]+)?)\s*元"),
    re.compile(r"每股(?:盈餘|純益|稅後純益|獲利|賺(?:了|到)?)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*元"),
    re.compile(r"稀釋每股(?:盈餘|純益)?\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*元"),
    re.compile(r"\bEPS\b\D{0,12}([0-9]+(?:\.[0-9]+)?)\s*元?", re.I),
    re.compile(r"EPS達\D{0,8}([0-9]+(?:\.[0-9]+)?)\s*元", re.I),
    re.compile(r"Q[1-4]\s*EPS\D{0,12}([0-9]+(?:\.[0-9]+)?)\s*元", re.I),
    re.compile(r"diluted earnings per share(?: of)?\s*NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
    re.compile(r"diluted EPS(?: of)?\s*NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
    re.compile(r"earnings per share(?: of)?\s*NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
]

PDF_EPS_PATTERNS = [
    re.compile(r"diluted earnings per share(?: of)?\s*NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
    re.compile(r"EPS(?: of)?\s*NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
]

TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
A_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)

BLOCK_PATTERNS = [
    ("cloudflare_challenge", re.compile(r"Just a moment\.\.\.|cf-browser-verification|Attention Required!|Cloudflare", re.I)),
    ("security_block", re.compile(r"THE PAGE CANNOT BE ACCESSED|FOR SECURITY REASONS", re.I)),
    ("captcha_block", re.compile(r"captcha|verify you are human|human verification", re.I)),
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_local_date() -> date:
    return datetime.now().date()


def quarter_sort_key(q: str) -> Tuple[int, int]:
    m = re.match(r"^(\d{4})Q([1-4])$", q)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def strip_tags(x: str) -> str:
    return re.sub(r"<[^>]+>", " ", x or "", flags=re.S)


def normalize_ws(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "")).strip()


def clean_html_text(x: str) -> str:
    return normalize_ws(unescape(strip_tags(x)))


def canonical_host(host: str) -> str:
    h = (host or "").lower().strip()
    if h.startswith("www."):
        h = h[4:]
    if h.startswith("m."):
        h = h[2:]
    return h


def detect_source_priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 0)


def quarter_word_from_num(qnum: int) -> str:
    return QUARTER_NUM_TO_EN_WORD.get(qnum, "NA")


def quarter_end_date_obj(year: int, quarter_num: int) -> date:
    if quarter_num == 1:
        return date(year, 3, 31)
    if quarter_num == 2:
        return date(year, 6, 30)
    if quarter_num == 3:
        return date(year, 9, 30)
    return date(year, 12, 31)


def quarter_end_date_from_label(quarter: str) -> str:
    m = re.match(r"^(\d{4})Q([1-4])$", quarter)
    if not m:
        return "NA"
    year = int(m.group(1))
    q = int(m.group(2))
    end = quarter_end_date_obj(year, q)
    return end.strftime("%B %d, %Y")


def assess_publication_state(year: int, quarter_num: int, today: date) -> str:
    q_end = quarter_end_date_obj(year, quarter_num)
    if today < q_end:
        return "NOT_ENDED_YET"
    if today < q_end + timedelta(days=21):
        return "LIKELY_NOT_PUBLISHED_YET"
    return "SHOULD_BE_PUBLISHED_OR_DISCOVERABLE"


def parse_iso_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def enrich_record(
    item: Dict[str, Any],
    *,
    data_origin: str,
    reference_source_type: str,
    reference_url_verified_this_run: bool,
) -> Dict[str, Any]:
    out = copy.deepcopy(item)
    out["fetched_at_utc"] = now_utc_iso()
    out["data_origin"] = data_origin
    out["source_priority"] = detect_source_priority(str(out.get("source", "")))
    out["reference_source_type"] = reference_source_type
    out["reference_url_verified_this_run"] = bool(reference_url_verified_this_run)
    return out


def build_session(sec_user_agent: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    s.headers["X-SEC-User-Agent"] = sec_user_agent
    return s


def sec_headers(sec_user_agent: str) -> Dict[str, str]:
    return {
        "User-Agent": sec_user_agent,
        "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Referer": "https://www.sec.gov/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def http_get_text(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    *,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    last_err: Optional[Exception] = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            if r.encoding is None:
                r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} | last_err={last_err}")


def http_get_bytes(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    *,
    headers: Optional[Dict[str, str]] = None,
) -> bytes:
    last_err: Optional[Exception] = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET bytes failed after {retries} attempts: {url} | last_err={last_err}")


def detect_block_reason(text: str) -> Optional[str]:
    for name, rx in BLOCK_PATTERNS:
        if rx.search(text or ""):
            return name
    return None


def find_title_text(html: str, fallback_url: str) -> str:
    m = H1_RE.search(html or "")
    if m:
        return clean_html_text(m.group(1))
    m = TITLE_TAG_RE.search(html or "")
    if m:
        return clean_html_text(m.group(1))
    return fallback_url


def infer_quarter_from_text(
    title: str,
    text: str,
    expected_year: Optional[int],
    expected_quarter_num: Optional[int],
) -> Optional[str]:
    combined = f"{title} {text}"

    m = OFFICIAL_TITLE_RE.search(combined)
    if m:
        year = int(m.group(1))
        qnum = QUARTER_CN_TO_NUM.get(m.group(2))
        if qnum:
            return f"{year}Q{qnum}"

    m = QUARTER_CN_YEAR_RE.search(combined)
    if m:
        year = int(m.group(1))
        qnum = QUARTER_CN_TO_NUM.get(m.group(2))
        if qnum:
            return f"{year}Q{qnum}"

    m = QUARTER_Q_RE_1.search(combined)
    if m:
        return f"{int(m.group(1))}Q{int(m.group(2))}"

    m = QUARTER_Q_RE_2.search(combined)
    if m:
        return f"{int(m.group(2))}Q{int(m.group(1))}"

    m = QUARTER_EN_YEAR_RE_1.search(combined)
    if m:
        qnum = QUARTER_EN_WORD_TO_NUM.get(m.group(1).lower())
        year = int(m.group(2))
        if qnum:
            return f"{year}Q{qnum}"

    m = QUARTER_EN_YEAR_RE_2.search(combined)
    if m:
        year = int(m.group(1))
        qnum = QUARTER_EN_WORD_TO_NUM.get(m.group(2).lower())
        if qnum:
            return f"{year}Q{qnum}"

    m = QUARTER_EN_YEAR_RE_3.search(combined)
    if m:
        qnum = int(m.group(1))
        yy = m.group(2)
        year = int(yy) if len(yy) == 4 else int("20" + yy)
        return f"{year}Q{qnum}"

    if expected_year is not None and expected_quarter_num is not None:
        expected_cn = f"{expected_year}年{QUARTER_NUM_TO_CN[expected_quarter_num]}季"
        q_token = f"Q{expected_quarter_num}"
        quarter_en = QUARTER_NUM_TO_EN_WORD[expected_quarter_num]
        if COMPANY_HINT_RE.search(combined):
            if expected_cn in combined:
                return f"{expected_year}Q{expected_quarter_num}"
            if q_token in combined or q_token.lower() in combined.lower():
                if str(expected_year) in combined or str(expected_year)[2:] in combined:
                    return f"{expected_year}Q{expected_quarter_num}"
            if quarter_en in combined.lower() and str(expected_year) in combined:
                return f"{expected_year}Q{expected_quarter_num}"

    return None


def infer_eps_from_text(title: str, text: str) -> Optional[float]:
    combined = f"{title} {text}"
    m = OFFICIAL_TITLE_RE.search(combined)
    if m:
        return float(m.group(3))
    for rx in EPS_PATTERNS:
        m = rx.search(combined)
        if m:
            return float(m.group(1))
    return None


def infer_eps_from_pdf_text(text: str) -> Optional[float]:
    for rx in PDF_EPS_PATTERNS:
        m = rx.search(text)
        if m:
            return float(m.group(1))
    return None


def infer_date_from_text(text: str) -> str:
    for rx in DATE_RE_LIST:
        m = rx.search(text or "")
        if m:
            return m.group(1).replace("/", "-")
    for rx in EN_DATE_RE_LIST:
        m = rx.search(text or "")
        if m:
            month = MONTH_NAME_TO_NUM.get(m.group(1).lower())
            day = int(m.group(2))
            year = int(m.group(3))
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"
    return "NA"


def parse_html_record(
    html: str,
    url: str,
    *,
    expected_year: Optional[int],
    expected_quarter_num: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], str]:
    block_reason = detect_block_reason(html)
    if block_reason:
        return None, f"blocked:{block_reason}"

    text = clean_html_text(html)
    title = find_title_text(html, url)

    quarter = infer_quarter_from_text(
        title=title,
        text=text,
        expected_year=expected_year,
        expected_quarter_num=expected_quarter_num,
    )
    if not quarter:
        return None, "quarter_not_detected"

    eps_val = infer_eps_from_text(title=title, text=text)
    if eps_val is None:
        return None, "eps_not_detected"

    qnum = int(quarter[-1])
    return {
        "quarter": quarter,
        "eps": eps_val,
        "as_of_date": infer_date_from_text(text),
        "article_title": title,
        "article_url": url,
        "quarter_end_date": quarter_end_date_from_label(quarter),
        "quarter_word": quarter_word_from_num(qnum),
    }, "ok"


def parse_pdf_record(
    pdf_bytes: bytes,
    pdf_url: str,
    *,
    expected_year: Optional[int],
    expected_quarter_num: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], str]:
    if not HAVE_PYPDF:
        return None, "pypdf_not_installed"

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:
        return None, f"pdf_read_failed:{e}"

    clean_text = normalize_ws(text)
    quarter = infer_quarter_from_text(
        title=pdf_url,
        text=clean_text,
        expected_year=expected_year,
        expected_quarter_num=expected_quarter_num,
    )
    if not quarter:
        return None, "quarter_not_detected_in_pdf"

    eps_val = infer_eps_from_pdf_text(clean_text)
    if eps_val is None:
        eps_val = infer_eps_from_text(title=pdf_url, text=clean_text)
    if eps_val is None:
        return None, "eps_not_detected_in_pdf"

    qnum = int(quarter[-1])
    return {
        "quarter": quarter,
        "eps": eps_val,
        "as_of_date": infer_date_from_text(clean_text),
        "article_title": f"TSMC {quarter} PDF",
        "article_url": pdf_url,
        "quarter_end_date": quarter_end_date_from_label(quarter),
        "quarter_word": quarter_word_from_num(qnum),
    }, "ok"


def extract_links(html: str, base_url: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for href, inner in A_RE.findall(html or ""):
        full = urljoin(base_url, unescape(href).strip())
        if not full.startswith("http"):
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append((full, clean_html_text(inner)))
    return out


def score_sec_link(url: str, title: str) -> int:
    hay = f"{url} {title}".lower()
    score = 0
    for token, pts in [
        ("99.1", 50),
        ("99-1", 50),
        ("99_1", 50),
        ("ex99", 40),
        ("earnings", 35),
        ("release", 35),
        ("press", 25),
        ("presentation", 15),
        (".pdf", 10),
        (".htm", 5),
        (".html", 5),
        ("financial", 5),
    ]:
        if token in hay:
            score += pts
    return score


def choose_better_record(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    old_verified = bool(old.get("reference_url_verified_this_run", False))
    new_verified = bool(new.get("reference_url_verified_this_run", False))
    if new_verified and not old_verified:
        return new
    if old_verified and not new_verified:
        return old

    old_vstatus = str(old.get("verification", {}).get("status", ""))
    new_vstatus = str(new.get("verification", {}).get("status", ""))
    if new_vstatus.startswith("VERIFIED") and not old_vstatus.startswith("VERIFIED"):
        return new
    if old_vstatus.startswith("VERIFIED") and not new_vstatus.startswith("VERIFIED"):
        return old

    old_pri = int(old.get("source_priority", detect_source_priority(str(old.get("source", "")))))
    new_pri = int(new.get("source_priority", detect_source_priority(str(new.get("source", "")))))
    if new_pri > old_pri:
        return new
    if new_pri < old_pri:
        return old

    new_origin = str(new.get("data_origin", ""))
    old_origin = str(old.get("data_origin", ""))
    if new_origin == "bootstrap_seed" and old_origin != "bootstrap_seed":
        return new
    if old_origin == "bootstrap_seed" and new_origin != "bootstrap_seed":
        return old

    return new


def load_existing_tracker(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"meta": {}, "quarters": []}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw.setdefault("meta", {})
            raw.setdefault("quarters", [])
            if not isinstance(raw["quarters"], list):
                raw["quarters"] = []
            return raw
    except Exception:
        pass

    return {"meta": {}, "quarters": []}


def merge_records(existing: List[Dict[str, Any]], fetched: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for item in existing:
        q = str(item.get("quarter", "")).strip()
        if not q:
            continue
        item.setdefault("source_priority", detect_source_priority(str(item.get("source", ""))))
        item.setdefault("data_origin", "unknown")
        item.setdefault("reference_source_type", "unknown")
        item.setdefault("reference_url_verified_this_run", False)
        merged[q] = item

    for item in fetched:
        q = str(item.get("quarter", "")).strip()
        if not q:
            continue
        if q in merged:
            merged[q] = choose_better_record(merged[q], item)
        else:
            merged[q] = item

    out = list(merged.values())
    out.sort(key=lambda x: quarter_sort_key(str(x.get("quarter", ""))))
    return out


def sec_submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik}.json"


def fetch_sec_recent_6k_candidates(
    session: requests.Session,
    *,
    cik: str,
    sec_user_agent: str,
    as_of_date: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    lookback_days: int,
) -> Tuple[List[Dict[str, Any]], str]:
    url = sec_submissions_url(cik)
    raw = http_get_text(session, url, timeout, retries, sleep_sec, headers=sec_headers(sec_user_agent))
    j = json.loads(raw)

    recent = (((j.get("filings") or {}).get("recent")) or {})
    forms = recent.get("form", []) or []
    filing_dates = recent.get("filingDate", []) or []
    accession_numbers = recent.get("accessionNumber", []) or []
    primary_documents = recent.get("primaryDocument", []) or []
    primary_doc_desc = recent.get("primaryDocDescription", []) or []

    rows: List[Dict[str, Any]] = []
    target_dt = parse_iso_date(as_of_date)
    if target_dt is None:
        return [], url

    n = min(len(forms), len(filing_dates), len(accession_numbers), len(primary_documents))
    cik_int = str(int(cik))  # remove leading zeros for archive URL path

    for i in range(n):
        form = str(forms[i] or "")
        if "6-K" not in form.upper():
            continue

        filing_date = str(filing_dates[i] or "")
        fd = parse_iso_date(filing_date)
        if fd is None:
            continue

        delta = abs((fd - target_dt).days)
        if delta > lookback_days:
            continue

        accession = str(accession_numbers[i] or "")
        primary = str(primary_documents[i] or "")
        if not accession or not primary:
            continue

        accession_nodash = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary}"

        rows.append(
            {
                "url": filing_url,
                "title": str(primary_doc_desc[i] or primary or filing_url),
                "filing_date": filing_date,
                "accession_number": accession,
                "form": form,
                "src_hint": "sec_recent_6k",
                "accept_reason": f"sec_submissions_json_delta_{delta}",
                "delta_days": delta,
            }
        )

    rows.sort(key=lambda x: (int(x["delta_days"]), x["filing_date"]))
    return rows, url


def build_seed_candidate_list(
    seed: Dict[str, Any],
    sec_candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(url: str, title: str, src_hint: str, accept_reason: str) -> None:
        u = (url or "").strip()
        if not u or not u.startswith("http"):
            return
        if u in seen:
            return
        seen.add(u)
        out.append(
            {
                "url": u,
                "title": title or u,
                "src_hint": src_hint,
                "accept_reason": accept_reason,
            }
        )

    for item in seed.get("verification_candidates", []) or []:
        add(str(item), str(item), "seed_manual_candidate", "seed_manual_candidate")

    for item in sec_candidates:
        add(
            item["url"],
            item.get("title", item["url"]),
            "sec_recent_6k",
            item.get("accept_reason", "sec_recent_6k"),
        )

    for key, hint in [
        ("pdf_url", "seed_pdf_url"),
        ("article_url", "seed_article_url"),
        ("page_url", "seed_page_url"),
        ("sec_filing_url", "seed_sec_filing_url"),
        ("sec_document_url", "seed_sec_document_url"),
    ]:
        val = str(seed.get(key, "")).strip()
        if val:
            add(val, val, hint, hint)

    return out


def verify_candidate_url(
    session: requests.Session,
    candidate: Dict[str, Any],
    *,
    expected_year: int,
    expected_quarter_num: int,
    expected_quarter: str,
    expected_eps: float,
    sec_user_agent: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    expand_sec_links: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    url = candidate["url"]
    title_hint = candidate.get("title", url)
    src_hint = candidate.get("src_hint", "unknown")
    accept_reason = candidate.get("accept_reason", "unknown")

    attempt: Dict[str, Any] = {
        "url": url,
        "title_hint": title_hint,
        "src_hint": src_hint,
        "accept_reason": accept_reason,
        "fetch_ok": False,
        "parse_ok": False,
        "parse_reason": None,
        "parsed_quarter": None,
        "parsed_eps": None,
        "expected_quarter": expected_quarter,
        "expected_eps": expected_eps,
        "matched_eps": False,
        "match_ok": False,
        "blocked_reason": None,
        "excerpt": None,
        "expanded_links_count": 0,
    }

    host = canonical_host(urlparse(url).netloc)
    hdrs = sec_headers(sec_user_agent) if host.endswith("sec.gov") or host == "data.sec.gov" else None
    path = urlparse(url).path.lower()

    if path.endswith(".pdf"):
        try:
            pdf_bytes = http_get_bytes(session, url, timeout, retries, sleep_sec, headers=hdrs)
            attempt["fetch_ok"] = True

            rec, reason = parse_pdf_record(
                pdf_bytes,
                url,
                expected_year=expected_year,
                expected_quarter_num=expected_quarter_num,
            )
            if rec is None:
                attempt["parse_reason"] = reason
                return None, attempt

            attempt["parse_ok"] = True
            attempt["parsed_quarter"] = rec["quarter"]
            attempt["parsed_eps"] = rec["eps"]
            attempt["matched_eps"] = abs(float(rec["eps"]) - float(expected_eps)) <= 0.01
            attempt["match_ok"] = (rec["quarter"] == expected_quarter) and attempt["matched_eps"]

            if not attempt["match_ok"]:
                attempt["parse_reason"] = f"quarter_or_eps_mismatch:{rec['quarter']}:{rec['eps']}"
                return None, attempt

            attempt["parse_reason"] = "ok"
            return rec, attempt

        except Exception as e:
            attempt["parse_reason"] = f"pdf_fetch_failed:{e}"
            return None, attempt

    try:
        html = http_get_text(session, url, timeout, retries, sleep_sec, headers=hdrs)
        attempt["fetch_ok"] = True
        attempt["excerpt"] = clean_html_text(html)[:220]
    except Exception as e:
        attempt["parse_reason"] = f"fetch_failed:{e}"
        return None, attempt

    block_reason = detect_block_reason(html)
    if block_reason:
        attempt["blocked_reason"] = block_reason

    rec, reason = parse_html_record(
        html,
        url,
        expected_year=expected_year,
        expected_quarter_num=expected_quarter_num,
    )

    if rec is not None:
        attempt["parse_ok"] = True
        attempt["parsed_quarter"] = rec["quarter"]
        attempt["parsed_eps"] = rec["eps"]
        attempt["matched_eps"] = abs(float(rec["eps"]) - float(expected_eps)) <= 0.01
        attempt["match_ok"] = (rec["quarter"] == expected_quarter) and attempt["matched_eps"]

        if attempt["match_ok"]:
            attempt["parse_reason"] = "ok"
            return rec, attempt

        attempt["parse_reason"] = f"quarter_or_eps_mismatch:{rec['quarter']}:{rec['eps']}"
    else:
        attempt["parse_reason"] = reason

    # SEC filing pages often need one extra layer expansion to exhibits / linked docs.
    if expand_sec_links and host.endswith("sec.gov"):
        links = extract_links(html, url)
        doc_links: List[Dict[str, Any]] = []

        for full, title in links:
            p = urlparse(full).path.lower()
            if not full.startswith("https://www.sec.gov/Archives/edgar/data/"):
                continue
            if not (p.endswith(".htm") or p.endswith(".html") or p.endswith(".txt") or p.endswith(".pdf")):
                continue
            doc_links.append({"url": full, "title": title or full})

        doc_links.sort(key=lambda x: (-score_sec_link(x["url"], x["title"]), x["url"]))
        attempt["expanded_links_count"] = len(doc_links)

        for child in doc_links[:12]:
            child_rec, child_attempt = verify_candidate_url(
                session,
                {
                    "url": child["url"],
                    "title": child["title"],
                    "src_hint": "sec_extracted_link",
                    "accept_reason": f"expanded_from:{url}",
                },
                expected_year=expected_year,
                expected_quarter_num=expected_quarter_num,
                expected_quarter=expected_quarter,
                expected_eps=expected_eps,
                sec_user_agent=sec_user_agent,
                timeout=timeout,
                retries=retries,
                sleep_sec=sleep_sec,
                expand_sec_links=False,
            )
            if child_rec is not None:
                child_attempt["parent_url"] = url
                return child_rec, child_attempt

    return None, attempt


def update_record_with_verification(
    seed_record: Dict[str, Any],
    verified: Optional[Dict[str, Any]],
    attempt: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    out = copy.deepcopy(seed_record)

    if verified is not None and attempt is not None:
        verification_status = "VERIFIED"
        verification_method = str(attempt.get("src_hint") or "unknown")
        verified_url = str(attempt.get("url") or "")
        reason = "matched_seed_quarter_and_eps"
        verified_eps = verified.get("eps")
        verified_quarter = verified.get("quarter")
        verified_as_of_date = verified.get("as_of_date")
        out["reference_url_verified_this_run"] = True
    else:
        verification_status = "VERIFY_FAILED"
        verification_method = str((attempt or {}).get("src_hint") or "NA")
        verified_url = str((attempt or {}).get("url") or "")
        reason = str((attempt or {}).get("parse_reason") or "no_attempt")
        verified_eps = None
        verified_quarter = None
        verified_as_of_date = None
        out["reference_url_verified_this_run"] = False

    out["verification"] = {
        "status": verification_status,
        "method": verification_method,
        "verified_url": verified_url,
        "reason": reason,
        "verified_quarter": verified_quarter,
        "verified_eps": verified_eps,
        "verified_as_of_date": verified_as_of_date,
        "attempted_at_utc": now_utc_iso(),
    }
    out["verification_status"] = verification_status
    out["verification_method"] = verification_method
    out["verified_url"] = verified_url
    out["verified_eps"] = verified_eps
    out["verified_as_of_date"] = verified_as_of_date
    out["fetched_at_utc"] = now_utc_iso()
    return out


def build_debug_quarter_entry(year: int, quarter_num: int) -> Dict[str, Any]:
    q = f"{year}Q{quarter_num}"
    return {
        "quarter": q,
        "publication_state": assess_publication_state(year, quarter_num, today_local_date()),
        "candidate_urls": [],
        "attempts": [],
        "discovered": False,
        "discovered_record_source": None,
        "status": "NOT_RUN",
    }


def verify_seed_record(
    session: requests.Session,
    seed_record: Dict[str, Any],
    *,
    sec_cik: str,
    sec_user_agent: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    sec_lookback_days: int,
    notes: List[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    quarter = str(seed_record["quarter"])
    year = int(quarter[:4])
    qnum = int(quarter[-1])
    expected_eps = float(seed_record["eps"])
    debug = build_debug_quarter_entry(year, qnum)

    submissions_url = None
    sec_candidates: List[Dict[str, Any]] = []

    try:
        sec_candidates, submissions_url = fetch_sec_recent_6k_candidates(
            session,
            cik=sec_cik,
            sec_user_agent=sec_user_agent,
            as_of_date=str(seed_record["as_of_date"]),
            timeout=timeout,
            retries=retries,
            sleep_sec=sleep_sec,
            lookback_days=sec_lookback_days,
        )
        if submissions_url:
            notes.append(f"{quarter}: SEC submissions queried: {submissions_url} | candidates={len(sec_candidates)}")
    except Exception as e:
        notes.append(f"{quarter}: SEC submissions query failed | err={e}")

    candidates = build_seed_candidate_list(seed_record, sec_candidates)
    debug["candidate_urls"] = candidates

    if not candidates:
        debug["status"] = "NO_CANDIDATES"
        verified_record = update_record_with_verification(seed_record, None, None)
        return verified_record, debug

    last_attempt: Optional[Dict[str, Any]] = None

    for candidate in candidates:
        rec, attempt = verify_candidate_url(
            session,
            candidate,
            expected_year=year,
            expected_quarter_num=qnum,
            expected_quarter=quarter,
            expected_eps=expected_eps,
            sec_user_agent=sec_user_agent,
            timeout=timeout,
            retries=retries,
            sleep_sec=sleep_sec,
            expand_sec_links=True,
        )
        debug["attempts"].append(attempt)
        last_attempt = attempt

        if rec is not None:
            debug["discovered"] = True
            debug["discovered_record_source"] = attempt.get("src_hint")
            debug["status"] = "VERIFIED"
            notes.append(
                f"{quarter}: verified via {attempt.get('src_hint')} | "
                f"url={attempt.get('url')} | eps={rec.get('eps')}"
            )
            return update_record_with_verification(seed_record, rec, attempt), debug

        notes.append(
            f"{quarter}: verify failed via {attempt.get('src_hint')} | "
            f"url={attempt.get('url')} | reason={attempt.get('parse_reason')}"
        )

    pub_state = debug["publication_state"]
    if pub_state in {"NOT_ENDED_YET", "LIKELY_NOT_PUBLISHED_YET"}:
        debug["status"] = pub_state
    else:
        debug["status"] = "VERIFY_FAILED"

    return update_record_with_verification(seed_record, None, last_attempt), debug


def build_output(
    merged_quarters: List[Dict[str, Any]],
    entry_pages: List[str],
    notes: List[str],
    discovery_debug: List[Dict[str, Any]],
) -> Dict[str, Any]:
    verified_count = sum(1 for x in merged_quarters if x.get("verification_status") == "VERIFIED")
    seed_count = sum(1 for x in merged_quarters if x.get("data_origin") == "bootstrap_seed")

    return {
        "meta": {
            "generated_at_utc": now_utc_iso(),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "source_policy": "seed_first_plus_sec_verification_then_direct_url_probe_no_search",
            "entry_pages": entry_pages,
            "notes": notes,
            "counts": {
                "verified_count": verified_count,
                "bootstrap_seed_count": seed_count,
                "total_quarters": len(merged_quarters),
            },
            "optional_features": {
                "pypdf_installed": HAVE_PYPDF,
            },
        },
        "discovery_debug": discovery_debug,
        "quarters": merged_quarters,
    }


def iter_target_quarters(start_year: int, end_year: int) -> List[Tuple[int, int]]:
    years = list(range(start_year, end_year - 1, -1)) if start_year >= end_year else list(range(start_year, end_year + 1))
    out: List[Tuple[int, int]] = []
    for y in years:
        for q in (1, 2, 3, 4):
            out.append((y, q))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update TSMC quarterly EPS tracker (seed-first + SEC verification)."
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output tracker JSON path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    parser.add_argument("--sleep-sec", type=float, default=DEFAULT_SLEEP, help="Sleep between retries")
    parser.add_argument("--start-year", type=int, default=datetime.now().year, help="Start year to scan")
    parser.add_argument("--end-year", type=int, default=max(datetime.now().year - 5, 2024), help="End year to scan")
    parser.add_argument("--sec-cik", default=DEFAULT_SEC_CIK, help="SEC CIK, zero-padded, e.g. 0001046179")
    parser.add_argument(
        "--sec-user-agent",
        default=DEFAULT_SEC_USER_AGENT,
        help="User-Agent used for SEC requests",
    )
    parser.add_argument(
        "--sec-lookback-days",
        type=int,
        default=DEFAULT_SEC_LOOKBACK_DAYS,
        help="Max abs day distance from seed as_of_date when selecting recent 6-K candidates",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session(args.sec_user_agent)
    existing = load_existing_tracker(out_path)
    existing_quarters = existing.get("quarters", [])

    notes: List[str] = []
    entry_pages: List[str] = [sec_submissions_url(args.sec_cik)]
    discovery_debug: List[Dict[str, Any]] = []
    fetched: List[Dict[str, Any]] = []

    seed_map: Dict[str, Dict[str, Any]] = {}
    for seed in BOOTSTRAP_SEEDS:
        item = enrich_record(
            seed,
            data_origin="bootstrap_seed",
            reference_source_type="bootstrap_seed",
            reference_url_verified_this_run=False,
        )
        seed_map[str(item["quarter"])] = item

    notes.append(f"bootstrapped seeds={len(seed_map)}")
    notes.append(f"optional pypdf installed={HAVE_PYPDF}")
    notes.append(f"SEC verification enabled with cik={args.sec_cik}")

    target_quarters = {f"{y}Q{q}" for y, q in iter_target_quarters(args.start_year, args.end_year)}
    relevant_quarters = sorted(
        set(target_quarters)
        | set(seed_map.keys())
        | {str(x.get('quarter')) for x in existing_quarters if x.get('quarter')},
        key=quarter_sort_key,
    )

    existing_map = {str(x.get("quarter")): x for x in existing_quarters if x.get("quarter")}

    for quarter in relevant_quarters:
        m = re.match(r"^(\d{4})Q([1-4])$", quarter)
        if not m:
            continue

        year = int(m.group(1))
        qnum = int(m.group(2))

        if quarter in seed_map:
            verified_record, dbg = verify_seed_record(
                session,
                seed_map[quarter],
                sec_cik=args.sec_cik,
                sec_user_agent=args.sec_user_agent,
                timeout=args.timeout,
                retries=args.retries,
                sleep_sec=args.sleep_sec,
                sec_lookback_days=args.sec_lookback_days,
                notes=notes,
            )
            fetched.append(verified_record)
            discovery_debug.append(dbg)
        else:
            dbg = build_debug_quarter_entry(year, qnum)
            if quarter in existing_map:
                dbg["status"] = "NO_SEED_EXISTING_ONLY"
            else:
                dbg["status"] = dbg["publication_state"]
            discovery_debug.append(dbg)

    merged_quarters = merge_records(existing_quarters, fetched)
    out = build_output(
        merged_quarters=merged_quarters,
        entry_pages=entry_pages,
        notes=notes,
        discovery_debug=discovery_debug,
    )

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] wrote tracker: {out_path}")
    print(f"[INFO] existing_quarters={len(existing_quarters)}")
    print(f"[INFO] fetched_quarters={len(fetched)}")
    print(f"[INFO] merged_quarters={len(merged_quarters)}")
    print(f"[INFO] pypdf_installed={HAVE_PYPDF}")

    verified_count = sum(1 for x in merged_quarters if x.get("verification_status") == "VERIFIED")
    print(f"[INFO] verified_count={verified_count}")

    for q in merged_quarters:
        print(
            f"  - {q.get('quarter')}: EPS={q.get('eps')} | "
            f"as_of={q.get('as_of_date')} | source={q.get('source')} | "
            f"origin={q.get('data_origin')} | pri={q.get('source_priority')} | "
            f"verified_this_run={q.get('reference_url_verified_this_run')} | "
            f"verification_status={q.get('verification_status')} | "
            f"verified_url={q.get('verified_url')}"
        )

    print("[INFO] discovery_debug summary:")
    for d in discovery_debug:
        print(
            f"  - {d.get('quarter')}: status={d.get('status')} | "
            f"pub_state={d.get('publication_state')} | "
            f"candidate_urls={len(d.get('candidate_urls', []))} | "
            f"attempts={len(d.get('attempts', []))} | "
            f"discovered={d.get('discovered')}"
        )

    print("[INFO] notes:")
    for n in notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()