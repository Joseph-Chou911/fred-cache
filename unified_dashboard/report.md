# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-07T11:04:18Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-05.3
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
- trend_basis: market_cache.SP500.signal=ALERT, tag=JUMP_ZD,JUMP_P, p252=78.968254, p252_on_threshold=80.0, data_date=2026-02-05
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=21.770000, ret1%60=16.791845, runaway_thresholds: ret1%60>=5.0, value>=20.0, data_date=2026-02-05)

**dq_gates (no guessing; conservative defaults)**
- roll25_derived_confidence=OK (derived metrics not used for upgrade triggers)
- fx_confidence=OK (fx not used as primary trigger)

### taiwan_signals (pass-through; not used for mode)
- source: --tw-signals (taiwan_margin_cache/signals_latest.json)
- margin_signal: NONE
- consistency: MARKET_SHOCK_ONLY
- confidence: OK
- dq_reason: NA
- date_alignment: twmargin_date=2026-02-06, roll25_used_date=2026-02-06, used_date_status=LATEST, strict_same_day=true, strict_not_stale=true, strict_roll_match=true
- dq_note: NA

## market_cache (detailed)
- as_of_ts: 2026-02-06T03:18:01Z
- run_ts_utc: 2026-02-06T15:54:32.323774+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@1981948
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | UP | JUMP | 21.770000 | 2026-02-05 | 12.608701 | 1.711100 | 91.666667 | 82.539683 | 1.097384 | 8.333333 | 16.791845 | abs(ZΔ60)>=0.75;abs(ret1%60)>=2 | JUMP_ZD,JUMP_RET | WATCH | WATCH→ALERT | 7 | 8 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | ALERT | HIGH | DOWN | JUMP | 6798.400000 | 2026-02-05 | 12.608701 | -0.544140 | 21.666667 | 78.968254 | -0.861189 | -35.000000 | -1.225097 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | WATCH | WATCH→ALERT | 3 | 4 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | ALERT | LOW | UP | JUMP | 0.838243 | 2026-02-05 | 12.608701 | 0.149980 | 60.000000 | 46.428571 | -1.032583 | -21.666667 | -0.693892 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | DERIVED |
| OFR_FSI | NONE | HIGH | DOWN | NONE | -2.335000 | 2026-02-03 | 12.608701 | 0.237588 | 71.666667 | 27.777778 | -0.022302 | 0.000000 | -0.386930 | NA | NA | WATCH | WATCH→NONE | 4 | 0 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-06T21:23:12+08:00
- run_ts_utc: 2026-02-06T14:06:44.356639+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 2
- INFO: 2
- NONE: 8
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DTWEXBGS | ALERT | NA | LEVEL | 117.899600 | 2026-01-30 | 0.725377 | -3.881004 | 1.666667 | 0.396825 | -1.285427 | 0.000000 | -1.161834 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | JUMP | 6798.400000 | 2026-02-05 | 0.725377 | -0.544140 | 21.666667 | 78.968254 | -0.861189 | -35.000000 | -1.225097 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | JUMP | 0.540000 | 2026-02-05 | 0.725377 | 0.686254 | 73.333333 | 93.650794 | -0.386246 | -26.666667 | -10.000000 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | INFO | INFO→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.477850 | 2026-01-30 | 0.725377 | 1.475645 | 100.000000 | 100.000000 | 0.026390 | 1.666667 | 1.056010 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | INFO | NA | LONG | 0.740000 | 2026-02-05 | 0.725377 | 1.556185 | 100.000000 | 100.000000 | 0.246594 | 3.333333 | 2.777778 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.860000 | 2026-02-04 | 0.725377 | -0.183387 | 46.666667 | 32.142857 | 0.087456 | 3.333333 | 0.350877 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | NONE | NA | JUMP | 61.600000 | 2026-02-02 | 0.725377 | 1.405252 | 91.666667 | 26.984127 | 0.661998 | 15.000000 | 1.885544 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.290000 | 2026-02-04 | 0.725377 | 1.888579 | 98.333333 | 61.904762 | 0.060170 | 1.666667 | 0.233645 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.570000 | 2026-02-04 | 0.725377 | 0.853017 | 80.000000 | 30.158730 | 0.041503 | 1.666667 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | JUMP | 48908.720000 | 2026-02-05 | 0.725377 | 0.661878 | 66.666667 | 92.063492 | -0.632436 | -30.000000 | -1.197100 | NA | JUMP_DELTA | INFO | INFO→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | JUMP | 22540.590000 | 2026-02-05 | 0.725377 | -1.955456 | 6.666667 | 65.476190 | -0.893687 | -10.000000 | -1.589158 | NA | JUMP_DELTA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.678400 | 2026-01-30 | 0.725377 | -0.488886 | 33.333333 | 35.317460 | 0.145199 | 5.000000 | 4.759231 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 18.640000 | 2026-02-04 | 0.725377 | 0.603571 | 83.333333 | 66.269841 | 0.242778 | 3.333333 | 3.555556 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-07T16:50:21+08:00
- run_ts_utc: 2026-02-07T08:50:25.828258+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@b46ada2
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | ALERT | MOVE | JUMP | 1.890000 | 2026-02-05 | 0.001341 | 0.083465 | 46.666667 | 38.492063 | -1.129413 | -49.943503 | -2.577320 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | NONE | NONE→ALERT | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.340000 | 2026-02-06 | 0.001341 | 1.552785 | 90.000000 | 62.301587 | 0.443937 | 6.949153 | 0.862069 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-07T16:50:22+08:00
- run_ts_utc: 2026-02-07T08:50:25.866928+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@b46ada2
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | LEVEL | 97.660000 | 2026-02-06 | 0.001074 | 2.218579 | 98.333333 | 91.666667 | 1.266357 | 16.977401 | 1.560062 | abs(Z60)>=2;abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | EXTREME_Z,JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260108&d2=20260207&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | LEVEL | 92.250000 | 2026-02-06 | 0.001074 | 2.446590 | 98.333333 | 93.650794 | 1.314461 | 13.587571 | 1.552180 | abs(Z60)>=2;abs(ZΔ60)>=0.75 | EXTREME_Z,JUMP_ZD | NONE | NONE→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260108&d2=20260207&i=d |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 455.460000 | 2026-02-06 | 0.001074 | 1.478305 | 91.666667 | 98.015873 | 0.403807 | 8.615819 | 3.042918 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=gld.us&d1=20260108&d2=20260207&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 93.240000 | 2026-02-06 | 0.001074 | 1.472073 | 91.666667 | 98.015873 | 0.398127 | 8.615819 | 3.004529 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | WATCH | SAME | 1 | 2 | https://stooq.com/q/d/l/?s=iau.us&d1=20260108&d2=20260207&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-06
- run_day_tag: NON_TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKEND
- tag (legacy): WEEKEND
- roll25_strict_not_stale: true (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 700313173141
- turnover_unit: TWD
- volume_multiplier: 0.888
- vol_multiplier: 0.888
- amplitude_pct: 2.133
- pct_change: -0.058
- close: 31782.92
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
- realized_vol_N_annualized_pct: 19.265559
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -3.596502
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-02-06
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.605000
- spot_sell: 31.755000
- mid: 31.680000
- ret1_pct: 0.094787 (from 2026-02-05 to 2026-02-06)
- chg_5d_pct: 0.699301 (from 2026-01-30 to 2026-02-06)
- dir: TWD_WEAK
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-07T10:59:11Z

<!-- rendered_at_utc: 2026-02-07T11:04:18Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
