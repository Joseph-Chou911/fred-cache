# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-03-04T02:47:56Z`
- generated_at_local: `2026-03-04T10:47:56.492967+08:00`
- report_date_local: `2026-03-04`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-03-03` (latest available)
- data_age_days: `1` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-03-03：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `1113233319063`
- close: `34323.65`
- pct_change: `-2.198142`
- amplitude_pct: `2.681116`
- volume_multiplier_20: `1.305799`

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

## 5) Z/P Table (market_cache-like; computed from roll25 points)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 1113233319063 | 2.251656 | 97.5 | 3.595318 | 99.404762 | 1.02684 | 80.833333 | 9.781978 | OK |
| CLOSE | 34323.65 | 1.676621 | 92.5 | 2.398588 | 98.214286 | -2.564537 | 0.833333 | -2.198142 | OK |
| PCT_CHANGE_CLOSE | -2.198142 | -2.349712 | 0.833333 | -1.543844 | 2.97619 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 2.681116 | 2.490578 | 99.166667 | 1.959439 | 96.626984 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 1.305799 | 1.141193 | 85.833333 | 1.398118 | 91.865079 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `34323.65` (source: latest_report.Close)

- sigma20_daily_%: `1.393897` (reason: `OK`)
- sigma60_daily_%: `1.111007` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.111007 | 3.513314 | 33117.75257 | 32339.948727 | 31960.091036 | 31911.855139 | 35529.54743 | 36307.351273 | 36687.208964 | 36735.444861 | OK |  |
| 12 | 1.111007 | 3.848642 | 33002.655551 | 32150.614131 | 31734.500879 | 31681.661101 | 35644.644449 | 36496.685869 | 36912.799121 | 36965.638899 | OK |  |
| 15 | 1.111007 | 4.302913 | 32846.733307 | 31894.122039 | 31428.893281 | 31369.816613 | 35800.566693 | 36753.177961 | 37218.406719 | 37277.483387 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.111007 | 3.513314 | ±3.513314 | ±5.779401 | ±6.886094 | ±7.026627 | OK |  |
| 12 | 1.111007 | 3.848642 | ±3.848642 | ±6.331016 | ±7.543339 | ±7.697284 | OK |  |
| 15 | 1.111007 | 4.302913 | ±4.302913 | ±7.078291 | ±8.433709 | ±8.605825 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `2.090846` (chosen_win=20; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2.090846 | 6.611836 | 32054.226716 | 30590.448699 | 29875.580364 | 29784.803433 | 36593.073284 | 38056.851301 | 38771.719636 | 38862.496567 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 2.090846 | 7.242903 | 31837.62135 | 30234.132871 | 29451.033846 | 29351.5927 | 36809.67865 | 38413.167129 | 39196.266154 | 39295.7073 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 2.090846 | 8.097812 | 31544.185472 | 29751.430852 | 28875.899526 | 28764.720945 | 37103.114528 | 38895.869148 | 39771.400474 | 39882.579055 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2.090846 | 6.611836 | ±6.611836 | ±10.876469 | ±12.959198 | ±13.223671 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 2.090846 | 7.242903 | ±7.242903 | ±11.914575 | ±14.19609 | ±14.485806 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 2.090846 | 8.097812 | ±8.097812 | ±13.3209 | ±15.871711 | ±16.195623 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

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
- AnchorClose: `34323.65` (source: roll25@UsedDate.close)
- PrevClose(strict): `35095.09`
- ret1_log_pct(abs): `2.222661`
- sigma_log_60_daily_%: `1.107671` (reason: `OK`)
- sigma_target_daily_% (Rule A): `2.222661`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 33569.167349 | Close >= 33569.167349 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 32831.269299 | Close <  32831.269299 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 1.305799 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | FAIL |
| Price Structure | 34323.65 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
| Self Risk | NO_MARGIN | no leverage / no pledge forced-sell risk | PASS |
| Action | CASH / WAIT (任一 FAIL → 空手觀望) | any FAIL => CASH; all PASS => optional tiny probe; else observe | — |

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
- zΔ60/pΔ60 are computed on the 1-day absolute change Δ = (today - prev) (strict adjacency), ranked vs last 60 such Δ’s (anchored at UsedDate); this is NOT (z_today - z_prev).
- AMPLITUDE derived policy: prefer prev_close (= close - change) as denominator when available; fallback to close.
- AMPLITUDE mismatch threshold: 0.01 (abs(latest - derived@UsedDate) > threshold => DOWNGRADED).
- CLOSE pct mismatch threshold: 0.05 (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).
- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.
- VOL_BANDS: sigma computed from anchored DAILY % returns; horizon scaling uses sqrt(T).
- Band % Mapping tables (5.1.a/5.2.a) are display-only: they map sigma_T_% to ±% moves; they do NOT alter signals.
- VOL thresholds: pass_max=1 fail_min=1.3 (parameterized)
- Anchor clarity: level_anchor=34323.65 (for bands) vs anchor_close=34323.65 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=293 computed=278 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-03-03 | UsedDminus1=2026-03-02
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
