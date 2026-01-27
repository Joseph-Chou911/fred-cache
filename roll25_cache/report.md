# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-27T11:22:50Z`
- generated_at_local: `2026-01-27T19:22:50.310576+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-27`
- UsedDateStatus: `OK_TODAY`
- RunDayTag: `WEEKDAY`
- summary: UsedDate=2026-01-27：Mode=FULL；freshness_ok=True

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
- NewLow_N: `0.000000`
- ConsecutiveBreak: `0.000000`

## 4) Data Quality Flags (from latest_report.json)
- OhlcMissing: `false`
- freshness_ok: `true`
- ohlc_status: `OK`
- mode: `FULL`

## 5) Z/P Table (market_cache-like; computed from roll25.json)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 817604546187.000000 | 1.628202 | 90.833 | 2.682746 | 97.817 | 1.140482 | 85.833 | 9.402053 | OK |
| CLOSE | 32317.920000 | 2.206849 | 99.167 | 2.492607 | 99.802 | 1.388271 | 94.167 | 0.790282 | OK |
| PCT_CHANGE_CLOSE | 0.790282 | 0.480532 | 72.500 | 0.422510 | 70.833 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.038812 | NA | NA | NA | NA | NA | NA | NA | DOWNGRADED |
| VOL_MULTIPLIER_20 | 1.097543 | 0.199575 | 62.500 | 0.344562 | 70.437 | NA | NA | NA | OK |

## 6) Audit Notes
- This report is computed from local files only (no external fetch).
- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).
- ret1% and zΔ60/pΔ60 are only computed for TURNOVER_TWD and CLOSE; other series show NA to avoid misleading ratios.
- If insufficient points for any required window, corresponding stats remain NA and confidence is DOWNGRADED (no guessing).

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=24 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-27 | UsedDminus1=2026-01-26
RunDayTag=WEEKDAY | UsedDateStatus=OK_TODAY
freshness_ok=True | freshness_age_days=0
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
