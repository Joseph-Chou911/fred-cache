# Risk Dashboard (asset_proxy_cache)

- Summary: ALERT=2 / WATCH=0 / INFO=0 / NONE=2; CHANGED=0; WATCH_STREAK>=3=0
- SCRIPT_FINGERPRINT: `render_dashboard_py_signals_v8@67f0cf6`
- RULESET_ID: `signals_v8`
- RUN_TS_UTC: `2026-02-01T16:50:23.366259+00:00`
- STATS.generated_at_utc: `2026-02-01T16:50:23Z`
- STATS.as_of_ts: `2026-02-02T00:50:19+08:00`
- script_version: `cycle_sidecars_stats_v1`
- stale_hours: `36.0`
- stats_path: `asset_proxy_cache/stats_latest.json`
- dash_history: `asset_proxy_cache/history_dashboard.json`
- streak_calc: `PrevSignal/Streak derived from dashboard/history.json filtered by (module + ruleset_id); StreakWA includes today; StreakHist excludes today; ORDER_SAFE: if history already contains same-day key, it is excluded from baseline`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`
- diag_cols: p60 (w60 percentile), z252 (w252 z-score); diagnostics only, NOT used in rules/sorting

| Signal | Tag | Near | Dir | DirNote | PrevSignal | DeltaSignal | StreakHist | StreakWA | Series | DQ | age_h | data_date | value | z60 | p60 | p252 | z252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | LONG_EXTREME,JUMP_ZD,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 8 | 9 | GLD.US_CLOSE | OK | 0 | 2026-01-30 | 444.95 | 1.357379 | 90 | 97.619048 | 2.218015 | -1.728682 | -10 | -10.295956 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260102&d2=20260201&i=d | 2026-02-02T00:50:19+08:00 |
| ALERT | LONG_EXTREME,JUMP_ZD,JUMP_RET | NA | MOVE | MOVE_ONLY | ALERT | SAME | 8 | 9 | IAU.US_CLOSE | OK | 0 | 2026-01-30 | 91.2 | 1.388809 | 90 | 97.619048 | 2.235855 | -1.694508 | -10 | -10.081717 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260102&d2=20260201&i=d | 2026-02-02T00:50:19+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | IYR.US_CLOSE | OK | 0 | 2026-01-30 | 96.21 | 1.119435 | 85 | 73.412698 | 0.553699 | -0.031056 | -1.440678 | -0.010387 | NA | https://stooq.com/q/d/l/?s=iyr.us&d1=20260102&d2=20260201&i=d | 2026-02-02T00:50:19+08:00 |
| NONE | NA | NA | MOVE | MOVE_ONLY | NONE | SAME | 0 | 0 | VNQ.US_CLOSE | OK | 0 | 2026-01-30 | 90.8 | 1.169135 | 86.666667 | 68.650794 | 0.433286 | 0.082808 | 0.225989 | 0.110254 | NA | https://stooq.com/q/d/l/?s=vnq.us&d1=20260102&d2=20260201&i=d | 2026-02-02T00:50:19+08:00 |
