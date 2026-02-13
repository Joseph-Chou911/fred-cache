# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=0 / WATCH=4 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@97751d7`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-13T17:08:40.734977+00:00`
- STATS.generated_at_utc: `2026-02-13T17:08:40Z`
- STATS.as_of_ts: `2026-02-14T01:08:37+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- metric_defs: ZΔ60 = z60(today) - z60(yesterday); PΔ60 = p60(today) - p60(yesterday) (units: percentile points); ret1% (1D) = (today - prev)/abs(prev) * 100
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_poschg60 | p_poschg60 | ret1_pct1d_absPrev | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | LONG_EXTREME,JUMP_RET | NEAR:PΔ60 | MOVE | MOVE_ONLY | WATCH | SAME | 1 | 2 | GLD.US_CLOSE | OK | 0 | 2026-02-12 | 451.39 | 1.113112 | 80 | 95.238095 | 2.088307 | -0.528594 | -14.915254 | -3.472831 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260114&d2=20260213&i=d | 2026-02-14T01:08:37+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NEAR:PΔ60 | MOVE | MOVE_ONLY | WATCH | SAME | 1 | 2 | IAU.US_CLOSE | OK | 0 | 2026-02-12 | 92.48 | 1.118722 | 80 | 95.238095 | 2.090848 | -0.519924 | -14.915254 | -3.414787 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260114&d2=20260213&i=d | 2026-02-14T01:08:37+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 7 | 8 | IYR.US_CLOSE | OK | 0 | 2026-02-12 | 98.87 | 2.423912 | 96.666667 | 98.412698 | 1.805668 | -0.206754 | -1.638418 | -0.075811 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260114&d2=20260213&i=d | 2026-02-14T01:08:37+08:00 |
| WATCH | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | WATCH | SAME | 7 | 8 | VNQ.US_CLOSE | OK | 0 | 2026-02-12 | 93.25 | 2.480829 | 96.666667 | 98.015873 | 1.680363 | -0.226079 | -1.638418 | -0.08569 | abs(Z60)>=2;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260114&d2=20260213&i=d | 2026-02-14T01:08:37+08:00 |
