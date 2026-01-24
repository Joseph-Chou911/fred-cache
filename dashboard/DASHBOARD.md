# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=1 / NONE=1; CHANGED=2; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@e5caa24`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-24T15:40:05.488487+00:00`
- STATS.generated_at_utc: `2026-01-24T13:27:02Z`
- STATS.as_of_ts: `2026-01-24T13:27:02Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P,JUMP_RET | NEAR:ZΔ60 | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 2 | 3 | OFR_FSI | OK | 2.22 | 2026-01-21 | -2.445 | -0.168536 | 48.333333 | 15.079365 | -0.770122 | -0.703891 | -28.333333 | -11.389522 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-24T13:27:02Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 3 | 4 | VIX | OK | 2.22 | 2026-01-23 | 16.09 | -0.388096 | 43.333333 | 28.571429 | -0.534485 | 0.172147 | 13.333333 | 2.877238 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-24T13:27:02Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | WATCH | WATCH→INFO | 3 | 0 | SP500 | OK | 2.22 | 2026-01-23 | 6915.61 | 0.867814 | 81.666667 | 95.634921 | 1.330795 | 0.012874 | 0 | 0.03269 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-24T13:27:02Z |
| NONE | NA | NA | LOW | NA | WATCH | WATCH→NONE | 5 | 0 | HYG_IEF_RATIO | OK | 2.22 | 2026-01-23 | 0.845649 | 1.972317 | 95 | 78.968254 | 0.697772 | -0.477955 | -5 | -0.215945 | NA | DERIVED | 2026-01-24T13:27:02Z |
