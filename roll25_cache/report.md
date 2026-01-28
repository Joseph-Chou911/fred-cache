# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-28T11:44:06Z`
- generated_at_local: `2026-01-28T19:44:06.380139+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-27`
- UsedDateStatus: `DATA_NOT_UPDATED`
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-01-27：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `817604546187`
- close: `32317.92`
- pct_change: `0.790282`
- amplitude_pct: `1.038812`
- volume_multiplier_20: `1.097543`

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
| TURNOVER_TWD | 817604546187 | 1.628202 | 90.833333 | 2.682746 | 97.81746 | 0.818931 | 74.166667 | 9.402053 | OK |
| CLOSE | 32317.92 | 2.206849 | 99.166667 | 2.492607 | 99.801587 | 0.564419 | 77.5 | 0.790282 | OK |
| PCT_CHANGE_CLOSE | 0.790282 | 0.480532 | 72.5 | 0.42251 | 70.833333 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.038812 | -0.289286 | 47.5 | -0.234214 | 50.198413 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 1.097543 | 0.271798 | 69.166667 | 0.425788 | 73.611111 | NA | NA | NA | OK |

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
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-27 | UsedDminus1=2026-01-26
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
