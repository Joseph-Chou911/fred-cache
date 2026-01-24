# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- unified_generated_at_utc: 2026-01-24T14:04:14Z

## market_cache (detailed)
- as_of_ts: 2026-01-24T04:04:09Z
- run_ts_utc: 2026-01-24T13:22:38.175834+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@0cefcdd
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | WATCH | HIGH | JUMP | -2.445000 | 2026-01-21 | 9.308104 | -0.168536 | 48.333333 | 15.079365 | -0.703891 | -28.333333 | -11.389522 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 2 | 3 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | JUMP | 16.090000 | 2026-01-23 | 9.308104 | -0.388096 | 43.333333 | 28.571429 | 0.172147 | 13.333333 | 2.877238 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 3 | 4 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | INFO | HIGH | LONG | 6915.610000 | 2026-01-23 | 9.308104 | 0.867814 | 81.666667 | 95.634921 | 0.012874 | 0.000000 | 0.032690 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 3 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.845649 | 2026-01-23 | 9.308104 | 1.972317 | 95.000000 | 78.968254 | -0.477955 | -5.000000 | -0.215945 | NA | NA | WATCH | WATCH→NONE | 5 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-01-24T21:43:14+08:00
- run_ts_utc: 2026-01-24T13:49:17.039986+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 2
- INFO: 4
- NONE: 6
- CHANGED: 1

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | ALERT | NA | LONG | 2.640000 | 2026-01-22 | 0.100289 | -1.947339 | 1.666667 | 1.587302 | -0.278774 | -1.666667 | -1.858736 | P252<=2 | LONG_EXTREME | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | LEVEL | 4.260000 | 2026-01-22 | 0.100289 | 2.018187 | 98.333333 | 51.190476 | -0.075486 | 0.000000 | 0.000000 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 15.640000 | 2026-01-22 | 0.100289 | -0.564433 | 30.000000 | 20.238095 | -0.465988 | -25.000000 | -7.455621 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49098.710000 | 2026-01-23 | 0.100289 | 1.179958 | 85.000000 | 96.428571 | -0.348236 | -8.333333 | -0.577717 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.505680 | 2026-01-16 | 0.100289 | 1.237692 | 90.000000 | 97.619048 | 0.020070 | 1.666667 | 0.850947 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6915.610000 | 2026-01-23 | 0.100289 | 0.867814 | 81.666667 | 95.634921 | 0.012874 | 0.000000 | 0.032690 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.540000 | 2026-01-23 | 0.100289 | 1.001965 | 86.666667 | 96.825397 | -0.087874 | -3.333333 | -1.818182 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 60.300000 | 2026-01-20 | 0.100289 | 0.609351 | 73.333333 | 19.444444 | 0.580173 | 16.666667 | 1.532244 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.610000 | 2026-01-22 | 0.100289 | 1.487105 | 96.666667 | 37.698413 | 0.120998 | 3.333333 | 0.277778 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 120.447800 | 2026-01-16 | 0.100289 | -1.045572 | 21.666667 | 14.682540 | -0.189991 | -5.000000 | -0.114276 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 23501.240000 | 2026-01-23 | 0.100289 | 0.491716 | 63.333333 | 90.873016 | 0.178382 | 11.666667 | 0.278290 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.651000 | 2026-01-16 | 0.100289 | -0.397953 | 35.000000 | 38.888889 | 0.056151 | 3.333333 | 2.016857 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.640000 | 2026-01-23 | 0.100289 | 0.465646 | 60.000000 | 88.888889 | -0.165952 | -6.666667 | -1.538462 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-01-23
- tag: NON_TRADING_DAY
- risk_level: 低
- turnover_twd: 818428930073
- turnover_unit: TWD
- volume_multiplier: 1.068
- vol_multiplier: 0.770
- amplitude_pct: 1.100
- pct_change: 0.679
- close: 31961.51
- LookbackNTarget: 20
- LookbackNActual: 16
- signals.DownDay: false
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: false
- signals.ConsecutiveBreak: false
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: 15.808803
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.617192
- max_drawdown_points_used: 10
- confidence: DOWNGRADED

## FX (USD/TWD)
- status: OK
- data_date: 2026-01-23
- source_url: https://rate.bot.com.tw/xrt/flcsv/0/2026-01-23
- spot_buy: 31.500000
- spot_sell: 31.483000
- mid: 31.491500
- ret1_pct: NA (from None to None)
- chg_5d_pct: NA (from None to None)
- dir: NA
- fx_signal: NA
- fx_reason: NA
- fx_confidence: DOWNGRADED

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-01-24T13:24:51Z

### cross_module (Margin × Roll25 consistency)
- margin_signal: WATCH
- margin_signal_source: DERIVED.rule_v1(TWSE_chg_yi_last5)
- margin_rule_version: rule_v1
- chg_last5: [43.4, 39.9, -34.8, 18.1, 60.2]
- sum_last5: 126.800
- pos_days_last5: 4
- latest_chg: 43.400
- margin_confidence: OK
- roll25_heated: false
- roll25_confidence: DOWNGRADED
- consistency: DIVERGENCE
- date_alignment: twmargin_date=2026-01-23, roll25_used_date=2026-01-23, match=true

<!-- rendered_at_utc: 2026-01-24T14:04:14Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
