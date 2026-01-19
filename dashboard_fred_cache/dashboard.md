# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=4 / INFO=3 / NONE=6; CHANGED=1; WATCH_STREAK>=3=3; NEAR=9; JUMP_1of3=4
- RUN_TS_UTC: `2026-01-19T00:02:13.321794+00:00`
- STATS.generated_at_utc: `2026-01-18T18:53:26+00:00`
- STATS.as_of_ts: `2026-01-19T02:53:10+08:00`
- STATS.generated_at_utc(norm): `2026-01-18T18:53:26+00:00`
- STATS.data_commit_sha: `25cb8c117a49eea274b9c6ad1e7024614d9e9c80`
- snapshot_id: `commit:25cb8c117a49eea274b9c6ad1e7024614d9e9c80`
- streak_basis: `distinct snapshots (snapshot_id); re-run same snapshot does not increment`
- streak_calc: `basis=snapshot_id; consecutive WATCH across prior distinct snapshots; re-run same snapshot excluded`
- script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- stale_hours: `72.0`
- dash_history: `dashboard_fred_cache/history.json`
- history_lite_used_for_jump: `cache/history_lite.json`
- ret1_guard: `ret1% guard: if abs(prev_value)<1e-3 -> ret1%=NA (avoid near-zero denom blow-ups)`
- threshold_eps: `threshold_eps: Z=1e-12, P=1e-09, R=1e-09 (avoid rounding/float boundary mismatch)`
- output_format: `display_nd: age=2, value=4, z=4, p=3, delta=4, ret1=3; dbg_nd=12 (dbg only for Near/Jump)`
- alignment: `PASS`; checked=13; mismatch=0; hl_missing=0
- jump_calc: `ret1%=(latest-prev)/abs(prev)*100; zΔ60=z60(latest)-z60(prev); pΔ60=p60(latest)-p60(prev) (prev computed from window ending at prev)`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (INFO), P252<=2 (ALERT)); Jump(2/3 vote: abs(zΔ60)>=0.75, abs(pΔ60)>=20, abs(ret1%)>=2 -> WATCH); Near(within 10% of jump thresholds)`

| Signal | Tag | Near | JUMP_HITS | HITBITS | DBG | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60+NEAR:ret1% | 3 | Z+P+R | zΔ60=0.753284869684;pΔ60=35;ret1%=2.220309810671 | WATCH | SAME | 3 | DCOILWTICO | OK | 5.15 | 2026-01-12 | 59.39 | 0.0292 | 13.889 | 0.7533 | 35 | 2.22 | abs(zΔ60)>=0.75;abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | zΔ60=0.881068008374;pΔ60=20;ret1%=1.424501424501 | NONE | NONE→WATCH | 1 | DGS2 | OK | 5.15 | 2026-01-15 | 3.56 | 0.7811 | 24.603 | 0.8811 | 20 | 1.425 | abs(zΔ60)>=0.75;abs(pΔ60)>=20 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| WATCH | JUMP_DELTA | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | zΔ60=-0.402847963268;pΔ60=-23.333333333333;ret1%=-17.468175388967 | WATCH | SAME | 3 | STLFSI4 | OK | 5.15 | 2026-01-09 | -0.6644 | -0.4541 | 36.508 | -0.4028 | -23.3333 | -17.468 | abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| WATCH | LONG_EXTREME | NEAR:PΔ60+NEAR:ret1% | 2 | P+R | zΔ60=0.393825236276;pΔ60=30;ret1%=16.326530612245 | WATCH | SAME | 3 | T10Y3M | OK | 5.15 | 2026-01-16 | 0.57 | 1.3071 | 100 | 0.3938 | 30 | 16.327 | P252>=95;abs(pΔ60)>=20;abs(ret1%)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 5.15 | 2026-01-16 | 49359.33 | 1.6199 | 98.413 | -0.1594 | -1.6667 | -0.168 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | zΔ60=-0.311746896402;pΔ60=-11.666666666667;ret1%=-5.916557639192 | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 5.15 | 2026-01-09 | -0.51 | 1.2176 | 97.222 | -0.3117 | -11.6667 | -5.917 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 5.15 | 2026-01-16 | 6940.01 | 1.1849 | 98.016 | -0.0887 | -1.6667 | -0.064 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| NONE | NA | NEAR:ret1% | 0 | NA | zΔ60=-0.312768028861;pΔ60=-8.333333333333;ret1%=-1.811594202899 | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 5.15 | 2026-01-15 | 2.71 | -1.7093 | 8.333 | -0.3128 | -8.3333 | -1.812 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 5.15 | 2026-01-15 | 4.17 | 0.8986 | 32.937 | 0.2906 | 10 | 0.482 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| NONE | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 1 | Z | zΔ60=0.920128699887;pΔ60=18.333333333333;ret1%=0.498384833099 | NONE | SAME | 0 | DTWEXBGS | OK | 5.15 | 2026-01-09 | 120.5856 | -0.8556 | 20.635 | 0.9201 | 18.3333 | 0.498 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 5.15 | 2026-01-16 | 23515.39 | 0.5427 | 91.667 | -0.0592 | -3.3333 | -0.062 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | zΔ60=0.549913887909;pΔ60=8.333333333333;ret1%=6.55737704918 | NONE | SAME | 0 | T10Y2Y | OK | 5.15 | 2026-01-16 | 0.65 | 0.7321 | 92.46 | 0.5499 | 8.3333 | 6.557 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | zΔ60=-0.328063721196;pΔ60=-15;ret1%=-5.432835820896 | NONE | SAME | 0 | VIXCLS | OK | 5.15 | 2026-01-15 | 15.84 | -0.4744 | 25.794 | -0.3281 | -15 | -5.433 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-19T02:53:10+08:00 |
