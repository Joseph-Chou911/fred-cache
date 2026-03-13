#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge_0050_valuation_bb.py  (v1.4d)

Purpose
-------
Merge three layers into one deterministic report:
1) Valuation map:
   EPS growth / FX haircut / P-E multiple -> TSMC fair price -> 0050 fair price
2) Execution map:
   current BB / regime / tranche references from tw0050_bb_cache/stats_latest.json
3) Pre-execution shock review:
   read Band 1 / Band 2 from roll25 markdown report and compare with manual TX night close

v1.4d changes
-------------
- Keep v1.4c structure and backward-compatible JSON schema
- Add one minimal robustness-check family:
  * 2027_defensive_family
- Purpose:
  * test whether current price still looks acceptable under a milder 2027 defensive setup
- Keep family interpolation display-only; does NOT alter final_execution_bias

Backward compatibility
----------------------
Kept legacy top-level keys:
- config_used
- bb_summary
- scenario_results
- combined

Also kept newer keys:
- meta
- inputs
- valuation_cases
- bb_snapshot
- family_interpolation
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "meta": {
        "config_version": "0050_merge_v1.4d",
        "note": (
            "Fixed rules, moving outputs. Update slow variables deliberately; "
            "update fast variables daily after close. "
            "Pre-execution shock review is optional and report-only. "
            "Family interpolation is display-only and does not alter final execution bias. "
            "Added 2027_defensive_family as a minimal robustness check."
        ),
    },
    "base": {
        "base_0050": "auto",   # auto_from_bb_stats unless overridden
        "base_tsmc": 1890.0,
        "tsmc_weight": 0.6408,
    },
    "dividend_drag": {
        "enabled": True,
        "mode": "light",  # off / light / heavy / custom
        "points_per_year_light": 1.0,
        "points_per_year_heavy": 2.5,
        "points_per_year_custom": 1.0,
        "note": (
            "Display-price sensitivity only. "
            "Use 'heavy' if you want to approximate the earlier pessimistic net-price style."
        ),
    },
    "dq_policy": {
        "caution_flags": [
            "PRICE_SERIES_BREAK_DETECTED",
            "FWD_MDD_CLEAN_APPLIED",
            "RAW_OUTLIER_EXCLUDED_BY_CLEAN",
            "FWD_MDD_OUTLIER_MIN_RAW_20D",
        ],
        "veto_flags": [],
    },
    "scenario_groups": [
        {
            "group_name": "2026_core",
            "years_ahead": 1,
            "scenarios": [
                {
                    "name": "2026_壓力",
                    "eps_base": 66.25,
                    "eps_growth": 0.20,
                    "fx_haircut": 0.06,
                    "pe": 18.0,
                    "other_ret": -0.15,
                },
                {
                    "name": "2026_保守",
                    "eps_base": 66.25,
                    "eps_growth": 0.20,
                    "fx_haircut": 0.03,
                    "pe": 20.0,
                    "other_ret": -0.08,
                },
                {
                    "name": "2026_中性偏保守",
                    "eps_base": 66.25,
                    "eps_growth": 0.25,
                    "fx_haircut": 0.03,
                    "pe": 22.0,
                    "other_ret": -0.03,
                },
                {
                    "name": "2026_中性",
                    "eps_base": 66.25,
                    "eps_growth": 0.25,
                    "fx_haircut": 0.00,
                    "pe": 24.0,
                    "other_ret": 0.00,
                },
            ],
        },
        {
            "group_name": "2027_core",
            "years_ahead": 2,
            "scenarios": [
                {
                    "name": "2027_中性",
                    "eps_base": 66.25,
                    "eps_growth": 0.25,
                    "fx_haircut": 0.06,
                    "pe": 22.0,
                    "other_ret": 0.02,
                },
                {
                    "name": "2027_中性偏樂觀",
                    "eps_base": 66.25,
                    "eps_growth": 0.25,
                    "fx_haircut": 0.00,
                    "pe": 24.0,
                    "other_ret": 0.05,
                },
                {
                    "name": "2027_樂觀延續",
                    "eps_base": 66.25,
                    "eps_growth": 0.30,
                    "fx_haircut": 0.00,
                    "pe": 24.0,
                    "other_ret": 0.05,
                },
            ],
        },
    ],
    "family_interpolation": {
        "enabled": True,
        "targets": [72.0, 71.0, 69.0],
        "note": (
            "Display-only. Single-axis dense interpolation within fixed assumption families. "
            "This section improves valuation readability but does not alter execution bias."
        ),
        "families": [
            {
                "family_name": "2026_conservative_family",
                "years_ahead": 1,
                "eps_base": 66.25,
                "eps_growth": 0.20,
                "fx_haircut": 0.03,
                "other_ret": -0.08,
                "pe_start": 18.0,
                "pe_end": 24.0,
                "pe_step": 0.5,
            },
            {
                "family_name": "2026_neutralish_family",
                "years_ahead": 1,
                "eps_base": 66.25,
                "eps_growth": 0.25,
                "fx_haircut": 0.03,
                "other_ret": -0.03,
                "pe_start": 20.0,
                "pe_end": 24.0,
                "pe_step": 0.5,
            },
            {
                "family_name": "2027_neutral_family",
                "years_ahead": 2,
                "eps_base": 66.25,
                "eps_growth": 0.25,
                "fx_haircut": 0.06,
                "other_ret": 0.02,
                "pe_start": 20.0,
                "pe_end": 24.0,
                "pe_step": 0.5,
            },
            {
                "family_name": "2027_defensive_family",
                "years_ahead": 2,
                "eps_base": 66.25,
                "eps_growth": 0.20,
                "fx_haircut": 0.06,
                "other_ret": 0.00,
                "pe_start": 18.0,
                "pe_end": 22.0,
                "pe_step": 0.5,
            },
        ],
    },
}


@dataclasses.dataclass
class BBState:
    date: str
    price_used: float
    state: str
    bb_z: float
    regime_tag: str
    regime_allowed: bool
    rv20_percentile: float
    action_bucket: str
    pledge_policy: str
    tranche_levels: List[Dict[str, Any]]
    dq_flags: List[str]


@dataclasses.dataclass
class ScenarioResult:
    group_name: str
    years_ahead: int
    name: str
    eps_base: float
    eps_growth: float
    fx_haircut: float
    pe: float
    other_ret: float
    eps_after_growth: float
    eps_after_fx: float
    tsmc_price: float
    tsmc_return_vs_base: float
    gross_0050: float
    net_0050: float


@dataclasses.dataclass
class PreExecutionReview:
    available: bool
    source_path: Optional[str]
    band1: Optional[float]
    band2: Optional[float]
    tx_night_last: Optional[float]
    tx_vs_band1: Optional[float]
    tx_vs_band2: Optional[float]
    preopen_shock_flag: str
    shock_override: str
    trigger_reasons: List[str]
    parse_notes: List[str]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def deep_copy_jsonable(x: Any) -> Any:
    return json.loads(json.dumps(x, ensure_ascii=False))


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        return float(x)
    except Exception:
        return default


def get_path(d: Dict[str, Any], dotted: str) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def has_path(d: Dict[str, Any], dotted: str) -> bool:
    try:
        get_path(d, dotted)
        return True
    except KeyError:
        return False


def validate_bb_stats_schema(stats: Dict[str, Any]) -> Dict[str, Any]:
    required_paths = [
        "latest.date",
        "latest.state",
        "latest.bb_z",
        "regime.tag",
        "regime.allowed",
        "vol.rv_ann_pctl",
        "pledge.decision.action_bucket",
        "pledge.decision.pledge_policy",
        "dq.flags",
    ]
    missing = [p for p in required_paths if not has_path(stats, p)]

    latest_price_candidates = [
        "latest.price_used",
        "latest.close",
        "latest.adjclose",
    ]
    if not any(has_path(stats, p) for p in latest_price_candidates):
        missing.append("one_of(latest.price_used, latest.close, latest.adjclose)")

    if missing:
        raise SystemExit(
            "ERROR: bb-stats schema validation failed; missing required keys: "
            + ", ".join(missing)
        )

    levels = (
        stats.get("pledge", {})
        .get("unconditional_tranche_levels", {})
        .get("levels", [])
    )
    if levels is not None and not isinstance(levels, list):
        raise SystemExit(
            "ERROR: bb-stats schema validation failed; "
            "pledge.unconditional_tranche_levels.levels is not a list"
        )

    return {
        "validated": True,
        "required_paths_checked": required_paths,
        "latest_price_candidates": latest_price_candidates,
        "tranche_levels_present": isinstance(levels, list) and len(levels) > 0,
    }


def merge_config(user_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = deep_copy_jsonable(DEFAULT_CONFIG)
    if not user_cfg:
        return cfg

    for top_key, value in user_cfg.items():
        if isinstance(value, dict) and isinstance(cfg.get(top_key), dict):
            cfg[top_key].update(value)
        else:
            cfg[top_key] = value
    return cfg


def parse_bb_stats(stats: Dict[str, Any]) -> BBState:
    latest = stats.get("latest", {})
    regime = stats.get("regime", {})
    pledge = stats.get("pledge", {})
    pledge_decision = pledge.get("decision", {}) or {}
    levels = pledge.get("unconditional_tranche_levels", {}).get("levels", []) or []
    dq_flags = stats.get("dq", {}).get("flags", []) or []

    price_used = safe_float(
        latest.get("price_used", latest.get("close", latest.get("adjclose", float("nan"))))
    )

    return BBState(
        date=str(latest.get("date", "")),
        price_used=price_used,
        state=str(latest.get("state", "N/A")),
        bb_z=safe_float(latest.get("bb_z", float("nan"))),
        regime_tag=str(regime.get("tag", "N/A")),
        regime_allowed=bool(regime.get("allowed", False)),
        rv20_percentile=safe_float(stats.get("vol", {}).get("rv_ann_pctl", float("nan"))),
        action_bucket=str(pledge_decision.get("action_bucket", "N/A")),
        pledge_policy=str(pledge_decision.get("pledge_policy", "N/A")),
        tranche_levels=list(levels),
        dq_flags=list(dq_flags),
    )


def resolve_base_0050(cfg: Dict[str, Any], bb_stats: Dict[str, Any], cli_base_0050: Optional[float]) -> Tuple[float, str]:
    if cli_base_0050 is not None:
        return float(cli_base_0050), "cli"

    cfg_val = cfg.get("base", {}).get("base_0050", "auto")
    if cfg_val not in (None, "", "auto", "AUTO", "auto_from_bb_stats"):
        return float(cfg_val), "config"

    latest = bb_stats.get("latest", {}) or {}
    for key in ("price_used", "close", "adjclose"):
        if key in latest:
            v = safe_float(latest.get(key))
            if not math.isnan(v):
                return v, f"bb_stats.latest.{key}"

    fallback = 76.85
    return fallback, "default_fallback"


def resolve_base_tsmc(cfg: Dict[str, Any], cli_base_tsmc: Optional[float]) -> Tuple[float, str]:
    if cli_base_tsmc is not None:
        return float(cli_base_tsmc), "cli"

    cfg_val = cfg.get("base", {}).get("base_tsmc", None)
    if cfg_val not in (None, "", "auto", "AUTO"):
        return float(cfg_val), "config"

    return 1890.0, "default_fallback"


def resolve_tsmc_weight(cfg: Dict[str, Any], cli_tsmc_weight: Optional[float]) -> Tuple[float, str]:
    if cli_tsmc_weight is not None:
        return float(cli_tsmc_weight), "cli"

    cfg_val = cfg.get("base", {}).get("tsmc_weight", None)
    if cfg_val is not None:
        return float(cfg_val), "config"

    return 0.6408, "default_fallback"


def resolve_dividend_drag(cfg: Dict[str, Any]) -> Tuple[bool, str, float]:
    dd = cfg.get("dividend_drag", {})
    enabled = bool(dd.get("enabled", True))
    mode = str(dd.get("mode", "light")).lower()

    if not enabled or mode == "off":
        return False, "off", 0.0

    if mode == "light":
        return True, "light", float(dd.get("points_per_year_light", dd.get("points_per_year", 1.0)))
    if mode == "heavy":
        return True, "heavy", float(dd.get("points_per_year_heavy", 2.5))
    if mode == "custom":
        return True, "custom", float(dd.get("points_per_year_custom", dd.get("points_per_year", 1.0)))

    return True, "legacy", float(dd.get("points_per_year", 1.0))


def apply_resolved_bases(
    cfg: Dict[str, Any],
    bb_stats: Dict[str, Any],
    cli_base_0050: Optional[float],
    cli_base_tsmc: Optional[float],
    cli_tsmc_weight: Optional[float],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    cfg2 = deep_copy_jsonable(cfg)

    base_0050, src_0050 = resolve_base_0050(cfg2, bb_stats, cli_base_0050)
    base_tsmc, src_tsmc = resolve_base_tsmc(cfg2, cli_base_tsmc)
    tsmc_weight, src_weight = resolve_tsmc_weight(cfg2, cli_tsmc_weight)

    cfg2["base"]["base_0050"] = base_0050
    cfg2["base"]["base_tsmc"] = base_tsmc
    cfg2["base"]["tsmc_weight"] = tsmc_weight

    sources = {
        "base_0050": src_0050,
        "base_tsmc": src_tsmc,
        "tsmc_weight": src_weight,
    }
    return cfg2, sources


def compute_tsmc_price(
    eps_base: float,
    eps_growth: float,
    years_ahead: int,
    fx_haircut: float,
    pe: float,
) -> Tuple[float, float, float]:
    eps_after_growth = eps_base * ((1.0 + eps_growth) ** years_ahead)
    eps_after_fx = eps_after_growth * (1.0 - fx_haircut)
    tsmc_price = eps_after_fx * pe
    return eps_after_growth, eps_after_fx, tsmc_price


def compute_0050_prices(
    base_0050: float,
    base_tsmc: float,
    tsmc_weight: float,
    tsmc_price: float,
    other_ret: float,
    years_ahead: int,
    dividend_drag_points_per_year: float,
    drag_enabled: bool,
) -> Tuple[float, float, float]:
    tsmc_ret = (tsmc_price / base_tsmc) - 1.0
    gross = base_0050 * (1.0 + tsmc_weight * tsmc_ret + (1.0 - tsmc_weight) * other_ret)
    drag = (dividend_drag_points_per_year * years_ahead) if drag_enabled else 0.0
    net = gross - drag
    return tsmc_ret, gross, net


def build_results(cfg: Dict[str, Any], drag_enabled: bool, drag_pts: float) -> List[ScenarioResult]:
    base_0050 = float(cfg["base"]["base_0050"])
    base_tsmc = float(cfg["base"]["base_tsmc"])
    tsmc_weight = float(cfg["base"]["tsmc_weight"])

    out: List[ScenarioResult] = []
    for group in cfg["scenario_groups"]:
        years_ahead = int(group["years_ahead"])
        group_name = str(group["group_name"])
        for s in group["scenarios"]:
            eps_base = float(s["eps_base"])
            eps_growth = float(s["eps_growth"])
            fx_haircut = float(s["fx_haircut"])
            pe = float(s["pe"])
            other_ret = float(s["other_ret"])

            eps_after_growth, eps_after_fx, tsmc_price = compute_tsmc_price(
                eps_base=eps_base,
                eps_growth=eps_growth,
                years_ahead=years_ahead,
                fx_haircut=fx_haircut,
                pe=pe,
            )
            tsmc_ret, gross, net = compute_0050_prices(
                base_0050=base_0050,
                base_tsmc=base_tsmc,
                tsmc_weight=tsmc_weight,
                tsmc_price=tsmc_price,
                other_ret=other_ret,
                years_ahead=years_ahead,
                dividend_drag_points_per_year=drag_pts,
                drag_enabled=drag_enabled,
            )

            out.append(
                ScenarioResult(
                    group_name=group_name,
                    years_ahead=years_ahead,
                    name=str(s["name"]),
                    eps_base=eps_base,
                    eps_growth=eps_growth,
                    fx_haircut=fx_haircut,
                    pe=pe,
                    other_ret=other_ret,
                    eps_after_growth=eps_after_growth,
                    eps_after_fx=eps_after_fx,
                    tsmc_price=tsmc_price,
                    tsmc_return_vs_base=tsmc_ret,
                    gross_0050=gross,
                    net_0050=net,
                )
            )
    return out


def percentile_rank(x: float, xs: List[float]) -> float:
    if not xs:
        return float("nan")
    less = sum(v < x for v in xs)
    equal = sum(v == x for v in xs)
    return 100.0 * (less + 0.5 * equal) / len(xs)


def zone_from_percentile(pctl: float) -> str:
    if math.isnan(pctl):
        return "N/A"
    if pctl <= 20:
        return "LOWER_ZONE"
    if pctl <= 40:
        return "LOWER_MID_ZONE"
    if pctl <= 60:
        return "MID_ZONE"
    if pctl <= 80:
        return "UPPER_MID_ZONE"
    return "UPPER_ZONE"


def zone_from_percentile_compact(pctl: float) -> str:
    if math.isnan(pctl):
        return "N/A"
    if pctl <= 20:
        return "CHEAP"
    if pctl <= 40:
        return "LOWER_MID"
    if pctl <= 60:
        return "MID"
    if pctl <= 80:
        return "UPPER_MID"
    return "RICH"


def quantile_linear(sorted_xs: List[float], q: float) -> float:
    if not sorted_xs:
        return float("nan")
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    if q <= 0:
        return sorted_xs[0]
    if q >= 1:
        return sorted_xs[-1]

    pos = (len(sorted_xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_xs[lo]
    w = pos - lo
    return sorted_xs[lo] * (1.0 - w) + sorted_xs[hi] * w


def generate_axis_values(start: float, end: float, step: float) -> List[float]:
    if step <= 0:
        raise ValueError("family interpolation step must be > 0")
    vals: List[float] = []
    cur = start
    eps = step / 1000.0
    while cur <= end + eps:
        vals.append(round(cur, 6))
        cur += step
    return vals


def classify_against_range(x: float, ordered: List[float]) -> str:
    if not ordered:
        return "N/A"
    if x < ordered[0]:
        return "BELOW_MIN"
    if x > ordered[-1]:
        return "ABOVE_MAX"
    return "IN_RANGE"


def gap_vs_range(x: float, ordered: List[float]) -> Dict[str, Optional[float]]:
    if not ordered:
        return {
            "gap_vs_min": None,
            "gap_vs_max": None,
            "pct_vs_min": None,
            "pct_vs_max": None,
        }
    mn = ordered[0]
    mx = ordered[-1]
    gap_min = x - mn
    gap_max = x - mx
    pct_min = ((x / mn) - 1.0) * 100.0 if mn not in (0, None) else None
    pct_max = ((x / mx) - 1.0) * 100.0 if mx not in (0, None) else None
    return {
        "gap_vs_min": gap_min,
        "gap_vs_max": gap_max,
        "pct_vs_min": pct_min,
        "pct_vs_max": pct_max,
    }


def classify_price(current_price: float, xs: List[float]) -> Dict[str, Any]:
    ordered = sorted(xs)
    pctl = percentile_rank(current_price, ordered)
    zone = zone_from_percentile(pctl)
    status = classify_against_range(current_price, ordered)
    gaps = gap_vs_range(current_price, ordered)
    return {
        "current_price": current_price,
        "scenario_net_min": min(ordered) if ordered else None,
        "scenario_net_max": max(ordered) if ordered else None,
        "scenario_net_pctl": pctl,
        "position_status": status,
        "gap_vs_min": gaps["gap_vs_min"],
        "gap_vs_max": gaps["gap_vs_max"],
        "pct_vs_min": gaps["pct_vs_min"],
        "pct_vs_max": gaps["pct_vs_max"],
        "zone": zone,
        "note": (
            "rough classification only; sparse scenario set and mixed 1Y/2Y horizons "
            "=> low decision value"
        ),
    }


def build_family_interpolation(
    cfg: Dict[str, Any],
    current_price: float,
    drag_enabled: bool,
    drag_pts: float,
) -> Dict[str, Any]:
    fi_cfg = cfg.get("family_interpolation", {}) or {}
    enabled = bool(fi_cfg.get("enabled", False))
    note = str(fi_cfg.get("note", ""))

    if not enabled:
        return {
            "enabled": False,
            "targets": [],
            "families": [],
            "note": "disabled",
        }

    base_0050 = float(cfg["base"]["base_0050"])
    base_tsmc = float(cfg["base"]["base_tsmc"])
    tsmc_weight = float(cfg["base"]["tsmc_weight"])
    targets = [float(x) for x in fi_cfg.get("targets", [])]

    families_out: List[Dict[str, Any]] = []
    for fam in fi_cfg.get("families", []):
        family_name = str(fam["family_name"])
        years_ahead = int(fam["years_ahead"])
        eps_base = float(fam["eps_base"])
        eps_growth = float(fam["eps_growth"])
        fx_haircut = float(fam["fx_haircut"])
        other_ret = float(fam["other_ret"])
        pe_start = float(fam["pe_start"])
        pe_end = float(fam["pe_end"])
        pe_step = float(fam["pe_step"])

        pe_values = generate_axis_values(pe_start, pe_end, pe_step)
        cases: List[Dict[str, Any]] = []
        net_values: List[float] = []

        for pe in pe_values:
            eps_after_growth, eps_after_fx, tsmc_price = compute_tsmc_price(
                eps_base=eps_base,
                eps_growth=eps_growth,
                years_ahead=years_ahead,
                fx_haircut=fx_haircut,
                pe=pe,
            )
            tsmc_ret, gross, net = compute_0050_prices(
                base_0050=base_0050,
                base_tsmc=base_tsmc,
                tsmc_weight=tsmc_weight,
                tsmc_price=tsmc_price,
                other_ret=other_ret,
                years_ahead=years_ahead,
                dividend_drag_points_per_year=drag_pts,
                drag_enabled=drag_enabled,
            )
            net_values.append(net)
            cases.append(
                {
                    "pe": pe,
                    "eps_after_growth": eps_after_growth,
                    "eps_after_fx": eps_after_fx,
                    "tsmc_price": tsmc_price,
                    "tsmc_return_vs_base": tsmc_ret,
                    "gross_0050": gross,
                    "net_0050": net,
                }
            )

        ordered = sorted(net_values)
        current_pctile = percentile_rank(current_price, ordered)
        current_status = classify_against_range(current_price, ordered)
        current_gaps = gap_vs_range(current_price, ordered)

        target_positions: List[Dict[str, Any]] = []
        for t in targets:
            p = percentile_rank(t, ordered)
            status = classify_against_range(t, ordered)
            gaps = gap_vs_range(t, ordered)
            target_positions.append(
                {
                    "price": t,
                    "percentile": p,
                    "zone": zone_from_percentile_compact(p),
                    "position_status": status,
                    "family_net_min": ordered[0] if ordered else None,
                    "family_net_max": ordered[-1] if ordered else None,
                    "gap_vs_min": gaps["gap_vs_min"],
                    "gap_vs_max": gaps["gap_vs_max"],
                    "pct_vs_min": gaps["pct_vs_min"],
                    "pct_vs_max": gaps["pct_vs_max"],
                }
            )

        family_stats = {
            "net_min": min(ordered) if ordered else None,
            "net_max": max(ordered) if ordered else None,
            "p10": quantile_linear(ordered, 0.10),
            "p25": quantile_linear(ordered, 0.25),
            "p50": quantile_linear(ordered, 0.50),
            "p75": quantile_linear(ordered, 0.75),
            "p90": quantile_linear(ordered, 0.90),
            "case_count": len(cases),
        }

        families_out.append(
            {
                "family_name": family_name,
                "years_ahead": years_ahead,
                "fixed_assumptions": {
                    "eps_base": eps_base,
                    "eps_growth": eps_growth,
                    "fx_haircut": fx_haircut,
                    "other_ret": other_ret,
                },
                "interpolation_axis": {
                    "axis_name": "pe",
                    "start": pe_start,
                    "end": pe_end,
                    "step": pe_step,
                    "count": len(pe_values),
                },
                "family_stats": family_stats,
                "current_price_percentile": current_pctile,
                "current_zone": zone_from_percentile_compact(current_pctile),
                "current_position_status": current_status,
                "current_gap_vs_min": current_gaps["gap_vs_min"],
                "current_gap_vs_max": current_gaps["gap_vs_max"],
                "current_pct_vs_min": current_gaps["pct_vs_min"],
                "current_pct_vs_max": current_gaps["pct_vs_max"],
                "target_positions": target_positions,
                "cases": cases,
            }
        )

    return {
        "enabled": True,
        "targets": targets,
        "families": families_out,
        "note": note,
    }


def decide_execution_bias(
    bb: BBState,
    price_zone: str,
    dq_policy: Dict[str, Any],
) -> Dict[str, Any]:
    """
    First decide base execution bias from price/regime/BB state.
    Then apply DQ overlay to downgrade trust or veto if configured.
    """
    if bb.regime_allowed is False and "UPPER" in bb.state:
        base_bias = "DEFENSIVE_NO_CHASE"
    elif price_zone in {"LOWER_ZONE", "LOWER_MID_ZONE"} and bb.regime_allowed:
        base_bias = "ALLOW_STAGED_ACCUMULATION"
    else:
        base_bias = "WAIT_FOR_BETTER_ALIGNMENT"

    caution_flags = set(dq_policy.get("caution_flags", []))
    veto_flags = set(dq_policy.get("veto_flags", []))
    dq_set = set(bb.dq_flags)

    matched_veto = sorted(list(dq_set & veto_flags))
    matched_caution = sorted(list(dq_set & caution_flags))

    if matched_veto:
        final_bias = "DEFENSIVE_DQ_VETO"
        dq_overlay = "VETO"
    elif matched_caution:
        if base_bias == "ALLOW_STAGED_ACCUMULATION":
            final_bias = "CAUTION_DQ_PRESENT"
        elif base_bias == "WAIT_FOR_BETTER_ALIGNMENT":
            final_bias = "WAIT_WITH_DQ_CAUTION"
        else:
            final_bias = base_bias
        dq_overlay = "CAUTION"
    else:
        final_bias = base_bias
        dq_overlay = "NONE"

    return {
        "base_execution_bias": base_bias,
        "dq_overlay": dq_overlay,
        "matched_caution_flags": matched_caution,
        "matched_veto_flags": matched_veto,
        "combined_execution_bias": final_bias,
    }


def parse_roll25_bands_from_report(report_text: str) -> Tuple[Optional[float], Optional[float], List[str]]:
    band1: Optional[float] = None
    band2: Optional[float] = None
    notes: List[str] = []

    for line in report_text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue

        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 6:
            continue

        label = parts[1]
        point_raw = parts[4] if len(parts) > 4 else ""
        point_val = safe_float(point_raw, default=float("nan"))

        if label.startswith("Band 1") and not math.isnan(point_val):
            band1 = point_val
        elif label.startswith("Band 2") and not math.isnan(point_val):
            band2 = point_val

    if band1 is None:
        notes.append("Band 1 not found in roll25 report markdown.")
    if band2 is None:
        notes.append("Band 2 not found in roll25 report markdown.")

    return band1, band2, notes


def build_pre_execution_review(
    roll25_report_path: Optional[str],
    tx_night_last: Optional[float],
) -> PreExecutionReview:
    parse_notes: List[str] = []
    band1: Optional[float] = None
    band2: Optional[float] = None

    if roll25_report_path:
        p = Path(roll25_report_path)
        if p.exists():
            try:
                report_text = load_text(p)
                band1, band2, notes = parse_roll25_bands_from_report(report_text)
                parse_notes.extend(notes)
            except Exception as e:
                parse_notes.append(f"Failed to parse roll25 report: {e}")
        else:
            parse_notes.append(f"roll25 report path does not exist: {roll25_report_path}")
    else:
        parse_notes.append("No roll25 report path provided.")

    tx_vs_band1 = None
    tx_vs_band2 = None
    if tx_night_last is not None and band1 is not None:
        tx_vs_band1 = tx_night_last - band1
    if tx_night_last is not None and band2 is not None:
        tx_vs_band2 = tx_night_last - band2

    available = (tx_night_last is not None) and ((band1 is not None) or (band2 is not None))
    trigger_reasons: List[str] = []
    preopen_shock_flag = "NONE"
    shock_override = "NONE"

    if available:
        if band2 is not None and tx_night_last < band2:
            preopen_shock_flag = "HARD_STOP"
            shock_override = "HARD_STOP_PREOPEN"
            trigger_reasons.append("tx_night_last_below_band2")
        elif band1 is not None and tx_night_last < band1:
            preopen_shock_flag = "CAUTION"
            shock_override = "OBSERVE_ONLY"
            trigger_reasons.append("tx_night_last_below_band1")
        else:
            preopen_shock_flag = "NONE"
            shock_override = "NONE"
    else:
        if tx_night_last is None:
            parse_notes.append("No TX night close provided.")
        if band1 is None and band2 is None:
            parse_notes.append("No usable Band 1 / Band 2 extracted from roll25 report.")

    return PreExecutionReview(
        available=available,
        source_path=roll25_report_path,
        band1=band1,
        band2=band2,
        tx_night_last=tx_night_last,
        tx_vs_band1=tx_vs_band1,
        tx_vs_band2=tx_vs_band2,
        preopen_shock_flag=preopen_shock_flag,
        shock_override=shock_override,
        trigger_reasons=trigger_reasons,
        parse_notes=parse_notes,
    )


def bias_rank(label: str) -> int:
    order = {
        "NONE": 0,
        "ALLOW_STAGED_ACCUMULATION": 10,
        "WAIT_FOR_BETTER_ALIGNMENT": 50,
        "DEFENSIVE_NO_CHASE": 55,
        "CAUTION_DQ_PRESENT": 60,
        "WAIT_WITH_DQ_CAUTION": 70,
        "OBSERVE_ONLY": 80,
        "DEFENSIVE_DQ_VETO": 90,
        "HARD_STOP_PREOPEN": 100,
    }
    return order.get(label, 0)


def decide_final_execution_bias(
    combined_execution_bias: str,
    shock_override: str,
) -> str:
    if bias_rank(shock_override) >= bias_rank(combined_execution_bias):
        return shock_override if shock_override != "NONE" else combined_execution_bias
    return combined_execution_bias


def action_instruction_from_bias(label: str) -> str:
    mapping = {
        "HARD_STOP_PREOPEN": "完全停手；盤前 shock 未消化。",
        "DEFENSIVE_DQ_VETO": "停手；資料品質 veto。",
        "OBSERVE_ONLY": "只觀察，不執行。",
        "WAIT_WITH_DQ_CAUTION": "觀察為主；等待更好對齊，且留意 DQ。",
        "CAUTION_DQ_PRESENT": "若非必要不要動；最多極小額。",
        "DEFENSIVE_NO_CHASE": "防守持有，不追價。",
        "WAIT_FOR_BETTER_ALIGNMENT": "等待更好對齊。",
        "ALLOW_STAGED_ACCUMULATION": "可分批累積。",
        "NONE": "無額外動作。",
    }
    return mapping.get(label, "等待更好對齊。")


def build_combined_view(
    bb: BBState,
    results: List[ScenarioResult],
    dq_policy: Dict[str, Any],
    pre_review: PreExecutionReview,
    family_interp: Dict[str, Any],
) -> Dict[str, Any]:
    net_prices = [r.net_0050 for r in results]
    gross_prices = [r.gross_0050 for r in results]
    price_pos = classify_price(bb.price_used, net_prices)

    tranche_levels = []
    for level in bb.tranche_levels:
        price_level = safe_float(level.get("price_level", float("nan")))
        tranche_levels.append(
            {
                "label": level.get("label", ""),
                "price_level": price_level,
                "vs_current_pct": ((price_level / bb.price_used) - 1.0) * 100.0 if bb.price_used else None,
            }
        )

    exec_info = decide_execution_bias(
        bb=bb,
        price_zone=price_pos["zone"],
        dq_policy=dq_policy,
    )

    final_execution_bias = decide_final_execution_bias(
        combined_execution_bias=exec_info["combined_execution_bias"],
        shock_override=pre_review.shock_override,
    )

    return {
        "bb": dataclasses.asdict(bb),
        "valuation_range": {
            "gross_min": min(gross_prices) if gross_prices else None,
            "gross_max": max(gross_prices) if gross_prices else None,
            "net_min": min(net_prices) if net_prices else None,
            "net_max": max(net_prices) if net_prices else None,
            "current_price_position": price_pos,
        },
        "family_interpolation": family_interp,
        "tranche_reference": tranche_levels,
        "pre_execution_review": dataclasses.asdict(pre_review),
        "base_execution_bias": exec_info["base_execution_bias"],
        "dq_overlay": exec_info["dq_overlay"],
        "matched_caution_flags": exec_info["matched_caution_flags"],
        "matched_veto_flags": exec_info["matched_veto_flags"],
        "combined_execution_bias": exec_info["combined_execution_bias"],
        "fast_shock_override": pre_review.shock_override,
        "final_execution_bias": final_execution_bias,
        "action_instruction": action_instruction_from_bias(final_execution_bias),
        "how_to_read": {
            "layer_1": "Use valuation scenarios to decide whether the current zone is cheap / fair / expensive.",
            "layer_1b": "Use family interpolation summary to improve valuation readability; this section is display-only.",
            "layer_2": "Use BB/regime/tranche references to decide whether to act now or wait.",
            "layer_3": "Use pre-execution review to override action bias when TX night close breaches roll25 bands.",
            "zone_note": "valuation zone is rough classification only; do not over-interpret sparse or mixed-horizon percentile output.",
            "family_note": "family interpolation is display-only and does not alter final execution bias.",
            "family_boundary_note": "percentile=0 or 100 can simply mean the target is below family min or above family max.",
            "family_robustness_note": "2027_defensive_family is a robustness check only; it does not alter execution bias.",
            "dq_note": "DQ flags can downgrade or veto action bias even when valuation or regime otherwise look acceptable.",
            "shock_note": "Pre-execution review is optional. If no roll25 report or TX night close is provided, no shock override is applied.",
            "note": "Rules fixed, outputs dynamic. Fast variables update daily; slow assumptions should be revised deliberately.",
        },
    }


def scenario_to_case(r: ScenarioResult) -> Dict[str, Any]:
    return {
        "group_name": r.group_name,
        "years_ahead": r.years_ahead,
        "name": r.name,
        "eps_base": r.eps_base,
        "eps_growth": r.eps_growth,
        "fx_haircut": r.fx_haircut,
        "pe": r.pe,
        "other_ret": r.other_ret,
        "eps_after_growth": r.eps_after_growth,
        "eps_after_fx": r.eps_after_fx,
        "tsmc_price": r.tsmc_price,
        "tsmc_return_vs_base": r.tsmc_return_vs_base,
        "gross_0050": r.gross_0050,
        "net_0050": r.net_0050,
    }


def build_output_json(
    cfg: Dict[str, Any],
    bb: BBState,
    results: List[ScenarioResult],
    family_interp: Dict[str, Any],
    combined: Dict[str, Any],
    bb_stats_path: str,
    roll25_report_path: Optional[str],
    tx_night_last: Optional[float],
    base_sources: Dict[str, str],
    drag_enabled: bool,
    drag_mode: str,
    drag_pts: float,
    schema_validation: Dict[str, Any],
) -> Dict[str, Any]:
    valuation_cases = [scenario_to_case(r) for r in results]

    meta = {
        "generated_at_utc": now_utc_iso(),
        "script": "merge_0050_valuation_bb.py",
        "schema_version": "0050_merge_schema_v1.4d_compat",
        "config_version": cfg.get("meta", {}).get("config_version", "unknown"),
        "note": cfg.get("meta", {}).get("note", ""),
    }

    inputs = {
        "bb_stats_path": bb_stats_path,
        "roll25_report_path": roll25_report_path,
        "tx_night_last": tx_night_last,
        "base_0050": float(cfg["base"]["base_0050"]),
        "base_tsmc": float(cfg["base"]["base_tsmc"]),
        "tsmc_weight": float(cfg["base"]["tsmc_weight"]),
        "base_sources": base_sources,
        "dividend_drag": {
            "enabled": drag_enabled,
            "mode": drag_mode,
            "points_per_year": drag_pts,
            "note": str(cfg.get("dividend_drag", {}).get("note", "")),
        },
        "family_interpolation_enabled": bool(cfg.get("family_interpolation", {}).get("enabled", False)),
        "current_date": bb.date,
        "current_0050_price": bb.price_used,
        "current_bb_state": bb.state,
        "current_bb_z": bb.bb_z,
        "schema_validation": schema_validation,
    }

    bb_snapshot = {
        "date": bb.date,
        "price_used": bb.price_used,
        "state": bb.state,
        "bb_z": bb.bb_z,
        "regime_tag": bb.regime_tag,
        "regime_allowed": bb.regime_allowed,
        "rv20_percentile": bb.rv20_percentile,
        "action_bucket": bb.action_bucket,
        "pledge_policy": bb.pledge_policy,
        "dq_flags": bb.dq_flags,
        "tranche_levels": bb.tranche_levels,
    }

    out_json = {
        "meta": meta,
        "inputs": inputs,
        "valuation_cases": valuation_cases,
        "family_interpolation": family_interp,
        "bb_snapshot": bb_snapshot,
        "combined": combined,
        "config_used": cfg,
        "bb_summary": dataclasses.asdict(bb),
        "scenario_results": [dataclasses.asdict(r) for r in results],
    }
    return out_json


def fmt_num(x: Any, digits: int = 2) -> str:
    try:
        v = float(x)
    except Exception:
        return "N/A"
    if math.isnan(v):
        return "N/A"
    return f"{v:.{digits}f}"


def fmt_pct(x: Any, digits: int = 2) -> str:
    try:
        v = float(x)
    except Exception:
        return "N/A"
    if math.isnan(v):
        return "N/A"
    return f"{v:.{digits}f}%"


def markdown_report(
    cfg: Dict[str, Any],
    bb: BBState,
    results: List[ScenarioResult],
    combined: Dict[str, Any],
    base_sources: Dict[str, str],
    drag_enabled: bool,
    drag_mode: str,
    drag_pts: float,
    schema_validation: Dict[str, Any],
) -> str:
    lines: List[str] = []
    pre = combined.get("pre_execution_review", {}) or {}
    fam = combined.get("family_interpolation", {}) or {}
    fam_targets = [float(x) for x in fam.get("targets", [])]

    lines.append("# 0050 Valuation × BB Merged Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- current_date: `{bb.date}`")
    lines.append(f"- current_0050_price: `{bb.price_used:.2f}`")
    lines.append(f"- bb_state: **{bb.state}**; bb_z=`{bb.bb_z:.4f}`")
    lines.append(f"- regime: **{bb.regime_tag}**; allowed=`{str(bb.regime_allowed).lower()}`")
    lines.append(f"- action_bucket: **{bb.action_bucket}**; pledge_policy=`{bb.pledge_policy}`")
    lines.append(f"- base_execution_bias: **{combined['base_execution_bias']}**")
    lines.append(f"- dq_overlay: **{combined['dq_overlay']}**")
    lines.append(f"- combined_execution_bias: **{combined['combined_execution_bias']}**")
    lines.append(f"- fast_shock_override: **{combined.get('fast_shock_override', 'NONE')}**")
    lines.append(f"- final_execution_bias: **{combined.get('final_execution_bias', combined['combined_execution_bias'])}**")
    lines.append(f"- action_instruction: `{combined.get('action_instruction', '')}`")
    if combined.get("matched_caution_flags"):
        lines.append(f"- matched_caution_flags: `{', '.join(combined['matched_caution_flags'])}`")
    if combined.get("matched_veto_flags"):
        lines.append(f"- matched_veto_flags: `{', '.join(combined['matched_veto_flags'])}`")
    if pre.get("trigger_reasons"):
        lines.append(f"- shock_trigger_reasons: `{', '.join(pre['trigger_reasons'])}`")
    if fam.get("enabled"):
        lines.append("- family_interpolation: **ENABLED** (display-only; no impact on final_execution_bias)")

    lines.append("")
    lines.append("## Base Inputs")
    lines.append(f"- base_0050: `{cfg['base']['base_0050']}` (source=`{base_sources['base_0050']}`)")
    lines.append(f"- base_tsmc: `{cfg['base']['base_tsmc']}` (source=`{base_sources['base_tsmc']}`)")
    lines.append(f"- tsmc_weight_in_0050: `{cfg['base']['tsmc_weight']}` (source=`{base_sources['tsmc_weight']}`)")
    lines.append(f"- dividend_drag_mode: `{drag_mode}`")
    lines.append(f"- dividend_drag_points_per_year: `{drag_pts}` (enabled=`{drag_enabled}`)")

    lines.append("")
    lines.append("## Valuation Scenario Table")
    lines.append("")
    lines.append("| scenario | years | EPS_base | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in results:
        lines.append(
            f"| {r.name} | {r.years_ahead} | {r.eps_base:.2f} | {r.eps_growth*100:.1f}% | {r.fx_haircut*100:.1f}% | {r.pe:.1f} | {r.other_ret*100:.1f}% | {r.tsmc_price:.2f} | {r.gross_0050:.2f} | {r.net_0050:.2f} |"
        )

    lines.append("")
    lines.append("## Current Price Position vs Scenario Net Range")
    cp = combined["valuation_range"]["current_price_position"]
    lines.append(f"- current_0050_price: `{cp['current_price']:.2f}`")
    lines.append(f"- scenario_net_range: `{fmt_num(cp['scenario_net_min'])}` ~ `{fmt_num(cp['scenario_net_max'])}`")
    lines.append(f"- percentile_in_scenario_net_range: `{fmt_num(cp['scenario_net_pctl'])}`")
    lines.append(f"- position_status: **{cp.get('position_status', 'N/A')}**")
    lines.append(f"- gap_vs_min: `{fmt_num(cp.get('gap_vs_min'))}`")
    lines.append(f"- gap_vs_max: `{fmt_num(cp.get('gap_vs_max'))}`")
    lines.append(f"- pct_vs_min: `{fmt_pct(cp.get('pct_vs_min'))}`")
    lines.append(f"- pct_vs_max: `{fmt_pct(cp.get('pct_vs_max'))}`")
    lines.append(f"- zone: **{cp['zone']}**")
    lines.append(f"- zone_note: `{cp['note']}`")

    if fam.get("enabled"):
        lines.append("")
        lines.append("## Family Interpolation Summary")
        lines.append("")
        lines.append("| family | years | axis | count | min | max | p10 | p25 | p50 | p75 | p90 | current_pctile | current_zone | current_status |")
        lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for f in fam.get("families", []):
            axis = f.get("interpolation_axis", {})
            stats = f.get("family_stats", {})
            lines.append(
                f"| {f.get('family_name')} | {f.get('years_ahead')} | "
                f"PE {axis.get('start')}~{axis.get('end')} step {axis.get('step')} | "
                f"{axis.get('count')} | "
                f"{fmt_num(stats.get('net_min'))} | "
                f"{fmt_num(stats.get('net_max'))} | "
                f"{fmt_num(stats.get('p10'))} | "
                f"{fmt_num(stats.get('p25'))} | "
                f"{fmt_num(stats.get('p50'))} | "
                f"{fmt_num(stats.get('p75'))} | "
                f"{fmt_num(stats.get('p90'))} | "
                f"{fmt_num(f.get('current_price_percentile'))} | "
                f"{f.get('current_zone')} | "
                f"{f.get('current_position_status')} |"
            )

        if fam_targets:
            lines.append("")
            lines.append("## Family Target Price Positions")
            headers: List[str] = [
                "family",
                "current_pctile",
                "current_zone",
                "current_status",
                "family_min",
                "family_max",
            ]
            for t in fam_targets:
                headers.extend([f"{t:.2f}_pctile", f"{t:.2f}_status"])

            aligns: List[str] = ["---", "---:", "---", "---", "---:", "---:"]
            for _ in fam_targets:
                aligns.extend(["---:", "---"])

            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(aligns) + " |")

            for f in fam.get("families", []):
                stats = f.get("family_stats", {})
                target_map = {float(tp["price"]): tp for tp in f.get("target_positions", [])}
                row = [
                    str(f.get("family_name")),
                    fmt_num(f.get("current_price_percentile")),
                    str(f.get("current_zone")),
                    str(f.get("current_position_status")),
                    fmt_num(stats.get("net_min")),
                    fmt_num(stats.get("net_max")),
                ]
                for t in fam_targets:
                    tp = target_map.get(float(t))
                    if tp is None:
                        row.extend(["N/A", "N/A"])
                    else:
                        row.extend([
                            fmt_num(tp.get("percentile")),
                            str(tp.get("position_status", "N/A")),
                        ])
                lines.append("| " + " | ".join(row) + " |")

        lines.append("")
        lines.append("### Family Interpolation Notes")
        lines.append(f"- enabled: `{fam.get('enabled')}`")
        lines.append(f"- targets: `{', '.join([str(t) for t in fam_targets])}`")
        lines.append(f"- note: `{fam.get('note', '')}`")
        lines.append("- boundary_note: `0 or 100 can simply mean target price is below family min or above family max.`")
        lines.append("- robustness_note: `2027_defensive_family is a display-only robustness check; it does not alter execution bias.`")

    lines.append("")
    lines.append("## BB Tranche References")
    lines.append("")
    lines.append("| label | price_level | vs_current_pct |")
    lines.append("|---|---:|---:|")
    for t in combined["tranche_reference"]:
        vsp = t["vs_current_pct"]
        vsp_str = "N/A" if vsp is None or math.isnan(vsp) else f"{vsp:.2f}%"
        price_level = t["price_level"]
        price_str = "N/A" if price_level is None or math.isnan(price_level) else f"{price_level:.2f}"
        lines.append(f"| {t['label']} | {price_str} | {vsp_str} |")

    lines.append("")
    lines.append("## Pre-Execution Review")
    lines.append(f"- available: `{pre.get('available', False)}`")
    lines.append(f"- roll25_report_path: `{pre.get('source_path')}`")
    lines.append(f"- band1: `{pre.get('band1')}`")
    lines.append(f"- band2: `{pre.get('band2')}`")
    lines.append(f"- tx_night_last: `{pre.get('tx_night_last')}`")
    lines.append(f"- tx_vs_band1: `{pre.get('tx_vs_band1')}`")
    lines.append(f"- tx_vs_band2: `{pre.get('tx_vs_band2')}`")
    lines.append(f"- preopen_shock_flag: **{pre.get('preopen_shock_flag', 'NONE')}**")
    lines.append(f"- shock_override: **{pre.get('shock_override', 'NONE')}**")
    if pre.get("trigger_reasons"):
        lines.append(f"- trigger_reasons: `{', '.join(pre['trigger_reasons'])}`")
    if pre.get("parse_notes"):
        lines.append(f"- parse_notes: `{'; '.join(pre['parse_notes'])}`")

    lines.append("")
    lines.append("## Data Quality")
    if bb.dq_flags:
        for flag in bb.dq_flags:
            lines.append(f"- {flag}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Schema Validation")
    lines.append(f"- validated: `{schema_validation.get('validated', False)}`")
    lines.append(f"- tranche_levels_present: `{schema_validation.get('tranche_levels_present', False)}`")

    lines.append("")
    lines.append("## How to Use")
    lines.append("- Step 1: Use the valuation table to decide whether current price is in a low / fair / high zone.")
    lines.append("- Step 1b: Use family interpolation summary to refine valuation readability across fixed assumption families.")
    lines.append("- Step 2: Read current_status / target_status first. A percentile of 0 or 100 may simply mean out-of-range, not model failure.")
    lines.append("- Step 3: Use 2027_defensive_family only as a robustness check: ask whether the price still looks acceptable under milder defensive assumptions.")
    lines.append("- Step 4: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.")
    lines.append("- Step 5: Use pre-execution review to override the action bias when TX night close breaches roll25 bands.")
    lines.append("- Step 6: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.")

    lines.append("")
    lines.append("## Notes")
    lines.append("- base_0050 is auto-resolved from bb-stats unless overridden.")
    lines.append("- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.")
    lines.append("- eps_base is a slow-moving fundamental anchor; revise only when earnings/model basis changes.")
    lines.append("- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.")
    lines.append("- Mixed-horizon scenario percentile combines 1Y and 2Y cases; treat it as display-only, not primary execution input.")
    lines.append("- Family interpolation is display-only and does not alter base_execution_bias / combined_execution_bias / final_execution_bias.")
    lines.append("- 2027_defensive_family is a robustness check only; it does not introduce a new trading rule by itself.")
    lines.append("- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.")
    lines.append("- Pre-execution review reads Band 1 / Band 2 from roll25 markdown report; if parsing fails, no shock override is applied.")
    lines.append("- TX night close is manual input and should be checked carefully before running the script.")
    lines.append("- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge 0050 valuation map with BB execution map.")
    parser.add_argument("--bb-stats", required=True, help="Path to tw0050_bb_cache/stats_latest.json")
    parser.add_argument("--config", required=False, help="Optional valuation config JSON")
    parser.add_argument("--base-0050", type=float, required=False, help="Override base 0050 price")
    parser.add_argument("--base-tsmc", type=float, required=False, help="Override base TSMC price")
    parser.add_argument("--tsmc-weight", type=float, required=False, help="Override TSMC weight in 0050")
    parser.add_argument("--roll25-report", required=False, help="Optional path to roll25 markdown report")
    parser.add_argument("--tx-night-last", type=float, required=False, help="Optional manual TX night-session close")
    parser.add_argument("--out-json", required=True, help="Output JSON path")
    parser.add_argument("--out-md", required=True, help="Output Markdown path")
    args = parser.parse_args()

    bb_stats_path = Path(args.bb_stats)
    bb_stats = load_json(bb_stats_path)

    schema_validation = validate_bb_stats_schema(bb_stats)

    user_cfg = load_json(Path(args.config)) if args.config else None
    cfg = merge_config(user_cfg)

    cfg, base_sources = apply_resolved_bases(
        cfg=cfg,
        bb_stats=bb_stats,
        cli_base_0050=args.base_0050,
        cli_base_tsmc=args.base_tsmc,
        cli_tsmc_weight=args.tsmc_weight,
    )

    drag_enabled, drag_mode, drag_pts = resolve_dividend_drag(cfg)

    bb = parse_bb_stats(bb_stats)
    results = build_results(cfg, drag_enabled=drag_enabled, drag_pts=drag_pts)
    family_interp = build_family_interpolation(
        cfg=cfg,
        current_price=bb.price_used,
        drag_enabled=drag_enabled,
        drag_pts=drag_pts,
    )

    pre_review = build_pre_execution_review(
        roll25_report_path=args.roll25_report,
        tx_night_last=args.tx_night_last,
    )

    combined = build_combined_view(
        bb=bb,
        results=results,
        dq_policy=cfg.get("dq_policy", {}),
        pre_review=pre_review,
        family_interp=family_interp,
    )

    out_json = build_output_json(
        cfg=cfg,
        bb=bb,
        results=results,
        family_interp=family_interp,
        combined=combined,
        bb_stats_path=str(bb_stats_path),
        roll25_report_path=args.roll25_report,
        tx_night_last=args.tx_night_last,
        base_sources=base_sources,
        drag_enabled=drag_enabled,
        drag_mode=drag_mode,
        drag_pts=drag_pts,
        schema_validation=schema_validation,
    )

    out_json_path = Path(args.out_json)
    out_md_path = Path(args.out_md)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)

    with out_json_path.open("w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)

    with out_md_path.open("w", encoding="utf-8") as f:
        f.write(
            markdown_report(
                cfg=cfg,
                bb=bb,
                results=results,
                combined=combined,
                base_sources=base_sources,
                drag_enabled=drag_enabled,
                drag_mode=drag_mode,
                drag_pts=drag_pts,
                schema_validation=schema_validation,
            )
        )


if __name__ == "__main__":
    main()