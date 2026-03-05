# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=4 / NONE=0; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@d14548d`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-05T03:10:48.767720+00:00`
- STATS.generated_at_utc: `2026-03-05T03:10:48Z`
- STATS.as_of_ts: `2026-03-05T11:10:44+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-05`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | WATCH→INFO | 1 | 0 | GLD.US_CLOSE | OK | 0 | 2026-03-04 | 471.76 | 1.124599 | 85 | 96.428571 | 2.088586 | 0.087 | 1.949153 | 0.756055 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260203&d2=20260305&i=d | 2026-03-05T11:10:44+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | WATCH→INFO | 1 | 0 | IAU.US_CLOSE | OK | 0 | 2026-03-04 | 96.65 | 1.12823 | 85 | 96.428571 | 2.089665 | 0.087568 | 1.949153 | 0.761051 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260203&d2=20260305&i=d | 2026-03-05T11:10:44+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-03-04 | 101.06 | 1.73974 | 95 | 98.809524 | 2.43667 | -0.016283 | 1.779661 | 0.113923 | P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260203&d2=20260305&i=d | 2026-03-05T11:10:44+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-03-04 | 95.54 | 1.798481 | 96.666667 | 99.206349 | 2.466377 | -0.016861 | 3.446328 | 0.12576 | P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260203&d2=20260305&i=d | 2026-03-05T11:10:44+08:00 |
