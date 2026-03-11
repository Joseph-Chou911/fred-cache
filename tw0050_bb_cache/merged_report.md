# 0050 Valuation × BB Merged Report

## Summary
- current_date: `2026-03-11`
- current_0050_price: `78.20`
- bb_state: **NEAR_UPPER_BAND**; bb_z=`1.4226`
- regime: **RISK_OFF_OR_DEFENSIVE**; allowed=`false`
- action_bucket: **VETO**; pledge_policy=`DISALLOW`
- base_execution_bias: **DEFENSIVE_NO_CHASE**
- dq_overlay: **CAUTION**
- combined_execution_bias: **DEFENSIVE_NO_CHASE**
- matched_caution_flags: `FWD_MDD_CLEAN_APPLIED, FWD_MDD_OUTLIER_MIN_RAW_20D, PRICE_SERIES_BREAK_DETECTED, RAW_OUTLIER_EXCLUDED_BY_CLEAN`

## Base Inputs
- base_0050: `78.19999694824219` (source=`bb_stats.latest.price_used`)
- base_tsmc: `1890.0` (source=`cli`)
- tsmc_weight_in_0050: `0.6408` (source=`config`)
- dividend_drag_mode: `light`
- dividend_drag_points_per_year: `1.0` (enabled=`True`)

## Valuation Scenario Table

| scenario | years | EPS_base | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026_壓力 | 1 | 66.25 | 20.0% | 6.0% | 18.0 | -15.0% | 1345.14 | 59.54 | 58.54 |
| 2026_保守 | 1 | 66.25 | 20.0% | 3.0% | 20.0 | -8.0% | 1542.30 | 66.73 | 65.73 |
| 2026_中性偏保守 | 1 | 66.25 | 25.0% | 3.0% | 22.0 | -3.0% | 1767.22 | 74.10 | 73.10 |
| 2026_中性 | 1 | 66.25 | 25.0% | 0.0% | 24.0 | 0.0% | 1987.50 | 80.79 | 79.79 |
| 2027_中性 | 2 | 66.25 | 25.0% | 6.0% | 22.0 | 2.0% | 2140.70 | 85.41 | 83.41 |
| 2027_中性偏樂觀 | 2 | 66.25 | 25.0% | 0.0% | 24.0 | 5.0% | 2484.38 | 95.36 | 93.36 |
| 2027_樂觀延續 | 2 | 66.25 | 30.0% | 0.0% | 24.0 | 5.0% | 2687.10 | 100.74 | 98.74 |

## Current Price Position vs Scenario Net Range
- current_0050_price: `78.20`
- scenario_net_range: `58.54` ~ `98.74`
- percentile_in_scenario_net_range: `42.86`
- zone: **MID_ZONE**
- zone_note: `rough classification only; sparse scenario set => low percentile resolution`

## BB Tranche References

| label | price_level | vs_current_pct |
|---|---:|---:|
| 10D_p10_uncond | 74.45 | -4.80% |
| 10D_p05_uncond | 73.27 | -6.30% |
| 20D_p10_uncond | 72.83 | -6.86% |
| 20D_p05_uncond | 70.96 | -9.26% |

## Data Quality
- PRICE_SERIES_BREAK_DETECTED
- FWD_MDD_CLEAN_APPLIED
- FWD_MDD_OUTLIER_MIN_RAW_20D
- RAW_OUTLIER_EXCLUDED_BY_CLEAN

## Schema Validation
- validated: `True`
- tranche_levels_present: `True`

## How to Use
- Step 1: Use the valuation table to decide whether current price is in a low / fair / high zone.
- Step 2: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.
- Step 3: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.

## Notes
- base_0050 is auto-resolved from bb-stats unless overridden.
- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.
- eps_base is a slow-moving fundamental anchor; revise only when earnings/model basis changes.
- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.
- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.
- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.
