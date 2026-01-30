# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=4 / WATCH=0 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@9fc10a9`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-30T17:59:04.477552+00:00`
- STATS.generated_at_utc: `2026-01-30T17:59:04Z`
- STATS.as_of_ts: `2026-01-31T01:59:02+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 6 | 7 | GLD.US_CLOSE | OK | 0 | 2026-01-29 | 495.9 | 3.097982 | 100 | 100 | 3.254799 | -0.263744 | 0 | 0.295212 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20251231&d2=20260130&i=d | 2026-01-31T01:59:02+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 6 | 7 | IAU.US_CLOSE | OK | 0 | 2026-01-29 | 101.57 | 3.095375 | 100 | 100 | 3.250063 | -0.262768 | 0 | 0.296238 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20251231&d2=20260130&i=d | 2026-01-31T01:59:02+08:00 |
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | ALERT | SAME | 2 | 3 | IYR.US_CLOSE | OK | 0 | 2026-01-29 | 96.27 | 1.165888 | 86.666667 | 74.206349 | 0.563673 | 1.128292 | 29.039548 | 1.27288 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=iyr.us&d1=20251231&d2=20260130&i=d | 2026-01-31T01:59:02+08:00 |
| ALERT | JUMP_ZD,JUMP_P | NA | MOVE | MOVE_ONLY | ALERT | SAME | 2 | 3 | VNQ.US_CLOSE | OK | 0 | 2026-01-29 | 90.71 | 1.102648 | 86.666667 | 66.666667 | 0.383865 | 1.320129 | 35.819209 | 1.397429 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=vnq.us&d1=20251231&d2=20260130&i=d | 2026-01-31T01:59:02+08:00 |
