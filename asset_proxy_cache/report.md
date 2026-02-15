# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=2
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@4881452`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-15T03:24:04.464239+00:00`
- STATS.generated_at_utc: `2026-02-15T03:24:04Z`
- STATS.as_of_ts: `2026-02-15T11:24:01+08:00`
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
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 8 | 9 | IYR.US_CLOSE | OK | 0 | 2026-02-13 | 100.22 | 3.056286 | 100 | 100 | 2.454252 | 0.653107 | 3.389831 | 1.390926 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260116&d2=20260215&i=d | 2026-02-15T11:24:01+08:00 |
| ALERT | EXTREME_Z,LONG_EXTREME | NA | MOVE | MOVE_ONLY | ALERT | SAME | 8 | 9 | VNQ.US_CLOSE | OK | 0 | 2026-02-13 | 94.59 | 3.126272 | 100 | 100 | 2.318735 | 0.664912 | 3.389831 | 1.404374 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260116&d2=20260215&i=d | 2026-02-15T11:24:01+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 2 | 3 | GLD.US_CLOSE | OK | 0 | 2026-02-13 | 462.62 | 1.414073 | 90 | 97.619048 | 2.266952 | 0.315672 | 10.338983 | 2.485655 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260116&d2=20260215&i=d | 2026-02-15T11:24:01+08:00 |
| WATCH | LONG_EXTREME,JUMP_RET | NA | MOVE | MOVE_ONLY | WATCH | SAME | 2 | 3 | IAU.US_CLOSE | OK | 0 | 2026-02-13 | 94.75 | 1.41365 | 90 | 97.619048 | 2.265702 | 0.309597 | 10.338983 | 2.443507 | P252>=95;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260116&d2=20260215&i=d | 2026-02-15T11:24:01+08:00 |
