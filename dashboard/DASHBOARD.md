# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=3 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=3
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@ffc271b`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-05T15:54:29.839970+00:00`
- STATS.generated_at_utc: `2026-02-05T11:27:29Z`
- STATS.as_of_ts: `2026-02-05T11:27:29Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 6 | 7 | VIX | OK | 4.45 | 2026-02-04 | 18.64 | 0.613716 | 83.333333 | 66.269841 | -0.058589 | 0.231563 | 1.666667 | 3.555556 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-05T11:27:29Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 3 | 4 | OFR_FSI | OK | 4.45 | 2026-02-02 | -2.326 | 0.259891 | 71.666667 | 27.777778 | -0.61461 | -0.196811 | -8.333333 | -3.148559 | abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-05T11:27:29Z |
| WATCH | JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 2 | 3 | SP500 | OK | 4.45 | 2026-02-04 | 6882.72 | 0.317049 | 56.666667 | 88.888889 | 1.173646 | -0.369409 | -15 | -0.507241 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-05T11:27:29Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 4.45 | 2026-02-04 | 0.8441 | 1.182563 | 81.666667 | 73.809524 | 0.622943 | -0.190918 | -3.333333 | -0.102971 | NA | DERIVED | 2026-02-05T11:27:29Z |
