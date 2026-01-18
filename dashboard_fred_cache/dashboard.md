# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=3 / INFO=3 / NONE=7; CHANGED=0; WATCH_STREAK>=3=3
- RUN_TS_UTC: `2026-01-18T14:23:59.170494+00:00`
- STATS.generated_at_utc: `2026-01-18T13:40:15+00:00`
- STATS.as_of_ts: `2026-01-18T21:40:12+08:00`
- script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- stale_hours: `72.0`
- dash_history: `dashboard_fred_cache/history.json`
- history_lite_used_for_jump: `cache/history_lite.json`
- jump_calc: `ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(2/3 vote: abs(zΔ60)>=0.75, abs(pΔ60)>=20, abs(ret1%)>=2 -> WATCH); Near(within 10% of jump thresholds)`

| Signal | Tag | Near | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | WATCH | SAME | 10 | DCOILWTICO | OK | 0.73 | 2026-01-12 | 59.39 | 0.029178 | 13.888889 | 0.753285 | 35 | 2.22031 | abs(zΔ60)>=0.75;abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | WATCH | SAME | 10 | STLFSI4 | OK | 0.73 | 2026-01-09 | -0.6644 | -0.454104 | 36.507937 | -0.402848 | -23.333333 | -17.468175 | abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| WATCH | LONG_EXTREME | NEAR:PΔ60+NEAR:ret1% | WATCH | SAME | 10 | T10Y3M | OK | 0.73 | 2026-01-16 | 0.57 | 1.307071 | 100 | 0.393825 | 30 | 16.326531 | P252>=95;abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| INFO | LONG_EXTREME | NA | INFO | SAME | 0 | DJIA | OK | 0.73 | 2026-01-16 | 49359.33 | 1.61987 | 98.412698 | -0.159386 | -1.666667 | -0.168094 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.73 | 2026-01-09 | -0.51002 | 1.217622 | 97.222222 | -0.311747 | -11.666667 | -5.916558 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| INFO | LONG_EXTREME | NA | INFO | SAME | 0 | SP500 | OK | 0.73 | 2026-01-16 | 6940.01 | 1.18493 | 98.015873 | -0.088684 | -1.666667 | -0.064224 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | NA | NEAR:ret1% | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.73 | 2026-01-15 | 2.71 | -1.709343 | 8.333333 | -0.312768 | -8.333333 | -1.811594 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.73 | 2026-01-15 | 4.17 | 0.898587 | 32.936508 | 0.290567 | 10 | 0.481928 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | NONE | SAME | 0 | DGS2 | OK | 0.73 | 2026-01-15 | 3.56 | 0.781119 | 24.603175 | 0.881068 | 20 | 1.424501 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | NONE | SAME | 0 | DTWEXBGS | OK | 0.73 | 2026-01-09 | 120.5856 | -0.855581 | 20.634921 | 0.920129 | 18.333333 | 0.498385 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.73 | 2026-01-16 | 23515.39 | 0.542703 | 91.666667 | -0.0592 | -3.333333 | -0.062176 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | NONE | SAME | 0 | T10Y2Y | OK | 0.73 | 2026-01-16 | 0.65 | 0.732118 | 92.460317 | 0.549914 | 8.333333 | 6.557377 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | NONE | SAME | 0 | VIXCLS | OK | 0.73 | 2026-01-15 | 15.84 | -0.474361 | 25.793651 | -0.328064 | -15 | -5.432836 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T21:40:12+08:00 |
