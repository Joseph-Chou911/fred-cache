# Bottom Cache Dashboard (v0)

- as_of_ts (TPE): `2026-01-31T01:21:50.557420+08:00`
- run_ts_utc: `2026-01-30T17:21:50.557410Z`
- bottom_state (Global): **NONE**  (streak=6)
- market_cache_as_of_ts: `2026-01-30T05:01:20Z`
- market_cache_generated_at_utc: `2026-01-30T05:01:20Z`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)
- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）

## Distance to Triggers (How far from activation) - Global
- VIX panic gap = 20.0 - 16.88 = **3.1200**  (<=0 means triggered)
- SP500 ret1% gap = -0.1292628435245983 - (-1.5) = **1.3707**  (<=0 means triggered)
- HYG veto gap (z) = 1.389844661581545 - (-2.0) = **3.3898**  (<=0 means systemic veto)
- OFR veto gap (z) = (2.0) - 0.04015865453224352 = **1.9598**  (<=0 means systemic veto)

### Nearest Conditions (Top-2) - Global
- SP500 ret1% gap (<=0 triggered): `1.3707`
- OFR veto gap z (<=0 veto): `1.9598`

## Context (Non-trigger) - Global
- SP500.p252 = `98.8095`; equity_extreme(p252>=95) = `1`
- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）

## Triggers (0/1/NA) - Global
- TRIG_PANIC: `0`
- TRIG_SYSTEMIC_VETO: `0`
- TRIG_REVERSAL: `0`

## TW Local Gate (roll25 + margin)
- tw_state: **TW_BOTTOM_WATCH**  (streak=1)
- UsedDate: `2026-01-29`; run_day_tag: `WEEKDAY`; risk_level: `NA`
- Lookback: `20/None`
- margin_signal(TWSE): `NONE`; unit: `億`
- margin_balance(TWSE latest): `3838.9` 億
- margin_chg(TWSE latest): `21.2` 億

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `1`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))
- TRIG_TW_LEVERAGE_HEAT: `0`  (margin_signal∈{WATCH,ALERT})
- TRIG_TW_REVERSAL: `0`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)

### TW Distances / Gating
- pct_change_to_nonnegative_gap: `-0.816`
- lookback_missing_points: `NA`

### TW Snapshot (key fields)
- pct_change: `-0.815606`; amplitude_pct: `1.596095`; turnover_twd: `959652045839.0`; close: `32536.27`
- signals: DownDay=True, VolumeAmplified=False, VolAmplified=False, NewLow_N=False, ConsecutiveBreak=True

## Action Map (v0)
- Global NONE: 維持既定 DCA/資產配置紀律；不把它當成抄底時點訊號
- Global BOTTOM_WATCH: 只做準備（現金/分批計畫/撤退條件），不進場
- Global BOTTOM_CANDIDATE: 允許分批（例如 2–3 段），但需設定撤退條件
- Global PANIC_BUT_SYSTEMIC: 不抄底，先等信用/壓力解除
- TW Local Gate: 若 TW_BOTTOM_CANDIDATE 才允許把「台股加碼」推進到執行層；否則僅做準備

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | note |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|
| 2026-01-25 | 2026-01-25T19:40:31.851190+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-26 | 2026-01-26T16:06:45.700719+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-27 | 2026-01-27T23:58:59.954073+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | None | 0 | equity_extreme |
| 2026-01-29 | 2026-01-29T01:08:17.402179+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-30 | 2026-01-30T01:25:46.779800+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-31 | 2026-01-31T01:21:50.557420+08:00 | NONE | 0 | 0 | 0 | TW_BOTTOM_WATCH | 1 | 0 | 0 | equity_extreme |

## Series Snapshot (Global)
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-29 | 16.88 | -0.06666986762878879 | 46.82539682539682 | 3.241590214067263 | 0.20824601888684496 | 11.666666666666671 |
| SP500 | LOW | INFO | 2026-01-29 | 6969.01 | 1.2854828306091972 | 98.80952380952381 | -0.1292628435245983 | -0.13252833362952088 | -3.3333333333333286 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-29 | 0.8440625 | 1.389844661581545 | 73.4126984126984 | -0.11649339832181196 | -0.23127779129627912 | -3.3333333333333286 |
| OFR_FSI | HIGH | NONE | 2026-01-27 | -2.383 | 0.04015865453224352 | 23.015873015873016 | 3.83373688458435 | 0.2777046371315133 | 20.0 |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`  (unit: 億)
- This dashboard does not fetch external URLs directly.
