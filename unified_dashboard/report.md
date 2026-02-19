# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- nasdaq_bb_cache: OK
- unified_generated_at_utc: 2026-02-19T16:13:02Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- trend_strong: false
- trend_relaxed: true
- fragility_high: false
- vol_watch: true
- vol_runaway: false
- matrix_cell: Trend=ON / Fragility=LOW
- mode: DEFENSIVE_DCA

**mode_decision_path**
- triggered: vol_watch downshift => DEFENSIVE_DCA

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, p252=86.904762, p252_on_threshold=80.0, data_date=2026-02-18
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=19.620000, ret1%60=-3.302119, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-18)
- vol_runaway_branch: THRESHOLDS_FAILED (display-only)
- vol_runaway_failed_leg: ret1%60<5.0, value<20.0 (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: QUIET
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-11, roll25_used_date=2026-02-11, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-19T03:25:48Z
- run_ts_utc: 2026-02-19T16:00:16.606354+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@8dc279d
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | WATCH | HIGH | DOWN | JUMP | -2.210000 | 2026-02-16 | 12.574613 | 1.107565 | 88.333333 | 41.269841 | -0.261665 | -6.666667 | -4.491726 | abs(ret1%1d)>=2 | JUMP_RET | NONE | NONE→WATCH | 0 | 1 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | WATCH | HIGH | UP | JUMP | 6881.310000 | 2026-02-18 | 12.574613 | 0.098632 | 48.333333 | 86.904762 | 0.382507 | 15.000000 | 0.556609 | abs(PΔ60)>=15 | JUMP_P | NONE | NONE→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | WATCH | HIGH | DOWN | JUMP | 19.620000 | 2026-02-18 | 12.574613 | 1.559474 | 90.000000 | 69.841270 | -0.317566 | -1.666667 | -3.302119 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 1 | 2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.834175 | 2026-02-18 | 12.574613 | -0.738875 | 20.000000 | 29.761905 | 0.487272 | 6.666667 | 0.336388 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-19T21:40:19+08:00
- run_ts_utc: 2026-02-19T14:14:19.493467+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 1
- INFO: 3
- NONE: 8
- CHANGED: 1

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DGS2 | ALERT | NA | LONG | 3.430000 | 2026-02-17 | 0.565970 | -1.568126 | 5.000000 | 1.587302 | 0.646304 | 3.333333 | 0.882353 | P252<=2 | LONG_EXTREME | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | WATCH | NA | LEVEL | 64.530000 | 2026-02-09 | 0.565970 | 2.229106 | 96.666667 | 60.317460 | 0.233989 | 1.666667 | 1.191783 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49662.660000 | 2026-02-18 | 0.565970 | 1.089796 | 93.333333 | 98.412698 | 0.118337 | 1.666667 | 0.261380 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | INFO | NA | LONG | 117.525800 | 2026-02-13 | 0.565970 | -1.701334 | 10.000000 | 2.380952 | 0.063373 | 0.000000 | -0.010039 | P252<=5 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.474590 | 2026-02-06 | 0.565970 | 1.612208 | 100.000000 | 100.000000 | 0.010222 | 0.000000 | 0.848219 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.940000 | 2026-02-17 | 0.565970 | 1.059185 | 86.666667 | 48.412698 | 0.079769 | 1.666667 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.050000 | 2026-02-17 | 0.565970 | -1.580140 | 10.000000 | 9.523810 | 0.187357 | 1.666667 | 0.247525 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22753.630000 | 2026-02-18 | 0.565970 | -1.365915 | 13.333333 | 68.650794 | 0.423804 | 3.333333 | 0.776185 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6881.310000 | 2026-02-18 | 0.565970 | 0.098632 | 48.333333 | 86.904762 | 0.382507 | 15.000000 | 0.556609 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.620800 | 2026-02-13 | 0.565970 | -0.250970 | 48.333333 | 43.650794 | 0.146568 | 11.666667 | 5.336993 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.620000 | 2026-02-18 | 0.565970 | -0.604450 | 31.666667 | 81.746032 | -0.034932 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.390000 | 2026-02-18 | 0.565970 | -0.552641 | 21.666667 | 81.349206 | 0.174965 | 1.666667 | 8.333333 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 20.290000 | 2026-02-17 | 0.565970 | 1.877040 | 91.666667 | 73.809524 | -0.292074 | -5.000000 | -4.292453 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-19T17:06:05+08:00
- run_ts_utc: 2026-02-19T09:06:09.423183+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@bc96e9b
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | WATCH | MOVE | JUMP | 2.290000 | 2026-02-18 | 0.001229 | 0.266453 | 68.333333 | 39.682540 | 0.687283 | 15.790960 | 1.327434 | abs(PΔ60)>=15 | JUMP_P | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | WATCH | MOVE | LEVEL | 1.790000 | 2026-02-17 | 0.001229 | -2.036426 | 8.333333 | 15.079365 | 0.532770 | 4.943503 | 1.129944 | abs(Z60)>=2 | EXTREME_Z | ALERT | ALERT→WATCH | 7 | 8 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-19T17:06:06+08:00
- run_ts_utc: 2026-02-19T09:06:09.474994+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@bc96e9b
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | LONG | 100.010000 | 2026-02-18 | 0.000965 | 2.410914 | 96.666667 | 99.206349 | -0.849177 | -3.333333 | -1.185654 | abs(Z60)>=2;P252>=95;abs(ZΔ60)>=0.75 | EXTREME_Z,LONG_EXTREME,JUMP_ZD | ALERT | SAME | 12 | 13 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260120&d2=20260219&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | LONG | 94.370000 | 2026-02-18 | 0.000965 | 2.450017 | 96.666667 | 99.206349 | -0.868900 | -3.333333 | -1.183246 | abs(Z60)>=2;P252>=95;abs(ZΔ60)>=0.75 | EXTREME_Z,LONG_EXTREME,JUMP_ZD | ALERT | SAME | 12 | 13 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260120&d2=20260219&i=d |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 458.280000 | 2026-02-18 | 0.000965 | 1.211263 | 86.666667 | 96.825397 | 0.292049 | 10.395480 | 2.242152 | P252>=95;abs(ret1%1d)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 6 | 7 | https://stooq.com/q/d/l/?s=gld.us&d1=20260120&d2=20260219&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 93.850000 | 2026-02-18 | 0.000965 | 1.208898 | 86.666667 | 96.825397 | 0.287501 | 10.395480 | 2.210847 | P252>=95;abs(ret1%1d)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 6 | 7 | https://stooq.com/q/d/l/?s=iau.us&d1=20260120&d2=20260219&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-17
- QQQ.close: 601.300000
- QQQ.signal: NEAR_LOWER_BAND (MONITOR)
- QQQ.z: -1.520671
- QQQ.position_in_band: 0.116411
- QQQ.dist_to_lower: 0.781000
- QQQ.dist_to_upper: 5.927000
- VXN.data_date: 2026-02-18
- VXN.value: 24.960000
- VXN.signal: NORMAL_RANGE (position_in_band=0.747461)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-11
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 699292298413
- turnover_unit: TWD
- volume_multiplier: 0.888
- vol_multiplier: 0.888
- amplitude_pct: 1.924
- pct_change: 1.611
- close: 33605.71
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
- realized_vol_N_annualized_pct: 23.798714
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -2.803763
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-13
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.425000
- spot_sell: 31.575000
- mid: 31.500000
- ret1_pct: 0.174909 (from 2026-02-12 to 2026-02-13)
- chg_5d_pct: -0.568182 (from 2026-02-06 to 2026-02-13)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-19T15:13:46Z

<!-- rendered_at_utc: 2026-02-19T16:13:03Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
