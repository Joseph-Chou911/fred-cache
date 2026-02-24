# Backtest MVP Summary

- generated_at_utc: `2026-02-24T07:32:21Z`
- script_fingerprint: `backtest_tw0050_leverage_mvp@2026-02-24.v26.6.hardfail_floor_and_break_ratio_guard`
- renderer_fingerprint: `render_backtest_mvp@2026-02-24.v9.post_only_b2_and_mdd40`
- suite_ok: `True`

## Ranking (policy)
- ranking_policy: `prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full; EXCLUDE hard_fail`
- renderer_filter_policy: `renderer_rank_filter_v4: exclude(ok=false); exclude(suite_hard_fail=true); exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post); exclude(post_gonogo=NO_GO); exclude(missing rank metrics on chosen basis); NOTE: eq50 gate disabled (basis_equity_min<=0.5 removed; equity_min semantics not aligned with MDD).`
- full_segment_note: `FULL_* metrics may be impacted by data singularity around 2014 (price series anomaly/adjustment). Treat FULL as audit-only; prefer POST for decision and ranking.`
- top3_recommended: `trend_leverage_price_gt_ma60_1.2x, always_leverage_1.2x, always_leverage_1.3x`
- top3_raw_from_suite: `trend_leverage_price_gt_ma60_1.2x, trend_leverage_price_gt_ma60_1.1x, always_leverage_1.1x`

## Strategies
note_full: `FULL_* columns may be contaminated by a known data singularity issue. Do not use FULL alone for go/no-go; use POST_* as primary.`

| id | ok | suite_hard_fail | entry_mode | L | full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔMDD | post_ΔSharpe | post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades | rv20_skipped |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| trend_leverage_price_gt_ma60_1.5x | True | True | trend | 1.50 | 8.63% | -118.88% | -0.194 | 0.073 | 0.31% | -41.55% | -0.695 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 22.20% | -37.67% | 1.031 | 0.589 | 2.42% | -3.84% | -0.044 | GO_OR_REVIEW | post | 1422 | -0.40 | 0 | 0.95 | 94 | 0 |
| trend_leverage_price_gt_ma60_1.3x | True | True | trend | 1.30 | 8.49% | -103.16% | -0.031 | 0.082 | 0.16% | -25.82% | -0.532 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.30% | -36.23% | 1.051 | 0.588 | 1.52% | -2.40% | -0.024 | GO_OR_REVIEW | post | 124 | -0.06 | 0 | 0.95 | 138 | 0 |
| trend_leverage_price_gt_ma60_1.2x | True | False | trend | 1.20 | 8.44% | -94.86% | 0.603 | 0.089 | 0.12% | -17.53% | 0.102 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.81% | -35.46% | 1.060 | 0.587 | 1.03% | -1.63% | -0.015 | GO_OR_REVIEW | post | 0 | 0.10 | 0 | 0.95 | 139 | 0 |
| trend_leverage_price_gt_ma60_1.1x | True | False | trend | 1.10 | 8.38% | -86.26% | 0.531 | 0.097 | 0.06% | -8.93% | 0.030 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.31% | -34.66% | 1.068 | 0.586 | 0.53% | -0.83% | -0.007 | NO_GO | post | 0 | 0.27 | 0 | 0.95 | 139 | 0 |
| always_leverage_1.1x | True | False | always | 1.10 | 8.55% | -83.64% | 0.519 | 0.102 | 0.23% | -6.31% | 0.018 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.43% | -35.71% | 1.047 | 0.572 | 0.65% | -1.88% | -0.028 | NO_GO | post | 0 | 0.32 | 0 | 0.95 | 69 | 0 |
| always_leverage_1.2x | True | False | always | 1.20 | 8.77% | -89.53% | 0.549 | 0.098 | 0.45% | -12.20% | 0.048 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.04% | -37.44% | 1.023 | 0.562 | 1.26% | -3.61% | -0.052 | GO_OR_REVIEW | post | 0 | 0.21 | 0 | 0.94 | 69 | 0 |
| always_leverage_1.3x | True | False | always | 1.30 | 8.99% | -95.05% | 0.599 | 0.095 | 0.66% | -17.71% | 0.098 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.62% | -39.02% | 1.003 | 0.554 | 1.84% | -5.19% | -0.072 | GO_OR_REVIEW | post | 0 | 0.11 | 0 | 0.94 | 69 | 0 |
| always_leverage_1.5x | True | True | always | 1.50 | 9.47% | -105.07% | -0.197 | 0.090 | 1.14% | -27.74% | -0.698 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 22.70% | -41.82% | 0.971 | 0.543 | 2.92% | -7.99% | -0.104 | GO_OR_REVIEW | post | 422 | -0.11 | 0 | 0.93 | 65 | 0 |
| bb_conditional | True | False | bb | 1.50 | 8.50% | -71.42% | 0.490 | 0.119 | 0.17% | 5.91% | -0.011 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 19.72% | -41.37% | 0.969 | 0.477 | -0.06% | -7.54% | -0.105 | NO_GO | post | 0 | 0.56 | 0 | 0.95 | 22 | 147 |

## Exclusions (not eligible for recommendation)
- total_strategies: `9`
- eligible: `3`
- excluded: `6` (suite_hard_fail=3, hard_fail_fullpost=3, post_NO_GO=3, ok_false=0, missing_rank_metrics=0)

- always_leverage_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- always_leverage_1.5x: `EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0`
- bb_conditional: `EXCLUDE_POST_GONOGO_NO_GO`
- trend_leverage_price_gt_ma60_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- trend_leverage_price_gt_ma60_1.3x: `EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0`
- trend_leverage_price_gt_ma60_1.5x: `EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0`

## Deterministic Always vs Trend (checkmarks)
compare_policy: `compare_v2: for same L, compare post if both post_ok else full; winner=calmar desc, then sharpe0 desc, then id; trend_id uses suite trend_rule`
trend_rule: `price_gt_ma60`

| L | basis | trend_id | always_id | winner | verdict |
|---:|---|---|---|---|---|
| 1.1x | N/A | trend_leverage_price_gt_ma60_1.1x | always_leverage_1.1x | N/A | N/A (trend excluded: EXCLUDE_POST_GONOGO_NO_GO; always excluded: EXCLUDE_POST_GONOGO_NO_GO) |
| 1.2x | post | trend_leverage_price_gt_ma60_1.2x | always_leverage_1.2x | trend_leverage_price_gt_ma60_1.2x | WIN:trend |
| 1.3x | N/A | trend_leverage_price_gt_ma60_1.3x | always_leverage_1.3x | N/A | N/A (trend excluded: EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0; always OK) |
| 1.5x | N/A | trend_leverage_price_gt_ma60_1.5x | always_leverage_1.5x | N/A | N/A (trend excluded: EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0; always excluded: EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0) |

## Post-only View (After Singularity / Ignore FULL)
post_only_policy_v2: `require post_ok=true; exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%); exclude post_gonogo=NO_GO; exclude missing post rank metrics; B2 gate: require post_ΔSharpe>= -0.03; post_MDD floor: require post_MDD>= -0.4 (i.e. not worse than -40%); ignore FULL and ignore suite_hard_fail.`
- top3_post_only: `trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.2x`
- would_be_eligible_post_only_but_excluded_by_full_floor: `trend_leverage_price_gt_ma60_1.3x`
- post_only_total: `9`; post_only_eligible: `2`; post_only_excluded: `7`
- post_only_exclusion_counters: `ok_false=0, post_ok_false=0, post_hard_fail=0, post_NO_GO=3, missing_rank_post=0, delta_sharpe_missing=0, b2_fail=5, post_mdd_floor_fail=2`

- always_leverage_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- always_leverage_1.2x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.03`
- always_leverage_1.3x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.03`
- always_leverage_1.5x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.03, EXCLUDE_POST_MDD_LT_-0.4`
- bb_conditional: `EXCLUDE_POST_GONOGO_NO_GO, EXCLUDE_POST_DELTA_SHARPE_LT_-0.03, EXCLUDE_POST_MDD_LT_-0.4`
- trend_leverage_price_gt_ma60_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- trend_leverage_price_gt_ma60_1.5x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.03`

## Post Go/No-Go Details (compact)
### trend_leverage_price_gt_ma60_1.5x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold
- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.3961632370832667)
  - full: equity_negative_days>0 (neg_days=1422)

### trend_leverage_price_gt_ma60_1.3x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold
- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.06394222997589749)
  - full: equity_negative_days>0 (neg_days=124)

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
- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.11447361653759569)
  - full: equity_negative_days>0 (neg_days=422)

### bb_conditional
- decision: `NO_GO`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=True`
  - all 3 post conditions met => stop / do not deploy
