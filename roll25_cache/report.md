# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-03-12T23:21:19Z`
- generated_at_local: `2026-03-13T07:21:19.307997+08:00`
- report_date_local: `2026-03-13`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-03-12` (latest available)
- data_age_days: `1` (warn_if > 2)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-03-12：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `784007384475`
- close: `33581.86`
- pct_change: `-1.560436`
- amplitude_pct: `1.644008`
- volume_multiplier_20: `0.935388`

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
| TURNOVER_TWD | 784007384475 | 0.361191 | 62.5 | 1.593681 | 91.071429 | 0.818569 | 75.833333 | 13.061273 | OK |
| CLOSE | 33581.86 | 1.116512 | 82.5 | 2.021288 | 95.833333 | -1.261692 | 5.833333 | -1.560436 | OK |
| PCT_CHANGE_CLOSE | -1.560436 | -1.234185 | 7.5 | -1.065615 | 7.738095 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.644008 | 0.178936 | 59.166667 | 0.442226 | 80.753968 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.935388 | -0.735083 | 30.833333 | -0.49158 | 33.531746 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `33581.86` (source: latest_report.Close)

- sigma20_daily_%: `2.242332` (reason: `OK`)
- sigma60_daily_%: `1.529635` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.529635 | 4.837131 | 31957.46142 | 30909.724336 | 30398.038783 | 30333.06284 | 35206.25858 | 36253.995664 | 36765.681217 | 36830.65716 | OK |  |
| 12 | 1.529635 | 5.298812 | 31802.420511 | 30654.68204 | 30094.158601 | 30022.981021 | 35361.299489 | 36509.03796 | 37069.561399 | 37140.738979 | OK |  |
| 15 | 1.529635 | 5.924251 | 31592.38617 | 30309.17555 | 29682.491293 | 29602.91234 | 35571.33383 | 36854.54445 | 37481.228707 | 37560.80766 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.529635 | 4.837131 | ±4.837131 | ±7.957081 | ±9.480777 | ±9.674262 | OK |  |
| 12 | 1.529635 | 5.298812 | ±5.298812 | ±8.716545 | ±10.385671 | ±10.597623 | OK |  |
| 15 | 1.529635 | 5.924251 | ±5.924251 | ±9.745394 | ±11.611533 | ±11.848503 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `3.363498` (chosen_win=20; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 3.363498 | 10.636314 | 30009.987931 | 27706.130447 | 26580.990745 | 26438.115862 | 37153.732069 | 39457.589553 | 40582.729255 | 40725.604138 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 3.363498 | 11.651498 | 29669.070191 | 27145.320764 | 25912.791974 | 25756.280381 | 37494.649809 | 40018.399236 | 41250.928026 | 41407.439619 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 3.363498 | 13.026771 | 29207.228002 | 26385.590364 | 25007.581284 | 24832.596005 | 37956.491998 | 40778.129636 | 42156.138716 | 42331.123995 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 3.363498 | 10.636314 | ±10.636314 | ±17.496736 | ±20.847175 | ±21.272628 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 3.363498 | 11.651498 | ±11.651498 | ±19.166715 | ±22.836936 | ±23.302996 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 3.363498 | 13.026771 | ±13.026771 | ±21.429038 | ±25.532471 | ±26.053542 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

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
- AnchorClose: `33581.86` (source: roll25@UsedDate.close)
- PrevClose(strict): `34114.19`
- ret1_log_pct(abs): `1.572739`
- sigma_log_60_daily_%: `1.533126` (reason: `OK`)
- sigma_target_daily_% (Rule A): `1.572739`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 33057.836667 | Close >= 33057.836667 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 32541.990382 | Close <  32541.990382 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.935388 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 33581.86 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- Anchor clarity: level_anchor=33581.86 (for bands) vs anchor_close=33581.86 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=300 computed=285 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-03-12 | UsedDminus1=2026-03-11
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
