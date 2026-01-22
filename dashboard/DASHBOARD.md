# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=3; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@72daac5`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-22T16:00:25.942330+00:00`
- STATS.generated_at_utc: `2026-01-22T04:34:34Z`
- STATS.as_of_ts: `2026-01-22T04:34:34Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 1 | 2 | VIX | OK | 11.43 | 2026-01-21 | 16.9 | -0.098899 | 55 | 46.428571 | -0.382638 | -1.187689 | -35 | -15.878547 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-22T04:34:34Z |
| ALERT | JUMP_ZD,JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 1 | 2 | SP500 | OK | 11.43 | 2026-01-21 | 6875.62 | 0.474532 | 66.666667 | 92.063492 | 1.269998 | 0.821254 | 36.666667 | 1.15877 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-22T04:34:34Z |
| WATCH | JUMP_P,JUMP_RET | NEAR:ZΔ60 | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | OFR_FSI | OK | 11.43 | 2026-01-19 | -2.437 | -0.133912 | 51.666667 | 15.873016 | -0.766847 | 0.745786 | 28.333333 | 9.774158 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-22T04:34:34Z |
| WATCH | EXTREME_Z | NA | LOW | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 3 | 4 | HYG_IEF_RATIO | OK | 11.43 | 2026-01-21 | 0.846764 | 2.477248 | 100 | 81.746032 | 0.78552 | -0.111183 | 0 | 0.035001 | abs(Z60)>=2 | DERIVED | 2026-01-22T04:34:34Z |
