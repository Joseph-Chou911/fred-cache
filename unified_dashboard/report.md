# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-06T06:58:52Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-05.3
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
- trend_basis: market_cache.SP500.signal=ALERT, tag=JUMP_ZD,JUMP_P, p252=78.968254, p252_on_threshold=80.0, data_date=2026-02-05
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=18.640000, ret1%60=3.555556, runaway_thresholds: ret1%60>=5.0, value>=20.0, data_date=2026-02-04)
- vol_runaway_failed_leg: ret1%60<5.0, value<20.0 (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: INFO
- consistency: MARKET_SHOCK_ONLY
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-05, roll25_used_date=2026-02-05, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-06T00:04:18Z
- run_ts_utc: 2026-02-06T00:13:41.304880+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@5d19cba
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP500 | ALERT | HIGH | DOWN | JUMP | 6798.400000 | 2026-02-05 | 0.156474 | -0.544140 | 21.666667 | 78.968254 | -0.861189 | -35.000000 | -1.225097 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | WATCH | WATCH→ALERT | 3 | 4 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | ALERT | LOW | UP | JUMP | 0.838243 | 2026-02-05 | 0.156474 | 0.149980 | 60.000000 | 46.428571 | -1.032583 | -21.666667 | -0.693892 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | DERIVED |
| VIX | WATCH | HIGH | UP | JUMP | 18.640000 | 2026-02-04 | 0.156474 | 0.613716 | 83.333333 | 66.269841 | 0.231563 | 1.666667 | 3.555556 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 7 | 8 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | NONE | HIGH | DOWN | NONE | -2.335000 | 2026-02-03 | 0.156474 | 0.237588 | 71.666667 | 27.777778 | -0.022302 | 0.000000 | -0.386930 | NA | NA | WATCH | WATCH→NONE | 4 | 0 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-06T08:04:55+08:00
- run_ts_utc: 2026-02-06T00:22:16.133849+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 2
- INFO: 3
- NONE: 7
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 117.899600 | 2026-01-30 | 0.288648 | -3.881004 | 1.666667 | 0.396825 | -1.285427 | 0.000000 | -1.161834 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 22904.580000 | 2026-02-04 | 0.288648 | -1.061769 | 16.666667 | 73.809524 | -0.926976 | -20.000000 | -1.507663 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | JUMP | 0.540000 | 2026-02-05 | 0.288648 | 0.686254 | 73.333333 | 93.650794 | -0.386246 | -26.666667 | -10.000000 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | INFO | INFO→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49501.300000 | 2026-02-04 | 0.288648 | 1.294314 | 96.666667 | 99.206349 | 0.222645 | 11.666667 | 0.528645 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.477850 | 2026-01-30 | 0.288648 | 1.475645 | 100.000000 | 100.000000 | 0.026390 | 1.666667 | 1.056010 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.740000 | 2026-02-05 | 0.288648 | 1.556185 | 100.000000 | 100.000000 | 0.246594 | 3.333333 | 2.777778 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.860000 | 2026-02-04 | 0.288648 | -0.183387 | 46.666667 | 32.142857 | 0.087456 | 3.333333 | 0.350877 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 61.600000 | 2026-02-02 | 0.288648 | 1.405252 | 91.666667 | 26.984127 | 0.661998 | 15.000000 | 1.885544 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.290000 | 2026-02-04 | 0.288648 | 1.888579 | 98.333333 | 61.904762 | 0.060170 | 1.666667 | 0.233645 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.570000 | 2026-02-04 | 0.288648 | 0.853017 | 80.000000 | 30.158730 | 0.041503 | 1.666667 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6882.720000 | 2026-02-04 | 0.288648 | 0.317049 | 56.666667 | 88.888889 | -0.369409 | -15.000000 | -0.507241 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.678400 | 2026-01-30 | 0.288648 | -0.488886 | 33.333333 | 35.317460 | 0.145199 | 5.000000 | 4.759231 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 18.640000 | 2026-02-04 | 0.288648 | 0.603571 | 83.333333 | 66.269841 | 0.242778 | 3.333333 | 3.555556 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-06T11:11:36+08:00
- run_ts_utc: 2026-02-06T03:11:39.845067+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@ba737cc
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | WATCH | MOVE | JUMP | 2.320000 | 2026-02-05 | 0.001068 | 1.115888 | 83.333333 | 51.190476 | -0.764342 | -11.581921 | -1.276596 | abs(ZΔ60)>=0.75 | JUMP_ZD | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.940000 | 2026-02-04 | 0.001068 | 1.228060 | 96.666667 | 55.952381 | 0.424834 | 11.920904 | 1.041667 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-06T11:11:36+08:00
- run_ts_utc: 2026-02-06T03:11:39.892690+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@ba737cc
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 442.010000 | 2026-02-05 | 0.001081 | 1.091273 | 83.333333 | 96.031746 | -0.415817 | -6.497175 | -2.630246 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=gld.us&d1=20260107&d2=20260206&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 90.530000 | 2026-02-05 | 0.001081 | 1.090716 | 83.333333 | 96.031746 | -0.411219 | -6.497175 | -2.603550 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=iau.us&d1=20260107&d2=20260206&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 96.150000 | 2026-02-05 | 0.001081 | 0.953559 | 81.666667 | 71.428571 | -0.229307 | -6.468927 | -0.238639 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260107&d2=20260206&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 90.840000 | 2026-02-05 | 0.001081 | 1.132368 | 85.000000 | 68.253968 | -0.137982 | -4.830508 | -0.120946 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260107&d2=20260206&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-05
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 715168705076
- turnover_unit: TWD
- volume_multiplier: 0.907
- vol_multiplier: 0.907
- amplitude_pct: 1.463
- pct_change: -1.513
- close: 31801.27
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
- realized_vol_N_annualized_pct: 19.613013
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -3.596502
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-06
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.640000
- spot_sell: 31.740000
- mid: 31.690000
- ret1_pct: 0.126382 (from 2026-02-05 to 2026-02-06)
- chg_5d_pct: 0.731087 (from 2026-01-30 to 2026-02-06)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-06T06:55:14Z

<!-- rendered_at_utc: 2026-02-06T06:58:52Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
