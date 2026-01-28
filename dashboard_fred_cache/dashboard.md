# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=1 / INFO=5 / NONE=6; CHANGED=0; WATCH_STREAK>=3=0; NEAR=6; JUMP_1of3=4
- RUN_TS_UTC: `2026-01-28T23:51:48.373908+00:00`
- day_key_local: `2026-01-29`
- STATS.generated_at_utc: `2026-01-28T19:43:27+00:00`
- STATS.as_of_ts: `2026-01-29T03:43:17+08:00`
- STATS.generated_at_utc(norm): `2026-01-28T19:43:27+00:00`
- STATS.data_commit_sha: `2a30aeb80be93437c5f3c3e0bd99468165b098ab`
- snapshot_id: `commit:2a30aeb80be93437c5f3c3e0bd99468165b098ab`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=1.666666666667;prev_p60=21.666666666667;z60=-2.595576368124;prev_z60=-1.045572439498;prev_v=120.4478;last_v=119.2855;zΔ60=-1.550003928626;pΔ60=-20;ret1%=-0.964982340898 | ALERT | SAME | 0 | DTWEXBGS | OK | 4.14 | 2026-01-23 | 119.2855 | -2.5956 | -1.2219 | 1.667 | 0.397 | -1.55 | -20 | -0.965 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| WATCH | LONG_EXTREME | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=96.666666666667;prev_p60=70;z60=1.412702560332;prev_z60=0.729878589132;prev_v=0.66;last_v=0.71;zΔ60=0.6828239712;pΔ60=26.666666666667;ret1%=7.575757575758 | WATCH | SAME | 2 | T10Y2Y | OK | 4.14 | 2026-01-27 | 0.71 | 1.4127 | 1.6875 | 96.667 | 99.206 | 0.6828 | 26.6667 | 7.576 | P252>=95;abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 4.14 | 2026-01-27 | 49003.41 | 0.9983 | 1.615 | 80 | 95.238 | -0.4609 | -13.3333 | -0.828 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NASDAQCOM | OK | 4.14 | 2026-01-27 | 23817.1 | 1.3642 | 1.3633 | 98.333 | 98.81 | 0.5917 | 11.6667 | 0.914 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=90;z60=1.449255202935;prev_z60=1.23769212487;prev_v=-0.50568;last_v=-0.48295;zΔ60=0.211563078064;pΔ60=8.333333333333;ret1%=4.494937509888 | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 4.14 | 2026-01-23 | -0.4829 | 1.4493 | 1.423 | 98.333 | 99.603 | 0.2116 | 8.3333 | 4.495 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 4.14 | 2026-01-27 | 6978.6 | 1.4754 | 1.4364 | 100 | 100 | 0.2606 | 5 | 0.408 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=90;z60=1.108479600709;prev_z60=1.026316958455;prev_v=0.55;last_v=0.57;zΔ60=0.082162642254;pΔ60=8.333333333333;ret1%=3.636363636364 | INFO | SAME | 0 | T10Y3M | OK | 4.14 | 2026-01-27 | 0.57 | 1.1085 | 2.3703 | 98.333 | 99.603 | 0.0822 | 8.3333 | 3.636 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 4.14 | 2026-01-27 | 2.71 | -1.3444 | -0.9421 | 11.667 | 8.333 | 0.1809 | 3.3333 | 0.743 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DCOILWTICO | OK | 4.14 | 2026-01-26 | 60.46 | 0.7433 | -0.9029 | 76.667 | 20.635 | 0.1339 | 3.3333 | 0.265 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 4.14 | 2026-01-26 | 4.22 | 1.3023 | -0.312 | 91.667 | 42.46 | -0.3474 | -3.3333 | -0.472 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 1 | P | p60=66.666666666667;prev_p60=91.666666666667;z60=0.535093285021;prev_z60=1.263410616204;prev_v=3.6;last_v=3.56;zΔ60=-0.728317331183;pΔ60=-25;ret1%=-1.111111111111 | NONE | SAME | 0 | DGS2 | OK | 4.14 | 2026-01-26 | 3.56 | 0.5351 | -0.8839 | 66.667 | 25 | -0.7283 | -25 | -1.111 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=35;prev_p60=31.666666666667;z60=-0.397953005876;prev_z60=-0.454103944422;prev_v=-0.6644;last_v=-0.651;zΔ60=0.056150938546;pΔ60=3.333333333333;ret1%=2.016857314871 | NONE | SAME | 0 | STLFSI4 | OK | 4.14 | 2026-01-16 | -0.651 | -0.398 | -0.4654 | 35 | 38.889 | 0.0562 | 3.3333 | 2.017 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | VIXCLS | OK | 4.14 | 2026-01-27 | 16.35 | -0.2903 | -0.4839 | 46.667 | 33.333 | 0.0776 | 3.3333 | 1.238 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-29T03:43:17+08:00 |
