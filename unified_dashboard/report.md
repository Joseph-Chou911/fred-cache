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
- unified_generated_at_utc: 2026-03-14T15:51:19Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- trend_strong: false
- trend_relaxed: false
- fragility_high: true
- vol_watch: true
- vol_runaway: false
- matrix_cell: Trend=OFF / Fragility=HIGH
- mode: DEFENSIVE_DCA

**mode_decision_path**
- triggered: vol_watch downshift => DEFENSIVE_DCA

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=ALERT, tag=EXTREME_Z, p252=54.761905, p252_on_threshold=80.0, data_date=2026-03-13
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=WATCH)=true
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=27.190000, ret1%60=-0.366435, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-13)
- vol_runaway_branch: THRESHOLDS_FAILED (display-only)
- vol_runaway_failed_leg: ret1%60<5.0 (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: MARKET_SHOCK_ONLY
- confidence: OK
- dq_reason: NA
- date_alignment: twmargin_date=2026-03-13, roll25_used_date=2026-03-13, used_date_status=LATEST, strict_same_day=true, strict_not_stale=true, strict_roll_match=true
- dq_note: NA

## market_cache (detailed)
- as_of_ts: 2026-03-14T03:14:13Z
- run_ts_utc: 2026-03-14T15:40:05.370109+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@aacf9e2
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | UP | LEVEL+JUMP | -0.925000 | 2026-03-11 | 12.431214 | 2.721462 | 96.666667 | 88.888889 | 0.865779 | 1.666667 | 36.556927 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 9 | 10 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | ALERT | HIGH | DOWN | LEVEL | 6632.190000 | 2026-03-13 | 12.431214 | -3.255711 | 1.666667 | 54.761905 | -0.227136 | 0.000000 | -0.605909 | abs(Z60)>=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | 2 | 3 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | WATCH | HIGH | DOWN | LEVEL | 27.190000 | 2026-03-13 | 12.431214 | 2.380320 | 96.666667 | 93.650794 | -0.196358 | -1.666667 | -0.366435 | abs(Z60)>=2 | EXTREME_Z | ALERT | ALERT→WATCH | 24 | 25 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.828539 | 2026-03-13 | 12.431214 | -1.349153 | 10.000000 | 15.873016 | -0.068125 | -1.666667 | -0.084620 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-14T21:13:31+08:00
- run_ts_utc: 2026-03-14T13:52:31.335572+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 5
- WATCH: 4
- INFO: 2
- NONE: 2
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 94.650000 | 2026-03-09 | 0.649538 | 4.294184 | 100.000000 | 100.000000 | -0.335029 | 0.000000 | 4.274540 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS2 | ALERT | NA | LEVEL | 3.760000 | 2026-03-12 | 0.649538 | 3.824702 | 100.000000 | 65.873016 | 1.451366 | 0.000000 | 3.296703 | abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | ALERT | NA | LEVEL | 46558.470000 | 2026-03-13 | 0.649538 | -2.973829 | 1.666667 | 61.111111 | 0.116285 | 0.000000 | -0.255753 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| SP500 | ALERT | NA | LEVEL | 6632.190000 | 2026-03-13 | 0.649538 | -3.255711 | 1.666667 | 54.761905 | -0.227136 | 0.000000 | -0.605909 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | ALERT | NA | LEVEL | 27.290000 | 2026-03-12 | 0.649538 | 2.576677 | 98.333333 | 94.047619 | 0.713586 | 3.333333 | 12.628972 | abs(Z60)>=2.5 | EXTREME_Z | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | LEVEL | 3.170000 | 2026-03-12 | 0.649538 | 2.239939 | 98.333333 | 79.365079 | 0.498778 | 5.000000 | 2.588997 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | JUMP | 4.270000 | 2026-03-12 | 0.649538 | 1.411557 | 93.333333 | 63.492063 | 0.758843 | 18.333333 | 1.425178 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | LEVEL | 22105.360000 | 2026-03-13 | 0.649538 | -2.355827 | 1.666667 | 50.793651 | -0.343960 | 0.000000 | -0.926050 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | WATCH | NA | JUMP | 0.550000 | 2026-03-13 | 0.649538 | -1.764303 | 6.666667 | 58.333333 | 0.795511 | 5.000000 | 7.843137 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | JUMP_DELTA | ALERT | ALERT→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.458750 | 2026-03-06 | 0.649538 | 1.641639 | 100.000000 | 100.000000 | 0.005256 | 0.000000 | 0.853685 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.560000 | 2026-03-13 | 0.649538 | 0.884756 | 83.333333 | 96.031746 | 0.111826 | 3.333333 | 1.818182 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 119.491000 | 2026-03-06 | 0.649538 | 0.482291 | 56.666667 | 13.492063 | -0.043063 | -1.666667 | -0.064649 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.427900 | 2026-03-06 | 0.649538 | 0.476401 | 75.000000 | 67.063492 | 0.040423 | 0.000000 | 3.539225 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |

- fallback_policy: display_only_reference
- fallback_note: fallback values are shown for freshness reference only; not used for signal/z/p calculations
- fallback_source: fallback_cache/latest.json

### fred_cache fallback references (display-only; not used for signal/z/p calculations)
- policy: only show when fallback.data_date > fred.data_date
- note: fallback is for freshness reference only; may be downgraded / unofficial depending on source

| series | primary_date | primary_value | fallback_date | fallback_value | gap_days | fallback_note | fallback_source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DGS2 | 2026-03-12 | 3.760000 | 2026-03-13 | 3.730000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| VIXCLS | 2026-03-12 | 27.290000 | 2026-03-13 | 27.190000 | 1 | WARN:fallback_cboe_vix | official_alt_source |
| DGS10 | 2026-03-12 | 4.270000 | 2026-03-13 | 4.280000 | 1 | WARN:fallback_treasury_csv | official_alt_source |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-14T16:53:35+08:00
- run_ts_utc: 2026-03-14T08:53:39.263260+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@49cb16c
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | WATCH | MOVE | JUMP | 1.890000 | 2026-03-12 | 0.001184 | 0.347068 | 51.666667 | 46.428571 | 0.632742 | 17.768362 | 2.162162 | abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_P,JUMP_RET | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.360000 | 2026-03-13 | 0.001184 | 1.499576 | 98.333333 | 80.158730 | -0.514907 | -1.666667 | -0.840336 | NA | NA | WATCH | WATCH→NONE | 2 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-14T16:53:36+08:00
- run_ts_utc: 2026-03-14T08:53:39.306923+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@49cb16c
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | NONE | MOVE | NONE | 460.840000 | 2026-03-13 | 0.000919 | 0.549041 | 61.666667 | 90.873016 | -0.210538 | -7.824859 | -1.314831 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260212&d2=20260314&i=d |
| IAU.US_CLOSE | NONE | MOVE | NONE | 94.380000 | 2026-03-13 | 0.000919 | 0.547610 | 61.666667 | 90.873016 | -0.215716 | -9.519774 | -1.348385 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260212&d2=20260314&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 97.500000 | 2026-03-13 | 0.000919 | 0.191986 | 60.000000 | 83.730159 | 0.063307 | 0.677966 | 0.174664 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260212&d2=20260314&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 92.160000 | 2026-03-13 | 0.000919 | 0.235866 | 60.000000 | 86.507937 | 0.073076 | 0.677966 | 0.201120 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260212&d2=20260314&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-13
- QQQ.close: 593.720000
- QQQ.signal: LOWER_BAND_TOUCH (MONITOR / SCALE_IN_ONLY)
- QQQ.z: -2.144014
- QQQ.position_in_band: 0.000000
- QQQ.dist_to_lower: -0.224000
- QQQ.dist_to_upper: 6.651000
- VXN.data_date: 2026-03-13
- VXN.value: 29.870000
- VXN.signal: NEAR_UPPER_BAND (WATCH) (position_in_band=0.960165)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-13
- run_day_tag: NON_TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKEND
- tag (legacy): WEEKEND
- roll25_strict_not_stale: true (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 752682671944
- turnover_unit: TWD
- volume_multiplier: 0.902
- vol_multiplier: 0.902
- amplitude_pct: 1.863
- pct_change: -0.541
- close: 33400.32
- LookbackNTarget: 20
- LookbackNActual: 20
- signals.DownDay: true
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: 0
- signals.ConsecutiveBreak: 2
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: 44.974367
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -8.504523
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
- generated_at_utc: 2026-03-14T14:54:53Z

<!-- rendered_at_utc: 2026-03-14T15:51:19Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
