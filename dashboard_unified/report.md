# Unified Risk Dashboard Report

## Module Status
- market_cache: OK
- fred_cache: OK
- taiwan_margin_financing: OK
- unified_generated_at_utc: 2026-01-24T04:11:07Z

## market_cache (detailed)
- as_of_ts: 2026-01-23T04:12:23Z
- run_ts_utc: 2026-01-23T15:54:00.791123+00:00
- series_count: 4

| series | signal | dir | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1%60 | reason | tag | prev | delta | streak_hist | streak_wa | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP500 | WATCH | HIGH | 6913.35 | 2026-01-22 | 11.693831 | 0.854939 | 81.666667 | 95.634921 | 0.380407 | 15 | 0.548751 | P252>=95;abs(PΔ60)>=15 | LONG_EXTREME,JUMP_P | ALERT | ALERT→WATCH | 2 | 3 | https://stooq.com/q/d/l/?s=^spx&i=d |
| VIX | WATCH | HIGH | 15.64 | 2026-01-22 | 11.693831 | -0.560243 | 30 | 20.238095 | -0.461344 | -25 | -7.455621 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | ALERT | ALERT→WATCH | 2 | 3 | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv |
| HYG_IEF_RATIO | WATCH | LOW | 0.847479 | 2026-01-22 | 11.693831 | 2.450272 | 100 | 83.730159 | -0.026976 | 0 | 0.084412 | abs(Z60)>=2 | EXTREME_Z | WATCH | SAME | 4 | 5 | DERIVED |
| OFR_FSI | WATCH | HIGH | -2.195 | 2026-01-20 | 11.693831 | 0.535354 | 76.666667 | 36.904762 | 0.669266 | 25 | 9.930242 | abs(PΔ60)>=15;abs(ret1%60)>=2 | JUMP_P,JUMP_RET | WATCH | SAME | 1 | 2 | https://www.financialresearch.gov/financial-stress-index/data/fsi.csv |

## fred_cache (WATCH+INFO)
- as_of_ts: 2026-01-18T14:57:27+08:00
- run_ts_utc: 2026-01-18T13:22:28.160501+00:00
- ALERT: 0
- WATCH: 8
- INFO: 2
- NONE: 3
- CHANGED: 0

| series | signal | value | data_date | age_h | z60 | p60 | p252 | zΔ60 | pΔ60 | ret1% | reason | tag | prev | delta | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DCOILWTICO | WATCH | 59.39 | 2026-01-12 | 6.416989 | 0.029178 | 56.666667 | 13.888889 | 0.753285 | 35 | 2.22031 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_RET | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 |
| DGS2 | WATCH | 3.56 | 2026-01-15 | 6.416989 | 0.781119 | 75 | 24.603175 | 0.881068 | 20 | 1.424501 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 |
| DTWEXBGS | WATCH | 120.5856 | 2026-01-09 | 6.416989 | -0.855581 | 26.666667 | 20.634921 | 0.920129 | 18.333333 | 0.498385 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | JUMP_DELTA | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 |
| NFCINONFINLEVERAGE | WATCH | -0.51002 | 2026-01-09 | 6.416989 | 1.217622 | 88.333333 | 97.222222 | -0.311747 | -11.666667 | -5.916558 | P252>=95;abs(ret1%)>=2 | JUMP_RET | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 |
| STLFSI4 | WATCH | -0.6644 | 2026-01-09 | 6.416989 | -0.454104 | 31.666667 | 36.507937 | -0.402848 | -23.333333 | -17.468175 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_RET | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 |
| T10Y2Y | WATCH | 0.65 | 2026-01-16 | 6.416989 | 0.732118 | 70 | 92.460317 | 0.549914 | 8.333333 | 6.557377 | abs(ret1%)>=2 | JUMP_RET | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 |
| T10Y3M | WATCH | 0.57 | 2026-01-16 | 6.416989 | 1.307071 | 100 | 100 | 0.393825 | 30 | 16.326531 | P252>=95;abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_RET | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 |
| VIXCLS | WATCH | 15.84 | 2026-01-15 | 6.416989 | -0.474361 | 36.666667 | 25.793651 | -0.328064 | -15 | -5.432836 | abs(pΔ60)>=15;abs(ret1%)>=2 | JUMP_RET | WATCH | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 |
| DJIA | INFO | 49359.33 | 2026-01-16 | 6.416989 | 1.61987 | 93.333333 | 98.412698 | -0.159386 | -1.666667 | -0.168094 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 |
| SP500 | INFO | 6940.01 | 2026-01-16 | 6.416989 | 1.18493 | 91.666667 | 98.015873 | -0.088684 | -1.666667 | -0.064224 | P252>=95 | LONG_EXTREME | INFO | SAME | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 |

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
