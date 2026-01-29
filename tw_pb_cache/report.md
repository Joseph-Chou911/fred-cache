# TW PB Sidecar Report (TAIEX P/B, DAILY)

## 1) Summary
- source_vendor: `twse` (OFFICIAL)
- endpoint: `https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK`
- fetch_status: `OK` / confidence: `OK` / dq_reason: `None`
- data_date: `None` / latest_row_date: `2026-01-29`
- series_len_rows: `744` / series_len_pbr: `0`

## 2) Latest
- date: `2026-01-29`
- PBR: `None`
- Close: `32536.3`

## 3) Stats (z / percentile)
- z60: `None` / p60: `None` / na_reason_60: `INSUFFICIENT_HISTORY:0/60`
- z252: `None` / p252: `None` / na_reason_252: `INSUFFICIENT_HISTORY:0/252`

## 4) Caveats
- This module uses TWSE RWD monthly-query endpoint to assemble a DAILY trading-day series.
- If TWSE response schema changes (fields renamed), extraction may degrade to DOWNGRADED with empty_rows.
- No interpolation; NA is preserved.
