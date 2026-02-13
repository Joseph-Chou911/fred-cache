# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-13T16:07:49Z

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
- trend_basis: market_cache.SP500.signal=ALERT, tag=JUMP_ZD,JUMP_P, p252=80.555556, p252_on_threshold=80.0, data_date=2026-02-12
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=20.820000, ret1%60=17.960340, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-12)
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
- as_of_ts: 2026-02-13T03:32:32Z
- run_ts_utc: 2026-02-13T15:56:38.347692+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@190cf66
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HYG_IEF_RATIO | ALERT | LOW | UP | JUMP | 0.834263 | 2026-02-12 | 12.401763 | -0.663787 | 21.666667 | 28.968254 | -1.015809 | -43.333333 | -0.668759 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | NONE | NONE→ALERT | 0 | 1 | DERIVED |
| SP500 | ALERT | HIGH | DOWN | JUMP | 6832.760000 | 2026-02-12 | 12.401763 | -0.299300 | 30.000000 | 80.555556 | -1.103946 | -50.000000 | -1.566095 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15 | JUMP_ZD,JUMP_P | INFO | INFO→ALERT | 0 | 1 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | ALERT | HIGH | UP | JUMP | 20.820000 | 2026-02-12 | 12.401763 | 1.613530 | 93.333333 | 78.571429 | 1.333250 | 15.000000 | 17.960340 | abs(ZΔ60)>=0.75;abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_ZD,JUMP_P,JUMP_RET | NONE | NONE→ALERT | 0 | 1 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | NONE | HIGH | DOWN | NONE | -2.280000 | 2026-02-10 | 12.401763 | 0.463975 | 81.666667 | 33.730159 | -0.023826 | -1.666667 | -1.333333 | NA | NA | WATCH | WATCH→NONE | 4 | 0 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-13T21:34:07+08:00
- run_ts_utc: 2026-02-13T14:07:09.843739+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 5
- INFO: 2
- NONE: 4
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 64.530000 | 2026-02-09 | 0.550234 | 2.902879 | 100.000000 | 53.571429 | 1.497627 | 8.333333 | 4.756494 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | ALERT | NA | LEVEL | 118.240700 | 2026-02-06 | 0.550234 | -3.111191 | 3.333333 | 0.793651 | 0.769812 | 1.666667 | 0.289314 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | NA | JUMP | 3.520000 | 2026-02-11 | 0.550234 | 0.019429 | 56.666667 | 20.238095 | 1.364092 | 46.666667 | 2.028986 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | INFO | INFO→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 22597.150000 | 2026-02-12 | 0.550234 | -1.740829 | 10.000000 | 65.476190 | -1.180046 | -16.666667 | -2.034642 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| SP500 | WATCH | NA | JUMP | 6832.760000 | 2026-02-12 | 0.550234 | -0.299300 | 30.000000 | 80.555556 | -1.103946 | -50.000000 | -1.566095 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | INFO | INFO→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | WATCH | NA | JUMP | 0.620000 | 2026-02-12 | 0.550234 | -0.484032 | 33.333333 | 82.142857 | -0.673312 | -18.333333 | -6.060606 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | NA | JUMP | 0.390000 | 2026-02-12 | 0.550234 | -0.435055 | 21.666667 | 81.349206 | -0.636085 | -18.333333 | -18.750000 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 49451.980000 | 2026-02-12 | 0.550234 | 0.937410 | 86.666667 | 96.825397 | -0.664952 | -10.000000 | -1.335597 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.474590 | 2026-02-06 | 0.550234 | 1.482931 | 100.000000 | 100.000000 | 0.007286 | 0.000000 | 0.682222 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.840000 | 2026-02-11 | 0.550234 | -0.229985 | 43.333333 | 27.777778 | -0.119077 | -6.666667 | -0.699301 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | JUMP | 4.180000 | 2026-02-11 | 0.550234 | 0.190689 | 66.666667 | 37.301587 | 0.275798 | 18.333333 | 0.480769 | NA | JUMP_DELTA | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.655800 | 2026-02-06 | 0.550234 | -0.393935 | 36.666667 | 38.095238 | 0.094951 | 3.333333 | 3.331368 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | NONE | 17.650000 | 2026-02-11 | 0.550234 | 0.230806 | 76.666667 | 56.349206 | -0.036214 | -1.666667 | -0.786959 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-13T17:04:26+08:00
- run_ts_utc: 2026-02-13T09:04:29.581254+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@49e9d81
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | WATCH | MOVE | JUMP | 1.860000 | 2026-02-11 | 0.000995 | -0.687582 | 28.333333 | 31.349206 | 0.486209 | 16.468927 | 1.086957 | abs(PΔ60)>=15 | JUMP_P | WATCH | SAME | 1 | 2 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.290000 | 2026-02-12 | 0.000995 | 0.266931 | 68.333333 | 38.492063 | -0.693347 | -11.327684 | -1.293103 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-13T17:04:26+08:00
- run_ts_utc: 2026-02-13T09:04:29.632150+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@49e9d81
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | WATCH | MOVE | LONG | 451.390000 | 2026-02-12 | 0.001009 | 1.113112 | 80.000000 | 95.238095 | -0.528594 | -14.915254 | -3.472831 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=gld.us&d1=20260114&d2=20260213&i=d |
| IAU.US_CLOSE | WATCH | MOVE | LONG | 92.480000 | 2026-02-12 | 0.001009 | 1.118722 | 80.000000 | 95.238095 | -0.519924 | -14.915254 | -3.414787 | P252>=95;abs(ret1%60)>=2 | LONG_EXTREME,JUMP_RET | INFO | INFO→WATCH | 0 | 1 | https://stooq.com/q/d/l/?s=iau.us&d1=20260114&d2=20260213&i=d |
| IYR.US_CLOSE | WATCH | MOVE | LONG | 98.870000 | 2026-02-12 | 0.001009 | 2.423912 | 96.666667 | 98.412698 | -0.206754 | -1.638418 | -0.075811 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | ALERT→WATCH | 6 | 7 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260114&d2=20260213&i=d |
| VNQ.US_CLOSE | WATCH | MOVE | LONG | 93.250000 | 2026-02-12 | 0.001009 | 2.480829 | 96.666667 | 98.015873 | -0.226079 | -1.638418 | -0.085690 | abs(Z60)>=2;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | ALERT→WATCH | 6 | 7 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260114&d2=20260213&i=d |

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-02-11
- run_day_tag: NON_TRADING_DAY
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
- generated_at_utc: 2026-02-13T15:09:44Z

<!-- rendered_at_utc: 2026-02-13T16:07:49Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
