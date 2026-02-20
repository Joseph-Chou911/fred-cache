# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=0 / NONE=2; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@479edb0`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-20T00:41:10.229993+00:00`
- STATS.generated_at_utc: `2026-02-20T00:41:10Z`
- STATS.as_of_ts: `2026-02-20T08:41:04+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-20`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NONE | NA | NA | MOVE | MOVE_ONLY | WATCH | WATCH→NONE | 8 | 0 | DFII10 | OK | 0 | 2026-02-18 | 1.8 | -1.758005 | 11.666667 | 18.253968 | -0.98813 | 0.275528 | 3.19209 | 0.558659 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:41:04+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | WATCH | WATCH→NONE | 1 | 0 | T10YIE | OK | 0 | 2026-02-19 | 2.29 | 0.248698 | 68.333333 | 40.079365 | -0.46901 | -0.00223 | 0.536723 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:41:04+08:00 |
