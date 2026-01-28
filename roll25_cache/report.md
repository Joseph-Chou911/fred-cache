# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-28T08:48:13Z`
- generated_at_local: `2026-01-28T16:48:13.782136+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-28`
- UsedDateStatus: `OK_TODAY`
- RunDayTag: `WEEKDAY`
- summary: UsedDate=2026-01-28：Mode=MISSING_OHLC；freshness_ok=True

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `850393655366`
- close: `NA`
- pct_change: `NA`
- amplitude_pct: `NA`
- volume_multiplier_20: `1.113129`

## 3) Market Behavior Signals (from latest_report.json)
- DownDay: `false`
- VolumeAmplified: `false`
- VolAmplified: `false`
- NewLow_N: `NA`
- ConsecutiveBreak: `NA`

## 4) Data Quality Flags (from latest_report.json)
- OhlcMissing: `true`
- freshness_ok: `true`
- ohlc_status: `MISSING`
- mode: `MISSING_OHLC`

## 5) Z/P Table (market_cache-like; computed from roll25.json)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 850393655366 | 1.789046 | 94.166667 | 2.859864 | 98.611111 | 0.349602 | 70.833333 | 4.010387 | OK |
| CLOSE | NA | NA | NA | NA | NA | 0.564419 | 77.5 | NA | DOWNGRADED |
| PCT_CHANGE_CLOSE | NA | NA | NA | NA | NA | NA | NA | NA | DOWNGRADED |
| AMPLITUDE_PCT | NA | NA | NA | NA | NA | NA | NA | NA | DOWNGRADED |
| VOL_MULTIPLIER_20 | 1.113129 | 0.352216 | 69.166667 | 0.507123 | 75.595238 | NA | NA | NA | OK |

## 6) Audit Notes
- This report is computed from local files only (no external fetch).
- Date ordering uses parsed dates (not string sort).
- All VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to UsedDate.
- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).
- ret1% is STRICT adjacency at UsedDate (UsedDate vs next older row); if missing => NA (no jumping).
- zΔ60/pΔ60 are computed on delta series (today - prev) over last 60 deltas (anchored), not (z_today - z_prev).
- AMPLITUDE mismatch threshold: 0.01 (abs(latest - roll25@UsedDate) > threshold => DOWNGRADED).
- CLOSE pct mismatch threshold: 0.05 (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).
- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=1 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=MISSING_OHLC | OHLC=MISSING | UsedDate=2026-01-28 | UsedDminus1=2026-01-27
RunDayTag=WEEKDAY | UsedDateStatus=OK_TODAY
freshness_ok=True | freshness_age_days=0
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
