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
- unified_generated_at_utc: 2026-03-08T11:12:50Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- trend_strong: false
- trend_relaxed: false
- fragility_high: false
- vol_watch: false
- vol_runaway: true
- matrix_cell: Trend=OFF / Fragility=LOW
- mode: PAUSE_RISK_ON

**mode_decision_path**
- triggered: vol_runaway override

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=ALERT, tag=EXTREME_Z,JUMP_ZD, p252=67.857143, p252_on_threshold=80.0, data_date=2026-03-06
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=29.490000, ret1%60=24.168421, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-06)
- vol_runaway_branch: SIGNAL_ALERT_OVERRIDE (display-only)
- vol_runaway_note: signal=ALERT triggers runaway by policy; thresholds shown for reference only (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: MARKET_SHOCK_ONLY
- confidence: OK
- dq_reason: NA
- date_alignment: twmargin_date=2026-03-06, roll25_used_date=2026-03-06, used_date_status=LATEST, strict_same_day=true, strict_not_stale=true, strict_roll_match=true
- dq_note: NA

## market_cache (detailed)
- as_of_ts: 2026-03-07T08:50:22Z
- run_ts_utc: 2026-03-07T15:35:34.025103+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@5f7d76a
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP500 | ALERT | HIGH | DOWN | LEVEL+JUMP | 6740.020000 | 2026-03-06 | 6.753340 | -2.490026 | 3.333333 | 67.857143 | -1.423329 | -11.666667 | -1.327680 | abs(Z60)>=2;abs(ZΔ60)>=0.75 | EXTREME_Z,JUMP_ZD | WATCH | WATCH→ALERT | 14 | 15 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | ALERT | HIGH | UP | LEVEL+JUMP | 29.490000 | 2026-03-06 | 6.753340 | 4.022463 | 100.000000 | 94.841270 | 1.494469 | 0.000000 | 24.168421 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 17 | 18 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | ALERT | HIGH | UP | LEVEL+JUMP | -1.190000 | 2026-03-04 | 6.753340 | 4.168326 | 100.000000 | 86.904762 | 0.784595 | 0.000000 | 26.086957 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 2 | 3 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.826188 | 2026-03-06 | 6.753340 | -1.949305 | 5.000000 | 9.523810 | -0.530203 | -5.000000 | -0.430269 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-07T21:07:30+08:00
- run_ts_utc: 2026-03-07T13:46:49.227150+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 4
- INFO: 2
- NONE: 5
- CHANGED: 4

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 71.130000 | 2026-03-02 | 0.651730 | 2.925254 | 100.000000 | 96.825397 | 0.994585 | 0.000000 | 6.227599 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | ALERT | NA | LEVEL | 23.750000 | 2026-03-05 | 0.651730 | 2.527994 | 100.000000 | 90.476190 | 0.891615 | 6.666667 | 12.293144 | abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | WATCH | NA | LEVEL | 47501.550000 | 2026-03-06 | 0.651730 | -2.314159 | 1.666667 | 71.825397 | -0.691586 | -6.666667 | -0.945037 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | LEVEL | 22387.680000 | 2026-03-06 | 0.651730 | -2.058643 | 1.666667 | 55.555556 | -0.826856 | -16.666667 | -1.588246 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | LEVEL | 6740.020000 | 2026-03-06 | 0.651730 | -2.490026 | 3.333333 | 67.857143 | -1.423329 | -11.666667 | -1.327680 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | WATCH | NA | JUMP | -0.443600 | 2026-02-27 | 0.651730 | 0.435979 | 75.000000 | 65.873016 | 0.598967 | 25.000000 | 25.831801 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | INFO | NA | LONG | 117.822300 | 2026-02-27 | 0.651730 | -1.164947 | 18.333333 | 4.365079 | -0.037386 | -3.333333 | -0.069463 | P252<=5 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.462700 | 2026-02-27 | 0.651730 | 1.636383 | 100.000000 | 100.000000 | 0.008649 | 0.000000 | 0.880444 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 3.000000 | 2026-03-05 | 0.651730 | 1.296738 | 93.333333 | 60.317460 | 0.234283 | 5.000000 | 1.010101 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.130000 | 2026-03-05 | 0.651730 | -0.412237 | 30.000000 | 27.777778 | 0.537757 | 6.666667 | 0.977995 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.570000 | 2026-03-05 | 0.651730 | 1.209836 | 90.000000 | 38.095238 | 0.537775 | 13.333333 | 0.847458 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | JUMP | 0.590000 | 2026-03-06 | 0.651730 | -1.312371 | 13.333333 | 75.793651 | 0.594048 | 8.333333 | 5.357143 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.460000 | 2026-03-06 | 0.651730 | -0.329997 | 33.333333 | 84.126984 | 0.361323 | 8.333333 | 6.976744 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

- fallback_policy: display_only_reference
- fallback_note: fallback values are shown for freshness reference only; not used for signal/z/p calculations
- fallback_source: fallback_cache/latest.json

### fred_cache fallback references (display-only; not used for signal/z/p calculations)
- policy: only show when fallback.data_date > fred.data_date
- note: fallback is for freshness reference only; may be downgraded / unofficial depending on source

| series | primary_date | primary_value | fallback_date | fallback_value | gap_days | fallback_note | fallback_source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VIXCLS | 2026-03-05 | 23.750000 | 2026-03-06 | 29.490000 | 1 | WARN:fallback_cboe_vix | official_alt_source |
| DGS10 | 2026-03-05 | 4.130000 | 2026-03-06 | 4.150000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| DGS2 | 2026-03-05 | 3.570000 | 2026-03-06 | 3.560000 | 1 | WARN:fallback_treasury_csv | official_alt_source |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-08T16:49:24+08:00
- run_ts_utc: 2026-03-08T08:49:27.988919+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@d172803
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | ALERT | MOVE | JUMP | 2.350000 | 2026-03-06 | 0.001108 | 1.561484 | 95.000000 | 76.984127 | 0.965362 | 23.813559 | 1.731602 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | ALERT | SAME | 1 | 2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.820000 | 2026-03-05 | 0.001108 | -0.896424 | 25.000000 | 27.777778 | 0.340243 | 1.271186 | 1.111111 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-08T16:49:24+08:00
- run_ts_utc: 2026-03-08T08:49:28.047269+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@d172803
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | INFO | MOVE | LONG | 473.510000 | 2026-03-06 | 0.001124 | 1.117907 | 86.666667 | 96.825397 | 0.210593 | 10.395480 | 1.583249 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260206&d2=20260308&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 96.980000 | 2026-03-06 | 0.001124 | 1.117017 | 86.666667 | 96.825397 | 0.202617 | 10.395480 | 1.528476 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260206&d2=20260308&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 99.020000 | 2026-03-06 | 0.001124 | 0.879458 | 75.000000 | 94.047619 | -0.453319 | -6.355932 | -1.157916 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260206&d2=20260308&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 93.550000 | 2026-03-06 | 0.001124 | 0.907407 | 75.000000 | 94.047619 | -0.429591 | -6.355932 | -1.089025 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260206&d2=20260308&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-06
- QQQ.close: 599.830000
- QQQ.signal: NEAR_LOWER_BAND (MONITOR)
- QQQ.z: -1.718726
- QQQ.position_in_band: 0.068397
- QQQ.dist_to_lower: 0.416000
- QQQ.dist_to_upper: 5.668000
- VXN.data_date: 2026-03-06
- VXN.value: 31.440000
- VXN.signal: UPPER_BAND_TOUCH (STRESS) (position_in_band=1.000000)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-06
- run_day_tag: NON_TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKEND
- tag (legacy): WEEKEND
- roll25_strict_not_stale: true (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 655472934511
- turnover_unit: TWD
- volume_multiplier: 0.761
- vol_multiplier: 0.761
- amplitude_pct: 1.506
- pct_change: -0.218
- close: 33599.54
- LookbackNTarget: 20
- LookbackNActual: 20
- signals.DownDay: true
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: 0
- signals.ConsecutiveBreak: 1
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: 35.927309
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -7.300995
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-06
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.605000
- spot_sell: 31.755000
- mid: 31.680000
- ret1_pct: 0.000000 (from 2026-03-05 to 2026-03-06)
- chg_5d_pct: 1.473414 (from 2026-02-26 to 2026-03-06)
- dir: TWD_WEAK
- fx_signal: INFO
- fx_reason: abs(chg_5d%)>=1.0 OR abs(ret1%)>=0.7
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-07T14:49:44Z

<!-- rendered_at_utc: 2026-03-08T11:12:50Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
