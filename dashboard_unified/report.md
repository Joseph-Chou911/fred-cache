# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- taiwan_margin_financing: OK
- unified_generated_at_utc: 2026-01-24T06:17:42Z

## market_cache (detailed)
- as_of_ts: 2026-01-23T04:12:23Z
- run_ts_utc: 2026-01-23T15:54:00.791123+00:00
- ruleset_id: signals_v8
- script_fingerprint: render_dashboard_py_signals_v8@b94000a
- script_version: market_cache_v2_2_stats_zp_w60_w252_ret1_delta_pctAbs_deltas_dq_lite400
- series_count: 4

| series | signal | dir | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP500 | WATCH | HIGH | 6913.35 | 2026-01-22 | 11.693831 | 0.854939 | 81.666667 | 95.634921 | 0.380407 | 15 | 0.548751 | P252>=95;abs(PΔ60)>=15 | LONG_EXTREME,JUMP_P | ALERT | ALERT→WATCH | 2 | 3 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | WATCH | HIGH | 15.64 | 2026-01-22 | 11.693831 | -0.560243 | 30 | 20.238095 | -0.461344 | -25 | -7.455621 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | ALERT | ALERT→WATCH | 2 | 3 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| HYG_IEF_RATIO | WATCH | LOW | 0.847479 | 2026-01-22 | 11.693831 | 2.450272 | 100 | 83.730159 | -0.026976 | 0 | 0.084412 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 4 | 5 | DERIVED |
| OFR_FSI | WATCH | HIGH | -2.195 | 2026-01-20 | 11.693831 | 0.535354 | 76.666667 | 36.904762 | 0.669266 | 25 | 9.930242 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 1 | 2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (ALERT+WATCH+INFO)
- as_of_ts: 2026-01-24T03:03:42+08:00
- run_ts_utc: 2026-01-24T05:31:32.048101+00:00
- ruleset_id: NA
- script_fingerprint: NA
- script_version: stats_v1_ddof0_w60_w252_pct_le_ret1_delta
- ALERT: 1
- WATCH: 2
- INFO: 4
- NONE: 6
- CHANGED: 1

| series | signal | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | ALERT | 2.64 | 2026-01-22 | 10.463624 | -1.947339 | 1.666667 | 1.587302 | -0.278774 | -1.666667 | -1.858736 | P252<=2 | LONG_EXTREME | NONE | NONE→ALERT | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 |
| DGS10 | WATCH | 4.26 | 2026-01-21 | 10.463624 | 2.093672 | 98.333333 | 50.793651 | -0.676696 | -1.666667 | -0.930233 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | 15.64 | 2026-01-22 | 10.463624 | -0.564433 | 30 | 20.238095 | -0.465988 | -25 | -7.455621 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | 49384.01 | 2026-01-22 | 10.463624 | 1.528194 | 93.333333 | 98.412698 | 0.273801 | 6.666667 | 0.625096 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | INFO | -0.50568 | 2026-01-16 | 10.463624 | 1.237692 | 90 | 97.619048 | 0.02007 | 1.666667 | 0.850947 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | 6913.35 | 2026-01-22 | 10.463624 | 0.854939 | 81.666667 | 95.634921 | 0.380407 | 15 | 0.548751 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | INFO | 0.55 | 2026-01-22 | 10.463624 | 1.089838 | 90 | 97.619048 | -0.088016 | -5 | -1.785714 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |

## Audit Notes
- fred_dir is DERIVED (heuristic) from a fixed mapping table in this script (FRED_DIR_MAP). Unmapped series => NA.
- market_class/fred_class are DERIVED from tag/reason only: LONG if tag contains LONG_EXTREME; JUMP if tag contains JUMP* or reason contains 'abs(' thresholds; otherwise NONE.

## Resonance Matrix (strict + alias)
| resonance_level | pair_type | series | market_series | fred_series | market_signal | fred_signal | market_class | fred_class | market_tag | fred_tag | market_dir | fred_dir | market_reason | fred_reason | market_date | fred_date | market_source | fred_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONCORD_STRONG | ALIAS | VIX↔VIXCLS | VIX | VIXCLS | WATCH | WATCH | JUMP | JUMP | JUMP_P,JUMP_RET | JUMP_DELTA | HIGH | HIGH | abs(PΔ60)>=15;abs(ret1%60)>=2 | abs(pΔ60)>=15;abs(ret1%)>=2 | 2026-01-22 | 2026-01-22 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DISCORD_MIXED | STRICT | SP500 | SP500 | SP500 | WATCH | INFO | LONG+JUMP | LONG | LONG_EXTREME,JUMP_P | LONG_EXTREME | HIGH | HIGH | P252>=95;abs(PΔ60)>=15 | P252>=95 | 2026-01-22 | 2026-01-22 | https://stooq.com/q/d/l/?s=^spx&i=d | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |

## taiwan_margin_financing (TWSE/TPEX)
### TWSE (data_date=2026-01-23)
- source_url: https://histock.tw/stock/three.aspx?m=mg
- latest.date: 2026-01-23
- latest.balance_yi: 3760.8
- latest.chg_yi: 43.4
- sum_chg_yi_last5: 126.8
- avg_chg_yi_last5: 25.36
- pos_days_last5: 4
- neg_days_last5: 1
- max_chg_last5: 60.2
- min_chg_last5: -34.8

### TPEX (data_date=2026-01-23)
- source_url: https://histock.tw/stock/three.aspx?m=mg&no=TWOI
- latest.date: 2026-01-23
- latest.balance_yi: 1312.5
- latest.chg_yi: 11.1
- sum_chg_yi_last5: 20.3
- avg_chg_yi_last5: 4.06
- pos_days_last5: 3
- neg_days_last5: 2
- max_chg_last5: 12.5
- min_chg_last5: -10.3
