# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=2 / INFO=4 / NONE=6; CHANGED=5; WATCH_STREAK>=3=2; NEAR=7; JUMP_1of3=3
- RUN_TS_UTC: `2026-02-10T14:24:07.526698+00:00`
- day_key_local: `2026-02-10`
- STATS.generated_at_utc: `2026-02-10T13:50:21+00:00`
- STATS.as_of_ts: `2026-02-10T21:50:19+08:00`
- STATS.generated_at_utc(norm): `2026-02-10T13:50:21+00:00`
- STATS.data_commit_sha: `6bae5069437139e3fbfa22dfbfbb862ba338e3c1`
- snapshot_id: `commit:6bae5069437139e3fbfa22dfbfbb862ba338e3c1`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=3.333333333333;prev_p60=1.666666666667;z60=-3.11119123456;prev_z60=-3.881003518348;prev_v=117.8996;last_v=118.2407;zΔ60=0.769812283789;pΔ60=1.666666666667;ret1%=0.289313958656 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.56 | 2026-02-06 | 118.2407 | -3.1112 | -1.5482 | 3.333 | 0.794 | 0.7698 | 1.6667 | 0.289 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=50;prev_p60=76.666666666667;z60=-0.090446456733;prev_z60=0.601091154118;prev_v=2.97;last_v=2.87;zΔ60=-0.691537610851;pΔ60=-26.666666666667;ret1%=-3.367003367003 | WATCH | SAME | 4 | BAMLH0A0HYM2 | OK | 0.56 | 2026-02-06 | 2.87 | -0.0904 | -0.5362 | 50 | 32.937 | -0.6915 | -26.6667 | -3.367 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | p60=76.666666666667;prev_p60=91.666666666667;z60=0.239328472884;prev_z60=1.705233500084;prev_v=21.77;last_v=17.76;zΔ60=-1.465905027201;pΔ60=-15;ret1%=-18.419843821773 | WATCH | SAME | 4 | VIXCLS | OK | 0.56 | 2026-02-06 | 17.76 | 0.2393 | -0.231 | 76.667 | 57.54 | -1.4659 | -15 | -18.42 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | WATCH | WATCH→INFO | 0 | DJIA | OK | 0.56 | 2026-02-09 | 50135.87 | 1.7602 | 1.8799 | 100 | 100 | -0.0626 | 0 | 0.04 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.56 | 2026-01-30 | -0.4778 | 1.4756 | 1.4479 | 100 | 100 | 0.0264 | 1.6667 | 1.056 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | WATCH | WATCH→INFO | 0 | SP500 | OK | 0.56 | 2026-02-09 | 6964.82 | 1.0857 | 1.31 | 90 | 97.619 | 0.2965 | 10 | 0.469 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=100;prev_p60=95;z60=1.462451661522;prev_z60=1.21292863273;prev_v=0.72;last_v=0.74;zΔ60=0.249523028792;pΔ60=5;ret1%=2.777777777778 | INFO | SAME | 0 | T10Y2Y | OK | 0.56 | 2026-02-09 | 0.74 | 1.4625 | 1.7842 | 100 | 100 | 0.2495 | 5 | 2.778 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 1 | P | p60=91.666666666667;prev_p60=76.666666666667;z60=1.405252182943;prev_z60=0.743254468694;prev_v=60.46;last_v=61.6;zΔ60=0.661997714249;pΔ60=15;ret1%=1.885544161429 | NONE | SAME | 0 | DCOILWTICO | OK | 0.56 | 2026-02-02 | 61.6 | 1.4053 | -0.681 | 91.667 | 26.984 | 0.662 | 15 | 1.886 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS10 | OK | 0.56 | 2026-02-06 | 4.22 | 0.8241 | -0.2582 | 80 | 43.254 | 0.1173 | 1.6667 | 0.238 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS2 | OK | 0.56 | 2026-02-06 | 3.5 | -0.4543 | -1.0969 | 38.333 | 13.889 | 0.5957 | 11.6667 | 0.865 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | NASDAQCOM | OK | 0.56 | 2026-02-09 | 23238.67 | -0.1154 | 1.0298 | 36.667 | 80.952 | 0.5469 | 11.6667 | 0.901 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=33.333333333333;prev_p60=28.333333333333;z60=-0.488886491383;prev_z60=-0.634085378622;prev_v=-0.7123;last_v=-0.6784;zΔ60=0.145198887239;pΔ60=5;ret1%=4.759230661238 | NONE | SAME | 0 | STLFSI4 | OK | 0.56 | 2026-01-30 | -0.6784 | -0.4889 | -0.5471 | 33.333 | 35.317 | 0.1452 | 5 | 4.759 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
| NONE | NA | NEAR:ret1% | 0 | NA | p60=65;prev_p60=73.333333333333;z60=0.572816951449;prev_z60=0.660112451827;prev_v=0.54;last_v=0.53;zΔ60=-0.087295500377;pΔ60=-8.333333333333;ret1%=-1.851851851852 | NONE | SAME | 0 | T10Y3M | OK | 0.56 | 2026-02-09 | 0.53 | 0.5728 | 1.9376 | 65 | 91.667 | -0.0873 | -8.3333 | -1.852 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-10T21:50:19+08:00 |
