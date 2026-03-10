# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-03-10T23:02:58Z`
- generated_at_local: `2026-03-11T07:02:58.803753+08:00`
- report_date_local: `2026-03-11`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-03-10` (latest available)
- data_age_days: `1` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-03-10：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `728225719000`
- close: `32771.87`
- pct_change: `2.059923`
- amplitude_pct: `2.496043`
- volume_multiplier_20: `0.856809`

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
| TURNOVER_TWD | 728225719000 | 0.11438 | 54.166667 | 1.316534 | 88.690476 | -1.405926 | 5.833333 | -16.132472 | OK |
| CLOSE | 32771.87 | 0.844454 | 79.166667 | 1.872855 | 95.039683 | 1.235778 | 90.833333 | 2.059923 | OK |
| PCT_CHANGE_CLOSE | 2.059923 | 1.230143 | 92.5 | 1.204701 | 93.452381 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 2.496043 | 1.520303 | 94.166667 | 1.589745 | 93.849206 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.856809 | -1.12089 | 10.833333 | -0.93814 | 13.293651 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `32771.87` (source: latest_report.Close)

- sigma20_daily_%: `2.090434` (reason: `OK`)
- sigma60_daily_%: `1.431356` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.431356 | 4.526345 | 31288.502158 | 30331.7299 | 29864.46903 | 29805.134316 | 34255.237842 | 35212.0101 | 35679.27097 | 35738.605684 | OK |  |
| 12 | 1.431356 | 4.958362 | 31146.921944 | 30098.830447 | 29586.97181 | 29521.973887 | 34396.818056 | 35444.909553 | 35956.76819 | 36021.766113 | OK |  |
| 15 | 1.431356 | 5.543618 | 30955.122843 | 29783.320927 | 29211.045573 | 29138.375686 | 34588.617157 | 35760.419073 | 36332.694427 | 36405.364314 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.431356 | 4.526345 | ±4.526345 | ±7.445837 | ±8.871636 | ±9.05269 | OK |  |
| 12 | 1.431356 | 4.958362 | ±4.958362 | ±8.156506 | ±9.71839 | ±9.916725 | OK |  |
| 15 | 1.431356 | 5.543618 | ±5.543618 | ±9.119251 | ±10.865491 | ±11.087235 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `3.135651` (chosen_win=20; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 3.135651 | 9.915799 | 29522.277262 | 27426.289947 | 26402.668234 | 26272.684525 | 36021.462738 | 38117.450053 | 39141.071766 | 39271.055475 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 3.135651 | 10.862214 | 29212.11951 | 26916.080444 | 25794.759039 | 25652.36902 | 36331.62049 | 38627.659556 | 39748.980961 | 39891.37098 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 3.135651 | 12.144324 | 28791.947961 | 26224.898245 | 24971.222803 | 24812.025921 | 36751.792039 | 39318.841755 | 40572.517197 | 40731.714079 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 3.135651 | 9.915799 | ±9.915799 | ±16.311489 | ±19.434966 | ±19.831598 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 3.135651 | 10.862214 | ±10.862214 | ±17.868341 | ±21.289938 | ±21.724427 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 3.135651 | 12.144324 | ±12.144324 | ±19.977413 | ±23.802875 | ±24.288648 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

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
- AnchorClose: `32771.87` (source: roll25@UsedDate.close)
- PrevClose(strict): `32110.42`
- ret1_log_pct(abs): `2.038994`
- sigma_log_60_daily_%: `1.438128` (reason: `OK`)
- sigma_target_daily_% (Rule A): `2.038994`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 32110.42 | Close >= 32110.42 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 31462.320355 | Close <  31462.320355 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.856809 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 32771.87 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- zΔ60/pΔ60 are computed on the 1-day absolute change Δ = (today - prev) (strict adjacency), ranked vs last 60 such Δ’s (anchored at UsedDate); this is NOT (z_today - z_prev).
- AMPLITUDE derived policy: prefer prev_close (= close - change) as denominator when available; fallback to close.
- AMPLITUDE mismatch threshold: 0.01 (abs(latest - derived@UsedDate) > threshold => DOWNGRADED).
- CLOSE pct mismatch threshold: 0.05 (abs(latest_pct_change - computed_close_ret1%) > threshold => DOWNGRADED).
- PCT_CHANGE_CLOSE and VOL_MULTIPLIER_20 suppress ret1% and zΔ60/pΔ60 to avoid double-counting / misleading ratios.
- VOL_BANDS: sigma computed from anchored DAILY % returns; horizon scaling uses sqrt(T).
- Band % Mapping tables (5.1.a/5.2.a) are display-only: they map sigma_T_% to ±% moves; they do NOT alter signals.
- VOL thresholds: pass_max=1 fail_min=1.3 (parameterized)
- Anchor clarity: level_anchor=32771.87 (for bands) vs anchor_close=32771.87 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=298 computed=283 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-03-10 | UsedDminus1=2026-03-09
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
