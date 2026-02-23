# Backtest MVP Summary

- generated_at_utc: `2026-02-23T08:01:17Z`
- script_fingerprint: `backtest_tw0050_leverage_mvp@2026-02-22.v26.4.minimal_patches`
- renderer_fingerprint: `render_backtest_mvp@2026-02-23.v6.disable_eq50_gate_v1`
- suite_ok: `True`

## Ranking (policy)
- ranking_policy: `prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full; EXCLUDE hard_fail`
- renderer_filter_policy: `renderer_rank_filter_v3: exclude(ok=false); exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post); exclude(post_gonogo=NO_GO); exclude(missing rank metrics on chosen basis); NOTE: eq50 gate disabled (basis_equity_min<=0.5 removed; equity_min semantics not aligned with MDD).`
- full_segment_note: `FULL_* metrics may be impacted by data singularity around 2014 (price series anomaly/adjustment). Treat FULL as audit-only; prefer POST for decision and ranking.`
- top3_recommended: `trend_leverage_price_gt_ma60_1.2x, always_leverage_1.2x, always_leverage_1.3x`
- top3_raw_from_suite: `trend_leverage_price_gt_ma60_1.2x, trend_leverage_price_gt_ma60_1.1x, always_leverage_1.1x`

## Strategies
note_full: `FULL_* columns may be contaminated by a known data singularity issue. Do not use FULL alone for go/no-go; use POST_* as primary.`

| id | ok | entry_mode | L | full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔMDD | post_ΔSharpe | post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| trend_leverage_price_gt_ma60_1.5x | True | trend | 1.50 | 8.63% | -118.88% | -0.193 | 0.073 | 0.31% | -41.55% | -0.693 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 22.20% | -37.67% | 1.031 | 0.589 | 2.42% | -3.84% | -0.044 | GO_OR_REVIEW | post | 1422 | -0.40 | 0 | 0.95 | 94 |
| trend_leverage_price_gt_ma60_1.3x | True | trend | 1.30 | 8.49% | -103.16% | -0.031 | 0.082 | 0.16% | -25.82% | -0.532 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.30% | -36.23% | 1.051 | 0.588 | 1.52% | -2.40% | -0.024 | GO_OR_REVIEW | post | 124 | -0.06 | 0 | 0.95 | 138 |
| trend_leverage_price_gt_ma60_1.2x | True | trend | 1.20 | 8.44% | -94.86% | 0.603 | 0.089 | 0.12% | -17.53% | 0.102 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.81% | -35.46% | 1.060 | 0.587 | 1.03% | -1.63% | -0.015 | GO_OR_REVIEW | post | 0 | 0.10 | 0 | 0.95 | 139 |
| trend_leverage_price_gt_ma60_1.1x | True | trend | 1.10 | 8.38% | -86.26% | 0.531 | 0.097 | 0.06% | -8.93% | 0.030 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.31% | -34.66% | 1.068 | 0.586 | 0.53% | -0.83% | -0.007 | NO_GO | post | 0 | 0.27 | 0 | 0.95 | 139 |
| always_leverage_1.1x | True | always | 1.10 | 8.55% | -83.64% | 0.519 | 0.102 | 0.23% | -6.31% | 0.018 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.43% | -35.71% | 1.047 | 0.572 | 0.65% | -1.88% | -0.028 | NO_GO | post | 0 | 0.32 | 0 | 0.95 | 69 |
| always_leverage_1.2x | True | always | 1.20 | 8.77% | -89.53% | 0.549 | 0.098 | 0.45% | -12.20% | 0.048 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.04% | -37.44% | 1.023 | 0.562 | 1.26% | -3.61% | -0.052 | GO_OR_REVIEW | post | 0 | 0.21 | 0 | 0.94 | 69 |
| always_leverage_1.3x | True | always | 1.30 | 8.99% | -95.05% | 0.599 | 0.095 | 0.66% | -17.71% | 0.098 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.62% | -39.02% | 1.003 | 0.554 | 1.84% | -5.19% | -0.072 | GO_OR_REVIEW | post | 0 | 0.11 | 0 | 0.94 | 69 |
| always_leverage_1.5x | True | always | 1.50 | 9.47% | -105.07% | -0.198 | 0.090 | 1.14% | -27.74% | -0.699 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 22.70% | -41.82% | 0.971 | 0.543 | 2.92% | -7.99% | -0.104 | GO_OR_REVIEW | post | 422 | -0.11 | 0 | 0.93 | 65 |
| bb_conditional | True | bb | 1.50 | 8.69% | -75.18% | 0.491 | 0.116 | 0.36% | 2.15% | -0.010 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.22% | -39.93% | 0.933 | 0.506 | 0.44% | -6.10% | -0.141 | NO_GO | post | 0 | 0.48 | 0 | 0.95 | 34 |

## Exclusions (not eligible for recommendation)
- total_strategies: `9`
- eligible: `3`
- excluded: `6` (hard_fail_fullpost=3, post_NO_GO=3, ok_false=0, missing_rank_metrics=0)

- always_leverage_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- always_leverage_1.5x: `HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0`
- bb_conditional: `EXCLUDE_POST_GONOGO_NO_GO`
- trend_leverage_price_gt_ma60_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- trend_leverage_price_gt_ma60_1.3x: `HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0`
- trend_leverage_price_gt_ma60_1.5x: `HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0`

## Deterministic Always vs Trend (checkmarks)
compare_policy: `compare_v1: for same L, compare post if both post_ok else full; winner=calmar desc, then sharpe0 desc, then id`

| L | basis | trend_id | always_id | winner | verdict |
|---:|---|---|---|---|---|
| 1.1x | N/A | trend_leverage_price_gt_ma60_1.1x | always_leverage_1.1x | N/A | N/A (trend excluded: EXCLUDE_POST_GONOGO_NO_GO; always excluded: EXCLUDE_POST_GONOGO_NO_GO) |
| 1.2x | post | trend_leverage_price_gt_ma60_1.2x | always_leverage_1.2x | trend_leverage_price_gt_ma60_1.2x | WIN:trend |
| 1.3x | N/A | trend_leverage_price_gt_ma60_1.3x | always_leverage_1.3x | N/A | N/A (trend excluded: HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0; always OK) |
| 1.5x | N/A | trend_leverage_price_gt_ma60_1.5x | always_leverage_1.5x | N/A | N/A (trend excluded: HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0; always excluded: HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0) |

## Post Go/No-Go Details (compact)
### trend_leverage_price_gt_ma60_1.5x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

### trend_leverage_price_gt_ma60_1.3x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

### trend_leverage_price_gt_ma60_1.2x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

### trend_leverage_price_gt_ma60_1.1x
- decision: `NO_GO`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=True`
  - all 3 post conditions met => stop / do not deploy

### always_leverage_1.1x
- decision: `NO_GO`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=True`
  - all 3 post conditions met => stop / do not deploy

### always_leverage_1.2x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

### always_leverage_1.3x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

### always_leverage_1.5x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

### bb_conditional
- decision: `NO_GO`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=True`
  - all 3 post conditions met => stop / do not deploy
