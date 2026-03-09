# 0050 Tactical Cash Overlay Backtest

- generated_at_utc: `2026-03-09T07:56:18Z`
- script_fingerprint: `backtest_tw0050_tactical_cash@2026-02-24.v2.3.fix_execdelay0_and_force_close`
- price_csv: `tw0050_bb_cache/data.csv`

## Strategy
- MA window: `60`
- core_frac: `0.9` (tactical_cash = 1-core)
- costs: fee_rate=0.001425, tax_rate=0.001, slip_bps=5.0

## Snapshot (audit)
- rows: `2963`
- date_range: `2014-01-03` ~ `2026-03-09`
- time_in_market_pct (tactical leg): `0.6973`

## Performance (overlay vs base-only)

| metric | overlay | base_only | delta_vs_base |
|---|---:|---:|---:|
| CAGR | 18.71% | 18.41% | 0.30% |
| MDD | -32.73% | -32.81% | 0.08% |
| Sharpe0 | 1.047 | 1.046 | 0.001 |

## Trade KPIs (tactical leg)
- n_trades: `77`
- win_rate: `0.3506`
- avg_net_pnl (per trade, equity units): `0.002855`
- profit_factor: `2.8009`
- avg_hold_days: `26.84`

## Notes
- base_only = core shares buy&hold + idle tactical cash (no trading).
- overlay = base_only + tactical leg switching (MA filter), with costs applied.
- This report is non-predictive; it is a backtest summary for audit and comparison.
