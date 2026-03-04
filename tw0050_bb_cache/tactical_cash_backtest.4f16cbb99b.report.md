# 0050 Tactical Cash Overlay Backtest

- generated_at_utc: `2026-03-04T07:50:38Z`
- script_fingerprint: `backtest_tw0050_tactical_cash@2026-02-24.v2.3.fix_execdelay0_and_force_close`
- price_csv: `tw0050_bb_cache/data.csv`

## Strategy
- MA window: `60`
- core_frac: `0.9` (tactical_cash = 1-core)
- costs: fee_rate=0.001425, tax_rate=0.001, slip_bps=5.0

## Snapshot (audit)
- rows: `2959`
- date_range: `2014-01-03` ~ `2026-03-03`
- time_in_market_pct (tactical leg): `0.6969`

## Performance (overlay vs base-only)

| metric | overlay | base_only | delta_vs_base |
|---|---:|---:|---:|
| CAGR | 19.38% | 19.07% | 0.31% |
| MDD | -32.73% | -32.81% | 0.08% |
| Sharpe0 | 1.083 | 1.082 | 0.001 |

## Trade KPIs (tactical leg)
- n_trades: `77`
- win_rate: `0.3506`
- avg_net_pnl (per trade, equity units): `0.003127`
- profit_factor: `2.9729`
- avg_hold_days: `26.79`

## Notes
- base_only = core shares buy&hold + idle tactical cash (no trading).
- overlay = base_only + tactical leg switching (MA filter), with costs applied.
- This report is non-predictive; it is a backtest summary for audit and comparison.
