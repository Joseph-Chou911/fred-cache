# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=0 / INFO=4 / NONE=8; CHANGED=0; WATCH_STREAK>=3=0; NEAR=9; JUMP_1of3=7
- RUN_TS_UTC: `2026-02-01T14:03:34.145434+00:00`
- day_key_local: `2026-02-01`
- STATS.generated_at_utc: `2026-02-01T13:11:17+00:00`
- STATS.as_of_ts: `2026-02-01T21:11:14+08:00`
- STATS.generated_at_utc(norm): `2026-02-01T13:11:17+00:00`
- STATS.data_commit_sha: `2150838d90e7c019df5654c718bc9c97ef1040a5`
- snapshot_id: `commit:2150838d90e7c019df5654c718bc9c97ef1040a5`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=1.666666666667;prev_p60=21.666666666667;z60=-2.595576368124;prev_z60=-1.045572439498;prev_v=120.4478;last_v=119.2855;zΔ60=-1.550003928626;pΔ60=-20;ret1%=-0.964982340898 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.87 | 2026-01-23 | 119.2855 | -2.5956 | -1.2219 | 1.667 | 0.397 | -1.55 | -20 | -0.965 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=90;z60=1.449255202935;prev_z60=1.23769212487;prev_v=-0.50568;last_v=-0.48295;zΔ60=0.211563078064;pΔ60=8.333333333333;ret1%=4.494937509888 | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.87 | 2026-01-23 | -0.4829 | 1.4493 | 1.423 | 98.333 | 99.603 | 0.2116 | 8.3333 | 4.495 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 0.87 | 2026-01-30 | 6939.03 | 0.9612 | 1.3193 | 83.333 | 96.032 | -0.3243 | -11.6667 | -0.43 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=100;prev_p60=96.666666666667;z60=1.732983879647;prev_z60=1.344680676255;prev_v=0.71;last_v=0.74;zΔ60=0.388303203393;pΔ60=3.333333333333;ret1%=4.225352112676 | INFO | SAME | 0 | T10Y2Y | OK | 0.87 | 2026-01-30 | 0.74 | 1.733 | 1.8775 | 100 | 100 | 0.3883 | 3.3333 | 4.225 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=96.666666666667;z60=1.1160115931;prev_z60=1.036752077678;prev_v=0.57;last_v=0.59;zΔ60=0.079259515422;pΔ60=1.666666666667;ret1%=3.508771929825 | INFO | SAME | 0 | T10Y3M | OK | 0.87 | 2026-01-30 | 0.59 | 1.116 | 2.3806 | 98.333 | 99.603 | 0.0793 | 1.6667 | 3.509 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | NA | NEAR:ret1% | 0 | NA | p60=25;prev_p60=13.333333333333;z60=-0.876522765712;prev_z60=-1.23415376583;prev_v=2.72;last_v=2.77;zΔ60=0.357631000118;pΔ60=11.666666666667;ret1%=1.838235294118 | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.87 | 2026-01-29 | 2.77 | -0.8765 | -0.7837 | 25 | 13.889 | 0.3576 | 11.6667 | 1.838 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DCOILWTICO | OK | 0.87 | 2026-01-26 | 60.46 | 0.7433 | -0.9029 | 76.667 | 20.635 | 0.1339 | 3.3333 | 0.265 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.87 | 2026-01-29 | 4.24 | 1.469 | -0.1597 | 93.333 | 48.016 | -0.3876 | -5 | -0.469 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=51.666666666667;prev_p60=68.333333333333;z60=0.018362796955;prev_z60=0.535145366502;prev_v=3.56;last_v=3.53;zΔ60=-0.516782569547;pΔ60=-16.666666666667;ret1%=-0.842696629213 | NONE | SAME | 0 | DGS2 | OK | 0.87 | 2026-01-29 | 3.53 | 0.0184 | -0.997 | 51.667 | 19.444 | -0.5168 | -16.6667 | -0.843 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DJIA | OK | 0.87 | 2026-01-30 | 48892.47 | 0.7936 | 1.5313 | 71.667 | 93.254 | -0.2115 | -8.3333 | -0.365 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=55;prev_p60=91.666666666667;z60=0.420160304586;prev_z60=0.988666558;prev_v=23685.119999999999;last_v=23461.82;zΔ60=-0.568506253414;pΔ60=-36.666666666667;ret1%=-0.942786019239 | NONE | SAME | 0 | NASDAQCOM | OK | 0.87 | 2026-01-30 | 23461.82 | 0.4202 | 1.1736 | 55 | 86.905 | -0.5685 | -36.6667 | -0.943 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=28.333333333333;prev_p60=35;z60=-0.634085378622;prev_z60=-0.397953005876;prev_v=-0.651;last_v=-0.7123;zΔ60=-0.236132372747;pΔ60=-6.666666666667;ret1%=-9.416282642089 | NONE | SAME | 0 | STLFSI4 | OK | 0.87 | 2026-01-23 | -0.7123 | -0.6341 | -0.6485 | 28.333 | 28.968 | -0.2361 | -6.6667 | -9.416 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=60;prev_p60=48.333333333333;z60=-0.085841870953;prev_z60=-0.283467383819;prev_v=16.35;last_v=16.88;zΔ60=0.197625512865;pΔ60=11.666666666667;ret1%=3.241590214067 | NONE | SAME | 0 | VIXCLS | OK | 0.87 | 2026-01-29 | 16.88 | -0.0858 | -0.3845 | 60 | 46.825 | 0.1976 | 11.6667 | 3.242 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-01T21:11:14+08:00 |
