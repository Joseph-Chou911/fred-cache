# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=2 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@5bf26a9`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-12T09:03:31.214035+00:00`
- STATS.generated_at_utc: `2026-03-12T09:03:31Z`
- STATS.as_of_ts: `2026-03-12T17:03:28+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-12`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | GLD.US_CLOSE | OK | 0 | 2026-03-11 | 476.24 | 1.103807 | 88.333333 | 97.222222 | 2.049231 | -0.073587 | -3.19209 | -0.339011 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260210&d2=20260312&i=d | 2026-03-12T17:03:28+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | IAU.US_CLOSE | OK | 0 | 2026-03-11 | 97.55 | 1.104871 | 88.333333 | 97.222222 | 2.04884 | -0.066994 | -3.19209 | -0.296402 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260210&d2=20260312&i=d | 2026-03-12T17:03:28+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-03-11 | 98.01 | 0.416505 | 63.333333 | 89.68254 | 1.078872 | -0.419152 | -9.548023 | -1.104889 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20260210&d2=20260312&i=d | 2026-03-12T17:03:28+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-03-11 | 92.65 | 0.46183 | 66.666667 | 90.47619 | 1.129399 | -0.395548 | -6.214689 | -1.036103 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20260210&d2=20260312&i=d | 2026-03-12T17:03:28+08:00 |
