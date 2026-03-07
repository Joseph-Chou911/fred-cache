#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge_0050_valuation_bb.py  (v1.3)

Purpose
-------
Merge two layers into one deterministic report:
1) Valuation map:
   EPS growth / FX haircut / P-E multiple -> TSMC fair price -> 0050 fair price
2) Execution map:
   current BB / regime / tranche references from tw0050_bb_cache/stats_latest.json

v1.3 changes
------------
- Add DQ-aware execution bias downgrade / veto logic
- Add dividend_drag mode: off / light / heavy / custom
- Add internal schema validation for bb-stats
- Mark valuation zone as rough classification only
- Keep backward-compatible JSON schema:
  * old keys: config_used / bb_summary / scenario_results / combined
  * new keys: meta / inputs / valuation_cases / bb_snapshot
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
        "config_version": "0050_merge_v1.3",
        "note": (
            "Fixed rules, moving outputs. Update slow variables deliberately; "
            "update fast variables daily after close."
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
        # Structural schema problems should fail fast before this policy is used.
        # These are data-quality flags that should at least downgrade trust.
        "caution_flags": [
            "PRICE_SERIES_BREAK_DETECTED",
            "FWD_MDD_CLEAN_APPLIED",
            "RAW_OUTLIER_EXCLUDED_BY_CLEAN",
            "FWD_MDD_OUTLIER_MIN_RAW_20D",
        ],
        # If future you adds more severe flags, put them here.
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


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def deep_copy_jsonable(x: Any) -> Any:
    return json.loads(json.dumps(x, ensure_ascii=False))


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    """
    Fail fast if required keys are missing.
    This prevents silent downstream misinterpretation when stats schema changes.
    """
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
    """
    Intentionally shallow at the top level.
    Note:
    - dict keys like meta/base/dividend_drag/dq_policy will update shallowly
    - scenario_groups, if provided, replace the default list as a whole
    """
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

    # backward-compatible fallback
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


def classify_price(current_price: float, xs: List[float]) -> Dict[str, Any]:
    ordered = sorted(xs)
    pctl = percentile_rank(current_price, ordered)
    if math.isnan(pctl):
        zone = "N/A"
    elif pctl <= 20:
        zone = "LOWER_ZONE"
    elif pctl <= 40:
        zone = "LOWER_MID_ZONE"
    elif pctl <= 60:
        zone = "MID_ZONE"
    elif pctl <= 80:
        zone = "UPPER_MID_ZONE"
    else:
        zone = "UPPER_ZONE"
    return {
        "current_price": current_price,
        "scenario_net_min": min(ordered) if ordered else None,
        "scenario_net_max": max(ordered) if ordered else None,
        "scenario_net_pctl": pctl,
        "zone": zone,
        "note": "rough classification only; sparse scenario set => low percentile resolution",
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


def build_combined_view(bb: BBState, results: List[ScenarioResult], dq_policy: Dict[str, Any]) -> Dict[str, Any]:
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

    return {
        "bb": dataclasses.asdict(bb),
        "valuation_range": {
            "gross_min": min(gross_prices) if gross_prices else None,
            "gross_max": max(gross_prices) if gross_prices else None,
            "net_min": min(net_prices) if net_prices else None,
            "net_max": max(net_prices) if net_prices else None,
            "current_price_position": price_pos,
        },
        "tranche_reference": tranche_levels,
        "base_execution_bias": exec_info["base_execution_bias"],
        "dq_overlay": exec_info["dq_overlay"],
        "matched_caution_flags": exec_info["matched_caution_flags"],
        "matched_veto_flags": exec_info["matched_veto_flags"],
        "combined_execution_bias": exec_info["combined_execution_bias"],
        "how_to_read": {
            "layer_1": "Use valuation scenarios to decide whether the current zone is cheap / fair / expensive.",
            "layer_2": "Use BB/regime/tranche references to decide whether to act now or wait.",
            "zone_note": "valuation zone is rough classification only; do not over-interpret sparse-percentile output.",
            "dq_note": "DQ flags can downgrade or veto action bias even when valuation or regime otherwise look acceptable.",
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
    combined: Dict[str, Any],
    bb_stats_path: str,
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
        "schema_version": "0050_merge_schema_v1_compat",
        "config_version": cfg.get("meta", {}).get("config_version", "unknown"),
        "note": cfg.get("meta", {}).get("note", ""),
    }

    inputs = {
        "bb_stats_path": bb_stats_path,
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
        # new schema
        "meta": meta,
        "inputs": inputs,
        "valuation_cases": valuation_cases,
        "bb_snapshot": bb_snapshot,

        # compatibility / richer sections
        "combined": combined,
        "config_used": cfg,
        "bb_summary": dataclasses.asdict(bb),
        "scenario_results": [dataclasses.asdict(r) for r in results],
    }
    return out_json


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
    if combined.get("matched_caution_flags"):
        lines.append(f"- matched_caution_flags: `{', '.join(combined['matched_caution_flags'])}`")
    if combined.get("matched_veto_flags"):
        lines.append(f"- matched_veto_flags: `{', '.join(combined['matched_veto_flags'])}`")

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
    lines.append(f"- scenario_net_range: `{cp['scenario_net_min']:.2f}` ~ `{cp['scenario_net_max']:.2f}`")
    lines.append(f"- percentile_in_scenario_net_range: `{cp['scenario_net_pctl']:.2f}`")
    lines.append(f"- zone: **{cp['zone']}**")
    lines.append(f"- zone_note: `{cp['note']}`")

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
    lines.append("- Step 2: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.")
    lines.append("- Step 3: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.")

    lines.append("")
    lines.append("## Notes")
    lines.append("- base_0050 is auto-resolved from bb-stats unless overridden.")
    lines.append("- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.")
    lines.append("- eps_base is a slow-moving fundamental anchor; revise only when earnings/model basis changes.")
    lines.append("- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.")
    lines.append("- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.")
    lines.append("- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge 0050 valuation map with BB execution map.")
    parser.add_argument("--bb-stats", required=True, help="Path to tw0050_bb_cache/stats_latest.json")
    parser.add_argument("--config", required=False, help="Optional valuation config JSON")
    parser.add_argument("--base-0050", type=float, required=False, help="Override base 0050 price")
    parser.add_argument("--base-tsmc", type=float, required=False, help="Override base TSMC price")
    parser.add_argument("--tsmc-weight", type=float, required=False, help="Override TSMC weight in 0050")
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
    combined = build_combined_view(
        bb=bb,
        results=results,
        dq_policy=cfg.get("dq_policy", {}),
    )

    out_json = build_output_json(
        cfg=cfg,
        bb=bb,
        results=results,
        combined=combined,
        bb_stats_path=str(bb_stats_path),
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