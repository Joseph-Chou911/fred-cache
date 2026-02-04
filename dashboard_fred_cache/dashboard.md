# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=2 / INFO=4 / NONE=6; CHANGED=3; WATCH_STREAK>=3=0; NEAR=6; JUMP_1of3=3
- RUN_TS_UTC: `2026-02-04T22:59:04.265802+00:00`
- day_key_local: `2026-02-05`
- STATS.generated_at_utc: `2026-02-04T22:58:16+00:00`
- STATS.as_of_ts: `2026-02-05T06:58:14+08:00`
- STATS.generated_at_utc(norm): `2026-02-04T22:58:16+00:00`
- STATS.data_commit_sha: `258df52e0b758e885e8f6df1ed0dc81c5241b815`
- snapshot_id: `commit:258df52e0b758e885e8f6df1ed0dc81c5241b815`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=1.666666666667;prev_p60=1.666666666667;z60=-3.881003518348;prev_z60=-2.595576368124;prev_v=119.2855;last_v=117.8996;zΔ60=-1.285427150224;pΔ60=0;ret1%=-1.161834422457 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.01 | 2026-01-30 | 117.8996 | -3.881 | -1.6711 | 1.667 | 0.397 | -1.2854 | 0 | -1.162 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=36.666666666667;prev_p60=81.666666666667;z60=-0.134793274496;prev_z60=0.755841199494;prev_v=23592.110000000001;last_v=23255.189999999999;zΔ60=-0.89063447399;pΔ60=-45;ret1%=-1.428104565467 | WATCH | SAME | 2 | NASDAQCOM | OK | 0.01 | 2026-02-03 | 23255.19 | -0.1348 | 1.0645 | 36.667 | 81.746 | -0.8906 | -45 | -1.428 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=80;prev_p60=45;z60=0.360792527495;prev_z60=-0.2666364388;prev_v=16.34;last_v=18;zΔ60=0.627428966295;pΔ60=35;ret1%=10.15911872705 | WATCH | SAME | 2 | VIXCLS | OK | 0.01 | 2026-02-03 | 18 | 0.3608 | -0.1771 | 80 | 60.317 | 0.6274 | 35 | 10.159 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.01 | 2026-02-03 | 49240.99 | 1.0717 | 1.6284 | 85 | 96.429 | -0.2077 | -6.6667 | -0.337 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.01 | 2026-01-30 | -0.4778 | 1.4756 | 1.4479 | 100 | 100 | 0.0264 | 1.6667 | 1.056 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y2Y | OK | 0.01 | 2026-02-04 | 0.72 | 1.3096 | 1.6708 | 96.667 | 99.206 | 0.1076 | 3.3333 | 1.408 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y3M | OK | 0.01 | 2026-02-04 | 0.6 | 1.0725 | 2.3347 | 100 | 100 | 0.0242 | 3.3333 | 1.695 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | BAMLH0A0HYM2 | OK | 0.01 | 2026-02-03 | 2.85 | -0.2708 | -0.5774 | 43.333 | 30.556 | 0.3002 | 10 | 1.423 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 1 | P | p60=91.666666666667;prev_p60=76.666666666667;z60=1.405252182943;prev_z60=0.743254468694;prev_v=60.46;last_v=61.6;zΔ60=0.661997714249;pΔ60=15;ret1%=1.885544161429 | NONE | SAME | 0 | DCOILWTICO | OK | 0.01 | 2026-02-02 | 61.6 | 1.4053 | -0.681 | 91.667 | 26.984 | 0.662 | 15 | 1.886 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS10 | OK | 0.01 | 2026-02-03 | 4.28 | 1.8284 | 0.1297 | 96.667 | 57.143 | -0.2416 | -1.6667 | -0.233 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS2 | OK | 0.01 | 2026-02-03 | 3.57 | 0.8115 | -0.804 | 78.333 | 29.762 | 0.0054 | 1.6667 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=71.666666666667;prev_p60=95;z60=0.686457792058;prev_z60=1.288275805175;prev_v=6976.44;last_v=6917.81;zΔ60=-0.601818013117;pΔ60=-23.333333333333;ret1%=-0.840399974772 | NONE | SAME | 0 | SP500 | OK | 0.01 | 2026-02-03 | 6917.81 | 0.6865 | 1.2541 | 71.667 | 93.254 | -0.6018 | -23.3333 | -0.84 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=33.333333333333;prev_p60=28.333333333333;z60=-0.488886491383;prev_z60=-0.634085378622;prev_v=-0.7123;last_v=-0.6784;zΔ60=0.145198887239;pΔ60=5;ret1%=4.759230661238 | NONE | SAME | 0 | STLFSI4 | OK | 0.01 | 2026-01-30 | -0.6784 | -0.4889 | -0.5471 | 33.333 | 35.317 | 0.1452 | 5 | 4.759 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-05T06:58:14+08:00 |
