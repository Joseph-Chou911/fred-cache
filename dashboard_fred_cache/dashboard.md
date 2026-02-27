# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=2 / INFO=2 / NONE=9; CHANGED=3; WATCH_STREAK>=3=1; NEAR=5; JUMP_1of3=4
- RUN_TS_UTC: `2026-02-27T14:03:56.700786+00:00`
- day_key_local: `2026-02-27`
- STATS.generated_at_utc: `2026-02-27T13:21:36+00:00`
- STATS.as_of_ts: `2026-02-27T21:21:34+08:00`
- STATS.generated_at_utc(norm): `2026-02-27T13:21:36+00:00`
- STATS.data_commit_sha: `38a0ec7343854cabd660f50e68cf09d76d6b855e`
- snapshot_id: `commit:38a0ec7343854cabd660f50e68cf09d76d6b855e`
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
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 2 | DCOILWTICO | OK | 0.71 | 2026-02-23 | 66.36 | 2.0613 | 0.6316 | 96.667 | 73.413 | -0.2337 | -3.3333 | -0.495 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=76.666666666667;prev_p60=85;z60=0.526264572196;prev_z60=1.314573891065;prev_v=19.55;last_v=17.93;zΔ60=-0.788309318869;pΔ60=-8.333333333333;ret1%=-8.286445012788 | WATCH | SAME | 3 | VIXCLS | OK | 0.71 | 2026-02-25 | 17.93 | 0.5263 | -0.2061 | 76.667 | 59.127 | -0.7883 | -8.3333 | -8.286 | abs(zΔ60)>=0.75;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.71 | 2026-02-26 | 49499.2 | 0.8687 | 1.4759 | 81.667 | 95.635 | -0.0044 | 0 | 0.034 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.71 | 2026-02-20 | -0.4668 | 1.6277 | 1.5414 | 100 | 100 | 0.0078 | 0 | 0.835 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.71 | 2026-02-25 | 2.94 | 1.1581 | -0.3443 | 88.333 | 49.603 | -0.3436 | -8.3333 | -1.01 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.71 | 2026-02-25 | 4.05 | -1.6301 | -1.3709 | 10 | 10.714 | 0.0909 | 1.6667 | 0.248 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | NA | NA | 0 | NA | NA | INFO | INFO→NONE | 0 | DGS2 | OK | 0.71 | 2026-02-25 | 3.45 | -1.0956 | -1.2978 | 15 | 5.556 | 0.3878 | 8.3333 | 0.583 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.71 | 2026-02-20 | 117.9917 | -1.1789 | -1.4815 | 21.667 | 5.159 | -0.1682 | -1.6667 | -0.206 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 1 | P | p60=16.666666666667;prev_p60=31.666666666667;z60=-1.148297712135;prev_z60=-0.399961942077;prev_v=23152.080000000002;last_v=22878.380000000001;zΔ60=-0.748335770058;pΔ60=-15;ret1%=-1.182183199091 | WATCH | WATCH→NONE | 0 | NASDAQCOM | OK | 0.71 | 2026-02-26 | 22878.38 | -1.1483 | 0.8004 | 16.667 | 70.635 | -0.7483 | -15 | -1.182 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=55;prev_p60=85;z60=0.311168312622;prev_z60=0.969903923468;prev_v=6946.13;last_v=6908.86;zΔ60=-0.658735610846;pΔ60=-30;ret1%=-0.536557766699 | WATCH | WATCH→NONE | 0 | SP500 | OK | 0.71 | 2026-02-26 | 6908.86 | 0.3112 | 1.095 | 55 | 89.286 | -0.6587 | -30 | -0.537 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=50;prev_p60=48.333333333333;z60=-0.162988734641;prev_z60=-0.250970486178;prev_v=-0.6208;last_v=-0.5981;zΔ60=0.087981751537;pΔ60=1.666666666667;ret1%=3.656572164948 | NONE | SAME | 0 | STLFSI4 | OK | 0.71 | 2026-02-20 | -0.5981 | -0.163 | -0.3125 | 50 | 48.016 | 0.088 | 1.6667 | 3.657 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.71 | 2026-02-26 | 0.6 | -1.1665 | 0.5964 | 20 | 78.175 | -0.0472 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=8.333333333333;prev_p60=15;z60=-1.763365086643;prev_z60=-1.332738032227;prev_v=0.36;last_v=0.34;zΔ60=-0.430627054416;pΔ60=-6.666666666667;ret1%=-5.555555555556 | NONE | SAME | 0 | T10Y3M | OK | 0.71 | 2026-02-26 | 0.34 | -1.7634 | 0.9635 | 8.333 | 78.175 | -0.4306 | -6.6667 | -5.556 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-27T21:21:34+08:00 |
