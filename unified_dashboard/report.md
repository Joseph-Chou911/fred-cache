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
- unified_generated_at_utc: 2026-03-01T15:46:17Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- trend_strong: false
- trend_relaxed: true
- fragility_high: true
- vol_watch: true
- vol_runaway: false
- matrix_cell: Trend=ON / Fragility=HIGH
- mode: DEFENSIVE_DCA

**mode_decision_path**
- triggered: vol_watch downshift => DEFENSIVE_DCA

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, p252=84.920635, p252_on_threshold=80.0, data_date=2026-02-27
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=WATCH)=true
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=19.860000, ret1%60=6.602254, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-27)
- vol_runaway_branch: THRESHOLDS_FAILED (display-only)
- vol_runaway_failed_leg: value<20.0 (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: QUIET
- confidence: OK
- dq_reason: NA
- date_alignment: twmargin_date=2026-02-26, roll25_used_date=2026-02-26, used_date_status=LATEST, strict_same_day=true, strict_not_stale=true, strict_roll_match=true
- dq_note: NA

## market_cache (detailed)
- as_of_ts: 2026-03-01T13:56:48Z
- run_ts_utc: 2026-03-01T15:35:10.128966+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@fe3ee5b
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | DOWN | JUMP | -2.601000 | 2026-02-25 | 1.639480 | -0.510445 | 35.000000 | 8.333333 | -1.192663 | -38.333333 | -10.964164 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | ALERT | SAME | 10 | 11 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| HYG_IEF_RATIO | ALERT | LOW | UP | LEVEL+JUMP | 0.823758 | 2026-02-27 | 1.639480 | -2.799425 | 1.666667 | 6.349206 | -0.750161 | 0.000000 | -0.558151 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75 | EXTREME_Z,JUMP_ZD | ALERT | SAME | 2 | 3 | DERIVED |
| VIX | WATCH | HIGH | UP | JUMP | 19.860000 | 2026-02-27 | 1.639480 | 1.379544 | 86.666667 | 73.015873 | 0.537564 | 8.333333 | 6.602254 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 11 | 12 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | WATCH | HIGH | DOWN | JUMP | 6878.880000 | 2026-02-27 | 1.639480 | -0.230106 | 40.000000 | 84.920635 | -0.541274 | -15.000000 | -0.433936 | abs(PΔ60)>=15 | JUMP_P | WATCH | SAME | 8 | 9 | https://stooq.com/q/d/l/?s=^spx&i=d |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-01T22:04:00+08:00
- run_ts_utc: 2026-03-01T14:04:37.003417+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 4
- INFO: 1
- NONE: 7
- CHANGED: 0

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DGS2 | ALERT | NA | LONG | 3.420000 | 2026-02-26 | 0.009723 | -1.630276 | 3.333333 | 1.190476 | -0.534668 | -11.666667 | -0.869565 | P252<=2 | LONG_EXTREME | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | WATCH | NA | LEVEL | 66.360000 | 2026-02-23 | 0.009723 | 2.061338 | 96.666667 | 73.412698 | -0.233722 | -3.333333 | -0.494827 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | LEVEL | 4.020000 | 2026-02-26 | 0.009723 | -2.059105 | 1.666667 | 5.952381 | -0.428980 | -8.333333 | -0.740741 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DJIA | WATCH | NA | JUMP | 48977.920000 | 2026-02-27 | 0.009723 | 0.095192 | 46.666667 | 87.301587 | -0.773551 | -35.000000 | -1.053108 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | LEVEL | 0.300000 | 2026-02-27 | 0.009723 | -2.271100 | 1.666667 | 76.587302 | -0.507735 | -6.666667 | -11.764706 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.466810 | 2026-02-20 | 0.009723 | 1.627734 | 100.000000 | 100.000000 | 0.007842 | 0.000000 | 0.834856 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.980000 | 2026-02-26 | 0.009723 | 1.558634 | 98.333333 | 57.539683 | 0.400502 | 10.000000 | 1.360544 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 117.991700 | 2026-02-20 | 0.009723 | -1.178939 | 21.666667 | 5.158730 | -0.168178 | -1.666667 | -0.206114 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22668.210000 | 2026-02-27 | 0.009723 | -1.674015 | 10.000000 | 63.888889 | -0.525718 | -6.666667 | -0.918640 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6878.880000 | 2026-02-27 | 0.009723 | -0.230106 | 40.000000 | 84.920635 | -0.541274 | -15.000000 | -0.433936 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.598100 | 2026-02-20 | 0.009723 | -0.162989 | 50.000000 | 48.015873 | 0.087982 | 1.666667 | 3.656572 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.590000 | 2026-02-27 | 0.009723 | -1.413669 | 11.666667 | 75.793651 | -0.247132 | -8.333333 | -1.666667 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 18.630000 | 2026-02-26 | 0.009723 | 0.841981 | 78.333333 | 65.476190 | 0.315716 | 1.666667 | 3.904071 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-01T16:48:41+08:00
- run_ts_utc: 2026-03-01T08:48:44.686704+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3770096
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | ALERT | MOVE | LEVEL | 1.740000 | 2026-02-26 | 0.001024 | -2.650358 | 1.666667 | 7.936508 | -0.397822 | -3.418079 | -1.694915 | abs(Z60)>=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | 2 | 3 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | WATCH | MOVE | JUMP | 2.250000 | 2026-02-27 | 0.001024 | -0.819639 | 30.000000 | 16.269841 | -0.731470 | -27.627119 | -1.315789 | abs(PΔ60)>=15 | JUMP_P | WATCH | SAME | 1 | 2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-01T16:48:42+08:00
- run_ts_utc: 2026-03-01T08:48:44.747369+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3770096
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 95.690000 | 2026-02-27 | 0.000763 | 2.169206 | 100.000000 | 100.000000 | -0.031982 | 0.000000 | 0.177973 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 22 | 23 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260130&d2=20260301&i=d |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 101.280000 | 2026-02-27 | 0.000763 | 2.113780 | 100.000000 | 100.000000 | -0.003244 | 1.694915 | 0.227610 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 2 | 3 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260130&d2=20260301&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 483.750000 | 2026-02-27 | 0.000763 | 1.626440 | 96.666667 | 99.206349 | 0.142959 | 1.751412 | 1.313144 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260130&d2=20260301&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 99.070000 | 2026-02-27 | 0.000763 | 1.624861 | 96.666667 | 99.206349 | 0.142391 | 1.751412 | 1.308927 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260130&d2=20260301&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-27
- QQQ.close: 607.290000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -1.084858
- QQQ.position_in_band: 0.223758
- QQQ.dist_to_lower: 1.302000
- QQQ.dist_to_upper: 4.517000
- VXN.data_date: 2026-02-27
- VXN.value: 24.520000
- VXN.signal: NORMAL_RANGE (position_in_band=0.744490)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-26
- run_day_tag: NON_TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKEND
- tag (legacy): WEEKEND
- roll25_strict_not_stale: true (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 1207836722507
- turnover_unit: TWD
- volume_multiplier: 1.452
- vol_multiplier: 1.452
- amplitude_pct: 1.152
- pct_change: 0.004
- close: 35414.49
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
- realized_vol_N_annualized_pct: 20.847361
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.569814
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-26
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.145000
- spot_sell: 31.295000
- mid: 31.220000
- ret1_pct: -0.303369 (from 2026-02-25 to 2026-02-26)
- chg_5d_pct: -0.715535 (from 2026-02-12 to 2026-02-26)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-01T14:50:10Z

<!-- rendered_at_utc: 2026-03-01T15:46:17Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
