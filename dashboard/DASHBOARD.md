# Risk Dashboard (market_cache)

- Summary: ALERT=1 / WATCH=2 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@bde1fcd`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-23T15:58:45.435570+00:00`
- STATS.generated_at_utc: `2026-02-23T03:31:04Z`
- STATS.as_of_ts: `2026-02-23T03:31:04Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-23`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 4 | 5 | OFR_FSI | OK | 12.46 | 2026-02-18 | -2.505 | -0.08811 | 43.333333 | 11.507937 | -0.792411 | -0.934894 | -36.666667 | -9.197908 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-23T03:31:04Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 5 | 6 | VIX | OK | 12.46 | 2026-02-20 | 19.09 | 1.21002 | 86.666667 | 67.857143 | 0.006636 | -0.617189 | -5 | -5.635195 | abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-23T03:31:04Z |
| WATCH | JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 2 | 3 | SP500 | OK | 12.46 | 2026-02-20 | 6909.51 | 0.405832 | 58.333333 | 90.079365 | 1.130397 | 0.628219 | 16.666667 | 0.693978 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-23T03:31:04Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.46 | 2026-02-20 | 0.834277 | -0.817965 | 20 | 30.555556 | -0.327846 | 0.066572 | 1.666667 | 0.074129 | NA | DERIVED | 2026-02-23T03:31:04Z |
