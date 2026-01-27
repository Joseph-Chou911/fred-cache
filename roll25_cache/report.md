# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-27T11:03:02Z`
- generated_at_local: `2026-01-27T19:03:02.130820+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-26`
- UsedDateStatus: `DATA_NOT_UPDATED`
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-01-26：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `747339306040`
- close: `32064.52`
- pct_change: `0.322294`
- amplitude_pct: `0.647310`
- volume_multiplier_20: `1.027252`

## 3) Market Behavior Signals (from latest_report.json)
- DownDay: `false`
- VolumeAmplified: `false`
- NewLow_N: `0`
- ConsecutiveBreak: `0`

## 4) Data Quality Flags (from latest_report.json)
- OhlcMissing: `false`
- freshness_ok: `true`
- freshness_age_days: `1`
- ohlc_status: `OK`
- mode: `FULL`

## 5) Z/P Table (market_cache-like; computed from roll25.json)
| series | value | z60 | p60 | z252 | p252 | zD60 | pD60 | ret1_pct | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 747339306040.000000 | 1.160229 | 79.167 | 2.221586 | 95.040 | 0.087570 | 60.833 | -8.686108 | OK |
| CLOSE | 32064.520000 | 2.182688 | 99.167 | 2.453498 | 99.802 | 0.877612 | 87.500 | 0.322294 | OK |
| PCT_CHANGE_CLOSE | 0.322294 | 0.091742 | 47.500 | 0.111997 | 53.373 | 0.279323 | 54.167 | -52.506298 | OK |
| AMPLITUDE_PCT | 0.647310 | -1.192265 | 2.500 | -0.780508 | 6.548 | -1.345826 | 10.833 | -41.167654 | OK |
| VOL_MULTIPLIER_20 | 1.027252 | -0.172992 | 49.167 | -0.016194 | 54.167 | -0.648484 | 30.833 | -10.589826 | OK |

## 6) Audit Notes
- This report is computed from local files only (no external fetch).
- z-score uses population std (ddof=0). Percentile is tie-aware.
- If insufficient points, corresponding stats remain NA (no guessing).

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
