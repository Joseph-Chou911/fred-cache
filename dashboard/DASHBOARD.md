# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@17a5b8e`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-11T16:00:56.115120+00:00`
- STATS.generated_at_utc: `2026-03-11T03:13:04Z`
- STATS.as_of_ts: `2026-03-11T03:13:04Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-11`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 21 | 22 | VIX | OK | 12.8 | 2026-03-10 | 24.93 | 2.174096 | 96.666667 | 92.063492 | 1.129773 | -0.317322 | -1.666667 | -2.235294 | abs(Z60)>=2;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-11T03:13:04Z |
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 6 | 7 | OFR_FSI | OK | 12.8 | 2026-03-06 | -0.802 | 4.182195 | 100 | 90.079365 | 1.157358 | 1.516846 | 1.666667 | 49.047014 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-11T03:13:04Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.8 | 2026-03-10 | 0.829946 | -1.22863 | 15 | 21.428571 | -0.729727 | 0.240758 | 5 | 0.148414 | NA | DERIVED | 2026-03-11T03:13:04Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | SP500 | OK | 12.8 | 2026-03-10 | 6781.48 | -1.692795 | 6.666667 | 69.444444 | 0.787288 | -0.16603 | 0 | -0.213508 | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-11T03:13:04Z |
