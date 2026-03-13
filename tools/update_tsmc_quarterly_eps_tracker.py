#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v1.0)

Purpose
-------
Automatically fetch TSMC official quarterly diluted EPS from TSMC official
Press Center pages and update a local tracker JSON.

Design
------
- Source priority:
  1) https://pr.tsmc.com/english/latest-news
  2) https://pr.tsmc.com/english/news-archives
- Only official TSMC domains are used.
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
    "script_version": "v1.0",
    "source_policy": "official_tsmc_press_center_only",
    "entry_pages": [...],
    "notes": [...]
  },
  "quarters": [
    {
      "quarter": "2025Q1",
      "eps": 13.94,
      "source": "tsmc_official_press_release",
      "as_of_date": "2025-04-17",
      "article_title": "...",
      "article_url": "...",
      "quarter_end_date": "March 31, 2025",
      "quarter_word": "first",
      "fetched_at_utc": "..."
    }
  ]
}

Usage example
-------------
python scripts/update_tsmc_quarterly_eps_tracker.py \
  --out tw0050_bb_cache/quarterly_eps_tracker.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v1.0"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_LATEST_URL = "https://pr.tsmc.com/english/latest-news"
DEFAULT_ARCHIVE_URL = "https://pr.tsmc.com/english/news-archives"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.2

UA = (
    "Mozilla/5.0 (compatible; TSMCQuarterlyEPSUpdater/1.0; "
    "+https://pr.tsmc.com/)"
)

QUARTER_WORD_TO_NUM = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
}

TITLE_RE = re.compile(
    r"TSMC Reports\s+(First|Second|Third|Fourth)\s+Quarter EPS of NT\$\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)

ARTICLE_EPS_RE = re.compile(
    r"diluted earnings per share of NT\$\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)

ARTICLE_QUARTER_ENDED_RE = re.compile(
    r"for the\s+(first|second|third|fourth)\s+quarter ended\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    re.I,
)

ISSUED_ON_RE = re.compile(
    r"Issued on:\s*(\d{4}/\d{2}/\d{2})",
    re.I,
)

H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
A_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)


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
            r.encoding = r.encoding or "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} | last_err={last_err}")


def parse_candidate_article_links(list_page_html: str, base_url: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen: set[str] = set()

    for href, inner_html in A_RE.findall(list_page_html):
        text = clean_html_text(inner_html)
        m = TITLE_RE.search(text)
        if not m:
            continue

        abs_url = urljoin(base_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)

        out.append(
            {
                "title": text,
                "url": abs_url,
                "quarter_word_from_title": m.group(1).lower(),
                "eps_from_title": m.group(2),
            }
        )

    return out


def parse_article_detail(article_html: str, article_url: str) -> Dict[str, Any]:
    text = clean_html_text(article_html)

    h1_match = H1_RE.search(article_html)
    title = clean_html_text(h1_match.group(1)) if h1_match else "NA"

    issued_match = ISSUED_ON_RE.search(text)
    issued_on = issued_match.group(1) if issued_match else "NA"

    eps_match = ARTICLE_EPS_RE.search(text)
    eps_val = float(eps_match.group(1)) if eps_match else None

    qe_match = ARTICLE_QUARTER_ENDED_RE.search(text)
    if qe_match:
        quarter_word = qe_match.group(1).lower()
        quarter_end_date = qe_match.group(2)
        year_match = re.search(r"(\d{4})$", quarter_end_date)
        fiscal_year = int(year_match.group(1)) if year_match else None
        quarter_num = QUARTER_WORD_TO_NUM.get(quarter_word)
        quarter = quarter_label(fiscal_year, quarter_num) if (fiscal_year and quarter_num) else None
    else:
        quarter_word = None
        quarter_end_date = "NA"
        fiscal_year = None
        quarter = None

    return {
        "article_title": title,
        "article_url": article_url,
        "issued_on": issued_on,
        "eps": eps_val,
        "quarter_word": quarter_word,
        "quarter_end_date": quarter_end_date,
        "quarter": quarter,
        "raw_excerpt": text[:500],
    }


def validate_article_record(rec: Dict[str, Any]) -> Tuple[bool, str]:
    if not rec.get("quarter"):
        return False, "missing quarter"
    if rec.get("eps") is None:
        return False, "missing eps"
    if rec.get("issued_on") in (None, "", "NA"):
        return False, "missing issued_on"
    return True, "ok"


def normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "quarter": str(rec["quarter"]),
        "eps": float(rec["eps"]),
        "source": "tsmc_official_press_release",
        "as_of_date": str(rec["issued_on"]).replace("/", "-"),
        "article_title": str(rec.get("article_title", "NA")),
        "article_url": str(rec.get("article_url", "NA")),
        "quarter_end_date": str(rec.get("quarter_end_date", "NA")),
        "quarter_word": str(rec.get("quarter_word", "NA")),
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


def merge_records(
    existing: List[Dict[str, Any]],
    fetched: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
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


def fetch_all_quarterly_eps(
    session: requests.Session,
    latest_url: str,
    archive_url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    fetched: List[Dict[str, Any]] = []
    seen_article_urls: set[str] = set()

    list_pages = [latest_url, archive_url]
    candidate_links: List[Dict[str, str]] = []

    for lp in list_pages:
        try:
            html = http_get_text(session, lp, timeout=timeout, retries=retries, sleep_sec=sleep_sec)
            links = parse_candidate_article_links(html, lp)
            notes.append(f"Parsed {len(links)} candidate quarter-EPS links from {lp}")
            candidate_links.extend(links)
        except Exception as e:
            notes.append(f"Failed list page {lp}: {e}")

    deduped_links: List[Dict[str, str]] = []
    for item in candidate_links:
        url = item["url"]
        if url in seen_article_urls:
            continue
        seen_article_urls.add(url)
        deduped_links.append(item)

    for item in deduped_links:
        url = item["url"]
        try:
            html = http_get_text(session, url, timeout=timeout, retries=retries, sleep_sec=sleep_sec)
            detail = parse_article_detail(html, url)
            ok, reason = validate_article_record(detail)
            if not ok:
                notes.append(f"Skipped article {url}: {reason}")
                continue
            fetched.append(normalize_record(detail))
        except Exception as e:
            notes.append(f"Failed article {url}: {e}")

    fetched.sort(key=lambda x: quarter_sort_key(str(x["quarter"])))
    return fetched, notes


def build_output(
    merged_quarters: List[Dict[str, Any]],
    latest_url: str,
    archive_url: str,
    notes: List[str],
) -> Dict[str, Any]:
    return {
        "meta": {
            "generated_at_utc": now_utc_iso(),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "source_policy": "official_tsmc_press_center_only",
            "entry_pages": [latest_url, archive_url],
            "notes": notes,
        },
        "quarters": merged_quarters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch TSMC official quarterly diluted EPS and update quarterly_eps_tracker.json"
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output tracker JSON path")
    parser.add_argument("--latest-url", default=DEFAULT_LATEST_URL, help="TSMC official latest news page")
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL, help="TSMC official news archives page")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    parser.add_argument("--sleep-sec", type=float, default=DEFAULT_SLEEP, help="Sleep between retries / requests")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session()

    existing = load_existing_tracker(out_path)
    existing_quarters = existing.get("quarters", [])

    fetched_quarters, notes = fetch_all_quarterly_eps(
        session=session,
        latest_url=args.latest_url,
        archive_url=args.archive_url,
        timeout=args.timeout,
        retries=args.retries,
        sleep_sec=args.sleep_sec,
    )

    merged_quarters = merge_records(existing_quarters, fetched_quarters)
    out = build_output(
        merged_quarters=merged_quarters,
        latest_url=args.latest_url,
        archive_url=args.archive_url,
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


if __name__ == "__main__":
    main()