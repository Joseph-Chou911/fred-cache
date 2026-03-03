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
- unified_generated_at_utc: 2026-03-03T16:07:05Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: false
- trend_strong: false
- trend_relaxed: false
- fragility_high: true
- vol_watch: false
- vol_runaway: true
- matrix_cell: Trend=OFF / Fragility=HIGH
- mode: PAUSE_RISK_ON

**mode_decision_path**
- triggered: vol_runaway override

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=NONE, tag=NA, p252=85.317460, p252_on_threshold=80.0, data_date=2026-03-02
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=ALERT)=true, rate_stress(DGS10=ALERT)=true
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=21.440000, ret1%60=7.955690, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-02)
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
- date_alignment: twmargin_date=2026-03-03, roll25_used_date=2026-03-02, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-03-03T03:21:44Z
- run_ts_utc: 2026-03-03T15:58:41.805659+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@614e295
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | UP | LEVEL+JUMP | 21.440000 | 2026-03-02 | 12.616057 | 2.012441 | 98.333333 | 81.746032 | 0.632897 | 11.666667 | 7.955690 | abs(Z60)>=2;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_RET | WATCH | WATCH→ALERT | 13 | 14 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | ALERT | HIGH | UP | JUMP | -2.414000 | 2026-02-26 | 12.616057 | 0.357975 | 61.666667 | 21.031746 | 0.868420 | 26.666667 | 7.189542 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | ALERT | SAME | 12 | 13 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| HYG_IEF_RATIO | WATCH | LOW | DOWN | LEVEL | 0.826837 | 2026-03-02 | 12.616057 | -2.118115 | 3.333333 | 10.317460 | 0.681310 | 1.666667 | 0.373824 | abs(Z60)>=2 | EXTREME_Z | ALERT | ALERT→WATCH | 4 | 5 | DERIVED |
| SP500 | NONE | HIGH | UP | NONE | 6881.620000 | 2026-03-02 | 12.616057 | -0.199256 | 41.666667 | 85.317460 | 0.030850 | 1.666667 | 0.039832 | NA | NA | WATCH | WATCH→NONE | 10 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-03T21:21:18+08:00
- run_ts_utc: 2026-03-03T14:03:43.138096+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 3
- WATCH: 1
- INFO: 2
- NONE: 7
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | ALERT | NA | LEVEL | 3.120000 | 2026-02-28 | 0.706705 | 2.647397 | 100.000000 | 71.031746 | -0.013273 | 0.000000 | 0.645161 | abs(Z60)>=2.5 | EXTREME_Z | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | ALERT | NA | LEVEL | 3.970000 | 2026-02-27 | 0.706705 | -2.607323 | 1.666667 | 0.793651 | -0.548218 | 0.000000 | -1.243781 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | ALERT | NA | LEVEL | 3.380000 | 2026-02-27 | 0.706705 | -2.246536 | 1.666667 | 0.396825 | -0.616260 | -1.666667 | -1.169591 | P252<=2;abs(Z60)>=2 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | WATCH | NA | LEVEL | 66.360000 | 2026-02-23 | 0.706705 | 2.061338 | 96.666667 | 73.412698 | -0.233722 | -3.333333 | -0.494827 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | INFO | NA | LONG | 117.822300 | 2026-02-27 | 0.706705 | -1.164947 | 18.333333 | 4.365079 | -0.037386 | -3.333333 | -0.069463 | P252<=5 | LONG_EXTREME | NONE | NONE→INFO | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.466810 | 2026-02-20 | 0.706705 | 1.627734 | 100.000000 | 100.000000 | 0.007842 | 0.000000 | 0.834856 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | NONE | 48904.780000 | 2026-03-02 | 0.706705 | -0.050413 | 41.666667 | 86.111111 | -0.145605 | -5.000000 | -0.149333 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22748.860000 | 2026-03-02 | 0.706705 | -1.398340 | 15.000000 | 66.666667 | 0.275675 | 5.000000 | 0.355785 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | NONE | 6881.620000 | 2026-03-02 | 0.706705 | -0.199256 | 41.666667 | 85.317460 | 0.030850 | 1.666667 | 0.039832 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.598100 | 2026-02-20 | 0.706705 | -0.162989 | 50.000000 | 48.015873 | 0.087982 | 1.666667 | 3.656572 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.580000 | 2026-03-02 | 0.706705 | -1.618549 | 6.666667 | 73.015873 | -0.204880 | -5.000000 | -1.694915 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.330000 | 2026-03-02 | 0.706705 | -1.915790 | 3.333333 | 76.984127 | 0.355310 | 1.666667 | 10.000000 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 19.860000 | 2026-02-27 | 0.706705 | 1.379544 | 86.666667 | 73.015873 | 0.537564 | 8.333333 | 6.602254 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-03T17:01:16+08:00
- run_ts_utc: 2026-03-03T09:01:20.643114+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@10af04b
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | ALERT | MOVE | JUMP | 2.290000 | 2026-03-02 | 0.001290 | 0.154636 | 68.333333 | 42.857143 | 0.993515 | 39.519774 | 1.777778 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | WATCH | WATCH→ALERT | 3 | 4 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | ALERT | MOVE | LEVEL | 1.720000 | 2026-02-27 | 0.001290 | -2.789474 | 1.666667 | 5.555556 | -0.143772 | -0.028249 | -1.149425 | abs(Z60)>=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | 4 | 5 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-03T17:01:17+08:00
- run_ts_utc: 2026-03-03T09:01:20.694181+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@10af04b
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 95.930000 | 2026-03-02 | 0.001026 | 2.146619 | 100.000000 | 100.000000 | -0.000610 | 0.000000 | 0.250810 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 24 | 25 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260201&d2=20260303&i=d |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 101.540000 | 2026-03-02 | 0.001026 | 2.092480 | 100.000000 | 100.000000 | 0.000013 | 0.000000 | 0.236967 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260201&d2=20260303&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 490.000000 | 2026-03-02 | 0.001026 | 1.744860 | 96.666667 | 99.206349 | 0.130038 | 0.056497 | 1.287855 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260201&d2=20260303&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 100.380000 | 2026-03-02 | 0.001026 | 1.745352 | 96.666667 | 99.206349 | 0.132062 | 0.056497 | 1.302110 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260201&d2=20260303&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-03
- QQQ.close: 594.410000
- QQQ.signal: LOWER_BAND_TOUCH (MONITOR / SCALE_IN_ONLY)
- QQQ.z: -2.377512
- QQQ.position_in_band: 0.000000
- QQQ.dist_to_lower: -0.570000
- QQQ.dist_to_upper: 6.814000
- VXN.data_date: 2026-03-02
- VXN.value: 25.400000
- VXN.signal: NEAR_UPPER_BAND (WATCH) (position_in_band=0.814966)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-02
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 1014040137978
- turnover_unit: TWD
- volume_multiplier: 1.211
- vol_multiplier: 1.211
- amplitude_pct: 2.091
- pct_change: -0.902
- close: 35095.09
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
- realized_vol_N_annualized_pct: 22.696928
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -0.901891
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-03
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.555000
- spot_sell: 31.705000
- mid: 31.630000
- ret1_pct: 0.572337 (from 2026-03-02 to 2026-03-03)
- chg_5d_pct: 0.572337 (from 2026-02-23 to 2026-03-03)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-03T15:13:04Z

<!-- rendered_at_utc: 2026-03-03T16:07:05Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
