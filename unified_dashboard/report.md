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
- unified_generated_at_utc: 2026-02-25T16:41:29Z

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
- trend_basis: market_cache.SP500.signal=ALERT, tag=JUMP_ZD,JUMP_P, p252=87.301587, p252_on_threshold=80.0, data_date=2026-02-24
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=WATCH)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=19.550000, ret1%60=-6.949072, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-24)
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
- date_alignment: twmargin_date=2026-02-25, roll25_used_date=2026-02-24, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-25T03:25:12Z
- run_ts_utc: 2026-02-25T16:16:53.293475+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@a6b7dd8
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | ALERT | HIGH | DOWN | JUMP | -2.527000 | 2026-02-20 | 12.861470 | -0.179868 | 41.666667 | 10.317460 | -0.779221 | -30.000000 | -7.121662 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | WATCH | WATCH→ALERT | 6 | 7 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | ALERT | HIGH | DOWN | JUMP | 19.550000 | 2026-02-24 | 12.861470 | 1.314574 | 85.000000 | 70.238095 | -0.760098 | -11.666667 | -6.949072 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_RET | ALERT | SAME | 7 | 8 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | ALERT | HIGH | UP | JUMP | 6890.070000 | 2026-02-24 | 12.861470 | 0.041426 | 50.000000 | 87.301587 | 0.833342 | 25.000000 | 0.765164 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | ALERT | SAME | 4 | 5 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | UP | NONE | 0.829629 | 2026-02-24 | 12.861470 | -1.794590 | 3.333333 | 17.460317 | -0.078810 | -1.666667 | -0.038287 | NA | NA | ALERT | ALERT→NONE | 2 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-25T21:40:53+08:00
- run_ts_utc: 2026-02-25T14:13:34.910992+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 3
- INFO: 1
- NONE: 8
- CHANGED: 4

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DGS2 | ALERT | NA | LONG | 3.430000 | 2026-02-23 | 0.541086 | -1.483434 | 6.666667 | 1.984127 | -0.953683 | -38.333333 | -1.436782 | P252<=2 | LONG_EXTREME | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | WATCH | NA | JUMP | 2.950000 | 2026-02-23 | 0.541086 | 1.293480 | 95.000000 | 53.174603 | 1.006297 | 36.666667 | 3.146853 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | JUMP | 6890.070000 | 2026-02-24 | 0.541086 | 0.041426 | 50.000000 | 87.301587 | 0.833342 | 25.000000 | 0.765164 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | LEVEL | 21.010000 | 2026-02-23 | 0.541086 | 2.074672 | 96.666667 | 79.365079 | 0.864652 | 10.000000 | 10.057622 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(ret1%)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.466810 | 2026-02-20 | 0.541086 | 1.627734 | 100.000000 | 100.000000 | 0.007842 | 0.000000 | 0.834856 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 62.530000 | 2026-02-17 | 0.541086 | 1.095474 | 80.000000 | 39.285714 | -0.223174 | -6.666667 | -0.824742 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.030000 | 2026-02-23 | 0.541086 | -1.829310 | 6.666667 | 6.349206 | -0.682488 | -8.333333 | -1.225490 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | JUMP | 49174.500000 | 2026-02-24 | 0.541086 | 0.479896 | 63.333333 | 91.269841 | 0.457840 | 16.666667 | 0.759035 | NA | JUMP_DELTA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 117.991700 | 2026-02-20 | 0.541086 | -1.178939 | 21.666667 | 5.158730 | -0.168178 | -1.666667 | -0.206114 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 22863.680000 | 2026-02-24 | 0.541086 | -1.230433 | 15.000000 | 70.238095 | 0.700778 | 6.666667 | 1.044801 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.620800 | 2026-02-13 | 0.541086 | -0.250970 | 48.333333 | 43.650794 | 0.146568 | 11.666667 | 5.336993 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.610000 | 2026-02-24 | 0.541086 | -0.885792 | 25.000000 | 79.761905 | 0.168719 | 3.333333 | 1.666667 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.350000 | 2026-02-24 | 0.541086 | -1.226370 | 11.666667 | 78.968254 | -0.044602 | 0.000000 | 2.941176 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-25T17:09:21+08:00
- run_ts_utc: 2026-02-25T09:09:24.922765+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@15bf40c
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | WATCH | MOVE | LEVEL | 1.770000 | 2026-02-23 | 0.001090 | -2.195423 | 5.000000 | 11.507937 | -0.492714 | -10.254237 | -1.666667 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.260000 | 2026-02-24 | 0.001090 | -0.509835 | 48.333333 | 20.238095 | 0.005439 | 0.875706 | 0.000000 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-25T17:09:22+08:00
- run_ts_utc: 2026-02-25T09:09:24.969885+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@15bf40c
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 100.760000 | 2026-02-24 | 0.000825 | 2.220248 | 98.333333 | 99.603175 | 0.001202 | 1.723164 | 0.243757 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 18 | 19 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260126&d2=20260225&i=d |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 95.130000 | 2026-02-24 | 0.000825 | 2.273925 | 98.333333 | 99.603175 | -0.000320 | 0.028249 | 0.252924 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 18 | 19 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260126&d2=20260225&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 474.610000 | 2026-02-24 | 0.000825 | 1.514438 | 93.333333 | 98.412698 | -0.254088 | -3.276836 | -1.387937 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 1 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260126&d2=20260225&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 97.200000 | 2026-02-24 | 0.000825 | 1.512955 | 93.333333 | 98.412698 | -0.254148 | -3.276836 | -1.389875 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 1 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260126&d2=20260225&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-25
- QQQ.close: 614.830000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -0.261557
- QQQ.position_in_band: 0.427692
- QQQ.dist_to_lower: 2.421000
- QQQ.dist_to_upper: 3.239000
- VXN.data_date: 2026-02-24
- VXN.value: 24.820000
- VXN.signal: NORMAL_RANGE (position_in_band=0.791121)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-24
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 861808912768
- turnover_unit: TWD
- volume_multiplier: 1.075
- vol_multiplier: 1.075
- amplitude_pct: 2.366
- pct_change: 2.746
- close: 34700.82
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
- realized_vol_N_annualized_pct: 23.271491
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.569814
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-25
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.240000
- spot_sell: 31.390000
- mid: 31.315000
- ret1_pct: -0.429253 (from 2026-02-24 to 2026-02-25)
- chg_5d_pct: -0.429253 (from 2026-02-11 to 2026-02-25)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-25T15:33:02Z

<!-- rendered_at_utc: 2026-02-25T16:41:29Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
