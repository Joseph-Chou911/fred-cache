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
- unified_generated_at_utc: 2026-02-23T01:57:55Z

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
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, p252=90.079365, p252_on_threshold=80.0, data_date=2026-02-20
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=19.090000, ret1%60=-5.635195, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-20)
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
- as_of_ts: 2026-02-22T23:29:20Z
- run_ts_utc: 2026-02-22T23:46:50.952463+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@c42b914
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | DOWN | JUMP | -2.505000 | 2026-02-18 | 0.291931 | -0.088110 | 43.333333 | 11.507937 | -0.934894 | -36.666667 | -9.197908 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | ALERT | SAME | 3 | 4 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | DOWN | JUMP | 19.090000 | 2026-02-20 | 0.291931 | 1.210020 | 86.666667 | 67.857143 | -0.617189 | -5.000000 | -5.635195 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 4 | 5 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | WATCH | HIGH | UP | JUMP | 6909.510000 | 2026-02-20 | 0.291931 | 0.405832 | 58.333333 | 90.079365 | 0.628219 | 16.666667 | 0.693978 | abs(PΔ60)>=15 | JUMP_P | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.834277 | 2026-02-20 | 0.291931 | -0.817965 | 20.000000 | 30.555556 | 0.066572 | 1.666667 | 0.074129 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-23T07:54:52+08:00
- run_ts_utc: 2026-02-22T23:57:06.844537+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 0
- WATCH: 0
- INFO: 3
- NONE: 10
- CHANGED: 0

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DJIA | INFO | NA | LONG | 49625.970000 | 2026-02-20 | 0.036901 | 1.067945 | 91.666667 | 98.015873 | 0.263171 | 16.666667 | 0.467273 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | INFO | NA | LONG | 117.525800 | 2026-02-13 | 0.036901 | -1.701334 | 10.000000 | 2.380952 | 0.063373 | 0.000000 | -0.010039 | P252<=5 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.470740 | 2026-02-13 | 0.036901 | 1.619892 | 100.000000 | 100.000000 | 0.007684 | 0.000000 | 0.811227 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.880000 | 2026-02-19 | 0.036901 | 0.490369 | 68.333333 | 36.507937 | 0.252171 | 11.666667 | 0.699301 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 62.530000 | 2026-02-17 | 0.036901 | 1.095474 | 80.000000 | 39.285714 | -0.223174 | -6.666667 | -0.824742 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.080000 | 2026-02-19 | 0.036901 | -1.135503 | 15.000000 | 13.095238 | -0.128417 | -5.000000 | -0.244499 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.470000 | 2026-02-19 | 0.036901 | -0.737507 | 36.666667 | 11.111111 | 0.025501 | 1.666667 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22886.070000 | 2026-02-20 | 0.036901 | -1.217914 | 15.000000 | 71.428571 | 0.465424 | 5.000000 | 0.896453 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6909.510000 | 2026-02-20 | 0.036901 | 0.405832 | 58.333333 | 90.079365 | 0.628219 | 16.666667 | 0.693978 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.620800 | 2026-02-13 | 0.036901 | -0.250970 | 48.333333 | 43.650794 | 0.146568 | 11.666667 | 5.336993 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.600000 | 2026-02-20 | 0.036901 | -1.040217 | 21.666667 | 78.571429 | -0.220680 | -3.333333 | -1.639344 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | NONE | 0.390000 | 2026-02-20 | 0.036901 | -0.669341 | 21.666667 | 81.349206 | -0.061949 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 20.230000 | 2026-02-19 | 0.036901 | 1.827209 | 91.666667 | 73.412698 | 0.267735 | 1.666667 | 3.109072 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-23T09:56:59+08:00
- run_ts_utc: 2026-02-23T01:57:03.195955+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@ac129f5
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.790000 | 2026-02-19 | 0.001166 | -1.886759 | 10.000000 | 15.476190 | -0.131108 | -1.864407 | -0.555556 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.280000 | 2026-02-20 | 0.001166 | 0.000000 | 58.333333 | 30.952381 | -0.232869 | -9.463277 | -0.436681 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-23T09:56:59+08:00
- run_ts_utc: 2026-02-23T01:57:03.244183+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@ac129f5
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 100.540000 | 2026-02-20 | 0.001179 | 2.396595 | 98.333333 | 99.603175 | 0.234263 | 3.418079 | 0.711209 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 16 | 17 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260124&d2=20260223&i=d |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 94.880000 | 2026-02-20 | 0.001179 | 2.440964 | 98.333333 | 99.603175 | 0.257796 | 3.418079 | 0.753956 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 16 | 17 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260124&d2=20260223&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 468.620000 | 2026-02-20 | 0.001179 | 1.446889 | 95.000000 | 98.809524 | 0.245077 | 8.559322 | 1.932073 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260124&d2=20260223&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 95.950000 | 2026-02-20 | 0.001179 | 1.447321 | 95.000000 | 98.809524 | 0.248163 | 8.559322 | 1.954951 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260124&d2=20260223&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-20
- QQQ.close: 608.810000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -0.981162
- QQQ.position_in_band: 0.249454
- QQQ.dist_to_lower: 1.407000
- QQQ.dist_to_upper: 4.232000
- VXN.data_date: 2026-02-20
- VXN.value: 24.230000
- VXN.signal: NORMAL_RANGE (position_in_band=0.741192)

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
- data_date: 2026-02-23
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.450000
- spot_sell: 31.550000
- mid: 31.500000
- ret1_pct: 0.000000 (from 2026-02-13 to 2026-02-23)
- chg_5d_pct: -0.079302 (from 2026-02-09 to 2026-02-23)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-23T01:54:58Z

<!-- rendered_at_utc: 2026-02-23T01:57:55Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
