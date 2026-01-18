# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=6 / INFO=0 / NONE=7
- RUN_TS_UTC: `2026-01-18T12:36:14.547024+00:00`
- STATS.generated_at_utc: `2026-01-18T06:57:29+00:00`
- STATS.as_of_ts: `2026-01-18T14:57:27+08:00`
- script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- stale_hours: `72.0`
- dash_history: `dashboard_fred_cache/history.json`
- history_lite_used_for_jump: `cache/history_lite.json`
- jump_calc: `ret1% = (latest-prev)/abs(prev)*100 (from history_lite last 2 points)`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(abs(ret1%60)>=2 -> WATCH)`

| Signal | Tag | Near | Series | DQ | data_date | value | z60 | p252 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_RET | NA | STLFSI4 | OK | 2026-01-09 | -0.6644 | NA | NA | -17.468175 | abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | VIXCLS | OK | 2026-01-15 | 15.84 | NA | NA | -5.432836 | abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | BAMLH0A0HYM2 | OK | 2026-01-15 | 2.71 | NA | NA | -1.811594 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | DGS2 | OK | 2026-01-15 | 3.56 | NA | NA | 1.424501 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | DGS10 | OK | 2026-01-15 | 4.17 | NA | NA | 0.481928 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | DTWEXBGS | OK | 2026-01-09 | 120.5856 | NA | NA | 0.498385 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | DCOILWTICO | OK | 2026-01-12 | 59.39 | NA | NA | 2.22031 | abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | SP500 | OK | 2026-01-16 | 6940.01 | NA | NA | -0.064224 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NASDAQCOM | OK | 2026-01-16 | 23515.39 | NA | NA | -0.062176 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | DJIA | OK | 2026-01-16 | 49359.33 | NA | NA | -0.168094 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | NFCINONFINLEVERAGE | OK | 2026-01-09 | -0.51002 | NA | NA | -5.916558 | abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | T10Y2Y | OK | 2026-01-16 | 0.65 | NA | NA | 6.557377 | abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | JUMP_RET | NA | T10Y3M | OK | 2026-01-16 | 0.57 | NA | NA | 16.326531 | abs(ret1%60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
