# Backtest MVP Summary

- generated_at_utc: `2026-03-10T07:53:21Z`
- script_fingerprint: `backtest_tw0050_leverage_mvp@2026-02-24.v26.9.cleanup_equity_curve_csvs`
- renderer_fingerprint: `render_backtest_mvp@2026-02-24.v13.dq_post_neg_days_vs_equity_csv`
- suite_ok: `True`

## Ranking (policy)
- ranking_policy: `prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full; EXCLUDE hard_fail`
- renderer_filter_policy: `renderer_rank_filter_v4: exclude(ok=false); exclude(suite_hard_fail=true); exclude(hard_fail: equity_min<=0 or equity_negative_days>0 or mdd<=-100% on full/post); exclude(post_gonogo=NO_GO); exclude(missing rank metrics on chosen basis); NOTE: eq50 gate disabled (basis_equity_min<=0.5 removed; equity_min semantics not aligned with MDD).`
- full_segment_note: `FULL_* metrics may be impacted by data singularity around 2014 (price series anomaly/adjustment). Treat FULL as audit-only; prefer POST for decision and ranking.`
- top3_recommended: `trend_leverage_price_gt_ma60_1.2x, always_leverage_1.2x, always_leverage_1.3x`
- top3_raw_from_suite: `trend_leverage_price_gt_ma60_1.2x, trend_leverage_price_gt_ma60_1.1x, always_leverage_1.1x`

## Strategies
note_full: `FULL_* columns may be contaminated by a known data singularity issue. Do not use FULL alone for go/no-go; use POST_* as primary.`

| id | ok | suite_hard_fail | entry_mode | L | full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔMDD | post_ΔSharpe | post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades | rv20_skipped | post_neg_days_csv | dq_post_neg_days |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| trend_leverage_price_gt_ma60_1.5x | True | True | trend | 1.50 | 8.33% | -118.88% | -0.196 | 0.070 | 0.22% | -41.55% | -0.689 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 21.90% | -37.65% | 1.015 | 0.582 | 2.35% | -3.82% | -0.044 | GO_OR_REVIEW | post | 1422 | -0.40 | 0 | 0.96 | 94 | 0 | 1421 | DQ_MISMATCH |
| trend_leverage_price_gt_ma60_1.3x | True | True | trend | 1.30 | 8.23% | -103.16% | -0.031 | 0.080 | 0.11% | -25.82% | -0.525 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 21.01% | -36.21% | 1.034 | 0.580 | 1.47% | -2.38% | -0.024 | GO_OR_REVIEW | post | 124 | -0.06 | 0 | 0.96 | 138 | 0 | 123 | DQ_MISMATCH |
| trend_leverage_price_gt_ma60_1.2x | True | False | trend | 1.20 | 8.20% | -94.86% | 0.596 | 0.086 | 0.08% | -17.53% | 0.102 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 20.55% | -35.45% | 1.044 | 0.580 | 1.00% | -1.62% | -0.015 | GO_OR_REVIEW | post | 0 | 0.10 | 0 | 0.96 | 139 | 0 | 0 | OK |
| trend_leverage_price_gt_ma60_1.1x | True | False | trend | 1.10 | 8.16% | -86.26% | 0.524 | 0.095 | 0.04% | -8.93% | 0.030 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 20.06% | -34.66% | 1.052 | 0.579 | 0.51% | -0.83% | -0.007 | NO_GO | post | 0 | 0.27 | 0 | 0.96 | 139 | 0 | 0 | OK |
| always_leverage_1.1x | True | False | always | 1.10 | 8.33% | -83.64% | 0.512 | 0.100 | 0.21% | -6.31% | 0.018 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 20.22% | -35.52% | 1.036 | 0.569 | 0.67% | -1.69% | -0.022 | NO_GO | post | 0 | 0.32 | 0 | 0.96 | 69 | 0 | 0 | OK |
| always_leverage_1.2x | True | False | always | 1.20 | 8.54% | -89.53% | 0.543 | 0.095 | 0.42% | -12.20% | 0.049 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 20.85% | -37.05% | 1.018 | 0.563 | 1.31% | -3.23% | -0.041 | GO_OR_REVIEW | post | 0 | 0.21 | 0 | 0.96 | 69 | 0 | 0 | OK |
| always_leverage_1.3x | True | False | always | 1.30 | 8.74% | -95.05% | 0.593 | 0.092 | 0.63% | -17.71% | 0.100 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 21.45% | -38.45% | 1.002 | 0.558 | 1.91% | -4.62% | -0.057 | GO_OR_REVIEW | post | 0 | 0.11 | 0 | 0.95 | 69 | 0 | 0 | OK |
| always_leverage_1.5x | True | True | always | 1.50 | 9.20% | -105.07% | -0.196 | 0.088 | 1.08% | -27.74% | -0.690 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 22.56% | -40.90% | 0.977 | 0.552 | 3.02% | -7.07% | -0.082 | GO_OR_REVIEW | post | 422 | -0.11 | 0 | 0.94 | 65 | 0 | 421 | DQ_MISMATCH |
| bb_conditional | True | False | bb | 1.50 | 8.29% | -71.42% | 0.483 | 0.116 | 0.18% | 5.91% | -0.011 | True | 2014-01-02 | 2014-01-03 | 2964 | 11.758 | 19.48% | -41.37% | 0.956 | 0.471 | -0.07% | -7.54% | -0.102 | NO_GO | post | 0 | 0.56 | 0 | 0.96 | 22 | 147 | 0 | OK |

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
post_only_policy_v3_semantic1: `require post_ok=true; exclude post hard fails (post equity_min<=0 or post neg_days>0 or post mdd<=-100%); exclude post_gonogo=NO_GO; exclude missing post rank metrics; PASS gate: require post_ΔSharpe>= -0.03; WATCH gate: require -0.05<=post_ΔSharpe<-0.03; post_MDD floor: require post_MDD>= -0.4 (i.e. not worse than -40%); ignore FULL and ignore suite_hard_fail for eligibility (Semantic1=new start).`
- dq_check_v13: `Compare JSON post_neg_days (post-segment normalized) vs equity CSV neg_days_count on date>=post_start_date (full-equity sliced). DQ_MISMATCH usually indicates semantic mismatch, not necessarily a bug.`
- top3_post_only_PASS: `trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.2x`
- top3_post_only_WATCH: `trend_leverage_price_gt_ma60_1.5x, always_leverage_1.2x`
- post_only_total: `9`; pass: `2`; watch: `2`; excluded: `5`
- post_only_warn_full_blowup (suite_hard_fail=true): `trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.5x`
- post_only_dq_mismatch_post_neg_days: `trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.5x`

### PASS (deploy-grade, strict; Semantic1=new start)
| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |
|---|---:|---:|---:|---:|---:|---|
| trend_leverage_price_gt_ma60_1.3x | 21.01% | -36.21% | 1.034 | 0.580 | -0.024 | WARNING: suite_hard_fail=true (FULL period floor violated; Semantic2 risk); DQ_MISMATCH(post_neg_days): json_post_neg_days=0;csv_post_neg_days_count=123 |
| trend_leverage_price_gt_ma60_1.2x | 20.55% | -35.45% | 1.044 | 0.580 | -0.015 |   |

### WATCH (research-grade, not for deploy; Semantic1=new start)
| id | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔSharpe | note |
|---|---:|---:|---:|---:|---:|---|
| trend_leverage_price_gt_ma60_1.5x | 21.90% | -37.65% | 1.015 | 0.582 | -0.044 | WARNING: suite_hard_fail=true (FULL period floor violated; Semantic2 risk); DQ_MISMATCH(post_neg_days): json_post_neg_days=0;csv_post_neg_days_count=1421 |
| always_leverage_1.2x | 20.85% | -37.05% | 1.018 | 0.563 | -0.041 |   |

### Post-only Exclusions (reasons)
- always_leverage_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`
- always_leverage_1.3x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.05`
- always_leverage_1.5x: `EXCLUDE_POST_DELTA_SHARPE_LT_-0.05, EXCLUDE_POST_MDD_LT_-0.4`
- bb_conditional: `EXCLUDE_POST_GONOGO_NO_GO, EXCLUDE_POST_DELTA_SHARPE_LT_-0.05, EXCLUDE_POST_MDD_LT_-0.4`
- trend_leverage_price_gt_ma60_1.1x: `EXCLUDE_POST_GONOGO_NO_GO`

## Post Go/No-Go Details (compact)
### trend_leverage_price_gt_ma60_1.5x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.3961620366146094)
  - full: equity_negative_days>0 (neg_days=1422)

- suite_hard_fail_evidence (from equity CSV, best-effort):
  - equity_csv: `/home/runner/work/fred-cache/fred-cache/tw0050_bb_cache/equity_curve.0d3098298f__trend_leverage_price_gt_ma60_1.5x.csv`
  - dq_post_neg_days (json vs csv, date>=post_start): `DQ_MISMATCH`; detail: `json_post_neg_days=0;csv_post_neg_days_count=1421`
  - FULL:
    - equity_min_date: `2014-02-05`
    - neg_days_first_date: `2014-01-02`
    - neg_days_last_date: `2020-04-24`
    - neg_days_count: `1422`
  - POST (date >= post_start_date) [NOTE: this is FULL equity sliced by date, not post-segment normalized]:
    - post_start_date: `2014-01-03`
    - equity_min_date: `2014-02-05`
    - neg_days_first_date: `2014-01-03`
    - neg_days_last_date: `2020-04-24`
    - neg_days_count: `1421`

### trend_leverage_price_gt_ma60_1.3x
- decision: `GO_OR_REVIEW`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=False`
  - delta_cagr not below threshold

- suite_hard_fail: `true`
  - full: equity_min<= 0.0 (equity_min=-0.06394146111913407)
  - full: equity_negative_days>0 (neg_days=124)

- suite_hard_fail_evidence (from equity CSV, best-effort):
  - equity_csv: `/home/runner/work/fred-cache/fred-cache/tw0050_bb_cache/equity_curve.0d3098298f__trend_leverage_price_gt_ma60_1.3x.csv`
  - dq_post_neg_days (json vs csv, date>=post_start): `DQ_MISMATCH`; detail: `json_post_neg_days=0;csv_post_neg_days_count=123`
  - FULL:
    - equity_min_date: `2014-02-05`
    - neg_days_first_date: `2014-01-02`
    - neg_days_last_date: `2016-01-28`
    - neg_days_count: `124`
  - POST (date >= post_start_date) [NOTE: this is FULL equity sliced by date, not post-segment normalized]:
    - post_start_date: `2014-01-03`
    - equity_min_date: `2014-02-05`
    - neg_days_first_date: `2014-01-03`
    - neg_days_last_date: `2016-01-28`
    - neg_days_count: `123`

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
  - full: equity_min<= 0.0 (equity_min=-0.11447429340908322)
  - full: equity_negative_days>0 (neg_days=422)

- suite_hard_fail_evidence (from equity CSV, best-effort):
  - equity_csv: `/home/runner/work/fred-cache/fred-cache/tw0050_bb_cache/equity_curve.0d3098298f__always_leverage_1.5x.csv`
  - dq_post_neg_days (json vs csv, date>=post_start): `DQ_MISMATCH`; detail: `json_post_neg_days=0;csv_post_neg_days_count=421`
  - FULL:
    - equity_min_date: `2014-02-05`
    - neg_days_first_date: `2014-01-02`
    - neg_days_last_date: `2016-07-14`
    - neg_days_count: `422`
  - POST (date >= post_start_date) [NOTE: this is FULL equity sliced by date, not post-segment normalized]:
    - post_start_date: `2014-01-03`
    - equity_min_date: `2014-02-05`
    - neg_days_first_date: `2014-01-03`
    - neg_days_last_date: `2016-07-14`
    - neg_days_count: `421`

### bb_conditional
- decision: `NO_GO`
- rule_id: `post_gonogo_v3`
- conditions: `delta_sharpe0_lt_0.0=True, delta_abs_mdd_gt_0.0=True, delta_cagr_lt_0.01=True`
  - all 3 post conditions met => stop / do not deploy
