# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@df04fe5`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-09T07:32:45.443414+00:00`
- STATS.generated_at_utc: `2026-02-09T07:32:08Z`
- STATS.as_of_ts: `2026-02-09T07:32:08Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_RET | NEAR:PΔ60 | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 10 | 11 | VIX | OK | 0.01 | 2026-02-06 | 17.76 | 0.248988 | 76.666667 | 57.539683 | -0.231955 | -1.462112 | -15 | -18.419844 | abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-09T07:32:08Z |
| ALERT | LONG_EXTREME,JUMP_ZD,JUMP_P | NEAR:ret1%60 | HIGH | RISK_BIAS_UP | ALERT | SAME | 6 | 7 | SP500 | OK | 0.01 | 2026-02-06 | 6932.3 | 0.789264 | 80 | 95.238095 | 1.255557 | 1.333404 | 58.333333 | 1.969581 | P252>=95;abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-09T07:32:08Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 0.01 | 2026-02-06 | 0.841157 | 0.639416 | 71.666667 | 58.730159 | 0.334138 | 0.489436 | 11.666667 | 0.347697 | NA | DERIVED | 2026-02-09T07:32:08Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | OFR_FSI | OK | 0.01 | 2026-02-04 | -2.295 | 0.351643 | 76.666667 | 32.142857 | -0.578112 | 0.114055 | 5 | 1.713062 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-09T07:32:08Z |
