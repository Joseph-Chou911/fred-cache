# Risk Dashboard (merged)

- SCRIPT_FINGERPRINT: `render_dashboard_py_fix_history_autodetect_and_staleh_2026-01-18`
- RUN_TS_UTC: `2026-01-18T07:55:39.779744+00:00`
- stale_hours_default: `36.0`
- stale_overrides: `{"STLFSI4": 240.0, "NFCINONFINLEVERAGE": 240.0, "BAMLH0A0HYM2": 72.0}`
- data_lag_default_days: `2`
- data_lag_overrides_days: `{"STLFSI4": 10, "NFCINONFINLEVERAGE": 10, "OFR_FSI": 7, "BAMLH0A0HYM2": 3, "DGS2": 3, "DGS10": 3, "VIXCLS": 3, "T10Y2Y": 3, "T10Y3M": 3}`
- FEED1.stats: `market_cache/stats_latest.json`
- FEED1.history: `market_cache/history_lite.json`
- FEED1.history_schema: `dict`
- FEED1.history_unwrap: `series`
- FEED1.history_series_count: `4`
- FEED1.as_of_ts: `2026-01-18T04:13:53Z`
- FEED1.generated_at_utc: `2026-01-18T04:13:53Z`
- FEED1.script_version: `market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400`
- FEED2.stats: `cache/stats_latest.json`
- FEED2.history: `cache/history_lite.json`
- FEED2.history_schema: `list`
- FEED2.history_unwrap: `root`
- FEED2.history_series_count: `13`
- FEED2.as_of_ts: `2026-01-18T14:57:27+08:00`
- FEED2.generated_at_utc: `2026-01-18T06:57:29+00:00`
- FEED2.script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- signal_rules: `Extreme(|Z60|>=2 (WATCH), |Z60|>=2.5 (ALERT), P252>=95 or <=5 (INFO if no |Z60|>=2 and no Jump), P252<=2 (ALERT)); Jump(ONLY |ZΔ60|>=0.75); Near(within 10% of thresholds: ZΔ60 / PΔ252 / ret1%); PΔ252>= 15 and |ret1%|>= 2 are INFO tags only (no escalation); StaleData(if data_lag_d > data_lag_thr_d => clamp Signal to INFO + Tag=STALE_DATA)`

| Signal | Tag | Near | PrevSignal | StreakWA | Feed | Series | DQ | age_h | stale_h | data_lag_d | data_lag_thr_d | data_date | value | z60 | p252 | z_delta60 | p_delta252 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_ZD | NA | NONE | 1 | cache | DGS2 | OK | 0.97 | 36 | 3 | 3 | 2026-01-15 | 3.56 | 0.781119 | 24.603175 | 0.881068 | NA | 1.424501 | \|ZΔ60\|>=0.75 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| WATCH | EXTREME_Z,INFO_PΔ | NEAR:ZΔ60 | NONE | 1 | market_cache | HYG_IEF_RATIO | OK | 3.7 | 36 | 2 | 2 | 2026-01-16 | 0.845304 | 2.464967 | 77.777778 | 0.743865 | 15.873016 | 0.447634 | \|Z60\|>=2 | DERIVED | 2026-01-18T04:13:53Z |
| INFO | JUMP_ZD,INFO_RET,STALE_DATA | NA | NONE | 1 | cache | DCOILWTICO | OK | 0.97 | 36 | 6 | 2 | 2026-01-12 | 59.39 | 0.029178 | 13.888889 | 0.753285 | NA | 2.22031 | STALE_DATA(lag_d=6>thr_d=2) | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | 1 | cache | DJIA | OK | 0.97 | 36 | 2 | 2 | 2026-01-16 | 49359.33 | 1.61987 | 98.412698 | -0.159386 | NA | -0.168094 | P252>=95 or <=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | JUMP_ZD,STALE_DATA | NA | NONE | 1 | cache | DTWEXBGS | OK | 0.97 | 36 | 9 | 2 | 2026-01-09 | 120.5856 | -0.855581 | 20.634921 | 0.920129 | NA | 0.498385 | STALE_DATA(lag_d=9>thr_d=2) | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME,INFO_RET | NA | NONE | 1 | cache | NFCINONFINLEVERAGE | OK | 0.97 | 240 | 9 | 10 | 2026-01-09 | -0.51002 | 1.217622 | 97.222222 | -0.311747 | NA | -5.916558 | P252>=95 or <=5 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | 1 | cache | SP500 | OK | 0.97 | 36 | 2 | 2 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | -0.088684 | NA | -0.064224 | P252>=95 or <=5 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME,INFO_RET | NA | NONE | 1 | cache | T10Y3M | OK | 0.97 | 36 | 2 | 3 | 2026-01-16 | 0.57 | 1.307071 | 100 | 0.393825 | NA | 16.326531 | P252>=95 or <=5 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| INFO | LONG_EXTREME | NA | NONE | 1 | market_cache | SP500 | OK | 3.7 | 36 | 2 | 2 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | -0.088684 | -0.396825 | -0.064224 | P252>=95 or <=5 | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-18T04:13:53Z |
| NONE | NA | NEAR:ret1% | NONE | 1 | cache | BAMLH0A0HYM2 | OK | 0.97 | 72 | 3 | 3 | 2026-01-15 | 2.71 | -1.709343 | 8.333333 | -0.312768 | NA | -1.811594 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 1 | cache | DGS10 | OK | 0.97 | 36 | 3 | 3 | 2026-01-15 | 4.17 | 0.898587 | 32.936508 | 0.290567 | NA | 0.481928 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | 1 | cache | NASDAQCOM | OK | 0.97 | 36 | 2 | 2 | 2026-01-16 | 23515.39 | 0.542703 | 91.666667 | -0.0592 | NA | -0.062176 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | INFO_RET | NA | NONE | 1 | cache | STLFSI4 | OK | 0.97 | 240 | 9 | 10 | 2026-01-09 | -0.6644 | -0.454104 | 36.507937 | -0.402848 | NA | -17.468175 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | INFO_RET | NA | NONE | 1 | cache | T10Y2Y | OK | 0.97 | 36 | 2 | 3 | 2026-01-16 | 0.65 | 0.732118 | 92.460317 | 0.549914 | NA | 6.557377 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | INFO_RET | NA | NONE | 1 | cache | VIXCLS | OK | 0.97 | 36 | 3 | 3 | 2026-01-15 | 15.84 | -0.474361 | 25.793651 | -0.328064 | NA | -5.432836 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | INFO_RET | NA | NONE | 1 | market_cache | OFR_FSI | OK | 3.7 | 36 | 4 | 7 | 2026-01-14 | -2.626 | -0.709121 | 6.746032 | 0.278718 | 3.174603 | 3.278085 | NA | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv | 2026-01-18T04:13:53Z |
| NONE | NA | NA | NONE | 1 | market_cache | VIX | OK | 3.7 | 36 | 2 | 2 | 2026-01-16 | 15.86 | -0.450183 | 25.793651 | 0.024178 | 0 | 0.126263 | NA | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-18T04:13:53Z |
