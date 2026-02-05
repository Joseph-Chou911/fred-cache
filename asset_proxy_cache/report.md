# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=2 / NONE=0; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@6e25450`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-05T03:12:38.410875+00:00`
- STATS.generated_at_utc: `2026-02-05T03:12:38Z`
- STATS.as_of_ts: `2026-02-05T11:12:35+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | NONE | NONE→ALERT | 0 | 1 | IYR.US_CLOSE | OK | 0 | 2026-02-04 | 96.38 | 1.181369 | 88.333333 | 77.380952 | 0.610571 | 1.270761 | 37.485876 | 1.452632 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260106&d2=20260205&i=d | 2026-02-05T11:12:35+08:00 |
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | NONE | NONE→ALERT | 0 | 1 | VNQ.US_CLOSE | OK | 0 | 2026-02-04 | 90.95 | 1.269685 | 90 | 70.238095 | 0.513763 | 1.356164 | 35.762712 | 1.450084 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260106&d2=20260205&i=d | 2026-02-05T11:12:35+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | ALERT→INFO | 11 | 0 | GLD.US_CLOSE | OK | 0 | 2026-02-04 | 453.95 | 1.519945 | 90 | 97.619048 | 2.313849 | -0.057064 | -1.525424 | -0.088038 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260106&d2=20260205&i=d | 2026-02-05T11:12:35+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | ALERT→INFO | 11 | 0 | IAU.US_CLOSE | OK | 0 | 2026-02-04 | 92.95 | 1.514845 | 90 | 97.619048 | 2.309963 | -0.062868 | -1.525424 | -0.128935 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260106&d2=20260205&i=d | 2026-02-05T11:12:35+08:00 |
