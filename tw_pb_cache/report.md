# TW PB Sidecar Report (TAIEX P/B, DAILY)


## 1) Summary
- source_vendor: `statementdog` (THIRD_PARTY)
- source_url: `https://statementdog.com/taiex`
- fetch_status: `OK` / confidence: `OK` / dq_reason: `None`
- data_date: `2026-02-05`
- series_len_pbr: `7`

## 2) Latest
- date: `2026-02-05`
- PBR: `3.3300`
- Close: `31801.27`

## 3) Stats (z / percentile)
- z60: `None` / p60: `None` / na_reason_60: `INSUFFICIENT_HISTORY:7/60`
- z252: `None` / p252: `None` / na_reason_252: `INSUFFICIENT_HISTORY:7/252`

## 4) Historical Context (non-trigger)
- label: `HISTORICAL_ANCHOR (USER_PROVIDED_SCREENSHOT)`
- vendor: `MacroMicro`
- anchor_period: `2000-03`
- anchor_pb: `3.08`
- note: Context-only; NOT used for deterministic signals (triggers rely on p60/p252 once available).

### 4.1) Anchor comparison (context only)
- latest_pb: `3.3300`
- compare_to_anchor: `GT` (GT/LT/EQ/NA)
- delta_vs_anchor: `0.2500`
- ratio_vs_anchor: `1.0812`

## 5) Caveats
- History builds forward only (NO historical backfill; NO inferred dates).
- This module appends the page's latest PBR into history.json on each successful run.
- z/p requires enough observations; NA is expected until the history grows (no guessing).
- Data source is third-party. Treat absolute thresholds cautiously; definition may differ from other vendors.
- The historical anchor in section 4 is derived from a user-provided screenshot tooltip; it is included as context only.
