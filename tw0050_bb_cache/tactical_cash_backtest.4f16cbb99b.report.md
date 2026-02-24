# 0050 Tactical Cash Overlay Backtest

- generated_at_utc: `2026-02-24T14:38:12Z`
- script_fingerprint: `backtest_tw0050_tactical_cash@2026-02-24.v2.2.post_only_segmentation_lag_execdelay_extraslip`
- price_csv: `tw0050_bb_cache/data.csv`

## Strategy
- MA window: `60`
- core_frac: `0.9` (tactical_cash = 1-core)
- costs: fee_rate=0.001425, tax_rate=0.001, slip_bps=5.0

## Snapshot (audit)
- rows: `2954`
- date_range: `2014-01-03` ~ `2026-02-24`
- time_in_market_pct (tactical leg): `0.0000`

## Performance (overlay vs base-only)

| metric | overlay | base_only | delta_vs_base |
|---|---:|---:|---:|
| CAGR | 19.23% | 19.23% | 0.00% |
| MDD | -32.81% | -32.81% | 0.00% |
| Sharpe0 | 1.090 | 1.090 | 0.000 |

## Trade KPIs (tactical leg)
- n_trades: `0`
- win_rate: `N/A`
- avg_net_pnl (per trade, equity units): `N/A`
- profit_factor: `N/A`
- avg_hold_days: `N/A`

## Notes
- base_only = core shares buy&hold + idle tactical cash (no trading).
- overlay = base_only + tactical leg switching (MA filter), with costs applied.
- This report is non-predictive; it is a backtest summary for audit and comparison.
