# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-27T11:42:15Z`
- generated_at_local: `2026-01-27T19:42:15.745514+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-26`
- UsedDateStatus: `DATA_NOT_UPDATED`
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-01-26：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `747339306040`
- close: `32064.52`
- pct_change: `0.322294`
- amplitude_pct: `0.64731`
- volume_multiplier_20: `1.027252`

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
| TURNOVER_TWD | 747339306040 | 1.160229 | 79.166667 | 2.221586 | 95.039683 | -0.748666 | 25.833333 | -8.686108 | OK |
| CLOSE | 32064.52 | 2.182688 | 99.166667 | 2.453498 | 99.801587 | 0.091742 | 47.5 | 0.322294 | OK |
| PCT_CHANGE_CLOSE | 0.322294 | NA | NA | NA | NA | NA | NA | NA | DOWNGRADED |
| AMPLITUDE_PCT | 0.64731 | -1.18707 | 2.5 | -0.769002 | 6.547619 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 1.027252 | NA | NA | NA | NA | NA | NA | NA | DOWNGRADED |

## 6) Audit Notes
- This report is computed from local files only (no external fetch).
- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).
- AMPLITUDE_PCT value uses latest_report.json:numbers.AmplitudePct; stats use roll25.json series (amplitude_pct or derived from H/L/C).
- AMPLITUDE_PCT mismatch check: abs(latest - roll25_derived@UsedDate) > 0.01 => DQ note + AMPLITUDE row confidence=DOWNGRADED.
- ret1% and zΔ60/pΔ60 are only computed for TURNOVER_TWD and CLOSE; other series show NA to avoid misleading ratios.
- If insufficient points for any required full window, corresponding stats remain NA and confidence is DOWNGRADED (no guessing).

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-26 | UsedDminus1=2026-01-23
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
