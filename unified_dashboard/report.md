# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-04T16:08:56Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- fragility_high: true
- vol_runaway: true
- matrix_cell: Trend=OFF / Fragility=HIGH
- mode: PAUSE_RISK_ON

**reasons**
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, data_date=2026-02-03
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=WATCH)=true
- vol_gate: market_cache.VIX only (signal=WATCH, dir=HIGH, ret1%60=10.159119, data_date=2026-02-03)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: WATCH
- consistency: DIVERGENCE
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-04, roll25_used_date=2026-02-03, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-04T03:17:44Z
- run_ts_utc: 2026-02-04T15:57:30.291016+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@30cfaed
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | JUMP | 18.000000 | 2026-02-03 | 12.662859 | 0.382153 | 81.666667 | 60.317460 | 0.627616 | 35.000000 | 10.159119 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 5 | 6 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | WATCH | HIGH | JUMP | -2.255000 | 2026-01-30 | 12.662859 | 0.456701 | 80.000000 | 33.333333 | 0.166716 | 6.666667 | 2.169197 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 2 | 3 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | WATCH | HIGH | JUMP | 6917.810000 | 2026-02-03 | 12.662859 | 0.686458 | 71.666667 | 93.253968 | -0.601818 | -23.333333 | -0.840400 | abs(PΔ60)>=15 | JUMP_P | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.844865 | 2026-02-03 | 12.662859 | 1.356229 | 85.000000 | 76.587302 | -0.300433 | -10.000000 | -0.168426 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-04T21:23:42+08:00
- run_ts_utc: 2026-02-04T14:07:32.845882+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 5
- INFO: 4
- NONE: 3
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 117.899600 | 2026-01-30 | 0.730513 | -3.881004 | 1.666667 | 0.396825 | -1.285427 | 0.000000 | -1.161834 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.810000 | 2026-02-02 | 0.730513 | -0.571002 | 33.333333 | 22.222222 | -0.443642 | -16.666667 | -2.430556 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | LEVEL | 4.290000 | 2026-02-02 | 0.730513 | 2.070030 | 98.333333 | 61.111111 | 0.355826 | 0.000000 | 0.704225 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | NA | JUMP | 3.570000 | 2026-02-02 | 0.730513 | 0.806078 | 76.666667 | 29.365079 | 0.948908 | 28.333333 | 1.420455 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 23255.190000 | 2026-02-03 | 0.730513 | -0.134793 | 36.666667 | 81.746032 | -0.890634 | -45.000000 | -1.428105 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 16.340000 | 2026-02-02 | 0.730513 | -0.266636 | 45.000000 | 31.746032 | -0.397831 | -26.666667 | -6.307339 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49240.990000 | 2026-02-03 | 0.730513 | 1.071670 | 85.000000 | 96.428571 | -0.207673 | -6.666667 | -0.337336 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.482950 | 2026-01-23 | 0.730513 | 1.449255 | 98.333333 | 99.603175 | 0.211563 | 8.333333 | 4.494938 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.710000 | 2026-02-03 | 0.730513 | 1.201961 | 93.333333 | 98.412698 | -0.185163 | -3.333333 | -1.388889 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.590000 | 2026-02-03 | 0.730513 | 1.048350 | 96.666667 | 99.206349 | -0.090697 | -3.333333 | -1.666667 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 60.460000 | 2026-01-26 | 0.730513 | 0.743254 | 76.666667 | 20.634921 | 0.133903 | 3.333333 | 0.265340 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6917.810000 | 2026-02-03 | 0.730513 | 0.686458 | 71.666667 | 93.253968 | -0.601818 | -23.333333 | -0.840400 | NA | JUMP_DELTA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.712300 | 2026-01-23 | 0.730513 | -0.634085 | 28.333333 | 28.968254 | -0.236132 | -6.666667 | -9.416283 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-04T17:02:07+08:00
- run_ts_utc: 2026-02-04T09:02:11.084350+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@891a904
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | ALERT | MOVE | JUMP | 1.940000 | 2026-02-02 | 0.001135 | 1.289072 | 96.666667 | 55.158730 | 0.869847 | 32.259887 | 2.105263 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | NONE | NONE→ALERT | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | WATCH | MOVE | LEVEL | 2.360000 | 2026-02-03 | 0.001135 | 2.223766 | 100.000000 | 72.619048 | 0.146726 | 3.389831 | 0.425532 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 7 | 8 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-04T17:02:07+08:00
- run_ts_utc: 2026-02-04T09:02:11.132147+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@891a904
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | ALERT | MOVE | LONG | 454.290000 | 2026-02-03 | 0.001148 | 1.588835 | 91.666667 | 98.015873 | 0.863410 | 6.920904 | 6.372767 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_ZD,JUMP_RET | WATCH | WATCH→ALERT | 10 | 11 | https://stooq.com/q/d/l/?s=gld.us&d1=20260105&d2=20260204&i=d |
| IAU.US_CLOSE | ALERT | MOVE | LONG | 93.030000 | 2026-02-03 | 0.001148 | 1.589559 | 91.666667 | 98.015873 | 0.849976 | 6.920904 | 6.280690 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_ZD,JUMP_RET | WATCH | WATCH→ALERT | 10 | 11 | https://stooq.com/q/d/l/?s=iau.us&d1=20260105&d2=20260204&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 95.000000 | 2026-02-03 | 0.001148 | -0.076581 | 51.666667 | 43.253968 | -0.214110 | -7.655367 | -0.241521 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260105&d2=20260204&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 89.660000 | 2026-02-03 | 0.001148 | -0.070914 | 55.000000 | 40.079365 | -0.221472 | -4.322034 | -0.233697 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260105&d2=20260204&i=d |

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
- data_date: 2026-02-04
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.480000
- spot_sell: 31.630000
- mid: 31.555000
- ret1_pct: 0.015848 (from 2026-02-03 to 2026-02-04)
- chg_5d_pct: 0.846916 (from 2026-01-28 to 2026-02-04)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-04T15:09:37Z

<!-- rendered_at_utc: 2026-02-04T16:08:56Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
