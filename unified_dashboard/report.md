# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-01-27T07:56:44Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- fragility_high: true
- vol_runaway: false
- matrix_cell: Trend=ON / Fragility=HIGH
- mode: DEFENSIVE_DCA

**reasons**
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, data_date=2026-01-26
- fragility_parts: credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=WATCH)=true, tw_margin(WATCH)=true, cross_divergence(DIVERGENCE)=true
- vol_gate: market_cache.VIX only (signal=WATCH, dir=HIGH, ret1%60=2.877238, data_date=2026-01-23)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=DOWNGRADED (fx not used as primary trigger)

## market_cache (detailed)
- as_of_ts: 2026-01-26T23:32:28Z
- run_ts_utc: 2026-01-26T23:33:12.597588+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3998fb8
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | JUMP | 16.090000 | 2026-01-23 | 0.012388 | -0.388096 | 43.333333 | 28.571429 | 0.172147 | 13.333333 | 2.877238 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 5 | 6 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | WATCH | HIGH | JUMP | -2.680000 | 2026-01-22 | 0.012388 | -0.813691 | 30.000000 | 7.142857 | -0.645155 | -18.333333 | -9.611452 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 4 | 5 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | INFO | HIGH | LONG | 6950.230000 | 2026-01-26 | 0.012388 | 1.214855 | 95.000000 | 98.809524 | 0.347042 | 13.333333 | 0.500607 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.844833 | 2026-01-26 | 0.012388 | 1.731892 | 91.666667 | 75.793651 | -0.240425 | -3.333333 | -0.096471 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-01-27T03:14:30+08:00
- run_ts_utc: 2026-01-26T23:36:21.351040+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 0
- WATCH: 1
- INFO: 4
- NONE: 8
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DGS10 | WATCH | NA | LEVEL | 4.260000 | 2026-01-22 | 4.363986 | 2.018187 | 98.333333 | 51.190476 | -0.075486 | 0.000000 | 0.000000 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49098.710000 | 2026-01-23 | 4.363986 | 1.179958 | 85.000000 | 96.428571 | -0.348236 | -8.333333 | -0.577717 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.505680 | 2026-01-16 | 4.363986 | 1.237692 | 90.000000 | 97.619048 | 0.020070 | 1.666667 | 0.850947 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6915.610000 | 2026-01-23 | 4.363986 | 0.867814 | 81.666667 | 95.634921 | 0.012874 | 0.000000 | 0.032690 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.540000 | 2026-01-23 | 4.363986 | 1.001965 | 86.666667 | 96.825397 | -0.087874 | -3.333333 | -1.818182 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.680000 | 2026-01-23 | 4.363986 | -1.639993 | 5.000000 | 5.555556 | 0.307346 | 3.333333 | 1.515152 | NA | NA | ALERT | ALERT→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 60.300000 | 2026-01-20 | 4.363986 | 0.609351 | 73.333333 | 19.444444 | 0.580173 | 16.666667 | 1.532244 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.610000 | 2026-01-22 | 4.363986 | 1.487105 | 96.666667 | 37.698413 | 0.120998 | 3.333333 | 0.277778 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 120.447800 | 2026-01-16 | 4.363986 | -1.045572 | 21.666667 | 14.682540 | -0.189991 | -5.000000 | -0.114276 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 23501.240000 | 2026-01-23 | 4.363986 | 0.491716 | 63.333333 | 90.873016 | 0.178382 | 11.666667 | 0.278290 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.651000 | 2026-01-16 | 4.363986 | -0.397953 | 35.000000 | 38.888889 | 0.056151 | 3.333333 | 2.016857 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.640000 | 2026-01-23 | 4.363986 | 0.465646 | 60.000000 | 88.888889 | -0.165952 | -6.666667 | -1.538462 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 16.090000 | 2026-01-23 | 4.363986 | -0.395352 | 41.666667 | 28.174603 | 0.169081 | 11.666667 | 2.877238 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-01-27T07:41:22+08:00
- run_ts_utc: 2026-01-26T23:41:26.158139+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@1c7f7c4
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.920000 | 2026-01-23 | 0.001155 | 0.913409 | 86.666667 | 48.015873 | -0.558009 | -11.638418 | -1.538462 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.320000 | 2026-01-26 | 0.001155 | 1.754473 | 95.000000 | 50.793651 | -0.062848 | 0.084746 | 0.000000 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-01-27T07:41:23+08:00
- run_ts_utc: 2026-01-26T23:41:26.200222+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@1c7f7c4
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | ALERT | MOVE | LONG | 464.700000 | 2026-01-26 | 0.000889 | 2.885037 | 100.000000 | 100.000000 | 0.048606 | 0.000000 | 1.462882 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 2 | 3 | https://stooq.com/q/d/l/?s=gld.us&d1=20251227&d2=20260126&i=d |
| IAU.US_CLOSE | ALERT | MOVE | LONG | 95.180000 | 2026-01-26 | 0.000889 | 2.885298 | 100.000000 | 100.000000 | 0.052217 | 0.000000 | 1.482034 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 2 | 3 | https://stooq.com/q/d/l/?s=iau.us&d1=20251227&d2=20260126&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 95.940000 | 2026-01-26 | 0.000889 | 0.929012 | 83.333333 | 65.873016 | -0.110361 | -1.412429 | -0.104123 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20251227&d2=20260126&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 90.420000 | 2026-01-26 | 0.000889 | 0.870587 | 81.666667 | 60.317460 | -0.141056 | -3.079096 | -0.132538 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20251227&d2=20260126&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-01-26
- run_day_tag: TRADING_DAY
- used_date_status: UNKNOWN_LATEST_ROW_DATE
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- note: run_day_tag is report-day context; UsedDate is the data date used for calculations (may lag on not-updated days)
- heat_split.heated_market: false
- heat_split.dq_issue: true
- risk_level: NA
- turnover_twd: 747339306040
- turnover_unit: TWD
- volume_multiplier: 1.027
- vol_multiplier: 1.027
- amplitude_pct: 0.647
- pct_change: 0.322
- close: 32064.52
- LookbackNTarget: 20
- LookbackNActual: 20
- signals.DownDay: false
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: 0
- signals.ConsecutiveBreak: 0
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: NA
- realized_vol_points_used: 0
- dd_n: 10
- max_drawdown_N_pct: NA
- max_drawdown_points_used: 0
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-01-27
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.375000
- spot_sell: 31.475000
- mid: 31.425000
- ret1_pct: -0.206415 (from 2026-01-26 to 2026-01-27)
- chg_5d_pct: NA (from None to None)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: DOWNGRADED

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-01-26T23:40:36Z

### cross_module (Margin × Roll25 consistency)
- margin_signal: WATCH
- margin_signal_source: DERIVED.rule_v1(TWSE_chg_yi_last5)
- margin_rule_version: rule_v1
- chg_unit: 億 (from modules.taiwan_margin_financing.latest.series.TWSE.chg_yi_unit.label)
- chg_last5: [55.0, 43.4, 39.9, -34.8, 18.1] 億
- sum_last5: 121.600 億
- pos_days_last5: 4
- latest_chg: 55.000 億
- margin_confidence: OK
- roll25_heated_market: false
- roll25_data_quality_issue: true
- roll25_heated (legacy): false
- roll25_confidence: OK
- roll25_split_ref: heated_market=false, dq_issue=true (see roll25_cache section)
- consistency: DIVERGENCE
- date_alignment: twmargin_date=2026-01-26, roll25_used_date=2026-01-26, match=true

<!-- rendered_at_utc: 2026-01-27T07:56:44Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
