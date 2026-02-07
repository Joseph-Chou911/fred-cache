# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=1 / WATCH=0 / INFO=0 / NONE=1; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@01ca80c`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-07T03:05:42.642036+00:00`
- STATS.generated_at_utc: `2026-02-07T03:05:42Z`
- STATS.as_of_ts: `2026-02-07T11:05:38+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | MOVE | MOVE_ONLY | NONE | NONE→ALERT | 0 | 1 | DFII10 | OK | 0 | 2026-02-05 | 1.89 | 0.083465 | 46.666667 | 38.492063 | -0.351056 | -1.129413 | -49.943503 | -2.57732 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-07T11:05:38+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | WATCH | WATCH→NONE | 1 | 0 | T10YIE | OK | 0 | 2026-02-06 | 2.34 | 1.552785 | 90 | 62.301587 | 0.284743 | 0.443937 | 6.949153 | 0.862069 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-07T11:05:38+08:00 |
