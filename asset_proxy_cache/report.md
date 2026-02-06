# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=0 / NONE=2; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@ba737cc`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-06T03:11:39.892690+00:00`
- STATS.generated_at_utc: `2026-02-06T03:11:39Z`
- STATS.as_of_ts: `2026-02-06T11:11:36+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | GLD.US_CLOSE | OK | 0 | 2026-02-05 | 442.01 | 1.091273 | 83.333333 | 96.031746 | 2.05929 | -0.415817 | -6.497175 | -2.630246 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260107&d2=20260206&i=d | 2026-02-06T11:11:36+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | IAU.US_CLOSE | OK | 0 | 2026-02-05 | 90.53 | 1.090716 | 83.333333 | 96.031746 | 2.058313 | -0.411219 | -6.497175 | -2.60355 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260107&d2=20260206&i=d | 2026-02-06T11:11:36+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | ALERT | ALERT→NONE | 1 | 0 | IYR.US_CLOSE | OK | 0 | 2026-02-05 | 96.15 | 0.953559 | 81.666667 | 71.428571 | 0.489065 | -0.229307 | -6.468927 | -0.238639 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20260107&d2=20260206&i=d | 2026-02-06T11:11:36+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | ALERT | ALERT→NONE | 1 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-02-05 | 90.84 | 1.132368 | 85 | 68.253968 | 0.455588 | -0.137982 | -4.830508 | -0.120946 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20260107&d2=20260206&i=d | 2026-02-06T11:11:36+08:00 |
