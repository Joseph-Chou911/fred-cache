# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=4 / INFO=0 / NONE=0; CHANGED=2; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@d96e1fd`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-24T03:16:17.698332+00:00`
- STATS.generated_at_utc: `2026-02-24T03:16:17Z`
- STATS.as_of_ts: `2026-02-24T11:16:14+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-24`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | GLD.US_CLOSE | OK | 0 | 2026-02-23 | 481.29 | 1.777589 | 96.666667 | 99.206349 | 2.461532 | 0.343195 | 1.751412 | 2.732182 | P252>=95;abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260125&d2=20260224&i=d | 2026-02-24T11:16:14+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | INFO | INFO→WATCH | 0 | 1 | IAU.US_CLOSE | OK | 0 | 2026-02-23 | 98.57 | 1.776147 | 96.666667 | 99.206349 | 2.45941 | 0.341262 | 1.751412 | 2.719883 | P252>=95;abs(ret1%1d)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260125&d2=20260224&i=d | 2026-02-24T11:16:14+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 17 | 18 | IYR.US_CLOSE | OK | 0 | 2026-02-23 | 100.51 | 2.23673 | 96.666667 | 99.206349 | 2.410642 | -0.136385 | -1.638418 | -0.029839 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260125&d2=20260224&i=d | 2026-02-24T11:16:14+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 17 | 18 | VNQ.US_CLOSE | OK | 0 | 2026-02-23 | 94.89 | 2.292835 | 98.333333 | 99.603175 | 2.337211 | -0.124277 | 0.028249 | 0.01054 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260125&d2=20260224&i=d | 2026-02-24T11:16:14+08:00 |
