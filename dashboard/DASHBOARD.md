# Risk Dashboard (market_cache)

- Summary: ALERT=3 / WATCH=0 / INFO=0 / NONE=1; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@f34a547`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-25T02:07:48.127708+00:00`
- STATS.generated_at_utc: `2026-02-25T02:07:15Z`
- STATS.as_of_ts: `2026-02-25T02:07:15Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-25`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 6 | 7 | OFR_FSI | OK | 0.01 | 2026-02-20 | -2.527 | -0.179868 | 41.666667 | 10.31746 | -0.80562 | -0.779221 | -30 | -7.121662 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-25T02:07:15Z |
| ALERT | JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 7 | 8 | VIX | OK | 0.01 | 2026-02-24 | 19.55 | 1.314574 | 85 | 70.238095 | 0.098171 | -0.760098 | -11.666667 | -6.949072 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-25T02:07:15Z |
| ALERT | JUMP_ZD,JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 4 | 5 | SP500 | OK | 0.01 | 2026-02-24 | 6890.07 | 0.041426 | 50 | 87.301587 | 1.076255 | 0.833342 | 25 | 0.765164 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-25T02:07:15Z |
| NONE | NA | NA | LOW | NA | ALERT | ALERT→NONE | 2 | 0 | HYG_IEF_RATIO | OK | 0.01 | 2026-02-24 | 0.829629 | -1.79459 | 3.333333 | 17.460317 | -0.833152 | -0.07881 | -1.666667 | -0.038287 | NA | DERIVED | 2026-02-25T02:07:15Z |
