# 0050 Valuation × BB Merged Report

## Summary
- current_date: `2026-03-06`
- current_0050_price: `76.70`
- bb_state: **NEAR_UPPER_BAND**; bb_z=`1.2403`
- regime: **RISK_OFF_OR_DEFENSIVE**; allowed=`false`
- action_bucket: **VETO**; pledge_policy=`DISALLOW`
- combined_execution_bias: **DEFENSIVE_NO_CHASE**

## Base Inputs
- base_0050: `76.85`
- base_tsmc: `1890.0`
- tsmc_weight_in_0050: `0.6408`
- dividend_drag_points_per_year: `1.0` (enabled=`True`)

## Valuation Scenario Table

| scenario | years | EPS_growth | FX_haircut | P/E | other_ret | TSMC | 0050_gross | 0050_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026_壓力 | 1 | 20.0% | 6.0% | 18.0 | -15.0% | 1345.14 | 58.51 | 57.51 |
| 2026_保守 | 1 | 20.0% | 3.0% | 20.0 | -8.0% | 1542.30 | 65.58 | 64.58 |
| 2026_中性偏保守 | 1 | 25.0% | 3.0% | 22.0 | -3.0% | 1767.22 | 72.82 | 71.82 |
| 2026_中性 | 1 | 25.0% | 0.0% | 24.0 | 0.0% | 1987.50 | 79.39 | 78.39 |
| 2027_中性 | 2 | 25.0% | 6.0% | 22.0 | 2.0% | 2140.70 | 83.93 | 81.93 |
| 2027_中性偏樂觀 | 2 | 25.0% | 0.0% | 24.0 | 5.0% | 2484.38 | 93.72 | 91.72 |
| 2027_樂觀延續 | 2 | 30.0% | 0.0% | 24.0 | 5.0% | 2687.10 | 99.00 | 97.00 |

## Current Price Position vs Scenario Net Range
- current_0050_price: `76.70`
- scenario_net_range: `57.51` ~ `97.00`
- percentile_in_scenario_net_range: `42.86`
- zone: **MID_ZONE**

## BB Tranche References

| label | price_level | vs_current_pct |
|---|---:|---:|
| 10D_p10_uncond | 73.02 | -4.80% |
| 10D_p05_uncond | 71.87 | -6.30% |
| 20D_p10_uncond | 71.43 | -6.87% |
| 20D_p05_uncond | 69.59 | -9.27% |

## Data Quality
- PRICE_SERIES_BREAK_DETECTED
- FWD_MDD_CLEAN_APPLIED
- FWD_MDD_OUTLIER_MIN_RAW_20D
- RAW_OUTLIER_EXCLUDED_BY_CLEAN

## How to Use
- Step 1: Use the valuation table to decide whether current price is in a low / fair / high zone.
- Step 2: Use BB state, regime, and tranche references to decide whether to act now or wait.
- Step 3: Keep rules fixed. Update fast variables daily after close; update slow assumptions only when fundamentals or policy materially change.

## Notes
- Outputs are dynamic, not fixed. The rules can stay fixed, but the zone boundaries will move when market data or scenario assumptions change.
- Slow-moving inputs: EPS growth assumptions, FX haircut assumptions, P/E bands, dividend drag.
- Fast-moving inputs: current 0050 price, BB state, regime, tranche levels, and TSMC weight if refreshed.
