# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@704b725`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-18T03:19:39.692083+00:00`
- STATS.generated_at_utc: `2026-02-18T03:19:39Z`
- STATS.as_of_ts: `2026-02-18T11:19:36+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-18`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 11 | 12 | IYR.US_CLOSE | OK | 0 | 2026-02-17 | 101.21 | 3.27825 | 100 | 100 | 2.881876 | 0.249383 | 0 | 0.977751 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260119&d2=20260218&i=d | 2026-02-18T11:19:36+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 11 | 12 | VNQ.US_CLOSE | OK | 0 | 2026-02-17 | 95.5 | 3.332594 | 100 | 100 | 2.73604 | 0.232802 | 0 | 0.962047 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260119&d2=20260218&i=d | 2026-02-18T11:19:36+08:00 |
| WATCH | JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 5 | 6 | GLD.US_CLOSE | OK | 0 | 2026-02-17 | 448.23 | 0.935359 | 76.666667 | 94.444444 | 1.979372 | -0.465746 | -13.163842 | -3.10845 | abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260119&d2=20260218&i=d | 2026-02-18T11:19:36+08:00 |
| WATCH | JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 5 | 6 | IAU.US_CLOSE | OK | 0 | 2026-02-17 | 91.82 | 0.937521 | 76.666667 | 94.444444 | 1.97999 | -0.463092 | -13.163842 | -3.092348 | abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260119&d2=20260218&i=d | 2026-02-18T11:19:36+08:00 |
