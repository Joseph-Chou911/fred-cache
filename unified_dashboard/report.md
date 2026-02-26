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
- unified_generated_at_utc: 2026-02-26T16:29:09Z

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
- trend_basis: market_cache.SP500.signal=ALERT, tag=LONG_EXTREME,JUMP_ZD,JUMP_P, p252=96.428571, p252_on_threshold=80.0, data_date=2026-02-25
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=17.930000, ret1%60=-8.286445, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-25)
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
- date_alignment: twmargin_date=2026-02-26, roll25_used_date=2026-02-25, used_date_status=LATEST, strict_same_day=false, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-02-26T03:20:22Z
- run_ts_utc: 2026-02-26T16:06:24.280997+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@71aefd9
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | DOWN | JUMP | 17.930000 | 2026-02-25 | 12.767300 | 0.526265 | 76.666667 | 59.126984 | -0.788309 | -8.333333 | -8.286445 | abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | JUMP_ZD,JUMP_RET | ALERT | SAME | 8 | 9 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| SP500 | ALERT | HIGH | UP | LONG+JUMP | 6946.130000 | 2026-02-25 | 12.767300 | 0.969904 | 85.000000 | 96.428571 | 0.928478 | 35.000000 | 0.813635 | P252>=95;abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | LONG_EXTREME,JUMP_ZD,JUMP_P | ALERT | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=^spx&i=d |
| OFR_FSI | WATCH | HIGH | UP | JUMP | -2.396000 | 2026-02-23 | 12.767300 | 0.440205 | 66.666667 | 23.015873 | 0.620073 | 25.000000 | 5.184013 | abs(PΔ60)>=15;abs(ret1%1d)>=2 | JUMP_P,JUMP_RET | ALERT | ALERT→WATCH | 7 | 8 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.831304 | 2026-02-25 | 12.767300 | -1.480519 | 6.666667 | 22.222222 | 0.338328 | 3.333333 | 0.217375 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-26T21:41:25+08:00
- run_ts_utc: 2026-02-26T14:13:59.591169+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 0
- WATCH: 4
- INFO: 3
- NONE: 6
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | WATCH | NA | LEVEL | 66.360000 | 2026-02-23 | 0.541831 | 2.061338 | 96.666667 | 73.412698 | -0.233722 | -3.333333 | -0.494827 | abs(Z60)>=2 | EXTREME_Z | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 23152.080000 | 2026-02-25 | 0.541831 | -0.399962 | 31.666667 | 78.571429 | 0.830471 | 16.666667 | 1.261389 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | LONG | 6946.130000 | 2026-02-25 | 0.541831 | 0.969904 | 85.000000 | 96.428571 | 0.928478 | 35.000000 | 0.813635 | P252>=95;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | LONG_EXTREME | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | JUMP | 19.550000 | 2026-02-24 | 0.541831 | 1.314574 | 85.000000 | 70.238095 | -0.760098 | -11.666667 | -6.949072 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DGS2 | INFO | NA | LONG | 3.430000 | 2026-02-24 | 0.541831 | -1.483434 | 6.666667 | 2.380952 | 0.000000 | 0.000000 | 0.000000 | P252<=5 | LONG_EXTREME | ALERT | ALERT→INFO | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49482.150000 | 2026-02-25 | 0.541831 | 0.873110 | 81.666667 | 95.634921 | 0.393215 | 18.333333 | 0.625629 | P252>=95 | LONG_EXTREME | NONE | NONE→INFO | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.466810 | 2026-02-20 | 0.541831 | 1.627734 | 100.000000 | 100.000000 | 0.007842 | 0.000000 | 0.834856 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.970000 | 2026-02-24 | 0.541831 | 1.501778 | 96.666667 | 55.555556 | 0.208298 | 1.666667 | 0.677966 | NA | NA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | NONE | 4.040000 | 2026-02-24 | 0.541831 | -1.721031 | 8.333333 | 8.333333 | 0.108279 | 1.666667 | 0.248139 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 117.991700 | 2026-02-20 | 0.541831 | -1.178939 | 21.666667 | 5.158730 | -0.168178 | -1.666667 | -0.206114 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.598100 | 2026-02-20 | 0.541831 | -0.162989 | 50.000000 | 48.015873 | 0.087982 | 1.666667 | 3.656572 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | NONE | 0.600000 | 2026-02-25 | 0.541831 | -1.119357 | 20.000000 | 78.174603 | -0.233565 | -5.000000 | -1.639344 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.360000 | 2026-02-25 | 0.541831 | -1.332738 | 15.000000 | 79.761905 | -0.106368 | 3.333333 | 2.857143 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-26T17:07:29+08:00
- run_ts_utc: 2026-02-26T09:07:33.976931+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@fb031ea
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.780000 | 2026-02-24 | 0.001382 | -1.984170 | 6.666667 | 13.888889 | 0.286716 | 1.581921 | 0.564972 | NA | NA | WATCH | WATCH→NONE | 1 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.280000 | 2026-02-25 | 0.001382 | -0.048805 | 58.333333 | 32.142857 | 0.484385 | 10.875706 | 0.884956 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-26T17:07:30+08:00
- run_ts_utc: 2026-02-26T09:07:34.018371+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@fb031ea
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 94.870000 | 2026-02-25 | 0.001116 | 2.023643 | 93.333333 | 98.412698 | -0.235325 | -4.971751 | -0.299590 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | WATCH | SAME | 19 | 20 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260127&d2=20260226&i=d |
| IYR.US_CLOSE | INFO | MOVE | LONG | 100.370000 | 2026-02-25 | 0.001116 | 1.943706 | 93.333333 | 98.412698 | -0.262602 | -4.971751 | -0.382115 | P252>=95 | LONG_EXTREME | WATCH | WATCH→INFO | 19 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260127&d2=20260226&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 473.420000 | 2026-02-25 | 0.001116 | 1.427327 | 91.666667 | 98.015873 | -0.074934 | -1.553672 | -0.250732 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260127&d2=20260226&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 96.970000 | 2026-02-25 | 0.001116 | 1.427973 | 91.666667 | 98.015873 | -0.072853 | -1.553672 | -0.236626 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260127&d2=20260226&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-02-26
- QQQ.close: 606.140000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -1.234644
- QQQ.position_in_band: 0.186950
- QQQ.dist_to_lower: 1.086000
- QQQ.dist_to_upper: 4.723000
- VXN.data_date: 2026-02-25
- VXN.value: 22.940000
- VXN.signal: NORMAL_RANGE (position_in_band=0.603293)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-25
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 1020570870136
- turnover_unit: TWD
- volume_multiplier: 1.258
- vol_multiplier: 1.258
- amplitude_pct: 2.214
- pct_change: 2.053
- close: 35413.07
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
- realized_vol_N_annualized_pct: 20.496359
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
- generated_at_utc: 2026-02-26T15:13:10Z

<!-- rendered_at_utc: 2026-02-26T16:29:09Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
