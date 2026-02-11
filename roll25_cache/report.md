# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-11T10:04:46Z`
- generated_at_local: `2026-02-11T18:04:46.303703+08:00`
- report_date_local: `2026-02-11`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-02-10` (latest available)
- data_age_days: `1` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-10：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `678490714672`
- close: `33072.97`
- pct_change: `2.062515`
- amplitude_pct: `1.954228`
- volume_multiplier_20: `0.86288`

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
| TURNOVER_TWD | 678490714672 | 0.294777 | 59.166667 | 1.422938 | 89.880952 | 0.279873 | 64.166667 | 3.751462 | OK |
| CLOSE | 33072.97 | 1.791279 | 99.166667 | 2.366664 | 99.801587 | 1.602609 | 95.833333 | 2.062515 | OK |
| PCT_CHANGE_CLOSE | 2.062515 | 1.419276 | 95.833333 | 1.265673 | 94.642857 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.954228 | 1.495731 | 87.5 | 1.018967 | 91.071429 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.86288 | -0.963981 | 14.166667 | -0.878876 | 14.484127 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `33072.97` (source: latest_report.Close)

- sigma20_daily_%: `1.21124` (reason: `OK`)
- sigma60_daily_%: `1.226482` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.226482 | 3.878476 | 31790.242902 | 30962.883924 | 30558.824888 | 30507.515804 | 34355.697098 | 35183.056076 | 35587.115112 | 35638.424196 | OK |  |
| 12 | 1.226482 | 4.248657 | 31667.812867 | 30761.486516 | 30318.862018 | 30262.655733 | 34478.127133 | 35384.453484 | 35827.077982 | 35883.284267 | OK |  |
| 15 | 1.226482 | 4.750143 | 31501.956565 | 30488.6529 | 29993.783668 | 29930.943131 | 34643.983435 | 35657.2871 | 36152.156332 | 36214.996869 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.226482 | 3.878476 | ±3.878476 | ±6.380092 | ±7.601812 | ±7.756951 | OK |  |
| 12 | 1.226482 | 4.248657 | ±4.248657 | ±6.989041 | ±8.327368 | ±8.497314 | OK |  |
| 15 | 1.226482 | 4.750143 | ±4.750143 | ±7.813986 | ±9.310281 | ±9.500286 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `1.839723` (chosen_win=60; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.839723 | 5.817714 | 31148.879353 | 29907.840886 | 29301.752332 | 29224.788706 | 34997.060647 | 36238.099114 | 36844.187668 | 36921.151294 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.839723 | 6.372986 | 30965.2343 | 29605.744773 | 28941.808028 | 28857.4986 | 35180.7057 | 36540.195227 | 37204.131972 | 37288.4414 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.839723 | 7.125215 | 30716.449848 | 29196.49435 | 28454.190502 | 28359.929696 | 35429.490152 | 36949.44565 | 37691.749498 | 37786.010304 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.839723 | 5.817714 | ±5.817714 | ±9.570139 | ±11.402718 | ±11.635427 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.839723 | 6.372986 | ±6.372986 | ±10.483562 | ±12.491052 | ±12.745972 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.839723 | 7.125215 | ±7.125215 | ±11.720978 | ±13.965421 | ±14.25043 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

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
- AnchorClose: `33072.97` (source: roll25@UsedDate.close)
- PrevClose(strict): `32404.62`
- ret1_log_pct(abs): `2.041533`
- sigma_log_60_daily_%: `1.226741` (reason: `OK`)
- sigma_target_daily_% (Rule A): `2.041533`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 32404.62 | Close >= 32404.62 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 31749.776248 | Close <  31749.776248 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.86288 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 33072.97 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- Anchor clarity: level_anchor=33072.97 (for bands) vs anchor_close=33072.97 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=286 computed=271 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-10 | UsedDminus1=2026-02-09
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
