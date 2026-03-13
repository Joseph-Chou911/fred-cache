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
- fast_shock_override: **OBSERVE_ONLY**
- final_execution_bias: **OBSERVE_ONLY**
- action_instruction: `只觀察，不執行。`
- matched_caution_flags: `FWD_MDD_CLEAN_APPLIED, FWD_MDD_OUTLIER_MIN_RAW_20D, PRICE_SERIES_BREAK_DETECTED, RAW_OUTLIER_EXCLUDED_BY_CLEAN`
- shock_trigger_reasons: `tx_night_last_below_band1`
- family_interpolation: **ENABLED** (display-only; no impact on final_execution_bias)

## Base Inputs
- base_0050: `75.94999694824219` (source=`bb_stats.latest.price_used`)
- base_tsmc: `1865.0` (source=`cli`)
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

## Quarterly EPS Accumulation Review
- quarterly_eps_tracker_path: `tw0050_bb_cache/quarterly_eps_tracker.json`
- quarterly_eps_tracker_path_source: `config`
- quarterly_eps_candidate_policy: `sum_complete_fiscal_year_only`
- quarterly_eps_replace_policy: `display_only_no_auto_replace`
- eps_quarters_collected: `none`
- annual_eps_candidate: `N/A`
- annual_eps_candidate_complete: `false`
- annual_eps_candidate_fiscal_year: `None`
- annual_eps_candidate_as_of_date: `NA`
- ready_to_replace_active_eps_base: `false`
- quarterly_eps_ready_diff_tolerance: `0.01`
- quarterly_eps_tracker_note: `Quarterly EPS collection is used to derive a candidate annual EPS. Candidate is display-only and does not auto-replace active_eps_base.`
- quarterly_eps_load_notes: `Quarterly EPS tracker not found: tw0050_bb_cache/quarterly_eps_tracker.json`

## Valuation Scenario Table

| scenario | years | EPS_base | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026_壓力 | 1 | 66.25 | 20.0% | 6.0% | 18.0 | -15.0% | 1345.14 | 58.29 | 57.29 |
| 2026_保守 | 1 | 66.25 | 20.0% | 3.0% | 20.0 | -8.0% | 1542.30 | 65.35 | 64.35 |
| 2026_中性偏保守 | 1 | 66.25 | 25.0% | 3.0% | 22.0 | -3.0% | 1767.22 | 72.58 | 71.58 |
| 2026_中性 | 1 | 66.25 | 25.0% | 0.0% | 24.0 | 0.0% | 1987.50 | 79.15 | 78.15 |
| 2027_中性 | 2 | 66.25 | 25.0% | 6.0% | 22.0 | 2.0% | 2140.70 | 83.69 | 81.69 |
| 2027_中性偏樂觀 | 2 | 66.25 | 25.0% | 0.0% | 24.0 | 5.0% | 2484.38 | 93.48 | 91.48 |
| 2027_樂觀延續 | 2 | 66.25 | 30.0% | 0.0% | 24.0 | 5.0% | 2687.10 | 98.77 | 96.77 |

## Current Price Position vs Scenario Net Range
- current_0050_price: `75.95`
- scenario_net_range: `57.29` ~ `96.77`
- percentile_in_scenario_net_range: `42.86`
- position_status: **IN_RANGE**
- gap_vs_min: `18.66`
- gap_vs_max: `-20.82`
- pct_vs_min: `32.57%`
- pct_vs_max: `-21.51%`
- zone: **MID_ZONE**
- zone_note: `rough classification only; sparse scenario set and mixed 1Y/2Y horizons => low decision value`

## Family Interpolation Summary

| family | years | axis | count | min | max | p10 | p25 | p50 | p75 | p90 | current_pctile | current_zone | current_status |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026_conservative_family | 1 | PE 18.0~24.0 step 0.5 | 13 | 60.32 | 72.40 | 61.53 | 63.34 | 66.36 | 69.38 | 71.19 | 100.00 | RICH | ABOVE_MAX |
| 2026_neutralish_family | 1 | PE 20.0~24.0 step 0.5 | 9 | 67.39 | 75.77 | 68.23 | 69.48 | 71.58 | 73.68 | 74.93 | 100.00 | RICH | ABOVE_MAX |
| 2027_neutral_family | 2 | PE 20.0~24.0 step 0.5 | 9 | 76.61 | 86.77 | 77.63 | 79.15 | 81.69 | 84.23 | 85.75 | 0.00 | CHEAP | BELOW_MIN |
| 2027_defensive_family | 2 | PE 18.0~22.0 step 0.5 | 9 | 67.40 | 76.77 | 68.34 | 69.74 | 72.08 | 74.42 | 75.83 | 88.89 | RICH | IN_RANGE |

## Family Target Price Positions
| family | current_pctile | current_zone | current_status | family_min | family_max | 72.00_pctile | 72.00_status | 71.00_pctile | 71.00_status | 69.00_pctile | 69.00_status |
| --- | ---: | --- | --- | ---: | ---: | ---: | --- | ---: | --- | ---: | --- |
| 2026_conservative_family | 100.00 | RICH | ABOVE_MAX | 60.32 | 72.40 | 92.31 | IN_RANGE | 84.62 | IN_RANGE | 69.23 | IN_RANGE |
| 2026_neutralish_family | 100.00 | RICH | ABOVE_MAX | 67.39 | 75.77 | 55.56 | IN_RANGE | 44.44 | IN_RANGE | 22.22 | IN_RANGE |
| 2027_neutral_family | 0.00 | CHEAP | BELOW_MIN | 76.61 | 86.77 | 0.00 | BELOW_MIN | 0.00 | BELOW_MIN | 0.00 | BELOW_MIN |
| 2027_defensive_family | 88.89 | RICH | IN_RANGE | 67.40 | 76.77 | 44.44 | IN_RANGE | 44.44 | IN_RANGE | 22.22 | IN_RANGE |

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
- tx_night_last: `33001.0`
- tx_vs_band1: `-56.83666700000322`
- tx_vs_band2: `459.00961800000005`
- preopen_shock_flag: **CAUTION**
- shock_override: **OBSERVE_ONLY**
- trigger_reasons: `tx_night_last_below_band1`

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
- Step 5: Review quarterly EPS accumulation fields. `annual_eps_candidate_complete=true` means a complete fiscal year candidate exists.
- Step 6: `ready_to_replace_active_eps_base=true` means the complete annual candidate materially differs from active_eps_base, but replacement is still manual.
- Step 7: Use BB state, regime, tranche references, and DQ overlay to decide whether to act now or wait.
- Step 8: Use pre-execution review to override the action bias when TX night close breaches roll25 bands.
- Step 9: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.

## Notes
- base_0050 is auto-resolved from bb-stats unless overridden.
- base_tsmc is slow-fast hybrid: usually update when market anchor changes meaningfully, or pass via CLI.
- active_eps_base is the live slow-moving valuation anchor; revise only when earnings/model basis changes.
- suggested_eps_base is display-only and never auto-applied.
- annual_eps_candidate is derived from collected quarterly EPS using COMPLETE fiscal year quarters only.
- ready_to_replace_active_eps_base does NOT auto-replace active_eps_base; it is a review flag only.
- tsmc_weight_meta is informative only; it does not change execution bias by itself.
- valuation zone is a rough classification only; do not over-interpret sparse scenario percentiles.
- Mixed-horizon scenario percentile combines 1Y and 2Y cases; treat it as display-only, not primary execution input.
- Family interpolation is display-only and does not alter base_execution_bias / combined_execution_bias / final_execution_bias.
- 2027_defensive_family is a robustness check only; it does not introduce a new trading rule by itself.
- DQ flags can downgrade execution bias even if valuation/regime otherwise look constructive.
- Pre-execution review reads Band 1 / Band 2 from roll25 markdown report; if parsing fails, no shock override is applied.
- TX night close is manual input and should be checked carefully before running the script.
- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.
