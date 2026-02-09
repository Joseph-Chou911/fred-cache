# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-09T23:32:59Z`
- generated_at_local: `2026-02-10T07:32:59.117302+08:00`
- report_date_local: `2026-02-10`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-02-09` (latest available)
- data_age_days: `1` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-09：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `653957736705`
- close: `32404.62`
- pct_change: `1.956082`
- amplitude_pct: `2.233401`
- volume_multiplier_20: `0.827958`

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

## 5) Z/P Table (market_cache-like; computed from roll25 points)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 653957736705 | 0.14162 | 54.166667 | 1.275856 | 88.293651 | -0.546857 | 29.166667 | -6.619244 | OK |
| CLOSE | 32404.62 | 1.534014 | 95.833333 | 2.210117 | 99.007937 | 1.526127 | 95.833333 | 1.956082 | OK |
| PCT_CHANGE_CLOSE | 1.956082 | 1.375456 | 95.833333 | 1.20244 | 94.246032 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 2.233401 | 2.136592 | 99.166667 | 1.418077 | 95.039683 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.827958 | -1.133389 | 5.833333 | -1.028688 | 11.309524 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `32404.62` (source: latest_report.Close)

- sigma20_daily_%: `1.148599` (reason: `OK`)
- sigma60_daily_%: `1.235144` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.235144 | 3.905869 | 31138.937943 | 30322.573017 | 29923.883169 | 29873.255887 | 33670.302057 | 34486.666983 | 34885.356831 | 34935.984113 | OK |  |
| 12 | 1.235144 | 4.278665 | 31018.134774 | 30123.851803 | 29687.108957 | 29631.649548 | 33791.105226 | 34685.388197 | 35122.131043 | 35177.590452 | OK |  |
| 15 | 1.235144 | 4.783693 | 30854.482392 | 29854.643636 | 29366.350289 | 29304.344785 | 33954.757608 | 34954.596364 | 35442.889711 | 35504.895215 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.235144 | 3.905869 | ±3.905869 | ±6.425155 | ±7.655504 | ±7.811738 | OK |  |
| 12 | 1.235144 | 4.278665 | ±4.278665 | ±7.038404 | ±8.386184 | ±8.557331 | OK |  |
| 15 | 1.235144 | 4.783693 | ±4.783693 | ±7.869175 | ±9.376039 | ±9.567386 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `1.852716` (chosen_win=60; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.852716 | 5.858804 | 30506.096915 | 29281.549525 | 28683.514754 | 28607.57383 | 34303.143085 | 35527.690475 | 36125.725246 | 36201.66617 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.852716 | 6.417998 | 30324.892161 | 28983.467705 | 28328.353436 | 28245.164322 | 34484.347839 | 35825.772295 | 36480.886564 | 36564.075678 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.852716 | 7.17554 | 30079.413589 | 28579.655453 | 27847.215434 | 27754.207177 | 34729.826411 | 36229.584547 | 36962.024566 | 37055.032823 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.852716 | 5.858804 | ±5.858804 | ±9.637732 | ±11.483255 | ±11.717607 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.852716 | 6.417998 | ±6.417998 | ±10.557607 | ±12.579276 | ±12.835996 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.852716 | 7.17554 | ±7.17554 | ±11.803763 | ±14.064058 | ±14.35108 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

- Interpretation notes:
  - These bands assume iid + normal approximation of daily returns; this is NOT a guarantee and will understate tail risk in regime shifts.
  - 1-tail 95% uses z=1.645 (one-sided yardstick). 2-tail 95% uses z=1.96 (central 95% interval yardstick).
  - Stress bands are heuristic; they are meant to be conservative-ish, not statistically exact.

## 5.3) Roll25 Dynamic Risk Check (Rule A; log-return bands)
- Policy (fixed; audit-grade):
  - ret1_log_pct = 100 * ln(Close_t / Close_{t-1})  (STRICT adjacency at UsedDate)
  - sigma_log(win=60) computed from last 60 daily log returns anchored at UsedDate (ddof=0)
  - sigma_target_pct = max(sigma_log, abs(ret1_log_pct))  (Rule A)
  - Band(z) = AnchorClose * exp(- z * sigma_target_pct / 100)

### 5.3.a) Parameter Setup
- AnchorClose: `32404.62` (source: roll25@UsedDate.close)
- PrevClose(strict): `31782.92`
- ret1_log_pct(abs): `1.937197`
- sigma_log_60_daily_%: `1.235957` (reason: `OK`)
- sigma_target_daily_% (Rule A): `1.937197`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 31782.92 | Close >= 31782.92 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 31173.147648 | Close <  31173.147648 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.827958 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 32404.62 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
| Self Risk | NO_MARGIN | no leverage / no pledge forced-sell risk | PASS |
| Action | OPTIONAL_TINY_PROBE (全 PASS → 可考慮極小額試單；非必要) | any FAIL => CASH; all PASS => optional tiny probe; else observe | — |

## 6) Audit Notes
- This report is computed from local files only (no external fetch).
- SERIES DIRECTION: all series are NEWEST-FIRST (index 0 = latest).
- roll25 points are read from roll25.json; if empty, fallback to latest_report.cache_roll25 (still local).
- Date ordering uses parsed dates (not string sort).
- MM/DD dates (no year) are resolved by choosing year in {Y-1,Y,Y+1} closest to UsedDate (cross-year safe).
- Rows missing date field are counted and sampled as '<NO_DATE_FIELD>' (audit visibility; no silent drop).
- If MM/DD=02/29 cannot be resolved within {Y-1,Y,Y+1}, it is recorded as 'MMDD_0229_NO_LEAP_IN_WINDOW' in sort diag samples.
- All VALUE/ret1%/zΔ60/pΔ60 are ANCHORED to as_of_data_date (UsedDate).
- UsedDateStatus: `DATA_NOT_UPDATED` (kept for audit; not treated as daily alarm).
- z-score uses population std (ddof=0). Percentile is tie-aware (less + 0.5*equal).
- ret1% (in Z/P table) is STRICT adjacency at as_of_data_date (simple %).
- Dynamic Risk Check ret1 uses STRICT adjacency LOG return: 100*ln(Close_t/Close_{t-1}).
- zΔ60/pΔ60 are computed on delta series (today - prev) over last 60 deltas (anchored), not (z_today - z_prev).
- AMPLITUDE derived policy: prefer prev_close (= close - change) as denominator when available; fallback to close.
- AMPLITUDE mismatch threshold: 0.01 (abs(latest - derived@UsedDate) > threshold => DOWNGRADED).
- CLOSE pct mismatch threshold: 0.05 (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).
- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.
- VOL_BANDS: sigma computed from anchored DAILY % returns; horizon scaling uses sqrt(T).
- Band % Mapping tables (5.1.a/5.2.a) are display-only: they map sigma_T_% to ±% moves; they do NOT alter signals.
- VOL thresholds: pass_max=1 fail_min=1.3 (parameterized)
- Anchor clarity: level_anchor=32404.62 (for bands) vs anchor_close=32404.62 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=285 computed=270 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-09 | UsedDminus1=2026-02-06
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
