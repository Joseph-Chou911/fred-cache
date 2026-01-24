# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=2 / INFO=4 / NONE=6; CHANGED=0; WATCH_STREAK>=3=2; NEAR=5; JUMP_1of3=2
- RUN_TS_UTC: `2026-01-24T23:11:41.208799+00:00`
- day_key_local: `2026-01-25`
- STATS.generated_at_utc: `2026-01-24T18:56:24+00:00`
- STATS.as_of_ts: `2026-01-25T02:56:21+08:00`
- STATS.generated_at_utc(norm): `2026-01-24T18:56:24+00:00`
- STATS.data_commit_sha: `50a7cca2268b0aebe4b5b47a568464a6a4aba1a1`
- snapshot_id: `commit:50a7cca2268b0aebe4b5b47a568464a6a4aba1a1`
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
| ALERT | LONG_EXTREME | NEAR:ret1% | 0 | NA | p60=1.666666666667;prev_p60=3.333333333333;z60=-1.947339273154;prev_z60=-1.668564956258;prev_v=2.69;last_v=2.64;zΔ60=-0.278774316896;pΔ60=-1.666666666667;ret1%=-1.85873605948 | ALERT | SAME | 0 | BAMLH0A0HYM2 | OK | 4.25 | 2026-01-22 | 2.64 | -1.9473 | -1.1299 | 1.667 | 1.587 | -0.2788 | -1.6667 | -1.859 | P252<=2 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 3 | DGS10 | OK | 4.25 | 2026-01-22 | 4.26 | 2.0182 | -0.0722 | 98.333 | 51.19 | -0.0755 | 0 | 0 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=30;prev_p60=55;z60=-0.564433146607;prev_z60=-0.098444930935;prev_v=16.9;last_v=15.64;zΔ60=-0.465988215672;pΔ60=-25;ret1%=-7.455621301775 | WATCH | SAME | 3 | VIXCLS | OK | 4.25 | 2026-01-22 | 15.64 | -0.5644 | -0.6194 | 30 | 20.238 | -0.466 | -25 | -7.456 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 4.25 | 2026-01-23 | 49098.71 | 1.18 | 1.6842 | 85 | 96.429 | -0.3482 | -8.3333 | -0.578 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 4.25 | 2026-01-16 | -0.5057 | 1.2377 | 1.3336 | 90 | 97.619 | 0.0201 | 1.6667 | 0.851 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 4.25 | 2026-01-23 | 6915.61 | 0.8678 | 1.3308 | 81.667 | 95.635 | 0.0129 | 0 | 0.033 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 0 | NA | p60=86.666666666667;prev_p60=90;z60=1.001964960139;prev_z60=1.089838477283;prev_v=0.55;last_v=0.54;zΔ60=-0.087873517144;pΔ60=-3.333333333333;ret1%=-1.818181818182 | INFO | SAME | 0 | T10Y3M | OK | 4.25 | 2026-01-23 | 0.54 | 1.002 | 2.2768 | 86.667 | 96.825 | -0.0879 | -3.3333 | -1.818 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=73.333333333333;prev_p60=56.666666666667;z60=0.609351143621;prev_z60=0.029178106248;prev_v=59.39;last_v=60.3;zΔ60=0.580173037373;pΔ60=16.666666666667;ret1%=1.532244485604 | NONE | SAME | 0 | DCOILWTICO | OK | 4.25 | 2026-01-20 | 60.3 | 0.6094 | -0.9399 | 73.333 | 19.444 | 0.5802 | 16.6667 | 1.532 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 4.25 | 2026-01-22 | 3.61 | 1.4871 | -0.685 | 96.667 | 37.698 | 0.121 | 3.3333 | 0.278 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 4.25 | 2026-01-16 | 120.4478 | -1.0456 | -0.8437 | 21.667 | 14.683 | -0.19 | -5 | -0.114 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 4.25 | 2026-01-23 | 23501.24 | 0.4917 | 1.2437 | 63.333 | 90.873 | 0.1784 | 11.6667 | 0.278 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=35;prev_p60=31.666666666667;z60=-0.397953005876;prev_z60=-0.454103944422;prev_v=-0.6644;last_v=-0.651;zΔ60=0.056150938546;pΔ60=3.333333333333;ret1%=2.016857314871 | NONE | SAME | 0 | STLFSI4 | OK | 4.25 | 2026-01-16 | -0.651 | -0.398 | -0.4654 | 35 | 38.889 | 0.0562 | 3.3333 | 2.017 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 4.25 | 2026-01-23 | 0.64 | 0.4656 | 1.1441 | 60 | 88.889 | -0.166 | -6.6667 | -1.538 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-25T02:56:21+08:00 |
