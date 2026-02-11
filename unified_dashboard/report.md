# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-11T16:35:35Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- trend_strong: true
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
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, p252=95.634921, p252_on_threshold=80.0, data_date=2026-02-10
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=17.790000, ret1%60=2.476959, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-10)
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
- date_alignment: twmargin_date=2026-02-11, roll25_used_date=2026-02-10, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-11T11:59:16Z
- run_ts_utc: 2026-02-11T16:13:21.499615+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@035f6cf
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HYG_IEF_RATIO | ALERT | LOW | UP | JUMP | 0.837633 | 2026-02-10 | 4.234861 | -0.020512 | 55.000000 | 44.841270 | -0.802623 | -21.666667 | -0.533621 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | DERIVED |
| OFR_FSI | WATCH | HIGH | DOWN | JUMP | -2.127000 | 2026-02-06 | 4.234861 | 0.817668 | 86.666667 | 45.238095 | -0.555971 | -1.666667 | -10.093168 | abs(ret1%60)>=2 | JUMP_RET | ALERT | ALERT→WATCH | 2 | 3 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | UP | JUMP | 17.790000 | 2026-02-10 | 4.234861 | 0.293516 | 80.000000 | 57.936508 | 0.173001 | 6.666667 | 2.476959 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 12 | 13 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | INFO | HIGH | DOWN | LONG | 6941.810000 | 2026-02-10 | 4.234861 | 0.836413 | 81.666667 | 95.634921 | -0.249317 | -8.333333 | -0.330375 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-11T21:45:50+08:00
- run_ts_utc: 2026-02-11T14:18:57.272817+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 1
- INFO: 4
- NONE: 7
- CHANGED: 3

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 118.240700 | 2026-02-06 | 0.548965 | -3.111191 | 3.333333 | 0.793651 | 0.769812 | 1.666667 | 0.289314 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | JUMP | 0.470000 | 2026-02-10 | 0.548965 | 0.165554 | 36.666667 | 84.920635 | -0.407263 | -28.333333 | -11.320755 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 50188.140000 | 2026-02-10 | 0.548965 | 1.734173 | 100.000000 | 100.000000 | -0.026052 | 0.000000 | 0.104257 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.474590 | 2026-02-06 | 0.548965 | 1.482931 | 100.000000 | 100.000000 | 0.007286 | 0.000000 | 0.682222 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6941.810000 | 2026-02-10 | 0.548965 | 0.836413 | 81.666667 | 95.634921 | -0.249317 | -8.333333 | -0.330375 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.710000 | 2026-02-10 | 0.548965 | 0.984932 | 86.666667 | 96.825397 | -0.477520 | -13.333333 | -4.054054 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.840000 | 2026-02-09 | 0.548965 | -0.279977 | 41.666667 | 28.174603 | -0.189530 | -8.333333 | -1.045296 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 61.600000 | 2026-02-02 | 0.548965 | 1.405252 | 91.666667 | 26.984127 | 0.661998 | 15.000000 | 1.885544 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.220000 | 2026-02-09 | 0.548965 | 0.799569 | 80.000000 | 43.650794 | -0.024501 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.480000 | 2026-02-09 | 0.548965 | -0.812391 | 33.333333 | 11.904762 | -0.358117 | -5.000000 | -0.571429 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 23102.470000 | 2026-02-10 | 0.548965 | -0.455165 | 28.333333 | 78.174603 | -0.339755 | -8.333333 | -0.586092 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.678400 | 2026-01-30 | 0.548965 | -0.488886 | 33.333333 | 35.317460 | 0.145199 | 5.000000 | 4.759231 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 17.360000 | 2026-02-09 | 0.548965 | 0.094393 | 71.666667 | 52.380952 | -0.144936 | -5.000000 | -2.252252 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-11T17:09:37+08:00
- run_ts_utc: 2026-02-11T09:09:41.077592+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@36b6314
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.870000 | 2026-02-09 | 0.001133 | -0.411347 | 30.000000 | 33.333333 | -0.227154 | -10.677966 | -0.531915 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.320000 | 2026-02-10 | 0.001133 | 0.991069 | 80.000000 | 51.587302 | -0.719114 | -14.915254 | -1.276596 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-11T17:09:37+08:00
- run_ts_utc: 2026-02-11T09:09:41.123846+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@36b6314
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | LONG | 99.320000 | 2026-02-10 | 0.001146 | 3.185970 | 100.000000 | 100.000000 | 0.728058 | 1.694915 | 1.284928 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | WATCH→ALERT | 4 | 5 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260112&d2=20260211&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | LONG | 93.880000 | 2026-02-10 | 0.001146 | 3.411991 | 100.000000 | 98.809524 | 0.734619 | 0.000000 | 1.327720 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260112&d2=20260211&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 462.400000 | 2026-02-10 | 0.001146 | 1.561710 | 91.666667 | 98.015873 | -0.195026 | -3.248588 | -0.991371 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 5 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260112&d2=20260211&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 94.710000 | 2026-02-10 | 0.001146 | 1.561005 | 91.666667 | 98.015873 | -0.191215 | -3.248588 | -0.967270 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 5 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260112&d2=20260211&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-10
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 678490714672
- turnover_unit: TWD
- volume_multiplier: 0.863
- vol_multiplier: 0.863
- amplitude_pct: 1.954
- pct_change: 2.063
- close: 33072.97
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
- realized_vol_N_annualized_pct: 23.635445
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -3.596502
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-11
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.375000
- spot_sell: 31.525000
- mid: 31.450000
- ret1_pct: -0.316957 (from 2026-02-10 to 2026-02-11)
- chg_5d_pct: -0.332752 (from 2026-02-04 to 2026-02-11)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-11T15:34:36Z

<!-- rendered_at_utc: 2026-02-11T16:35:35Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
