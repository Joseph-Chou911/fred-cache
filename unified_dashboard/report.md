# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-10T04:53:16Z

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
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, p252=97.619048, p252_on_threshold=80.0, data_date=2026-02-09
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=17.360000, ret1%60=-2.252252, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-09)
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
- date_alignment: twmargin_date=2026-02-09, roll25_used_date=2026-02-09, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-10T04:42:44Z
- run_ts_utc: 2026-02-10T04:51:52.713870+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@c0269b8
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | UP | JUMP | -1.932000 | 2026-02-05 | 0.152421 | 1.373638 | 88.333333 | 53.968254 | 1.021995 | 11.666667 | 15.816993 | abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | JUMP_ZD,JUMP_RET | ALERT | SAME | 1 | 2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | DOWN | JUMP | 17.360000 | 2026-02-09 | 0.152421 | 0.120514 | 73.333333 | 52.380952 | -0.128473 | -3.333333 | -2.252252 | abs(ret1%60)>=2 | JUMP_RET | ALERT | ALERT→WATCH | 11 | 12 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | INFO | HIGH | UP | LONG | 6964.820000 | 2026-02-09 | 0.152421 | 1.085729 | 90.000000 | 97.619048 | 0.296466 | 10.000000 | 0.469108 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.842127 | 2026-02-09 | 0.152421 | 0.782111 | 76.666667 | 67.460317 | 0.142694 | 5.000000 | 0.115280 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-10T07:50:23+08:00
- run_ts_utc: 2026-02-09T23:58:50.236158+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 5
- INFO: 2
- NONE: 5
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 118.240700 | 2026-02-06 | 0.139788 | -3.111191 | 3.333333 | 0.793651 | 0.769812 | 1.666667 | 0.289314 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.870000 | 2026-02-06 | 0.139788 | -0.090446 | 50.000000 | 32.936508 | -0.691538 | -26.666667 | -3.367003 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DJIA | WATCH | NA | LONG | 50115.670000 | 2026-02-06 | 0.139788 | 1.822800 | 100.000000 | 100.000000 | 1.160921 | 33.333333 | 2.467760 | P252>=95;abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | LONG_EXTREME | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 23031.210000 | 2026-02-06 | 0.139788 | -0.662324 | 25.000000 | 77.380952 | 1.293132 | 18.333333 | 2.176607 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | LONG | 6932.300000 | 2026-02-06 | 0.139788 | 0.789264 | 80.000000 | 95.238095 | 1.333404 | 58.333333 | 1.969581 | P252>=95;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | LONG_EXTREME | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 17.760000 | 2026-02-06 | 0.139788 | 0.239328 | 76.666667 | 57.539683 | -1.465905 | -15.000000 | -18.419844 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.477850 | 2026-01-30 | 0.139788 | 1.475645 | 100.000000 | 100.000000 | 0.026390 | 1.666667 | 1.056010 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.740000 | 2026-02-09 | 0.139788 | 1.462452 | 100.000000 | 100.000000 | 0.249523 | 5.000000 | 2.777778 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 61.600000 | 2026-02-02 | 0.139788 | 1.405252 | 91.666667 | 26.984127 | 0.661998 | 15.000000 | 1.885544 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.220000 | 2026-02-06 | 0.139788 | 0.824070 | 80.000000 | 43.253968 | 0.117278 | 1.666667 | 0.237530 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.500000 | 2026-02-06 | 0.139788 | -0.454274 | 38.333333 | 13.888889 | 0.595679 | 11.666667 | 0.864553 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.678400 | 2026-01-30 | 0.139788 | -0.488886 | 33.333333 | 35.317460 | 0.145199 | 5.000000 | 4.759231 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | NONE | 0.530000 | 2026-02-09 | 0.139788 | 0.572817 | 65.000000 | 91.666667 | -0.087296 | -8.333333 | -1.851852 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-10T11:31:06+08:00
- run_ts_utc: 2026-02-10T03:31:11.018376+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@e00029c
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.880000 | 2026-02-06 | 0.001394 | -0.165420 | 41.666667 | 37.301587 | -0.227506 | -4.096045 | -0.529101 | NA | NA | ALERT | ALERT→NONE | 3 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.350000 | 2026-02-09 | 0.001394 | 1.726968 | 95.000000 | 69.841270 | 0.179874 | 5.169492 | 0.427350 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-10T11:31:07+08:00
- run_ts_utc: 2026-02-10T03:31:11.065573+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@e00029c
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNQ.US_CLOSE | ALERT | MOVE | LONG | 92.640000 | 2026-02-09 | 0.001129 | 2.679018 | 100.000000 | 95.634921 | 0.188442 | 1.694915 | 0.422764 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 3 | 4 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260111&d2=20260210&i=d |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 98.060000 | 2026-02-09 | 0.001129 | 2.462859 | 98.333333 | 97.222222 | 0.208433 | 0.028249 | 0.419867 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | ALERT→WATCH | 3 | 4 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260111&d2=20260210&i=d |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 467.030000 | 2026-02-09 | 0.001129 | 1.775285 | 95.000000 | 98.809524 | 0.313762 | 3.474576 | 2.540289 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=gld.us&d1=20260111&d2=20260210&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 95.630000 | 2026-02-09 | 0.001129 | 1.770749 | 95.000000 | 98.809524 | 0.315468 | 3.474576 | 2.552279 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=iau.us&d1=20260111&d2=20260210&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-09
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 653957736705
- turnover_unit: TWD
- volume_multiplier: 0.828
- vol_multiplier: 0.828
- amplitude_pct: 2.233
- pct_change: 1.956
- close: 32404.62
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
- realized_vol_N_annualized_pct: 21.704867
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -3.596502
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-10
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.515000
- spot_sell: 31.615000
- mid: 31.565000
- ret1_pct: 0.126883 (from 2026-02-09 to 2026-02-10)
- chg_5d_pct: 0.047544 (from 2026-02-03 to 2026-02-10)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-09T23:36:05Z

<!-- rendered_at_utc: 2026-02-10T04:53:16Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
