# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=0 / NONE=4; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@437f4a2`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-16T15:54:27.949438+00:00`
- STATS.generated_at_utc: `2026-02-16T03:31:51Z`
- STATS.as_of_ts: `2026-02-16T03:31:51Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1% (1D) = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.38 | 2026-02-13 | 0.831705 | -1.141085 | 15 | 21.825397 | -0.63325 | -0.492433 | -6.666667 | -0.31693 | NA | DERIVED | 2026-02-16T03:31:51Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | OFR_FSI | OK | 12.38 | 2026-02-11 | -2.305 | 0.46194 | 76.666667 | 31.746032 | -0.585896 | -0.002035 | -5 | -1.096491 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-16T03:31:51Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | SP500 | OK | 12.38 | 2026-02-13 | 6836.17 | -0.301766 | 31.666667 | 80.952381 | 1.017115 | -0.002466 | 1.666667 | 0.049907 | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-16T03:31:51Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | VIX | OK | 12.38 | 2026-02-13 | 20.6 | 1.618929 | 93.333333 | 76.190476 | 0.29399 | 0.005399 | 0 | -1.056676 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-16T03:31:51Z |
