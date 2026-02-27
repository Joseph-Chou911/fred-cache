# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=4 / INFO=0 / NONE=0; CHANGED=3; WATCH_STREAK>=3=3
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@c61b139`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-27T02:53:43.736574+00:00`
- STATS.generated_at_utc: `2026-02-27T02:52:55Z`
- STATS.as_of_ts: `2026-02-27T02:52:55Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline; Fail-open if today_day missing (no same-day exclusion)`
- today_day: `2026-02-27`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%1d)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1%1d = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting
- deprecated_fields: `ret1_pct60 (legacy alias of ret1_pct1d_absPrev); z_delta60/p_delta60 (legacy; use z_poschg60/p_poschg60)`

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 9 | 10 | VIX | OK | 0.01 | 2026-02-26 | 18.63 | 0.841981 | 78.333333 | 65.47619 | -0.068748 | 0.315716 | 1.666667 | 3.904071 | abs(ret1%1d)>=2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-27T02:52:55Z |
| WATCH | JUMP_P | NA | HIGH | DIR_UNCERTAIN_ABS | ALERT | ALERT→WATCH | 6 | 7 | SP500 | OK | 0.01 | 2026-02-26 | 6908.86 | 0.311168 | 55 | 89.285714 | 1.094987 | -0.658736 | -30 | -0.536558 | abs(PΔ60)>=15 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-27T02:52:55Z |
| WATCH | EXTREME_Z | NA | LOW | DIR_UNCERTAIN_ABS | NONE | NONE→WATCH | 0 | 1 | HYG_IEF_RATIO | OK | 0.01 | 2026-02-26 | 0.828381 | -2.049264 | 1.666667 | 13.492063 | -0.96058 | -0.570447 | -5 | -0.352668 | abs(Z60)>=2 | DERIVED | 2026-02-27T02:52:55Z |
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 8 | 9 | OFR_FSI | OK | 0.01 | 2026-02-24 | -2.344 | 0.682219 | 73.333333 | 28.571429 | -0.591345 | 0.242013 | 6.666667 | 2.170284 | abs(ret1%1d)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-27T02:52:55Z |
