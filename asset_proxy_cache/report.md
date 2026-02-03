# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=4; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@93637cc`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-03T08:59:02.127635+00:00`
- STATS.generated_at_utc: `2026-02-03T08:59:02Z`
- STATS.as_of_ts: `2026-02-03T16:58:58+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | NONE | NONE→ALERT | 0 | 1 | IYR.US_CLOSE | OK | 0 | 2026-02-02 | 95.23 | 0.143645 | 60 | 47.619048 | 0.023416 | -0.96243 | -24.745763 | -1.070019 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260104&d2=20260203&i=d | 2026-02-03T16:58:58+08:00 |
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | NONE | NONE→ALERT | 0 | 1 | VNQ.US_CLOSE | OK | 0 | 2026-02-02 | 89.86 | 0.159323 | 60 | 47.619048 | -0.053642 | -0.993867 | -26.440678 | -1.035242 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260104&d2=20260203&i=d | 2026-02-03T16:58:58+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | ALERT→WATCH | 9 | 10 | GLD.US_CLOSE | OK | 0 | 2026-02-02 | 427.13 | 0.74301 | 85 | 96.428571 | 1.849346 | -0.601471 | -4.830508 | -4.004944 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260104&d2=20260203&i=d | 2026-02-03T16:58:58+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | ALERT→WATCH | 9 | 10 | IAU.US_CLOSE | OK | 0 | 2026-02-02 | 87.57 | 0.75709 | 85 | 96.428571 | 1.857197 | -0.619022 | -4.830508 | -4.116939 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260104&d2=20260203&i=d | 2026-02-03T16:58:58+08:00 |
