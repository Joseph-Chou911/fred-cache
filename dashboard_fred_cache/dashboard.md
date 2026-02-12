# Risk Dashboard (fred_cache)

- Summary: ALERT=2 / WATCH=2 / INFO=4 / NONE=5; CHANGED=5; WATCH_STREAK>=3=0; NEAR=8; JUMP_1of3=4
- RUN_TS_UTC: `2026-02-12T14:14:42.438835+00:00`
- day_key_local: `2026-02-12`
- STATS.generated_at_utc: `2026-02-12T13:42:08+00:00`
- STATS.as_of_ts: `2026-02-12T21:42:06+08:00`
- STATS.generated_at_utc(norm): `2026-02-12T13:42:08+00:00`
- STATS.data_commit_sha: `ef784baecaa7550c06d842b6b2ae6a9136d6914a`
- snapshot_id: `commit:ef784baecaa7550c06d842b6b2ae6a9136d6914a`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=91.666666666667;z60=2.902879225783;prev_z60=1.405252182943;prev_v=61.6;last_v=64.53;zΔ60=1.49762704284;pΔ60=8.333333333333;ret1%=4.756493506494 | NONE | NONE→ALERT | 0 | DCOILWTICO | OK | 0.54 | 2026-02-09 | 64.53 | 2.9029 | -0.1167 | 100 | 53.571 | 1.4976 | 8.3333 | 4.756 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=3.333333333333;prev_p60=1.666666666667;z60=-3.11119123456;prev_z60=-3.881003518348;prev_v=117.8996;last_v=118.2407;zΔ60=0.769812283789;pΔ60=1.666666666667;ret1%=0.289313958656 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.54 | 2026-02-06 | 118.2407 | -3.1112 | -1.5482 | 3.333 | 0.794 | 0.7698 | 1.6667 | 0.289 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=48.333333333333;prev_p60=80;z60=-0.085109292318;prev_z60=0.799568782203;prev_v=4.22;last_v=4.16;zΔ60=-0.884678074521;pΔ60=-31.666666666667;ret1%=-1.421800947867 | NONE | NONE→WATCH | 1 | DGS10 | OK | 0.54 | 2026-02-10 | 4.16 | -0.0851 | -0.6645 | 48.333 | 30.159 | -0.8847 | -31.6667 | -1.422 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | p60=51.666666666667;prev_p60=86.666666666667;z60=0.189279784855;prev_z60=0.98493179679;prev_v=0.71;last_v=0.66;zΔ60=-0.795652011935;pΔ60=-35;ret1%=-7.042253521127 | INFO | INFO→WATCH | 1 | T10Y2Y | OK | 0.54 | 2026-02-11 | 0.66 | 0.1893 | 1.1345 | 51.667 | 88.095 | -0.7957 | -35 | -7.042 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| INFO | LONG_EXTREME | NEAR:PΔ60 | 1 | P | p60=10;prev_p60=33.333333333333;z60=-1.344662813192;prev_z60=-0.812391332511;prev_v=3.48;last_v=3.45;zΔ60=-0.532271480681;pΔ60=-23.333333333333;ret1%=-0.862068965517 | NONE | NONE→INFO | 0 | DGS2 | OK | 0.54 | 2026-02-10 | 3.45 | -1.3447 | -1.3091 | 10 | 3.571 | -0.5323 | -23.3333 | -0.862 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.54 | 2026-02-11 | 50121.4 | 1.6024 | 1.8332 | 96.667 | 99.206 | -0.1318 | -3.3333 | -0.133 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.54 | 2026-02-06 | -0.4746 | 1.4829 | 1.4666 | 100 | 100 | 0.0073 | 0 | 0.682 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 0.54 | 2026-02-11 | 6941.47 | 0.8046 | 1.2426 | 80 | 95.238 | -0.0318 | -1.6667 | -0.005 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.54 | 2026-02-10 | 2.86 | -0.1109 | -0.5693 | 50 | 31.349 | 0.1691 | 8.3333 | 0.704 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.54 | 2026-02-11 | 23066.47 | -0.5608 | 0.94 | 26.667 | 77.778 | -0.1056 | -1.6667 | -0.156 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=36.666666666667;prev_p60=33.333333333333;z60=-0.393935395483;prev_z60=-0.488886491383;prev_v=-0.6784;last_v=-0.6558;zΔ60=0.0949510959;pΔ60=3.333333333333;ret1%=3.331367924528 | NONE | SAME | 0 | STLFSI4 | OK | 0.54 | 2026-02-06 | -0.6558 | -0.3939 | -0.4817 | 36.667 | 38.095 | 0.095 | 3.3333 | 3.331 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=40;prev_p60=36.666666666667;z60=0.201030126622;prev_z60=0.165553877913;prev_v=0.47;last_v=0.48;zΔ60=0.035476248709;pΔ60=3.333333333333;ret1%=2.127659574468 | WATCH | WATCH→NONE | 0 | T10Y3M | OK | 0.54 | 2026-02-11 | 0.48 | 0.201 | 1.6709 | 40 | 85.714 | 0.0355 | 3.3333 | 2.128 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=78.333333333333;prev_p60=71.666666666667;z60=0.267020882578;prev_z60=0.094392639957;prev_v=17.36;last_v=17.79;zΔ60=0.172628242622;pΔ60=6.666666666667;ret1%=2.476958525346 | NONE | SAME | 0 | VIXCLS | OK | 0.54 | 2026-02-10 | 17.79 | 0.267 | -0.2295 | 78.333 | 57.937 | 0.1726 | 6.6667 | 2.477 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-12T21:42:06+08:00 |
