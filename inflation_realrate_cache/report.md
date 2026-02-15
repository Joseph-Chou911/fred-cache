# Risk Dashboard (inflation_realrate_cache)

- Summary: ALERT=1 / WATCH=0 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@4881452`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-15T03:24:04.407776+00:00`
- STATS.generated_at_utc: `2026-02-15T03:24:04Z`
- STATS.as_of_ts: `2026-02-15T11:24:00+08:00`
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
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_P,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 3 | 4 | DFII10 | OK | 0 | 2026-02-12 | 1.8 | -2.035704 | 6.666667 | 17.063492 | -1.013273 | -1.339524 | -20.451977 | -3.225806 | abs(Z60)>=2;abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-15T11:24:00+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | T10YIE | OK | 0 | 2026-02-13 | 2.27 | -0.193369 | 60 | 24.206349 | -0.818949 | -0.458654 | -7.79661 | -0.873362 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 | 2026-02-15T11:24:00+08:00 |
