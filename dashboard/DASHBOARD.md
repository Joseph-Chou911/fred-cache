# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=1 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@12642dc`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-04T15:57:26.161077+00:00`
- STATS.generated_at_utc: `2026-03-04T03:13:42Z`
- STATS.as_of_ts: `2026-03-04T03:13:42Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-04`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_RET | NEAR:ZΔ60 | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 14 | 15 | VIX | OK | 12.73 | 2026-03-03 | 23.57 | 2.742206 | 100 | 88.888889 | 0.889178 | 0.729765 | 1.666667 | 9.934701 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-04T03:13:42Z |
| ALERT | JUMP_ZD,JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 11 | 12 | SP500 | OK | 12.73 | 2026-03-03 | 6816.63 | -1.329061 | 11.666667 | 74.206349 | 0.890927 | -1.129805 | -30 | -0.9444 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-04T03:13:42Z |
| WATCH | EXTREME_Z | NA | LOW | DIR_UNCERTAIN_ABS | WATCH | SAME | 5 | 6 | HYG_IEF_RATIO | OK | 12.73 | 2026-03-03 | 0.825809 | -2.213528 | 3.333333 | 9.126984 | -1.218639 | -0.056297 | 0 | -0.096436 | abs(Z60)>=2 | DERIVED | 2026-03-04T03:13:42Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | OFR_FSI | OK | 12.73 | 2026-02-27 | -2.386 | 0.476573 | 68.333333 | 25.396825 | -0.618947 | 0.118598 | 6.666667 | 1.159901 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-04T03:13:42Z |
