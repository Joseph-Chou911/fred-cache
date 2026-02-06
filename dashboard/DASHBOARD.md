# Risk Dashboard (market_cache)

- Summary: ALERT=3 / WATCH=0 / INFO=0 / NONE=1; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@1981948`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-06T15:54:32.323774+00:00`
- STATS.generated_at_utc: `2026-02-06T03:18:01Z`
- STATS.as_of_ts: `2026-02-06T03:18:01Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 7 | 8 | VIX | OK | 12.61 | 2026-02-05 | 21.77 | 1.7111 | 91.666667 | 82.539683 | 0.52628 | 1.097384 | 8.333333 | 16.791845 | abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-06T03:18:01Z |
| ALERT | JUMP_ZD,JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 3 | 4 | SP500 | OK | 12.61 | 2026-02-05 | 6798.4 | -0.54414 | 21.666667 | 78.968254 | 0.995861 | -0.861189 | -35 | -1.225097 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-06T03:18:01Z |
| ALERT | JUMP_ZD,JUMP_P | NA | LOW | DIR_UNCERTAIN_ABS | NONE | NONE→ALERT | 0 | 1 | HYG_IEF_RATIO | OK | 12.61 | 2026-02-05 | 0.838243 | 0.14998 | 60 | 46.428571 | 0.026053 | -1.032583 | -21.666667 | -0.693892 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | DERIVED | 2026-02-06T03:18:01Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 4 | 0 | OFR_FSI | OK | 12.61 | 2026-02-03 | -2.335 | 0.237588 | 71.666667 | 27.777778 | -0.623615 | -0.022302 | 0 | -0.38693 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-06T03:18:01Z |
