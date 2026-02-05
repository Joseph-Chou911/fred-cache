# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-05T00:08:35Z`
- generated_at_local: `2026-02-05T08:08:35.931055+08:00`
- timezone: `Asia/Taipei`
- UsedDate: `2026-02-04`
- UsedDateStatus: `DATA_NOT_UPDATED`
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-04：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `704644032693`
- close: `32289.81`
- pct_change: `0.293365`
- amplitude_pct: `1.359575`
- volume_multiplier_20: `0.890968`

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
| TURNOVER_TWD | 704644032693 | 0.499378 | 67.5 | 1.646912 | 91.865079 | -1.407865 | 7.5 | -14.232445 | OK |
| CLOSE | 32289.81 | 1.639081 | 94.166667 | 2.265072 | 98.611111 | 0.060314 | 45.833333 | 0.293365 | OK |
| PCT_CHANGE_CLOSE | 0.293365 | 0.033843 | 45.833333 | 0.102705 | 53.373016 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.359575 | 0.366878 | 67.5 | 0.207798 | 73.214286 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.890968 | -0.958192 | 19.166667 | -0.786966 | 18.452381 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list (daily % returns): `20,60` (population std; ddof=0)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `32289.81` (prefer latest_report.Close else roll25@UsedDate)

- sigma20_daily_%: `1.029479` (reason: `OK`)
- sigma60_daily_%: `1.197262` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.197262 | 3.786074 | 31067.29377 | 30278.770802 | 29893.67819 | 29844.777541 | 33512.32623 | 34300.849198 | 34685.94181 | 34734.842459 | OK |  |
| 12 | 1.197262 | 4.147437 | 30950.610568 | 30086.826935 | 29664.979114 | 29611.411136 | 33629.009432 | 34492.793065 | 34914.640886 | 34968.208864 | OK |  |
| 15 | 1.197262 | 4.636975 | 30792.539518 | 29826.800056 | 29355.159854 | 29295.269035 | 33787.080482 | 34752.819944 | 35224.460146 | 35284.350965 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `1.795893` (policy: max(sigma60,sigma20) * stress_mult)
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.795893 | 5.679112 | 30456.035656 | 29273.251203 | 28695.612285 | 28622.261311 | 34123.584344 | 35306.368797 | 35884.007715 | 35957.358689 | OK | stress_mult=1.5; sigma_stress=max(sigma60,sigma20)*mult |
| 12 | 1.795893 | 6.221155 | 30281.010852 | 28985.335402 | 28352.563671 | 28272.211705 | 34298.609148 | 35594.284598 | 36227.056329 | 36307.408295 | OK | stress_mult=1.5; sigma_stress=max(sigma60,sigma20)*mult |
| 15 | 1.795893 | 6.955463 | 30043.904276 | 28595.295085 | 27887.834782 | 27797.998553 | 34535.715724 | 35984.324915 | 36691.785218 | 36781.621447 | OK | stress_mult=1.5; sigma_stress=max(sigma60,sigma20)*mult |

- Interpretation notes:
  - These bands assume iid + normal approximation of daily returns; this is NOT a guarantee and will understate tail risk in regime shifts.
  - 1-tail 95% uses z=1.645 (one-sided yardstick). 2-tail 95% uses z=1.96 (central 95% interval yardstick).
  - Stress bands are heuristic; they are meant to be conservative-ish, not statistically exact.

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
- VOL_BANDS: sigma computed from anchored DAILY % returns; horizon scaling uses sqrt(T).

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-04 | UsedDminus1=2026-02-03
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
