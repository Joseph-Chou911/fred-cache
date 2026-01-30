# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=1 / NONE=2; CHANGED=1; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@4cd7fa5`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-30T23:42:08.126628+00:00`
- STATS.generated_at_utc: `2026-01-30T23:37:59Z`
- STATS.as_of_ts: `2026-01-30T23:37:59Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | VIX | OK | 0.07 | 2026-01-29 | 16.88 | -0.06667 | 61.666667 | 46.825397 | -0.384879 | 0.208246 | 11.666667 | 3.24159 | abs(ret1%60)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-30T23:37:59Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 0.07 | 2026-01-30 | 6939.03 | 0.961222 | 83.333333 | 96.031746 | 1.319331 | -0.324261 | -11.666667 | -0.43019 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-30T23:37:59Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 0.07 | 2026-01-30 | 0.845532 | 1.588936 | 91.666667 | 79.761905 | 0.744 | 0.199092 | 5 | 0.17413 | NA | DERIVED | 2026-01-30T23:37:59Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | OFR_FSI | OK | 0.07 | 2026-01-28 | -2.404 | -0.004855 | 61.666667 | 21.031746 | -0.706048 | -0.045013 | -3.333333 | -0.881242 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-30T23:37:59Z |
