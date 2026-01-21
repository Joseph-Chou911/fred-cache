# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=1 / INFO=0 / NONE=1; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@4b754d9`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-21T16:03:03.415319+00:00`
- STATS.generated_at_utc: `2026-01-21T04:15:13Z`
- STATS.as_of_ts: `2026-01-21T04:15:13Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z | NA | LOW | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 2 | 3 | HYG_IEF_RATIO | OK | 11.8 | 2026-01-20 | 0.846468 | 2.588431 | 100 | 81.349206 | 0.747205 | 0.123464 | 0 | 0.137696 | abs(Z60)>=2;abs(Z60)>=2.5 | DERIVED | 2026-01-21T04:15:13Z |
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | INFO | INFO→ALERT | 0 | 1 | SP500 | OK | 11.8 | 2026-01-20 | 6796.86 | -0.346722 | 30 | 83.333333 | 1.115968 | -1.531651 | -61.666667 | -2.062677 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-21T04:15:13Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | VIX | OK | 11.8 | 2026-01-20 | 20.09 | 1.088791 | 90 | 74.603175 | 0.21765 | 0.433463 | 8.333333 | 6.63482 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-21T04:15:13Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 2 | 0 | OFR_FSI | OK | 11.8 | 2026-01-16 | -2.701 | -0.879698 | 23.333333 | 5.555556 | -1.067352 | -0.013096 | -1.666667 | -0.408922 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-21T04:15:13Z |
