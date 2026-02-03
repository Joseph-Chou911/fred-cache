# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=3 / INFO=0 / NONE=1; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@3aa2389`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-03T22:59:10.327410+00:00`
- STATS.generated_at_utc: `2026-02-03T22:58:32Z`
- STATS.as_of_ts: `2026-02-03T22:58:32Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | INFO | INFO→WATCH | 0 | 1 | SP500 | OK | 0.01 | 2026-02-03 | 6917.81 | 0.686458 | 71.666667 | 93.253968 | 1.254132 | -0.601818 | -23.333333 | -0.8404 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-03T22:58:32Z |
| WATCH | JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 4 | 5 | VIX | OK | 0.01 | 2026-02-02 | 16.34 | -0.245463 | 46.666667 | 31.746032 | -0.487721 | -0.389856 | -26.666667 | -6.307339 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-03T22:58:32Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 1 | 2 | OFR_FSI | OK | 0.01 | 2026-01-30 | -2.255 | 0.456701 | 80 | 33.333333 | -0.536476 | 0.166716 | 6.666667 | 2.169197 | abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-03T22:58:32Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 0.01 | 2026-02-03 | 0.844865 | 1.356229 | 85 | 76.587302 | 0.694521 | -0.300433 | -10 | -0.168426 | NA | DERIVED | 2026-02-03T22:58:32Z |
