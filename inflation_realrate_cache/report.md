# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@49e9d81`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-13T09:04:29.581254+00:00`
- STATS.generated_at_utc: `2026-02-13T09:04:29Z`
- STATS.as_of_ts: `2026-02-13T17:04:26+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1% (1D) = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P | NA | MOVE | MOVE_ONLY | WATCH | SAME | 1 | 2 | DFII10 | OK | 0 | 2026-02-11 | 1.86 | -0.687582 | 28.333333 | 31.349206 | -0.560088 | 0.486209 | 16.468927 | 1.086957 | abs(PΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-13T17:04:26+08:00 |
| NONE | NA | NEAR:ZΔ60 | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | T10YIE | OK | 0 | 2026-02-12 | 2.29 | 0.266931 | 68.333333 | 38.492063 | -0.498261 | -0.693347 | -11.327684 | -1.293103 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-13T17:04:26+08:00 |
