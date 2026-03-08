# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-03-08T02:54:07Z`
- generated_at_local: `2026-03-08T10:54:07.291690+08:00`
- report_date_local: `2026-03-08`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-03-06` (latest available)
- data_age_days: `2` (warn_if > 2)
- RunDayTag: `WEEKEND`
- summary: 今日為週末；UsedDate=2026-03-06：Mode=FULL；freshness_ok=True

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `655472934511`
- close: `33599.54`
- pct_change: `-0.217979`
- amplitude_pct: `1.505571`
- volume_multiplier_20: `0.761487`

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
| TURNOVER_TWD | 655472934511 | -0.204889 | 40.833333 | 0.950264 | 84.325397 | -1.449969 | 5.833333 | -17.399462 | OK |
| CLOSE | 33599.54 | 1.248651 | 85.833333 | 2.124448 | 96.626984 | -0.417294 | 29.166667 | -0.217979 | OK |
| PCT_CHANGE_CLOSE | -0.217979 | -0.429707 | 30.833333 | -0.238506 | 35.515873 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.505571 | 0.133311 | 59.166667 | 0.301143 | 77.97619 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.761487 | -1.518594 | 2.5 | -1.383889 | 5.357143 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `33599.54` (source: latest_report.Close)

- sigma20_daily_%: `1.811277` (reason: `OK`)
- sigma60_daily_%: `1.287041` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.287041 | 4.069979 | 32232.045629 | 31350.01176 | 30919.251033 | 30864.551258 | 34967.034371 | 35849.06824 | 36279.828967 | 36334.528742 | OK |  |
| 12 | 1.287041 | 4.458439 | 32101.524972 | 31135.305278 | 30663.430544 | 30603.509943 | 35097.555028 | 36063.774722 | 36535.649456 | 36595.570057 | OK |  |
| 15 | 1.287041 | 4.984686 | 31924.708282 | 30844.441825 | 30316.869834 | 30249.876565 | 35274.371718 | 36354.638175 | 36882.210166 | 36949.203435 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.287041 | 4.069979 | ±4.069979 | ±6.695116 | ±7.97716 | ±8.139959 | OK |  |
| 12 | 1.287041 | 4.458439 | ±4.458439 | ±7.334132 | ±8.738541 | ±8.916878 | OK |  |
| 15 | 1.287041 | 4.984686 | ±4.984686 | ±8.199809 | ±9.769985 | ±9.969373 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `2.716915` (chosen_win=20; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2.716915 | 8.59164 | 30712.788496 | 28850.833775 | 27941.507051 | 27826.036991 | 36486.291504 | 38348.246225 | 39257.572949 | 39373.043009 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 2.716915 | 9.41167 | 30437.262166 | 28397.592963 | 27401.475446 | 27274.984332 | 36761.817834 | 38801.487037 | 39797.604554 | 39924.095668 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 2.716915 | 10.522567 | 30064.0059 | 27783.586405 | 26669.893164 | 26528.4718 | 37135.0741 | 39415.493595 | 40529.186836 | 40670.6082 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2.716915 | 8.59164 | ±8.59164 | ±14.133248 | ±16.839614 | ±17.18328 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 2.716915 | 9.41167 | ±9.41167 | ±15.482197 | ±18.446873 | ±18.82334 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 2.716915 | 10.522567 | ±10.522567 | ±17.309623 | ±20.624231 | ±21.045134 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

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
- AnchorClose: `33599.54` (source: roll25@UsedDate.close)
- PrevClose(strict): `33672.94`
- ret1_log_pct(abs): `0.218217`
- sigma_log_60_daily_%: `1.289126` (reason: `OK`)
- sigma_target_daily_% (Rule A): `1.289126`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 33169.179549 | Close >= 33169.179549 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 32744.331379 | Close <  32744.331379 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.761487 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 33599.54 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- UsedDateStatus: `OK_LATEST` (kept for audit; not treated as daily alarm).
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
- Anchor clarity: level_anchor=33599.54 (for bands) vs anchor_close=33599.54 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=296 computed=281 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-03-06 | UsedDminus1=2026-03-05
RunDayTag=WEEKEND | UsedDateStatus=OK_LATEST
freshness_ok=True | freshness_age_days=2
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
