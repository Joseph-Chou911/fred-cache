# 0050 Tactical Cash Overlay Backtest

- generated_at_utc: `2026-02-24T14:23:32Z`
- script_fingerprint: `backtest_tw0050_tactical_cash@2026-02-24.v2.1.post_only_segmentation_signal_lag1`
- price_csv: `tw0050_bb_cache/data.csv`

## Strategy
- MA window: `60`
- core_frac: `0.9` (tactical_cash = 1-core)
- costs: fee_rate=0.001425, tax_rate=0.001, slip_bps=5.0

## Snapshot (audit)
- rows: `2954`
- date_range: `2014-01-03` ~ `2026-02-24`
- time_in_market_pct (tactical leg): `0.6963`

## Performance (overlay vs base-only)

| metric | overlay | base_only | delta_vs_base |
|---|---:|---:|---:|
| CAGR | 19.54% | 19.23% | 0.31% |
| MDD | -32.73% | -32.81% | 0.08% |
| Sharpe0 | 1.091 | 1.090 | 0.001 |

## Trade KPIs (tactical leg)
- n_trades: `77`
- win_rate: `0.3506`
- avg_net_pnl (per trade, equity units): `0.003182`
- profit_factor: `3.0074`
- avg_hold_days: `26.73`

## Notes
- base_only = core shares buy&hold + idle tactical cash (no trading).
- overlay = base_only + tactical leg switching (MA filter), with costs applied.
- This report is non-predictive; it is a backtest summary for audit and comparison.
