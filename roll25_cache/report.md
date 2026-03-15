# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-03-15T03:28:25Z`
- generated_at_local: `2026-03-15T11:28:25.931015+08:00`
- report_date_local: `2026-03-15`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-03-13` (latest available)
- data_age_days: `2` (warn_if > 2)
- RunDayTag: `WEEKEND`
- summary: 今日為週末；UsedDate=2026-03-13：Mode=FULL；freshness_ok=True

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `752682671944`
- close: `33400.32`
- pct_change: `-0.540589`
- amplitude_pct: `1.863268`
- volume_multiplier_20: `0.901721`

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
| TURNOVER_TWD | 752682671944 | 0.170278 | 55.833333 | 1.41526 | 89.484127 | -0.353079 | 35.833333 | -3.995461 | OK |
| CLOSE | 33400.32 | 1.003814 | 80.833333 | 1.952598 | 95.436508 | -0.544301 | 22.5 | -0.540589 | OK |
| PCT_CHANGE_CLOSE | -0.540589 | -0.553102 | 22.5 | -0.435728 | 26.785714 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 1.863268 | 0.466446 | 67.5 | 0.728001 | 85.515873 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.901721 | -0.923528 | 22.5 | -0.66888 | 26.388889 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `33400.32` (source: latest_report.Close)

- sigma20_daily_%: `2.223114` (reason: `OK`)
- sigma60_daily_%: `1.532979` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.532979 | 4.847704 | 31781.171392 | 30736.820541 | 30226.788729 | 30162.022785 | 35019.468608 | 36063.819459 | 36573.851271 | 36638.617215 | OK |  |
| 12 | 1.532979 | 5.310394 | 31626.631567 | 30482.602528 | 29923.890672 | 29852.943135 | 35174.008433 | 36318.037472 | 36876.749328 | 36947.696865 | OK |  |
| 15 | 1.532979 | 5.9372 | 31417.276047 | 30138.212697 | 29513.553852 | 29434.232094 | 35383.363953 | 36662.427303 | 37287.086148 | 37366.407906 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.532979 | 4.847704 | ±4.847704 | ±7.974473 | ±9.5015 | ±9.695408 | OK |  |
| 12 | 1.532979 | 5.310394 | ±5.310394 | ±8.735597 | ±10.408371 | ±10.620787 | OK |  |
| 15 | 1.532979 | 5.9372 | ±5.9372 | ±9.766695 | ±11.636913 | ±11.874401 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `3.334671` (chosen_win=20; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 3.334671 | 10.545156 | 29878.204196 | 27606.439502 | 26496.973023 | 26356.088391 | 36922.435804 | 39194.200498 | 40303.666977 | 40444.551609 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 3.334671 | 11.551639 | 29542.035448 | 27053.441911 | 25838.082277 | 25683.750895 | 37258.604552 | 39747.198089 | 40962.557723 | 41116.889105 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 3.334671 | 12.915126 | 29086.626732 | 26304.294574 | 24945.481195 | 24772.933464 | 37714.013268 | 40496.345426 | 41855.158805 | 42027.706536 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 3.334671 | 10.545156 | ±10.545156 | ±17.346781 | ±20.668506 | ±21.090312 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 12 | 3.334671 | 11.551639 | ±11.551639 | ±19.002447 | ±22.641213 | ±23.103279 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |
| 15 | 3.334671 | 12.915126 | ±12.915126 | ±21.245382 | ±25.313646 | ±25.830251 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=20 stress_mult=1.5 |

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
- AnchorClose: `33400.32` (source: roll25@UsedDate.close)
- PrevClose(strict): `33581.86`
- ret1_log_pct(abs): `0.542056`
- sigma_log_60_daily_%: `1.536323` (reason: `OK`)
- sigma_target_daily_% (Rule A): `1.536323`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 32891.104722 | Close >= 32891.104722 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 32389.652849 | Close <  32389.652849 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.901721 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 33400.32 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- Anchor clarity: level_anchor=33400.32 (for bands) vs anchor_close=33400.32 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=301 computed=286 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-03-13 | UsedDminus1=2026-03-12
RunDayTag=WEEKEND | UsedDateStatus=OK_LATEST
freshness_ok=True | freshness_age_days=2
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
