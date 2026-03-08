# Risk Dashboard (market_cache)

- Summary: ALERT=3 / WATCH=0 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@832049e`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-08T15:36:23.870930+00:00`
- STATS.generated_at_utc: `2026-03-08T03:18:53Z`
- STATS.as_of_ts: `2026-03-08T03:18:53Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-08`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 18 | 19 | VIX | OK | 12.29 | 2026-03-06 | 29.49 | 4.022463 | 100 | 94.84127 | 2.012612 | 1.494469 | 0 | 24.168421 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-08T03:18:53Z |
| ALERT | EXTREME_Z,JUMP_ZD | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 15 | 16 | SP500 | OK | 12.29 | 2026-03-06 | 6740.02 | -2.490026 | 3.333333 | 67.857143 | 0.719377 | -1.423329 | -11.666667 | -1.32768 | abs(Z60)>=2;abs(ZΔ60)>=0.75 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-08T03:18:53Z |
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 3 | 4 | OFR_FSI | OK | 12.29 | 2026-03-04 | -1.19 | 4.168326 | 100 | 86.904762 | 0.726724 | 0.784595 | 0 | 26.086957 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-08T03:18:53Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.29 | 2026-03-06 | 0.826188 | -1.949305 | 5 | 9.52381 | -1.159671 | -0.530203 | -5 | -0.430269 | NA | DERIVED | 2026-03-08T03:18:53Z |
