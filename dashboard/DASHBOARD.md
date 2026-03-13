# Risk Dashboard (market_cache)

- Summary: ALERT=3 / WATCH=0 / INFO=0 / NONE=1; CHANGED=1; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@60e7331`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-13T15:56:46.179597+00:00`
- STATS.generated_at_utc: `2026-03-13T03:16:10Z`
- STATS.as_of_ts: `2026-03-13T03:16:10Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-13`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_RET | NEAR:ZΔ60 | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 23 | 24 | VIX | OK | 12.68 | 2026-03-12 | 27.29 | 2.576677 | 98.333333 | 94.047619 | 1.558927 | 0.713586 | 3.333333 | 12.628972 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-13T03:16:10Z |
| ALERT | JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 8 | 9 | OFR_FSI | OK | 12.68 | 2026-03-10 | -1.458 | 1.855683 | 95 | 80.15873 | 0.41462 | -2.569443 | -5 | -392.567568 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-13T03:16:10Z |
| ALERT | EXTREME_Z,JUMP_ZD | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 1 | 2 | SP500 | OK | 12.68 | 2026-03-12 | 6672.62 | -3.028575 | 1.666667 | 59.52381 | 0.559655 | -1.321547 | -5 | -1.522772 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-13T03:16:10Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.68 | 2026-03-12 | 0.82924 | -1.281028 | 11.666667 | 17.857143 | -0.805426 | -0.38947 | -13.333333 | -0.316724 | NA | DERIVED | 2026-03-13T03:16:10Z |
