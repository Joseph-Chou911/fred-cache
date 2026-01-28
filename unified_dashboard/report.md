# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-01-28T23:42:25Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- fragility_high: false
- vol_runaway: false
- matrix_cell: Trend=ON / Fragility=LOW
- mode: NORMAL_DCA

**reasons**
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, data_date=2026-01-27
- fragility_parts: credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false, tw_margin(WATCH)=true, cross_divergence(DIVERGENCE)=true
- vol_gate: market_cache.VIX only (signal=NONE, dir=HIGH, ret1%60=1.238390, data_date=2026-01-27)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=DOWNGRADED (fx not used as primary trigger)

## market_cache (detailed)
- as_of_ts: 2026-01-28T04:15:06Z
- run_ts_utc: 2026-01-28T16:04:39.549874+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@1c13705
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | WATCH | HIGH | JUMP | -2.505000 | 2026-01-23 | 11.825986 | -0.316485 | 41.666667 | 11.111111 | 0.497207 | 11.666667 | 6.529851 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 6 | 7 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | INFO | HIGH | LONG | 6978.600000 | 2026-01-27 | 11.825986 | 1.475446 | 100.000000 | 100.000000 | 0.260590 | 5.000000 | 0.408188 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.845697 | 2026-01-27 | 11.825986 | 1.811259 | 95.000000 | 79.761905 | 0.079367 | 3.333333 | 0.102275 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |
| VIX | NONE | HIGH | NONE | 16.350000 | 2026-01-27 | 11.825986 | -0.280135 | 48.333333 | 33.730159 | 0.080721 | 3.333333 | 1.238390 | NA | NA | NONE | SAME | 0 | 0 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-01-29T03:43:17+08:00
- run_ts_utc: 2026-01-28T23:30:22.193390+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 1
- INFO: 5
- NONE: 6
- CHANGED: 0

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 119.285500 | 2026-01-23 | 3.781998 | -2.595576 | 1.666667 | 0.396825 | -1.550004 | -20.000000 | -0.964982 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | WATCH | NA | LONG | 0.710000 | 2026-01-27 | 3.781998 | 1.412703 | 96.666667 | 99.206349 | 0.682824 | 26.666667 | 7.575758 | P252>=95;abs(pΔ60)>=15;abs(ret1%)>=2 | LONG_EXTREME | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49003.410000 | 2026-01-27 | 3.781998 | 0.998284 | 80.000000 | 95.238095 | -0.460867 | -13.333333 | -0.827707 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | INFO | NA | LONG | 23817.100000 | 2026-01-27 | 3.781998 | 1.364158 | 98.333333 | 98.809524 | 0.591656 | 11.666667 | 0.914100 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.482950 | 2026-01-23 | 3.781998 | 1.449255 | 98.333333 | 99.603175 | 0.211563 | 8.333333 | 4.494938 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6978.600000 | 2026-01-27 | 3.781998 | 1.475446 | 100.000000 | 100.000000 | 0.260590 | 5.000000 | 0.408188 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.570000 | 2026-01-27 | 3.781998 | 1.108480 | 98.333333 | 99.603175 | 0.082163 | 8.333333 | 3.636364 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.710000 | 2026-01-27 | 3.781998 | -1.344375 | 11.666667 | 8.333333 | 0.180948 | 3.333333 | 0.743494 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 60.460000 | 2026-01-26 | 3.781998 | 0.743254 | 76.666667 | 20.634921 | 0.133903 | 3.333333 | 0.265340 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.220000 | 2026-01-26 | 3.781998 | 1.302349 | 91.666667 | 42.460317 | -0.347363 | -3.333333 | -0.471698 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | JUMP | 3.560000 | 2026-01-26 | 3.781998 | 0.535093 | 66.666667 | 25.000000 | -0.728317 | -25.000000 | -1.111111 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.651000 | 2026-01-16 | 3.781998 | -0.397953 | 35.000000 | 38.888889 | 0.056151 | 3.333333 | 2.016857 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | NONE | 16.350000 | 2026-01-27 | 3.781998 | -0.290347 | 46.666667 | 33.333333 | 0.077632 | 3.333333 | 1.238390 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-01-29T07:41:31+08:00
- run_ts_utc: 2026-01-28T23:41:35.496547+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3274a17
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | ALERT | MOVE | LEVEL | 2.360000 | 2026-01-28 | 0.001249 | 2.726922 | 100.000000 | 71.031746 | 0.424608 | 0.000000 | 0.854701 | abs(Z60)>=2;abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | 1 | 2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.900000 | 2026-01-27 | 0.001249 | 0.509469 | 65.000000 | 41.269841 | -0.005433 | 0.593220 | 0.000000 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-01-29T07:41:32+08:00
- run_ts_utc: 2026-01-28T23:41:35.545865+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3274a17
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | JUMP | 95.060000 | 2026-01-28 | 0.000985 | 0.043638 | 58.333333 | 46.428571 | -0.922914 | -24.717514 | -1.010101 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=iyr.us&d1=20251229&d2=20260128&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | JUMP | 89.450000 | 2026-01-28 | 0.000985 | -0.210342 | 51.666667 | 35.317460 | -1.004854 | -27.994350 | -1.039938 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=vnq.us&d1=20251229&d2=20260128&i=d |
| GLD.US_CLOSE | ALERT | MOVE | LONG | 494.560000 | 2026-01-28 | 0.000985 | 3.371203 | 100.000000 | 100.000000 | 0.321839 | 0.000000 | 3.905708 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95;abs(ret1%60)>=2 | EXTREME_Z,LONG_EXTREME,JUMP_RET | ALERT | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=gld.us&d1=20251229&d2=20260128&i=d |
| IAU.US_CLOSE | ALERT | MOVE | LONG | 101.270000 | 2026-01-28 | 0.000985 | 3.367673 | 100.000000 | 100.000000 | 0.319424 | 0.000000 | 3.887977 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95;abs(ret1%60)>=2 | EXTREME_Z,LONG_EXTREME,JUMP_RET | ALERT | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=iau.us&d1=20251229&d2=20260128&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-01-28
- run_day_tag: TRADING_DAY
- used_date_status: OK_LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- note: run_day_tag is report-day context; UsedDate is the data date used for calculations (may lag on not-updated days)
- heat_split.heated_market: false
- heat_split.dq_issue: false
- risk_level: NA
- turnover_twd: 853922428449
- turnover_unit: TWD
- volume_multiplier: 1.117
- vol_multiplier: 1.117
- amplitude_pct: 1.306
- pct_change: 1.504
- close: 32803.82
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
- realized_vol_N_annualized_pct: 16.501909
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.617192
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-01-28
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.215000
- spot_sell: 31.365000
- mid: 31.290000
- ret1_pct: -0.445434 (from 2026-01-27 to 2026-01-28)
- chg_5d_pct: NA (from None to None)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: DOWNGRADED

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-01-28T23:19:59Z

### cross_module (Margin × Roll25 consistency)
- margin_signal: WATCH
- margin_signal_source: DERIVED.rule_v1(TWSE_chg_yi_last5)
- margin_rule_version: rule_v1
- chg_unit: 億 (from modules.taiwan_margin_financing.latest.series.TWSE.chg_yi_unit.label)
- chg_last5: [21.9, 11.5, 55.0, 43.4, 39.9] 億
- sum_last5: 171.700 億
- pos_days_last5: 5
- latest_chg: 21.900 億
- margin_confidence: OK
- roll25_heated_market: false
- roll25_data_quality_issue: false
- roll25_heated (legacy): false
- roll25_confidence: OK
- roll25_split_ref: heated_market=false, dq_issue=false (see roll25_cache section)
- consistency: DIVERGENCE
- date_alignment: twmargin_date=2026-01-28, roll25_used_date=2026-01-28, match=true

<!-- rendered_at_utc: 2026-01-28T23:42:25Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
