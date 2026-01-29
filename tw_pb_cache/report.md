# TW PB Sidecar Report (TAIEX P/B, DAILY)


## 1) Summary
- source_vendor: `statementdog` (THIRD_PARTY)
- source_url: `https://statementdog.com/taiex`
- fetch_status: `OK` / confidence: `OK` / dq_reason: `None`
- data_date: `2026-01-29`
- series_len_pbr: `2`

## 2) Latest
- date: `2026-01-29`
- PBR: `3.41`
- Close: `32536.27`

## 3) Stats (z / percentile)
- z60: `None` / p60: `None` / na_reason_60: `INSUFFICIENT_HISTORY:2/60`
- z252: `None` / p252: `None` / na_reason_252: `INSUFFICIENT_HISTORY:2/252`

## 4) Caveats
- This module stores a DAILY time series by appending the page's latest PBR into history.json on each successful run.
- z/p requires enough observations; NA is expected until the history grows (no guessing).
- Data source is third-party (StatementDog). Treat absolute thresholds cautiously; definition may differ from other vendors.
