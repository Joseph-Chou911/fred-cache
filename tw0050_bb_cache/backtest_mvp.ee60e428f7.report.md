# Backtest MVP Summary

- generated_at_utc: `2026-02-24T08:27:44Z`
- script_fingerprint: `backtest_tw0050_leverage_mvp@2026-02-24.v26.6.hardfail_floor_and_break_ratio_guard`
- renderer_fingerprint: `render_backtest_mvp@2026-02-24.v11.suite_hard_fail_date_evidence`
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
| trend_leverage_price_gt_ma60_1.5x | True | True | trend | 1.50 | 8.87% | -118.88% | -0.193 | 0.075 | 0.38% | -41.55% | -0.699 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 22.52% | -37.67% | 1.042 | 0.598 | 2.48% | -3.84% | -0.044 | GO_OR_REVIEW | post | 1422 | -0.40 | 0 | 0.95 | 94 | 0 |
| trend_leverage_price_gt_ma60_1.3x | True | True | trend | 1.30 | 8.70% | -103.16% | -0.030 | 0.084 | 0.21% | -25.82% | -0.537 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.59% | -36.23% | 1.062 | 0.596 | 1.55% | -2.40% | -0.024 | GO_OR_REVIEW | post | 124 | -0.06 | 0 | 0.95 | 138 | 0 |
| trend_leverage_price_gt_ma60_1.2x | True | False | trend | 1.20 | 8.64% | -94.86% | 0.607 | 0.091 | 0.15% | -17.53% | 0.101 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.10% | -35.46% | 1.071 | 0.595 | 1.06% | -1.63% | -0.015 | GO_OR_REVIEW | post | 0 | 0.10 | 0 | 0.95 | 139 | 0 |
| trend_leverage_price_gt_ma60_1.1x | True | False | trend | 1.10 | 8.56% | -86.26% | 0.536 | 0.099 | 0.07% | -8.93% | 0.030 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.58% | -34.66% | 1.079 | 0.594 | 0.54% | -0.83% | -0.007 | NO_GO | post | 0 | 0.27 | 0 | 0.95 | 139 | 0 |
| always_leverage_1.1x | True | False | always | 1.10 | 8.73% | -83.64% | 0.524 | 0.104 | 0.24% | -6.31% | 0.018 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 20.70% | -35.71% | 1.057 | 0.580 | 0.66% | -1.88% | -0.028 | NO_GO | post | 0 | 0.32 | 0 | 0.95 | 69 | 0 |
| always_leverage_1.2x | True | False | always | 1.20 | 8.96% | -89.53% | 0.554 | 0.100 | 0.47% | -12.20% | 0.048 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.32% | -37.44% | 1.033 | 0.570 | 1.28% | -3.61% | -0.052 | GO_OR_REVIEW | post | 0 | 0.21 | 0 | 0.94 | 69 | 0 |
| always_leverage_1.3x | True | False | always | 1.30 | 9.18% | -95.05% | 0.603 | 0.097 | 0.69% | -17.71% | 0.097 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 21.91% | -39.02% | 1.013 | 0.562 | 1.87% | -5.19% | -0.072 | GO_OR_REVIEW | post | 0 | 0.11 | 0 | 0.94 | 69 | 0 |
| always_leverage_1.5x | True | True | always | 1.50 | 9.68% | -105.07% | -0.196 | 0.092 | 1.19% | -27.74% | -0.702 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 23.01% | -41.82% | 0.981 | 0.550 | 2.96% | -7.99% | -0.105 | GO_OR_REVIEW | post | 422 | -0.11 | 0 | 0.93 | 65 | 0 |
| bb_conditional | True | False | bb | 1.50 | 8.66% | -71.42% | 0.495 | 0.121 | 0.17% | 5.91% | -0.011 | True | 2014-01-02 | 2014-01-02 | 2955 | 11.722 | 19.98% | -41.37% | 0.979 | 0.483 | -0.06% | -7.54% | -0.106 | NO_GO | post | 0 | 0.56 | 0 | 0.95 | 22 | 147 |

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
post_only_policy_v3: `require post_ok=true; exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%); exclude post_gonogo=NO_GO; exclude missing post rank metrics; PASS gate: require post_ΔSharpe>= -0.03; WATCH gate: require -0.05<=post_ΔSharpe<-0.03; post_MDD floor: require post_MDD>= -0.4 (i.e. not worse than -40%); ignore FULL and ignore suite_hard_fail.`
- top3_post_only_PASS: `trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.2x`
- top3_post_only_WATCH: `trend_leverage_price_gt_ma60_1.5x`
- post_only_total: `9`; pass: `2`; watch: `1`; excluded: `6`
- would_be_pass_or_watch_post_only_but_excluded_by_renderer_v4: `trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.5x`

### PASS (deploy-grade, strict)
| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |
|---|---:|---:|---:|---:|---:|---|
| trend_leverage_price_gt_ma60_1.3x | 21.59% | -36.23% | 1.062 | 0.596 | -0.024 | excluded_by_renderer_v4: EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0 |
| trend_leverage_price_gt_ma60_1.2x | 21.10% | -35.46% | 1.071 | 0.595 | -0.015 |   |

### WATCH (research-grade, not for deploy)
| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |
|---|---:|---:|---:|---:|---:|---|
| trend_leverage_price_gt_ma60_1.5x | 22.52% | -37.67% | 1.042 | 0.598 | -0.044 | excluded_by_renderer_v4: EXCLUDE_SUITE_HARD_FAIL_TRUE, HARD_FAIL_FULL_MDD_LE_-100PCT, HARD_FAIL_FULL_EQUITY_MIN_LE_0, HARD_FAIL_FULL_NEG_DAYS_GT_0 |

### Post-only Exclusions (reasons)
- always_leverage_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- always_leverage_1.2x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.05`
- always_leverage_1.3x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.05`
- always_leverage_1.5x: `EXCLUDE_POST_MDD_LT_-0.4, EXCLUDE_POST_DELTA_SHARPE_LT_-0.05`
- bb_conditional: `EXCLUDE_POST_GONOGO_NO_GO, EXCLUDE_POST_MDD_LT_-0.4, EXCLUDE_POST_DELTA_SHARPE_LT_-0.05`
- trend_leverage_price_gt_ma60_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`

## Post Go/No-Go Details (compact)
### trend_leverage_price_gt_ma60_1.5x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.39616459186496916)
  - full: equity_negative_days>0 (neg_days=1422)

- suite_hard_fail_evidence (from equity CSV, best-effort):
  - status: `N/A` (equity csv not found)

### trend_leverage_price_gt_ma60_1.3x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.0639430290987017)
  - full: equity_negative_days>0 (neg_days=124)

- suite_hard_fail_evidence (from equity CSV, best-effort):
  - status: `N/A` (equity csv not found)

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
  - full: equity_min<= 0.0 (equity_min=-0.11447548296733157)
  - full: equity_negative_days>0 (neg_days=422)

- suite_hard_fail_evidence (from equity CSV, best-effort):
  - status: `N/A` (equity csv not found)

### bb_conditional
- decision: `NO_GO`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=True`
  - all 3 post conditions met => stop / do not deploy
