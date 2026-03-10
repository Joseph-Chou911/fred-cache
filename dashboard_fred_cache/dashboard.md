# Risk Dashboard (fred_cache)

- Summary: ALERT=3 / WATCH=2 / INFO=1 / NONE=7; CHANGED=4; WATCH_STREAK>=3=2; NEAR=8; JUMP_1of3=3
- RUN_TS_UTC: `2026-03-10T14:06:11.033703+00:00`
- day_key_local: `2026-03-10`
- STATS.generated_at_utc: `2026-03-10T13:35:46+00:00`
- STATS.as_of_ts: `2026-03-10T21:35:44+08:00`
- STATS.generated_at_utc(norm): `2026-03-10T13:35:46+00:00`
- STATS.data_commit_sha: `0b20f62135068c6e09a3ae88207c45754da6cf48`
- snapshot_id: `commit:0b20f62135068c6e09a3ae88207c45754da6cf48`
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
| ALERT | EXTREME_Z | NEAR:ret1% | 0 | NA | p60=100;prev_p60=100;z60=2.620244567573;prev_z60=2.312625217785;prev_v=3.13;last_v=3.19;zΔ60=0.307619349788;pΔ60=0;ret1%=1.916932907348 | NONE | NONE→ALERT | 0 | BAMLH0A0HYM2 | OK | 0.51 | 2026-03-09 | 3.19 | 2.6202 | 0.3545 | 100 | 81.746 | 0.3076 | 0 | 1.917 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=100;z60=2.925254423533;prev_z60=1.930669257529;prev_v=66.96;last_v=71.13;zΔ60=0.994585166004;pΔ60=0;ret1%=6.227598566308 | ALERT | SAME | 0 | DCOILWTICO | OK | 0.51 | 2026-03-02 | 71.13 | 2.9253 | 1.8686 | 100 | 96.825 | 0.9946 | 0 | 6.228 | P252>=95;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:ret1% | 2 | Z+R | p60=100;prev_p60=100;z60=4.022462658751;prev_z60=2.527993626484;prev_v=23.75;last_v=29.49;zΔ60=1.494469032267;pΔ60=0;ret1%=24.168421052632 | ALERT | SAME | 0 | VIXCLS | OK | 0.51 | 2026-03-06 | 29.49 | 4.0225 | 2.0126 | 100 | 94.841 | 1.4945 | 0 | 24.168 | abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=18.333333333333;prev_p60=1.666666666667;z60=-1.235436299705;prev_z60=-2.058642711557;prev_v=22387.68;last_v=22695.950000000001;zΔ60=0.823206411851;pΔ60=16.666666666667;ret1%=1.376962686621 | WATCH | SAME | 4 | NASDAQCOM | OK | 0.51 | 2026-03-09 | 22695.95 | -1.2354 | 0.6788 | 18.333 | 64.683 | 0.8232 | 16.6667 | 1.377 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | p60=75;prev_p60=50;z60=0.435978634339;prev_z60=-0.162988734641;prev_v=-0.5981;last_v=-0.4436;zΔ60=0.59896736898;pΔ60=25;ret1%=25.831800702224 | WATCH | SAME | 6 | STLFSI4 | OK | 0.51 | 2026-02-27 | -0.4436 | 0.436 | 0.1497 | 75 | 65.873 | 0.599 | 25 | 25.832 | abs(pΔ60)>=15;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.51 | 2026-02-27 | -0.4627 | 1.6364 | 1.5655 | 100 | 100 | 0.0086 | 0 | 0.88 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.51 | 2026-03-06 | 4.15 | -0.1404 | -0.584 | 43.333 | 34.127 | 0.2719 | 13.3333 | 0.484 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.51 | 2026-03-06 | 3.56 | 1.0353 | -0.6812 | 83.333 | 34.524 | -0.1745 | -6.6667 | -0.28 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | NA | NA | 0 | NA | NA | WATCH | WATCH→NONE | 0 | DJIA | OK | 0.51 | 2026-03-09 | 47740.8 | -1.9585 | 0.8272 | 3.333 | 75 | 0.3556 | 1.6667 | 0.504 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | NA | NA | 0 | NA | NA | INFO | INFO→NONE | 0 | DTWEXBGS | OK | 0.51 | 2026-03-06 | 119.491 | 0.4823 | -0.814 | 56.667 | 13.492 | -0.0431 | -1.6667 | -0.065 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60 | 1 | Z | p60=6.666666666667;prev_p60=3.333333333333;z60=-1.526765380538;prev_z60=-2.490025789297;prev_v=6740.02;last_v=6795.99;zΔ60=0.963260408759;pΔ60=3.333333333333;ret1%=0.830412966134 | WATCH | WATCH→NONE | 0 | SP500 | OK | 0.51 | 2026-03-09 | 6795.99 | -1.5268 | 0.8224 | 6.667 | 70.238 | 0.9633 | 3.3333 | 0.83 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=6.666666666667;prev_p60=13.333333333333;z60=-1.881483917584;prev_z60=-1.312371317635;prev_v=0.59;last_v=0.56;zΔ60=-0.569112599949;pΔ60=-6.666666666667;ret1%=-5.084745762712 | NONE | SAME | 0 | T10Y2Y | OK | 0.51 | 2026-03-09 | 0.56 | -1.8815 | 0.1728 | 6.667 | 63.889 | -0.5691 | -6.6667 | -5.085 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=25;prev_p60=33.333333333333;z60=-0.927733966002;prev_z60=-0.329997080286;prev_v=0.46;last_v=0.41;zΔ60=-0.597736885717;pΔ60=-8.333333333333;ret1%=-10.869565217391 | NONE | SAME | 0 | T10Y3M | OK | 0.51 | 2026-03-09 | 0.41 | -0.9277 | 1.2187 | 25 | 80.952 | -0.5977 | -8.3333 | -10.87 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-10T21:35:44+08:00 |
