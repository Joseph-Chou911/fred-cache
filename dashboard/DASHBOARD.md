# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=0 / NONE=3; CHANGED=1; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@17d0d33`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-18T00:38:05.256141+00:00`
- STATS.generated_at_utc: `2026-02-17T08:06:20Z`
- STATS.as_of_ts: `2026-02-17T08:06:20Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-17`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | OFR_FSI | OK | 16.53 | 2026-02-12 | -2.138 | 1.095628 | 90 | 44.84127 | -0.397527 | 0.633688 | 13.333333 | 7.245119 | abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-17T08:06:20Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 16.53 | 2026-02-13 | 0.831705 | -1.141085 | 15 | 21.825397 | -0.63325 | -0.492433 | -6.666667 | -0.31693 | NA | DERIVED | 2026-02-17T08:06:20Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | SP500 | OK | 16.53 | 2026-02-13 | 6836.17 | -0.301766 | 31.666667 | 80.952381 | 1.017115 | -0.002466 | 1.666667 | 0.049907 | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-17T08:06:20Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | VIX | OK | 16.53 | 2026-02-13 | 20.6 | 1.618929 | 93.333333 | 76.190476 | 0.29399 | 0.005399 | 0 | -1.056676 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-17T08:06:20Z |
