# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=2 / NONE=11; CHANGED=1; WATCH_STREAK>=3=0; NEAR=5; JUMP_1of3=5
- RUN_TS_UTC: `2026-02-23T23:06:49.188973+00:00`
- day_key_local: `2026-02-24`
- STATS.generated_at_utc: `2026-02-23T23:06:16+00:00`
- STATS.as_of_ts: `2026-02-24T07:06:12+08:00`
- STATS.generated_at_utc(norm): `2026-02-23T23:06:16+00:00`
- STATS.data_commit_sha: `186a7a342a837c24b4acfa73bc50612f711344cd`
- snapshot_id: `commit:186a7a342a837c24b4acfa73bc50612f711344cd`
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
| INFO | LONG_EXTREME | NEAR:PΔ60 | 1 | P | p60=91.666666666667;prev_p60=75;z60=1.067945320773;prev_z60=0.804773855199;prev_v=49395.160000000003;last_v=49625.970000000001;zΔ60=0.263171465573;pΔ60=16.666666666667;ret1%=0.467272502002 | INFO | SAME | 0 | DJIA | OK | 0.01 | 2026-02-20 | 49625.97 | 1.0679 | 1.5703 | 91.667 | 98.016 | 0.2632 | 16.6667 | 0.467 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| INFO | LONG_EXTREME | NA | 0 | NA | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.01 | 2026-02-13 | -0.4707 | 1.6199 | 1.5184 | 100 | 100 | 0.0077 | 0 | 0.811 | P252>=95 | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 0.01 | 2026-02-20 | 2.86 | 0.2872 | -0.5684 | 58.333 | 31.349 | -0.2032 | -10 | -0.694 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DCOILWTICO | OK | 0.01 | 2026-02-17 | 62.53 | 1.0955 | -0.3172 | 80 | 39.286 | -0.2232 | -6.6667 | -0.825 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS10 | OK | 0.01 | 2026-02-20 | 4.08 | -1.1468 | -1.1779 | 15 | 13.492 | -0.0113 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | DGS2 | OK | 0.01 | 2026-02-20 | 3.48 | -0.5298 | -1.1524 | 45 | 14.683 | 0.2078 | 8.3333 | 0.288 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | INFO | INFO→NONE | 0 | DTWEXBGS | OK | 0.01 | 2026-02-20 | 117.9917 | -1.1789 | -1.4815 | 21.667 | 5.159 | -0.1682 | -1.6667 | -0.206 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 0.01 | 2026-02-20 | 22886.07 | -1.2179 | 0.8286 | 15 | 71.429 | 0.4654 | 5 | 0.896 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | JUMP_DELTA | NEAR:PΔ60 | 1 | P | p60=58.333333333333;prev_p60=41.666666666667;z60=0.405832454602;prev_z60=-0.222386880443;prev_v=6861.89;last_v=6909.51;zΔ60=0.628219335045;pΔ60=16.666666666667;ret1%=0.693977898218 | NONE | SAME | 0 | SP500 | OK | 0.01 | 2026-02-20 | 6909.51 | 0.4058 | 1.1304 | 58.333 | 90.079 | 0.6282 | 16.6667 | 0.694 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=48.333333333333;prev_p60=36.666666666667;z60=-0.250970486178;prev_z60=-0.397538049189;prev_v=-0.6558;last_v=-0.6208;zΔ60=0.14656756301;pΔ60=11.666666666667;ret1%=5.336992985666 | NONE | SAME | 0 | STLFSI4 | OK | 0.01 | 2026-02-13 | -0.6208 | -0.251 | -0.3793 | 48.333 | 43.651 | 0.1466 | 11.6667 | 5.337 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | NA | NA | 0 | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 0.01 | 2026-02-23 | 0.6 | -1.0545 | 0.6119 | 21.667 | 78.571 | -0.0143 | 0 | 0 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=11.666666666667;prev_p60=21.666666666667;z60=-1.181767367757;prev_z60=-0.669341281558;prev_v=0.39;last_v=0.34;zΔ60=-0.512426086199;pΔ60=-10;ret1%=-12.820512820513 | NONE | SAME | 0 | T10Y3M | OK | 0.01 | 2026-02-23 | 0.34 | -1.1818 | 0.9799 | 11.667 | 78.968 | -0.5124 | -10 | -12.821 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
| NONE | JUMP_RET | NEAR:ret1% | 1 | R | p60=86.666666666667;prev_p60=91.666666666667;z60=1.21001993381;prev_z60=1.827209270625;prev_v=20.23;last_v=19.09;zΔ60=-0.617189336815;pΔ60=-5;ret1%=-5.635195254572 | NONE | SAME | 0 | VIXCLS | OK | 0.01 | 2026-02-20 | 19.09 | 1.21 | 0.0066 | 86.667 | 67.857 | -0.6172 | -5 | -5.635 | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-02-24T07:06:12+08:00 |
