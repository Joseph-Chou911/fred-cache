# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=2 / NONE=0; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@786e81b`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-04T08:57:55.487021+00:00`
- STATS.generated_at_utc: `2026-03-04T08:57:55Z`
- STATS.as_of_ts: `2026-03-04T16:57:52+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-04`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | LONG_EXTREME,JUMP_RET | NEAR:ZΔ60 | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | GLD.US_CLOSE | OK | 0 | 2026-03-03 | 468.14 | 1.052399 | 83.333333 | 96.031746 | 2.051884 | -0.682791 | -13.276836 | -4.440998 | P252>=95;abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260202&d2=20260304&i=d | 2026-03-04T16:57:52+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NEAR:ZΔ60 | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | IAU.US_CLOSE | OK | 0 | 2026-03-03 | 95.92 | 1.055425 | 83.333333 | 96.031746 | 2.052679 | -0.680282 | -13.276836 | -4.424073 | P252>=95;abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260202&d2=20260304&i=d | 2026-03-04T16:57:52+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | WATCH→INFO | 5 | 0 | IYR.US_CLOSE | OK | 0 | 2026-03-03 | 100.96 | 1.775052 | 93.333333 | 98.412698 | 2.408218 | -0.296842 | -6.666667 | -0.566391 | P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260202&d2=20260304&i=d | 2026-03-04T16:57:52+08:00 |
| INFO | LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | WATCH→INFO | 25 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-03-03 | 95.42 | 1.835158 | 93.333333 | 98.412698 | 2.42546 | -0.289891 | -6.666667 | -0.531638 | P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260202&d2=20260304&i=d | 2026-03-04T16:57:52+08:00 |
