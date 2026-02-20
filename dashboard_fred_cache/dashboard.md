# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=3 / NONE=8; CHANGED=3; WATCH_STREAK>=3=0; NEAR=5; JUMP_1of3=3
- RUN_TS_UTC: `2026-02-20T00:39:12.434163+00:00`
- day_key_local: `2026-02-20`
- STATS.generated_at_utc: `2026-02-20T00:38:43+00:00`
- STATS.as_of_ts: `2026-02-20T08:38:40+08:00`
- STATS.generated_at_utc(norm): `2026-02-20T00:38:43+00:00`
- STATS.data_commit_sha: `31f7e9a0771edf05ab175b3e6fabb9057f6b8fb5`
- snapshot_id: `commit:31f7e9a0771edf05ab175b3e6fabb9057f6b8fb5`
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
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | p60=56.666666666667;prev_p60=86.666666666667;z60=0.23819796107;prev_z60=1.059185130599;prev_v=2.94;last_v=2.86;zΔ60=-0.820987169529;pΔ60=-30;ret1%=-2.721088435374 | NONE | NONE→WATCH | 1 | BAMLH0A0HYM2 | OK | 0.01 | 2026-02-18 | 2.86 | 0.2382 | -0.5702 | 56.667 | 30.952 | -0.821 | -30 | -2.721 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=35;prev_p60=5;z60=-0.763008141718;prev_z60=-1.568125998379;prev_v=3.43;last_v=3.47;zΔ60=0.805117856661;pΔ60=30;ret1%=1.166180758017 | ALERT | ALERT→WATCH | 1 | DGS2 | OK | 0.01 | 2026-02-18 | 3.47 | -0.763 | -1.2032 | 35 | 10.714 | 0.8051 | 30 | 1.166 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.01 | 2026-02-18 | 49662.66 | 1.0898 | 1.6112 | 93.333 | 98.413 | 0.1183 | 1.6667 | 0.261 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DTWEXBGS | OK | 0.01 | 2026-02-13 | 117.5258 | -1.7013 | -1.683 | 10 | 2.381 | 0.0634 | 0 | -0.01 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.01 | 2026-02-13 | -0.4707 | 1.6199 | 1.5184 | 100 | 100 | 0.0077 | 0 | 0.811 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DCOILWTICO | OK | 0.01 | 2026-02-17 | 62.53 | 1.0955 | -0.3172 | 80 | 39.286 | -0.2232 | -6.6667 | -0.825 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.01 | 2026-02-18 | 4.09 | -1.0071 | -1.1211 | 20 | 14.286 | 0.5731 | 10 | 0.988 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.01 | 2026-02-18 | 22753.63 | -1.3659 | 0.7818 | 13.333 | 68.651 | 0.4238 | 3.3333 | 0.776 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=48.333333333333;prev_p60=33.333333333333;z60=0.098632440634;prev_z60=-0.283874106707;prev_v=6843.22;last_v=6881.31;zΔ60=0.382506547341;pΔ60=15;ret1%=0.556609315498 | NONE | SAME | 0 | SP500 | OK | 0.01 | 2026-02-18 | 6881.31 | 0.0986 | 1.091 | 48.333 | 86.905 | 0.3825 | 15 | 0.557 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=48.333333333333;prev_p60=36.666666666667;z60=-0.250970486178;prev_z60=-0.397538049189;prev_v=-0.6558;last_v=-0.6208;zΔ60=0.14656756301;pΔ60=11.666666666667;ret1%=5.336992985666 | NONE | SAME | 0 | STLFSI4 | OK | 0.01 | 2026-02-13 | -0.6208 | -0.251 | -0.3793 | 48.333 | 43.651 | 0.1466 | 11.6667 | 5.337 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.01 | 2026-02-19 | 0.61 | -0.8195 | 0.7065 | 25 | 79.762 | -0.2151 | -6.6667 | -1.613 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y3M | OK | 0.01 | 2026-02-19 | 0.39 | -0.6074 | 1.2205 | 21.667 | 81.349 | -0.0548 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=90;prev_p60=91.666666666667;z60=1.559474495704;prev_z60=1.877040457815;prev_v=20.29;last_v=19.62;zΔ60=-0.31756596211;pΔ60=-1.666666666667;ret1%=-3.302119270577 | NONE | SAME | 0 | VIXCLS | OK | 0.01 | 2026-02-18 | 19.62 | 1.5595 | 0.1058 | 90 | 69.841 | -0.3176 | -1.6667 | -3.302 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-20T08:38:40+08:00 |
