# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=1 / NONE=1; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@725289e`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-19T07:53:51.771883+00:00`
- STATS.generated_at_utc: `2026-01-19T07:35:30Z`
- STATS.as_of_ts: `2026-01-19T07:35:30Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | EXTREME_Z | NEAR:ZΔ60 | LOW | DIR_UNCERTAIN_ABS | NA | NA | 0 | 1 | HYG_IEF_RATIO | OK | 0.31 | 2026-01-16 | 0.845304 | 2.464967 | 77.777778 | 0.743865 | 1.666667 | 0.447634 | abs(Z60)>=2 | DERIVED | 2026-01-19T07:35:30Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NA | NA | 0 | 1 | OFR_FSI | OK | 0.31 | 2026-01-14 | -2.626 | -0.709121 | 6.746032 | 0.278718 | 13.333333 | 3.278085 | abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-19T07:35:30Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | NA | NA | 0 | 0 | SP500 | OK | 0.31 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | -0.088684 | -1.666667 | -0.064224 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-19T07:35:30Z |
| NONE | NA | NA | HIGH | NA | NA | NA | 0 | 0 | VIX | OK | 0.31 | 2026-01-16 | 15.86 | -0.450183 | 25.793651 | 0.024178 | 1.666667 | 0.126263 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-19T07:35:30Z |
