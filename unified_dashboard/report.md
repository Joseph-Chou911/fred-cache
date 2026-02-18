# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-18T02:17:27Z

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
- trend_basis: market_cache.SP500.signal=NONE, tag=NA, p252=81.746032, p252_on_threshold=80.0, data_date=2026-02-17
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=21.200000, ret1%60=2.912621, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-16)
- vol_runaway_branch: SIGNAL_ALERT_OVERRIDE (display-only)
- vol_runaway_note: signal=ALERT triggers runaway by policy; thresholds shown for reference only (display-only)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: QUIET
- confidence: DOWNGRADED
- dq_reason: ROLL25_STALE
- date_alignment: twmargin_date=2026-02-11, roll25_used_date=2026-02-11, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-18T00:44:22Z
- run_ts_utc: 2026-02-18T00:45:14.268029+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@92b8255
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | UP | LEVEL+JUMP | 21.200000 | 2026-02-16 | 0.014519 | 2.169114 | 96.666667 | 79.365079 | 0.550185 | 3.333333 | 2.912621 | abs(Z60)>=2;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_RET | NONE | NONE→ALERT | 0 | 1 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | NONE | HIGH | UP | NONE | -2.115000 | 2026-02-13 | 0.014519 | 1.369231 | 95.000000 | 47.619048 | 0.273603 | 5.000000 | 1.075772 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.831276 | 2026-02-17 | 0.014519 | -1.244284 | 13.333333 | 21.428571 | -0.103200 | -1.666667 | -0.051561 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |
| SP500 | NONE | HIGH | UP | NONE | 6843.220000 | 2026-02-17 | 0.014519 | -0.283874 | 33.333333 | 81.746032 | 0.017892 | 1.666667 | 0.103128 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-18T10:12:16+08:00
- run_ts_utc: 2026-02-18T02:12:52.318765+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 3
- WATCH: 0
- INFO: 2
- NONE: 8
- CHANGED: 4

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 64.530000 | 2026-02-09 | 0.009533 | 2.902879 | 100.000000 | 53.571429 | 1.497627 | 8.333333 | 4.756494 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS2 | ALERT | NA | LEVEL | 3.400000 | 2026-02-13 | 0.009533 | -2.214430 | 1.666667 | 0.396825 | -1.286792 | -28.333333 | -2.017291 | P252<=2;abs(Z60)>=2 | EXTREME_Z | WATCH | WATCH→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | ALERT | NA | LEVEL | 117.525800 | 2026-02-13 | 0.009533 | -3.447392 | 1.666667 | 0.396825 | -0.336201 | -1.666667 | -0.604614 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49533.190000 | 2026-02-17 | 0.009533 | 0.971459 | 91.666667 | 98.015873 | 0.014772 | 3.333333 | 0.065170 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.474590 | 2026-02-06 | 0.009533 | 1.482931 | 100.000000 | 100.000000 | 0.007286 | 0.000000 | 0.682222 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.940000 | 2026-02-16 | 0.009533 | 0.734135 | 81.666667 | 48.412698 | -0.011765 | -3.333333 | -0.338983 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.040000 | 2026-02-13 | 0.009533 | -1.767497 | 8.333333 | 7.539683 | -0.660446 | -6.666667 | -1.222494 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22546.670000 | 2026-02-13 | 0.009533 | -1.842359 | 8.333333 | 63.492063 | -0.101530 | -1.666667 | -0.223391 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | NONE | 6843.220000 | 2026-02-17 | 0.009533 | -0.283874 | 33.333333 | 81.746032 | 0.017892 | 1.666667 | 0.103128 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.655800 | 2026-02-06 | 0.009533 | -0.393935 | 36.666667 | 38.095238 | 0.094951 | 3.333333 | 3.331368 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | JUMP | 0.620000 | 2026-02-17 | 0.009533 | -0.569519 | 31.666667 | 81.746032 | -0.375578 | -6.666667 | -3.125000 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | NONE | 0.360000 | 2026-02-17 | 0.009533 | -0.727606 | 20.000000 | 80.952381 | -0.042220 | 0.000000 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | NONE | 21.200000 | 2026-02-16 | 0.009533 | 1.691767 | 93.333333 | 79.365079 | 0.251172 | 1.666667 | 1.825168 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-18T08:48:32+08:00
- run_ts_utc: 2026-02-18T00:48:38.242953+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@9b13e15
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | ALERT | MOVE | LEVEL | 1.770000 | 2026-02-13 | 0.001734 | -2.563199 | 3.333333 | 11.111111 | -0.516517 | -3.446328 | -1.666667 | abs(Z60)>=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | 6 | 7 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.260000 | 2026-02-17 | 0.001734 | -0.421044 | 51.666667 | 19.444444 | -0.225981 | -7.655367 | -0.440529 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-18T08:48:34+08:00
- run_ts_utc: 2026-02-18T00:48:38.297922+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@9b13e15
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | LONG | 101.210000 | 2026-02-17 | 0.001194 | 3.278250 | 100.000000 | 100.000000 | 0.249383 | 0.000000 | 0.977751 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 11 | 12 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260119&d2=20260218&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | LONG | 95.500000 | 2026-02-17 | 0.001194 | 3.332594 | 100.000000 | 100.000000 | 0.232802 | 0.000000 | 0.962047 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 11 | 12 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260119&d2=20260218&i=d |
| GLD.US_CLOSE | WATCH | MOVE | JUMP | 448.230000 | 2026-02-17 | 0.001194 | 0.935359 | 76.666667 | 94.444444 | -0.465746 | -13.163842 | -3.108450 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=gld.us&d1=20260119&d2=20260218&i=d |
| IAU.US_CLOSE | WATCH | MOVE | JUMP | 91.820000 | 2026-02-17 | 0.001194 | 0.937521 | 76.666667 | 94.444444 | -0.463092 | -13.163842 | -3.092348 | abs(ret1%1d)>=2 | JUMP_RET | WATCH | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=iau.us&d1=20260119&d2=20260218&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-11
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
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
- generated_at_utc: 2026-02-17T15:13:33Z

<!-- rendered_at_utc: 2026-02-18T02:17:27Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
