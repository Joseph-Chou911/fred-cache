# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-29T04:55:53Z`
- generated_at_local: `2026-01-29T12:55:53.708713+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-28`
- UsedDateStatus: `DATA_NOT_UPDATED`
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-01-28：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `853922428449`
- close: `32803.82`
- pct_change: `1.5035`
- amplitude_pct: `1.305963`
- volume_multiplier_20: `1.11749`

## 3) Market Behavior Signals (from latest_report.json)
- DownDay: `false`
- VolumeAmplified: `false`
- VolAmplified: `false`
- NewLow_N: `0`
- ConsecutiveBreak: `0`

## 4) Data Quality Flags (from latest_report.json)
- OhlcMissing: `false`
- freshness_ok: `true`
- ohlc_status: `OK`
- mode: `FULL`

## 5) Z/P Table (market_cache-like; computed from roll25.json)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 853922428449 | 1.81283 | 95.833333 | 2.883827 | 99.007937 | 0.39235 | 70.833333 | 4.441986 | OK |
| CLOSE | 32803.82 | 2.345237 | 99.166667 | 2.599967 | 99.801587 | 1.23675 | 90.833333 | 1.5035 | OK |
| PCT_CHANGE_CLOSE | 1.5035 | 1.067858 | 85.833333 | 0.886156 | 87.896825 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.305963 | 0.308744 | 67.5 | 0.120019 | 68.452381 | NA | NA | NA | DOWNGRADED |
| VOL_MULTIPLIER_20 | 1.11749 | 0.374962 | 70.833333 | 0.530204 | 76.785714 | NA | NA | NA | OK |

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
- DQ_NOTES:
  - AMPLITUDE_PCT mismatch: abs(latest_report.AmplitudePct - roll25@UsedDate) = 0.019345 > 0.01

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-28 | UsedDminus1=2026-01-27
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
