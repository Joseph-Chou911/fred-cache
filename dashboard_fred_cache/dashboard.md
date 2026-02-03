# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=4 / INFO=5 / NONE=3; CHANGED=3; WATCH_STREAK>=3=0; NEAR=8; JUMP_1of3=4
- RUN_TS_UTC: `2026-02-03T23:00:10.029669+00:00`
- day_key_local: `2026-02-04`
- STATS.generated_at_utc: `2026-02-03T22:57:50+00:00`
- STATS.as_of_ts: `2026-02-04T06:57:48+08:00`
- STATS.generated_at_utc(norm): `2026-02-03T22:57:50+00:00`
- STATS.data_commit_sha: `fbc3f18e0aa603099c345b3e80e9643768406777`
- snapshot_id: `commit:fbc3f18e0aa603099c345b3e80e9643768406777`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=1.666666666667;prev_p60=1.666666666667;z60=-3.881003518348;prev_z60=-2.595576368124;prev_v=119.2855;last_v=117.8996;zΔ60=-1.285427150224;pΔ60=0;ret1%=-1.161834422457 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.04 | 2026-01-30 | 117.8996 | -3.881 | -1.6711 | 1.667 | 0.397 | -1.2854 | 0 | -1.162 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=33.333333333333;prev_p60=50;z60=-0.571001919677;prev_z60=-0.127360072295;prev_v=2.88;last_v=2.81;zΔ60=-0.443641847381;pΔ60=-16.666666666667;ret1%=-2.430555555556 | WATCH | SAME | 2 | BAMLH0A0HYM2 | OK | 0.04 | 2026-02-02 | 2.81 | -0.571 | -0.6823 | 33.333 | 22.222 | -0.4436 | -16.6667 | -2.431 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | NONE | NONE→WATCH | 1 | DGS10 | OK | 0.04 | 2026-02-02 | 4.29 | 2.07 | 0.1888 | 98.333 | 61.111 | 0.3558 | 0 | 0.704 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=76.666666666667;prev_p60=48.333333333333;z60=0.806078421995;prev_z60=-0.142829594572;prev_v=3.52;last_v=3.57;zΔ60=0.948908016567;pΔ60=28.333333333333;ret1%=1.420454545455 | NONE | NONE→WATCH | 1 | DGS2 | OK | 0.04 | 2026-02-02 | 3.57 | 0.8061 | -0.8097 | 76.667 | 29.365 | 0.9489 | 28.3333 | 1.42 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=45;prev_p60=71.666666666667;z60=-0.2666364388;prev_z60=0.131194658678;prev_v=17.44;last_v=16.34;zΔ60=-0.397831097478;pΔ60=-26.666666666667;ret1%=-6.307339449541 | NONE | NONE→WATCH | 1 | VIXCLS | OK | 0.04 | 2026-02-02 | 16.34 | -0.2666 | -0.4877 | 45 | 31.746 | -0.3978 | -26.6667 | -6.307 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| INFO | LONG_EXTREME | NEAR:PΔ60 | 1 | P | p60=91.666666666667;prev_p60=71.666666666667;z60=1.279342109478;prev_z60=0.793643952063;prev_v=48892.470000000001;last_v=49407.660000000003;zΔ60=0.485698157415;pΔ60=20;ret1%=1.053720542243 | INFO | SAME | 0 | DJIA | OK | 0.04 | 2026-02-02 | 49407.66 | 1.2793 | 1.7051 | 91.667 | 98.016 | 0.4857 | 20 | 1.054 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=90;z60=1.449255202935;prev_z60=1.23769212487;prev_v=-0.50568;last_v=-0.48295;zΔ60=0.211563078064;pΔ60=8.333333333333;ret1%=4.494937509888 | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.04 | 2026-01-23 | -0.4829 | 1.4493 | 1.423 | 98.333 | 99.603 | 0.2116 | 8.3333 | 4.495 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 0.04 | 2026-02-02 | 6976.44 | 1.2883 | 1.3834 | 95 | 98.81 | 0.3271 | 11.6667 | 0.539 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y2Y | OK | 0.04 | 2026-02-03 | 0.71 | 1.202 | 1.6064 | 93.333 | 98.413 | -0.1852 | -3.3333 | -1.389 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y3M | OK | 0.04 | 2026-02-03 | 0.59 | 1.0483 | 2.3181 | 96.667 | 99.206 | -0.0907 | -3.3333 | -1.667 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DCOILWTICO | OK | 0.04 | 2026-01-26 | 60.46 | 0.7433 | -0.9029 | 76.667 | 20.635 | 0.1339 | 3.3333 | 0.265 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=81.666666666667;prev_p60=55;z60=0.755841199494;prev_z60=0.420160304586;prev_v=23461.82;last_v=23592.110000000001;zΔ60=0.335680894908;pΔ60=26.666666666667;ret1%=0.555327762296 | NONE | SAME | 0 | NASDAQCOM | OK | 0.04 | 2026-02-02 | 23592.11 | 0.7558 | 1.2214 | 81.667 | 93.651 | 0.3357 | 26.6667 | 0.555 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=28.333333333333;prev_p60=35;z60=-0.634085378622;prev_z60=-0.397953005876;prev_v=-0.651;last_v=-0.7123;zΔ60=-0.236132372747;pΔ60=-6.666666666667;ret1%=-9.416282642089 | NONE | SAME | 0 | STLFSI4 | OK | 0.04 | 2026-01-23 | -0.7123 | -0.6341 | -0.6485 | 28.333 | 28.968 | -0.2361 | -6.6667 | -9.416 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-04T06:57:48+08:00 |
