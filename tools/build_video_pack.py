#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


TZ_NAME = "Asia/Taipei"
SCHEMA_VERSION = "episode_pack_schema_v1"
BUILD_FINGERPRINT = "build_video_pack@v1.flat"


def _now_local() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo(TZ_NAME))


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(p: Path) -> Dict[str, Any]:
    if not p.exists():
        raise FileNotFoundError(f"missing input file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def pick(d: Dict[str, Any], keys: Tuple[str, ...], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def get_nested(d: Dict[str, Any], path: Tuple[str, ...], default=None):
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def parse_ymd(x: Any) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    s = str(x).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return None
    return None


def compute_age_days(as_of: Optional[date], today: date) -> Optional[int]:
    if as_of is None:
        return None
    try:
        return (today - as_of).days
    except Exception:
        return None


def extract_dq_flags(d: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    v = get_nested(d, ("dq", "flags"))
    if isinstance(v, list):
        flags.extend([str(x) for x in v])
    v2 = d.get("dq_flags")
    if isinstance(v2, list):
        flags.extend([str(x) for x in v2])
    out: List[str] = []
    seen = set()
    for f in flags:
        if f not in seen:
            out.append(f)
            seen.add(f)
    return out


def best_effort_extract_numbers(tag: str, d: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Tuple[str, Tuple[str, ...]]] = []

    if tag == "tw0050_bb":
        candidates = [
            ("price", ("last_price", "price", "close", "adjclose_last", "adjclose")),
            ("bb_z", ("bb_z", "bb_z60", "z60", "z_score", "bbz")),
            ("pctl", ("p60", "percentile", "pct", "pctl")),
        ]
    elif tag == "roll25":
        candidates = [
            ("mode", ("mode", "Mode")),
            ("used_date", ("UsedDate", "used_date", "as_of_data_date")),
            ("turnover_z", ("turnover_z", "z", "z60", "z_score")),
        ]
    elif tag == "margin":
        candidates = [
            ("margin_balance", ("margin_balance", "financing_balance", "total_margin", "balance")),
            ("delta", ("delta", "change", "chg", "diff")),
            ("as_of", ("as_of", "as_of_date", "date", "day_key_local")),
        ]

    extracted: List[Dict[str, Any]] = []
    for name, keys in candidates:
        val = pick(d, keys, default=None)
        if val is None:
            summ = d.get("summary")
            if isinstance(summ, dict):
                val = pick(summ, keys, default=None)
        if val is not None:
            extracted.append({"field": name, "value": val, "picked_from": list(keys)})
    return extracted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tw0050", required=True)
    ap.add_argument("--roll25", required=True)
    ap.add_argument("--margin", required=True)
    ap.add_argument("--out_dir", required=True, help="Output directory that will contain episode_pack.json and episode_outline.md")
    args = ap.parse_args()

    tw_path = Path(args.tw0050)
    r25_path = Path(args.roll25)
    m_path = Path(args.margin)

    tw = _read_json(tw_path)
    r25 = _read_json(r25_path)
    m = _read_json(m_path)

    now_local = _now_local()
    today = now_local.date()
    day_key = today.isoformat()

    # as_of dates (best effort; no guessing)
    tw_asof = parse_ymd(pick(tw, ("last_date", "as_of_data_date", "UsedDate", "day_key_local")))
    r25_asof = parse_ymd(pick(r25, ("as_of_data_date", "UsedDate", "last_date", "day_key_local")))
    m_asof = parse_ymd(pick(m, ("as_of_date", "as_of", "date", "day_key_local", "last_date")))

    tw_age = compute_age_days(tw_asof, today)
    r25_age = compute_age_days(r25_asof, today)
    m_age = compute_age_days(m_asof, today)

    warnings: List[str] = []
    if tw_asof is None:
        warnings.append("tw0050_as_of_missing")
    if r25_asof is None:
        warnings.append("roll25_as_of_missing")
    if m_asof is None:
        warnings.append("margin_as_of_missing")

    if tw_asof and r25_asof and m_asof and not (tw_asof == r25_asof == m_asof):
        warnings.append(f"date_misaligned: tw0050={tw_asof}, roll25={r25_asof}, margin={m_asof}")

    STALE_DAYS_WARN = 2
    for name, age in (("tw0050", tw_age), ("roll25", r25_age), ("margin", m_age)):
        if age is not None and age > STALE_DAYS_WARN:
            warnings.append(f"stale_{name}: age_days={age} (> {STALE_DAYS_WARN})")

    tw_dq = extract_dq_flags(tw)
    r25_dq = extract_dq_flags(r25)
    m_dq = extract_dq_flags(m)

    extracts = {
        "tw0050_bb": best_effort_extract_numbers("tw0050_bb", tw),
        "roll25": best_effort_extract_numbers("roll25", r25),
        "margin": best_effort_extract_numbers("margin", m),
    }

    meta_env = {
        "GITHUB_SHA": os.environ.get("GITHUB_SHA"),
        "GITHUB_RUN_ID": os.environ.get("GITHUB_RUN_ID"),
        "GITHUB_WORKFLOW": os.environ.get("GITHUB_WORKFLOW"),
        "GITHUB_REF_NAME": os.environ.get("GITHUB_REF_NAME"),
        "GITHUB_REPOSITORY": os.environ.get("GITHUB_REPOSITORY"),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pack = {
        "schema_version": SCHEMA_VERSION,
        "build_fingerprint": BUILD_FINGERPRINT,
        "generated_at_utc": _now_utc_iso(),
        "generated_at_local": now_local.isoformat(),
        "timezone": TZ_NAME,
        "day_key_local": day_key,
        "inputs": {
            "tw0050_bb": {
                "path": str(tw_path),
                "as_of_date": tw_asof.isoformat() if tw_asof else None,
                "age_days": tw_age,
                "dq_flags": tw_dq,
                "fingerprint": pick(tw, ("build_script_fingerprint", "script_fingerprint", "SCRIPT_FINGERPRINT")),
            },
            "roll25": {
                "path": str(r25_path),
                "as_of_date": r25_asof.isoformat() if r25_asof else None,
                "age_days": r25_age,
                "dq_flags": r25_dq,
                "fingerprint": pick(r25, ("script_fingerprint", "SCRIPT_FINGERPRINT")),
            },
            "taiwan_margin": {
                "path": str(m_path),
                "as_of_date": m_asof.isoformat() if m_asof else None,
                "age_days": m_age,
                "dq_flags": m_dq,
                "fingerprint": pick(m, ("script_fingerprint", "SCRIPT_FINGERPRINT")),
            },
        },
        "warnings": warnings,
        "extracts_best_effort": extracts,
        # v1: keep raw blobs to avoid losing information (NotebookLM can search them)
        "raw": {
            "tw0050_bb": tw,
            "roll25": r25,
            "taiwan_margin": m,
        },
        "meta_env": meta_env,
    }

    _write_json(out_dir / "episode_pack.json", pack)

    def _fmt_extract(block: str) -> str:
        rows = extracts.get(block, [])
        if not rows:
            return "- 可引用數據：N/A（未在 JSON 中找到常見欄位；請直接在 episode_pack.json 內搜尋）"
        return "\n".join([f"- {r['field']}: {r['value']}" for r in rows])

    outline = f"""# 投資日記 Episode Outline（roll25 + taiwan margin + tw0050_bb）

- 產出日：{day_key}（{TZ_NAME}）
- 輸出：episode_pack.json, episode_outline.md
- warnings: {", ".join(warnings) if warnings else "None"}

## 開場（20秒）
- 今天用三個訊號整理市場位置：成交熱度（roll25）、槓桿動向（margin）、0050 技術位置（BB）。
- 若 warnings 含 stale 或 date_misaligned：本集只做「狀態描述」，避免跨模組因果結論。

## 1) 成交熱度（roll25）（60秒）
- as_of：{r25_asof.isoformat() if r25_asof else "N/A"}；age_days={r25_age if r25_age is not None else "N/A"}
{_fmt_extract("roll25")}

## 2) 槓桿動向（taiwan margin）（60秒）
- as_of：{m_asof.isoformat() if m_asof else "N/A"}；age_days={m_age if m_age is not None else "N/A"}
{_fmt_extract("margin")}

## 3) 0050 位置（tw0050_bb）（80秒）
- as_of：{tw_asof.isoformat() if tw_asof else "N/A"}；age_days={tw_age if tw_age is not None else "N/A"}
{_fmt_extract("tw0050_bb")}

## 收尾（20秒）
- 免責：非投資建議。資料可能落後/不一致（見 warnings）。歷史統計不保證未來。
- 行動句（模板）：若風險訊號升溫，優先守住現金流與部位上限；若訊號降溫，再考慮分批與再平衡。
"""
    _write_text(out_dir / "episode_outline.md", outline)

    print(f"[OK] wrote: {out_dir / 'episode_pack.json'}")
    print(f"[OK] wrote: {out_dir / 'episode_outline.md'}")


if __name__ == "__main__":
    main()