# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=2 / INFO=3 / NONE=7; CHANGED=5; WATCH_STREAK>=3=1; NEAR=4; JUMP_1of3=2
- RUN_TS_UTC: `2026-02-18T14:11:19.768625+00:00`
- day_key_local: `2026-02-18`
- STATS.generated_at_utc: `2026-02-18T13:39:16+00:00`
- STATS.as_of_ts: `2026-02-18T21:39:12+08:00`
- STATS.generated_at_utc(norm): `2026-02-18T13:39:16+00:00`
- STATS.data_commit_sha: `f768b8b0eb372b6a5255079f48d7c1ca860c8397`
- snapshot_id: `commit:f768b8b0eb372b6a5255079f48d7c1ca860c8397`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | p60=1.666666666667;prev_p60=30;z60=-2.214430020546;prev_z60=-0.927637532607;prev_v=3.47;last_v=3.4;zΔ60=-1.286792487939;pΔ60=-28.333333333333;ret1%=-2.017291066282 | WATCH | WATCH→ALERT | 0 | DGS2 | OK | 0.53 | 2026-02-13 | 3.4 | -2.2144 | -1.5319 | 1.667 | 0.397 | -1.2868 | -28.3333 | -2.017 | P252<=2;abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | ALERT | ALERT→WATCH | 1 | DCOILWTICO | OK | 0.53 | 2026-02-09 | 64.53 | 2.2291 | 0.115 | 96.667 | 60.317 | 0.234 | 1.6667 | 1.192 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| WATCH | EXTREME_Z | NEAR:ret1% | 1 | R | p60=96.666666666667;prev_p60=93.333333333333;z60=2.169114090454;prev_z60=1.618928811464;prev_v=20.6;last_v=21.2;zΔ60=0.550185278989;pΔ60=3.333333333333;ret1%=2.912621359223 | WATCH | SAME | 5 | VIXCLS | OK | 0.53 | 2026-02-16 | 21.2 | 2.1691 | 0.4057 | 96.667 | 79.365 | 0.5502 | 3.3333 | 2.913 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.53 | 2026-02-17 | 49533.19 | 0.9715 | 1.5817 | 91.667 | 98.016 | 0.0148 | 3.3333 | 0.065 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | ALERT | ALERT→INFO | 0 | DTWEXBGS | OK | 0.53 | 2026-02-13 | 117.5258 | -1.7013 | -1.683 | 10 | 2.381 | 0.0634 | 0 | -0.01 | P252<=5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.53 | 2026-02-06 | -0.4746 | 1.6122 | 1.4963 | 100 | 100 | 0.0102 | 0 | 0.848 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | BAMLH0A0HYM2 | OK | 0.53 | 2026-02-16 | 2.94 | 0.9794 | -0.3528 | 85 | 48.413 | 0.0019 | -3.3333 | -0.339 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DGS10 | OK | 0.53 | 2026-02-13 | 4.04 | -1.7675 | -1.4848 | 8.333 | 7.54 | -0.6604 | -6.6667 | -1.222 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.53 | 2026-02-17 | 22578.38 | -1.7897 | 0.7106 | 10 | 64.683 | 0.0526 | 1.6667 | 0.141 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | SP500 | OK | 0.53 | 2026-02-17 | 6843.22 | -0.2839 | 1.0236 | 33.333 | 81.746 | 0.0179 | 1.6667 | 0.103 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=36.666666666667;prev_p60=33.333333333333;z60=-0.397538049189;prev_z60=-0.491301815101;prev_v=-0.6781;last_v=-0.6558;zΔ60=0.093763765912;pΔ60=3.333333333333;ret1%=3.288600501401 | NONE | SAME | 0 | STLFSI4 | OK | 0.53 | 2026-02-06 | -0.6558 | -0.3975 | -0.4826 | 36.667 | 38.095 | 0.0938 | 3.3333 | 3.289 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=31.666666666667;prev_p60=38.333333333333;z60=-0.569518793427;prev_z60=-0.193940388196;prev_v=0.64;last_v=0.62;zΔ60=-0.375578405231;pΔ60=-6.666666666667;ret1%=-3.125 | NONE | SAME | 0 | T10Y2Y | OK | 0.53 | 2026-02-17 | 0.62 | -0.5695 | 0.7992 | 31.667 | 81.746 | -0.3756 | -6.6667 | -3.125 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y3M | OK | 0.53 | 2026-02-17 | 0.36 | -0.7276 | 1.0944 | 20 | 80.952 | -0.0422 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-18T21:39:12+08:00 |
