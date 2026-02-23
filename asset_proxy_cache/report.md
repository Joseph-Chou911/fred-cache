# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=2 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@f9dd299`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-23T03:21:19.903033+00:00`
- STATS.generated_at_utc: `2026-02-23T03:21:19Z`
- STATS.as_of_ts: `2026-02-23T11:21:17+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-23`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 16 | 17 | IYR.US_CLOSE | OK | 0 | 2026-02-20 | 100.54 | 2.396595 | 98.333333 | 99.603175 | 2.456857 | 0.234263 | 3.418079 | 0.711209 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260124&d2=20260223&i=d | 2026-02-23T11:21:17+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 16 | 17 | VNQ.US_CLOSE | OK | 0 | 2026-02-20 | 94.88 | 2.440964 | 98.333333 | 99.603175 | 2.355702 | 0.257796 | 3.418079 | 0.753956 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260124&d2=20260223&i=d | 2026-02-23T11:21:17+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1%1d | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | GLD.US_CLOSE | OK | 0 | 2026-02-20 | 468.62 | 1.446889 | 95 | 98.809524 | 2.26755 | 0.245077 | 8.559322 | 1.932073 | P252>=95 | https://stooq.com/q/d/l/?s=gld.us&d1=20260124&d2=20260223&i=d | 2026-02-23T11:21:17+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1%1d | MOVE | MOVE_ONLY | INFO | SAME | 0 | 0 | IAU.US_CLOSE | OK | 0 | 2026-02-20 | 95.95 | 1.447321 | 95 | 98.809524 | 2.266785 | 0.248163 | 8.559322 | 1.954951 | P252>=95 | https://stooq.com/q/d/l/?s=iau.us&d1=20260124&d2=20260223&i=d | 2026-02-23T11:21:17+08:00 |
