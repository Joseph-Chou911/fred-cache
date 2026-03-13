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
- unified_generated_at_utc: 2026-03-13T16:02:08Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- trend_strong: false
- trend_relaxed: false
- fragility_high: true
- vol_watch: false
- vol_runaway: true
- matrix_cell: Trend=OFF / Fragility=HIGH
- mode: PAUSE_RISK_ON

**mode_decision_path**
- triggered: vol_runaway override

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=ALERT, tag=EXTREME_Z,JUMP_ZD, p252=59.523810, p252_on_threshold=80.0, data_date=2026-03-12
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=WATCH)=true
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=27.290000, ret1%60=12.628972, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-12)
- vol_runaway_branch: SIGNAL_ALERT_OVERRIDE (display-only)
- vol_runaway_note: signal=ALERT triggers runaway by policy; thresholds shown for reference only (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: MARKET_SHOCK_ONLY
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-03-13, roll25_used_date=2026-03-12, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-03-13T03:16:10Z
- run_ts_utc: 2026-03-13T15:56:46.179597+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@60e7331
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | UP | LEVEL+JUMP | 27.290000 | 2026-03-12 | 12.676717 | 2.576677 | 98.333333 | 94.047619 | 0.713586 | 3.333333 | 12.628972 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_RET | WATCH | WATCH→ALERT | 23 | 24 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | ALERT | HIGH | DOWN | JUMP | -1.458000 | 2026-03-10 | 12.676717 | 1.855683 | 95.000000 | 80.158730 | -2.569443 | -5.000000 | -392.567568 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_RET | ALERT | SAME | 8 | 9 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | ALERT | HIGH | DOWN | LEVEL+JUMP | 6672.620000 | 2026-03-12 | 12.676717 | -3.028575 | 1.666667 | 59.523810 | -1.321547 | -5.000000 | -1.522772 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75 | EXTREME_Z,JUMP_ZD | ALERT | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.829240 | 2026-03-12 | 12.676717 | -1.281028 | 11.666667 | 17.857143 | -0.389470 | -13.333333 | -0.316724 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-13T21:22:16+08:00
- run_ts_utc: 2026-03-13T14:04:36.392796+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 4
- WATCH: 4
- INFO: 1
- NONE: 4
- CHANGED: 8

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 94.650000 | 2026-03-09 | 0.705109 | 4.294184 | 100.000000 | 100.000000 | -0.335029 | 0.000000 | 4.274540 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DJIA | ALERT | NA | LEVEL | 46677.850000 | 2026-03-12 | 0.705109 | -3.090114 | 1.666667 | 63.095238 | -0.800708 | 0.000000 | -1.559390 | abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| SP500 | ALERT | NA | LEVEL | 6672.620000 | 2026-03-12 | 0.705109 | -3.028575 | 1.666667 | 59.523810 | -1.321547 | -5.000000 | -1.522772 | abs(Z60)>=2.5 | EXTREME_Z | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | ALERT | NA | LEVEL | 0.510000 | 2026-03-12 | 0.705109 | -2.559814 | 1.666667 | 29.365079 | -0.929205 | -6.666667 | -10.526316 | abs(Z60)>=2.5 | EXTREME_Z | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | JUMP | 4.210000 | 2026-03-11 | 0.705109 | 0.652715 | 75.000000 | 47.619048 | 0.784099 | 30.000000 | 1.445783 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | NA | LEVEL | 3.640000 | 2026-03-11 | 0.705109 | 2.373336 | 100.000000 | 53.174603 | 1.132834 | 8.333333 | 1.960784 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | LEVEL | 22311.980000 | 2026-03-12 | 0.705109 | -2.011867 | 1.666667 | 52.777778 | -0.905397 | -20.000000 | -1.779132 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | JUMP | 0.550000 | 2026-03-12 | 0.705109 | 0.772931 | 80.000000 | 94.841270 | 0.610909 | 33.333333 | 10.000000 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.458750 | 2026-03-06 | 0.705109 | 1.641639 | 100.000000 | 100.000000 | 0.005256 | 0.000000 | 0.853685 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 3.090000 | 2026-03-11 | 0.705109 | 1.741160 | 93.333333 | 68.650794 | 0.192276 | 1.666667 | 0.980392 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 119.491000 | 2026-03-06 | 0.705109 | 0.482291 | 56.666667 | 13.492063 | -0.043063 | -1.666667 | -0.064649 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.427900 | 2026-03-06 | 0.705109 | 0.476401 | 75.000000 | 67.063492 | 0.040423 | 0.000000 | 3.539225 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 24.230000 | 2026-03-11 | 0.705109 | 1.863091 | 95.000000 | 89.682540 | -0.311005 | -1.666667 | -2.807862 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

- fallback_policy: display_only_reference
- fallback_note: fallback values are shown for freshness reference only; not used for signal/z/p calculations
- fallback_source: fallback_cache/latest.json

### fred_cache fallback references (display-only; not used for signal/z/p calculations)
- policy: only show when fallback.data_date > fred.data_date
- note: fallback is for freshness reference only; may be downgraded / unofficial depending on source

| series | primary_date | primary_value | fallback_date | fallback_value | gap_days | fallback_note | fallback_source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DJIA | 2026-03-12 | 46677.850000 | 2026-03-13 | 46700.480000 | 1 | WARN:nonofficial_stooq(^dji);derived_1d_pct | unofficial_reference |
| SP500 | 2026-03-12 | 6672.620000 | 2026-03-13 | 6659.590000 | 1 | WARN:nonofficial_stooq(^spx);derived_1d_pct | unofficial_reference |
| DGS10 | 2026-03-11 | 4.210000 | 2026-03-12 | 4.270000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| DGS2 | 2026-03-11 | 3.640000 | 2026-03-12 | 3.760000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| NASDAQCOM | 2026-03-12 | 22311.980000 | 2026-03-13 | 22220.719000 | 1 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | unofficial_reference |
| VIXCLS | 2026-03-11 | 24.230000 | 2026-03-12 | 27.290000 | 1 | WARN:fallback_cboe_vix | official_alt_source |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-13T16:59:56+08:00
- run_ts_utc: 2026-03-13T09:00:01.232371+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@604a732
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | WATCH | MOVE | LEVEL | 2.380000 | 2026-03-12 | 0.001453 | 2.030426 | 100.000000 | 89.285714 | 0.392857 | 0.000000 | 0.847458 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 1 | 2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.850000 | 2026-03-11 | 0.001453 | -0.302223 | 33.333333 | 35.714286 | 0.476353 | 2.824859 | 1.648352 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-13T16:59:57+08:00
- run_ts_utc: 2026-03-13T09:00:01.285928+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@604a732
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | WATCH | MOVE | JUMP | 466.880000 | 2026-03-12 | 0.001191 | 0.776450 | 70.000000 | 92.857143 | -0.314070 | -18.135593 | -1.944398 | abs(PΔ60)>=15 | JUMP_P | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=gld.us&d1=20260211&d2=20260313&i=d |
| IAU.US_CLOSE | WATCH | MOVE | JUMP | 95.650000 | 2026-03-12 | 0.001191 | 0.780160 | 71.666667 | 93.253968 | -0.311437 | -16.468927 | -1.927217 | abs(PΔ60)>=15 | JUMP_P | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=iau.us&d1=20260211&d2=20260313&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 97.320000 | 2026-03-12 | 0.001191 | 0.141429 | 60.000000 | 83.333333 | -0.260060 | -2.711864 | -0.693807 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260211&d2=20260313&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 92.010000 | 2026-03-12 | 0.001191 | 0.175998 | 60.000000 | 84.126984 | -0.270570 | -6.101695 | -0.717755 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260211&d2=20260313&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-13
- QQQ.close: 597.520000
- QQQ.signal: NEAR_LOWER_BAND (MONITOR)
- QQQ.z: -1.763874
- QQQ.position_in_band: 0.057344
- QQQ.dist_to_lower: 0.361000
- QQQ.dist_to_upper: 5.940000
- VXN.data_date: 2026-03-12
- VXN.value: 29.830000
- VXN.signal: NEAR_UPPER_BAND (WATCH) (position_in_band=0.988824)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-12
- run_day_tag: NON_TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 784007384475
- turnover_unit: TWD
- volume_multiplier: 0.935
- vol_multiplier: 0.935
- amplitude_pct: 1.644
- pct_change: -1.560
- close: 33581.86
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
- realized_vol_N_annualized_pct: 45.072588
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -9.329712
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-13
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.840000
- spot_sell: 31.990000
- mid: 31.915000
- ret1_pct: 0.204082 (from 2026-03-12 to 2026-03-13)
- chg_5d_pct: 0.741793 (from 2026-03-06 to 2026-03-13)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-13T15:09:41Z

<!-- rendered_at_utc: 2026-03-13T16:02:08Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
