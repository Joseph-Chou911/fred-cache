# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@1a099df`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-09T03:23:09.891949+00:00`
- STATS.generated_at_utc: `2026-02-09T03:23:09Z`
- STATS.as_of_ts: `2026-02-09T11:23:06+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | ALERT | SAME | 2 | 3 | IYR.US_CLOSE | OK | 0 | 2026-02-06 | 97.66 | 2.218579 | 98.333333 | 91.666667 | 1.253484 | 1.266357 | 16.977401 | 1.560062 | abs(Z60)>=2;abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260110&d2=20260209&i=d | 2026-02-09T11:23:06+08:00 |
| ALERT | EXTREME_Z,JUMP_ZD | NEAR:PΔ60 | MOVE | MOVE_ONLY | ALERT | SAME | 2 | 3 | VNQ.US_CLOSE | OK | 0 | 2026-02-06 | 92.25 | 2.44659 | 98.333333 | 93.650794 | 1.185965 | 1.314461 | 13.587571 | 1.55218 | abs(Z60)>=2;abs(ZΔ60)>=0.75 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260110&d2=20260209&i=d | 2026-02-09T11:23:06+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 3 | 4 | GLD.US_CLOSE | OK | 0 | 2026-02-06 | 455.46 | 1.478305 | 91.666667 | 98.015873 | 2.288284 | 0.403807 | 8.615819 | 3.042918 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260110&d2=20260209&i=d | 2026-02-09T11:23:06+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 3 | 4 | IAU.US_CLOSE | OK | 0 | 2026-02-06 | 93.24 | 1.472073 | 91.666667 | 98.015873 | 2.283676 | 0.398127 | 8.615819 | 3.004529 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260110&d2=20260209&i=d | 2026-02-09T11:23:06+08:00 |
