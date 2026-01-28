# Risk Dashboard Snapshot (snapshot_fast)

- Summary: ALERT=0 / WATCH=0 / INFO=12 / NONE=0; CHANGED=0; WATCH_STREAK>=3=0
- RUN_TS_UTC: `2026-01-28T17:08:04.417892+00:00`
- SNAPSHOT.as_of_ts: `2026-01-28T15:57:05Z`
- snapshot_script_version: `fallback_vA_official_no_key_lock+history_v1`
- stale_hours: `36.0`
- input_snapshot: `fallback_cache/latest.json`
- dash_history: `dashboard_snapshot/history.json`
- streak_calc: `PrevSignal/StreakWA derived from dash_history file (past renderer outputs) + today's signal`
- signal_rules: `DQ=MISSING->ALERT; STALE>stale_hours->WATCH; STALE>=2x->ALERT; NOTES:ERROR->ALERT; NOTES:WARN->INFO; else INFO; Near=within 10% below staleness threshold`

| Signal | Tag | Near | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | change_pct_1d | notes | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFO | fredgraph_no_key | NA | INFO | SAME | 0 | BAMLH0A0HYM2 | OK | 1.18 | 2026-01-27 | 2.71 | NA | WARN:fredgraph_no_key(BAMLH0A0HYM2) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2 | 2026-01-28T15:57:05Z |
| INFO | nonofficial_datahub_oil_prices | NA | INFO | SAME | 0 | DCOILWTICO | OK | 1.18 | 2026-01-20 | 60.3 | NA | WARN:nonofficial_datahub_oil_prices(wti-daily) | https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv | 2026-01-28T15:57:05Z |
| INFO | fallback_treasury_csv | NA | INFO | SAME | 0 | DGS10 | OK | 1.18 | 2026-01-27 | 4.24 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-28T15:57:05Z |
| INFO | fallback_treasury_csv | NA | INFO | SAME | 0 | DGS2 | OK | 1.18 | 2026-01-27 | 3.53 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-28T15:57:05Z |
| INFO | nonofficial_stooq | NA | INFO | SAME | 0 | DJIA | OK | 1.18 | 2026-01-28 | 49017.34 | 0.028427 | WARN:nonofficial_stooq(^dji);derived_1d_pct | https://stooq.com/q/d/l/?s=^dji&i=d | 2026-01-28T15:57:05Z |
| INFO | nonofficial_stooq | NA | INFO | SAME | 0 | NASDAQCOM | OK | 1.18 | 2026-01-28 | 23850.818 | 0.141571 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | https://stooq.com/q/d/l/?s=^ndq&i=d | 2026-01-28T15:57:05Z |
| INFO | fallback_chicagofed_nfci | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 1.18 | 2026-01-23 | -0.482954 | NA | WARN:fallback_chicagofed_nfci(nonfinancial leverage) | https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv | 2026-01-28T15:57:05Z |
| INFO | nonofficial_stooq | NA | INFO | SAME | 0 | SP500 | OK | 1.18 | 2026-01-28 | 6981.53 | 0.041985 | WARN:nonofficial_stooq(^spx);derived_1d_pct | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-28T15:57:05Z |
| INFO | derived_from_treasury | NA | INFO | SAME | 0 | T10Y2Y | OK | 1.18 | 2026-01-27 | 0.71 | NA | WARN:derived_from_treasury(10Y-2Y) | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-28T15:57:05Z |
| INFO | derived_from_treasury | NA | INFO | SAME | 0 | T10Y3M | OK | 1.18 | 2026-01-27 | 0.57 | NA | WARN:derived_from_treasury(10Y-3M) | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-28T15:57:05Z |
| INFO | fallback_treasury_csv | NA | INFO | SAME | 0 | UST3M | OK | 1.18 | 2026-01-27 | 3.67 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-28T15:57:05Z |
| INFO | fallback_cboe_vix | NA | INFO | SAME | 0 | VIXCLS | OK | 1.18 | 2026-01-27 | 16.35 | NA | WARN:fallback_cboe_vix | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-28T15:57:05Z |
