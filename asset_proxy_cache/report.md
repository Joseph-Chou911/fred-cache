# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=2 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@3770096`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-01T08:48:44.747369+00:00`
- STATS.generated_at_utc: `2026-03-01T08:48:44Z`
- STATS.as_of_ts: `2026-03-01T16:48:42+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-01`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 22 | 23 | VNQ.US_CLOSE | OK | 0 | 2026-02-27 | 95.69 | 2.169206 | 100 | 100 | 2.599035 | -0.031982 | 0 | 0.177973 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260130&d2=20260301&i=d | 2026-03-01T16:48:42+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 2 | 3 | IYR.US_CLOSE | OK | 0 | 2026-02-27 | 101.28 | 2.11378 | 100 | 100 | 2.619619 | -0.003244 | 1.694915 | 0.22761 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260130&d2=20260301&i=d | 2026-03-01T16:48:42+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | GLD.US_CLOSE | OK | 0 | 2026-02-27 | 483.75 | 1.62644 | 96.666667 | 99.206349 | 2.376586 | 0.142959 | 1.751412 | 1.313144 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260130&d2=20260301&i=d | 2026-03-01T16:48:42+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | IAU.US_CLOSE | OK | 0 | 2026-02-27 | 99.07 | 1.624861 | 96.666667 | 99.206349 | 2.374313 | 0.142391 | 1.751412 | 1.308927 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260130&d2=20260301&i=d | 2026-03-01T16:48:42+08:00 |
