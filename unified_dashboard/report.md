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
- unified_generated_at_utc: 2026-03-05T16:09:53Z

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
- trend_basis: market_cache.SP500.signal=ALERT, tag=JUMP_ZD,JUMP_P, p252=82.539683, p252_on_threshold=80.0, data_date=2026-03-04
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=21.150000, ret1%60=-10.267289, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-04)
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
- date_alignment: twmargin_date=2026-03-05, roll25_used_date=2026-03-04, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-03-05T03:16:43Z
- run_ts_utc: 2026-03-05T16:01:17.324766+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@07af7f8
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | UP | LEVEL+JUMP | -1.893000 | 2026-03-02 | 12.742868 | 2.584326 | 100.000000 | 61.111111 | 2.107753 | 31.666667 | 20.662196 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_P,JUMP_RET | NONE | NONE→ALERT | 0 | 1 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | ALERT | HIGH | DOWN | JUMP | 21.150000 | 2026-03-04 | 12.742868 | 1.636378 | 93.333333 | 81.349206 | -1.105828 | -6.666667 | -10.267289 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_RET | ALERT | SAME | 15 | 16 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | ALERT | HIGH | UP | JUMP | 6869.500000 | 2026-03-04 | 12.742868 | -0.404801 | 31.666667 | 82.539683 | 0.924260 | 20.000000 | 0.775603 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | ALERT | SAME | 12 | 13 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | WATCH | LOW | DOWN | JUMP | 0.830493 | 2026-03-04 | 12.742868 | -1.334303 | 11.666667 | 22.222222 | 0.879225 | 8.333333 | 0.567154 | abs(ZΔ60)>=0.75 | JUMP_ZD | WATCH | SAME | 6 | 7 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-05T21:34:36+08:00
- run_ts_utc: 2026-03-05T14:05:22.197967+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 5
- INFO: 2
- NONE: 4
- CHANGED: 6

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 71.130000 | 2026-03-02 | 0.511999 | 2.925254 | 100.000000 | 96.825397 | 0.994585 | 0.000000 | 6.227599 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | ALERT | NA | LEVEL | 23.570000 | 2026-03-03 | 0.511999 | 2.742206 | 100.000000 | 88.888889 | 0.729765 | 1.666667 | 9.934701 | abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | LEVEL | 3.080000 | 2026-03-03 | 0.511999 | 2.078274 | 96.666667 | 66.269841 | 0.363580 | 0.000000 | 1.650165 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 22807.480000 | 2026-03-04 | 0.511999 | -1.122115 | 20.000000 | 68.650794 | 0.806700 | 18.333333 | 1.291442 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | JUMP | 6869.500000 | 2026-03-04 | 0.511999 | -0.404801 | 31.666667 | 82.539683 | 0.924260 | 20.000000 | 0.775603 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | WATCH | NA | JUMP | -0.443600 | 2026-02-27 | 0.511999 | 0.435979 | 75.000000 | 65.873016 | 0.598967 | 25.000000 | 25.831801 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | WATCH | NA | LEVEL | 0.550000 | 2026-03-04 | 0.511999 | -2.132040 | 3.333333 | 60.317460 | 0.064155 | 1.666667 | 0.000000 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | INFO | NA | LONG | 117.822300 | 2026-02-27 | 0.511999 | -1.164947 | 18.333333 | 4.365079 | -0.037386 | -3.333333 | -0.069463 | P252<=5 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.462700 | 2026-02-27 | 0.511999 | 1.636383 | 100.000000 | 100.000000 | 0.008649 | 0.000000 | 0.880444 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.060000 | 2026-03-03 | 0.511999 | -1.360836 | 15.000000 | 14.285714 | 0.134293 | 1.666667 | 0.246914 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | JUMP | 3.510000 | 2026-03-03 | 0.511999 | 0.133601 | 58.333333 | 22.222222 | 0.722497 | 18.333333 | 1.152738 | NA | JUMP_DELTA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | NONE | 48739.410000 | 2026-03-04 | 0.511999 | -0.359320 | 36.666667 | 84.920635 | 0.342007 | 5.000000 | 0.490997 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.380000 | 2026-03-04 | 0.511999 | -1.301308 | 16.666667 | 79.761905 | 0.378147 | 6.666667 | 8.571429 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-05T17:01:53+08:00
- run_ts_utc: 2026-03-05T09:01:57.826286+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@60d87c7
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.770000 | 2026-03-03 | 0.001341 | -1.776408 | 11.666667 | 13.492063 | 0.234656 | 6.581921 | 0.568182 | NA | NA | ALERT | ALERT→NONE | 6 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.290000 | 2026-03-04 | 0.001341 | 0.122834 | 68.333333 | 43.650794 | -0.001052 | 0.536723 | 0.000000 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-05T17:01:54+08:00
- run_ts_utc: 2026-03-05T09:01:58.374489+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@60d87c7
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | INFO | MOVE | LONG | 471.800000 | 2026-03-04 | 0.001215 | 1.124599 | 85.000000 | 96.428571 | 0.087000 | 1.949153 | 0.756055 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 1 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260203&d2=20260305&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 96.650000 | 2026-03-04 | 0.001215 | 1.128230 | 85.000000 | 96.428571 | 0.087568 | 1.949153 | 0.761051 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 1 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260203&d2=20260305&i=d |
| IYR.US_CLOSE | INFO | MOVE | LONG | 101.060000 | 2026-03-04 | 0.001215 | 1.739740 | 95.000000 | 98.809524 | -0.016283 | 1.779661 | 0.113923 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260203&d2=20260305&i=d |
| VNQ.US_CLOSE | INFO | MOVE | LONG | 95.540000 | 2026-03-04 | 0.001215 | 1.798481 | 96.666667 | 99.206349 | -0.016861 | 3.446328 | 0.125760 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260203&d2=20260305&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-05
- QQQ.close: 610.340000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -0.606553
- QQQ.position_in_band: 0.341783
- QQQ.dist_to_lower: 2.005000
- QQQ.dist_to_upper: 3.861000
- VXN.data_date: 2026-03-04
- VXN.value: 24.870000
- VXN.signal: NORMAL_RANGE (position_in_band=0.730439)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-04
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 1099338575770
- turnover_unit: TWD
- volume_multiplier: 1.269
- vol_multiplier: 1.269
- amplitude_pct: 4.078
- pct_change: -4.355
- close: 32828.88
- LookbackNTarget: 20
- LookbackNActual: 20
- signals.DownDay: true
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: 0
- signals.ConsecutiveBreak: 3
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: 36.171813
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -7.300995
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-05
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.605000
- spot_sell: 31.755000
- mid: 31.680000
- ret1_pct: -0.047326 (from 2026-03-04 to 2026-03-05)
- chg_5d_pct: 1.165576 (from 2026-02-25 to 2026-03-05)
- dir: TWD_STRONG
- fx_signal: INFO
- fx_reason: abs(chg_5d%)>=1.0 OR abs(ret1%)>=0.7
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-05T15:25:50Z

<!-- rendered_at_utc: 2026-03-05T16:09:53Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
