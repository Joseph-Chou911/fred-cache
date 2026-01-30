# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=0 / INFO=6 / NONE=6; CHANGED=0; WATCH_STREAK>=3=0; NEAR=4; JUMP_1of3=3
- RUN_TS_UTC: `2026-01-30T15:02:02.080650+00:00`
- day_key_local: `2026-01-30`
- STATS.generated_at_utc: `2026-01-30T14:08:54+00:00`
- STATS.as_of_ts: `2026-01-30T22:08:52+08:00`
- STATS.generated_at_utc(norm): `2026-01-30T14:08:54+00:00`
- STATS.data_commit_sha: `6f6fcd83ba3113e57f333a65bd7701978915681a`
- snapshot_id: `commit:6f6fcd83ba3113e57f333a65bd7701978915681a`
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
| ALERT | EXTREME_Z | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=1.666666666667;prev_p60=21.666666666667;z60=-2.595576368124;prev_z60=-1.045572439498;prev_v=120.4478;last_v=119.2855;zΔ60=-1.550003928626;pΔ60=-20;ret1%=-0.964982340898 | ALERT | SAME | 0 | DTWEXBGS | OK | 0.89 | 2026-01-23 | 119.2855 | -2.5956 | -1.2219 | 1.667 | 0.397 | -1.55 | -20 | -0.965 | P252<=2;abs(Z60)>=2.5 | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | DJIA | OK | 0.89 | 2026-01-29 | 49071.56 | 1.0051 | 1.6111 | 80 | 95.238 | 0.0256 | 0 | 0.114 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NASDAQCOM | OK | 0.89 | 2026-01-29 | 23685.12 | 0.9887 | 1.282 | 91.667 | 96.825 | -0.4519 | -8.3333 | -0.722 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| INFO | LONG_EXTREME | NEAR:ret1% | 1 | R | p60=98.333333333333;prev_p60=90;z60=1.449255202935;prev_z60=1.23769212487;prev_v=-0.50568;last_v=-0.48295;zΔ60=0.211563078064;pΔ60=8.333333333333;ret1%=4.494937509888 | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.89 | 2026-01-23 | -0.4829 | 1.4493 | 1.423 | 98.333 | 99.603 | 0.2116 | 8.3333 | 4.495 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | SP500 | OK | 0.89 | 2026-01-29 | 6969.01 | 1.2855 | 1.3918 | 95 | 98.81 | -0.1325 | -3.3333 | -0.129 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y2Y | OK | 0.89 | 2026-01-29 | 0.71 | 1.3447 | 1.6565 | 96.667 | 99.206 | 0.1106 | 6.6667 | 1.429 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | T10Y3M | OK | 0.89 | 2026-01-29 | 0.57 | 1.0368 | 2.3142 | 96.667 | 99.206 | -0.0934 | -1.6667 | -1.724 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.89 | 2026-01-28 | 2.72 | -1.2342 | -0.9162 | 13.333 | 8.73 | 0.1102 | 1.6667 | 0.369 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DCOILWTICO | OK | 0.89 | 2026-01-26 | 60.46 | 0.7433 | -0.9029 | 76.667 | 20.635 | 0.1339 | 3.3333 | 0.265 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.89 | 2026-01-28 | 4.26 | 1.8566 | -0.0367 | 98.333 | 52.778 | 0.2476 | 3.3333 | 0.472 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=68.333333333333;prev_p60=50;z60=0.535145366502;prev_z60=-0.014924708203;prev_v=3.53;last_v=3.56;zΔ60=0.550070074705;pΔ60=18.333333333333;ret1%=0.849858356941 | NONE | SAME | 0 | DGS2 | OK | 0.89 | 2026-01-28 | 3.56 | 0.5351 | -0.873 | 68.333 | 25.794 | 0.5501 | 18.3333 | 0.85 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=28.333333333333;prev_p60=35;z60=-0.634085378622;prev_z60=-0.397953005876;prev_v=-0.651;last_v=-0.7123;zΔ60=-0.236132372747;pΔ60=-6.666666666667;ret1%=-9.416282642089 | NONE | SAME | 0 | STLFSI4 | OK | 0.89 | 2026-01-23 | -0.7123 | -0.6341 | -0.6485 | 28.333 | 28.968 | -0.2361 | -6.6667 | -9.416 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | VIXCLS | OK | 0.89 | 2026-01-28 | 16.35 | -0.2835 | -0.4832 | 48.333 | 33.73 | 0.0069 | 1.6667 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-30T22:08:52+08:00 |
