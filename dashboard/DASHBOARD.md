# Risk Dashboard (market_cache)

- Summary: ALERT=0 / WATCH=1 / INFO=1 / NONE=2; CHANGED=2; WATCH_STREAK>=3=1
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@e78b3ab`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-12T06:24:26.364869+00:00`
- STATS.generated_at_utc: `2026-02-12T06:23:58Z`
- STATS.as_of_ts: `2026-02-12T06:23:58Z`
- script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- stale_hours: `36.0`
- stats_path: `market_cache/stats_latest.json`
- dash_history: `dashboard/history.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1% (1D) = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | HIGH | DIR_UNCERTAIN_ABS | WATCH | SAME | 3 | 4 | OFR_FSI | OK | 0.01 | 2026-02-09 | -2.25 | 0.487802 | 83.333333 | 36.507937 | -0.528616 | -0.329866 | -3.333333 | -5.782793 | abs(ret1%60)>=2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-02-12T06:23:58Z |
| INFO | LONG_EXTREME | NA | HIGH | RISK_BIAS_UP | INFO | SAME | 0 | 0 | SP500 | OK | 0.01 | 2026-02-11 | 6941.47 | 0.804646 | 80 | 95.238095 | 1.242566 | -0.031767 | -1.666667 | -0.004898 | P252>=95 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-12T06:23:58Z |
| NONE | NA | NA | LOW | NA | ALERT | ALERT→NONE | 1 | 0 | HYG_IEF_RATIO | OK | 0.01 | 2026-02-11 | 0.839879 | 0.352022 | 65 | 51.984127 | 0.219716 | 0.372534 | 10 | 0.268144 | NA | DERIVED | 2026-02-12T06:23:58Z |
| NONE | NA | NA | HIGH | NA | WATCH | WATCH→NONE | 13 | 0 | VIX | OK | 0.01 | 2026-02-11 | 17.65 | 0.28028 | 78.333333 | 56.349206 | -0.258438 | -0.013236 | -1.666667 | -0.786959 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-12T06:23:58Z |
