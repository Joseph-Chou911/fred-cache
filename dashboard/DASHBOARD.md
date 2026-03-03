# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=1 / INFO=0 / NONE=1; CHANGED=3; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@614e295`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-03T15:58:41.805659+00:00`
- STATS.generated_at_utc: `2026-03-03T03:21:44Z`
- STATS.as_of_ts: `2026-03-03T03:21:44Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-03`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 13 | 14 | VIX | OK | 12.62 | 2026-03-02 | 21.44 | 2.012441 | 98.333333 | 81.746032 | 0.476199 | 0.632897 | 11.666667 | 7.95569 | abs(Z60)>=2;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-03T03:21:44Z |
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 12 | 13 | OFR_FSI | OK | 12.62 | 2026-02-26 | -2.414 | 0.357975 | 61.666667 | 21.031746 | -0.655865 | 0.86842 | 26.666667 | 7.189542 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-03T03:21:44Z |
| WATCH | EXTREME_Z | NEAR:ZΔ60 | LOW | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 4 | 5 | HYG_IEF_RATIO | OK | 12.62 | 2026-03-02 | 0.826837 | -2.118115 | 3.333333 | 10.31746 | -1.113328 | 0.68131 | 1.666667 | 0.373824 | abs(Z60)>=2 | DERIVED | 2026-03-03T03:21:44Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 10 | 0 | SP500 | OK | 12.62 | 2026-03-02 | 6881.62 | -0.199256 | 41.666667 | 85.31746 | 1.025253 | 0.03085 | 1.666667 | 0.039832 | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-03T03:21:44Z |
