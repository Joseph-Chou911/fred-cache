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
- unified_generated_at_utc: 2026-03-10T23:46:51Z

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
- trend_basis: market_cache.SP500.signal=NONE, tag=NA, p252=69.444444, p252_on_threshold=80.0, data_date=2026-03-10
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=ALERT)=true, rate_stress(DGS10=NONE)=false
- vol_gate_v2: market_cache.VIX only (signal=ALERT, dir=HIGH, value=25.500000, ret1%60=-13.530010, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-03-09)
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
- date_alignment: twmargin_date=2026-03-10, roll25_used_date=2026-03-10, used_date_status=LATEST, strict_same_day=true, strict_not_stale=false, strict_roll_match=false
- dq_note: NA
- note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## market_cache (detailed)
- as_of_ts: 2026-03-10T23:31:46Z
- run_ts_utc: 2026-03-10T23:33:07.541648+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@b97439f
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX | ALERT | HIGH | DOWN | LEVEL+JUMP | 25.500000 | 2026-03-09 | 0.022650 | 2.491418 | 98.333333 | 93.253968 | -1.531044 | -1.666667 | -13.530010 | abs(Z60)>=2;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 20 | 21 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| OFR_FSI | ALERT | HIGH | UP | LEVEL+JUMP | -0.802000 | 2026-03-06 | 0.022650 | 4.182195 | 100.000000 | 90.079365 | 1.516846 | 1.666667 | 49.047014 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET | ALERT | SAME | 5 | 6 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | NONE | HIGH | DOWN | NONE | 6781.480000 | 2026-03-10 | 0.022650 | -1.692795 | 6.666667 | 69.444444 | -0.166030 | 0.000000 | -0.213508 | NA | NA | WATCH | WATCH→NONE | 17 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.829946 | 2026-03-10 | 0.022650 | -1.228630 | 15.000000 | 21.428571 | 0.240758 | 5.000000 | 0.148414 | NA | NA | NONE | SAME | 0 | 0 | DERIVED |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-03-11T07:35:20+08:00
- run_ts_utc: 2026-03-10T23:36:23.701552+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 3
- INFO: 1
- NONE: 7
- CHANGED: 1

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | ALERT | NA | LEVEL | 3.190000 | 2026-03-09 | 0.017139 | 2.620245 | 100.000000 | 81.746032 | 0.307619 | 0.000000 | 1.916933 | abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DCOILWTICO | ALERT | NA | LEVEL | 71.130000 | 2026-03-02 | 0.017139 | 2.925254 | 100.000000 | 96.825397 | 0.994585 | 0.000000 | 6.227599 | P252>=95;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | WATCH | NA | JUMP | 22695.950000 | 2026-03-09 | 0.017139 | -1.235436 | 18.333333 | 64.682540 | 0.823206 | 16.666667 | 1.376963 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | WATCH | NA | JUMP | -0.443600 | 2026-02-27 | 0.017139 | 0.435979 | 75.000000 | 65.873016 | 0.598967 | 25.000000 | 25.831801 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | NA | LEVEL | 25.500000 | 2026-03-09 | 0.017139 | 2.491418 | 98.333333 | 93.253968 | -1.531044 | -1.666667 | -13.530010 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(ret1%)>=2 | EXTREME_Z | ALERT | ALERT→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.462700 | 2026-02-27 | 0.017139 | 1.636383 | 100.000000 | 100.000000 | 0.008649 | 0.000000 | 0.880444 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| DGS10 | NONE | NA | JUMP | 4.120000 | 2026-03-09 | 0.017139 | -0.527147 | 28.333333 | 25.000000 | -0.386769 | -15.000000 | -0.722892 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| DGS2 | NONE | NA | NONE | 3.560000 | 2026-03-09 | 0.017139 | 1.075118 | 85.000000 | 34.920635 | 0.039780 | 1.666667 | 0.000000 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | NONE | NA | NONE | 47740.800000 | 2026-03-09 | 0.017139 | -1.958518 | 3.333333 | 75.000000 | 0.355641 | 1.666667 | 0.503668 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | NONE | NA | NONE | 119.491000 | 2026-03-06 | 0.017139 | 0.482291 | 56.666667 | 13.492063 | -0.043063 | -1.666667 | -0.064649 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| SP500 | NONE | NA | JUMP | 6795.990000 | 2026-03-09 | 0.017139 | -1.526765 | 6.666667 | 70.238095 | 0.963260 | 3.333333 | 0.830413 | NA | JUMP_DELTA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | NONE | NA | JUMP | 0.580000 | 2026-03-10 | 0.017139 | -1.484989 | 10.000000 | 72.619048 | 0.396495 | 3.333333 | 3.571429 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.440000 | 2026-03-10 | 0.017139 | -0.563122 | 30.000000 | 82.936508 | 0.364612 | 5.000000 | 7.317073 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

- fallback_policy: display_only_reference
- fallback_note: fallback values are shown for freshness reference only; not used for signal/z/p calculations
- fallback_source: fallback_cache/latest.json

### fred_cache fallback references (display-only; not used for signal/z/p calculations)
- policy: only show when fallback.data_date > fred.data_date
- note: fallback is for freshness reference only; may be downgraded / unofficial depending on source

| series | primary_date | primary_value | fallback_date | fallback_value | gap_days | fallback_note | fallback_source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NASDAQCOM | 2026-03-09 | 22695.950000 | 2026-03-10 | 22697.104000 | 1 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | unofficial_reference |
| DGS10 | 2026-03-09 | 4.120000 | 2026-03-10 | 4.150000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| DGS2 | 2026-03-09 | 3.560000 | 2026-03-10 | 3.570000 | 1 | WARN:fallback_treasury_csv | official_alt_source |
| DJIA | 2026-03-09 | 47740.800000 | 2026-03-10 | 47706.510000 | 1 | WARN:nonofficial_stooq(^dji);derived_1d_pct | unofficial_reference |
| SP500 | 2026-03-09 | 6795.990000 | 2026-03-10 | 6781.480000 | 1 | WARN:nonofficial_stooq(^spx);derived_1d_pct | unofficial_reference |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-03-11T01:09:35+08:00
- run_ts_utc: 2026-03-10T17:09:39.491999+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@d76e871
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | NONE | MOVE | NONE | 1.800000 | 2026-03-06 | 0.001248 | -1.182506 | 25.000000 | 22.222222 | -0.300773 | -0.423729 | -1.098901 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.340000 | 2026-03-09 | 0.001248 | 1.265928 | 86.666667 | 69.444444 | -0.277126 | -8.248588 | -0.425532 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-03-11T01:09:35+08:00
- run_ts_utc: 2026-03-10T17:09:39.544235+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@d76e871
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLD.US_CLOSE | INFO | MOVE | LONG | 472.530000 | 2026-03-09 | 0.001262 | 1.055435 | 83.333333 | 96.031746 | -0.050270 | -3.107345 | -0.206965 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260208&d2=20260310&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 96.780000 | 2026-03-09 | 0.001262 | 1.053193 | 83.333333 | 96.031746 | -0.051614 | -3.107345 | -0.216539 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260208&d2=20260310&i=d |
| IYR.US_CLOSE | NONE | MOVE | NONE | 99.230000 | 2026-03-09 | 0.001262 | 0.924065 | 75.000000 | 94.047619 | 0.061357 | 0.423729 | 0.201979 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260208&d2=20260310&i=d |
| VNQ.US_CLOSE | NONE | MOVE | NONE | 93.760000 | 2026-03-09 | 0.001262 | 0.963596 | 75.000000 | 94.047619 | 0.072995 | 0.423729 | 0.235168 | NA | NA | NONE | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260208&d2=20260310&i=d |

## nasdaq_bb_cache (display-only)
- status: OK
- note: display-only; not used for positioning/mode/cross_module
- QQQ.data_date: 2026-03-10
- QQQ.close: 607.730000
- QQQ.signal: NORMAL_RANGE
- QQQ.z: -0.780019
- QQQ.position_in_band: 0.298827
- QQQ.dist_to_lower: 1.766000
- QQQ.dist_to_upper: 4.144000
- VXN.data_date: 2026-03-10
- VXN.value: 27.330000
- VXN.signal: NEAR_UPPER_BAND (WATCH) (position_in_band=0.841992)

## roll25_cache (TW turnover)
- status: OK
- UsedDate: 2026-03-10
- run_day_tag: TRADING_DAY
- used_date_status: LATEST
- used_date_selection_tag: WEEKDAY
- tag (legacy): WEEKDAY
- roll25_strict_not_stale: false (from taiwan_signals; display-only)
- note: UsedDate is the data date used for calculations. used_date_status is policy-normalized to LATEST for display only (typically T-1). Staleness/strictness should be tracked by dedicated checks (e.g., taiwan_signals strict flags).
- risk_level: NA
- turnover_twd: 728225719000
- turnover_unit: TWD
- volume_multiplier: 0.857
- vol_multiplier: 0.857
- amplitude_pct: 2.496
- pct_change: 2.060
- close: 32771.87
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
- realized_vol_N_annualized_pct: 43.425452
- realized_vol_points_used: 10
- dd_n: 10
- max_drawdown_N_pct: -9.329712
- max_drawdown_points_used: 10
- confidence: OK

## FX (USD/TWD)
- status: OK
- data_date: 2026-03-10
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.750000
- spot_sell: 31.900000
- mid: 31.825000
- ret1_pct: -0.297619 (from 2026-03-09 to 2026-03-10)
- chg_5d_pct: 0.616503 (from 2026-03-03 to 2026-03-10)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-03-10T23:07:05Z

<!-- rendered_at_utc: 2026-03-10T23:46:51Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
