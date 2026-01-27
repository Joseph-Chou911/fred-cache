# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=0 / INFO=5 / NONE=7; CHANGED=5; WATCH_STREAK>=3=0; NEAR=7; JUMP_1of3=5
- RUN_TS_UTC: `2026-01-27T13:50:13.782435+00:00`
- day_key_local: `2026-01-27`
- STATS.generated_at_utc: `2026-01-27T13:49:15+00:00`
- STATS.as_of_ts: `2026-01-27T21:49:13+08:00`
- STATS.generated_at_utc(norm): `2026-01-27T13:49:15+00:00`
- STATS.data_commit_sha: `005b6f1996a4914661e5d7981e1896c4e4c5f987`
- snapshot_id: `commit:005b6f1996a4914661e5d7981e1896c4e4c5f987`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=1.666666666667;prev_p60=21.666666666667;z60=-2.595576368124;prev_z60=-1.045572439498;prev_v=120.4478;last_v=119.2855;zΔ60=-1.550003928626;pΔ60=-20;ret1%=-0.964982340898 | NONE | NONE→ALERT | 0 | DTWEXBGS | OK | 0.02 | 2026-01-23 | 119.2855 | -2.5956 | -1.2219 | 1.667 | 0.397 | -1.55 | -20 | -0.965 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.02 | 2026-01-26 | 49412.4 | 1.4592 | 1.7846 | 93.333 | 98.413 | 0.2792 | 8.3333 | 0.639 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| INFO | LONG_EXTREME | NEAR:PΔ60 | 1 | P | p60=86.666666666667;prev_p60=63.333333333333;z60=0.772501706087;prev_z60=0.491716195057;prev_v=23501.240000000002;last_v=23601.360000000001;zΔ60=0.28078551103;pΔ60=23.333333333333;ret1%=0.426020073834 | NONE | NONE→INFO | 0 | NASDAQCOM | OK | 0.02 | 2026-01-26 | 23601.36 | 0.7725 | 1.2783 | 86.667 | 96.032 | 0.2808 | 23.3333 | 0.426 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.02 | 2026-01-16 | -0.5057 | 1.2377 | 1.3336 | 90 | 97.619 | 0.0201 | 1.6667 | 0.851 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 0.02 | 2026-01-26 | 6950.23 | 1.2149 | 1.3906 | 95 | 98.81 | 0.347 | 13.3333 | 0.501 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 0 | NA | p60=90;prev_p60=86.666666666667;z60=1.026316958455;prev_z60=1.001964960139;prev_v=0.54;last_v=0.55;zΔ60=0.024351998315;pΔ60=3.333333333333;ret1%=1.851851851852 | INFO | SAME | 0 | T10Y3M | OK | 0.02 | 2026-01-26 | 0.55 | 1.0263 | 2.2987 | 90 | 97.619 | 0.0244 | 3.3333 | 1.852 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | NA | NA | 0 | NA | NA | ALERT | ALERT→NONE | 0 | BAMLH0A0HYM2 | OK | 0.02 | 2026-01-23 | 2.68 | -1.64 | -1.0217 | 5 | 5.556 | 0.3073 | 3.3333 | 1.515 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=73.333333333333;prev_p60=56.666666666667;z60=0.609351143621;prev_z60=0.029178106248;prev_v=59.39;last_v=60.3;zΔ60=0.580173037373;pΔ60=16.666666666667;ret1%=1.532244485604 | NONE | SAME | 0 | DCOILWTICO | OK | 0.02 | 2026-01-20 | 60.3 | 0.6094 | -0.9399 | 73.333 | 19.444 | 0.5802 | 16.6667 | 1.532 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS10 | OK | 0.02 | 2026-01-23 | 4.24 | 1.6497 | -0.1911 | 95 | 46.825 | -0.3685 | -3.3333 | -0.469 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.02 | 2026-01-23 | 3.6 | 1.2634 | -0.721 | 91.667 | 35.714 | -0.2237 | -5 | -0.277 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=35;prev_p60=31.666666666667;z60=-0.397953005876;prev_z60=-0.454103944422;prev_v=-0.6644;last_v=-0.651;zΔ60=0.056150938546;pΔ60=3.333333333333;ret1%=2.016857314871 | NONE | SAME | 0 | STLFSI4 | OK | 0.02 | 2026-01-16 | -0.651 | -0.398 | -0.4654 | 35 | 38.889 | 0.0562 | 3.3333 | 2.017 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=70;prev_p60=60;z60=0.729878589132;prev_z60=0.465646487809;prev_v=0.64;last_v=0.66;zΔ60=0.264232101322;pΔ60=10;ret1%=3.125 | NONE | SAME | 0 | T10Y2Y | OK | 0.02 | 2026-01-26 | 0.66 | 0.7299 | 1.2971 | 70 | 92.46 | 0.2642 | 10 | 3.125 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=41.666666666667;prev_p60=30;z60=-0.395351785025;prev_z60=-0.564433146607;prev_v=15.64;last_v=16.09;zΔ60=0.169081361582;pΔ60=11.666666666667;ret1%=2.877237851662 | WATCH | WATCH→NONE | 0 | VIXCLS | OK | 0.02 | 2026-01-23 | 16.09 | -0.3954 | -0.535 | 41.667 | 28.175 | 0.1691 | 11.6667 | 2.877 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-27T21:49:13+08:00 |
