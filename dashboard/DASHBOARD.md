# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=1 / NONE=2; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@38509e4`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-27T15:54:55.060667+00:00`
- STATS.generated_at_utc: `2026-01-27T13:55:03Z`
- STATS.as_of_ts: `2026-01-27T13:55:03Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 5 | 6 | OFR_FSI | OK | 2 | 2026-01-22 | -2.68 | -0.813691 | 30 | 7.142857 | -1.028792 | -0.645155 | -18.333333 | -9.611452 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-27T13:55:03Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 2 | 2026-01-26 | 6950.23 | 1.214855 | 95 | 98.809524 | 1.390574 | 0.347042 | 13.333333 | 0.500607 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-27T13:55:03Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 6 | 0 | VIX | OK | 2 | 2026-01-26 | 16.15 | -0.360856 | 45 | 30.15873 | -0.521079 | 0.02724 | 1.666667 | 0.372902 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-27T13:55:03Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 2 | 2026-01-26 | 0.844833 | 1.731892 | 91.666667 | 75.793651 | 0.632358 | -0.240425 | -3.333333 | -0.096471 | NA | DERIVED | 2026-01-27T13:55:03Z |
