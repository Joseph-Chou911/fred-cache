# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=6 / INFO=2 / NONE=5; CHANGED=2
- RUN_TS_UTC: `2026-01-18T13:02:33.215205+00:00`
- STATS.generated_at_utc: `2026-01-18T06:57:29+00:00`
- STATS.as_of_ts: `2026-01-18T14:57:27+08:00`
- script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- stale_hours: `72.0`
- dash_history: `dashboard_fred_cache/history.json`
- history_lite_used_for_jump: `cache/history_lite.json`
- jump_calc: `ret1% = (latest-prev)/abs(prev)*100 (from history_lite last 2 points)`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(abs(ret1%)>=2 -> WATCH)`

| Signal | Tag | Near | PrevSignal | DeltaSignal | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NONE | NA | NA | NONE | SAME | BAMLH0A0HYM2 | OK | 6.09 | 2026-01-15 | 2.71 | -1.709343 | 8.333333 | NA | NA | -1.811594 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | WATCH | SAME | DCOILWTICO | OK | 6.09 | 2026-01-12 | 59.39 | 0.029178 | 13.888889 | NA | NA | 2.22031 | abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | DGS10 | OK | 6.09 | 2026-01-15 | 4.17 | 0.898587 | 32.936508 | NA | NA | 0.481928 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | DGS2 | OK | 6.09 | 2026-01-15 | 3.56 | 0.781119 | 24.603175 | NA | NA | 1.424501 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | NONE→INFO | DJIA | OK | 6.09 | 2026-01-16 | 49359.33 | 1.61987 | 98.412698 | NA | NA | -0.168094 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | DTWEXBGS | OK | 6.09 | 2026-01-09 | 120.5856 | -0.855581 | 20.634921 | NA | NA | 0.498385 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | NASDAQCOM | OK | 6.09 | 2026-01-16 | 23515.39 | 0.542703 | 91.666667 | NA | NA | -0.062176 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | WATCH | SAME | NFCINONFINLEVERAGE | OK | 6.09 | 2026-01-09 | -0.51002 | 1.217622 | 97.222222 | NA | NA | -5.916558 | P252>=95;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | NONE→INFO | SP500 | OK | 6.09 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | NA | NA | -0.064224 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | WATCH | SAME | STLFSI4 | OK | 6.09 | 2026-01-09 | -0.6644 | -0.454104 | 36.507937 | NA | NA | -17.468175 | abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | WATCH | SAME | T10Y2Y | OK | 6.09 | 2026-01-16 | 0.65 | 0.732118 | 92.460317 | NA | NA | 6.557377 | abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | WATCH | SAME | T10Y3M | OK | 6.09 | 2026-01-16 | 0.57 | 1.307071 | 100 | NA | NA | 16.326531 | P252>=95;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | WATCH | SAME | VIXCLS | OK | 6.09 | 2026-01-15 | 15.84 | -0.474361 | 25.793651 | NA | NA | -5.432836 | abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
