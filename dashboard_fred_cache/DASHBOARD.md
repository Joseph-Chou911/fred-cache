# Risk Dashboard (fred_cache)

- Summary: ALERT=0 / WATCH=0 / INFO=0 / NONE=13; CHANGED=4; WATCH_STREAK>=3=0
- RUN_TS_UTC: `2026-01-18T11:56:36.608238+00:00`
- STATS.generated_at_utc: `2026-01-18T06:57:29+00:00`
- STATS.as_of_ts: `2026-01-18T14:57:27+08:00`
- script_version: `stats_v1_ddof0_w60_w252_pct_le_ret1_delta`
- stale_hours: `72.0`
- dash_history: `dashboard_fred_cache/history.json`
- history_lite_used_for_jump: `cache/history_lite.json`
- streak_calc: `PrevSignal/Streak derived from history.json (dashboard outputs)`
- jump_calc: `recompute z60/p252/zΔ60/pΔ60/ret1%60 from history_lite values; ret1% denom = abs(prev_value) else NA`
- signal_rules: `Extreme(abs(Z60)>=2 (WATCH), abs(Z60)>=2.5 (ALERT), P252>=95 or <=5 (WATCH/INFO), P252<=2 (ALERT)); Jump(abs(ZΔ60)>=0.75 OR abs(PΔ60)>=15 OR abs(ret1%60)>=2); Near(within 10% of jump thresholds); INFO if only long-extreme and no jump and abs(Z60)<2`

| Signal | Tag | Near | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | z60 | p252 | z_delta60 | p_delta60 | ret1_pct60 | Reason | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NONE | NA | NA | INFO | INFO→NONE | 0 | DJIA | OK | 4.99 | 2026-01-16 | 49359.33 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DJIA&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | INFO | INFO→NONE | 0 | NFCINONFINLEVERAGE | OK | 4.99 | 2026-01-09 | -0.51002 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NFCINONFINLEVERAGE&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | INFO | INFO→NONE | 0 | SP500 | OK | 4.99 | 2026-01-16 | 6940.01 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=SP500&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | INFO | INFO→NONE | 0 | T10Y3M | OK | 4.99 | 2026-01-16 | 0.57 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y3M&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | BAMLH0A0HYM2 | OK | 4.99 | 2026-01-15 | 2.71 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | DCOILWTICO | OK | 4.99 | 2026-01-12 | 59.39 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DCOILWTICO&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | DGS10 | OK | 4.99 | 2026-01-15 | 4.17 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | DGS2 | OK | 4.99 | 2026-01-15 | 3.56 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | DTWEXBGS | OK | 4.99 | 2026-01-09 | 120.5856 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | NASDAQCOM | OK | 4.99 | 2026-01-16 | 23515.39 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQCOM&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | STLFSI4 | OK | 4.99 | 2026-01-09 | -0.6644 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=STLFSI4&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | T10Y2Y | OK | 4.99 | 2026-01-16 | 0.65 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
| NONE | NA | NA | NONE | SAME | 0 | VIXCLS | OK | 4.99 | 2026-01-15 | 15.84 | NA | NA | NA | NA | NA | NA | https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&file_type=json&sort_order=desc&limit=1 | 2026-01-18T14:57:27+08:00 |
