# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@1c7f7c4`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-26T23:41:26.158139+00:00`
- STATS.generated_at_utc: `2026-01-26T23:41:26Z`
- STATS.as_of_ts: `2026-01-27T07:41:22+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | DFII10 | OK | 0 | 2026-01-23 | 1.92 | 0.913409 | 86.666667 | 48.015873 | -0.183055 | -0.558009 | -11.638418 | -1.538462 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-01-27T07:41:22+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | T10YIE | OK | 0 | 2026-01-26 | 2.32 | 1.754473 | 95 | 50.793651 | -0.069875 | -0.062848 | 0.084746 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-01-27T07:41:22+08:00 |
