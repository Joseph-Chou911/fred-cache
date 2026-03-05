# Risk Dashboard (market_cache)

- Summary: ALERT=3 / WATCH=1 / INFO=0 / NONE=0; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@07af7f8`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-05T16:01:17.324766+00:00`
- STATS.generated_at_utc: `2026-03-05T03:16:43Z`
- STATS.as_of_ts: `2026-03-05T03:16:43Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-05`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | NONE | NONE→ALERT | 0 | 1 | OFR_FSI | OK | 12.74 | 2026-03-02 | -1.893 | 2.584326 | 100 | 61.111111 | -0.062937 | 2.107753 | 31.666667 | 20.662196 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-05T03:16:43Z |
| ALERT | JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 15 | 16 | VIX | OK | 12.74 | 2026-03-04 | 21.15 | 1.636378 | 93.333333 | 81.349206 | 0.427611 | -1.105828 | -6.666667 | -10.267289 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-05T03:16:43Z |
| ALERT | JUMP_ZD,JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 12 | 13 | SP500 | OK | 12.74 | 2026-03-04 | 6869.5 | -0.404801 | 31.666667 | 82.539683 | 0.98661 | 0.92426 | 20 | 0.775603 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-05T03:16:43Z |
| WATCH | JUMP_ZD | NA | LOW | DIR_UNCERTAIN_ABS | WATCH | SAME | 6 | 7 | HYG_IEF_RATIO | OK | 12.74 | 2026-03-04 | 0.830493 | -1.334303 | 11.666667 | 22.222222 | -0.692286 | 0.879225 | 8.333333 | 0.567154 | abs(ZΔ60)>=0.75 | DERIVED | 2026-03-05T03:16:43Z |
