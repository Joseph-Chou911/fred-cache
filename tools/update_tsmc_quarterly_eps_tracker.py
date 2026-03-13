#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v4.1-mops-q4-diff)

Design goals
------------
1) Seed-first
   - Quarterly EPS values still come from manually maintained seeds.
   - MOPS is used as the official verification path.

2) Official Taiwan source
   - Probe MOPS single-company income statement page:
     /mops/web/t164sb04
   - Submit historical quarter query to:
     /mops/web/ajax_t164sb04

3) Non-blocking verification
   - Verification metadata is additive.
   - Seeds remain the primary values if verification fails.

4) Q4 fix
   - Q1/Q2/Q3: verify against current-quarter EPS parsed from MOPS row layout.
   - Q4: verify against standalone Q4 EPS computed as:
       FY cumulative EPS - Q3 cumulative EPS

5) Robust parsing
   - No dependency on lxml/bs4.
   - Built-in HTMLParser-based table extraction.
   - Multiple fallbacks:
       a) table row parse
       b) regex over flattened text

Dependencies
------------
Required:
- requests
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v4.1-mops-q4-diff"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.8

DEFAULT_MOPS_BASE_URL = "https://mopsov.twse.com.tw/mops/web"
DEFAULT_STOCK_NO = "2330"
DEFAULT_EPS_TOLERANCE = 0.02

SOURCE_PRIORITY = {
    "tsmc_seed_record": 20,
    "tsmc_existing_record": 10,
}

QUARTER_NUM_TO_CN = {1: "第一", 2: "第二", 3: "第三", 4: "第四"}
QUARTER_CN_TO_NUM = {v: k for k, v in QUARTER_NUM_TO_CN.items()}
QUARTER_NUM_TO_EN_WORD = {1: "first", 2: "second", 3: "third", 4: "fourth"}

BOOTSTRAP_SEEDS: List[Dict[str, Any]] = [
    {
        "quarter": "2024Q4",
        "eps": 14.45,
        "source": "tsmc_seed_record",
        "as_of_date": "2025-01-16",
        "article_title": "台積公司2024年第四季每股盈餘新台幣14.45元",
        "article_url": "https://pr.tsmc.com/chinese/news/3201",
        "page_url": "https://pr.tsmc.com/chinese/news/3201",
        "quarter_end_date": "December 31, 2024",
        "quarter_word": "fourth",
    },
    {
        "quarter": "2025Q1",
        "eps": 13.94,
        "source": "tsmc_seed_record",
        "as_of_date": "2025-04-17",
        "article_title": "台積公司2025年第一季每股盈餘新台幣13.94元",
        "article_url": "https://pr.tsmc.com/chinese/news/3222",
        "page_url": "https://pr.tsmc.com/chinese/news/3222",
        "quarter_end_date": "March 31, 2025",
        "quarter_word": "first",
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
    },
]

FAILURE_CLASS_HTTP = "HTTP_ERROR"
FAILURE_CLASS_NOT_ENDED = "NOT_ENDED_YET"
FAILURE_CLASS_NOT_PUBLISHED = "LIKELY_NOT_PUBLISHED_YET"
FAILURE_CLASS_NOT_FOUND = "MOPS_NOT_FOUND"
FAILURE_CLASS_PARSE = "MOPS_PARSE_FAILED"
FAILURE_CLASS_MISMATCH = "EPS_MISMATCH"
FAILURE_CLASS_Q4_DEP = "Q4_DIFF_DEPENDENCY_FAILED"

BASIC_LABEL_PATTERNS = [
    re.compile(r"基本每股盈餘", re.I),
    re.compile(r"基本每股(?:淨利|損失)", re.I),
    re.compile(r"basic earnings per share", re.I),
    re.compile(r"basic earnings loss per share", re.I),
]

DILUTED_LABEL_PATTERNS = [
    re.compile(r"稀釋每股盈餘", re.I),
    re.compile(r"稀釋每股(?:淨利|損失)", re.I),
    re.compile(r"diluted earnings per share", re.I),
    re.compile(r"diluted earnings loss per share", re.I),
]

NO_DATA_PATTERNS = [
    re.compile(r"查無資料"),
    re.compile(r"沒有符合條件"),
    re.compile(r"無符合條件"),
    re.compile(r"no data", re.I),
]

DATE_PATTERNS = [
    re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"),
    re.compile(r"民國\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
]


class SimpleHTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self._in_table = False
        self._in_tr = False
        self._in_cell = False
        self._current_table: List[List[str]] = []
        self._current_row: List[str] = []
        self._current_cell_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif tag == "tr" and self._in_table:
            self._in_tr = True
            self._current_row = []
        elif tag in {"td", "th"} and self._in_tr:
            self._in_cell = True
            self._current_cell_chunks = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._in_cell:
            text = normalize_ws(unescape("".join(self._current_cell_chunks)))
            self._current_row.append(text)
            self._in_cell = False
            self._current_cell_chunks = []
        elif tag == "tr" and self._in_tr:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_tr = False
        elif tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = []
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell_chunks.append(data)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def quarter_sort_key(q: str) -> Tuple[int, int]:
    m = re.match(r"^(\d{4})Q([1-4])$", q)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


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
    y = int(m.group(1))
    q = int(m.group(2))
    return quarter_end_date_obj(y, q).strftime("%B %d, %Y")


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


def normalize_ws(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = s.replace("\u3000", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_text(s: Any) -> str:
    if s is None:
        return ""
    return normalize_ws(str(s))


def detect_source_priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 0)


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
    return requests.Session()


def mops_headers(page_url: str) -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": page_url,
        "Origin": re.sub(r"/mops/web.*$", "", page_url),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def http_post_text(
    session: requests.Session,
    url: str,
    data: Dict[str, str],
    timeout: int,
    retries: int,
    sleep_sec: float,
    *,
    headers: Dict[str, str],
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    last_err: Optional[str] = None
    last_status: Optional[int] = None

    for i in range(1, retries + 1):
        try:
            r = session.post(url, data=data, timeout=timeout, headers=headers)
            last_status = r.status_code
            r.raise_for_status()
            if not r.encoding:
                r.encoding = r.apparent_encoding or "utf-8"
            return r.text, r.status_code, None
        except Exception as e:
            last_err = str(e)
            if i < retries:
                time.sleep(sleep_sec * i)

    return None, last_status, last_err


def western_to_roc_year(year: int) -> int:
    return year - 1911


def safe_float_from_text(s: str) -> Optional[float]:
    s = normalize_text(s)
    if not s:
        return None

    s = s.replace(",", "")
    s = s.replace("(", "-").replace(")", "")
    s = s.replace("−", "-")
    s = s.replace("—", "-")
    s = s.replace("–", "-")

    if s in {"-", "--", "—", "–", "NA", "N/A"}:
        return None

    if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        try:
            return float(s)
        except Exception:
            return None
    return None


def detect_mops_no_data(html: str) -> bool:
    text = normalize_text(re.sub(r"<[^>]+>", " ", html, flags=re.S))
    return any(rx.search(text) for rx in NO_DATA_PATTERNS)


def parse_as_of_date_from_text(text: str) -> Optional[str]:
    text = normalize_text(text)

    for rx in DATE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        if rx.pattern.startswith("(\\d{4})"):
            y = int(m.group(1))
            mm = int(m.group(2))
            dd = int(m.group(3))
            return f"{y:04d}-{mm:02d}-{dd:02d}"
        roc_y = int(m.group(1))
        y = roc_y + 1911
        mm = int(m.group(2))
        dd = int(m.group(3))
        return f"{y:04d}-{mm:02d}-{dd:02d}"
    return None


def find_label_kind(cell_text: str) -> Optional[str]:
    for rx in BASIC_LABEL_PATTERNS:
        if rx.search(cell_text):
            return "basic"
    for rx in DILUTED_LABEL_PATTERNS:
        if rx.search(cell_text):
            return "diluted"
    return None


def extract_numeric_values_after_label(cells: List[str], label_idx: int) -> List[float]:
    out: List[float] = []
    for x in cells[label_idx + 1 :]:
        v = safe_float_from_text(x)
        if v is not None:
            out.append(v)
    return out


def summarize_eps_layout(numeric_values: List[float], quarter_num: int) -> Dict[str, Optional[float]]:
    """
    Heuristic mapping from row numeric sequence to metrics.

    Observed MOPS patterns:
    - Q1: [current, prior_year_current]
    - Q2/Q3: [current, prior_year_current, cumulative, prior_year_cumulative]
    - Q4: [full_year_cumulative, prior_year_full_year_cumulative]
    """
    current_eps: Optional[float] = None
    cumulative_eps: Optional[float] = None
    prior_current_eps: Optional[float] = None
    prior_cumulative_eps: Optional[float] = None
    direct_first_numeric: Optional[float] = numeric_values[0] if numeric_values else None

    if quarter_num == 1:
        if len(numeric_values) >= 1:
            current_eps = numeric_values[0]
            cumulative_eps = numeric_values[0]
        if len(numeric_values) >= 2:
            prior_current_eps = numeric_values[1]

    elif quarter_num in {2, 3}:
        if len(numeric_values) >= 1:
            current_eps = numeric_values[0]
        if len(numeric_values) >= 2:
            prior_current_eps = numeric_values[1]
        if len(numeric_values) >= 3:
            cumulative_eps = numeric_values[2]
        if len(numeric_values) >= 4:
            prior_cumulative_eps = numeric_values[3]

    elif quarter_num == 4:
        if len(numeric_values) >= 1:
            cumulative_eps = numeric_values[0]
        if len(numeric_values) >= 2:
            prior_cumulative_eps = numeric_values[1]

    return {
        "direct_first_numeric": direct_first_numeric,
        "current_eps": current_eps,
        "cumulative_eps": cumulative_eps,
        "prior_current_eps": prior_current_eps,
        "prior_cumulative_eps": prior_cumulative_eps,
    }


def parse_eps_from_tables(html: str, quarter_num: int) -> Dict[str, Any]:
    parser = SimpleHTMLTableParser()
    parser.feed(html)
    tables = parser.tables

    out: Dict[str, Any] = {
        "tables_found": len(tables),
        "basic_direct": None,
        "diluted_direct": None,
        "basic_current_eps": None,
        "diluted_current_eps": None,
        "basic_cumulative_eps": None,
        "diluted_cumulative_eps": None,
        "as_of_date": None,
        "row_hits": [],
        "table_preview": [],
    }

    flat_text = normalize_text(re.sub(r"<[^>]+>", " ", html, flags=re.S))
    out["as_of_date"] = parse_as_of_date_from_text(flat_text)

    preview_count = 0
    for t_idx, table in enumerate(tables):
        for r_idx, row in enumerate(table[:8]):
            if preview_count >= 12:
                break
            out["table_preview"].append(
                {
                    "table_index": t_idx,
                    "row_index": r_idx,
                    "cells": [normalize_text(x) for x in row[:8]],
                }
            )
            preview_count += 1
        if preview_count >= 12:
            break

    best_hit_by_kind: Dict[str, Dict[str, Any]] = {}

    for t_idx, table in enumerate(tables):
        for r_idx, row in enumerate(table):
            cells = [normalize_text(c) for c in row]
            if not any(cells):
                continue

            label_idx: Optional[int] = None
            label_kind: Optional[str] = None
            label_text: Optional[str] = None

            for idx, cell in enumerate(cells):
                kind = find_label_kind(cell)
                if kind:
                    label_idx = idx
                    label_kind = kind
                    label_text = cell
                    break

            if label_idx is None or label_kind is None:
                continue

            numeric_values = extract_numeric_values_after_label(cells, label_idx)
            layout = summarize_eps_layout(numeric_values, quarter_num)

            hit = {
                "table_index": t_idx,
                "row_index": r_idx,
                "label_kind": label_kind,
                "label_text": label_text,
                "row_cells": cells[:12],
                "numeric_values": numeric_values[:8],
                "derived_direct": layout["direct_first_numeric"],
                "derived_current_eps": layout["current_eps"],
                "derived_cumulative_eps": layout["cumulative_eps"],
                "derived_prior_current_eps": layout["prior_current_eps"],
                "derived_prior_cumulative_eps": layout["prior_cumulative_eps"],
            }
            out["row_hits"].append(hit)

            # Prefer the first row of each kind that actually has numeric values.
            if label_kind not in best_hit_by_kind and numeric_values:
                best_hit_by_kind[label_kind] = hit

    basic_hit = best_hit_by_kind.get("basic")
    diluted_hit = best_hit_by_kind.get("diluted")

    if basic_hit:
        out["basic_direct"] = basic_hit["derived_direct"]
        out["basic_current_eps"] = basic_hit["derived_current_eps"]
        out["basic_cumulative_eps"] = basic_hit["derived_cumulative_eps"]

    if diluted_hit:
        out["diluted_direct"] = diluted_hit["derived_direct"]
        out["diluted_current_eps"] = diluted_hit["derived_current_eps"]
        out["diluted_cumulative_eps"] = diluted_hit["derived_cumulative_eps"]

    # Regex fallback only for direct numeric after label.
    if out["basic_direct"] is None:
        m = re.search(r"基本每股盈餘[^0-9\-]{0,30}(-?\d+(?:\.\d+)?)", flat_text)
        if m:
            try:
                out["basic_direct"] = float(m.group(1))
            except Exception:
                pass

    if out["diluted_direct"] is None:
        m = re.search(r"稀釋每股盈餘[^0-9\-]{0,30}(-?\d+(?:\.\d+)?)", flat_text)
        if m:
            try:
                out["diluted_direct"] = float(m.group(1))
            except Exception:
                pass

    # If current/cumulative missing but direct exists, provide conservative fallback.
    if quarter_num == 1:
        if out["basic_current_eps"] is None and out["basic_direct"] is not None:
            out["basic_current_eps"] = out["basic_direct"]
            out["basic_cumulative_eps"] = out["basic_direct"]
        if out["diluted_current_eps"] is None and out["diluted_direct"] is not None:
            out["diluted_current_eps"] = out["diluted_direct"]
            out["diluted_cumulative_eps"] = out["diluted_direct"]

    return out


def pick_match_from_candidates(
    expected_eps: float,
    tolerance: float,
    candidates: List[Tuple[str, Optional[float]]],
) -> Tuple[Optional[float], Optional[str], str]:
    for method_name, value in candidates:
        if value is None:
            continue
        if abs(float(value) - expected_eps) <= tolerance:
            return float(value), method_name, f"exact_match_{method_name}"
    first_available = next(((name, val) for name, val in candidates if val is not None), None)
    if first_available is not None:
        return float(first_available[1]), first_available[0], f"mismatch_{first_available[0]}"
    return None, None, "no_eps_found"


def build_debug_quarter_entry(year: int, quarter_num: int) -> Dict[str, Any]:
    q = f"{year}Q{quarter_num}"
    return {
        "quarter": q,
        "publication_state": assess_publication_state(year, quarter_num, datetime.now().date()),
        "probe_source": "mops_single_company_income_statement",
        "request": None,
        "http_status": None,
        "fetch_ok": False,
        "tables_found": 0,
        "parsed_basic_eps": None,
        "parsed_diluted_eps": None,
        "parsed_basic_cumulative_eps": None,
        "parsed_diluted_cumulative_eps": None,
        "parsed_as_of_date": None,
        "q4_dependency_quarter": None,
        "q4_dependency_fetch_ok": False,
        "q4_dependency_http_status": None,
        "q4_dependency_basic_cumulative_eps": None,
        "q4_dependency_diluted_cumulative_eps": None,
        "computed_q4_basic_eps": None,
        "computed_q4_diluted_eps": None,
        "candidate_preview": [],
        "attempts": [],
        "discovered": False,
        "discovered_record_source": None,
        "status": "NOT_RUN",
    }


def choose_representative_failure(
    attempts: List[Dict[str, Any]]
) -> Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not attempts:
        return FAILURE_CLASS_PARSE, None, None

    first = attempts[0]
    last = attempts[-1]

    priority = [
        FAILURE_CLASS_HTTP,
        FAILURE_CLASS_NOT_FOUND,
        FAILURE_CLASS_Q4_DEP,
        FAILURE_CLASS_PARSE,
        FAILURE_CLASS_MISMATCH,
    ]
    for klass in priority:
        for a in attempts:
            if str(a.get("failure_class", "")) == klass:
                return klass, first, last

    return str(last.get("failure_class", FAILURE_CLASS_PARSE)), first, last


def update_record_with_verification(
    seed_record: Dict[str, Any],
    *,
    verified_eps: Optional[float],
    verified_method_detail: Optional[str],
    verified_as_of_date: Optional[str],
    probe_url: str,
    attempts: List[Dict[str, Any]],
    tolerance: float,
    parsed_basic_eps: Optional[float],
    parsed_diluted_eps: Optional[float],
    parsed_basic_cumulative_eps: Optional[float],
    parsed_diluted_cumulative_eps: Optional[float],
    computed_q4_basic_eps: Optional[float],
    computed_q4_diluted_eps: Optional[float],
    q4_dependency_quarter: Optional[str],
) -> Dict[str, Any]:
    out = copy.deepcopy(seed_record)
    out["fetched_at_utc"] = now_utc_iso()

    primary_failure_class, first_failure, last_failure = choose_representative_failure(attempts)

    if verified_eps is not None:
        out["reference_url_verified_this_run"] = True
        out["verification_status"] = "VERIFIED"
        out["verification_method"] = "mops_income_statement"
        out["verified_url"] = probe_url
        out["verified_eps"] = verified_eps
        out["verified_as_of_date"] = verified_as_of_date
        out["reference_source_type"] = "mops_income_statement"
        out["verification"] = {
            "status": "VERIFIED",
            "method": "mops_income_statement",
            "method_detail": verified_method_detail,
            "verified_url": probe_url,
            "verified_eps": verified_eps,
            "verified_quarter": seed_record.get("quarter"),
            "verified_as_of_date": verified_as_of_date,
            "parsed_basic_eps": parsed_basic_eps,
            "parsed_diluted_eps": parsed_diluted_eps,
            "parsed_basic_cumulative_eps": parsed_basic_cumulative_eps,
            "parsed_diluted_cumulative_eps": parsed_diluted_cumulative_eps,
            "computed_q4_basic_eps": computed_q4_basic_eps,
            "computed_q4_diluted_eps": computed_q4_diluted_eps,
            "q4_dependency_quarter": q4_dependency_quarter,
            "reason": "seed_eps_matched_mops_within_tolerance",
            "tolerance": tolerance,
            "attempted_at_utc": now_utc_iso(),
            "candidate_count_considered": len(attempts),
            "primary_failure_class": None,
            "first_failure": None,
            "last_failure": None,
        }
        return out

    out["reference_url_verified_this_run"] = False
    out["verification_status"] = "VERIFY_FAILED"
    out["verification_method"] = "mops_income_statement"
    out["verified_url"] = probe_url
    out["verified_eps"] = None
    out["verified_as_of_date"] = None
    out["verification"] = {
        "status": "VERIFY_FAILED",
        "method": "mops_income_statement",
        "method_detail": None,
        "verified_url": probe_url,
        "verified_eps": None,
        "verified_quarter": None,
        "verified_as_of_date": None,
        "parsed_basic_eps": parsed_basic_eps,
        "parsed_diluted_eps": parsed_diluted_eps,
        "parsed_basic_cumulative_eps": parsed_basic_cumulative_eps,
        "parsed_diluted_cumulative_eps": parsed_diluted_cumulative_eps,
        "computed_q4_basic_eps": computed_q4_basic_eps,
        "computed_q4_diluted_eps": computed_q4_diluted_eps,
        "q4_dependency_quarter": q4_dependency_quarter,
        "reason": primary_failure_class,
        "tolerance": tolerance,
        "attempted_at_utc": now_utc_iso(),
        "candidate_count_considered": len(attempts),
        "primary_failure_class": primary_failure_class,
        "first_failure": first_failure,
        "last_failure": last_failure,
    }
    return out


def statement_cache_key(stock_no: str, year: int, quarter_num: int) -> str:
    return f"{stock_no}:{year}Q{quarter_num}"


def fetch_and_parse_mops_statement(
    *,
    session: requests.Session,
    mops_base_url: str,
    stock_no: str,
    year: int,
    quarter_num: int,
    timeout: int,
    retries: int,
    sleep_sec: float,
    cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    key = statement_cache_key(stock_no, year, quarter_num)
    if key in cache:
        return copy.deepcopy(cache[key])

    roc_year = western_to_roc_year(year)
    page_url = f"{mops_base_url}/t164sb04"
    ajax_url = f"{mops_base_url}/ajax_t164sb04"

    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "TYPEK": "all",
        "isnew": "false",
        "co_id": stock_no,
        "year": str(roc_year),
        "season": f"{quarter_num:02d}",
    }

    result: Dict[str, Any] = {
        "quarter": f"{year}Q{quarter_num}",
        "page_url": page_url,
        "ajax_url": ajax_url,
        "payload": payload,
        "http_status": None,
        "fetch_ok": False,
        "failure_class": None,
        "failure_reason": None,
        "parsed": None,
    }

    html, http_status, err = http_post_text(
        session=session,
        url=ajax_url,
        data=payload,
        timeout=timeout,
        retries=retries,
        sleep_sec=sleep_sec,
        headers=mops_headers(page_url),
    )
    result["http_status"] = http_status

    if html is None:
        result["failure_class"] = FAILURE_CLASS_HTTP
        result["failure_reason"] = f"mops_fetch_failed:{err}"
        cache[key] = copy.deepcopy(result)
        return copy.deepcopy(result)

    result["fetch_ok"] = True

    if detect_mops_no_data(html):
        result["failure_class"] = FAILURE_CLASS_NOT_FOUND
        result["failure_reason"] = "mops_returned_no_data"
        cache[key] = copy.deepcopy(result)
        return copy.deepcopy(result)

    parsed = parse_eps_from_tables(html, quarter_num)
    result["parsed"] = parsed

    if (
        parsed.get("basic_direct") is None
        and parsed.get("diluted_direct") is None
        and parsed.get("basic_current_eps") is None
        and parsed.get("diluted_current_eps") is None
        and parsed.get("basic_cumulative_eps") is None
        and parsed.get("diluted_cumulative_eps") is None
    ):
        result["failure_class"] = FAILURE_CLASS_PARSE
        result["failure_reason"] = "eps_row_not_found_or_numeric_parse_failed"

    cache[key] = copy.deepcopy(result)
    return copy.deepcopy(result)


def probe_seed_with_mops(
    seed_record: Dict[str, Any],
    *,
    session: requests.Session,
    mops_base_url: str,
    stock_no: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    tolerance: float,
    notes: List[str],
    statement_cache: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    quarter = str(seed_record["quarter"])
    year = int(quarter[:4])
    qnum = int(quarter[-1])

    debug = build_debug_quarter_entry(year, qnum)
    pub_state = debug["publication_state"]

    page_url = f"{mops_base_url}/t164sb04"
    ajax_url = f"{mops_base_url}/ajax_t164sb04"

    if pub_state == "NOT_ENDED_YET":
        debug["status"] = "NOT_ENDED_YET"
        record = copy.deepcopy(seed_record)
        record["verification_status"] = "NOT_ENDED_YET"
        record["verification_method"] = "mops_income_statement"
        record["reference_url_verified_this_run"] = False
        record["verification"] = {
            "status": "NOT_ENDED_YET",
            "method": "mops_income_statement",
            "verified_url": ajax_url,
            "verified_eps": None,
            "verified_quarter": None,
            "verified_as_of_date": None,
            "reason": FAILURE_CLASS_NOT_ENDED,
            "attempted_at_utc": now_utc_iso(),
            "candidate_count_considered": 0,
            "primary_failure_class": FAILURE_CLASS_NOT_ENDED,
            "first_failure": None,
            "last_failure": None,
        }
        notes.append(f"{quarter}: skipped MOPS probe because quarter not ended yet")
        return record, debug

    if pub_state == "LIKELY_NOT_PUBLISHED_YET":
        debug["status"] = "LIKELY_NOT_PUBLISHED_YET"
        record = copy.deepcopy(seed_record)
        record["verification_status"] = "LIKELY_NOT_PUBLISHED_YET"
        record["verification_method"] = "mops_income_statement"
        record["reference_url_verified_this_run"] = False
        record["verification"] = {
            "status": "LIKELY_NOT_PUBLISHED_YET",
            "method": "mops_income_statement",
            "verified_url": ajax_url,
            "verified_eps": None,
            "verified_quarter": None,
            "verified_as_of_date": None,
            "reason": FAILURE_CLASS_NOT_PUBLISHED,
            "attempted_at_utc": now_utc_iso(),
            "candidate_count_considered": 0,
            "primary_failure_class": FAILURE_CLASS_NOT_PUBLISHED,
            "first_failure": None,
            "last_failure": None,
        }
        notes.append(f"{quarter}: skipped MOPS probe because publication likely not ready yet")
        return record, debug

    attempts: List[Dict[str, Any]] = []

    main_stmt = fetch_and_parse_mops_statement(
        session=session,
        mops_base_url=mops_base_url,
        stock_no=stock_no,
        year=year,
        quarter_num=qnum,
        timeout=timeout,
        retries=retries,
        sleep_sec=sleep_sec,
        cache=statement_cache,
    )

    debug["request"] = {
        "page_url": main_stmt["page_url"],
        "ajax_url": main_stmt["ajax_url"],
        "payload": main_stmt["payload"],
    }
    debug["http_status"] = main_stmt.get("http_status")
    debug["fetch_ok"] = bool(main_stmt.get("fetch_ok"))

    if main_stmt.get("failure_class") == FAILURE_CLASS_HTTP:
        debug["status"] = "MOPS_FETCH_FAILED"
        attempts.append(
            {
                "probe": "mops_fetch",
                "failure_class": FAILURE_CLASS_HTTP,
                "reason": main_stmt.get("failure_reason"),
                "url": main_stmt.get("ajax_url"),
                "payload": main_stmt.get("payload"),
                "http_status": main_stmt.get("http_status"),
            }
        )
        debug["attempts"] = attempts
        record = update_record_with_verification(
            seed_record,
            verified_eps=None,
            verified_method_detail=None,
            verified_as_of_date=None,
            probe_url=ajax_url,
            attempts=attempts,
            tolerance=tolerance,
            parsed_basic_eps=None,
            parsed_diluted_eps=None,
            parsed_basic_cumulative_eps=None,
            parsed_diluted_cumulative_eps=None,
            computed_q4_basic_eps=None,
            computed_q4_diluted_eps=None,
            q4_dependency_quarter=None,
        )
        notes.append(f"{quarter}: MOPS fetch failed | err={main_stmt.get('failure_reason')}")
        return record, debug

    if main_stmt.get("failure_class") == FAILURE_CLASS_NOT_FOUND:
        debug["status"] = "MOPS_NOT_FOUND"
        attempts.append(
            {
                "probe": "mops_no_data_check",
                "failure_class": FAILURE_CLASS_NOT_FOUND,
                "reason": main_stmt.get("failure_reason"),
                "url": main_stmt.get("ajax_url"),
                "http_status": main_stmt.get("http_status"),
            }
        )
        debug["attempts"] = attempts
        record = update_record_with_verification(
            seed_record,
            verified_eps=None,
            verified_method_detail=None,
            verified_as_of_date=None,
            probe_url=ajax_url,
            attempts=attempts,
            tolerance=tolerance,
            parsed_basic_eps=None,
            parsed_diluted_eps=None,
            parsed_basic_cumulative_eps=None,
            parsed_diluted_cumulative_eps=None,
            computed_q4_basic_eps=None,
            computed_q4_diluted_eps=None,
            q4_dependency_quarter=None,
        )
        notes.append(f"{quarter}: MOPS returned no data")
        return record, debug

    parsed = main_stmt.get("parsed") or {}
    debug["tables_found"] = parsed.get("tables_found", 0)
    debug["parsed_basic_eps"] = parsed.get("basic_current_eps") or parsed.get("basic_direct")
    debug["parsed_diluted_eps"] = parsed.get("diluted_current_eps") or parsed.get("diluted_direct")
    debug["parsed_basic_cumulative_eps"] = parsed.get("basic_cumulative_eps")
    debug["parsed_diluted_cumulative_eps"] = parsed.get("diluted_cumulative_eps")
    debug["parsed_as_of_date"] = parsed.get("as_of_date")
    debug["candidate_preview"] = parsed.get("row_hits", [])[:8]

    if main_stmt.get("failure_class") == FAILURE_CLASS_PARSE:
        debug["status"] = "MOPS_PARSE_FAILED"
        attempts.append(
            {
                "probe": "mops_parse",
                "failure_class": FAILURE_CLASS_PARSE,
                "reason": main_stmt.get("failure_reason"),
                "tables_found": parsed.get("tables_found"),
                "as_of_date": parsed.get("as_of_date"),
            }
        )
        debug["attempts"] = attempts
        record = update_record_with_verification(
            seed_record,
            verified_eps=None,
            verified_method_detail=None,
            verified_as_of_date=None,
            probe_url=ajax_url,
            attempts=attempts,
            tolerance=tolerance,
            parsed_basic_eps=debug["parsed_basic_eps"],
            parsed_diluted_eps=debug["parsed_diluted_eps"],
            parsed_basic_cumulative_eps=debug["parsed_basic_cumulative_eps"],
            parsed_diluted_cumulative_eps=debug["parsed_diluted_cumulative_eps"],
            computed_q4_basic_eps=None,
            computed_q4_diluted_eps=None,
            q4_dependency_quarter=None,
        )
        notes.append(f"{quarter}: MOPS parse failed | no EPS row found")
        return record, debug

    expected_eps = float(seed_record["eps"])
    matched_eps: Optional[float] = None
    matched_method: Optional[str] = None
    match_reason: str = "no_eps_found"
    computed_q4_basic_eps: Optional[float] = None
    computed_q4_diluted_eps: Optional[float] = None
    q4_dependency_quarter: Optional[str] = None

    if qnum in {1, 2, 3}:
        matched_eps, matched_method, match_reason = pick_match_from_candidates(
            expected_eps=expected_eps,
            tolerance=tolerance,
            candidates=[
                ("diluted_eps", parsed.get("diluted_current_eps")),
                ("basic_eps", parsed.get("basic_current_eps")),
                ("diluted_direct", parsed.get("diluted_direct")),
                ("basic_direct", parsed.get("basic_direct")),
            ],
        )

    else:
        # Q4: standalone EPS = FY cumulative - Q3 cumulative
        q4_dependency_quarter = f"{year}Q3"
        debug["q4_dependency_quarter"] = q4_dependency_quarter

        q3_stmt = fetch_and_parse_mops_statement(
            session=session,
            mops_base_url=mops_base_url,
            stock_no=stock_no,
            year=year,
            quarter_num=3,
            timeout=timeout,
            retries=retries,
            sleep_sec=sleep_sec,
            cache=statement_cache,
        )

        debug["q4_dependency_http_status"] = q3_stmt.get("http_status")
        debug["q4_dependency_fetch_ok"] = bool(q3_stmt.get("fetch_ok"))

        q3_parsed = q3_stmt.get("parsed") or {}
        q3_basic_cum = q3_parsed.get("basic_cumulative_eps")
        q3_diluted_cum = q3_parsed.get("diluted_cumulative_eps")

        debug["q4_dependency_basic_cumulative_eps"] = q3_basic_cum
        debug["q4_dependency_diluted_cumulative_eps"] = q3_diluted_cum

        fy_basic_cum = parsed.get("basic_cumulative_eps")
        fy_diluted_cum = parsed.get("diluted_cumulative_eps")

        if fy_basic_cum is not None and q3_basic_cum is not None:
            computed_q4_basic_eps = round(float(fy_basic_cum) - float(q3_basic_cum), 2)
        if fy_diluted_cum is not None and q3_diluted_cum is not None:
            computed_q4_diluted_eps = round(float(fy_diluted_cum) - float(q3_diluted_cum), 2)

        debug["computed_q4_basic_eps"] = computed_q4_basic_eps
        debug["computed_q4_diluted_eps"] = computed_q4_diluted_eps

        if q3_stmt.get("failure_class") in {FAILURE_CLASS_HTTP, FAILURE_CLASS_NOT_FOUND, FAILURE_CLASS_PARSE}:
            debug["status"] = "Q4_DIFF_DEPENDENCY_FAILED"
            attempts.append(
                {
                    "probe": "q4_diff_dependency_q3",
                    "failure_class": FAILURE_CLASS_Q4_DEP,
                    "reason": "q3_dependency_fetch_or_parse_failed",
                    "dependency_quarter": q4_dependency_quarter,
                    "dependency_failure_class": q3_stmt.get("failure_class"),
                    "dependency_failure_reason": q3_stmt.get("failure_reason"),
                    "dependency_http_status": q3_stmt.get("http_status"),
                }
            )
            debug["attempts"] = attempts
            record = update_record_with_verification(
                seed_record,
                verified_eps=None,
                verified_method_detail=None,
                verified_as_of_date=parsed.get("as_of_date"),
                probe_url=ajax_url,
                attempts=attempts,
                tolerance=tolerance,
                parsed_basic_eps=parsed.get("basic_direct"),
                parsed_diluted_eps=parsed.get("diluted_direct"),
                parsed_basic_cumulative_eps=fy_basic_cum,
                parsed_diluted_cumulative_eps=fy_diluted_cum,
                computed_q4_basic_eps=computed_q4_basic_eps,
                computed_q4_diluted_eps=computed_q4_diluted_eps,
                q4_dependency_quarter=q4_dependency_quarter,
            )
            notes.append(
                f"{quarter}: Q4_DIFF_DEPENDENCY_FAILED | "
                f"Q3 dependency failure_class={q3_stmt.get('failure_class')}"
            )
            return record, debug

        matched_eps, matched_method, match_reason = pick_match_from_candidates(
            expected_eps=expected_eps,
            tolerance=tolerance,
            candidates=[
                ("q4_diluted_diff", computed_q4_diluted_eps),
                ("q4_basic_diff", computed_q4_basic_eps),
            ],
        )

    if matched_eps is not None and match_reason.startswith("exact_match"):
        attempts.append(
            {
                "probe": "mops_eps_match",
                "failure_class": None,
                "reason": match_reason,
                "matched_method": matched_method,
                "matched_eps": matched_eps,
                "parsed_basic_eps": debug["parsed_basic_eps"],
                "parsed_diluted_eps": debug["parsed_diluted_eps"],
                "parsed_basic_cumulative_eps": debug["parsed_basic_cumulative_eps"],
                "parsed_diluted_cumulative_eps": debug["parsed_diluted_cumulative_eps"],
                "computed_q4_basic_eps": computed_q4_basic_eps,
                "computed_q4_diluted_eps": computed_q4_diluted_eps,
                "q4_dependency_quarter": q4_dependency_quarter,
                "as_of_date": parsed.get("as_of_date"),
            }
        )
        debug["attempts"] = attempts
        debug["discovered"] = True
        debug["discovered_record_source"] = "mops_income_statement"
        debug["status"] = "VERIFIED"

        record = update_record_with_verification(
            seed_record,
            verified_eps=matched_eps,
            verified_method_detail=matched_method,
            verified_as_of_date=parsed.get("as_of_date"),
            probe_url=ajax_url,
            attempts=attempts,
            tolerance=tolerance,
            parsed_basic_eps=debug["parsed_basic_eps"],
            parsed_diluted_eps=debug["parsed_diluted_eps"],
            parsed_basic_cumulative_eps=debug["parsed_basic_cumulative_eps"],
            parsed_diluted_cumulative_eps=debug["parsed_diluted_cumulative_eps"],
            computed_q4_basic_eps=computed_q4_basic_eps,
            computed_q4_diluted_eps=computed_q4_diluted_eps,
            q4_dependency_quarter=q4_dependency_quarter,
        )

        if qnum == 4:
            notes.append(
                f"{quarter}: VERIFIED via MOPS Q4 diff | matched_method={matched_method} "
                f"fy_basic={parsed.get('basic_cumulative_eps')} fy_diluted={parsed.get('diluted_cumulative_eps')} "
                f"q3_basic_cum={debug.get('q4_dependency_basic_cumulative_eps')} "
                f"q3_diluted_cum={debug.get('q4_dependency_diluted_cumulative_eps')} "
                f"q4_basic={computed_q4_basic_eps} q4_diluted={computed_q4_diluted_eps}"
            )
        else:
            notes.append(
                f"{quarter}: VERIFIED via MOPS | matched_method={matched_method} "
                f"current_basic={parsed.get('basic_current_eps')} current_diluted={parsed.get('diluted_current_eps')}"
            )
        return record, debug

    # Failure path
    debug["status"] = "EPS_MISMATCH"
    attempts.append(
        {
            "probe": "mops_eps_compare",
            "failure_class": FAILURE_CLASS_MISMATCH,
            "reason": "mops_eps_parsed_but_does_not_match_seed",
            "expected_eps": seed_record["eps"],
            "parsed_basic_eps": debug["parsed_basic_eps"],
            "parsed_diluted_eps": debug["parsed_diluted_eps"],
            "parsed_basic_cumulative_eps": debug["parsed_basic_cumulative_eps"],
            "parsed_diluted_cumulative_eps": debug["parsed_diluted_cumulative_eps"],
            "computed_q4_basic_eps": computed_q4_basic_eps,
            "computed_q4_diluted_eps": computed_q4_diluted_eps,
            "q4_dependency_quarter": q4_dependency_quarter,
            "as_of_date": parsed.get("as_of_date"),
        }
    )
    debug["attempts"] = attempts

    record = update_record_with_verification(
        seed_record,
        verified_eps=None,
        verified_method_detail=None,
        verified_as_of_date=parsed.get("as_of_date"),
        probe_url=ajax_url,
        attempts=attempts,
        tolerance=tolerance,
        parsed_basic_eps=debug["parsed_basic_eps"],
        parsed_diluted_eps=debug["parsed_diluted_eps"],
        parsed_basic_cumulative_eps=debug["parsed_basic_cumulative_eps"],
        parsed_diluted_cumulative_eps=debug["parsed_diluted_cumulative_eps"],
        computed_q4_basic_eps=computed_q4_basic_eps,
        computed_q4_diluted_eps=computed_q4_diluted_eps,
        q4_dependency_quarter=q4_dependency_quarter,
    )

    if qnum == 4:
        notes.append(
            f"{quarter}: EPS_MISMATCH via MOPS Q4 diff | expected={seed_record['eps']} "
            f"q4_basic={computed_q4_basic_eps} q4_diluted={computed_q4_diluted_eps} "
            f"fy_basic={parsed.get('basic_cumulative_eps')} fy_diluted={parsed.get('diluted_cumulative_eps')}"
        )
    else:
        notes.append(
            f"{quarter}: EPS_MISMATCH via MOPS | expected={seed_record['eps']} "
            f"current_basic={parsed.get('basic_current_eps')} current_diluted={parsed.get('diluted_current_eps')}"
        )
    return record, debug


def choose_better_record(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    old_verified = bool(old.get("reference_url_verified_this_run", False))
    new_verified = bool(new.get("reference_url_verified_this_run", False))
    if new_verified and not old_verified:
        return new
    if old_verified and not new_verified:
        return old

    old_status = str(old.get("verification_status", "") or "")
    new_status = str(new.get("verification_status", "") or "")
    if new_status == "VERIFIED" and old_status != "VERIFIED":
        return new
    if old_status == "VERIFIED" and new_status != "VERIFIED":
        return old

    old_pri = int(old.get("source_priority", detect_source_priority(str(old.get("source", "")))))
    new_pri = int(new.get("source_priority", detect_source_priority(str(new.get("source", "")))))
    if new_pri > old_pri:
        return new
    if new_pri < old_pri:
        return old

    new_fetched = str(new.get("fetched_at_utc", "") or "")
    old_fetched = str(old.get("fetched_at_utc", "") or "")
    if new_fetched >= old_fetched:
        return new
    return old


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


def build_output(
    merged_quarters: List[Dict[str, Any]],
    entry_pages: List[str],
    notes: List[str],
    discovery_debug: List[Dict[str, Any]],
) -> Dict[str, Any]:
    verified_count = sum(1 for x in merged_quarters if x.get("verification_status") == "VERIFIED")
    failed_count = sum(1 for x in merged_quarters if x.get("verification_status") == "VERIFY_FAILED")
    skipped_count = sum(
        1
        for x in merged_quarters
        if x.get("verification_status") in {"NOT_ENDED_YET", "LIKELY_NOT_PUBLISHED_YET"}
    )
    not_found_count = sum(
        1
        for x in merged_quarters
        if str((x.get("verification") or {}).get("primary_failure_class", "")) == FAILURE_CLASS_NOT_FOUND
    )
    parse_failed_count = sum(
        1
        for x in merged_quarters
        if str((x.get("verification") or {}).get("primary_failure_class", "")) == FAILURE_CLASS_PARSE
    )
    mismatch_count = sum(
        1
        for x in merged_quarters
        if str((x.get("verification") or {}).get("primary_failure_class", "")) == FAILURE_CLASS_MISMATCH
    )
    q4_dep_failed_count = sum(
        1
        for x in merged_quarters
        if str((x.get("verification") or {}).get("primary_failure_class", "")) == FAILURE_CLASS_Q4_DEP
    )
    seed_count = sum(1 for x in merged_quarters if x.get("data_origin") == "bootstrap_seed")

    return {
        "meta": {
            "generated_at_utc": now_utc_iso(),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "source_policy": "seed_first_plus_official_mops_single_company_income_statement_probe_non_blocking_q4_diff",
            "entry_pages": entry_pages,
            "notes": notes,
            "counts": {
                "verified_count": verified_count,
                "verify_failed_count": failed_count,
                "verify_skipped_count": skipped_count,
                "mops_not_found_count": not_found_count,
                "mops_parse_failed_count": parse_failed_count,
                "eps_mismatch_count": mismatch_count,
                "q4_dependency_failed_count": q4_dep_failed_count,
                "bootstrap_seed_count": seed_count,
                "total_quarters": len(merged_quarters),
            },
            "optional_features": {
                "mops_probe_enabled": True,
                "single_company_mode": True,
                "q4_diff_enabled": True,
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
        description="Update TSMC quarterly EPS tracker (seed-first + optional MOPS probe + Q4 diff)."
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output tracker JSON path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    parser.add_argument("--sleep-sec", type=float, default=DEFAULT_SLEEP, help="Sleep between retries")
    parser.add_argument("--start-year", type=int, default=datetime.now().year, help="Start year to scan")
    parser.add_argument("--end-year", type=int, default=max(datetime.now().year - 5, 2024), help="End year to scan")
    parser.add_argument(
        "--mops-base-url",
        default=DEFAULT_MOPS_BASE_URL,
        help="MOPS base URL, e.g. https://mopsov.twse.com.tw/mops/web",
    )
    parser.add_argument("--stock-no", default=DEFAULT_STOCK_NO, help="Stock number, default 2330")
    parser.add_argument(
        "--eps-tolerance",
        type=float,
        default=DEFAULT_EPS_TOLERANCE,
        help="Absolute EPS tolerance for MOPS verification match",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session()
    existing = load_existing_tracker(out_path)
    existing_quarters = existing.get("quarters", [])

    notes: List[str] = []
    discovery_debug: List[Dict[str, Any]] = []
    fetched: List[Dict[str, Any]] = []
    statement_cache: Dict[str, Dict[str, Any]] = {}

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
    notes.append("probe mode=mops_single_company_income_statement")
    notes.append("q4_rule=use_fy_cumulative_minus_q3_cumulative")
    notes.append(f"mops_base_url={args.mops_base_url}")
    notes.append(f"stock_no={args.stock_no}")
    notes.append(f"eps_tolerance={args.eps_tolerance}")

    entry_pages = [
        f"{args.mops_base_url}/t164sb04",
        f"{args.mops_base_url}/ajax_t164sb04",
    ]

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
            updated, dbg = probe_seed_with_mops(
                seed_map[quarter],
                session=session,
                mops_base_url=args.mops_base_url,
                stock_no=args.stock_no,
                timeout=args.timeout,
                retries=args.retries,
                sleep_sec=args.sleep_sec,
                tolerance=args.eps_tolerance,
                notes=notes,
                statement_cache=statement_cache,
            )
            fetched.append(updated)
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

    verified_count = sum(1 for x in merged_quarters if x.get("verification_status") == "VERIFIED")
    failed_count = sum(1 for x in merged_quarters if x.get("verification_status") == "VERIFY_FAILED")
    skipped_count = sum(
        1
        for x in merged_quarters
        if x.get("verification_status") in {"NOT_ENDED_YET", "LIKELY_NOT_PUBLISHED_YET"}
    )
    print(f"[INFO] verified_count={verified_count}")
    print(f"[INFO] verify_failed_count={failed_count}")
    print(f"[INFO] verify_skipped_count={skipped_count}")

    for q in merged_quarters:
        print(
            f"  - {q.get('quarter')}: EPS={q.get('eps')} | "
            f"as_of={q.get('as_of_date')} | source={q.get('source')} | "
            f"origin={q.get('data_origin')} | pri={q.get('source_priority')} | "
            f"verified_this_run={q.get('reference_url_verified_this_run')} | "
            f"verification_status={q.get('verification_status')} | "
            f"verification_method={q.get('verification_method')} | "
            f"verified_url={q.get('verified_url')} | "
            f"verified_eps={q.get('verified_eps')}"
        )

    print("[INFO] discovery_debug summary:")
    for d in discovery_debug:
        print(
            f"  - {d.get('quarter')}: status={d.get('status')} | "
            f"pub_state={d.get('publication_state')} | "
            f"http_status={d.get('http_status')} | "
            f"tables_found={d.get('tables_found')} | "
            f"parsed_basic_eps={d.get('parsed_basic_eps')} | "
            f"parsed_diluted_eps={d.get('parsed_diluted_eps')} | "
            f"parsed_basic_cumulative_eps={d.get('parsed_basic_cumulative_eps')} | "
            f"parsed_diluted_cumulative_eps={d.get('parsed_diluted_cumulative_eps')} | "
            f"computed_q4_basic_eps={d.get('computed_q4_basic_eps')} | "
            f"computed_q4_diluted_eps={d.get('computed_q4_diluted_eps')} | "
            f"attempts={len(d.get('attempts', []))} | "
            f"discovered={d.get('discovered')}"
        )

    print("[INFO] notes:")
    for n in notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()