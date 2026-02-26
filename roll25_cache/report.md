# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-26T19:06:15Z`
- generated_at_local: `2026-02-27T03:06:15.291998+08:00`
- report_date_local: `2026-02-27`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-02-25` (latest available)
- data_age_days: `2` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-25：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `1020570870136`
- close: `35413.07`
- pct_change: `2.052545`
- amplitude_pct: `2.213867`
- volume_multiplier_20: `1.257709`

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
| TURNOVER_TWD | 1020570870136 | 2.20389 | 99.166667 | 3.394675 | 99.801587 | 1.722871 | 94.166667 | 18.421944 | OK |
| CLOSE | 35413.07 | 2.433156 | 99.166667 | 2.829964 | 99.801587 | 1.625478 | 95.833333 | 2.052545 | OK |
| PCT_CHANGE_CLOSE | 2.052545 | 1.377699 | 94.166667 | 1.229584 | 93.849206 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 2.213867 | 1.819431 | 95.833333 | 1.346132 | 94.246032 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 1.257709 | 0.978727 | 82.5 | 1.157972 | 88.690476 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `35413.07` (source: latest_report.Close)

- sigma20_daily_%: `1.325909` (reason: `OK`)
- sigma60_daily_%: `1.174979` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.174979 | 3.715608 | 34097.258964 | 33248.560846 | 32834.080369 | 32781.447928 | 36728.881036 | 37577.579154 | 37992.059631 | 38044.692072 | OK |  |
| 12 | 1.174979 | 4.070245 | 33971.671228 | 33041.96902 | 32587.928407 | 32530.272456 | 36854.468772 | 37784.17098 | 38238.211593 | 38295.867544 | OK |  |
| 15 | 1.174979 | 4.550672 | 33801.537182 | 32762.098514 | 32254.465676 | 32190.004364 | 37024.602818 | 38064.041486 | 38571.674324 | 38636.135636 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.174979 | 3.715608 | ±3.715608 | ±6.112176 | ±7.282593 | ±7.431217 | OK |  |
| 12 | 1.174979 | 4.070245 | ±4.070245 | ±6.695553 | ±7.977681 | ±8.14049 | OK |  |
| 15 | 1.174979 | 4.550672 | ±4.550672 | ±7.485856 | ±8.919318 | ±9.101345 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `1.988864` (chosen_win=20; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.988864 | 6.28934 | 33185.821683 | 31749.246519 | 31047.6633 | 30958.573367 | 37640.318317 | 39076.893481 | 39778.4767 | 39867.566633 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 1.988864 | 6.889627 | 32973.241712 | 31399.552466 | 30631.006555 | 30533.413423 | 37852.898288 | 39426.587534 | 40195.133445 | 40292.726577 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 1.988864 | 7.702837 | 32685.259047 | 30925.820982 | 30066.560532 | 29957.448094 | 38140.880953 | 39900.319018 | 40759.579468 | 40868.691906 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.988864 | 6.28934 | ±6.28934 | ±10.345964 | ±12.327106 | ±12.57868 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 1.988864 | 6.889627 | ±6.889627 | ±11.333436 | ±13.503668 | ±13.779253 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 1.988864 | 7.702837 | ±7.702837 | ±12.671166 | ±15.09756 | ±15.405673 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

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
- AnchorClose: `35413.07` (source: roll25@UsedDate.close)
- PrevClose(strict): `34700.82`
- ret1_log_pct(abs): `2.031764`
- sigma_log_60_daily_%: `1.174648` (reason: `OK`)
- sigma_target_daily_% (Rule A): `2.031764`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 34700.82 | Close >= 34700.82 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 34002.895221 | Close <  34002.895221 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 1.257709 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | NOTE |
| Price Structure | 35413.07 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
| Self Risk | NO_MARGIN | no leverage / no pledge forced-sell risk | PASS |
| Action | OBSERVE (NOTE 狀態：觀察；不加碼) | any FAIL => CASH; all PASS => optional tiny probe; else observe | — |

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
- Anchor clarity: level_anchor=35413.07 (for bands) vs anchor_close=35413.07 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=290 computed=275 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-25 | UsedDminus1=2026-02-24
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=2
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
