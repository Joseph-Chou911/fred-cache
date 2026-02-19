# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@bc96e9b`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-19T09:06:09.474994+00:00`
- STATS.generated_at_utc: `2026-02-19T09:06:09Z`
- STATS.as_of_ts: `2026-02-19T17:06:06+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-19`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,LONG_EXTREME,JUMP_ZD | NA | MOVE | MOVE_ONLY | ALERT | SAME | 12 | 13 | IYR.US_CLOSE | OK | 0 | 2026-02-18 | 100.01 | 2.410914 | 96.666667 | 99.206349 | 2.26727 | -0.849177 | -3.333333 | -1.185654 | abs(Z60)>=2;P252>=95;abs(ZΔ60)>=0.75 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260120&d2=20260219&i=d | 2026-02-19T17:06:06+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME,JUMP_ZD | NA | MOVE | MOVE_ONLY | ALERT | SAME | 12 | 13 | VNQ.US_CLOSE | OK | 0 | 2026-02-18 | 94.37 | 2.450017 | 96.666667 | 99.206349 | 2.149486 | -0.8689 | -3.333333 | -1.183246 | abs(Z60)>=2;P252>=95;abs(ZΔ60)>=0.75 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260120&d2=20260219&i=d | 2026-02-19T17:06:06+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 6 | 7 | GLD.US_CLOSE | OK | 0 | 2026-02-18 | 458.28 | 1.211263 | 86.666667 | 96.825397 | 2.138323 | 0.292049 | 10.39548 | 2.242152 | P252>=95;abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260120&d2=20260219&i=d | 2026-02-19T17:06:06+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 6 | 7 | IAU.US_CLOSE | OK | 0 | 2026-02-18 | 93.85 | 1.208898 | 86.666667 | 96.825397 | 2.136129 | 0.287501 | 10.39548 | 2.210847 | P252>=95;abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260120&d2=20260219&i=d | 2026-02-19T17:06:06+08:00 |
