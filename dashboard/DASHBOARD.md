# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=0 / NONE=3; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@df3685b`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-18T13:41:01.762465+00:00`
- STATS.generated_at_utc: `2026-02-18T13:34:48Z`
- STATS.as_of_ts: `2026-02-18T13:34:48Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-18`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | VIX | OK | 0.1 | 2026-02-17 | 20.29 | 1.87704 | 91.666667 | 73.809524 | 0.232918 | -0.292074 | -5 | -4.292453 | abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-18T13:34:48Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 1 | 0 | OFR_FSI | OK | 0.1 | 2026-02-13 | -2.115 | 1.369231 | 95 | 47.619048 | -0.369914 | 0.273603 | 5 | 1.075772 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-18T13:34:48Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 0.1 | 2026-02-17 | 0.831379 | -1.226147 | 13.333333 | 21.428571 | -0.662568 | -0.085063 | -1.666667 | -0.039191 | NA | DERIVED | 2026-02-18T13:34:48Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | SP500 | OK | 0.1 | 2026-02-17 | 6843.22 | -0.283874 | 33.333333 | 81.746032 | 1.023602 | 0.017892 | 1.666667 | 0.103128 | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-18T13:34:48Z |
