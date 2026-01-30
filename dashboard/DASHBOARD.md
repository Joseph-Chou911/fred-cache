# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=1 / NONE=1; CHANGED=2; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@03d6f30`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-30T17:08:48.297983+00:00`
- STATS.generated_at_utc: `2026-01-30T05:01:20Z`
- STATS.as_of_ts: `2026-01-30T05:01:20Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | OFR_FSI | OK | 12.12 | 2026-01-27 | -2.383 | 0.040159 | 65 | 23.015873 | -0.68567 | 0.277705 | 20 | 3.833737 | abs(PΔ60)>=15;abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-30T05:01:20Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | VIX | OK | 12.12 | 2026-01-29 | 16.88 | -0.06667 | 61.666667 | 46.825397 | -0.384879 | 0.208246 | 11.666667 | 3.24159 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-30T05:01:20Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 12.12 | 2026-01-29 | 6969.01 | 1.285483 | 95 | 98.809524 | 1.391756 | -0.132528 | -3.333333 | -0.129263 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-30T05:01:20Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.12 | 2026-01-29 | 0.844063 | 1.389845 | 86.666667 | 73.412698 | 0.586407 | -0.231278 | -3.333333 | -0.116493 | NA | DERIVED | 2026-01-30T05:01:20Z |
