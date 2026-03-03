# Risk Dashboard (fred_cache)

- Summary: ALERT=3 / WATCH=1 / INFO=2 / NONE=7; CHANGED=5; WATCH_STREAK>=3=1; NEAR=3; JUMP_1of3=3
- RUN_TS_UTC: `2026-03-03T14:03:43.138096+00:00`
- day_key_local: `2026-03-03`
- STATS.generated_at_utc: `2026-03-03T13:21:19+00:00`
- STATS.as_of_ts: `2026-03-03T21:21:18+08:00`
- STATS.generated_at_utc(norm): `2026-03-03T13:21:19+00:00`
- STATS.data_commit_sha: `6730cb66970e0ba16f10a1588a0720c8053fa0eb`
- snapshot_id: `commit:6730cb66970e0ba16f10a1588a0720c8053fa0eb`
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
| ALERT | EXTREME_Z | NA | 0 | NA | NA | NONE | NONE→ALERT | 0 | BAMLH0A0HYM2 | OK | 0.71 | 2026-02-28 | 3.12 | 2.6474 | 0.1555 | 100 | 71.032 | -0.0133 | 0 | 0.645 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| ALERT | EXTREME_Z | NA | 0 | NA | NA | WATCH | WATCH→ALERT | 0 | DGS10 | OK | 0.71 | 2026-02-27 | 3.97 | -2.6073 | -1.9209 | 1.667 | 0.794 | -0.5482 | 0 | -1.244 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| ALERT | EXTREME_Z | NA | 0 | NA | NA | ALERT | SAME | 0 | DGS2 | OK | 0.71 | 2026-02-27 | 3.38 | -2.2465 | -1.6432 | 1.667 | 0.397 | -0.6163 | -1.6667 | -1.17 | P252<=2;abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 6 | DCOILWTICO | OK | 0.71 | 2026-02-23 | 66.36 | 2.0613 | 0.6316 | 96.667 | 73.413 | -0.2337 | -3.3333 | -0.495 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | NONE | NONE→INFO | 0 | DTWEXBGS | OK | 0.71 | 2026-02-27 | 117.8223 | -1.1649 | -1.5271 | 18.333 | 4.365 | -0.0374 | -3.3333 | -0.069 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.71 | 2026-02-20 | -0.4668 | 1.6277 | 1.5414 | 100 | 100 | 0.0078 | 0 | 0.835 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DJIA | OK | 0.71 | 2026-03-02 | 48904.78 | -0.0504 | 1.2543 | 41.667 | 86.111 | -0.1456 | -5 | -0.149 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.71 | 2026-03-02 | 22748.86 | -1.3983 | 0.7318 | 15 | 66.667 | 0.2757 | 5 | 0.356 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | SP500 | OK | 0.71 | 2026-03-02 | 6881.62 | -0.1993 | 1.0253 | 41.667 | 85.317 | 0.0309 | 1.6667 | 0.04 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=50;prev_p60=48.333333333333;z60=-0.162988734641;prev_z60=-0.250970486178;prev_v=-0.6208;last_v=-0.5981;zΔ60=0.087981751537;pΔ60=1.666666666667;ret1%=3.656572164948 | NONE | SAME | 0 | STLFSI4 | OK | 0.71 | 2026-02-20 | -0.5981 | -0.163 | -0.3125 | 50 | 48.016 | 0.088 | 1.6667 | 3.657 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.71 | 2026-03-02 | 0.58 | -1.6185 | 0.4034 | 6.667 | 73.016 | -0.2049 | -5 | -1.695 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=3.333333333333;prev_p60=1.666666666667;z60=-1.915789822371;prev_z60=-2.271099895831;prev_v=0.3;last_v=0.33;zΔ60=0.35531007346;pΔ60=1.666666666667;ret1%=10 | WATCH | WATCH→NONE | 0 | T10Y3M | OK | 0.71 | 2026-03-02 | 0.33 | -1.9158 | 0.9066 | 3.333 | 76.984 | 0.3553 | 1.6667 | 10 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=86.666666666667;prev_p60=78.333333333333;z60=1.379544223422;prev_z60=0.841980512869;prev_v=18.63;last_v=19.86;zΔ60=0.537563710554;pΔ60=8.333333333333;ret1%=6.602254428341 | NONE | SAME | 0 | VIXCLS | OK | 0.71 | 2026-02-27 | 19.86 | 1.3795 | 0.168 | 86.667 | 73.016 | 0.5376 | 8.3333 | 6.602 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-03T21:21:18+08:00 |
