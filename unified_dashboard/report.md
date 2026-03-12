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
- unified_generated_at_utc: 2026-03-12T16:33:49Z

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
- trend_basis: market_cache.SP500.signal=NONE, tag=NA, p252=69.047619, p252_on_threshold=80.0, data_date=2026-03-11
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=24.230000, ret1%60=-2.807862, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-11)
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
- date_alignment: twmargin_date=2026-03-12, roll25_used_date=2026-03-11, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-03-12T03:18:55Z
- run_ts_utc: 2026-03-12T16:12:28.396762+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@159fc9b
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | UP | LEVEL+JUMP | -0.296000 | 2026-03-09 | 12.892610 | 4.425126 | 100.000000 | 94.047619 | 0.242931 | 0.000000 | 63.092269 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_RET | ALERT | SAME | 7 | 8 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | DOWN | JUMP | 24.230000 | 2026-03-11 | 12.892610 | 1.863091 | 95.000000 | 89.682540 | -0.311005 | -1.666667 | -2.807862 | abs(ret1%1d)>=2 | JUMP_RET | ALERT | ALERT→WATCH | 22 | 23 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.831875 | 2026-03-11 | 12.892610 | -0.891557 | 25.000000 | 27.777778 | 0.337073 | 10.000000 | 0.232415 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |
| SP500 | NONE | HIGH | DOWN | NONE | 6775.800000 | 2026-03-11 | 12.892610 | -1.707028 | 6.666667 | 69.047619 | -0.014233 | 0.000000 | -0.083758 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-12T21:34:55+08:00
- run_ts_utc: 2026-03-12T14:08:23.519348+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 4
- INFO: 1
- NONE: 7
- CHANGED: 4

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 94.650000 | 2026-03-09 | 0.557089 | 4.294184 | 100.000000 | 100.000000 | -0.335029 | 0.000000 | 4.274540 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 3.060000 | 2026-03-10 | 0.557089 | 1.548884 | 91.666667 | 66.269841 | -1.071361 | -8.333333 | -4.075235 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | JUMP_DELTA | ALERT | ALERT→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DJIA | WATCH | NA | LEVEL | 47417.270000 | 2026-03-11 | 0.557089 | -2.289406 | 1.666667 | 69.444444 | -0.317006 | -1.666667 | -0.606290 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | JUMP | 0.500000 | 2026-03-11 | 0.557089 | 0.162022 | 46.666667 | 87.301587 | 0.725144 | 16.666667 | 13.636364 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | LEVEL | 24.930000 | 2026-03-10 | 0.557089 | 2.174096 | 96.666667 | 92.063492 | -0.317322 | -1.666667 | -2.235294 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.458750 | 2026-03-06 | 0.557089 | 1.641639 | 100.000000 | 100.000000 | 0.005256 | 0.000000 | 0.853685 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | JUMP | 4.150000 | 2026-03-10 | 0.557089 | -0.131384 | 45.000000 | 34.920635 | 0.395763 | 16.666667 | 0.728155 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.570000 | 2026-03-10 | 0.557089 | 1.240502 | 91.666667 | 39.285714 | 0.165384 | 6.666667 | 0.280899 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 119.491000 | 2026-03-06 | 0.557089 | 0.482291 | 56.666667 | 13.492063 | -0.043063 | -1.666667 | -0.064649 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22716.130000 | 2026-03-11 | 0.557089 | -1.106470 | 21.666667 | 65.079365 | 0.085524 | 1.666667 | 0.083843 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | NONE | 6775.800000 | 2026-03-11 | 0.557089 | -1.707028 | 6.666667 | 69.047619 | -0.014233 | 0.000000 | -0.083758 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.427900 | 2026-03-06 | 0.557089 | 0.476401 | 75.000000 | 67.063492 | 0.040423 | 0.000000 | 3.539225 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.570000 | 2026-03-11 | 0.557089 | -1.630609 | 8.333333 | 67.460317 | -0.145619 | -1.666667 | -1.724138 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |

- fallback_policy: display_only_reference
- fallback_note: fallback values are shown for freshness reference only; not used for signal/z/p calculations
- fallback_source: fallback_cache/latest.json

### fred_cache fallback references (display-only; not used for signal/z/p calculations)
- policy: only show when fallback.data_date > fred.data_date
- note: fallback is for freshness reference only; may be downgraded / unofficial depending on source

| series | primary_date | primary_value | fallback_date | fallback_value | gap_days | fallback_note | fallback_source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DJIA | 2026-03-11 | 47417.270000 | 2026-03-12 | 46752.040000 | 1 | WARN:nonofficial_stooq(^dji);derived_1d_pct | unofficial_reference |
| VIXCLS | 2026-03-10 | 24.930000 | 2026-03-11 | 24.230000 | 1 | WARN:fallback_cboe_vix | official_alt_source |
| DGS10 | 2026-03-10 | 4.150000 | 2026-03-11 | 4.210000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| DGS2 | 2026-03-10 | 3.570000 | 2026-03-11 | 3.640000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| NASDAQCOM | 2026-03-11 | 22716.130000 | 2026-03-12 | 22315.770000 | 1 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | unofficial_reference |
| SP500 | 2026-03-11 | 6775.800000 | 2026-03-12 | 6685.220000 | 1 | WARN:nonofficial_stooq(^spx);derived_1d_pct | unofficial_reference |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-12T17:03:27+08:00
- run_ts_utc: 2026-03-12T09:03:31.159528+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@5bf26a9
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | WATCH | MOVE | JUMP | 1.820000 | 2026-03-10 | 0.001155 | -0.789931 | 30.000000 | 28.571429 | 0.645138 | 14.745763 | 2.247191 | abs(ret1%1d)>=2 | JUMP_RET | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | WATCH | MOVE | JUMP | 2.360000 | 2026-03-11 | 0.001155 | 1.656075 | 100.000000 | 80.555556 | 0.687758 | 20.338983 | 1.287554 | abs(PΔ60)>=15 | JUMP_P | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-12T17:03:28+08:00
- run_ts_utc: 2026-03-12T09:03:31.214035+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@5bf26a9
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | INFO | MOVE | LONG | 476.240000 | 2026-03-11 | 0.000893 | 1.103807 | 88.333333 | 97.222222 | -0.073587 | -3.192090 | -0.339011 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260210&d2=20260312&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 97.550000 | 2026-03-11 | 0.000893 | 1.104871 | 88.333333 | 97.222222 | -0.066994 | -3.192090 | -0.296402 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260210&d2=20260312&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 98.010000 | 2026-03-11 | 0.000893 | 0.416505 | 63.333333 | 89.682540 | -0.419152 | -9.548023 | -1.104889 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260210&d2=20260312&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 92.650000 | 2026-03-11 | 0.000893 | 0.461830 | 66.666667 | 90.476190 | -0.395548 | -6.214689 | -1.036103 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260210&d2=20260312&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-12
- QQQ.close: 598.620000
- QQQ.signal: NEAR_LOWER_BAND (MONITOR)
- QQQ.z: -1.721260
- QQQ.position_in_band: 0.067773
- QQQ.dist_to_lower: 0.414000
- QQQ.dist_to_upper: 5.690000
- VXN.data_date: 2026-03-11
- VXN.value: 26.820000
- VXN.signal: NORMAL_RANGE (position_in_band=0.788276)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-11
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 693435834178
- turnover_unit: TWD
- volume_multiplier: 0.828
- vol_multiplier: 0.828
- amplitude_pct: 3.327
- pct_change: 4.096
- close: 34114.19
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
- realized_vol_N_annualized_pct: 46.353644
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -9.329712
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-12
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.775000
- spot_sell: 31.925000
- mid: 31.850000
- ret1_pct: 0.378191 (from 2026-03-11 to 2026-03-12)
- chg_5d_pct: 0.536616 (from 2026-03-05 to 2026-03-12)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-12T15:30:41Z

<!-- rendered_at_utc: 2026-03-12T16:33:49Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
