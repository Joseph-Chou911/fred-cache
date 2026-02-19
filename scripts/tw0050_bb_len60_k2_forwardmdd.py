#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TW0050 Bollinger Bands (window=60, k=2) + forward MDD (20 trading days)

重點修正（針對你目前遇到的問題）：
1) 修掉 yfinance 回傳 MultiIndex 欄位時，誤把 2D DataFrame 丟進 pd.to_numeric 造成：
   TypeError: arg must be a list, tuple, 1-d array, or Series
   -> 透過 _extract_yf_series() 保證取到 1D Series。

2) 加入「官方分割」機制，避免用 auto-detect 亂抓到 2014-01-02 這類疑似資料供應商異常：
   - 預設使用 0050 官方分割：民國114/06/17，比例 4:1
   - 會自動找出「第一個交易日 >= 官方日期」作為 effective_date（通常是 114/06/18）
   - 若資料已經被供應商回補/回溯調整（Adj Close 常見），則只記錄事件、不再重複調整
   - 若資料尚未調整（Close 常見），才會把 earlier history 乘上 1/f 進行連續化。

3) prices.csv 變得更可稽核：
   - close_raw, adjclose_raw（yfinance 原始欄位）
   - price_selected_raw（你選的分析價格：Close 或 Adj Close）
   - price_final（套用 official/auto split 後的最終價格）
   - yf_adj_factor = adjclose_raw / close_raw（用來觀察供應商的調整因子變動）

輸出（在 --cache_dir）：
- stats_latest.json : 最新日快照 + forward MDD 統計 + dq 稽核訊息
- history_lite.json : 最後 N 筆（lite）
- prices.csv        : 稽核用原始/調整後價格表

注意：
- gap audit 採「weekday heuristic」只認週一到週五，不建模台灣休市日，所以會列出很多春節/連假 gap（這是正常現象）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # pragma: no cover


DEFAULT_TZ = "Asia/Taipei"


# ---------------------------
# helpers
# ---------------------------

def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def local_today(tz_name: str) -> date:
    if ZoneInfo is None:
        return datetime.now().date()
    return datetime.now(ZoneInfo(tz_name)).date()


def _to_1d_series(x, index, name: str) -> pd.Series:
    """
    Force x into a 1D pandas Series aligned to `index`.
    Accepts Series / 1-col DataFrame / ndarray (n,) or (n,1).
    """
    if isinstance(x, pd.DataFrame):
        if x.shape[1] != 1:
            raise ValueError(f"{name}: expected 1 column, got {x.shape}")
        x = x.iloc[:, 0]

    if isinstance(x, pd.Series):
        s = x.copy()
        if len(s) != len(index):
            arr = np.asarray(s.to_numpy()).reshape(-1)
            s = pd.Series(arr, index=index, name=name)
        else:
            s = s.reindex(index)
    else:
        arr = np.asarray(x).reshape(-1)  # (n,1) -> (n,)
        s = pd.Series(arr, index=index, name=name)

    s = pd.to_numeric(s, errors="coerce")
    s.name = name
    return s


def _extract_yf_series(df: pd.DataFrame, field: str, symbol: str) -> pd.Series:
    """
    兼容 yfinance 可能回傳 MultiIndex 欄位：
      - (PriceField, Ticker) 或 (Ticker, PriceField)
    保證回傳 1D Series，避免 pd.to_numeric 的 2D TypeError。
    """
    if df is None or df.empty:
        raise RuntimeError("Empty yfinance dataframe.")

    if not isinstance(df.columns, pd.MultiIndex):
        if field not in df.columns:
            return df.iloc[:, 0]
        s = df[field]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s

    cols = df.columns

    # Try (field, symbol)
    try:
        if (field, symbol) in cols:
            s = df[(field, symbol)]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            return s
    except Exception:
        pass

    # Try (symbol, field)
    try:
        if (symbol, field) in cols:
            s = df[(symbol, field)]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            return s
    except Exception:
        pass

    # Try selecting by first level == field
    try:
        lv0 = cols.get_level_values(0)
        if field in set(lv0):
            sub = df.loc[:, lv0 == field]
            if isinstance(sub, pd.DataFrame):
                if sub.shape[1] == 1:
                    return sub.iloc[:, 0]
                # prefer exact symbol if present
                try:
                    lv1 = sub.columns.get_level_values(1)
                    if symbol in set(lv1):
                        s = sub.loc[:, lv1 == symbol]
                        if isinstance(s, pd.DataFrame):
                            return s.iloc[:, 0]
                        return s
                except Exception:
                    pass
                return sub.iloc[:, 0]
    except Exception:
        pass

    # Try selecting by second level == field
    try:
        lv1 = cols.get_level_values(1)
        if field in set(lv1):
            sub = df.loc[:, lv1 == field]
            if isinstance(sub, pd.DataFrame):
                if sub.shape[1] == 1:
                    return sub.iloc[:, 0]
                # prefer exact symbol if present on first level
                try:
                    lv0 = sub.columns.get_level_values(0)
                    if symbol in set(lv0):
                        s = sub.loc[:, lv0 == symbol]
                        if isinstance(s, pd.DataFrame):
                            return s.iloc[:, 0]
                        return s
                except Exception:
                    pass
                return sub.iloc[:, 0]
    except Exception:
        pass

    return df.iloc[:, 0]


def read_csv_prices(csv_path: Path, price_col: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if "Date" not in df.columns:
        raise ValueError("CSV must contain 'Date' column (YYYY-MM-DD).")

    if price_col not in df.columns:
        candidates = ["Adj Close", "AdjClose", "Close", "close", "adj_close", "adjclose", "price"]
        found = None
        for c in candidates:
            if c in df.columns:
                found = c
                break
        if not found:
            raise ValueError(
                f"CSV must contain price column '{price_col}' or one of {candidates}."
            )
        price_col = found

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    px = pd.to_numeric(df[price_col], errors="coerce")
    out = pd.DataFrame({"price": px.values}, index=pd.to_datetime(df["Date"]).values)
    out.index.name = "Date"
    out = out.dropna()
    return out


def fetch_yahoo_prices(symbol: str, start: str, end: Optional[str]) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed. Install with: pip install yfinance")

    df = yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
    )
    if df is None or df.empty:
        raise RuntimeError(f"Empty price data from yfinance for symbol={symbol}.")
    df = df.copy()
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.dropna(axis=0, how="any")
    return df


def calc_forward_mdd(prices_1d: np.ndarray, horizon: int) -> np.ndarray:
    prices_1d = np.asarray(prices_1d).reshape(-1)
    n = len(prices_1d)
    out = np.full(n, np.nan, dtype=float)
    if horizon <= 0:
        return out

    for t in range(0, n - horizon):
        p0 = prices_1d[t]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        fut = prices_1d[t + 1 : t + 1 + horizon]
        if fut.size == 0 or not np.all(np.isfinite(fut)):
            continue
        m = np.min(fut / p0 - 1.0)
        out[t] = min(0.0, float(m))
    return out


def conf_from_n(n: int) -> str:
    if n >= 120:
        return "HIGH"
    if n >= 60:
        return "MED"
    if n >= 20:
        return "LOW"
    return "NA"


def bb_state_from_z(z: Optional[float]) -> Tuple[str, str]:
    if z is None or not np.isfinite(z):
        return ("NA", "z is NA")
    if z <= -2.0:
        return ("BELOW_LOWER_BAND", "z<=-2.0")
    if z <= -1.5:
        return ("NEAR_LOWER_BAND", "z<=-1.5")
    if z >= 2.0:
        return ("ABOVE_UPPER_BAND", "z>=2.0")
    if z >= 1.5:
        return ("NEAR_UPPER_BAND", "z>=1.5")
    return ("IN_BAND", "-1.5<z<1.5")


def compute_mdd_stats(arr: np.ndarray) -> Dict[str, Any]:
    arr = np.asarray(arr, dtype=float)
    fin = arr[np.isfinite(arr)]
    n = int(fin.size)
    if n == 0:
        return {"n": 0, "p50": None, "p10": None, "min": None, "conf": "NA"}
    return {
        "n": n,
        "p50": float(np.percentile(fin, 50)),
        "p10": float(np.percentile(fin, 10)),
        "min": float(np.min(fin)),
        "conf": conf_from_n(n),
    }


def _is_close_ratio(r: float, target: float, tol: float) -> bool:
    if not np.isfinite(r) or r <= 0:
        return False
    return abs(r / target - 1.0) <= tol


def _parse_roc_or_iso_date(s: str) -> date:
    s = str(s).strip()
    if not s:
        raise ValueError("empty date string")

    # ISO
    if "-" in s and len(s.split("-")[0]) == 4:
        return pd.to_datetime(s, errors="raise").date()

    # ROC
    if "/" in s:
        parts = s.split("/")
    else:
        parts = s.split("-")
    if len(parts) != 3:
        raise ValueError(f"Unrecognized date format: {s}")

    y = int(parts[0])
    m = int(parts[1])
    d = int(parts[2])
    if y < 1900:
        y = y + 1911
    return date(y, m, d)


def _find_first_index_ge(dates: pd.DatetimeIndex, target: date) -> Optional[int]:
    if len(dates) == 0:
        return None
    d_arr = pd.to_datetime(dates).date
    for i, di in enumerate(d_arr):
        if di >= target:
            return i
    return None


def apply_official_split_if_needed(
    price_selected: pd.Series,
    dates: pd.DatetimeIndex,
    official_date: date,
    factor: float,
    tol: float,
) -> Tuple[pd.Series, Dict[str, Any]]:
    s = _to_1d_series(price_selected, dates, "price_selected_raw")
    idx = pd.to_datetime(dates)
    eff_i = _find_first_index_ge(idx, official_date)
    event = {
        "type": "OFFICIAL_SPLIT",
        "official_date": str(official_date),
        "effective_index": eff_i,
        "effective_date": None,
        "factor": float(factor),
        "tolerance": float(tol),
        "observed_ratio": None,
        "apply_multiplier_to_earlier": None,
        "applied": False,
        "note": None,
    }
    if eff_i is None or eff_i <= 0:
        event["note"] = "effective index not found or at start; skip"
        return s, event

    event["effective_date"] = str(pd.to_datetime(idx[eff_i]).date())

    p_prev = float(s.iloc[eff_i - 1])
    p_now = float(s.iloc[eff_i])
    if not (np.isfinite(p_prev) and np.isfinite(p_now)) or p_prev <= 0:
        event["note"] = "non-finite prices around event; skip"
        return s, event

    r = p_now / p_prev
    event["observed_ratio"] = float(r)

    if _is_close_ratio(r, 1.0 / factor, tol):
        mult = 1.0 / float(factor)
        s2 = s.copy()
        s2.iloc[:eff_i] = s2.iloc[:eff_i] * mult
        event["apply_multiplier_to_earlier"] = float(mult)
        event["applied"] = True
        event["note"] = "observed ~1/f, applied to earlier history"
        return s2, event

    if _is_close_ratio(r, 1.0, tol):
        event["note"] = "observed ~1.0; data likely already back-adjusted; no action"
        return s, event

    event["note"] = "ratio not near 1/f or 1.0; no action (manual audit recommended)"
    return s, event


def detect_and_heal_splits_auto(
    price_in: pd.Series,
    factors: List[float],
    tol: float,
    min_price: float = 0.01,
) -> Tuple[pd.Series, List[Dict[str, Any]]]:
    s = _to_1d_series(price_in, price_in.index, "price_auto_in")
    s = s.where(s > min_price)

    idx = s.index
    vals = s.to_numpy(dtype=float)
    n = len(vals)
    if n < 3:
        return s, []

    adj = vals.copy()
    events: List[Dict[str, Any]] = []

    for t in range(1, n):
        p_prev = adj[t - 1]
        p_now = adj[t]
        if not (np.isfinite(p_prev) and np.isfinite(p_now)) or p_prev <= 0:
            continue

        r = p_now / p_prev

        matched = None
        direction = None
        implied = None

        for f in factors:
            if _is_close_ratio(r, 1.0 / f, tol):
                matched = f
                direction = "SPLIT"
                implied = f
                break
            if _is_close_ratio(r, f, tol):
                matched = f
                direction = "REVERSE_SPLIT"
                implied = f
                break

        if matched is None:
            continue

        factor_apply = (1.0 / float(implied)) if direction == "SPLIT" else float(implied)
        adj[:t] = adj[:t] * factor_apply

        events.append(
            {
                "event_index": t,
                "event_date": str(pd.to_datetime(idx[t]).date()),
                "raw_ratio": float(r),
                "direction": direction,
                "implied_factor": float(implied),
                "tolerance": float(tol),
                "applied_to_range": f"[0:{t})",
                "apply_multiplier_to_earlier": float(factor_apply),
            }
        )

    price_adj = pd.Series(adj.reshape(-1), index=idx, name="price_auto_adj")
    return price_adj, events


def _gap_audit_weekday_only(dates: pd.DatetimeIndex, gap_busdays_warn: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    idx = pd.to_datetime(dates)
    idx = idx.sort_values()
    suspects: List[Dict[str, Any]] = []
    n = len(idx)

    if n < 2:
        return suspects, {"n": n, "gap_count": 0, "gap_busdays_warn": gap_busdays_warn, "weekday_heuristic": True}

    for i in range(1, n):
        d0 = idx[i - 1].date()
        d1 = idx[i].date()

        exp = pd.bdate_range(pd.Timestamp(d0), periods=2)[1].date()

        if d1 <= exp:
            continue

        miss = int(np.busday_count(exp, d1))
        if miss >= int(gap_busdays_warn):
            suspects.append({"from": str(d0), "to": str(d1), "missing_busdays": miss})

    meta = {
        "n": n,
        "gap_count": len(suspects),
        "gap_busdays_warn": int(gap_busdays_warn),
        "weekday_heuristic": True,
    }
    return suspects, meta


def _jump_audit(
    dates: pd.DatetimeIndex,
    close_raw: pd.Series,
    adjclose_raw: pd.Series,
    price_final: pd.Series,
    ret_jump_raw: float,
    ret_jump_adj: float,
    raw_jump_thr: float,
    adj_stable_thr: float,
    adj_factor_change_tol: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    idx = pd.to_datetime(dates)
    close_raw = _to_1d_series(close_raw, idx, "close_raw")
    adjclose_raw = _to_1d_series(adjclose_raw, idx, "adjclose_raw")
    price_final = _to_1d_series(price_final, idx, "price_final")

    ret_raw = close_raw.pct_change()
    ret_adj = price_final.pct_change()

    jump_suspects: List[Dict[str, Any]] = []

    for i in range(1, len(idx)):
        rr = ret_raw.iloc[i]
        ra = ret_adj.iloc[i]
        if np.isfinite(rr) and abs(float(rr)) >= float(ret_jump_raw):
            jump_suspects.append(
                {
                    "date": str(idx[i].date()),
                    "kind": "RET_JUMP_RAW",
                    "price_raw": None if not np.isfinite(close_raw.iloc[i]) else float(close_raw.iloc[i]),
                    "price_adj": None if not np.isfinite(price_final.iloc[i]) else float(price_final.iloc[i]),
                    "ret_raw": float(rr),
                    "ret_adj": None if not np.isfinite(ra) else float(ra),
                }
            )

    for i in range(1, len(idx)):
        ra = ret_adj.iloc[i]
        if np.isfinite(ra) and abs(float(ra)) >= float(ret_jump_adj):
            jump_suspects.append(
                {
                    "date": str(idx[i].date()),
                    "kind": "RET_JUMP_ADJ",
                    "price_raw": None if not np.isfinite(close_raw.iloc[i]) else float(close_raw.iloc[i]),
                    "price_adj": None if not np.isfinite(price_final.iloc[i]) else float(price_final.iloc[i]),
                    "ret_raw": None if not np.isfinite(ret_raw.iloc[i]) else float(ret_raw.iloc[i]),
                    "ret_adj": float(ra),
                }
            )

    for i in range(1, len(idx)):
        p0 = close_raw.iloc[i - 1]
        p1 = close_raw.iloc[i]
        ra = ret_adj.iloc[i]
        if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0):
            continue
        raw_jump = float(p1 / p0 - 1.0)
        if abs(raw_jump) >= float(raw_jump_thr) and (np.isfinite(ra) and abs(float(ra)) <= float(adj_stable_thr)):
            jump_suspects.append(
                {
                    "date": str(idx[i].date()),
                    "kind": "RAW_JUMP_ADJ_STABLE",
                    "price_raw": float(p1),
                    "price_adj": None if not np.isfinite(price_final.iloc[i]) else float(price_final.iloc[i]),
                    "ret_raw": raw_jump,
                    "ret_adj": float(ra),
                }
            )

    factor = adjclose_raw / close_raw
    factor_prev = factor.shift(1)
    factor_chg = (factor / factor_prev) - 1.0

    factor_change_suspects: List[Dict[str, Any]] = []
    for i in range(1, len(idx)):
        fc = factor_chg.iloc[i]
        if np.isfinite(fc) and abs(float(fc)) >= float(adj_factor_change_tol):
            factor_change_suspects.append(
                {
                    "date": str(idx[i].date()),
                    "yf_adj_factor": None if not np.isfinite(factor.iloc[i]) else float(factor.iloc[i]),
                    "yf_adj_factor_chg": float(fc),
                }
            )

    meta = {
        "n": int(len(idx)),
        "jump_count": int(len(jump_suspects)),
        "factor_change_count": int(len(factor_change_suspects)),
        "params": {
            "ret_jump_raw": float(ret_jump_raw),
            "ret_jump_adj": float(ret_jump_adj),
            "raw_jump_thr": float(raw_jump_thr),
            "adj_stable_thr": float(adj_stable_thr),
            "adj_factor_change_tol": float(adj_factor_change_tol),
        },
    }
    return jump_suspects, factor_change_suspects, meta


# ---------------------------
# main
# ---------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="TW0050 BB(60,2) + forward_mdd(20D) generator (official split aware)"
    )
    ap.add_argument("--symbol", default="0050.TW", help="Yahoo Finance symbol (default: 0050.TW)")
    ap.add_argument("--start", default="2003-01-01", help="Start date YYYY-MM-DD (default: 2003-01-01)")
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: None)")
    ap.add_argument("--window", type=int, default=60, help="BB window length (default: 60)")
    ap.add_argument("--k", type=float, default=2.0, help="BB k (default: 2.0)")
    ap.add_argument("--horizon", type=int, default=20, help="Forward MDD horizon in trading days (default: 20)")
    ap.add_argument("--cache_dir", default="tw0050_bb_cache", help="Output cache dir")
    ap.add_argument("--history_limit", type=int, default=400, help="Rows to keep in history_lite.json (default: 400)")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"Local timezone for age calculation (default: {DEFAULT_TZ})")

    ap.add_argument("--input_csv", default=None, help="Optional CSV input instead of yfinance")
    ap.add_argument("--csv_price_col", default="Adj Close", help="CSV price column name (default: 'Adj Close')")

    ap.add_argument("--use_adj_close", action="store_true", help="Use Adj Close for analysis")
    ap.add_argument("--use_close", action="store_true", help="Use Close for analysis (overrides --use_adj_close)")
    ap.add_argument("--use_logclose", action="store_true", help="Compute BB on log(price_final)")

    ap.add_argument("--official_split_date", default="114/06/17", help="Official split date (ROC or ISO). Default: 114/06/17")
    ap.add_argument("--official_split_factor", type=float, default=4.0, help="Official split factor (default: 4.0 for 4:1)")
    ap.add_argument("--official_split_tol", type=float, default=0.06, help="Tolerance for detecting split ratio (default: 0.06)")
    ap.add_argument("--disable_official_split", action="store_true", help="Disable official split handling")

    ap.add_argument("--enable_auto_split", action="store_true", help="Enable auto split detection/healing (USE WITH CARE)")
    ap.add_argument("--split_factors", default="4", help="Comma-separated split factors for auto mode (default: '4')")
    ap.add_argument("--split_tol", type=float, default=0.06, help="Tolerance for auto split detection (default: 0.06)")

    ap.add_argument("--z_cheap", type=float, default=-1.5, help="Cheap-side threshold (default: -1.5)")
    ap.add_argument("--z_hot", type=float, default=1.5, help="Hot-side threshold (default: 1.5)")
    ap.add_argument("--z_hot2", type=float, default=2.0, help="Extreme hot-side threshold (default: 2.0)")

    ap.add_argument("--gap_busdays_warn", type=int, default=2, help="Warn if missing business days >= this (default: 2)")
    ap.add_argument("--ret_jump_raw", type=float, default=0.2, help="abs(ret_raw) >= thr => jump suspect (default: 0.2)")
    ap.add_argument("--ret_jump_adj", type=float, default=0.2, help="abs(ret_adj) >= thr => jump suspect (default: 0.2)")
    ap.add_argument("--raw_jump_thr", type=float, default=0.2, help="abs(raw_jump) >= thr AND adj stable => suspect (default: 0.2)")
    ap.add_argument("--adj_stable_thr", type=float, default=0.05, help="abs(ret_adj) <= thr => considered stable (default: 0.05)")
    ap.add_argument("--adj_factor_change_tol", type=float, default=0.1, help="abs(yf_adj_factor_chg) >= tol => suspect (default: 0.1)")

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    script_fp = sha256_file(Path(__file__))

    dq: Dict[str, Any] = {
        "fetch_ok": False,
        "insufficient_history": False,
        "stale_days_local": None,
        "official_split_enabled": (not args.disable_official_split),
        "official_split_event": None,
        "auto_split_enabled": bool(args.enable_auto_split),
        "auto_split_events": [],
        "gap_suspects": [],
        "jump_suspects": [],
        "factor_change_suspects": [],
        "gap_audit": None,
        "notes": [],
    }

    # Load prices
    if args.input_csv:
        data_source = "csv"
        prices_df = read_csv_prices(Path(args.input_csv), args.csv_price_col)
        prices_df.index = pd.to_datetime(prices_df.index, errors="coerce")
        prices_df = prices_df.dropna()
        prices_df.index.name = "Date"

        close_raw = _to_1d_series(prices_df.iloc[:, 0], prices_df.index, "close_raw")
        adjclose_raw = close_raw.copy()
        price_basis = "csv:" + str(args.csv_price_col)

        if args.use_close:
            price_selected = close_raw.copy()
            price_selected_basis = "Close(csv)"
        else:
            price_selected = adjclose_raw.copy()
            price_selected_basis = "AdjClose(csv)"
    else:
        data_source = "yfinance"
        df = fetch_yahoo_prices(args.symbol, args.start, args.end)

        close_s = _extract_yf_series(df, "Close", args.symbol)

        # try get Adj Close safely
        try:
            adj_s = _extract_yf_series(df, "Adj Close", args.symbol)
            has_adj = True
        except Exception:
            adj_s = None
            has_adj = False

        close_raw = _to_1d_series(close_s, df.index, "close_raw")
        if not has_adj or adj_s is None:
            adjclose_raw = close_raw.copy()
            dq["notes"].append("Adj Close not found; using Close as adjclose_raw fallback.")
        else:
            adjclose_raw = _to_1d_series(adj_s, df.index, "adjclose_raw")

        if args.use_close:
            price_selected = close_raw.copy()
            price_selected_basis = "Close"
        else:
            price_selected = adjclose_raw.copy()
            price_selected_basis = "Adj Close"

        price_basis = price_selected_basis

    if price_selected.dropna().empty:
        raise RuntimeError("No usable price data loaded.")

    dq["fetch_ok"] = True

    dates = pd.to_datetime(price_selected.index, errors="coerce")
    close_raw = _to_1d_series(close_raw, dates, "close_raw")
    adjclose_raw = _to_1d_series(adjclose_raw, dates, "adjclose_raw")
    price_selected = _to_1d_series(price_selected, dates, "price_selected_raw")

    # Official split (safe)
    price_after_official = price_selected.copy()
    if not args.disable_official_split:
        try:
            off_date = _parse_roc_or_iso_date(args.official_split_date)
            price_after_official, off_event = apply_official_split_if_needed(
                price_selected=price_after_official,
                dates=dates,
                official_date=off_date,
                factor=float(args.official_split_factor),
                tol=float(args.official_split_tol),
            )
            dq["official_split_event"] = off_event
            if off_event and off_event.get("applied"):
                dq["notes"].append(
                    f"Official split applied: official_date={off_event.get('official_date')} effective_date={off_event.get('effective_date')} factor={args.official_split_factor}"
                )
            else:
                dq["notes"].append(
                    f"Official split recorded (no adjustment): official_date={off_event.get('official_date')} effective_date={off_event.get('effective_date')}"
                )
        except Exception as e:
            dq["notes"].append(f"Official split step failed: {type(e).__name__}: {e}")

    # Auto split (optional)
    price_final = price_after_official.copy()
    if args.enable_auto_split:
        try:
            factors: List[float] = []
            for tok in str(args.split_factors).split(","):
                tok = tok.strip()
                if tok:
                    factors.append(float(tok))
            if not factors:
                factors = [4.0]

            price_final, auto_events = detect_and_heal_splits_auto(
                price_in=price_final,
                factors=factors,
                tol=float(args.split_tol),
            )
            dq["auto_split_events"] = auto_events
            if auto_events:
                dq["notes"].append(f"Auto split heal applied: detected_events={len(auto_events)} factors={factors} tol={args.split_tol}")
            else:
                dq["notes"].append(f"Auto split enabled but no events detected (factors={factors}, tol={args.split_tol})")
        except Exception as e:
            dq["notes"].append(f"Auto split step failed: {type(e).__name__}: {e}")

    # prices.csv
    yf_adj_factor = (adjclose_raw / close_raw).replace([np.inf, -np.inf], np.nan)

    prices_out = pd.DataFrame(
        {
            "date": pd.to_datetime(dates).date.astype(str),
            "close_raw": close_raw.to_numpy(dtype=float),
            "adjclose_raw": adjclose_raw.to_numpy(dtype=float),
            "price_selected_raw": price_selected.to_numpy(dtype=float),
            "price_final": _to_1d_series(price_final, dates, "price_final").to_numpy(dtype=float),
            "yf_adj_factor": yf_adj_factor.to_numpy(dtype=float),
        }
    )
    prices_out.to_csv(cache_dir / "prices.csv", index=False)

    # gap & jump audits
    gap_suspects, gap_meta = _gap_audit_weekday_only(dates, int(args.gap_busdays_warn))
    dq["gap_suspects"] = gap_suspects
    dq["gap_audit"] = {
        "n": int(gap_meta.get("n", 0)),
        "gap_count": int(gap_meta.get("gap_count", 0)),
        "gap_busdays_warn": int(args.gap_busdays_warn),
        "weekday_heuristic": True,
        "params": {
            "gap_busdays_warn": int(args.gap_busdays_warn),
            "ret_jump_raw": float(args.ret_jump_raw),
            "ret_jump_adj": float(args.ret_jump_adj),
            "raw_jump_thr": float(args.raw_jump_thr),
            "adj_stable_thr": float(args.adj_stable_thr),
            "adj_factor_change_tol": float(args.adj_factor_change_tol),
        },
    }
    dq["notes"].append("Gap audit uses weekday heuristic only (market holidays not modeled).")
    if gap_suspects:
        dq["notes"].append(f"GAP_WARNING: missing business days detected (count={len(gap_suspects)})")

    jump_suspects, factor_change_suspects, _ = _jump_audit(
        dates=dates,
        close_raw=close_raw,
        adjclose_raw=adjclose_raw,
        price_final=price_final,
        ret_jump_raw=float(args.ret_jump_raw),
        ret_jump_adj=float(args.ret_jump_adj),
        raw_jump_thr=float(args.raw_jump_thr),
        adj_stable_thr=float(args.adj_stable_thr),
        adj_factor_change_tol=float(args.adj_factor_change_tol),
    )
    dq["jump_suspects"] = jump_suspects
    dq["factor_change_suspects"] = factor_change_suspects
    if jump_suspects:
        dq["notes"].append(f"JUMP_WARNING: return jumps detected (count={len(jump_suspects)})")
    if factor_change_suspects:
        dq["notes"].append(f"FACTOR_WARNING: raw/adj factor changes detected (count={len(factor_change_suspects)})")

    # Compute indicators
    price_final = _to_1d_series(price_final, dates, "price_final")

    if args.use_logclose:
        base = np.log(price_final)
        bb_base_label = "log(price_final)"
    else:
        base = price_final.copy()
        bb_base_label = "price_final"

    win = int(args.window)
    horizon = int(args.horizon)

    if len(base) < win + horizon + 5:
        dq["insufficient_history"] = True
        dq["notes"].append(
            f"Insufficient length: need roughly window+horizon; len={len(base)}, window={win}, horizon={horizon}"
        )

    base = _to_1d_series(base, dates, "bb_base")

    sma = base.rolling(window=win, min_periods=win).mean()
    std = base.rolling(window=win, min_periods=win).std(ddof=0)

    upper = sma + float(args.k) * std
    lower = sma - float(args.k) * std

    z = (base - sma) / std
    band_w = upper - lower
    pos = (base - lower) / band_w

    if args.use_logclose:
        lower_px = np.exp(lower)
        upper_px = np.exp(upper)
        dist_to_lower = (price_final - lower_px) / price_final
        dist_to_upper = (upper_px - price_final) / price_final
    else:
        dist_to_lower = (price_final - lower) / price_final
        dist_to_upper = (upper - price_final) / price_final

    price_np = np.asarray(price_final.to_numpy()).astype(float).reshape(-1)
    fwd_mdd = calc_forward_mdd(price_np, horizon)

    sma = _to_1d_series(sma, dates, "sma")
    std = _to_1d_series(std, dates, "std")
    upper = _to_1d_series(upper, dates, "upper")
    lower = _to_1d_series(lower, dates, "lower")
    z = _to_1d_series(z, dates, "z")
    pos = _to_1d_series(pos, dates, "pos")
    dist_to_lower = _to_1d_series(dist_to_lower, dates, "dist_to_lower")
    dist_to_upper = _to_1d_series(dist_to_upper, dates, "dist_to_upper")
    fwd_mdd_s = _to_1d_series(fwd_mdd, dates, "forward_mdd")

    last_dt = pd.to_datetime(dates[-1]).date()
    today_local = local_today(args.tz)
    dq["stale_days_local"] = int((today_local - last_dt).days)

    out_df = pd.DataFrame(
        {
            "price": price_final,
            "bb_base": base,
            "sma": sma,
            "std": std,
            "upper": upper,
            "lower": lower,
            "z": z,
            "pos": pos,
            "dist_to_lower": dist_to_lower,
            "dist_to_upper": dist_to_upper,
            "forward_mdd": fwd_mdd_s,
        },
        index=dates,
    )

    lite = out_df.tail(int(args.history_limit)).copy()
    lite = lite.reset_index().rename(columns={"Date": "date", "index": "date"})
    lite["date"] = pd.to_datetime(lite["date"]).dt.date.astype(str)

    history_lite: List[Dict[str, Any]] = []
    for _, r in lite.iterrows():
        def _f(x):
            return None if not np.isfinite(x) else float(x)

        history_lite.append(
            {
                "date": r["date"],
                "price": _f(r["price"]),
                "sma": _f(r["sma"]),
                "std": _f(r["std"]),
                "upper": _f(r["upper"]),
                "lower": _f(r["lower"]),
                "z": _f(r["z"]),
                "pos": _f(r["pos"]),
                "dist_to_lower": _f(r["dist_to_lower"]),
                "dist_to_upper": _f(r["dist_to_upper"]),
                "forward_mdd": _f(r["forward_mdd"]),
            }
        )
    write_json(cache_dir / "history_lite.json", history_lite)

    last_row = out_df.iloc[-1]
    z_last = None if not np.isfinite(last_row["z"]) else float(last_row["z"])
    state, state_reason = bb_state_from_z(z_last)

    mdd_all = out_df["forward_mdd"].to_numpy()
    z_arr = out_df["z"].to_numpy()

    stats_all = compute_mdd_stats(mdd_all)

    z_cheap = float(args.z_cheap)
    mask_cheap = np.isfinite(mdd_all) & np.isfinite(z_arr) & (z_arr <= z_cheap)
    stats_cheap = compute_mdd_stats(out_df.loc[mask_cheap, "forward_mdd"].to_numpy())
    stats_cheap["condition"] = f"z <= {z_cheap}"
    stats_cheap["z_threshold"] = z_cheap

    z_hot = float(args.z_hot)
    mask_hot = np.isfinite(mdd_all) & np.isfinite(z_arr) & (z_arr >= z_hot)
    stats_hot = compute_mdd_stats(out_df.loc[mask_hot, "forward_mdd"].to_numpy())
    stats_hot["condition"] = f"z >= {z_hot}"
    stats_hot["z_threshold"] = z_hot

    z_hot2 = float(args.z_hot2)
    mask_hot2 = np.isfinite(mdd_all) & np.isfinite(z_arr) & (z_arr >= z_hot2)
    stats_hot2 = compute_mdd_stats(out_df.loc[mask_hot2, "forward_mdd"].to_numpy())
    stats_hot2["condition"] = f"z >= {z_hot2}"
    stats_hot2["z_threshold"] = z_hot2

    stats_latest = {
        "meta": {
            "run_ts_utc": utc_now_iso(),
            "module": "tw0050_bb",
            "symbol": args.symbol,
            "data_source": data_source,
            "price_basis": price_basis,
            "bb_base": bb_base_label,
            "window": int(args.window),
            "k": float(args.k),
            "horizon": int(args.horizon),
            "script_fingerprint": script_fp,
            "timezone_local": args.tz,
            "as_of_date": str(last_dt),

            "gap_busdays_warn": int(args.gap_busdays_warn),
            "ret_jump_raw": float(args.ret_jump_raw),
            "ret_jump_adj": float(args.ret_jump_adj),
            "raw_jump_thr": float(args.raw_jump_thr),
            "adj_stable_thr": float(args.adj_stable_thr),
            "adj_factor_change_tol": float(args.adj_factor_change_tol),

            "official_split_date": str(args.official_split_date),
            "official_split_factor": float(args.official_split_factor),
            "official_split_tol": float(args.official_split_tol),
            "auto_split_enabled": bool(args.enable_auto_split),
            "split_factors": str(args.split_factors),
            "split_tol": float(args.split_tol),

            "z_threshold_cheap": float(args.z_cheap),
            "z_threshold_hot": float(args.z_hot),
            "z_threshold_hot2": float(args.z_hot2),
        },
        "dq": dq,
        "latest": {
            "date": str(last_dt),
            "price": None if not np.isfinite(last_row["price"]) else float(last_row["price"]),
            "sma": None if not np.isfinite(last_row["sma"]) else float(last_row["sma"]),
            "std": None if not np.isfinite(last_row["std"]) else float(last_row["std"]),
            "upper": None if not np.isfinite(last_row["upper"]) else float(last_row["upper"]),
            "lower": None if not np.isfinite(last_row["lower"]) else float(last_row["lower"]),
            "z": z_last,
            "pos": None if not np.isfinite(last_row["pos"]) else float(last_row["pos"]),
            "dist_to_lower_pct": None if not np.isfinite(last_row["dist_to_lower"]) else float(last_row["dist_to_lower"] * 100.0),
            "dist_to_upper_pct": None if not np.isfinite(last_row["dist_to_upper"]) else float(last_row["dist_to_upper"] * 100.0),
            "state": state,
            "state_reason": state_reason,
        },
        "forward_mdd": {
            "definition": "min(0, min_{i=1..H} (price[t+i]/price[t]-1)), H=horizon trading days",
            "all_days": stats_all,
            "conditional": {
                "cheap_side": stats_cheap,
                "hot_side": stats_hot,
                "hot_side_extreme": stats_hot2,
            },
        },
    }

    write_json(cache_dir / "stats_latest.json", stats_latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
