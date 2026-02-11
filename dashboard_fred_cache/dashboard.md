# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=1 / INFO=4 / NONE=7; CHANGED=3; WATCH_STREAK>=3=0; NEAR=6; JUMP_1of3=4
- RUN_TS_UTC: `2026-02-11T12:01:23.576240+00:00`
- day_key_local: `2026-02-11`
- STATS.generated_at_utc: `2026-02-11T12:00:07+00:00`
- STATS.as_of_ts: `2026-02-11T20:00:04+08:00`
- STATS.generated_at_utc(norm): `2026-02-11T12:00:07+00:00`
- STATS.data_commit_sha: `7ad1f9dc2f3ab2399e824f308b02c823d2300ea1`
- snapshot_id: `commit:7ad1f9dc2f3ab2399e824f308b02c823d2300ea1`
- streak_basis: `distinct snapshots (snapshot_id); re-run same snapshot does not increment`
- streak_calc: `basis=snapshot_id; consecutive WATCH across prior distinct daily buckets; same-day rerun overwrites`
- script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- stale_hours: `72.0`
- dash_history: `dashboard_fred_cache/history.json`
- history_lite_used_for_jump: `cache/history_lite.json`
- ret1_guard: `ret1% guard: if abs(prev_value)<1e-3 -> ret1%=NA (avoid near-zero denom blow-ups)`
- threshold_eps: `threshold_eps: Z=1e-12, P=1e-09, R=1e-09 (avoid rounding/float boundary mismatch)`
- output_format: `display_nd: age=2, value=4, z=4, p=3, delta=4, ret1=3; dbg_nd=12 (dbg only for Near/Jump)`
- alignment: `PASS`; checked=13; mismatch=0; hl_missing=0
- jump_calc: `ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(2/3 vote: abs(zΔ60)>=0.75, abs(pΔ60)>=15, abs(ret1%)>=2 -> WATCH); Near(within 10% of jump thresholds)`

| Signal | Tag | Near | JUMP_HITS | HITBITS | DBG | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | z252 | p60 | p252 | z_delta60 | p_delta60 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALERT | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=3.333333333333;prev_p60=1.666666666667;z60=-3.11119123456;prev_z60=-3.881003518348;prev_v=117.8996;last_v=118.2407;zΔ60=0.769812283789;pΔ60=1.666666666667;ret1%=0.289313958656 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.02 | 2026-02-06 | 118.2407 | -3.1112 | -1.5482 | 3.333 | 0.794 | 0.7698 | 1.6667 | 0.289 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=36.666666666667;prev_p60=65;z60=0.165553877913;prev_z60=0.572816951449;prev_v=0.53;last_v=0.47;zΔ60=-0.407263073537;pΔ60=-28.333333333333;ret1%=-11.320754716981 | NONE | NONE→WATCH | 1 | T10Y3M | OK | 0.02 | 2026-02-10 | 0.47 | 0.1656 | 1.6405 | 36.667 | 84.921 | -0.4073 | -28.3333 | -11.321 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.02 | 2026-02-10 | 50188.14 | 1.7342 | 1.8771 | 100 | 100 | -0.0261 | 0 | 0.104 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.02 | 2026-01-30 | -0.4778 | 1.4756 | 1.4479 | 100 | 100 | 0.0264 | 1.6667 | 1.056 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 0.02 | 2026-02-10 | 6941.81 | 0.8364 | 1.2534 | 81.667 | 95.635 | -0.2493 | -8.3333 | -0.33 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=86.666666666667;prev_p60=100;z60=0.98493179679;prev_z60=1.462451661522;prev_v=0.74;last_v=0.71;zΔ60=-0.477519864732;pΔ60=-13.333333333333;ret1%=-4.054054054054 | INFO | SAME | 0 | T10Y2Y | OK | 0.02 | 2026-02-10 | 0.71 | 0.9849 | 1.5375 | 86.667 | 96.825 | -0.4775 | -13.3333 | -4.054 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | BAMLH0A0HYM2 | OK | 0.02 | 2026-02-09 | 2.84 | -0.28 | -0.6207 | 41.667 | 28.175 | -0.1895 | -8.3333 | -1.045 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 1 | P | p60=91.666666666667;prev_p60=76.666666666667;z60=1.405252182943;prev_z60=0.743254468694;prev_v=60.46;last_v=61.6;zΔ60=0.661997714249;pΔ60=15;ret1%=1.885544161429 | NONE | SAME | 0 | DCOILWTICO | OK | 0.02 | 2026-02-02 | 61.6 | 1.4053 | -0.681 | 91.667 | 26.984 | 0.662 | 15 | 1.886 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.02 | 2026-02-09 | 4.22 | 0.7996 | -0.2516 | 80 | 43.651 | -0.0245 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.02 | 2026-02-09 | 3.48 | -0.8124 | -1.1809 | 33.333 | 11.905 | -0.3581 | -5 | -0.571 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.02 | 2026-02-10 | 23102.47 | -0.4552 | 0.9627 | 28.333 | 78.175 | -0.3398 | -8.3333 | -0.586 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=33.333333333333;prev_p60=28.333333333333;z60=-0.488886491383;prev_z60=-0.634085378622;prev_v=-0.7123;last_v=-0.6784;zΔ60=0.145198887239;pΔ60=5;ret1%=4.759230661238 | NONE | SAME | 0 | STLFSI4 | OK | 0.02 | 2026-01-30 | -0.6784 | -0.4889 | -0.5471 | 33.333 | 35.317 | 0.1452 | 5 | 4.759 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=71.666666666667;prev_p60=76.666666666667;z60=0.094392639957;prev_z60=0.239328472884;prev_v=17.76;last_v=17.36;zΔ60=-0.144935832927;pΔ60=-5;ret1%=-2.252252252252 | WATCH | WATCH→NONE | 0 | VIXCLS | OK | 0.02 | 2026-02-09 | 17.36 | 0.0944 | -0.3087 | 71.667 | 52.381 | -0.1449 | -5 | -2.252 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-11T20:00:04+08:00 |
