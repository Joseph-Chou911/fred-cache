# Risk Dashboard (market_cache)

- Summary: ALERT=1 / WATCH=1 / INFO=1 / NONE=1; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@a5970e4`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-10T16:16:39.567619+00:00`
- STATS.generated_at_utc: `2026-02-10T04:42:44Z`
- STATS.as_of_ts: `2026-02-10T04:42:44Z`
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
| ALERT | JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 1 | 2 | OFR_FSI | OK | 11.57 | 2026-02-05 | -1.932 | 1.373638 | 88.333333 | 53.968254 | -0.174016 | 1.021995 | 11.666667 | 15.816993 | abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-10T04:42:44Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 11 | 12 | VIX | OK | 11.57 | 2026-02-09 | 17.36 | 0.120514 | 73.333333 | 52.380952 | -0.309144 | -0.128473 | -3.333333 | -2.252252 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-10T04:42:44Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 11.57 | 2026-02-09 | 6964.82 | 1.085729 | 90 | 97.619048 | 1.309962 | 0.296466 | 10 | 0.469108 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-10T04:42:44Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 11.57 | 2026-02-09 | 0.842127 | 0.782111 | 76.666667 | 67.460317 | 0.440756 | 0.142694 | 5 | 0.11528 | NA | DERIVED | 2026-02-10T04:42:44Z |
