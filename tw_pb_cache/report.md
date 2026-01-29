# TW PB Sidecar Report (TAIEX P/B, MONTHLY)

## 1) Summary
- source_vendor: `wantgoo` (THIRD_PARTY)
- source_url: `https://www.wantgoo.com/index/0000/price-book-river`
- fetch_status: `DOWNGRADED` / confidence: `DOWNGRADED` / dq_reason: `http_403`
- freq: `MONTHLY`
- period_ym: `None` / data_date: `None`
- series_len: `0`

## 2) Latest (from monthly table)
- PBR: `None`
- Monthly Close: `None`

## 3) Stats (z / percentile)
- z60: `None` / p60: `None` / na_reason_60: `INSUFFICIENT_HISTORY:0/60`
- z252: `None` / p252: `None` / na_reason_252: `INSUFFICIENT_HISTORY:0/252`

## 4) Caveats
- This module uses the MONTHLY river table series for stats; intraday values are not used for z/p.
- z252/p252 will remain NA until >=252 monthly observations exist (likely unavailable with current public table).
