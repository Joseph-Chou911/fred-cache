# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-01-31T04:49:45Z`
- generated_at_local: `2026-01-31T12:49:45.764101+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-01-30`
- UsedDateStatus: `OK_LATEST`
- RunDayTag: `WEEKEND`
- summary: 今日為週末；UsedDate=2026-01-30：Mode=FULL；freshness_ok=True

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `941320964545`
- close: `32063.75`
- pct_change: `-1.452287`
- amplitude_pct: `1.692142`
- volume_multiplier_20: `1.179184`

## 3) Market Behavior Signals (from latest_report.json)
- DownDay: `true`
- VolumeAmplified: `false`
- VolAmplified: `false`
- NewLow_N: `0`
- ConsecutiveBreak: `2`

## 4) Data Quality Flags (from latest_report.json)
- OhlcMissing: `false`
- freshness_ok: `true`
- ohlc_status: `OK`
- mode: `FULL`

## 5) Z/P Table (market_cache-like; computed from roll25.json)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 941320964545 | 2.155248 | 97.5 | 3.311797 | 99.404762 | -0.288839 | 40.833333 | -1.91018 | OK |
| CLOSE | 32063.75 | 1.720001 | 92.5 | 2.29406 | 98.214286 | -1.625331 | 7.5 | -1.452287 | OK |
| PCT_CHANGE_CLOSE | -1.452287 | -1.449896 | 7.5 | -1.052663 | 8.531746 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.692142 | 1.272775 | 85.833333 | 0.693741 | 88.293651 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 1.179184 | 0.610222 | 72.5 | 0.777912 | 83.134921 | NA | NA | NA | OK |

## 6) Audit Notes
- This report is computed from local files only (no external fetch).
- Date ordering uses parsed dates (not string sort).
- All VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to UsedDate.
- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).
- ret1% is STRICT adjacency at UsedDate (UsedDate vs next older row); if missing => NA (no jumping).
- zΔ60/pΔ60 are computed on delta series (today - prev) over last 60 deltas (anchored), not (z_today - z_prev).
- AMPLITUDE derived policy: prefer prev_close (= close - change) as denominator when available; fallback to close.
- AMPLITUDE mismatch threshold: 0.01 (abs(latest - derived@UsedDate) > threshold => DOWNGRADED).
- CLOSE pct mismatch threshold: 0.05 (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).
- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-30 | UsedDminus1=2026-01-29
RunDayTag=WEEKEND | UsedDateStatus=OK_LATEST
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
