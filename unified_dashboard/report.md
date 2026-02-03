# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-03T23:05:56Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- fragility_high: true
- vol_runaway: false
- matrix_cell: Trend=OFF / Fragility=HIGH
- mode: RISK_OFF

**reasons**
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, data_date=2026-02-03
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=WATCH)=true
- vol_gate: market_cache.VIX only (signal=WATCH, dir=HIGH, ret1%60=-6.307339, data_date=2026-02-02)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: WATCH
- consistency: DIVERGENCE
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-03, roll25_used_date=2026-02-03, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-03T22:58:32Z
- run_ts_utc: 2026-02-03T22:59:10.327410+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3aa2389
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP500 | WATCH | HIGH | JUMP | 6917.810000 | 2026-02-03 | 0.010647 | 0.686458 | 71.666667 | 93.253968 | -0.601818 | -23.333333 | -0.840400 | abs(PΔ60)>=15 | JUMP_P | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | WATCH | HIGH | JUMP | 16.340000 | 2026-02-02 | 0.010647 | -0.245463 | 46.666667 | 31.746032 | -0.389856 | -26.666667 | -6.307339 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 4 | 5 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | WATCH | HIGH | JUMP | -2.255000 | 2026-01-30 | 0.010647 | 0.456701 | 80.000000 | 33.333333 | 0.166716 | 6.666667 | 2.169197 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 1 | 2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.844865 | 2026-02-03 | 0.010647 | 1.356229 | 85.000000 | 76.587302 | -0.300433 | -10.000000 | -0.168426 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-04T06:57:48+08:00
- run_ts_utc: 2026-02-03T23:00:10.029669+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 4
- INFO: 5
- NONE: 3
- CHANGED: 3

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 117.899600 | 2026-01-30 | 0.038897 | -3.881004 | 1.666667 | 0.396825 | -1.285427 | 0.000000 | -1.161834 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.810000 | 2026-02-02 | 0.038897 | -0.571002 | 33.333333 | 22.222222 | -0.443642 | -16.666667 | -2.430556 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | LEVEL | 4.290000 | 2026-02-02 | 0.038897 | 2.070030 | 98.333333 | 61.111111 | 0.355826 | 0.000000 | 0.704225 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | NA | JUMP | 3.570000 | 2026-02-02 | 0.038897 | 0.806078 | 76.666667 | 29.365079 | 0.948908 | 28.333333 | 1.420455 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 16.340000 | 2026-02-02 | 0.038897 | -0.266636 | 45.000000 | 31.746032 | -0.397831 | -26.666667 | -6.307339 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49407.660000 | 2026-02-02 | 0.038897 | 1.279342 | 91.666667 | 98.015873 | 0.485698 | 20.000000 | 1.053721 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.482950 | 2026-01-23 | 0.038897 | 1.449255 | 98.333333 | 99.603175 | 0.211563 | 8.333333 | 4.494938 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6976.440000 | 2026-02-02 | 0.038897 | 1.288276 | 95.000000 | 98.809524 | 0.327054 | 11.666667 | 0.539124 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.710000 | 2026-02-03 | 0.038897 | 1.201961 | 93.333333 | 98.412698 | -0.185163 | -3.333333 | -1.388889 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.590000 | 2026-02-03 | 0.038897 | 1.048350 | 96.666667 | 99.206349 | -0.090697 | -3.333333 | -1.666667 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 60.460000 | 2026-01-26 | 0.038897 | 0.743254 | 76.666667 | 20.634921 | 0.133903 | 3.333333 | 0.265340 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | JUMP | 23592.110000 | 2026-02-02 | 0.038897 | 0.755841 | 81.666667 | 93.650794 | 0.335681 | 26.666667 | 0.555328 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.712300 | 2026-01-23 | 0.038897 | -0.634085 | 28.333333 | 28.968254 | -0.236132 | -6.666667 | -9.416283 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-04T07:04:42+08:00
- run_ts_utc: 2026-02-03T23:04:47.505735+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@0d3f054
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | ALERT | MOVE | JUMP | 1.940000 | 2026-02-02 | 0.001529 | 1.289072 | 96.666667 | 55.158730 | 0.869847 | 32.259887 | 2.105263 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | NONE | NONE→ALERT | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | WATCH | MOVE | LEVEL | 2.360000 | 2026-02-03 | 0.001529 | 2.223766 | 100.000000 | 72.619048 | 0.146726 | 3.389831 | 0.425532 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 7 | 8 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-04T07:04:44+08:00
- run_ts_utc: 2026-02-03T23:04:47.554642+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@0d3f054
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | ALERT | MOVE | LONG | 454.350000 | 2026-02-03 | 0.000987 | 1.588835 | 91.666667 | 98.015873 | 0.863410 | 6.920904 | 6.372767 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_ZD,JUMP_RET | WATCH | WATCH→ALERT | 10 | 11 | https://stooq.com/q/d/l/?s=gld.us&d1=20260104&d2=20260203&i=d |
| IAU.US_CLOSE | ALERT | MOVE | LONG | 93.070000 | 2026-02-03 | 0.000987 | 1.589559 | 91.666667 | 98.015873 | 0.849976 | 6.920904 | 6.280690 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_ZD,JUMP_RET | WATCH | WATCH→ALERT | 10 | 11 | https://stooq.com/q/d/l/?s=iau.us&d1=20260104&d2=20260203&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 95.000000 | 2026-02-03 | 0.000987 | -0.076581 | 51.666667 | 43.253968 | -0.214110 | -7.655367 | -0.241521 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260104&d2=20260203&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 89.650000 | 2026-02-03 | 0.000987 | -0.070914 | 55.000000 | 40.079365 | -0.221472 | -4.322034 | -0.233697 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260104&d2=20260203&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-03
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- note: run_day_tag is report-day context; UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST (latest available; typically T-1). If upstream indicates DATA_NOT_UPDATED, staleness is tracked via taiwan_signals/resonance checks (e.g., strict_not_stale=false) and confidence may be downgraded.
- risk_level: NA
- turnover_twd: 821574120123
- turnover_unit: TWD
- volume_multiplier: 1.027
- vol_multiplier: 1.027
- amplitude_pct: 1.759
- pct_change: 1.807
- close: 32195.36
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
- realized_vol_N_annualized_pct: 21.377520
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
- generated_at_utc: 2026-02-03T23:03:35Z

<!-- rendered_at_utc: 2026-02-03T23:05:56Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
