# 0050 Valuation × BB Merged Report

## Summary
- current_date: `2026-03-13`
- current_0050_price: `76.15`
- bb_state: **IN_BAND**; bb_z=`1.0188`
- regime: **RISK_OFF_OR_DEFENSIVE**; allowed=`false`
- action_bucket: **VETO**; pledge_policy=`DISALLOW`
- base_execution_bias: **WAIT_FOR_BETTER_ALIGNMENT**
- dq_overlay: **CAUTION**
- combined_execution_bias: **WAIT_WITH_DQ_CAUTION**
- fast_shock_override: **NONE**
- final_execution_bias: **WAIT_WITH_DQ_CAUTION**
- action_instruction: `觀察為主；等待更好對齊，且留意 DQ。`
- matched_caution_flags: `FWD_MDD_CLEAN_APPLIED, FWD_MDD_OUTLIER_MIN_RAW_20D, PRICE_SERIES_BREAK_DETECTED, RAW_OUTLIER_EXCLUDED_BY_CLEAN`
- family_interpolation: **ENABLED** (display-only; no impact on final_execution_bias)

## Base Inputs
- base_0050: `76.1500015258789` (source=`bb_stats.latest.price_used`)
- base_tsmc: `1870.0` (source=`cli`)
- tsmc_weight_in_0050: `0.6408` (source=`config`)
- dividend_drag_mode: `light`
- dividend_drag_points_per_year: `1.0` (enabled=`True`)

## Valuation Scenario Table

| scenario | years | EPS_base | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026_壓力 | 1 | 66.25 | 20.0% | 6.0% | 18.0 | -15.0% | 1345.14 | 58.35 | 57.35 |
| 2026_保守 | 1 | 66.25 | 20.0% | 3.0% | 20.0 | -8.0% | 1542.30 | 65.41 | 64.41 |
| 2026_中性偏保守 | 1 | 66.25 | 25.0% | 3.0% | 22.0 | -3.0% | 1767.22 | 72.65 | 71.65 |
| 2026_中性 | 1 | 66.25 | 25.0% | 0.0% | 24.0 | 0.0% | 1987.50 | 79.22 | 78.22 |
| 2027_中性 | 2 | 66.25 | 25.0% | 6.0% | 22.0 | 2.0% | 2140.70 | 83.76 | 81.76 |
| 2027_中性偏樂觀 | 2 | 66.25 | 25.0% | 0.0% | 24.0 | 5.0% | 2484.38 | 93.55 | 91.55 |
| 2027_樂觀延續 | 2 | 66.25 | 30.0% | 0.0% | 24.0 | 5.0% | 2687.10 | 98.84 | 96.84 |

## Current Price Position vs Scenario Net Range
- current_0050_price: `76.15`
- scenario_net_range: `57.35` ~ `96.84`
- percentile_in_scenario_net_range: `42.86`
- zone: **MID_ZONE**
- zone_note: `rough classification only; sparse scenario set => low percentile resolution`

## Family Interpolation Summary

| family | years | axis | count | p10 | p25 | p50 | p75 | p90 | current_pctile | current_zone |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026_conservative_family | 1 | PE 18.0~24.0 step 0.5 | 13 | 61.59 | 63.40 | 66.42 | 69.44 | 71.25 | 100.00 | RICH |
| 2026_neutralish_family | 1 | PE 20.0~24.0 step 0.5 | 9 | 68.29 | 69.55 | 71.65 | 73.74 | 75.00 | 100.00 | RICH |
| 2027_neutral_family | 2 | PE 20.0~24.0 step 0.5 | 9 | 77.70 | 79.22 | 81.76 | 84.30 | 85.82 | 0.00 | CHEAP |

## Family Target Price Positions
| family | current_pctile | current_zone | 72.00_pctile | 71.00_pctile | 69.00_pctile |
|---|---:|---:|---:|---:|---|
| 2026_conservative_family | 100.00 | RICH | 92.31 | 84.62 | 69.23 |
| 2026_neutralish_family | 100.00 | RICH | 55.56 | 44.44 | 22.22 |
| 2027_neutral_family | 0.00 | CHEAP | 0.00 | 0.00 | 0.00 |

### Family Interpolation Notes
- enabled: `True`
- targets: `72.0, 71.0, 69.0`
- note: `Display-only. Single-axis dense interpolation within fixed assumption families. This section improves valuation readability but does not alter execution bias.`

## BB Tranche References

| label | price_level | vs_current_pct |
|---|---:|---:|
| 10D_p10_uncond | 72.49 | -4.81% |
| 10D_p05_uncond | 71.32 | -6.35% |
| 20D_p10_uncond | 70.92 | -6.86% |
| 20D_p05_uncond | 69.10 | -9.26% |

## Pre-Execution Review
- available: `True`
- roll25_report_path: `roll25_cache/report.md`
- band1: `33057.836667`
- band2: `32541.990382`
- tx_night_last: `33274.0`
- tx_vs_band1: `216.16333299999678`
- tx_vs_band2: `732.009618`
- preopen_shock_flag: **NONE**
- shock_override: **NONE**

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
- Step 1b: Use family interpolation summary to refine valuation readability across fixed assumption families.
- Step 2: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.
- Step 3: Use pre-execution review to override the action bias when TX night close breaches roll25 bands.
- Step 4: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.

## Notes
- base_0050 is auto-resolved from bb-stats unless overridden.
- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.
- eps_base is a slow-moving fundamental anchor; revise only when earnings/model basis changes.
- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.
- Family interpolation is display-only and does not alter base_execution_bias / combined_execution_bias / final_execution_bias.
- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.
- Pre-execution review reads Band 1 / Band 2 from roll25 markdown report; if parsing fails, no shock override is applied.
- TX night close is manual input and should be checked carefully before running the script.
- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.
