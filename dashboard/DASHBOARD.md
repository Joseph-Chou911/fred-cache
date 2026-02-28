# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=2; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@770b64c`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-28T15:33:17.291091+00:00`
- STATS.generated_at_utc: `2026-02-28T02:59:48Z`
- STATS.as_of_ts: `2026-02-28T02:59:48Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-28`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 9 | 10 | OFR_FSI | OK | 12.56 | 2026-02-25 | -2.601 | -0.510445 | 35 | 8.333333 | -0.870551 | -1.192663 | -38.333333 | -10.964164 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-28T02:59:48Z |
| ALERT | EXTREME_Z,JUMP_ZD | NA | LOW | DIR_UNCERTAIN_ABS | WATCH | WATCH→ALERT | 1 | 2 | HYG_IEF_RATIO | OK | 12.56 | 2026-02-27 | 0.823604 | -2.824563 | 1.666667 | 6.349206 | -1.48523 | -0.775298 | 0 | -0.57663 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75 | DERIVED | 2026-02-28T02:59:48Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 10 | 11 | VIX | OK | 12.56 | 2026-02-27 | 19.86 | 1.379544 | 86.666667 | 73.015873 | 0.168007 | 0.537564 | 8.333333 | 6.602254 | abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-28T02:59:48Z |
| WATCH | JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 7 | 8 | SP500 | OK | 12.56 | 2026-02-27 | 6878.88 | -0.230106 | 40 | 84.920635 | 1.02806 | -0.541274 | -15 | -0.433936 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-28T02:59:48Z |
