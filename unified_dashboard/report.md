# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-01-31T15:55:51Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- fragility_high: false
- vol_runaway: false
- matrix_cell: Trend=ON / Fragility=LOW
- mode: NORMAL_DCA

**reasons**
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, data_date=2026-01-30
- fragility_parts: credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false, tw_margin(INFO)=false, cross_divergence(CONVERGENCE)=false
- vol_gate: market_cache.VIX only (signal=WATCH, dir=HIGH, ret1%60=3.317536, data_date=2026-01-30)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

## market_cache (detailed)
- as_of_ts: 2026-01-31T04:52:16Z
- run_ts_utc: 2026-01-31T15:49:58.306251+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@12c0726
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | WATCH | HIGH | JUMP | 17.440000 | 2026-01-30 | 10.961752 | 0.144392 | 73.333333 | 55.158730 | 0.211062 | 11.666667 | 3.317536 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 1 | 2 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | INFO | HIGH | LONG | 6939.030000 | 2026-01-30 | 10.961752 | 0.961222 | 83.333333 | 96.031746 | -0.324261 | -11.666667 | -0.430190 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.845528 | 2026-01-30 | 10.961752 | 1.588299 | 91.666667 | 79.761905 | 0.198455 | 5.000000 | 0.173679 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |
| OFR_FSI | NONE | HIGH | NONE | -2.404000 | 2026-01-28 | 10.961752 | -0.004855 | 61.666667 | 21.031746 | -0.045013 | -3.333333 | -0.881242 | NA | NA | NONE | SAME | 0 | 0 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-01-31T21:54:07+08:00
- run_ts_utc: 2026-01-31T14:01:27.078760+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 0
- INFO: 4
- NONE: 8
- CHANGED: 2

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 119.285500 | 2026-01-23 | 0.121689 | -2.595576 | 1.666667 | 0.396825 | -1.550004 | -20.000000 | -0.964982 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.482950 | 2026-01-23 | 0.121689 | 1.449255 | 98.333333 | 99.603175 | 0.211563 | 8.333333 | 4.494938 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6939.030000 | 2026-01-30 | 0.121689 | 0.961222 | 83.333333 | 96.031746 | -0.324261 | -11.666667 | -0.430190 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.740000 | 2026-01-30 | 0.121689 | 1.732984 | 100.000000 | 100.000000 | 0.388303 | 3.333333 | 4.225352 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.590000 | 2026-01-30 | 0.121689 | 1.116012 | 98.333333 | 99.603175 | 0.079260 | 1.666667 | 3.508772 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.770000 | 2026-01-29 | 0.121689 | -0.876523 | 25.000000 | 13.888889 | 0.357631 | 11.666667 | 1.838235 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 60.460000 | 2026-01-26 | 0.121689 | 0.743254 | 76.666667 | 20.634921 | 0.133903 | 3.333333 | 0.265340 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.240000 | 2026-01-29 | 0.121689 | 1.468962 | 93.333333 | 48.015873 | -0.387603 | -5.000000 | -0.469484 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | JUMP | 3.530000 | 2026-01-29 | 0.121689 | 0.018363 | 51.666667 | 19.444444 | -0.516783 | -16.666667 | -0.842697 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | NONE | 48892.470000 | 2026-01-30 | 0.121689 | 0.793644 | 71.666667 | 93.253968 | -0.211484 | -8.333333 | -0.364957 | NA | NA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | JUMP | 23461.820000 | 2026-01-30 | 0.121689 | 0.420160 | 55.000000 | 86.904762 | -0.568506 | -36.666667 | -0.942786 | NA | JUMP_DELTA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.712300 | 2026-01-23 | 0.121689 | -0.634085 | 28.333333 | 28.968254 | -0.236132 | -6.666667 | -9.416283 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 16.880000 | 2026-01-29 | 0.121689 | -0.085842 | 60.000000 | 46.825397 | 0.197626 | 11.666667 | 3.241590 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-01-31T17:02:18+08:00
- run_ts_utc: 2026-01-31T09:02:22.696105+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3d13ae5
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | WATCH | MOVE | LEVEL | 2.360000 | 2026-01-30 | 0.001304 | 2.436421 | 100.000000 | 71.825397 | 0.133516 | 1.694915 | 0.425532 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 3 | 4 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.890000 | 2026-01-29 | 0.001304 | 0.244827 | 53.333333 | 38.095238 | -0.219716 | -11.073446 | -0.526316 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-01-31T17:02:19+08:00
- run_ts_utc: 2026-01-31T09:02:22.737839+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@3d13ae5
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | ALERT | MOVE | LONG | 444.950000 | 2026-01-30 | 0.001038 | 1.357379 | 90.000000 | 97.619048 | -1.728682 | -10.000000 | -10.295956 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_ZD,JUMP_RET | ALERT | SAME | 6 | 7 | https://stooq.com/q/d/l/?s=gld.us&d1=20260101&d2=20260131&i=d |
| IAU.US_CLOSE | ALERT | MOVE | LONG | 91.200000 | 2026-01-30 | 0.001038 | 1.388809 | 90.000000 | 97.619048 | -1.694508 | -10.000000 | -10.081717 | P252>=95;abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_ZD,JUMP_RET | ALERT | SAME | 6 | 7 | https://stooq.com/q/d/l/?s=iau.us&d1=20260101&d2=20260131&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 96.210000 | 2026-01-30 | 0.001038 | 1.119435 | 85.000000 | 73.412698 | -0.031056 | -1.440678 | -0.010387 | NA | NA | ALERT | ALERT→NONE | 2 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260101&d2=20260131&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 90.800000 | 2026-01-30 | 0.001038 | 1.169135 | 86.666667 | 68.650794 | 0.082808 | 0.225989 | 0.110254 | NA | NA | ALERT | ALERT→NONE | 2 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260101&d2=20260131&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-01-30
- run_day_tag: NON_TRADING_DAY
- used_date_status: OK_LATEST
- used_date_selection_tag: WEEKEND
- tag (legacy): WEEKEND
- note: run_day_tag is report-day context; UsedDate is the data date used for calculations (may lag on not-updated days)
- heat_split.heated_market: true
- heat_split.dq_issue: false
- risk_level: NA
- turnover_twd: 941320964545
- turnover_unit: TWD
- volume_multiplier: 1.179
- vol_multiplier: 1.179
- amplitude_pct: 1.692
- pct_change: -1.452
- close: 32063.75
- LookbackNTarget: 20
- LookbackNActual: 20
- signals.DownDay: true
- signals.VolumeAmplified: false
- signals.VolAmplified: false
- signals.NewLow_N: 0
- signals.ConsecutiveBreak: 2
- signals.OhlcMissing: false

### roll25_derived (realized vol / drawdown)
- status: OK
- vol_n: 10
- realized_vol_N_annualized_pct: 18.059431
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -2.256048
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-01-30
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.385000
- spot_sell: 31.535000
- mid: 31.460000
- ret1_pct: 0.511182 (from 2026-01-29 to 2026-01-30)
- chg_5d_pct: -0.285261 (from 2026-01-23 to 2026-01-30)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-01-31T14:58:52Z

### cross_module (Margin × Roll25 consistency)
- margin_signal: INFO
- margin_signal_source: DERIVED.rule_v1(TWSE_chg_yi_last5)
- margin_rule_version: rule_v1
- chg_unit: 億 (from modules.taiwan_margin_financing.latest.series.TWSE.chg_yi_unit.label)
- chg_last5: [21.2, -31.4, 21.9, 11.5, 55.0] 億
- sum_last5: 78.200 億
- pos_days_last5: 4
- latest_chg: 21.200 億
- margin_confidence: OK
- roll25_heated_market: true
- roll25_data_quality_issue: false
- roll25_heated (legacy): true
- roll25_confidence: OK
- roll25_split_ref: heated_market=true, dq_issue=false (see roll25_cache section)
- consistency: CONVERGENCE
- date_alignment: twmargin_date=2026-01-30, roll25_used_date=2026-01-30, match=true

<!-- rendered_at_utc: 2026-01-31T15:55:51Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
