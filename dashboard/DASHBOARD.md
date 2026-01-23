# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=4 / INFO=0 / NONE=0; CHANGED=2; WATCH_STREAK>=3=3
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@b94000a`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-23T15:54:00.791123+00:00`
- STATS.generated_at_utc: `2026-01-23T04:12:23Z`
- STATS.as_of_ts: `2026-01-23T04:12:23Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | LONG_EXTREME,JUMP_P | NA | HIGH | RISK_BIAS_UP | ALERT | ALERT→WATCH | 2 | 3 | SP500 | OK | 11.69 | 2026-01-22 | 6913.35 | 0.854939 | 81.666667 | 95.634921 | 1.33727 | 0.380407 | 15 | 0.548751 | P252>=95;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-23T04:12:23Z |
| WATCH | JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 2 | 3 | VIX | OK | 11.69 | 2026-01-22 | 15.64 | -0.560243 | 30 | 20.238095 | -0.619447 | -0.461344 | -25 | -7.455621 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-23T04:12:23Z |
| WATCH | EXTREME_Z | NA | LOW | DIR_UNCERTAIN_ABS | WATCH | SAME | 4 | 5 | HYG_IEF_RATIO | OK | 11.69 | 2026-01-22 | 0.847479 | 2.450272 | 100 | 83.730159 | 0.863746 | -0.026976 | 0 | 0.084412 | abs(Z60)>=2 | DERIVED | 2026-01-23T04:12:23Z |
| WATCH | JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 1 | 2 | OFR_FSI | OK | 11.69 | 2026-01-20 | -2.195 | 0.535354 | 76.666667 | 36.904762 | -0.492944 | 0.669266 | 25 | 9.930242 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-23T04:12:23Z |
