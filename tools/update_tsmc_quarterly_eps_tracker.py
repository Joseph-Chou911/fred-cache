#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v1.1)

Purpose
-------
Automatically fetch TSMC official quarterly diluted EPS from TSMC official
Investor Relations quarterly-results pages and update a local tracker JSON.

Design
------
- Source priority:
  1) https://investor.tsmc.com/english/quarterly-results/{year}/q{quarter}
  2) Earnings Release PDF linked from each quarterly-results page
- Only official TSMC investor pages / linked official PDFs are used.
- This script updates tracker data only.
- It does NOT modify active_eps_base directly.
- Intended to work with merge_0050_valuation_bb.py v1.6a+.

Dependencies
------------
- Python stdlib
- requests

Output schema
-------------
{
  "meta": {
    "generated_at_utc": "...",
    "script": "update_tsmc_quarterly_eps_tracker.py",
    "script_version": "v1.1",
    "source_policy": "official_tsmc_investor_quarterly_results_pdf_only",
    "entry_pages": [...],
    "notes": [...]
  },
  "quarters": [
    {
      "quarter": "2025Q1",
      "eps": 13.94,
      "source": "tsmc_official_investor_earnings_release_pdf",
      "as_of_date": "2025-04-17",
      "article_title": "Financial Results -2025Q1 | Earnings Release",
      "article_url": "...pdf",
      "quarter_end_date": "March 31, 2025",
      "quarter_word": "first",
      "page_url": ".../2025/q1",
      "fetched_at_utc": "..."
    }
  ]
}

Usage example
-------------
python tools/update_tsmc_quarterly_eps_tracker.py \
  --out tw0050_bb_cache/quarterly_eps_tracker.json
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
from urllib.parse import urljoin

import requests

SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v1.1"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_BASE_URL = "https://investor.tsmc.com/english/quarterly-results"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.2

UA = (
    "Mozilla/5.0 (compatible; TSMCQuarterlyEPSUpdater/1.1; "
    "+https://investor.tsmc.com/)"
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

A_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)


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


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


def http_get(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    binary: bool = False,
) -> requests.Response:
    last_err: Optional[Exception] = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} | last_err={last_err}")


def http_get_text(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> str:
    r = http_get(session, url, timeout, retries, sleep_sec, binary=False)
    r.encoding = r.encoding or "utf-8"
    return r.text


def http_get_bytes(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> bytes:
    r = http_get(session, url, timeout, retries, sleep_sec, binary=True)
    return r.content


def parse_page_title(page_html: str, page_url: str) -> str:
    m = H1_RE.search(page_html)
    if m:
        return clean_html_text(m.group(1))
    return page_url


def find_earnings_release_pdf_url(page_html: str, page_url: str) -> Optional[str]:
    candidates: List[Tuple[str, str]] = []

    for href, inner_html in A_RE.findall(page_html):
        text = clean_html_text(inner_html)
        abs_url = urljoin(page_url, href)

        if "earnings release" in text.lower():
            return abs_url

        if abs_url.lower().endswith(".pdf") and "earningsrelease" in abs_url.lower():
            candidates.append((text, abs_url))

    if candidates:
        return candidates[0][1]
    return None


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

    month_hits = MONTH_RE.findall(text)
    full_month_hits = MONTH_RE.finditer(text)
    first_date = None
    for m in full_month_hits:
        first_date = m.group(0)
        break

    issued_on_iso = iso_from_long_date(first_date) if first_date else "NA"

    return {
        "article_title": f"{page_title} | Earnings Release",
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


def normalize_record(rec: Dict[str, Any], page_url: str) -> Dict[str, Any]:
    return {
        "quarter": str(rec["quarter"]),
        "eps": float(rec["eps"]),
        "source": "tsmc_official_investor_earnings_release_pdf",
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
    years: List[int]
    if start_year >= end_year:
        years = list(range(start_year, end_year - 1, -1))
    else:
        years = list(range(start_year, end_year + 1))

    out: List[Tuple[int, int]] = []
    for y in years:
        for q in (1, 2, 3, 4):
            out.append((y, q))
    return out


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

        try:
            page_html = http_get_text(session, page_url, timeout, retries, sleep_sec)
        except Exception as e:
            notes.append(f"Skipped quarterly page {page_url}: {e}")
            continue

        page_title = parse_page_title(page_html, page_url)
        pdf_url = find_earnings_release_pdf_url(page_html, page_url)

        if not pdf_url:
            notes.append(f"No Earnings Release PDF link found on quarterly page {page_url}")
            continue

        try:
            pdf_bytes = http_get_bytes(session, pdf_url, timeout, retries, sleep_sec)
        except Exception as e:
            notes.append(f"Failed PDF fetch {pdf_url}: {e}")
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
            notes.append(f"Skipped PDF {pdf_url}: {reason}")
            continue

        q = str(detail["quarter"])
        if q in seen_quarters:
            notes.append(f"Duplicate quarter skipped from fetched set: {q} | {pdf_url}")
            continue

        seen_quarters.add(q)
        fetched.append(normalize_record(detail, page_url=page_url))
        notes.append(f"Parsed {q} EPS={detail['eps']} from {pdf_url}")

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
            "source_policy": "official_tsmc_investor_quarterly_results_pdf_only",
            "entry_pages": entry_pages,
            "notes": notes,
        },
        "quarters": merged_quarters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch TSMC official quarterly diluted EPS from investor quarterly-results pages"
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