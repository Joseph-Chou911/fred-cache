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
- unified_generated_at_utc: 2026-03-09T23:18:26Z

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
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_ZD, p252=70.238095, p252_on_threshold=80.0, data_date=2026-03-09
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
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
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-03-09, roll25_used_date=2026-03-09, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-03-09T22:55:03Z
- run_ts_utc: 2026-03-09T22:56:41.388666+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@e751b02
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | UP | LEVEL+JUMP | 29.490000 | 2026-03-06 | 0.027330 | 4.022463 | 100.000000 | 94.841270 | 1.494469 | 0.000000 | 24.168421 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 19 | 20 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | ALERT | HIGH | DOWN | LEVEL+JUMP | -1.574000 | 2026-03-05 | 0.027330 | 2.665349 | 98.333333 | 76.190476 | -1.502976 | -1.666667 | -32.268908 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 4 | 5 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | WATCH | HIGH | UP | JUMP | 6795.990000 | 2026-03-09 | 0.027330 | -1.526765 | 6.666667 | 70.238095 | 0.963260 | 3.333333 | 0.830413 | abs(ZΔ60)>=0.75 | JUMP_ZD | ALERT | ALERT→WATCH | 16 | 17 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.828613 | 2026-03-09 | 0.027330 | -1.485694 | 10.000000 | 15.873016 | 0.463611 | 5.000000 | 0.293444 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-10T06:57:17+08:00
- run_ts_utc: 2026-03-09T22:59:08.824706+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 5
- INFO: 1
- NONE: 5
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 71.130000 | 2026-03-02 | 0.030229 | 2.925254 | 100.000000 | 96.825397 | 0.994585 | 0.000000 | 6.227599 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | ALERT | NA | LEVEL | 29.490000 | 2026-03-06 | 0.030229 | 4.022463 | 100.000000 | 94.841270 | 1.494469 | 0.000000 | 24.168421 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | LEVEL | 3.130000 | 2026-03-06 | 0.030229 | 2.312625 | 100.000000 | 75.000000 | 1.015888 | 6.666667 | 4.333333 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(ret1%)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DJIA | WATCH | NA | LEVEL | 47501.550000 | 2026-03-06 | 0.030229 | -2.314159 | 1.666667 | 71.825397 | -0.691586 | -6.666667 | -0.945037 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | LEVEL | 22387.680000 | 2026-03-06 | 0.030229 | -2.058643 | 1.666667 | 55.555556 | -0.826856 | -16.666667 | -1.588246 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | LEVEL | 6740.020000 | 2026-03-06 | 0.030229 | -2.490026 | 3.333333 | 67.857143 | -1.423329 | -11.666667 | -1.327680 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | WATCH | NA | JUMP | -0.443600 | 2026-02-27 | 0.030229 | 0.435979 | 75.000000 | 65.873016 | 0.598967 | 25.000000 | 25.831801 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.462700 | 2026-02-27 | 0.030229 | 1.636383 | 100.000000 | 100.000000 | 0.008649 | 0.000000 | 0.880444 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.150000 | 2026-03-06 | 0.030229 | -0.140378 | 43.333333 | 34.126984 | 0.271859 | 13.333333 | 0.484262 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.560000 | 2026-03-06 | 0.030229 | 1.035337 | 83.333333 | 34.523810 | -0.174499 | -6.666667 | -0.280112 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 119.491000 | 2026-03-06 | 0.030229 | 0.482291 | 56.666667 | 13.492063 | -0.043063 | -1.666667 | -0.064649 | NA | NA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | JUMP | 0.560000 | 2026-03-09 | 0.030229 | -1.881484 | 6.666667 | 63.888889 | -0.569113 | -6.666667 | -5.084746 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.410000 | 2026-03-09 | 0.030229 | -0.927734 | 25.000000 | 80.952381 | -0.597737 | -8.333333 | -10.869565 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

- fallback_policy: display_only_reference
- fallback_note: fallback values are shown for freshness reference only; not used for signal/z/p calculations
- fallback_source: fallback_cache/latest.json

### fred_cache fallback references (display-only; not used for signal/z/p calculations)
- policy: only show when fallback.data_date > fred.data_date
- note: fallback is for freshness reference only; may be downgraded / unofficial depending on source

| series | primary_date | primary_value | fallback_date | fallback_value | gap_days | fallback_note | fallback_source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DJIA | 2026-03-06 | 47501.550000 | 2026-03-09 | 47740.800000 | 3 | WARN:nonofficial_stooq(^dji);derived_1d_pct | unofficial_reference |
| NASDAQCOM | 2026-03-06 | 22387.680000 | 2026-03-09 | 22695.945000 | 3 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | unofficial_reference |
| SP500 | 2026-03-06 | 6740.020000 | 2026-03-09 | 6795.990000 | 3 | WARN:nonofficial_stooq(^spx);derived_1d_pct | unofficial_reference |
| DGS10 | 2026-03-06 | 4.150000 | 2026-03-09 | 4.120000 | 3 | WARN:fallback_treasury_csv | official_alt_source |
| DGS2 | 2026-03-06 | 3.560000 | 2026-03-09 | 3.560000 | 3 | WARN:fallback_treasury_csv | official_alt_source |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-10T07:02:02+08:00
- run_ts_utc: 2026-03-09T23:02:06.593769+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@35fc295
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | NONE | MOVE | NONE | 2.340000 | 2026-03-09 | 0.001276 | 1.265928 | 86.666667 | 69.444444 | -0.277126 | -8.248588 | -0.425532 | NA | NA | ALERT | ALERT→NONE | 3 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.800000 | 2026-03-06 | 0.001276 | -1.182506 | 25.000000 | 22.222222 | -0.300773 | -0.423729 | -1.098901 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-10T07:02:03+08:00
- run_ts_utc: 2026-03-09T23:02:06.648770+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@35fc295
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | INFO | MOVE | LONG | 472.530000 | 2026-03-09 | 0.001014 | 1.055435 | 83.333333 | 96.031746 | -0.050270 | -3.107345 | -0.206965 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260207&d2=20260309&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 96.770000 | 2026-03-09 | 0.001014 | 1.053193 | 83.333333 | 96.031746 | -0.051614 | -3.107345 | -0.216539 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260207&d2=20260309&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 99.220000 | 2026-03-09 | 0.001014 | 0.924065 | 75.000000 | 94.047619 | 0.061357 | 0.423729 | 0.201979 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260207&d2=20260309&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 93.770000 | 2026-03-09 | 0.001014 | 0.963596 | 75.000000 | 94.047619 | 0.072995 | 0.423729 | 0.235168 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260207&d2=20260309&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-09
- QQQ.close: 607.710000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -0.810022
- QQQ.position_in_band: 0.291347
- QQQ.dist_to_lower: 1.742000
- QQQ.dist_to_upper: 4.237000
- VXN.data_date: 2026-03-09
- VXN.value: 27.690000
- VXN.signal: NEAR_UPPER_BAND (WATCH) (position_in_band=0.889913)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-09
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 868304737884
- turnover_unit: TWD
- volume_multiplier: 1.008
- vol_multiplier: 1.008
- amplitude_pct: 2.456
- pct_change: -4.432
- close: 32110.42
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
- realized_vol_N_annualized_pct: 41.756984
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -9.329712
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-09
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.845000
- spot_sell: 31.995000
- mid: 31.920000
- ret1_pct: 0.757576 (from 2026-03-06 to 2026-03-09)
- chg_5d_pct: 1.494436 (from 2026-03-02 to 2026-03-09)
- dir: TWD_WEAK
- fx_signal: INFO
- fx_reason: abs(chg_5d%)>=1.0 OR abs(ret1%)>=0.7
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-09T23:07:01Z

<!-- rendered_at_utc: 2026-03-09T23:18:26Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
