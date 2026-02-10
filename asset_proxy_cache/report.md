# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=1 / WATCH=3 / INFO=0 / NONE=0; CHANGED=1; WATCH_STREAK>=3=3
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@e00029c`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-10T03:31:11.065573+00:00`
- STATS.generated_at_utc: `2026-02-10T03:31:10Z`
- STATS.as_of_ts: `2026-02-10T11:31:07+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 3 | 4 | VNQ.US_CLOSE | OK | 0 | 2026-02-09 | 92.64 | 2.679018 | 100 | 95.634921 | 1.384549 | 0.188442 | 1.694915 | 0.422764 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260111&d2=20260210&i=d | 2026-02-10T11:31:07+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | ALERT→WATCH | 3 | 4 | IYR.US_CLOSE | OK | 0 | 2026-02-09 | 98.06 | 2.462859 | 98.333333 | 97.222222 | 1.454834 | 0.208433 | 0.028249 | 0.419867 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260111&d2=20260210&i=d | 2026-02-10T11:31:07+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 4 | 5 | GLD.US_CLOSE | OK | 0 | 2026-02-09 | 467.03 | 1.775285 | 95 | 98.809524 | 2.473225 | 0.313762 | 3.474576 | 2.540289 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260111&d2=20260210&i=d | 2026-02-10T11:31:07+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 4 | 5 | IAU.US_CLOSE | OK | 0 | 2026-02-09 | 95.63 | 1.770749 | 95 | 98.809524 | 2.469287 | 0.315468 | 3.474576 | 2.552279 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260111&d2=20260210&i=d | 2026-02-10T11:31:07+08:00 |
