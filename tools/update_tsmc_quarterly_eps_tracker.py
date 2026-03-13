#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v2.0)

What changed vs v1.6
--------------------
1) Official archive first:
   - Fetch https://pr.tsmc.com/chinese/news-archives
   - Parse official PR links/titles directly
   - Avoid making search engine discovery the primary path
2) Deterministic official fallback:
   - Try direct investor relations quarterly-results pages:
     https://investor.tsmc.com/chinese/quarterly-results/{year}/q{q}
     https://investor.tsmc.com/english/quarterly-results/{year}/q{q}
3) Optional PDF fallback:
   - If a quarterly-results page exposes an Earnings Release PDF and pypdf is installed,
     parse EPS from the official PDF.
4) Search engine downgraded to last resort:
   - DuckDuckGo HTML discovery is retained only as fallback.
5) Better status separation:
   - NOT_ENDED_YET / LIKELY_NOT_PUBLISHED_YET / SEARCH_NO_RESULT / FETCH_OK_PARSE_FAILED / DISCOVERED
6) Keep output schema close to v1.6 for easier downstream compatibility.

Dependencies
------------
Required:
- requests

Optional (for official IR PDF fallback):
- pypdf
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import re
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests

try:
    from pypdf import PdfReader  # type: ignore
    HAVE_PYPDF = True
except Exception:
    PdfReader = None  # type: ignore
    HAVE_PYPDF = False


SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v2.0"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.5
DEFAULT_ARCHIVE_URL = "https://pr.tsmc.com/chinese/news-archives"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

QUARTER_NUM_TO_CN = {
    1: "第一",
    2: "第二",
    3: "第三",
    4: "第四",
}
QUARTER_CN_TO_NUM = {v: k for k, v in QUARTER_NUM_TO_CN.items()}

QUARTER_NUM_TO_EN_WORD = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
}
QUARTER_EN_WORD_TO_NUM = {v: k for k, v in QUARTER_NUM_TO_EN_WORD.items()}

SOURCE_PRIORITY = {
    "tsmc_official_chinese_news": 100,
    "tsmc_official_ir_earnings_release_pdf": 95,
    "tsmc_official_ir_quarterly_results_html": 90,
    "syndicated_official_announcement_cnyes": 60,
    "tsmc_official_chinese_news_seed": 20,
}

BOOTSTRAP_SEEDS: List[Dict[str, Any]] = [
    {
        "quarter": "2024Q4",
        "eps": 14.45,
        "source": "tsmc_official_chinese_news_seed",
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
        "source": "tsmc_official_chinese_news_seed",
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
        "source": "tsmc_official_chinese_news_seed",
        "as_of_date": "2025-07-17",
        "article_title": "台積公司2025年第二季每股盈餘新台幣15.36元",
        "article_url": "https://pr.tsmc.com/chinese/news/3249",
        "quarter_end_date": "June 30, 2025",
        "quarter_word": "second",
        "page_url": "https://pr.tsmc.com/chinese/news/3249",
    },
    {
        "quarter": "2025Q3",
        "eps": 17.44,
        "source": "tsmc_official_chinese_news_seed",
        "as_of_date": "2025-10-16",
        "article_title": "台積公司2025年第三季每股盈餘新台幣17.44元",
        "article_url": "https://pr.tsmc.com/chinese/news/3264",
        "quarter_end_date": "September 30, 2025",
        "quarter_word": "third",
        "page_url": "https://pr.tsmc.com/chinese/news/3264",
    },
    {
        "quarter": "2025Q4",
        "eps": 19.50,
        "source": "tsmc_official_chinese_news_seed",
        "as_of_date": "2026-01-15",
        "article_title": "台積公司2025年第四季每股盈餘新台幣19.50元",
        "article_url": "https://pr.tsmc.com/chinese/news/3281",
        "quarter_end_date": "December 31, 2025",
        "quarter_word": "fourth",
        "page_url": "https://pr.tsmc.com/chinese/news/3281",
    },
]

DATE_RE_LIST = [
    re.compile(r"發佈日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})"),
    re.compile(r"發言日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})"),
    re.compile(r"公告日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})"),
    re.compile(r"(\d{4}/\d{2}/\d{2})"),
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

CN_TITLE_RE = re.compile(
    r"台積公司(\d{4})年(第一|第二|第三|第四)季每股盈餘"
)

QUARTER_CN_YEAR_RE = re.compile(r"(\d{4})年(第一|第二|第三|第四)季")
QUARTER_Q_RE_1 = re.compile(r"(\d{4})\s*[Qq]([1-4])")
QUARTER_Q_RE_2 = re.compile(r"[Qq]([1-4])\s*(?:FY|fy)?\s*(\d{4})")
QUARTER_EN_YEAR_RE_1 = re.compile(r"\b(first|second|third|fourth)\s+quarter\s+(?:of\s+)?(\d{4})\b", re.I)
QUARTER_EN_YEAR_RE_2 = re.compile(r"\b(\d{4})\s+(first|second|third|fourth)\s+quarter\b", re.I)
QUARTER_EN_YEAR_RE_3 = re.compile(r"\b([1-4])Q\s*'?(\d{2,4})\b", re.I)

COMPANY_HINT_RE = re.compile(r"(台積電|台積公司|TSMC)", re.I)

EPS_PATTERNS = [
    re.compile(r"每股盈餘(?:為)?新台幣\s*([0-9]+(?:\.[0-9]+)?)\s*元"),
    re.compile(r"每股(?:盈餘|純益|稅後純益|獲利|賺(?:了|到)?)\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*元"),
    re.compile(r"稀釋每股(?:盈餘|純益)?\D{0,20}([0-9]+(?:\.[0-9]+)?)\s*元"),
    re.compile(r"\bEPS\b\D{0,12}([0-9]+(?:\.[0-9]+)?)\s*元?", re.I),
    re.compile(r"EPS達\D{0,8}([0-9]+(?:\.[0-9]+)?)\s*元", re.I),
    re.compile(r"Q[1-4]\s*EPS\D{0,12}([0-9]+(?:\.[0-9]+)?)\s*元", re.I),
]

PDF_EPS_PATTERNS = [
    re.compile(r"diluted earnings per share of NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
    re.compile(r"EPS of NT\$?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
]

H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
A_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
RESULT_A_RE = re.compile(
    r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)

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
    return re.sub(r"<[^>]+>", " ", x, flags=re.S)


def normalize_ws(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip()


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


def quarter_end_date_from_label(quarter: str) -> str:
    quarter_end_date_map = {
        "Q1": "March 31",
        "Q2": "June 30",
        "Q3": "September 30",
        "Q4": "December 31",
    }
    q_suffix = quarter[-2:]
    return f"{quarter_end_date_map.get(q_suffix, 'NA')}, {quarter[:4]}" if q_suffix in quarter_end_date_map else "NA"


def quarter_end_date_obj(year: int, quarter_num: int) -> date:
    if quarter_num == 1:
        return date(year, 3, 31)
    if quarter_num == 2:
        return date(year, 6, 30)
    if quarter_num == 3:
        return date(year, 9, 30)
    return date(year, 12, 31)


def assess_publication_state(year: int, quarter_num: int, today: date) -> str:
    q_end = quarter_end_date_obj(year, quarter_num)
    if today < q_end:
        return "NOT_ENDED_YET"
    if today < q_end + timedelta(days=21):
        return "LIKELY_NOT_PUBLISHED_YET"
    return "SHOULD_BE_PUBLISHED_OR_DISCOVERABLE"


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


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.google.com/",
        }
    )
    return s


def curl_get_text(url: str, timeout: int) -> str:
    cmd = [
        "curl",
        "-L",
        "--compressed",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout),
        "-A",
        UA,
        "-H",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H",
        "Accept-Language: zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "-H",
        "Cache-Control: no-cache",
        "-H",
        "Pragma: no-cache",
        "-e",
        "https://www.google.com/",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"curl failed rc={proc.returncode} url={url} stderr={proc.stderr.decode('utf-8', errors='ignore')[:300]}"
        )
    return proc.stdout.decode("utf-8", errors="ignore")


def http_get_bytes(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> bytes:
    last_err: Optional[Exception] = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET bytes failed after {retries} attempts: {url} | last_err={last_err}")


def http_get_text(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> str:
    last_err: Optional[Exception] = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            if r.encoding is None:
                r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            try:
                return curl_get_text(url, timeout=timeout)
            except Exception as e2:
                last_err = e2
                if i < retries:
                    time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} | last_err={last_err}")


def unwrap_search_url(url: str) -> str:
    url = unescape(url).strip()
    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)
    if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.startswith("/l/"):
        q = parse_qs(parsed.query)
        uddg = q.get("uddg")
        if uddg:
            return unquote(uddg[0])

    return url


def normalize_candidate_url(url: str) -> str:
    url = unwrap_search_url(url)
    url = unescape(url).strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def search_ddg_html(
    session: requests.Session,
    query: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> List[Dict[str, str]]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    html = http_get_text(session, url, timeout, retries, sleep_sec)

    out: List[Dict[str, str]] = []
    seen: set[str] = set()

    for href, inner_html in RESULT_A_RE.findall(html):
        real_url = normalize_candidate_url(href)
        title = clean_html_text(inner_html)
        if real_url in seen:
            continue
        seen.add(real_url)
        out.append({"url": real_url, "title": title})

    if not out:
        for href, inner_html in A_RE.findall(html):
            real_url = normalize_candidate_url(href)
            title = clean_html_text(inner_html)
            if real_url in seen:
                continue
            seen.add(real_url)
            out.append({"url": real_url, "title": title})

    return out


def find_title_text(html: str, fallback_url: str) -> str:
    m = H1_RE.search(html)
    if m:
        return clean_html_text(m.group(1))
    m = TITLE_TAG_RE.search(html)
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
        m = rx.search(text)
        if m:
            return m.group(1).replace("/", "-")

    for rx in EN_DATE_RE_LIST:
        m = rx.search(text)
        if m:
            month = MONTH_NAME_TO_NUM.get(m.group(1).lower())
            day = int(m.group(2))
            year = int(m.group(3))
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"

    return "NA"


def parse_article_record(
    html: str,
    url: str,
    *,
    expected_year: Optional[int],
    expected_quarter_num: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], str]:
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

    as_of_date = infer_date_from_text(text)
    qnum = int(quarter[-1])
    quarter_word = quarter_word_from_num(qnum)
    quarter_end_date = quarter_end_date_from_label(quarter)

    parsed = urlparse(url)
    host = canonical_host(parsed.netloc)

    source = "tsmc_official_chinese_news"
    reference_source_type = "official_tsmc_chinese_news"
    if host == "investor.tsmc.com":
        source = "tsmc_official_ir_quarterly_results_html"
        reference_source_type = "official_tsmc_ir_html"
    elif host.endswith("cnyes.com"):
        source = "syndicated_official_announcement_cnyes"
        reference_source_type = "cnyes"

    rec = {
        "quarter": quarter,
        "eps": eps_val,
        "source": source,
        "as_of_date": as_of_date,
        "article_title": title,
        "article_url": url,
        "quarter_end_date": quarter_end_date,
        "quarter_word": quarter_word,
        "page_url": url,
        "data_origin": "auto_discovered",
        "source_priority": detect_source_priority(source),
        "reference_source_type": reference_source_type,
        "reference_url_verified_this_run": True,
        "fetched_at_utc": now_utc_iso(),
    }
    return rec, "ok"


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
        return None, "eps_not_detected_in_pdf"

    as_of_date = infer_date_from_text(clean_text)
    qnum = int(quarter[-1])

    rec = {
        "quarter": quarter,
        "eps": eps_val,
        "source": "tsmc_official_ir_earnings_release_pdf",
        "as_of_date": as_of_date,
        "article_title": f"TSMC {quarter} Earnings Release PDF",
        "article_url": pdf_url,
        "quarter_end_date": quarter_end_date_from_label(quarter),
        "quarter_word": quarter_word_from_num(qnum),
        "page_url": pdf_url,
        "data_origin": "auto_discovered",
        "source_priority": detect_source_priority("tsmc_official_ir_earnings_release_pdf"),
        "reference_source_type": "official_tsmc_ir_pdf",
        "reference_url_verified_this_run": True,
        "fetched_at_utc": now_utc_iso(),
    }
    return rec, "ok"


def choose_better_record(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    old_pri = int(old.get("source_priority", detect_source_priority(str(old.get("source", "")))))
    new_pri = int(new.get("source_priority", detect_source_priority(str(new.get("source", "")))))

    if new_pri > old_pri:
        return new
    if new_pri < old_pri:
        return old

    old_verified = bool(old.get("reference_url_verified_this_run", False))
    new_verified = bool(new.get("reference_url_verified_this_run", False))
    if new_verified and not old_verified:
        return new
    if old_verified and not new_verified:
        return old

    old_origin = str(old.get("data_origin", ""))
    new_origin = str(new.get("data_origin", ""))
    if new_origin == "auto_discovered" and old_origin != "auto_discovered":
        return new
    if old_origin == "auto_discovered" and new_origin != "auto_discovered":
        return old

    return new


def load_existing_tracker(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"meta": {}, "quarters": []}

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
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

        if "source_priority" not in item:
            item["source_priority"] = detect_source_priority(str(item.get("source", "")))
        if "data_origin" not in item:
            item["data_origin"] = "unknown"
        if "reference_source_type" not in item:
            item["reference_source_type"] = "unknown"
        if "reference_url_verified_this_run" not in item:
            item["reference_url_verified_this_run"] = False

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


def build_debug_quarter_entry(year: int, quarter_num: int) -> Dict[str, Any]:
    q = f"{year}Q{quarter_num}"
    return {
        "quarter": q,
        "publication_state": assess_publication_state(year, quarter_num, today_local_date()),
        "archive_candidates": [],
        "direct_candidates": [],
        "queries": [],
        "candidates": [],
        "attempts": [],
        "discovered": False,
        "discovered_record_source": None,
        "status": "NOT_RUN",
    }


def result_likely_matches_quarter(title: str, expected_year: int, expected_quarter_num: int) -> bool:
    t = normalize_ws(title)
    if not t:
        return False

    quarter_cn = QUARTER_NUM_TO_CN[expected_quarter_num]
    quarter_en = QUARTER_NUM_TO_EN_WORD[expected_quarter_num]
    q_token = f"Q{expected_quarter_num}"

    if str(expected_year) in t and quarter_cn in t:
        return True
    if str(expected_year) in t and quarter_en.lower() in t.lower():
        return True
    if q_token.lower() in t.lower() and str(expected_year) in t:
        return True

    m = CN_TITLE_RE.search(t)
    if m:
        y = int(m.group(1))
        qn = QUARTER_CN_TO_NUM.get(m.group(2))
        return y == expected_year and qn == expected_quarter_num

    return False


def classify_candidate_result(
    url: str,
    title: str,
    expected_year: int,
    expected_quarter_num: int,
) -> Tuple[bool, Optional[str], str, str]:
    norm_url = normalize_candidate_url(url)
    parsed = urlparse(norm_url)
    host = canonical_host(parsed.netloc)
    path = (parsed.path or "").lower()

    if not parsed.scheme.startswith("http"):
        return False, None, "non_http_url", norm_url

    if "duckduckgo.com" in host:
        return False, None, "still_ddg_redirect", norm_url

    title_match = result_likely_matches_quarter(title or "", expected_year, expected_quarter_num)

    if host == "pr.tsmc.com":
        if "/chinese/news/" in path or path.startswith("/chinese/news"):
            return True, "official_pr", "accepted_pr_news", norm_url
        if path.startswith("/chinese/news-archives"):
            return True, "official_pr_archive", "accepted_pr_archive", norm_url
        return False, None, "pr_tsmc_but_path_not_supported", norm_url

    if host == "investor.tsmc.com":
        if f"/chinese/quarterly-results/{expected_year}/q{expected_quarter_num}" in path:
            return True, "official_ir_html", "accepted_ir_quarterly_results_html", norm_url
        if f"/english/quarterly-results/{expected_year}/q{expected_quarter_num}" in path:
            return True, "official_ir_html", "accepted_ir_quarterly_results_html", norm_url
        if path.endswith(".pdf") and ("earningsrelease" in path or title_match):
            return True, "official_ir_pdf", "accepted_ir_pdf", norm_url
        return False, None, "investor_tsmc_but_path_not_supported", norm_url

    if host.endswith("cnyes.com"):
        if "/news/id/" in path or ("/news/" in path and title_match):
            return True, "cnyes", "accepted_cnyes", norm_url
        return False, None, "cnyes_host_but_path_not_supported", norm_url

    return False, None, "host_not_supported", norm_url


def fetch_official_archive_candidates(
    session: requests.Session,
    timeout: int,
    retries: int,
    sleep_sec: float,
    archive_url: str = DEFAULT_ARCHIVE_URL,
) -> Tuple[List[Dict[str, str]], str]:
    html = http_get_text(session, archive_url, timeout, retries, sleep_sec)
    candidates: List[Dict[str, str]] = []
    seen: set[str] = set()

    for href, inner_html in A_RE.findall(html):
        title = clean_html_text(inner_html)
        if not title:
            continue

        norm_href = normalize_candidate_url(urljoin(archive_url, href))
        parsed = urlparse(norm_href)
        host = canonical_host(parsed.netloc)
        path = (parsed.path or "").lower()

        if host != "pr.tsmc.com":
            continue
        if "/chinese/news/" not in path:
            continue
        if "每股盈餘" not in title:
            continue
        if norm_href in seen:
            continue
        seen.add(norm_href)

        candidates.append(
            {
                "url": norm_href,
                "title": title,
                "src_hint": "official_archive",
                "accept_reason": "archive_link",
            }
        )

    return candidates, html


def extract_earnings_release_pdf_links(page_html: str, page_url: str) -> List[str]:
    urls: List[str] = []
    seen: set[str] = set()

    for href, inner_html in A_RE.findall(page_html):
        title = clean_html_text(inner_html).lower()
        full = normalize_candidate_url(urljoin(page_url, href))
        path = urlparse(full).path.lower()

        if not path.endswith(".pdf"):
            continue
        if "earningsrelease" not in path and "earnings release" not in title:
            continue
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)

    return urls


def build_direct_ir_candidates(year: int, quarter_num: int) -> List[Dict[str, str]]:
    out = [
        {
            "url": f"https://investor.tsmc.com/chinese/quarterly-results/{year}/q{quarter_num}",
            "title": f"TSMC {year}Q{quarter_num} official IR quarterly results (chinese)",
            "src_hint": "official_ir_html",
            "accept_reason": "direct_ir_html_chinese",
        },
        {
            "url": f"https://investor.tsmc.com/english/quarterly-results/{year}/q{quarter_num}",
            "title": f"TSMC {year}Q{quarter_num} official IR quarterly results (english)",
            "src_hint": "official_ir_html",
            "accept_reason": "direct_ir_html_english",
        },
    ]
    return out


def build_existing_url_candidates(existing_quarters: List[Dict[str, Any]], expected_quarter: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in existing_quarters:
        if str(item.get("quarter")) != expected_quarter:
            continue
        url = str(item.get("article_url", "") or item.get("page_url", "")).strip()
        title = str(item.get("article_title", "")).strip()
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": title or url,
                "src_hint": "existing_tracker",
                "accept_reason": "existing_tracker_url",
            }
        )
    return out


def search_one_quarter(
    session: requests.Session,
    year: int,
    quarter_num: int,
    timeout: int,
    retries: int,
    sleep_sec: float,
    notes: List[str],
    archive_candidates_all: List[Dict[str, str]],
    existing_quarters: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    quarter_cn = QUARTER_NUM_TO_CN[quarter_num]
    expected_quarter = f"{year}Q{quarter_num}"

    debug_entry = build_debug_quarter_entry(year, quarter_num)
    pub_state = debug_entry["publication_state"]

    if pub_state == "NOT_ENDED_YET":
        debug_entry["status"] = "NOT_ENDED_YET"
        notes.append(f"{expected_quarter}: skipped active discovery because quarter not ended yet")
        return None, debug_entry

    candidate_urls: List[Dict[str, str]] = []
    seen: set[str] = set()

    def add_candidate(item: Dict[str, str], bucket: str) -> None:
        norm_url = normalize_candidate_url(item["url"])
        if norm_url in seen:
            return
        seen.add(norm_url)
        candidate = {
            "url": norm_url,
            "title": item.get("title", norm_url),
            "src_hint": item.get("src_hint", "unknown"),
            "accept_reason": item.get("accept_reason", "unknown"),
        }
        candidate_urls.append(candidate)
        debug_entry[bucket].append(candidate)

    # 1) Official archive first
    for item in archive_candidates_all:
        if result_likely_matches_quarter(item.get("title", ""), year, quarter_num):
            add_candidate(item, "archive_candidates")

    # 2) Reuse known URLs from existing tracker
    for item in build_existing_url_candidates(existing_quarters, expected_quarter):
        add_candidate(item, "direct_candidates")

    # 3) Deterministic official IR pages
    for item in build_direct_ir_candidates(year, quarter_num):
        add_candidate(item, "direct_candidates")

    # 4) Search-engine fallback only if needed
    queries = [
        f'"台積公司{year}年{quarter_cn}季每股盈餘新台幣" site:pr.tsmc.com/chinese/news',
        f'"台積公司{year}年{quarter_cn}季每股盈餘新台幣" site:investor.tsmc.com',
        f'"TSMC {year} Q{quarter_num} earnings release" site:investor.tsmc.com',
        f'"台積電 {year} Q{quarter_num} EPS" site:anuenews.cnyes.com/news/id',
    ]

    for q in queries:
        query_debug: Dict[str, Any] = {
            "query": q,
            "result_count": 0,
            "status": "NOT_RUN",
            "raw_results": [],
        }
        try:
            results = search_ddg_html(session, q, timeout, retries, sleep_sec)
            query_debug["result_count"] = len(results)
            query_debug["status"] = "OK"
        except Exception as e:
            query_debug["status"] = f"FAIL: {e}"
            debug_entry["queries"].append(query_debug)
            notes.append(f"search query failed: {q} | err={e}")
            continue

        for item in results:
            raw_url = item["url"]
            title = item["title"]

            accepted, src_hint, reason, norm_url = classify_candidate_result(
                raw_url,
                title,
                year,
                quarter_num,
            )

            query_debug["raw_results"].append(
                {
                    "title": title,
                    "raw_url": raw_url,
                    "normalized_url": norm_url,
                    "accepted": accepted,
                    "src_hint": src_hint,
                    "reason": reason,
                }
            )

            if not accepted:
                continue
            add_candidate(
                {
                    "url": norm_url,
                    "title": title,
                    "src_hint": src_hint or "unknown",
                    "accept_reason": reason,
                },
                "candidates",
            )

        debug_entry["queries"].append(query_debug)

    if not debug_entry["candidates"]:
        debug_entry["candidates"] = list(candidate_urls)
    else:
        debug_entry["candidates"] = list(candidate_urls)

    def cand_rank(x: Dict[str, str]) -> Tuple[int, str]:
        src = x.get("src_hint", "")
        if src == "official_archive":
            return (0, x["url"])
        if src == "existing_tracker":
            return (1, x["url"])
        if src == "official_ir_html":
            return (2, x["url"])
        if src == "official_pr":
            return (3, x["url"])
        if src == "official_ir_pdf":
            return (4, x["url"])
        if src == "cnyes":
            return (5, x["url"])
        return (9, x["url"])

    candidate_urls.sort(key=cand_rank)

    if not candidate_urls:
        debug_entry["status"] = "SEARCH_NO_RESULT" if pub_state == "SHOULD_BE_PUBLISHED_OR_DISCOVERABLE" else pub_state
        notes.append(f"no candidate urls for {expected_quarter}")
        return None, debug_entry

    for cand in candidate_urls:
        url = cand["url"]
        title_hint = cand["title"]

        attempt: Dict[str, Any] = {
            "url": url,
            "title_hint": title_hint,
            "src_hint": cand.get("src_hint"),
            "accept_reason": cand.get("accept_reason"),
            "fetch_ok": False,
            "parse_ok": False,
            "parse_reason": None,
            "parsed_quarter": None,
            "parsed_eps": None,
            "excerpt": None,
            "expanded_pdf_urls": [],
        }

        path = urlparse(url).path.lower()

        if path.endswith(".pdf"):
            try:
                pdf_bytes = http_get_bytes(session, url, timeout, retries, sleep_sec)
                attempt["fetch_ok"] = True
                rec, reason = parse_pdf_record(
                    pdf_bytes,
                    url,
                    expected_year=year,
                    expected_quarter_num=quarter_num,
                )
                if rec is None:
                    attempt["parse_reason"] = reason
                    debug_entry["attempts"].append(attempt)
                    notes.append(f"candidate pdf parse failed: {url} | reason={reason}")
                    continue

                attempt["parse_ok"] = True
                attempt["parse_reason"] = "ok"
                attempt["parsed_quarter"] = rec["quarter"]
                attempt["parsed_eps"] = rec["eps"]

                if rec["quarter"] != expected_quarter:
                    attempt["parse_ok"] = False
                    attempt["parse_reason"] = f"quarter_mismatch:{rec['quarter']}"
                    debug_entry["attempts"].append(attempt)
                    notes.append(f"candidate pdf quarter mismatch: {url} -> {rec['quarter']} expected={expected_quarter}")
                    continue

                debug_entry["attempts"].append(attempt)
                debug_entry["discovered"] = True
                debug_entry["discovered_record_source"] = rec["source"]
                debug_entry["status"] = "DISCOVERED"
                notes.append(f"parsed quarter {rec['quarter']} eps={rec['eps']} from official pdf {url}")
                return rec, debug_entry
            except Exception as e:
                attempt["parse_reason"] = f"pdf_fetch_failed:{e}"
                debug_entry["attempts"].append(attempt)
                notes.append(f"candidate pdf fetch failed: {url} | err={e}")
                continue

        try:
            html = http_get_text(session, url, timeout, retries, sleep_sec)
            attempt["fetch_ok"] = True
            attempt["excerpt"] = clean_html_text(html)[:220]
        except Exception as e:
            attempt["parse_reason"] = f"fetch_failed: {e}"
            debug_entry["attempts"].append(attempt)
            notes.append(f"candidate fetch failed: {url} | err={e}")
            continue

        rec, reason = parse_article_record(
            html,
            url,
            expected_year=year,
            expected_quarter_num=quarter_num,
        )

        if rec is not None:
            attempt["parse_ok"] = True
            attempt["parse_reason"] = "ok"
            attempt["parsed_quarter"] = rec["quarter"]
            attempt["parsed_eps"] = rec["eps"]

            if rec["quarter"] != expected_quarter:
                attempt["parse_ok"] = False
                attempt["parse_reason"] = f"quarter_mismatch:{rec['quarter']}"
                debug_entry["attempts"].append(attempt)
                notes.append(f"candidate quarter mismatch: {url} -> {rec['quarter']} expected={expected_quarter}")
            else:
                debug_entry["attempts"].append(attempt)
                debug_entry["discovered"] = True
                debug_entry["discovered_record_source"] = rec["source"]
                debug_entry["status"] = "DISCOVERED"
                notes.append(f"parsed quarter {rec['quarter']} eps={rec['eps']} from {url} source={rec['source']}")
                return rec, debug_entry
        else:
            attempt["parse_reason"] = reason

        host = canonical_host(urlparse(url).netloc)
        if host == "investor.tsmc.com":
            pdf_urls = extract_earnings_release_pdf_links(html, url)
            attempt["expanded_pdf_urls"] = pdf_urls[:]
            for pdf_url in pdf_urls:
                pdf_attempt: Dict[str, Any] = {
                    "url": pdf_url,
                    "title_hint": "expanded_from_ir_html",
                    "src_hint": "official_ir_pdf",
                    "accept_reason": "expanded_from_ir_html",
                    "fetch_ok": False,
                    "parse_ok": False,
                    "parse_reason": None,
                    "parsed_quarter": None,
                    "parsed_eps": None,
                    "excerpt": None,
                }
                try:
                    pdf_bytes = http_get_bytes(session, pdf_url, timeout, retries, sleep_sec)
                    pdf_attempt["fetch_ok"] = True
                except Exception as e:
                    pdf_attempt["parse_reason"] = f"pdf_fetch_failed:{e}"
                    debug_entry["attempts"].append(pdf_attempt)
                    notes.append(f"expanded pdf fetch failed: {pdf_url} | err={e}")
                    continue

                rec_pdf, reason_pdf = parse_pdf_record(
                    pdf_bytes,
                    pdf_url,
                    expected_year=year,
                    expected_quarter_num=quarter_num,
                )
                if rec_pdf is None:
                    pdf_attempt["parse_reason"] = reason_pdf
                    debug_entry["attempts"].append(pdf_attempt)
                    notes.append(f"expanded pdf parse failed: {pdf_url} | reason={reason_pdf}")
                    continue

                pdf_attempt["parse_ok"] = True
                pdf_attempt["parse_reason"] = "ok"
                pdf_attempt["parsed_quarter"] = rec_pdf["quarter"]
                pdf_attempt["parsed_eps"] = rec_pdf["eps"]

                if rec_pdf["quarter"] != expected_quarter:
                    pdf_attempt["parse_ok"] = False
                    pdf_attempt["parse_reason"] = f"quarter_mismatch:{rec_pdf['quarter']}"
                    debug_entry["attempts"].append(pdf_attempt)
                    notes.append(f"expanded pdf quarter mismatch: {pdf_url} -> {rec_pdf['quarter']} expected={expected_quarter}")
                    continue

                debug_entry["attempts"].append(attempt)
                debug_entry["attempts"].append(pdf_attempt)
                debug_entry["discovered"] = True
                debug_entry["discovered_record_source"] = rec_pdf["source"]
                debug_entry["status"] = "DISCOVERED"
                notes.append(f"parsed quarter {rec_pdf['quarter']} eps={rec_pdf['eps']} from expanded pdf {pdf_url}")
                return rec_pdf, debug_entry

        debug_entry["attempts"].append(attempt)
        notes.append(f"candidate parse failed: {url} | reason={attempt['parse_reason']}")

    if pub_state in {"NOT_ENDED_YET", "LIKELY_NOT_PUBLISHED_YET"}:
        debug_entry["status"] = pub_state
    else:
        debug_entry["status"] = "FETCH_OK_PARSE_FAILED"

    notes.append(f"no discovered article parsed for {expected_quarter}")
    return None, debug_entry


def build_output(
    merged_quarters: List[Dict[str, Any]],
    entry_pages: List[str],
    notes: List[str],
    discovery_debug: List[Dict[str, Any]],
) -> Dict[str, Any]:
    auto_discovered_count = sum(1 for x in merged_quarters if x.get("data_origin") == "auto_discovered")
    seed_count = sum(1 for x in merged_quarters if x.get("data_origin") == "bootstrap_seed")

    return {
        "meta": {
            "generated_at_utc": now_utc_iso(),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "source_policy": (
                "bootstrap_seeds_plus_official_archive_first_"
                "then_direct_official_ir_then_pdf_then_search_fallback"
            ),
            "entry_pages": entry_pages,
            "notes": notes,
            "counts": {
                "auto_discovered_count": auto_discovered_count,
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
    parser = argparse.ArgumentParser(description="Update TSMC quarterly EPS tracker.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output tracker JSON path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    parser.add_argument("--sleep-sec", type=float, default=DEFAULT_SLEEP, help="Sleep between retries")
    parser.add_argument("--start-year", type=int, default=datetime.now().year, help="Start year to scan")
    parser.add_argument("--end-year", type=int, default=max(datetime.now().year - 5, 2024), help="End year to scan")
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL, help="Official PR news archive URL")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session()
    existing = load_existing_tracker(out_path)
    existing_quarters = existing.get("quarters", [])

    notes: List[str] = []
    entry_pages: List[str] = []
    discovery_debug: List[Dict[str, Any]] = []
    fetched: List[Dict[str, Any]] = []

    for seed in BOOTSTRAP_SEEDS:
        item = enrich_record(
            seed,
            data_origin="bootstrap_seed",
            reference_source_type="official_tsmc_chinese_news",
            reference_url_verified_this_run=False,
        )
        fetched.append(item)
    notes.append(f"bootstrapped seeds={len(BOOTSTRAP_SEEDS)}")
    notes.append(f"optional pypdf installed={HAVE_PYPDF}")

    try:
        archive_candidates_all, archive_html = fetch_official_archive_candidates(
            session=session,
            timeout=args.timeout,
            retries=args.retries,
            sleep_sec=args.sleep_sec,
            archive_url=args.archive_url,
        )
        notes.append(f"official archive fetch ok: {args.archive_url} | archive_eps_candidates={len(archive_candidates_all)}")
        entry_pages.append(args.archive_url)
        if archive_html:
            notes.append("official archive html fetched")
    except Exception as e:
        archive_candidates_all = []
        notes.append(f"official archive fetch failed: {args.archive_url} | err={e}")

    for year, quarter_num in iter_target_quarters(args.start_year, args.end_year):
        q = f"{year}Q{quarter_num}"
        entry_pages.append(f"scan://{q}")

        rec, dbg = search_one_quarter(
            session=session,
            year=year,
            quarter_num=quarter_num,
            timeout=args.timeout,
            retries=args.retries,
            sleep_sec=args.sleep_sec,
            notes=notes,
            archive_candidates_all=archive_candidates_all,
            existing_quarters=existing_quarters,
        )
        discovery_debug.append(dbg)
        if rec is not None:
            fetched.append(rec)

    merged_quarters = merge_records(existing_quarters, fetched)
    out = build_output(
        merged_quarters=merged_quarters,
        entry_pages=entry_pages,
        notes=notes,
        discovery_debug=discovery_debug,
    )

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote tracker: {out_path}")
    print(f"[INFO] existing_quarters={len(existing_quarters)}")
    print(f"[INFO] fetched_quarters={len(fetched)}")
    print(f"[INFO] merged_quarters={len(merged_quarters)}")

    auto_discovered_count = sum(1 for x in merged_quarters if x.get("data_origin") == "auto_discovered")
    seed_count = sum(1 for x in merged_quarters if x.get("data_origin") == "bootstrap_seed")
    print(f"[INFO] auto_discovered_count={auto_discovered_count}")
    print(f"[INFO] bootstrap_seed_count={seed_count}")
    print(f"[INFO] pypdf_installed={HAVE_PYPDF}")

    for q in merged_quarters:
        print(
            f"  - {q.get('quarter')}: EPS={q.get('eps')} | "
            f"as_of={q.get('as_of_date')} | source={q.get('source')} | "
            f"origin={q.get('data_origin')} | pri={q.get('source_priority')} | "
            f"verified_this_run={q.get('reference_url_verified_this_run')} | "
            f"url={q.get('article_url')}"
        )

    print("[INFO] discovery_debug summary:")
    for d in discovery_debug:
        print(
            f"  - {d.get('quarter')}: status={d.get('status')} | "
            f"pub_state={d.get('publication_state')} | "
            f"archive_candidates={len(d.get('archive_candidates', []))} | "
            f"direct_candidates={len(d.get('direct_candidates', []))} | "
            f"candidates={len(d.get('candidates', []))} | "
            f"attempts={len(d.get('attempts', []))} | "
            f"discovered={d.get('discovered')}"
        )

    print("[INFO] notes:")
    for n in notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()