# Risk Dashboard (market_cache)

- Summary: ALERT=3 / WATCH=0 / INFO=0 / NONE=1; CHANGED=4; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@29f2b8d`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-13T04:02:02.485214+00:00`
- STATS.generated_at_utc: `2026-02-13T03:32:32Z`
- STATS.as_of_ts: `2026-02-13T03:32:32Z`
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
| ALERT | JUMP_ZD,JUMP_P | NA | LOW | DIR_UNCERTAIN_ABS | NONE | NONE→ALERT | 0 | 1 | HYG_IEF_RATIO | OK | 0.49 | 2026-02-12 | 0.834263 | -0.663787 | 21.666667 | 28.968254 | -0.366673 | -1.015809 | -43.333333 | -0.668759 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | DERIVED | 2026-02-13T03:32:32Z |
| ALERT | JUMP_ZD,JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | INFO | INFO→ALERT | 0 | 1 | SP500 | OK | 0.49 | 2026-02-12 | 6832.76 | -0.2993 | 30 | 80.555556 | 1.018038 | -1.103946 | -50 | -1.566095 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-13T03:32:32Z |
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→ALERT | 0 | 1 | VIX | OK | 0.49 | 2026-02-12 | 20.82 | 1.61353 | 93.333333 | 78.571429 | 0.337456 | 1.33325 | 15 | 17.96034 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-13T03:32:32Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 4 | 0 | OFR_FSI | OK | 0.49 | 2026-02-10 | -2.28 | 0.463975 | 81.666667 | 33.730159 | -0.560256 | -0.023826 | -1.666667 | -1.333333 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-13T03:32:32Z |
