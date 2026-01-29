# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=1 / NONE=3; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@7b73349`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-01-29T17:09:56.543797+00:00`
- STATS.generated_at_utc: `2026-01-29T04:58:52Z`
- STATS.as_of_ts: `2026-01-29T04:58:52Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 12.18 | 2026-01-28 | 6978.03 | 1.418011 | 98.333333 | 99.603175 | 1.422422 | -0.057435 | -1.666667 | -0.008168 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-29T04:58:52Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.18 | 2026-01-28 | 0.845047 | 1.621122 | 90 | 76.587302 | 0.67593 | -0.190136 | -5 | -0.076871 | NA | DERIVED | 2026-01-29T04:58:52Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | OFR_FSI | OK | 12.18 | 2026-01-26 | -2.478 | -0.237546 | 45 | 11.904762 | -0.795053 | 0.078939 | 3.333333 | 1.077844 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-29T04:58:52Z |
| NONE | NA | NA | HIGH | NA | NONE | SAME | 0 | 0 | VIX | OK | 12.18 | 2026-01-28 | 16.35 | -0.274916 | 50 | 33.730159 | -0.483265 | 0.005219 | 1.666667 | 0 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-29T04:58:52Z |
