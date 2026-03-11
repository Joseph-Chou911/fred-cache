# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=0 / NONE=0; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@1a0eb6e`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-11T23:04:50.450510+00:00`
- STATS.generated_at_utc: `2026-03-11T23:04:50Z`
- STATS.as_of_ts: `2026-03-12T07:04:46+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-12`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NEAR:PΔ60 | MOVE | MOVE_ONLY | NONE | NONE→WATCH | 0 | 1 | DFII10 | OK | 0 | 2026-03-10 | 1.82 | -0.789931 | 30 | 28.571429 | -0.740542 | 0.645138 | 14.745763 | 2.247191 | abs(ret1%1d)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:04:46+08:00 |
| WATCH | JUMP_P | NEAR:ZΔ60 | MOVE | MOVE_ONLY | NONE | NONE→WATCH | 0 | 1 | T10YIE | OK | 0 | 2026-03-11 | 2.36 | 1.656075 | 100 | 80.555556 | 0.844984 | 0.687758 | 20.338983 | 1.287554 | abs(PΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:04:46+08:00 |
