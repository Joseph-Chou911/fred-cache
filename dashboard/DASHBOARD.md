# Risk Dashboard (market_cache)

- Summary: ALERT=1 / WATCH=2 / INFO=1 / NONE=0; CHANGED=2; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@9e0f799`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-11T12:00:41.328680+00:00`
- STATS.generated_at_utc: `2026-02-11T11:59:16Z`
- STATS.as_of_ts: `2026-02-11T11:59:16Z`
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
| ALERT | JUMP_ZD,JUMP_P | NA | LOW | DIR_UNCERTAIN_ABS | NONE | NONE→ALERT | 0 | 1 | HYG_IEF_RATIO | OK | 0.02 | 2026-02-10 | 0.837633 | -0.020512 | 55 | 44.84127 | -0.023078 | -0.802623 | -21.666667 | -0.533621 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | DERIVED | 2026-02-11T11:59:16Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 2 | 3 | OFR_FSI | OK | 0.02 | 2026-02-06 | -2.127 | 0.817668 | 86.666667 | 45.238095 | -0.392149 | -0.555971 | -1.666667 | -10.093168 | abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-11T11:59:16Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 12 | 13 | VIX | OK | 0.02 | 2026-02-10 | 17.79 | 0.293516 | 80 | 57.936508 | -0.229974 | 0.173001 | 6.666667 | 2.476959 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-11T11:59:16Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 0.02 | 2026-02-10 | 6941.81 | 0.836413 | 81.666667 | 95.634921 | 1.253416 | -0.249317 | -8.333333 | -0.330375 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-11T11:59:16Z |
