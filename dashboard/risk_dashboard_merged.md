# Risk Dashboard (merged)

- SCRIPT_FINGERPRINT: `render_dashboard_py_fix_history_autodetect_and_staleh_2026-01-18`
- RUN_TS_UTC: `2026-01-18T08:40:11.785480+00:00`
- stale_hours_default: `36`
- stale_overrides: `{"STLFSI4": 240.0, "NFCINONFINLEVERAGE": 240.0, "BAMLH0A0HYM2": 72.0}`
- data_lag_default_days: `2`
- data_lag_overrides_days: `{"STLFSI4": 10, "NFCINONFINLEVERAGE": 10, "OFR_FSI": 7, "BAMLH0A0HYM2": 3, "DGS2": 3, "DGS10": 3, "VIXCLS": 3, "T10Y2Y": 3, "T10Y3M": 3}`

- market_cache.stats: `market_cache/stats_latest.json`
- market_cache.history: `market_cache/history_lite.json`
- market_cache.history_schema: `dict`
- market_cache.history_unwrap: `series`
- market_cache.history_series_count: `4`
- market_cache.as_of_ts: `2026-01-18T04:13:53Z`
- market_cache.generated_at_utc: `2026-01-18T04:13:53Z`
- market_cache.script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`

- cache.stats: `cache/stats_latest.json`
- cache.history: `cache/history_lite.json`
- cache.history_schema: `list`
- cache.history_unwrap: `root`
- cache.history_series_count: `13`
- cache.as_of_ts: `2026-01-18T14:57:27+08:00`
- cache.generated_at_utc: `2026-01-18T06:57:29+00:00`
- cache.script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`

- signal_rules: `Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); Jump(ONLY |ZΔ60|>=0.75); Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)`

| Signal | Tag | Near | PrevSignal | StreakWA | Feed | Series | DQ | age_h | stale_h | data_lag_d | data_lag_thr_d | data_date | value | z60 | p252 | z_delta60 | p_delta252 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFO | INFO_RET,LONG_EXTREME | NA | NONE | 0 | cache | DJIA | NA | 1.71 | 36 | 2 | 2 | 2026-01-16 | 49359.33 | 1.61987 | 98.412698 | NA | NA | -83.11 | P252>=95.0 or <=5.0 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | 0 | cache | NFCINONFINLEVERAGE | NA | 1.71 | 24 | 9 | 10 | 2026-01-09 | -0.51002 | 1.217622 | 97.222222 | NA | NA | -0.02849 | P252>=95.0 or <=5.0 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | INFO_RET,LONG_EXTREME | NA | NONE | 0 | cache | SP500 | NA | 1.71 | 36 | 2 | 2 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | NA | NA | -4.46 | P252>=95.0 or <=5.0 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | 0 | cache | T10Y3M | NA | 1.71 | 36 | 2 | 3 | 2026-01-16 | 0.57 | 1.307071 | 100 | NA | NA | 0.08 | P252>=95.0 or <=5.0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | cache | BAMLH0A0HYM2 | NA | 1.71 | 72 | 3 | 3 | 2026-01-15 | 2.71 | -1.709343 | 8.333333 | NA | NA | -0.05 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | STALE_DATA | NA | NONE | 0 | cache | DCOILWTICO | NA | 1.71 | 36 | 6 | 2 | 2026-01-12 | 59.39 | 0.029178 | 13.888889 | NA | NA | 1.29 | STALE_DATA(lag_d=6>thr_d=2) | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | cache | DGS10 | NA | 1.71 | 36 | 3 | 3 | 2026-01-15 | 4.17 | 0.898587 | 32.936508 | NA | NA | 0.02 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | cache | DGS2 | NA | 1.71 | 36 | 3 | 3 | 2026-01-15 | 3.56 | 0.781119 | 24.603175 | NA | NA | 0.05 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | STALE_DATA | NA | NONE | 0 | cache | DTWEXBGS | NA | 1.71 | 36 | 9 | 2 | 2026-01-09 | 120.5856 | -0.855581 | 20.634921 | NA | NA | 0.598 | STALE_DATA(lag_d=9>thr_d=2) | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | market_cache | HYG_IEF_RATIO | NA | 4.44 | 36 | 2 | 2 | 2026-01-16 | 0.845304 | NA | NA | NA | NA | NA | NA | DERIVED | 2026-01-18T04:13:53Z |
| NONE | INFO_RET | NA | NONE | 0 | cache | NASDAQCOM | NA | 1.71 | 36 | 2 | 2 | 2026-01-16 | 23515.39 | 0.542703 | 91.666667 | NA | NA | -14.63 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | market_cache | OFR_FSI | NA | 4.44 | 36 | 4 | 7 | 2026-01-14 | -2.626 | NA | NA | NA | NA | NA | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-18T04:13:53Z |
| NONE | NA | NA | NONE | 0 | market_cache | SP500 | NA | 4.44 | 36 | 2 | 2 | 2026-01-16 | 6940.01 | NA | NA | NA | NA | NA | NA | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-18T04:13:53Z |
| NONE | NA | NA | NONE | 0 | cache | STLFSI4 | NA | 1.71 | 24 | 9 | 10 | 2026-01-09 | -0.6644 | -0.454104 | 36.507937 | NA | NA | -0.0988 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | cache | T10Y2Y | NA | 1.71 | 36 | 2 | 3 | 2026-01-16 | 0.65 | 0.732118 | 92.460317 | NA | NA | 0.04 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 0 | market_cache | VIX | NA | 4.44 | 36 | 2 | 2 | 2026-01-16 | 15.86 | NA | NA | NA | NA | NA | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-18T04:13:53Z |
| NONE | NA | NA | NONE | 0 | cache | VIXCLS | NA | 1.71 | 36 | 3 | 3 | 2026-01-15 | 15.84 | -0.474361 | 25.793651 | NA | NA | -0.91 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
