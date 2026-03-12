# Risk Dashboard (fred_cache)

- Summary: ALERT=2 / WATCH=4 / INFO=1 / NONE=6; CHANGED=5; WATCH_STREAK>=3=0; NEAR=7; JUMP_1of3=2
- RUN_TS_UTC: `2026-03-12T23:00:20.444738+00:00`
- day_key_local: `2026-03-13`
- STATS.generated_at_utc: `2026-03-12T22:59:26+00:00`
- STATS.as_of_ts: `2026-03-13T06:59:23+08:00`
- STATS.generated_at_utc(norm): `2026-03-12T22:59:26+00:00`
- STATS.data_commit_sha: `382de5d2ac00880296d803b1a6a282ee12e255f7`
- snapshot_id: `commit:382de5d2ac00880296d803b1a6a282ee12e255f7`
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
| ALERT | EXTREME_Z | NEAR:ret1% | 1 | R | p60=100;prev_p60=100;z60=4.294183566752;prev_z60=4.629212284865;prev_v=90.77;last_v=94.65;zΔ60=-0.335028718113;pΔ60=0;ret1%=4.274540046271 | ALERT | SAME | 0 | DCOILWTICO | OK | 0.02 | 2026-03-09 | 94.65 | 4.2942 | 6.2686 | 100 | 100 | -0.335 | 0 | 4.275 | P252>=95;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=1.666666666667;prev_p60=8.333333333333;z60=-2.559813930678;prev_z60=-1.630608664551;prev_v=0.57;last_v=0.51;zΔ60=-0.929205266127;pΔ60=-6.666666666667;ret1%=-10.526315789474 | NONE | NONE→ALERT | 0 | T10Y2Y | OK | 0.02 | 2026-03-12 | 0.51 | -2.5598 | -0.3712 | 1.667 | 29.365 | -0.9292 | -6.6667 | -10.526 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=75;prev_p60=45;z60=0.652714756159;prev_z60=-0.131384219977;prev_v=4.15;last_v=4.21;zΔ60=0.784098976136;pΔ60=30;ret1%=1.44578313253 | NONE | NONE→WATCH | 1 | DGS10 | OK | 0.02 | 2026-03-11 | 4.21 | 0.6527 | -0.1423 | 75 | 47.619 | 0.7841 | 30 | 1.446 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| WATCH | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 1 | Z | p60=100;prev_p60=91.666666666667;z60=2.373335795741;prev_z60=1.240501701435;prev_v=3.57;last_v=3.64;zΔ60=1.132834094306;pΔ60=8.333333333333;ret1%=1.960784313725 | NONE | NONE→WATCH | 1 | DGS2 | OK | 0.02 | 2026-03-11 | 3.64 | 2.3733 | -0.2387 | 100 | 53.175 | 1.1328 | 8.3333 | 1.961 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 2 | DJIA | OK | 0.02 | 2026-03-11 | 47417.27 | -2.2894 | 0.7065 | 1.667 | 69.444 | -0.317 | -1.6667 | -0.606 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=80;prev_p60=46.666666666667;z60=0.772930785667;prev_z60=0.162021681977;prev_v=0.5;last_v=0.55;zΔ60=0.61090910369;pΔ60=33.333333333333;ret1%=10 | WATCH | SAME | 2 | T10Y3M | OK | 0.02 | 2026-03-12 | 0.55 | 0.7729 | 1.8008 | 80 | 94.841 | 0.6109 | 33.3333 | 10 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.02 | 2026-03-06 | -0.4587 | 1.6416 | 1.5892 | 100 | 100 | 0.0053 | 0 | 0.854 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | BAMLH0A0HYM2 | OK | 0.02 | 2026-03-11 | 3.09 | 1.7412 | 0.0816 | 93.333 | 68.651 | 0.1923 | 1.6667 | 0.98 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.02 | 2026-03-06 | 119.491 | 0.4823 | -0.814 | 56.667 | 13.492 | -0.0431 | -1.6667 | -0.065 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.02 | 2026-03-11 | 22716.13 | -1.1065 | 0.6753 | 21.667 | 65.079 | 0.0855 | 1.6667 | 0.084 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | SP500 | OK | 0.02 | 2026-03-11 | 6775.8 | -1.707 | 0.7696 | 6.667 | 69.048 | -0.0142 | 0 | -0.084 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=75;prev_p60=75;z60=0.476401492764;prev_z60=0.435978634339;prev_v=-0.4436;last_v=-0.4279;zΔ60=0.040422858425;pΔ60=0;ret1%=3.539224526601 | NONE | SAME | 0 | STLFSI4 | OK | 0.02 | 2026-03-06 | -0.4279 | 0.4764 | 0.193 | 75 | 67.063 | 0.0404 | 0 | 3.539 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=95;prev_p60=96.666666666667;z60=1.863091101675;prev_z60=2.17409635604;prev_v=24.93;last_v=24.23;zΔ60=-0.311005254364;pΔ60=-1.666666666667;ret1%=-2.807862013638 | WATCH | WATCH→NONE | 0 | VIXCLS | OK | 0.02 | 2026-03-11 | 24.23 | 1.8631 | 0.9916 | 95 | 89.683 | -0.311 | -1.6667 | -2.808 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-13T06:59:23+08:00 |
