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
- unified_generated_at_utc: 2026-02-27T04:04:07Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
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
- trend_basis: market_cache.SP500.signal=WATCH, tag=JUMP_P, p252=89.285714, p252_on_threshold=80.0, data_date=2026-02-26
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=WATCH, dir=HIGH, value=18.630000, ret1%60=3.904071, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-26)
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
- date_alignment: twmargin_date=2026-02-26, roll25_used_date=2026-02-26, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-27T02:52:55Z
- run_ts_utc: 2026-02-27T02:53:43.736574+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@c61b139
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | UP | JUMP | 18.630000 | 2026-02-26 | 0.013538 | 0.841981 | 78.333333 | 65.476190 | 0.315716 | 1.666667 | 3.904071 | abs(ret1%1d)>=2 | JUMP_RET | ALERT | ALERT→WATCH | 9 | 10 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | WATCH | HIGH | DOWN | JUMP | 6908.860000 | 2026-02-26 | 0.013538 | 0.311168 | 55.000000 | 89.285714 | -0.658736 | -30.000000 | -0.536558 | abs(PΔ60)>=15 | JUMP_P | ALERT | ALERT→WATCH | 6 | 7 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | WATCH | LOW | UP | LEVEL | 0.828381 | 2026-02-26 | 0.013538 | -2.049264 | 1.666667 | 13.492063 | -0.570447 | -5.000000 | -0.352668 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | 0 | 1 | DERIVED |
| OFR_FSI | WATCH | HIGH | UP | JUMP | -2.344000 | 2026-02-24 | 0.013538 | 0.682219 | 73.333333 | 28.571429 | 0.242013 | 6.666667 | 2.170284 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 8 | 9 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-27T10:50:14+08:00
- run_ts_utc: 2026-02-27T03:37:31.600457+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 0
- WATCH: 3
- INFO: 2
- NONE: 8
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | WATCH | NA | LEVEL | 66.360000 | 2026-02-23 | 0.787389 | 2.061338 | 96.666667 | 73.412698 | -0.233722 | -3.333333 | -0.494827 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 23152.080000 | 2026-02-25 | 0.787389 | -0.399962 | 31.666667 | 78.571429 | 0.830471 | 16.666667 | 1.261389 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 17.930000 | 2026-02-25 | 0.787389 | 0.526265 | 76.666667 | 59.126984 | -0.788309 | -8.333333 | -8.286445 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49499.200000 | 2026-02-26 | 0.787389 | 0.868743 | 81.666667 | 95.634921 | -0.004367 | 0.000000 | 0.034457 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.466810 | 2026-02-20 | 0.787389 | 1.627734 | 100.000000 | 100.000000 | 0.007842 | 0.000000 | 0.834856 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.940000 | 2026-02-25 | 0.787389 | 1.158132 | 88.333333 | 49.603175 | -0.343646 | -8.333333 | -1.010101 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.050000 | 2026-02-25 | 0.787389 | -1.630125 | 10.000000 | 10.714286 | 0.090906 | 1.666667 | 0.247525 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.450000 | 2026-02-25 | 0.787389 | -1.095608 | 15.000000 | 5.555556 | 0.387826 | 8.333333 | 0.583090 | NA | NA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 117.991700 | 2026-02-20 | 0.787389 | -1.178939 | 21.666667 | 5.158730 | -0.168178 | -1.666667 | -0.206114 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6908.860000 | 2026-02-26 | 0.787389 | 0.311168 | 55.000000 | 89.285714 | -0.658736 | -30.000000 | -0.536558 | NA | JUMP_DELTA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.598100 | 2026-02-20 | 0.787389 | -0.162989 | 50.000000 | 48.015873 | 0.087982 | 1.666667 | 3.656572 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.600000 | 2026-02-26 | 0.787389 | -1.166537 | 20.000000 | 78.174603 | -0.047180 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.340000 | 2026-02-26 | 0.787389 | -1.763365 | 8.333333 | 78.174603 | -0.430627 | -6.666667 | -5.555556 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-27T11:10:27+08:00
- run_ts_utc: 2026-02-27T03:10:32.033173+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3da8548
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | WATCH | MOVE | LEVEL | 1.770000 | 2026-02-25 | 0.001398 | -2.178697 | 5.000000 | 11.904762 | -0.088676 | -0.084746 | -0.561798 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.280000 | 2026-02-26 | 0.001398 | -0.070100 | 58.333333 | 32.539683 | 0.000595 | 0.706215 | 0.000000 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-27T11:10:27+08:00
- run_ts_utc: 2026-02-27T03:10:32.088210+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3da8548
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 101.050000 | 2026-02-26 | 0.001413 | 2.137280 | 98.333333 | 99.603175 | 0.201700 | 5.112994 | 0.677493 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260128&d2=20260227&i=d |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 95.520000 | 2026-02-26 | 0.001413 | 2.222681 | 100.000000 | 100.000000 | 0.209212 | 6.779661 | 0.711687 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 20 | 21 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260128&d2=20260227&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 477.480000 | 2026-02-26 | 0.001413 | 1.497754 | 95.000000 | 98.809524 | 0.084747 | 3.474576 | 0.857589 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260128&d2=20260227&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 97.790000 | 2026-02-26 | 0.001413 | 1.496721 | 95.000000 | 98.809524 | 0.083009 | 3.474576 | 0.845622 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260128&d2=20260227&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-26
- QQQ.close: 609.280000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -0.884192
- QQQ.position_in_band: 0.273273
- QQQ.dist_to_lower: 1.569000
- QQQ.dist_to_upper: 4.173000
- VXN.data_date: 2026-02-26
- VXN.value: 23.610000
- VXN.signal: NORMAL_RANGE (position_in_band=0.663474)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-26
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 1207836722507
- turnover_unit: TWD
- volume_multiplier: 1.452
- vol_multiplier: 1.452
- amplitude_pct: 1.152
- pct_change: 0.004
- close: 35414.49
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
- realized_vol_N_annualized_pct: 20.847361
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.569814
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-26
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.145000
- spot_sell: 31.295000
- mid: 31.220000
- ret1_pct: -0.303369 (from 2026-02-25 to 2026-02-26)
- chg_5d_pct: -0.715535 (from 2026-02-12 to 2026-02-26)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-27T02:02:01Z

<!-- rendered_at_utc: 2026-02-27T04:04:07Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
