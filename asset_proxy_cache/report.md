# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=0 / NONE=4; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@7850663`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-14T16:50:21.910553+00:00`
- STATS.generated_at_utc: `2026-03-14T16:50:21Z`
- STATS.as_of_ts: `2026-03-15T00:50:18+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-15`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | GLD.US_CLOSE | OK | 0 | 2026-03-13 | 460.84 | 0.549041 | 61.666667 | 90.873016 | 1.75688 | -0.210538 | -7.824859 | -1.314831 | NA | https://stooq.com/q/d/l/?s=gld.us&d1=20260212&d2=20260314&i=d | 2026-03-15T00:50:18+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IAU.US_CLOSE | OK | 0 | 2026-03-13 | 94.38 | 0.54761 | 61.666667 | 90.873016 | 1.75564 | -0.215716 | -9.519774 | -1.348385 | NA | https://stooq.com/q/d/l/?s=iau.us&d1=20260212&d2=20260314&i=d | 2026-03-15T00:50:18+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-03-13 | 97.5 | 0.191986 | 60 | 83.730159 | 0.850517 | 0.063307 | 0.677966 | 0.174664 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20260212&d2=20260314&i=d | 2026-03-15T00:50:18+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-03-13 | 92.16 | 0.235866 | 60 | 86.507937 | 0.90412 | 0.073076 | 0.677966 | 0.20112 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20260212&d2=20260314&i=d | 2026-03-15T00:50:18+08:00 |
