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
- unified_generated_at_utc: 2026-02-23T23:09:38Z

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
- trend_basis: market_cache.SP500.signal=ALERT, tag=JUMP_ZD,JUMP_P, p252=79.365079, p252_on_threshold=80.0, data_date=2026-02-23
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=19.090000, ret1%60=-5.635195, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-20)
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
- date_alignment: twmargin_date=2026-02-23, roll25_used_date=2026-02-23, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-23T23:04:43Z
- run_ts_utc: 2026-02-23T23:05:31.129801+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@f556989
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP500 | ALERT | HIGH | DOWN | JUMP | 6837.750000 | 2026-02-23 | 0.013369 | -0.791916 | 25.000000 | 79.365079 | -1.197748 | -33.333333 | -1.038569 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | WATCH | WATCH→ALERT | 2 | 3 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | ALERT | LOW | UP | JUMP | 0.830152 | 2026-02-23 | 0.013369 | -1.676733 | 5.000000 | 18.253968 | -0.858768 | -15.000000 | -0.494510 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | DERIVED |
| OFR_FSI | WATCH | HIGH | UP | JUMP | -2.359000 | 2026-02-19 | 0.013369 | 0.599354 | 71.666667 | 25.793651 | 0.687463 | 28.333333 | 5.828343 | abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_P,JUMP_RET | ALERT | ALERT→WATCH | 4 | 5 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | DOWN | JUMP | 19.090000 | 2026-02-20 | 0.013369 | 1.210020 | 86.666667 | 67.857143 | -0.617189 | -5.000000 | -5.635195 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 5 | 6 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-24T07:06:12+08:00
- run_ts_utc: 2026-02-23T23:06:49.188973+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 0
- WATCH: 0
- INFO: 2
- NONE: 11
- CHANGED: 1

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DJIA | INFO | NA | LONG | 49625.970000 | 2026-02-20 | 0.009219 | 1.067945 | 91.666667 | 98.015873 | 0.263171 | 16.666667 | 0.467273 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.470740 | 2026-02-13 | 0.009219 | 1.619892 | 100.000000 | 100.000000 | 0.007684 | 0.000000 | 0.811227 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.860000 | 2026-02-20 | 0.009219 | 0.287183 | 58.333333 | 31.349206 | -0.203186 | -10.000000 | -0.694444 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 62.530000 | 2026-02-17 | 0.009219 | 1.095474 | 80.000000 | 39.285714 | -0.223174 | -6.666667 | -0.824742 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.080000 | 2026-02-20 | 0.009219 | -1.146822 | 15.000000 | 13.492063 | -0.011318 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.480000 | 2026-02-20 | 0.009219 | -0.529751 | 45.000000 | 14.682540 | 0.207755 | 8.333333 | 0.288184 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 117.991700 | 2026-02-20 | 0.009219 | -1.178939 | 21.666667 | 5.158730 | -0.168178 | -1.666667 | -0.206114 | NA | NA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22886.070000 | 2026-02-20 | 0.009219 | -1.217914 | 15.000000 | 71.428571 | 0.465424 | 5.000000 | 0.896453 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6909.510000 | 2026-02-20 | 0.009219 | 0.405832 | 58.333333 | 90.079365 | 0.628219 | 16.666667 | 0.693978 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.620800 | 2026-02-13 | 0.009219 | -0.250970 | 48.333333 | 43.650794 | 0.146568 | 11.666667 | 5.336993 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.600000 | 2026-02-23 | 0.009219 | -1.054511 | 21.666667 | 78.571429 | -0.014294 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.340000 | 2026-02-23 | 0.009219 | -1.181767 | 11.666667 | 78.968254 | -0.512426 | -10.000000 | -12.820513 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 19.090000 | 2026-02-20 | 0.009219 | 1.210020 | 86.666667 | 67.857143 | -0.617189 | -5.000000 | -5.635195 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-24T07:08:46+08:00
- run_ts_utc: 2026-02-23T23:08:50.085138+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@01ec0e4
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.800000 | 2026-02-20 | 0.001135 | -1.661000 | 15.000000 | 19.047619 | 0.258273 | 4.830508 | 0.558659 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.260000 | 2026-02-23 | 0.001135 | -0.486158 | 48.333333 | 19.841270 | -0.466189 | -9.293785 | -0.877193 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-24T07:08:46+08:00
- run_ts_utc: 2026-02-23T23:08:50.138720+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@01ec0e4
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 481.290000 | 2026-02-23 | 0.001150 | 1.777589 | 96.666667 | 99.206349 | 0.343195 | 1.751412 | 2.732182 | P252>=95;abs(ret1%1d)>=2 | LONG_EXTREME,JUMP_RET | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=gld.us&d1=20260124&d2=20260223&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 98.570000 | 2026-02-23 | 0.001150 | 1.776147 | 96.666667 | 99.206349 | 0.341262 | 1.751412 | 2.719883 | P252>=95;abs(ret1%1d)>=2 | LONG_EXTREME,JUMP_RET | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=iau.us&d1=20260124&d2=20260223&i=d |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 100.510000 | 2026-02-23 | 0.001150 | 2.236730 | 96.666667 | 99.206349 | -0.136385 | -1.638418 | -0.029839 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 17 | 18 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260124&d2=20260223&i=d |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 94.890000 | 2026-02-23 | 0.001150 | 2.292835 | 98.333333 | 99.603175 | -0.124277 | 0.028249 | 0.010540 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 17 | 18 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260124&d2=20260223&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-23
- QQQ.close: 603.950000
- QQQ.signal: NEAR_LOWER_BAND (MONITOR)
- QQQ.z: -1.549652
- QQQ.position_in_band: 0.109819
- QQQ.dist_to_lower: 0.626000
- QQQ.dist_to_upper: 5.078000
- VXN.data_date: 2026-02-20
- VXN.value: 24.230000
- VXN.signal: NORMAL_RANGE (position_in_band=0.741192)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-23
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 949992767170
- turnover_unit: TWD
- volume_multiplier: 1.186
- vol_multiplier: 1.186
- amplitude_pct: 1.635
- pct_change: 0.499
- close: 33773.26
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
- realized_vol_N_annualized_pct: 23.062346
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.569814
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-23
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.375000
- spot_sell: 31.525000
- mid: 31.450000
- ret1_pct: -0.158730 (from 2026-02-13 to 2026-02-23)
- chg_5d_pct: -0.237906 (from 2026-02-09 to 2026-02-23)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-23T23:00:32Z

<!-- rendered_at_utc: 2026-02-23T23:09:38Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
