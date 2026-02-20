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
- unified_generated_at_utc: 2026-02-20T16:00:17Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- trend_strong: false
- trend_relaxed: false
- fragility_high: false
- vol_watch: true
- vol_runaway: false
- matrix_cell: Trend=OFF / Fragility=LOW
- mode: DEFENSIVE_DCA

**mode_decision_path**
- triggered: vol_watch downshift => DEFENSIVE_DCA

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=NONE, tag=NA, p252=84.920635, p252_on_threshold=80.0, data_date=2026-02-19
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=20.230000, ret1%60=3.109072, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-19)
- vol_runaway_branch: THRESHOLDS_FAILED (display-only)
- vol_runaway_failed_leg: ret1%60<5.0 (display-only)

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
- as_of_ts: 2026-02-20T03:19:37Z
- run_ts_utc: 2026-02-20T15:50:54.625119+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@e51a55a
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | UP | JUMP | 20.230000 | 2026-02-19 | 12.521563 | 1.827209 | 91.666667 | 73.412698 | 0.267735 | 1.666667 | 3.109072 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 2 | 3 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | WATCH | HIGH | DOWN | JUMP | -2.294000 | 2026-02-17 | 12.521563 | 0.846784 | 80.000000 | 32.936508 | -0.260781 | -8.333333 | -3.800905 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 1 | 2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | NONE | HIGH | DOWN | NONE | 6861.890000 | 2026-02-19 | 12.521563 | -0.222387 | 41.666667 | 84.920635 | -0.321019 | -6.666667 | -0.282214 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.833745 | 2026-02-19 | 12.521563 | -0.868413 | 18.333333 | 29.365079 | -0.120133 | -1.666667 | -0.045359 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-20T21:22:13+08:00
- run_ts_utc: 2026-02-20T14:04:29.586947+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 0
- WATCH: 2
- INFO: 2
- NONE: 9
- CHANGED: 4

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.860000 | 2026-02-18 | 0.703774 | 0.238198 | 56.666667 | 30.952381 | -0.820987 | -30.000000 | -2.721088 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | NA | JUMP | 3.470000 | 2026-02-18 | 0.703774 | -0.763008 | 35.000000 | 10.714286 | 0.805118 | 30.000000 | 1.166181 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | ALERT | ALERT→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | INFO | NA | LONG | 117.525800 | 2026-02-13 | 0.703774 | -1.701334 | 10.000000 | 2.380952 | 0.063373 | 0.000000 | -0.010039 | P252<=5 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.470740 | 2026-02-13 | 0.703774 | 1.619892 | 100.000000 | 100.000000 | 0.007684 | 0.000000 | 0.811227 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 62.530000 | 2026-02-17 | 0.703774 | 1.095474 | 80.000000 | 39.285714 | -0.223174 | -6.666667 | -0.824742 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.090000 | 2026-02-18 | 0.703774 | -1.007086 | 20.000000 | 14.285714 | 0.573054 | 10.000000 | 0.987654 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | JUMP | 49395.160000 | 2026-02-19 | 0.703774 | 0.804774 | 75.000000 | 94.047619 | -0.285022 | -18.333333 | -0.538634 | NA | JUMP_DELTA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22682.730000 | 2026-02-19 | 0.703774 | -1.683339 | 10.000000 | 66.666667 | -0.317424 | -3.333333 | -0.311599 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | NONE | 6861.890000 | 2026-02-19 | 0.703774 | -0.222387 | 41.666667 | 84.920635 | -0.321019 | -6.666667 | -0.282214 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.620800 | 2026-02-13 | 0.703774 | -0.250970 | 48.333333 | 43.650794 | 0.146568 | 11.666667 | 5.336993 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.610000 | 2026-02-19 | 0.703774 | -0.819538 | 25.000000 | 79.761905 | -0.215087 | -6.666667 | -1.612903 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | NONE | 0.390000 | 2026-02-19 | 0.703774 | -0.607392 | 21.666667 | 81.349206 | -0.054751 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 19.620000 | 2026-02-18 | 0.703774 | 1.559474 | 90.000000 | 69.841270 | -0.317566 | -1.666667 | -3.302119 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-20T17:00:25+08:00
- run_ts_utc: 2026-02-20T09:00:30.267171+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@6c29aea
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.800000 | 2026-02-18 | 0.001463 | -1.758005 | 11.666667 | 18.253968 | 0.275528 | 3.192090 | 0.558659 | NA | NA | WATCH | WATCH→NONE | 8 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.290000 | 2026-02-19 | 0.001463 | 0.248698 | 68.333333 | 40.079365 | -0.002230 | 0.536723 | 0.000000 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-20T17:00:26+08:00
- run_ts_utc: 2026-02-20T09:00:30.314528+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@6c29aea
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 99.830000 | 2026-02-19 | 0.001198 | 2.184381 | 95.000000 | 98.809524 | -0.214050 | -1.610169 | -0.179982 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | ALERT→WATCH | 13 | 14 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260121&d2=20260220&i=d |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 94.170000 | 2026-02-19 | 0.001198 | 2.205416 | 95.000000 | 98.015873 | -0.237571 | -1.610169 | -0.211932 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | ALERT→WATCH | 13 | 14 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260121&d2=20260220&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 459.560000 | 2026-02-19 | 0.001198 | 1.214258 | 86.666667 | 96.825397 | 0.016407 | 0.225989 | 0.290216 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 7 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260121&d2=20260220&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 94.120000 | 2026-02-19 | 0.001198 | 1.211558 | 86.666667 | 96.825397 | 0.016125 | 0.225989 | 0.287693 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 7 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260121&d2=20260220&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-20
- QQQ.close: 605.960000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -1.304599
- QQQ.position_in_band: 0.169855
- QQQ.dist_to_lower: 0.968000
- QQQ.dist_to_upper: 4.733000
- VXN.data_date: 2026-02-19
- VXN.value: 25.640000
- VXN.signal: NEAR_UPPER_BAND (WATCH) (position_in_band=0.852962)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-11
- run_day_tag: NON_TRADING_DAY
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
- generated_at_utc: 2026-02-20T15:08:40Z

<!-- rendered_at_utc: 2026-02-20T16:00:18Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
