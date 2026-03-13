#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v3.1)

Design goals
------------
1) Seed-first
   - Quarterly EPS values come from manually maintained seeds.
   - The script no longer depends on front-end pages or sec.gov Archives HTML.

2) Optional XBRL probe (non-blocking)
   - Probe only data.sec.gov XBRL companyfacts JSON.
   - Never fail the whole run if probing fails.
   - Verification is additive metadata, not a prerequisite for output.

3) Auditability
   - Explicit verification status.
   - Explicit primary failure class / first failure / last failure.
   - Avoid misleading "verification_method" caused by the final failed attempt.

Dependencies
------------
Required:
- requests

No PDF / HTML parsing from blocked front-end pages is attempted in this version.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v3.1"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.5

# TSMC
DEFAULT_SEC_CIK = "0001046179"
DEFAULT_SEC_USER_AGENT = "Joseph Chou joseph@example.com"
DEFAULT_XBRL_TOLERANCE = 0.02  # EPS comparison tolerance

SOURCE_PRIORITY = {
    "tsmc_seed_record": 20,
    "tsmc_existing_record": 10,
}

QUARTER_NUM_TO_CN = {1: "第一", 2: "第二", 3: "第三", 4: "第四"}
QUARTER_CN_TO_NUM = {v: k for k, v in QUARTER_NUM_TO_CN.items()}
QUARTER_NUM_TO_EN_WORD = {1: "first", 2: "second", 3: "third", 4: "fourth"}

# --------------------------------------------------------------------
# Seed-first data
# --------------------------------------------------------------------
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

# Preferred concept names first; if absent, we fall back to heuristic scan.
DIRECT_EPS_CONCEPTS = [
    ("ifrs-full", "BasicAndDilutedEarningsPerShare"),
    ("ifrs-full", "DilutedEarningsPerShare"),
    ("ifrs-full", "BasicEarningsPerShare"),
    ("us-gaap", "EarningsPerShareDiluted"),
    ("us-gaap", "EarningsPerShareBasicAndDiluted"),
    ("us-gaap", "EarningsPerShareBasic"),
]

FAILURE_CLASS_HTTP = "HTTP_ERROR"
FAILURE_CLASS_NO_DATA = "NO_XBRL_DATA"
FAILURE_CLASS_NO_CANDIDATE = "NO_CANDIDATE"
FAILURE_CLASS_MISMATCH = "BEST_CANDIDATE_MISMATCH"
FAILURE_CLASS_NOT_ENDED = "NOT_ENDED_YET"
FAILURE_CLASS_NOT_PUBLISHED = "LIKELY_NOT_PUBLISHED_YET"


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
    s = requests.Session()
    return s


def sec_headers(sec_user_agent: str) -> Dict[str, str]:
    return {
        "User-Agent": sec_user_agent,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.8",
        "Referer": "https://www.sec.gov/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def http_get_json(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    sleep_sec: float,
    *,
    headers: Dict[str, str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    last_err: Optional[str] = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            return r.json(), None
        except Exception as e:
            last_err = str(e)
            if i < retries:
                time.sleep(sleep_sec * i)
    return None, last_err


def sec_companyfacts_url(cik: str) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def unit_preference_score(unit_key: str) -> int:
    u = (unit_key or "").lower()
    score = 0
    if "twd" in u:
        score += 50
    if "usd" in u:
        score -= 25
    if "share" in u:
        score += 10
    if u == "pure":
        score -= 30
    return score


def concept_preference_score(taxonomy: str, concept: str) -> int:
    c = concept.lower()
    score = 0
    if "basicanddiluted" in c:
        score += 25
    if "diluted" in c:
        score += 20
    elif "basic" in c:
        score += 5
    if "earnings" in c and "share" in c:
        score += 15
    if taxonomy == "ifrs-full":
        score += 5
    return score


def is_eps_concept_name(concept: str) -> bool:
    c = concept.lower()

    negative_tokens = [
        "weightedaverage",
        "sharesoutstanding",
        "numberofshares",
        "sharecapital",
        "ordinaryshares",
        "authorizedshares",
        "issuedshares",
    ]
    if any(tok in c for tok in negative_tokens):
        return False

    if c in {
        "basicanddilutedearningspershare",
        "dilutedearningspershare",
        "basicearningspershare",
        "earningspersharediluted",
        "earningspersharebasicanddiluted",
        "earningspersharebasic",
    }:
        return True

    return ("earnings" in c and "share" in c) or ("eps" in c and "share" in c)


def safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def infer_quarter_from_fact(
    fact: Dict[str, Any],
    *,
    expected_quarter: str,
) -> Tuple[Optional[str], str]:
    """
    Returns:
      (quarter_label_or_none, derivation_method)
    """
    fy = fact.get("fy")
    fp = str(fact.get("fp", "") or "").upper().strip()

    if fy is not None and fp in {"Q1", "Q2", "Q3", "Q4"}:
        try:
            return f"{int(fy)}{fp}", "fy_fp"
        except Exception:
            pass

    end_s = str(fact.get("end", "") or "")
    end_d = parse_iso_date(end_s)
    if end_d is not None:
        for qn in (1, 2, 3, 4):
            q_label = f"{end_d.year}Q{qn}"
            if end_d == quarter_end_date_obj(end_d.year, qn):
                return q_label, "end_date"
    return None, "unknown"


def candidate_score(
    candidate: Dict[str, Any],
    *,
    expected_quarter: str,
    expected_as_of_date: str,
) -> int:
    score = 0

    if candidate.get("derived_quarter") == expected_quarter:
        score += 100
    elif candidate.get("derived_quarter") is not None:
        score -= 60

    filed_s = str(candidate.get("filed", "") or "")
    filed_d = parse_iso_date(filed_s)
    asof_d = parse_iso_date(expected_as_of_date)
    if filed_d is not None and asof_d is not None:
        delta = abs((filed_d - asof_d).days)
        score += max(0, 25 - min(delta, 25))

    form = str(candidate.get("form", "") or "").upper()
    if form == "6-K":
        score += 25
    elif form in {"20-F", "40-F"}:
        score += 8
    elif form in {"10-Q", "10-K"}:
        score += 5

    score += unit_preference_score(str(candidate.get("unit_key", "") or ""))
    score += concept_preference_score(
        str(candidate.get("taxonomy", "") or ""),
        str(candidate.get("concept", "") or ""),
    )

    if str(candidate.get("quarter_derivation", "")) == "fy_fp":
        score += 8
    elif str(candidate.get("quarter_derivation", "")) == "end_date":
        score += 3

    return score


def collect_xbrl_eps_candidates(
    companyfacts: Dict[str, Any],
    *,
    expected_quarter: str,
    expected_as_of_date: str,
) -> List[Dict[str, Any]]:
    facts_root = companyfacts.get("facts", {})
    if not isinstance(facts_root, dict):
        return []

    candidates: List[Dict[str, Any]] = []

    # 1) direct preferred concepts first
    preferred_pairs = set(DIRECT_EPS_CONCEPTS)

    for taxonomy, concepts in facts_root.items():
        if not isinstance(concepts, dict):
            continue

        for concept, meta in concepts.items():
            if not isinstance(meta, dict):
                continue

            pair = (taxonomy, concept)
            if pair not in preferred_pairs and not is_eps_concept_name(concept):
                continue

            units = meta.get("units", {})
            if not isinstance(units, dict):
                continue

            for unit_key, rows in units.items():
                if not isinstance(rows, list):
                    continue

                for row in rows:
                    if not isinstance(row, dict):
                        continue

                    val = safe_float(row.get("val"))
                    if val is None:
                        continue

                    derived_quarter, derivation = infer_quarter_from_fact(
                        row,
                        expected_quarter=expected_quarter,
                    )

                    cand = {
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "label": meta.get("label"),
                        "description": meta.get("description"),
                        "unit_key": unit_key,
                        "value": val,
                        "fy": row.get("fy"),
                        "fp": row.get("fp"),
                        "form": row.get("form"),
                        "filed": row.get("filed"),
                        "end": row.get("end"),
                        "frame": row.get("frame"),
                        "accn": row.get("accn"),
                        "derived_quarter": derived_quarter,
                        "quarter_derivation": derivation,
                    }
                    cand["score"] = candidate_score(
                        cand,
                        expected_quarter=expected_quarter,
                        expected_as_of_date=expected_as_of_date,
                    )
                    candidates.append(cand)

    candidates.sort(
        key=lambda x: (
            -int(x.get("score", 0)),
            str(x.get("filed", "")),
            str(x.get("taxonomy", "")),
            str(x.get("concept", "")),
        )
    )
    return candidates


def pick_best_xbrl_candidate(
    candidates: List[Dict[str, Any]],
    *,
    expected_quarter: str,
    expected_eps: float,
    tolerance: float,
) -> Tuple[Optional[Dict[str, Any]], str]:
    if not candidates:
        return None, "no_candidate"

    # Prefer exact quarter candidates first
    exact_quarter = [c for c in candidates if c.get("derived_quarter") == expected_quarter]
    pool = exact_quarter if exact_quarter else candidates

    best = pool[0]
    if abs(float(best["value"]) - float(expected_eps)) <= tolerance and best.get("derived_quarter") == expected_quarter:
        return best, "exact_match"

    return best, "best_candidate_mismatch"


def build_debug_quarter_entry(year: int, quarter_num: int) -> Dict[str, Any]:
    q = f"{year}Q{quarter_num}"
    return {
        "quarter": q,
        "publication_state": assess_publication_state(year, quarter_num, datetime.now().date()),
        "probe_source": "sec_companyfacts_xbrl",
        "candidate_count": 0,
        "candidate_preview": [],
        "attempts": [],
        "discovered": False,
        "discovered_record_source": None,
        "status": "NOT_RUN",
    }


def summarize_candidate(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "taxonomy": c.get("taxonomy"),
        "concept": c.get("concept"),
        "unit_key": c.get("unit_key"),
        "value": c.get("value"),
        "fy": c.get("fy"),
        "fp": c.get("fp"),
        "form": c.get("form"),
        "filed": c.get("filed"),
        "end": c.get("end"),
        "derived_quarter": c.get("derived_quarter"),
        "quarter_derivation": c.get("quarter_derivation"),
        "score": c.get("score"),
        "accn": c.get("accn"),
    }


def choose_representative_failure(attempts: List[Dict[str, Any]]) -> Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not attempts:
        return FAILURE_CLASS_NO_CANDIDATE, None, None

    first = attempts[0]
    last = attempts[-1]

    # prioritize mismatch if we had actual candidates but mismatch
    for a in attempts:
        if str(a.get("failure_class", "")) == FAILURE_CLASS_MISMATCH:
            return FAILURE_CLASS_MISMATCH, first, last

    # then any HTTP-like issue
    for a in attempts:
        if str(a.get("failure_class", "")) == FAILURE_CLASS_HTTP:
            return FAILURE_CLASS_HTTP, first, last

    return str(last.get("failure_class", FAILURE_CLASS_NO_CANDIDATE)), first, last


def update_record_with_verification(
    seed_record: Dict[str, Any],
    *,
    verified_candidate: Optional[Dict[str, Any]],
    companyfacts_url: str,
    attempts: List[Dict[str, Any]],
    tolerance: float,
) -> Dict[str, Any]:
    out = copy.deepcopy(seed_record)
    out["fetched_at_utc"] = now_utc_iso()

    primary_failure_class, first_failure, last_failure = choose_representative_failure(attempts)

    if verified_candidate is not None:
        out["reference_url_verified_this_run"] = True
        out["verification_status"] = "VERIFIED"
        out["verification_method"] = "xbrl_companyfacts"
        out["verified_url"] = companyfacts_url
        out["verified_eps"] = verified_candidate.get("value")
        out["verified_as_of_date"] = verified_candidate.get("filed")
        out["reference_source_type"] = "sec_companyfacts_xbrl"
        out["verification"] = {
            "status": "VERIFIED",
            "method": "xbrl_companyfacts",
            "verified_url": companyfacts_url,
            "verified_eps": verified_candidate.get("value"),
            "verified_quarter": verified_candidate.get("derived_quarter"),
            "verified_as_of_date": verified_candidate.get("filed"),
            "verified_concept": {
                "taxonomy": verified_candidate.get("taxonomy"),
                "concept": verified_candidate.get("concept"),
                "unit_key": verified_candidate.get("unit_key"),
                "form": verified_candidate.get("form"),
                "accn": verified_candidate.get("accn"),
                "score": verified_candidate.get("score"),
            },
            "reason": "seed_eps_matched_best_xbrl_candidate_within_tolerance",
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
    out["verification_method"] = "xbrl_companyfacts"
    out["verified_url"] = companyfacts_url
    out["verified_eps"] = None
    out["verified_as_of_date"] = None
    out["verification"] = {
        "status": "VERIFY_FAILED",
        "method": "xbrl_companyfacts",
        "verified_url": companyfacts_url,
        "verified_eps": None,
        "verified_quarter": None,
        "verified_as_of_date": None,
        "verified_concept": None,
        "reason": primary_failure_class,
        "tolerance": tolerance,
        "attempted_at_utc": now_utc_iso(),
        "candidate_count_considered": len(attempts),
        "primary_failure_class": primary_failure_class,
        "first_failure": first_failure,
        "last_failure": last_failure,
    }
    return out


def probe_seed_with_xbrl(
    seed_record: Dict[str, Any],
    *,
    companyfacts: Optional[Dict[str, Any]],
    companyfacts_url: str,
    companyfacts_err: Optional[str],
    tolerance: float,
    notes: List[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    quarter = str(seed_record["quarter"])
    year = int(quarter[:4])
    qnum = int(quarter[-1])

    debug = build_debug_quarter_entry(year, qnum)
    pub_state = debug["publication_state"]

    if pub_state == "NOT_ENDED_YET":
        debug["status"] = "NOT_ENDED_YET"
        record = copy.deepcopy(seed_record)
        record["verification_status"] = "NOT_ENDED_YET"
        record["verification_method"] = "xbrl_companyfacts"
        record["reference_url_verified_this_run"] = False
        record["verification"] = {
            "status": "NOT_ENDED_YET",
            "method": "xbrl_companyfacts",
            "verified_url": companyfacts_url,
            "verified_eps": None,
            "verified_quarter": None,
            "verified_as_of_date": None,
            "verified_concept": None,
            "reason": FAILURE_CLASS_NOT_ENDED,
            "attempted_at_utc": now_utc_iso(),
            "candidate_count_considered": 0,
            "primary_failure_class": FAILURE_CLASS_NOT_ENDED,
            "first_failure": None,
            "last_failure": None,
        }
        notes.append(f"{quarter}: skipped XBRL probe because quarter not ended yet")
        return record, debug

    if pub_state == "LIKELY_NOT_PUBLISHED_YET":
        debug["status"] = "LIKELY_NOT_PUBLISHED_YET"
        record = copy.deepcopy(seed_record)
        record["verification_status"] = "LIKELY_NOT_PUBLISHED_YET"
        record["verification_method"] = "xbrl_companyfacts"
        record["reference_url_verified_this_run"] = False
        record["verification"] = {
            "status": "LIKELY_NOT_PUBLISHED_YET",
            "method": "xbrl_companyfacts",
            "verified_url": companyfacts_url,
            "verified_eps": None,
            "verified_quarter": None,
            "verified_as_of_date": None,
            "verified_concept": None,
            "reason": FAILURE_CLASS_NOT_PUBLISHED,
            "attempted_at_utc": now_utc_iso(),
            "candidate_count_considered": 0,
            "primary_failure_class": FAILURE_CLASS_NOT_PUBLISHED,
            "first_failure": None,
            "last_failure": None,
        }
        notes.append(f"{quarter}: skipped XBRL probe because publication likely not ready yet")
        return record, debug

    attempts: List[Dict[str, Any]] = []

    if companyfacts is None:
        debug["status"] = "NO_XBRL_DATA"
        attempt = {
            "probe": "companyfacts_fetch",
            "failure_class": FAILURE_CLASS_HTTP,
            "reason": f"companyfacts_fetch_failed:{companyfacts_err}",
            "companyfacts_url": companyfacts_url,
        }
        attempts.append(attempt)
        debug["attempts"] = attempts
        record = update_record_with_verification(
            seed_record,
            verified_candidate=None,
            companyfacts_url=companyfacts_url,
            attempts=attempts,
            tolerance=tolerance,
        )
        notes.append(f"{quarter}: companyfacts unavailable | err={companyfacts_err}")
        return record, debug

    candidates = collect_xbrl_eps_candidates(
        companyfacts,
        expected_quarter=quarter,
        expected_as_of_date=str(seed_record["as_of_date"]),
    )
    debug["candidate_count"] = len(candidates)
    debug["candidate_preview"] = [summarize_candidate(c) for c in candidates[:12]]

    if not candidates:
        debug["status"] = "NO_XBRL_CANDIDATE"
        attempts.append(
            {
                "probe": "companyfacts_candidate_search",
                "failure_class": FAILURE_CLASS_NO_CANDIDATE,
                "reason": "no_eps_candidate_found_in_companyfacts",
                "companyfacts_url": companyfacts_url,
            }
        )
        debug["attempts"] = attempts
        record = update_record_with_verification(
            seed_record,
            verified_candidate=None,
            companyfacts_url=companyfacts_url,
            attempts=attempts,
            tolerance=tolerance,
        )
        notes.append(f"{quarter}: no XBRL EPS candidate found in companyfacts")
        return record, debug

    best, pick_reason = pick_best_xbrl_candidate(
        candidates,
        expected_quarter=quarter,
        expected_eps=float(seed_record["eps"]),
        tolerance=tolerance,
    )

    if best is None:
        debug["status"] = "NO_XBRL_CANDIDATE"
        attempts.append(
            {
                "probe": "companyfacts_candidate_pick",
                "failure_class": FAILURE_CLASS_NO_CANDIDATE,
                "reason": "best_candidate_none",
                "companyfacts_url": companyfacts_url,
            }
        )
        debug["attempts"] = attempts
        record = update_record_with_verification(
            seed_record,
            verified_candidate=None,
            companyfacts_url=companyfacts_url,
            attempts=attempts,
            tolerance=tolerance,
        )
        notes.append(f"{quarter}: best XBRL candidate is none")
        return record, debug

    best_summary = summarize_candidate(best)

    if pick_reason == "exact_match":
        attempts.append(
            {
                "probe": "companyfacts_best_candidate",
                "failure_class": None,
                "reason": "exact_match",
                "candidate": best_summary,
            }
        )
        debug["attempts"] = attempts
        debug["discovered"] = True
        debug["discovered_record_source"] = "xbrl_companyfacts"
        debug["status"] = "VERIFIED"
        record = update_record_with_verification(
            seed_record,
            verified_candidate=best,
            companyfacts_url=companyfacts_url,
            attempts=attempts,
            tolerance=tolerance,
        )
        notes.append(
            f"{quarter}: VERIFIED via companyfacts "
            f"{best.get('taxonomy')}:{best.get('concept')} "
            f"value={best.get('value')} filed={best.get('filed')}"
        )
        return record, debug

    attempts.append(
        {
            "probe": "companyfacts_best_candidate",
            "failure_class": FAILURE_CLASS_MISMATCH,
            "reason": "best_candidate_mismatch",
            "expected_quarter": quarter,
            "expected_eps": seed_record["eps"],
            "candidate": best_summary,
        }
    )
    debug["attempts"] = attempts
    debug["status"] = "VERIFY_FAILED"

    record = update_record_with_verification(
        seed_record,
        verified_candidate=None,
        companyfacts_url=companyfacts_url,
        attempts=attempts,
        tolerance=tolerance,
    )
    notes.append(
        f"{quarter}: VERIFY_FAILED best XBRL candidate mismatch | "
        f"candidate={best.get('taxonomy')}:{best.get('concept')} "
        f"value={best.get('value')} quarter={best.get('derived_quarter')} filed={best.get('filed')}"
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
    seed_count = sum(1 for x in merged_quarters if x.get("data_origin") == "bootstrap_seed")

    return {
        "meta": {
            "generated_at_utc": now_utc_iso(),
            "script": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            "source_policy": "seed_first_plus_optional_data_sec_companyfacts_xbrl_probe_non_blocking",
            "entry_pages": entry_pages,
            "notes": notes,
            "counts": {
                "verified_count": verified_count,
                "verify_failed_count": failed_count,
                "verify_skipped_count": skipped_count,
                "bootstrap_seed_count": seed_count,
                "total_quarters": len(merged_quarters),
            },
            "optional_features": {
                "xbrl_probe_enabled": True,
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
        description="Update TSMC quarterly EPS tracker (seed-first + optional XBRL probe)."
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output tracker JSON path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    parser.add_argument("--sleep-sec", type=float, default=DEFAULT_SLEEP, help="Sleep between retries")
    parser.add_argument("--start-year", type=int, default=datetime.now().year, help="Start year to scan")
    parser.add_argument("--end-year", type=int, default=max(datetime.now().year - 5, 2024), help="End year to scan")
    parser.add_argument("--sec-cik", default=DEFAULT_SEC_CIK, help="SEC CIK, zero-padded")
    parser.add_argument(
        "--sec-user-agent",
        default=DEFAULT_SEC_USER_AGENT,
        help="User-Agent for data.sec.gov requests; use a real contact identity if possible",
    )
    parser.add_argument(
        "--xbrl-tolerance",
        type=float,
        default=DEFAULT_XBRL_TOLERANCE,
        help="Absolute EPS tolerance for XBRL verification match",
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
    notes.append("XBRL probe mode=companyfacts_only")
    notes.append(f"SEC companyfacts probe cik={args.sec_cik}")

    companyfacts_url = sec_companyfacts_url(args.sec_cik)
    entry_pages = [companyfacts_url]

    companyfacts, companyfacts_err = http_get_json(
        session,
        companyfacts_url,
        args.timeout,
        args.retries,
        args.sleep_sec,
        headers=sec_headers(args.sec_user_agent),
    )
    if companyfacts is None:
        notes.append(f"companyfacts fetch failed: {companyfacts_url} | err={companyfacts_err}")
    else:
        notes.append(f"companyfacts fetch ok: {companyfacts_url}")

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
            updated, dbg = probe_seed_with_xbrl(
                seed_map[quarter],
                companyfacts=companyfacts,
                companyfacts_url=companyfacts_url,
                companyfacts_err=companyfacts_err,
                tolerance=args.xbrl_tolerance,
                notes=notes,
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
            f"verified_url={q.get('verified_url')}"
        )

    print("[INFO] discovery_debug summary:")
    for d in discovery_debug:
        print(
            f"  - {d.get('quarter')}: status={d.get('status')} | "
            f"pub_state={d.get('publication_state')} | "
            f"candidate_count={d.get('candidate_count')} | "
            f"attempts={len(d.get('attempts', []))} | "
            f"discovered={d.get('discovered')}"
        )

    print("[INFO] notes:")
    for n in notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()