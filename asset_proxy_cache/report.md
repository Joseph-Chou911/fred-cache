# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=2 / NONE=0; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@caacd4e`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-12T17:18:57.628741+00:00`
- STATS.generated_at_utc: `2026-02-12T17:18:57Z`
- STATS.as_of_ts: `2026-02-13T01:18:54+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1% (1D) = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 6 | 7 | IYR.US_CLOSE | OK | 0 | 2026-02-11 | 98.93 | 2.655984 | 98.333333 | 99.206349 | 1.858621 | -0.501225 | -1.666667 | -0.39267 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260113&d2=20260212&i=d | 2026-02-13T01:18:54+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 6 | 7 | VNQ.US_CLOSE | OK | 0 | 2026-02-11 | 93.36 | 2.73269 | 98.333333 | 98.412698 | 1.729958 | -0.648657 | -1.666667 | -0.543305 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260113&d2=20260212&i=d | 2026-02-13T01:18:54+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | GLD.US_CLOSE | OK | 0 | 2026-02-11 | 467.63 | 1.655632 | 95 | 98.809524 | 2.416398 | 0.111077 | 3.474576 | 1.131055 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260113&d2=20260212&i=d | 2026-02-13T01:18:54+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | IAU.US_CLOSE | OK | 0 | 2026-02-11 | 95.76 | 1.652554 | 95 | 98.809524 | 2.413311 | 0.108707 | 3.474576 | 1.113986 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260113&d2=20260212&i=d | 2026-02-13T01:18:54+08:00 |
