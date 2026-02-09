# Roll25 Cache Report (TWSE Turnover)
## 1) Summary
- generated_at_utc: `2026-02-09T07:37:10Z`
- generated_at_local: `2026-02-09T15:37:10.052487+08:00`
- report_date_local: `2026-02-09`
- timezone: `Asia/Taipei`
- as_of_data_date: `2026-02-06` (latest available)
- data_age_days: `3` (warn_if > 2)
- ⚠️ staleness_warning: as_of_data_date is 3 days behind report_date_local (可能跨週末/長假；請避免當作「今日盤後」解讀)
- RunDayTag: `WEEKDAY`
- summary: 今日資料未更新；UsedDate=2026-02-06：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet

## 2) Key Numbers (from latest_report.json)
- turnover_twd: `700313173141`
- close: `31782.92`
- pct_change: `-0.057702`
- amplitude_pct: `2.133059`
- volume_multiplier_20: `0.888196`

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
| TURNOVER_TWD | 700313173141 | 0.442108 | 62.5 | 1.589529 | 90.674603 | -0.19945 | 47.5 | -2.077207 | OK |
| CLOSE | 31782.92 | 1.275874 | 84.166667 | 2.059775 | 96.230159 | -0.234182 | 35.833333 | -0.057702 | OK |
| PCT_CHANGE_CLOSE | -0.057702 | -0.229984 | 35.833333 | -0.133628 | 40.674603 | NA | NA | NA | OK |
| AMPLITUDE_PCT | 2.133059 | 2.037467 | 97.5 | 1.286706 | 94.246032 | NA | NA | NA | OK |
| VOL_MULTIPLIER_20 | 0.888196 | -0.889446 | 20.833333 | -0.743347 | 19.642857 | NA | NA | NA | OK |

## 5.1) Volatility Bands (sigma; approximation)
- sigma_win_list_input: `20,60`
- sigma_win_list_effective: `20,60` (includes sigma_base_win + 20 + 60 for audit stability)
- sigma_base_win: `60` (BASE bands)
- T list (trading days): `10,12,15`
- level anchor: `31782.92` (source: latest_report.Close)

- sigma20_daily_%: `1.094758` (reason: `OK`)
- sigma60_daily_%: `1.216175` (reason: `OK`)

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.216175 | 3.845882 | 30560.586267 | 29772.181009 | 29387.145884 | 29338.252534 | 33005.253733 | 33793.658991 | 34178.694116 | 34227.587466 | OK |  |
| 12 | 1.216175 | 4.212953 | 30443.920483 | 29580.265795 | 29158.480947 | 29104.920967 | 33121.919517 | 33985.574205 | 34407.359053 | 34460.919033 | OK |  |
| 15 | 1.216175 | 4.710225 | 30285.87303 | 29320.277734 | 28848.707938 | 28788.826059 | 33279.96697 | 34245.562266 | 34717.132062 | 34777.013941 | OK |  |

### 5.1.a) Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.216175 | 3.845882 | ±3.845882 | ±6.326477 | ±7.53793 | ±7.691765 | OK |  |
| 12 | 1.216175 | 4.212953 | ±4.212953 | ±6.930308 | ±8.257388 | ±8.425906 | OK |  |
| 15 | 1.216175 | 4.710225 | ±4.710225 | ±7.74832 | ±9.232041 | ±9.42045 | OK |  |

## 5.2) Stress Bands (regime-shift guardrail; heuristic)
- sigma_stress_daily_%: `1.824262` (chosen_win=60; policy: primary=max(60,20) else fallback=max(effective) )
- stress_mult: `1.5`

| T | sigma_daily_% | sigma_T_% | down_1σ | down_95%(1-tail) | down_95%(2-tail) | down_2σ | up_1σ | up_95%(1-tail) | up_95%(2-tail) | up_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.824262 | 5.768824 | 29949.419401 | 28766.811514 | 28189.258825 | 28115.918801 | 33616.420599 | 34799.028486 | 35376.581175 | 35449.921199 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.824262 | 6.31943 | 29774.420725 | 28478.938693 | 27846.261421 | 27765.92145 | 33791.419275 | 35086.901307 | 35719.578579 | 35799.91855 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.824262 | 7.065337 | 29537.349544 | 28088.9566 | 27381.601907 | 27291.779089 | 34028.490456 | 35476.8834 | 36184.238093 | 36274.060911 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

### 5.2.a) Stress Band % Mapping (display-only; prevents confusing points with %)
| T | sigma_daily_% | sigma_T_% | pct_1σ | pct_95%(1-tail) | pct_95%(2-tail) | pct_2σ | confidence | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.824262 | 5.768824 | ±5.768824 | ±9.489715 | ±11.306894 | ±11.537647 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 12 | 1.824262 | 6.31943 | ±6.31943 | ±10.395462 | ±12.386082 | ±12.638859 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |
| 15 | 1.824262 | 7.065337 | ±7.065337 | ±11.62248 | ±13.848061 | ±14.130674 | OK | policy=primary:max(sigma60,sigma20)*mult chosen_win=60 stress_mult=1.5 |

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
- AnchorClose: `31782.92` (source: roll25@UsedDate.close)
- PrevClose(strict): `31801.27`
- ret1_log_pct(abs): `0.057719`
- sigma_log_60_daily_%: `1.217219` (reason: `OK`)
- sigma_target_daily_% (Rule A): `1.217219`
- confidence: `OK`
- notes: `anchor_source=roll25@UsedDate.close; vol_mult_source=latest_report.VolumeMultiplier`

### 5.3.b) Risk Bands
| band | z | formula | point | close_confirm_rule |
| --- | --- | --- | --- | --- |
| Band 1 (normal) | 1 | P*exp(-z*sigma) | 31398.397135 | Close >= 31398.397135 => PASS else NOTE/FAIL |
| Band 2 (stress) | 2 | P*exp(-z*sigma) | 31018.526386 | Close <  31018.526386 => FAIL (do not catch knife) |

### 5.3.c) Health Check (deterministic)
| item | value | rule | status |
| --- | --- | --- | --- |
| Volume_Mult_20 | 0.888196 | <= 1.0 PASS; (1.0,1.3) NOTE; >= 1.3 FAIL | PASS |
| Price Structure | 31782.92 | Close>=B1 PASS; B2<=Close<B1 NOTE; Close<B2 FAIL | PASS |
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
- Anchor clarity: level_anchor=31782.92 (for bands) vs anchor_close=31782.92 (for risk check)
  - anchors_match: `true` ; abs_diff: `0`
- EXTRA_AUDIT_NOTES:
  - VOL_MULT_20 window diag: win=20 min_points=15 len_turnover=284 computed=269 na_invalid_a=0 na_no_tail=1 na_insufficient_window=14 na_zero_avg=0

## 7) Caveats / Sources (from latest_report.json)
```
Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-06 | UsedDminus1=2026-02-05
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=3
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
GUARDRAIL: retry/backoff enabled; monthly fallback for current month; cache-only degrade supported; cache-preserving merge (None does not overwrite).
```
