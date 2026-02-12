# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- roll25_cache: OK
- taiwan_margin_financing: OK
- fx_usdtwd: OK
- asset_proxy_cache: OK
- inflation_realrate_cache: OK
- unified_generated_at_utc: 2026-02-12T16:34:26Z

## (2) Positioning Matrix
### Current Strategy Mode (deterministic; report-only)
- strategy_version: strategy_mode_v1
- strategy_params_version: 2026-02-07.2
- source_policy: SP500,VIX => market_cache_only (fred_cache SP500/VIXCLS not used for mode)
- trend_on: true
- trend_strong: true
- trend_relaxed: true
- fragility_high: true
- vol_watch: false
- vol_runaway: false
- matrix_cell: Trend=ON / Fragility=HIGH
- mode: DEFENSIVE_DCA

**mode_decision_path**
- 4-quadrant: trend_on=true, fragility_high=true

**strategy_params (deterministic constants)**
- TREND_P252_ON: 80.0
- VIX_RUNAWAY_RET1_60_MIN: 5.0
- VIX_RUNAWAY_VALUE_MIN: 20.0

**reasons**
- trend_basis: market_cache.SP500.signal=INFO, tag=LONG_EXTREME, p252=95.238095, p252_on_threshold=80.0, data_date=2026-02-11
- note: trend_relaxed uses (signal + p252) only; tag is informational (display-only).
- fragility_parts (global-only): credit_fragile(BAMLH0A0HYM2=NONE)=false, rate_stress(DGS10=WATCH)=true
- vol_gate_v2: market_cache.VIX only (signal=NONE, dir=HIGH, value=17.650000, ret1%60=-0.786959, runaway_policy: (signal=ALERT => runaway override) OR (signal=WATCH AND ret1%60>=5.0 AND value>=20.0), data_date=2026-02-11)
- vol_runaway_branch: NA (display-only)

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
- as_of_ts: 2026-02-12T06:23:58Z
- run_ts_utc: 2026-02-12T06:24:26.364869+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@e78b3ab
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | risk_impulse | market_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OFR_FSI | WATCH | HIGH | DOWN | JUMP | -2.250000 | 2026-02-09 | 0.007879 | 0.487802 | 83.333333 | 36.507937 | -0.329866 | -3.333333 | -5.782793 | abs(ret1%60)>=2 | JUMP_RET | WATCH | SAME | 3 | 4 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |
| SP500 | INFO | HIGH | DOWN | LONG | 6941.470000 | 2026-02-11 | 0.007879 | 0.804646 | 80.000000 | 95.238095 | -0.031767 | -1.666667 | -0.004898 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=^spx&i=d |
| HYG_IEF_RATIO | NONE | LOW | DOWN | NONE | 0.839879 | 2026-02-11 | 0.007879 | 0.352022 | 65.000000 | 51.984127 | 0.372534 | 10.000000 | 0.268144 | NA | NA | ALERT | ALERT→NONE | 1 | 0 | DERIVED |
| VIX | NONE | HIGH | DOWN | NONE | 17.650000 | 2026-02-11 | 0.007879 | 0.280280 | 78.333333 | 56.349206 | -0.013236 | -1.666667 | -0.786959 | NA | NA | WATCH | WATCH→NONE | 13 | 0 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-02-12T21:42:06+08:00
- run_ts_utc: 2026-02-12T14:14:42.438835+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 2
- WATCH: 2
- INFO: 4
- NONE: 5
- CHANGED: 5

| series | signal | fred_dir | fred_class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | ALERT | NA | LEVEL | 64.530000 | 2026-02-09 | 0.542900 | 2.902879 | 100.000000 | 53.571429 | 1.497627 | 8.333333 | 4.756494 | abs(Z60)>=2.5 | EXTREME_Z | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | ALERT | NA | LEVEL | 118.240700 | 2026-02-06 | 0.542900 | -3.111191 | 3.333333 | 0.793651 | 0.769812 | 1.666667 | 0.289314 | P252<=2;abs(Z60)>=2.5 | EXTREME_Z | ALERT | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | NA | JUMP | 4.160000 | 2026-02-10 | 0.542900 | -0.085109 | 48.333333 | 30.158730 | -0.884678 | -31.666667 | -1.421801 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | NONE | NONE→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | WATCH | NA | JUMP | 0.660000 | 2026-02-11 | 0.542900 | 0.189280 | 51.666667 | 88.095238 | -0.795652 | -35.000000 | -7.042254 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | INFO | INFO→WATCH | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| DGS2 | INFO | NA | LONG | 3.450000 | 2026-02-10 | 0.542900 | -1.344663 | 10.000000 | 3.571429 | -0.532271 | -23.333333 | -0.862069 | P252<=5 | LONG_EXTREME | NONE | NONE→INFO | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | NA | LONG | 50121.400000 | 2026-02-11 | 0.542900 | 1.602362 | 96.666667 | 99.206349 | -0.131810 | -3.333333 | -0.132980 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | NA | LONG | -0.474590 | 2026-02-06 | 0.542900 | 1.482931 | 100.000000 | 100.000000 | 0.007286 | 0.000000 | 0.682222 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | NA | LONG | 6941.470000 | 2026-02-11 | 0.542900 | 0.804646 | 80.000000 | 95.238095 | -0.031767 | -1.666667 | -0.004898 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| BAMLH0A0HYM2 | NONE | NA | NONE | 2.860000 | 2026-02-10 | 0.542900 | -0.110908 | 50.000000 | 31.349206 | 0.169068 | 8.333333 | 0.704225 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| NASDAQCOM | NONE | NA | NONE | 23066.470000 | 2026-02-11 | 0.542900 | -0.560783 | 26.666667 | 77.777778 | -0.105618 | -1.666667 | -0.155827 | NA | NA | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | NONE | NA | JUMP | -0.655800 | 2026-02-06 | 0.542900 | -0.393935 | 36.666667 | 38.095238 | 0.094951 | 3.333333 | 3.331368 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | NONE | NA | JUMP | 0.480000 | 2026-02-11 | 0.542900 | 0.201030 | 40.000000 | 85.714286 | 0.035476 | 3.333333 | 2.127660 | NA | JUMP_RET | WATCH | WATCH→NONE | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | NONE | NA | JUMP | 17.790000 | 2026-02-10 | 0.542900 | 0.267021 | 78.333333 | 57.936508 | 0.172628 | 6.666667 | 2.476959 | NA | JUMP_RET | NONE | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |

## inflation_realrate_cache (detailed)
- status: OK
- as_of_ts: 2026-02-12T17:08:09+08:00
- run_ts_utc: 2026-02-12T09:08:12.496044+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@6f47682
- script_version: cycle_sidecars_stats_v1
- series_count: 2

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DFII10 | WATCH | MOVE | JUMP | 1.840000 | 2026-02-10 | 0.000971 | -1.141134 | 13.333333 | 25.396825 | -0.690159 | -15.480226 | -1.604278 | abs(PΔ60)>=15 | JUMP_P | NONE | NONE→WATCH | 0 | 1 | https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |
| T10YIE | NONE | MOVE | NONE | 2.320000 | 2026-02-11 | 0.000971 | 0.967714 | 80.000000 | 51.984127 | -0.016005 | 0.338983 | 0.000000 | NA | NA | NONE | SAME | 0 | 0 | https://api.stlouisfed.org/fred/series/observations?series_id=T10YIE&api_key=REDACTED&file_type=json&sort_order=desc&limit=1 |

## asset_proxy_cache (detailed)
- status: OK
- as_of_ts: 2026-02-12T17:08:09+08:00
- run_ts_utc: 2026-02-12T09:08:12.542253+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@6f47682
- script_version: cycle_sidecars_stats_v1
- series_count: 4

| series | signal | dir | class | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IYR.US_CLOSE | ALERT | MOVE | LONG | 98.930000 | 2026-02-11 | 0.000984 | 2.655984 | 98.333333 | 99.206349 | -0.501225 | -1.666667 | -0.392670 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=iyr.us&d1=20260113&d2=20260212&i=d |
| VNQ.US_CLOSE | ALERT | MOVE | LONG | 93.360000 | 2026-02-11 | 0.000984 | 2.732690 | 98.333333 | 98.412698 | -0.648657 | -1.666667 | -0.543305 | abs(Z60)>=2;abs(Z60)>=2.5;P252>=95 | EXTREME_Z,LONG_EXTREME | ALERT | SAME | 5 | 6 | https://stooq.com/q/d/l/?s=vnq.us&d1=20260113&d2=20260212&i=d |
| GLD.US_CLOSE | INFO | MOVE | LONG | 467.630000 | 2026-02-11 | 0.000984 | 1.655632 | 95.000000 | 98.809524 | 0.111077 | 3.474576 | 1.131055 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=gld.us&d1=20260113&d2=20260212&i=d |
| IAU.US_CLOSE | INFO | MOVE | LONG | 95.760000 | 2026-02-11 | 0.000984 | 1.652554 | 95.000000 | 98.809524 | 0.108707 | 3.474576 | 1.113986 | P252>=95 | LONG_EXTREME | INFO | SAME | 0 | 0 | https://stooq.com/q/d/l/?s=iau.us&d1=20260113&d2=20260212&i=d |

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
- data_date: 2026-02-12
- source_url: https://rate.bot.com.tw/xrt?Lang=zh-TW
- spot_buy: 31.370000
- spot_sell: 31.520000
- mid: 31.445000
- ret1_pct: -0.015898 (from 2026-02-11 to 2026-02-12)
- chg_5d_pct: -0.647709 (from 2026-02-05 to 2026-02-12)
- dir: TWD_STRONG
- fx_signal: NONE
- fx_reason: below thresholds
- fx_confidence: OK

## taiwan_margin_financing (TWSE/TPEX)
- status: OK
- schema_version: taiwan_margin_financing_latest_v1
- generated_at_utc: 2026-02-12T15:26:54Z

<!-- rendered_at_utc: 2026-02-12T16:34:26Z -->
<!-- input_path: unified_dashboard/latest.json | input_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/latest.json -->
<!-- output_path: unified_dashboard/report.md | output_abs: /home/runner/work/fred-cache/fred-cache/unified_dashboard/report.md -->
<!-- root_report_exists: false | root_report_is_output: false -->
