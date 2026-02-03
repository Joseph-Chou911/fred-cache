# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-03T23:02:58Z`
- generated_at_local: `2026-02-04T07:02:58.080195+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-02-03`
- UsedDateStatus: `DATA_NOT_UPDATED`
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-03：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `821574120123`
- close: `32195.36`
- pct_change: `1.806632`
- amplitude_pct: `1.758694`
- volume_multiplier_20: `1.027315`

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
| TURNOVER_TWD | 821574120123 | 1.282752 | 87.5 | 2.439283 | 97.02381 | 0.530674 | 69.166667 | 6.501595 | OK |
| CLOSE | 32195.36 | 1.660192 | 94.166667 | 2.270149 | 98.611111 | 1.436555 | 94.166667 | 1.806632 | OK |
| PCT_CHANGE_CLOSE | 1.806632 | 1.28878 | 92.5 | 1.096509 | 92.65873 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.758694 | 1.300939 | 87.5 | 0.773629 | 89.087302 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 1.027315 | -0.226275 | 47.5 | -0.054148 | 52.97619 | NA | NA | NA | OK |

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
Mode=FULL | OHLC=OK | UsedDate=2026-02-03 | UsedDminus1=2026-02-02
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
