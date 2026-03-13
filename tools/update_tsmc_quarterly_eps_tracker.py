#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_tsmc_quarterly_eps_tracker.py  (v1.4)

Purpose
-------
Automatically maintain TSMC quarterly EPS tracker.

What changed vs v1.3
--------------------
1) Make provenance explicit:
   - data_origin
   - source_priority
   - reference_source_type
   - reference_url_verified_this_run
2) Strengthen Cnyes parsing:
   - allow title/body patterns like 台積電 / Q1 / EPS / 每股盈餘
3) Merge by source priority:
   official discovered > cnyes discovered > bootstrap seed
4) Keep bootstrap seeds as fallback so tracker is never empty in restricted CI

Notes
-----
- This script does NOT change active_eps_base directly.
- Seeds are bootstrap reference values, not proof of live fetch success.
- Discovery still tries official first, then Cnyes.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests

SCRIPT_NAME = "update_tsmc_quarterly_eps_tracker.py"
SCRIPT_VERSION = "v1.4"

DEFAULT_OUT = "tw0050_bb_cache/quarterly_eps_tracker.json"
DEFAULT_TIMEOUT = 20
DEFAULT_SLEEP = 0.5

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

SOURCE_PRIORITY = {
    "tsmc_official_chinese_news": 100,
    "syndicated_official_announcement_cnyes": 60,
    "tsmc_official_chinese_news_seed": 20,
}

# Bootstrap seeds from recent known-good official pages.
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

# Parsing patterns
DATE_RE_1 = re.compile(r"發佈日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})")
DATE_RE_2 = re.compile(r"發言日期\s*[:：]?\s*(\d{4}/\d{2}/\d{2})")
DATE_RE_3 = re.compile(r"(\d{4}/\d{2}/\d{2})")

# Official page style:
OFFICIAL_TITLE_RE = re.compile(
    r"台積公司(\d{4})年(第一|第二|第三|第四)季每股盈餘新台幣([0-9]+(?:\.[0-9]+)?)元"
)

# More flexible body/title patterns for Cnyes or mirrored pages:
EPS_RE_1 = re.compile(r"每股盈餘(?:為)?新台幣\s*([0-9]+(?:\.[0-9]+)?)\s*元")
EPS_RE_2 = re.compile(r"\bEPS\b[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*元?", re.I)
EPS_RE_3 = re.compile(r"每股(?:純益|盈餘)[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*元")

QUARTER_CN_YEAR_RE = re.compile(r"(\d{4})年(第一|第二|第三|第四)季")
QUARTER_Q_RE_1 = re.compile(r"(\d{4})\s*[Qq]([1-4])")
QUARTER_Q_RE_2 = re.compile(r"[Qq]([1-4])")
QUARTER_TITLE_FALLBACK_RE = re.compile(r"台積電|台積公司|TSMC", re.I)

H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
A_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RESULT_A_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def quarter_word_from_num(qnum: int) -> str:
    return {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
    }.get(qnum, "NA")


def quarter_end_date_from_label(quarter: str) -> str:
    quarter_end_date_map = {
        "Q1": "March 31",
        "Q2": "June 30",
        "Q3": "September 30",
        "Q4": "December 31",
    }
    q_suffix = quarter[-2:]
    return f"{quarter_end_date_map.get(q_suffix, 'NA')}, {quarter[:4]}" if q_suffix in quarter_end_date_map else "NA"


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
            try:
                return curl_get_text(url, timeout=timeout)
            except Exception as e2:
                last_err = e2
                if i < retries:
                    time.sleep(sleep_sec * i)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} | last_err={last_err}")


def unwrap_search_url(url: str) -> str:
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

    out: List[Dict[str, str]] = []
    seen: set[str] = set()

    for href, inner_html in RESULT_A_RE.findall(html):
        real_url = unwrap_search_url(href)
        title = clean_html_text(inner_html)
        if real_url in seen:
            continue
        seen.add(real_url)
        out.append({"url": real_url, "title": title})

    if not out:
        for href, inner_html in A_RE.findall(html):
            real_url = unwrap_search_url(href)
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
    fallback_year: Optional[int] = None,
    fallback_quarter_num: Optional[int] = None,
) -> Optional[str]:
    combined = f"{title} {text}"

    m = OFFICIAL_TITLE_RE.search(combined)
    if m:
        year = int(m.group(1))
        quarter_cn = m.group(2)
        qnum = QUARTER_CN_TO_NUM.get(quarter_cn)
        if qnum:
            return f"{year}Q{qnum}"

    m = QUARTER_CN_YEAR_RE.search(combined)
    if m:
        year = int(m.group(1))
        quarter_cn = m.group(2)
        qnum = QUARTER_CN_TO_NUM.get(quarter_cn)
        if qnum:
            return f"{year}Q{qnum}"

    m = QUARTER_Q_RE_1.search(combined)
    if m:
        return f"{int(m.group(1))}Q{int(m.group(2))}"

    if fallback_year is not None and fallback_quarter_num is not None:
        if QUARTER_TITLE_FALLBACK_RE.search(combined):
            return f"{fallback_year}Q{fallback_quarter_num}"

    return None


def infer_eps_from_text(title: str, text: str) -> Optional[float]:
    combined = f"{title} {text}"

    m = OFFICIAL_TITLE_RE.search(combined)
    if m:
        return float(m.group(3))

    for rx in (EPS_RE_1, EPS_RE_2, EPS_RE_3):
        m = rx.search(combined)
        if m:
            return float(m.group(1))

    return None


def infer_date_from_text(text: str) -> str:
    for rx in (DATE_RE_1, DATE_RE_2, DATE_RE_3):
        m = rx.search(text)
        if m:
            return m.group(1).replace("/", "-")
    return "NA"


def parse_article_record(
    html: str,
    url: str,
    *,
    expected_year: Optional[int] = None,
    expected_quarter_num: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    text = clean_html_text(html)
    title = find_title_text(html, url)

    quarter = infer_quarter_from_text(
        title=title,
        text=text,
        fallback_year=expected_year,
        fallback_quarter_num=expected_quarter_num,
    )
    if not quarter:
        return None

    eps_val = infer_eps_from_text(title=title, text=text)
    if eps_val is None:
        return None

    as_of_date = infer_date_from_text(text)

    qnum = int(quarter[-1])
    quarter_word = quarter_word_from_num(qnum)
    quarter_end_date = quarter_end_date_from_label(quarter)

    source = "tsmc_official_chinese_news"
    reference_source_type = "official_tsmc_chinese_news"
    if "cnyes.com" in url:
        source = "syndicated_official_announcement_cnyes"
        reference_source_type = "cnyes"

    return {
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


def search_one_quarter(
    session: requests.Session,
    year: int,
    quarter_num: int,
    timeout: int,
    retries: int,
    sleep_sec: float,
    notes: List[str],
) -> Optional[Dict[str, Any]]:
    quarter_cn = QUARTER_NUM_TO_CN[quarter_num]

    queries = [
        f'"台積公司{year}年{quarter_cn}季每股盈餘新台幣" site:pr.tsmc.com/chinese/news',
        f'"台積電 {year} Q{quarter_num} EPS" site:anuenews.cnyes.com/news/id',
        f'"台積電 {year}年{quarter_cn}季 EPS" site:anuenews.cnyes.com/news/id',
        f'"台積公司{year}年{quarter_cn}季每股盈餘新台幣" site:anuenews.cnyes.com/news/id',
        f'"台積公司{year}年{quarter_cn}季每股盈餘" 台積電',
    ]

    candidate_urls: List[str] = []
    seen: set[str] = set()

    for q in queries:
        try:
            results = search_ddg_html(session, q, timeout, retries, sleep_sec)
            notes.append(f"search query ok: {q} | results={len(results)}")
        except Exception as e:
            notes.append(f"search query failed: {q} | err={e}")
            continue

        for item in results:
            url = item["url"]
            if (
                "pr.tsmc.com/chinese/news/" not in url
                and "anuenews.cnyes.com/news/id/" not in url
                and "news.cnyes.com/news/id/" not in url
            ):
                continue
            if url in seen:
                continue
            seen.add(url)
            candidate_urls.append(url)

    # official first, cnyes second
    candidate_urls.sort(
        key=lambda u: (
            0 if "pr.tsmc.com/chinese/news/" in u else 1,
            u,
        )
    )

    for url in candidate_urls:
        try:
            html = http_get_text(session, url, timeout, retries, sleep_sec)
        except Exception as e:
            notes.append(f"candidate fetch failed: {url} | err={e}")
            continue

        rec = parse_article_record(
            html,
            url,
            expected_year=year,
            expected_quarter_num=quarter_num,
        )
        if rec is None:
            notes.append(f"candidate parse failed: {url}")
            continue

        expected_quarter = f"{year}Q{quarter_num}"
        if rec["quarter"] != expected_quarter:
            notes.append(f"candidate quarter mismatch: {url} -> {rec['quarter']} expected={expected_quarter}")
            continue

        notes.append(f"parsed quarter {rec['quarter']} eps={rec['eps']} from {url} source={rec['source']}")
        return rec

    notes.append(f"no discovered article parsed for {year}Q{quarter_num}")
    return None


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

    # last write wins only when same quality
    return new


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
            "source_policy": "bootstrap_seeds_plus_official_then_cnyes_discovery",
            "entry_pages": entry_pages,
            "notes": notes,
        },
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
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session()
    existing = load_existing_tracker(out_path)
    existing_quarters = existing.get("quarters", [])

    notes: List[str] = []
    entry_pages: List[str] = []
    fetched: List[Dict[str, Any]] = []

    # 1) bootstrap seeds
    for seed in BOOTSTRAP_SEEDS:
        item = enrich_record(
            seed,
            data_origin="bootstrap_seed",
            reference_source_type="official_tsmc_chinese_news",
            reference_url_verified_this_run=False,
        )
        fetched.append(item)
    notes.append(f"bootstrapped seeds={len(BOOTSTRAP_SEEDS)}")

    # 2) search discovery for target quarters not already seeded
    seeded_quarters = {str(x["quarter"]) for x in BOOTSTRAP_SEEDS}
    for year, quarter_num in iter_target_quarters(args.start_year, args.end_year):
        q = f"{year}Q{quarter_num}"
        entry_pages.append(f"search://{q}")

        if q in seeded_quarters:
            notes.append(f"skip discovery for seeded quarter {q}")
            continue

        rec = search_one_quarter(
            session=session,
            year=year,
            quarter_num=quarter_num,
            timeout=args.timeout,
            retries=args.retries,
            sleep_sec=args.sleep_sec,
            notes=notes,
        )
        if rec is not None:
            fetched.append(rec)

    merged_quarters = merge_records(existing_quarters, fetched)
    out = build_output(merged_quarters=merged_quarters, entry_pages=entry_pages, notes=notes)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote tracker: {out_path}")
    print(f"[INFO] existing_quarters={len(existing_quarters)}")
    print(f"[INFO] fetched_quarters={len(fetched)}")
    print(f"[INFO] merged_quarters={len(merged_quarters)}")
    for q in merged_quarters:
        print(
            f"  - {q.get('quarter')}: EPS={q.get('eps')} | "
            f"as_of={q.get('as_of_date')} | source={q.get('source')} | "
            f"origin={q.get('data_origin')} | pri={q.get('source_priority')} | "
            f"verified_this_run={q.get('reference_url_verified_this_run')} | "
            f"url={q.get('article_url')}"
        )

    print("[INFO] notes:")
    for n in notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()