# Risk Dashboard Snapshot (snapshot_fast)

- Summary: ALERT=0 / WATCH=12 / INFO=0 / NONE=0; CHANGED=0; WATCH_STREAK>=3=0
- RUN_TS_UTC: `2026-01-18T10:49:06.795545+00:00`
- SNAPSHOT.as_of_ts: `2026-01-18T07:40:37Z`
- snapshot_script_version: `fallback_vA_official_no_key_lock+history_v1`
- stale_hours: `36.0`
- input_snapshot: `fallback_cache/latest.json`
- dash_history: `dashboard_snapshot/history.json`
- streak_calc: `PrevSignal/StreakWA derived from dashboard/history.json (past renderer outputs) + today's signal`
- signal_rules: `DQ=MISSING->ALERT; STALE>stale_hours->WATCH; STALE>=2x->ALERT; NOTES:ERROR->ALERT; NOTES:WARN->WATCH; else INFO; Near=within 10% below staleness threshold`

| Signal | Tag | Near | PrevSignal | DeltaSignal | StreakWA | Series | DQ | age_h | data_date | value | change_pct_1d | notes | Source | as_of_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WATCH | fredgraph_no_key | NA | WATCH | SAME | 2 | BAMLH0A0HYM2 | OK | 3.14 | 2026-01-15 | 2.71 | NA | WARN:fredgraph_no_key(BAMLH0A0HYM2) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2 | 2026-01-18T07:40:37Z |
| WATCH | nonofficial_datahub_oil_prices | NA | WATCH | SAME | 2 | DCOILWTICO | OK | 3.14 | 2026-01-12 | 59.39 | NA | WARN:nonofficial_datahub_oil_prices(wti-daily) | https://datahub.io/core/oil-prices/_r/-/data/wti-daily.csv | 2026-01-18T07:40:37Z |
| WATCH | fallback_treasury_csv | NA | WATCH | SAME | 2 | DGS10 | OK | 3.14 | 2026-01-16 | 4.24 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-18T07:40:37Z |
| WATCH | fallback_treasury_csv | NA | WATCH | SAME | 2 | DGS2 | OK | 3.14 | 2026-01-16 | 3.59 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-18T07:40:37Z |
| WATCH | nonofficial_stooq | NA | WATCH | SAME | 2 | DJIA | OK | 3.14 | 2026-01-16 | 49359.33 | -0.168094 | WARN:nonofficial_stooq(^dji);derived_1d_pct | https://stooq.com/q/d/l/?s=^dji&i=d | 2026-01-18T07:40:37Z |
| WATCH | nonofficial_stooq | NA | WATCH | SAME | 2 | NASDAQCOM | OK | 3.14 | 2026-01-16 | 23515.39 | -0.062176 | WARN:nonofficial_stooq(^ndq);derived_1d_pct | https://stooq.com/q/d/l/?s=^ndq&i=d | 2026-01-18T07:40:37Z |
| WATCH | fallback_chicagofed_nfci | NA | WATCH | SAME | 2 | NFCINONFINLEVERAGE | OK | 3.14 | 2026-01-09 | -0.510021 | NA | WARN:fallback_chicagofed_nfci(nonfinancial leverage) | https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv | 2026-01-18T07:40:37Z |
| WATCH | nonofficial_stooq | NA | WATCH | SAME | 2 | SP500 | OK | 3.14 | 2026-01-16 | 6940.01 | -0.064224 | WARN:nonofficial_stooq(^spx);derived_1d_pct | https://stooq.com/q/d/l/?s=^spx&i=d | 2026-01-18T07:40:37Z |
| WATCH | derived_from_treasury | NA | WATCH | SAME | 2 | T10Y2Y | OK | 3.14 | 2026-01-16 | 0.65 | NA | WARN:derived_from_treasury(10Y-2Y) | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-18T07:40:37Z |
| WATCH | derived_from_treasury | NA | WATCH | SAME | 2 | T10Y3M | OK | 3.14 | 2026-01-16 | 0.57 | NA | WARN:derived_from_treasury(10Y-3M) | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-18T07:40:37Z |
| WATCH | fallback_treasury_csv | NA | WATCH | SAME | 2 | UST3M | OK | 3.14 | 2026-01-16 | 3.67 | NA | WARN:fallback_treasury_csv | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202601?_format=csv&field_tdr_date_value_month=202601&page=&type=daily_treasury_yield_curve | 2026-01-18T07:40:37Z |
| WATCH | fallback_cboe_vix | NA | WATCH | SAME | 2 | VIXCLS | OK | 3.14 | 2026-01-16 | 15.86 | NA | WARN:fallback_cboe_vix | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv | 2026-01-18T07:40:37Z |
