# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=0 / NONE=0; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@76af506`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-28T02:36:09.313636+00:00`
- STATS.generated_at_utc: `2026-01-28T02:36:09Z`
- STATS.as_of_ts: `2026-01-28T10:36:04+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P | NA | MOVE | MOVE_ONLY | NONE | NONE→WATCH | 0 | 1 | DFII10 | OK | 0 | 2026-01-26 | 1.9 | 0.52741 | 65 | 40.873016 | -0.321955 | -0.38697 | -21.440678 | -1.041667 | abs(PΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-01-28T10:36:04+08:00 |
| WATCH | EXTREME_Z | NA | MOVE | MOVE_ONLY | NONE | NONE→WATCH | 0 | 1 | T10YIE | OK | 0 | 2026-01-27 | 2.34 | 2.284664 | 100 | 61.507937 | 0.243355 | 0.535263 | 5.084746 | 0.862069 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-01-28T10:36:04+08:00 |
