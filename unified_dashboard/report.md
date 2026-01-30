# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-01-30T17:22:14Z

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
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, data_date=2026-01-29
- fragility_parts: credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false, tw_margin(INFO)=false, cross_divergence(CONVERGENCE)=false
- vol_gate: market_cache.VIX only (signal=WATCH, dir=HIGH, ret1%60=3.241590, data_date=2026-01-29)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

## market_cache (detailed)
- as_of_ts: 2026-01-30T05:01:20Z
- run_ts_utc: 2026-01-30T17:08:48.297983+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@03d6f30
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | WATCH | HIGH | JUMP | -2.383000 | 2026-01-27 | 12.124527 | 0.040159 | 65.000000 | 23.015873 | 0.277705 | 20.000000 | 3.833737 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | NONE | NONE→WATCH | 0 | 1 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| VIX | WATCH | HIGH | JUMP | 16.880000 | 2026-01-29 | 12.124527 | -0.066670 | 61.666667 | 46.825397 | 0.208246 | 11.666667 | 3.241590 | abs(ret1%60)>=2 | JUMP_RET | NONE | NONE→WATCH | 0 | 1 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | INFO | HIGH | LONG | 6969.010000 | 2026-01-29 | 12.124527 | 1.285483 | 95.000000 | 98.809524 | -0.132528 | -3.333333 | -0.129263 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | NONE | 0.844063 | 2026-01-29 | 12.124527 | 1.389845 | 86.666667 | 73.412698 | -0.231278 | -3.333333 | -0.116493 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-01-30T22:08:52+08:00
- run_ts_utc: 2026-01-30T15:02:02.080650+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 0
- INFO: 6
- NONE: 6
- CHANGED: 0

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 119.285500 | 2026-01-23 | 0.885578 | -2.595576 | 1.666667 | 0.396825 | -1.550004 | -20.000000 | -0.964982 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49071.560000 | 2026-01-29 | 0.885578 | 1.005128 | 80.000000 | 95.238095 | 0.025648 | 0.000000 | 0.114168 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | INFO | NA | LONG | 23685.120000 | 2026-01-29 | 0.885578 | 0.988667 | 91.666667 | 96.825397 | -0.451883 | -8.333333 | -0.722332 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.482950 | 2026-01-23 | 0.885578 | 1.449255 | 98.333333 | 99.603175 | 0.211563 | 8.333333 | 4.494938 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6969.010000 | 2026-01-29 | 0.885578 | 1.285483 | 95.000000 | 98.809524 | -0.132528 | -3.333333 | -0.129263 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.710000 | 2026-01-29 | 0.885578 | 1.344681 | 96.666667 | 99.206349 | 0.110602 | 6.666667 | 1.428571 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | NA | LONG | 0.570000 | 2026-01-29 | 0.885578 | 1.036752 | 96.666667 | 99.206349 | -0.093392 | -1.666667 | -1.724138 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.720000 | 2026-01-28 | 0.885578 | -1.234154 | 13.333333 | 8.730159 | 0.110222 | 1.666667 | 0.369004 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | NONE | 60.460000 | 2026-01-26 | 0.885578 | 0.743254 | 76.666667 | 20.634921 | 0.133903 | 3.333333 | 0.265340 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.260000 | 2026-01-28 | 0.885578 | 1.856565 | 98.333333 | 52.777778 | 0.247599 | 3.333333 | 0.471698 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | JUMP | 3.560000 | 2026-01-28 | 0.885578 | 0.535145 | 68.333333 | 25.793651 | 0.550070 | 18.333333 | 0.849858 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.712300 | 2026-01-23 | 0.885578 | -0.634085 | 28.333333 | 28.968254 | -0.236132 | -6.666667 | -9.416283 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | NONE | 16.350000 | 2026-01-28 | 0.885578 | -0.283467 | 48.333333 | 33.730159 | 0.006879 | 1.666667 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-01-30T18:04:11+08:00
- run_ts_utc: 2026-01-30T10:04:16.522226+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@bd752ea
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10YIE | WATCH | MOVE | LEVEL | 2.350000 | 2026-01-29 | 0.001534 | 2.293614 | 98.333333 | 67.857143 | -0.429691 | -1.666667 | -0.423729 | abs(Z60)>=2 | EXTREME_Z | ALERT | ALERT→WATCH | 2 | 3 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| DFII10 | NONE | MOVE | NONE | 1.900000 | 2026-01-28 | 0.001534 | 0.483392 | 65.000000 | 41.666667 | -0.005048 | 0.593220 | 0.000000 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-01-30T18:04:11+08:00
- run_ts_utc: 2026-01-30T10:04:16.569091+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@bd752ea
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | ALERT | MOVE | LONG | 495.900000 | 2026-01-29 | 0.001547 | 3.097982 | 100.000000 | 100.000000 | -0.263744 | 0.000000 | 0.295212 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=gld.us&d1=20251231&d2=20260130&i=d |
| IAU.US_CLOSE | ALERT | MOVE | LONG | 101.570000 | 2026-01-29 | 0.001547 | 3.095375 | 100.000000 | 100.000000 | -0.262768 | 0.000000 | 0.296238 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=iau.us&d1=20251231&d2=20260130&i=d |
| IYR.US_CLOSE | ALERT | MOVE | JUMP | 96.270000 | 2026-01-29 | 0.001547 | 1.165888 | 86.666667 | 74.206349 | 1.128292 | 29.039548 | 1.272880 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | ALERT | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=iyr.us&d1=20251231&d2=20260130&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | JUMP | 90.710000 | 2026-01-29 | 0.001547 | 1.102648 | 86.666667 | 66.666667 | 1.320129 | 35.819209 | 1.397429 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | ALERT | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=vnq.us&d1=20251231&d2=20260130&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-01-29
- run_day_tag: NON_TRADING_DAY
- used_date_status: OK_LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- note: run_day_tag is report-day context; UsedDate is the data date used for calculations (may lag on not-updated days)
- heat_split.heated_market: true
- heat_split.dq_issue: false
- risk_level: NA
- turnover_twd: 959652045839
- turnover_unit: TWD
- volume_multiplier: 1.223
- vol_multiplier: 1.223
- amplitude_pct: 1.596
- pct_change: -0.816
- close: 32536.27
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
- realized_vol_N_annualized_pct: 17.277042
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -1.617192
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
- generated_at_utc: 2026-01-30T16:01:59Z

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
- date_alignment: twmargin_date=2026-01-30, roll25_used_date=2026-01-29, match=false

<!-- rendered_at_utc: 2026-01-30T17:22:14Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
