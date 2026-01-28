# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@1b2438f`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-28T17:53:03.911975+00:00`
- STATS.generated_at_utc: `2026-01-28T17:53:03Z`
- STATS.as_of_ts: `2026-01-29T01:52:58+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 4 | 5 | GLD.US_CLOSE | OK | 0 | 2026-01-27 | 476.1 | 3.061661 | 100 | 100 | 2.996905 | 0.175386 | 0 | 2.425221 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20251229&d2=20260128&i=d | 2026-01-29T01:52:58+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 4 | 5 | IAU.US_CLOSE | OK | 0 | 2026-01-27 | 97.48 | 3.060502 | 100 | 100 | 2.993986 | 0.173707 | 0 | 2.416474 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20251229&d2=20260128&i=d | 2026-01-29T01:52:58+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-01-27 | 96.03 | 0.981871 | 83.333333 | 67.857143 | 0.440892 | 0.069569 | 0.282486 | 0.093809 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20251229&d2=20260128&i=d | 2026-01-29T01:52:58+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-01-27 | 90.39 | 0.810019 | 80 | 59.52381 | 0.216876 | -0.043576 | -1.355932 | -0.033179 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20251229&d2=20260128&i=d | 2026-01-29T01:52:58+08:00 |
