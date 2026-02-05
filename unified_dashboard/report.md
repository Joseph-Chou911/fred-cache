# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-05T12:08:07Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-05.3
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
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, p252=88.888889, p252_on_threshold=80.0, data_date=2026-02-04
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=18.000000, ret1%60=10.159119, runaway_thresholds: ret1%60>=5.0, value>=20.0, data_date=2026-02-03)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: WATCH
- consistency: DIVERGENCE
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-04, roll25_used_date=2026-02-04, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-04T23:00:37Z
- run_ts_utc: 2026-02-04T23:01:14.346129+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@8866958
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4
- reading_note: JUMP tags indicate large recent change (delta/return), not necessarily high level; use p252/z60 for level context.
- reading_note: risk_impulse is display-only; combines dir (riskier direction) with sign(ret1%60) to reduce misread.

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | UP | JUMP | 18.000000 | 2026-02-03 | 0.010374 | 0.382153 | 81.666667 | 60.317460 | 0.627616 | 35.000000 | 10.159119 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 5 | 6 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | WATCH | HIGH | DOWN | JUMP | -2.326000 | 2026-02-02 | 0.010374 | 0.259891 | 71.666667 | 27.777778 | -0.196811 | -8.333333 | -3.148559 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 2 | 3 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | WATCH | HIGH | DOWN | JUMP | 6882.720000 | 2026-02-04 | 0.010374 | 0.317049 | 56.666667 | 88.888889 | -0.369409 | -15.000000 | -0.507241 | abs(PΔ60)>=15 | JUMP_P | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.843838 | 2026-02-04 | 0.010374 | 1.139057 | 80.000000 | 73.015873 | -0.234424 | -5.000000 | -0.133949 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-05T06:58:14+08:00
- run_ts_utc: 2026-02-04T22:59:04.265802+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 2
- INFO: 4
- NONE: 6
- CHANGED: 3

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 117.899600 | 2026-01-30 | 0.013407 | -3.881004 | 1.666667 | 0.396825 | -1.285427 | 0.000000 | -1.161834 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 23255.190000 | 2026-02-03 | 0.013407 | -0.134793 | 36.666667 | 81.746032 | -0.890634 | -45.000000 | -1.428105 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 18.000000 | 2026-02-03 | 0.013407 | 0.360793 | 80.000000 | 60.317460 | 0.627429 | 35.000000 | 10.159119 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49240.990000 | 2026-02-03 | 0.013407 | 1.071670 | 85.000000 | 96.428571 | -0.207673 | -6.666667 | -0.337336 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.477850 | 2026-01-30 | 0.013407 | 1.475645 | 100.000000 | 100.000000 | 0.026390 | 1.666667 | 1.056010 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.720000 | 2026-02-04 | 0.013407 | 1.309592 | 96.666667 | 99.206349 | 0.107630 | 3.333333 | 1.408451 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.600000 | 2026-02-04 | 0.013407 | 1.072501 | 100.000000 | 100.000000 | 0.024151 | 3.333333 | 1.694915 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.850000 | 2026-02-03 | 0.013407 | -0.270843 | 43.333333 | 30.555556 | 0.300159 | 10.000000 | 1.423488 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 61.600000 | 2026-02-02 | 0.013407 | 1.405252 | 91.666667 | 26.984127 | 0.661998 | 15.000000 | 1.885544 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.280000 | 2026-02-03 | 0.013407 | 1.828409 | 96.666667 | 57.142857 | -0.241620 | -1.666667 | -0.233100 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.570000 | 2026-02-03 | 0.013407 | 0.811513 | 78.333333 | 29.761905 | 0.005435 | 1.666667 | 0.000000 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6917.810000 | 2026-02-03 | 0.013407 | 0.686458 | 71.666667 | 93.253968 | -0.601818 | -23.333333 | -0.840400 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.678400 | 2026-01-30 | 0.013407 | -0.488886 | 33.333333 | 35.317460 | 0.145199 | 5.000000 | 4.759231 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-05T17:04:20+08:00
- run_ts_utc: 2026-02-05T09:04:24.498158+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@299a1be
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.920000 | 2026-02-03 | 0.001249 | 0.814751 | 85.000000 | 50.396825 | -0.465035 | -11.610169 | -1.030928 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.350000 | 2026-02-04 | 0.001249 | 1.893288 | 95.000000 | 68.650794 | -0.332217 | -5.000000 | -0.423729 | NA | NA | WATCH | WATCH→NONE | 8 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-05T17:04:20+08:00
- run_ts_utc: 2026-02-05T09:04:24.546536+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@299a1be
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | JUMP | 96.360000 | 2026-02-04 | 0.001263 | 1.181369 | 88.333333 | 77.380952 | 1.270761 | 37.485876 | 1.452632 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260106&d2=20260205&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | JUMP | 90.950000 | 2026-02-04 | 0.001263 | 1.269685 | 90.000000 | 70.238095 | 1.356164 | 35.762712 | 1.450084 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260106&d2=20260205&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 453.970000 | 2026-02-04 | 0.001263 | 1.519945 | 90.000000 | 97.619048 | -0.057064 | -1.525424 | -0.088038 | P252>=95 | LONG_EXTREME | ALERT | ALERT→INFO | 11 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260106&d2=20260205&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 92.920000 | 2026-02-04 | 0.001263 | 1.514845 | 90.000000 | 97.619048 | -0.062868 | -1.525424 | -0.128935 | P252>=95 | LONG_EXTREME | ALERT | ALERT→INFO | 11 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260106&d2=20260205&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-04
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 704644032693
- turnover_unit: TWD
- volume_multiplier: 0.891
- vol_multiplier: 0.891
- amplitude_pct: 1.360
- pct_change: 0.293
- close: 32289.81
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
- realized_vol_N_annualized_pct: 19.613013
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -3.596502
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-05
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.575000
- spot_sell: 31.725000
- mid: 31.650000
- ret1_pct: 0.301062 (from 2026-02-04 to 2026-02-05)
- chg_5d_pct: 1.118211 (from 2026-01-29 to 2026-02-05)
- dir: TWD_WEAK
- fx_signal: INFO
- fx_reason: abs(chg_5d%)>=1.0 OR abs(ret1%)>=0.7
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-05T10:28:53Z

<!-- rendered_at_utc: 2026-02-05T12:08:07Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
