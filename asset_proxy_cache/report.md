# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=0 / NONE=2; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@604a732`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-13T09:00:01.285928+00:00`
- STATS.generated_at_utc: `2026-03-13T09:00:01Z`
- STATS.as_of_ts: `2026-03-13T16:59:57+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-13`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P | NEAR:ret1%1d | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | GLD.US_CLOSE | OK | 0 | 2026-03-12 | 466.88 | 0.77645 | 70 | 92.857143 | 1.875688 | -0.31407 | -18.135593 | -1.944398 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=gld.us&d1=20260211&d2=20260313&i=d | 2026-03-13T16:59:57+08:00 |
| WATCH | JUMP_P | NEAR:ret1%1d | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | IAU.US_CLOSE | OK | 0 | 2026-03-12 | 95.65 | 0.78016 | 71.666667 | 93.253968 | 1.87688 | -0.311437 | -16.468927 | -1.927217 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=iau.us&d1=20260211&d2=20260313&i=d | 2026-03-13T16:59:57+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-03-12 | 97.32 | 0.141429 | 60 | 83.333333 | 0.784104 | -0.26006 | -2.711864 | -0.693807 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20260211&d2=20260313&i=d | 2026-03-13T16:59:57+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-03-12 | 92.01 | 0.175998 | 60 | 84.126984 | 0.825886 | -0.27057 | -6.101695 | -0.717755 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20260211&d2=20260313&i=d | 2026-03-13T16:59:57+08:00 |
