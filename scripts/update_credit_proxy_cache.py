import argparse
import csv
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import requests

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None  # type: ignore

# -------------------------
# Paths / Outputs
# -------------------------
OUT_DIR = "credit_proxy_cache"
LATEST_JSON = os.path.join(OUT_DIR, "latest.json")
HISTORY_JSON = os.path.join(OUT_DIR, "history.json")
LATEST_CSV = os.path.join(OUT_DIR, "latest.csv")
MANIFEST_JSON = os.path.join(OUT_DIR, "manifest.json")

# -------------------------
# Config
# -------------------------
SCRIPT_VERSION = "credit_proxy_cache_v1.1"
MAX_HISTORY_ROWS = 720  # ratio 每天最多 1 筆；720 夠用很久，也不會太大

SYMBOL_HYG = "hyg.us"
SYMBOL_IEF = "ief.us"

# Stooq daily CSV:
# https://stooq.com/q/d/l/?s={sym}&d1={YYYYMMDD}&d2={YYYYMMDD}&i=d
STOOQ_URL_TMPL = "https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"

REQUEST_TIMEOUT = 20
RETRY = 3
BACKOFF_SEC = [2, 4, 8]


# -------------------------
# Helpers
# -------------------------
def safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _tzinfo():
    """
    Prefer TZ (GitHub style) then TIMEZONE. Fallback to Asia/Taipei, final fallback fixed +08:00.
    """
    tz_name = (os.environ.get("TZ") or os.environ.get("TIMEZONE") or "Asia/Taipei").strip() or "Asia/Taipei"

    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            try:
                return ZoneInfo("Asia/Taipei")
            except Exception:
                return timezone(timedelta(hours=8))

    # no zoneinfo
    if tz_name == "Asia/Taipei":
        return timezone(timedelta(hours=8))
    return timezone.utc


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_local_iso(tz) -> str:
    # e.g. 2026-01-06T22:30:00+08:00
    return datetime.now(tz).replace(microsecond=0).isoformat()


def yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def http_get_text(url: str) -> str:
    last_err = None
    for i in range(RETRY):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if i < RETRY - 1:
                time.sleep(BACKOFF_SEC[i])
    raise RuntimeError(f"GET failed after retries: {url} :: {last_err}")


def parse_stooq_daily_csv(text: str) -> List[Dict[str, str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or "Date," not in lines[0]:
        return []
    reader = csv.DictReader(lines)
    rows: List[Dict[str, str]] = []
    for row in reader:
        if row.get("Date") and row.get("Close"):
            rows.append(row)
    return rows


def to_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def pick_latest_common_close(
    hyg_rows: List[Dict[str, str]],
    ief_rows: List[Dict[str, str]],
) -> Optional[Tuple[str, float, float]]:
    hyg_map = {r["Date"]: to_float(r["Close"]) for r in hyg_rows if to_float(r["Close"]) is not None}
    ief_map = {r["Date"]: to_float(r["Close"]) for r in ief_rows if to_float(r["Close"]) is not None}

    common_dates = sorted(set(hyg_map.keys()) & set(ief_map.keys()))
    if not common_dates:
        return None

    d = common_dates[-1]
    return d, float(hyg_map[d]), float(ief_map[d])


def _atomic_write_text(path: str, text: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def write_json(path: str, obj) -> None:
    # atomic JSON write
    safe_mkdir(os.path.dirname(path) or ".")
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    _atomic_write_text(path, text)


def read_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # bad json / partial file => treat as missing
        return None


def read_history() -> List[Dict]:
    data = read_json(HISTORY_JSON)
    return data if isinstance(data, list) else []


def write_latest_csv(rows: List[Dict]) -> None:
    safe_mkdir(OUT_DIR)
    fieldnames = ["series_id", "data_date", "value", "source_url", "notes", "as_of_ts"]
    with open(LATEST_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def build_manifest(data_sha: str, as_of_ts_iso: str) -> Dict:
    repo = os.environ.get("GITHUB_REPOSITORY", "NA")
    base = f"https://raw.githubusercontent.com/{repo}/{data_sha}/{OUT_DIR}"
    branch_manifest = f"https://raw.githubusercontent.com/{repo}/main/{OUT_DIR}/manifest.json"
    return {
        "generated_at_utc": now_utc_iso(),
        "as_of_ts": as_of_ts_iso,
        "data_commit_sha": data_sha,
        "pinned": {
            "latest_json": f"{base}/latest.json",
            "history_json": f"{base}/history.json",
            "latest_csv": f"{base}/latest.csv",
            # ✅ 對齊其他 sidecar：提供 manifest_json
            # 仍是 branch 入口（可能有 cache），但讀到 data_commit_sha 後會再跳 pinned data
            "manifest_json": branch_manifest,
            # ✅ 相容欄位：保留你原本的命名
            "manifest_json_branch": branch_manifest,
        },
    }


# -------------------------
# Modes
# -------------------------
def run_mode_data() -> None:
    safe_mkdir(OUT_DIR)
    tz = _tzinfo()
    as_of_ts = now_local_iso(tz)

    # use local "today" to avoid boundary surprises for Taipei users
    now_local = datetime.now(tz)
    d2 = yyyymmdd(now_local)
    d1 = yyyymmdd(now_local - timedelta(days=120))

    url_hyg = STOOQ_URL_TMPL.format(sym=SYMBOL_HYG, d1=d1, d2=d2)
    url_ief = STOOQ_URL_TMPL.format(sym=SYMBOL_IEF, d1=d1, d2=d2)

    latest_rows: List[Dict] = [{
        "series_id": "__META__",
        "data_date": now_local.strftime("%Y-%m-%d"),
        "value": SCRIPT_VERSION,
        "source_url": "NA",
        "notes": "INFO:script_version",
        "as_of_ts": as_of_ts,
    }]

    history = read_history()

    try:
        hyg_text = http_get_text(url_hyg)
        ief_text = http_get_text(url_ief)
        hyg_rows = parse_stooq_daily_csv(hyg_text)
        ief_rows = parse_stooq_daily_csv(ief_text)
        latest = pick_latest_common_close(hyg_rows, ief_rows)
    except Exception as e:
        # 不中斷：latest 補 NA；history 不新增（避免污染）
        latest_rows.append({
            "series_id": "HYG_IEF_RATIO",
            "data_date": "NA",
            "value": "NA",
            "source_url": f"{url_hyg} | {url_ief}",
            "notes": f"NA:fetch_or_parse_failed:{type(e).__name__}",
            "as_of_ts": as_of_ts,
        })
        write_json(LATEST_JSON, latest_rows)
        write_json(HISTORY_JSON, history)  # ✅ ensure file exists / remains valid
        write_latest_csv(latest_rows)
        return

    if latest is None:
        latest_rows.append({
            "series_id": "HYG_IEF_RATIO",
            "data_date": "NA",
            "value": "NA",
            "source_url": f"{url_hyg} | {url_ief}",
            "notes": "NA:no_common_date_or_no_data",
            "as_of_ts": as_of_ts,
        })
        write_json(LATEST_JSON, latest_rows)
        write_json(HISTORY_JSON, history)
        write_latest_csv(latest_rows)
        return

    data_date, hyg_close, ief_close = latest
    ratio = (hyg_close / ief_close) if ief_close != 0 else None

    latest_rows.extend([
        {
            "series_id": "HYG_CLOSE",
            "data_date": data_date,
            "value": hyg_close,
            "source_url": url_hyg,
            "notes": "close_price_common_date",
            "as_of_ts": as_of_ts,
        },
        {
            "series_id": "IEF_CLOSE",
            "data_date": data_date,
            "value": ief_close,
            "source_url": url_ief,
            "notes": "close_price_common_date",
            "as_of_ts": as_of_ts,
        },
        {
            "series_id": "HYG_IEF_RATIO",
            "data_date": data_date,
            "value": ratio if ratio is not None else "NA",
            "source_url": f"{url_hyg} | {url_ief}",
            "notes": f"ratio=HYG_CLOSE/IEF_CLOSE; hyg_close={hyg_close}; ief_close={ief_close}",
            "as_of_ts": as_of_ts,
        },
    ])

    # ---------- history append with dedupe (same data_date won't grow) ----------
    exists = any(
        isinstance(r, dict)
        and r.get("series_id") == "HYG_IEF_RATIO"
        and r.get("data_date") == data_date
        for r in history
    )

    if not exists:
        history.append({
            "series_id": "HYG_IEF_RATIO",
            "data_date": data_date,
            "value": ratio if ratio is not None else "NA",
            "source_url": f"{url_hyg} | {url_ief}",
            "notes": f"hyg_close={hyg_close}; ief_close={ief_close}",
            "as_of_ts": as_of_ts,
        })

        if len(history) > MAX_HISTORY_ROWS:
            history = history[-MAX_HISTORY_ROWS:]

    write_json(LATEST_JSON, latest_rows)
    write_json(HISTORY_JSON, history)
    write_latest_csv(latest_rows)


def run_mode_manifest(data_sha: str) -> None:
    safe_mkdir(OUT_DIR)
    tz = _tzinfo()
    as_of_ts = now_local_iso(tz)
    manifest = build_manifest(data_sha=data_sha, as_of_ts_iso=as_of_ts)
    write_json(MANIFEST_JSON, manifest)


def extract_latest_ratio_date_from_latest_json() -> str:
    data = read_json(LATEST_JSON)
    if not isinstance(data, list):
        return "NA"
    for r in data:
        if isinstance(r, dict) and r.get("series_id") == "HYG_IEF_RATIO":
            return str(r.get("data_date", "NA"))
    return "NA"


def run_mode_check() -> None:
    history = read_history()
    history_records = len(history)

    days = [
        r.get("data_date") for r in history
        if isinstance(r, dict) and r.get("data_date") and r.get("data_date") != "NA"
    ]
    days_in_history = sorted(set(days))

    rows_per_day: Dict[str, int] = {}
    for d in days:
        rows_per_day[d] = rows_per_day.get(d, 0) + 1

    pairs = []
    for r in history:
        if not isinstance(r, dict):
            continue
        sid = r.get("series_id")
        d = r.get("data_date")
        if sid and d:
            pairs.append((sid, d))
    dedupe_ok = (len(set(pairs)) == len(pairs))

    cap_records = MAX_HISTORY_ROWS
    cap_ok = (history_records <= cap_records)

    rows_per_day_ok = all(v == 1 for v in rows_per_day.values()) if rows_per_day else True

    latest_ratio_date = extract_latest_ratio_date_from_latest_json()
    history_last_date = days_in_history[-1] if days_in_history else "NA"

    print(f"history_records = {history_records}")
    print(f"days_in_history = {days_in_history}")
    print(f"rows_per_day    = {rows_per_day}")
    print(f"dedupe_ok       = {dedupe_ok}")
    print(f"cap_records     = {cap_records}  cap_ok = {cap_ok}")
    print(f"rows_per_day_ok = {rows_per_day_ok}")
    print(f"latest_ratio_date = {latest_ratio_date}")
    print(f"history_last_date = {history_last_date}")


# -------------------------
# Entrypoint
# -------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["data", "manifest", "check"], required=True)
    p.add_argument("--data-sha", default="")
    args = p.parse_args()

    if args.mode == "data":
        run_mode_data()
    elif args.mode == "manifest":
        if not args.data_sha:
            raise SystemExit("ERROR: --data-sha is required in manifest mode")
        run_mode_manifest(args.data_sha)
    else:
        run_mode_check()


if __name__ == "__main__":
    main()