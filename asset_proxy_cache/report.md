# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@524eac5`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-26T02:10:24.938453+00:00`
- STATS.generated_at_utc: `2026-01-26T02:10:24Z`
- STATS.as_of_ts: `2026-01-26T10:10:21+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 1 | 2 | GLD.US_CLOSE | OK | 0 | 2026-01-23 | 458 | 2.838172 | 100 | 100 | 2.731373 | 0.055325 | 0 | 1.374532 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20251227&d2=20260126&i=d | 2026-01-26T10:10:21+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 1 | 2 | IAU.US_CLOSE | OK | 0 | 2026-01-23 | 93.79 | 2.834577 | 100 | 100 | 2.728042 | 0.046141 | 0 | 1.328868 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20251227&d2=20260126&i=d | 2026-01-26T10:10:21+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-01-23 | 96.04 | 1.007798 | 83.333333 | 68.650794 | 0.45108 | 0.24825 | 5.367232 | 0.292398 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20251227&d2=20260126&i=d | 2026-01-26T10:10:21+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-01-23 | 90.54 | 0.982156 | 83.333333 | 63.095238 | 0.294062 | 0.174193 | 1.977401 | 0.199203 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20251227&d2=20260126&i=d | 2026-01-26T10:10:21+08:00 |
