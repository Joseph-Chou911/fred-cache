# 0050 Valuation × BB Merged Report

## Summary
- current_date: `2026-03-13`
- current_0050_price: `76.05`
- bb_state: **IN_BAND**; bb_z=`1.0023`
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
- base_0050: `76.05000305175781` (source=`bb_stats.latest.price_used`)
- base_tsmc: `1875.0` (source=`cli`)
- tsmc_weight_in_0050: `0.6408` (source=`config`)
- dividend_drag_mode: `light`
- dividend_drag_points_per_year: `1.0` (enabled=`True`)

## Valuation Scenario Table

| scenario | years | EPS_base | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026_壓力 | 1 | 66.25 | 20.0% | 6.0% | 18.0 | -15.0% | 1345.14 | 58.18 | 57.18 |
| 2026_保守 | 1 | 66.25 | 20.0% | 3.0% | 20.0 | -8.0% | 1542.30 | 65.22 | 64.22 |
| 2026_中性偏保守 | 1 | 66.25 | 25.0% | 3.0% | 22.0 | -3.0% | 1767.22 | 72.43 | 71.43 |
| 2026_中性 | 1 | 66.25 | 25.0% | 0.0% | 24.0 | 0.0% | 1987.50 | 78.97 | 77.97 |
| 2027_中性 | 2 | 66.25 | 25.0% | 6.0% | 22.0 | 2.0% | 2140.70 | 83.50 | 81.50 |
| 2027_中性偏樂觀 | 2 | 66.25 | 25.0% | 0.0% | 24.0 | 5.0% | 2484.38 | 93.25 | 91.25 |
| 2027_樂觀延續 | 2 | 66.25 | 30.0% | 0.0% | 24.0 | 5.0% | 2687.10 | 98.52 | 96.52 |

## Current Price Position vs Scenario Net Range
- current_0050_price: `76.05`
- scenario_net_range: `57.18` ~ `96.52`
- percentile_in_scenario_net_range: `42.86`
- position_status: **IN_RANGE**
- gap_vs_min: `18.87`
- gap_vs_max: `-20.47`
- pct_vs_min: `33.00%`
- pct_vs_max: `-21.21%`
- zone: **MID_ZONE**
- zone_note: `rough classification only; sparse scenario set and mixed 1Y/2Y horizons => low decision value`

## Family Interpolation Summary

| family | years | axis | count | min | max | p10 | p25 | p50 | p75 | p90 | current_pctile | current_zone | current_status |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026_conservative_family | 1 | PE 18.0~24.0 step 0.5 | 13 | 60.21 | 72.23 | 61.41 | 63.22 | 66.22 | 69.23 | 71.03 | 100.00 | RICH | ABOVE_MAX |
| 2026_neutralish_family | 1 | PE 20.0~24.0 step 0.5 | 9 | 67.25 | 75.60 | 68.09 | 69.34 | 71.43 | 73.52 | 74.77 | 100.00 | RICH | ABOVE_MAX |
| 2027_neutral_family | 2 | PE 20.0~24.0 step 0.5 | 9 | 76.44 | 86.56 | 77.46 | 78.97 | 81.50 | 84.03 | 85.55 | 0.00 | CHEAP | BELOW_MIN |
| 2027_defensive_family | 2 | PE 18.0~22.0 step 0.5 | 9 | 67.27 | 76.59 | 68.20 | 69.60 | 71.93 | 74.26 | 75.66 | 88.89 | RICH | IN_RANGE |

## Family Target Price Positions
| family | current_pctile | current_zone | current_status | family_min | family_max | 72.00_pctile | 72.00_status | 71.00_pctile | 71.00_status | 69.00_pctile | 69.00_status |
| --- | ---: | --- | --- | ---: | ---: | ---: | --- | ---: | --- | ---: | --- |
| 2026_conservative_family | 100.00 | RICH | ABOVE_MAX | 60.21 | 72.23 | 92.31 | IN_RANGE | 84.62 | IN_RANGE | 69.23 | IN_RANGE |
| 2026_neutralish_family | 100.00 | RICH | ABOVE_MAX | 67.25 | 75.60 | 55.56 | IN_RANGE | 44.44 | IN_RANGE | 22.22 | IN_RANGE |
| 2027_neutral_family | 0.00 | CHEAP | BELOW_MIN | 76.44 | 86.56 | 0.00 | BELOW_MIN | 0.00 | BELOW_MIN | 0.00 | BELOW_MIN |
| 2027_defensive_family | 88.89 | RICH | IN_RANGE | 67.27 | 76.59 | 55.56 | IN_RANGE | 44.44 | IN_RANGE | 22.22 | IN_RANGE |

### Family Interpolation Notes
- enabled: `True`
- targets: `72.0, 71.0, 69.0`
- note: `Display-only. Single-axis dense interpolation within fixed assumption families. This section improves valuation readability but does not alter execution bias.`
- boundary_note: `0 or 100 can simply mean target price is below family min or above family max.`
- robustness_note: `2027_defensive_family is a display-only robustness check; it does not alter execution bias.`

## BB Tranche References

| label | price_level | vs_current_pct |
|---|---:|---:|
| 10D_p10_uncond | 72.39 | -4.81% |
| 10D_p05_uncond | 71.22 | -6.35% |
| 20D_p10_uncond | 70.83 | -6.86% |
| 20D_p05_uncond | 69.01 | -9.26% |

## Pre-Execution Review
- available: `True`
- roll25_report_path: `roll25_cache/report.md`
- band1: `33057.836667`
- band2: `32541.990382`
- tx_night_last: `33284.0`
- tx_vs_band1: `226.16333299999678`
- tx_vs_band2: `742.009618`
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
- Step 2: Read current_status / target_status first. A percentile of 0 or 100 may simply mean out-of-range, not model failure.
- Step 3: Use 2027_defensive_family only as a robustness check: ask whether the price still looks acceptable under milder defensive assumptions.
- Step 4: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.
- Step 5: Use pre-execution review to override the action bias when TX night close breaches roll25 bands.
- Step 6: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.

## Notes
- base_0050 is auto-resolved from bb-stats unless overridden.
- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.
- eps_base is a slow-moving fundamental anchor; revise only when earnings/model basis changes.
- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.
- Mixed-horizon scenario percentile combines 1Y and 2Y cases; treat it as display-only, not primary execution input.
- Family interpolation is display-only and does not alter base_execution_bias / combined_execution_bias / final_execution_bias.
- 2027_defensive_family is a robustness check only; it does not introduce a new trading rule by itself.
- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.
- Pre-execution review reads Band 1 / Band 2 from roll25 markdown report; if parsing fails, no shock override is applied.
- TX night close is manual input and should be checked carefully before running the script.
- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.
