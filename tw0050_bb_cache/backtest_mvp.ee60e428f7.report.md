# Backtest MVP Summary

- generated_at_utc: `2026-02-22T11:13:47Z`
- script_fingerprint: `backtest_tw0050_leverage_mvp@2026-02-22.v25.postok_is_true.postcsv_guard.abort_sync`
- suite_ok: `True`

## Ranking (policy)
- ranking_policy: `prefer post (calmar desc, sharpe0 desc) when post_ok=true; else fallback to full`
- top3_by_policy: `trend_leverage_price_gt_ma60_1.5x, trend_leverage_price_gt_ma60_1.3x, trend_leverage_price_gt_ma60_1.2x`

## Strategies
| id | ok | entry_mode | L | full_CAGR | full_MDD | full_Sharpe | full_Calmar | ΔCAGR | ΔMDD | ΔSharpe | post_go/no-go | neg_days | equity_min | trades |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| bb_conditional | True | bb | 1.50 | 8.67% | -75.18% | 0.490 | 0.115 | 0.36% | 2.15% | -0.010 | NO_GO | 0 | 0.48 | 34 |
| always_leverage_1.1x | True | always | 1.10 | 8.54% | -83.64% | 0.519 | 0.102 | 0.23% | -6.31% | 0.018 | NO_GO | 0 | 0.32 | 69 |
| always_leverage_1.2x | True | always | 1.20 | 8.76% | -89.53% | 0.549 | 0.098 | 0.45% | -12.20% | 0.048 | GO_OR_REVIEW | 0 | 0.21 | 69 |
| always_leverage_1.3x | True | always | 1.30 | 8.97% | -95.05% | 0.599 | 0.094 | 0.66% | -17.71% | 0.098 | GO_OR_REVIEW | 0 | 0.11 | 69 |
| always_leverage_1.5x | True | always | 1.50 | 9.45% | -105.07% | -0.197 | 0.090 | 1.14% | -27.74% | -0.697 | GO_OR_REVIEW | 422 | -0.11 | 65 |
| trend_leverage_price_gt_ma60_1.1x | True | trend | 1.10 | 8.37% | -86.26% | 0.531 | 0.097 | 0.06% | -8.93% | 0.030 | NO_GO | 0 | 0.27 | 139 |
| trend_leverage_price_gt_ma60_1.2x | True | trend | 1.20 | 8.42% | -94.86% | 0.602 | 0.089 | 0.11% | -17.53% | 0.102 | GO_OR_REVIEW | 0 | 0.10 | 139 |
| trend_leverage_price_gt_ma60_1.3x | True | trend | 1.30 | 8.47% | -103.16% | -0.031 | 0.082 | 0.16% | -25.82% | -0.531 | GO_OR_REVIEW | 124 | -0.06 | 138 |
| trend_leverage_price_gt_ma60_1.5x | True | trend | 1.50 | 8.61% | -118.88% | -0.194 | 0.072 | 0.30% | -41.55% | -0.694 | GO_OR_REVIEW | 1422 | -0.40 | 94 |
