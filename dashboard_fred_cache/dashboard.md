# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=3 / INFO=1 / NONE=8; CHANGED=3; WATCH_STREAK>=3=0; NEAR=6; JUMP_1of3=2
- RUN_TS_UTC: `2026-03-11T23:03:02.924309+00:00`
- day_key_local: `2026-03-12`
- STATS.generated_at_utc: `2026-03-11T23:02:21+00:00`
- STATS.as_of_ts: `2026-03-12T07:02:18+08:00`
- STATS.generated_at_utc(norm): `2026-03-11T23:02:21+00:00`
- STATS.data_commit_sha: `5cf3fb45d3165f965bc9c33ea4ddeecae39d743f`
- snapshot_id: `commit:5cf3fb45d3165f965bc9c33ea4ddeecae39d743f`
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
| ALERT | EXTREME_Z | NEAR:ret1% | 1 | R | p60=100;prev_p60=100;z60=4.294183566752;prev_z60=4.629212284865;prev_v=90.77;last_v=94.65;zΔ60=-0.335028718113;pΔ60=0;ret1%=4.274540046271 | ALERT | SAME | 0 | DCOILWTICO | OK | 0.01 | 2026-03-09 | 94.65 | 4.2942 | 6.2686 | 100 | 100 | -0.335 | 0 | 4.275 | P252>=95;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=91.666666666667;prev_p60=100;z60=1.54888400156;prev_z60=2.620244567573;prev_v=3.19;last_v=3.06;zΔ60=-1.071360566014;pΔ60=-8.333333333333;ret1%=-4.075235109718 | ALERT | ALERT→WATCH | 1 | BAMLH0A0HYM2 | OK | 0.01 | 2026-03-10 | 3.06 | 1.5489 | -0.0019 | 91.667 | 66.27 | -1.0714 | -8.3333 | -4.075 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=46.666666666667;prev_p60=30;z60=0.162021681977;prev_z60=-0.563122363643;prev_v=0.44;last_v=0.5;zΔ60=0.72514404562;pΔ60=16.666666666667;ret1%=13.636363636364 | NONE | NONE→WATCH | 1 | T10Y3M | OK | 0.01 | 2026-03-11 | 0.5 | 0.162 | 1.5966 | 46.667 | 87.302 | 0.7251 | 16.6667 | 13.636 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| WATCH | EXTREME_Z | NEAR:ret1% | 1 | R | p60=96.666666666667;prev_p60=98.333333333333;z60=2.17409635604;prev_z60=2.491418265839;prev_v=25.5;last_v=24.93;zΔ60=-0.317321909799;pΔ60=-1.666666666667;ret1%=-2.235294117647 | WATCH | SAME | 2 | VIXCLS | OK | 0.01 | 2026-03-10 | 24.93 | 2.1741 | 1.1298 | 96.667 | 92.063 | -0.3173 | -1.6667 | -2.235 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.01 | 2026-03-06 | -0.4587 | 1.6416 | 1.5892 | 100 | 100 | 0.0053 | 0 | 0.854 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=45;prev_p60=28.333333333333;z60=-0.131384219977;prev_z60=-0.527147175313;prev_v=4.12;last_v=4.15;zΔ60=0.395762955336;pΔ60=16.666666666667;ret1%=0.728155339806 | NONE | SAME | 0 | DGS10 | OK | 0.01 | 2026-03-10 | 4.15 | -0.1314 | -0.5764 | 45 | 34.921 | 0.3958 | 16.6667 | 0.728 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.01 | 2026-03-10 | 3.57 | 1.2405 | -0.616 | 91.667 | 39.286 | 0.1654 | 6.6667 | 0.281 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DJIA | OK | 0.01 | 2026-03-10 | 47706.51 | -1.9724 | 0.8093 | 3.333 | 73.81 | -0.0139 | 0 | -0.072 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.01 | 2026-03-06 | 119.491 | 0.4823 | -0.814 | 56.667 | 13.492 | -0.0431 | -1.6667 | -0.065 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.01 | 2026-03-10 | 22697.1 | -1.192 | 0.6731 | 20 | 64.683 | 0.0434 | 1.6667 | 0.005 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | SP500 | OK | 0.01 | 2026-03-10 | 6781.48 | -1.6928 | 0.7873 | 6.667 | 69.444 | -0.166 | 0 | -0.214 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=75;prev_p60=75;z60=0.476401492764;prev_z60=0.435978634339;prev_v=-0.4436;last_v=-0.4279;zΔ60=0.040422858425;pΔ60=0;ret1%=3.539224526601 | WATCH | WATCH→NONE | 0 | STLFSI4 | OK | 0.01 | 2026-03-06 | -0.4279 | 0.4764 | 0.193 | 75 | 67.063 | 0.0404 | 0 | 3.539 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.01 | 2026-03-11 | 0.57 | -1.6306 | 0.2581 | 8.333 | 67.46 | -0.1456 | -1.6667 | -1.724 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-12T07:02:18+08:00 |
