# Risk Dashboard Snapshot (snapshot_fast)

- Summary: ALERT=0 / WATCH=0 / INFO=12 / NONE=0; CHANGED=0; WATCH_STREAK>=3=0
- RUN_TS_UTC: `2026-02-19T16:06:41.864231+00:00`
- SNAPSHOT.as_of_ts: `2026-02-19T15:08:36Z`
- snapshot_script_version: `fallback_vA_official_no_key_lock+history_v1`
- stale_hours: `36.0`
- input_snapshot: `fallback_cache/latest.json`
- dash_history: `dashboard_snapshot/history.json`
- streak_calc: `PrevSignal/StreakWA derived from dash_history file (past renderer outputs) + today's signal`
- signal_rules: `DQ=MISSING->ALERT; STALE>stale_hours->WATCH; STALE>=2x->ALERT; NOTES:ERROR->ALERT; NOTES:WARN->INFO; else INFO; Near=within 10% below staleness threshold`

| Signal | Tag | Near | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | change_pct_1d | notes | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFO | fredgraph_no_key | NA | INFO | SAME | 0 | BAMLH0A0HYM2 | OK | 0.97 | 2026-02-18 | 2.86 | NA | WARN:fredgraph_no_key(BAMLH0A0HYM2) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2 | 2026-02-19T15:08:36Z |
| INFO | nonofficial_datahub_oil_prices | NA | INFO | SAME | 0 | DCOILWTICO | OK | 0.97 | 2026-02-09 | 64.53 | NA | WARN:nonofficial_datahub_oil_prices(wti-daily) | https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv | 2026-02-19T15:08:36Z |
| INFO | fallback_treasury_csv | NA | INFO | SAME | 0 | DGS10 | OK | 0.97 | 2026-02-18 | 4.09 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202602?_format=csv&field_tdr_date_value_month=202602&page=&type=daily_treasury_yield_curve | 2026-02-19T15:08:36Z |
| INFO | fallback_treasury_csv | NA | INFO | SAME | 0 | DGS2 | OK | 0.97 | 2026-02-18 | 3.47 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202602?_format=csv&field_tdr_date_value_month=202602&page=&type=daily_treasury_yield_curve | 2026-02-19T15:08:36Z |
| INFO | nonofficial_stooq | NA | INFO | SAME | 0 | DJIA | OK | 0.97 | 2026-02-19 | 49422.23 | -0.484126 | WARN:nonofficial_stooq(^dji);derived_1d_pct | https://stooq.com/q/d/l/?s=^dji&i=d | 2026-02-19T15:08:36Z |
| INFO | nonofficial_stooq | NA | INFO | SAME | 0 | NASDAQCOM | OK | 0.97 | 2026-02-19 | 22715.768 | -0.1664 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | https://stooq.com/q/d/l/?s=^ndq&i=d | 2026-02-19T15:08:36Z |
| INFO | fallback_chicagofed_nfci | NA | INFO | SAME | 0 | NFCINONFINLEVERAGE | OK | 0.97 | 2026-02-13 | -0.470738 | NA | WARN:fallback_chicagofed_nfci(nonfinancial leverage) | https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv | 2026-02-19T15:08:36Z |
| INFO | nonofficial_stooq | NA | INFO | SAME | 0 | SP500 | OK | 0.97 | 2026-02-19 | 6865.31 | -0.232514 | WARN:nonofficial_stooq(^spx);derived_1d_pct | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-02-19T15:08:36Z |
| INFO | derived_from_treasury | NA | INFO | SAME | 0 | T10Y2Y | OK | 0.97 | 2026-02-18 | 0.62 | NA | WARN:derived_from_treasury(10Y-2Y) | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202602?_format=csv&field_tdr_date_value_month=202602&page=&type=daily_treasury_yield_curve | 2026-02-19T15:08:36Z |
| INFO | derived_from_treasury | NA | INFO | SAME | 0 | T10Y3M | OK | 0.97 | 2026-02-18 | 0.39 | NA | WARN:derived_from_treasury(10Y-3M) | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202602?_format=csv&field_tdr_date_value_month=202602&page=&type=daily_treasury_yield_curve | 2026-02-19T15:08:36Z |
| INFO | fallback_treasury_csv | NA | INFO | SAME | 0 | UST3M | OK | 0.97 | 2026-02-18 | 3.7 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202602?_format=csv&field_tdr_date_value_month=202602&page=&type=daily_treasury_yield_curve | 2026-02-19T15:08:36Z |
| INFO | fallback_cboe_vix | NA | INFO | SAME | 0 | VIXCLS | OK | 0.97 | 2026-02-18 | 19.62 | NA | WARN:fallback_cboe_vix | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-02-19T15:08:36Z |
