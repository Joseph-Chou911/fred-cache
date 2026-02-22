# Backtest MVP Summary

- generated_at_utc: `2026-02-22T12:59:46Z`
- script_fingerprint: `backtest_tw0050_leverage_mvp@2026-02-22.v26.4.minimal_patches`
- renderer_fingerprint: `render_backtest_mvp@2026-02-22.v1.post_cols`
- suite_ok: `True`

## Ranking (policy)
- ranking_policy: `prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full; EXCLUDE hard_fail`
- top3_by_policy: `trend_leverage_price_gt_ma60_1.2x, trend_leverage_price_gt_ma60_1.1x, always_leverage_1.1x`

## Strategies
| id | ok | entry_mode | L | full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | post_ok | split | post_start | post_n | post_years | post_CAGR | post_MDD | post_Sharpe | post_Calmar | post_ΔCAGR | post_ΔSharpe | post_go/no-go | rank_basis | neg_days | equity_min | post_neg_days | post_equity_min | trades |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| trend_leverage_price_gt_ma60_1.5x | True | trend | 1.50 | 8.61% | -118.88% | -0.194 | 0.072 | 0.30% | -41.55% | -0.694 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 22.18% | -37.67% | 1.030 | 0.589 | 2.42% | -0.044 | GO_OR_REVIEW | post | 1422 | -0.40 | 0 | 0.95 | 94 |
| trend_leverage_price_gt_ma60_1.3x | True | trend | 1.30 | 8.47% | -103.16% | -0.031 | 0.082 | 0.16% | -25.82% | -0.531 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 21.28% | -36.23% | 1.050 | 0.587 | 1.51% | -0.024 | GO_OR_REVIEW | post | 124 | -0.06 | 0 | 0.95 | 138 |
| trend_leverage_price_gt_ma60_1.2x | True | trend | 1.20 | 8.42% | -94.86% | 0.602 | 0.089 | 0.11% | -17.53% | 0.102 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 20.79% | -35.46% | 1.059 | 0.586 | 1.03% | -0.015 | GO_OR_REVIEW | post | 0 | 0.10 | 0 | 0.95 | 139 |
| trend_leverage_price_gt_ma60_1.1x | True | trend | 1.10 | 8.37% | -86.26% | 0.531 | 0.097 | 0.06% | -8.93% | 0.030 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 20.29% | -34.66% | 1.067 | 0.585 | 0.53% | -0.007 | NO_GO | post | 0 | 0.27 | 0 | 0.95 | 139 |
| always_leverage_1.1x | True | always | 1.10 | 8.54% | -83.64% | 0.519 | 0.102 | 0.23% | -6.31% | 0.018 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 20.41% | -35.71% | 1.046 | 0.571 | 0.65% | -0.028 | NO_GO | post | 0 | 0.32 | 0 | 0.95 | 69 |
| always_leverage_1.2x | True | always | 1.20 | 8.76% | -89.53% | 0.549 | 0.098 | 0.45% | -12.20% | 0.048 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 21.02% | -37.44% | 1.022 | 0.562 | 1.26% | -0.051 | GO_OR_REVIEW | post | 0 | 0.21 | 0 | 0.94 | 69 |
| always_leverage_1.3x | True | always | 1.30 | 8.97% | -95.05% | 0.599 | 0.094 | 0.66% | -17.71% | 0.098 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 21.60% | -39.02% | 1.002 | 0.554 | 1.84% | -0.071 | GO_OR_REVIEW | post | 0 | 0.11 | 0 | 0.94 | 69 |
| always_leverage_1.5x | True | always | 1.50 | 9.45% | -105.07% | -0.197 | 0.090 | 1.14% | -27.74% | -0.697 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 22.68% | -41.82% | 0.970 | 0.542 | 2.92% | -0.103 | GO_OR_REVIEW | post | 422 | -0.11 | 0 | 0.93 | 65 |
| bb_conditional | True | bb | 1.50 | 8.67% | -75.18% | 0.490 | 0.115 | 0.36% | 2.15% | -0.010 | True | 2014-01-02 | 2014-01-02 | 2954 | 11.718 | 20.20% | -39.93% | 0.933 | 0.506 | 0.44% | -0.141 | NO_GO | post | 0 | 0.48 | 0 | 0.95 | 34 |

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
