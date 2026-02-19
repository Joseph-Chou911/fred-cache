# TW0050 BB(60,2) + ForwardMDD(20D) Report

- report_generated_at_utc: `2026-02-19T10:43:59Z`
- report_generated_at_local: `2026-02-19 18:43:59 +0800`

## 1) Core Stats (from stats_latest.json)

- stats.meta.run_ts_utc: `2026-02-19T10:43:31Z`
- stats.meta.stats_generated_at_utc: `N/A`
- stats.meta.stats_as_of_ts: `N/A`
- stats.meta.day_key_local: `N/A`

### Snapshot

- close: N/A
- bb.z: N/A
- bb.position_in_band: N/A

### Forward MDD (best-effort)

- min_entry_date: `2020-02-19`
- min_entry_price: 19.4179
- min_future_date: `2020-03-19`
- min_future_price: 14.4528
- forward_mdd_pct: N/A

## 2) Chip Overlay (TWSE T86 + TWT72U + Yuanta PCF)

- chip.meta.run_ts_utc: `2026-02-19T10:43:58.907Z`
- chip.meta.aligned_last_date: `20260219`
- chip.data_age_days (local): `0`
- dq.flags: `['ETF_UNITS_FETCH_FAILED']`

### Sources (for audit)

- T86: `https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999`
- TWT72U: `https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB`
- PCF: `https://www.yuantaetfs.com/tradeInfo/pcf/0050`

### ETF Units (PCF)

- trade_date: `None`
- posting_dt: `None`
- units_outstanding: N/A
- units_chg_1d: N/A (N/A)
- units.dq: `['ETF_UNITS_PCF_TRADE_DATE_NOT_FOUND', 'ETF_UNITS_PCF_POSTING_DATE_NOT_FOUND', 'ETF_UNITS_PCF_OUTSTANDING_NOT_FOUND', 'ETF_UNITS_PCF_NET_CHANGE_NOT_FOUND', 'ETF_UNITS_PCF_PARSE_ALL_MISSING']`

### Securities Lending (TWT72U)

- asof_date: `20260211`
- borrow_shares: 135,405,000
- borrow_shares_chg_1d: -9,446,000
- borrow_mv_ntd: 10453266000.0
- borrow_mv_ntd_chg_1d: -482984500.0
- borrow_ratio: N/A

### Institutional Net (T86) - Rolling Window Aggregate

- window_n: `5`
- days_used: `['20260211', '20260210', '20260209', '20260206', '20260205']`
- foreign_net_shares_sum: -14,398,187
- trust_net_shares_sum: 17,326,000
- dealer_net_shares_sum: -11,810,680
- total3_net_shares_sum: -8,882,867
