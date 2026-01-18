# Risk Dashboard (market_cache)

- RUN_TS_UTC: `2026-01-18T09:17:31.332233+00:00`
- STATS.generated_at_utc: `2026-01-18T04:13:53Z`
- STATS.as_of_ts: `2026-01-18T04:13:53Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- history_used_for_streak: `market_cache/history_lite.json`
- streak_calc: `recompute z60/p252/zΔ60/pΔ60/ret1% from history_lite values; ret1% denom = abs(prev_value) else NA`
- signal_rules: `Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(|ZΔ60|>=0.75 OR |PΔ60|>=15 OR |ret1%60|>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and |Z60|<2`

| Signal | Tag | Near | PrevSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | EXTREME_Z | NEAR:ZΔ60 | INFO | 1 | HYG_IEF_RATIO | OK | 5.06 | 2026-01-16 | 0.845304 | 2.464967 | 77.777778 | 0.743865 | 1.666667 | 0.447634 | &#124;Z60&#124;>=2 | DERIVED | 2026-01-18T04:13:53Z |
| WATCH | JUMP_RET | NA | WATCH | 2 | OFR_FSI | OK | 5.06 | 2026-01-14 | -2.626 | -0.709121 | 6.746032 | 0.278718 | 13.333333 | 3.278085 | &#124;ret1%60&#124;>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-18T04:13:53Z |
| INFO | LONG_EXTREME | NA | NONE | 0 | SP500 | OK | 5.06 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | -0.088684 | -1.666667 | -0.064224 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-18T04:13:53Z |
| NONE | NA | NA | ALERT | 0 | VIX | OK | 5.06 | 2026-01-16 | 15.86 | -0.450183 | 25.793651 | 0.024178 | 1.666667 | 0.126263 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-18T04:13:53Z |
