# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=0 / NONE=2; CHANGED=1; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@e51a55a`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-20T15:50:54.625119+00:00`
- STATS.generated_at_utc: `2026-02-20T03:19:37Z`
- STATS.as_of_ts: `2026-02-20T03:19:37Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-20`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 2 | 3 | VIX | OK | 12.52 | 2026-02-19 | 20.23 | 1.827209 | 91.666667 | 73.412698 | 0.221896 | 0.267735 | 1.666667 | 3.109072 | abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-20T03:19:37Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 1 | 2 | OFR_FSI | OK | 12.52 | 2026-02-17 | -2.294 | 0.846784 | 80 | 32.936508 | -0.562986 | -0.260781 | -8.333333 | -3.800905 | abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-20T03:19:37Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 1 | 0 | SP500 | OK | 12.52 | 2026-02-19 | 6861.89 | -0.222387 | 41.666667 | 84.920635 | 1.044795 | -0.321019 | -6.666667 | -0.282214 | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-20T03:19:37Z |
| NONE | NA | NA | LOW | NA | NONE | SAME | 0 | 0 | HYG_IEF_RATIO | OK | 12.52 | 2026-02-19 | 0.833745 | -0.868413 | 18.333333 | 29.365079 | -0.393498 | -0.120133 | -1.666667 | -0.045359 | NA | DERIVED | 2026-02-20T03:19:37Z |
