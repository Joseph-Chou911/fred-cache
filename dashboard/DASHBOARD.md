# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=1 / INFO=0 / NONE=1; CHANGED=0; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@10cd14a`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-03-10T16:12:26.123998+00:00`
- STATS.generated_at_utc: `2026-03-10T03:14:01Z`
- STATS.as_of_ts: `2026-03-10T03:14:01Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-03-10`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 20 | 21 | VIX | OK | 12.97 | 2026-03-09 | 25.5 | 2.491418 | 98.333333 | 93.253968 | 1.243051 | -1.531044 | -1.666667 | -13.53001 | abs(Z60)>=2;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-03-10T03:14:01Z |
| ALERT | EXTREME_Z,JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 5 | 6 | OFR_FSI | OK | 12.97 | 2026-03-05 | -1.574 | 2.665349 | 98.333333 | 76.190476 | 0.296882 | -1.502976 | -1.666667 | -32.268908 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-03-10T03:14:01Z |
| WATCH | JUMP_ZD | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 17 | 18 | SP500 | OK | 12.97 | 2026-03-09 | 6795.99 | -1.526765 | 6.666667 | 70.238095 | 0.822438 | 0.96326 | 3.333333 | 0.830413 | abs(ZΔ60)>=0.75 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-03-10T03:14:01Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.97 | 2026-03-09 | 0.828613 | -1.485694 | 10 | 15.873016 | -0.883537 | 0.463611 | 5 | 0.293444 | NA | DERIVED | 2026-03-10T03:14:01Z |
