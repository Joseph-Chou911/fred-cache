# Risk Dashboard (market_cache)

- RUN_TS_UTC: `2026-01-18T05:39:08.741486+00:00`
- STATS.generated_at_utc: `2026-01-18T04:13:53Z`
- STATS.as_of_ts: `2026-01-18T04:13:53Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- signal_rules: `Extreme(|Z60|>=2 OR P252>= 95 OR P252<= 5); Jump(|ZΔ60|>=0.5 OR |PΔ60|>=10 OR |ret1%60|>=1)`

| Signal | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | HYG_IEF_RATIO | OK | 1.42 | 2026-01-16 | 0.845304 | 2.464967 | 77.777778 | 0.743865 | 1.666667 | 0.447634 | |Z60|>=2;|ZΔ60|>=0.5 | DERIVED | 2026-01-18T04:13:53Z |
| ALERT | OFR_FSI | OK | 1.42 | 2026-01-14 | -2.626 | -0.709121 | 6.746032 | 0.278718 | 13.333333 | 3.278085 | |PΔ60|>=10;|ret1%60|>=1 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-18T04:13:53Z |
| ALERT | SP500 | OK | 1.42 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | -0.088684 | -1.666667 | -0.064224 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-18T04:13:53Z |
| NONE | VIX | OK | 1.42 | 2026-01-16 | 15.86 | -0.450183 | 25.793651 | 0.024178 | 1.666667 | 0.126263 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-18T04:13:53Z |
