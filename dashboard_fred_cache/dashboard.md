# Risk Dashboard (fred_cache)

- Summary: ALERT=5 / WATCH=4 / INFO=2 / NONE=2; CHANGED=5; WATCH_STREAK>=3=0; NEAR=8; JUMP_1of3=1
- RUN_TS_UTC: `2026-03-14T13:52:31.335572+00:00`
- day_key_local: `2026-03-14`
- STATS.generated_at_utc: `2026-03-14T13:13:33+00:00`
- STATS.as_of_ts: `2026-03-14T21:13:31+08:00`
- STATS.generated_at_utc(norm): `2026-03-14T13:13:33+00:00`
- STATS.data_commit_sha: `2e1243e41570c4d92220518f97eb606a36aa8473`
- snapshot_id: `commit:2e1243e41570c4d92220518f97eb606a36aa8473`
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
| ALERT | EXTREME_Z | NEAR:ret1% | 1 | R | p60=100;prev_p60=100;z60=4.294183566752;prev_z60=4.629212284865;prev_v=90.77;last_v=94.65;zΔ60=-0.335028718113;pΔ60=0;ret1%=4.274540046271 | ALERT | SAME | 0 | DCOILWTICO | OK | 0.65 | 2026-03-09 | 94.65 | 4.2942 | 6.2686 | 100 | 100 | -0.335 | 0 | 4.275 | P252>=95;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=100;z60=3.824701948903;prev_z60=2.373335795741;prev_v=3.64;last_v=3.76;zΔ60=1.451366153162;pΔ60=0;ret1%=3.296703296703 | WATCH | WATCH→ALERT | 0 | DGS2 | OK | 0.65 | 2026-03-12 | 3.76 | 3.8247 | 0.4076 | 100 | 65.873 | 1.4514 | 0 | 3.297 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| ALERT | EXTREME_Z | NA | 0 | NA | NA | ALERT | SAME | 0 | DJIA | OK | 0.65 | 2026-03-13 | 46558.47 | -2.9738 | 0.4079 | 1.667 | 61.111 | 0.1163 | 0 | -0.256 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| ALERT | EXTREME_Z | NA | 0 | NA | NA | ALERT | SAME | 0 | SP500 | OK | 0.65 | 2026-03-13 | 6632.19 | -3.2557 | 0.4734 | 1.667 | 54.762 | -0.2271 | 0 | -0.606 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=95;z60=2.576677414709;prev_z60=1.863091101675;prev_v=24.23;last_v=27.29;zΔ60=0.713586313033;pΔ60=3.333333333333;ret1%=12.628972348329 | NONE | NONE→ALERT | 0 | VIXCLS | OK | 0.65 | 2026-03-12 | 27.29 | 2.5767 | 1.5589 | 98.333 | 94.048 | 0.7136 | 3.3333 | 12.629 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| WATCH | EXTREME_Z | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=93.333333333333;z60=2.23993858932;prev_z60=1.741160410051;prev_v=3.09;last_v=3.17;zΔ60=0.498778179269;pΔ60=5;ret1%=2.588996763754 | NONE | NONE→WATCH | 1 | BAMLH0A0HYM2 | OK | 0.65 | 2026-03-12 | 3.17 | 2.2399 | 0.3024 | 98.333 | 79.365 | 0.4988 | 5 | 2.589 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=93.333333333333;prev_p60=75;z60=1.411557442608;prev_z60=0.652714756159;prev_v=4.21;last_v=4.27;zΔ60=0.758842686449;pΔ60=18.333333333333;ret1%=1.425178147268 | WATCH | SAME | 2 | DGS10 | OK | 0.65 | 2026-03-12 | 4.27 | 1.4116 | 0.2914 | 93.333 | 63.492 | 0.7588 | 18.3333 | 1.425 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 2 | NASDAQCOM | OK | 0.65 | 2026-03-13 | 22105.36 | -2.3558 | 0.392 | 1.667 | 50.794 | -0.344 | 0 | -0.926 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=6.666666666667;prev_p60=1.666666666667;z60=-1.764303148972;prev_z60=-2.559813930678;prev_v=0.51;last_v=0.55;zΔ60=0.795510781706;pΔ60=5;ret1%=7.843137254902 | ALERT | ALERT→WATCH | 1 | T10Y2Y | OK | 0.65 | 2026-03-13 | 0.55 | -1.7643 | 0.0363 | 6.667 | 58.333 | 0.7955 | 5 | 7.843 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.65 | 2026-03-06 | -0.4587 | 1.6416 | 1.5892 | 100 | 100 | 0.0053 | 0 | 0.854 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 0 | NA | p60=83.333333333333;prev_p60=80;z60=0.884756412143;prev_z60=0.772930785667;prev_v=0.55;last_v=0.56;zΔ60=0.111825626476;pΔ60=3.333333333333;ret1%=1.818181818182 | WATCH | WATCH→INFO | 0 | T10Y3M | OK | 0.65 | 2026-03-13 | 0.56 | 0.8848 | 1.8261 | 83.333 | 96.032 | 0.1118 | 3.3333 | 1.818 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.65 | 2026-03-06 | 119.491 | 0.4823 | -0.814 | 56.667 | 13.492 | -0.0431 | -1.6667 | -0.065 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=75;prev_p60=75;z60=0.476401492764;prev_z60=0.435978634339;prev_v=-0.4436;last_v=-0.4279;zΔ60=0.040422858425;pΔ60=0;ret1%=3.539224526601 | NONE | SAME | 0 | STLFSI4 | OK | 0.65 | 2026-03-06 | -0.4279 | 0.4764 | 0.193 | 75 | 67.063 | 0.0404 | 0 | 3.539 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-14T21:13:31+08:00 |
