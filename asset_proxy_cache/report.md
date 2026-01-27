# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@e4698b0`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-27T17:48:04.587327+00:00`
- STATS.generated_at_utc: `2026-01-27T17:48:04Z`
- STATS.as_of_ts: `2026-01-28T01:48:00+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 3 | 4 | GLD.US_CLOSE | OK | 0 | 2026-01-26 | 464.7 | 2.885037 | 100 | 100 | 2.822297 | 0.048606 | 0 | 1.462882 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20251228&d2=20260127&i=d | 2026-01-28T01:48:00+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 3 | 4 | IAU.US_CLOSE | OK | 0 | 2026-01-26 | 95.18 | 2.885298 | 100 | 100 | 2.820557 | 0.052217 | 0 | 1.482034 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20251228&d2=20260127&i=d | 2026-01-28T01:48:00+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-01-26 | 95.94 | 0.929012 | 83.333333 | 65.873016 | 0.396968 | -0.110361 | -1.412429 | -0.104123 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20251228&d2=20260127&i=d | 2026-01-28T01:48:00+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-01-26 | 90.42 | 0.870587 | 81.666667 | 60.31746 | 0.231743 | -0.141056 | -3.079096 | -0.132538 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20251228&d2=20260127&i=d | 2026-01-28T01:48:00+08:00 |
