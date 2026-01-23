# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=4 / NONE=7; CHANGED=5; WATCH_STREAK>=3=0; NEAR=4; JUMP_1of3=1
- RUN_TS_UTC: `2026-01-23T14:02:06.304037+00:00`
- day_key_local: `2026-01-23`
- STATS.generated_at_utc: `2026-01-23T13:55:41+00:00`
- STATS.as_of_ts: `2026-01-23T21:55:31+08:00`
- STATS.generated_at_utc(norm): `2026-01-23T13:55:41+00:00`
- STATS.data_commit_sha: `36c2900455cdca1f5620f39f7ae7693ab9ace1fc`
- snapshot_id: `commit:36c2900455cdca1f5620f39f7ae7693ab9ace1fc`
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
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(2/3 vote: abs(zΔ60)>=0.75, abs(pΔ60)>=20, abs(ret1%)>=2 -> WATCH); Near(within 10% of jump thresholds)`

| Signal | Tag | Near | JUMP_HITS | HITBITS | DBG | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | z252 | p60 | p252 | z_delta60 | p_delta60 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | EXTREME_Z | NEAR:ZΔ60 | 0 | NA | p60=98.333333333333;prev_p60=100;z60=2.093672411509;prev_z60=2.770368590001;prev_v=4.3;last_v=4.26;zΔ60=-0.676696178492;pΔ60=-1.666666666667;ret1%=-0.93023255814 | ALERT | ALERT→WATCH | 1 | DGS10 | OK | 0.11 | 2026-01-21 | 4.26 | 2.0937 | -0.0803 | 98.333 | 50.794 | -0.6767 | -1.6667 | -0.93 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | p60=55;prev_p60=90;z60=-0.098444930935;prev_z60=1.086958478575;prev_v=20.09;last_v=16.9;zΔ60=-1.18540340951;pΔ60=-35;ret1%=-15.878546540567 | NONE | NONE→WATCH | 1 | VIXCLS | OK | 0.11 | 2026-01-21 | 16.9 | -0.0984 | -0.3833 | 55 | 46.429 | -1.1854 | -35 | -15.879 | abs(zΔ60)>=0.75;abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.11 | 2026-01-22 | 49384.01 | 1.5282 | 1.8101 | 93.333 | 98.413 | 0.2738 | 6.6667 | 0.625 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.11 | 2026-01-16 | -0.5057 | 1.2377 | 1.3336 | 90 | 97.619 | 0.0201 | 1.6667 | 0.851 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | WATCH | WATCH→INFO | 0 | SP500 | OK | 0.11 | 2026-01-22 | 6913.35 | 0.8549 | 1.3373 | 81.667 | 95.635 | 0.3804 | 15 | 0.549 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y3M | OK | 0.11 | 2026-01-22 | 0.55 | 1.0898 | 2.3552 | 90 | 97.619 | -0.088 | -5 | -1.786 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.11 | 2026-01-21 | 2.69 | -1.6686 | -0.9974 | 3.333 | 5.952 | -0.2481 | -1.6667 | -1.465 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DCOILWTICO | OK | 0.11 | 2026-01-20 | 60.3 | 0.6094 | -0.9399 | 73.333 | 19.444 | 0.5802 | 16.6667 | 1.532 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.11 | 2026-01-21 | 3.6 | 1.3661 | -0.7324 | 93.333 | 35.317 | -0.0473 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.11 | 2026-01-16 | 120.4478 | -1.0456 | -0.8437 | 21.667 | 14.683 | -0.19 | -5 | -0.114 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | NA | NEAR:PΔ60 | 0 | NA | p60=51.666666666667;prev_p60=33.333333333333;z60=0.313333769536;prev_z60=-0.228766723637;prev_v=23224.82;last_v=23436.02;zΔ60=0.542100493173;pΔ60=18.333333333333;ret1%=0.909371956381 | NONE | SAME | 0 | NASDAQCOM | OK | 0.11 | 2026-01-22 | 23436.02 | 0.3133 | 1.2241 | 51.667 | 88.492 | 0.5421 | 18.3333 | 0.909 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=35;prev_p60=31.666666666667;z60=-0.397953005876;prev_z60=-0.454103944422;prev_v=-0.6644;last_v=-0.651;zΔ60=0.056150938546;pΔ60=3.333333333333;ret1%=2.016857314871 | NONE | SAME | 0 | STLFSI4 | OK | 0.11 | 2026-01-16 | -0.651 | -0.398 | -0.4654 | 35 | 38.889 | 0.0562 | 3.3333 | 2.017 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | T10Y2Y | OK | 0.11 | 2026-01-22 | 0.65 | 0.6316 | 1.2337 | 66.667 | 91.667 | -0.1685 | -3.3333 | -1.515 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-23T21:55:31+08:00 |
