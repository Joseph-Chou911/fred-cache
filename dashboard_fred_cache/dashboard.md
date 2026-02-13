# Risk Dashboard (fred_cache)

- Summary: ALERT=2 / WATCH=4 / INFO=2 / NONE=5; CHANGED=4; WATCH_STREAK>=3=0; NEAR=8; JUMP_1of3=2
- RUN_TS_UTC: `2026-02-13T04:03:40.983645+00:00`
- day_key_local: `2026-02-13`
- STATS.generated_at_utc: `2026-02-13T03:19:14+00:00`
- STATS.as_of_ts: `2026-02-13T11:19:12+08:00`
- STATS.generated_at_utc(norm): `2026-02-13T03:19:14+00:00`
- STATS.data_commit_sha: `7da24cb0258b78b63628058851f47a6945466d58`
- snapshot_id: `commit:7da24cb0258b78b63628058851f47a6945466d58`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=91.666666666667;z60=2.902879225783;prev_z60=1.405252182943;prev_v=61.6;last_v=64.53;zΔ60=1.49762704284;pΔ60=8.333333333333;ret1%=4.756493506494 | ALERT | SAME | 0 | DCOILWTICO | OK | 0.74 | 2026-02-09 | 64.53 | 2.9029 | -0.1167 | 100 | 53.571 | 1.4976 | 8.3333 | 4.756 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60 | 1 | Z | p60=3.333333333333;prev_p60=1.666666666667;z60=-3.11119123456;prev_z60=-3.881003518348;prev_v=117.8996;last_v=118.2407;zΔ60=0.769812283789;pΔ60=1.666666666667;ret1%=0.289313958656 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.74 | 2026-02-06 | 118.2407 | -3.1112 | -1.5482 | 3.333 | 0.794 | 0.7698 | 1.6667 | 0.289 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | p60=56.666666666667;prev_p60=10;z60=0.019429383514;prev_z60=-1.344662813192;prev_v=3.45;last_v=3.52;zΔ60=1.364092196706;pΔ60=46.666666666667;ret1%=2.028985507246 | INFO | INFO→WATCH | 1 | DGS2 | OK | 0.74 | 2026-02-11 | 3.52 | 0.0194 | -0.9859 | 56.667 | 20.238 | 1.3641 | 46.6667 | 2.029 | abs(zΔ60)>=0.75;abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=30;prev_p60=80;z60=-0.299299988433;prev_z60=0.804645786634;prev_v=6941.47;last_v=6832.76;zΔ60=-1.103945775067;pΔ60=-50;ret1%=-1.56609478972 | INFO | INFO→WATCH | 1 | SP500 | OK | 0.74 | 2026-02-12 | 6832.76 | -0.2993 | 1.018 | 30 | 80.556 | -1.1039 | -50 | -1.566 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=33.333333333333;prev_p60=51.666666666667;z60=-0.484031743159;prev_z60=0.189279784855;prev_v=0.66;last_v=0.62;zΔ60=-0.673311528014;pΔ60=-18.333333333333;ret1%=-6.060606060606 | WATCH | SAME | 2 | T10Y2Y | OK | 0.74 | 2026-02-12 | 0.62 | -0.484 | 0.8101 | 33.333 | 82.143 | -0.6733 | -18.3333 | -6.061 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=21.666666666667;prev_p60=40;z60=-0.435054932166;prev_z60=0.201030126622;prev_v=0.48;last_v=0.39;zΔ60=-0.636085058788;pΔ60=-18.333333333333;ret1%=-18.75 | NONE | NONE→WATCH | 1 | T10Y3M | OK | 0.74 | 2026-02-12 | 0.39 | -0.4351 | 1.245 | 21.667 | 81.349 | -0.6361 | -18.3333 | -18.75 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.74 | 2026-02-12 | 49451.98 | 0.9374 | 1.5829 | 86.667 | 96.825 | -0.665 | -10 | -1.336 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.74 | 2026-02-06 | -0.4746 | 1.4829 | 1.4666 | 100 | 100 | 0.0073 | 0 | 0.682 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.74 | 2026-02-11 | 2.84 | -0.23 | -0.625 | 43.333 | 27.778 | -0.1191 | -6.6667 | -0.699 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=66.666666666667;prev_p60=48.333333333333;z60=0.190689098674;prev_z60=-0.085109292318;prev_v=4.16;last_v=4.18;zΔ60=0.275798390992;pΔ60=18.333333333333;ret1%=0.480769230769 | WATCH | WATCH→NONE | 0 | DGS10 | OK | 0.74 | 2026-02-11 | 4.18 | 0.1907 | -0.5187 | 66.667 | 37.302 | 0.2758 | 18.3333 | 0.481 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.74 | 2026-02-11 | 23066.47 | -0.5608 | 0.94 | 26.667 | 77.778 | -0.1056 | -1.6667 | -0.156 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=36.666666666667;prev_p60=33.333333333333;z60=-0.393935395483;prev_z60=-0.488886491383;prev_v=-0.6784;last_v=-0.6558;zΔ60=0.0949510959;pΔ60=3.333333333333;ret1%=3.331367924528 | NONE | SAME | 0 | STLFSI4 | OK | 0.74 | 2026-02-06 | -0.6558 | -0.3939 | -0.4817 | 36.667 | 38.095 | 0.095 | 3.3333 | 3.331 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | VIXCLS | OK | 0.74 | 2026-02-11 | 17.65 | 0.2308 | -0.2579 | 76.667 | 56.349 | -0.0362 | -1.6667 | -0.787 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-13T11:19:12+08:00 |
