# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=2 / NONE=0; CHANGED=3; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@36b6314`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-11T09:09:41.123846+00:00`
- STATS.generated_at_utc: `2026-02-11T09:09:41Z`
- STATS.as_of_ts: `2026-02-11T17:09:37+08:00`
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
| ALERT | EXTREME_Z,LONG_EXTREME | NEAR:ZΔ60 | MOVE | MOVE_ONLY | WATCH | WATCH→ALERT | 4 | 5 | IYR.US_CLOSE | OK | 0 | 2026-02-10 | 99.32 | 3.18597 | 100 | 100 | 2.074163 | 0.728058 | 1.694915 | 1.284928 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260112&d2=20260211&i=d | 2026-02-11T17:09:37+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NEAR:ZΔ60 | MOVE | MOVE_ONLY | ALERT | SAME | 4 | 5 | VNQ.US_CLOSE | OK | 0 | 2026-02-10 | 93.88 | 3.411991 | 100 | 98.809524 | 2.004173 | 0.734619 | 0 | 1.32772 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260112&d2=20260211&i=d | 2026-02-11T17:09:37+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | WATCH→INFO | 5 | 0 | GLD.US_CLOSE | OK | 0 | 2026-02-10 | 462.4 | 1.56171 | 91.666667 | 98.015873 | 2.353075 | -0.195026 | -3.248588 | -0.991371 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260112&d2=20260211&i=d | 2026-02-11T17:09:37+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | WATCH→INFO | 5 | 0 | IAU.US_CLOSE | OK | 0 | 2026-02-10 | 94.71 | 1.561005 | 91.666667 | 98.015873 | 2.35153 | -0.191215 | -3.248588 | -0.96727 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260112&d2=20260211&i=d | 2026-02-11T17:09:37+08:00 |
