# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=1 / NONE=1; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@5b36c04`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-02T15:49:57.073937+00:00`
- STATS.generated_at_utc: `2026-02-02T15:12:17Z`
- STATS.as_of_ts: `2026-02-02T15:12:17Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | OFR_FSI | OK | 0.63 | 2026-01-29 | -2.305 | 0.289985 | 73.333333 | 30.555556 | -0.593589 | 0.29484 | 11.666667 | 4.118136 | abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-02T15:12:17Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 3 | 4 | VIX | OK | 0.63 | 2026-01-30 | 17.44 | 0.144392 | 73.333333 | 55.15873 | -0.280306 | 0.211062 | 11.666667 | 3.317536 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-02T15:12:17Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 0.63 | 2026-02-02 | 6969.58 | 1.223232 | 95 | 98.809524 | 1.369667 | 0.262009 | 11.666667 | 0.440263 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-02T15:12:17Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 0.63 | 2026-02-02 | 0.844268 | 1.319015 | 85 | 74.603175 | 0.625391 | -0.269285 | -6.666667 | -0.149089 | NA | DERIVED | 2026-02-02T15:12:17Z |
