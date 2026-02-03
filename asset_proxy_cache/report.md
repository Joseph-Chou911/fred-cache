# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@0d3f054`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-03T23:04:47.554642+00:00`
- STATS.generated_at_utc: `2026-02-03T23:04:47Z`
- STATS.as_of_ts: `2026-02-04T07:04:44+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | LONG_EXTREME,JUMP_ZD,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | WATCH→ALERT | 10 | 11 | GLD.US_CLOSE | OK | 0 | 2026-02-03 | 454.35 | 1.588835 | 91.666667 | 98.015873 | 2.352086 | 0.86341 | 6.920904 | 6.372767 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260104&d2=20260203&i=d | 2026-02-04T07:04:44+08:00 |
| ALERT | LONG_EXTREME,JUMP_ZD,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | WATCH→ALERT | 10 | 11 | IAU.US_CLOSE | OK | 0 | 2026-02-03 | 93.07 | 1.589559 | 91.666667 | 98.015873 | 2.35167 | 0.849976 | 6.920904 | 6.28069 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260104&d2=20260203&i=d | 2026-02-04T07:04:44+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | ALERT | ALERT→NONE | 1 | 0 | IYR.US_CLOSE | OK | 0 | 2026-02-03 | 95 | -0.076581 | 51.666667 | 43.253968 | -0.09528 | -0.21411 | -7.655367 | -0.241521 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20260104&d2=20260203&i=d | 2026-02-04T07:04:44+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | ALERT | ALERT→NONE | 1 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-02-03 | 89.65 | -0.070914 | 55 | 40.079365 | -0.161029 | -0.221472 | -4.322034 | -0.233697 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20260104&d2=20260203&i=d | 2026-02-04T07:04:44+08:00 |
