#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TWSE sidecar updater (roll25_cache/):
- Fetches:
  1) FMTQIK: trade value / close / change
  2) MI_5MINS_HIST: OHLC (must truly have high/low; never guess)
- Maintains rolling cache: roll25_cache/roll25.json (max 25 trading days)
- Writes:
  - roll25_cache/latest_report.json
  - roll25_cache/manifest.json (pinned URLs for audit, based on git HEAD sha)

Robustness:
- Supports ROC compact date like "1150102" (YYYMMDD in ROC year)
- Supports MI_5MINS_HIST fields: HighestIndex / LowestIndex / ClosingIndex
- If FMTQIK can't be parsed into usable dates:
  - Print diagnostics
  - Do NOT overwrite cache files
  - Exit 0 so sanity check still runs
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import requests

TZ_TAIPEI = ZoneInfo("Asia/Taipei")

FMTQIK_URL = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
MI_5MINS_HIST_URL = "https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST"

CACHE_DIR = "roll25_cache"
ROLL25_PATH = os.path.join(CACHE_DIR, "roll25.json")
LATEST_REPORT_PATH = os.path.join(CACHE_DIR, "latest_report.json")
MANIFEST_PATH = os.path.join(CACHE_DIR, "manifest.json")

LOOKBACK_TARGET = 20
STORE_CAP = 25


# ---------- helpers ----------

def _now_taipei() -> datetime:
    return datetime.now(tz=TZ_TAIPEI)

def _today_taipei() -> date:
    return _now_taipei().date()

def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == "" or s.upper() == "NA" or s.lower() == "null":
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None

def _safe_int(x: Any) -> Optional[int]:
    f = _safe_float(x)
    if f is None:
        return None
    try:
        return int(round(f))
    except Exception:
        return None

def _roc_slash_to_iso(roc: str) -> Optional[str]:
    """
    ROC date like "114/01/05" -> "2025-01-05"
    """
    if not isinstance(roc, str):
        return None
    s = roc.strip()
    m = re.match(r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$", s)
    if not m:
        return None
    y = int(m.group(1)) + 1911
    mo = int(m.group(2))
    da = int(m.group(3))
    try:
        return date(y, mo, da).isoformat()
    except Exception:
        return None

def _roc_compact_to_iso(compact: str) -> Optional[str]:
    """
    ROC compact date like "1150102" (YYYMMDD, ROC year) -> "2026-01-02"
    """
    if not isinstance(compact, str):
        return None
    s = compact.strip()
    if not re.match(r"^\d{7}$", s):
        return None
    try:
        roc_y = int(s[:3])
        mo = int(s[3:5])
        da = int(s[5:7])
        y = roc_y + 1911
        return date(y, mo, da).isoformat()
    except Exception:
        return None

def _parse_date_any(v: Any) -> Optional[str]:
    """
    Accept:
    - "YYYY-MM-DD"
    - "YYYY/MM/DD"
    - ROC "114/01/05"
    - ROC compact "1150102"
    """
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
    s = str(v).strip()
    if s == "":
        return None

    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            return None

    iso = _roc_slash_to_iso(s)
    if iso:
        return iso

    iso2 = _roc_compact_to_iso(s)
    if iso2:
        return iso2

    return None

def _http_get_json(url: str, timeout: int = 25) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "twse-sidecar/1.2 (+github-actions)"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)

def _read_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def _write_json_file(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)

def _git_head_sha() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if re.match(r"^[0-9a-f]{40}$", out):
            return out
    except Exception:
        pass
    return "UNKNOWN"

def _pinned_raw_url(repo: str, sha: str, path: str) -> str:
    path = path.lstrip("/")
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"

def _repo_slug_from_env() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "<OWNER>/<REPO>")

def _avg(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)

def _calc_amplitude_pct(high: float, low: float, prev_close: float) -> Optional[float]:
    if prev_close == 0:
        return None
    return (high - low) / prev_close * 100.0

def _unwrap_to_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("data", "result", "records", "items", "aaData", "dataset"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        if all(not isinstance(v, list) for v in payload.values()):
            return [payload]
    return []

def _diag_payload(name: str, payload: Any) -> None:
    t = type(payload).__name__
    print(f"[DIAG] {name}: type={t}")
    if isinstance(payload, dict):
        keys = list(payload.keys())[:30]
        print(f"[DIAG] {name}: top_keys={keys}")
        rows = _unwrap_to_rows(payload)
        if rows:
            print(f"[DIAG] {name}: unwrapped_rows={len(rows)}")
            print(f"[DIAG] {name}: row0_keys={list(rows[0].keys())[:30]}")
        else:
            print(f"[DIAG] {name}: cannot unwrap to rows")
    elif isinstance(payload, list):
        print(f"[DIAG] {name}: list_len={len(payload)}")
        for i in range(min(2, len(payload))):
            if isinstance(payload[i], dict):
                print(f"[DIAG] {name}: row{i}_keys={list(payload[i].keys())[:30]}")
            else:
                print(f"[DIAG] {name}: row{i}_type={type(payload[i]).__name__}")


# ---------- domain parsing ----------

@dataclass
class FmtqikRow:
    date: str
    trade_value: Optional[int]
    close: Optional[float]
    change: Optional[float]
    raw: Dict[str, Any]

def _parse_fmtqik(payload: Any) -> List[FmtqikRow]:
    rows = _unwrap_to_rows(payload)
    if not rows:
        return []

    parsed: List[FmtqikRow] = []
    for r in rows:
        d = _parse_date_any(r.get("Date") or r.get("date") or r.get("日期") or r.get("DATE"))
        if not d:
            continue

        tv = _safe_int(r.get("TradeValue") or r.get("tradeValue") or r.get("成交金額"))

        # FMTQIK uses "TAIEX" for index value
        close = _safe_float(
            r.get("TAIEX") or r.get("Close") or r.get("close") or r.get("收盤指數") or r.get("收盤")
        )

        chg = _safe_float(r.get("Change") or r.get("change") or r.get("漲跌點數") or r.get("漲跌"))

        parsed.append(FmtqikRow(date=d, trade_value=tv, close=close, change=chg, raw=r))

    parsed.sort(key=lambda x: x.date)
    return parsed

@dataclass
class OhlcRow:
    date: str
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    raw: Dict[str, Any]

def _parse_mi_5mins_hist(payload: Any) -> List[OhlcRow]:
    rows = _unwrap_to_rows(payload)
    if not rows:
        return []

    parsed: List[OhlcRow] = []
    for r in rows:
        d = _parse_date_any(r.get("Date") or r.get("date") or r.get("日期") or r.get("DATE"))
        if not d:
            continue

        # MI_5MINS_HIST uses these keys:
        # OpeningIndex / HighestIndex / LowestIndex / ClosingIndex
        high = _safe_float(r.get("HighestIndex") or r.get("High") or r.get("high") or r.get("最高"))
        low = _safe_float(r.get("LowestIndex") or r.get("Low") or r.get("low") or r.get("最低"))
        close = _safe_float(r.get("ClosingIndex") or r.get("Close") or r.get("close") or r.get("收盤"))

        parsed.append(OhlcRow(date=d, high=high, low=low, close=close, raw=r))

    parsed.sort(key=lambda x: x.date)
    return parsed

def _index_by_date_fmtqik(rows: List[FmtqikRow]) -> Dict[str, FmtqikRow]:
    return {x.date: x for x in rows}

def _index_by_date_ohlc(rows: List[OhlcRow]) -> Dict[str, OhlcRow]:
    return {x.date: x for x in rows}

def _latest_date(dates: List[str]) -> Optional[str]:
    return max(dates) if dates else None


# ---------- cache and selection ----------

def _merge_roll_cache(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    m: Dict[str, Dict[str, Any]] = {}
    for it in existing:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it
    for it in new_items:
        if isinstance(it, dict) and "date" in it:
            m[str(it["date"])] = it

    merged = list(m.values())
    merged.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    merged = merged[:STORE_CAP]

    dates = [str(x.get("date", "")) for x in merged]
    dedupe_ok = (len(dates) == len(set(dates)))
    return merged, dedupe_ok

def _pick_used_date(today: date, fmt_dates: List[str]) -> Tuple[str, str]:
    if not fmt_dates:
        return ("NA", "FMTQIK_EMPTY")

    today_iso = today.isoformat()
    if _is_weekend(today):
        return (_latest_date(fmt_dates) or fmt_dates[-1], "NON_TRADING_DAY")
    if today_iso not in fmt_dates:
        return (_latest_date(fmt_dates) or fmt_dates[-1], "DATA_NOT_UPDATED")
    return (today_iso, "OK_TODAY")

def _build_cache_item(used_date: str, fmt: Optional[FmtqikRow], ohlc: Optional[OhlcRow]) -> Dict[str, Any]:
    close = fmt.close if fmt else (ohlc.close if ohlc else None)
    change = fmt.change if fmt else None
    trade_value = fmt.trade_value if fmt else None
    high = ohlc.high if ohlc else None
    low = ohlc.low if ohlc else None
    return {"date": used_date, "close": close, "change": change, "trade_value": trade_value, "high": high, "low": low}

def _extract_lookback_series(roll: List[Dict[str, Any]], used_date: str) -> List[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) <= used_date]
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[:LOOKBACK_TARGET]

def _find_dminus1(roll: List[Dict[str, Any]], used_date: str) -> Optional[Dict[str, Any]]:
    eligible = [r for r in roll if isinstance(r, dict) and str(r.get("date", "")) < used_date]
    if not eligible:
        return None
    eligible.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return eligible[0]


# ---------- main ----------

def main() -> None:
    _ensure_cache_dir()

    existing_roll = _read_json_file(ROLL25_PATH, default=[])
    if not isinstance(existing_roll, list):
        existing_roll = []

    try:
        fmt_raw = _http_get_json(FMTQIK_URL)
    except Exception as e:
        print(f"[ERROR] Failed to fetch/parse FMTQIK JSON: {e}")
        return

    try:
        ohlc_raw = _http_get_json(MI_5MINS_HIST_URL)
    except Exception as e:
        print(f"[ERROR] Failed to fetch/parse MI_5MINS_HIST JSON: {e}")
        ohlc_raw = []

    fmt_rows = _parse_fmtqik(fmt_raw)
    ohlc_rows = _parse_mi_5mins_hist(ohlc_raw)

    if not fmt_rows:
        print("[ERROR] FMTQIK returned no usable rows/dates after parsing.")
        _diag_payload("FMTQIK", fmt_raw)
        return

    fmt_by_date = _index_by_date_fmtqik(fmt_rows)
    ohlc_by_date = _index_by_date_ohlc(ohlc_rows)

    fmt_dates = sorted(fmt_by_date.keys())
    today = _today_taipei()

    used_date, tag = _pick_used_date(today, fmt_dates)
    if used_date == "NA":
        print("[ERROR] UsedDate could not be determined (fmt_dates empty).")
        _diag_payload("FMTQIK", fmt_raw)
        return

    fmt_used = fmt_by_date.get(used_date)
    ohlc_used = ohlc_by_date.get(used_date)

    ohlc_ok = bool(ohlc_used and (ohlc_used.high is not None) and (ohlc_used.low is not None))
    mode = "FULL" if ohlc_ok else "MISSING_OHLC"
    ohlc_status = "OK" if ohlc_ok else "MISSING"

    cache_item = _build_cache_item(used_date, fmt_used, ohlc_used)
    merged_roll, dedupe_ok = _merge_roll_cache(existing_roll, [cache_item])

    lookback = _extract_lookback_series(merged_roll, used_date)
    lookback_n_actual = len(lookback)
    lookback_oldest = lookback[-1]["date"] if lookback else "NA"

    freshness_ok = True
    if lookback_n_actual > 0:
        try:
            oldest_dt = datetime.fromisoformat(str(lookback_oldest)).date()
            delta_days = (today - oldest_dt).days
            if delta_days > 45:
                freshness_ok = False
        except Exception:
            freshness_ok = False

    dminus1 = _find_dminus1(merged_roll, used_date)
    used_dminus1 = dminus1["date"] if dminus1 else "NA"
    prev_close = _safe_float(dminus1.get("close")) if dminus1 else None

    today_close = _safe_float(cache_item.get("close"))
    today_trade_value = _safe_float(cache_item.get("trade_value"))
    today_change = _safe_float(cache_item.get("change"))

    pct_change = None
    if today_close is not None and prev_close is not None and prev_close != 0:
        pct_change = (today_close - prev_close) / prev_close * 100.0

    prior_days = lookback[1:] if lookback_n_actual >= 2 else []

    prior_tv = [_safe_float(x.get("trade_value")) for x in prior_days]
    prior_tv = [x for x in prior_tv if x is not None]

    volume_mult = None
    if today_trade_value is not None and len(prior_tv) >= 9:
        avg_tv = sum(prior_tv[:LOOKBACK_TARGET - 1]) / len(prior_tv[:LOOKBACK_TARGET - 1])
        if avg_tv and avg_tv != 0:
            volume_mult = today_trade_value / avg_tv

    amplitude_pct = None
    vol_mult = None
    if ohlc_ok and prev_close is not None and prev_close != 0:
        high = _safe_float(cache_item.get("high"))
        low = _safe_float(cache_item.get("low"))
        if high is not None and low is not None:
            amplitude_pct = _calc_amplitude_pct(high, low, prev_close)

            prior_amp: List[float] = []
            for x in prior_days:
                d = str(x.get("date", ""))
                h = _safe_float(x.get("high"))
                l = _safe_float(x.get("low"))
                dm1 = _find_dminus1(merged_roll, d)
                pc = _safe_float(dm1.get("close")) if dm1 else None
                if h is None or l is None or pc is None or pc == 0:
                    continue
                amp = _calc_amplitude_pct(h, l, pc)
                if amp is not None:
                    prior_amp.append(amp)

            if amplitude_pct is not None and len(prior_amp) >= 9:
                avg_amp = sum(prior_amp[:LOOKBACK_TARGET - 1]) / len(prior_amp[:LOOKBACK_TARGET - 1])
                if avg_amp and avg_amp != 0:
                    vol_mult = amplitude_pct / avg_amp

    is_down_day = (pct_change is not None and pct_change < 0) or (today_change is not None and today_change < 0)

    closes = []
    for x in lookback:
        c = _safe_float(x.get("close"))
        if c is not None:
            closes.append((str(x.get("date", "")), c))

    new_low = False
    if today_close is not None and closes:
        min_close = min(c for _, c in closes)
        new_low = (today_close <= min_close)

    consecutive_break = False
    if dminus1 is not None:
        d1_date = str(dminus1.get("date"))
        d1_close = _safe_float(dminus1.get("close"))
        if d1_close is not None:
            d1_lookback = _extract_lookback_series(merged_roll, d1_date)
            d1_closes = [_safe_float(x.get("close")) for x in d1_lookback]
            d1_closes = [x for x in d1_closes if x is not None]
            if d1_closes:
                d1_new_low = (d1_close <= min(d1_closes))
                if new_low and d1_new_low:
                    consecutive_break = True

    risk_level = "未知"
    signal_text = ""

    if not freshness_ok:
        risk_level = "未知（資料不可靠）"
        signal_text = "資料過舊：lookback 最舊一筆距今 >45 天"
    elif lookback_n_actual < 10:
        risk_level = "未知（資料不足）"
        signal_text = "可得交易日數 <10，倍數不計算"
    else:
        if mode == "FULL":
            # 完整模式觸發：下跌日 + 量能>=1.2 + 波動>=1.2
            vol_ok = (vol_mult is not None and vol_mult >= 1.2)
            volu_ok = (volume_mult is not None and volume_mult >= 1.2)
            if is_down_day and volu_ok and vol_ok:
                if (volume_mult >= 1.5) and (vol_mult >= 1.5) and (pct_change is not None and pct_change <= -1.5):
                    risk_level = "高"
                elif (pct_change is not None and pct_change <= -1.0):
                    risk_level = "中"
                else:
                    risk_level = "低"
                signal_text = "去槓桿風險上升（放量下跌 + 振幅放大）"
            else:
                risk_level = "低"
                signal_text = "未觸發 A) 規則"
        else:
            # 缺 OHLC 模式：不得觸發「去槓桿風險上升」
            if is_down_day and (volume_mult is not None and volume_mult >= 1.3) and (pct_change is not None and pct_change <= -1.2):
                risk_level = "中"
                signal_text = "代理警訊：放量下跌；OHLC缺失可能漏報踩踏"
            else:
                risk_level = "未知（資料不足：OHLC缺失）"
                signal_text = "OHLC缺失，無法套用完整模式"

    prefix = ""
    if tag == "NON_TRADING_DAY":
        prefix = "今日非交易日；"
    elif tag == "DATA_NOT_UPDATED":
        prefix = "今日資料未更新；"

    if mode == "MISSING_OHLC":
        summary = f"{prefix}UsedDate={used_date}：OHLC缺失，{signal_text}；風險等級={risk_level}"
    else:
        summary = f"{prefix}UsedDate={used_date}：{signal_text}；風險等級={risk_level}"

    def _fmt_num(x: Optional[float], nd: int = 2) -> Any:
        return None if x is None else round(float(x), nd)

    numbers = {
        "UsedDate": used_date,
        "Close": _fmt_num(today_close, 2),
        "PctChange": _fmt_num(pct_change, 3),
        "TradeValue": _safe_int(today_trade_value),
        "VolumeMultiplier": _fmt_num(volume_mult, 3),
        "AmplitudePct": _fmt_num(amplitude_pct, 3),
        "VolMultiplier": _fmt_num(vol_mult, 3),
    }

    signal = {
        "DownDay": bool(is_down_day) if (pct_change is not None or today_change is not None) else None,
        "NewLow_N": bool(new_low) if today_close is not None else None,
        "ConsecutiveBreak": bool(consecutive_break),
        "VolumeAmplified": (volume_mult is not None and volume_mult >= 1.2) if volume_mult is not None else None,
        "VolAmplified": (vol_mult is not None and vol_mult >= 1.2) if vol_mult is not None else None,
    }

    if risk_level in ("中", "高"):
        if mode == "FULL" and "去槓桿風險上升" in signal_text:
            action = "先下調槓桿與部位曝險、提高保證金緩衝（例如提高現金比重/降低融資占比），並觀察下一個交易日是否延續破位與放量。"
        else:
            action = "先控槓桿與保證金緩衝，暫不做激進判斷；等待 OHLC 補齊後再用完整模式重算是否觸發踩踏風險。"
    else:
        action = "維持風險控管紀律（槓桿與保證金緩衝不惡化），持續每日觀察量能倍數、是否破位與資料完整性。"

    caveats_lines = []
    caveats_lines.append(f"Sources: FMTQIK={FMTQIK_URL} ; MI_5MINS_HIST={MI_5MINS_HIST_URL}")
    if not ohlc_ok:
        caveats_lines.append("OHLC: high 或 low 缺失（嚴格規則：不得硬猜；因此波動倍數=NA且不觸發完整模式）")
    if dminus1 is None:
        caveats_lines.append("D-1: 昨收缺失（無法計算漲跌幅與振幅%）")

    meta_line = (
        f"Mode={mode} | UsedDate={used_date} | UsedDminus1={used_dminus1} | "
        f"LookbackNTarget={LOOKBACK_TARGET} | LookbackNActual={lookback_n_actual} | "
        f"LookbackOldest={lookback_oldest} | OHLC={ohlc_status}"
    )
    caveats_lines.append(meta_line)
    caveats = "\n".join(caveats_lines)

    latest_report = {
        "generated_at": _now_taipei().isoformat(),
        "timezone": "Asia/Taipei",
        "summary": summary,
        "numbers": numbers,
        "signal": signal,
        "action": action,
        "caveats": caveats,
        "cache_roll25": merged_roll,
        "tag": tag,
        "freshness_ok": freshness_ok,
        "risk_level": risk_level,
        "mode": mode,
        "ohlc_status": ohlc_status,
        "used_date": used_date,
        "used_dminus1": used_dminus1,
        "lookback_n_actual": lookback_n_actual,
        "lookback_oldest": lookback_oldest,
    }

    _write_json_file(ROLL25_PATH, merged_roll)
    _write_json_file(LATEST_REPORT_PATH, latest_report)

    sha = _git_head_sha()
    repo = _repo_slug_from_env()
    manifest = {
        "generated_at_taipei": _now_taipei().isoformat(),
        "as_of_ts": _now_taipei().isoformat(),
        "data_commit_sha": sha,
        "pinned": {
            "roll25_json": _pinned_raw_url(repo, sha, "roll25_cache/roll25.json"),
            "latest_report_json": _pinned_raw_url(repo, sha, "roll25_cache/latest_report.json"),
            "manifest_json": _pinned_raw_url(repo, sha, "roll25_cache/manifest.json"),
        }
    }
    _write_json_file(MANIFEST_PATH, manifest)

    print("TWSE sidecar updated:")
    print(f"  UsedDate={used_date}  Mode={mode}  Risk={risk_level}  LookbackNActual={lookback_n_actual}")
    print(f"  roll25_records={len(merged_roll)}  dedupe_ok={dedupe_ok}  sha={sha}")


if __name__ == "__main__":
    main()