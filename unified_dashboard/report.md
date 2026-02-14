# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-14T15:49:36Z

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
- vol_runaway: false
- matrix_cell: Trend=OFF / Fragility=HIGH
- mode: RISK_OFF

**mode_decision_path**
- 4-quadrant: trend_on=false, fragility_high=true

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=NONE, tag=NA, p252=80.952381, p252_on_threshold=80.0, data_date=2026-02-13
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=WATCH)=true
- vol_gate_v2: market_cache.VIX only (signal=NONE, dir=HIGH, value=20.600000, ret1%60=-1.056676, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-13)
- vol_runaway_branch: NA (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: QUIET
- confidence: OK
- dq_reason: NA
- date_alignment: twmargin_date=2026-02-11, roll25_used_date=2026-02-11, used_date_status=LATEST, strict_same_day=true, strict_not_stale=true, strict_roll_match=true
- dq_note: NA

## market_cache (detailed)
- as_of_ts: 2026-02-14T03:15:57Z
- run_ts_utc: 2026-02-14T15:37:31.217255+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@0b4bd91
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.831576 | 2026-02-13 | 12.359505 | -1.163474 | 15.000000 | 21.428571 | -0.514822 | -6.666667 | -0.332309 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | DERIVED |
| SP500 | NONE | HIGH | UP | NONE | 6836.170000 | 2026-02-13 | 12.359505 | -0.301766 | 31.666667 | 80.952381 | -0.002466 | 1.666667 | 0.049907 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | NONE | HIGH | DOWN | NONE | 20.600000 | 2026-02-13 | 12.359505 | 1.618929 | 93.333333 | 76.190476 | 0.005399 | 0.000000 | -1.056676 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | NONE | HIGH | DOWN | NONE | -2.305000 | 2026-02-11 | 12.359505 | 0.461940 | 76.666667 | 31.746032 | -0.002035 | -5.000000 | -1.096491 | NA | NA | NONE | SAME | 0 | 0 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-14T21:10:53+08:00
- run_ts_utc: 2026-02-14T13:51:20.723796+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 4
- INFO: 2
- NONE: 5
- CHANGED: 7

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 64.530000 | 2026-02-09 | 0.673812 | 2.902879 | 100.000000 | 53.571429 | 1.497627 | 8.333333 | 4.756494 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | ALERT | NA | LEVEL | 118.240700 | 2026-02-06 | 0.673812 | -3.111191 | 3.333333 | 0.793651 | 0.769812 | 1.666667 | 0.289314 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.920000 | 2026-02-12 | 0.673812 | 0.439011 | 78.333333 | 45.238095 | 0.668996 | 35.000000 | 2.816901 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | JUMP | 4.090000 | 2026-02-12 | 0.673812 | -1.107050 | 15.000000 | 13.095238 | -1.297739 | -51.666667 | -2.153110 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | NA | JUMP | 3.470000 | 2026-02-12 | 0.673812 | -0.927638 | 30.000000 | 9.523810 | -0.947067 | -26.666667 | -1.420455 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 20.820000 | 2026-02-12 | 0.673812 | 1.440594 | 91.666667 | 78.571429 | 1.209788 | 15.000000 | 17.960340 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49500.930000 | 2026-02-13 | 0.673812 | 0.956687 | 88.333333 | 97.222222 | 0.019277 | 1.666667 | 0.098985 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.474590 | 2026-02-06 | 0.673812 | 1.482931 | 100.000000 | 100.000000 | 0.007286 | 0.000000 | 0.682222 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22546.670000 | 2026-02-13 | 0.673812 | -1.842359 | 8.333333 | 63.492063 | -0.101530 | -1.666667 | -0.223391 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | NONE | 6836.170000 | 2026-02-13 | 0.673812 | -0.301766 | 31.666667 | 80.952381 | -0.002466 | 1.666667 | 0.049907 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.655800 | 2026-02-06 | 0.673812 | -0.393935 | 36.666667 | 38.095238 | 0.094951 | 3.333333 | 3.331368 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | JUMP | 0.640000 | 2026-02-13 | 0.673812 | -0.193940 | 38.333333 | 83.730159 | 0.290091 | 5.000000 | 3.225806 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.360000 | 2026-02-13 | 0.673812 | -0.685386 | 20.000000 | 80.952381 | -0.250331 | -1.666667 | -7.692308 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-14T16:51:16+08:00
- run_ts_utc: 2026-02-14T08:51:19.702214+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@c3e4e9c
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | ALERT | MOVE | LEVEL | 1.800000 | 2026-02-12 | 0.001028 | -2.035704 | 6.666667 | 17.063492 | -1.339524 | -20.451977 | -3.225806 | abs(Z60)>=2;abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | EXTREME_Z,JUMP_ZD,JUMP_P,JUMP_RET | WATCH | WATCH→ALERT | 2 | 3 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.270000 | 2026-02-13 | 0.001028 | -0.193369 | 60.000000 | 24.206349 | -0.458654 | -7.796610 | -0.873362 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-14T16:51:17+08:00
- run_ts_utc: 2026-02-14T08:51:19.755377+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@c3e4e9c
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | LONG | 100.220000 | 2026-02-13 | 0.000765 | 3.056286 | 100.000000 | 100.000000 | 0.653107 | 3.389831 | 1.390926 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | WATCH→ALERT | 7 | 8 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260115&d2=20260214&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | LONG | 94.590000 | 2026-02-13 | 0.000765 | 3.126272 | 100.000000 | 100.000000 | 0.664912 | 3.389831 | 1.404374 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | WATCH→ALERT | 7 | 8 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260115&d2=20260214&i=d |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 462.620000 | 2026-02-13 | 0.000765 | 1.414073 | 90.000000 | 97.619048 | 0.315672 | 10.338983 | 2.485655 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260115&d2=20260214&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 94.750000 | 2026-02-13 | 0.000765 | 1.413650 | 90.000000 | 97.619048 | 0.309597 | 10.338983 | 2.443507 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260115&d2=20260214&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-11
- run_day_tag: NON_TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKEND
- tag (legacy): WEEKEND
- roll25_strict_not_stale: true (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 699292298413
- turnover_unit: TWD
- volume_multiplier: 0.888
- vol_multiplier: 0.888
- amplitude_pct: 1.924
- pct_change: 1.611
- close: 33605.71
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
- realized_vol_N_annualized_pct: 23.798714
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -2.803763
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-13
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.425000
- spot_sell: 31.575000
- mid: 31.500000
- ret1_pct: 0.174909 (from 2026-02-12 to 2026-02-13)
- chg_5d_pct: -0.568182 (from 2026-02-06 to 2026-02-13)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-14T14:53:33Z

<!-- rendered_at_utc: 2026-02-14T15:49:36Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
