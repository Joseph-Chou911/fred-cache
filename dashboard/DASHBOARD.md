# Risk Dashboard (market_cache)

- Summary: ALERT=2 / WATCH=1 / INFO=0 / NONE=1; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@71aefd9`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-26T16:06:24.280997+00:00`
- STATS.generated_at_utc: `2026-02-26T03:20:22Z`
- STATS.as_of_ts: `2026-02-26T03:20:22Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-26`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | JUMP_ZD,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | SAME | 8 | 9 | VIX | OK | 12.77 | 2026-02-25 | 17.93 | 0.526265 | 76.666667 | 59.126984 | -0.206055 | -0.788309 | -8.333333 | -8.286445 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-26T03:20:22Z |
| ALERT | LONG_EXTREME,JUMP_ZD,JUMP_P | NA | HIGH | RISK_BIAS_UP | ALERT | SAME | 5 | 6 | SP500 | OK | 12.77 | 2026-02-25 | 6946.13 | 0.969904 | 85 | 96.428571 | 1.17694 | 0.928478 | 35 | 0.813635 | P252>=95;abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-26T03:20:22Z |
| WATCH | JUMP_P,JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 7 | 8 | OFR_FSI | OK | 12.77 | 2026-02-23 | -2.396 | 0.440205 | 66.666667 | 23.015873 | -0.65446 | 0.620073 | 25 | 5.184013 | abs(PΔ60)>=15;abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-26T03:20:22Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.77 | 2026-02-25 | 0.831304 | -1.480519 | 6.666667 | 22.222222 | -0.63856 | 0.338328 | 3.333333 | 0.217375 | NA | DERIVED | 2026-02-26T03:20:22Z |
