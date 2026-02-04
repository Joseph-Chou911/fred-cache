# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=1 / WATCH=1 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@6af3195`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-04T17:09:23.200346+00:00`
- STATS.generated_at_utc: `2026-02-04T17:09:23Z`
- STATS.as_of_ts: `2026-02-05T01:09:20+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 1 | 2 | DFII10 | OK | 0 | 2026-02-02 | 1.94 | 1.289072 | 96.666667 | 55.15873 | 0.010169 | 0.869847 | 32.259887 | 2.105263 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-05T01:09:20+08:00 |
| WATCH | EXTREME_Z | NA | MOVE | MOVE_ONLY | WATCH | SAME | 8 | 9 | T10YIE | OK | 0 | 2026-02-03 | 2.36 | 2.223766 | 100 | 72.619048 | 0.580982 | 0.146726 | 3.389831 | 0.425532 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-05T01:09:20+08:00 |
