# Risk Dashboard (fred_cache)

- Summary: ALERT=1 / WATCH=4 / INFO=1 / NONE=7; CHANGED=0; WATCH_STREAK>=3=1; NEAR=5; JUMP_1of3=3
- RUN_TS_UTC: `2026-03-01T13:46:42.135970+00:00`
- day_key_local: `2026-03-01`
- STATS.generated_at_utc: `2026-03-01T13:08:50+00:00`
- STATS.as_of_ts: `2026-03-01T21:08:46+08:00`
- STATS.generated_at_utc(norm): `2026-03-01T13:08:50+00:00`
- STATS.data_commit_sha: `6a955fe9a7ade05bf4b1880c38e98a1380f1f591`
- snapshot_id: `commit:6a955fe9a7ade05bf4b1880c38e98a1380f1f591`
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
| ALERT | LONG_EXTREME | NA | 0 | NA | NA | ALERT | SAME | 0 | DGS2 | OK | 0.63 | 2026-02-26 | 3.42 | -1.6303 | -1.4465 | 3.333 | 1.19 | -0.5347 | -11.6667 | -0.87 | P252<=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 4 | DCOILWTICO | OK | 0.63 | 2026-02-23 | 66.36 | 2.0613 | 0.6316 | 96.667 | 73.413 | -0.2337 | -3.3333 | -0.495 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| WATCH | EXTREME_Z | NA | 0 | NA | NA | WATCH | SAME | 2 | DGS10 | OK | 0.63 | 2026-02-26 | 4.02 | -2.0591 | -1.5766 | 1.667 | 5.952 | -0.429 | -8.3333 | -0.741 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| WATCH | JUMP_DELTA | NEAR:ZΔ60+NEAR:PΔ60 | 2 | Z+P | p60=46.666666666667;prev_p60=81.666666666667;z60=0.095191858003;prev_z60=0.868743162208;prev_v=49499.199999999997;last_v=48977.919999999998;zΔ60=-0.773551304205;pΔ60=-35;ret1%=-1.053107929017 | WATCH | SAME | 2 | DJIA | OK | 0.63 | 2026-02-27 | 48977.92 | 0.0952 | 1.2894 | 46.667 | 87.302 | -0.7736 | -35 | -1.053 | abs(zΔ60)>=0.75;abs(pΔ60)>=15 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| WATCH | EXTREME_Z | NEAR:ret1% | 1 | R | p60=1.666666666667;prev_p60=8.333333333333;z60=-2.271099895831;prev_z60=-1.763365086643;prev_v=0.34;last_v=0.3;zΔ60=-0.507734809188;pΔ60=-6.666666666667;ret1%=-11.764705882353 | WATCH | SAME | 2 | T10Y3M | OK | 0.63 | 2026-02-27 | 0.3 | -2.2711 | 0.7775 | 1.667 | 76.587 | -0.5077 | -6.6667 | -11.765 | abs(Z60)>=2 | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.63 | 2026-02-20 | -0.4668 | 1.6277 | 1.5414 | 100 | 100 | 0.0078 | 0 | 0.835 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.63 | 2026-02-26 | 2.98 | 1.5586 | -0.2325 | 98.333 | 57.54 | 0.4005 | 10 | 1.361 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 0.63 | 2026-02-20 | 117.9917 | -1.1789 | -1.4815 | 21.667 | 5.159 | -0.1682 | -1.6667 | -0.206 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.63 | 2026-02-27 | 22668.21 | -1.674 | 0.703 | 10 | 63.889 | -0.5257 | -6.6667 | -0.919 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=40;prev_p60=55;z60=-0.230105714746;prev_z60=0.311168312622;prev_v=6908.86;last_v=6878.88;zΔ60=-0.541274027368;pΔ60=-15;ret1%=-0.433935555215 | NONE | SAME | 0 | SP500 | OK | 0.63 | 2026-02-27 | 6878.88 | -0.2301 | 1.0281 | 40 | 84.921 | -0.5413 | -15 | -0.434 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=50;prev_p60=48.333333333333;z60=-0.162988734641;prev_z60=-0.250970486178;prev_v=-0.6208;last_v=-0.5981;zΔ60=0.087981751537;pΔ60=1.666666666667;ret1%=3.656572164948 | NONE | SAME | 0 | STLFSI4 | OK | 0.63 | 2026-02-20 | -0.5981 | -0.163 | -0.3125 | 50 | 48.016 | 0.088 | 1.6667 | 3.657 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.63 | 2026-02-27 | 0.59 | -1.4137 | 0.5007 | 11.667 | 75.794 | -0.2471 | -8.3333 | -1.667 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=78.333333333333;prev_p60=76.666666666667;z60=0.841980512869;prev_z60=0.526264572196;prev_v=17.93;last_v=18.63;zΔ60=0.315715940673;pΔ60=1.666666666667;ret1%=3.904071388734 | NONE | SAME | 0 | VIXCLS | OK | 0.63 | 2026-02-26 | 18.63 | 0.842 | -0.0687 | 78.333 | 65.476 | 0.3157 | 1.6667 | 3.904 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-03-01T21:08:46+08:00 |
