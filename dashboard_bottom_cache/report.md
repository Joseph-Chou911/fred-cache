# Bottom Cache Dashboard (v0)

- as_of_ts (TPE): `2026-01-27T14:59:00.580562+08:00`
- run_ts_utc: `2026-01-27T06:59:00.580550Z`
- bottom_state (Global): **NONE**  (streak=3)
- market_cache_as_of_ts: `2026-01-27T04:17:10Z`
- market_cache_generated_at_utc: `2026-01-27T04:17:10Z`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)
- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）

## Distance to Triggers (How far from activation) - Global
- VIX panic gap = 20.0 - 16.15 = **3.8500**  (<=0 means triggered)
- SP500 ret1% gap = 0.5006065986948351 - (-1.5) = **2.0006**  (<=0 means triggered)
- HYG veto gap (z) = 1.7318916416182217 - (-2.0) = **3.7319**  (<=0 means systemic veto)
- OFR veto gap (z) = (2.0) - -0.8136912270406668 = **2.8137**  (<=0 means systemic veto)

### Nearest Conditions (Top-2) - Global
- SP500 ret1% gap (<=0 triggered): `2.0006`
- OFR veto gap z (<=0 veto): `2.8137`

## Context (Non-trigger) - Global
- SP500.p252 = `98.8095`; equity_extreme(p252>=95) = `1`
- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）

## Triggers (0/1/NA) - Global
- TRIG_PANIC: `0`
- TRIG_SYSTEMIC_VETO: `0`
- TRIG_REVERSAL: `0`

## TW Local Gate (roll25 + margin)
- tw_state: **NA**  (streak=1)
- UsedDate: `2026-01-26`; run_day_tag: `WEEKDAY`; risk_level: `NA`
- Lookback: `20/None`
- margin_signal(TWSE): `WATCH`; unit: `億`
- margin_balance(TWSE latest): `3815.8` 億
- margin_chg(TWSE latest): `55.0` 億

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `None`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))
- TRIG_TW_LEVERAGE_HEAT: `1`  (margin_signal∈{WATCH,ALERT})
- TRIG_TW_REVERSAL: `0`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)

### TW Distances / Gating
- pct_change_to_nonnegative_gap: `0.322`
- lookback_missing_points: `NA`

### TW Snapshot (key fields)
- pct_change: `0.322294`; amplitude_pct: `0.64731`; turnover_twd: `747339306040.0`; close: `32064.52`
- signals: DownDay=False, VolumeAmplified=None, VolAmplified=None, NewLow_N=None, ConsecutiveBreak=None

## Excluded / NA Reasons
- TRIG_TW_PANIC: missing_fields:roll25.signal.*

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
| 2026-01-27 | 2026-01-27T14:59:00.580562+08:00 | NONE | 0 | 0 | 0 | NA | None | 1 | 0 | equity_extreme |

## Series Snapshot (Global)
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-26 | 16.15 | -0.36085631266913765 | 30.158730158730158 | 0.3729024238657472 | 0.02723975338937812 | 1.6666666666666643 |
| SP500 | LOW | INFO | 2026-01-26 | 6950.23 | 1.2148554889307452 | 98.80952380952381 | 0.5006065986948351 | 0.3470418017456982 | 13.333333333333329 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-26 | 0.8448329690914768 | 1.7318916416182217 | 75.79365079365078 | -0.09647105702835386 | -0.24042533428908808 | -3.333333333333343 |
| OFR_FSI | HIGH | NONE | 2026-01-22 | -2.68 | -0.8136912270406668 | 7.142857142857142 | -9.611451942740299 | -0.6451549078442044 | -18.333333333333336 |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`  (unit: 億)
- This dashboard does not fetch external URLs directly.
