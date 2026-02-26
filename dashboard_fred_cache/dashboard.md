# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=3 / INFO=3 / NONE=7; CHANGED=4; WATCH_STREAK>=3=1; NEAR=6; JUMP_1of3=3
- RUN_TS_UTC: `2026-02-26T01:55:07.971435+00:00`
- day_key_local: `2026-02-26`
- STATS.generated_at_utc: `2026-02-26T01:54:27+00:00`
- STATS.as_of_ts: `2026-02-26T09:54:26+08:00`
- STATS.generated_at_utc(norm): `2026-02-26T01:54:27+00:00`
- STATS.data_commit_sha: `7dc2fd579ec0ada7ccca2c79f170147e941bc67a`
- snapshot_id: `commit:7dc2fd579ec0ada7ccca2c79f170147e941bc67a`
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
| WATCH | EXTREME_Z | NA | 0 | NA | NA | NONE | NONE→WATCH | 1 | DCOILWTICO | OK | 0.01 | 2026-02-23 | 66.36 | 2.0613 | 0.6316 | 96.667 | 73.413 | -0.2337 | -3.3333 | -0.495 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| WATCH | LONG_EXTREME | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=85;prev_p60=50;z60=0.969903923468;prev_z60=0.041426020141;prev_v=6890.07;last_v=6946.13;zΔ60=0.928477903328;pΔ60=35;ret1%=0.813634694568 | WATCH | SAME | 3 | SP500 | OK | 0.01 | 2026-02-25 | 6946.13 | 0.9699 | 1.1769 | 85 | 96.429 | 0.9285 | 35 | 0.814 | P252>=95;abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=85;prev_p60=96.666666666667;z60=1.314573891065;prev_z60=2.074671657348;prev_v=21.01;last_v=19.55;zΔ60=-0.760097766283;pΔ60=-11.666666666667;ret1%=-6.949071870538 | WATCH | SAME | 2 | VIXCLS | OK | 0.01 | 2026-02-24 | 19.55 | 1.3146 | 0.0982 | 85 | 70.238 | -0.7601 | -11.6667 | -6.949 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | ALERT | ALERT→INFO | 0 | DGS2 | OK | 0.01 | 2026-02-24 | 3.43 | -1.4834 | -1.3976 | 6.667 | 2.381 | 0 | 0 | 0 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| INFO | LONG_EXTREME | NEAR:PΔ60 | 1 | P | p60=81.666666666667;prev_p60=63.333333333333;z60=0.87311019704;prev_z60=0.479895576183;prev_v=49174.5;last_v=49482.150000000001;zΔ60=0.393214620857;pΔ60=18.333333333333;ret1%=0.625629137053 | NONE | NONE→INFO | 0 | DJIA | OK | 0.01 | 2026-02-25 | 49482.15 | 0.8731 | 1.4837 | 81.667 | 95.635 | 0.3932 | 18.3333 | 0.626 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.01 | 2026-02-20 | -0.4668 | 1.6277 | 1.5414 | 100 | 100 | 0.0078 | 0 | 0.835 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | BAMLH0A0HYM2 | OK | 0.01 | 2026-02-24 | 2.97 | 1.5018 | -0.2653 | 96.667 | 55.556 | 0.2083 | 1.6667 | 0.678 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.01 | 2026-02-24 | 4.04 | -1.721 | -1.452 | 8.333 | 8.333 | 0.1083 | 1.6667 | 0.248 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.01 | 2026-02-20 | 117.9917 | -1.1789 | -1.4815 | 21.667 | 5.159 | -0.1682 | -1.6667 | -0.206 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | NA | NEAR:ZΔ60 | 0 | NA | p60=15;prev_p60=8.333333333333;z60=-1.230432974746;prev_z60=-1.931210581783;prev_v=22627.27;last_v=22863.68;zΔ60=0.700777607037;pΔ60=6.666666666667;ret1%=1.04480125088 | NONE | SAME | 0 | NASDAQCOM | OK | 0.01 | 2026-02-24 | 22863.68 | -1.2304 | 0.8076 | 15 | 70.238 | 0.7008 | 6.6667 | 1.045 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=50;prev_p60=48.333333333333;z60=-0.162988734641;prev_z60=-0.250970486178;prev_v=-0.6208;last_v=-0.5981;zΔ60=0.087981751537;pΔ60=1.666666666667;ret1%=3.656572164948 | NONE | SAME | 0 | STLFSI4 | OK | 0.01 | 2026-02-20 | -0.5981 | -0.163 | -0.3125 | 50 | 48.016 | 0.088 | 1.6667 | 3.657 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.01 | 2026-02-25 | 0.6 | -1.1194 | 0.6013 | 20 | 78.175 | -0.2336 | -5 | -1.639 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=15;prev_p60=11.666666666667;z60=-1.332738032227;prev_z60=-1.226369661976;prev_v=0.35;last_v=0.36;zΔ60=-0.106368370251;pΔ60=3.333333333333;ret1%=2.857142857143 | NONE | SAME | 0 | T10Y3M | OK | 0.01 | 2026-02-25 | 0.36 | -1.3327 | 1.0604 | 15 | 79.762 | -0.1064 | 3.3333 | 2.857 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-26T09:54:26+08:00 |
