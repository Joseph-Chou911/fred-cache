# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=4 / WATCH=0 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@7ef5304`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-29T18:03:36.894165+00:00`
- STATS.generated_at_utc: `2026-01-29T18:03:36Z`
- STATS.as_of_ts: `2026-01-30T02:03:33+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 5 | 6 | GLD.US_CLOSE | OK | 0 | 2026-01-28 | 494.56 | 3.371203 | 100 | 100 | 3.300336 | 0.321839 | 0 | 3.905708 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20251230&d2=20260129&i=d | 2026-01-30T02:03:33+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 5 | 6 | IAU.US_CLOSE | OK | 0 | 2026-01-28 | 101.25 | 3.367673 | 100 | 100 | 3.295223 | 0.319424 | 0 | 3.887977 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20251230&d2=20260129&i=d | 2026-01-30T02:03:33+08:00 |
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | ALERT | SAME | 1 | 2 | IYR.US_CLOSE | OK | 0 | 2026-01-28 | 95.08 | 0.043638 | 58.333333 | 46.428571 | -0.056049 | -0.922914 | -24.717514 | -1.010101 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=iyr.us&d1=20251230&d2=20260129&i=d | 2026-01-30T02:03:33+08:00 |
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | ALERT | SAME | 1 | 2 | VNQ.US_CLOSE | OK | 0 | 2026-01-28 | 89.46 | -0.210342 | 51.666667 | 35.31746 | -0.266466 | -1.004854 | -27.99435 | -1.039938 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=vnq.us&d1=20251230&d2=20260129&i=d | 2026-01-30T02:03:33+08:00 |
