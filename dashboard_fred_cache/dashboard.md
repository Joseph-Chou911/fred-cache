# Risk Dashboard (fred_cache)

- Summary: ALERT=2 / WATCH=4 / INFO=2 / NONE=5; CHANGED=4; WATCH_STREAK>=3=1; NEAR=8; JUMP_1of3=2
- RUN_TS_UTC: `2026-03-07T13:46:49.227150+00:00`
- day_key_local: `2026-03-07`
- STATS.generated_at_utc: `2026-03-07T13:07:43+00:00`
- STATS.as_of_ts: `2026-03-07T21:07:30+08:00`
- STATS.generated_at_utc(norm): `2026-03-07T13:07:43+00:00`
- STATS.data_commit_sha: `c11c55d2ea9f36ce30cf7c6251f9a88776c3522c`
- snapshot_id: `commit:c11c55d2ea9f36ce30cf7c6251f9a88776c3522c`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=100;z60=2.925254423533;prev_z60=1.930669257529;prev_v=66.96;last_v=71.13;zΔ60=0.994585166004;pΔ60=0;ret1%=6.227598566308 | ALERT | SAME | 0 | DCOILWTICO | OK | 0.65 | 2026-03-02 | 71.13 | 2.9253 | 1.8686 | 100 | 96.825 | 0.9946 | 0 | 6.228 | P252>=95;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=93.333333333333;z60=2.527993626484;prev_z60=1.636378294096;prev_v=21.15;last_v=23.75;zΔ60=0.891615332388;pΔ60=6.666666666667;ret1%=12.293144208038 | WATCH | WATCH→ALERT | 0 | VIXCLS | OK | 0.65 | 2026-03-05 | 23.75 | 2.528 | 0.929 | 100 | 90.476 | 0.8916 | 6.6667 | 12.293 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| WATCH | EXTREME_Z | NEAR:ZΔ60 | 0 | NA | p60=1.666666666667;prev_p60=8.333333333333;z60=-2.314159129247;prev_z60=-1.622573361374;prev_v=47954.739999999998;last_v=47501.550000000003;zΔ60=-0.691585767873;pΔ60=-6.666666666667;ret1%=-0.9450369244 | WATCH | SAME | 2 | DJIA | OK | 0.65 | 2026-03-06 | 47501.55 | -2.3142 | 0.754 | 1.667 | 71.825 | -0.6916 | -6.6667 | -0.945 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| WATCH | EXTREME_Z | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=1.666666666667;prev_p60=18.333333333333;z60=-2.058642711557;prev_z60=-1.231786671661;prev_v=22748.990000000002;last_v=22387.68;zΔ60=-0.826856039896;pΔ60=-16.666666666667;ret1%=-1.588246335332 | NONE | NONE→WATCH | 1 | NASDAQCOM | OK | 0.65 | 2026-03-06 | 22387.68 | -2.0586 | 0.5497 | 1.667 | 55.556 | -0.8269 | -16.6667 | -1.588 | abs(Z60)>=2;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| WATCH | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=3.333333333333;prev_p60=15;z60=-2.490025789297;prev_z60=-1.066696644445;prev_v=6830.71;last_v=6740.02;zΔ60=-1.423329144851;pΔ60=-11.666666666667;ret1%=-1.327680431463 | NONE | NONE→WATCH | 1 | SP500 | OK | 0.65 | 2026-03-06 | 6740.02 | -2.49 | 0.7194 | 3.333 | 67.857 | -1.4233 | -11.6667 | -1.328 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=75;prev_p60=50;z60=0.435978634339;prev_z60=-0.162988734641;prev_v=-0.5981;last_v=-0.4436;zΔ60=0.59896736898;pΔ60=25;ret1%=25.831800702224 | WATCH | SAME | 3 | STLFSI4 | OK | 0.65 | 2026-02-27 | -0.4436 | 0.436 | 0.1497 | 75 | 65.873 | 0.599 | 25 | 25.832 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DTWEXBGS | OK | 0.65 | 2026-02-27 | 117.8223 | -1.1649 | -1.5271 | 18.333 | 4.365 | -0.0374 | -3.3333 | -0.069 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.65 | 2026-02-27 | -0.4627 | 1.6364 | 1.5655 | 100 | 100 | 0.0086 | 0 | 0.88 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | BAMLH0A0HYM2 | OK | 0.65 | 2026-03-05 | 3 | 1.2967 | -0.1662 | 93.333 | 60.317 | 0.2343 | 5 | 1.01 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.65 | 2026-03-05 | 4.13 | -0.4122 | -0.7286 | 30 | 27.778 | 0.5378 | 6.6667 | 0.978 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.65 | 2026-03-05 | 3.57 | 1.2098 | -0.6349 | 90 | 38.095 | 0.5378 | 13.3333 | 0.847 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=13.333333333333;prev_p60=5;z60=-1.312371317635;prev_z60=-1.906419539339;prev_v=0.56;last_v=0.59;zΔ60=0.594048221704;pΔ60=8.333333333333;ret1%=5.357142857143 | NONE | SAME | 0 | T10Y2Y | OK | 0.65 | 2026-03-06 | 0.59 | -1.3124 | 0.4795 | 13.333 | 75.794 | 0.594 | 8.3333 | 5.357 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=33.333333333333;prev_p60=25;z60=-0.329997080286;prev_z60=-0.691319706788;prev_v=0.43;last_v=0.46;zΔ60=0.361322626502;pΔ60=8.333333333333;ret1%=6.976744186047 | NONE | SAME | 0 | T10Y3M | OK | 0.65 | 2026-03-06 | 0.46 | -0.33 | 1.4539 | 33.333 | 84.127 | 0.3613 | 8.3333 | 6.977 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-07T21:07:30+08:00 |
