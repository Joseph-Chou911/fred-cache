#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v1.2)

Purpose
-------
Automatically fetch TSMC official quarterly diluted EPS and update a local tracker JSON.

What changed vs v1.1
--------------------
- Keep official TSMC PDF as the primary data source
- Add browser-like curl fallback when requests gets blocked
- Add search-based discovery fallback to locate official PDF URLs when
  quarterly-results pages return 403 in GitHub Actions
- Prefer official Earnings Release PDF
- Fallback to official Management Report PDF if Earnings Release PDF is not found
- Keep tracker schema backward-compatible

Source policy
-------------
- Primary data extraction must come from official TSMC investor PDFs
- Search engine is used only as a discovery mechanism for official PDF URLs
- If no official PDF can be fetched, the script records notes and leaves quarters empty
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
import zlib
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests

SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v1.2"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_BASE_URL = "https://investor.tsmc.com/english/quarterly-results"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.5

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

QUARTER_WORD_TO_NUM = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
}

MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
    re.I,
)

EPS_RE = re.compile(
    r"diluted earnings per share of NT\$\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)

QUARTER_ENDED_RE = re.compile(
    r"for the\s+(first|second|third|fourth)\s+quarter ended\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    re.I,
)

ANNUAL_EPS_RE = re.compile(
    r"Diluted EPS was NT\$\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)

A_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)

RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)

GENERIC_LINK_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def strip_tags(x: str) -> str:
    return re.sub(r"<[^>]+>", " ", x, flags=re.S)


def normalize_ws(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip()


def clean_html_text(x: str) -> str:
    return normalize_ws(unescape(strip_tags(x)))


def quarter_label(year: int, quarter_num: int) -> str:
    return f"{year}Q{quarter_num}"


def quarter_sort_key(q: str) -> Tuple[int, int]:
    m = re.match(r"^(\d{4})Q([1-4])$", q)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def iso_from_long_date(x: str) -> str:
    try:
        return datetime.strptime(x, "%B %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        return "NA"


def yy(year: int) -> str:
    return f"{year % 100:02d}"


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.google.com/",
        }
    )
    return s


def requests_get(
    session: requests.Session,
    url: str,
    timeout: int,
) -> requests.Response:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r


def curl_get_bytes(url: str, timeout: int) -> bytes:
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
        "Accept-Language: en-US,en;q=0.9",
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
    if not proc.stdout:
        raise RuntimeError(f"curl returned empty body for url={url}")
    return proc.stdout


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
            r = requests_get(session, url, timeout=timeout)
            r.encoding = r.encoding or "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            try:
                raw = curl_get_bytes(url, timeout=timeout)
                return raw.decode("utf-8", errors="ignore")
            except Exception as e2:
                last_err = e2
                if i < retries:
                    time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} | last_err={last_err}")


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
            r = requests_get(session, url, timeout=timeout)
            return r.content
        except Exception as e:
            last_err = e
            try:
                return curl_get_bytes(url, timeout=timeout)
            except Exception as e2:
                last_err = e2
                if i < retries:
                    time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET(bytes) failed after {retries} attempts: {url} | last_err={last_err}")


def parse_page_title(page_html: str, page_url: str) -> str:
    m = H1_RE.search(page_html)
    if m:
        return clean_html_text(m.group(1))
    return page_url


def pdf_preference_score(url: str) -> int:
    u = url.lower()
    score = 0
    if "earningsrelease.pdf" in u:
        score += 100
    if "management%20report.pdf" in u or "management report.pdf" in u:
        score += 50
    if "investor.tsmc.com" in u:
        score += 20
    return score


def find_pdf_links_in_quarter_page(page_html: str, page_url: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    for href, inner_html in A_RE.findall(page_html):
        text = clean_html_text(inner_html)
        abs_url = urljoin(page_url, href)
        u = abs_url.lower()

        if "investor.tsmc.com" not in u:
            continue

        if "earnings release" in text.lower() or "management report" in text.lower():
            if abs_url not in seen:
                seen.add(abs_url)
                out.append((text, abs_url))
            continue

        if u.endswith(".pdf") and ("earningsrelease" in u or "management%20report" in u or "management report" in u):
            if abs_url not in seen:
                seen.add(abs_url)
                out.append((text, abs_url))

    out.sort(key=lambda x: pdf_preference_score(x[1]), reverse=True)
    return out


def unwrap_ddg_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        q = parse_qs(parsed.query)
        uddg = q.get("uddg")
        if uddg:
            return unquote(uddg[0])
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

    results: List[Dict[str, str]] = []
    seen: set[str] = set()

    for href, inner_html in RESULT_LINK_RE.findall(html):
        real_url = unwrap_ddg_url(href)
        title = clean_html_text(inner_html)
        if real_url in seen:
            continue
        seen.add(real_url)
        results.append({"url": real_url, "title": title})

    # fallback parse if DDG changes class names
    if not results:
        for href, inner_html in GENERIC_LINK_RE.findall(html):
            real_url = unwrap_ddg_url(href)
            if "investor.tsmc.com" not in real_url.lower():
                continue
            title = clean_html_text(inner_html)
            if real_url in seen:
                continue
            seen.add(real_url)
            results.append({"url": real_url, "title": title})

    return results


def discover_pdf_urls_via_search(
    session: requests.Session,
    year: int,
    quarter_num: int,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> List[str]:
    token = f"{quarter_num}Q{yy(year)}"
    queries = [
        f'"{token}EarningsRelease.pdf" site:investor.tsmc.com',
        f'"{token} Management Report.pdf" site:investor.tsmc.com',
        f'TSMC "{token}" Earnings Release PDF site:investor.tsmc.com',
        f'TSMC "{token}" Management Report PDF site:investor.tsmc.com',
    ]

    found: List[str] = []
    seen: set[str] = set()

    for q in queries:
        try:
            results = search_ddg_html(session, q, timeout, retries, sleep_sec)
        except Exception:
            continue

        for item in results:
            url = item["url"]
            lu = url.lower()
            if "investor.tsmc.com" not in lu:
                continue
            if ".pdf" not in lu:
                continue
            if token.lower() not in lu:
                continue
            if "earningsrelease.pdf" not in lu and "management%20report.pdf" not in lu and "management report.pdf" not in lu:
                continue
            if url not in seen:
                seen.add(url)
                found.append(url)

    found.sort(key=pdf_preference_score, reverse=True)
    return found


def try_extract_pdf_text_with_pypdf(pdf_bytes: bytes) -> Optional[str]:
    for mod_name in ("pypdf", "PyPDF2"):
        try:
            mod = __import__(mod_name)
            reader_cls = getattr(mod, "PdfReader", None)
            if reader_cls is None:
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tf:
                tf.write(pdf_bytes)
                tf.flush()
                reader = reader_cls(tf.name)
                texts: List[str] = []
                for page in reader.pages:
                    try:
                        texts.append(page.extract_text() or "")
                    except Exception:
                        continue
                out = "\n".join(texts).strip()
                if out:
                    return out
        except Exception:
            continue
    return None


def try_extract_pdf_text_with_pdftotext(pdf_bytes: bytes) -> Optional[str]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tf:
            tf.write(pdf_bytes)
            tf.flush()
            proc = subprocess.run(
                ["pdftotext", "-layout", tf.name, "-"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout
    except Exception:
        return None
    return None


def try_extract_pdf_text_from_flate_streams(pdf_bytes: bytes) -> Optional[str]:
    chunks: List[str] = []
    pattern = re.compile(rb"<<.*?>>\s*stream\r?\n(.*?)\r?\nendstream", re.S)
    for m in pattern.finditer(pdf_bytes):
        raw_stream = m.group(1)
        try:
            data = zlib.decompress(raw_stream)
        except Exception:
            continue

        try:
            txt = data.decode("utf-8", errors="ignore")
        except Exception:
            txt = data.decode("latin1", errors="ignore")

        if txt:
            chunks.append(txt)

    if not chunks:
        return None
    return "\n".join(chunks)


def extract_pdf_text_best_effort(pdf_bytes: bytes) -> str:
    for fn in (
        try_extract_pdf_text_with_pypdf,
        try_extract_pdf_text_with_pdftotext,
        try_extract_pdf_text_from_flate_streams,
    ):
        out = fn(pdf_bytes)
        if out and out.strip():
            return normalize_ws(out)
    return ""


def parse_pdf_detail(
    pdf_text: str,
    pdf_url: str,
    page_year: int,
    page_quarter_num: int,
    page_title: str,
) -> Dict[str, Any]:
    text = normalize_ws(pdf_text)

    eps_match = EPS_RE.search(text)
    eps_val = float(eps_match.group(1)) if eps_match else None

    quarter_word: Optional[str] = None
    quarter_end_date = "NA"
    quarter = None

    qe_match = QUARTER_ENDED_RE.search(text)
    if qe_match:
        quarter_word = qe_match.group(1).lower()
        quarter_end_date = qe_match.group(2)
        year_match = re.search(r"(\d{4})$", quarter_end_date)
        fiscal_year = int(year_match.group(1)) if year_match else page_year
        quarter_num = QUARTER_WORD_TO_NUM.get(quarter_word, page_quarter_num)
        quarter = quarter_label(fiscal_year, quarter_num)
    else:
        quarter_word = {1: "first", 2: "second", 3: "third", 4: "fourth"}.get(page_quarter_num)
        quarter = quarter_label(page_year, page_quarter_num)

    first_date_match = MONTH_RE.search(text)
    issued_on_iso = iso_from_long_date(first_date_match.group(0)) if first_date_match else "NA"

    return {
        "article_title": f"{page_title} | PDF",
        "article_url": pdf_url,
        "issued_on": issued_on_iso,
        "eps": eps_val,
        "quarter_word": quarter_word,
        "quarter_end_date": quarter_end_date,
        "quarter": quarter,
        "raw_excerpt": text[:500],
    }


def validate_record(rec: Dict[str, Any]) -> Tuple[bool, str]:
    if not rec.get("quarter"):
        return False, "missing quarter"
    if rec.get("eps") is None:
        return False, "missing eps"
    if rec.get("issued_on") in (None, "", "NA"):
        return False, "missing issued_on"
    return True, "ok"


def normalize_record(rec: Dict[str, Any], page_url: str, source_label: str) -> Dict[str, Any]:
    return {
        "quarter": str(rec["quarter"]),
        "eps": float(rec["eps"]),
        "source": source_label,
        "as_of_date": str(rec["issued_on"]),
        "article_title": str(rec.get("article_title", "NA")),
        "article_url": str(rec.get("article_url", "NA")),
        "quarter_end_date": str(rec.get("quarter_end_date", "NA")),
        "quarter_word": str(rec.get("quarter_word", "NA")),
        "page_url": str(page_url),
        "fetched_at_utc": now_utc_iso(),
    }


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
        if q:
            merged[q] = item

    for item in fetched:
        q = str(item["quarter"])
        merged[q] = item

    out = list(merged.values())
    out.sort(key=lambda x: quarter_sort_key(str(x.get("quarter", ""))))
    return out


def iter_quarter_pages(start_year: int, end_year: int) -> List[Tuple[int, int]]:
    if start_year >= end_year:
        years = list(range(start_year, end_year - 1, -1))
    else:
        years = list(range(start_year, end_year + 1))

    out: List[Tuple[int, int]] = []
    for y in years:
        for q in (1, 2, 3, 4):
            out.append((y, q))
    return out


def fetch_one_quarter_record(
    session: requests.Session,
    base_url: str,
    year: int,
    quarter_num: int,
    timeout: int,
    retries: int,
    sleep_sec: float,
    notes: List[str],
) -> Optional[Dict[str, Any]]:
    page_url = f"{base_url}/{year}/q{quarter_num}"
    page_title = f"Financial Results - {year}Q{quarter_num}"
    pdf_candidates: List[str] = []

    # Step 1: try quarter page directly
    try:
        page_html = http_get_text(session, page_url, timeout, retries, sleep_sec)
        page_title = parse_page_title(page_html, page_url)
        page_links = find_pdf_links_in_quarter_page(page_html, page_url)
        if page_links:
            pdf_candidates.extend([u for _, u in page_links])
            notes.append(f"Found {len(page_links)} PDF link(s) from quarter page {page_url}")
        else:
            notes.append(f"No PDF links found on quarter page {page_url}")
    except Exception as e:
        notes.append(f"Quarter page blocked or failed {page_url}: {e}")

    # Step 2: search-based official PDF discovery
    if not pdf_candidates:
        discovered = discover_pdf_urls_via_search(session, year, quarter_num, timeout, retries, sleep_sec)
        if discovered:
            pdf_candidates.extend(discovered)
            notes.append(f"Search discovery found {len(discovered)} official PDF candidate(s) for {year}Q{quarter_num}")
        else:
            notes.append(f"Search discovery found no official PDF for {year}Q{quarter_num}")

    # de-dup + sort
    seen: set[str] = set()
    uniq_candidates: List[str] = []
    for u in pdf_candidates:
        if u not in seen:
            seen.add(u)
            uniq_candidates.append(u)
    uniq_candidates.sort(key=pdf_preference_score, reverse=True)

    for pdf_url in uniq_candidates:
        try:
            pdf_bytes = http_get_bytes(session, pdf_url, timeout, retries, sleep_sec)
        except Exception as e:
            notes.append(f"Failed official PDF fetch {pdf_url}: {e}")
            continue

        pdf_text = extract_pdf_text_best_effort(pdf_bytes)
        if not pdf_text:
            notes.append(f"Failed PDF text extraction {pdf_url}")
            continue

        detail = parse_pdf_detail(
            pdf_text=pdf_text,
            pdf_url=pdf_url,
            page_year=year,
            page_quarter_num=quarter_num,
            page_title=page_title,
        )
        ok, reason = validate_record(detail)
        if not ok:
            notes.append(f"Skipped parsed PDF {pdf_url}: {reason}")
            continue

        source_label = "tsmc_official_investor_earnings_release_pdf"
        if "management" in pdf_url.lower():
            source_label = "tsmc_official_investor_management_report_pdf"

        notes.append(f"Parsed {detail['quarter']} EPS={detail['eps']} from official PDF {pdf_url}")
        return normalize_record(detail, page_url=page_url, source_label=source_label)

    return None


def fetch_all_quarterly_eps(
    session: requests.Session,
    base_url: str,
    start_year: int,
    end_year: int,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    notes: List[str] = []
    entry_pages: List[str] = []
    fetched: List[Dict[str, Any]] = []
    seen_quarters: set[str] = set()

    for year, quarter_num in iter_quarter_pages(start_year, end_year):
        page_url = f"{base_url}/{year}/q{quarter_num}"
        entry_pages.append(page_url)

        rec = fetch_one_quarter_record(
            session=session,
            base_url=base_url,
            year=year,
            quarter_num=quarter_num,
            timeout=timeout,
            retries=retries,
            sleep_sec=sleep_sec,
            notes=notes,
        )
        if rec is None:
            continue

        q = str(rec["quarter"])
        if q in seen_quarters:
            notes.append(f"Duplicate quarter skipped from fetched set: {q}")
            continue

        seen_quarters.add(q)
        fetched.append(rec)

    fetched.sort(key=lambda x: quarter_sort_key(str(x["quarter"])))
    return fetched, notes, entry_pages


def build_output(
    merged_quarters: List[Dict[str, Any]],
    entry_pages: List[str],
    notes: List[str],
) -> Dict[str, Any]:
    return {
        "meta": {
            "generated_at_utc": now_utc_iso(),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "source_policy": "official_tsmc_pdf_with_search_discovery_fallback",
            "entry_pages": entry_pages,
            "notes": notes,
        },
        "quarters": merged_quarters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch TSMC official quarterly diluted EPS from official PDFs"
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output tracker JSON path")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="TSMC investor quarterly results base URL")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    parser.add_argument("--sleep-sec", type=float, default=DEFAULT_SLEEP, help="Sleep between retries / requests")
    parser.add_argument(
        "--start-year",
        type=int,
        default=datetime.now().year,
        help="Start year to scan (default: current year)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=max(datetime.now().year - 5, 1997),
        help="End year to scan (default: current year - 5)",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session()

    existing = load_existing_tracker(out_path)
    existing_quarters = existing.get("quarters", [])

    fetched_quarters, notes, entry_pages = fetch_all_quarterly_eps(
        session=session,
        base_url=args.base_url,
        start_year=args.start_year,
        end_year=args.end_year,
        timeout=args.timeout,
        retries=args.retries,
        sleep_sec=args.sleep_sec,
    )

    merged_quarters = merge_records(existing_quarters, fetched_quarters)
    out = build_output(
        merged_quarters=merged_quarters,
        entry_pages=entry_pages,
        notes=notes,
    )

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote tracker: {out_path}")
    print(f"[INFO] existing_quarters={len(existing_quarters)}")
    print(f"[INFO] fetched_quarters={len(fetched_quarters)}")
    print(f"[INFO] merged_quarters={len(merged_quarters)}")

    for q in merged_quarters:
        print(
            f"  - {q.get('quarter')}: EPS={q.get('eps')} | "
            f"as_of={q.get('as_of_date')} | url={q.get('article_url')}"
        )

    if notes:
        print("[INFO] notes:")
        for n in notes:
            print(f"  - {n}")


if __name__ == "__main__":
    main()