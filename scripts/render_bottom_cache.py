#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottom_cache renderer (v0.1.10)

- Global bottom/reversal workflow from market_cache (single-source):
    * market_cache/stats_latest.json
- TW local gate from existing repo outputs (no fetch):
    * roll25_cache/latest_report.json
    * taiwan_margin_cache/latest.json

Outputs (ONE folder):
- dashboard_bottom_cache/latest.json
- dashboard_bottom_cache/history.json
- dashboard_bottom_cache/report.md

Principles:
- Deterministic rules only; no guessing.
- Missing fields => NA + excluded reasons.
- TW leverage heat: flow-only signal is always computed if enough rows.
  Optional "level gate" is applied when there are enough balance points; otherwise DOWNGRADED (does not NA-out the flow signal).

Patch v0.1.7:
- Always back up existing history.json BEFORE parsing/writing.
- Report history_pre_items / history_post_items and backup status (file + bytes).

Patch v0.1.8 (hardening):
- Fail-Closed history writes:
    * If history.json exists but load/parse is not OK => default SKIP writing history (avoid clobber).
    * Allow explicit reset only when env BOTTOM_HISTORY_ALLOW_RESET=1.
- Shrink Guard (unique TPE day buckets):
    * If unique day buckets decrease => default SKIP writing history (avoid silent shrink).
    * Allow override only when env BOTTOM_HISTORY_ALLOW_SHRINK=1.
- Backup retention:
    * Keep last N backups (default 30; env BOTTOM_HISTORY_BACKUP_KEEP_N).
- Reset leaves trace in latest.json/report.md when executed.

Patch v0.1.9 (TW panic hardening):
- ConsecutiveBreak>=2 no longer counts as stress by itself.
  It must be paired with (VolumeAmplified OR VolAmplified OR NewLow_N>=1) to count as stress.
  This reduces false positives for TW_BOTTOM_WATCH.

Patch v0.1.10 (auditability):
- report.md prints roll25 raw fields (DownDay/VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak)
  and the paired_basis used by v0.1.9 (VolumeAmplified OR VolAmplified OR NewLow_N>=1).
- latest.json also includes stress_consec_pair_basis + rule string under tw_local_gate.signals.

Note:
- This script does NOT fetch external URLs directly. It only reads local JSON files produced by other workflows.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo

TZ_TPE = ZoneInfo("Asia/Taipei")
RENDERER_VERSION = "v0.1.10"

# ---- config ----
MARKET_STATS_PATH = "market_cache/stats_latest.json"

# TW inputs (existing workflow outputs, no fetch)
TW_ROLL25_REPORT_PATH = "roll25_cache/latest_report.json"
TW_MARGIN_PATH = "taiwan_margin_cache/latest.json"

# unified output folder
OUT_DIR = "dashboard_bottom_cache"
OUT_LATEST = f"{OUT_DIR}/latest.json"
OUT_HISTORY = f"{OUT_DIR}/history.json"
OUT_MD = f"{OUT_DIR}/report.md"

# what we need from market_cache
NEEDED = ["VIX", "SP500", "HYG_IEF_RATIO", "OFR_FSI"]

# risk direction is a RULE (not guessed)
RISK_DIR = {
    "VIX": "HIGH",
    "OFR_FSI": "HIGH",
    "HYG_IEF_RATIO": "LOW",
    "SP500": "LOW",
}

# v0 thresholds (deterministic)
TH_VIX_PANIC = 20.0
TH_SPX_RET1_PANIC = -1.5     # unit = percent (%)
TH_HYG_VETO_Z = -2.0         # systemic credit stress veto (LOW direction)
TH_OFR_VETO_Z = 2.0          # systemic stress veto (HIGH direction)

HISTORY_SHOW_N = 10

# --- TW panic semantics (deterministic numeric thresholds) ---
TH_TW_CONSEC_BREAK_STRESS = 2       # ConsecutiveBreak >= 2 is eligible stress
TH_TW_NEWLOW_STRESS_MIN = 1         # NewLow_N >= 1 counts as stress

# v0.1.9 change: ConsecutiveBreak must be paired with (volume or newlow) to count as stress
TW_CONSEC_STRESS_REQUIRE_PAIR = True
TW_CONSEC_PAIR_BASIS_RULE = "VolumeAmplified OR VolAmplified OR (NewLow_N>=1)"

# --- TW margin flow thresholds (億) ---
TW_MARGIN_WATCH_SUM5_YI = 100.0
TW_MARGIN_ALERT_SUM5_YI = 150.0
TW_MARGIN_POSDAYS5_MIN = 4
TW_MARGIN_FLOW_MIN_POINTS = 5       # require last5 fully available for strictness

# --- OPTIONAL: TW margin level gate (balance percentile) ---
TW_MARGIN_LEVEL_GATE_ENABLED = True
TW_MARGIN_LEVEL_MIN_POINTS = 60     # below this => downgrade to flow-only
TW_MARGIN_LEVEL_WINDOW = 252        # use up to last252 points if available
TW_MARGIN_LEVEL_P_MIN = 95.0        # high percentile => "level is extreme"

# --- history hardening controls (env overrides) ---
ENV_ALLOW_RESET = "BOTTOM_HISTORY_ALLOW_RESET"
ENV_ALLOW_SHRINK = "BOTTOM_HISTORY_ALLOW_SHRINK"
ENV_RESET_REASON = "BOTTOM_HISTORY_RESET_REASON"
ENV_BACKUP_KEEP_N = "BOTTOM_HISTORY_BACKUP_KEEP_N"
DEFAULT_BACKUP_KEEP_N = 30


# ---------------- basic io ----------------

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tpe_now() -> str:
    return datetime.now(TZ_TPE).isoformat()


def _safe_ts_for_filename(run_ts_utc: str) -> str:
    # "2026-02-01T09:56:54.083393Z" -> "20260201T095654Z" (drop subseconds)
    try:
        dt = datetime.fromisoformat(run_ts_utc.replace("Z", "+00:00"))
        return dt.strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        s = run_ts_utc.replace(":", "").replace("-", "").replace(".", "")
        return s.replace("Z", "Z")


# ---------------- type coercion ----------------

def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            return float(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return float(s)
    except Exception:
        return None


def _as_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return int(x)
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)
        s = str(x).strip()
        if s == "" or s.upper() == "NA":
            return None
        return int(float(s))
    except Exception:
        return None


def _as_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    s = str(x).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def _as_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x)
    if s.strip() == "" or s.strip().upper() == "NA":
        return None
    return s


def _get(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


# ---------------- formatting helpers ----------------

def _series_signal(z60: Optional[float], p252: Optional[float]) -> Optional[str]:
    if z60 is None and p252 is None:
        return None
    if z60 is not None and abs(z60) >= 2.5:
        return "ALERT"
    if z60 is not None and abs(z60) >= 2.0:
        return "WATCH"
    if p252 is not None and (p252 >= 95.0 or p252 <= 5.0):
        return "INFO"
    return "NONE"


def _day_key_tpe_from_iso(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_TPE)
        return dt.date().isoformat()
    except Exception:
        return "NA"


def _safe_float_str(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "NA"
    fmt = f"{{:.{nd}f}}"
    return fmt.format(float(x))


def _iso_sort_key(iso: str) -> Tuple[int, str]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (int(dt.timestamp()), iso)
    except Exception:
        return (0, iso)


def _fmt_na(x: Any) -> str:
    """
    Normalize any null-ish value for report rendering.
    IMPORTANT: "NONE" is a legitimate signal value and must NOT be rendered as "NA".

    - None -> "NA"
    - empty string -> "NA"
    - "NA"/"N/A"/"NULL"/"NaN" (case-insensitive) -> "NA"
    - legacy null strings: "None" or "none" -> "NA"  (but "NONE" stays "NONE")
    Otherwise -> str(x)
    """
    if x is None:
        return "NA"

    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return "NA"

        up = s.upper()
        if up in ("NA", "N/A", "NULL", "NAN"):
            return "NA"

        # legacy null strings (do NOT collapse "NONE")
        if s in ("None", "none"):
            return "NA"

        return s

    return str(x)


def _canon_margin_signal(x: Any) -> Optional[str]:
    """
    Canonicalize margin signal:
    - returns one of {"NONE","WATCH","ALERT"} or None
    - treats "NA"/"None"/""/"null"/"nan" as None
    - normalizes case (e.g., "watch" -> "WATCH")
    """
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return None
        up = s.upper()
        if up in ("NA", "N/A", "NULL", "NAN"):
            return None
        if s in ("None", "none"):
            return None
        if up in ("NONE", "WATCH", "ALERT"):
            return up
        return None
    return None


def _env_flag(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    try:
        s = os.environ.get(name, "").strip()
        if s == "":
            return default
        return max(0, int(float(s)))
    except Exception:
        return default


# ---------------- TW helpers ----------------

def _load_tw_roll25(excluded: List[Dict[str, str]]) -> Tuple[Dict[str, Any], bool]:
    if not os.path.exists(TW_ROLL25_REPORT_PATH):
        excluded.append({"trigger": "TW:INPUT_ROLL25", "reason": "not_available:file_not_found"})
        return ({}, False)
    try:
        obj = _read_json(TW_ROLL25_REPORT_PATH)
        return (obj if isinstance(obj, dict) else {}, True)
    except Exception as e:
        excluded.append({"trigger": "TW:INPUT_ROLL25", "reason": f"read_or_parse_failed:{type(e).__name__}"})
        return ({}, False)


def _load_tw_margin(excluded: List[Dict[str, str]]) -> Tuple[Dict[str, Any], bool]:
    if not os.path.exists(TW_MARGIN_PATH):
        excluded.append({"trigger": "TW:INPUT_MARGIN", "reason": "not_available:file_not_found"})
        return ({}, False)
    try:
        obj = _read_json(TW_MARGIN_PATH)
        return (obj if isinstance(obj, dict) else {}, True)
    except Exception as e:
        excluded.append({"trigger": "TW:INPUT_MARGIN", "reason": f"read_or_parse_failed:{type(e).__name__}"})
        return ({}, False)


def _sort_rows_newest_first(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _k(r: Dict[str, Any]) -> str:
        return _as_str(r.get("date")) or ""
    # dates are YYYY-MM-DD; lexical sort works
    return sorted(rows, key=_k, reverse=True)


def _derive_margin_flow_signal(rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Flow-only leverage heat signal from TWSE rows (chg_yi):
    - WATCH if sum_last5 >= 100 and pos_days_last5 >= 4
    - ALERT if sum_last5 >= 150 and pos_days_last5 >= 4
    Returns (signal, dbg); signal=None => NA (insufficient data)
    """
    if not isinstance(rows, list) or len(rows) == 0:
        return (None, {"reason": "rows_empty_or_invalid"})

    rows2 = _sort_rows_newest_first([r for r in rows if isinstance(r, dict)])
    last5 = rows2[:5]
    chgs: List[float] = []
    for r in last5:
        v = _as_float(r.get("chg_yi"))
        chgs.append(float("nan") if v is None else float(v))

    if len(chgs) < TW_MARGIN_FLOW_MIN_POINTS or any(str(x) == "nan" for x in chgs):
        return (
            None,
            {
                "reason": "insufficient_flow_points_or_nan",
                "need_points": TW_MARGIN_FLOW_MIN_POINTS,
                "have_points": len(chgs),
                "chg_last5_yi": chgs,
            },
        )

    sum5 = float(sum(chgs))
    pos_days = sum(1 for x in chgs if x > 0)

    sig = "NONE"
    if pos_days >= TW_MARGIN_POSDAYS5_MIN and sum5 >= TW_MARGIN_ALERT_SUM5_YI:
        sig = "ALERT"
    elif pos_days >= TW_MARGIN_POSDAYS5_MIN and sum5 >= TW_MARGIN_WATCH_SUM5_YI:
        sig = "WATCH"

    dbg = {
        "chg_last5_yi": chgs,
        "sum_last5_yi": sum5,
        "pos_days_last5": pos_days,
        "rule": (
            f"WATCH(sum5>={TW_MARGIN_WATCH_SUM5_YI} & pos_days>={TW_MARGIN_POSDAYS5_MIN}); "
            f"ALERT(sum5>={TW_MARGIN_ALERT_SUM5_YI} & pos_days>={TW_MARGIN_POSDAYS5_MIN})"
        ),
    }
    return (sig, dbg)


def _compute_percentile(latest: float, xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    n = len(xs)
    c = sum(1 for x in xs if x <= latest)
    return (c / n) * 100.0


def _derive_margin_level_gate(rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Level gate using balance_yi percentile within last N points (up to 252).
    - PASS if p >= 95
    - FAIL if p < 95
    - NA if insufficient points (<60)
    """
    if not TW_MARGIN_LEVEL_GATE_ENABLED:
        return ("SKIPPED", {"reason": "level_gate_disabled"})

    rows2 = _sort_rows_newest_first([r for r in rows if isinstance(r, dict)])
    balances: List[float] = []
    for r in rows2[: max(1, min(TW_MARGIN_LEVEL_WINDOW, len(rows2)))]:
        v = _as_float(r.get("balance_yi"))
        if v is None:
            continue
        balances.append(float(v))

    if len(balances) < TW_MARGIN_LEVEL_MIN_POINTS:
        return (
            None,
            {
                "reason": "insufficient_level_points",
                "min_points": TW_MARGIN_LEVEL_MIN_POINTS,
                "have_points": len(balances),
            },
        )

    latest = balances[0]
    p = _compute_percentile(latest, balances)
    if p is None:
        return (None, {"reason": "percentile_compute_failed"})

    gate = "PASS" if p >= TW_MARGIN_LEVEL_P_MIN else "FAIL"
    dbg = {
        "window_used": min(TW_MARGIN_LEVEL_WINDOW, len(balances)),
        "p": p,
        "p_min": TW_MARGIN_LEVEL_P_MIN,
        "latest_balance_yi": latest,
        "have_points": len(balances),
        "min_points": TW_MARGIN_LEVEL_MIN_POINTS,
    }
    return (gate, dbg)


# ---------------- history (v0.1.8 hardened) ----------------

def _list_backup_files(history_path: str) -> List[str]:
    # expected: dashboard_bottom_cache/history.json.bak.YYYYMMDDTHHMMSSZ.json
    prefix = history_path + ".bak."
    d = os.path.dirname(history_path) or "."
    out: List[str] = []
    try:
        for fn in os.listdir(d):
            full = os.path.join(d, fn)
            if full.startswith(prefix) and full.endswith(".json"):
                out.append(full)
    except Exception:
        return []
    return sorted(out)  # lexical ok for YYYYMMDDTHHMMSSZ timestamps


def _prune_old_backups(history_path: str, keep_n: int) -> Dict[str, Any]:
    files = _list_backup_files(history_path)
    audit = {"prune_status": "SKIPPED", "prune_reason": "no_backups_or_keep_all", "deleted": 0}
    if keep_n <= 0:
        return audit
    if len(files) <= keep_n:
        audit.update({"prune_status": "OK", "prune_reason": f"within_keep_n:{keep_n}", "deleted": 0})
        return audit

    to_delete = files[: max(0, len(files) - keep_n)]
    deleted = 0
    for p in to_delete:
        try:
            os.remove(p)
            deleted += 1
        except Exception:
            # best-effort prune; do not fail run
            pass

    audit.update({"prune_status": "OK", "prune_reason": f"pruned_to_keep_n:{keep_n}", "deleted": deleted})
    return audit


def _backup_history_if_exists(out_history: str, run_ts_utc: str) -> Dict[str, Any]:
    """
    Always back up the existing history.json BEFORE parsing/writing.
    Also prunes old backups (keep last N).
    Returns audit dict.
    """
    os.makedirs(os.path.dirname(out_history), exist_ok=True)

    audit: Dict[str, Any] = {
        "backup_status": "SKIPPED",
        "backup_reason": "no_existing_history",
        "backup_path": None,
        "backup_bytes": None,
        "backup_keep_n": _env_int(ENV_BACKUP_KEEP_N, DEFAULT_BACKUP_KEEP_N),
        "backup_prune": {"prune_status": "SKIPPED", "prune_reason": "not_run", "deleted": 0},
    }

    if not os.path.exists(out_history):
        return audit

    safe = _safe_ts_for_filename(run_ts_utc)
    bak_path = f"{out_history}.bak.{safe}.json"
    try:
        shutil.copy2(out_history, bak_path)
        bsz = os.path.getsize(bak_path)
        audit.update(
            {
                "backup_status": "OK",
                "backup_reason": "copied_pre_write",
                "backup_path": bak_path,
                "backup_bytes": int(bsz),
            }
        )
    except Exception as e:
        audit.update(
            {
                "backup_status": "FAIL",
                "backup_reason": f"copy_failed:{type(e).__name__}",
                "backup_path": bak_path,
                "backup_bytes": None,
            }
        )
        # even if copy failed, still try prune (it’s independent)

    keep_n = int(audit.get("backup_keep_n", DEFAULT_BACKUP_KEEP_N) or DEFAULT_BACKUP_KEEP_N)
    audit["backup_prune"] = _prune_old_backups(out_history, keep_n)
    return audit


def _load_history(out_history: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load history.json robustly.
    Returns (hist, audit):
      - audit: {history_load_status, reason, loaded_items}
    """
    audit: Dict[str, Any] = {
        "history_load_status": "NA",
        "history_load_reason": "not_loaded",
        "loaded_items": 0,
    }
    hist: Dict[str, Any] = {"schema_version": "bottom_history_v1", "items": []}

    if not os.path.exists(out_history):
        audit.update(
            {
                "history_load_status": "NA",
                "history_load_reason": "file_not_found",
                "loaded_items": 0,
            }
        )
        return hist, audit

    try:
        tmp = _read_json(out_history)

        if not isinstance(tmp, dict):
            audit.update(
                {
                    "history_load_status": "DOWNGRADED",
                    "history_load_reason": "not_a_dict",
                    "loaded_items": 0,
                }
            )
            return hist, audit

        items = tmp.get("items")
        if isinstance(items, list):
            hist = tmp
            audit.update(
                {
                    "history_load_status": "OK",
                    "history_load_reason": "dict.items",
                    "loaded_items": len(items),
                }
            )
            return hist, audit

        audit.update(
            {
                "history_load_status": "DOWNGRADED",
                "history_load_reason": f"items_not_list:{type(items).__name__}",
                "loaded_items": 0,
            }
        )
        return hist, audit

    except Exception as e:
        audit.update(
            {
                "history_load_status": "DOWNGRADED",
                "history_load_reason": f"read_or_parse_failed:{type(e).__name__}",
                "loaded_items": 0,
            }
        )
        return hist, audit


def _unique_day_buckets(items: List[Dict[str, Any]]) -> int:
    days: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        asof = _as_str(it.get("as_of_ts")) or "NA"
        dk = _day_key_tpe_from_iso(asof)
        if dk != "NA":
            days.add(dk)
    return len(days)


def main() -> None:
    run_ts_utc = _utc_now()
    as_of_ts_tpe = _tpe_now()
    git_sha = os.environ.get("GITHUB_SHA", "NA")

    excluded: List[Dict[str, str]] = []

    allow_reset = _env_flag(ENV_ALLOW_RESET)
    allow_shrink = _env_flag(ENV_ALLOW_SHRINK)
    reset_reason = os.environ.get(ENV_RESET_REASON, "").strip() or "unspecified"

    # ---- read market_cache stats ----
    try:
        root = _read_json(MARKET_STATS_PATH)
        ok_market = True
    except Exception as e:
        root = {}
        ok_market = False
        excluded.append({"trigger": "ALL", "reason": f"read_or_parse_failed:{type(e).__name__}"})

    meta = {
        "generated_at_utc": _as_str(root.get("generated_at_utc")),
        "as_of_ts": _as_str(root.get("as_of_ts")),
        "script_version": _as_str(root.get("script_version")),
        "ret1_mode": _as_str(root.get("ret1_mode")),
        "percentile_method": _as_str(root.get("percentile_method")),
    }

    series_root = root.get("series") if isinstance(root.get("series"), dict) else {}

    # ---- extract series snapshots ----
    series_out: Dict[str, Any] = {}
    for sid in NEEDED:
        s = series_root.get(sid, {}) if isinstance(series_root, dict) else {}
        latest = s.get("latest") if isinstance(s.get("latest"), dict) else {}
        w60 = _get(s, ["windows", "w60"]) if isinstance(_get(s, ["windows", "w60"]), dict) else {}
        w252 = _get(s, ["windows", "w252"]) if isinstance(_get(s, ["windows", "w252"]), dict) else {}

        z60 = _as_float(w60.get("z"))
        p252 = _as_float(w252.get("p"))
        sig = _series_signal(z60, p252)

        series_out[sid] = {
            "series_id": sid,
            "risk_dir": RISK_DIR.get(sid, "NA"),
            "latest": {
                "data_date": _as_str(latest.get("data_date")),
                "value": _as_float(latest.get("value")),
                "as_of_ts": _as_str(latest.get("as_of_ts")) or meta["as_of_ts"],
                "source_url": _as_str(latest.get("source_url")) or "NA",
            },
            "w60": {
                "z": z60,
                "p": _as_float(w60.get("p")),
                "ret1_pct": _as_float(w60.get("ret1_pct")),
                "z_delta": _as_float(w60.get("z_delta")),
                "p_delta": _as_float(w60.get("p_delta")),
            },
            "w252": {
                "z": _as_float(w252.get("z")),
                "p": p252,
            },
            "series_signal": sig or "NA",
        }

    # ---- Global triggers ----
    vix_val = series_out["VIX"]["latest"]["value"]
    spx_ret1 = series_out["SP500"]["w60"]["ret1_pct"]

    trig_panic: Optional[int] = None
    if vix_val is None and spx_ret1 is None:
        excluded.append({"trigger": "TRIG_PANIC", "reason": "missing_fields:VIX.latest.value & SP500.w60.ret1_pct"})
    else:
        cond_vix = (vix_val is not None and float(vix_val) >= TH_VIX_PANIC)
        cond_spx = (spx_ret1 is not None and float(spx_ret1) <= TH_SPX_RET1_PANIC)
        trig_panic = 1 if (cond_vix or cond_spx) else 0

    hyg_z = series_out["HYG_IEF_RATIO"]["w60"]["z"]
    hyg_sig = series_out["HYG_IEF_RATIO"]["series_signal"]
    ofr_z = series_out["OFR_FSI"]["w60"]["z"]
    ofr_sig = series_out["OFR_FSI"]["series_signal"]

    trig_veto: Optional[int] = None
    if hyg_z is None and ofr_z is None:
        excluded.append({"trigger": "TRIG_SYSTEMIC_VETO", "reason": "missing_fields:HYG_IEF_RATIO.w60.z & OFR_FSI.w60.z"})
    else:
        hyg_can = (hyg_z is not None and hyg_sig in ("WATCH", "ALERT"))
        ofr_can = (ofr_z is not None and ofr_sig in ("WATCH", "ALERT"))
        hyg_veto = 1 if (hyg_can and float(hyg_z) <= TH_HYG_VETO_Z) else 0
        ofr_veto = 1 if (ofr_can and float(ofr_z) >= TH_OFR_VETO_Z) else 0
        trig_veto = 1 if (hyg_veto == 1 or ofr_veto == 1) else 0

    trig_rev: Optional[int] = None
    if trig_panic != 1 or trig_veto != 0:
        trig_rev = 0
    else:
        vix_ret1 = series_out["VIX"]["w60"]["ret1_pct"]
        vix_zd = series_out["VIX"]["w60"]["z_delta"]
        vix_pd = series_out["VIX"]["w60"]["p_delta"]

        # VIX cooling: any available metric < 0
        vix_cooling: Optional[int] = None
        for x in (vix_ret1, vix_zd, vix_pd):
            if x is not None:
                vix_cooling = 1 if float(x) < 0 else 0
                break

        spx_stab: Optional[int] = None
        if spx_ret1 is not None:
            spx_stab = 1 if float(spx_ret1) >= 0 else 0

        if vix_cooling is None or spx_stab is None:
            miss = []
            if vix_cooling is None:
                miss.append("VIX(w60.ret1_pct/z_delta/p_delta)")
            if spx_stab is None:
                miss.append("SP500(w60.ret1_pct)")
            excluded.append({"trigger": "TRIG_REVERSAL", "reason": "missing_fields:" + "&".join(miss)})
            trig_rev = None
        else:
            trig_rev = 1 if (vix_cooling == 1 and spx_stab == 1) else 0

    # bottom state
    if trig_panic == 0:
        bottom_state = "NONE"
    elif trig_panic == 1:
        if trig_veto == 1:
            bottom_state = "PANIC_BUT_SYSTEMIC"
        elif trig_veto == 0:
            bottom_state = "BOTTOM_CANDIDATE" if trig_rev == 1 else "BOTTOM_WATCH"
        else:
            bottom_state = "BOTTOM_WATCH"
    else:
        bottom_state = "NA"

    # context (non-trigger)
    spx_p252 = series_out["SP500"]["w252"]["p"]
    context_equity_extreme: Optional[int] = None
    if spx_p252 is not None:
        context_equity_extreme = 1 if float(spx_p252) >= 95.0 else 0

    # distances (<=0 means triggered)
    dist_vix_panic = (TH_VIX_PANIC - float(vix_val)) if vix_val is not None else None
    dist_spx_panic = (float(spx_ret1) - TH_SPX_RET1_PANIC) if spx_ret1 is not None else None
    dist_hyg_veto = (float(hyg_z) - TH_HYG_VETO_Z) if hyg_z is not None else None
    dist_ofr_veto = (TH_OFR_VETO_Z - float(ofr_z)) if ofr_z is not None else None

    # ---------------- TW Local Gate ----------------
    tw_roll25, ok_roll25 = _load_tw_roll25(excluded)
    tw_margin, ok_margin = _load_tw_margin(excluded)

    # roll25 key fields
    tw_used_date = _as_str(tw_roll25.get("used_date") or _get(tw_roll25, ["numbers", "UsedDate"]))
    tw_run_day_tag = _as_str(
        tw_roll25.get("run_day_tag")
        or _get(tw_roll25, ["signal", "RunDayTag"])
        or tw_roll25.get("tag")
    )
    tw_used_date_status = _as_str(tw_roll25.get("used_date_status") or _get(tw_roll25, ["signal", "UsedDateStatus"]))
    tw_lookback_actual = _as_int(_get(tw_roll25, ["numbers", "LookbackNActual"]) or tw_roll25.get("lookback_n_actual"))
    tw_lookback_target = _as_int(_get(tw_roll25, ["numbers", "LookbackNTarget"]) or tw_roll25.get("lookback_n_target"))

    tw_pct_change = _as_float(_get(tw_roll25, ["numbers", "PctChange"]))
    tw_amplitude_pct = _as_float(_get(tw_roll25, ["numbers", "AmplitudePct"]))
    tw_turnover_twd = _as_float(_get(tw_roll25, ["numbers", "TradeValue"]))
    tw_close = _as_float(_get(tw_roll25, ["numbers", "Close"]))

    sig_obj = _get(tw_roll25, ["signal"])
    if not isinstance(sig_obj, dict):
        sig_obj = {}

    # numeric-aware parsing
    sig_downday = _as_bool(sig_obj.get("DownDay"))
    sig_volamp = _as_bool(sig_obj.get("VolumeAmplified"))
    sig_volamp2 = _as_bool(sig_obj.get("VolAmplified"))
    sig_newlow_n = _as_int(sig_obj.get("NewLow_N"))
    sig_consec_n = _as_int(sig_obj.get("ConsecutiveBreak"))

    stress_newlow = None if sig_newlow_n is None else (sig_newlow_n >= TH_TW_NEWLOW_STRESS_MIN)

    # v0.1.10: make paired basis explicit (for audit)
    paired_basis: Optional[bool] = None
    if stress_newlow is None or sig_volamp is None or sig_volamp2 is None:
        paired_basis = None
    else:
        paired_basis = bool(sig_volamp or sig_volamp2 or stress_newlow)

    # v0.1.9: consecutive break is eligible, but may require pairing
    stress_consec_raw = None if sig_consec_n is None else (sig_consec_n >= TH_TW_CONSEC_BREAK_STRESS)
    stress_consec_paired: Optional[bool] = None
    if stress_consec_raw is None or paired_basis is None:
        stress_consec_paired = None
    else:
        if not stress_consec_raw:
            stress_consec_paired = False
        else:
            stress_consec_paired = paired_basis if TW_CONSEC_STRESS_REQUIRE_PAIR else True

    # TW margin (TWSE)
    tw_margin_unit = "億"
    twse_rows: List[Dict[str, Any]] = []
    twse_data_date: Optional[str] = None

    if ok_margin:
        series = tw_margin.get("series")
        if isinstance(series, dict) and isinstance(series.get("TWSE"), dict):
            twse = series["TWSE"]
            twse_data_date = _as_str(twse.get("data_date"))
            rows = twse.get("rows")
            if isinstance(rows, list):
                twse_rows = [r for r in rows if isinstance(r, dict)]
            unit_label = _get(twse, ["chg_yi_unit", "label"])
            if isinstance(unit_label, str) and unit_label.strip():
                tw_margin_unit = unit_label.strip()

    # derive margin flow + optional level gate
    margin_flow_signal: Optional[str] = None
    margin_flow_dbg: Dict[str, Any] = {}
    margin_level_gate: Optional[str] = None
    margin_level_dbg: Dict[str, Any] = {}
    margin_confidence = "OK"

    if ok_margin and twse_rows:
        margin_flow_signal, margin_flow_dbg = _derive_margin_flow_signal(twse_rows)
        margin_flow_signal = _canon_margin_signal(margin_flow_signal)

        if margin_flow_signal is None:
            excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "margin_flow_signal_NA"})

        # level gate
        margin_level_gate, margin_level_dbg = _derive_margin_level_gate(twse_rows)
        if margin_level_gate is None and TW_MARGIN_LEVEL_GATE_ENABLED:
            margin_confidence = "DOWNGRADED"
    else:
        if ok_margin:
            excluded.append({"trigger": "TRIG_TW_LEVERAGE_HEAT", "reason": "missing_fields:series.TWSE.rows"})

    # final margin signal (canonical)
    tw_margin_signal: Optional[str] = None
    if margin_flow_signal is None:
        tw_margin_signal = None
    else:
        if TW_MARGIN_LEVEL_GATE_ENABLED and margin_level_gate == "FAIL":
            tw_margin_signal = "NONE"
        else:
            tw_margin_signal = margin_flow_signal

    tw_margin_signal = _canon_margin_signal(tw_margin_signal)

    # TRIG_TW_PANIC
    trig_tw_panic: Optional[int] = None
    if not ok_roll25:
        trig_tw_panic = None
        excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_input:roll25_cache/latest_report.json"})
    else:
        need = [sig_downday, sig_volamp, sig_volamp2, stress_newlow, stress_consec_raw, stress_consec_paired]
        if any(x is None for x in need):
            excluded.append({"trigger": "TRIG_TW_PANIC", "reason": "missing_fields:roll25.signal.*"})
            trig_tw_panic = None
        else:
            consec_counts = bool(stress_consec_paired)
            any_stress = bool(sig_volamp or sig_volamp2 or stress_newlow or consec_counts)
            trig_tw_panic = 1 if (sig_downday and any_stress) else 0

    # TRIG_TW_LEVERAGE_HEAT
    trig_tw_heat: Optional[int] = None
    if tw_margin_signal is None:
        trig_tw_heat = None
    else:
        trig_tw_heat = 1 if (tw_margin_signal in ("WATCH", "ALERT")) else 0

    # TRIG_TW_REVERSAL: PANIC & NOT heat & pct_change>=0 & DownDay=false
    trig_tw_rev: Optional[int] = None
    if trig_tw_panic != 1:
        trig_tw_rev = 0 if trig_tw_panic in (0, None) else None
    else:
        if tw_pct_change is None or sig_downday is None:
            excluded.append({"trigger": "TRIG_TW_REVERSAL", "reason": "missing_fields:pct_change or DownDay"})
            trig_tw_rev = None
        else:
            if trig_tw_heat is None:
                trig_tw_rev = 0
            else:
                trig_tw_rev = 1 if (trig_tw_heat == 0 and float(tw_pct_change) >= 0 and sig_downday is False) else 0

    # TW state
    if trig_tw_panic is None:
        tw_state = "NA"
    elif trig_tw_panic == 0:
        tw_state = "NONE"
    else:
        if trig_tw_heat == 1:
            tw_state = "PANIC_BUT_LEVERAGE_HEAT"
        elif trig_tw_heat == 0:
            tw_state = "TW_BOTTOM_CANDIDATE" if trig_tw_rev == 1 else "TW_BOTTOM_WATCH"
        else:
            tw_state = "TW_BOTTOM_WATCH"

    # TW distances / gating
    pct_change_to_nonnegative_gap: Optional[float] = None
    if tw_pct_change is not None:
        pct_change_to_nonnegative_gap = max(0.0, 0.0 - float(tw_pct_change))

    lookback_missing_points: Optional[int] = None
    if tw_lookback_actual is not None and tw_lookback_target is not None:
        lookback_missing_points = max(0, int(tw_lookback_target) - int(tw_lookback_actual))

    # latest balance display
    twse_latest_balance_yi: Optional[float] = None
    twse_latest_chg_yi: Optional[float] = None
    if twse_rows:
        rows2 = _sort_rows_newest_first(twse_rows)
        twse_latest_balance_yi = _as_float(rows2[0].get("balance_yi"))
        twse_latest_chg_yi = _as_float(rows2[0].get("chg_yi"))

    # ---- history backup & load ----
    history_file_exists = os.path.exists(OUT_HISTORY)
    backup_audit = _backup_history_if_exists(OUT_HISTORY, run_ts_utc)
    hist, history_load_audit = _load_history(OUT_HISTORY)

    history_pre_items = int(history_load_audit.get("loaded_items", 0))
    old_items = hist.get("items", [])
    if not isinstance(old_items, list):
        old_items = []
    old_items = [it for it in old_items if isinstance(it, dict)]
    pre_unique_days = _unique_day_buckets(old_items)

    # ---- build latest.json (base) ----
    latest_out: Dict[str, Any] = {
        "schema_version": "bottom_cache_v1_1",
        "renderer_version": RENDERER_VERSION,
        "generated_at_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "inputs": {
            "market_cache_stats_path": MARKET_STATS_PATH,
            "market_cache_ok": ok_market,
            "market_cache_generated_at_utc": meta["generated_at_utc"] or "NA",
            "market_cache_as_of_ts": meta["as_of_ts"] or "NA",
            "market_cache_script_version": meta["script_version"] or "NA",
            "market_cache_ret1_mode": meta["ret1_mode"] or "NA",
            "market_cache_percentile_method": meta["percentile_method"] or "NA",
            "tw_roll25_report_path": TW_ROLL25_REPORT_PATH,
            "tw_margin_path": TW_MARGIN_PATH,
        },
        "bottom_state_global": bottom_state,
        "triggers_global": {
            "TRIG_PANIC": trig_panic,
            "TRIG_SYSTEMIC_VETO": trig_veto,
            "TRIG_REVERSAL": trig_rev,
        },
        "context_global": {
            "context_equity_extreme_sp500_p252_ge_95": context_equity_extreme,
            "sp500_p252": spx_p252 if spx_p252 is not None else None,
        },
        "distances_global": {
            "vix_panic_gap": dist_vix_panic,
            "sp500_ret1_panic_gap": dist_spx_panic,
            "hyg_veto_gap_z": dist_hyg_veto,
            "ofr_veto_gap_z": dist_ofr_veto,
        },
        "tw_local_gate": {
            "tw_state": tw_state,
            "UsedDate": tw_used_date or "NA",
            "run_day_tag": tw_run_day_tag or "NA",
            "used_date_status": tw_used_date_status or "NA",
            "lookback_n_actual": tw_lookback_actual,
            "lookback_n_target": tw_lookback_target,
            "pct_change": tw_pct_change,
            "amplitude_pct": tw_amplitude_pct,
            "turnover_twd": tw_turnover_twd,
            "close": tw_close,
            "signals": {
                "DownDay": sig_downday,
                "VolumeAmplified": sig_volamp,
                "VolAmplified": sig_volamp2,
                "NewLow_N": sig_newlow_n,
                "ConsecutiveBreak": sig_consec_n,
                "stress_newlow": stress_newlow,
                "stress_consecutive_break_raw": stress_consec_raw,
                "stress_consecutive_break_paired": stress_consec_paired,
                "stress_consec_pair_required": TW_CONSEC_STRESS_REQUIRE_PAIR,
                "stress_consec_pair_basis": paired_basis,
                "stress_consec_pair_basis_rule": TW_CONSEC_PAIR_BASIS_RULE,
            },
            "margin": {
                "data_date": twse_data_date,
                "unit": tw_margin_unit,
                "flow_signal": margin_flow_signal,
                "flow_dbg": margin_flow_dbg,
                "level_gate": margin_level_gate,
                "level_dbg": margin_level_dbg,
                "final_signal": tw_margin_signal,
                "confidence": margin_confidence,
                "latest_balance_yi": twse_latest_balance_yi,
                "latest_chg_yi": twse_latest_chg_yi,
            },
            "triggers": {
                "TRIG_TW_PANIC": trig_tw_panic,
                "TRIG_TW_LEVERAGE_HEAT": trig_tw_heat,
                "TRIG_TW_REVERSAL": trig_tw_rev,
            },
            "distances": {
                "pct_change_to_nonnegative_gap": pct_change_to_nonnegative_gap,
                "lookback_missing_points": lookback_missing_points,
            },
        },
        "excluded_triggers": excluded,
        "series_global": series_out,
        "history_audit": {
            **history_load_audit,
            **backup_audit,
            "history_file_exists": history_file_exists,
            "history_pre_items": history_pre_items,
            "history_pre_unique_days": pre_unique_days,
            "history_post_items": None,
            "history_post_unique_days": None,
            "history_write_status": "NA",
            "history_write_reason": "not_decided",
            "history_reset": False,
            "history_reset_reason": None,
            "allow_reset": allow_reset,
            "allow_shrink": allow_shrink,
        },
        "notes": [
            "Global: single source = market_cache/stats_latest.json",
            "TW: uses existing repo outputs only (no external fetch here)",
            "Signals are deterministic; missing fields => NA + excluded reasons",
            "ret1_pct unit is percent (%)",
            "TW margin heat uses flow signal; optional level gate blocks only when enough data; otherwise downgrade",
            "v0.1.7: always backup history.json before write",
            "v0.1.8: fail-closed history writes + unique-day shrink guard + backup retention",
            "v0.1.9: TW panic hardening (ConsecutiveBreak stress requires pairing)",
            "v0.1.10: report prints roll25 raw fields + paired_basis",
        ],
    }

    # ---------------- history append / guards ----------------
    history_write_status = "OK"
    history_write_reason = "ok"
    history_reset = False
    history_reset_reason = None

    # Fail-Closed: if history exists but load is not OK
    if history_file_exists and history_load_audit.get("history_load_status") != "OK":
        if allow_reset:
            history_reset = True
            history_reset_reason = reset_reason or history_load_audit.get("history_load_reason")
            hist = {"schema_version": "bottom_history_v1", "items": []}
            old_items = []
            history_pre_items = 0
            pre_unique_days = 0
            latest_out["history_audit"]["history_load_status"] = "RESET"
            latest_out["history_audit"]["history_load_reason"] = f"allowed_reset:{history_load_audit.get('history_load_reason')}"
        else:
            history_write_status = "SKIPPED"
            history_write_reason = "FAIL_CLOSED:history_load_not_ok"
    # else: OK or file_not_found => proceed

    # Build the history item for this run (even if we might skip writing, report/latest still reflect current run)
    item = {
        "run_ts_utc": run_ts_utc,
        "as_of_ts": as_of_ts_tpe,
        "data_commit_sha": git_sha,
        "bottom_state_global": bottom_state,
        "triggers_global": latest_out["triggers_global"],
        "context_global": latest_out["context_global"],
        "distances_global": latest_out["distances_global"],
        "tw_state": tw_state,
        "tw_triggers": latest_out["tw_local_gate"]["triggers"],
        "margin_final_signal": tw_margin_signal,
        "margin_confidence": margin_confidence,
    }

    # Compute would-be new history (1 row per TPE day)
    dk = _day_key_tpe_from_iso(as_of_ts_tpe)
    if isinstance(hist, dict) and isinstance(hist.get("items"), list):
        base_items = [it for it in hist.get("items", []) if isinstance(it, dict)]
    else:
        base_items = []

    new_items = [
        it for it in base_items
        if _day_key_tpe_from_iso(_as_str(it.get("as_of_ts")) or "NA") != dk
    ]
    new_items.append(item)

    post_unique_days = _unique_day_buckets(new_items)
    history_post_items = len(new_items)

    # Shrink Guard (unique day buckets)
    if history_write_status == "OK":
        if history_file_exists and pre_unique_days > 0 and post_unique_days < pre_unique_days and not allow_shrink:
            history_write_status = "SKIPPED"
            history_write_reason = f"FAIL_SHRINK_GUARD:unique_days {post_unique_days} < {pre_unique_days}"

    # If allowed, write history.json (and reflect post counts)
    effective_items_for_report = base_items  # default if we skip
    if history_write_status == "OK":
        hist2 = dict(hist) if isinstance(hist, dict) else {}
        hist2["schema_version"] = hist2.get("schema_version") or "bottom_history_v1"
        hist2["items"] = new_items
        _write_json(OUT_HISTORY, hist2)
        effective_items_for_report = new_items
    else:
        history_post_items = history_pre_items
        post_unique_days = pre_unique_days

    # finalize history audit in latest_out
    latest_out["history_audit"]["history_write_status"] = history_write_status
    latest_out["history_audit"]["history_write_reason"] = history_write_reason
    latest_out["history_audit"]["history_reset"] = history_reset
    latest_out["history_audit"]["history_reset_reason"] = history_reset_reason
    latest_out["history_audit"]["history_post_items"] = history_post_items
    latest_out["history_audit"]["history_post_unique_days"] = post_unique_days

    # write latest.json always (even if history write skipped)
    _write_json(OUT_LATEST, latest_out)

    # ---------------- report analytics (use effective history, i.e., persisted state) ----------------
    items_sorted: List[Dict[str, Any]] = [it for it in effective_items_for_report if isinstance(it, dict)]
    items_sorted.sort(key=lambda x: _iso_sort_key(_as_str(x.get("as_of_ts")) or "NA"))
    recent = items_sorted[-HISTORY_SHOW_N:] if items_sorted else []

    # streaks based on effective history (if history write skipped, streak excludes this run)
    streak_global = 0
    for it in reversed(items_sorted):
        if (it.get("bottom_state_global") or "NA") == bottom_state:
            streak_global += 1
        else:
            break

    streak_tw = 0
    for it in reversed(items_sorted):
        if (it.get("tw_state") or "NA") == tw_state:
            streak_tw += 1
        else:
            break

    # ---- TW audit strings for report.md ----
    flow_sum5 = None
    flow_pos5 = None
    if isinstance(margin_flow_dbg, dict):
        flow_sum5 = _as_float(margin_flow_dbg.get("sum_last5_yi"))
        flow_pos5 = _as_int(margin_flow_dbg.get("pos_days_last5"))

    level_have = None
    level_min = None
    level_p = None
    if isinstance(margin_level_dbg, dict):
        level_have = _as_int(margin_level_dbg.get("have_points"))
        level_min = _as_int(margin_level_dbg.get("min_points"))
        level_p = _as_float(margin_level_dbg.get("p"))

    # tw panic hit string (v0.1.9 aware)
    tw_panic_hit = "NA"
    required = {
        "DownDay": sig_downday,
        "VolumeAmplified": sig_volamp,
        "VolAmplified": sig_volamp2,
        "NewLow_N": sig_newlow_n,
        "ConsecutiveBreak": sig_consec_n,
        "stress_newlow": stress_newlow,
        "stress_consec_raw": stress_consec_raw,
        "stress_consec_paired": stress_consec_paired,
        "paired_basis": paired_basis,
    }
    if any(v is None for v in required.values()):
        missing = [k for k, v in required.items() if v is None]
        tw_panic_hit = "NA (missing_fields:" + ",".join(missing) + ")"
    else:
        stress_hit: List[str] = []
        stress_miss: List[str] = []

        if bool(sig_volamp):
            stress_hit.append("VolumeAmplified")
        else:
            stress_miss.append("VolumeAmplified")

        if bool(sig_volamp2):
            stress_hit.append("VolAmplified")
        else:
            stress_miss.append("VolAmplified")

        if bool(stress_newlow):
            stress_hit.append(f"NewLow_N>={TH_TW_NEWLOW_STRESS_MIN}")
        else:
            stress_miss.append(f"NewLow_N>={TH_TW_NEWLOW_STRESS_MIN}")

        if TW_CONSEC_STRESS_REQUIRE_PAIR:
            if bool(stress_consec_paired):
                stress_hit.append(f"ConsecutiveBreak>={TH_TW_CONSEC_BREAK_STRESS}&paired")
            else:
                if bool(stress_consec_raw):
                    stress_miss.append(f"ConsecutiveBreak>={TH_TW_CONSEC_BREAK_STRESS}&paired(FAILED)")
                else:
                    stress_miss.append(f"ConsecutiveBreak>={TH_TW_CONSEC_BREAK_STRESS}&paired")
        else:
            if bool(stress_consec_raw):
                stress_hit.append(f"ConsecutiveBreak>={TH_TW_CONSEC_BREAK_STRESS}")
            else:
                stress_miss.append(f"ConsecutiveBreak>={TH_TW_CONSEC_BREAK_STRESS}")

        stress_str = ",".join(stress_hit) if stress_hit else ""
        miss_str = ",".join(stress_miss) if stress_miss else ""
        tw_panic_hit = f"DownDay={sig_downday} + Stress={{{stress_str}}}; Miss={{{miss_str}}}"

    # ---- report.md ----
    md: List[str] = []
    md.append("# Bottom Cache Dashboard (v0.1)\n\n")
    md.append(f"- renderer_version: `{RENDERER_VERSION}`\n")
    md.append(f"- as_of_ts (TPE): `{as_of_ts_tpe}`\n")
    md.append(f"- run_ts_utc: `{run_ts_utc}`\n")
    md.append(f"- bottom_state (Global): **{bottom_state}**  (streak={streak_global})\n")
    md.append(f"- market_cache_as_of_ts: `{meta['as_of_ts'] or 'NA'}`\n")
    md.append(f"- market_cache_generated_at_utc: `{meta['generated_at_utc'] or 'NA'}`\n")

    md.append(
        f"- history_load_status: `{latest_out['history_audit'].get('history_load_status','NA')}`; "
        f"reason: `{latest_out['history_audit'].get('history_load_reason','NA')}`; "
        f"loaded_items: `{history_pre_items}`\n"
    )
    md.append(
        f"- history_pre_items: `{history_pre_items}`; history_post_items: `{history_post_items}`; "
        f"pre_unique_days: `{pre_unique_days}`; post_unique_days: `{post_unique_days}`\n"
    )
    md.append(
        f"- history_write: status=`{history_write_status}`; reason=`{history_write_reason}`; "
        f"allow_reset=`{allow_reset}`; allow_shrink=`{allow_shrink}`\n"
    )
    if history_reset:
        md.append(f"- history_reset: `true`; reset_reason: `{history_reset_reason}`\n")

    ba = latest_out["history_audit"]
    prune = ba.get("backup_prune", {}) if isinstance(ba.get("backup_prune"), dict) else {}
    md.append(
        f"- history_backup: status=`{ba.get('backup_status','NA')}`; "
        f"reason=`{ba.get('backup_reason','NA')}`; "
        f"file=`{ba.get('backup_path') or 'NA'}`; "
        f"bytes=`{ba.get('backup_bytes') if ba.get('backup_bytes') is not None else 'NA'}`; "
        f"keep_n=`{ba.get('backup_keep_n','NA')}`; "
        f"prune_deleted=`{prune.get('deleted','NA')}`\n\n"
    )

    md.append("## Rationale (Decision Chain) - Global\n")
    md.append(f"- TRIG_PANIC = `{_fmt_na(trig_panic)}`  (VIX >= {TH_VIX_PANIC} OR SP500.ret1% <= {TH_SPX_RET1_PANIC})\n")
    md.append(f"- TRIG_SYSTEMIC_VETO = `{_fmt_na(trig_veto)}`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)\n")
    md.append(f"- TRIG_REVERSAL = `{_fmt_na(trig_rev)}`  (panic & NOT systemic & VIX cooling & SP500 stable)\n\n")

    md.append("## Distance to Triggers - Global\n")
    md.append(f"- VIX panic gap: `{_safe_float_str(dist_vix_panic, 4)}`\n")
    md.append(f"- SP500 ret1% gap: `{_safe_float_str(dist_spx_panic, 4)}`\n")
    md.append(f"- HYG veto gap(z): `{_safe_float_str(dist_hyg_veto, 4)}`\n")
    md.append(f"- OFR veto gap(z): `{_safe_float_str(dist_ofr_veto, 4)}`\n\n")

    md.append("## Context (Non-trigger) - Global\n")
    md.append(f"- SP500.p252: `{_fmt_na(spx_p252)}`; equity_extreme(p252>=95): `{_fmt_na(context_equity_extreme)}`\n\n")

    md.append("## TW Local Gate (roll25 + margin)\n")
    md.append(f"- tw_state: **{tw_state}**  (streak={streak_tw})\n")
    md.append(f"- UsedDate: `{tw_used_date or 'NA'}`; run_day_tag: `{tw_run_day_tag or 'NA'}`; used_date_status: `{tw_used_date_status or 'NA'}`\n")
    md.append(f"- Lookback: `{_fmt_na(tw_lookback_actual)}/{_fmt_na(tw_lookback_target)}`\n")

    # v0.1.10: roll25 raw + paired basis (auditability)
    md.append(
        "- roll25_raw: "
        f"DownDay=`{_fmt_na(sig_downday)}`; "
        f"VolumeAmplified=`{_fmt_na(sig_volamp)}`; "
        f"VolAmplified=`{_fmt_na(sig_volamp2)}`; "
        f"NewLow_N=`{_fmt_na(sig_newlow_n)}`; "
        f"ConsecutiveBreak=`{_fmt_na(sig_consec_n)}`\n"
    )
    md.append(
        f"- roll25_paired_basis: `{_fmt_na(paired_basis)}` "
        f"(basis = {TW_CONSEC_PAIR_BASIS_RULE})\n"
    )

    md.append(f"- margin_final_signal(TWSE): `{_fmt_na(tw_margin_signal)}`; confidence: `{margin_confidence}`; unit: `{tw_margin_unit}`\n")
    md.append(f"- margin_balance(TWSE latest): `{_safe_float_str(twse_latest_balance_yi, 1)}` {tw_margin_unit}\n")
    md.append(f"- margin_chg(TWSE latest): `{_safe_float_str(twse_latest_chg_yi, 1)}` {tw_margin_unit}\n")

    md.append(
        f"- margin_flow_audit: signal=`{_fmt_na(margin_flow_signal)}`; "
        f"sum_last5=`{_safe_float_str(flow_sum5, 1)}`; "
        f"pos_days_last5=`{_fmt_na(flow_pos5)}`\n"
    )

    md.append(
        f"- margin_level_gate_audit: gate=`{_fmt_na(margin_level_gate)}`; "
        f"points=`{_fmt_na(level_have)}/{_fmt_na(level_min)}`; "
        f"p=`{_fmt_na(level_p)}`; p_min=`{TW_MARGIN_LEVEL_P_MIN}`\n"
    )

    md.append(f"- tw_panic_hit: `{tw_panic_hit}`\n\n")

    md.append("### TW Triggers (0/1/NA)\n")
    md.append(f"- TRIG_TW_PANIC: `{_fmt_na(trig_tw_panic)}`\n")
    md.append(f"- TRIG_TW_LEVERAGE_HEAT: `{_fmt_na(trig_tw_heat)}`\n")
    md.append(f"- TRIG_TW_REVERSAL: `{_fmt_na(trig_tw_rev)}`\n\n")

    if excluded:
        md.append("## Excluded / NA Reasons\n")
        for e in excluded:
            md.append(f"- {e.get('trigger','NA')}: {e.get('reason','NA')}\n")
        md.append("\n")

    md.append("## Recent History (last 10 buckets)\n")
    if not recent:
        md.append("- NA (history empty)\n\n")
    else:
        md.append("| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | margin_final | margin_conf |\n")
        md.append("|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|\n")
        for it in recent:
            asof = _as_str(it.get("as_of_ts")) or "NA"
            dk2 = _day_key_tpe_from_iso(asof)
            st = it.get("bottom_state_global") or "NA"

            tr = it.get("triggers_global") if isinstance(it.get("triggers_global"), dict) else {}
            p = _fmt_na(tr.get("TRIG_PANIC", None))
            v = _fmt_na(tr.get("TRIG_SYSTEMIC_VETO", None))
            r = _fmt_na(tr.get("TRIG_REVERSAL", None))

            tws = it.get("tw_state") or "NA"
            twtr = it.get("tw_triggers") if isinstance(it.get("tw_triggers"), dict) else {}
            twp = _fmt_na(twtr.get("TRIG_TW_PANIC", None))
            twh = _fmt_na(twtr.get("TRIG_TW_LEVERAGE_HEAT", None))
            twr = _fmt_na(twtr.get("TRIG_TW_REVERSAL", None))

            mf = _fmt_na(it.get("margin_final_signal"))
            mc = _fmt_na(it.get("margin_confidence"))

            md.append(f"| {dk2} | {asof} | {st} | {p} | {v} | {r} | {tws} | {twp} | {twh} | {twr} | {mf} | {mc} |\n")
        md.append("\n")

    md.append("## Data Sources\n")
    md.append(f"- Global (single-source): `{MARKET_STATS_PATH}`\n")
    md.append("- TW Local Gate (existing workflow outputs, no fetch):\n")
    md.append(f"  - `{TW_ROLL25_REPORT_PATH}`\n")
    md.append(f"  - `{TW_MARGIN_PATH}`\n")
    md.append("- This dashboard does not fetch external URLs directly.\n")

    _write_text(OUT_MD, "".join(md))


if __name__ == "__main__":
    main()