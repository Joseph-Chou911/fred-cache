# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-03T16:11:48Z

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
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, data_date=2026-02-02
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
- vol_gate: market_cache.VIX only (signal=WATCH, dir=HIGH, ret1%60=-6.307339, data_date=2026-02-02)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: WATCH
- consistency: RESONANCE
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-03, roll25_used_date=2026-02-02, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-03T03:21:33Z
- run_ts_utc: 2026-02-03T16:01:32.778059+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@97becde
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | JUMP | 16.340000 | 2026-02-02 | 12.666605 | -0.245463 | 46.666667 | 31.746032 | -0.389856 | -26.666667 | -6.307339 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 4 | 5 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | WATCH | HIGH | JUMP | -2.305000 | 2026-01-29 | 12.666605 | 0.289985 | 73.333333 | 30.555556 | 0.294840 | 11.666667 | 4.118136 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 1 | 2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | INFO | HIGH | LONG | 6976.440000 | 2026-02-02 | 12.666605 | 1.288276 | 95.000000 | 98.809524 | 0.327054 | 11.666667 | 0.539124 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.846291 | 2026-02-02 | 12.666605 | 1.656662 | 95.000000 | 83.730159 | 0.068363 | 3.333333 | 0.090169 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-03T21:23:32+08:00
- run_ts_utc: 2026-02-03T14:09:10.190810+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 1
- INFO: 5
- NONE: 6
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 117.899600 | 2026-01-30 | 0.760331 | -3.881004 | 1.666667 | 0.396825 | -1.285427 | 0.000000 | -1.161834 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.880000 | 2026-01-31 | 0.760331 | -0.127360 | 50.000000 | 37.698413 | 0.749163 | 25.000000 | 3.971119 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49407.660000 | 2026-02-02 | 0.760331 | 1.279342 | 91.666667 | 98.015873 | 0.485698 | 20.000000 | 1.053721 | P252>=95 | LONG_EXTREME | NONE | NONE→INFO | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.482950 | 2026-01-23 | 0.760331 | 1.449255 | 98.333333 | 99.603175 | 0.211563 | 8.333333 | 4.494938 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6976.440000 | 2026-02-02 | 0.760331 | 1.288276 | 95.000000 | 98.809524 | 0.327054 | 11.666667 | 0.539124 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.720000 | 2026-02-02 | 0.760331 | 1.387125 | 96.666667 | 99.206349 | -0.345859 | -3.333333 | -2.702703 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.600000 | 2026-02-02 | 0.760331 | 1.139047 | 100.000000 | 100.000000 | 0.023036 | 1.666667 | 1.694915 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 60.460000 | 2026-01-26 | 0.760331 | 0.743254 | 76.666667 | 20.634921 | 0.133903 | 3.333333 | 0.265340 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.260000 | 2026-01-30 | 0.760331 | 1.714204 | 98.333333 | 53.571429 | 0.245242 | 5.000000 | 0.471698 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.520000 | 2026-01-30 | 0.760331 | -0.142830 | 48.333333 | 18.253968 | -0.161192 | -3.333333 | -0.283286 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | JUMP | 23592.110000 | 2026-02-02 | 0.760331 | 0.755841 | 81.666667 | 93.650794 | 0.335681 | 26.666667 | 0.555328 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.712300 | 2026-01-23 | 0.760331 | -0.634085 | 28.333333 | 28.968254 | -0.236132 | -6.666667 | -9.416283 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 17.440000 | 2026-01-30 | 0.760331 | 0.131195 | 71.666667 | 55.158730 | 0.217037 | 11.666667 | 3.317536 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-03T16:58:57+08:00
- run_ts_utc: 2026-02-03T08:59:02.080045+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@93637cc
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | WATCH | MOVE | LEVEL | 2.350000 | 2026-02-02 | 0.001411 | 2.082436 | 96.666667 | 68.253968 | -0.374917 | -3.333333 | -0.423729 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 6 | 7 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.900000 | 2026-01-30 | 0.001411 | 0.439041 | 65.000000 | 42.460317 | 0.217306 | 12.457627 | 0.529101 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-03T16:58:58+08:00
- run_ts_utc: 2026-02-03T08:59:02.127635+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@93637cc
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | JUMP | 95.230000 | 2026-02-02 | 0.001147 | 0.143645 | 60.000000 | 47.619048 | -0.962430 | -24.745763 | -1.070019 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260104&d2=20260203&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | JUMP | 89.860000 | 2026-02-02 | 0.001147 | 0.159323 | 60.000000 | 47.619048 | -0.993867 | -26.440678 | -1.035242 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260104&d2=20260203&i=d |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 427.130000 | 2026-02-02 | 0.001147 | 0.743010 | 85.000000 | 96.428571 | -0.601471 | -4.830508 | -4.004944 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | ALERT | ALERT→WATCH | 9 | 10 | https://stooq.com/q/d/l/?s=gld.us&d1=20260104&d2=20260203&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 87.570000 | 2026-02-02 | 0.001147 | 0.757090 | 85.000000 | 96.428571 | -0.619022 | -4.830508 | -4.116939 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | ALERT | ALERT→WATCH | 9 | 10 | https://stooq.com/q/d/l/?s=iau.us&d1=20260104&d2=20260203&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-02
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- note: run_day_tag is report-day context; UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST (latest available; typically T-1). If upstream indicates DATA_NOT_UPDATED, staleness is tracked via taiwan_signals/resonance checks (e.g., strict_not_stale=false) and confidence may be downgraded.
- risk_level: NA
- turnover_twd: 771419543919
- turnover_unit: TWD
- volume_multiplier: 0.968
- vol_multiplier: 0.968
- amplitude_pct: 2.023
- pct_change: -1.371
- close: 31624.03
- LookbackNTarget: 20
- LookbackNActual: 20
- signals.DownDay: true
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: 0
- signals.ConsecutiveBreak: 3
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: 19.402989
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -3.596502
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-03
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.475000
- spot_sell: 31.625000
- mid: 31.550000
- ret1_pct: -0.126622 (from 2026-02-02 to 2026-02-03)
- chg_5d_pct: 0.381801 (from 2026-01-27 to 2026-02-03)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-03T15:11:13Z

<!-- rendered_at_utc: 2026-02-03T16:11:49Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
