# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=0; CHANGED=1; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@18b03cc`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-03T03:15:59.660637+00:00`
- STATS.generated_at_utc: `2026-03-03T03:15:59Z`
- STATS.as_of_ts: `2026-03-03T11:15:55+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-03`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | WATCH | WATCH→ALERT | 3 | 4 | T10YIE | OK | 0 | 2026-03-02 | 2.29 | 0.154636 | 68.333333 | 42.857143 | -0.414071 | 0.993515 | 39.519774 | 1.777778 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-03-03T11:15:55+08:00 |
| ALERT | EXTREME_Z | NA | MOVE | MOVE_ONLY | ALERT | SAME | 4 | 5 | DFII10 | OK | 0 | 2026-02-27 | 1.72 | -2.789474 | 1.666667 | 5.555556 | -1.534827 | -0.143772 | -0.028249 | -1.149425 | abs(Z60)>=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-03-03T11:15:55+08:00 |
