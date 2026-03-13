# 0050 Valuation × BB Merged Report

## Summary
- current_date: `2026-03-13`
- current_0050_price: `75.95`
- bb_state: **IN_BAND**; bb_z=`0.9511`
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
- base_0050: `75.94999694824219` (source=`bb_stats.latest.price_used`)
- base_tsmc: `1860.0` (source=`cli`)
- tsmc_weight_in_0050: `0.6408` (source=`config`)
- dividend_drag_mode: `light`
- dividend_drag_points_per_year: `1.0` (enabled=`True`)

## Slow Variable Review
- active_eps_base: `66.25` (source=`config`)
- eps_base_policy: `manual_review_only`
- eps_base_note: `Active EPS base is a slow-moving valuation anchor. Revise only when earnings basis / model basis changes materially.`
- suggested_eps_base: `N/A`
- suggested_eps_source: `NA`
- suggested_eps_as_of_date: `NA`
- suggested_eps_method: `NA`
- suggested_eps_note: `display-only; never auto-applied`
- family_targets: `72.0, 71.0, 69.0`
- targets_note: `Display-only target price markers.`
- tsmc_weight_meta_as_of_date: `NA`
- tsmc_weight_meta_update_policy: `low_frequency_review`
- tsmc_weight_meta_note: `TSMC weight is a structural observation; daily auto-refresh is unnecessary.`

## Valuation Scenario Table

| scenario | years | EPS_base | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026_壓力 | 1 | 66.25 | 20.0% | 6.0% | 18.0 | -15.0% | 1345.14 | 58.39 | 57.39 |
| 2026_保守 | 1 | 66.25 | 20.0% | 3.0% | 20.0 | -8.0% | 1542.30 | 65.45 | 64.45 |
| 2026_中性偏保守 | 1 | 66.25 | 25.0% | 3.0% | 22.0 | -3.0% | 1767.22 | 72.70 | 71.70 |
| 2026_中性 | 1 | 66.25 | 25.0% | 0.0% | 24.0 | 0.0% | 1987.50 | 79.29 | 78.29 |
| 2027_中性 | 2 | 66.25 | 25.0% | 6.0% | 22.0 | 2.0% | 2140.70 | 83.84 | 81.84 |
| 2027_中性偏樂觀 | 2 | 66.25 | 25.0% | 0.0% | 24.0 | 5.0% | 2484.38 | 93.65 | 91.65 |
| 2027_樂觀延續 | 2 | 66.25 | 30.0% | 0.0% | 24.0 | 5.0% | 2687.10 | 98.96 | 96.96 |

## Current Price Position vs Scenario Net Range
- current_0050_price: `75.95`
- scenario_net_range: `57.39` ~ `96.96`
- percentile_in_scenario_net_range: `42.86`
- position_status: **IN_RANGE**
- gap_vs_min: `18.56`
- gap_vs_max: `-21.01`
- pct_vs_min: `32.35%`
- pct_vs_max: `-21.67%`
- zone: **MID_ZONE**
- zone_note: `rough classification only; sparse scenario set and mixed 1Y/2Y horizons => low decision value`

## Family Interpolation Summary

| family | years | axis | count | min | max | p10 | p25 | p50 | p75 | p90 | current_pctile | current_zone | current_status |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026_conservative_family | 1 | PE 18.0~24.0 step 0.5 | 13 | 60.42 | 72.53 | 61.63 | 63.45 | 66.47 | 69.50 | 71.32 | 100.00 | RICH | ABOVE_MAX |
| 2026_neutralish_family | 1 | PE 20.0~24.0 step 0.5 | 9 | 67.50 | 75.91 | 68.34 | 69.60 | 71.70 | 73.81 | 75.07 | 100.00 | RICH | ABOVE_MAX |
| 2027_neutral_family | 2 | PE 20.0~24.0 step 0.5 | 9 | 76.75 | 86.93 | 77.77 | 79.29 | 81.84 | 84.39 | 85.91 | 0.00 | CHEAP | BELOW_MIN |
| 2027_defensive_family | 2 | PE 18.0~22.0 step 0.5 | 9 | 67.52 | 76.90 | 68.46 | 69.86 | 72.21 | 74.56 | 75.96 | 88.89 | RICH | IN_RANGE |

## Family Target Price Positions
| family | current_pctile | current_zone | current_status | family_min | family_max | 72.00_pctile | 72.00_status | 71.00_pctile | 71.00_status | 69.00_pctile | 69.00_status |
| --- | ---: | --- | --- | ---: | ---: | ---: | --- | ---: | --- | ---: | --- |
| 2026_conservative_family | 100.00 | RICH | ABOVE_MAX | 60.42 | 72.53 | 92.31 | IN_RANGE | 84.62 | IN_RANGE | 69.23 | IN_RANGE |
| 2026_neutralish_family | 100.00 | RICH | ABOVE_MAX | 67.50 | 75.91 | 55.56 | IN_RANGE | 44.44 | IN_RANGE | 22.22 | IN_RANGE |
| 2027_neutral_family | 0.00 | CHEAP | BELOW_MIN | 76.75 | 86.93 | 0.00 | BELOW_MIN | 0.00 | BELOW_MIN | 0.00 | BELOW_MIN |
| 2027_defensive_family | 88.89 | RICH | IN_RANGE | 67.52 | 76.90 | 44.44 | IN_RANGE | 33.33 | IN_RANGE | 22.22 | IN_RANGE |

### Family Interpolation Notes
- enabled: `True`
- targets: `72.0, 71.0, 69.0`
- note: `Display-only. Single-axis dense interpolation within fixed assumption families. This section improves valuation readability but does not alter execution bias.`
- boundary_note: `0 or 100 can simply mean target price is below family min or above family max.`
- robustness_note: `2027_defensive_family is a display-only robustness check; it does not alter execution bias.`

## BB Tranche References

| label | price_level | vs_current_pct |
|---|---:|---:|
| 10D_p10_uncond | 72.29 | -4.81% |
| 10D_p05_uncond | 71.12 | -6.36% |
| 20D_p10_uncond | 70.74 | -6.86% |
| 20D_p05_uncond | 68.91 | -9.26% |

## Pre-Execution Review
- available: `True`
- roll25_report_path: `roll25_cache/report.md`
- band1: `33057.836667`
- band2: `32541.990382`
- tx_night_last: `33253.0`
- tx_vs_band1: `195.16333299999678`
- tx_vs_band2: `711.009618`
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
- Step 4: Treat suggested_eps_base as review material only; it never changes the live model automatically.
- Step 5: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.
- Step 6: Use pre-execution review to override the action bias when TX night close breaches roll25 bands.
- Step 7: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.

## Notes
- base_0050 is auto-resolved from bb-stats unless overridden.
- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.
- active_eps_base is the live slow-moving valuation anchor; revise only when earnings/model basis changes.
- suggested_eps_base is display-only and never auto-applied.
- tsmc_weight_meta is informative only; it does not change execution bias by itself.
- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.
- Mixed-horizon scenario percentile combines 1Y and 2Y cases; treat it as display-only, not primary execution input.
- Family interpolation is display-only and does not alter base_execution_bias / combined_execution_bias / final_execution_bias.
- 2027_defensive_family is a robustness check only; it does not introduce a new trading rule by itself.
- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.
- Pre-execution review reads Band 1 / Band 2 from roll25 markdown report; if parsing fails, no shock override is applied.
- TX night close is manual input and should be checked carefully before running the script.
- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.
