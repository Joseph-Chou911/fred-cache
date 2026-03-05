# Risk Dashboard (fred_cache)

- Summary: ALERT=2 / WATCH=4 / INFO=2 / NONE=5; CHANGED=5; WATCH_STREAK>=3=0; NEAR=6; JUMP_1of3=2
- RUN_TS_UTC: `2026-03-05T01:52:45.120785+00:00`
- day_key_local: `2026-03-05`
- STATS.generated_at_utc: `2026-03-05T01:51:52+00:00`
- STATS.as_of_ts: `2026-03-05T09:51:50+08:00`
- STATS.generated_at_utc(norm): `2026-03-05T01:51:52+00:00`
- STATS.data_commit_sha: `cb8301ec9c1965a49a40adc4babbd40ee2f61195`
- snapshot_id: `commit:cb8301ec9c1965a49a40adc4babbd40ee2f61195`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=100;z60=2.925254423533;prev_z60=1.930669257529;prev_v=66.96;last_v=71.13;zΔ60=0.994585166004;pΔ60=0;ret1%=6.227598566308 | WATCH | WATCH→ALERT | 0 | DCOILWTICO | OK | 0.01 | 2026-03-02 | 71.13 | 2.9253 | 1.8686 | 100 | 96.825 | 0.9946 | 0 | 6.228 | P252>=95;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 1 | R | p60=100;prev_p60=98.333333333333;z60=2.742206426743;prev_z60=2.01244117638;prev_v=21.44;last_v=23.57;zΔ60=0.729765250363;pΔ60=1.666666666667;ret1%=9.934701492537 | WATCH | WATCH→ALERT | 0 | VIXCLS | OK | 0.01 | 2026-03-03 | 23.57 | 2.7422 | 0.8892 | 100 | 88.889 | 0.7298 | 1.6667 | 9.935 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 2 | BAMLH0A0HYM2 | OK | 0.01 | 2026-03-03 | 3.08 | 2.0783 | 0.0491 | 96.667 | 66.27 | 0.3636 | 0 | 1.65 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=31.666666666667;prev_p60=11.666666666667;z60=-0.404800759602;prev_z60=-1.329060567054;prev_v=6816.63;last_v=6869.5;zΔ60=0.924259807451;pΔ60=20;ret1%=0.775603193954 | WATCH | SAME | 2 | SP500 | OK | 0.01 | 2026-03-04 | 6869.5 | -0.4048 | 0.9866 | 31.667 | 82.54 | 0.9243 | 20 | 0.776 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=75;prev_p60=50;z60=0.435978634339;prev_z60=-0.162988734641;prev_v=-0.5981;last_v=-0.4436;zΔ60=0.59896736898;pΔ60=25;ret1%=25.831800702224 | NONE | NONE→WATCH | 1 | STLFSI4 | OK | 0.01 | 2026-02-27 | -0.4436 | 0.436 | 0.1497 | 75 | 65.873 | 0.599 | 25 | 25.832 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 2 | T10Y2Y | OK | 0.01 | 2026-03-04 | 0.55 | -2.132 | 0.1062 | 3.333 | 60.317 | 0.0642 | 1.6667 | 0 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DTWEXBGS | OK | 0.01 | 2026-02-27 | 117.8223 | -1.1649 | -1.5271 | 18.333 | 4.365 | -0.0374 | -3.3333 | -0.069 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.01 | 2026-02-27 | -0.4627 | 1.6364 | 1.5655 | 100 | 100 | 0.0086 | 0 | 0.88 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS10 | OK | 0.01 | 2026-03-03 | 4.06 | -1.3608 | -1.2457 | 15 | 14.286 | 0.1343 | 1.6667 | 0.247 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 1 | P | p60=58.333333333333;prev_p60=40;z60=0.133601049026;prev_z60=-0.588896310709;prev_v=3.47;last_v=3.51;zΔ60=0.722497359736;pΔ60=18.333333333333;ret1%=1.152737752161 | WATCH | WATCH→NONE | 0 | DGS2 | OK | 0.01 | 2026-03-03 | 3.51 | 0.1336 | -0.9597 | 58.333 | 22.222 | 0.7225 | 18.3333 | 1.153 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DJIA | OK | 0.01 | 2026-03-04 | 48739.41 | -0.3593 | 1.1806 | 36.667 | 84.921 | 0.342 | 5 | 0.491 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.01 | 2026-03-03 | 22516.69 | -1.9288 | 0.625 | 1.667 | 58.333 | -0.5305 | -13.3333 | -1.021 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=16.666666666667;prev_p60=10;z60=-1.301307683366;prev_z60=-1.67945468855;prev_v=0.35;last_v=0.38;zΔ60=0.378147005185;pΔ60=6.666666666667;ret1%=8.571428571429 | NONE | SAME | 0 | T10Y3M | OK | 0.01 | 2026-03-04 | 0.38 | -1.3013 | 1.1159 | 16.667 | 79.762 | 0.3781 | 6.6667 | 8.571 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-05T09:51:50+08:00 |
