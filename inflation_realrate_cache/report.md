# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=0 / NONE=1; CHANGED=1; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@3da8548`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-27T03:10:32.033173+00:00`
- STATS.generated_at_utc: `2026-02-27T03:10:31Z`
- STATS.as_of_ts: `2026-02-27T11:10:27+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `inflation_realrate_cache/stats_latest.json`
- dash_history: `inflation_realrate_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-27`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | EXTREME_Z | NA | MOVE | MOVE_ONLY | NONE | NONE→WATCH | 0 | 1 | DFII10 | OK | 0 | 2026-02-25 | 1.77 | -2.178697 | 5 | 11.904762 | -1.176163 | -0.088676 | -0.084746 | -0.561798 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-27T11:10:27+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | T10YIE | OK | 0 | 2026-02-26 | 2.28 | -0.0701 | 58.333333 | 32.539683 | -0.605075 | 0.000595 | 0.706215 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-27T11:10:27+08:00 |
