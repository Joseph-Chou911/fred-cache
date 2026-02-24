# 0050 Tactical Cash Overlay Backtest

- generated_at_utc: `2026-02-24T13:57:45Z`
- script_fingerprint: `backtest_tw0050_tactical_cash@2026-02-24.v1`
- price_csv: `tw0050_bb_cache/data.csv`

## Strategy
- MA window: `60`
- core_frac: `0.9` (tactical_cash = 1-core)
- costs: fee_rate=0.001425, tax_rate=0.001, slip_bps=5.0

## Snapshot (audit)
- rows: `4193`
- date_range: `2009-01-02` ~ `2026-02-24`
- time_in_market_pct (tactical leg): `0.6678`

## Performance (overlay vs base-only)

| metric | overlay | base_only | delta_vs_base |
|---|---:|---:|---:|
| CAGR | 7.98% | 7.99% | -0.00% |
| MDD | -77.65% | -73.10% | -4.55% |
| Sharpe0 | 0.495 | 0.488 | 0.007 |

## Trade KPIs (tactical leg)
- n_trades: `121`
- win_rate: `0.2645`
- avg_net_pnl (per trade, equity units): `-0.000023`
- profit_factor: `0.9833`
- avg_hold_days: `23.15`

## Notes
- base_only = core shares buy&hold + idle tactical cash (no trading).
- overlay = base_only + tactical leg switching (MA filter), with costs applied.
- This report is non-predictive; it is a backtest summary for audit and comparison.
