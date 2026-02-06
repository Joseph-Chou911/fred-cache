# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-06T14:28:19Z`
- generated_at_local: `2026-02-06T22:28:19.731820+08:00`
- report_date_local: `2026-02-06`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-02-05` (latest available)
- data_age_days: `1` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-05：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `715168705076`
- close: `31801.27`
- pct_change: `-1.512985`
- amplitude_pct: `1.463496`
- volume_multiplier_20: `0.906804`

## 3) Market Behavior Signals (from latest_report.json)
- DownDay: `true`
- VolumeAmplified: `false`
- VolAmplified: `false`
- NewLow_N: `0`
- ConsecutiveBreak: `1`

## 4) Data Quality Flags (from latest_report.json)
- OhlcMissing: `false`
- freshness_ok: `true`
- ohlc_status: `OK`
- mode: `FULL`

## 5) Z/P Table (market_cache-like; computed from roll25 points)
| series | value | z60 | p60 | z252 | p252 | zΔ60 | pΔ60 | ret1% | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TURNOVER_TWD | 715168705076 | 0.552977 | 67.5 | 1.702234 | 92.261905 | 0.098376 | 62.5 | 1.493615 | OK |
| CLOSE | 31801.27 | 1.33172 | 85.833333 | 2.092021 | 96.626984 | -1.580723 | 7.5 | -1.512985 | OK |
| PCT_CHANGE_CLOSE | -1.512985 | -1.43501 | 7.5 | -1.101926 | 6.547619 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.463496 | 0.60609 | 72.5 | 0.353104 | 80.753968 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.906804 | -0.828085 | 25.833333 | -0.668425 | 24.404762 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `31801.27` (source: latest_report.Close)

- sigma20_daily_%: `1.097921` (reason: `OK`)
- sigma60_daily_%: `1.216487` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.216487 | 3.846871 | 30577.916123 | 29788.852872 | 29403.496401 | 29354.562246 | 33024.623877 | 33813.687128 | 34199.043599 | 34247.977754 | OK |  |
| 12 | 1.216487 | 4.214036 | 30461.152971 | 29596.777488 | 29174.640624 | 29121.035943 | 33141.387029 | 34005.762512 | 34427.899376 | 34481.504057 | OK |  |
| 15 | 1.216487 | 4.711436 | 30302.973613 | 29336.572444 | 28864.609082 | 28804.677226 | 33299.566387 | 34265.967556 | 34737.930918 | 34797.862774 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.216487 | 3.846871 | ±3.846871 | ±6.328103 | ±7.539867 | ±7.693742 | OK |  |
| 12 | 1.216487 | 4.214036 | ±4.214036 | ±6.93209 | ±8.259511 | ±8.428072 | OK |  |
| 15 | 1.216487 | 4.711436 | ±4.711436 | ±7.750312 | ±9.234414 | ±9.422871 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `1.824731` (chosen_win=60; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.824731 | 5.770307 | 29966.239184 | 28782.644308 | 28204.609601 | 28131.208369 | 33636.300816 | 34819.895692 | 35397.930399 | 35471.331631 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.824731 | 6.321054 | 29791.094457 | 28494.531232 | 27861.325936 | 27780.918914 | 33811.445543 | 35108.008768 | 35741.214064 | 35821.621086 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.824731 | 7.067154 | 29553.82542 | 28104.223665 | 27396.278623 | 27306.380839 | 34048.71458 | 35498.316335 | 36206.261377 | 36296.159161 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.824731 | 5.770307 | ±5.770307 | ±9.492155 | ±11.309801 | ±11.540613 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.824731 | 6.321054 | ±6.321054 | ±10.398134 | ±12.389266 | ±12.642109 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.824731 | 7.067154 | ±7.067154 | ±11.625468 | ±13.851621 | ±14.134307 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

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
- AnchorClose: `31801.27` (source: roll25@UsedDate.close)
- PrevClose(strict): `32289.81`
- ret1_log_pct(abs): `1.524547`
- sigma_log_60_daily_%: `1.21759` (reason: `OK`)
- sigma_target_daily_% (Rule A): `1.524547`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 31320.121537 | Close >= 31320.121537 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 30846.252779 | Close <  30846.252779 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.906804 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 31801.27 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- Anchor clarity: level_anchor=31801.27 (for bands) vs anchor_close=31801.27 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=283 computed=268 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-05 | UsedDminus1=2026-02-04
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
```
