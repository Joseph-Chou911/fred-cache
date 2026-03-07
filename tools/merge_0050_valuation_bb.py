#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge_0050_valuation_bb.py

Purpose
-------
Merge two layers into one deterministic report:
1) Valuation map:
   EPS growth / FX haircut / P-E multiple -> TSMC fair price -> 0050 fair price
2) Execution map:
   current BB / regime / tranche references from tw0050_bb_cache/stats_latest.json

Design principles
-----------------
- Audit-first: every output should be reproducible from explicit inputs.
- No web calls in the script.
- Keep valuation inputs configurable and slow-moving; keep BB inputs market-driven and fast-moving.
- Separate gross price (before dividend-drag display adjustment) from net/display price.
- Backward-compatible JSON schema:
  * keep old keys: config_used / bb_summary / scenario_results / combined
  * add new keys: meta / inputs / valuation_cases / bb_snapshot
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
        "config_version": "0050_merge_v1.1",
        "note": (
            "Fixed rules, moving outputs. Update slow variables deliberately; "
            "update fast variables daily after close."
        ),
    },
    "base": {
        "base_0050": 76.85,
        "base_tsmc": 1890.0,
        "tsmc_weight": 0.6408,
    },
    "dividend_drag": {
        "enabled": True,
        "points_per_year": 1.0,
        "note": "Display-price sensitivity only. Keep total-return thinking separate.",
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


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def merge_config(user_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not user_cfg:
        return json.loads(json.dumps(DEFAULT_CONFIG))

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
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

    price_used_raw = latest.get("price_used", latest.get("close", float("nan")))
    try:
        price_used = float(price_used_raw)
    except Exception:
        price_used = float("nan")

    try:
        bb_z = float(latest.get("bb_z", float("nan")))
    except Exception:
        bb_z = float("nan")

    try:
        rv20_pctl = float(stats.get("vol", {}).get("rv_ann_pctl", float("nan")))
    except Exception:
        rv20_pctl = float("nan")

    return BBState(
        date=str(latest.get("date", "")),
        price_used=price_used,
        state=str(latest.get("state", "N/A")),
        bb_z=bb_z,
        regime_tag=str(regime.get("tag", "N/A")),
        regime_allowed=bool(regime.get("allowed", False)),
        rv20_percentile=rv20_pctl,
        action_bucket=str(pledge_decision.get("action_bucket", "N/A")),
        pledge_policy=str(pledge_decision.get("pledge_policy", "N/A")),
        tranche_levels=list(levels),
        dq_flags=list(dq_flags),
    )


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


def build_results(cfg: Dict[str, Any]) -> List[ScenarioResult]:
    base_0050 = float(cfg["base"]["base_0050"])
    base_tsmc = float(cfg["base"]["base_tsmc"])
    tsmc_weight = float(cfg["base"]["tsmc_weight"])
    drag_enabled = bool(cfg["dividend_drag"].get("enabled", True))
    drag_pts = float(cfg["dividend_drag"].get("points_per_year", 1.0))

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
    }


def build_combined_view(bb: BBState, results: List[ScenarioResult]) -> Dict[str, Any]:
    net_prices = [r.net_0050 for r in results]
    gross_prices = [r.gross_0050 for r in results]
    price_pos = classify_price(bb.price_used, net_prices)

    tranche_levels = []
    for level in bb.tranche_levels:
        try:
            price_level = float(level.get("price_level", float("nan")))
        except Exception:
            price_level = float("nan")

        tranche_levels.append(
            {
                "label": level.get("label", ""),
                "price_level": price_level,
                "vs_current_pct": ((price_level / bb.price_used) - 1.0) * 100.0 if bb.price_used else None,
            }
        )

    if bb.regime_allowed is False and "UPPER" in bb.state:
        execution_bias = "DEFENSIVE_NO_CHASE"
    elif price_pos["zone"] in {"LOWER_ZONE", "LOWER_MID_ZONE"} and bb.regime_allowed:
        execution_bias = "ALLOW_STAGED_ACCUMULATION"
    else:
        execution_bias = "WAIT_FOR_BETTER_ALIGNMENT"

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
        "combined_execution_bias": execution_bias,
        "how_to_read": {
            "layer_1": "Use valuation scenarios to decide whether the current zone is cheap / fair / expensive.",
            "layer_2": "Use BB/regime/tranche references to decide whether to act now or wait.",
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
        "dividend_drag": {
            "enabled": bool(cfg["dividend_drag"].get("enabled", True)),
            "points_per_year": float(cfg["dividend_drag"].get("points_per_year", 1.0)),
            "note": str(cfg["dividend_drag"].get("note", "")),
        },
        "current_date": bb.date,
        "current_0050_price": bb.price_used,
        "current_bb_state": bb.state,
        "current_bb_z": bb.bb_z,
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
        # new schema (for workflow assert)
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


def markdown_report(cfg: Dict[str, Any], bb: BBState, results: List[ScenarioResult], combined: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# 0050 Valuation × BB Merged Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- current_date: `{bb.date}`")
    lines.append(f"- current_0050_price: `{bb.price_used:.2f}`")
    lines.append(f"- bb_state: **{bb.state}**; bb_z=`{bb.bb_z:.4f}`")
    lines.append(f"- regime: **{bb.regime_tag}**; allowed=`{str(bb.regime_allowed).lower()}`")
    lines.append(f"- action_bucket: **{bb.action_bucket}**; pledge_policy=`{bb.pledge_policy}`")
    lines.append(f"- combined_execution_bias: **{combined['combined_execution_bias']}**")
    lines.append("")
    lines.append("## Base Inputs")
    lines.append(f"- base_0050: `{cfg['base']['base_0050']}`")
    lines.append(f"- base_tsmc: `{cfg['base']['base_tsmc']}`")
    lines.append(f"- tsmc_weight_in_0050: `{cfg['base']['tsmc_weight']}`")
    lines.append(f"- dividend_drag_points_per_year: `{cfg['dividend_drag']['points_per_year']}` (enabled=`{cfg['dividend_drag']['enabled']}`)")
    lines.append("")
    lines.append("## Valuation Scenario Table")
    lines.append("")
    lines.append("| scenario | years | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in results:
        lines.append(
            f"| {r.name} | {r.years_ahead} | {r.eps_growth*100:.1f}% | {r.fx_haircut*100:.1f}% | {r.pe:.1f} | {r.other_ret*100:.1f}% | {r.tsmc_price:.2f} | {r.gross_0050:.2f} | {r.net_0050:.2f} |"
        )

    lines.append("")
    lines.append("## Current Price Position vs Scenario Net Range")
    cp = combined["valuation_range"]["current_price_position"]
    lines.append(f"- current_0050_price: `{cp['current_price']:.2f}`")
    lines.append(f"- scenario_net_range: `{cp['scenario_net_min']:.2f}` ~ `{cp['scenario_net_max']:.2f}`")
    lines.append(f"- percentile_in_scenario_net_range: `{cp['scenario_net_pctl']:.2f}`")
    lines.append(f"- zone: **{cp['zone']}**")

    lines.append("")
    lines.append("## BB Tranche References")
    lines.append("")
    lines.append("| label | price_level | vs_current_pct |")
    lines.append("|---|---:|---:|")
    for t in combined["tranche_reference"]:
        vsp = t["vs_current_pct"]
        if vsp is None or math.isnan(vsp):
            vsp_str = "N/A"
        else:
            vsp_str = f"{vsp:.2f}%"
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
    lines.append("## How to Use")
    lines.append("- Step 1: Use the valuation table to decide whether current price is in a low / fair / high zone.")
    lines.append("- Step 2: Use BB state, regime, and tranche references to decide whether to act now or wait.")
    lines.append("- Step 3: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.")

    lines.append("")
    lines.append("## Notes")
    lines.append("- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.")
    lines.append("- Slow-moving inputs: EPS growth assumptions, FX haircut assumptions, P/E bands, dividend drag.")
    lines.append("- Fast-moving inputs: current 0050 price, BB state, regime, tranche levels, and TSMC weight if refreshed.")

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

    user_cfg = load_json(Path(args.config)) if args.config else None
    cfg = merge_config(user_cfg)

    if args.base_0050 is not None:
        cfg["base"]["base_0050"] = args.base_0050
    if args.base_tsmc is not None:
        cfg["base"]["base_tsmc"] = args.base_tsmc
    if args.tsmc_weight is not None:
        cfg["base"]["tsmc_weight"] = args.tsmc_weight

    bb = parse_bb_stats(bb_stats)
    results = build_results(cfg)
    combined = build_combined_view(bb, results)

    out_json = build_output_json(
        cfg=cfg,
        bb=bb,
        results=results,
        combined=combined,
        bb_stats_path=str(bb_stats_path),
    )

    out_json_path = Path(args.out_json)
    out_md_path = Path(args.out_md)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)

    with out_json_path.open("w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)

    with out_md_path.open("w", encoding="utf-8") as f:
        f.write(markdown_report(cfg, bb, results, combined))


if __name__ == "__main__":
    main()